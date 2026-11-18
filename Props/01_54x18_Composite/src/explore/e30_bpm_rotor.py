"""Exploration 30: absolute broadband (BPM TBL-TE) hover noise of the tri and hex, against the Gutin tones.

Entry 29 compared broadband by scaling only. Here BPM's trailing-edge model (bpm.py, NASA RP-1218, validated against the
report's own Figure 44 predictions for a 30.48 cm NACA 0012 at 31.7-71.3 m/s) is applied strip by strip to the hovering
rotors of entry 28 (best-camber blades at tip-Mach caps 0.45-0.60):
  each strip: chord c, span dr, local speed W, effective angle alpha* = alpha - alpha_L0 (angle from zero lift; BPM is
  built on the symmetric NACA 0012, so this is the usual way to apply it to cambered sections), untripped BL fits;
  observer at 50 m, 30 deg below the disk plane (theta = 120 deg from the thrust axis, near the loudest tonal direction);
  directivity D_h evaluated in each strip's own trailing-edge frame and averaged over the azimuth (the blade passes the
  observer once per revolution; time-averaged mean square); Doppler frequency shift neglected;
  n rotors x B blades x strips added incoherently; 1/3-octave bands 100 Hz - 20 kHz; A-weighted.
Compared with the Gutin tonal level at the same observer (entry 27 model).

Hand check: one representative strip (0.75 R) by hand: peak level = 10 log10(delta* M^5 L D_h / r^2) + K1 - 3 for each
side (A = 0 at the peak Strouhal number), times N_strips-equivalent and n B blades.
"""
import json, math, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import bemt
import bpm
import e01_coax_blade as e01
import e02_coax_two_point as e02
import e24_chain_best_blades as e24
import e27_rotor_noise as e27
from common import RESULTS, save_json

OUT = os.path.join(RESULTS, "explore")
S_OBS, THETA = 50.0, math.radians(120.0)
NPSI = 24
LAY = {"tri": ("tri", 3), "hex": ("hex0", 6)}
AW = np.array([e27.a_weight(f) for f in bpm.BANDS])


def alpha_l0(db, tc, re, mach):
    al = np.radians(np.arange(-8, 4, 0.05)); cl, _ = db.lookup(np.full_like(al, tc), np.full_like(al, re), np.full_like(al, mach), al)
    return float(np.degrees(np.interp(0.0, cl, al)))


def rotor_bpm(c, bd):
    G = e01.G; p, hot = G["p"], G["hot"]; W = G["ph1"]["vehicle"]["weight_n"]; n = LAY[c][1]
    db = e24.db_for(LAY[c][0], "best"); Rr = p["rotor"]["diameter_in"] * p["constants"]["inch_to_m"] / 2
    b = e02.blade_from(bd, Rr, p["rotor"]["hub_radius_m"]); h = bemt.hover_at_thrust(b, db, hot, W / n)
    obs = np.array([math.sin(THETA), 0.0, math.cos(THETA)]) * S_OBS      # rotor axis = +z (thrust), observer below
    msq = np.zeros(len(bpm.BANDS)); strips = []
    for k in range(len(h["r"])):
        r, dr, ch, w, tc = float(h["r"][k]), float(h["dr"][k]), float(h["chord"][k]), float(h["W"][k]), float(h["tc"][k])
        if w <= 1 or r < 0.25 * Rr: continue                              # inboard strips: negligible (W^5)
        a0 = alpha_l0(db, tc, float(h["re"][k]), min(float(h["mach"][k]), 0.6))
        astar = float(np.degrees(h["alpha"][k])) - a0
        acc = np.zeros(len(bpm.BANDS))
        for j in range(NPSI):
            psi = 2 * math.pi * j / NPSI
            pos = np.array([r * math.cos(psi), r * math.sin(psi), 0.0])
            tang = np.array([-math.sin(psi), math.cos(psi), 0.0])          # blade velocity direction
            xe, ye, ze = -tang, pos / r, np.array([0.0, 0.0, 1.0])         # TE frame: x downstream, y span, z normal
            d = obs - pos; re_ = float(np.linalg.norm(d)); x, y, z = d @ xe, d @ ye, d @ ze
            phi = math.atan2(math.hypot(z, 0.0) if z >= 0 else abs(z), y) if abs(y) > 1e-9 else math.pi / 2
            phi = math.atan2(abs(z), y)
            theta = math.atan2(y * math.cos(phi) + abs(z) * math.sin(phi), x)
            o = bpm.tbl_te(ch, dr, w, astar, re_, theta=theta, phi=phi, c0=hot["a"], nu=hot["mu"] / hot["rho"])
            acc += 10 ** (o["total"] / 10)
        acc /= NPSI; msq += acc
        strips.append({"r_over_R": r / Rr, "W": w, "c": ch, "alpha_star": astar, "oaspl": 10 * math.log10(acc.sum()), "dstar_s_mm": 1000 * o["dstar_s"], "Rc": o["Rc"]})
    msq *= n * b.N
    spl = 10 * np.log10(msq); oaspl = 10 * math.log10(msq.sum()); dba = 10 * math.log10((msq * 10 ** (AW / 10)).sum())
    ton = e27.levels(h, b.N, hot["a"], n, THETA)
    return {"rpm": h["rpm"], "spectrum": spl.tolist(), "oaspl": oaspl, "dba": dba, "f_peak": float(bpm.BANDS[int(np.argmax(spl))]),
            "tonal_oaspl": ton["oaspl"], "tonal_dba": ton["dba"], "total_dba": 10 * math.log10(10 ** (dba / 10) + 10 ** (ton["dba"] / 10)), "strips": strips, "n": n, "B": b.N}


def run():
    e01.init(); e28 = json.load(open(os.path.join(OUT, "e28_noise_cap.json")))
    rows = []
    for r in e28["rows"]:
        x = rotor_bpm(r["layout"], r["blade"]); x.update({"layout": r["layout"], "cap": r["cap"], "dpayload_vs_060": r["dpayload_vs_060"]}); rows.append(x)
        print(f"  {r['layout']} cap {r['cap']:.2f}: rpm {x['rpm']:.0f}; broadband {x['oaspl']:.1f} dB / {x['dba']:.1f} dBA (peak {x['f_peak']:.0f} Hz);"
              f" tonal {x['tonal_oaspl']:.1f} dB / {x['tonal_dba']:.1f} dBA; total {x['total_dba']:.1f} dBA", flush=True)
    # hand check at the 0.75 R strip of the tri, cap 0.60
    t = next(x for x in rows if x["layout"] == "tri" and x["cap"] == 0.60)
    s = min(t["strips"], key=lambda q: abs(q["r_over_R"] - 0.75))
    out = {"observer_m": S_OBS, "theta_deg": 120.0, "bands_hz": bpm.BANDS.tolist(), "rows": rows, "hand_strip_tri_060": s}
    # equal-total-noise parity: tri payload at the hex's cap-0.60 total dBA
    tri = sorted((x for x in rows if x["layout"] == "tri"), key=lambda x: x["cap"]); hx = next(x for x in rows if x["layout"] == "hex" and x["cap"] == 0.60)
    xs = [x["total_dba"] for x in tri]; ys = [x["dpayload_vs_060"] for x in tri]
    out["parity_total"] = {"hex_total_dba": hx["total_dba"], "tri_dpayload": float(np.interp(hx["total_dba"], xs, ys)) if xs[0] <= hx["total_dba"] <= xs[-1] else (0.0 if hx["total_dba"] > xs[-1] else None)}
    print(f"  parity on total dBA: {out['parity_total']}; hand strip: {s}")
    save_json(os.path.join("explore", "e30_bpm_rotor.json"), out); plot(out)
    print("  wrote results/explore/e30_bpm_rotor.json")


def plot(o):
    fig, axs = plt.subplots(1, 2, figsize=(10, 3.6)); col = {"tri": "#0b0b0b", "hex": "#2a78d6"}; F = o["bands_hz"]
    for x in o["rows"]:
        if x["cap"] == 0.60: axs[0].semilogx(F, x["spectrum"], "-", color=col[x["layout"]], label=f"{x['layout']} broadband (BPM)")
    axs[0].set_xlabel("1/3-octave band [Hz]"); axs[0].set_ylabel("SPL [dB] at 50 m, 30 deg below disk"); axs[0].grid(alpha=.3, which="both"); axs[0].legend(fontsize=7)
    for c in ("tri", "hex"):
        rs = sorted((x for x in o["rows"] if x["layout"] == c), key=lambda x: x["cap"])
        axs[1].plot([x["total_dba"] for x in rs], [x["dpayload_vs_060"] for x in rs], "o-", color=col[c], label=f"{c} tonal + broadband")
        axs[1].plot([x["tonal_dba"] for x in rs], [x["dpayload_vs_060"] for x in rs], "o:", color=col[c], alpha=.5, label=f"{c} tonal only")
    axs[1].set_xlabel("hover level [dBA] at 50 m"); axs[1].set_ylabel("payload vs own cap-0.60 optimum [kg]"); axs[1].legend(fontsize=6); axs[1].grid(alpha=.3)
    fig.suptitle("Exploration 30: BPM trailing-edge broadband vs Gutin tones (hover)", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "e30_bpm_rotor.png"), dpi=140); plt.close(fig)


if __name__ == "__main__":
    run()

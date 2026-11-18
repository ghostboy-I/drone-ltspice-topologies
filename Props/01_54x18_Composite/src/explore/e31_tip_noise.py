"""Exploration 31: blade-tip vortex formation noise (BPM section 5.3) added to entry 30's trailing-edge broadband and the
Gutin tones, for the tri and hex hover rotors of entry 28.

BPM eqs. (61)-(67), implemented in bpm.tip_vortex and checked against the report's Figure 91 prediction:
    SPL_TIP = 10 log(M^2 Mmax^3 l^2 D_h / r_e^2) - 30.5 (log St'' + 0.3)^2 + 126,   St'' = f l / Umax
    l/c = 0.008 alpha'_TIP (rounded tip)  or  0.0378 + 0.0095 alpha'_TIP (flat tip, alpha' > 2 deg)
    Mmax/M = 1 + 0.036 alpha'_TIP,  Umax = c0 Mmax
alpha'_TIP (eq. 66) is the tip angle scaled by the ratio of the tip lift gradient dL'/dy to that of the report's
reference wing. That ratio cannot be evaluated without the reference wing's loading, so the base case takes the ratio as 1
and uses the zero-lift angle of attack alpha* of the outermost BEMT strip (which already includes Prandtl's tip-loss
inflow); a sensitivity band of 0.5-1.5 on the ratio is reported. One tip source per blade, at r = R, observer and
azimuth averaging as in entry 30, n B incoherent, A-weighted.
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
import e30_bpm_rotor as e30
from common import RESULTS, save_json

OUT = os.path.join(RESULTS, "explore")
RATIOS = (0.5, 1.0, 1.5)


def dba(msq):
    return 10 * math.log10((np.asarray(msq) * 10 ** (e30.AW / 10)).sum())


def tip_rotor(c, bd):
    G = e01.G; p, hot = G["p"], G["hot"]; W = G["ph1"]["vehicle"]["weight_n"]; n = e30.LAY[c][1]
    db = e24.db_for(e30.LAY[c][0], "best"); Rr = p["rotor"]["diameter_in"] * p["constants"]["inch_to_m"] / 2
    b = e02.blade_from(bd, Rr, p["rotor"]["hub_radius_m"]); h = bemt.hover_at_thrust(b, db, hot, W / n)
    k = int(np.argmax(h["r"]))
    ch, w, tc = float(h["chord"][k]), float(h["W"][k]), float(h["tc"][k])
    astar_edge = float(np.degrees(h["alpha"][k])) - e30.alpha_l0(db, tc, float(h["re"][k]), min(float(h["mach"][k]), 0.6))
    # tip vortex strength = the peak bound circulation Gamma = W c Cl / 2: take alpha' at the max-Gamma station
    clv = np.array([db.lookup(np.array([h["tc"][i]]), np.array([h["re"][i]]), np.array([min(h["mach"][i], 0.6)]), np.array([h["alpha"][i]]))[0][0] for i in range(len(h["r"]))])
    gam = 0.5 * np.asarray(h["W"]) * np.asarray(h["chord"]) * clv; m = int(np.argmax(gam))
    astar_gam = float(np.degrees(h["alpha"][m])) - e30.alpha_l0(db, float(h["tc"][m]), float(h["re"][m]), min(float(h["mach"][m]), 0.6))
    wtip = h["rpm"] * 2 * math.pi / 60 * Rr                                   # source speed at the tip itself
    obs = np.array([math.sin(e30.THETA), 0.0, math.cos(e30.THETA)]) * e30.S_OBS
    out = {"r_over_R_strip": float(h["r"][k]) / Rr, "chord_tip": ch, "W_tip": wtip, "alpha_star_tip": astar_edge, "rpm": h["rpm"],
           "gamma_max": float(gam[m]), "r_over_R_gamma_max": float(h["r"][m]) / Rr, "alpha_star_gamma_max": astar_gam, "gamma_tip_strip": float(gam[k])}
    for shape, ratio in [(s_, r_) for s_ in ("rounded", "flat") for r_ in RATIOS] + [("rounded", "G"), ("flat", "G")]:
            astar = astar_gam if ratio == "G" else astar_edge; ratio = 1.0 if ratio == "G" else ratio; tag = "G" if astar is astar_gam else ratio
            acc = np.zeros(len(bpm.BANDS))
            for j in range(e30.NPSI):
                psi = 2 * math.pi * j / e30.NPSI
                pos = np.array([Rr * math.cos(psi), Rr * math.sin(psi), 0.0]); tang = np.array([-math.sin(psi), math.cos(psi), 0.0])
                xe, ye, ze = -tang, pos / Rr, np.array([0.0, 0.0, 1.0])
                d = obs - pos; re_ = float(np.linalg.norm(d)); x, y, z = d @ xe, d @ ye, d @ ze
                phi = math.atan2(abs(z), y); theta = math.atan2(y * math.cos(phi) + abs(z) * math.sin(phi), x)
                o = bpm.tip_vortex(ch, wtip, ratio * astar, re_, theta, phi, c0=hot["a"], rounded=(shape == "rounded"))
                acc += 10 ** (o["spl"] / 10)
            msq = acc / e30.NPSI * n * b.N
            out[f"{shape}_{tag}"] = {"spectrum": (10 * np.log10(msq)).tolist(), "oaspl": 10 * math.log10(msq.sum()), "dba": dba(msq),
                                       "l_mm": 1000 * o["l"], "f_peak": o["f_peak"]}
    return out


def run():
    e01.init()
    e28 = json.load(open(os.path.join(OUT, "e28_noise_cap.json"))); e30j = json.load(open(os.path.join(OUT, "e30_bpm_rotor.json")))
    rows = []
    for r in e28["rows"]:
        t = tip_rotor(r["layout"], r["blade"])
        te = next(x for x in e30j["rows"] if x["layout"] == r["layout"] and x["cap"] == r["cap"])
        te_msq = 10 ** (np.array(te["spectrum"]) / 10)
        for key in [k for k in t if k.startswith(("rounded", "flat"))]:
            tip_msq = 10 ** (np.array(t[key]["spectrum"]) / 10)
            t[key]["broadband_dba"] = dba(te_msq + tip_msq)
            t[key]["total_dba"] = 10 * math.log10(10 ** (t[key]["broadband_dba"] / 10) + 10 ** (te["tonal_dba"] / 10))
        t.update({"layout": r["layout"], "cap": r["cap"], "dpayload_vs_060": r["dpayload_vs_060"], "te_dba": te["dba"], "tonal_dba": te["tonal_dba"], "e30_total_dba": te["total_dba"]})
        rows.append(t)
        f = t["flat_G"]; g = t["rounded_G"]
        print(f"  {r['layout']} cap {r['cap']:.2f}: tip c {1000*t['chord_tip']:.0f} mm, alpha* edge {t['alpha_star_tip']:.2f}, at Gmax (r/R {t['r_over_R_gamma_max']:.2f}) {t['alpha_star_gamma_max']:.2f} deg;"
              f" edge-angle tip noise flat {t['flat_1.0']['dba']:.1f} dBA; Gmax-angle:"
              f" tip noise rounded {g['dba']:.1f} / flat {f['dba']:.1f} dBA (TE {t['te_dba']:.1f}); total flat {f['total_dba']:.1f} vs e30 {t['e30_total_dba']:.1f}", flush=True)
    out = {"rows": rows, "ratios": RATIOS, "parity": {}}
    for key in ("rounded_1.0", "flat_1.0", "flat_1.5", "rounded_G", "flat_G"):
        tri = sorted((x for x in rows if x["layout"] == "tri"), key=lambda x: x["cap"]); hx = next(x for x in rows if x["layout"] == "hex" and x["cap"] == 0.60)
        xs = [x[key]["total_dba"] for x in tri]; ys = [x["dpayload_vs_060"] for x in tri]; lim = hx[key]["total_dba"]
        out["parity"][key] = {"hex_total_dba": lim, "tri_total_dba": tri[-1][key]["total_dba"], "tri_dpayload": float(np.interp(lim, xs, ys)) if xs[0] <= lim <= xs[-1] else None}
    print("  parity:", json.dumps(out["parity"], indent=1))
    save_json(os.path.join("explore", "e31_tip_noise.json"), out); plot(out, e30j)
    print("  wrote results/explore/e31_tip_noise.json")


def plot(o, e30j):
    fig, axs = plt.subplots(1, 2, figsize=(10, 3.6)); col = {"tri": "#0b0b0b", "hex": "#2a78d6"}; F = bpm.BANDS
    for x in o["rows"]:
        if x["cap"] != 0.60: continue
        te = next(y for y in e30j["rows"] if y["layout"] == x["layout"] and y["cap"] == 0.60)
        axs[0].semilogx(F, te["spectrum"], "-", color=col[x["layout"]], label=f"{x['layout']} trailing edge")
        axs[0].semilogx(F, x["flat_G"]["spectrum"], "--", color=col[x["layout"]], label=f"{x['layout']} tip vortex (flat, max-Gamma angle)")
        axs[0].semilogx(F, x["rounded_G"]["spectrum"], ":", color=col[x["layout"]], label=f"{x['layout']} tip vortex (rounded, max-Gamma angle)")
    axs[0].set_xlabel("1/3-octave band [Hz]"); axs[0].set_ylabel("SPL [dB] at 50 m, 30 deg below disk"); axs[0].set_ylim(0, 50); axs[0].grid(alpha=.3, which="both"); axs[0].legend(fontsize=6)
    for c in ("tri", "hex"):
        rs = sorted((x for x in o["rows"] if x["layout"] == c), key=lambda x: x["cap"])
        axs[1].plot([x["e30_total_dba"] for x in rs], [x["dpayload_vs_060"] for x in rs], "o:", color=col[c], alpha=.5, label=f"{c} TE + tones (entry 30)")
        axs[1].plot([x["flat_G"]["total_dba"] for x in rs], [x["dpayload_vs_060"] for x in rs], "o-", color=col[c], label=f"{c} + tip vortex (flat, max-Gamma angle)")
    axs[1].set_xlabel("hover level [dBA] at 50 m"); axs[1].set_ylabel("payload vs own cap-0.60 optimum [kg]"); axs[1].legend(fontsize=6); axs[1].grid(alpha=.3)
    fig.suptitle("Exploration 31: tip-vortex formation noise (BPM 5.3) added to trailing-edge broadband and tones", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "e31_tip_noise.png"), dpi=140); plt.close(fig)


if __name__ == "__main__":
    run()

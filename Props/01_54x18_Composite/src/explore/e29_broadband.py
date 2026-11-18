"""Exploration 29: broadband (trailing-edge) noise scaling of the tri and hex, on entry 28's cap-swept optima.

Entries 27-28 used Gutin's steady-loading tones only. For large, slow rotors the A-weighted level is often set by
broadband noise instead, mainly turbulent-boundary-layer trailing-edge (TBL-TE) noise. No calibrated broadband model is
available here (BPM needs its empirical spectra, which are not in the repo), so this entry compares the layouts by the
physical scaling of edge noise and reports level DIFFERENCES only, in dB:

  Ffowcs Williams & Hall (1970): a turbulent boundary layer convecting past a sharp edge radiates intensity per unit span
      dI ~ rho^2 W^5 delta* dr / (a r^2)            (W local section speed, delta* boundary-layer displacement thickness)
  turbulent flat plate (1/7 power law): delta* = 0.046 c Re_c^-0.2 per side, both sides counted
  peak frequency (BPM's Strouhal scaling): f_p = St W / delta*, St ~ 0.02  -> a few kHz, where A-weighting is ~0 dB
  for comparison, the Schlegel-King-Mull 'vortex noise' scaling ~ W_0.7^6 x blade area (an older empirical law)

Whole vehicle: n rotors x B blades, incoherent. Hover thrust, the entry 28 blades at each tip-Mach cap.

Hand check: the tri vs hex difference at cap 0.60 from blade count, rpm and chord alone:
    dB = 10 log10(n_t B / n_h B) + 50 log10(rpm_t / rpm_h) + 8 log10(c_t / c_h) - 2 log10(rpm_t / rpm_h)
    (delta* ~ c^0.8 W^-0.2, so W^5 delta* ~ W^4.8 c^0.8)
"""
import json, math, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import bemt
import e01_coax_blade as e01
import e02_coax_two_point as e02
import e24_chain_best_blades as e24
import e27_rotor_noise as e27
from common import RESULTS, save_json

OUT = os.path.join(RESULTS, "explore")
ST = 0.02
LAY = {"tri": ("tri", 3), "hex": ("hex0", 6)}


def broadband(c, bd):
    G = e01.G; p, hot = G["p"], G["hot"]; W = G["ph1"]["vehicle"]["weight_n"]; n = LAY[c][1]
    db = e24.db_for(LAY[c][0], "best"); Rr = p["rotor"]["diameter_in"] * p["constants"]["inch_to_m"] / 2
    b = e02.blade_from(bd, Rr, p["rotor"]["hub_radius_m"]); h = bemt.hover_at_thrust(b, db, hot, W / n)
    w, ch, dr = h["W"], h["chord"], h["dr"]; re = hot["rho"] * w * ch / hot["mu"]
    dstar = 0.046 * ch * re ** -0.2
    te = n * b.N * float(np.sum(w ** 5 * 2 * dstar * dr))
    skm = n * b.N * float(np.sum(w ** 6 * ch * dr))
    i = int(np.argmin(abs(h["r"] / Rr - 0.75)))
    fp = ST * w[i] / dstar[i]
    return {"rpm": h["rpm"], "te": te, "skm": skm, "f_peak_075": fp, "a_weight_f_peak": e27.a_weight(fp), "W_075": float(w[i]), "c_075": float(ch[i]),
            "dstar_075_mm": 1000 * float(dstar[i]), "B": b.N, "n": n, "solidity": b.solidity()}


def run():
    e01.init(); e28 = json.load(open(os.path.join(OUT, "e28_noise_cap.json")))
    rows = []
    for r in e28["rows"]:
        bb = broadband(r["layout"], r["blade"])
        rows.append({"layout": r["layout"], "cap": r["cap"], "dpayload_vs_060": r["dpayload_vs_060"], "tonal_dba": r["noise"]["hover"]["max_dba"], **bb})
    ref = next(x for x in rows if x["layout"] == "hex" and x["cap"] == 0.60)
    for x in rows:
        x["te_db_vs_hex060"] = 10 * math.log10(x["te"] / ref["te"]); x["skm_db_vs_hex060"] = 10 * math.log10(x["skm"] / ref["skm"])
        x["tonal_db_vs_hex060"] = x["tonal_dba"] - ref["tonal_dba"]
        print(f"  {x['layout']} cap {x['cap']:.2f}: rpm {x['rpm']:.0f}, sigma {x['solidity']:.3f}, dpay {x['dpayload_vs_060']:+.2f} kg; vs hex 0.60:"
              f" tonal {x['tonal_db_vs_hex060']:+.1f} dBA, TE broadband {x['te_db_vs_hex060']:+.1f} dB, SKM {x['skm_db_vs_hex060']:+.1f} dB;"
              f" f_peak(0.75R) {x['f_peak_075']:.0f} Hz (A {x['a_weight_f_peak']:+.1f} dB), delta* {x['dstar_075_mm']:.2f} mm, W {x['W_075']:.0f} m/s, c {1000*x['c_075']:.0f} mm")
    t6 = next(x for x in rows if x["layout"] == "tri" and x["cap"] == 0.60)
    rr = t6["rpm"] / ref["rpm"]; cr = t6["c_075"] / ref["c_075"]
    hc = {"blade_count_db": 10 * math.log10(3 / 6), "speed_db_50log": 50 * math.log10(rr), "chord_db_8log": 8 * math.log10(cr), "re_db_m2log": -2 * math.log10(rr)}
    hc["total_hand_db"] = sum(hc.values()); hc["model_db"] = t6["te_db_vs_hex060"]
    # where would the tri reach broadband parity with the hex: interpolate te_db against cap
    tri = sorted((x for x in rows if x["layout"] == "tri"), key=lambda x: x["cap"])
    ys = [x["te_db_vs_hex060"] for x in tri]; caps = [x["cap"] for x in tri]; pays = [x["dpayload_vs_060"] for x in tri]
    par = None
    if min(ys) <= 0 <= max(ys):
        cap_p = float(np.interp(0.0, ys, caps)); par = {"cap": cap_p, "tri_dpayload": float(np.interp(cap_p, caps, pays))}
    hc["broadband_parity"] = par
    print(f"  hand: {hc}")
    out = {"rows": rows, "hand_check": hc, "strouhal": ST}
    save_json(os.path.join("explore", "e29_broadband.json"), out); plot(out)
    print("  wrote results/explore/e29_broadband.json")


def plot(o):
    fig, axs = plt.subplots(1, 2, figsize=(10, 3.6)); col = {"tri": "#0b0b0b", "hex": "#2a78d6"}
    for c in ("tri", "hex"):
        rs = sorted((r for r in o["rows"] if r["layout"] == c), key=lambda r: r["cap"])
        caps = [r["cap"] for r in rs]
        axs[0].plot(caps, [r["tonal_db_vs_hex060"] for r in rs], "o-", color=col[c], label=f"{c} tonal (Gutin, dBA)")
        axs[0].plot(caps, [r["te_db_vs_hex060"] for r in rs], "s--", color=col[c], label=f"{c} trailing-edge broadband")
        axs[0].plot(caps, [r["skm_db_vs_hex060"] for r in rs], "^:", color=col[c], label=f"{c} SKM vortex scaling")
        axs[1].plot([r["te_db_vs_hex060"] for r in rs], [r["dpayload_vs_060"] for r in rs], "s--", color=col[c], label=f"{c}, broadband")
        axs[1].plot([r["tonal_db_vs_hex060"] for r in rs], [r["dpayload_vs_060"] for r in rs], "o-", color=col[c], label=f"{c}, tonal")
    axs[0].axhline(0, color="#888", lw=0.8); axs[0].set_xlabel("tip-Mach cap at T/W 2"); axs[0].set_ylabel("level vs hex at cap 0.60 [dB]"); axs[0].legend(fontsize=6); axs[0].grid(alpha=.3)
    axs[1].axvline(0, color="#888", lw=0.8); axs[1].set_xlabel("noise vs hex at cap 0.60 [dB]"); axs[1].set_ylabel("payload vs own cap-0.60 optimum [kg]"); axs[1].legend(fontsize=6); axs[1].grid(alpha=.3)
    fig.suptitle("Exploration 29: broadband vs tonal noise, hover, whole vehicle (differences only)", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "e29_broadband.png"), dpi=140); plt.close(fig)


if __name__ == "__main__":
    run()

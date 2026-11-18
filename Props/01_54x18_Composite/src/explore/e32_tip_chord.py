"""Exploration 32: does a bounded tip chord (plus a rounded tip) buy back the tri's tip-vortex noise penalty?

Entry 31 found that slowing the tri (lower tip-Mach cap) widens its tip (57 mm at cap 0.60 -> 110 mm at 0.45). With the
loading-based tip angle, BPM tip noise grows as l^2 with l ~ c_tip and its peak moves down into the A-weighted band, so the
tri cannot reach the hex's noise level with flat tips. Here the entry 13 tri optimiser (best-camber 44/24 hybrid blade,
torque-sized motor, 15 m/s frame as in entry 28) is re-run at caps 0.45/0.50/0.55 with an upper bound on the tip chord
(chord at r = R) of 65 and 45 mm, and each optimum is scored for total hover noise at 50 m, 30 deg below the disk:
BPM trailing edge (entry 30) + BPM tip vortex at the max-circulation angle, flat and rounded tip (entry 31) + Gutin tones.

Hand check: the l^2 scaling. At fixed tip speed and tip angle, cutting c_tip from c1 to c2 lowers the tip-noise peak by
20 log10(c1/c2) dB and raises its peak frequency by c1/c2.
"""
import json, math, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from multiprocessing import Pool
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT_NAME = "e32_tip_chord.json"
CAPS = (0.45, 0.50, 0.55)
LIMS = (0.065, 0.045)


def job(args):
    cap, lim = args
    import e01_coax_blade as e01, e02_coax_two_point as e02, e13_tri_torque_margin as e13, e24_chain_best_blades as e24
    from common import RESULTS
    e01.init(); db = e24.db_for("tri", "best"); e01.G["db"] = db; e01.G["p"]["rotor"]["tip_mach_max"] = cap
    base_shape = e02.shape

    def bounded(b, x):
        nb = base_shape(b, x)
        if float(nb.c_def[int(np.argmax(nb.r_def))]) > lim: raise ValueError("tip chord above bound")
        return nb
    e02.shape = bounded
    bd = e24.blade_for("tri", "best")
    # start inside the bound: scale the starting blade's chord linearly down toward the tip if needed
    r = np.array(bd["r"]); c = np.array(bd["chord"]); R = r.max(); ct = float(c[np.argmax(r)])
    if ct > lim * 0.98:
        k = (lim * 0.97 / ct - 1) / (1 - 0.5)                       # chord factor 1 at r/R <= 0.5, lim*0.97/ct at the tip
        c = c * np.where(r / R > 0.5, 1 + k * (r / R - 0.5), 1.0); bd = dict(bd, chord=c.tolist())
    t0 = time.time()
    try:
        res = e13.optimise((f"tri M{cap:.2f} ctip<={1000*lim:.0f}mm", bd))
    finally:
        e02.shape = base_shape
    ref = json.load(open(os.path.join(RESULTS, "explore", "e13_tri_torque_margin.json")))["reference"]
    whkg = e01.G["p"]["mass"]["pack_wh_per_kg_cited"]; e = res["end"]
    pay = -(e["hw"] - ref["hw"] + (e["pack"] - ref["pack"]) / whkg)
    return {"cap": cap, "tip_chord_max": lim, "payload": pay, "pack": e["pack"], "hw": e["hw"], "rpm_hover": e["rpm_hover"], "solidity": e["solidity"],
            "margin": e["margin"], "tw_mach": e["tw_mach"], "motor_kg": e["motor_kg"], "blade": res["blade"], "runtime_s": time.time() - t0}


def score(row):
    import e01_coax_blade as e01, e30_bpm_rotor as e30, e31_tip_noise as e31
    e01.init()
    te = e30.rotor_bpm("tri", row["blade"]); tip = e31.tip_rotor("tri", row["blade"])
    te_msq = 10 ** (np.array(te["spectrum"]) / 10); out = {"te_dba": te["dba"], "tonal_dba": te["tonal_dba"], "rpm": te["rpm"],
                                                           "chord_tip_strip": tip["chord_tip"], "alpha_star_gamma_max": tip["alpha_star_gamma_max"], "gamma_max": tip["gamma_max"]}
    for key in ("rounded_G", "flat_G"):
        bb = e31.dba(te_msq + 10 ** (np.array(tip[key]["spectrum"]) / 10))
        out[key] = {"tip_dba": tip[key]["dba"], "f_peak": tip[key]["f_peak"], "l_mm": tip[key]["l_mm"], "broadband_dba": bb,
                    "total_dba": 10 * math.log10(10 ** (bb / 10) + 10 ** (te["tonal_dba"] / 10))}
    return out


def run():
    import e01_coax_blade as e01
    from common import RESULTS, save_json
    t0 = time.time(); OUT = os.path.join(RESULTS, "explore")
    with Pool(4) as pool:
        rows = pool.map(job, [(c, l) for c in CAPS for l in LIMS])
    e28 = json.load(open(os.path.join(OUT, "e28_noise_cap.json"))); e31j = json.load(open(os.path.join(OUT, "e31_tip_noise.json")))
    ref060 = next(x for x in e28["rows"] if x["layout"] == "tri" and x["cap"] == 0.60)["payload"]
    for x in e28["rows"]:                                            # unbounded e28 optima as the baseline rows
        if x["layout"] == "tri": rows.append({"cap": x["cap"], "tip_chord_max": None, "payload": x["payload"], "blade": x["blade"], "rpm_hover": x["rpm_hover"], "solidity": x["solidity"], "margin": x["margin"], "tw_mach": x["tw_mach"]})
    with Pool(4) as pool:
        sc = pool.map(score, rows)
    for r, s in zip(rows, sc):
        r.update(s); r["dpayload_vs_060"] = r["payload"] - ref060
        print(f"  cap {r['cap']:.2f} ctip<= {('%.0f mm' % (1000*r['tip_chord_max'])) if r['tip_chord_max'] else 'free':>6}: payload {r['payload']:+.2f} kg ({r['dpayload_vs_060']:+.2f}),"
              f" tip chord {1000*r['chord_tip_strip']:.0f} mm, a*Gmax {r['alpha_star_gamma_max']:.2f}, rpm {r['rpm']:.0f}; TE {r['te_dba']:.1f}, tonal {r['tonal_dba']:.1f},"
              f" tip flat {r['flat_G']['tip_dba']:.1f} / rounded {r['rounded_G']['tip_dba']:.1f}; total flat {r['flat_G']['total_dba']:.1f}, rounded {r['rounded_G']['total_dba']:.1f} dBA", flush=True)
    hx = {k: next(x for x in e31j["rows"] if x["layout"] == "hex" and x["cap"] == 0.60)[k]["total_dba"] for k in ("rounded_G", "flat_G")}
    # best payload among all tri designs that meet the hex level
    par = {}
    for k in ("rounded_G", "flat_G"):
        ok = [r for r in rows if r[k]["total_dba"] <= hx[k] + 1e-9]
        best = max(ok, key=lambda r: r["dpayload_vs_060"]) if ok else None
        par[k] = {"hex_total_dba": hx[k], "best": None if best is None else {"cap": best["cap"], "tip_chord_max": best["tip_chord_max"], "dpayload_vs_060": best["dpayload_vs_060"], "total_dba": best[k]["total_dba"]}}
    print("  parity:", json.dumps(par, indent=1))
    save_json(os.path.join("explore", OUT_NAME), {"rows": rows, "parity": par, "hex_cap060": hx, "runtime_s": time.time() - t0}); plot(rows, hx, OUT)
    print(f"  wrote results/explore/{OUT_NAME} in {time.time()-t0:.0f} s")


def plot(rows, hx, OUT):
    fig, axs = plt.subplots(1, 2, figsize=(10, 3.6)); mk = {None: "o", 0.065: "s", 0.045: "^"}
    for ax, k, ttl in ((axs[0], "flat_G", "flat tip"), (axs[1], "rounded_G", "rounded tip")):
        for lim in (None, 0.065, 0.045):
            rs = sorted((r for r in rows if r["tip_chord_max"] == lim), key=lambda r: r["cap"])
            ax.plot([r[k]["total_dba"] for r in rs], [r["dpayload_vs_060"] for r in rs], mk[lim] + "-", color="#0b0b0b", alpha=1 if lim is None else .6,
                    label=f"tri, tip chord {'free' if lim is None else '<= %.0f mm' % (1000*lim)}")
            for r in rs: ax.annotate(f"{r['cap']:.2f}", (r[k]["total_dba"], r["dpayload_vs_060"]), fontsize=6, xytext=(3, 2), textcoords="offset points")
        ax.axvline(hx[k], color="#2a78d6", ls="--", label="hex at cap 0.60"); ax.set_title(ttl, fontsize=8)
        ax.set_xlabel("total hover level [dBA] at 50 m"); ax.set_ylabel("tri payload vs its cap-0.60 optimum [kg]"); ax.grid(alpha=.3); ax.legend(fontsize=6)
    fig.suptitle("Exploration 32: tri tip-chord bound against total hover noise (TE + tip vortex at max-Gamma angle + tones)", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "e32_tip_chord.png"), dpi=140); plt.close(fig)


if __name__ == "__main__":
    run()

"""Exploration 28: payload against tonal noise. The tri and hex best-camber blades re-optimised at tip-Mach caps
0.45-0.60, each optimum's hover noise computed with entry 27's Gutin model.

Entry 27 found the hex 6.9 dBA quieter (tonal, hover, 50 m) and estimated from entry 15 (44xx blades) that quieting the
tri to match would cost it > 2 kg. Here, properly: for each layout and cap, entries 11 (hex) / 13 (tri) optimisers with
the best-camber polars (hex 24xx, tri 44/24 hybrid), started from the entry-22 optima. A lower cap forces a slower
rotor, so a larger solidity (more chord) and more torque, so heavier motors. Each optimum gets its hover and T/W 2 tonal
level. The result is a payload-vs-dBA frontier per layout, and the payload each layout gives at an equal-noise limit.
Payload is reported as the change from that layout's own cap-0.60 optimum, then added to entry 24's full-chain
ranking (15 m/s and free speed), since the 15 m/s optimiser frame (entries 11/13) and entry 24's frame differ.

Hand checks:
  (1) on the cap, Q_max = P_max / Omega_cap with Omega_cap ~ M: motor mass ~ 1/M (entry 15's rule) against the optimiser;
  (2) dBA change against 60 log10 of the hover rpm ratio at fixed thrust (entry 27's Gutin scaling).
"""
import json, math, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from multiprocessing import Pool
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import bemt
import e01_coax_blade as e01
import e02_coax_two_point as e02
import e11_blade_with_motor as e11
import e13_tri_torque_margin as e13
import e24_chain_best_blades as e24
import e27_rotor_noise as e27
from common import RESULTS, save_json

OUT = os.path.join(RESULTS, "explore")
CAPS = (0.45, 0.50, 0.55, 0.60)
LAY = {"tri": ("tri", 3), "hex": ("hex0", 6)}


def noise(c, bd, db):
    G = e01.G; p, hot = G["p"], G["hot"]; W = G["ph1"]["vehicle"]["weight_n"]; n = LAY[c][1]
    Rr = p["rotor"]["diameter_in"] * p["constants"]["inch_to_m"] / 2; b = e02.blade_from(bd, Rr, p["rotor"]["hub_radius_m"]); out = {}
    for pt, T in (("hover", W / n), ("T/W 2", p["vehicle"]["tw_target"] * W / n)):
        h = bemt.hover_at_thrust(b, db, hot, T)
        d = [e27.levels(h, b.N, hot["a"], n, th) for th in e27.THETAS]
        out[pt] = {"rpm": h["rpm"], "tip_mach": h["tip_mach"], "max_dba": max(x["dba"] for x in d), "max_oaspl": max(x["oaspl"] for x in d)}
    return out


def job(args):
    c, cap = args
    e01.init(); db = e24.db_for(LAY[c][0], "best"); e01.G["db"] = db; e01.G["p"]["rotor"]["tip_mach_max"] = cap
    bd = e24.blade_for(LAY[c][0], "best")
    if c == "tri":
        r = e13.optimise((f"tri M{cap:.2f}", bd)); ref = json.load(open(os.path.join(OUT, "e13_tri_torque_margin.json")))["reference"]
        whkg = e01.G["p"]["mass"]["pack_wh_per_kg_cited"]; pay = -(r["end"]["hw"] - ref["hw"] + (r["end"]["pack"] - ref["pack"]) / whkg)
    else:
        r = e11.optimise((f"hex M{cap:.2f}", bd, "motor")); pay = r["end"]["payload"]
    e = r["end"]
    return {"layout": c, "cap": cap, "payload": pay, "pack": e["pack"], "hw": e["hw"], "Q_max": e["Q_max"], "motor_kg": e["motor_kg"], "rpm_hover": e["rpm_hover"],
            "solidity": e["solidity"], "margin": e["margin"], "tw_mach": e["tw_mach"], "blade": r["blade"], "noise": noise(c, r["blade"], db), "runtime_s": r["runtime_s"]}


def run():
    t0 = time.time(); e01.init()
    with Pool(4) as pool:
        rows = pool.map(job, [(c, m) for c in ("tri", "hex") for m in CAPS])
    save_json(os.path.join("explore", "e28_noise_cap.json"), {"rows": rows})
    R = {c: sorted((r for r in rows if r["layout"] == c), key=lambda r: r["cap"]) for c in ("tri", "hex")}
    for c in R:
        p0 = R[c][-1]["payload"]
        for r in R[c]:
            r["dpayload_vs_060"] = r["payload"] - p0
            print(f"  {c} cap {r['cap']:.2f}: payload {r['payload']:+.2f} kg ({r['dpayload_vs_060']:+.2f} vs 0.60), pack {r['pack']:.0f} Wh, hw {r['hw']:.2f}, Q_max {r['Q_max']:.1f},"
                  f" motor {r['motor_kg']:.2f}, rpm_h {r['rpm_hover']:.0f}, sigma {r['solidity']:.3f}, margin {r['margin']:.1f}, tw_mach {r['tw_mach']:.2f};"
                  f" hover {r['noise']['hover']['max_dba']:.1f} dBA (M {r['noise']['hover']['tip_mach']:.3f}), T/W2 {r['noise']['T/W 2']['max_dba']:.1f} dBA [{r['runtime_s']:.0f}s]", flush=True)
    # equal-noise ranking: entry 24's hex - tri plus each layout's payload change at a common hover dBA limit
    e24r = json.load(open(os.path.join(OUT, "e24_chain_best_blades.json")))["sets"]["best camber (entry 22)"]["ranking"]["scenarios"]
    base = {(s["speed"], s["body"], s["e_b"]): s["hex_minus_tri_kg"] for s in e24r}
    def at(c, lim, pt="hover"):
        xs = [r["noise"][pt]["max_dba"] for r in R[c]]; ys = [r["dpayload_vs_060"] for r in R[c]]
        if lim >= xs[-1]: return 0.0
        if lim < xs[0]: return None
        return float(np.interp(lim, xs, ys))
    lims = np.arange(34.0, 47.5, 0.5); frontier = []
    for lim in lims:
        dt, dh = at("tri", lim), at("hex", lim)
        row = {"limit_dba": float(lim), "tri_dpayload": dt, "hex_dpayload": dh}
        for k, v in base.items():
            row[f"{k[0]}|{k[1]}|{k[2]:.0f}"] = (v + dh - dt) if (dt is not None and dh is not None) else None
        frontier.append(row)
    hexq = R["hex"][-1]["noise"]["hover"]["max_dba"]; par = {"limit_dba": hexq, "tri_dpayload": at("tri", hexq)}
    for k, v in base.items():
        par[f"{k[0]}|{k[1]}|{k[2]:.0f}"] = v - par["tri_dpayload"] if par["tri_dpayload"] is not None else None
    print(f"  noise parity at the hex's own hover level ({hexq:.1f} dBA): tri payload change {par['tri_dpayload']}, ranking {par}", flush=True)
    t6, t5 = R["tri"][-1], next(r for r in R["tri"] if r["cap"] == 0.55)
    hc = {"motor_ratio_055_over_060": t5["motor_kg"] / t6["motor_kg"], "hand_1_over_M": 0.60 / 0.55,
          "tri_dba_drop_060_to_cap": {f"{r['cap']:.2f}": {"model": r["noise"]["hover"]["max_dba"] - t6["noise"]["hover"]["max_dba"],
                                                           "hand_60log_rpm": 60 * math.log10(r["noise"]["hover"]["rpm"] / t6["noise"]["hover"]["rpm"])} for r in R["tri"]}}
    print(f"  hand: {json.dumps(hc, indent=1)}")
    out = {"rows": rows, "frontier": frontier, "parity_at_hex_level": par, "hand_check": hc, "runtime_s": time.time() - t0}
    save_json(os.path.join("explore", "e28_noise_cap.json"), out); plot(out)
    print(f"  wrote results/explore/e28_noise_cap.json in {out['runtime_s']:.0f} s")


def plot(o):
    fig, axs = plt.subplots(1, 2, figsize=(10, 3.6)); col = {"tri": "#0b0b0b", "hex": "#2a78d6"}
    for c in ("tri", "hex"):
        rs = sorted((r for r in o["rows"] if r["layout"] == c), key=lambda r: r["cap"])
        axs[0].plot([r["noise"]["hover"]["max_dba"] for r in rs], [r["dpayload_vs_060"] for r in rs], "o-", color=col[c], label=c)
        for r in rs: axs[0].annotate(f"M{r['cap']:.2f}", (r["noise"]["hover"]["max_dba"], r["dpayload_vs_060"]), fontsize=6, xytext=(3, 3), textcoords="offset points")
    axs[0].set_xlabel("hover tonal level at 50 m [dBA] (Gutin, lower bound)"); axs[0].set_ylabel("payload change vs own cap-0.60 optimum [kg]"); axs[0].legend(fontsize=7); axs[0].grid(alpha=.3)
    F = o["frontier"]; L = [f["limit_dba"] for f in F]
    for key, ls, lab in (("15 m/s|constant|303", "-", "15 m/s, 303 Wh/kg"), ("free|constant|303", "--", "free speed, 303 Wh/kg"), ("free|constant|200", ":", "free speed, 200 Wh/kg")):
        axs[1].plot(L, [f[key] if f[key] is not None else np.nan for f in F], ls, color="#2a78d6", label=lab)
    axs[1].axhline(0, color="#888", lw=0.8); axs[1].set_xlabel("hover noise limit [dBA at 50 m]"); axs[1].set_ylabel("hex minus tri payload [kg]")
    axs[1].legend(fontsize=7); axs[1].grid(alpha=.3)
    fig.suptitle("Exploration 28: payload against tonal noise (best-camber blades re-optimised at tip-Mach caps 0.45-0.60)", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "e28_noise_cap.png"), dpi=140); plt.close(fig)


if __name__ == "__main__":
    if sys.argv[1:] == ["plot"]:
        plot(json.load(open(os.path.join(OUT, "e28_noise_cap.json"))))
    else:
        run()

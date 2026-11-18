"""Exploration 20: camber for the re-optimised tri and hex blades (NACA 64xx and the 64/44 thickness-blended hybrid).

The Phase 2 blade uses NACA 44xx (4 % camber at 40 % chord). The blade trade study (results/blade_trade.json) compared
64xx at fixed design rules; here camber goes through the same optimisers as entries 11 (hex) and 13 (tri), with the
motor in the objective and the 15 m/s design point:
    '64/44 hybrid'  6 % camber where t/c >= 15 % (inboard), 4 % where t/c <= 12 %, blended between (blade_trade_study.HybridDB)
    '64xx'          6 % camber full span
XFOIL polars for 64xx are cached in results/polars (built by the blade trade study, same Re/Mach grid as 44xx).
Payload is scored on the same absolute hardware + pack bookkeeping as entries 11/13 (tri: against entry 13's 44xx
reference, re-scored on 44xx polars so the reference does not move with the polar set).

Hand checks:
  (1) thin-airfoil zero-lift angle of a NACA m p camber line, alpha_L0 = -(1/pi) int_0^pi (dz/dx)(cos th - 1) d th
  (2) hover profile power at fixed thrust: C_T = sigma Cl / 6 -> sigma ~ 1/Cl, P0 ~ sigma Cd ~ Cd / Cl, and with the rpm
      free the best section maximises Cl^1.5 / Cd (Glauert); compare (Cl^1.5/Cd)_max of 4412 and 6412 from the polars.
"""
import json, math, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from multiprocessing import Pool
from scipy.integrate import quad
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import airfoils
import e01_coax_blade as e01
import e11_blade_with_motor as e11
import e13_tri_torque_margin as e13
from blade_trade_study import HybridDB
from common import RESULTS, save_json

OUT = os.path.join(RESULTS, "explore")


def dbs():
    p = e01.G["p"]; db44 = e01.G["db"]
    p64 = json.loads(json.dumps(p)); p64["airfoils"]["family"] = "64"; p64["airfoils"]["compare_sections"] = []
    db64, _ = airfoils.build_db(p64, n_proc=1)
    return {"44xx": db44, "64/44 hybrid": HybridDB(db44, db64), "64xx": db64}


def job(args):
    layout, fam = args
    e01.init(); D = dbs(); e01.G["db"] = D[fam]
    e13r = json.load(open(os.path.join(OUT, "e13_tri_torque_margin.json"))); e11r = json.load(open(os.path.join(OUT, "e11_blade_with_motor.json")))
    whkg = e01.G["p"]["mass"]["pack_wh_per_kg_cited"]
    if layout == "tri":
        bd = max(e13r["runs"], key=lambda r: r["end"]["dpayload"])["blade"]
        r = e13.optimise((f"tri {fam}", bd)); ref = e13r["reference"]
        f = lambda e: -(e["hw"] - ref["hw"] + (e["pack"] - ref["pack"]) / whkg)
        start, end = r["start"], r["end"]
    else:
        bd = max((x for x in e11r["runs"] if x["mode"] == "motor"), key=lambda x: x["end"]["payload"])["blade"]
        r = e11.optimise((f"hex {fam}", bd, "motor")); f = lambda e: e["payload"]
        start, end = r["start"], r["end"]
    keys = ("pack", "hover", "cruise", "hw", "motor_kg", "blade_kg", "Q_max", "rpm_hover", "solidity", "margin", "tw_mach")
    return {"layout": layout, "family": fam, "payload_start": f(start), "payload_end": f(end), "start": {k: start[k] for k in keys},
            "end": {k: end[k] for k in keys}, "blade": r["blade"], "evaluations": r["evaluations"], "runtime_s": r["runtime_s"]}


def alpha_l0(m, pp):
    dz = lambda x: (2 * m / pp ** 2) * (pp - x) if x < pp else (2 * m / (1 - pp) ** 2) * (pp - x)
    return -quad(lambda th: dz(0.5 * (1 - math.cos(th))) * (math.cos(th) - 1), 0, math.pi, points=[math.acos(1 - 2 * pp)])[0] / math.pi


def run():
    t0 = time.time(); e01.init()
    jobs = [(l, f) for l in ("tri", "hex") for f in ("64/44 hybrid", "64xx")]
    with Pool(4) as pool:
        rows = pool.map(job, jobs)
    save_json(os.path.join("explore", "e20_camber.json"), {"rows": rows})
    e13r = json.load(open(os.path.join(OUT, "e13_tri_torque_margin.json"))); e11r = json.load(open(os.path.join(OUT, "e11_blade_with_motor.json")))
    base = {"tri": max(r["end"]["dpayload"] for r in e13r["runs"]), "hex": max(r["end"]["payload"] for r in e11r["runs"] if r["mode"] == "motor")}
    for r in rows:
        r["payload_vs_44xx_opt"] = r["payload_end"] - base[r["layout"]]
        print(f"  {r['layout']} {r['family']:13s}: payload start {r['payload_start']:+.2f} -> end {r['payload_end']:+.2f} kg (44xx optimum {base[r['layout']]:+.2f}; change {r['payload_vs_44xx_opt']:+.2f}),"
              f" pack {r['start']['pack']:.0f} -> {r['end']['pack']:.0f} Wh, rpm_h {r['end']['rpm_hover']:.0f}, sigma {r['end']['solidity']:.3f}, Q_max {r['end']['Q_max']:.1f},"
              f" motor {r['end']['motor_kg']:.2f}, blade {r['end']['blade_kg']:.3f} [{r['runtime_s']:.0f}s]", flush=True)
    # hand checks
    D = dbs(); hc = {"alpha_L0_deg": {f"NACA {int(100*m)}{int(10*pp)}xx": math.degrees(alpha_l0(m, pp)) for m, pp in ((0.04, 0.4), (0.06, 0.4))}}
    al = np.radians(np.arange(-2, 14.01, 0.25)); best = {}
    for fam in ("44xx", "64xx"):
        for tc in (0.09, 0.12):
            cl, cd = D[fam].lookup(np.full_like(al, tc), np.full_like(al, 6e5), np.full_like(al, 0.30), al)
            m = (cl > 0.05) & (cd > 0); g = np.where(m, np.maximum(cl, 1e-6) ** 1.5 / np.maximum(cd, 1e-6), 0)
            i = int(np.argmax(g)); best[f"{fam} t/c {tc}"] = {"cl": float(cl[i]), "cd": float(cd[i]), "cl15_over_cd": float(g[i]), "alpha_deg": float(np.degrees(al[i])),
                                                            "cl_max": float(cl.max())}
    hc["glauert_section_figure_Re6e5_M0.3"] = best
    out = {"rows": rows, "baseline_44xx": base, "hand_check": hc, "runtime_s": time.time() - t0}
    print(f"  hand: {hc}")
    save_json(os.path.join("explore", "e20_camber.json"), out); plot(out)
    print(f"  wrote results/explore/e20_camber.json in {out['runtime_s']:.0f} s")


def plot(o):
    fig, axs = plt.subplots(1, 2, figsize=(9, 3.3)); col = {"tri": "#0b0b0b", "hex": "#2a78d6"}; ls = {"64/44 hybrid": "--", "64xx": ":"}
    for r in o["rows"]:
        b = r["blade"]; x = np.array(b["r"]) / max(b["r"])
        axs[0].plot(x, 1000 * np.array(b["chord"]), ls[r["family"]], color=col[r["layout"]], label=f"{r['layout']} {r['family']} ({r['payload_vs_44xx_opt']:+.2f} kg)")
        axs[1].plot(x, b["twist_deg"], ls[r["family"]], color=col[r["layout"]])
    axs[0].set_xlabel("r / R"); axs[0].set_ylabel("chord [mm]"); axs[0].legend(fontsize=6); axs[0].grid(alpha=.3)
    axs[1].set_xlabel("r / R"); axs[1].set_ylabel("twist [deg]"); axs[1].grid(alpha=.3)
    fig.suptitle("Exploration 20: camber in the motor-in-objective optimiser (legend: payload change vs the 44xx optimum)", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "e20_camber.png"), dpi=140); plt.close(fig)


if __name__ == "__main__":
    run()

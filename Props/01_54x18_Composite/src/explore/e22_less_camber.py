"""Exploration 22: less camber outboard (NACA 24xx) for the motor-sized tri and hex blades.

Entry 20: with torque-sized motors the optimum blade runs its sections at Cl ~0.6-0.9, where 64xx drags 13-36 % more
than 44xx. A section with LESS camber puts its drag bucket lower. New XFOIL polars for 24xx (2 % camber at 40 % chord,
t/c 9-18 %, same Re/Mach grid as 44xx; all 80 cases converged) are cached in results/polars. Families tried (entry 20's
optimisers and bookkeeping, 15 m/s design point, start from the 44xx optima):
    '44/24 hybrid'   4 % camber where t/c >= 15 % (inboard, where the thick root needs lift), 2 % where t/c <= 12 %
    '24xx'           2 % camber full span
Hand check: section drag at the operating Cl (Re 6e5, M 0.3) and the thin-airfoil zero-lift angle of the 24xx line.
"""
import json, math, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from multiprocessing import Pool
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import airfoils
import e01_coax_blade as e01
import e20_camber as e20
from blade_trade_study import HybridDB
from common import RESULTS, save_json

OUT = os.path.join(RESULTS, "explore")


def dbs():
    p = e01.G["p"]; db44 = e01.G["db"]
    p24 = json.loads(json.dumps(p)); p24["airfoils"]["family"] = "24"; p24["airfoils"]["compare_sections"] = []
    db24, _ = airfoils.build_db(p24, n_proc=1)
    return {"44xx": db44, "44/24 hybrid": HybridDB(db24, db44), "24xx": db24}


def job(args):
    e20.dbs = dbs
    return e20.job(args)


def run():
    t0 = time.time(); e01.init()
    jobs = [(l, f) for l in ("tri", "hex") for f in ("44/24 hybrid", "24xx")]
    with Pool(4) as pool:
        rows = pool.map(job, jobs)
    save_json(os.path.join("explore", "e22_less_camber.json"), {"rows": rows})
    e13r = json.load(open(os.path.join(OUT, "e13_tri_torque_margin.json"))); e11r = json.load(open(os.path.join(OUT, "e11_blade_with_motor.json")))
    base = {"tri": max(r["end"]["dpayload"] for r in e13r["runs"]), "hex": max(r["end"]["payload"] for r in e11r["runs"] if r["mode"] == "motor")}
    for r in rows:
        r["payload_vs_44xx_opt"] = r["payload_end"] - base[r["layout"]]
        print(f"  {r['layout']} {r['family']:13s}: payload {r['payload_start']:+.2f} -> {r['payload_end']:+.2f} kg (44xx {base[r['layout']]:+.2f}; change {r['payload_vs_44xx_opt']:+.2f}),"
              f" pack {r['end']['pack']:.0f} Wh, rpm_h {r['end']['rpm_hover']:.0f}, sigma {r['end']['solidity']:.3f}, Q_max {r['end']['Q_max']:.1f}, motor {r['end']['motor_kg']:.2f},"
              f" blade {r['end']['blade_kg']:.3f}, margin {r['end']['margin']:.1f} deg [{r['runtime_s']:.0f}s]", flush=True)
    D = dbs(); al = np.radians(np.arange(-4, 12, 0.05)); tab = {}
    for fam in ("44xx", "24xx"):
        for tc in (0.09, 0.12):
            cl, cd = D[fam].lookup(np.full_like(al, tc), np.full_like(al, 6e5), np.full_like(al, 0.30), al)
            for c0 in (0.4, 0.6, 0.8, 1.0):
                i = int(np.argmin(abs(cl - c0))); tab[f"{fam} t/c {tc} Cl {c0}"] = {"cd": float(cd[i]), "alpha_deg": float(np.degrees(al[i]))}
            tab[f"{fam} t/c {tc} cl_max"] = float(cl.max())
    hc = {"alpha_L0_deg_24xx": math.degrees(e20.alpha_l0(0.02, 0.4)), "cd_at_cl": tab}
    out = {"rows": rows, "baseline_44xx": base, "hand_check": hc, "runtime_s": time.time() - t0}
    print(f"  hand: {hc}")
    save_json(os.path.join("explore", "e22_less_camber.json"), out)
    fig, axs = plt.subplots(1, 2, figsize=(9, 3.3)); col = {"tri": "#0b0b0b", "hex": "#2a78d6"}; ls = {"44/24 hybrid": "--", "24xx": ":"}
    for r in rows:
        b = r["blade"]; x = np.array(b["r"]) / max(b["r"])
        axs[0].plot(x, 1000 * np.array(b["chord"]), ls[r["family"]], color=col[r["layout"]], label=f"{r['layout']} {r['family']} ({r['payload_vs_44xx_opt']:+.2f} kg)")
        axs[1].plot(x, b["twist_deg"], ls[r["family"]], color=col[r["layout"]])
    axs[0].set_xlabel("r / R"); axs[0].set_ylabel("chord [mm]"); axs[0].legend(fontsize=6); axs[0].grid(alpha=.3)
    axs[1].set_xlabel("r / R"); axs[1].set_ylabel("twist [deg]"); axs[1].grid(alpha=.3)
    fig.suptitle("Exploration 22: less camber outboard (legend: payload change vs the 44xx optimum)", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "e22_less_camber.png"), dpi=140); plt.close(fig)
    print(f"  wrote results/explore/e22_less_camber.json in {out['runtime_s']:.0f} s")


if __name__ == "__main__":
    run()

"""Exploration 23: camber below 2 % (NACA 14xx and symmetric 00xx) for the motor-sized hex and tri blades.

Entry 22: going from 4 % to 2 % camber gave the hex +1.03 kg, because torque-sized motors push the rotor to a higher rpm
and a lower section Cl (~0.4-0.6), where the 2 % section's drag bucket sits. Does the trend continue? New XFOIL polars
for 14xx (1 % camber at 40 % chord) and 00xx (symmetric), t/c 9-18 %, same Re/Mach grid, cached in results/polars.
Families (entry 20's optimisers and bookkeeping, 15 m/s design point, start from the 44xx optima):
    hex  '14xx'           1 % camber full span
    hex  '00xx'           symmetric full span
    hex  '24/00 hybrid'   2 % camber where t/c >= 15 % (inboard), symmetric where t/c <= 12 %
    tri  '44/14 hybrid'   4 % inboard, 1 % outboard (entry 22's best tri layout was 44/24)
    tri  '14xx'
Payload is reported against the 44xx optimum (entries 11/13) and against entry 22's best for that layout.

Hand checks: thin-airfoil zero-lift angle of the 14xx line (alpha_L0 is linear in camber m: -1.04 deg expected), and the
section drag at Cl 0.3-0.8 for 24xx / 14xx / 00xx at t/c 9 and 12 % (Re 6e5, M 0.3).
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
JOBS = [("hex", "14xx"), ("hex", "00xx"), ("hex", "24/00 hybrid"), ("tri", "44/14 hybrid"), ("tri", "14xx")]


def fam_db(fam):
    q = json.loads(json.dumps(e01.G["p"])); q["airfoils"]["family"] = fam; q["airfoils"]["compare_sections"] = []
    return airfoils.build_db(q, n_proc=1)[0]


def dbs():
    db44 = e01.G["db"]; d = {f: fam_db(f) for f in ("24", "14", "00")}
    return {"44xx": db44, "24xx": d["24"], "14xx": d["14"], "00xx": d["00"],
            "24/00 hybrid": HybridDB(d["00"], d["24"]), "44/14 hybrid": HybridDB(d["14"], db44)}


def job(args):
    e20.dbs = dbs
    return e20.job(args)


def run():
    t0 = time.time(); e01.init()
    with Pool(4) as pool:
        rows = pool.map(job, JOBS)
    save_json(os.path.join("explore", "e23_camber_sweep.json"), {"rows": rows})
    e13r = json.load(open(os.path.join(OUT, "e13_tri_torque_margin.json"))); e11r = json.load(open(os.path.join(OUT, "e11_blade_with_motor.json")))
    e22r = json.load(open(os.path.join(OUT, "e22_less_camber.json")))
    base = {"tri": max(r["end"]["dpayload"] for r in e13r["runs"]), "hex": max(r["end"]["payload"] for r in e11r["runs"] if r["mode"] == "motor")}
    best22 = {L: max(r["payload_vs_44xx_opt"] for r in e22r["rows"] if r["layout"] == L) for L in ("tri", "hex")}
    for r in rows:
        r["payload_vs_44xx_opt"] = r["payload_end"] - base[r["layout"]]; r["payload_vs_e22_best"] = r["payload_vs_44xx_opt"] - best22[r["layout"]]
        print(f"  {r['layout']} {r['family']:13s}: vs 44xx {r['payload_vs_44xx_opt']:+.2f} kg, vs entry-22 best {r['payload_vs_e22_best']:+.2f} kg,"
              f" pack {r['end']['pack']:.0f} Wh, rpm_h {r['end']['rpm_hover']:.0f}, sigma {r['end']['solidity']:.3f}, Q_max {r['end']['Q_max']:.1f}, motor {r['end']['motor_kg']:.2f},"
              f" margin {r['end']['margin']:.1f} deg [{r['runtime_s']:.0f}s]", flush=True)
    D = dbs(); al = np.radians(np.arange(-6, 12, 0.05)); tab = {}
    for fam in ("24xx", "14xx", "00xx"):
        for tc in (0.09, 0.12):
            cl, cd = D[fam].lookup(np.full_like(al, tc), np.full_like(al, 6e5), np.full_like(al, 0.30), al)
            for c0 in (0.3, 0.4, 0.6, 0.8):
                i = int(np.argmin(abs(cl - c0))); tab[f"{fam} t/c {tc} Cl {c0}"] = {"cd": float(cd[i]), "alpha_deg": float(np.degrees(al[i]))}
            tab[f"{fam} t/c {tc} cl_max"] = float(cl.max())
            tab[f"{fam} t/c {tc} alpha_L0_xfoil"] = float(np.degrees(np.interp(0.0, cl[(al > -0.1) & (al < 0.1)], al[(al > -0.1) & (al < 0.1)])))
    hc = {"alpha_L0_deg_thin": {f: math.degrees(e20.alpha_l0(m, 0.4)) for f, m in (("24xx", 0.02), ("14xx", 0.01))}, "cd_at_cl": tab}
    out = {"rows": rows, "baseline_44xx": base, "best_e22_vs_44xx": best22, "hand_check": hc, "runtime_s": time.time() - t0}
    print(f"  hand: {json.dumps(hc, indent=1)}")
    save_json(os.path.join("explore", "e23_camber_sweep.json"), out); plot(out)
    print(f"  wrote results/explore/e23_camber_sweep.json in {out['runtime_s']:.0f} s")


def plot(o):
    fig, axs = plt.subplots(1, 3, figsize=(12, 3.4)); col = {"tri": "#0b0b0b", "hex": "#2a78d6"}
    ls = {"14xx": ":", "00xx": "-.", "24/00 hybrid": "--", "44/14 hybrid": "--"}
    for r in o["rows"]:
        b = r["blade"]; x = np.array(b["r"]) / max(b["r"])
        axs[0].plot(x, 1000 * np.array(b["chord"]), ls[r["family"]], color=col[r["layout"]], label=f"{r['layout']} {r['family']} ({r['payload_vs_44xx_opt']:+.2f} kg)")
        axs[1].plot(x, b["twist_deg"], ls[r["family"]], color=col[r["layout"]])
    axs[0].set_xlabel("r / R"); axs[0].set_ylabel("chord [mm]"); axs[0].legend(fontsize=6); axs[0].grid(alpha=.3)
    axs[1].set_xlabel("r / R"); axs[1].set_ylabel("twist [deg]"); axs[1].grid(alpha=.3)
    # payload against outboard camber, both layouts (entries 20, 22, 23)
    e20r = json.load(open(os.path.join(OUT, "e20_camber.json"))); e22r = json.load(open(os.path.join(OUT, "e22_less_camber.json")))
    full = {"00xx": 0, "14xx": 1, "24xx": 2, "44xx": 4, "64xx": 6}
    for L in ("hex", "tri"):
        pts = [(4, 0.0)] + [(full[r["family"]], r["payload_vs_44xx_opt"]) for R in (e20r, e22r, o) for r in R["rows"] if r["layout"] == L and r["family"] in full]
        pts.sort(); axs[2].plot([p[0] for p in pts], [p[1] for p in pts], "o-", color=col[L], label=f"{L}, full-span camber")
    axs[2].axhline(0, color="#888", lw=0.8); axs[2].set_xlabel("camber [% chord]"); axs[2].set_ylabel("payload vs 44xx optimum [kg]"); axs[2].legend(fontsize=7); axs[2].grid(alpha=.3)
    fig.suptitle("Exploration 23: camber below 2 % (legend: payload change vs the 44xx optimum)", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "e23_camber_sweep.png"), dpi=140); plt.close(fig)


if __name__ == "__main__":
    if sys.argv[1:] == ["plot"]:
        plot(json.load(open(os.path.join(OUT, "e23_camber_sweep.json"))))
    else:
        run()

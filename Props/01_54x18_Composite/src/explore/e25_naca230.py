"""Exploration 25: NACA 230xx, a section designed for Cl_i = 0.3, on the motor-sized hex and tri blades.

Entries 22-23: the best 4-digit camber is 2 % (24xx), and the motor-sized rotors run their sections at Cl ~0.3 (hex)
and ~0.4 (tri). A NACA 5-digit section is specified by its design (ideal) lift coefficient: the first digit L gives
Cl_i = 0.15 L, so 230xx has Cl_i = 0.30, with the camber peak forward at 15 % chord (P = 3 -> 0.05 P). New XFOIL polars
230xx, t/c 9-18 %, same Re/Mach grid, cached in results/polars. Families (entry 20's optimisers, 15 m/s design point,
start from the 44xx optima):
    hex  '230xx'            full span
    hex  '24/230 hybrid'    24xx where t/c >= 15 % (inboard), 230xx where t/c <= 12 %
    tri  '230xx'
    tri  '44/230 hybrid'    44xx inboard, 230xx outboard
Payload is reported against the 44xx optimum (entries 11/13) and against the best of entries 22-23.

Hand checks: thin-airfoil theory on the 5-digit mean line, y = (k1/6)(x^3 - 3 m x^2 + m^2 (3 - m) x) for x < m and
(k1 m^3 / 6)(1 - x) after (230: m = 0.2025, k1 = 15.957):
    alpha_L0 = -(1/pi) int (dz/dx)(cos th - 1) d th
    ideal angle (A0 = 0): alpha_i = (1/pi) int (dz/dx) d th;  Cl_i = 2 pi (alpha_i - alpha_L0)   (should be 0.30)
and the section drag at Cl 0.2-0.6 against 24xx.
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
import e01_coax_blade as e01
import e20_camber as e20
import e23_camber_sweep as e23
from blade_trade_study import HybridDB
from common import RESULTS, save_json

OUT = os.path.join(RESULTS, "explore")
JOBS = [("hex", "230xx"), ("hex", "24/230 hybrid"), ("tri", "230xx"), ("tri", "44/230 hybrid")]
M5, K1 = 0.2025, 15.957


def dbs():
    db44 = e01.G["db"]; d = {f: e23.fam_db(f) for f in ("24", "230")}
    return {"44xx": db44, "24xx": d["24"], "230xx": d["230"], "24/230 hybrid": HybridDB(d["230"], d["24"]), "44/230 hybrid": HybridDB(d["230"], db44)}


def job(args):
    e20.dbs = dbs
    return e20.job(args)


def dzdx(x):
    return K1 / 6 * (3 * x * x - 6 * M5 * x + M5 * M5 * (3 - M5)) if x < M5 else -K1 * M5 ** 3 / 6


def thin_airfoil():
    th_m = math.acos(1 - 2 * M5); f = lambda th: dzdx(0.5 * (1 - math.cos(th)))
    a_l0 = -quad(lambda th: f(th) * (math.cos(th) - 1), 0, math.pi, points=[th_m])[0] / math.pi
    a_i = quad(f, 0, math.pi, points=[th_m])[0] / math.pi
    xs = np.linspace(0, 1, 2001); y = [K1 / 6 * (x ** 3 - 3 * M5 * x * x + M5 * M5 * (3 - M5) * x) if x < M5 else K1 * M5 ** 3 / 6 * (1 - x) for x in xs]
    i = int(np.argmax(y))
    return {"alpha_L0_deg": math.degrees(a_l0), "alpha_ideal_deg": math.degrees(a_i), "cl_ideal": 2 * math.pi * (a_i - a_l0),
            "max_camber": float(y[i]), "x_max_camber": float(xs[i]), "alpha_L0_24xx_deg": math.degrees(e20.alpha_l0(0.02, 0.4))}


def run():
    t0 = time.time(); e01.init()
    with Pool(4) as pool:
        rows = pool.map(job, JOBS)
    save_json(os.path.join("explore", "e25_naca230.json"), {"rows": rows})
    e13r = json.load(open(os.path.join(OUT, "e13_tri_torque_margin.json"))); e11r = json.load(open(os.path.join(OUT, "e11_blade_with_motor.json")))
    base = {"tri": max(r["end"]["dpayload"] for r in e13r["runs"]), "hex": max(r["end"]["payload"] for r in e11r["runs"] if r["mode"] == "motor")}
    prev = [r for f in ("e22_less_camber", "e23_camber_sweep") for r in json.load(open(os.path.join(OUT, f + ".json")))["rows"]]
    best = {L: max(r["payload_vs_44xx_opt"] for r in prev if r["layout"] == L) for L in ("tri", "hex")}
    for r in rows:
        r["payload_vs_44xx_opt"] = r["payload_end"] - base[r["layout"]]; r["payload_vs_best_2pct"] = r["payload_vs_44xx_opt"] - best[r["layout"]]
        print(f"  {r['layout']} {r['family']:14s}: vs 44xx {r['payload_vs_44xx_opt']:+.2f} kg, vs best 2 % {r['payload_vs_best_2pct']:+.2f} kg, pack {r['end']['pack']:.0f} Wh,"
              f" hw {r['end']['hw']:.2f}, rpm_h {r['end']['rpm_hover']:.0f}, sigma {r['end']['solidity']:.3f}, Q_max {r['end']['Q_max']:.1f}, motor {r['end']['motor_kg']:.2f},"
              f" margin {r['end']['margin']:.1f} deg, tw_mach {r['end']['tw_mach']:.2f} [{r['runtime_s']:.0f}s]", flush=True)
    D = dbs(); al = np.radians(np.arange(-6, 14, 0.05)); tab = {}
    for fam in ("24xx", "230xx"):
        for tc in (0.09, 0.12):
            cl, cd = D[fam].lookup(np.full_like(al, tc), np.full_like(al, 6e5), np.full_like(al, 0.30), al)
            for c0 in (0.2, 0.3, 0.4, 0.6, 0.8):
                i = int(np.argmin(abs(cl - c0))); tab[f"{fam} t/c {tc} Cl {c0}"] = {"cd": float(cd[i]), "alpha_deg": float(np.degrees(al[i]))}
            m = (al > -0.1) & (al < 0.1)
            tab[f"{fam} t/c {tc} cl_max"] = float(cl.max()); tab[f"{fam} t/c {tc} alpha_L0_xfoil"] = float(np.degrees(np.interp(0.0, cl[m], al[m])))
            tab[f"{fam} t/c {tc} cl_at_min_cd"] = float(cl[(cl > 0) & (cl < 1)][int(np.argmin(cd[(cl > 0) & (cl < 1)]))])
    hc = {"thin_airfoil_230": thin_airfoil(), "cd_at_cl": tab}
    out = {"rows": rows, "baseline_44xx": base, "best_2pct_vs_44xx": best, "hand_check": hc, "runtime_s": time.time() - t0}
    print(f"  hand: {json.dumps(hc, indent=1)}")
    save_json(os.path.join("explore", "e25_naca230.json"), out); plot(out)
    print(f"  wrote results/explore/e25_naca230.json in {out['runtime_s']:.0f} s")


def plot(o):
    fig, axs = plt.subplots(1, 3, figsize=(12, 3.4)); col = {"tri": "#0b0b0b", "hex": "#2a78d6"}; ls = {"230xx": ":", "24/230 hybrid": "--", "44/230 hybrid": "--"}
    for r in o["rows"]:
        b = r["blade"]; x = np.array(b["r"]) / max(b["r"])
        axs[0].plot(x, 1000 * np.array(b["chord"]), ls[r["family"]], color=col[r["layout"]], label=f"{r['layout']} {r['family']} ({r['payload_vs_44xx_opt']:+.2f} kg)")
        axs[1].plot(x, b["twist_deg"], ls[r["family"]], color=col[r["layout"]])
    axs[0].set_xlabel("r / R"); axs[0].set_ylabel("chord [mm]"); axs[0].legend(fontsize=6); axs[0].grid(alpha=.3)
    axs[1].set_xlabel("r / R"); axs[1].set_ylabel("twist [deg]"); axs[1].grid(alpha=.3)
    t = o["hand_check"]["cd_at_cl"]; cls = (0.2, 0.3, 0.4, 0.6, 0.8)
    for fam, c in (("24xx", "#888"), ("230xx", "#d62a2a")):
        for tc, mk in ((0.09, "o-"), (0.12, "s--")):
            axs[2].plot(cls, [1e4 * t[f"{fam} t/c {tc} Cl {c0}"]["cd"] for c0 in cls], mk, color=c, ms=3, label=f"{fam} t/c {tc}")
    axs[2].set_xlabel("section Cl"); axs[2].set_ylabel("Cd x 1e4 (Re 6e5, M 0.3)"); axs[2].legend(fontsize=6); axs[2].grid(alpha=.3)
    fig.suptitle("Exploration 25: NACA 230xx (design Cl 0.3) on the motor-sized blades (legend: payload vs the 44xx optimum)", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "e25_naca230.png"), dpi=140); plt.close(fig)


if __name__ == "__main__":
    if sys.argv[1:] == ["plot"]:
        plot(json.load(open(os.path.join(OUT, "e25_naca230.json"))))
    elif sys.argv[1:] == ["hand"]:
        print(thin_airfoil())
    else:
        run()

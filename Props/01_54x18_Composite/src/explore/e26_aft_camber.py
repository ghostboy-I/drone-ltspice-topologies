"""Exploration 26: 2 % camber moved aft (NACA 25xx, 26xx) for the motor-sized hex and tri blades.

Entry 25: at Re ~6e5 the section drag is set by how far back the upper surface stays laminar. The 230's forward camber
peak (15 % chord) moved transition from 76 % to 37 % chord and cost ~1 kg. The converse: keep 2 % camber but move its
peak aft, from 40 % (24xx) to 50 % (25xx) and 60 % (26xx). New XFOIL polars, t/c 9-18 %, same grid. Families (entry 20's
optimisers, 15 m/s design point, start from the 44xx optima):
    hex  '25xx', '26xx'
    tri  '44/25 hybrid', '44/26 hybrid'   (44xx where t/c >= 15 %, aft-cambered 2 % where t/c <= 12 %)
Payload against the 44xx optimum and against the best 2 % blades (hex 24xx, tri 44/24 hybrid).

Hand checks (thin-airfoil theory on the NACA 4-digit mean line, m = 0.02, p = 0.4 / 0.5 / 0.6):
    alpha_L0 = -(1/pi) int (dz/dx)(cos th - 1) d th
    Cm_c/4   = (pi/4)(A2 - A1),  A_n = (2/pi) int (dz/dx) cos(n th) d th
  aft camber makes the pitching moment more nose-down, which loads the blade in torsion and the pitch link / grip;
  and the XFOIL transition points (upper / lower x_tr) at Cl 0.3 and 0.4 against 24xx.
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
from airfoils import POLAR_DIR
from blade_trade_study import HybridDB
from common import RESULTS, save_json

OUT = os.path.join(RESULTS, "explore")
JOBS = [("hex", "25xx"), ("hex", "26xx"), ("tri", "44/25 hybrid"), ("tri", "44/26 hybrid")]


def dbs():
    db44 = e01.G["db"]; d = {f: e23.fam_db(f) for f in ("24", "25", "26")}
    return {"44xx": db44, "24xx": d["24"], "25xx": d["25"], "26xx": d["26"],
            "44/25 hybrid": HybridDB(d["25"], db44), "44/26 hybrid": HybridDB(d["26"], db44)}


def job(args):
    e20.dbs = dbs
    return e20.job(args)


def thin(m, p):
    dz = lambda x: (2 * m / p ** 2) * (p - x) if x < p else (2 * m / (1 - p) ** 2) * (p - x)
    f = lambda th: dz(0.5 * (1 - math.cos(th))); tp = [math.acos(1 - 2 * p)]
    A = lambda n: 2 / math.pi * quad(lambda th: f(th) * math.cos(n * th), 0, math.pi, points=tp)[0]
    return {"alpha_L0_deg": math.degrees(e20.alpha_l0(m, p)), "cm_c4": math.pi / 4 * (A(2) - A(1))}


def transition(fam, tc, re=6e5, mach=0.30):
    """XFOIL points near Cl 0.3 and 0.4: (alpha, cl, cd, cdp, cm, x_tr upper, x_tr lower)."""
    a = np.array(json.load(open(os.path.join(POLAR_DIR, f"naca{fam}{int(round(100*tc)):02d}_re{re:.0f}_m{mach:.2f}.json")))["points"]); a = a[a[:, 0].argsort()]
    out = {}
    for c0 in (0.3, 0.4):
        i = int(np.argmin(abs(a[:, 1] - c0))); out[f"Cl {c0}"] = {"cl": a[i, 1], "cd": a[i, 2], "cm": a[i, 4], "xtr_upper": a[i, 5], "xtr_lower": a[i, 6]}
    return out


def run():
    t0 = time.time(); e01.init()
    with Pool(4) as pool:
        rows = pool.map(job, JOBS)
    save_json(os.path.join("explore", "e26_aft_camber.json"), {"rows": rows})
    e13r = json.load(open(os.path.join(OUT, "e13_tri_torque_margin.json"))); e11r = json.load(open(os.path.join(OUT, "e11_blade_with_motor.json")))
    base = {"tri": max(r["end"]["dpayload"] for r in e13r["runs"]), "hex": max(r["end"]["payload"] for r in e11r["runs"] if r["mode"] == "motor")}
    prev = [r for f in ("e22_less_camber", "e23_camber_sweep", "e25_naca230") for r in json.load(open(os.path.join(OUT, f + ".json")))["rows"]]
    best = {L: max(r["payload_vs_44xx_opt"] for r in prev if r["layout"] == L) for L in ("tri", "hex")}
    for r in rows:
        r["payload_vs_44xx_opt"] = r["payload_end"] - base[r["layout"]]; r["payload_vs_best_2pct"] = r["payload_vs_44xx_opt"] - best[r["layout"]]
        print(f"  {r['layout']} {r['family']:13s}: vs 44xx {r['payload_vs_44xx_opt']:+.2f} kg, vs best 2 % {r['payload_vs_best_2pct']:+.2f} kg, pack {r['end']['pack']:.0f} Wh,"
              f" hw {r['end']['hw']:.2f}, hover {r['end']['hover']:.0f} W, rpm_h {r['end']['rpm_hover']:.0f}, sigma {r['end']['solidity']:.3f}, Q_max {r['end']['Q_max']:.1f},"
              f" motor {r['end']['motor_kg']:.2f}, margin {r['end']['margin']:.1f} deg, tw_mach {r['end']['tw_mach']:.2f} [{r['runtime_s']:.0f}s]", flush=True)
    D = dbs(); al = np.radians(np.arange(-6, 14, 0.05)); tab = {}
    for fam in ("24xx", "25xx", "26xx"):
        for tc in (0.09, 0.12):
            cl, cd = D[fam].lookup(np.full_like(al, tc), np.full_like(al, 6e5), np.full_like(al, 0.30), al)
            for c0 in (0.2, 0.3, 0.4, 0.6, 0.8):
                i = int(np.argmin(abs(cl - c0))); tab[f"{fam} t/c {tc} Cl {c0}"] = float(cd[i])
            tab[f"{fam} t/c {tc} cl_max"] = float(cl.max())
            tab[f"{fam} t/c {tc} transition"] = transition(fam[:2], tc)
    hc = {"thin": {f: thin(0.02, p) for f, p in (("24xx", 0.4), ("25xx", 0.5), ("26xx", 0.6))}, "polar": tab}
    out = {"rows": rows, "baseline_44xx": base, "best_2pct_vs_44xx": best, "hand_check": hc, "runtime_s": time.time() - t0}
    print(f"  hand: {json.dumps(hc, indent=1)}")
    save_json(os.path.join("explore", "e26_aft_camber.json"), out); plot(out)
    print(f"  wrote results/explore/e26_aft_camber.json in {out['runtime_s']:.0f} s")


def plot(o):
    fig, axs = plt.subplots(1, 3, figsize=(12, 3.4)); col = {"tri": "#0b0b0b", "hex": "#2a78d6"}
    ls = {"25xx": "--", "26xx": ":", "44/25 hybrid": "--", "44/26 hybrid": ":"}
    for r in o["rows"]:
        b = r["blade"]; x = np.array(b["r"]) / max(b["r"])
        axs[0].plot(x, 1000 * np.array(b["chord"]), ls[r["family"]], color=col[r["layout"]], label=f"{r['layout']} {r['family']} ({r['payload_vs_best_2pct']:+.2f} kg vs best 2 %)")
        axs[1].plot(x, b["twist_deg"], ls[r["family"]], color=col[r["layout"]])
    axs[0].set_xlabel("r / R"); axs[0].set_ylabel("chord [mm]"); axs[0].legend(fontsize=6); axs[0].grid(alpha=.3)
    axs[1].set_xlabel("r / R"); axs[1].set_ylabel("twist [deg]"); axs[1].grid(alpha=.3)
    t = o["hand_check"]["polar"]; cls = (0.2, 0.3, 0.4, 0.6, 0.8)
    for fam, c in (("24xx", "#888"), ("25xx", "#2a78d6"), ("26xx", "#d62a2a")):
        for tc, mk in ((0.09, "o-"), (0.12, "s--")):
            axs[2].plot(cls, [1e4 * t[f"{fam} t/c {tc} Cl {c0}"] for c0 in cls], mk, color=c, ms=3, label=f"{fam} t/c {tc}")
    axs[2].set_xlabel("section Cl"); axs[2].set_ylabel("Cd x 1e4 (Re 6e5, M 0.3)"); axs[2].legend(fontsize=6); axs[2].grid(alpha=.3)
    fig.suptitle("Exploration 26: 2 % camber moved aft (25xx, 26xx)", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "e26_aft_camber.png"), dpi=140); plt.close(fig)


if __name__ == "__main__":
    if sys.argv[1:] == ["plot"]:
        plot(json.load(open(os.path.join(OUT, "e26_aft_camber.json"))))
    elif sys.argv[1:] == ["hand"]:
        print({f: thin(0.02, p) for f, p in (("24xx", 0.4), ("25xx", 0.5), ("26xx", 0.6))})
    else:
        run()

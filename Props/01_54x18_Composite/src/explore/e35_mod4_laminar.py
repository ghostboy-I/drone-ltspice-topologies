"""Exploration 35: a longer-laminar-run section from coordinates: NACA 24xx-64 and 24xx-65 (4-digit-modified thickness,
maximum thickness moved from 30 % to 40 % / 50 % chord, normal leading-edge radius), against the 24xx baseline.

Moving the maximum thickness aft extends the favourable pressure gradient, so free transition (XFOIL e^N, Ncrit 9) moves
aft at low lift; the price is a steeper pressure recovery behind it, which separates earlier as lift rises. The rotor
sections run at Cl 0.3-0.5, between the two regimes, so only the full blade optimisation can tell which wins.

Coordinates: naca_mod4.py (validated: -63 reproduces the 4-digit thickness to 0.3 % chord; the XFOIL coordinate route
reproduces the built-in 2412 polar). Polars: xfoil_coords.py, same recipe and grid as the 24xx family.
Blades: the entry 28 setup at tip-Mach cap 0.60: hex (entry 11 optimiser, 24xx outboard and inboard) and tri (entry 13
optimiser, 44xx inboard / new section outboard via the t/c 0.12-0.15 hybrid), each started from its best-camber blade.
"""
import json, math, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from multiprocessing import Pool
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SUFFIXES = (None, "64", "65")
CAP = 0.60


def dbs(suffix, n_proc=1):
    import e01_coax_blade as e01, e24_chain_best_blades as e24, xfoil_coords as xc
    e01.init(); db44 = e01.G["db"]; db24 = e24.db_for("hex0", "best")
    thin = db24 if suffix is None else xc.build_db("24", suffix, e01.G["p"], n_proc=n_proc)
    return thin, db44


def job(args):
    layout, suffix = args
    import e01_coax_blade as e01, e11_blade_with_motor as e11, e13_tri_torque_margin as e13, e24_chain_best_blades as e24
    from blade_trade_study import HybridDB
    from common import RESULTS
    thin, db44 = dbs(suffix)
    bd = e24.blade_for("hex0" if layout == "hex" else "tri", "best")
    e01.G["db"] = thin if layout == "hex" else HybridDB(thin, db44); e01.G["p"]["rotor"]["tip_mach_max"] = CAP
    lab = f"{layout} 24xx{'' if suffix is None else '-' + suffix}"
    if layout == "tri":
        r = e13.optimise((lab, bd)); ref = json.load(open(os.path.join(RESULTS, "explore", "e13_tri_torque_margin.json")))["reference"]
        pay = -(r["end"]["hw"] - ref["hw"] + (r["end"]["pack"] - ref["pack"]) / e01.G["p"]["mass"]["pack_wh_per_kg_cited"])
    else:
        r = e11.optimise((lab, bd, "motor")); pay = r["end"]["payload"]
    e = r["end"]
    # section operating point at 0.75 R in hover
    import bemt, e02_coax_two_point as e02
    G = e01.G; p, hot = G["p"], G["hot"]; n = 3 if layout == "tri" else 6; R = p["rotor"]["diameter_in"] * p["constants"]["inch_to_m"] / 2
    b = e02.blade_from(r["blade"], R, p["rotor"]["hub_radius_m"]); h = bemt.hover_at_thrust(b, G["db"], hot, G["ph1"]["vehicle"]["weight_n"] / n)
    k = int(np.argmin(abs(h["r"] / R - 0.75))); cl, cd = G["db"].lookup(h["tc"][k], h["re"][k], min(h["mach"][k], 0.6), h["alpha"][k])
    return {"layout": layout, "section": "24xx" if suffix is None else f"24xx-{suffix}", "payload": pay, "pack": e["pack"], "hw": e["hw"], "rpm_hover": e["rpm_hover"],
            "solidity": e["solidity"], "margin": e["margin"], "tw_mach": e["tw_mach"], "motor_kg": e["motor_kg"], "blade": r["blade"],
            "cl_075": float(cl), "cd_075": float(cd), "re_075": float(h["re"][k]), "tc_075": float(h["tc"][k]), "mach_075": float(h["mach"][k]), "alpha_075_deg": math.degrees(float(h["alpha"][k]))}


def section_table(p):
    """Drag polars at the rotor's typical outboard condition (t/c 0.12, Re 1.2e6, M 0.30), with transition."""
    import xfoil_coords as xc, airfoils
    out = {}
    for name in ("2412", "2412-64", "2412-65"):
        rec = airfoils.polar_case((name, 1.2e6, 0.30)) if "-" not in name else xc.case((name, 1.2e6, 0.30))
        out[name] = rec["points"]
    return out


def run():
    import e01_coax_blade as e01
    from common import RESULTS, save_json
    OUT = os.path.join(RESULTS, "explore")
    for s in ("64", "65"): dbs(s, n_proc=4)                                 # build/cached polars first (4 XFOIL workers)
    with Pool(4) as pool:
        rows = pool.map(job, [(l, s) for l in ("tri", "hex") for s in SUFFIXES])
    base = {l: next(r for r in rows if r["layout"] == l and r["section"] == "24xx")["payload"] for l in ("tri", "hex")}
    for r in rows:
        r["dpayload_vs_24xx"] = r["payload"] - base[r["layout"]]
        print(f"  {r['layout']} {r['section']:9s}: payload {r['payload']:+.2f} kg ({r['dpayload_vs_24xx']:+.2f}), pack {r['pack']:.0f} Wh, hw {r['hw']:.2f} kg, rpm {r['rpm_hover']:.0f},"
              f" sigma {r['solidity']:.3f}, margin {r['margin']:.1f}; 0.75R: Cl {r['cl_075']:.3f} Cd {r['cd_075']:.5f} (t/c {r['tc_075']:.3f}, Re {r['re_075']:.2e}, M {r['mach_075']:.2f})", flush=True)
    e01.init(); sec = section_table(e01.G["p"])
    save_json(os.path.join("explore", "e35_mod4_laminar.json"), {"cap": CAP, "rows": rows, "sections_re1.2e6_m0.30": sec}); plot(rows, sec, OUT)
    print("  wrote results/explore/e35_mod4_laminar.json")


def plot(rows, sec, OUT):
    import naca_mod4 as nm
    fig, axs = plt.subplots(1, 3, figsize=(13, 3.6)); col = {"2412": "#0b0b0b", "2412-64": "#2a78d6", "2412-65": "#d62a5e"}
    x = np.linspace(0, 1, 401)
    axs[0].plot(x, 2 * nm.thickness_4digit(x, 0.12), color=col["2412"], label="4-digit (max t at 30 %)")
    axs[0].plot(x, 2 * nm.thickness(x, 0.12, 6, 0.4), color=col["2412-64"], label="-64 (40 %)"); axs[0].plot(x, 2 * nm.thickness(x, 0.12, 6, 0.5), color=col["2412-65"], label="-65 (50 %)")
    axs[0].set_xlabel("x / c"); axs[0].set_ylabel("thickness / c"); axs[0].legend(fontsize=7); axs[0].grid(alpha=.3)
    for n, pts in sec.items():
        d = np.array(pts); axs[1].plot(d[:, 2] * 1e4, d[:, 1], color=col[n], label=n); axs[2].plot(d[:, 1], d[:, 5], "-", color=col[n], label=f"{n} upper"); axs[2].plot(d[:, 1], d[:, 6], ":", color=col[n])
    axs[1].set_xlim(30, 200); axs[1].set_ylim(-0.4, 1.4); axs[1].set_xlabel("Cd x 1e4"); axs[1].set_ylabel("Cl"); axs[1].legend(fontsize=7); axs[1].grid(alpha=.3)
    axs[1].set_title("t/c 0.12, Re 1.2e6, M 0.30", fontsize=8)
    for r in rows:
        if r["section"] != "24xx": continue
        axs[1].axhline(r["cl_075"], color="#888", lw=0.7, ls="--"); axs[1].annotate(f"{r['layout']} 0.75R", (150, r["cl_075"]), fontsize=6)
    axs[2].set_xlim(-0.4, 1.4); axs[2].set_xlabel("Cl"); axs[2].set_ylabel("transition x/c (solid upper, dotted lower)"); axs[2].grid(alpha=.3); axs[2].legend(fontsize=6)
    fig.suptitle("Exploration 35: NACA 4-digit-modified sections, max thickness moved aft", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "e35_mod4_laminar.png"), dpi=140); plt.close(fig)


if __name__ == "__main__":
    run()

"""Exploration 15: what the 0.60 tip-Mach cap costs (tri and hex, blades re-optimised with torque-sized motors).

Entry 13's tri optimum sits on the cap (M 0.60 at T/W 2, hot day); entry 11's hex optimum does not (M 0.52). Re-run the
entry 11 / entry 13 optimisers with the cap at 0.50, 0.55, 0.60, 0.65, 0.70, each starting from its entry-13/11 optimum.
Caveat: the XFOIL polar grid stops at M 0.60 and the lookup clips above it, so above 0.60 the tip sections keep their
M 0.60 drag: results there are optimistic (no drag rise) and are flagged.

Hand checks:
  (1) On the cap the top speed is fixed, Omega_cap = M a / R, so Q_max = P_max / Omega_cap. If FM stays put, P_max stays put
      and Q_max ~ 1/M, motor mass ~ 1/M:  d(3 m_motor)/dM = -3 m / M.
  (2) Critical Mach of a tip section (Karman-Tsien + isentropic sonic Cp): the local flow first goes sonic where
      Cp0 / (sqrt(1-M^2) + M^2/(1+sqrt(1-M^2)) Cp0/2) = Cp*(M) = 2/(g M^2) [((2+(g-1)M^2)/(g+1))^(g/(g-1)) - 1]
  (3) Noise rule of thumb: rotational loading noise ~ V_tip^6, i.e. +60 log10(M2/M1) dB at the same thrust.
"""
import json, math, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from multiprocessing import Pool
from scipy.optimize import brentq
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import e01_coax_blade as e01
import e11_blade_with_motor as e11
import e13_tri_torque_margin as e13
from common import RESULTS, save_json

OUT = os.path.join(RESULTS, "explore")
CAPS = (0.50, 0.55, 0.60, 0.65, 0.70)
POLAR_M_MAX = 0.60
RPM_M060 = 2987.35                                             # rpm at M 0.60, hot day, 54 in (entry 13)


def job(args):
    layout, cap, bd = args
    e01.G["p"]["rotor"]["tip_mach_max"] = cap
    if layout == "tri":
        r = e13.optimise((f"tri M{cap:.2f}", bd)); end = r["end"]; pay = end["dpayload"]
    else:
        r = e11.optimise((f"hex M{cap:.2f}", bd, "motor")); end = r["end"]; pay = end["payload"]
    tip = 0.60 * end["rpm_max"] / RPM_M060                     # tip Mach scales with rpm (hot-day a fixed)
    return {"layout": layout, "cap": cap, "payload": pay, "pack": end["pack"], "Q_max": end["Q_max"], "P_max": end["P_max"], "motor_kg": end["motor_kg"],
            "rpm_hover": end["rpm_hover"], "rpm_max": end["rpm_max"], "solidity": end["solidity"], "blade_kg": end["blade_kg"], "tip_mach_at_tw2": tip,
            "flag_polar_clipped": cap > POLAR_M_MAX + 1e-9, "blade": r["blade"]}


def m_crit(cp0, g=1.4):
    kt = lambda M: cp0 / (math.sqrt(1 - M * M) + M * M / (1 + math.sqrt(1 - M * M)) * cp0 / 2)
    star = lambda M: 2 / (g * M * M) * (((2 + (g - 1) * M * M) / (g + 1)) ** (g / (g - 1)) - 1)
    return brentq(lambda M: kt(M) - star(M), 0.2, 0.9)      # above ~0.95 the Karman-Tsien denominator crosses zero


def run():
    t0 = time.time(); e01.init()
    e13r = json.load(open(os.path.join(OUT, "e13_tri_torque_margin.json"))); e11r = json.load(open(os.path.join(OUT, "e11_blade_with_motor.json")))
    tri0 = max(e13r["runs"], key=lambda r: r["end"]["dpayload"])["blade"]
    hex0 = max((r for r in e11r["runs"] if r["mode"] == "motor"), key=lambda r: r["end"]["payload"])["blade"]
    jobs = [("tri", c, tri0) for c in CAPS] + [("hex", c, hex0) for c in CAPS if c <= 0.55]
    with Pool(4, initializer=e01.init) as pool:
        rows = pool.map(job, jobs)
    save_json(os.path.join("explore", "e15_tip_mach_cap.json"), {"rows": rows})
    for r in rows:
        print(f"  {r['layout']} cap {r['cap']:.2f}: payload {r['payload']:+.2f} kg, pack {r['pack']:.0f} Wh, Q_max {r['Q_max']:.1f}, motor {r['motor_kg']:.2f} kg,"
              f" rpm_h {r['rpm_hover']:.0f}, rpm_max {r['rpm_max']:.0f}, sigma {r['solidity']:.3f}, M(T/W2) {r['tip_mach_at_tw2']:.3f}{'  [polar clipped]' if r['flag_polar_clipped'] else ''}", flush=True)
    tri = {r["cap"]: r for r in rows if r["layout"] == "tri"}
    m6 = tri[0.60]["motor_kg"]
    hc = {"motor_slope_hand_kg_per_M": -3 * m6 / 0.60, "motor_slope_fd_kg_per_M": 3 * (tri[0.55]["motor_kg"] - tri[0.60]["motor_kg"]) / (0.55 - 0.60),
          "payload_slope_fd_kg_per_M_055_060": (tri[0.60]["payload"] - tri[0.55]["payload"]) / 0.05,
          "Q_ratio_055_over_060": tri[0.55]["Q_max"] / tri[0.60]["Q_max"], "hand_Q_ratio_inverse_M": 0.60 / 0.55,
          "m_crit": {cp: m_crit(cp) for cp in (-0.6, -0.8, -1.0, -1.2)},
          "noise_db_vs_060": {c: 60 * math.log10(c / 0.60) for c in CAPS}}
    print(f"  hand: {hc}")
    out = {"rows": rows, "hand_check": hc, "runtime_s": time.time() - t0}
    save_json(os.path.join("explore", "e15_tip_mach_cap.json"), out); plot(out)
    print(f"  wrote results/explore/e15_tip_mach_cap.json in {out['runtime_s']:.0f} s")


def plot(o):
    fig, axs = plt.subplots(1, 2, figsize=(9, 3.3))
    for lay, col in (("tri", "#0b0b0b"), ("hex", "#2a78d6")):
        rs = sorted((r for r in o["rows"] if r["layout"] == lay), key=lambda r: r["cap"])
        x = [r["cap"] for r in rs]
        axs[0].plot(x, [r["payload"] for r in rs], "o-", color=col, label=lay)
        axs[1].plot(x, [r["Q_max"] for r in rs], "o-", color=col, label=lay)
    for a in axs: a.axvspan(0.60, 0.72, color="#ccc", alpha=.4, lw=0); a.set_xlabel("tip-Mach cap at T/W 2"); a.grid(alpha=.3)
    axs[0].set_ylabel("payload vs Phase 2 tri [kg]"); axs[1].set_ylabel("Q_max per rotor [N m]"); axs[0].legend(fontsize=7)
    axs[0].text(0.605, axs[0].get_ylim()[0], " polar clipped", fontsize=6, va="bottom")
    fig.suptitle("Exploration 15: cost of the tip-Mach cap (blades re-optimised with torque-sized motors)", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "e15_tip_mach_cap.png"), dpi=140); plt.close(fig)


if __name__ == "__main__":
    if sys.argv[1:] == ["plot"]:
        plot(json.load(open(os.path.join(OUT, "e15_tip_mach_cap.json"))))
    else:
        run()

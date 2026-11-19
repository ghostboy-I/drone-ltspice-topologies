"""Exploration 49: decision curves at the 10 % reserve (from entry 48's chain points; no new BEMT), and the Y6 re-scored
with catalogue motors.

(1) hex - tri payload against pack specific energy e_b (150-400 Wh/kg), at 15 m/s and at each layout's best speed
    (re-optimised for every e_b), for the 24xx and 24xx-64 designs: payload difference = sum_tri - sum_hex with
    sum = hw + pack / e_b (entry 19's bookkeeping).
(2) Y6 (entry 12's best arm: 27.2 N m at T/W 2, fitted motor 2.44 kg) on catalogue motors: the MN1320 at a 10 %
    reserve allows 0.90 x 32.44 = 29.2 N m, so it fits without re-optimisation; payload change = 6 (2.44 - 2.07).
"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import e19_ranking as e19
from common import RESULTS, save_json

OUT = os.path.join(RESULTS, "explore")


def run():
    pts = json.load(open(os.path.join(OUT, "e48_chain_10pct.json")))["points"]
    rows = lambda k, c: e19.rows({"cases": {f"{c}|x": {"rows": sorted((q for q in pts if q["key"] == k), key=lambda q: q["V"])}}}, c, "x")
    ebs = np.arange(150.0, 400.1, 5.0); curves = {}
    for sec in ("24xx", "24xx-64"):
        for sp, v in (("15 m/s", 15.0), ("free", None)):
            y = [e19.best(rows(f"tri {sec}", "tri"), eb, v)["sum"] - e19.best(rows(f"hex {sec}", "hex0"), eb, v)["sum"] for eb in ebs]
            i = np.where(np.diff(np.sign(y)))[0]
            cross = float(np.interp(0, [y[i[0] + 1], y[i[0]]], [ebs[i[0] + 1], ebs[i[0]]])) if len(i) else None
            curves[f"{sec} | {sp}"] = {"hex_minus_tri": y, "breakeven_wh_kg": cross}
            print(f"  {sec:8s} {sp:7s}: break-even {cross} Wh/kg; at 250 {y[20]:+.2f}, 303 ~{np.interp(303.3, ebs, y):+.2f}, 350 {y[40]:+.2f} kg", flush=True)
    y6 = {"Q_max": 27.2, "motor_fit_kg": 2.44, "catalogue": "MN1320 KV49", "catalogue_kg": 2.070, "limit_10pct": 0.90 * 32.44, "payload_vs_tri_fit": -0.43}
    y6["fits"] = y6["Q_max"] <= y6["limit_10pct"]; y6["payload_change"] = 6 * (y6["motor_fit_kg"] - y6["catalogue_kg"])
    print("  y6:", y6, flush=True)
    out = {"e_b": ebs.tolist(), "curves": curves, "y6": y6}
    save_json(os.path.join("explore", "e49_decision_curves.json"), out)
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    sty = {"24xx | 15 m/s": ("#2a78d6", "-"), "24xx-64 | 15 m/s": ("#2a78d6", "--"), "24xx | free": ("#0b0b0b", "-"), "24xx-64 | free": ("#0b0b0b", "--")}
    for k, c in curves.items():
        col, ls = sty[k]; ax.plot(ebs, c["hex_minus_tri"], ls, color=col, label=f"{k}" + (f" (break-even {c['breakeven_wh_kg']:.0f})" if c["breakeven_wh_kg"] else ""))
    ax.axhline(0, color="#888", lw=0.8); ax.axvline(303.3, color="#888", ls=":", lw=0.8); ax.axvline(200, color="#888", ls=":", lw=0.8)
    ax.text(303.3, ax.get_ylim()[1], " semi-solid", fontsize=7, va="top"); ax.text(200, ax.get_ylim()[1], " LiPo", fontsize=7, va="top")
    ax.set_xlabel("pack specific energy [Wh/kg]"); ax.set_ylabel("hex payload minus tri payload [kg]"); ax.grid(alpha=.3); ax.legend(fontsize=7)
    ax.set_title("Exploration 49: layout vs battery at a 10 % torque reserve (hex 50 dBA, tri 60 dBA)", fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "e49_decision_curves.png"), dpi=140); plt.close(fig)
    print("  wrote results/explore/e49_decision_curves.json and .png")


if __name__ == "__main__":
    run()

"""Exploration 43: BEMT calibrated on the toroid session's 2-blade reference CFD (queue item 44, 2026-11-18).

The toroid session solved this program's final 2-blade blade (results/blade_final.csv) in OpenFOAM at 2280 rpm in
45 C sea-level air: T = 437.4 N, Q = 35.88 N m, FoM 0.590 (converged, 1500 iterations; read from
Props/02_Toroidal_Rotor/results/cfd_reference.json, not modified here). Plain BEMT over-predicts thrust by ~25-30 %.

Correction model (the toroid session's, src/optimize.py there):  theta_eff = theta - a0   and   cd_eff = cd + dcd,
fitted here to the two totals (T, Q) with a uniform a0 (its a1 = 0 case). Also a thrust-only fit (a0 alone, dcd = 0).

Then the key designs of entries 38-42 are re-evaluated in entry 41's chain (constant body, 15 m/s) under:
  plain       : uncorrected BEMT
  as built    : a0 and dcd applied to the blade as designed
  re-pitched  : dcd only (a designer adds a0 of collective back: a uniform pitch loss is fully recoverable)
and checked against each catalogue motor's 12 % reserve torque (entry 39) at T/W 2.
Single process, nice 19 (toroid CFD running).
"""
import json, math, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from scipy.optimize import least_squares, brentq
import bemt
import e01_coax_blade as e01
import e02_coax_two_point as e02
import e17_blade_at_best_speed as e17
import e18_body_incidence as e18
import e24_chain_best_blades as e24
from common import RESULTS, save_json

OUT = os.path.join(RESULTS, "explore")
CFD = {"rpm": 2280.0, "T": 437.36038602016663, "Q": 35.88058575356666, "FoM": 0.5896405821585474}
LIM = {"MN1123 KV53": (1.425, 0.88 * 22.19), "MN1320 KV49": (2.070, 0.88 * 32.4), "V13828 55KV": (2.465, 0.88 * 43.1), "U15XL KV38": (4.408, 0.88 * 50.4)}


class DragShift:
    def __init__(self, db, dcd): self.db, self.dcd = db, dcd
    def lookup(self, tc, re, mach, alpha):
        cl, cd = self.db.lookup(tc, re, mach, alpha); return cl, cd + self.dcd
    def __getattr__(self, k): return getattr(self.db, k)


def shift(b, a0):
    return bemt.Blade(b.R, b.r_hub, b.N, b.r_def, b.c_def, b.th_def - math.radians(a0), b.tc_def)


def calibrate():
    G = e01.G; p, db, hot = G["p"], G["db"], G["hot"]
    d = np.loadtxt(os.path.join(RESULTS, "blade_final.csv"), delimiter=",", comments="#", skiprows=2)
    R = p["rotor"]["diameter_in"] * p["constants"]["inch_to_m"] / 2
    b = bemt.Blade(R, p["rotor"]["hub_radius_m"], p["rotor"]["n_blades"], d[:, 0], d[:, 2], np.radians(d[:, 3]), d[:, 4])
    run = lambda a0, dcd: bemt.axial(shift(b, a0), DragShift(db, dcd), hot, CFD["rpm"], 0.0, n=60)
    plain = run(0, 0)
    fa = least_squares(lambda x: [run(x[0], 0)["T"] / CFD["T"] - 1], x0=[3.0]); A = run(fa.x[0], 0)
    fb = least_squares(lambda x: [run(x[0], x[1])["T"] / CFD["T"] - 1, run(x[0], x[1])["Q"] / CFD["Q"] - 1], x0=[3.0, 0.02], bounds=([-5, -0.02], [12, 0.2])); B = run(*fb.x)
    out = {"air": {"rho": hot["rho"], "a": hot["a"], "mu": hot["mu"]}, "R": R, "cfd": CFD,
           "plain": {"T": plain["T"], "Q": plain["Q"], "P": plain["P"]},
           "thrust_only": {"a0_deg": float(fa.x[0]), "T": A["T"], "Q": A["Q"]},
           "full": {"a0_deg": float(fb.x[0]), "dcd": float(fb.x[1]), "T": B["T"], "Q": B["Q"], "P": B["P"]}}
    print("  calibration:", json.dumps(out), flush=True)
    return out


def designs():
    e38 = json.load(open(os.path.join(OUT, "e38_motor_survey.json")))["rows"]; e39 = json.load(open(os.path.join(OUT, "e39_torque_reserve.json")))["rows"]
    e40 = json.load(open(os.path.join(OUT, "e40_tri_u15xl_reserve.json")))["rows"]
    return [("hex MN1123 (e39, cap 0.65)", "hex0", "MN1123 KV53", next(r["blade"] for r in e39 if r["layout"] == "hex" and r["cap"] == 0.65)),
            ("hex MN1320 (e38, cap 0.60)", "hex0", "MN1320 KV49", next(r["blade"] for r in e38 if r["motor"] == "MN1320 KV49")),
            ("tri V13828 (e39, cap 0.80)", "tri", "V13828 55KV", next(r["blade"] for r in e39 if r["layout"] == "tri" and r["cap"] == 0.80)),
            ("tri U15XL (e40, cap 0.70)", "tri", "U15XL KV38", next(r["blade"] for r in e40 if r["cap"] == 0.70))]


def evaluate(c, bd, motor, a0, dcd):
    G = e01.G; p = G["p"]; base = e24.db_for(c, "best"); db0 = G["db"]; G["db"] = DragShift(base, dcd); e17.cruise = e18.make_cruise("constant")
    S = e17.setup(c); Rr = p["rotor"]["diameter_in"] * p["constants"]["inch_to_m"] / 2
    b = shift(e02.blade_from(bd, Rr, p["rotor"]["hub_radius_m"]), a0)
    try:
        r = e17.evaluate(b, S, 15.0)
        W = G["ph1"]["vehicle"]["weight_n"]; mkg, qlim = LIM[motor]
        q_of = lambda tw: bemt.hover_at_thrust(b, G["db"], G["hot"], tw * W / S["n"])["Q"] - qlim
        try: tw_lim = brentq(q_of, 1.0, 3.5, xtol=1e-3)
        except ValueError: tw_lim = float("nan")
        h = bemt.hover_at_thrust(b, G["db"], G["hot"], W / S["n"])
    finally:
        G["db"] = db0
    return {"mass_sum_cat": r["mass_sum"] - S["n"] * (r["motor_kg"] - mkg), "pack": r["pack"], "hover_w": r["hover"], "cruise_w": r["cruise"], "Q_max": r["Q_max"],
            "Q_limit": qlim, "fits": r["Q_max"] <= qlim * 1.01, "tw_at_limit": tw_lim, "rpm_hover": r["rpm_hover"], "rpm_max": r["rpm_max"], "FoM_hover": h.get("FoM", float("nan"))}


def run():
    e01.init(); cal = calibrate(); a0, dcd = cal["full"]["a0_deg"], cal["full"]["dcd"]
    rows = []
    for name, c, motor, bd in designs():
        row = {"design": name, "layout": c, "motor": motor}
        for tag, (x0, x1) in {"plain": (0.0, 0.0), "as_built": (a0, dcd), "repitched": (0.0, dcd), "thrust_only": (cal["thrust_only"]["a0_deg"], 0.0)}.items():
            row[tag] = evaluate(c, bd, motor, x0, x1)
            q = row[tag]; print(f"  {name:28s} {tag:11s}: mass_sum {q['mass_sum_cat']:.2f} kg, pack {q['pack']:.0f} Wh, hover {q['hover_w']:.0f} W, Q_max {q['Q_max']:.2f}/{q['Q_limit']:.2f} N m"
                                f" (fits {q['fits']}), T/W at limit {q['tw_at_limit']:.2f}, rpm {q['rpm_hover']:.0f}/{q['rpm_max']:.0f}", flush=True)
        rows.append(row)
    save_json(os.path.join("explore", "e43_cfd_calibration.json"), {"calibration": cal, "rows": rows}); print("  wrote results/explore/e43_cfd_calibration.json")


if __name__ == "__main__":
    run()

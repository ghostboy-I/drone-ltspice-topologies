"""Exploration 37: catalogue motors instead of the continuous mass fit.

Since entry 10 every optimiser sized the motor continuously, m = 0.0909 tau^0.996 kg, fitted through three T-Motor
units (U13II 0.975 kg / 11.4 N m, U15II 1.740 kg / 18.0 N m, U15XL 4.408 kg / 50.4 N m; 100 %-throttle test torques).
The tri's optimum needs 50.6 N m and lands on the U15XL (entry 13). The hex's needs 20.5 N m: between the U15II and the
U15XL, so its fitted 1.84 kg motor does not exist in that list.

Here: (1) re-score the cap-0.60 optima with the lightest listed motor whose test torque covers Q_max at T/W 2
(tolerance 1 %); (2) re-optimise the hex to fit the U15II: motor mass fixed at 1.740 kg and a penalty on Q_max > 18.0 N m,
at tip-Mach caps 0.60 / 0.65 / 0.70 (higher rpm, less torque for the same power: Q = P / Omega); the tri re-optimised
to the U15XL the same way (4.408 kg, Q_max <= 50.4 N m). ESC mass keeps its P^0.7 scaling. Noise of each result scored
as in entry 34 (BPM trailing edge + rounded tip vortex + Gutin tones, 50 m, 30 deg below the disk).
Runs on 2 cores at nice 19 while the toroid session's CFD runs.
"""
import json, math, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from multiprocessing import Pool
import numpy as np

CAT = [("U13II KV65", 0.975, 11.4), ("U15II KV80", 1.740, 18.0), ("U15XL KV38", 4.408, 50.4)]
TOL = 1.01
JOBS = [("hex", 0.60, "U15II KV80"), ("hex", 0.65, "U15II KV80"), ("hex", 0.70, "U15II KV80"), ("tri", 0.60, "U15XL KV38")]
HARD_JOBS = [("hex", 0.60, "U15II KV80", "hard"), ("hex", 0.65, "U15II KV80", "hard")]   # second pass: penalty x20, so the torque limit binds


def pick(q):
    for name, m, t in CAT:
        if q <= t * TOL: return name, m
    return None, float("nan")


def noise(layout, blade):
    import e30_bpm_rotor as e30, e31_tip_noise as e31
    te = e30.rotor_bpm(layout, blade); tip = e31.tip_rotor(layout, blade)
    bb = e31.dba(10 ** (np.array(te["spectrum"]) / 10) + 10 ** (np.array(tip["rounded_G"]["spectrum"]) / 10))
    return {"te_dba": te["dba"], "tonal_dba": te["tonal_dba"], "total_dba": 10 * math.log10(10 ** (bb / 10) + 10 ** (te["tonal_dba"] / 10))}


def job(args):
    layout, cap, target = args[:3]; k = 20.0 if len(args) > 3 else 1.0
    import e01_coax_blade as e01, e11_blade_with_motor as e11, e13_tri_torque_margin as e13, e24_chain_best_blades as e24
    from common import RESULTS
    e01.init(); n = 6 if layout == "hex" else 3; mname, mkg, tq = next(c for c in CAT if c[0] == target)
    e01.G["db"] = e24.db_for("hex0" if layout == "hex" else "tri", "best"); e01.G["p"]["rotor"]["tip_mach_max"] = cap
    mod = e11 if layout == "hex" else e13; orig = mod.evaluate; whkg = e01.G["p"]["mass"]["pack_wh_per_kg_cited"]
    ref13 = json.load(open(os.path.join(RESULTS, "explore", "e13_tri_torque_margin.json")))["reference"]

    def ev(b, S, *a):
        r = orig(b, S, *a)
        dm = n * (r["motor_kg"] - mkg)                                   # catalogue motor instead of the fitted one
        r["hw"] -= dm; r["motor_kg_fit"] = r["motor_kg"]; r["motor_kg"] = mkg
        over = max(0.0, r["Q_max"] / tq - 1.0)
        if layout == "hex": r["payload"] += dm; r["payload_cat"] = r["payload"]; r["payload"] -= k * (400 * over ** 2 + 20 * over)
        else:
            r["payload_cat"] = -(r["hw"] - ref13["hw"] + (r["pack"] - ref13["pack"]) / whkg)
            if "dpayload" in r: r["dpayload"] = r["payload_cat"] - k * (400 * over ** 2 + 20 * over)
        return r
    mod.evaluate = ev
    bd = e24.blade_for("hex0" if layout == "hex" else "tri", "best")
    try:
        res = e11.optimise((f"hex cap {cap:.2f} -> {mname}", bd, "motor")) if layout == "hex" else e13.optimise((f"tri cap {cap:.2f} -> {mname}", bd))
        S = mod.setup(); import e02_coax_two_point as e02
        R = e01.G["p"]["rotor"]["diameter_in"] * e01.G["p"]["constants"]["inch_to_m"] / 2
        b = e02.blade_from(res["blade"], R, e01.G["p"]["rotor"]["hub_radius_m"])
        end = ev(b, S, ref13) if layout == "tri" else ev(b, S)
    finally:
        mod.evaluate = orig
    out = {"penalty": "hard" if k > 1 else "soft", "layout": layout, "cap": cap, "motor": mname, "motor_kg": mkg, "motor_torque": tq, "payload_cat": end["payload_cat"], "Q_max": end["Q_max"],
           "fits": end["Q_max"] <= tq * TOL, "pack": end["pack"], "hw": end["hw"], "rpm_hover": end["rpm_hover"], "rpm_max": end["rpm_max"],
           "P_max": end["P_max"], "solidity": end["solidity"], "margin": end["margin"], "tw_mach": end["tw_mach"], "blade": res["blade"]}
    out.update(noise(layout, res["blade"]))
    print(f"  [{'hard' if k > 1 else 'soft'}] {layout} cap {cap:.2f} -> {mname}: payload {out['payload_cat']:+.2f} kg, Q_max {out['Q_max']:.2f} N m (limit {tq}), fits {out['fits']},"
          f" rpm hover/max {out['rpm_hover']:.0f}/{out['rpm_max']:.0f}, P_max {out['P_max']:.0f} W, pack {out['pack']:.0f} Wh, hw {out['hw']:.2f} kg, sigma {out['solidity']:.3f},"
          f" T/W at cap {out['tw_mach']:.2f}, total {out['total_dba']:.1f} dBA", flush=True)
    return out


def rescore():
    """the cap-0.60 continuous-fit optima of entries 28 and 35, with catalogue motors"""
    from common import RESULTS
    import e01_coax_blade as e01
    e01.init(); whkg = e01.G["p"]["mass"]["pack_wh_per_kg_cited"]
    e28 = json.load(open(os.path.join(RESULTS, "explore", "e28_noise_cap.json"))); e35 = json.load(open(os.path.join(RESULTS, "explore", "e35_mod4_laminar.json")))
    rows = []
    for x in e28["rows"]:
        if x["cap"] != 0.60: continue
        n = 6 if x["layout"] == "hex" else 3; name, m = pick(x["Q_max"])
        d = n * (x["motor_kg"] - m) if name else float("nan")
        rows.append({"case": f"{x['layout']} 24xx cap 0.60 (entry 28)", "layout": x["layout"], "Q_max": x["Q_max"], "motor_fit_kg": x["motor_kg"], "catalogue": name, "catalogue_kg": m,
                     "payload_fit": x["payload"], "payload_cat": x["payload"] + d})
    for x in e35["rows"]:
        if x["section"] != "24xx-64": continue
        n = 6 if x["layout"] == "hex" else 3
        rows.append({"case": f"{x['layout']} 24xx-64 cap 0.60 (entry 35)", "layout": x["layout"], "motor_fit_kg": x["motor_kg"], "payload_fit": x["payload"]})
    return rows


def run_hard():
    from common import RESULTS, save_json
    p = os.path.join(RESULTS, "explore", "e37_catalogue_motor.json"); o = json.load(open(p))
    with Pool(2) as pool:
        o["rows"] = [r for r in o["rows"] if r.get("penalty", "soft") == "soft"] + pool.map(job, HARD_JOBS)
    for r in o["rows"]: r.setdefault("penalty", "soft")
    save_json(os.path.join("explore", "e37_catalogue_motor.json"), o); print("  wrote results/explore/e37_catalogue_motor.json (with hard-penalty rows)")


def run():
    from common import RESULTS, save_json
    rs = rescore()
    for r in rs: print("  rescore:", {k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()})
    with Pool(2) as pool:
        rows = pool.map(job, JOBS)
    save_json(os.path.join("explore", "e37_catalogue_motor.json"), {"catalogue": CAT, "tolerance": TOL, "rescore": rs, "rows": rows})
    print("  wrote results/explore/e37_catalogue_motor.json")


if __name__ == "__main__":
    run_hard() if "--hard" in sys.argv else run()

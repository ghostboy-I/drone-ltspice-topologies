"""Exploration 41: the speed / body / battery scenarios with catalogue motors and a 12 % torque reserve (queue item 50).

Entries 37-40 compared the layouts exactly only at 15 m/s with the 303 Wh/kg pack; the other scenarios were shifted by
(delta hex - delta tri). Here the re-optimised blades of entries 39-40 go through entry 24's full chain (entry 17/18
vehicle model: arms, fairings, hover download, cruise trim with the four body models at 14-30 m/s, mission energy)
and entry 19's ranking (15 m/s and free speed; 303.3 and 200 Wh/kg). The fitted motor mass is replaced by the
catalogue motor's mass: mass_sum -= n (m_fit - m_cat). Variants:
  base    : entry 24's best-camber blades, continuous motor fit (regression check against entry 24's ranking)
  hex     : MN1123 (1.425 kg), 12 % reserve, cap 0.65 blade (entry 39)
  tri-V   : V13828 (2.465 kg), 12 % reserve, cap 0.80 blade (entry 39)
  tri-XL  : U15XL (4.408 kg), 12 % reserve, cap 0.70 blade (entry 40)
2 cores, nice 19, while the toroid CFD runs.
"""
import json, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from multiprocessing import Pool
import e01_coax_blade as e01
import e02_coax_two_point as e02
import e17_blade_at_best_speed as e17
import e18_body_incidence as e18
import e19_ranking as e19
import e24_chain_best_blades as e24
from common import RESULTS, save_json

OUT = os.path.join(RESULTS, "explore")
MOTOR = {"hex": ("MN1123 KV53", 1.425), "tri-V": ("V13828 55KV", 2.465), "tri-XL": ("U15XL KV38", 4.408)}


def blade(var):
    if var.startswith("base"): return e24.blade_for(var.split(":")[1], "best")
    if var == "tri-XL": return next(r["blade"] for r in json.load(open(os.path.join(OUT, "e40_tri_u15xl_reserve.json")))["rows"] if r["cap"] == 0.70)
    lay, cap = ("hex", 0.65) if var == "hex" else ("tri", 0.80)
    return next(r["blade"] for r in json.load(open(os.path.join(OUT, "e39_torque_reserve.json")))["rows"] if r["layout"] == lay and r["cap"] == cap)


def point(args):
    var, model, V = args
    c = "hex0" if var in ("hex", "base:hex0") else "tri"
    db44 = e01.G["db"]; e01.G["db"] = e24.db_for(c, "best"); e17.cruise = e18.make_cruise(model)
    S = e17.setup(c); p = e01.G["p"]; Rr = p["rotor"]["diameter_in"] * p["constants"]["inch_to_m"] / 2
    b = e02.blade_from(blade(var), Rr, p["rotor"]["hub_radius_m"])
    try:
        r = e17.evaluate(b, S, V)
    finally:
        e01.G["db"] = db44
    m_fit = r["motor_kg"]; m = MOTOR[var][1] if var in MOTOR else m_fit
    return {"var": var, "layout": c, "model": model, "V": V, "mass_sum": r["mass_sum"] - S["n"] * (m_fit - m), "pack": r["pack"],
            "motor_fit_kg": m_fit, "motor_kg": m, "Q_max": r["Q_max"], "rpm_max": r["rpm_max"], "cruise_w": r["cruise"]}


def cases(pts, var):
    c = "hex0" if var in ("hex", "base:hex0") else "tri"
    return {f"{c}|{m}": {"rows": sorted((r for r in pts if r["var"] == var and r["model"] == m), key=lambda r: r["V"])} for m in e18.MODELS}


def run():
    t0 = time.time(); e01.init()
    VARS = ("base:hex0", "base:tri", "hex", "tri-V", "tri-XL")
    jobs = [(v, m, V) for v in VARS for m in e18.MODELS for V in e18.SPEEDS]
    with Pool(2, initializer=e01.init) as pool:
        pts = pool.map(point, jobs, chunksize=4)
    out = {"variants": VARS, "motors": MOTOR, "points": pts, "rankings": {}}
    for name, (h, t) in {"base (entry 24)": ("base:hex0", "base:tri"), "hex MN1123 vs tri V13828": ("hex", "tri-V"), "hex MN1123 vs tri U15XL": ("hex", "tri-XL")}.items():
        rk = e24.ranking({**cases(pts, h), **cases(pts, t)}); out["rankings"][name] = rk
        for x in rk["scenarios"]:
            print(f"  [{name}] {x['speed']:7s} {x['body']:17s} {x['e_b']:5.0f} Wh/kg: hex - tri {x['hex_minus_tri_kg']:+5.2f} kg, V {x['V_tri']:.1f}/{x['V_hex']:.1f},"
                  f" pack {x['pack_tri']:.0f}/{x['pack_hex']:.0f} Wh, dhw {x['dhw_kg']:+.2f} kg, break-even {x['e_b_breakeven']:.0f} Wh/kg", flush=True)
        print(f"  [{name}] break-even e_b: {rk['breakeven']}", flush=True)
    out["runtime_s"] = time.time() - t0
    save_json(os.path.join("explore", "e41_scenarios_catalogue.json"), out); print("  wrote results/explore/e41_scenarios_catalogue.json")


if __name__ == "__main__":
    run()

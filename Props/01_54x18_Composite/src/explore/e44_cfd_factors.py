"""Exploration 44: both layouts re-optimised with the CFD's equal-thrust factors (queue item 54, 2026-11-18).

Entry 43: at equal thrust the 2-blade reference CFD needs K_RPM = 1.156 x the rpm, K_Q = 1.229 x the torque and
K_P = 1.421 x the power of plain BEMT (FoM 0.59 vs 0.84). Here bemt.hover_at_thrust is wrapped so every hover / T/W-2
point it returns carries those factors (rpm, Q, P scaled; spanwise arrays untouched), in all optimisers and in the
chain. Assumptions: the factors are constant across loading and rotor (one CFD point); cruise (edgewise) is left
plain, since forward flight is profile- and parasite-dominated and no CFD exists for it.
Jobs (hard torque penalty, entry 37's job()):
  hex  MN1320 (12 % reserve, 28.5 N m) at caps 0.60, 0.65;  hex V13828 (12 % reserve, 37.9 N m) at cap 0.60
  tri  U15XL with NO reserve (50.4 N m) at cap 0.70;        tri U15XL 12 % reserve (44.35 N m) at cap 0.70
Then the best hex and best tri through entry 41's chain (constant body, 14-30 m/s): hex - tri at 15 m/s and free speed,
303 and 200 Wh/kg. 2 cores, nice 19 (toroid CFD running).
"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from multiprocessing import Pool
import bemt

K_RPM, K_Q, K_P = 1.1563, 1.2293, 1.4215
_orig = bemt.hover_at_thrust


def patched(*a, **kw):
    r = dict(_orig(*a, **kw)); r["rpm"] *= K_RPM; r["Q"] *= K_Q; r["P"] *= K_P
    if "FoM" in r: r["FoM"] /= K_P
    return r


def install():
    bemt.hover_at_thrust = patched


import e37_catalogue_motor as e37
import e38_motor_survey as e38
import e39_torque_reserve as e39

JOBS = [("hex", 0.60, "MN1320 KV49", "hard", "res"), ("hex", 0.65, "MN1320 KV49", "hard", "res"), ("hex", 0.60, "V13828 55KV", "hard", "res"),
        ("tri", 0.70, "U15XL KV38", "hard", "nores"), ("tri", 0.70, "U15XL KV38", "hard", "res")]


def job(a):
    install(); e37.CAT = e39.CAT if a[4] == "res" else e38.CAT
    r = e37.job(a[:4]); r["reserve"] = a[4]; return r


def point(args):
    install()
    import e01_coax_blade as e01, e02_coax_two_point as e02, e17_blade_at_best_speed as e17, e18_body_incidence as e18, e24_chain_best_blades as e24
    c, bd, mkg, V = args
    db44 = e01.G["db"]; e01.G["db"] = e24.db_for(c, "best"); e17.cruise = e18.make_cruise("constant")
    S = e17.setup(c); p = e01.G["p"]; Rr = p["rotor"]["diameter_in"] * p["constants"]["inch_to_m"] / 2
    b = e02.blade_from(bd, Rr, p["rotor"]["hub_radius_m"])
    try:
        r = e17.evaluate(b, S, V)
    finally:
        e01.G["db"] = db44
    return {"layout": c, "V": V, "mass_sum": r["mass_sum"] - S["n"] * (r["motor_kg"] - mkg), "pack": r["pack"], "hover_w": r["hover"], "Q_max": r["Q_max"]}


def run():
    from common import save_json
    import e01_coax_blade as e01, e18_body_incidence as e18, e19_ranking as e19
    with Pool(2) as pool:
        rows = pool.map(job, JOBS)
    for r in rows: r["fits"] = bool(r["fits"])
    ok = lambda L: [r for r in rows if r["layout"] == L and r["fits"]] or [r for r in rows if r["layout"] == L]
    hx = max(ok("hex"), key=lambda r: r["payload_cat"]); tr = max(ok("tri"), key=lambda r: r["payload_cat"])
    with Pool(2, initializer=e01.init) as pool:
        pts = pool.map(point, [("hex0", hx["blade"], hx["motor_kg"], V) for V in e18.SPEEDS] + [("tri", tr["blade"], tr["motor_kg"], V) for V in e18.SPEEDS], chunksize=4)
    rs = lambda c: sorted((q for q in pts if q["layout"] == c), key=lambda q: q["V"])
    rank = {}
    for eb in (e19.EB_CITED, e19.EB_CONS):
        for sp, v in (("15 m/s", 15.0), ("free", None)):
            t = e19.best(e19.rows({"cases": {"tri|c": {"rows": rs("tri")}}}, "tri", "c"), eb, v); h = e19.best(e19.rows({"cases": {"hex0|c": {"rows": rs("hex0")}}}, "hex0", "c"), eb, v)
            rank[f"{sp} {eb:.0f}"] = {"hex_minus_tri": t["sum"] - h["sum"], "V_tri": t["V"], "V_hex": h["V"], "pack_tri": t["pack"], "pack_hex": h["pack"], "hw_tri": t["hw"], "hw_hex": h["hw"],
                                     "sum_tri": t["sum"], "sum_hex": h["sum"]}
            print(f"  {sp} {eb:.0f} Wh/kg: hex - tri {rank[f'{sp} {eb:.0f}']['hex_minus_tri']:+.2f} kg (sum hex {h['sum']:.2f}, tri {t['sum']:.2f}; pack {h['pack']:.0f}/{t['pack']:.0f} Wh; V {h['V']:.1f}/{t['V']:.1f})", flush=True)
    save_json(os.path.join("explore", "e44_cfd_factors.json"), {"factors": {"rpm": K_RPM, "Q": K_Q, "P": K_P}, "rows": rows, "chosen": {"hex": f"{hx['motor']} cap {hx['cap']}", "tri": f"{tr['motor']} cap {tr['cap']} {tr['reserve']}"},
                                                             "points": pts, "ranking": rank})
    print("  wrote results/explore/e44_cfd_factors.json")


if __name__ == "__main__":
    run()

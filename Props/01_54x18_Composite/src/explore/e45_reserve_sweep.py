"""Exploration 45: sweep the torque reserve, 0 / 5 / 8 / 12 %, for the hex MN1123 and the tri V13828 (queue item 53).

Entries 38-42 (plain BEMT): no reserve, hex MN1123 +6.37 kg (48.5 dBA), tri V13828 +6.87 kg (55.9 dBA); 12 % reserve,
hex +5.06 kg (50.8 dBA), tri +4.37 kg (61.4 dBA). Here the in-between reserves are optimised (e37 job(), hard
penalty, catalogue torque x (1 - reserve)) and all eight designs go through entry 41's chain (constant body, 14-30 m/s,
best speed at 303.3 and 200 Wh/kg) to give hex - tri against the reserve, with each design's hover dBA.
Plain BEMT (the CFD question of entries 43-44 is left open). 2 cores, nice 19 (toroid CFD running).
"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from multiprocessing import Pool
import e37_catalogue_motor as e37
import e38_motor_survey as e38
from common import RESULTS, save_json

OUT = os.path.join(RESULTS, "explore")
NEW = [("hex", 0.65, "MN1123 KV53", 0.05), ("hex", 0.65, "MN1123 KV53", 0.08), ("tri", 0.75, "V13828 55KV", 0.05), ("tri", 0.80, "V13828 55KV", 0.08)]


def opt(a):
    lay, cap, m, res = a
    e37.CAT = [(n, mk, t * (1 - res)) for n, mk, t in e38.CAT]
    r = e37.job((lay, cap, m, "hard")); r["reserve"] = res; return r


def point(args):
    import e01_coax_blade as e01, e02_coax_two_point as e02, e17_blade_at_best_speed as e17, e18_body_incidence as e18, e24_chain_best_blades as e24
    key, c, bd, mkg, V = args
    db44 = e01.G["db"]; e01.G["db"] = e24.db_for(c, "best"); e17.cruise = e18.make_cruise("constant")
    S = e17.setup(c); p = e01.G["p"]; Rr = p["rotor"]["diameter_in"] * p["constants"]["inch_to_m"] / 2
    b = e02.blade_from(bd, Rr, p["rotor"]["hub_radius_m"])
    try:
        r = e17.evaluate(b, S, V)
    finally:
        e01.G["db"] = db44
    return {"key": key, "V": V, "mass_sum": r["mass_sum"] - S["n"] * (r["motor_kg"] - mkg), "pack": r["pack"]}


def run():
    import e01_coax_blade as e01, e18_body_incidence as e18, e19_ranking as e19
    with Pool(2) as pool:
        new = pool.map(opt, NEW)
    r38 = json.load(open(os.path.join(OUT, "e38_motor_survey.json")))["rows"]; r39 = json.load(open(os.path.join(OUT, "e39_torque_reserve.json")))["rows"]
    old = [dict(next(r for r in r38 if r["motor"] == "MN1123 KV53"), reserve=0.0), dict(next(r for r in r38 if r["motor"] == "V13828 55KV" and r["cap"] == 0.70), reserve=0.0),
           dict(next(r for r in r39 if r["layout"] == "hex" and r["cap"] == 0.65), reserve=0.12), dict(next(r for r in r39 if r["layout"] == "tri" and r["cap"] == 0.80), reserve=0.12)]
    des = old + new
    for d in des: d["key"] = f"{d['layout']} {d['reserve']:.2f}"
    e01.init()
    with Pool(2, initializer=e01.init) as pool:
        pts = pool.map(point, [(d["key"], "hex0" if d["layout"] == "hex" else "tri", d["blade"], d["motor_kg"], V) for d in des for V in e18.SPEEDS], chunksize=4)
    rows = lambda k, c: e19.rows({"cases": {f"{c}|x": {"rows": sorted((q for q in pts if q["key"] == k), key=lambda q: q["V"])}}}, c, "x")
    out = {"designs": [{k: d[k] for k in ("key", "layout", "reserve", "cap", "motor", "payload_cat", "Q_max", "fits", "rpm_hover", "rpm_max", "P_max", "solidity", "total_dba", "tonal_dba", "te_dba")} for d in des],
           "points": pts, "table": []}
    for res in (0.0, 0.05, 0.08, 0.12):
        h, t = f"hex {res:.2f}", f"tri {res:.2f}"; row = {"reserve": res}
        for eb in (e19.EB_CITED, e19.EB_CONS):
            for sp, v in (("15", 15.0), ("free", None)):
                th, tt = e19.best(rows(h, "hex0"), eb, v), e19.best(rows(t, "tri"), eb, v)
                row[f"{sp}_{eb:.0f}"] = tt["sum"] - th["sum"]
        row["dba_hex"] = next(d["total_dba"] for d in out["designs"] if d["key"] == h); row["dba_tri"] = next(d["total_dba"] for d in out["designs"] if d["key"] == t)
        out["table"].append(row); print("  reserve", row, flush=True)
    for d in out["designs"]: print("  design", {k: (round(v, 3) if isinstance(v, float) else v) for k, v in d.items()}, flush=True)
    save_json(os.path.join("explore", "e45_reserve_sweep.json"), out); print("  wrote results/explore/e45_reserve_sweep.json")


if __name__ == "__main__":
    run()

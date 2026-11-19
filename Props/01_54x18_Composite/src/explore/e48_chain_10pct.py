"""Exploration 48: entry 41's full chain on the 10 %-reserve designs, 24xx and 24xx-64 (queue item 57, 2026-11-18).

Entry 47 estimated the ranking with the -64 section by frame shifts (+-0.5 kg). Here the four 10 %-reserve designs
  hex MN1123 cap 0.65: 24xx (entry 46), 24xx-64 (entry 47);   tri V13828 cap 0.80: 24xx, 24xx-64 (entry 47)
go through the entry 17/18 vehicle model (constant body, 14-30 m/s) with their own polar sets and catalogue motor
masses, then entry 19's best-speed pick at 303.3 and 200 Wh/kg. Plain BEMT. 2 cores, nice 19 (toroid CFD running).
"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from multiprocessing import Pool
from common import RESULTS, save_json

OUT = os.path.join(RESULTS, "explore")
_DB = {}


def db(c, sec):
    import e24_chain_best_blades as e24, e35_mod4_laminar as e35
    from blade_trade_study import HybridDB
    if sec == "24xx": return e24.db_for(c, "best")
    if "t" not in _DB: _DB["t"], _DB["d44"] = e35.dbs("64")
    return _DB["t"] if c == "hex0" else HybridDB(_DB["t"], _DB["d44"])


def point(args):
    import e01_coax_blade as e01, e02_coax_two_point as e02, e17_blade_at_best_speed as e17, e18_body_incidence as e18
    key, c, sec, bd, mkg, V = args
    d0 = e01.G["db"]; e01.G["db"] = db(c, sec); e17.cruise = e18.make_cruise("constant")
    S = e17.setup(c); p = e01.G["p"]; Rr = p["rotor"]["diameter_in"] * p["constants"]["inch_to_m"] / 2
    b = e02.blade_from(bd, Rr, p["rotor"]["hub_radius_m"])
    try:
        r = e17.evaluate(b, S, V)
    finally:
        e01.G["db"] = d0
    return {"key": key, "V": V, "mass_sum": r["mass_sum"] - S["n"] * (r["motor_kg"] - mkg), "pack": r["pack"], "cruise_w": r["cruise"], "hover_w": r["hover"]}


def run():
    import e01_coax_blade as e01, e18_body_incidence as e18, e19_ranking as e19
    r46 = json.load(open(os.path.join(OUT, "e46_hex_noise_curve.json")))["rows"]; r47 = json.load(open(os.path.join(OUT, "e47_section_torque_bound.json")))["rows"]
    des = [("hex 24xx", "hex0", "24xx", next(r for r in r46 if r["motor"] == "MN1123 KV53" and r["cap"] == 0.65)),
           ("hex 24xx-64", "hex0", "24xx-64", next(r for r in r47 if r["layout"] == "hex")),
           ("tri 24xx", "tri", "24xx", next(r for r in r47 if r["layout"] == "tri" and r["section"] == "24xx")),
           ("tri 24xx-64", "tri", "24xx-64", next(r for r in r47 if r["layout"] == "tri" and r["section"] == "24xx-64"))]
    e01.init()
    with Pool(2, initializer=e01.init) as pool:
        pts = pool.map(point, [(k, c, s, d["blade"], d["motor_kg"], V) for k, c, s, d in des for V in e18.SPEEDS], chunksize=4)
    rows = lambda k, c: e19.rows({"cases": {f"{c}|x": {"rows": sorted((q for q in pts if q["key"] == k), key=lambda q: q["V"])}}}, c, "x")
    out = {"points": pts, "ranking": {}, "dba": {k: d["total_dba"] for k, _, _, d in des}}
    for sec in ("24xx", "24xx-64"):
        for eb in (e19.EB_CITED, e19.EB_CONS):
            for sp, v in (("15 m/s", 15.0), ("free", None)):
                h, t = e19.best(rows(f"hex {sec}", "hex0"), eb, v), e19.best(rows(f"tri {sec}", "tri"), eb, v)
                x = {"hex_minus_tri": t["sum"] - h["sum"], "sum_hex": h["sum"], "sum_tri": t["sum"], "pack_hex": h["pack"], "pack_tri": t["pack"], "hw_hex": h["hw"], "hw_tri": t["hw"], "V_hex": h["V"], "V_tri": t["V"]}
                out["ranking"][f"{sec} | {sp} | {eb:.0f}"] = x
                print(f"  {sec:8s} {sp:7s} {eb:5.0f} Wh/kg: hex - tri {x['hex_minus_tri']:+.2f} kg (hex {h['sum']:.2f} / tri {t['sum']:.2f}; pack {h['pack']:.0f}/{t['pack']:.0f}; hw {h['hw']:.2f}/{t['hw']:.2f}; V {h['V']:.1f}/{t['V']:.1f})", flush=True)
    save_json(os.path.join("explore", "e48_chain_10pct.json"), out); print("  wrote results/explore/e48_chain_10pct.json")


if __name__ == "__main__":
    run()

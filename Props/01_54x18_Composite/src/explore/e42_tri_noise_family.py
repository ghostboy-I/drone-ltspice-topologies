"""Exploration 42: the free-speed break-even noise limit (queue item 52, 2026-11-18).

Entry 41: at free speed with the 303 Wh/kg pack (constant body) the hex MN1123 (50.8 dBA) loses to the V13828 tri
(61.4 dBA) by 3.77 kg and to the U15XL tri (55.5 dBA) by 0.42 kg. Between and around those two points, build a tri
family, all with the 12 % torque reserve of entry 39:
  U15XL at caps 0.65 (entry 40), 0.70 (entry 40), 0.75, 0.80 (new optimisations here), V13828 at cap 0.80 (entry 39).
Each goes through entry 41's chain (entry 17/18 vehicle model, constant body, 14-30 m/s) and entry 19's best-speed
pick at 303.3 and 200 Wh/kg; the hex MN1123 points are reused from entry 41. The result is hex - tri payload against
the tri's hover dBA (BPM TE + rounded tip + Gutin tones at 50 m, 30 deg below the disk, entry 31's model), and the
noise limit at which they tie. 2 cores, nice 19 (toroid CFD running).
"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from multiprocessing import Pool
import e01_coax_blade as e01
import e02_coax_two_point as e02
import e17_blade_at_best_speed as e17
import e18_body_incidence as e18
import e19_ranking as e19
import e24_chain_best_blades as e24
import e37_catalogue_motor as e37
import e39_torque_reserve as e39
from common import RESULTS, save_json

OUT = os.path.join(RESULTS, "explore")
MKG = {"U15XL KV38": 4.408, "V13828 55KV": 2.465}


def opt(a):
    e37.CAT = e39.CAT
    return e37.job(a)


def point(args):
    name, bd, mkg, V = args
    db44 = e01.G["db"]; e01.G["db"] = e24.db_for("tri", "best"); e17.cruise = e18.make_cruise("constant")
    S = e17.setup("tri"); p = e01.G["p"]; Rr = p["rotor"]["diameter_in"] * p["constants"]["inch_to_m"] / 2
    b = e02.blade_from(bd, Rr, p["rotor"]["hub_radius_m"])
    try:
        r = e17.evaluate(b, S, V)
    finally:
        e01.G["db"] = db44
    return {"name": name, "V": V, "mass_sum": r["mass_sum"] - S["n"] * (r["motor_kg"] - mkg), "pack": r["pack"]}


def run():
    e01.init()
    with Pool(2) as pool:
        new = pool.map(opt, [("tri", 0.75, "U15XL KV38", "hard"), ("tri", 0.80, "U15XL KV38", "hard")])
    e39r = json.load(open(os.path.join(OUT, "e39_torque_reserve.json")))["rows"]; e40r = json.load(open(os.path.join(OUT, "e40_tri_u15xl_reserve.json")))["rows"]
    fam = [r for r in e40r] + new + [next(r for r in e39r if r["layout"] == "tri" and r["cap"] == 0.80)]
    for r in fam: r["name"] = f"{r['motor']} cap {r['cap']:.2f}"
    with Pool(2, initializer=e01.init) as pool:
        pts = pool.map(point, [(r["name"], r["blade"], MKG[r["motor"]], V) for r in fam for V in e18.SPEEDS], chunksize=4)
    e41 = json.load(open(os.path.join(OUT, "e41_scenarios_catalogue.json")))
    hx = [{"V": q["V"], "pack": q["pack"], "mass_sum": q["mass_sum"]} for q in e41["points"] if q["var"] == "hex" and q["model"] == "constant"]
    hx.sort(key=lambda q: q["V"]); out = {"family": [], "hex_dba": 50.8}
    for r in fam:
        rs = sorted((q for q in pts if q["name"] == r["name"]), key=lambda q: q["V"]); row = {k: r[k] for k in ("name", "motor", "cap", "payload_cat", "Q_max", "fits", "rpm_hover", "rpm_max", "P_max", "solidity", "te_dba", "tonal_dba", "total_dba")}
        for eb in (e19.EB_CITED, e19.EB_CONS):
            for sp, v in (("free", None), ("15 m/s", 15.0)):
                t = e19.best(e19.rows({"cases": {"tri|c": {"rows": rs}}}, "tri", "c"), eb, v); h = e19.best(e19.rows({"cases": {"hex0|c": {"rows": hx}}}, "hex0", "c"), eb, v)
                row[f"hex_minus_tri_{sp}_{eb:.0f}"] = t["sum"] - h["sum"]; row[f"V_tri_{sp}_{eb:.0f}"] = t["V"]; row[f"pack_tri_{sp}_{eb:.0f}"] = t["pack"]; row[f"hw_tri_{sp}_{eb:.0f}"] = t["hw"]
        out["family"].append(row)
        print(f"  {r['name']}: fits {r['fits']}, Q {r['Q_max']:.2f}, rpm {r['rpm_hover']:.0f}/{r['rpm_max']:.0f}, sigma {r['solidity']:.3f}, {r['total_dba']:.1f} dBA (TE {r['te_dba']:.1f}, tonal {r['tonal_dba']:.1f});"
              f" hex - tri free/303 {row['hex_minus_tri_free_303']:+.2f}, free/200 {row['hex_minus_tri_free_200']:+.2f}, 15/303 {row['hex_minus_tri_15 m/s_303']:+.2f} kg, V_tri {row['V_tri_free_303']:.1f}", flush=True)
    f = sorted((r for r in out["family"] if r["fits"]), key=lambda r: r["total_dba"])
    x = np.array([r["total_dba"] for r in f]); y = np.array([r["hex_minus_tri_free_303"] for r in f])
    i = np.where(np.diff(np.sign(y)))[0]
    out["breakeven_dba_free_303"] = float(np.interp(0, [y[i[0] + 1], y[i[0]]], [x[i[0] + 1], x[i[0]]])) if len(i) else None
    out["kg_per_db_fit"] = float(np.polyfit(x, y, 1)[0]) if len(f) > 1 else None
    print(f"  break-even tri noise (free, 303, constant body): {out['breakeven_dba_free_303']}; slope {out['kg_per_db_fit']} kg/dB", flush=True)
    save_json(os.path.join("explore", "e42_tri_noise_family.json"), out); print("  wrote results/explore/e42_tri_noise_family.json")


if __name__ == "__main__":
    run()

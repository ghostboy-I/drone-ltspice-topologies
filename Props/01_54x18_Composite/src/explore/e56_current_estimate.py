"""Exploration 56: one current-best estimate of hex - tri per decision scenario, combining entries 48-55 (2026-11-19).

Basis: entry 48's 10 %-reserve chain points (catalogue motors, constant body, hex with the entry 14 fairing at 0.35 kg/m2,
tri bare), for the 24xx and 24xx-64 sections at 14-30 m/s. Applied on top, each from its own entry:
  entry 50: usable specific energy per layout, e = e_nameplate x f_verify x f_age x f_usable(layout), with f_usable 0.9845
            (hex) and 0.9663 (tri) from the I R loss at mission current;
  entry 55: hex fairing skin 0.15 kg/m2 (-0.40 kg), and a t/c 0.5 tri fairing with 0.15 kg/m2 skin wherever it pays
            (the tri takes it or not per speed, whichever is lighter);
  speed:    '15' fixes 15 m/s; 'free' re-picks each layout's best speed for every pack state.
Pack states: semi-solid (303.3 Wh/kg nameplate) and LiPo (200), each new or end of life (0.80), as claimed (1.00).
Noise (entries 46-52, hover, 50 m): hex 50.3 dBA on the MN1123 (this chain's motor class), tri about 59.7-60.4 dBA on
the V13828 (entry 47-48); quieter options are listed for reference, not re-scored here.
"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e55_fairings_chain import tri_fairing
from common import RESULTS, save_json

OUT = os.path.join(RESULTS, "explore")
E0 = 303.3
FU = {"hex": json.load(open(os.path.join(OUT, "e50_pack_model.json")))["usable"]["hex"][0],
      "tri": json.load(open(os.path.join(OUT, "e50_pack_model.json")))["usable"]["tri"][0]}


def run():
    e9 = json.load(open(os.path.join(OUT, "e09_hex_vs_y6.json"))); e14 = json.load(open(os.path.join(OUT, "e14_faired_arms.json")))
    pts = json.load(open(os.path.join(OUT, "e48_chain_10pct.json")))["points"]; C = e14["configs"]["tri"]
    hex_area = e14["configs"]["hex0"]["rows"]["full t/c 0.5"]["fairing_kg"] / 0.35
    rows = []
    for sec in ("24xx", "24xx-64"):
        for chem, en in (("semi-solid", 303.3), ("LiPo", 200.0)):
            for age, fa in (("new", 1.0), ("end of life", 0.8)):
                for spd in ("15", "free"):
                    best = {}
                    for lay in ("hex", "tri"):
                        e = en * fa * FU[lay]
                        for q in (q for q in pts if q["key"] == f"{lay} {sec}" and (spd == "free" or q["V"] == 15.0)):
                            hw = q["mass_sum"] - q["pack"] / E0; opts = []
                            if lay == "hex": opts.append(("hex fairing 0.15", hw - 0.20 * hex_area, q["pack"]))
                            else:
                                opts.append(("tri bare", hw, q["pack"]))
                                dpk, area = tri_fairing(q["V"], q["hover_w"], e9, C); opts.append(("tri fairing 0.15", hw + 0.15 * area, q["pack"] + dpk))
                            for name, h, pk in opts:
                                m = h + pk / e
                                if lay not in best or m < best[lay]["mass"]: best[lay] = {"mass": m, "V": q["V"], "opt": name, "pack": pk, "hw": h, "e": e}
                    r = {"section": sec, "chemistry": chem, "age": age, "speed": spd, "hex_minus_tri": best["tri"]["mass"] - best["hex"]["mass"], "hex": best["hex"], "tri": best["tri"]}
                    rows.append(r)
                    print(f"  {sec:7s} {chem:10s} {age:11s} {spd:4s}: hex - tri {r['hex_minus_tri']:+.2f} kg (V {best['hex']['V']:.0f}/{best['tri']['V']:.0f},"
                          f" e {best['hex']['e']:.0f}/{best['tri']['e']:.0f} Wh/kg, tri {best['tri']['opt']})", flush=True)
    save_json(os.path.join("explore", "e56_current_estimate.json"), {"f_usable": FU, "rows": rows}); print("  wrote results/explore/e56_current_estimate.json")


if __name__ == "__main__":
    run()

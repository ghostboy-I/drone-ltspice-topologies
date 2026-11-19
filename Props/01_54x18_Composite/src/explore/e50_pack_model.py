"""Exploration 50: usable pack specific energy built up from the nameplate, and what it does to the layout ranking
(queue item 58, 2026-11-18). No new BEMT: the hex - tri curves of entry 49 (10 % reserve, constant body) are read at
the effective specific energy.

  e_eff = e_nameplate x f_verify x f_usable x f_age

  e_nameplate : semi-solid MAD 24S 55 Ah, 4884 Wh / 16.112 kg = 303.3 Wh/kg (reseller listing, data/catalog.yaml);
                conventional LiPo 200 Wh/kg (params 'conservative', already a pack-level assumption)
  f_verify    : nameplate vs measured capacity. 1.00 (as claimed) or 0.95 (a reseller figure that is 5 % optimistic)
  f_usable    : extra energy lost to the pack's internal resistance at the mission's currents beyond the loss already
                in the 1C rating, f = (1 - I R / V) / (1 - I_1C R / V), averaged over the mission by energy. Each layout
                gets its own: the tri draws more current per kg of pack, so it loses more (hex ~0.985, tri ~0.967)
For 15 m/s the mass sum is exact: m = hw + pack / e (entry 48 points, pack energy fixed by the mission). For the free
speed the best speed shifts with e, so the entry 49 curve is read at the mean e and corrected to first order for the
two layouts' different usable fractions, d(hex - tri) = pack_t (1/e_t - 1/e_m) - pack_h (1/e_h - 1/e_m).
  f_age       : capacity fade. 1.00 new, 0.90 mid-life, 0.80 end of life (the usual EOL definition)
The mission's own 20 % landing reserve (params) is kept on top, as before.
"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from common import RESULTS, save_json

OUT = os.path.join(RESULTS, "explore")
V_NOM, R_PACK = 24 * 3.7, 24 * 0.0012        # 24S nominal voltage; pack DC resistance from an assumed 1.2 mOhm per 55 Ah cell
I_1C = 55.0                                   # rating current (1C) at which the nameplate energy is quoted


def usable_fraction(p_hover, t_hover, p_cruise, t_cruise):
    f = lambda P: (1 - (P / V_NOM) * R_PACK / V_NOM) / (1 - I_1C * R_PACK / V_NOM)   # I R / V with I = P / V, relative to 1C
    e_h, e_c = p_hover * t_hover, p_cruise * t_cruise
    return (e_h * f(p_hover) + e_c * f(p_cruise)) / (e_h + e_c), f(p_hover), f(p_cruise)


def run():
    c = json.load(open(os.path.join(OUT, "e49_decision_curves.json"))); eb = np.array(c["e_b"])
    pts = json.load(open(os.path.join(OUT, "e48_chain_10pct.json")))["points"]
    hx = next(q for q in pts if q["key"] == "hex 24xx" and q["V"] == 15.0); tr = next(q for q in pts if q["key"] == "tri 24xx" and q["V"] == 15.0)
    print("  e48 points:", [(q["key"], q["V"], round(q["mass_sum"], 2), round(q["pack"])) for q in pts], flush=True)
    t_h, t_c = 204.0, 18520.0 / 15.0
    use = {k: usable_fraction(q["hover_w"], t_h, q["cruise_w"], t_c) for k, q in (("hex", hx), ("tri", tr))}
    print("  usable fraction (mission-energy weighted, hover, cruise):", {k: tuple(round(x, 4) for x in v) for k, v in use.items()}, flush=True)
    rows = []
    for chem, e0 in (("semi-solid", 303.3), ("LiPo", 200.0)):
        for fv in (1.00, 0.95):
            for age, fa in (("new", 1.00), ("mid-life", 0.90), ("end of life", 0.80)):
                eh, et = e0 * fv * fa * use["hex"][0], e0 * fv * fa * use["tri"][0]; em = 0.5 * (eh + et)
                r = {"chemistry": chem, "f_verify": fv, "age": age, "f_age": fa, "e_hex": eh, "e_tri": et}
                for mot in ("24xx", "24xx-64"):
                    h = [q for q in pts if q["key"] == f"hex {mot}" and q["V"] == 15.0][0]; t = [q for q in pts if q["key"] == f"tri {mot}" and q["V"] == 15.0][0]
                    hw_h, hw_t = h["mass_sum"] - h["pack"] / 303.3, t["mass_sum"] - t["pack"] / 303.3
                    r[f"{mot} | 15 m/s"] = (hw_t + t["pack"] / et) - (hw_h + h["pack"] / eh)
                    hf = [q for q in pts if q["key"] == f"hex {mot}" and q["V"] != 15.0]; tf = [q for q in pts if q["key"] == f"tri {mot}" and q["V"] != 15.0]
                    ph = min(hf, key=lambda q: abs(q["pack"] / (q["mass_sum"] - hw_h) - em))["pack"]; ptr = min(tf, key=lambda q: abs(q["pack"] / (q["mass_sum"] - hw_t) - em))["pack"]
                    base = float(np.interp(em, eb, c["curves"][f"{mot} | free"]["hex_minus_tri"]))
                    r[f"{mot} | free"] = base + ptr * (1 / et - 1 / em) - ph * (1 / eh - 1 / em)
                rows.append(r)
                print(f"  {chem:10s} verify {fv:.2f} {age:11s}: e hex {eh:5.1f} / tri {et:5.1f} Wh/kg -> hex - tri 15 m/s {r['24xx | 15 m/s']:+.2f} (24xx) / {r['24xx-64 | 15 m/s']:+.2f} (-64);"
                      f" free {r['24xx | free']:+.2f} / {r['24xx-64 | free']:+.2f} kg", flush=True)
    save_json(os.path.join("explore", "e50_pack_model.json"), {"V_nom": V_NOM, "R_pack": R_PACK, "I_1C": I_1C, "usable": use, "rows": rows,
                                                             "breakeven": {k: v["breakeven_wh_kg"] for k, v in c["curves"].items()}})
    print("  wrote results/explore/e50_pack_model.json")


if __name__ == "__main__":
    run()

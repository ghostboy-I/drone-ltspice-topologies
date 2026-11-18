"""Hand checks for exploration 05: three estimates of the arm's induced power against BEMT, as ratios to equal diameters.

1. Disk area only (no interference): each rotor carries T/2 with ideal power (T/2)^1.5 / sqrt(2 rho A), so
     P / P_ref = (1/sqrt(A_u) + 1/sqrt(A_l)) / (2/sqrt(A_0)) = (D_0/D_u + D_0/D_l) / 2
2. Momentum with interference (hand() in e05_diameter_split.py): BEMT thrust split, wake velocity w and edge r_w, uniform own inflow per disk.
3. BEMT induced power, sum dT (v + v_i), from the full model.
"""
import json, os
here = os.path.dirname(os.path.abspath(__file__))
o = json.load(open(os.path.join(here, "..", "..", "results", "explore", "e05_diameter_split.json")))
rows = [r for r in o["rows"] if "error" not in r]
ref = next(r for r in rows if r["mode"] == "lower" and r["s"] == 1.0)
out = []
print(f"  {'mode':9s} {'s':>5s} {'D_u':>5s} {'D_l':>5s} | {'area only':>9s} {'momentum':>9s} {'BEMT ind':>9s} | {'pack':>7s}")
for r in rows:
    area = (54 / r["D_upper_in"] + 54 / r["D_lower_in"]) / 2
    q = {"mode": r["mode"], "s": r["s"], "D_upper_in": r["D_upper_in"], "D_lower_in": r["D_lower_in"], "area_only": area,
         "momentum": r["P_ind_hand_arm"] / ref["P_ind_hand_arm"], "bemt_induced": r["P_ind_bemt_arm"] / ref["P_ind_bemt_arm"],
         "pack_ratio": r["pack_wh"] / ref["pack_wh"]}
    out.append(q)
    print(f"  {q['mode']:9s} {q['s']:5.2f} {q['D_upper_in']:5.1f} {q['D_lower_in']:5.1f} | {area:9.3f} {q['momentum']:9.3f} {q['bemt_induced']:9.3f} | {q['pack_ratio']:7.3f}")
json.dump(out, open(os.path.join(here, "..", "..", "results", "explore", "e05_hand_check.json"), "w"), indent=1)

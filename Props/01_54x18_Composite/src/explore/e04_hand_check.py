"""Hand check for exploration 04: velocity triangles of the upper and lower blades at 0.5 R (identical blades, h = 0.2 D).

Both blades have the same twist, so alpha_lower - alpha_upper = -(phi_lower - phi_upper), with phi = atan(inflow / (Omega r)).
Inflows from the vortex-cylinder model (mean values, uniform loading):
  upper: v_u + (1 - k) v_l      lower (inside the upper wake): v_l + w,  w = (1 + k) v_u,  k = h / sqrt(R^2 + h^2)
The equal-torque trim sets each rotor's Omega, and the lower rotor spins faster, which offsets part of the wake inflow.
The fixed-Omega estimate in e04 (d_phi = 6.2 deg) leaves that trim out, so it overstates the twist the lower blade needs.
"""
import json, math, os
here = os.path.dirname(os.path.abspath(__file__))
o = json.load(open(os.path.join(here, "..", "..", "results", "explore", "e04_upper_lower_blades.json")))
ref = next(q for q in o["rows"] if q.get("d0") == 0 and q.get("d_in") == 0)
R = 0.6858; h = o["h_over_D"] * 2 * R; k = h / math.sqrt(R * R + h * h)
w = ref["w"]; v_u = w / (1 + k)
i = min(range(len(ref["r"])), key=lambda j: abs(ref["r"][j] / R - 0.5)); r = ref["r"][i]
v_l = ref["vi_lower"][i]
om_u, om_l = (ref[f"rpm_{s}"] * 2 * math.pi / 60 for s in ("upper", "lower"))
phi_u = math.degrees(math.atan((v_u + (1 - k) * v_l) / (om_u * r)))
phi_l = math.degrees(math.atan((v_l + w) / (om_l * r)))
phi_l_fixed = math.degrees(math.atan((v_l + w) / (om_u * r)))
out = {"r_over_R": r / R, "k": k, "v_upper": v_u, "w": w, "v_lower": v_l, "rpm_upper": ref["rpm_upper"], "rpm_lower": ref["rpm_lower"],
       "phi_upper_deg": phi_u, "phi_lower_deg": phi_l, "phi_lower_if_same_rpm_deg": phi_l_fixed,
       "hand_alpha_diff_deg": -(phi_l - phi_u), "bemt_alpha_diff_deg": ref["alpha_lower_deg"][i] - ref["alpha_upper_deg"][i],
       "rpm_share_of_correction": (phi_l_fixed - phi_l) / (phi_l_fixed - phi_u)}
for kk, v in out.items(): print(f"  {kk}: {v:.3f}")
json.dump(out, open(os.path.join(here, "..", "..", "results", "explore", "e04_hand_check.json"), "w"), indent=1)

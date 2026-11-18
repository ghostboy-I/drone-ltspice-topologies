"""Hand checks for exploration 07.

1. Inflow gradient on the rotor's own disk (skewed vortex cylinder, chi = wake skew):
   Coleman et al.: slope at the hub along the fore-aft diameter, K_x = tan(chi / 2)
   Pitt-Peters: least-squares over the whole disk, K_x = (15 pi / 32) tan(chi / 2)
   (the exact field is not linear: it steepens toward the trailing edge, which is why the two differ)
2. Prandtl's biplane factor. In cruise each rotor acts like a lifting wing of span b = 2R, with induced power
   P_i = T^2 / (2 rho A V') (Glauert), the same as an elliptic wing's L^2 / (pi q b^2) x V. Two wings a gap G apart:
       P = (T_u^2 + 2 sigma T_u T_l + T_l^2) / (2 rho A V'),   sigma = (1 - 0.66 G/b) / (1.055 + 3.7 G/b)
   so with equal thrusts the mutual (interference) power per arm is 2 sigma P_i(one rotor). The vortex-wake equivalent is
   sigma_bs = (mean w on lower + mean w on upper) / (2 v_i0).
"""
import json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import e07_cruise_wake as e7

o = json.load(open(os.path.join(e7.OUT, "e07_cruise_wake.json")))
chi = math.radians(o["chi_deg"]); R = e7.R
a, b, g = e7.rings(chi)
xs = np.linspace(-0.3, 0.3, 7) * R          # fore-aft diameter near the hub, x aft
pts = np.stack([xs, np.zeros_like(xs), np.full_like(xs, -1e-4 * R)], 1)
w = e7.down(e7.biot_savart(a, b, g, pts)); w0 = w[3]
kx_hub = float(np.polyfit(xs / R, w / w0, 1)[0])
res = {"chi_deg": o["chi_deg"], "Kx_hub_slope_bs": kx_hub, "Kx_coleman": math.tan(chi / 2),
       "Kx_full_disk_fit_bs": o["checks"]["coleman"]["Kx_fit"], "Kx_pitt_peters": 15 * math.pi / 32 * math.tan(chi / 2), "biplane": []}
print(f"  K_x: hub slope {kx_hub:.3f} vs Coleman tan(chi/2) {res['Kx_coleman']:.3f};  full-disk fit {res['Kx_full_disk_fit_bs']:.3f} vs Pitt-Peters {res['Kx_pitt_peters']:.3f}")
for r in o["rows"]:
    gb = r["h_over_D"]                       # G / b = h / (2R) = h / D
    sp = (1 - 0.66 * gb) / (1.055 + 3.7 * gb)
    sb = (r["mean_w_lower_over_vi0"] + r["mean_w_upper_over_vi0"]) / 2
    res["biplane"].append({"G_over_b": gb, "sigma_prandtl": sp, "sigma_vortex_wake": sb, "sigma_lens_equiv": r["f_lens"]})
    print(f"  G/b {gb:.2f}: sigma Prandtl {sp:.3f}, vortex wake {sb:.3f}, lens-model equivalent {r['f_lens']:.3f}")
json.dump(res, open(os.path.join(e7.OUT, "e07_hand_check.json"), "w"), indent=1)

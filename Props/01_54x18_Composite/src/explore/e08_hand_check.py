"""Hand check for exploration 08: stagger seen from the Trefftz plane (Munk's stagger theorem, generalised).

Munk (1923): the total induced drag of a system of lifting surfaces with fixed loads does not change when the surfaces are
moved along the direction their wakes trail in. Only their positions in the Trefftz plane (a plane far downstream, normal
to the wake) matter. Here the wakes trail along e = (sin chi, 0, -cos chi), not along the flight path, so moving the lower
rotor forward by s also moves it sideways in the Trefftz plane. The unit normal to e in the x-z plane is n = (cos chi, 0, sin chi);
the lower hub sits at (-s, 0, -h), so its Trefftz-plane distance from the upper is
    G_eff = |(-s, 0, -h) . n| = |s cos chi + h sin chi|
With chi = 68 deg: sin chi = 0.93, cos chi = 0.37. Forward stagger is only 37 % as effective as extra mast height, and aft
stagger (s < 0) moves the lower rotor back toward the upper wake (G_eff -> 0 at s = -h tan chi = -2.5 h).
Prediction: sigma(s) = Prandtl sigma(G_eff / b), b = 2R. Compared with the vortex-wake sigma from e08_stagger.py.
"""
import json, math, os
here = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(here, "..", "..", "results", "explore")
o = json.load(open(os.path.join(OUT, "e08_stagger.json"))); R = 0.6858
prandtl = lambda g: (1 - 0.66 * g) / (1.055 + 3.7 * g)
res = {"curves": [], "rows": []}
for hd in sorted({r["h_over_D"] for r in o["rows"]}):
    rr = sorted([r for r in o["rows"] if r["h_over_D"] == hd], key=lambda r: r["s_over_R"])
    chi = math.radians(rr[0]["chi_deg"]); h = hd * 2 * R
    cur = {"h_over_D": hd, "s_over_R": [], "G_eff_over_b": [], "sigma_prandtl_Geff": [], "sigma_bs": []}
    for r in rr:
        g = abs(r["s_over_R"] * R * math.cos(chi) + h * math.sin(chi)) / (2 * R)
        cur["s_over_R"].append(r["s_over_R"]); cur["G_eff_over_b"].append(g); cur["sigma_prandtl_Geff"].append(prandtl(g)); cur["sigma_bs"].append(r["sigma_bs"])
        res["rows"].append({"h_over_D": hd, "s_over_R": r["s_over_R"], "G_eff_over_b": g, "sigma_prandtl": prandtl(g), "sigma_bs": r["sigma_bs"]})
        print(f"  h/D {hd:.1f} s/R {r['s_over_R']:+.2f}: G_eff/b {g:.3f}, sigma Prandtl {prandtl(g):.3f}, vortex wake {r['sigma_bs']:.3f}")
    res["curves"].append(cur)
# what stagger buys compared with height: d(G_eff)/ds = cos chi, d(G_eff)/dh = sin chi
c = math.radians(o["rows"][0]["chi_deg"]); res["dG_ds"] = math.cos(c); res["dG_dh"] = math.sin(c)
print(f"  dG_eff/ds = cos chi = {math.cos(c):.3f}, dG_eff/dh = sin chi = {math.sin(c):.3f}")
json.dump(res, open(os.path.join(OUT, "e08_hand_check.json"), "w"), indent=1)

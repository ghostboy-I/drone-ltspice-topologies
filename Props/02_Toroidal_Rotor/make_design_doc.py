"""Builds 02_Toroidal_Rotor_Design.pdf from results/*.json and the figures. No number here is typed in: everything comes
from the result files written by src/toroid.py. Before the CFD run exists, the CFD column says so."""
import json, math, os, sys
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, "..", "..", "Topologies", "tools"))
from designdoc import Doc
import yaml

R_ = os.path.join(here, "results")
J = lambda n: json.load(open(os.path.join(R_, n))) if os.path.exists(os.path.join(R_, n)) else None
S, G, C, M, CFD = J("sizing.json"), J("geometry.json"), J("case_toroid.json"), J("mesh_toroid.json"), J("cfd_toroid.json")
CFDREF = J("cfd_reference.json")
P = yaml.safe_load(open(os.path.join(here, "params.yaml")))
PH1 = json.load(open(os.path.join(here, "..", "01_54x18_Composite", "results", "phase1.json")))
I = S["inputs"]; B = S["bemt"]; air = I["air"]; g = P["rotor"]
f0 = lambda x: f"{x:,.0f}"; f1 = lambda x: f"{x:.1f}"; f2 = lambda x: f"{x:.2f}"; f3 = lambda x: f"{x:.3f}"
pct = lambda a, b: f"{100 * (b - a) / a:+.1f} %"
LB = 0.45359237

doc = Doc("Prop 02: Toroidal (Closed-Loop) Rotor",
          "280 lb tricopter  |  T/W 1.5 per rotor on the hot day  |  54 in, 2 loops / 4 legs  |  preliminary sizing and OpenFOAM case")

# ------------------------------------------------------------------------------------------------------------------
doc.h("1. What was asked, and what it implies")
doc.p(f"A toroidal rotor that lets the {P['vehicle']['mtow_lb']:.0f} lb vehicle ({P['vehicle']['drone_max_lb']:.0f} lb drone + "
      f"{P['vehicle']['payload_lb']:.0f} lb payload = {I['sum_check_lb']:.0f} lb) reach a thrust-to-weight ratio of "
      f"{P['vehicle']['tw_required']}:1. The vehicle is the prop program's tricopter, so each of the {I['n_rotors']} rotors must make "
      f"T/W x W / 3 at full throttle, in the program's design air (45 C at sea level).")
doc.table(["Quantity", "Value", "How"], [
    ["Weight W", f"{f0(I['W_n'])} N  ({I['mtow_kg']:.1f} kg)", "280 lb x 0.4536 x g"],
    ["Hover thrust per rotor", f"{f1(I['T_hover'])} N", "W / 3"],
    ["T/W 1.5 thrust per rotor (the requirement)", f"{f1(I['T_required'])} N", "1.5 W / 3"],
    ["Air density / kinematic viscosity, 45 C", f"{air['rho']:.4f} kg/m^3 / {air['nu']:.3e} m^2/s", "ISA pressure, hot air"],
    ["Disk area (54 in) / disk loading in hover", f"{I['A']:.4f} m^2 / {f0(I['disk_loading'])} N/m^2", "pi R^2"],
    ["Motor speed available (U15XL KV38, 84 V sag)", f"{f0(I['rpm_available_sag'])} rpm", "k_load KV V"],
    ["Tip-Mach 0.60 speed limit", f"{f0(I['rpm_mach_limit'])} rpm", "Props/01 requirement"],
], widths=[0.45, 0.33, 0.22])
mb = PH1["mass_budget"]["cases"]["required_tw1.5/cited_303"]
blades = 3 * P["mass"]["reference_blade_set_kg"]
doc.p(f"The weight split does not close, and no propeller can close it. Phase 1 of the prop program found that the drone's hardware "
      f"without any battery already weighs {mb['non_battery']:.1f} kg (motors {mb['motors']:.1f}, frame {mb['frame']:.1f}, props "
      f"{mb['props']:.1f}, ESCs {mb['escs']:.1f}, avionics {mb['avionics_wiring']:.1f}) against a {I['drone_max_kg']:.1f} kg limit, and the "
      f"mission battery adds {mb['battery']:.0f} kg or more. All three blade sets together are about {blades:.1f} kg. The toroidal rotor "
      "is therefore judged on what it does to the whole chain: blade mass, the power it needs (which sets battery and motor mass), "
      "and whether one motor can still turn it. That is what the decision matrix after the CFD run will weigh, with mass first.")

# ------------------------------------------------------------------------------------------------------------------
doc.h("2. What a toroidal rotor is")
doc.img(os.path.join(R_, "fig_geometry.png"), width=6.6)
doc.bullets([
    "Each blade is a closed loop. A leading leg runs out from the hub, turns through the tip and comes back as a trailing leg, "
    "so there is no free tip. Two loops make four legs, balanced like a 2-blade rotor.",
    "Seen from above each loop is a petal: the legs are up to "
    f"{1000 * g['sweep_max_m']:.0f} mm apart tangentially at mid-span and close to {1000 * g['sweep_end_m']:.0f} mm at both turns. "
    f"Seen along the radius the legs are stacked {1000 * g['gap_m']:.0f} mm apart, the trailing leg high.",
    "Why the trailing leg is high: the leading leg's wake descends at the inflow angle phi, so a following leg at height +h passes "
    "h + s tan(phi) above it, while one at -h would pass only h - s tan(phi) away.",
    "What it might buy: no concentrated tip vortex (the vorticity leaves along the whole tip turn), lower tip loss, a quieter tip, and "
    "a closed frame instead of two cantilevers. What it costs: the extra wetted area of the turns, the interference of two legs "
    "working one chord apart (a biplane), and two hub joints per loop.",
])

# ------------------------------------------------------------------------------------------------------------------
doc.h("3. Momentum theory: what any 54 in rotor needs")
doc.p("An actuator disk that accelerates the air through area A gives the induced velocity and the ideal (lossless) power. The real "
      "shaft power is larger by the figure of merit FoM. None of this depends on the blade shape, which is why the toroid keeps the "
      "54 in disk: the comparison with the 2-blade reference is then about the loop alone.")
doc.eq(r"v_i=\sqrt{\frac{T}{2\rho A}},\qquad P_{ideal}=T\,v_i=\frac{T^{3/2}}{\sqrt{2\rho A}},\qquad FoM=\frac{P_{ideal}}{P_{shaft}}")
mo = S["momentum"]
doc.table(["Point", "Thrust [N]", "v_i [m/s]", "P_ideal [W]", "Disk flow v_i A [m^3/s]"], [
    ["Hover", f1(mo["hover"]["T"]), f2(mo["hover"]["vi"]), f0(mo["hover"]["P_ideal"]), f2(mo["hover"]["disk_flow_m3s"])],
    ["T/W 1.5", f1(mo["tw_required"]["T"]), f2(mo["tw_required"]["vi"]), f0(mo["tw_required"]["P_ideal"]), f2(mo["tw_required"]["disk_flow_m3s"])],
    ["T/W 2.0", f1(mo["tw_target"]["T"]), f2(mo["tw_target"]["vi"]), f0(mo["tw_target"]["P_ideal"]), f2(mo["tw_target"]["disk_flow_m3s"])],
], widths=[0.2, 0.18, 0.18, 0.2, 0.24])

doc.h("4. Blade loading, solidity and tip loss")
doc.p("The thrust coefficient (helicopter convention) and the solidity set the mean lift coefficient the sections must work at. "
      "Giving each leg half the reference chord keeps the solidity, hence the blade loading, the same as the 2-blade rotor:")
doc.eq(r"C_T=\frac{T}{\rho A(\Omega R)^2},\qquad \sigma=\frac{N\,\bar c}{\pi R},\qquad \bar c_l\approx\frac{6\,C_T}{\sigma}")
ref15 = B["reference"]["tw_required"]; leg15 = B["legs_tip_loss"]["tw_required"]
doc.p(f"Solidity: reference {f3(S['solidity']['reference'])}, loop legs {f3(S['solidity']['legs'])}. At T/W 1.5 the reference runs at "
      f"C_T = {ref15['CT_h']:.4f}, so 6 C_T / sigma = {6 * ref15['CT_h'] / S['solidity']['reference']:.2f}; the blade-element mean "
      f"lift coefficient is {ref15['mean_cl']:.2f}, inside the NACA 44xx's useful range.")
tl = S["tip_loss_hand"]
doc.p("Prandtl's tip loss shrinks the working disk to an effective radius BR. More, narrower blades lose less; a closed loop has no free "
      "tip at all, so 'no tip loss' is its upper bound and '4 open legs' its lower bound:")
doc.eq(r"B\approx1-\frac{\sqrt{2C_T}}{N},\qquad P_i\propto\frac{1}{B}")
doc.p(f"With C_T = {tl['CT_h']:.4f}: B = {tl['B_2']:.3f} for 2 blades and {tl['B_4']:.3f} for 4 legs, so 4 legs should need "
      f"{tl['induced_power_cut_2_to_4_pct']:.1f} % less induced power before any loop effect.")

# ------------------------------------------------------------------------------------------------------------------
doc.h("5. Blade-element estimate (the hand calculation the CFD is checked against)")
doc.p("The prop program's blade-element momentum (BEMT) solver and XFOIL polars, run on the reference blade and on the loop's legs "
      "treated as an open 4-bladed rotor (each leg a blade, the turn replaced by the leg running on to R). The motor current is "
      "I = Q / k_t with the U15XL's k_t; its 120 s peak rating is "
      f"{I['i_peak']} A.")
rows = []
for k, nm in (("reference", "2-blade reference"), ("legs_tip_loss", "4 legs, tip loss"), ("legs_no_tip_loss", "4 legs, closed tip")):
    a, h_ = B[k]["tw_required"], B[k]["hover"]
    rows.append([nm, f0(a["rpm"]), f1(a["Q"]), f2(a["P"] / 1000), f3(a["FoM"]), f0(a["motor_current_a"]), f2(h_["P"] / 1000), f2(B[k]["at_motor_rpm"]["tw"])])
doc.table(["At T/W 1.5", "rpm", "Q [N m]", "P [kW]", "FoM", "Amps", "Hover [kW]", "T/W max"], rows,
          widths=[0.26, 0.09, 0.11, 0.1, 0.09, 0.09, 0.13, 0.13])
doc.p("'T/W max' is the thrust at the motor's full speed on a sagged pack, over the hover thrust. 'Closed tip' switches the tip-loss "
      "factor off: the ideal a loop could approach.")
doc.p(f"All three reach T/W 1.5 below the motor's {f0(I['rpm_available_sag'])} rpm and inside the 180 A rating. The legs need "
      f"{pct(ref15['rpm'], leg15['rpm'])} rpm against the reference (lower tip loss) but slightly more torque. The CFD case runs at "
      f"{S['cfd_rpm']} rpm, the open-leg BEMT speed for T/W 1.5 rounded to 10 rpm. Caution carried from the prop program: on the "
      "Caradonna-Tung validation rotor this BEMT over-predicted thrust by about 31 %, so these numbers are a cross-check, not the answer.")

# ------------------------------------------------------------------------------------------------------------------
doc.h("6. Geometry: how the loop is built")
doc.p("Each loop is one closed tube of airfoil sections swept along a closed centre-line in the rotating frame (r, psi, z). With "
      "xi = (r - r0)/(rt - r0) along a leg and u in (0, 1) through a turn:")
doc.eq(r"s(r)=s_{end}+(s_{max}-s_{end})\sin^2(\pi\xi),\qquad \psi_{A,B}=\pm\frac{s}{2r},\qquad z_{A,B}=\mp\frac{h}{2}")
doc.eq(r"\mathrm{turns:}\quad r=r_t+a\sin(\pi u),\qquad q=-\cos(\pi u),\qquad \psi=-\frac{q\,s_{end}}{2r},\qquad z=\frac{q\,h}{2}")
doc.p("Sections lie in the plane normal to the path tangent t. The chord points along the projection of the rotation direction "
      "e_psi on that plane, pitched by theta_p about t:")
doc.eq(r"c_0=\frac{e_\psi-(e_\psi\cdot t)\,t}{|\cdot|},\qquad e_c=c_0\cos\theta_p+(t\times c_0)\sin\theta_p,\qquad e_n=t\times e_c")
doc.p("On the outgoing leg theta_p = +theta(r); on the returning leg t is reversed, so theta_p = -theta(r) gives the same nose-up pitch. "
      "Through each turn theta_p and the camber go as cos(pi u), through zero mid-turn. That makes the turn's circulation "
      "antisymmetric, Prandtl's box-wing tip loading. The leg pitch is the reference blade's twist at the same radius; t/c runs "
      f"{100 * g['tc'][0]:.0f} % at the root to {100 * g['tc'][-1]:.0f} % outboard (thicker than the reference: a deeper spar per kg).")
st = G["stl"]; fc = G["fold_check"]; gp = G["gaps"]
mid = min(gp, key=lambda x: abs(x["r"] - 0.75 * G["R"]))
mi = (M or {})
doc.table(["Check", "Result", "Expect"], [
    ["Open / mis-oriented edges", f"{st['edges_not_shared_by_two']} / {st['edges_inconsistent']} ({st['triangles']:,} triangles)", "0 / 0"],
    ["Self-intersection (surfaceCheck)", ("none" if mi.get("surface_self_intersecting") is False and mi.get("self_intersection_checked") else
                                          ("not run yet" if not mi else f"{mi.get('surface_self_intersections')} locations")), "none"],
    ["Sections never cross (min. advance ratio)", f"{fc['min_advance_ratio']:.2f} (segment {fc['segment']})", "> 0"],
    ["Volume: STL vs. sections x path", f"{1e6 * st['volume_m3']:.0f} cm^3, {G['volume_diff_pct']:+.2f} %", "< 1 %"],
    ["Wetted area: STL vs. sections x path", f"{st['area_m2']:.4f} m^2, {G['area_diff_pct']:+.2f} %", "< 1 %"],
    ["Leg gap / stagger at 0.75 R", f"{1000 * mid['gap_normal_to_chord_m']:.0f} / {1000 * mid['stagger_along_chord_m']:.0f} mm, "
     f"chord {1000 * mid['chord_m']:.0f} mm", "gap ~ 1 chord"],
    ["Radial / axial extent", f"{G['r_extent_m'][0]:.3f} - {G['r_extent_m'][1]:.4f} m / {1000 * G['z_extent_m'][0]:.0f} to {1000 * G['z_extent_m'][1]:.0f} mm", "r <= R + t/2"],
], widths=[0.4, 0.44, 0.16])
doc.p(f"The volume and area checks integrate the section shapes along the centre-line independently of the triangulation. The tip turn "
      f"reaches {1000 * (G['r_extent_m'][1] - G['R']):.1f} mm past R (half the section thickness at the apex), a {100 * (G['r_extent_m'][1] / G['R'] - 1):.1f} % "
      "larger radius than the reference. A first build did self-intersect: the legs' stations were packed 0.4 mm apart at the root "
      "while the root turn stepped 4 mm, so the section frame swung faster than the stations advanced and the 39 mm trailing edge "
      "crossed itself. Matching the station spacing across the joints fixed it; the 'min advance ratio' check now guards against it.")

# ------------------------------------------------------------------------------------------------------------------
doc.h("7. Mass: what can be said before a structural design")
ms = G["mass"]
doc.p("The structure is not designed yet, so the blade-set mass is bracketed two ways from the reference blade set "
      f"({ms['reference_kg']:.2f} kg vendor-scaled, {ms['reference_volume_cm3']:.0f} cm^3, {ms['reference_area_m2']:.3f} m^2 wetted):")
doc.table(["Scaling", "Toroid", "vs. reference", "When it holds"], [
    ["By solid volume", f"{ms['volume_scaled_kg']:.2f} kg ({ms['toroid_volume_cm3']:.0f} cm^3)", pct(ms["reference_kg"], ms["volume_scaled_kg"]), "foam-cored, core-dominated blades"],
    ["By wetted area", f"{ms['area_scaled_kg']:.2f} kg ({ms['toroid_area_m2']:.3f} m^2)", pct(ms["reference_kg"], ms["area_scaled_kg"]), "thin carbon skins at minimum gauge"],
], widths=[0.2, 0.3, 0.15, 0.35])
sa = G["area_by_segment_m2"]
doc.p(f"Half-chord legs have a quarter of the section area each, so two of them hold half the volume, but the same skin area; the turns "
      f"add {sa['tip turn'] + sa['root turn']:.3f} m^2 ({100 * (sa['tip turn'] + sa['root turn']) / ms['toroid_area_m2']:.0f} % of the wetted area). "
      "The loop's structural gain is the closed frame: with the tip turn tying the two legs, the tip rotation is restrained "
      "by the legs' axial stiffness, and a leg moves from a cantilever toward a fixed-guided beam:")
doc.eq(r"\delta_{cantilever}=\frac{wL^4}{8EI}\ \rightarrow\ \delta_{fixed-guided}=\frac{wL^4}{24EI},\qquad M_{root}=\frac{wL^2}{2}\ \rightarrow\ \frac{wL^2}{3}")
doc.p("Up to three times stiffer and a third less root bending per leg, but each half-chord leg has about one eighth of the full "
      "blade's bending stiffness, so the loop as a whole lands near the reference for the same skin. On a whole-vehicle scale "
      f"the blade sets are about {blades:.1f} kg of {I['mtow_kg']:.0f} kg: the rotor's power, through battery and motor mass, matters more "
      "than its own weight. That trade is for the matrix.")

# ------------------------------------------------------------------------------------------------------------------
doc.h("8. CFD case")
mm = P["cfd"]["meshes"]["prelim"]
doc.bullets([
    f"OpenFOAM 13, foamRun with incompressibleFluid, steady SIMPLE, k-omega SST with wall functions (Spalding). Frozen rotor: a "
    f"multiple reference frame turns at {S['cfd_rpm']} rpm inside a cylinder of radius {C['mrf_radius']:.3f} m and height +/-{C['mrf_half_height']:.3f} m; "
    "the rest of the domain is stationary. The same recipe as the prop program's Caradonna-Tung validation case.",
    f"Domain: cylinder of radius {C['radius']:.2f} m (5 D), {-C['z0']:.2f} m below and {C['z1']:.2f} m above the rotor (10 D / 5 D). "
    "Top and side: total pressure (open, entrainment). Bottom: fixed static pressure, inlet-outlet velocity.",
    f"Mesh: blockMesh O-grid with {C['base_cell']} m core cells, snappyHexMesh to {C['surface_cell_mm']:.2f} mm on the blades, refined by surface "
    f"curvature (resolveFeatureAngle {mm['resolve_feature_angle']} deg) to {C['curvature_cell_mm']:.2f} mm round the leading edges, "
    f"{C['edge_cell_mm']:.2f} mm on the sharp trailing edges, {C['disk_cell_mm']:.0f} mm in the disk and coarser down the wake; "
    f"{mm['n_layers']} prism layers sized relative to the local cell.",
    f"Leading-edge resolution was the lesson of the validation case: there, 3.1 mm cells across a 3.0 mm nose radius lost the suction "
    f"peak and over-predicted torque by about 20 N m. Here the nose radius is {G['nose_radius_mm_at_075R']:.2f} mm at 0.75 R and "
    f"{G['nose_radius_mm_at_tip_turn']:.2f} mm in the tip turn, so {C['curvature_cell_mm']:.2f} mm cells give "
    f"{G['nose_radius_mm_at_075R'] / C['curvature_cell_mm']:.1f} and {G['nose_radius_mm_at_tip_turn'] / C['curvature_cell_mm']:.1f} cells per nose radius.",
    "A guard stops the run if the thrust coefficient leaves (0, 3 x the T/W 1.5 value) or the outlet flow exceeds 10 x 2 v_i A for 50 "
    "iterations after the first 150: the runaway the validation case once had.",
])
if M:
    rows = [["Cells", f"{M['cells']:,.0f}" if M.get("cells") else "-"], ["Mesh OK (checkMesh)", str(M.get("mesh_ok"))],
            ["Max non-orthogonality / skewness / aspect ratio", f"{M.get('max_non_orthogonality')} / {M.get('max_skewness')} / {M.get('max_aspect_ratio')}"]]
    if M.get("layer_coverage_pct") is not None:
        rows.append(["Prism-layer coverage / mean layers", f"{M['layer_coverage_pct']:.0f} % / {M['layers_mean']:.2f}"])
    rows.append(["Meshing wall time", f"{M['wall_s'] / 60:.0f} min on {M['n_mesh']} processes"])
    doc.table(["Mesh", "Value"], rows, widths=[0.5, 0.5])
    if M.get("failed_checks"):
        doc.p("checkMesh flags: " + "; ".join(M["failed_checks"]))

# ------------------------------------------------------------------------------------------------------------------
doc.h("9. Hand calculation vs. CFD")
hp = S["cfd_point_bemt"]
if CFD:
    rows = []
    for row in CFD["vs_hand"]:
        c_ = row["cfd"]; lo, hi = row["legs_tip_loss"], row["legs_no_tip_loss"]
        fmt = f3 if "merit" in row["quantity"] else f1
        rows.append([row["quantity"], fmt(lo), fmt(hi), fmt(c_), pct(lo, c_), fmt(row["reference"])])
    doc.table(["At " + str(S["cfd_rpm"]) + " rpm", "BEMT, tip loss", "BEMT, closed tip", "CFD", "CFD vs. BEMT", "Reference BEMT"], rows,
              widths=[0.22, 0.15, 0.16, 0.13, 0.15, 0.19])
    doc.p(f"CFD at {CFD['iterations']} iterations, drift thrust {CFD['T_drift_pct_per100']:+.2f} % and torque {CFD['Q_drift_pct_per100']:+.2f} % "
          f"per 100 iterations ({'converged' if CFD['converged'] else 'NOT converged'}, limit 0.5 %). T/W at {S['cfd_rpm']} rpm: {CFD['tw_at_cfd_rpm']:.2f}. "
          f"Scaling at constant C_T: T/W 1.5 needs {CFD['rpm_for_tw_required']:.0f} rpm, {CFD['Q_at_tw_required']:.1f} N m, "
          f"{CFD['P_at_tw_required']:.0f} W and {CFD['motor_current_at_tw_required_a']:.0f} A on the U15XL; T/W at its {f0(I['rpm_available_sag'])} rpm: "
          f"{CFD['tw_at_motor_rpm']:.2f}.")
else:
    doc.table(["At " + str(S["cfd_rpm"]) + " rpm", "BEMT, tip loss", "BEMT, closed tip", "CFD", "Reference BEMT"], [
        ["Thrust [N]", f1(hp["legs_tip_loss"]["T"]), f1(hp["legs_no_tip_loss"]["T"]), "run pending", f1(hp["reference"]["T"])],
        ["Torque [N m]", f1(hp["legs_tip_loss"]["Q"]), f1(hp["legs_no_tip_loss"]["Q"]), "run pending", f1(hp["reference"]["Q"])],
        ["Shaft power [W]", f0(hp["legs_tip_loss"]["P"]), f0(hp["legs_no_tip_loss"]["P"]), "run pending", f0(hp["reference"]["P"])],
        ["Figure of merit", f3(hp["legs_tip_loss"]["FoM"]), f3(hp["legs_no_tip_loss"]["FoM"]), "run pending", f3(hp["reference"]["FoM"])],
    ], widths=[0.24, 0.18, 0.2, 0.18, 0.2])
    doc.p("The CFD column fills in when `python3 src/toroid.py post` has run; this document is regenerated from the result files. The "
          "requirement is met if the CFD thrust at this speed is at least the T/W 1.5 thrust, or, scaling at constant C_T, if the speed "
          "for it stays below the motor's speed and its torque below the 180 A rating.")
if os.path.exists(os.path.join(R_, "fig_convergence_toroid.png")):
    doc.img(os.path.join(R_, "fig_convergence_toroid.png"), width=6.2)

# ------------------------------------------------------------------------------------------------------------------
doc.h("10. Takeaways so far")
doc.bullets([
    f"On the blade-element numbers the toroid meets T/W 1.5 at {f0(leg15['rpm'])} rpm with {f0(leg15['motor_current_a'])} A, inside the U15XL's "
    f"{f0(I['rpm_available_sag'])} rpm and 180 A; its T/W at full motor speed is {B['legs_tip_loss']['at_motor_rpm']['tw']:.2f} to "
    f"{B['legs_no_tip_loss']['at_motor_rpm']['tw']:.2f} against {B['reference']['at_motor_rpm']['tw']:.2f} for the 2-blade reference.",
    f"Its blade set brackets {ms['volume_scaled_kg']:.2f} to {ms['area_scaled_kg']:.2f} kg against {ms['reference_kg']:.2f} kg: not the lever "
    "that closes the 55 lb budget. Its value, if any, is the power it saves (battery mass) and the noise.",
    "What the CFD settles: the real thrust and torque of the loop, including the tip-turn drag and the leg-to-leg interference that "
    "the blade-element method cannot see. A like-for-like run of the 2-blade reference on the same mesh recipe "
    "(`toroid.py case reference`) removes the mesh bias from the comparison.",
    "Next: the decision matrix across the rotor options (2-blade 44xx, 3-blade, 64xx, 60 in, toroid), weighted with mass first.",
])

out = os.path.join(here, "02_Toroidal_Rotor_Design.pdf")
doc.save(out)
print("wrote", out)

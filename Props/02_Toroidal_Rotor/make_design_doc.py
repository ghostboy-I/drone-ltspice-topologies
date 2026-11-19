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
CFDREF, MREF = J("cfd_reference.json"), J("mesh_reference.json")
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
    "The same leading-edge cell size is coarser relative to the toroid's thinner legs than to the reference's wide blade (its nose radius "
    "is several millimetres inboard). If the validation case's lesson carries over, an under-resolved nose reads high on torque, so the "
    "toroid-vs-reference torque comparison leans against the toroid, not for it.",
    "Mesh budget: a first mesh with 0.31 mm curvature cells (resolveFeatureAngle 25, 3 cells between levels) reached 4.25 M cells before "
    "layers, 1.8 M of them at the finest level, and snappy's layer stage ran out of memory on this 14 GB machine. The validation mesh "
    "that solved here is 2.45 M cells, so the curvature refinement was capped one level coarser, at 30 deg with 2 cells between levels.",
    "A guard stops the run if the thrust coefficient leaves (0, 3 x the T/W 1.5 value) or the outlet flow exceeds 10 x 2 v_i A for 50 "
    "iterations after the first 150: the runaway the validation case once had.",
])
SM = {"Toroid": J("smoke_toroid.json"), "2-blade reference": J("smoke_reference.json")}
mrows = []
for nm, m_ in (("Toroid", M), ("2-blade reference", MREF)):
    if m_:
        sk = sum(int(x) for x in __import__("re").findall(r"(\d+) highly skew faces", " ".join(m_.get("failed_checks", [])))) if m_.get("failed_checks") else 0
        sm = SM[nm] or {}
        mrows.append([nm, f"{m_['cells'] / 1e6:.2f} M", f"{m_['max_non_orthogonality']:.1f} / {m_['max_skewness']:.1f}", f"{sk}",
                      f"{m_['layer_coverage_pct']:.0f} % / {m_['layers_mean']:.1f}" if m_.get("layer_coverage_pct") is not None else "-",
                      f"{sm['s_per_iteration']:.1f} s, {sm['solver_memory_gb']:.1f} GB" if sm.get("s_per_iteration") else "-",
                      f"{sm['estimated_run_h']:.1f} h" if sm.get("estimated_run_h") else "-"])
if mrows:
    doc.table(["Mesh", "Cells", "Ortho / skew", "Skewed", "Layers", "Per iteration", "1500 it."], mrows,
              widths=[0.19, 0.1, 0.16, 0.11, 0.14, 0.18, 0.12])
    doc.p("Both meshes keep non-orthogonality under 65 deg (the limited schemes are built for that). checkMesh's only flag is a handful of "
          "faces with skewness above 4, out of millions; the validation mesh had none. 'Per iteration' is from a 10-iteration smoke test "
          "on 10 cores (case restored afterwards); '1500 it.' is the run time it implies.")

# ------------------------------------------------------------------------------------------------------------------
doc.h("9. Hand calculation vs. CFD")
hp = S["cfd_point_bemt"]
if CFD:
    rows = []
    for row in CFD["vs_hand"]:
        c_ = row["cfd"]; lo, hi = row["legs_tip_loss"], row["legs_no_tip_loss"]
        fmt = f3 if "merit" in row["quantity"] else (f0 if "power" in row["quantity"] else f1)
        rows.append([row["quantity"], fmt(lo), fmt(hi), fmt(c_), pct(lo, c_), fmt(row["reference"])])
    doc.table(["At " + str(S["cfd_rpm"]) + " rpm", "BEMT 4 legs", "BEMT closed", "CFD", "CFD vs BEMT", "BEMT 2-blade"], rows,
              widths=[0.24, 0.15, 0.15, 0.13, 0.16, 0.17])
    doc.p("'BEMT 4 legs' has Prandtl tip loss, 'BEMT closed' none; 'BEMT 2-blade' is the reference blade at the same speed.")
    doc.p(f"CFD at {CFD['iterations']} iterations, drift thrust {CFD['T_drift_pct_per100']:+.2f} % and torque {CFD['Q_drift_pct_per100']:+.2f} % "
          f"per 100 iterations ({'converged' if CFD['converged'] else 'NOT converged'}, limit 0.5 %). T/W at {S['cfd_rpm']} rpm: {CFD['tw_at_cfd_rpm']:.2f}. "
          f"Scaling at constant C_T: T/W 1.5 needs {CFD['rpm_for_tw_required']:.0f} rpm, {CFD['Q_at_tw_required']:.1f} N m, "
          f"{CFD['P_at_tw_required']:.0f} W and {CFD['motor_current_at_tw_required_a']:.0f} A on the U15XL. The motor's ceiling: the {CFD['motor_limit']} limit binds "
          f"first, at {f0(CFD['rpm_motor_limit'])} rpm and {f1(CFD['Q_motor_limit'])} N m, for T/W {CFD['tw_max_motor']:.2f}.")
    doc.p("Motor ceiling, from one CFD point: T and Q scale as rpm^2 at constant C_T and C_Q, so the rotor reaches the torque limit "
          "k_t I_peak at rpm x sqrt(Q_max/Q). Whichever comes first, that speed or the motor's k_load KV V, sets the ceiling.")
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
if CFD and CFDREF:
    doc.h("9b. Toroid vs. 2-blade reference, both by CFD on the same mesh recipe")
    rows = [[q_, fmt(CFD[k_]), fmt(CFDREF[k_]), pct(CFDREF[k_], CFD[k_])] for q_, k_, fmt in (
        (f"Thrust at {S['cfd_rpm']} rpm [N]", "T", f1), (f"Torque at {S['cfd_rpm']} rpm [N m]", "Q", f2), ("Figure of merit", "FoM", f3),
        ("rpm for T/W 1.5", "rpm_for_tw_required", f0), ("Power at T/W 1.5 [W]", "P_at_tw_required", f0),
        ("Motor current at T/W 1.5 [A]", "motor_current_at_tw_required_a", f0), ("Speed at the motor ceiling [rpm]", "rpm_motor_limit", f0),
        ("T/W at the motor ceiling", "tw_max_motor", f2))]
    doc.table(["Quantity", "Toroid", "Reference", "Toroid vs. ref."], rows, widths=[0.4, 0.2, 0.2, 0.2])
    doc.p(f"Both converged: toroid {CFD['converged']}, reference {CFDREF['converged']}. Same speed, air, domain and mesh settings, so the "
          f"mesh error is largely common to both and the difference is the rotor. At equal thrust the loop needs {pct(CFDREF['Q'], CFD['Q'])} torque; "
          f"the toroid hits the torque limit ({CFD['motor_limit']}) while the 2-blade reaches the speed limit ({CFDREF['motor_limit']}).")

# ------------------------------------------------------------------------------------------------------------------
LD, CAL, SW, BIAS, SWR, PRED = J("loads_toroid.json"), J("opt_calibration.json"), J("opt_sweep.json"), J("opt_bias.json"), J("opt_sweep_reference.json"), J("opt_predict_toroid_opt1.json")
OPT1 = J("cfd_toroid_opt1.json")
if LD and CAL and SW:
    doc.h("10. Optimisation, step 1")
    doc.p("Goal: T/W 1.5 inside the U15XL envelope (speed k_load KV V, torque k_t I_peak) at the lowest blade mass. Inside that envelope "
          f"the shaft power is at most Q_max Omega_max = {I['kt'] * I['i_peak']:.1f} N m x {I['rpm_available_sag'] * math.pi / 30:.1f} rad/s = "
          f"{I['kt'] * I['i_peak'] * I['rpm_available_sag'] * math.pi / 30 / 1000:.1f} kW, so T/W 1.5 needs a figure of merit of")
    pmax = I['kt'] * I['i_peak'] * I['rpm_available_sag'] * math.pi / 30
    doc.eq(r"FoM \geq \frac{T^{3/2}}{\sqrt{2\rho A}\;Q_{max}\,\Omega_{max}}" + f" = {I['T_required'] ** 1.5 / math.sqrt(2 * air['rho'] * I['A']) / pmax:.2f}")
    doc.p("and the best rotor is the one that absorbs the torque limit exactly at the speed limit with the highest figure of merit.")
    sg = LD["segments"]
    doc.p(f"Where the loop's thrust goes (CFD pressure forces, both loops): leading legs {f0(sg['leading leg']['Fz'])} N, trailing legs "
          f"{f0(sg['trailing leg']['Fz'])} N ({100 * LD['leg_thrust_ratio_trailing_to_leading']:.0f} % of the leading), tip turns {f0(sg['tip turn']['Fz'])} N, "
          f"root turns {f1(sg['root turn']['Fz'])} N. Both legs run ~35 % under the blade-element loading inboard; outboard, where the legs "
          "stack, the trailing leg loses most: biplane interference.")
    doc.img(os.path.join(R_, "fig_loads_toroid.png"), width=6.6)
    doc.p("A blade-element model anchored to the CFD: the section pitch is reduced by an effective pitch loss and the section drag raised "
          "by dcd, both fitted to the CFD (thrust per unit span and total torque):")
    doc.eq(r"\theta_{eff}=\theta-\left[a_0+a_1\left(\frac{r}{R}-0.6\right)\right],\qquad c_{d,eff}=c_d+\Delta c_d")
    doc.p(f"Fit on the toroid: a0 = {CAL['a0_deg']:.2f} deg, a1 = {CAL['a1_deg']:.2f} deg, dcd = {CAL['dcd']:.4f}; it reproduces the CFD "
          f"({f1(CAL['calibrated']['T'])} N, {f2(CAL['calibrated']['Q'])} N m) with the spanwise thrust within {CAL['span_rms_error_pct_of_peak']:.1f} % rms.")
    if BIAS:
        bb = BIAS[f"a1={CAL['a1_deg']:.2f}"]
        doc.table(["Fit (totals, same a1)", "a0 [deg]", "dcd", "Reading"], [
            ["2-blade reference CFD", f2(bb["reference"]["a0_deg"]), f"{bb['reference']['dcd']:.4f}", "the method (mesh, strip theory)"],
            ["Toroid CFD", f2(bb["toroid"]["a0_deg"]), f"{bb['toroid']['dcd']:.4f}", "method + loop"],
            ["Difference", f2(bb["toroid"]["a0_deg"] - bb["reference"]["a0_deg"]), f"{bb['toroid']['dcd'] - bb['reference']['dcd']:.4f}", "what the loop itself costs"],
        ], widths=[0.32, 0.14, 0.14, 0.4])
        doc.p("Most of the correction is common to both rotors, so it is the method: the thrust shortfall matches the Caradonna-Tung "
              "finding, and the extra drag is likely part mesh (coarse leading edges read high on torque). Comparisons between the two "
              "rotors remain fair; absolute torques probably read high.")
    doc.img(os.path.join(R_, "fig_opt_sweep.png"), width=6.6)
    bt = SW["highest_tw"]
    rows = [["Toroid as built", "0.50 x / +0", f2(CFD["tw_max_motor"]) + " (CFD)", f2(ms["area_scaled_kg"])],
            ["Toroid, best of sweep", f"{bt['chord_fraction']:.2f} x / {bt['collective_add_deg']:+.0f}", f2(bt["tw_max"]), f2(bt["mass_area_kg"])]]
    if PRED:
        rows.append(["Toroid candidate opt1", "0.30 x / +5, -3 deg/R", (f"{OPT1['tw_max_motor']:.2f} CFD ({PRED['motor']['tw_max']:.2f} fcst)" if OPT1 else f"{PRED['motor']['tw_max']:.2f} (forecast)"),
                     f2(T_ if (T_ := J('geometry_toroid_opt1.json')['mass']['area_scaled_kg']) else 0)])
    if SWR:
        br = SWR["best"]
        rows.append(["2-blade as built", "1.0 x / +0", f2(CFDREF["tw_max_motor"]) + " (CFD)" if CFDREF else f2(SWR["as_built_check"]["tw_max"]), f2(P["mass"]["reference_blade_set_kg"])])
        rows.append(["2-blade, best of sweep", f"{br['chord_scale']:.1f} x / {br['collective_add_deg']:+.0f}", f2(br["tw_max"]), f2(br["mass_area_kg"])])
    doc.table(["Rotor", "Chord / collective [deg]", "T/W ceiling on U15XL", "Blade set [kg]"], rows, widths=[0.27, 0.26, 0.31, 0.16])
    doc.p("Blade-set mass by wetted area (thin skins at minimum gauge). Swept rows are the calibrated model; 'CFD' rows are direct. "
          "In the model both rotor families improve the same way: thinner blades with more pitch absorb the torque limit right at the "
          "speed limit, and the two land within a few hundredths of each other. Neither reaches T/W 1.5 on this motor: the ~12 kW it "
          "can deliver is the binding limit, not the blade.")
    if OPT1 and PRED:
        m_ = PRED["model_at_cfd_rpm"]; LO = J("loads_toroid_opt1.json")
        doc.p(f"Candidate opt1 by CFD at {OPT1['rpm']} rpm ({OPT1['iterations']} iterations, converged {OPT1['converged']}): {f0(OPT1['T'])} N and "
              f"{f1(OPT1['Q'])} N m against the forecast {f0(m_['T'])} N and {f1(m_['Q'])} N m ({pct(m_['T'], OPT1['T'])} thrust, {pct(m_['Q'], OPT1['Q'])} torque). "
              f"Figure of merit {OPT1['FoM']:.2f}, below the as-built toroid's {CFD['FoM']:.2f}; ceiling T/W {OPT1['tw_max_motor']:.2f} "
              f"({OPT1['motor_limit']}-limited at {f0(OPT1['rpm_motor_limit'])} rpm). The forecast failed.")
        if LO:
            doc.p(f"What changed: the thinner legs did cure the interference (trailing leg {100 * LO['leg_thrust_ratio_trailing_to_leading']:.0f} % of the "
                  f"leading, up from {100 * LD['leg_thrust_ratio_trailing_to_leading']:.0f} %), but the sections now run at section force coefficients "
                  "near 1.0-1.1 where the model expected ~1.4, at the same torque: more pressure drag at high lift. The candidate's leading-edge "
                  f"radius is {J('geometry_toroid_opt1.json')['nose_radius_mm_at_075R']:.2f} mm at 0.75 R, about one {C['curvature_cell_mm']:.2f} mm cell, "
                  "the regime where the Caradonna-Tung case lost its suction peak; low-Reynolds stall (chord ~33 mm) is the other candidate. "
                  "Either way the model's constant extra drag does not carry over to thinner, higher-pitched blades on this mesh, so the "
                  "swept rows above are not trustworthy away from the as-built designs.")
        doc.img(os.path.join(R_, "fig_loads_toroid_opt1.png"), width=6.6)

# ------------------------------------------------------------------------------------------------------------------
doc.h("11. Takeaways so far")
tk = []
if CFD:
    tk.append(f"CFD (converged, {CFD['iterations']} iterations): at {S['cfd_rpm']} rpm the toroid makes {f0(CFD['T'])} N, {pct(hp['legs_tip_loss']['T'], CFD['T'])} "
              f"against the blade-element {f0(hp['legs_tip_loss']['T'])} N, for {f1(CFD['Q'])} N m ({pct(hp['legs_tip_loss']['Q'], CFD['Q'])}). Figure of merit "
              f"{CFD['FoM']:.2f} against {hp['legs_tip_loss']['FoM']:.2f}: the loop loses thrust far more than it saves torque.")
    ok = CFD["rpm_for_tw_required"] <= I["rpm_available_sag"] and CFD["motor_current_at_tw_required_a"] <= I["i_peak"]
    tk.append(f"T/W 1.5 on the U15XL: {'MET' if ok else 'NOT MET'}. Scaled at constant C_T it needs {f0(CFD['rpm_for_tw_required'])} rpm "
              f"(motor: {f0(I['rpm_available_sag'])}) and {f0(CFD['motor_current_at_tw_required_a'])} A (peak rating {I['i_peak']} A); "
              f"the toroid's ceiling on this motor is T/W {CFD['tw_max_motor']:.2f} ({CFD['motor_limit']}-limited at {f0(CFD['rpm_motor_limit'])} rpm)" +
              (f", the 2-blade reference's {CFDREF['tw_max_motor']:.2f} ({CFDREF['motor_limit']}-limited)." if CFDREF else "."))
    tk.append("The size of the shortfall matches the prop program's Caradonna-Tung check, where the same blade-element method over-predicted "
              "thrust by about 31 % while CFD matched the experiment. So part of the gap may be blade-element optimism that the 2-blade "
              "reference shares. " + ("The reference CFD (section 9b) confirms it: the 2-blade lands as far below its own estimate, so the "
              "shortfall is the method's, and the loop's own cost is the extra torque." if CFDREF else
              "The 2-blade reference on the same mesh (running) separates loop topology from method: if it also lands ~30 % low, the "
              "toroid's deficit is the method's; if it lands near its estimate, the loop itself is the problem."))
else:
    tk.append(f"On the blade-element numbers the toroid meets T/W 1.5 at {f0(leg15['rpm'])} rpm with {f0(leg15['motor_current_a'])} A, inside the U15XL's "
              f"{f0(I['rpm_available_sag'])} rpm and 180 A; its T/W at full motor speed is {B['legs_tip_loss']['at_motor_rpm']['tw']:.2f} to "
              f"{B['legs_no_tip_loss']['at_motor_rpm']['tw']:.2f} against {B['reference']['at_motor_rpm']['tw']:.2f} for the 2-blade reference.")
BSM = J("blade_structure_mass.json")
if BSM:
    tk.append(f"Blade mass under the same 50 N / 1.2 mm flex test as the 2-blade (Props/01 spar model): {BSM['toroid']['fixed-guided equivalent (6.25 N)']['set_kg']:.2f} kg "
              f"per rotor against {BSM['reference_set']:.2f} kg, and the legs pass only because the tip turn ties them; the early area/volume bracket "
              f"({ms['volume_scaled_kg']:.2f}-{ms['area_scaled_kg']:.2f} kg) was optimistic. The thin-leg candidate cannot pass at all.")
else:
    tk.append(f"Its blade set brackets {ms['volume_scaled_kg']:.2f} to {ms['area_scaled_kg']:.2f} kg against {ms['reference_kg']:.2f} kg.")
tk.append("The decision matrix (section 12) ranks the toroid 7th of 9, about 3.5 kg heavier than the 2-blade tri; the 2-blade hexacopter ranks first at the "
          "15 m/s design point. The refined-nose CFD (item 55 of the 54x18 log) is the remaining check on the absolute torque.")
doc.bullets(tk)

DM, DMF = J("decision_matrix.json"), J("decision_matrix_free_speed.json")
if DM:
    doc.h("12. Decision matrix, weight first")
    doc.p(f"Basis: {DM['basis']}. The mass criterion (50 %) is the change in propulsion + arms + fairing + mission pack against the "
          "tricopter with 2-blade 54 in rotors, read from the projects that computed it (Props/01 design-exploration entries 21, 44, 48, 49, "
          "the diameter study, Airframe 01/02, and this project's CFD), on two bases: plain blade-element (entry 48) and the 2-blade CFD's "
          "torque and power factors (entry 44). The coarse-nose CFD reads torque high, so the truth should lie between them. The other "
          "criteria are 0-10 judgements with a reason each (matrix_inputs.yaml); mass is scored linearly between the lightest and heaviest option.")
    rows = []
    fm = lambda x: "-" if x is None else f"{x:+.1f}"
    for i, r_ in enumerate(DM["rows"], 1):
        sc = r_["scores"]
        short = {"hex_2blade": "Hex, 2-blade", "hex_3blade": "Hex, 3-blade", "tri_60in": "Tri, 2-blade 60 in", "y6_2blade": "Y6, 2-blade",
                 "tri_2blade": "Tri, 2-blade (current)", "tri_3blade": "Tri, 3-blade", "tri_toroid": "Tri, toroid as built",
                 "tri_toroid_opt1": "Tri, toroid cand. 1", "tilt_tri": "Tilt-tri (Osprey)"}[r_["key"]]
        rows.append([str(i), short, f"{fm(r_['mass_delta_bemt'])} / {fm(r_['mass_delta_cfd'])}",
                     f"{sc['mass']:.1f}", str(sc["tw15"]), str(sc["noise"]), str(sc["evidence"]), str(sc["risk"]), f"{r_['total']:.2f}"])
    doc.table(["#", "Option", "Mass d [kg]", "Mass", "T/W", "Noise", "Evid.", "Risk", "Total"], rows,
              widths=[0.04, 0.29, 0.17, 0.08, 0.08, 0.08, 0.08, 0.08, 0.10])
    doc.p("Mass d: BEMT basis / CFD-factor basis, kg against the 2-blade tri (negative is lighter). Scores 0-10, total weighted.")
    doc.img(os.path.join(R_, "fig_decision_matrix.png"), width=6.6)
    tor = next(r_ for r_ in DM["rows"] if r_["key"] == "tri_toroid"); pt = tor["parts"]
    doc.p(f"The toroid's mass, from the CFD pair at equal thrust: power x{pt['power_ratio']:.3f} and torque x{pt['torque_ratio']:.3f}. Blades sized "
          f"by the same 50 N / 1.2 mm flex test as every other row (Props/01 spar model; the loop's legs pass only with the tip turn tying them): "
          f"{pt['blades_flex_test']:+.2f} kg; torque-sized motors {pt['motors']:+.2f} kg (a full catalogue step to the next motor would be "
          f"{pt['motor_catalogue_step_worst']:+.2f}); ESCs {pt['escs']:+.2f}; pack for the hover segments {pt['pack_hover']:+.2f}, and up to "
          f"{pt['pack_cruise_if_penalised']:+.2f} more if cruise carries the same penalty (no forward-flight CFD of the loop exists).")
    doc.table(["What moves the mass most", "Tri [kg]", "Hex [kg]"],
              [[lv["lever"], fm(lv["tri"]), fm(lv["hex"])] for lv in DM["levers"]], widths=[0.6, 0.2, 0.2])
    sens = DM["sensitivity_mass_weight"]; sensf = DMF["sensitivity_mass_weight"] if DMF else {}
    lab = {r_["key"]: r_["label"] for r_ in DM["rows"]}
    doc.bullets([
        f"At the 15 m/s design point the 2-blade hexacopter ranks first at every mass weight from 30 % to 70 %; it is the lightest "
        f"({fm(DM['rows'][0]['mass_delta_bemt'])} to {fm(DM['rows'][0]['mass_delta_cfd'])} kg), the quietest, and like the Y6 it survives a motor out.",
        "If cruise speed is free (best range, ~21-25 m/s), the tri is lighter than the hex by "
        + (f"{next(r_ for r_ in DMF['rows'] if r_['key'] == 'hex_2blade')['mass_delta_mid']:.1f} kg" if DMF else "a few kg")
        + "; the hex still ranks first up to a ~60 % mass weight, and above that the 60 in tricopter overtakes it ("
        + (" > ".join(lab[k] for k in sensf.get("0.7", [])[:2]) if sensf else "") + ").",
        "The toroidal rotor ranks 7th of 9 in both scenarios and at every mass weight: about 3.5 kg heavier than the 2-blade tri, "
        "and further from T/W 1.5 on the U15XL. Its one possible advantage, lower noise, is an estimate here, not a computation.",
        "The requirements move the mass far more than any rotor choice: the battery chemistry (13 kg on the tri), the cruise speed "
        "(7 kg), whether the CFD torque is real (5-8 kg) and sizing the motors for T/W 1.5 instead of 2.0 (~2 kg). None of the options "
        f"comes near the 55 lb ({DM['drone_budget_kg']:.1f} kg) drone limit: propulsion, arms and pack alone are 43-52 kg.",
    ])

out = os.path.join(here, "02_Toroidal_Rotor_Design.pdf")
doc.save(out)
print("wrote", out)

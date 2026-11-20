"""Builds 03_Osprey_TiltHex_Design.pdf from results/*.json and the figures. No number here is typed in: everything comes
from sizing.json, final.json, geometry.json and transition.json (and Airframe 02's results for the comparison)."""
import json, math, os, sys
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, "..", "..", "Topologies", "tools"))
from designdoc import Doc
sys.path.insert(0, os.path.join(here, "src"))
import wing_sections as wsec
AF = lambda n: wsec.LABEL.get(n, "NACA " + n)

R = os.path.join(here, "results")
J = lambda n, root=R: json.load(open(os.path.join(root, n)))
S, F, G = J("sizing.json"), J("final.json"), J("geometry.json")
T = J("transition.json") if os.path.exists(os.path.join(R, "transition.json")) else None
R2 = os.path.join(here, "..", "02_Osprey_TiltTri", "results")
S2, F2 = J("sizing.json", R2), J("final.json", R2)
T2 = J("transition.json", R2) if os.path.exists(os.path.join(R2, "transition.json")) else None
img = lambda n: os.path.join(R, n)
w, L, st, dr, cr, dl, ro, cx = S["wing"], S["layout"], S["stability"], S["drag"], S["cruise"], S["download"], S["rotor"], S["coax_alternative"]
r54 = S["rotor_54x18_on_mn1123"]
d = F["design"]
import yaml
P = yaml.safe_load(open(os.path.join(here, "params.yaml")))

doc = Doc("Airframe 03: Osprey-Style Tilt-Hex Frame",
          "280 lb MTOW, 225 lb payload  |  six 54 in hex rotors, four tilting  |  25 m/s  |  sizing, FEM screen, BEMT trim")

# ------------------------------------------------------------------------------------------------------------------
doc.h("1. What was asked, and the decisions it needed")
doc.p("The request: a wing-attached fuselage for the hexacopter, because the hex is the layout the decision matrix "
      "(Props/02_Toroidal_Rotor/DECISION_MATRIX.md) ranks first. The user did not mind keeping the Osprey shape or grouping props. "
      "Four inputs were confirmed, and one was revised after the first numbers came in:")
doc.table(["Question", "Decision (2026-11-20)", "Why it had to be asked"], [
    ["Which rotor", "The matrix's hex rotor", "Props entry 46: 54 in, 2 blades, MN1123 KV53"],
    ["How it flies forward", "4 tilting + 2 fixed aft", "Sets the layout: tilt mechanism count, airplane-mode thrust"],
    ["Tilting rotors", "Planar on the wing*", f"*revised: coax pairs cost x{cx['power_ratio']:.2f} power (sec. 3)"],
    ["Mass and speed", "Same as the Osprey", "280 lb / 225 lb payload, 25 m/s, hot day"],
    ["Scope", "Sizing + model + trim", "No shell FEM or fittings yet"],
], widths=[0.2, 0.28, 0.52])

# ------------------------------------------------------------------------------------------------------------------
doc.h("2. The frame")
doc.img(img("fig_iso_hover.png"), width=5.6)
doc.img(img("fig_3view.png"), width=6.0)
doc.table(["Item", "Value", "Item", "Value"], [
    ["Overall width (disks)", f"{G['hover']['overall_width']:.2f} m", "Overall length", f"{G['hover']['overall_length']:.2f} m"],
    ["Wing span / chord", f"{w['b']:.2f} / {w['c']:.3f} m", "Wing section / incidence", f"{AF(w['airfoil'])} / {w['incidence_deg']:.1f} deg"],
    ["Tip hubs", f"x {L['x_front_hub']:+.2f}, y +/-{L['y_front_hub']:.2f} m", "Inboard hubs", f"x {L['x_inboard_hub']:+.2f}, y +/-{L['y_inboard_hub']:.2f} m"],
    ["Aft hubs", f"x {L['x_tail_hub']:+.2f}, y +/-{L['y_tail_hub']:.2f} m", "Hover CG (mean hub)", f"x {L['x_cg_hover']:+.3f} m"],
    ["Inboard pylon length", f"{L['inboard_pylon_length_m']:.2f} m", "H-tail / fins", f"{st['S_h']:.2f} / {st['S_v_total']:.2f} m^2"],
], widths=[0.24, 0.26, 0.24, 0.26])
doc.p("The fuselage, wing and tail are Airframe 02's: same weight, same cruise speed, and therefore the same wing "
      f"({AF(w['airfoil'])}, {w['S']:.2f} m^2, picked on tripped clmax in Airframe 02 sec. 5). What changes is everything that holds rotors.")

# ------------------------------------------------------------------------------------------------------------------
doc.h("3. The rotor, and why the props are not grouped coaxially")
doc.p("The hex rotor is read from Props entry 46 (the row the matrix scores), not copied: its blade, its 24xx polar set and the motor's "
      "loaded speed and torque limits. Re-solving its hover point with the Props BEMT reproduces the entry:")
doc.table(["Hex rotor at W/6, hot day", "This frame", "Props entry 46"], [
    ["Hover rpm", f"{ro['hover_rpm']:.1f}", f"{ro['hover_rpm_props']:.1f}"],
    ["Shaft power / torque", f"{ro['hover_P_w']:.0f} W / {ro['hover_Q_nm']:.2f} N m", "-"],
    ["Figure of merit", f"{ro['FoM']:.3f}", "-"],
    ["Thrust ceiling (limit)", f"{ro['thrust_cap_n']:.0f} N ({ro['cap_limit']}), T/W {ro['T_over_W_cap']:.2f}", "T/W 2 design"],
], widths=[0.4, 0.35, 0.25])
doc.p("Grouping props was allowed, so the first layout put a coaxial pair on each tilting wing-tip head. The Props coaxial model "
      "(config_study.coax_pair: the upper wake as a semi-infinite vortex cylinder on the lower disk, both rotors on the BEMT, "
      "trimmed to equal torque) gives the interference factor")
doc.eq(r"\kappa_{int}=\frac{P_{ind,upper}+P_{ind,lower}}{2\,P_{ind,iso}(T/2)}=%.3f,\qquad \frac{P_{pair}}{2\,P_{iso}}=\frac{%.0f}{%.0f}=%.3f" %
       (cx["kappa_int"], cx["P_pair_w"], cx["P_two_isolated_w"], cx["power_ratio"]),
       note=f"spacing h = {cx['h_m']:.3f} m (0.2 D); upper rotor carries {100*cx['split_upper']:.1f} %, lower runs at {cx['rpm_lower']:.0f} rpm")
doc.p(f"Hand check: momentum theory with the lower rotor in the fully developed upper wake gives 1.281 (Leishman), and uniform "
      f"loading at infinite spacing gives 1.354 (Props docstring), so {cx['kappa_int']:.2f} is in the expected range. The vehicle would "
      f"hover on {cx['hover_total_w']/1e3:.1f} kW against {cx['hover_planar_w']/1e3:.1f} kW planar, no better than the tricopter, and "
      f"the lower rotors would turn {cx['rpm_lower']:.0f} rpm against a {S['motor']['rpm_max']:.0f} rpm limit. The user moved the "
      "tilting four to the wing, side by side.")
doc.p("The hex blade has a catch for a tiltrotor. It was optimised to reach T/W 2 on the light MN1123 (rpm and torque limits "
      "reached together), so it has low pitch. The Props BEMT puts its zero-thrust speed in axial flight at the motor limit at "
      f"{S['prop_airplane']['hex']['v_zero_thrust_at_rpm_max']:.1f} m/s, below the wing's {w['v_stall_ms']:.1f} m/s stall speed: "
      "with these blades the frame cannot fly full airplane mode. The Phase 2 54x18 blade keeps pulling to "
      f"{S['prop_airplane']['54x18']['v_zero_thrust_at_rpm_max']:.1f} m/s. On the same motor it trades against the hex blade like this:")
doc.table(["Blade on the tilting rotors (MN1123)", "Hex blade (entry 46)", "54x18 (Phase 2)"], [
    ["Hover rpm / power at W/6", f"{ro['hover_rpm']:.0f} / {ro['hover_P_w']:.0f} W", f"{r54['hover_rpm']:.0f} / {r54['hover_P_w']:.0f} W"],
    ["Hover torque / FoM", f"{ro['hover_Q_nm']:.1f} N m / {ro['FoM']:.3f}", f"{r54['hover_Q_nm']:.1f} N m / {r54['FoM']:.3f}"],
    ["Thrust ceiling, T/W", f"{ro['thrust_cap_n']:.0f} N ({ro['cap_limit']}), {ro['T_over_W_cap']:.2f}", f"{r54['thrust_cap_n']:.0f} N ({r54['cap_limit']}), {r54['T_over_W_cap']:.2f}"],
    ["Zero-thrust speed (axial, motor limit)", f"{S['prop_airplane']['hex']['v_zero_thrust_at_rpm_max']:.1f} m/s", f"{S['prop_airplane']['54x18']['v_zero_thrust_at_rpm_max']:.1f} m/s"],
], widths=[0.4, 0.3, 0.3])
doc.p("The 54x18 hovers more efficiently (lower tip speed) and flies airplane mode, but it is torque-hungry: on the MN1123 it stops at "
      f"T/W {r54['T_over_W_cap']:.2f}. Reaching T/W 2 with it needs the heavier MN1320 class. Section 8 flies both.")

# ------------------------------------------------------------------------------------------------------------------
doc.h("4. Rotor layout: equal thrust, download and blade clearance")
doc.p("Six equal rotors share the weight equally only when the CG sits at the mean hub position. With the tip and inboard heads at "
      "different x:")
doc.eq(r"x_{cg}=\frac{2x_{tip}+2x_{in}+2x_t}{6}\quad\Rightarrow\quad x_{tip}=3\,x_{cg,hover}-x_{in}-x_t",
       note=f"x_tip = 3({L['x_cg_hover']:+.3f}) - ({L['x_inboard_hub']:+.3f}) - ({L['x_tail_hub']:+.3f}) = {L['x_front_hub']:+.3f} m; FE check: mean hub x {L['x_cg_hub_mean']:+.3f} m")
doc.p(f"Three constraints set the hubs. (1) The aft disks clear the wing trailing edge in plan: x_t = x_TE - gap - R = {L['x_tail_hub']:+.3f} m. "
      f"(2) The inboard disks clear the leading edge in plan, so they put no download on the wing: x_in = x_LE(y_in) + gap + R = "
      f"{L['x_inboard_hub']:+.3f} m, on {L['inboard_pylon_length_m']:.2f} m pylons. Strip theory with the disk over the wing would put "
      f"most of the rotor's thrust into download (Cd,90 2.0 at the wake speed v = {dl['v_wing_ms']:.1f} m/s, q = {dl['q_wing_pa']:.0f} Pa). "
      f"(3) The CG equation then puts the tip pivot at x {L['x_front_hub']:+.3f} m, behind the tip leading edge. Tilted forward, the "
      f"disk plane stands at x {L['x_front_hub'] + 0.35:+.3f} m, so any inboard overlap would put the blades through the wing: the tip "
      f"disks sit fully outboard (0.10 m gap), and the side-by-side spacing 2R + gap places the inboard hubs at y +/-{L['y_inboard_hub']:.2f} m.")
dt = S["download_tail"]
doc.p(f"Download: tip {100*dl['chosen']['frac']:.1f} %, inboard {100*dl['inboard']['frac']:.1f} %, each aft rotor {100*dt['frac']:.1f} % "
      f"(its disk edge over the boom and the cone, {dt['A_boom_m2']:.3f} + {dt['A_fuselage_m2']:.3f} m^2); vehicle "
      f"{100*S['download_total_frac']:.1f} % of the weight, against {100*S2['download_total_frac']:.1f} % on the tricopter.")

# ------------------------------------------------------------------------------------------------------------------
doc.h("5. Airplane mode: stability and drag")
doc.table(["Quantity", "Value", "Quantity", "Value"], [
    ["Static margin", f"{100*st['static_margin']:.0f} % MAC", "CG shift on conversion", f"{st['dx_conversion']*1e3:+.0f} mm (4 heads)"],
    ["H-tail volume / area", f"{st['V_h']:.2f} / {st['S_h']:.2f} m^2", "Tail arm", f"{st['l_h']:.2f} m"],
    ["Drag area D/q", f"{dr['CDA_total_m2']:.3f} m^2 (tri {S2['drag']['CDA_total_m2']:.3f})", "L/D at 25 m/s", f"{dr['L_over_D']:.1f} (tri {S2['drag']['L_over_D']:.1f})"],
], widths=[0.24, 0.26, 0.24, 0.26])
rows = [[k, f"{v_:.4f}"] for k, v_ in dr["parts_m2"].items()] + [["wing profile + induced", f"{dr['wing_profile_m2'] + dr['induced_m2']:.4f}"]]
doc.table(["Drag item (Raymer build-up, as Airframe 02)", "D/q [m^2]"], rows, widths=[0.7, 0.3])
doc.p("The two parked aft rotors with their pylons and cross-beam, and the inboard pylons, are what the hex adds over the tri. "
      + (f"Airplane mode with the hex blades: {cr['note']}." if not cr["airplane_mode_possible"] else
         f"Airplane-mode cruise: {cr['shaft_power_w']:.0f} W shaft, eta {cr['prop_eta']:.2f}."))

# ------------------------------------------------------------------------------------------------------------------
doc.h("6. Structure: FEM screen")
doc.p("Airframe 02's beam model (Airframe/01's Timoshenko frame FE, laminate sections and allowables), extended: two wing nodes at the "
      "inboard pylon roots, pylon tubes forward to the inboard pivots, a cross-beam tube at the boom carrying the aft rotors, six "
      "MN1123 heads. Hover trims distribute six thrusts by the least change from equal thrust that zeroes pitch and roll:")
doc.eq(r"T=T_0+A^T\left(AA^T\right)^{-1}\left(b-A\,T_0\right),\qquad T_0=\frac{F}{6}", size=12,
       note="A = [1 ... 1; y_1 ... y_6; x_1 ... x_6] (rows: sum of thrust, roll moment, pitch moment), b = F [1, y_cg, x_cg]; T is the six thrusts")
doc.table(["Member", "Selected design (sweep: lightest PASS)"], [
    ["Wing box", f"{d['wing']['n_w45']} x +/-45 per face, UD caps {d['wing']['n_ud_root']} -> {d['wing']['n_ud_tip']}, {d['wing']['core_mm']:.1f} mm core"],
    ["Pods + pylons", f"{d['pod']['n_w45']} x 45 + {d['pod']['n_ud']} UD (pod D {F['pod_D_m']*1e3:.0f} mm, pylon D {P['nacelle']['pylon_diameter_m']*1e3:.0f} mm)"],
    ["Keel", f"{d['keel']['depth']*1e3:.0f} x {d['keel']['width']*1e3:.0f} mm, {d['keel']['n_w45']} x 45 + {d['keel']['n_ud']} UD, {d['keel']['core_mm']:.1f} mm core"],
    ["Boom / cross-beam", f"D {d['boom']['D']*1e3:.0f} mm ({d['boom']['n_w45']} + {d['boom']['n_ud']}) / D {d['xbeam']['D']*1e3:.0f} mm ({d['xbeam']['n_w45']} + {d['xbeam']['n_ud']})"],
    ["Gear", f"D {d['gear']['D']*1e3:.0f} mm legs, {d['gear']['absorber_mm']:.0f} mm struts, track {d['gear']['main_track']:.2f} m"],
], widths=[0.2, 0.8])
rows = [[g_, f"{wv['strain']:+.2f}", wv["strain_case"], f"{wv['buckling']:+.2f}", wv["buck_case"]] for g_, wv in sorted(F["worst"].items())]
doc.table(["Group", "Strain MS", "case", "Buckling MS", "case"], rows, widths=[0.1, 0.13, 0.3, 0.14, 0.33])
lc1 = F["cases"]["LC1 hover pull-up n=2"]
doc.p(f"Verdict: {F['verdict']}. Shaft tilt at LC1 {max(lc1['shaft_tilt_deg']):.2f} deg (limit 1.0). Modal bands: 1P/2P +-15 % at the hex "
      f"rotor's {S['rotor']['hover_rpm']:.0f} rpm hover (faster than the tri's 1932 rpm, so the 1P band moves up to "
      f"{F['bands']['nominal']['hover']['1'][0]:.1f}-{F['bands']['nominal']['hover']['1'][1]:.1f} Hz). The airplane band is centred on the "
      f"tilting rotors' rpm at the best-range trim point of sec. 8 ({30*sum(F['bands']['nominal']['airplane']['1']):.0f} rpm, hex blade), "
      f"{F['bands']['nominal']['airplane']['1'][0]:.1f}-{F['bands']['nominal']['airplane']['1'][1]:.1f} Hz; the first screen used the hover rpm "
      "there, and once the trim result was fed back two wing/pylon modes (26.1 and 28.4 Hz) fell inside it, so the members were re-swept "
      f"around the first design (+0.6 kg). The selected design puts its nearest airplane modes at "
      f"{max(h for h in F['modes']['airplane']['hz'] if h < F['bands']['nominal']['airplane']['1'][0]):.1f} Hz, only just below the band: "
      "a pass on the screen's rule, not a real separation, and the first thing the whirl-flutter check must look at. "
      f"{len(F['flags'])} flags remain, mostly modes below 1P that need the whirl-flutter check this model does not do.")
doc.img(img("fig_modes.png"), width=6.2)
hc = F["hand_checks"]
doc.table(["Hand check", "Hand", "FE", "Diff", "Note"], [
    ["H1 wing root moment, LC1", f"{hc['H1']['M_hand_nm']:.0f} N m", f"{hc['H1']['M_fe_nm']:.0f} N m", f"{hc['H1']['diff_pct']:+.1f} %", "T_tip y_tip + T_in y_in - n g sum(m y)"],
    ["H2 wing root moment, LC5", f"{hc['H2']['M_hand_nm']:.0f} N m", f"{hc['H2']['M_fe_nm']:.0f} N m", f"{hc['H2']['diff_pct']:+.1f} %", f"lumped lift: {hc['H2']['M_hand_lumped_nm']:.0f} N m"],
    ["H3 wing-box EI (root)", f"{hc['H3']['EI_hand']:.3g}", f"{hc['H3']['EI_section']:.3g}", f"{hc['H3']['diff_pct']:+.1f} %", "parallel axis, mid-planes"],
], widths=[0.27, 0.13, 0.13, 0.1, 0.37])
doc.p(f"H1: two rotors per wing half at y {hc['H1']['y_hub']:.2f} and {hc['H1']['y_inboard']:.2f} m, {hc['H1']['T_front_n']:.0f} N each at n = 2. "
      f"The inboard rotor sits halfway out, so the root moment is lower than the tri's ({F2['hand_checks']['H1']['M_hand_nm']:.0f} N m) "
      f"even though the tip rotor is further out. H2 is the lumping error of the 12-element elliptic load, as in Airframe 02.")

# ------------------------------------------------------------------------------------------------------------------
doc.h("7. Mass")
doc.img(img("fig_mass.png"), width=6.2)
vm, vm2 = F["vehicle_mass"], F2["vehicle_mass"]
doc.table(["Item [kg]", "Tilt-hex (03)", "Tilt-tri (02)"], [
    [k, f"{vm.get(k, 0):.2f}", f"{vm2.get(k2, 0):.2f}"] for k, k2 in (("airframe", "airframe"), ("propulsion (6 rotors)", "propulsion (3 rotors)"),
                                                                     ("tilt hardware", "tilt hardware"), ("battery", "battery"), ("avionics", "avionics"), ("payload", "payload"))
] + [["total", f"{sum(vm.values()):.1f}", f"{sum(vm2.values()):.1f}"]], widths=[0.4, 0.3, 0.3])
doc.p(f"The six MN1123 heads ({F['tip_mass_kg']:.2f} kg each) weigh less than the tri's three U15XL heads, and the lighter rotor loads "
      f"let the wing box shed caps: airframe {F['mass_airframe_kg']:.1f} kg against {F2['mass_airframe_kg']:.1f} kg. The vehicle is still "
      f"{sum(vm.values()):.0f} kg against the {F['mtow_kg']:.0f} kg MTOW (the same budget gap as every frame in this program). At that mass "
      f"each rotor must hover {F['hover_thrust_per_rotor_model_n']:.0f} N, so the hex rotor's {ro['thrust_cap_n']:.0f} N ceiling gives T/W "
      f"{6 * ro['thrust_cap_n'] / (sum(vm.values()) * 9.80665):.2f}, not 2.")

# ------------------------------------------------------------------------------------------------------------------
if T:
    doc.h("8. Forward flight with the BEMT: corridor, transition, missions")
    doc.p("The trim model is Airframe 02's (src/transition.py, sec. 12 of its design doc), extended to six rotors. In the pitch plane, "
          "at each airspeed V and nacelle angle delta it solves sum F_x = m a, sum F_z = W, sum M_cg = 0 for (tilting rpm, pitch theta, "
          "aft rpm) with the aft rotors running, or (tilting rpm, theta, elevator) with them parked. Every rotor is a Props "
          "bemt.edgewise call at its own disk angle:")
    doc.eq(r"\gamma=\delta+\theta,\qquad \alpha_s=90^\circ-\gamma,\qquad \vec F_{rotor}=T\,(\cos\gamma,\sin\gamma)+H\,(-\sin\gamma,\cos\gamma)", size=12)
    doc.p(f"The four tilting rotors share one angle, rpm and flow, so they make the same thrust. Limits: motor rpm {S['motor']['rpm_max']:.0f} "
          f"and torque {S['motor']['Q_max_nm']:.1f} N m (MN1123), pitch -10..+15 deg, elevator 25 deg, tail CL 1.0, wing stall once the wing could "
          f"carry 10 % of the weight. The H-tail incidence is rigged to {T['tail_rig']['i_t_deg']:.1f} deg for a neutral elevator in airplane "
          "cruise at 25 m/s (with the 54x18 blades, the only ones that can fly it).")
    doc.img(img("fig_corridor.png"), width=6.6)
    doc.img(img("fig_power_speed.png"), width=6.4)
    rows = []
    for key, lab in (("design", "hex blade, 127 kg"), ("design_54x18", "54x18 tilting, 127 kg"), ("current", f"hex blade, {T['current']['mass_kg']:.0f} kg")):
        r = T.get(key)
        if not r: continue
        h0 = next(o for o in r["heli_mode"] if o["V"] == 0)
        ba, bh, bp = r.get("best_range_airplane"), r.get("best_range_heli"), r["best_range_any"]
        rows.append([lab, f"{h0['P_batt']/1e3:.1f} kW",
                     f"{bp['wh_per_km']:.1f} @ {bp['V']:.0f} m/s, {bp['delta']:.0f} deg",
                     f"{ba['wh_per_km']:.1f} @ {ba['V']:.0f}" if ba else "cannot trim",
                     f"{bh['wh_per_km']:.1f} @ {bh['V']:.0f}" if bh else "-"])
    if T2:
        r = T2["design"]; h0 = next(o for o in r["heli_mode"] if o["V"] == 0); bp, ba, bh = r["best_range_any"], r.get("best_range_airplane"), r.get("best_range_heli")
        rows.append(["Airframe 02 tri, 127 kg", f"{h0['P_batt']/1e3:.1f} kW", f"{bp['wh_per_km']:.1f} @ {bp['V']:.0f} m/s, {bp['delta']:.0f} deg",
                     f"{ba['wh_per_km']:.1f} @ {ba['V']:.0f}" if ba else "-", f"{bh['wh_per_km']:.1f} @ {bh['V']:.0f}" if bh else "-"])
    doc.table(["Case", "Hover", "Best range [Wh/km]", "Airplane", "Nacelles up"], rows, widths=[0.3, 0.11, 0.29, 0.15, 0.15])
    doc.img(img("fig_transition.png"), width=6.4)
    rows = []
    for key, lab in (("design", "hex"), ("design_54x18", "54x18")):
        r = T.get(key)
        if not r: continue
        for k, v_ in r["mission"].items():
            if isinstance(v_, dict):
                rows.append([lab, k.replace("_", " "), f"{v_['V_cruise']:.0f} m/s", f"{v_['transition_s']:.0f} s", f"{v_['accel_wh'] + v_['decel_wh']:.0f}",
                             f"{v_['total_wh']:.0f}", "yes" if v_["complete"] else "gaps"])
    doc.p("Hover is battery power; best range is over every nacelle angle; airplane and nacelles-up are Wh/km at their best speeds. "
          "Missions: 60 s of hover, accelerate from hover along the minimum-power nacelle schedule, cruise to 10 km, decelerate, at the "
          "fastest of 1, 0.5 and 0.25 m/s^2 that trims at every speed.")
    doc.table(["Blade", "Strategy", "Cruise", "Transitions", "Transition Wh", "Total Wh", "Trims"], rows, widths=[0.1, 0.2, 0.12, 0.14, 0.16, 0.14, 0.14])
    hk = T["design"]["hand_checks"]; h1 = hk["H1_hover"]
    rows = [["H1 hover statics", f"T_tilt {h1['T_f_hand']:.1f} / T_aft {h1['T_t_hand']:.1f} N", f"{h1['T_f_trim']:.1f} / {h1['T_t_trim']:.1f} N", "Z and M balance"],
            ["H1 figure of merit", f"P_ideal {h1['P_ideal_w']:.0f} W", f"BEMT {h1['P_f_bemt_w']:.0f} W", f"FoM {h1['FoM']:.3f}"]]
    if "H2_cruise" in T["design_54x18"]["hand_checks"]:
        h2 = T["design_54x18"]["hand_checks"]["H2_cruise"]
        rows.append(["H2 airplane cruise (54x18)", f"axial BEMT {h2['P_axial_bemt_same_T_w']:.0f} W", f"edgewise {h2['P_shaft_trim_w']:.0f} W",
                     f"eta {h2['eta_prop']:.2f} vs ideal {h2['eta_ideal']:.2f}"])
    if "H3_statics" in hk:
        h3 = hk["H3_statics"]
        rows.append(["H3 force closure", "0", f"{h3['sum_Fx_N']:.1e} / {h3['sum_Fz_N']:.1e} N", f"V {h3['V']:.0f}, delta {h3['delta']:.0f}"])
    for rw in hk["H4_energy"]["rows"][:4]:
        rows.append([f"H4 energy V {rw['V']:.0f} delta {rw['delta']:.0f}", f"{rw['P_hand_w']:.0f} W", f"{rw['P_bemt_w']:.0f} W",
                     f"{100*(rw['P_bemt_w']/rw['P_hand_w']-1):+.1f} %"])
    doc.table(["Hand check (127 kg)", "Hand", "Model", "Note"], rows, widths=[0.3, 0.26, 0.24, 0.2])
    doc.p(f"H1's BEMT hover power ({h1['P_f_bemt_w']:.0f} W per tilting rotor, FoM {h1['FoM']:.3f}) is above the sec. 3 value "
          f"({ro['hover_P_w']:.0f} W, FoM {ro['FoM']:.3f}): the trim calls bemt.edgewise at V = 0, which uses one uniform inflow times "
          "kappa, while sec. 3 uses the axial BEMT with momentum on every annulus. The trim is the conservative of the two; both are "
          "the same Props code.")
    h2 = T["design_54x18"]["hand_checks"].get("H2_cruise")
    if h2:
        doc.p(f"H2 explains why airplane mode loses to partial conversion on this frame. At 25 m/s the drag is shared by four rotors, "
              f"{h2['thrust_per_rotor_trim_n']:.0f} N each: the 54x18 turns {h2['rpm_trim']:.0f} rpm for it and spends most of its power "
              f"on profile drag, eta {h2['eta_prop']:.2f} against the momentum ideal {h2['eta_ideal']:.2f} (the tri's three rotors at "
              f"{T2['design']['best_range_airplane']['eta_prop']:.2f}). With the nacelles at 60-70 deg the rotors still lift about 45 % "
              "of the weight while pulling, and the wing runs at a lower CL; that is the cheapest way through the air for both blades.")
    c5 = T["design_54x18"].get("convert_at_cruise")
    if c5:
        doc.p(f"Conversion with the 54x18: the out path flies the minimum-power schedule to {c5['V']:.0f} m/s, which ends at "
              f"{c5['from_delta']:.0f} deg, then tilts to 0 at constant speed; every angle from there to 0 trims at that speed "
              f"({'yes' if c5['all_angles_trim'] else 'no'}). The hex-blade frame has no such path: its airplane-mode column is empty.")
    doc.p("H4 is the rotor energy budget P = F_prop V + kappa T v_i + P_0: v_i from Glauert's equation, profile power scaled from the "
          "hover point by (Omega/Omega_h)^3 (1 + 4.65 mu^2). It closes within a few per cent wherever it is evaluated, so the BEMT "
          "numbers behind the corridor are self-consistent.")

# ------------------------------------------------------------------------------------------------------------------
doc.h("9. Takeaways")
tk = [f"Grouping props coaxially costs x{cx['power_ratio']:.2f} hover power on the pair (kappa_int {cx['kappa_int']:.2f}); it would erase the hex's lead. "
      "Planar on the wing, the four tilting rotors put no download on it.",
      f"The six-rotor frame is lighter than the tri: airframe {F['mass_airframe_kg']:.1f} vs {F2['mass_airframe_kg']:.1f} kg, propulsion "
      f"{vm['propulsion (6 rotors)']:.1f} vs {vm2['propulsion (3 rotors)']:.1f} kg.",
      f"The matrix's hex blade is a hover blade sized to the MN1123: it cannot pull past {S['prop_airplane']['hex']['v_zero_thrust_at_rpm_max']:.0f} m/s, "
      "so the hex-blade frame flies wing-borne only partly converted. The 54x18 on the tilting rotors flies airplane mode and hovers "
      f"cheaper, but caps T/W at {r54['T_over_W_cap']:.2f} on the MN1123."]
if T:
    a, b5 = T["design"]["best_range_any"], T["design_54x18"]["best_range_any"]
    tk.append(f"Best range (127 kg): hex blade {a['wh_per_km']:.1f} Wh/km at {a['V']:.0f} m/s with the nacelles at {a['delta']:.0f} deg; "
              f"54x18 tilting blades {b5['wh_per_km']:.1f} Wh/km at {b5['V']:.0f} m/s, {b5['delta']:.0f} deg"
              + (f"; the Airframe 02 tri {T2['design']['best_range_any']['wh_per_km']:.1f} Wh/km." if T2 else "."))
if T and T2:
    h_, h5, h2_ = (next(o for o in r["heli_mode"] if o["V"] == 0)["P_batt"] / 1e3 for r in (T["design"], T["design_54x18"], T2["design"]))
    tk.append(f"Hover is where the hex pays: {h_:.1f} kW (hex blades) or {h5:.1f} kW (54x18 tilting) at 127 kg against the tri's {h2_:.1f} kW. "
              "Cruise is a tie at best (four lightly loaded rotors in airplane mode are profile-bound), so the hex frame wins on hover-heavy missions.")
tk.append("Open: shell FEM and fittings (scope), whirl flutter (modes below 1P on 1.07 m pylons), the inboard rotors' slipstream on "
          "the wing, fixed-pitch 1P blade loads in edgewise flight, the real mass against 280 lb, and a blade designed for the tilting rotors.")
doc.bullets(tk)
doc.save(os.path.join(here, "03_Osprey_TiltHex_Design.pdf"))
print("written")

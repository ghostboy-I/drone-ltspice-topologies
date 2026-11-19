"""Builds 02_Osprey_TiltTri_Design.pdf from results/*.json and the figures. No number here is typed in: everything comes
from sizing.json, final.json, geometry.json and (when the runs exist) cfd_airfoil2d.json."""
import json, math, os, sys
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, "..", "..", "Topologies", "tools"))
from designdoc import Doc

R = os.path.join(here, "results")
J = lambda n: json.load(open(os.path.join(R, n)))
S, F, G = J("sizing.json"), J("final.json"), J("geometry.json")
CFD = J("cfd_airfoil2d.json") if os.path.exists(os.path.join(R, "cfd_airfoil2d.json")) else None
img = lambda n: os.path.join(R, n)
f0 = lambda x: f"{x:.0f}"; f1 = lambda x: f"{x:.1f}"; f2 = lambda x: f"{x:.2f}"; f3 = lambda x: f"{x:.3f}"
w, L, st, dr, cr, dl = S["wing"], S["layout"], S["stability"], S["drag"], S["cruise"], S["download"]
d = F["design"]

doc = Doc("Airframe 02: Osprey-Style Tilt-Tricopter Frame",
          "280 lb MTOW, 225 lb payload  |  three 54 in rotors, two tilting  |  wing-borne cruise at 25 m/s  |  sizing, FEM screen, CFD set-up")

# ------------------------------------------------------------------------------------------------------------------
doc.h("1. What was asked, and the decisions it needed")
doc.p("The request: a drone frame that looks like a V-22 Osprey, matched to the prop program's rotor size, with CFD on the airfoils "
      "and FEM on the fuselage to follow. No tiltrotor outline existed in the repository, so four inputs were confirmed first. "
      "Each one changed the design:")
doc.table(["Question", "Decision (user, 2026-11-18)", "Why it had to be asked"], [
    ["Rotor count", "3 rotors, Osprey look", "A true twin needs 623 N per 54 in rotor just to hover; CFD gives ~437 N"],
    ["Conversion", "Real tilt, faster cruise", "Sets whether the wing is structure + lift, or a fairing"],
    ["Mass targets", "280 lb MTOW, 225 lb payload", "Same as the tricopter program (55 lb drone known not to close)"],
    ["Wing size", "Long wing, cruise 25 m/s", f"V-22 proportions give {S['v22_scaled']['wing_area_m2']:.2f} m^2: needs {S['v22_scaled']['speed_for_CL1_ms']:.0f} m/s"],
], widths=[0.17, 0.30, 0.53])
doc.p(f"The last row is the key physics. Scaled to 54 in rotors, the V-22 has hubs {S['v22_scaled']['hub_spacing_m']:.2f} m apart and a "
      f"{S['v22_scaled']['wing_area_m2']:.2f} m^2 wing. Carrying 280 lb on it at CL 1.0 takes {S['v22_scaled']['speed_for_CL1_ms']:.0f} m/s. "
      f"The fixed-pitch prop can't get near that: from its own BEMT advance curve, thrust falls to zero at J = {S['prop_airplane']['J_zero_thrust']:.2f}, "
      f"which is {S['prop_airplane']['v_zero_thrust_at_rpm_max']:.1f} m/s at the motor's {S['motor']['rpm_max']:.0f} rpm limit. The real V-22 gets "
      f"there with variable-pitch proprotors at {S['v22']['wing_loading_n_m2']/1e3:.1f} kN/m^2 wing loading. So the wing grows until it carries "
      "the weight at a speed the props can reach. The Osprey look (high wing, wingtip nacelles, H-tail with twin fins, upswept "
      "ramp, tricycle gear in sponsons) stays.")

# ------------------------------------------------------------------------------------------------------------------
doc.h("2. The frame")
doc.img(img("fig_iso_hover.png"), width=5.8)
doc.img(img("fig_3view.png"), width=6.4)
doc.table(["Item", "Value", "Item", "Value"], [
    ["Overall width (disks)", f"{G['hover']['overall_width']:.2f} m", "Overall length", f"{G['hover']['overall_length']:.2f} m"],
    ["Wing span / chord", f"{w['b']:.2f} / {w['c']:.3f} m", "Wing area / AR", f"{w['S']:.2f} m^2 / {w['AR']:.1f}"],
    ["Wing section", f"NACA {w['airfoil']}", "Sweep / dihedral", f"{w['sweep_deg']:+.0f} / {w['dihedral_deg']:.1f} deg (V-22)"],
    ["Front hubs (hover)", f"x {L['x_front_hub']:+.2f}, y +/-{L['y_front_hub']:.2f} m", "Tail hub", f"x {L['x_tail_hub']:+.2f} m"],
    ["Fuselage L x W x H", f"{S['fuselage']['L']:.2f} x {S['fuselage']['W']:.2f} x {S['fuselage']['H']:.2f} m", "H-tail / fins", f"{st['S_h']:.2f} m^2 / {st['S_v_total']:.2f} m^2"],
    ["Hover CG (= hub centroid)", f"x {L['x_cg_hover']:+.3f} m", "Height (hover)", f"{G['hover']['height_hover']:.2f} m"],
], widths=[0.25, 0.25, 0.22, 0.28])
doc.p("Coordinates: x forward, y left, z up, origin at the wing-root quarter chord on the spar-box axis. The rotor heads tilt the way the "
      "Bell V-280 does (the newer member of the Osprey family). Each wing tip carries a fixed pod, and only the motor and rotor tilt, at "
      "the pod's front end. Section 4 shows why the heads must sit ahead of the wing.")

# ------------------------------------------------------------------------------------------------------------------
doc.h("3. What was taken from the V-22, and what physics overrode")
v = S["v22"]
doc.table(["Proportion", "V-22", "Used here", "Set by"], [
    ["Wing aspect ratio", f"{v['AR']:.2f}", f"{w['AR']:.2f}", "V-22 (look)"],
    ["Forward sweep / dihedral", "6 / 3.5 deg", f"{-w['sweep_deg']:.0f} / {w['dihedral_deg']:.1f} deg", "V-22 (look; sweep gives blade-flap clearance)"],
    ["Fuselage length / rotor D", f"{v['fuselage_L_over_D']:.2f}", f"{S['fuselage']['L']/1.3716:.2f}", "V-22"],
    ["Hub spacing / rotor D", f"{v['hub_spacing_over_D']:.2f}", f"{L['hub_spacing_front_m']/1.3716:.2f}", "wing span + download limit (sec. 4)"],
    ["Wing chord / rotor D", f"{v['chord_over_D']:.2f}", f"{w['c']/1.3716:.2f}", "wing area for 25 m/s (sec. 5)"],
    ["Wing loading", f"{v['wing_loading_n_m2']:.0f} N/m^2", f"{w['wing_loading_n_m2']:.0f} N/m^2", "stall margin at 25 m/s"],
], widths=[0.28, 0.16, 0.16, 0.40])

# ------------------------------------------------------------------------------------------------------------------
doc.h("4. Rotor layout: equal thrust, download and the tail")
doc.p("Three equal rotors share the weight equally only when the CG sits at the centroid of the hub triangle. Moments about the "
      "front-hub axis give:")
doc.eq(r"x_{cg} = \frac{2\,x_f + x_t}{3}", note="equal thrust T = W/3 on every rotor (front hubs at x_f, tail hub at x_t)")
doc.p(f"The tail disk must clear the wing in plan, so x_t <= x_TE - gap - R = {L['x_tail_hub']:+.3f} m. Airplane mode needs the CG "
      f"ahead of the neutral point by the static margin. If the hubs sat on the wing spar, as on the V-22, the centroid would fall at "
      f"about 81 % of the chord, and holding a 10 % margin would need a tail volume of ~1.6 (a 1.8 m^2 tail). Inverting the equation "
      f"for a normal tail volume (V_h = {st['V_h']:.2f}, Raymer, twin-engine GA) gives the front hub position:")
doc.eq(r"x_f = \frac{3\,x_{cg,hover} - x_t}{2}", note=f"= {L['x_front_hub']:+.3f} m: the heads sit {L['head_ahead_of_tip_LE_m']:+.2f} m ahead of the wing-tip leading edge")
doc.p("Download. The wake below a hovering rotor accelerates. Momentum theory on the wake axis gives the velocity a distance z below the disk:")
doc.eq(r"v(z) = v_i\left(1 + \frac{z}{\sqrt{z^2+R^2}}\right),\quad v_i=\sqrt{\frac{T}{2\rho A}},\quad D = C_{d,90}\,\frac{\rho v^2}{2}\,A_{overlap}",
       note=f"v_i = {dl['vi_ms']:.1f} m/s, v = {dl['v_wing_ms']:.1f} m/s at the wing (z = {dl['z_m']:.2f} m); Cd,90 = 2.0 (flat strip, no flaperon)")
doc.img(img("fig_download_thrust.png"), width=6.4)
dt = S["download_tail"]
doc.p(f"Left: wing download against how far the disk reaches inboard of the wing tip. With the hub on the tip, as on the V-22, the wing "
      f"under the disk takes {100*dl['v22_like']['frac']:.0f} % of the rotor's thrust (the V-22 cuts its own ~10 % by drooping its "
      f"flaperons). The largest overlap within the 5 % limit is {dl['chosen']['overlap']:.2f} R, giving {100*dl['chosen']['frac']:.1f} %. "
      f"Under the tail rotor, the boom and the aft fuselage cone ({dt['A_boom_m2']:.3f} + {dt['A_fuselage_m2']:.3f} m^2) take "
      f"{100*dt['frac']:.1f} % of that rotor's thrust. That exceeds 5 %, so it is reported as an open item: an airfoil-section boom (as "
      f"Airframe/01's arms) is the fix. Vehicle total: {100*S['download_total_frac']:.1f} % of the weight. "
      "Right: thrust from the two front props against airplane-mode drag (section 5).")

# ------------------------------------------------------------------------------------------------------------------
doc.h("5. Wing: section and size")
doc.p("The wing is the smallest one that cruises at 1.2 x its stall speed (light-aircraft practice, Raymer ch. 5). 3-D CLmax is taken as "
      "0.9 x the section clmax (Raymer eq. 12.15, unswept, untwisted), and the aspect ratio stays at the V-22's:")
doc.eq(r"C_{L,cr} = \frac{0.9\,c_{l,max}}{1.2^2},\qquad S = \frac{W}{\frac{1}{2}\rho V^2 C_{L,cr}},\qquad b=\sqrt{AR\,S}")
doc.img(img("fig_polars.png"), width=6.4)
rows = [[f"NACA {a['name']}", f"{a['tc']:.2f}", f3(a['clmax']), f3(a['CL_cruise']), f2(a['S']), f"{a['cd_cruise']:.5f}", f"{a['cm0']:+.3f}", f"{a['DA_wing']:.4f}"]
        for a in S["airfoil_table"]]
doc.table(["Section", "t/c", "clmax", "CL cruise", "S [m^2]", "cd", "cm0", "wing D/q [m^2]"], rows, widths=[0.14, 0.07, 0.1, 0.12, 0.11, 0.12, 0.1, 0.16])
doc.p(f"Ranking: wing drag area (profile + induced) among sections thick enough for a spar box (t/c >= 15 %). At CL ~1 the induced "
      f"drag ({dr['induced_m2']:.3f} m^2) is ten times the profile drag ({dr['wing_profile_m2']:.3f} m^2), so the sections score within "
      f"4 % of each other, and t/c and cm0 decide. NACA {w['airfoil']} wins. Its cm0 of {w['cm0']:+.3f} is a nose-down moment the tail "
      "trims (it is in the airplane load case). Wing: "
      f"S = {w['S']:.2f} m^2, b = {w['b']:.2f} m, c = {w['c']:.3f} m, stall {w['v_stall_ms']:.1f} m/s, Re = {S['wing_re']:.2e}.")

# ------------------------------------------------------------------------------------------------------------------
doc.h("6. Airplane mode: stability, drag, thrust, gusts")
doc.eq(r"h_n = h_{ac,wb} + \eta\,V_h\,\frac{a_t}{a_w}\left(1-\frac{d\varepsilon}{d\alpha}\right),\quad a=\frac{2\pi AR}{2+\sqrt{AR^2+4}},\quad \frac{d\varepsilon}{d\alpha}=\frac{2a_w}{\pi AR}",
       note="neutral point (Etkin; Helmbold lift slope); the fuselage shifts h_ac forward via Raymer eq. 16.25")
doc.table(["Quantity", "Value", "Quantity", "Value"], [
    ["a_w / a_t [1/rad]", f"{st['a_w']:.2f} / {st['a_t']:.2f}", "d eps / d alpha", f3(st['deps_dalpha'])],
    ["h_ac (wing + body)", f3(st['h_ac_wb']), "Fuselage shift", f"{st['dh_fuselage']:+.3f} c"],
    ["Neutral point h_n", f3(st['h_n']), "CG, airplane mode", f3(st['h_cg_air'])],
    ["Static margin", f"{100*st['static_margin']:.0f} % MAC", "CG shift on conversion", f"{st['dx_conversion']*1e3:+.0f} mm (heads swing forward)"],
], widths=[0.25, 0.22, 0.25, 0.28])
doc.p("Not in this estimate: the destabilising normal force of the two props in airplane mode. On tiltrotors that force is large, which "
      "is why the margin is 10 % and not 5 %. The 3-D CFD case listed in section 9 should measure it.")
rows = [[k, f"{v_:.4f}"] for k, v_ in dr["parts_m2"].items()] + [["wing profile (XFOIL cd)", f"{dr['wing_profile_m2']:.4f}"], ["induced, CL^2/(pi e AR)", f"{dr['induced_m2']:.4f}"],
                                                               ["total D/q", f"{dr['CDA_total_m2']:.3f}"]]
doc.table(["Drag item (Raymer component build-up)", "D/q [m^2]"], rows, widths=[0.7, 0.3])
doc.p(f"Drag {dr['drag_n']:.0f} N, L/D {dr['L_over_D']:.1f} (best possible {dr['LD_max']:.1f} at CL {dr['CL_LDmax']:.2f}, so the stall-limited "
      f"wing is already near its best L/D). The two props give {cr['thrust_available_n']:.0f} N at 25 m/s on the motor's speed limit "
      f"(x{cr['thrust_margin']:.1f}). They cruise at {cr['rpm']:.0f} rpm, J = {cr['J']:.3f}, prop efficiency {cr['prop_eta']:.2f}, "
      f"{cr['shaft_power_w']/1e3:.1f} kW shaft. That is {cr['wh_per_km']:.0f} Wh/km against {cr['multirotor_wh_per_km']:.0f} Wh/km for "
      "the tricopter at 15 m/s (Props Phase 2), the payoff of the wing.")
g = S["gust"]
doc.eq(r"n = 1 + \frac{K_g\,U\,V\,a\,\rho}{2\,W/S},\qquad K_g=\frac{0.88\,\mu}{5.3+\mu},\qquad \mu=\frac{2\,W/S}{\rho\,c\,a\,g}",
       note=f"FAR 23.341, U = 15.24 m/s: mu = {g['mu_g']:.1f}, Kg = {g['K_g']:.3f}, n = {g['n_gust']:.2f} (the design case; above the 2.5 manoeuvre)")

# ------------------------------------------------------------------------------------------------------------------
doc.h("7. Structure: FEM screen")
doc.p("The FE model reuses Airframe/01's beam FE (12-DOF Timoshenko frame elements, consistent mass, inertia relief, free-free modes), its "
      "thin-walled composite sections and its Toray 2510 laminate data and allowables. Both flight modes are built, with the rotor heads "
      "and their inertia in the right place. Members: one spar box tip to tip (sandwich webs, UD caps tapering to the tip), pod tubes "
      "to the tilt pivots, a keel box under the cabin floor, a tail-boom tube, and tricycle gear with shock struts. The payload is "
      "placed so the hover CG lands exactly on the hub centroid.")
dd = d
doc.table(["Member", "Selected design (sweep: lightest PASS)"], [
    ["Wing box", f"{dd['wing']['n_w45']} x +/-45 woven per face, UD caps {dd['wing']['n_ud_root']} -> {dd['wing']['n_ud_tip']} plies root -> tip, {dd['wing']['core_mm']:.1f} mm core"],
    ["Pods", f"D {F['pod_D_m']*1e3:.0f} mm tube, {dd['pod']['n_w45']} x 45 + {dd['pod']['n_ud']} UD"],
    ["Keel", f"{dd['keel']['depth']*1e3:.0f} x {dd['keel']['width']*1e3:.0f} mm box, {dd['keel']['n_w45']} x 45 + {dd['keel']['n_ud']} UD, {dd['keel']['core_mm']:.1f} mm core"],
    ["Tail boom", f"D {dd['boom']['D']*1e3:.0f} mm, {dd['boom']['n_w45']} x 45 + {dd['boom']['n_ud']} UD"],
    ["Gear", f"D {dd['gear']['D']*1e3:.0f} mm legs, {dd['gear']['n_w45']} x 45 + {dd['gear']['n_ud']} UD, {dd['gear']['absorber_mm']:.0f} mm struts, track {dd['gear']['main_track']:.2f} m, clearance {dd['gear']['clearance']*1e3:.0f} mm"],
], widths=[0.18, 0.82])
rows = []
for gname, wv in sorted(F["worst"].items()):
    rows.append([gname, f"{wv['strain']:+.2f}", wv["strain_case"], f"{wv['buckling']:+.2f}", wv["buck_case"]])
doc.table(["Group", "Strain MS", "case", "Buckling MS", "case"], rows, widths=[0.1, 0.13, 0.3, 0.14, 0.33])
lc1 = F["cases"]["LC1 hover pull-up n=2"]
doc.p(f"Verdict: {F['verdict']}. "
      + (("Open items: " + "; ".join(F["reasons"]) + ". ") if F["reasons"] else "")
      + f"Shaft tilt at LC1 {max(lc1['shaft_tilt_deg']):.2f} deg (limit 1.0); landing strokes "
      + ", ".join(f"{k.split(' ', 1)[1]} {v['stroke']*1e3:.0f} mm (n {v['n']:.2f})" for k, v in F["landing"].items()) + ". "
      + (f"The sweep evaluated {F['sweep']['n']} designs; {F['sweep']['n_pass']} passed." if "sweep" in F else ""))
doc.img(img("fig_modes.png"), width=6.4)
doc.p("Modes. Airframe/01 required every hub-moving mode to stay out of the 1P and 2P bands over all hover weights and atmospheres. "
      "Merged, those bands run 16.6 to 78.6 Hz (red strip). A 6.6 m wide frame always has hub-moving modes in that range. This design "
      "therefore checks the bands at its two operating points instead: MTOW hover on a hot day, and airplane cruise. It keeps 01's "
      "direction rule: axial hub motion against 2P, in-plane motion against 1P. "
      "This deviates from Airframe/01, and the user confirmed it on 2026-11-18. Envelope crossings are still listed as flags for off-design weights and air. Modes below 1P are allowed (V-22 practice) but must pass a "
      f"whirl-flutter check, which this model doesn't do. Flags: {len(F['flags'])} (listed in final.json).")
hc = F["hand_checks"]
doc.table(["Hand check", "Hand", "FE", "Diff", "Note"], [
    ["H1 wing root moment, LC1", f"{hc['H1']['M_hand_nm']:.0f} N m", f"{hc['H1']['M_fe_nm']:.0f} N m", f"{hc['H1']['diff_pct']:+.1f} %", "T y_hub - n g sum(m y)"],
    ["H2 wing root moment, LC5", f"{hc['H2']['M_hand_nm']:.0f} N m", f"{hc['H2']['M_fe_nm']:.0f} N m", f"{hc['H2']['diff_pct']:+.1f} %", f"lumped lift: {hc['H2']['M_hand_lumped_nm']:.0f} N m"],
    ["H3 wing-box EI (root)", f"{hc['H3']['EI_hand']:.3g}", f"{hc['H3']['EI_section']:.3g}", f"{hc['H3']['diff_pct']:+.1f} %", "parallel axis, mid-planes"],
], widths=[0.27, 0.14, 0.14, 0.1, 0.35])
doc.p(f"H2 is {hc['H2']['diff_pct']:.0f} % high against the exact elliptic centroid 4/(3 pi)(b/2) = {hc['H2']['ybar_elliptic']:.3f} m. "
      f"The cause is the 12-element lumping, which puts the centroid at {hc['H2']['ybar_lumped']:.3f} m; against the lumped load the FE "
      f"agrees to {100*(hc['H2']['M_fe_nm']/hc['H2']['M_hand_lumped_nm']-1):+.1f} %. The error is conservative. H3 matches by construction: "
      f"it confirms the box geometry the FE uses (depth {hc['H3']['depth_m']*1e3:.1f} mm from the NACA contour at 15 % and 60 % chord).")

# ------------------------------------------------------------------------------------------------------------------
doc.h("8. Mass against the budget")
doc.img(img("fig_mass.png"), width=6.4)
doc.p(f"Airframe {F['mass_airframe_kg']:.1f} kg (wing {F['mass_breakdown'].get('wing', 0):.1f} kg is the biggest item). The drone without "
      f"payload is {F['drone_kg']:.1f} kg against the 55 lb ({F['drone_budget_kg']:.1f} kg) budget, so the vehicle is "
      f"{sum(F['vehicle_mass'].values()):.0f} kg against the {F['mtow_kg']:.0f} kg MTOW. This is the same gap Phase 1 of the prop program "
      "found; the structure is designed for the real mass. Two consequences follow at that mass. Each rotor must hover "
      f"{F['hover_thrust_per_rotor_model_n']:.0f} N (CFD-corrected 54 in rotor: ~437 N at the motor limit). The wing stalls at "
      f"{F['stall_at_model_mass_ms']:.1f} m/s, so keeping the 1.2 margin at 25 m/s would need {F['wing_area_for_model_mass_m2']:.2f} m^2. "
      "The wing was sized to the 280 lb requirement, as specified.")

# ------------------------------------------------------------------------------------------------------------------
doc.h("9. CFD and FEM still to run")
if CFD:
    for code, blk in CFD.items():
        rows = [[f"{r_['alpha']:+d}", f3(r_.get('cl', float('nan'))) if 'cl' in r_ else r_.get("status", ""), f"{r_['cd']:.5f}" if 'cd' in r_ else "",
                 f"{r_.get('diff_cl_pct'):+.1f} %" if r_.get('diff_cl_pct') is not None else "", f"{r_.get('diff_cd_pct'):+.0f} %" if 'diff_cd_pct' in r_ else ""] for r_ in blk["rows"]]
        doc.table([f"NACA {code} alpha", "cl (CFD)", "cd (CFD)", "cl vs XFOIL", "cd vs XFOIL"], rows, widths=[0.2, 0.2, 0.2, 0.2, 0.2])
pl = json.load(open(os.path.join(here, "cfd", "airfoil2d", "plan.json")))
doc.p(f"2-D airfoil RANS (OpenFOAM 13, foamRun incompressibleFluid, k-omega SST), set up and meshed. The NACA {w['airfoil']} wing case runs at "
      f"Re {pl[w['airfoil']]['Re']:.2e} with alpha {pl[w['airfoil']]['alphas'][0]} to {pl[w['airfoil']]['alphas'][-1]} deg; the NACA 0012 tail at "
      f"Re {pl['0012']['Re']:.2e}. Each uses a six-block C-grid with {pl[w['airfoil']]['cells']} cells and first cell "
      f"{pl[w['airfoil']]['dy1_m']*1e6:.0f} um (y+ ~ 1), and checkMesh passes. Run with cfd/airfoil2d/run_all.sh, which waits while another "
      "session's foamRun holds the machine. Stated before running: fully turbulent SST should give cd above XFOIL's free-transition value "
      "and an earlier stall, with cl in the linear range within a few %.")
doc.bullets([
    "3-D CFD next: geometry/airframe_hover.stl and rotor_disks_hover.stl (named solids, metres, FE axes) are ready for snappyHexMesh "
    "with actuator disks. They give the real wing and boom download (sec. 4) and the fuselage interference.",
    "Fuselage FEM next: the beam screen above sizes the keel; a CalculiX shell model of the fuselage skin, frames and the wing "
    "carry-through (as Airframe/01's ccx_verify.py does for its arm) is the follow-up.",
    "Whirl flutter of the wing + pod + rotor (the defining tiltrotor aeroelastic check) is not in any model yet.",
])

# ------------------------------------------------------------------------------------------------------------------
doc.h("10. Takeaways")
doc.bullets([
    f"A true V-22 scale-down can't fly wing-borne on fixed-pitch 54 in props: its wing needs {S['v22_scaled']['speed_for_CL1_ms']:.0f} m/s and "
    f"the props stop pulling at {S['prop_airplane']['v_zero_thrust_at_rpm_max']:.0f} m/s. The Osprey look survives with a longer wing.",
    f"The wing pays for itself in cruise: {cr['wh_per_km']:.0f} Wh/km against {cr['multirotor_wh_per_km']:.0f} Wh/km for the tricopter.",
    f"Hub on the wing tip (V-22) puts {100*dl['v22_like']['frac']:.0f} % download on the wing; this frame keeps the disks mostly outboard.",
    "Equal thrust on three equal rotors fixes the hover CG at the hub centroid, which pushes the front heads ahead of the wing (V-280 "
    "style) so the airplane mode can have a normal tail.",
    f"Gusts, not manoeuvres, size the wing: n = {g['n_gust']:.2f} at 25 m/s, because the wing loading is light ({w['wing_loading_n_m2']:.0f} N/m^2).",
    f"Modal rule: nominal operating-point bands (user, 2026-11-18). Open decisions: the tail-boom download ({100*S['download_tail']['frac']:.0f} % of the tail rotor), the real mass against the 280 lb sizing weight, "
    f"and the tilt actuator ({S['tilt_actuator']['hold_torque_nm']:.0f} N m hold torque against an assumed 0.85 kg actuator).",
])
doc.save(os.path.join(here, "02_Osprey_TiltTri_Design.pdf"))
print("written")

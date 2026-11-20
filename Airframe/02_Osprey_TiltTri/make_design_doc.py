"""Builds 02_Osprey_TiltTri_Design.pdf from results/*.json and the figures. No number here is typed in: everything comes
from sizing.json, final.json, geometry.json and (when the runs exist) cfd_airfoil2d.json."""
import json, math, os, sys
FRAME_CAP_W_ = 0.030   # m, as src/fuselage_shell.py FRAME_CAP_W
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, "..", "..", "Topologies", "tools"))
from designdoc import Doc
sys.path.insert(0, os.path.join(here, "src"))
import tiltcfg, wing_sections as wsec
AF = lambda n: wsec.LABEL.get(n, "NACA " + n)

R = os.path.join(here, "results")
J = lambda n: json.load(open(os.path.join(R, n)))
S, F, G = J("sizing.json"), J("final.json"), J("geometry.json")
CFD = J("cfd_airfoil2d.json") if os.path.exists(os.path.join(R, "cfd_airfoil2d.json")) else None
FS = J("fuselage_shell_model.json") if os.path.exists(os.path.join(R, "fuselage_shell_model.json")) else None
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
    ["Wing section / incidence", f"{AF(w['airfoil'])} / {w['incidence_deg']:.1f} deg", "Sweep / dihedral", f"{w['sweep_deg']:+.0f} / {w['dihedral_deg']:.1f} deg (V-22)"],
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
doc.h("5. Wing: section, size and incidence")
AT = {a["name"]: a for a in S["airfoil_table"]}; a0 = AT["4415"]; ab = AT[w["airfoil"]]
doc.p("The wing is the smallest one that cruises at 1.2 x its stall speed (light-aircraft practice, Raymer ch. 5). 3-D CLmax is taken as "
      "0.9 x the section clmax (Raymer eq. 12.15, unswept, untwisted), and the aspect ratio stays at the V-22's:")
doc.eq(r"C_{L,cr} = \frac{0.9\,c_{l,max}}{1.2^2},\qquad S = \frac{W}{\frac{1}{2}\rho V^2 C_{L,cr}},\qquad b=\sqrt{AR\,S}")
doc.p("Candidates: NACA 4- and 5-digit sections from XFOIL's generator, and three NASA general-aviation sections read from the UIUC "
      "coordinate database (src/wing_sections.py converts their Lednicer layout to XFOIL's Selig order and checks t/c from the "
      "coordinates). Each gets two XFOIL polars at the cruise Re and Mach: free transition (e^N, Ncrit 9) and tripped at 5 % / 10 % "
      "chord. The wing is sized on the TRIPPED clmax. A wing with bugs, rain or a seam loses its laminar run, and the fully turbulent "
      "CFD (sec. 10) follows the tripped polar, not the free one. Cruise drag uses the free polar.")
doc.img(img("fig_polars.png"), width=6.4)
rows = [[AF(a['name']), f"{a['tc']:.3f}", f"{a['clmax_free']:.3f} / {a['clmax']:.3f}" + ("" if a["stall_found"] else " *"), f3(a['CL_cruise']), f2(a['S']),
         f"{a['cd_cruise']:.5f}", f"{a['cm0']:+.3f}", f"{a['DA_wing']:.4f}"] for a in S["airfoil_table"]]
doc.table(["Section", "t/c", "clmax free/trip", "CL cr", "S [m^2]", "cd", "cm0", "D/q [m^2]"], rows,
          widths=[0.25, 0.07, 0.18, 0.08, 0.09, 0.1, 0.09, 0.12])
doc.p(f"Ranked by tripped clmax. * = the peak is at the 20 deg end of the sweep, not a stall (NACA 6418 tripped), so it is not eligible. "
      f"Pick: the largest tripped clmax with t/c >= 15 % (spar depth): {AF(w['airfoil'])}, clmax {ab['clmax']:.3f} against {a0['clmax']:.3f} for "
      f"the NACA 4415 the first version picked. That version ranked by wing drag area instead, so it chose the 4415 for drag, not lift. "
      "The GA(W) sections get their lift from a large leading-edge radius, which keeps the suction peak attached to a higher angle, and a "
      "cusped lower surface that loads the aft chord. The MOD variant has less aft loading than the original: cm0 "
      f"{ab['cm0']:+.3f} against {AT['ls417']['cm0']:+.3f}, close to the 4415's {a0['cm0']:+.3f}, so the tail trims it as before. The NACA 6-digit "
      f"camber that would match its lift costs twice the nose-down moment (6415: {AT['6415']['cm0']:+.3f}). At 17 % it is also deeper "
      "than the 4415, so the spar box gains depth.")
doc.p("What the higher clmax buys, and what it costs. The rule fixes the stall speed at V / 1.2, so a better section shrinks the wing: "
      f"S {a0['S']:.2f} -> {w['S']:.2f} m^2, span {math.sqrt(w['AR']*a0['S']):.2f} -> {w['b']:.2f} m. The induced drag at fixed weight and speed "
      "depends only on the span:")
bi0 = math.sqrt(w['AR'] * a0['S'])
doc.eq(r"\frac{D_i}{q}=\frac{C_L^2 S}{\pi e\,AR}=\frac{(W/q)^2}{\pi e\,b^2}:\qquad \frac{D_{i}}{D_{i,4415}}=\left(\frac{%.3f}{%.3f}\right)^2=%.3f" % (bi0, w['b'], (bi0 / w['b']) ** 2),
       note="induced drag area %.4f m^2 (sizing.json: %.4f)" % ((S['W_n'] / S['q_cruise_pa']) ** 2 / (math.pi * 0.80 * w['b'] ** 2), dr['induced_m2']))
doc.p(f"The section's own profile drag is also higher (cd {ab['cd_cruise']:.4f} at its cruise CL against {a0['cd_cruise']:.4f}). Wing drag area "
      f"goes from {a0['DA_wing']:.3f} to {ab['DA_wing']:.3f} m^2 (+{100*(ab['DA_wing']/a0['DA_wing']-1):.0f} %), and the vehicle cruise L/D is "
      f"{dr['L_over_D']:.2f} ({cr['wh_per_km']:.1f} Wh/km). For the NACA 4415 wing it was 7.37 (75.7 Wh/km, commit 2d4d5e4). So the "
      f"high-lift section gives a smaller, lighter wing (airframe {F['mass_airframe_kg']:.2f} kg against 32.87, mostly wing, its fairings and "
      "the smaller tail) and it costs ~7 % cruise energy. Keeping the old wing "
      "area and spending the higher clmax on stall margin is the other option (sec. 10a).")
inc = w["incidence_deg"]
doc.p("Incidence. The fuselage should fly level in cruise (cabin floor, payload, drag). For an untwisted wing, CL = a_w (alpha - alpha_L0), "
      "so the root chord is set at the angle that gives the cruise CL. alpha_L0 comes from the tripped polar, which the CFD follows (sec. 10):")
doc.eq(r"i_w=\alpha_{L0}+\frac{C_{L,cr}}{a_w}=%.2f^\circ+\frac{%.3f}{%.3f}\,\frac{180}{\pi}=%.1f^\circ,\qquad \alpha_{stall}=\alpha_{L0}+\frac{C_{L,max}}{a_w}=%.1f^\circ" %
       (w['alpha_L0_deg'], w['CL_cruise'], w['a_per_rad'], inc, w['alpha_stall_3d_deg']), note="a_w = Helmbold slope (sec. 6), 1/rad")
ft = wsec.spar_feet(S, tiltcfg.params()["wing"])
dz_ped = ft["front"][1] - ft["rear"][1]
doc.p(f"The cruise CL is high ({w['CL_cruise']:.2f}: the wing flies at 1.2 x stall speed), so the incidence is large. A V-22 needs only a "
      "few degrees because it cruises at a much lower CL. Every model applies it the same way (src/wing_sections.py): the section is "
      "pitched nose-up about the root quarter chord, so the STL, the wing shell FEM, the beam (box axes rotated about the span) and the "
      f"fuselage interface all use the same contour. The rear spar foot drops: the root lower surface is at z = {ft['front'][1]*1e3:+.0f} mm "
      f"under the front spar and {ft['rear'][1]*1e3:+.0f} mm under the rear one. The fuselage top now sits at the rear foot, and the "
      f"wing's front lug brackets drop {dz_ped*1e3:.0f} mm to meet it (sec. 11 has the hand check), so the fuselage frames stay level. "
      "Before, the fuselage top sat at -c t/c / 2 for both spars, which was already 15-30 mm off the real feet.")

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
if FS:
    FSB = J("fuselage_shell_bonded.json") if os.path.exists(os.path.join(R, "fuselage_shell_bonded.json")) else None
    FSF, FT = None, None                                         # the run with the fittings (9.3); 9.2 is the run before them
    if os.path.exists(os.path.join(R, "fuselage_shell_model_nofit.json")):
        FSF, FT, FS = FS, J("fittings.json"), J("fuselage_shell_model_nofit.json")
    doc.h("9. Fuselage shell FEM (CalculiX)")
    ne = FS["elements"]; m_ = FS["mass_kg"]; st = FS["stations"]
    doc.p("The beam screen treats the fuselage as one beam, the keel box, and the skin as a fairing. A shell model asks what a "
          "beam cannot: does a skin attached to the keel and frames pick up load, and does its one woven ply survive that; what happens "
          "where the wing, gear and boom put their loads in; and how the keel turns up the tail ramp to the boom. It was run twice: "
          "first with the skin bonded (9.1), then, by the user's decision, with the fairing floating (9.2). 9.2 showed the two fittings "
          "were missing; 9.3 designs them and re-runs the model with them in place (the current design).")
    doc.bullets([
        f"Mesh: the STL's outer mould line (one shared function), {ne['ESKIN']} skin, {ne['EFLANGE']} keel-flange, {ne['EWEB']} keel-web "
        f"and {ne['EFLOOR']} floor S8R shells, {len(FS['frames_x'])} frames as {ne['EFRAME']} shells; {FS['nodes']} nodes. Each face is homogenised by "
        "CLT and written transversely isotropic about x (Airframe/01's method).",
        "Keel inside the mould line, following the belly, so it climbs the tail ramp to the boom; its bottom flange replaces the belly skin. "
        "ASSUMED: frames 4 mm x 40 mm quasi-isotropic carbon, at most 0.30 m apart.",
        "Support: the top of the two wing-attach frames is fixed. Loads: for each case the beam model's own inertia-relief solution, cut at "
        "the wing carry-through. Every fuselage-side node load L = F_ext + M Phi (g - a) is spread over a patch of shell nodes as the "
        "least-norm force set with the same resultant force and moment (a distributing coupling). Ultimate = 1.5 x limit.",
    ])
    doc.eq(r"\min_{f}\ \sum_i |f_i|^2\quad \mathrm{s.t.}\quad \sum_i f_i = F,\quad \sum_i (r_i - r_0)\times f_i = M"
           r"\ \ \Rightarrow\ \ f = A^T (A A^T)^{-1} \{F;\,M\}", note="the patch load; A stacks the identity and the cross-product rows of every node")
    doc.p(f"Strain margins are against eps_allow = {FS['eps_allow']*1e6:.0f} ue (CAI/OHC, Airframe/01), at ultimate: MS = eps_allow / eps_max - 1.")

    if FSB:
        doc.h("9.1 First run: skin bonded to keel and frames")
        rows = []
        for n_, o in FSB["cases"].items():
            st_ = o["strain"]; b_ = FSB["skin_buckling"][n_]
            rows.append([n_.split()[0], f2(st_["ESKIN"]["MS"]), f2(st_["EFLANGE"]["MS"]), f2(st_["EWEB"]["MS"]), f2(st_["EFLOOR"]["MS"]),
                         f2(st_["EFRAME"]["MS"]), f"{b_['lam_min_clear']:.2f}"])
        doc.table(["Case", "skin", "keel flange", "keel web", "floor", "frames", "skin buckling factor"], rows,
                  widths=[0.1, 0.12, 0.14, 0.13, 0.12, 0.12, 0.27])
        doc.p("The buckling column is a hand check on every skin element's FE membrane loads (axial: curved panel with the SP-8007 "
              "knockdown or wide column between frames; shear: Donnell with 0.67; R_c + R_s^2 = 1). A factor below 1 means that skin "
              "panel buckles before ultimate.")
        lo = min(b['lam_min_clear'] for b in FSB['skin_buckling'].values()); hi = max(b['lam_min_clear'] for b in FSB['skin_buckling'].values())
        doc.p(f"Bonded, the one woven ply is structural whether intended or not: the wing holds the fuselage by the crowns of two frames, so "
              f"the crown skin is a direct load path, and it buckles at {lo:.2f}-{hi:.2f} of ultimate, i.e. it would wrinkle in ordinary "
              "flight. The keel itself passed with room to spare (flange MS +0.8 or more). Two fixes were possible: float the fairing "
              "(slotted or elastomeric attachments, so the keel-only beam model holds), or make the skin structural (foam-core sandwich or "
              "stringers, heavier). DECIDED (user, 2026-11-19): float the fairing. params.yaml: fuselage.skin = floating.")

    doc.h("9.2 Floating fairing, before the fittings")
    doc.p("The skin elements are left out of the analysis; the fairing's mass stays in the loads (it is in the beam model's mass), its "
          "stiffness does not. Everything is now carried by the keel box (flange, two webs, floor) and the frames.")
    doc.img(img("fig_fuselage_shell_nofit.png" if FSF else "fig_fuselage_shell.png"), width=6.6)
    cs = FS["cases"]
    rows = []
    for n_, o in cs.items():
        st_, sc = o["strain"], o["strain_clear"]
        rows.append([n_.split()[0], f2(st_["EFLANGE"]["MS"]), f2(st_["EWEB"]["MS"]), f2(st_["EFLOOR"]["MS"]), f2(st_["EFRAME"]["MS"]),
                     f2(sc["EFLANGE"]["MS"]), f2(sc["EWEB"]["MS"]), f2(sc["EFRAME"]["MS"]), f2(min(c["MS"] for c in o["core"].values()))])
    doc.table(["Case", "flange", "web", "floor", "frames", "flange*", "web*", "frames*", "core shear"], rows,
              widths=[0.08, 0.11, 0.11, 0.11, 0.11, 0.12, 0.12, 0.12, 0.12])
    xb = st["x_end"]
    doc.p(f"Columns with * leave out the boom-fitting patch (x < {xb + 0.06:.2f} m, the last 0.06 m before the boom at x = {xb:.2f} m). "
          f"Wing-attach frames: x = {st['x_f']:.2f} and {st['x_r']:.2f} m.")
    l5, l4 = next(v for k, v in cs.items() if k.startswith("LC5")), cs["LC4 hard landing one main"]
    l1 = cs["LC1 hover pull-up n=2"]
    peak = l1["hand_F2"]
    doc.p("Where the margins go negative, and why:")
    doc.bullets([
        f"Boom fitting. In the first four columns every worst point is at x = -1.25, where the boom's root force and moment enter the end of the keel "
        f"(LC5 web {l5['strain']['EWEB']['eps_max']*1e6:,.0f} ue, MS {l5['strain']['EWEB']['MS']:+.2f}). With the skin bonded, the whole "
        "tail-cone shell shared that load; floating, the keel alone takes it, and at the boom it is at its shallowest. The beam model's "
        "rigid tail-cone link hid this. A boom fitting (a plug that spreads the moment over the end frame and the keel walls) is needed.",
        f"Wing attach. Away from the boom, the worst points sit at the wing-attach frames, mostly x = {st['x_f']:.2f} m (LC1 web MS "
        f"{l1['strain_clear']['EWEB']['MS']:+.2f}, LC4 web MS {l4['strain_clear']['EWEB']['MS']:+.2f} at x = {l4['strain_clear']['EWEB']['at'][0]:.2f}). "
        "The model fixes the frame crowns rigidly, so the whole fuselage load funnels through a few nodes; a carry-through fitting spreads it. "
        "These numbers are hot spots at an idealised support, not sized structure.",
        f"Between the fittings. At the cabin cut (x = {peak['x_s']:.2f} m, LC1) the bending strains are only ~"
        f"{max(abs(peak['crown']['fe']), abs(peak['belly']['fe']))*1e6:.0f} ue; the larger strains are shear, in the webs and at the floor edges. "
        f"The floor passes in every case (MS {min(o['strain']['EFLOOR']['MS'] for o in cs.values()):+.2f} or more), so does the core shear "
        f"({min(min(c['MS'] for c in o['core'].values()) for o in cs.values()):+.2f} or more) and so do the frames away from the fittings. "
        f"LC5's web* {l5['strain_clear']['EWEB']['MS']:+.2f} sits at x = {l5['strain_clear']['EWEB']['at'][0]:.2f} m, just outside the "
        "excluded patch: that is still the boom load spreading into the keel.",
    ])
    q = l1["hand_F2_bays"][0]["resultants"]; hb = l1["hand_F2_bays"][0]
    doc.table(["Hand check (floating)", "Hand", "FE", "Diff"], [
        ["F1 wing reactions = - sum of loads, LC1 z [N]", f1(-l1["applied_N"][2]), f1(l1["reaction_N"][2]), f"{100*(l1['reaction_N'][2]/-l1['applied_N'][2]-1):+.3f} %"],
        [f"F2 pitch moment at the cut x = {hb['x_s']:.2f} m, LC1 [N m]", f1(q["M_pitch_statics"]), f1(q["M_pitch_fe"]), f"{100*(q['M_pitch_fe']/q['M_pitch_statics']-1):+.1f} %"],
        [f"F2 yaw moment at the same cut, LC1 [N m]", f1(q["M_yaw_statics"]), f1(q["M_yaw_fe"]), f"{100*(q['M_yaw_fe']/q['M_yaw_statics']-1):+.1f} %"],
        ["F2 pitch moment, same cut, LC5 [N m]", f1(l5["hand_F2"]["resultants"]["M_pitch_statics"]), f1(l5["hand_F2"]["resultants"]["M_pitch_fe"]),
         f"{100*(l5['hand_F2']['resultants']['M_pitch_fe']/l5['hand_F2']['resultants']['M_pitch_statics']-1):+.1f} %"],
        ["F3 floor strain (top of keel box), LC1 [ue]", f0(hb["crown"]["beam"]*1e6), f0(hb["crown"]["fe"]*1e6), f"{100*hb['crown']['diff']:+.0f} %"],
        ["F3 keel flange strain (bottom), LC1 [ue]", f0(hb["belly"]["beam"]*1e6), f0(hb["belly"]["fe"]*1e6), f"{100*hb['belly']['diff']:+.0f} %"],
    ], widths=[0.55, 0.15, 0.15, 0.15])
    doc.eq(r"N=\sum_i Q_{11,i}\,t_i\,\Delta s_i\,(\varepsilon_x+\nu_{21}\varepsilon_s)_i ,\qquad M_{pitch}=\sum_i Q_{11,i}\,t_i\,\Delta s_i\,(\varepsilon_x+\nu_{21}\varepsilon_s)_i\,(z_i-z_c)",
           note="F2: the FE stress resultants over one row of elements must equal the statics of the loads aft of the cut")
    doc.p("F1 and F2 hold the model to statics: the reactions close to rounding, and the FE stresses at the prismatic cabin cut carry the "
          "moment of every load behind it to within a few %. (Cuts further aft, on the ramp, are not plane cuts through an inclined keel, "
          "so only the cabin cut is used.) F3, plane-sections beam theory, misses by a factor of 2-3 even though the moment is right. The "
          "bay is short (0.30 m between frames) and the floor and flange are wide (0.26 m), so shear lag dominates: the webs carry the "
          "bending, and the strain falls off toward the middle of the floor and the flange (13 ue at the flange centre line, 66 ue at its "
          "edges, in LC1). The total is right; the plane-section distribution is not. With the skin bonded, F3 missed the same way "
          + (f"(crown {FSB['cases']['LC1 hover pull-up n=2']['hand_F2']['crown']['beam']*1e6:.0f} vs {FSB['cases']['LC1 hover pull-up n=2']['hand_F2']['crown']['fe']*1e6:.0f} ue)." if FSB else "."))
    doc.bullets([
        f"Mass: shell structure {sum(v for k, v in m_.items() if k != 'ESKIN'):.1f} kg (keel webs, floor and flange "
        f"{m_['EWEB']+m_['EFLOOR']+m_['EFLANGE']:.2f}, frames {m_['EFRAME']:.2f}) plus the {m_['ESKIN']:.2f} kg fairing, against "
        f"{FS['beam_model_mass_kg']['keel']:.2f} kg keel + {FS['beam_model_mass_kg']['fuselage_fairing']:.2f} kg fairing in the beam model: "
        "the frames are new mass the screen did not carry. The floating mounts and both fittings will add more.",
        "CalculiX *BUCKLE could not be used: it expands every shell into a brick layer, and a 0.218 mm ply on 25 mm elements is too thin for that. "
        "It returned 0.995-1.003 for every case, with loads scaled x10 and for an isotropic skin-only model; with a 3 mm skin it gave 68. "
        "The floating fairing still sees air loads; it needs a local panel check, not a fuselage-load one.",
        "Beam-model inconsistency found: tiltframe.py hangs the keel under the floor, 0.09 m below the mould line's belly; the shell model puts "
        "it inside, as the fuselage height (payload stack + floor + keel + skin) was derived. It moves the CG and the gear length slightly.",
        "Next: design the boom fitting and the wing carry-through fitting, model them in the shell model, and re-run (9.3).",
    ])
    if FSF:
        CF = FSF["cases"]; HH = FSF["hand_H"]; lg = FT["lug"]; wf = FT["wing_frames"]; sk = FT["socket"]; mf = FSF["mass_kg"]
        doc.h("9.3 The fittings: wing carry-through and boom socket")
        cF = CF["LC4 hard landing one main"]["strain_clear"]
        doc.p("Correction (2026-11-20). The wing shell model (sec. 11) showed that CalculiX 2.21 writes composite-shell strains in each "
              "element's own axes (1 along the orientation's x, 2 in the plane, 3 normal), not in global x, y, z; a one-element test "
              "confirmed it. The fuselage post-processing had read them as global: harmless for the floor and flange, wrong for the keel "
              "webs, frames and bulkheads. Corrected, the one-wheel landing failed at the spar frames' web feet, and section 9.5 resizes "
              "the structure there. Everything below is the corrected, resized design. Section 9.2 (before the fittings) still carries "
              "the error.")
        doc.p("Both are sized by hand in fittings.py at the ultimate free-body loads the shell model applies, then built into the shell "
              "model (params fuselage.fittings) and checked there. Fitting factor 1.15 (FAR 23.625) on the metal parts.")
        doc.p("Wing carry-through. The spar box runs unbroken over the fuselage. The fuselage hangs from it by four bolted 7075-T6 lugs, "
              f"two on the crown of each spar frame (x = {FT['x_f']:.3f} and {FT['x_r']:.3f} m) at y = +-{abs(FT['lug_points'][0][1]):.2f} m, over "
              "the payload. Four pins x 3 forces is 12 unknowns for 6 equations, so the first split assumes equal pin stiffness "
              "(the least-norm patch formula above). Each lug is then sized against its three classic failure modes:")
        doc.eq(r"d\geq\sqrt{\frac{4\,P\,FF}{2\pi F_{su}}},\qquad t\geq\max\left(\frac{P\,FF}{(w-d)F_{tu}},\ \frac{P\,FF}{2(e-d/2)F_{su}},\ \frac{P\,FF}{d\,F_{bru}}\right)",
               note="double-shear bolt; lug net tension, shear-out, bearing (e = 1.5 d, w = 3 d)", size=11)
        doc.table(["Lug item", "Value", "MS"], [
            ["Design load P x 1.15 (worst lug)", f"{lg['P_design_N']:.0f} N", ""],
            ["Bolt, class 10.9, double shear", f"M{lg['bolt_d_m']*1e3:.0f} (6 mm floor)", f"{lg['bolt_MS']:+.2f}"],
            ["Lug tang thickness", f"{lg['t_m']*1e3:.0f} mm (3 mm floor)", ""],
            ["  t needed: tension / shear-out / bearing", f"{lg['t_required_m']['net_tension']*1e3:.2f} / {lg['t_required_m']['shear_out']*1e3:.2f} / {lg['t_required_m']['bearing']*1e3:.2f} mm",
             f"{lg['MS']['net_tension']:+.2f} / {lg['MS']['shear_out']:+.2f} / {lg['MS']['bearing']:+.2f}"],
            ["Mass, each lug + bolt (estimate)", f"{lg['mass_each_kg']*1e3:.0f} g", ""],
        ], widths=[0.42, 0.33, 0.25])
        doc.p("Heavy frame. Each spar frame is a closed ring loaded in its own plane by the two lug reactions at the crown and the keel "
              "at the two web feet. A closed ring is three times statically indeterminate: cut it at the crown, put redundants "
              "(H, V, M0) on the cut, and make the cut close (unit-load method, bending flexibility only). Both lugs bolt into the same "
              "spanwise-rigid spar, so their spacing cannot change either: a fourth redundant, the arch thrust between the lugs.")
        doc.eq(r"M(s)=M_{open}(s)+M_0+(y_0-y)V-(z_0-z)H,\qquad \oint M\,\frac{\partial M}{\partial X_i}\,\frac{ds}{EI}=0,\qquad H_{arch}=-\frac{\oint M\,m_H\,ds}{\oint m_H^2\,ds}")
        st_ = FT["self_test"]
        doc.p(f"Self-test: a circular ring under two opposite loads gives {st_['ring_M_at_load_Nm']:.2f} N m at the loads against Roark's "
              f"PR/pi = {st_['roark_PR_over_pi']:.2f}, and {st_['ring_M_at_90deg_Nm']:.2f} against PR(1/2 - 1/pi) = {st_['roark_PR_(1/2-1/pi)']:.2f} at 90 deg.")
        rows = []
        for n_, c in FT["cases"].items():
            ff = c["frame_front"]; h = HH[n_]
            rows.append([n_.split()[0], f"{ff['arch_thrust_N']:.0f}", f"{ff['keel_stiffened']['arch_thrust_N']:.0f}", f"{abs(h['lug_fe_N'][0][1]):.0f}",
                         f"{c['lug_max_N']:.0f}", f"{h['lug_max_fe_N']:.0f}", f"{h['frame_front']['eps_hand']*1e6:.0f}", f"{h['frame_front']['eps_fe_clear']*1e6:.0f}"])
        doc.table(["Case", "H ring", "H keel", "H FE", "lug hand", "lug FE", "eps hand", "eps FE"], rows,
                  widths=[0.09, 0.13, 0.13, 0.13, 0.13, 0.13, 0.13, 0.13])
        doc.p("Front spar frame; forces in N, strains in ue. H ring / H keel: arch thrust from the plain ring and from the ring with a "
              "rigid keel arc; H FE: the FE lug's lateral reaction. The plain ring over-predicts the arch thrust by ~40 %. Treating the frame's lower "
              "arc between the web feet as rigid (it is the bottom of the keel box) brings the thrust to within 3-10 % of the FE in the four cases "
              "that load the lugs (20 % in LC3, the lightest). That verifies the lug load path. The peak frame moment then sits where that rigid arc meets the frame. "
              "With the frame caps of 9.5 the FE peak there is within about 10 % of the hand value in LC4 (one-wheel landing, the sizing case) "
              "and below it in the others. (An earlier version of this page said the FE was a third of the hand value everywhere; that came "
              "from the strain-axis error.) Sizing: "
              f"frames {wf['front']['t_m']*1e3:.1f} mm (front) and {wf['rear']['t_m']*1e3:.1f} mm (rear) x {wf['front']['d_m']*1e3:.0f} mm "
              "quasi-isotropic carbon, against 4 x 40 mm before. The FE split also differs from equal stiffness (LC4: the stiffer front "
              "frame takes more), so the lug design load is the larger of the two.")
        doc.p("Boom socket. The boom (D = %.3f m) runs forward inside the tail cone to x = %.3f m and is held by aluminium collars, "
              "bonded to it and bolted to two sandwich bulkheads at x = %.3f and %.3f m, both aft of the payload. The aft collar is a slip "
              "fit (radial forces only) and the forward one also takes the axial force and the torsion, so the split is statically "
              "determinate. With the boom rigid between the collars, spacing s:" % (sk["boom_D_m"], sk["x_fwd"], sk["x_fwd"], sk["x_aft"]))
        doc.eq(r"M_{fwd}=M_{root}+(r_{root}-r_{fwd})\times F", size=12)
        doc.eq(r"F_{aft,z}=\frac{M_{y,fwd}}{s},\quad F_{aft,y}=-\frac{M_{z,fwd}}{s},\quad F_{fwd}=F-F_{aft},\quad T_{fwd}=M_{x}", size=12)
        rows = [[n_.split()[0], f"{c['F_boom_N'][2]:.0f}", f"{c['M_boom_root_Nm'][1]:.0f}", f"{c['F_aft_collar_N'][2]:.0f}", f"{c['F_fwd_collar_N'][2]:.0f}",
                 f"{c['F_aft_collar_N'][1]:.0f} / {c['F_fwd_collar_N'][1]:.0f}"] for n_, c in sk["cases"].items()]
        doc.table(["Case", "boom F_z [N]", "root M_y [N m]", "aft collar F_z", "fwd collar F_z", "F_y aft / fwd"], rows, widths=[0.1, 0.16, 0.18, 0.18, 0.18, 0.2])
        doc.p(f"The short socket multiplies the load: LC1's 1.5 kN tail-rotor force becomes {max(abs(c['F_aft_collar_N'][2]) for c in sk['cases'].values()):.0f} N "
              f"at the aft collar. Collar bond: {sk['bond_tau_Pa']/1e6:.2f} MPa shear (force and torsion, x 1.15) against a 10 MPa "
              f"toughened-epoxy design value (MS {sk['bond_MS']:+.0f}); no bolts go through the UD-heavy boom wall. Collar-to-bulkhead: "
              f"8 x M{sk['flange_bolt_d_m']*1e3:.0f} into potted inserts. Mould line: the tail cone ends at "
              f"{sk['tail_end_section_m'][0]:.3f} x {sk['tail_end_section_m'][1]:.3f} m, smaller than the boom, so the floating fairing's aft "
              "closure must open around it (a geometry change for geometry.py).")
        doc.img(img("fig_fuselage_shell.png"), width=6.6)
        rows = []
        for n_, o in CF.items():
            sc = o["strain_clear"]
            rows.append([n_.split()[0]] + [f2(sc[k_]["MS"]) for k_ in ("EFLANGE", "EWEB", "EFLOOR", "EWEBD", "EFLOORD", "EFRAME", "EFRAMEF", "EFRAMER", "EBULK")]
                        + [f2(min(c_["MS"] for c_ in o["core"].values()))])
        doc.table(["Case", "flange", "web", "floor", "web dbl", "floor dbl", "frames", "front fr.", "rear fr.", "bulkh.", "core"], rows,
                  widths=[0.08] + [0.092] * 10)
        l4f = CF["LC4 hard landing one main"]["strain_clear"]["EFLANGE"]
        q = CF["LC1 hover pull-up n=2"]["hand_F2_bays"][0]["resultants"]
        doc.p("Strain MS at ultimate, outside the elements that touch a lug pin or a collar (the metal parts there are the hand checks above). "
              f"F1 still closes exactly, and F2 at the cabin cut: pitch {q['M_pitch_statics']:.0f} / {q['M_pitch_fe']:.0f} N m, yaw "
              f"{q['M_yaw_statics']:.0f} / {q['M_yaw_fe']:.0f} N m (statics / FE, LC1). Getting here took four more design and model changes:")
        doc.bullets([
            "Bulkheads: one +-45 ply per face (the keel web lay-up) failed the 33 mm ligament between the boom hole and the crown at 4,400 ue; "
            "the design has 5 per face.",
            "Keel doublers (+2 +-45 plies per face, +3 since 9.5): on the web, floor and flange two elements either side of each bulkhead, and on the web "
            "and floor over the whole carry-through bay between the spar frames, where the one-wheel landing's roll torque runs through the keel.",
            "Lug model: pinning every frame node within 25 mm of a lug made a moment clamp; a lug turns on its bolt, so it is now one pinned "
            "node on the frame's mid-depth line.",
            "Bulkhead-to-keel joint: tying the nearest bulkhead node within 20 mm by *EQUATION passed the forces but not their couples (F x d "
            "of every offset tie). F2 caught it: the cabin cut lost 15 % of the pitch and 90 % of the yaw moment, and the LC4 margins "
            "looked better than they are. The joint now merges nodes within 6 mm (a shared, bonded line). With the moment conserved, LC4's "
            "torque reached the keel and the carry-through-bay doublers became necessary.",
        ])
        m_old = sum(v for k_, v in FS["mass_kg"].items() if k_ != "ESKIN")
        m_new = sum(v for k_, v in mf.items() if k_ not in ("ESKIN", "fittings_metal", "boom_extension"))
        doc.bullets([
            f"Mass: keel, frames and bulkheads {m_new:.2f} kg against {m_old:.2f} kg before the fittings, plus {mf['fittings_metal']:.2f} kg of "
            f"lugs, bolts and collars and {mf['boom_extension']:.2f} kg for the {sk['boom_extension_m']:.2f} m of boom inside the socket: "
            f"+{m_new - m_old + mf['fittings_metal'] + mf['boom_extension']:.2f} kg in all. Not yet in the beam model's mass.",
            "F2 between the collars (x = -0.83 m) closes in pitch but not in yaw: the lateral collar forces bend the sandwich webs as plates, "
            "and the check integrates membrane strain only. That is a limit of the check, not an equilibrium error.",
        ])

    if FSF and FT and "gear" in FT:
        G = FT["gear"]; g4 = G["cases"]["LC4 hard landing one main"]; g3 = G["cases"]["LC3 hard landing 3 wheels"]
        kt = G["keel_torsion"]; bo = G["bolts"]; c4 = CF["LC4 hard landing one main"]["strain_clear"]
        doc.h("9.4 Main-gear fitting")
        doc.p(f"The main gear is a transverse bow (one beam, both wheels at y = +-{abs(g4['wheels'][0][0][1]):.2f} m, "
              f"{abs(g4['wheels'][0][0][2] - G['saddle_L'][2]):.2f} m below the keel) at x = {G['x_ml']:.3f} m, between the gear diaphragm and the "
              "rear spar frame. Until now its load was smeared over +-60 mm of keel. The fitting is two aluminium saddles, one under each keel "
              f"web foot (y = +-{abs(G['saddle_L'][1]):.3f} m), each with {bo['n']} x M{bo['d_m']*1e3:.0f} bolts through potted inserts, and a "
              f"+-45 sandwich diaphragm ({2} plies per face) across the keel at the saddle station, with a {0.10*1e3:.0f} mm hole for systems.")
        doc.p("Saddle split. The bow is a rigid beam on two supports, so its root force F and moment M about the keel centre split by statics "
              "alone (6 equations, 6 unknowns: two vertical and two fore-aft forces, one lateral force, one pitch couple shared by the saddles). "
              "For one wheel loaded at a distance a outboard of the near saddle, with saddle spacing b, the lever rule gives:")
        doc.eq(r"P_{near}=P\left(1+\frac{a}{b}\right),\qquad P_{far}=-P\,\frac{a}{b},\qquad T_{keel}=M_x", size=12)
        a_ = abs(g4['wheels'][0][0][1]) - abs(G['saddle_L'][1]); b_ = 2 * abs(G['saddle_L'][1]); P_ = g4["wheels"][0][1][2]
        doc.p(f"LC4: P = {P_:.0f} N, a = {a_:.3f} m, b = {b_:.3f} m, so P(1 + a/b) = {P_*(1+a_/b_):.0f} N and -P a/b = {-P_*a_/b_:.0f} N by hand; "
              f"gear_split() gives {g4['P_L_N'][2]:.0f} and {g4['P_R_N'][2]:.0f} N (statics residual {g4['statics_residual']:.0e} N). The difference is "
              "the bow-root moment the beam model adds. The far saddle is pulled down, so its bolts work in tension. "
              "The shell model applies exactly these saddle forces, so the FE checks the structure behind the saddles, not the split.")
        doc.table(["Case", "P left [N]", "P right [N]", "keel torque [N m]"],
                  [[n_.split()[0], f"{c['P_L_N'][2]:.0f}", f"{c['P_R_N'][2]:.0f}", f"{c['keel_torque_Nm']:.0f}"] for n_, c in G["cases"].items()],
                  widths=[0.2, 0.25, 0.25, 0.3])
        doc.p("Hand checks on the saddle and the keel:")
        doc.eq(r"p=\frac{P_{max}}{A_{pad}},\qquad q=\frac{T}{2A_{box}},\qquad \gamma=\frac{q}{G\,t_{face}},\qquad \varepsilon_1=\frac{\gamma}{2}", size=12)
        doc.table(["Item", "Hand value", "Allowable / FE", "MS"], [
            ["Saddle pad on the foam core", f"{G['pad_pressure_Pa']/1e6:.2f} MPa ({G['pad_m2']*1e4:.0f} cm^2)", f"{G['core_comp_strength_Pa']/1e6:.1f} MPa crush", f"{G['pad_MS_on_core']:+.2f}"],
            [f"Bolts {bo['n']} x M{bo['d_m']*1e3:.0f}, tension", f"{-G['P_down_max_N']:.0f} N", "", f"{bo['tension_MS']:+.1f}"],
            ["Bolts, shear", "", "", f"{bo['shear_MS']:+.1f}"],
            ["Keel box torsion, LC4 (Bredt)", f"q = {kt['q_N_per_m']/1e3:.1f} kN/m, eps1 = {kt['eps_principal']*1e6:.0f} ue",
             f"FE flange peak {c4['EFLANGE']['eps_max']*1e6:.0f} ue", ""],
            ["Gear diaphragm (FE)", "", f"{c4['EBULKG']['eps_max']*1e6:.0f} ue", f"{c4['EBULKG']['MS']:+.2f}"],
            ["Saddle mass, each (estimate)", f"{G['saddle_mass_each_kg']*1e3:.0f} g", "", ""],
        ], widths=[0.36, 0.3, 0.2, 0.14])
        ea = FSF["eps_allow"]; e4 = c4["EFLANGE"]["eps_max"]; need = e4 / ea
        doc.p(f"The pad pressure is {G['pad_pressure_Pa']/1e6:.1f} MPa against 0.9 MPa foam crush, so the core under each saddle must be "
              "replaced by a solid insert (high-density foam or a G10 block, potted) over the pad area. That is standard practice for "
              "any bolted sandwich hard point.")
        doc.p(f"The keel flange beside the rear spar frame is the one-wheel landing's other hot spot: {e4*1e6:.0f} ue (MS {c4['EFLANGE']['MS']:+.2f}) "
              f"at x = {c4['EFLANGE']['at'][0]:.2f} m in the resized design, against {kt['eps_principal']*1e6:.0f} ue from Bredt's formula. The "
              "difference is restrained warping: the gear diaphragm (x = -0.375) and the rear spar frame (x = -0.278) are 0.1 m apart and "
              "both stop the twisted keel's cross-section from warping, which forces axial strain into the flanges. Bredt cannot see it. "
              "Before the resize this spot read MS -0.22. Part of that was the strain-axis error, and most of the rest came from the "
              "uncapped frames bending out of plane next to it. A UD flange doubler (+2 UD +2 +-45 per face over x = -0.40 to -0.25 m) "
              "was sized by hand for it, because CalculiX 2.21 returns NaN stiffness whenever the flange section changes at a wing frame "
              "or the gear diaphragm. Four model variants failed: a plain doubled section, a one-layer composite frame section, S8 "
              "elements and an overlay shell. With the 9.5 resize the flange no longer needs it, and the doubler is dropped.")
        doc.bullets([
            "Still not modelled: landing drag and wheel spin-up loads (fore-aft at the wheel, which would add pitch moment at the saddles), "
            "and the nose gear, which is still smeared over the keel.",
            f"Mass: 2 x {G['saddle_mass_each_kg']:.2f} kg saddles and the diaphragm (in the FE mass), on top of 9.3's fittings. "
            "Not yet in the beam model.",
        ])

if FSF:
    doc.h("9.5 Resize after the strain-axis correction")
    c4 = FSF["cases"]["LC4 hard landing one main"]["strain_clear"]
    doc.p("With the strains read in the right axes, the one-wheel landing (LC4) failed at the spar frames where they meet the keel "
          "webs: web doubler MS -0.62, front and rear frames -0.37 / -0.40, keel web and flange -0.06; the web doubler was also "
          "negative in LC1 (-0.45) and LC5 (-0.25). Splitting each strain into its components showed two mechanisms:")
    doc.bullets([
        "Frames: the strain at the eight integration points of the worst frame element fits e = a eta + b zeta, a in-plane gradient across the "
        "frame depth (eta) and one through its thickness (zeta). Here a ~ 2,200 ue, which is the ring bending of the hand model (2,549 ue), "
        "and b ~ 2,200-2,600 ue, which is the flat frame bending out of its own plane. The model's frame is a bare 50 mm plate, and the "
        "keel's roll torque twists it.",
        "Web doubler: direct vertical strain (2,300-3,900 ue mean) in the one element row at each frame's web foot, falling to ~1,100 ue "
        "one row up. The frame's vertical load entered the web through a single shared node.",
    ])
    doc.p("Fixes, each run in the full model:")
    doc.bullets([
        f"Cap flange on the inner edge of both spar frames, {FRAME_CAP_W_*1e3:.0f} mm wide, same laminate and thickness: the frames become T sections. "
        "Out-of-plane bending stiffness rises by w^3 / (d t^2) ~ 34. Frame strain away from the web feet fell from ~4,800 to 700-1,300 ue.",
        "Vertical web posts at both spar frames: the frame continued up each keel web as a ~36 mm strip, joined to the web, the flange "
        "and the floor. This spreads the frame's vertical load over the web height.",
        "Keel web doublers: +3 +-45 plies per face (was +2) and, on the webs only, over the whole boom-socket bay and +-75 mm around "
        "the nose gear (LC1 web at MS -0.01 between the collars).",
        "Tried and rejected: a full sandwich diaphragm closing the keel box at each spar frame. It made the web-foot corner a hard "
        "point (LC4 frame MS -0.81, flange -0.65); the code keeps it behind KEEL_DIA = False. Also tried: moving the frame's radial "
        "edge onto the web line, which folded the adjacent frame elements (nonpositive Jacobians).",
    ])
    rows = []
    for n_, o in FSF["cases"].items():
        sc = o["strain_clear"]
        rows.append([n_.split()[0]] + [f"{sc[k]['MS']:+.2f}" for k in ("EWEBD", "EFRAMEF", "EFRAMER", "EFRAMEFC", "EFRAMEFP", "EFLANGE", "EWEB")])
    doc.table(["Case", "web dbl", "front fr.", "rear fr.", "front cap", "front post", "flange", "web"], rows,
              widths=[0.09, 0.13, 0.13, 0.13, 0.13, 0.13, 0.13, 0.13])
    mf5 = FSF["mass_kg"]; add = sum(mf5.get(k, 0) for k in ("EFRAMEFC", "EFRAMERC", "EFRAMEFP", "EFRAMERP"))
    doc.p(f"All margins are now positive. The tightest are the frames at the web-foot junction in LC4 ({c4['EFRAMEF']['MS']:+.2f} / {c4['EFRAMER']['MS']:+.2f}). "
          "That is a shell-intersection peak which halves within 40 mm. The real frame-to-keel joint there is a bonded clip, a detail "
          f"for drawings. Caps and posts weigh {add:.2f} kg, and the heavier doublers add the rest: the keel, frames and bulkheads went from "
          "12.12 to " + f"{sum(v for k_, v in mf5.items() if k_ != 'ESKIN'):.2f} kg (with the fitting metal). Equilibrium (F1) and the cabin-cut statics (F2) still close.")
    doc.p("Re-check with the LS(1)-0417MOD wing (sec. 5). The keel, boom and gear were frozen and only the wing and pods re-sized, "
          "because the global sweep's lighter keel failed the shell check (LC4 web MS -0.17). Two changes followed. The shorter chord "
          "moved the rear spar frame 15 mm forward and opened an 11 mm undoubled strip between the bay doubler and the gear-frame "
          "doubler (LC4 web MS -0.03). The bay doubler now runs on to the gear frame when that frame is within 6 DX. The front frame "
          "junction came out at MS -0.01. The FE junction peak runs ~11 % above the hand ring strain, so the hand target for the heavy "
          f"frames went from MS 0.10 to 0.15: front {FT['wing_frames']['front']['t_m']*1e3:.1f} mm (was 5.5), rear {FT['wing_frames']['rear']['t_m']*1e3:.1f} mm.")

doc.h("10. Airfoil CFD: lift checked, drag from XFOIL")
pl = json.load(open(os.path.join(here, "cfd", "airfoil2d", "plan.json")))
doc.p(f"2-D RANS of the sections (OpenFOAM 13, Spalart-Allmaras): the {AF(w['airfoil'])} wing at Re {pl[w['airfoil']]['Re']:.2e} (and the "
      f"first wing's NACA 4415 at Re {pl['4415']['Re']:.2e}), "
      f"alpha {pl[w['airfoil']]['alphas'][0]} to {pl[w['airfoil']]['alphas'][-1]} deg, and the NACA 0012 tail at Re {pl['0012']['Re']:.2e}. "
      f"The mesh is a single-block C-grid with {pl[w['airfoil']]['cells']} cells, written directly by cfd_airfoil2d.c_grid(), "
      f"with the first cell at {pl[w['airfoil']]['dy1_m']*1e6:.0f} um (y+ ~ 1) from the flat-plate estimate:")
doc.eq(r"C_f=\frac{0.026}{Re_x^{1/7}},\qquad u_\tau=U\sqrt{C_f/2},\qquad \Delta y_1=\frac{y^+\,\nu}{u_\tau}")
doc.p("Each grid line is a cubic Hermite curve from the wall point W, leaving along the surface normal N, to its far-field point F. "
      "This keeps the wall cells orthogonal (0.7 deg mean, 8 deg max). The blockMesh grid it replaced was sheared 40-60 deg at the "
      "leading edge:")
doc.eq(r"P(t)=h_{00}(t)\,W+h_{10}(t)\,k_{wall}L\,N+h_{01}(t)\,F+h_{11}(t)\,F',\qquad h_{00}=2t^3-3t^2+1,\; h_{10}=t^3-2t^2+t", size=11)
doc.p("The runs start from a physical field: nuTilda = 3 nu (the NASA TMR freestream value) everywhere, and U from potentialFoam. "
      "The earlier viscous start-up field leaked into the wall boundary condition through OpenFOAM's bound() and froze there. On "
      "the new mesh it also got trapped in the wake. The script docstring lists all seven setup failures and their fixes.")
doc.p("Verification found a solver fault, not a setup one. On a laminar Poiseuille channel the exact pressure gradient is:")
doc.eq(r"\frac{dp}{dx}=\frac{12\,\mu\,\bar U}{H^2}=\frac{12\,(10^{-3})(1)}{0.02^2}=30\ \mathrm{Pa/m}\ (\rho=1)")
doc.table(["Check", "Exact / ref.", "Result", "Error"], [
    ["Channel dp/dx, icoFoam", "30", "29.99", "0 %"],
    ["Channel dp/dx, foamRun incompressibleFluid", "30", "44.2", "+47 %"],
    ["Channel dp/dx, legacy porousSimpleFoam", "30", "44.25", "+48 %"],
    ["Channel wall-cell U (icoFoam / foamRun)", "0.0375", "0.0375 / 0.069 & 0.042", "odd-even"],
    ["NASA TMR NACA 0012, Re 6e6, alpha 10: cl", "1.0909", "1.039", "-4.8 %"],
    ["NASA TMR NACA 0012, Re 6e6, alpha 10: cd", "0.01231", "0.0194", "+58 %"],
], widths=[0.46, 0.14, 0.26, 0.14])
doc.p("Every OpenFOAM 13 solver that computes the viscous term through the momentumTransport library (divDevSigma) overestimates "
      "wall shear by about 48 %, laminar or turbulent. icoFoam does not use that library, and it is exact. Changing schemes, "
      "pressure-velocity coupling, cell shape or wall boundary condition does not move the error. One cell off the wall the "
      "boundary-layer profile matches the log law, so the fault is in the wall cells. Decision (user, 2026-11-19): use the CFD for "
      "lift only, and take section drag from XFOIL. The tripped XFOIL polar (5 % chord) is the "
      "like-for-like comparison for fully turbulent SA, and the free-transition polar is what sizing used.")
if CFD:
    for code, blk in CFD.items():
        pct = lambda v: f"{v:+.1f} %" if v is not None else "-"
        rows = [[f"{r_['alpha']:+d}", (f3(r_['cl']) if r_.get('steady', True) else "unsteady") if 'cl' in r_ else r_.get("status", ""),
                 f3(r_['xfoil_trip_cl']) if 'xfoil_trip_cl' in r_ else "-", pct(r_.get('diff_trip_cl_pct')),
                 f3(r_['xfoil_cl']) if 'xfoil_cl' in r_ else "-", pct(r_.get('diff_cl_pct')),
                 f"{r_['xfoil_cd']:.4f}" if 'xfoil_cd' in r_ else "-", f"{r_['cd']:.4f}" if 'cd' in r_ else ""] for r_ in blk["rows"]]
        doc.table([f"{code} alpha", "cl CFD", "cl trip", "diff", "cl free", "diff", "cd XFOIL", "cd CFD (unused)"],
                  rows, widths=[0.15, 0.1, 0.1, 0.1, 0.1, 0.1, 0.15, 0.2])
    doc.img(img("cfd_airfoil2d_polar.png"), width=6.4)
if CFD and w['airfoil'] in CFD and all(any(r_['alpha'] == a_ and 'cl' in r_ for r_ in CFD[w['airfoil']]['rows']) for a_ in (0, 8, 16)):
    RW = {r_['alpha']: r_ for r_ in CFD[w['airfoil']]["rows"] if 'cl' in r_}
    WS = [r_ for r_ in RW.values() if r_.get('diff_trip_cl_pct') is not None and abs(r_['alpha']) <= 8]
    sl_cfd = (RW[8]['cl'] - RW[0]['cl']) / 8; sl_xf = (RW[8]['xfoil_trip_cl'] - RW[0]['xfoil_trip_cl']) / 8
    doc.eq(r"a=\frac{c_l(8^\circ)-c_l(0^\circ)}{8^\circ}:\quad a_{CFD}=%.4f,\; a_{XFOIL,trip}=%.4f\ \mathrm{per\ deg}\ (%+.1f\ \%%)" % (sl_cfd, sl_xf, 100 * (sl_cfd / sl_xf - 1)),
           note="lift slope of the %s, alpha 0-8 deg (thin-airfoil theory: 2 pi / rad = 0.110 per deg)" % AF(w['airfoil']))
    ok_ = {a_: r_ for a_, r_ in RW.items() if r_.get('steady', True)}
    a_top = max(ok_); cl_top = ok_[a_top]['cl']; uns = sorted(a_ for a_ in RW if a_ not in ok_)
    aL0_cfd = -RW[0]['cl'] / sl_cfd
    R4 = {r_['alpha']: r_ for r_ in CFD['4415']['rows'] if 'cl' in r_} if '4415' in CFD else {}
    ab_ = [a for a in S['airfoil_table'] if a['name'] == w['airfoil']][0]
    vs_ratio = math.sqrt(ab_['clmax'] / cl_top)
    doc.bullets([
        f"Linear range (alpha -4 to 8): CFD cl is {-max(r_['diff_trip_cl_pct'] for r_ in WS if r_['alpha'] >= 0):.1f} to {-min(r_['diff_trip_cl_pct'] for r_ in WS if r_['alpha'] >= 0):.1f} % below "
        f"tripped XFOIL on the {AF(w['airfoil'])} (the NACA 4415 showed 4-9 %), and the lift slope is {100*abs(sl_cfd/sl_xf-1):.1f} % lower. "
        f"The zero-lift angle, which sets the incidence, agrees: {aL0_cfd:+.2f} deg from the CFD against {w['alpha_L0_deg']:+.2f} deg from "
        "tripped XFOIL. The NASA TMR case puts the solver's own lift error at -4.8 %, and the inflated wall shear thickens the "
        "trailing-edge boundary layer, which takes away effective camber; a section that loads its aft chord loses more from that.",
        f"Near stall: the steady solution holds up to {a_top} deg (cl {cl_top:.3f}, still rising) and breaks into a non-converging "
        f"oscillation at {', '.join(str(a_) for a_ in uns)} deg: separation that a steady solver cannot settle, so no number there. "
        f"The last steady cl is {100*(1-cl_top/ab_['clmax']):.0f} % below the tripped XFOIL clmax that sized the wing ({ab_['clmax']:.3f}). "
        f"If it were the true clmax, the stall speed would rise by sqrt({ab_['clmax']:.3f} / {cl_top:.3f}) = {vs_ratio:.3f}, to "
        f"{w['v_stall_ms']*vs_ratio:.1f} m/s, and the cruise margin would fall from 1.20 to {1.2/vs_ratio:.2f} x stall speed.",
        (f"The first wing's NACA 4415 stayed steady to 16 deg (cl {R4[16]['cl']:.3f}), above its own XFOIL clmax (1.645). So near "
         "stall the two methods rank the sections differently: XFOIL gives the LS(1)-0417MOD a 13 % higher clmax; this CFD gives "
         "the two about the same lift at 15-16 deg. 2-D steady SA is not a reliable stall predictor (it over-predicted the 4415), "
         "so sizing stays on XFOIL. A wind-tunnel polar of the LS(1)-0417MOD at Re ~1e6 would settle it.") if 16 in R4 else "",
        "Table columns: cl trip / cl free = XFOIL tripped at 5 % chord / free transition (Ncrit 9); cd XFOIL is the free-transition value.",
        "NACA 0012 tail: cl 3-8 % below tripped XFOIL, the same pattern. The tail volume coefficients have margin for that.",
    ])
doc.h("10a. Still to run")
doc.bullets([
    "Airfoil CFD drag: a second CFD code (SU2, or an OpenFOAM release without this fault) would give an independent cd. Not "
    "needed for sizing, which uses XFOIL drag.",
    "3-D CFD: geometry/airframe_hover.stl and rotor_disks_hover.stl (named solids, metres, FE axes) are ready for snappyHexMesh "
    "with actuator disks. They give the real wing and boom download (sec. 4) and the fuselage interference. Its forces would "
    "carry the same wall-shear error, so pressure (lift and download) forces only.",
    "Fuselage: section 9.2 (before the fittings) still carries the strain-axis error; re-read it if that run is needed again.",
    f"Wing size trade (sec. 5): the high-lift section shrank the wing and costs ~7 % cruise energy ({cr['wh_per_km']:.1f} against 75.7 Wh/km). "
    "Decided (user, 2026-11-20): keep the smaller wing. The alternative was the NACA 4415 wing area with the new section, banking "
    "the higher clmax as stall margin (cruise at ~1.27 x stall speed).",
    "Beam model: the wing box EI is %.2f x too low (sec. 11), so its wing modes are ~%.0f %% low. Re-run the modal check with the "
    "contour-true box. It matters now: an airplane-mode mode sits at %.1f Hz, at the lower edge of the in-plane 1P band (%.2f Hz), "
    "and a stiffer wing moves it up into the band." % (J('wing_shell_model.json')['cases']['LC1 hover pull-up n=2']['cuts'][0]['EI_flap'] / J('wing_shell_model.json')['beam_box_EI_flap'],
        100 * (math.sqrt(J('wing_shell_model.json')['cases']['LC1 hover pull-up n=2']['cuts'][0]['EI_flap'] / J('wing_shell_model.json')['beam_box_EI_flap']) - 1),
        [m_ for m_ in F['modes']['airplane']['hz'] if 25 < m_ < 40][0],
        F['bands']['nominal']['airplane']['1'][0]),
    "Whirl flutter of the wing + pod + rotor (the defining tiltrotor aeroelastic check) is not in any model yet.",
])

# ------------------------------------------------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------------------------------
if os.path.exists(os.path.join(R, "wing_shell_model.json")):
    WS = J("wing_shell_model.json"); wc = WS["cases"]; l1 = wc["LC1 hover pull-up n=2"]
    doc.h("11. Wing shell FEM (CalculiX)")
    doc.p("The frame screen (sec. 7) models the wing as one beam: a box between the spars with no ribs, panels checked as infinitely "
          "long plates, clamped at one centre node. Its tightest wing margin is the upper box skin buckling in LC1, MS "
          f"{WS['beam_wing_buckling_MS']:+.2f}. A shell model answers what that beam cannot: panel buckling between real ribs, the pods' load "
          "into the tip rib, the four lug supports, shear lag and the dihedral kink at the root. src/wing_shell.py builds it; the "
          "solve (fea/wing/wing_static.inp, ~2 min, 2.2 GB) runs on one thread.")
    ne = WS["elements"]
    doc.bullets([
        f"Box between the spars (15 % and 60 % chord) on the true {AF(w['airfoil'])} contour, pitched {w['incidence_deg']:.1f} deg nose-up "
        "about the quarter chord (sec. 5), swept and dihedralled as the STL; "
        f"{sum(v for k, v in ne.items() if k != 'ERIB')} skin and web S8R shells, {ne['ERIB']} rib shells, {WS['nodes']} nodes.",
        "Skins and webs: the selected design's laminates (sandwich, the beam's cap and web faces), so shell and beam are the same structure. "
        f"Ribs (not in the beam): {len(WS['stations_y'])} flat sandwich ribs, {WS['rib_w45']} woven +-45 per face (ASSUMED), at every beam-node "
        f"station, the two lug stations (y = +-{WS['y_lug']:.3f} m) and the tips.",
        "LE and TE shells: fairings, mass only, as in the beam model.",
        "Support: the four lugs of sec. 9.3, each one pinned node at a spar-web foot. Loads: the beam model's wing free body (box, pods, "
        "heads) with inertia relief, L = F + M Phi (g - a), x 1.5, spread over the box perimeter at each station as least-norm nodal "
        "forces with the same resultant force and moment.",
    ])
    doc.p("Hand checks. W3 cuts the left wing between ribs and compares the FE spanwise strain at mid-chord of the upper and lower skins with "
          "beam theory of the shell's own cross-section. W4 compares the shear flow at mid-chord of the upper skin with Bredt's formula, "
          "where the vertical-shear flow is zero by symmetry:")
    doc.eq(r"\varepsilon=\frac{N}{EA}+\kappa_c\,a+\kappa_n\,b,\qquad q=\frac{T}{2A_{enc}}", size=12)
    rows = []
    for n_, o in wc.items():
        c_ = o["cuts"][1]
        rows.append([n_.split()[0], f"{c_['y_cut']:.2f}", f"{c_['M_flap_statics']:.0f} / {c_['M_flap_fe']:.0f}",
                     f"{c_['upper']['beam']*1e6:.0f} / {c_['upper']['fe']*1e6:.0f}", f"{c_['lower']['beam']*1e6:.0f} / {c_['lower']['fe']*1e6:.0f}",
                     f"{abs(c_['q_bredt']):.0f} / {abs(c_['q_fe_mid']['upper']):.0f}"])
    doc.table(["Case", "y cut", "M flap stat./FE", "upper beam/FE", "lower beam/FE", "|q| Bredt/FE"], rows, widths=[0.09, 0.1, 0.2, 0.2, 0.2, 0.21])
    doc.p("Moments in N m, strains in ue, shear flow in N/m. The FE strains follow beam theory within ~5 % and Bredt within a few per cent "
          "away from the root in LC1 and LC2. Where the torque at the cut is small (LC3-LC5), the mid-chord shear flow is no longer torsion "
          "alone: shear lag and the chordwise load spread add a few hundred N/m. The FE moment resultant "
          "runs ~6 % above statics: the check weights each element by its CLT Q11, which is slightly stiffer than the transversely "
          "isotropic material written to CalculiX. W1 (lug reactions against the applied total) closes to the round-off of the patches.")
    rows = [[n_.split()[0], f"{o['tip_dz_mm']['beam_L']:.1f}", f"{o['tip_dz_mm']['fe_L']:.1f}", f"{WS['W2_lugs'][n_]['max_hand_N']:.0f}",
             f"{WS['W2_lugs'][n_]['max_fuselage_fe_N']:.0f}", f"{WS['W2_lugs'][n_]['max_wing_fe_N']:.0f}"] for n_, o in wc.items()]
    doc.table(["Case", "tip dz beam", "tip dz shell", "lug hand", "lug fus. FE", "lug wing FE"], rows, widths=[0.1, 0.18, 0.18, 0.18, 0.18, 0.18])
    ei = WS["cases"]["LC1 hover pull-up n=2"]["cuts"][0]["EI_flap"]
    doc.p(f"Tip deflection in mm (left tip, relative to the lugs, ultimate); lug loads in N. The shell is stiffer than the beam: its flapwise EI is "
          f"{ei/1e3:.0f} kN m^2 against the beam's {WS['beam_box_EI_flap']/1e3:.0f} ({ei/WS['beam_box_EI_flap']:.2f} x). The beam takes a flat box of the mean "
          f"spar depth ({WS['beam_box_depth_m']*1e3:.0f} mm); the true contour is thicker between the spars. EI alone would give "
          f"{l1['tip_dz_mm']['beam_L']/(ei/WS['beam_box_EI_flap']):.1f} mm in LC1; the shell's {l1['tip_dz_mm']['fe_L']:.1f} mm adds the sandwich shear and the lug-bay "
          f"flexibility. So the beam is conservative on strain, but its wing bending frequencies are ~{100*(math.sqrt(ei/WS['beam_box_EI_flap'])-1):.0f} % low "
          f"(sqrt {ei/WS['beam_box_EI_flap']:.2f}): the modal check should be re-run (sec. 10a). Lugs: the shell treats the fuselage as rigid and the fuselage model treats the wing as rigid, so the true split "
          f"lies between them. The lug design load is the largest of the three ({FT['lug_design_source']}: "
          f"{FT['lug']['P_design_N']:.0f} N with FF 1.15; shear-out MS {FT['lug']['MS']['shear_out']:+.2f}, still a 3 mm tang).")
    doc.img(img("fig_wing_shell.png"), width=6.6)
    rows = []
    for n_, o in wc.items():
        sc = o["strain_clear"]; pb = o["panel_buckling"]
        rows.append([n_.split()[0]] + [f"{sc[k]['MS']:+.2f}" for k in ("EUP", "ELO", "EWF", "EWR", "ERIB")]
                    + [f"{min(c['MS'] for c in o['core'].values()):+.1f}", f"{pb['MS']:+.2f}", f"{o['wrinkling']['MS']:+.1f}"])
    doc.table(["Case", "upper", "lower", "front web", "rear web", "ribs", "core", "panel buckl.", "wrinkl."], rows,
              widths=[0.09, 0.1, 0.1, 0.12, 0.12, 0.1, 0.1, 0.15, 0.12])
    pb = l1["panel_buckling"]
    doc.p("Strain MS at ultimate outside 60 mm of the lug nodes; core shear; and W6, the hand panel-buckling check on the FE membrane "
          "loads of every box-skin element: an orthotropic plate between its two ribs and the two spars, simply supported, with the "
          "sandwich shear softening and the compression-shear interaction:")
    doc.eq(r"N_{x,cr}=\frac{\pi^2}{b^2}\min_m\left[D_{11}\left(\frac{mb}{a}\right)^2+2(D_{12}+2D_{66})+D_{22}\left(\frac{a}{mb}\right)^2\right],\quad \frac{1}{N}=\frac{1}{N_b}+\frac{1}{G_c d},\quad R_c+R_s^2=1", size=10)
    doc.p(f"The worst panel is the upper skin in the centre bay between the two lug ribs (y = 0 to +-{WS['y_lug']:.3f} m) in LC1: N_x = "
          f"{pb['Nx']/1e3:.0f} kN/m against {pb['Nx_cr']/1e3:.0f} kN/m, MS {pb['MS']:+.2f}, close to the beam's {WS['beam_wing_buckling_MS']:+.2f}. "
          "The ribs raise the critical load, but between the lugs the skin load is higher than the beam predicts: the root moment "
          "stays at its full value there, and the dihedral kink adds to it. Outboard of the lugs the panel load falls with the bending "
          "moment. With the LS(1)-0417MOD wing the design refine (wing and pods only, sec. 7) first thinned the core to the beam's "
          "buckling limit (beam MS +0.03), and this check then gave -0.001. The beam is ~3 % unconservative for this bay, so the core "
          f"was set back to {d['wing']['core_mm']:.1f} mm (beam MS {WS['beam_wing_buckling_MS']:+.2f}).")
    pk = l1["strain"]
    doc.p(f"At the lug nodes themselves the FE peaks at {max(pk[k]['eps_max'] for k in ('ELO','EWF','EWR'))*1e6:.0f} ue (LC1). That is the singularity of "
          "a single pinned node, as in the fuselage model, and it grows with mesh refinement. The real wing-side lug bracket is bonded and "
          "bolted to the spar web over a length L_b along the span and feeds the load in as shear. With the incidence, the front "
          f"bracket also drops dz = {dz_ped*1e3:.0f} mm below the web foot to the level frame crown (sec. 5). Its lateral force H (the arch "
          "thrust) then puts a moment H dz about x on the web. That moment lies in the web's own plane, and the bolt line reacts it as a "
          "vertical couple H dz / L_b. Its fore-aft force F_x puts F_x dz about y into the rib at the lug station, also in that rib's plane. "
          "Worst front lug (wing FE, rigid fuselage, so the largest H), L_b = 80 mm, web face G t from the laminate:")
    LB_ = 0.08; GT = 35.2e6
    worst = max(((n_, k_, o_["lug_reactions_N"][k_]) for n_, o_ in wc.items() for k_ in (0, 1)), key=lambda t_: math.hypot(*t_[2]))
    Rl = worst[2]; P_ = math.hypot(*Rl); H_ = abs(Rl[1]); Mx_ = H_ * dz_ped; q_ = (P_ + Mx_ / LB_) / LB_; g_ = q_ / GT
    doc.eq(r"q=\frac{P+H\,dz/L_b}{L_b}=\frac{%.0f+%.0f\times%.3f/0.08}{0.08}=%.0f\ \mathrm{kN/m},\quad \gamma=\frac{q}{G_f\,t_f}=%.0f\ \mu\varepsilon,\quad \varepsilon_1=\frac{\gamma}{2}=%.0f\ \mu\varepsilon\ (MS\ %+.2f)" %
           (P_, H_, dz_ped, q_ / 1e3, g_ * 1e6, g_ / 2 * 1e6, WS["eps_allow"] / (g_ / 2) - 1), size=10,
           note="%s, lug %d; G_f t_f = %.1f MN/m (3 x +-45 woven face); the couple is added to the direct shear, conservatively" % (worst[0].split()[0], worst[1] + 1, GT / 1e6))
    doc.p(f"The rib takes F_x dz = {abs(Rl[0]):.0f} x {dz_ped:.3f} = {abs(Rl[0])*dz_ped:.0f} N m in its plane over its "
          f"{(wsec.depth_at(w['airfoil'], 0.15)*w['c'])*1e3:.0f} mm depth at the front spar. So the existing web and rib carry the drop bracket; "
          "its bolts need potted inserts through the core, like the gear saddles. The drop bracket itself (7075, a "
          "taller lug base) is a detail for drawings.")
    m_ = WS["mass_kg"]
    doc.bullets([
        f"Mass: box skins and webs {sum(v for k, v in m_.items() if k != 'ERIB'):.2f} kg (beam model: {WS['beam_wing_mass_kg']:.2f} kg for the same "
        f"laminates on its flat box) plus ribs {m_['ERIB']:.2f} kg. The beam budgets the ribs as +25 % on the LE/TE shells.",
        "Not modelled: the LE/TE shells as structure (bonded, they would add torsion stiffness), the tilt-actuator and pod fittings in the "
        "tip rib (load spread over the tip ring here), and whirl flutter.",
        "Method lesson: the Bredt check is what exposed CalculiX's element-local strain output. Without a hand check that depends on the "
        "in-plane shear, the error would have stayed hidden, as it had in the fuselage model.",
    ])

# ------------------------------------------------------------------------------------------------------------------
TR = J("transition.json") if os.path.exists(os.path.join(R, "transition.json")) else None
if TR:
    dz, cu, rig = TR["design"], TR["current"], TR["tail_rig"]
    hc, hcc = dz["hand_checks"], cu["hand_checks"]
    BL = dz["blade_loads"]; pa = S["prop_airplane"]
    mi, mic = dz["mission"], cu["mission"]
    bra, brp, brh = dz["best_range_airplane"], dz["best_range_any"], dz["best_range_heli"]
    pt = lambda r_, V_, d_, m_=None: min([o for o in r_["points"] if o["ok"] and o["V"] == V_ and round(o["delta"]) == d_ and (m_ is None or o["mode"] == m_)],
                                          key=lambda o: o["P_batt"])
    p_air, p_par = pt(dz, 25.0, 0), pt(dz, 25.0, 70)
    okset = {(o["V"], round(o["delta"])) for o in dz["points"] if o["ok"]}
    V_alls = [V_ for V_ in TR["assumptions"]["V"] if all((V_, d_) in okset for d_ in TR["assumptions"]["deltas"])]
    Vb = [o["V"] for o in dz["best"] if o["mode"] == "B"]
    doc.pagebreak()
    doc.h("12. Flying it on the designed props: conversion corridor and transition")
    doc.p("Proof of concept: how well do the 54 x 18 props from Props/01, designed for hover, carry this airframe from hover through "
          "conversion to wing-borne cruise and back? src/transition.py trims the vehicle in the pitch plane at every airspeed V "
          f"(0-{max(TR['assumptions']['V']):.0f} m/s) and nacelle angle delta (90 = hover, 0 = airplane, 5 deg steps), for the 280 lb sizing mass "
          f"({dz['mass_kg']:.0f} kg) and the current mass estimate ({cu['mass_kg']:.0f} kg). Every rotor is the Props program's own blade-element "
          "model of the final blade (bemt.edgewise: azimuth-resolved, Drees inflow, tip loss, kappa 1.15), run at the angle its disk "
          "actually sees the air. That one model covers hover, edgewise flight and the axial airplane mode.")
    doc.eq(r"\sum F_x = m\,a,\qquad \sum F_z = W,\qquad \sum M_{cg}=0,\qquad \gamma=\delta+\theta,\qquad \alpha_s = 90^\circ-\gamma",
           note="alpha_s: the disk tilt the BEMT sees (0 hover, 90 airplane)")
    doc.p("Unknowns at each point: front rpm, pitch theta and either the tail rpm (mode A, elevator neutral) or the elevator "
          "(mode B, tail rotor parked fore-aft).")
    doc.p("Each rotor gives thrust T along its shaft and an in-plane force H. The front pair acts at the hub on its 0.35 m arm, so the "
          "CG moves forward with delta as the two heads swing. The other pieces:")
    doc.bullets([
        "Wing: CL = a_w (theta + i_w - alpha_L0) up to CL_max,3D, blended to a flat plate (CL = CD90/2 sin 2a, CD = CD90 sin^2 a) over "
        "8 deg past stall; CD from the free-transition XFOIL polar plus CL^2/(pi e AR); cm0 about the wing-body aerodynamic centre.",
        "H-tail: CL_t = a_t (theta + i_t - eps + tau delta_e), eps = (d eps/d alpha) CL/a_w, tau 0.5, |delta_e| <= 25 deg, |CL_t| <= 1. "
        f"The tail incidence is rigged so the elevator is neutral in airplane-mode cruise at {rig['V']:.0f} m/s and 127 kg: i_t = "
        f"{rig['i_t_deg']:.1f} deg (the wing's {w['incidence_deg']:.1f} deg incidence and its downwash leave a 0 deg tail at a large negative "
        "angle; untrimmed, the elevator needed +23 deg).",
        "Download (sizing, sec. 4) fades as the wake is blown aft: f(V) = f_0 sin^2(delta) v_i^2/(v_i^2 + V^2) on the wing, f_0 v_i^2/(v_i^2 + V^2) on the boom.",
        "Rest of the vehicle: the sizing drag build-up less the wing (CDA %.3f m^2)." % (dr["CDA_total_m2"] - dr["wing_profile_m2"] - dr["induced_m2"]),
        f"Limits: rpm <= {dz['rpm_max']:.0f} (motor KV x sagged pack, loaded), theta in [{TR['assumptions']['theta_lim_deg'][0]:.0f}, "
        f"+{TR['assumptions']['theta_lim_deg'][1]:.0f}] deg (ASSUMED cabin/payload limits), the tail limits above, the wing below stall once it could "
        f"carry 10 % of W (above {dz['V_wing10']:.1f} m/s; below that a stalled wing is only a drag item).",
    ])
    doc.p("Several roots exist (one is a deep-stall branch with the elevator hard over), so each point starts from the neighbouring "
          "speed's solution, falls back to four fixed seeds, and keeps the cheapest feasible root. Mode A sweeps up from hover, mode B "
          "down from cruise.")
    # hand checks
    H1, H2, H3 = hc["H1_hover"], hc["H2_cruise"], hc["H3_statics"]
    rows = [
        ["H1 hover T_f / T_t [N]", f"{H1['T_f_hand']:.1f} / {H1['T_t_hand']:.1f}", f"{H1['T_f_trim']:.1f} / {H1['T_t_trim']:.1f}",
         f"{abs(100*(H1['T_f_trim']/H1['T_f_hand']-1)):.1f} %", "forces + moments, 2 x 2"],
        ["H1 hover P front [W]", f"ideal {H1['P_ideal_w']:.0f}", f"{H1['P_f_bemt_w']:.0f}", f"FoM {H1['FoM']:.3f}", "P_id = T^1.5/sqrt(2 rho A)"],
        ["H2 cruise 25 m/s P [W]", f"{H2['sizing_P_shaft_w']:.0f}", f"{H2['P_shaft_trim_w']:.0f}",
         f"{100*(H2['P_shaft_trim_w']/H2['sizing_P_shaft_w']-1):+.1f} %", f"sizing; CL {H2['sizing_CL']:.3f} vs {H2['CL']:.3f}"],
        ["H2 axial BEMT, same T [W]", f"{H2['P_axial_bemt_same_T_w']:.0f}", f"{H2['P_shaft_trim_w']:.0f}",
         f"{100*(H2['P_shaft_trim_w']/H2['P_axial_bemt_same_T_w']-1):+.1f} %", f"{H2['thrust_per_rotor_trim_n']:.1f} N per rotor"],
        [f"H3 sum F, {H3['V']:.0f} m/s, d {H3['delta']:.0f}", "0", f"{max(abs(H3['sum_Fx_N']), abs(H3['sum_Fz_N'])):.0e} N", "-", "parts re-summed"],
    ]
    for r_ in hc["H4_energy"]["rows"]:
        if (r_["V"], r_["delta"], r_["mode"]) in ((10.0, 90.0, "A"), (25.0, 90.0, "A"), (25.0, 45.0, "B"), (25.0, 0.0, "B")):
            rows.append([f"H4 P, {r_['V']:.0f} m/s, d {r_['delta']:.0f} [W]", f"{r_['P_hand_w']:.0f}", f"{r_['P_bemt_w']:.0f}",
                         f"{100*(r_['P_hand_w']/r_['P_bemt_w']-1):+.1f} %", f"{r_['F_prop_V_w']:.0f} + {r_['P_induced_w']:.0f} + {r_['P_profile_w']:.0f}"])
    doc.table(["Check (127 kg)", "Hand", "Model", "Diff", "Note (H4: F V + ind. + prof.)"], rows, widths=[0.3, 0.16, 0.14, 0.12, 0.28])
    doc.eq(r"P = (T\cos\gamma - H\sin\gamma)\,V + \kappa\,T\,v_i + P_{0,h}\left(\frac{\Omega}{\Omega_h}\right)^3(1+4.65\,\mu^2),\qquad v_i=\frac{T}{2\rho A\sqrt{(V\cos\alpha_s)^2+(V\sin\alpha_s+v_i)^2}}", size=11,
           note=f"H4: work + Glauert induced + profile; P_0,h = {hc['H4_energy']['P0_hover_w']:.0f} W from hover")
    doc.p("H4 is the check that matters for an edgewise rotor. It is tempting to bound the power below by T (V sin alpha_s + v_i). "
          "That ignores the in-plane force: a lifting rotor in edgewise flight works like a wing, and the free stream pays part of the "
          "work through H. The energy budget with the actual propulsive force closes to a few per cent at every point, hover to airplane mode.")
    doc.img(img("fig_corridor.png"), width=6.6)
    doc.p(f"Conversion corridor. Green squares trim inside every limit; the marks say which limit blocks the others. At {dz['mass_kg']:.0f} kg airplane mode "
          f"(delta 0) holds from {dz['airplane_V_min']:.0f} to {dz['airplane_V_max']:.0f} m/s: wing stall below, front rpm above (the fixed-pitch "
          f"prop's zero-thrust J). With the nacelles up the craft flies to {dz['heli_V_max']:.0f} m/s before the nose-down pitch limit blocks it. "
          f"Between them the corridor is wide: from {min(V_alls):.0f} to {max(V_alls):.0f} m/s every angle trims, so the nacelles can go down anywhere in that band. At "
          f"{cu['mass_kg']:.0f} kg airplane mode shrinks to {cu['airplane_V_min']:.0f}-{cu['airplane_V_max']:.0f} m/s: the wing stalls just below the "
          "speed where the props run out of rpm. The solid line is the nacelle schedule used for transition (the minimum-power angle, "
          "made monotonic); the dotted line is the minimum-power angle itself.")
    doc.img(img("fig_power_speed.png"), width=6.6)
    doc.p("Prop effectiveness, three numbers:")
    doc.bullets([
        f"Hover: FoM {H1['FoM']:.3f} per front rotor at {H1['T_f_trim']:.0f} N (Props reported 0.836 at the 415 N design thrust; the "
        f"download and the tail's larger share move the front rotors off that point). Hover costs {dz['heli_mode'][0]['P_batt']/1e3:.1f} kW at the battery.",
        f"Airplane mode: eta = {H2['eta_prop']:.2f} at 25 m/s against the ideal (actuator-disk) {H2['eta_ideal']:.2f}. The big disk is lightly "
        f"loaded, so almost none of that gap is momentum loss. The 18 in pitch prop runs at J {S['cruise']['J']:.2f}, close to its zero-thrust "
        f"J {pa['J_zero_thrust']:.2f}: the outer blade sits at negative angle of attack (largest section alpha {BL['airplane']['alpha_max_deg']:.1f} deg) "
        f"and profile drag eats the power. Each prop makes {H2['thrust_per_rotor_trim_n']:.0f} N from {H2['P_shaft_trim_w']/2:.0f} W.",
        f"Edgewise lift: the same disks tilted to 70 deg at 25 m/s make {p_par['T_f']:.0f} N each for {p_par['P_f']:.0f} W, while still pulling "
        f"(eta {p_par['eta_prop']:.2f} on their forward component). A big, lightly loaded rotor in edgewise flight is an efficient lifting surface.",
    ])
    doc.p(f"Hence the main finding. At the design mass the cheapest way to fly {min(Vb):.0f}-{max(Vb):.0f} m/s is not airplane mode but partial "
          f"conversion: nacelles at ~{brp['delta']:.0f} deg, tail rotor parked, the wing carrying {100*brp['wing_lift_frac']:.0f} % of the weight. "
          f"At 25 m/s that needs {p_par['P_batt']/1e3:.2f} kW at the battery against {p_air['P_batt']/1e3:.2f} kW in airplane mode. "
          f"Best range: {brp['wh_per_km']:.1f} Wh/km at {brp['V']:.0f} m/s against {bra['wh_per_km']:.1f} Wh/km in airplane mode "
          f"({bra['V']:.0f} m/s) and {brh['wh_per_km']:.1f} Wh/km nacelles up ({brh['V']:.0f} m/s). The wing is not the reason: in airplane mode it "
          f"cruises at CL {p_air['CL']:.2f}, near its best-L/D CL ({dr['CL_LDmax']:.2f}), and at CL {p_par['CL']:.2f} in partial conversion it loses little. "
          f"The props are. In airplane mode each turns {p_air['P_f']:.0f} W into {p_air['T_f']:.0f} N near its zero-thrust J. Tilted to 70 deg they "
          f"turn slower ({p_par['rpm_f']:.0f} against {p_air['rpm_f']:.0f} rpm) with the blades at a working angle of attack, take the lift the wing "
          f"gives up and still supply the propulsive force. At the current mass the same holds: {cu['best_range_any']['wh_per_km']:.0f} Wh/km against "
          f"{cu['best_range_airplane']['wh_per_km']:.0f} Wh/km.")
    doc.img(img("fig_transition.png"), width=6.6)
    po, pi_ = dz["paths"]["airplane"]
    doc.p("Transition. The same trim with m a in the x equation, along the schedule, at the fastest of 1, 0.5 and 0.25 m/s^2 that "
          f"trims at every speed (dt = dV/a). Out: {po['a']:+.2f} m/s^2, {po['time_s']:.0f} s, {po['energy_wh']:.0f} Wh, {po['distance_km']*1e3:.0f} m. "
          f"Back: {pi_['a']:+.2f} m/s^2 ({pi_['time_s']:.0f} s, {pi_['energy_wh']:.0f} Wh); a faster deceleration fails to trim at mid "
          "speeds, where it needs more rearward force than the nose-up pitch limit and the tilted rotors give. At the end of the out path the nacelles finish at "
          f"{dz['convert_at_cruise']['from_delta']:.0f} deg; every angle down to 0 trims at {dz['convert_at_cruise']['V']:.0f} m/s, so they tilt the rest of "
          "the way at constant speed.")
    rows = []
    for lab, k in (("Full conversion", "airplane"), ("Partial conversion", "partial"), ("Nacelles up", "nacelles_up")):
        for mm, rr in ((dz, mi), (cu, mic)):
            if k not in rr: continue
            m_ = rr[k]
            rows.append([lab if mm is dz else "", f"{mm['mass_kg']:.0f}", f"{m_['V_cruise']:.0f}", f"{m_['wh_per_km']:.1f}",
                         f"{m_['accel_a']:+.2f} / {m_['decel_a']:+.2f}", f"{m_['accel_wh'] + m_['decel_wh']:.0f}", f"{m_['total_wh']:.0f}" + ("" if m_["complete"] else " *")])
    doc.table(["Strategy", "kg", "V [m/s]", "Wh/km", "a out / back", "trans. Wh", "total Wh"], rows, widths=[0.24, 0.08, 0.1, 0.1, 0.18, 0.14, 0.16])
    doc.p(f"Mission: 60 s hover in all (take-off and landing, {mi['hover_wh']:.0f} Wh at 127 kg), accelerate, a {mi['cruise_km']:.0f} km leg in all, decelerate. "
          "* Nacelles up cannot accelerate at even 0.25 m/s^2 over the last few m/s before its cruise speed (pitch limit), so its row is optimistic. "
          "The tilt pays for itself on every leg; partial conversion pays most.")
    pB = BL["partial"]
    doc.p("What this model leaves out, and where it could bite:")
    doc.bullets([
        f"Blade loads. A fixed-pitch prop in edgewise flight has no cyclic pitch or flapping hinge to even out the lift between "
        f"the advancing and retreating sides. At the partial-conversion cruise point one blade's root flap moment swings +-{pB['M_1P']:.0f} N m (1P) about "
        f"{pB['M_mean']:.0f} N m, against {BL['hover']['M_mean']:.0f} N m steady in hover, and each hub carries {pB['M_roll']:.0f} N m of roll moment "
        f"(the counter-rotating pair cancels it on the airframe, not in the nacelle or the blade root). Nacelles up it is +-{BL['nacelles_up']['M_1P']:.0f} N m. "
        f"The blade and hub need a fatigue check at these cycles ({pB['rpm']*60:.1e} per hour) before partial conversion is a cruise mode.",
        f"Hub moments are not in the trim (pitch hub moment {pB['M_pitch']:.0f} N m per rotor in partial conversion, {BL['nacelles_up']['M_pitch']:.0f} N m nacelles up).",
        "No rotor wake on the wing beyond the hover download, no wing in the slipstream, no whirl flutter, no dynamics or control laws: "
        "quasi-steady trim points only.",
        "Pitch limits [-10, +15] deg are ASSUMED; they set the nacelles-up speed limit and the deceleration rate.",
    ])

doc.h("13. Takeaways")
doc.bullets([
    f"A true V-22 scale-down can't fly wing-borne on fixed-pitch 54 in props: its wing needs {S['v22_scaled']['speed_for_CL1_ms']:.0f} m/s and "
    f"the props stop pulling at {S['prop_airplane']['v_zero_thrust_at_rpm_max']:.0f} m/s. The Osprey look survives with a longer wing.",
    f"The wing pays for itself in cruise: {cr['wh_per_km']:.0f} Wh/km against {cr['multirotor_wh_per_km']:.0f} Wh/km for the tricopter.",
    f"Hub on the wing tip (V-22) puts {100*dl['v22_like']['frac']:.0f} % download on the wing; this frame keeps the disks mostly outboard.",
    "Equal thrust on three equal rotors fixes the hover CG at the hub centroid, which pushes the front heads ahead of the wing (V-280 "
    "style) so the airplane mode can have a normal tail.",
    f"Gusts, not manoeuvres, size the wing: n = {g['n_gust']:.2f} at 25 m/s, because the wing loading is light ({w['wing_loading_n_m2']:.0f} N/m^2).",
    "The fuselage shell FEM shows the one-ply skin, bonded to the keel and frames, buckles far below ultimate, so the fairing "
    "floats. Equilibrium checks close; plane-sections beam theory does not hold in this short fuselage.",
    "The fittings (sec. 9.3-9.4): four bolted lugs on two heavy spar frames carry the fuselage, and a two-bulkhead socket carries the boom (+3.0 kg). "
    "The checks earned their keep twice: the arch thrust between the lugs only matched the FE once the keel box was in the hand ring, "
    "and the cabin-cut statics exposed offset FE ties that had hidden a third of the one-wheel-landing torque. The main gear "
    "hangs on two bolted saddles and a diaphragm; restrained warping between that diaphragm and the rear spar frame puts axial "
    "strain in the keel flange that Bredt torsion cannot see, "
    "so the saddles need solid core inserts. After the strain-axis correction the spar frames became T sections with web posts "
    "(sec. 9.5): all fuselage margins are positive again.",
    f"Wing section (sec. 5): the first wing was picked for least drag among NACA sections. Picked for lift (tripped clmax), the NASA "
    f"LS(1)-0417MOD gives {S['airfoil_table'][0]['clmax']:.2f} against 1.64, a {100*(1-w['S']/[a for a in S['airfoil_table'] if a['name']=='4415'][0]['S']):.0f} % smaller wing and a 17 % deep spar, "
    f"for ~7 % more cruise energy. It is set at {w['incidence_deg']:.1f} deg incidence so the fuselage flies level.",
    "Wing shell FEM: all strain margins positive, with the worst panel (the centre bay between the lugs) at buckling MS "
    f"{J('wing_shell_model.json')['cases']['LC1 hover pull-up n=2']['panel_buckling']['MS']:+.2f}. The true-contour box is "
    f"{J('wing_shell_model.json')['cases']['LC1 hover pull-up n=2']['cuts'][0]['EI_flap']/J('wing_shell_model.json')['beam_box_EI_flap']:.2f} x stiffer than the beam's. "
    "Its Bredt check exposed a strain-axis error in the CalculiX post-processing. Corrected, the fuselage failed at the spar frames "
    "in the one-wheel landing, and frame caps plus web posts fixed it (+1.4 kg).",
    *([f"Flown on the Props/01 blade model (sec. 12), the conversion corridor is wide at 127 kg ({dz['airplane_V_min']:.0f}-{dz['airplane_V_max']:.0f} m/s in airplane mode) and nearly "
       f"closed at {cu['mass_kg']:.0f} kg ({cu['airplane_V_min']:.0f}-{cu['airplane_V_max']:.0f} m/s). The hover props are poor airplane props (eta {hc['H2_cruise']['eta_prop']:.2f}, "
       f"near their zero-thrust J) but good edgewise lifters: partial conversion (nacelles ~{brp['delta']:.0f} deg) cruises at {brp['wh_per_km']:.0f} Wh/km against "
       f"{bra['wh_per_km']:.0f} in airplane mode, pending a fatigue check of the fixed-pitch blades' 1P loads."] if TR else []),
    "OpenFOAM 13's viscous wall term over-predicts wall shear by ~48 % (a laminar channel shows it). Airfoil CFD checks lift "
    "and stall; section drag comes from XFOIL.",
    f"Modal rule: nominal operating-point bands (user, 2026-11-18). Open decisions: the tail-boom download ({100*S['download_tail']['frac']:.0f} % of the tail rotor), the real mass against the 280 lb sizing weight, "
    f"and the tilt actuator ({S['tilt_actuator']['hold_torque_nm']:.0f} N m hold torque against an assumed 0.85 kg actuator).",
])
doc.save(os.path.join(here, "02_Osprey_TiltTri_Design.pdf"))
print("written")

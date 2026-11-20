"""Frame finite-element screen of the Osprey-style tilt-HEX, in both flight modes (Airframe 02's model, six rotors).

Reuses Airframe/01's beam FE (frame_fem.Model: Timoshenko 12-DOF frame elements, consistent mass, inertia relief,
free-free modes), its thin-walled sections (sections.py) and its laminate theory and allowables (materials.py).

Structure (x forward, y left, z up; origin at the wing root quarter-chord on the spar-box axis):
  * wing: one carbon spar box (front spar 15 % c, rear spar 60 % c, depth from the NACA 4415 contour), continuous tip
    to tip over the fuselage, forward sweep and dihedral from the V-22. Sandwich webs, UD caps tapering to the tip.
    The leading- and trailing-edge shells outside the box are fairings (mass only).
  * pods: a fixed carbon tube from each wing-tip spar out to the tilt pivot; a pylon tube from the spar box forward to
    each inboard pivot. Every rotor head (MN1123 motor, mount, blades, hub) sits on a rigid mast above its pivot in
    hover and ahead of it in airplane mode.
  * fuselage keel: a closed box along the cabin floor. The payload stack, battery and avionics ride on it; the
    wing carry-through bolts to it on two frames (one rigid link, the fuselage frames are not modelled).
  * tail boom: a carbon tube from the keel's aft end to the H-tail, with a cross-beam tube carrying the two aft rotors.
  * tricycle gear: a nose leg and two main legs (V-22 sponsons), each with a shock strut (Airframe/01 model).
  * fairings, wing LE/TE shells, H-tail and fins: mass only, plus a non-optimum factor on all members.

Load cases (limit; ultimate = 1.5 x limit):
  hover  LC1 pull-up n = 2 (six thrusts: the least change from equal thrust that zeroes pitch and roll about the CG)
         LC2 one tip rotor at its thrust ceiling, the others at W/6
         LC3 hard landing on all three wheels, LC4 on one main wheel (Airframe/01 energy method)
  plane  LC5 symmetric gust / manoeuvre at n = max(FAR 23.341 gust, 2.5): elliptic wing lift + trimming tail load,
         thrust = drag at the hubs, prop torque
Checks (same as Airframe/01): ply strain vs. the CAI/OHC allowable, local buckling, shaft tilt at LC1, landing stroke,
and the modes against the rotor 1P / 2P bands (hub-moving modes only). A mode BELOW the lowest band is allowed here
(a 6.6 m tiltrotor cannot be stiffer than 1P; the V-22's wing modes are below 1P too) if it is above f_soft_min, and
is flagged for the whirl-flutter check, which this model does not do.
"""
import copy, math, os, sys, time
import numpy as np
from tiltcfg import params, af01_params, jload, RESULTS, AF01, PROPS, G0, LB
import materials as mat
import sections as sx
import wing_sections as wsec
from frame_fem import Model
import airframe as af01                                   # landing_case, gear_section, keel_section

DEFAULT = {
    "wing": {"n_w45": 2, "n_ud_root": 8, "n_ud_tip": 2, "core_mm": 6.0},
    "pod": {"n_w45": 2, "n_ud": 2},
    "keel": {"depth": 0.16, "width": 0.30, "n_w45": 1, "n_ud": 3, "core_mm": 6.0},
    "boom": {"D": 0.12, "n_w45": 2, "n_ud": 4},
    "xbeam": {"D": 0.06, "n_w45": 2, "n_ud": 4},
    "gear": {"D": 0.040, "n_w45": 1, "n_ud": 6, "absorber_mm": 80.0, "main_track": 0.90, "main_dx": -0.25,
             "nose_dx_from_nose": -0.25, "clearance": 0.15},
}
F_SOFT_MIN = 4.0      # Hz, assumption: >= 4 x a ~1 Hz attitude-loop bandwidth for a vehicle this size


def merge(base, over):
    d = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict): d[k].update(v)
        else: d[k] = v
    return d


class Rigid:
    mass_per_m = 0.0; theta_p = 0.0; EA = 1.0; EIyy = EIzz = 1.0; EIyz = 0.0; GJ = 1.0


def naca4_half_thickness(tc, x):
    return 5 * tc * (0.2969 * math.sqrt(x) - 0.1260 * x - 0.3516 * x ** 2 + 0.2843 * x ** 3 - 0.1036 * x ** 4)


_SEC = {}


def cached(key, fn):
    """Sections depend only on their inputs; the sweep rebuilds the same ones thousands of times."""
    if key not in _SEC: _SEC[key] = fn()
    return _SEC[key]


def wing_box(pm, sz, n_ud, wd):
    return cached(("wing", n_ud, wd["n_w45"], wd["core_mm"]), lambda: _wing_box(pm, sz, n_ud, wd))


def _wing_box(pm, sz, n_ud, wd):
    """Spar box between the spars: depth = mean of the contour thickness at the two spars minus the skin."""
    w = sz["wing"]; c = w["c"]
    xf, xr = pm["wing"]["spar_front_xc"], pm["wing"]["spar_rear_xc"]
    depth = c * (wsec.depth_at(w["airfoil"], xf) + wsec.depth_at(w["airfoil"], xr)) / 2 - 0.004   # mean spar depth - skins
    width = (xr - xf) * c
    kd = pm["materials"]["shell_knockdown"]
    side = mat.wall(pm, n_w45=wd["n_w45"], core_t=wd["core_mm"] * 1e-3)
    cap = mat.wall(pm, n_ud0=n_ud, n_w45=wd["n_w45"], core_t=wd["core_mm"] * 1e-3)
    return sx.box(depth, width, side, cap, knockdown=kd)


def tube(pm, D, n_w45, n_ud):
    return cached(("tube", round(D, 5), n_w45, n_ud), lambda: sx.circle(D, mat.wall(pm, n_ud0=n_ud, n_w45=n_w45), knockdown=pm["materials"]["shell_knockdown"]))


def context():
    """Everything the model needs that does not change between designs."""
    p = params(); a1 = af01_params()
    pm = copy.deepcopy(a1); pm["loads"].update(p["loads"])        # materials, structure, absorber from Airframe/01
    pm["wing"] = p["wing"]; pm["modal"].update(p["modal"])
    sz = jload(os.path.join(RESULTS, "sizing.json"))
    req01 = jload(os.path.join(AF01, "results", "requirements.json"))
    p2 = jload(os.path.join(PROPS, "results", "phase2.json"))
    rpm_h = sz["rotor"]["hover_rpm"]                                  # hex rotor, MTOW hover, hot day (sizing.py, Props entry 46)
    # rotor-head masses: the hex motor from the Props entry-46 row; ESC scaled (Props coax_esc_mass_scale); blades,
    # hub and mount as Airframe/01 (54 in class)
    hm = dict(a1["masses"]); hm["motor_kg"] = sz["motor"]["motor_kg"]; hm["esc_kg"] = a1["masses"]["esc_kg"] * p["rotors"]["esc_mass_scale"]
    tf_ = trans_rpm()
    return {"p": p, "a1": a1, "pm": pm, "sz": sz, "req01": req01, "rpm_hover": rpm_h, "hm": hm,
            "rpm_cruise": tf_ or rpm_h, "rpm_cruise_source": "transition.json best-range point" if tf_ else "hover rpm (no trim yet)",
            "thrust_cap": sz["rotor"]["thrust_cap_n"]}


def trans_rpm():
    """Front-rotor rpm at the forward-flight trim's best-range point (transition.py), if it has been run."""
    f = os.path.join(RESULTS, "transition.json")
    if not os.path.exists(f): return None
    J = jload(f)
    b = J.get("design", {}).get("best_range_any")
    return b.get("rpm_f") if b else None


def build(ctx, d, mode="hover", x_payload=None):
    p, a1, pm, sz = ctx["p"], ctx["a1"], ctx["pm"], ctx["sz"]
    ms, nac = ctx["hm"], p["nacelle"]
    w, L, st, fu = sz["wing"], sz["layout"], sz["stability"], sz["fuselage"]
    b, c = w["b"], w["c"]
    R = a1["vehicle"]["rotor_radius_m"]
    tsw, tdi = math.tan(math.radians(-w["sweep_deg"])), math.tan(math.radians(w["dihedral_deg"]))
    x_spar = -c * ((p["wing"]["spar_front_xc"] + p["wing"]["spar_rear_xc"]) / 2 - 0.25)   # box centre rel. to qc
    M = Model(); Rg = Rigid()
    info = {"design": d, "mode": mode, "struct_extra": {}}

    # ---- wing spar box, 12 elements per side, caps taper root -> tip
    nseg = 12
    y_in = L["y_inboard_hub"]
    ys = np.linspace(-b / 2, b / 2, 2 * nseg + 1)
    ys = np.array(sorted(set(np.round(np.r_[ys[np.abs(np.abs(ys) - y_in) > 0.05], -y_in, y_in], 9))))   # nodes at the pylon roots
    wn = [M.node((abs(y) * tsw + x_spar, y, abs(y) * tdi)) for y in ys]
    wd = d["wing"]
    inc = math.radians(w.get("incidence_deg", 0.0))
    vref_w = (-math.sin(inc), 0.0, math.cos(inc))                # box depth axis = chord normal, pitched by the incidence
    for i in range(len(ys) - 1):
        eta = abs((ys[i] + ys[i + 1]) / 2) / (b / 2)
        n_ud = int(round(wd["n_ud_root"] + (wd["n_ud_tip"] - wd["n_ud_root"]) * eta))
        M.beam(wn[i], wn[i + 1], wing_box(pm, sz, n_ud, wd), vref_w, "wing", "wing")
    info["wing_nodes"], info["wing_y"] = wn, ys
    centre = wn[int(np.argmin(np.abs(ys)))]; M.tags["centre"] = centre

    # ---- keel along the cabin floor
    k = d["keel"]
    z_top = wsec.fuselage_top_z(sz, p["wing"])                     # fuselage top at the lower root spar foot
    z_floor = z_top - fu["H"] + 0.04
    zk = z_floor - k["depth"] / 2
    x_nose, x_tail = fu["x_nose"], fu["x_tail"]
    x_cg_t = L["x_cg_hover"]
    xp = x_cg_t if x_payload is None else x_payload
    x_nl = x_nose + d["gear"]["nose_dx_from_nose"]; x_ml = x_cg_t + d["gear"]["main_dx"]
    key = sorted(set(np.round([x_tail + 0.05, x_nose - 0.10, 0.0, xp - 0.15, xp + 0.15, x_nl, x_ml, x_nose - 0.25, x_cg_t], 6)))
    xs = []
    for x0, x1 in zip(key[:-1], key[1:]):
        n = max(1, int(math.ceil((x1 - x0) / 0.12))); xs += list(np.linspace(x0, x1, n + 1)[:-1])
    xs.append(key[-1])
    kn_ = [M.node((x, 0, zk)) for x in xs]
    knode = {round(x, 6): n for x, n in zip(xs, kn_)}
    kn = lambda x: knode[round(x, 6)]
    ksec = cached(("keel",) + tuple(sorted(k.items())), lambda: af01.keel_section(pm, k))
    for n1, n2 in zip(kn_[:-1], kn_[1:]): M.beam(n1, n2, ksec, (0, 0, 1), "keel", "keel")
    M.beam(centre, kn(0.0), Rg, (1, 0, 0), "carry-through", "rigid", rigid=True)
    info["keel_nodes"] = kn_

    # ---- pods + rotor heads
    rotors = []
    m_head_static = ms["motor_kg"] + ms["motor_mount_kg"] + nac["head_fairing_kg"]
    m_rot = 2 * ms["blade_kg"] + ms["hub_kg"]
    Jp = 2 * ms["blade_kg"] * R ** 2 / 3
    arm = nac["head_arm_m"]
    pod = tube(pm, nac["pod_diameter_m"], d["pod"]["n_w45"], d["pod"]["n_ud"])
    rot_dir = p["vehicle"]["rotation"]                            # tip L, tip R, inboard L, inboard R, aft L, aft R
    pyl = tube(pm, nac["pylon_diameter_m"], d["pod"]["n_w45"], d["pod"]["n_ud"])
    ax = np.array([0, 0, 1.0]) if mode == "hover" else np.array([1.0, 0, 0])
    I = (Jp / 2, Jp / 2, Jp) if mode == "hover" else (Jp, Jp / 2, Jp / 2)

    def head(piv, root, sgn, kind, az):
        n_mot = M.node(M.X[piv] + 0.6 * arm * ax); n_hub = M.node(M.X[piv] + arm * ax)
        M.beam(piv, n_mot, Rg, (0, 1, 0), "mast", "rigid", rigid=True)
        M.beam(n_mot, n_hub, Rg, (0, 1, 0), "mast", "rigid", rigid=True)
        M.mass(piv, ms["esc_kg"] + nac["tilt_actuator_kg"] + nac["pivot_bearing_kg"])
        M.mass(n_mot, m_head_static)
        M.mass(n_hub, m_rot, I)
        rotors.append(dict(node=n_hub, root=root, xy=M.X[n_hub][:2], az=az, rot=sgn, axis=ax, kind=kind))

    for side, nt, sgn in ((+1, wn[-1], rot_dir[0]), (-1, wn[0], rot_dir[1])):
        tip = M.X[nt]
        piv = M.node((L["x_front_hub"], side * L["y_front_hub"], tip[2]))
        M.beam(nt, piv, pod, (0, 0, 1), "pod", "pod", n_sub=4)
        head(piv, nt, sgn, "front", 0.0 if side > 0 else 1.0)
    for side, sgn in ((+1, rot_dir[2]), (-1, rot_dir[3])):
        nr = wn[int(np.argmin(np.abs(ys - side * y_in)))]
        piv = M.node((L["x_inboard_hub"], side * y_in, M.X[nr][2]))
        M.beam(nr, piv, pyl, (0, 0, 1), "pod", "pod", n_sub=4)
        head(piv, nr, sgn, "inboard", 0.0 if side > 0 else 1.0)

    # ---- tail boom, tail rotor, empennage
    bd = d["boom"]
    x_ht = st["x_ht_ac"]
    z_boom = z_top - 0.10                                        # boom leaves the upswept tail cone near the top
    nb0 = M.node((x_tail + 0.05, 0, z_boom))
    M.beam(kn(x_tail + 0.05), nb0, Rg, (1, 0, 0), "tailcone", "rigid", rigid=True)
    ntr = M.node((L["x_tail_hub"], 0, z_boom)); nht = M.node((x_ht, 0, z_boom))
    bsec = tube(pm, bd["D"], bd["n_w45"], bd["n_ud"])
    M.beam(nb0, ntr, bsec, (0, 0, 1), "boom", "boom", n_sub=6)
    M.beam(ntr, nht, bsec, (0, 0, 1), "boom", "boom", n_sub=3)
    xb = d["xbeam"]; xsec = tube(pm, xb["D"], xb["n_w45"], xb["n_ud"])
    for side, sgn in ((+1, rot_dir[4]), (-1, rot_dir[5])):
        ne = M.node((L["x_tail_hub"], side * L["y_tail_hub"], z_boom))
        M.beam(ntr, ne, xsec, (0, 0, 1), "xbeam", "boom", n_sub=4)
        n_tm = M.node((L["x_tail_hub"], side * L["y_tail_hub"], z_boom + p["tail"]["pylon_height_m"] - 0.07))
        n_th = M.node((L["x_tail_hub"], side * L["y_tail_hub"], z_boom + p["tail"]["pylon_height_m"]))
        M.beam(ne, n_tm, Rg, (1, 0, 0), "mast", "rigid", rigid=True); M.beam(n_tm, n_th, Rg, (1, 0, 0), "mast", "rigid", rigid=True)
        M.mass(n_tm, ms["motor_kg"] + ms["esc_kg"] + ms["motor_mount_kg"])
        M.mass(n_th, m_rot, (Jp / 2, Jp / 2, Jp))
        rotors.append(dict(node=n_th, root=ne, xy=M.X[n_th][:2], az=180.0, rot=sgn, axis=np.array([0, 0, 1.0]), kind="tail"))
    tail_area = st["S_h"] + st["S_v_total"]
    m_tail = 1.2 * tail_area                                     # assumption: 1.2 kg/m^2 planform, foam-core composite surfaces
    M.mass(nht, m_tail)
    info["n_htail"] = nht

    # ---- payload, battery, avionics
    pl = a1["fuselage"]["payload_plates"]
    m_pay = ms["payload_kg"]; r_ = pl["D_m"] / 2; hh = pl["n"] * pl["t_m"]
    Ixy = m_pay * (r_ * r_ / 4 + hh * hh / 12); mh = m_pay * 0.15 ** 2
    zc = z_floor + hh / 2
    for xh in (xp + 0.15, xp - 0.15):
        npay = M.node((xh, 0, zc))
        M.beam(kn(xh), npay, Rg, (1, 0, 0), "payload_link", "rigid", rigid=True)
        M.mass(npay, m_pay / 2, (Ixy / 2, max(Ixy - mh, 0) / 2, max(m_pay * r_ * r_ / 2 - mh, 0) / 2))
    M.mass(kn(x_nose - 0.25), p["masses"]["avionics_kg"])
    nbat = M.node((x_cg_t, 0, zk + k["depth"] / 2 + 0.06))     # battery: flat pack under the payload, on the keel
    M.beam(kn(x_cg_t), nbat, Rg, (1, 0, 0), "bat_link", "rigid", rigid=True)
    M.mass(nbat, p["masses"]["battery_kg"])

    # ---- gear (tricycle)
    g = d["gear"]
    z_ground = z_floor - 0.04 - g["clearance"] - k["depth"]       # fuselage belly (keel under the floor) + clearance
    gsec = cached(("gear", round(g["D"], 5), g["n_w45"], g["n_ud"]), lambda: af01.gear_section(pm, g, g["D"]))
    contacts = {}
    nn = M.node((x_nl, 0, z_ground)); M.beam(kn(x_nl), nn, gsec, (1, 0, 0), "gear_nose", "gear", n_sub=3)
    contacts["nose"] = nn
    for side in (1, -1):
        nm = M.node((x_ml, side * g["main_track"] / 2, z_ground))
        M.beam(kn(x_ml), nm, gsec, (1, 0, 0), "gear_main", "gear", n_sub=4)
        contacts["main_L" if side > 0 else "main_R"] = nm
    info["z_ground"] = z_ground

    # ---- non-structural shells and non-optimum mass
    wv = pm["materials"]["woven"]
    ply = wv["t_ply"] * wv["rho"] * 1.3                          # 1 woven ply, resin-rich + paint (Airframe/01 rule)
    fus_wet = 3.4 * (0.8 * fu["L"] * fu["W"] + 0.8 * fu["L"] * fu["H"]) / 2
    m_fair = fus_wet * pm["fuselage"]["skin_plies_woven"] * ply
    box_frac = p["wing"]["spar_rear_xc"] - p["wing"]["spar_front_xc"]
    m_wing_shell = 2.04 * w["S"] * (1 - box_frac) * ply * 1.25   # LE/TE shells outside the box, +25 % ribs
    m_pod_fair = 0.0                                              # the pod tube is its own skin
    M.assemble()
    struct = M.mass_by_group()
    jf = pm["structure"]["non_optimum_factor"]
    m_abs = 3 * pm["structure"]["absorber_mass_kg"] if g.get("absorber_mm", 0) > 0 else 0.0
    for cn in contacts.values(): M.mass(cn, m_abs / 3)
    extra_k = jf * (struct.get("keel", 0) + struct.get("boom", 0) + struct.get("xbeam", 0) + struct.get("gear", 0)) + m_fair
    for n in kn_: M.mass(n, extra_k / len(kn_))
    extra_w = jf * (struct.get("wing", 0) + struct.get("pod", 0)) + m_wing_shell
    for n in wn: M.mass(n, extra_w / len(wn))
    M.assemble()
    info.update(rotors=rotors, contacts=contacts, mass_struct=struct, m_fair=m_fair, m_wing_shell=m_wing_shell,
                m_tail_surfaces=m_tail, m_nonopt=jf * sum(struct.values()), m_abs=m_abs, x_payload=xp, z_floor=z_floor, zk=zk,
                nose=x_nose, x_nl=x_nl, x_ml=x_ml)
    return M, info


def build_balanced(ctx, d, modes=("hover", "airplane")):
    """Place the payload so the HOVER CG sits on the hub-triangle centroid (equal thrust), then build the given mode."""
    # The payload moves rigidly, so one trial build gives the exact shift: dx_cg = m_payload dx_p / m.
    target = ctx["sz"]["layout"]["x_cg_hover"]
    M, info = build(ctx, d, "hover", target)
    xp = target + (target - M.cg()[0]) * M.total_mass() / ctx["a1"]["masses"]["payload_kg"]
    return {mode: build(ctx, d, mode, xp) for mode in modes}


# ------------------------------------------------------------------ loads ---------------------------------------------
def trim3(M, rotors, F):
    """Six thrusts for total F with zero roll and pitch moment about the CG: the least change from equal thrust,
    T = T0 + A^T (A A^T)^-1 (b - A T0), T0 = F / n (A: the three equations sum T = F, sum T y = F y_cg, sum T x = F x_cg)."""
    cg = M.cg(); n = len(rotors)
    A = np.array([[1.0] * n, [r["xy"][1] for r in rotors], [r["xy"][0] for r in rotors]])
    b_ = np.array([F, F * cg[1], F * cg[0]]); T0 = np.full(n, F / n)
    return T0 + A.T @ np.linalg.solve(A @ A.T, b_ - A @ T0)


def hover_loads(M, info, ctx, T):
    F = np.zeros(M.ndof)
    qt = ctx["req01"]["q_over_t_m"]
    for r, t in zip(info["rotors"], T):
        d = 6 * r["node"]
        F[d + 2] += t                                             # no tail tilt servo: hover yaw from the torque split
        F[d + 5] += -r["rot"] * qt * t
    return F


def airplane_loads(M, info, ctx, n):
    """Trimmed symmetric pull-up / gust at load factor n: elliptic wing lift + tail load (pitch balance about the CG),
    wing pitching moment from cm0, thrust = drag at the two hubs, prop reaction torque about x."""
    sz = ctx["sz"]; w = sz["wing"]
    m = M.total_mass(); W = m * G0
    cg = M.cg()
    q = 0.5 * sz["air"]["rho"] * sz["cruise"]["V"] ** 2
    M0 = q * w["S"] * w["c"] * w["cm0"]                          # aero convention: nose-up positive (cm0 < 0: nose-down)
    # Elliptic lift, lumped on the wing nodes by tributary span; it acts on the local quarter-chord line, which is
    # dx = -x_spar ahead of the spar-box axis the nodes sit on.
    ys, wn = info["wing_y"], info["wing_nodes"]
    b = w["b"]
    wt = np.sqrt(np.clip(1 - (2 * ys / b) ** 2, 0, None))
    trib = np.zeros_like(ys); dy = np.diff(ys)
    trib[:-1] += dy / 2; trib[1:] += dy / 2
    wt = wt * trib; wt /= wt.sum()
    tsw = math.tan(math.radians(-w["sweep_deg"]))
    x_l = float(np.sum(wt * np.abs(ys) * tsw))                    # lift centroid x (quarter-chord line)
    x_t = sz["stability"]["x_ht_ac"]
    # Lw + Lt = n W ;  Lw (x_l - x_cg) + Lt (x_t - x_cg) + M0 = 0   (moments about the CG, nose-up positive)
    A = np.array([[1, 1], [x_l - cg[0], x_t - cg[0]]])
    Lw, Lt = np.linalg.solve(A, [n * W, -M0])
    F = np.zeros(M.ndof)
    x_spar = M.X[wn[len(wn) // 2]][0]                             # box axis rel. to the quarter chord (< 0)
    for nd, f in zip(wn, wt):
        d = 6 * nd
        F[d + 2] += Lw * f
        # FE sign: +My turns +z toward +x, i.e. nose-DOWN. Lift Fz at dx ahead of the node: My = -dx Fz.
        F[d + 4] += -(-x_spar) * Lw * f
        F[d + 4] += -M0 * f                                       # aero moment, nose-up positive -> My = -M0
    F[6 * info["n_htail"] + 2] += Lt
    # thrust and torque
    Dr = sz["cruise"]["thrust_required_n"]
    tilt = [r for r in info["rotors"] if r["kind"] in ("front", "inboard")]
    P_sh = sz["cruise"]["shaft_power_w"] or Dr * sz["cruise"]["V"] / 0.65     # hex blade: no airplane-mode trim; eta 0.65 assumed
    Q = P_sh / len(tilt) / (2 * math.pi * ctx["rpm_cruise"] / 60)
    for r in tilt:
        d = 6 * r["node"]
        F[d + 0] += Dr / len(tilt)
        F[d + 3] += -r["rot"] * Q
    return F, {"Lw": Lw, "Lt": Lt, "M0": M0, "x_lift": x_l}


# ------------------------------------------------------------------ checks --------------------------------------------
def margins(M, u, uf, allow):
    grp = {}
    for e, fe in zip(M.elems, M.element_forces(u)):
        if e["rigid"]: continue
        s = e["sec"]
        for end in fe:
            eps, gam, q = s.recover(*[uf * x for x in end])
            half = eps / 2; rad = np.sqrt(half ** 2 + (gam / 2) ** 2)
            emax = np.max(np.maximum(np.abs(half + rad), np.abs(half - rad)))
            ms_s = allow / max(emax, 1e-12) - 1
            sig_c = np.clip(-s.Ex * eps, 0, None); tau = q / s.tm
            Rc = sig_c / s.sig_cr; Rs = tau / s.tau_cr
            lam = np.where(Rs > 1e-12, (-Rc + np.sqrt(Rc ** 2 + 4 * Rs ** 2)) / (2 * np.maximum(Rs ** 2, 1e-24)),
                           1 / np.maximum(Rc, 1e-12))
            ms_b = float(np.min(lam)) - 1
            cur = grp.setdefault(e["group"], {"strain": 9e9, "buckling": 9e9})
            cur["strain"] = min(cur["strain"], ms_s); cur["buckling"] = min(cur["buckling"], ms_b)
    return grp


def run(ctx, design=None, want_modes=True, n_modes=16):
    t0 = time.perf_counter()
    d = merge(DEFAULT, design)
    pm, sz = ctx["pm"], ctx["sz"]
    uf = pm["loads"]["ultimate_factor"]
    allow = mat.strain_allowable(pm)["eps_allow"]
    out = {"design": d, "cases": {}, "worst": {}}
    models = build_balanced(ctx, d)
    M, info = models["hover"]
    m = M.total_mass(); W = m * G0
    rot = info["rotors"]
    cases = {}
    T1 = trim3(M, rot, pm["loads"]["n_z_hover"] * W)
    cases["LC1 hover pull-up n=2"] = ("hover", hover_loads(M, info, ctx, T1))
    T2 = np.array([ctx["thrust_cap"]] + [W / 6] * (len(rot) - 1))
    cases["LC2 front rotor at ceiling"] = ("hover", hover_loads(M, info, ctx, T2))
    land = {}
    cons = info["contacts"]
    pmL = copy.deepcopy(pm); info_l = dict(info); info_l["design"] = {"gear": d["gear"]}
    for name, used in (("LC3 hard landing 3 wheels", list(cons.values())), ("LC4 hard landing one main", [cons["main_L"]])):
        Ld = af01.landing_case(M, info_l, pmL, used)
        F = hover_loads(M, info, ctx, trim3(M, rot, Ld["lift"]))
        for n_ in used: F[6 * n_ + 2] += Ld["F"] / len(used)
        cases[name] = ("hover", F); land[name] = Ld
    Ma, infa = models["airplane"]
    n_air = sz["gust"]["n_design_airplane"]
    Fa, trim_a = airplane_loads(Ma, infa, ctx, n_air)
    cases[f"LC5 airplane gust n={n_air:.2f}"] = ("airplane", Fa)
    out["airplane_trim"] = trim_a
    out["thrust_LC1"], out["thrust_LC2"] = T1.tolist(), T2.tolist()
    for name, (mode, F) in cases.items():
        Mm, inf = models[mode]
        u, acc, resid = Mm.static_inertia_relief(F, hold_node=Mm.tags["centre"])
        out.setdefault("_loads", {})[name] = (mode, F, acc)          # fuselage_shell.py cuts the fuselage free body
        g = margins(Mm, u, uf, allow)
        c0 = 6 * Mm.tags["centre"]
        tilt = [math.degrees(np.linalg.norm(u[6 * r["node"] + 3:6 * r["node"] + 6] - u[c0 + 3:c0 + 6])) for r in inf["rotors"]]
        tipdz = [1e3 * (u[6 * inf["wing_nodes"][i] + 2] - u[c0 + 2]) for i in (0, -1)]
        out["cases"][name] = {"margins": g, "shaft_tilt_deg": tilt, "wing_tip_dz_mm": tipdz, "residual": resid}
        for k_, v_ in g.items():
            wv = out["worst"].setdefault(k_, {"strain": 9e9, "buckling": 9e9})
            if v_["strain"] < wv["strain"]: wv.update(strain=v_["strain"], strain_case=name)
            if v_["buckling"] < wv["buckling"]: wv.update(buckling=v_["buckling"], buck_case=name)
    out["landing"] = land
    st = info["mass_struct"]
    out["mass_breakdown"] = dict(st, non_optimum=info["m_nonopt"], fuselage_fairing=info["m_fair"], wing_shells=info["m_wing_shell"],
                                 tail_surfaces=info["m_tail_surfaces"], absorbers=info["m_abs"])
    out["mass_airframe_kg"] = sum(out["mass_breakdown"].values())
    out["mass_total_kg"] = m
    out["x_payload"] = info["x_payload"]
    out["cg_hover"] = M.cg().tolist(); out["cg_airplane"] = Ma.cg().tolist()
    if want_modes:
        # Two band rules (see module doc and params.yaml modal.band_rule):
        #   envelope (Airframe/01): 1P and 2P over every hover weight and atmosphere, +-15 %; merged 16.6-78.6 Hz
        #   nominal: +-15 % around 1P and 2P at the design hover (MTOW, hot day) and at the airplane cruise rpm
        mg = pm["modal"]["margin"]
        # Direction-aware, as Airframe/01: a 2-blade rotor passes axial force and hub moments at 2P, in-plane force at
        # 1P (unbalance). So axial hub motion is checked against the 2P band, in-plane motion against the 1P band.
        env = {o: (b_["avoid_lo"], b_["avoid_hi"]) for o, b_ in zip((1, 2), ctx["req01"]["bands"])}
        nom = {"hover": {o: (o * ctx["rpm_hover"] / 60 * (1 - mg), o * ctx["rpm_hover"] / 60 * (1 + mg)) for o in (1, 2)},
               "airplane": {o: (o * ctx["rpm_cruise"] / 60 * (1 - mg), o * ctx["rpm_cruise"] / 60 * (1 + mg)) for o in (1, 2)}}
        rule = pm["modal"].get("band_rule", "nominal")
        out["modes"], bad, flags = {}, [], []
        tipm = ctx["req01"]["mass"]["tip_mass_kg"]
        pmin = pm["modal"]["participation_min"]
        inside = lambda f_, iv: iv[0] <= f_ <= iv[1]
        for mode, (Mm, inf) in models.items():
            f, V = Mm.modes(n_modes)
            live = [r for r in inf["rotors"] if not (mode == "airplane" and r["kind"] == "tail")]   # aft rotors stopped in cruise
            pa, pi = [], []
            for j in range(len(f)):
                a_, i_ = 0.0, 0.0
                for r in live:
                    ph = V[6 * r["node"]:6 * r["node"] + 3, j]; ax = r["axis"]
                    ax_ = float(ph @ ax); a_ = max(a_, tipm * ax_ ** 2); i_ = max(i_, tipm * float(ph @ ph - ax_ ** 2))
                pa.append(a_); pi.append(i_)
            out["modes"][mode] = {"hz": f.tolist(), "p_axial": pa, "p_inplane": pi, "hub_participation": [max(x, y) for x, y in zip(pa, pi)]}
            hard = env if rule == "envelope" else nom[mode]
            for fj, a_, i_ in zip(f, pa, pi):
                if max(a_, i_) < pmin: continue
                hit = (a_ >= pmin and inside(fj, hard[2])) or (i_ >= pmin and inside(fj, hard[1]))
                if hit: bad.append(f"{mode} {fj:.1f} Hz in a {rule} band ({'axial 2P' if a_ >= pmin and inside(fj, hard[2]) else 'in-plane 1P'})")
                elif fj < F_SOFT_MIN: bad.append(f"{mode} {fj:.1f} Hz below the {F_SOFT_MIN:.0f} Hz control floor")
                elif rule != "envelope" and ((a_ >= pmin and inside(fj, env[2])) or (i_ >= pmin and inside(fj, env[1]))):
                    flags.append(f"{mode} {fj:.1f} Hz inside the Airframe/01 envelope band (off-design weight / air)")
                if fj < hard[1][0]: flags.append(f"{mode} {fj:.1f} Hz below 1P: whirl-flutter check needed")
        out["modes_bad"], out["modes_flags"] = bad, flags
        out["bands"] = {"envelope": env, "nominal": nom, "rule": rule}
    out["verdict"], out["reasons"] = verdict(pm, out)
    out["runtime_s"] = time.perf_counter() - t0
    out["_models"] = models
    return out


def verdict(pm, r):
    reasons = []
    for g, w in r["worst"].items():
        if w["strain"] < 0: reasons.append(f"{g}: strain MS {w['strain']:+.2f} ({w['strain_case']})")
        if w["buckling"] < 0: reasons.append(f"{g}: buckling MS {w['buckling']:+.2f} ({w['buck_case']})")
    t1 = max(r["cases"]["LC1 hover pull-up n=2"]["shaft_tilt_deg"])
    if t1 > pm["loads"]["shaft_tilt_max_deg"]: reasons.append(f"shaft tilt {t1:.2f} deg at LC1 > {pm['loads']['shaft_tilt_max_deg']}")
    cl = r["design"]["gear"]["clearance"]
    for name, L in r["landing"].items():
        smax = min(pm["loads"]["landing_stroke_max_m"], cl - 0.02)
        if L["stroke"] > smax: reasons.append(f"{name}: stroke {L['stroke']*1e3:.0f} mm > {smax*1e3:.0f}")
    reasons += r.get("modes_bad", [])
    return ("PASS" if not reasons else "FAIL"), reasons


def summary(r):
    s = [f"{r['verdict']}  airframe {r['mass_airframe_kg']:.2f} kg, vehicle model {r['mass_total_kg']:.1f} kg, payload at x {r['x_payload']:+.3f} ({r['runtime_s']:.2f} s)"]
    for g, w in sorted(r["worst"].items()):
        s.append(f"  {g:5s} strain MS {w['strain']:+7.2f} [{w['strain_case']}]  buckling MS {w['buckling']:+7.2f} [{w['buck_case']}]")
    for name, c in r["cases"].items():
        s.append(f"  {name}: shaft tilt max {max(c['shaft_tilt_deg']):.2f} deg, wing tip dz {c['wing_tip_dz_mm'][1]:+.0f} mm")
    for name, L in r["landing"].items(): s.append(f"  {name}: stroke {L['stroke']*1e3:.0f} mm, n {L['n']:.2f}")
    if "modes" in r:
        for mode, mo in r["modes"].items():
            s.append(f"  modes {mode}: " + ", ".join(f"{f:.1f}{'*' if p_ >= 0.05 else ''}" for f, p_ in zip(mo["hz"][:10], mo["hub_participation"])) + "  (* moves a hub)")
    s.append("  mass: " + ", ".join(f"{k} {v:.2f}" for k, v in r["mass_breakdown"].items()))
    for x in r["reasons"]: s.append("  - " + x)
    for x in r.get("modes_flags", [])[:4]: s.append("  ~ " + x)
    return "\n".join(s)


if __name__ == "__main__":
    import json
    ctx = context()
    des = json.load(open(sys.argv[1])) if len(sys.argv) > 1 else None
    r = run(ctx, des)
    print(summary(r))

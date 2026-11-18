"""Toroidal (closed-loop) rotor for the 280 lb tricopter: hand sizing, loop geometry, OpenFOAM case, mesh, run, post.

    python3 src/toroid.py sizing            # requirements, momentum theory, BEMT of the reference and of the loop legs
    python3 src/toroid.py geometry          # loop surface (STL), watertightness, areas, volumes, mass estimate, views
    python3 src/toroid.py case [rotor]      # OpenFOAM 13 case (rotor = toroid | reference), under cfd.run_root
    python3 src/toroid.py mesh [rotor]      # blockMesh, surfaceFeatures, surfaceCheck, snappyHexMesh, checkMesh
    python3 src/toroid.py run [rotor]       # foamRun (MRF, k-omega SST, steady) with the runaway guard, from iteration 0
    python3 src/toroid.py resume [rotor]    # continue from the last written iteration
    python3 src/toroid.py status [rotor]    # progress, thrust, torque, drift
    python3 src/toroid.py post [rotor]      # forces -> T, Q, P, FoM, T/W; CFD vs. hand-calculation table

GEOMETRY. Each loop is one closed tube of airfoil sections swept along a closed centreline in the rotating frame
(r, psi, z), psi in the direction of rotation (counter-clockwise seen from +z, thrust +z):
    leading leg  A:  r0 -> rt,  psi = +s(r) / (2 r),  z = -h/2       (rt = R - a_tip)
    tip turn:        r = rt + a_tip sin(pi u),  q = -cos(pi u),  psi = -q s_end / (2 r),  z = q h/2
    trailing leg B:  rt -> r0,  psi = -s(r) / (2 r),  z = +h/2
    root turn:       r = r0 - a_root sin(pi u), q = cos(pi u), same psi and z rule
with s(r) = s_end + (s_max - s_end) sin^2(pi xi), xi = (r - r0)/(rt - r0): the tangential separation of the legs, zero
slope at both turns so the path is tangent-continuous. Seen from above each loop is a petal; at both turns the legs
are stacked axially, so the turns are box-wing-like connectors. The trailing leg is the high one: the leading leg's
wake descends at the inflow angle phi, so the trailing leg passes h + s tan(phi) above it instead of h - s tan(phi).

Sections lie in the plane normal to the path tangent t. Chord direction (trailing edge -> leading edge):
    c0 = e_psi - (e_psi . t) t, normalised;   e_c = c0 cos(theta_p) + (t x c0) sin(theta_p);   e_n = t x e_c
theta_p is the pitch about the path tangent. On leg A (t = +e_r) it is +theta(r); on leg B (t = -e_r) it is -theta(r),
which gives the same nose-up pitch in space. Through each turn it goes as theta_end cos(pi u), through zero at the
middle. The NACA camber follows the same rule (+m on A, -m on B relative to e_n, zero mid-turn), so the suction side
always faces +z on the legs. The circulation is then antisymmetric on the turns, the box-wing tip loading of Prandtl.
The second loop is the first turned by 360/n_loops degrees about z.
"""
import copy, json, math, os, re, shutil, signal, subprocess, sys, time
import numpy as np
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PROP01 = os.path.join(ROOT, "..", "01_54x18_Composite")
sys.path.insert(0, os.path.join(PROP01, "src"))
import atmosphere as atm      # noqa: E402  (prop program, read only)
import bemt                   # noqa: E402
import momentum as mt         # noqa: E402

RESULTS = os.path.join(ROOT, "results")
GEOM = os.path.join(ROOT, "geometry")
LB, G0, IN = 0.45359237, 9.80665, 0.0254


def load_params():
    p = yaml.safe_load(open(os.path.join(ROOT, "params.yaml")))
    p01 = yaml.safe_load(open(os.path.join(PROP01, "params.yaml")))
    return p, p01


def rotor_params(p, rotor):
    """The base parameters, or the base with a design variant's overrides (params.yaml `variants: <name>: rotor: {...}`)."""
    v = (p.get("variants") or {}).get(rotor)
    if not v:
        return p
    q = copy.deepcopy(p)
    for k, val in (v.get("rotor") or {}).items():
        q["rotor"][k] = val
    return q


def case_rpm(rotor):
    return load_json(f"case_{rotor}.json")["rpm"]


def save_json(name, obj):
    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, name), "w") as f:
        json.dump(obj, f, indent=1, default=float)


def load_json(name):
    return json.load(open(os.path.join(RESULTS, name)))


def air_state(p, p01):
    a = p01["atmospheres"][p["design_atmosphere"]]
    return atm.state(a["temp_c"], a["alt_m"])


def reference_table():
    """The prop program's final 2-blade blade: r [m], chord [m], twist [deg], t/c."""
    d = np.loadtxt(os.path.join(PROP01, "results", "blade_final.csv"), delimiter=",", comments="#", skiprows=2)
    return d[:, 0], d[:, 2], d[:, 3], d[:, 4]


def naca4(tc, m, pc, n):
    """Unit-chord NACA 4-digit section with a closed trailing edge. Upper and lower (x, y), leading to trailing edge."""
    x = 0.5 * (1 - np.cos(np.linspace(0, math.pi, n)))
    yt = 5 * tc * (0.2969 * np.sqrt(x) - 0.1260 * x - 0.3516 * x ** 2 + 0.2843 * x ** 3 - 0.1036 * x ** 4)
    if m == 0:
        return (x, yt), (x, -yt)
    yc = np.where(x < pc, m / pc ** 2 * (2 * pc * x - x ** 2), m / (1 - pc) ** 2 * ((1 - 2 * pc) + 2 * pc * x - x ** 2))
    dyc = np.where(x < pc, 2 * m / pc ** 2 * (pc - x), 2 * m / (1 - pc) ** 2 * (pc - x))
    th = np.arctan(dyc)
    return (x - yt * np.sin(th), yc + yt * np.cos(th)), (x + yt * np.sin(th), yc - yt * np.cos(th))


def section_ring(tc, m, pc, n):
    """Closed ring of unit-section points (x from LE, y on the e_n side positive): TE -> upper -> LE -> lower.
    Negative camber is the mirror image (upper and lower swap, y -> -y)."""
    (xu, yu), (xl, yl) = naca4(tc, abs(m), pc, n)
    if m < 0:
        (xu, yu), (xl, yl) = (xl, -yl), (xu, -yu)
    return np.concatenate([xu[::-1], xl[1:-1]]), np.concatenate([yu[::-1], yl[1:-1]])


def unit_section_props(tc, n=400):
    """Area / c^2 and perimeter / c of a symmetric NACA 00xx section (camber changes them by well under 1 %)."""
    x, y = section_ring(tc, 0.0, 0.4, n)
    xs, ys = np.append(x, x[0]), np.append(y, y[0])
    area = 0.5 * abs(np.sum(xs[:-1] * ys[1:] - xs[1:] * ys[:-1]))
    perim = float(np.sum(np.hypot(np.diff(xs), np.diff(ys))))
    return area, perim


# ---- loop definition ---------------------------------------------------------------------------------------------
def leg_props(p, r):
    """Chord, t/c and pitch [rad] of a loop leg at radius r (arrays)."""
    g = p["rotor"]; R = g["diameter_in"] * IN / 2
    rr, cc, tw, _ = reference_table()
    c = np.maximum(g["chord_fraction"] * np.interp(r, rr, cc), g["chord_min_m"])
    tc = np.interp(r / R, g["tc_r_over_R"], g["tc"])
    th = np.radians(np.interp(r, rr, tw) + g["collective_offset_deg"] + g.get("twist_slope_deg", 0.0) * (r / R - 0.6))
    return c, tc, th


def loop_path(p):
    """Closed centreline of loop 0 and the section data at each station: dict of arrays (r, psi, z, chord, tc, camber,
    theta_p, segment id 0 = leg A, 1 = tip turn, 2 = leg B, 3 = root turn)."""
    g = p["rotor"]; R = g["diameter_in"] * IN / 2
    r0, ar, at, h = g["r_root_m"], g["root_turn_depth_m"], g["tip_turn_depth_m"], g["gap_m"]
    rt = R - at
    smax, send = g["sweep_max_m"], g["sweep_end_m"]
    up = 1.0 if g["trailing_leg_high"] else -1.0
    m0 = g["camber"]
    sep = lambda r: send + (smax - send) * np.sin(math.pi * (r - r0) / (rt - r0)) ** 2
    # half uniform, half cosine: the station step at the leg ends (~2.5 mm) matches the turns' step, so the section frame
    # never swings faster than the stations advance (a mismatch folds the long trailing edge back through itself)
    u_ = np.linspace(0, 1, g["n_leg_stations"])
    xi = 0.5 * u_ + 0.25 * (1 - np.cos(math.pi * u_))
    rl = r0 + (rt - r0) * xi
    cl_, tcl, thl = leg_props(p, rl)
    segs = []
    # leg A (leading, low), outward
    segs.append(dict(r=rl, psi=sep(rl) / (2 * rl), z=np.full_like(rl, -up * h / 2), chord=cl_, tc=tcl, camber=np.full_like(rl, m0), theta_p=thl, seg=np.zeros_like(rl)))
    # tip turn (interior points only)
    u = np.linspace(0, 1, g["n_tip_turn_stations"] + 2)[1:-1]
    r = rt + at * np.sin(math.pi * u); q = -np.cos(math.pi * u)
    ct, tct, tht = (v[-1] for v in (cl_, tcl, thl))
    segs.append(dict(r=r, psi=-q * send / (2 * r), z=q * up * h / 2, chord=np.full_like(u, ct), tc=np.full_like(u, tct),
                     camber=m0 * np.cos(math.pi * u), theta_p=tht * np.cos(math.pi * u), seg=np.ones_like(u)))
    # leg B (trailing, high), inward
    rb = rl[::-1]
    segs.append(dict(r=rb, psi=-sep(rb) / (2 * rb), z=np.full_like(rb, up * h / 2), chord=cl_[::-1], tc=tcl[::-1], camber=np.full_like(rb, -m0), theta_p=-thl[::-1], seg=np.full_like(rb, 2)))
    # root turn (interior points only)
    u = np.linspace(0, 1, g["n_root_turn_stations"] + 2)[1:-1]
    r = r0 - ar * np.sin(math.pi * u); q = np.cos(math.pi * u)
    # the root turn is the hub stand-in: its chord narrows and its pitch fades faster (cos |cos|) so the pitched trailing
    # edge stays well inside the bend radius (in-plane offset 0.75 c sin(theta) < a^2 / b)
    c0, tc0, th0 = cl_[0], tcl[0], thl[0]
    cq = np.cos(math.pi * u)
    segs.append(dict(r=r, psi=-q * send / (2 * r), z=q * up * h / 2, chord=c0 * (1 - g["root_turn_chord_cut"] * np.sin(math.pi * u)), tc=np.full_like(u, tc0),
                     camber=-m0 * cq, theta_p=-th0 * cq * np.abs(cq), seg=np.full_like(u, 3)))
    out = {k: np.concatenate([s_[k] for s_ in segs]) for k in segs[0]}
    out.update(R=R, rt=rt, r0=r0)
    return out


def loop_frames(path):
    """Centreline points (n, 3), unit tangent, chord direction (TE -> LE) and section normal at every station."""
    r, ps, z = path["r"], path["psi"], path["z"]
    C = np.column_stack([r * np.cos(ps), r * np.sin(ps), z])
    t = np.roll(C, -1, axis=0) - np.roll(C, 1, axis=0)                     # central differences on the closed loop
    t /= np.linalg.norm(t, axis=1, keepdims=True)
    e_psi = np.column_stack([-np.sin(ps), np.cos(ps), np.zeros_like(ps)])
    c0 = e_psi - np.einsum("ij,ij->i", e_psi, t)[:, None] * t
    proj = np.linalg.norm(c0, axis=1)
    c0 /= proj[:, None]
    th = path["theta_p"][:, None]
    tc0 = np.cross(t, c0)
    e_c = c0 * np.cos(th) + tc0 * np.sin(th)
    e_n = np.cross(t, e_c)
    return C, t, e_c, e_n, proj


def loop_rings(p, path=None):
    g = p["rotor"]
    path = path or loop_path(p)
    C, t, e_c, e_n, proj = loop_frames(path)
    rings = []
    for i in range(len(C)):
        x, y = section_ring(path["tc"][i], path["camber"][i], g["camber_position"], g["n_airfoil_points"])
        a = (g["stacking_x_over_c"] - x) * path["chord"][i]
        rings.append(C[i] + a[:, None] * e_c[i] + (y * path["chord"][i])[:, None] * e_n[i])
    return np.array(rings), path, (C, t, e_c, e_n, proj)


def tube_triangles(rings):
    """Closed tube through closed rings (n_st, m, 3): every edge is shared by two triangles, no caps needed."""
    n, m = rings.shape[:2]
    i, j = np.meshgrid(np.arange(n), np.arange(m), indexing="ij")
    i1, j1 = (i + 1) % n, (j + 1) % m
    a, b, c, d = rings[i, j], rings[i1, j], rings[i1, j1], rings[i, j1]
    return np.concatenate([np.stack([a, b, c], axis=2).reshape(-1, 3, 3), np.stack([a, c, d], axis=2).reshape(-1, 3, 3)])


def rotor_triangles(p):
    rings, path, frames = loop_rings(p)
    t0 = tube_triangles(rings)
    out = []
    for k in range(p["rotor"]["n_loops"]):
        a = 2 * math.pi * k / p["rotor"]["n_loops"]
        Rz = np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1]])
        out.append(t0 @ Rz.T)
    tris = np.concatenate(out)
    return tris, rings, path, frames


def mesh_stats(tris):
    """Watertightness (every edge in exactly two triangles, opposite directions), volume, area, inertia about z."""
    scale = np.abs(tris).max()
    key = np.round(tris.reshape(-1, 3) / (scale * 1e-8)).astype(np.int64)
    _, idx = np.unique(key, axis=0, return_inverse=True)
    f = idx.reshape(-1, 3)
    e = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
    _, cnt = np.unique(np.sort(e, axis=1), axis=0, return_counts=True)
    _, dcnt = np.unique(e, axis=0, return_counts=True)
    a, b, c = tris[:, 0], tris[:, 1], tris[:, 2]
    det = np.einsum("ij,ij->i", a, np.cross(b, c))
    vol = det.sum() / 6.0
    sec = lambda k: (det / 60.0 * (a[:, k] ** 2 + b[:, k] ** 2 + c[:, k] ** 2 + a[:, k] * b[:, k] + a[:, k] * c[:, k] + b[:, k] * c[:, k])).sum()
    area = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    return {"triangles": int(len(tris)), "edges_not_shared_by_two": int((cnt != 2).sum()), "edges_inconsistent": int((dcnt != 1).sum()),
            "volume_m3": float(vol), "area_m2": float(area.sum()), "izz_unit_density": float(sec(0) + sec(1)),
            "degenerate_triangles": int((area < 1e-12 * area.max()).sum()),
            "bbox_min": tris.reshape(-1, 3).min(axis=0).tolist(), "bbox_max": tris.reshape(-1, 3).max(axis=0).tolist()}


def write_stl(path, tris, name):
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-30)
    with open(path, "w") as f:
        f.write(f"solid {name}\n")
        for t_, nn in zip(tris, n):
            f.write(f" facet normal {nn[0]:.6e} {nn[1]:.6e} {nn[2]:.6e}\n  outer loop\n")
            for v in t_: f.write(f"   vertex {v[0]:.8e} {v[1]:.8e} {v[2]:.8e}\n")
            f.write("  endloop\n endfacet\n")
        f.write(f"endsolid {name}\n")


def read_stl_ascii(path):
    v = np.array([l.split()[1:4] for l in open(path) if l.lstrip().startswith("vertex")], float)
    return v.reshape(-1, 3, 3)


def read_stl_binary(path):
    raw = open(path, "rb").read()
    n = int(np.frombuffer(raw[80:84], "<u4")[0])
    rec = np.frombuffer(raw[84:84 + 50 * n], dtype=np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]))
    return rec["v"].astype(float)


# ---- stage: sizing -----------------------------------------------------------------------------------------------
def build_polars(p01):
    import airfoils
    db, _ = airfoils.build_db(p01)          # XFOIL polars are cached in Props/01_54x18_Composite/results/polars
    return db


def reference_blade(p01):
    rr, cc, tw, tc = reference_table()
    R = p01["rotor"]["diameter_in"] * IN / 2
    return bemt.Blade(R, p01["rotor"]["hub_radius_m"], p01["rotor"]["n_blades"], rr, cc, np.radians(tw), tc)


def leg_blade(p):
    """The loop's legs as an open 4-bladed rotor out to R (each leg is a blade; the turn is replaced by the leg running on)."""
    g = p["rotor"]; R = g["diameter_in"] * IN / 2
    r = np.linspace(g["r_root_m"], R, 60)
    c, tc, th = leg_props(p, r)
    return bemt.Blade(R, g["r_root_m"], 2 * g["n_loops"], r, c, th, tc)


def bemt_point(blade, db, air, rpm, tip_loss=True):
    s = bemt.axial(blade, db, air, rpm, 0.0, n=60, tip_loss=tip_loss)
    return {k: float(s[k]) for k in ("rpm", "T", "Q", "P", "CT_h", "FoM", "tip_mach")} | {"mean_cl": float(np.sum(s["cl"] * s["dT_dr"] * s["dr"]) / s["T"])}


def at_thrust(blade, db, air, T, tip_loss=True):
    s = bemt.trim_rpm(lambda rpm: bemt.axial(blade, db, air, rpm, 0.0, n=60, tip_loss=tip_loss), T)
    return bemt_point(blade, db, air, s["rpm"], tip_loss)


def stage_sizing(p, p01):
    v = p["vehicle"]; air = air_state(p, p01); g = p["rotor"]
    R = g["diameter_in"] * IN / 2; A = math.pi * R * R
    W = v["mtow_lb"] * LB * G0
    T_h, T_req, T_tgt = W / v["n_rotors"], v["tw_required"] * W / v["n_rotors"], v["tw_target"] * W / v["n_rotors"]
    ph1 = json.load(open(os.path.join(PROP01, "results", "phase1.json")))
    mot = ph1["motor_match"]["catalog_motors"]["tmotor_u15xl_kv38"]
    el = p01["electrical"]
    rpm_av = el["k_load"] * mot["kv"] * el["cells_baseline"] * el["v_cell_sag"]
    rpm_mach = mt.rpm_from_vtip(p01["rotor"]["tip_mach_max"] * air["a"], 2 * R)
    mom = {}
    for tag, T in (("hover", T_h), ("tw_required", T_req), ("tw_target", T_tgt)):
        vi = math.sqrt(T / (2 * air["rho"] * A))
        mom[tag] = {"T": T, "vi": vi, "P_ideal": T * vi, "disk_flow_m3s": vi * A, "far_wake_speed": 2 * vi}
    db = build_polars(p01)
    ref, legs = reference_blade(p01), leg_blade(p)
    out = {"inputs": {"mtow_kg": v["mtow_lb"] * LB, "W_n": W, "drone_max_kg": v["drone_max_lb"] * LB, "payload_kg": v["payload_lb"] * LB,
                      "sum_check_lb": v["drone_max_lb"] + v["payload_lb"], "n_rotors": v["n_rotors"], "T_hover": T_h, "T_required": T_req, "T_target": T_tgt,
                      "R": R, "A": A, "disk_loading": T_h / A, "air": air, "rpm_available_sag": rpm_av, "rpm_mach_limit": rpm_mach,
                      "kt": mot["kt"], "i_peak": mot["peak_current_a"], "motor_mass_kg": mot["mass_kg"]},
           "momentum": mom, "solidity": {"reference": ref.solidity(), "legs": legs.solidity()}}
    # hand: blade loading and Prandtl tip-loss factor B = 1 - sqrt(2 CT)/N at the T/W 1.5 point of the reference
    rows = {}
    rows["reference"] = {"tw_required": at_thrust(ref, db, air, T_req), "hover": at_thrust(ref, db, air, T_h)}
    rows["legs_tip_loss"] = {"tw_required": at_thrust(legs, db, air, T_req), "hover": at_thrust(legs, db, air, T_h)}
    rows["legs_no_tip_loss"] = {"tw_required": at_thrust(legs, db, air, T_req, False), "hover": at_thrust(legs, db, air, T_h, False)}
    for k, b in (("reference", ref), ("legs_tip_loss", legs)):
        rows[k]["at_motor_rpm"] = bemt_point(b, db, air, rpm_av)
        rows[k]["at_motor_rpm"]["tw"] = rows[k]["at_motor_rpm"]["T"] / T_h
    rows["legs_no_tip_loss"]["at_motor_rpm"] = bemt_point(legs, db, air, rpm_av, False)
    rows["legs_no_tip_loss"]["at_motor_rpm"]["tw"] = rows["legs_no_tip_loss"]["at_motor_rpm"]["T"] / T_h
    out["bemt"] = rows
    ct_h = rows["reference"]["tw_required"]["CT_h"]
    out["tip_loss_hand"] = {"CT_h": ct_h, "B_2": 1 - math.sqrt(2 * ct_h) / 2, "B_4": 1 - math.sqrt(2 * ct_h) / 4,
                            "induced_power_cut_2_to_4_pct": 100 * (1 - (1 - math.sqrt(2 * ct_h) / 2) / (1 - math.sqrt(2 * ct_h) / 4))}
    rpm_cfd = p["cfd"]["rpm"] or 10 * round(rows["legs_tip_loss"]["tw_required"]["rpm"] / 10)
    out["cfd_rpm"] = rpm_cfd
    out["cfd_point_bemt"] = {"legs_tip_loss": bemt_point(legs, db, air, rpm_cfd), "legs_no_tip_loss": bemt_point(legs, db, air, rpm_cfd, False),
                             "reference": bemt_point(ref, db, air, rpm_cfd)}
    # motor current at the T/W 1.5 point: I = Q / kt
    for k in rows:
        rows[k]["tw_required"]["motor_current_a"] = rows[k]["tw_required"]["Q"] / mot["kt"]
    save_json("sizing.json", out)
    print(json.dumps({"T_req": T_req, "rpm_av": rpm_av, "solidity": out["solidity"], "cfd_rpm": rpm_cfd,
                      "tw_req": {k: rows[k]["tw_required"] for k in rows}, "tip_loss": out["tip_loss_hand"]}, indent=1, default=float))
    return out


# ---- stage: geometry ---------------------------------------------------------------------------------------------
def stage_geometry(p, p01, rotor="toroid"):
    p = rotor_params(p, rotor); tag = "" if rotor == "toroid" else f"_{rotor}"
    g = p["rotor"]
    tris, rings, path, (C, t, e_c, e_n, proj) = rotor_triangles(p)
    st = mesh_stats(tris)
    if st["volume_m3"] < 0:
        raise SystemExit("inward normals: ring orientation is wrong")
    os.makedirs(GEOM, exist_ok=True)
    write_stl(os.path.join(GEOM, f"{rotor}.stl"), tris, "toroid")
    R = path["R"]
    # independent checks: (1) volume from the sections (section area x path length) vs. the STL volume
    seg_len = np.linalg.norm(np.roll(C, -1, axis=0) - C, axis=1)
    ds = 0.5 * (seg_len + np.roll(seg_len, 1))
    props = np.array([unit_section_props(tc_) for tc_ in path["tc"]])
    vol_sections = g["n_loops"] * float(np.sum(props[:, 0] * path["chord"] ** 2 * ds))
    area_sections = g["n_loops"] * float(np.sum(props[:, 1] * path["chord"] * ds))
    # (2) leg gap: distance between the legs' chord lines at mid-span, normal to the chord
    leg = path["seg"]
    iA = np.where(leg == 0)[0]; iB = np.where(leg == 2)[0][::-1]
    gaps = []
    for k in range(len(iA)):
        d = C[iB[k]] - C[iA[k]]
        gaps.append({"r": float(path["r"][iA[k]]), "gap_normal_to_chord_m": float(abs(d @ e_n[iA[k]])), "stagger_along_chord_m": float(d @ e_c[iA[k]]),
                     "chord_m": float(path["chord"][iA[k]])})
    # (3) no-fold check: every ring point must advance along the local tangent from one station to the next. The ratio
    # (P[i+1,k] - P[i,k]) . t_i / |C[i+1] - C[i]| is 1 for a straight tube and reaches 0 where the sections cross.
    adv = np.einsum("ikj,ij->ik", np.roll(rings, -1, axis=0) - rings, t) / seg_len[:, None]
    fold = {"min_advance_ratio": float(adv.min()), "station": int(np.unravel_index(adv.argmin(), adv.shape)[0]),
            "segment": int(path["seg"][np.unravel_index(adv.argmin(), adv.shape)[0]]), "n_negative": int((adv <= 0).sum())}
    # (4) worst projection of e_psi on the section plane (1 = flow exactly normal to the section plane)
    # (5) reference blade-set area and volume from the BEMT planform (same section integrals)
    rr, cc, tw, tcr = reference_table()
    Rr = p01["rotor"]["diameter_in"] * IN / 2
    rs = np.linspace(p01["rotor"]["hub_radius_m"], Rr, 400); cs = np.interp(rs, rr, cc); ts = np.interp(rs, rr, tcr)
    pr = np.array([unit_section_props(x) for x in ts])
    nb = p01["rotor"]["n_blades"]
    ref_vol = nb * float(np.trapezoid(pr[:, 0] * cs ** 2, rs)); ref_area = nb * float(np.trapezoid(pr[:, 1] * cs, rs))
    m_ref = p["mass"]["reference_blade_set_kg"]
    mass = {"reference_kg": m_ref, "reference_volume_cm3": 1e6 * ref_vol, "reference_area_m2": ref_area,
            "toroid_volume_cm3": 1e6 * st["volume_m3"], "toroid_area_m2": st["area_m2"],
            "volume_scaled_kg": m_ref * st["volume_m3"] / ref_vol, "area_scaled_kg": m_ref * st["area_m2"] / ref_area}
    seg_names = ["leg A", "tip turn", "leg B", "root turn"]
    seg_area = {seg_names[k]: g["n_loops"] * float(np.sum((props[:, 1] * path["chord"] * ds)[leg == k])) for k in range(4)}
    out = {"stl": st, "R": R, "rt": path["rt"], "r0": path["r0"], "stations": int(len(C)), "ring_points": int(rings.shape[1]),
           "volume_from_sections_m3": vol_sections, "volume_diff_pct": 100 * (st["volume_m3"] / vol_sections - 1),
           "area_from_sections_m2": area_sections, "area_diff_pct": 100 * (st["area_m2"] / area_sections - 1),
           "area_by_segment_m2": seg_area, "min_flow_projection": float(proj.min()), "fold_check": fold,
           "gaps": gaps[:: max(1, len(gaps) // 12)], "mass": mass,
           "z_extent_m": [float(np.min(tris[:, :, 2])), float(np.max(tris[:, :, 2]))],
           "r_extent_m": [float(np.min(np.hypot(tris[:, :, 0], tris[:, :, 1]))), float(np.max(np.hypot(tris[:, :, 0], tris[:, :, 1])))],
           "leading_edge_length_m": g["n_loops"] * float(np.sum(seg_len)),
           "nose_radius_mm_at_tip_turn": 1000 * 1.1019 * float(path["tc"][leg == 1][0]) ** 2 * float(path["chord"][leg == 1][0]),
           "nose_radius_mm_at_075R": 1000 * 1.1019 * float(np.interp(0.75 * R, path["r"][iA], path["tc"][iA])) ** 2 * float(np.interp(0.75 * R, path["r"][iA], path["chord"][iA]))}
    save_json(f"geometry{tag}.json", out)
    plot_geometry(p, tris, rings, path, C, os.path.join(RESULTS, f"fig_geometry{tag}.png"))
    if fold["n_negative"]:
        raise SystemExit(f"sections fold at station {fold['station']} (segment {fold['segment']}): {fold}")
    print(json.dumps({k: out[k] for k in ("stl", "fold_check", "volume_diff_pct", "area_diff_pct", "area_by_segment_m2", "min_flow_projection", "mass", "z_extent_m", "r_extent_m",
                                          "nose_radius_mm_at_tip_turn", "nose_radius_mm_at_075R")}, indent=1))
    return out


def plot_geometry(p, tris, rings, path, C, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    R = path["R"]
    fig = plt.figure(figsize=(12, 11))
    gs = fig.add_gridspec(3, 2, height_ratios=[1.3, 0.55, 0.9])
    ax = fig.add_subplot(gs[0, 0], projection="3d")
    sub = tris[:: max(1, len(tris) // 30000)]
    n = np.cross(sub[:, 1] - sub[:, 0], sub[:, 2] - sub[:, 0]); n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-30
    shade = 0.35 + 0.6 * np.clip(n @ np.array([0.3, -0.5, 0.8]) / np.linalg.norm([0.3, -0.5, 0.8]), 0, 1)
    pc = Poly3DCollection(sub, facecolors=plt.cm.Greys(shade * 0.8 + 0.1), edgecolor="none")
    ax.add_collection3d(pc)
    ax.set_xlim(-R, R); ax.set_ylim(-R, R); ax.set_zlim(-0.2 * R, 0.2 * R); ax.set_box_aspect((2, 2, 0.4), zoom=1.25); ax.view_init(32, -62)
    ax.set_title("Toroidal rotor, 2 loops (4 legs), 54 in", fontsize=9); ax.set_axis_off()
    from matplotlib.collections import PolyCollection
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.add_collection(PolyCollection(tris[:, :, :2], facecolors="#52514e", edgecolors="none"))
    th = np.linspace(0, 2 * math.pi, 200)
    ax2.plot(R * np.cos(th), R * np.sin(th), color="#2a78d6", lw=0.8, ls="--", label="54 in disk")
    ax2.annotate("", xy=(0.25 * R, 0.55 * R), xytext=(0.55 * R, 0.25 * R), arrowprops=dict(arrowstyle="->", color="#2a78d6", connectionstyle="arc3,rad=0.3"))
    ax2.text(0.47 * R, 0.47 * R, "rotation", color="#2a78d6", fontsize=7)
    ax2.set_xlim(-1.05 * R, 1.05 * R); ax2.set_ylim(-1.05 * R, 1.05 * R)
    ax2.set_aspect("equal"); ax2.set_title("Top view: each loop is a petal (leading leg ahead, legs meet at the turns)", fontsize=9); ax2.legend(fontsize=7, loc="lower right"); ax2.grid(alpha=.3)
    ax3 = fig.add_subplot(gs[1, :])
    leg = path["seg"]; iA = np.where(leg == 0)[0]; iB = np.where(leg == 2)[0]
    off = 0.0
    for x in (0.25, 0.5, 0.75, 0.9):
        for idx, col in ((iA, "#0b0b0b"), (iB, "#2a78d6")):
            i = idx[np.argmin(np.abs(path["r"][idx] - x * R))]
            ring = rings[i]; rr_ = np.hypot(ring[:, 0], ring[:, 1])
            s_ = rr_ * np.arctan2(ring[:, 1], ring[:, 0])
            ax3.fill(1000 * s_ + off, 1000 * ring[:, 2], color=col, lw=0)
        ax3.text(off, -75, f"r/R = {x}", ha="center", fontsize=7)
        off += 300
    ax3.set_aspect("equal"); ax3.set_xlabel("tangential position r psi [mm] (rotation to the right; panels offset)"); ax3.set_ylabel("z [mm]")
    ax3.set_ylim(-90, 70); ax3.set_title("Leg sections, loop seen along the radius: leading leg (black) low, trailing (blue) high", fontsize=9); ax3.grid(alpha=.3)
    ax4 = fig.add_subplot(gs[2, :])
    leg = path["seg"]
    for k, nm in ((0, "leading leg"), (2, "trailing leg")):
        m = leg == k
        ax4.plot(path["r"][m] / R, 1000 * path["chord"][m], label=f"chord [mm], {nm}" if k == 0 else None, color="#0b0b0b")
    m = leg == 0
    ax4.plot(path["r"][m] / R, np.degrees(path["theta_p"][m]), color="#2a78d6", label="pitch [deg]")
    ax4.plot(path["r"][m] / R, 100 * path["tc"][m], color="#c0392b", label="t/c [%]")
    ax4.plot(path["r"][m] / R, 1000 * path["r"][m] * 2 * path["psi"][m], color="#7f8c8d", ls="--", label="tangential leg separation [mm]")
    rr, cc, tw, _ = reference_table()
    ax4.plot(rr / R, 1000 * cc, color="#0b0b0b", ls=":", label="2-blade reference chord [mm]")
    ax4.set_xlabel("r / R"); ax4.set_title("Leg definition", fontsize=9); ax4.legend(fontsize=7); ax4.grid(alpha=.3)
    fig.tight_layout(); fig.savefig(out, dpi=140); plt.close(fig)


# ---- OpenFOAM case -----------------------------------------------------------------------------------------------
HDR = lambda cls, obj, loc="": "FoamFile\n{\n    format      ascii;\n    class       %s;\n%s    object      %s;\n}\n\n" % (cls, ('    location    "%s";\n' % loc) if loc else "", obj)
MESH = "prelim"


def case_dir(p, rotor):
    return os.path.join(os.path.expanduser(p["cfd"]["run_root"]), f"{rotor}_{MESH}")


def rotor_stl(rotor):
    return os.path.join(GEOM, f"{rotor}.stl") if rotor.startswith("toroid") else os.path.join(PROP01, "geometry", "prop_ccw.stl")


def guard_limits(p, p01, rotor="toroid"):
    s = load_json("sizing.json")
    T = s["inputs"]["T_required"]; A = s["inputs"]["A"]; rho = s["inputs"]["air"]["rho"]
    vi = math.sqrt(T / (2 * rho * A)); g = p["cfd"]["guard"]
    om = case_rpm(rotor) * math.pi / 30; R = s["inputs"]["R"]
    ct = T / (rho * A * (om * R) ** 2)
    return {"ct_min": 0.0, "ct_max": g["ct_max_factor"] * ct, "flow_max": g["bottom_flow_max_factor"] * 2 * vi * A, "wake_flow_momentum": 2 * vi * A,
            "start": g["start_iteration"], "window": g["window"], "qref": rho * A * (om * R) ** 2}


def stage_case(p, p01, rotor="toroid"):
    s = load_json("sizing.json")
    air = s["inputs"]["air"]; rpm = ((p.get("variants") or {}).get(rotor) or {}).get("cfd_rpm") or s["cfd_rpm"]
    mm, dom, v = p["cfd"]["meshes"][MESH], p["cfd"]["domain"], p["cfd"]
    case = case_dir(p, rotor)
    for d_ in ("0", "constant/geometry", "system"):
        os.makedirs(os.path.join(case, d_), exist_ok=True)
    src = rotor_stl(rotor)
    if rotor.startswith("toroid"):
        shutil.copy(src, os.path.join(case, "constant", "geometry", "rotor.stl"))
    else:                                                     # the prop program's ASCII STL (metres) is named prop_ccw; rename the solid "rotor"
        with open(src) as fi, open(os.path.join(case, "constant", "geometry", "rotor.stl"), "w") as fo:
            for line in fi:
                fo.write(re.sub(r"^(end)?solid\s+\S+", lambda m_: (m_.group(1) or "") + "solid rotor", line))
    W = lambda rel, txt: open(os.path.join(case, rel), "w").write(txt)
    R = s["inputs"]["R"]; D = 2 * R; h = mm["base_cell_m"]
    a = dom["core_half_width_R"] * R; n = round(2 * a / h); a = n * h / 2
    z0, z1 = -round(dom["below_D"] * D / h) * h, round(dom["above_D"] * D / h) * h
    nz = round((z1 - z0) / h); Rc = dom["radius_D"] * D; q = Rc / math.sqrt(2)
    grade = 0.25; nr = max(4, round((Rc - a) / (h * (1 + 1 / grade) / 2)))
    vz = lambda z: [(-a, -a, z), (a, -a, z), (a, a, z), (-a, a, z), (-q, -q, z), (q, -q, z), (q, q, z), (-q, q, z)]
    verts = "\n".join("    (%.6f %.6f %.6f)" % t for t in vz(z0) + vz(z1))
    arcs = "\n".join("    arc %d %d (%.6f %.6f %.6f)" % t for z, o in ((z0, 0), (z1, 8)) for t in
                     ((4 + o, 5 + o, 0, -Rc, z), (5 + o, 6 + o, Rc, 0, z), (6 + o, 7 + o, 0, Rc, z), (7 + o, 4 + o, -Rc, 0, z)))
    W("system/blockMeshDict", HDR("dictionary", "blockMeshDict") + f"""// O-grid cylinder (radius {Rc:.3f} m = 5 D, {-z0:.2f} m below and {z1:.2f} m above the rotor): a Cartesian core of
// {h} m cubes where all refinement happens, and four graded outer blocks.
convertToMeters 1;
vertices
(
{verts}
);
blocks
(
    hex (0 1 2 3 8 9 10 11)   ({n} {n} {nz})  simpleGrading (1 1 1)
    hex (4 5 1 0 12 13 9 8)   ({n} {nr} {nz}) simpleGrading (1 {grade} 1)
    hex (5 6 2 1 13 14 10 9)  ({n} {nr} {nz}) simpleGrading (1 {grade} 1)
    hex (6 7 3 2 14 15 11 10) ({n} {nr} {nz}) simpleGrading (1 {grade} 1)
    hex (7 4 0 3 15 12 8 11)  ({n} {nr} {nz}) simpleGrading (1 {grade} 1)
);
edges
(
{arcs}
);
boundary
(
    far_side   {{ type patch; faces ((4 5 13 12) (5 6 14 13) (6 7 15 14) (7 4 12 15)); }}
    far_bottom {{ type patch; faces ((0 3 2 1) (4 0 1 5) (5 1 2 6) (6 2 3 7) (7 3 0 4)); }}
    far_top    {{ type patch; faces ((8 9 10 11) (12 13 9 8) (13 14 10 9) (14 15 11 10) (15 12 8 11)); }}
);
""")
    W("system/surfaceFeaturesDict", HDR("dictionary", "surfaceFeaturesDict") + 'surfaces ("rotor.stl");\nincludedAngle 150;\nsubsetFeatures { nonManifoldEdges yes; openEdges yes; }\n')
    W("system/meshQualityDict", HDR("dictionary", "meshQualityDict") + '#includeEtc "caseDicts/mesh/generation/meshQualityDict"\n')
    cyl = lambda name, zlo, zhi, rad: f"    {name} {{ type cylinder; point1 (0 0 {zlo:.4f}); point2 (0 0 {zhi:.4f}); radius {rad:.4f}; }}\n"
    W("system/snappyHexMeshDict", HDR("dictionary", "snappyHexMeshDict") + f"""// Surface cells {1e3 * h / 2 ** mm['surface_level'][0]:.2f} mm, refined by curvature (resolveFeatureAngle) to {1e3 * h / 2 ** mm['surface_level'][1]:.2f} mm round the leading edges.
castellatedMesh true;
snap            true;
addLayers       true;

geometry
{{
    rotor {{ type triSurface; file "rotor.stl"; }}
{cyl("disk", -0.5 * R, 0.3 * R, 1.25 * R)}{cyl("wake", -2.0 * R, 0.5 * R, 1.4 * R)}{cyl("farWake", -6.0 * R, 1.0 * R, 2.0 * R)}{cyl("farWake2", -12.0 * R, 1.5 * R, 2.3 * R)}}};

castellatedMeshControls
{{
    maxLocalCells 2000000;
    maxGlobalCells {mm['max_global_cells']};
    minRefinementCells 10;
    maxLoadUnbalance 0.10;
    nCellsBetweenLevels {mm.get('n_cells_between_levels', 3)};
    features ( {{ file "rotor.eMesh"; level {mm['edge_level']}; }} );
    refinementSurfaces
    {{
        rotor {{ level ({mm['surface_level'][0]} {mm['surface_level'][1]}); patchInfo {{ type wall; }} }}
    }}
    resolveFeatureAngle {mm['resolve_feature_angle']};
    refinementRegions
    {{
        disk     {{ mode inside; level {mm['disk_level']}; }}
        wake     {{ mode inside; level {mm['wake_level']}; }}
        farWake  {{ mode inside; level {mm['far_wake_level']}; }}
        farWake2 {{ mode inside; level 1; }}
    }}
    insidePoint (0.0123 0.0217 0.4113);
    allowFreeStandingZoneFaces true;
}}

snapControls
{{
    nSmoothPatch 3;
    tolerance 2.0;
    nSolveIter 50;
    nRelaxIter 5;
    nFeatureSnapIter 10;
    implicitFeatureSnap false;
    explicitFeatureSnap true;
    multiRegionFeatureSnap false;
}}

addLayersControls
{{
    relativeSizes true;
    layers {{ rotor {{ nSurfaceLayers {mm['n_layers']}; }} }}
    expansionRatio {mm['expansion']};
    finalLayerThickness {mm['final_layer_rel']};
    minThickness 0.08;
    nGrow 0;
    featureAngle 130;
    slipFeatureAngle 30;
    nRelaxIter 5;
    nSmoothSurfaceNormals 1;
    nSmoothNormals 3;
    nSmoothThickness 10;
    maxFaceThicknessRatio 0.5;
    maxThicknessToMedialRatio 0.3;
    minMedianAxisAngle 90;
    nBufferCellsNoExtrude 0;
    nLayerIter 50;
}}

meshQualityControls
{{
    #include "meshQualityDict"
}}

writeFlags ( scalarLevels layerSets layerFields );
mergeTolerance 1e-6;
""")
    W("system/decomposeParDict", HDR("dictionary", "decomposeParDict") + f"numberOfSubdomains {v['n_proc']};\ndecomposer scotch;\ndistributor ptscotch;\n")
    n_it = ((p.get("variants") or {}).get(rotor) or {}).get("iterations") or mm["iterations"]
    W("system/controlDict", HDR("dictionary", "controlDict") + f"""// {rotor} rotor, frozen-rotor MRF at {rpm} rpm, hot day (rho {air['rho']:.4f} kg/m^3, nu {air['nu']:.4e} m^2/s)
solver          incompressibleFluid;
startFrom       latestTime;
startTime       0;
stopAt          endTime;
endTime         {n_it};
deltaT          1;
writeControl    timeStep;
writeInterval   100;
purgeWrite      2;
writeFormat     binary;
writePrecision  8;
writeCompression off;
timeFormat      general;
timePrecision   6;
runTimeModifiable true;

functions
{{
    forces
    {{
        type forces; libs ("libforces.so");
        patches (rotor); rho rhoInf; rhoInf {air['rho']:.6f}; CofR (0 0 0);
        writeControl timeStep; writeInterval 1; log no;
    }}
    rotorSurface
    {{
        type surfaces; libs ("libsampling.so");
        writeControl writeTime; surfaceFormat raw; fields (p); interpolationScheme cell;
        surfaces {{ rotor {{ type patch; patches (rotor); interpolate false; }} }}
    }}
    yPlus
    {{
        type yPlus; libs ("libfieldFunctionObjects.so"); writeControl writeTime;
    }}
    bottomFlow
    {{
        type surfaceFieldValue; libs ("libfieldFunctionObjects.so"); writeControl timeStep; writeInterval 1; log no;
        patch far_bottom; operation sum; fields (phi); writeFields no;
    }}
}}
""")
    W("system/fvSchemes", HDR("dictionary", "fvSchemes") + """ddtSchemes { default steadyState; }
gradSchemes { default Gauss linear; grad(U) cellLimited Gauss linear 1; }
divSchemes
{
    default         none;
    div(phi,U)      bounded Gauss linearUpwindV grad(U);
    div(phi,k)      bounded Gauss upwind;
    div(phi,omega)  bounded Gauss upwind;
    div((nuEff*dev2(T(grad(U))))) Gauss linear;
}
laplacianSchemes { default Gauss linear limited 0.5; }
interpolationSchemes { default linear; }
snGradSchemes { default limited 0.5; }
wallDist { method meshWave; }
""")
    ctl = "{ nNonOrthogonalCorrectors 0; consistent yes; }"
    W("system/fvSolution", HDR("dictionary", "fvSolution") + f"""solvers
{{
    p {{ solver GAMG; smoother GaussSeidel; tolerance 1e-8; relTol 0.01; }}
    "(U|k|omega)" {{ solver smoothSolver; smoother GaussSeidel; tolerance 1e-9; relTol 0.1; nSweeps 1; }}
}}
SIMPLE {ctl}
PIMPLE {ctl}
relaxationFactors {{ equations {{ U 0.8; k 0.6; omega 0.6; }} }}
""")
    mz = v["mrf_zone"]; zr, zh = mz["radius_R"] * R, mz["half_height_R"] * R
    W("constant/MRFProperties", HDR("dictionary", "MRFProperties", "constant") + f"""// Rotating frame only in a cylinder around the rotor (frozen rotor); the rest of the domain is stationary.
rotor
{{
    cellZone
    {{
        type        cylinder;
        zoneType    cell;
        point1      (0 0 {-zh:.5f});
        point2      (0 0 {zh:.5f});
        radius      {zr:.5f};
    }}
    origin      (0 0 0);
    axis        (0 0 1);
    omega       {rpm} [rpm];
}}
""")
    W("constant/momentumTransport", HDR("dictionary", "momentumTransport", "constant") + "simulationType RAS;\nRAS { model kOmegaSST; turbulence on; }\n")
    W("constant/physicalProperties", HDR("dictionary", "physicalProperties", "constant") + f"viscosityModel constant;\nnu [0 2 -1 0 0 0 0] {air['nu']:.6e};\n")
    k0, om0 = 1e-3, 10.0
    fld = lambda cls, name, dim, internal, bcs: HDR(cls, name, "0") + f"dimensions {dim};\ninternalField uniform {internal};\nboundaryField\n{{\n    #includeEtc \"caseDicts/setConstraintTypes\"\n" + "".join(f"    {k} {{ {b} }}\n" for k, b in bcs.items()) + "}\n"
    io = lambda val: f"type inletOutlet; inletValue uniform {val}; value uniform {val};"
    W("0/U", fld("volVectorField", "U", "[0 1 -1 0 0 0 0]", "(0 0 0)", {
        "far_top": "type pressureInletOutletVelocity; value uniform (0 0 0);", "far_side": "type pressureInletOutletVelocity; value uniform (0 0 0);",
        "far_bottom": "type inletOutlet; inletValue uniform (0 0 0); value uniform (0 0 0);", "rotor": "type MRFnoSlip;"}))
    W("0/p", fld("volScalarField", "p", "[0 2 -2 0 0 0 0]", "0", {
        "far_top": "type totalPressure; p0 uniform 0; value uniform 0;", "far_side": "type totalPressure; p0 uniform 0; value uniform 0;",
        "far_bottom": "type fixedValue; value uniform 0;", "rotor": "type zeroGradient;"}))
    W("0/k", fld("volScalarField", "k", "[0 2 -2 0 0 0 0]", k0, {"far_top": io(k0), "far_side": io(k0), "far_bottom": io(k0), "rotor": f"type kqRWallFunction; value uniform {k0};"}))
    W("0/omega", fld("volScalarField", "omega", "[0 0 -1 0 0 0 0]", om0, {"far_top": io(om0), "far_side": io(om0), "far_bottom": io(om0), "rotor": f"type omegaWallFunction; value uniform {om0};"}))
    W("0/nut", fld("volScalarField", "nut", "[0 2 -1 0 0 0 0]", "0", {"far_top": "type calculated; value uniform 0;", "far_side": "type calculated; value uniform 0;",
                                                                       "far_bottom": "type calculated; value uniform 0;", "rotor": "type nutUSpaldingWallFunction; value uniform 0;"}))
    open(os.path.join(case, f"{rotor}.foam"), "w").close()
    info = {"case": case, "rotor": rotor, "rpm": rpm, "base_cell": h, "core_cells": n, "nz": nz, "nr": nr, "z0": z0, "z1": z1, "radius": Rc,
            "background_cells": nz * (n * n + 4 * n * nr), "surface_cell_mm": 1e3 * h / 2 ** mm["surface_level"][0],
            "curvature_cell_mm": 1e3 * h / 2 ** mm["surface_level"][1], "edge_cell_mm": 1e3 * h / 2 ** mm["edge_level"], "disk_cell_mm": 1e3 * h / 2 ** mm["disk_level"],
            "mrf_radius": zr, "mrf_half_height": zh}
    save_json(f"case_{rotor}.json", info); print(json.dumps(info, indent=1))
    return info


MEM_MIN_GB = float("inf")


def foam(case, cmd, log, parallel=0, mem_floor_gb=None, nice=False):
    """Run an OpenFOAM command in the case, log in the case. With mem_floor_gb, a watchdog kills the job if the free
    memory (MemAvailable) drops below it, so meshing beside another solver run can never push that run into swap."""
    global MEM_MIN_GB
    full = "source /opt/openfoam13/etc/bashrc && " + ("nice -n 19 " if nice else "") + (f"mpirun --mca btl ^tcp -np {parallel} {cmd} -parallel" if parallel else cmd)
    with open(os.path.join(case, log), "w") as f:
        pr = subprocess.Popen(["bash", "-c", full], cwd=case, stdout=f, stderr=subprocess.STDOUT, start_new_session=True)
        low = None
        while pr.poll() is None:
            time.sleep(2)
            if mem_floor_gb:
                avail = int(next(l.split()[1] for l in open("/proc/meminfo") if l.startswith("MemAvailable"))) / 1048576
                if avail < mem_floor_gb:
                    low = avail; os.killpg(pr.pid, signal.SIGTERM); pr.wait(); break
            if mem_floor_gb:
                MEM_MIN_GB = min(MEM_MIN_GB, avail)
    if low is not None:
        print(f"** {cmd}: stopped by the memory watchdog, {low:.2f} GB free < {mem_floor_gb} GB **", flush=True)
        return 99
    return pr.returncode


def collect_logs(p, rotor):
    case = case_dir(p, rotor); dst = os.path.join(ROOT, "cfd", f"{rotor}_{MESH}")
    os.makedirs(dst, exist_ok=True)
    for f in os.listdir(case):
        if f.startswith("log."):
            shutil.copy(os.path.join(case, f), os.path.join(dst, f + ".txt"))          # .txt: *.log is git-ignored in this repo
    for sub in ("system", "constant/MRFProperties", "constant/momentumTransport", "constant/physicalProperties", "0"):
        src = os.path.join(case, sub)
        if os.path.isdir(src): shutil.copytree(src, os.path.join(dst, sub), dirs_exist_ok=True)
        elif os.path.exists(src): os.makedirs(os.path.dirname(os.path.join(dst, sub)), exist_ok=True); shutil.copy(src, os.path.join(dst, sub))


def stage_mesh(p, p01, rotor="toroid", n_mesh=None, mem_floor_gb="1.5"):
    """Mesh in parallel on n_mesh processes (default: the solver count), then redistribute to the solver count if they differ."""
    case, n = case_dir(p, rotor), p["cfd"]["n_proc"]
    n_mesh = int(n_mesh or n); mem = float(mem_floor_gb)
    for d_ in os.listdir(case):
        if d_.startswith("processor") or d_ == "postProcessing":
            shutil.rmtree(os.path.join(case, d_))
    shutil.rmtree(os.path.join(case, "constant", "polyMesh"), ignore_errors=True)
    dec = os.path.join(case, "system", "decomposeParDict"); dtxt = open(dec).read()
    open(dec, "w").write(re.sub(r"numberOfSubdomains \d+;", f"numberOfSubdomains {n_mesh};", dtxt))
    steps = [("blockMesh", "log.blockMesh", 0), ("surfaceFeatures", "log.surfaceFeatures", 0),
             ("surfaceCheck -checkSelfIntersection constant/geometry/rotor.stl", "log.surfaceCheck", 0), ("decomposePar -copyZero", "log.decomposePar", 0),
             ("snappyHexMesh -overwrite", "log.snappyHexMesh", n_mesh), ("checkMesh", "log.checkMesh", n_mesh)]
    t0 = time.time(); times = {}
    for cmd, log, par in steps:
        t1 = time.time()
        rc = foam(case, cmd, log, parallel=par, mem_floor_gb=mem, nice=True)
        times[cmd.split()[0]] = time.time() - t1
        print(cmd, "->", rc, f"({times[cmd.split()[0]]:.0f} s)", flush=True)
        if cmd.startswith("surfaceCheck"):
            si = mesh_info(case)
            if si.get("surface_self_intersecting") or not si.get("surface_closed"):
                collect_logs(p, rotor); raise SystemExit(f"rotor STL is not a clean closed surface, see log.surfaceCheck: {si}")
        if rc != 0 and not cmd.startswith(("checkMesh", "surfaceCheck")):
            print(open(os.path.join(case, log), errors="replace").read()[-3000:]); collect_logs(p, rotor); raise SystemExit(1)
    if n_mesh != n:                                           # gather the mesh and split it again for the solver
        for cmd, log in (("reconstructPar -constant", "log.reconstructPar"),):
            foam(case, cmd, log, mem_floor_gb=mem, nice=True)
        for d_ in os.listdir(case):
            if d_.startswith("processor"): shutil.rmtree(os.path.join(case, d_))
        open(dec, "w").write(dtxt)
        foam(case, "decomposePar -copyZero", "log.decomposePar.solver", mem_floor_gb=mem, nice=True)
    else:
        open(dec, "w").write(dtxt)
    save_json(f"mesh_{rotor}.json", {"wall_s": time.time() - t0, "steps_s": times, "n_mesh": n_mesh, **mesh_info(case)})
    collect_logs(p, rotor)
    print(json.dumps(mesh_info(case), indent=1))


def grab(path, pat):
    if not os.path.exists(path): return []
    return [m_ for m_ in (re.search(pat, l) for l in open(path, errors="replace")) if m_]


def mesh_info(case):
    cm = os.path.join(case, "log.checkMesh")
    g1 = lambda pat: (lambda h: float(h[-1].group(1)) if h else None)(grab(cm, pat))
    info = {"cells": g1(r"^\s+cells:\s+(\d+)"), "max_non_orthogonality": g1(r"non-orthogonality Max: ([\d.]+)"), "avg_non_orthogonality": g1(r"average: ([\d.]+)"),
            "max_skewness": g1(r"Max skewness = ([\d.]+)"), "max_aspect_ratio": g1(r"Max aspect ratio = ([\d.]+)"),
            "mesh_ok": any("Mesh OK" in l for l in open(cm, errors="replace")) if os.path.exists(cm) else None,
            "failed_checks": [m_.group(0).strip() for m_ in grab(cm, r"\*\*\*.*")][:8]}
    lay = grab(os.path.join(case, "log.snappyHexMesh"), r"^rotor\s+(\d+)\s+([\d.]+)\s+([\d.eE+-]+)\s+([\d.]+)")
    if lay: info.update(layer_faces=int(lay[-1].group(1)), layers_mean=float(lay[-1].group(2)), layer_thickness_m=float(lay[-1].group(3)), layer_coverage_pct=float(lay[-1].group(4)))
    sc = os.path.join(case, "log.surfaceCheck")
    if os.path.exists(sc):
        txt = open(sc, errors="replace").read()
        info["surface_closed"] = "Surface is closed" in txt
        m_ = re.search(r"Surface is self-intersecting at (\d+) locations", txt)
        info["surface_self_intersections"] = int(m_.group(1)) if m_ else 0
        info["surface_self_intersecting"] = bool(m_)
        info["self_intersection_checked"] = "Checking self-intersection" in txt
        m_ = re.search(r"Surface has (\d+) illegal triangles", txt)
        info["surface_illegal_triangles"] = int(m_.group(1)) if m_ else 0
    return info


# ---- run / status / post -----------------------------------------------------------------------------------------
def restart_files(base, name):
    return [(float(t), os.path.join(base, t, name)) for t in sorted(os.listdir(base), key=float) if os.path.exists(os.path.join(base, t, name))]


def trim_restarts(rows):
    out, tmin = [], float("inf")
    for r in reversed(rows):
        if r[0] < tmin: out.append(r); tmin = r[0]
    return np.array(out[::-1])


def read_forces(case):
    base = os.path.join(case, "postProcessing", "forces"); rows = []
    for t, f in restart_files(base, "forces.dat"):
        for line in open(f, errors="replace"):
            if line.startswith("#"): continue
            try: v_ = [float(x) for x in re.sub(r"[()]", " ", line).split()]
            except ValueError: continue
            if len(v_) >= 13: rows.append(v_[:13])
    a = trim_restarts(rows)
    return a[:, 0], a[:, 1:4] + a[:, 4:7], a[:, 7:10] + a[:, 10:13], a[:, 4:7], a[:, 10:13]


def read_bottom_flow(case):
    base = os.path.join(case, "postProcessing", "bottomFlow"); rows = []
    if os.path.isdir(base):
        for t, f in restart_files(base, "surfaceFieldValue.dat"):
            for line in open(f, errors="replace"):
                v_ = line.split()
                if v_ and not line.startswith("#"):
                    try: rows.append((float(v_[0]), float(v_[1])))
                    except (ValueError, IndexError): pass
    return trim_restarts(rows).reshape(-1, 2)


def check_guard(p, p01, case, rotor="toroid"):
    L = guard_limits(p, p01, rotor)
    try: t, F, _, _, _ = read_forces(case)
    except (FileNotFoundError, IndexError, ValueError): return None
    m = t >= L["start"]
    if m.sum() < L["window"]: return None
    ct = F[m, 2][-L["window"]:] / L["qref"]
    if np.all(ct < L["ct_min"]): return f"CT below 0 for {L['window']} iterations (last {ct[-1]:.5f})"
    if np.all(ct > L["ct_max"]): return f"CT above {L['ct_max']:.5f} for {L['window']} iterations (last {ct[-1]:.5f})"
    bf = read_bottom_flow(case)
    bf = bf[bf[:, 0] >= L["start"]][-L["window"]:] if len(bf) else bf
    if len(bf) >= L["window"] and np.all(np.abs(bf[:, 1]) > L["flow_max"]):
        return f"outlet flow above {L['flow_max']:.0f} m^3/s for {L['window']} iterations (last {bf[-1, 1]:.0f})"
    return None


def foam_guarded(p, p01, case, log, rotor, poll_s=30):
    n = p["cfd"]["n_proc"]
    full = f"source /opt/openfoam13/etc/bashrc && mpirun --mca btl ^tcp -np {n} foamRun -parallel"
    with open(os.path.join(case, log), "w") as f:
        pr = subprocess.Popen(["bash", "-c", full], cwd=case, stdout=f, stderr=subprocess.STDOUT, start_new_session=True)
        reason = None
        while pr.poll() is None:
            time.sleep(poll_s)
            reason = check_guard(p, p01, case, rotor)
            if reason:
                os.killpg(pr.pid, signal.SIGTERM)
                try: pr.wait(timeout=120)
                except subprocess.TimeoutExpired: os.killpg(pr.pid, signal.SIGKILL); pr.wait()
                break
    save_json(f"guard_{rotor}.json", {"stopped_by_guard": bool(reason), "reason": reason, "returncode": pr.returncode, "limits": guard_limits(p, p01, rotor)})
    if reason: print("** GUARD STOPPED THE RUN: " + reason + " **", flush=True)
    return pr.returncode


def stage_run(p, p01, rotor="toroid"):
    case, n = case_dir(p, rotor), p["cfd"]["n_proc"]
    for i in range(n):
        for f in os.listdir(os.path.join(case, "0")):
            shutil.copy(os.path.join(case, "0", f), os.path.join(case, f"processor{i}", "0", f))
        for d_ in os.listdir(os.path.join(case, f"processor{i}")):
            if d_ not in ("0", "constant"): shutil.rmtree(os.path.join(case, f"processor{i}", d_))
    shutil.rmtree(os.path.join(case, "postProcessing"), ignore_errors=True)
    print("foamRun ->", foam_guarded(p, p01, case, "log.foamRun", rotor)); collect_logs(p, rotor)


def stage_smoke(p, p01, rotor="toroid", n_it="10"):
    """Start-up check: run n_it solver iterations, record seconds per iteration, the lowest free memory and the forces, then
    restore the case exactly (endTime, no time folders, no postProcessing) so `run` starts clean."""
    case, n = case_dir(p, rotor), p["cfd"]["n_proc"]; n_it = int(n_it)
    cd = os.path.join(case, "system", "controlDict"); txt = open(cd).read()
    open(cd, "w").write(re.sub(r"^endTime\s+\S+;", f"endTime         {n_it};", txt, flags=re.M))
    free0 = int(next(l.split()[1] for l in open("/proc/meminfo") if l.startswith("MemAvailable"))) / 1048576
    try:
        for i in range(n):
            for f in os.listdir(os.path.join(case, "0")):
                shutil.copy(os.path.join(case, "0", f), os.path.join(case, f"processor{i}", "0", f))
        rc = foam(case, "foamRun", "log.foamRun.smoke", parallel=n, mem_floor_gb=1.5)
        lg = open(os.path.join(case, "log.foamRun.smoke"), errors="replace").read()
        ex = [float(x) for x in re.findall(r"^ExecutionTime = ([\d.]+)", lg, re.M)]
        t, F, M, _, _ = read_forces(case)
        out = {"rotor": rotor, "returncode": rc, "iterations": len(ex), "s_per_iteration": (ex[-1] - ex[0]) / max(len(ex) - 1, 1) if len(ex) > 1 else None,
               "startup_s": ex[0] if ex else None, "fatal": "FOAM FATAL" in lg, "free_gb_before": free0, "free_gb_min": MEM_MIN_GB,
               "solver_memory_gb": free0 - MEM_MIN_GB, "thrust_last_N": float(F[-1, 2]), "torque_last_Nm": float(-M[-1, 2]),
               "all_finite": bool(np.all(np.isfinite(F)) and np.all(np.isfinite(M))), "mrf_zone_created": "creating MRF zone: rotor" in lg}
        n_est = p["cfd"]["meshes"][MESH]["iterations"]
        if out["s_per_iteration"]: out["estimated_run_h"] = n_est * out["s_per_iteration"] / 3600
    finally:
        open(cd, "w").write(txt)
        for i in range(n):
            for d_ in os.listdir(os.path.join(case, f"processor{i}")):
                if d_ not in ("0", "constant"): shutil.rmtree(os.path.join(case, f"processor{i}", d_))
        shutil.rmtree(os.path.join(case, "postProcessing"), ignore_errors=True)
    save_json(f"smoke_{rotor}.json", out); collect_logs(p, rotor)
    print(json.dumps(out, indent=1, default=float))


def stage_resume(p, p01, rotor="toroid"):
    case = case_dir(p, rotor)
    k = 1 + sum(1 for f in os.listdir(case) if f.startswith("log.foamRun.resume"))
    print("foamRun (resume) ->", foam_guarded(p, p01, case, f"log.foamRun.resume{k}", rotor)); collect_logs(p, rotor)


def latest_log(case):
    logs = [os.path.join(case, f) for f in os.listdir(case) if f.startswith("log.foamRun")]
    return max(logs, key=os.path.getmtime) if logs else None


def stage_status(p, p01, rotor="toroid"):
    case = case_dir(p, rotor); lg = latest_log(case)
    if not lg: print("not started"); return
    txt = open(lg, errors="replace").read()
    its = [int(float(x)) for x in re.findall(r"^Time = ([\d.]+)s?$", txt, re.M)]; ex = [float(x) for x in re.findall(r"^ExecutionTime = ([\d.]+)", txt, re.M)]
    if len(ex) < 3: print("starting up, no iterations yet"); return
    end = int(next((l.split()[1].rstrip(";") for l in open(os.path.join(case, "system", "controlDict")) if l.startswith("endTime")), 0))
    k = min(50, len(ex) - 1); per = (ex[-1] - ex[-1 - k]) / k
    s = load_json("sizing.json"); T_req = s["inputs"]["T_required"]
    t, F, M, _, _ = read_forces(case); T, Q = F[:, 2], -M[:, 2]; k2 = min(100, len(Q) - 1)
    dr = lambda y: 100 * (y[-1] - y[-1 - k2]) / abs(y[-1]) * 100 / k2
    bf = read_bottom_flow(case); L = guard_limits(p, p01, rotor)
    dT_ = f", {dr(T):+.2f} %/100 it" if k2 >= 50 else ", drift shown after 50 iterations"
    dQ_ = f" ({dr(Q):+.2f} %/100 it; converged below 0.5)" if k2 >= 50 else ""
    print(f"iteration {its[-1]} of {end}, {per:.1f} s/iteration, about {(end - its[-1]) * per / 3600:.1f} h left | thrust {T[-1]:.1f} N "
          f"({T[-1] / T_req:.3f} of the T/W 1.5 thrust{dT_}) | torque {Q[-1]:.2f} N m{dQ_}"
          + (f" | outlet flow {bf[-1, 1]:.0f} m^3/s (2 vi A = {L['wake_flow_momentum']:.0f})" if len(bf) else "")
          + ("  ** FATAL error in the log **" if "FOAM FATAL" in txt else "") + ("  (finished)" if its[-1] >= end else ""))


def motor_limited(T, Q, rpm, I):
    """The motor's real ceiling from one CFD point, at constant C_T and C_Q (T, Q ~ rpm^2): the speed limit
    (k_load KV V) or the torque limit (k_t I_peak), whichever the rotor reaches first."""
    q_max = I["kt"] * I["i_peak"]
    rpm_q = rpm * math.sqrt(q_max / Q)                               # speed at which this rotor's torque hits the limit
    rpm_lim = min(I["rpm_available_sag"], rpm_q)
    return {"motor_limit": "torque" if rpm_q < I["rpm_available_sag"] else "speed", "rpm_motor_limit": rpm_lim,
            "T_motor_limit": T * (rpm_lim / rpm) ** 2, "Q_motor_limit": Q * (rpm_lim / rpm) ** 2,
            "tw_max_motor": T * (rpm_lim / rpm) ** 2 / I["T_hover"]}


def stage_post(p, p01, rotor="toroid"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    case = case_dir(p, rotor); s = load_json("sizing.json"); I = s["inputs"]
    rho, A, R = I["air"]["rho"], I["A"], I["R"]; rpm = case_rpm(rotor); om = rpm * math.pi / 30
    t, F, M, Fv, Mv = read_forces(case); T, Q = F[:, 2], -M[:, 2]
    n = len(t); w = max(100, n // 5); last = slice(max(0, n - w), n)
    drift = lambda y: float(100 * (y[-1] - y[-w]) / abs(y[last].mean()) * 100 / w)
    Tm, Qm = float(T[last].mean()), float(Q[last].mean()); P = Qm * om
    fom = Tm ** 1.5 / math.sqrt(2 * rho * A) / P if Tm > 0 and P > 0 else None
    scale = I["T_required"] / Tm                                    # CT and CQ held: T ~ rpm^2, Q ~ rpm^2
    rpm_req = rpm * math.sqrt(scale)
    out = {"rotor": rotor, "rpm": rpm, "iterations": int(t[-1]), "window": int(w), "T": Tm, "Q": Qm, "P": P, "FoM": fom,
           "CT_h": Tm / (rho * A * (om * R) ** 2), "tw_at_cfd_rpm": Tm / I["T_hover"],
           "T_drift_pct_per100": drift(T), "Q_drift_pct_per100": drift(Q), "converged": abs(drift(T)) < 0.5 and abs(drift(Q)) < 0.5,
           "viscous_thrust_fraction": float(Fv[last, 2].mean() / Tm), "viscous_torque_fraction": float(-Mv[last, 2].mean() / Qm),
           "rpm_for_tw_required": rpm_req, "Q_at_tw_required": Qm * scale, "P_at_tw_required": Qm * scale * rpm_req * math.pi / 30,
           "motor_current_at_tw_required_a": Qm * scale / I["kt"], "motor_rpm_available": I["rpm_available_sag"],
           "tw_at_motor_rpm": Tm * (I["rpm_available_sag"] / rpm) ** 2 / I["T_hover"],          # speed limit only (kept for history)
           **motor_limited(Tm, Qm, rpm, I),
           "mesh": mesh_info(case)}
    if rpm == s["cfd_rpm"] and rotor in ("toroid", "reference"):
        hand = s["cfd_point_bemt"]
    else:                                                           # a variant, or another speed: plain BEMT at this case's speed
        db = build_polars(p01); pv = rotor_params(p, rotor)
        hand = {"legs_tip_loss": bemt_point(leg_blade(pv), db, I["air"], rpm), "legs_no_tip_loss": bemt_point(leg_blade(pv), db, I["air"], rpm, False),
                "reference": bemt_point(reference_blade(p01), db, I["air"], rpm)}
    out["vs_hand"] = [{"quantity": q_, "cfd": out[k_], **{h_: hand[h_][hk] for h_ in hand}} for q_, k_, hk in
                      (("Thrust [N]", "T", "T"), ("Torque [N m]", "Q", "Q"), ("Shaft power [W]", "P", "P"), ("Figure of merit", "FoM", "FoM"))]
    yp = os.path.join(case, "postProcessing", "yPlus", "0", "yPlus.dat")
    if os.path.exists(yp):
        rows = [l.split() for l in open(yp) if not l.startswith("#")]
        if rows: out["yplus"] = {"min": float(rows[-1][2]), "max": float(rows[-1][3]), "average": float(rows[-1][4])}
    save_json(f"cfd_{rotor}.json", out)
    fig, axs = plt.subplots(1, 2, figsize=(9, 3.2))
    axs[0].plot(t, T, color="#0b0b0b"); axs[0].axhline(I["T_required"], color="#2a78d6", ls="--", label="T/W 1.5 thrust per rotor")
    axs[0].set_xlabel("iteration"); axs[0].set_ylabel("thrust [N]"); axs[0].legend(fontsize=7); axs[0].grid(alpha=.3); axs[0].set_ylim(0, 1.6 * max(I["T_required"], Tm))
    axs[1].plot(t, Q, color="#0b0b0b"); axs[1].set_xlabel("iteration"); axs[1].set_ylabel("torque [N m]"); axs[1].grid(alpha=.3); axs[1].set_ylim(0, 1.6 * max(Qm, 1))
    fig.suptitle(f"{rotor} rotor, {rpm} rpm, hot day: convergence", fontsize=9); fig.tight_layout()
    fig.savefig(os.path.join(RESULTS, f"fig_convergence_{rotor}.png"), dpi=140); plt.close(fig)
    collect_logs(p, rotor)
    export_cfd_results(p, rotor, out, t, F, M, Fv, Mv)
    print(json.dumps({k: v for k, v in out.items() if k != "mesh"}, indent=1, default=float))
    return out


CFD_RESULTS = os.path.join(ROOT, "..", "..", "CFD_Results", "02_Toroidal_Rotor")


def export_cfd_results(p, rotor, out, t, F, M, Fv, Mv):
    """Shared results folder (agreed with the 54x18 session): CFD_Results/<project>/<case>/ holds a README, the summary
    JSON, the plots and the force history. No time or processor folders (hundreds of MB, regenerable from the case)."""
    dst = os.path.join(CFD_RESULTS, f"{rotor}_{MESH}")
    os.makedirs(dst, exist_ok=True)
    s = load_json("sizing.json"); I = s["inputs"]; case = load_json(f"case_{rotor}.json")
    mesh = out.get("mesh", {}); mm = p["cfd"]["meshes"][MESH]
    json.dump(out, open(os.path.join(dst, "summary.json"), "w"), indent=1, default=float)
    hist = np.column_stack([t, F[:, 2], -M[:, 2], Fv[:, 2], -Mv[:, 2]])
    np.savetxt(os.path.join(dst, "force_history.csv"), hist, delimiter=",", fmt=["%d", "%.4f", "%.5f", "%.4f", "%.5f"],
               header="iteration,thrust_N,torque_Nm,viscous_thrust_N,viscous_torque_Nm", comments="")
    for fig in (f"fig_convergence_{rotor}.png", "fig_geometry.png" if rotor == "toroid" else f"fig_geometry_{rotor}.png", f"fig_loads_{rotor}.png"):
        if os.path.exists(os.path.join(RESULTS, fig)):
            shutil.copy(os.path.join(RESULTS, fig), os.path.join(dst, fig))
    what = {"toroid": "2-loop (4-leg) toroidal rotor, 54 in, Props/02_Toroidal_Rotor geometry",
            "reference": "2-blade 54 in reference blade (Props/01_54x18_Composite Phase 3 prop_ccw.stl), same mesh recipe and speed as the toroid"}.get(
        rotor, f"toroidal rotor design variant {rotor}: {json.dumps(((p.get('variants') or {}).get(rotor) or {}).get('rotor', {}))}")
    rows = "\n".join(f"| {r['quantity']} | {r['cfd']:.3f} | {r['legs_tip_loss']:.3f} | {r['legs_no_tip_loss']:.3f} | {r['reference']:.3f} |" for r in out["vs_hand"])
    txt = f"""# {rotor}_{MESH}: {what}

Generated by `Props/02_Toroidal_Rotor/src/toroid.py post {rotor}`. Do not edit by hand.

## Case

- OpenFOAM 13, foamRun incompressibleFluid, steady SIMPLE, k-omega SST with Spalding wall functions; frozen-rotor MRF at
  {case['rpm']} rpm in a cylinder r = {case['mrf_radius']:.3f} m, |z| < {case['mrf_half_height']:.3f} m.
- Hot day: rho = {I['air']['rho']:.4f} kg/m^3, nu = {I['air']['nu']:.3e} m^2/s.
- Domain: cylinder r = {case['radius']:.2f} m (5 D), {-case['z0']:.2f} m below, {case['z1']:.2f} m above. Total-pressure top and side, fixed-pressure outlet.
- Mesh: {case['base_cell']} m core, {case['surface_cell_mm']:.2f} mm on the blade, curvature-refined to {case['curvature_cell_mm']:.2f} mm,
  {mm['n_layers']} relative prism layers. Cells {mesh.get('cells')}, checkMesh OK: {mesh.get('mesh_ok')},
  max non-orthogonality {mesh.get('max_non_orthogonality')}, layer coverage {mesh.get('layer_coverage_pct')} %.
- {out['iterations']} iterations; drift over the last {out['window']}: thrust {out['T_drift_pct_per100']:+.2f} %, torque {out['Q_drift_pct_per100']:+.2f} %
  per 100 iterations ({'converged' if out['converged'] else 'NOT converged'}, limit 0.5 %).

## Result

| Quantity | CFD | BEMT, 4 legs with tip loss | BEMT, 4 legs closed tip | BEMT, 2-blade reference |
|---|---|---|---|---|
{rows}

The BEMT columns are the hand calculations at the same {case['rpm']} rpm. T/W at {case['rpm']} rpm:
{out['tw_at_cfd_rpm']:.3f}. Scaled at constant C_T to the T/W 1.5 thrust ({I['T_required']:.1f} N per rotor): {out['rpm_for_tw_required']:.0f} rpm,
{out['Q_at_tw_required']:.2f} N m, {out['P_at_tw_required']:.0f} W, {out['motor_current_at_tw_required_a']:.0f} A on the U15XL
(180 A peak, {out['motor_rpm_available']:.0f} rpm available). Viscous share: thrust {100 * out['viscous_thrust_fraction']:.1f} %, torque {100 * out['viscous_torque_fraction']:.1f} %.

## Files

| File | What |
|---|---|
| `summary.json` | All numbers above, mesh statistics, y+ |
| `force_history.csv` | Thrust and torque (total and viscous) per iteration |
| `fig_convergence_{rotor}.png` | Thrust and torque against iteration |

Full case setup and solver logs: `Props/02_Toroidal_Rotor/cfd/{rotor}_{MESH}/`. The case itself (time and processor folders)
stays under `{p['cfd']['run_root']}`.
"""
    open(os.path.join(dst, "README.md"), "w").write(txt)
    print("exported to", os.path.relpath(dst, os.path.join(ROOT, "..", "..")))


# ---- stage: loads (where along the loop thrust and torque come from) -------------------------------------------
def stage_loads(p, p01, rotor="toroid", time_="1500"):
    """Splits the CFD pressure force by loop segment and radius. Needs <case>/surface_<time>.npz from
    `pvpython src/extract_surface.py <case> <rotor>.foam <time> <case>/surface_<time>.npz`. Pressure only (the viscous part is
    13 % of the torque and ~0 of the thrust in the totals). Each face is assigned to the nearest ring point of the loop
    definition, so it inherits that station's segment and radius."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from scipy.spatial import cKDTree
    case = case_dir(p, rotor); s = load_json("sizing.json"); I = s["inputs"]; rho = I["air"]["rho"]; rpm = case_rpm(rotor); om = rpm * math.pi / 30
    p = rotor_params(p, rotor)
    d = np.load(os.path.join(case, f"surface_{time_}.npz"))
    cen, S, pk = d["cen"], d["S"], d["p"]
    F = rho * pk[:, None] * S                                       # force on the body (patch normal points into the body)
    Mz = cen[:, 0] * F[:, 1] - cen[:, 1] * F[:, 0]
    out = {"rotor": rotor, "time": float(d["time"]), "faces": int(len(pk)), "Fz_pressure": float(F[:, 2].sum()), "Q_pressure": float(-Mz.sum())}
    rings, path, frames = loop_rings(p)
    nl = p["rotor"]["n_loops"]
    ang = np.arctan2(cen[:, 1], cen[:, 0]); k_loop = np.round(ang / (2 * math.pi / nl)).astype(int) % nl
    a = -2 * math.pi * k_loop / nl                                   # rotate every face back into loop 0
    loc = np.column_stack([cen[:, 0] * np.cos(a) - cen[:, 1] * np.sin(a), cen[:, 0] * np.sin(a) + cen[:, 1] * np.cos(a), cen[:, 2]])
    m = rings.shape[1]
    dist, idx = cKDTree(rings.reshape(-1, 3)).query(loc)
    st = idx // m
    seg = path["seg"][st].astype(int)
    out["assign_max_distance_mm"] = float(1000 * dist.max())
    names = ["leading leg", "tip turn", "trailing leg", "root turn"]
    out["segments"] = {names[k]: {"Fz": float(F[seg == k, 2].sum()), "Q": float(-Mz[seg == k].sum()),
                                  "area_m2": float(np.linalg.norm(S[seg == k], axis=1).sum())} for k in range(4)}
    # spanwise thrust and torque per unit radius on each leg (both loops added, then per leg)
    R = path["R"]; edges = np.linspace(path["r0"], path["rt"], 25); rm = 0.5 * (edges[1:] + edges[:-1]); dr = np.diff(edges)
    rs = path["r"][st]
    span = {}
    for k in (0, 2):
        sel = seg == k
        Tz = np.array([F[sel & (rs >= a_) & (rs < b_), 2].sum() for a_, b_ in zip(edges[:-1], edges[1:])]) / nl / dr
        Qz = np.array([-Mz[sel & (rs >= a_) & (rs < b_)].sum() for a_, b_ in zip(edges[:-1], edges[1:])]) / nl / dr
        c_, _, _ = leg_props(p, rm)
        span[names[k]] = {"dT_dr": Tz.tolist(), "dQ_dr": Qz.tolist(), "cn": (Tz / (0.5 * rho * (om * rm) ** 2 * c_)).tolist()}
    db = build_polars(p01)
    b = bemt.axial(leg_blade(p), db, I["air"], rpm, 0.0, n=60)
    per_leg = np.interp(rm, b["r"], b["dT_dr"]) / leg_blade(p).N
    per_leg_q = np.interp(rm, b["r"], b["dQ_dr"]) / leg_blade(p).N
    out["span"] = {"r": rm.tolist(), "r_over_R": (rm / R).tolist(), "bemt_dT_dr_per_leg": per_leg.tolist(), "bemt_dQ_dr_per_leg": per_leg_q.tolist(),
                   "bemt_cl_per_leg": np.interp(rm, b["r"], b["cl"]).tolist(), "bemt_alpha_deg": np.degrees(np.interp(rm, b["r"], b["alpha"])).tolist(), **span}
    out["leg_thrust_ratio_trailing_to_leading"] = out["segments"]["trailing leg"]["Fz"] / out["segments"]["leading leg"]["Fz"]
    out["bemt_leg_thrust_each"] = float(np.sum(per_leg * dr)) * nl
    save_json(f"loads_{rotor}.json", out)
    fig, axs = plt.subplots(1, 3, figsize=(13, 3.6))
    for k, col in (("leading leg", "#0b0b0b"), ("trailing leg", "#2a78d6")):
        axs[0].plot(rm / R, span[k]["dT_dr"], color=col, label=f"CFD {k}")
        axs[1].plot(rm / R, span[k]["dQ_dr"], color=col, label=f"CFD {k}")
        axs[2].plot(rm / R, span[k]["cn"], color=col, label=f"CFD {k}")
    axs[0].plot(rm / R, per_leg, color="#c0392b", ls="--", label="BEMT, per leg"); axs[1].plot(rm / R, per_leg_q, color="#c0392b", ls="--", label="BEMT, per leg")
    axs[2].plot(rm / R, out["span"]["bemt_cl_per_leg"], color="#c0392b", ls="--", label="BEMT cl")
    for ax_, yl in zip(axs, ("thrust per leg per metre [N/m]", "torque per leg per metre [N m/m]", "section force coefficient")):
        ax_.set_xlabel("r / R"); ax_.set_ylabel(yl); ax_.grid(alpha=.3); ax_.legend(fontsize=7)
    fig.suptitle(f"{rotor}, {rpm} rpm: where the loop makes its thrust (pressure forces, iteration {time_})", fontsize=9); fig.tight_layout()
    fig.savefig(os.path.join(RESULTS, f"fig_loads_{rotor}.png"), dpi=140); plt.close(fig)
    print(json.dumps({k: v for k, v in out.items() if k != "span"}, indent=1))
    return out


if __name__ == "__main__":
    P, P01 = load_params()
    globals()["stage_" + sys.argv[1]](P, P01, *sys.argv[2:])

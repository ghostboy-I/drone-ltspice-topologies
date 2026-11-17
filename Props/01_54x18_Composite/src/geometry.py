"""Phase 3: parametric propeller geometry. Reads results/blade_final.csv, smooths it, lofts NACA sections with the
OpenCASCADE kernel in gmsh (driven by a generated .geo script), unions two blades with a hub disc, and exports STEP
(mm) and STL for the CCW and the mirrored CW propeller. Then checks the result independently by slicing the STL.

Axes: z is the rotor axis, thrust is +z. Blade 1 lies along +x. The CCW prop turns counter-clockwise seen from above
(from +z), so blade 1 moves toward +y and its leading edge points to +y. A section at radius r, chord c, twist theta:
    P = (r, 0, 0) + (x_stack - xc) c e_chord + yc c e_normal,   e_chord = (0, cos t, sin t),  e_normal = (0, -sin t, cos t)
with (xc, yc) the unit airfoil (xc from leading to trailing edge, yc positive on the suction side).
The CW prop is the mirror image in the x-z plane (y -> -y). A mirror, not a rotation: rotating a CCW prop can never
make a CW one. After mirroring, the CW prop turning clockwise still pushes air down and thrust stays +z.
"""
import json, math, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from scipy.interpolate import PchipInterpolator
from common import ROOT, RESULTS, load_params, save_json

GEOM = os.path.join(ROOT, "geometry")


def naca4(tc, m, pc, n, closed_te=False):
    """Unit-chord NACA 4-digit section. Returns upper and lower (x, y), leading to trailing edge. The standard formula
    leaves a small blunt trailing edge; closed_te uses the modified last coefficient (-0.1036) that closes it."""
    x = 0.5 * (1 - np.cos(np.linspace(0, math.pi, n)))
    yt = 5 * tc * (0.2969 * np.sqrt(x) - 0.1260 * x - 0.3516 * x ** 2 + 0.2843 * x ** 3 - (0.1036 if closed_te else 0.1015) * x ** 4)
    if m == 0:
        return (x, yt), (x, -yt)
    yc = np.where(x < pc, m / pc ** 2 * (2 * pc * x - x ** 2), m / (1 - pc) ** 2 * ((1 - 2 * pc) + 2 * pc * x - x ** 2))
    dyc = np.where(x < pc, 2 * m / pc ** 2 * (pc - x), 2 * m / (1 - pc) ** 2 * (pc - x))
    th = np.arctan(dyc)
    return (x - yt * np.sin(th), yc + yt * np.cos(th)), (x + yt * np.sin(th), yc - yt * np.cos(th))


def load_table():
    d = np.loadtxt(os.path.join(RESULTS, "blade_final.csv"), delimiter=",", comments="#", skiprows=2)
    return {"r": d[:, 0], "x": d[:, 1], "chord": d[:, 2], "twist": np.radians(d[:, 3]), "tc": d[:, 4]}


def smooth_definition(p, tab):
    """Monotone cubic (PCHIP) through a reduced set of stations: C1-continuous, no overshoot, removes the kinks left by
    the chord cap and the root blend. Returns callables chord(x), twist(x), tc(x) on x = r/R."""
    g = p["geometry"]
    xc = np.array(g["control_r_over_R"])
    chord = PchipInterpolator(xc, np.interp(xc, tab["x"], tab["chord"]), extrapolate=True)
    twist = PchipInterpolator(xc, np.interp(xc, tab["x"], tab["twist"]), extrapolate=True)
    return chord, twist


def stations(p, R):
    """Section radii, chord, twist and thickness for the loft (root inside the hub, rounded tip)."""
    g, d, rh = p["geometry"], p["design"], p["rotor"]["hub_radius_m"]
    tab = load_table()
    chord_f, twist_f = smooth_definition(p, tab)
    x0, xc0 = g["root_start_fraction_of_hub"] * rh / R, g["control_r_over_R"][0]
    beta = np.linspace(0, math.pi / 2, g["n_sections"])
    x = x0 + (1 - x0) * np.sin(beta)                                  # clustered toward the tip
    xe = np.clip(x, xc0, 1.0)                                         # inboard of the first BEMT station: hold values
    c, th = chord_f(xe), twist_f(xe)
    xt = g["tip_round_start_r_over_R"]
    s = np.clip((x - xt) / (1 - xt), 0, 1)
    f_tip = g["tip_chord_fraction"]
    c = c * (f_tip + (1 - f_tip) * np.sqrt(1 - s ** 2))               # elliptical rounding to tip_chord_fraction
    xr, xh = g["root_transition_r_over_R"], rh / R
    u = np.clip((xr - x) / (xr - xh), 0, 1)
    w = u * u * (3 - 2 * u)                                           # smoothstep: C1 blend from blade to shank
    c = (1 - w) * c + w * g["root_chord_over_hub_radius"] * rh
    stack = (1 - w) * g["stacking_x_over_c"] + w * g["root_stacking_x_over_c"]
    tc = np.interp(x, d["tc_r_over_R"], d["tc"])
    xb = d["root_blend_r_over_R"]
    tc = np.where(x < xb, d["tc"][0] + (g["root_tc"] - d["tc"][0]) * np.clip((xb - x) / (xb - xh), 0, 1), tc)
    return {"x": x, "r": x * R, "chord": c, "twist": th, "tc": tc, "stack": stack}


def section_points(p, r, c, th, tc, mirror=False, stack=None):
    """Closed polygon of one section in global coordinates [m]: trailing edge (upper) -> leading edge -> trailing edge (lower)."""
    g = p["geometry"]
    (xu, yu), (xl, yl) = naca4(tc, g["camber"], g["camber_position"], g["n_airfoil_points"])
    xs, ys = np.concatenate([xu[::-1], xl[1:]]), np.concatenate([yu[::-1], yl[1:]])
    a = ((g["stacking_x_over_c"] if stack is None else stack) - xs) * c
    y = a * math.cos(th) - ys * c * math.sin(th)
    z = a * math.sin(th) + ys * c * math.cos(th)
    return np.column_stack([np.full_like(y, r), -y if mirror else y, z])


def write_geo(p, st, name, mirror):
    """gmsh script in millimetres: one spline + trailing-edge line per section, ThruSections loft, second blade by a
    half turn, hub disc, boolean union, STEP and STL export."""
    g, rh = p["geometry"], p["rotor"]["hub_radius_m"]
    L = ['SetFactory("OpenCASCADE");', "Geometry.OCCTargetUnit = \"MM\";"]
    pid, cid, wires = 0, 0, []
    zmin, zmax = 1e9, -1e9
    for r, c, th, tc, sk in zip(st["r"], st["chord"], st["twist"], st["tc"], st["stack"]):
        P = section_points(p, r, c, th, tc, mirror, sk) * 1000.0
        if r <= rh * 1.05:
            zmin, zmax = min(zmin, P[:, 2].min()), max(zmax, P[:, 2].max())
        ids = []
        for q in P:
            pid += 1; ids.append(pid); L.append(f"Point({pid}) = {{{q[0]:.6f}, {q[1]:.6f}, {q[2]:.6f}}};")
        cid += 1; L.append(f"Spline({cid}) = {{{', '.join(map(str, ids))}}};")
        cid += 1; L.append(f"Line({cid}) = {{{ids[-1]}, {ids[0]}}};")
        wires.append(len(wires) + 1); L.append(f"Wire({wires[-1]}) = {{{cid - 1}, {cid}}};")
    z0, h = zmin - 1000 * g["hub_margin_m"], (zmax - zmin) + 2000 * g["hub_margin_m"]
    L += [f"ThruSections(1) = {{{', '.join(map(str, wires))}}};",
          "Rotate {{0, 0, 1}, {0, 0, 0}, Pi} { Duplicata { Volume{1}; } }",
          f"Cylinder(10) = {{0, 0, {z0:.6f}, 0, 0, {h:.6f}, {1000 * rh:.6f}}};",
          "BooleanUnion(20) = { Volume{10}; Delete; }{ Volume{1, 2}; Delete; };",
          f"Mesh.MeshSizeMin = {g['mesh_size_min_mm']}; Mesh.MeshSizeMax = {g['mesh_size_max_mm']};",
          f"Mesh.MeshSizeFromCurvature = {g['mesh_curvature_elements']}; Mesh.Algorithm = 6;",
          f'Save "{name}.step";', "Mesh 2;", "Mesh.Binary = 1;", f'Save "{name}_mm.stl";']
    os.makedirs(GEOM, exist_ok=True)
    path = os.path.join(GEOM, f"{name}.geo")
    open(path, "w").write("\n".join(L) + "\n")
    return path, {"hub_z0_mm": z0, "hub_height_mm": h}


def run_gmsh(geo):
    r = subprocess.run(["gmsh", os.path.basename(geo), "-"], cwd=GEOM, capture_output=True, text=True, timeout=1800)
    open(geo.replace(".geo", ".gmsh.txt"), "w").write(r.stdout + r.stderr)
    if r.returncode != 0:
        raise RuntimeError(f"gmsh failed on {geo}: {(r.stdout + r.stderr)[-800:]}")


# ---- STL utilities (independent of gmsh) ---------------------------------------------------------------------
def read_stl(path):
    raw = open(path, "rb").read()
    n = int(np.frombuffer(raw[80:84], "<u4")[0])
    rec = np.frombuffer(raw[84:84 + 50 * n], dtype=np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]))
    return rec["v"].astype(float)                      # (n, 3, 3)


def write_stl(path, tris, name="prop"):
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-30)
    with open(path, "w") as f:                         # ASCII, single named solid: OpenFOAM uses the name as the patch
        f.write(f"solid {name}\n")
        for t, nn in zip(tris, n):
            f.write(f" facet normal {nn[0]:.6e} {nn[1]:.6e} {nn[2]:.6e}\n  outer loop\n")
            for v in t: f.write(f"   vertex {v[0]:.8e} {v[1]:.8e} {v[2]:.8e}\n")
            f.write("  endloop\n endfacet\n")
        f.write(f"endsolid {name}\n")


def mesh_stats(tris, tol=1e-9):
    """Watertightness (every edge shared by exactly two triangles, with opposite directions), volume, centroid and
    inertia about z for unit density, all by the divergence theorem."""
    scale = np.abs(tris).max()
    key = np.round(tris.reshape(-1, 3) / (scale * 1e-7)).astype(np.int64)
    _, idx = np.unique(key, axis=0, return_inverse=True)
    f = idx.reshape(-1, 3)
    e = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
    und = np.sort(e, axis=1)
    _, cnt = np.unique(und, axis=0, return_counts=True)
    dirs, dcnt = np.unique(e, axis=0, return_counts=True)
    a, b, c = tris[:, 0], tris[:, 1], tris[:, 2]
    det = np.einsum("ij,ij->i", a, np.cross(b, c))
    vol = det.sum() / 6.0
    cen = ((a + b + c) / 4.0 * det[:, None]).sum(axis=0) / 6.0 / vol
    def second(i):                                     # integral of x_i^2 over the solid
        return (det / 60.0 * (a[:, i] ** 2 + b[:, i] ** 2 + c[:, i] ** 2 + a[:, i] * b[:, i] + a[:, i] * c[:, i] + b[:, i] * c[:, i])).sum()
    area = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    return {"triangles": int(len(tris)), "vertices": int(key.shape[0] and idx.max() + 1), "edges_not_shared_by_two": int((cnt != 2).sum()),
            "edges_with_inconsistent_orientation": int((dcnt != 1).sum()), "volume": float(vol), "centroid": cen.tolist(),
            "izz_unit_density": float(second(0) + second(1)), "surface_area": float(area.sum()),
            "min_triangle_area": float(area.min()), "degenerate_triangles": int((area < tol * area.max()).sum()),
            "bbox_min": tris.reshape(-1, 3).min(axis=0).tolist(), "bbox_max": tris.reshape(-1, 3).max(axis=0).tolist()}


def slice_section(tris, r):
    """Cut the surface with the plane x = r. Returns the measured chord, twist, max thickness, which way the leading
    edge points (sign of y), whether the nose is pitched toward +z, and whether the camber bulges toward +z."""
    x = tris[:, :, 0]
    m = (x.min(axis=1) < r) & (x.max(axis=1) > r)
    pts = []
    for t in tris[m]:
        for i, j in ((0, 1), (1, 2), (2, 0)):
            a, b = t[i], t[j]
            if (a[0] - r) * (b[0] - r) < 0:
                s = (r - a[0]) / (b[0] - a[0]); pts.append(a[1:] + s * (b[1:] - a[1:]))
    P = np.array(pts)
    hull = P[np.argsort(P[:, 0])]
    d2 = ((P[:, None, :] - P[None, :, :]) ** 2).sum(-1)
    i, j = np.unravel_index(np.argmax(d2), d2.shape)
    A, B = P[i], P[j]
    chord = math.sqrt(d2[i, j])
    u = (B - A) / chord; nrm = np.array([-u[1], u[0]])
    s, t = (P - A) @ u / chord, (P - A) @ nrm
    thick = lambda lo, hi: np.ptp(t[(s >= lo) & (s <= hi)]) if ((s >= lo) & (s <= hi)).sum() > 1 else 0.0
    le_is_A = thick(0.02, 0.12) > thick(0.88, 0.98)            # the nose is the thick, round end
    LE, TE = (A, B) if le_is_A else (B, A)
    e = (LE - TE) / chord; up = np.array([-e[1], e[0]]) * (1 if e[0] > 0 else -1)     # normal with +z component for a level chord
    if up[1] < 0: up = -up
    off = (P - TE) @ up
    sc = (P - TE) @ e / chord
    mid = (sc > 0.3) & (sc < 0.6)
    camber_mid = 0.5 * (off[mid].max() + off[mid].min())
    return {"r": r, "chord": chord, "twist_deg": math.degrees(math.atan2(LE[1] - TE[1], abs(LE[0] - TE[0]))), "thickness": float(np.ptp(off)),
            "le_y_sign": int(np.sign(LE[0] - TE[0])), "nose_up": bool(LE[1] > TE[1]), "camber_toward_plus_z": bool(camber_mid > 0), "n_points": int(len(P))}


def normal_extent(p, tc):
    """Extent of the unit section normal to its chord line (upper-surface maximum minus lower-surface minimum). This
    is what a slice measures; it is larger than t/c on a cambered section."""
    g = p["geometry"]
    (xu, yu), (xl, yl) = naca4(tc, g["camber"], g["camber_position"], 201)
    return float(yu.max() - yl.min())


def surface_check(stl_m, name):
    """OpenFOAM surfaceCheck and surfaceFeatures on the metre-scaled STL, in a throwaway case folder."""
    import shutil
    case = os.path.join(os.path.expanduser(load_params()["cfd"]["run_root"]), "geometry_check")     # no spaces allowed in OpenFOAM paths
    logs = os.path.join(ROOT, "cfd", "geometry_check"); os.makedirs(logs, exist_ok=True)
    os.makedirs(os.path.join(case, "constant", "geometry"), exist_ok=True); os.makedirs(os.path.join(case, "system"), exist_ok=True)
    shutil.copy(stl_m, os.path.join(case, "constant", "geometry", f"{name}.stl"))
    hdr = lambda cls, obj: f"FoamFile\n{{\n    format ascii;\n    class {cls};\n    object {obj};\n}}\n"
    open(os.path.join(case, "system", "controlDict"), "w").write(hdr("dictionary", "controlDict") + "application foamRun;\nstartTime 0;\nendTime 1;\ndeltaT 1;\nwriteInterval 1;\n")
    open(os.path.join(case, "system", "surfaceFeaturesDict"), "w").write(hdr("dictionary", "surfaceFeaturesDict") + f'surfaces ("{name}.stl");\nincludedAngle 150;\nsubsetFeatures {{ nonManifoldEdges yes; openEdges yes; }}\nwriteObj yes;\n')
    src = "source /opt/openfoam13/etc/bashrc && "
    r1 = subprocess.run(["bash", "-c", src + f'surfaceCheck "constant/geometry/{name}.stl"'], cwd=case, capture_output=True, text=True, timeout=900)
    r2 = subprocess.run(["bash", "-c", src + "surfaceFeatures"], cwd=case, capture_output=True, text=True, timeout=900)
    open(os.path.join(logs, f"surfaceCheck_{name}.txt"), "w").write(r1.stdout + r1.stderr)
    open(os.path.join(logs, f"surfaceFeatures_{name}.txt"), "w").write(r2.stdout + r2.stderr)
    out = r1.stdout
    grab = lambda key: next((l.strip() for l in out.splitlines() if key in l), None)
    feat = next((l.strip() for l in r2.stdout.splitlines() if "feature edges" in l.lower() or "Initial feature set" in l), None)
    return {"returncode": r1.returncode, "closed_line": grab("closed"), "illegal_line": grab("llegal"), "quality_line": grab("quality"),
            "unconnected_line": grab("unconnected parts"), "features_returncode": r2.returncode, "features_line": feat,
            "emesh_written": any(f.startswith(name) and f.endswith("eMesh") for f in os.listdir(os.path.join(case, "constant", "geometry")))
            or os.path.exists(os.path.join(case, "constant", "geometry", f"{name}.extendedFeatureEdgeMesh")), "case_dir": case}


def run():
    import bemt, airfoils, atmosphere as atm
    p = load_params()
    c = p["constants"]; R = p["rotor"]["diameter_in"] * c["inch_to_m"] / 2
    ph2 = json.load(open(os.path.join(RESULTS, "phase2.json")))
    st = stations(p, R)
    out = {"stations": {k: v.tolist() for k, v in st.items()}}

    # smoothing must not change the aerodynamics: BEMT on the table vs on the lofted definition
    db, _ = airfoils.build_db(p)
    hot = atm.state(p["atmospheres"][p["design_atmosphere"]]["temp_c"], p["atmospheres"][p["design_atmosphere"]]["alt_m"])
    t_h = ph2["candidates"]["final design"]["hover"]["T"]
    tab = load_table()
    rh = p["rotor"]["hub_radius_m"]
    b_tab = bemt.Blade(R, rh, p["rotor"]["n_blades"], tab["r"], tab["chord"], tab["twist"], tab["tc"])
    m = st["r"] >= rh
    b_geo = bemt.Blade(R, rh, p["rotor"]["n_blades"], st["r"][m], st["chord"][m], st["twist"][m], np.minimum(st["tc"][m], 0.18))
    h0, h1 = bemt.hover_at_thrust(b_tab, db, hot, t_h), bemt.hover_at_thrust(b_geo, db, hot, t_h)
    WS = (tab["x"] >= p["geometry"]["root_transition_r_over_R"]) & (tab["x"] < p["geometry"]["tip_round_start_r_over_R"])
    out["smoothing_check"] = {"table": {k: h0[k] for k in ("rpm", "P", "Q", "FoM")}, "lofted": {k: h1[k] for k in ("rpm", "P", "Q", "FoM")},
                              "rpm_diff_pct": 100 * (h1["rpm"] / h0["rpm"] - 1), "power_diff_pct": 100 * (h1["P"] / h0["P"] - 1),
                              "max_chord_change_mm": 1000 * float(np.max(np.abs(np.interp(tab["x"][WS], st["x"], st["chord"]) - tab["chord"][WS]))),
                              "max_twist_change_deg": float(np.degrees(np.max(np.abs(np.interp(tab["x"][WS], st["x"], st["twist"]) - tab["twist"][WS])))),
                              "compared_span": [p["geometry"]["root_transition_r_over_R"], p["geometry"]["tip_round_start_r_over_R"]]}

    check_x = [0.30, 0.50, 0.75, 0.90, 0.97]
    for name, mirror in (("prop_ccw", False), ("prop_cw", True)):
        geo, hub = write_geo(p, st, name, mirror)
        run_gmsh(geo)
        tris_mm = read_stl(os.path.join(GEOM, f"{name}_mm.stl"))
        tris = tris_mm / 1000.0
        stl_m = os.path.join(GEOM, f"{name}.stl"); write_stl(stl_m, tris, name)
        ms_ = mesh_stats(tris)
        sl = []
        for xq in check_x:
            s = slice_section(tris, xq * R)
            s.update(x=xq, chord_target=float(np.interp(xq, st["x"], st["chord"])), twist_target_deg=float(np.degrees(np.interp(xq, st["x"], st["twist"]))),
                     thickness_target=normal_extent(p, float(np.interp(xq, st["x"], st["tc"]))) * float(np.interp(xq, st["x"], st["chord"])))
            s["chord_err_pct"] = 100 * (s["chord"] / s["chord_target"] - 1); s["twist_err_deg"] = s["twist_deg"] - s["twist_target_deg"]
            s["thickness_err_pct"] = 100 * (s["thickness"] / s["thickness_target"] - 1)
            sl.append(s)
        # handedness: blade 1 is on +x. Positive lift needs the nose leading, so the blade must move toward its leading edge.
        le = sl[2]["le_y_sign"]
        hand = {"rotation": "CCW (counter-clockwise from above)" if le > 0 else "CW (clockwise from above)", "rotation_sign": le,
                "thrust_direction": "+z" if (sl[2]["nose_up"] and sl[2]["camber_toward_plus_z"]) else "NOT +z",
                "consistent_along_span": bool(all(s["le_y_sign"] == le and s["nose_up"] and s["camber_toward_plus_z"] for s in sl))}
        # BEMT on the geometry measured back from the STL (chord and twist from slices on a finer set of radii)
        xs = np.linspace(0.12, 0.985, 24)
        meas = [slice_section(tris, x_ * R) for x_ in xs]
        b_meas = bemt.Blade(R, rh, p["rotor"]["n_blades"], xs * R, [q["chord"] for q in meas], np.radians([q["twist_deg"] for q in meas]),
                            np.minimum(np.interp(xs, st["x"], st["tc"]), 0.18))            # chord and twist measured; t/c from the schedule
        hm = bemt.axial(b_meas, db, hot, h1["rpm"])
        out[name] = {"hub": hub, "mesh": ms_, "slices": sl, "handedness": hand, "surfaceCheck": surface_check(stl_m, name),
                     "bemt_from_stl": {"rpm": h1["rpm"], "T": hm["T"], "P": hm["P"], "T_vs_design_pct": 100 * (hm["T"] / t_h - 1)},
                     "step_bytes": os.path.getsize(os.path.join(GEOM, f"{name}.step"))}
        print(f"  {name}: {ms_['triangles']} triangles, open edges {ms_['edges_not_shared_by_two']}, volume {ms_['volume']*1e6:.0f} cm3, {hand['rotation']}, thrust {hand['thrust_direction']}", flush=True)

    # volume: CAD vs the strip estimate used in Phase 2 (hand calc vs CAD)
    import design_opt as do
    hubv = math.pi * rh ** 2 * out["prop_ccw"]["hub"]["hub_height_mm"] / 1000
    strip = do.naca4_area_factor() * float(np.trapezoid(st["tc"][m] * st["chord"][m] ** 2, st["r"][m]))
    dens = p["design"]["laminate_density_kg_m3"]
    v = out["prop_ccw"]["mesh"]["volume"]
    out["volume_check"] = {"cad_total_cm3": 1e6 * v, "hub_cylinder_cm3": 1e6 * hubv, "cad_blades_cm3_each": 1e6 * (v - hubv) / 2, "strip_estimate_cm3_each": 1e6 * strip,
                           "diff_pct": 100 * ((v - hubv) / 2 / strip - 1), "solid_mass_kg": v * dens, "izz_solid_kg_m2": out["prop_ccw"]["mesh"]["izz_unit_density"] * dens,
                           "density_placeholder": dens}
    a, b = out["prop_ccw"], out["prop_cw"]
    out["cw_ccw"] = {"volume_diff_pct": 100 * (b["mesh"]["volume"] / a["mesh"]["volume"] - 1), "izz_diff_pct": 100 * (b["mesh"]["izz_unit_density"] / a["mesh"]["izz_unit_density"] - 1),
                     "thrust_diff_pct": 100 * (b["bemt_from_stl"]["T"] / a["bemt_from_stl"]["T"] - 1), "opposite_rotation": a["handedness"]["rotation_sign"] == -b["handedness"]["rotation_sign"],
                     "same_thrust_direction": a["handedness"]["thrust_direction"] == b["handedness"]["thrust_direction"] == "+z"}
    save_json("phase3.json", out)
    plot(p, st, out, R)
    return out


def plot(p, st, out, R):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    tab = load_table()
    fig = plt.figure(figsize=(9.5, 6.4))
    ax = fig.add_subplot(2, 2, 1); ax.plot(tab["x"], 1000 * tab["chord"], ".", color="#8e8d88", ms=4, label="BEMT table"); ax.plot(st["x"], 1000 * st["chord"], color="#0b0b0b", label="lofted definition")
    ax.set_xlabel("r / R"); ax.set_ylabel("chord [mm]"); ax.legend(fontsize=7); ax.grid(alpha=.3)
    ax = fig.add_subplot(2, 2, 2); ax.plot(tab["x"], np.degrees(tab["twist"]), ".", color="#8e8d88", ms=4); ax.plot(st["x"], np.degrees(st["twist"]), color="#0b0b0b")
    ax.plot(st["x"], 100 * st["tc"], color="#2a78d6", label="t/c [%]"); ax.set_xlabel("r / R"); ax.set_ylabel("twist [deg]"); ax.legend(fontsize=7); ax.grid(alpha=.3)
    ax = fig.add_subplot(2, 2, 3)
    le = st["stack"] * st["chord"] * np.cos(st["twist"]); te = -(1 - st["stack"]) * st["chord"] * np.cos(st["twist"])
    for r, a_, b_ in zip(st["r"], le, te):
        ax.plot([r, r], [1000 * b_, 1000 * a_], color="#d6d5d0", lw=0.6)
    ax.plot(st["r"], 1000 * le, color="#0b0b0b"); ax.plot(st["r"], 1000 * te, color="#0b0b0b"); ax.plot(-st["r"], -1000 * le, color="#0b0b0b"); ax.plot(-st["r"], -1000 * te, color="#0b0b0b")
    t = np.linspace(0, 2 * math.pi, 100); ax.plot(p["rotor"]["hub_radius_m"] * np.cos(t), 1000 * p["rotor"]["hub_radius_m"] * np.sin(t), color="#c0392b")
    ax.set_aspect(0.001); ax.set_xlabel("x [m]"); ax.set_ylabel("y [mm]"); ax.set_title("CCW prop, planform from above (leading edges toward rotation)", fontsize=8); ax.grid(alpha=.3)
    ax = fig.add_subplot(2, 2, 4)
    for xq, col in ((0.25, "#c0392b"), (0.5, "#0b0b0b"), (0.75, "#2a78d6"), (0.95, "#3a9a5c")):
        P = section_points(p, xq * R, float(np.interp(xq, st["x"], st["chord"])), float(np.interp(xq, st["x"], st["twist"])), float(np.interp(xq, st["x"], st["tc"])))
        ax.plot(1000 * np.append(P[:, 1], P[0, 1]), 1000 * np.append(P[:, 2], P[0, 2]), color=col, label=f"r/R {xq}")
    ax.set_aspect("equal"); ax.set_xlabel("y [mm] (direction of motion →)"); ax.set_ylabel("z [mm] (thrust ↑)"); ax.legend(fontsize=7); ax.grid(alpha=.3)
    fig.tight_layout(); fig.savefig(os.path.join(RESULTS, "phase3_geometry.png"), dpi=150); plt.close(fig)


if __name__ == "__main__":
    run(); print("wrote results/phase3.json")

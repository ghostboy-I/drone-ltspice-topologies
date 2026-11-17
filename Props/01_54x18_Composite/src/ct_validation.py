"""Phase 4.0: Caradonna-Tung hover rotor validation.
Stages (run as `python3 src/ct_validation.py <stage> [mesh]`):
  bemt      hand calculation: BEMT with XFOIL NACA 0012 polars, and the thrust implied by the report's sectional CL
  geometry  two untwisted NACA 0012 blades as a closed STL
  case      write the OpenFOAM 13 case (steady, whole-domain rotating frame)
  mesh      blockMesh + surfaceFeatures + snappyHexMesh + checkMesh
  run       foamRun in parallel
  post      forces, sectional Cp and cl against Table 17
"""
import csv, json, math, os, shutil, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import yaml
from common import ROOT, RESULTS, load_params, save_json
import atmosphere as atm

CT = yaml.safe_load(open(os.path.join(ROOT, "data", "caradonna_tung.yaml")))


def setup(p):
    """Rotor and flow definition. Only the entries under ct_validation in params.yaml are assumptions."""
    v = p["ct_validation"]
    R = CT["rotor"]["radius_m"]; c = R / CT["rotor"]["aspect_ratio"]
    rpm, mt_ = CT["case"]["rpm"], CT["case"]["tip_mach"]
    om = rpm * 2 * math.pi / 60
    a = om * R / mt_                                   # speed of sound implied by the reported tip Mach number
    T = a * a / (atm.GAMMA * atm.R_AIR)
    pinf = v["ambient_pressure_pa"]
    rho = pinf / (atm.R_AIR * T); mu = atm.sutherland_viscosity(T)
    return {"R": R, "chord": c, "N": CT["rotor"]["n_blades"], "theta": math.radians(CT["case"]["collective_deg"]), "rpm": rpm, "omega": om,
            "a": a, "T": T, "p": pinf, "rho": rho, "mu": mu, "nu": mu / rho, "vtip": om * R, "r_root": v["root_cutout_chords"] * c,
            "re_tip": rho * om * R * c / mu, "sigma": CT["rotor"]["n_blades"] * c / (math.pi * R)}


def table17():
    rows = []
    with open(os.path.join(ROOT, "data", "caradonna_tung_table17.csv")) as f:
        for r in csv.DictReader(l for l in f if not l.startswith("#")):
            rows.append({"x": float(r["r_over_R"]), "surface": r["surface"], "xc": float(r["x_over_c"]), "cp": -float(r["minus_cp"]), "flag": r["flag"]})
    return rows


def cn_from_points(xc_u, cp_u, xc_l, cp_l):
    """Normal-force coefficient from chordwise pressures: cn = integral of (Cp_lower - Cp_upper) d(x/c), trapezoid rule,
    each surface extended to Cp at x/c = 1 by holding its last value and to x/c = 0 by its first."""
    def integ(x, y):
        o = np.argsort(x); x, y = np.asarray(x)[o], np.asarray(y)[o]
        x = np.concatenate([[0.0], x, [1.0]]); y = np.concatenate([[y[0]], y, [y[-1]]])
        return float(np.trapezoid(y, x))
    return integ(xc_l, cp_l) - integ(xc_u, cp_u)


def experimental_thrust(s):
    """Thrust coefficient implied by the report's sectional C_L values: CT = (sigma/2) * integral of cl x^2 dx.
    The report gives five stations from 0.5 R to 0.96 R, so the inboard and tip parts need an assumption. Three are
    bracketed: cl held constant inboard and dropped linearly to zero at the tip (central); cl falling linearly to zero
    at the root cutout (low); cl held to the tip (high)."""
    xs = np.array(sorted(CT["case"]["sectional_cl"])); cl = np.array([CT["case"]["sectional_cl"][k] for k in xs])
    x0 = s["r_root"] / s["R"]
    def ct(inboard, tip):
        x = np.concatenate([[x0], xs, [1.0]]); y = np.concatenate([[inboard], cl, [tip]])
        xx = np.linspace(x0, 1.0, 2001)
        return float(s["sigma"] / 2 * np.trapezoid(np.interp(xx, x, y) * xx ** 2, xx))
    return {"central": ct(cl[0], 0.0), "low": ct(0.0, 0.0), "high": ct(cl[0], cl[-1]), "stations": xs.tolist(), "cl": cl.tolist(),
            "measured_span_only": float(s["sigma"] / 2 * np.trapezoid(cl * xs ** 2, xs))}


def stage_bemt(p):
    import airfoils, bemt
    s = setup(p)
    p2 = dict(p); p2["airfoils"] = p["ct_validation"]["polars"]
    db, _ = airfoils.build_db(p2)
    r = np.linspace(s["r_root"], s["R"], 60)
    blade = bemt.Blade(s["R"], s["r_root"], s["N"], r, np.full_like(r, s["chord"]), np.full_like(r, s["theta"]), np.full_like(r, 0.12))
    air = {"rho": s["rho"], "mu": s["mu"], "a": s["a"]}
    h = bemt.axial(blade, db, air, s["rpm"], n=60)
    ex = experimental_thrust(s)
    stations = []
    for x, cl_exp in zip(ex["stations"], ex["cl"]):
        cl_b = float(np.interp(x * s["R"], h["r"], h["cl"]))
        # the report's C_L is referenced to (Omega r)^2; BEMT cl is referenced to W^2, so convert before comparing
        w2 = float(np.interp(x * s["R"], h["r"], (h["W"] / (s["omega"] * h["r"])) ** 2))
        stations.append({"x": x, "cl_exp": cl_exp, "cl_bemt": cl_b * w2, "alpha_deg": float(np.degrees(np.interp(x * s["R"], h["r"], h["alpha"]))),
                         "diff_pct": 100 * (cl_b * w2 / cl_exp - 1)})
    lam = math.sqrt(h["CT_h"] / 2)
    out = {"setup": s, "polar_failed": [list(f) for f in db.failed],
           "bemt": {k: float(h[k]) for k in ("T", "Q", "P", "CT_h", "FoM", "tip_mach")}, "stations": stations, "experimental_ct": ex,
           "momentum_inflow_ratio": lam, "ct_bemt_vs_exp_central_pct": 100 * (h["CT_h"] / ex["central"] - 1),
           # closed-form check of BEMT: untwisted blade, uniform inflow, lift slope a = 2 pi / sqrt(1 - M75^2) (Prandtl-Glauert at 0.75 R)
           }
    a0 = 2 * math.pi / math.sqrt(1 - (0.75 * CT["case"]["tip_mach"]) ** 2)
    lo, hi = 0.0, 0.02
    for _ in range(80):                                 # CT = (sigma a/2)(theta/3 - sqrt(CT/2)/2)
        mid = 0.5 * (lo + hi)
        if s["sigma"] * a0 / 2 * (s["theta"] / 3 - math.sqrt(mid / 2) / 2) > mid: lo = mid
        else: hi = mid
    out["closed_form"] = {"lift_slope": a0, "ct": lo, "bemt_vs_closed_form_pct": 100 * (h["CT_h"] / lo - 1)}
    save_json("ct_bemt.json", out)
    print(json.dumps({k: out[k] for k in ("bemt", "stations", "experimental_ct", "closed_form", "ct_bemt_vs_exp_central_pct", "polar_failed")}, indent=1, default=float))
    return out


# ---- geometry ------------------------------------------------------------------------------------------------
def blade_points(s, r, n=121):
    """Closed NACA 0012 section at radius r: pitch theta about the quarter chord, blade along +x, rotation toward +y."""
    import geometry as geo
    (xu, yu), (xl, yl) = geo.naca4(0.12, 0.0, 0.4, n, closed_te=True)
    xs, ys = np.concatenate([xu[::-1], xl[1:-1]]), np.concatenate([yu[::-1], yl[1:-1]])     # TE -> LE (upper) -> just before TE (lower)
    a = (0.25 - xs) * s["chord"]
    th = s["theta"]
    return np.column_stack([np.full_like(a, r), a * math.cos(th) - ys * s["chord"] * math.sin(th), a * math.sin(th) + ys * s["chord"] * math.cos(th)])


def stage_geometry(p, *_):
    import geometry as geo
    s = setup(p)
    n_span = 100
    radii = np.linspace(s["r_root"], s["R"], n_span + 1)
    secs = [blade_points(s, r) for r in radii]
    m = len(secs[0]); tris = []
    for a_, b_ in zip(secs[:-1], secs[1:]):
        for i in range(m):
            j = (i + 1) % m
            tris += [[a_[i], b_[i], b_[j]], [a_[i], b_[j], a_[j]]]
    for sec, flip in ((secs[0], False), (secs[-1], True)):         # flat end caps as strips between the two surfaces
        nu = (m + 2) // 2                                            # upper points: indices 0..nu-1 (TE..LE); lower: nu..m-1 (after LE .. before TE)
        up = [sec[i] for i in range(nu)]; lo = [sec[0]] + [sec[m - 1 - k] for k in range(m - nu)] + [sec[nu - 1]]
        for k in range(nu - 1):
            q = [up[k], up[k + 1], lo[k + 1], lo[k]]
            for t in ([q[0], q[1], q[2]], [q[0], q[2], q[3]]):
                if np.linalg.norm(np.cross(t[1] - t[0], t[2] - t[0])) > 1e-14:
                    tris.append(t[::-1] if flip else t)
    b1 = np.array(tris)
    b2 = b1.copy(); b2[:, :, 0] *= -1; b2[:, :, 1] *= -1               # second blade: half turn about z
    tris = np.concatenate([b1, b2])
    st = geo.mesh_stats(tris)
    if st["volume"] < 0:
        tris = tris[:, ::-1, :]; st = geo.mesh_stats(tris)
    os.makedirs(geo.GEOM, exist_ok=True)
    geo.write_stl(os.path.join(geo.GEOM, "ct_blades.stl"), tris, "blades")
    sl = geo.slice_section(tris, 0.8 * s["R"])
    exact_vol = 2 * 0.685 * 0.12 * s["chord"] ** 2 * (s["R"] - s["r_root"])
    out = {"mesh": st, "slice_0p8R": sl, "chord_target": s["chord"], "twist_target_deg": math.degrees(s["theta"]),
           "volume_strip_estimate": exact_vol, "volume_diff_pct": 100 * (st["volume"] / exact_vol - 1)}
    save_json("ct_geometry.json", out)
    print({k: st[k] for k in ("triangles", "edges_not_shared_by_two", "edges_with_inconsistent_orientation", "volume")}, {k: sl[k] for k in ("chord", "twist_deg", "le_y_sign", "nose_up")}, out["volume_diff_pct"])
    return out


# ---- OpenFOAM case -----------------------------------------------------------------------------------------------
HDR = lambda cls, obj, loc="": "FoamFile\n{\n    format      ascii;\n    class       %s;\n%s    object      %s;\n}\n\n" % (cls, ('    location    "%s";\n' % loc) if loc else "", obj)


def case_dir(p, mesh):
    return os.path.join(os.path.expanduser(p["cfd"]["run_root"]), "ct_validation", mesh)


def stage_case(p, mesh="coarse"):
    import geometry as geo
    s, v = setup(p), p["ct_validation"]; mm = v["meshes"][mesh]; dom = v["domain"]
    case = case_dir(p, mesh)
    for d_ in ("0", "constant/geometry", "system"):
        os.makedirs(os.path.join(case, d_), exist_ok=True)
    shutil.copy(os.path.join(geo.GEOM, "ct_blades.stl"), os.path.join(case, "constant", "geometry", "blades.stl"))
    W = lambda rel, txt: open(os.path.join(case, rel), "w").write(txt)
    D, R, h = 2 * s["R"], s["R"], mm["base_cell_m"]
    a = dom["core_half_width_m"]; n = round(2 * a / h); a = n * h / 2
    z0, z1 = -round(dom["below_D"] * D / h) * h, round(dom["above_D"] * D / h) * h
    nz = round((z1 - z0) / h); Rc = dom["radius_D"] * D; q = Rc / math.sqrt(2)
    grade = 0.25; nr = max(4, round((Rc - a) / (h * (1 + 1 / grade) / 2)))
    vz = lambda z: [(-a, -a, z), (a, -a, z), (a, a, z), (-a, a, z), (-q, -q, z), (q, -q, z), (q, q, z), (-q, q, z)]
    verts = "\n".join("    (%.6f %.6f %.6f)" % t for t in vz(z0) + vz(z1))
    arcs = "\n".join("    arc %d %d (%.6f %.6f %.6f)" % t for z, o in ((z0, 0), (z1, 8)) for t in
                     ((4 + o, 5 + o, 0, -Rc, z), (5 + o, 6 + o, Rc, 0, z), (6 + o, 7 + o, 0, Rc, z), (7 + o, 4 + o, -Rc, 0, z)))
    W("system/blockMeshDict", HDR("dictionary", "blockMeshDict") + f"""// O-grid cylinder: a Cartesian core of cubes (side {h} m) where all refinement happens, four graded outer blocks.
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
    W("system/surfaceFeaturesDict", HDR("dictionary", "surfaceFeaturesDict") + 'surfaces ("blades.stl");\nincludedAngle 150;\nsubsetFeatures { nonManifoldEdges yes; openEdges yes; }\n')
    W("system/meshQualityDict", HDR("dictionary", "meshQualityDict") + '#includeEtc "caseDicts/mesh/generation/meshQualityDict"\n')
    cyl = lambda name, zlo, zhi, rad: f"    {name} {{ type cylinder; point1 (0 0 {zlo:.4f}); point2 (0 0 {zhi:.4f}); radius {rad:.4f}; }}\n"
    W("system/snappyHexMeshDict", HDR("dictionary", "snappyHexMeshDict") + f"""castellatedMesh true;
snap            true;
addLayers       true;

geometry
{{
    blades {{ type triSurface; file "blades.stl"; }}
{cyl("disk", -0.5 * R, 0.3 * R, 1.25 * R)}{cyl("wake", -2.0 * R, 0.5 * R, 1.4 * R)}{cyl("farWake", -6.0 * R, 1.0 * R, 2.0 * R)}{cyl("farWake2", -12.0 * R, 1.5 * R, 2.3 * R)}}};

castellatedMeshControls
{{
    maxLocalCells 1500000;
    maxGlobalCells 6000000;
    minRefinementCells 10;
    maxLoadUnbalance 0.10;
    nCellsBetweenLevels 3;
    features ( {{ file "blades.eMesh"; level {mm['edge_level']}; }} );
    refinementSurfaces
    {{
        blades {{ level ({mm['surface_level'][0]} {mm['surface_level'][1]}); patchInfo {{ type wall; }} }}
    }}
    resolveFeatureAngle 30;
    refinementRegions
    {{
        disk     {{ mode inside; level {mm['disk_level']}; }}
        wake     {{ mode inside; level {mm['wake_level']}; }}
        farWake  {{ mode inside; level {mm['far_wake_level']}; }}
        farWake2 {{ mode inside; level 1; }}
    }}
    insidePoint (0.0123 0.0217 0.5113);
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
    relativeSizes false;
    layers {{ blades {{ nSurfaceLayers {mm['n_layers']}; }} }}
    expansionRatio {mm['expansion']};
    firstLayerThickness {mm['first_layer_m']};
    minThickness {mm['first_layer_m'] * 0.3};
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
    n_it = mm["iterations"]
    W("system/controlDict", HDR("dictionary", "controlDict") + f"""solver          incompressibleFluid;
startFrom       latestTime;
startTime       0;
stopAt          endTime;
endTime         {n_it};
deltaT          1;
writeControl    timeStep;
writeInterval   {n_it // 3};
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
        patches (blades); rho rhoInf; rhoInf {s['rho']:.6f}; CofR (0 0 0);
        writeControl timeStep; writeInterval 1; log no;
    }}
    bladeSurface
    {{
        type surfaces; libs ("libsampling.so");
        writeControl writeTime; surfaceFormat raw; fields (p); interpolationScheme cell;
        surfaces {{ blades {{ type patch; patches (blades); interpolate false; }} }}
    }}
    yPlus
    {{
        type yPlus; libs ("libfieldFunctionObjects.so"); writeControl writeTime;
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
    ctl = "{ nNonOrthogonalCorrectors 1; consistent yes; }"
    W("system/fvSolution", HDR("dictionary", "fvSolution") + f"""solvers
{{
    p {{ solver GAMG; smoother GaussSeidel; tolerance 1e-8; relTol 0.01; }}
    "(U|k|omega)" {{ solver smoothSolver; smoother GaussSeidel; tolerance 1e-9; relTol 0.1; nSweeps 1; }}
}}
SIMPLE {ctl}
PIMPLE {ctl}
relaxationFactors {{ equations {{ U 0.8; k 0.6; omega 0.6; }} }}
""")
    W("constant/MRFProperties", HDR("dictionary", "MRFProperties", "constant") + f"""// Whole-domain rotating frame: the helical wake is steady in this frame. The far boundaries are surfaces of revolution.
rotor
{{
    cellZone    all;
    origin      (0 0 0);
    axis        (0 0 1);
    omega       {s['rpm']} [rpm];
}}
""")
    W("constant/momentumTransport", HDR("dictionary", "momentumTransport", "constant") + "simulationType RAS;\nRAS { model kOmegaSST; turbulence on; }\n")
    W("constant/physicalProperties", HDR("dictionary", "physicalProperties", "constant") + f"viscosityModel constant;\nnu [0 2 -1 0 0 0 0] {s['nu']:.6e};\n")
    k0, om0 = 1e-3, 10.0
    fld = lambda cls, name, dim, internal, bcs: HDR(cls, name, "0") + f"dimensions {dim};\ninternalField uniform {internal};\nboundaryField\n{{\n" + "".join(f"    {k} {{ {b} }}\n" for k, b in bcs.items()) + "}\n"
    W("0/U", fld("volVectorField", "U", "[0 1 -1 0 0 0 0]", "(0 0 0)", {
        "far_top": "type pressureInletOutletVelocity; value uniform (0 0 0);", "far_side": "type slip;",
        "far_bottom": "type inletOutlet; inletValue uniform (0 0 0); value uniform (0 0 0);", "blades": "type MRFnoSlip;"}))
    W("0/p", fld("volScalarField", "p", "[0 2 -2 0 0 0 0]", "0", {
        "far_top": "type totalPressure; p0 uniform 0; value uniform 0;", "far_side": "type zeroGradient;",
        "far_bottom": "type fixedValue; value uniform 0;", "blades": "type zeroGradient;"}))
    io = lambda val: f"type inletOutlet; inletValue uniform {val}; value uniform {val};"
    W("0/k", fld("volScalarField", "k", "[0 2 -2 0 0 0 0]", k0, {"far_top": io(k0), "far_side": "type zeroGradient;", "far_bottom": io(k0), "blades": f"type kqRWallFunction; value uniform {k0};"}))
    W("0/omega", fld("volScalarField", "omega", "[0 0 -1 0 0 0 0]", om0, {"far_top": io(om0), "far_side": "type zeroGradient;", "far_bottom": io(om0), "blades": f"type omegaWallFunction; value uniform {om0};"}))
    W("0/nut", fld("volScalarField", "nut", "[0 2 -1 0 0 0 0]", "0", {"far_top": "type calculated; value uniform 0;", "far_side": "type calculated; value uniform 0;",
                                                                       "far_bottom": "type calculated; value uniform 0;", "blades": "type nutUSpaldingWallFunction; value uniform 0;"}))
    info = {"case": case, "base_cell": h, "core_cells": n, "nz": nz, "nr": nr, "z0": z0, "z1": z1, "radius": Rc, "background_cells": nz * (n * n + 4 * n * nr),
            "surface_cell_mm": 1000 * h / 2 ** mm["surface_level"][0], "edge_cell_mm": 1000 * h / 2 ** mm["edge_level"], "disk_cell_mm": 1000 * h / 2 ** mm["disk_level"]}
    save_json(f"ct_case_{mesh}.json", info); print(info)
    return info


def foam(case, cmd, log, timeout=None, parallel=0):
    """Run an OpenFOAM command in the case directory, with the log saved in the case and copied to the project."""
    full = f"source /opt/openfoam13/etc/bashrc && " + (f"mpirun -np {parallel} {cmd} -parallel" if parallel else cmd)
    with open(os.path.join(case, log), "w") as f:
        r = subprocess.run(["bash", "-c", full], cwd=case, stdout=f, stderr=subprocess.STDOUT, timeout=timeout)
    return r.returncode


def stage_mesh(p, mesh="coarse"):
    case, n = case_dir(p, mesh), p["ct_validation"]["n_proc"]
    for d_ in os.listdir(case):
        if d_.startswith("processor") or d_ == "postProcessing":
            shutil.rmtree(os.path.join(case, d_))
    shutil.rmtree(os.path.join(case, "constant", "polyMesh"), ignore_errors=True)
    steps = [("blockMesh", "log.blockMesh", 0), ("surfaceFeatures", "log.surfaceFeatures", 0), ("decomposePar -copyZero", "log.decomposePar", 0),
             ("snappyHexMesh", "log.snappyHexMesh", n), ("checkMesh", "log.checkMesh", n)]
    for cmd, log, par in steps:
        rc = foam(case, cmd, log, parallel=par)
        print(cmd, "->", rc, flush=True)
        if rc != 0 and cmd != "checkMesh":
            print(open(os.path.join(case, log)).read()[-2500:]); raise SystemExit(1)
    collect_logs(p, mesh)


def collect_logs(p, mesh):
    case = case_dir(p, mesh); dst = os.path.join(ROOT, "cfd", "00_validation_caradonna_tung", mesh)
    os.makedirs(dst, exist_ok=True)
    for f in os.listdir(case):
        if f.startswith("log."):
            shutil.copy(os.path.join(case, f), os.path.join(dst, f + ".txt"))       # .txt: *.log is git-ignored in this repo
    for sub in ("system", "constant/MRFProperties", "constant/momentumTransport", "constant/physicalProperties", "0"):
        src = os.path.join(case, sub)
        if os.path.isdir(src): shutil.copytree(src, os.path.join(dst, sub), dirs_exist_ok=True)
        elif os.path.exists(src): os.makedirs(os.path.dirname(os.path.join(dst, sub)), exist_ok=True); shutil.copy(src, os.path.join(dst, sub))


def stage_run(p, mesh="coarse"):
    case, n = case_dir(p, mesh), p["ct_validation"]["n_proc"]
    rc = foam(case, "foamRun", "log.foamRun", parallel=n)
    print("foamRun ->", rc)
    collect_logs(p, mesh)


if __name__ == "__main__":
    P = load_params()
    stage = sys.argv[1]
    globals()["stage_" + stage](P, *sys.argv[2:])

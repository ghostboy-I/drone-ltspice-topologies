"""2-D RANS cases (OpenFOAM 13, foamRun / incompressibleFluid, Spalart-Allmaras) for the wing and tail sections.

    python3 src/cfd_airfoil2d.py setup [4415|0012 ...]   write cfd/airfoil2d/<code>/a<alpha>/ cases + a run script
    python3 src/cfd_airfoil2d.py mesh 4415               blockMesh + checkMesh on one case (light, single core)
    python3 src/cfd_airfoil2d.py post                    collect cl, cd, cm vs XFOIL -> results/ and CFD_Results/

Why 2-D first. The wing is straight (6 deg sweep), AR 5.5 and runs at Re ~1.1e6, so its section polar sets the stall
speed, the cruise cd and the pitching moment the tail must trim. Those were taken from XFOIL in sizing.py; this case
is the independent check (rule: hand calc / lower-order first, then simulation, then compare, explain > 10 %).

Expected differences, stated before the run:
  * Spalart-Allmaras is fully turbulent; XFOIL (Ncrit 9) has free transition with laminar runs. Expect CFD cd above
    XFOIL by roughly the laminar-run saving (often 20-40 % at this Re) and cl_max lower, since a fully turbulent
    boundary layer is thicker at the trailing edge.
  * The cruise lift slope and cl at a given alpha should agree within a few %.

Mesh: a six-block C-grid (blockMesh). Wall-normal first cell sized for y+ ~ 1 from the flat-plate skin friction
    C_f = 0.026 / Re_x^(1/7),  u_tau = U sqrt(C_f / 2),  dy_1 = y+ nu / u_tau,
geometric growth to a far field 15 chords out, wake 20 chords long, one cell thick in z (empty front/back).
Angle of attack is set by rotating the freestream (geometry fixed), so one mesh serves all alphas.

What it took to get a converged run (kept here because each was a real failure):
  1. Wake cells at the wall spacing all the way to the outlet (45,000:1 aspect ratio): k went negative, every case
     diverged. Fix: edgeGrading relaxes the wake-normal spacing to 0.01 c at the outlet (max aspect ratio ~600).
  2. Far-field vertices directly above the split station and the TE: 90 cells packed into 0.56 m of far field next
     to 0.44 m cells on the arc, a 50:1 neighbour volume jump (checkMesh -allGeometry: volume ratio 0.02). Fix: the
     far-field vertices split the far boundary in proportion to each block's cell count, far edges uniform (0.27).
  3. Model and start-up: k-omega SST (Tu 0.1 %, nut/nu 1) and even a laminar first-order run blew up within ~40
     iterations from a uniform start, while the OpenFOAM airFoil2D tutorial settings converged on the same mesh. The
     bisection pinned it on the start: a near-inviscid initial field at Re 1e6 separates and SIMPLE diverges before a
     boundary layer forms. Fix: Spalart-Allmaras (the airfoil-calibrated one-equation model) with the physical
     freestream nuTilda = 3 nu (NASA TMR) at the far field but a viscous start (nuTilda = 0.007 U c) inside; the
     start is convected out and the converged answer does not depend on it.
"""
import json, math, os, shutil, subprocess, sys
import numpy as np
from tiltcfg import ROOT, RESULTS, REPO, jload, params

# OpenFOAM cannot work in a path with spaces (this repo's), so cases run under the user's OpenFOAM run directory, as
# the toroid cases do; post() copies the logs and force histories back into cfd/airfoil2d/ in the repo.
CFD = os.path.join(os.path.expanduser("~"), "OpenFOAM", f"{os.environ.get('USER', 'user')}-13", "run", "osprey_airfoil2d")
REPO_CFD = os.path.join(ROOT, "cfd", "airfoil2d")
SUMMARY = os.path.join(REPO, "CFD_Results", "02_Osprey_TiltTri", "airfoil2d")
HDR = 'FoamFile {{ format ascii; class {cls}; {loc}object {obj}; }}\n'


def naca4_closed(code, n):
    """NACA 4-digit with the closed-TE coefficient (-0.1036). Returns upper (LE->TE) and lower (LE->TE) at unit chord."""
    m, p_, t = int(code[0]) / 100, int(code[1]) / 10, int(code[2:]) / 100
    beta = np.linspace(0, math.pi, n)
    x = 0.5 * (1 - np.cos(beta))
    yt = 5 * t * (0.2969 * np.sqrt(x) - 0.1260 * x - 0.3516 * x ** 2 + 0.2843 * x ** 3 - 0.1036 * x ** 4)
    if m > 0:
        yc = np.where(x < p_, m / p_ ** 2 * (2 * p_ * x - x ** 2), m / (1 - p_) ** 2 * ((1 - 2 * p_) + 2 * p_ * x - x ** 2))
        dy = np.where(x < p_, 2 * m / p_ ** 2 * (p_ - x), 2 * m / (1 - p_) ** 2 * (p_ - x))
    else:
        yc = np.zeros_like(x); dy = np.zeros_like(x)
    th = np.arctan(dy)
    up = np.c_[x - yt * np.sin(th), yc + yt * np.cos(th)]
    lo = np.c_[x + yt * np.sin(th), yc - yt * np.cos(th)]
    up[-1] = lo[-1] = [1.0, yc[-1]]                                # single TE point
    return up, lo


def ratio_for(first, total, n):
    """Geometric growth ratio r with first * (r^n - 1) / (r - 1) = total."""
    lo, hi = 1.0 + 1e-9, 2.0
    for _ in range(200):
        r = 0.5 * (lo + hi)
        if first * (r ** n - 1) / (r - 1) > total: hi = r
        else: lo = r
    return r


def block_mesh_dict(code, c, U, nu, dz, Ro=15.0, Lw=20.0, nf=70, na=90, nn=120, nw=110, yplus=1.0):
    up, lo = naca4_closed(code, 241)
    xs = 0.30                                                     # split station (x/c) on both surfaces
    iu = int(np.argmin(abs(up[:, 0] - xs))); il = int(np.argmin(abs(lo[:, 0] - xs)))
    re = U * c / nu
    cf = 0.026 / re ** (1 / 7)
    dy1 = yplus * nu / (U * math.sqrt(cf / 2))
    R, L = Ro * c, Lw * c
    g_n = ratio_for(dy1, R, nn) ** (nn - 1)                         # last / first cell, wall-normal
    ds_te = (1 - xs) * c / na * 0.5                                 # TE cell along the surface (graded 0.5 toward TE)
    g_w = ratio_for(ds_te, L - c, nw) ** (nw - 1)
    # Wake blocks: the wall-normal spacing must NOT run at dy1 all the way to the outlet (first attempt: 45,000:1 cells
    # there, k went negative at iteration 1 and every run diverged). edgeGrading relaxes it to dy_out at the outlet.
    dy_out = 0.01 * c
    g_out = ratio_for(dy_out, R, nn) ** (nn - 1)
    P = lambda q: q * c
    # Far field: a quarter arc (centre (xs*c, 0), radius R) then a straight line to the outlet, top and bottom. The far
    # vertices 5/6 (and 11/10) are placed so each block gets its share of the far-field length in proportion to its cell
    # count, and the far edges are uniform. Second attempt: with 5/6 above the split station and the TE, block 1's 90
    # cells were packed into 0.56 m of far field next to 0.44 m cells on the arc -> 50:1 neighbour volume jumps there,
    # and even a laminar first-order run diverged.
    cx = xs * c
    S_arc, S_tot = 0.5 * math.pi * R, 0.5 * math.pi * R + (L - cx)
    def far(sv, sgn):                                            # point at arc length sv from the front stagnation vertex
        if sv <= S_arc:
            th = sv / R
            return (cx - R * math.cos(th), sgn * R * math.sin(th))
        return (cx + (sv - S_arc), sgn * R)
    ntot = nf + na + nw
    s5, s6 = S_tot * nf / ntot, S_tot * (nf + na) / ntot
    v = [(0, 0), P(up[iu]), (c, 0), P(lo[il]), (cx - R, 0), far(s5, 1), far(s6, 1), (L, R), (L, 0), (L, -R), far(s6, -1), far(s5, -1)]
    v[0] = tuple(P(up[0])); v[2] = tuple(P(up[-1])); v[8] = (L, v[2][1])
    verts = "".join(f"    ({x:.8f} {y:.8f} 0)\n" for x, y in v) + "".join(f"    ({x:.8f} {y:.8f} {dz})\n" for x, y in v)
    def pl(a, b, pts):
        s = ""
        for o in (0, 12):
            s += f"    polyLine {a+o} {b+o} (" + " ".join(f"({x:.8f} {y:.8f} {0 if o == 0 else dz})" for x, y in pts) + ")\n"
        return s
    edges = pl(0, 1, P(up[1:iu])) + pl(1, 2, P(up[iu + 1:-1])) + pl(0, 3, P(lo[1:il])) + pl(3, 2, P(lo[il + 1:-1]))
    fs = lambda a, b, sgn: [far(t, sgn) for t in np.linspace(a, b, 40)[1:-1]]
    edges += pl(4, 5, fs(0, s5, 1)) + pl(5, 6, fs(s5, s6, 1)) + pl(4, 11, fs(0, s5, -1)) + pl(11, 10, fs(s5, s6, -1))
    h = lambda a, b, c_, d: f"({a} {b} {c_} {d} {a+12} {b+12} {c_+12} {d+12})"
    gn, gw, go = f"{g_n:.6g}", f"{g_w:.6g}", f"{g_out:.6g}"
    rn, ro = f"{1/g_n:.6g}", f"{1/g_out:.6g}"
    eg = lambda x1, x2: "edgeGrading (" + " ".join(x1 + x2) + " 1 1 1 1)"
    # x1 edges in blockMesh order (0-1, 3-2, 7-6, 4-5): inner surface/wake-cut edges graded, far-field edges uniform
    blocks = (f"    hex {h(0,1,5,4)} ({nf} {nn} 1) {eg(['3', '1', '1', '3'], [gn] * 4)}\n"
              f"    hex {h(1,2,6,5)} ({na} {nn} 1) {eg(['0.5', '1', '1', '0.5'], [gn] * 4)}\n"
              f"    hex {h(2,8,7,6)} ({nw} {nn} 1) {eg([gw, '1', '1', gw], [gn, go, go, gn])}\n"
              f"    hex {h(3,0,4,11)} ({nf} {nn} 1) {eg(['0.333333', '1', '1', '0.333333'], [gn] * 4)}\n"
              f"    hex {h(2,3,11,10)} ({na} {nn} 1) {eg(['2', '1', '1', '2'], [gn] * 4)}\n"
              f"    hex {h(10,9,8,2)} ({nw} {nn} 1) {eg(['1', gw, gw, '1'], [rn, ro, ro, rn])}\n")
    f2 = lambda a, b: f"({a} {b} {b+12} {a+12})"
    bnd = ("    airfoil { type wall; faces (" + " ".join(f2(a, b) for a, b in ((0, 1), (1, 2), (3, 0), (2, 3))) + "); }\n"
           "    farfield { type patch; faces (" + " ".join(f2(a, b) for a, b in ((4, 5), (5, 6), (6, 7), (7, 8), (8, 9), (9, 10), (10, 11), (11, 4))) + "); }\n"
           "    frontAndBack { type empty; faces (" + " ".join(f"({a} {b} {c_} {d})" for a, b, c_, d in ((0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 8), (3, 11, 4, 0), (2, 10, 11, 3), (10, 2, 8, 9))) +
           " " + " ".join(f"({a+12} {b+12} {c_+12} {d+12})" for a, b, c_, d in ((0, 1, 5, 4), (1, 2, 6, 5), (2, 8, 7, 6), (3, 0, 4, 11), (2, 3, 11, 10), (10, 9, 8, 2))) + "); }\n")
    txt = (HDR.format(cls="dictionary", loc="", obj="blockMeshDict") + "convertToMeters 1;\nvertices\n(\n" + verts + ");\nblocks\n(\n" + blocks +
           ");\nedges\n(\n" + edges + ");\nboundary\n(\n" + bnd + ");\n")
    info = {"Re": re, "dy1_m": dy1, "grading_normal": g_n, "grading_wake": g_w, "dy_wake_outlet_m": dy_out, "cells": (2 * (nf + na + nw)) * nn,
            "far_field_chords": Ro, "wake_chords": Lw}
    return txt, info


def case_files(code, alpha, c, U, nu, dz):
    a = math.radians(alpha)
    Ux, Uy = U * math.cos(a), U * math.sin(a)
    nt_inf = 3.0 * nu                                                   # NASA TMR freestream nuTilda for SA
    nt_0 = 0.007 * U * c                                                # viscous start-up field (convected out)
    files = {}
    files["constant/physicalProperties"] = HDR.format(cls="dictionary", loc='location "constant"; ', obj="physicalProperties") + \
        f"viscosityModel constant;\nnu [0 2 -1 0 0 0 0] {nu:.6e};\n"
    files["constant/momentumTransport"] = HDR.format(cls="dictionary", loc='location "constant"; ', obj="momentumTransport") + \
        "simulationType RAS;\nRAS { model SpalartAllmaras; turbulence on; printCoeffs on; }\n"
    files["system/controlDict"] = HDR.format(cls="dictionary", loc="", obj="controlDict") + f"""
solver incompressibleFluid;
startFrom latestTime; startTime 0; stopAt endTime; endTime 5000; deltaT 1;
writeControl timeStep; writeInterval 500; purgeWrite 1; writeFormat binary; writePrecision 8;
timeFormat general; timePrecision 6; runTimeModifiable true;
functions
{{
    forceCoeffs
    {{
        type forceCoeffs; libs ("libforces.so"); patches (airfoil);
        rho rhoInf; rhoInf 1; magUInf {U}; lRef {c}; Aref {c*dz:.8g}; CofR ({0.25*c:.6f} 0 0);
        liftDir ({-math.sin(a):.8f} {math.cos(a):.8f} 0); dragDir ({math.cos(a):.8f} {math.sin(a):.8f} 0); pitchAxis (0 0 1);
        writeControl timeStep; writeInterval 1; log no;
    }}
    yPlus {{ type yPlus; libs ("libfieldFunctionObjects.so"); writeControl writeTime; }}
    residuals {{ type residuals; libs ("libutilityFunctionObjects.so"); fields (p U nuTilda); }}
}}
"""
    files["system/fvSchemes"] = HDR.format(cls="dictionary", loc="", obj="fvSchemes") + """
ddtSchemes { default steadyState; }
gradSchemes { default Gauss linear; }
divSchemes
{
    default none;
    div(phi,U) bounded Gauss linearUpwind grad(U);
    div(phi,nuTilda) bounded Gauss linearUpwind grad(nuTilda);
    div((nuEff*dev2(T(grad(U))))) Gauss linear;
}
laplacianSchemes { default Gauss linear corrected; }
interpolationSchemes { default linear; }
snGradSchemes { default corrected; }
wallDist { method meshWave; }
"""
    files["system/fvSolution"] = HDR.format(cls="dictionary", loc="", obj="fvSolution") + """
solvers
{
    p { solver GAMG; smoother GaussSeidel; tolerance 1e-7; relTol 0.1; }
    "(U|nuTilda)" { solver smoothSolver; smoother GaussSeidel; tolerance 1e-9; relTol 0.1; nSweeps 2; }
}
SIMPLE { nNonOrthogonalCorrectors 1; residualControl { p 1e-5; U 1e-6; nuTilda 1e-6; } }
relaxationFactors { fields { p 0.3; } equations { U 0.7; nuTilda 0.7; } }
"""
    bc = lambda name, cls, dim, internal, far, wall: HDR.format(cls=cls, loc='location "0"; ', obj=name) + \
        f"dimensions {dim};\ninternalField uniform {internal};\nboundaryField\n{{\n    farfield {{ {far} }}\n    airfoil {{ {wall} }}\n    frontAndBack {{ type empty; }}\n}}\n"
    Uv = f"({Ux:.8f} {Uy:.8f} 0)"
    files["0/U"] = bc("U", "volVectorField", "[0 1 -1 0 0 0 0]", Uv, f"type freestreamVelocity; freestreamValue uniform {Uv}; value uniform {Uv};", "type noSlip;")
    files["0/p"] = bc("p", "volScalarField", "[0 2 -2 0 0 0 0]", "0", "type freestreamPressure; freestreamValue uniform 0; value uniform 0;", "type zeroGradient;")
    files["0/nuTilda"] = bc("nuTilda", "volScalarField", "[0 2 -1 0 0 0 0]", f"{nt_0:.6e}", f"type freestream; freestreamValue uniform {nt_inf:.6e};", "type fixedValue; value uniform 0;")
    files["0/nut"] = bc("nut", "volScalarField", "[0 2 -1 0 0 0 0]", f"{nt_0:.6e}", f"type freestream; freestreamValue uniform {nt_inf:.6e};", "type nutUSpaldingWallFunction; value uniform 0;")
    return files


def setup(codes=("4415", "0012")):
    sz = jload(os.path.join(RESULTS, "sizing.json"))
    U, nu = sz["cruise"]["V"], sz["air"]["mu"] / sz["air"]["rho"]
    plan = {}
    for code in codes:
        c = sz["wing"]["c"] if code == sz["wing"]["airfoil"] else sz["stability"]["c_h"]
        alphas = [-4, 0, 2, 4, 6, 8, 10, 12, 14, 16] if code != "0012" else [0, 4, 8, 12]
        dz = 0.01 * c
        bmd, info = block_mesh_dict(code, c, U, nu, dz)
        for a in alphas:
            d = os.path.join(CFD, code, f"a{a:+03d}")
            for sub in ("system", "constant", "0"): os.makedirs(os.path.join(d, sub), exist_ok=True)
            with open(os.path.join(d, "system", "blockMeshDict"), "w") as f: f.write(bmd)
            for k_, txt in case_files(code, a, c, U, nu, dz).items():
                with open(os.path.join(d, k_), "w") as f: f.write(txt)
        plan[code] = dict(info, chord=c, U=U, nu=nu, alphas=alphas)
    with open(os.path.join(CFD, "plan.json"), "w") as f: json.dump(plan, f, indent=1)
    os.makedirs(REPO_CFD, exist_ok=True)
    with open(os.path.join(REPO_CFD, "plan.json"), "w") as f: json.dump(dict(plan, run_dir=CFD), f, indent=1)
    run = os.path.join(CFD, "run_all.sh")
    with open(run, "w") as f:
        f.write("""#!/bin/bash
# Runs every airfoil case, two at a time, serial each (2 cores total), at nice 19.
# Waits while another session's foamRun is on the machine (shared-machine rule: start no CFD while it runs).
cd "$(dirname "$0")"
source /opt/openfoam13/etc/bashrc
while [ "$(pgrep -x foamRun | wc -l)" -gt 0 ]; do echo "$(date) foamRun busy, waiting"; sleep 300; done
run_case() {
  cd "$1"
  [ -f log.foamRun ] && grep -q "^End" log.foamRun && return 0
  blockMesh > log.blockMesh 2>&1 && checkMesh > log.checkMesh 2>&1 && nice -n 19 foamRun > log.foamRun 2>&1
}
export -f run_case
ls -d */a* | xargs -P 2 -I{} bash -c 'run_case "$PWD/{}"'
echo "$(date) all airfoil cases finished"
""")
    os.chmod(run, 0o755)
    print(json.dumps(plan, indent=1))


def mesh(code):
    d = sorted(os.listdir(os.path.join(CFD, code)))[0]
    case = os.path.join(CFD, code, d)
    cmd = f"source /opt/openfoam13/etc/bashrc && cd '{case}' && nice -n 19 blockMesh > log.blockMesh 2>&1 && nice -n 19 checkMesh > log.checkMesh 2>&1; tail -30 log.checkMesh"
    print(subprocess.run(["bash", "-c", cmd], capture_output=True, text=True).stdout)


def post():
    plan = jload(os.path.join(CFD, "plan.json"))
    pol = jload(os.path.join(RESULTS, "wing_polars.json"))
    os.makedirs(SUMMARY, exist_ok=True)
    out = {}
    for code, pl in plan.items():
        rows = []
        for a in pl["alphas"]:
            d = os.path.join(CFD, code, f"a{a:+03d}")
            fc = None
            for root, _, files in os.walk(os.path.join(d, "postProcessing", "forceCoeffs")):
                for fn in files:
                    if fn.endswith(".dat"): fc = os.path.join(root, fn)
            if not fc: rows.append({"alpha": a, "status": "not run"}); continue
            data = np.array([[float(x) for x in ln.split()] for ln in open(fc) if ln.strip() and not ln.startswith("#")])
            hdr = [ln for ln in open(fc) if ln.startswith("#")][-1].replace("#", "").split()
            col = {h: i for i, h in enumerate(hdr)}
            tail = data[-200:]
            cl, cd, cm = (float(tail[:, col[k]].mean()) for k in ("Cl", "Cd", "Cm"))
            osc = float(tail[:, col["Cl"]].std())
            log = open(os.path.join(d, "log.foamRun")).read() if os.path.exists(os.path.join(d, "log.foamRun")) else ""
            rows.append({"alpha": a, "cl": cl, "cd": cd, "cm": cm, "cl_std_last200": osc, "iterations": int(data[-1, 0]),
                         "converged": "SIMPLE solution converged" in log})
        key = next((k for k in pol if k.startswith(code + "@")), None)
        if key:
            P = np.array(pol[key])
            for r in rows:
                if "cl" in r:
                    r["xfoil_cl"] = float(np.interp(r["alpha"], P[:, 0], P[:, 1])); r["xfoil_cd"] = float(np.interp(r["alpha"], P[:, 0], P[:, 2]))
                    r["diff_cl_pct"] = 100 * (r["cl"] / r["xfoil_cl"] - 1) if abs(r["xfoil_cl"]) > 0.05 else None
                    r["diff_cd_pct"] = 100 * (r["cd"] / r["xfoil_cd"] - 1)
        out[code] = {"plan": pl, "rows": rows}
        for a in pl["alphas"]:                                     # keep logs + force histories in the repo
            src = os.path.join(CFD, code, f"a{a:+03d}"); dst = os.path.join(REPO_CFD, code, f"a{a:+03d}")
            if not os.path.isdir(src): continue
            os.makedirs(dst, exist_ok=True)
            for fn in ("log.blockMesh", "log.checkMesh", "log.foamRun"):
                if os.path.exists(os.path.join(src, fn)): shutil.copy(os.path.join(src, fn), dst)
            if os.path.isdir(os.path.join(src, "postProcessing")):
                shutil.copytree(os.path.join(src, "postProcessing"), os.path.join(dst, "postProcessing"), dirs_exist_ok=True)
    with open(os.path.join(RESULTS, "cfd_airfoil2d.json"), "w") as f: json.dump(out, f, indent=1)
    with open(os.path.join(SUMMARY, "summary.json"), "w") as f: json.dump(out, f, indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "setup": setup(tuple(sys.argv[2:]) or ("4415", "0012"))
    elif cmd == "mesh": mesh(sys.argv[2])
    elif cmd == "post": post()

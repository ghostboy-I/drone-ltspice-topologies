"""2-D RANS cases (OpenFOAM 13, foamRun / incompressibleFluid, Spalart-Allmaras) for the wing and tail sections.

    python3 src/cfd_airfoil2d.py setup [4415|0012 ...]   write cfd/airfoil2d/<code>/a<alpha>/ cases + a run script
    python3 src/cfd_airfoil2d.py mesh 4415               checkMesh on one case (light, single core)
    python3 src/cfd_airfoil2d.py post                    collect cl, cd, cm vs XFOIL -> results/ and CFD_Results/

Why 2-D first. The wing is straight (6 deg sweep), AR 5.5 and runs at Re ~1.1e6, so its section polar sets the stall
speed, the cruise cd and the pitching moment the tail must trim. Those were taken from XFOIL in sizing.py; this case
is the independent check (rule: hand calc / lower-order first, then simulation, then compare, explain > 10 %).

Expected differences, stated before the run:
  * Spalart-Allmaras is fully turbulent; XFOIL (Ncrit 9) has free transition with laminar runs. Expect CFD cd above
    XFOIL by roughly the laminar-run saving (often 20-40 % at this Re) and cl_max lower, since a fully turbulent
    boundary layer is thicker at the trailing edge.
  * The cruise lift slope and cl at a given alpha should agree within a few %.

Mesh: a single-block C-grid written directly as an OpenFOAM polyMesh by c_grid() (540 x 120 = 64,800 cells). The
wall-normal first cell is sized for y+ ~ 1 from the flat-plate skin friction
    C_f = 0.026 / Re_x^(1/7),  u_tau = U sqrt(C_f / 2),  dy_1 = y+ nu / u_tau,
then grows geometrically along each grid line to a far field 15 chords out, with a wake 20 chords long and one cell
thick in z (empty front/back). Each grid line is a cubic Hermite curve that leaves the wall along the surface normal
(item 6). The angle of attack is set by rotating the freestream with the geometry fixed, so one mesh serves all alphas.

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
  4. The start leaked into the wall: the first 14-case run converged to cl ~40 % low and cd 5-7x high (NACA 4415,
     alpha 4: cl 0.52 vs XFOIL 0.93, cd 0.056 vs 0.0074). nuTilda on the airfoil was ~0.0175 m^2/s (1000 nu) at the
     end, under a "fixedValue 0" BC. OpenFOAM 13's bound() (finiteVolume/.../bound.C), called whenever nuTilda goes
     negative somewhere, also does  bsf == max(bsf, patchInternalField * pos0(-bsf))  on every patch: a patch value
     <= 0 is overwritten (forced, ==) by the adjacent cell's value. In iteration 2-3 that was the viscous start-up
     field; the wall was then positive, pos0 = 0, and the value froze for the whole run (it scaled exactly with the
     start value: 0.0087 for half of it). A turbulent source on the wall thickened the boundary layer 2-3x and put
     friction drag at 3.6x the flat-plate value. Fix: wall value 1e-30 (physically zero, but > 0 so bound() leaves it).
  5. Wall distance. With item 4 fixed the 4415 at alpha 4 gave cl 0.738, cd 0.0272, and the 0012 at alpha 0 cd 0.0217
     against XFOIL tripped at the LE (0.850 / 0.0140 and 0.0120). Near the wall nuTilda followed kappa u_tau y at y+ 1
     but ran 1.3-1.45x above it by y+ ~20, the signature of an overestimated wall distance d (SA's destruction term goes
     as (nuTilda/d)^2). meshWave on these 5 mm x 0.02 mm wall cells is the suspect; Poisson gave cl 0.791, cd 0.0205
     and 0012 cd 0.0153 (friction 0.0126, pressure 0.0027), and advectionDiffusion gave the same as Poisson to 4 digits
     (and crashed on the 0012), so Poisson is used. What remains is the usual SA vs. XFOIL-integral-BL spread: a
     tripped turbulent flat plate gives friction 2 x 0.074 Re^-0.2 = 0.0101, x ~1.15 for a 12 % section's
     supervelocities = 0.0116 against CFD 0.0126.
  6. Mesh and start-up, redone. The blockMesh C-grid's wall cells were sheared 40-60 deg from the surface normal over
     the forward upper surface, because blockMesh pairs wall and offset points by arc length and the offset curve is
     shorter at the LE. c_grid() instead builds each grid line as a cubic Hermite curve
         P(t) = h00 W + h10 (k_wall L) N + h01 F + h11 dF,   h00 = 2t^3-3t^2+1, h10 = t^3-2t^2+t, ...
     from the wall point W along the unit normal N to the far-field point F. At the wall it is tangent to N, which keeps
     wall non-orthogonality at 0.7 deg mean and 8 deg max. k_wall = 0.2 (0.5 folded the 4415 grid near the TE). On this
     mesh the viscous start (item 3) got trapped in the wake (nuTilda 0.17 m^2/s at 1.5 c), so the start is now
     physical: nuTilda = nut = 3 nu everywhere, with U from potentialFoam -initialiseUBCs, so an attached potential
     flow replaces the near-inviscid uniform field that blew up in item 3.
  7. OpenFOAM 13 over-predicts wall shear by 48 %, so CFD cd is not used. On the NASA TMR NACA 0012 check (Re 6e6,
     alpha 10, published SA answer cl 1.0909, cd 0.01231) this mesh gives cl 1.039 (-4.8 %) but cd 0.0194 (+58 %).
     The boundary-layer profile one cell off the wall follows the log law, so the error sits in the wall cells. A
     laminar Poiseuille channel isolates it. The exact answer is
         dp/dx = 12 mu U_bar / H^2   (30 Pa/m per unit density here), and the wall-cell velocity is 0.03749.
     icoFoam gets 29.99 and 0.03749. Both foamRun/incompressibleFluid and the legacy porousSimpleFoam give 44.2 and
     wall cells that alternate 0.069 / 0.042 cell to cell along the wall (an odd-even mode). The result is the same
     with laminar or SA, every convection/gradient scheme, SIMPLE, SIMPLEC or PISO, square cells, and noSlip or
     fixedValue walls. The common factor is OpenFOAM 13's momentumTransport viscous term (divDevSigma), which icoFoam
     does not use. So post() reports CFD cd for the record only. The design takes the section drag from XFOIL, and
     uses CFD cl as an independent lift check (slope within 2 %, zero-lift offset 4-9 %; no stall by 16 deg).
Reference: SA is fully turbulent, so post() compares against XFOIL both free (ncrit 9, what sizing used) and tripped
at 5 % chord (the like-for-like turbulence state). A 1 % trip is closer to SA's turbulent-from-the-stagnation-point
boundary layer, but XFOIL's Newton iteration fails above alpha 6-7 deg with it (NaN, "sequence halted"); the 5 % trip
converges to stall and is within 1 % on cl and 3 % on cd of the 1 % trip where both converge.
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


def section_closed(code, n):
    """Upper and lower surface (LE->TE), unit chord, single TE point. NACA codes: naca4_closed. Coordinate files
    (wing_sections.py): the finite TE gap g is closed by moving each surface by -/+ (g/2) x/c (a linear thickness taper,
    0.4 % of the chord at the TE for the LS(1)-0417MOD; the C-grid needs one TE point)."""
    if code.isdigit(): return naca4_closed(code, n)
    import wing_sections as ws
    x, zu, zl = ws.surfaces(code, n)
    g = zu[-1] - zl[-1]
    zu, zl = zu - g / 2 * x, zl + g / 2 * x
    up, lo = np.c_[x, zu], np.c_[x, zl]
    up[0] = lo[0] = [0.0, 0.5 * (zu[0] + zl[0])]
    return up, lo


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


def geom_fractions(n, grading):
    """n cells whose sizes grow geometrically with last/first = grading; returns n+1 fractions 0..1."""
    if abs(grading - 1) < 1e-9: return np.linspace(0, 1, n + 1)
    r = grading ** (1 / (n - 1)); s = np.r_[0, np.cumsum(r ** np.arange(n))]
    return s / s[-1]


def geom_from_first(first, total, n):
    r = ratio_for(first, total, n) if first * n < total else 1.0
    s = np.r_[0, np.cumsum(first * r ** np.arange(n))] if r != 1.0 else np.linspace(0, total, n + 1)
    return s * total / s[-1]


def c_grid(code, c, U, nu, dz, Ro=15.0, Lw=20.0, nf=70, na=90, nn=120, nw=110, yplus=1.0, k_wall=0.2):
    """Single-block C-grid built here and written straight to constant/polyMesh (docstring item 6).
    i runs outlet (lower) -> TE -> lower surface -> LE -> upper surface -> TE -> outlet (upper); j runs wall -> far field.
    Each j-line is a cubic Hermite curve that leaves the wall point along the surface normal and arrives at its far-field
    point, so cells at the wall are orthogonal to it; j-spacing is geometric in arc length from dy1."""
    re = U * c / nu
    cf = 0.026 / re ** (1 / 7)
    dy1 = yplus * nu / (U * math.sqrt(cf / 2))
    R, L = Ro * c, Lw * c
    xs = 0.30
    # dense surface, arc-length parametrised, unit chord
    up, lo = section_closed(code, 4001)
    def arc(p): return np.r_[0, np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))]
    def place(p, f):                                              # points at arc fractions f of curve p
        s = arc(p); t = f * s[-1]
        return np.c_[np.interp(t, s, p[:, 0]), np.interp(t, s, p[:, 1])]
    def split(p):
        k = int(np.argmin(abs(p[:, 0] - xs))); return p[:k + 1], p[k:]
    def surface(p):                                               # LE -> TE points: nf cells (grading 3) then na (0.5)
        a, b = split(p)
        return np.r_[place(a, geom_fractions(nf, 3.0)), place(b, geom_fractions(na, 0.5))[1:]]
    su, sl = surface(up), surface(lo)
    def normals(dense, pts, sgn):
        t = np.gradient(dense, axis=0); n = sgn * np.c_[-t[:, 1], t[:, 0]]; n /= np.linalg.norm(n, axis=1)[:, None]
        s = arc(dense); sp = np.array([s[np.argmin(np.hypot(*(dense - q).T))] for q in pts])
        nn_ = np.c_[np.interp(sp, s, n[:, 0]), np.interp(sp, s, n[:, 1])]
        w = np.clip((pts[:, 0] - 0.85) / 0.15, 0, 1); w = w * w * (3 - 2 * w)  # blend to +-y at the TE: the wake cut is along x
        nn_ = (1 - w)[:, None] * nn_ + w[:, None] * np.array([0.0, sgn])
        return nn_ / np.linalg.norm(nn_, axis=1)[:, None]
    nu_, nl_ = normals(up, su, 1), normals(lo, sl, -1)
    nle = nu_[0] + nl_[0]; nle /= np.linalg.norm(nle); nu_[0] = nl_[0] = nle
    su, sl = su * c, sl * c
    te = su[-1]
    ds_te = np.linalg.norm(su[-1] - su[-2])
    xw = te[0] + geom_from_first(ds_te, L - te[0], nw)              # wake cut, TE -> outlet
    wake = np.c_[xw, np.full_like(xw, te[1])]
    # wall/cut points along i, and their outward directions
    W = np.r_[wake[::-1], sl[::-1][1:], su[1:], wake[1:]]
    Nv = np.r_[np.tile([0.0, -1.0], (nw + 1, 1)), nl_[::-1][1:], nu_[1:], np.tile([0.0, 1.0], (nw, 1))]
    Nv[nw] = nl_[-1]; Nv[-nw - 1] = nu_[-1]
    NIp = len(W); NI = NIp - 1
    # far-field points: uniform in i along the C (bottom line, front arc, top line)
    cx = xs * c
    S_line, S_arc = L - cx, math.pi * R
    def far(sv):
        if sv < S_line: return (L - sv, -R)
        if sv < S_line + S_arc:
            th = (sv - S_line) / R; return (cx - R * math.sin(th), -R * math.cos(th))
        return (cx + sv - S_line - S_arc, R)
    F = np.array([far(v) for v in np.linspace(0, 2 * S_line + S_arc, NIp)])
    # j lines
    dy_out = 0.01 * c
    first = np.full(NIp, dy1)
    for k in range(nw + 1):                                       # wake: relax the first spacing to dy_out at the outlet
        fr = (W[k, 0] - te[0]) / (L - te[0])
        first[k] = first[NI - k] = dy1 * (dy_out / dy1) ** fr
    X = np.zeros((NIp, nn + 1, 2))
    u = np.linspace(0, 1, 4001)
    h00, h10, h01, h11 = 2*u**3 - 3*u**2 + 1, u**3 - 2*u**2 + u, -2*u**3 + 3*u**2, u**3 - u**2
    for i in range(NIp):
        d = F[i] - W[i]; Ld = np.linalg.norm(d)
        curve = h00[:, None] * W[i] + h10[:, None] * Nv[i] * (k_wall * Ld) + h01[:, None] * F[i] + h11[:, None] * d
        s = arc(curve); t = geom_from_first(first[i], s[-1], nn)
        X[i] = np.c_[np.interp(t, s, curve[:, 0]), np.interp(t, s, curve[:, 1])]
    X[NI - nw:, 0] = X[nw::-1, 0]                                  # the cut: upper wake j=0 points are the lower ones
    # ---------------- polyMesh ----------------
    NJ = nn
    pid = np.arange(NIp * (nn + 1)).reshape(NIp, nn + 1)          # 2-D point ids before merging the cut
    for i in range(NI - nw, NIp): pid[i, 0] = pid[NI - i, 0]
    used = np.unique(pid); remap = -np.ones(pid.max() + 1, int); remap[used] = np.arange(len(used)); pid = remap[pid]
    n2 = len(used)
    P2 = np.zeros((n2, 2)); P2[pid.ravel()] = X.reshape(-1, 2)
    pts = np.r_[np.c_[P2, np.zeros(n2)], np.c_[P2, np.full(n2, dz)]]
    cell = lambda i, j: i + j * NI
    cc = np.zeros((NI * NJ, 3))
    for j in range(NJ):
        q = (X[:-1, j] + X[1:, j] + X[:-1, j + 1] + X[1:, j + 1]) / 4; cc[j * NI:(j + 1) * NI] = np.c_[q, np.full(NI, dz / 2)]
    def quad(a, b):                                               # face from 2-D edge a-b, extruded in z
        return [a, b, b + n2, a + n2]
    internal, bnd = [], {"airfoil": [], "farfield": [], "frontAndBack": []}
    for j in range(NJ):                                           # i-faces
        for i in range(1, NI): internal.append((cell(i - 1, j), cell(i, j), quad(pid[i, j], pid[i, j + 1])))
        bnd["farfield"].append((cell(0, j), quad(pid[0, j], pid[0, j + 1])))
        bnd["farfield"].append((cell(NI - 1, j), quad(pid[NI, j], pid[NI, j + 1])))
    for j in range(1, NJ):                                        # j-faces
        for i in range(NI): internal.append((cell(i, j - 1), cell(i, j), quad(pid[i, j], pid[i + 1, j])))
    for i in range(NI):
        f0 = quad(pid[i, 0], pid[i + 1, 0])
        if i < nw: internal.append((cell(i, 0), cell(NI - 1 - i, 0), f0))         # wake cut
        elif i >= NI - nw: pass
        else: bnd["airfoil"].append((cell(i, 0), f0))
        bnd["farfield"].append((cell(i, NJ - 1), quad(pid[i, NJ], pid[i + 1, NJ])))
    for j in range(NJ):
        for i in range(NI):
            a, b, c_, d_ = pid[i, j], pid[i + 1, j], pid[i + 1, j + 1], pid[i, j + 1]
            bnd["frontAndBack"].append((cell(i, j), [a, d_, c_, b])); bnd["frontAndBack"].append((cell(i, j), [a + n2, b + n2, c_ + n2, d_ + n2]))
    def orient(f, own, target):                                   # normal must point from the owner towards target
        p = pts[f]; nvec = np.cross(p[1] - p[0], p[2] - p[0]) + np.cross(p[2] - p[0], p[3] - p[0])
        return f if np.dot(nvec, target - cc[own]) > 0 else f[::-1]
    internal = [(min(o, n_), max(o, n_), f) for o, n_, f in internal]
    internal.sort(key=lambda t: (t[0], t[1]))
    faces, owner, neigh = [], [], []
    for o, n_, f in internal: faces.append(orient(f, o, cc[n_])); owner.append(o); neigh.append(n_)
    patches = []
    for name in ("airfoil", "farfield", "frontAndBack"):
        start = len(faces)
        for o, f in bnd[name]: faces.append(orient(f, o, pts[f].mean(0))); owner.append(o)
        patches.append((name, start, len(faces) - start))
    hdr = lambda cls, obj, note="": ("FoamFile { format ascii; class %s; %slocation \"constant/polyMesh\"; object %s; }\n" % (cls, note, obj))
    note = f'note "nPoints: {len(pts)} nCells: {NI*NJ} nFaces: {len(faces)} nInternalFaces: {len(neigh)}"; '
    files = {
        "points": hdr("vectorField", "points") + f"{len(pts)}\n(\n" + "".join(f"({x:.10g} {y:.10g} {z:.10g})\n" for x, y, z in pts) + ")\n",
        "faces": hdr("faceList", "faces") + f"{len(faces)}\n(\n" + "".join("4(%d %d %d %d)\n" % tuple(f) for f in faces) + ")\n",
        "owner": hdr("labelList", "owner", note) + f"{len(owner)}\n(\n" + "\n".join(map(str, owner)) + "\n)\n",
        "neighbour": hdr("labelList", "neighbour", note) + f"{len(neigh)}\n(\n" + "\n".join(map(str, neigh)) + "\n)\n",
        "boundary": hdr("polyBoundaryMesh", "boundary") + f"{len(patches)}\n(\n" + "".join(
            f"    {nm} {{ type {'wall' if nm == 'airfoil' else 'empty' if nm == 'frontAndBack' else 'patch'}; nFaces {n_}; startFace {s}; }}\n"
            for nm, s, n_ in patches) + ")\n"}
    info = {"Re": re, "dy1_m": dy1, "cells": NI * NJ, "far_field_chords": Ro, "wake_chords": Lw, "n_i": NI, "n_j": NJ,
            "dy_wake_outlet_m": dy_out, "mesh": "single-block C-grid, Hermite wall-normal lines (cfd_airfoil2d.c_grid)"}
    return files, info


def case_files(code, alpha, c, U, nu, dz):
    a = math.radians(alpha)
    Ux, Uy = U * math.cos(a), U * math.sin(a)
    nt_inf = 3.0 * nu                                                   # NASA TMR freestream nuTilda for SA
    nt_0 = nt_inf                                                       # physical start (docstring item 6)
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
wallDist { method Poisson; }                                     // see docstring item 5
"""
    files["system/fvSolution"] = HDR.format(cls="dictionary", loc="", obj="fvSolution") + """
solvers
{
    yPsi { solver GAMG; smoother GaussSeidel; tolerance 1e-8; relTol 0; }
    Phi { solver GAMG; smoother GaussSeidel; tolerance 1e-8; relTol 0.01; }
    p { solver GAMG; smoother GaussSeidel; tolerance 1e-7; relTol 0.1; }
    "(U|nuTilda)" { solver smoothSolver; smoother GaussSeidel; tolerance 1e-9; relTol 0.1; nSweeps 2; }
}
SIMPLE { nNonOrthogonalCorrectors 1; residualControl { p 1e-5; U 1e-6; nuTilda 1e-6; } }
relaxationFactors { fields { p 0.3; } equations { U 0.7; nuTilda 0.7; } }
potentialFlow { nNonOrthogonalCorrectors 3; }          // potentialFoam start, item 6
"""
    bc = lambda name, cls, dim, internal, far, wall: HDR.format(cls=cls, loc='location "0"; ', obj=name) + \
        f"dimensions {dim};\ninternalField uniform {internal};\nboundaryField\n{{\n    farfield {{ {far} }}\n    airfoil {{ {wall} }}\n    frontAndBack {{ type empty; }}\n}}\n"
    Uv = f"({Ux:.8f} {Uy:.8f} 0)"
    files["0/U"] = bc("U", "volVectorField", "[0 1 -1 0 0 0 0]", Uv, f"type freestreamVelocity; freestreamValue uniform {Uv}; value uniform {Uv};", "type noSlip;")
    files["0/p"] = bc("p", "volScalarField", "[0 2 -2 0 0 0 0]", "0", "type freestreamPressure; freestreamValue uniform 0; value uniform 0;", "type zeroGradient;")
    files["0/nuTilda"] = bc("nuTilda", "volScalarField", "[0 2 -1 0 0 0 0]", f"{nt_0:.6e}", f"type freestream; freestreamValue uniform {nt_inf:.6e};", "type fixedValue; value uniform 1e-30;")   # > 0: see docstring item 4
    files["0/nut"] = bc("nut", "volScalarField", "[0 2 -1 0 0 0 0]", f"{nt_0:.6e}", f"type freestream; freestreamValue uniform {nt_inf:.6e};", "type nutUSpaldingWallFunction; value uniform 0;")
    return files


def setup(codes=None):
    sz = jload(os.path.join(RESULTS, "sizing.json"))
    codes = codes or (sz["wing"]["airfoil"], "0012")
    U, nu = sz["cruise"]["V"], sz["air"]["mu"] / sz["air"]["rho"]
    pf = os.path.join(CFD, "plan.json")                           # keep the cases of sections not set up again (the
    plan = {k: v for k, v in (jload(pf) if os.path.exists(pf) else {}).items() if k != "run_dir"}   # NACA 4415 record)
    for code in codes:
        c = sz["wing"]["c"] if code == sz["wing"]["airfoil"] else sz["stability"]["c_h"]
        alphas = [-4, 0, 4, 8, 10, 12, 13, 14, 15, 16] if code != "0012" else [0, 4, 8, 12]   # ~27 min per case on 1 core
        dz = 0.01 * c
        mesh_files, info = c_grid(code, c, U, nu, dz)
        for a in alphas:
            d = os.path.join(CFD, code, f"a{a:+03d}")
            if os.path.isdir(d):                                  # clear the previous run so run_all.sh re-runs it
                for e in os.listdir(d):
                    if e == "postProcessing" or e.startswith("log.") or (e not in ("0", "constant", "system") and e.replace(".", "").isdigit()):
                        pth = os.path.join(d, e); shutil.rmtree(pth) if os.path.isdir(pth) else os.remove(pth)
                shutil.rmtree(os.path.join(d, "0"), ignore_errors=True)
            for sub in ("system", "constant/polyMesh", "0"): os.makedirs(os.path.join(d, sub), exist_ok=True)
            if os.path.exists(os.path.join(d, "system", "blockMeshDict")): os.remove(os.path.join(d, "system", "blockMeshDict"))
            for k_, txt in mesh_files.items():
                with open(os.path.join(d, "constant", "polyMesh", k_), "w") as f: f.write(txt)
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
  checkMesh > log.checkMesh 2>&1
  nice -n 19 potentialFoam -initialiseUBCs > log.potentialFoam 2>&1
  nice -n 19 foamRun > log.foamRun 2>&1
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
    cmd = f"source /opt/openfoam13/etc/bashrc && cd '{case}' && nice -n 19 checkMesh > log.checkMesh 2>&1; tail -30 log.checkMesh"
    print(subprocess.run(["bash", "-c", cmd], capture_output=True, text=True).stdout)


def xfoil_polar(code, re, mach, xtr=1.0, ncrit=9.0):
    """XFOIL polar at one Re, free transition (xtr 1) or tripped (xtr 0.05 both sides). Rows (alpha, cl, cd, cdp, cm, ...).
    NACA codes and coordinate files alike (wing_sections.run)."""
    import wing_sections as ws
    return ws.run(code, re, mach, ncrit=ncrit, xtr=(xtr, xtr), a_pos=(0.0, 18.0), iters=300)


def post():
    plan = jload(os.path.join(CFD, "plan.json"))
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
            rng = float(np.ptp(data[-1000:, col["Cl"]]))                # steady test: cl range over the last 1000 iterations (< 0.2; low-alpha runs wobble 0.05-0.08, separated ones swing > 1)
            log = open(os.path.join(d, "log.foamRun")).read() if os.path.exists(os.path.join(d, "log.foamRun")) else ""
            rows.append({"alpha": a, "cl": cl, "cd": cd, "cm": cm, "cl_std_last200": osc, "cl_range_last1000": rng, "steady": rng < 0.2, "iterations": int(data[-1, 0]),
                         "converged": "SIMPLE solution converged" in log})
        sz = jload(os.path.join(RESULTS, "sizing.json"))
        mach = pl["U"] / sz["air"]["a"]
        polars = {}
        for tag, xtr in (("", 1.0), ("_trip", 0.05)):             # free transition (as sizing) and tripped at 5 % c
            P = xfoil_polar(code, pl["Re"], mach, xtr)
            polars["free" if not tag else "trip05"] = P[:, :3].round(5).tolist()   # alpha, cl, cd
            for r in rows:
                if "cl" not in r or not (P[0, 0] <= r["alpha"] <= P[-1, 0]): continue
                r[f"xfoil{tag}_cl"] = float(np.interp(r["alpha"], P[:, 0], P[:, 1])); r[f"xfoil{tag}_cd"] = float(np.interp(r["alpha"], P[:, 0], P[:, 2]))
                r[f"diff{tag}_cl_pct"] = 100 * (r["cl"] / r[f"xfoil{tag}_cl"] - 1) if abs(r[f"xfoil{tag}_cl"]) > 0.05 else None
                r[f"diff{tag}_cd_pct"] = 100 * (r["cd"] / r[f"xfoil{tag}_cd"] - 1)
        out[code] = {"plan": pl, "rows": rows, "xfoil": polars}
        for a in pl["alphas"]:                                     # keep logs + force histories in the repo
            src = os.path.join(CFD, code, f"a{a:+03d}"); dst = os.path.join(REPO_CFD, code, f"a{a:+03d}")
            if not os.path.isdir(src): continue
            os.makedirs(dst, exist_ok=True)
            for fn in ("log.checkMesh", "log.potentialFoam", "log.foamRun"):
                if os.path.exists(os.path.join(src, fn)): shutil.copy(os.path.join(src, fn), dst)
            if os.path.isdir(os.path.join(src, "postProcessing")):
                shutil.copytree(os.path.join(src, "postProcessing"), os.path.join(dst, "postProcessing"), dirs_exist_ok=True)
    plot(out)
    with open(os.path.join(RESULTS, "cfd_airfoil2d.json"), "w") as f: json.dump(out, f, indent=1)
    with open(os.path.join(SUMMARY, "summary.json"), "w") as f: json.dump(out, f, indent=1)
    print(json.dumps(out, indent=1))


def plot(out):
    """cl(alpha) and the drag polar, CFD against XFOIL free and tripped -> results/cfd_airfoil2d_polar.png."""
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(len(out), 2, figsize=(10, 3.6 * len(out)), squeeze=False)
    for k, (code, blk) in enumerate(out.items()):
        r = [x for x in blk["rows"] if "cl" in x and x.get("steady", True)]   # steady runs only
        un = [x["alpha"] for x in blk["rows"] if "cl" in x and not x.get("steady", True)]
        import wing_sections as ws
        nm = ws.LABEL.get(code, "NACA " + code)
        A, CL, CD = (np.array([x[q] for x in r]) for q in ("alpha", "cl", "cd"))
        for name, sty in (("free", "-"), ("trip05", "--")):
            P = np.array(blk["xfoil"][name])
            lab = "XFOIL free (Ncrit 9)" if name == "free" else "XFOIL tripped 5 % c"
            ax[k, 0].plot(P[:, 0], P[:, 1], "k" + sty, lw=1, label=lab); ax[k, 1].plot(P[:, 2], P[:, 1], "k" + sty, lw=1, label=lab)
        ax[k, 0].plot(A, CL, "o", color="C0", label="OpenFOAM SA (cl used)")
        for a_ in un: ax[k, 0].axvline(a_, color="C3", ls=":", lw=1)
        if un: ax[k, 0].plot([], [], color="C3", ls=":", lw=1, label="SA unsteady (no steady solution)")
        ax[k, 1].plot(CD, CL, "x", color="C3", label="OpenFOAM SA (cd NOT used: item 7)")
        ax[k, 0].set(xlabel="alpha [deg]", ylabel="cl", title=f"{nm}, Re {blk['plan']['Re']:.2e}: lift")
        ax[k, 1].set(xlabel="cd", ylabel="cl", title=f"{nm}: drag polar")
        for a_ in ax[k]: a_.grid(alpha=0.3); a_.legend(fontsize=7)
    fig.tight_layout(); fig.savefig(os.path.join(RESULTS, "cfd_airfoil2d_polar.png"), dpi=130); plt.close(fig)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "setup": setup(tuple(sys.argv[2:]) or None)
    elif cmd == "mesh": mesh(sys.argv[2])
    elif cmd == "post": post()

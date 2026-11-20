"""Wing-section polars from XFOIL for NACA codes AND coordinate files (geometry/airfoils/<name>.dat, UIUC database).

Why a second runner: the Props program's run_xfoil only uses XFOIL's NACA generator, which limits the wing to NACA 4- and
5-digit sections. The high-lift general-aviation sections (NASA LS(1)-0417 = GA(W)-1, NLF(1)-0416) exist only as
coordinates, so this runner LOADs a Selig-order file (TE -> upper -> LE -> lower -> TE) and repanels it (PPAR).

UIUC files come in two layouts:
  Selig:    name line, then x z from the upper TE round the nose to the lower TE.
  Lednicer: name line, a line "n_upper. n_lower.", then the upper surface LE -> TE and the lower surface LE -> TE.
read_coords() accepts both and returns the Selig loop.

Transition: free (e^N, ncrit 9) and tripped (XTR 0.05 upper / 0.10 lower). Tripped is the "dirty wing" case: bugs, rain,
a composite seam or a fastener row trip the laminar run, so a section must still lift tripped. The airfoil CFD (SA RANS,
fully turbulent) also matches the tripped XFOIL lift better than the free one.
"""
import math, os, shutil, subprocess, tempfile
import numpy as np
from tiltcfg import ROOT

AIRFOIL_DIR = os.path.join(ROOT, "geometry", "airfoils")
LABEL = {"ls417": "LS(1)-0417 (GA(W)-1)", "ls417mod": "LS(1)-0417MOD", "nlf416": "NLF(1)-0416"}
XTR_TRIP = (0.05, 0.10)


def is_naca(name): return name.isdigit()


def read_coords(name):
    """Selig-order (N, 2) array for a coordinate-file section."""
    L = [l for l in open(os.path.join(AIRFOIL_DIR, name + ".dat")).read().splitlines()]
    rows = []
    for l in L[1:]:
        try:
            v = [float(s) for s in l.split()]
        except ValueError:
            continue
        if len(v) == 2: rows.append(v)
    rows = np.array(rows)
    if rows[0, 0] > 1.5:                                         # Lednicer: first row holds the point counts
        nu, nl = int(rows[0, 0]), int(rows[0, 1])
        up, lo = rows[1:1 + nu], rows[1 + nu:1 + nu + nl]
        return np.vstack([up[::-1], lo[1:]])
    return rows


def surfaces(name, n=401):
    """x, z_upper, z_lower on a common x grid (cosine spacing), chord 1."""
    if is_naca(name):
        from geometry import naca4
        x, z = naca4(name, n=200)
        P = np.c_[x, z]
    else:
        P = read_coords(name)
    i = int(np.argmin(P[:, 0]))
    up, lo = P[: i + 1][::-1], P[i:]
    xs = 0.5 * (1 - np.cos(np.linspace(0, math.pi, n)))
    return xs, np.interp(xs, up[:, 0], up[:, 1]), np.interp(xs, lo[:, 0], lo[:, 1])


def thickness(name):
    """Max t/c (NACA codes: from the code; files: from the coordinates)."""
    if is_naca(name): return int(name[-2:]) / 100
    xs, zu, zl = surfaces(name)
    return float((zu - zl).max())


def run(name, re, mach, ncrit=9.0, xtr=(1.0, 1.0), a_pos=(0.0, 20.0), a_neg=(-0.5, -6.0), step=0.5, iters=200,
        panels=200, timeout=300):
    """One XFOIL session (sweep up from 0, re-initialise, sweep down). Returns alpha, cl, cd, cdp, cm, xtr_top, xtr_bot."""
    import airfoils                                              # Props program: XFOIL path and the no-FPE shim
    with tempfile.TemporaryDirectory() as td:
        if is_naca(name):
            geo = f"NACA {name}\n"
        else:
            P = read_coords(name)
            with open(os.path.join(td, "af.dat"), "w") as fh:
                fh.write(name + "\n" + "\n".join(f"{x:.6f} {z:.6f}" for x, z in P) + "\n")
            geo = "LOAD af.dat\n"
        cmds = f"""PLOP
G F

{geo}PPAR
N {panels}


OPER
VISC {re:.0f}
MACH {mach:.3f}
VPAR
N {ncrit}
XTR {xtr[0]} {xtr[1]}

ITER {iters}
PACC
p.txt

ASEQ {a_pos[0]} {a_pos[1]} {step}
INIT
ASEQ {a_neg[0]} {a_neg[1]} {-step}
PACC

QUIT
"""
        env = dict(os.environ)
        env.pop("DISPLAY", None)
        if os.path.exists(airfoils.SHIM):
            shutil.copy(airfoils.SHIM, os.path.join(td, "nofpe_shim.so"))
            env["LD_PRELOAD"] = "./nofpe_shim.so"
        try:
            subprocess.run([airfoils.xfoil_version_and_path()], input=cmds, text=True, capture_output=True, cwd=td,
                           env=env, timeout=timeout, errors="replace")
        except subprocess.TimeoutExpired:
            pass
        rows = []
        pf = os.path.join(td, "p.txt")
        if os.path.exists(pf):
            for line in open(pf, errors="replace"):
                try:
                    vals = [float(x) for x in line.split()[:7]]
                except ValueError:
                    continue
                if len(vals) == 7: rows.append(vals)
    rows = sorted(r for r in rows if r[2] > 0 and abs(r[1]) < 2.5)
    out, seen = [], set()
    for r in rows:
        if r[0] not in seen:
            seen.add(r[0]); out.append(r)
    return np.array(out)


# ------------------------------------------------------------------ section geometry used by every model ------------
# Wing frame: x forward, z up, origin on the root quarter-chord. The chord line sits 2 % c below the spar-box axis
# (as the STL always had), and the section is pitched nose-up by the incidence i about that quarter-chord point:
#     x' = x cos i - z sin i,   z' = x sin i + z cos i      (x = (0.25 - x/c) c, z = -0.02 c + c z_af(x/c))
def contour(name, n=100):
    """Closed contour, unit chord, LE at x = 0: TE -> upper -> LE -> lower -> TE, n points per side (cosine spacing)."""
    xs, zu, zl = surfaces(name, n)
    return np.r_[xs[::-1], xs[1:]], np.r_[zu[::-1], zl[1:]]


def to_wing(xc, zc, c, inc_deg):
    """Section coordinates (x/c aft from the LE, z/c) -> wing frame (x forward from the qc, z up), with incidence."""
    i = math.radians(inc_deg)
    x = (0.25 - np.asarray(xc)) * c
    z = -0.02 * c + c * np.asarray(zc)
    return x * math.cos(i) - z * math.sin(i), x * math.sin(i) + z * math.cos(i)


def depth_at(name, xc):
    """Vertical section thickness z_u - z_l at chord fraction xc (unit chord)."""
    xs, zu, zl = surfaces(name)
    return float(np.interp(xc, xs, zu) - np.interp(xc, xs, zl))


def spar_feet(sz, pw):
    """Wing-frame (x, z) of the root lower-surface points at the front and rear spars (the lug feet)."""
    w = sz["wing"]; xs, zu, zl = surfaces(w["airfoil"])
    out = {}
    for k, xc in (("front", pw["spar_front_xc"]), ("rear", pw["spar_rear_xc"])):
        x, z = to_wing(xc, np.interp(xc, xs, zl), w["c"], w.get("incidence_deg", 0.0))
        out[k] = (float(x), float(z))
    return out


def fuselage_top_z(sz, pw):
    """The fuselage top sits at the LOWER of the two root spar feet; the other lug stands on a pedestal of the difference."""
    f = spar_feet(sz, pw)
    return min(f["front"][1], f["rear"][1])

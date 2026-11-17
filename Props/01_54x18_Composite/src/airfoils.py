"""Airfoil polars: XFOIL runs at the local Reynolds and Mach numbers, Viterna post-stall extension, and a
4-D interpolant (thickness, log Re, Mach, alpha) for the blade-element solver.

XFOIL (Drela) couples a panel method with an integral boundary-layer solution and an e^N transition model. Its
compressibility correction is Karman-Tsien, valid only while the flow stays subsonic everywhere on the section,
so results near and above the critical Mach number are flagged, not trusted.

Viterna-Corrigan extension beyond stall (alpha_s, cl_s, cd_s), for blade aspect ratio AR:
    cd_max = 1.11 + 0.018 AR
    cd = cd_max sin^2(a) + B2 cos(a),                 B2 = (cd_s - cd_max sin^2(a_s)) / cos(a_s)
    cl = (cd_max/2) sin(2a) + A2 cos^2(a) / sin(a),   A2 = (cl_s - cd_max sin(a_s) cos(a_s)) sin(a_s) / cos^2(a_s)
It matches the polar at the stall point and tends to flat-plate behaviour at 90 degrees. Beyond +/-90 degrees and on
the negative side a flat-plate model with the customary 0.7 lift factor is used (reverse-flow region only).
"""
import json, math, os, subprocess, tempfile
import numpy as np
from common import ROOT

XFOIL_LOCAL = os.path.join(ROOT, "tools", "xfoil_pkg", "usr", "bin", "xfoil")
SHIM = os.path.join(ROOT, "tools", "nofpe_shim.so")
POLAR_DIR = os.path.join(ROOT, "results", "polars")
ALPHA_GRID = np.arange(-180.0, 180.0 + 1e-9, 0.5)


def xfoil_version_and_path():
    path = XFOIL_LOCAL if os.path.exists(XFOIL_LOCAL) else "xfoil"
    return path


def run_xfoil(naca, re, mach, a_pos=(0.0, 20.0), a_neg=(-0.5, -10.0), step=0.5, ncrit=9.0, iters=150, panels=200, timeout=300):
    """One XFOIL session: sweep up from 0, re-initialise the boundary layer, sweep down. Returns converged points only."""
    with tempfile.TemporaryDirectory() as td:
        cmds = f"""PLOP
G F

NACA {naca}
PPAR
N {panels}


OPER
VISC {re:.0f}
MACH {mach:.3f}
VPAR
N {ncrit}

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
        if os.path.exists(SHIM):                 # LD_PRELOAD is space-separated, so use a relative path inside the temp dir
            import shutil
            shutil.copy(SHIM, os.path.join(td, "nofpe_shim.so"))
            env["LD_PRELOAD"] = "./nofpe_shim.so"
        try:
            subprocess.run([xfoil_version_and_path()], input=cmds, text=True, capture_output=True, cwd=td, env=env,
                           timeout=timeout, errors="replace")
        except subprocess.TimeoutExpired:
            pass
        rows = []
        pf = os.path.join(td, "p.txt")
        if os.path.exists(pf):
            for line in open(pf, errors="replace"):
                parts = line.split()
                try:
                    vals = [float(x) for x in parts[:7]]
                except ValueError:
                    continue
                if len(vals) == 7:
                    rows.append(vals)
    rows = [r for r in rows if r[2] > 0 and abs(r[1]) < 2.5]
    rows.sort(key=lambda r: r[0])
    out, seen = [], set()
    for r in rows:
        if r[0] not in seen:
            seen.add(r[0]); out.append(r)
    return np.array(out)        # alpha, cl, cd, cdp, cm, xtr_top, xtr_bot


def viterna(alpha_deg, a_s, cl_s, cd_s, cd_max):
    a, s = np.radians(alpha_deg), math.radians(a_s)
    b2 = (cd_s - cd_max * math.sin(s) ** 2) / math.cos(s)
    a2 = (cl_s - cd_max * math.sin(s) * math.cos(s)) * math.sin(s) / math.cos(s) ** 2
    cl = cd_max / 2 * np.sin(2 * a) + a2 * np.cos(a) ** 2 / np.sin(a)
    cd = cd_max * np.sin(a) ** 2 + b2 * np.cos(a)
    return cl, cd


def extend_polar(data, aspect_ratio):
    """XFOIL points between negative and positive stall, Viterna to +90, flat plate elsewhere. Returns cl, cd on ALPHA_GRID
    and a summary dict."""
    al, cl, cd = data[:, 0], data[:, 1], data[:, 2]
    extrapolated_neg = bool(al.min() > -4.0)
    if extrapolated_neg:                       # negative sweep did not converge: continue the lift line down to -5 deg, cd held
        lin0 = al <= al.min() + 4.0
        sl = np.polyfit(al[lin0], cl[lin0], 1)[0]
        add = np.arange(-5.0, al.min() - 1e-9, 0.5)
        al = np.concatenate([add, al]); cl = np.concatenate([cl[0] + sl * (add - data[0, 0]), cl]); cd = np.concatenate([np.full(len(add), cd[0]), cd])
    ip = int(np.argmax(np.where(al > 0, cl, -9)))            # positive stall = first local maximum of cl (global max as fallback)
    for i in range(len(al) - 2):
        if al[i] >= 4.0 and cl[i] > cl[i + 1] and cl[i] > cl[i + 2]:
            ip = i; break
    im = int(np.argmin(np.where(al < 0.5, cl, 9)))           # negative stall = min cl
    a_s, cl_s, cd_s = al[ip], cl[ip], cd[ip]
    a_n, cl_n, cd_n = al[im], cl[im], cd[im]
    cd_max = 1.11 + 0.018 * aspect_ratio
    g = ALPHA_GRID
    CL, CD = np.empty_like(g), np.empty_like(g)
    flat_cl = 0.7 * cd_max / 2 * np.sin(2 * np.radians(g))
    flat_cd = cd_max * np.sin(np.radians(g)) ** 2 + min(cd)
    CL[:], CD[:] = flat_cl, flat_cd
    core = (g >= a_n) & (g <= a_s)
    CL[core] = np.interp(g[core], al[im:ip + 1], cl[im:ip + 1])
    CD[core] = np.interp(g[core], al[im:ip + 1], cd[im:ip + 1])
    post = (g > a_s) & (g <= 90)
    CL[post], CD[post] = viterna(g[post], a_s, cl_s, cd_s, cd_max)
    blend = (g < a_n) & (g >= a_n - 15)                       # linear blend from negative stall into the flat-plate model
    w = (a_n - g[blend]) / 15.0
    CL[blend] = (1 - w) * cl_n + w * flat_cl[blend]
    CD[blend] = (1 - w) * cd_n + w * flat_cd[blend]
    lin = (al >= -2) & (al <= 4)
    slope, icpt = np.polyfit(al[lin], cl[lin], 1) if lin.sum() >= 3 else (float("nan"), float("nan"))
    ld = cl[im:ip + 1] / cd[im:ip + 1]; pf = np.where(cl[im:ip + 1] > 0, cl[im:ip + 1], 0) ** 1.5 / cd[im:ip + 1]
    k, kp = int(np.argmax(ld)), int(np.argmax(pf))
    summary = {"n_points": int(len(data)), "neg_side_extrapolated": extrapolated_neg, "alpha_stall": float(a_s), "cl_max": float(cl_s), "alpha_neg_stall": float(a_n),
               "cl_min": float(cl_n), "alpha_zero_lift": float(-icpt / slope), "lift_slope_per_deg": float(slope),
               "ld_max": float(ld[k]), "cl_at_ld_max": float(cl[im + k]), "alpha_at_ld_max": float(al[im + k]),
               "cd_min": float(min(cd)), "pf_max": float(pf[kp]), "cl_at_pf_max": float(cl[im + kp]),
               "alpha_at_pf_max": float(al[im + kp])}
    return CL, CD, summary


def polar_case(args):
    """Worker: run one (naca, re, mach) and cache the raw XFOIL points."""
    naca, re, mach = args
    os.makedirs(POLAR_DIR, exist_ok=True)
    f = os.path.join(POLAR_DIR, f"naca{naca}_re{re:.0f}_m{mach:.2f}.json")
    if os.path.exists(f):
        return json.load(open(f))
    d = run_xfoil(naca, re, mach)
    rec = {"naca": naca, "re": re, "mach": mach, "ncrit": 9.0, "points": d.tolist()}
    if len(d):                                   # never cache a failed run
        json.dump(rec, open(f, "w"))
    return rec


class PolarDB:
    """cl, cd as functions of (t/c, Re, Mach, alpha) for one camber family, linear in t/c, log Re, Mach and alpha."""
    def __init__(self, family, thicknesses, re_grid, mach_grid, aspect_ratio, records):
        from scipy.interpolate import RegularGridInterpolator
        self.family, self.tc = family, np.array(thicknesses) / 100.0
        self.re, self.mach, self.ar = np.array(re_grid, float), np.array(mach_grid, float), aspect_ratio
        shape = (len(thicknesses), len(re_grid), len(mach_grid), len(ALPHA_GRID))
        CL, CD = np.full(shape, np.nan), np.full(shape, np.nan)
        self.summary, self.failed = {}, []
        for i, t in enumerate(thicknesses):
            for j, re in enumerate(re_grid):
                for k, m in enumerate(mach_grid):
                    d = np.array(records[(f"{family}{t:02d}", re, m)]["points"])
                    ok = len(d) >= 12 and d[:, 0].max() >= 6
                    if ok:
                        CL[i, j, k], CD[i, j, k], s = extend_polar(d, aspect_ratio)
                        self.summary[(t, re, m)] = s
                    else:
                        self.failed.append((t, re, m, int(len(d))))
        for (i, j, k) in zip(*np.where(np.isnan(CL[..., 0]))):         # fill failed cases from the nearest lower Mach, then Re
            for kk in list(range(k - 1, -1, -1)) + list(range(k + 1, len(mach_grid))):
                if not np.isnan(CL[i, j, kk, 0]):
                    CL[i, j, k], CD[i, j, k] = CL[i, j, kk], CD[i, j, kk]; break
        if np.isnan(CL).any():
            raise RuntimeError(f"polar database has unfilled cases: {self.failed}")
        self.valid = ~np.isnan(np.array([[[self.summary.get((t, re, m), {}).get("cl_max", np.nan) for m in mach_grid] for re in re_grid] for t in thicknesses]))
        self._props = {}
        for name in ("alpha_stall", "cl_max", "alpha_at_ld_max", "cl_at_ld_max", "alpha_at_pf_max", "alpha_zero_lift", "ld_max"):
            arr = np.array([[[self.summary.get((t, re, m), {}).get(name, np.nan) for m in mach_grid] for re in re_grid] for t in thicknesses])
            for (i, j, k) in zip(*np.where(np.isnan(arr))):
                for kk in range(k - 1, -1, -1):
                    if not np.isnan(arr[i, j, kk]):
                        arr[i, j, k] = arr[i, j, kk]; break
            self._props[name] = RegularGridInterpolator((self.tc, np.log(self.re), self.mach), arr)
        ax = (self.tc, np.log(self.re), self.mach, np.radians(ALPHA_GRID))
        self._cl = RegularGridInterpolator(ax, CL); self._cd = RegularGridInterpolator(ax, CD)

    def lookup(self, tc, re, mach, alpha):
        """All arguments broadcastable arrays; alpha in radians (any value, wrapped). Inputs outside the grid are clamped."""
        tc, re, mach, alpha = np.broadcast_arrays(np.asarray(tc, float), np.asarray(re, float), np.asarray(mach, float), np.asarray(alpha, float))
        a = (alpha + np.pi) % (2 * np.pi) - np.pi
        pts = np.stack([np.clip(tc, self.tc[0], self.tc[-1]), np.log(np.clip(re, self.re[0], self.re[-1])),
                        np.clip(mach, self.mach[0], self.mach[-1]), a], axis=-1)
        return self._cl(pts), self._cd(pts)


    def prop(self, name, tc, re, mach):
        """Section property (degrees for angles) interpolated in (t/c, log Re, Mach)."""
        tc, re, mach = np.broadcast_arrays(np.asarray(tc, float), np.asarray(re, float), np.asarray(mach, float))
        pts = np.stack([np.clip(tc, self.tc[0], self.tc[-1]), np.log(np.clip(re, self.re[0], self.re[-1])), np.clip(mach, self.mach[0], self.mach[-1])], axis=-1)
        return self._props[name](pts)


class AnalyticPolar:
    """Idealised section for solver tests only: cl = a (alpha - alpha0), constant cd. Not used for design numbers."""
    def __init__(self, slope=2 * math.pi, alpha0=0.0, cd=0.0):
        self.slope, self.alpha0, self.cd = slope, alpha0, cd

    def lookup(self, tc, re, mach, alpha):
        alpha = np.asarray(alpha, float)
        return self.slope * (alpha - self.alpha0), np.full_like(alpha, self.cd)


def build_db(p, n_proc=None):
    """Run (or load from cache) every XFOIL case in params['airfoils'] and return (PolarDB, comparison records)."""
    from multiprocessing import Pool
    af = p["airfoils"]
    cases = [(f"{af['family']}{t:02d}", float(re), float(m)) for t in af["thicknesses_pct"] for re in af["re_grid"] for m in af["mach_grid"]]
    comp = [(n, float(af["compare_re"]), float(af["compare_mach"])) for n in af["compare_sections"]]
    cached = lambda c: os.path.exists(os.path.join(POLAR_DIR, f"naca{c[0]}_re{c[1]:.0f}_m{c[2]:.2f}.json"))
    if all(cached(c) for c in cases + comp):
        recs = [polar_case(c) for c in cases + comp]
    else:
        with Pool(n_proc or min(16, os.cpu_count())) as pool:
            recs = pool.map(polar_case, cases + comp, chunksize=1)
    by = {(r["naca"], r["re"], r["mach"]): r for r in recs}
    db = PolarDB(af["family"], af["thicknesses_pct"], [float(x) for x in af["re_grid"]], [float(x) for x in af["mach_grid"]],
                 af["viterna_aspect_ratio"], by)
    comparison = []
    for n, re, m in comp:
        d = np.array(by[(n, re, m)]["points"])
        if len(d) >= 12:
            comparison.append(dict(naca=n, re=re, mach=m, **extend_polar(d, af["viterna_aspect_ratio"])[2]))
    return db, comparison

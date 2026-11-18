"""XFOIL polars for sections given as coordinates (airfoils.run_xfoil only builds NACA 4/5-digit sections internally).
Same session recipe as airfoils.run_xfoil (PPAR 200 panels, Ncrit 9, sweep up from 0, re-init, sweep down) and the
same cache format in results/polars, keyed 'naca<name>' so airfoils.PolarDB can read the records."""
import json, os, shutil, subprocess, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import numpy as np
import airfoils
import naca_mod4


def run_coords(name, xy, re, mach, a_pos=(0.0, 20.0), a_neg=(-0.5, -10.0), step=0.5, ncrit=9.0, iters=150, panels=200, timeout=300):
    with tempfile.TemporaryDirectory() as td:
        with open(os.path.join(td, "af.dat"), "w") as fh:
            fh.write(f"NACA {name}\n"); fh.writelines(f"{x:.6f} {y:.6f}\n" for x, y in xy)
        cmds = f"""PLOP
G F

LOAD af.dat
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
        env = dict(os.environ); env.pop("DISPLAY", None)
        if os.path.exists(airfoils.SHIM):
            shutil.copy(airfoils.SHIM, os.path.join(td, "nofpe_shim.so")); env["LD_PRELOAD"] = "./nofpe_shim.so"
        try:
            subprocess.run([airfoils.xfoil_version_and_path()], input=cmds, text=True, capture_output=True, cwd=td, env=env, timeout=timeout, errors="replace")
        except subprocess.TimeoutExpired:
            pass
        rows = []
        pf = os.path.join(td, "p.txt")
        if os.path.exists(pf):
            for line in open(pf, errors="replace"):
                try: vals = [float(x) for x in line.split()[:7]]
                except ValueError: continue
                if len(vals) == 7: rows.append(vals)
    rows = [r for r in rows if r[2] > 0 and abs(r[1]) < 2.5]; rows.sort(key=lambda r: r[0])
    out, seen = [], set()
    for r in rows:
        if r[0] not in seen: seen.add(r[0]); out.append(r)
    return np.array(out)


def case(args):
    """name like '2412-65' -> cached record under results/polars/naca2412-65_re..._m....json"""
    name, re, mach = args
    os.makedirs(airfoils.POLAR_DIR, exist_ok=True)
    f = os.path.join(airfoils.POLAR_DIR, f"naca{name}_re{re:.0f}_m{mach:.2f}.json")
    if os.path.exists(f): return json.load(open(f))
    d = run_coords(name, naca_mod4.coords(name), re, mach)
    rec = {"naca": name, "re": re, "mach": mach, "ncrit": 9.0, "points": d.tolist(), "source": "coordinates, naca_mod4"}
    if len(d): json.dump(rec, open(f, "w"))
    return rec


def build_db(family, suffix, p, n_proc=4):
    """family '24', suffix '65' -> PolarDB over p['airfoils'] thicknesses/Re/Mach for NACA 24tt-65."""
    from multiprocessing import Pool
    af = p["airfoils"]
    cases = [(f"{family}{t:02d}-{suffix}", float(re), float(m)) for t in af["thicknesses_pct"] for re in af["re_grid"] for m in af["mach_grid"]]
    todo = [c for c in cases if not os.path.exists(os.path.join(airfoils.POLAR_DIR, f"naca{c[0]}_re{c[1]:.0f}_m{c[2]:.2f}.json"))]
    if todo:
        with Pool(n_proc) as pool: pool.map(case, todo, chunksize=1)
    recs = [case(c) for c in cases]
    by = {}
    for r in recs:                                # PolarDB keys records as (family + 2-digit thickness, re, mach)
        t = r["naca"].split("-")[0][2:]
        by[(f"{family}m{suffix}{t}", r["re"], r["mach"])] = r
    return airfoils.PolarDB(f"{family}m{suffix}", af["thicknesses_pct"], [float(x) for x in af["re_grid"]], [float(x) for x in af["mach_grid"]], af["viterna_aspect_ratio"], by)

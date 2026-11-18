"""Caradonna-Tung torque diagnosis (pvpython): radial split of blade pressure thrust and torque, chordwise vs chord-normal
force, and the torque the missing leading-edge suction costs. Hard-wired to the C-T case (8 deg, R 1.143 m, c 0.1905 m).
Usage: pvpython src/ct_torque_split.py <case dir> <time> <rho> <out.json>"""
import sys, json
import numpy as np
from paraview.simple import OpenFOAMReader, MergeBlocks, ExtractSurface, servermanager
from vtk.util.numpy_support import vtk_to_numpy as v2n

case, t, rho = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
rd = OpenFOAMReader(FileName=case + "/coarse.foam")
rd.CaseType = "Decomposed Case"
rd.MeshRegions = ["patch/blades"]
rd.CellArrays = ["p", "U", "yPlus"]
rd.UpdatePipeline(t)
m = MergeBlocks(Input=rd); s = ExtractSurface(Input=m); s.UpdatePipeline(t)
pd = servermanager.Fetch(s)
P = v2n(pd.GetPoints().GetData())
p = v2n(pd.GetCellData().GetArray("p"))
yp = v2n(pd.GetCellData().GetArray("yPlus"))
cen, Sv = [], []
for i in range(pd.GetNumberOfCells()):
    ids = pd.GetCell(i).GetPointIds()
    v = P[[ids.GetId(k) for k in range(ids.GetNumberOfIds())]]
    c = v.mean(0)
    S = 0.5 * sum(np.cross(v[k] - c, v[(k + 1) % len(v)] - c) for k in range(len(v)))   # area vector, OpenFOAM order
    cen.append(c); Sv.append(S)
cen, Sv = np.array(cen), np.array(Sv)
F = rho * p[:, None] * Sv                       # patch normal points out of the fluid (into the blade): force on blade = p S
r = np.hypot(cen[:, 0], cen[:, 1])
Mz = cen[:, 0] * F[:, 1] - cen[:, 1] * F[:, 0]
out = {"n_faces": len(p), "Fz_total": float(F[:, 2].sum()), "Mz_total": float(Mz.sum()), "area": float(np.linalg.norm(Sv, axis=1).sum())}
edges = np.linspace(0, 1.143 * 1.001, 24)
rows = []
for a, b in zip(edges[:-1], edges[1:]):
    k = (r >= a) & (r < b)
    if k.any():
        rows.append({"r_mid": float((a + b) / 2), "dr": float(b - a), "Fz": float(F[k, 2].sum()), "Q": float(-Mz[k].sum()),
                     "yplus_mean": float(yp[k].mean()), "n": int(k.sum())})
out["bands"] = rows
json.dump(out, open(sys.argv[4], "w"), indent=1)
print(json.dumps({k: v for k, v in out.items() if k != "bands"}))
for q in rows: print(f"{q['r_mid']:.3f} Fz {q['Fz']:8.2f} Q {q['Q']:7.2f} y+ {q['yplus_mean']:6.1f} n {q['n']}")

# ---- blade-fixed axes: chordwise force (+ toward leading edge = suction) and chord-normal force -------------
th = np.radians(8.0)
sgn = np.where(cen[:, 0] >= 0, 1.0, -1.0)            # blade on -x is the same blade turned half a revolution
Fy, Fz_ = F[:, 1] * sgn, F[:, 2]
Fc = Fy * np.cos(th) + Fz_ * np.sin(th); Fn = -Fy * np.sin(th) + Fz_ * np.cos(th)
print("\n r/R   Fn[N]   Fc[N]  psi=atan(Fc/Fn)[deg]  (ideal ~ alpha_eff, i.e. a few deg forward)")
for a, b in zip(edges[:-1], edges[1:]):
    k = (r >= a) & (r < b)
    if k.any() and Fn[k].sum() > 1:
        print(f"{(a+b)/2/1.143:5.2f} {Fn[k].sum():7.2f} {Fc[k].sum():7.3f} {np.degrees(np.arctan2(Fc[k].sum(), Fn[k].sum())):7.2f}")
print("total Fn %.1f Fc %.2f" % (Fn.sum(), Fc.sum()))
# leading-edge region only (front 10 % of chord) vs rest
a_ = (cen[:, 1] * sgn) * np.cos(th) + cen[:, 2] * np.sin(th); xc = 0.25 - a_ / 0.1905
for lo, hi in ((-.05, .02), (.02, .1), (.1, .5), (.5, 1.05)):
    k = (xc >= lo) & (xc < hi) & (r > 0.3)
    print(f"x/c {lo:.2f}-{hi:.2f}: Fc {Fc[k].sum():8.2f} N  Fn {Fn[k].sum():8.1f} N  faces {k.sum()}")

# ---- what the torque would be with the leading-edge suction an attached airfoil should have --------------------
om, c, rho_, M75 = 130.8997, 0.1905, rho, 0.439
a0 = 2 * np.pi * 0.95 / np.sqrt(1 - (M75 * 0.75) ** 2)    # NACA 0012 lift slope ~0.95 x 2 pi, Prandtl-Glauert
cdp = 0.002                                                # attached-flow pressure drag of NACA 0012 near Re 2e6, cl 0.3
dQ_tot = 0.0; rows = []
for a, b in zip(edges[:-1], edges[1:]):
    k = (r >= a) & (r < b) & (np.abs(cen[:, 0]) > 0)
    if not k.any() or Fn[k].sum() < 1: continue
    rm = (a + b) / 2; q = 0.5 * rho_ * (om * rm) ** 2; S2 = 2 * c * (b - a)
    cn = Fn[k].sum() / (q * S2); al = cn / a0
    fc_ideal = Fn[k].sum() * np.tan(al) - cdp * q * S2
    dfc = fc_ideal - Fc[k].sum()
    dQ = rm * dfc * np.cos(th); dQ_tot += dQ
    rows.append((rm / 1.143, cn, np.degrees(al), Fc[k].sum(), fc_ideal, dQ))
print("\n r/R    cn   alpha  Fc_cfd  Fc_ideal  dQ[N m]")
for w in rows: print("%5.2f %5.3f %5.2f %7.2f %8.2f %7.2f" % w)
print("torque removed if the suction were right: %.1f N m of %.1f pressure torque" % (dQ_tot, -Mz.sum()))

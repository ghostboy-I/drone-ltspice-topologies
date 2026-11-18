"""pvpython: rotor-surface face centres, area vectors and kinematic pressure from a decomposed OpenFOAM case, to .npz.
Reads only the rotor patch (not the volume mesh), so it is light on memory.
Usage: pvpython src/extract_surface.py <case dir> <foam file name> <time> <out.npz>"""
import sys
import numpy as np
from paraview.simple import OpenFOAMReader, MergeBlocks, ExtractSurface, servermanager
from vtk.util.numpy_support import vtk_to_numpy as v2n

case, foam, t, out = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4]
rd = OpenFOAMReader(FileName=case + "/" + foam)
rd.CaseType = "Decomposed Case"
rd.MeshRegions = ["patch/rotor"]
rd.CellArrays = ["p", "yPlus"]
rd.UpdatePipeline(t)
s = ExtractSurface(Input=MergeBlocks(Input=rd)); s.UpdatePipeline(t)
pd = servermanager.Fetch(s)
P = v2n(pd.GetPoints().GetData()).astype(float)
p = v2n(pd.GetCellData().GetArray("p")).astype(float)
yp = v2n(pd.GetCellData().GetArray("yPlus")).astype(float) if pd.GetCellData().GetArray("yPlus") else np.zeros_like(p)
cen, Sv = np.zeros((pd.GetNumberOfCells(), 3)), np.zeros((pd.GetNumberOfCells(), 3))
for i in range(pd.GetNumberOfCells()):
    ids = pd.GetCell(i).GetPointIds()
    v = P[[ids.GetId(k) for k in range(ids.GetNumberOfIds())]]
    c = v.mean(0)
    cen[i] = c
    Sv[i] = 0.5 * sum(np.cross(v[k] - c, v[(k + 1) % len(v)] - c) for k in range(len(v)))   # OpenFOAM order: out of the fluid
np.savez_compressed(out, cen=cen, S=Sv, p=p, yplus=yp, time=t)
print("faces", len(p), "area", float(np.linalg.norm(Sv, axis=1).sum()))

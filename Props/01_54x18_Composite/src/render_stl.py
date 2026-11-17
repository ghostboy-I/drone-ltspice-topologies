"""pvpython script: off-screen renders of the STL files for visual checking. Usage: pvpython src/render_stl.py"""
import os
from paraview.simple import *
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
view = GetActiveViewOrCreate("RenderView"); view.ViewSize = [1500, 700]; view.Background = [1, 1, 1]; view.OrientationAxesVisibility = 1
for name, color in (("prop_ccw", [0.25, 0.25, 0.28]), ("prop_cw", [0.16, 0.47, 0.84])):
    src = STLReader(FileNames=[os.path.join(root, "geometry", name + ".stl")])
    rep = Show(src, view); rep.DiffuseColor = color; rep.Specular = 0.3
    for tag, pos, up in (("top", [0, 0, 3.0], [0, 1, 0]), ("iso", [1.1, -1.5, 0.9], [0, 0, 1]), ("root", [0.25, -0.35, 0.18], [0, 0, 1])):
        view.CameraPosition = pos; view.CameraFocalPoint = [0.12 if tag == "root" else 0, 0, 0]; view.CameraViewUp = up
        if tag != "root": ResetCamera(view); view.CameraPosition = pos; view.CameraFocalPoint = [0, 0, 0]; view.CameraViewUp = up; ResetCamera(view)
        SaveScreenshot(os.path.join(root, "results", f"phase3_{name}_{tag}.png"), view)
    Hide(src, view)

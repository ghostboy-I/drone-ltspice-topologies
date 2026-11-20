"""Outer-mould-line geometry of the Osprey-style tilt-hex, from results/sizing.json and designs/selected.json.

Six rotors: a tilting head at each wing tip (pod) and one inboard on a pylon ahead of the leading edge per side,
plus two fixed lift rotors aft on a tail cross-beam.

Writes (geometry/):
  airframe_hover.stl, airframe_airplane.stl   multi-solid ASCII STL, one named solid per part (fuselage, wing, pod_L ...),
                                               closed surfaces, metres, same axes as the FE model -> ready for snappyHexMesh
  rotor_disks_hover.stl                        actuator-disk surfaces for a later download / interference CFD
  wing_section.dat                             the NACA 4-digit wing section (Selig format) for the 2-D CFD case
and results/fig_3view.png, results/fig_iso_hover.png, results/fig_iso_airplane.png.

Shapes: the fuselage is a loft of super-ellipse sections |y/a|^n + |z/b|^n = 1 (n = 2.6: the V-22's boxy, rounded
cabin), with an ogive nose and an upswept aft ramp. The wing and tail surfaces are lofts of NACA 4-digit sections.
"""
import json, math, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from tiltcfg import ROOT, RESULTS, params, af01_params, jload
import tiltframe as tf
import wing_sections as wsec

GEO = os.path.join(ROOT, "geometry")
os.makedirs(GEO, exist_ok=True)


# ------------------------------------------------------------------ primitives --------------------------------------
def naca4(code, n=60):
    """Closed NACA 4-digit contour, unit chord, LE at x=0, TE->upper->LE->lower->TE (n points per side)."""
    m, pp, t = int(code[0]) / 100, int(code[1]) / 10, int(code[2:]) / 100
    beta = np.linspace(0, math.pi, n)
    x = 0.5 * (1 - np.cos(beta))
    yt = 5 * t * (0.2969 * np.sqrt(x) - 0.1260 * x - 0.3516 * x ** 2 + 0.2843 * x ** 3 - 0.1036 * x ** 4)
    if m > 0:
        yc = np.where(x < pp, m / pp ** 2 * (2 * pp * x - x ** 2), m / (1 - pp) ** 2 * ((1 - 2 * pp) + 2 * pp * x - x ** 2))
        dy = np.where(x < pp, 2 * m / pp ** 2 * (pp - x), 2 * m / (1 - pp) ** 2 * (pp - x))
    else:
        yc = np.zeros_like(x); dy = np.zeros_like(x)
    th = np.arctan(dy)
    xu, zu = x - yt * np.sin(th), yc + yt * np.cos(th)
    xl, zl = x + yt * np.sin(th), yc - yt * np.cos(th)
    return np.r_[xu[::-1], xl[1:]], np.r_[zu[::-1], zl[1:]]


def loft(rings, cap=True):
    """Triangles of a surface through rings (each (m,3), same m, closed loops); end caps as fans."""
    tris = []
    for a, b in zip(rings[:-1], rings[1:]):
        m = len(a)
        for i in range(m):
            j = (i + 1) % m
            tris += [(a[i], b[i], b[j]), (a[i], b[j], a[j])]
    if cap:
        for ring, flip in ((rings[0], True), (rings[-1], False)):
            c = ring.mean(axis=0); m = len(ring)
            for i in range(m):
                j = (i + 1) % m
                tris.append((c, ring[j], ring[i]) if flip else (c, ring[i], ring[j]))
    return np.array(tris)


def surface_of_revolution(p0, axis, stations, radii, n=32):
    axis = np.asarray(axis, float); axis /= np.linalg.norm(axis)
    ref = np.array([0, 0, 1.0]) if abs(axis[2]) < 0.9 else np.array([1.0, 0, 0])
    e1 = np.cross(axis, ref); e1 /= np.linalg.norm(e1); e2 = np.cross(axis, e1)
    th = np.linspace(0, 2 * math.pi, n, endpoint=False)
    rings = [np.asarray(p0) + s * axis + np.maximum(r, 1e-4) * (np.outer(np.cos(th), e1) + np.outer(np.sin(th), e2))
             for s, r in zip(stations, radii)]
    return loft(rings)


def lifting_surface(code, root_le, tip_le, c_root, c_tip, n=40, twist_axis=None):
    """Loft of NACA sections from root to tip LE points (sections lie in x-z planes, LE at the given point)."""
    xs, zs = naca4(code, n)
    rings = []
    for le, c in ((root_le, c_root), (tip_le, c_tip)):
        rings.append(np.c_[le[0] - xs * c, np.full_like(xs, le[1]), le[2] + zs * c])
    return loft(rings)


def fin(code, root_le, height, c_root, c_tip, n=40):
    xs, zs = naca4(code, n)
    rings = []
    for k, c in ((0.0, c_root), (1.0, c_tip)):
        le = np.asarray(root_le) + [-(c_root - c) * 0.3, 0, k * height]
        rings.append(np.c_[le[0] - xs * c, le[1] + zs * c, np.full_like(xs, le[2])])
    return loft(rings)


def write_stl(path, solids):
    with open(path, "w") as f:
        for name, T in solids.items():
            f.write(f"solid {name}\n")
            for a, b, c in T:
                nrm = np.cross(b - a, c - a); L = np.linalg.norm(nrm)
                nrm = nrm / L if L > 0 else nrm
                f.write(f" facet normal {nrm[0]:.6e} {nrm[1]:.6e} {nrm[2]:.6e}\n  outer loop\n")
                for v in (a, b, c): f.write(f"   vertex {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
                f.write("  endloop\n endfacet\n")
            f.write(f"endsolid {name}\n")


SUPER_N = 2.6      # super-ellipse exponent of the fuselage sections


def fuselage_station(s, fu, z_top, nfr, nt):
    """Fuselage section at fraction s of the length (0 = nose): x, half-width, half-height, centre z.
    Shared by the STL loft and the shell FE model (fuselage_shell.py), so both use one outer mould line."""
    H, Wd, Lf = fu["H"], fu["W"], fu["L"]
    x = fu["x_nose"] - s * Lf
    if s < nfr:
        k = math.sqrt(max(1 - ((nfr - s) / nfr) ** 2, 0)) * 0.95 + 0.05     # ogive-like nose
        return x, Wd / 2 * k, H / 2 * (0.55 + 0.45 * k), z_top - H / 2 - (1 - k) * 0.12 * H
    if s > 1 - nt:
        k = (s - (1 - nt)) / nt                                              # 0 -> 1 along the ramp
        hh = H / 2 * (1 - 0.80 * k)
        return x, Wd / 2 * (1 - 0.65 * k), hh, z_top - hh
    return x, Wd / 2, H / 2, z_top - H / 2


# ------------------------------------------------------------------ the vehicle -------------------------------------
def build(mode="hover"):
    p, a1 = params(), af01_params()
    sz = jload(os.path.join(RESULTS, "sizing.json"))
    sel = os.path.join(ROOT, "designs", "selected.json")
    d = tf.merge(tf.DEFAULT, json.load(open(sel)) if os.path.exists(sel) else None)
    w, L, st, fu = sz["wing"], sz["layout"], sz["stability"], sz["fuselage"]
    b, c, tc = w["b"], w["c"], w["tc"]
    R = a1["vehicle"]["rotor_radius_m"]
    tsw, tdi = math.tan(math.radians(-w["sweep_deg"])), math.tan(math.radians(w["dihedral_deg"]))
    S = {}

    # fuselage: super-ellipse loft. Top line level at z_top; the aft 30 % ramps the belly up to the boom.
    z_top = wsec.fuselage_top_z(sz, p["wing"]); H, Wd, Lf = fu["H"], fu["W"], fu["L"]   # at the lower root spar foot
    x0, x1 = fu["x_nose"], fu["x_tail"]
    nfr, nt = p["fuselage"]["nose_frac"], p["fuselage"]["tail_frac"]
    ne = SUPER_N; th = np.linspace(0, 2 * math.pi, 48, endpoint=False)
    se = lambda a_, b_: np.c_[a_ * np.sign(np.cos(th)) * np.abs(np.cos(th)) ** (2 / ne), b_ * np.sign(np.sin(th)) * np.abs(np.sin(th)) ** (2 / ne)]
    rings = []
    for s in np.linspace(0, 1, 40):
        x, hw, hh, zc = fuselage_station(s, fu, z_top, nfr, nt)
        ring = se(hw, hh)
        rings.append(np.c_[np.full(len(th), x), ring[:, 0], zc + ring[:, 1]])
    S["fuselage"] = loft(rings)
    # sponsons (main-gear fairings, the V-22's side bulges)
    x_ml = L["x_cg_hover"] + d["gear"]["main_dx"]
    for side, nm in ((1, "sponson_L"), (-1, "sponson_R")):
        S[nm] = surface_of_revolution((x_ml + 0.35, side * (Wd / 2 + 0.02), z_top - H + 0.12), (-1, 0, 0),
                                      np.linspace(0, 0.75, 12), 0.09 * np.sin(np.linspace(0.05, math.pi - 0.05, 12)) ** 0.6 + 0.0)

    # wing: the sized section (wing_sections.contour), pitched nose-up by the incidence about the quarter-chord, qc line
    # swept and dihedralled; split at the root for the dihedral kink
    xs_, zs_ = wsec.contour(w["airfoil"], 40)
    xw, zw = wsec.to_wing(xs_, zs_, c, w.get("incidence_deg", 0.0))
    for side, nm in ((1, "wing_L"), (-1, "wing_R")):
        rings = [np.c_[xw + ay * tsw, np.full_like(xw, side * ay), zw + ay * tdi] for ay in (0.0, b / 2)]
        S[nm] = loft(rings)

    # pods (fixed) and rotor heads (tilting)
    arm = p["nacelle"]["head_arm_m"]; dp = p["nacelle"]["pod_diameter_m"]
    for side, nm in ((1, "L"), (-1, "R")):
        tipz = b / 2 * tdi
        x_aft = b / 2 * tsw - 0.75 * c - 0.10
        piv = np.array([L["x_front_hub"], side * L["y_front_hub"], tipz])
        start = np.array([x_aft, side * L["y_front_hub"], tipz])
        lpod = piv[0] - x_aft
        s_ = np.linspace(0, lpod, 14)
        r_ = dp / 2 * np.minimum(1, np.minimum(s_ / 0.15 + 0.3, (lpod - s_) / 0.10 + 0.6))
        S[f"pod_{nm}"] = surface_of_revolution(start, (1, 0, 0), s_, r_)
        # stub joining the pod to the wing tip
        xs_le = b / 2 * tsw - c * ((p["wing"]["spar_front_xc"] + p["wing"]["spar_rear_xc"]) / 2 - 0.25) + 0.175 * c
        S[f"pod_stub_{nm}"] = lifting_surface("0021", np.array([xs_le, side * b / 2, tipz]),
                                              np.array([xs_le, side * L["y_front_hub"], tipz]), c * 0.35, c * 0.35)
        ax = np.array([0, 0, 1.0]) if mode == "hover" else np.array([1.0, 0, 0])
        s_ = np.linspace(0, arm, 12)
        r_ = 0.5 * dp * np.where(s_ < arm * 0.75, 1.0, np.sqrt(np.clip(1 - ((s_ - arm * 0.75) / (arm * 0.27)) ** 2, 0.02, 1)))
        S[f"head_{nm}"] = surface_of_revolution(piv - 0.05 * ax, ax, s_, r_)
        # inboard head: pylon from the spar box forward to the pivot ahead of the leading edge
        dy_ = p["nacelle"]["pylon_diameter_m"]
        yi = side * L["y_inboard_hub"]; zi = L["y_inboard_hub"] * tdi
        x_sp = L["y_inboard_hub"] * tsw - c * ((p["wing"]["spar_front_xc"] + p["wing"]["spar_rear_xc"]) / 2 - 0.25)
        lpy = L["x_inboard_hub"] - x_sp
        s_ = np.linspace(0, lpy, 12)
        r_ = dy_ / 2 * np.minimum(1, (lpy - s_) / 0.10 + 0.7)
        S[f"pylon_{nm}"] = surface_of_revolution((x_sp, yi, zi), (1, 0, 0), s_, r_)
        piv_i = np.array([L["x_inboard_hub"], yi, zi])
        s_ = np.linspace(0, arm, 12)
        r_ = 0.5 * dy_ * np.where(s_ < arm * 0.75, 1.0, np.sqrt(np.clip(1 - ((s_ - arm * 0.75) / (arm * 0.27)) ** 2, 0.02, 1)))
        S[f"head_in_{nm}"] = surface_of_revolution(piv_i - 0.05 * ax, ax, s_, r_)

    # tail boom, pylon, H-tail with twin fins at its tips (V-22 H-tail)
    z_b = z_top - 0.10
    x_ht = st["x_ht_ac"]; c_h, b_h = st["c_h"], st["b_h"]
    x_end = x_ht - 0.75 * c_h
    s_ = np.linspace(0, x1 + 0.3 - x_end, 16)
    S["boom"] = surface_of_revolution((x1 + 0.3, 0, z_b), (-1, 0, 0), s_, d["boom"]["D"] / 2 * np.minimum(1, (s_[-1] - s_) / 0.05 + 0.5))
    hp = p["tail"]["pylon_height_m"]; yt = L["y_tail_hub"]
    S["tail_crossbeam"] = lifting_surface("0030", np.array([L["x_tail_hub"] + 0.05, -yt, z_b]), np.array([L["x_tail_hub"] + 0.05, yt, z_b]), 0.12, 0.12)
    for side, nm in ((1, "L"), (-1, "R")):
        S[f"tail_pylon_{nm}"] = fin("0018", (L["x_tail_hub"] + 0.10, side * yt, z_b), hp - 0.05, 0.24, 0.16)
        S[f"tail_head_{nm}"] = surface_of_revolution((L["x_tail_hub"], side * yt, z_b + hp - 0.12), (0, 0, 1), np.linspace(0, 0.14, 8), np.full(8, 0.07))
    le = x_ht + 0.25 * c_h
    for side, nm in ((1, "htail_L"), (-1, "htail_R")):
        S[nm] = lifting_surface("0012", np.array([le, 0, z_b]), np.array([le, side * b_h / 2, z_b]), c_h, c_h)
    hv = math.sqrt(st["S_v_total"] / 2 * 1.5)                       # each fin: AR 1.5 (height^2 / area)
    cv = st["S_v_total"] / 2 / hv
    for side, nm in ((1, "fin_L"), (-1, "fin_R")):
        S[nm] = fin("0012", (le + 0.1 * c_h, side * b_h / 2, z_b - 0.35 * hv), hv, cv * 1.15, cv * 0.85)

    # gear (struts + wheels), figure and STL
    zg = z_top - H - d["gear"]["clearance"] - 0.02
    x_nl = fu["x_nose"] + d["gear"]["nose_dx_from_nose"]
    for nm, (x, y) in {"gear_nose": (x_nl, 0), "gear_L": (x_ml, d["gear"]["main_track"] / 2), "gear_R": (x_ml, -d["gear"]["main_track"] / 2)}.items():
        top = np.array([x, y * 0.6, z_top - H + 0.05]); bot = np.array([x, y, zg + 0.075])
        v_ = bot - top
        S[nm] = surface_of_revolution(top, v_, np.linspace(0, np.linalg.norm(v_), 4), np.full(4, d["gear"]["D"] / 2), n=12)
        S[nm + "_wheel"] = surface_of_revolution(np.array([x, y - 0.03, zg + 0.075]), (0, 1, 0), np.linspace(0, 0.06, 4), np.full(4, 0.075), n=20)

    # rotor disks (separate)
    disks = {}
    tz, iz = b / 2 * tdi, L["y_inboard_hub"] * tdi
    for nm, piv in (("disk_tip_L", (L["x_front_hub"], L["y_front_hub"], tz)), ("disk_tip_R", (L["x_front_hub"], -L["y_front_hub"], tz)),
                    ("disk_in_L", (L["x_inboard_hub"], L["y_inboard_hub"], iz)), ("disk_in_R", (L["x_inboard_hub"], -L["y_inboard_hub"], iz)),
                    ("disk_tail_L", (L["x_tail_hub"], yt, z_b + hp)), ("disk_tail_R", (L["x_tail_hub"], -yt, z_b + hp))):
        tail = nm.startswith("disk_tail")
        ax = np.array((0, 0, 1.0) if (mode == "hover" or tail) else (1.0, 0, 0))
        disks[nm] = (np.array(piv, float) + (0 if tail else arm) * ax, ax)
    geo = {"z_ground": zg, "overall_length": max(fu["x_nose"], L["x_inboard_hub"] + R) - x_end, "overall_width": 2 * (L["y_front_hub"] + R),
           "height_hover": (b / 2 * tdi + arm) - zg, "tail_disk_ground_clear": (z_b + hp) - zg}
    return S, disks, geo, R


def disk_tris(hub, ax, R, n=48):
    ax = ax / np.linalg.norm(ax)
    ref = np.array([1.0, 0, 0]) if abs(ax[0]) < 0.9 else np.array([0, 0, 1.0])
    e1 = np.cross(ax, ref); e1 /= np.linalg.norm(e1); e2 = np.cross(ax, e1)
    th = np.linspace(0, 2 * math.pi, n + 1)
    pts = [hub + R * (math.cos(t) * e1 + math.sin(t) * e2) for t in th]
    return np.array([(hub, pts[i], pts[i + 1]) for i in range(n)])


COL = {"pylon": "#7d8590", "fuselage": "#9aa3ad", "wing": "#c8ccd1", "pod": "#7d8590", "head": "#3b4048", "boom": "#9aa3ad", "htail": "#c8ccd1", "fin": "#b5bac0",
       "gear": "#2a2d31", "sponson": "#8a939d", "tail": "#3b4048"}


LIGHT = np.array([-0.4, -0.5, 0.77]) / np.linalg.norm([-0.4, -0.5, 0.77])


def colour(nm):
    for k, v in COL.items():
        if nm.startswith(k): return v
    return "#aaaaaa"


def draw(ax, S, disks, R, elev, azim, title, show_disks=True):
    for nm, T in S.items():
        n_ = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
        n_ /= np.maximum(np.linalg.norm(n_, axis=1, keepdims=True), 1e-12)
        lam = 0.45 + 0.55 * np.abs(n_ @ LIGHT)                      # two-sided Lambert shading
        base = np.array(matplotlib.colors.to_rgb(colour(nm)))
        ax.add_collection3d(Poly3DCollection(T, facecolors=np.clip(lam[:, None] * base, 0, 1), edgecolors="none", linewidths=0))
    if show_disks:
        for nm, (hub, a_) in disks.items():
            ax.add_collection3d(Poly3DCollection(disk_tris(hub, a_, R), facecolor="#2a78d6", edgecolor="none", alpha=0.18))
    allp = np.concatenate([T.reshape(-1, 3) for T in S.values()] + [disk_tris(h, a_, R).reshape(-1, 3) for h, a_ in disks.values()])
    lo, hi = allp.min(axis=0), allp.max(axis=0); cen = (lo + hi) / 2; span = 0.36 * (hi - lo).max()
    ax.set_xlim(cen[0] - span, cen[0] + span); ax.set_ylim(cen[1] - span, cen[1] + span); ax.set_zlim(cen[2] - span, cen[2] + span)
    ax.set_box_aspect((1, 1, 1)); ax.view_init(elev=elev, azim=azim); ax.set_axis_off(); ax.set_title(title, fontsize=10)


def draw2d(ax, S, disks, R, view, title):
    """Orthographic projection drawn back to front (painter's algorithm), shaded like the 3-D view."""
    from matplotlib.collections import PolyCollection
    i, j, k, sgn = {"plan": (0, 1, 2, 1), "side": (0, 2, 1, -1), "front": (1, 2, 0, 1)}[view]
    polys, cols, depth = [], [], []
    for nm, T in S.items():
        n_ = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]); n_ /= np.maximum(np.linalg.norm(n_, axis=1, keepdims=True), 1e-12)
        lam = 0.45 + 0.55 * np.abs(n_ @ LIGHT)
        base = np.array(matplotlib.colors.to_rgb(colour(nm)))
        polys += list(T[:, :, [i, j]]); cols += list(np.clip(lam[:, None] * base, 0, 1)); depth += list(sgn * T[:, :, k].mean(axis=1))
    o = np.argsort(depth)
    ax.add_collection(PolyCollection([polys[q] for q in o], facecolors=[cols[q] for q in o], edgecolors="none"))
    for nm, (hub, a_) in disks.items():
        D_ = disk_tris(hub, a_, R)
        ax.add_collection(PolyCollection(list(D_[:, :, [i, j]]), facecolors="#2a78d6", edgecolors="none", alpha=0.15))
    allp = np.concatenate([T.reshape(-1, 3) for T in S.values()] + [disk_tris(h, a_, R).reshape(-1, 3) for h, a_ in disks.values()])
    ax.set_xlim(allp[:, i].min() - 0.1, allp[:, i].max() + 0.1); ax.set_ylim(allp[:, j].min() - 0.1, allp[:, j].max() + 0.1)
    ax.set_aspect("equal"); ax.set_title(title, fontsize=10)
    ax.set_xlabel({0: "x [m] (forward)", 1: "y [m] (left)"}[i], fontsize=8); ax.set_ylabel({1: "y [m]", 2: "z [m]"}[j], fontsize=8)
    ax.tick_params(labelsize=7); ax.grid(alpha=0.25)
    if view == "front": ax.invert_xaxis()


def main():
    out = {}
    for mode in ("hover", "airplane"):
        S, disks, geo, R = build(mode)
        write_stl(os.path.join(GEO, f"airframe_{mode}.stl"), S)
        if mode == "hover":
            write_stl(os.path.join(GEO, "rotor_disks_hover.stl"), {k: disk_tris(h, a_, R) for k, (h, a_) in disks.items()})
        out[mode] = geo
        fig = plt.figure(figsize=(10, 7.5)); ax = fig.add_axes([0, 0, 1, 0.95], projection="3d")
        draw(ax, S, disks, R, 22, -135 if mode == "hover" else -140, f"{'Helicopter mode (six rotor disks shaded)' if mode == 'hover' else 'Airplane mode (four heads tilted, aft rotors stopped)'}", show_disks=True)
        fig.savefig(os.path.join(RESULTS, f"fig_iso_{mode}.png"), dpi=150); plt.close(fig)
        if mode == "hover":
            fig = plt.figure(figsize=(11, 10))
            gs = fig.add_gridspec(2, 2, height_ratios=[1.55, 1])
            draw2d(fig.add_subplot(gs[0, :]), S, disks, R, "plan", "Plan (helicopter mode; rotor disks shaded)")
            draw2d(fig.add_subplot(gs[1, 0]), S, disks, R, "side", "Side")
            draw2d(fig.add_subplot(gs[1, 1]), S, disks, R, "front", "Front")
            fig.tight_layout(); fig.savefig(os.path.join(RESULTS, "fig_3view.png"), dpi=150); plt.close(fig)
    sz = jload(os.path.join(RESULTS, "sizing.json"))
    xs, zs = wsec.contour(sz["wing"]["airfoil"], 100)
    with open(os.path.join(GEO, "wing_section.dat"), "w") as f:
        f.write(f"{wsec.LABEL.get(sz['wing']['airfoil'], 'NACA ' + sz['wing']['airfoil'])}\n")
        for x, z in zip(xs, zs): f.write(f"{x:.6f} {z:.6f}\n")
    with open(os.path.join(RESULTS, "geometry.json"), "w") as f: json.dump(out, f, indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()

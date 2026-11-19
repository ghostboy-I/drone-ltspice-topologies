"""Fuselage shell finite-element model (CalculiX) of the Osprey tilt-tricopter.

    python3 src/fuselage_shell.py            build, run (static, five load cases), post -> results/
    python3 src/fuselage_shell.py --build    write the .inp files only
    python3 src/fuselage_shell.py --post     post-process existing results only

Why. The frame screen (tiltframe.py) models the fuselage as ONE beam, the keel box, and treats the skin as a
non-structural fairing (one woven ply). Three things a beam cannot answer:
  1. A skin bonded to the keel and frames carries load whether it was meant to or not. How much, and does that one ply
     survive the strain it picks up, or buckle?
  2. Load introduction: the wing attaches at two frames, the boom at the tail-cone end, the gear at the keel. Strain
     concentrates there.
  3. The tail cone. Behind the cabin the outer mould line ramps up to the boom, and the keel must follow it.

Model (x forward, y left, z up; the same axes and origin as tiltframe.py):
  * Outer mould line: geometry.fuselage_station (the same function the STL uses), super-ellipse sections.
  * Skin: 8-node shells (S8R), structured, one woven ply at 0/90 (params of Airframe/01).
  * Keel box: two sandwich webs at y = +-w/2 standing on the belly skin, a sandwich floor on top; between the webs the
    belly skin is replaced by the keel's bottom flange. Section from the selected design (designs/selected.json). The
    keel follows the belly line, so in the nose and the tail ramp it stays inside the mould line. Its half-width is
    capped at 75 % of the local half-width and its depth at 60 % of the local height (both bind only in the tail cone).
  * Frames: flat carbon rings standing inward from the skin (one row of S8R shells in the frame plane) at the keel
    ends, the nose gear, the two wing-attach stations (front and rear spar), the main gear, the tail end and in between
    at <= 0.30 m spacing. ASSUMED section: 4 mm thick, 40 mm deep (less where the section is tight: <= 35 % of the
    smaller half-axis), quasi-isotropic carbon. The frames are not in the beam screen. (First try: B32R beam rings.
    CalculiX expands beams into bricks, and at the tight corners of the tail end those folded over: negative Jacobians.)
  * Materials: each face homogenised by CLT (materials.Laminate) and written transversely isotropic about the
    fuselage axis x (E2 = E3, G12 = G13), Airframe/01's method. A single rectangular orientation (axis 1 = x) is then
    exact on every facet that contains the x direction, which is all of the model except the nose tip.
  * Fairing: params fuselage.skin. "floating" (user decision, 2026-11-19): the skin rides on compliant mounts and is left
    out of the stiffness; keel, floor and frames carry everything, as the beam screen assumes. "bonded": the skin is
    shared with the frames and keel (results/fuselage_shell_bonded.json: it buckled at 0.01-0.15 of ultimate).
  * Support: the wing bolts to the top of the two wing-attach frames. Those nodes are fixed. Everything else is loaded.
  * Fittings (params fuselage.fittings, sized by hand in fittings.py -> results/fittings.json):
      - wing carry-through: the two wing frames are heavy frames (their own thickness and depth), and the support is
        four bolted lugs instead of the crown arc: the lug is one pinned node (translations) on the
        frame's mid-depth line: a pin, as the bolt is. Reactions are printed per lug (check H1 against the hand split).
      - boom socket: the frames at the two collar stations become sandwich bulkheads (EBULK, BULK_W45 +-45 plies per face) with a
        hole for the boom. The boom load reaches them as the collar forces of socket_split (aft collar radial
        only, forward collar radial + axial + torsion), spread over the hole edge. The bulkhead shares the perimeter
        nodes along the belly; a real bulkhead is also bonded to the webs and floor,
        so bulkhead nodes within TIE_TOL of a keel web or floor node are merged with it (a shared, bonded line). Off: the earlier model (tail loads smeared over the last 3 cm of keel,
        crown arc clamped), kept as results/*_nofit.*.

Loads. For every load case the beam model is solved with inertia relief (tiltframe.run). The fuselage free body is
everything connected to the keel once the wing carry-through link is cut: keel, payload, battery, avionics, gear, the
tail boom and the tail rotor. On each of those beam nodes the load is
    L = F_ext + M Phi (g - a)          (applied forces, gravity, minus the rigid-body inertia, from the same solve)
which is exactly what the beam model applies to its own keel. Each load is moved onto a patch of shell nodes as the
least-norm set of nodal forces with the same resultant force and moment (a distributing coupling, done in Python so
it can be checked). The wing reactions in CalculiX must then equal minus the sum of the applied loads (check F1).
All loads are ULTIMATE (x 1.5). The beam model's keel mass includes the fairing mass, so the shell's own weight is
not added again.

Checks:
  * strain: max principal strain in every face layer (core layers excluded) against eps_allow (Airframe/01, CAI/OHC)
  * core shear stress against the ROHACELL 51 shear strength
  * skin buckling, by hand formulas on the FE membrane loads of every skin element (not *BUCKLE, see below):
        axial  N_cr = max( k 2 sqrt(D11 A22') / R ,  pi^2 D11 / L^2 )      curved panel (SP-8007, k = shell_knockdown)
                                                                           or wide column between frames
        shear  N_cr = max( 0.67 x 0.747 E t (t/R)^(5/4) (R/L)^(1/2) ,  5.35 pi^2 D / L^2 )
        R: local hoop radius of the skin, L: frame bay; interaction R_c + R_s^2 = 1 (as tiltframe.margins)
    Why not CalculiX *BUCKLE: it expands each shell into a brick layer, and a 0.218 mm ply on 25 mm elements is too
    thin for that. It returned factors of 0.995-1.003 for every case, unchanged when the loads were scaled by 10 and
    for an isotropic skin-only model; the same model with a 3 mm skin gave 68. Load-independent ~1.0 is the symptom.
  * hand checks: F1 equilibrium (exact); F2 the crown and keel-floor strain at a tail-cone station against
    engineering beam theory eps = N/EA + M (z - z_na)/EI of the shell's own cross-section.
"""
import json, math, os, re, subprocess, sys, time
import numpy as np
from tiltcfg import ROOT, RESULTS, params, af01_params, jload, G0
import tiltframe as tf
import materials as mat
from geometry import fuselage_station, SUPER_N

FEA = os.path.join(ROOT, "fea", "fuselage")
FRAME_SEC = (0.004, 0.040)          # m, ASSUMED frame ring section (thickness along x, depth inward)
FRAME_MAX_GAP = 0.30                # m, ASSUMED maximum frame spacing
DX = 0.025                          # m, element length along x
NB, NR, NV = 8, 72, 6               # elements: belly between the keel webs, rest of the perimeter, keel web height
S0 = 0.03                           # the mesh starts 3 % of the length behind the nose tip (an open 0.28 m hole)
UF = 1.5
STRAIN_SETS = ("ESKIN", "EFLANGE", "EWEB", "EFLOOR", "EFRAME", "EFRAMEF", "EFRAMER", "EBULK", "EWEBD", "EFLOORD", "EFLANGED")
CORE_SETS = ("EWEB", "EFLOOR", "EFLANGE", "EBULK", "EWEBD", "EFLOORD", "EFLANGED")
DBL_W45 = 2                         # +-45 woven plies added per face on the keel next to each fitting frame (socket
                                    # bulkheads and wing frames): a bonded-joint doubler. Without it the socket junction ran
                                    # 4,300-5,100 ue with the bulkhead tied in, and the keel beside the wing frames 3,200 ue
BULK_W45 = 5                        # +-45 woven plies per bulkhead face (1, the keel web lay-up, failed the ligament above
                                    # the boom hole at 4,400 ue; see fittings check H3)
TIE_TOL = 0.006                     # m, bulkhead-to-keel node merge distance (well under the ~10-18 mm element size)
NBR = 10                            # element rows across a bulkhead, perimeter to hole


# ------------------------------------------------------------------ geometry and mesh ---------------------------------
def ring(s, fu, z_top, nfr, nt, kd):
    """Perimeter at station s: 2*(NB+NR) points (S8R corner + midside), index 0 = left keel point, 2*NB = right."""
    x, hw, hh, zc = fuselage_station(s, fu, z_top, nfr, nt)
    wk = min(kd["width"] / 2, 0.75 * hw)
    a = math.acos((wk / hw) ** (SUPER_N / 2))
    t1, t2 = -a, -math.pi + a                                    # right / left keel points on the belly
    pt = lambda t: np.c_[hw * np.sign(np.cos(t)) * np.abs(np.cos(t)) ** (2 / SUPER_N),
                         zc + hh * np.sign(np.sin(t)) * np.abs(np.sin(t)) ** (2 / SUPER_N)]

    def resample(ta, tb, n):                                     # 2n+1 points equally spaced in arc length
        t = np.linspace(ta, tb, 4000); P = pt(t)
        sl = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
        ts = np.interp(np.linspace(0, sl[-1], 2 * n + 1), sl, t)
        return pt(ts)
    bot = resample(t2, t1, NB); rest = resample(t1, t2 + 2 * math.pi, NR)
    P = np.vstack([bot, rest[1:-1]])
    dk = min(kd["depth"], 0.6 * 2 * hh)
    return x, P, dict(hw=hw, hh=hh, zc=zc, wk=wk, dk=dk)


def stations(ctx, d, fu, x_pay):
    sz = ctx["sz"]; L = sz["layout"]; c = sz["wing"]["c"]; pw = ctx["p"]["wing"]
    x_f, x_r = c * (0.25 - pw["spar_front_xc"]), -c * (pw["spar_rear_xc"] - 0.25)
    x_ka = fu["x_nose"] - 0.10                                   # keel front end (tiltframe: x_nose - 0.10)
    x_nl = fu["x_nose"] + d["gear"]["nose_dx_from_nose"]
    x_ml = L["x_cg_hover"] + d["gear"]["main_dx"]
    x_end = fu["x_tail"]
    frames = sorted({round(v, 6) for v in (x_ka, x_nl, x_f, x_r, x_ml, x_end)}, reverse=True)
    full = [frames[0]]
    for a_, b_ in zip(frames[:-1], frames[1:]):                  # extra frames so no bay exceeds FRAME_MAX_GAP
        n = int(math.ceil((a_ - b_) / FRAME_MAX_GAP - 1e-9))
        full += list(np.linspace(a_, b_, n + 1)[1:])
    x0 = fu["x_nose"] - S0 * fu["L"]
    keys = [x0] + full
    xs = [x0]
    for a_, b_ in zip(keys[:-1], keys[1:]):
        n = max(1, int(math.ceil((a_ - b_) / DX)))
        xs += list(np.linspace(a_, b_, n + 1)[1:])
    return np.array(xs), dict(x_f=x_f, x_r=x_r, x_ka=x_ka, x_nl=x_nl, x_ml=x_ml, x_end=x_end, frames=full, x_pay=x_pay)


class Mesh:
    def __init__(self):
        self.X = []; self.idx = {}; self.el = {}; self.tag = {}

    def node(self, key, xyz):
        if key not in self.idx:
            self.idx[key] = len(self.X) + 1; self.X.append(np.asarray(xyz, float))
        return self.idx[key]

    def elem(self, eset, nodes, kind="S8R"):
        self.el.setdefault(eset, []).append((kind, nodes))


def build_mesh(ctx, d, x_pay):
    sz = ctx["sz"]; fu = sz["fuselage"]; w = sz["wing"]; p = ctx["p"]
    z_top = -(w["c"] * w["tc"] / 2)
    nfr, nt = p["fuselage"]["nose_frac"], p["fuselage"]["tail_frac"]
    xc, st = stations(ctx, d, fu, x_pay)
    # corner rings at xc, midside rings halfway
    xa = np.empty(2 * len(xc) - 1); xa[0::2] = xc; xa[1::2] = (xc[:-1] + xc[1:]) / 2
    s_of = lambda x: (fu["x_nose"] - x) / fu["L"]
    rings = [ring(s_of(x), fu, z_top, nfr, nt, d["keel"]) for x in xa]
    np_ = 2 * (NB + NR)
    me = Mesh(); me.rings = rings; me.xa = xa; me.st = st; me.np = np_
    me.skip = {"ESKIN"} if ctx["p"]["fuselage"].get("skin", "bonded") == "floating" else set()
    # Junctions (web on skin, floor on web, frame on skin) SHARE nodes: CalculiX joins them with a rigid "knot", i.e. a
    # bonded, moment-carrying joint. (Tried: separate nodes tied by *EQUATION, translations only. That pins every
    # corner of the keel box, which then shears like a parallelogram held only by the frames: LC4 web strain went from
    # 3,000 to 21,600 ue, and CalculiX drops loads and reactions on dependent nodes. It did not cure *BUCKLE either.)
    me.ties = []
    def share(key, master, xyz):
        me.idx[key] = me.idx[master]
    in_keel = lambda x: st["x_end"] - 1e-9 <= x <= st["x_ka"] + 1e-9
    corner = lambda a, b: (a % 2 == 0) or (b % 2 == 0)           # S8R: skip the (odd, odd) centre points
    FIT = ctx.get("fit")
    bulk_x = {} if not FIT else {min(st["frames"], key=lambda f_: abs(f_ - xs)): tag for xs, tag in
                                 ((FIT["socket"]["x_fwd"], "fwd"), (FIT["socket"]["x_aft"], "aft"))}
    jw = [st["x_f"], st["x_r"]] if FIT else []                  # keel junctions: socket bulkheads (web, floor, flange)
    near = lambda a, xs_, n_=1: any(abs(0.5 * (xa[a] + xa[a + 2]) - xb) < (n_ + 0.05) * DX for xb in xs_)   # and wing frames (web only)
    # (flange doublers at the wing frames: CalculiX 2.21 returned NaN stiffness wherever a thicker flange met a wing frame
    #  on the belly, plain or one-layer-composite frame section alike; the same doubler beside a bulkhead runs. Web and
    #  floor doublers, which do not share the frame's belly nodes, run.)
    # carry-through bay: the one-wheel landing (LC4) roll torque runs through the keel between the wing frames, so the web
    # and floor doublers cover the whole bay, x_r - 2 DX to x_f + 2 DX
    bay = lambda a: bool(jw) and min(jw) - 2.05 * DX < 0.5 * (xa[a] + xa[a + 2]) < max(jw) + 2.05 * DX
    dbl = lambda a, web=False: "D" if near(a, list(bulk_x), 2) or (web and bay(a)) else ""
    for a, (x, P, g) in enumerate(rings):
        for b in range(np_):
            if corner(a, b): me.node(("s", a, b), (x, P[b, 0], P[b, 1]))
        if in_keel(x):
            for side, b0 in (("L", 0), ("R", 2 * NB)):           # webs: 2*NV+1 points from the skin up
                y0, z0 = P[b0]
                share(("w", side, a, 0), ("s", a, b0), None)
                for v in range(1, 2 * NV + 1):
                    if corner(a, v): me.node(("w", side, a, v), (x, y0, z0 + g["dk"] * v / (2 * NV)))
            zf = P[0, 1] + g["dk"]
            share(("f", a, 0), ("w", "L", a, 2 * NV), None); share(("f", a, 2 * NB), ("w", "R", a, 2 * NV), None)
            for f in range(1, 2 * NB):
                if corner(a, f): me.node(("f", a, f), (x, P[0, 0] + (P[2 * NB, 0] - P[0, 0]) * f / (2 * NB), zf))
    web = lambda side, a, v: me.idx[("w", side, a, v)]
    flo = lambda a, f: me.idx[("f", a, f)]
    q8 = lambda g_: [g_(0, 0), g_(2, 0), g_(2, 2), g_(0, 2), g_(1, 0), g_(2, 1), g_(1, 2), g_(0, 1)]
    for a in range(0, len(xa) - 2, 2):
        for b in range(0, np_, 2):
            eset = "EFLANGE" + dbl(a) if (b < 2 * NB and in_keel(xa[a]) and in_keel(xa[a + 2])) else "ESKIN"
            me.elem(eset, q8(lambda i, j: me.idx[("s", a + i, (b + j) % np_)]))
        if in_keel(xa[a]) and in_keel(xa[a + 2]):
            for side in ("L", "R"):
                for v in range(0, 2 * NV, 2):
                    me.elem("EWEB" + dbl(a, web=True), q8(lambda i, j: web(side, a + i, v + j)))
            for f in range(0, 2 * NB, 2):
                me.elem("EFLOOR" + dbl(a, web=True), q8(lambda i, j: flo(a + i, f + j)))
    # frames: one row of shells from the skin ring inward, in the frame plane
    me.frame_rings = []; me.collars = {}; me.frame_set = {}
    heavy = {} if not FIT else {round(st["x_f"], 6): FIT["wing_frames"]["front"], round(st["x_r"], 6): FIT["wing_frames"]["rear"]}
    for xf in st["frames"]:
        a = int(np.argmin(abs(xa - xf))); assert a % 2 == 0 and abs(xa[a] - xf) < 1e-6
        me.frame_rings.append(a)
        x, P, g = rings[a]
        if xf in bulk_x:                                         # sandwich bulkhead with the boom hole
            zb, rh = FIT["z_boom"], FIT["socket"]["boom_D_m"] / 2 + 0.008
            for b in range(np_):
                ph = math.atan2(P[b, 1] - zb, P[b, 0]); C = np.array([rh * math.cos(ph), zb + rh * math.sin(ph)])
                for k_ in range(1, 2 * NBR + 1):
                    if b % 2 == 0 or k_ % 2 == 0:
                        q = P[b] + (C - P[b]) * k_ / (2 * NBR)
                        me.node(("bk", a, b, k_), (x, q[0], q[1]))
                share(("bk", a, b, 0), ("s", a, b), None)
            # bonded to the keel webs and floor: an interior bulkhead node within TIE_TOL of a web or floor node in this
            # plane BECOMES that node (shared, a bonded line). First version tied the nearest node within 20 mm by
            # *EQUATION (translations): offset ties pass the force but not its couple F x d, and the cabin-cut statics
            # check F2 then lost 15 % of the pitch and 90 % of the yaw moment.
            me.n_merged = getattr(me, "n_merged", 0)
            if in_keel(x):
                keel_pts = [me.idx[("w", sd, a, v)] for sd in ("L", "R") for v in range(1, 2 * NV + 1)] + \
                           [me.idx[("f", a, f_)] for f_ in range(1, 2 * NB)]
                cand = {(b, k_): me.X[me.idx[("bk", a, b, k_)] - 1][1:] for b in range(np_) for k_ in range(1, 2 * NBR)
                        if ("bk", a, b, k_) in me.idx}
                for km in keel_pts:
                    yz = me.X[km - 1][1:]
                    dist, key_ = min((np.linalg.norm(v_ - yz), kk) for kk, v_ in cand.items())
                    if dist <= TIE_TOL:
                        me.idx[("bk", a) + key_] = km; cand.pop(key_); me.n_merged += 1
            bn = lambda b_, k_: me.idx[("bk", a, b_ % np_, k_)]
            for b in range(0, np_, 2):
                for k_ in range(0, 2 * NBR, 2):
                    me.elem("EBULK", [bn(b, k_), bn(b + 2, k_), bn(b + 2, k_ + 2), bn(b, k_ + 2),
                                      bn(b + 1, k_), bn(b + 2, k_ + 1), bn(b + 1, k_ + 2), bn(b, k_ + 1)])
            me.collars[bulk_x[xf]] = dict(x=x, ids=[bn(b, 2 * NBR) for b in range(np_)], centre=np.array([x, 0.0, zb]))
            continue
        hv = heavy.get(round(xf, 6))
        fset = "EFRAME" if hv is None else ("EFRAMEF" if abs(xf - st["x_f"]) < 1e-6 else "EFRAMER")
        me.frame_set[fset] = FRAME_SEC[0] if hv is None else hv["t_m"]
        depth = min(FRAME_SEC[1] if hv is None else hv["d_m"], 0.35 * min(g["hw"], g["hh"]))
        for b in range(np_):
            tng = P[(b + 1) % np_] - P[b - 1]
            nrm = np.array([-tng[1], tng[0]]); nrm /= np.linalg.norm(nrm)
            if nrm @ (np.array([0.0, g["zc"]]) - P[b]) < 0: nrm = -nrm          # point inward
            if ("s", a, b) in me.idx: share(("fr", a, b, 0), ("s", a, b), None)
            for k_ in (1, 2):
                if k_ == 2 or b % 2 == 0:
                    q = P[b] + nrm * depth * k_ / 2
                    me.node(("fr", a, b, k_), (x, q[0], q[1]))
        fn = lambda a_, b_, k_: me.idx[("fr", a_, b_ % np_, k_)]
        for b in range(0, np_, 2):
            me.elem(fset, [fn(a, b, 0), fn(a, b + 2, 0), fn(a, b + 2, 2), fn(a, b, 2),
                               fn(a, b + 1, 0), fn(a, b + 2, 1), fn(a, b + 1, 2), fn(a, b, 1)])
    return me


# ------------------------------------------------------------------ sections ------------------------------------------
def face_material(lam_face):
    """Transversely isotropic about x from the face's CLT membrane constants (Airframe/01 ccx_verify.face_props)."""
    Ex, Ey, G, nu = lam_face.Ex, lam_face.Ey, lam_face.Gxy, min(lam_face.nuxy, 0.45)
    return dict(E1=Ex, E2=Ey, E3=Ey, nu12=nu, nu13=nu, nu23=0.3, G12=G, G13=G, G23=Ey / 2.6)


def sections(ctx, d):
    pm = ctx["pm"]; wv = pm["materials"]["woven"]; foam = pm["materials"]["foam"]
    k = d["keel"]; ct = k["core_mm"] * 1e-3
    skin = mat.Laminate([(wv, 0.0)] * pm["fuselage"]["skin_plies_woven"])
    web = mat.wall(pm, n_w45=k["n_w45"], core_t=ct)
    fl = mat.wall(pm, n_ud0=k["n_ud"], n_w45=k["n_w45"], core_t=ct)
    face = lambda lam: mat.Laminate(lam.plies)
    rho_face = lambda lam: sum(m_["t_ply"] * m_["rho"] for m_, _ in lam.plies) / sum(m_["t_ply"] for m_, _ in lam.plies)
    secs = {
        "ESKIN": dict(layers=[("SKIN", skin.h)], mats={"SKIN": face_material(skin)}, areal=skin.h * rho_face(skin)),
        "EWEB": dict(layers=[("FWEB", face(web).h), ("FOAM", ct), ("FWEB", face(web).h)], mats={"FWEB": face_material(face(web))},
                     areal=2 * face(web).h * rho_face(web) + ct * foam["rho"]),
        "EFLOOR": dict(layers=[("FFLG", face(fl).h), ("FOAM", ct), ("FFLG", face(fl).h)], mats={"FFLG": face_material(face(fl))},
                       areal=2 * face(fl).h * rho_face(fl) + ct * foam["rho"]),
    }
    secs["EFLANGE"] = dict(secs["EFLOOR"])
    # junction doublers: +DBL_W45 +-45 plies per face on the keel web, floor and flange next to each socket bulkhead
    for k_, lam, nm in (("EWEBD", mat.wall(pm, n_w45=k["n_w45"] + DBL_W45, core_t=ct), "FWEBD"),
                        ("EFLOORD", mat.wall(pm, n_ud0=k["n_ud"], n_w45=k["n_w45"] + DBL_W45, core_t=ct), "FFLGD")):
        secs[k_] = dict(layers=[(nm, face(lam).h), ("FOAM", ct), (nm, face(lam).h)], mats={nm: face_material(face(lam))},
                        areal=2 * face(lam).h * rho_face(lam) + ct * foam["rho"])
    secs["EFLANGED"] = dict(secs["EFLOORD"])
    bk = mat.wall(pm, n_w45=BULK_W45, core_t=ct)                 # socket bulkheads: +-45 woven faces, keel core
    secs["EBULK"] = dict(layers=[("FBULK", face(bk).h), ("FOAM", ct), ("FBULK", face(bk).h)], mats={"FBULK": face_material(face(bk))},
                         areal=2 * face(bk).h * rho_face(bk) + ct * foam["rho"])
    secs["_skin_lam"] = skin
    qi = mat.strain_allowable(pm)
    return secs, {"E": qi["Ex_qi"], "nu": 0.3, "rho": pm["materials"]["ud"]["rho"]}, foam, qi["eps_allow"]


# ------------------------------------------------------------------ loads ---------------------------------------------
def free_body(ctx, d):
    """Run the beam model; return its fuselage-side nodes and their ultimate loads (6 per node) for every case."""
    r = tf.run(ctx, d, want_modes=False)
    out = {}
    for name, (mode, F, acc) in r["_loads"].items():
        M, info = r["_models"][mode]
        cut = [i for i, e in enumerate(M.elems) if e["name"] == "carry-through"]
        adj = {}
        for i, e in enumerate(M.elems):
            if i in cut: continue
            adj.setdefault(e["n1"], set()).add((e["n2"], i)); adj.setdefault(e["n2"], set()).add((e["n1"], i))
        keel = {n for e in M.elems if e["group"] == "keel" for n in (e["n1"], e["n2"])}
        seen, todo = set(keel), list(keel)
        while todo:
            n = todo.pop()
            for m_, _ in adj.get(n, ()):
                if m_ not in seen: seen.add(m_); todo.append(m_)
        Phi = M.rigid_modes(M._cg(M.total_mass()))
        g6 = np.r_[0, 0, -G0, 0, 0, 0]
        Lv = F + M.M @ (Phi @ (g6 - acc))
        # which keel node each hanging node belongs to, and through which element group
        owner = {}
        for n in keel: owner[n] = (n, "keel")
        frontier = [(n, n) for n in keel]
        while frontier:
            n, root = frontier.pop()
            for m_, ei in adj.get(n, ()):
                if m_ in owner: continue
                grp = owner[n][1] if owner[n][1] != "keel" else M.elems[ei]["name"]
                owner[m_] = (root, grp); frontier.append((m_, root))
        loads = [dict(node=n, x=M.X[n].copy(), L=UF * Lv[6 * n:6 * n + 6], root=owner[n][0], root_x=M.X[owner[n][0]].copy(),
                      group=owner[n][1]) for n in sorted(seen)]
        wing_side = [n for n in range(len(M.X)) if n not in seen]
        tot = sum(UF * Lv[6 * n:6 * n + 3] for n in seen)
        out[name] = dict(mode=mode, loads=loads, total_F=tot, n_wing_side=len(wing_side))
    return r, out


def patch_forces(Pn, F, Mo, r0):
    """Least-norm nodal forces f_i at points Pn with sum f = F and sum (P - r0) x f = Mo (a distributing coupling)."""
    n = len(Pn); R = Pn - r0
    A = np.zeros((6, 3 * n))
    for i in range(n):
        A[0:3, 3 * i:3 * i + 3] = np.eye(3)
        rx, ry, rz = R[i]
        A[3:6, 3 * i:3 * i + 3] = [[0, -rz, ry], [rz, 0, -rx], [-ry, rx, 0]]
    f = A.T @ np.linalg.lstsq(A @ A.T, np.r_[F, Mo], rcond=None)[0]
    return f.reshape(n, 3)


def socket_split(F, M, rb, x_fwd, x_aft, z_boom):
    """Boom load (F, M about rb) -> aft collar radial force, forward collar force (incl. axial), forward torsion.
    The boom is rigid between the collars; moments about the forward collar: (r_aft - r_fwd) x F_aft = M_perp, with
    r_aft - r_fwd = (-s, 0, 0):  s F_aft,z = M_y  and  -s F_aft,y = M_z."""
    pf = np.array([x_fwd, 0, z_boom]); s = x_fwd - x_aft
    Mf = M + np.cross(rb - pf, F)
    Fa = np.array([0.0, -Mf[2] / s, Mf[1] / s])
    return Fa, F - Fa, Mf[0]


def map_loads(me, case, st):
    """Group the beam loads by where they enter the fuselage and spread each group's resultant over its patch."""
    X = np.array(me.X)
    keel_ids = sorted({n for s_ in ("EWEB", "EFLOOR", "EFLANGE", "EWEBD", "EFLOORD", "EFLANGED") for _, ns in me.el.get(s_, []) for n in ns})
    floor_ids = sorted({n for s_ in ("EFLOOR", "EFLOORD") for _, ns in me.el.get(s_, []) for n in ns})
    groups = {}
    for ld in case["loads"]:
        g = ld["group"]
        if g == "keel": key = ("keel", round(ld["x"][0], 4))
        elif g in ("payload_link", "bat_link"): key = (g, round(ld["x"][0], 4))
        elif g.startswith("gear"): key = ("gear", round(ld["root_x"][0], 4))
        else: key = ("tail", 0.0)                                # tailcone link, boom, tail mast, H-tail
        grp = groups.setdefault(key, {"F": np.zeros(3), "M": np.zeros(3), "pts": []})
        grp["F"] += ld["L"][:3]; grp["M"] += ld["L"][3:] + np.cross(ld["x"], ld["L"][:3])   # moments about the origin
    f = np.zeros_like(X); used = {}
    for (kind, xk), grp in groups.items():
        if kind == "keel":
            ids = [i for i in keel_ids if abs(X[i - 1, 0] - xk) <= DX * 0.51]
            if not ids:                                          # keel beam node in the bit ahead of the mesh start
                ids = [i for i in keel_ids if abs(X[i - 1, 0] - X[np.array(keel_ids) - 1, 0].max()) < 1e-6]
        elif kind == "payload_link":
            ids = [i for i in floor_ids if abs(X[i - 1, 0] - xk) <= 0.11]
        elif kind == "bat_link":
            ids = [i for i in floor_ids if abs(X[i - 1, 0] - xk) <= 0.15]
        elif kind == "gear":
            ids = [i for i in keel_ids if abs(X[i - 1, 0] - xk) <= 0.06]
        elif me.collars:                                         # boom socket: collar forces on the hole edges
            Fa, Ff, Tf = socket_split(grp["F"], grp["M"] - np.cross(me.rb, grp["F"]), me.rb, me.collars["fwd"]["x"], me.collars["aft"]["x"], me.rb[2])
            for tag, Fc, Mc in (("aft", Fa, np.zeros(3)), ("fwd", Ff, np.array([Tf, 0, 0]))):
                cl = me.collars[tag]; ids = cl["ids"]
                fi = patch_forces(X[np.array(ids) - 1], Fc, Mc, cl["centre"])
                for i, v in zip(ids, fi): f[i - 1] += v
                used[f"collar_{tag}"] = dict(n_nodes=len(ids), F=Fc.tolist(), M=Mc.tolist())
            continue
        else:                                                    # boom fitting: keel + end frames
            live = sorted({n for s_, els in me.el.items() if s_ not in me.skip for _, ns in els for n in ns})
            ids = [i for i in live if X[i - 1, 0] <= st["x_end"] + 0.03]
        P = X[np.array(ids) - 1]
        fi = patch_forces(P, grp["F"], grp["M"], np.zeros(3))
        for i, v in zip(ids, fi): f[i - 1] += v
        used[f"{kind} {xk:+.3f}"] = dict(n_nodes=len(ids), F=grp["F"].tolist())
    return f, used


# ------------------------------------------------------------------ CalculiX input ------------------------------------
def write_inp(me, secs, qi, foam, cases_f, fixed, path, buckle_case=None):
    L = ["*HEADING", "Osprey tilt-tricopter fuselage shell model (fuselage_shell.py)", "*NODE"]
    L += [f"{i + 1}, {x[0]:.6f}, {x[1]:.6f}, {x[2]:.6f}" for i, x in enumerate(me.X)]
    eid = 1; me.eid = {}
    for eset, els in me.el.items():
        if eset in me.skip: continue
        kind = els[0][0]
        L.append(f"*ELEMENT, TYPE={kind}, ELSET={eset}")
        for _, ns in els:
            L.append(f"{eid}, " + ", ".join(map(str, ns))); me.eid.setdefault(eset, []).append(eid); eid += 1
    L += ["*NSET, NSET=NFIX"] + [", ".join(map(str, fixed[i:i + 12])) for i in range(0, len(fixed), 12)]
    for k_, ids in enumerate(getattr(me, "lugs", [])):
        L += [f"*NSET, NSET=NLUG{k_ + 1}"] + [", ".join(map(str, ids[i:i + 12])) for i in range(0, len(ids), 12)]
    L += ["*ORIENTATION, NAME=OX, SYSTEM=RECTANGULAR", "1., 0., 0., 0., 1., 0."]
    mats = {}
    for k_, s_ in secs.items():
        if not k_.startswith("_"): mats.update(s_["mats"])
    for nm, m_ in mats.items():
        L += [f"*MATERIAL, NAME={nm}", "*ELASTIC, TYPE=ENGINEERING CONSTANTS",
              f"{m_['E1']:.6g}, {m_['E2']:.6g}, {m_['E3']:.6g}, {m_['nu12']:.4f}, {m_['nu13']:.4f}, {m_['nu23']:.4f}, {m_['G12']:.6g}, {m_['G13']:.6g}",
              f"{m_['G23']:.6g}, 0."]
    L += ["*MATERIAL, NAME=FOAM", "*ELASTIC, TYPE=ENGINEERING CONSTANTS",
          f"{foam['E']:.6g}, {foam['E']:.6g}, {foam['E']:.6g}, 0.3, 0.3, 0.3, {foam['G']:.6g}, {foam['G']:.6g}", f"{foam['G']:.6g}, 0."]
    L += ["*MATERIAL, NAME=FRAMEQI", "*ELASTIC", f"{qi['E']:.6g}, {qi['nu']}"]
    for eset, s_ in secs.items():
        if eset not in me.el or eset.startswith("_") or eset in me.skip: continue
        if len(s_["layers"]) == 1:
            L += [f"*SHELL SECTION, ELSET={eset}, MATERIAL={s_['layers'][0][0]}, ORIENTATION=OX", f"{s_['layers'][0][1]:.6g}"]
        else:
            L += [f"*SHELL SECTION, ELSET={eset}, COMPOSITE"] + [f"{t:.6g},, {m_}, OX" for m_, t in s_["layers"]]
    for fset, t_ in me.frame_set.items():
        L += [f"*SHELL SECTION, ELSET={fset}, MATERIAL=FRAMEQI", f"{t_}"]
    L += ["*EQUATION"]
    for sl, ma in me.ties:
        for dof in (1, 2, 3): L += ["2", f"{sl}, {dof}, 1., {ma}, {dof}, -1."]
    L += ["*BOUNDARY", "NFIX, 1, 3"]
    for name, f in cases_f.items():
        if buckle_case is not None and name != buckle_case: continue
        L += ["*STEP", "*BUCKLE", "4"] if buckle_case is not None else ["*STEP", "*STATIC"]
        L += ["*CLOAD, OP=NEW"]
        for i in np.nonzero(np.abs(f).sum(1) > 1e-9)[0]:
            for dof in range(3):
                if abs(f[i, dof]) > 1e-9: L.append(f"{i + 1}, {dof + 1}, {f[i, dof]:.6e}")
        if buckle_case is None:
            L += ["*NODE PRINT, NSET=NFIX, TOTALS=ONLY", "RF"]
            for k_ in range(len(getattr(me, "lugs", []))): L += [f"*NODE PRINT, NSET=NLUG{k_ + 1}, TOTALS=ONLY", "RF"]
            for eset in STRAIN_SETS:
                if eset in me.skip or eset not in me.el: continue
                L += [f"*EL PRINT, ELSET={eset}", "E"]
            for eset in CORE_SETS:
                if eset in me.el: L += [f"*EL PRINT, ELSET={eset}", "S"]
            L += ["*NODE FILE", "U", "*EL FILE", "E"]
        L += ["*END STEP"]
    if path is not None:                                         # None: only number the elements (post-processing)
        with open(path, "w") as fh: fh.write("\n".join(L) + "\n")


def run_ccx(job):
    env = dict(os.environ, OMP_NUM_THREADS="1", CCX_NPROC_EQUATION_SOLVER="1")
    t0 = time.time()
    r = subprocess.run(["nice", "-n", "19", "ccx", "-i", job], cwd=FEA, env=env, capture_output=True, text=True)
    with open(os.path.join(FEA, job + ".log"), "w") as fh: fh.write(r.stdout + r.stderr)
    if "Job finished" not in r.stdout: raise RuntimeError(f"ccx {job} failed, see fea/fuselage/{job}.log")
    return time.time() - t0


# ------------------------------------------------------------------ post ----------------------------------------------
def read_dat_blocks(path):
    """{(quantity, set, time): array rows} from a CalculiX .dat file."""
    blocks, cur = {}, None
    for ln in open(path):
        m_ = re.match(r"\s*(strains|stresses|total force).*?(?:for set|set)\s+(\S+)\s+and time\s+(\S+)", ln)
        if m_:
            cur = (m_.group(1), m_.group(2), float(m_.group(3))); blocks[cur] = []; continue
        if cur and ln.strip():
            tok = ln.split()
            try: blocks[cur].append([float(v) for v in tok[:8]])   # strain rows end with the orientation name
            except ValueError: cur = None
    return {k: np.array(v) for k, v in blocks.items()}


def element_frames(me):
    """Centroid, unit normal and two tangents (t1 along x where possible) of every shell element, by element id."""
    X = np.array(me.X); out = {}
    for eset, ids in me.eid.items():
        for eid, (_, ns) in zip(ids, me.el[eset]):
            P = X[np.array(ns[:4]) - 1]
            n = np.cross(P[2] - P[0], P[3] - P[1]); n /= np.linalg.norm(n)
            t1 = np.array([1.0, 0, 0]) - n[0] * n
            if np.linalg.norm(t1) < 0.3: t1 = np.cross(n, [0, 0, 1.0])
            t1 /= np.linalg.norm(t1); t2 = np.cross(n, t1)
            out[eid] = (eset, X[np.array(ns) - 1].mean(0), n, t1, t2)
    return out


def inplane(E, t1, t2):
    """In-plane 2x2 part of a symmetric 3x3 tensor in the tangent basis; principal values, (along-x, hoop) components."""
    T = np.array([t1, t2]); A = T @ E @ T.T
    return np.linalg.eigvalsh(A), (A[0, 0], A[1, 1])


def tensor(row):
    xx, yy, zz, xy, xz, yz = row
    return np.array([[xx, xy, xz], [xy, yy, yz], [xz, yz, zz]])


def section_check(me, f, ef, eps_by_el, secs, x_s):
    """Hand check F2: engineering beam theory of the shell cross-section at x_s against the FE axial strain."""
    X = np.array(me.X)
    aft = X[:, 0] < x_s
    # one row of elements: the row whose centroids are nearest x_s (a mid-bay station can fall on a node ring, and a
    # +-DX/2 window then catches two rows and doubles every resultant: the first version of this check did that)
    cx = np.array([v[1][0] for v in ef.values() if v[0] in ("ESKIN", "EFLANGE")])
    x_row = cx[np.argmin(abs(cx - x_s))]
    strip = [(eid, v) for eid, v in ef.items() if v[0] != "EFRAME" and abs(v[1][0] - x_row) < 2e-3]
    x_s = float(x_row)
    # section: each element contributes perimeter length x membrane thickness x E along x
    # membrane stiffness per unit width along x, plane stress: N_x = Q11 t (eps_x + nu21 eps_s)
    def q(mat_, t):
        nu21 = mat_["nu12"] * mat_["E2"] / mat_["E1"]
        return mat_["E1"] * t / (1 - mat_["nu12"] * nu21), nu21
    Et = {"ESKIN": q(secs["ESKIN"]["mats"]["SKIN"], secs["ESKIN"]["layers"][0][1])}       # absent from ef when floating
    for k_, m_ in (("EWEB", "FWEB"), ("EFLOOR", "FFLG"), ("EFLANGE", "FFLG"), ("EWEBD", "FWEBD"), ("EFLOORD", "FFLGD"), ("EFLANGED", "FFLGD")):
        if k_ in secs: Et[k_] = q(secs[k_]["mats"][m_], 2 * secs[k_]["layers"][0][1])
    rows = []
    for eid, (eset, c, n, t1, t2) in strip:
        ns = me.el[eset][me.eid[eset].index(eid)][1]
        P = X[np.array(ns[:4]) - 1]
        ds = 0.5 * (np.linalg.norm(P[3] - P[0]) + np.linalg.norm(P[2] - P[1]))   # edge length across the strip
        rows.append((eid, c[1], c[2], ds * Et[eset][0], Et[eset][1]))
    R = np.array([r_[1:4] for r_ in rows]); w = R[:, 2]; nu21 = np.array([r_[4] for r_ in rows])
    EA = w.sum(); yc = (w * R[:, 0]).sum() / EA; zc = (w * R[:, 1]).sum() / EA
    dy, dz = R[:, 0] - yc, R[:, 1] - zc
    Iyy, Izz, Iyz = (w * dz * dz).sum(), (w * dy * dy).sum(), (w * dy * dz).sum()
    c0 = np.array([x_s, yc, zc])
    Fa = f[aft].sum(0); Ma = np.cross(X[aft] - c0, f[aft]).sum(0)
    N, Sz, Sy = -Fa[0], -Ma[1], Ma[2]                            # int sigma dA, int sigma dz dA, int sigma dy dA
    kz, ky = np.linalg.solve([[Iyy, Iyz], [Iyz, Izz]], [Sz, Sy])
    beam = N / EA + kz * dz + ky * dy
    fe = np.array([eps_by_el[r_[0]][0] for r_ in rows])
    fs_ = np.array([eps_by_el[r_[0]][1] for r_ in rows])
    fe_eff = fe + nu21 * fs_                                     # the axial-stress-equivalent strain
    top = int(np.argmax(R[:, 1])); bot = int(np.argmin(R[:, 1]))
    # statics check, independent of the plane-section assumption: the FE axial stress resultants over the cut must
    # equal the loads aft of it
    N_fe = float((w * fe_eff).sum()); Sz_fe = float((w * fe_eff * dz).sum()); Sy_fe = float((w * fe_eff * dy).sum())
    rel = lambda i: float(fe_eff[i] / beam[i] - 1)
    return {"x_s": x_s, "N": float(N), "M_pitch": float(Sz), "M_yaw": float(Sy), "EA": float(EA), "EI_pitch": float(Iyy), "z_na": float(zc),
            "crown": {"beam": float(beam[top]), "fe": float(fe_eff[top]), "diff": rel(top)},
            "belly": {"beam": float(beam[bot]), "fe": float(fe_eff[bot]), "diff": rel(bot)},
            "rms_diff_of_peak": float(np.sqrt(np.mean((fe_eff - beam) ** 2)) / max(abs(beam).max(), 1e-12)),
            "resultants": {"N_statics": float(N), "N_fe": N_fe, "M_pitch_statics": float(Sz), "M_pitch_fe": Sz_fe,
                           "M_yaw_statics": float(Sy), "M_yaw_fe": Sy_fe}}


def skin_buckling(me, B, t, ef, lam, kd):
    """Hand buckling check of every skin element from its FE membrane loads (see the module docstring)."""
    X = np.array(me.X)
    A = lam.A; D11 = lam.D[0, 0]; a = np.linalg.inv(A); A22p = 1 / a[1, 1]
    th = lam.h; E = math.sqrt(lam.Ex * lam.Ey)
    D = lam.D[0, 0]
    frames = np.array(sorted(me.st["frames"]))
    rows = B[("strains", "ESKIN", t)]
    acc = {}
    for row in rows:
        eid = int(row[0]); _, c, n, t1, t2 = ef[eid]
        T = np.array([t1, t2]); Ein = T @ tensor(row[2:8]) @ T.T
        acc.setdefault(eid, []).append(Ein)
    out = []
    ids = me.eid["ESKIN"]
    for eid, (_, ns) in zip(ids, me.el["ESKIN"]):
        if eid not in acc: continue
        Ein = np.mean(acc[eid], axis=0)
        N = A @ np.array([Ein[0, 0], Ein[1, 1], 2 * Ein[0, 1]])
        p0, pm_, p2 = X[ns[0] - 1], X[ns[7] - 1], X[ns[3] - 1]          # hoop edge: corner, midside, corner
        a_, b_, c_ = np.linalg.norm(pm_ - p0), np.linalg.norm(p2 - pm_), np.linalg.norm(p2 - p0)
        area2 = np.linalg.norm(np.cross(pm_ - p0, p2 - p0))
        R = min(a_ * b_ * c_ / max(area2, 1e-15), 50.0)
        xc = ef[eid][1][0]
        hi = frames[frames >= xc - 1e-9]; lo = frames[frames <= xc + 1e-9]
        Lb = (hi.min() - lo.max()) if len(hi) and len(lo) else 0.3
        Lb = max(Lb, 0.05)
        Nc = max(kd * 2 * math.sqrt(D11 * A22p) / R, math.pi ** 2 * D11 / Lb ** 2)
        Ns = max(0.67 * 0.747 * E * th * (th / R) ** 1.25 * math.sqrt(R / Lb), 5.35 * math.pi ** 2 * D / Lb ** 2)
        Rc = max(-N[0], 0) / Nc; Rs = abs(N[2]) / Ns
        lamb = 1 / max(Rc, 1e-12) if Rs < 1e-9 else (-Rc + math.sqrt(Rc ** 2 + 4 * Rs ** 2)) / (2 * Rs ** 2)
        out.append((lamb, eid, xc, R, N[0], N[2]))
    out.sort()
    clear = [o for o in out if o[2] > me.st["x_end"] + 0.06]
    area = lambda e_: 1.0
    lm, eid, xc, R, Nx, Nxs = out[0]
    return {"lam_min": lm, "at": [round(float(v), 3) for v in ef[eid][1]], "R": R, "Nx": Nx, "Nxs": Nxs,
            "lam_min_clear": clear[0][0], "at_clear": [round(float(v), 3) for v in ef[clear[0][1]][1]],
            "frac_below_1": sum(o[0] < 1 for o in out) / len(out)}


def post(me, secs, eps_allow, foam, cases_f, names, pm_kd):
    ef = element_frames(me)
    B = read_dat_blocks(os.path.join(FEA, "fus_static.dat"))
    res = {}
    for k_, name in enumerate(names):
        t = float(k_ + 1)
        out = {"reaction_N": B[("total force", "NFIX", t)][0].tolist(), "applied_N": cases_f[name].sum(0).tolist(), "strain": {}, "core": {}}
        eps_x = {}; emax_el = {}
        if getattr(me, "lugs", None):
            out["lug_reactions_N"] = [B[("total force", f"NLUG{k_ + 1}", t)][0].tolist() for k_ in range(len(me.lugs))]
        for eset in STRAIN_SETS:
            if eset in me.skip or eset not in me.el: continue
            A = B[("strains", eset, t)]
            nl = len(secs[eset]["layers"]) if eset in secs else 1
            worst = (0.0, None); worst_c = (0.0, None)          # worst_c: outside the boom-fitting patch (x > x_end + 0.06)
            per = {}
            for row in A:
                eid, ip = int(row[0]), int(row[1])
                layer = (ip - 1) // 8 if nl == 3 else 0
                if nl == 3 and layer == 1: continue                  # foam core: checked in shear below
                _, c, n, t1, t2 = ef[eid]
                pv, exx = inplane(tensor(row[2:8]), t1, t2)
                e = max(abs(pv[0]), abs(pv[1]))
                if e > worst[0]: worst = (e, eid)
                if e > worst_c[0] and eid not in me.fit_elems: worst_c = (e, eid)
                if e > emax_el.get(eid, 0.0): emax_el[eid] = e
                per.setdefault(eid, []).append(exx)
            eps_x.update({e_: np.mean(np.array(v), axis=0) for e_, v in per.items()})
            c = ef[worst[1]][1]
            out["strain"][eset] = {"eps_max": worst[0], "MS": eps_allow / max(worst[0], 1e-12) - 1, "at": [round(v, 3) for v in c]}
            cc = ef[worst_c[1]][1]
            out.setdefault("strain_clear", {})[eset] = {"eps_max": worst_c[0], "MS": eps_allow / max(worst_c[0], 1e-12) - 1, "at": [round(v, 3) for v in cc]}
        for eset in CORE_SETS:
            if eset not in me.el: continue
            A = B[("stresses", eset, t)]
            tmax, at = 0.0, None
            for row in A:
                if (int(row[1]) - 1) // 8 != 1: continue
                _, c, n, t1, t2 = ef[int(row[0])]
                tr = tensor(row[2:8]) @ n; tau = np.linalg.norm(tr - (tr @ n) * n)
                if tau > tmax: tmax, at = tau, c
            out["core"][eset] = {"tau_max_Pa": tmax, "MS": foam["shear_strength"] / max(tmax, 1e-9) - 1, "at": [round(v, 3) for v in at]}
        gaps = [(a_, b_) for a_, b_ in zip(me.st["frames"][:-1], me.st["frames"][1:]) if b_ < me.st["x_ml"] - 1e-6]
        # every bay aft of the main-gear frame; plane sections only hold away from load introduction (the wing clamp
        # sits at the crown, the keel carries the load at the belly, so the first bay is still diffusing)
        out["hand_F2_bays"] = [section_check(me, cases_f[name], ef, eps_x, secs, 0.5 * (a_ + b_)) for a_, b_ in gaps]
        out["_emax"] = emax_el
        out["hand_F2"] = out["hand_F2_bays"][0]                  # the prismatic cabin bay (the ramp bays are not plane cuts)
        res[name] = out
    buck = {} if "ESKIN" in me.skip else {name: skin_buckling(me, B, float(k_ + 1), ef, secs["_skin_lam"], pm_kd) for k_, name in enumerate(names)}
    return res, buck

def hand_fittings(me, res, FIT):
    """H1: FE lug reactions against the hand (equal-stiffness) split. H2: FE wing-frame strain outside the lug bases
    against the closed-ring hand calc. H3: FE bulkhead strain (no hand number: reported)."""
    out = {}
    for name, o in res.items():
        hc = FIT["cases"][name]
        fe = np.array(o.get("lug_reactions_N", [])); hd = np.array(hc["lug_reactions_N"])
        h = {"lug_fe_N": fe.round(1).tolist(), "lug_hand_N": hd.round(1).tolist(),
             "lug_max_fe_N": float(np.linalg.norm(fe, axis=1).max()), "lug_max_hand_N": hc["lug_max_N"]}
        for tag, fset in (("front", "EFRAMEF"), ("rear", "EFRAMER")):
            sec = FIT["wing_frames"][tag]; fr = hc[f"frame_{tag}"]
            eps_h = 6 * fr["M_max_Nm"] / (FIT["E_frame"] * sec["t_m"] * sec["d_m"] ** 2) + abs(fr["N_at_Mmax_N"]) / (FIT["E_frame"] * sec["t_m"] * sec["d_m"])
            h[f"frame_{tag}"] = {"eps_hand": eps_h, "eps_fe_clear": o["strain_clear"][fset]["eps_max"], "at_fe": o["strain_clear"][fset]["at"],
                                 "eps_fe_all": o["strain"][fset]["eps_max"]}
        h["bulkhead"] = {"eps_fe_clear": o["strain_clear"]["EBULK"]["eps_max"], "eps_fe_all": o["strain"]["EBULK"]["eps_max"], "at": o["strain"]["EBULK"]["at"]}
        out[name] = h
    return out


def figure(me, res, buck, eps_allow):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LogNorm
    ef = element_frames(me)
    show = ("ESKIN",) if "ESKIN" not in me.skip else ("EWEB", "EFRAME", "EFLANGE", "EFRAMEF", "EFRAMER", "EBULK", "EWEBD", "EFLANGED")
    fig = plt.figure(figsize=(12, 6.2))
    gs = fig.add_gridspec(2, 2, width_ratios=[2.3, 1], hspace=0.35, wspace=0.25)
    ax = [fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[1, 0]), fig.add_subplot(gs[:, 1])]
    what = "skin" if show == ("ESKIN",) else "keel web, flange and frames"
    for a_, name in zip(ax[:2], ("LC1 hover pull-up n=2", "LC5 airplane gust n=2.78")):
        em = res[name]["_emax"]
        pts = np.array([(ef[e][1][0], ef[e][1][2], v) for e, v in em.items() if ef[e][0] in show and ef[e][1][1] >= 0])
        sc = a_.scatter(pts[:, 0], pts[:, 1], c=np.clip(pts[:, 2], 1e-5, None) / eps_allow, s=9, cmap="viridis", norm=LogNorm(0.02, 2))
        for xf in me.st["frames"]: a_.axvline(xf, color="0.85", lw=0.5, zorder=0)
        a_.set_title(f"{name.split()[0]} ({' '.join(name.split()[1:])}): {what} strain / allowable, left side, ultimate", fontsize=9)
        a_.set_xlabel("x [m]  (nose left)"); a_.set_ylabel("z [m]")
        a_.set_aspect("equal"); a_.invert_xaxis()
    fig.colorbar(sc, ax=ax[:2], shrink=0.9, label="max principal strain / eps_allow", pad=0.02)
    names = list(res)
    if buck:
        ax[2].bar(range(len(names)), [buck[n]["lam_min_clear"] for n in names], color="#b55")
        ax[2].axhline(1, color="k", lw=0.8); ax[2].set_yscale("log")
        ax[2].set_title("skin buckling factor at ultimate (hand, FE loads)", fontsize=9)
    else:
        groups = [g for g in ("EFLANGE", "EWEB", "EFLOOR", "EFRAMEF", "EFRAMER", "EBULK", "EWEBD", "EFLOORD") if g in res[names[0]]["strain"]] \
            if me.fit_elems else ["EFLANGE", "EWEB", "EFLOOR", "EFRAME"]
        wdt = 0.8 / len(groups)
        key = "strain_clear" if me.fit_elems else "strain"
        for k_, g in enumerate(groups):
            ax[2].bar(np.arange(len(names)) + (k_ - (len(groups) - 1) / 2) * wdt, [res[n][key][g]["MS"] for n in names], wdt, label=g[1:].lower())
        ax[2].axhline(0, color="k", lw=0.8); ax[2].legend(fontsize=8)
        ax[2].set_title("strain margin of safety at ultimate" + (" (outside the lug and collar patches)" if me.fit_elems else ""), fontsize=9)
    ax[2].set_xticks(range(len(names))); ax[2].set_xticklabels([n.split()[0] for n in names])
    plt.savefig(os.path.join(RESULTS, "fig_fuselage_shell" + ("" if me.fit_elems else "_nofit") + ".png"), dpi=150, bbox_inches="tight"); plt.close(fig)


def main(build_only=False, post_only=False):
    os.makedirs(FEA, exist_ok=True)
    ctx = tf.context()
    d = tf.merge(tf.DEFAULT, json.load(open(os.path.join(ROOT, "designs", "selected.json"))))
    if ctx["p"]["fuselage"].get("fittings", False): ctx["fit"] = jload(os.path.join(RESULTS, "fittings.json"))
    r, fb = free_body(ctx, d)
    me = build_mesh(ctx, d, r["x_payload"])
    sz_ = ctx["sz"]; me.rb = np.array([sz_["fuselage"]["x_tail"] + 0.05, 0, -(sz_["wing"]["c"] * sz_["wing"]["tc"] / 2) - 0.10])
    tag = "" if ctx.get("fit") else "_nofit"
    secs, qi, foam, eps_allow = sections(ctx, d)
    X = np.array(me.X)
    # wing attach: top arc of the two wing-attach frames (above the section centre + 70 % of the half-height)
    fixed = []; me.lugs = []
    if ctx.get("fit"):                                           # four lug bases: frame nodes within LUG_R of each lug
        live = {n for s_, els in me.el.items() if s_ not in me.skip for _, ns in els for n in ns}
        for k_, lp in enumerate(ctx["fit"]["lug_points"]):
            # a lug turns on its bolt (axis x, through the frame plane), so it is a PIN for in-plane loads: one node on
            # the frame's mid-depth line. (First version pinned every frame node within LUG_R: a patch across the frame
            # depth is a moment clamp, and the frame strain came out at a third of the hand pin-ring value.)
            a = int(np.argmin(abs(me.xa - lp[0])))
            b = ctx["fit"]["wing_frames"]["front" if k_ < 2 else "rear"]["lug_idx"][k_ % 2]
            b = b if b % 2 == 0 else b + 1
            ids = [me.idx[("fr", a, b, 1)]]
            me.lugs.append(ids); fixed += ids
    else:
        for xk in (me.st["x_f"], me.st["x_r"]):
            a = int(np.argmin(abs(me.xa - xk))); x_, P, g = me.rings[a]
            fixed += [me.idx[("s", a, b)] for b in range(me.np) if ("s", a, b) in me.idx and P[b, 1] > g["zc"] + 0.7 * g["hh"]]
    # elements touching a support or collar node: load introduction into the fittings, reported apart ("clear" excludes them)
    fit_n = set(fixed) | {i for c_ in me.collars.values() for i in c_["ids"]}
    write_inp(me, *sections(ctx, d)[:1], {"E": 1, "nu": 0.3}, {"E": 1, "G": 1}, {}, fixed, None)   # numbers the elements
    me.fit_elems = {eid for s_, ids in me.eid.items() for eid, (_, ns) in zip(ids, me.el[s_]) if fit_n & set(ns)} if ctx.get("fit") else set()
    cases_f, used = {}, {}
    for name, cs in fb.items():
        cases_f[name], used[name] = map_loads(me, cs, me.st)
        # CalculiX drops a *CLOAD on the dependent node of an *EQUATION (first version: wing reactions no longer
        # balanced the applied loads). Move each such load onto its master node: same point, same statics.
        f = cases_f[name]
        for sl, ma in reversed(me.ties):                          # floor ends tie to web tops, which are masters
            f[ma - 1] += f[sl - 1]; f[sl - 1] = 0.0
    write_inp(me, secs, qi, foam, cases_f, fixed, None if post_only else os.path.join(FEA, "fus_static.inp"))
    names = list(cases_f)
    nel = {k_: len(v) for k_, v in me.el.items()}
    # shell mass (areal density x area) for comparison with the beam model's keel + fairing
    def area(ns): P = X[np.array(ns[:4]) - 1]; return 0.5 * (np.linalg.norm(np.cross(P[1] - P[0], P[3] - P[0])) + np.linalg.norm(np.cross(P[1] - P[2], P[3] - P[2])))
    mass = {k_: sum(area(ns) for _, ns in me.el[k_]) * secs[k_]["areal"] for k_ in ("ESKIN", "EWEB", "EFLOOR", "EFLANGE", "EWEBD", "EFLOORD", "EFLANGED") if k_ in me.el}
    for fset, t_ in me.frame_set.items(): mass[fset] = sum(area(ns) for _, ns in me.el[fset]) * t_ * qi["rho"]
    if "EBULK" in me.el: mass["EBULK"] = sum(area(ns) for _, ns in me.el["EBULK"]) * secs["EBULK"]["areal"]
    if ctx.get("fit"):
        F_ = ctx["fit"]
        mass["fittings_metal"] = 4 * F_["lug"]["mass_each_kg"] + 2 * F_["socket"]["collar_mass_each_kg"]
        mass["boom_extension"] = F_["socket"]["boom_extension_kg"]
    info = dict(nodes=len(X), elements=nel, frames_x=me.st["frames"], stations={k_: v for k_, v in me.st.items() if k_ != "frames"},
                n_fixed=len(fixed), n_bulkhead_keel_merged=getattr(me, "n_merged", 0), n_ties=len(me.ties), mass_kg=mass, eps_allow=eps_allow, load_patches=used,
                applied_total_N={n: f.sum(0).tolist() for n, f in cases_f.items()},
                beam_free_body_total_N={n: c["total_F"].tolist() for n, c in fb.items()})
    print(json.dumps({k_: info[k_] for k_ in ("nodes", "elements", "n_fixed", "mass_kg", "applied_total_N")}, indent=1))
    with open(os.path.join(RESULTS, f"fuselage_shell_model{tag}.json"), "w") as fh: json.dump(info, fh, indent=1)
    if build_only: return
    if not post_only:
        t = run_ccx("fus_static"); print(f"static: {t:.0f} s")
    res, buck = post(me, secs, eps_allow, foam, cases_f, names, ctx["pm"]["materials"]["shell_knockdown"])
    figure(me, res, buck, eps_allow)
    for o in res.values(): o.pop("_emax")
    mb = r["mass_breakdown"]
    info.update(cases=res, skin_buckling=buck, beam_model_mass_kg={"keel": mb.get("keel", 0.0), "fuselage_fairing": mb.get("fuselage_fairing", 0.0)})
    if ctx.get("fit"): info["hand_H"] = hand_fittings(me, res, ctx["fit"])
    with open(os.path.join(RESULTS, f"fuselage_shell_model{tag}.json"), "w") as fh: json.dump(info, fh, indent=1)
    if ctx.get("fit"): print(json.dumps(info["hand_H"], indent=1))
    for name, o in res.items():
        print(name)
        print("   reaction", [round(v, 1) for v in o["reaction_N"]], " applied", [round(v, 1) for v in o["applied_N"]])
        for k_, v in o["strain"].items(): print(f"   {k_:8s} eps {v['eps_max']*1e6:7.0f} ue  MS {v['MS']:+6.2f}  at {[float(q) for q in v['at']]}")
        for k_, v in o["strain_clear"].items(): print(f"   clear {k_:8s} eps {v['eps_max']*1e6:7.0f} ue  MS {v['MS']:+6.2f}  at {[float(q) for q in v['at']]}")
        for k_, v in o["core"].items(): print(f"   core {k_:8s} tau {v['tau_max_Pa']/1e3:6.0f} kPa  MS {v['MS']:+6.2f}  at {[float(q) for q in v['at']]}")
        h = o["hand_F2"]
        print(f"   F2 x={h['x_s']:.3f}: crown beam {h['crown']['beam']*1e6:.0f} ue FE {h['crown']['fe']*1e6:.0f} ue ({h['crown']['diff']:+.1%}); "
              f"belly beam {h['belly']['beam']*1e6:.0f} FE {h['belly']['fe']*1e6:.0f} ({h['belly']['diff']:+.1%}); rms {h['rms_diff_of_peak']:.1%}")
        for h in o["hand_F2_bays"]:
            q = h["resultants"]
            print(f"      bay x={h['x_s']:+.3f}: statics N {q['N_statics']:7.1f} / FE {q['N_fe']:7.1f} N,  M_pitch {q['M_pitch_statics']:7.1f} / {q['M_pitch_fe']:7.1f} N m,  M_yaw {q['M_yaw_statics']:7.1f} / {q['M_yaw_fe']:7.1f} N m")
            print(f"      bay x={h['x_s']:+.3f}: crown {h['crown']['beam']*1e6:6.0f}/{h['crown']['fe']*1e6:6.0f} ue  belly {h['belly']['beam']*1e6:6.0f}/{h['belly']['fe']*1e6:6.0f} ue (beam/FE)  M_pitch {h['M_pitch']:7.1f} N m")
        b_ = buck.get(name)
        if b_: print(f"   skin buckling (hand, FE loads): min factor {b_['lam_min']:.2f} at {b_['at']} (R {b_['R']:.2f} m, N_x {b_['Nx']:.0f} N/m, N_xs {b_['Nxs']:.0f} N/m);"
              f" away from the boom fitting {b_['lam_min_clear']:.2f}; skin area below 1.0: {b_['frac_below_1']:.0%}")


if __name__ == "__main__":
    main(build_only="--build" in sys.argv, post_only="--post" in sys.argv)

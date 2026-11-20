"""Wing shell finite-element model (CalculiX) of the Osprey tilt-tricopter.

    python3 src/wing_shell.py            build, run (static, five load cases), post -> results/wing_shell_model.json
    python3 src/wing_shell.py --build    write fea/wing/wing_static.inp only
    python3 src/wing_shell.py --post     post-process existing results only

Why. The frame screen (tiltframe.py) models the wing as ONE beam: a thin-walled box between the spars, with no ribs.
Its panels are checked as infinitely long plates as wide as the box, and the wing is clamped at one centre node.
A shell model can answer three things the beam cannot:
  1. Panel buckling between ribs. The beam's governing margin is the upper box skin buckling at LC1 (+0.15) as a
     long plate. Ribs make the panels short, and the shell gives the real membrane loads in each panel.
  2. Load introduction. The pods hang on the tip rib, and the fuselage carries the wing on four bolted lugs
     (fittings.py) at y = +-0.203 m, not at one centre node.
  3. Shear lag and the dihedral / sweep kink at the root. The beam has plane sections; the shell does not.

Model (x forward, y left, z up; the same axes and origin as tiltframe.py and geometry.py):
  * Box: NACA 4415 contour between the front spar (15 % c) and the rear spar (60 % c), 6 deg forward sweep and
    3.5 deg dihedral, a kink at y = 0. The contour is the STL's (wing_sections.surfaces, pitched by the incidence about the qc, chord line 2 % c below the axis).
    The skin mid-surface is inset by half the sandwich thickness from the mould line.
  * Upper and lower box skins: sandwich, faces = the beam's cap laminate (n_ud UD + n_w45 woven +-45 per face), the
    wing core. Spar webs: sandwich, n_w45 woven +-45 per face. Laminates from designs/selected.json, so the shell and
    the beam are the same structure.
  * Ribs (not in the beam model): flat sandwich plates in the streamwise x-z plane at every beam node station, at the
    two lug stations (y = +-y_lug) and at the tips. ASSUMED lay-up RIB_W45 woven +-45 per face on the wing core.
  * LE and TE shells outside the box are fairings, as in the beam model: mass only (their mass is already on the beam's
    wing nodes, so it arrives with the inertia loads).
  * Materials: each face homogenised by CLT, transversely isotropic about the span direction (one orientation per
    wing half, axis 1 along the swept, dihedralled span line); ribs about x. Airframe/01's method.
  * Support: four lugs (fittings.py), each a single pinned node (translations only) at the foot of a spar web at
    y = +-y_lug. A pin turns on its bolt; a node patch would clamp it (lesson from fuselage_shell.py).

Loads. For every load case the beam model is solved with inertia relief (tiltframe.run). The wing free body is
everything connected to the wing once the carry-through link to the keel is cut: the box, the pods, the pivots and
the rotor heads. On each of those beam nodes the load is
    L = F_ext + M Phi (g - a)
(applied forces, gravity, minus the rigid-body inertia, from the same solve), times the ultimate factor 1.5. Wing
node loads are spread over the box perimeter at that node's station, and each pod's total load over the tip
station, as the least-norm nodal forces with the same resultant force and moment (fuselage_shell.patch_forces).
The beam node at y = +-b/24 sits 21 mm inboard of the lug rib; its load goes to the lug station with the moment
of the shift included.

Checks (all ultimate):
  W1 equilibrium: the four lug reactions against minus the applied total (exact).
  W2 lug split: FE wing-side lug reactions against the hand split (fittings.py, equal pin stiffness) and the
     fuselage FE (fuselage_shell.py). Wing and fuselage see equal and opposite forces.
  W3 beam theory at mid-bay cuts on the left wing: FE spanwise strain at the upper and lower box skin against
     eps = N/EA + kappa_c a + kappa_n b from the outboard loads, and the FE stress resultants against statics.
  W4 Bredt torsion: shear flow at the middle of the upper skin, q = T / (2 A), against the FE.
  W5 tip deflection against the beam model (relative to the lug station).
  W6 panel buckling of every box-skin element by hand from its FE membrane loads, plate between ribs (Whitney,
     orthotropic, simply supported, m half-waves), sandwich shear softening, R_c + R_s^2 = 1; face wrinkling.
  strain: max principal strain in every face layer against eps_allow (Airframe/01, CAI/OHC); core shear stress.
"""
import json, math, os, sys, time, subprocess
import numpy as np
from tiltcfg import ROOT, RESULTS, G0
import tiltframe as tf
import materials as mat
import fuselage_shell as fs
import wing_sections as ws

FEA = os.path.join(ROOT, "fea", "wing")
JOB = "wing_static"
NC, NV = 16, 6          # elements chordwise across a box skin, and up a spar web
DY = 0.025              # m, target element length along the span
RIB_W45 = 2             # ASSUMED: woven +-45 plies per rib face (no rib in the beam model)
UF = 1.5
LUG_CLEAR = 0.06        # m: elements within this distance of a lug node are left out of the "clear" margins
KINDS = ("EUP", "ELO", "EWF", "EWR", "ERIB")
NAMES = {"EUP": "upper skin", "ELO": "lower skin", "EWF": "front spar web", "EWR": "rear spar web", "ERIB": "ribs"}


# ------------------------------------------------------------------ geometry --------------------------------------------
def contour(code):
    """Upper and lower surface z/c as functions of x/c (wing_sections.surfaces, the STL's section)."""
    xs, zu, zl = ws.surfaces(code)
    return (lambda x: np.interp(x, xs, zu)), (lambda x: np.interp(x, xs, zl))


class WingMesh:
    def __init__(self, ctx, d, y_lug):
        sz, pw = ctx["sz"], ctx["p"]["wing"]
        w = sz["wing"]
        self.b, self.c, self.tc = w["b"], w["c"], w["tc"]
        self.tsw = math.tan(math.radians(-w["sweep_deg"])); self.tdi = math.tan(math.radians(w["dihedral_deg"]))
        self.xf, self.xr = pw["spar_front_xc"], pw["spar_rear_xc"]
        self.zu, self.zl = contour(w["airfoil"])
        self.inc = w.get("incidence_deg", 0.0)
        self.y_lug = y_lug
        self.X, self.key = [], {}
        self.el = {}
        # stations: the beam model's node stations (12 per side), the one next to the lug moved onto the lug
        nseg = 12
        yb = [k * self.b / 2 / nseg for k in range(nseg + 1)]
        yb[1] = y_lug
        self.st_abs = yb
        self.stations = sorted(set([-v for v in yb[1:]] + yb))
        # quadratic grid along the span: corners + midsides; station indices in it
        yq = [self.stations[0]]
        for a, b_ in zip(self.stations[:-1], self.stations[1:]):
            n = max(2, int(math.ceil((b_ - a) / DY)))
            yq += list(np.linspace(a, b_, 2 * n + 1)[1:])
        self.yq = np.array(yq)
        self.j_st = [int(np.argmin(abs(self.yq - s))) for s in self.stations]
        self.np_ = 4 * NC + 4 * NV                                  # perimeter points (closed loop, quadratic)
        self.inset = 0.0

    # x, z of a box point; xc the chord fraction, which = 0 lower / 1 upper surface (mid-surface inset)
    def surf(self, y, xc, upper):
        ay = abs(y)
        zc = (self.zu(xc) if upper else self.zl(xc)) + (-self.inset if upper else self.inset) / self.c
        x, z = ws.to_wing(xc, zc, self.c, self.inc)                 # section pitched by the incidence about the qc
        return np.array([ay * self.tsw + float(x), y, ay * self.tdi + float(z)])

    def perim(self, p, y):
        """Perimeter point p (0..np_-1): lower skin front->rear, rear web up, upper skin rear->front, front web down."""
        p %= self.np_
        n2c, n2v = 2 * NC, 2 * NV
        xcs = lambda i: self.xf + (self.xr - self.xf) * i / n2c
        if p <= n2c: return self.surf(y, xcs(p), False)
        if p <= n2c + n2v:
            k = p - n2c; lo, up = self.surf(y, self.xr, False), self.surf(y, self.xr, True)
            return lo + (up - lo) * k / n2v
        if p <= 2 * n2c + n2v:
            i = n2c - (p - n2c - n2v); return self.surf(y, xcs(i), True)
        k = n2v - (p - 2 * n2c - n2v); lo, up = self.surf(y, self.xf, False), self.surf(y, self.xf, True)
        return lo + (up - lo) * k / n2v

    def rib_key(self, j, i, k):
        """Rib grid point (chord i 0..2NC, height k 0..2NV) at span index j -> a perimeter key on the boundary."""
        n2c, n2v = 2 * NC, 2 * NV
        if k == 0: return ("p", j, i)
        if k == n2v: return ("p", j, 2 * n2c + n2v - i)
        if i == 0: return ("p", j, (2 * n2c + 2 * n2v - k) % self.np_)
        if i == n2c: return ("p", j, n2c + k)
        return ("r", j, i, k)

    def node(self, key):
        if key in self.key: return self.key[key]
        y = self.yq[key[1]]
        if key[0] == "p": P = self.perim(key[2], y)
        else:
            _, j, i, k = key
            xc = self.xf + (self.xr - self.xf) * i / (2 * NC)
            lo, up = self.surf(y, xc, False), self.surf(y, xc, True)
            P = lo + (up - lo) * k / (2 * NV)
        self.X.append(P); self.key[key] = len(self.X)
        return self.key[key]

    def build(self):
        n2c, n2v = 2 * NC, 2 * NV
        q8 = lambda f, i, j: [f(i, j), f(i + 2, j), f(i + 2, j + 2), f(i, j + 2), f(i + 1, j), f(i + 2, j + 1), f(i + 1, j + 2), f(i, j + 1)]
        for j in range(0, len(self.yq) - 1, 2):
            side = "L" if self.yq[j + 1] > 0 else "R"
            for p in range(0, self.np_, 2):
                kind = "ELO" if p < n2c else "EWR" if p < n2c + n2v else "EUP" if p < 2 * n2c + n2v else "EWF"
                ns = q8(lambda a, b_: self.node(("p", b_, a % self.np_)), p, j)
                self.el.setdefault(kind + side, []).append(ns)
        for j in self.j_st:
            for i in range(0, n2c, 2):
                for k in range(0, n2v, 2):
                    ns = q8(lambda a, b_: self.node(self.rib_key(j, a, b_)), i, k)
                    self.el.setdefault("ERIB", []).append(ns)
        self.Xa = np.array(self.X)
        return self

    def ring(self, y):
        """Node ids of the box perimeter (and the rib) at the station nearest y."""
        j = self.j_st[int(np.argmin([abs(s - y) for s in self.stations]))]
        return sorted({v for k_, v in self.key.items() if k_[1] == j})

    def lug_nodes(self):
        """Front and rear spar web feet at y = +-y_lug, in fittings.json order: front L, front R, rear L, rear R."""
        out = []
        for p in (2 * NC + 2 * NV + 2 * NC + 2 * NV, 2 * NC):          # front web foot (= p 0), rear web foot
            for y in (self.y_lug, -self.y_lug):
                j = self.j_st[int(np.argmin([abs(s - y) for s in self.stations]))]
                out.append(self.key[("p", j, p % self.np_)])
        return out


# ------------------------------------------------------------------ sections --------------------------------------------
def cap_plies(wd, k):
    """UD cap plies in beam segment k (0..11 from the root), the beam model's rule (tiltframe.build):
    n = round(n_root + (n_tip - n_root) eta), eta at the segment middle."""
    eta = (k + 0.5) / 12
    return int(round(wd["n_ud_root"] + (wd["n_ud_tip"] - wd["n_ud_root"]) * eta))


def sec_key(me, eset, eid):
    """Section key of an element: the cap sets carry their ply count, the rest the set kind."""
    kind = eset if eset == "ERIB" else eset[:-1]
    return f"{kind}{me.nud[eid]}" if kind in ("EUP", "ELO") else kind


def sections(ctx, d):
    pm = ctx["pm"]; foam = pm["materials"]["foam"]
    wd = d["wing"]; ct = wd["core_mm"] * 1e-3
    cap = mat.wall(pm, n_ud0=wd["n_ud_root"], n_w45=wd["n_w45"], core_t=ct)
    web = mat.wall(pm, n_w45=wd["n_w45"], core_t=ct)
    rib = mat.wall(pm, n_w45=RIB_W45, core_t=ct)
    face = lambda lam: mat.Laminate(lam.plies)
    rho_face = lambda lam: sum(m_["t_ply"] * m_["rho"] for m_, _ in lam.plies) / sum(m_["t_ply"] for m_, _ in lam.plies)
    secs = {}
    for k_, lam, nm in (("EUP", cap, "FCAP"), ("ELO", cap, "FCAP"), ("EWF", web, "FWEB"), ("EWR", web, "FWEB"), ("ERIB", rib, "FRIB")):
        secs[k_] = dict(layers=[(nm, face(lam).h), ("FOAM", ct), (nm, face(lam).h)], mats={nm: fs.face_material(face(lam))},
                        areal=2 * face(lam).h * rho_face(lam) + ct * foam["rho"], lam=lam, face=face(lam))
    # tapered caps: one section per UD ply count, "EUP3", "ELO2", ... (cap_plies() gives each element's count)
    for n in sorted({cap_plies(wd, k) for k in range(12)}):
        lam = mat.wall(pm, n_ud0=n, n_w45=wd["n_w45"], core_t=ct); nm = f"FCAP{n}"
        for k_ in ("EUP", "ELO"):
            secs[f"{k_}{n}"] = dict(layers=[(nm, face(lam).h), ("FOAM", ct), (nm, face(lam).h)], mats={nm: fs.face_material(face(lam))},
                                    areal=2 * face(lam).h * rho_face(lam) + ct * foam["rho"], lam=lam, face=face(lam))
    qi = mat.strain_allowable(pm)
    return secs, foam, qi["eps_allow"]


# ------------------------------------------------------------------ loads -----------------------------------------------
def free_body(ctx, d):
    """Run the beam model; return the wing-side beam nodes and their ultimate loads, per case, plus the beam's own
    wing deflections (relative to the lug station) for check W5."""
    r = tf.run(ctx, d, want_modes=False)
    out = {}
    for name, (mode, F, acc) in r["_loads"].items():
        M, info = r["_models"][mode]
        cut = [i for i, e in enumerate(M.elems) if e["name"] == "carry-through"]
        adj = {}
        for i, e in enumerate(M.elems):
            if i in cut: continue
            adj.setdefault(e["n1"], set()).add(e["n2"]); adj.setdefault(e["n2"], set()).add(e["n1"])
        wn = list(info["wing_nodes"])
        owner = {n: n for n in wn}                                   # each wing-side node -> the wing node it hangs on
        todo = list(wn)
        while todo:
            n = todo.pop()
            for m_ in adj.get(n, ()):
                if m_ not in owner: owner[m_] = owner[n]; todo.append(m_)
        Phi = M.rigid_modes(M._cg(M.total_mass()))
        g6 = np.r_[0, 0, -G0, 0, 0, 0]
        Lv = UF * (F + M.M @ (Phi @ (g6 - acc)))
        groups = {}
        for n, root in owner.items():                               # resultant per wing node, moment about that node
            g = groups.setdefault(root, {"F": np.zeros(3), "M": np.zeros(3), "x": M.X[root].copy(), "n": 0})
            l6 = Lv[6 * n:6 * n + 6]
            g["F"] += l6[:3]; g["M"] += l6[3:] + np.cross(M.X[n] - M.X[root], l6[:3]); g["n"] += 1
        u, acc2, resid = M.static_inertia_relief(F, hold_node=M.tags["centre"])
        dz = np.array([u[6 * n + 2] for n in wn]); yw = np.array([M.X[n][1] for n in wn])
        out[name] = dict(mode=mode, groups=groups, total_F=sum(g["F"] for g in groups.values()), wing_y=yw, wing_dz=UF * dz)
    return r, out


def map_loads(me, case):
    X = me.Xa; f = np.zeros_like(X); used = {}
    for root, g in case["groups"].items():
        y = g["x"][1]
        ids = me.ring(y)
        fi = fs.patch_forces(X[np.array(ids) - 1], g["F"], g["M"], g["x"])
        for i, v in zip(ids, fi): f[i - 1] += v
        used[f"{y:+.3f}"] = dict(n_nodes=len(ids), F=g["F"].tolist(), beam_nodes=g["n"])
    return f, used


# ------------------------------------------------------------------ CalculiX input --------------------------------------
def write_inp(me, secs, foam, cases_f, lugs, path):
    L = ["*HEADING", "Osprey tilt-tricopter wing shell model (wing_shell.py)", "*NODE"]
    L += [f"{i + 1}, {x[0]:.6f}, {x[1]:.6f}, {x[2]:.6f}" for i, x in enumerate(me.X)]
    eid = 1; me.eid = {}; me.nud = {}; ssets = {}
    seg = me.b / 2 / 12                                          # beam segment length along y
    for eset, els in me.el.items():
        L.append(f"*ELEMENT, TYPE=S8R, ELSET={eset}")
        for ns in els:
            L.append(f"{eid}, " + ", ".join(map(str, ns))); me.eid.setdefault(eset, []).append(eid)
            if eset != "ERIB":
                ym = abs(float(np.mean(me.Xa[np.array(ns[:4]) - 1][:, 1])))
                me.nud[eid] = cap_plies(me.d["wing"], min(int(ym / seg), 11))
            ssets.setdefault(eset + "|" + sec_key(me, eset, eid), []).append(eid)
            eid += 1
    for k_, ids in ssets.items():
        L += [f"*ELSET, ELSET=S{k_.replace('|', '_')}"] + [", ".join(map(str, ids[i:i + 12])) for i in range(0, len(ids), 12)]
    for k_, n in enumerate(lugs):
        L += [f"*NSET, NSET=NLUG{k_ + 1}", f"{n}"]
    L += ["*NSET, NSET=NLUGS", ", ".join(map(str, lugs))]
    for tag, y in (("TIPL", me.b / 2), ("TIPR", -me.b / 2)):
        ids = me.ring(y)
        L += [f"*NSET, NSET=N{tag}"] + [", ".join(map(str, ids[i:i + 12])) for i in range(0, len(ids), 12)]
    es = lambda sgn: np.array([me.tsw, sgn, me.tdi]) / math.sqrt(me.tsw ** 2 + 1 + me.tdi ** 2)
    for nm, a in (("OL", es(1)), ("OR", es(-1))):
        L += [f"*ORIENTATION, NAME={nm}, SYSTEM=RECTANGULAR", f"{a[0]:.6f}, {a[1]:.6f}, {a[2]:.6f}, 1., 0., 0."]
    L += ["*ORIENTATION, NAME=OX, SYSTEM=RECTANGULAR", "1., 0., 0., 0., 0., 1."]
    mats = {}
    for s_ in secs.values(): mats.update(s_["mats"])
    for nm, m_ in mats.items():
        L += [f"*MATERIAL, NAME={nm}", "*ELASTIC, TYPE=ENGINEERING CONSTANTS",
              f"{m_['E1']:.6g}, {m_['E2']:.6g}, {m_['E3']:.6g}, {m_['nu12']:.4f}, {m_['nu13']:.4f}, {m_['nu23']:.4f}, {m_['G12']:.6g}, {m_['G13']:.6g}",
              f"{m_['G23']:.6g}, 0."]
    L += ["*MATERIAL, NAME=FOAM", "*ELASTIC, TYPE=ENGINEERING CONSTANTS",
          f"{foam['E']:.6g}, {foam['E']:.6g}, {foam['E']:.6g}, 0.3, 0.3, 0.3, {foam['G']:.6g}, {foam['G']:.6g}", f"{foam['G']:.6g}, 0."]
    for k_ in ssets:
        eset, key = k_.split("|")
        ori = "OX" if eset == "ERIB" else ("OL" if eset.endswith("L") else "OR")
        L += [f"*SHELL SECTION, ELSET=S{eset}_{key}, COMPOSITE"] + [f"{t:.6g},, {m_}, {ori}" for m_, t in secs[key]["layers"]]
    L += ["*BOUNDARY", "NLUGS, 1, 3"]
    for name, f in cases_f.items():
        L += ["*STEP", "*STATIC", "*CLOAD, OP=NEW"]
        for i in np.nonzero(np.abs(f).sum(1) > 1e-9)[0]:
            for dof in range(3):
                if abs(f[i, dof]) > 1e-9: L.append(f"{i + 1}, {dof + 1}, {f[i, dof]:.6e}")
        for k_ in range(len(lugs)): L += [f"*NODE PRINT, NSET=NLUG{k_ + 1}, TOTALS=ONLY", "RF"]
        L += ["*NODE PRINT, NSET=NTIPL", "U", "*NODE PRINT, NSET=NTIPR", "U"]
        for eset in me.el: L += [f"*EL PRINT, ELSET={eset}", "E"]
        for eset in me.el: L += [f"*EL PRINT, ELSET={eset}", "S"]
        L += ["*NODE FILE", "U", "*EL FILE", "E", "*END STEP"]
    with open(path, "w") as fh: fh.write("\n".join(L) + "\n")


def run_ccx():
    env = dict(os.environ, OMP_NUM_THREADS="1", CCX_NPROC_EQUATION_SOLVER="1")
    t0 = time.time()
    r = subprocess.run(["nice", "-n", "19", "ccx", "-i", JOB], cwd=FEA, env=env, capture_output=True, text=True)
    with open(os.path.join(FEA, JOB + ".log"), "w") as fh: fh.write(r.stdout + r.stderr)
    if "Job finished" not in r.stdout: raise RuntimeError(f"ccx {JOB} failed, see fea/wing/{JOB}.log")
    return time.time() - t0


# ------------------------------------------------------------------ post ------------------------------------------------
def read_dat(path):
    """{(quantity, set, time): rows}; quantity in strains, stresses, total force, displacements."""
    import re
    blocks, cur, rows = {}, None, []                             # each block becomes an array as soon as it ends (the
    hdr = re.compile(r"\s*(strains|stresses|total force|displacements).*?(?:for set|set)\s+(\S+)\s+and time\s+(\S+)")
    def close():                                                 # .dat is ~300 MB; lists of floats would need GBs)
        if cur is not None: blocks[cur] = np.array(rows, dtype=float)
    for ln in open(path):
        m_ = hdr.match(ln)
        if m_:
            close(); cur = (m_.group(1), m_.group(2), float(m_.group(3))); rows = []; continue
        if cur is not None and ln.strip():
            tok = ln.split()
            try: rows.append([float(v) for v in tok[:8]])
            except ValueError: close(); cur = None; rows = []
    close()
    return blocks


def frames(me):
    """Centroid, normal, and tangents (t1 along the local span line for skins/webs, along x for ribs) per element."""
    X = me.Xa; out = {}
    es = {s: np.array([me.tsw, s, me.tdi]) / math.sqrt(me.tsw ** 2 + 1 + me.tdi ** 2) for s in (1, -1)}
    for eset, ids in me.eid.items():
        for eid, ns in zip(ids, me.el[eset]):
            P = X[np.array(ns[:4]) - 1]
            n = np.cross(P[2] - P[0], P[3] - P[1]); n /= np.linalg.norm(n)
            c = X[np.array(ns) - 1].mean(0)
            a = np.array([1.0, 0, 0]) if eset == "ERIB" else es[1 if c[1] >= 0 else -1]
            t1 = a - (a @ n) * n; t1 /= np.linalg.norm(t1); t2 = np.cross(n, t1)
            out[eid] = (eset, c, n, t1, t2)
    return out


def layer_rows(B, eset, t):
    """Per element: list of (layer, 3x3 tensor) of the integration points (S8R composite: 8 points per layer).
    CalculiX 2.21 writes composite-shell strains and stresses in each element's OWN system (the rows end with
    "OL_shell_<eid>"): axis 1 = the orientation's axis 1 projected onto the shell, axis 2 in the shell plane, axis 3
    = the normal. So the in-plane part is the upper-left 2x2 block and the transverse shear is (13, 23)."""
    out = {}
    for row in B[eset]:
        eid, ip = int(row[0]), int(row[1])
        out.setdefault(eid, []).append(((ip - 1) // 8, fs.tensor(row[2:8])))
    return out


def panel_buckling(lam, a, b, Nx, Ny, Nxy):
    """Orthotropic plate a (along x = span, between ribs) by b (chord, between spars), simply supported:
        N_x,cr = pi^2 / b^2 min_m [ D11 (m b/a)^2 + 2 (D12 + 2 D66) + D22 (a / (m b))^2 ]       (Whitney)
    shear  N_xy,cr = k_s pi^2 D_eff / b_s^2,  k_s = 5.35 + 4 (b_s / a_s)^2,  b_s = min(a, b), D_eff = (D11 D22^3)^(1/4)
    sandwich shear softening 1/N = 1/N_b + 1/(G_c d); interaction R_c + R_s^2 = 1. Returns the load factor."""
    D11, D22, D12, D66 = lam.D[0, 0], lam.D[1, 1], lam.D[0, 1], lam.D[2, 2]
    Nc = min(math.pi ** 2 / b ** 2 * (D11 * (m * b / a) ** 2 + 2 * (D12 + 2 * D66) + D22 * (a / (m * b)) ** 2) for m in range(1, 8))
    bs, as_ = min(a, b), max(a, b)
    Ns = (5.35 + 4 * (bs / as_) ** 2) * math.pi ** 2 * (D11 * D22 ** 3) ** 0.25 / bs ** 2
    if lam.Gc:
        dd = lam.core_t + lam.h_faces / 2
        soft = lambda N_: 1 / (1 / N_ + 1 / (lam.Gc * dd))
        Nc, Ns = soft(Nc), soft(Ns)
    Rc, Rs = max(-Nx, 0) / Nc, abs(Nxy) / Ns
    if Rs < 1e-12: return 1 / max(Rc, 1e-12), Nc, Ns
    return (-Rc + math.sqrt(Rc ** 2 + 4 * Rs ** 2)) / (2 * Rs ** 2), Nc, Ns


def cut_check(me, f, ef, eps, secs, y_s):
    """W3 + W4 at a mid-bay cut on the left wing (y_s > 0): beam theory and Bredt against the FE."""
    X = me.Xa
    e_s = np.array([me.tsw, 1, me.tdi]); e_s /= np.linalg.norm(e_s)
    e_c = np.array([1.0, 0, 0]) - e_s[0] * e_s; e_c /= np.linalg.norm(e_c)
    e_n = np.cross(e_s, e_c)
    ys = np.array([v[1][1] for v in ef.values() if v[0] != "ERIB" and v[1][1] > 0])
    y_row = ys[np.argmin(abs(ys - y_s))]
    strip = [(eid, v) for eid, v in ef.items() if v[0] != "ERIB" and abs(v[1][1] - y_row) < 1e-6]
    out_ = X[:, 1] > y_row
    C = np.array([v[1] for _, v in strip])
    rows = []
    for eid, (eset, c, n, t1, t2) in strip:
        ns = me.el[eset][me.eid[eset].index(eid)]
        P = X[np.array(ns[:4]) - 1]
        ds = 0.5 * (np.linalg.norm(P[1] - P[0]) + np.linalg.norm(P[2] - P[3]))
        lam = secs[sec_key(me, eset, eid)]["face"]
        Q11 = lam.Ex * 2 * lam.h / (1 - lam.nuxy * lam.nuxy * lam.Ey / lam.Ex)
        tang = (P[1] - P[0]) / np.linalg.norm(P[1] - P[0])           # along the perimeter
        rows.append(dict(eid=eid, kind=eset[:-1], c=c, ds=ds, w=ds * Q11, nu21=lam.nuxy * lam.Ey / lam.Ex, tang=tang,
                         Gt=lam.Gxy * 2 * lam.h))
    w = np.array([r_["w"] for r_ in rows]); EA = w.sum()
    c0 = (w[:, None] * C).sum(0) / EA
    a_ = (C - c0) @ e_c; b_ = (C - c0) @ e_n
    Fo = f[out_].sum(0); Mo = np.cross(X[out_] - c0, f[out_]).sum(0)
    # int sigma dA = Fo.e_s ; int sigma (r - c0) x e_s dA = Mo   (the cut face's outward normal is -e_s)
    lever = np.array([np.cross(C[i] - c0, e_s) for i in range(len(C))])
    A = np.zeros((4, 3)); rhs = np.r_[Fo @ e_s, Mo]
    basis = np.c_[np.ones(len(C)), a_, b_]
    A[0] = w @ basis
    for k in range(3): A[1 + k] = (w * lever[:, k]) @ basis
    p_ = np.linalg.lstsq(A, rhs, rcond=None)[0]
    beam = basis @ p_
    fe = np.array([eps[r_["eid"]]["ss"] + r_["nu21"] * eps[r_["eid"]]["cc"] for r_ in rows])
    up = [i for i, r_ in enumerate(rows) if r_["kind"] == "EUP"]; lo = [i for i, r_ in enumerate(rows) if r_["kind"] == "ELO"]
    iu = up[int(np.argmin(abs(a_[up])))]; il = lo[int(np.argmin(abs(a_[lo])))]
    N_fe = float(w @ fe); M_fe = (w * fe) @ lever
    # Bredt: torque about the span axis through c0; enclosed area of the mid-surface perimeter
    P2 = np.array([[(C[i] - c0) @ e_c, (C[i] - c0) @ e_n] for i in range(len(C))])
    order = np.argsort(np.arctan2(P2[:, 1], P2[:, 0]))
    Q = P2[order]; Aenc = 0.5 * abs(np.sum(Q[:, 0] * np.roll(Q[:, 1], -1) - np.roll(Q[:, 0], -1) * Q[:, 1]))
    T = float(Mo @ e_s)
    q_hand = T / (2 * Aenc)
    q_fe = {k: float(rows[i]["Gt"] * eps[rows[i]["eid"]]["sc"]) for k, i in (("upper", iu), ("lower", il))}
    rel = lambda i: float(fe[i] / beam[i] - 1) if abs(beam[i]) > 1e-9 else float("nan")
    return {"y_cut": float(y_row), "N_statics": float(Fo @ e_s), "N_fe": N_fe,
            "M_flap_statics": float(Mo @ e_c), "M_flap_fe": float(M_fe @ e_c), "M_chord_statics": float(Mo @ e_n), "M_chord_fe": float(M_fe @ e_n),
            "upper": {"beam": float(beam[iu]), "fe": float(fe[iu]), "diff": rel(iu)},
            "lower": {"beam": float(beam[il]), "fe": float(fe[il]), "diff": rel(il)},
            "EA": float(EA), "EI_flap": float((w * b_ ** 2).sum()), "A_enc": float(Aenc), "T": T, "q_bredt": q_hand, "q_fe_mid": q_fe}


def post(me, secs, foam, eps_allow, cases_f, names, lugs, beam_fb):
    ef = frames(me)
    B = read_dat(os.path.join(FEA, JOB + ".dat"))
    X = me.Xa
    lugP = X[np.array(lugs) - 1]
    near_lug = {eid for eid, v in ef.items() if np.min(np.linalg.norm(lugP - v[1], axis=1)) < LUG_CLEAR}
    res = {}
    rib_y = np.array(me.stations)
    for k_, name in enumerate(names):
        t = float(k_ + 1)
        o = {"applied_N": cases_f[name].sum(0).tolist(),
             "lug_reactions_N": [B[("total force", f"NLUG{i + 1}", t)][0].tolist() for i in range(len(lugs))], "strain": {}, "strain_clear": {}, "core": {}}
        o["reaction_N"] = np.sum(o["lug_reactions_N"], axis=0).tolist()
        emax = {}; eps_mid = {}; buck = []
        for eset in me.el:
            kind = eset if eset == "ERIB" else eset[:-1]
            Es = layer_rows({eset: B[("strains", eset, t)]}, eset, t)
            Ss = layer_rows({eset: B[("stresses", eset, t)]}, eset, t)
            for eid, pts in Es.items():
                fl = [E for L_, E in pts if L_ != 1]
                e_ = max(max(abs(v) for v in np.linalg.eigvalsh(E[:2, :2])) for E in fl)
                emax[eid] = (kind, e_)
                Em = np.mean(fl, axis=0)
                eps_mid[eid] = {"ss": Em[0, 0], "cc": Em[1, 1], "sc": 2 * Em[0, 1]}
            for eid, pts in Ss.items():
                c = ef[eid][1]
                tau = max(math.hypot(S[0, 2], S[1, 2]) for L_, S in pts if L_ == 1)
                cur = o["core"].get(kind)
                if cur is None or tau > cur["tau_max_Pa"]:
                    o["core"][kind] = {"tau_max_Pa": float(tau), "MS": foam["shear_strength"] / max(tau, 1e-9) - 1, "at": [round(float(v), 3) for v in c]}
        for kind in KINDS:
            for key, excl in (("strain", set()), ("strain_clear", near_lug)):
                cand = [(e_, eid) for eid, (k2, e_) in emax.items() if k2 == kind and eid not in excl]
                e_, eid = max(cand)
                o[key][kind] = {"eps_max": float(e_), "MS": eps_allow / e_ - 1, "at": [round(float(v), 3) for v in ef[eid][1]]}
        # W6 panel buckling, every box-skin element, panel between its two ribs
        for eid, (kind, _) in emax.items():
            if kind not in ("EUP", "ELO") or eid in near_lug: continue
            _, c, n, t1, t2 = ef[eid]
            ay = abs(c[1]); i = np.searchsorted(rib_y[rib_y >= 0], ay)
            ry = rib_y[rib_y >= 0]; a = (ry[min(i, len(ry) - 1)] - ry[max(i - 1, 0)]) * math.sqrt(1 + me.tsw ** 2 + me.tdi ** 2)
            bw = (me.xr - me.xf) * me.c
            lam = secs[f"{kind}{me.nud[eid]}"]["lam"]; e = eps_mid[eid]
            N = lam.A @ np.array([e["ss"], e["cc"], e["sc"]])
            lf, Nc, Ns = panel_buckling(lam, a, bw, N[0], N[1], N[2])
            buck.append((lf, eid, kind, float(N[0]), float(N[2]), Nc, Ns))
        buck.sort()
        lf, eid, kind, Nx, Nxy, Nc, Ns = buck[0]
        o["panel_buckling"] = {"factor": lf, "MS": lf - 1, "kind": kind, "at": [round(float(v), 3) for v in ef[eid][1]], "Nx": Nx, "Nxy": Nxy,
                               "Nx_cr": Nc, "Nxy_cr": Ns}
        wr = []                                                   # face wrinkling, each cap element with its own face
        for eid_, (k2, _) in emax.items():
            if k2 not in ("EUP", "ELO") or eid_ in near_lug: continue
            lam = secs[f"{k2}{me.nud[eid_]}"]["lam"]; sg = max(-eps_mid[eid_]["ss"], 0) * lam.Ex
            wr.append((lam.wrinkling_sigma() / max(sg, 1), sg, lam.wrinkling_sigma()))
        r_, sg, sw = min(wr)
        o["wrinkling"] = {"sigma_face_Pa": sg, "sigma_wr_Pa": sw, "MS": r_ - 1}
        # W3 / W4 at mid-bay cuts on the left wing
        mids = [0.5 * (a_ + b_) for a_, b_ in zip(rib_y[:-1], rib_y[1:]) if a_ >= me.y_lug - 1e-9]
        o["cuts"] = [cut_check(me, cases_f[name], ef, eps_mid, secs, ym) for ym in mids[:: 3]]
        # W5 tip deflection (mean of the tip ring) against the beam, both relative to the lug station
        tipz = {s: float(np.mean(B[("displacements", f"NTIP{s}", t)][:, 3])) for s in ("L", "R")}
        fb = beam_fb[name]
        dz_lug = np.interp(me.y_lug, fb["wing_y"][fb["wing_y"] >= 0], fb["wing_dz"][fb["wing_y"] >= 0])
        dz_lugR = np.interp(me.y_lug, -fb["wing_y"][fb["wing_y"] <= 0][::-1], fb["wing_dz"][fb["wing_y"] <= 0][::-1])
        o["tip_dz_mm"] = {"fe_L": 1e3 * tipz["L"], "fe_R": 1e3 * tipz["R"],
                          "beam_L": 1e3 * float(fb["wing_dz"][-1] - dz_lug), "beam_R": 1e3 * float(fb["wing_dz"][0] - dz_lugR)}
        o["_emax"] = {k: v[1] for k, v in emax.items()}
        res[name] = o
    return res, ef, near_lug


def hand_lugs(res, FIT, FUS):
    """W2: wing-side FE lug reactions against minus the fuselage-side hand split and FE."""
    out = {}
    for name, o in res.items():
        fe = np.array(o["lug_reactions_N"])
        hd = -np.array(FIT["cases"][name]["lug_reactions_N"]) if FIT else None
        fu = -np.array(FUS["hand_H"][name]["lug_fe_N"]) if FUS else None
        out[name] = {"wing_fe_N": fe.round(1).tolist(), "hand_N": None if hd is None else hd.round(1).tolist(),
                     "fuselage_fe_N": None if fu is None else fu.round(1).tolist(),
                     "max_wing_fe_N": float(np.linalg.norm(fe, axis=1).max()),
                     "max_hand_N": None if hd is None else float(np.linalg.norm(hd, axis=1).max()),
                     "max_fuselage_fe_N": None if fu is None else float(np.linalg.norm(fu, axis=1).max())}
    return out


def figure(me, res, ef, eps_allow):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LogNorm
    fig = plt.figure(figsize=(12, 7))
    gs = fig.add_gridspec(3, 2, width_ratios=[2.4, 1], hspace=0.55, wspace=0.22)
    plots = [("LC1 hover pull-up n=2", "EUP"), ("LC4 hard landing one main", "EUP"), (next(k for k in res if k.startswith("LC5")), "ELO")]
    for r_, (name, kind) in enumerate(plots):
        a_ = fig.add_subplot(gs[r_, 0])
        em = res[name]["_emax"]
        pts = np.array([(ef[e][1][1], ef[e][1][0], v) for e, v in em.items() if ef[e][0][:3] == kind[:3] and ef[e][0] != "ERIB"])
        sc = a_.scatter(pts[:, 0], pts[:, 1], c=np.clip(pts[:, 2], 1e-5, None) / eps_allow, s=5, marker="s", cmap="viridis", norm=LogNorm(0.02, 1.5))
        for s in me.stations: a_.axvline(s, color="0.8", lw=0.4, zorder=0)
        a_.set_title(f"{name}: {NAMES[kind]} strain / allowable (plan view, ultimate)", fontsize=9)
        a_.set_ylabel("x [m]"); a_.set_aspect("equal"); a_.invert_xaxis()
        if r_ == 2: a_.set_xlabel("y [m]  (left wing on the left)")
    fig.colorbar(sc, ax=fig.axes[:3], shrink=0.9, label="max principal strain / eps_allow", pad=0.01)
    a2 = fig.add_subplot(gs[:2, 1])
    names = list(res); wdt = 0.8 / len(KINDS)
    for k_, kind in enumerate(KINDS):
        a2.bar(np.arange(len(names)) + (k_ - (len(KINDS) - 1) / 2) * wdt, [res[n]["strain_clear"][kind]["MS"] for n in names], wdt, label=NAMES[kind])
    a2.bar(np.arange(len(names)) + 0.45, [res[n]["panel_buckling"]["MS"] for n in names], 0.08, color="k", label="panel buckling")
    a2.axhline(0, color="k", lw=0.8); a2.legend(fontsize=7); a2.set_yscale("symlog", linthresh=1)
    a2.set_xticks(range(len(names))); a2.set_xticklabels([n.split()[0] for n in names])
    a2.set_title("margins of safety at ultimate (outside the lug patches)", fontsize=9)
    a3 = fig.add_subplot(gs[2, 1])
    x = np.arange(len(names))
    a3.bar(x - 0.2, [res[n]["tip_dz_mm"]["beam_L"] for n in names], 0.4, label="beam")
    a3.bar(x + 0.2, [res[n]["tip_dz_mm"]["fe_L"] for n in names], 0.4, label="shell FE")
    a3.set_xticks(x); a3.set_xticklabels([n.split()[0] for n in names]); a3.legend(fontsize=7)
    a3.set_title("left tip deflection dz [mm], ultimate, rel. to the lugs", fontsize=9)
    plt.savefig(os.path.join(RESULTS, "fig_wing_shell.png"), dpi=150, bbox_inches="tight"); plt.close(fig)


def main(build_only=False, post_only=False):
    os.makedirs(FEA, exist_ok=True)
    ctx = tf.context()
    d = tf.merge(tf.DEFAULT, json.load(open(os.path.join(ROOT, "designs", "selected.json"))))
    FIT = json.load(open(os.path.join(RESULTS, "fittings.json")))
    FUS = json.load(open(os.path.join(RESULTS, "fuselage_shell_model.json")))
    y_lug = abs(FIT["lug_points"][0][1])
    secs, foam, eps_allow = sections(ctx, d)
    me = WingMesh(ctx, d, y_lug); me.d = d
    me.inset = secs["EUP"]["lam"].h / 2
    me.build()
    lugs = me.lug_nodes()
    r, fb = free_body(ctx, d)
    names = list(fb)
    cases_f, used = {}, {}
    for name in names:
        cases_f[name], used[name] = map_loads(me, fb[name])
        err = np.abs(cases_f[name].sum(0) - fb[name]["total_F"]).max()
        assert err < 1e-6 * max(1.0, np.abs(fb[name]["total_F"]).max()), (name, err)
    print(f"mesh: {len(me.X)} nodes, " + ", ".join(f"{k} {len(v)}" for k, v in me.el.items()) + f"; {len(me.stations)} rib stations")
    write_inp(me, secs, foam, cases_f, lugs, os.path.join(FEA, JOB + ".inp"))
    if build_only: return
    if not post_only:
        print(f"ccx: {run_ccx():.0f} s")
    res, ef, near_lug = post(me, secs, foam, eps_allow, cases_f, names, lugs, fb)
    W2 = hand_lugs(res, FIT, FUS)
    mass = {}
    for eset, els in me.el.items():
        kind = eset if eset == "ERIB" else eset[:-1]
        for ns, eid in zip(els, me.eid[eset]):
            P = me.Xa[np.array(ns[:4]) - 1]
            mass[kind] = mass.get(kind, 0.0) + 0.5 * np.linalg.norm(np.cross(P[2] - P[0], P[3] - P[1])) * secs[sec_key(me, eset, eid)]["areal"]
    mass = {k: float(v) for k, v in mass.items()}
    out = {"nodes": len(me.X), "elements": {k: len(v) for k, v in me.el.items()}, "stations_y": me.stations, "y_lug": y_lug,
           "rib_w45": RIB_W45, "eps_allow": eps_allow, "mass_kg": mass, "beam_wing_mass_kg": r["mass_breakdown"]["wing"],
           "beam_wing_buckling_MS": r["worst"]["wing"]["buckling"], "beam_wing_strain_MS": r["worst"]["wing"]["strain"],
           "beam_box_EI_flap": float(tf.wing_box(ctx["pm"], ctx["sz"], d["wing"]["n_ud_root"], d["wing"]).EIyy),
           "beam_box_depth_m": ctx["sz"]["wing"]["c"] * (ws.depth_at(ctx["sz"]["wing"]["airfoil"], ctx["p"]["wing"]["spar_front_xc"]) + ws.depth_at(ctx["sz"]["wing"]["airfoil"], ctx["p"]["wing"]["spar_rear_xc"])) / 2 - 0.004,
           "beam_tip_dz_mm_rel_centre": {n: r["cases"][n]["wing_tip_dz_mm"] for n in names},
           "load_patches": used, "W2_lugs": W2,
           "cases": {n: {k: v for k, v in o.items() if not k.startswith("_")} for n, o in res.items()}}
    with open(os.path.join(RESULTS, "wing_shell_model.json"), "w") as fh: json.dump(out, fh, indent=1, default=float)
    figure(me, res, ef, eps_allow)
    for n, o in res.items():
        print(n)
        print(f"   W1 reaction {np.round(o['reaction_N'], 1)}  applied {np.round(o['applied_N'], 1)}")
        w2 = W2[n]; print(f"   W2 lug max: wing FE {w2['max_wing_fe_N']:.0f}  hand {w2['max_hand_N']:.0f}  fuselage FE {w2['max_fuselage_fe_N']:.0f} N")
        for kind in KINDS:
            s_, c_ = o["strain"][kind], o["strain_clear"][kind]
            print(f"   {kind:5s} eps {s_['eps_max']*1e6:6.0f} ue MS {s_['MS']:+6.2f} at {s_['at']}   clear {c_['eps_max']*1e6:6.0f} MS {c_['MS']:+6.2f} at {c_['at']}")
        for kind, c_ in o["core"].items(): print(f"   core {kind:5s} tau {c_['tau_max_Pa']/1e3:6.0f} kPa MS {c_['MS']:+.2f}")
        pb = o["panel_buckling"]; print(f"   W6 panel buckling factor {pb['factor']:.2f} ({pb['kind']} at {pb['at']}, Nx {pb['Nx']:.0f} / {pb['Nx_cr']:.0f}, Nxy {pb['Nxy']:.0f} / {pb['Nxy_cr']:.0f} N/m); wrinkling MS {o['wrinkling']['MS']:+.2f}")
        for c_ in o["cuts"]:
            print(f"   W3 y={c_['y_cut']:.3f}: M_flap {c_['M_flap_statics']:.0f}/{c_['M_flap_fe']:.0f}  M_chord {c_['M_chord_statics']:.0f}/{c_['M_chord_fe']:.0f} N m; "
                  f"upper {c_['upper']['beam']*1e6:.0f}/{c_['upper']['fe']*1e6:.0f} ue lower {c_['lower']['beam']*1e6:.0f}/{c_['lower']['fe']*1e6:.0f}; "
                  f"W4 T {c_['T']:.0f} N m q {c_['q_bredt']:.0f} / FE {c_['q_fe_mid']['upper']:.0f}, {c_['q_fe_mid']['lower']:.0f} N/m")
        td = o["tip_dz_mm"]; print(f"   W5 tip dz L {td['fe_L']:.1f} (beam {td['beam_L']:.1f}) R {td['fe_R']:.1f} (beam {td['beam_R']:.1f}) mm")
    print("mass", {k: round(v, 2) for k, v in mass.items()}, "beam wing", round(r["mass_breakdown"]["wing"], 2))


if __name__ == "__main__":
    main(build_only="--build" in sys.argv, post_only="--post" in sys.argv)

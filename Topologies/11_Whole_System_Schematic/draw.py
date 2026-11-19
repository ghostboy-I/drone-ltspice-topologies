"""Drawn LTspice schematics: parts at real positions, connected with real wires.

A Sheet places symbols (rotation R0/R90/R180/R270, mirrors M0..M270), draws orthogonal wires, ground symbols and the
few labels a normal schematic uses (supply rails, signals that cross to another area). Three checks keep the drawing
honest:
  lint()      wire ends that touch nothing, pins that touch nothing, pins sitting on the middle of a wire
  verify()    runs LTspice -netlist on the written sheet and compares every pin of every part with the expected net
              (from the parts table), so a drawing error cannot hide
  render()    a PNG of the sheet (symbol graphics read from the LTspice .asy files) to look at the layout
"""
import os, re, subprocess, collections, math

LT = os.path.expanduser("~/.wine/drive_c/Program Files/ADI/LTspice/LTspice.exe")
SYM_DIR = os.path.expanduser("~/.wine/drive_c/users/elijah-callahan/AppData/Local/LTspice/lib/sym")
HERE = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------- symbols
class Symbol:
    def __init__(self, name):
        self.name = name
        path = None
        for d in (HERE,):
            if os.path.exists(os.path.join(d, name + ".asy")): path = os.path.join(d, name + ".asy")
        if path is None:
            for root, _, files in os.walk(SYM_DIR):
                for f in files:
                    if f.lower() == name.lower() + ".asy": path = os.path.join(root, f)
                if path: break
        if path is None: raise FileNotFoundError(name)
        raw = open(path, "rb").read()
        txt = raw.decode("utf-16le") if raw[1:2] == b"\x00" else raw.decode("latin1")
        self.pins, self.order, self.gfx, self.windows = {}, {}, [], {}
        cur = None
        for line in txt.replace("\r", "").split("\n"):
            p = line.split()
            if not p: continue
            if p[0] == "PIN": cur = (int(p[1]), int(p[2])); last = None
            elif p[0] == "PINATTR" and p[1] == "PinName" and cur:
                last = p[2] if len(p) > 2 else f"_NC{len(self.pins)}"; self.pins[last] = cur
            elif p[0] == "PINATTR" and p[1] == "SpiceOrder":
                if last is None: last = f"_NC{len(self.pins)}"; self.pins[last] = cur
                self.order[last] = int(p[2])
            elif p[0] in ("LINE", "RECTANGLE", "CIRCLE"): self.gfx.append((p[0], [int(v) for v in p[2:6]]))
            elif p[0] == "ARC": self.gfx.append(("ARC", [int(v) for v in p[2:10]]))
            elif p[0] == "WINDOW": self.windows[int(p[1])] = (int(p[2]), int(p[3]))
            elif p[0] == "TEXT" and len(p) > 5: self.gfx.append(("TEXT", [int(p[1]), int(p[2]), " ".join(p[5:])]))
        self.pin_by_order = [n for n, _ in sorted(self.order.items(), key=lambda kv: kv[1])]


_SYMS = {}
def sym(name):
    if name not in _SYMS: _SYMS[name] = Symbol(name)
    return _SYMS[name]


def xform(rot, x, y):
    """LTspice symbol orientation applied to a symbol-local point (y grows downward)."""
    m = rot.startswith("M"); a = int(rot[1:])
    if m: x = -x
    for _ in range(a // 90): x, y = -y, x
    return x, y


# ---------------------------------------------------------------- sheet
class Placed:
    def __init__(self, sh, ref, symname, x, y, rot, value, spice, expect, extra):
        self.ref, self.symname, self.x, self.y, self.rot = ref, symname, x, y, rot
        self.value, self.spice, self.expect, self.extra = value, spice, expect, extra
        self.s = sym(symname)

    def __getitem__(self, pin):
        px, py = self.s.pins[pin]; dx, dy = xform(self.rot, px, py)
        return (self.x + dx, self.y + dy)


class Sheet:
    def __init__(self, name, title=""):
        self.name, self.title = name, title
        self.parts, self.wires, self.flags, self.iopins, self.texts, self.rects, self.lines = [], [], [], [], [], [], []

    # -- placing
    def place(self, ref, symname, x, y, rot="R0", value="", spice="", expect=None, extra=()):
        """expect: {pin: net} the parts table says this pin must be on (checked by verify())."""
        p = Placed(self, ref, symname, x, y, rot, value, spice, expect or {}, extra)
        self.parts.append(p); return p

    def wire(self, *pts):
        pts = [tuple(p) for p in pts]
        for a, b in zip(pts, pts[1:]):
            if a == b: continue
            if a[0] != b[0] and a[1] != b[1]:          # make it orthogonal: horizontal first
                self.wires.append((a, (b[0], a[1]))); self.wires.append(((b[0], a[1]), b))
            else: self.wires.append((a, b))
        return pts[-1]

    def wire_v(self, a, b):
        """vertical first, then horizontal"""
        a, b = tuple(a), tuple(b)
        return self.wire(a, (a[0], b[1]), b)

    def flag(self, pt, net):
        self.flags.append((tuple(pt), net)); return pt

    def gnd(self, pt, drop=0):
        pt = tuple(pt)
        if drop: pt = self.wire(pt, (pt[0], pt[1] + drop))
        return self.flag(pt, "0")

    def rail(self, pt, net, rise=0):
        pt = tuple(pt)
        if rise: pt = self.wire(pt, (pt[0], pt[1] - rise))
        return self.flag(pt, net)

    def port(self, pt, net):
        self.flags.append((tuple(pt), net)); self.iopins.append(tuple(pt))

    def text(self, x, y, s, size=2, align="Left"):
        self.texts.append((x, y, align, size, s))

    def frame(self, x1, y1, x2, y2, title=None, size=3):
        self.rects.append((x1, y1, x2, y2))
        if title: self.text(x1 + 16, y1 + 40, ";" + title, size)

    def line(self, x1, y1, x2, y2):
        self.lines.append((x1, y1, x2, y2))

    def normalize(self):
        """Split every wire at each wire end, pin or label that lies on it (a drawn T is a junction), drop duplicates."""
        pts = set()
        for a, b in self.wires: pts.add(a); pts.add(b)
        for p in self.parts:
            for n in p.s.pins: pts.add(p[n])
        for pt, _ in self.flags: pts.add(pt)
        out = set()
        for a, b in self.wires:
            if a == b: continue
            if a[0] == b[0]:
                lo, hi = sorted((a[1], b[1])); cut = sorted({lo, hi} | {q[1] for q in pts if q[0] == a[0] and lo < q[1] < hi})
                segs = [((a[0], u), (a[0], v)) for u, v in zip(cut, cut[1:])]
            else:
                lo, hi = sorted((a[0], b[0])); cut = sorted({lo, hi} | {q[0] for q in pts if q[1] == a[1] and lo < q[0] < hi})
                segs = [((u, a[1]), (v, a[1])) for u, v in zip(cut, cut[1:])]
            out.update(segs)
        self.wires = sorted(out)

    # -- writing
    def write(self, path=None, directives=()):
        self.normalize()
        path = path or os.path.join(HERE, self.name + ".asc")
        xs = [0]; ys = [0]
        for p in self.parts: xs.append(p.x); ys.append(p.y)
        L = ["Version 4", f"SHEET 1 {max(xs) + 800} {max(ys) + 800}"]
        for (a, b) in self.wires: L.append(f"WIRE {a[0]} {a[1]} {b[0]} {b[1]}")
        for (pt, n) in self.flags: L.append(f"FLAG {pt[0]} {pt[1]} {n}")
        for pt in self.iopins: L.append(f"IOPIN {pt[0]} {pt[1]} BiDir")
        for p in self.parts:
            L.append(f"SYMBOL {p.symname} {p.x} {p.y} {p.rot}")
            if p.rot in ("R90", "R270") and p.symname in ("res", "cap", "ind", "diode", "schottky", "polcap"):
                L += ["WINDOW 0 0 56 VBottom 2", "WINDOW 3 32 56 VTop 2"]
            L.append(f"SYMATTR InstName {p.ref}")
            if p.value: L.append(f"SYMATTR Value {p.value.replace('µ', 'u')}")
            if p.spice: L.append(f"SYMATTR SpiceLine {p.spice.replace('µ', 'u')}")
            for e in p.extra: L.append(e)
        for (x1, y1, x2, y2) in self.rects: L.append(f"RECTANGLE Normal {x2} {y2} {x1} {y1} 2")
        for (x1, y1, x2, y2) in self.lines: L.append(f"LINE Normal {x1} {y1} {x2} {y2} 2")
        for (x, y, al, sz, s) in self.texts: L.append(f"TEXT {x} {y} {al} {sz} {s.replace('µ', 'u')}")
        y0 = max(ys) + 400
        for i, d in enumerate(directives): L.append(f"TEXT 0 {y0 + 32 * i} Left 2 {d.replace('µ', 'u')}")
        open(path, "w", newline="\r\n", encoding="latin-1", errors="replace").write("\n".join(L) + "\n")
        return path

    # -- checks
    def lint(self):
        """Geometry problems LTspice would not report: dangling wire ends, unconnected pins, pins on a wire's middle."""
        pts = collections.Counter()
        for a, b in self.wires: pts[a] += 1; pts[b] += 1
        pinpts = {}
        for p in self.parts:
            for n in p.s.pins: pinpts.setdefault(p[n], []).append(f"{p.ref}.{n}")
        flagpts = {pt for pt, _ in self.flags}
        def on_mid(pt):
            for a, b in self.wires:
                if pt in (a, b): continue
                if a[0] == b[0] == pt[0] and min(a[1], b[1]) < pt[1] < max(a[1], b[1]): return True
                if a[1] == b[1] == pt[1] and min(a[0], b[0]) < pt[0] < max(a[0], b[0]): return True
            return False
        problems = []
        for pt, c in pts.items():
            if c == 1 and pt not in pinpts and pt not in flagpts and not on_mid(pt):
                problems.append(f"dangling wire end at {pt}")
        for pt, names in pinpts.items():
            if on_mid(pt): problems.append(f"pin on the middle of a wire: {names} at {pt}")
            if len(names) > 1 and pts[pt] == 0 and pt not in flagpts: pass   # pins touching directly: allowed
        for p in self.parts:
            for n in p.s.pins:
                pt = p[n]
                if p.expect.get(n) is None: continue
                if pts[pt] == 0 and pt not in flagpts and len(pinpts[pt]) == 1 and not on_mid(pt):
                    problems.append(f"unconnected pin {p.ref}.{n} at {pt} (should be {p.expect[n]})")
        return problems

    def verify(self, path=None, ports_as_labels=True):
        """LTspice -netlist the sheet; check every expected pin->net. Returns list of errors (empty = drawing is right)."""
        path = path or os.path.join(HERE, self.name + ".asc")
        d, f = os.path.split(path)
        net = os.path.join(d, os.path.splitext(f)[0] + ".net")
        if os.path.exists(net): os.remove(net)
        subprocess.run(["wine", LT, "-netlist", f], cwd=d, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
        txt = open(net, "rb").read().decode("latin1")
        lines = [l for l in txt.replace("\r", "").split("\n")]
        # only the top level of this sheet (sub-circuits of blocks come after .subckt lines)
        top, depth = [], 0
        for l in lines:
            if l.lower().startswith(".subckt"): depth += 1; continue
            if l.lower().startswith(".ends"): depth -= 1; continue
            if depth == 0: top.append(l)
        elem = {}
        for l in top:
            if not l or l[0] in "*.;+": continue
            tok = l.split()
            name = tok[0]
            elem[re.sub(r"[^A-Za-z0-9_]", "", name).lower()] = tok[1:]
        errs = []
        id2exp, exp2id = {}, {}
        for p in self.parts:
            if not p.expect: continue
            key = p.ref.lower()
            cands = [k for k in elem if k == key or (len(k) == len(key) + 1 and k.endswith(key))]
            if not cands: errs.append(f"{p.ref}: not in LTspice netlist"); continue
            toks = elem[cands[0]]
            idx = {n: o - 1 for n, o in p.s.order.items()} if p.s.order else {n: i for i, n in enumerate(PIN_ORDER.get(p.symname, []))}
            for pin, i in sorted(idx.items(), key=lambda kv: kv[1]):
                if pin not in p.expect: continue
                got = toks[i]; want = p.expect[pin].rstrip("*") if isinstance(p.expect[pin], str) else p.expect[pin]
                want = "0" if want in ("0", "GND") else want
                # the LTspice net must map one-to-one onto the expected nets
                if got in id2exp and id2exp[got] != want:
                    errs.append(f"{p.ref}.{pin}: on LTspice net {got} together with {id2exp[got]}, but should be {want}")
                elif want in exp2id and exp2id[want] != got:
                    errs.append(f"{p.ref}.{pin}: should be on {want} but LTspice puts it on {got} (rest of {want} is on {exp2id[want]})")
                else:
                    id2exp[got] = want; exp2id[want] = got
                if re.match(r"^[A-Za-z_+]", got) and got.upper() != want.upper() and not got.startswith("N0") and got != "0" and want != "0":
                    if got in [n for _, n in self.flags]: errs.append(f"{p.ref}.{pin}: label {got} but table says {want}")
        return errs

    # -- picture
    def render(self, png, scale=0.25, region=None, title=None, dpi=100):
        import matplotlib; matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import Arc
        xs, ys = [], []
        for a, b in self.wires: xs += [a[0], b[0]]; ys += [a[1], b[1]]
        for p in self.parts:
            xs.append(p.x); ys.append(p.y)
            for kind, v in p.s.gfx:
                if kind in ("LINE", "RECTANGLE", "CIRCLE"):
                    for qx, qy in ((v[0], v[1]), (v[2], v[3])):
                        dx, dy = xform(p.rot, qx, qy); xs.append(p.x + dx); ys.append(p.y + dy)
        for r in self.rects: xs += [r[0], r[2]]; ys += [r[1], r[3]]
        for (x, y, al, sz, s) in self.texts:
            if not s.startswith("!"): xs.append(x); ys.append(y)
        x0, x1 = min(xs) - 100, max(xs) + 100; y0, y1 = min(ys) - 100, max(ys) + 100
        if region: x0, y0, x1, y1 = region
        W = (x1 - x0) / 100 * scale; H = (y1 - y0) / 100 * scale
        fig = plt.figure(figsize=(W, H), dpi=100); ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(x0, x1); ax.set_ylim(y1, y0)
        ax.axis("off"); lw = 0.9; fs = 4.2 * scale / 0.25
        for a, b in self.wires: ax.plot([a[0], b[0]], [a[1], b[1]], color="#1a5fb4", lw=lw)
        cnt = collections.Counter()
        for a, b in self.wires: cnt[a] += 1; cnt[b] += 1
        for p in self.parts:
            for n in p.s.pins: cnt[p[n]] += 1
        for pt, c in cnt.items():
            if c >= 3: ax.plot(*pt, "o", color="#1a5fb4", ms=2.2 * scale / 0.25)
        for r in self.rects: ax.add_patch(plt.Rectangle((r[0], r[1]), r[2] - r[0], r[3] - r[1], fill=False, ec="#999", lw=0.8, ls="--"))
        for (x, y, al, sz, s) in self.texts:
            if s.startswith("!"): continue
            ax.text(x, y, s.lstrip(";"), fontsize=fs * (1.35 if sz >= 3 else 1.0), va="center", ha="left", color="#333",
                    weight="bold" if sz >= 3 else "normal")
        for (pt, n) in self.flags:
            if n == "0":
                x, y = pt; ax.plot([x - 16, x + 16, x, x - 16], [y, y, y + 16, y], color="#000", lw=lw)
            else:
                ax.text(pt[0], pt[1] - 6, n, fontsize=fs, color="#a51d2d", ha="center", va="bottom", weight="bold")
                ax.plot(*pt, "s", color="#a51d2d", ms=1.5)
        for p in self.parts:
            T = lambda x, y: (p.x + xform(p.rot, x, y)[0], p.y + xform(p.rot, x, y)[1])
            for kind, v in p.s.gfx:
                if kind == "LINE":
                    (a, b), (c, d) = T(v[0], v[1]), T(v[2], v[3]); ax.plot([a, c], [b, d], color="#000", lw=lw)
                elif kind == "RECTANGLE":
                    pts = [T(v[0], v[1]), T(v[2], v[1]), T(v[2], v[3]), T(v[0], v[3]), T(v[0], v[1])]
                    ax.plot([q[0] for q in pts], [q[1] for q in pts], color="#000", lw=lw)
                elif kind == "CIRCLE":
                    (a, b), (c, d) = T(v[0], v[1]), T(v[2], v[3])
                    ax.add_patch(plt.Circle(((a + c) / 2, (b + d) / 2), abs(c - a) / 2, fill=False, ec="#000", lw=lw))
                elif kind == "ARC":
                    (a, b), (c, d) = T(v[0], v[1]), T(v[2], v[3]); cx, cy = (a + c) / 2, (b + d) / 2
                    (sx, sy), (ex, ey) = T(v[4], v[5]), T(v[6], v[7])
                    t1 = math.degrees(math.atan2(-(sy - cy), sx - cx)); t2 = math.degrees(math.atan2(-(ey - cy), ex - cx))
                    # y axis is inverted in the plot: draw counter-clockwise in screen coordinates
                    th = [math.radians(t1 + (t2 - t1) % 360 * k / 24) for k in range(25)]
                    rx, ry = abs(c - a) / 2, abs(d - b) / 2
                    ax.plot([cx + rx * math.cos(t) for t in th], [cy - ry * math.sin(t) for t in th], color="#000", lw=lw)
                elif kind == "TEXT":
                    a, b = T(v[0], v[1]); ax.text(a, b, v[2], fontsize=fs * 0.8, ha="center", va="center")
            wx, wy = p.s.windows.get(0, (24, 0)); tx, ty = T(wx, wy)
            ax.text(tx, ty, p.ref, fontsize=fs, color="#000", ha="left", va="center")
            if p.value and len(p.value) < 28:
                wx, wy = p.s.windows.get(3, (24, 48)); tx, ty = T(wx, wy)
                ax.text(tx, ty + 0, p.value, fontsize=fs * 0.85, color="#555", ha="left", va="center")
        if title: ax.text(x0 + 30, y0 + 40, title, fontsize=fs * 2, weight="bold")
        fig.savefig(png, dpi=dpi); plt.close(fig)

    def render_areas(self, prefix, dpi=250, min_w=1000, pad=40, page=(10.1, 7.2)):
        """One PNG per numbered frame (the dashed areas with a bold title); returns [(png, title)]."""
        out = []
        for i, (x1, y1, x2, y2) in enumerate(self.rects):
            if x2 - x1 < min_w: continue
            heads = [t for t in self.texts if t[3] >= 3 and x1 <= t[0] <= x2 and y1 <= t[1] <= y2]
            name = heads[0][4].lstrip(";").strip() if heads else f"area {i}"
            png = f"{prefix}_area{len(out) + 1}.png"
            scale = min(page[0] / ((x2 - x1 + 2 * pad) / 100), page[1] / ((y2 - y1 + 2 * pad) / 100))   # fill a landscape page
            self.render(png, scale=scale, region=(x1 - pad, y1 - pad, x2 + pad, y2 + pad), dpi=dpi); out.append((png, name))
        return out


# netlist pin order of LTspice's built-in symbols
PIN_ORDER = {"res": ["A", "B"], "cap": ["A", "B"], "ind": ["A", "B"], "polcap": ["A", "B"], "diode": ["A", "K"],
             "schottky": ["A", "K"], "zener": ["A", "K"], "voltage": ["+", "-"], "bv": ["+", "-"], "bi": ["+", "-"],
             "nmos": ["D", "G", "S"], "battery": ["+", "-"]}

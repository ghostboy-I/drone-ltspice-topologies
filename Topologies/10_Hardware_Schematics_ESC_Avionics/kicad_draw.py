"""Drawn KiCad 9 schematics: parts placed by hand, connected with real wires, one hierarchical sheet per block.

kicad_export.py writes each board as a parts list with a net label on every pin: correct, but not a drawing. This module
draws the same parts table as a schematic you can read:

  Project(name, outdir, title, parts)      the board: symbols resolved with kicad_export.Resolver (same symbols, pin
                                           numbers and footprints), one root sheet, one sub-sheet per block
  s = proj.sheet(file, name, title)        a sub-sheet (A3)
  u = s.place("U1", x, y, rot)             a symbol; u["VIN"] is the sheet position of the pin the parts table calls VIN
  s.two("R2", at, "D", first="1")          a two-pin part with pin `first` at `at`, body running down/up/left/right
  s.wire(a, b, c, ...)                     an orthogonal wire through the points
  s.gnd(pt) / s.rail(pt, "+12V")           power symbols (global nets), s.label / s.glabel local / global labels
  s.nc(pt)                                 no-connect flag

Coordinates are millimetres, y down, on KiCad's 1.27 mm grid. A pin sits only at a wire end; a wire that ends on the
middle of another wire is split there and gets a junction dot. Before anything is written, check():
  * lint: wire ends that touch nothing, pins that touch nothing, pins sitting on the middle of a wire
  * connectivity: the drawing's own nets (union of wires, pins, labels) must partition the pins exactly like the parts
    table does. Nets without a label get one automatically, with the parts-table name, on their longest wire.
kicad_check.py then repeats the net comparison with KiCad's own net list.
"""
import os, re, json, copy, uuid, collections
import sexpr as S
from sexpr import Sym
import kicad_export as K
from board import eng

G = 1.27
KLIB = K.KLIB


def P(x, y):
    return (round(x, 3), round(y, 3))


def on_grid(pt):
    return all(abs(v / G - round(v / G)) < 1e-3 for v in pt)


def xf(px, py, rot, mirror=None):
    """Library point (y up) -> sheet offset (y down) for a symbol at angle rot (CCW on screen), optional mirror."""
    x, y = px, py
    if mirror == "y": x = -x
    if mirror == "x": y = -y
    for _ in range((int(rot) % 360) // 90): x, y = -y, x
    return (round(x, 4), round(-y, 4) + 0.0)


DIRS = {"R": (1, 0), "L": (-1, 0), "D": (0, 1), "U": (0, -1)}


def eff(size=1.27, justify=None, hide=False, bold=False):
    f = [Sym("font"), [Sym("size"), size, size]] + ([[Sym("bold"), Sym("yes")]] if bold else [])
    e = [Sym("effects"), f]
    if justify: e.append([Sym("justify")] + [Sym(j) for j in justify.split()])
    if hide: e.append([Sym("hide"), Sym("yes")])
    return e


def drawn_symbol(name, spec, left, right, pitch=5.08, width=None):
    """A custom IC symbol for drawing: pins in the given order top to bottom (None = empty row), at `pitch` mm, so each
    pin has room for a part beside it. Same pin names and numbers as kicad_export.custom_symbol."""
    byn = {}
    for our, nums in spec["pins"].items():
        for n in nums: byn[n] = K.PIN_LABEL.get(our, our)
    rows = max(len(left), len(right))
    h = (rows - 1) * pitch + 2 * 2.54
    w = width or 25.4
    pins = []
    for side, lst in ((-1, left), (1, right)):
        for i, n in enumerate(lst):
            if n is None: continue
            y = (rows - 1) * pitch / 2 - i * pitch
            x = side * (w / 2 + 2.54)
            pins.append([Sym("pin"), Sym("no_connect" if byn[n] == "NC" else "passive"), Sym("line"),
                         [Sym("at"), round(x, 3), round(y, 3), 0 if side < 0 else 180], [Sym("length"), 2.54],
                         [Sym("name"), byn[n], eff()], [Sym("number"), n, eff()]])
    missing = set(byn) - set(left) - set(right)
    if missing: raise ValueError(f"{name}: pins not placed: {sorted(missing)}")
    body = [Sym("rectangle"), [Sym("start"), -w / 2, h / 2], [Sym("end"), w / 2, -h / 2],
            [Sym("stroke"), [Sym("width"), 0.254], [Sym("type"), Sym("default")]], [Sym("fill"), [Sym("type"), Sym("background")]]]
    prop = lambda k, v, y, hide=False: [Sym("property"), k, v, [Sym("at"), 0, y, 0], eff(hide=hide)]
    return [Sym("symbol"), name, [Sym("pin_names"), [Sym("offset"), 1.016]], [Sym("exclude_from_sim"), Sym("no")],
            [Sym("in_bom"), Sym("yes")], [Sym("on_board"), Sym("yes")],
            prop("Reference", "U", h / 2 + 2.54), prop("Value", name, -h / 2 - 2.54), prop("Footprint", "", 0, True),
            prop("Datasheet", "", 0, True), prop("Description", spec["desc"], 0, True),
            [Sym("symbol"), f"{name}_0_1", body], [Sym("symbol"), f"{name}_1_1"] + pins]


class Inst:
    """A placed symbol. inst[our_pin] -> sheet point of that pin (first package pin if it has several)."""
    def __init__(self, sh, ref, x, y, rot=0, mirror=None):
        self.sh, self.ref, self.x, self.y, self.rot, self.mirror = sh, ref, x, y, rot, mirror
        self.part, self.key, self.sym, self.pmap, self.pins = sh.proj.parts[ref]
        self.bynum = {num: (nm, px, py, a) for nm, num, px, py, a in self.pins}
        self.uuid = sh.proj.U()

    def at(self, num):
        nm, px, py, a = self.bynum[num]
        dx, dy = xf(px, py, self.rot, self.mirror)
        return P(self.x + dx, self.y + dy)

    def __getitem__(self, our):
        return self.at(self.pmap[our][0])

    def all(self, our):
        return [self.at(n) for n in self.pmap[our]]

    def out(self, our):
        """Unit vector pointing away from the body at that pin (the way a wire should leave)."""
        nm, px, py, a = self.bynum[self.pmap[our][0]]
        d = {0: (-1, 0), 90: (0, -1), 180: (1, 0), 270: (0, 1)}[int(a) % 360]   # library: pin angle points into the body
        return tuple(int(round(v)) for v in xf(d[0], d[1], self.rot, self.mirror))

    def pin_points(self):
        return {num: self.at(num) for num in self.bynum}


class KSheet:
    def __init__(self, proj, file, name, title, paper="A3"):
        self.proj, self.file, self.name, self.title, self.paper = proj, file, name, title, paper
        self.uuid = proj.U()            # the sheet symbol's UUID in the root sheet (instance paths use it)
        self.file_uuid = proj.U()
        self.insts, self.wires, self.labels, self.power, self.ncs, self.texts, self.rects = {}, [], [], [], [], [], []
        self.junctions = []

    # ------------------------------------------------------------------ placing
    def place(self, ref, x, y, rot=0, mirror=None, ref_at=None, val_at=None, hide_value=False):
        if ref in self.proj.placed: raise ValueError(f"{ref} placed twice ({self.proj.placed[ref]} and {self.name})")
        i = Inst(self, ref, round(x, 3), round(y, 3), rot, mirror)
        if not on_grid((i.x, i.y)): raise ValueError(f"{ref} at {(x, y)} is off the 1.27 mm grid")
        i.ref_at, i.val_at, i.hide_value = ref_at, val_at, hide_value
        self.insts[ref] = i; self.proj.placed[ref] = self.name
        return i

    def two(self, ref, at, d="D", first=None, **kw):
        """Two-pin part with pin `first` (parts-table name, default the first one) at `at`, body running in direction d."""
        _, key, sym, pmap, pins = self.proj.parts[ref]
        names = list(pmap)
        first = first or names[0]
        other = [n for n in names if n != first][0]
        n1, n2 = pmap[first][0], pmap[other][0]
        lib = {num: (px, py) for _, num, px, py, _ in pins}
        want = DIRS[d]
        for rot in (0, 90, 180, 270):
            a = xf(*lib[n1], rot); b = xf(*lib[n2], rot)
            v = (b[0] - a[0], b[1] - a[1])
            if abs(v[0]) > 1e-6 and v[1] == 0 and (v[0] > 0) == (want[0] > 0) and want[1] == 0 or \
               abs(v[1]) > 1e-6 and v[0] == 0 and (v[1] > 0) == (want[1] > 0) and want[0] == 0:
                inst = self.place(ref, at[0] - a[0], at[1] - a[1], rot, **kw)
                inst.a, inst.b = inst[first], inst[other]
                return inst
        raise ValueError(f"{ref}: no rotation gives direction {d}")

    def wire(self, *pts):
        pts = [P(*p) for p in pts]
        for a, b in zip(pts, pts[1:]):
            if a == b: continue
            if a[0] != b[0] and a[1] != b[1]: raise ValueError(f"{self.name}: diagonal wire {a} -> {b}")
            if not (on_grid(a) and on_grid(b)): raise ValueError(f"{self.name}: wire off grid {a} -> {b}")
            self.wires.append((a, b))

    def _power(self, pt, lib, net, body_dir, hide_value=False):
        self.power.append(dict(pt=P(*pt), lib=lib, net=net, dir=body_dir, hide=hide_value))

    def gnd(self, pt, d="D", hide_value=True):
        self._power(pt, "GND", "GND", d, hide_value)

    def rail(self, pt, net, d="U"):
        self._power(pt, net, net, d)

    def flag(self, pt, d="D"):
        """PWR_FLAG: tells the ERC that this net is driven (the board's supplies come from connectors/regulators)."""
        self._power(pt, "PWR_FLAG", None, d, hide_value=True)

    def label(self, pt, net, d="R"):
        self.labels.append(dict(pt=P(*pt), net=net, kind="label", dir=d))

    def glabel(self, pt, net, d="R", shape="bidirectional"):
        self.labels.append(dict(pt=P(*pt), net=net, kind="global_label", dir=d, shape=shape))

    def nc(self, pt):
        self.ncs.append(P(*pt))

    def text(self, x, y, s, size=1.5, bold=False):
        self.texts.append((P(x, y), s, size, bold))

    def rect(self, x1, y1, x2, y2):
        self.rects.append((P(x1, y1), P(x2, y2)))

    # ------------------------------------------------------------------ geometry helpers
    def pin_points(self):
        """[(point, ref, pin number)] of every symbol pin on the sheet."""
        out = []
        for r, i in self.insts.items():
            for num, pt in i.pin_points().items(): out.append((pt, r, num))
        return out

    @staticmethod
    def _inside(pt, w):
        (x1, y1), (x2, y2) = w
        if x1 == x2 == pt[0]: return min(y1, y2) < pt[1] < max(y1, y2)
        if y1 == y2 == pt[1]: return min(x1, x2) < pt[0] < max(x1, x2)
        return False

    def finish(self):
        """Split wires at T joins, add junctions, lint. Returns a list of problems."""
        probs = []
        # split at wire ends, pins and power-symbol pins that land on the middle of a wire (KiCad connects them there);
        # an accidental contact is caught by the net comparison with the parts table
        changed = True
        taps = {pt for pt, *_ in self.pin_points()} | {p["pt"] for p in self.power}
        while changed:
            changed = False
            ends = {p for w in self.wires for p in w} | taps
            for k, w in enumerate(self.wires):
                hit = [p for p in ends if self._inside(p, w)]
                if hit:
                    p = hit[0]; self.wires[k:k + 1] = [(w[0], p), (p, w[1])]; changed = True; break
        pins = self.pin_points()
        ppts = collections.Counter(pt for pt, *_ in pins)
        pwr = collections.Counter(p["pt"] for p in self.power)
        lab = {l["pt"] for l in self.labels}
        ncs = set(self.ncs)
        endc = collections.Counter(p for w in self.wires for p in w)
        for pt, r, num in pins:
            touched = endc[pt] or ppts[pt] > 1 or pwr[pt] or pt in lab or pt in ncs
            if not touched and not self._stacked(r, num): probs.append(f"{self.name}: pin {r}.{num} at {pt} is not connected")
        for p, c in endc.items():
            if c == 1 and not (ppts[p] or pwr[p] or p in lab or p in ncs):
                probs.append(f"{self.name}: wire end at {p} touches nothing")
        for l in self.labels:
            if not (endc[l["pt"]] or ppts[l["pt"]] or any(self._inside(l["pt"], w) for w in self.wires)):
                probs.append(f"{self.name}: label {l['net']} at {l['pt']} is not on a wire or pin")
        for pt in set(endc) | set(ppts):
            n = endc[pt] + ppts[pt] + pwr[pt]
            if n >= 3: self.junctions.append(pt)
        # parts overlapping: two symbol origins on the same point
        org = collections.Counter((i.x, i.y) for i in self.insts.values())
        probs += [f"{self.name}: two symbols at {p}" for p, c in org.items() if c > 1]
        return probs

    def translate(self, dx, dy):
        """Move the whole drawing (after check, before write) so it sits at the top-left of a smaller page."""
        T = lambda p: P(p[0] + dx, p[1] + dy)
        for i in self.insts.values():
            i.x, i.y = round(i.x + dx, 3), round(i.y + dy, 3)
            if i.ref_at: i.ref_at = (i.ref_at[0] + dx, i.ref_at[1] + dy, i.ref_at[2])
            if i.val_at: i.val_at = (i.val_at[0] + dx, i.val_at[1] + dy, i.val_at[2])
        self.wires = [(T(a), T(b)) for a, b in self.wires]
        self.junctions = [T(p) for p in self.junctions]
        self.ncs = [T(p) for p in self.ncs]
        for d in self.labels + self.power: d["pt"] = T(d["pt"])
        self.texts = [(t[0] if t[0][1] <= 31 else T(t[0]),) + t[1:] for t in self.texts]      # header lines stay put
        self.rects = [(T(a), T(b)) for a, b in self.rects]

    def _stacked(self, ref, num):
        """A pin stacked on another pin of the same symbol (e.g. LT3045 IN 1/2) is connected through it."""
        i = self.insts[ref]; pt = i.at(num)
        return any(n != num and i.at(n) == pt for n in i.bynum)


class Project:
    def __init__(self, name, outdir, title, parts, custom=None):
        self.name, self.outdir, self.title = name, outdir, title
        self._ns, self._cnt = uuid.uuid5(uuid.NAMESPACE_URL, "drone-ltspice-topologies/drawn/" + name), 0
        self.prefix = f"{name}_custom"
        self.R = K.Resolver(self.prefix)
        for nm, (left, right, pitch, width) in (custom or {}).items():           # drawn variants of the generated ICs
            key = f"{self.prefix}:{nm}"
            self.R.cache[key] = drawn_symbol(nm, K.CUSTOM[nm], left, right, pitch, width); self.R.cache[key][1] = key
        self.root_uuid = self.U()
        self.sheets, self.placed, self.parts = [], {}, {}
        self.expected = {}
        for p in parts:
            if p.sim: continue
            key, sym, pmap = self.R.resolve(p)
            if "CP_" in (p.fp or ""):                                      # polarised: pad 1 = +, same pin numbers
                key, sym = self.R.get("Device", "C_Polarized")
            pins = K.pin_list(sym)
            for r in p.refs():
                self.parts[r] = (p, key, sym, pmap, pins)
                for our, nums in pmap.items():
                    if our in p.nets:
                        for n in nums: self.expected.setdefault("GND" if p.nets_for(r)[our] == "0" else p.nets_for(r)[our], set()).add((r, n))

    def U(self):
        self._cnt += 1
        return str(uuid.uuid5(self._ns, str(self._cnt)))

    def sheet(self, file, name, title, paper="A3"):
        s = KSheet(self, file, name, title, paper); self.sheets.append(s); return s

    # ------------------------------------------------------------------ connectivity (the drawing's own net list)
    def nets(self):
        """Union-find over every sheet: wires, pins, labels (local per sheet, global and power across sheets)."""
        parent = {}
        def f(a):
            parent.setdefault(a, a)
            while parent[a] != a: parent[a] = parent[parent[a]]; a = parent[a]
            return a
        def u(a, b): parent[f(a)] = f(b)
        for s in self.sheets:
            pt = lambda p: ("pt", s.name, p)
            for a, b in s.wires: u(pt(a), pt(b))
            for p, r, num in s.pin_points(): u(("pin", r, num), pt(p))
            for p in s.power:
                if p["net"]: u(pt(p["pt"]), ("net", p["net"]))
            for l in s.labels:
                key = ("net", l["net"]) if l["kind"] == "global_label" else ("lnet", s.name, l["net"])
                where = [w for w in s.wires if l["pt"] in w or KSheet._inside(l["pt"], w)]
                u(pt(where[0][0]) if where else pt(l["pt"]), key)
        groups = collections.defaultdict(set)
        for k in list(parent):
            if k[0] == "pin": groups[f(k)].add((k[1], k[2]))
        return [g for g in groups.values()]

    def check(self):
        probs = []
        for s in self.sheets: probs += s.finish()
        missing = sorted(set(self.parts) - set(self.placed))
        if missing: probs.append(f"parts not drawn: {missing}")
        got = self.nets()
        exp_by_pin = {pin: n for n, pins in self.expected.items() for pin in pins}
        for g in got:
            names = {exp_by_pin.get(p) for p in g}
            used = {n for n in names if n}
            if len(used) > 1: probs.append(f"short: drawing joins nets {sorted(used)} via {sorted(g)[:6]}")
            elif used and self.expected[used.pop()] != {p for p in g if p in exp_by_pin}:
                n = exp_by_pin[next(p for p in g if p in exp_by_pin)]
                miss = sorted(self.expected[n] - g)
                probs.append(f"open: net {n} is split, this piece lacks {miss[:6]}")
        return probs

    def autolabel(self):
        """Give every net that has no label/power symbol its parts-table name, on its longest wire segment."""
        exp_by_pin = {pin: n for n, pins in self.expected.items() for pin in pins}
        named = set()
        for s in self.sheets:
            named |= {l["net"] for l in s.labels} | {p["net"] for p in s.power if p["net"]}
        for s in self.sheets:
            pins_at = collections.defaultdict(set)
            for p, r, num in s.pin_points(): pins_at[p].add((r, num))
            # local clusters of this sheet: wires + pins
            parent = {}
            def f(a):
                parent.setdefault(a, a)
                while parent[a] != a: parent[a] = parent[parent[a]]; a = parent[a]
                return a
            for a, b in s.wires: parent[f(a)] = f(b)
            clusters = collections.defaultdict(list)
            for w in s.wires: clusters[f(w[0])].append(w)
            for root, ws in clusters.items():
                pts = {p for w in ws for p in w}
                pins = {x for p in pts for x in pins_at.get(p, ())}
                nets = {exp_by_pin[x] for x in pins if x in exp_by_pin}
                if len(nets) != 1: continue
                n = nets.pop()
                if n in named: continue
                need = len(n) * 0.95 + 1.5
                hz = sorted([w for w in ws if w[0][1] == w[1][1]], key=lambda w: -abs(w[1][0] - w[0][0]))
                vt = sorted([w for w in ws if w[0][0] == w[1][0]], key=lambda w: -abs(w[1][1] - w[0][1]))
                if hz and abs(hz[0][1][0] - hz[0][0][0]) >= need:
                    w = hz[0]; x = min(w[0][0], w[1][0]); s.label(P(x + G, w[0][1]), n, "R")
                elif vt and abs(vt[0][1][1] - vt[0][0][1]) >= need:
                    w = vt[0]; y = max(w[0][1], w[1][1]); s.label(P(w[0][0], y - G), n, "U")
                else: continue
                named.add(n)

    # ------------------------------------------------------------------ writing
    def write(self, comments=()):
        os.makedirs(self.outdir, exist_ok=True)
        self.autolabel()
        pw = S.library(f"{KLIB}/power.kicad_sym")
        npwr = 0
        total = len(self.sheets) + 1
        for page, s in enumerate(self.sheets, 2):
            if getattr(s, "shift", None): s.translate(*s.shift); s.shift = None
            items, used = [], {}
            path = f"/{self.root_uuid}/{s.uuid}"
            for r, i in s.insts.items():
                used[i.key] = self.R.cache[i.key]
                items.append(self._symbol(i, path))
            for p in s.power:
                key = f"power:{p['lib']}"
                if key not in used: used[key] = K.flatten(pw, p["lib"], key)
                npwr += 1
                items.append(self._power_sym(p, key, used[key], path, npwr))
            for a, b in s.wires:
                items.append([Sym("wire"), [Sym("pts"), [Sym("xy"), a[0], a[1]], [Sym("xy"), b[0], b[1]]],
                              [Sym("stroke"), [Sym("width"), 0], [Sym("type"), Sym("default")]], [Sym("uuid"), self.U()]])
            for pt in sorted(set(s.junctions)):
                items.append([Sym("junction"), [Sym("at"), pt[0], pt[1]], [Sym("diameter"), 0], [Sym("color"), 0, 0, 0, 0], [Sym("uuid"), self.U()]])
            for pt in s.ncs:
                items.append([Sym("no_connect"), [Sym("at"), pt[0], pt[1]], [Sym("uuid"), self.U()]])
            for l in s.labels:
                ang = {"R": 0, "U": 90, "L": 180, "D": 270}[l["dir"]]
                if l["kind"] == "label":
                    j = "left bottom" if ang in (0, 90) else "right bottom"
                    items.append([Sym("label"), l["net"], [Sym("at"), l["pt"][0], l["pt"][1], ang], eff(justify=j), [Sym("uuid"), self.U()]])
                else:
                    j = "left" if ang in (0, 90) else "right"
                    items.append([Sym("global_label"), l["net"], [Sym("shape"), Sym(l["shape"])], [Sym("at"), l["pt"][0], l["pt"][1], ang],
                                  [Sym("fields_autoplaced"), Sym("yes")], eff(justify=j), [Sym("uuid"), self.U()],
                                  [Sym("property"), "Intersheetrefs", "${INTERSHEET_REFS}", [Sym("at"), l["pt"][0], l["pt"][1], 0],
                                   eff(size=1.0, justify=j, hide=True)]])
            for pt, txt, size, bold in s.texts:
                items.append([Sym("text"), txt, [Sym("exclude_from_sim"), Sym("no")], [Sym("at"), pt[0], pt[1], 0],
                              eff(size=size, justify="left", bold=bold), [Sym("uuid"), self.U()]])
            for a, b in s.rects:
                items.append([Sym("rectangle"), [Sym("start"), a[0], a[1]], [Sym("end"), b[0], b[1]],
                              [Sym("stroke"), [Sym("width"), 0.2], [Sym("type"), Sym("dash")]], [Sym("fill"), [Sym("type"), Sym("none")]],
                              [Sym("uuid"), self.U()]])
            sch = [Sym("kicad_sch"), [Sym("version"), Sym("20250114")], [Sym("generator"), "eeschema"], [Sym("generator_version"), "9.0"],
                   [Sym("uuid"), s.file_uuid], [Sym("paper"), s.paper], self._title_block(s.title, page, total, comments),
                   [Sym("lib_symbols")] + list(used.values())] + items + [[Sym("embedded_fonts"), Sym("no")]]
            open(os.path.join(self.outdir, s.file), "w").write(S.dump(sch) + "\n")
        self._write_root(comments, total)
        self._write_libs()

    def _title_block(self, title, page, total, comments):
        tb = [Sym("title_block"), [Sym("title"), title.split(":")[0].strip()], [Sym("rev"), "A"], [Sym("company"), self.title]]
        for k, c in enumerate(comments[:4], 1): tb.append([Sym("comment"), k, c])
        return tb

    def _symbol(self, i, path):
        p = i.part
        val = part_value(p)
        fp = f"{K.FP_LIB}:{K.fp_name(p.fp)}"
        pts = list(i.pin_points().values())
        xs, ys = [q[0] for q in pts], [q[1] for q in pts]
        two = len(i.bynum) == 2 or (len(set(pts)) == 2)
        if i.ref_at: rat = i.ref_at
        elif i.ref.startswith("J") and not i.mirror and min(xs) < i.x:   # connector, pins on the left: text right of the body
            rat = (i.x + 3.81, min(ys), "left")
        elif i.ref.startswith("J"):                       # connector: text above the body
            rat = (i.x, min(ys) - 2.54, "center")
        elif i.ref.startswith("Q"):                       # FET: text above-left, clear of the gate wire
            rat = (i.x - 2.54, i.y - 5.08, "right")
        elif two and max(xs) - min(xs) < 0.01:          # vertical two-pin: text on the right
            rat = (i.x + 2.54, i.y - 1.27, "left")
        elif two:                                       # horizontal two-pin: "R6 30.1k" on one line above the body
            rat = (i.x - 0.635, i.y - 2.794, "right")
        else:
            rat = (i.x, min(ys) - 6.35, "center") if max(ys) - min(ys) > 0 else (i.x, i.y - 7.62, "center")
        if i.val_at: vat = i.val_at
        elif i.ref.startswith("J") and not i.mirror and min(xs) < i.x: vat = (i.x + 3.81, min(ys) + 2.54, "left")
        elif i.ref.startswith("J"): vat = (i.x, max(ys) + 2.54, "center")
        elif i.ref.startswith("Q"): vat = (i.x - 2.54, i.y - 2.54, "right")
        elif two and max(xs) - min(xs) < 0.01: vat = (i.x + 2.54, i.y + 1.27, "left")
        elif two: vat = (i.x + 0.635, i.y - 2.794, "left")
        else: vat = (rat[0], rat[1] + 2.54, "center") if rat[1] < i.y else (i.x, max(ys) + 3.81, "center")
        just = lambda j: None if j == "center" else j
        props = [("Reference", i.ref, rat, False), ("Value", val, vat, i.hide_value), ("Footprint", fp, (i.x, i.y, "center"), True),
                 ("Datasheet", "", (i.x, i.y, "center"), True), ("Description", p.desc, (i.x, i.y, "center"), True),
                 ("MPN/Spec", p.pn, (i.x, i.y, "center"), True), ("Rating", p.rating, (i.x, i.y, "center"), True)]
        node = [Sym("symbol"), [Sym("lib_id"), i.key], [Sym("at"), i.x, i.y, i.rot]]
        if i.mirror: node.append([Sym("mirror"), Sym(i.mirror)])
        node += [[Sym("unit"), 1], [Sym("exclude_from_sim"), Sym("no")], [Sym("in_bom"), Sym("yes")], [Sym("on_board"), Sym("yes")],
                 [Sym("dnp"), Sym("yes" if "DNP" in p.pn else "no")], [Sym("uuid"), i.uuid]]
        fa = 90 if int(i.rot) % 180 == 90 else 0          # KiCad draws a field at (its angle + the symbol's): keep text horizontal
        flip = (int(i.rot) + fa) % 360 == 180            # KiCad mirrors the justification of text drawn at 180 degrees
        for k, v, (x, y, j), hide in props:
            if flip and j in ("left", "right"): j = "right" if j == "left" else "left"
            node.append([Sym("property"), k, v, [Sym("at"), round(x, 3), round(y, 3), fa], eff(justify=just(j), hide=hide)])
        for num in i.bynum: node.append([Sym("pin"), num, [Sym("uuid"), self.U()]])
        node.append([Sym("instances"), [Sym("project"), self.name, [Sym("path"), path, [Sym("reference"), i.ref], [Sym("unit"), 1]]]])
        return node

    def _power_sym(self, p, key, sym, path, n):
        body = {"GND": (0, -1), "PWR_FLAG": (0, 1)}.get(p["lib"], (0, 1))      # library direction of the body from the pin
        rot = next(r for r in (0, 90, 180, 270) if tuple(round(v) for v in xf(*body, r)) == DIRS[p["dir"]])
        x, y = p["pt"]
        ref = f"#{'FLG' if p['lib'] == 'PWR_FLAG' else 'PWR'}{n:03d}"
        off = xf(0, -3.81 if p["lib"] == "GND" else 3.81, rot)
        vx, vy = x + off[0] * (1.0 if p["dir"] in "UD" else 1.6), y + off[1]
        return [Sym("symbol"), [Sym("lib_id"), key], [Sym("at"), x, y, rot], [Sym("unit"), 1], [Sym("exclude_from_sim"), Sym("no")],
                [Sym("in_bom"), Sym("yes")], [Sym("on_board"), Sym("yes")], [Sym("dnp"), Sym("no")], [Sym("uuid"), self.U()],
                [Sym("property"), "Reference", ref, [Sym("at"), x, y, 0], eff(hide=True)],
                [Sym("property"), "Value", p["lib"], [Sym("at"), round(vx, 3), round(vy, 3), 0], eff(hide=p["hide"])],
                [Sym("property"), "Footprint", "", [Sym("at"), x, y, 0], eff(hide=True)],
                [Sym("property"), "Datasheet", "", [Sym("at"), x, y, 0], eff(hide=True)],
                [Sym("property"), "Description", "", [Sym("at"), x, y, 0], eff(hide=True)],
                [Sym("pin"), "1", [Sym("uuid"), self.U()]],
                [Sym("instances"), [Sym("project"), self.name, [Sym("path"), path, [Sym("reference"), ref], [Sym("unit"), 1]]]]]

    def _write_root(self, comments, total):
        items = []
        x0, y0, w, h, gap = 20.32, 38.1, 60.96, 27.94, 7.62
        for k, s in enumerate(self.sheets):
            x = x0 + (k % 3) * (w + gap * 2); y = y0 + (k // 3) * (h + gap * 2)
            items.append([Sym("sheet"), [Sym("at"), x, y], [Sym("size"), w, h], [Sym("exclude_from_sim"), Sym("no")],
                          [Sym("in_bom"), Sym("yes")], [Sym("on_board"), Sym("yes")], [Sym("dnp"), Sym("no")],
                          [Sym("fields_autoplaced"), Sym("yes")],
                          [Sym("stroke"), [Sym("width"), 0.1524], [Sym("type"), Sym("solid")]], [Sym("fill"), [Sym("color"), 0, 0, 0, 0.0]],
                          [Sym("uuid"), s.uuid],
                          [Sym("property"), "Sheetname", s.name, [Sym("at"), x, round(y - 0.7, 3), 0], eff(justify="left bottom")],
                          [Sym("property"), "Sheetfile", s.file, [Sym("at"), x, round(y + h + 0.6, 3), 0], eff(justify="left top")],
                          [Sym("instances"), [Sym("project"), self.name, [Sym("path"), f"/{self.root_uuid}", [Sym("page"), str(k + 2)]]]]])
            for li, line in enumerate(_wrap(s.title, 34)[:6]):
                items.append([Sym("text"), line, [Sym("exclude_from_sim"), Sym("no")], [Sym("at"), x + 2.54, round(y + 5.08 + li * 3.3, 3), 0],
                              eff(size=1.6, justify="left"), [Sym("uuid"), self.U()]])
        rows = (len(self.sheets) + 2) // 3
        ny = 120 if rows <= 2 else y0 + rows * (h + gap * 2) + 4          # notes below the last row of sheet boxes
        for li, line in enumerate(self.root_notes):
            items.append([Sym("text"), line, [Sym("exclude_from_sim"), Sym("no")], [Sym("at"), 25.4, round(ny + li * 4.2, 3), 0],
                          eff(size=1.8, justify="left", bold=li == 0), [Sym("uuid"), self.U()]])
        sch = [Sym("kicad_sch"), [Sym("version"), Sym("20250114")], [Sym("generator"), "eeschema"], [Sym("generator_version"), "9.0"],
               [Sym("uuid"), self.root_uuid], [Sym("paper"), "A4"], self._title_block(self.title, 1, total, comments),
               [Sym("lib_symbols")]] + items + [[Sym("sheet_instances"), [Sym("path"), "/", [Sym("page"), "1"]]], [Sym("embedded_fonts"), Sym("no")]]
        open(os.path.join(self.outdir, f"{self.name}.kicad_sch"), "w").write(S.dump(sch) + "\n")
        pro_path = os.path.join(self.outdir, f"{self.name}.kicad_pro")
        pro = json.load(open(pro_path)) if os.path.exists(pro_path) else {"meta": {"filename": f"{self.name}.kicad_pro", "version": 3}}
        pro["sheets"] = [[self.root_uuid, "Root"]] + [[s.uuid, s.name] for s in self.sheets]
        open(pro_path, "w").write(json.dumps(pro, indent=2) + "\n")

    root_notes = []

    def _write_libs(self):
        lib = [Sym("kicad_symbol_lib"), [Sym("version"), Sym("20241209")], [Sym("generator"), "kicad_draw"], [Sym("generator_version"), "9.0"]]
        for k, v in self.R.cache.items():
            if k.startswith(self.prefix + ":"):
                v2 = copy.deepcopy(v); v2[1] = k.split(":")[1]; lib.append(v2)
        open(os.path.join(self.outdir, f"{self.prefix}.kicad_sym"), "w").write(S.dump(lib) + "\n")
        stock = sorted({k.split(":")[0] for k in self.R.cache} - {self.prefix} | {"power"})
        rows = [f'  (lib (name "{self.prefix}")(type "KiCad")(uri "${{KIPRJMOD}}/{self.prefix}.kicad_sym")(options "")(descr "generated from datasheets"))']
        rows += [f'  (lib (name "{l}")(type "KiCad")(uri "${{KICAD9_SYMBOL_DIR}}/{l}.kicad_sym")(options "")(descr "KiCad stock library"))' for l in stock]
        open(os.path.join(self.outdir, "sym-lib-table"), "w").write("(sym_lib_table\n  (version 7)\n" + "\n".join(rows) + "\n)\n")
        open(os.path.join(self.outdir, "fp-lib-table"), "w").write(
            f'(fp_lib_table\n  (version 7)\n  (lib (name "{K.FP_LIB}")(type "KiCad")(uri "${{KIPRJMOD}}/../{K.FP_LIB}.pretty")(options "")'
            f'(descr "every footprint of the ESC and avionics boards: KiCad stock copies + generated from ADI/AMASS drawings"))\n)\n')

    def pcb_parts(self, netmap):
        """Footprint list for kicad_export.export_pcb: hierarchical paths (/sheet-uuid/symbol-uuid)."""
        out = []
        for s in self.sheets:
            for r, i in s.insts.items():
                p = i.part
                pads = {num: netmap[(r, num)] for num in i.bynum if (r, num) in netmap and not netmap[(r, num)].startswith("unconnected-")}
                out.append(dict(ref=r, fp=K.fp_name(p.fp), value=part_value(p),
                                uuid=i.uuid, path=f"/{s.uuid}/{i.uuid}", sheetname=f"/{s.name}/", sheetfile=s.file,
                                pads=pads, block=s.name, dnp="DNP" in p.pn))
        return out


def part_value(p):
    """Value field: the BOM value; connectors (no value) get their part family, e.g. 'Molex Micro-Fit 3.0'."""
    if p.value: return eng(p.bomval or p.value)
    return re.sub(r"^(Molex|JST|AMASS|TE)\s+", "", re.split(r"[,(]", p.pn)[0].strip())


def _wrap(t, n):
    import textwrap
    return textwrap.wrap(t, n)


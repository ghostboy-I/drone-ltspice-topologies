"""A drawn Sheet whose parts come from a board's parts table (board.py): value, SPICE line and the net every pin must
be on are taken from the table by reference designator, so the drawing and the BOM / net list cannot disagree."""
import paths  # noqa: F401  (topology 10's parts tables)
import os, re
from draw import Sheet, sym, xform
from board import eng

ALIAS = {"res": {"1": "A", "2": "B"}, "cap": {"1": "A", "2": "B"}, "ind": {"1": "A", "2": "B"}, "polcap": {"1": "A", "2": "B"},
         "diode": {"A": "+", "K": "-"}, "schottky": {"A": "+", "K": "-"}, "zener": {"A": "+", "K": "-"}}
DIRS = {"D": "R0", "R": "R270", "L": "R90", "U": "R180"}


class Table:
    def __init__(self, B):
        self.by = {}
        for p in B.parts:
            for r in p.refs(): self.by[r] = p

    def info(self, ref):
        p = self.by[ref]
        nets = p.nets_for(ref) if p.mult > 1 else dict(p.nets)
        val = (p.value if p.simm else (p.bomval or p.value)) if p.mult > 1 else p.value
        return p, val, p.spice, nets


def orient(S, f, o, d):
    """rotation that puts pin o in direction d (D/R/L/U) from pin f"""
    want = {"D": (0, 1), "U": (0, -1), "R": (1, 0), "L": (-1, 0)}[d]
    for rot in ("R0", "R90", "R180", "R270"):
        a = xform(rot, *S.pins[f]); b = xform(rot, *S.pins[o])
        v = (b[0] - a[0], b[1] - a[1])
        if (v[0] > 0) - (v[0] < 0) == want[0] and (v[1] > 0) - (v[1] < 0) == want[1]: return rot
    raise ValueError(d)


def ren(expr, m):
    """rename nodes / elements inside V(..) and I(..) of a behavioural expression"""
    def sub(mo):
        inner = ",".join(m.get(x.strip(), x.strip()) for x in mo.group(2).split(","))
        return f"{mo.group(1)}({inner})"
    return re.sub(r"\b(V|I)\(([^()]*)\)", sub, expr)


class TSheet(Sheet):
    def __init__(self, name, table, rename=None, title=""):
        super().__init__(name, title)
        self.T, self.rename, self.used, self.vren = table, rename or {}, set(), {}

    def _v(self, v):
        if isinstance(v, str) and v[:2] in ("V=", "I="): return ren(v, self.vren) if self.vren else v
        return eng(v)

    def _exp(self, symname, nets):
        al = ALIAS.get(symname, {})
        return {al.get(k, k): self.rename.get(v, v) for k, v in nets.items()}

    def put(self, ref, x, y, rot="R0", symname=None, value=None, spice=None, inst=None):
        p, val, sp, nets = self.T.info(ref)
        symname = symname or p.sym
        self.used.add(ref)
        return self.place(inst or ref, symname, x, y, rot, value=self._v(val) if value is None else value,
                          spice=sp if spice is None else spice, expect=self._exp(symname, nets))

    def two(self, ref, a, d, first=None, symname=None, value=None, spice=None, inst=None):
        """Two-terminal table part with its `first` pin (default: pin 1 / anode / +) at point a, body pointing D/R/L/U.
        Returns (part, other pin point)."""
        p, val, sp, nets = self.T.info(ref)
        symname = symname or p.sym
        S = sym(symname); pins = S.pin_by_order
        f = first if first is not None else pins[0]
        f = ALIAS.get(symname, {}).get(f, f)
        rot = orient(S, f, [q for q in pins if q != f][0], d); fx, fy = xform(rot, *S.pins[f])
        self.used.add(ref)
        P = self.place(inst or ref, symname, a[0] - fx, a[1] - fy, rot, value=self._v(val) if value is None else value,
                       spice=sp if spice is None else spice, expect=self._exp(symname, nets))
        return P, P[[q for q in pins if q != f][0]]

    def free2(self, inst, symname, a, d, value, spice="", first=None, expect=None):
        """Two-terminal part that is not in the table (inside a model sheet)."""
        S = sym(symname); pins = S.pin_by_order
        f = first or pins[0]; rot = orient(S, f, [q for q in pins if q != f][0], d); fx, fy = xform(rot, *S.pins[f])
        P = self.place(inst, symname, a[0] - fx, a[1] - fy, rot, value=value, spice=spice, expect=expect or {})
        return P, P[[q for q in pins if q != f][0]]

    def conn(self, x, y, ref, text, w=None, side="L"):
        """A connector drawn as a graphic (it has no SPICE model): a box with its reference and pin text."""
        w = w or max(160, 12 * len(text) + 40)
        x1 = x - w if side == "L" else x
        self.rects.append((x1, y - 40, x1 + w, y + 40))
        self.text(x1 + 12, y - 12, f";{ref}", 2); self.text(x1 + 12, y + 20, f";{text}", 1)


def block_asy(path, pins, box, title, sub=None):
    """Hierarchical block symbol. pins: [(name, x, y)]; box (x1,y1,x2,y2)."""
    x1, y1, x2, y2 = box
    if not os.path.isabs(path): path = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
    L = ["Version 4", "SymbolType BLOCK", f"RECTANGLE Normal {x1} {y1} {x2} {y2}", f"WINDOW 0 {x1} {y1 - 16} Bottom 2"]
    for i, t in enumerate(title.split("|")):
        L.append(f"TEXT {(x1 + x2) // 2} {y1 + 32 + 32 * i} Center 2 {t}")
    if sub: L.append(f"TEXT {(x1 + x2) // 2} {y2 - 24} Center 1 {sub}")
    for i, (n, x, y) in enumerate(pins):
        side = "LEFT" if x <= x1 else "RIGHT" if x >= x2 else "TOP" if y <= y1 else "BOTTOM"
        L += [f"PIN {x} {y} {side} 8", f"PINATTR PinName {n}", f"PINATTR SpiceOrder {i + 1}"]
    open(path, "w", newline="\r\n", encoding="latin-1").write("\n".join(L) + "\n")

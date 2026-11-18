"""Board builder: one parts table -> LTspice schematic (.asc) + KiCad-ready BOM and net list.

Every real component is a Part with a reference designator (R1, C1, Q1, U1, J1 ...), its simulation value and the data a
PCB needs (part number or specification, footprint, rating). Parts with sim=True are simulation-only stimulus or models
(battery packs, loads, the behavioural MCU) and are left out of the BOM.

Connections are made with net labels at the pins, so every net has a readable name that carries straight into KiCad."""
import os, re, csv, math

ASY_DIR = os.path.expanduser("~/.wine/drive_c/users/elijah-callahan/AppData/Local/LTspice/lib/sym")
# pin offsets of the built-in two-terminal and transistor symbols (R0); pin names as the netlist orders them
BUILTIN = {
    "res": [("1", 16, 16), ("2", 16, 96)], "cap": [("1", 16, 0), ("2", 16, 64)], "ind": [("1", 16, 16), ("2", 16, 96)],
    "polcap": [("+", 16, 0), ("-", 16, 64)], "diode": [("A", 16, 0), ("K", 16, 64)], "schottky": [("A", 16, 0), ("K", 16, 64)],
    "zener": [("A", 16, 0), ("K", 16, 64)], "voltage": [("+", 0, 16), ("-", 0, 96)], "bv": [("+", 0, 16), ("-", 0, 96)],
    "bi": [("+", 0, 0), ("-", 0, 80)], "nmos": [("D", 48, 0), ("G", 0, 80), ("S", 48, 96)],
}
PREFIX_OK = re.compile(r"^(R|C|L|D|Q|U|J|F|FB|TP|Y)\d+[A-Z]?$")


def read_asy(name):
    """Pin name -> (x, y) offsets of an LTspice library symbol (searched in all lib/sym subfolders)."""
    for root, _, files in os.walk(ASY_DIR):
        for f in files:
            if f.lower() == name.lower() + ".asy":
                raw = open(os.path.join(root, f), "rb").read()
                txt = raw.decode("utf-16le") if raw[:2] in (b"\xff\xfe",) or raw[1:2] == b"\x00" else raw.decode("latin1")
                pins, cur = [], None
                for line in txt.replace("\r", "").split("\n"):
                    p = line.split()
                    if p[:1] == ["PIN"]: cur = (int(p[1]), int(p[2]))
                    elif p[:2] == ["PINATTR", "PinName"] and cur: pins.append((p[2], cur[0], cur[1])); cur = None
                return pins
    raise FileNotFoundError(name)


def eng(v):
    """'3.3e-08' -> '33n', '976000' -> '976k'; anything that is not a plain number is returned unchanged."""
    try: x = float(v)
    except (TypeError, ValueError): return v
    if x == 0: return "0"
    for exp, suf in ((6, "Meg"), (3, "k"), (0, ""), (-3, "m"), (-6, "µ"), (-9, "n"), (-12, "p")):
        if abs(x) >= 10 ** exp * 0.9999:
            m = x / 10 ** exp; t = f"{m:.4g}"
            return t + suf
    return v


class Part:
    def __init__(self, ref, sym, value, nets, spice="", sim=False, desc="", pn="", fp="", rating="", qty=1, note="",
                 mult=1, simm=True, bomval=None):
        """mult > 1: one LTspice symbol stands for `mult` identical parts in parallel (e.g. 4 FETs per switch position).
        The BOM and net list expand it to consecutive references (Q4 -> Q4 Q5 Q6 Q7). simm=True passes m=mult to LTspice;
        simm=False means the simulated value is already the parallel equivalent (bomval is then the value of each part)."""
        self.__dict__.update(locals()); del self.__dict__["self"]

    def nets_for(self, ref):
        """Connections of one expanded copy: a net ending in '*' is per copy (GAH* -> GAH1..GAH4, e.g. each FET's own gate
        node behind its own gate resistor). LTspice simulates the parallel equivalent and just drops the '*'."""
        i = self.refs().index(ref) + 1
        return {k: (v[:-1] + str(i) if v.endswith("*") else v) for k, v in self.nets.items()}

    def refs(self):
        if self.mult == 1: return [self.ref]
        m = re.match(r"([A-Z]+)(\d+)$", self.ref)
        return [f"{m.group(1)}{int(m.group(2)) + i}" for i in range(self.mult)]


class Board:
    def __init__(self, name, title):
        self.name, self.title = name, title
        self.parts, self.blocks, self.directives = [], [], []

    def block(self, title, x, y, w, h):
        """A framed functional block (becomes a hierarchical sheet or a labelled area in KiCad)."""
        self.blocks.append(dict(title=title, x=x, y=y, w=w, h=h, cx=x + 48, cy=y + 96, row_h=0, items=[]))
        return self.blocks[-1]

    def add(self, blk, part, at=None, dx=None):
        """Place part in block blk. Parts flow left to right in rows inside the frame unless 'at' gives a position."""
        part.blk = blk["title"]
        if part.sym is None:                                   # connector / mechanical part: BOM + net list only
            part.pos, part.pins = None, [(n, 0, 0) for n in part.nets]
            blk.setdefault("notes", []).append(f"{part.ref} ({part.desc}): " + ", ".join(f"{k}={'GND' if v == '0' else v}" for k, v in part.nets.items()))
            self.parts.append(part); return part
        pins = BUILTIN.get(part.sym) or read_asy(part.sym)
        if at is None:
            minx = min(p[1] for p in pins); maxx = max(p[1] for p in pins)
            miny = min(p[2] for p in pins); maxy = max(p[2] for p in pins)
            w = max(maxx - minx, 32) + (dx or 112)
            if blk["cx"] - minx + w > blk["x"] + blk["w"] - 16:
                blk["cx"] = blk["x"] + 48; blk["cy"] += blk["row_h"] + 96; blk["row_h"] = 0
            x, y = blk["cx"] - minx, blk["cy"] - miny
            blk["cx"] += w; blk["row_h"] = max(blk["row_h"], maxy - miny)
        else:
            x, y = at
        part.pos, part.pins = (x, y), pins
        missing = [n for n in part.nets if n not in [p[0] for p in pins]]
        if missing: raise KeyError(f"{part.ref}: no pin(s) {missing} on {part.sym} (has {[p[0] for p in pins]})")
        self.parts.append(part)
        return part

    def check_refs(self):
        seen = {}
        for p in self.parts:
            if p.sim: continue
            for r in p.refs():
                if r in seen: raise ValueError(f"duplicate reference {r} ({seen[r]} and {p.desc})")
                seen[r] = p.desc
        return len(seen)

    # ------------------------------------------------------------------ LTspice
    def write_asc(self, path, ports=()):
        """ports: net names that become hierarchical ports (IOPIN) when this sheet is used as a block."""
        self._ported = set()
        L = ["Version 4", "SHEET 1 7000 5000"]
        for b in self.blocks:
            L.append(f"RECTANGLE Normal {b['x']} {b['y']} {b['x'] + b['w']} {b['y'] + b['h']} 2")
            L.append(f"TEXT {b['x'] + 16} {b['y'] + 40} Left 3 ;{b['title']}")
            for i, n in enumerate(b.get("notes", [])):
                L.append(f"TEXT {b['x'] + 16} {b['y'] + b['h'] - 24 - 32 * (len(b['notes']) - 1 - i)} Left 2 ;{n}")
        for p in self.parts:
            if p.pos is None: continue
            x, y = p.pos
            # LTspice reads a UTF-8 'µ' as two Latin-1 characters and drops the unit (47µ -> 47 H!), so write 'u'
            L += [f"SYMBOL {p.sym} {x} {y} R0", f"SYMATTR InstName {p.ref}", f"SYMATTR Value {p.value.replace('µ', 'u')}"]
            spice = p.spice + (f" m={p.mult}" if p.mult > 1 and p.simm else "")
            if spice.strip(): L.append(f"SYMATTR SpiceLine {spice.strip().replace('µ', 'u')}")
            for name, px, py in p.pins:
                net = p.nets.get(name)
                if net is None: continue                       # unconnected pin (left open on purpose)
                L.append(f"FLAG {x + px} {y + py} {net.rstrip('*')}")
                if net in ports and net not in self._ported:
                    L.append(f"IOPIN {x + px} {y + py} BiDir"); self._ported.add(net)
        y0 = max(b["y"] + b["h"] for b in self.blocks) + 120
        for i, d in enumerate(self.directives):
            L.append(f"TEXT 32 {y0 + 34 * i} Left 2 {d.replace('µ', 'u')}")
        open(path, "w", newline="\r\n", encoding="latin-1", errors="replace").write("\n".join(L) + "\n")

    # ------------------------------------------------------------------ KiCad hand-off
    def write_bom(self, path):
        rows = {}
        for p in self.parts:
            if p.sim: continue
            if not PREFIX_OK.match(p.ref): raise ValueError(f"{p.ref}: not a PCB reference designator; mark sim=True if simulation-only")
            key = (p.desc, eng(p.bomval or p.value), p.pn, p.fp, p.rating)
            for r in p.refs(): rows.setdefault(key, []).append((r, p.qty))
        def refkey(r):
            m = re.match(r"([A-Z]+)(\d+)", r); return (m.group(1), int(m.group(2)))
        out = sorted(rows.items(), key=lambda kv: refkey(sorted(kv[1], key=lambda r: refkey(r[0]))[0][0]))
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["References", "Qty", "Description", "Value", "Part number / specification", "KiCad footprint", "Rating"])
            for (desc, val, pn, fp, rating), refs in out:
                refs = sorted(refs, key=lambda r: refkey(r[0]))
                w.writerow([" ".join(r for r, _ in refs), sum(q for _, q in refs), desc, val, pn, fp, rating])
        return len(out)

    def write_netlist(self, path):
        """Net -> list of 'REF.pin' (PCB parts only), the list you wire in KiCad. Simulation-only parts are dropped,
        so a net that only touched a stimulus (e.g. a load) shows up with its board connector pin."""
        nets = {}
        for p in self.parts:
            if p.sim: continue
            for r in p.refs():
                for pin, net in p.nets_for(r).items():
                    nets.setdefault(net, []).append(f"{r}.{pin}")
        with open(path, "w", newline="") as f:
            w = csv.writer(f); w.writerow(["Net", "Connections (reference.pin)"])
            for net in sorted(nets, key=lambda n: (n != "0", n)):
                w.writerow(["GND" if net == "0" else net, " ".join(sorted(nets[net]))])
        single = [n for n, c in nets.items() if len(c) < 2]
        return len(nets), single

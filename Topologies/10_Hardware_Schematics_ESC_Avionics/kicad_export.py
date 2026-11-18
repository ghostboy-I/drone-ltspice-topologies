"""Writes a KiCad 9 project for a board defined in board.py (python3 kicad_export.py [esc|avionics]).

  kicad/<Name>.kicad_pro, .kicad_sch, <Name>_custom.kicad_sym, sym-lib-table

* KiCad library symbols are used wherever they exist, so symbol pin numbers match the footprint pads.
* The LTC7801 (FE TSSOP-24), LTC7063 (MSE-12), LT1763 (S8), LT8641 and LT3045 have no stock symbol. They are generated from
  the datasheet pin tables below (LTC7801, LTC7063 and LT1763 were read from ADI's pin-configuration drawings).
* Every pin gets a net label, the LTspice net names; unused pins get no-connect flags; simulation-only parts are dropped.
"""
import os, sys, uuid, json, copy, re
import sexpr as S
from sexpr import Sym
from board import eng

KLIB = "/usr/share/kicad/symbols"
FP_DIR = "/usr/share/kicad/footprints"
U = lambda: str(uuid.uuid4())

# ---------------- pin tables of the generated symbols: our (LTspice) pin name -> package pin numbers ----------------
CUSTOM = {
    "LTC7801": dict(pins={"SENSE-": ["1"], "SS": ["2"], "VFB": ["3"], "ITH": ["4"], "MODE": ["5"], "GND": ["6", "25"],
                          "CPUMP_EN": ["7"], "PLLIN": ["8"], "PGOOD": ["9"], "FREQ": ["10"], "DRVSET": ["11"], "DRVUV": ["12"],
                          "TG": ["13"], "SW": ["14"], "BOOST": ["15"], "BG": ["16"], "DRVCC": ["17"], "NDRV": ["18"], "VIN": ["19"],
                          "EXTVCC": ["20"], "RUN": ["21"], "INTVCC": ["22"], "OVLO": ["23"], "SENSE+": ["24"]},
                    desc="150 V synchronous buck controller, FE TSSOP-24 (pin 25 = exposed pad, GND)",
                    left=["19", "21", "23", "20", "10", "8", "5", "7", "11", "12", "2", "4", "3"],
                    right=["17", "18", "15", "13", "14", "16", "24", "1", "22", "9", "6", "25"]),
    "LTC7063": dict(pins={"PWM": ["1"], "EN": ["2"], "_FLT": ["3"], "DT": ["4"], "Vcc": ["5"], "BGVcc": ["6"], "BGRTN": ["7"],
                          "BG": ["8"], "NC": ["9"], "SW": ["10"], "TG": ["11"], "BST": ["12"], "SGND": ["13"]},
                    desc="150 V half-bridge driver, MSE-12 (pin 13 = exposed pad, SGND)",
                    left=["5", "6", "1", "2", "3", "4", "13"], right=["12", "11", "10", "9", "8", "7"]),
    "LT1763-5": dict(pins={"OUT": ["1"], "Sense": ["2"], "GND": ["3", "6", "7"], "BYP": ["4"], "_SHDN": ["5"], "IN": ["8"]},
                     desc="500 mA LDO 5 V, S8", left=["8", "5", "3", "6", "7"], right=["1", "2", "4"]),
    "LT1763-3.3": dict(pins={"OUT": ["1"], "Sense": ["2"], "GND": ["3", "6", "7"], "BYP": ["4"], "_SHDN": ["5"], "IN": ["8"]},
                       desc="500 mA LDO 3.3 V, S8", left=["8", "5", "3", "6", "7"], right=["1", "2", "4"]),
}
PIN_LABEL = {"_FLT": "~{FLT}", "_SHDN": "~{SHDN}"}           # KiCad overbar syntax


def flatten(lib, name, newname):
    """Copy a library symbol, resolving (extends ...) so the schematic cache gets a complete symbol named newname."""
    sym = copy.deepcopy(lib[name])
    ext = S.first(sym, "extends")
    if ext:
        parent = flatten(lib, ext[1], newname)
        props = {p[1]: p for p in S.find(sym, "property")}
        out = [e for e in parent if not (isinstance(e, list) and e[0] == "property" and e[1] in props)]
        out += list(props.values())
        sym = out
    sym[1] = newname
    base = newname.split(":")[-1]
    for u in S.find(sym, "symbol"):
        u[1] = re.sub(r"^.*_(\d+_\d+)$", base + r"_\1", u[1])
    return [e for e in sym if not (isinstance(e, list) and e[0] == "extends")]


def custom_symbol(name, spec):
    """A rectangular symbol: pins in package order, first half on the left, second half on the right."""
    pins = []
    for our, nums in spec["pins"].items():
        for i, n in enumerate(nums):
            pins.append((PIN_LABEL.get(our, our), n))
    pins.sort(key=lambda p: int(p[1]))
    if "left" in spec:                                   # functional placement: given pin numbers, top to bottom
        byn = {n: (nm, n) for nm, n in pins}
        pins = [byn[n] for n in spec["left"]] + [byn[n] for n in reversed(spec["right"])]
        half = len(spec["left"])
    else:
        half = (len(pins) + 1) // 2
    h = max(half, len(pins) - half) * 2.54 + 2.54
    w = 25.4 if name == "LTC7801" else 20.32
    body = [Sym("rectangle"), [Sym("start"), -w / 2, h / 2], [Sym("end"), w / 2, -h / 2],
            [Sym("stroke"), [Sym("width"), 0.254], [Sym("type"), Sym("default")]], [Sym("fill"), [Sym("type"), Sym("background")]]]
    pin_nodes = []
    for i, (pname, num) in enumerate(pins):
        left = i < half
        row = i if left else (len(pins) - 1 - i)
        y = h / 2 - 2.54 - row * 2.54
        x = -w / 2 - 2.54 if left else w / 2 + 2.54
        pin_nodes.append([Sym("pin"), Sym("no_connect" if pname == "NC" else "passive"), Sym("line"),
                          [Sym("at"), round(x, 2), round(y, 2), 0 if left else 180], [Sym("length"), 2.54],
                          [Sym("name"), pname, [Sym("effects"), [Sym("font"), [Sym("size"), 1.27, 1.27]]]],
                          [Sym("number"), num, [Sym("effects"), [Sym("font"), [Sym("size"), 1.27, 1.27]]]]])
    prop = lambda k, v, y, hide=False: [Sym("property"), k, v, [Sym("at"), 0, y, 0],
                                         [Sym("effects"), [Sym("font"), [Sym("size"), 1.27, 1.27]]] + ([[Sym("hide"), Sym("yes")]] if hide else [])]
    return [Sym("symbol"), name, [Sym("pin_names"), [Sym("offset"), 1.016]], [Sym("exclude_from_sim"), Sym("no")],
            [Sym("in_bom"), Sym("yes")], [Sym("on_board"), Sym("yes")],
            prop("Reference", "U", h / 2 + 2.54), prop("Value", name, -h / 2 - 2.54), prop("Footprint", "", 0, True),
            prop("Datasheet", "", 0, True), prop("Description", spec["desc"], 0, True),
            [Sym("symbol"), f"{name}_0_1", body], [Sym("symbol"), f"{name}_1_1"] + pin_nodes]


def pin_list(sym):
    """[(name, number, x, y, angle)] of a flattened symbol (unit 1 / common units only)."""
    out = []
    for u in S.find(sym, "symbol"):
        m = re.search(r"_(\d+)_(\d+)$", u[1])
        if m and m.group(1) not in ("0", "1"): continue
        for p in S.find(u, "pin"):
            at = S.first(p, "at")
            out.append((S.first(p, "name")[1], S.first(p, "number")[1], float(at[1]), float(at[2]), float(at[3]) if len(at) > 3 else 0.0))
    return out


class Resolver:
    """Maps one Part to (lib_id, flattened symbol, {our pin name: [pin numbers]})."""
    def __init__(self, prefix):
        self.cache, self.libs, self.prefix = {}, {}, prefix

    def lib(self, name):
        if name not in self.libs: self.libs[name] = S.library(f"{KLIB}/{name}.kicad_sym")
        return self.libs[name]

    def get(self, libname, symname):
        key = f"{libname}:{symname}"
        if key not in self.cache:
            if libname == self.prefix: self.cache[key] = custom_symbol(symname, CUSTOM[symname]); self.cache[key][1] = key
            else: self.cache[key] = flatten(self.lib(libname), symname, key)
        return key, self.cache[key]

    def resolve(self, p):
        names = list(p.nets)
        if p.sym in CUSTOM or p.value in CUSTOM:
            n = p.sym if p.sym in CUSTOM else p.value
            key, sym = self.get(self.prefix, n); return key, sym, CUSTOM[n]["pins"]
        if p.sym == "res":
            if "NTC" in p.desc: lib = ("Device", "Thermistor_NTC")
            elif p.ref.startswith("FB"): lib = ("Device", "FerriteBead")
            else: lib = ("Device", "R")
            key, sym = self.get(*lib); return key, sym, {"1": ["1"], "2": ["2"]}
        if p.sym == "cap" or (p.sym is None and p.ref.startswith("C")):
            key, sym = self.get("Device", "C"); return key, sym, {"1": ["1"], "2": ["2"]}
        if p.sym == "ind":
            key, sym = self.get("Device", "L"); return key, sym, {"1": ["1"], "2": ["2"]}
        if p.sym in ("diode", "schottky"):
            key, sym = self.get("Device", "LED" if "LED" in p.desc else "D"); return key, sym, {"A": ["2"], "K": ["1"]}
        if p.sym == "zener":
            key, sym = self.get("Device", "D_TVS"); return key, sym, {"A": ["2"], "K": ["1"]}
        if p.sym == "nmos":
            if p.value in ("BSC520N15NS3", "BSC360N15NS3"):
                key, sym = self.get("Transistor_FET", "BSC026N08NS5"); return key, sym, {"D": ["5"], "G": ["4"], "S": ["1", "2", "3"]}
            if p.value == "BSP89":
                key, sym = self.get("Transistor_FET", "BSP89"); return key, sym, {"G": ["1"], "D": ["2"], "S": ["3"]}
            key, sym = self.get("Transistor_FET", "Q_NMOS_GDS"); return key, sym, {"G": ["1"], "D": ["2"], "S": ["3"]}
        if p.sym is None and "ACS770" in p.pn:
            key, sym = self.get("Sensor_Current", "ACS770xCB-200B-PFF")
            return key, sym, {n: [num for nm, num, *_ in pin_list(sym) if nm == n] for n in names}
        if p.sym is None and "STM32G431" in p.pn:
            key, sym = self.get("MCU_ST_STM32G4", "STM32G431CBTx")
            return key, sym, {n: [num for nm, num, *_ in pin_list(sym) if nm == n] for n in names}
        if p.sym is None and p.ref.startswith("J"):
            key, sym = self.get("Connector_Generic", f"Conn_01x{len(names):02d}")
            return key, sym, {n: [str(i + 1)] for i, n in enumerate(names)}
        raise KeyError(f"no KiCad symbol rule for {p.ref} ({p.sym}, {p.value})")


def fp_ok(fp):
    fp = (fp or "").split(" (")[0]
    if ":" not in fp: return ""
    lib, name = fp.split(":", 1)
    return fp if os.path.exists(f"{FP_DIR}/{lib}.pretty/{name}.kicad_mod") else ""


def export(B, name, outdir):
    os.makedirs(outdir, exist_ok=True)
    prefix = f"{name}_custom"
    R = Resolver(prefix)
    root_uuid = U()
    items, placed, report = [], [], dict(nc=0, labels=0)
    net = lambda n: "GND" if n == "0" else n
    # ---- expand parts, resolve symbols, check every net-carrying pin exists ----
    entries = []
    for p in B.parts:
        if p.sim: continue
        key, sym, pmap = R.resolve(p)
        pins = pin_list(sym)
        nums = {num for _, num, *_ in pins}
        for our, n in p.nets.items():
            if our not in pmap or not pmap[our] or any(x not in nums for x in pmap[our]):
                raise KeyError(f"{p.ref}: pin '{our}' -> {pmap.get(our)} not on {key}")
        for r in p.refs():
            entries.append((r, p, key, sym, pmap, pins))      # per-copy nets via p.nets_for(r) below
    # ---- layout: one region per block, in the order the blocks were defined ----
    blocks = {}
    for e in entries: blocks.setdefault(e[1].blk, []).append(e)
    X0, Y0, page_w = 20.0, 30.0, 1150.0
    bx, by, row_h = X0, Y0, 0.0
    for title, ents in blocks.items():
        # block size from its parts
        cells = []
        for r, p, key, sym, pmap, pins in ents:
            xs = [x for *_, x, y, a in pins] or [0]; ys = [y for *_, x, y, a in pins] or [0]
            lab = max([len(net(p.nets.get(o, ""))) for o in p.nets] + [4]) * 1.3 + 6
            cells.append((max(xs) - min(xs) + 2 * lab + 8, max(ys) - min(ys) + 14, min(xs) - lab - 4, max(ys) + 7))
        cols = max(1, min(len(cells), 6 if len(cells) > 12 else 4))
        widths = [0.0] * cols; heights = []
        for i, c in enumerate(cells):
            widths[i % cols] = max(widths[i % cols], c[0])
            if i % cols == 0: heights.append(0.0)
            heights[-1] = max(heights[-1], c[1])
        bw, bh = sum(widths) + 10, sum(heights) + 22
        if bx + bw > X0 + page_w: bx, by, row_h = X0, by + row_h + 12, 0.0
        items.append([Sym("rectangle"), [Sym("start"), round(bx, 2), round(by, 2)], [Sym("end"), round(bx + bw, 2), round(by + bh, 2)],
                      [Sym("stroke"), [Sym("width"), 0.3], [Sym("type"), Sym("dash")]], [Sym("fill"), [Sym("type"), Sym("none")]], [Sym("uuid"), U()]])
        short = re.split(r"[:(]", title)[0].strip()
        short = short if len(short) * 2.0 < bw - 6 else short[: int((bw - 6) / 2.0) - 1] + "…"
        items.append([Sym("text"), short, [Sym("exclude_from_sim"), Sym("no")], [Sym("at"), round(bx + 3, 2), round(by + 6, 2), 0],
                      [Sym("effects"), [Sym("font"), [Sym("size"), 2.5, 2.5], [Sym("bold"), Sym("yes")]], [Sym("justify"), Sym("left")]], [Sym("uuid"), U()]])
        cy = by + 16
        for i, ((r, p, key, sym, pmap, pins), c) in enumerate(zip(ents, cells)):
            col = i % cols
            if col == 0 and i: cy += heights[i // cols - 1]
            cx = bx + 5 + sum(widths[:col])
            X = round((cx - c[2]) / 2.54) * 2.54; Y = round((cy + c[3]) / 2.54) * 2.54
            placed.append((r, p, key, sym, pmap, pins, X, Y))
        bx += bw + 12; row_h = max(row_h, bh)
    page_h = by + row_h + 30
    # ---- symbol instances, labels, no-connects ----
    for r, p, key, sym, pmap, pins, X, Y in placed:
        su = U()
        val = eng(p.bomval or p.value) if p.value else p.pn.split(" ")[0]
        fp = fp_ok(p.fp)
        if key.startswith(prefix + ":LTC7801"): fp = "Package_SO:HTSSOP-24-1EP_4.4x7.8mm_P0.65mm_EP3.2x5mm"
        props = [("Reference", r, -3.0, False), ("Value", val, 3.0, False), ("Footprint", fp, 0, True), ("Datasheet", "", 0, True),
                 ("Description", p.desc, 0, True), ("MPN/Spec", p.pn, 0, True), ("Rating", p.rating, 0, True)]
        node = [Sym("symbol"), [Sym("lib_id"), key], [Sym("at"), X, Y, 0], [Sym("unit"), 1], [Sym("exclude_from_sim"), Sym("no")],
                [Sym("in_bom"), Sym("yes")], [Sym("on_board"), Sym("yes")], [Sym("dnp"), Sym("yes" if "DNP" in p.pn else "no")],
                [Sym("uuid"), su]]
        ys = [y for *_, x, y, a in pins] or [0]
        for k, v, dy, hide in props:
            yy = Y - max(ys) - 2.5 if k == "Reference" else (Y - min(ys) + 2.5 if k == "Value" else Y)
            node.append([Sym("property"), k, v, [Sym("at"), X, round(yy, 2), 0],
                         [Sym("effects"), [Sym("font"), [Sym("size"), 1.27, 1.27]]] + ([[Sym("hide"), Sym("yes")]] if hide else [])])
        for _, num, *_ in pins: node.append([Sym("pin"), num, [Sym("uuid"), U()]])
        node.append([Sym("instances"), [Sym("project"), name, [Sym("path"), "/" + root_uuid, [Sym("reference"), r], [Sym("unit"), 1]]]])
        items.append(node)
        used = {}
        for our, nums in pmap.items():
            if our in p.nets:
                for n in nums: used[n] = net(p.nets_for(r)[our])
        for pname, num, px, py, ang in pins:
            ax, ay = round(X + px, 2), round(Y - py, 2)
            if num in used:
                la = (ang + 180) % 360
                items.append([Sym("label"), used[num], [Sym("at"), ax, ay, la],
                              [Sym("effects"), [Sym("font"), [Sym("size"), 1.0, 1.0]], [Sym("justify"), Sym("right" if la == 180 else "left"), Sym("bottom")]],
                              [Sym("uuid"), U()]])
                report["labels"] += 1
            else:
                items.append([Sym("no_connect"), [Sym("at"), ax, ay], [Sym("uuid"), U()]]); report["nc"] += 1
    # ---- PWR_FLAGs: the board's supplies come from connectors and regulators the ERC cannot see as power sources ----
    flag_key, flag_sym = None, None
    pw = S.library(f"{KLIB}/power.kicad_sym"); flag_sym = flatten(pw, "PWR_FLAG", "power:PWR_FLAG"); R.cache["power:PWR_FLAG"] = flag_sym
    rails = [n for n in ("GND", "VBUS", "VIN_AV", "+12V", "+5V", "+3V3", "VDDA") if any(net(v) == n for e in placed for v in e[1].nets.values())]
    for i, n in enumerate(rails):
        X, Y = round((X0 + 10 + 30 * i) / 2.54) * 2.54, round((page_h - 15) / 2.54) * 2.54
        items.append([Sym("symbol"), [Sym("lib_id"), "power:PWR_FLAG"], [Sym("at"), X, Y, 0], [Sym("unit"), 1], [Sym("exclude_from_sim"), Sym("no")],
                      [Sym("in_bom"), Sym("no")], [Sym("on_board"), Sym("yes")], [Sym("dnp"), Sym("no")], [Sym("uuid"), U()],
                      [Sym("property"), "Reference", f"#FLG{i + 1:02d}", [Sym("at"), X, Y + 3, 0], [Sym("effects"), [Sym("font"), [Sym("size"), 1.27, 1.27]], [Sym("hide"), Sym("yes")]]],
                      [Sym("property"), "Value", "PWR_FLAG", [Sym("at"), X, Y - 4, 0], [Sym("effects"), [Sym("font"), [Sym("size"), 1.27, 1.27]]]],
                      [Sym("pin"), "1", [Sym("uuid"), U()]],
                      [Sym("instances"), [Sym("project"), name, [Sym("path"), "/" + root_uuid, [Sym("reference"), f"#FLG{i + 1:02d}"], [Sym("unit"), 1]]]]])
        items.append([Sym("label"), n, [Sym("at"), X, Y, 270], [Sym("effects"), [Sym("font"), [Sym("size"), 1.0, 1.0]], [Sym("justify"), Sym("left"), Sym("bottom")]], [Sym("uuid"), U()]])
    # ---- write ----
    sch = [Sym("kicad_sch"), [Sym("version"), Sym("20250114")], [Sym("generator"), "eeschema"], [Sym("generator_version"), "9.0"],
           [Sym("uuid"), root_uuid], [Sym("paper"), "User", round(page_w + 2 * X0 + 20, 1), round(page_h + 10, 1)],
           [Sym("title_block"), [Sym("title"), B.title], [Sym("rev"), "A"],
            [Sym("comment"), 1, "Generated from the topology 10 parts table (board.py) - LTspice net names"],
            [Sym("comment"), 2, "Custom symbols: LTC7801 FE, LTC7063 MSE, LT1763 S8 pinouts from ADI pin-configuration drawings"]],
           [Sym("lib_symbols")] + list(R.cache.values())] + items + [
           [Sym("sheet_instances"), [Sym("path"), "/", [Sym("page"), "1"]]], [Sym("embedded_fonts"), Sym("no")]]
    open(f"{outdir}/{name}.kicad_sch", "w").write(S.dump(sch) + "\n")
    lib = [Sym("kicad_symbol_lib"), [Sym("version"), Sym("20241209")], [Sym("generator"), "kicad_export"], [Sym("generator_version"), "9.0"]]
    for k, v in R.cache.items():
        if k.startswith(prefix + ":"):
            v2 = copy.deepcopy(v); v2[1] = k.split(":")[1]; lib.append(v2)
    open(f"{outdir}/{prefix}.kicad_sym", "w").write(S.dump(lib) + "\n")
    stock = sorted({k.split(":")[0] for k in R.cache} - {prefix})
    rows = [f'  (lib (name "{prefix}")(type "KiCad")(uri "${{KIPRJMOD}}/{prefix}.kicad_sym")(options "")(descr "generated from datasheets"))']
    rows += [f'  (lib (name "{l}")(type "KiCad")(uri "${{KICAD9_SYMBOL_DIR}}/{l}.kicad_sym")(options "")(descr "KiCad stock library"))' for l in stock]
    open(f"{outdir}/sym-lib-table", "w").write("(sym_lib_table\n  (version 7)\n" + "\n".join(rows) + "\n)\n")
    pro = {"meta": {"filename": f"{name}.kicad_pro", "version": 3}, "sheets": [[root_uuid, "Root"]]}
    open(f"{outdir}/{name}.kicad_pro", "w").write(json.dumps(pro, indent=2) + "\n")
    expected = {}
    for r, p, key, sym, pmap, pins, X, Y in placed:
        for our, nums in pmap.items():
            if our in p.nets:
                for n in nums: expected.setdefault(net(p.nets_for(r)[our]), set()).add((r, n))
    return dict(parts=len(placed), symbols=len(R.cache), **report, expected=expected)


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "esc"
    if which == "esc":
        import esc; B = esc.build(); name = "ESC_Board"
    else:
        import avionics; B = avionics.build(); name = "Avionics_Board"
    info = export(B, name, os.path.join(os.path.dirname(os.path.abspath(__file__)), "kicad", name))
    json.dump({k: sorted(map(list, v)) for k, v in info.pop("expected").items()},
              open(os.path.join("kicad", name, "expected_nets.json"), "w"), indent=0)
    print(name, info)

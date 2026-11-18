"""Builds 11_KiCad_Entry_Guide.pdf: everything needed to enter the two boards into KiCad by hand, block by block,
cross-referenced to the LTspice schematics (same reference designators, same block numbers, same net names)."""
import os, sys, textwrap, re
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, here)
import paths  # noqa: F401  (topology 10 parts tables + tools)
from designdoc import Doc
from board import eng
import esc, avionics
from kicad_export import Resolver, CUSTOM

ROWS = 26                                   # table rows per chunk (a table must fit on one page)


def chunks(header, rows, widths, doc):
    for i in range(0, len(rows), ROWS):
        doc.table(header, rows[i:i + ROWS], widths=widths)


def wrap(s, n):
    return textwrap.wrap(s, n) or [""]


def board_rows(B, prefix):
    R = Resolver(prefix)
    blocks = {}
    for p in B.parts:
        if p.sim: continue
        blocks.setdefault(p.blk, []).append(p)
    out = []
    for title, parts in blocks.items():
        prow, wrow = [], []
        for p in parts:
            refs = p.refs()
            refstr = refs[0] if len(refs) == 1 else f"{refs[0]}–{refs[-1]}"
            val = eng(p.bomval or p.value) if p.value else ""
            fp = (p.fp or "").replace("Package_", "").replace("Capacitor_SMD:", "").replace("Resistor_SMD:", "")
            pn = p.pn
            if p.sym is None and p.desc.startswith("LDO bypass, DO NOT FIT"): val = "DNP"
            prow.append([refstr, str(len(refs)), (val or "—")[:10], pn[:33] + ("…" if len(pn) > 33 else ""), fp[:31] + ("…" if len(fp) > 31 else "")])
            try: key, sym, pmap = R.resolve(p)
            except KeyError: key, pmap = "?", {}
            for r in refs:
                nets = p.nets_for(r)
                conn = []
                for pin, net in nets.items():
                    nums = pmap.get(pin, [])
                    label = {"1": "1", "2": "2"}.get(pin, pin)
                    pads = ",".join(nums)
                    name = label if (pads == label or not pads) else f"{label}({pads})"
                    conn.append(f"{name}={'GND' if net == '0' else net}")
                lines = wrap("  ".join(conn), 92)
                wrow.append([r, lines[0]])
                wrow += [["", l] for l in lines[1:]]
                if len(refs) > 1 and r == refs[0] and "*" in "".join(p.nets.values()):
                    pass
        out.append((title, prow, wrow))
    return out


doc = Doc("11  KiCad Entry Guide: ESC + Avionics Boards",
          "parts, footprints and pin-by-pin wiring, cross-referenced to the LTspice schematics")
doc.h("1. How this guide maps to the LTspice schematics")
doc.p("Open Power_System.asc in LTspice: it shows the whole system, and each board is a block you can double-click. "
      "ESC_Block.asc (the ESC board) and Avionics_Block.asc (the avionics board) are drawn like a normal schematic: every part, "
      "wired. They are divided into numbered, framed areas (1 POWER INPUT + DC LINK, 2 ESC AUX SUPPLY, 4-6 LEG A-C, ...). This guide "
      "uses the same area numbers, the same reference designators and the same net names. Suggested KiCad layout: one hierarchical "
      "sheet per area; power symbols for GND, VBUS, +12V, +5V and +3V3; a global label for every other net that crosses areas.")
doc.bullets([
    "Every part on the drawn sheets is a board part with its PCB reference, one symbol per part: all 24 inverter FETs, each with "
    "its own gate resistor and 10 kOhm pull-down (gate nets GAH1-GAH4, GAL1-GAL4, ... in the tables below).",
    "Three ESC parts have no maker SPICE model, so in LTspice they are blocks with an equivalent circuit inside: U7/U8 ACS772 "
    "(the Hall sensor) and U9 STM32G431 (its inside is the FOC firmware). On the PCB they are the real chips, wired by the pins "
    "listed below. The connectors (J..) are drawn as boxes because they have no SPICE model either.",
    "Simulation-only items to ignore: the packs (V_PACK), harness (L_HARN), the load sources (B_VTX, B_FC, B_SENS, B_ENC, C_VTX) "
    "and the MOTOR blocks.",
    "Pins are written NAME(pad) when the name differs from the pad number, e.g. G(1) D(2) S(3), or SENSE+(24). Use the pad "
    "number when you draw the symbol; it must match the footprint.",
    "Footprints: every one is in the project library 10_Hardware_Schematics_ESC_Avionics/kicad/Drone_Power.pretty. Stock KiCad "
    "footprints are copied in under their KiCad names; four were made from the manufacturers' drawings: LT8641 UDC QFN "
    "(Linear_UDC-18-2EP), LTC7801 FE24 (Linear_HTSSOP-24-1EP..._EP2.74x3.25mm), the AS150 pigtail pads and the 8 AWG phase pads.",
    "The generated KiCad projects (kicad/ESC_Board, kicad/Avionics_Board) already contain all of this: schematic, symbols, and a "
    "PCB with every footprint loaded and on its net. Use this guide to check them, or to enter the boards by hand.",
])

doc.h("2. Symbols and pin numbers")
doc.table(["Part", "KiCad symbol", "Pin numbering (must match the footprint)"], [
    ["R, C, L, ferrite, NTC", "Device: R, C, L, FerriteBead, ...", "1, 2"],
    ["ES1D, LED", "Device:D / Device:LED", "K = 1, A = 2"],
    ["IPB065N15N3 (TO-263-2)", "Transistor_FET:Q_NMOS_GDS", "G = 1, D = 2 (tab), S = 3"],
    ["BSC520N15NS3 / BSC360…", "Transistor_FET:BSC026N08NS5", "S = 1, 2, 3; G = 4; D = 5 (tab)"],
    ["BSP89 (SOT-223)", "Transistor_FET:BSP89", "G = 1, D = 2 (tab), S = 3"],
    ["ACS772ECB-250B", "Sensor_Current:ACS770xCB-200B-PFF", "VCC 1, GND 2, VIOUT 3, IP+ 4, IP− 5"],
    ["STM32G431CBT6", "MCU_ST_STM32G4:STM32G431CBTx", "by pin name (PA8, PB12, VDD, ...)"],
    ["LT3045 (avionics)", "Regulator_Linear:LT3045xDD", "by pin name; pad 11 = GND"],
    ["SMBJ110A TVS, fuses", "Device:D_Zener, Device:Fuse", "K = 1, A = 2; 1, 2"],
    ["FDB33N25 (TO-263-2)", "Transistor_FET:Q_NMOS_GDS", "G = 1, D = 2 (tab), S = 3"],
    ["LTC7801, LTC7063 ...", "<Board>_custom.kicad_sym", "tables below (also LT1763, LT8641, LTC4366)"],
], widths=[0.30, 0.37, 0.33])
for name, title in (("LTC7801", "LTC7801EFE (TSSOP-24 with exposed pad, pad 25 = GND)"), ("LTC7063", "LTC7063EMSE (MSOP-12 with exposed pad, pad 13 = SGND)"),
                    ("LT1763-5", "LT1763CS8-5 / -3.3 (SO-8)"),
                    ("LT8641", "LT8641EUDC (UDC 20(18)-lead QFN 3x4 mm: pads 5 and 12 removed, 21 and 22 = exposed SW pads)"),
                    ("LTC4366-2", "LTC4366CTS8-2 (TSOT-23-8; BASE, pad 5, unused)")):
    pins = sorted(((int(n), nm) for nm, ns in CUSTOM[name]["pins"].items() for n in ns))
    doc.p(f"{title}. Read from ADI's pin-configuration drawings:", size=9.5)
    half = (len(pins) + 1) // 2
    rows = []
    for i in range(half):
        a = pins[i]; b = pins[i + half] if i + half < len(pins) else None
        rows.append([str(a[0]), a[1].replace("_", "~"), str(b[0]) if b else "", (b[1].replace("_", "~") if b else "")])
    doc.table(["Pad", "Name", "Pad", "Name"], rows, widths=[0.12, 0.38, 0.12, 0.38])

for B, prefix, name in ((esc.build(), "ESC", "ESC board (one per motor)"), (avionics.build(), "Avionics", "Avionics power board")):
    doc.pagebreak()
    doc.h(f"{'3' if prefix == 'ESC' else '4'}. {name}")
    for title, prow, wrow in board_rows(B, prefix):
        doc.h(re.split(r"[:(]", title)[0].strip()[:70])
        doc.p(title[:200], size=8.5)
        chunks(["Refs", "Qty", "Value", "Part number / specification", "KiCad footprint"], prow, [0.12, 0.05, 0.10, 0.39, 0.34], doc)
        chunks(["Ref", "Pin = net"], wrow, [0.09, 0.91], doc)

# ---- net index
for B, prefix, name in ((esc.build(), "ESC", "ESC board"), (avionics.build(), "Avionics", "Avionics board")):
    doc.pagebreak(); doc.h(f"Net index: {name}")
    doc.p("Every net and every pin on it (the same content as the *_Netlist.csv file). Check each net off as you wire it.", size=9)
    nets = {}
    for p in B.parts:
        if p.sim: continue
        for r in p.refs():
            for pin, net in p.nets_for(r).items():
                nets.setdefault("GND" if net == "0" else net, []).append(f"{r}.{pin}")
    rows = []
    def keyf(n): return (n != "GND", n)
    for n in sorted(nets, key=keyf):
        lines = wrap(" ".join(sorted(nets[n], key=lambda s: (re.match(r"[A-Z]+", s).group(), int(re.search(r"\d+", s).group())))), 88)
        rows.append([n, lines[0]]); rows += [["", l] for l in lines[1:]]
    chunks(["Net", "Pins"], rows, [0.14, 0.86], doc)

n = doc.save(os.path.join(here, "11_KiCad_Entry_Guide.pdf"))
print("pages:", n)

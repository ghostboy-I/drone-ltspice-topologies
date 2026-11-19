"""Avionics power board: PCB layout for JLCPCB (4 layers, 1.6 mm, 2 oz outer / 1 oz inner copper).

    python3 pcb_avionics.py            re-export the netted board from the schematic, then place, pour, route, fill, check
    python3 pcb_avionics.py place      placement only (fast), with the render, for checking the floorplan

The layout is a script, so it can be re-run after any schematic change. Steps (each one a function below):
  1. setup()      4 copper layers, JLC stackup, net classes, the high-voltage clearance rules (Avionics_Board.kicad_dru)
  2. outline()    100 x 62 mm board, 4 x M3 holes
  3. place()      every part at a hand-chosen spot (PLACE): power flows left to right, input -> surge stopper -> 12 V -> 5 V -> 3.3 V
  4. pours()      copper areas for the power nets on F.Cu, GND planes on In1 / In2 and a GND pour on B.Cu
  5. fanout()     a via next to every ground pad, into the inner planes
  6. route()      the rest with kicad_route.Router (A* on a 0.05 mm grid, F.Cu + B.Cu); rip-up and retry: if a net
                  fails, the whole layout is run again with the failed nets first (up to 5 passes, the best is kept)
  7. fill + DRC   zones filled by KiCad with the HV rules loaded, kicad-cli DRC (report next to the board), and
                  pinfield_audit(): the U1 pin-field exemption must not reach copper outside the pin field
    python3 pcb_avionics.py fab        Gerbers, drill, BOM and CPL for JLCPCB in kicad/Avionics_Board/jlcpcb/
"""
import os, sys, json, math, subprocess, re
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "kicad", "Avionics_Board")
NAME = "Avionics_Board"
PCB = os.path.join(OUT, NAME + ".kicad_pcb")
LIB = os.path.join(HERE, "kicad", "Drone_Power.pretty")
MM = 1e6
OX, OY = 50.0, 40.0                      # board origin on the KiCad page
W, H = 100.0, 62.0                       # board size (mm)
mm = lambda x, y: pcbnew.VECTOR2I_MM(OX + x, OY + y)

# ---------------------------------------------------------------- net classes and clearances
# IPC-2221B table 6-1, B2 (external, uncoated, sea level to 3050 m): 31-150 V -> 0.6 mm, 151-300 V -> 1.25 mm.
# Peak voltages from Avionics_SurgeTest.raw (pack 1 at 200 V behind 4 ohm): VIN_AV 179 V, GATE_SS 121 V, VDD_SS 122 V,
# VIN_PROT 115.8 V, VSS_SS / TMR_SS 110 V. The pack nets are rated for the full 200 V surge.
CLASSES = {
    "HVIN": dict(nets=["/Inputs/PACK1+", "/Inputs/PACK2+", "/Inputs/PACK3+", "/Inputs/PACK1_F", "/Inputs/PACK2_F",
                       "/Inputs/PACK3_F", "/Inputs/VIN_AV"], track=1.0, desc="pack side, up to 200 V"),
    "HVF": dict(nets=["VIN_PROT", "/Inputs/VDD_SS", "/Inputs/VSS_SS", "/Inputs/TMR_SS", "/Inputs/GATE_SS",
                      "/Inputs/GATE_SSD", "/Inputs/FB_SS", "unconnected-(U4-BASE-Pad5)"], track=0.5,
                desc="VIN_PROT and the floating LTC4366 nets (BASE is unused but floats with them), <= 122 V"),
    "HVSW": dict(nets=["/Buck_12V/SW12", "/Buck_12V/BST12", "/Buck_12V/TG12"], track=0.5, desc="12 V switch node and high-side drive, 0-126 V"),
    "PWR": dict(nets=["+12V", "+5V", "+3V3", "GND", "/Out_12V/VTX_12V", "/Buck_5V/SW5", "/Buck_12V/SNS12"], track=0.8,
                desc="low-voltage power"),
    "DRV": dict(nets=["/Buck_12V/BG12", "/Buck_12V/DRVCC12", "/Buck_12V/INTVCC12", "/Buck_12V/NDRV12", "/Buck_5V/BST5",
                      "/Buck_5V/INTVCC5"], track=0.4, desc="gate drive and driver supplies"),
}
CLEAR = {("HVIN", "LV"): 1.25, ("HVIN", "HVSW"): 1.25, ("HVIN", "HVF"): 0.6,
         ("HVF", "LV"): 0.6, ("HVF", "HVSW"): 0.6, ("HVSW", "LV"): 0.6}
HV = ("HVIN", "HVF", "HVSW")
INNER_HV = 0.5                           # inner layers (IPC B1 asks 0.2 mm up to 300 V; 0.5 mm for margin)
MIN_CLEAR, MIN_TRACK, VIA = 0.2, 0.2, (0.6, 0.3)   # JLC 2 oz outer copper: 0.2 / 0.2 mm is comfortable
EXEMPT = ["U1"]                          # fine-pitch IC whose own pinout puts VIN next to low-voltage pins
EXEMPT_EDGE = 0.25                       # rule area = router's exempt region + half the widest pin-field track + 1 cell


def netclass_of(name):
    for c, d in CLASSES.items():
        if name in d["nets"]: return c
    return "Default"


def hv_group(c):
    return c if c in HV else "LV"


def clearance(a, b, outer=True):
    """Clearance (mm) between copper of net classes a and b."""
    ga, gb = hv_group(a), hv_group(b)
    if ga == gb: return MIN_CLEAR
    if not outer: return INNER_HV
    return CLEAR.get((ga, gb)) or CLEAR.get((gb, ga)) or MIN_CLEAR


def write_rules():
    """Avionics_Board.kicad_dru: one rule per class pair (outer layers) plus the inner-layer rule and the IC exemption.
    KiCad applies the last matching rule, so the exemption comes last."""
    r = ["(version 1)", ""]
    pairs = sorted({tuple(sorted(k)) for k in CLEAR})
    for a, b in pairs:
        v = CLEAR.get((a, b)) or CLEAR[(b, a)]
        def cond(x, y):
            if y == "LV": return f"A.NetClass == '{x}' && !(B.NetClass == 'HVIN' || B.NetClass == 'HVF' || B.NetClass == 'HVSW') && B.Type != 'Footprint'"
            return f"A.NetClass == '{x}' && B.NetClass == '{y}'"
        x, y = (a, b) if b == "LV" or a != "LV" else (b, a)
        r += [f"(rule \"{x} to {y}: {v} mm (IPC-2221B B2)\"", "  (layer outer)",
              f"  (condition \"{cond(x, y)} && B.Net != ''\")",
              f"  (constraint clearance (min {v}mm)))", ""]
        if y == "LV":           # unconnected copper (mounting-hole pads, connector pegs) counts as low voltage too
            r += [f"(rule \"{x} to unconnected copper: {v} mm\"", "  (layer outer)",
                  f"  (condition \"A.NetClass == '{x}' && B.Net == '' && B.Type == 'Pad'\")",
                  f"  (constraint clearance (min {v}mm)))", ""]
    r += ["(rule \"HV on inner layers: 0.5 mm (IPC B1 asks 0.2 mm)\"", "  (layer inner)",
          "  (condition \"(A.NetClass == 'HVIN' || A.NetClass == 'HVF' || A.NetClass == 'HVSW') && A.Net != B.Net\")",
          f"  (constraint clearance (min {INNER_HV}mm)))", ""]
    for ref in EXEMPT:
        r += [f"(rule \"{ref} pin field: the IC's own pin pitch (0.2 mm between VIN / BST and their neighbours)\"",
              "  (layer \"F.Cu\")",
              f"  (condition \"A.intersectsArea('{ref}_PINS') && B.intersectsArea('{ref}_PINS') && A.Type != 'Zone' && B.Type != 'Zone'\")",
              f"  (constraint clearance (min {MIN_CLEAR}mm)))", ""]
    open(os.path.join(OUT, NAME + ".kicad_dru"), "w").write("\n".join(r))


def write_project():
    """Net classes and the JLC minimums into the .kicad_pro (pcbnew reads them from there)."""
    p = os.path.join(OUT, NAME + ".kicad_pro")
    pro = json.load(open(p))
    base = pro["net_settings"]["classes"][0]
    base.update(clearance=MIN_CLEAR, track_width=0.25, via_diameter=VIA[0], via_drill=VIA[1])
    classes = [base]
    for i, (c, d) in enumerate(CLASSES.items()):
        k = dict(base); k.update(name=c, priority=i, track_width=d["track"], clearance=MIN_CLEAR,
                                 via_diameter=0.8 if c in ("PWR", "HVIN") else VIA[0], via_drill=0.4 if c in ("PWR", "HVIN") else VIA[1])
        classes.append(k)
    pro["net_settings"]["classes"] = classes
    pro["net_settings"]["netclass_patterns"] = [{"netclass": c, "pattern": n} for c, d in CLASSES.items() for n in d["nets"]]
    ds = pro["board"]["design_settings"]
    rules = ds.setdefault("rules", {})
    rules.update(min_clearance=MIN_CLEAR, min_track_width=MIN_TRACK, min_via_diameter=0.5, min_through_hole_diameter=0.3,
                 min_via_annular_width=0.13, min_copper_edge_clearance=0.4, min_hole_clearance=0.25, min_hole_to_hole=0.5,
                 min_silk_clearance=0.0, solder_mask_to_copper_clearance=0.0, min_text_height=0.8, min_text_thickness=0.12)
    ds["track_widths"] = [0.0, 0.25, 0.4, 0.5, 0.8, 1.0, 1.5]
    ds["via_dimensions"] = [{"diameter": 0.0, "drill": 0.0}, {"diameter": 0.6, "drill": 0.3}, {"diameter": 0.8, "drill": 0.4}]
    sev = ds.setdefault("rule_severities", {})
    json.dump(pro, open(p, "w"), indent=2)


# ---------------------------------------------------------------- placement (board frame: mm from the top-left corner)
# (x, y, rotation in degrees, CCW as KiCad shows it)
PLACE = {
    # 1  inputs: three packs -> fuse -> diode-OR. Connector GND pins on the outside edge, PACK+ facing the fuses.
    "J1": (8.0, 14.0, 180), "F1": (15.6, 14.0, 0), "D1": (22.6, 14.0, 180),
    "J2": (8.0, 25.0, 180), "F2": (15.6, 25.0, 0), "D2": (22.6, 25.0, 180),
    "J3": (8.0, 36.0, 180), "F3": (15.6, 36.0, 0), "D3": (22.6, 36.0, 180),
    "D4": (29.0, 42.0, 270),                                   # TVS on VIN_AV, anode to GND below
    # surge stopper: Q4 tab is VIN_AV (left), source = VIN_PROT (top right), gate (bottom right)
    "Q4": (36.6, 22.0, 180),
    "C26": (40.6, 29.6, 180), "R25": (44.6, 30.0, 90), "U4": (44.0, 34.2, 0), "R21": (37.5, 33.5, 0),
    "C27": (41.0, 37.6, 0), "C28": (45.5, 37.6, 180), "R22": (42.0, 41.2, 270), "R23": (48.6, 33.6, 0),
    "R24": (49.6, 36.6, 0),
    "C1": (52.3, 25.0, 270),                                   # VIN_PROT bulk
    # 2  12 V buck power stage: C2/C3 -> Q1 (high side) -> SW -> Q2 (low side); return through In1 under the stage
    "C2": (54.3, 13.3, 180), "C3": (54.3, 16.7, 180),
    "Q1": (60.5, 15.0, 180), "Q2": (67.9, 15.0, 180),
    "L1": (64.2, 23.7, 270), "R1": (64.2, 32.0, 0),
    "U1": (85.0, 10.0, 180),
    "C5": (71.0, 10.6, 270),                                   # bootstrap cap at the switch-node pour (pad 2 sits in it)
    "Q3": (79.6, 21.0, 0), "C6": (74.1, 22.4, 90),            # DRVCC pass FET (VIN_PROT -> ~10 V) and its output cap
    # OVLO divider above the RUN divider: OVLO (pin 23) leaves U1 inside RUN (pin 21), so it takes the upper row
    "R4": (88.6, 20.0, 0), "R5": (92.6, 20.0, 0), "R2": (88.6, 23.0, 0), "R3": (92.6, 23.0, 0),
    "C4": (85.0, 15.6, 0),
    "R20": (91.0, 6.4, 0), "R6": (91.0, 8.1, 0), "C7": (91.0, 9.8, 0), "C10": (91.0, 11.5, 0), "C8": (91.0, 13.2, 0),
    "R8": (91.0, 14.9, 0), "R7": (91.0, 16.6, 180),
    "R10": (94.8, 9.8, 0), "R9": (94.8, 11.5, 0), "C9": (94.8, 13.2, 0),
    # 3  +12V output: bulk, fuse, transmitter connector
    "C13": (69.0, 36.5, 0), "C14": (69.0, 40.0, 0),
    "C11": (77.0, 32.8, 0), "C12": (77.0, 40.0, 0),
    "F4": (87.5, 31.4, 0), "J4": (95.5, 31.0, 270),
    # 4  5 V buck (LT8641): input caps either side of the IC, SW out of the bottom into L2, +5V out to the right
    "U2": (85.0, 46.0, 0), "C15": (81.9, 47.0, 270), "C16": (88.1, 46.9, 270),
    "L2": (85.0, 51.6, 0), "C21": (90.6, 50.3, 0), "C22": (90.6, 53.6, 0),
    "C17": (81.2, 51.6, 270), "C18": (79.6, 44.4, 180), "C19": (91.0, 45.0, 0), "R11": (91.0, 46.9, 0),
    # feedback / PG pull-up row 2.5 mm above U2's top pins: room for the vias of the four nets leaving U2's corner
    "C20": (82.6, 40.0, 90), "R12": (84.3, 40.0, 90), "R13": (86.0, 40.0, 90), "R14": (87.8, 40.0, 90),
    "J5": (84.5, 58.6, 180),
    # 5  3.3 V LDO (LT3045)
    "U3": (73.0, 50.5, 0), "C24": (69.0, 49.8, 90), "C25": (77.0, 49.8, 90),
    "C23": (78.9, 52.6, 0), "R15": (78.9, 54.3, 0), "R17": (75.4, 53.6, 180), "R18": (75.4, 55.3, 0),   # SET right of PGFB
    "R16": (70.4, 53.6, 0), "R19": (70.4, 55.3, 0),
    "J6": (66.0, 58.6, 180),
}
HOLES = [(4.0, 4.0), (W - 4.0, 4.0), (4.0, H - 4.0), (W - 4.0, H - 4.0)]


def load():
    """Load the board with the net classes from the .kicad_pro on disk. pcbnew keeps a project in memory once one of its
    boards is loaded (here: by the schematic export), and a later LoadBoard reuses that copy, even after write_project()
    changed the file. Without the classes no HV rule in the .kicad_dru matches (they test A.NetClass) and the pours are
    filled at 0.2 mm everywhere. So unload the cached project first, and check the classes arrived."""
    sm = pcbnew.GetSettingsManager()
    pro = sm.GetProject(os.path.abspath(os.path.join(OUT, NAME + ".kicad_pro")))
    if pro: sm.UnloadProject(pro, False)
    b = pcbnew.LoadBoard(PCB)
    got = {str(k) for k in b.GetDesignSettings().m_NetSettings.GetNetclasses()}
    assert set(CLASSES) <= got, f"net classes missing after load: {set(CLASSES) - got}"
    return b


def setup(b):
    b.SetCopperLayerCount(4)
    ds = b.GetDesignSettings()
    ds.SetBoardThickness(int(1.6 * MM))
    ds.m_TrackMinWidth = int(MIN_TRACK * MM); ds.m_MinClearance = int(MIN_CLEAR * MM)
    ds.m_ViasMinSize = int(0.5 * MM); ds.m_MinThroughDrill = int(0.3 * MM); ds.m_CopperEdgeClearance = int(0.4 * MM)
    ds.m_HoleClearance = int(0.25 * MM)
    for L in (pcbnew.In1_Cu, pcbnew.In2_Cu):
        b.SetLayerType(L, pcbnew.LT_POWER)
    b.SetLayerName(pcbnew.In1_Cu, "In1.GND"); b.SetLayerName(pcbnew.In2_Cu, "In2.GND")


def outline(b):
    """Rounded rectangle on Edge.Cuts and the four M3 holes (board-only footprints, no schematic symbol)."""
    for d in list(b.GetDrawings()):
        if d.GetLayer() in (pcbnew.Edge_Cuts, pcbnew.Cmts_User): b.Remove(d)
    r = 2.0
    segs = [((r, 0), (W - r, 0)), ((W, r), (W, H - r)), ((W - r, H), (r, H)), ((0, H - r), (0, r))]
    for a, c in segs:
        s = pcbnew.PCB_SHAPE(b, pcbnew.SHAPE_T_SEGMENT); s.SetStart(mm(*a)); s.SetEnd(mm(*c))
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(int(0.1 * MM)); b.Add(s)
    for cx, cy, a0 in ((r, r, 180), (W - r, r, 270), (W - r, H - r, 0), (r, H - r, 90)):
        s = pcbnew.PCB_SHAPE(b, pcbnew.SHAPE_T_ARC); s.SetCenter(mm(cx, cy))
        s.SetStart(mm(cx + r * math.cos(math.radians(a0)), cy + r * math.sin(math.radians(a0))))
        s.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(90, pcbnew.DEGREES_T), True)
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(int(0.1 * MM)); b.Add(s)
    for i, (x, y) in enumerate(HOLES):
        fp = pcbnew.FootprintLoad(LIB, "MountingHole_3.2mm_M3")
        fp.SetFPID(pcbnew.LIB_ID("Drone_Power", "MountingHole_3.2mm_M3"))
        fp.SetReference(f"H{i + 1}"); fp.SetValue("M3")
        fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_POS_FILES | pcbnew.FP_EXCLUDE_FROM_BOM)
        fp.SetPosition(mm(x, y)); b.Add(fp)


def place(b):
    missing = []
    for fp in b.GetFootprints():
        ref = fp.GetReference()
        if ref.startswith("H"): continue
        if ref not in PLACE: missing.append(ref); continue
        x, y, rot = PLACE[ref]
        fp.SetOrientationDegrees(rot); fp.SetPosition(mm(x, y))
    if missing: raise KeyError(f"not placed: {missing}")


# ---------------------------------------------------------------- checks and pictures
def courtyard_overlaps(b):
    out = []
    fps = [(fp.GetReference(), fp.GetCourtyard(pcbnew.F_CrtYd)) for fp in b.GetFootprints()]
    for i in range(len(fps)):
        for j in range(i + 1, len(fps)):
            a, b2 = fps[i][1], fps[j][1]
            if a.OutlineCount() == 0 or b2.OutlineCount() == 0: continue
            x = pcbnew.SHAPE_POLY_SET(a); x.BooleanIntersection(b2)
            if x.OutlineCount() and x.Area() > 0.01 * MM * MM: out.append((fps[i][0], fps[j][0], round(x.Area() / MM / MM, 2)))
    return out


def render(b, png, title="", zones=True, scale=14, win=None):
    """Top view for review: F.Cu pads coloured by voltage class, courtyards, refs, zones, tracks (F red, B blue), vias.
    win = (x0, y0, x1, y1) in board mm zooms in on one area."""
    wx0, wy0, wx1, wy1 = win or (0, 0, W, H)
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon, Circle
    col = {"HVIN": "#d62728", "HVF": "#ff7f0e", "HVSW": "#9467bd", "PWR": "#2ca02c", "DRV": "#17becf", "Default": "#7f7f7f"}
    fig, ax = plt.subplots(figsize=(W / 6.0, W / 6.0 * (wy1 - wy0) / (wx1 - wx0)), dpi=100)
    ax.add_patch(Polygon([(0, 0), (W, 0), (W, H), (0, H)], closed=True, fc="#f4f1e8", ec="k", lw=1))
    def pts(o): return [(o.CPoint(i).x / MM - OX, o.CPoint(i).y / MM - OY) for i in range(o.PointCount())]
    if zones:
        for z in b.Zones():
            nc = netclass_of(z.GetNetname()); c = col.get(nc, "#7f7f7f")
            for L in (pcbnew.F_Cu, pcbnew.B_Cu):
                if not z.IsOnLayer(L) or z.GetNetname() == "GND" and L == pcbnew.F_Cu and False: continue
                fill = z.GetFilledPolysList(L) if z.IsFilled() else None
                polys = fill if fill is not None and fill.OutlineCount() else z.Outline()
                for k in range(polys.OutlineCount()):
                    if z.GetNetname() == "GND" and L == pcbnew.B_Cu: continue
                    ax.add_patch(Polygon(pts(polys.Outline(k)), closed=True, fc=c, alpha=0.18 if L == pcbnew.F_Cu else 0.08,
                                         ec=c, lw=0.6, ls="-" if L == pcbnew.F_Cu else "--"))
    for t in b.GetTracks():
        if t.GetClass() == "PCB_VIA":
            p = t.GetPosition(); ax.add_patch(Circle((p.x / MM - OX, p.y / MM - OY), t.GetWidth(pcbnew.F_Cu) / MM / 2,
                                                     fc="#444" if t.GetNetname() == "GND" else col.get(netclass_of(t.GetNetname()), "#777"), ec="k", lw=0.3))
        else:
            s, e = t.GetStart(), t.GetEnd()
            ax.plot([s.x / MM - OX, e.x / MM - OX], [s.y / MM - OY, e.y / MM - OY], color="#c0392b" if t.GetLayer() == pcbnew.F_Cu else "#2c64c9",
                    lw=t.GetWidth() / MM * 72 * 0.91 * fig.get_size_inches()[0] / (wx1 - wx0), alpha=0.75, solid_capstyle="round")
    for fp in b.GetFootprints():
        cy = fp.GetCourtyard(pcbnew.F_CrtYd)
        for k in range(cy.OutlineCount()):
            ax.add_patch(Polygon(pts(cy.Outline(k)), closed=True, fill=False, ec="#b04fb0", lw=0.5))
        for p in fp.Pads():
            ps = pcbnew.SHAPE_POLY_SET(); p.TransformShapeToPolygon(ps, pcbnew.F_Cu if p.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu, 0, int(0.01 * MM), pcbnew.ERROR_INSIDE)
            n = p.GetNetname(); c = "#555" if n == "GND" else col.get(netclass_of(n), "#999") if n else "#ddd"
            for k in range(ps.OutlineCount()):
                ax.add_patch(Polygon(pts(ps.Outline(k)), closed=True, fc=c, ec="k", lw=0.2))
        c = fp.GetPosition()
        bb = fp.GetCourtyard(pcbnew.F_CrtYd).BBox() if cy.OutlineCount() else fp.GetBoundingBox(False)
        ax.text(bb.GetCenter().x / MM - OX, bb.GetCenter().y / MM - OY, fp.GetReference(), ha="center", va="center", fontsize=7,
                color="#1a1a6e", weight="bold")
    ax.set_xlim(wx0 - 2 * (not win), wx1 + 2 * (not win)); ax.set_ylim(wy1 + 2 * (not win), wy0 - 2 * (not win)); ax.set_aspect("equal")
    st = 5 if not win else 1
    ax.set_xticks(range(int(wx0), int(wx1) + 1, st)); ax.set_yticks(range(int(wy0), int(wy1) + 1, st)); ax.tick_params(labelsize=6); ax.grid(lw=0.2, alpha=0.5)
    ax.set_title(title, fontsize=9)
    fig.tight_layout(); fig.savefig(png); plt.close(fig)


# ---------------------------------------------------------------- copper
def P(b, ref, num):
    """Pad centre in board coordinates."""
    p = next(p for p in b.FindFootprintByReference(ref).Pads() if p.GetNumber() == str(num))
    return (p.GetPosition().x / MM - OX, p.GetPosition().y / MM - OY)


def PB(b, ref, num):
    """Pad bounding box (x0, y0, x1, y1) in board coordinates."""
    p = next(p for p in b.FindFootprintByReference(ref).Pads() if p.GetNumber() == str(num))
    bb = p.GetBoundingBox()
    return (bb.GetLeft() / MM - OX, bb.GetTop() / MM - OY, bb.GetRight() / MM - OX, bb.GetBottom() / MM - OY)


def exempt_rect(b, ref):
    """U1's courtyard plus 1 mm on the side its gate-drive pins fan out (board coordinates)."""
    bb = b.FindFootprintByReference(ref).GetCourtyard(pcbnew.F_CrtYd).BBox()
    return (bb.GetLeft() / MM - OX - 1.0, bb.GetTop() / MM - OY, bb.GetRight() / MM - OX, bb.GetBottom() / MM - OY)


def zone(b, net, layers, pts, prio, thermal=False, minw=0.25, name=""):
    z = pcbnew.ZONE(b)
    ls = pcbnew.LSET()
    for L in layers: ls.AddLayer(L)
    z.SetLayerSet(ls)
    z.SetNet(b.FindNet(net))
    ol = z.Outline(); ol.NewOutline()
    for x, y in pts: ol.Append(int(round((OX + x) * MM)), int(round((OY + y) * MM)))
    z.SetAssignedPriority(prio)
    z.SetLocalClearance(int(MIN_CLEAR * MM))
    z.SetMinThickness(int(minw * MM))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THT_THERMAL if thermal else pcbnew.ZONE_CONNECTION_FULL)
    z.SetThermalReliefGap(int(0.4 * MM)); z.SetThermalReliefSpokeWidth(int(0.6 * MM))
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    if name: z.SetZoneName(name)
    b.Add(z)
    return z


F, B_, I1, I2 = pcbnew.F_Cu, pcbnew.B_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu
PWR_STAGE_GND_VIAS = []                  # filled by power_copper(): (x, y) of the hand-placed hot-loop ground vias


def pours(b):
    """Copper areas. Power nets on F.Cu (2 oz), drawn around the parts that carry the current; KiCad's filler keeps
    every clearance (the HV rules included) and removes islands. GND: In1 and In2 solid, F.Cu and B.Cu flood."""
    zone(b, "/Inputs/VIN_AV", [F], [(23.2, 11.6), (40.0, 11.6), (40.0, 27.6), (37.0, 27.6), (37.0, 35.0), (33.0, 35.0),
                                   (33.0, PB(b, "D4", 1)[3] + 0.2), (25.0, PB(b, "D4", 1)[3] + 0.2), (25.0, 38.4), (23.2, 38.4)], 10,
         name="VIN_AV")
    zone(b, "VIN_PROT", [F], [(41.0, 10.5), (61.9, 10.5), (61.9, 17.4), (58.9, 17.4), (58.9, 32.6), (47.0, 32.6),
                              (47.0, 21.6), (41.0, 21.6)], 10, name="VIN_PROT")
    zone(b, "VIN_PROT", [B_], [(41.0, 10.5), (61.9, 10.5), (61.9, 17.4), (58.4, 17.4), (58.4, 21.6), (41.0, 21.6)], 5,
         name="VIN_PROT_B")
    zone(b, "/Buck_12V/SW12", [F], [(62.6, 13.75), (64.3, 13.75), (64.3, 11.6), (70.3, 11.6), (70.3, 10.95), (71.7, 10.95),
                                    (71.7, 12.2), (69.6, 12.2), (69.6, 18.4), (68.9, 18.4),
                                    (68.9, 21.9), (59.5, 21.9), (59.5, 18.0), (62.6, 18.0)], 10, name="SW12")
    zone(b, "/Buck_12V/SNS12", [F], [(59.5, 25.5), (68.9, 25.5), (68.9, 28.6), (62.5, 28.6), (62.5, 34.0), (59.6, 34.0)], 10,
         name="SNS12")
    zone(b, "+12V", [F], [(65.4, 29.4), (86.6, 29.4), (86.6, 33.5), (81.6, 33.5), (81.6, 43.0), (65.4, 43.0)], 9, name="+12V")
    zone(b, "/Out_12V/VTX_12V", [F], [(88.8, 29.5), (97.3, 29.5), (97.3, 32.3), (88.8, 32.3)], 10, name="VTX_12V")
    zone(b, "+5V", [F], [(84.6, 49.2), (88.9, 49.2), (88.9, 55.2), (87.0, 55.2), (87.0, 57.8), (84.6, 57.8)], 10, name="+5V")
    zone(b, "/Buck_5V/SW5", [F], [(84.55, 47.45), (85.45, 47.45), (85.45, 48.55), (84.4, 49.3), (84.4, 53.6), (80.6, 53.6),
                                  (80.6, 51.6), (83.1, 51.6), (83.1, 49.3), (84.55, 48.55)], 10, name="SW5")
    zone(b, "GND", [F], [(70.2, 13.75), (72.6, 13.75), (72.6, 17.7), (70.2, 17.7)], 10, name="Q2_SOURCE")
    for ref in EXEMPT:                                         # rule area for the IC pin-field exemption (.kicad_dru)
        x0, y0, x1, y1 = exempt_rect(b, ref)
        # The router exempts a track by its centreline; the copper reaches half a width (0.2 mm) further, plus one grid
        # cell. The rule area is the router's region grown by that much, so every bit of copper the router spaced at
        # 0.2 mm lies inside it, and everything outside it has the full spacing (pinfield_audit checks this).
        g = EXEMPT_EDGE; x0, y0, x1, y1 = x0 - g, y0 - g, x1 + g, y1 + g
        ra = pcbnew.ZONE(b); ls = pcbnew.LSET(); ls.AddLayer(F); ra.SetLayerSet(ls)          # F.Cu: where the pins are
        ra.SetIsRuleArea(True); ra.SetDoNotAllowTracks(False); ra.SetDoNotAllowVias(False); ra.SetDoNotAllowPads(False)
        ra.SetDoNotAllowCopperPour(False); ra.SetDoNotAllowFootprints(False); ra.SetZoneName(f"{ref}_PINS")
        ol = ra.Outline(); ol.NewOutline()
        for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)): ol.Append(int(round((OX + x) * MM)), int(round((OY + y) * MM)))
        b.Add(ra)
    e = 0.3
    board = [(e, e), (W - e, e), (W - e, H - e), (e, H - e)]
    zone(b, "GND", [F], board, 1, thermal=True, name="GND_F")
    zone(b, "GND", [B_], board, 1, thermal=True, name="GND_B")
    zone(b, "GND", [I1, I2], board, 0, thermal=True, name="GND_PLANES")


def track(b, net, pts, w, layer=F):
    for a, c in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(b); t.SetStart(mm(*a)); t.SetEnd(mm(*c)); t.SetWidth(int(round(w * MM)))
        t.SetLayer(layer); t.SetNet(b.FindNet(net)); b.Add(t)


def via(b, net, c, size=VIA):
    v = pcbnew.PCB_VIA(b); v.SetPosition(mm(*c)); v.SetWidth(int(round(size[0] * MM))); v.SetDrill(int(round(size[1] * MM)))
    v.SetNet(b.FindNet(net)); v.SetLayerPair(F, B_); b.Add(v)
    return v


def power_copper(b):
    """Copper drawn by hand before the router runs: the pack inputs, the hot-loop vias, the exposed-pad vias, the 5 V
    input loop and the Kelvin taps on the sense resistor."""
    for k in (1, 2, 3):                                        # J pin 1 -> fuse -> diode anode, 1.0 mm (0.7 A worst case)
        track(b, f"/Inputs/PACK{k}+", [P(b, f"J{k}", 1), P(b, f"F{k}", 1)], 1.0)
        track(b, f"/Inputs/PACK{k}_F", [P(b, f"F{k}", 2), P(b, f"D{k}", 2)], 1.0)
    # 12 V hot loop: three vias beside each input capacitor's ground pad, four beside Q2's sources (zone Q2_SOURCE)
    for ref in ("C2", "C3"):
        x, y = P(b, ref, 2)
        track(b, "GND", [(x, y), (51.35, y)], 1.0)
        track(b, "GND", [(51.35, y - 0.9), (51.35, y + 0.9)], 0.8)
        for dy in (-0.9, 0.0, 0.9): via(b, "GND", (51.35, y + dy)); PWR_STAGE_GND_VIAS.append((51.35, y + dy))
    for y in (14.4, 15.4, 16.4, 17.3): via(b, "GND", (71.9, y)); PWR_STAGE_GND_VIAS.append((71.9, y))
    # 12 V output capacitors sit inside the +12V pour: their ground pads get two vias each, outside the pad
    for ref, dx in (("C11", 2.5), ("C12", 1.6), ("C13", 1.2), ("C14", 1.2)):     # C12: C20's pad is 2.9 mm right
        x, y = P(b, ref, 2)
        track(b, "GND", [(x, y), (x + dx, y)], 1.0)
        for dy in (-0.6, 0.6): via(b, "GND", (x + dx, y + dy))
        track(b, "GND", [(x + dx, y - 0.6), (x + dx, y + 0.6)], 0.8)
    # VIN_PROT: stitch the F.Cu and B.Cu pours, and a row above Q1's tab to pull its heat into both
    for x in (57.6, 58.6, 59.6, 60.6, 61.4): via(b, "VIN_PROT", (x, 11.3))
    for x in (42.5, 45.0, 47.5):
        for y in (12.0, 14.5, 17.0): via(b, "VIN_PROT", (x, y))
    # exposed pads: thermal vias (U1 EP is ground, U3 EP is ground)
    x, y = P(b, "U1", 25)
    for dx in (-0.8, 0.8):
        for dy in (-1.0, 0.0, 1.0): via(b, "GND", (x + dx, y + dy))
    x, y = P(b, "U3", 11)
    for dy in (-0.7, 0.7): via(b, "GND", (x, y + dy))
    for ref, pin, ep in EP_TIES:                               # ground pins beside an exposed pad: tie them to it
        track(b, "GND", [P(b, ref, pin), P(b, ref, ep)], 0.25)
    # LT8641: its two exposed SW pads join pins 8/9; VIN pins neck down from the input capacitors
    (x21, y21), (x22, y22) = P(b, "U2", 21), P(b, "U2", 22)
    track(b, "/Buck_5V/SW5", [(x22, y22), (x21, y21), (x21, P(b, "U2", 8)[1])], 0.2)
    for pin, cap, dx in ((4, "C15", -0.65), (13, "C16", 0.65)):
        px, py = P(b, "U2", pin); cx, cy = P(b, cap, 1)
        track(b, "+12V", [(px, py), (px + dx, py)], 0.25); track(b, "+12V", [(px + dx, py), (cx, cy)], 0.6)
    # Kelvin taps: one via just inside each pad's inner edge, the sense lines leave from there on B.Cu
    p1, p2 = PB(b, "R1", 1), PB(b, "R1", 2)
    yc = P(b, "R1", 1)[1]
    k1, k2 = (p1[2] + 0.45, yc), (p2[0] - 0.45, yc)
    track(b, "/Buck_12V/SNS12", [(p1[2] - 0.3, yc), k1], 0.5); track(b, "+12V", [(p2[0] + 0.3, yc), k2], 0.5)
    via(b, "/Buck_12V/SNS12", k1); via(b, "+12V", k2)
    return k1, k2


def fresh():
    """Re-export the schematic's netted, unplaced board (kicad_avionics.export) so the layout always starts from it."""
    import kicad_avionics
    kicad_avionics.export()


def fill(b):
    """Pour the zones. pcbnew.LoadBoard does not load the .kicad_dru into the board's DRC engine, and the zone filler asks
    that engine for each clearance, so a bare fill uses the net-class clearance (0.2 mm) everywhere and ignores the
    HV rules. WriteDRCReport loads the rules file into the engine (and runs a DRC we throw away); the filler then
    knocks the pours back by the right amount."""
    import tempfile
    pcbnew.WriteDRCReport(b, os.path.join(tempfile.gettempdir(), "avionics_prime_drc.rpt"), pcbnew.EDA_UNITS_MM, False)
    b.BuildConnectivity()
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.BuildConnectivity()


def width_for(net):
    c = netclass_of(net)
    if net in ("VIN_PROT",): return 0.5
    if net in ("+5V", "+3V3"): return 0.5                # the pours carry the load current; routed taps feed ICs (< 0.5 A)
    return {"HVIN": 1.0, "HVF": 0.4, "HVSW": 0.4, "PWR": 0.8, "DRV": 0.4}.get(c, 0.25) if net != "GND" else 0.4


def pad_layers(p):
    if p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH,): return (F, B_)
    return (F,) if p.IsOnLayer(F) else (B_,)


def islands(b, net):
    """Groups of pads of one net that copper already joins: tracks and vias (KiCad's neighbour lists) and zone fills
    (pad, via or track end inside or within reach of a filled outline, all layers)."""
    code = b.FindNet(net).GetNetCode()
    c = b.GetConnectivity()
    pads = [p for fp in b.GetFootprints() for p in fp.Pads() if p.GetNetCode() == code]
    tracks = [t for t in b.GetTracks() if t.GetNetCode() == code]
    items = pads + tracks
    uid = {x.m_Uuid.AsString(): i for i, x in enumerate(items)}
    par = list(range(len(items)))
    def find(i):
        while par[i] != i: par[i] = par[par[i]]; i = par[i]
        return i
    def union(i, j): par[find(i)] = find(j)
    for j, t in enumerate(tracks):
        n = len(pads) + j
        for q in list(c.GetConnectedPads(t)) + list(c.GetConnectedTracks(t)):
            k = uid.get(q.m_Uuid.AsString())
            if k is not None: union(n, k)
    for z in b.Zones():
        if z.GetNetCode() != code or z.GetIsRuleArea(): continue
        for L in (F, I1, I2, B_):
            if not z.IsOnLayer(L) or not z.HasFilledPolysForLayer(L): continue
            fp = z.GetFilledPolysList(L)
            for k in range(fp.OutlineCount()):
                ch = fp.Outline(k); members = []
                for i, x in enumerate(items):
                    if not x.IsOnLayer(L): continue
                    if i < len(pads):
                        r = int(max(x.GetSize(L).x, x.GetSize(L).y) / 2 + 0.5 * MM)
                        pts = [x.GetPosition()]
                    elif x.GetClass() == "PCB_VIA":
                        r = int(x.GetWidth(L) / 2 + 0.05 * MM); pts = [x.GetPosition()]
                    else:
                        r = int(x.GetWidth() / 2 + 0.05 * MM); pts = [x.GetStart(), x.GetEnd()]
                    if any(ch.PointInside(pt) or ch.Collide(pt, r) for pt in pts): members.append(i)
                for i in members[1:]: union(members[0], i)
    groups = {}
    for i, p in enumerate(pads): groups.setdefault(find(i), []).append(p)
    return list(groups.values())


def abs_pt(p):
    return (p.GetPosition().x / MM, p.GetPosition().y / MM)


def route_pads(R, net, pa, pb, widths, layers=(F, B_), margin=8.0):
    """Join two pads: every width (widest first) in a window `margin` around them, then once more in a wider window."""
    for m in (margin, 20.0):
        items, w = R.connect(net, abs_pt(pa), abs_pt(pb), list(widths), start_layers=pad_layers(pa), goal_layers=pad_layers(pb),
                             layers=layers, margin=m)
        if items is not None: return items, w
    return None, None


def build_router(b):
    from kicad_route import Router
    ex = []
    for ref in EXEMPT:
        x0, y0, x1, y1 = exempt_rect(b, ref)
        ex.append((OX + x0, OY + y0, OX + x1, OY + y1))
    return Router(b, (OX, OY), (W, H), lambda n: hv_group(netclass_of(n)), lambda a, c: clearance(a, c), exempt=ex,
                  min_clear=MIN_CLEAR, via=VIA, exempt_layers=(F,))


F_CRT = pcbnew.F_CrtYd
LOG = []


def log(*a):
    s = " ".join(str(x) for x in a); LOG.append(s); print(s, flush=True)


def widths_for(net):
    """Widths to try, widest first, never wider than the net's own width (a signal does not take a power track's room)."""
    w0 = width_for(net)
    return sorted({w for w in (w0, 0.4, 0.3, 0.25, 0.2) if w <= w0 + 1e-9}, reverse=True)


# pins tied to an exposed ground pad beside them by a short stub (power_copper), so they need no fan-out via that would
# sit in the escape lane of the next pin
EP_TIES = [("U1", "6", "25"), ("U3", "8", "11")]


def route(b, kelvin, prio=()):
    """Ordered routing. The Kelvin pair first (then guarded), then the explicit connections around U1 (EXTVCC, VIN,
    the DRVSET tie, gate drive, driver supply), then every remaining island of every net, nearest pads first.
    prio: nets that failed in an earlier pass. They go ahead of everything after the Kelvin pair and ahead of the
    ground fan-out vias (rip-up and retry: the whole layout is redone, so nothing has to be torn out by hand).
    Returns the router and the failures [(net, description)]."""
    R = build_router(b)
    A = lambda pt: (OX + pt[0], OY + pt[1])
    pad = lambda ref, n: next(p for p in b.FindFootprintByReference(ref).Pads() if p.GetNumber() == str(n))
    # Kelvin sense pair on B.Cu from the R1 taps to vias beside U1's sense pins, then guarded
    k1, k2 = kelvin
    u24, u1 = P(b, "U1", 24), P(b, "U1", 1)
    t1, t2 = (u24[0] + 0.5, u24[1] + 1.75), (u1[0] - 0.4, u1[1] + 1.75)
    guarded = []
    for net, a, c, pin, cap in (("/Buck_12V/SNS12", k1, t1, ("U1", 24), ("C4", 1)), ("+12V", k2, t2, ("U1", 1), ("C4", 2))):
        items = R.connect(net, A(a), A(c), 0.3, start_layers=(B_,), goal_layers=(B_,), layers=(B_,), margin=10)
        if items is None: log("Kelvin route failed", net); continue
        v = R.add_via(R.code(net), A(c))
        tr = [R.add_track(R.code(net), A(c), A(P(b, *pin)), 0.3, F), R.add_track(R.code(net), A(c), A(P(b, *cap)), 0.3, F)]
        guarded += items + [v] + tr
        log(f"Kelvin {net}: {len(items)} items")
    R.guard(guarded)
    kelvin_pads = {pad(r, n).m_Uuid.AsString() for r, n in (("U1", 1), ("U1", 24), ("C4", 1), ("C4", 2))}
    failed = []
    # explicit connections around U1: (net, from pad, to pad or to a point in a pour)
    # U1's left pins 19-23 all leave to the left and turn down. In this order nothing has to cross: INTVCC (22) dives
    # to B.Cu at the pin, OVLO (23) then RUN (21) wrap around to their dividers below the IC, EXTVCC (20) goes down
    # outside them to the +12V pour, and VIN (19) runs on B.Cu under the IC to the VIN_PROT end of the OVLO divider.
    steps = [("/Buck_12V/INTVCC12", ("U1", 22), ("U1", 5)), ("/Buck_12V/OVLO12", ("U1", 23), ("R4", 2)),
             ("/Buck_12V/RUN12", ("U1", 21), ("R2", 2)),
             ("+12V", ("U1", 20), (80.0, 30.5)),                       # EXTVCC into the +12V pour, not onto the Kelvin line
             ("VIN_PROT", ("U1", 19), ("R4", 1)),
             ("/Buck_12V/TG12", ("U1", 13), ("Q1", 4)), ("/Buck_12V/SW12", ("U1", 14), (68.4, 11.9)),
             ("/Buck_12V/BST12", ("U1", 15), ("C5", 1)), ("/Buck_12V/BG12", ("U1", 16), ("Q2", 4)),
             ("/Buck_12V/DRVCC12", ("U1", 17), ("Q3", 3)), ("/Buck_12V/NDRV12", ("U1", 18), ("Q3", 1)),
             ("/Buck_12V/DRVCC12", ("Q3", 3), ("C6", 1))]
    steps.sort(key=lambda st: st[0] not in prio)                       # stable: earlier failures first
    for net, a, c in steps:
        pa = pad(*a)
        if isinstance(c[0], str):
            items, w = route_pads(R, net, pa, pad(*c), widths_for(net))
        else:
            items, w = R.connect(net, abs_pt(pa), A(c), widths_for(net), start_layers=(F,), goal_layers=(F,), margin=10)
        tag = f"{net} {a[0]}.{a[1]} -> {c[0] + '.' + str(c[1]) if isinstance(c[0], str) else c}"
        log(f"{tag}: {'w %.2f' % w if items else 'FAILED'}")
        if items is None: failed.append((net, tag))

    def join(nets):
        """Join the islands of each net, nearest pads first; returns (connections attempted, failures)."""
        todo, bad = 0, []
        for net in nets:
            isl = islands(b, net)
            stuck = set()                                      # pads of islands that could not be joined this round
            while True:
                main = max(isl, key=len)
                rest = [p for g in isl if g is not main for p in g if p.m_Uuid.AsString() not in stuck]
                if not rest: break
                todo += 1
                d2 = lambda xy: (abs_pt(xy[0])[0] - abs_pt(xy[1])[0]) ** 2 + (abs_pt(xy[0])[1] - abs_pt(xy[1])[1]) ** 2
                pairs = sorted(((x, y) for x in main for y in rest), key=d2)
                seen, cand = set(), []
                for pa, pb in pairs:                           # the nearest few distinct pad pairs
                    k = (pa.m_Uuid.AsString(), pb.m_Uuid.AsString())
                    if kelvin_pads & set(k): continue          # the Kelvin pins take no other connection
                    if k not in seen: seen.add(k); cand.append((pa, pb))
                    if len(cand) == 8: break
                items = None
                if not cand: bad.append((net, net + " (only Kelvin pads left)")); log("  NO CANDIDATES", net); break
                for pa, pb in cand:
                    items, w = route_pads(R, net, pb, pa, widths_for(net))
                    if items is not None: break
                tag = f"{net} {pb.GetParentFootprint().GetReference()}.{pb.GetNumber()} -> {pa.GetParentFootprint().GetReference()}.{pa.GetNumber()}"
                if items is None:                               # give up on this island only; try the net's others
                    bad.append((net, tag)); log("  FAILED", tag)
                    g = next(g for g in isl if any(p.m_Uuid.AsString() == pb.m_Uuid.AsString() for p in g))
                    stuck |= {p.m_Uuid.AsString() for p in g}
                    continue
                log(f"  {tag}: w {w}")
                b.BuildConnectivity()
                n0 = len(isl); isl = islands(b, net)
                if len(isl) >= n0:
                    bad.append((net, tag + " (routed but still apart)")); log("  NO PROGRESS", tag); break
        return todo, bad

    # small-signal nets first (they need the short paths between IC pins), then the drive and power nets, ground last
    rank = lambda n: (n not in prio, n == "GND", {"Default": 0, "DRV": 1, "HVF": 2, "HVSW": 2, "HVIN": 3, "PWR": 4}[netclass_of(n)], n)
    nets = sorted({p.GetNetname() for fp in b.GetFootprints() for p in fp.Pads() if p.GetNetname() and not p.GetNetname().startswith("unconnected")}, key=rank)
    if prio: join([n for n in nets if n in prio])
    # ground: a via beside every SMD ground pad (not the hot-loop parts, the exposed pads or the pins tied to them)
    skip = {(r, p) for r, p, _ in EP_TIES} | {("U1", "25"), ("U3", "11")}
    nf = 0
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() != "GND" or p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH: continue
            if fp.GetReference() in ("C2", "C3", "C11", "C12", "C13", "C14", "Q2") or (fp.GetReference(), p.GetNumber()) in skip: continue
            if R.fanout(p, 0.4) or R.fanout(p, 0.25): nf += 1
            else: log(f"no fan-out via for {fp.GetReference()}.{p.GetNumber()}")
    log(f"ground fan-out vias: {nf}")
    fill(b)
    bad = []
    for rnd in range(3):
        todo, bad = join(nets)
        fill(b)
        if not todo: break
    return R, failed + bad


SILK_H, SILK_T = 0.8, 0.15             # reference text height and stroke (JLC: stroke >= 0.15 mm stays legible)


def silk(b):
    """Reference designators. Each one goes to the first spot around its part (on the body for big parts, then above,
    below, left, right, then the corners; upright or turned 90 deg) that is clear of every pad, every other silkscreen
    line and text, and the board edge. A part with no free spot keeps its reference on F.Fab only (assembly drawing)."""
    V = lambda x, y: pcbnew.VECTOR2I(int(round(x * MM)), int(round(y * MM)))
    pads = [p.GetEffectiveShape(F) for fp in b.GetFootprints() for p in fp.Pads() if p.IsOnLayer(F)]
    lines = [g.GetEffectiveShape() for fp in b.GetFootprints() for g in fp.GraphicalItems()
             if g.GetLayer() == pcbnew.F_SilkS and g.GetClass() == "PCB_SHAPE"]
    placed = []
    x0, y0, x1, y1 = OX + 0.5, OY + 0.5, OX + W - 0.5, OY + H - 0.5
    hidden = []
    for fp in sorted(b.GetFootprints(), key=lambda f: -f.GetCourtyard(F_CRT).BBox().GetArea()):
        t = fp.Reference()
        if fp.GetReference().startswith("H"): t.SetVisible(False); continue
        t.SetTextSize(V(SILK_H, SILK_H)); t.SetTextThickness(int(SILK_T * MM)); t.SetKeepUpright(True)
        bb = fp.GetCourtyard(F_CRT).BBox()
        if bb.GetWidth() == 0: bb = fp.GetBoundingBox(False)
        cx, cy = bb.GetCenter().x / MM, bb.GetCenter().y / MM
        hw, hh = bb.GetWidth() / MM / 2, bb.GetHeight() / MM / 2
        tw = 0.6 * SILK_H * len(fp.GetReference()) / 2 + 0.1     # half-length of the text, a little generous
        th = SILK_H / 2 + 0.1
        spots = []
        if hw > 2.0 and hh > 2.0: spots += [(cx, cy, 0), (cx, cy, 90)]
        spots += [(cx, cy - hh - th, 0), (cx, cy + hh + th, 0), (cx - hw - th, cy, 90), (cx + hw + th, cy, 90),
                  (cx - hw - tw, cy, 0), (cx + hw + tw, cy, 0), (cx, cy - hh - tw, 90), (cx, cy + hh + tw, 90),
                  (cx - hw - tw, cy - hh - th, 0), (cx + hw + tw, cy - hh - th, 0),
                  (cx - hw - tw, cy + hh + th, 0), (cx + hw + tw, cy + hh + th, 0)]
        ok = False
        for x, y, a in spots:
            t.SetTextAngle(pcbnew.EDA_ANGLE(a, pcbnew.DEGREES_T)); t.SetPosition(V(x, y))
            s = t.GetEffectiveShape(pcbnew.F_SilkS); r = s.BBox()
            if r.GetLeft() < x0 * MM or r.GetRight() > x1 * MM or r.GetTop() < y0 * MM or r.GetBottom() > y1 * MM: continue
            if any(s.Collide(o, int(0.15 * MM)) for o in pads): continue
            if any(s.Collide(o, int(0.1 * MM)) for o in lines + placed): continue
            ok = True; break
        if ok:
            t.SetVisible(True); placed.append(t.GetEffectiveShape(pcbnew.F_SilkS))
        else:
            t.SetVisible(False); hidden.append(fp.GetReference())
    return hidden


def drc(b):
    rep = os.path.join(OUT, NAME + "_drc.json")
    subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "--severity-all", "--schematic-parity", "-o", rep, PCB],
                   capture_output=True)
    d = json.load(open(rep))
    from collections import Counter
    v = d.get("violations", [])
    cnt = Counter((x["severity"], x["type"]) for x in v)
    return d, cnt


def pinfield_audit(b):
    """Check the exemption is not being abused. The DRC rule lets two items 0.2 mm apart when both *touch* the pin-field
    area, so a long track that leaves the area keeps the 0.2 mm allowance along its whole length. Here every pair of
    such items (different nets, groups that need more than 0.2 mm) is cut back to the copper outside the area, and
    the gap between what is left is measured by bisection on KiCad's own shape collision test.
    Returns [(net A, net B, gap mm, needed mm)] for pairs closer than they should be outside the pin field."""
    group = lambda n: c if (c := netclass_of(n)) in HV else "LV"
    need = lambda a, b_: CLEAR.get((a, b_)) or CLEAR.get((b_, a)) or MIN_CLEAR
    bad = []
    for ref in EXEMPT:
        area = next(z for z in b.Zones() if z.GetZoneName() == f"{ref}_PINS").Outline()
        items = [t for t in b.GetTracks() if t.IsOnLayer(F)] + [p for fp in b.GetFootprints() for p in fp.Pads() if p.IsOnLayer(F)]
        out = []
        for it in items:
            if not it.GetEffectiveShape(F).Collide(area.Outline(0), 0) and not area.Contains(it.GetPosition()): continue
            ps = pcbnew.SHAPE_POLY_SET()
            it.TransformShapeToPolygon(ps, F, 0, int(0.005 * MM), pcbnew.ERROR_OUTSIDE)
            ps.BooleanSubtract(area)
            if ps.OutlineCount(): out.append((it.GetNetname(), group(it.GetNetname()), ps))
        for i, (na, ga, pa) in enumerate(out):
            for nb, gb, pb in out[i + 1:]:
                r = need(ga, gb)
                if na == nb or r <= MIN_CLEAR or not pa.Collide(pb, int(r * MM) - 1000): continue
                lo, hi = 0.0, r                   # the item pair touches inside r: find the actual gap
                for _ in range(12):
                    m = (lo + hi) / 2
                    lo, hi = (lo, m) if pa.Collide(pb, int(m * MM)) else (m, hi)
                bad.append((na, nb, round(hi, 3), r))
    return bad


def fab():
    """JLCPCB files in kicad/Avionics_Board/jlcpcb/: Gerbers + Excellon drill (zipped), BOM and CPL in JLC's column format.
    The LCSC column is left empty: JLC matches on the manufacturer part number in 'Comment' or you pick parts there."""
    import csv, zipfile, glob, shutil
    d = os.path.join(OUT, "jlcpcb"); g = os.path.join(d, "gerbers")
    shutil.rmtree(d, ignore_errors=True); os.makedirs(g)
    layers = "F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts"
    run = lambda *a: subprocess.run(["kicad-cli", "pcb", "export", *a, PCB], capture_output=True, text=True, check=True)
    run("gerbers", "--layers", layers, "--subtract-soldermask", "-o", g + "/")
    run("drill", "--format", "excellon", "--excellon-separate-th", "--generate-map", "--map-format", "gerberx2", "-o", g + "/")
    zp = os.path.join(d, f"{NAME}_gerbers.zip")
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(glob.glob(os.path.join(g, "*"))): z.write(f, os.path.basename(f))
    pos = os.path.join(d, "pos.csv")
    run("pos", "--format", "csv", "--units", "mm", "--side", "front", "--exclude-dnp", "-o", pos)
    spec = {}
    for row in csv.DictReader(open(os.path.join(HERE, "Avionics_BOM.csv"), encoding="utf-8")):
        for r in row["References"].split(): spec[r] = (row["Part number / specification"], row["Rating"])
    b = load()
    groups = {}
    for fp in b.GetFootprints():
        if fp.GetAttributes() & pcbnew.FP_EXCLUDE_FROM_BOM: continue
        ref = fp.GetReference(); pn, rating = spec.get(ref, ("", ""))
        comment = " ".join(x for x in (fp.GetValue(), pn, rating) if x)
        for a, c in (("µ", "u"), ("Ω", "R"), ("≤", "<="), ("≥", ">=")): comment = comment.replace(a, c)   # JLC's matcher
        key = (comment, fp.GetFPID().GetLibItemName().wx_str())
        groups.setdefault(key, []).append(ref)
    nat = lambda r: (re.sub(r"\d", "", r), int(re.sub(r"\D", "", r) or 0))
    with open(os.path.join(d, f"{NAME}_BOM_JLC.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        for (comment, fpn), refs in sorted(groups.items(), key=lambda kv: nat(sorted(kv[1], key=nat)[0])):
            w.writerow([comment, ",".join(sorted(refs, key=nat)), fpn, ""])
    with open(os.path.join(d, f"{NAME}_CPL_JLC.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for row in csv.DictReader(open(pos)):
            if row["Ref"].startswith("H"): continue
            w.writerow([row["Ref"], f"{float(row['PosX']):.3f}mm", f"{float(row['PosY']):.3f}mm",
                        "Top" if row["Side"] == "top" else "Bottom", f"{float(row['Rot']):.0f}"])
    os.remove(pos)
    return d, len(groups)


if __name__ == "__main__":
    step = sys.argv[1] if len(sys.argv) > 1 else "all"
    if step == "fab":
        print(fab()); sys.exit()
    def start():
        """The netted board from the schematic. The export rewrites the .kicad_pro, so the net classes go in after it."""
        fresh(); write_project(); write_rules()
        b = load(); setup(b); outline(b); place(b)
        return b
    if step == "place":
        b = start()
        log("courtyard overlaps:", courtyard_overlaps(b))
        render(b, os.path.join(OUT, "layout_place.png"), "placement")
        pcbnew.SaveBoard(PCB, b); write_project(); write_rules(); sys.exit()
    # rip-up and retry: lay the board out again with the nets that failed routed first, keep the best pass
    best, prio = None, []
    for n in range(1, 6):
        b = start()
        ov = courtyard_overlaps(b)
        if ov: log("courtyard overlaps:", ov)
        PWR_STAGE_GND_VIAS.clear()
        pours(b); kelvin = power_copper(b); fill(b)
        R, failed = route(b, kelvin, prio)
        fn = list(dict.fromkeys(n_ for n_, _ in failed))
        log(f"=== pass {n}: {len(failed)} failed connections {fn}")
        if best is None or len(failed) < len(best[2]): best = (b, R, failed, n)
        if not failed: break
        prio = fn + [x for x in prio if x not in fn]
    b, R, failed, n = best
    log(f"=== keeping pass {n}")
    pcbnew.SaveBoard(PCB, b)                                  # reload it with this project's net classes and rules:
    write_project(); write_rules(); b = load()                 # the later passes' exports rewrote the project file
    fill(b)
    hidden = silk(b)
    log("references kept on F.Fab only (no room on the silkscreen):", " ".join(hidden))
    pcbnew.SaveBoard(PCB, b); write_project(); write_rules()   # SaveBoard rewrites the .kicad_pro: put the classes back
    render(b, os.path.join(OUT, "layout_routed.png"), "routed")
    d, cnt = drc(b)
    nunc = len(d.get("unconnected_items", []))
    log("unrouted:", nunc, "failed routes:", len(failed))
    audit = pinfield_audit(b)
    log("pin-field audit, pairs short of full spacing outside the exempt area:", audit)
    for k, n in sorted(cnt.items()): log(f"  {k[0]:8s} {k[1]:28s} {n}")
    tr = [t for t in b.GetTracks() if t.GetClass() == "PCB_TRACK"]
    stats = dict(tracks=len(tr), vias=sum(1 for t in b.GetTracks() if t.GetClass() == "PCB_VIA"),
                 length_mm={b.GetLayerName(L): round(sum(t.GetLength() for t in tr if t.GetLayer() == L) / MM, 1) for L in (F, B_)},
                 routed_by_router=len(R.added), failed=failed, hidden_refs=hidden, unconnected=nunc,
                 drc={f"{k[0]}:{k[1]}": n for k, n in sorted(cnt.items())}, schematic_parity=len(d.get("schematic_parity", [])),
                 parts=sum(1 for fp in b.GetFootprints() if not fp.GetReference().startswith("H")),
                 pinfield_audit=audit)
    json.dump(stats, open(os.path.join(OUT, "layout_stats.json"), "w"), indent=1)

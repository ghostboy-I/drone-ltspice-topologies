"""ESC board: PCB layout for JLCPCB (4 layers, 1.6 mm, 2 oz outer / 1 oz inner copper, bus bars on the phase lanes).

    python3 pcb_esc.py            re-export the netted board from the schematic, then place, pour, route, fill, check
    python3 pcb_esc.py place      placement only (fast), with the render, for checking the floorplan
    python3 pcb_esc.py fab        Gerbers, drill, BOM and CPL for JLCPCB in kicad/ESC_Board/jlcpcb/

Same method as pcb_avionics.py (whose net-island and routing helpers it reuses), with a power stage that carries
116 A rms per phase:
  1. setup()      4 copper layers, net classes, the clearance groups (ESC_Board.kicad_dru)
  2. outline()    W x H board, 4 x M3 holes with a copper keep-out for the screw heads
  3. place()      every part at a computed or hand-chosen spot (placements()). Three identical legs side by side:
                    HS column (4 x D2PAK, drain tab = VBUS) | phase lane | LS column (tab = phase) | ground lane
                  The phase lane holds the HS gate resistors and a 4.5 mm mask-free strip for a soldered copper bar;
                  the ground lane holds the LS gate resistors, a via field into the inner ground plane and the next
                  leg's DC-link ceramics. 24 polymer capacitors in three rows of eight above the legs, J1 to their
                  right, the aux 12 V buck in the top-right corner, the low-current band below the legs.
  4. pours()      power copper as zones on all four layers; thermal vias in every FET tab; gate-drive copper by hand
  5. route()      the control and signal nets with kicad_route.Router (A* on a 0.05 mm grid, F.Cu + B.Cu)
  6. fill + DRC   zones filled by KiCad with the rules loaded, kicad-cli DRC, pinfield_audit()
"""
import os, sys, json, math, subprocess, re
import pcbnew
from pcb_avionics import abs_pt, pad_layers, route_pads, courtyard_overlaps

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "kicad", "ESC_Board")
NAME = "ESC_Board"
PCB = os.path.join(OUT, NAME + ".kicad_pcb")
LIB = os.path.join(HERE, "kicad", "Drone_Power.pretty")
MM = 1e6
OX, OY = 50.0, 40.0                      # board origin on the KiCad page
W, H = 175.0, 130.0                      # board size (mm)
mm = lambda x, y: pcbnew.VECTOR2I_MM(OX + x, OY + y)
F, B_, I1, I2 = pcbnew.F_Cu, pcbnew.B_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu

# ---------------------------------------------------------------- net classes and clearance groups
# The DC link is 24S: 100.8 V at 4.2 V per cell, 150 V FETs. IPC-2221B table 6-1, B2 (external, uncoated, up to
# 3050 m): 31-150 V -> 0.6 mm. Every net that can sit more than 30 V away from another gets its own group; nets that
# stay within 30 V of each other share one (a phase, its bootstrap supply and its high-side gates move together).
G = lambda qs: [f"Net-(Q{q}-G)" for q in qs]
CLASSES = {
    "HVBUS": dict(nets=["VBUS"], track=1.0, desc="DC link, up to 100.8 V"),
    "HVDIV1": dict(nets=["Net-(R1-Pad2)"], track=0.3, desc="bus divider, 2/3 of VBUS"),
    "HVDIV2": dict(nets=["Net-(R2-Pad2)"], track=0.3, desc="bus divider, 1/3 of VBUS"),
    "SW_A": dict(nets=["PH_A", "/Leg_A/BST_A", "/Leg_A/TG_A", "/Current_Sense/MOT_A"] + G(range(4, 8)), track=0.5,
                 desc="phase A, its bootstrap and high-side gates, 0-113 V"),
    "SW_B": dict(nets=["PH_B", "/Leg_B/BST_B", "/Leg_B/TG_B", "/Current_Sense/MOT_B"] + G(range(12, 16)), track=0.5,
                 desc="phase B"),
    "SW_C": dict(nets=["PH_C", "/Leg_C/BST_C", "/Leg_C/TG_C"] + G(range(20, 24)), track=0.5, desc="phase C"),
    "SW_AUX": dict(nets=["/Aux_12V/SW_AUX", "/Aux_12V/BST_AUX", "/Aux_12V/TG_AUX"], track=0.4,
                   desc="12 V aux switch node and its high-side drive"),
    "PWR": dict(nets=["GND", "+12V", "+5V", "+3V3", "/Aux_12V/SNS_AUX"], track=0.5, desc="low-voltage power"),
    "DRV": dict(nets=["/Leg_A/BG_A", "/Leg_B/BG_B", "/Leg_C/BG_C", "/Aux_12V/BG_AUX", "/Aux_12V/DRVCC_AUX",
                      "/Aux_12V/INTVCC_AUX", "/Aux_12V/NDRV_AUX"] + G(list(range(8, 12)) + list(range(16, 20)) + list(range(24, 28))),
                track=0.4, desc="low-side gate drive and driver supplies"),
}
HV = ("HVBUS", "HVDIV1", "HVDIV2", "SW_A", "SW_B", "SW_C", "SW_AUX")
HV_CLEAR = 0.6                           # B2, 31-150 V
INNER_HV = 0.3                           # inner layers: IPC B1 asks 0.2 mm up to 300 V; 0.3 keeps the via-field webs
MIN_CLEAR, MIN_TRACK, VIA = 0.2, 0.2, (0.6, 0.3)
EXEMPT = ["U1", "U4", "U5", "U6"]        # ICs whose own pinout puts a 100 V pin next to a low-voltage one
EXEMPT_EDGE = 0.25
# U1's left pin row (0.65 mm pitch) leaves through a two-column via fan-out: pins 17-23 alternate between a column
# 1.22 mm and one 2.27 mm left of the pin centres, so every stub to the outer column passes between two inner vias
# with 0.225 mm to spare. Pin 19 (VBUS) drops straight into the In2 VBUS plane; the rest continue on B.Cu.
U1_ESC = {17: -1.22, 18: -2.27, 19: -1.22, 20: -2.27, 21: -1.22, 22: -2.27, 23: -1.22}


def netclass_of(name):
    for c, d in CLASSES.items():
        if name in d["nets"]: return c
    return "Default"


def group(c):
    return c if c in HV else "LV"


def clearance(a, b, outer=True):
    """Clearance (mm) between copper of net classes a and b."""
    ga, gb = group(a), group(b)
    if ga == gb: return MIN_CLEAR
    if "LV" == ga == gb: return MIN_CLEAR
    return HV_CLEAR if outer else INNER_HV


def write_rules():
    """ESC_Board.kicad_dru. One rule covers every pair of groups: copper of an HV class keeps 0.6 mm from copper of any
    other class. KiCad tries each condition with the two items both ways round, so 'A is HV' also catches HV-as-B.
    The pin-field exemptions come last (KiCad applies the last matching rule)."""
    hv = " || ".join(f"A.NetClass == '{c}'" for c in HV)
    r = ["(version 1)", "",
         f"(rule \"HV group to any other copper: {HV_CLEAR} mm (IPC-2221B B2, 31-150 V)\"", "  (layer outer)",
         f"  (condition \"({hv}) && A.NetClass != B.NetClass && B.Net != '' && B.Type != 'Footprint'\")",
         f"  (constraint clearance (min {HV_CLEAR}mm)))", "",
         f"(rule \"HV group to unconnected copper: {HV_CLEAR} mm\"", "  (layer outer)",
         f"  (condition \"({hv}) && B.Net == '' && B.Type == 'Pad'\")",
         f"  (constraint clearance (min {HV_CLEAR}mm)))", "",
         f"(rule \"HV on inner layers: {INNER_HV} mm (IPC-2221B B1 asks 0.2 mm)\"", "  (layer inner)",
         f"  (condition \"({hv}) && A.NetClass != B.NetClass\")",
         f"  (constraint clearance (min {INNER_HV}mm)))", ""]
    for ref in EXEMPT:
        r += [f"(rule \"{ref} pin field: the IC's own pin pitch\"", "  (layer \"F.Cu\")",
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
                                 via_diameter=VIA[0], via_drill=VIA[1])
        classes.append(k)
    pro["net_settings"]["classes"] = classes
    pro["net_settings"]["netclass_patterns"] = [{"netclass": c, "pattern": n} for c, d in CLASSES.items() for n in d["nets"]]
    ds = pro["board"]["design_settings"]
    rules = ds.setdefault("rules", {})
    rules.update(min_clearance=MIN_CLEAR, min_track_width=MIN_TRACK, min_via_diameter=0.5, min_through_hole_diameter=0.3,
                 min_via_annular_width=0.13, min_copper_edge_clearance=0.4, min_hole_clearance=0.25, min_hole_to_hole=0.5,
                 min_silk_clearance=0.0, solder_mask_to_copper_clearance=0.0, min_text_height=0.8, min_text_thickness=0.12)
    ds["track_widths"] = [0.0, 0.25, 0.4, 0.5, 0.8, 1.0, 1.5]
    ds["via_dimensions"] = [{"diameter": 0.0, "drill": 0.0}, {"diameter": 0.6, "drill": 0.3}]
    json.dump(pro, open(p, "w"), indent=2)


# ---------------------------------------------------------------- placement (board frame: mm from the top-left corner)
Y0, PITCH = 51.9, 12.0                   # centre of the top FET row, FET pitch along a column
ROWS = [Y0 + PITCH * k for k in range(4)]
COL_TOP, COL_BOT = Y0 - 5.7, ROWS[-1] + 5.7          # courtyard extent of a FET column
LS_OFF = 26.0                            # LS column centre = HS column centre + 26 mm
DY = COL_BOT + 7.6                       # row of the gate drivers (bottom band)
# Per leg: HS column centre, first FET / resistor numbers (4 consecutive each), driver parts, DC-link ceramics.
LEGS = {
    "A": dict(c=14.5, hs=4, ls=8, rs_h=19, rp_h=23, rs_l=27, rp_l=31, drv="U4", dio="D1", cb="C46", cv="C47", rdt="R18",
              cer=["C17", "C18", "C19"], ph="PH_A", tg="/Leg_A/TG_A", bg="/Leg_A/BG_A"),
    "B": dict(c=69.5, hs=12, ls=16, rs_h=36, rp_h=40, rs_l=44, rp_l=48, drv="U5", dio="D2", cb="C48", cv="C49", rdt="R35",
              cer=["C20", "C21", "C22", "C23"], ph="PH_B", tg="/Leg_B/TG_B", bg="/Leg_B/BG_B"),
    "C": dict(c=124.5, hs=20, ls=24, rs_h=53, rp_h=57, rs_l=61, rp_l=65, drv="U6", dio="D3", cb="C50", cv="C51", rdt="R52",
              cer=["C24", "C25", "C26"], ph="PH_C", tg="/Leg_C/TG_C", bg="/Leg_C/BG_C"),
}
# DC-link bank: three rows of eight, rows alternate so that the strips between them are GND / VBUS / GND / VBUS from
# the top; the bottom strip (VBUS) runs along the tops of all three legs.
BANK = [[f"C{i}" for i in range(65, 73)], [f"C{i}" for i in range(9, 17)], [f"C{i}" for i in range(1, 9)]]
BANK_Y = [7.3, 20.8, 34.3]               # row centres (courtyards 13.4 tall)
BANK_ROT = [90, 270, 90]                 # 90: pad 1 (VBUS) down, 270: pad 1 up
CAP_PITCH, BANK_X0 = 11.1, 8.0
BANK_X1 = BANK_X0 + 8 * CAP_PITCH        # right edge of the bank courtyards
J1_X = BANK_X1 + 0.6 + 4.75              # J1 pad 1 (VBUS); pad 2 (GND) 15 mm to the right
HOLES = [(4.0, 4.0), (W - 4.0, 4.0), (4.0, H - 4.0), (W - 4.0, H - 4.0)]
HOLE_KEEPOUT = 3.5                       # radius: M3 screw head (5.5 mm) and washer


def placements():
    """{ref: (x, y, rotation)}. The legs and the capacitor bank are computed from LEGS / BANK, the rest is by hand."""
    P = {}
    for row, y, rot in zip(BANK, BANK_Y, BANK_ROT):
        for k, ref in enumerate(row):
            P[ref] = (BANK_X0 + CAP_PITCH / 2 + CAP_PITCH * k, y, rot)
    P["J1"] = (J1_X, BANK_Y[0], 0)                          # wires leave over the top edge
    for L, g in LEGS.items():
        c = g["c"]; d = c + LS_OFF
        for k, y in enumerate(ROWS):
            for fx, q, rs, rp in ((c, g["hs"], g["rs_h"], g["rp_h"]), (d, g["ls"], g["rs_l"], g["rp_l"])):
                P[f"Q{q + k}"] = (fx, y, 180)                # tab to the left, gate and source leads to the right
                P[f"R{rs + k}"] = (fx + 11.9, y + 2.54, 180)  # series gate resistor, in line with the gate lead
                P[f"R{rp + k}"] = (fx + 11.075, y + 0.3, 90)  # pull-down, gate end next to the series resistor
        ys = [y + 6.0 for y in ROWS[:3]] if len(g["cer"]) == 3 else [y + 3.0 for y in ROWS]
        for ref, y in zip(g["cer"], ys):
            P[ref] = (c - 8.84, y, 180)                      # VBUS pad against the HS tabs, GND pad in the lane
        # driver under the LS column: gate-drive pins (rot 90) face up
        P[g["drv"]] = (d + 6.5, DY, 90)
        P[g["cb"]] = (d + 1.5, DY - 3.4, 180)
        P[g["dio"]] = (d + 0.0, DY + 0.5, 180)
        P[g["rdt"]] = (d + 5.5, DY + 5.0, 180)
        P[g["cv"]] = (d + 8.9, DY + 5.0, 0)
    # current sensors (primary pads up, under the phase lanes), motor-lead pads
    ys = DY + 19.4
    P.update({"U7": (23.0, ys, 0), "U8": (78.0, ys, 0), "J2": (7.0, DY + 1.0, 0), "J3": (62.0, DY + 1.0, 0),
              "J4": (139.5, DY + 0.5, 0), "C52": (23.0, ys + 3.2, 0), "C54": (78.0, ys + 3.2, 0)})
    # MCU (rot 90: PWM / FAULT up, analog inputs down, SWD left, encoder right) and its parts
    m = DY + 13.0
    P.update({"U9": (120.0, m, 90),
              "C56": (117.0, m + 7.0, 90), "C57": (127.5, m - 3.5, 90), "C58": (115.5, m - 7.0, 0), "C59": (112.5, m + 3.0, 90),
              "C60": (110.0, m + 3.0, 90), "FB1": (127.5, m + 2.0, 90), "C61": (130.0, m + 2.0, 90), "C62": (130.0, m - 2.0, 90),
              "C63": (114.0, m + 7.5, 90), "R74": (110.5, m - 2.0, 0), "R69": (124.0, m - 7.5, 0), "R75": (106.0, m + 7.0, 0),
              "D4": (106.0, m + 9.5, 0), "R76": (106.0, m, 0), "J7": (107.0, m - 5.0, 0),
              "R70": (118.5, m + 9.5, 0), "R71": (118.5, m + 11.6, 0), "C53": (122.0, m + 11.6, 0),
              "R72": (122.0, m + 9.5, 0), "R73": (125.5, m + 11.6, 0), "C55": (125.5, m + 9.5, 0),
              "R4": (129.0, m + 9.5, 0), "C27": (129.0, m + 11.6, 0), "R5": (132.5, m + 9.5, 0), "C28": (132.5, m + 11.6, 0),
              "R6": (110.0, COL_BOT + 1.8, 90)})             # NTC at the bottom of the B / C ground lane, by the FETs
    # LDOs (12 V -> 5 V -> 3.3 V) and the connectors (bottom right)
    P.update({"U2": (168.0, DY + 7.0, 0), "C40": (172.6, DY + 2.5, 90), "C41": (162.8, DY + 8.5, 90), "C42": (168.0, DY + 11.0, 0),
              "U3": (168.0, DY + 16.5, 0), "C43": (172.6, DY + 12.0, 90), "C44": (162.8, DY + 17.5, 90), "C45": (168.0, DY + 20.5, 0),
              "J5": (144.0, H - 4.5, 0), "J6": (156.0, H - 4.5, 0)})
    # 12 V aux buck (top right): Q1 over Q2 (drains up), LTC7801 to their right, inductor to their left. U1's left
    # pins, top to bottom, are TG SW BST BG DRVCC NDRV VBUS EXTVCC RUN INTVCC OVLO SNS; their parts go round it in the
    # same order (Q1, C30, Q2, Q3 + C31 below-left, then the RUN / OVLO dividers below-right), so no route has to cross.
    P.update({"C38": (128.5, 10.5, 270), "C39": (125.0, 10.5, 270),
              "Q1": (134.0, 10.0, 90), "Q2": (134.0, 18.5, 90), "L1": (124.5, 24.0, 270),
              "U1": (143.0, 15.0, 180), "C30": (138.2, 11.6, 90), "Q3": (141.0, 26.0, 270), "C31": (136.2, 27.0, 90),
              "R8": (147.0, 24.5, 90), "R10": (150.5, 24.5, 90), "R9": (147.0, 28.5, 0), "R11": (150.5, 30.0, 0),
              "R17": (149.0, 11.5, 0), "R12": (149.0, 13.2, 0), "R16": (152.5, 13.2, 0), "C32": (149.0, 14.9, 0),
              "R15": (149.0, 16.6, 0), "C34": (152.5, 16.6, 0), "C35": (152.5, 18.3, 0), "R13": (149.0, 18.3, 0),
              "R14": (149.0, 20.0, 0), "C33": (152.5, 20.0, 0), "C29": (143.0, 20.8, 0),
              "R7": (124.5, 32.6, 0), "C36": (128.0, 33.0, 270), "C37": (131.5, 33.0, 270), "C64": (135.0, 33.0, 270),
              "R1": (155.5, 36.0, 0), "R2": (160.3, 36.0, 0), "R3": (165.1, 36.0, 0)})
    return P


def load():
    """Load the board with the net classes from the .kicad_pro on disk (see pcb_avionics.load: pcbnew caches the
    project, so unload it first, and check the classes arrived)."""
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
    for L in (I1, I2):
        b.SetLayerType(L, pcbnew.LT_POWER)
    b.SetLayerName(I1, "In1.GND"); b.SetLayerName(I2, "In2.PWR")


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
    P = placements()
    missing = []
    for fp in b.GetFootprints():
        ref = fp.GetReference()
        if ref.startswith("H"): continue
        if ref not in P: missing.append(ref); continue
        x, y, rot = P[ref]
        fp.SetOrientationDegrees(rot); fp.SetPosition(mm(x, y))
    if missing: raise KeyError(f"not placed: {missing}")
    extra = set(P) - {fp.GetReference() for fp in b.GetFootprints()}
    if extra: raise KeyError(f"placed but not on the board: {sorted(extra)}")


# ---------------------------------------------------------------- pictures
COL = {"HVBUS": "#d62728", "HVDIV1": "#e377c2", "HVDIV2": "#e377c2", "SW_A": "#9467bd", "SW_B": "#8c564b",
       "SW_C": "#bcbd22", "SW_AUX": "#ff7f0e", "PWR": "#2ca02c", "DRV": "#17becf", "Default": "#7f7f7f"}


def render(b, png, title="", zones=True, win=None, layers=(F,)):
    """Top view for review: pads coloured by clearance group, courtyards, refs, zones (F solid, others dashed),
    tracks (F red, B blue), vias. win = (x0, y0, x1, y1) zooms in on one area."""
    wx0, wy0, wx1, wy1 = win or (0, 0, W, H)
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon, Circle
    fs = max(9.0, min(24, (wx1 - wx0) / 7.0))
    fig, ax = plt.subplots(figsize=(fs, fs * (wy1 - wy0) / (wx1 - wx0)), dpi=100)
    ax.add_patch(Polygon([(0, 0), (W, 0), (W, H), (0, H)], closed=True, fc="#f4f1e8", ec="k", lw=1))
    def pts(o): return [(o.CPoint(i).x / MM - OX, o.CPoint(i).y / MM - OY) for i in range(o.PointCount())]
    if zones:
        for z in b.Zones():
            if z.GetIsRuleArea():
                for k in range(z.Outline().OutlineCount()):
                    ax.add_patch(Polygon(pts(z.Outline().Outline(k)), closed=True, fill=False, ec="#000", lw=0.4, ls=":"))
                continue
            c = "#555" if z.GetNetname() == "GND" else COL.get(netclass_of(z.GetNetname()), "#7f7f7f")
            for L in layers:
                if not z.IsOnLayer(L) or z.GetNetname() == "GND" and L != F: continue
                fill = z.GetFilledPolysList(L) if z.IsFilled() else None
                polys = fill if fill is not None and fill.OutlineCount() else z.Outline()
                for k in range(polys.OutlineCount()):
                    ax.add_patch(Polygon(pts(polys.Outline(k)), closed=True, fc=c, alpha=0.12 if z.GetNetname() == "GND" else 0.22,
                                         ec=c, lw=0.5, ls="-" if L == F else "--"))
    for t in b.GetTracks():
        if t.GetClass() == "PCB_VIA":
            p = t.GetPosition(); ax.add_patch(Circle((p.x / MM - OX, p.y / MM - OY), t.GetWidth(F) / MM / 2,
                                                     fc="#444" if t.GetNetname() == "GND" else COL.get(netclass_of(t.GetNetname()), "#777"), ec="k", lw=0.2))
        else:
            s, e = t.GetStart(), t.GetEnd()
            ax.plot([s.x / MM - OX, e.x / MM - OX], [s.y / MM - OY, e.y / MM - OY], color="#c0392b" if t.GetLayer() == F else "#2c64c9",
                    lw=t.GetWidth() / MM * 72 * 0.91 * fig.get_size_inches()[0] / (wx1 - wx0),
                    alpha=0.75 if t.GetLayer() in layers else 0.15, solid_capstyle="round")      # other layer faint
    for fp in b.GetFootprints():
        cy = fp.GetCourtyard(pcbnew.F_CrtYd)
        for k in range(cy.OutlineCount()):
            ax.add_patch(Polygon(pts(cy.Outline(k)), closed=True, fill=False, ec="#b04fb0", lw=0.4))
        for p in fp.Pads():
            if not (p.IsOnLayer(F) or p.IsOnLayer(B_)): continue
            ps = pcbnew.SHAPE_POLY_SET(); p.TransformShapeToPolygon(ps, F if p.IsOnLayer(F) else B_, 0, int(0.01 * MM), pcbnew.ERROR_INSIDE)
            n = p.GetNetname(); c = "#555" if n == "GND" else COL.get(netclass_of(n), "#999") if n else "#ddd"
            for k in range(ps.OutlineCount()):
                ax.add_patch(Polygon(pts(ps.Outline(k)), closed=True, fc=c, ec="k", lw=0.15))
        bb = cy.BBox() if cy.OutlineCount() else fp.GetBoundingBox(False)
        if not fp.GetReference().startswith("H"):
            ax.text(bb.GetCenter().x / MM - OX, bb.GetCenter().y / MM - OY, fp.GetReference(), ha="center", va="center",
                    fontsize=5 if not win else 7, color="#1a1a6e", weight="bold")
    ax.set_xlim(wx0 - 1, wx1 + 1); ax.set_ylim(wy1 + 1, wy0 - 1); ax.set_aspect("equal")
    st = 5 if (wx1 - wx0) > 60 else 1
    ax.set_xticks(range(int(wx0), int(wx1) + 1, st)); ax.set_yticks(range(int(wy0), int(wy1) + 1, st))
    ax.tick_params(labelsize=5); ax.grid(lw=0.2, alpha=0.5)
    ax.set_title(title, fontsize=9)
    fig.tight_layout(); fig.savefig(png); plt.close(fig)


def fresh():
    """Re-export the schematic's netted, unplaced board (kicad_esc.export) so the layout always starts from it."""
    import kicad_esc
    kicad_esc.export()


F_CRT = pcbnew.F_CrtYd
LOG = []


def log(*a):
    s = " ".join(str(x) for x in a); LOG.append(s); print(s, flush=True)




# ---------------------------------------------------------------- copper helpers
def pad(b, ref, num):
    return next(p for p in b.FindFootprintByReference(ref).Pads() if p.GetNumber() == str(num))


def P(b, ref, num):
    """Pad centre in board coordinates."""
    p = pad(b, ref, num)
    return (p.GetPosition().x / MM - OX, p.GetPosition().y / MM - OY)


def pad_on(b, ref, net):
    """Number of the pad of `ref` that is on `net`."""
    return next(p.GetNumber() for p in b.FindFootprintByReference(ref).Pads() if p.GetNetname() == net)


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def circle(cx, cy, r, n=32):
    return [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n)) for k in range(n)]


def inside(poly, x, y, margin=0.0):
    """Point inside the polygon and at least `margin` from its edges."""
    from matplotlib.path import Path
    if not Path(poly).contains_point((x, y)): return False
    def d(a, c):
        dx, dy = c[0] - a[0], c[1] - a[1]; L2 = dx * dx + dy * dy
        t = max(0.0, min(1.0, ((x - a[0]) * dx + (y - a[1]) * dy) / L2)) if L2 else 0.0
        return math.hypot(x - a[0] - t * dx, y - a[1] - t * dy)
    return min(d(a, c) for a, c in zip(poly, poly[1:] + poly[:1])) >= margin


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


def rule_area(b, name, pts, layers, keepout=False):
    """A rule area: a named region for the .kicad_dru (keepout=False) or a copper keep-out (no tracks, vias, pours)."""
    ra = pcbnew.ZONE(b); ls = pcbnew.LSET()
    for L in layers: ls.AddLayer(L)
    ra.SetLayerSet(ls)
    ra.SetIsRuleArea(True); ra.SetDoNotAllowTracks(keepout); ra.SetDoNotAllowVias(keepout); ra.SetDoNotAllowPads(False)
    ra.SetDoNotAllowCopperPour(keepout); ra.SetDoNotAllowFootprints(False); ra.SetZoneName(name)
    ol = ra.Outline(); ol.NewOutline()
    for x, y in pts: ol.Append(int(round((OX + x) * MM)), int(round((OY + y) * MM)))
    b.Add(ra)
    return ra


def track(b, net, pts, w, layer=F):
    for a, c in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(b); t.SetStart(mm(*a)); t.SetEnd(mm(*c)); t.SetWidth(int(round(w * MM)))
        t.SetLayer(layer); t.SetNet(b.FindNet(net)); b.Add(t)


def via(b, net, c, size=VIA):
    v = pcbnew.PCB_VIA(b); v.SetPosition(mm(*c)); v.SetWidth(int(round(size[0] * MM))); v.SetDrill(int(round(size[1] * MM)))
    v.SetNet(b.FindNet(net)); v.SetLayerPair(F, B_); b.Add(v)
    return v


def mask_open(b, layer, x0, y0, x1, y1):
    """A filled rectangle on a solder-mask layer: the mask is opened there (bare copper for a bar or heat sink)."""
    s = pcbnew.PCB_SHAPE(b, pcbnew.SHAPE_T_RECT); s.SetStart(mm(x0, y0)); s.SetEnd(mm(x1, y1))
    s.SetLayer(layer); s.SetWidth(0); s.SetFilled(True); b.Add(s)


def leg(L):
    g = LEGS[L]
    return g, g["c"], g["c"] + LS_OFF


# ---------------------------------------------------------------- power copper: geometry
FAULT_DROP = 1.25                        # FAULT_N via below the driver's pin 3 (pin centre to via centre)
SENSOR_X = {"A": 23.0, "B": 78.0}        # U7 / U8: primary slots at y 99.2, IP+ (phase) 6.9 mm right of the part origin
GATE_DY = 2.54                           # gate lead below the FET centre (rot 180)
COLX = 13.7                              # gate-drive column: 13.7 mm right of each FET column centre
TG_Y, BG_Y = 94.6, 95.6                  # B.Cu runs from the drivers to the gate columns
VIA_Y = 97.2                             # row of the TG / BG vias above the driver pins (pins end at y 98.33)
# DC link on F.Cu, an E on its side: strip 1 holds the VBUS pads of bank rows 1-2 and J1, the bridge right of the
# bank takes the battery current down to strip 3 (bank row 3 and the bar along the tops of the three legs).
VBUS_F = [(0.6, 7.6), (97.1, 7.6), (97.1, 2.4), (107.0, 2.4), (107.0, 41.0), (170.0, 41.0), (170.0, 45.6), (0.6, 45.6),
          (0.6, 34.6), (97.1, 34.6), (97.1, 20.5), (0.6, 20.5)]
AUX_VBUS = [(123.4, 6.4), (136.5, 6.4), (136.5, 11.5), (131.5, 11.5), (131.5, 9.85), (123.4, 9.85)]
AUX_SW = [(121.6, 14.6), (131.5, 14.6), (131.5, 12.4), (135.3, 12.4), (135.3, 14.0), (136.5, 14.0), (136.5, 20.3),
          (131.2, 20.3), (131.2, 20.8), (121.6, 20.8)]
AUX_12V = [(124.7, 30.6), (136.0, 30.6), (136.0, 32.4), (126.3, 32.4), (126.3, 33.5), (124.7, 33.5)]
MOT = {"A": rect(0.6, 94.2, SENSOR_X["A"] + 1.6, 108.0), "B": rect(56.4, 94.2, SENSOR_X["B"] + 1.6, 108.0)}
BAR_S3 = (1.0, 41.4, 169.6, 45.2)        # mask-free strips for soldered copper bars
BAR_BRIDGE = (98.2, 13.6, 106.0, 41.4)


def vbus_col(L, top=45.0):
    g, c, d = leg(L)
    return rect(c - 8.0, top, c + 4.6, COL_BOT - 0.2)


def ph_poly(L):
    """Phase copper of one leg: HS sources + LS tabs (the phase lane), a notch for the bootstrap capacitor's SW pad,
    and an exit down to the current sensor's IP+ slot (legs A, B) or to the motor-lead pad J4 (leg C)."""
    g, c, d = leg(L)
    top = [(c + 5.2, COL_TOP), (d + 4.7, COL_TOP), (d + 4.7, 96.8), (d + 1.4, 96.8), (d + 1.4, 98.8), (d - 0.2, 98.8),
           (d - 0.2, 95.6)]
    if L == "C":
        ex = [(144.6, 95.6), (144.6, 106.6), (134.4, 106.6), (134.4, 95.6)]
    else:
        ux = SENSOR_X[L]
        ex = [(ux + 11.6, 95.6), (ux + 11.6, 99.2), (ux + 2.0, 99.2), (ux + 2.0, 95.6)]
    return top + ex + [(c + 5.2, 95.6)]


def exempt_rect(b, ref):
    """Courtyard plus a fan-out margin on the side the gate-drive pins leave: 1 mm up for the drivers, 1.6 mm left for
    U1 (its two-column via fan-out, U1_ESC)."""
    bb = b.FindFootprintByReference(ref).GetCourtyard(F_CRT).BBox()
    x0, y0, x1, y1 = bb.GetLeft() / MM - OX, bb.GetTop() / MM - OY, bb.GetRight() / MM - OX, bb.GetBottom() / MM - OY
    return (x0 - 1.6, y0, x1, y1) if ref == "U1" else (x0, y0 - 1.0, x1, y1)


def pours(b):
    """Every power zone, by layer. Priorities: phase 11 > DC link / aux 10 > motor lead 9 > ground flood 1 > planes 0.
    KiCad's filler keeps every clearance of the .kicad_dru (0.6 mm between groups on the outer layers)."""
    for L in "ABC":
        zone(b, "VBUS", [F, I2], vbus_col(L), 12, name=f"VBUS_COL_{L}")   # same net as VBUS_F: distinct priority
        zone(b, "VBUS", [B_], vbus_col(L, COL_TOP), 10, name=f"VBUS_COL_{L}_B")
        zone(b, LEGS[L]["ph"], [F, I2, B_], ph_poly(L), 11, name=f"PH_{L}")
    for L, net in (("A", "/Current_Sense/MOT_A"), ("B", "/Current_Sense/MOT_B")):
        zone(b, net, [F, I2, B_], MOT[L], 9, name=f"MOT_{L}")
    zone(b, "VBUS", [F], VBUS_F, 10, name="VBUS_F")
    zone(b, "VBUS", [I2], rect(0.6, 0.6, W - 0.6, COL_TOP - 0.6), 10, name="VBUS_IN2")
    zone(b, "VBUS", [B_], circle(*P(b, "J1", 1), 6.0), 10, name="VBUS_J1_B")
    zone(b, "VBUS", [F], AUX_VBUS, 10, name="AUX_VBUS")
    zone(b, "/Aux_12V/SW_AUX", [F], AUX_SW, 10, name="AUX_SW")
    zone(b, "+12V", [F], AUX_12V, 10, name="AUX_12V")
    for i, (x, y) in enumerate(HOLES):
        rule_area(b, f"HOLE{i + 1}_KEEPOUT", circle(x, y, HOLE_KEEPOUT), [F, I1, I2, B_], keepout=True)
    for ref in EXEMPT:
        x0, y0, x1, y1 = exempt_rect(b, ref)
        g = EXEMPT_EDGE
        rule_area(b, f"{ref}_PINS", rect(x0 - g, y0 - g, x1 + g, y1 + g), [F])
    e = 0.3
    board = rect(e, e, W - e, H - e)
    zone(b, "GND", [F], board, 1, thermal=True, name="GND_F")
    zone(b, "GND", [B_], board, 1, thermal=True, name="GND_B")
    zone(b, "GND", [I2], board, 1, thermal=True, name="GND_IN2")
    zone(b, "GND", [I1], board, 0, thermal=True, name="GND_IN1")
    # the battery ground lead carries the full DC current: solid connection on every layer, no thermal spokes
    pad(b, "J1", 2).SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)


# ground pins tied to the exposed pad beside them by a stub (power_copper), so they need no fan-out via
EP_TIES = [("U1", "5", "25"), ("U1", "6", "25"), ("U1", "8", "25")] + [(LEGS[L]["drv"], "7", "13") for L in "ABC"]
HAND_GND = {"Q2", "C36", "C37", "C64", "C38", "C39", "J1"}          # parts whose ground vias are drawn by hand


def power_copper(b):
    """Copper drawn by hand: thermal and stitching vias, the gate drive of all 24 FETs, the driver hookups, the hand
    ground vias of the aux buck, and the solder-mask openings. Returns the via count by purpose."""
    n = {}
    def V(net, c, tag):
        via(b, net, c); n[tag] = n.get(tag, 0) + 1
    for L in "ABC":
        g, c, d = leg(L)
        for fx, q0, tab, src in ((c, g["hs"], "VBUS", g["ph"]), (d, g["ls"], g["ph"], "GND")):
            for k, y in enumerate(ROWS):
                # 30 vias in the drain tab (9.4 x 10.8 mm): heat to the B.Cu heat-sink face, current into In2
                for dx in (-3.0, -1.5, 0.0, 1.5, 3.0):
                    for dy in (-3.75, -2.25, -0.75, 0.75, 2.25, 3.75):
                        V(tab, (fx - 1.5 + dx, y + dy), "tab")
                # source copper above the source lead: 6 x 4 vias (one row under the top FET, VBUS strip above it)
                for dx in (6.0, 7.2, 8.4, 9.6, 10.8, 12.0):
                    for dy in ((-4.3,) if k == 0 else (-7.9, -6.7, -5.5, -4.3)):
                        V(src, (fx + dx, y + dy), "source")
        # ground lane right of the LS column: 3 (leg C: 4) columns of vias into In1 and B.Cu
        for x in [d + 15.0, d + 16.2, d + 17.4] + ([d + 18.6] if L == "C" else []):
            for k in range(40):
                y = 46.8 + 1.2 * k
                if y <= COL_BOT - 0.5: V("GND", (x, y), "lane")
        gate_drive(b, L); driver_hookup(b, L)
    for k in range(40):                                        # leg A's outer lane (DC-link ceramics' ground pads)
        y = 46.8 + 1.2 * k
        if y <= COL_BOT - 0.5: V("GND", (1.6, y), "lane")
    # bulk capacitors: three vias either side of each pad (VBUS pads into In2, GND pads into In1 / B.Cu)
    for row in BANK:
        for ref in row:
            for num in ("1", "2"):
                px, py = P(b, ref, num); net = pad(b, ref, num).GetNetname()
                for dx in (-2.1, 2.1):
                    for dy in (-1.3, 0.0, 1.3): V(net, (px + dx, py + dy), "bank")
    # battery leads: a ring of vias around each 8.4 mm pad, kept inside its own copper
    for num, net in (("1", "VBUS"), ("2", "GND")):
        cx, cy = P(b, "J1", num)
        for x, y in circle(cx, cy, 5.6, 20):
            if y < 1.3: continue
            if net == "VBUS" and not inside(VBUS_F, x, y, 0.4): continue
            if net == "GND" and (inside(VBUS_F, x, y) or min(math.hypot(x - qx, y - qy) for qx, qy in AUX_VBUS) < 2.0
                                 or x > AUX_VBUS[0][0] - 1.0): continue
            if BAR_BRIDGE[0] - 0.4 < x < BAR_BRIDGE[2] + 0.4 and y > BAR_BRIDGE[1] - 0.4: continue
            V(net, (x, y), "J1")
    # aux buck: VBUS vias beside C38 / C39 and Q1's drain, ground vias under the capacitors and Q2's sources
    for x in (124.3, 125.7, 127.8, 129.2): V("VBUS", (x, 7.3), "aux")
    for y in (7.0, 8.2, 9.4): V("VBUS", (130.8, y), "aux")
    for ref in ("C39", "C38"):
        px, py = P(b, ref, pad_on(b, ref, "GND"))
        for dx in (-0.7, 0.7):
            track(b, "GND", [(px + dx, py), (px + dx, py + 1.27)], 0.6); V("GND", (px + dx, py + 1.27), "aux")
    for num in ("1", "2", "3"):
        px, py = P(b, "Q2", num)
        track(b, "GND", [(px, py), (px, py + 2.45)], 0.4)
        for dy in (1.25, 2.45): V("GND", (px, py + dy), "aux")
    for ref in ("C36", "C37", "C64"):
        px, py = P(b, ref, pad_on(b, ref, "GND"))
        for dx in (-0.7, 0.7):
            track(b, "GND", [(px + dx, py), (px + dx, py + 1.43)], 0.6); V("GND", (px + dx, py + 1.43), "aux")
    # exposed pads: ground vias, and the ground pins beside them tied in
    for L in "ABC":
        x, y = P(b, LEGS[L]["drv"], 13)
        for dx in (-0.9, 0.0, 0.9): V("GND", (x + dx, y), "EP")
    x, y = P(b, "U1", 25)
    for dx in (-0.7, 0.7):
        for dy in (-1.0, 0.0, 1.0): V("GND", (x + dx, y + dy), "EP")
    for ref, pin, ep in EP_TIES:
        if ref == "U1":
            px, py = P(b, ref, pin); track(b, "GND", [(px, py), (P(b, ref, ep)[0] + 1.1, py)], 0.25)
    # U1's left pin row: stubs to the two-column fan-out (U1_ESC). The VBUS pin's via lands in the In2 plane, inside
    # the pin field (0.2 mm there), so no 100 V track has to leave the pin field
    for pin, dx in U1_ESC.items():
        net = pad(b, "U1", pin).GetNetname(); px, py = P(b, "U1", pin)
        track(b, net, [(px, py), (px + dx, py)], 0.25); V(net, (px + dx, py), "U1 fan-out")
    # bars and heat sink: mask-free copper
    for L in "ABC":
        g, c, d = leg(L)
        mask_open(b, pcbnew.F_Mask, c + 14.6, COL_TOP + 0.4, c + 19.2, 95.2)       # phase bar
        for fx in (c, d):
            mask_open(b, pcbnew.B_Mask, fx - 6.2, COL_TOP + 0.3, fx + 3.2, COL_BOT - 0.3)  # heat-sink face
    mask_open(b, pcbnew.F_Mask, *BAR_S3); mask_open(b, pcbnew.F_Mask, *BAR_BRIDGE)
    return n


def gate_drive(b, L):
    """Per FET: gate lead -> series resistor (pad 2), pull-down (pad 1) beside it, resistor pad 1 -> via -> a B.Cu
    column that joins the four resistors of a column (TG for the high side, BG for the low side)."""
    g, c, d = leg(L)
    for fx, q0, rs0, rp0, net in ((c, g["hs"], g["rs_h"], g["rp_h"], g["tg"]), (d, g["ls"], g["rs_l"], g["rp_l"], g["bg"])):
        for k in range(4):
            q, rs, rp, gn = f"Q{q0 + k}", f"R{rs0 + k}", f"R{rp0 + k}", f"Net-(Q{q0 + k}-G)"
            assert pad(b, q, 1).GetNetname() == gn and pad(b, rs, 2).GetNetname() == gn and pad(b, rp, 1).GetNetname() == gn
            assert pad(b, rs, 1).GetNetname() == net, (rs, pad(b, rs, 1).GetNetname(), net)
            s1, s2 = P(b, rs, 1), P(b, rs, 2)
            track(b, gn, [P(b, q, 1), s2], 0.6)
            track(b, gn, [P(b, rp, 1), s2], 0.5)
            track(b, net, [s1, (fx + COLX, s1[1])], 0.5)
            via(b, net, (fx + COLX, s1[1]))
        track(b, net, [(fx + COLX, ROWS[0] + GATE_DY), (fx + COLX, ROWS[-1] + GATE_DY)], 0.5, B_)


def driver_hookup(b, L):
    """The LTC7063's gate-drive pins (top row, left to right: BST TG SW NC BG GND) to the bootstrap parts, the phase
    copper and the two gate columns. TG and BG drop to B.Cu right above the pins and run under the phase copper."""
    g, c, d = leg(L); u = g["drv"]
    bst, tg, sw, bgp, gnd = (P(b, u, n) for n in (12, 11, 10, 8, 7))
    for pin, net in ((12, g["ph"].replace("PH_", "/Leg_%s/BST_" % L)), (11, g["tg"]), (10, g["ph"]), (8, g["bg"]), (7, "GND")):
        assert pad(b, u, pin).GetNetname() == net, (u, pin, pad(b, u, pin).GetNetname(), net)
    bnet = pad(b, u, 12).GetNetname()
    tv, bv = (tg[0] - 0.08, VIA_Y), (bgp[0] + 0.08, VIA_Y)
    track(b, g["tg"], [tg, tv], 0.3); via(b, g["tg"], tv)
    track(b, g["tg"], [tv, (tv[0], TG_Y), (c + COLX, TG_Y), (c + COLX, ROWS[-1] + GATE_DY)], 0.5, B_)
    track(b, g["bg"], [bgp, bv], 0.3); via(b, g["bg"], bv)
    track(b, g["bg"], [bv, (bv[0], BG_Y), (d + COLX, BG_Y), (d + COLX, ROWS[-1] + GATE_DY)], 0.5, B_)
    track(b, g["ph"], [sw, (sw[0], 96.4), (d + 4.3, 96.4)], 0.3)               # SW pin into the phase copper
    cb, dio = P(b, g["cb"], pad_on(b, g["cb"], bnet)), P(b, g["dio"], pad_on(b, g["dio"], bnet))
    j = (d + 3.3, bst[1])
    track(b, bnet, [bst, j], 0.3)
    track(b, bnet, [j, (cb[0], cb[1] + 0.4), cb], 0.3)
    track(b, bnet, [j, (dio[0] + 0.45, bst[1] + 0.85), (dio[0] + 0.45, dio[1] - 0.7)], 0.3)
    ep = P(b, u, 13)
    track(b, "GND", [gnd, (gnd[0], 100.0), (ep[0] + 1.1, 100.6)], 0.3)
    # logic row (bottom, left to right: PWM EN FAULT DT 12V 12V). DRV_EN and FAULT_N are both buses along the three
    # drivers, on neighbouring pins, so one of them has to change layer: FAULT_N drops to B.Cu through a via straight
    # below its pin, between the EN and DT stubs (0.225 mm each side), and the router runs its bus on B.Cu.
    fx, fy = P(b, u, 3)
    assert pad(b, u, 3).GetNetname() == "FAULT_N" and pad(b, u, 2).GetNetname() == "DRV_EN"
    fv = (fx, fy + (FAULT_DROP if fy > ep[1] else -FAULT_DROP))
    track(b, "FAULT_N", [(fx, fy), fv], 0.25); via(b, "FAULT_N", fv)


def tidy(b):
    """Two clean-ups after routing. (1) Neck-down: the router walks cell centres and then snaps the last point onto the
    exact pad centre, up to half a cell (25 um) off the grid it checked, so a segment that ends in a pad keeps no wider
    than the pad's narrow side less one cell (25 um each side). Narrowing only ever adds clearance. (2) Two fan-outs can
    pick the same spot for a via of one net: keep one (a double drill is a fab warning). Returns the counts."""
    pads = [p for fp in b.GetFootprints() for p in fp.Pads() if p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD]
    necked, NECK = 0, 1.2 * MM                     # a longer segment is narrowed for 1.2 mm only: past the next pins
    for t in list(b.GetTracks()):
        if t.GetClass() != "PCB_TRACK": continue
        for end in ("start", "end"):
            q = t.GetStart() if end == "start" else t.GetEnd()
            p = next((p for p in pads if p.GetNetCode() == t.GetNetCode() and p.IsOnLayer(t.GetLayer()) and p.HitTest(q)), None)
            if p is None: continue
            cap = max(int(min(p.GetSize(F).x, p.GetSize(F).y) - 0.05 * MM), int(MIN_TRACK * MM))
            if t.GetWidth() <= cap: continue
            o = t.GetEnd() if end == "start" else t.GetStart()
            n = math.hypot(o.x - q.x, o.y - q.y)
            if n <= 1.5 * NECK:
                t.SetWidth(cap)
            else:
                m = pcbnew.VECTOR2I(int(round(q.x + (o.x - q.x) * NECK / n)), int(round(q.y + (o.y - q.y) * NECK / n)))
                k = pcbnew.PCB_TRACK(b); k.SetStart(q); k.SetEnd(m); k.SetWidth(cap); k.SetLayer(t.GetLayer())
                k.SetNet(t.GetNet()); b.Add(k)
                if end == "start": t.SetStart(m)
                else: t.SetEnd(m)
            necked += 1
    seen, dup = set(), 0
    for v in [t for t in b.GetTracks() if t.GetClass() == "PCB_VIA"]:
        k = (v.GetNetCode(), v.GetPosition().x // 1000, v.GetPosition().y // 1000)
        if k in seen: b.Remove(v); dup += 1
        else: seen.add(k)
    return {"necked": necked, "duplicate vias": dup}


def fill(b):
    """Pour the zones with the .kicad_dru loaded (WriteDRCReport primes the DRC engine; see pcb_avionics.fill)."""
    import tempfile
    pcbnew.WriteDRCReport(b, os.path.join(tempfile.gettempdir(), "esc_prime_drc.rpt"), pcbnew.EDA_UNITS_MM, False)
    b.BuildConnectivity()
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.BuildConnectivity()


def islands(b, net):
    """Groups of pads of one net that copper already joins (pcb_avionics.islands), plus one thing that version misses:
    two pours of the same net that overlap are one conductor even when no pad or via sits in the overlap (here the VBUS
    columns run into the VBUS strip). Each filled outline is a node; outlines on one layer that touch are joined."""
    code = b.FindNet(net).GetNetCode()
    c = b.GetConnectivity()
    pads = [p for fp in b.GetFootprints() for p in fp.Pads() if p.GetNetCode() == code]
    tracks = [t for t in b.GetTracks() if t.GetNetCode() == code]
    items = pads + tracks
    uid = {x.m_Uuid.AsString(): i for i, x in enumerate(items)}
    polys = []                                            # (layer, SHAPE_LINE_CHAIN), node = len(items) + index
    for z in b.Zones():
        if z.GetNetCode() != code or z.GetIsRuleArea(): continue
        for L in (F, I1, I2, B_):
            if not z.IsOnLayer(L) or not z.HasFilledPolysForLayer(L): continue
            fp = z.GetFilledPolysList(L)
            for k in range(fp.OutlineCount()): polys.append((L, fp.Outline(k)))
    par = list(range(len(items) + len(polys)))
    def find(i):
        while par[i] != i: par[i] = par[par[i]]; i = par[i]
        return i
    def union(i, j): par[find(i)] = find(j)
    for j, t in enumerate(tracks):
        n = len(pads) + j
        for q in list(c.GetConnectedPads(t)) + list(c.GetConnectedTracks(t)):
            k = uid.get(q.m_Uuid.AsString())
            if k is not None: union(n, k)
    for pi, (L, ch) in enumerate(polys):
        node = len(items) + pi
        for i, x in enumerate(items):
            if not x.IsOnLayer(L): continue
            if i < len(pads):
                r = int(max(x.GetSize(L).x, x.GetSize(L).y) / 2 + 0.5 * MM); pts = [x.GetPosition()]
            elif x.GetClass() == "PCB_VIA":
                r = int(x.GetWidth(L) / 2 + 0.05 * MM); pts = [x.GetPosition()]
            else:
                r = int(x.GetWidth() / 2 + 0.05 * MM); pts = [x.GetStart(), x.GetEnd()]
            if any(ch.PointInside(pt) or ch.Collide(pt, r) for pt in pts): union(node, i)
        for pj in range(pi):
            L2, ch2 = polys[pj]
            if L2 != L or not ch.BBox().Intersects(ch2.BBox()): continue
            a = pcbnew.SHAPE_POLY_SET(ch); a2 = pcbnew.SHAPE_POLY_SET(ch2)
            if a.Collide(a2.Outline(0), 0) or a.Contains(ch2.CPoint(0)) or a2.Contains(ch.CPoint(0)): union(node, len(items) + pj)
    groups = {}
    for i, p in enumerate(pads): groups.setdefault(find(i), []).append(p)
    return list(groups.values())


# ---------------------------------------------------------------- routing
# Areas the router stays out of (free cells only; pads, zone outlines and hand copper keep their nets): the bank and
# the three legs are power copper on every layer. The 3.8 mm corridor along the right edge stays open for the two
# signals that leave the top band (+12V from the aux buck, VBUS_SNS from the divider).
KEEP_BOXES = [(0.0, 0.0, 117.5, COL_TOP), (0.0, 41.0, 170.3, COL_BOT + 0.3)]


def width_for(net):
    if net == "GND": return 0.4
    if net in ("VBUS", "+12V", "/Aux_12V/SNS_AUX"): return 0.5
    if net in ("+5V", "+3V3"): return 0.4
    c = netclass_of(net)
    if c in ("DRV",) or c.startswith("SW"): return 0.4
    if c.startswith("HVDIV"): return 0.3
    return 0.25


def widths_for(net):
    w0 = width_for(net)
    return sorted({w for w in (w0, 0.4, 0.3, 0.25, 0.2) if w <= w0 + 1e-9}, reverse=True)


def build_router(b):
    from kicad_route import Router, KEEP, OUTER
    ex = []
    for ref in EXEMPT:
        x0, y0, x1, y1 = exempt_rect(b, ref)
        ex.append((OX + x0, OY + y0, OX + x1, OY + y1))
    R = Router(b, (OX, OY), (W, H), lambda n: group(netclass_of(n)), lambda a, c: clearance(a, c), exempt=ex,
               min_clear=MIN_CLEAR, via=VIA, exempt_layers=(F,))
    for x0, y0, x1, y1 in KEEP_BOXES:
        i0, j0 = R.ij(OX + x0, OY + y0); i1, j1 = R.ij(OX + x1, OY + y1)
        for L in OUTER:
            sub = R.lab[L][i0:i1 + 1, j0:j1 + 1]; sub[sub == 0] = KEEP
    for x, y in HOLES:
        for sl, m in R._circle_cells((OX + x, OY + y), HOLE_KEEPOUT):
            for L in OUTER:
                sub = R.lab[L][sl]; sub[m & (sub == 0)] = KEEP
    return R


def u1_esc(b, pin):
    px, py = P(b, "U1", pin)
    return (px + U1_ESC[pin], py)


def explicit_steps(b):
    """Connections routed one by one before the general join, as (net, from, to): the aux buck's pin field, then the NTC
    divider's +3V3 (R5 sits in the bottom row under the encoder bus to J5, which would otherwise wall it in). A "from"
    of ("U1v", pin) is that pin's fan-out via (left on B.Cu); a "to" of (x, y) is a point in a pour of the net."""
    sns, v12 = pad_on(b, "C29", "/Aux_12V/SNS_AUX"), pad_on(b, "C29", "+12V")
    return [("/Aux_12V/TG_AUX", ("U1", 13), ("Q1", 4)), ("/Aux_12V/SW_AUX", ("U1", 14), ("C30", 2)),
            ("/Aux_12V/BST_AUX", ("U1", 15), ("C30", 1)), ("/Aux_12V/BG_AUX", ("U1", 16), ("Q2", 4)),
            ("/Aux_12V/SNS_AUX", ("U1", 24), ("C29", sns)), ("+12V", ("U1", 1), ("C29", v12)),
            ("/Aux_12V/INTVCC_AUX", ("U1v", 22), ("U1", 7)), ("/Aux_12V/OVLO_AUX", ("U1v", 23), ("R10", 2)),
            ("/Aux_12V/RUN_AUX", ("U1v", 21), ("R8", 2)), ("+12V", ("U1v", 20), ("U1", 1)),
            ("/Aux_12V/NDRV_AUX", ("U1v", 18), ("Q3", 1)), ("/Aux_12V/DRVCC_AUX", ("U1v", 17), ("Q3", 3)),
            ("/Aux_12V/DRVCC_AUX", ("Q3", 3), ("C31", 1)),
            ("/Aux_12V/SW_AUX", ("C30", 2), (136.0, 15.0)),           # bootstrap cap's SW end into the SW pour
            ("/Aux_12V/SNS_AUX", ("C29", sns), ("R7", 1)), ("+12V", ("C29", v12), ("R7", 2)),
            ("+3V3", ("R5", 1), ("FB1", 1))]


def explicit_step(R, b, net, a, c):
    A = lambda pt: (OX + pt[0], OY + pt[1])
    pa = pc = None
    mm_ = lambda v: v / MM
    if a[0] == "U1v":
        start, sl = A(u1_esc(b, a[1])), (B_,)
    else:
        pa = pad(b, *a); start, sl = abs_pt(pa), pad_layers(pa)
    if isinstance(c[0], str):
        pc = pad(b, *c); goal, gl = abs_pt(pc), pad_layers(pc)
    else:
        goal, gl = A(c), (F,)
    # no wider than the narrow side of either end pad: a 0.5 mm track on a 0.45 mm pin of a 0.65 mm-pitch row would
    # stick out 25 um towards the next pin
    cap = min([mm_(min(p.GetSize(F).x, p.GetSize(F).y)) for p in (pa, pc) if p is not None] or [9.0])
    ws = [x for x in widths_for(net) if x <= cap + 1e-9] or [min(widths_for(net))]
    items, w = None, None
    for m in (10.0, 20.0):
        items, w = R.connect(net, start, goal, ws, start_layers=sl, goal_layers=gl, margin=m)
        if items is not None: break
    tag = f"{net} {a[0]}.{a[1]} -> {c[0] + '.' + str(c[1]) if isinstance(c[0], str) else c}"
    return items, w, tag


def route(b, prio=()):
    """The explicit steps first (explicit_steps: the aux buck's pin field from its via fan-out, and R5's +3V3), then
    fan-out vias, then every remaining island of every net, nearest
    pads first. prio: nets that failed in an earlier pass go ahead of everything (rip-up and retry).
    Returns the router and the failures [(net, description)]."""
    R = build_router(b)
    A = lambda pt: (OX + pt[0], OY + pt[1])
    failed = []
    for net, a, c in sorted(explicit_steps(b), key=lambda st: st[0] not in prio):
        items, w, tag = explicit_step(R, b, net, a, c)
        log(f"{tag}: {'w %.2f' % w if items else 'FAILED'}")
        if items is None: failed.append((net, tag))

    def join(nets):
        todo, bad = 0, []
        for net in nets:
            isl = islands(b, net)
            stuck = set()
            while True:
                main = max(isl, key=len)
                rest = [p for g in isl if g is not main for p in g if p.m_Uuid.AsString() not in stuck]
                if not rest: break
                todo += 1
                d2 = lambda xy: (abs_pt(xy[0])[0] - abs_pt(xy[1])[0]) ** 2 + (abs_pt(xy[0])[1] - abs_pt(xy[1])[1]) ** 2
                pairs = sorted(((x, y) for x in main for y in rest), key=d2)
                seen, cand = set(), []
                for pa, pb in pairs:
                    k = (pa.m_Uuid.AsString(), pb.m_Uuid.AsString())
                    if k not in seen: seen.add(k); cand.append((pa, pb))
                    if len(cand) == 8: break
                items = None
                for pa, pb in cand:
                    items, w = route_pads(R, net, pb, pa, widths_for(net))
                    if items is not None: break
                tag = f"{net} {pb.GetParentFootprint().GetReference()}.{pb.GetNumber()} -> {pa.GetParentFootprint().GetReference()}.{pa.GetNumber()}"
                if items is None:
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

    order = {"Default": 0, "DRV": 1, "HVDIV1": 2, "HVDIV2": 2, "SW_AUX": 2, "SW_A": 2, "SW_B": 2, "SW_C": 2, "HVBUS": 3, "PWR": 4}
    rank = lambda n: (n not in prio, n == "GND", order[netclass_of(n)], n)
    nets = sorted({p.GetNetname() for fp in b.GetFootprints() for p in fp.Pads()
                   if p.GetNetname() and not p.GetNetname().startswith("unconnected")}, key=rank)
    if prio: join([n for n in nets if n in prio])
    # fan-out vias: every SMD ground pad outside the power stage into In1, the aux buck's VBUS pads into In2
    skip = {(r, p) for r, p, _ in EP_TIES} | {("U1", "25")} | {(LEGS[L]["drv"], "13") for L in "ABC"}
    power = {f"Q{i}" for i in range(4, 28)} | {r for row in BANK for r in row} | {r for g in LEGS.values() for r in g["cer"]}
    power |= {f"R{g['rp_l'] + k}" for g in LEGS.values() for k in range(4)} | HAND_GND
    # A fan-out via lands beside a fine-pitch pad, where the grid error bites (one came 0.196 mm from an LQFP pin), so
    # it keeps the full error (see kicad_route), not 0.75 cell. Routed vias keep 0.75 cell: the full margin everywhere
    # costs so many via spots that the router no longer completes, and KiCad's DRC checks them.
    nf = 0; R.via_extra = (math.sqrt(2) - 0.75) * R.cell
    for fp in b.GetFootprints():
        ref = fp.GetReference()
        if ref in power: continue
        for p in fp.Pads():
            net = p.GetNetname()
            if net not in ("GND", "VBUS") or p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH or (ref, p.GetNumber()) in skip: continue
            if net == "VBUS" and ref in ("U1", "C38", "C39", "Q1"): continue
            if R.fanout(p, 0.4) or R.fanout(p, 0.25): nf += 1
            else: log(f"no fan-out via for {ref}.{p.GetNumber()} ({net})")
    log(f"fan-out vias: {nf}"); R.via_extra = 0.0
    fill(b)
    bad = []
    for rnd in range(3):
        todo, bad = join(nets)
        fill(b)
        if not todo: break
    return R, failed + bad


SILK_H, SILK_T = 0.8, 0.15


def silk(b):
    """Reference designators at the first free spot around each part (see pcb_avionics.silk)."""
    V = lambda x, y: pcbnew.VECTOR2I(int(round(x * MM)), int(round(y * MM)))
    pads = [p.GetEffectiveShape(F) for fp in b.GetFootprints() for p in fp.Pads() if p.IsOnLayer(F)]
    lines = [g.GetEffectiveShape() for fp in b.GetFootprints() for g in fp.GraphicalItems()
             if g.GetLayer() == pcbnew.F_SilkS and g.GetClass() == "PCB_SHAPE"]
    # no silkscreen on the mask-free bars (it would not stick to bare copper)
    bars = []
    for d in b.GetDrawings():
        if d.GetLayer() == pcbnew.F_Mask: bars.append(d.GetEffectiveShape())
    placed, hidden = [], []
    x0, y0, x1, y1 = OX + 0.5, OY + 0.5, OX + W - 0.5, OY + H - 0.5
    for fp in sorted(b.GetFootprints(), key=lambda f: -f.GetCourtyard(F_CRT).BBox().GetArea()):
        t = fp.Reference()
        if fp.GetReference().startswith("H"): t.SetVisible(False); continue
        t.SetTextSize(V(SILK_H, SILK_H)); t.SetTextThickness(int(SILK_T * MM)); t.SetKeepUpright(True)
        bb = fp.GetCourtyard(F_CRT).BBox()
        if bb.GetWidth() == 0: bb = fp.GetBoundingBox(False)
        cx, cy = bb.GetCenter().x / MM, bb.GetCenter().y / MM
        hw, hh = bb.GetWidth() / MM / 2, bb.GetHeight() / MM / 2
        tw = 0.6 * SILK_H * len(fp.GetReference()) / 2 + 0.1
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
            if any(s.Collide(o, int(0.15 * MM)) for o in pads + bars): continue
            if any(s.Collide(o, int(0.1 * MM)) for o in lines + placed): continue
            ok = True; break
        if ok:
            t.SetVisible(True); placed.append(t.GetEffectiveShape(pcbnew.F_SilkS))
        else:
            t.SetVisible(False); hidden.append(fp.GetReference())
    return hidden


def notes(b):
    """Fabrication and assembly notes on the silkscreen, in the free strip along the bottom-left."""
    pass


def drc(b):
    rep = os.path.join(OUT, NAME + "_drc.json")
    subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "--severity-all", "--schematic-parity", "-o", rep, PCB],
                   capture_output=True)
    d = json.load(open(rep))
    from collections import Counter
    v = d.get("violations", [])
    return d, Counter((x["severity"], x["type"]) for x in v)


def pinfield_audit(b):
    """The pin-field exemption must not reach copper outside the pin-field areas: every pair of F.Cu items that touch
    an area, cut back to the copper outside it, must keep the full clearance for their pair of groups
    (bisection on KiCad's own collision test, as in pcb_avionics). Returns [(net A, net B, gap mm, needed mm)]."""
    bad = []
    items = [t for t in b.GetTracks() if t.IsOnLayer(F)] + [p for fp in b.GetFootprints() for p in fp.Pads() if p.IsOnLayer(F)]
    for ref in EXEMPT:
        area = next(z for z in b.Zones() if z.GetZoneName() == f"{ref}_PINS").Outline()
        out = []
        for it in items:
            if not it.GetEffectiveShape(F).Collide(area.Outline(0), 0) and not area.Contains(it.GetPosition()): continue
            ps = pcbnew.SHAPE_POLY_SET()
            it.TransformShapeToPolygon(ps, F, 0, int(0.005 * MM), pcbnew.ERROR_OUTSIDE)
            ps.BooleanSubtract(area)
            if ps.OutlineCount(): out.append((it.GetNetname(), netclass_of(it.GetNetname()), ps))
        for i, (na, ca, pa) in enumerate(out):
            for nb, cb, pb in out[i + 1:]:
                r = clearance(ca, cb)
                if na == nb or r <= MIN_CLEAR or not pa.Collide(pb, int(r * MM) - 1000): continue
                lo, hi = 0.0, r
                for _ in range(12):
                    m = (lo + hi) / 2
                    lo, hi = (lo, m) if pa.Collide(pb, int(m * MM)) else (m, hi)
                bad.append((ref, na, nb, round(hi, 3), r))
    return bad


def measure_gaps(b, limit=3.0):
    """Independent check of the clearance groups (not KiCad's DRC engine): per copper layer, all copper of each group
    (pads, tracks, vias, zone fills) as one polygon set, the pin-field areas cut out on F.Cu (pinfield_audit covers
    them), and for every pair of groups that needs more than MIN_CLEAR the smallest gap: grow the smaller set by d
    (Clipper offset) and intersect it with the other, bisecting on d to 1 um. Items are polygonised with at most 0.5 um
    error, outside the copper, and the offset's arcs are chords inside the true arc, so the result is good to ~1 um
    (with the default 5 um error a gap reads up to 5 um short: slivers at 0.595 mm on a 0.6 mm rule).
    Returns {layer: {"A|B": [gap mm, needed mm]}}; gap None = more than `limit`. The sets are appended and simplified
    once: a union per item (thousands of vias) takes hours, and so does KiCad's edge-by-edge Collide on whole sets."""
    E = 500                                                     # nm
    pin_areas = pcbnew.SHAPE_POLY_SET()
    for z in b.Zones():
        if z.GetIsRuleArea() and z.GetZoneName().endswith("_PINS"): pin_areas.Append(z.Outline())
    pin_areas.Simplify()
    out = {}
    for L in (F, I1, I2, B_):
        polys = {}
        get = lambda n: polys.setdefault(group(netclass_of(n)), pcbnew.SHAPE_POLY_SET())
        for it in [t for t in b.GetTracks() if t.IsOnLayer(L)] + [p for fp in b.GetFootprints() for p in fp.Pads() if p.IsOnLayer(L)]:
            if it.GetNetname(): it.TransformShapeToPolygon(get(it.GetNetname()), L, 0, E, pcbnew.ERROR_OUTSIDE)
        for z in b.Zones():
            if not z.GetIsRuleArea() and z.IsOnLayer(L) and z.GetNetname(): get(z.GetNetname()).Append(z.GetFilledPolysList(L))
        for ps in polys.values():
            ps.Simplify()
            if L == F: ps.BooleanSubtract(pin_areas)
        def near(pa, pb, d):
            q = pcbnew.SHAPE_POLY_SET(pa); q.Inflate(int(d * MM), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, E)
            q.BooleanIntersection(pb); return q.OutlineCount() > 0
        res, gs = {}, sorted(polys)
        for i, ga in enumerate(gs):
            for gb in gs[i + 1:]:
                need = clearance(ga, gb, outer=L in (F, B_))
                if need <= MIN_CLEAR: continue
                pa, pb = sorted((polys[ga], polys[gb]), key=lambda p: p.TotalVertices())
                if not near(pa, pb, limit): res[f"{ga}|{gb}"] = [None, need]; continue
                lo, hi = 0.0, limit
                while hi - lo > 0.001:
                    m = (lo + hi) / 2
                    lo, hi = (lo, m) if near(pa, pb, m) else (m, hi)
                res[f"{ga}|{gb}"] = [round(lo, 3), need]
        out[b.GetLayerName(L)] = res
    return out


def fab():
    """JLCPCB files in kicad/ESC_Board/jlcpcb/ (see pcb_avionics.fab): Gerbers + drill (zipped), BOM, CPL."""
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
    for row in csv.DictReader(open(os.path.join(HERE, "ESC_BOM.csv"), encoding="utf-8")):
        for r in row["References"].split(): spec[r] = (row["Part number / specification"], row["Rating"])
    b = load()
    groups, nospec = {}, []
    for fp in b.GetFootprints():
        if fp.GetAttributes() & pcbnew.FP_EXCLUDE_FROM_BOM: continue
        ref = fp.GetReference(); pn, rating = spec.get(ref, ("", ""))
        if ref not in spec: nospec.append(ref)
        comment = " ".join(x for x in (fp.GetValue(), pn, rating) if x)
        for a, c in (("µ", "u"), ("Ω", "R"), ("≤", "<="), ("≥", ">="), ("≈", "~")): comment = comment.replace(a, c)
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
    return d, len(groups), nospec


def start():
    """The netted board from the schematic. The export rewrites the .kicad_pro, so the net classes go in after it."""
    fresh(); write_project(); write_rules()
    b = load(); setup(b); outline(b); place(b)
    return b


if __name__ == "__main__":
    step = sys.argv[1] if len(sys.argv) > 1 else "all"
    if step == "fab":
        print(fab()); sys.exit()
    if step == "render":                       # the two routed renders again, from the saved board
        b = load(); fill(b)
        render(b, os.path.join(OUT, "layout_routed.png"), "routed: F.Cu (B.Cu tracks faint)")
        render(b, os.path.join(OUT, "layout_routed_B.png"), "routed: B.Cu (F.Cu tracks faint)", layers=(B_,))
        sys.exit()
    if step == "check":                        # independent clearance measurement of the saved board, into the stats
        b = load(); fill(b)
        gaps = measure_gaps(b)
        p = os.path.join(OUT, "layout_stats.json"); st = json.load(open(p)); st["measured_gaps"] = gaps
        json.dump(st, open(p, "w"), indent=1)
        for L, r in gaps.items():
            worst = min(((v[0] if v[0] is not None else 99) - v[1], k, v) for k, v in r.items())
            log(f"{L:6s} closest to its rule: {worst[1]} {worst[2][0]} mm (needs {worst[2][1]})")
        sys.exit()
    if step == "place":
        b = start()
        log("courtyard overlaps:", courtyard_overlaps(b))
        render(b, os.path.join(OUT, "layout_place.png"), "placement")
        pcbnew.SaveBoard(PCB, b); write_project(); write_rules(); sys.exit()
    if step == "copper":                       # pours and hand copper only, filled, for checking before routing
        b = start(); pours(b); n = power_copper(b)
        pcbnew.SaveBoard(PCB, b); write_project(); write_rules(); b = load(); fill(b)
        pcbnew.SaveBoard(PCB, b); write_project(); write_rules()
        log("hand vias:", n)
        render(b, os.path.join(OUT, "layout_copper.png"), "power copper (F.Cu)")
        d, cnt = drc(b)
        for k, v in sorted(cnt.items()): log(f"  {k[0]:8s} {k[1]:28s} {v}")
        sys.exit()
    best, prio = None, []
    for n in range(1, 6):
        b = start()
        ov = courtyard_overlaps(b)
        if ov: log("courtyard overlaps:", ov)
        pours(b); nv = power_copper(b); fill(b)
        R, failed = route(b, prio)
        fn = list(dict.fromkeys(n_ for n_, _ in failed))
        log(f"=== pass {n}: {len(failed)} failed connections {fn}")
        if best is None or len(failed) < len(best[2]): best = (b, R, failed, n)
        if not failed: break
        prio = fn + [x for x in prio if x not in fn]
    b, R, failed, n = best
    log(f"=== keeping pass {n}")
    log("tidy:", tidy(b))
    pcbnew.SaveBoard(PCB, b)
    write_project(); write_rules(); b = load()
    fill(b)
    hidden = silk(b)
    log("references kept on F.Fab only (no room on the silkscreen):", " ".join(hidden))
    pcbnew.SaveBoard(PCB, b); write_project(); write_rules()
    render(b, os.path.join(OUT, "layout_routed.png"), "routed: F.Cu (B.Cu tracks faint)")
    render(b, os.path.join(OUT, "layout_routed_B.png"), "routed: B.Cu (F.Cu tracks faint)", layers=(B_,))
    d, cnt = drc(b)
    nunc = len(d.get("unconnected_items", []))
    log("unrouted:", nunc, "failed routes:", len(failed))
    audit = pinfield_audit(b)
    log("pin-field audit, pairs short of full spacing outside the exempt areas:", audit)
    for k, v in sorted(cnt.items()): log(f"  {k[0]:8s} {k[1]:28s} {v}")
    tr = [t for t in b.GetTracks() if t.GetClass() == "PCB_TRACK"]
    stats = dict(tracks=len(tr), vias=sum(1 for t in b.GetTracks() if t.GetClass() == "PCB_VIA"), hand_vias=nv,
                 length_mm={b.GetLayerName(L): round(sum(t.GetLength() for t in tr if t.GetLayer() == L) / MM, 1) for L in (F, B_)},
                 routed_by_router=len(R.added), failed=failed, hidden_refs=hidden, unconnected=nunc,
                 drc={f"{k[0]}:{k[1]}": v for k, v in sorted(cnt.items())}, schematic_parity=len(d.get("schematic_parity", [])),
                 parts=sum(1 for fp in b.GetFootprints() if not fp.GetReference().startswith("H")),
                 pinfield_audit=audit, size_mm=[W, H], measured_gaps=measure_gaps(b))
    json.dump(stats, open(os.path.join(OUT, "layout_stats.json"), "w"), indent=1)

"""Avionics power board as a drawn KiCad 9 schematic (python3 kicad_avionics.py) -> kicad/Avionics_Board/

One sheet per numbered block of avionics.py (the same blocks as the LTspice drawing in topology 11):
  1 Inputs     3 packs -> fuse + diode-OR -> VIN_AV, TVS, LTC4366 surge stopper -> VIN_PROT, bulk
  2 Buck_12V   LTC7801 12 V / 5 A synchronous buck (video/telemetry transmitter, feeds the 5 V stage)
  3 Out_12V    PTC fuse + transmitter connector
  4 Buck_5V    LT8641 5 V / 3 A (flight controller + receiver), enabled by 12 V PGOOD
  5 LDO_3V3    LT3045 3.3 V / 0.3 A (sensors), enabled by 5 V PG

Parts, values, footprints and nets all come from avionics.py. kicad_draw checks the drawing against that table before
writing; kicad_check.py then checks it again with KiCad's own net list, ERC and the PCB.
"""
import os, sys
import avionics
import kicad_draw as D

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "kicad", "Avionics_Board")

# drawn pin order of the generated IC symbols (package pin numbers, top to bottom; None = empty row)
CUSTOM = {
    "LTC4366-2": (["1", "2", "3", "4"], ["8", "7", "6", "5"], 5.08, 20.32),
    "LTC7801": (["19", "21", "23", "20", "7", "5", "8", "12", "11", "10", "2", "4", "3"],
                ["18", "17", "15", "13", "14", "16", None, "24", "1", "22", "9", "6", "25"], 7.62, 30.48),
    "LT8641": (["4", "13", "14", "15", "16", "2", "17", None, "18", "6", "7", "10", "11"],
               ["3", "8", "9", "21", "22", None, "20", "1", None, None, "19", None, None], 7.62, 25.4),
}


COMMENTS = ["Drawn from avionics.py (topology 10) by kicad_avionics.py",
            "LTC7801, LT8641, LTC4366 symbols: ADI pin drawings",
            "Footprints: Drone_Power.pretty"]


def build():
    B = avionics.build()
    pr = D.Project("Avionics_Board", OUT, "AVIONICS POWER BOARD", B.parts, custom=CUSTOM)
    pr.root_notes = [
        "Avionics power board: three 24S packs (88.8 V nominal) -> 12 V / 5 A, 5 V / 3 A, 3.3 V / 0.3 A",
        "Parts, values and nets: avionics.py (topology 10). Simulated: Avionics_Board.asc, Avionics_SurgeTest.asc, Avionics_LoopTest.asc.",
        "Sheets connect through power symbols (GND, +12V, +5V, +3V3) and global labels (VIN_PROT, PG12, PG5).",
        "Startup order: packs -> LTC4366 turns Q4 on -> 12 V (UVLO 59.8 V, OVLO 118.8 V) -> PG12 enables 5 V -> PG5 enables 3.3 V.",
        "High-voltage nets (VIN_AV, VIN_PROT, PACKx, SW12, gate/boost of Q1): 100 V class; keep them away from the 5 V / 3.3 V side.",
    ]
    sheet1(pr); sheet2(pr); sheet3(pr); sheet4(pr); sheet5(pr)
    return pr


def side(s, ref, pin, d, stub=2.54, end="GND", first=None):
    """Part beside an IC pin: a short wire out of the pin, the part continuing in direction d, ground (or nothing) after it."""
    dx, dy = D.DIRS[d]
    a = (pin[0] + dx * stub, pin[1] + dy * stub)
    s.wire(pin, a)
    i = s.two(ref, a, d, first=first)
    if end == "GND":
        e = (i.b[0] + dx * 2.54, i.b[1] + dy * 2.54); s.wire(i.b, e); s.gnd(e)
    return i


def hang(s, ref, top, end="GND", first=None):
    i = s.two(ref, top, "D", first=first)
    if end == "GND": s.gnd(i.b)
    return i


# ---------------------------------------------------------------------------------------------------------- 1 inputs
def sheet1(pr):
    s = pr.sheet("inputs.kicad_sch", "Inputs", "1  PACK INPUTS: fuse + diode-OR per pack, TVS, LTC4366 surge stopper (115 V), bulk", paper="A4")
    s.text(20.32, 20.32, "1  PACK INPUTS", 3, True)
    s.text(20.32, 26.67, "Any pack keeps the avionics alive (diode-OR). U4 LTC4366-2 floats on the supply and holds VIN_PROT at", 1.6)
    s.text(20.32, 29.97, "VREG = 1.23 V (1 + R24/R23) = 115 V during a surge (the LTC7801 is rated 150 V); C27 sets the 51 ms overvoltage time.", 1.6)
    rail = 38.1
    bus = 76.2
    for k, y in zip((1, 2, 3), (63.5, 81.28, 99.06)):
        j = s.place(f"J{k}", 25.4, y, 0, mirror="y")
        s.wire(j["2"], (33.02, y + 2.54), (33.02, y + 7.62)); s.gnd((33.02, y + 7.62))
        f = s.two(f"F{k}", (38.1, y), "R")
        s.wire(j["1"], f.a)
        d = s.two(f"D{k}", (55.88, y), "R", first="A")
        s.wire(f.b, d.a)
        s.wire(d.b, (bus, y))
    s.flag((33.02, 106.68), "R")                        # GND driven (from the packs)
    s.wire((bus, 99.06), (bus, rail))
    s.text(22.86, 116.84, "J1-J3: one Micro-Fit lead from each pack's PDB tap. F1-F3 0.5 A, D1-D3 ES1D (200 V).", 1.4)
    # VIN_AV: TVS, RIN, pass FET
    s.wire((bus, rail), (114.3, rail))
    d4 = hang(s, "D4", (88.9, rail), first="K")
    r21 = s.two("R21", (101.6, rail), "D")
    q4 = s.place("Q4", 119.38, 40.64, 90, ref_at=(110.49, 31.75, "left"), val_at=(110.49, 34.29, "left"))   # D left, S right, G down
    assert q4["D"] == (114.3, rail) and q4["S"] == (124.46, rail), (q4["D"], q4["S"])
    s.wire(q4["G"], (119.38, 55.88), (124.46, 55.88))
    hang(s, "C26", (119.38, 55.88))
    r25 = s.two("R25", (124.46, 55.88), "R", first="2")
    # U4 LTC4366-2: left VDD SD TIMER VSS, right GATE FB OUT BASE (rows 5.08 apart)
    u4 = s.place("U4", 160.02, 76.2)
    s.wire(r25.b, (177.8, 55.88), (177.8, u4["GATE"][1]), u4["GATE"])
    s.wire(r21.b, (101.6, u4["VDD"][1]), u4["VDD"])
    s.wire(u4["_SD"], (144.78, u4["_SD"][1]), (144.78, u4["VDD"][1]))
    s.wire(u4["TIMER"], (139.7, u4["TIMER"][1]))
    c27 = hang(s, "C27", (139.7, u4["TIMER"][1]), end=None)
    c27.ref_at, c27.val_at = (137.16, 81.28, "right"), (137.16, 83.82, "right")
    vss = 91.44
    s.wire(u4["VSS"], (144.78, u4["VSS"][1]), (144.78, vss))
    s.wire(c27.b, (139.7, vss), (144.78, vss))
    hang(s, "R22", (144.78, vss))
    s.nc(u4["BASE"])
    s.wire(u4["OUT"], (182.88, u4["OUT"][1]), (182.88, rail))
    s.wire(u4["FB"], (195.58, u4["FB"][1]))
    r23 = s.two("R23", (195.58, rail), "D")
    s.wire(r23.b, (195.58, u4["FB"][1]))
    hang(s, "R24", (195.58, u4["FB"][1]))
    c28 = s.two("C28", (208.28, rail), "D")
    s.wire(c28.b, (208.28, vss), (144.78, vss))
    # VIN_PROT rail: bulk, then on to the 12 V buck
    s.wire((124.46, rail), (264.16, rail))
    hang(s, "C1", (226.06, rail))
    s.glabel((264.16, rail), "VIN_PROT", "R")
    s.text(132.08, 104.14, "Q4 FDB33N25 (250 V) drops the surge; R21 RIN feeds U4's shunt regulator, R22 RSS lets it float.", 1.4)
    s.text(132.08, 107.95, "R25 at Q4's gate stops it oscillating; C26 ramps the gate and bypasses Cgd during a surge.", 1.4)
    s.text(132.08, 111.76, "After 51 ms of overvoltage (C27) U4 turns Q4 off for a 9 s cool-down, then retries.", 1.4)
    s.text(212.09, 52.07, "C1 33 µF 160 V low-ESR electrolytic: damps the input filter", 1.4)


# ---------------------------------------------------------------------------------------------------------- 2 12 V buck
def sheet2(pr):
    s = pr.sheet("buck_12v.kicad_sch", "Buck_12V", "2  12 V / 5 A BUCK: U1 LTC7801, peak current mode, 148 kHz (video/telemetry TX, feeds the 5 V stage)", paper="A4")
    s.shift = (-101.6, -45.72)
    s.text(20.32, 20.32, "2  12 V / 5 A BUCK  (U1 LTC7801, 148 kHz)", 3, True)
    s.text(20.32, 26.67, "Peak current mode, R1 10 mΩ sense (Kelvin to SENSE+/-). RUN divider: on above 59.8 V; OVLO: off above 118.8 V.", 1.6)
    s.text(20.32, 29.97, "Q3 BSP89 pre-regulates DRVCC (10 V, set by R20) from VIN until EXTVCC takes over from the 12 V output.", 1.6)
    rail = 81.28
    u = s.place("U1", 190.5, 152.4, ref_at=(190.5, 101.6, "center"), val_at=(190.5, 203.2, "center"))
    L = u["VIN"][0]                                                  # 172.72
    s.glabel((132.08, rail), "VIN_PROT", "L")
    s.wire((132.08, rail), (256.54, rail))
    # VIN, RUN and OVLO dividers
    s.wire(u["VIN"], (167.64, u["VIN"][1]), (167.64, rail))
    r2 = s.two("R2", (154.94, rail), "D")
    s.wire(r2.b, (154.94, u["RUN"][1]), u["RUN"])
    side(s, "R3", (154.94, u["RUN"][1]), "L", stub=0)
    r4 = s.two("R4", (142.24, rail), "D")
    s.wire(r4.b, (142.24, u["OVLO"][1]), u["OVLO"])
    hang(s, "R5", (142.24, u["OVLO"][1]))
    s.wire(u["EXTVCC"], (167.64, u["EXTVCC"][1])); s.rail((167.64, u["EXTVCC"][1]), "+12V")
    y1, y2 = u["CPUMP_EN"][1], u["MODE"][1]
    s.wire(u["CPUMP_EN"], (167.64, y1), (167.64, y2), u["MODE"])
    s.wire((167.64, (y1 + y2) / 2), (154.94, (y1 + y2) / 2)); s.label((154.94, (y1 + y2) / 2), "INTVCC12", "L")
    for pin in ("PLLIN", "DRVUV"):
        s.wire(u[pin], (167.64, u[pin][1])); s.gnd((167.64, u[pin][1]))
    side(s, "R20", u["DRVSET"], "L")
    side(s, "R6", u["FREQ"], "L")
    side(s, "C8", u["SS"], "L")
    # compensation and feedback below the IC
    s.wire(u["ITH"], (154.94, u["ITH"][1]), (154.94, 210.82))
    hang(s, "C10", (154.94, 210.82))
    r9 = s.two("R9", (154.94, 210.82), "L")
    s.wire(r9.b, (142.24, 210.82)); hang(s, "C9", (142.24, 210.82))
    s.wire(u["VFB"], (167.64, u["VFB"][1]), (167.64, 210.82), (172.72, 210.82))
    hang(s, "R8", (167.64, 210.82))
    r7 = s.two("R7", (172.72, 210.82), "R", first="2")
    s.wire(r7.b, (185.42, 210.82)); s.rail((185.42, 210.82), "+12V")
    s.text(132.08, 228.6, "ITH: R9/C9 type II compensation, C10 high-frequency pole. VFB divider R7/R8: 12.0 V.", 1.4)
    # gate drive: DRVCC pre-regulator Q3
    q3 = s.place("Q3", 228.6, 91.44)
    s.wire(q3["D"], (231.14, rail))
    s.wire(u["NDRV"], (215.9, u["NDRV"][1]), (215.9, q3["G"][1]), q3["G"])
    s.wire(u["DRVCC"], (231.14, u["DRVCC"][1]), q3["S"])
    hang(s, "C6", (223.52, u["DRVCC"][1]))
    # half bridge: TG straight to Q1, BG straight to Q2, SW to the node between them
    q1 = s.place("Q1", 233.68, u["TG"][1]); q2 = s.place("Q2", 233.68, u["BG"][1])
    s.wire(u["TG"], q1["G"]); s.wire(u["BG"], q2["G"])
    s.wire(q1["S"], q2["D"])
    s.wire(u["SW"], (236.22, u["SW"][1]))
    s.gnd(q2["S"])
    s.wire(q1["D"], (236.22, rail))
    s.wire(u["BOOST"], (213.36, u["BOOST"][1])); s.label((213.36, u["BOOST"][1]), "BST12", "R")
    for k, x in (("C2", 246.38), ("C3", 256.54)): hang(s, k, (x, rail))
    s.text(241.3, 96.52, "C2, C3 2.2 µF 250 V: right at Q1's drain", 1.4)
    c5 = s.two("C5", (241.3, 129.54), "D")
    s.wire(c5.a, (241.3, 127.0), (246.38, 127.0)); s.label((246.38, 127.0), "BST12", "R")
    sw = u["SW"][1]
    s.wire((236.22, sw), (248.92, sw))
    l1 = s.two("L1", (248.92, sw), "R")
    r1 = s.two("R1", (264.16, sw), "R")
    s.wire(l1.b, r1.a)
    s.wire((259.08, sw), (259.08, 144.78))
    c4 = s.two("C4", (259.08, 144.78), "R")
    s.wire(c4.b, (274.32, 144.78), (274.32, sw))
    # Kelvin sense lines
    s.wire(u["SENSE+"], (256.54, u["SENSE+"][1]), l1.b)
    s.wire(u["SENSE-"], (276.86, u["SENSE-"][1]), (276.86, sw))
    # output
    s.wire(r1.b, (335.28, sw))
    for k, x in (("C13", 289.56), ("C14", 299.72), ("C11", 309.88), ("C12", 320.04)): hang(s, k, (x, sw))
    s.rail((330.2, sw), "+12V"); s.flag((335.28, sw), "U")
    s.text(284.48, 157.48, "C13, C14 10 µF X7R 1210; C11, C12 47 µF polymer", 1.4)
    # INTVCC, PGOOD, GND
    s.wire(u["INTVCC"], (248.92, u["INTVCC"][1]))
    s.label((226.06, u["INTVCC"][1]), "INTVCC12", "R")
    hang(s, "C7", (248.92, u["INTVCC"][1]))
    r10 = s.two("R10", (220.98, u["INTVCC"][1]), "D")
    s.wire(u["PGOOD"], r10.b, (231.14, u["PGOOD"][1])); s.glabel((231.14, u["PGOOD"][1]), "PG12", "R")
    g1, g2 = u.all("GND")
    s.wire(g1, (213.36, g1[1]), (213.36, g2[1] + 5.08)); s.wire(g2, (213.36, g2[1])); s.gnd((213.36, g2[1] + 5.08))
    s.text(226.06, 193.04, "U1 exposed pad (25) = GND: solder it, and stitch it to the ground plane with vias.", 1.4)


# ---------------------------------------------------------------------------------------------------------- 3 12 V out
def sheet3(pr):
    s = pr.sheet("out_12v.kicad_sch", "Out_12V", "3  12 V OUTPUT: video / telemetry transmitter", paper="A4")
    s.text(20.32, 20.32, "3  12 V OUTPUT: video / telemetry transmitter", 3, True)
    s.text(20.32, 26.67, "F4 PTC (2 A hold) protects the 12 V rail from a transmitter fault.", 1.6)
    s.rail((50.8, 63.5), "+12V")
    f = s.two("F4", (55.88, 63.5), "R")
    s.wire((50.8, 63.5), f.a)
    j = s.place("J4", 91.44, 63.5)
    s.wire(f.b, j["1"])
    s.wire(j["2"], (81.28, 66.04), (81.28, 71.12)); s.gnd((81.28, 71.12))


# ---------------------------------------------------------------------------------------------------------- 4 5 V buck
def sheet4(pr):
    s = pr.sheet("buck_5v.kicad_sch", "Buck_5V", "4  5 V / 3 A BUCK: U2 LT8641, 1 MHz (flight controller + receiver), enabled by 12 V PGOOD", paper="A4")
    s.shift = (-111.76, -50.8)
    s.text(20.32, 20.32, "4  5 V / 3 A BUCK  (U2 LT8641, 1 MHz)", 3, True)
    s.text(20.32, 26.67, "Internally compensated; C20 feed-forward across R12. EN/UV from the 12 V stage's PGOOD, so 5 V starts after 12 V is good.", 1.6)
    s.text(20.32, 29.97, "C15 and C16 go one at each VIN pin (4 and 13), as close as possible: they carry the switching current.", 1.6)
    u = s.place("U2", 203.2, 152.4, ref_at=(203.2, 101.6, "center"), val_at=(203.2, 203.2, "center"))
    top = 88.9
    s.rail((142.24, top), "+12V")
    s.wire((142.24, top), (182.88, top))
    s.wire(u["Vin1"], (182.88, u["Vin1"][1]), (182.88, top))
    s.wire(u["Vin2"], (172.72, u["Vin2"][1]), (172.72, top))
    hang(s, "C15", (152.4, top)); hang(s, "C16", (162.56, top))
    s.wire(u["EN/UV"], (175.26, u["EN/UV"][1])); s.glabel((175.26, u["EN/UV"][1]), "PG12", "L")
    side(s, "R11", u["Rt"], "L")
    side(s, "C19", u["TR/SS"], "L")
    yi = u["INTVcc"][1]
    s.wire(u["INTVcc"], (172.72, yi)); s.label((175.26, yi), "INTVCC5", "R")
    hang(s, "C18", (172.72, yi))
    gp = [u["Sync/Mode"], u["GND"]] + u.all("GND1") + u.all("GND2")
    for p in gp: s.wire(p, (182.88, p[1]))
    s.wire((182.88, gp[0][1]), (182.88, gp[-1][1] + 5.08)); s.gnd((182.88, gp[-1][1] + 5.08))
    s.text(132.08, 215.9, "GND pins 6, 7, 10, 11, 18 and SYNC/MODE (pulse-skipping off: forced continuous at light load is not needed here).", 1.4)
    # switch node, BST, inductor
    sws = u.all("SW")
    for p in sws: s.wire(p, (223.52, p[1]))
    s.wire((223.52, sws[0][1]), (223.52, sws[-1][1]))
    s.wire(u["BST"], (228.6, u["BST"][1]))
    c17 = hang(s, "C17", (228.6, u["BST"][1]), end=None)
    c17.ref_at, c17.val_at = (226.06, 109.22, "right"), (226.06, 111.76, "right")
    y5 = c17.b[1]
    s.wire((223.52, y5), (236.22, y5))
    l2 = s.two("L2", (236.22, y5), "R")
    s.wire(l2.b, (314.96, y5))
    s.rail((276.86, y5), "+5V"); s.flag((304.8, y5), "U")
    # feedback
    r12 = s.two("R12", (256.54, y5), "D"); s.wire(r12.b, (256.54, u["FB"][1]))
    c20 = s.two("C20", (271.78, y5), "D"); s.wire(c20.b, (271.78, u["FB"][1]))
    s.wire(u["FB"], (256.54, u["FB"][1]), (271.78, u["FB"][1]))
    hang(s, "R13", (256.54, u["FB"][1]))
    s.wire(u["Bias"], (223.52, u["Bias"][1])); s.rail((223.52, u["Bias"][1]), "+5V")
    # PG
    s.wire(u["PG"], (238.76, u["PG"][1])); s.glabel((238.76, u["PG"][1]), "PG5", "R")
    r14 = s.two("R14", (231.14, u["PG"][1]), "U", first="2")
    s.label(r14.b, "INTVCC5", "R")
    # outputs
    for k, x in (("C21", 284.48), ("C22", 294.64)): hang(s, k, (x, y5))
    j = s.place("J5", 325.12, y5 + 7.62)
    s.wire((314.96, y5), (314.96, j["2"][1])); s.wire(j["1"], (314.96, j["1"][1])); s.wire(j["2"], (314.96, j["2"][1]))
    s.wire(j["3"], (317.5, j["3"][1]), (317.5, j["4"][1] + 2.54)); s.wire(j["4"], (317.5, j["4"][1])); s.gnd((317.5, j["4"][1] + 2.54))
    s.text(284.48, 134.62, "C21, C22 47 µF X7R 1210 (~30 µF each at 5 V)", 1.4)
    s.text(299.72, 142.24, "J5: flight controller + receiver, 2 pins per rail", 1.4)


# ---------------------------------------------------------------------------------------------------------- 5 3.3 V LDO
def sheet5(pr):
    s = pr.sheet("ldo_3v3.kicad_sch", "LDO_3V3", "5  3.3 V / 0.3 A ULTRALOW-NOISE LDO: U3 LT3045 (sensors), enabled by 5 V PG", paper="A4")
    s.shift = (-91.44, -76.2)
    s.text(20.32, 20.32, "5  3.3 V / 0.3 A ULTRALOW-NOISE LDO  (U3 LT3045)", 3, True)
    s.text(20.32, 26.67, "VOUT = 100 µA × RSET (R15 33.2 kΩ, 0.1 %) = 3.32 V; CSET (C23) filters the reference noise and sets the soft-start.", 1.6)
    s.text(20.32, 29.97, "R16 sets the current limit (300 mA); R17/R18 set the PG threshold on the output. EN/UV from the 5 V stage's PG.", 1.6)
    X, Y = 165.1, 127.0
    u = s.place("U3", X, Y, ref_at=(X, Y - 10.16, "center"), val_at=(X + 2.54, Y + 12.7, "left"))
    ytop = Y - 12.7
    s.rail((X - 50.8, ytop), "+5V")
    s.wire((X - 50.8, ytop), (X - 15.24, ytop))
    s.wire(u["IN"], (X - 15.24, u["IN"][1]), (X - 15.24, ytop))
    hang(s, "C24", (X - 35.56, ytop))
    r19 = hang(s, "R19", (X - 45.72, ytop), end=None)
    s.label(r19.b, "PG33", "D")
    s.wire(u["EN/UV"], (X - 30.48, Y)); s.glabel((X - 30.48, Y), "PG5", "L")
    s.wire(u["ILIM"], (X - 25.4, u["ILIM"][1])); hang(s, "R16", (X - 25.4, u["ILIM"][1]))
    s.wire(u["SET"], (X - 12.7, u["SET"][1]), (X - 12.7, Y + 12.7), (X - 20.32, Y + 12.7))
    hang(s, "R15", (X - 12.7, Y + 12.7)); hang(s, "C23", (X - 20.32, Y + 12.7))
    s.gnd(u["GND"])
    # output and PG
    s.wire(u["OUT"], (X + 15.24, u["OUT"][1])); s.wire(u["OUTS"], (X + 15.24, u["OUTS"][1]))
    s.wire((X + 15.24, u["OUTS"][1]), (X + 15.24, Y - 10.16), (X + 50.8, Y - 10.16))
    r17 = s.two("R17", (X + 27.94, Y - 10.16), "D")
    s.wire(r17.b, (X + 27.94, u["PGFB"][1]))
    s.wire(u["PGFB"], (X + 27.94, u["PGFB"][1]))
    hang(s, "R18", (X + 27.94, u["PGFB"][1]))
    s.wire(u["PG"], (X + 15.24, u["PG"][1])); s.label((X + 15.24, u["PG"][1]), "PG33", "R")
    hang(s, "C25", (X + 38.1, Y - 10.16))
    s.rail((X + 45.72, Y - 10.16), "+3V3")
    j = s.place("J6", X + 55.88, Y - 10.16)
    s.wire(j["2"], (X + 48.26, j["2"][1]), (X + 48.26, j["2"][1] + 2.54)); s.gnd((X + 48.26, j["2"][1] + 2.54))
    s.text(X + 20.32, Y + 22.86, "PG33 (open drain, pulled up by R19) is spare: route it to a test pad if the sensors want a power-good.", 1.4)


def export(pcb=True):
    """Schematic, then the PCB with every footprint linked to its symbol (as Update PCB from Schematic would do)."""
    import json
    import kicad_export as K
    pr = build()
    probs = pr.check()
    if probs: raise SystemExit("drawing problems:\n  " + "\n  ".join(probs))
    pr.write(comments=COMMENTS)
    name = pr.name
    json.dump({k: sorted(map(list, v)) for k, v in pr.expected.items()}, open(os.path.join(OUT, "expected_nets.json"), "w"), indent=0)
    info = dict(parts=len(pr.placed), sheets=len(pr.sheets))
    if pcb:
        netmap = K.kicad_netlist(os.path.join(OUT, f"{name}.kicad_sch"))
        info.update(K.export_pcb(name, OUT, pr.pcb_parts(netmap), [s.name for s in pr.sheets], netmap))
        pro_path = os.path.join(OUT, f"{name}.kicad_pro")                  # pcbnew.SaveBoard rewrites the project file:
        pro = json.load(open(pro_path)); pro["sheets"] = [[pr.root_uuid, "Root"]] + [[s.uuid, s.name] for s in pr.sheets]
        open(pro_path, "w").write(json.dumps(pro, indent=2) + "\n")
        if os.path.exists(os.path.join(OUT, f"{name}.kicad_prl")): os.remove(os.path.join(OUT, f"{name}.kicad_prl"))
    return info


if __name__ == "__main__":
    print(export(pcb="--sch-only" not in sys.argv))

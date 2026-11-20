"""ESC board as a drawn KiCad 9 schematic (python3 kicad_esc.py) -> kicad/ESC_Board/

One sheet per numbered block of esc.py:
  1 Power_Input    AS150 input, 24 x 150 µF polymer + 10 x 2.2 µF ceramic DC link, bus-voltage divider, NTC
  2 Aux_12V        LTC7801 12 V / 0.3 A buck from the 100 V bus (gate drivers and logic)
  3 LDOs           LT1763 5 V (sensors, encoder) and 3.3 V (MCU)
  4-6 Leg_A/B/C    LTC7063 half-bridge driver + 2 x 4 IPB065N15N3 in parallel, one gate resistor and pull-down per FET
  7 Current_Sense  ACS772 Hall sensors in phases A and B, 2/3 divider into the ADC; motor leads J2, J3
  8 MCU            STM32G431 (FOC), decoupling, signal / encoder / SWD connectors

Parts, values, footprints and nets all come from esc.py. kicad_draw checks the drawing against that table before writing;
kicad_check.py then checks it again with KiCad's own net list, ERC and the PCB.
"""
import os, sys
import esc
import kicad_draw as D
import kicad_avionics as KA
from kicad_avionics import side, hang

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "kicad", "ESC_Board")

# drawn pin order of the generated IC symbols (package pin numbers, top to bottom), pitch and body width
CUSTOM = {
    "LTC7801": KA.CUSTOM["LTC7801"],
    "LTC7063": (["5", "6", "1", "2", "3", "4", "13"], ["12", "11", "10", "9", "8", "7"], 5.08, 20.32),
    "LT1763-5": (["8", "5", "3", "6", "7"], ["1", "2", "4"], 5.08, 20.32),
    "LT1763-3.3": (["8", "5", "3", "6", "7"], ["1", "2", "4"], 5.08, 20.32),
}
COMMENTS = ["Drawn from esc.py (topology 10) by kicad_esc.py",
            "LTC7801, LTC7063, LT1763 symbols: ADI pin drawings",
            "Footprints: Drone_Power.pretty"]
GLOBAL = {"VBUS_SNS", "TEMP", "PWM_A", "PWM_B", "PWM_C", "DRV_EN", "FAULT_N", "ISNS_A", "ISNS_B", "PH_A", "PH_B", "PH_C"}


def build():
    B = esc.build()
    pr = D.Project("ESC_Board", OUT, "ESC BOARD (one per motor)", B.parts, custom=CUSTOM)
    pr.root_notes = [
        "ESC board, one per motor: 24S (100.8 V max) -> 3-phase inverter, FOC on an STM32G431",
        "Parts, values, nets: esc.py (topology 10). Simulated: ESC_Board.asc.",
        "Sheets connect through power symbols and global labels.",
        "VBUS, PH_A/B/C, BST_x, TG_x are 100 V nets: keep them away from the MCU and ADC lines.",
    ]
    pick = Picker(B)
    sheet1(pr, pick); sheet2(pr); sheet3(pr)
    for ph in "ABC": leg(pr, pick, ph)
    sheet7(pr, pick); sheet8(pr)
    return pr


class Picker:
    """Find a part's references by its connections (so the drawing follows esc.py's numbering, not a copy of it)."""
    def __init__(self, B):
        self.parts = [p for p in B.parts if not p.sim]

    def __call__(self, pred, n=1):
        hit = [p for p in self.parts if pred(p)]
        if len(hit) != n: raise ValueError(f"expected {n} parts, found {[p.ref for p in hit]}")
        return [r for p in hit for r in p.refs()]


def stub(s, pin, d, n=2.54):
    dx, dy = D.DIRS[d]
    e = (pin[0] + dx * n, pin[1] + dy * n)
    s.wire(pin, e)
    return e


# ---------------------------------------------------------------------------------------------------------- 1 input
def sheet1(pr, pick):
    s = pr.sheet("power_input.kicad_sch", "Power_Input", "1  POWER INPUT + DC LINK: AS150, 24 x 150 µF polymer + 10 x 2.2 µF ceramic, bus and NTC sense")
    s.text(20.32, 20.32, "1  POWER INPUT + DC LINK", 3, True)
    s.text(20.32, 26.67, "J1 AMASS AS150 (anti-spark) on 8 AWG pigtails. The DC link carries 61.7 A rms of ripple at hover: 24 hybrid polymer", 1.6)
    s.text(20.32, 29.97, "caps share it (2.57 A each, rated 3.5 A); the 2.2 µF 250 V ceramics sit right at the FET legs for the switching edges.", 1.6)
    y = 63.5
    j = s.place("J1", 30.48, y, 0, mirror="y")
    bulk = pick(lambda p: "DC-link bulk" in p.desc, 2)
    s.wire(j["+"], (50.8 + 10.16 * (len(bulk) - 1), y))
    s.rail((48.26, y), "VBUS"); s.flag((40.64, y), "U")
    s.wire(j["-"], (38.1, j["-"][1]), (38.1, 76.2)); s.gnd((38.1, 76.2)); s.flag((38.1, 71.12), "R")
    for k, r in enumerate(bulk): hang(s, r, (50.8 + 10.16 * k, y))
    s.text(50.8, 81.28, "C1-C16, C65-C72: 150 µF 125 V hybrid polymer, ESR ≤ 20 mΩ, ≥ 3.5 A ripple each", 1.4)
    y2 = 99.06
    cer = pick(lambda p: "DC-link ceramic" in p.desc)
    s.rail((50.8, y2), "VBUS")
    s.wire((50.8, y2), (60.96 + 10.16 * (len(cer) - 1), y2))
    for k, r in enumerate(cer): hang(s, r, (60.96 + 10.16 * k, y2))
    s.text(50.8, 116.84, "C17-C26: 2.2 µF X7R 1210 250 V (≈1.1 µF at 90 V), spread over the three legs' VBUS-GND pads", 1.4)
    # bus voltage divider (three 1206 in series for the voltage rating) and the NTC
    x = 187.96
    s.rail((x, 96.52), "VBUS")
    r1 = s.two("R1", (x, 96.52), "D"); r2 = s.two("R2", r1.b, "D"); r3 = s.two("R3", r2.b, "D"); r4 = s.two("R4", r3.b, "D")
    s.gnd(r4.b)
    s.wire(r3.b, (215.9, r3.b[1])); hang(s, "C27", (200.66, r3.b[1])); s.glabel((215.9, r3.b[1]), "VBUS_SNS", "R")
    s.text(177.8, 142.24, "VBUS_SNS = VBUS × 33k / 1023k: 100.8 V -> 3.25 V at the ADC", 1.4)
    x = 241.3
    s.rail((x, 96.52), "+3V3")
    r5 = s.two("R5", (x, 96.52), "D"); r6 = s.two("R6", r5.b, "D"); s.gnd(r6.b)
    s.wire(r5.b, (266.7, r5.b[1])); hang(s, "C28", (254.0, r5.b[1])); s.glabel((266.7, r5.b[1]), "TEMP", "R")
    s.text(236.22, 127.0, "R6: 10 kΩ NTC (B3950) on the FET heatsink area", 1.4)


# ---------------------------------------------------------------------------------------------------------- 2 aux 12 V
def sheet2(pr):
    s = pr.sheet("aux_12v.kicad_sch", "Aux_12V", "2  AUX SUPPLY 12 V / 0.3 A: U1 LTC7801, 440 kHz, from the 100 V bus (gate drivers + logic)", paper="A4")
    s.shift = (-101.6, -40.64)                  # A3-sized drawing moved onto A4, clear of the header lines
    s.text(20.32, 20.32, "2  AUX SUPPLY 12 V / 0.3 A  (U1 LTC7801, 440 kHz)", 3, True)
    s.text(20.32, 26.67, "Each ESC makes its own 12 V from the bus (topology 07). RUN divider: on above 59.8 V; OVLO: off above 118.8 V.", 1.6)
    s.text(20.32, 29.97, "Q3 BSP89 pre-regulates DRVCC (10 V, set by R17) from VBUS until EXTVCC takes over from the 12 V output.", 1.6)
    rail = 81.28
    u = s.place("U1", 190.5, 152.4, ref_at=(190.5, 101.6, "center"), val_at=(190.5, 203.2, "center"))
    s.rail((132.08, rail), "VBUS")
    s.wire((132.08, rail), (256.54, rail))
    s.wire(u["VIN"], (167.64, u["VIN"][1]), (167.64, rail))
    r8 = s.two("R8", (154.94, rail), "D")
    s.wire(r8.b, (154.94, u["RUN"][1]), u["RUN"])
    side(s, "R9", (154.94, u["RUN"][1]), "L", stub=0)
    r10 = s.two("R10", (142.24, rail), "D")
    s.wire(r10.b, (142.24, u["OVLO"][1]), u["OVLO"])
    hang(s, "R11", (142.24, u["OVLO"][1]))
    s.wire(u["EXTVCC"], (167.64, u["EXTVCC"][1])); s.rail((167.64, u["EXTVCC"][1]), "+12V")
    s.wire(u["CPUMP_EN"], (162.56, u["CPUMP_EN"][1])); s.label((162.56, u["CPUMP_EN"][1]), "INTVCC_AUX", "L")
    for pin in ("MODE", "PLLIN", "DRVUV"):
        s.wire(u[pin], (167.64, u[pin][1])); s.gnd((167.64, u[pin][1]))
    side(s, "R17", u["DRVSET"], "L")
    side(s, "R12", u["FREQ"], "L")
    side(s, "C33", u["SS"], "L")
    # compensation and feedback below the IC
    s.wire(u["ITH"], (154.94, u["ITH"][1]), (154.94, 210.82))
    hang(s, "C35", (154.94, 210.82))
    r15 = s.two("R15", (154.94, 210.82), "L")
    s.wire(r15.b, (142.24, 210.82)); hang(s, "C34", (142.24, 210.82))
    s.wire(u["VFB"], (167.64, u["VFB"][1]), (167.64, 210.82), (172.72, 210.82))
    hang(s, "R14", (167.64, 210.82))
    r13 = s.two("R13", (172.72, 210.82), "R", first="2")
    s.wire(r13.b, (185.42, 210.82)); s.rail((185.42, 210.82), "+12V")
    s.text(132.08, 228.6, "ITH: R15/C34 type II compensation, C35 high-frequency pole. VFB divider R13/R14: 12.0 V.", 1.4)
    # DRVCC pre-regulator Q3
    q3 = s.place("Q3", 228.6, 91.44)
    s.wire(q3["D"], (231.14, rail))
    s.wire(u["NDRV"], (215.9, u["NDRV"][1]), (215.9, q3["G"][1]), q3["G"])
    s.wire(u["DRVCC"], (231.14, u["DRVCC"][1]), q3["S"])
    hang(s, "C31", (223.52, u["DRVCC"][1]))
    # half bridge
    q1 = s.place("Q1", 233.68, u["TG"][1]); q2 = s.place("Q2", 233.68, u["BG"][1])
    s.wire(u["TG"], q1["G"]); s.wire(u["BG"], q2["G"])
    s.wire(q1["S"], q2["D"])
    s.wire(u["SW"], (236.22, u["SW"][1]))
    s.gnd(q2["S"])
    s.wire(q1["D"], (236.22, rail))
    s.wire(u["BOOST"], (213.36, u["BOOST"][1])); s.label((213.36, u["BOOST"][1]), "BST_AUX", "R")
    for k, x in (("C38", 246.38), ("C39", 256.54)): hang(s, k, (x, rail))
    s.text(241.3, 96.52, "C38, C39 2.2 µF 250 V: right at Q1's drain", 1.4)
    c30 = s.two("C30", (241.3, 129.54), "D")
    s.wire(c30.a, (241.3, 127.0), (246.38, 127.0)); s.label((246.38, 127.0), "BST_AUX", "R")
    sw = u["SW"][1]
    s.wire((236.22, sw), (248.92, sw))
    l1 = s.two("L1", (248.92, sw), "R")
    r7 = s.two("R7", (264.16, sw), "R")
    s.wire(l1.b, r7.a)
    s.wire((259.08, sw), (259.08, 144.78))
    c29 = s.two("C29", (259.08, 144.78), "R")
    s.wire(c29.b, (274.32, 144.78), (274.32, sw))
    s.wire(u["SENSE+"], (256.54, u["SENSE+"][1]), l1.b)
    s.wire(u["SENSE-"], (276.86, u["SENSE-"][1]), (276.86, sw))
    s.wire(r7.b, (325.12, sw))
    for k, x in (("C36", 289.56), ("C37", 299.72), ("C64", 309.88)): hang(s, k, (x, sw))
    s.rail((320.04, sw), "+12V"); s.flag((325.12, sw), "U")
    s.text(284.48, 157.48, "C36, C37 10 µF X7R 1210; C64 47 µF: absorbs the three bootstrap charges at driver enable", 1.4)
    s.wire(u["INTVCC"], (248.92, u["INTVCC"][1]))
    s.label((226.06, u["INTVCC"][1]), "INTVCC_AUX", "R")
    hang(s, "C32", (248.92, u["INTVCC"][1]))
    r16 = s.two("R16", (220.98, u["INTVCC"][1]), "D")
    s.wire(u["PGOOD"], r16.b)
    g1, g2 = u.all("GND")
    s.wire(g1, (213.36, g1[1]), (213.36, g2[1] + 5.08)); s.wire(g2, (213.36, g2[1])); s.gnd((213.36, g2[1] + 5.08))
    s.text(226.06, 193.04, "U1 exposed pad (25) = GND: solder it, and stitch it to the ground plane with vias.", 1.4)


# ---------------------------------------------------------------------------------------------------------- 3 LDOs
def ldo(s, ref, X, Y, vin, vout, cin, cout, cbyp):
    u = s.place(ref, X, Y, ref_at=(X, Y - 15.24, "center"), val_at=(X, Y + 15.24, "center"))
    s.wire(u["IN"], (X - 20.32, u["IN"][1])); s.wire(u["_SHDN"], (X - 20.32, u["_SHDN"][1]))
    s.wire((X - 20.32, u["_SHDN"][1]), (X - 20.32, Y - 20.32), (X - 30.48, Y - 20.32))
    s.rail((X - 20.32, Y - 20.32), vin)
    hang(s, cin, (X - 30.48, Y - 20.32))
    for g in u.all("GND"): s.wire(g, (X - 17.78, g[1]))
    s.wire((X - 17.78, Y), (X - 17.78, Y + 15.24)); s.gnd((X - 17.78, Y + 15.24))
    s.wire(u["OUT"], (X + 20.32, u["OUT"][1])); s.wire(u["Sense"], (X + 20.32, u["Sense"][1]))
    s.wire((X + 20.32, u["Sense"][1]), (X + 20.32, u["OUT"][1]), (X + 45.72, u["OUT"][1]))
    hang(s, cout, (X + 33.02, u["OUT"][1]))
    s.rail((X + 40.64, u["OUT"][1]), vout); s.flag((X + 45.72, u["OUT"][1]), "U")
    s.wire(u["BYP"], (X + 25.4, u["BYP"][1]))
    c = s.two(cbyp, (X + 25.4, u["BYP"][1]), "U", first="2")
    s.wire(c.b, (X + 25.4, u["OUT"][1]))


def sheet3(pr):
    s = pr.sheet("ldos.kicad_sch", "LDOs", "3  LOGIC SUPPLIES: U2 LT1763-5 (sensors, encoder), U3 LT1763-3.3 (MCU)", paper="A4")
    s.text(20.32, 20.32, "3  LOGIC SUPPLIES  (LT1763, 500 mA low-noise LDOs)", 3, True)
    s.text(20.32, 26.67, "12 V -> 5 V (current sensors, encoder) -> 3.3 V (MCU). The 5 V LDO drops 7 V at ~60 mA: 0.42 W in the SO-8.", 1.6)
    s.text(20.32, 29.97, "C42, C45 (BYP, 10 nF) are not fitted: they lower the noise but stretch the start-up to several ms.", 1.6)
    ldo(s, "U2", 76.2, 101.6, "+12V", "+5V", "C40", "C41", "C42")
    ldo(s, "U3", 190.5, 101.6, "+5V", "+3V3", "C43", "C44", "C45")


# ---------------------------------------------------------------------------------------------------------- 4-6 legs
def cell(s, rg, rpd, q, X, Y, gate_net, top, bot):
    """One FET with its own gate resistor and gate-source pull-down: gate label on the left, drain up to `top`, source
    and pull-down down to `bot`."""
    r = s.two(rg, (X - 20.32, Y), "R", first="1")
    qi = s.place(q, X, Y, hide_value=True)                           # value in the sheet note (no room per FET)
    s.wire(r.b, qi["G"])
    p = s.two(rpd, (X - 10.16, Y), "D", first="1")
    s.wire(p.b, (X - 10.16, bot))
    s.wire(qi["D"], (X + 2.54, top)); s.wire(qi["S"], (X + 2.54, bot))
    s.label(r.a, gate_net, "L")


def leg(pr, pick, ph):
    i = "ABC".index(ph)
    s = pr.sheet(f"leg_{ph.lower()}.kicad_sch", f"Leg_{ph}",
                 f"{4 + i}  LEG {ph}: LTC7063 half-bridge driver (bootstrap) + 2 x 4 IPB065N15N3 in parallel")
    s.text(20.32, 20.32, f"{4 + i}  LEG {ph}  (U{4 + i} LTC7063 + 2 x 4 IPB065N15N3)", 3, True)
    s.text(20.32, 26.67, "Four FETs in parallel per switch, each with its own 10 Ω gate resistor (no gate-loop ringing between them) and 10 kΩ", 1.6)
    s.text(20.32, 29.97, "pull-down (keeps them off while the driver is unpowered). Dead time from the DT resistor: 150 kΩ ≈ 140 ns.", 1.6)
    u_ref = pick(lambda p: p.sym == "LTC7063" and p.nets["PWM"] == f"PWM_{ph}")[0]
    d_bt = pick(lambda p: p.sym == "diode" and p.nets.get("K") == f"BST_{ph}")[0]
    c_bt = pick(lambda p: p.nets == {"1": f"BST_{ph}", "2": f"PH_{ph}"})[0]
    c_vcc = pick(lambda p: p.desc.startswith("Driver Vcc"), 3)[i]
    r_dt = pick(lambda p: p.nets.get("1") == f"DT_{ph}")[0]
    Xu, Yu = 76.2, 101.6
    u = s.place(u_ref, Xu, Yu, ref_at=(Xu, Yu - 20.32, "center"), val_at=(Xu, Yu + 20.32, "center"))
    # supply, inputs, dead time
    s.wire(u["Vcc"], (55.88, u["Vcc"][1])); s.wire(u["BGVcc"], (55.88, u["BGVcc"][1]))
    s.wire((55.88, u["BGVcc"][1]), (55.88, 76.2), (45.72, 76.2)); s.rail((55.88, 76.2), "+12V")
    hang(s, c_vcc, (45.72, 76.2))
    for pin, net in (("PWM", f"PWM_{ph}"), ("EN", "DRV_EN"), ("_FLT", "FAULT_N")):
        s.wire(u[pin], (43.18, u[pin][1])); s.glabel((43.18, u[pin][1]), net, "L")
    s.wire(u["DT"], (55.88, u["DT"][1]))
    r = s.two(r_dt, (55.88, u["DT"][1]), "D"); s.wire(r.b, (55.88, 121.92)); s.gnd((55.88, 121.92))
    s.wire(u["SGND"], (60.96, u["SGND"][1]), (60.96, 124.46)); s.gnd((60.96, 124.46))
    # bootstrap and outputs
    s.wire(u["BST"], (111.76, u["BST"][1])); s.label((90.17, u["BST"][1]), f"BST_{ph}", "R")
    d = s.two(d_bt, (99.06, u["BST"][1]), "U", first="K"); s.rail(d.b, "+12V")
    c = s.two(c_bt, (111.76, u["BST"][1]), "U", first="1"); s.glabel(c.b, f"PH_{ph}", "U")
    s.label(stub(s, u["TG"], "R", 5.08), f"TG_{ph}", "R")
    s.glabel(stub(s, u["SW"], "R", 5.08), f"PH_{ph}", "R")
    s.nc(u["NC"])
    s.label(stub(s, u["BG"], "R", 5.08), f"BG_{ph}", "R")
    s.wire(u["BGRTN"], (93.98, u["BGRTN"][1]), (93.98, 116.84)); s.gnd((93.98, 116.84))
    # the eight FETs
    hs = [pick(lambda p, k=k: p.nets.get(k[0]) == k[1]) for k in (("1", f"TG_{ph}"), ("1", f"G{ph}H*"), ("G", f"G{ph}H*"))]
    ls = [pick(lambda p, k=k: p.nets.get(k[0]) == k[1]) for k in (("1", f"BG_{ph}"), ("1", f"G{ph}L*"), ("G", f"G{ph}L*"))]
    X = [152.4 + 35.56 * n for n in range(4)]
    yv, yh, yp, yl, yg = 76.2, 88.9, 101.6, 114.3, 127.0
    for n in range(4):
        cell(s, hs[0][n], hs[1][n], hs[2][n], X[n], yh, f"TG_{ph}", yv, yp)
        cell(s, ls[0][n], ls[1][n], ls[2][n], X[n], yl, f"BG_{ph}", yp, yg)
    xe = X[-1] + 15.24
    s.wire((X[0] + 2.54, yv), (xe, yv)); s.rail((xe, yv), "VBUS")
    s.wire((X[0] - 10.16, yg), (X[-1] + 2.54, yg)); s.gnd((X[-1] + 2.54, yg))
    s.wire((X[0] - 10.16, yp), (xe, yp))
    if ph == "C":                       # phase C has no current sensor: its motor lead leaves from this sheet
        s.wire((xe, yp), (xe, 93.98)); s.glabel((xe, 93.98), "PH_C", "U")
        s.wire((xe, yp), (xe + 12.7, yp)); s.place("J4", xe + 17.78, yp)
        s.text(xe - 5.08, 111.76, "J4: motor phase C, 8 AWG lead pad", 1.4)
    else:
        s.glabel((xe, yp), f"PH_{ph}", "R")
    fets = hs[2] + ls[2]
    s.text(132.08, 144.78, f"{fets[0]}-{fets[-1]}: IPB065N15N3 (150 V, 6.5 mΩ, D2PAK). High side: drains on VBUS, sources on PH. "
           "Low side: drains on PH, sources on GND.", 1.4)
    s.text(132.08, 148.59, "Layout: the 2.2 µF ceramics across each leg's VBUS-GND, gate resistors at the gates, driver next to its leg.", 1.4)


# ---------------------------------------------------------------------------------------------------------- 7 current sense
def sheet7(pr, pick):
    s = pr.sheet("current_sense.kicad_sch", "Current_Sense", "7  PHASE CURRENT: U7, U8 ACS772 ±250 A Hall sensors in phases A, B; 2/3 divider into the ADC", paper="A4")
    s.text(20.32, 20.32, "7  PHASE CURRENT  (ACS772 ±250 A, 8 mV/A)", 3, True)
    s.text(20.32, 26.67, "The phase current runs through the sensor's 100 µΩ conductor (IP+ -> IP-) on its way to the motor lead.", 1.6)
    s.text(20.32, 29.97, "Output 2.5 V ± 2 V at 5 V supply; R top / R bottom = 10k / 20k scale it to the 3.3 V ADC (×2/3), 1 nF anti-alias.", 1.6)
    for ph, Y in (("A", 76.2), ("B", 127.0)):
        u_ref = pick(lambda p: p.nets.get("IP+") == f"PH_{ph}")[0]
        j_ref = pick(lambda p: p.ref.startswith("J") and p.nets.get("1") == f"MOT_{ph}")[0]
        c_dec = pick(lambda p: p.desc == f"{u_ref} decoupling")[0]
        rt = pick(lambda p: p.nets.get("1") == f"ACS_{ph}")[0]
        rb = pick(lambda p: p.nets == {"1": f"ISNS_{ph}", "2": "0"} and p.ref.startswith("R"))[0]
        ca = pick(lambda p: p.nets == {"1": f"ISNS_{ph}", "2": "0"} and p.ref.startswith("C"))[0]
        X = 101.6
        u = s.place(u_ref, X, Y)
        s.wire(u["IP+"], (81.28, u["IP+"][1])); s.glabel((81.28, u["IP+"][1]), f"PH_{ph}", "L")
        s.wire(u["IP-"], (86.36, u["IP-"][1]), (86.36, Y + 12.7), (81.28, Y + 12.7))
        s.place(j_ref, 76.2, Y + 12.7, 0, mirror="y")
        s.wire(u["VCC"], (X, Y - 12.7), (116.84, Y - 12.7)); s.rail((X, Y - 12.7), "+5V")
        hang(s, c_dec, (116.84, Y - 12.7))
        s.gnd(u["GND"])
        s.wire(u["VIOUT"], (121.92, Y))
        r = s.two(rt, (121.92, Y), "R", first="1")
        hang(s, rb, r.b)
        s.wire(r.b, (147.32, Y)); hang(s, ca, (139.7, Y)); s.glabel((147.32, Y), f"ISNS_{ph}", "R")
    s.text(76.2, 165.1, "J2, J3: motor phase A, B (8 AWG lead pads). Phase C (J4) has no sensor: ic = -(ia + ib).", 1.4)


# ---------------------------------------------------------------------------------------------------------- 8 MCU
def sheet8(pr):
    s = pr.sheet("mcu.kicad_sch", "MCU", "8  MCU U9 STM32G431CBT6 (FOC firmware) + connectors: signal, encoder, SWD")
    s.text(20.32, 20.32, "8  MCU  (U9 STM32G431CBT6, Cortex-M4F 170 MHz)", 3, True)
    s.text(20.32, 26.67, "TIM1 CH1-3 (PA8-PA10) drive the three legs; ADC on PA0-PA3; SPI1 (PA4-PA7) reads the AS5047P encoder;", 1.6)
    s.text(20.32, 29.97, "PA15 takes DShot from the flight controller, PB6 sends telemetry. The pin map is a proposal: check it in STM32CubeMX.", 1.6)
    X, Y = 215.9, 139.7
    u = s.place("U9", X, Y)
    part = u.part
    inv = {num: our for our, nums in u.pmap.items() for num in nums}
    special = {"VDD", "VSS", "VSSA", "VDDA", "VBAT"}
    for num, (nm, px, py, a) in u.bynum.items():
        pt = u.at(num)
        our = inv.get(num)
        if our is None: s.nc(pt); continue
        if our in special: continue
        net = part.nets[our]
        d = "R" if px > 0 else "L"
        e = stub(s, pt, d, 5.08)
        if net == "VDDA": s.rail(e, "VDDA")
        elif net in GLOBAL: s.glabel(e, net, d)
        else: s.label(e, net, d)
    top = Y - 40.64
    for p in u.all("VDD") + [u["VBAT"]]: s.wire(p, (p[0], top - 5.08))
    s.wire((X - 5.08, top - 5.08), (X + 2.54, top - 5.08)); s.rail((X - 5.08, top - 5.08), "+3V3")
    s.wire(u["VDDA"], (X + 5.08, top - 7.62)); s.rail((X + 5.08, top - 7.62), "VDDA")
    s.wire(u["VSS"], (X, Y + 45.72)); s.wire(u["VSSA"], (X + 2.54, Y + 43.18), (X, Y + 43.18)); s.gnd((X, Y + 45.72))
    # decoupling: one 100 nF per VDD pin + bulk, VDDA through the ferrite bead
    y = 63.5
    s.rail((45.72, y), "+3V3"); s.wire((45.72, y), (96.52, y))
    for k, r in enumerate(("C56", "C57", "C58", "C59", "C60")): hang(s, r, (55.88 + 10.16 * k, y))
    s.text(45.72, 81.28, "C56-C59 100 nF at the four VDD/VBAT pins, C60 4.7 µF", 1.4)
    s.rail((119.38, y), "+3V3"); s.wire((119.38, y), (127.0, y))
    fb = s.two("FB1", (127.0, y), "R", first="1")
    s.wire(fb.b, (170.18, y))
    hang(s, "C61", (147.32, y)); hang(s, "C62", (157.48, y))
    s.rail((162.56, y), "VDDA"); s.flag((170.18, y), "U")
    s.text(127.0, 81.28, "VDDA / VREF+: ferrite bead + 1 µF + 100 nF", 1.4)
    # reset, boot, LED, fault pull-up
    s.label((45.72, 101.6), "NRST", "L"); s.wire((45.72, 101.6), (55.88, 101.6)); hang(s, "C63", (55.88, 101.6))
    s.label((45.72, 119.38), "BOOT0", "L"); s.wire((45.72, 119.38), (55.88, 119.38)); hang(s, "R74", (55.88, 119.38))
    s.label((45.72, 139.7), "LED", "L"); s.wire((45.72, 139.7), (50.8, 139.7))
    r75 = s.two("R75", (50.8, 139.7), "R", first="1")
    d4 = s.two("D4", r75.b, "R", first="K", val_at=(62.23, 143.51, "center")); s.rail(stub(s, d4.b, "R", 7.62), "+3V3")
    s.rail((45.72, 157.48), "+3V3")
    r69 = s.two("R69", (45.72, 157.48), "D", first="1"); s.glabel(r69.b, "FAULT_N", "D")
    s.text(55.88, 165.1, "R69: pull-up for the three drivers' open-drain FLT outputs (wired-OR)", 1.4)
    # connectors
    j5 = s.place("J5", 40.64, 203.2, 0, mirror="y")
    s.wire(j5["1"], (50.8, j5["1"][1]))
    r76 = s.two("R76", (50.8, j5["1"][1]), "R", first="1"); s.label(stub(s, r76.b, "R", 5.08), "SIG_IN", "R")
    s.label(stub(s, j5["2"], "R", 22.86), "TLM_TX", "R")
    s.gnd(stub(s, j5["3"], "R", 22.86), "R")
    s.text(30.48, 215.9, "J5: DShot in (R76 100 Ω series), telemetry out, GND (JST GH 3)", 1.4)
    conn(s, "J6", 40.64, 248.92, {"+5V": "rail", "GND": "gnd"})
    s.text(30.48, 264.16, "J6: AS5047P encoder on the motor, SPI (JST GH 6)", 1.4)
    conn(s, "J7", 299.72, 228.6, {"+3V3": "rail", "GND": "gnd"})
    s.text(289.56, 243.84, "J7: Tag-Connect TC2030-NL (SWD); pad 6 SWO unused", 1.4)


def conn(s, ref, x, y, power):
    """A connector with every pin on a stub: power symbols for rails, labels for signals."""
    j = s.place(ref, x, y, 0, mirror="y")
    for our, net in j.part.nets.items():
        net = "GND" if net == "0" else net
        e = stub(s, j[our], "R", 22.86)
        if power.get(net) == "rail": s.rail(e, net)
        elif power.get(net) == "gnd": s.gnd(e, "R")
        else: s.label(e, net, "R")


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

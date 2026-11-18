"""Draws the ESC board as a real wired schematic (python3 esc_draw.py):

  ESC_Block.asc        the ESC board, every part at a position and connected with wires: DC link (16 + 10 caps),
                       12 V aux buck (LTC7801), 5 V / 3.3 V LDOs, 3 legs (LTC7063 + 4 + 4 IPB065N15N3, each FET with its
                       own gate and pull-down resistor), 2 ACS770 current sensors, STM32G431
  ACS770.asc/.asy      the ACS770 Hall sensor (no maker model): its equivalent circuit inside a chip symbol
  STM32G431_FOC.asc/.asy  the STM32: pins of the real chip; inside, the FOC firmware written as a signal-flow model
  U15XL_Motor.asc/.asy the motor (3 windings in star + back-EMF, rotor and prop as their electrical analog)

Values, SPICE lines and the net every pin must be on come from esc.py's parts table; verify() checks the drawing
against it with LTspice's own netlister.
"""
import paths  # noqa: F401  (topology 10's parts tables)
import re, sys
import esc
from tablesheet import Table, TSheet, block_asy
from circuits import ltc7801

B = esc.build(block=True)
T = Table(B)
def blk(n): return [p for p in B.parts if p.blk.startswith(n)]
def refs_of(parts): return [r for p in parts for r in p.refs()]


from tablesheet import ren


# ====================================================================== sub-sheets (models of parts without a SPICE model)
def acs770():
    s = TSheet("ACS770", T)
    s.frame(0, 0, 1500, 900, "ACS770LCB-200B Hall current sensor, equivalent circuit (Allegro gives no SPICE model)")
    s.text(32, 96, ";The primary is a 100 uOhm copper conductor (IP+ to IP-). Output = VCC/5 x (2.5 V + 10 mV/A x Ip), 120 kHz bandwidth.", 2)
    pa = s.wire((400, 192), (400, 224)); s.port((400, 192), "IP+")
    _, b = s.free2("R_CS", "res", pa, "D", "100u")
    s.wire(b, (400, 400)); s.port((400, 400), "IP-")
    s.text(432, 300, ";primary conductor", 2)
    src = T.info("B_CSA")[1]
    val = ren(src, {"+5V": "VCC", "R_CSA": "R_CS"})
    p = s.place("B_CS", "bv", 800, 224, "R0", val)
    s.flag(p["-"], "GND")
    _, b = s.free2("R_BW", "res", s.wire(p["+"], (880, 240)), "R", T.info("R_BWA")[1])
    out = s.wire(b, (1104, 240)); _, c = s.free2("C_BW", "cap", out, "D", T.info("C_BWA")[1]); s.flag(c, "GND")
    s.wire(out, (1200, 240)); s.port((1200, 240), "VIOUT")
    s.text(640, 520, ";Hall cell + amplifier (output follows the primary current)        R_BW + C_BW: 120 kHz bandwidth", 2)
    q = s.place("B_Q", "bi", 400, 640, "R0", ren(T.info("B_ACSQA")[1], {"+5V": "VCC"}))
    s.wire(q["+"], (400, 608)); s.port((400, 608), "VCC"); s.wire(q["-"], (400, 752)); s.port((400, 752), "GND")
    s.text(432, 690, ";supply current of the sensor", 2)
    s.write()
    block_asy("ACS770.asy", [("IP+", 0, -128), ("IP-", 0, 128), ("VCC", -128, -48), ("GND", -128, 48), ("VIOUT", 128, 0)],
              (-128, -128, 128, 128), "ACS770|±200 A", "Hall sensor")
    return s


FW_PINS_L = ["VDD", "VBAT", "VDDA", "VREF+", "PG10", "PB8", "PA13", "PA14", "PA15", "PB6", "PC13", "VSS", "VSSA"]
FW_PINS_R = ["PA8", "PA9", "PA10", "PB0", "PB12", "PA0", "PA1", "PA2", "PA3", "PA4", "PA5", "PA6", "PA7", "ENC_THETA", "ENC_OMEGA"]
PIN_Y = lambda i: -448 + 64 * i
IO = {"ISNS_A": "PA0", "ISNS_B": "PA1", "VBUS_SNS": "PA2", "DRV_EN": "PB0", "PWM_A": "PA8", "PWM_B": "PA9", "PWM_C": "PA10"}


def stm32():
    s = TSheet("STM32G431_FOC", T)
    s.frame(0, 0, 4200, 2300, "STM32G431CBT6 running the FOC firmware: behavioural model of the code (a microcontroller has no SPICE model)")
    s.text(32, 96, ";Pins are the real chip's. Inputs: ADC pins PA0 (phase A current), PA1 (phase B), PA2 (bus voltage); encoder angle and speed."
           " Outputs: TIM1 PWM on PA8/PA9/PA10, driver enable PB0.", 2)
    s.text(32, 136, ";Each source below is one line of the firmware: its output node name is the variable, its expression is the code.", 2)
    fw = [p for p in blk("SIM: STM32") if p.sym == "bv"]
    stages = [("1 ADC READ: amps from the ADC counts", ["B_IA", "B_IB", "B_VB", "B_EN"]),
              ("2 ENCODER", ["B_THETA", "B_OMEGA", "B_WE"]),
              ("3 CLARKE + PARK (abc -> dq)", ["B_IAL", "B_IBE", "B_ID", "B_IQ"]),
              ("4 SPEED LOOP -> iq command", ["B_IQREF"]),
              ("5 CURRENT LOOPS (PI + decoupling)", ["B_VD", "B_VQ"]),
              ("6 INVERSE PARK + CLARKE", ["B_VAL", "B_VBE", "B_VA", "B_VBB", "B_VC"]),
              ("7 SPACE-VECTOR DUTY", ["B_VOFF", "B_DA", "B_DB", "B_DC"]),
              ("8 TIMER PWM OUT + DRIVER ENABLE", ["B_PWMA", "B_PWMB", "B_PWMC", "B_DRVEN"])]
    extra = {"B_THETA": ("V=V(ENC_THETA)", "the"), "B_OMEGA": ("V=V(ENC_OMEGA)", "omega"), "B_WE": ("V={Pp}*V(ENC_OMEGA)", "we")}
    by = {p.ref: p for p in fw}
    col_w, x0, y0 = 1000, 64, 260
    for k, (title, names) in enumerate(stages):
        cx = x0 + (k % 4) * col_w; cy = y0 + (k // 4) * 1000
        s.text(cx, cy, f";{title}", 3)
        for j, n in enumerate(names):
            y = cy + 80 + 210 * j
            if n in extra: val, node = extra[n]; exp = {}
            else:
                p = by[n]; node = IO.get(p.nets["+"], p.nets["+"]); val = ren(p.value, IO); exp = {"+": node, "-": "0"}
            P = s.place(n, "bv", cx + 48, y, "R0", val, expect=exp)
            if node in IO.values(): s.wire(P["+"], (cx + 48, y - 16)); s.port((cx + 48, y - 16), node)
            else: s.flag(P["+"], node)
            s.gnd(P["-"])
    # timebase, throttle command, bus filter
    cx, cy = x0, y0 + 2000 - 40
    s.text(cx, cy - 64, ";THROTTLE (DShot from the flight controller), PWM CARRIER, BUS-VOLTAGE FILTER", 3)
    v = s.place("V_WREF", "voltage", cx + 48, cy, "R0", T.info("V_WREF")[1]); s.flag(v["+"], "wref"); s.gnd(v["-"])
    v = s.place("V_TRI", "voltage", cx + 600, cy, "R0", T.info("V_TRI")[1]); s.flag(v["+"], "tri"); s.gnd(v["-"])
    a = s.flag((cx + 1100, cy + 16), "vbusm")
    _, b = s.free2("R_VBF", "res", a, "R", "1k"); b = s.wire(b, (cx + 1280, cy + 16))
    _, c = s.free2("C_VBF", "cap", b, "D", T.info("C_VBF")[1]); s.gnd(c); s.wire(b, (cx + 1344, cy + 16)); s.flag((cx + 1344, cy + 16), "vbusf")
    # supply current and pin leakage
    cx = x0 + 1700
    s.text(cx - 400, cy - 64, ";SUPPLY CURRENT AND INPUT PINS (10 MOhm = pin leakage; ADC and encoder inputs are read by the code above)", 3)
    q = s.place("B_MCU", "bi", cx + 48, cy - 16, "R0", ren(T.info("B_MCU")[1], {"+3V3": "VDD"}))
    s.wire(q["+"], (cx + 48, cy - 32)); s.port((cx + 48, cy - 32), "VDD"); s.wire(q["-"], (cx + 48, cy + 96)); s.port((cx + 48, cy + 96), "VSS")
    unused = [n for n in FW_PINS_L + FW_PINS_R if n not in ("VDD", "VSS", "PA8", "PA9", "PA10", "PB0")]
    for i, n in enumerate(unused):
        x = cx + 240 + 96 * i
        s.wire((x, cy - 32), (x, cy - 16)); s.port((x, cy - 32), n)
        _, b = s.free2(f"R_PIN{i}", "res", (x, cy - 16), "D", "10Meg")
        s.wire(b, (x, cy + 96)); s.port((x, cy + 96), "VSS")
    s.write()
    pins = [(n, -288, PIN_Y(i)) for i, n in enumerate(FW_PINS_L)] + [(n, 288, PIN_Y(i)) for i, n in enumerate(FW_PINS_R)]
    block_asy("STM32G431_FOC.asy", pins, (-288, -512, 288, 512), "U9|STM32G431CBT6|FOC firmware", "LQFP-48")
    return s


def motor():
    m = {"MOT_A": "A", "MOT_B": "B", "PH_C": "C", "omega": "OMEGA", "the": "THETA_E"}
    s = TSheet("U15XL_Motor", T, rename=m); s.vren = {"the": "THETA_E"}
    s.frame(0, 0, 3000, 1500, "T-MOTOR U15XL KV38 + 54 x 18 PROP: three windings in star, back-EMF, and the rotor as an electrical analog")
    s.text(32, 96, ";Each phase: winding inductance Lph + resistance Rph + back-EMF e = Kph * omega * sin(theta_e - k*120 deg). Star point n is floating.", 2)
    ys = {"a": 240, "b": 400, "c": 560}
    for ph, y in ys.items():
        P = ph.upper()
        s.port((96, y), P); a = s.wire((96, y), (192, y))
        _, b = s.two(f"L{ph}", a, "R"); _, b2 = s.two(f"R{ph}_M", s.wire(b, (304, y)), "R")
        e = s.put(f"B_E{P}", 0, 0, "R270")
        ex, ey = e["+"]; e.x += (b2[0] + 32) - ex; e.y += y - ey
        s.wire(b2, e["+"]); s.wire(e["-"], (720, y))
        s.text(110, y - 40, f";phase {P}", 2)
    s.wire((720, 240), (720, 400), (720, 560)); s.text(736, 400, ";n (star)", 2)
    # mechanics: omega node = speed (V = rad/s), C_J = inertia, current sources = torques
    s.text(1000, 200, ";ROTOR: node 'OMEGA' is the speed (1 V = 1 rad/s). Torque in = current in; inertia J = capacitor; prop drag = current out", 2)
    te = s.put("B_TE", 1000, 300); s.flag(te["+"], "te"); s.gnd(te["-"])
    s.text(1040, 440, ";electromagnetic torque te", 2)
    y = 300; bus = 1400
    tm = s.put("B_TM", bus, y - 16); s.wire(tm["+"], (bus, y - 64)); s.gnd((bus, y - 64)); s.wire(tm["-"], (bus, y + 112))
    nodes = [(bus, y + 112)]
    cj = s.two("C_J", (bus + 240, y + 112), "D"); s.gnd(cj[1])
    tp = s.put("B_TP", bus + 480, y + 112); s.gnd(tp["-"])
    lk = s.two("R_LK", (bus + 720, y + 112), "D"); s.gnd(lk[1])
    s.wire((bus, y + 112), (bus + 240, y + 112), (bus + 480, y + 112), (bus + 720, y + 112), (bus + 880, y + 112))
    s.port((bus + 880, y + 112), "OMEGA")
    s.text(bus + 32, y + 260, ";torque in      inertia J      prop + friction      leak", 2)
    # angle
    y2 = 900
    s.text(1000, y2 - 80, ";ANGLE: theta = integral of omega (capacitor C_TH charged by a current = omega); theta_e = Pp * theta", 2)
    dth = s.put("B_DTH", bus, y2 - 16); s.wire(dth["+"], (bus, y2 - 64)); s.gnd((bus, y2 - 64)); s.wire(dth["-"], (bus, y2 + 112))
    th = s.two("C_TH", (bus + 240, y2 + 112), "D"); s.gnd(th[1])
    lk2 = s.two("R_LK2", (bus + 480, y2 + 112), "D"); s.gnd(lk2[1])
    s.wire((bus, y2 + 112), (bus + 240, y2 + 112), (bus + 480, y2 + 112), (bus + 560, y2 + 112)); s.flag((bus + 560, y2 + 112), "theta")
    for i, n in enumerate(["B_THE", "B_RPM", "B_WE"]):
        x = 2200 + 240 * i
        P = s.put(n, x, y2 - 16); s.gnd(P["-"])
        nn = s.rename.get(T.info(n)[3]["+"], T.info(n)[3]["+"])
        if nn == "THETA_E": s.wire(P["+"], (x, y2 - 64)); s.port((x, y2 - 64), "THETA_E")
        else: s.flag(P["+"], nn)
    s.text(2200, y2 + 160, ";theta_e (to the encoder)   rpm   omega_e", 2)
    s.write()
    block_asy("U15XL_Motor.asy", [("A", -192, -96), ("B", -192, 0), ("C", -192, 96), ("THETA_E", -192, 224), ("OMEGA", -192, 288)],
              (-192, -192, 192, 352), "MOTOR|T-Motor U15XL|KV38 + 54x18 prop", "PMSM, 21 pole pairs")
    return s


# ====================================================================== the ESC board
def esc_sheet():
    s = TSheet("ESC_Block", T)
    # ---------------------------------------------------------------- 1 power input + DC link
    s.frame(-400, -40, 3800, 640, "1  POWER INPUT + DC LINK")
    s.port((64, 160), "VBUS"); s.conn(64, 160, "J1", "AS150 battery (+)")
    s.text(-380, 260, ";J1 (-) = GND", 2)
    xs = [320 + 96 * i for i in range(16)] + [1920 + 96 * i for i in range(10)]
    cap_refs = refs_of(blk("1 ")[0:0] or [T.by["C1"]]) + refs_of([T.by["C17"]])
    s.wire((64, 160), (2944, 160))
    for x, r in zip(xs, cap_refs):
        s.wire((x, 160), (x, 224)); _, b = s.two(r, (x, 224), "D"); s.gnd(b)
    s.text(320, 400, ";C1-C16: 150 uF 125 V hybrid polymer (bulk)", 2); s.text(1920, 400, ";C17-C26: 2.2 uF X7R 1210 at the FETs", 2)
    _, b = s.two("R1", (2944, 160), "D"); _, b = s.two("R2", b, "D"); _, n = s.two("R3", b, "D"); _, b = s.two("R4", n, "D"); s.gnd(b)
    s.wire(n, (3040, 400)); _, c = s.two("C27", (3040, 400), "D"); s.gnd(c); s.wire((3040, 400), (3136, 400)); s.flag((3136, 400), "VBUS_SNS")
    s.text(2976, 520, ";bus voltage sense -> MCU PA2", 2)
    s.flag((3328, 240), "+3V3"); _, n = s.two("R5", (3328, 240), "D"); _, b = s.two("R6", n, "D"); s.gnd(b)
    s.wire(n, (3424, 320)); _, c = s.two("C28", (3424, 320), "D"); s.gnd(c); s.wire((3424, 320), (3520, 320)); s.flag((3520, 320), "TEMP")
    s.text(3360, 440, ";R6 = NTC on heatsink", 2)
    # ---------------------------------------------------------------- 4..6 legs
    legs = [blk("4 "), blk("5 "), blk("6 ")]
    sens = blk("7 ")
    yv = 1152
    s.wire((224, 160), (224, yv))
    taps = [224]
    for k, (ph, parts) in enumerate(zip("ABC", legs)):
        cx, cy = 640 + 2560 * k, 1600
        s.frame(cx - 480, cy - 560, cx + 2080, cy + 1000, f"{4 + k}  LEG {ph}: half-bridge driver + 4 + 4 FETs" + ("" if ph == "C" else f" + phase current sensor"))
        U, D, Cb, Cd, Rdt = [p.ref for p in parts[:5]]
        rgh, rph, qh, rgl, rpl, ql = [p.refs() for p in parts[5:11]]
        u = s.put(U, cx, cy)
        # supply + bootstrap
        s.wire(u["Vcc"], (cx, cy - 352)); s.flag((cx, cy - 352), "+12V")
        s.wire((cx, cy - 320), (cx - 96, cy - 320)); _, c = s.two(Cd, (cx - 96, cy - 320), "D"); s.gnd(c)
        s.wire(u["BGVcc"], (cx - 224, cy - 192), (cx - 224, cy - 320), (cx - 96, cy - 320))
        s.wire(u["BST"], (cx + 224, cy - 192)); _, a = s.two(D, (cx + 224, cy - 192), "U", first="K"); s.flag(a, "+12V")
        _, c = s.two(Cb, (cx + 224, cy - 192), "D"); s.wire(c, (cx + 224, cy))
        # logic side
        for pin, net in (("EN", "DRV_EN"), ("_FLT", "FAULT_N"), ("PWM", f"PWM_{ph}")):
            p0 = u[pin]; s.wire(p0, (cx - 288, p0[1])); s.flag((cx - 288, p0[1]), net)
        s.wire(u["DT"], (cx - 224, cy + 192)); _, c = s.two(Rdt, (cx - 224, cy + 192), "D"); s.gnd(c)
        s.gnd(u["SGND"]); s.gnd(u["BGRTN"])
        # gate drive buses
        X = [cx + 512 + 336 * j for j in range(4)]
        s.wire(u["TG"], (X[3] - 112, cy - 96))
        s.wire(u["SW"], (cx + 240, cy), (cx + 240, cy + 80))
        s.wire(u["BG"], (cx + 288, cy + 96), (cx + 288, cy + 160), (X[3] - 112, cy + 160))
        xout = cx + 1632
        s.wire((cx + 240, cy + 80), (xout, cy + 80))                         # phase node bus
        s.flag((xout, cy + 80), f"PH_{ph}"); s.flag((cx + 224, cy - 192), f"BST_{ph}")
        s.flag((X[0] - 112, cy), f"G{ph}H1"); s.flag((X[0] - 112, cy + 256), f"G{ph}L1")
        s.wire((X[0] - 112, cy + 336), (X[3] + 48, cy + 336)); s.gnd((X[1] + 48, cy + 336))
        for j, x in enumerate(X):
            # high side
            q = s.put(qh[j], x, cy - 80)
            s.wire(q["D"], (x + 48, yv)); taps.append(x + 48)
            _, b = s.two(rgh[j], (x - 112, cy - 96), "D"); s.wire(b, (x - 112, cy), q["G"])
            _, b = s.two(rph[j], (x - 112, cy), "D"); s.wire(q["S"], (x + 48, cy + 80))
            # low side
            q = s.put(ql[j], x, cy + 176)
            s.wire(q["D"], (x + 48, cy + 80))
            _, b = s.two(rgl[j], (x - 112, cy + 160), "D"); s.wire(b, (x - 112, cy + 256), q["G"])
            _, b = s.two(rpl[j], (x - 112, cy + 256), "D"); s.wire(q["S"], (x + 48, cy + 336))
        s.text(X[0] - 48, cy - 480, f";Q{qh[0][1:]}-Q{qh[3][1:]} high side, Q{ql[0][1:]}-Q{ql[3][1:]} low side: IPB065N15N3 (each with its own gate R and 10k pull-down)", 2)
        port = {"A": "MOT_A", "B": "MOT_B", "C": "PH_C"}[ph]
        if ph in "AB":
            sp = [p for p in sens if p.ref.endswith(ph) or p.ref in ()]   # sim parts of this phase (inside the ACS770 block)
            i0 = [p.ref for p in sens].index(f"R_CS{ph}")
            Usens, _bq, Cdec, Rt, Rb, Cf = [p.ref for p in sens[i0 + 4:i0 + 10]]
            ys = cy + 512
            s.wire((xout, cy + 80), (xout, ys))
            a = s.put(Usens, xout, ys + 128, symname="ACS770")
            s.wire(a["IP-"], (xout, cy + 896))
            s.wire(a["VCC"], (xout - 224, a["VCC"][1])); s.flag((xout - 224, a["VCC"][1]), "+5V")
            _, c = s.two(Cdec, (xout - 192, a["VCC"][1]), "D"); s.gnd(c)
            s.gnd(a["GND"])
            _, n = s.two(Rt, a["VIOUT"], "R"); s.wire(n, (xout + 272, n[1]))
            _, c = s.two(Rb, (xout + 272, n[1]), "D"); s.gnd(c)
            s.wire((xout + 272, n[1]), (xout + 400, n[1])); _, c = s.two(Cf, (xout + 400, n[1]), "D"); s.gnd(c)
            s.wire((xout + 400, n[1]), (xout + 512, n[1])); s.flag((xout + 512, n[1]), f"ISNS_{ph}")
        else:
            s.wire((xout, cy + 80), (xout, cy + 896))
        s.port((xout, cy + 896), port)
        jr = {"A": "J2", "B": "J3", "C": "J4"}[ph]
        s.rects.append((xout - 80, cy + 912, xout + 80, cy + 992)); s.text(xout - 64, cy + 936, f";{jr}", 2)
        s.text(xout - 64, cy + 968, f";motor {ph}", 1)
    s.wire(*[(x, yv) for x in sorted(set(taps))])
    s.text(240, yv - 16, ";VBUS", 2)

    # ---------------------------------------------------------------- 2 aux 12 V supply (LTC7801)
    ox, oy = 912, 3600
    s.frame(-400, 2700, 2500, 4500, "2  ESC AUX SUPPLY 12 V / 0.3 A: U1 LTC7801 synchronous buck, 440 kHz (gate drivers + logic)")
    ltc7801(s, ox, oy, 2960, dict(U="U1", Q1="Q1", Q2="Q2", Q3="Q3", L="L1", Rsense="R7", Csense="C29", Cboost="C30", Cdrv="C31",
                                   Cint="C32", Rrun_t="R8", Rrun_b="R9", Rov_t="R10", Rov_b="R11", Rfreq="R12", Css="C33",
                                   Rfb_t="R13", Rfb_b="R14", Rith="R15", Cith="C34", Cithb="C35", Rpg="R16", Rdrvset="R17",
                                   Couts=["C36", "C37", "C64"], Cins=["C38", "C39"]), rail_label="VBUS")
    s.text(1300, 4300, ";Q1/Q2: BSC520N15NS3 / BSC360N15NS3, L1 150 uH, R7 0.1 Ohm sense. Q3 BSP89 pre-regulates DRVCC from the 90 V bus.", 2)

    # ---------------------------------------------------------------- 3 LDOs
    s.frame(2560, 2700, 4100, 3700, "3  LOGIC SUPPLIES: U2 LT1763-5, U3 LT1763-3.3")
    u2 = s.put("U2", 2944, 3344)
    s.wire(u2["IN"], (2768, u2["IN"][1]), (2640, u2["IN"][1])); s.flag((2640, u2["IN"][1]), "+12V")
    s.wire(u2["_SHDN"], (2768, u2["_SHDN"][1]), (2768, u2["IN"][1]))
    _, c = s.two("C40", (2704, u2["IN"][1]), "D"); s.gnd(c)
    s.wire(u2["OUT"], (3152, u2["OUT"][1]), (3152, u2["Sense"][1]), u2["Sense"])
    s.wire((3152, u2["OUT"][1]), (3456, u2["OUT"][1])); s.flag((3280, u2["OUT"][1]), "+5V")
    _, c = s.two("C41", (3216, u2["OUT"][1]), "D"); s.gnd(c)
    s.wire(u2["BYP"], (3168, u2["BYP"][1])); s.flag((3168, u2["BYP"][1]), "BYP5"); s.text(3184, u2["BYP"][1] + 32, ";C42 10 nF: DNP", 1)
    s.gnd(u2["GND"])
    u3 = s.put("U3", 3600, 3328)
    s.wire(u3["_SHDN"], (3424, u3["_SHDN"][1]), (3424, u3["IN"][1]))
    _, c = s.two("C43", (3376, u3["IN"][1]), "D"); s.gnd(c)
    s.wire(u3["OUT"], (3808, u3["OUT"][1]), (3808, u3["Sense"][1]), u3["Sense"])
    s.wire((3808, u3["OUT"][1]), (4000, u3["OUT"][1])); s.flag((4000, u3["OUT"][1]), "+3V3")
    _, c = s.two("C44", (3904, u3["OUT"][1]), "D"); s.gnd(c)
    s.wire(u3["BYP"], (3824, u3["BYP"][1])); s.flag((3824, u3["BYP"][1]), "BYP33"); s.text(3840, u3["BYP"][1] + 32, ";C45 10 nF: DNP", 1)
    s.gnd(u3["GND"])

    # ---------------------------------------------------------------- 8 MCU
    mx, my = 5600, 3700
    s.frame(4200, 2700, 7400, 4700, "8  MCU U9 STM32G431CBT6 (double-click: FOC firmware model) + connectors")
    mcu = s.put("U9", mx, my, symname="STM32G431_FOC")
    mcu.expect.update({"ENC_THETA": "ENC_THETA", "ENC_OMEGA": "ENC_OMEGA"})
    P = lambda n: mcu[n]
    mp = blk("8 "); crefs = [p.ref for p in mp if p.ref.startswith("C")]
    dec, bulk, cvdda1, cvdda2, crst = crefs[0:4], crefs[4], crefs[5], crefs[6], crefs[7]
    # +3V3, VBAT, decoupling row above the chip
    yt = my - 704
    s.wire(P("VDD"), (mx - 352, P("VDD")[1]), (mx - 352, yt)); s.wire(P("VBAT"), (mx - 352, P("VBAT")[1]), (mx - 352, P("VDD")[1]))
    s.flag((mx - 352, yt), "+3V3"); s.wire((mx - 352, yt), (mx + 192, yt))
    for i, r in enumerate(dec + [bulk]):
        _, c = s.two(r, (mx - 256 + 112 * i, yt), "D"); s.gnd(c)
    # VDDA through the ferrite
    fb = s.flag((mx - 544, my - 496), "+3V3")
    _, b = s.two("FB1", (mx - 544, my - 496), "D"); s.wire(b, (mx - 544, P("VDDA")[1]), P("VDDA"))
    s.wire(P("VREF+"), (mx - 416, P("VREF+")[1]), (mx - 416, P("VDDA")[1]))
    s.wire((mx - 544, P("VDDA")[1]), (mx - 736, P("VDDA")[1]))
    _, c = s.two(cvdda1, (mx - 640, P("VDDA")[1]), "D"); s.gnd(c); _, c = s.two(cvdda2, (mx - 736, P("VDDA")[1]), "D"); s.gnd(c)
    # reset, boot, SWD, signal, LED
    s.wire(P("PG10"), (mx - 448, P("PG10")[1])); s.flag((mx - 448, P("PG10")[1]), "NRST")
    rb = [p.ref for p in mp if p.ref.startswith("R")]; rboot, rled, rsig = rb
    _, c = s.two(rboot, P("PB8"), "L"); s.gnd(c)
    for pin, net in (("PA13", "SWDIO"), ("PA14", "SWCLK"), ("PB6", "TLM_TX")):
        s.wire(P(pin), (mx - 448, P(pin)[1])); s.flag((mx - 448, P(pin)[1]), net)
    _, b = s.two(rsig, P("PA15"), "L", first="2"); s.wire(b, (mx - 448, b[1])); s.flag((mx - 448, b[1]), "SIG_EXT")
    _, k = s.two(rled, P("PC13"), "L", first="1")
    dled = [p.ref for p in mp if p.ref.startswith("D")][0]
    _, a = s.two(dled, k, "L", first="K"); s.wire(a, (a[0] - 32, a[1])); s.flag((a[0] - 32, a[1]), "+3V3")
    s.wire(P("VSS"), (mx - 352, P("VSS")[1]), (mx - 352, P("VSSA")[1]), P("VSSA")); s.gnd((mx - 352, P("VSSA")[1]))
    # right side
    for pin in ("PA8", "PA9", "PA10", "PB0", "PB12", "PA0", "PA1", "PA2", "PA3", "PA4", "PA5", "PA6", "PA7"):
        net = T.info("U9")[3][pin]
        s.wire(P(pin), (mx + 480, P(pin)[1])); s.flag((mx + 480, P(pin)[1]), net)
    s.wire((mx + 480, P("PB12")[1]), (mx + 640, P("PB12")[1])); s.flag((mx + 640, P("PB12")[1] - 96), "+3V3")
    rfault = [p for p in legs[0] if p.ref.startswith("R") and "FAULT_N" in p.nets.values()][0].ref
    _, b = s.two(rfault, (mx + 640, P("PB12")[1] - 96), "D"); s.wire(b, (mx + 640, P("PB12")[1]))
    for pin in ("ENC_THETA", "ENC_OMEGA"):
        s.wire(P(pin), (mx + 800, P(pin)[1])); s.port((mx + 800, P(pin)[1]), pin)
    # connectors (graphics: no SPICE model) + encoder supply load
    cx = 6500
    s.conn(cx + 300, 3000, "J5", "JST GH 3: 1 SIG_EXT (DShot in), 2 TLM_TX, 3 GND", w=420, side="R")
    s.conn(cx + 300, 3160, "J6", "JST GH 6 to AS5047P encoder: +5V GND ENC_CS SCK MISO MOSI", w=420, side="R")
    s.conn(cx + 300, 3320, "J7", "TC2030 SWD: 1 +3V3, 2 SWDIO, 3 NRST, 4 SWCLK, 5 GND", w=420, side="R")
    s.text(mx + 700, my + 300, ";ENC_THETA / ENC_OMEGA: the encoder's angle and speed (SPI data on the real board), from the motor block", 2)
    s.flag((mx - 1100, my + 360), "NRST"); _, c = s.two(crst, (mx - 1100, my + 360), "D"); s.gnd(c)
    s.text(mx - 1240, my + 520, ";reset cap", 2)
    s.flag((mx - 900, my + 360), "+5V")
    q, b = s.free2("B_ENC", "bi", (mx - 900, my + 360), "D", T.info("B_ENC")[1]); s.gnd(b)
    s.text(mx - 960, my + 520, ";encoder supply (sim)", 2)

    s.text(-380, 4560, ";Labels used only for rails (VBUS, +12V, +5V, +3V3), ground and the control signals between the MCU and the legs."
           " Parts without a maker SPICE model are blocks: U7/U8 ACS770, U9 STM32 (double-click to see inside).", 2)
    s.write(directives=["; ESC board, one per motor (block of Power_System.asc). Ports: VBUS, MOT_A, MOT_B, PH_C, ENC_THETA, ENC_OMEGA. Parameters on the top sheet."])
    return s


if __name__ == "__main__":
    a, f, m = acs770(), stm32(), motor()
    s = esc_sheet()
    tbl = {r for p in B.parts if not p.sim and p.sym is not None for r in p.refs()}
    missing = sorted(tbl - s.used - {"C42", "C45"})
    print("table parts not drawn:", missing)
    for sh in (a, f, m, s):
        lint = sh.lint(); errs = sh.verify()
        print(f"{sh.name}: {len(sh.parts)} parts, {len(sh.wires)} wires; lint {len(lint)}; netlist errors {len(errs)}")
        for e in (lint + errs)[:25]: print("   ", e)
    if "--png" in sys.argv:
        s.render("esc_drawn.png", scale=0.22)

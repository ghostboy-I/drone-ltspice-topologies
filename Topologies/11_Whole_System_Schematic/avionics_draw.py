"""Draws the avionics power board as a real wired schematic (python3 avionics_draw.py) -> Avionics_Block.asc

  1 pack inputs: 3 x (fuse + diode-OR) -> VIN_AV, TVS, LTC4366 surge stopper -> VIN_PROT, bulk     2 12 V / 5 A buck (LTC7801)     3 12 V transmitter output
  4 5 V / 3 A buck (LT8641)     5 3.3 V ultralow-noise LDO (LT3045)

Values and nets come from avionics.py's parts table; verify() checks every pin with LTspice's netlister."""
import paths  # noqa: F401  (topology 10's parts tables)
import sys
import avionics
from tablesheet import Table, TSheet
from circuits import ltc7801

B = avionics.build(block=True)
T = Table(B)


def sheet():
    s = TSheet("Avionics_Block", T)
    # ---------------------------------------------------------------- 1 inputs
    s.frame(-400, -40, 1300, 1700, "1  PACK INPUTS: fuse + diode-OR per pack, TVS, U4 LTC4366 surge stopper (115 V), bulk")
    rail = 160
    for k, y in zip((1, 2, 3), (320, 480, 640)):
        s.port((64, y), f"PACK{k}+"); s.conn(64, y, f"J{k}", f"pack {k} (+), (-) = GND")
        _, b = s.two(f"F{k}", (128, y), "R"); s.wire((64, y), (128, y))
        s.wire(b, (288, y)); _, k_ = s.two(f"D{k}", (288, y), "R"); s.wire(k_, (560, y))
    s.wire((560, 640), (560, 480), (560, 320), (560, rail))
    s.text(80, 760, ";F1-F3 0.5 A fuses, D1-D3 ES1D diode-OR: any pack keeps the avionics alive", 2)
    s.wire((560, rail), (720, rail))
    _, a = s.two("D4", (720, rail), "D", first="K"); s.gnd(a)
    s.flag((640, rail), "VIN_AV")
    s.flag((960, rail), "VIN_PROT"); s.wire((960, rail), (1216, rail))
    _, c = s.two("C1", (1216, rail), "D"); s.gnd(c)
    s.text(680, 330, ";D4 TVS", 2); s.text(1000, 330, ";C1 33 uF bulk", 2)
    # surge stopper (drawn with net labels): Q4 passes VIN_AV -> VIN_PROT; U4 holds VIN_PROT at 115 V during a surge
    q = s.put("Q4", -320, 900)
    s.flag(q["D"], "VIN_AV"); s.flag(q["S"], "VIN_PROT")
    _, b = s.two("R25", (-416 + 64, 980), "L", first="B"); s.wire(q["G"], (-352, 980)) if q["G"] != (-352, 980) else None
    s.flag(b, "GATE_SSD"); s.flag(q["G"], "GATE_SS")
    _, b = s.two("R_SSRUN", (-96, 900), "D"); s.flag((-96, 900), "VIN_AV"); s.flag(b, "VIN_PROT")
    s.text(-140, 1060, ";R_SSRUN: Q4 already on (sim)", 1)
    u = s.put("U4", 640, 1000)
    for pin, net in (("VDD", "VDD_SS"), ("_SD", "VDD_SS"), ("TIMER", "TMR_SS"), ("VSS", "VSS_SS"), ("FB", "FB_SS"),
                     ("OUT", "VIN_PROT"), ("GATE", "GATE_SSD")):
        s.flag(u[pin], net)
    for i, (r, top, bot) in enumerate((("R21", "VIN_AV", "VDD_SS"), ("R22", "VSS_SS", "0"), ("R23", "VIN_PROT", "FB_SS"),
                                       ("R24", "FB_SS", "0"), ("C26", "GATE_SS", "0"), ("C27", "TMR_SS", "VSS_SS"),
                                       ("C28", "VIN_PROT", "VSS_SS"))):
        x = -320 + 192 * i; y = 1360
        _, b = s.two(r, (x, y), "D"); s.flag((x, y), top)
        s.gnd(b) if bot == "0" else s.flag(b, bot)
    s.text(-360, 1620, ";U4 LTC4366-2 floats on the supply (R21 RIN, R22 RSS): VREG = 1.23 V (1 + R24/R23) = 115 V, C27 51 ms timer", 2)
    # ---------------------------------------------------------------- 2 12 V buck
    ox, oy = 2400, 800
    s.frame(1340, -40, 4300, 1700, "2  12 V / 5 A BUCK: U1 LTC7801, peak current mode, 148 kHz (video/telemetry TX, feeds the 5 V stage)")
    s.wire((1216, rail), (ox - 784, rail))
    out = ltc7801(s, ox, oy, rail, dict(U="U1", Q1="Q1", Q2="Q2", Q3="Q3", L="L1", Rsense="R1", Csense="C4", Cboost="C5", Cdrv="C6",
                                       Cint="C7", Rrun_t="R2", Rrun_b="R3", Rov_t="R4", Rov_b="R5", Rfreq="R6", Css="C8",
                                       Rfb_t="R7", Rfb_b="R8", Rith="R9", Cith="C9", Cithb="C10", Rpg="R10", Rdrvset="R20",
                                       Couts=["C11", "C12", "C13", "C14"], Cins=["C2", "C3"]))
    # ---------------------------------------------------------------- 3 12 V output
    s.frame(4360, -40, 5600, 1000, "3  12 V OUTPUT: video / telemetry transmitter")
    y12 = out[1]
    s.wire(out, (4480, y12)); s.port((4480, y12), "+12V")
    _, v = s.two("F4", (4480, y12), "R"); s.wire(v, (4800, y12)); s.flag((4800, y12), "VTX_12V")
    s.conn(4800, y12, "J4", "VTX 12 V, (-) = GND", side="R")
    _, c = s.two("C_VTX", (4704, y12), "D"); s.gnd(c)
    q, c = s.free2("B_VTX", "bi", (4704, y12 + 160), "D", T.info("B_VTX")[1], expect={"+": "VTX_12V", "-": "0"})
    s.flag((4704, y12 + 160), "VTX_12V"); s.gnd(c)
    s.text(4600, y12 + 330, ";C_VTX, B_VTX: transmitter load (sim)", 2)
    s.text(4380, y12 - 64, ";F4 PTC 2 A", 2)
    # ---------------------------------------------------------------- 4 5 V buck (LT8641)
    ux, uy = 2400, 2400
    s.frame(1340, 1760, 4300, 3100, "4  5 V / 3 A BUCK: U2 LT8641, 1 MHz (flight controller + receiver), enabled by 12 V PGOOD")
    u = s.put("U2", ux, uy)
    s.wire(u["EN/UV"], (ux, uy - 368)); s.flag((ux, uy - 368), "PG12")
    s.wire(u["Vin1"], (ux - 336, u["Vin1"][1])); s.flag((ux - 336, u["Vin1"][1]), "+12V")
    _, c = s.two("C15", (ux - 272, u["Vin1"][1]), "D"); s.gnd(c)
    s.wire(u["Vin2"], (ux + 336, u["Vin2"][1])); s.flag((ux + 336, u["Vin2"][1]), "+12V")
    _, c = s.two("C16", (ux + 240, u["Vin2"][1]), "D"); s.gnd(c)
    s.wire(u["GND1"], (ux - 192, u["GND1"][1])); s.gnd((ux - 192, u["GND1"][1]))
    s.wire(u["GND2"], (ux + 192, u["GND2"][1])); s.gnd((ux + 192, u["GND2"][1]))
    s.wire(u["INTVcc"], (ux - 336, u["INTVcc"][1])); _, c = s.two("C18", (ux - 336, u["INTVcc"][1]), "D"); s.gnd(c)
    s.wire(u["Sync/Mode"], (ux - 192, u["Sync/Mode"][1])); s.gnd((ux - 192, u["Sync/Mode"][1]))
    _, b = s.two("R14", (ux - 240, u["INTVcc"][1]), "D"); s.wire(b, (ux - 240, u["PG"][1]))
    s.wire(u["PG"], (ux - 336, u["PG"][1])); s.flag((ux - 336, u["PG"][1]), "PG5")
    s.wire(u["TR/SS"], (ux - 192, u["TR/SS"][1])); _, c = s.two("C19", (ux - 192, u["TR/SS"][1]), "D"); s.gnd(c)
    _, c = s.two("R11", u["Rt"], "D"); s.gnd(c)
    s.gnd(u["GND"])
    s.wire(u["BST"], (ux + 240, u["BST"][1])); _, c = s.two("C17", (ux + 240, u["BST"][1]), "D"); s.wire(c, (ux + 240, u["SW"][1]))
    s.wire(u["SW"], (ux + 336, u["SW"][1])); _, o = s.two("L2", (ux + 336, u["SW"][1]), "R"); s.flag((ux + 304, u["SW"][1]), "SW5")
    y5 = o[1]
    s.wire(o, (ux + 1200, y5))
    s.wire(u["Bias"], (ux + 512, u["Bias"][1]), (ux + 512, y5))
    for i, r in enumerate(("C21", "C22")):
        _, c = s.two(r, (ux + 592 + 80 * i, y5), "D"); s.gnd(c)
    _, b = s.two("R12", (ux + 832, y5), "D"); s.wire(b, (ux + 832, u["FB"][1])); s.wire(u["FB"], (ux + 832, u["FB"][1]))
    _, c = s.two("R13", (ux + 832, u["FB"][1]), "D"); s.gnd(c)
    _, c = s.two("C20", (ux + 928, y5), "D"); s.wire(c, (ux + 928, u["FB"][1]), (ux + 832, u["FB"][1]))
    s.port((ux + 1200, y5), "+5V")
    s.conn(ux + 1200, y5 + 160, "J5", "FC + receiver: +5V +5V GND GND", w=380, side="R")
    q, c = s.free2("B_FC", "bi", (ux + 1104, y5), "D", T.info("B_FC")[1], expect={"+": "+5V", "-": "0"}); s.gnd(c)
    s.text(ux + 1000, y5 + 330, ";B_FC: FC + receiver load (sim)", 2)
    # ---------------------------------------------------------------- 5 3.3 V LDO (LT3045)
    vx, vy = 5000, 2400
    s.frame(4360, 1760, 6400, 3100, "5  3.3 V / 0.3 A ULTRALOW-NOISE LDO: U3 LT3045 (sensors), enabled by 5 V PG")
    u = s.put("U3", vx, vy)
    s.flag((vx - 608, u["IN"][1]), "+5V"); s.wire((vx - 608, u["IN"][1]), u["IN"])
    _, c = s.two("C24", (vx - 512, u["IN"][1]), "D"); s.gnd(c)
    _, b = s.two("R19", (vx - 336, u["IN"][1]), "D"); s.wire(b, (vx - 336, u["PG"][1]), u["PG"])
    s.flag((vx - 288, u["PG"][1]), "PG33")
    s.wire(u["EN/UV"], (vx - 288, u["EN/UV"][1])); s.flag((vx - 288, u["EN/UV"][1]), "PG5")
    s.wire(u["SET"], (u["SET"][0], u["SET"][1] + 32)); _, c = s.two("R15", (u["SET"][0], u["SET"][1] + 32), "D"); s.gnd(c)
    s.wire((u["SET"][0], u["SET"][1] + 32), (u["SET"][0] - 96, u["SET"][1] + 32))
    _, c = s.two("C23", (u["SET"][0] - 96, u["SET"][1] + 32), "D"); s.gnd(c)
    s.gnd(u["GND"])
    _, c = s.two("R16", u["ILIM"], "D"); s.gnd(c)
    s.wire(u["OUT"], (vx + 400, u["OUT"][1]), (vx + 400, u["OUTS"][1]), u["OUTS"])
    s.wire((vx + 400, u["OUT"][1]), (vx + 960, u["OUT"][1]))
    _, c = s.two("C25", (vx + 496, u["OUT"][1]), "D"); s.gnd(c)
    _, b = s.two("R17", (vx + 592, u["OUT"][1]), "D"); s.wire(b, (vx + 592, u["PGFB"][1] + 32), (u["PGFB"][0], u["PGFB"][1] + 32), u["PGFB"])
    _, c = s.two("R18", (u["PGFB"][0], u["PGFB"][1] + 32), "D"); s.gnd(c)
    s.port((vx + 960, u["OUT"][1]), "+3V3")
    s.conn(vx + 960, u["OUT"][1] + 160, "J6", "sensors: +3V3 GND", w=260, side="R")
    q, c = s.free2("B_SENS", "bi", (vx + 800, u["OUT"][1]), "D", T.info("B_SENS")[1], expect={"+": "+3V3", "-": "0"}); s.gnd(c)
    s.write(directives=["; Avionics board as a block of Power_System.asc. Ports: PACK1+, PACK2+, PACK3+, +12V, +5V, +3V3. Parameters and models on the top sheet."])
    return s


if __name__ == "__main__":
    s = sheet()
    tbl = {r for p in B.parts if p.sym is not None for r in p.refs()} - {"B_VTX", "B_FC", "B_SENS"}
    print("table parts not drawn:", sorted(tbl - s.used))
    lint = s.lint(); errs = s.verify()
    print(f"{s.name}: {len(s.parts)} parts, {len(s.wires)} wires; lint {len(lint)}; netlist errors {len(errs)}")
    for e in (lint + errs)[:30]: print("   ", e)
    if "--png" in sys.argv: s.render("avionics_drawn.png", scale=0.3)

"""Whole power system as one LTspice schematic (python3 gen_system.py):

  Power_System.asc   top sheet, drawn with wires: 3 x 24S pack -> PDB -> harness -> ESC board -> U15XL motor,
                     and every PDB -> avionics power board -> 12 V / 5 V / 3.3 V
  ESC_Block.asc      the ESC board, drawn part by part (esc_draw.py); inside it U7/U8 ACS772 and U9 STM32 are blocks
  U15XL_Motor.asc    the motor: windings, back-EMF and rotor/prop analog (esc_draw.py)
  Avionics_Block.asc the avionics board, drawn part by part (avionics_draw.py)

Double-click a block in LTspice to open its sheet. Scenario: the packs are connected through their anti-spark
pre-charge (0 -> 88.8 V over 1 ms), all four boards power up, the ESCs enable their drivers at Ten, and at Tpunch
every motor is commanded from standstill (current limited to Imax).
"""
import paths  # noqa: F401  (topology 10's parts tables)
import esc_draw, avionics_draw
import hand_calc as h
from draw import Sheet
from tablesheet import block_asy

h09 = h.h09
g = lambda v: f"{v:.4g}"

# ------------------------------------------------------------------ boards and models
for f in (esc_draw.acs770, esc_draw.stm32, esc_draw.motor, esc_draw.esc_sheet, avionics_draw.sheet): f()
ESC_PINS = [("VBUS", -256, -96), ("MOT_A", 256, -96), ("MOT_B", 256, 0), ("PH_C", 256, 96), ("ENC_THETA", 256, 224), ("ENC_OMEGA", 256, 288)]
block_asy("ESC_Block.asy", ESC_PINS, (-256, -224, 256, 320), "ESC BOARD|LTC7063 x3 + 24 FETs|STM32G431 FOC", "double-click to open")
AV_PINS = [("PACK1+", -288, -96), ("PACK2+", -288, 0), ("PACK3+", -288, 96), ("+12V", 288, -96), ("+5V", 288, 0), ("+3V3", 288, 96)]
block_asy("Avionics_Block.asy", AV_PINS, (-288, -224, 288, 224), "AVIONICS POWER BOARD|12 V / 5 V / 3.3 V", "double-click to open")

# ------------------------------------------------------------------ top sheet
s = Sheet("Power_System")
s.text(0, -120, ";WHOLE POWER SYSTEM: three 24S packs -> three ESC boards -> three motors, and all three packs -> one avionics board", 3)
s.text(0, -72, ";Each pack drives its own ESC and motor (independent channels). The avionics board takes power from every pack through a diode-OR.", 2)
for k in range(3):
    y = 160 + 800 * k; n = k + 1
    v = s.place(f"V_PACK{n}", "battery", 64, y, "R0", f"PWL(0 0 {{Tplug}} {h.V_NOM})", spice=f"Rser={g(h09.Rpk)}")
    s.gnd(v["-"]); s.text(112, y + 120, f";24S pack {n} (88.8 V, 30 mOhm)", 2)
    pdb = (384, y - 64)
    s.wire(v["+"], (64, pdb[1]), pdb); s.flag(pdb, f"PDB{n}")
    lh = s.place(f"L_HARN{n}", "ind", 496, pdb[1] + 16, "R270", g(h09.Lh), spice=f"Rser={g(h09.Rh)}")
    s.wire(pdb, lh["A"]); s.text(560, pdb[1] - 64, ";8 AWG harness, 1 m", 2)
    ex, ey = 1100, pdb[1] + 96
    e = s.place(f"ESC{n}", "ESC_Block", ex, ey, "R0")
    s.wire(lh["B"], e["VBUS"])
    m = s.place(f"MOTOR{n}", "U15XL_Motor", ex + 768, ey, "R0")
    for a, b, lab in (("MOT_A", "A", "A"), ("MOT_B", "B", "B"), ("PH_C", "C", "C")):
        s.wire(e[a], m[b]); s.flag(((e[a][0] + m[b][0]) // 2, e[a][1]), f"M{n}_{lab}")
    s.wire(m["THETA_E"], e["ENC_THETA"]); s.wire(m["OMEGA"], e["ENC_OMEGA"])
    s.text(ex + 300, ey + 260, ";encoder", 1)
# avionics block fed from every PDB (labels PDB1..3 = the same nodes as the packs' PDB wires above)
ax, ay = 1100, 2700
av = s.place("AV1", "Avionics_Block", ax, ay, "R0")
for k in range(3):                      # each PDB runs down the left of the packs into its avionics input
    p = av[f"PACK{k + 1}+"]; top = (64, 160 + 800 * k - 64); xk = -96 - 64 * k
    s.wire(top, (xk, top[1]), (xk, p[1]), p)
for n in ("+12V", "+5V", "+3V3"):
    p = av[n]; s.wire(p, (p[0] + 128, p[1])); s.flag((p[0] + 128, p[1]), f"AV_{n.strip('+')}")
s.text(ax + 480, ay - 104, ";AV_12V -> video / telemetry transmitter", 2)
s.text(ax + 480, ay - 8, ";AV_5V -> flight controller + receiver", 2)
s.text(ax + 480, ay + 88, ";AV_3V3 -> sensors", 2)
s.text(0, ay + 300, ";Phase wires M1_A..M3_C are on this sheet. Inside a block, a node is ESC1:<net>, ESC1:U9:<node> or MOTOR1:<part>"
       " (e.g. V(ESC1:+12V), I(MOTOR1:La)); add it to the .save line to keep it.", 2)

ch1 = ("V(ESC1:+12V) V(ESC1:+5V) V(ESC1:+3V3) V(ESC1:DRV_EN) V(ESC1:PWM_A) V(ESC1:GAH1) V(ESC1:GAL1) V(ESC1:BST_A) "
       "V(ESC1:ISNS_A) V(ESC1:ISNS_B) V(ESC1:SW_AUX) V(ESC1:U9:iq) V(ESC1:U9:iqref) V(ESC1:U9:id) "
       "I(MOTOR1:La) I(MOTOR1:Lb) I(MOTOR1:Lc) V(MOTOR1:rpm) V(MOTOR1:te) V(ESC1:PH_A) V(ESC1:GAH2) V(AV1:SW5) "
       "V(AV1:VIN_AV) V(AV1:VIN_PROT) V(AV1:SW12) V(AV1:PG12) V(AV1:PG5) I(AV1:L1) I(AV1:L2)")
allch = " ".join(f"V(M{n}_A) V(M{n}_B) V(M{n}_C) V(PDB{n}) I(L_HARN{n}) I(V_PACK{n}) V(MOTOR{n}:rpm)" for n in (1, 2, 3))
D = [
    "; === 10  WHOLE POWER SYSTEM: power-up of all four boards, then every motor commanded from standstill ===",
    "; Blocks: double-click ESC1..3, MOTOR1..3 or AV1 to open them. Board parts carry their PCB reference designators (see the KiCad entry guide).",
    f"!.param KV={h09.KV} Ke={{60/(2*pi*KV)}} Kph={{Ke/sqrt(3)}} Pp={h09.Pp} Rph={g(h09.Rph)} Lph={g(h09.Lph)}",
    f"!.param Jrot={h09.Jrot} Kprop={g(h09.Kprop)} Bfric={g(h09.Bfric)}",
    f"!.param Fsw={g(h09.Fsw)} Tsw={{1/Fsw}} Rdt=150k",
    f"!.param Kpi={g(h09.Kpi)} Kii={g(h09.Kii)} Kpw={g(h09.Kpw)} Kiw={g(h09.Kiw)}",
    "!.param W0=0 Iq0=0 Wpunch=50 Imax=60          ; motors start at rest; at Tpunch the speed command steps, current-limited to Imax",
    "!.param Tplug=1m Ten=3m Tpunch=4m Tvtx=4.5m Tfc=5m Tpull=1      ; (Tpull: unused here, packs stay connected)",
    "!.model SMBJ110A D(Is=1p Rs=12 N=1 BV=128 IBV=1m)",
    "!.tran 0 6m 0 uic        ; skip the DC solve: packs at 0 V, every board cold",
    "!.save V(AV_12V) V(AV_5V) V(AV_3V3) " + allch + " " + ch1,
    "!.meas TRAN Ipack1 AVG -I(V_PACK1) FROM 5.5m TO 6m", "!.meas TRAN Ipack2 AVG -I(V_PACK2) FROM 5.5m TO 6m",
    "!.meas TRAN Ipack3 AVG -I(V_PACK3) FROM 5.5m TO 6m",
    "!.meas TRAN Iesc1 AVG I(L_HARN1) FROM 5.5m TO 6m",
    "!.meas TRAN Vav12 AVG V(AV_12V) FROM 5.5m TO 6m", "!.meas TRAN Vav5 AVG V(AV_5V) FROM 5.5m TO 6m",
    "!.meas TRAN Vav33 AVG V(AV_3V3) FROM 5.5m TO 6m",
    "!.meas TRAN T_av12 WHEN V(AV_12V)=10.8 RISE=1", "!.meas TRAN T_av5 WHEN V(AV_5V)=4.5 RISE=1",
    "!.meas TRAN Iph1_rms RMS I(MOTOR1:La) FROM 5.5m TO 6m", "!.meas TRAN Iq1 AVG V(ESC1:U9:iq) FROM 5.5m TO 6m",
    "!.meas TRAN RPM1 MAX V(MOTOR1:rpm)", "!.meas TRAN V12_esc1 AVG V(ESC1:+12V) FROM 5.5m TO 6m",
]
s.write(directives=D)
import sys
if "--png" in sys.argv: s.render("power_system_top.png", scale=0.3, dpi=250)
print("wrote Power_System.asc + ESC_Block / U15XL_Motor / ACS772 / STM32G431_FOC / Avionics_Block sheets and symbols")

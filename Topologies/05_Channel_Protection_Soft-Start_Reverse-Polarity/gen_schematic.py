"""Generates ChannelProtection.asc: one battery channel (topology 04, channel 2 harness) with
   (a) plain XT60, (b) XT90-S style precharge resistor, (c) back-to-back N-MOSFET soft-start + reverse-polarity block.
   .step Case: 0 bare XT60 | 1 XT90-S precharge | 2 active MOSFET without Cgs (fails) | 3 active MOSFET + Cgs | 4 reversed, bare | 5 reversed, active"""
L = []; a = L.append
a("Version 4"); a("SHEET 1 2400 1600")
def F(x, y, n): a(f"FLAG {x} {y} {n}")
def S(sym, x, y, rot, inst, val, extra=()):
    a(f"SYMBOL {sym} {x} {y} {rot}"); a(f"SYMATTR InstName {inst}"); a(f"SYMATTR Value {val}")
    for e in extra: a(e)
def T(x, y, s): a(f"TEXT {x} {y} Left 2 {s}")
def two(sym, x, y, inst, val, top, bot, extra=()):          # vertical 2-pin part, nets by flags
    S(sym, x, y, "R0", inst, val, extra)
    pins = {"res": (16, 16, 16, 96), "ind": (16, 16, 16, 96), "cap": (16, 0, 16, 64), "diode": (16, 0, 16, 64),
            "voltage": (0, 16, 0, 96), "bv": (0, 16, 0, 96), "bi": (0, 0, 0, 80)}[sym]
    F(x + pins[0], y + pins[1], top); F(x + pins[2], y + pins[3], bot)
def nmos(x, y, inst, d, g, s):
    S("nmos", x, y, "R0", inst, "PROT_FET"); F(x + 48, y, d); F(x, y + 80, g); F(x + 48, y + 96, s)

# battery (polarity set by Pol) and internal resistance
two("voltage", 64, 96, "Vbat", "{Pol*Vb}", "braw", "0")
two("res", 176, 80, "Rint", "{Rbatt}", "braw", "bt")
# connector: main contact and (XT90-S) precharge contact, as time-switched conductances
two("bi", 320, 96, "B_MAIN", "I=V(bt,hp)*({Gon}*(1+tanh((time-{Tmain})/{Tc}))/2+1e-9)", "bt", "hp")
two("bi", 448, 96, "B_PRE", "I=V(bt,hp)*{Pre}/{Rpre}*(1+tanh((time-{Tplug})/{Tc}))/2", "bt", "hp")
# harness (channel 2 of topology 04: 30 cm pair) + and -
two("ind", 560, 80, "Lpos", "{Lloop/2}", "hp", "bus", ["SYMATTR SpiceLine Rser={Rloop/2}"])
two("ind", 688, 80, "Lneg", "{Lloop/2}", "0", "hn", ["SYMATTR SpiceLine Rser={Rloop/2}"])
# protection: back-to-back N-MOSFETs in the negative line (common source s), or a bypass when Prot=0
nmos(880, 96, "MQ1", "hn", "gt", "s")        # Q1 body diode: s -> hn  (conducts normal return current; blocks reverse)
nmos(1040, 96, "MQ2", "g", "gt", "s")        # Q2 body diode: s -> g   (blocks normal current until the gate opens: soft-start)
two("res", 1184, 80, "Rbyp", "{if(Prot,1G,0.1m)}", "hn", "g")
two("res", 1312, 80, "Rg", "{Rgate}", "bus", "gt")
two("cap", 1440, 96, "Cm", "{Cmiller}", "gt", "g")
two("res", 1568, 80, "Rgs", "100k", "gt", "s")
two("diode", 1696, 96, "Dz", "DZ12", "s", "gt")
two("cap", 1776, 96, "Cgsx", "{Cgsx}", "gt", "s")   # holds the gate down against the plug-in dV/dt kick through Cm
# ESC input: DC link caps, inverter body diodes (lumped), and its averaged load with an enable
two("cap", 1856, 96, "Ccer", "10u", "bus", "g", ["SYMATTR SpiceLine Rser=2m Lser=2n"])
two("cap", 1984, 96, "Cbulk", "470u", "bus", "g", ["SYMATTR SpiceLine Rser=30m Lser=10n"])
two("diode", 2112, 96, "Desc", "ESC_BODY", "g", "bus")
two("bi", 2240, 96, "B_LOAD", "I=V(pload)/max(V(bus,g),9)*(1+tanh(4*(V(bus,g)-9)))/2", "bus", "g")
S("voltage", 2240, 336, "R0", "Vpload", "PWL(0 0 {Ton} 0 {Ton+5m} {P1} {Tpunch} {P1} {Tpunch+0.2m} {P2})"); F(2240, 352, "pload"); F(2240, 432, "0")

T(32, 8, "; BATTERY 4S + CONNECTOR (main + precharge contact)       HARNESS 30 cm       PROTECTION: back-to-back N-FETs in the - line       ESC DC LINK + LOAD")
D = [
 "; === 05  PER-CHANNEL PROTECTION: anti-spark soft-start + reverse-polarity block (one channel of topology 04) ===",
 "!.param Vb=15.0 Rbatt=20m Rloop=5.97m Lloop=140n",
 "!.param Tplug=1m Tc=50n Gon={1/0.5m} Rpre=5 Tpre=10m Tmain={Tplug+Pre*Tpre}",
 "!.param Rgate=12k Cmiller=100n      ; soft-start: Iinrush = (Vb - Vplateau)*Cdc/(Rgate*Cmiller) ~ 5 A;  Cgs > Cmiller*(2*Vb/Vto - 1)",
 "!.param Ton=20m P1=126 Tpunch=35m P2=293   ; ESC enables at 20 ms, ramps to 126 W (20,000 RPM), punches to 293 W",
 "!.step param Case list 0 1 2 3 4 5   ; 0 bare XT60 | 1 XT90-S precharge | 2 active FETs, no Cgs (naive) | 3 active FETs + 2.2 uF Cgs | 4 reversed, bare | 5 reversed, active",
 "!.param Pol={if(Case>=4,-1,1)} Pre={if(Case==1,1,0)} Prot={if(Case==2,1,if(Case==3,1,if(Case==5,1,0)))} Cgsx={if(Case==2,1p,2.2u)}",
 "!.model PROT_FET VDMOS(Rd=0.4m Rs=0.2m Vto=2.5 Kp=300 Cgdmax=2n Cgdmin=300p Cgs=6n Cjo=3n Is=10p N=1.05 Rb=2m Vds=40 Ron=1m Qg=80n mfg=Learning)",
 "!.model DZ12 D(Is=1n Rs=5 BV=12 IBV=1m N=1.5)",
 "!.model ESC_BODY D(Is=15p N=1.05 Rs=1.3m)      ; the 6 inverter body diodes, lumped",
 "!.tran 0 45m 0",
 "!.options method=gear      ; trapezoidal integration rang numerically at the punch (5 min, 2 GB); Gear damps it",
 "!.save V(bus) V(g) V(hn) V(s) V(gt) V(hp) V(bt) I(Lpos) I(Lneg) I(Cbulk) I(Ccer) Id(MQ1) Id(MQ2) I(Desc) I(B_PRE) I(B_MAIN) V(pload)",
]
M = [
 "!.meas TRAN Ipk_plug MAX I(Lpos) FROM 0 TO 19m",
 "!.meas TRAN Imin_plug MIN I(Lpos) FROM 0 TO 19m",
 "!.meas TRAN Ipk_main MAX I(Lpos) FROM {Tmain-0.05m} TO {Tmain+1m}",
 "!.meas TRAN Vpk_plug MAX V(bus,g) FROM 0 TO 19m",
 "!.meas TRAN V_ready AVG V(bus,g) FROM 17m TO 19m",
 "!.meas TRAN T90 WHEN V(bus,g)={0.9*Vb} RISE=1",
 "!.meas TRAN E_fets INTEG V(g,s)*Id(MQ2)+V(hn,s)*Id(MQ1) FROM 0 TO 19m",
 "!.meas TRAN Pk_fet MAX V(g,s)*Id(MQ2) FROM 0 TO 19m",
 "!.meas TRAN E_rpre INTEG V(bt,hp)*I(B_PRE) FROM 0 TO 19m",
 "!.meas TRAN Irev_avg AVG I(Lpos) FROM 15m TO 19m",
 "!.meas TRAN Vgs_on AVG V(gt,s) FROM 28m TO 33m",
 "!.meas TRAN Ibat_cruise AVG I(Lpos) FROM 28m TO 33m",
 "!.meas TRAN Vbus_cruise AVG V(bus,g) FROM 28m TO 33m",
 "!.meas TRAN Pprot_cruise AVG V(g,s)*Id(MQ2)+V(hn,s)*Id(MQ1) FROM 28m TO 33m",
 "!.meas TRAN Ibat_punch AVG I(Lpos) FROM 40m TO 45m",
 "!.meas TRAN Vbus_punch AVG V(bus,g) FROM 40m TO 45m",
 "!.meas TRAN Pprot_punch AVG V(g,s)*Id(MQ2)+V(hn,s)*Id(MQ1) FROM 40m TO 45m",
]
for i, s in enumerate(D):
    T(32, -460 + 32 * i, s)
for i, s in enumerate(M):
    T(32, 560 + 28 * i, s)
open("ChannelProtection.asc", "w", newline="\r\n").write("\n".join(L) + "\n")

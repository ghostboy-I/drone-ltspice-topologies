"""Generates ThreePhase_FOC.asc: 3-phase inverter + sinusoidal PMSM under sensored field-oriented control.
Kept so the layout can be regenerated or edited programmatically."""
L = []; a = L.append
a("Version 4"); a("SHEET 1 2600 2200")
def W(x1, y1, x2, y2): a(f"WIRE {x1} {y1} {x2} {y2}")
def F(x, y, n): a(f"FLAG {x} {y} {n}")
def S(sym, x, y, rot, inst, val, extra=()):
    a(f"SYMBOL {sym} {x} {y} {rot}"); a(f"SYMATTR InstName {inst}"); a(f"SYMATTR Value {val}")
    for e in extra: a(e)
def T(x, y, s): a(f"TEXT {x} {y} Left 2 {s}")
def BV(x, y, inst, expr, node):          # behavioral voltage source to ground: + (x,y+16)  - (x,y+96)
    S("bv", x, y, "R0", inst, "V=" + expr); F(x, y + 16, node); F(x, y + 96, "0")

# ---------------- battery, wiring, DC link (same as topologies 01/02) ----------------
S("voltage", 64, 128, "R0", "Vbat", "{Vbatt}"); F(64, 224, "0"); F(64, 144, "vbat")
S("res", 96, 160, "R270", "Rint", "{Rbatt}"); W(64, 144, 112, 144)
S("ind", 224, 160, "R270", "Lwire", "{Lwire}", ["SYMATTR SpiceLine Rser=2m"]); W(192, 144, 240, 144)
S("cap", 400, 144, "R0", "Cbulk", "470u", ["SYMATTR SpiceLine Rser=30m Lser=10n"]); F(416, 208, "0")
S("cap", 496, 144, "R0", "Cceram", "10u", ["SYMATTR SpiceLine Rser=2m"]); F(512, 208, "0")
W(320, 144, 1328, 144); F(448, 144, "bus")

# ---------------- three half-bridge legs, every leg complementary PWM with dead time ----------------
for k, (ph, x) in enumerate([("a", 800), ("b", 1040), ("c", 1280)]):
    P = ph.upper(); node = "p" + ph
    S("nmos", x, 144, "R0", f"M{P}H", "ESC_FET")
    S("nmos", x, 240, "R0", f"M{P}L", "ESC_FET")
    F(x + 48, 336, "0"); F(x + 48, 240, node)
    S("res", x - 16, 208, "R90", f"Rg_{P}H", "{Rg}"); W(x - 32, 224, x, 224)
    S("res", x - 16, 304, "R90", f"Rg_{P}L", "{Rg}"); W(x - 32, 320, x, 320)
    S("bv", x - 112, 208, "R0", f"B_G{P}H", f"V={{Vdrv}}*V(h{ph})"); F(x - 112, 304, node)   # floating high-side drive
    S("bv", x - 112, 304, "R0", f"B_G{P}L", f"V={{Vdrv}}*V(l{ph})"); F(x - 112, 400, "0")
    T(x - 96, 440, f";  LEG {P}")

# ---------------- PMSM: 3 wye phases, SINUSOIDAL back-EMF  e_x = -Kph*w*sin(the - k*120deg) ----------------
for k, (ph, y) in enumerate([("a", 560), ("b", 656), ("c", 752)]):
    P = ph.upper(); shift = f"-{2*k}*pi/3" if k else ""
    F(1520, y, "p" + ph)
    S("ind", 1504, y + 16, "R270", f"L{ph}", "{Lph}")
    S("res", 1616, y + 16, "R270", f"R{ph}", "{Rph}")
    W(1600, y, 1632, y); F(1712, y, "x" + ph)
    S("bv", 1696, y, "R270", f"B_E{P}", f"V=-{{Kph}}*V(omega)*sin(V(the){shift})")
W(1792, 560, 1792, 752); F(1792, 560, "n")
T(1488, 480, ";  PMSM (wye)  -  each phase: L, R, sinusoidal back-EMF.  Same R, L, KV and poles as topology 02")

# ---------------- mechanics + rotor angle (ideal encoder) ----------------
S("bv", 240, 976, "R0", "B_TE", "V=-{Kph}*(sin(V(the))*I(La)+sin(V(the)-2*pi/3)*I(Lb)+sin(V(the)-4*pi/3)*I(Lc))")
F(240, 992, "te"); F(240, 1072, "0")
S("bi", 400, 1072, "R180", "B_Tmotor", "I=V(te)"); F(400, 1072, "0"); F(400, 992, "omega")
S("cap", 512, 992, "R0", "C_J", "{Jrot}"); F(528, 992, "omega"); F(528, 1056, "0")
S("bi", 640, 992, "R0", "B_Tprop", "I={Kprop}*V(omega)*abs(V(omega))+{Bfric}*V(omega)"); F(640, 992, "omega"); F(640, 1072, "0")
S("res", 736, 976, "R0", "R_leak", "100Meg"); F(752, 992, "omega"); F(752, 1072, "0")
S("bi", 880, 1072, "R180", "B_dtheta", "I=V(omega)"); F(880, 1072, "0"); F(880, 992, "theta")
S("cap", 992, 992, "R0", "C_theta", "1"); F(1008, 992, "theta"); F(1008, 1056, "0")
S("res", 1104, 976, "R0", "R_leak2", "1G"); F(1120, 992, "theta"); F(1120, 1072, "0")
BV(1248, 976, "B_THE", "{Pp}*V(theta)", "the")
BV(1376, 976, "B_RPM", "V(omega)*60/(2*pi)", "rpm")
BV(1504, 976, "B_WE", "{Pp}*V(omega)", "we")
T(32, 900, "; MECHANICS:  V(te)=torque  V(omega)=rad/s (C_J=inertia)  V(theta)=rotor angle (ideal encoder)  V(the)=electrical angle  V(we)=electrical rad/s")

# ---------------- FOC controller (continuous-time behavioral blocks) ----------------
y0 = 1240
T(32, y0 - 80, "; FOC CONTROLLER:  speed PI -> iq*,  Clarke + Park of the measured currents,  d/q current PIs + decoupling,  inverse Park/Clarke,  min-max (SVPWM) injection")
# row 1: references and speed loop
S("voltage", 64, y0, "R0", "Vwref", "PWL(0 0 {Tramp} {Wref})"); F(64, y0 + 16, "wref"); F(64, y0 + 96, "0")
S("voltage", 192, y0, "R0", "Vidref", "PULSE(0 {-Idstep} {Tstep} 1u 1u {Tdur})"); F(192, y0 + 16, "idref"); F(192, y0 + 96, "0")
BV(320, y0, "B_IQREF", "limit({Kpw}*(V(wref)-V(omega))+{Kiw}*idt(V(wref)-V(omega)), -{Imax}, {Imax})", "iqref")
# row 1: Clarke + Park
BV(640, y0, "B_IAL", "I(La)", "ial")
BV(768, y0, "B_IBE", "(I(La)+2*I(Lb))/sqrt(3)", "ibe")
BV(896, y0, "B_ID", "V(ial)*cos(V(the))+V(ibe)*sin(V(the))", "id")
BV(1024, y0, "B_IQ", "-V(ial)*sin(V(the))+V(ibe)*cos(V(the))", "iq")
# row 2: current PIs with decoupling feed-forward
y1 = y0 + 200
BV(64, y1, "B_VD", "{Kpi}*(V(idref)-V(id))+{Kii}*idt(V(idref)-V(id)) - {Dec}*V(we)*{Lph}*V(iq)", "vd")
BV(448, y1, "B_VQ", "{Kpi}*(V(iqref)-V(iq))+{Kii}*idt(V(iqref)-V(iq)) + {Dec}*(V(we)*{Lph}*V(id)+{Kph}*V(omega))", "vq")
# row 2: inverse Park + inverse Clarke
BV(832, y1, "B_VAL", "V(vd)*cos(V(the))-V(vq)*sin(V(the))", "val")
BV(960, y1, "B_VBE", "V(vd)*sin(V(the))+V(vq)*cos(V(the))", "vbe")
BV(1088, y1, "B_VA", "V(val)", "va")
BV(1216, y1, "B_VB", "-V(val)/2+sqrt(3)/2*V(vbe)", "vb")
BV(1344, y1, "B_VC", "-V(val)/2-sqrt(3)/2*V(vbe)", "vc")
# row 3: SVPWM (min-max zero-sequence injection), duty, comparators
y2 = y1 + 200
BV(64, y2, "B_VOFF", "{Svm}*(max(max(V(va),V(vb)),V(vc))+min(min(V(va),V(vb)),V(vc)))/2", "voff")
S("voltage", 192, y2, "R0", "Vtri", "PULSE(0 1 0 {Tsw/2} {Tsw/2} 0 {Tsw})"); F(192, y2 + 16, "tri"); F(192, y2 + 96, "0")
for k, ph in enumerate("abc"):
    x = 448 + 384 * k
    BV(x, y2, f"B_D{ph.upper()}", f"limit(0.5+(V(v{ph})-V(voff))/V(bus), 0.01, 0.99)", "du" + ph)
    BV(x + 128, y2, f"B_H{ph.upper()}", f"(1+tanh(500*(V(du{ph})-{{dband}}-V(tri))))/2", "h" + ph)
    BV(x + 256, y2, f"B_L{ph.upper()}", f"(1+tanh(500*(V(tri)-V(du{ph})-{{dband}})))/2", "l" + ph)

# ---------------- directives ----------------
D = [
 "; === 03  THREE-PHASE INVERTER + SINUSOIDAL PMSM, SENSORED FIELD-ORIENTED CONTROL (FOC) with SVPWM ===",
 "!.param Vbatt=15.2 Rbatt=20m Lwire=100n",
 "!.param Fsw=48k Tsw={1/Fsw} Tdead=100n dband={Tdead/Tsw} Vdrv=10 Rg=4.7",
 "!.param KV=2300 Ke={60/(2*pi*KV)} Kph={Ke/sqrt(3)} Pp=7 Rph=50m Lph=7.5u   ; line-line peak EMF = Ke*w (same KV as 02)",
 "!.param Jrot=5u Kprop=1.15e-8 Bfric=1u",
 "!.param RPMref=14000 Wref={RPMref*2*pi/60} Tramp=120m Imax=30          ; speed command ramps 0 -> 14000 RPM",
 "!.param Fci=3k Kpi={Lph*2*pi*Fci} Kii={Rph*2*pi*Fci}                    ; current PI: zero cancels the R-L pole",
 "!.param Fcw=30 Kt={1.5*Kph} Kpw={Jrot*2*pi*Fcw/Kt} Kiw={Kpw*2*pi*Fcw/4}   ; speed PI",
 "!.param Dec=1 Svm=1 Idstep=5 Tstep=170m Tdur=10m    ; decoupling on, SVPWM on, -5 A d-axis test step",
 "!.model ESC_FET VDMOS(Rd=2.5m Rs=0.5m Vto=1.8 Kp=120 Cgdmax=1.2n Cgdmin=150p Cgs=2.2n Cjo=1.5n Is=5p N=1.05 Rb=4m Tt=20n Vds=30 Ron=3m Qg=30n mfg=Learning)",
 "!.tran 0 250m 0",
 "!.save V(bus) V(pa) V(pb) V(pc) V(n) V(xa) V(xb) V(xc) V(omega) V(rpm) V(te) V(the) V(wref) V(id) V(iq) V(idref) V(iqref) V(vd) V(vq) V(va) V(vb) V(vc) V(voff) V(dua) V(dub) V(duc) I(La) I(Lb) I(Lc) I(Lwire) Id(MAH) Id(MAL) Id(MBH) Id(MBL) Id(MCH) Id(MCL)",
 "!.meas TRAN RPM_final AVG V(rpm) FROM 230m TO 250m",
 "!.meas TRAN Ibat_avg AVG I(Lwire) FROM 230m TO 250m",
 "!.meas TRAN Iph_rms RMS I(La) FROM 230m TO 250m",
 "!.meas TRAN Iph_peak MAX abs(I(La)) FROM 0 TO 250m",
 "!.meas TRAN Iq_avg AVG V(iq) FROM 230m TO 250m",
 "!.meas TRAN Id_avg AVG V(id) FROM 230m TO 250m",
 "!.meas TRAN Iq_max MAX V(iqref) FROM 0 TO 150m",
 "!.meas TRAN Vd_avg AVG V(vd) FROM 230m TO 250m",
 "!.meas TRAN Vq_avg AVG V(vq) FROM 230m TO 250m",
 "!.meas TRAN Te_avg AVG V(te) FROM 230m TO 250m",
 "!.meas TRAN Te_ripple PP V(te) FROM 245m TO 250m",
 "!.meas TRAN Vbus_ripple PP V(bus) FROM 245m TO 250m",
 "!.meas TRAN Id_at_tau AVG V(id) FROM {Tstep+1/(2*pi*Fci)-2u} TO {Tstep+1/(2*pi*Fci)+2u}",
 "!.meas TRAN Id_settled AVG V(id) FROM {Tstep+4m} TO {Tstep+6m}",
 "!.meas TRAN Pin AVG V(bus)*I(Lwire) FROM 230m TO 250m",
 "!.meas TRAN Pmech AVG V(te)*V(omega) FROM 230m TO 250m",
 "!.meas TRAN Pcu AVG {Rph}*(I(La)**2+I(Lb)**2+I(Lc)**2) FROM 230m TO 250m",
 "!.meas TRAN Pfet_hi AVG V(bus,pa)*Id(MAH)+V(bus,pb)*Id(MBH)+V(bus,pc)*Id(MCH) FROM 230m TO 250m",
 "!.meas TRAN Pfet_lo AVG V(pa)*Id(MAL)+V(pb)*Id(MBL)+V(pc)*Id(MCL) FROM 230m TO 250m",
 "!.meas TRAN Efficiency PARAM Pmech/Pin",
]
for i, s in enumerate(D):
    T(32, -560 + 32 * i if i < 12 else 2000 + 28 * (i - 12), s)
T(32, 40, "; BATTERY 4S"); T(352, 40, "; DC-LINK CAPS"); T(880, 40, "; 3-PHASE INVERTER (3 half-bridge legs, all complementary)")
open("ThreePhase_FOC.asc", "w", newline="\r\n").write("\n".join(L) + "\n")

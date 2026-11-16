"""Generates ThreePhase_ESC_BLDC.asc (kept so the layout can be regenerated/edited programmatically)."""
L = []; a = L.append
a("Version 4"); a("SHEET 1 2200 1500")
def W(x1, y1, x2, y2): a(f"WIRE {x1} {y1} {x2} {y2}")
def F(x, y, n): a(f"FLAG {x} {y} {n}")
def S(sym, x, y, rot, inst, val, extra=()):
    a(f"SYMBOL {sym} {x} {y} {rot}"); a(f"SYMATTR InstName {inst}"); a(f"SYMATTR Value {val}")
    for e in extra: a(e)
def T(x, y, s): a(f"TEXT {x} {y} Left 2 {s}")

# ---------------- battery, wiring, DC link (same as topology 01) ----------------
S("voltage", 64, 128, "R0", "Vbat", "{Vbatt}"); F(64, 224, "0"); F(64, 144, "vbat")
S("res", 96, 160, "R270", "Rint", "{Rbatt}"); W(64, 144, 112, 144)
S("ind", 224, 160, "R270", "Lwire", "{Lwire}", ["SYMATTR SpiceLine Rser=2m"]); W(192, 144, 240, 144)
S("cap", 400, 144, "R0", "Cbulk", "470u", ["SYMATTR SpiceLine Rser=30m Lser=10n"]); F(416, 208, "0")
S("cap", 496, 144, "R0", "Cceram", "10u", ["SYMATTR SpiceLine Rser=2m"]); F(512, 208, "0")
W(320, 144, 1328, 144); F(448, 144, "bus")

# ---------------- three half-bridge legs ----------------
for k, (ph, x) in enumerate([("a", 800), ("b", 1040), ("c", 1280)]):
    P = ph.upper(); node = "p" + ph; shift = f"-{2*k}*pi/3" if k else ""
    S("nmos", x, 144, "R0", f"M{P}H", "ESC_FET")            # D(x+48,144) G(x,224) S(x+48,240)
    S("nmos", x, 240, "R0", f"M{P}L", "ESC_FET")            # D(x+48,240) G(x,320) S(x+48,336)
    F(x + 48, 336, "0"); F(x + 48, 240, node)
    S("res", x - 16, 208, "R90", f"Rg_{P}H", "{Rg}"); W(x - 32, 224, x, 224)   # pins (x-32,224) (x-112,224)
    S("res", x - 16, 304, "R90", f"Rg_{P}L", "{Rg}"); W(x - 32, 320, x, 320)   # pins (x-32,320) (x-112,320)
    th = f"V(the){shift}"
    S("bv", x - 112, 208, "R0", f"B_G{P}H", f"V={{Vdrv}}*hi({th})*V(pwmh)")      # + (x-112,224)  - (x-112,304)
    F(x - 112, 304, node)
    S("bv", x - 112, 304, "R0", f"B_G{P}L", f"V={{Vdrv}}*(lo({th})+{{Sync}}*hi({th})*V(pwml))")  # + (x-112,320) - (x-112,400)
    F(x - 112, 400, "0")
    T(x - 96, 440, f";  LEG {P}")

# ---------------- BLDC motor: 3 wye-connected phases (R, L, trapezoidal back-EMF) ----------------
for k, (ph, y) in enumerate([("a", 560), ("b", 656), ("c", 752)]):
    P = ph.upper(); shift = f"-{2*k}*pi/3" if k else ""
    F(1520, y, "p" + ph)
    S("ind", 1504, y + 16, "R270", f"L{ph}", "{Lph}")        # A(1520,y) B(1600,y)
    S("res", 1616, y + 16, "R270", f"R{ph}", "{Rph}")        # A(1632,y) B(1712,y)
    W(1600, y, 1632, y); F(1712, y, "x" + ph)
    S("bv", 1696, y, "R270", f"B_E{P}", f"V={{Ke/2}}*V(omega)*trap(V(the){shift})")  # + (1712,y) - (1792,y)
W(1792, 560, 1792, 752); F(1792, 560, "n")
T(1488, 480, ";  BLDC MOTOR (wye, neutral n not accessible)  -  each phase: L, R, trapezoidal back-EMF")

# ---------------- mechanics + rotor angle ----------------
S("bv", 240, 976, "R0", "B_TE", "V={Ke/2}*(trap(V(the))*I(La)+trap(V(the)-2*pi/3)*I(Lb)+trap(V(the)-4*pi/3)*I(Lc))")
F(240, 992, "te"); F(240, 1072, "0")
S("bi", 400, 1072, "R180", "B_Tmotor", "I=V(te)"); F(400, 1072, "0"); F(400, 992, "omega")
S("cap", 512, 992, "R0", "C_J", "{Jrot}"); F(528, 992, "omega"); F(528, 1056, "0")
S("bi", 640, 992, "R0", "B_Tprop", "I={Kprop}*V(omega)*abs(V(omega))+{Bfric}*V(omega)"); F(640, 992, "omega"); F(640, 1072, "0")
S("res", 736, 976, "R0", "R_leak", "100Meg"); F(752, 992, "omega"); F(752, 1072, "0")
S("bi", 880, 1072, "R180", "B_dtheta", "I=V(omega)"); F(880, 1072, "0"); F(880, 992, "theta")
S("cap", 992, 992, "R0", "C_theta", "1"); F(1008, 992, "theta"); F(1008, 1056, "0")
S("res", 1104, 976, "R0", "R_leak2", "1G"); F(1120, 992, "theta"); F(1120, 1072, "0")
S("bv", 1248, 976, "R0", "B_THE", "V={Pp}*V(theta)"); F(1248, 992, "the"); F(1248, 1072, "0")
S("bv", 1376, 976, "R0", "B_RPM", "V=V(omega)*60/(2*pi)"); F(1376, 992, "rpm"); F(1376, 1072, "0")
T(32, 900, "; MECHANICS:  V(te)=motor torque  V(omega)=rad/s (C_J=inertia)  V(theta)=rotor angle (integral of omega, C=1F)  V(the)=electrical angle = Pp*theta")

# ---------------- PWM generation ----------------
S("voltage", 240, 1200, "R0", "Vtri", "PULSE(0 1 0 {Tsw/2} {Tsw/2} 0 {Tsw})"); F(240, 1216, "tri"); F(240, 1296, "0")
S("voltage", 400, 1200, "R0", "Vthrottle", "PWL(0 0 {Tramp} {Duty})"); F(400, 1216, "duty"); F(400, 1296, "0")
S("bv", 560, 1200, "R0", "B_PWMH", "V=(1+tanh(500*(V(duty)-{db}-V(tri))))/2"); F(560, 1216, "pwmh"); F(560, 1296, "0")
S("bv", 720, 1200, "R0", "B_PWML", "V=(1+tanh(500*(V(tri)-V(duty)-{db})))/2"); F(720, 1216, "pwml"); F(720, 1296, "0")
T(32, 1136, "; PWM: pwmh = high-side chop, pwml = its complement with dead time (used only when Sync=1)")

# ---------------- directives ----------------
D = [
 "; === 02  THREE-PHASE ESC (6 half-bridges = 3 legs) + BLDC, 6-STEP TRAPEZOIDAL COMMUTATION with ideal Hall sensors ===",
 "!.param Vbatt=15.2 Rbatt=20m Lwire=100n",
 "!.param Fsw=48k Tsw={1/Fsw} Tdead=100n db={Tdead/Tsw} Vdrv=10 Rg=4.7",
 "!.param Duty=0.5 Tramp=30m",
 "!.param KV=2300 Ke={60/(2*pi*KV)} Pp=7 Rph=50m Lph=7.5u    ; 12N14P 2205-class: line-line 0.1 ohm, 15 uH",
 "!.param Jrot=5u Kprop=1.15e-8 Bfric=1u",
 "!.step param Sync list 0 1     ; 0 = high-side PWM, low side ON (body-diode freewheel)   1 = complementary (synchronous) PWM",
 "!.func trap(x) = limit(6/pi*asin(sin(x)), -1, 1)       ; 120-degree flat-top trapezoid",
 "!.func hi(x) = (1+tanh(100*(sin(x)-0.5)))/2              ; Hall logic: phase drives HIGH during its +flat top",
 "!.func lo(x) = (1+tanh(100*(-sin(x)-0.5)))/2             ; Hall logic: phase drives LOW during its -flat top",
 "!.model ESC_FET VDMOS(Rd=2.5m Rs=0.5m Vto=1.8 Kp=120 Cgdmax=1.2n Cgdmin=150p Cgs=2.2n Cjo=1.5n Is=5p N=1.05 Rb=4m Tt=20n Vds=30 Ron=3m Qg=30n mfg=Learning)",
 "!.tran 0 300m 0",
 "!.save V(bus) V(pa) V(pb) V(pc) V(n) V(xa) V(xb) V(xc) V(omega) V(rpm) V(te) V(the) V(duty) V(tri) I(La) I(Lb) I(Lc) I(Lwire) Id(MAH) Id(MAL) Id(MBH) Id(MBL) Id(MCH) Id(MCL)",
 "!.meas TRAN RPM_final AVG V(rpm) FROM 280m TO 300m",
 "!.meas TRAN Ibat_avg AVG I(Lwire) FROM 280m TO 300m",
 "!.meas TRAN Iph_rms RMS I(La) FROM 280m TO 300m",
 "!.meas TRAN Iph_peak MAX abs(I(La)) FROM 0 TO 300m",
 "!.meas TRAN Te_avg AVG V(te) FROM 280m TO 300m",
 "!.meas TRAN Te_ripple PP V(te) FROM 295m TO 300m",
 "!.meas TRAN Vbus_ripple PP V(bus) FROM 295m TO 300m",
 "!.meas TRAN Pin AVG V(bus)*I(Lwire) FROM 280m TO 300m",
 "!.meas TRAN Pmech AVG V(te)*V(omega) FROM 280m TO 300m",
 "!.meas TRAN Pcu AVG {Rph}*(I(La)**2+I(Lb)**2+I(Lc)**2) FROM 280m TO 300m",
 "!.meas TRAN Pfet_hi AVG V(bus,pa)*Id(MAH)+V(bus,pb)*Id(MBH)+V(bus,pc)*Id(MCH) FROM 280m TO 300m",
 "!.meas TRAN Pfet_lo AVG V(pa)*Id(MAL)+V(pb)*Id(MBL)+V(pc)*Id(MCL) FROM 280m TO 300m",
 "!.meas TRAN Efficiency PARAM Pmech/Pin",
]
for i, s in enumerate(D):
    T(32, -520 + 32 * i if i < 12 else 1360 + 28 * (i - 12), s)
T(32, 40, "; BATTERY 4S"); T(352, 40, "; DC-LINK CAPS"); T(880, 40, "; 3-PHASE INVERTER (3 half-bridge legs)")
open("ThreePhase_ESC_BLDC.asc", "w", newline="\r\n").write("\n".join(L) + "\n")

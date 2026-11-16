"""Generates ThreeChannel_Transmission.asc: 3 independent batteries -> 3 cable harnesses -> 3 ESC inputs -> 3 motor loads.
Each ESC + motor is replaced by its exact DC-bus behaviour (switching-function model), so the simulation is about the
electrical transmission: cables, connectors, DC-link capacitors, hot-plug, ripple, load steps and grounding."""
L = []; a = L.append
a("Version 4"); a("SHEET 1 3600 2200")
def W(x1, y1, x2, y2): a(f"WIRE {x1} {y1} {x2} {y2}")
def F(x, y, n): a(f"FLAG {x} {y} {n}")
def S(sym, x, y, rot, inst, val, extra=()):
    a(f"SYMBOL {sym} {x} {y} {rot}"); a(f"SYMATTR InstName {inst}"); a(f"SYMATTR Value {val}")
    for e in extra: a(e)
def T(x, y, s): a(f"TEXT {x} {y} Left 2 {s}")
def BV(x, y, inst, expr, node):          # behavioral voltage to ground: + (x,y+16)  - (x,y+96)
    S("bv", x, y, "R0", inst, "V=" + expr); F(x, y + 16, node); F(x, y + 96, "0")

for k in (1, 2, 3):
    y = (k - 1) * 560; g, bn, bus = f"g{k}", f"bn{k}", f"bus{k}"
    T(32, y + 40, f"; CHANNEL {k}:  battery {k} -> harness {k} -> ESC {k} -> motor {k}")
    # battery (plugged in at Tplug through the connector) + internal resistance
    S("voltage", 64, y + 128, "R0", f"Vbat{k}", f"PWL(0 0 {{Tplug}} 0 {{Tplug+Tcontact}} {{Vb{k}}})"); F(64, y + 224, bn)
    S("res", 96, y + 160, "R270", f"Rint{k}", "{Rbatt}"); W(64, y + 144, 112, y + 144)
    # harness: + and - conductors, each carries half the loop R and L (connector resistance included)
    S("ind", 224, y + 160, "R270", f"Lpos{k}", f"{{Lloop{k}/2}}", [f"SYMATTR SpiceLine Rser={{Rloop{k}/2}}"]); W(192, y + 144, 240, y + 144)
    S("ind", 224, y + 240, "R270", f"Lneg{k}", f"{{Lloop{k}/2}}", [f"SYMATTR SpiceLine Rser={{Rloop{k}/2}}"])
    F(240, y + 224, bn); F(320, y + 224, g)
    # ESC DC link: ceramic always, electrolytic only when Ebulk=1
    S("cap", 400, y + 144, "R0", f"Ccer{k}", "{Ccer}", ["SYMATTR SpiceLine Rser=2m Lser=2n"]); F(416, y + 208, g)
    S("cap", 496, y + 144, "R0", f"Cbulk{k}", "470u", ["SYMATTR SpiceLine Rser={if(Ebulk,30m,1Meg)} Lser=10n"]); F(512, y + 208, g)
    W(320, y + 144, 640, y + 144); F(448, y + 144, bus)
    # inverter input current = sum over legs of (high-side on) x (phase current)
    S("bi", 640, y + 144, "R0", f"B_INV{k}", f"I=V(ibus{k})"); F(640, y + 224, g)
    # signal ground from this ESC to the flight controller (node 0) and the optional battery-negative tie
    S("ind", 704, y + 128, "R0", f"Lsig{k}", "{Lsig}", ["SYMATTR SpiceLine Rser={Rsig}"]); F(720, y + 144, g); F(720, y + 224, "0")
    S("res", 800, y + 128, "R0", f"Rtie{k}", "{if(Tie,1m,1G)}"); F(816, y + 144, bn); F(816, y + 224, "tie")
    # ---- ESC + motor load model (FOC operating point at fixed speed; see topology 03) ----
    x0 = 1024
    S("voltage", x0, y + 128, "R0", f"Viq{k}", f"PWL(0 0 {{Tthr}} 0 {{Tthr+1m}} {{Iq{k}}} {{Tstep}} {{Iq{k}}} {{Tstep+Trise}} {{Iq{k}s}})")
    F(x0, y + 144, f"iq{k}"); F(x0, y + 224, "0")
    BV(x0 + 128, y + 128, f"B_TH{k}", f"2*pi*{{Pp}}*{{RPM{k}}}/60*time", f"th{k}")
    BV(x0 + 256, y + 128, f"B_VQ{k}", f"{{Rph}}*V(iq{k})+{{Kph}}*{{RPM{k}}}*2*pi/60", f"vq{k}")
    BV(x0 + 384, y + 128, f"B_VD{k}", f"-{{Pp}}*{{RPM{k}}}*2*pi/60*{{Lph}}*V(iq{k})", f"vd{k}")
    for j, ph in enumerate("abc"):
        sh = f"-{2*j}*pi/3" if j else ""
        BV(x0 + 512 + 128 * j, y + 128, f"B_I{ph.upper()}{k}", f"-V(iq{k})*sin(V(th{k}){sh})", f"i{ph}{k}")
        BV(x0 + 896 + 128 * j, y + 128, f"B_V{ph.upper()}{k}", f"V(vd{k})*cos(V(th{k}){sh})-V(vq{k})*sin(V(th{k}){sh})", f"v{ph}{k}")
    BV(x0, y + 320, f"B_VOFF{k}", f"(max(max(V(va{k}),V(vb{k})),V(vc{k}))+min(min(V(va{k}),V(vb{k})),V(vc{k})))/2", f"voff{k}")
    S("voltage", x0 + 128, y + 320, "R0", f"Vtri{k}", f"PULSE(0 1 {{Tph{k}}} {{Tsw/2}} {{Tsw/2}} 0 {{Tsw}})"); F(x0 + 128, y + 336, f"tri{k}"); F(x0 + 128, y + 416, "0")
    for j, ph in enumerate("abc"):
        BV(x0 + 256 + 256 * j, y + 320, f"B_D{ph.upper()}{k}", f"limit(0.5+(V(v{ph}{k})-V(voff{k}))/max(V(vbf{k}),1), 0, 1)", f"du{ph}{k}")
        BV(x0 + 384 + 256 * j, y + 320, f"B_H{ph.upper()}{k}", f"(1+tanh(500*(V(du{ph}{k})-V(tri{k}))))/2", f"h{ph}{k}")
    BV(x0 + 1024, y + 320, f"B_IBUS{k}", f"V(ha{k})*V(ia{k})+V(hb{k})*V(ib{k})+V(hc{k})*V(ic{k})", f"ibus{k}")
    # ESC measures its bus voltage through a 3 kHz low-pass (ADC filter + sampling): used for the duty feed-forward
    BV(x0 + 1152, y + 320, f"B_VBS{k}", f"V(bus{k},g{k})", f"vbs{k}")
    S("res", x0 + 1264, y + 320, "R0", f"Rvf{k}", "1k"); F(x0 + 1280, y + 336, f"vbs{k}"); F(x0 + 1280, y + 416, f"vbf{k}")
    S("cap", x0 + 1376, y + 336, "R0", f"Cvf{k}", "{1/(2*pi*1k*Fvf)}"); F(x0 + 1392, y + 336, f"vbf{k}"); F(x0 + 1392, y + 400, "0")
    T(x0, y + 40, f"; ESC {k} + MOTOR {k}: phase currents and voltages of the FOC operating point; bus current = sum(h_x * i_x)")

D = [
 "; === 04  THREE-CHANNEL POWER TRANSMISSION: 3 independent 4S batteries -> 3 harnesses -> 3 ESCs -> 3 motors ===",
 "!.param Rbatt=20m Vb1=15.2 Vb2=15.0 Vb3=14.8          ; three packs at slightly different states of charge",
 "!.param Rloop1=2.66m Lloop1=47n  Rloop2=5.97m Lloop2=140n  Rloop3=10.94m Lloop3=770n   ; 10 cm pair, 30 cm pair, 60 cm separated (14 AWG + XT60)",
 "!.param Ccer=10u Rsig=27m Lsig=200n                      ; ESC ceramic; 20 cm 26 AWG signal ground to the flight controller",
 "!.param Fsw=48k Tsw={1/Fsw} Tph1=0 Tph2=7u Tph3=13u       ; three ESCs with unsynchronised PWM carriers",
 "!.param Pp=7 Rph=50m Lph=7.5u Kph={60/(2*pi*2300)/sqrt(3)}  ; same 2300KV 7-pole-pair motor as 02/03",
 "!.param RPM1=14000 Iq1=7.28  RPM2=20000 Iq2=14.6  RPM3=10000 Iq3=3.80   ; prop load at each speed (k w^2)",
 "!.param Iq1s={Iq1} Iq2s={Iq2} Iq3s=25 Tstep=8m Trise=100u              ; motor 3 punches to 25 A at 8 ms",
 "!.param Tplug=10u Tcontact=100n Tthr=3m Fvf=3k     ; ESC bus-voltage measurement bandwidth",
 "!.step param Case list 0 1 2     ; 0 = ceramic only   1 = + 470 uF electrolytic at each ESC   2 = case 1 + battery negatives tied together",
 "!.param Ebulk={if(Case>=1,1,0)} Tie={if(Case==2,1,0)}",
 "!.tran 0 11m 0",
]
M = ["!.save V(bus1,g1) V(bus2,g2) V(bus3,g3) V(g1) V(g2) V(g3) V(bn1) V(bn2) V(bn3) I(Lpos1) I(Lpos2) I(Lpos3) I(Lneg1) I(Lneg2) I(Lneg3) I(Ccer1) I(Ccer2) I(Ccer3) I(Cbulk1) I(Cbulk2) I(Cbulk3) I(Lsig1) I(Lsig2) I(Lsig3) V(ibus1) V(ibus2) V(ibus3) V(iq3)"]
for k in (1, 2, 3):
    M += [f"!.meas TRAN Vplug_pk{k} MAX V(bus{k},g{k}) FROM 0 TO 2.5m",
          f"!.meas TRAN Iplug_pk{k} MAX I(Lpos{k}) FROM 0 TO 2.5m",
          f"!.meas TRAN Vbus_avg{k} AVG V(bus{k},g{k}) FROM 6m TO 8m",
          f"!.meas TRAN Ibat_avg{k} AVG I(Lpos{k}) FROM 6m TO 8m",
          f"!.meas TRAN Ibat_rms{k} RMS I(Lpos{k}) FROM 6m TO 8m",
          f"!.meas TRAN Iinv_avg{k} AVG V(ibus{k}) FROM 6m TO 8m",
          f"!.meas TRAN Iinv_rms{k} RMS V(ibus{k}) FROM 6m TO 8m",
          f"!.meas TRAN Icer_rms{k} RMS I(Ccer{k}) FROM 6m TO 8m",
          f"!.meas TRAN Ibulk_rms{k} RMS I(Cbulk{k}) FROM 6m TO 8m",
          f"!.meas TRAN Vrip{k} PP V(bus{k},g{k}) FROM 6m TO 8m",
          f"!.meas TRAN Pload{k} AVG V(bus{k},g{k})*V(ibus{k}) FROM 6m TO 8m",
          f"!.meas TRAN Isig_rms{k} RMS I(Lsig{k}) FROM 6m TO 8m"]
M += ["!.meas TRAN Vmin_step3 MIN V(bus3,g3) FROM 8m TO 11m",
      "!.meas TRAN Vbus_after3 AVG V(bus3,g3) FROM 10m TO 11m",
      "!.meas TRAN Ibat_after3 AVG I(Lpos3) FROM 10m TO 11m",
      "!.meas TRAN Vbus1_during AVG V(bus1,g1) FROM 10m TO 11m",
      "!.meas TRAN Isig3_after RMS I(Lsig3) FROM 10m TO 11m",
      "!.meas TRAN Ineg3_after AVG I(Lneg3) FROM 10m TO 11m"]
for i, s in enumerate(D):
    T(32, -460 + 32 * i, s)
for i, s in enumerate(M):
    T(32, 1720 + 26 * i, s)
open("ThreeChannel_Transmission.asc", "w", newline="\r\n").write("\n".join(L) + "\n")

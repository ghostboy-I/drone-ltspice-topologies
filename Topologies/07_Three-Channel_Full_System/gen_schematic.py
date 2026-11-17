"""Generates the two schematics of topology 07, the full 3-battery -> 3-motor system:

  FullSystem_PlugIn.asc  : all three packs plugged in (staggered), protection soft-start, BEC start, ESC arming + spin-up
  FullSystem_Flight.asc  : motors start at speed (.ic), steady flight, throttle punch on motor 3, pack 1 pulled mid-flight

Each channel = 4S pack (04) -> connector -> 14 AWG harness (04) -> back-to-back N-FET protection in the - line (05)
             -> ESC DC link (04) -> switching 3-phase inverter + sensored FOC with SVPWM (03) -> PMSM + prop (03).
The 5 V BEC (06) hangs on channel 1's ESC bus as an averaged (state-space averaged, ideal-loop) model.
All nets are joined by labels (FLAGs) so the generator stays short; the layout is one band per channel."""
import sys

L = []
a = L.append


def F(x, y, n): a(f"FLAG {x} {y} {n}")
def S(sym, x, y, rot, inst, val, extra=()):
    a(f"SYMBOL {sym} {x} {y} {rot}"); a(f"SYMATTR InstName {inst}"); a(f"SYMATTR Value {val}")
    for e in extra: a(e)
def T(x, y, s): a(f"TEXT {x} {y} Left 2 {s}")
PINS = {"res": (16, 16, 16, 96), "ind": (16, 16, 16, 96), "cap": (16, 0, 16, 64), "diode": (16, 0, 16, 64),
        "voltage": (0, 16, 0, 96), "bv": (0, 16, 0, 96), "bi": (0, 0, 0, 80)}
def two(sym, x, y, inst, val, top, bot, extra=()):           # vertical 2-pin part, nets by flags
    S(sym, x, y, "R0", inst, val, extra); p = PINS[sym]
    F(x + p[0], y + p[1], top); F(x + p[2], y + p[3], bot)
def BV(x, y, inst, expr, node, ref="0"): two("bv", x, y, inst, "V=" + expr, node, ref)
def nmos(x, y, inst, model, d, g, s):
    S("nmos", x, y, "R0", inst, model); F(x + 48, y, d); F(x, y + 80, g); F(x + 48, y + 96, s)


def channel(k, Y, wcmd):
    bus, g, ph = f"bus{k}", f"g{k}", ["a", "b", "c"]
    n = lambda s: f"{s}{k}"
    T(32, Y - 40, f"; ===== CHANNEL {k}:  pack {k} -> connector -> harness {k} -> protection FETs -> ESC {k} DC link -> inverter {k} -> motor {k} + prop =====")
    # ---- pack, connector, harness ----
    two("voltage", 64, Y, n("Vbat"), f"{{Vb{k}}}", n("bp"), n("bn"))
    two("res", 176, Y - 16, n("Rint"), "{Rbatt}", n("bp"), n("bt"))
    two("bi", 304, Y, n("B_CONN"),
        f"I=V(bt{k},hp{k})*({{Gon}}*(1+tanh((time-{{Ton{k}}})/{{Tc}}))*(1-tanh((time-{{Toff{k}}})/{{Tc}}))/4+1e-9)", n("bt"), n("hp"))
    two("ind", 416, Y - 16, n("Lpos"), f"{{Lloop{k}/2}}", n("hp"), bus, [f"SYMATTR SpiceLine Rser={{Rloop{k}/2}}"])
    two("ind", 528, Y - 16, n("Lneg"), f"{{Lloop{k}/2}}", n("hn"), n("bn"), [f"SYMATTR SpiceLine Rser={{Rloop{k}/2}}"])
    # ---- protection: back-to-back N-FETs in the - line, Miller soft-start gate network (topology 05) ----
    nmos(672, Y, n("MQ1"), "PROT_FET", n("hn"), n("gt"), n("s"))
    nmos(816, Y, n("MQ2"), "PROT_FET", g, n("gt"), n("s"))
    two("res", 944, Y - 16, n("Rgp"), "{Rgate}", bus, n("gt"))
    two("cap", 1040, Y, n("Cm"), "{Cmiller}", n("gt"), g)
    two("res", 1136, Y - 16, n("Rgs"), "100k", n("gt"), n("s"))
    two("diode", 1232, Y, n("Dz"), "DZ12", n("s"), n("gt"))
    two("cap", 1328, Y, n("Cgsx"), "{Cgsx}", n("gt"), n("s"))
    # ---- ESC DC link ----
    two("cap", 1456, Y, n("Ccer"), "10u", bus, g, ["SYMATTR SpiceLine Rser=2m"])   # no ESL: as in 03, the commutation loop is not modelled
    two("cap", 1552, Y, n("Cbulk"), "470u", bus, g, ["SYMATTR SpiceLine Rser=30m Lser=10n"])
    # signal ground (26 AWG) from this ESC to the flight controller; channel 1's is the BEC ground lead (22 AWG)
    rs, ls = ("{Rbgnd}", "{Lbgnd}") if k == 1 else ("{Rsig}", "{Lsig}")
    two("ind", 1648, Y - 16, n("Lsig"), ls, g, "0", [f"SYMATTR SpiceLine Rser={rs}"])
    T(32, Y + 120, f"; PACK {k}  Rint   CONNECTOR   HARNESS +/-        PROTECTION Q1|Q2 + gate network (05)          DC LINK    SIGNAL GND to FC")
    # ---- inverter: 3 legs, complementary PWM, dead time ----
    for j, p in enumerate(ph):
        x = 1840 + 352 * j; P = p.upper()
        nmos(x, Y - 16, f"M{P}H{k}", "ESC_FET", bus, n(f"gh{p}"), n(f"p{p}"))
        nmos(x, Y + 128, f"M{P}L{k}", "ESC_FET", n(f"p{p}"), n(f"gl{p}"), g)
        two("res", x - 112, Y - 16, f"Rg_{P}H{k}", "{Rg}", n(f"dh{p}"), n(f"gh{p}"))
        two("res", x - 112, Y + 128, f"Rg_{P}L{k}", "{Rg}", n(f"dl{p}"), n(f"gl{p}"))
        BV(x - 208, Y - 16, f"B_G{P}H{k}", f"{{Vdrv}}*V(h{p}{k})", n(f"dh{p}"), n(f"p{p}"))      # floating high-side drive
        BV(x - 208, Y + 128, f"B_G{P}L{k}", f"{{Vdrv}}*V(l{p}{k})", n(f"dl{p}"), g)
    T(1700, Y + 260, f"; INVERTER {k}: 3 legs, 6 x ESC_FET, complementary PWM with dead time, gates driven from the FOC comparators")
    # ---- PMSM: wye, sinusoidal back-EMF ----
    for j, p in enumerate(ph):
        x = 2960 + 320 * j; sh = f"-{2*j}*pi/3" if j else ""
        two("ind", x, Y - 16, f"L{p}{k}", "{Lph}", n(f"p{p}"), n(f"m{p}"))
        two("res", x + 96, Y - 16, f"R{p}{k}", "{Rph}", n(f"m{p}"), n(f"x{p}"))
        BV(x + 192, Y - 16, f"B_E{P_(p)}{k}", f"-{{Kph}}*V(omega{k})*sin(V(the{k}){sh})", n(f"x{p}"), n("n"))
    T(2960, Y + 120, f"; MOTOR {k} (wye): L, R, sinusoidal back-EMF per phase")
    # ---- mechanics ----
    Ym = Y + 320
    ia, ib, ic = f"I(La{k})", f"I(Lb{k})", f"I(Lc{k})"
    BV(64, Ym, n("B_TE"), f"-{{Kph}}*(sin(V(the{k}))*{ia}+sin(V(the{k})-2*pi/3)*{ib}+sin(V(the{k})-4*pi/3)*{ic})", n("te"))
    two("bi", 192, Ym, n("B_Tmot"), f"I=V(te{k})", "0", n("omega"))
    two("cap", 288, Ym, n("C_J"), "{Jrot}", n("omega"), "0")
    two("bi", 384, Ym, n("B_Tprop"), f"I={{Kprop}}*V(omega{k})*abs(V(omega{k}))+{{Bfric}}*V(omega{k})", n("omega"), "0")
    two("res", 480, Ym - 16, n("R_leak"), "100Meg", n("omega"), "0")
    two("bi", 576, Ym, n("B_dth"), f"I=V(omega{k})", "0", n("theta"))
    two("cap", 672, Ym, n("C_th"), "1", n("theta"), "0")
    two("res", 768, Ym - 16, n("R_leak2_"), "1G", n("theta"), "0")
    BV(864, Ym, n("B_THE"), f"{{Pp}}*V(theta{k})", n("the"))
    BV(960, Ym, n("B_RPM"), f"V(omega{k})*60/(2*pi)", n("rpm"))
    BV(1056, Ym, n("B_WE"), f"{{Pp}}*V(omega{k})", n("we"))
    T(32, Ym + 120, f"; MECHANICS {k}: V(te)=torque, V(omega)=rad/s (C_J = inertia), prop k*w^2, V(theta)=rotor angle (ideal encoder)")
    # ---- FOC controller (topology 03), referenced to this ESC's ground for the bus measurement ----
    Yc = Y + 560
    two("voltage", 64, Yc, n("Vwref"), f"PWL({wcmd})", n("wref"), "0")
    BV(192, Yc, n("B_EN"), f"(1+tanh(4*(V(vbf{k})-{{Vuvlo}})))/2*(1+tanh((time-{{Tarm}})/20u))/2", n("en"))
    BV(320, Yc, n("B_IQREF"), f"limit({{Kpw}}*(V(wref{k})-V(omega{k}))+{{Kiw}}*idt(V(wref{k})-V(omega{k}),{{Iq{k}0/Kiw}}),-{{Imax}},{{Imax}})", n("iqref"))
    BV(448, Yc, n("B_IAL"), ia, n("ial"))
    BV(576, Yc, n("B_IBE"), f"({ia}+2*{ib})/sqrt(3)", n("ibe"))
    BV(704, Yc, n("B_ID"), f"V(ial{k})*cos(V(the{k}))+V(ibe{k})*sin(V(the{k}))", n("id"))
    BV(832, Yc, n("B_IQ"), f"-V(ial{k})*sin(V(the{k}))+V(ibe{k})*cos(V(the{k}))", n("iq"))
    BV(960, Yc, n("B_VD"), f"{{Kpi}}*(0-V(id{k}))+{{Kii}}*idt(0-V(id{k})) - V(we{k})*{{Lph}}*V(iq{k})", n("vd"))
    BV(1088, Yc, n("B_VQ"), f"{{Kpi}}*(V(iqref{k})-V(iq{k}))+{{Kii}}*idt(V(iqref{k})-V(iq{k}),{{Rph*Iq{k}0/Kii}}) + V(we{k})*{{Lph}}*V(id{k})+{{Kph}}*V(omega{k})", n("vq"))
    BV(1216, Yc, n("B_VAL"), f"V(vd{k})*cos(V(the{k}))-V(vq{k})*sin(V(the{k}))", n("val"))
    BV(1344, Yc, n("B_VBE"), f"V(vd{k})*sin(V(the{k}))+V(vq{k})*cos(V(the{k}))", n("vbe"))
    BV(1472, Yc, n("B_VA"), f"V(val{k})", n("va"))
    BV(1600, Yc, n("B_VB"), f"-V(val{k})/2+sqrt(3)/2*V(vbe{k})", n("vb"))
    BV(1728, Yc, n("B_VC"), f"-V(val{k})/2-sqrt(3)/2*V(vbe{k})", n("vc"))
    Yd = Yc + 200
    BV(64, Yd, n("B_VOFF"), f"(max(max(V(va{k}),V(vb{k})),V(vc{k}))+min(min(V(va{k}),V(vb{k})),V(vc{k})))/2", n("voff"))
    two("voltage", 192, Yd, n("Vtri"), f"PULSE(0 1 {{Tph{k}}} {{Tsw/2}} {{Tsw/2}} 0 {{Tsw}})", n("tri"), "0")
    for j, p in enumerate(ph):
        x = 320 + 384 * j; P = p.upper()
        BV(x, Yd, f"B_D{P}{k}", f"limit(0.5+(V(v{p}{k})-V(voff{k}))/max(V(vbf{k}),3), 0.01, 0.99)", n(f"du{p}"))
        BV(x + 128, Yd, f"B_H{P}{k}", f"V(en{k})*(1+tanh(500*(V(du{p}{k})-{{dband}}-V(tri{k}))))/2", n(f"h{p}"))
        BV(x + 256, Yd, f"B_L{P}{k}", f"V(en{k})*(1+tanh(500*(V(tri{k})-V(du{p}{k})-{{dband}})))/2", n(f"l{p}"))
    # bus-voltage sense through a 3 kHz low-pass (ADC filter), as in 04: used by the duty feed-forward and the UVLO
    BV(1856, Yc, n("B_VBS"), f"V(bus{k},g{k})", n("vbs"))
    two("res", 1968, Yc - 16, n("Rvf"), "1k", n("vbs"), n("vbf"))
    two("cap", 2064, Yc, n("Cvf"), "{1/(2*pi*1k*Fvf)}", n("vbf"), "0")
    T(32, Yc - 60, f"; FOC {k} (topology 03): speed PI -> iq*, Clarke+Park, d/q current PIs + decoupling, inverse Park/Clarke, SVPWM, comparators.  "
                   f"B_EN{k} = arming x under-voltage lockout ({{Vuvlo}} V)")


def P_(p): return p.upper()


def bec(X, Y):
    """Averaged BEC on channel 1's bus: ideal 5 V source with dropout (Dmax*Vin), input current = Pout/(eta*Vin)."""
    T(X, Y - 40, "; ===== BEC (topology 06), AVERAGED: Vout = ss*min(Vset, Dmax*Vin);  Iin = Vout*Iout/(eta*Vin);  UVLO at {Vbec_uv} V, 0.3 ms soft-start =====")
    two("cap", X, Y, "Cbec_in", "{Cbec_in}", "bus1", "g1", ["SYMATTR SpiceLine Rser=3m Lser=0.5n"])
    two("bi", X + 112, Y, "B_BECIN", "I=V(v5b,g1)*V(v5b,v5)/{Rbo}/({Etabec}*max(V(bus1,g1),2))", "bus1", "g1")
    BV(X + 224, Y, "B_BECEN", "(1+tanh(4*(V(bus1,g1)-{Vbec_uv})))/2", "enb")
    two("res", X + 336, Y - 16, "Rss", "1k", "enb", "ssb")
    two("cap", X + 432, Y, "Css", "{Tss/1k}", "ssb", "0")
    BV(X + 528, Y, "B_BEC", "V(ssb)*min({V5set},{Dmax}*V(bus1,g1))", "v5b", "g1")
    two("res", X + 640, Y - 16, "Rbo", "{Rbo}", "v5b", "v5")
    two("cap", X + 736, Y, "Cout", "40u", "v5", "g1", ["SYMATTR SpiceLine Rser=3m"])
    two("res", X + 832, Y - 16, "R5lead", "{Rbgnd}", "v5", "v5fc")
    two("res", X + 928, Y - 16, "Ravionics", "{V5set/I5}", "v5fc", "0")
    two("cap", X + 1024, Y, "Cfc", "22u", "v5fc", "0", ["SYMATTR SpiceLine Rser=5m"])
    T(X, Y + 130, "; 5 V lead + and - (22 AWG, 20 cm): the - lead is Lsig1.   Avionics (flight controller, receiver, VTX) = 3 A at 5 V, returns to FC ground = node 0")


COMMON = [
 "!.param Rbatt=20m Vb1=15.2 Vb2=15.0 Vb3=14.8           ; packs 1-3 (topology 04)",
 "!.param Rloop1=2.66m Lloop1=47n  Rloop2=5.97m Lloop2=140n  Rloop3=10.94m Lloop3=770n   ; harness loops incl. XT60 (04)",
 "!.param Gon={1/50u} Tc=1u                               ; connector = switch (its resistance is already in Rloop)",
 "!.param Rsig=27m Lsig=200n Rbgnd=10.6m Lbgnd=200n         ; 26 AWG signal ground (ch2, ch3); 22 AWG BEC lead (ch1)",
 "!.param Rgate=12k Cmiller=100n Cgsx=2.2u                 ; protection soft-start (topology 05)",
 "!.param Fsw=48k Tsw={1/Fsw} Tdead=100n dband={Tdead/Tsw} Vdrv=10 Rg=4.7 Tph1=0 Tph2=7u Tph3=13u   ; 3 unsynchronised ESCs",
 "!.param KV=2300 Kph={60/(2*pi*KV)/sqrt(3)} Pp=7 Rph=50m Lph=7.5u Jrot=5u Kprop=1.15e-8 Bfric=1u  ; motor + prop (03)",
 "!.param Fci=3k Kpi={Lph*2*pi*Fci} Kii={Rph*2*pi*Fci} Fcw=30 Kpw={Jrot*2*pi*Fcw/(1.5*Kph)} Kiw={Kpw*2*pi*Fcw/4} Imax=30 Vuvlo=9 Fvf=3k",
 "!.param V5set=4.984 I5=3 Etabec=0.97 Dmax=0.95 Rbo=5m Cbec_in=20u Vbec_uv=6 Tss=0.3m   ; BEC (06), averaged",
 "!.param W1={14000*pi/30} W2={20000*pi/30} W3={10000*pi/30} W3p={16000*pi/30}",
 "!.model ESC_FET VDMOS(Rd=2.5m Rs=0.5m Vto=1.8 Kp=120 Cgdmax=1.2n Cgdmin=150p Cgs=2.2n Cjo=1.5n Is=5p N=1.05 Rb=4m Tt=20n Vds=30 Ron=3m Qg=30n mfg=Learning)",
 "!.model PROT_FET VDMOS(Rd=0.4m Rs=0.2m Vto=2.5 Kp=300 Cgdmax=2n Cgdmin=300p Cgs=6n Cjo=3n Is=10p N=1.05 Rb=2m Vds=40 Ron=1m Qg=80n mfg=Learning)",
 "!.model DZ12 D(Is=1n Rs=5 BV=12 IBV=1m N=1.5)",
]
SAVE_CH = ("V(bus{k}) V(g{k}) V(gt{k}) V(s{k}) V(hn{k}) V(hp{k}) V(bt{k}) V(bn{k}) I(Lpos{k}) I(Lsig{k}) Id(MQ1{k}) Id(MQ2{k}) "
           "V(omega{k}) V(rpm{k}) V(te{k}) V(iq{k}) V(id{k}) V(iqref{k}) V(en{k}) V(vbf{k}) I(La{k}) I(Lb{k}) I(Lc{k}) Id(MAH{k}) Id(MBH{k}) Id(MCH{k})")
SAVE = "!.save " + " ".join(SAVE_CH.format(k=k) for k in (1, 2, 3)) + " V(v5) V(v5fc) V(v5b) I(B_BECIN) V(ssb)"


def meas_ch(k, t0, t1, tag):
    w = f"FROM {t0} TO {t1}"
    return [f"!.meas TRAN Vbus{k}_{tag} AVG V(bus{k},g{k}) {w}",
            f"!.meas TRAN Ibat{k}_{tag} AVG I(Lpos{k}) {w}",
            f"!.meas TRAN rpm{k}_{tag} AVG V(rpm{k}) {w}",
            f"!.meas TRAN Isig{k}_{tag} AVG I(Lsig{k}) {w}"]


def build(mode):
    del L[:]
    a("Version 4"); a("SHEET 1 4200 4600")
    for k in (1, 2, 3):
        if mode == "plugin":
            wcmd = f"0 0 {{Tarm}} 0 {{Tarm+Tramp}} {{W{k}}}"
        else:
            wcmd = "0 {W3} 8m {W3} 8.001m {W3p}" if k == 3 else f"0 {{W{k}}}"
        channel(k, 160 + (k - 1) * 1400, wcmd)
    bec(32, 4400)
    if mode == "plugin":
        D = ["; === 07  FULL SYSTEM, run 1: PLUG-IN of the three packs (staggered), soft-start, BEC start, ESC arming + spin-up ===",
             "!.param Ton1=0.5m Ton2=1.5m Ton3=2.5m Toff1=1 Toff2=1 Toff3=1   ; contacts close at 0.5 / 1.5 / 2.5 ms, never open",
             "!.param Tarm=10m Tramp=120m Iq10=0 Iq20=0 Iq30=0                ; ESCs arm at 10 ms; speed commands ramp over 120 ms (as in 03)",
             "!.tran 0 20m 0",
             "!.options method=gear",
             ] + COMMON + [SAVE]
        M = []
        for k in (1, 2, 3):
            M += [f"!.meas TRAN Ipk{k} MAX I(Lpos{k}) FROM 0 TO {{Tarm}}",
                  f"!.meas TRAN T90_{k} WHEN V(bus{k},g{k})={{0.9*Vb{k}}} RISE=1",
                  f"!.meas TRAN T10_{k} WHEN V(bus{k},g{k})={{0.1*Vb{k}}} RISE=1",
                  f"!.meas TRAN Vrdy{k} AVG V(bus{k},g{k}) FROM 9.5m TO 10m",
                  f"!.meas TRAN Efet{k} INTEG V(g{k},s{k})*Id(MQ2{k})+V(hn{k},s{k})*Id(MQ1{k}) FROM 0 TO {{Tarm}}",
                  f"!.meas TRAN Vgs{k}_arm FIND V(gt{k},s{k}) AT {{Tarm}}",
                  f"!.meas TRAN Vgs{k}_end FIND V(gt{k},s{k}) AT 20m",
                  f"!.meas TRAN rpm{k}_end FIND V(rpm{k}) AT 20m",
                  f"!.meas TRAN Iq{k}_spin AVG V(iq{k}) FROM 15m TO 20m",
                  f"!.meas TRAN Ibat{k}_spin AVG I(Lpos{k}) FROM 18m TO 20m",
                  f"!.meas TRAN Isig{k}_pk MAX abs(I(Lsig{k})) FROM 0 TO 20m"]
        M += ["!.meas TRAN T5v WHEN V(v5fc)=4.5 RISE=1",
              "!.meas TRAN V5_rdy AVG V(v5fc) FROM 9.5m TO 10m",
              "!.meas TRAN Ibec_rdy AVG I(B_BECIN) FROM 9.5m TO 10m",
              "!.meas TRAN Isig1_rdy AVG I(Lsig1) FROM 9.5m TO 10m",
              "!.meas TRAN Vbus1_min_arm MIN V(bus1,g1) FROM {Tarm} TO 20m"]
        name = "FullSystem_PlugIn.asc"
    else:
        D = ["; === 07  FULL SYSTEM, run 2: IN FLIGHT. Motors start at speed (.ic), steady 4-8 ms, motor 3 punch at 8 ms, pack 1 pulled at 16 ms ===",
             "!.param Ton1=-1m Ton2=-1m Ton3=-1m Toff1=16m Toff2=1 Toff3=1      ; pack 1 disconnects at 16 ms",
             "!.param Tarm=-1m Iq10=7.28 Iq20=14.6 Iq30=3.80                  ; integrators pre-loaded with the hand-calculated iq (03/04)",
             "; speed commands: 14,000 / 20,000 / 10,000 RPM; throttle punch: motor 3 -> 16,000 RPM at 8 ms (current-limited at Imax)",
             "!.ic V(omega1)={W1} V(omega2)={W2} V(omega3)={W3} V(theta1)=0 V(theta2)=0 V(theta3)=0",
             "!.ic I(La1)=0 I(Lb1)={0.866*Iq10} I(Lc1)={-0.866*Iq10} I(La2)=0 I(Lb2)={0.866*Iq20} I(Lc2)={-0.866*Iq20} I(La3)=0 I(Lb3)={0.866*Iq30} I(Lc3)={-0.866*Iq30}",
             "!.tran 0 24m 0",
             "!.options method=gear",
             ] + COMMON + [SAVE]
        M = []
        for k in (1, 2, 3):
            w = "FROM 4m TO 8m"
            M += meas_ch(k, "4m", "8m", "ss") + [
                  f"!.meas TRAN Ibrms{k}_ss RMS I(Lpos{k}) {w}",
                  f"!.meas TRAN Iq{k}_ss AVG V(iq{k}) {w}",
                  f"!.meas TRAN Vrip{k}_ss PP V(bus{k},g{k}) {w}",
                  f"!.meas TRAN Vbt{k}_ss AVG V(bt{k},bn{k}) {w}",
                  f"!.meas TRAN Vharn{k}_ss AVG V(hp{k},bus{k})+V(hn{k},bn{k}) {w}",
                  f"!.meas TRAN Pprot{k}_ss AVG V(g{k},s{k})*Id(MQ2{k})+V(hn{k},s{k})*Id(MQ1{k}) {w}",
                  f"!.meas TRAN Vgs{k}_ss AVG V(gt{k},s{k}) {w}",
                  f"!.meas TRAN Pbatt{k}_ss AVG V(bt{k},bn{k})*I(Lpos{k}) {w}",
                  f"!.meas TRAN Pinv{k}_ss AVG V(bus{k},g{k})*(Id(MAH{k})+Id(MBH{k})+Id(MCH{k})) {w}",
                  f"!.meas TRAN Pcu{k}_ss AVG {{Rph}}*(I(La{k})**2+I(Lb{k})**2+I(Lc{k})**2) {w}",
                  f"!.meas TRAN Pmech{k}_ss AVG V(te{k})*V(omega{k}) {w}",
                  f"!.meas TRAN Isigrms{k}_ss RMS I(Lsig{k}) {w}"]
            M += meas_ch(k, "13m", "16m", "pu") + meas_ch(k, "21m", "24m", "dc")
            M += [f"!.meas TRAN Vbusmin{k}_pu MIN V(bus{k},g{k}) FROM 8m TO 16m",
                  f"!.meas TRAN Vbusmax{k}_pu MAX V(bus{k},g{k}) FROM 8m TO 16m"]
        M += ["!.meas TRAN V5_ss AVG V(v5fc) {w}".format(w="FROM 4m TO 8m"),
              "!.meas TRAN V5esc_ss AVG V(v5,g1) FROM 4m TO 8m",
              "!.meas TRAN Pbec_ss AVG V(bus1,g1)*I(B_BECIN) FROM 4m TO 8m",
              "!.meas TRAN P5_ss AVG V(v5fc)**2/{V5set/I5} FROM 4m TO 8m",
              "!.meas TRAN V5_pu MIN V(v5fc) FROM 8m TO 16m",
              "!.meas TRAN Iq3_pu AVG V(iq3) FROM 10m TO 16m",
              "!.meas TRAN w3_a FIND V(omega3) AT 10m",
              "!.meas TRAN w3_b FIND V(omega3) AT 15m",
              "!.meas TRAN Ibat3_15 AVG I(Lpos3) FROM 14.5m TO 15.5m",
              "!.meas TRAN Pinv3_15 AVG V(bus3,g3)*(Id(MAH3)+Id(MBH3)+Id(MCH3)) FROM 14.5m TO 15.5m",
              "!.meas TRAN Vbus3_15 AVG V(bus3,g3) FROM 14.5m TO 15.5m",
              "!.meas TRAN T_uvlo1 WHEN V(bus1,g1)={Vuvlo} FALL=1",
              "!.meas TRAN T_v5_45 WHEN V(v5fc)=4.5 FALL=1",
              "!.meas TRAN T_bec_uv WHEN V(bus1,g1)={Vbec_uv} FALL=1",
              "!.meas TRAN Vbus1_floor AVG V(bus1,g1) FROM 22m TO 24m",
              "!.meas TRAN V5_end AVG V(v5fc) FROM 22m TO 24m",
              "!.meas TRAN w3_c FIND V(omega3) AT 18m",
              "!.meas TRAN w3_d FIND V(omega3) AT 23m",
              "!.meas TRAN Isig2_max MAX abs(I(Lsig2)) FROM 0 TO 24m",
              "!.meas TRAN Isig3_max MAX abs(I(Lsig3)) FROM 0 TO 24m"]
        name = "FullSystem_Flight.asc"
    for i, s in enumerate(D):
        T(32, -1300 + 32 * i, s)
    for i, s in enumerate(M):
        T(4400, -1300 + 26 * i, s)
    open(name, "w", newline="\r\n").write("\n".join(L) + "\n")
    print("wrote", name)


if __name__ == "__main__":
    for m in (sys.argv[1:] or ["plugin", "flight"]):
        build(m)

"""Generates Redundant_Avionics.asc: three floating 4S packs -> three harnesses -> three ESC buses (topology 04), each ESC bus
tapped by an 18 AWG pair to an avionics power board that OR's the three channels into one 5 V rail.

.step param Case list 0 1 2 3 4   (see hand_calc.py for the five architectures)
Timeline: 0-3 ms start-up and normal sharing | 3-4 ms ESC 1 punch (365 W) | 5 ms pack 1 unplugged | 6 ms bus 2 shorted.
Every component value comes from hand_calc.py."""
import hand_calc as h

L = []; a = L.append
a("Version 4"); a("SHEET 1 4200 3000")
PINS = {"res": (16, 16, 16, 96), "ind": (16, 16, 16, 96), "cap": (16, 0, 16, 64), "voltage": (0, 16, 0, 96),
        "bv": (0, 16, 0, 96), "bi": (0, 0, 0, 80), "diode": (16, 0, 16, 64)}
def F(x, y, n): a(f"FLAG {x} {y} {n}")
def S(sym, x, y, inst, val, extra=()):
    a(f"SYMBOL {sym} {x} {y} R0"); a(f"SYMATTR InstName {inst}"); a(f"SYMATTR Value {val}")
    for e in extra: a(e)
def T(x, y, s): a(f"TEXT {x} {y} Left 2 {s}")
def two(sym, x, y, inst, val, top, bot, extra=()):
    S(sym, x, y, inst, val, extra); p = PINS[sym]; F(x + p[0], y + p[1], top); F(x + p[2], y + p[3], bot)
def nmos(x, y, inst, d, g, s, model="ORFET"):
    S("nmos", x, y, inst, model); F(x + 48, y, d); F(x, y + 80, g); F(x + 48, y + 96, s)
def switch(x, y, inst, model, A, B, cp, cn):
    S("sw", x, y, inst, model); F(x, y + 16, A); F(x, y + 96, B); F(x - 48, y + 80, cp); F(x - 48, y + 32, cn)

def ideal_diode(x, y, tag, A, K, on):
    """LM74700-style ideal diode: N-FET (source = anode A, drain = cathode K) + behavioural controller.
    Sense V_AK through a first-order lag (comparator response). Gate current: gm*(V_AK - Vreg) limited to +-Ichg
    (an integrator on the gate capacitance: regulates V_AK to Vreg), clamped at 11 V / 0 V, plus a 2.4 A pull-down
    once V_AK < Vrev (fast reverse turn-off). 'on' = 1 enables the controller (else the gate rests at 0 via Rgs)."""
    g, sr, sn = f"g{tag}", f"sr{tag}", f"s{tag}"
    nmos(x, y, f"M{tag}", K, g, A)
    two("res", x + 96, y, f"Rgs{tag}", "10Meg", g, A)
    two("bv", x + 192, y, f"B_SEN{tag}", f"V=V({A})-V({K})", sr, "0")
    two("res", x + 288, y, f"Rsn{tag}", "1k", sr, sn)
    two("cap", x + 384, y + 16, f"Csn{tag}", "{Tsense/1k}", sn, "0")
    x_ = f"limit((V({sn})-{{Vreg}})/{{Vlin}},-1,1)"
    vgs = f"V({g},{A})"
    hi = f"(1-tanh(({vgs}-11)/0.3))/2"; lo = f"(1+tanh(({vgs}-0.3)/0.05))/2"
    expr = (f"I={{Ichg}}*V(enid)*{on}*(max({x_},0)*{hi}+min({x_},0)*{lo})"
            f"-{{Ipd}}*{on}*(1-tanh((V({sn})-{{Vrev}})/1m))/2*{lo}")
    two("bi", x + 480, y + 16, f"B_G{tag}", expr, A, g)     # current flows A -> source -> g: into the gate

# ---------------- three channels ----------------
for k in (1, 2, 3):
    y = (k - 1) * 720
    bp = "bp1" if k != 1 else "bpi1"
    T(32, y - 40, f"; CHANNEL {k}: pack {k} (floating) -> harness {k} -> ESC {k} bus -> 18 AWG tap pair to the avionics power board")
    two("voltage", 64, y, f"Vbat{k}", f"{{Vb{k}}}", f"bp0{k}", f"bn{k}")
    two("res", 160, y, f"Rint{k}", "{Rbatt}", f"bp0{k}", bp if k == 1 else f"bp{k}")
    if k == 1:   # pack 1 unplugged at Tunp (connector opens over 20 us)
        switch(304, y, "S_UNP", "SWU", "bpi1", "bp1", "cunp", "0")
        two("voltage", 352, y + 160, "Vcunp", "PWL(0 1 {Tunp} 1 {Tunp+20u} 0)", "cunp", "0")
    two("ind", 400, y, f"Lpos{k}", f"{{Lh{k}/2}}", f"bp{k}", f"bus{k}", [f"SYMATTR SpiceLine Rser={{Rh{k}/2}}"])
    two("ind", 400, y + 160, f"Lneg{k}", f"{{Lh{k}/2}}", f"g{k}", f"bn{k}", [f"SYMATTR SpiceLine Rser={{Rh{k}/2}}"])
    # ESC DC link and ESC + motor as a constant-power load with UVLO at 9 V
    two("cap", 512, y, f"Ccer{k}", "{Ccer}", f"bus{k}", f"g{k}", ["SYMATTR SpiceLine Rser=2m Lser=2n"])
    two("cap", 608, y, f"Cbulk{k}", "{Cbulk}", f"bus{k}", f"g{k}", ["SYMATTR SpiceLine Rser=30m Lser=10n"])
    # the ESC regulates power from a filtered bus measurement (04: 3 kHz ADC filter); an instantaneous P/V load would be a
    # negative resistance at every frequency and oscillates against the capacitors' ESL (it did, in the first run)
    pk = "V(p1)" if k == 1 else f"{{Pesc{k}}}"
    two("bi", 704, y, f"B_ESC{k}", f"I={pk}/max(V(vbf{k}),6)*V(enesc)*(1+tanh((V(vbf{k})-9)/0.3))/2", f"bus{k}", f"g{k}")
    two("bv", 704, y + 160, f"B_VB{k}", f"V=V(bus{k},g{k})", f"vbs{k}", "0")
    two("res", 800, y + 320, f"Rvf{k}", "1k", f"vbs{k}", f"vbf{k}"); two("cap", 896, y + 336, f"Cvf{k}", "{1/(2*pi*1k*Fvf)}", f"vbf{k}", "0")
    if k == 1:
        two("voltage", 800, y, "Vp1", "PWL(0 {Pesc1} {Tp} {Pesc1} {Tp+100u} {P1p} {Tp+1m} {P1p} {Tp+1.1m} {Pesc1})", "p1", "0")
    if k == 2:   # bus 2 shorted (failed ESC FET / crushed lead) at Tsh, closing in 50 ns
        switch(928, y, "S_SH", "SWSH", "bus2", "g2", "csh", "0")
        two("voltage", 896, y + 160, "Vcsh", "PWL(0 0 {Tsh} 0 {Tsh+50n} 1)", "csh", "0")
    # signal ground: ESC ground -> flight-controller ground (node 0 = FC / BEC / avionics ground)
    two("ind", 1024, y, f"Lsig{k}", "{Lsig}", f"g{k}", "0", ["SYMATTR SpiceLine Rser={Rsig}"])
    # + tap and its ideal diode (anode a_k, cathode = BEC input vin); Schottky alternative in Case 3
    two("ind", 1120, y, f"Ltp{k}", "{Ltap}", f"bus{k}", f"a{k}", ["SYMATTR SpiceLine Rser={Rtap}"])
    ideal_diode(1248, y, f"P{k}", f"a{k}", "vin", "{OnP}")
    two("res", 1856, y, f"Rsch{k}", "{if(Case==3,1u,1G)}", f"a{k}", f"as{k}")
    two("diode", 1856, y + 160, f"DS{k}", "SCH", f"as{k}", "vin")
    # return (-) path: 0 --[ideal diode | bypass]-- r_k --18 AWG-- rr_k --[select]-- g_k
    ideal_diode(1248, y + 240, f"N{k}", "0", f"r{k}", "{OnN}")
    two("res", 1952, y + 240, f"Rbyp{k}", "{if(Case==1,1G,1u)}", "0", f"r{k}")
    two("ind", 2048, y + 240, f"Lrt{k}", "{Lret}", f"r{k}", f"rr{k}", ["SYMATTR SpiceLine Rser={Rret}"])
    two("res", 2144, y + 240, f"Rrsel{k}", "{if(Case>=1&Case<=3,1u,1G)}", f"rr{k}", f"g{k}")
    # ---- Case 4: isolated DC-DC module k (input across its own tap pair, output referenced to the FC ground) ----
    T(2304, y - 40, f"; isolated module {k} (Case 4 only): input from tap {k}, output OR'ed onto the 5 V rail")
    two("ind", 2304, y, f"Lmi{k}", "{Lret}", f"g{k}", f"mi{k}", ["SYMATTR SpiceLine Rser={Rret}"])
    two("res", 2400, y, f"Rmsel{k}", "{if(Iso,1u,1Meg)}", f"mi{k}", f"mn{k}")
    two("cap", 2496, y, f"Cmi{k}", "10u", f"a{k}", f"mn{k}", ["SYMATTR SpiceLine Rser=5m"])
    two("bi", 2592, y, f"B_MI{k}", f"I={{Iso}}*V(mo{k})*I(Leq{k})/{{Eta}}/max(V(mvf{k}),6)", f"a{k}", f"mn{k}")
    two("bv", 2592, y + 160, f"B_MV{k}", f"V=V(a{k},mn{k})", f"mvs{k}", "0")   # module input sense, 50 kHz (its own loop)
    two("res", 2688, y + 320, f"Rmv{k}", "1k", f"mvs{k}", f"mvf{k}"); two("cap", 2784, y + 336, f"Cmv{k}", "{1/(2*pi*1k*50k)}", f"mvf{k}", "0")
    two("bv", 2688, y, f"B_EM{k}", f"V={{Iso}}*V(enmod)*(1+tanh((V(mvf{k})-9)/0.3))/2", f"em{k}", "0")
    two("bv", 2784, y, f"B_VS{k}", f"V={{Vset{k}}}*V(em{k})", f"vs{k}", "0")
    two("ind", 2880, y, f"Leq{k}", "{Leq}", f"vs{k}", f"mo{k}", ["SYMATTR SpiceLine Rser={Rdroop}"])
    two("cap", 2976, y, f"Cmo{k}", "{Cmo}", f"mo{k}", "0", ["SYMATTR SpiceLine Rser={ESRmo}"])
    ideal_diode(3104, y, f"O{k}", f"mo{k}", "out", "{Iso}")

# ---------------- BEC (06) averaged model, fed from vin ----------------
y0 = 2200
T(32, y0 - 40, "; BEC (topology 06) AVERAGED: <v_sw> = d*Vin, <i_in> = d*iL + switching/conduction loss; Type III + filtered input feed-forward")
two("cap", 64, y0, "Cin", "{Cin}", "vin", "0", ["SYMATTR SpiceLine Rser=3m Lser=0.5n"])
two("bi", 160, y0, "B_IIN", "I=(1-{Iso})*(V(d)*I(L1)+{Pfet}*limit(V(out)/4,0,1)/max(V(vin),5))", "vin", "0")
two("bv", 256, y0, "B_SW", "V=V(d)*V(vin)", "sw", "0")
two("res", 352, y0, "Rbsel", "{if(Iso,1G,1u)}", "sw", "swl")
two("ind", 448, y0, "L1", "{Lout}", "swl", "out", ["SYMATTR SpiceLine Rser={DCR}"])
two("cap", 544, y0, "Cout", "{Cout}", "out", "0", ["SYMATTR SpiceLine Rser={ESR} Lser=0.3n"])
two("bi", 640, y0, "B_LOAD", "I={Iload}*limit(V(out)/4,0,1)", "out", "0")
two("res", 736, y0, "Rff", "1k", "vin", "vinf"); two("cap", 832, y0, "Cff", "{1/(2*pi*1k*Fff)}", "vinf", "0")
two("bv", 928, y0, "B_D", "V=limit(V(comp)/(max(V(vinf),1)/{KFF}),0,{Dmax})", "d", "0")
two("res", 1024, y0, "Rtop", "{Rtop}", "out", "fb")
two("res", 1120, y0, "R3", "{R3}", "out", "n3"); two("cap", 1120, y0 + 144, "C3", "{C3}", "n3", "fb")
two("res", 1216, y0, "Rbot", "{Rbot}", "fb", "0")
two("res", 1312, y0, "R2", "{R2}", "fb", "n2"); two("cap", 1312, y0 + 144, "C1", "{C1}", "n2", "comp")
two("cap", 1408, y0, "C2", "{C2}", "fb", "comp")
two("voltage", 1504, y0, "Vref", "PWL(0 0 {Tss0} 0 {Tss0+Tss} {Vref})", "ref", "0")
two("bi", 1600, y0, "B_GM", "I={gm}*(V(ref)-V(fb))", "0", "ea")
two("res", 1696, y0, "Rea", "{A0/gm}", "ea", "0"); two("cap", 1792, y0, "Cea", "{gm/(2*pi*GBW)}", "ea", "0")
two("bv", 1888, y0, "B_EAOUT", "V=limit(V(ea),0.02,4)", "comp", "0")
# enables (real controllers hold everything off at t = 0)
two("bv", 2048, y0, "B_ENID", "V=(1+tanh((time-50u)/10u))/2", "enid", "0")
two("bv", 2144, y0, "B_ENESC", "V=(1+tanh((time-0.5m)/0.1m))/2", "enesc", "0")
two("bv", 2240, y0, "B_ENMOD", "V=(1+tanh((time-0.4m)/0.1m))/2", "enmod", "0")

R2, C1, C2, R3, C3 = h.h06.PARTS
D = [
 "; === 08  REDUNDANT AVIONICS POWER: one 5 V rail from three floating packs, without ground loops or back-feed ===",
 f"!.param Vb1={h.VB[0]} Vb2={h.VB[1]} Vb3={h.VB[2]} Rbatt={h.Rbatt}",
 f"!.param Rh1={h.RH[0]:.5g} Lh1={h.LH[0]:.4g} Rh2={h.RH[1]:.5g} Lh2={h.LH[1]:.4g} Rh3={h.RH[2]:.5g} Lh3={h.LH[2]:.4g}   ; harness loops (04)",
 f"!.param Ccer=10u Cbulk=470u Rsig={h.Rsig} Lsig={h.Lsig} Fvf=3k   ; Fvf: ESC bus-measurement bandwidth (04)",
 f"!.param Pesc1={h.PESC[0]:.4g} Pesc2={h.PESC[1]:.4g} Pesc3={h.PESC[2]:.4g} P1p={h.P1_PUNCH} Tp=3m Tunp=5m Tsh=6m   ; ESC loads (04 operating points), events",
 f"!.param Rtap={h.Rtap:.4g} Ltap={h.Ltap:.4g} Rret={h.Rret:.4g} Lret={h.Lret:.4g}   ; 15 cm 18 AWG pairs to the power board",
 f"!.param Vreg={h.Vreg} Vrev={h.Vrev} Ichg={h.Ichg} Ipd={h.Ipd} Vlin={h.Vlin} Tsense={h.Tsense}   ; ideal-diode controller (LM74700-style)",
 f"!.param Lout={h.h06.L} DCR={h.h06.DCR} Cout={h.h06.C:.4g} ESR={h.h06.ESR:.4g} Cin={h.Cin} KFF={h.h06.KFF} Dmax=0.9 Fff=100k Pfet={h.P_FET} Iload={h.Iload}",
 f"!.param Vref={h.h06.Vref} Rtop={h.h06.Rtop:.4g} Rbot={h.h06.Rbot:.4g} R2={R2:.4g} C1={C1:.4g} C2={C2:.4g} R3={R3:.4g} C3={C3:.4g} gm=1m A0=10k GBW=10Meg Tss0=0.1m Tss=0.5m",
 f"!.param Vset1={h.VSET[0]} Vset2={h.VSET[1]} Vset3={h.VSET[2]} Rdroop={h.Rdroop} Leq={h.Leq} Cmo={h.Cmo} ESRmo={h.ESRmo} Eta={h.ETA_ISO}   ; isolated modules",
 "!.step param Case list 0 1 2 3 4   ; 0 +OR only | 1 +/- OR | 2 +OR + star return | 3 Schottky + star | 4 isolated DC-DC per pack",
 "!.param OnP={if(Case<=2,1,0)} OnN={if(Case==1,1,0)} Iso={if(Case==4,1,0)}",
 f"!.model ORFET VDMOS(Rd={h.FET['Rd']} Rs={h.FET['Rs']} Vto={h.FET['Vto']} Kp={h.FET['Kp']} Cgdmax=1n Cgdmin=150p Cgs={h.FET['Cgs']} Cjo=1n Is=10p N=1.05 Rb=3m BV={h.FET['BV']} IBV=1m Vds=40 Ron=2.7m Qg=30n mfg=Learning)",
 f"!.model SCH D(Is={h.SCH['Is']} N={h.SCH['N']} Rs={h.SCH['Rs']} Cjo={h.SCH['Cjo']} BV={h.SCH['BV']} IBV=100u)",
 "!.model SWU SW(Ron=10u Roff=100Meg Vt=0.5 Vh=-0.4)",
 "!.model SWSH SW(Ron=5m Roff=100Meg Vt=0.5 Vh=-0.4)",
 "!.tran 0 7m 0",
 "!.options method=gear   ; trapezoidal stalls in the ~20 MHz ring after diode 2 avalanches (1.1 GB, no finish); Gear damps real ringing a little",
]
sv = ["V(vin)", "V(out)", "V(d)"] + [f"V(bus{k})" for k in (1, 2, 3)] + [f"V(g{k})" for k in (1, 2, 3)] + [f"V(a{k})" for k in (1, 2, 3)]
sv += [f"I(Ltp{k})" for k in (1, 2, 3)] + [f"I(Lsig{k})" for k in (1, 2, 3)] + [f"I(Lrt{k})" for k in (1, 2, 3)] + [f"I(Lpos{k})" for k in (1, 2, 3)]
sv += [f"V(gP{k})" for k in (1, 2, 3)] + [f"I(Leq{k})" for k in (1, 2, 3)] + [f"V(mo{k})" for k in (1, 2, 3)] + ["V(r1)"]
M = ["!.save " + " ".join(sv)]
W = {"n": ("2.4m", "2.9m"), "p": ("3.5m", "3.95m"), "a": ("6.6m", "6.95m")}
for w, (t1, t2) in W.items():
    for k in (1, 2, 3):
        M += [f"!.meas TRAN Itap{k}_{w} AVG I(Ltp{k}) FROM {t1} TO {t2}",
              f"!.meas TRAN Isig{k}_{w} AVG -I(Lsig{k}) FROM {t1} TO {t2}",
              f"!.meas TRAN Iret{k}_{w} AVG I(Lrt{k}) FROM {t1} TO {t2}",
              f"!.meas TRAN Imod{k}_{w} AVG I(Leq{k}) FROM {t1} TO {t2}",
              f"!.meas TRAN Vbus{k}_{w} AVG V(bus{k},g{k}) FROM {t1} TO {t2}"]
    M += [f"!.meas TRAN Vin_{w} AVG V(vin) FROM {t1} TO {t2}",
          f"!.meas TRAN Vout_{w} AVG V(out) FROM {t1} TO {t2}",
          f"!.meas TRAN Pav_{w} AVG V(bus1,g1)*I(Ltp1)+V(bus2,g2)*I(Ltp2)+V(bus3,g3)*I(Ltp3) FROM {t1} TO {t2}",
          f"!.meas TRAN Pld_{w} AVG V(out)*{{Iload}}*limit(V(out)/4,0,1) FROM {t1} TO {t2}"]
M += ["!.meas TRAN Vak1_n AVG V(a1)-V(vin) FROM 2.4m TO 2.9m",
      "!.meas TRAN Pd1_n AVG (V(a1)-V(vin))*I(Ltp1) FROM 2.4m TO 2.9m",
      "!.meas TRAN Vakn1_n AVG -V(r1) FROM 2.4m TO 2.9m",
      "!.meas TRAN t_hand WHEN I(Ltp2)+I(Ltp3)=0.52 TD=5m RISE=1",
      "!.meas TRAN Itap1_rev MIN I(Ltp1) FROM 5.1m TO 5.95m",
      "!.meas TRAN Vbus1_end AVG V(bus1,g1) FROM 5.9m TO 5.95m",
      "!.meas TRAN Vin_unp_min MIN V(vin) FROM 5m TO 5.95m",
      "!.meas TRAN Vout_unp_min MIN V(out) FROM 5m TO 5.95m",
      "!.meas TRAN Irev2_pk MIN I(Ltp2) FROM 6m TO 6.05m",
      "!.meas TRAN Isig2_sh MAX I(Lsig2) FROM 6m TO 6.05m",
      "!.meas TRAN t_off WHEN V(gP2)-V(a2)=1 TD=6m FALL=1",
      "!.meas TRAN Vds2_pk MAX V(vin)-V(a2) FROM 6m TO 6.05m",
      "!.meas TRAN Vin_sh_min MIN V(vin) FROM 6m TO 6.1m",
      "!.meas TRAN Vout_sh_min MIN V(out) FROM 6m TO 6.6m",
      "!.meas TRAN Vout_sh_max MAX V(out) FROM 6m TO 6.6m",
      "!.meas TRAN Itap2_after AVG I(Ltp2) FROM 6.6m TO 6.95m",
      "!.meas TRAN Vout_min_all MIN V(out) FROM 1.5m TO 7m",
      "!.meas TRAN Vout_max_all MAX V(out) FROM 1.5m TO 7m"]
for i, s in enumerate(D):
    T(32, -720 + 32 * i, s)
for i, s in enumerate(M):
    T(32, 2560 + 26 * i, s)
open("Redundant_Avionics.asc", "w", newline="\r\n").write("\n".join(L) + "\n")

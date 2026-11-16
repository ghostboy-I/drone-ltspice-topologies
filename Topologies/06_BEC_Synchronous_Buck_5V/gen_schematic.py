"""Generates BEC_Buck.asc (switching transient model) and BEC_Buck_AC.asc (averaged model for loop gain).
Both share the same power stage values and Type-III compensation network (see hand_calc.py)."""
import hand_calc as h
R2, C1, C2, R3, C3 = h.PARTS

def build(fname, averaged):
    L = []; a = L.append
    a("Version 4"); a("SHEET 1 2400 1400")
    def F(x, y, n): a(f"FLAG {x} {y} {n}")
    def S(sym, x, y, rot, inst, val, extra=()):
        a(f"SYMBOL {sym} {x} {y} {rot}"); a(f"SYMATTR InstName {inst}"); a(f"SYMATTR Value {val}")
        for e in extra: a(e)
    def T(x, y, s): a(f"TEXT {x} {y} Left 2 {s}")
    PINS = {"res": (16, 16, 16, 96), "ind": (16, 16, 16, 96), "cap": (16, 0, 16, 64), "voltage": (0, 16, 0, 96), "bv": (0, 16, 0, 96), "bi": (0, 0, 0, 80)}
    def two(sym, x, y, inst, val, top, bot, extra=()):
        S(sym, x, y, "R0", inst, val, extra); p = PINS[sym]; F(x + p[0], y + p[1], top); F(x + p[2], y + p[3], bot)

    # ---- input (the ESC bus of one channel) ----
    if averaged:
        two("voltage", 64, 96, "Vin", "{Vin}", "in", "0")
    else:
        two("voltage", 64, 96, "Vin", "PWL(0 {Vin} {Tsag} {Vin} {Tsag+50u} {Vin-Vsag})", "vdc", "0")
        two("bv", 64, 288, "B_RIP", "V=V(vdc)+{Vrip}/2*sin(2*pi*{Fesc}*time)*(time>{Trip})", "vbus", "0")
        two("ind", 176, 80, "Lin", "30n", "vbus", "in", ["SYMATTR SpiceLine Rser=5m"])
    two("cap", 288, 96, "Cin", "{Cin}", "in", "0", ["SYMATTR SpiceLine Rser=3m Lser=0.5n"])
    # ---- power stage ----
    if averaged:
        two("bv", 400, 80, "B_SWAVG", "V=V(d)*V(in)", "sw", "0")              # averaged switch: <v_sw> = d * Vin
        two("bi", 512, 96, "B_IIN", "I=V(d)*I(L1)", "in", "0")              # averaged input current: d * iL
        two("bv", 400, 288, "B_D", "V=V(comp)/(V(in)/{KFF})", "d", "0")
    else:
        S("nmos", 400, 96, "R0", "MH", "BUCK_FET"); F(448, 96, "in"); F(400, 176, "gh"); F(448, 192, "sw")
        S("nmos", 400, 192, "R0", "ML", "BUCK_FET"); F(448, 192, "sw"); F(400, 272, "gl"); F(448, 288, "0")
        two("bv", 320, 288, "B_GH", "V={Vdrv}*V(hs)", "ghd", "sw"); two("res", 240, 288, "RgH", "{RgH}", "ghd", "gh")
        two("bv", 320, 448, "B_GL", "V={Vdrv}*V(ls)", "gld", "0"); two("res", 240, 448, "RgL", "{RgL}", "gld", "gl")
    two("ind", 624, 80, "L1", "{Lout}", "sw", "out", ["SYMATTR SpiceLine Rser={DCR}"])
    two("cap", 752, 96, "Cout", "{Cout}", "out", "0", ["SYMATTR SpiceLine Rser={ESR} Lser=0.3n"])
    if averaged:
        two("res", 864, 80, "Rload", "{Rl}", "out", "0")
    else:
        two("bi", 864, 96, "B_LOAD", "I=V(iload)*limit(V(out)/4,0,1)", "out", "0")
        two("voltage", 976, 96, "Viload", "PWL(0 {Ilo} {Tst1} {Ilo} {Tst1+1u} {Ihi} {Tst2} {Ihi} {Tst2+1u} {Ilo} {Tst3} {Ilo} {Tst3+1u} {Ihi})", "iload", "0")
    # ---- feedback, Type-III network, error amplifier ----
    top = "x" if averaged else "out"
    if averaged:
        two("voltage", 1088, 96, "Vinj", "0 AC 1", "x", "out")             # loop-gain injection: T = -V(out)/V(x)
    two("res", 1200, 80, "Rtop", "{Rtop}", top, "fb")
    two("res", 1296, 80, "R3", "{R3}", top, "n3"); two("cap", 1296, 224, "C3", "{C3}", "n3", "fb")
    two("res", 1408, 80, "Rbot", "{Rbot}", "fb", "0")
    two("res", 1504, 80, "R2", "{R2}", "fb", "n2"); two("cap", 1504, 224, "C1", "{C1}", "n2", "comp")
    two("cap", 1616, 96, "C2", "{C2}", "fb", "comp")
    two("voltage", 1728, 96, "Vref", "{Vref}" if averaged else "PWL(0 0 {Tss} {Vref})", "ref", "0")
    two("bi", 1840, 96, "B_GM", "I={gm}*(V(ref)-V(fb))", "0", "ea")       # transconductance stage -> ea
    two("res", 1952, 80, "Rea", "{A0/gm}", "ea", "0"); two("cap", 2064, 96, "Cea", "{gm/(2*pi*GBW)}", "ea", "0")
    two("bv", 2176, 80, "B_EAOUT", "V=limit(V(ea),0.02,4)" if not averaged else "V=V(ea)", "comp", "0")
    if not averaged:
        # ---- PWM with input-voltage feed-forward: ramp amplitude = Vin/KFF (FF=1) or fixed (FF=0) ----
        two("voltage", 1840, 336, "Vsaw", "PULSE(0 1 0 {Tsw-10n} 10n 0 {Tsw})", "saw", "0")
        two("bv", 1952, 336, "B_AMP", "V={FF}*V(vinf)/{KFF}+(1-{FF})*{Vin}/{KFF}", "amp", "0")
        two("res", 1840, 480, "Rff", "1k", "in", "vinf"); two("cap", 1840, 624, "Cff", "{1/(2*pi*1k*Fff)}", "vinf", "0")   # feed-forward sense filter
        two("bv", 1952, 480, "B_EN", "V=(1+tanh((time-5u)/0.5u))/2", "en", "0")   # both FETs off until enabled (as a real controller)
        two("bv", 2064, 336, "B_X", "V=limit(V(comp)/V(amp),0,{Dmax})", "dcmd", "0")
        two("bv", 2176, 336, "B_HS", "V=(1+tanh(300*(V(dcmd)-V(saw)-{dband})))/2*V(en)", "hs", "0")
        two("bv", 2288, 336, "B_LS", "V=(1+tanh(300*(V(saw)-V(dcmd)-{dband})))/2*V(en)", "ls", "0")

    P = [
     f"; === 06  BEC: 4S -> 5 V / 3 A SYNCHRONOUS BUCK, voltage mode, Type-III compensation, input feed-forward  ({'AVERAGED model, loop gain' if averaged else 'SWITCHING model, transients'}) ===",
     f"!.param Vin={h.Vin} Lout={h.L} DCR={h.DCR} Cout={h.C:.4g} ESR={h.ESR:.4g} Cin={h.Cin} KFF={h.KFF}",
     f"!.param Vref={h.Vref} Rtop={h.Rtop:.4g} Rbot={h.Rbot:.4g} R2={R2:.4g} C1={C1:.4g} C2={C2:.4g} R3={R3:.4g} C3={C3:.4g}",
     "!.param gm=1m A0=10k GBW=10Meg      ; error amplifier: 80 dB DC gain, 10 MHz gain-bandwidth",
    ]
    if averaged:
        P += ["!.step param Rl list 1.667 16.67     ; full load 3 A and light load 0.3 A",
              "!.ac dec 200 100 1Meg",
              "!.save V(out) V(x) V(comp) V(d)"]
    else:
        P += [f"!.param Fsw={h.fsw:.4g} Tsw={{1/Fsw}} Tdead=20n dband={{Tdead/Tsw}} Dmax=0.9 Vdrv=5 RgH=10 RgL=1   ; slow high-side turn-on, stiff low-side hold-off (first run, 2 ohm both: shoot-through)",
              "!.param Fff=100k        ; feed-forward Vin sense filter (removes switching spikes from the ramp amplitude)",
              "!.param Tss=1m Ilo=0.5 Ihi=3 Tst1=1.5m Tst2=2.2m Tst3=2.6m",
              "!.param Fesc=48k Vrip=1.5 Trip=2.9m Tsag=3.5m Vsag=0.8     ; ESC bus disturbances seen in topology 04",
              "!.step param FF list 1 0     ; input-voltage feed-forward on / off",
              "!.model BUCK_FET VDMOS(Rd=3m Rs=1m Vto=1.6 Kp=60 Cgdmax=400p Cgdmin=60p Cgs=900p Cjo=500p Is=2p N=1.05 Rb=6m Tt=10n Vds=30 Ron=6m Qg=10n mfg=Learning)",
              "!.tran 0 4.2m 0",
              "!.save V(in) V(vinf) V(sw) V(out) V(comp) V(dcmd) V(fb) V(ref) V(iload) I(L1) I(Lin) I(Cin) Id(MH) Id(ML) V(gh) V(gl)",
              "!.meas TRAN Vout_lo AVG V(out) FROM 1.3m TO 1.5m",
              "!.meas TRAN Vrip_lo PP V(out) FROM 1.3m TO 1.5m",
              "!.meas TRAN Vmin_step MIN V(out) FROM 1.5m TO 1.7m",
              "!.meas TRAN Vmax_unload MAX V(out) FROM 2.2m TO 2.4m",
              "!.meas TRAN Vout_hi AVG V(out) FROM 2.7m TO 2.9m",
              "!.meas TRAN Vrip_hi PP V(out) FROM 2.7m TO 2.9m",
              "!.meas TRAN IL_pp PP I(L1) FROM 2.7m TO 2.9m",
              "!.meas TRAN Icin_rms RMS I(Cin) FROM 2.7m TO 2.9m",
              "!.meas TRAN Vout_pp_esc PP V(out) FROM 3.1m TO 3.5m",
              "!.meas TRAN Vout_sag MIN V(out) FROM 3.5m TO 3.8m",
              "!.meas TRAN Vout_after AVG V(out) FROM 4.0m TO 4.2m",
              "!.meas TRAN Pin AVG V(in)*I(Lin) FROM 2.7m TO 2.9m",
              "!.meas TRAN Pout AVG V(out)*V(iload)*limit(V(out)/4,0,1) FROM 2.7m TO 2.9m",
              "!.meas TRAN Phs AVG V(in,sw)*Id(MH) FROM 2.7m TO 2.9m",
              "!.meas TRAN Pls AVG V(sw)*Id(ML) FROM 2.7m TO 2.9m",
              "!.meas TRAN Pdcr AVG {DCR}*I(L1)**2 FROM 2.7m TO 2.9m",
              "!.meas TRAN Eff PARAM Pout/Pin",
              "!.meas TRAN T_ss WHEN V(out)=4.5 RISE=1"]
    for i, s in enumerate(P):
        T(32, -500 + 30 * i if i < 10 else 600 + 26 * (i - 10), s)
    open(fname, "w", newline="\r\n").write("\n".join(L) + "\n")

build("BEC_Buck.asc", averaged=False)
build("BEC_Buck_AC.asc", averaged=True)

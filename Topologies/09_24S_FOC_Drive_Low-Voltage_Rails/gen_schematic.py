"""Generates the topology 09 schematics (python3 gen_schematic.py [rails] [drive] [ac] [qg]):
  Rails_Switching.asc : the switching power tree. AUX12 (in the ESC), HV12 -> BEC5 -> 3.3 V LDO (avionics), the inverter
                        as its DC-link current, start-up sequencing, load steps, a throttle punch. .step over 72/88.8/100.8 V
  Drive_24S.asc       : 24S pack -> harness -> DC link -> switching inverter with BOOTSTRAP gate drivers fed from the
                        ESC's 12 V rail -> U15XL under FOC (topology 03), starting at hover (.ic), throttle punch at 8 ms
  Rails_AC.asc        : averaged models of the three bucks, loop gain by Middlebrook injection, .step over converter x load
  GateCharge.asc      : gate-charge test bench of the inverter switch (constant gate current, clamped inductive load)
Every connection is made with net labels at the pins, so each part is placed in a labelled block, left to right."""
import sys, math
import hand_calc as h

PINS = {"res": ((16, 16), (16, 96)), "ind": ((16, 16), (16, 96)), "cap": ((16, 0), (16, 64)),
        "voltage": ((0, 16), (0, 96)), "bv": ((0, 16), (0, 96)), "bi": ((0, 0), (0, 80)), "diode": ((16, 0), (16, 64))}


class Sheet:
    def __init__(self):
        self.L = ["Version 4", "SHEET 1 4000 4000"]; self.x = 32; self.y = 0; self.row0 = 0

    def block(self, title):
        self.y = self.row0 + 160; self.row0 = self.y + 200; self.x = 32
        self.text(32, self.y - 64, f"; ===== {title} =====")

    def _next(self, w=160):
        if self.x > 3600: self.y += 240; self.row0 = self.y + 200; self.x = 32
        x = self.x; self.x += w; return x, self.y

    def flag(self, x, y, n): self.L.append(f"FLAG {x} {y} {n}")
    def text(self, x, y, s): self.L.append(f"TEXT {x} {y} Left 2 {s}")

    def two(self, sym, inst, val, top, bot, extra=()):
        x, y = self._next()
        self.L += [f"SYMBOL {sym} {x} {y} R0", f"SYMATTR InstName {inst}", f"SYMATTR Value {val}"] + list(extra)
        (a, b), (c, d) = PINS[sym]; self.flag(x + a, y + b, top); self.flag(x + c, y + d, bot)

    def bv(self, inst, expr, node, ref="0"): self.two("bv", inst, "V=" + expr, node, ref)
    def bi(self, inst, expr, frm, to): self.two("bi", inst, "I=" + expr, frm, to)

    def nmos(self, inst, model, d, g, s):
        x, y = self._next(176)
        self.L += [f"SYMBOL nmos {x} {y} R0", f"SYMATTR InstName {inst}", f"SYMATTR Value {model}"]
        self.flag(x + 48, y, d); self.flag(x, y + 80, g); self.flag(x + 48, y + 96, s)

    def directives(self, lines, x=32, y=None):
        y = self.row0 + 240 if y is None else y
        for i, s in enumerate(lines): self.text(x, y + 32 * i, s)

    def save(self, fname):
        open(fname, "w", newline="\r\n").write("\n".join(self.L) + "\n")


g = lambda v: f"{v:.6g}"
STEP = lambda t: f"(1+tanh((time-{t})/2u))/2"          # smooth step (no hard conditionals in B-sources)


def buck_switching(S, b, vin, out, en_expr, ref_expr):
    """Switching synchronous buck (topology 06 structure): ideal floating gate drive, Type III, gm error amp, feed-forward."""
    P = b.name; R2, C1, C2, R3, C3 = b.parts; Tsw = 1 / b.fsw
    S.block(f"{P}: {b.vin_min:g}-{b.vin_max:g} V -> {b.vout:g} V / {b.iout:g} A synchronous buck, {b.fsw/1e3:g} kHz, voltage mode + Type III + input feed-forward")
    S.two("res", f"Rs_{P}", "1m", vin, f"{P}in")                       # input current sense
    S.two("cap", f"Cin_{P}", g(b.cin), f"{P}in", "0", ["SYMATTR SpiceLine Rser=3m"])
    S.nmos(f"MH_{P}", b.top, f"{P}in", f"{P}gh", f"{P}sw")
    S.nmos(f"ML_{P}", b.bot, f"{P}sw", f"{P}gl", "0")
    S.bv(f"B_GH_{P}", f"{g(b.vdrv)}*V({P}hs)", f"{P}ghd", f"{P}sw"); S.two("res", f"RgH_{P}", g(b.RgH), f"{P}ghd", f"{P}gh")
    S.bv(f"B_GL_{P}", f"{g(b.vdrv)}*V({P}ls)", f"{P}gld"); S.two("res", f"RgL_{P}", g(b.RgL), f"{P}gld", f"{P}gl")
    S.two("ind", f"L_{P}", g(b.L), f"{P}sw", out, [f"SYMATTR SpiceLine Rser={g(b.DCR)}"])
    S.two("cap", f"Cout_{P}", g(b.C), out, "0", [f"SYMATTR SpiceLine Rser={g(b.ESR)} Lser=0.3n"])
    S.two("res", f"Rtop_{P}", g(b.Rtop), out, f"{P}fb")
    S.two("res", f"R3_{P}", g(R3), out, f"{P}n3"); S.two("cap", f"C3_{P}", g(C3), f"{P}n3", f"{P}fb")
    S.two("res", f"Rbot_{P}", g(b.Rbot), f"{P}fb", "0")
    S.two("res", f"R2_{P}", g(R2), f"{P}fb", f"{P}n2"); S.two("cap", f"C1_{P}", g(C1), f"{P}n2", f"{P}comp")
    S.two("cap", f"C2_{P}", g(C2), f"{P}fb", f"{P}comp")
    S.bv(f"B_REF_{P}", ref_expr, f"{P}ref")
    S.bi(f"B_GM_{P}", f"1m*(V({P}ref)-V({P}fb))", "0", f"{P}ea")
    S.two("res", f"Rea_{P}", "10Meg", f"{P}ea", "0"); S.two("cap", f"Cea_{P}", g(1e-3 / (2 * math.pi * 10e6)), f"{P}ea", "0")
    S.bv(f"B_EAOUT_{P}", f"limit(V({P}ea),0.02,4)", f"{P}comp")
    S.two("voltage", f"Vsaw_{P}", f"PULSE(0 1 0 {g(Tsw - 10e-9)} 10n 0 {g(Tsw)})", f"{P}saw", "0")
    S.two("res", f"Rff_{P}", "1k", f"{P}in", f"{P}vinf"); S.two("cap", f"Cff_{P}", g(1 / (2 * math.pi * 1e3 * b.Fff)), f"{P}vinf", "0")
    S.bv(f"B_AMP_{P}", f"V({P}vinf)/{g(b.KFF)}", f"{P}amp")
    S.bv(f"B_EN_{P}", en_expr, f"{P}en")
    S.bv(f"B_X_{P}", f"limit(V({P}comp)/V({P}amp),0,0.9)", f"{P}dcmd")
    db = g(b.tdead / Tsw)
    S.bv(f"B_HS_{P}", f"(1+tanh(300*(V({P}dcmd)-V({P}saw)-{db})))/2*V({P}en)", f"{P}hs")
    S.bv(f"B_LS_{P}", f"(1+tanh(300*(V({P}saw)-V({P}dcmd)-{db})))/2*V({P}en)", f"{P}ls")


def ldo(S, P, vin, out, cout, load_expr):
    """Behavioural LDO as a transconductance pass device: I_pass = Gm (3.3 V - Vout), limited to 0..2 A and scaled down in
    dropout (Vin - Vout < 0.25 V). Its input current IS its output current (+ Iq), so it cannot source power from a dead input.
    Load regulation = I/Gm (10 mV at 0.5 A with Gm = 50 S)."""
    S.block(f"{P}: 3.3 V LDO (behavioural pass device, Gm = 50 S, dropout {h.VDO} V, Iq {h.IQ_LDO*1e3:g} mA)")
    S.bi(f"B_{P}", f"limit(50*({h.V33}-V({out})),0,2)*limit((V({vin})-V({out}))/{h.VDO},0,1)", vin, out)
    S.bi(f"B_{P}q", f"{h.IQ_LDO}*limit(V({vin})/3,0,1)", vin, "0")
    S.two("cap", f"C_{P}", g(cout), out, "0", ["SYMATTR SpiceLine Rser=5m"])
    S.two("res", f"Rbl_{P}", "1Meg", out, "0")                       # DC path for the operating point
    S.bi(f"B_{P}load", load_expr, out, "0")


# ======================================================================================================
def build_rails():
    S = Sheet(); hv = h.hover(); pu = h.punch()
    i_inv_h = hv["mp"]["p_in"] / hv["vbus"]; i_inv_p = pu["mp"]["p_in"] / pu["vbus"]
    Kr = hv["icap"] / i_inv_h
    S.block("24S PACK -> PDB (avionics tap) -> 8 AWG harness -> ESC DC link; the inverter is its DC-link current (Run 2 has the real one)")
    S.two("voltage", "Vpk", "{Vpk}", "vpk", "0")
    S.two("res", "Rpk", g(h.Rpk), "vpk", "pdb")
    S.two("ind", "Lh", g(h.Lh), "pdb", "bus", [f"SYMATTR SpiceLine Rser={g(h.Rh)}"])
    S.two("cap", "Cbulk", g(h.CBULK), "bus", "0", [f"SYMATTR SpiceLine Rser={g(h.ESR_BULK)}"])
    S.two("cap", "Ccer", g(h.CCER), "bus", "0", ["SYMATTR SpiceLine Rser=1m"])
    S.two("voltage", "Vidc", f"PWL(0 0 {{Thov}} 0 {{Thov+0.3m}} {g(i_inv_h)} {{Tpunch}} {g(i_inv_h)} {{Tpunch+0.1m}} {g(i_inv_p)} "
                             f"{{Trel}} {g(i_inv_p)} {{Trel+0.1m}} {g(i_inv_h)})", "idc", "0")
    S.bi("B_INV", f"V(idc)*(1+{g(Kr)}*tanh(10*sin(2*pi*{g(2*h.Fsw)}*time)))", "bus", "0")
    # ---- ESC aux supply ----
    buck_switching(S, h.AUX12, "bus", "v12e", STEP("10u"), f"{h.Buck.Vref}*limit((time-10u)/{{Tss}},0,1)")
    S.block("ESC 12 V loads: bootstrap/gate charge pulses (6 x Qg per PWM period) + driver Iq")
    qg = h.ESC["Qg"]; tp = qg / 2.0
    S.two("voltage", "Vgp", f"PULSE(0 1 {{Thov}} 10n 10n {g(tp)} {g(1/(6*h.Fsw))})", "gp", "0")
    S.bi("B_GATE", f"2*V(gp)*limit(V(v12e)/10,0,1)+{h.I_DRV_Q}*limit(V(v12e)/10,0,1)", "v12e", "0")
    ldo(S, "LDOE", "v12e", "v33e", 4.7e-6, f"{h.I_MCU}*limit(V(v33e)/3,0,1)")
    # ---- avionics ----
    buck_switching(S, h.HV12, "pdb", "v12a", STEP("10u"), f"{h.Buck.Vref}*limit((time-10u)/{{Tss}},0,1)")
    S.block("Avionics 12 V load: video / telemetry transmitter, switched on at Tvtx (10 uF input capacitor on its board)")
    S.two("cap", "Cvtx", "10u", "v12a", "0", ["SYMATTR SpiceLine Rser=10m"])
    S.bi("B_VTX", f"{h.I_VTX}*{STEP('{Tvtx}')}*limit(V(v12a)/10,0,1)", "v12a", "0")
    S.bv("B_PG12", "(1+tanh((V(v12a)-10.8)/0.1))/2", "pg12")
    S.bi("B_SS5", "V(pg12)*1u*0.8/{Tss5}", "0", "ss5"); S.two("cap", "Css5", "1u", "ss5", "0"); S.two("res", "Rss5", "100Meg", "ss5", "0")
    buck_switching(S, h.BEC5, "v12a", "v5", "V(pg12)", "min(V(ss5),0.8)")
    S.block("Avionics 5 V loads: flight controller + receiver (0.8 A idle, +1.0 A at Tfc)")
    S.bi("B_FC", f"(0.8+1.0*{STEP('{Tfc}')})*limit(V(v5)/4,0,1)", "v5", "0")
    ldo(S, "LDOF", "v5", "v33", 10e-6, f"{h.I_SENS}*limit(V(v33)/3,0,1)")

    W = "FROM {Tw1} TO {Tw2}"
    D = ["; === 09  RUN 1: SWITCHING POWER TREE of one 24S channel. AUX12 in the ESC, HV12 -> BEC5 -> LDO for the avionics ===",
         "!.param Thov=2.0m Tvtx=2.6m Tfc=3.0m Tw1=3.3m Tw2=3.7m Tpunch=3.8m Trel=4.6m Tss=0.8m Tss5=0.5m",
         "!.step param Vpk list 88.8 72 100.8",
         h.vdmos_line("HV_TOP", h.FETS["HV_TOP"]), h.vdmos_line("HV_BOT", h.FETS["HV_BOT"]), h.vdmos_line("BUCK_FET", h.FETS["BUCK_FET"], "10n"),
         "!.tran 0 5.0m 0",
         "!.save V(vpk) V(pdb) V(bus) V(idc) V(v12e) V(v33e) V(v12a) V(v5) V(v33) V(pg12) V(ss5) V(HV12sw) V(AUX12sw) V(BEC5sw) "
         "V(HV12comp) V(AUX12comp) V(BEC5comp) I(L_HV12) I(L_AUX12) I(L_BEC5) I(Rs_HV12) I(Rs_AUX12) I(Rs_BEC5) I(Lh) I(Rpk) "
         "V(HV12in) V(AUX12in) V(BEC5in)",
         "!.meas TRAN T_aux WHEN V(v12e)=10.8 RISE=1", "!.meas TRAN T_hv WHEN V(v12a)=10.8 RISE=1",
         "!.meas TRAN T_5 WHEN V(v5)=4.5 RISE=1", "!.meas TRAN T_33 WHEN V(v33)=3.0 RISE=1",
         "!.meas TRAN T_33e WHEN V(v33e)=3.0 RISE=1",
         f"!.meas TRAN V12e AVG V(v12e) {W}", f"!.meas TRAN V12a AVG V(v12a) {W}", f"!.meas TRAN V5 AVG V(v5) {W}",
         f"!.meas TRAN V33 AVG V(v33) {W}", f"!.meas TRAN V33e AVG V(v33e) {W}",
         f"!.meas TRAN Vbus AVG V(bus) {W}", f"!.meas TRAN Vpdb AVG V(pdb) {W}",
         f"!.meas TRAN Rip_bus PP V(bus) {W}", f"!.meas TRAN Rip_pdb PP V(pdb) {W}",
         f"!.meas TRAN Rip12e PP V(v12e) {W}", f"!.meas TRAN Rip12a PP V(v12a) {W}", f"!.meas TRAN Rip5 PP V(v5) {W}",
         f"!.meas TRAN Rip33 PP V(v33) {W}",
         f"!.meas TRAN ILpp_hv PP I(L_HV12) {W}", f"!.meas TRAN ILpp_aux PP I(L_AUX12) {W}", f"!.meas TRAN ILpp_5 PP I(L_BEC5) {W}",
         f"!.meas TRAN Pin_hv AVG V(HV12in)*I(Rs_HV12) {W}", f"!.meas TRAN Pout_hv AVG V(v12a)*I(L_HV12) {W}",
         f"!.meas TRAN Pin_aux AVG V(AUX12in)*I(Rs_AUX12) {W}", f"!.meas TRAN Pout_aux AVG V(v12e)*I(L_AUX12) {W}",
         f"!.meas TRAN Pin_5 AVG V(BEC5in)*I(Rs_BEC5) {W}", f"!.meas TRAN Pout_5 AVG V(v5)*I(L_BEC5) {W}",
         "!.meas TRAN Eff_hv PARAM Pout_hv/Pin_hv", "!.meas TRAN Eff_aux PARAM Pout_aux/Pin_aux", "!.meas TRAN Eff_5 PARAM Pout_5/Pin_5",
         f"!.meas TRAN Ipk AVG I(Rpk) {W}", f"!.meas TRAN Pav_pdb AVG V(pdb)*I(Rs_HV12) {W}",
         "!.meas TRAN Dip_vtx MIN V(v12a) FROM {Tvtx} TO {Tvtx+0.25m}", "!.meas TRAN V12a_pre AVG V(v12a) FROM {Tvtx-0.1m} TO {Tvtx}",
         "!.meas TRAN Dip_fc MIN V(v5) FROM {Tfc} TO {Tfc+0.2m}", "!.meas TRAN V5_pre AVG V(v5) FROM {Tfc-0.1m} TO {Tfc}",
         "!.meas TRAN Vbus_punch MIN V(bus) FROM {Tpunch} TO {Trel}", "!.meas TRAN Vpdb_punch MIN V(pdb) FROM {Tpunch} TO {Trel}",
         "!.meas TRAN Vbus_pk_rel MAX V(bus) FROM {Trel} TO {Trel+0.3m}",
         "!.meas TRAN V12a_dev_punch PP V(v12a) FROM {Tpunch} TO {Trel+0.3m}", "!.meas TRAN V12e_dev_punch PP V(v12e) FROM {Tpunch} TO {Trel+0.3m}",
         "!.meas TRAN V5_dev_punch PP V(v5) FROM {Tpunch} TO {Trel+0.3m}",
         "!.meas TRAN V12e_min_gate MIN V(v12e) FROM {Thov+0.5m} TO {Tvtx}"]
    S.directives(D)
    S.save("Rails_Switching.asc")


# ======================================================================================================
def build_drive():
    S = Sheet(); hv = h.hover(); mp = hv["mp"]
    iq0 = mp["iq"]; w0 = h.W_HOVER; vb0 = hv["vbus"]; av_w = hv["av"]["p12_in"]
    S.block("24S PACK -> PDB (avionics: constant power) -> 8 AWG harness -> ESC DC link (16 x 150 uF polymer + 20 uF ceramic)")
    S.two("voltage", "Vpk", g(h.V_NOM), "vpk", "0")
    S.two("res", "Rpk", g(h.Rpk), "vpk", "pdb")
    S.bi("B_AV", f"{g(av_w)}/max(V(pdb),20)", "pdb", "0")
    S.two("ind", "Lh", g(h.Lh), "pdb", "bus", [f"SYMATTR SpiceLine Rser={g(h.Rh)}"])
    S.two("cap", "Cbulk", g(h.CBULK), "bus", "0", [f"SYMATTR SpiceLine Rser={g(h.ESR_BULK)}"])
    S.two("cap", "Ccer", g(h.CCER), "bus", "0", ["SYMATTR SpiceLine Rser=1m"])
    S.block("ESC 12 V rail: AUX12 AVERAGED (Run 1 has it switching): Vout = min(12, 0.9 Vbus), Iin = Pout/(eta Vbus); + driver Iq + MCU LDO")
    S.bv("B_AUX", "min(12,0.9*V(bus))", "v12s")
    S.two("res", "Raux", "20m", "v12s", "v12e")
    S.two("cap", "C12e", g(h.AUX12.C), "v12e", "0", [f"SYMATTR SpiceLine Rser={g(h.AUX12.ESR)}"])
    S.bi("B_AUXIN", "V(v12s)*I(Raux)/({Eta_aux}*max(V(bus),20))", "bus", "0")
    S.bi("B_ESCLOAD", f"{g(h.I_MCU + h.IQ_LDO + h.I_DRV_Q)}", "v12e", "0")
    for ph in "abc":
        P = ph.upper()
        S.block(f"LEG {P}: bootstrap gate drive. Low side from the 12 V rail; high side from Cboot, recharged through Dboot while the low side is on")
        S.nmos(f"M{P}H", "ESC150", "bus", f"gh{ph}", f"p{ph}")
        S.nmos(f"M{P}L", "ESC150", f"p{ph}", f"gl{ph}", "0")
        S.two("res", f"Rboot{ph}", "{Rboot}", "v12e", f"nb{ph}")
        S.two("diode", f"Dboot{ph}", "DBOOT", f"nb{ph}", f"boot{ph}")
        S.two("cap", f"Cboot{ph}", "{Cboot}", f"boot{ph}", f"p{ph}", ["SYMATTR SpiceLine Rser=5m"])
        S.bi(f"B_HON{ph}", f"V(h{ph})*(V(boot{ph})-V(gh{ph}))/{{Rdrv}}", f"boot{ph}", f"gh{ph}")
        S.bi(f"B_HOFF{ph}", f"(1-V(h{ph}))*(V(gh{ph})-V(p{ph}))/{{Rdrv}}", f"gh{ph}", f"p{ph}")
        S.bi(f"B_LON{ph}", f"V(l{ph})*(V(v12e)-V(gl{ph}))/{{Rdrv}}", "v12e", f"gl{ph}")
        S.bi(f"B_LOFF{ph}", f"(1-V(l{ph}))*V(gl{ph})/{{Rdrv}}", f"gl{ph}", "0")
        S.two("res", f"Rgsh{ph}", "10k", f"gh{ph}", f"p{ph}"); S.two("res", f"Rgsl{ph}", "10k", f"gl{ph}", "0")
        S.two("res", f"Rbl{ph}", "100k", f"boot{ph}", f"p{ph}")       # high-side driver quiescent / leakage
    S.block("U15XL PMSM (wye): each phase L, R, sinusoidal back-EMF;  mechanics: inertia, prop Kprop w^2, drag Bfric w (calibrated on vendor data)")
    for k, ph in enumerate("abc"):
        shift = f"-{2*k}*pi/3" if k else ""
        S.two("ind", f"L{ph}", "{Lph}", f"p{ph}", f"r{ph}")
        S.two("res", f"R{ph}", "{Rph}", f"r{ph}", f"x{ph}")
        S.bv(f"B_E{ph.upper()}", f"-{{Kph}}*V(omega)*sin(V(the){shift})", f"x{ph}", "n")
    S.bv("B_TE", "-{Kph}*(sin(V(the))*I(La)+sin(V(the)-2*pi/3)*I(Lb)+sin(V(the)-4*pi/3)*I(Lc))", "te")
    S.bi("B_Tmotor", "V(te)", "0", "omega")
    S.two("cap", "C_J", "{Jrot}", "omega", "0")
    S.bi("B_Tprop", "{Kprop}*V(omega)*abs(V(omega))+{Bfric}*V(omega)", "omega", "0")
    S.two("res", "R_leak", "100Meg", "omega", "0")
    S.bi("B_dtheta", "V(omega)", "0", "theta"); S.two("cap", "C_theta", "1", "theta", "0"); S.two("res", "R_leak2", "1G", "theta", "0")
    S.bv("B_THE", "{Pp}*V(theta)", "the"); S.bv("B_RPM", "V(omega)*60/(2*pi)", "rpm"); S.bv("B_WE", "{Pp}*V(omega)", "we")
    S.block("FOC (topology 03): speed PI -> iq*, Clarke + Park, d/q current PIs + decoupling, inverse Park/Clarke, SVPWM; integrators pre-loaded for hover")
    S.two("voltage", "Vwref", "PWL(0 {W0} {Tpunch} {W0} {Tpunch+10u} {Wpunch})", "wref", "0")
    S.bv("B_IQREF", "limit({Kpw}*(V(wref)-V(omega))+{Kiw}*idt(V(wref)-V(omega),{Iq0/Kiw}),-{Imax},{Imax})", "iqref")
    S.bv("B_IAL", "I(La)", "ial"); S.bv("B_IBE", "(I(La)+2*I(Lb))/sqrt(3)", "ibe")
    S.bv("B_ID", "V(ial)*cos(V(the))+V(ibe)*sin(V(the))", "id"); S.bv("B_IQ", "-V(ial)*sin(V(the))+V(ibe)*cos(V(the))", "iq")
    S.bv("B_VD", "{Kpi}*(0-V(id))+{Kii}*idt(0-V(id)) - V(we)*{Lph}*V(iq)", "vd")
    S.bv("B_VQ", "{Kpi}*(V(iqref)-V(iq))+{Kii}*idt(V(iqref)-V(iq),{Rph*Iq0/Kii}) + V(we)*{Lph}*V(id)+{Kph}*V(omega)", "vq")
    S.bv("B_VAL", "V(vd)*cos(V(the))-V(vq)*sin(V(the))", "val"); S.bv("B_VBE", "V(vd)*sin(V(the))+V(vq)*cos(V(the))", "vbe")
    S.bv("B_VA", "V(val)", "va"); S.bv("B_VB", "-V(val)/2+sqrt(3)/2*V(vbe)", "vb"); S.bv("B_VC", "-V(val)/2-sqrt(3)/2*V(vbe)", "vc")
    S.bv("B_VOFF", "(max(max(V(va),V(vb)),V(vc))+min(min(V(va),V(vb)),V(vc)))/2", "voff")
    S.two("res", "Rbf", "1k", "bus", "busf"); S.two("cap", "Cbf", g(1 / (2 * math.pi * 1e3 * 3e3)), "busf", "0")   # 3 kHz bus sense (07)
    S.two("voltage", "Vtri", "PULSE(0 1 0 {Tsw/2} {Tsw/2} 0 {Tsw})", "tri", "0")
    for ph in "abc":
        P = ph.upper()
        S.bv(f"B_D{P}", f"limit(0.5+(V(v{ph})-V(voff))/V(busf), 0.01, 0.99)", f"du{ph}")
        S.bv(f"B_H{P}", f"(1+tanh(500*(V(du{ph})-{{dband}}-V(tri))))/2", f"h{ph}")
        S.bv(f"B_L{P}", f"(1+tanh(500*(V(tri)-V(du{ph})-{{dband}})))/2", f"l{ph}")

    W = "FROM 4m TO 8m"; WP = "FROM 14m TO 20m"
    ic_boot = " ".join(f"V(boot{ph})={g(vb0 + 11.3)}" for ph in "abc")
    D = ["; === 09  RUN 2: 24S FOC DRIVE with bootstrap gate drive. Starts at hover (.ic + pre-loaded integrators), punch at 8 ms ===",
         f"!.param KV={h.KV} Ke={{60/(2*pi*KV)}} Kph={{Ke/sqrt(3)}} Pp={h.Pp} Rph={g(h.Rph)} Lph={g(h.Lph)}",
         f"!.param Jrot={h.Jrot} Kprop={g(h.Kprop)} Bfric={g(h.Bfric)}",
         f"!.param Fsw={g(h.Fsw)} Tsw={{1/Fsw}} Tdead={g(h.Tdead)} dband={{Tdead/Tsw}} Rdrv={h.Rdrv} Rboot={h.RBOOT} Cboot={g(h.CBOOT)} Eta_aux=0.90",
         f"!.param W0={g(h.W_HOVER)} Wpunch={g(h.RPM_TW2*2*math.pi/60)} Tpunch=8m Iq0={g(iq0)} Imax={h.Imax}",
         f"!.param Kpi={g(h.Kpi)} Kii={g(h.Kii)} Kpw={g(h.Kpw)} Kiw={g(h.Kiw)}",
         h.vdmos_line("ESC150", h.ESC, "50n"),
         "!.model DBOOT D(Is=1n Rs=0.5 N=1.5 Cjo=20p Tt=20n BV=200)",
         f"!.ic V(omega)={{W0}} V(theta)=0 I(La)=0 I(Lb)={{0.866*Iq0}} I(Lc)={{-0.866*Iq0}} I(Lh)={g(hv['i_esc'])} V(bus)={g(vb0)} V(busf)={g(vb0)} V(v12e)=12 {ic_boot}",
         "!.tran 0 20m 0",
         "!.save V(vpk) V(pdb) V(bus) V(busf) V(wref) V(pa) V(pb) V(pc) V(n) V(omega) V(rpm) V(te) V(the) V(id) V(iq) V(iqref) V(vd) V(vq) "
         "V(dua) V(dub) V(duc) I(La) I(Lb) I(Lc) I(Lh) I(Rpk) I(Cbulk) I(Ccer) V(v12e) I(Raux) V(boota) V(bootb) V(bootc) V(gha) V(gla) "
         "I(Rboota) I(Rbootb) I(Rbootc) Id(MAH) Id(MAL) Id(MBH) Id(MBL) Id(MCH) Id(MCL)",
         f"!.meas TRAN RPM_h AVG V(rpm) {W}", f"!.meas TRAN Iq_h AVG V(iq) {W}", f"!.meas TRAN Id_h AVG V(id) {W}",
         f"!.meas TRAN Vd_h AVG V(vd) {W}", f"!.meas TRAN Vq_h AVG V(vq) {W}", f"!.meas TRAN Te_h AVG V(te) {W}",
         f"!.meas TRAN Te_pp PP V(te) FROM 7m TO 8m",
         f"!.meas TRAN Vbus_h AVG V(bus) {W}", f"!.meas TRAN Vpdb_h AVG V(pdb) {W}", f"!.meas TRAN Vbus_pp PP V(bus) FROM 7m TO 8m",
         f"!.meas TRAN Vpdb_pp PP V(pdb) FROM 7m TO 8m",
         f"!.meas TRAN Ipk_h AVG I(Rpk) {W}", f"!.meas TRAN Iesc_h AVG I(Lh) {W}", f"!.meas TRAN Ilh_pp PP I(Lh) FROM 7m TO 8m",
         f"!.meas TRAN Icap_rms RMS I(Cbulk)+I(Ccer) {W}", f"!.meas TRAN Iph_rms RMS I(La) {W}",
         f"!.meas TRAN Pin_esc AVG V(bus)*I(Lh) {W}",
         f"!.meas TRAN Pshaft AVG {{Kprop}}*V(omega)**3 {W}", f"!.meas TRAN Pdrag AVG {{Bfric}}*V(omega)**2 {W}",
         f"!.meas TRAN Pcu AVG {{Rph}}*(I(La)**2+I(Lb)**2+I(Lc)**2) {W}",
         f"!.meas TRAN Pfet AVG V(bus,pa)*Id(MAH)+V(bus,pb)*Id(MBH)+V(bus,pc)*Id(MCH)+V(pa)*Id(MAL)+V(pb)*Id(MBL)+V(pc)*Id(MCL) {W}",
         f"!.meas TRAN Pchem AVG {h.V_NOM}*I(Rpk) {W}",
         "!.meas TRAN Eff_drive PARAM Pshaft/Pin_esc",
         f"!.meas TRAN I12_h AVG I(Raux) {W}", f"!.meas TRAN Iboot AVG I(Rboota)+I(Rbootb)+I(Rbootc) {W}",
         f"!.meas TRAN V12_min MIN V(v12e) {W}",
         f"!.meas TRAN Vboot_max MAX V(boota,pa) {W}", f"!.meas TRAN Vboot_min MIN V(boota,pa) {W}",
         f"!.meas TRAN Vgh_on MAX V(gha,pa) {W}",
         "!.meas TRAN Du_max MAX V(dua) FROM 4m TO 8m",
         "!.meas TRAN T_iq90 TRIG V(wref) VAL={W0+1} RISE=1 TARG V(iq) VAL={Iq0+0.9*(Imax-Iq0)} RISE=1",
         f"!.meas TRAN Iq_p AVG V(iq) {WP}", f"!.meas TRAN Vbus_p AVG V(bus) {WP}", f"!.meas TRAN Iesc_p AVG I(Lh) {WP}",
         f"!.meas TRAN Ipk_p AVG I(Rpk) {WP}",
         "!.meas TRAN Vbus_min MIN V(bus) FROM 8m TO 20m", "!.meas TRAN Vpdb_min_p MIN V(pdb) FROM 8m TO 20m",
         "!.meas TRAN Vboot_min_p MIN V(boota,pa) FROM 8m TO 20m",
         f"!.meas TRAN Icap_rms_p RMS I(Cbulk)+I(Ccer) {WP}",
         "!.meas TRAN W_end AVG V(omega) FROM 19.5m TO 20m"]
    S.directives(D)
    S.save("Drive_24S.asc")


# ======================================================================================================
def build_ac():
    """One averaged buck, .step over k: 0/1 AUX12 full/10 % load, 2/3 HV12, 4/5 BEC5. Parameters come from table(k, ...)."""
    S = Sheet()
    def tab(fn):
        pts = []
        for i, b in enumerate(h.BUCKS):
            for j, frac in enumerate((1.0, 0.1)):
                pts += [str(2 * i + j), g(fn(b, frac))]
        return "table(k," + ",".join(pts) + ")"
    prm = dict(Vin=lambda b, f: b.vin, L=lambda b, f: b.L, DCR=lambda b, f: b.DCR, C=lambda b, f: b.C, ESR=lambda b, f: b.ESR,
               Rtop=lambda b, f: b.Rtop, R2=lambda b, f: b.parts[0], C1=lambda b, f: b.parts[1], C2=lambda b, f: b.parts[2],
               R3=lambda b, f: b.parts[3], C3=lambda b, f: b.parts[4], Rl=lambda b, f: b.vout / (b.iout * f))
    S.block("AVERAGED SYNCHRONOUS BUCK (state-space averaged switch): <v_sw> = d*Vin, <i_in> = d*iL;  d = comp/(Vin/KFF)")
    S.two("voltage", "Vin", "{Vin}", "in", "0")
    S.bv("B_SWAVG", "V(d)*V(in)", "sw")
    S.bi("B_IIN", "V(d)*I(L1)", "in", "0")
    S.bv("B_D", "V(comp)/(V(in)/10)", "d")
    S.two("ind", "L1", "{L}", "sw", "out", ["SYMATTR SpiceLine Rser={DCR}"])
    S.two("cap", "Cout", "{C}", "out", "0", ["SYMATTR SpiceLine Rser={ESR}"])
    S.two("res", "Rload", "{Rl}", "out", "0")
    S.two("voltage", "Vinj", "0 AC 1", "x", "out")
    S.two("res", "Rtop", "{Rtop}", "x", "fb")
    S.two("res", "R3", "{R3}", "x", "n3"); S.two("cap", "C3", "{C3}", "n3", "fb")
    S.two("res", "Rbot", "10k", "fb", "0")
    S.two("res", "R2", "{R2}", "fb", "n2"); S.two("cap", "C1", "{C1}", "n2", "comp")
    S.two("cap", "C2", "{C2}", "fb", "comp")
    S.two("voltage", "Vref", "0.8", "ref", "0")
    S.bi("B_GM", "1m*(V(ref)-V(fb))", "0", "ea")
    S.two("res", "Rea", "10Meg", "ea", "0"); S.two("cap", "Cea", g(1e-3 / (2 * math.pi * 10e6)), "ea", "0")
    S.bv("B_EAOUT", "V(ea)", "comp")
    D = ["; === 09  LOOP GAIN of the three bucks (T = -V(out)/V(x)).  k: 0/1 AUX12 full/10 % load, 2/3 HV12, 4/5 BEC5 ===",
         "!.step param k 0 5 1"] + [f"!.param {n}={tab(fn)}" for n, fn in prm.items()] + [
         "!.ac dec 200 100 1Meg", "!.save V(out) V(x) V(comp) V(d)"]
    S.directives(D)
    S.save("Rails_AC.asc")


# ======================================================================================================
def build_qg():
    """Gate-charge test: constant 10 mA into the gate, drain carries the hover |i| average through a clamp diode to Vbus."""
    S = Sheet(); hv = h.hover(); iabs = 2 / math.pi * hv["mp"]["iq"]
    S.block("GATE CHARGE TEST BENCH (datasheet method): Ig = 10 mA constant, Iload clamped to Vdd by a diode; Qg = Ig * t(Vgs = 12 V)")
    S.two("voltage", "Vdd", g(h.V_NOM), "vdd", "0")
    S.two("diode", "Dclamp", "DCL", "d", "vdd")
    S.bi("B_LOAD", g(iabs), "0", "d")
    S.nmos("M1", "ESC150", "d", "g", "0")
    S.bi("B_IG", "10m*limit(time/10n,0,1)*(1+tanh(5*(14-V(g))))/2", "0", "g")
    S.two("res", "Rgs", "100Meg", "g", "0")
    D = ["; === 09  GATE CHARGE of the inverter switch (ESC150 = 4 x 150 V FETs in parallel) at the hover current ===",
         h.vdmos_line("ESC150", h.ESC, "50n"), "!.model DCL D(Is=1p Rs=1m N=1 Tt=0)",
         "!.tran 0 60u 0 2n", "!.save V(g) V(d) Id(M1)",
         "!.meas TRAN T_th WHEN V(g)=3.6 RISE=1", "!.meas TRAN T_pl1 WHEN V(d)={0.9*" + g(h.V_NOM) + "} FALL=1",
         "!.meas TRAN T_pl2 WHEN V(d)=2 FALL=1", "!.meas TRAN T_12 WHEN V(g)=12 RISE=1", "!.meas TRAN T_10 WHEN V(g)=10 RISE=1",
         "!.meas TRAN Qg12 PARAM 10m*T_12", "!.meas TRAN Qg10 PARAM 10m*T_10", "!.meas TRAN Qgd PARAM 10m*(T_pl2-T_pl1)",
         "!.meas TRAN Vplat AVG V(g) FROM T_pl1 TO T_pl2"]
    S.directives(D)
    S.save("GateCharge.asc")


if __name__ == "__main__":
    want = sys.argv[1:] or ["rails", "drive", "ac", "qg"]
    for w, fn in (("rails", build_rails), ("drive", build_drive), ("ac", build_ac), ("qg", build_qg)):
        if w in want: fn(); print("wrote", fn.__name__)

"""Builds 10_Hardware_Schematics_ESC_Avionics_Design.pdf: the two PCBs of topology 09 with real parts, hand vs. LTspice."""
import os, sys, math, json, csv
import numpy as np
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, "..", "tools")); sys.path.insert(0, here)
from designdoc import Doc
from ltraw import read_meas
import hand_calc as h

ma = {k: v[0] for k, v in read_meas(os.path.join(here, "Avionics_Board.log")).items()}
me = {k: v[0] for k, v in read_meas(os.path.join(here, "ESC_Board.log")).items()}
ex = json.load(open(os.path.join(here, "extra_metrics.json")))
h09 = h.h09; U1, A = h.U1, h.AUX
av = h.avionics()
pct = lambda a, b: f"{(b - a) / a * 100:+.1f} %"
nparts = lambda f: sum(int(r[1]) for r in list(csv.reader(open(os.path.join(here, f))))[1:])
nlines = lambda f: len(list(csv.reader(open(os.path.join(here, f))))) - 1

doc = Doc("10  Hardware Schematics: ESC + Avionics Boards",
          "topology 09 with real parts  |  LTC7801, LT8641, LT3045, LTC7063, LT1763, IPB065N15N3, ACS772, STM32G431, LTC4366  |  LTspice + KiCad hand-off")

doc.h("1. From a simulation to two boards")
doc.p("Topology 09 proved the power tree with behavioural controllers. A PCB needs real parts, reference designators, footprints "
      "and a net list. This topology splits the aircraft's electronics into the two boards it would actually have:")
doc.table(["Board", "Qty", "Parts", "Main parts"], [
    ["ESC board", "3", f"{nparts('ESC_BOM.csv')}", "LTC7801, 2×LT1763, 3×LTC7063, 24×IPB065N15N3, 2×ACS772, STM32G431"],
    ["Avionics board", "1", f"{nparts('Avionics_BOM.csv')}", "diode-OR (3×ES1D), LTC7801 12 V, LT8641 5 V, LT3045 3.3 V"],
], widths=[0.17, 0.06, 0.08, 0.69])
doc.p("Each board is described once, as a Python parts table (board.py). Every part carries its simulation value and its PCB data "
      "(part number, footprint, rating). The same table writes the LTspice schematic, the BOM and the net list, so the three cannot "
      "disagree. The controller ICs are ADI's own LTspice models. The FETs and diodes are the vendors' models from LTspice's library. "
      "The STM32's FOC firmware is a behavioural block that reads the same ADC nets the real chip would.")

# =====================================================================================================================
doc.h("2. Avionics board: the 12 V stage is now a real current-mode controller")
doc.p("09's HV12 was a voltage-mode buck with feed-forward. The LTC7801 is peak current mode: it switches the top FET off when "
      "the inductor current, seen across R1 = 10 mΩ, reaches a level set by the error amplifier's ITH voltage. The inductor then "
      "behaves like a current source, the LC double pole becomes a single pole at the output capacitor, and a Type II network "
      "(RITH + CITH, CITHB) is enough:")
doc.eq(r"T(s) = g_m Z_{ITH}(s)\;\frac{V_{FB}}{V_{out}}\;\frac{A_{ITH}}{R_{sense}}\;Z_{out}(s)\;e^{-s T_{sw}} \qquad R_{ITH} = \frac{2\pi f_c\,C_{out} V_{out} R_{sense}}{g_m V_{FB} A_{ITH}} = %.0f\ \Omega" % U1.rith_ideal, size=11)
doc.p("A_ITH, the ITH-to-sense-voltage gain, is not something I could take from a datasheet here. I assumed 1/12 and then measured "
      "the loop. Section 3 shows how. The power stage follows the usual steps:")
d0, dI0, dV0 = U1.ripple(h.V_FULL)
doc.table(["Quantity", "Formula", "Value"], [
    ["Switching frequency", "RFREQ = 30.1 kΩ, datasheet table", f"{U1.fsw/1e3:.1f} kHz"],
    ["Minimum on-time (100.8 V)", "D / fsw", f"{d0/U1.fsw*1e9:.0f} ns (limit ≈ 80–130 ns)"],
    ["Inductor ripple (100.8 V)", "(Vin − Vout) D / (L fsw), L = 47 µH", f"{dI0:.2f} A (30 % of 5 A)"],
    ["Current limit (output, min)", "VSENSE,min / Rsense − ΔI/2", f"{U1.ilim()['min']:.2f} A (≥ 5 A rating)"],
    ["Output ripple", "ΔI/(8 fsw C) + ΔI·ESR", f"{dV0*1e3:.1f} mV"],
    ["Soft-start", "0.8 V · CSS / 10 µA", f"{U1.tss*1e3:.2f} ms"],
    ["RUN / OVLO", "1.2 V · (1 + Rtop/Rbot)", f"{h.V_RUN:.1f} V / {h.V_OVLO:.1f} V"],
    ["Compensation", "RITH, CITH at fc/8, CITHB at fsw/2", f"{U1.rith/1e3:.2f} kΩ, {U1.cith*1e9:.0f} nF, {U1.cithb*1e12:.0f} pF"],
], widths=[0.3, 0.42, 0.28])
doc.p("Gate drive: DRVSET = 100 kΩ gives DRVCC = 5 × 20 µA × R = 10 V (the 150 V FETs are rated at 10 V), started by Q3 from "
      "Vin and then taken over by EXTVCC = 12 V output. That moves the gate power off the 88 V input, the loss 09 had to add on paper. "
      "The 5 V stage is ADI's LT8641 application circuit retargeted to a 12 V input. It is internally compensated, so the design is just "
      "the RT, L and Cout ranges from the datasheet. The 3.3 V LDO sets Vout = 100 µA × RSET = %.3f V." % h.V33)

doc.h("3. Measuring a switching loop gain with a transient injection")
doc.p("The LTC7801 model is encrypted and switching, so .ac cannot be used. Instead the loop test (Avionics_LoopTest.asc) puts a 20 mV "
      "sine in series with the feedback divider, as a network analyser would on the bench, and steps it over 3, 6, 12 and 24 kHz. "
      "After settling, both sides of the source are correlated with exp(−j2πft) over 8 cycles, and T = −V(+12V)/V(+12V_INJ).")
lp = ex["loop"]
rows = [[f"{p[0]/1e3:.0f} kHz", f"{abs(U1.loop(p[0], 5.0)):.3f} / {np.degrees(np.angle(U1.loop(p[0], 5.0))):.0f}°", f"{p[1]:.3f} / {p[2]:.0f}°"] for p in lp["points"]]
rows.append(["Crossover / phase margin", f"{lp['fc_hand']/1e3:.2f} kHz / {lp['pm_hand']:.1f}°", f"{lp['fc']/1e3:.2f} kHz / {lp['pm']:.1f}°"])
doc.table(["Frequency", "Hand |T| / phase", "LTspice |T| / phase"], rows, widths=[0.3, 0.35, 0.35])
doc.p("The first hand model had the right magnitude (within 10 %%, so A_ITH ≈ 1/13) but 78° of phase margin against 53° measured. The "
      "missing phase grew in proportion to frequency, 27° at 12 kHz and 56° at 24 kHz, which is the signature of a pure time delay: "
      "Δφ = 360°·f·τ gives τ ≈ 6.4 µs, almost one switching period (6.8 µs). A current-mode modulator acts once per period, so it adds "
      "about one period of delay. With e^(−sTsw) in the model the hand margin is %.1f°, against %.1f° measured." % (lp["pm_hand"], lp["pm"]))

doc.h("4. Avionics board: verification (Avionics_Board.asc)")
doc.p("8 ms from cold. All three packs connected; the 12 V soft-starts; its PGOOD enables the 5 V buck; the 5 V PG enables the 3.3 V LDO; "
      "the transmitter switches on at 6.0 ms; the controller steps 0.8 → 1.8 A at 6.5 ms; pack 1 is unplugged at 7.1 ms.")
dip_vtx = h.I_VTX / (2 * math.pi * lp["fc"] * (U1.C + 10e-6))
doc.table(["Quantity", "Hand", "LTspice", "Δ"], [
    ["+12V / +5V / +3V3 (V)", f"{U1.vset:.3f} / {h.V5:.3f} / {h.V33:.3f}", f"{ma['v12']:.3f} / {ma['v5']:.3f} / {ma['v33']:.3f}", pct(h.V5, ma["v5"])],
    ["12 V reaches 10.8 V (ms)", f"{U1.tss*10.8/12*1e3:.2f} + delay", f"{ma['t12']*1e3:.2f}", ""],
    ["12 V ripple (mV p-p) / inductor ripple (A)", f"{U1.ripple(h.V_NOM)[2]*1e3:.1f} / {U1.ripple(h.V_NOM)[1]:.2f}", f"{ma['rip12']*1e3:.1f} / {ma['il1pp']:.2f}", ""],
    ["Each pack's current, all 3 connected (A)", f"{av['i_in']/3:.3f}", f"{ma['i1']:.3f} / {ma['i2']:.3f} / {ma['i3']:.3f}", pct(av["i_in"] / 3, ma["i1"])],
    ["After pack 1 is pulled: packs 2, 3 (A)", f"{av['i_in']/2:.3f}", f"{ma['i2_after']:.3f}", pct(av["i_in"] / 2, ma["i2_after"])],
    ["12 V dip when pack 1 is pulled (mV)", "≈ 0 (diode-OR)", f"{(ma['v12'] - ma['v12_pull'])*1e3:.0f}", ""],
    ["Transmitter on: 12 V dip (mV)", f"{dip_vtx*1e3:.0f}", f"{(ma['v12_pre'] - ma['dip_vtx'])*1e3:.0f}", pct(dip_vtx, ma["v12_pre"] - ma["dip_vtx"])],
    ["Controller step: 5 V dip (mV)", "internal comp.", f"{(ma['v5_pre'] - ma['dip_fc'])*1e3:.0f}", ""],
    ["12 V stage efficiency", f"{av['l12']['eff']*100:.1f} %", f"{ma['eff12']*100:.1f} %", ""],
    ["Whole board (loads / packs)", f"{av['eff_total']*100:.1f} %", f"{ma['eff_board']*100:.1f} %", ""],
], widths=[0.38, 0.22, 0.26, 0.14])
doc.img(os.path.join(here, "Avionics_results.png"), width=6.6)
doc.p("The 5 V rail sits 1.2 %% high: 1 MΩ / 191 kΩ was sized for 0.800 V, and the model's reference works out to %.3f V. That is "
      "within a 5 V rail's tolerance, so the divider stays. The 12 V efficiency is 2 points below the hand estimate. The hand loss "
      "model uses the FETs' typical Ron at 25 °C and leaves out the controller's quiescent and DRVCC current. Pulling a pack costs "
      "the 12 V rail only %.0f mV, because the other two packs' diodes simply carry 3/2 of their previous current."
      % (ma["v5"] / (1 + h.LT8641["rtop"] / h.LT8641["rbot"]), (ma["v12"] - ma["v12_pull"]) * 1e3))

# =====================================================================================================================
doc.h("5. ESC board: design")
doc.table(["Block", "Design point", "Result"], [
    ["Inverter switch", "4 × IPB065N15N3 in parallel", f"{h.FETS['IPB065N15N3']['Ron']/4*1e3:.2f} mΩ per position"],
    ["Gate drive", "LTC7063, bootstrap 1 µF + ES1D", f"6·Qg·fsw = {h.I_GATE*1e3:.0f} mA, ΔVboot 0.30 V"],
    ["Dead time", "DT resistor 150 kΩ", f"{ex['esc']['dead_bg_tg']:.0f} / {ex['esc']['dead_tg_bg']:.0f} ns at Vgs = 3 V"],
    ["Aux 12 V (U1 LTC7801)", "440 kHz, 150 µH, 0.1 Ω, 32 µF", f"{h.I_12V*1e3:.0f} mA, ton {12/100.8/A.fsw*1e9:.0f} ns at 100.8 V"],
    ["Logic", "LT1763-5 → LT1763-3.3", f"{h.I_5V*1e3:.0f} / {h.I_3V3*1e3:.0f} mA, {h.P_LDO5:.2f} W in U2"],
    ["Current sense", "ACS772 ±250 A, 2/3 divider", f"±{h.I_RANGE:.0f} A in range, {h.ADC_A_PER_LSB*1e3:.0f} mA/LSB"],
    ["Bus sense", "3 × 330 kΩ (200 V each) + 33 kΩ", f"100.8 V → {h.VBUS_ADC_FULL:.2f} V"],
], widths=[0.25, 0.37, 0.38])
doc.p("Four D2PAKs per position give 1.4 mΩ against 09's assumed 1.05 mΩ, so conduction loss rises by a third. With 6.5 mΩ-max parts "
      "that is the price of using a FET LTspice has a vendor model for. A 4.8 mΩ part (IPB048N15N5) would bring it back to 09's number. "
      "The aux supply runs at 440 kHz rather than 148 kHz, so a 150 µH inductor can give 30 % ripple at 0.12 A. At 100.8 V the on-time "
      "is still 271 ns, twice the LTC7801's worst-case minimum.")

doc.h("6. ESC board: verification (ESC_Board.asc)")
doc.p("The ESC run is a real cold start of the electronics, with the rotor already turning at hover, as when an ESC is reset in "
      "flight: aux 12 V soft-start → LDOs → the MCU enables the drivers at 1.5 ms → FOC catches the spinning motor (a flying start) → "
      "throttle punch at 7 ms. The motor coasts for 1.5 ms and slows by about 0.3 rad/s, and the 10 Hz speed loop takes tens of "
      "milliseconds to recover that. So the hand values below are evaluated at the operating point LTspice actually reached (its iq "
      "and ω), not at nominal hover.")
es = ex["esc"]; w_h = es["omega_h"]; iq_h = es["iq_true"]
mp = h09.motor_point(w_h, h09.Kt * iq_h, me["vbus_h"])
inv_hand = h09.esc_loss(iq_h, me["vbus_h"])
ron_ratio = (h.FETS["IPB065N15N3"]["Ron"] / 4) / h09.ron_esc
inv_hand_tot = inv_hand["total"] + inv_hand["cond"] * (ron_ratio - 1)
p_em = 1.5 * h09.Kph * w_h * iq_h; p_cu = 1.5 * h09.Rph * iq_h ** 2
p_in_hand = p_em + p_cu + inv_hand_tot
p_drag = h09.Bfric * w_h ** 2
i_rgs = 3 * 0.5 * 12 / (10e3 / h.N_PAR)                       # high-side pull-downs, on half the time
iboot_hand = 3 * h.QG_SWITCH * h.FSW_INV + i_rgs
doc.table(["Quantity (4–7 ms)", "Hand at LTspice's iq, ω", "LTspice", "Δ"], [
    ["12 / 5 / 3.3 V reach 90 % (ms)", f"{A.tss*10.8/12*1e3:.2f} + delay", f"{me['t12']*1e3:.2f} / {me['t5']*1e3:.2f} / {me['t33']*1e3:.2f}", ""],
    ["+12V / +5V / +3V3 (V)", "12.000 / 5.000 / 3.300", f"{me['v12']:.3f} / {me['v5']:.3f} / {me['v33']:.3f}", ""],
    ["+12V min. at driver enable (V)", f"{12 - 3e-6*12/(A.C + 1e-6*3):.1f} (charge sharing)", f"{me['v12_en_min']:.2f}", ""],
    ["True iq / id (A)", f"{iq_h:.1f} / 0", f"{iq_h:.1f} / {es['id_true']:.1f}", ""],
    ["iq / id as read by the MCU (A)", f"{iq_h:.1f} / 0", f"{me['iq_h']:.1f} / {me['id_h']:.1f}", pct(iq_h, me["iq_h"])],
    ["Phase-current error, RMS (A)", "ripple + filter lag", f"{es['ia_err_rms']:.2f}", ""],
    ["Copper loss (W)", f"{p_cu:.1f}", f"{me['pcu']:.1f}", pct(p_cu, me["pcu"])],
    ["Inverter loss (W)", f"{inv_hand_tot:.1f}", f"{me['pfet']:.1f}", pct(inv_hand_tot, me["pfet"])],
    ["Electromagnetic power (W)", f"{p_em:.0f}", f"{es['p_em']:.0f}", pct(p_em, es["p_em"])],
    ["  = prop + drag + accel. (W)", f"{h09.Kprop*w_h**3:.0f} + {p_drag:.0f} + {p_em - h09.Kprop*w_h**3 - p_drag:.0f}",
     f"{me['pshaft']:.0f} + {p_drag:.0f} + {es['p_kin']:.0f}", ""],
    ["ESC input power (W)", f"{p_in_hand:.0f}", f"{me['pin_esc']:.0f}", pct(p_in_hand, me["pin_esc"])],
    ["DC-link capacitor RMS (A)", f"{h09.kolar(iq_h, mp['vd'], mp['vq'], me['vbus_h']):.1f}", f"{me['icap_rms']:.1f}", ""],
    ["Per bulk cap RMS (A, 24 x 3.5 A)", f"{h09.kolar(iq_h, mp['vd'], mp['vq'], me['vbus_h'])/h.N_BULK:.2f}",
     f"{me['icap_bulk']/h.N_BULK:.2f}", ""],
    ["Bootstrap current, 3 legs (mA)", f"{iboot_hand*1e3:.1f}", f"{me['iboot']*1e3:.1f}", pct(iboot_hand, me["iboot"])],
    ["Bootstrap voltage min–max (V)", "12 − Vf − Qg/C", f"{me['vboot_min']:.2f}–{me['vboot_max']:.2f}", ""],
    ["Aux 12 V ripple / punch min (V)", "—", f"{me['v12_pp']:.3f} / {me['v12_min_p']:.3f}", ""],
    ["Punch: iq / ESC current (A)", f"{h09.Imax:.0f} / —", f"{me['iq_p']:.1f} / {me['iesc_p']:.1f}", ""],
], widths=[0.34, 0.27, 0.25, 0.14])
doc.p("The rotor is still speeding up in this window (%.2f → %.2f rad/s in 3 ms), so %.0f W of the input goes into its kinetic "
      "energy ½Jω². Counting that, the energy balance closes: input = electromagnetic + copper + inverter to within a few watts. "
      "Bootstrap current: 3·Qg·fsw plus the high-side gate pull-downs, which draw 12 V / 2.5 kΩ while the FET is on. That is %.1f mA, "
      "a cost of the pull-downs worth knowing. The MCU's id reads a few amps off because the 6.7 µs ADC filter lags the 640 Hz "
      "currents by ωe·τ = 1.5°, and iq·sin(1.5°) ≈ 4 A. Firmware compensates for that by advancing the angle it uses for the Park "
      "transform by ωe·τ." % (es["omega0"], es["omega1"], es["p_kin"], i_rgs * 1e3))
doc.img(os.path.join(here, "ESC_results.png"), width=6.6)

doc.pagebreak()
doc.h("7. Fixes from the alternatives study")
doc.p("Topologies/Alternatives_Study checked every section against datasheet ratings and found three real problems. "
      "All three are fixed in the parts tables, so the schematics, BOMs, KiCad projects and topology 11 follow.", size=9.5)
dl = h.dc_link(); su = h.surge()
ms = {k: v[0] for k, v in read_meas(os.path.join(here, "Avionics_SurgeTest.log")).items()}
doc.p("DC link. The inverter's DC-link ripple (Kolar and Round) flows almost entirely in the polymer bank. Divided over "
      f"16 capacitors it was {dl['icap_h']/16:.2f} A rms each at hover, over the 3.5 A rating. C65-C72 add 8 more:", size=9.5)
doc.eq(r"I_{cap} = \frac{I_{C,rms}}{N} = \frac{%.1f\ \mathrm{A}}{24} = %.2f\ \mathrm{A\ (hover)}, \quad "
       r"\frac{%.1f\ \mathrm{A}}{24} = %.2f\ \mathrm{A\ (punch,\ seconds)}" % (dl["icap_h"], dl["per_h"], dl["icap_p"], dl["per_p"]), size=12)
doc.p(f"Phase current. Punch needs iq = {h09.Imax:.0f} A, outside the ACS770-200B's ±200 A. The ACS772ECB-250B (±250 A, "
      f"8 mV/A, 200 kHz, same CB package and pinout) replaces it. With the same 2/3 divider, ±{h.I_RANGE:.0f} A fits the ADC at "
      f"{h.ADC_A_PER_LSB*1e3:.0f} mA/LSB; the firmware conversion uses the new 8 mV/A.", size=9.5)
doc.p("Avionics surge. The SMBJ110A clamps to 177 V at 3.4 A, and the LTC7801 is rated to 150 V. U4 LTC4366-2 floats on the "
      "supply (RIN, RSS) and drives Q4 FDB33N25 (250 V) so that VIN_PROT stays at VREG while Q4 drops the rest. "
      "Equations from the LTC4366 datasheet:", size=9.5)
doc.eq(r"V_{REG} = 1.23\,\mathrm{V}\left(1+\frac{R_{24}}{R_{23}}\right) = 1.23\left(1+\frac{1.15\,\mathrm{M}}{12.4\,\mathrm{k}}\right) = %.1f\ \mathrm{V}" % su["vreg"], size=12)
doc.eq(r"R_{SS} \leq \frac{V_{IN,min}-V_{Z(OUT)}}{I_{VSS(CP)}} = \frac{71.25-6.0}{230\,\mu A} = %.0f\,\mathrm{k}\Omega \qquad "
       r"R_{IN} \leq \frac{V_{IN,min}-4.9-0.58-V_{TH}-72\,\mu A\,R_{SS}}{13\,\mu A} = %.2f\,\mathrm{M}\Omega" % (su["rss_max"] / 1e3, su["rin_max"] / 1e6), size=11)
doc.eq(r"t_{OV} = \frac{2.8\,\mathrm{V}\; C_T}{9\,\mu A} = %.0f\ \mathrm{ms} \qquad P_{Q4} = (V_{IN\_AV}-V_{REG})\,I_{load} = %.1f\ \mathrm{W}" % (su["t_tmr"] * 1e3, su["p_fet"]), size=12)
doc.p("RSS = 274 kΩ and RIN = 2.49 MΩ meet both limits; the start-up limit RSS ≤ RIN(VREG − 7)/(VIN,max − 5 − VREG) is "
      f"{su['rss_max_hi']/1e3:.0f} kΩ at a 200 V start. Avionics_SurgeTest.asc steps pack 1 to 200 V behind 4 Ω for 20 ms "
      "(an ISO 7637-2 pulse-5a-like source) with the 12 V stage modelled as its 0.35 A input current:", size=9.5)
doc.table(["Quantity", "Hand", "LTspice", "Error"], [
    ["VIN_PROT in regulation (V)", f"{su['vreg']:.1f}", f"{ms['vprot_reg']:.1f}", pct(su["vreg"], ms["vprot_reg"])],
    ["VIN_PROT peak during the surge (V)", f"{su['vreg']:.1f}", f"{ms['vprot_max']:.1f}", pct(su["vreg"], ms["vprot_max"])],
    ["VIN_AV at the TVS (V)", f"{su['v_av']:.0f}", f"{ms['vav_surge']:.1f}", pct(su["v_av"], ms["vav_surge"])],
    ["Q4 dissipation while regulating (W)", f"{su['p_fet']:.1f}", f"{ms['pq4']:.1f}", pct(su["p_fet"], ms["pq4"])],
    ["TIMER after 20 ms (V; fault at 2.8 V)", f"{9e-6*20e-3/h.SURGE['ct']:.2f}", f"{ms['vtmr_max']:.2f}", pct(9e-6*20e-3/h.SURGE['ct'], ms["vtmr_max"])],
    ["Start-up: VIN_PROT reaches 80 V (ms)", "~100 (7.5 µA, CG)", f"{ms['t_on']*1e3:.0f}", "—"],
], widths=[0.42, 0.2, 0.18, 0.2])
doc.img(os.path.join(here, "Avionics_surge.png"), width=6.4)
doc.p("The LTC4366 needs about 0.1 s to ramp Q4's gate, far longer than the 8 ms board run. Avionics_Board.asc therefore starts "
      "with Q4 already on (sim-only R_SSRUN, 94 mΩ, across it); the stopper itself is verified here. The 1.56 J in Q4 over the "
      "51 ms timer is well inside a D2PAK's transient rating. A surge longer than the timer turns Q4 off for the 9 s cool-down, "
      "so the flight controller would brown out; size CT for the longest surge the airframe can produce.", size=9)

# =====================================================================================================================
kd = os.path.join(here, "kicad", "Avionics_Board")
PITCH_ROW = 12.0                                   # ESC FET row pitch (pcb_esc.PITCH)
ls = json.load(open(os.path.join(kd, "layout_stats.json")))
doc.pagebreak()
doc.h("8. Avionics PCB layout (KiCad, for JLCPCB)")
doc.p("pcb_avionics.py turns the netted KiCad board into a manufacturable one: 4 layers, 1.6 mm, 2 oz outer / 1 oz inner copper "
      "(JLC04161H-7628: F.Cu, 0.21 mm prepreg, In1, 1.07 mm core, In2, 0.21 mm prepreg, B.Cu), 100 × 62 mm, four M3 holes. In1 and "
      "In2 are solid ground planes; F.Cu carries the power pours and B.Cu a ground pour plus the signal crossings. The layout is a "
      "script, so a schematic change is one re-run: export → place → pour → route → fill → DRC → Gerbers.", size=9.5)
# --- clearances
pk = {"HVIN": "200 (surge)", "HVF": f"{ms['vprot_max']:.0f}–122", "HVSW": "0–126", "PWR / DRV / signal": "≤ 13"}
doc.p("Clearance. IPC-2221B table 6-1, column B2 (external, uncoated, below 3050 m), gives the minimum spacing for the peak "
      "voltage between two conductors: 31–150 V → 0.6 mm, 151–300 V → 1.25 mm. Inner layers (B1) need only 0.2 mm up to 300 V; 0.5 mm "
      "is used. The peak voltages are from Avionics_SurgeTest (pack 1 stepped to 200 V behind 4 Ω). Nets are grouped by voltage, and "
      "the rule applies to the difference between the two groups' peaks:", size=9.5)
doc.table(["Group", "Nets", "Peak (V)", "Outer clearance to LV"], [
    ["HVIN", "PACK1-3+, PACK1-3_F, VIN_AV", pk["HVIN"], "1.25 mm (0.6 to HVF)"],
    ["HVF", "VIN_PROT, LTC4366 floating nets", pk["HVF"], "0.6 mm"],
    ["HVSW", "SW12, BST12, TG12", pk["HVSW"], "0.6 mm (0.6 to HVF)"],
    ["LV", "+12V/+5V/+3V3, GND, drivers, control", pk["PWR / DRV / signal"], "0.2 mm (JLC 2 oz minimum)"],
], widths=[0.11, 0.38, 0.17, 0.34])
doc.p("Inside one group the spacing is 0.2 mm: the floating LTC4366 nets all sit within 13 V of each other, and BST12 is SW12 + "
      "12 V. One exception: the LTC7801's own pinout puts VIN (pin 19) 0.65 mm from low-voltage pins, so the IC's pin field is a "
      "KiCad rule area where 0.2 mm applies. Its HTSSOP-24 pitch cannot meet B2, which is why the datasheet derates. Conformal "
      "coating (IPC B4: 0.13 mm up to 150 V) covers this; coat the board. The rule applies when both items touch the area, so a "
      "long track that leaves it would keep 0.2 mm along its whole length, and a ground pour (which covers the area) would get "
      "0.2 mm to every HV pin. So zones are excluded from the exemption, and pinfield_audit() cuts every exempt item back to the "
      "copper outside the area and measures the gaps that are left: all must meet the full rule. The router exempts a track by its "
      "centreline, while the copper reaches half a width further, so the rule area is the router's region grown by 0.25 mm "
      "(0.2 mm half-width + one 0.05 mm cell); without that margin the audit found BG12 0.56 mm from BST12 right at the edge.", size=9.5)
# --- trace width
ipc = lambda w_mm, oz=2, dT=10: 0.048 * dT ** 0.44 * ((w_mm / 0.0254) * oz * 1.378) ** 0.725
i_in = av["i_in"]; i_in_max = U1.vset * U1.iout / 0.93 / 71.25
doc.p("Track width. IPC-2221 (external): I = 0.048 ΔT^0.44 A^0.725, with A the cross-section in mil² (2 oz = 2.76 mil) and ΔT "
      "the allowed rise. At ΔT = 10 °C (the input maximum is 5 A out of the 12 V stage from the lowest pack, 71 V, at 93 %):", size=9.5)
doc.eq(r"I_{1.0\,mm} = 0.048\cdot 10^{0.44}\,(39.4\cdot 2.76)^{0.725} = %.1f\ \mathrm{A} \qquad I_{0.5\,mm} = %.1f\ \mathrm{A} \qquad I_{0.2\,mm} = %.1f\ \mathrm{A}" % (ipc(1.0), ipc(0.5), ipc(0.2)), size=11)
doc.table(["Path", "Current", "Copper", "Capacity (ΔT 10 °C)"], [
    ["Pack inputs → Q4 (HVIN)", f"{i_in:.2f} A typ, {i_in_max:.2f} A max", "1.0 mm + pours", f"{ipc(1.0):.1f} A"],
    ["12 V: SW → L1 → R1 → +12V", f"{U1.iout:.0f} A max", "pours ≥ 4 mm", f"{ipc(4.0):.0f} A"],
    ["+5V / +3V3 taps to ICs", "< 0.5 A", "0.5 mm (0.2 at pins)", f"{ipc(0.5):.1f} A / {ipc(0.2):.1f} A"],
    ["Signals, gate drive", "mA (gate ~1 A for ns)", "0.2–0.4 mm", f"{ipc(0.2):.1f}–{ipc(0.4):.1f} A"],
], widths=[0.3, 0.27, 0.22, 0.21])
# --- hot loop and Kelvin
mu0 = 4e-7 * math.pi; h_pp = 0.21e-3; l_loop = (71.9 - 51.35) * 1e-3; w_loop = 5e-3
L_loop = mu0 * h_pp * l_loop / w_loop; didt = U1.iout / 10e-9
doc.p("Hot loop. In a buck the current that switches on and off every cycle flows in C_in → Q1 → Q2 → ground → C_in. Q1, the switch "
      "node and Q2 sit in one line with C2/C3 at the left end; the loop closes back through the In1 plane 0.21 mm below "
      "(vias at C2/C3 and at Q2's source). A loop over a plane is a strip line, L ≈ µ0·h·l/w:", size=9.5)
doc.eq(r"L_{loop} \approx \frac{\mu_0\,h\,l}{w} = \frac{4\pi\cdot10^{-7}\cdot 0.21\,\mathrm{mm}\cdot %.1f\,\mathrm{mm}}{%.0f\,\mathrm{mm}} = %.2f\ \mathrm{nH}, \quad L\frac{di}{dt} = %.2f\,\mathrm{nH}\cdot\frac{%.0f\,\mathrm{A}}{10\,\mathrm{ns}} = %.2f\ \mathrm{V}" % (l_loop * 1e3, w_loop * 1e3, L_loop * 1e9, L_loop * 1e9, U1.iout, L_loop * didt), size=11)
doc.p("A side-by-side layout with the return on the same layer would enclose an area of millimetres, not 0.21 mm, and be ~10× worse. "
      "The FET packages add ~1 nH each, so the plane return halves the total.", size=9.5)
r_cu = 1.72e-8 * 5e-3 / (0.8e-3 * 70e-6)
doc.p(f"Kelvin sense. R1 = 10 mΩ gives 10 mV/A. A shared 5 mm × 0.8 mm run of 2 oz copper is ρl/(wt) = {r_cu*1e3:.1f} mΩ, so "
      f"tapping the pour instead of the resistor would read {r_cu/10e-3*100:.0f} % high and move the current limit. Two 0.3 mm traces "
      "leave from the inner edges of R1's pads, run together on B.Cu over the ground plane (no loop for the switch node to couple "
      "into), and reach SENSE+/SENSE− and the filter capacitor C4. The router marks them as foreign copper after they are drawn, so "
      "no other +12V connection can join them.", size=9.5)
# --- router
doc.p("Router. kicad_route.py is a small A* router on a 0.05 mm grid with two layers and vias (cost 2.5 mm of track). For each "
      "net it computes, with a Euclidean distance transform per voltage group, the cells where a track of the chosen width would come "
      "closer than that pair's clearance, then searches the free cells. A cell counts as copper when its centre is inside the copper. "
      "The real edge then lies beyond the outermost marked centre by up to one cell in each axis, so near a corner it can be a full "
      "cell diagonal closer than the grid says:", size=9.5)
doc.eq(r"e_{max} = \sqrt{2}\,\Delta = 0.071\ \mathrm{mm}, \qquad \mathrm{blocked\ if}\; d < s_{pair} + \frac{w}{2} + 0.75\,\Delta", size=12)
doc.p("The first version used a 0.1 mm grid and no margin; KiCad's DRC found 51 places 0.03–0.1 mm too close, which is exactly that "
      "error. The 0.75 Δ (0.04 mm) margin is a compromise: the full 0.071 mm would stop a 0.2 mm track from leaving a 0.5 mm-pitch pin "
      "(0.1 + 0.2 + 0.071 > 0.35 mm to the next pad), so the rest is left to KiCad's DRC. On the ESC board the DRC caught one via "
      "0.196 mm from an LQFP pin, so there the fan-out vias beside fine-pitch pads keep the full √2 Δ (all vias at √2 Δ cost too many via spots for the router to finish). Order matters too: the gate drive and the Kelvin pair go first, then a ground via beside every ground pad, then the "
      "small-signal nets (they need the short paths between IC pins), then the power taps, ground last. A track wider than a "
      "fine-pitch pin cannot reach it, so each connection retries at 0.4, 0.3, 0.25 and 0.2 mm.", size=9.5)
doc.p("Checking the checker. The first full run reported 0 DRC errors, and that was wrong. The rules were correct in the files, "
      "but two things kept them from the zone filler. (1) pcbnew.LoadBoard does not load the .kicad_dru into the board's DRC "
      "engine, and the filler asks that engine for every clearance, so it used the net-class value, 0.2 mm, everywhere. Calling "
      "WriteDRCReport first loads the rules file into the engine. (2) pcbnew keeps a project in memory after the first board is "
      "loaded and reuses it, so a reload missed the net classes written to the .kicad_pro afterwards. With no HV classes, no rule "
      "in the .kicad_dru matches (they all test A.NetClass), and the DRC agreed with a fill that was wrong. Re-checking with the "
      "classes in place gave 240 violations: pours 0.2 mm from 100–200 V copper. The fix unloads the cached project before every "
      "load and asserts that the classes arrived. The layout's clearances were then measured independently with KiCad's shape "
      "collision test: GND pour to HVIN ≥ 1.25 mm and to HVF/HVSW ≥ 0.6 mm on F.Cu/B.Cu, and ≥ 0.5 mm on the inner planes.", size=9.5)
drc = ls["drc"]
err = sum(v for k, v in drc.items() if k.startswith("error")); warn = {k.split(":")[1]: v for k, v in drc.items() if k.startswith("warning")}
doc.table(["Result", "Value"], [
    ["Parts placed", f"{ls['parts']} + 4 mounting holes"],
    ["Tracks / vias", f"{ls['tracks']} / {ls['vias']}  (F.Cu {ls['length_mm']['F.Cu']:.0f} mm, B.Cu {ls['length_mm']['B.Cu']:.0f} mm)"],
    ["Unrouted connections (KiCad DRC)", f"{ls['unconnected']}"],
    ["DRC errors", f"{err}" + ("" if not err else "  (" + ", ".join(f"{k.split(':')[1]} {v}" for k, v in drc.items() if k.startswith('error')) + ")")],
    ["DRC warnings", ", ".join(f"{k} {v}" for k, v in warn.items()) or "0"],
    ["Schematic ↔ PCB parity issues", f"{ls['schematic_parity']}"],
    ["Pin-field audit failures (outside U1 area)", f"{len(ls['pinfield_audit'])}"],
    ["References on F.Fab only (no silkscreen room)", f"{len(ls['hidden_refs'])} of {ls['parts']}"],
], widths=[0.45, 0.55])
doc.img(os.path.join(kd, "layout_routed.png"), width=6.6)
doc.img(os.path.join(kd, "board_3d_top.png"), width=5.2)
doc.p("Fabrication files (python3 pcb_avionics.py fab → kicad/Avionics_Board/jlcpcb/): Gerbers for the 4 copper layers, mask, "
      "paste, silkscreen and outline, Excellon drill (plated and non-plated), all in one zip for upload; the BOM and the CPL "
      "(placement) in JLC's column format. Check each part's rotation in JLC's preview before ordering: footprint zero "
      "orientations differ between KiCad and JLC's library for some packages (SOT-23, diodes, electrolytics).", size=9.5)

# =====================================================================================================================
kq = os.path.join(here, "kicad", "ESC_Board")
lq = json.load(open(os.path.join(kq, "layout_stats.json")))
doc.pagebreak()
doc.h("9. ESC PCB layout (KiCad, for JLCPCB)")
doc.p("pcb_esc.py lays out one ESC board the same way (same stackup, router and checks), %.0f × %.0f mm. The floorplan follows "
      "the current: a bank of 24 polymer capacitors in three rows of eight at the top, the battery pigtail J1 to the right of it, "
      "then three identical legs side by side, each a column of four high-side D2PAKs, a phase lane, four low-side D2PAKs and a "
      "ground lane. Below the legs is the low-current band: gate drivers, current sensors, motor-lead pads, MCU, LDOs and "
      "connectors. The aux 12 V buck sits in the top-right corner, where VBUS is. Battery current flows top to bottom and "
      "motor current leaves at the bottom, so no high current crosses the MCU's area and one solid ground plane (In1) serves "
      "both power and signal ground. A split ground is not needed." % tuple(lq["size_mm"]), size=9.5)
# --- clearance groups
doc.p("Clearance. 24S is 100.8 V full. Every net class that can sit 31–150 V away from another copper class gets 0.6 mm on the "
      "outer layers (IPC-2221B B2), and 0.3 mm on the inner ones (B1 asks 0.2 mm). Each phase is its own group, because two "
      "phases can be the full bus voltage apart. A phase, its bootstrap supply (phase + 12 V) and its high-side gates move "
      "together, so they share a group at 0.2 mm:", size=9.5)
doc.table(["Group", "Nets", "Voltage", "Outer clearance"], [
    ["HVBUS", "VBUS", "0–100.8 V", "0.6 mm to every other class"],
    ["SW_A/B/C", "PH_x, BST_x, TG_x, HS gates, MOT_x", "−1 to 113 V", "0.6 mm (0.2 mm inside a phase)"],
    ["SW_AUX", "aux SW, BST, TG", "0–113 V", "0.6 mm"],
    ["HVDIV1 / HVDIV2", "bus divider taps", "67 V / 34 V", "0.6 mm"],
    ["LV", "GND, +12V, +5V, +3V3, LS gates, signals", "≤ 13 V", "0.2 mm"],
], widths=[0.17, 0.4, 0.14, 0.29])
doc.p("The LTC7063's own pinout puts SW 0.25 mm from the unused NC pin and from BG, about 113 V apart, so each driver's pin field "
      "(and the LTC7801's) is an exempt rule area, checked by pinfield_audit() as on the avionics board. Conformal coating is "
      "required, as it is for any 100 V MSOP.", size=9.5)
# --- currents and copper
iq_t, id_t = es["iq_true"], es["id_true"]
iph_hand = math.hypot(iq_t, id_t) / math.sqrt(2); iph_p = me["iq_p"] / math.sqrt(2)
idc_hand = p_in_hand / me["vbus_h"]
doc.p("Currents. With amplitude-invariant Park transforms the phase current's RMS is |i_dq|/√2, and the DC current is the "
      "input power over the bus voltage:", size=9.5)
doc.eq(r"I_{ph,rms} = \frac{\sqrt{i_q^2+i_d^2}}{\sqrt{2}} = \frac{%.1f\ \mathrm{A}}{\sqrt{2}} = %.1f\ \mathrm{A} \qquad I_{DC} = \frac{P_{in}}{V_{bus}} = \frac{%.0f\ \mathrm{W}}{%.1f\ \mathrm{V}} = %.1f\ \mathrm{A}" % (math.hypot(iq_t, id_t), iph_hand, p_in_hand, me["vbus_h"], idc_hand), size=11)
doc.table(["Current", "Hand", "LTspice", "Δ"], [
    ["Phase, RMS, hover (A)", f"{iph_hand:.1f}", f"{me['iph_rms']:.1f}", pct(iph_hand, me["iph_rms"])],
    ["Phase, RMS, punch (A, seconds)", f"{iph_p:.1f} (from LTspice iq)", "—", ""],
    ["DC link, hover (A)", f"{idc_hand:.1f}", f"{me['iesc_h']:.1f}", pct(idc_hand, me["iesc_h"])],
    ["DC link, punch (A)", "—", f"{me['iesc_p']:.1f}", ""],
    ["DC-link capacitor ripple, RMS (A)", f"{h09.kolar(iq_h, mp['vd'], mp['vq'], me['vbus_h']):.1f}", f"{me['icap_rms']:.1f}", ""],
], widths=[0.4, 0.24, 0.18, 0.18])
doc.p("LTspice's phase RMS is a little higher: its 4–7 ms window still holds the end of the flying-start transient, and it "
      "includes the PWM ripple. For copper the 2 %% does not matter. IPC-2221's chart, for 2 oz outer copper and a 30 °C rise, "
      "asks for a %.0f mm wide trace at %.0f A. That is why the phases and the DC link are pours on all four layers, with a "
      "soldered bar on top." % (((iph_hand / (0.048 * 30 ** 0.44)) ** (1 / 0.725)) / (2 * 1.378) * 0.0254, iph_hand), size=9.5)
rs2, rs1 = 1.72e-8 / 70e-6, 1.72e-8 / 35e-6
rsq = 1 / (2 / rs2 + 1 / rs1)
w_lane, s_row, n_exit = 20.0, PITCH_ROW, 0.8
n_lane = s_row / w_lane * (1 + 4 + 9) / 16 + n_exit
p_lane = me["iph_rms"] ** 2 * rsq * n_lane
r_bar = 1.72e-8 / 8e-6 * 1e3                                     # 8 mm^2 bar: Ohm/m * 1e3 = uOhm/mm
r_lane = rsq / w_lane * 1e6                                      # lane: R_sq / w, uOhm per mm of length
k_bar = r_lane / (r_lane + r_bar)                                # the bar's share of the current
n_in2, n_br = 0.4, 2.8
r_feed = 1 / (1 / (rs1 * n_in2) + 1 / (rs2 * n_br)); r_bar_feed = 1.72e-8 / 8e-6 * 28e-3
r_feed_bar = 1 / (1 / r_feed + 1 / r_bar_feed)
doc.p("Counting squares. A sheet of copper of thickness t has a sheet resistance R_sq = ρ/t (ohms per square) whatever its size: %.3f mΩ for 2 oz, %.3f mΩ for 1 oz. A "
      "path l long and w wide is l/w squares. The phase lane is F.Cu + In2 + B.Cu in parallel, %.3f mΩ/□, about %.0f mm wide. "
      "Each of the four FET rows feeds a quarter of the phase current, so the three gaps between rows (%.0f mm each) carry I/4, "
      "I/2 and 3I/4, and the exit to the sensor carries all of it (≈ %.1f □):" % (rs2 * 1e3, rs1 * 1e3, rsq * 1e3, w_lane, s_row, n_exit), size=9.5)
doc.eq(r"P_{lane} = I^2 R_{\mathrm{sq}}\left[\frac{s}{w}\cdot\frac{1+4+9}{16} + n_{exit}\right] = %.0f^2\cdot %.3f\,\mathrm{m\Omega}\cdot %.2f = %.2f\ \mathrm{W\ per\ leg}" % (me["iph_rms"], rsq * 1e3, n_lane, p_lane), size=11)
doc.p("A 4 × 2 mm copper bar (8 mm², about the motor lead's 8 AWG) soldered on the lane is %.2f µΩ/mm against the lane's "
      "%.2f µΩ/mm, so it takes %.0f %% of the current and cuts the lane loss to about %.2f W. The DC feed from J1 runs through In2 "
      "(the whole top band, ≈ %.1f □) and the F.Cu bridge right of the bank (10 × 28 mm, %.1f □): %.2f mΩ, %.1f W at hover. A bar "
      "on the bridge brings that to %.2f mΩ, %.2f W." % (r_bar, r_lane, k_bar * 100, p_lane * (1 - k_bar),
      n_in2, n_br, r_feed * 1e3, me["iesc_h"] ** 2 * r_feed, r_feed_bar * 1e3, me["iesc_h"] ** 2 * r_feed_bar), size=9.5)
# --- thermal vias
k_cu, t_pl, d_via, t_pcb = 390.0, 25e-6, 0.3e-3, 1.6e-3
r_via = t_pcb / (k_cu * math.pi * d_via * t_pl); n_tab = 30
r_pad = 0.5e-3 / (3.0 * 9.4e-3 * 10.8e-3); r_jc = 0.5
p_fet1 = me["pfet"] / 24
dT = p_fet1 * (r_jc + r_via / n_tab + r_pad)
doc.p("Heat. %.0f W of FET loss at hover is %.1f W per D2PAK. Its tab is soldered to F.Cu; the heat sink presses on the opened "
      "B.Cu under each column through an insulating pad (B.Cu is at VBUS or phase potential). The path through the board is the "
      "via barrels, plated %.0f µm thick:" % (me["pfet"], p_fet1, t_pl * 1e6), size=9.5)
doc.eq(r"R_{via} = \frac{t_{PCB}}{k_{Cu}\,\pi d\,t_{pl}} = \frac{1.6\,\mathrm{mm}}{390\cdot\pi\cdot 0.3\,\mathrm{mm}\cdot 25\,\mu\mathrm{m}} = %.0f\ \mathrm{K/W}, \quad \frac{R_{via}}{%d} = %.1f\ \mathrm{K/W}" % (r_via, n_tab, r_via / n_tab), size=11)
doc.eq(r"\Delta T_{j-sink} = P\,(R_{jc} + R_{vias} + R_{pad}) = %.2f\,(%.1f + %.1f + %.1f) = %.0f\ \mathrm{K}" % (p_fet1, r_jc, r_via / n_tab, r_pad, dT), size=11)
doc.p("The pad is 0.5 mm at 3 W/m·K over the 9.4 × 10.8 mm tab. The FR-4 between the vias (0.3 W/m·K) adds a parallel path of about "
      "50 K/W and the inner planes spread the heat sideways; both are ignored, so the estimate is on the safe side. With the sink at "
      "60 °C the junctions run near %.0f °C, far from 175 °C. The vias sit in the solder pads, so order them epoxy-filled and capped "
      "(JLC 'POFV'), or the solder wicks down them." % (60 + dT), size=9.5)
# --- hot loop
l_hl, w_hl = 44e-3, 4 * PITCH_ROW * 1e-3
L_hl = mu0 * 0.21e-3 * l_hl / w_hl
doc.p("Commutation loop. Per leg the loop is ceramic → HS tab → HS source → phase lane → LS tab → LS source → ground lane, and "
      "back through In1, 0.21 mm under all of it, to the ceramic's ground pad. It is %.0f mm long but only 0.21 mm high and as "
      "wide as the four-row column (%.0f mm):" % (l_hl * 1e3, w_hl * 1e3), size=9.5)
doc.eq(r"L_{board} \approx \frac{\mu_0\,h\,l}{w} = \frac{4\pi\cdot10^{-7}\cdot 0.21\,\mathrm{mm}\cdot %.0f\,\mathrm{mm}}{%.0f\,\mathrm{mm}} = %.2f\ \mathrm{nH}" % (l_hl * 1e3, w_hl * 1e3, L_hl * 1e9), size=11)
doc.p("That is small next to the D2PAK leads themselves, so the overshoot is set by the packages. The next leg's ceramics sit on "
      "the other side of each ground lane, so every leg has capacitors at both ends of its loop. Gate drive: each FET has its "
      "series and pull-down resistors at the gate lead; the four of a column are joined by a B.Cu run under the phase copper (the "
      "high side) or the ground lane (the low side). The return is the copper directly above, so the gate loop is also flat.", size=9.5)
# --- routing
doc.p("Routing. The same A* router, with the hard spots planned by hand. (1) Pin order is topology: around an IC the "
      "destinations must come in the same cyclic order as the pins, or some connection has to change layer. The LTC7801's left "
      "row (0.65 mm pitch) has VBUS between NDRV and EXTVCC, and INTVCC must reach the far side of the chip, so pins 17–23 leave "
      "through a two-column via fan-out: alternate pins go 1.22 and 2.27 mm out, so each stub to the outer column passes between "
      "two inner vias with 0.225 mm to spare. VBUS drops straight into the In2 plane and the rest continue on B.Cu. (2) FAULT_N and "
      "DRV_EN are both buses along the three drivers, on neighbouring pins, so whichever is routed first walls in the other. "
      "FAULT_N drops to B.Cu through a via straight under its pin, between the EN and DT stubs. (3) The NTC divider's +3V3 is "
      "routed before the encoder bus to J5, which would otherwise wall R5 in. (4) After routing, tidy() necks every segment that "
      "ends in a pad down to the pad's narrow side less one cell: the router walks cell centres and then snaps the last point onto "
      "the exact pad centre, up to 25 µm off the grid it checked. It also removes vias that two fan-outs put on the same spot. "
      "Rip-up and retry did not help here: with the failed net routed first, a neighbour failed instead (+3V3, then PWM_B, then "
      "DT_B, then DRV_EN), so each crossing was fixed at its cause.", size=9.5)
# --- results
drq = lq["drc"]
errq = sum(v for k, v in drq.items() if k.startswith("error")); warnq = {k.split(":")[1]: v for k, v in drq.items() if k.startswith("warning")}
doc.table(["Result", "Value"], [
    ["Board", f"{lq['size_mm'][0]:.0f} × {lq['size_mm'][1]:.0f} mm, 4 layers, 2 oz / 1 oz, {lq['parts']} parts + 4 M3 holes"],
    ["Tracks", f"{lq['tracks']}  (F.Cu {lq['length_mm']['F.Cu']:.0f} mm, B.Cu {lq['length_mm']['B.Cu']:.0f} mm)"],
    ["Vias", f"{lq['vias']}  ({sum(lq['hand_vias'].values())} placed by hand, {lq['hand_vias']['tab']} of them in FET tabs)"],
    ["Unrouted connections (KiCad DRC)", f"{lq['unconnected']}"],
    ["DRC errors", f"{errq}" + ("" if not errq else "  (" + ", ".join(f"{k.split(':')[1]} {v}" for k, v in drq.items() if k.startswith('error')) + ")")],
    ["DRC warnings", ", ".join(f"{k} {v}" for k, v in warnq.items()) or "0"],
    ["Schematic ↔ PCB parity issues", f"{lq['schematic_parity']}"],
    ["Pin-field audit failures (U1, U4–U6)", f"{len(lq['pinfield_audit'])}"],
    ["Smallest HV gap, measured", "%.3f mm outer, %.3f mm inner (rules 0.6 / 0.3)" % (
        min(v[0] for L in ("F.Cu", "B.Cu") for v in lq["measured_gaps"][L].values() if v[0] is not None),
        min(v[0] for L in ("In1.GND", "In2.PWR") for v in lq["measured_gaps"][L].values() if v[0] is not None))],
    ["References on F.Fab only", f"{len(lq['hidden_refs'])} of {lq['parts']}"],
], widths=[0.36, 0.64])
doc.p("The measured gaps come from measure_gaps(), which does not use KiCad's DRC engine: per layer, all copper of each "
      "voltage group (pads, tracks, vias, zone fills) becomes one polygon set; one set is grown by d and intersected with the "
      "other, and d is bisected to 1 µm. Items are polygonised with at most 0.5 µm error. With KiCad's default 5 µm the "
      "first measurement showed slivers 0.595 mm from a 0.6 mm rule: the measuring tool's own error, not the board's.", size=9.5)
doc.img(os.path.join(kq, "layout_routed.png"), width=5.9)
doc.img(os.path.join(kq, "layout_routed_B.png"), width=5.9)
doc.img(os.path.join(kq, "board_3d_top.png"), width=5.6)
doc.p("Assembly notes. (1) Solder a 4 × 2 mm copper bar (or flattened 8 AWG wire) on each mask-free strip: the three phase lanes, "
      "the VBUS strip along the tops of the legs and the bridge from J1. (2) Put an insulating thermal pad (≥ 0.5 mm, ≥ 3 W/m·K, "
      "rated for 150 V) between the opened B.Cu and the heat sink. The NTC R6 sits on F.Cu at the bottom of leg B's ground lane, so it "
      "reads the board next to the FETs, not the sink. (3) Conformal-coat "
      "the board. (4) Order 2 oz outer copper and filled, capped vias, and check every part's rotation in JLC's preview.", size=9.5)

doc.h("10. What went wrong first (and what each taught)")
doc.bullets([
    "Units: the .asc files were first written as UTF-8 with 'µ'. LTspice read it as two Latin-1 characters and dropped the unit, so 47µ became 47 H and 0.1µ became 0.1 F, and nothing started. Write 'u', or write the file in Latin-1.",
    "Library models: a test from a bare .cir file said the vendor FETs were missing. From a schematic they load, because LTspice adds its standard libraries only for .asc files. Confirm a model by measuring it (here: Ron with 1 V / 1 mΩ), not by the absence of an error.",
    "A file named aux.asc cannot be opened under Wine: AUX is a reserved DOS device name.",
    "Net-name collision: the ESC aux supply's TG/BG nets were named TG_A/BG_A, the same as leg A's gate nets. Two gate drivers drove each other's FETs, and the 12 V rail climbed to 45 V. In a net-label schematic the names are the wiring, so give every block a unique suffix (_AUX).",
    "Behavioural loads that draw a constant current even at 0 V drag a rail negative at start-up and break the IC models. Scale every load by limit(V/Vnom, 0, 1).",
    "Encrypted IC models and .ic: forcing a soft-start pin or a rail at the operating point can leave a model in a state a real chip never reaches. Let the controllers start from cold, and give .ic only what is physically fixed (rotor speed).",
    "Missing parts the simulation found: gate-source pull-downs (without them the high-side FETs drift on through Cgd while the drivers are unpowered), and the LT1763 bypass capacitors (10 nF slows start-up to several ms; now 'do not fit').",
    "A DRC that passes is only as good as the rules it was given. The first full layout run reported 0 errors because the rules never reached the zone filler: pcbnew.LoadBoard skips the .kicad_dru, and a reload reused a cached project without the HV net classes. With the classes in place the same board had 240 violations (pours 0.2 mm from 100–200 V copper). Check that the rules are loaded (assert the classes) and measure a few clearances by an independent method.",
    "Burst Mode on the avionics 12 V gave a 90 mV, 25 kHz sawtooth at light load, which a radio does not want. MODE is tied to INTVCC (forced continuous).",
    "Driver enable dipped the first ESC's +12V to 7.4 V: all three bootstrap capacitors (3 × 1 µF) charge from the rail at once, and it had only ~10 µF. A 47 µF X7R (≈22 µF at 12 V) brings the minimum to 9.9 V. Charge sharing, ΔV ≈ 3·Cboot·12 V / C12, predicts 11.0 V; the rest is the drivers' own start-up current before the loop responds.",
    "A sensor model can lie too: the first ACS770 model got its 120 kHz bandwidth from 1 kΩ + 1.3 nF, and that 1 kΩ, loaded by the 30 kΩ ADC divider, lost 3 % of the signal. The real part's output impedance is a few ohms, so the model now uses 10 Ω + 133 nF.",
    "The first 'drive efficiency' read 76.6 %. It was not an efficiency: the rotor was still speeding up after the coast, so ½Jω² was absorbing about 0.9 kW. Write the energy balance before you trust a ratio.",
    "ESC layout: the router drew thin VBUS tracks from the high-side tabs to the capacitor bank, alongside the pours that already joined them. Its connectivity check counted two overlapping pours of the same net as separate islands when no pad or via sat in the overlap. Touching fills on the same layer now count as connected.",
    "ESC layout: the LTC7801's left pin row could not escape on one layer however the router ordered it. VBUS sits between NDRV and EXTVCC, and INTVCC has to reach the far side of the chip, so the destinations around the IC are not in the same cyclic order as its pins and some connection must change layer. A two-column via fan-out (alternate pins 1.22 and 2.27 mm out) is the standard answer for a 0.65 mm TSSOP.",
])

doc.h("11. Takeaways")
doc.bullets([
    "Clearance is set by the voltage between two conductors, not by the voltage of either one. Group the nets by peak voltage (from the surge simulation) and give KiCad one rule per pair of groups.",
    "Close the hot loop through the plane directly underneath it: L ≈ µ0·h·l/w with h = 0.21 mm is about 1 nH, a tenth of a loop drawn side by side.",
    "A grid router has its own error: with centre-sampled cells, copper can be up to a cell diagonal closer than the grid says. Add as much of it as the finest pin pitch allows (all of it for the fan-out vias beside fine-pitch pads), and let KiCad's DRC check the rest.",
    "Test the checker as well as the board: a DRC that reports 0 errors may simply not have loaded the rules. A deliberately bad case, or an independent clearance measurement, shows whether it is working.",
    "Describe the board once (a parts table) and generate the simulation, BOM and net list from it. That way what you simulated is what you build.",
    "A current-mode buck is a Type II loop on a single pole, plus about one switching period of delay. The delay costs ~25° of phase at fc ≈ fsw/13.",
    "You can measure a loop gain on a switching model with a series sine injection and a correlation at the injection frequency, which works even when the controller model is encrypted.",
    "At 0.35 A of avionics input current, three ordinary 200 V diodes OR the packs for 0.25 W. Ideal diodes (08) only pay off at higher current.",
    "An ESC that resets in flight must catch a spinning motor: freeze the FOC integrators until the drivers are enabled, then let the current loop take over.",
])
n = doc.save(os.path.join(here, "10_Hardware_Schematics_ESC_Avionics_Design.pdf"))
print("pages:", n)

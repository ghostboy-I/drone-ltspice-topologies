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
          "topology 09 with real parts  |  LTC7801, LT8641, LT3045, LTC7063, LT1763, IPB065N15N3, ACS770, STM32G431  |  LTspice + KiCad hand-off")

doc.h("1. From a simulation to two boards")
doc.p("Topology 09 proved the power tree with behavioural controllers. A PCB needs real parts, reference designators, footprints "
      "and a net list. This topology splits the aircraft's electronics into the two boards it would actually have:")
doc.table(["Board", "Qty", "Parts", "Main parts"], [
    ["ESC board", "3", f"{nparts('ESC_BOM.csv')}", "LTC7801, 2×LT1763, 3×LTC7063, 24×IPB065N15N3, 2×ACS770, STM32G431"],
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
    ["Current sense", "ACS770 ±200 A, 2/3 divider", f"±{h.I_RANGE:.0f} A in range, {h.ADC_A_PER_LSB*1e3:.0f} mA/LSB"],
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

doc.h("7. What went wrong first (and what each taught)")
doc.bullets([
    "Units: the .asc files were first written as UTF-8 with 'µ'. LTspice read it as two Latin-1 characters and dropped the unit, so 47µ became 47 H and 0.1µ became 0.1 F, and nothing started. Write 'u', or write the file in Latin-1.",
    "Library models: a test from a bare .cir file said the vendor FETs were missing. From a schematic they load, because LTspice adds its standard libraries only for .asc files. Confirm a model by measuring it (here: Ron with 1 V / 1 mΩ), not by the absence of an error.",
    "A file named aux.asc cannot be opened under Wine: AUX is a reserved DOS device name.",
    "Net-name collision: the ESC aux supply's TG/BG nets were named TG_A/BG_A, the same as leg A's gate nets. Two gate drivers drove each other's FETs, and the 12 V rail climbed to 45 V. In a net-label schematic the names are the wiring, so give every block a unique suffix (_AUX).",
    "Behavioural loads that draw a constant current even at 0 V drag a rail negative at start-up and break the IC models. Scale every load by limit(V/Vnom, 0, 1).",
    "Encrypted IC models and .ic: forcing a soft-start pin or a rail at the operating point can leave a model in a state a real chip never reaches. Let the controllers start from cold, and give .ic only what is physically fixed (rotor speed).",
    "Missing parts the simulation found: gate-source pull-downs (without them the high-side FETs drift on through Cgd while the drivers are unpowered), and the LT1763 bypass capacitors (10 nF slows start-up to several ms; now 'do not fit').",
    "Burst Mode on the avionics 12 V gave a 90 mV, 25 kHz sawtooth at light load, which a radio does not want. MODE is tied to INTVCC (forced continuous).",
    "Driver enable dipped the first ESC's +12V to 7.4 V: all three bootstrap capacitors (3 × 1 µF) charge from the rail at once, and it had only ~10 µF. A 47 µF X7R (≈22 µF at 12 V) brings the minimum to 9.9 V. Charge sharing, ΔV ≈ 3·Cboot·12 V / C12, predicts 11.0 V; the rest is the drivers' own start-up current before the loop responds.",
    "A sensor model can lie too: the first ACS770 model got its 120 kHz bandwidth from 1 kΩ + 1.3 nF, and that 1 kΩ, loaded by the 30 kΩ ADC divider, lost 3 % of the signal. The real part's output impedance is a few ohms, so the model now uses 10 Ω + 133 nF.",
    "The first 'drive efficiency' read 76.6 %. It was not an efficiency: the rotor was still speeding up after the coast, so ½Jω² was absorbing about 0.9 kW. Write the energy balance before you trust a ratio.",
])

doc.h("8. Takeaways")
doc.bullets([
    "Describe the board once (a parts table) and generate the simulation, BOM and net list from it. That way what you simulated is what you build.",
    "A current-mode buck is a Type II loop on a single pole, plus about one switching period of delay. The delay costs ~25° of phase at fc ≈ fsw/13.",
    "You can measure a loop gain on a switching model with a series sine injection and a correlation at the injection frequency, which works even when the controller model is encrypted.",
    "At 0.35 A of avionics input current, three ordinary 200 V diodes OR the packs for 0.25 W. Ideal diodes (08) only pay off at higher current.",
    "An ESC that resets in flight must catch a spinning motor: freeze the FOC integrators until the drivers are enabled, then let the current loop take over.",
])
n = doc.save(os.path.join(here, "10_Hardware_Schematics_ESC_Avionics_Design.pdf"))
print("pages:", n)

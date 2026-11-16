"""Builds 06_BEC_Synchronous_Buck_5V_Design.pdf: hand design + LTspice verification of the 4S -> 5 V BEC."""
import os, sys, math, json
import numpy as np
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, "..", "tools")); sys.path.insert(0, here)
from designdoc import Doc, INK, INK2, ACCENT
from ltraw import read_meas
from matplotlib.patches import FancyBboxPatch
import hand_calc as h

m = read_meas(os.path.join(here, "BEC_Buck.log")); S = lambda k, ff=1: m[k][ff]       # step order: FF=0, FF=1
ex = json.load(open(os.path.join(here, "extra_metrics.json")))
R2, C1, C2, R3, C3 = h.PARTS
fc0, pm0 = h.margins(h.PARTS, h.Vout / h.Iout); fc1, pm1 = h.margins(h.PARTS, h.Vout / h.Iout_min)
dV_step = (h.Iout - 0.5) / (2 * math.pi * fc0 * h.C)
Icin_hand = math.sqrt(h.D * (h.Iout ** 2 + h.dI ** 2 / 12) - (h.D * h.Iout) ** 2)
a48 = {ff: abs(h.line_cl(48e3, ff)) * 0.75 for ff in (0, 1)}; sag = {ff: h.step_peak(0.8, ff) for ff in (0, 1)}
Ron = ex["ron"]
P_hand = ex["hand_HS conduction"] + ex["hand_HS switching"] + ex["hand_LS conduction"] + ex["hand_Dead-time diode"] + ex["hand_Inductor DCR"]
eff_hand = h.Vout_set * h.Iout / (h.Vout_set * h.Iout + P_hand)
f_in = 1 / (2 * math.pi * math.sqrt(30e-9 * h.Cin))

doc = Doc("06  BEC: 4S to 5 V Synchronous Buck",
          "5 V / 3 A avionics rail  |  500 kHz, voltage mode, Type-III compensation, input feed-forward")

doc.h("1. What a BEC is and why this one")
doc.p("The flight controller, receiver, GPS and sensors need a clean 5 V, but the battery gives 12.8–16.8 V (4S, empty to full) and the "
      "ESC bus it shares is noisy (topology 04: 1.5 V p-p ripple at 48 kHz, plus a sag of about 0.8 V on a throttle punch). A battery "
      "eliminator circuit (BEC) is the step-down converter that makes the rail. A linear regulator would waste (15.2−5)/15.2 = 67 % of "
      "the power. A synchronous buck wastes about 3 %. This design powers the avionics from one channel's ESC bus; how three channels "
      "would feed it redundantly is a later topology.")

def block(ax):
    ax.set_xlim(0, 10); ax.set_ylim(0, 2.2)
    for x, t, sub in [(0, "ESC bus", "15.2 V + ripple"), (2.0, "Cin + FETs", "10 µF, half bridge"), (4.0, "L + Cout", "6.8 µH, 3x22 µF"),
                      (6.0, "5 V rail", "3 A avionics")]:
        ax.add_patch(FancyBboxPatch((x, 1.25), 1.7, 0.75, boxstyle="round,pad=0.02,rounding_size=0.06", fc="#eef4fc", ec=ACCENT, lw=1))
        ax.text(x + 0.85, 1.7, t, ha="center", fontsize=9, weight="bold", color=INK); ax.text(x + 0.85, 1.42, sub, ha="center", fontsize=7.5, color=INK2)
    for x in (1.7, 3.7, 5.7):
        ax.annotate("", (x + 0.3, 1.62), (x, 1.62), arrowprops=dict(arrowstyle="->", color=INK2))
    ax.add_patch(FancyBboxPatch((2.0, 0.1), 5.7, 0.75, boxstyle="round,pad=0.02,rounding_size=0.06", fc="white", ec=INK2, lw=0.8, ls="--"))
    ax.text(4.85, 0.55, "divider -> Type-III error amp -> PWM comparator (ramp = Vin/10) -> dead time -> gates", ha="center", fontsize=8, color=INK2)
    ax.text(4.85, 0.25, "two models: switching (transients) and averaged (loop gain with .ac)", ha="center", fontsize=8, color=INK2)
    ax.annotate("", (6.85, 0.85), (6.85, 1.25), arrowprops=dict(arrowstyle="->", color=INK2))
    ax.annotate("", (2.85, 1.25), (2.85, 0.85), arrowprops=dict(arrowstyle="->", color=INK2))
doc.figure(block, 2.1)

doc.h("2. Power stage")
doc.eq(r"D = \frac{V_{out}}{V_{in}} = \frac{5}{15.2} = %.3f \qquad \Delta I_L = \frac{(V_{in} - V_{out})\,D}{L\,f_{sw}} = %.2f\ \mathrm{A}\ \ (%.0f\%%\ \mathrm{of}\ 3\ \mathrm{A})" % (h.D, h.dI, h.dI / 3 * 100), size=12)
doc.p("L = 6.8 µH puts the ripple near the usual 30 %% of full load. The output capacitors are three 22 µF X7R ceramics. A ceramic loses "
      "capacitance under DC bias, typically about 40 %% at 5 V for a 10 V part in a small case, so the design uses C = %.1f µF, not 66 µF. "
      "Forgetting this is a classic cause of a loop that is less stable than designed." % (h.C * 1e6))
doc.eq(r"\Delta V_{out} = \frac{\Delta I_L}{8 f_{sw} C} + \Delta I_L\,ESR = %.1f + %.1f = %.1f\ \mathrm{mV} \qquad V_{out} = V_{ref}\left(1 + \frac{R_{top}}{R_{bot}}\right) = 0.8\left(1 + \frac{52.3}{10}\right) = %.3f\ \mathrm{V}" % (h.dI / (8 * h.fsw * h.C) * 1e3, h.dI * h.ESR * 1e3, h.dV * 1e3, h.Vout_set), size=11)
doc.eq(r"I_{C_{in},rms} = \sqrt{D\left(I_o^2 + \frac{\Delta I_L^2}{12}\right) - (D I_o)^2} = %.2f\ \mathrm{A}" % Icin_hand, size=12)

doc.h("3. The plant: a double pole the loop must cross")
doc.p("Averaging the switch over one period turns it into a voltage source d·Vin (the averaged switch model used in BEC_Buck_AC.asc). "
      "The duty-to-output transfer is then the output L-C filter, with the load damping it:")
doc.eq(r"G_{vd}(s) = V_{in}\,\frac{Z_o}{Z_o + DCR + sL} \qquad Z_o = R_{load}\,\|\,\left(ESR + \frac{1}{sC}\right) \qquad f_0 = \frac{1}{2\pi\sqrt{LC}} = %.2f\ \mathrm{kHz}" % (h.f0 / 1e3), size=12)
doc.p("Above f0 the gain falls at −40 dB/decade and the phase heads to −180°. The ceramics' ESR zero is at %.1f MHz, too high to help. "
      "A Type-II compensator (one zero) cannot recover enough phase, so voltage mode with ceramics needs Type III: two zeros." % (h.fesr / 1e6))

doc.h("4. Input-voltage feed-forward")
doc.p("The PWM comparator compares the error-amp output with a sawtooth of amplitude Vramp, so d = Vcomp/Vramp and the modulator gain "
      "is Vin/Vramp. If Vramp is fixed, the loop gain changes with battery voltage, and every input ripple passes straight to the "
      "switch node. Making the ramp amplitude proportional to Vin, Vramp = Vin/10, fixes both:")
doc.eq(r"\overline{v_{sw}} = d\,V_{in} = \frac{V_{comp}}{V_{in}/10}\,V_{in} = 10\,V_{comp} \qquad \Rightarrow\ \mathrm{modulator\ gain} = 10\ \mathrm{at\ any\ } V_{in}", size=12)
doc.p("The Vin sense is low-pass filtered at 100 kHz. The first run used the raw Vin: the switching spikes on Cin modulated the ramp "
      "amplitude, the comparator chattered, and the high-side FET dissipated 17 W. The filter costs some rejection at 48 kHz (section 8).")

doc.h("5. Type-III compensation")
doc.p("The error amp is a transconductance stage (80 dB, 10 MHz GBW). R1 = Rtop feeds the inverting input; R3–C3 in parallel with R1 "
      "add the second zero and a pole; R2–C1 and C2 in the feedback path give the integrator, the first zero and the second pole:")
doc.eq(r"f_{z1} = \frac{1}{2\pi R_2 C_1} \quad f_{z2} \approx \frac{1}{2\pi R_1 C_3} \quad f_{p1} = \frac{1}{2\pi R_2 C_2} \quad f_{p2} = \frac{1}{2\pi R_3 C_3}", size=12)
doc.bullets([
    "Both zeros a little below f0 (0.5·f0 and 0.7·f0) cancel the double pole's phase drop and add margin.",
    "Both poles at fsw/2 = 250 kHz: the ESR zero is out of reach, so the poles only roll off switching noise.",
    "R2 sets the mid-band gain. It was found by a 1-D search so that |T| = 1 at 50 kHz (fsw/10).",
])
doc.table(["Part", "Ideal", "Used (E96/E12)", "Sets"],
          [["R2", f"{h.PARTS_IDEAL[0]/1e3:.2f} kΩ", f"{R2/1e3:.1f} kΩ", "crossover"], ["C1", f"{h.PARTS_IDEAL[1]*1e9:.2f} nF", f"{C1*1e9:.1f} nF", f"fz1 = {1/(2*math.pi*R2*C1)/1e3:.1f} kHz"],
           ["C2", f"{h.PARTS_IDEAL[2]*1e12:.1f} pF", f"{C2*1e12:.0f} pF", f"fp1 = {1/(2*math.pi*R2*C2)/1e3:.0f} kHz"],
           ["R3", f"{h.PARTS_IDEAL[3]/1e3:.2f} kΩ", f"{R3/1e3:.2f} kΩ", f"fp2 = {1/(2*math.pi*R3*C3)/1e3:.0f} kHz"],
           ["C3", f"{h.PARTS_IDEAL[4]*1e12:.0f} pF", f"{C3*1e12:.0f} pF", f"fz2 = {1/(2*math.pi*h.Rtop*C3)/1e3:.1f} kHz"]],
          widths=[0.15, 0.25, 0.25, 0.35])
doc.eq(r"T(s) = 10\cdot\frac{Z_o}{Z_o + DCR + sL}\cdot\frac{Z_f}{Z_i} \qquad \mathrm{hand:}\ f_c = %.1f\ \mathrm{kHz},\ \ PM = %.1f^\circ\ (3\ \mathrm{A}),\ \ %.1f^\circ\ (0.3\ \mathrm{A})" % (fc0 / 1e3, pm0, pm1), size=12)
doc.p("LTspice measures T by injecting a 1 V AC source in series with the feedback divider (Middlebrook's method): T = −V(out)/V(x).")

doc.h("6. Load step")
doc.p("When the load jumps, the output capacitor supplies the difference until the loop responds, roughly in one crossover period. "
      "The standard estimate of the dip:")
doc.eq(r"\Delta V \approx \frac{\Delta I}{2\pi f_c C} = \frac{2.5}{2\pi\cdot %.0f\,k\cdot %.1f\,\mu} = %.0f\ \mathrm{mV}\ \ (%.1f\%%)" % (fc0 / 1e3, h.C * 1e6, dV_step * 1e3, dV_step / 5 * 100), size=12)
doc.p("To halve the dip, double fc or C. Doubling fc needs a faster amplifier and more phase margin; doubling C is easier, but it must "
      "be counted at its derated value.")

doc.h("7. Gate drive: Cdv/dt shoot-through")
doc.p("The first switching run had 95.1 % efficiency, and 0.53 W was lost in the low-side FET where conduction explains only 0.1 W. "
      "Body-diode reverse recovery looked guilty, but removing it (Tt = 0) made the loss worse, so that was ruled out. The real cause "
      "was the same mechanism as the plug-in trap in topology 05. The switch node rose at up to 40 V/ns. The low-side FET's Cgd "
      "pushed current into its own gate through the 2 Ω driver, and the gate reached 3.4 V against a 1.6 V threshold. Both FETs "
      "were on for a moment: shoot-through. The induced gate voltage is roughly:")
doc.eq(r"V_{GS,ind} \approx \min\left(R_{g,L}\,C_{gd}\frac{dV}{dt},\ \frac{C_{gd}}{C_{gd} + C_{gs}}\Delta V\right)", size=12)
doc.p("The fix is what real gate drivers do: turn the high side on slowly (RgH = 10 Ω) and hold the low side down hard (RgL = 1 Ω). "
      "Shoot-through stopped: the induced Vgs fell to %.2f V and efficiency rose to %.1f %%. Margin is still thin (0.3 V). A real design "
      "would add a FET with a lower Cgd/Cgs ratio or a split turn-off path." % (ex["vgs_ls_induced"], S("eff") * 100))
doc.p("The slower high-side turn-on costs switching loss, estimated from the Miller charge Qgd ≈ Cgd·Vin (Cgd averaged at 150 pF) "
      "and the gate current at the plateau:")
doc.eq(r"t_r = \frac{Q_{gd}}{(V_{drv} - V_{plat})/R_{gH}} = %.1f\ \mathrm{ns} \quad t_f = \frac{Q_{gd}}{V_{plat}/R_{gH}} = %.1f\ \mathrm{ns} \quad P_{sw} = \frac{1}{2}V_{in}I_o(t_r + t_f)f_{sw} = %.2f\ \mathrm{W}" % (ex["tr"] * 1e9, ex["tf"] * 1e9, ex["hand_HS switching"]), size=11)

doc.h("8. Rejecting the ESC bus")
doc.p("With the loop closed, an input disturbance reaches the output through:")
doc.eq(r"\frac{v_{out}}{v_{in}} = \frac{D\,\frac{Z_o}{Z_o + DCR + sL}\,(1 - F(s))}{1 + T(s)} \qquad F = 0\ \mathrm{(no\ FF)},\ \ F = \frac{1}{1 + s/2\pi\,100\,\mathrm{kHz}}\ \mathrm{(filtered\ FF)}", size=12)
doc.p("At 48 kHz the loop gain is only about 1, so the loop barely helps. The L-C filter (−27 dB) and the feed-forward (−7 dB with the "
      "100 kHz filter) do the work. A 0.8 V sag in 50 µs is a slower disturbance, which the feed-forward cancels almost completely.")

doc.h("9. Hand calculation vs. LTspice")
rows = []
def add(lab, hv, sv, fmt):
    e = (sv / hv - 1) * 100
    rows.append([lab, fmt.format(hv), fmt.format(sv), "0.0 %" if abs(e) < 0.05 else f"{e:+.1f} %"])
add("Output voltage (V)", h.Vout_set, S("vout_hi"), "{:.3f}")
add("Inductor ripple p-p (A)", h.dI, S("il_pp"), "{:.3f}")
add("Output ripple p-p (mV)", h.dV * 1e3, ex["vrip_detrended"] * 1e3, "{:.2f}")
add("Input cap RMS current (A)", Icin_hand, S("icin_rms"), "{:.2f}")
add("Crossover, 3 A (kHz)", fc0 / 1e3, ex["fc_sim_0"] / 1e3, "{:.1f}")
add("Phase margin, 3 A (deg)", pm0, ex["pm_sim_0"], "{:.1f}")
add("Phase margin, 0.3 A (deg)", pm1, ex["pm_sim_1"], "{:.1f}")
add("Load-step dip 0.5 -> 3 A (mV)", dV_step * 1e3, (h.Vout_set - S("vmin_step")) * 1e3, "{:.0f}")
add("48 kHz at output, FF off (mV amp)", a48[0] * 1e3, ex["a48_off"] * 1e3, "{:.1f}")
add("48 kHz at output, FF on (mV amp)", a48[1] * 1e3, ex["a48_on"] * 1e3, "{:.1f}")
add("Sag dip, FF off (mV), sag + ripple", (sag[0] + a48[0]) * 1e3, ex["sag_off"] * 1e3, "{:.1f}")
add("Sag dip, FF on (mV), sag + ripple", (sag[1] + a48[1]) * 1e3, ex["sag_on"] * 1e3, "{:.1f}")
add("High-side FET loss (W)", ex["hand_HS conduction"] + ex["hand_HS switching"], S("phs"), "{:.3f}")
add("Low-side FET loss (W)", ex["hand_LS conduction"] + ex["hand_Dead-time diode"], S("pls"), "{:.3f}")
add("Inductor DCR loss (W)", ex["hand_Inductor DCR"], S("pdcr"), "{:.3f}")
add("Efficiency at 3 A (%)", eff_hand * 100, S("eff") * 100, "{:.1f}")
doc.table(["Quantity", "Hand calc", "LTspice", "Difference"], rows, widths=[0.46, 0.18, 0.18, 0.18])
doc.bullets([
    "Input cap RMS is %.0f %% high: the 30 nH input wire and the 10 µF Cin resonate at %.0f kHz, near fsw, so some ripple current circulates "
    "between them (the same harness resonance as topology 04, one level down)." % ((S("icin_rms") / Icin_hand - 1) * 100, f_in / 1e3),
    "The low-side loss is below the hand value: the real dead time, where the body diode conducts, is shorter than the 20 ns commanded, "
    "because the gate thresholds sit partway up the edges.",
    "The sag dips are rough. The hand model treats the sag and the 48 kHz ripple separately and adds their peaks; in the simulation the "
    "sag lands at some ripple phase.",
    "Output ripple: the capacitive part (a parabola-like wave, %.1f mV) and the ESR part (a triangle, %.1f mV) peak at different "
    "moments, so adding them overestimates the total. The capacitive term alone is within %.0f %% of the simulation." % (h.dI / (8 * h.fsw * h.C) * 1e3, h.dI * h.ESR * 1e3, abs(ex["vrip_detrended"] / (h.dI / (8 * h.fsw * h.C)) - 1) * 100),
    "The loop-gain differences of 1–2° come from the error amp's 10 MHz GBW, which the hand model ignores.",
])

doc.h("10. Simulated waveforms")
doc.img(os.path.join(here, "BEC_results.png"), width=6.6)

doc.h("11. Key takeaways")
doc.bullets([
    "A buck's duty-to-output transfer is an L-C double pole. With ceramic outputs, voltage mode needs Type-III compensation.",
    "Two models, one design: averaged for the loop (.ac, Middlebrook injection), switching for ripple, edges and losses.",
    "Count ceramic capacitors at their DC-bias-derated value. Here 66 µF nominal is about 40 µF real.",
    "Input feed-forward makes the loop gain independent of battery voltage and cancels input disturbances. Filter its sense input.",
    "Fast edges cause Cdv/dt turn-on of the low-side FET. Gate resistors trade switching loss against shoot-through.",
    "ΔV ≈ ΔI/(2π fc C) gives the load-step dip in one line, and here it matched the simulation exactly.",
])
out = os.path.join(here, "06_BEC_Synchronous_Buck_5V_Design.pdf")
print(out, doc.save(out), "pages")

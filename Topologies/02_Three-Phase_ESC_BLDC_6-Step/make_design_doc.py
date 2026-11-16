"""Builds 02_Three-Phase_ESC_BLDC_6-Step_Design.pdf: hand calculations + LTspice results for topology 02."""
import os, sys, math
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, "..", "tools"))
from designdoc import Doc, INK, INK2, ACCENT
from ltraw import read_meas
from matplotlib.patches import FancyBboxPatch

# ---------------- design parameters (same as the .asc) ----------------
Vbatt, Rbatt, Rwire = 15.2, 20e-3, 2e-3
Fsw, Tdead, D = 48e3, 100e-9, 0.5
KV, Pp, Rph, Lph = 2300, 7, 50e-3, 7.5e-6
J, kprop, bfric = 5e-6, 1.15e-8, 1e-6
Vdrv, Vto, Kp, Rds_ext = 10, 1.8, 120, 3e-3
Is_d, N_d, Rb_d = 5e-12, 1.05, 4e-3
Ke = 60 / (2 * math.pi * KV)
Ron = Rds_ext + 1 / (Kp * (Vdrv - Vto))           # Rd + Rs + channel resistance at Vgs = 10 V
Vt = 0.02585
vf = lambda i: N_d * Vt * math.log(i / Is_d) + i * Rb_d   # body-diode forward drop

def operating_point(sync, comm=True):
    Vbus, I, w = Vbatt, 8.0, 1600.0
    for _ in range(50):
        Vf = vf(I)
        fcomm_ = 6 * Pp * (w if _ else 1600) / (2 * math.pi)
        Vcomm = fcomm_ * Lph * I if comm else 0.0                         # commutation-overlap volt-second loss
        if sync: Rfet, Vdrop = 2 * Ron, 2 * Tdead * Fsw * Vf + Vcomm
        else:    Rfet, Vdrop = Ron * (1 + D), (1 - D) * Vf + Vcomm
        R = 2 * Rph + Rfet
        a, b, c = R * kprop / Ke, R * bfric / Ke + Ke, -(D * Vbus - Vdrop)
        w = (-b + math.sqrt(b * b - 4 * a * c)) / (2 * a)
        I = (kprop * w * w + bfric * w) / Ke
        Vbus = Vbatt - D * I * (Rbatt + Rwire)
    Vcomm_final = Vcomm
    dI = (Vbus - I * R - Ke * w) * D / (2 * Lph * Fsw)
    Irms2 = I ** 2 + dI ** 2 / 12
    Pcu = 2 * Rph * Irms2
    Phi = Irms2 * Ron * D
    if sync: Plo = Irms2 * Ron + Irms2 * Ron * (1 - D) + 2 * Vf * I * Tdead * Fsw
    else:    Plo = Irms2 * Ron + Vf * I * (1 - D)
    Pm = Ke * I * w
    Pin = Pm + Pcu + Phi + Plo
    return dict(Vcomm=Vcomm_final, Vbus=Vbus, I=I, w=w, rpm=w * 60 / (2 * math.pi), Vf=Vf, R=R, Vdrop=Vdrop, dI=dI, Pcu=Pcu,
                Phi=Phi, Plo=Plo, Pm=Pm, Pin=Pin, Ibat=Pin / Vbus, Iph_rms=math.sqrt(Irms2 * 2 / 3))

op0, op1 = operating_point(False), operating_point(True)
op1_nc = operating_point(True, comm=False)
fe = Pp * op1["w"] / (2 * math.pi); fcomm = 6 * fe
sim = read_meas(os.path.join(here, "ThreePhase_ESC_BLDC.log"))
s = lambda k, i: sim[k][i]

doc = Doc("02  Three-Phase ESC + BLDC (6-step)", "Hall-sensored trapezoidal drive  |  4S LiPo, 48 kHz PWM, 2300KV 7-pole-pair motor, 5 in prop")

doc.h("1. What the circuit is")
doc.p("This is a real drone ESC power stage: three copies of the half-bridge leg from topology 01, all on one DC bus, each driving one "
      "terminal of a wye-connected brushless motor. In 6-step (trapezoidal) drive, at any instant one leg pulls its phase HIGH, one "
      "pulls its phase LOW, and the third leg is OFF so its phase floats. The rotor position (from Hall sensors) decides which pair is "
      "driven, and the pair changes every 60 electrical degrees: 6 steps per electrical revolution.")

def block(ax):
    ax.set_xlim(0, 10); ax.set_ylim(0, 2.2)
    for x, t, sub in [(0, "4S LiPo + DC link", "15.2 V, 480 $\\mu$F"), (2.6, "3-phase inverter", "6 FETs, 3 legs"),
                      (5.2, "BLDC motor", "wye, trapezoidal EMF"), (7.8, "Rotor + prop", "J, $k\\omega^2$")]:
        ax.add_patch(FancyBboxPatch((x, 0.9), 2.1, 0.95, boxstyle="round,pad=0.02,rounding_size=0.08", fc="#eef4fc", ec=ACCENT, lw=1.2))
        ax.text(x + 1.05, 1.5, t, ha="center", fontsize=9.5, weight="bold", color=INK)
        ax.text(x + 1.05, 1.15, sub, ha="center", fontsize=8, color=INK2)
    for x, lab in [(2.1, "bus"), (4.7, "a, b, c"), (7.3, "torque")]:
        ax.annotate("", (x + 0.5, 1.37), (x, 1.37), arrowprops=dict(arrowstyle="->", color=INK2)); ax.text(x + 0.25, 1.95, lab, ha="center", fontsize=8, color=INK2)
    ax.add_patch(FancyBboxPatch((2.6, 0.05), 4.7, 0.55, boxstyle="round,pad=0.02,rounding_size=0.08", fc="white", ec=INK2, lw=0.8, ls="--"))
    ax.text(4.95, 0.25, "Hall sensors -> sector logic -> 6 gate signals (+ PWM)", ha="center", fontsize=8.5, color=INK2)
    ax.annotate("", (3.6, 0.9), (3.6, 0.6), arrowprops=dict(arrowstyle="->", color=INK2))
    ax.annotate("", (6.3, 0.6), (6.3, 0.9), arrowprops=dict(arrowstyle="->", color=INK2))
doc.figure(block, 1.9)

doc.h("2. The six commutation steps")
doc.p("θe is the electrical angle. Each phase is driven during the 120° where its back-EMF is flat (section 3):")
doc.table(["Sector", "θe range", "HIGH (PWM)", "LOW (on)", "Floating"],
          [["1", "-30° to 30°", "C", "B", "A"], ["2", "30° to 90°", "A", "B", "C"], ["3", "90° to 150°", "A", "C", "B"],
           ["4", "150° to 210°", "B", "C", "A"], ["5", "210° to 270°", "B", "A", "C"], ["6", "270° to 330°", "C", "A", "B"]],
          widths=[0.14, 0.26, 0.2, 0.2, 0.2])

doc.h("3. Motor model")
doc.p("Each phase x ∈ {a, b, c} has a resistance, an inductance and a back-EMF. All three meet at the hidden neutral n:")
doc.eq(r"v_x - v_n = R_{ph}\,i_x + L_{ph}\frac{di_x}{dt} + e_x \qquad e_x = \frac{K_e}{2}\,\omega\;\mathrm{trap}\!\left(\theta_e - k_x\frac{2\pi}{3}\right)")
doc.eq(r"\theta_e = P_p\,\theta_m = %d\,\theta_m \qquad \mathrm{trap}(x) = \mathrm{clamp}\!\left(\frac{6}{\pi}\arcsin(\sin x),\,-1,\,1\right)" % Pp,
       note="arcsin(sin x) is a triangle wave; scaling by 6/pi and clipping at +/-1 leaves a 120-degree flat top")
doc.p("The rotor angle is made in the circuit by integrating speed: a 1 F capacitor charged by a current equal to ω gives V(theta) = θm. "
      "The ideal Hall logic is a comparison: phase x is driven HIGH when sin(θe - kx·2π/3) > 0.5 and LOW when it is < -0.5. "
      "Those are exactly the 120° windows where that phase's EMF is flat.")

doc.h("4. Torque: why 6-step BLDC behaves like a DC motor")
doc.p("Electrical power absorbed by the EMFs becomes mechanical power, so torque follows from a power balance:")
doc.eq(r"T_e\,\omega = \sum_x e_x\,i_x \;\Rightarrow\; T_e = \frac{K_e}{2}\left(f_a i_a + f_b i_b + f_c i_c\right)")
doc.p("In sector 2 (A high, B low) f_a = +1, f_b = -1, i_a = -i_b = I and i_c = 0, so:")
doc.eq(r"T_e = \frac{K_e}{2}(I + I) = K_e\,I \qquad K_e = \frac{60}{2\pi\,KV} = %.2f\ \mathrm{mV\,s/rad}" % (Ke * 1e3))
doc.p("The two driven phases in series form a DC motor with R = 2·Rph = %.2f Ω and L = 2·Lph = %.0f µH, which are the exact values used "
      "in topology 01. That is deliberate, and it exposes the one real difference: 6-step runs about 8 %% slower at the same duty, "
      "because of commutation (section 6)." % (2 * Rph, 2 * Lph * 1e6))

doc.h("5. Timing: why the PWM frequency was raised to 48 kHz")
doc.eq(r"f_e = \frac{P_p\,\mathrm{RPM}}{60} = \frac{%d \cdot %.0f}{60} = %.0f\ \mathrm{Hz} \qquad f_{comm} = 6 f_e = %.1f\ \mathrm{kHz}" % (Pp, op1["rpm"], fe, fcomm / 1e3))
doc.eq(r"\mathrm{PWM\ pulses\ per\ step} = \frac{f_{sw}}{f_{comm}} = \frac{48\ \mathrm{kHz}}{%.1f\ \mathrm{kHz}} = %.1f" % (fcomm / 1e3, Fsw / fcomm))
doc.p("At 24 kHz there would be only about two pulses per step at half throttle, and fewer at full throttle. High-pole-count, high-KV "
      "drone motors need fast PWM just to resolve the commutation steps.")

doc.h("6. Average voltage and operating point for the two PWM modes")
doc.p("Sync = 0 (H_PWM-L_ON): the HIGH phase's top FET is chopped while the LOW phase's bottom FET stays on. During the off time the "
      "current freewheels through the body diode of the HIGH phase's bottom FET, so that terminal sits at -Vf. "
      "Sync = 1 (complementary): the bottom FET is switched on in the off time instead of leaving the diode to conduct, with dead time between.")
doc.eq(r"\mathrm{Sync}=0:\ \ \overline{V}_{LL} = D\,V_{bus} - (1-D)\,V_f - (1+D)\,R_{on} I")
doc.eq(r"\mathrm{Sync}=1:\ \ \overline{V}_{LL} = D\,V_{bus} - 2R_{on} I")
doc.eq(r"V_f = N V_T \ln\frac{I}{I_S} + I R_b = %.2f\ \mathrm{V} \qquad R_{on} = R_d + R_s + \frac{1}{K_p(V_{GS}-V_{to})} = %.1f\ \mathrm{m\Omega}" % (op1["Vf"], Ron * 1e3),
       note="body-diode and on-resistance values computed from the VDMOS model parameters in the schematic")
doc.p("One more voltage is lost at every commutation. The incoming phase's current must build up from zero in its inductance, and those "
      "volt-seconds never reach the back-EMF. This is the same commutation-overlap drop found in 6-pulse rectifiers, and it grows with "
      "speed and current:")
doc.eq(r"\Delta V_{comm} \approx f_{comm}\,L_{ph}\,I = %.1f\ \mathrm{kHz} \cdot 7.5\,\mu\mathrm{H} \cdot %.2f\ \mathrm{A} = %.2f\ \mathrm{V}" % (fcomm / 1e3, op1["I"], op1["Vcomm"]))
doc.p("Setting the average line voltage, minus these drops, equal to 2·Rph·I + Ke·ω and using I = (kω² + bω)/Ke gives the same quadratic as topology 01:")
doc.eq(r"\frac{R\,k}{K_e}\omega^2 + \left(\frac{R\,b}{K_e} + K_e\right)\omega - \overline{V}' = 0 \qquad (R = 2R_{ph} + R_{FET},\ \ \overline{V}' = \overline{V}_{LL,0} - \Delta V_{comm})")
doc.eq(r"\mathrm{Sync}=0:\ \ \omega = %.0f\ \mathrm{rad/s}\ \ (%.0f\ \mathrm{RPM}),\ \ I = %.2f\ \mathrm{A}" % (op0["w"], op0["rpm"], op0["I"]), size=12)
doc.eq(r"\mathrm{Sync}=1:\ \ \omega = %.0f\ \mathrm{rad/s}\ \ (%.0f\ \mathrm{RPM}),\ \ I = %.2f\ \mathrm{A}" % (op1["w"], op1["rpm"], op1["I"]), size=12)

doc.h("7. Losses")
doc.p("Two phases carry I at a time, and each phase conducts 2/3 of the time:")
doc.eq(r"I_{ph,rms} = I\sqrt{2/3} \qquad P_{cu} = 3R_{ph}I_{ph,rms}^2 = 2R_{ph}\left(I^2 + \frac{\Delta I^2}{12}\right) \qquad \Delta I = \frac{(V_{bus} - RI - K_e\omega)\,D}{2L_{ph}\,f_{sw}}")
doc.eq(r"\mathrm{Sync}=0:\ \ P_{diode} = V_f\,I\,(1-D) = %.2f \cdot %.2f \cdot %.1f = %.2f\ \mathrm{W}" % (op0["Vf"], op0["I"], 1 - D, op0["Vf"] * op0["I"] * (1 - D)))
doc.eq(r"\mathrm{Sync}=1:\ \ P_{FET,off} = I^2 R_{on}(1-D) = %.3f\ \mathrm{W} \quad + \quad P_{dead} = 2V_f I\,T_{dead} f_{sw} = %.3f\ \mathrm{W}" % (op1["I"] ** 2 * Ron * (1 - D), 2 * op1["Vf"] * op1["I"] * Tdead * Fsw), size=11)
doc.p("A diode drops about 0.8 V no matter how big it is, while a FET drops only I·Ron = %.0f mV at this current. Switching the FET on "
      "instead of letting the diode conduct (synchronous rectification) is the single biggest efficiency step in a modern ESC." % (op1["I"] * Ron * 1e3))

doc.h("8. Commutation torque ripple")
doc.p("At each step change, current must move from the outgoing phase to the incoming one through the phase inductances. The outgoing "
      "phase floats, and its current is forced through a body diode to a bus rail, which makes it fall quickly. The incoming phase rises "
      "only as fast as the available voltage margin (D·Vbus minus back-EMF) allows. While the two rates differ, the current in the "
      "always-on phase sags, and so does torque (T = Ke·I). That creates the 6-per-electrical-rev torque dips in panel E. Sinusoidal "
      "drive and FOC (a later topology) remove them.")
import json
tr = json.load(open(os.path.join(here, "torque_ripple.json")))
doc.p("Two kinds of ripple are present in panel E. The fast one is PWM current ripple (ΔI·Ke), and it is too fast for the rotor and prop "
      "to follow. The slow one, visible after averaging over each PWM period, is the commutation dip:")
doc.eq(r"\mathrm{raw:}\ \Delta T_{pp} = %.0f\ \mathrm{mN\,m} \quad \mathrm{commutation\ (PWM\ avg):}\ \Delta T_{pp} = %.0f\ \mathrm{mN\,m}\ \mathrm{on}\ T_{avg} = %.0f\ \mathrm{mN\,m}"
       % (tr["te_raw_pp"] * 1e3, tr["te_avg_filt_pp"] * 1e3, tr["te_avg_filt_mean"] * 1e3), size=11)

doc.h("9. Hand calculation vs. LTspice")
rows = []
for lab, h0, h1, k, fmt in [("Speed (RPM)", op0["rpm"], op1["rpm"], "rpm_final", "{:,.0f}"),
                            ("Battery current (A)", op0["Ibat"], op1["Ibat"], "ibat_avg", "{:.2f}"),
                            ("Phase current RMS (A)", op0["Iph_rms"], op1["Iph_rms"], "iph_rms", "{:.2f}"),
                            ("Copper loss (W)", op0["Pcu"], op1["Pcu"], "pcu", "{:.2f}"),
                            ("High-side FET loss (W)", op0["Phi"], op1["Phi"], "pfet_hi", "{:.2f}"),
                            ("Low-side FET + diode (W)", op0["Plo"], op1["Plo"], "pfet_lo", "{:.2f}"),
                            ("Input power (W)", op0["Pin"], op1["Pin"], "pin", "{:.1f}"),
                            ("Efficiency (%)", op0["Pm"] / op0["Pin"] * 100, op1["Pm"] / op1["Pin"] * 100, "efficiency", "{:.1f}")]:
    sim0, sim1 = s(k, 0), s(k, 1)
    if k == "efficiency": sim0, sim1 = sim0 * 100, sim1 * 100
    rows.append([lab, fmt.format(h0), fmt.format(sim0), fmt.format(h1), fmt.format(sim1)])
doc.table(["Quantity", "Sync=0 hand", "Sync=0 sim", "Sync=1 hand", "Sync=1 sim"], rows, widths=[0.32, 0.17, 0.17, 0.17, 0.17])
doc.p("The hand model has no switching losses and treats commutation as a simple voltage drop, so expect agreement within several "
      "percent, not exact. Without the commutation term the hand model predicts %.0f RPM for Sync=1, %.0f %% too fast: the comparison is "
      "what revealed that commutation matters. Peak phase current at start-up was %.0f A, set by the 30 ms throttle ramp as in topology 01." % (op1_nc["rpm"], (op1_nc["rpm"] / s("rpm_final", 1) - 1) * 100, s("iph_peak", 1)))

doc.h("10. Simulated waveforms")
doc.img(os.path.join(here, "ThreePhase_ESC_BLDC_results.png"), width=6.7)

doc.h("11. Key takeaways")
doc.bullets([
    "A 3-phase ESC is three half-bridge legs. In 6-step drive only two phases conduct, so the motor acts like the DC motor of topology 01.",
    "Commutation is a lookup from rotor position (Hall sensors) to one of six FET states, changing every 60 electrical degrees.",
    "Pole pairs multiply the electrical frequency: a 7-pole-pair motor at 14.5k RPM commutates at about 10 kHz, so the PWM must be much faster.",
    "Letting body diodes freewheel wastes about Vf·I·(1-D). Complementary (synchronous) PWM removes most of it.",
    "6-step drive has inherent torque dips at each commutation. That is the motivation for sinusoidal and FOC drives.",
])
out = os.path.join(here, "02_Three-Phase_ESC_BLDC_6-Step_Design.pdf")
print(out, doc.save(out), "pages")

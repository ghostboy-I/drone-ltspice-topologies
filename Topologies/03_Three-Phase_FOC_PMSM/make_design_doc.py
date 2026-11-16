"""Builds 03_Three-Phase_FOC_PMSM_Design.pdf: hand calculations + LTspice results for topology 03 (sensored FOC)."""
import os, sys, math, json
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, "..", "tools"))
from designdoc import Doc, INK, INK2, ACCENT
from ltraw import read_meas
from matplotlib.patches import FancyBboxPatch

# ---------------- design parameters (same as the .asc) ----------------
Vbatt, Rbatt, Rwire = 15.2, 20e-3, 2e-3
Fsw, Tdead = 48e3, 100e-9
KV, Pp, Rph, Lph = 2300, 7, 50e-3, 7.5e-6
J, kprop, bfric = 5e-6, 1.15e-8, 1e-6
Vdrv, Vto, Kp_fet, Rds_ext = 10, 1.8, 120, 3e-3
Is_d, N_d, Rb_d, Vt = 5e-12, 1.05, 4e-3, 0.02585
RPMref, Fci, Fcw, Idstep = 14000, 3e3, 30, 5.0

Ke = 60 / (2 * math.pi * KV)                 # line-line peak EMF constant (V s/rad), same KV as topology 02
Kph = Ke / math.sqrt(3)                      # phase peak EMF constant
Kt = 1.5 * Kph                               # torque constant on iq (amplitude-invariant Park)
Ron = Rds_ext + 1 / (Kp_fet * (Vdrv - Vto))
vf = lambda i: N_d * Vt * math.log(i / Is_d) + i * Rb_d

# ---------------- controller tuning ----------------
wci = 2 * math.pi * Fci; Kpi, Kii, tau_i = Lph * wci, Rph * wci, 1 / wci
wcw = 2 * math.pi * Fcw; Kpw = J * wcw / Kt; Kiw = Kpw * wcw / 4

# ---------------- operating point (speed is set by the loop, so everything follows from the load) ----------------
w = RPMref * 2 * math.pi / 60; we = Pp * w; fe = we / (2 * math.pi)
T = kprop * w * w + bfric * w
iq = T / Kt; Irms = iq / math.sqrt(2); Iabs = 2 / math.pi * iq
vq = Rph * iq + Kph * w; vd = -we * Lph * iq; vmag = math.hypot(vd, vq)
Pm = T * w; Pcu = 1.5 * Rph * iq ** 2
Vf = vf(Iabs)
Pcond = 3 * Ron * Irms ** 2                  # one FET of every leg always carries the phase current
Pdead = 3 * 2 * Tdead * Fsw * Vf * Iabs      # body diode conducts during the two dead times of each period
Pin = Pm + Pcu + Pcond + Pdead
Vbus = Vbatt
for _ in range(20):
    Ibat = Pin / Vbus; Vbus = Vbatt - Ibat * (Rbatt + Rwire)
dV_dead = 4 / math.pi * Tdead * Fsw * Vbus; vq_real = vq + Ron * iq + dV_dead
Vmax_svm, Vmax_spwm = Vbus / math.sqrt(3), Vbus / 2
rpm_max = lambda V: V / Kph * 60 / (2 * math.pi)

sim = {k: v[0] for k, v in read_meas(os.path.join(here, "ThreePhase_FOC.log")).items()}
s02 = read_meas(os.path.join(here, "..", "02_Three-Phase_ESC_BLDC_6-Step", "ThreePhase_ESC_BLDC.log"))
tr = json.load(open(os.path.join(here, "torque_ripple.json")))
tr02 = json.load(open(os.path.join(here, "..", "02_Three-Phase_ESC_BLDC_6-Step", "torque_ripple.json")))

doc = Doc("03  Three-Phase FOC Drive (PMSM)",
          "Sensored FOC with SVPWM  |  4S LiPo, 48 kHz PWM, 2300KV 7-pole-pair motor, 5 in prop, speed loop at 14,000 RPM")

doc.h("1. What the circuit is")
doc.p("The power stage is the same three-leg inverter as topology 02, but now every leg switches all the time with complementary PWM, "
      "and all three phases carry current at once. The motor has sinusoidal back-EMF (a PMSM, which most drone motors are close to). "
      "A controller measures two phase currents and the rotor angle, and shapes the three phase voltages so the currents are sine waves "
      "locked to the rotor. That is field-oriented control (FOC).")

def block(ax):
    ax.set_xlim(0, 10); ax.set_ylim(0, 2.4)
    for x, t, sub in [(0, "4S LiPo + DC link", "15.2 V, 480 $\\mu$F"), (2.6, "3-phase inverter", "6 FETs, all switching"),
                      (5.2, "PMSM", "sinusoidal EMF"), (7.8, "Rotor + prop", "J, $k\\omega^2$")]:
        ax.add_patch(FancyBboxPatch((x, 1.25), 2.1, 0.95, boxstyle="round,pad=0.02,rounding_size=0.08", fc="#eef4fc", ec=ACCENT, lw=1.2))
        ax.text(x + 1.05, 1.85, t, ha="center", fontsize=9.5, weight="bold", color=INK)
        ax.text(x + 1.05, 1.5, sub, ha="center", fontsize=8, color=INK2)
    for x in (2.1, 4.7, 7.3):
        ax.annotate("", (x + 0.5, 1.72), (x, 1.72), arrowprops=dict(arrowstyle="->", color=INK2))
    ax.add_patch(FancyBboxPatch((0.4, 0.05), 9.2, 0.8, boxstyle="round,pad=0.02,rounding_size=0.08", fc="white", ec=INK2, lw=0.8, ls="--"))
    ax.text(5.0, 0.55, "speed PI -> iq*  |  Clarke + Park (ia, ib, θe) -> id, iq  |  two current PIs + decoupling -> vd, vq", ha="center", fontsize=8.3, color=INK2)
    ax.text(5.0, 0.22, "inverse Park + Clarke -> va, vb, vc  |  SVPWM offset  |  duty = 0.5 + (vx - voff)/Vbus  ->  6 gates", ha="center", fontsize=8.3, color=INK2)
    ax.annotate("", (3.65, 1.25), (3.65, 0.85), arrowprops=dict(arrowstyle="->", color=INK2))
    ax.annotate("", (6.25, 0.85), (6.25, 1.25), arrowprops=dict(arrowstyle="->", color=INK2)); ax.text(6.35, 1.0, "ia, ib", fontsize=8, color=INK2)
    ax.annotate("", (8.85, 0.85), (8.85, 1.25), arrowprops=dict(arrowstyle="->", color=INK2)); ax.text(8.95, 1.0, "θm (encoder)", fontsize=8, color=INK2)
doc.figure(block, 2.2)

doc.h("2. Why sinusoidal currents give smooth torque")
doc.p("Torque comes from the power balance Te·ω = Σ ex·ix. With sinusoidal back-EMF and sinusoidal currents in phase with it:")
doc.eq(r"e_x = E\sin(\theta_e - k_x 120^\circ),\ \ i_x = I\sin(\theta_e - k_x 120^\circ) \;\Rightarrow\; \sum_x e_x i_x = E I \sum_x \sin^2(\cdot) = \frac{3}{2}E I", size=12)
doc.p("The sum of three sin² terms 120° apart is exactly 3/2 at every angle, so torque has no ripple at all. In 6-step drive the "
      "current jumps between phases every 60°, and torque dips at each jump (topology 02, %.0f mN·m p-p)." % (tr02["te_avg_filt_pp"] * 1e3))

doc.h("3. Motor model")
doc.p("For a fair comparison the motor keeps topology 02's R, L, pole pairs and KV. The KV sets the peak line-to-line EMF to Ke·ω, so the phase EMF constant is Ke/√3:")
doc.eq(r"v_x - v_n = R_{ph}i_x + L_{ph}\frac{di_x}{dt} + e_x \qquad e_x = -K_{ph}\,\omega\,\sin(\theta_e - k_x 120^\circ)")
doc.eq(r"K_{ph} = \frac{K_e}{\sqrt{3}} = \frac{%.3f}{\sqrt{3}} = %.3f\ \mathrm{mV\,s/rad}" % (Ke * 1e3, Kph * 1e3),
       note="the minus sign puts the back-EMF on the +q axis of the Park transform below")

doc.h("4. Clarke and Park: turning three AC currents into two DC numbers")
doc.p("Clarke maps the three phase quantities (which sum to zero) onto two orthogonal axes α, β fixed to the stator. "
      "Park then rotates those axes with the rotor by θe. In the rotor frame the sine waves stand still and become DC:")
doc.eq(r"i_\alpha = i_a \qquad i_\beta = \frac{i_a + 2 i_b}{\sqrt{3}}", note="Clarke (amplitude-invariant): only two current sensors needed, since ic = -ia - ib")
doc.eq(r"i_d = i_\alpha\cos\theta_e + i_\beta\sin\theta_e \qquad i_q = -i_\alpha\sin\theta_e + i_\beta\cos\theta_e", note="Park")
doc.p("id is the current aligned with the magnet flux: it makes no torque, only weakens or strengthens the field. iq is 90° ahead of it "
      "and produces all of the torque. Writing the motor equations in this frame:")
doc.eq(r"v_d = R i_d + L\frac{di_d}{dt} - \omega_e L\, i_q \qquad v_q = R i_q + L\frac{di_q}{dt} + \omega_e L\, i_d + \omega_e\psi", size=12)
doc.eq(r"T_e = \frac{3}{2}K_{ph}\,i_q = K_t\,i_q \qquad K_t = %.3f\ \mathrm{mN\,m/A} \qquad \omega_e\psi = K_{ph}\,\omega" % (Kt * 1e3), size=12)
doc.p("The terms ωe·L·iq and ωe·L·id couple the two axes, and ωe·ψ is the back-EMF. The controller cancels all three by feed-forward "
      "(decoupling), so each axis looks like a plain R-L circuit to its PI controller.")

doc.h("5. Current loops: PI tuning by pole-zero cancellation")
doc.p("Each axis plant is 1/(R + sL), a single pole at R/L. Put the PI zero on top of it and the open loop becomes a pure integrator:")
doc.eq(r"C(s)\,P(s) = \left(K_p + \frac{K_i}{s}\right)\frac{1}{R+sL} = \frac{K_p}{L}\cdot\frac{s + K_i/K_p}{s\,(s + R/L)}", size=12)
doc.eq(r"\mathrm{choose}\ \ \frac{K_i}{K_p} = \frac{R}{L}\ \ \Rightarrow\ \ C(s)P(s) = \frac{\omega_c}{s} \qquad \omega_c = \frac{K_p}{L}", size=12)
doc.eq(r"K_p = L\,\omega_c = %.3f\ \mathrm{V/A} \qquad K_i = R\,\omega_c = %.0f\ \mathrm{V/(A\,s)} \qquad \omega_c = 2\pi\cdot %.0f\ \mathrm{kHz}" % (Kpi, Kii, Fci / 1e3), size=12)
doc.p("The closed loop is then first order, ωc/(s + ωc): a step in id* reaches 63 %% of its final value in τ = 1/ωc = %.0f µs. "
      "Panel F tests exactly that. 3 kHz is about 1/16 of the PWM frequency; a digital controller with its sampling delay "
      "would normally stop near 1/10 to 1/20." % (tau_i * 1e6))
doc.p("A check worth doing: the current ripple fed back through Kp must not make the duty signal slope faster than the PWM carrier, or the "
      "comparator chatters. Carrier slope = 2·Vbus·fsw ≈ 1.5 V/µs; ripple feedback ≈ Kp·(2/3)Vbus/L ≈ 0.19 V/µs. Safe by about 8×.")

doc.h("6. Speed loop")
doc.p("The speed PI sets iq*. Its plant is the rotor inertia, ω = Kt·iq/(J s). With crossover ωs and the PI zero 4× lower:")
doc.eq(r"K_{p\omega} = \frac{J\,\omega_s}{K_t} = %.3f\ \frac{\mathrm{A}}{\mathrm{rad/s}} \qquad K_{i\omega} = K_{p\omega}\frac{\omega_s}{4} = %.1f \qquad \omega_s = 2\pi\cdot %d\ \mathrm{Hz}" % (Kpw, Kiw, Fcw), size=12)
doc.p("The speed loop is 100× slower than the current loops, so it treats them as instantaneous. This cascade (fast inner current, slow "
      "outer speed) is the standard structure. iq* is clamped at ±30 A, which is also the drive's current limit. The speed command "
      "ramps to %s RPM over 120 ms, so the acceleration torque J·dω/dt stays inside that limit." % f"{RPMref:,}")

doc.h("7. SVPWM: 15 % more voltage for free")
doc.p("Plain sine PWM gives duty = 0.5 + vx/Vbus, so a phase can swing only ±Vbus/2. But the motor neutral floats: adding the same "
      "offset to all three phases changes no line-to-line voltage. Subtracting the midpoint of the largest and smallest phase "
      "(min-max injection) centres the three references and is equivalent to space-vector PWM:")
doc.eq(r"v_{off} = \frac{\max(v_a,v_b,v_c) + \min(v_a,v_b,v_c)}{2} \qquad d_x = \frac{1}{2} + \frac{v_x - v_{off}}{V_{bus}}")
doc.eq(r"\hat V_{max}:\ \ \mathrm{sine\ PWM}\ \frac{V_{bus}}{2} = %.2f\ \mathrm{V} \quad \mathrm{SVPWM}\ \frac{V_{bus}}{\sqrt{3}} = %.2f\ \mathrm{V}\ \ (+15.5\%%)" % (Vmax_spwm, Vmax_svm), size=12)
doc.p("At no load that is the difference between %s and %s RPM of top speed (ω = V̂/Kph). The SVPWM limit is exactly KV × Vbus, "
      "which is what the KV rating promises. Panel D shows the resulting saddle-shaped duty." % (f"{rpm_max(Vmax_spwm):,.0f}", f"{rpm_max(Vmax_svm):,.0f}"))

doc.h("8. Operating point at 14,000 RPM")
doc.eq(r"\omega = %.0f\ \mathrm{rad/s} \qquad \omega_e = P_p\omega = %.0f\ \mathrm{rad/s}\ \ (f_e = %.0f\ \mathrm{Hz})" % (w, we, fe), size=12)
doc.eq(r"T = k\omega^2 + b\omega = %.2f\ \mathrm{mN\,m}" % (T * 1e3), size=12)
doc.eq(r"i_q = \frac{T}{K_t} = %.2f\ \mathrm{A} \qquad I_{ph,rms} = \frac{i_q}{\sqrt{2}} = %.2f\ \mathrm{A} \qquad i_d = 0" % (iq, Irms), size=12)
doc.eq(r"v_q = R i_q + K_{ph}\omega = %.3f + %.3f = %.2f\ \mathrm{V} \qquad v_d = -\omega_e L i_q = %.2f\ \mathrm{V}" % (Rph * iq, Kph * w, vq, vd), size=12)
doc.eq(r"|v| = \sqrt{v_d^2 + v_q^2} = %.2f\ \mathrm{V} \;\Rightarrow\; %.0f\%%\ \mathrm{of\ the\ SVPWM\ limit}" % (vmag, vmag / Vmax_svm * 100), size=12)
doc.p("Note vd is negative even with id = 0: the voltage leads the current by atan(%.2f/%.2f) = %.1f° to push current through the "
      "inductance at %.0f Hz. The decoupling feed-forward supplies exactly this." % (-vd, vq, math.degrees(math.atan2(-vd, vq)), fe))

doc.h("9. Losses")
doc.eq(r"P_{cu} = 3R_{ph}I_{ph,rms}^2 = \frac{3}{2}R_{ph}\,i_q^2 = %.2f\ \mathrm{W}" % Pcu, size=12)
doc.eq(r"P_{cond} = 3R_{on}I_{ph,rms}^2 = %.2f\ \mathrm{W} \qquad P_{dead} = 3\cdot 2T_{dead}f_{sw}\,V_f\,\overline{|i|} = %.2f\ \mathrm{W}" % (Pcond, Pdead), size=12)
doc.p("With complementary PWM one FET of every leg is always conducting the phase current, so conduction loss is 3·Ron·I²rms "
      "(Ron = %.1f mΩ), split between the high and low FET by the duty. The body diode carries current only in the dead times "
      "(Vf = %.2f V, mean |i| = %.2f A). Switching loss is not in the hand model; the simulation includes it." % (Ron * 1e3, Vf, Iabs))
doc.p("Copper loss for the same torque is the same as ideal 6-step: 6-step needs I = T/Ke in two phases for 2/3 of the time, giving "
      "2R·(T/Ke)² = %.2f W; FOC gives (3/2)R·(T/Kt)² = %.2f W. The FOC advantage is smoothness, not copper efficiency." % (2 * Rph * (T / Ke) ** 2, Pcu))

doc.h("10. Hand calculation vs. LTspice")
rows = []
for lab, h, k, fmt, sc in [("Speed (RPM)", RPMref, "rpm_final", "{:,.0f}", 1), ("Torque (mN·m)", T * 1e3, "te_avg", "{:.2f}", 1e3),
                           ("iq (A)", iq, "iq_avg", "{:.2f}", 1), ("id (A)", 0.0, "id_avg", "{:.3f}", 1),
                           ("Phase current RMS (A)", Irms, "iph_rms", "{:.2f}", 1), ("vq (V)", vq, "vq_avg", "{:.2f}", 1),
                           ("vq incl. FET + dead time (V)", vq_real, "vq_avg", "{:.2f}", 1), ("vd (V)", vd, "vd_avg", "{:.2f}", 1), ("Copper loss (W)", Pcu, "pcu", "{:.2f}", 1),
                           ("FET loss, no switching (W)", Pcond + Pdead, None, "{:.2f}", 1), ("Mechanical power (W)", Pm, "pmech", "{:.1f}", 1),
                           ("Input power (W)", Pin, "pin", "{:.1f}", 1), ("Battery current (A)", Ibat, "ibat_avg", "{:.2f}", 1),
                           ("Efficiency (%)", Pm / Pin * 100, "efficiency", "{:.1f}", 100),
                           ("id step: time to 63 % (µs)", tau_i * 1e6, "t63", "{:.1f}", 1e6)]:
    sv = tr["t63_id_step"] * sc if k == "t63" else sim["pfet_hi"] + sim["pfet_lo"] if k is None else sim[k] * sc
    err = "" if abs(h) < 1e-9 else f"{(sv / h - 1) * 100:+.1f} %"
    rows.append([lab, fmt.format(h), fmt.format(sv), err])
doc.table(["Quantity", "Hand calc", "LTspice", "Difference"], rows, widths=[0.4, 0.2, 0.2, 0.2])
doc.p("FET loss is where the hand model and simulation differ most: the hand model has no switching loss, and the gap (%.2f W) is the "
      "switching loss of six FETs at 48 kHz. Most other numbers are set by the load and the controller, so they land close." % (sim["pfet_hi"] + sim["pfet_lo"] - Pcond - Pdead))
doc.p("vq is %.1f %% above the ideal value because the inverter is not ideal. The PI integrator quietly adds what is missing: the FET drop "
      "Ron·iq = %.0f mV and the dead-time error. During each dead time the phase voltage is set by the current direction, not the gate "
      "command, which costs a square wave of volt-seconds in phase with the current; its fundamental is (4/π)·Tdead·fsw·Vbus = %.0f mV. "
      "Adding both gives %.2f V against %.2f V simulated. The id step is %.0f %% slower than 1/ωc for the same reason: the tuning "
      "assumed R = Rph, but the real loop also sees Ron and the dead-time effect. The PWM ripple on id is ±1.5 A, so the step is read "
      "from the PWM-averaged trace (panel F); real ESCs sample the current at the carrier peak, where the ripple crosses its average." %
      ((sim["vq_avg"] / vq - 1) * 100, Ron * iq * 1e3, dV_dead * 1e3, vq_real, sim["vq_avg"], (tr["t63_id_step"] / tau_i - 1) * 100))

doc.h("11. FOC vs. 6-step at about the same speed")
e02 = lambda k: s02[k][1]
doc.table(["Quantity", "02 6-step (Sync=1)", "03 FOC"],
          [["Speed (RPM)", f"{e02('rpm_final'):,.0f}", f"{sim['rpm_final']:,.0f}"],
           ["Torque, PWM-averaged p-p (mN·m)", f"{tr02['te_avg_filt_pp']*1e3:.1f}", f"{tr['te_avg_filt_pp']*1e3:.1f}"],
           ["Torque, raw p-p incl. PWM ripple (mN·m)", f"{tr02['te_raw_pp']*1e3:.1f}", f"{tr['te_raw_pp']*1e3:.1f}"],
           ["Phase current RMS (A)", f"{e02('iph_rms'):.2f}", f"{sim['iph_rms']:.2f}"],
           ["Copper loss (W)", f"{e02('pcu'):.2f}", f"{sim['pcu']:.2f}"],
           ["FET loss (W)", f"{e02('pfet_hi')+e02('pfet_lo'):.2f}", f"{sim['pfet_hi']+sim['pfet_lo']:.2f}"],
           ["Efficiency (%)", f"{e02('efficiency')*100:.1f}", f"{sim['efficiency']*100:.1f}"]],
          widths=[0.5, 0.25, 0.25])
doc.p("The 6-step run was at a fixed 50 %% duty and settled at %s RPM, slightly faster than 14,000, so its powers are a little higher. "
      "FOC is still %.1f points more efficient: partly the lighter load, partly the commutation transients of 6-step (current "
      "spikes and diode conduction) that FOC never has. The clear win for FOC is the torque: the slow commutation dips are gone, "
      "which means less vibration, less acoustic noise and less stress on the frame and IMU." % (f"{e02('rpm_final'):,.0f}", (sim["efficiency"] - e02("efficiency")) * 100))

doc.h("12. Simulated waveforms")
doc.img(os.path.join(here, "ThreePhase_FOC_results.png"), width=6.6)

doc.h("13. Key takeaways")
doc.bullets([
    "Sinusoidal EMF times sinusoidal current in phase gives constant power, and so constant torque, at every rotor angle.",
    "Clarke + Park turn three AC phase currents into two DC numbers: id (flux) and iq (torque). Plain PI loops can then regulate DC.",
    "Tune each current PI by cancelling the R-L pole: Kp = L·ωc, Ki = R·ωc. The loop becomes first order with τ = 1/ωc.",
    "Decoupling feed-forward removes the ωe·L cross terms and the back-EMF, so the PIs only correct small errors.",
    "Min-max injection (SVPWM) uses the floating neutral to get Vbus/√3 instead of Vbus/2: 15.5 % more speed or headroom.",
    "This model uses an ideal encoder. Real drone ESCs are sensorless: they estimate θe from the back-EMF with an observer.",
])
out = os.path.join(here, "03_Three-Phase_FOC_PMSM_Design.pdf")
print(out, doc.save(out), "pages")

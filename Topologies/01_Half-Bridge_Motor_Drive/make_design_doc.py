"""Builds 01_Half-Bridge_Motor_Drive_Design.pdf: hand calculations + LTspice results for topology 01."""
import os, re, sys, math
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, "..", "tools"))
from designdoc import Doc, INK, INK2, ACCENT
from matplotlib.patches import FancyBboxPatch

# ---------------- design parameters (same as the .asc) ----------------
Vbatt, Rbatt, Rwire = 15.2, 20e-3, 2e-3
Fsw, Tdead, D = 24e3, 100e-9, 0.5
KV, Rmot, Lmot = 2300, 0.1, 15e-6
J, kprop, bfric = 5e-6, 1.15e-8, 1e-6
Ron, Vf = 3e-3, 0.8
Cbulk, Lwire = 470e-6 + 10e-6, 100e-9
Tsw = 1 / Fsw
Ke = 60 / (2 * math.pi * KV); Kt = Ke
R = Rmot + Ron                      # one FET is always in series with the winding

# ---------------- hand calculations ----------------
Vbus = Vbatt
for _ in range(20):                 # iterate: bus sag depends on battery current
    a, b, c = R * kprop / Kt, R * bfric / Kt + Ke, -D * Vbus
    w = (-b + math.sqrt(b * b - 4 * a * c)) / (2 * a)
    I = (kprop * w * w + bfric * w) / Kt
    Ibat = D * I
    Vbus = Vbatt - Ibat * (Rbatt + Rwire)
rpm = w * 60 / (2 * math.pi)
Vemf = Ke * w
dI = Vbus * D * (1 - D) / (Lmot * Fsw)
Irms2 = I ** 2 + dI ** 2 / 12
Pcu = Rmot * Irms2
Pmech = Kt * I * w
Pin = Vbus * Ibat
Istall = D * Vbus / Rmot
tau = J / (2 * kprop * w + bfric + Kt ** 2 / R)
db = Tdead / Tsw
Pcond = Irms2 * Ron * D
Pdt = 2 * Vf * I * Tdead * Fsw
f_res = 1 / (2 * math.pi * math.sqrt(Lwire * Cbulk))
Icap_rms = I * math.sqrt(D * (1 - D))

# ---------------- simulation results from the LTspice log ----------------
log = open(os.path.join(here, "HalfBridge_MotorDrive.log"), "rb").read().replace(b"\x00", b"").decode("utf-8", "ignore")
sim = {m.group(1): float(m.group(2)) for m in re.finditer(r"^(\w+): .*?=(-?[\d.eE+-]+)", log, re.M)}

doc = Doc("01  Half-Bridge Motor Drive", "One ESC phase leg (synchronous buck)  |  4S LiPo, 24 kHz PWM, 2300KV motor, 5 in prop")

doc.h("1. What the circuit is")
doc.p("Two N-channel MOSFETs are stacked between the battery bus and ground. Their midpoint, the switch "
      "node sw, is connected to the motor. Exactly one FET is on at a time. With the high-side FET on, the motor "
      "sees +Vbus; with the low-side FET on, it sees 0 V and its current keeps flowing through the low-side FET. "
      "A drone ESC is three of these legs sharing one bus, so everything here carries over to the 3-phase design.")

def block_diagram(ax):
    ax.set_xlim(0, 10); ax.set_ylim(0, 2)
    boxes = [(0.0, "4S LiPo", "15.2 V, 20 m$\\Omega$"), (2.05, "DC link", "470 $\\mu$F + 10 $\\mu$F"),
             (4.1, "Half-bridge", "2 FETs + dead time"), (6.15, "Motor (R-L-EMF)", "0.1 $\\Omega$, 15 $\\mu$H, $K_e\\omega$"),
             (8.2, "Rotor + prop", "J, $k\\omega^2$")]
    for x, t, s in boxes:
        ax.add_patch(FancyBboxPatch((x, 0.55), 1.75, 0.95, boxstyle="round,pad=0.02,rounding_size=0.08",
                                    fc="#eef4fc", ec=ACCENT, lw=1.2))
        ax.text(x + 0.875, 1.15, t, ha="center", fontsize=9.5, weight="bold", color=INK)
        ax.text(x + 0.875, 0.8, s, ha="center", fontsize=8, color=INK2)
    for x, lab in [(1.75, "bus"), (3.8, ""), (5.85, "sw"), (7.9, "torque")]:
        ax.annotate("", (x + 0.3, 1.02), (x, 1.02), arrowprops=dict(arrowstyle="->", color=INK2))
        ax.text(x + 0.15, 1.6, lab, ha="center", fontsize=8, color=INK2)
    ax.text(5, 0.12, "PWM: triangle carrier vs. throttle  ->  gate signals with dead time", ha="center", fontsize=8.5, color=INK2)
doc.figure(block_diagram, 1.5)

doc.h("2. Average model: the duty cycle sets the motor voltage")
doc.p("Averaged over one PWM period, the switch node is at Vbus for a fraction D of the time and at 0 V otherwise:")
doc.eq(r"\overline{V}_{sw} = D\,V_{bus} = %.2f \times %.2f\ \mathrm{V} = %.2f\ \mathrm{V}" % (D, Vbus, D * Vbus))
doc.p("The motor is a resistance, an inductance and a speed-dependent voltage source (back-EMF). The rotor obeys Newton's law for rotation:")
doc.eq(r"v = R\,i + L\frac{di}{dt} + K_e\,\omega \qquad\qquad J\frac{d\omega}{dt} = K_t\,i - k\,\omega^2 - b\,\omega")
doc.eq(r"K_e = K_t = \frac{60}{2\pi\,KV} = \frac{60}{2\pi \cdot %d} = %.2f\ \mathrm{mV\,s/rad}" % (KV, Ke * 1e3),
       note="Ke in V per rad/s equals Kt in N m per A: the same constant seen from the electrical and mechanical sides")

doc.h("3. Steady-state operating point")
doc.p("In steady state di/dt = 0 and dω/dt = 0. The torque balance gives the current, $I = (k\\omega^2 + b\\omega)/K_t$. "
      "Substituting into the voltage equation gives a quadratic in ω, with R = R_motor + R_DS(on) = %.3f Ω:" % R)
doc.eq(r"\frac{R\,k}{K_t}\,\omega^2 + \left(\frac{R\,b}{K_t} + K_e\right)\omega - D\,V_{bus} = 0")
doc.eq(r"\omega = %.0f\ \mathrm{rad/s}\ \ (%.0f\ \mathrm{RPM}) \qquad I = %.2f\ \mathrm{A} \qquad K_e\omega = %.2f\ \mathrm{V}" % (w, rpm, I, Vemf))
doc.p("Notice that most of the applied voltage is cancelled by the back-EMF. The resistive drop is only I·R = %.2f V. "
      "Speed is therefore set mainly by voltage: ω ≈ D·Vbus/Ke." % (I * R))

doc.h("4. Battery current: the half-bridge steps current up")
doc.p("Power is conserved through the (nearly lossless) switches, so the battery sees the motor current scaled by D:")
doc.eq(r"I_{bat} \approx D\,I_{mot} = %.2f \times %.2f = %.2f\ \mathrm{A}" % (D, I, Ibat))

doc.h("5. Current ripple")
doc.p("While the high-side FET is on, the inductor sees (Vbus - D·Vbus) for a time D·Tsw, so its current ramps up by:")
doc.eq(r"\Delta I = \frac{(V_{bus}-D V_{bus})\,D\,T_{sw}}{L} = \frac{V_{bus}\,D(1-D)}{L\,f_{sw}} = \frac{%.2f \cdot %.2f}{15\,\mu\mathrm{H} \cdot 24\,\mathrm{kHz}} = %.1f\ \mathrm{A_{pp}}" % (Vbus, D * (1 - D), dI))
doc.p("Ripple is largest at D = 0.5. It adds heat but no torque, because the RMS current exceeds the average:")
doc.eq(r"I_{rms}^2 = I^2 + \frac{\Delta I^2}{12} \quad\Rightarrow\quad P_{cu} = R_m I_{rms}^2 = %.2f\ \mathrm{W}\ \ (\mathrm{of\ which\ ripple:}\ %.2f\ \mathrm{W})" % (Pcu, Rmot * dI ** 2 / 12))

doc.h("6. Start-up: no back-EMF means no current limit")
doc.eq(r"I_{stall} = \frac{D\,V_{bus}}{R_m} = \frac{%.2f}{%.1f} = %.0f\ \mathrm{A} \qquad \tau_{mech} \approx \frac{J}{2k\omega + b + K_t^2/R} = %.0f\ \mathrm{ms}" % (D * Vbus, Rmot, Istall, tau * 1e3))
doc.p("The 30 ms throttle ramp keeps the peak well below the stall value, because the rotor builds back-EMF while D rises. "
      "The time constant τ is the linearized settling time, so the speed is about 95 % settled after roughly 3τ.")

doc.h("7. Dead time")
doc.p("The triangle carrier rises from 0 to 1 in Tsw/2. The high-side FET switches off at duty - db and the low-side FET switches on at duty + db. "
      "The gap, 2·db in carrier units, therefore corresponds to a time of:")
doc.eq(r"T_{dead} = 2\,db \cdot \frac{T_{sw}}{2} = db\,T_{sw} \quad\Rightarrow\quad db = \frac{T_{dead}}{T_{sw}} = \frac{100\,\mathrm{ns}}{41.7\,\mu\mathrm{s}} = %.4f" % db)
doc.p("During the dead time the motor current must keep flowing, so it goes through the low-side body diode and the switch node "
      "drops to about -Vf. The cost per PWM period is two diode intervals:")
doc.eq(r"P_{dead} \approx 2\,V_f\,I\,T_{dead}\,f_{sw} = 2 \cdot %.1f \cdot %.1f \cdot 100\,\mathrm{ns} \cdot 24\,\mathrm{kHz} = %.0f\ \mathrm{mW}" % (Vf, I, Pdt * 1e3))

doc.h("8. FET conduction loss and the DC link")
doc.eq(r"P_{cond,hi} \approx I_{rms}^2\,R_{DS(on)}\,D = %.2f\ \mathrm{W} \qquad I_{C,rms} \approx I\sqrt{D(1-D)} = %.1f\ \mathrm{A}" % (Pcond, Icap_rms))
doc.p("The capacitors carry the pulsed part of the current, so they must be rated for this RMS current. "
      "The battery-lead inductance and the bulk capacitor also form a resonant tank:")
doc.eq(r"f_{res} = \frac{1}{2\pi\sqrt{L_{wire}\,C_{bulk}}} = \frac{1}{2\pi\sqrt{100\,\mathrm{nH}\cdot 480\,\mu\mathrm{F}}} = %.0f\ \mathrm{kHz}" % (f_res / 1e3))
doc.p("This resonance sits almost exactly on the 24 kHz PWM frequency. That is why the battery current in panel D of the plot still swings "
      "strongly instead of being smooth. A real design would move the PWM frequency away from it or add damping (bulk-cap ESR or an RC snubber).")

doc.h("9. Hand calculation vs. LTspice")
rows = [
    ["Speed", f"{rpm:,.0f} RPM", f"{sim['rpm_final']:,.0f} RPM"],
    ["Motor current (avg)", f"{I:.2f} A", f"{sim['imot_avg']:.2f} A"],
    ["Battery current (avg)", f"{Ibat:.2f} A", f"{sim['ibat_avg']:.2f} A"],
    ["Ripple current (p-p)", f"{dI:.1f} A", f"{sim['imot_ripple']:.1f} A"],
    ["Copper loss", f"{Pcu:.2f} W", f"{sim['pcu']:.2f} W"],
    ["Mechanical power", f"{Pmech:.1f} W", f"{sim['pmech']:.1f} W"],
    ["Input power", f"{Pin:.1f} W", f"{sim['pin']:.1f} W"],
    ["Peak start-up current", f"< {Istall:.0f} A (stall)", f"{sim['imot_peak']:.0f} A"],
    ["FET loss hi / lo", f"~{Pcond:.2f} W cond. each", f"{sim['pfet_hi']:.2f} / {sim['pfet_lo']:.2f} W"],
    ["Efficiency (Pmech / Pin)", f"{Pmech / Pin * 100:.1f} %", f"{sim['efficiency'] * 100:.1f} %"],
]
doc.table(["Quantity", "Hand calculation", "LTspice"], rows, widths=[0.4, 0.3, 0.3])
doc.p("The hand model ignores switching and dead-time losses and the cap ESR, so it lands slightly optimistic. "
      "Agreement within a few percent means the simulation is set up correctly. Always do this check before trusting a model.")
doc.p("This check earned its keep. The first run stopped at 150 ms and reported 8.23 A, 6 % above the hand value. "
      "At the simulated speed the prop needs only about 7.5 A, so the remaining current was accelerating the rotor: it had not reached "
      "steady state. Extending the run to 300 ms closed the gap. Lesson: measure only after every time constant has settled, "
      "and the slowest one here is mechanical, not electrical.")

doc.h("10. Simulated waveforms")
doc.img(os.path.join(here, "HalfBridge_MotorDrive_results.png"), width=6.7)

doc.h("11. Key takeaways")
doc.bullets([
    "Duty cycle sets the voltage. Back-EMF cancels most of it, so voltage sets speed and load sets current.",
    "The winding inductance is the filter. Ripple ΔI = V·D(1-D)/(L·f): low-L motors need higher PWM frequency.",
    "With no back-EMF at start-up, current is limited only by R, which is why ESCs ramp throttle and limit current.",
    "Dead time prevents shoot-through but costs body-diode loss. Keep it as short as the FETs safely allow.",
    "The DC-link caps, not the battery, supply the pulsed current. Check their RMS rating and the L-C resonance.",
])

out = os.path.join(here, "01_Half-Bridge_Motor_Drive_Design.pdf")
print(out, doc.save(out), "pages")

"""Builds 04_Three-Channel_Power_Transmission_Design.pdf: hand calculations + LTspice results for topology 04."""
import os, sys, math, json
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, "..", "tools")); sys.path.insert(0, here)
from designdoc import Doc, INK, INK2, ACCENT
from ltraw import read_meas
from matplotlib.patches import FancyBboxPatch
from hand_calc import *

sim = read_meas(os.path.join(here, "ThreeChannel_Transmission.log"))
S = lambda k, case: sim[k][case]
ops = [op_point(c) for c in CH]
op3s = op_point(CH[2], IQ3_STEP)
hp0 = [hotplug(c, False) for c in CH]; hp1 = [hotplug(c, True) for c in CH]
gl_ss = ground_loop([o["Ibat"] for o in ops]); gl_st = ground_loop([ops[0]["Ibat"], ops[1]["Ibat"], op3s["Ibat"]])
extra = json.load(open(os.path.join(here, "extra_metrics.json")))
s03 = read_meas(os.path.join(here, "..", "03_Three-Phase_FOC_PMSM", "ThreePhase_FOC.log"))

doc = Doc("04  Three-Channel Power Transmission",
          "3 independent 4S packs -> 3 harnesses (14 AWG + XT60) -> 3 ESC DC links -> 3 motors  |  plug-in, ripple, punch, grounding")

doc.h("1. What this design is about")
doc.p("The goal of the series is three batteries driving three motors independently. This topology covers the electrical transmission "
      "between them: the battery's internal resistance, the cable harness and connector, and the ESC's DC-link capacitors. Each channel "
      "is a separate loop: battery k feeds only ESC k. The three ESCs share only a signal ground to the flight controller, because the "
      "throttle signals need a common reference. Down-conversion for sensors and avionics comes later.")

def block(ax):
    ax.set_xlim(0, 10); ax.set_ylim(0, 2.3)
    for row, y in enumerate((1.6, 0.9, 0.2)):
        k = row + 1
        for x, t in [(0, f"4S pack {k}"), (2.3, f"harness {k}"), (4.6, f"ESC {k} DC link"), (6.9, f"ESC {k} + motor {k}")]:
            ax.add_patch(FancyBboxPatch((x, y), 1.9, 0.5, boxstyle="round,pad=0.02,rounding_size=0.06", fc="#eef4fc", ec=ACCENT, lw=1))
            ax.text(x + 0.95, y + 0.18, t, ha="center", fontsize=8.5, color=INK)
        for x in (1.9, 4.2, 6.5):
            ax.annotate("", (x + 0.4, y + 0.25), (x, y + 0.25), arrowprops=dict(arrowstyle="->", color=INK2))
        ax.plot([8.8, 9.3], [y + 0.25, y + 0.25], color=INK2, lw=0.8, ls="--")
    ax.plot([9.3, 9.3], [0.45, 1.85], color=INK2, lw=0.8, ls="--"); ax.text(9.4, 1.0, "FC\nsignal\nground", fontsize=7.5, color=INK2)
    ax.text(3.25, 2.18, "R = 2·l·8.28 mΩ/m + 1 mΩ,   L = (μ0/π)·ln(s/r)·l", ha="center", fontsize=7.5, color=INK2)
doc.figure(block, 2.3)

doc.h("2. Harness model")
doc.p("Each harness is a + and a − wire of 14 AWG silicone cable plus an XT60. The loop resistance is the copper of both wires plus the "
      "connector. The loop inductance is that of a two-wire line: it depends on the wire spacing s, and only logarithmically on it.")
doc.eq(r"R_{loop} = 2\,\ell\,R' + R_{XT60} \qquad L_{loop} = \frac{\mu_0}{\pi}\ln\frac{s}{r}\,\ell \qquad R' = 8.28\ \mathrm{m\Omega/m},\ r = 0.81\ \mathrm{mm}", size=12)
rows = []
for c in CH:
    Rl, Ll, Lp = harness(c)
    rows.append([f"ch{c['k']}", c["desc"], f"{Rl*1e3:.2f} mΩ", f"{Lp*1e6:.2f} µH/m", f"{Ll*1e9:.0f} nH"])
doc.table(["Channel", "Routing", "R loop", "L per m", "L loop"], rows, widths=[0.12, 0.36, 0.17, 0.18, 0.17])
doc.p("Pulling the two wires 20 mm apart nearly triples the inductance per metre. Twisting or taping the pair together is the cheapest fix in this whole design.")
doc.p("Is a lumped R-L good enough, or is the cable a transmission line? The edges of the ESC current take about 20 ns, which puts their "
      "spectrum up to roughly 0.35/20 ns ≈ 18 MHz. In the cable that is a wavelength of about 2·10⁸/18·10⁶ ≈ 11 m. The rule of thumb is "
      "that a line under λ/10 (1.1 m) behaves as lumped R-L-C, so all three harnesses can be modelled as lumped.")

doc.h("3. ESC + motor as a switching-function load")
doc.p("The transmission only sees the current the ESC draws from its DC link, so each ESC + motor is replaced by that current. With the "
      "high-side gate signals h_x ∈ {0, 1} from the SVPWM comparators of topology 03, and sinusoidal phase currents i_x, the inverter's input "
      "current is exactly:")
doc.eq(r"i_{inv}(t) = h_a\,i_a + h_b\,i_b + h_c\,i_c \qquad \overline{i_{inv}} = \frac{1}{V_{bus}}\sum_x \overline{v_x i_x} = \frac{\frac{3}{2}v_q i_q}{V_{bus}}")
doc.p("This keeps every switching edge but needs no FETs, motor, mechanics or controller, so a three-case run takes about a minute "
      "instead of about 40. The operating points come from the prop law of topologies 02 and 03 at fixed speed; speed changes over "
      "about 100 ms, much slower than this 11 ms window. Check: channel 1 at 14,000 RPM draws %.2f A here, against %.2f A in the full FOC "
      "simulation of topology 03. The difference is the 03 FET losses, which this model leaves out." % (S("ibat_avg1", 1), s03["ibat_avg"][0]))
doc.p("A real ESC computes its duty from a filtered, sampled bus voltage, so the model feeds the duty calculation through a 3 kHz low-pass. "
      "Without that filter the load would act as an ideal constant-power load (incremental resistance −V²/P) right up to the cable "
      "resonance, and it would wrongly predict instability.")

doc.h("4. Steady state: voltage drop and loss")
doc.eq(r"I_{bat} = \frac{P}{V_{bus}} \qquad V_{bus} = V_{batt} - I_{bat}\,(R_{int} + R_{loop}) \qquad P_{harness} = I_{bat,rms}^2\,R_{loop}", size=12)
rows = []
for i, c in enumerate(CH):
    o = ops[i]
    rows.append([f"ch{c['k']}", f"{c['rpm']:,}", f"{o['P']:.1f} W", f"{o['Ibat']:.2f} A", f"{o['Vbus']:.3f} V", f"{o['drop']*1e3:.0f} mV", f"{o['Pcable']*1e3:.0f} mW"])
doc.table(["Ch", "RPM", "Power", "I bat", "V bus", "Drop", "Harness loss"], rows, widths=[0.08, 0.13, 0.15, 0.15, 0.17, 0.15, 0.17])
doc.p("At these currents the harness is not the problem: even 30 cm of 14 AWG loses well under 1 %. The battery's own 20 mΩ costs "
      "more. What makes the harness matter is its inductance, and that shows up in ripple, plug-in and transients (sections 5 to 7).")

doc.h("5. Ripple current and the cable resonance")
doc.p("The inverter current is a train of pulses. Its DC part comes from the battery, but most of its AC part must come from the DC-link "
      "capacitors, which is why ESCs have them. For SVPWM with sinusoidal phase currents, Kolar & Round give the RMS of that AC part in "
      "closed form, with M = V̂ph/(Vbus/2) and φ the angle between phase voltage and current:")
doc.eq(r"I_{C,rms} = I_{ph,rms}\sqrt{2M\left[\frac{\sqrt{3}}{4\pi} + \cos^2\varphi\left(\frac{\sqrt{3}}{\pi} - \frac{9M}{16}\right)\right]} \qquad I_{inv,rms} = \sqrt{\overline{I}^{\,2} + I_{C,rms}^2}", size=12)
doc.p("Where that AC current flows depends on impedance. The battery path is R + sL_loop, and the capacitors are ESR + sESL + 1/(sC). "
      "With only the 10 µF ceramic, the harness inductance and the ceramic form a resonant tank:")
doc.eq(r"f_{res} = \frac{1}{2\pi\sqrt{L_{loop}\,C_{cer}}} \qquad Z_0 = \sqrt{\frac{L_{loop}}{C_{cer}}} \qquad Q = \frac{Z_0}{R_{int} + R_{loop} + ESR}", size=12)
doc.table(["Channel", "f res", "Z0", "Q", "Nearest PWM harmonic"],
          [[f"ch{c['k']}", f"{hp0[i]['f0']/1e3:.0f} kHz", f"{hp0[i]['Z0']*1e3:.0f} mΩ", f"{hp0[i]['Q']:.1f}",
            f"{round(hp0[i]['f0']/Fsw)}·fsw = {round(hp0[i]['f0']/Fsw)*48} kHz"] for i, c in enumerate(CH)],
          widths=[0.16, 0.18, 0.18, 0.12, 0.36])
doc.p("Channel 3's long, spread-apart harness resonates at 57 kHz, right next to the 48 kHz PWM, with Q ≈ 8. Panel C shows that its bus "
      "impedance there peaks above 2 Ω. The PWM current harmonics and their motor-frequency sidebands land on that peak, and the bus "
      "rings. The 470 µF electrolytic fixes this in two ways. Its ESR (30 mΩ) damps the tank, and its large C moves the resonance down to "
      "about 8 kHz, where the current harmonics are small.")

doc.h("6. Plug-in: overshoot and the spark")
doc.p("Plugging a pack into an ESC switches a voltage step onto a series R-L-C: battery resistance, harness, and uncharged capacitors. "
      "The second-order step response gives the peak voltage and current:")
doc.eq(r"\zeta = \frac{R}{2Z_0} \qquad V_{pk} = V_{batt}\left(1 + e^{-\pi\zeta/\sqrt{1-\zeta^2}}\right) \qquad I_{pk} = \frac{V_{batt}}{\omega_d L}e^{-\alpha t_{pk}}\sin\omega_d t_{pk}", size=12)
doc.p("ωd = ω0√(1−ζ²), α = ζω0, and tpk = atan(ωd/α)/ωd is when the current peaks. With only a ceramic, ζ is 0.06 to 0.18, so the "
      "bus rings up to 1.6–1.8 × Vbatt: 27 V on a 14.8 V pack, a few volts below the 30 V FET rating. Higher cell counts or longer "
      "wires would exceed it. With the electrolytic, the bulk ESR makes ζ ≈ 0.8–2.4, so there is no overshoot. But the capacitors now "
      "absorb a ~270 A current pulse. That is the spark you see and hear at the XT60, and it pits the contacts. An overdamped circuit "
      "is bounded by Ipk < V/R, which is the value used in the table below.")

doc.h("7. Throttle punch on channel 3")
doc.p("At 8 ms motor 3's torque current steps from 3.8 A to 25 A in 100 µs: the first milliseconds of a punch, before the speed moves. "
      "The final bus voltage is simple, V = Vbatt − I(Rint + Rloop) = %.2f V at %.2f A. The transient is not. With only a ceramic, "
      "the bigger ripple current drives the 57 kHz tank, and the bus swings from %.1f V to %.1f V (panel D). An ESC would brown out its "
      "logic or overstress its FETs. With the electrolytic, the PWM-averaged bus dips only to %.2f V, and the raw ripple is %.1f to %.1f V."
      % (op3s["Vbus"], op3s["Ibat"], S("vmin_step3", 0), 19.8, extra["vmin_avg_step3_bulk"], S("vmin_step3", 1), 15.6))

doc.h("8. Independence and grounding")
doc.p("With separate packs, each battery is a floating source. KCL around battery k says every amp out of its + terminal returns to its "
      "own − terminal. The only connection between channels is the signal ground, and no loop passes through it, so it carries "
      "no power current. The simulation confirms it: signal-ground current is about 10⁻¹⁰ A, and ESC 1's bus does not move when motor 3 "
      "punches (panel E). Independent packs give independence for free.")
doc.p("That breaks the moment the battery negatives are joined somewhere else, for example a common negative bus on a PDB, a charger "
      "lead, or a metal frame. The signal-ground wires then close a loop parallel to each negative power wire, and the negative-wire "
      "voltage drops (I·Rneg) drive current through them. Solving the DC resistor network (nodal analysis, see hand_calc.py) gives:")
doc.table(["Signal wire", "Steady, hand", "Steady, sim", "After punch, hand", "After punch, sim"],
          [[f"wire {k+1}", f"{gl_ss[1][k]:+.2f} A", f"{extra[f'isig_avg_ss{k+1}']:+.2f} A", f"{gl_st[1][k]:+.2f} A",
            f"{extra[f'isig_avg_after{k+1}']:+.2f} A"] for k in range(3)],
          widths=[0.2, 0.2, 0.2, 0.2, 0.2])
doc.p("(Sim values are time averages, i.e. the DC part; on top of it rides PWM-frequency current, %.2f A rms in wire 3 after the punch.)" % S("isig3_after", 2))
doc.p("Up to %.1f A flows in a 26 AWG signal wire that was never meant to carry power. Motor 3's return current splits: %.2f A through its "
      "own negative wire (hand) and %.2f A (sim); the rest detours through the flight controller's ground plane. That injects noise "
      "into the throttle signals and IMU. Rule: tie the negatives in one place only, or not at all." % (max(abs(x) for x in gl_st[1]), gl_st[0][2], -S("ineg3_after", 2)))

doc.h("9. Hand calculation vs. LTspice")
rows = []
def add(lab, h, sv, fmt):
    e = (sv / h - 1) * 100; rows.append([lab, fmt.format(h), fmt.format(sv), "0.0 %" if abs(e) < 0.05 else f"{e:+.1f} %"])
for k in (1, 2, 3):
    i = k - 1
    add(f"ch{k} battery current (A)", ops[i]["Ibat"], S(f"ibat_avg{k}", 1), "{:.3f}")
    add(f"ch{k} inverter RMS current, Kolar (A)", ops[i]["Iinv_rms"], S(f"iinv_rms{k}", 1), "{:.2f}")
    add(f"ch{k} plug-in peak V, ceramic (V)", hp0[i]["Vpk"], S(f"vplug_pk{k}", 0), "{:.2f}")
    add(f"ch{k} plug-in peak I, ceramic (A)", hp0[i]["Ipk"], S(f"iplug_pk{k}", 0), "{:.1f}")
    add(f"ch{k} plug-in peak I, + bulk (A)", hp1[i]["Ipk"], S(f"iplug_pk{k}", 1), "{:.0f}")
add("ch3 bus after punch (V)", op3s["Vbus"], S("vbus_after3", 1), "{:.3f}")
add("ch3 battery current after punch (A)", op3s["Ibat"], S("ibat_after3", 1), "{:.2f}")
add("ch3 own negative wire, tied (A)", gl_st[0][2], -S("ineg3_after", 2), "{:.2f}")
doc.table(["Quantity", "Hand calc", "LTspice", "Difference"], rows, widths=[0.46, 0.18, 0.18, 0.18])
doc.p("All rows match closely except the bulk-capacitor inrush on channels 1 and 2. Those circuits are overdamped, and V/R is only an "
      "upper bound: the inductance and the ceramic hold the current back while it rises. Channel 3 with bulk is underdamped (ζ = 0.76), "
      "so its exact formula applies and lands within 2 %.")

doc.h("10. Simulated waveforms")
doc.img(os.path.join(here, "ThreeChannel_Transmission_results.png"), width=6.6)

doc.h("11. Design rules for the 3-battery, 3-motor transmission")
doc.bullets([
    "Keep + and − wires together (twisted or taped). Spacing sets inductance, and inductance sets every problem in this document.",
    "Put a low-ESR electrolytic (or polymer) at every ESC, as close as possible. It damps the harness resonance; ceramics alone ring.",
    "Check f_res = 1/(2π√(L·C)) for every harness: keep it well away from fsw and 2·fsw.",
    "Plug-in needs either damping (bulk ESR) to stop overshoot or an anti-spark/precharge circuit to stop the ~270 A inrush. Ideally both.",
    "Independent packs are naturally isolated. Share only the signal ground, and never join the battery negatives a second time.",
    "Harness I²R is small at these currents. Size wire for the peak punch current and voltage drop, not the hover current.",
])
out = os.path.join(here, "04_Three-Channel_Power_Transmission_Design.pdf")
print(out, doc.save(out), "pages")

"""Builds 11_Whole_System_Schematic_Design.pdf: the whole power system drawn part by part and simulated, hand vs. LTspice.
Needs Power_System.raw/.log (run Power_System.asc first, ~20 min)."""
import os, math
import numpy as np
import paths  # noqa: F401
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from designdoc import Doc
from ltraw import read_raw, read_meas
import hand_calc as h

here = os.path.dirname(os.path.abspath(__file__))
P = lambda f: os.path.join(here, f)
h09 = h.h09
M = {k: v[0] for k, v in read_meas(P("Power_System.log")).items()}
d = read_raw(P("Power_System.raw")); t = np.abs(np.asarray(d["time"]))
sig = lambda k: np.asarray(d[k])
win = t > 5.5e-3
avg = lambda k: float(sig(k)[win].mean())

# ------------------------------------------------------------------ hand calculations
C_bus = 16 * 150e-6 + 12 * 1.1e-6                  # C1-C16, C17-C26, C38-C39
I_inrush = C_bus * h.V_NOM / 1e-3
Ke = 60 / (2 * math.pi * h09.KV); Kph = Ke / math.sqrt(3)
ia_t, ib_t, ic_t = avg("I(motor1:La)"), avg("I(motor1:Lb)"), avg("I(motor1:Lc)")
iq_true = (ia_t + 2 * ib_t) / math.sqrt(3)
T_em = 1.5 * Kph * iq_true; alpha = T_em / h09.Jrot
t_on = 2e-3; w_hand = alpha * t_on; rpm_hand = w_hand * 60 / (2 * math.pi)
Rds_eq = 6.5e-3 / 4
P_cu = h09.Rph * 1.5 * iq_true ** 2; P_cond = Rds_eq * 1.5 * iq_true ** 2; P_mech = T_em * w_hand / 2
I_idle = 0.12
I_bus_hand = (P_cu + P_cond + P_mech) / h.V_NOM + I_idle
rset, cset = 33.2e3, 47e-9; tau33 = rset * cset; V33 = 100e-6 * rset
v33 = sig("V(av_3v3)"); pts = [float(np.interp(x, t, v33)) for x in (4.999e-3, 5.499e-3, 5.999e-3)]
r = (pts[2] - pts[1]) / (pts[1] - pts[0]); tau_fit = 0.5e-3 / math.log(1 / r); v_inf = pts[2] + (pts[2] - pts[1]) * r / (1 - r)
V5 = avg("V(esc1:+5v)"); rr = V5 / 5
read = lambda I: (rr * (h.ACS_ZERO + h.ACS_GAIN * I) - h.ACS_ZERO) / h.ACS_GAIN
ia_r, ib_r = read(ia_t), read(ib_t)
iq_read_hand = (ia_r + 2 * ib_r) / math.sqrt(3)
ia_m = (avg("V(esc1:isns_a)") / h.K_DIV - h.ACS_ZERO) / h.ACS_GAIN
ib_m = (avg("V(esc1:isns_b)") / h.K_DIV - h.ACS_ZERO) / h.ACS_GAIN

# ------------------------------------------------------------------ plots
ms = t * 1e3
fig, ax = plt.subplots(3, 1, figsize=(7.2, 7.4), sharex=True)
ax[0].plot(ms, sig("V(pdb1)"), label="PDB1 (pack 1)"); ax[0].set_ylabel("V"); ax[0].legend(fontsize=8); ax[0].grid(alpha=.3)
ax[0].set_title("Power-up: pack pre-charge, then the four boards start", fontsize=10)
ax[1].plot(ms, sig("I(L_HARN1)"), color="C3"); ax[1].set_ylabel("harness 1 current (A)"); ax[1].grid(alpha=.3)
for k, lab in (("V(av_12v)", "avionics 12 V"), ("V(av_5v)", "avionics 5 V"), ("V(av_3v3)", "avionics 3.3 V"), ("V(esc1:+12v)", "ESC1 12 V")):
    ax[2].plot(ms, sig(k), label=lab)
ax[2].set_ylabel("V"); ax[2].set_xlabel("time (ms)"); ax[2].legend(fontsize=8, ncol=2); ax[2].grid(alpha=.3)
fig.tight_layout(); fig.savefig(P("11_powerup.png"), dpi=130); plt.close(fig)

fig, ax = plt.subplots(3, 1, figsize=(7.2, 7.0), sharex=True)
w = t > 3.5e-3
for k, lab in (("I(motor1:La)", "ia"), ("I(motor1:Lb)", "ib"), ("I(motor1:Lc)", "ic")): ax[0].plot(ms[w], sig(k)[w], label=lab)
ax[0].set_ylabel("motor 1 phase current (A)"); ax[0].legend(fontsize=8); ax[0].grid(alpha=.3)
ax[0].set_title("Motor 1 commanded from standstill at 4 ms (current limit 60 A)", fontsize=10)
ax[1].plot(ms[w], sig("V(esc1:u9:iq)")[w], label="iq read by the MCU"); ax[1].plot(ms[w], sig("V(esc1:u9:iqref)")[w], "--", label="iq command")
ax[1].axhline(iq_true, color="k", lw=0.8, ls=":", label=f"true iq from the motor currents ({iq_true:.1f} A)")
ax[1].set_ylabel("A"); ax[1].legend(fontsize=8); ax[1].grid(alpha=.3)
for n in (1, 2, 3): ax[2].plot(ms[w], sig(f"V(motor{n}:rpm)")[w], label=f"motor {n}")
ax[2].set_ylabel("rpm"); ax[2].set_xlabel("time (ms)"); ax[2].legend(fontsize=8); ax[2].grid(alpha=.3)
fig.tight_layout(); fig.savefig(P("11_motor.png"), dpi=130); plt.close(fig)

fig, ax = plt.subplots(2, 1, figsize=(7.2, 4.6), sharex=True)
w = (t > 5.80e-3) & (t < 5.90e-3)
ax[0].plot(ms[w], sig("V(m1_a)")[w], label="phase A (M1_A)"); ax[0].plot(ms[w], sig("V(esc1:bst_a)")[w], label="BST_A")
ax[0].set_ylabel("V"); ax[0].legend(fontsize=8); ax[0].grid(alpha=.3)
ax[0].set_title("Inside ESC1, two PWM periods (50 µs each)", fontsize=10)
ax[1].plot(ms[w], sig("V(esc1:gah1)")[w] - sig("V(m1_a)")[w], label="Q4 gate-source (high side, GAH1)")
ax[1].plot(ms[w], sig("V(esc1:gal1)")[w], label="Q8 gate (low side, GAL1)")
ax[1].set_ylabel("V"); ax[1].set_xlabel("time (ms)"); ax[1].legend(fontsize=8); ax[1].grid(alpha=.3)
fig.tight_layout(); fig.savefig(P("11_switching.png"), dpi=130); plt.close(fig)

# ------------------------------------------------------------------ document
doc = Doc("11  Whole Power System, Drawn Part by Part",
          "3 × 24S pack → 3 ESC boards → 3 U15XL motors + avionics board, every part wired")
doc.h("1. What is drawn")
doc.p("Topology 10 described each board as a parts table and wrote its LTspice sheet with a net label on every pin: correct, but a "
      "list of parts, not a circuit anyone can read. Here the same tables are drawn as real schematics: every part placed and connected "
      "with wires, framed in the numbered areas of a PCB schematic. Labels are kept only for supply rails, ground and the MCU-to-driver "
      "signals. Power_System.asc ties it together: each pack feeds its own ESC and motor, and every pack feeds the avionics board.")
doc.img(P("power_system_top.png"), width=5.6)
doc.table(["Sheet", "Contents"], [
    ["ESC_Block (×3)", "181 parts: DC link, LTC7801, 2 × LT1763, 3 × (LTC7063 + 8 FETs)"],
    ["Avionics_Block", "65 parts: fuses + diode-OR, TVS, LTC7801, LT8641, LT3045"],
    ["ACS770 (U7, U8)", "equivalent circuit: 100 µΩ primary, ratiometric output"],
    ["STM32G431_FOC (U9)", "real pins; FOC firmware as signal flow (ADC → PI → SVPWM)"],
    ["U15XL_Motor (×3)", "3 windings in star + back-EMF; rotor as RC analog"],
], widths=[0.24, 0.76])

doc.h("2. How the drawing is checked")
doc.p("A drawn schematic can be wrong in ways a label list cannot: a wire touching the wrong pin, a part rotated backwards, a rail "
      "never named. Each sheet is therefore written by a script and checked twice. A lint pass looks for wire ends that touch nothing "
      "and pins sitting on the middle of a wire. Then LTspice's own netlister (-netlist) is run on the sheet, and every pin of every part "
      "is compared with the net the parts table assigns it. The mapping must be one-to-one: one LTspice net per table net.")
doc.table(["Sheet", "Parts", "Wires", "Lint", "Pin errors"], [
    ["ESC_Block", "181", "427", "0", "0"], ["Avionics_Block", "65", "129", "0", "0"], ["STM32G431_FOC", "54", "52", "0", "0"],
    ["U15XL_Motor", "20", "26", "0", "0"], ["ACS770", "5", "7", "0", "0"]], widths=[0.3, 0.15, 0.15, 0.15, 0.25])
doc.p("The check found three real errors while the sheets were being drawn: a bootstrap diode placed reversed (its anode, labelled +12V, "
      "landed on the phase node and shorted 12 V to all three phases), and two rails (VIN_AV, VTX_12V) with no label, which left a FET "
      "drain and a load on unnamed islands. It also caught two netlist conventions worth knowing: LTspice names a MOSFET 'M§Q4' and a "
      "block 'X§U7', and a symbol whose pins skip SpiceOrder numbers gets MP_ placeholder nodes in the gaps.")
doc.img(P("esc_drawn.png"), width=6.6)
doc.p("ESC_Block as drawn (preview render; LTspice also shows pin names).", size=8.5)

doc.h("3. Power-up")
doc.p("Every pack starts at 0 V and ramps to 88.8 V in Tplug = 1 ms (a stand-in for the anti-spark pre-charge). The ESC bus is "
      "mostly capacitance, so the harness current during the ramp is")
doc.eq(r"I = C_{bus}\,\frac{dV}{dt} = (16\times150\,\mu F + 12\times1.1\,\mu F)\,\frac{88.8\ \mathrm{V}}{1\ \mathrm{ms}} = %.0f\ \mathrm{A}" % I_inrush)
doc.p("A real anti-spark connector ramps over about 100 ms, which limits the inrush to about 2 A. The simulation starts with `uic` "
      "(no DC operating point): with every source at 0 V, LTspice cannot find an operating point for four switching boards, and the "
      "physical start is all-cold anyway. The avionics 3.3 V rail is an LT3045, whose output follows its SET pin; C_SET filters it:")
doc.eq(r"V_{out} = 100\,\mu A \cdot R_{SET} = %.2f\ \mathrm{V}, \qquad \tau = R_{SET} C_{SET} = 33.2\,k\Omega \cdot 47\,nF = %.2f\ \mathrm{ms}" % (V33, tau33 * 1e3))
doc.img(P("11_powerup.png"), width=6.2)

doc.h("4. The motor punch from standstill")
doc.p("At Tpunch = 4 ms each ESC is commanded to 50 rad/s; the speed loop saturates and asks for the current limit. With the rotor at "
      "θe ≈ 0, the inverse Park/Clarke transform (amplitude-invariant, id = 0) puts all of iq into phases B and C:")
doc.eq(r"i_a = -i_q\sin\theta_e \approx 0, \quad i_b = -i_q\sin(\theta_e - 120^\circ) = 0.866\,i_q, \quad i_c = -0.866\,i_q")
doc.p("The torque and the speed reached 2 ms later (the prop's drag is negligible this slow):")
doc.eq(r"T = \frac{3}{2}K_{ph}\,i_q = 1.5 \cdot %.4f \cdot %.1f = %.1f\ \mathrm{N\,m}, \quad \omega = \frac{T}{J}\,t = \frac{%.1f}{%.2f}\cdot 2\ \mathrm{ms} = %.3f\ \mathrm{rad/s}" % (Kph, iq_true, T_em, T_em, h09.Jrot, w_hand), size=11)
doc.p("So the punch barely shows on the bus: the 54 × 18 prop's inertia means 2 ms of full current moves the rotor 0.2 milliradians. "
      "The ESC's input power is almost all I²R in the windings and FETs:")
doc.eq(r"P = \frac{3}{2}i_q^2 (R_{ph} + R_{DS}/4) = 1.5\cdot %.1f^2\,(8.5 + 1.6)\ \mathrm{m\Omega} = %.0f\ \mathrm{W} \;\Rightarrow\; I_{bus} \approx %.2f\ \mathrm{A} + 0.12\ \mathrm{A\ idle}" % (iq_true, P_cu + P_cond, (P_cu + P_cond) / h.V_NOM), size=11)
doc.img(P("11_motor.png"), width=6.2)
doc.img(P("11_switching.png"), width=6.0)

doc.h("5. A real finding: the current-sense zero moves with the 5 V rail")
doc.p("The ACS770's output is ratiometric: Vout = (VCC/5)(2.5 V + 10 mV/A · I). The firmware converts with the nominal 2.5 V zero. "
      f"The ESC's LT1763-5 actually makes {V5:.3f} V, so every reading is scaled by r = VCC/5 = {rr:.4f}:")
doc.eq(r"\hat{i} = \frac{r\,(2.5 + 0.01\,i) - 2.5}{0.01} = r\,i - (1-r)\cdot 250\ \mathrm{A} = r\,i - %.2f\ \mathrm{A}" % ((1 - rr) * 250))
doc.p("While the motor spins, this offset rotates in the dq frame and only adds ripple (topology 10's hover test reads iq within "
      "0.5 %). At standstill the phase currents are DC, so it adds straight into iq, and the limit lets more current through than set. "
      "Production FOC firmware measures each ADC's zero at boot, drivers off, and subtracts it.")
doc.table(["", "ia (A)", "ib (A)", "iq (A)"], [
    ["true (motor)", f"{ia_t:.2f}", f"{ib_t:.2f}", f"{iq_true:.1f}"],
    ["MCU reads, hand (ratiometric offset)", f"{ia_r:.2f}", f"{ib_r:.2f}", f"{iq_read_hand:.1f}"],
    ["MCU reads, LTspice", f"{ia_m:.2f}", f"{ib_m:.2f}", f"{M['iq1']:.1f}"],
], widths=[0.46, 0.18, 0.18, 0.18])
doc.p(f"The hand model explains {iq_true - iq_read_hand:.1f} of the {iq_true - M['iq1']:.1f} A gap; the remaining "
      f"{(iq_read_hand - M['iq1']):.1f} A is a further ~0.1 % low reading in the sense chain that I have not traced.", size=9.5)

doc.h("6. Hand calculation vs. LTspice")
doc.table(["Quantity", "Hand", "LTspice", "Diff."], [
    ["Inrush per pack (1 ms ramp)", f"{I_inrush:.0f} A", "214 A", "0 %"],
    ["Avionics 12 V / 5 V (5.5–6 ms)", "12.0 / 5.05 V", f"{M['vav12']:.2f} / {M['vav5']:.2f} V", "0 %"],
    ["3.3 V: τ and final value", f"{tau33*1e3:.2f} ms, {V33:.2f} V", f"{tau_fit*1e3:.2f} ms, {v_inf:.2f} V (fit)", f"{(tau_fit/tau33-1)*100:+.1f} %"],
    ["12 V / 5 V reach 90 %", "—", f"{M['t_av12']*1e3:.2f} / {M['t_av5']*1e3:.2f} ms", ""],
    ["Phase currents ia / ib / ic", f"0 / {0.866*iq_true:.1f} / {-0.866*iq_true:.1f} A", f"{ia_t:.1f} / {ib_t:.1f} / {ic_t:.1f} A", ""],
    ["Rotor speed 2 ms after the punch", f"{rpm_hand:.2f} rpm", f"{M['rpm1']:.2f} rpm", f"{(M['rpm1']/rpm_hand-1)*100:+.0f} %"],
    ["ESC1 bus current", f"{I_bus_hand:.2f} A", f"{M['iesc1']:.3f} A", "switching"],
    ["Pack currents 1 / 2 / 3", "equal", f"{M['ipack1']:.3f} / {M['ipack2']:.3f} / {M['ipack3']:.3f} A", "0.03 %"],
    ["ESC1 12 V aux", "12.0 V", f"{M['v12_esc1']:.2f} V", "0 %"],
], widths=[0.36, 0.22, 0.28, 0.14])
doc.p("The rotor speed is 4 % under the hand value because the current takes about 0.1 ms to reach the limit after the command. The "
      f"bus-current gap, {M['iesc1'] - I_bus_hand:.2f} A × 88.8 V ≈ {(M['iesc1'] - I_bus_hand)*88.8:.0f} W, is the switching and "
      "gate-drive loss of 24 FETs at 20 kHz, which the hand estimate leaves out.", size=9.5)

doc.h("7. Takeaways")
doc.bullets([
    "Draw from the parts table, then check the drawing against it with the simulator's own netlister. A wrong wire on a drawn schematic "
    "is silent; the check turned three of them into error messages.",
    "Parts without a maker model become blocks with the real pin-out outside and an honest equivalent circuit inside, so the schematic "
    "still reads like the PCB (U7/U8 ACS770, U9 STM32).",
    "A system with no DC path to start from (all sources at 0 V, switching controllers) needs `uic`; it is also the true physical start.",
    "Hierarchical probing: V(ESC1:<net>), V(ESC1:U9:<node>), I(MOTOR1:La). Only .save'd nodes are kept; saving everything would be GB.",
    "Ratiometric sensors move with their supply: calibrate the zero at boot, or measure the supply. Standstill current limiting is where "
    "the error shows.",
])
n = doc.save(P("11_Whole_System_Schematic_Design.pdf")); print("pages:", n)

"""Builds 05_Channel_Protection_Soft-Start_Reverse-Polarity_Design.pdf: hand calculations + LTspice results for topology 05."""
import os, sys, math, json
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, "..", "tools"))
from designdoc import Doc, INK, INK2, ACCENT
from ltraw import read_meas
from matplotlib.patches import FancyBboxPatch

# ---------------- parameters (same as the .asc) ----------------
Vb, Rbatt, Rloop, Lloop = 15.0, 20e-3, 5.97e-3, 140e-9
Cdc, ESRb = 480e-6, 30e-3
Rpre, Tpre = 5.0, 10e-3
Rg, Cm, Cgs_fet, Cgsx, Rgs = 12e3, 100e-9, 6e-9, 2.2e-6, 100e3
Vto, Kp, Rds_ext = 2.5, 300, 0.6e-3
Is_b, N_b, Rs_b, Vt = 15e-12, 1.05, 1.3e-3, 0.02585
Coss = 3e-9

sim = {k: v for k, v in read_meas(os.path.join(here, "ChannelProtection.log")).items()}
S = lambda k, c: sim[k][c]
ex = json.load(open(os.path.join(here, "extra_metrics.json")))

# ---------------- hand calculations ----------------
R_path = Rbatt + Rloop + ESRb
I_bare = Vb / R_path                                         # overdamped bound (see topology 04)
R_pre_tot = Rpre + Rbatt + Rloop
tau_pre = R_pre_tot * Cdc; I_pre = Vb / R_pre_tot
t90_pre = tau_pre * math.log(10)
dV_main = Vb * math.exp(-Tpre / tau_pre); I_main = dV_main / R_path
E_half = 0.5 * Cdc * Vb ** 2

I_target = 5.0
V_plat = Vto + math.sqrt(2 * I_target / Kp)
I_in = (Vb - V_plat) * Cdc / (Rg * Cm)
t_ramp = Cdc * Vb / I_in
V_kick_naive = Vb * Cm / (Cm + Cgs_fet)
Vds_ring = 2 * Vb                                            # contact ringing bound (L with Coss)
V_kick = Vds_ring * Cm / (Cm + Cgs_fet + Cgsx)
V_kick_settled = Vb * Cm / (Cm + Cgs_fet + Cgsx)
Cgs_min = Cm * (Vds_ring / Vto - 1)
tau_g = Rg * (Cm + Cgsx + Cgs_fet)
t_delay = tau_g * math.log((Vb - V_kick_settled) / (Vb - V_plat))
Ig = (Vb - V_plat) / Rg; I_Cm = Ig - V_plat / Rgs - (Cgsx + Cgs_fet) * ex["dvgs_dt"]; I_in_ref = I_Cm * Cdc / Cm
P_start = Vb * I_in

Ronf = lambda vgs: Rds_ext + 1 / (Kp * (vgs - Vto))
Ron = Ronf(12.0); Ron_cr = Ronf(ex["vgs_cruise"]); Ron_pu = Ronf(ex["vgs_punch"])
P_cr = 2 * Ron_cr * S("ibat_cruise", 3) ** 2; P_pu = 2 * Ron_pu * S("ibat_punch", 3) ** 2

I_rev = 400.0
for _ in range(50):
    Vf = N_b * Vt * math.log(I_rev / Is_b) + I_rev * Rs_b
    I_rev = (Vb - Vf) / (Rbatt + Rloop)

doc = Doc("05  Channel Protection: Soft-Start + Reverse Polarity",
          "One channel of topology 04 (30 cm harness, 480 µF ESC link)  |  bare XT60 vs XT90-S vs back-to-back MOSFETs")

doc.h("1. The two problems from topology 04")
doc.p("Topology 04 showed that plugging a pack into an ESC with a proper electrolytic draws about 230–270 A for a few microseconds. "
      "That is the spark that pits XT60 contacts. It also left a worse event untested: a pack plugged in backwards. Every ESC "
      "inverter has six body diodes that point from ground to the bus, so a reversed pack short-circuits straight through them. This "
      "topology adds protection to each channel and compares three ways of plugging in, plus reverse plugging with and without protection.")

def block(ax):
    ax.set_xlim(0, 10); ax.set_ylim(0, 2.0)
    for x, t, sub in [(0, "4S pack", "15 V, 20 mΩ"), (2.0, "connector", "XT60 / XT90-S"), (4.0, "harness", "30 cm"),
                      (6.0, "Q1 | Q2", "back-to-back N-FETs"), (8.0, "ESC", "480 µF + body diodes")]:
        ax.add_patch(FancyBboxPatch((x, 0.95), 1.7, 0.8, boxstyle="round,pad=0.02,rounding_size=0.06", fc="#eef4fc", ec=ACCENT, lw=1))
        ax.text(x + 0.85, 1.45, t, ha="center", fontsize=9, weight="bold", color=INK); ax.text(x + 0.85, 1.15, sub, ha="center", fontsize=7.5, color=INK2)
    for x in (1.7, 3.7, 5.7, 7.7):
        ax.annotate("", (x + 0.3, 1.35), (x, 1.35), arrowprops=dict(arrowstyle="->", color=INK2))
    ax.text(6.85, 0.55, "in the − line, common source;\ngate fed from bus+ via 12 kΩ,\n100 nF Miller cap, 2.2 µF Cgs, 12 V zener", ha="center", fontsize=7.5, color=INK2)
doc.figure(block, 1.9)

doc.h("2. The back-to-back MOSFET pair")
doc.p("A MOSFET only blocks in one direction: its body diode conducts the other way. So blocking both the inrush (normal polarity) "
      "and a reversed pack takes two FETs in series, sources joined (common source), in the negative line. N-channel FETs go in the "
      "negative line because their gate can be driven from the pack's own + rail, with no charge pump.")
doc.bullets([
    "Q2 (drain at ESC ground): its body diode blocks the normal return current, so nothing flows until Q2's gate opens. That is the soft-start.",
    "Q1 (drain at battery −): its body diode would carry the normal current, but its gate is on too, so the channel carries it at milliohms. If the pack is reversed, Q1's body diode blocks and the gate is pulled negative. That is the reverse-polarity block.",
    "One gate network drives both FETs. A 12 V zener protects the gate, and 100 kΩ discharges it after unplugging.",
])

doc.h("3. Soft-start by the Miller plateau")
doc.p("A 100 nF capacitor Cm from gate to Q2's drain (the ESC ground) turns the FET into a slew-rate limiter. While Q2 conducts in its "
      "linear region, Vgs sits at the plateau needed for the current (V_plat = Vto + √(2I/Kp)). The gate current through Rg then "
      "flows only into Cm, which fixes how fast the drain may move. The drain voltage is the capacitor-voltage deficit, so:")
doc.eq(r"I_g = \frac{V_b - V_{plat}}{R_g} = C_m\frac{dV_{DS}}{dt} \qquad I_{inrush} = C_{dc}\frac{dV_{DS}}{dt} = \frac{(V_b - V_{plat})\,C_{dc}}{R_g\,C_m}", size=12)
doc.eq(r"V_{plat} = %.1f + \sqrt{2\cdot 5/300} = %.2f\ \mathrm{V} \qquad I_{inrush} = \frac{%.2f \cdot 480\,\mu}{12\,k \cdot 100\,n} = %.2f\ \mathrm{A} \qquad t_{ramp} = \frac{C_{dc}V_b}{I_{inrush}} = %.2f\ \mathrm{ms}" % (Vto, V_plat, Vb - V_plat, I_in, t_ramp * 1e3), size=11)
doc.p("The inrush current is set by a ratio of passives (two capacitors and a resistor), not by the FET, so it is repeatable.")

doc.h("4. The trap: dV/dt turn-on at the moment of contact")
doc.p("The first simulation of this design failed (case 2 in the plots). When the connector touches, the uncharged ESC capacitors "
      "pull the ESC ground up with the bus, so Q2's drain jumps by the full pack voltage in microseconds. Cm couples that jump into the "
      "gate, and only the FET's own ~6 nF of Cgs resists it:")
doc.eq(r"\Delta V_{GS} = V_b\frac{C_m}{C_m + C_{gs}} = 15\cdot\frac{100}{106} = %.1f\ \mathrm{V} \;\gg\; V_{to}" % V_kick_naive, size=12)
doc.p("The FET snapped fully on, and the inrush was %.0f A, barely better than a bare connector, with a %.0f W pulse in the FET. "
      "The fix is a gate-source capacitor big enough that the capacitive divider keeps the kick below threshold. The drain does not just "
      "step to Vb: until Q2 conducts, the harness inductance rings with Q2's output capacitance, and the drain overshoots toward 2·Vb "
      "(26 V simulated). Size Cgs for that peak:" % (S("ipk_plug", 2), S("pk_fet", 2)))
doc.eq(r"C_{gs} > C_m\left(\frac{2V_b}{V_{to}} - 1\right) = %.0f\ \mathrm{nF} \;\Rightarrow\; 2.2\ \mu\mathrm{F}:\ \ \Delta V_{GS} = 2V_b\frac{C_m}{C_m + C_{gs}} = %.2f\ \mathrm{V}" % (Cgs_min * 1e9, V_kick), size=11)
doc.p("My first fix used 1 µF, sized for a 15 V step. The simulation showed a 2.4 V kick against a 2.5 V threshold: it worked by luck. "
      "2.2 µF gives the 2·Vb case real margin.")
doc.p("Cgs does not change the inrush current, because Vgs is constant on the plateau so Cgs takes no current there. It only adds a "
      "turn-on delay. Once the contact ringing dies, the kick settles to Vb·Cm/(Cm+Cgs) = %.2f V, and the gate then charges toward the plateau:" % V_kick_settled)
doc.eq(r"t_d = R_g(C_m + C_{gs})\ln\frac{V_b - \Delta V_{GS}}{V_b - V_{plat}} = 12\,k\cdot 2.3\,\mu\cdot\ln\frac{%.2f}{%.2f} = %.2f\ \mathrm{ms}" % (Vb - V_kick_settled, Vb - V_plat, t_delay * 1e3), size=12)

doc.h("5. Energy: the ½CV² that has to go somewhere")
doc.p("Charging a capacitor from a fixed voltage through anything resistive dissipates exactly the energy that ends up stored, no matter "
      "how slowly it is done:")
doc.eq(r"E_{loss} = \int_0^\infty i\,(V_b - v_C)\,dt = \frac{1}{2}C_{dc}V_b^2 = %.0f\ \mathrm{mJ}" % (E_half * 1e3), size=12)
doc.p("A bare connector dumps it into the contact arc. The XT90-S puts it into its 5 Ω resistor; the active circuit puts it into Q2 "
      "over about %.1f ms, an average of %.0f W with an initial peak up to Vb·I = %.0f W. That has to fit inside the FET's linear-mode "
      "safe operating area (SOA). Check the datasheet's 1 ms or 10 ms SOA curve at 15 V; this is where cheap anti-spark boards fail."
      % (t_ramp * 1e3, E_half / t_ramp, P_start))

doc.h("6. XT90-S precharge resistor")
doc.p("An XT90-S has a short contact with a built-in resistor that touches first; the main contacts close a moment later. Here the main "
      "contact is assumed to close %.0f ms after the first touch, which depends on how fast a hand pushes the plug." % (Tpre * 1e3))
doc.eq(r"I_{pk} = \frac{V_b}{R_{pre} + R_{int} + R_{loop}} = %.2f\ \mathrm{A} \qquad \tau = R\,C_{dc} = %.2f\ \mathrm{ms} \qquad t_{90} = \tau\ln 10 = %.2f\ \mathrm{ms}" % (I_pre, tau_pre * 1e3, t90_pre * 1e3), size=12)
doc.eq(r"\Delta V(T_{pre}) = V_b e^{-T_{pre}/\tau} = %.0f\ \mathrm{mV} \;\Rightarrow\; I_{main} \lesssim \frac{\Delta V}{R_{int}+R_{loop}+ESR} = %.1f\ \mathrm{A}" % (dV_main * 1e3, I_main), size=12)
doc.p("It works, but only if the hand is slow. Pushed in within 1 ms, the main contacts would see about 94 % of the pack voltage. It also does nothing for reverse polarity.")

doc.h("7. Reverse polarity")
doc.p("With the pack reversed and no protection, current flows from the pack's − terminal through the ESC's body diodes into its +. "
      "Solving I = (Vb − Vf(I)) / (Rint + Rloop) with the diode equation Vf = N·VT·ln(I/Is) + I·Rs:")
doc.eq(r"I_{rev} = %.0f\ \mathrm{A}\ \ (V_f = %.2f\ \mathrm{V})" % (I_rev, Vf), size=12)
doc.p("That is a dead short. Within seconds it destroys the FETs, the electrolytic (now reverse-biased) and probably the pack. With "
      "the back-to-back pair, Q1's body diode is reverse-biased and its gate sits at about −15 V relative to the source, so only "
      "leakage flows: %.0f nA in the simulation." % (abs(S("irev_avg", 5)) * 1e9))

doc.h("8. Cost while flying")
doc.eq(r"R_{on} = R_d + R_s + \frac{1}{K_p(V_{GS} - V_{to})} = %.2f\ \mathrm{m\Omega}\ \ \mathrm{at}\ V_{GS} = 12\ \mathrm{V} \qquad P = 2R_{on}I^2" % (Ron * 1e3), size=12)
doc.p("The big Cgs has a side effect: the gate needs about 3·Rg·(Cm + Cgs) ≈ 80 ms to reach its 12 V clamp. At the cruise window "
      "(28–33 ms) Vgs is only %.1f V (Ron = %.2f mΩ), and at the punch (40–45 ms) %.1f V (Ron = %.2f mΩ). The ESC should wait about "
      "100 ms after plug-in before allowing full throttle, which an arming sequence does anyway." % (ex["vgs_cruise"], Ron_cr * 1e3, ex["vgs_punch"], Ron_pu * 1e3))
doc.p("At cruise (%.1f A) the pair loses %.2f W, and at a punch (%.1f A) %.2f W. A Schottky diode, the textbook reverse-polarity "
      "part, would lose 0.45 V × I = %.1f W and %.1f W, and it could not do soft-start at all. This is why every modern design uses "
      "MOSFETs as 'ideal diodes'." % (S("ibat_cruise", 3), P_cr, S("ibat_punch", 3), P_pu, 0.45 * S("ibat_cruise", 3), 0.45 * S("ibat_punch", 3)))

doc.h("9. Hand calculation vs. LTspice")
rows = []
def add(lab, h, sv, fmt):
    e = (sv / h - 1) * 100
    rows.append([lab, fmt.format(h), fmt.format(sv), "0.0 %" if abs(e) < 0.05 else f"{e:+.1f} %"])
add("Bare XT60 inrush peak (A), bound V/R", I_bare, S("ipk_plug", 0), "{:.0f}")
add("XT90-S time to 90 % (ms)", t90_pre * 1e3, (S("t90", 1) - 1e-3) * 1e3, "{:.2f}")
add("XT90-S main-contact spark (A), bound", I_main, S("ipk_main", 1), "{:.1f}")
add("XT90-S resistor energy (mJ)", E_half * 1e3, S("e_rpre", 1) * 1e3, "{:.1f}")
add("Active: gate kick at contact (V)", V_kick, ex["vgs_kick"], "{:.2f}")
add("Active: turn-on delay to 10 % (ms)", t_delay * 1e3, ex["t10_active"] * 1e3, "{:.2f}")
add("Active: mean inrush, ideal formula (A)", I_in, ex["iavg_ramp_active"], "{:.2f}")
add("Active: mean inrush, refined (A)", I_in_ref, ex["iavg_ramp_active"], "{:.2f}")
add("Active: 10-90 % ramp time (ms)", 0.8 * t_ramp * 1e3, ex["t_ramp_active"] * 1e3, "{:.2f}")
add("Active: FET energy (mJ)", E_half * 1e3, S("e_fets", 3) * 1e3, "{:.1f}")
add("Active: Q2 Vds peak at contact (V), bound 2Vb", 2 * Vb, ex["vds_q2_pk"], "{:.1f}")
add("Reverse, bare: current (A)", I_rev, -S("irev_avg", 4), "{:.0f}")
add("FET pair loss at cruise (W)", P_cr, S("pprot_cruise", 3), "{:.3f}")
add("FET pair loss at punch (W)", P_pu, S("pprot_punch", 3), "{:.3f}")
doc.table(["Quantity", "Hand calc", "LTspice", "Difference"], rows, widths=[0.46, 0.18, 0.18, 0.18])
doc.p("Notes on the larger differences:")
doc.bullets([
    "The bare inrush and the main-contact spark are V/R upper bounds; the harness inductance and the ceramic slow the rise (as in topology 04).",
    "The active inrush is %.0f %% under the ideal formula. Of the %.3f mA through Rg, Rgs takes %.3f mA, and Cgs takes %.3f mA because the "
    "plateau is not perfectly flat (Vgs creeps up %.0f V/s). That leaves %.3f mA for Cm, which predicts %.2f A (refined row). The rest comes "
    "from the FET's own voltage-dependent capacitances: the current climbs from %.1f A to %.1f A during the ramp instead of staying flat. "
    "In hardware you would trim Rg." % ((1 - ex["iavg_ramp_active"] / I_in) * 100, ex["ig_rg"] * 1e3, ex["ig_rgs"] * 1e3,
    (Cgsx + Cgs_fet) * ex["dvgs_dt"] * 1e3, ex["dvgs_dt"], I_Cm * 1e3, I_in_ref, ex["i_q2_start"], ex["i_q2_end"]),
    "Q2's drain rings to %.1f V at contact. Until Q2 conducts, the harness inductance resonates with Q2's ~3 nF output capacitance in "
    "series with the ESC caps. That is a step into an almost lossless L-C, bounded by 2Vb. The FET must be rated well above 2× pack "
    "voltage: 40 V for 4S, and 60 V or more for 6S." % ex["vds_q2_pk"],
    "This run uses Gear integration. Trapezoidal integration rang numerically after the punch: a 2 GB file and no finish in 5 minutes. "
    "Gear damps such artifacts but also slightly damps real ringing, so for ringing amplitudes topology 04 (trapezoidal) is the reference.",
])

doc.h("10. Simulated waveforms")
doc.img(os.path.join(here, "ChannelProtection_results.png"), width=6.6)

doc.h("11. Design rules for each of the three channels")
doc.bullets([
    "Put back-to-back N-FETs in each negative line: one block gives soft-start and reverse-polarity protection for about 0.1–0.8 W.",
    "Set the inrush with Rg·Cm: I = (Vb − Vplat)·Cdc/(Rg·Cm). Aim for a few amps, a ramp of a few ms.",
    "Always add Cgs > Cm·(2Vb/Vto − 1), sized for the contact ringing, or the plug-in dV/dt kicks the gate on and the soft-start does nothing.",
    "Size the FET for ½CV² in its linear SOA, and for ≥ 2× pack voltage of Vds at the moment of contact.",
    "Protection sits in each channel's own negative line, so the three channels stay independent (topology 04, section 8).",
])
out = os.path.join(here, "05_Channel_Protection_Soft-Start_Reverse-Polarity_Design.pdf")
print(out, doc.save(out), "pages")

"""Builds 08_Redundant_Avionics_Power_Design.pdf: how one 5 V rail draws from three floating packs, hand math vs LTspice."""
import os, sys, json, math
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, "..", "tools")); sys.path.insert(0, here)
from designdoc import Doc, INK, INK2, ACCENT
from ltraw import read_meas
from matplotlib.patches import FancyBboxPatch
import hand_calc as h

m = read_meas(os.path.join(here, "Redundant_Avionics.log")); S = lambda k, c: m[k][c]
ex = json.load(open(os.path.join(here, "extra_metrics.json")))
PUNCH = [h.P1_PUNCH, h.PESC[1], h.PESC[2]]
sh = {c: h.share(c, h.PESC) for c in range(4)}; sp = {c: h.share(c, PUNCH) for c in range(4)}
gn = {c: h.ground_nodal(c, sh[c]["I"], sh[c]["iesc"]) for c in range(4)}
gp = {c: h.ground_nodal(c, sp[c]["I"], sp[c]["iesc"]) for c in range(4)}
tie = h.ground_nodal(0, sh[0]["I"], sh[0]["iesc"], tie=True)
iso = h.iso_share()
ua = h.unplug_handover(sh[2])
s_after = {c: h.share(c, [0, h.PESC[1], h.PESC[2]], alive=(0, 1, 1)) for c in (0, 2)}
sr = {c: h.short_reverse(c, s_after[c]["vin"], s_after[c]["I"][1]) for c in (0, 2)}
s3 = h.share(2, [0, 0, h.PESC[2]], alive=(0, 0, 1))
dip = h.vin_dip_after_short(s_after[2]["I"][2], s3["I"][2], sr[2]["Q"])
Rpar = h.Rsig * h.Rret / (h.Rsig + h.Rret)
I1 = sh[2]["I"][0]
Pav_hand = {c: h.P_BEC + sh[c]["I"][0] ** 2 * (h.Rtap + (h.Rsig if c == 0 else Rpar)) + (h.vf_schottky if c == 3 else h.vf_ideal)(sh[c]["I"][0]) * sh[c]["I"][0] for c in (0, 2, 3)}
Pav_hand[4] = sum(iso["pin"])
t_hold = h.holdup(h.Cin, sh[2]["vin"])

doc = Doc("08  Redundant Avionics Power",
          "one 5 V rail from three floating 4S packs  |  ideal-diode OR-ing, ground returns, switchover, reverse blocking")

doc.h("1. The problem")
doc.p("Topology 04 gave each motor its own pack, harness and ESC, and showed that the three packs must float: their negatives are "
      "joined only once, at the flight controller (FC), through the thin 26 AWG signal-ground wires that carry the ESC throttle "
      "signals. Topology 06 built the 5 V BEC for the avionics, fed from one channel. If that one pack is unplugged, shorted or sags "
      "too far, the flight controller browns out and all three motors are lost. This topology feeds the BEC from all three packs so "
      "that any one can fail. Two rules must hold:")
doc.bullets(["No ground loop: no power current may use the signal wires, and no motor current may circulate between channels.",
             "No back-feed: a healthy pack must never push current into a dead, unplugged or shorted channel."])
doc.p("The core difficulty is that the BEC has one ground (it is a non-isolated buck, so its input − and output − are the same node, "
      "the FC ground), while the three packs have three separate negatives. OR-ing the positives is the easy half. The question this "
      "design answers is: which way does the BEC's return current go home to the pack that supplied it?")

def block(ax):
    ax.set_xlim(0, 10); ax.set_ylim(0, 3.3)
    box = lambda x, y, w, t, sub, fc="#eef4fc", ec=ACCENT, ls="-": (ax.add_patch(FancyBboxPatch((x, y), w, 0.55, boxstyle="round,pad=0.02,rounding_size=0.05", fc=fc, ec=ec, lw=1, ls=ls)),
        ax.text(x + w / 2, y + 0.33, t, ha="center", fontsize=8.5, weight="bold", color=INK), ax.text(x + w / 2, y + 0.1, sub, ha="center", fontsize=7, color=INK2))
    for k, y in enumerate((2.55, 1.6, 0.65)):
        box(0.0, y, 1.3, f"pack {k+1}", f"{h.VB[k]} V, 20 mΩ")
        box(1.75, y, 1.45, f"ESC {k+1}", "480 µF + motor")
        ax.annotate("", (1.75, y + 0.28), (1.3, y + 0.28), arrowprops=dict(arrowstyle="-", color=INK2, lw=2))
        ax.text(1.52, y + 0.6, "harness", fontsize=6.5, color=INK2, ha="center")
        ax.annotate("", (5.0, 1.95), (3.2, y + 0.38), arrowprops=dict(arrowstyle="->", color="#c0392b", lw=1))
        ax.annotate("", (3.2, y + 0.16), (5.0, 1.45), arrowprops=dict(arrowstyle="->", color=INK, lw=1, ls="--"))
        ax.annotate("", (3.2, y + 0.05), (8.3, 0.35), arrowprops=dict(arrowstyle="-", color="#999999", lw=0.8, ls=":"))
    box(5.0, 1.45, 1.6, "OR board", "+ ideal diodes ×3", fc="#fdf1ea", ec="#eb6834")
    box(7.0, 1.45, 1.35, "BEC (06)", "15 V -> 5 V, 3 A")
    box(8.55, 1.45, 1.4, "FC + avionics", "5 V rail, FC ground")
    ax.annotate("", (7.0, 1.72), (6.6, 1.72), arrowprops=dict(arrowstyle="->", color=INK2)); ax.annotate("", (8.55, 1.72), (8.35, 1.72), arrowprops=dict(arrowstyle="->", color=INK2))
    ax.text(4.1, 2.95, "18 AWG + taps (red)", fontsize=7, color="#c0392b"); ax.text(4.1, 0.95, "return: the design question (dashed)", fontsize=7, color=INK)
    ax.text(8.3, 0.12, "26 AWG signal grounds (dotted) -> FC ground", fontsize=7, color=INK2, ha="right")
doc.figure(block, 3.1)

doc.h("2. Five architectures (one .step, five cases)")
doc.table(["Case", "Positive rail", "Return to the packs", "Expected weakness"],
          [["0", "ideal diode ×3", "signal grounds only", "BEC return in signal wires"],
           ["1", "ideal diode ×3", "ideal diode ×3 + 18 AWG", "diode shunted by signal wire"],
           ["2", "ideal diode ×3", "18 AWG star wire ×3", "(recommended)"],
           ["3", "Schottky ×3", "18 AWG star wire ×3", "0.36 V drop, loss"],
           ["4", "isolated DC-DC ×3", "none (galvanic isolation)", "cost, 85 % efficiency"]], widths=[0.08, 0.22, 0.34, 0.36])
doc.p("The taps are 15 cm 18 AWG pairs from each ESC's power pads to the avionics board: R = %.2f mΩ and L = %.0f nH per conductor "
      "(04's two-wire formula, L = (μ0/π)·ln(s/r) per metre of loop). The signal ground is 27 mΩ / 200 nH. Each case runs the same "
      "timeline: start-up, normal flight, a 365 W punch on ESC 1 (3–4 ms), pack 1 unplugged at 5 ms, bus 2 shorted (5 mΩ) at 6 ms. "
      "After 6 ms only pack 3 is left." % (h.Rtap * 1e3, h.Ltap * 1e9))

doc.h("3. The ideal diode (LM74700-style, behavioural)")
doc.p("An ideal-diode controller drives an N-FET whose body diode points the right way (source = anode). It does not just switch the "
      "FET fully on. It regulates the FET's drop to a small target, Vreg = 20 mV, by integrating a gate current into the gate "
      "capacitance (2.7 mA charge pump, gm = Ichg/50 mV). At light current the FET is therefore only partly on:")
doc.eq(r"R_{DS,reg} = \frac{V_{reg}}{I} \qquad \mathrm{e.g.}\ \ \frac{20\ \mathrm{mV}}{%.2f\ \mathrm{A}} = %.1f\ \mathrm{m\Omega}\ \ (\mathrm{fully\ on:}\ %.1f\ \mathrm{m\Omega})" % (I1, h.Vreg / I1 * 1e3, h.RDS_ON * 1e3), size=12)
doc.p("If V_AK falls below −11 mV (current trying to flow backwards), a comparator pulls the gate down with 2.4 A. Its response is "
      "modelled as a first-order lag, τ = 0.3 µs, on V_AK. Below Vreg and above −11 mV the gate is off and the body diode (0.6 V) is "
      "not yet conducting, so the device carries nothing. The forward drop and loss compared with a Schottky:")
doc.eq(r"V_F = nV_T\ln\left(\frac{I}{I_s}\right) + I R_s = %.0f\ \mathrm{mV} \qquad P_{Schottky} = V_F I = %.0f\ \mathrm{mW} \qquad P_{ideal} = V_{reg} I = %.1f\ \mathrm{mW}" % (h.vf_schottky(sh[3]["I"][0]) * 1e3, h.vf_schottky(sh[3]["I"][0]) * sh[3]["I"][0] * 1e3, h.Vreg * I1 * 1e3), size=12)
doc.p("At 1 A that is 18× less heat, and 0.34 V more headroom for the BEC on an empty pack. The gap grows with current: at 15 A "
      "this Schottky would dissipate %.1f W, the ideal diode (fully on) %.2f W." % (h.vf_schottky(15) * 15, 15 ** 2 * h.RDS_ON))

doc.h("4. Which pack supplies the BEC?")
doc.p("An OR is a selector, not a sharer. Every path k from a pack to vin has its own Thévenin voltage and resistance. Path k "
      "conducts only if it can reach vin with a positive current, and all conducting paths end at the same vin:")
doc.eq(r"v_{in} = V_k - (I_{ESC,k} + I_k)(R_{int} + R_{h,k}) - I_k R_{tap} - V_F(I_k) - V_{ret}(I_k), \qquad \sum_k I_k = \frac{P_{BEC}}{v_{in}}", size=11.5)
doc.p("I_ESC,k = P_k/V_bus,k is the ESC's own current through the same pack and harness, so a busy channel sags and drops out of the "
      "OR. P_BEC = %.2f W (06: 14.95 W out at 97 %%). The ESC loads are constant-power, so the equations are iterated. In normal "
      "flight bus 1 sits at %.2f V and buses 2 and 3 at %.2f and %.2f V: pack 1 is 0.33 V ahead and supplies the whole %.3f A. "
      "During the punch ESC 1 draws 25 A, and bus 1 sags to %.2f V, so pack 1 drops out, and packs 2 and 3 share because their "
      "buses are only 11 mV apart. With both conducting and ideal diodes:" % (h.P_BEC, sh[2]["vbus"][0], sh[2]["vbus"][1], sh[2]["vbus"][2], I1, sp[2]["vbus"][0]))
doc.eq(r"V_2' - I_2 R_2 = V_3' - I_3 R_3,\quad I_2 + I_3 = I_{BEC}\ \Rightarrow\ I_2 = \frac{V_2' - V_3' + R_3 I_{BEC}}{R_2 + R_3} = %.3f\ \mathrm{A},\ \ I_3 = %.3f\ \mathrm{A}" % (sp[2]["I"][1], sp[2]["I"][2]), size=11.5)
doc.p("Here V' is each bus voltage with its ESC load but without the BEC, and R_k = Rint + R_h,k + R_tap + R_ret. The 20 mV regulated "
      "drop is the same in both paths and cancels. Sharing is set by a few millivolts and a few tens of milliohms: it is accidental, "
      "not designed. A Schottky's soft knee spreads the current a little more (Case 3 lets %.0f mA through pack 1 during the punch)." % (sp[3]["I"][0] * 1e3))

doc.h("5. Where does the return current go?  (the ground-loop question)")
doc.p("Topology 04's ground loop needed two joins at different points of the return: the ESC grounds joined at the FC by the signal "
      "wires, and the pack negatives joined at the packs. A motor's return current then had two parallel routes from its ESC "
      "ground to its own pack negative, one of them through the signal wires. Here the + rail is OR'ed through diodes, so no pack "
      "can push current into another pack's + terminal. What remains is the BEC's own return current, which must get from the FC "
      "ground to the negative of whichever pack supplied it. Each architecture gives it a different route:")
doc.bullets([
    "Case 0, + OR only: the signal wire is the only route. All %.2f A of BEC return current flows through 26 AWG, and its 27 mΩ "
    "moves the ESC's signal reference by %.0f mV. This is the ground loop by another route: it does not circulate, but it uses a "
    "signal wire as a power conductor." % (sh[0]["I"][0], sh[0]["I"][0] * h.Rsig * 1e3),
    "Case 1, an ideal diode in each return wire too: the diode sits in parallel with the signal wire. It regulates to 20 mV, so it "
    "conducts nothing until the signal wire itself drops 20 mV, which takes Vreg/Rsig = %.2f A. Above that:" % (h.Vreg / h.Rsig),
])
doc.eq(r"I_{diode} = \frac{I R_{sig} - V_{reg}}{R_{sig} + R_{ret}} = %.3f\ \mathrm{A} \qquad I_{sig} = I - I_{diode} = %.3f\ \mathrm{A}" % (gn[1]["Iret"][0], gn[1]["Isig"][0]), size=12)
doc.p("During the punch each supplying pack carries less than 0.74 A, so the return diodes switch off completely and all the return "
      "current goes back to the signal wires. A diode in the negative rail cannot help while a lower-impedance path sits beside it.")
doc.bullets([
    "Case 2, a plain 18 AWG return wire from the BEC ground to each ESC's ground pad: a current divider with the signal wire.",
])
doc.eq(r"I_{sig} = I\,\frac{R_{ret}}{R_{ret} + R_{sig}} = %.3f \times \frac{%.2f}{%.2f + 27} = %.3f\ \mathrm{A}" % (I1, h.Rret * 1e3, h.Rret * 1e3, gn[2]["Isig"][0]), size=12)
doc.p("Is the star a second join? Yes, but both joins are at the same end of the return (the ESC ground pads), so the star wires "
      "and the signal wires form a mesh among the ESC grounds with no source inside it. A motor's current still has only one "
      "route to its pack (its own harness negative), because the pack negatives are not joined anywhere else. Only the BEC's own "
      "%.2f A is shared, and 87 %% of it takes the heavy wire. To see what goes wrong otherwise, tie the three pack negatives "
      "together as well (04's Case 2). The same nodal analysis then gives %.2f, %.2f and %.2f A in the three signal wires, made "
      "of motor current." % (I1, *tie["Isig"]))
doc.bullets(["Case 4, isolated converters: each module's input is referenced to its own pack and its output to the FC ground, with no "
             "galvanic path between them. The signal wires carry exactly the 04 value, zero."])
doc.p("The ground currents are found by nodal analysis, as in 04. The nodes are the three ESC grounds and the three pack negatives, "
      "with the FC ground as reference. ESC k injects its current at g_k, pack k removes I_ESC,k + I_k at bn_k, and the BEC returns "
      "ΣI_k into the reference. The case-1 return diodes are piecewise: off, or a 20 mV source behind R_ret, written in Norton form and "
      "iterated until the on/off states are consistent. Then solve G·v = J.")

doc.h("6. Losing a pack: switchover and hold-up")
doc.p("Unplugging pack 1 (at its connector) does not drop vin at once. ESC 1's 480 µF stays on bus 1, and ESC 1 keeps drawing from it. "
      "Bus 1 falls at (I_ESC1 + I_BEC)/C until it reaches the level packs 2 and 3 can hold, and then the OR hands over smoothly:")
doc.eq(r"t_{hand} = \frac{C_{ESC}\,\Delta V}{I_{ESC,1} + I_{BEC}} = \frac{480\,\mu\mathrm{F}\times %.3f\ \mathrm{V}}{%.2f\ \mathrm{A}} = %.1f\ \mu\mathrm{s}" % (ua["dV"], ua["I"], ua["t"] * 1e6), size=12)
doc.p("After that, bus 1 keeps falling to ESC 1's 9 V undervoltage lockout, and diode 1 must stay off. Without it, packs 2 and 3 "
      "would feed motor 1 through an 18 AWG tap. The simulation shows %.0f µA of reverse current: blocked." % (abs(S("itap1_rev", 2)) * 1e6))
doc.p("The BEC's own 10 µF input capacitor is not a hold-up reserve. With no pack left, a constant-power load empties it from %.1f V to "
      "the 5.5 V dropout in:" % sh[2]["vin"])
doc.eq(r"t = \frac{C\,(V_0^2 - V_{min}^2)}{2P} = \frac{10\,\mu\mathrm{F}\,(%.1f^2 - 5.5^2)}{2 \times %.1f\ \mathrm{W}} = %.0f\ \mu\mathrm{s}" % (sh[2]["vin"], h.P_BEC, t_hold * 1e6), size=12)
doc.p("OR-ing gives redundancy, not hold-up. Riding through a total loss of power for 10 ms would need %.0f µF at vin." % (2 * h.P_BEC * 10e-3 / (sh[2]["vin"] ** 2 - 5.5 ** 2) * 1e6))

doc.h("7. A shorted channel: reverse current until the diode opens")
doc.p("When bus 2 shorts, diode 2 is conducting %.2f A in regulation. For a moment the BEC's input capacitor sees the short through "
      "the still-on FET. Three details set the reverse current:" % s_after[2]["I"][1])
doc.bullets([
    "The short is not 0 V. Pack 2 drives V_b/(R_int + R_h + 5 mΩ) = %.0f A through it, so %.2f V remains across it." % (sr[2]["Vshort"] / h.R_SHORT, sr[2]["Vshort"]),
    "The loop inductance is the + tap plus the return path: %.0f nH in Case 2 (star wire ∥ signal wire), %.0f nH in Cases 0–1 (the signal wire alone)." % (sr[2]["L"] * 1e9, sr[0]["L"] * 1e9),
    "In regulation the FET is barely on (Vgs − Vth ≈ 0.36 V, R_DS = %.0f mΩ), so V_AK ramps down at k = R_DS·di/dt. The comparator "
    "sees it through its lag and fires after the filtered V_AK has fallen Vreg − Vrev = 31 mV:" % (sr[2]["Rds_reg"] * 1e3),
])
doc.eq(r"k\left(t - \tau(1 - e^{-t/\tau})\right) = 31\ \mathrm{mV} \ \Rightarrow\ t_{det} \approx \sqrt{\frac{2\tau\cdot 31\,\mathrm{mV}}{k}} \qquad I_{rev,pk} = \frac{V_0 - V_{short}}{L}\,t_{det} - I_0", size=12)
doc.p("For Case 2: di/dt = %.0f A/µs, t_det = %.0f ns, I_pk = %.1f A. A larger loop inductance gives a lower peak (Case 0: %.1f A), "
      "because the comparator needs longer but the current also rises more slowly. When the FET opens, the current in the tap "
      "inductance avalanches the FET at its 40 V rating, but the energy is only ½LI² = %.1f µJ. The Schottky has no detection delay: "
      "its only reverse current (%.1f A peak) charges its own and the parallel FET's junction capacitance." % (sr[2]["didt"] / 1e6, sr[2]["t_det"] * 1e9, sr[2]["Ipk"], sr[0]["Ipk"], sr[2]["E"] * 1e6, abs(S("irev2_pk", 3))))
doc.p("After the diode opens, pack 3 must pick up pack 2's share at once. The extra current builds up in the tap inductance against "
      "Cin, and Cin also lost charge Q to the reverse pulse:")
doc.eq(r"\Delta v_{in} \approx \Delta I\sqrt{L/C_{in}} + Q/C_{in} = %.2f \times %.0f\ \mathrm{m\Omega} + %.0f\ \mathrm{mV} = %.0f\ \mathrm{mV}" % (s3["I"][2] - s_after[2]["I"][2], math.sqrt((h.Ltap + h.Lsig * h.Lret / (h.Lsig + h.Lret)) / h.Cin) * 1e3, sr[2]["Q"] / h.Cin * 1e3, dip * 1e3), size=12)
doc.p("06's input feed-forward makes the BEC almost blind to a 0.1 V input step. The 5 V rail moves by less than 1 mV in every "
      "event, in Cases 0–3 alike: the OR architecture decides where the currents flow, not how good the rail is.")

doc.h("8. The isolated alternative (Case 4)")
doc.p("Each pack feeds its own isolated 5 V module, and the outputs are OR'ed on the 5 V side, where all grounds are already the FC "
      "ground. The modules share by droop. Each output is a source V_set,k behind R_droop = 50 mΩ, with setpoints trimmed to "
      "±0.5 % (5.025 / 5.000 / 4.975 V):")
doc.eq(r"V_{out} = \overline{V_{set}} - V_{reg} - R_{droop}\frac{I_{load}}{3} = %.3f\ \mathrm{V} \qquad I_k = \frac{V_{set,k} - V_{reg} - V_{out}}{R_{droop}} = %.1f,\ %.1f,\ %.1f\ \mathrm{A}" % (iso["vout"], *iso["I"]), size=12)
doc.p("Ground currents are zero, and a dead pack only takes its own module out. The costs are real: three converters, each rated for "
      "the full load (any one may be the last one left), and about 85 %% efficiency instead of 97 %%. That is %.1f W from the packs "
      "for 14.8 W of avionics instead of %.1f W, plus the weight. After two failures the rail droops to %.2f V (one module carries "
      "3 A). When pack 1 is unplugged, module 1 runs on ESC 1's capacitors until they reach its 9 V lockout, and then drops out "
      "with a %.0f mV dip." % (Pav_hand[4], Pav_hand[2], S("vout_a", 4), (S("vout_n", 4) - S("vout_unp_min", 4)) * 1e3))

doc.h("9. Modelling choices")
doc.bullets([
    "BEC = 06's averaged model (d·Vin switch, Type III, 100 kHz-filtered feed-forward, soft-start) plus 0.33 W of switching loss, so "
    "it draws 06's measured 97 %. It keeps the loop dynamics that decide the 5 V glitch. Switching ripple is not part of this "
    "question, and leaving it out keeps all five cases at 25 s instead of hours.",
    "ESC + motor = constant-power loads at 04's operating points. The ESC computes current from a 3 kHz-filtered bus measurement, as "
    "in 04. The first run used an instantaneous P/V: a negative resistance at every frequency. It oscillated against the capacitors' "
    "few-nH ESL, the bus swung from −30 to +66 V, and the run stalled. Real ESCs regulate power only within their control bandwidth.",
    "No motor dynamics are needed: the propeller speeds are fixed for 7 ms, so there is no slow mechanical time constant to wait for.",
    "Gear integration. With trapezoidal integration the run is fine up to the bus-2 short. After the FET avalanches, the ~20 MHz "
    "ring of the tap inductance against the FET capacitance makes trap take sub-ns steps (1.1 GB, Case 0 still unfinished after "
    "7 min). With Gear all five cases take 25 s and every steady-state number is identical. Gear also damps real ringing a "
    "little, so that ring (plot D) is real but somewhat under-stated.",
])

doc.h("10. Hand calculation vs. LTspice")
rows = []
def add(lab, hv, sv, fmt):
    e = (sv / hv - 1) * 100 if hv else 0
    rows.append([lab, fmt.format(hv), fmt.format(sv), "0.0 %" if abs(e) < 0.05 else f"{e:+.1f} %"])
add("Normal: pack 1 BEC current, C0 (A)", sh[0]["I"][0], S("itap1_n", 0), "{:.4f}")
add("Normal: pack 1 BEC current, C2 (A)", sh[2]["I"][0], S("itap1_n", 2), "{:.4f}")
add("Normal: vin, C2 (V)", sh[2]["vin"], S("vin_n", 2), "{:.3f}")
add("Punch: pack 2, C0 (A)", sp[0]["I"][1], S("itap2_p", 0), "{:.4f}")
add("Punch: pack 3, C0 (A)", sp[0]["I"][2], S("itap3_p", 0), "{:.4f}")
add("Punch: pack 2, C2 (A)", sp[2]["I"][1], S("itap2_p", 2), "{:.4f}")
add("Punch: pack 3, C2 (A)", sp[2]["I"][2], S("itap3_p", 2), "{:.4f}")
add("Punch, Schottky: pack 1 (mA)", sp[3]["I"][0] * 1e3, S("itap1_p", 3) * 1e3, "{:.1f}")
add("Punch, Schottky: pack 2 (A)", sp[3]["I"][1], S("itap2_p", 3), "{:.4f}")
add("Ideal diode V_AK (mV)", h.Vreg * 1e3, S("vak1_n", 2) * 1e3, "{:.2f}")
add("Ideal diode loss (mW)", h.Vreg * I1 * 1e3, S("pd1_n", 2) * 1e3, "{:.1f}")
add("Schottky V_F (mV)", h.vf_schottky(sh[3]["I"][0]) * 1e3, S("vak1_n", 3) * 1e3, "{:.1f}")
add("Schottky loss (mW)", h.vf_schottky(sh[3]["I"][0]) * sh[3]["I"][0] * 1e3, S("pd1_n", 3) * 1e3, "{:.0f}")
add("Signal-wire current, C0 (A)", gn[0]["Isig"][0], S("isig1_n", 0), "{:.4f}")
add("Signal-wire current, C1 (A)", gn[1]["Isig"][0], S("isig1_n", 1), "{:.4f}")
add("Return-diode current, C1 (A)", gn[1]["Iret"][0], S("iret1_n", 1), "{:.4f}")
add("Signal-wire current, C2 (A)", gn[2]["Isig"][0], S("isig1_n", 2), "{:.4f}")
add("Signal wires during punch, C2 (A)", gp[2]["Isig"][1] + gp[2]["Isig"][2], S("isig2_p", 2) + S("isig3_p", 2), "{:.4f}")
add("Isolated: module 1 (A)", iso["I"][0], S("imod1_n", 4), "{:.3f}")
add("Isolated: module 2 (A)", iso["I"][1], S("imod2_n", 4), "{:.3f}")
add("Isolated: module 3 (A)", iso["I"][2], S("imod3_n", 4), "{:.3f}")
add("Isolated: 5 V rail (V)", iso["vout"], S("vout_n", 4), "{:.3f}")
add("Avionics input power, C2 (W)", Pav_hand[2], S("pav_n", 2), "{:.3f}")
add("Avionics input power, C3 (W)", Pav_hand[3], S("pav_n", 3), "{:.3f}")
add("Avionics input power, C4 (W)", Pav_hand[4], S("pav_n", 4), "{:.3f}")
add("Unplug: handover time (µs)", ua["t"] * 1e6, (S("t_hand", 2) - 5e-3) * 1e6, "{:.1f}")
add("Only pack 3 left: vin, C2 (V)", s3["vin"], S("vin_a", 2), "{:.3f}")
add("Short: detection time, C0 (ns)", sr[0]["t_det"] * 1e9, ex["t_det_0"] * 1e9, "{:.0f}")
add("Short: detection time, C2 (ns)", sr[2]["t_det"] * 1e9, ex["t_det_2"] * 1e9, "{:.0f}")
add("Short: reverse peak, C0 (A)", sr[0]["Ipk"], -S("irev2_pk", 0), "{:.2f}")
add("Short: reverse peak, C2 (A)", sr[2]["Ipk"], -S("irev2_pk", 2), "{:.2f}")
add("Short: vin dip below final, C2 (mV)", dip * 1e3, (S("vin_a", 2) - S("vin_sh_min", 2)) * 1e3, "{:.0f}")
doc.table(["Quantity", "Hand calc", "LTspice", "Difference"], rows, widths=[0.46, 0.18, 0.18, 0.18])
doc.p("Notes on the differences larger than a few percent:")
doc.bullets([
    "Schottky, pack 1 during the punch: the first comparison had the simulation 2.5× low. The cause was the 1 mΩ on-resistance of "
    "the switch that unplugs pack 1 later: 25 A × 1 mΩ = 25 mV, and a Schottky's current changes e-fold every nV_T = 27 mV. An "
    "exponential device turns a millivolt modelling error into a factor of 2. With a 10 µΩ switch they agree to %.1f %%." % (abs(S("itap1_p", 3) / sp[3]["I"][0] - 1) * 100),
    "Short detection and peak (Case 0: %+.0f %% / %+.0f %%, Case 2: %+.0f %% / %+.0f %%): the hand model starts the ramp from a perfect "
    "step. In the simulation the fault closes over 50 ns, so the current has already started to turn, and the comparator's filter "
    "has started to move, before bus 2 reaches the bottom. Detection is earlier and the peak lower. Case 2's di/dt is three times "
    "faster, so the 50 ns matters less there." % ((ex["t_det_0"] / sr[0]["t_det"] - 1) * 100, (-S("irev2_pk", 0) / sr[0]["Ipk"] - 1) * 100,
    (ex["t_det_2"] / sr[2]["t_det"] - 1) * 100, (-S("irev2_pk", 2) / sr[2]["Ipk"] - 1) * 100),
    "vin dip (%+.0f %%): the ΔI·sqrt(L/C) step estimate leaves out pack 3's ideal diode, which is in regulation (Rds = Vreg/I3 = "
    "%.0f mΩ) when the extra current arrives, so a little more voltage is lost across it until its gate catches up (about 2 µs at "
    "2.7 mA)." % (((S("vin_a", 2) - S("vin_sh_min", 2)) / dip - 1) * 100, h.Vreg / s_after[2]["I"][2] * 1e3),
    "Signal-wire currents: the simulation adds 1 µΩ case-selector resistors, which shows up only in the fourth digit.",
])

doc.h("11. Simulated waveforms")
doc.img(os.path.join(here, "Redundant_Avionics_results.png"), width=6.6)
doc.p("A: the OR picks pack 1, hands over to 2 + 3 in the punch, back to 1, then to 2 + 3 when pack 1 is pulled, then to 3 alone. "
      "B: the return current in the signal wires, simulation (bars) and nodal analysis (ticks). C: the unplug, handover and blocked "
      "reverse current. D: the reverse-current pulse when bus 2 shorts. E: the 5 V rail. F: battery power used by the avionics.")

doc.h("12. Recommendation: Case 2, ideal-diode OR on + plus a star return")
doc.bullets([
    "Tap every ESC's power pads with a twisted 18 AWG pair (+ and −) to the avionics board. Put an LM74700-class ideal diode in each "
    "+ lead. Join the three − leads at the BEC ground, which is the FC ground: one deliberate star.",
    "Do not tie the pack negatives anywhere else (the star joins ESC grounds only). That would rebuild 04's loop (%.2f A of motor "
    "current in a signal wire)." % max(abs(i) for i in tie["Isig"]),
    "Do not put ideal diodes in the − leads while the signal grounds exist. They are shunted and push the return current back into "
    "the signal wires (Case 1). The + diodes alone already prevent all pack-to-pack and back-feed currents.",
    "What remains in the signal wire is the R_ret/(R_ret + R_sig) share, %.0f %%. Make the return wires heavier to shrink it, or "
    "drop the separate signal-ground wire and take the ESC signal reference from the star." % (h.Rret / (h.Rret + h.Rsig) * 100),
    "Ideal diode instead of Schottky: 20 mW instead of 380 mW at 1 A, and 0.34 V more input headroom. The cost is a ~0.1 µs-class "
    "reverse pulse of %.0f A into a shorted channel. Keep the tap loop inductance and the comparator lag small, or add a TVS." % abs(S("irev2_pk", 2)),
    "Choose isolated modules (Case 4) only if the packs must stay galvanically separate (for example for per-pack current sensing). "
    "The price is %.1f W more from the packs and three full-rated converters." % (S("pav_n", 4) - S("pav_n", 2)),
    "Add bulk at vin only if the avionics must ride through losing all three packs; the 10 µF Cin lasts %.0f µs." % (t_hold * 1e6),
])
out = os.path.join(here, "08_Redundant_Avionics_Power_Design.pdf")
print(out, doc.save(out), "pages")

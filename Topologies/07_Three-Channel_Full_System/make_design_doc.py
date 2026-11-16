"""Builds 07_Three-Channel_Full_System_Design.pdf: hand calculations + LTspice results for topology 07."""
import os, sys, math, json, re
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, "..", "tools")); sys.path.insert(0, here)
from designdoc import Doc, INK, INK2, ACCENT
from ltraw import read_meas
from matplotlib.patches import FancyBboxPatch
import hand_calc as H


def meas(log):
    """read_meas, plus the time of WHEN measurements (read_meas returns the value at the crossing, not the time)."""
    path = os.path.join(here, log)
    m = {k: v[0] for k, v in read_meas(path).items()}
    txt = open(path, 'rb').read().replace(b'\x00', b'').decode('utf-8', 'ignore').replace('\r', '')
    for mm in re.finditer(r'^(\w+): [^\n]*? AT ([-\d.eE+]+)', txt, re.M):
        m[mm.group(1).lower() + '@'] = float(mm.group(2))
    return m


F = meas("FullSystem_Flight.log")
P = meas("FullSystem_PlugIn.log")
ex = json.load(open(os.path.join(here, "extra_metrics.json")))
S, B, SYS = H.system()
HU = H.holdup()
PL = [H.plugin(k) for k in range(3)]
SP = [H.spinup(k) for k in range(3)]

doc = Doc("07  Full System: 3 Packs → 3 Motors",
          "Topologies 03–06 together: 3 protected channels, 3 switching FOC ESCs (14k / 20k / 10k RPM), 5 V BEC on ch1")

# ---------------------------------------------------------------- 1
doc.h("1. What is being simulated")
doc.p("This topology puts everything from 03 to 06 into one LTspice model. Each of the three channels is a complete power path: a 4S "
      "pack with 20 mΩ internal resistance, the 14 AWG harness of topology 04, the back-to-back MOSFET protection of topology 05 in the "
      "negative line, the ESC's DC link (10 µF ceramic + 470 µF electrolytic), a real switching three-phase inverter (6 VDMOS FETs, "
      "48 kHz complementary PWM with 100 ns dead time) and the sensored FOC controller of topology 03 driving its own PMSM and prop. "
      "The BEC of topology 06 hangs on channel 1's ESC bus and feeds the 5 V avionics (3 A) at the flight controller (FC).")

def block(ax):
    ax.set_xlim(0, 10); ax.set_ylim(0, 3.3)
    boxes = [(0.0, "pack {n}", ["15.2 V", "15.0 V", "14.8 V"]), (1.65, "harness {n}", ["10 cm, 47 nH", "30 cm, 140 nH", "60 cm, 770 nH"]),
             (3.3, "Q1|Q2", ["soft-start, rev. pol."] * 3), (4.95, "DC link", ["500 µF", "480 µF", "480 µF"]),
             (6.6, "inverter + FOC", ["14,000 RPM", "20,000 RPM", "10,000 RPM"]), (8.25, "PMSM + prop", ["2300KV, k·ω²"] * 3)]
    for row, y in enumerate((2.35, 1.35, 0.35)):
        for x, t, sub in boxes:
            ax.add_patch(FancyBboxPatch((x, y), 1.45, 0.62, boxstyle="round,pad=0.02,rounding_size=0.06", fc="#eef4fc", ec=ACCENT, lw=0.9))
            ax.text(x + 0.72, y + 0.38, t.format(n=row + 1), ha="center", fontsize=7.5, weight="bold", color=INK)
            ax.text(x + 0.72, y + 0.13, sub[row], ha="center", fontsize=6.5, color=INK2)
        for x in (1.45, 3.1, 4.75, 6.4, 8.05):
            ax.annotate("", (x + 0.2, y + 0.31), (x, y + 0.31), arrowprops=dict(arrowstyle="->", color=INK2, lw=0.8))
    ax.text(5.67, 3.12, "BEC 5 V / 3 A (averaged) on channel 1's bus  →  flight controller", ha="center", fontsize=7.5, color=ACCENT)
    ax.annotate("", (5.67, 2.99), (5.67, 3.05), arrowprops=dict(arrowstyle="-", color=ACCENT))
doc.figure(block, 2.5)
doc.p("The three packs are floating. Their only connection is through the flight-controller ground (LTspice node 0): ESC 2 and ESC 3 "
      "reach it through 26 AWG signal-ground wires (27 mΩ, 200 nH), and ESC 1 through the BEC's 22 AWG ground lead (10.6 mΩ), which "
      "also carries the 3 A avionics return current. Topology 04 showed this is the only safe arrangement. Here it is checked again "
      "with switching inverters, protection FETs and a real avionics return current.")

# ---------------------------------------------------------------- 2
doc.h("2. Two runs, and how run time was kept sane")
doc.p("Three switching inverters force LTspice to resolve every edge of three unsynchronised 48 kHz carriers: about 0.5–1 ns time "
      "steps at the edges and ~100 s of CPU per simulated millisecond. Topology 03 needed 250 ms to spin one motor up, which would "
      "take days here. So the scenarios are split into two runs, and each run is made as short as the physics allows:")
doc.bullets([
    "Run 1, FullSystem_PlugIn (20 ms): the three packs are plugged in 1 ms apart, the protection FETs soft-start the DC links, the BEC "
    "starts, and at 10 ms the ESCs arm and begin a 120 ms speed ramp. Only the first 10 ms of spin-up are simulated: enough to check "
    "the start-up currents. Before arming the inverters do not switch, so this part is fast.",
    "Run 2, FullSystem_Flight (24 ms): the motors start at speed. .ic V(omega_k) and V(theta_k) set the rotors, .ic I(La..Lc) sets the "
    "phase currents of the hand-calculated operating point, and the PI integrators are pre-loaded with idt(x, ic) so that iq starts "
    "at its steady value. Steady flight 4–8 ms, throttle punch on motor 3 at 8 ms, pack 1 pulled out at 16 ms.",
    ".save keeps only the ~70 traces that are plotted or measured. The flight .raw is still about 2.5 GB, so plot_results.py "
    "opens it with np.memmap and converts only the columns it needs.",
])
doc.p("Why the BEC is averaged. The real BEC (topology 06) switches at 500 kHz with ~2 ns edges, ten times the ESC frequency. In this model "
      "it would set the time step for all 24 ms of the run. What the ESC bus sees of the BEC is its input power, about 15 W, drawn as "
      "a constant power because the BEC regulates its output. 06 showed that its loop crosses over at 53 kHz with 57° margin, so "
      "for anything slower than ~20 µs the averaged model is exact:")
doc.eq(r"V_{5} = ss\cdot\min(V_{set},\ D_{max}V_{in}) \qquad I_{in} = \frac{V_{5}\,I_{out}}{\eta\,V_{in}} \qquad \eta = 0.97\ (06\ \mathrm{at}\ 3\,A)", size=12)
doc.p("It keeps what matters at system level: the negative incremental input resistance (−V²/P), the dropout below 5.25 V input, the "
      "under-voltage lockout (6 V) and the soft-start. It drops the 500 kHz input ripple (06: tens of mA in its own 20 µF, invisible "
      "next to the ESC's 48 kHz ripple) and the loop's own dynamics.")

# ---------------------------------------------------------------- 3
doc.h("3. Steady flight: the power chain by hand")
doc.p("The speed loop sets the speed, so everything follows from the prop: T = kω² + Bω, iq = T/Kt with Kt = 1.5·Kph = %.3f mN·m/A "
      "(topology 03). The mechanical power is Tω, and the copper loss in the dq frame is 1.5·R·iq²:" % (H.Kt * 1e3))
doc.eq(r"i_q = \frac{k\omega^2 + B\omega}{K_t} \qquad P_{mech} = T\omega \qquad P_{cu} = \frac{3}{2}R_{ph}i_q^2", size=12)
doc.p("The inverter loss has five parts. For a sine of amplitude iq the mean of |i| is (2/π)·iq. One FET of each leg always carries the "
      "phase current (Ron = %.2f mΩ at 10 V gate drive). During the two dead times per period a body diode conducts. At each hard "
      "turn-on the opposite body diode's stored charge Qrr = Tt·I (charge-control model, Tt = 20 ns) and the output charge are dumped "
      "into the FET. Each turn-on and turn-off also overlaps V and I for t ≈ Qgd·Rg/(Vdrv − Vplat) and Qgd·Rg/Vplat:" % (H.ron_esc * 1e3))
doc.eq(r"P_{esc} = \frac{3}{2}i_q^2R_{on} + 6T_{dead}f_{sw}V_F\bar{|i|} + 3V_{bus}T_t\bar{|i|}f_{sw} + \frac{3}{2}V_{bus}\bar{|i|}(t_{on}+t_{off})f_{sw} + 3Q_{oss}V_{bus}f_{sw}", size=10.5)
doc.p("The DC link adds one more loss. The inverter draws its current in 48 kHz pulses, and the AC part (Kolar's formula from topology 04: "
      "%.1f / %.1f / %.1f A rms) flows mostly in the electrolytic's 30 mΩ ESR: %.2f / %.2f / %.2f W." % (tuple(s["Ic"] for s in S) + tuple(s["pcap"] for s in S)))
doc.p("Then the bus has to supply Pbus = Pinv + Pcap (plus the BEC on channel 1), with Pinv = Pmech + Pcu + Pesc, through the total series resistance Rtot = Rint + "
      "Rloop + 2·Ron,prot. Constant power into a source with series resistance is a quadratic:")
doc.eq(r"P = (V_b - IR_{tot})\,I \;\Rightarrow\; I = \frac{V_b - \sqrt{V_b^2 - 4R_{tot}P}}{2R_{tot}} \qquad R_{on,prot} = R_d + R_s + \frac{1}{K_p(V_{GS} - V_{to})} = %.2f\ \mathrm{m\Omega}" % (H.ron_prot(12) * 1e3), size=11)
rows = []
for k, s in enumerate(S):
    rows.append([f"ch{k+1}  {H.RPM[k]:,} RPM", f"{s['iq']:.2f}", f"{s['pm']:.1f}", f"{s['pcu']:.2f}", f"{s['esc']['total']:.2f}",
                 f"{s['pinv']:.1f}", f"{s['pin']:.1f}", f"{s['Rtot']*1e3:.1f}", f"{s['I']:.3f}", f"{s['Vbus']:.3f}"])
doc.table(["channel", "iq (A)", "Pmech", "Pcu", "Pesc", "Pinv (W)", "Pbus (W)", "Rtot (mΩ)", "Ibat (A)", "Vbus (V)"], rows,
          widths=[0.19, 0.08, 0.08, 0.07, 0.07, 0.1, 0.1, 0.11, 0.1, 0.10])
doc.p("The BEC (averaged): Iout = 4.984 V / (Rout + 2·Rlead + Ravionics) = %.3f A, so the FC sees %.3f V: the 22 AWG leads drop %.0f mV. "
      "Its input power is 4.984·Iout/0.97 = %.2f W. The system efficiency, prop shaft + avionics power over the chemical power Vb·I of "
      "the three packs, is %.1f / %.1f = %.1f %%." % (B["iout"], B["v5fc"], (B["v5esc"] - B["v5fc"]) * 1e3, B["pin"], SYS["puse"], SYS["pchem"], SYS["eff"] * 100))

doc.h("4. Steady flight: hand calculation vs. LTspice (4–8 ms)")
rows = []
def add(lab, h, sv, fmt, rel=True):
    if rel:
        e = (sv / h - 1) * 100 if h else float('nan'); d = "0.0 %" if abs(e) < 0.05 else f"{e:+.1f} %"
    else:
        d = fmt.format(sv - h)
    rows.append([lab, fmt.format(h), fmt.format(sv), d])
for k, s in enumerate(S):
    n = k + 1
    add(f"ch{n} speed (RPM)", H.RPM[k], F[f"rpm{n}_ss"], "{:,.0f}")
    add(f"ch{n} iq (A)", s["iq"], F[f"iq{n}_ss"], "{:.2f}")
    add(f"ch{n} shaft power (W)", s["pm"], F[f"pmech{n}_ss"], "{:.2f}")
    add(f"ch{n} copper loss (W)", s["pcu"], F[f"pcu{n}_ss"], "{:.2f}")
    add(f"ch{n} inverter input power (W)", s["pinv"], F[f"pinv{n}_ss"], "{:.2f}")
    add(f"ch{n} battery current (A)", s["I"], F[f"ibat{n}_ss"], "{:.3f}")
    add(f"ch{n} bus voltage (V)", s["Vbus"], F[f"vbus{n}_ss"], "{:.3f}")
    add(f"ch{n} harness drop, + and − (mV)", s["harn"] * 1e3, F[f"vharn{n}_ss"] * 1e3, "{:.1f}")
    add(f"ch{n} protection FET loss (mW)", s["Pprot"] * 1e3, F[f"pprot{n}_ss"] * 1e3, "{:.1f}")
doc.table(["Quantity", "Hand calc", "LTspice", "Difference"], rows, widths=[0.46, 0.18, 0.18, 0.18])
rows = []
add("BEC input power (W)", B["pin"], F["pbec_ss"], "{:.2f}")
add("5 V at the flight controller (V)", B["v5fc"], F["v5_ss"], "{:.3f}")
add("BEC ground-lead current |Isig1| (A)", B["iout"], abs(F["isig1_ss"]), "{:.3f}")
add("Signal-ground current ch2 (mA)", 0.0, F["isig2_ss"] * 1e3, "{:.3f}", rel=False)
add("Signal-ground current ch3 (mA)", 0.0, F["isig3_ss"] * 1e3, "{:.3f}", rel=False)
pchem = sum(H.VB[k] * F[f"ibat{k+1}_ss"] for k in range(3))
puse = sum(F[f"pmech{k+1}_ss"] for k in range(3)) + F["p5_ss"]
add("Chemical power of the 3 packs (W)", SYS["pchem"], pchem, "{:.1f}")
add("System efficiency (shaft + avionics) (%)", SYS["eff"] * 100, puse / pchem * 100, "{:.1f}")
doc.table(["Quantity", "Hand calc", "LTspice", "Difference"], rows, widths=[0.46, 0.18, 0.18, 0.18])
EXPLAIN_STEADY = [
    "Copper loss is 1–5 % high. The hand value uses the fundamental only; the 48 kHz PWM ripple in the phase currents adds its own "
    "R·I² (relatively most for motor 3, which carries the least current).",
    "Protection-FET loss is %.0f %% high on channel 1. The loss goes as the RMS battery current squared, not the mean squared. Channel 1's "
    "short harness (47 nH) lets more of the PWM ripple reach the pack: Irms = %.2f A vs Iavg = %.2f A, and (%.2f/%.2f)² = %.2f, which "
    "accounts for the whole difference. The FETs are still loafing: 33 mW at 4 A." % ((F["pprot1_ss"] / S[0]["Pprot"] - 1) * 100,
    F["ibrms1_ss"], F["ibat1_ss"], F["ibrms1_ss"], F["ibat1_ss"], (F["ibrms1_ss"] / F["ibat1_ss"]) ** 2),
    "Before the DC-link ESR term was added, the battery currents came out 0.4–0.9 %% low. The measured Ibat·Vbus − Pinv on channel 2 is "
    "%.2f W against %.2f W from Kolar's ripple. The link capacitor is a real, small loss of its own." % (F["ibat2_ss"] * F["vbus2_ss"] - F["pinv2_ss"], S[1]["pcap"]),
    "The ESC-loss estimate (switching from a guessed Qgd = 6 nC, recovery from Qrr = Tt·I) cannot be checked on its own, but the "
    "inverter input power, which contains it, agrees to 0.05 %. That is only 0.3–2 W out of 15–130 W, so it is a weak test.",
    "Signal-ground currents of channels 2 and 3 average about 1e-11 A. KCL forces them to zero because each pack is a floating loop; the "
    "only return path for ESC k's current is its own pack's negative wire.",
]
doc.p("Notes on the differences:")
doc.bullets(EXPLAIN_STEADY)

# ---------------------------------------------------------------- 5
doc.h("5. Plug-in: three soft-starts at once")
doc.p("Each channel's protection block works exactly as in topology 05. The Miller capacitor turns Q2 into a dV/dt limiter, so each "
      "DC link charges with a constant current set by passives:")
doc.eq(r"t_d = R_g(C_m + C_{gs})\ln\frac{V_b - \Delta V_{GS}}{V_b - V_{plat}} \qquad I_{in} = \frac{(V_b - V_{plat})\,C_{dc}}{R_g C_m} \qquad t_{ramp} = \frac{C_{dc}V_b}{I_{in}} = \frac{R_g C_m V_b}{V_b - V_{plat}}", size=11)
doc.p("Channel 1's DC link is 500 µF (the BEC's 20 µF input capacitor is in parallel), so its inrush is 4 %% higher. The ramp time is "
      "the same for all channels because it does not depend on Cdc. The BEC also starts during channel 1's ramp, once the bus passes its "
      "6 V UVLO. Its ~1–2.5 A flows through Q2 while Q2 still drops Vb − Vbus, which adds about %.1f mJ to that FET's ½CV² of %.1f mJ. After the ramp the "
      "gate keeps charging from the plateau toward the Rg/Rgs Thevenin voltage (%.1f V, τ = %.1f ms) until the 12 V zener clamps it, so "
      "Vgs is only about %.1f V when the ESCs arm at 10 ms." % (PL[0]["Ebec"] * 1e3, PL[0]["E"] * 1e3, PL[0]["Vth"], PL[0]["tau_on"] * 1e3, PL[0]["vgs_at"](10e-3)))
rows = []
for k in range(3):
    n = k + 1; pl = PL[k]
    add(f"ch{n} delay contact → 10 % (ms)", (pl["T10"] - H.TON[k]) * 1e3, (P[f"t10_{n}@"] - H.TON[k]) * 1e3, "{:.2f}")
    add(f"ch{n} contact → 90 % (ms)", (pl["T90"] - H.TON[k]) * 1e3, (P[f"t90_{n}@"] - H.TON[k]) * 1e3, "{:.2f}")
    add(f"ch{n} mean inrush 10–90 % (A)", pl["I_in"] + pl["Ibec"], ex[f"iavg_ramp{n}"], "{:.2f}")
    add(f"ch{n} protection-FET energy (mJ)", (pl["E"] + pl["Ebec"]) * 1e3, P[f"efet{n}"] * 1e3, "{:.1f}")
    add(f"ch{n} Vgs at arming, 10 ms (V)", pl["vgs_at"](10e-3), P[f"vgs{n}_arm"], "{:.2f}")
add("5 V rail ready (V)", B["v5fc"], P["v5_rdy"], "{:.3f}")
doc.table(["Quantity", "Hand calc", "LTspice", "Difference"], rows, widths=[0.46, 0.18, 0.18, 0.18])
EXPLAIN_PLUG = [
    "The inrush is 11 %% under the ideal formula, the same deficit topology 05 found and explained. Part of the gate current goes into "
    "Rgs and into Cgs (the plateau is not perfectly flat). The FET's own voltage-dependent Cgd adds to Cm, which slows the ramp. "
    "So the ramp is about 13 %% longer (%.2f ms 10–90 %% vs %.2f ms) and contact-to-90 %% is about 5 %% late." % (ex["t_ramp2"] * 1e3, 0.8 * PL[1]["t_ramp"] * 1e3),
    "Channel 1 is 14 %% low, not 11 %%. Its BEC current during the ramp comes from a model of the 0.3 ms soft-start filter that is only "
    "approximate. The ramp current climbs to %.1f A at its end, when the BEC is fully running (plot B)." % P["ipk1"],
    "The FET energy is 3 % under ½CV². The FETs' own capacitances (charged through the channel) and the slow tail at the end of the "
    "ramp take a little of the charging energy elsewhere. The bound ½CV² is the right number for the SOA check.",
    "There is no spark: the largest current spike at contact is %.0f mA, compared with 230–270 A for a bare XT60 in topology 04." % (max(ex["ipk_contact1"], ex["ipk_contact2"], ex["ipk_contact3"]) * 1e3),
]
doc.bullets(EXPLAIN_PLUG)

# ---------------------------------------------------------------- 6
doc.h("6. Arming and spin-up")
doc.p("At 10 ms each ESC is enabled and its speed command ramps from 0 at α = ω_target/120 ms. The speed PI plus the rotor inertia is a "
      "type-2 loop, so after the transient it follows a ramp with no error. The torque it needs is then just Jα, and the load torque is "
      "negligible at a few hundred RPM:")
doc.eq(r"i_q \rightarrow \frac{J\alpha}{K_t} = %.1f,\ %.1f,\ %.1f\ \mathrm{A} \qquad P_{bus} \approx \frac{3}{2}R\,i_q^2 + K_t i_q\omega" % tuple(s["iq_ff"] for s in SP), size=12)
doc.p("Only 10 ms of spin-up are simulated, which is less than one period of the 30 Hz speed loop, so iq is still rising toward Jα/Kt. "
      "The fair comparison is a linear model of the same loop (PI with the same Kp and Ki, rotor J, ideal current loop), integrated in "
      "hand_calc.py. That is the dashed line in plot C. At these speeds almost all of the battery power is copper loss: the motor is a "
      "50 mΩ resistor carrying 10–20 A, and the back-EMF is still under a volt.")
rows = []
for k in range(3):
    n = k + 1; sp = SP[k]; m = sp["t"] >= 15e-3
    add(f"ch{n} mean iq 15–20 ms (A), linear model", float(sp["iq"][m].mean()), ex[f"iq{n}_spin"], "{:.2f}")
    add(f"ch{n} speed at 20 ms (RPM), linear model", float(sp["w"][-1] * 30 / math.pi), P[f"rpm{n}_end"], "{:,.0f}")
    m2 = sp["t"] >= 18e-3
    pin = float(sum(H.spin_power(k, w, i, H.VB[k]) for w, i in zip(sp["w"][m2][::50], sp["iq"][m2][::50])) / len(sp["w"][m2][::50]))
    pin += H.bec()["pin"] if k == 0 else 0
    add(f"ch{n} battery current 18–20 ms (A)", H.solve_bus(k, pin, PL[k]["vgs_at"](19e-3))["I"], P[f"ibat{n}_spin"], "{:.2f}")
doc.table(["Quantity", "Hand calc", "LTspice", "Difference"], rows, widths=[0.46, 0.18, 0.18, 0.18])
EXPLAIN_SPIN = [
    "The speed loop matches its linear model to 0.1 % in iq and 0.3 % in speed. The current loop (3 kHz) is effectively ideal on this "
    "time scale, and the 30 A limit is never reached.",
    "Battery current is 1–4 % high. At low speed the duty cycles sit near 50 %, which is exactly where PWM current ripple is "
    "largest (ΔI ≈ Vbus/(4·L·fsw)). The ripple adds copper loss that the fundamental-only hand model misses. It matters most on "
    "channel 2, which runs the most current.",
    "Note the battery current: 2.7 / 3.5 / 0.9 A while iq is 14 / 21 / 10 A. A motor at low speed draws its torque current from the "
    "bus at low duty, so the ESC is a step-down converter here: Ibat ≈ Pbus/Vbus, not iq.",
]
doc.bullets(EXPLAIN_SPIN)

# ---------------------------------------------------------------- 7
doc.h("7. Throttle punch on motor 3")
doc.p("At 8 ms motor 3's speed command steps from 10,000 to 16,000 RPM. The speed PI saturates at once, so iq sits at the 30 A limit, and "
      "the rotor accelerates under a constant motor torque against the growing prop torque:")
w3 = H.RPM[2] * math.pi / 30
doc.eq(r"J\frac{d\omega}{dt} = K_t I_{max} - k\omega^2 - B\omega \qquad \left.\frac{d\omega}{dt}\right|_{10\,000\,RPM} = \frac{%.1f - %.1f}{5\,\mu} = %.0f\ \mathrm{rad/s^2}" % (H.Kt * H.Imax * 1e3, H.load_torque(w3) * 1e3, (H.Kt * H.Imax - H.load_torque(w3)) / H.Jrot), size=11)
doc.p("Integrated numerically, that gives the dashed line in plot D. The bus power at 15 ms follows from the same equations as section 3 "
      "with iq = 30 A: Te·ω + 1.5·R·30² + Pesc. The copper loss alone is 67.5 W, so a punch costs efficiency as well as power.")
w15 = H.punch(w3, H.TPUNCH, 15e-3)
def punch_bus(w, vbus):
    pinv = H.Kt * H.Imax * w + 1.5 * H.Rph * H.Imax ** 2 + H.esc_loss(H.Imax, vbus)["total"]
    vq, vd = H.Rph * H.Imax + H.Kph * w, -H.Pp * w * H.Lph * H.Imax
    return pinv, H.solve_bus(2, pinv + H.cap_loss(2, H.Imax, vq, vd, vbus)[1])
pinv15, b15 = punch_bus(w15, F["vbus3_15"])
w225 = H.punch(w3, H.TPUNCH, 22.5e-3); b225 = punch_bus(w225, F["vbus3_dc"])[1]
w145 = H.punch(w3, H.TPUNCH, 14.5e-3); b145 = punch_bus(w145, F["vbus3_pu"])[1]
rows = []
add("motor 3 speed at 10 ms (rad/s)", H.punch(w3, H.TPUNCH, 10e-3), F["w3_a"], "{:.0f}")
add("motor 3 speed at 15 ms (rad/s)", w15, F["w3_b"], "{:.0f}")
add("motor 3 speed at 23 ms, after pack-1 loss (rad/s)", H.punch(w3, H.TPUNCH, 23e-3), F["w3_d"], "{:.0f}")
add("motor 3 iq during the punch (A)", H.Imax, F["iq3_pu"], "{:.2f}")
add("ch3 inverter input power at 15 ms (W)", pinv15, F["pinv3_15"], "{:.1f}")
add("ch3 battery current at 15 ms (A)", b15["I"], F["ibat3_15"], "{:.2f}")
add("ch3 bus voltage at 15 ms (V)", b15["Vbus"], F["vbus3_15"], "{:.3f}")
add("ch1 bus change, punch vs steady (mV)", 0.0, (F["vbus1_pu"] - F["vbus1_ss"]) * 1e3, "{:.2f}", rel=False)
add("ch2 bus change, punch vs steady (mV)", 0.0, (F["vbus2_pu"] - F["vbus2_ss"]) * 1e3, "{:.2f}", rel=False)
add("motor 1 speed change (RPM)", 0.0, F["rpm1_pu"] - F["rpm1_ss"], "{:.2f}", rel=False)
add("motor 2 speed change (RPM)", 0.0, F["rpm2_pu"] - F["rpm2_ss"], "{:.2f}", rel=False)
doc.table(["Quantity", "Hand calc", "LTspice", "Difference"], rows, widths=[0.46, 0.18, 0.18, 0.18])
EXPLAIN_PUNCH = [
    "The acceleration matches the current-limited ODE to 0.1 % across 15 ms, including the stretch where pack 1 is pulled. Motor 3 "
    "does not notice.",
    "Battery current during the punch is 2 % high, the same ripple-and-ESR story as in steady flight, now at 30 A.",
    "Channel 3's bus sags %.0f mV, which is just ΔI·Rtot = (%.1f − %.1f) A × %.1f mΩ. Its own pack and harness see the punch and "
    "nothing else does: the other buses move by tens of µV and the other motors by a fraction of an RPM. That is the speed loops' own "
    "residual ripple averaged over different windows, not coupling (plot G)." % (-ex["dvbus3_pu_mV"], F["ibat3_pu"], F["ibat3_ss"], S[2]["Rtot"] * 1e3),
]
doc.bullets(EXPLAIN_PUNCH)

# ---------------------------------------------------------------- 8
doc.h("8. Pack 1 pulled out mid-flight")
doc.p("At 16 ms pack 1's + contact opens. From then on ESC 1 and the BEC live on the energy in channel 1's 500 µF DC link. Both are "
      "constant-power loads, so the capacitor energy falls linearly with time:")
doc.eq(r"\frac{1}{2}C\,(V_0^2 - V^2) = P\,t \;\Rightarrow\; t_{UVLO} = \frac{C(V_0^2 - 9^2)}{2(P_{inv1} + P_{BEC})} = \frac{500\,\mu\,(%.2f^2 - 81)}{2\cdot %.1f} = %.2f\ \mathrm{ms}" % (HU["V0"], HU["P1"], HU["t_uvlo"] * 1e3), size=11)
doc.p("ESC 1 reads its bus through a 3 kHz filter, so it stops about τ = 53 µs late, at roughly %.1f V. With the inverter off, only the BEC "
      "is left (%.1f W), and it keeps the 5 V rail regulated until its own 6 V UVLO:" % (HU["v_at"], B["pin"]))
doc.eq(r"t_{BEC} = \frac{C\,(%.2f^2 - 6^2)}{2\cdot %.1f} = %.2f\ \mathrm{ms} \qquad t_{rail} \approx t_{UVLO} + \tau + t_{BEC} = %.2f\ \mathrm{ms}" % (HU["v_at"], B["pin"], HU["t_bec"] * 1e3, HU["t_rail"] * 1e3), size=11)
doc.p("So the flight controller loses power about %.1f ms after the connector lets go. Motor 1 keeps spinning (and slowing) with its "
      "inverter off. Its line-line back-EMF peak is Ke·ω = %.1f V, and the six body diodes rectify it, which sets a floor under the dying "
      "bus. That floor is below the BEC's dropout and UVLO, so it cannot save the rail." % (HU["t_rail"] * 1e3, HU["Vll"]))
rows = []
add("ESC 1 UVLO after the disconnect (ms)", HU["t_uvlo"] * 1e3, (F["t_uvlo1@"] - H.TOFF) * 1e3, "{:.2f}")
add("5 V rail < 4.5 V after the disconnect (ms)", HU["t_rail"] * 1e3, (F["t_v5_45@"] - H.TOFF) * 1e3, "{:.2f}")
add("ch2 bus change, after vs steady (mV)", 0.0, (F["vbus2_dc"] - F["vbus2_ss"]) * 1e3, "{:.2f}", rel=False)
add("ch3 bus 21–24 ms, still accelerating (V)", b225["Vbus"], F["vbus3_dc"], "{:.3f}")
add("ch3 bus change 13–16 → 21–24 ms (mV)", (b225["Vbus"] - b145["Vbus"]) * 1e3, (F["vbus3_dc"] - F["vbus3_pu"]) * 1e3, "{:.1f}")
add("motor 2 speed change (RPM)", 0.0, F["rpm2_dc"] - F["rpm2_ss"], "{:.2f}", rel=False)
add("Peak |Isig| ch2, one time step (mA)", 0.0, F["isig2_max"] * 1e3, "{:.3f}", rel=False)
add("Peak |Isig| ch3, one time step (mA)", 0.0, F["isig3_max"] * 1e3, "{:.3f}", rel=False)
doc.table(["Quantity", "Hand calc", "LTspice", "Difference"], rows, widths=[0.46, 0.18, 0.18, 0.18])
EXPLAIN_LOSS = [
    "The UVLO time matches to 0.2 %. The constant-power discharge model is exact while the FOC loop holds motor 1's power constant.",
    "The rail lasts 3 % longer than predicted. As the BEC's smooth UVLO turns it off, its input power fades over a few hundred "
    "microseconds instead of switching off at exactly 6 V.",
    "Channel 1's bus does not fall to zero: it settles at %.2f V. Motor 1 is now a generator (still %.0f RPM at 21–24 ms), and the "
    "six body diodes rectify its line-line EMF (%.1f V peak) minus two diode drops into the link capacitors. Nothing is drawing current "
    "any more, so the drops are small." % (F["vbus1_floor"], F["rpm1_dc"], HU["Vll"]),
    "Channel 3's bus keeps falling slowly after the pack loss because motor 3 is still accelerating, so its power still rises. The "
    "hand model of that drift agrees to within a few mV. Channels 2 and 3 cannot see channel 1 at all.",
    "Signal-ground spikes: single time points of up to %.1f mA appear throughout the run, at no particular event. With reltol = 1e-3 "
    "and 10–30 A flowing, Newton may leave a few mA of error at any one time step. Averaged over one PWM period they are below 1 µA, and the "
    "4 ms means are 1e-11 A." % (max(F["isig2_max"], F["isig3_max"]) * 1e3),
]
doc.bullets(EXPLAIN_LOSS)

# ---------------------------------------------------------------- 9
doc.h("9. Simulated waveforms")
doc.img(os.path.join(here, "FullSystem_results.png"), width=6.6)

doc.h("10. Simulation craft: what went wrong first")
CRAFT = [
    "First run: ESC bus voltage fed raw into the duty feed-forward and the UVLO. Bus ringing made the duty and the enable react within "
    "nanoseconds, a relaxation oscillation set in (bus 5–25 V), and the time step collapsed to 25 ps. Fix: sense the bus through a "
    "3 kHz RC, as a real ESC's ADC filter does (topology 04 already did this).",
    "Second run: the 2 nH ESL on the ceramic rang with the FETs' output capacitance at every edge. That gave ~30 ps steps, and 0.3 ms took "
    "4 minutes. In hardware this is the commutation loop, a layout problem. Topology 03 left the ceramic ESL out, so this model does "
    "too, and it runs ~70× faster (31 s for 0.3 ms).",
    "Starting at speed is not enough by itself: the PI integrators must start at their steady values (idt(x, ic)), or the "
    "speed loop spends tens of ms re-finding iq. With .ic on omega, theta and the three phase currents, the system is in steady flight "
    "within about 1 ms.",
    "Gear integration (as in 05) for both runs: three asynchronous inverters plus the soft-start FETs are a stiff system. It damps "
    "real ringing slightly, so ringing amplitudes are taken from topology 04, not from here.",
    "LTspice writes 'Total elapsed time' before it evaluates the .meas lines. On a 2 GB raw that takes several minutes, so a script "
    "that waits for that line must also wait for the process to exit.",
    "Run time: plug-in 24 min, flight 46 min (two runs in parallel). Raw files 1.1 GB and 2.1 GB; plot_results.py memory-maps them.",
]
doc.bullets(CRAFT)

doc.h("11. Takeaways")
TAKE = [
    "The three channels are electrically independent. A 30 A punch on one motor moves the other buses by under 0.1 mV and the other "
    "motors by under 1 RPM. Losing a pack does not move the other two at all.",
    "Every steady-flight power, current and voltage is predictable by hand to about 1 % once three things are counted: the inverter "
    "losses, the DC-link capacitor ESR loss and RMS (not mean) currents for I²R in the protection FETs.",
    "End to end, 86 % of the packs' chemical power reaches the props and the avionics. The biggest losses are motor copper (21 W), "
    "the ESCs (3 W) and the packs' own 20 mΩ (1.9 W). The harnesses (0.5 W) and protection FETs (0.2 W) hardly matter.",
    "The protection works in the full system too: about 4.5 A soft-start per channel, no spark, then about 4 V of gate drive when the "
    "ESCs arm. The ESC firmware should wait about 100 ms before allowing full throttle (topology 05).",
    "Single point of failure: with the BEC on channel 1, losing pack 1 kills the flight controller about 1.3 ms later, while motors 2 "
    "and 3 run on blindly at their last command. This is exactly why topology 08 feeds the avionics from all three packs.",
]
doc.bullets(TAKE)

out = os.path.join(here, "07_Three-Channel_Full_System_Design.pdf")
print(out, doc.save(out), "pages")

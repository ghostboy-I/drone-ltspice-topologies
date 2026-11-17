"""Builds 09_24S_FOC_Drive_Low-Voltage_Rails_Design.pdf: hand design + LTspice verification of one 24S channel
(FOC drive with bootstrap gate drive, ESC aux supply, avionics 12 V / 5 V / 3.3 V rails)."""
import os, sys, math, json
import numpy as np
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, "..", "tools")); sys.path.insert(0, here)
from designdoc import Doc, INK, INK2, ACCENT
from ltraw import read_meas
from matplotlib.patches import FancyBboxPatch
import hand_calc as h

md = {k: v[0] for k, v in read_meas(os.path.join(here, "Drive_24S.log")).items()}
mr = read_meas(os.path.join(here, "Rails_Switching.log"))                   # LTspice sorts the list: 72, 88.8, 100.8 V
mq = {k: v[0] for k, v in read_meas(os.path.join(here, "GateCharge.log")).items()}
ex = json.load(open(os.path.join(here, "extra_metrics.json")))
R = lambda k, s=1: mr[k][s]
hv, pu = h.hover(), h.punch(); mp, pm = hv["mp"], pu["mp"]; av = hv["av"]
A, HV, B5 = h.AUX12, h.HV12, h.BEC5
pct = lambda a, b: f"{(b - a) / a * 100:+.1f} %"
f3 = lambda x: f"{x:.3f}"

doc = Doc("09  24S FOC Drive and Low-Voltage Rails",
          "one 24S channel  |  U15XL FOC with bootstrap drive  |  ESC 12 V + 3.3 V  |  avionics 12 V, 5 V, 3.3 V")

# =====================================================================================================================
doc.h("1. What this topology does")
doc.p("Topology 03 drove a small motor from 4S, and 06 made the 5 V avionics rail from the same 4S bus. The real tricopter (Props/01) "
      "runs T-Motor U15XL motors with 54x18 props from 24S packs: 72 V empty, 88.8 V nominal, 100.8 V full. This topology moves the FOC "
      "drive to 24S and builds every low-voltage rail the aircraft needs from the same pack: 12 V for the ESC's gate drivers, 3.3 V for "
      "the ESC's microcontroller, 12 V for the video/telemetry transmitter, 5 V for the flight controller and receiver, and 3.3 V for the "
      "sensors. One of the three identical channels is simulated.")

def block(ax):
    ax.set_xlim(-0.15, 10.05); ax.set_ylim(-0.35, 3.3)
    def box(x, y, w, t, sub, ec=ACCENT, fc="#eef4fc"):
        ax.add_patch(FancyBboxPatch((x, y), w, 0.62, boxstyle="round,pad=0.02,rounding_size=0.06", fc=fc, ec=ec, lw=1))
        ax.text(x + w / 2, y + 0.38, t, ha="center", fontsize=8.5, weight="bold", color=INK)
        ax.text(x + w / 2, y + 0.13, sub, ha="center", fontsize=6.8, color=INK2)
    def arr(x0, y0, x1, y1): ax.annotate("", (x1, y1), (x0, y0), arrowprops=dict(arrowstyle="->", color=INK2, lw=0.9))
    box(0.0, 1.35, 1.3, "24S pack", "72-100.8 V, 30 mΩ")
    box(1.7, 1.35, 1.1, "PDB", "avionics tap")
    box(3.2, 2.45, 1.4, "harness", "8 AWG, 1 m")
    box(5.0, 2.45, 1.5, "ESC DC link", "2.4 mF polymer")
    box(6.9, 2.45, 1.5, "inverter + FOC", "150 V FETs, 20 kHz")
    box(8.7, 2.45, 1.25, "U15XL", "5.65 kW hover")
    box(6.9, 1.6, 1.5, "AUX12 buck", "12 V / 0.5 A", ec="#7b5ab6", fc="#f3effa")
    box(8.7, 1.6, 1.25, "gate drive", "bootstrap + 3.3 V LDO", ec="#7b5ab6", fc="#f3effa")
    box(3.2, 0.5, 1.4, "HV12 buck", "12 V / 5 A", ec="#e07b39", fc="#fdf2ea")
    box(5.0, 0.5, 1.5, "BEC5 = 06", "5 V / 3 A", ec="#e07b39", fc="#fdf2ea")
    box(6.9, 0.5, 1.5, "3.3 V LDO", "sensors 0.5 A", ec="#e07b39", fc="#fdf2ea")
    box(3.2, -0.25, 1.4, "video / telem TX", "12 V 1.5 A", ec="#e07b39", fc="#fdf2ea")
    box(8.7, 0.5, 1.25, "FC + receiver", "5 V 1.8 A", ec="#e07b39", fc="#fdf2ea")
    arr(1.3, 1.66, 1.7, 1.66); arr(2.8, 1.85, 3.2, 2.7); arr(4.6, 2.76, 5.0, 2.76); arr(6.5, 2.76, 6.9, 2.76); arr(8.4, 2.76, 8.7, 2.76)
    arr(6.5, 2.6, 6.9, 1.95); arr(8.4, 1.91, 8.7, 1.91); arr(2.8, 1.5, 3.2, 0.85); arr(4.6, 0.81, 5.0, 0.81); arr(6.5, 0.81, 6.9, 0.81)
    arr(6.5, 0.68, 8.7, 0.68); arr(3.9, 0.5, 3.9, 0.37)
    ax.text(0.0, 0.55, "ESC (one per motor)", fontsize=7.5, color="#7b5ab6"); ax.text(0.0, 0.3, "avionics", fontsize=7.5, color="#e07b39")
doc.figure(block, 3.5)
doc.p("Two rules from earlier topologies shape the tree. (1) Each ESC makes its own 12 V from its own pack. Topology 07 showed that "
      "a shared supply on one pack is a single point of failure, and a dead gate-drive supply means a dead motor. (2) The avionics tap "
      "the pack at the power distribution board (PDB), before the motor harness. The harness inductance then filters the inverter's "
      "ripple before the avionics converter sees it (section 8 measures a factor of 6.6). In the full aircraft, the avionics supply is "
      "fed from all three packs through ideal diodes (topology 08). Here one pack feeds it.")

# =====================================================================================================================
doc.h("2. Scaling the FOC drive to the U15XL")
doc.p("The FOC controller is topology 03 unchanged in structure. Only the motor constants, the gains and the inverter change. "
      "The vendor gives KV and line-line resistance. Three values had to be assumed and are worth measuring:")
doc.table(["Quantity", "Value", "Source"], [
    ["KV, R line-line", f"{h.KV} rpm/V, {h.R_LL*1e3:.0f} mΩ  (Rph = {h.Rph*1e3:.1f} mΩ)", "vendor (ligpower U15XL)"],
    ["Ke, Kph = Ke/√3, Kt = 1.5 Kph", f"{h.Ke:.4f}, {h.Kph:.4f}, {h.Kt:.4f} N·m/A", "topology 03"],
    ["Phase inductance Lph", f"{h.Lph*1e6:.0f} µH", "ASSUMED: measure L line-line / 2"],
    ["Pole pairs", f"{h.Pp} (36N42P)", "ASSUMED: typical of the U15 series"],
    ["Rotor + prop inertia", f"{h.Jrot} kg·m²", "ASSUMED: 2 × 0.47 kg blades as rods"],
    ["Hover (54x18, hot day)", f"{h.RPM_HOVER:.0f} rpm, {h.Q_HOVER} N·m", "Props/01 Phase 2 (BEMT)"],
], widths=[0.36, 0.34, 0.30])
doc.p("A pure R-L-EMF motor model has no iron, bearing or windage loss, so it would be more efficient than the real motor. The missing loss "
      "is calibrated on the vendor's bench point (U15XL + 52x20 prop, 50 % throttle: 98 V, 41.3 A, 1836 rpm, 18.46 N·m). It is modelled "
      "as a drag torque Bfric·ω, so it grows with ω²:")
doc.eq(r"B_{fric} = \frac{V I - Q\omega - \frac{3}{2}R_{ph}\,i_q^2 - P_{ESC}}{\omega^2} = \frac{%.0f - %.0f - %.0f - 20}{%.1f^2} = %.4f\ \mathrm{N\,m\,s}" %
       (h.VEND["V"] * h.VEND["I"], h.VEND["Q"] * h.w_v, h.P_vend_cu, h.w_v, h.Bfric), size=12)
doc.p("At hover the motor makes the prop torque plus the drag, Te = Kprop·ω² + Bfric·ω = %.2f N·m. With id = 0, the dq steady state "
      "(03, section 3) gives the current and the voltage the inverter must make:" % (mp["iq"] * h.Kt))
doc.eq(r"i_q = \frac{T_e}{K_t} = %.1f\ \mathrm{A} \qquad v_d = -\omega_e L i_q = %.2f\ \mathrm{V} \qquad v_q = R i_q + K_{ph}\,\omega = %.2f\ \mathrm{V}" %
       (mp["iq"], mp["vd"], mp["vq"]), size=12)
doc.eq(r"|v| = %.1f\ \mathrm{V}\ \ <\ \ \frac{V_{bus}}{\sqrt{3}} = %.1f\ \mathrm{V} \qquad M = \frac{|v|}{V_{bus}/2} = %.3f" % (mp["vm"], mp["vlim"], mp["M"]), size=12)
doc.p("At ωe = %.0f rad/s the inductive term ωe·L·iq is already half the back-EMF. This is why Lph matters, even though the vendor does "
      "not give it. With L = 40 µH, the thrust-to-weight 2 point (2217 rpm, 205 A) would need %.0f V of the %.0f V available on a sagged "
      "pack, and the drive would need field weakening. The gains follow 03: current PI zero on the R-L pole (Kp = L·ωc, Ki = R·ωc) at "
      "%.0f kHz (fsw/20), speed PI at %.0f Hz." % (h.Pp * h.W_HOVER, math.hypot(h.Pp * h.RPM_TW2 * math.pi / 30 * 40e-6 * 205, 0.1451 * h.RPM_TW2 * math.pi / 30 + 1.7), 84 / math.sqrt(3), h.Fci / 1e3, h.Fcw), size=10)

# =====================================================================================================================
doc.h("3. The inverter at 100 V")
doc.p("A 24S pack reaches 100.8 V, and switching overshoot adds more, so the switches are 150 V parts. Each switch is four 150 V, 4.8 mΩ "
      "FETs in parallel, modelled as one VDMOS ('ESC150'). Its on-resistance at 12 V gate drive is Rd + Rs + 1/(Kp(Vgs − Vto)) = %.2f mΩ. "
      "The losses use the same formulas as 07:" % (h.ron_esc * 1e3))
inv = mp["inv"]
doc.table(["Inverter loss at hover", "Formula", "Hand (W)"], [
    ["Conduction", "3 · Irms² · Ron = 1.5 iq² Ron", f"{inv['cond']:.1f}"],
    ["Switching (hard edges)", "3 · ½ Vbus ⟨|i|⟩ (ton + toff) fsw", f"{inv['sw']:.1f}"],
    ["Body-diode reverse recovery", "3 · Vbus · Tt ⟨|i|⟩ · fsw", f"{inv['rr']:.1f}"],
    ["Dead time + Coss", "3·2·tdead·fsw·Vf⟨|i|⟩ + 3 Qoss Vbus fsw", f"{inv['dead'] + inv['oss']:.1f}"],
    ["Total", "", f"{inv['total']:.1f}"],
], widths=[0.34, 0.46, 0.20])
doc.p("The DC-link capacitors carry the inverter's pulsed current. The Kolar-Round formula (topology 04) gives its RMS value. "
      "With cos φ = vq/|v| and M from section 2:")
doc.eq(r"I_{C,rms} = \frac{i_q}{\sqrt{2}}\sqrt{2M\left[\frac{\sqrt{3}}{4\pi} + \cos^2\varphi\left(\frac{\sqrt{3}}{\pi} - \frac{9M}{16}\right)\right]} = %.1f\ \mathrm{A}" % hv["icap"], size=12)
doc.p("62 A RMS is far beyond a few electrolytics (about 2–3 A each), so the link uses 16 × 150 µF / 125 V hybrid polymer capacitors "
      "(about 3.5 A each, 2.4 mF, 1.25 mΩ). One consequence is the plug-in spark: charging 2.4 mF to 100.8 V dissipates "
      "½CV² = %.1f J in the connector, compared with 0.07 J for topology 04's 4S link. Topology 05's soft-start is not optional at 24S." % h.hotplug_energy())

# =====================================================================================================================
doc.h("4. Gate drive: where the ESC's 12 V goes")
doc.p("Every switching period, each of the six switches has its gate charged to 12 V and discharged again. That charge is the main "
      "load on the ESC's 12 V rail, so it was measured with LTspice's version of the datasheet test (GateCharge.asc): 10 mA constant "
      "into the gate, with the hover current (2/π · iq = 92 A) clamped to 88.8 V.")
doc.img(os.path.join(here, "GateCharge.png"), width=6.6)
doc.eq(r"Q_g \approx C_{gs}V_{drv} + C_{gd,min}V_{ds} + C_{gd,max}(V_{drv} - V_{plat}) = %.0f + %.0f + %.0f = %.0f\ \mathrm{nC}\quad (\mathrm{bench}: %.0f\ \mathrm{nC})" %
       (h.ESC["Cgs"] * 12e9, h.ESC["Cgdmin"] * h.V_NOM * 1e9, h.ESC["Cgdmax"] * (12 - h.VPLAT_HAND) * 1e9, h.qg_esc_hand() * 1e9, mq["qg12"] * 1e9), size=11)
doc.p("The three terms are the three slopes of the curve. Below the plateau the gate charges Cgs. On the plateau (Vgs = %.1f V, "
      "measured %.2f V) the drain falls and all the gate current goes into Cgd (the Miller charge, %.0f nC measured). Above it, the "
      "drain sits near 0 V, so Cgd is at its large value. The first version of the hand formula omitted the third term and came out "
      "13 %% low." % (h.VPLAT_HAND, mq["vplat"], mq["qgd"] * 1e9))
qg = mq["qg12"]; igd = 6 * qg * h.Fsw
doc.eq(r"I_{gate} = 6\,Q_g\,f_{sw} = 6 \times %.0f\ \mathrm{nC} \times 20\ \mathrm{kHz} = %.1f\ \mathrm{mA} \qquad I_{12} = I_{gate} + I_{drv} + I_{MCU} + I_{q} = %.0f\ \mathrm{mA}" %
       (qg * 1e9, igd * 1e3, (igd + h.I_DRV_Q + h.I_MCU + h.IQ_LDO) * 1e3), size=11)
doc.p("The low-side drivers take their charge straight from the 12 V rail. The high-side source floats on the switch node, which swings "
      "0 → 88 V, so its driver runs from a bootstrap capacitor. While the low side is on, the switch node is at 0 V and Cboot charges "
      "from 12 V through Dboot and 2 Ω. While the high side is on, the diode blocks and Cboot alone supplies the gate. Each high-side "
      "turn-on takes Qg from Cboot:")
doc.eq(r"\Delta V_{boot} = \frac{Q_g}{C_{boot}} = \frac{%.0f\ \mathrm{nC}}{1\ \mu\mathrm{F}} = %.2f\ \mathrm{V} \qquad \tau = (R_{boot} + R_s)\,C_{boot} = 2.5\ \mu\mathrm{s} \ll t_{low,min} = (1 - %.2f)/f_{sw}" %
       (qg * 1e9, qg / h.CBOOT, md["du_max"]), size=11)
doc.p("The rule of thumb Cboot ≥ 10·Qg/ΔVmax keeps the droop below 10 %%. The SVPWM duty is clamped at 0.99, so the low side is on at "
      "least 0.5 µs every period and the capacitor always gets topped up. In this design the maximum duty at hover is %.2f, which "
      "leaves %.0f µs, about 3τ. The ESC's 3.3 V comes from a linear regulator on the 12 V rail and burns (12 − 3.3) × 80 mA = "
      "%.2f W, acceptable in a small package with copper." % (md["du_max"], (1 - md["du_max"]) / h.Fsw * 1e6, (12 - 3.3) * h.I_MCU))

# =====================================================================================================================
doc.h("5. Three bucks, one design procedure")
doc.p("Going from 100 V to 5 V in one step would need D = 5/100.8 = 0.05: a 99 ns on-time at 500 kHz, below the minimum on-time of "
      "most 100 V controllers. Two stages avoid this. 100 → 12 V runs at D = 0.12–0.17, so the on-time is 0.5–0.8 µs at 200–250 kHz. "
      "12 → 5 V is topology 06's converter, which is happy at D = 0.42. The 12 V intermediate rail also directly feeds the transmitter, "
      "which wants 12 V anyway. All three bucks follow 06's procedure:")
doc.bullets(["Size L for about 30 % ripple at the highest input voltage, and size C (derated for DC bias) for ripple.",
             "Put the Type III zeros at 0.5 f0 and 0.7 f0, and the poles at min(fESR, fsw/2) and fsw/2.",
             "Solve for R2 so that |T(fc)| = 1, then snap the parts to E96 / E12 values. The same Python code (hand_calc.Buck) designs all three."])
rows = []
for b in h.BUCKS:
    s = b.summary(); ac_ = ex["ac"][f"{b.name}_full"]
    rows.append([b.name, f"{b.vin_min:g}–{b.vin_max:g} → {b.vout:g}", f"{s['D_min']:.3f}–{s['D_max']:.3f}", f"{s['ton_min']*1e9:.0f} ns",
                 f"{b.L*1e6:g} µH / {s['C']*1e6:.1f} µF", f"{s['f0']/1e3:.2f} kHz", f"{b.fsw/1e3:g} kHz"])
doc.table(["Buck", "V in → out", "D range", "min ton", "L / C (derated)", "f0", "fsw"], rows, widths=[0.11, 0.17, 0.15, 0.11, 0.19, 0.13, 0.14])
doc.p("Input feed-forward is what makes this reusable. The PWM ramp amplitude is Vin/10, so the duty is d = vcomp/(Vin/10) and the "
      "modulator-plus-switch gain Vin·∂d/∂vcomp = 10, whatever Vin is:")
doc.eq(r"T(s) = K_{FF}\;\frac{Z_o}{Z_o + DCR + sL}\;H_c(s), \qquad K_{FF} = 10\ \ \mathrm{(no}\ V_{in}\ \mathrm{term)}", size=12)
doc.p("So 06's compensator, designed for a 15.2 V input, still crosses at 53 kHz when fed from 12 V, and the two 100 V bucks hold their "
      "loop over the whole 72–100.8 V pack range. LTspice (Rails_AC.asc, averaged switch, Middlebrook injection) confirms all three:")
rows = []
for b in h.BUCKS:
    for load in ("full", "light"):
        e = ex["ac"][f"{b.name}_{load}"]
        rows.append([f"{b.name}, {'full' if load == 'full' else '10 %'} load", f"{e['fc_hand']/1e3:.1f} kHz / {e['pm_hand']:.1f}°",
                     f"{e['fc']/1e3:.1f} kHz / {e['pm']:.1f}°"])
doc.table(["Loop", "Hand fc / PM", "LTspice fc / PM"], rows, widths=[0.4, 0.3, 0.3])
doc.img(os.path.join(here, "Rails_loop_gain.png"), width=6.6)
doc.p("LTspice's phase margin is about 1° lower because its error amplifier has finite gain (80 dB) and a 10 MHz pole, which the hand "
      "model leaves out. The 100 V bucks' compensation parts are (R2, C1, C2, R3, C3): AUX12 %s, HV12 %s. The 5 V buck keeps 06's "
      "18.7k, 1.8n, 33p, 1.43k, 470p." % (", ".join(f"{x:.3g}" for x in A.parts), ", ".join(f"{x:.3g}" for x in HV.parts)))

# =====================================================================================================================
doc.h("6. Power budget at hover")
l5, l12 = av["l5"], av["l12"]; laux = hv["l_aux"]
doc.table(["Rail", "Load", "Converter loss (W)", "Input (W)"], [
    ["3.3 V sensors (LDO from 5 V)", f"{h.I_SENS} A = {3.3*h.I_SENS:.2f} W", f"LDO {(B5.vset-3.3)*h.I_SENS:.2f}", f"{B5.vset*h.I_SENS:.2f} on 5 V"],
    ["5 V: FC + RX + LDO", f"{av['i5']:.2f} A", f"BEC5 {l5['total_sim']:.2f}", f"{av['p5_in']:.2f} on 12 V"],
    ["12 V avionics: TX + BEC5", f"{av['i12']:.2f} A", f"HV12 {l12['total_sim']:.2f}", f"{av['p12_in']:.2f} at the PDB"],
    ["12 V ESC: gates, LDO", f"{hv['gd']['i12']*1e3:.0f} mA", f"AUX12 {laux['total_sim']:.2f}", f"{hv['p_aux']:.2f} on the DC link"],
    ["Motor drive", f"{mp['p_shaft']:.0f} W shaft", f"drag {mp['p_drag']:.0f}, Cu {mp['p_cu']:.0f}, inv {mp['inv']['total']:.0f}", f"{mp['p_in']:.0f} on the DC link"],
    ["Pack (chemical)", f"{hv['i_pk']:.2f} A", f"pack {hv['p_pk_loss']:.0f}, harness {hv['p_harn']:.0f}", f"{hv['p_chem']:.0f}"],
], widths=[0.29, 0.2, 0.3, 0.21])
doc.p("All the low-voltage electronics together take %.1f W, about 0.5 %% of the 6.6 kW the motor draws. Your propeller study assumed "
      "150 W of avionics, so a payload or companion computer can take up to about 100 W more. The HV12 buck is rated 60 W for that "
      "reason. The bus voltage follows from constant power on a resistive source (07): with the avionics at the PDB and the ESC "
      "after the harness, the hand solution is Vpdb = %.3f V, Vbus = %.3f V." % (av["p12_in"] + hv["p_aux"], hv["vpdb"], hv["vbus"]))

# =====================================================================================================================
doc.h("7. Verification: the drive (Drive_24S.asc)")
doc.p("The switching inverter with real bootstrap drivers runs for 20 ms. It starts at hover (.ic on ω, the phase currents, the harness "
      "current and the bootstrap capacitors, with the PI integrators pre-loaded as in 07), runs steady for 8 ms, then the speed "
      "command jumps to 2217 rpm and iq goes to its 210 A limit. The 0.15 kg·m² rotor needs about 0.5 s to speed up, so the punch "
      "window (14–20 ms) is at hover speed and full current: exactly the electrical worst case.")
dr = ex["drive"]; i_gate = dr["igate_total"]
doc.table(["Quantity (hover 4–8 ms unless noted)", "Hand", "LTspice", "Δ"], [
    ["Speed (rpm)", f"{h.RPM_HOVER:.0f}", f"{md['rpm_h']:.1f}", ""],
    ["iq / id (A)", f"{mp['iq']:.1f} / 0", f"{md['iq_h']:.1f} / {md['id_h']:.2f}", pct(mp["iq"], md["iq_h"])],
    ["vd / vq (V)", f"{mp['vd']:.2f} / {mp['vq']:.2f}", f"{md['vd_h']:.2f} / {md['vq_h']:.2f}", pct(mp["vq"], md["vq_h"])],
    ["DC-link / PDB voltage (V)", f"{hv['vbus']:.3f} / {hv['vpdb']:.3f}", f"{md['vbus_h']:.3f} / {md['vpdb_h']:.3f}", pct(hv["vbus"], md["vbus_h"])],
    ["Pack current (A)", f"{hv['i_pk']:.2f}", f"{md['ipk_h']:.2f}", pct(hv["i_pk"], md["ipk_h"])],
    ["Copper / drag loss (W)", f"{mp['p_cu']:.1f} / {mp['p_drag']:.1f}", f"{md['pcu']:.1f} / {md['pdrag']:.1f}", pct(mp["p_cu"], md["pcu"])],
    ["Inverter loss (W)", f"{mp['inv']['total']:.1f}", f"{md['pfet']:.1f}", pct(mp["inv"]["total"], md["pfet"])],
    ["Drive efficiency (shaft / ESC input)", f"{mp['p_shaft']/hv['p_esc']*100:.2f} %", f"{md['eff_drive']*100:.2f} %", ""],
    ["DC-link capacitor RMS (A)", f"{hv['icap']:.1f}", f"{md['icap_rms']:.1f}", pct(hv["icap"], md["icap_rms"])],
    ["ESC 12 V: gate-drive current (mA)", f"{igd*1e3:.1f}", f"{i_gate*1e3:.1f}", pct(igd, i_gate)],
    ["Bootstrap: Cboot voltage min–max (V)", f"droop {qg/h.CBOOT:.2f}", f"{md['vboot_min']:.2f}–{md['vboot_max']:.2f}", ""],
    ["Punch: iq 10–90 % rise (µs)", f"{h.iq_rise()*1e6:.0f}", f"{ex.get('iq_rise_us', float('nan')):.0f}", ""],
    ["Punch: bus voltage / ESC current", f"{pu['vbus']:.2f} V / {pu['i_esc']:.1f} A", f"{md['vbus_p']:.2f} V / {md['iesc_p']:.1f} A", pct(pu["i_esc"], md["iesc_p"])],
], widths=[0.4, 0.22, 0.24, 0.14])
doc.img(os.path.join(here, "Drive_24S_results.png"), width=6.6)
doc.p("The gate-drive current is %s above 6·Qg·fsw. The difference is the 10 kΩ gate-source resistors (12 V/10 kΩ for half of each "
      "period, 3.6 mA total) and the high-side driver bias (Rbl, 0.3 mA). With those added the prediction is %.1f mA. The inverter loss "
      "is the loosest number (%s): the switching-time estimate uses a two-slope Cgd, and LTspice integrates the real nonlinear one. "
      "The bootstrap swings more than Qg/Cboot because the diode's forward drop depends on the recharge current, which is large "
      "just after the switch node falls and decays with τ = 2.5 µs (bottom-right panel)." %
      (pct(igd, i_gate), (igd + 6 * 0.5 * 12 / 10e3 + 3 * 11.3 / 100e3) * 1e3, pct(mp["inv"]["total"], md["pfet"])))

# =====================================================================================================================
doc.h("8. Verification: the power tree (Rails_Switching.asc)")
doc.p("All three bucks switch, with real FETs and the Type III loops, at 72, 88.8 and 100.8 V. The inverter appears as its DC-link "
      "current: the hover value with the Kolar RMS ripple at 2·fsw, which reproduces Run 2's bus ripple. Sequence: the 12 V rails "
      "soft-start over 0.8 ms; the 5 V buck waits for 12 V power-good (10.8 V) and then soft-starts over 0.5 ms; the motor goes to "
      "hover at 2.0 ms; the transmitter switches on at 2.6 ms; the flight controller steps 0.8 → 1.8 A at 3.0 ms; the punch is "
      "74 → 111 A from 3.8 to 4.6 ms.")
t_hv = 10e-6 + 0.8e-3 * 10.8 / 12; t_5 = t_hv + 0.5e-3 * 4.5 / B5.vset; t_33 = t_hv + 0.5e-3 * 3.25 / B5.vset
i_aux = h.ESC["Qg"] * 6 * h.Fsw + h.I_DRV_Q + h.I_MCU + h.IQ_LDO
la, lh_, lb = A.losses(i_aux), HV.losses(av["i12"]), B5.losses(av["i5"])
dip_vtx = h.I_VTX / (2 * math.pi * ex["ac"]["HV12_full"]["fc"] * (HV.C + 10e-6))
dip_fc = 1.0 / (2 * math.pi * ex["ac"]["BEC5_full"]["fc"] * B5.C)
d_iesc = pu["i_esc"] - hv["i_esc"]
dv_pdb = d_iesc * h.Rpk; dv_bus = d_iesc * (h.Rpk + h.Rh)
s12 = 2 * HV.step_peak(dv_pdb, 0.1e-3); s12e = 2 * A.step_peak(dv_bus, 0.1e-3)
rows = [
    ["12 V rails reach 10.8 V (ms)", f"{t_hv*1e3:.2f}", f"{R('t_aux')*1e3:.2f} / {R('t_hv')*1e3:.2f}"],
    ["5 V reaches 4.5 V / sensor 3.3 V reaches 3.0 V (ms)", f"{t_5*1e3:.2f} / {t_33*1e3:.2f}", f"{R('t_5')*1e3:.2f} / {R('t_33')*1e3:.2f}"],
    ["ESC 12 V / avionics 12 V (V)", f"{A.vset:.3f} / {HV.vset:.3f}", f"{R('v12e'):.3f} / {R('v12a'):.3f}"],
    ["5 V / 3.3 V sensors / 3.3 V ESC (V)", f"{B5.vset:.3f} / 3.290 / 3.298", f"{R('v5'):.3f} / {R('v33'):.3f} / {R('v33e'):.3f}"],
    ["Output ripple HV12 / BEC5 (mV p-p)", f"{HV.ripple()[2]*1e3:.1f} / {B5.ripple()[2]*1e3:.1f}", f"{R('rip12a')*1e3:.1f} / {R('rip5')*1e3:.1f}"],
    ["Inductor ripple AUX12 / HV12 / BEC5 (A)", f"{A.ripple()[1]:.3f} / {HV.ripple()[1]:.2f} / {B5.ripple()[1]:.2f}", f"{R('ilpp_aux'):.3f} / {R('ilpp_hv'):.2f} / {R('ilpp_5'):.2f}"],
    ["Bus ripple: ESC DC link / PDB (V p-p)", f"{h.bus_ripple(hv['icap'], hv['vbus']):.2f} / —", f"{R('rip_bus'):.2f} / {R('rip_pdb'):.3f}"],
    ["Efficiency AUX12 / HV12 / BEC5 (%)", f"{la['eta_sim']*100:.1f} / {lh_['eta_sim']*100:.1f} / {lb['eta_sim']*100:.1f}",
     f"{R('eff_aux')*100:.1f} / {R('eff_hv')*100:.1f} / {R('eff_5')*100:.1f}"],
    ["ESC 12 V ripple from gate pulses, 1 µs avg (mV p-p)", f"{h.ESC['Qg']/A.C*1e3:.0f}", f"{ex['rails']['rip12e_avg']*1e3:.0f}"],
    ["Transmitter on: 12 V dip (mV)", f"{dip_vtx*1e3:.0f}", f"{(R('v12a_pre') - R('dip_vtx'))*1e3:.0f}"],
    ["FC step: 5 V dip (mV)", f"{dip_fc*1e3:.0f}", f"{(R('v5_pre') - R('dip_fc'))*1e3:.0f}"],
    ["Punch: PDB / DC link min (V, incl. ripple)", f"{dv_pdb:.2f} / {dv_bus:.2f}", f"{R('vpdb') - R('vpdb_punch'):.2f} / {R('vbus') - R('vbus_punch'):.2f}"],
    ["Punch, 1 µs avg: 12 V avion. / ESC (mV)", f"{s12*1e3:.1f} / {s12e*1e3:.1f} + ripple",
     f"{ex['rails']['punch_pp_avg']['V(v12a)']*1e3:.0f} / {ex['rails']['punch_pp_avg']['V(v12e)']*1e3:.0f}"],
]
doc.table(["Quantity (88.8 V pack)", "Hand", "LTspice"], rows, widths=[0.5, 0.25, 0.25])
doc.p("Pack voltage range (72 / 88.8 / 100.8 V): the 12 V rails measure %s V (avionics) and %s V (ESC), and the 5 V rail %s V. "
      "HV12 efficiency goes %s %% from empty to full, because switching and Coss loss grow with Vin." % (
          " / ".join(f3(R('v12a', s)) for s in (0, 1, 2)), " / ".join(f3(R('v12e', s)) for s in (0, 1, 2)),
          " / ".join(f3(R('v5', s)) for s in (0, 1, 2)), " → ".join(f"{R('eff_hv', s)*100:.1f}" for s in (0, 1, 2))))
doc.p("The punch sags the PDB by 1.1 V within 0.1 ms. Through the closed loop and the feed-forward, the hand line transfer (section 5, "
      "inverse FFT of Vout/Vin) predicts only %.1f mV p-p on the avionics 12 V, far below its %.0f mV switching ripple. So LTspice's "
      "punch-window numbers are the ripple floor (35 mV avionics, 60 mV ESC), and the punch itself is not visible. That is the result "
      "a feed-forward loop is meant to give." % (s12 * 1e3, R("rip12a") * 1e3))
doc.img(os.path.join(here, "Rails_results.png"), width=6.6)
doc.p("The ESC 12 V rail is the interesting one. Each gate-charge pulse takes Qg = 276 nC from the 11 µF output capacitor, a %.0f mV "
      "step, six times per 50 µs PWM period (120 kHz). That is far above the AUX12 loop's 19 kHz crossover, so the capacitor alone "
      "supplies it. The pulses also beat with the 250 kHz switching (250 − 2 × 120 = 10 kHz), which shows as a slow wobble. The raw "
      "peak-to-peak (%.0f mV) is dominated by 10 ns spikes: 2 A edges through the capacitor's 0.3 nH ESL. On a real board, each gate "
      "driver has its own 1 µF ceramic right at its supply pin, and that capacitor supplies the edge." % (h.ESC["Qg"] / A.C * 1e3, ex["rails"]["rip12e_raw"] * 1e3))
doc.p("Where the numbers differ. AUX12 measures %.1f %% against %.1f %% by hand. At 0.12 A, the fixed losses (Coss charge, the "
      "inductor ripple current circulating through both FETs) are most of the total, and those are the roughest terms in the hand "
      "model. The 12 V rails reach 10.8 V about %.0f µs after the ideal soft-start ramp. Two parts: (1) a loop with one integrator follows "
      "a ramp with a constant time lag of 1/Kv, where Kv = lim s·T(s) = %.2g /s for HV12, so 1/Kv = %.0f µs; (2) about 33 µs before "
      "the output leaves 0 V, while the enable edge passes and the error amplifier comes off its lower clamp (the lag is already 31 µs "
      "at 0.2 V). The 5 V rail is timed from 12 V power-good and inherits the delay. The load-step dips match to within %s." % (
          R("eff_aux") * 100, A.losses(i_aux)["eta_sim"] * 100, (R("t_hv") - t_hv) * 1e6,
          abs(HV.loop(30.0)) * 2 * math.pi * 30, 1e6 / (abs(HV.loop(30.0)) * 2 * math.pi * 30), "15 %"))
doc.p("The hand efficiencies leave out the gate-drive power because the simulation drives its gates from ideal sources. In a real "
      "100 V controller the gate driver runs from an internal regulator fed from Vin, so the gate power is multiplied by Vin/Vdrv. For "
      "HV12 that is (9 + 11) nC × 88 V × 200 kHz = %.2f W, which takes its real efficiency from %.1f %% to about %.1f %%. The 24S "
      "hardware BEC in Hardware/06 counts the same effect and lands at 91.6 %% at 5 V." % (20e-9 * 88 * 200e3, lh_["eta_sim"] * 100,
                                                                                    lh_["pout"] / (lh_["pout"] + lh_["total_sim"] + 20e-9 * 88 * 200e3) * 100))

# =====================================================================================================================
doc.h("9. Takeaways")
doc.bullets([
    "At 24S, the low-voltage rails take about 0.5 % of the motor power. The hard part is not their size but the 100 V input and its ripple.",
    "Go 100 → 12 → 5 V in two stages. A single 100 → 5 V stage would need a 99 ns on-time. The 12 V rail is useful anyway: gate drive and the transmitter want it.",
    "Feed-forward (ramp = Vin/10) makes the loop gain independent of the input. 06's compensator was reused unchanged at 12 V, and the 100 V bucks keep their phase margin from 72 to 100.8 V.",
    "Tap the avionics at the PDB, not at the ESC: the harness inductance reduces the inverter ripple there by about 6.6×.",
    "Each ESC makes its own 12 V from its own pack (07's single-point-of-failure lesson). The gate charge, 6·Qg·fsw = 36 mA, is most of that rail's load. Measure Qg with a gate-charge bench rather than trusting Cgs·V.",
    "Bootstrap: Cboot ≥ 10·Qg/ΔV and a duty clamp below 1 so the low side always tops it up.",
    "At 24S the DC link carries about 62 A RMS and stores 12 J at 100.8 V. Use polymer capacitors and a mandatory soft-start (05).",
])
doc.h("10. What to measure on the real motor and hardware")
doc.bullets(["Line-line inductance (LCR meter at 1 kHz) and the pole count: both set the voltage margin at thrust-to-weight 2.",
             "Rotor + prop inertia (bifilar pendulum, or a spin-down test with the drag model above). It sets the speed-loop gains.",
             "The actual flight controller, receiver and transmitter currents, to replace the assumed 1.8 A at 5 V and 1.5 A at 12 V.",
             "Which ESC: a commercial 24S ESC (Thunder 300A) already contains its own AUX12 and bootstrap drive; this design then informs "
             "the avionics side only."])

n = doc.save(os.path.join(here, "09_24S_FOC_Drive_Low-Voltage_Rails_Design.pdf"))
print("pages:", n)

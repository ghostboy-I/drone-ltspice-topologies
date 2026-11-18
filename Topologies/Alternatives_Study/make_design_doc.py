"""Builds Alternatives_Study.pdf: alternative parts and methods for each section of the ESC and avionics boards,
with the loss math and every number from alternatives_calc.py (python3 make_design_doc.py)."""
import os, sys, math
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, "..", "tools"))
from designdoc import Doc
import alternatives_calc as A

C = A.collect()
H, P = C["ops"]["hover"], C["ops"]["punch"]
F = C["fets"]; base = F["IPB065N15N3 G (today)"]
LH, LP = C["links"]["hover"], C["links"]["punch"]
INK, INK2, GRID = "#1f1f1e", "#5c5b55", "#d9d8d2"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]     # validated default categorical order


def loss_chart(path):
    keys = list(F)
    comps = [("cond", "conduction"), ("sw", "switching"), ("oss", "Qoss"), ("rr", "reverse recovery"), ("dead", "dead time")]
    fig, axs = plt.subplots(1, 2, figsize=(10, 4.2), sharey=True)
    for ax, op, title in ((axs[0], "hover", f"Hover (iq {H['iq']:.0f} A)"), (axs[1], "punch", f"Punch (iq {P['iq']:.0f} A)")):
        for i, k in enumerate(keys):
            left = 0
            for j, (c, lab) in enumerate(comps):
                v = F[k][op][c]
                ax.barh(i, v, left=left, height=0.62, color=SERIES[j], edgecolor="white", linewidth=1.5,
                        label=lab if (i == 0 and op == "hover") else None)
                left += v
            ax.text(left + 3, i, f"{left:.0f} W", va="center", fontsize=8.5, color=INK)
        ax.set_title(title, fontsize=10, color=INK, loc="left")
        ax.set_xlim(0, 245); ax.set_xlabel("inverter loss per ESC (W)", fontsize=9, color=INK2)
        ax.grid(axis="x", color=GRID, linewidth=0.6); ax.set_axisbelow(True)
        for s in ("top", "right"): ax.spines[s].set_visible(False)
        ax.tick_params(colors=INK2, labelsize=8.5)
    axs[0].set_yticks(range(len(keys)))
    axs[0].set_yticklabels([f"{k}  ×{A.FETS[k]['n']}" for k in keys], fontsize=8.5, color=INK)
    axs[0].invert_yaxis()
    fig.legend(loc="lower center", ncol=5, fontsize=8.5, frameon=False, bbox_to_anchor=(0.55, -0.01))
    fig.tight_layout(rect=(0, 0.07, 1, 1)); fig.savefig(path, dpi=160); plt.close(fig)


chart = os.path.join(here, "inverter_losses.png"); loss_chart(chart)

doc = Doc("Parts Alternatives: ESC + Avionics",
          "a trade study for every section of topology 10/11, judged at the 24S hover and punch operating points")

doc.h("1. What this study does")
doc.p("Each section of the two boards was compared with the parts and methods that could replace it. Every alternative "
      "is judged at the same operating points as topology 09 (one U15XL on 24S), and one loss method is applied to "
      "every part, so the comparison is fair even where the absolute numbers carry assumptions. Device numbers are "
      "datasheet typicals; the sources are listed at the end and in README.md. Run python3 alternatives_calc.py to "
      "reproduce every number.")
doc.table(["Operating point", "iq (A peak)", "Vbus (V)", "DC-link ripple (A rms)", "Inverter loss, 09 model (W)"], [
    ["Hover", f"{H['iq']:.1f}", f"{H['vbus']:.2f}", f"{H['icap']:.1f}", f"{H['m09']['total']:.1f}"],
    ["Throttle punch", f"{P['iq']:.1f}", f"{P['vbus']:.2f}", f"{P['icap']:.1f}", f"{P['m09']['total']:.1f}"],
], widths=[0.22, 0.15, 0.13, 0.24, 0.26])

doc.h("2. Summary: what to change, in order")
doc.p("Status: the first three items are fixed in the topology 10/11 boards (24 DC-link capacitors, ACS772ECB-250B, "
      "LTC4366 surge stopper verified by Avionics_SurgeTest.asc). The rest are options, not applied.", size=9.5)
doc.bullets([
    f"DC-link capacitors are under-rated (section 5). The 16 hybrid-polymer caps carry {LH['per']:.2f} A rms each at "
    f"hover ({LH['ratio']:.2f}× the 3.5 A spec) and {LP['per']:.2f} A at punch. Use about {LH['need']} caps, or a "
    "higher-ripple part, or add film / MLCC.",
    "Current sensors run out of range at punch (section 4). The ACS770-200B is specified to ±200 A and the punch "
    "current is 210 A. ACS772ECB-250B uses the same CB footprint and covers ±250 A.",
    "Avionics TVS (section 7). SMBJ110A clamps to 177 V at its rated pulse current, above the LTC7801's 150 V maximum. "
    "Use a surge stopper (LTC4366) or size the clamp so it stays below 150 V.",
    f"Inverter FETs (section 3). OptiMOS 5 stores 6 to 11 times less reverse-recovery charge than IPB065N15N3. With the same "
    f"24 FETs, IPB044N15N5 cuts hover loss from {base['hover']['total']:.0f} W to "
    f"{F['IPB044N15N5']['hover']['total']:.0f} W, but needs a TO-263-7 footprint.",
    f"Gate resistors (section 3). Going from 10 Ω to 3.3 Ω per FET saves "
    f"{base['hover']['total'] - F['IPB065N15N3 G, 3.3 ohm Rg']['hover']['total']:.0f} W at hover for free; check the "
    "ringing on the first board.",
    "Keep the LTC7063 gate drivers and the LTC7801 aux supply. The alternatives found are either weaker, rated too "
    "close to the 100.8 V bus, or being discontinued (sections 3 and 6).",
    "Method changes worth a look: a sensorless flux observer instead of the encoder, and DroneCAN instead of DShot "
    "(section 8).",
])

doc.pagebreak()
doc.h("3. Inverter MOSFETs (24 × IPB065N15N3 today)")
doc.p("The candidates are 150 V parts (the bus is 100.8 V at full charge, so 150 V keeps the usual 2/3 derating). "
      "OptiMOS 5/6 are Infineon's newer silicon; EPC2305 is a 150 V GaN FET with no body diode.", size=9.5)
rows = []
for k, f in A.FETS.items():
    if "3.3 ohm" in k: continue
    rows.append([k.replace(" G (today)", " (today)"), f["pkg"].replace(" (HSOF-8)", "").replace(" (D2PAK)", ""),
                 f"{f['rds']*1e3:.1f} / {f['rds_max']*1e3:.1f}", f"{f['qg']*1e9:.0f}", f"{f['qsw']*1e9:.1f}",
                 f"{f['qoss']*1e9:.0f}", f"{f['qrr']*1e9:.0f}", f["qrr_at"].replace(" (no body diode)", "")])
doc.table(["Part", "Package", "Rds mΩ", "Qg", "Qsw", "Qoss", "Qrr", "Qrr test"], rows,
          widths=[0.22, 0.14, 0.11, 0.06, 0.06, 0.07, 0.07, 0.27])
doc.p("Rds: typical / maximum at 10 V (EPC2305 at 5 V), 25 °C. Charges in nC; Qoss at 75 V.", size=8.5)
doc.p("Loss method (three-phase, sinusoidal current of amplitude iq, n FETs in parallel per switch, fsw = 20 kHz, "
      "mean |i| = 2 iq / π):", size=9.5)
doc.eq(r"P_{cond} = \frac{3}{2}\, i_q^2\, \frac{k_T R_{DS}}{n} \qquad "
       r"P_{sw} = \frac{3}{2} V_{bus} \frac{2 i_q}{\pi} (t_{on}+t_{off}) f_{sw}", size=12)
doc.eq(r"t_{on} = \frac{Q_{sw}(R_{g,ext}+R_{g,int}+n R_{up})}{V_{drv}-V_{pl}} \qquad "
       r"t_{off} = \frac{Q_{sw}(R_{g,ext}+R_{g,int}+n R_{dn})}{V_{pl}}", size=12)
doc.eq(r"P_{oss} = 3 n Q_{oss} V_{bus} f_{sw} \qquad P_{rr} = 3 n Q_{rr} V_{bus} f_{sw} \qquad "
       r"P_{dead} = 6\, t_{dead} f_{sw} V_{SD} \frac{2 i_q}{\pi}", size=12)
doc.p(f"kT = {A.HOT_SI} for silicon and {A.HOT_GAN} for GaN (Rds(on) at Tj ≈ 110 °C, an assumption). LTC7063 at "
      "10 V drive: 1.5 Ω pull-up, 0.8 Ω pull-down, 10 Ω per FET, 300 ns dead time. GaN case: an LMG1210-class 200 V "
      "half-bridge driver (1.5 A / 3 A at 5 V), 2 Ω per FET, 50 ns dead time. One hard turn-on per phase per period "
      "loses Eoss(own) + Qoss·V − Eoss(other) ≈ Qoss·V.", size=9)
doc.img(chart)
rows = []
for k in F:
    hv, pu = F[k]["hover"], F[k]["punch"]
    rows.append([k.replace(" G (today)", " (today)").replace(" G, 3.3 ohm Rg", ", 3.3 Ω Rg"), str(A.FETS[k]["n"] * 6), f"{hv['cond']:.0f}", f"{hv['sw']:.0f}", f"{hv['rr']:.1f}",
                 f"{hv['total']:.0f}", f"{pu['total']:.0f}", f"{hv['per_fet']:.1f} / {pu['per_fet']:.1f}"])
doc.table(["Part", "FETs", "cond", "sw", "rr", "Hover W", "Punch W", "W/FET h / p"],
          rows, widths=[0.3, 0.07, 0.08, 0.07, 0.07, 0.12, 0.12, 0.17])
doc.p("cond, sw, rr: hover losses in W per ESC (three phases). W/FET: per-FET loss at hover / punch.", size=8.5)
doc.bullets([
    f"Reverse recovery: IPB065N15N3's body diode stores 478 nC; OptiMOS 5 parts store 42-77 nC. That alone is "
    f"{base['hover']['rr']:.1f} W → ~1 W per ESC at hover.",
    f"Switching is set mostly by the 10 Ω gate resistors (t_on {base['hover']['t_on']*1e9:.0f} ns). At 3.3 Ω, t_on "
    f"drops to {F['IPB065N15N3 G, 3.3 ohm Rg']['hover']['t_on']*1e9:.0f} ns. The cost is faster dv/dt and di/dt, so "
    "more ringing, more EMI and more Qrr (Qrr roughly doubles from 500 to 1000 A/µs on IPT025N15NM6).",
    "Fewer, bigger FETs (IPT025N15NM6, 2 per switch) save parts but not loss: each FET carries more gate charge through "
    "the shared driver, so switching gets slower. TOLL's 0.38 K/W junction-to-case still needs a good heatsink path for "
    f"{F['IPT025N15NM6']['punch']['per_fet']:.0f} W per FET at punch.",
    f"GaN roughly halves the loss ({F['EPC2305 (GaN)']['hover']['total']:.0f} W at hover) and the 3 × 5 mm parts are "
    "top-side cooled (0.2 K/W). But it needs a new 5 V driver, a very tight power-loop layout, and gate voltage kept "
    "under the +6 V limit. It is a different board, not a part swap.",
    f"Check on topology 09's model: this method gives {base['hover']['total']:.0f} W at hover for today's FETs, against "
    f"{H['m09']['total']:.0f} W from 09. The difference is the hot Rds(on) (09 used about 4.8 mΩ, the 25 °C value) and "
    "the switching charge: 09's Cgd model gives about 7 nC per FET, the datasheet Qsw is 25 nC. Keep the higher figure "
    "for heatsink sizing until a bench measurement settles it.",
])

doc.pagebreak()
doc.h("3b. Gate drivers (3 × LTC7063 today)")
doc.table(["Driver", "Voltage rating", "Drive"], [
    ["LTC7063 (today)", "140 V supply, BST 150 V abs max", "1.5 Ω up / 0.8 Ω down"],
    ["Infineon 6ED2742S01Q", "VB 160 V, three phases in one QFN32", "1 A / 2 A"],
    ["TI UCC27301A / UCC27211", "HB 120 V abs max", "3.7 A / 4.5 A"],
    ["Infineon IRS2186", "600 V", "4 A / 4 A, 170 ns delay"],
    ["TI LMG1210 (GaN)", "200 V", "1.5 A / 3 A, 10 ns delay"],
], widths=[0.3, 0.4, 0.3])
doc.bullets([
    "LTC7063: keep. Its floating grounds tolerate the source bounce of four paralleled FETs.",
    "6ED2742S01Q: adds a current-sense amp, over-current protection and a charge pump, but distributors list it as "
    "last-time-buy / scheduled for obsolescence. Do not design it in.",
    "UCC27301A / UCC27211: reject. HB = 100.8 V + 10 V gate = 110.8 V leaves 9 V before ringing.",
    "IRS2186: large margin and cheap. Dead time must come from the STM32 timer, and there is no floating ground.",
    "LMG1210: the driver for the GaN option; 5 V UVLO, adjustable dead time.",
])

doc.h("4. Phase current sensing (2 × ACS770LCB-200B today)")
doc.p(f"Phase current amplitude: {H['iq']:.0f} A at hover, {P['iq']:.0f} A at punch. The ACS770-200B is specified "
      f"to ±200 A (10 mV/A, 120 kHz, 100 µΩ conductor), so punch is {P['iq']/A.ACS770_RANGE*100:.0f} % of its range: "
      "outside the linearity and accuracy spec.", size=9.5)
doc.table(["Option", "Range / bandwidth", "Loss per phase at hover"], [
    ["ACS770LCB-200B (today)", "±200 A, 120 kHz", f"{A.shunt_loss(H['iq'], 100e-6):.2f} W (100 µΩ conductor)"],
    ["ACS772ECB-250B", "±250 A, 8 mV/A", "same CB package"],
    ["Shunt + INA241", "CM −5 to 110 V, 1.1 MHz", f"{A.shunt_loss(H['iq'], 100e-6):.2f} W (100 µΩ shunt)"],
    ["Coreless field sensor (ACS37610)", "150 / 250 kHz", "≈0 (beside a busbar)"],
    ["3 low-side shunts", "per leg, ground-referenced", "about half of an inline shunt"],
], widths=[0.36, 0.3, 0.34])
doc.bullets([
    f"ACS772ECB-250B: same footprint; punch is {P['iq']/A.ACS772_RANGE*100:.0f} % of its range. Rescale the ADC "
    "(±2 V for ±250 A).",
    "Shunt + INA241: fast and accurate, but its 110 V common-mode limit is only 9 V above the 100.8 V bus.",
    "Coreless sensor: no insertion loss, but it needs a shaped busbar and care with crosstalk from the other phases.",
    "Low-side shunts: cheapest, and the usual drone-ESC method; the current is visible only while the low FET is on.",
])

doc.h("5. DC-link capacitors (16 × 150 µF 125 V hybrid polymer today)")
doc.p("The inverter's DC-link ripple current (Kolar and Round, SVPWM, sinusoidal currents) flows almost entirely in "
      "the polymer bank: at 20 kHz the 20 µF of ceramics is 0.7 Ω against 3.5 mΩ for the bank.", size=9.5)
doc.eq(r"I_{C,rms} = \frac{i_q}{\sqrt{2}} \sqrt{2M\left[\frac{\sqrt{3}}{4\pi} + \cos^2\varphi\left(\frac{\sqrt{3}}{\pi} - "
       r"\frac{9M}{16}\right)\right]}", size=12)
doc.table(["Point", "I_C rms (A)", "Per cap (A)", "× spec", "Loss/cap", f"Caps at {A.CAP_RIPPLE*A.K_FREQ:.1f} A"], [
    ["Hover", f"{H['icap']:.1f}", f"{LH['per']:.2f}", f"{LH['ratio']:.2f}", f"{LH['p_each']*1e3:.0f} mW", str(LH["need"])],
    ["Punch", f"{P['icap']:.1f}", f"{LP['per']:.2f}", f"{LP['ratio']:.2f}", f"{LP['p_each']*1e3:.0f} mW", str(LP["need"])],
], widths=[0.12, 0.15, 0.14, 0.15, 0.16, 0.28])
doc.p(f"{A.K_FREQ} is an assumed ripple multiplier below 100 kHz; read the real one from the chosen series' table. "
      "Punch lasts seconds, so the thermal rating can be judged on hover, but hover alone is already over the spec. "
      f"Options: about {LH['need']} caps; a higher-ripple 125 V hybrid series (Nichicon's GY family goes to 125 V); or move part "
      "of the ripple to film or to a larger MLCC bank (MLCCs at 100 V keep only about half their capacitance).", size=9.5)

doc.pagebreak()
doc.h("6. ESC aux supply (LTC7801 + BSC520/BSC360 + BSP89 today)")
rows = []
for k, a in C["aux"].items():
    rows.append([k.replace(" (today)", "").replace(" (TI, 120 V abs max)", " (TI)").replace(" (ADI, 140 V)", " (ADI)"), f"{a['vmax']} V", f"{a['eff']*100:.0f} %" if a["eff"] else "—",
                 f"{a['pin']:.2f} W" if a["pin"] else "—", str(a["parts"])])
doc.table(["Option", "Max VIN", "Efficiency", "Pin", "Parts"], rows, widths=[0.44, 0.14, 0.14, 0.14, 0.14])
doc.p("Efficiency at 12 V / 0.12 A from 100 V: LTC7801 from the topology 10 hand calc; LM5169 read from TI's Fig. 8-16 "
      "(500 kHz); LTC7138 not checked. Today's design is the LTC7801 with BSC520/BSC360 FETs and the BSP89 pre-regulator.",
      size=8.5)
doc.p("The single-chip bucks save about half the parts and board area, but the LM5169's 120 V absolute maximum sits "
      "right at the 118.8 V OVLO this board already guards against, and at 100 V in it is less efficient. The LTC7138 "
      "(140 V, 400 mA) has the margin and is the one to try if the aux area must shrink. The 0.2 W difference is "
      "small next to the inverter.", size=9.5)

doc.h("7. Avionics board input and 12 V rail")
doc.p(f"SMBJ110A: stand-off {A.TVS['vrwm']} V, breakdown ≥ {A.TVS['vbr_min']} V, clamp {A.TVS['vc']} V at "
      f"{A.TVS['ipp']} A. The LTC7801 is rated to {A.LTC7801_VMAX} V, so any surge that drives more than a small "
      "current into the TVS can exceed it.", size=9.5)
doc.bullets([
    "LTC4366 surge stopper: floats on the supply (9 V to over 500 V), drives an external N-FET to cap the output during "
    "a surge, with a fault timer. Set it to about 115 V and the LTC7801 never sees the spike.",
    "Or a larger TVS (SMCJ / 5.0SMDJ class) whose clamp at the expected surge current stays under 150 V, plus an RC or "
    "LC filter ahead of it.",
    "Isolated 4:1 brick instead of the LTC7801 (TRACO TEN 40-7212WIR, Cincon ECLB40W-110S12): 43-160 V in, 12 V "
    "3.33 A, about 90 % efficient, 1.6-3 kV isolation, protections built in. It covers the 2.5 A load, isolates the "
    "flight controller from the motor ground, and absorbs surges to 160 V, at about 2.4 W more loss than the 97.9 % "
    "LTC7801 design.",
    "The ES1D diode-OR is fine at 0.35 A (0.25 W); ideal-diode controllers only pay off at amps.",
])

doc.h("8. Methods")
doc.bullets([
    "Rotor position: drone FOC ESCs normally run sensorless (a flux observer on the measured currents; the nonlinear "
    "observer of Lee, Hong, Nam, Ortega et al., IEEE Trans. Power Electronics, 2010, is the one VESC uses). A propeller "
    "has almost no load at standstill, so open-loop start then the observer works; the AS5047P encoder and its cable "
    "become optional. Some 24S drone ESCs still list a magnetic encoder for low-speed torque.",
    "Flight-controller link: DShot is one-way per motor plus a telemetry wire. DroneCAN (CAN FD) carries throttle, RPM, "
    "current, temperature and faults on one bus, which suits a 3-motor heavy lift. The STM32G431 has an FDCAN; add a "
    "3.3 V CAN transceiver and a 4-pin connector.",
    "Switching frequency: with GaN, 40-60 kHz becomes cheap, which cuts current ripple in the low-inductance motor and "
    "moves acoustic noise out of the audible range.",
    "Current sensing: two Hall sensors (today) versus three low-side shunts. Shunts are cheaper and more accurate but "
    "need the low-side FET on long enough to sample, which limits the modulation index.",
])

doc.h("9. Sources (datasheets read for this study)")
doc.p("Infineon IPB065N15N3 G Rev 2.1; IPB060N15N5, IPB044N15N5, IPT039N15N5, IPT025N15NM6, IPT034N15NM6 datasheets; "
      "EPC2305 datasheet; Infineon 6ED2742S01Q final datasheet V1.2 (2024); TI LM5168/LM5169 SNVSBS7B (Fig. 8-16); "
      "TI INA241 SBOSA30D; Allegro ACS770 datasheet; Allegro ACS772 selection data; TI UCC27301A and LMG1210 product "
      "pages; ADI LTC7063, LTC7138 and LTC4366 data; Littelfuse SMBJ110A; TRACO TEN 40WIR and Cincon ECLB40W listings; "
      "Hobbywing XRotor 24S product pages. Links in README.md.", size=9)

n = doc.save(os.path.join(here, "Alternatives_Study.pdf"))
print("pages:", n)

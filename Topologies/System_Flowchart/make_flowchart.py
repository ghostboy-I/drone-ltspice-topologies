"""Whole-series flow chart of the drone power system, with the part numbers from the topology 10 BOMs.

Writes System_Flowchart.pdf (vector, zoomable), System_Flowchart.png and System_Flowchart.svg.
Every block is tagged with the topology numbers (01-11) where that circuit was designed and verified.
Run:  python3 make_flowchart.py      (checks that every text fits inside its box, and fails if not)
"""
import os
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 364, 252                         # canvas in units of 0.1 inch
fig = plt.figure(figsize=(W / 10, H / 10))
ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, W); ax.set_ylim(0, H); ax.axis("off")
fig.patch.set_facecolor("white")

# ------------------------------------------------------------------ styles
FILL = dict(power="#fde2e0", inv="#ede0f7", drv="#e3ecfb", mcu="#dff3ea", lv="#fff1d6", sense="#e6f5e0",
            conn="#eeeeee", motor="#e8e8f4", load="#f4f4f4", pack="#fbd3cf", note="#ffffff")
EDGE = dict(power="#b03a2e", inv="#6c3483", drv="#2e5aa8", mcu="#1e8449", lv="#b9770e", sense="#2e8b57",
            conn="#555555", motor="#3f3f7f", load="#555555", pack="#922b21", note="#888888")
WIRE = {"hv": dict(color="#c0392b", lw=3.2), "phase": dict(color="#7d3c98", lw=3.2),
        "lv": dict(color="#d68910", lw=2.0), "sig": dict(color="#2471a3", lw=1.4),
        "sense": dict(color="#229954", lw=1.4), "mech": dict(color="#666666", lw=1.6, ls=(0, (5, 3)))}
boxes = []                              # (patch, [texts]) for the fit check
K = 1.55                                # font scale for the 36 in wide sheet


def box(x0, y0, x1, y1, kind, title, body="", tags="", fs=8.0, tfs=9.5):
    p = FancyBboxPatch((x0, y0), x1 - x0, y1 - y0, boxstyle="round,pad=0,rounding_size=1.2",
                       fc=FILL[kind], ec=EDGE[kind], lw=1.4, zorder=2)
    ax.add_patch(p)
    ts = [ax.text(x0 + 1.4, y1 - 1.3, title, fontsize=tfs * K, weight="bold", va="top", ha="left", zorder=4)]
    if body:
        ts.append(ax.text(x0 + 1.4, y1 - 1.3 - tfs * K * 0.24, body, fontsize=fs * K, va="top", ha="left",
                          linespacing=1.3, zorder=4))
    if tags:
        ts.append(ax.text(x1 - 1.0, y0 + 0.9, tags, fontsize=7 * K, color="#555", va="bottom", ha="right",
                          style="italic", zorder=4))
    boxes.append((p, ts))
    return p


def cluster(x0, y0, x1, y1, label):
    ax.add_patch(FancyBboxPatch((x0, y0), x1 - x0, y1 - y0, boxstyle="round,pad=0,rounding_size=2",
                                fc="#fbfbfb", ec="#444", lw=1.6, ls=(0, (6, 3)), zorder=1))
    ax.text(x0 + 2, y1 - 1.2, label, fontsize=11 * K, weight="bold", va="top", ha="left", color="#333", zorder=4)


def wire(pts, kind, label=None, at=None, ha="center", va="bottom", arrow=True, both=False, fs=7.5):
    st = WIRE[kind]
    xs, ys = zip(*pts)
    ax.plot(xs[:-1] if arrow else xs, ys[:-1] if arrow else ys, solid_capstyle="butt", zorder=3,
            **{k: v for k, v in st.items()})
    if arrow:
        ax.annotate("", xy=pts[-1], xytext=pts[-2], zorder=3,
                    arrowprops=dict(arrowstyle="-|>,head_length=0.9,head_width=0.45", color=st["color"],
                                    lw=st["lw"], ls="-", shrinkA=0, shrinkB=0))
    if both:
        ax.annotate("", xy=pts[0], xytext=pts[1], zorder=3,
                    arrowprops=dict(arrowstyle="-|>,head_length=0.9,head_width=0.45", color=st["color"],
                                    lw=st["lw"], shrinkA=0, shrinkB=0))
    if label:
        x, y = at if at else ((pts[0][0] + pts[1][0]) / 2, (pts[0][1] + pts[1][1]) / 2 + 0.6)
        ax.text(x, y, label, fontsize=fs * K, ha=ha, va=va, color=st["color"], weight="bold", zorder=5,
                bbox=dict(fc="white", ec="none", pad=0.4, alpha=0.85))


# ------------------------------------------------------------------ title
ax.text(W / 2, H - 2.5, "Drone motor power system: the whole series (topologies 01 to 11)", fontsize=30,
        weight="bold", ha="center", va="top")
ax.text(W / 2, H - 7.6, "Three 24S packs drive three independent ESC boards and three U15XL motors. All three packs also "
        "feed one avionics power board through a diode-OR. Part numbers are from the topology 10 BOMs; "
        "topology 11 draws and simulates every part.", fontsize=15, ha="center", va="top", color="#333")

# ------------------------------------------------------------------ left column: series map + legend
box(14, 150, 102, 188, "note", "THE SERIES: where each block was designed",
    "01  Half-bridge leg: one inverter switch pair driving a motor\n"
    "02  3-phase inverter + BLDC, 6-step commutation\n"
    "03  3-phase inverter + PMSM, field-oriented control (FOC)\n"
    "04  3 packs, 3 harnesses, 3 ESCs: DC link, ripple, resonance\n"
    "05  Input protection: anti-spark soft-start, reverse polarity\n"
    "06  Synchronous buck (BEC) design: compensation, feed-forward\n"
    "07  Full 3-pack, 3-motor system (arming, punch, pack loss)\n"
    "08  Avionics fed from all three packs (diode-OR)\n"
    "09  24S drive: bootstrap gate drive, 12 V / 5 V / 3.3 V rails\n"
    "10  Real parts: ESC + avionics boards, BOMs, KiCad\n"
    "11  Whole system drawn part by part and simulated in LTspice\n"
    "Tags like [06 09] on a block = the topologies that cover it", fs=8.6, tfs=10.5)
box(14, 128, 102, 147, "note", "LINE KEY", "", fs=8)
for i, (k, lab) in enumerate([("hv", "pack / DC bus power (88.8 V nominal)"), ("phase", "motor phase current"),
                              ("lv", "low-voltage rail (12 V, 5 V, 3.3 V)"), ("sig", "control / data signal"),
                              ("sense", "measurement (current, voltage, temp)"),
                              ("mech", "mechanical (rotor shaft)")]):
    c, r = i % 2, i // 2
    x, y = 16 + c * 43, 140.5 - r * 4.4
    wire([(x, y), (x + 8, y)], k, arrow=False)
    ax.text(x + 9.5, y, lab, fontsize=7.6 * K, va="center", zorder=5)

# ------------------------------------------------------------------ channel 1, detailed
cy = 207
box(14, 196, 44, 218, "pack", "PACK 1", "24S Li-ion, 55 Ah\n88.8 V nominal, 100.8 V full\nRint 30 mΩ", "[04 09]")
box(50, 199, 70, 215, "power", "PDB 1", "pack 1 bus\ntap to avionics", "[07 08]")
box(76, 199, 102, 215, "power", "HARNESS 1", "8 AWG pair, 1 m\n4.1 mΩ, 0.73 µH", "[04]")
wire([(44, cy), (50, cy)], "hv"); wire([(70, cy), (76, cy)], "hv"); wire([(102, cy), (110, cy)], "hv")

cluster(106, 128, 300, 232, "ESC BOARD 1   (BOM: 10_Hardware_Schematics_ESC_Avionics/ESC_BOM.csv;  drawn sheet: 11_Whole_System_Schematic/ESC_Block.asc)")
box(110, 196, 131, 220, "conn", "J1 input", "AMASS AS150\nanti-spark plug\n150 A, 24S", "[05 10]")
box(136, 196, 182, 220, "power", "DC link (VBUS)",
    "C1-C16: 16 × 150 µF 125 V\n   hybrid polymer, ESR ≤ 20 mΩ\nC17-C26: 10 × 2.2 µF X7R 250 V",
    "[04 07 10]")
box(196, 192, 246, 222, "inv", "3-phase inverter",
    "Q4-Q27: 24 × Infineon IPB065N15N3\n150 V, 6.5 mΩ, TO-263\n4 FETs in parallel per switch\n"
    "3 half-bridges (phases A, B, C)\nRg 10 Ω + 10 kΩ G-S pull-down per FET", "[01 02 03 09 10]")
box(252, 196, 296, 220, "sense", "Phase current sensors",
    "U7, U8: Allegro ACS770LCB-200B\n±200 A, 10 mV/A, 5 V supply\nin phases A and B (C = -A-B)", "[03 10]")
wire([(131, cy), (136, cy)], "hv")
wire([(182, cy), (196, cy)], "hv", "VBUS", at=(189, cy + 0.8))
wire([(246, cy), (252, cy)], "phase")
wire([(296, cy), (306, cy)], "phase", "J2-J4", at=(301, cy + 0.8))

box(110, 158, 150, 189, "lv", "Aux 12 V supply",
    "U1: ADI LTC7801 150 V sync buck\nQ1 BSC520N15NS3 (top)\nQ2 BSC360N15NS3 (bottom)\nQ3 BSP89 DRVCC pre-regulator\n"
    "L1 150 µH, R7 100 mΩ sense\n435 kHz, UVLO 59.8 V, OVLO 118.8 V", "[06 09 10]")
wire([(141, 196), (141, 189)], "hv", "VBUS", at=(144.5, 191.2), ha="left")
box(156, 175, 190, 189, "lv", "+5 V LDO", "U2: ADI LT1763-5 (500 mA)\nalso feeds U7, U8, encoder", "[09 10]")
box(156, 157, 190, 171, "lv", "+3.3 V LDO", "U3: ADI LT1763-3.3\nFB1 Murata BLM18PG601SN1\n   bead to the MCU VDDA", "[09 10]")
box(156, 132, 190, 152, "sense", "Bus + temperature sense",
    "R1-R4 divider: 100.8 V → 3.25 V\n   VBUS_SNS → PA2\nR5 + R6 NTC 10 k B3950\n   on heatsink, TEMP → PA3", "[10]")
wire([(150, 182), (156, 182)], "lv")
wire([(173, 175), (173, 171)], "lv", "+5 V", at=(174.5, 172.9), ha="left", va="center")
wire([(150, 186), (153, 186), (153, 191), (192, 191), (192, 182), (196, 182)], "lv",
     "+12 V to drivers (Vcc, BGVcc)", at=(172.5, 191.6))
wire([(190, 164), (193.5, 164), (193.5, 152), (196, 152)], "lv")
wire([(190, 141), (196, 141)], "sense")

box(196, 165, 246, 188, "drv", "Gate drivers",
    "U4, U5, U6: ADI LTC7063 (one per phase)\n150 V half-bridge, floating ground\n"
    "bootstrap D1-D3 ES1D + 1 µF\ndead time R 150 kΩ (≈140 ns)", "[09 10]")
box(196, 132, 246, 159, "mcu", "MCU: FOC controller",
    "U9: ST STM32G431CBT6\nCortex-M4F 170 MHz, LQFP-48\nPWM_A/B/C on PA8, PA9, PA10\nDRV_EN PB0, FAULT_N PB12\n"
    "ADC: PA0, PA1 (current), PA2, PA3", "[03 10 11]")
wire([(221, 188), (221, 192)], "sig")
ax.text(222.5, 190.0, "TG / BG gates", fontsize=7.5 * K, color=WIRE["sig"]["color"], weight="bold", va="center", zorder=5)
wire([(212, 159), (212, 165)], "sig", "PWM, EN", at=(210.5, 162), ha="right", va="center")
wire([(230, 165), (230, 159)], "sig", "FAULT_N", at=(231.5, 162), ha="left", va="center")

box(252, 132, 296, 155, "conn", "Board connectors",
    "J5 JST-GH 3: DShot in (PA15),\n   telemetry out (PB6)\nJ6 JST-GH 6: encoder SPI\n   (PA4-PA7) + 5 V\nJ7 TC2030: SWD programming",
    "[10]")
wire([(252, 145), (246, 145)], "sig", both=True)
wire([(264, 196), (264, 158), (249, 158), (249, 156), (246, 156)], "sense",
     "ISNS_A/B via R70-R73\n(2/3 divider) → PA0, PA1", at=(266, 177), ha="left", va="center")

box(306, 190, 354, 224, "motor", "MOTOR 1",
    "U15XL brushless outrunner, 38 KV\n21 pole pairs (36N42P)\nLph ≈ 25 µH per phase\n"
    "54 × 18 in propeller\nrotor J ≈ 0.15 kg·m²", "[03 09]")
box(306, 140, 354, 160, "sense", "Rotor encoder (on motor)", "ams AS5047P\n14-bit magnetic angle\nSPI to ESC J6, 5 V", "[03 10]")
wire([(330, 190), (330, 160)], "mech", "shaft magnet", at=(331.5, 175), ha="left", va="center", arrow=False)
wire([(306, 150), (296, 150)], "sig", "SPI", at=(301, 150.8))

# ------------------------------------------------------------------ channels 2 and 3, compact
for n, c in ((2, 116), (3, 96)):
    box(14, c - 8, 44, c + 8, "pack", f"PACK {n}", "24S Li-ion, 88.8 V\nsame as pack 1", "[04 09]", fs=7.6)
    box(50, c - 6, 70, c + 6, "power", f"PDB {n}", "tap to avionics", "", fs=7.6)
    box(76, c - 6, 102, c + 6, "power", f"HARNESS {n}", "8 AWG, 1 m", "[04]", fs=7.6)
    box(106, c - 8, 300, c + 8, "inv", f"ESC BOARD {n}: the same circuit as ESC board 1",
        "AS150 in → DC link 16 × 150 µF → LTC7801 12 V aux → LT1763-5 / LT1763-3.3 → 3 × LTC7063 → "
        "24 × IPB065N15N3 → 2 × ACS770LCB-200B → phases\nSTM32G431CBT6 runs FOC from the AS5047P angle "
        "and the DShot command from the flight controller", "[07 10]", fs=8.0)
    box(306, c - 4, 354, c + 8, "motor", f"MOTOR {n}", "U15XL 38 KV + AS5047P\n54 × 18 in prop", "[03 09]", fs=7.6)
    wire([(44, c), (50, c)], "hv"); wire([(70, c), (76, c)], "hv"); wire([(102, c), (106, c)], "hv")
    wire([(300, c + 2), (306, c + 2)], "phase")

# PDB taps to the avionics inputs (no crossings: outer line enters lowest)
for (yb, ytap, x, yin, lab) in ((199, 193, 4, 54, "PDB 1"), (110, 106, 7, 60, "PDB 2"), (90, 85.5, 10, 66, "PDB 3")):
    wire([(60, yb), (60, ytap), (x, ytap), (x, yin), (22, yin)], "hv", fs=7)
    ax.text(32, ytap, f"{lab} tap → avionics", fontsize=7.2 * K, color=WIRE["hv"]["color"], weight="bold",
            va="center", ha="center", zorder=5, bbox=dict(fc="white", ec="none", pad=0.6))

# ------------------------------------------------------------------ avionics board, detailed
cluster(18, 6, 300, 80, "AVIONICS POWER BOARD   (BOM: 10_.../Avionics_BOM.csv;  drawn sheet: 11_Whole_System_Schematic/Avionics_Block.asc)")
box(22, 36, 72, 73, "power", "Pack inputs + diode-OR",
    "J1-J3: Molex Micro-Fit 3.0, 2-pin\n   (one per pack PDB tap)\nF1-F3: Littelfuse 0451.500\n   0.5 A fast, 125 V DC\n"
    "D1-D3: ES1D (200 V 1 A) diode-OR\nD4: SMBJ110A TVS, 110 V stand-off\nC1 33 µF 160 V + C2, C3 2.2 µF",
    "[05 08 10]")
box(82, 34, 140, 73, "lv", "12 V buck, 5 A",
    "U1: ADI LTC7801 150 V sync buck\nQ1 BSC520N15NS3 (top)\nQ2 BSC360N15NS3 (bottom)\nQ3 BSP89 DRVCC pre-regulator\n"
    "L1 47 µH Coilcraft XAL1010\nR1 10 mΩ sense, 148 kHz\nsoft-start 2.6 ms\nUVLO 59.8 V, OVLO 118.8 V", "[06 09 10]")
box(162, 40, 210, 68, "lv", "5 V buck, 3.5 A",
    "U2: ADI LT8641 65 V sync buck\nL2 3.3 µH Coilcraft XAL4020\n1 MHz (RT 41.2 kΩ)\nFB 1 MΩ / 191 kΩ → 5.0 V", "[06 09 10]")
box(232, 40, 284, 68, "lv", "3.3 V ultralow-noise LDO",
    "U3: ADI LT3045\nRSET 33.2 kΩ: 100 µA × R = 3.32 V\nCSET 47 nF (noise, soft-start)\ncurrent limit 300 mA (R 499 Ω)",
    "[09 10]")
box(150, 11, 182, 24, "lv", "F4 PTC fuse", "Bourns MF-MSMF200\n2 A hold", "[10]")
wire([(72, 56), (82, 56)], "hv", "VIN_AV", at=(77, 56.8), fs=7)
wire([(140, 54), (162, 54)], "lv", "+12 V", at=(151, 54.8))
wire([(210, 54), (232, 54)], "lv", "+5 V", at=(221, 54.8))
wire([(284, 62), (306, 62)], "lv", "+3.3 V, J6", at=(295, 62.8))
wire([(186, 40), (186, 33), (306, 33)], "lv", "+5 V, J5", at=(296, 33.8))
wire([(111, 34), (111, 17.5), (150, 17.5)], "lv", "+12 V", at=(113, 25), ha="left", va="center")
wire([(182, 17.5), (306, 17.5)], "lv", "VTX_12V, J4", at=(292, 18.3))

box(306, 8, 354, 26, "load", "Video / telemetry transmitter", "12 V, 1.5 A\nJ4 JST-XH 2-pin", "[09]")
box(306, 29, 354, 50, "load", "Flight controller + receiver",
    "5 V: FC 1.5 A + RC receiver 0.3 A\nJ5 JST-GH 4-pin\nsends DShot to each ESC", "[09]")
box(306, 55, 354, 72, "load", "Sensors (IMU, baro, mag)", "3.3 V, low noise\nJ6 JST-GH 2-pin", "[09]")

# DShot from the flight controller up the right edge to each ESC's J5
wire([(354, 40), (359, 40), (359, 137), (296, 137)], "sig", "DShot command / telemetry  (ESC 1 J5)",
     at=(327, 137.7), both=True, fs=7)
for c in (116, 96):
    wire([(359, c - 6), (300, c - 6)], "sig", f"DShot / telemetry (ESC {2 if c == 116 else 3})",
         at=(329.5, c - 6.6), va="top", both=True, fs=7)

ax.text(4, 2, "Generated by Topologies/System_Flowchart/make_flowchart.py.  Gate-drive, ADC and connector pin names "
        "match ESC_Netlist.csv / Avionics_Netlist.csv in topology 10.", fontsize=11, color="#666", va="bottom")

# ------------------------------------------------------------------ check: every text inside its box
fig.canvas.draw(); r = fig.canvas.get_renderer(); bad = []
for p, ts in boxes:
    bb = p.get_window_extent(r)
    for t in ts:
        tb = t.get_window_extent(r)
        if tb.x1 > bb.x1 - 2 or tb.y0 < bb.y0 + 1 or tb.x0 < bb.x0 or tb.y1 > bb.y1:
            bad.append(t.get_text().split("\n")[0])
# tags must not overlap the body text
for p, ts in boxes:
    if len(ts) == 3:
        if ts[2].get_window_extent(r).overlaps(ts[1].get_window_extent(r)):
            bad.append("tag overlaps body: " + ts[0].get_text())
if bad:
    raise SystemExit("text does not fit:\n  " + "\n  ".join(bad))

for ext, kw in (("pdf", {}), ("png", dict(dpi=100)), ("svg", {})):
    fig.savefig(os.path.join(HERE, f"System_Flowchart.{ext}"), **kw)
print("wrote System_Flowchart.pdf / .png / .svg; all", sum(len(t) for _, t in boxes), "texts fit their boxes")

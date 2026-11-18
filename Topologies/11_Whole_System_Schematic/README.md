# 11 — Whole System Schematic: every part drawn, wired and simulated

**Topology type:** the complete drone power system in one LTspice file, with no "coded" boards. Three 24S packs → PDBs →
8 AWG harnesses → three ESC boards → three U15XL motors, and every PDB → the avionics power board → 12 V / 5 V / 3.3 V.
The ESC board and the avionics board are their own drawn sub-sheets, with every part of the topology 10 BOM placed and wired.

**Builds on:** [10](../10_Hardware_Schematics_ESC_Avionics/README.md) (the parts tables, BOMs and hand calculations),
[09](../09_24S_FOC_Drive_Low-Voltage_Rails/README.md), [07](../07_Three-Channel_Full_System/README.md), [08](../08_Redundant_Avionics_Power/README.md).
**Design document (with all the math):** `11_Whole_System_Schematic_Design.pdf`
**Block diagram with part numbers:** [`../System_Flowchart/System_Flowchart.pdf`](../System_Flowchart/README.md)

## Sheets
`python3 gen_system.py` writes everything. The board sheets are drawn by `esc_draw.py` and `avionics_draw.py` from the
same parts tables as the topology 10 BOM, so the drawing and the BOM cannot disagree.

| Sheet | What you see (double-click a block to open it) |
|---|---|
| `Power_System.asc` | 3 × 24S pack → PDB → 8 AWG harness → **ESC1–3** → **MOTOR1–3** (phase wires `M1_A`…`M3_C`, encoder lines back), every PDB → **AV1** → 12 V / 5 V / 3.3 V |
| `ESC_Block.asc` | The ESC board, 181 parts wired: (1) DC link, 16 + 10 caps, bus/NTC sense; (2) LTC7801 12 V aux buck; (3) LT1763 5 V / 3.3 V; (4–6) legs A–C, each with an LTC7063 and **all 8 FETs drawn, each with its own gate resistor and pull-down**; ACS770 sensors in phases A/B; (8) STM32 + connectors |
| `Avionics_Block.asc` | The avionics board, 65 parts wired: fuse + diode-OR per pack, TVS, LTC7801 12 V, LT8641 5 V, LT3045 3.3 V |
| `ACS770.asc` (U7, U8) | Hall sensor equivalent circuit (Allegro gives no SPICE model) inside a chip symbol |
| `STM32G431_FOC.asc` (U9) | Chip symbol with the real pins. Inside: the FOC firmware as a signal-flow model (ADC → Clarke/Park → PI → inverse → SVPWM → TIM1) |
| `U15XL_Motor.asc` | Three windings in star (Lph, Rph, back-EMF). The rotor and prop are an electrical analog: speed = voltage, inertia = capacitor, torque = current |

## Files
| File | What it is |
|---|---|
| `gen_system.py` | Writes the top sheet and calls the sheet builders |
| `esc_draw.py`, `avionics_draw.py`, `circuits.py` | The drawn board sheets (the LTC7801 buck layout is shared) |
| `draw.py`, `tablesheet.py` | Drawing library: symbols, rotation, wires, lint, and the LTspice-netlist check |
| `make_kicad_guide.py` → `11_KiCad_Entry_Guide.pdf` | Every part, pin, pad and net, for entering the boards into KiCad by hand |
| `make_design_doc.py` → `11_Whole_System_Schematic_Design.pdf` | The math, hand vs. LTspice, plots |
| `paths.py` | Lets the scripts import topology 10's parts tables and `../tools` |

## How the drawings are checked
- `esc_draw.py` and `avionics_draw.py` run LTspice's own netlister on every sheet and compare every pin of every part with the
  parts table: 0 errors on all five sheets. A lint pass reports no dangling wires and no pins left on the middle of a wire.
- The check caught real drawing mistakes: a bootstrap diode drawn reversed (it shorted +12 V to all three phases), and two rails
  missing their labels.
- Only rails (VBUS, +12V, +5V, +3V3), ground and the MCU ↔ leg control signals use labels; everything else is a wire.
  Labels also mark the nets worth probing (`PH_A`, `GAH1`, `BST_A`, `SW_AUX`, `SW12`, `SW5`).

## Running and probing
```bash
wine "$HOME/.wine/drive_c/Program Files/ADI/LTspice/LTspice.exe" -b Power_System.asc
```
About 19 minutes under Wine (`.tran 0 6m 0 uic`, all 72 inverter FETs as separate devices). Then `python3 make_design_doc.py`.
- **Probing inside a block:** `V(ESC1:+12V)`, `V(ESC1:U9:iq)`, `I(MOTOR1:La)`. Only what is on the `.save` line is kept, so add
  a node there before you run. Without `.save` the raw file would be several GB.
- The packs need `uic`. Without it, LTspice tries to find a DC operating point for four boards with every source at 0 V, and never converges.
- Open `Power_System.asc` from **this** folder. An LTspice window still pointing at the old folder-10 path writes a stray run there.

## Results (hand → LTspice)
| Quantity | Hand | LTspice |
|---|---|---|
| Inrush per pack during the 1 ms pre-charge ramp (2.413 mF ESC bus) | 214 A | 214 A |
| Avionics 12 V / 5 V / 3.3 V | 12.0 / 5.05 / 3.32 V | 12.00 / 5.05 / 3.20 V, still rising at 6 ms |
| 3.3 V soft-start time constant, R_SET·C_SET | 1.56 ms | fit from the run → settles at 3.32 V |
| Rotor speed 2 ms after the punch (13 N·m into J = 0.15 kg·m²) | ≈1.7 rpm | 1.59 rpm |
| Phase currents at standstill, θe ≈ 0 | ia ≈ 0, ib = −ic = 0.866·iq | 1.2 / 52.2 / −53.4 A |
| Each pack's current (ESC + 1/3 of the avionics board) | — | 1.065 A, equal to within 0.03 % on all three |
| MCU iq vs true iq from the motor currents | equal | 58.3 vs 61.0 A (see below) |

The design PDF has the full table with the numbers pulled from `Power_System.log`.

- **Current-sense offset (real finding).** The ACS770 output is ratiometric to its 5 V supply, and the ESC's LT1763 makes 4.978 V.
  The zero moves from 2.500 V to 2.489 V, which the firmware reads as about −1.1 A on each sensed phase. At standstill the currents
  are DC, so the offset adds straight into iq. Real FOC firmware reads the ADC zero at boot with the drivers off and subtracts it.
- A real anti-spark connector ramps over about 100 ms, which limits the inrush to about 2 A. The sim uses a 1 ms ramp only to keep the run short.

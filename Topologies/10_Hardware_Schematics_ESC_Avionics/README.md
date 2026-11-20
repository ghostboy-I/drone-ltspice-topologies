# 10 — Hardware Schematics: ESC Board and Avionics Power Board

**Topology type:** topology 09 turned into two real PCBs with real parts. Each board is one LTspice schematic you can run, plus a BOM and a net list you can redraw in KiCad.

| Board | Qty per aircraft | What it does |
|---|---|---|
| **ESC board** (`ESC_Board.asc`) | 3 (one per motor) | 24S DC link → 3 × LTC7063 gate drivers → 24 × IPB065N15N3 (4 in parallel per switch) → U15XL. It has its own LTC7801 12 V aux supply, LT1763 5 V / 3.3 V, two ACS772 ±250 A current sensors and an STM32G431 running FOC. |
| **Avionics power board** (`Avionics_Board.asc`) | 1 | Three 24S packs → fuses + diode-OR → TVS + LTC4366 surge stopper (115 V) → LTC7801 12 V / 5 A (transmitter) → LT8641 5 V / 3 A (flight controller + receiver) → LT3045 3.3 V / 0.3 A (sensors). |

**Builds on:** [09](../09_24S_FOC_Drive_Low-Voltage_Rails/README.md) (the design these boards implement), [03](../03_Three-Phase_FOC_PMSM/README.md) (FOC), [06](../06_BEC_Synchronous_Buck_5V/README.md) (buck design), [08](../08_Redundant_Avionics_Power/README.md) (avionics fed from all three packs).
**Design document (with all the math):** `10_Hardware_Schematics_ESC_Avionics_Design.pdf`

## Files
| File | What it is |
|---|---|
| `board.py` | Builder: one parts table → `.asc` + BOM + net list (they can't drift apart) |
| `hand_calc.py` | All predictions (`python3 hand_calc.py`, `python3 hand_calc.py esc`) |
| `avionics.py`, `esc.py` | The two boards. `python3 avionics.py loop` also writes the loop-gain test |
| `*_BOM.csv` | Reference, quantity, description, value, part number / specification, **KiCad footprint**, rating |
| `*_Netlist.csv` | Every net with every `REF.pin` on it, the wiring list for KiCad (simulation-only parts removed) |
| `plot_results.py`, `make_design_doc.py` | Plots and the design PDF |
| `kicad_footprints.py`, `kicad_export.py`, `kicad_check.py` | KiCad: footprint library, both projects with PCBs, and the checks (see below) |
| `kicad_draw.py`, `kicad_avionics.py`, `kicad_esc.py`, `sexpr.py` | Both boards as drawn, hierarchical KiCad schematics (avionics five sheets, ESC eight), checked against the parts tables |
| `pcb_avionics.py`, `pcb_esc.py`, `kicad_route.py` | The two PCB layouts for JLCPCB: placement, pours, a grid router, DRC, Gerbers / BOM / CPL (see below) |

## Running the simulations
Open the `.asc` in LTspice and press Run, or in batch:
```bash
wine "$HOME/.wine/drive_c/Program Files/ADI/LTspice/LTspice.exe" -b ESC_Board.asc
```
| Run | Shows | Time |
|---|---|---|
| `Avionics_Board.asc` (8 ms) | Cold start and sequencing, transmitter switch-on, controller load step, pack 1 pulled | ~10 min |
| `Avionics_LoopTest.asc` | 12 V loop gain at 3 / 6 / 12 / 24 kHz by injection, on the switching circuit | ~5 min |
| `Avionics_SurgeTest.asc` (300 ms) | LTC4366 start-up, then pack 1 at 200 V behind 4 Ω for 20 ms: VIN_PROT must stay at 115 V | ~2 s |
| `ESC_Board.asc` (13 ms) | Cold start of the ESC electronics with the rotor at hover, flying start, throttle punch | ~7 min |

Parts named `V_…`, `B_…`, `L_HARN`, `R_CS…`, `R_BW…`, `C_BW…`, `La/Lb/Lc`, `C_J`, `C_TH`, `R_LK…`, `R_VBF`, `C_VBF`, `C_VTX`, `R_SSRUN`, `R_LOAD_SS` are simulation stimulus or models: the packs, the loads, the motor, and the STM32's FOC firmware as a behavioural block. Everything else is a board part with its real reference designator.

## Fixes from the parts-alternatives study
[Alternatives_Study](../Alternatives_Study/README.md) checked each section against datasheet ratings. Three problems are fixed here:
| Problem | Fix | Check |
|---|---|---|
| DC-link ripple 61.7 A rms at hover over 16 caps = 3.86 A each, above the 3.5 A rating | C65–C72: 8 more 150 µF 125 V hybrid polymer, 24 in all → 2.57 A each (3.48 A at punch, seconds only) | `python3 hand_calc.py changes`; ESC run `Icap_bulk`: 68.8 A → 2.87 A each at the run's iq of 160 A (hand 2.80) |
| Punch needs iq = 210 A; ACS770LCB-200B is specified to ±200 A | U7, U8 → ACS772ECB-250B: ±250 A, 8 mV/A, 200 kHz, same CB package and pinout. ADC still fits ±306 A, 151 mA/LSB | ESC run (firmware block uses 8 mV/A) |
| SMBJ110A clamps to 177 V at 3.4 A; the LTC7801 is rated to 150 V | U4 LTC4366-2 surge stopper + Q4 FDB33N25 (250 V): VIN_PROT held at VREG = 1.23 V (1 + R24/R23) = 115.3 V, 51 ms timer, 9 s cool-down | `Avionics_SurgeTest.asc`: 179 V in → 115.5 V out (hand 115.3 V) |

The LTC4366 takes ~0.1 s to turn Q4 on, so the 8 ms board run models Q4 already on (sim-only `R_SSRUN`, 94 mΩ), and its packs
ramp up from 0 V in 0.2 ms (the LTC4366 model has no DC operating point with the packs already at 88.8 V).

## Whole power system
The whole system, with both boards drawn part by part and wired to three packs and three motors, is now topology
[11](../11_Whole_System_Schematic/README.md) (`Power_System.asc`, the drawn board sheets and the KiCad entry guide).
The block diagram of everything, with part numbers, is in [System_Flowchart](../System_Flowchart/README.md).

## KiCad projects (both boards): schematic, footprints and PCB
```bash
python3 kicad_export.py all     # footprint library + both projects + overview plots
python3 kicad_check.py          # ERC, net list vs parts table, footprints, schematic-PCB parity (KiCad itself)
```
| Folder | What it is |
|---|---|
| `kicad/Drone_Power.pretty/` | **Every footprint both boards use (39).** 35 are KiCad 9 stock footprints, copied in under their KiCad names (`kicad_footprints.py`). 4 are not in KiCad's library and are generated from the manufacturers' drawings (table below) |
| `kicad/ESC_Board/` | The ESC board (197 parts): drawn schematic on eight sheets, and the **laid-out, routed PCB** (section below) |
| `kicad/Avionics_Board/` | The avionics board (77 parts): drawn schematic on five sheets, and the **laid-out, routed PCB** (next section) |
| `kicad/*_footprints.png` | KiCad's plot of each imported PCB: footprints parked by schematic block, ready for placement |

The PCBs are what **Tools → Update PCB from Schematic** would give: each footprint is linked to its symbol (same UUID path),
the nets come from KiCad's own net list of the schematic, and attributes (DNP, BOM) follow the symbols. The boards are laid
out by `pcb_avionics.py` and `pcb_esc.py`.

| Generated footprint | Part | Source |
|---|---|---|
| `Linear_UDC-18-2EP_3x4mm_P0.5mm` | LT8641 (avionics U2) | LT8641 datasheet Rev B: UDC 20(18)-lead QFN 3 × 4 mm, DWG 05-08-1956 Rev C. 0.25 × 0.70 mm lands at 0.5 mm, pins 5 and 12 removed, two exposed SW pads (21: 0.22 × 0.40 mm, 22: 0.22 × 0.356 mm) |
| `Linear_HTSSOP-24-1EP_4.4x7.8mm_P0.65mm_EP2.74x3.25mm` | LTC7801 (U1, both boards) | LTC DWG 05-08-1771 Rev B, FE24 exposed pad variation AA: 0.45 × 1.05 mm lands, exposed pad 2.74 × 3.25 mm = GND, 2 × 2 paste windows |
| `AMASS_AS150_Pigtail_2x8AWG_P15mm` | J1, ESC battery input | The AS150's two 8 AWG pigtail leads: 5.1 mm drill, 8.4 mm pads, 15 mm pitch (6.6 mm copper gap on the 100 V bus). Pad 1 = +, pad 2 = − |
| `SolderWire-8AWG_1x01_D4.2mm_OD7mm` | J2–J4, motor phase leads | 8 AWG silicone lead (4.2 mm conductor): KiCad's wire-pad rule, drill = conductor + 0.9 mm |

**Checked** (`kicad_check.py`): ERC 0 errors / 0 warnings on both boards; KiCad's net list equals the parts table on all
92 + 40 nets; every symbol pin has a pad of the same number; schematic-PCB parity 0 issues; polarised capacitors have pad 1
(+) off ground. Pads without a net are only unused MCU pins, the LTC7063 NC pins, TC2030 pad 6 (SWO) and connector
mounting tabs. Re-running the export gives identical files (UUIDs are derived from the board name).

**Corrected while importing the footprints**
- The LTC7801 had been given an HTSSOP-24 footprint whose 3.2 × 5 mm exposed pad comes from an ST drawing; ADI's FE24 pad is
  2.74 × 3.25 mm, so that land would have printed about 1.8× too much solder paste under the chip.
- The LT8641 is in ADI's UDC QFN (LT8641EUDC#PBF), not an LQFN: the BOM part number and package are fixed.
- J7 (Tag-Connect TC2030) had SWCLK and NRST swapped against the TC2030-CTX cable (pads 1 VCC, 2 SWDIO, 3 nRESET, 4 SWCLK,
  5 GND): now NRST is pad 3 and SWCLK pad 4.
- The motor phase pads were KiCad's 2.5 mm² wire pad, far too small for the 6–8 AWG phase leads; now 8 AWG pads.
- SMBJ110A is unidirectional, so it uses `Device:D_Zener` (K = 1, A = 2) instead of the bidirectional `D_TVS`; fuses use `Device:Fuse`.

## Avionics PCB layout (JLCPCB, 4 layers)
```bash
python3 pcb_avionics.py         # schematic -> placed, poured, routed, filled board + DRC + layout_routed.png (a few minutes)
python3 pcb_avionics.py place   # placement only, with layout_place.png
python3 pcb_avionics.py fab     # kicad/Avionics_Board/jlcpcb/: Gerber zip, BOM and CPL for JLC
```
The layout is a script, so a schematic change is one re-run. **Board:** 100 × 62 mm, 4 layers, 1.6 mm, 2 oz outer / 1 oz
inner (JLC04161H-7628 stackup), four M3 holes. In1 and In2 are solid ground planes; F.Cu carries the power pours; B.Cu has a
ground pour and the signal crossings. Power flows left to right: inputs → surge stopper → 12 V → 5 V → 3.3 V.

**Clearance rules** (`Avionics_Board.kicad_dru`, IPC-2221B table 6-1, B2 = external, uncoated). The spacing between two
conductors depends on the voltage *between* them, so nets are grouped by their peak voltage from the surge simulation:

| Group (net class) | Nets | Peak | Outer-layer clearance |
|---|---|---|---|
| HVIN | PACK1–3+, PACK1–3_F, VIN_AV | 200 V (pack surge) | 1.25 mm to LV and HVSW, 0.6 mm to HVF |
| HVF | VIN_PROT and the floating LTC4366 nets | ≤ 122 V | 0.6 mm |
| HVSW | SW12, BST12, TG12 | 0–126 V | 0.6 mm |
| LV (PWR, DRV, signal) | +12V, +5V, +3V3, GND, gate drive, control | ≤ 13 V | 0.2 mm |

Inner layers use 0.5 mm (B1 asks only 0.2 mm). Inside a group the spacing is 0.2 mm. The LTC7801's own pinout puts VIN 0.65 mm
from low-voltage pins, so its pin field (`U1_PINS` rule area, F.Cu) allows 0.2 mm. **Conformal-coat the board** (IPC B4).

**How it is checked**
- KiCad's DRC (`kicad-cli pcb drc` with schematic parity): `Avionics_Board_drc.json`, summary in `layout_stats.json`.
- `pinfield_audit()`: the U1 exemption must not reach copper outside the pin field. Every exempt item is cut back to the
  copper outside the area and the gaps that are left must meet the full rule.
- Before trusting a DRC of 0, make sure it loaded the rules. pcbnew's `LoadBoard` skips the `.kicad_dru`, so the zone filler
  needs the rules loaded first (`WriteDRCReport`). A reload in the same process also reuses a cached project, net classes and all.
  The script handles both (`fill()`, `load()`), and `load()` asserts that the HV classes are present.

**Results** (from `layout_stats.json`): 77 parts + 4 M3 holes; 512 tracks (F.Cu 498 mm, B.Cu 225 mm) and 114 vias; **0 unrouted, KiCad DRC 0 errors / 0 warnings with the HV rules loaded, schematic parity 0, pin-field audit 0.** Measured independently (KiCad's shape collision test), the ground pours sit ≥ 1.25 mm from HVIN copper and ≥ 0.6 mm from HVF / HVSW on the outer layers, and ≥ 0.5 mm on the inner planes. C10 and C23 have their references on F.Fab only (no silkscreen room).

![layout](kicad/Avionics_Board/layout_routed.png)
![3D](kicad/Avionics_Board/board_3d_top.png)

`board_3d_top.png` is `kicad-cli pcb render --side top`. U1, U2 and the input connectors have no 3D model, so you see their pads.

**Ordering at JLCPCB** (`kicad/Avionics_Board/jlcpcb/`): upload `Avionics_Board_gerbers.zip`, choose 4 layers, 1.6 mm,
outer copper 2 oz, inner 1 oz, impedance control off (stackup JLC04161H-7628). For assembly, add `Avionics_Board_BOM_JLC.csv`
and `Avionics_Board_CPL_JLC.csv`. The LCSC column is empty, so pick each part in JLC's matcher, and **check every rotation
in JLC's 3D preview**: zero orientations differ between KiCad and JLC for SOT-23s, diodes and polarised parts.

Open items before ordering:
- F1–F3 are rated 125 V DC, but the surge test drives a pack input to 200 V. The fuse only has to survive it, not break
  it (the TVS and LTC4366 clamp downstream), but a 250 V DC-rated fuse in the same footprint removes the question.
- C26 is the 250 V 1206 part (it sits on the 100–121 V node).

## ESC PCB layout (JLCPCB, 4 layers + bus bars)
```bash
python3 pcb_esc.py              # schematic -> placed, poured, routed, filled board + DRC + renders + stats (~6 min)
python3 pcb_esc.py place        # placement only, with layout_place.png
python3 pcb_esc.py copper       # power copper and hand vias only, filled, with layout_copper.png and DRC
python3 pcb_esc.py check        # independent clearance measurement of the saved board, into layout_stats.json
python3 pcb_esc.py fab          # kicad/ESC_Board/jlcpcb/: Gerber zip, BOM and CPL for JLC
```
**Board:** 175 × 130 mm, 4 layers, 1.6 mm, 2 oz outer / 1 oz inner (JLC04161H-7628), four M3 holes. The floorplan follows
the current. At the top is the DC link: 24 polymer capacitors in three rows of eight, with the battery pigtail J1 to their
right. Below them sit the three legs side by side, each a column of four high-side D2PAKs, a phase lane, four low-side
D2PAKs and a ground lane. The next leg's DC-link ceramics sit across each ground lane. Along the bottom is the low-current
band (drivers, current sensors, motor-lead pads, MCU, LDOs, connectors), and the aux 12 V buck is in the top-right corner.
Battery current flows top to bottom and motor current leaves at the bottom, so no high current crosses the MCU, and one
solid ground plane (In1) serves power and signal ground.

**Power copper.** VBUS, the phases and ground are pours on all four layers, sized by counting squares (design doc sec. 9).
Mask-free strips take a soldered copper bar (4 × 2 mm, or flattened 8 AWG): the three phase lanes, the VBUS strip along
the tops of the legs and the bridge from J1. Every FET tab has 30 thermal vias. The B.Cu under each FET column is opened
for the heat sink, which needs an insulating pad, because that copper is at VBUS or phase potential.

**Clearance rules** (`ESC_Board.kicad_dru`). These are the avionics board's groups, extended to 24S (100.8 V):

| Group (net class) | Nets | Voltage | Outer clearance |
|---|---|---|---|
| HVBUS | VBUS | 0–100.8 V | 0.6 mm to every other class |
| SW_A / SW_B / SW_C | PH_x, BST_x, TG_x, HS gates, MOT_x | −1 to 113 V | 0.6 mm (0.2 mm inside one phase) |
| SW_AUX | aux SW, BST, TG | 0–113 V | 0.6 mm |
| HVDIV1 / HVDIV2 | bus divider taps | 67 V / 34 V | 0.6 mm |
| LV (PWR, DRV, signal) | GND, +12V, +5V, +3V3, LS gates, control | ≤ 13 V | 0.2 mm |

Each phase is its own group: two phases can be the full bus apart, while a phase, its bootstrap supply and its high-side
gates move together. Inner layers use 0.3 mm (B1 asks only 0.2 mm). The LTC7063s and the LTC7801 put 100 V pins 0.2–0.25 mm from
low-voltage ones, so their pin fields are exempt rule areas (0.2 mm), checked by `pinfield_audit()`. **Conformal-coat the board.**

**Routing.** This uses the same A* router (`kicad_route.py`), with the hard spots planned by hand:
- **The LTC7801's left pin row escapes through a two-column via fan-out** (alternate pins 1.22 / 2.27 mm out). VBUS sits
  between NDRV and EXTVCC there, so no single-layer order works (What went wrong, 13).
- **FAULT_N drops to B.Cu through a via under each driver's pin 3.** It and DRV_EN are buses on neighbouring pins of all
  three drivers, so whichever routes first walls in the other.
- **R5's +3V3 routes before the encoder bus**, which would otherwise wall it in.
- **`tidy()` necks a track down to the pad's narrow side less 0.05 mm where it ends in a pad.** The router snaps the
  last point onto the exact pad centre, up to 25 µm off the grid it checked. `tidy()` also removes vias that two
  fan-outs put on the same spot.
- **Fan-out vias keep the full grid error** (cell × √2). KiCad's DRC caught one placed with only 0.75 cell, 0.196 mm from
  an LQFP pin.

**How it is checked**
- KiCad's DRC with schematic parity, with the HV rules loaded: `ESC_Board_drc.json`.
- `pinfield_audit()`: the exemptions must not reach copper outside the pin fields.
- `measure_gaps()` is an independent measurement that doesn't use KiCad's DRC engine. Per layer, all copper of each group
  (pads, tracks, vias, zone fills) becomes one polygon set. One set is grown by d (Clipper) and intersected with the
  other, bisecting d to 1 µm.

**Results** (`layout_stats.json`): 197 parts + 4 M3 holes; 1061 tracks (F.Cu 1598 mm, B.Cu
1161 mm) and 2147 vias (1974 placed by hand: 720 in FET tabs, 468 at the FET sources,
429 in the ground lanes, 288 in the capacitor bank). **0 unrouted, KiCad DRC 0 errors / 0 warnings, schematic parity 0,
pin-field audit 0.** Measured independently, every HV group keeps at least 0.600 mm from the other groups on F.Cu and B.Cu
and 0.300 mm on In1/In2. The closest pairs sit exactly at the rule, where the zone filler puts a pour.
6 references (Q8, Q25, Q17, R12, R15, R14) are on F.Fab only, because there was no room on the silkscreen.

![layout](kicad/ESC_Board/layout_routed.png)
![3D](kicad/ESC_Board/board_3d_top.png)

**Ordering at JLCPCB** (`kicad/ESC_Board/jlcpcb/`): upload `ESC_Board_gerbers.zip` and choose:
- 4 layers, 1.6 mm, outer copper 2 oz, inner 1 oz.
- **Via covering "epoxy filled & capped"**: the thermal vias sit in the D2PAK tab pads, so open vias would wick the solder away.

For assembly, add `ESC_Board_BOM_JLC.csv` and `ESC_Board_CPL_JLC.csv`. The LCSC column is empty, so pick each part in JLC's
matcher, and check every rotation in JLC's 3D preview (D2PAKs, diodes, polarised capacitors, SOT-223).

Fit by hand after assembly:
1. Solder the copper bars on the mask-free strips.
2. Fit J1 (AS150 pigtails) and the 8 AWG motor leads.
3. Fit the heat sink over a ≥ 0.5 mm, ≥ 3 W/m·K, 150 V-rated insulating pad.
4. Conformal-coat the board.

R6 (the NTC) sits at the bottom of leg B's ground lane, on the board copper next to the FETs, not on the sink.

## Porting to KiCad by hand
1. **One schematic per board**, with one hierarchical sheet per numbered block (the framed areas in the `.asc`): e.g. ESC = 1 power input, 2 aux supply, 3 logic supplies, 4–6 legs A/B/C, 7 current sense, 8 MCU and connectors. Use global labels for the nets that cross sheets (`VBUS`, `+12V`, `+5V`, `+3V3`, `PWM_A`…).
2. **Symbols.** KiCad's stock library has the STM32G431CBTx, the ACS770/ACS772 CB-package symbol, the LT3045 and the AS5047. The **LTC7801, LTC7063, LT8641, LT1763 and LTC4366 are not in KiCad's library**: use the generated ones in `kicad/<Board>/<Board>_custom.kicad_sym`. Pin names in the net list are LTspice's names (`SENSE+`, `BGRTN`, `_FLT` = FLT-bar, `_SHDN` = SHDN-bar); match them to the datasheet pin names, not to pin numbers.
3. **Wire from `*_Netlist.csv`**: each row is one net and every pin on it. Parts listed with a quantity (e.g. `Q4 Q5 Q6 Q7`) are parallel copies with identical connections.
4. **Footprints** are all in `kicad/Drone_Power.pretty` (add it to your footprint library table). The BOM gives each one by its KiCad library name; the four `Drone_Power:` ones are generated from the manufacturers' drawings.
5. **The MCU pin map is a proposal.** TIM1 CH1–3 on PA8–PA10 for the gate drivers, ADC1 on PA0–PA3, SPI1 on PA4–PA7 for the encoder, SWD on PA13/PA14. Check every alternate function in STM32CubeMX before you route.

## Layout rules that the schematic can't show
- **Power loop first.** Per leg, the loop from the DC-link ceramics (C17–C26) through the high-side and low-side FETs must be as small as possible. Put the ceramics right across each leg, with the polymer capacitors next to them.
- **Current.** Per phase 116 A rms at hover and about 149 A rms in a punch; on the DC link 83 A at hover and 112 A in a punch (ESC_Board.log). That needs bus bars or very heavy copper on VBUS, GND and the phases. The motor leads need about 6–8 AWG. (An earlier version of this line gave 110 A / 74 A without saying which current; those were rough DC-link figures.)
- **100 V spacing.** Keep at least 0.6 mm clearance between 100 V nets and logic. Keep the bootstrap nodes (`BST_x`, `PH_x`) away from the MCU.
- **Gate drive.** Each LTC7063 goes next to its leg. Route TG with its return SW (and BG with BGRTN) as tight pairs, put one gate resistor at each FET, and place the bootstrap diode and capacitor at the driver.
- **Grounds.** Power ground (FET sources, DC link) and signal ground (MCU, ADC dividers, LDOs) join at one point near the DC-link negative. The ACS772 is isolated, so its output side belongs to signal ground.
- **Sense lines.** Use a Kelvin connection on R1 / R7 (current sense) to SENSE+ / SENSE−, and route the ADC lines (ISNS_x, VBUS_SNS) as guarded traces away from the switch nodes.
- **Thermal.** About 105 W of FET loss at hover (4.4 W per D2PAK, ESC_Board.log), so the 24 D2PAKs need a heatsink. The NTC (R6) goes on it.

## Results (hand → LTspice)
**Avionics board**
| | Hand | LTspice |
|---|---|---|
| +12V / +5V / +3V3 (V) | 12.000 / 4.988 / 3.320 | 11.995 / 5.046 / 3.282 |
| 12 V loop: crossover / phase margin | 11.57 kHz / 49.8° | 10.59 kHz / 53.0° (transient injection) |
| Current per pack, all three connected (A) | 0.112 | 0.114 |
| Packs 2 and 3 after pack 1 is pulled (A) | 0.167 | 0.170 (12 V moves 20 mV) |
| Transmitter switch-on: 12 V dip (mV) | 198 | 222 |
| 12 V stage / whole board efficiency | 97.9 % / 93.8 % | 95.2 % / 91.2 % (input now includes the LTC4366 stage, ≈ 45 mW in its resistors) |

**ESC board** (hand evaluated at the operating point LTspice reached: iq = 160.4 A, ω = 190.7 rad/s)
| | Hand | LTspice |
|---|---|---|
| Cold start: 12 V up / drivers enabled | 0.72 ms + delay / 1.5 ms (MCU) | 1.00 ms / FAULT_N high at ~1.6 ms |
| +12V minimum at driver enable (V) | 11.0 (charge sharing) | 9.86 |
| iq read by the MCU vs. true (A) | 160.4 | 159.6 (-0.5 %) |
| ESC input = electromagnetic + copper + inverter (W) | 6660 + 328 + 97 | 7102 = 6660 + 329 + 105 |
| Dead time at Vgs = 3 V (DT = 150 kΩ) | — | 142 / 141 ns |
| Bootstrap current, 3 legs (mA) | 25.3 | 24.4 |
| Bootstrap voltage (V) | 12 − Vf − Qg/C | 11.04–12.12 |
| Punch: iq / ESC current (A) | 210 | 210.5 / 112.3 |

![avionics](Avionics_results.png)
![esc](ESC_results.png)

## What went wrong first
1. **Units.** The `.asc` files were first written as UTF-8 with `µ`. LTspice read it as two Latin-1 characters and dropped the unit: 47µ became 47 H and nothing started. `board.py` now writes `u` in Latin-1.
2. **Library models looked missing** from a bare `.cir` test. LTspice loads its standard libraries only for `.asc` files. Confirm a model by measuring it (Ron with 1 V / 1 mΩ), not by the absence of an error.
3. **`aux.asc` cannot be opened under Wine**: AUX is a reserved DOS device name.
4. **Net-name collision**: the aux supply's gate nets were `TG_A` / `BG_A`, the same as leg A's. Two gate drivers drove each other's FETs and +12V reached 45 V. In a net-label schematic the names are the wiring, so the aux nets are now `_AUX`.
5. **Constant-current loads** dragged rails negative at start-up and broke the LDO models. Every load now scales with limit(V/Vnom, 0, 1).
6. **`.ic` on an encrypted controller** (soft-start pin, output rail) gave impossible operating points (29 A in L1 at t = 0). The electronics now start cold, and only the rotor speed is preset.
7. **Missing parts the simulation found**: gate-source pull-downs (high-side FETs drifted on through Cgd while the drivers were unpowered), the LT1763 bypass capacitors (they slow start-up by several ms; now do-not-fit), and 12 V bulk (driver enable dipped +12V to 7.4 V; a 47 µF fixes it).
8. **Burst Mode** on the avionics 12 V gave a 90 mV, 25 kHz sawtooth at light load, so MODE is tied to INTVCC (forced continuous).
9. **The sensor model lied**: a 1 kΩ bandwidth resistor in the ACS770 model lost 3 % into the ADC divider (now 10 Ω + 133 nF).
10. **"Efficiency" of 76.6 %** was the rotor still accelerating after the coast (649–867 W into ½Jω²). The energy balance closes once that is counted.
11. **`ltraw.read_meas`** returned the threshold of WHEN measurements instead of the time. Fixed for every topology.
12. **Same-net pours looked unconnected** to the ESC router's island check when they overlapped without a pad or via in the overlap, so it drew
    thin VBUS tracks beside the pours. Touching fills on the same layer now count as connected.
13. **Pin order is topology.** The LTC7801's left row (VBUS between NDRV and EXTVCC, INTVCC heading to the far side) cannot escape
    on one layer. When the destinations around a chip are not in the cyclic order of its pins, something must change layer:
    U1 now has a two-column via fan-out, the usual escape for a 0.65 mm TSSOP.

## Assumptions to replace with measurements
Inherited from 09: motor Lph 25 µH, 21 pole pairs, rotor inertia 0.15 kg·m², pack resistance 30 mΩ, and the avionics currents. New here: the LTC7801's ITH gain (assumed 1/12, measured ≈ 1/13), the supply currents of the STM32 / ACS772 / AS5047, and the derated capacitances of the ceramics at their bias voltage.

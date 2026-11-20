# Drone Motor Power Topologies (LTspice)

| # | Topology | Folder | Status |
|---|---|---|---|
| 01 | Half-bridge (synchronous buck / one ESC leg) → DC motor equivalent | `01_Half-Bridge_Motor_Drive/` | Done, verified by simulation |
| 02 | 3-phase inverter (ESC) + BLDC, 6-step trapezoidal commutation, Hall-sensored | `02_Three-Phase_ESC_BLDC_6-Step/` | Done, verified by simulation |
| 03 | 3-phase inverter + PMSM, sensored field-oriented control (FOC) with SVPWM | `03_Three-Phase_FOC_PMSM/` | Done, verified by simulation |
| 04 | Three-channel power transmission: 3 batteries → 3 harnesses → 3 ESCs, independent (plug-in, ripple, resonance, grounding) | `04_Three-Channel_Power_Transmission/` | Done, verified by simulation |
| 05 | Per-channel protection: back-to-back MOSFET soft-start (anti-spark) + reverse-polarity block, vs XT60 / XT90-S | `05_Channel_Protection_Soft-Start_Reverse-Polarity/` | Done, verified by simulation |
| 06 | BEC: synchronous buck 4S → 5 V / 3 A for avionics (voltage mode, Type III, input feed-forward) | `06_BEC_Synchronous_Buck_5V/` | Done, verified by simulation |
| 07 | Full 3-battery → 3-motor system: three protected channels, three switching FOC ESCs on their own harnesses, plus the BEC (plug-in/arming, flight, punch, pack loss) | `07_Three-Channel_Full_System/` | Done, verified by simulation |
| 08 | Redundant avionics power: feed the BEC from all three packs (ideal-diode OR-ing) without creating ground loops | `08_Redundant_Avionics_Power/` | Done, verified by simulation |
| 09 | 24S channel of the real tricopter: FOC drive (03) on a U15XL with bootstrap gate drive, ESC 12 V + 3.3 V supply, avionics 12 V (transmitter) → 5 V (06, controller + receiver) → 3.3 V | `09_24S_FOC_Drive_Low-Voltage_Rails/` | Done, verified by simulation |
| 10 | Hardware schematics of 09 with real parts: ESC board (LTC7801 aux, 3 × LTC7063, 24 × IPB065N15N3, ACS772, STM32G431) and avionics power board (diode-OR, LTC4366 surge stopper, LTC7801, LT8641, LT3045), with BOMs and KiCad 9 projects for both boards: drawn schematics, every footprint in one project library, and both PCBs laid out, routed and DRC-clean with JLCPCB files (avionics 100 × 62 mm; ESC 175 × 130 mm, 4 layers, 2 oz, bus bars) | `10_Hardware_Schematics_ESC_Avionics/` | Done, verified by simulation |
| 11 | Whole power system drawn part by part: 3 packs → 3 drawn ESC boards (every FET, driver, sensor, MCU) → 3 U15XL motors, plus the drawn avionics board, in one LTspice run; KiCad entry guide | `11_Whole_System_Schematic/` | Done, verified by simulation |
| 12 | Full H-bridge (bidirectional / reversing) | — | Optional |

**Flow chart of the whole system with part numbers:** [`System_Flowchart/System_Flowchart.pdf`](System_Flowchart/README.md), every block tagged with the topologies that cover it.

**Parts alternatives study:** [`Alternatives_Study/Alternatives_Study.pdf`](Alternatives_Study/README.md), alternative parts and methods for every section of the two boards, judged at the 24S hover and punch points.

**End goal:** three batteries driving three motors independently. Transmission (04, 05), down-conversion for avionics (06), then the full system (07), redundant avionics power (08), and the move to the real 24S packs with every low-voltage rail (09).

`tools/ltraw.py` reads LTspice binary `.raw` files into Python so results can be plotted.

`tools/sweep.py` runs parameter sweeps in parallel: one LTspice process per case, several at once, results in
`<topology>/sweeps/<name>/results.csv`. Example (from this folder):
```bash
python3 tools/sweep.py 02_Three-Phase_ESC_BLDC_6-Step/ThreePhase_ESC_BLDC.asc --param Duty=0.3,0.5,0.7,0.9 --param Sync=0,1 --name duty
```
A single transient run cannot be split across cores (every time step needs the one before it), but separate cases are
independent, so a sweep scales with core count. Each ESC run keeps about 2 cores busy and uses ~0.17 GB, so the default
is one job per 2 cores (`--jobs` overrides). Topology 02 has a worked example: `sweep_fsw.py`.

Each topology folder has its schematic, a README, results plot and `NN_<Topology>_Design.pdf` (the math). Rebuild that PDF with `make_design_doc.py`.

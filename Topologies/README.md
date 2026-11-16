# Drone Motor Power Topologies (LTspice)

| # | Topology | Folder | Status |
|---|---|---|---|
| 01 | Half-bridge (synchronous buck / one ESC leg) → DC motor equivalent | `01_Half-Bridge_Motor_Drive/` | Done, verified by simulation |
| 02 | 3-phase inverter (ESC) + BLDC, 6-step trapezoidal commutation, Hall-sensored | `02_Three-Phase_ESC_BLDC_6-Step/` | Done, verified by simulation |
| 03 | 3-phase inverter + PMSM, sensored field-oriented control (FOC) with SVPWM | `03_Three-Phase_FOC_PMSM/` | Done, verified by simulation |
| 04 | Three-channel power transmission: 3 batteries → 3 harnesses → 3 ESCs, independent (plug-in, ripple, resonance, grounding) | `04_Three-Channel_Power_Transmission/` | Done, verified by simulation |
| 05 | Per-channel protection: back-to-back MOSFET soft-start (anti-spark) + reverse-polarity block, vs XT60 / XT90-S | `05_Channel_Protection_Soft-Start_Reverse-Polarity/` | Done, verified by simulation |
| 06 | BEC: synchronous buck 4S → 5 V / 3 A for avionics (voltage mode, Type III, input feed-forward) | `06_BEC_Synchronous_Buck_5V/` | Done, verified by simulation |
| 07 | Full 3-battery → 3-motor system: three protected channels, three switching FOC ESCs on their own harnesses, plus the BEC | — | Next |
| 08 | Redundant avionics power: feed the BEC from all three packs (ideal-diode OR-ing) without creating ground loops | — | Planned |
| 09 | Full H-bridge (bidirectional / reversing) | — | Optional |
| 10 | Bootstrap high-side gate drive | — | Optional |

**End goal:** three batteries driving three motors independently. Transmission (04, 05), down-conversion for avionics (06), then the full system (07) and redundant avionics power (08).

`tools/ltraw.py` reads LTspice binary `.raw` files into Python so results can be plotted.

Each topology folder has its schematic, a README, results plot and `NN_<Topology>_Design.pdf` (the math). Rebuild that PDF with `make_design_doc.py`.

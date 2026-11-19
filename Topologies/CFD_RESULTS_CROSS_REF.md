# CFD RESULTS CROSS REF

Cross-reference of every CFD result in `ghostboy-I/drone-ltspice-topologies` as of 2026-11-18.
All results live on the **`prop-54x18`** branch (none are on `main`), under `CFD_Results/` with case setups in
`Props/*/cfd/`. Numbers below are copied or derived from the case READMEs and `summary.json` / `ct_cfd_*.json` files.

Common method for all cases: OpenFOAM 13, `incompressibleFluid` (steady SIMPLE), frozen-rotor MRF, k-omega SST, 10 cores.

---

## 1. Case inventory

| # | Case | Rotor / prop | Size | Blades | Speed / setting | Air | Mesh (cells) | Iterations | Converged |
|---|---|---|---|---|---|---|---|---|---|
| A | `01_54x18_Composite/caradonna_tung_coarse` | Caradonna–Tung validation rotor (NACA 0012, untwisted) | R 1.143 m (90 in dia), c 0.1905 m | 2 | 8° collective, tip Mach 0.439 | standard | 1.50 M, baseline (3.1 mm blade / LE) | 600 | **No** (torque drift +0.73 %/100 it) |
| B | `01_54x18_Composite/caradonna_tung_coarse_le` | Caradonna–Tung validation rotor | same | 2 | same | standard | 2.45 M, + 0.78 mm LE tube | 1500 | Yes |
| C | `02_Toroidal_Rotor/reference_prelim` | 54x18 composite, Phase 3 blade (`prop_ccw.stl`) | 54 in (1.372 m) | 2 | 2280 rpm | hot day, ρ 1.1095 | 2.15 M (1.25 mm blade, 0.62 mm curvature) | 1500 | Yes (drift ≈ 0 %) |
| D | `02_Toroidal_Rotor/toroid_prelim` | Toroidal (closed-loop) rotor | 54 in | 2 loops / 4 legs | 2280 rpm | hot day, ρ 1.1095 | 2.76 M (same recipe as C) | 1500 | Yes (drift < 0.1 %) |

Cases A/B check the CFD method against experiment. Cases C/D are the design cases, run on the same mesh recipe, speed and air so they compare directly.

---

## 2. Method validation: Caradonna–Tung (A vs B)

| Quantity | A: baseline mesh | B: LE-refined mesh | Change | Experiment | BEMT hand calc |
|---|---|---|---|---|---|
| Thrust T [N] | 493.5 | 497.1 | +0.7 % | | |
| C_T | 0.00440 | 0.00443 | +0.7 % | 0.00459 | 0.00602 |
| C_T vs experiment | −4.2 % | **−3.5 %** | | | |
| C_T vs BEMT | −26.9 % | −26.3 % | | | |
| Torque Q [N·m] | 83.2 | 75.8 | **−8.9 %** | | |
| Pressure / viscous torque [N·m] | 66.8 / 16.4 | 58.4 / 17.4 | | | |
| Viscous torque share | 20 % | 23 % | | | |
| Figure of merit | 0.318 | 0.353 | +11 % | | |
| Core-hours | 9.8 | 11.3 | | | |

Sectional normal force vs the report's C_L (r/R 0.5 → 0.96): A runs −4.5 % to −15.5 % low and B runs −4.5 % to −14.6 % low.

**What this shows**
- Thrust is captured within ~4 % of experiment and barely depends on the mesh.
- Torque is mesh-sensitive. Refining only the leading edge removed 7.4 N·m of spurious pressure torque. About 11 N·m more is estimated to remain (an expected ~60–65 N·m), so **CFD torque on coarse noses is pessimistic (too high)**.
- BEMT over-predicts thrust by ~26–27 % here, which matches the gap seen on the 54 in rotors (section 4).

---

## 3. Design comparison: 54 in 2-blade vs 54 in toroid (C vs D, same mesh, 2280 rpm, hot day)

| Quantity | C: 2-blade 54x18 | D: toroid 2-loop / 4-leg | Toroid vs 2-blade |
|---|---|---|---|
| Thrust T [N] | 437.4 | 436.3 | −0.2 % (equal) |
| Torque Q [N·m] | 35.88 | 38.56 | **+7.5 %** |
| Shaft power [W] | 8,567 | 9,206 | +7.5 % |
| Figure of merit | **0.590** | 0.547 | −0.043 |
| C_T (hover) | 0.00995 | 0.00993 | |
| Viscous torque share | 10.2 % | 13.0 % | more wetted area |
| T/W at 2280 rpm | 1.053 | 1.051 | |
| Mean y+ | 31.5 | 30.0 | |
| checkMesh | fail: 2 skewed faces | fail: 20 skewed faces | |

### Scaled to the T/W 1.5 target (622.8 N per rotor, constant C_T)

| Quantity | C: 2-blade | D: toroid |
|---|---|---|
| rpm needed | 2,721 | 2,724 |
| Torque [N·m] | 51.09 | 55.03 |
| Power [W] | 14,556 | 15,698 |
| Motor current (U15XL) [A] | 203 | 219 |

The U15XL has 180 A peak and 2554 rpm available, so **neither rotor reaches T/W 1.5 on the U15XL**.

### Ceiling on the U15XL (2554 rpm, ~45.2 N·m)

| | C: 2-blade | D: toroid |
|---|---|---|
| Limit | speed (2554 rpm) | torque (at 2469 rpm) |
| Max thrust [N] | 548.6 | 511.8 |
| **Max T/W** | **1.32** | **1.23** |

---

## 4. CFD vs BEMT hand calculations (all cases)

| Case | CFD thrust | BEMT thrust | CFD vs BEMT | CFD torque | BEMT torque | CFD vs BEMT | CFD FoM | BEMT FoM |
|---|---|---|---|---|---|---|---|---|
| A: C–T baseline | C_T 0.00440 | C_T 0.00602 | −26.9 % | | | | 0.318 | |
| B: C–T LE mesh | C_T 0.00443 | C_T 0.00602 | −26.3 % | | | | 0.353 | |
| C: 54 in 2-blade | 437.4 N | 584.8 N | **−25.2 %** | 35.88 N·m | 39.02 N·m | −8.1 % | 0.590 | 0.838 |
| D: 54 in toroid | 436.3 N | 620.1 N (tip loss) / 636.0 (closed tip) | **−29.6 %** / −31.4 % | 38.56 N·m | 42.54 / 42.66 N·m | −9.4 % | 0.547 | 0.840 / 0.870 |

**Pattern:** on every geometry, BEMT is 25–31 % optimistic on thrust and ~8–9 % on torque, so its figure of merit is far too high (0.84 vs 0.55–0.59).
The design log (`Props/01_54x18_Composite/DESIGN_EXPLORATION.md`, entries 43–44) calibrated BEMT on case C. At equal thrust, CFD needs **1.16× the rpm, 1.23× the torque and 1.42× the power** of plain BEMT, and this moved the motor sizing (hex → MN1320; tri only on the U15XL with no reserve). The fitted pitch loss / extra drag was a₀ 3.97°, Δc_d 0.0327 (2-blade) and a₀ 4.64°, Δc_d 0.0358 (toroid).

---

## 5. Key takeaways

1. **Thrust is trustworthy, torque is conservative.** The validation matches experimental thrust within ~4 %. Torque falls ~9 % with leading-edge refinement and probably has ~15 % more to fall, so the C/D torques (0.62 mm curvature cells, no dedicated LE tube) are likely somewhat high.
2. **The 2-blade 54x18 beats the toroid.** At equal thrust the toroid costs +7.5 % torque and power, has a lower FoM (0.547 vs 0.590), and hits the U15XL torque limit first (T/W 1.23 vs 1.32).
3. **BEMT absolute numbers need the CFD correction.** Payloads and motor sizing from uncorrected BEMT are 5–10 kg optimistic (per the design log).
4. **No rotor reaches T/W 1.5 on the U15XL** in CFD. Both need ~203–219 A against 180 A peak.

## 6. Gaps / recommended next runs

- A finer leading-edge (or "medium") mesh on the **2-blade 54x18** (case C) to split the 23 % torque excess between physics and mesh artefact (design-log queue item 55).
- A second rpm or loading point on case C, to check that the BEMT correction holds across loadings.
- Fix the skewed faces flagged by checkMesh in C (2 faces) and D (20 faces).
- No CFD yet for other prop sizes, pitches or blade counts (e.g. the 3-blade, coax or diameter-study variants in `Props/01_54x18_Composite/results/explore/`). Those are BEMT-only.

## Sources (branch `prop-54x18`)

- `CFD_Results/README.md`, `CFD_Results/01_54x18_Composite/README.md`, `CFD_Results/02_Toroidal_Rotor/README.md`
- `CFD_Results/01_54x18_Composite/caradonna_tung_coarse{,_le}/README.md` and `ct_cfd_*.json`
- `CFD_Results/02_Toroidal_Rotor/{reference_prelim,toroid_prelim}/README.md` and `summary.json`
- `Props/01_54x18_Composite/DESIGN_EXPLORATION.md` (entries 43, 44, queue items 44/54/55)

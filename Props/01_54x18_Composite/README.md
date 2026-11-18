# 54″ × 18″ composite heavy-lift propeller

Design, simulation and verification of a carbon-composite propeller for a 280 lb MTOW tricopter. The brief is
`Prompts/fable_heavy_lift_prop_prompt.md` at the repository root.

**Status: Phases 0–3 done (environment, sizing, airfoils + BEMT + blade design, geometry). Decisions so far: MTOW stays 280 lb with
payload as an output; diameter stays 54″. Next is Phase 4.0, the Caradonna–Tung CFD validation.** Read the reports in order:
`PHASE1_REPORT.md`, `PHASE2_REPORT.md`, `DIAMETER_STUDY.md`, `PHASE3_REPORT.md`. Claims and assumptions are in `REGISTERS.md`.

## Run

```bash
make all
```

That runs, in order: `tools/get_xfoil.sh` (fetches XFOIL locally if missing), the environment report, the unit tests (pytest if
installed, otherwise `run_tests.py`), Phase 1, Phase 2 (about 4 minutes; XFOIL polars are cached in `results/polars/`), the diameter
study, and the Phase 3 geometry build (needs `gmsh`, OpenFOAM 13 and optionally `pvpython`). Each step also has its own target:
`make phase1`, `make phase2`, `make diameter`, `make geometry`.

OpenFOAM cannot run in a path with spaces, so its cases live under the `cfd.run_root` folder named in `params.yaml`.

### Phase 4.0 CFD (Caradonna–Tung validation), where it stands

The `coarse` run (600 iterations) over-predicts torque: about 83.5 N·m against roughly 62 N·m expected from the hand calculation. The
diagnosis is lost leading-edge suction: its 3.1 mm leading-edge cells span a 3.0 mm nose radius. The `coarse_le` mesh adds a level-9
tube (0.78 mm cells) along each leading edge. It ran to 1500 iterations and converged (CQ drift -0.13 % per 100
iterations). Torque fell to 75.8 N·m (-9 %) with thrust unchanged (CT 0.00443, -3.5 % vs. experiment), and the figure of merit
rose from 0.318 to 0.353. The torque split puts about another 11 N·m in still-missing leading-edge suction, so the next step is
a finer blade surface. Summaries of both meshes are in `CFD_Results/01_54x18_Composite/` at the repository root (written by
`python3 src/ct_export.py coarse coarse_le`). The full case lives under `cfd.run_root`, and copies of its setup and logs are in
`cfd/00_validation_caradonna_tung/coarse_le/`.

```bash
python3 src/ct_validation.py resume coarse_le    # continue from the last saved iteration (10 cores, about 12 s per iteration)
python3 src/ct_validation.py status coarse_le    # progress, CT, CQ, torque drift, outlet flow
python3 src/ct_validation.py post coarse_le      # after it converges: CT/CQ vs. data, Cp sections, convergence plot
```

Then split the torque into its pressure and viscous parts and their chordwise and normal components: touch `coarse.foam` in the case
folder, then run `pvpython src/ct_torque_split.py <case> <time> 1.221248 results/ct_torque_split_coarse_le.json`. Compare it with
`results/ct_torque_split_coarse.json`. To pause a run cleanly, set `stopAt writeNow;` in the case's `system/controlDict`; the solver
saves the current iteration and exits. Set it back to `endTime` before resuming. `run` (instead of `resume`) starts again from
iteration 0.

## Layout

| Path | What it is |
|---|---|
| `params.yaml` | Single source of truth for every input. Requirements and assumptions are marked. |
| `data/catalog.yaml`, `data/*.csv` | Vendor catalog data with source URLs |
| `src/atmosphere.py` | ISA pressure, density, viscosity, speed of sound |
| `src/momentum.py` | Actuator-disk theory, coefficient conventions, first-order blade-element sizing |
| `src/motor_match.py` | KV, current and ESC matching |
| `src/mission.py` | Trim, forward-flight power, mission energy, mass budget |
| `src/prelim_checks.py` | First-pass balance, misalignment and flex numbers |
| `src/phase1.py` | Phase 1 driver |
| `src/airfoils.py` | XFOIL runner, Viterna extension, polar database |
| `src/bemt.py` | Blade-element momentum solver: hover, climb, forward flight |
| `src/design_opt.py` | Minimum-induced-loss design, constraints, constant-pitch candidates |
| `src/phase2.py`, `src/diameter_study.py` | Phase 2 driver and the diameter study |
| `src/geometry.py`, `src/render_stl.py` | Phase 3 geometry, STEP/STL export, checks, renders |
| `geometry/` | Generated CAD and STL (git-ignored) |
| `tests/` | Unit tests against closed-form limits and the brief's hand numbers |
| `results/` | JSON outputs and plots |
| `PHASE*_REPORT.md`, `DIAMETER_STUDY.md`, `REGISTERS.md`, `ENVIRONMENT.md` | Generated; do not edit by hand |

Not built yet: CFD cases, structures and FE, thermal, balance, the motor-drive export and the final design PDF (`make_design_doc.py`).

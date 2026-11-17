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

# Prop 02: toroidal (closed-loop) rotor

A toroidal rotor for the 280 lb tricopter (55 lb drone + 225 lb payload) that has to reach **T/W 1.5 on the hot day**:
623 N per rotor. It keeps the 54″ disk of the 2-blade reference in `../01_54x18_Composite`, so the comparison is about
the loop alone. Each of the 2 loops is a leading leg, a tip turn, a trailing leg and a root turn (the hub stand-in);
each leg has half the reference chord, so solidity and blade loading match.

The design document is `02_Toroidal_Rotor_Design.pdf` (built by `make_design_doc.py` from `results/*.json`). It has
the momentum, blade-loading, tip-loss and loop-geometry math, the blade-element hand calculation, the mass bracket and
the CFD setup. Its CFD column fills in after the run.

Inputs from the prop program are read, not copied: the reference blade (`results/blade_final.csv`), its XFOIL polar
cache, the atmosphere model and the U15XL motor data.

## Status

Sizing, geometry and both OpenFOAM cases are done, meshed and smoke-tested (10 solver iterations each, then reset).
**Both CFD runs are done and converged (2280 rpm, hot day, same mesh recipe). Neither reaches T/W 1.5 on the U15XL.**
The toroid makes 436 N for 38.6 N·m (FoM 0.55); the 2-blade reference makes 437 N for 35.9 N·m (FoM 0.59). Both are ~25-30 % below their blade-element estimates, the same over-prediction the Caradonna-Tung check found, so the loop's own cost is the 7.5 % extra torque at equal thrust. Motor ceilings (speed 2554 rpm or torque 45.2 N·m, whichever binds first): toroid T/W 1.23 (torque-limited at 2469 rpm), 2-blade T/W 1.32 (speed-limited). Summaries in `CFD_Results/02_Toroidal_Rotor/`.

Blade-element numbers at T/W 1.5: 2285 rpm, 42.7 N·m, 10.2 kW, 170 A on the
U15XL (2-blade reference: 2350 rpm, 41.6 N·m, 166 A). Both cases run at 2280 rpm.

| Case | Cells | Layer coverage | checkMesh | Solver memory | Time for 1500 iterations (10 cores) |
|---|---|---|---|---|---|
| `toroid_prelim` | 2.76 M | 95 % | 20 skewed faces (max 7.0) | 4.6 GB | about 5.5 h |
| `reference_prelim` | 2.15 M | 94 % | 2 skewed faces (max 4.9) | 3.6 GB | about 4.3 h |

Max non-orthogonality is under 65° on both. The few highly skewed faces are the only checkMesh flags; the bounded,
limited schemes are the same ones that ran the Caradonna-Tung case, and the guard stops a run that goes non-physical.
Run the two one after the other, not side by side.

## Run the CFD

OpenFOAM cannot run in a path with spaces, so the case lives under `~/OpenFOAM/elijah-callahan-13/run/toroid/toroid_prelim`.
Logs and the case setup are copied back to `cfd/toroid_prelim/`.

```bash
cd "/home/elijah-callahan/Claude Access Folder for LTSpice/Props/02_Toroidal_Rotor"
```

```bash
nohup python3 src/toroid.py run toroid > results/run_toroid.txt 2>&1 &
```

```bash
python3 src/toroid.py status toroid
```

```bash
python3 src/toroid.py post toroid && python3 make_design_doc.py
```

`post` also exports the case summary, force history and plots to the shared results folder
`CFD_Results/02_Toroidal_Rotor/<rotor>_prelim/` at the repository root (one folder per case, no time or processor
folders; layout agreed with the 54x18 prop session).

`run` starts from iteration 0 (1500 iterations, 10 cores). If it is interrupted, continue with
`python3 src/toroid.py resume toroid`; it restarts from the last write (every 100 iterations). To pause cleanly, set
`stopAt writeNow;` in the case's `system/controlDict`, and set it back to `endTime` before resuming. The guard stops the
run by itself if the thrust or the outlet flow goes non-physical (`results/guard_toroid.json` says why).

For a fair comparison, the 2-blade reference runs on the same mesh recipe at the same 2280 rpm (case
`~/OpenFOAM/elijah-callahan-13/run/toroid/reference_prelim`, built by `case reference` and `mesh reference`). Run it after
the toroid, not beside it: one 10-core solve at a time.

```bash
nohup python3 src/toroid.py run reference > results/run_reference.txt 2>&1 &
```

```bash
python3 src/toroid.py post reference
```

## Optimisation (started 2026-11-18)

Goal: T/W 1.5 inside the U15XL envelope (2554 rpm on a sagged pack, 45.2 N·m = 180 A), at the lowest blade-set mass.
Inside that envelope the shaft power is at most ~12.1 kW, so T/W 1.5 needs a figure of merit of at least 0.71 at C_T 0.0113.

1. **Where the thrust goes** (`loads`): CFD pressure forces split by loop segment and radius. Both legs run ~35 % under the
   blade-element loading inboard; outboard, where the legs stack, the trailing leg carries only ~79 % of the leading one.
   ```bash
   pvpython src/extract_surface.py <case> toroid.foam 1500 <case>/surface_1500.npz && python3 src/toroid.py loads toroid 1500
   ```
2. **CFD-anchored model** (`src/optimize.py calibrate`): the blade-element model with an effective pitch loss
   (a0 + a1 (r/R - 0.6)) and an extra section drag dcd, fitted to the CFD thrust per span and total torque.
3. **Sweep** (`optimize.py sweep`): leg chord x collective pitch x twist slope against the motor envelope. Best predicted
   T/W 1.42 (legs 0.25 x chord, +8 deg), so no point reaches 1.5 on this motor; thinner legs win on mass and T/W because
   they absorb the torque limit right at the speed limit. Results: `results/opt_sweep.json`, `fig_opt_sweep.png`.
4. **Candidates** live under `variants:` in `params.yaml` and run through the same stages with their own name
   (`geometry`, `case`, `mesh`, `run`, `post` with `toroid_opt1` etc.). `optimize.py predict <variant>` records the model's
   forecast before the CFD, so the CFD tests the model.
5. **Candidate 1 by CFD (2550 rpm, converged): forecast failed.** 544 N and 50.0 N·m against the forecast 593 N and 46.0 N·m; FoM 0.53 (as-built toroid 0.55), ceiling T/W 1.19. The thinner legs cured the leg-to-leg interference (trailing leg 94 % of the leading, up from 79 %) but lost more to pressure drag at high lift, on noses about one cell wide. The model's constant extra drag does not carry over to thinner, higher-pitched blades on this mesh.

## Rebuild everything before the CFD

```bash
python3 src/toroid.py sizing && python3 src/toroid.py geometry && python3 src/toroid.py case toroid && python3 src/toroid.py mesh toroid
```

`mesh` takes optional arguments: the number of meshing processes and a free-memory floor in GB
(`python3 src/toroid.py mesh toroid 6 1.5`). Below the floor a watchdog stops the mesher, so meshing beside another
solver run cannot push that run into swap. When the meshing count differs from the solver's 10, the mesh is gathered
and split again for the solver.

## Files

| Path | What it is |
|---|---|
| `params.yaml` | Every input; requirements and assumptions marked |
| `src/toroid.py` | All stages: sizing, geometry, case, mesh, run, resume, status, post |
| `make_design_doc.py` | The design PDF, from the result files |
| `results/sizing.json` | Requirements, momentum theory, BEMT of the reference and of the legs, the CFD speed |
| `results/geometry.json`, `fig_geometry.png` | STL checks, areas, volumes, leg gaps, mass bracket, views |
| `results/case_*.json`, `mesh_*.json` | Case and mesh summaries (cells, quality, layers, surface checks) |
| `results/cfd_*.json`, `fig_convergence_*.png` | CFD results (after `post`) |
| `cfd/<rotor>_prelim/` | Copies of the case setup and logs |
| `geometry/toroid.stl` | Generated surface (git-ignored; `geometry` rebuilds it) |

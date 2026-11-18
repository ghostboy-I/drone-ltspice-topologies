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

Sizing, geometry and the OpenFOAM case are done. **The CFD run has not been made yet.** Blade-element numbers at T/W 1.5:
2285 rpm, 42.7 N·m, 10.2 kW, 170 A on the U15XL (2-blade reference: 2350 rpm, 41.6 N·m, 166 A). The case runs at
2280 rpm.

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

`run` starts from iteration 0 (1500 iterations, 10 cores). If it is interrupted, continue with
`python3 src/toroid.py resume toroid`; it restarts from the last write (every 100 iterations). To pause cleanly, set
`stopAt writeNow;` in the case's `system/controlDict`, and set it back to `endTime` before resuming. The guard stops the
run by itself if the thrust or the outlet flow goes non-physical (`results/guard_toroid.json` says why).

Optional, for a fair comparison: the 2-blade reference on the same mesh recipe.

```bash
python3 src/toroid.py case reference && python3 src/toroid.py mesh reference && nohup python3 src/toroid.py run reference > results/run_reference.txt 2>&1 &
```

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

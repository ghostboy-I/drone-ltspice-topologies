# Airframe 02: Osprey-style tilt-tricopter frame

A V-22-look frame for the 280 lb vehicle (225 lb payload: five 45 lb bumper plates) on the prop program's three 54 in
rotors. Two front rotors tilt on wingtip pods for wing-borne cruise at 25 m/s; the third is a fixed lift rotor on the
tail boom. Rotor, motor, mission and material numbers are **read** from `Props/01_54x18_Composite` and
`Airframe/01_Tricopter_Fuselage`, never copied.

The design document is `02_Osprey_TiltTri_Design.pdf` (built by `make_design_doc.py`).

## User decisions this design rests on (2026-11-18)

| Question | Decision |
|---|---|
| Rotor count | 3 rotors, Osprey look (a twin needs 623 N per 54 in rotor to hover) |
| Conversion | Real tilt, faster cruise |
| Mass | 280 lb MTOW, 225 lb payload (55 lb drone target, known not to close) |
| Wing | Long wing, 25 m/s cruise: V-22 proportions need ~67 m/s, the fixed-pitch prop stops pulling at ~33 m/s |

## Pipeline

```bash
python3 src/sizing.py                 # XFOIL wing polars, wing, layout, tail, drag, cruise thrust, download, gusts (~1 min)
python3 src/screen.py sweep 600       # FEM design sweep, nice 19 on 2 cores (~5 min); writes designs/selected.json
python3 src/screen.py check designs/selected.json   # one design, PASS/FAIL in ~1 s
python3 src/geometry.py               # STL (hover + airplane), rotor disks, 3-view and iso figures
python3 src/make_results.py           # final.json, hand checks of the FE model, figures
python3 src/cfd_airfoil2d.py setup    # 2-D OpenFOAM airfoil cases (wing NACA 4415 + tail NACA 0012)
python3 src/fuselage_shell.py         # CalculiX shell model of the fuselage, five load cases (~6 min, 1 thread, nice 19)
python3 make_design_doc.py
```

CFD runs (OpenFOAM 13 cannot use this repo's path, which has spaces, so cases live in
`~/OpenFOAM/$USER-13/run/osprey_airfoil2d/`):

```bash
~/OpenFOAM/$USER-13/run/osprey_airfoil2d/run_all.sh      # waits while another foamRun is on the machine, 2 cores
python3 src/cfd_airfoil2d.py post                         # CFD vs XFOIL -> results/, CFD_Results/02_Osprey_TiltTri/
```

## Files

| Path | What it is |
|---|---|
| `params.yaml` | Every input: requirements, V-22 proportions (cited), assumptions (logged) |
| `src/tiltcfg.py` | Paths and loaders; links to the Props and Airframe/01 code |
| `src/sizing.py` | Conceptual sizing, all hand methods, writes `results/sizing.json` |
| `src/tiltframe.py` | Frame FE model in hover and airplane mode, five load cases, checks, verdict |
| `src/screen.py` | The instant check and the design sweep |
| `src/geometry.py` | Outer-mould-line STL + figures |
| `src/make_results.py` | Selected design, hand checks (H1-H3), figures, `results/final.json` |
| `src/fuselage_shell.py` | Fuselage shell FEM (CalculiX): keel, floor, frames (+ skin if `fuselage.skin: bonded`); loads cut from the beam model; hand checks F1-F3 |
| `src/cfd_airfoil2d.py` | 2-D RANS airfoil cases: C-grid blockMesh, Spalart-Allmaras, post-processing against XFOIL |
| `geometry/` | `airframe_hover.stl`, `airframe_airplane.stl`, `rotor_disks_hover.stl`, `wing_section.dat` |
| `cfd/airfoil2d/` | Case plan; logs and force histories copied back after the runs |
| `results/` | JSON and figures |

## Decided

- Fuselage skin (user, 2026-11-19): the fairing floats on compliant mounts and carries no fuselage load (`fuselage.skin:
  floating`). The bonded one-ply skin buckled at 0.01-0.15 of ultimate; that run is kept in `results/*_bonded.*`.

- Modal rule (user, 2026-11-18): +-15 % bands around 1P / 2P at the two operating points (MTOW hover on a hot day, airplane
  cruise), direction-aware as Airframe/01, instead of 01's envelope band (16.6-78.6 Hz), which no frame this size clears.
  Envelope crossings are still flagged in `results/final.json` for off-design weights and air.

## Open items (need a decision or a run)

- Tail-boom + aft-cone download, 8.6 % of the tail rotor's thrust: an airfoil-section boom is the fix.
- Real vehicle mass (~185 kg) against the 280 lb (127 kg) sizing weight: the wing stalls at ~25 m/s at the real mass.
- Whirl flutter, prop normal force in airplane mode, transition corridor: not modelled yet.
- Boom fitting and wing carry-through fitting (fuselage shell FEM, floating fairing): the keel alone fails where the boom enters
  its shallow tail end (LC5 web MS -0.89) and at the rigidly fixed wing-attach frames (LC4 web MS -0.54). Between them it has a
  large margin. Design both fittings, add them to `fuselage_shell.py`, re-run.
- tiltframe.py hangs the keel 0.09 m below the mould line's belly; the shell model puts it inside. Fix and re-sweep.
- 3-D download CFD: inputs ready, not run.

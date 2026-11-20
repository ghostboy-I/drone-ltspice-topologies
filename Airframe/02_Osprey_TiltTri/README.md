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
python3 src/sizing.py                 # XFOIL wing polars (free + tripped), section, wing, incidence, layout, tail, drag, cruise, download, gusts (~1 min)
python3 src/screen.py sweep 600       # FEM design sweep, nice 19 on 2 cores (~5 min); writes designs/selected.json
python3 src/screen.py refine 400 designs/selected.json wing,pod   # local refine of the named components only (the rest frozen)
python3 src/screen.py check designs/selected.json   # one design, PASS/FAIL in ~1 s
python3 src/geometry.py               # STL (hover + airplane), rotor disks, 3-view and iso figures
python3 src/make_results.py           # final.json, hand checks of the FE model, figures
python3 src/cfd_airfoil2d.py setup ls417mod   # 2-D OpenFOAM airfoil cases for the wing section (earlier cases are kept)
python3 src/fittings.py               # hand sizing of the wing lugs, spar frames, boom socket and main-gear saddles -> results/fittings.json
python3 src/fuselage_shell.py         # CalculiX shell model of the fuselage with the fittings, five load cases (~1 min, 1 thread)
python3 src/fittings.py               # again: the lug design load takes the FE split if it is larger
python3 src/wing_shell.py             # CalculiX shell model of the wing box + ribs on the four lugs (~2 min, 2.2 GB RAM)
python3 src/fittings.py               # once more: the lug design load takes the wing FE split if it is larger
python3 src/transition.py             # trim grid over speed x nacelle angle on the Props blade model, 127 + 183 kg (~2 h, nice 19, 2 cores)
python3 src/transition.py --post      # paths, missions and hand checks only, from the saved grid (30-60 min)
python3 src/transition_figs.py        # corridor, power vs speed, transition time history
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
| `src/wing_sections.py` | Wing sections for every model: XFOIL runner for NACA codes and coordinate files, Lednicer/Selig reader, t/c, spar depth, the contour pitched by the incidence, the spar feet and the fuselage top |
| `src/tiltframe.py` | Frame FE model in hover and airplane mode, five load cases, checks, verdict |
| `src/screen.py` | The instant check and the design sweep |
| `src/geometry.py` | Outer-mould-line STL + figures |
| `src/make_results.py` | Selected design, hand checks (H1-H3), figures, `results/final.json` |
| `src/fuselage_shell.py` | Fuselage shell FEM (CalculiX): keel, floor, frames (+ skin if `fuselage.skin: bonded`), fittings if `fuselage.fittings`; loads cut from the beam model; hand checks F1-F3, H1-H3 |
| `src/wing_shell.py` | Wing shell FEM (CalculiX): box skins, spar webs and ribs on the true section contour at the wing incidence, tapered caps, four pinned lugs, beam-model free-body loads; hand checks W1-W6 (equilibrium, lug split, beam theory, Bredt, tip deflection, panel buckling between ribs). `--build` writes `fea/wing/wing_static.inp` for running ccx elsewhere, `--post` reads the results back |
| `src/fittings.py` | Wing carry-through (four bolted lugs, heavy spar frames by a closed-ring unit-load solution with arch thrust) boom socket (two collars, two bulkheads) and main-gear saddles + diaphragm (lever-rule split, core crush, bolts, Bredt torsion) sized by hand |
| `src/transition.py` | Pitch-plane trim of the whole vehicle on the Props/01 blade model (bemt.edgewise for every rotor at its own disk angle): conversion corridor, minimum-power nacelle schedule, quasi-steady accelerating/decelerating transition, three mission strategies; hand checks H1-H4 (hover statics, cruise vs sizing and axial BEMT, statics closure, rotor energy budget) -> `results/transition.json` |
| `src/transition_figs.py` | `fig_corridor.png`, `fig_power_speed.png`, `fig_transition.png` |
| `src/cfd_airfoil2d.py` | 2-D RANS airfoil cases: orthogonal Hermite C-grid, Spalart-Allmaras, polar plot against XFOIL. Lift only: OpenFOAM 13's wall shear is +48 % (channel test), so section drag comes from XFOIL |
| `geometry/` | `airframe_hover.stl`, `airframe_airplane.stl`, `rotor_disks_hover.stl`, `wing_section.dat` |
| `geometry/airfoils/` | UIUC coordinate files (m-selig.ae.illinois.edu/ads): NASA LS(1)-0417, LS(1)-0417MOD, NLF(1)-0416 (+ Selig-order copies) |
| `cfd/airfoil2d/` | Case plan; logs and force histories copied back after the runs |
| `results/` | JSON and figures |

## Decided

- Wing rework (user, 2026-11-20): pick the section for lift and set the incidence. The LS(1)-0417MOD (17 %, tripped
  clmax 1.85 vs 1.64) at 11.6 deg incidence; the fuselage flies level. Smaller wing (3.10 vs 3.48 m^2), airframe
  30.65 vs 32.87 kg, cruise 80.8 vs 75.7 Wh/km. Keel, boom and gear frozen at the shell-verified design; wing + pods refined.

- Airfoil CFD (user, 2026-11-19): lift only; section drag stays on XFOIL. OpenFOAM 13's incompressibleFluid and the legacy
  porousSimpleFoam both over-predict laminar channel wall shear by 48 % (icoFoam is exact).

- Fuselage skin (user, 2026-11-19): the fairing floats on compliant mounts and carries no fuselage load (`fuselage.skin:
  floating`). The bonded one-ply skin buckled at 0.01-0.15 of ultimate; that run is kept in `results/*_bonded.*`.

- Modal rule (user, 2026-11-18): +-15 % bands around 1P / 2P at the two operating points (MTOW hover on a hot day, airplane
  cruise), direction-aware as Airframe/01, instead of 01's envelope band (16.6-78.6 Hz), which no frame this size clears.
  Envelope crossings are still flagged in `results/final.json` for off-design weights and air.

## Open items (need a decision or a run)

- Tail-boom + aft-cone download, 8.6 % of the tail rotor's thrust: an airfoil-section boom is the fix.
- Real vehicle mass (~185 kg) against the 280 lb (127 kg) sizing weight: the wing stalls at ~25 m/s at the real mass.
- Whirl flutter and the prop normal force in airplane mode: not modelled yet.
- **Transition / forward flight on the designed props (2026-11-20, src/transition.py, design doc sec. 12):** at 127 kg
  airplane mode trims 21-29 m/s (wing stall below, prop rpm above), nacelles up to 26 m/s, and every angle trims from
  21 to 26 m/s. The 54 x 18 hover props are poor airplane props (eta 0.71 vs ideal 0.96 at 25 m/s: J 0.49 near the
  zero-thrust J 0.56) but good edgewise lifters, so **partial conversion** (nacelles ~70 deg, tail rotor parked, wing
  62 % of the lift) is the cheapest cruise: 52.7 Wh/km against 77.8 in airplane mode. At the 183 kg estimate airplane
  mode shrinks to 25-27 m/s. Transition out 24 s / 90 Wh at 1 m/s^2; back only at 0.5 m/s^2 (pitch limit). Tail
  incidence rigged to 10.3 deg (elevator neutral at 25 m/s). Open before partial conversion is a cruise mode: blade/hub
  fatigue at the edgewise 1P loads (+-36 N m on 33 N m mean, 41 N m hub roll moment), rotor wake on the wing, the
  ASSUMED pitch limits [-10, +15] deg.
- **Strain-axis correction and resize (2026-11-20):** CalculiX 2.21 writes composite-shell strains in element-local
  axes; read correctly, LC4 failed at the spar frames' web feet. Fixed with 30 mm caps on the spar frames (T sections),
  vertical web posts at those frames and +3 +-45 keel-web doublers (also over the socket bay and the nose gear), +1.4 kg.
  All fuselage margins positive. After the wing rework: front frame 6.0 mm (hand target MS 0.15), bay doubler on to the
  gear frame; tightest LC4 front-frame web-foot junction +0.05 (a shell-intersection peak; bonded clip in the drawings).
  `*_nofit.json` still carries the old reading.
- Wing (src/wing_shell.py, LS(1)-0417MOD): all strain margins positive; centre-bay panel buckling MS +0.07 (LC1); the
  front lug brackets drop 64 mm to the level fuselage (hand check MS +0.77). The true-contour box is 1.54 x stiffer than
  the beam's flat box, so the beam's wing modes are ~24 % low. **Re-run the modal check with it**: an airplane-mode mode
  sits at 31.65 Hz, just under the in-plane 1P band (31.73 Hz).
- Wing size trade: decided (user, 2026-11-20): keep the smaller high-lift wing (~7 % more cruise energy, 2.2 kg lighter).
- LS(1)-0417MOD CFD (SA, steady): lift steady and rising to cl 1.76 at 15 deg, unsteady at 16; 5 % below the tripped-XFOIL
  clmax that sized the wing (stall 20.8 -> 21.4 m/s if the CFD were right). Zero-lift angle agrees (-3.47 vs -3.49 deg).
  A wind-tunnel polar at Re ~1e6 would settle the clmax.
- Main-gear saddles need solid core inserts (pad 2.2 MPa vs 0.9 MPa foam crush). Landing drag/spin-up loads and the nose
  gear are not modelled.
- Fittings mass (+3.0 kg, +0.7 kg for the gear saddles and doubler) and the boom extension are not in the beam model's mass yet.
- Tail cone end (0.196 x 0.124 m) is smaller than the 0.134 m boom: the fairing's aft closure must open around it.
- tiltframe.py hangs the keel 0.09 m below the mould line's belly; the shell model puts it inside. Fix and re-sweep.
- 3-D download CFD: inputs ready, not run.

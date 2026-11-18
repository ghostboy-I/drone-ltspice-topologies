# 02_Toroidal_Rotor

CFD of the toroidal (closed-loop) rotor from `Props/02_Toroidal_Rotor`, and of the 2-blade 54x18 reference blade on the
same mesh recipe, speed (2280 rpm) and hot-day air, so the two can be compared directly. Each case folder is written by
`python3 src/toroid.py post <rotor>` in that project; the design document `Props/02_Toroidal_Rotor/02_Toroidal_Rotor_Design.pdf`
has the derivations and the hand-calculation comparison.

| Case | Rotor | Status |
|---|---|---|
| [toroid_prelim/](toroid_prelim/) | 2 loops / 4 legs, 54 in | converged, 1500 iterations |
| `reference_prelim/` | 2-blade 54x18 Phase 3 blade | running (started 2026-11-18 14:13 EST) |

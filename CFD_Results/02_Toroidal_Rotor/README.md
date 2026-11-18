# 02_Toroidal_Rotor

CFD of the toroidal (closed-loop) rotor from `Props/02_Toroidal_Rotor`, and of the 2-blade 54x18 reference blade on the
same mesh recipe, speed (2280 rpm) and hot-day air, so the two can be compared directly. Each case folder is written by
`python3 src/toroid.py post <rotor>` in that project; the design document `Props/02_Toroidal_Rotor/02_Toroidal_Rotor_Design.pdf`
has the derivations and the hand-calculation comparison.

| Case | Rotor | Status |
|---|---|---|
| [toroid_prelim/](toroid_prelim/) | 2 loops / 4 legs, 54 in | converged, 1500 iterations |
| [reference_prelim/](reference_prelim/) | 2-blade 54x18 Phase 3 blade | converged, 1500 iterations |

At 2280 rpm both rotors make the same thrust (toroid 436 N, 2-blade 437 N); the toroid needs +7.5 % torque. On the U15XL (2554 rpm, 45.2 N·m) the ceilings are T/W 1.23 (toroid, torque-limited) and 1.32 (2-blade, speed-limited).

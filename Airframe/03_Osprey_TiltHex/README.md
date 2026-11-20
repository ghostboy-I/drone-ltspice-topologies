# Airframe 03: Osprey-style tilt-hex frame

A wing-borne frame for the decision matrix's winner, the hexacopter (`Props/02_Toroidal_Rotor/DECISION_MATRIX.md`, rank 1),
on the same basis as Airframe 02 (280 lb MTOW, 225 lb payload, 25 m/s, hot day) so the two compare one to one.
Four rotors tilt (two on the wing tips, two on pylons ahead of the wing, side by side); two fixed lift rotors sit on a
cross-beam behind the wing. The fuselage, wing (LS(1)-0417MOD, 3.10 m^2) and tail are Airframe 02's; everything that
holds rotors is new. The rotor is **read** from Props entry 46 (`results/explore/e46_hex_noise_curve.json`, MN1123 KV53,
0.65 cap, 24xx sections); the Phase 2 54x18 blade is carried as the alternative for the tilting rotors.

The design document is `03_Osprey_TiltHex_Design.pdf` (built by `make_design_doc.py`).

## User decisions (2026-11-20)

| Question | Decision |
|---|---|
| Concept | 4 tilting + 2 fixed aft rotors |
| Mass basis | Same as the Osprey: 280 lb MTOW, 225 lb payload, 25 m/s, hot day |
| Scope | Sizing + 3-D model + beam FEM screen + BEMT forward-flight trim (no shell FEM, no fittings) |
| Tilting rotors | Planar, on the wing (coaxial tip pairs were costed first: x1.45 pair power) |

## Pipeline

```bash
python3 src/sizing.py                 # rotor (hex + 54x18 on the MN1123), coax cost, layout, download, wing, tail, drag, cruise, gusts
python3 src/screen.py sweep 1500      # FEM design sweep, nice 19 on 2 cores (~16 min); writes designs/selected.json
python3 src/screen.py refine 600 designs/selected.json   # local refine (used after the trim moved the airplane 1P band)
python3 src/screen.py check designs/selected.json        # one design, PASS/FAIL in ~1 s
python3 src/geometry.py               # STL (hover + airplane), six disks, 3-view and iso figures
python3 src/transition.py             # trim grid, three cases (hex 127 kg, 54x18 tilting 127 kg, hex at the model mass), ~55 min
python3 src/transition_figs.py        # corridor, power vs speed, transition time histories
python3 src/make_results.py           # final.json (reads the cruise rpm from transition.json for the airplane modal band)
python3 make_design_doc.py
```

`make_results.py` runs after `transition.py` because the airplane-mode 1P band is centred on the trimmed cruise rpm.

## Headline numbers (127 kg design mass unless stated)

| | Tilt-hex, hex blades | Tilt-hex, 54x18 tilting | Airframe 02 tilt-tri |
|---|---|---|---|
| Hover, battery | 16.1 kW | 14.8 kW | 21.8 kW |
| Best range | 65.5 Wh/km (21 m/s, nacelles 70 deg) | 52.6 Wh/km (21 m/s, 70 deg) | 52.7 Wh/km (24 m/s, 70 deg) |
| Airplane mode | cannot trim (blade stops pulling at 18.5 m/s) | 21-34 m/s, 94 Wh/km best | 77.8 Wh/km |
| T/W on the MN1123 | 2.00 | 1.45 (torque-limited) | - |

See the design doc for the airframe mass, FEM margins and open items (whirl flutter, slipstream on the wing,
1P blade loads, real mass against 280 lb).

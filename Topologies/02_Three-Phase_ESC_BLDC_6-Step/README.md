# 02 — Three-Phase ESC + BLDC (6-step trapezoidal)

**Topology type:** 3-phase inverter (3 half-bridge legs, 6 FETs) driving a wye-connected BLDC, Hall-sensored 6-step commutation
**Builds on:** [01 Half-Bridge](../01_Half-Bridge_Motor_Drive/README.md). Each leg here is that circuit.
**Design document (with all the math):** `02_Three-Phase_ESC_BLDC_6-Step_Design.pdf`

## Files
| File | What it is |
|---|---|
| `ThreePhase_ESC_BLDC.asc` | LTspice schematic. Open it and press Run (about 6 min; `.step` runs both PWM modes) |
| `gen_schematic.py` | Script that generated the schematic. Edit and rerun it to change the layout |
| `plot_results.py` | Builds `ThreePhase_ESC_BLDC_results.png` from the `.raw` file |
| `make_design_doc.py` | Builds the design PDF: hand calculations plus the LTspice `.meas` results |
| `sweep_fsw.py` | Parallel PWM-frequency sweep (12 runs, 9 at a time), hand-calc checks, `sweeps/fsw_sync/fsw_sweep.png` |

## Techniques new in this design
- **Rotor angle by integration:** a 1 F capacitor charged by I = ω makes V(theta) = θm. Then θe = Pp·θm.
- **Trapezoidal back-EMF from one formula:** `trap(x) = limit(6/pi*asin(sin(x)), -1, 1)`, defined with `.func`.
- **Ideal Hall logic:** a phase drives HIGH when sin(θe − k·120°) > 0.5 and LOW when it is < −0.5.
- **Torque from power balance:** Te = Σ eₓiₓ / ω.
- **`.step param Sync list 0 1`:** compares high-side-only PWM (body-diode freewheel) against complementary PWM in one run.

## Results (50 % throttle, steady state 280–300 ms)
| | Sync=0 (diode freewheel) | Sync=1 (complementary) |
|---|---|---|
| Speed | 13,706 RPM | 14,178 RPM |
| Battery current | 2.93 A | 3.03 A |
| Low-side FET + diode loss | **2.75 W** | **0.60 W** |
| Efficiency | 83.2 % | 87.5 % |

![results](ThreePhase_ESC_BLDC_results.png)

## Lessons
1. In 6-step drive only two phases conduct, so the motor behaves like topology 01's DC motor: same R, L and Ke.
2. Yet it runs about 8 % slower than topology 01 at the same duty. Each commutation costs f_comm·L_ph·I ≈ 0.5 V
   of volt-seconds. The hand-vs-sim comparison found this; the first hand model, which left it out, was 9 % too fast.
3. Synchronous (complementary) PWM cuts low-side loss by about 4.6× (2.75 W → 0.60 W) because a FET drops ~27 mV where a diode drops ~0.8 V.
4. Torque has fast PWM ripple (about 41 mN·m p-p) plus slower commutation dips (about 16 mN·m p-p, 6 per electrical revolution) on 26 mN·m.
   Sinusoidal drive and FOC remove the dips.
5. A 7-pole-pair motor at 14.5k RPM commutates at about 10 kHz, so 48 kHz PWM gives only ~4.7 pulses per step.

## Experiments to try
- `Duty=0.9`: full throttle. Does the commutation loss grow?
- `Pp=6`: fewer pole pairs means fewer commutations per revolution.
- `Lph=15u`: more inductance means bigger commutation loss and smaller PWM ripple.
- `Fsw=24k`: count the PWM pulses per step in `V(pa)`.

## Parallel sweep: PWM frequency (`sweep_fsw.py`)
`python3 sweep_fsw.py` runs Fsw = 16k…96k × Sync = 0/1 (12 LTspice runs) with `../tools/sweep.py`, 9 at a time on this
20-core laptop: **12 min instead of ~40 min back-to-back**. Results: `sweeps/fsw_sync/results.csv` and `fsw_sweep.png`.
Validation first: the 48 kHz cases reproduce the table above to every printed digit.

![fsw sweep](sweeps/fsw_sync/fsw_sweep.png)

| Fsw | 16k | 24k | 32k | 48k | 64k | 96k |
|---|---|---|---|---|---|---|
| Efficiency, Sync=1 | 82.8 % | 85.7 % | 86.7 % | 87.5 % | 87.7 % | 87.7 % |
| Torque ripple p-p, Sync=1 (sim / hand) | 93 / 82 | 70 / 60 | 57 / 49 | 43 / 38 | 38 / 32 | 29 / 27 mN·m |

What it teaches:
1. **Ripple falls as 1/Fsw.** Volt-seconds on 2·Lph give ΔI = Vbus·D(1−D)/(2·Lph·Fsw), so torque ripple ≈ Ke·ΔI + 16 mN·m
   (the commutation dips do not depend on Fsw). Hand calc vs. LTspice agrees within ±16 % over a 6× frequency range.
2. **Efficiency here is set by ripple copper loss, not by switching loss.** A triangle ripple adds ΔI²/12 to I²rms, so
   P_cu,ripple = 2·Rph·ΔI²/12 ∝ 1/Fsw². Hand calc predicts 2.03 W less copper loss from 16 to 96 kHz; LTspice gives 2.54 W (Sync=1).
3. **Switching loss is real but small in this model**: high-side FET loss fits 0.26 W + 1.2 µJ × Fsw. That is +0.1 W from 16 to 96 kHz.
   A real ESC also pays gate-drive loss Qg·Vdrv·Fsw per FET and motor iron loss, which grows with Fsw.
   Those are not modeled, so the real optimum is lower than this plot's "faster is always better". Most ESCs run 24–48 kHz.
4. **Diode freewheel (Sync=0) runs faster at low Fsw** (14,774 RPM at 16 kHz vs 13,706 at 48 kHz). The likely cause (not yet
   confirmed on a waveform: rerun case_001 with `--keep-raw` and plot I(La)): with large ripple the phase current reaches zero during the off-time (discontinuous conduction). The terminal then floats up to the back-EMF,
   so the motor sees more average voltage than D·Vbus. Complementary PWM lets the current go negative, which keeps
   conduction continuous and the speed flat (14,100–14,200 RPM). That is one more reason ESCs use it: speed tracks throttle linearly.

Make your own sweep of any `.param` (from the `Topologies` folder):
```bash
python3 tools/sweep.py 02_Three-Phase_ESC_BLDC_6-Step/ThreePhase_ESC_BLDC.asc --param Lph=5u,7.5u,15u --param Sync=0,1 --name lph
```

**Note:** the `.raw` file is about 1.7 GB (two 300 ms runs). Delete it if you need the space. Running the simulation again recreates it.

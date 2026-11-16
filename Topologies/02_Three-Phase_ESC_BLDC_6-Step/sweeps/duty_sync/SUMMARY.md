# Duty × Sync sweep — 02 Three-Phase ESC + BLDC

Parallel sweep of `ThreePhase_ESC_BLDC.asc`: `Duty = 0.3, 0.5, 0.7, 0.9` × `Sync = 0, 1`,
8 LTspice runs, 6 at a time. Full precision is in `results.csv`; the table below rounds those entries.
Run by a Parallel Code agent; reviewed against `results.csv` (every table value checked) and the hand calc below added.

**Note on `iph_peak`:** this `.meas` runs FROM 0, so it is the **start-up** peak set by the 30 ms throttle ramp,
not the running current. Running phase current is ≈ ibat_avg / Duty (2.8–13.3 A).

**Validation:** the Duty = 0.5 rows reproduce the topology README table: 13,706 RPM / 83.2 % (Sync=0)
and 14,178 RPM / 87.5 % (Sync=1).

## Results

| Duty | Sync | rpm_final (RPM) | ibat_avg (A) | iph_peak (A) | pfet_hi (W) | pfet_lo (W) | pcu (W) | efficiency (%) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.3 | 0 | 8547.4 | 0.773 | 27.274 | 0.044 | 1.431 | 0.855 | 79.83 |
| 0.3 | 1 | 9206.8 | 0.834 | 28.652 | 0.059 | 0.217 | 1.028 | 89.36 |
| 0.5 | 0 | 13706.3 | 2.935 | 43.345 | 0.274 | 2.749 | 4.239 | 83.23 |
| 0.5 | 1 | 14177.9 | 3.026 | 44.205 | 0.298 | 0.601 | 4.625 | 87.49 |
| 0.7 | 0 | 18191.7 | 6.634 | 56.978 | 0.852 | 3.427 | 11.482 | 83.74 |
| 0.7 | 1 | 18437.3 | 6.751 | 56.397 | 0.888 | 1.247 | 12.054 | 85.53 |
| 0.9 | 0 | 22071.0 | 11.881 | 67.987 | 2.029 | 3.190 | 23.716 | 83.30 |
| 0.9 | 1 | 22147.5 | 11.931 | 67.230 | 2.046 | 2.150 | 24.024 | 83.78 |

## Speed vs throttle

Speed rises with throttle in both modes, but each equal duty increment buys less speed
(Sync=0: +5,158.9 RPM from 0.3→0.5, then +4,485.4, then +3,879.3; Sync=1: +4,971.1, +4,259.4, +3,710.2).
The two modes converge at high throttle: Sync=1 is 659.4 RPM faster at Duty=0.3, 471.6 RPM at 0.5,
245.6 RPM at 0.7, and only 76.5 RPM at 0.9.

## Efficiency vs throttle

Sync=0 peaks mid-throttle: 79.83 % → 83.23 % → 83.74 % → 83.30 % for Duty 0.3 → 0.9.
Sync=1 falls monotonically over the same range: 89.36 % → 87.49 % → 85.53 % → 83.78 %, because
copper loss (`pcu` 1.028 W → 24.024 W) grows faster than the fixed losses as current rises.
Complementary PWM's advantage therefore shrinks with throttle: +9.53, +4.26, +1.80 and +0.47
percentage points at Duty = 0.3, 0.5, 0.7 and 0.9.

## Low-side FET loss and synchronous PWM savings

With Sync=0 the low side freewheels through the body diode: `pfet_lo` is 1.431 W at Duty=0.3,
2.749 W at 0.5, 3.427 W at 0.7, then 3.190 W at 0.9. With Sync=1 the low-side FET conducts instead
(0.217 W, 0.601 W, 1.247 W, 2.150 W), and loss keeps rising with current.

| Duty | pfet_lo Sync=0 (W) | pfet_lo Sync=1 (W) | Saved (W) | Ratio | Reduction |
|---:|---:|---:|---:|---:|---:|
| 0.3 | 1.431 | 0.217 | 1.214 | 6.60× | 84.85 % |
| 0.5 | 2.749 | 0.601 | 2.148 | 4.57× | 78.14 % |
| 0.7 | 3.427 | 1.247 | 2.181 | 2.75× | 63.62 % |
| 0.9 | 3.190 | 2.150 | 1.040 | 1.48× | 32.60 % |

Synchronous PWM saves the most power in absolute terms around 0.5–0.7 duty (2.15–2.18 W), but its
relative benefit is largest at low throttle (6.60× at Duty=0.3 versus 1.48× at 0.9). The reason is *when* the
diode conducts. It only carries the freewheel current during the PWM off-time, a fraction (1 − D) of each period.
The saving is the diode drop minus the FET drop over that time:

    P_saved ≈ (1 − D) · I · (V_diode − I · R_on),   I ≈ ibat_avg / D (phase current while conducting),
    V_diode = N·Vt·ln(I/Is) + I·Rb  (body-diode model: N = 1.05, Is = 5 pA, Rb = 4 mΩ),  R_on ≈ 3 mΩ

| Duty | I (A) | Hand calc (W) | LTspice saved (W) | Error |
|---:|---:|---:|---:|---:|
| 0.3 | 2.78 | 1.43 | 1.214 | +18 % |
| 0.5 | 6.05 | 2.30 | 2.148 | +7 % |
| 0.7 | 9.64 | 2.25 | 2.181 | +3 % |
| 0.9 | 13.26 | 1.05 | 1.040 | +1 % |

The saving first grows with current, then collapses at Duty = 0.9 because the off-time shrinks to 10 %. The ratio
also falls because the *other* low-side loss, the low phase's FET that is on for the whole 120° interval,
grows as I²·R_on in both modes and does not change with Sync. The hand calc is 18 % high at Duty = 0.3 because the
ripple there (about 4.4 A p-p at 48 kHz) is larger than the 2.8 A average. The current nearly reaches zero during
the off-time, so the diode conducts less than the formula assumes (the same discontinuous-conduction effect that
`check_dcm.py` shows at 16 kHz).

All simulated values above are from `results.csv`; deltas, ratios and percentage-point differences are arithmetic
on those entries. The hand-calc column uses the schematic's ESC_FET model parameters.

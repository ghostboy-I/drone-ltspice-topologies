# Phase-inductance × Sync sweep — 02 Three-Phase ESC + BLDC

Parallel sweep of `ThreePhase_ESC_BLDC.asc`: `Lph = 3.75u, 7.5u, 15u, 30u` × `Sync = 0, 1`,
8 LTspice runs, 8 at a time, finished in 412 s. Full precision is in `results.csv`; the tables below
round those entries. Run by a Parallel Code agent and reviewed against `results.csv`; the review
corrected hand calcs 2 and 3 and the final section (see the review notes there).

Constants used for the hand calculations: `Vbus = 15.2 V`, `D = 0.5`, `Fsw = 48 kHz`, `Rph = 0.05 Ω`, `Ke = 60/(2π·2300) = 4.1519e-3 V·s/rad`, `Pp = 7`.

**Validation:** the `Lph = 7.5u` rows reproduce the topology README table: 13,706.3 RPM / 83.23 % for
Sync=0 and 14,177.9 RPM / 87.49 % for Sync=1.

## Results

| Lph | Sync | rpm_final (RPM) | ibat_avg (A) | iph_rms (A) | te_ripple (mN·m) | pcu (W) | pfet_lo (W) | efficiency (%) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 3.75u | 0 | 14,376.2 | 3.378 | 6.153 | 56.3 | 5.689 | 3.000 | 81.95 |
| 3.75u | 1 | 14,675.7 | 3.415 | 6.340 | 71.7 | 6.059 | 0.720 | 85.75 |
| 7.5u | 0 | 13,706.3 | 2.935 | 5.316 | 37.2 | 4.239 | 2.749 | 83.23 |
| 7.5u | 1 | 14,177.9 | 3.026 | 5.568 | 43.1 | 4.625 | 0.601 | 87.49 |
| 15u | 0 | 12,970.9 | 2.457 | 4.598 | 26.9 | 3.181 | 2.435 | 83.73 |
| 15u | 1 | 13,407.4 | 2.568 | 4.878 | 26.8 | 3.582 | 0.579 | 88.03 |
| 30u | 0 | 11,936.1 | 1.974 | 3.967 | 17.1 | 2.353 | 2.157 | 83.51 |
| 30u | 1 | 12,318.8 | 2.041 | 4.197 | 17.3 | 2.628 | 0.617 | 88.07 |

## Hand calc 1 — PWM ripple and torque ripple

Two phases carry the current, so the peak-to-peak phase-current ripple is

    dI = Vbus·D·(1−D) / (2·Lph·Fsw) = 15.2·0.5·0.5 / (2·Lph·48e3)

Predicted torque ripple = `Ke·dI + 16e-3` N·m; the 16 mN·m term is the commutation dip.

Error here is (predicted − simulated) / simulated.

| Lph | Sync | dI (A p-p) | Predicted te_ripple (mN·m) | Simulated te_ripple (mN·m) | Error |
|---:|---:|---:|---:|---:|---:|
| 3.75u | 0 | 10.556 | 59.8 | 56.3 | +6.2 % |
| 3.75u | 1 | 10.556 | 59.8 | 71.7 | −16.6 % |
| 7.5u | 0 | 5.278 | 37.9 | 37.2 | +1.9 % |
| 7.5u | 1 | 5.278 | 37.9 | 43.1 | −12.0 % |
| 15u | 0 | 2.639 | 27.0 | 26.9 | +0.2 % |
| 15u | 1 | 2.639 | 27.0 | 26.8 | +0.6 % |
| 30u | 0 | 1.319 | 21.5 | 17.1 | +25.7 % |
| 30u | 1 | 1.319 | 21.5 | 17.3 | +24.1 % |

For `Lph ≤ 15u` the prediction is within ±17 %. At `Lph = 30u` both cases are more than 20 % high
(+25.7 % and +24.1 %). That is a >20 % disagreement: why the simulated ripple falls below
`Ke·dI + 16 mN·m` at 30u is **not explained**.

## Hand calc 2 — ripple copper loss

A triangular ripple adds `dI²/12` to the mean-square phase current. With two phases conducting,

    Pcu,ripple = 2·Rph·dI²/12

For Sync=1, the hand calc gives 0.928 W at `Lph = 3.75u` and 0.0145 W at `Lph = 30u`, a predicted
change of **−0.914 W**. The simulated `pcu` changes from 6.059 W to 2.628 W, a change of
**−3.432 W**. The ripple term alone accounts for only 26.6 % of the simulated drop.

**Review note: most of the rest comes from the operating point.** The comparison above (set by the task prompt) holds
the DC current fixed, but it is not fixed: a larger Lph slows the motor (hand calc 3), so the propeller needs less
torque and the conducting current falls from I = 6.829 A to 4.081 A. The DC part of the copper loss, 2·Rph·I², then
drops by 0.1·(6.829² − 4.081²) = **3.00 W**. Adding the ripple term:

    ΔPcu ≈ 3.00 W (DC) + 0.91 W (ripple) = 3.91 W   vs   3.43 W simulated   (+14 %)

So most of the copper-loss saving at large Lph comes from the motor running slower, not from smaller ripple.

The simple model gets the *change* right, but not the absolute levels. (`pcu` itself is exactly 3·Rph·iph_rms²:
6.030 W and 2.642 W from `iph_rms`, matching 6.059 W and 2.628 W.) The two-phase hand calc 2·Rph·I² + 2·Rph·dI²/12
gives 5.59 W at 3.75u (8 % low) and 1.68 W at 30u (**36 % low**). Something that adds copper loss and grows with
Lph is missing from it. That part is **not explained**.

## Hand calc 3 — commutation voltage loss

Each commutation costs about `Lph·I` volt-seconds, and there are `6·Pp·(rpm/60)` commutations per second:

    V_comm = 6·Pp·(rpm/60)·Lph·I,    I = ibat_avg / D

| Lph (Sync=1) | rpm_final (RPM) | ibat_avg (A) | I (A) | V_comm (V) |
|---:|---:|---:|---:|---:|
| 3.75u | 14,675.7 | 3.415 | 6.829 | 0.263 |
| 7.5u | 14,177.9 | 3.026 | 6.051 | 0.450 |
| 15u | 13,407.4 | 2.568 | 5.137 | 0.723 |
| 30u | 12,318.8 | 2.041 | 4.081 | 1.056 |

`V_comm` rises monotonically, 0.263 V → 1.056 V (Δ = 0.793 V), while the speed falls monotonically,
14,675.7 → 12,318.8 RPM (Δ = 2,356.9 RPM). So the direction agrees.

**Review note on the size.** Dividing by Ke alone (`ΔV_comm / Ke` → 1,823 RPM) treats the motor as unloaded.
With the propeller, a lower speed also needs less current, so each volt moves the speed less. The loaded
small-signal slope (as in the topology 02 README's DCM section) is

    dV/dω = Ke + 2·Rph·(2·Kprop·ω + Bfric)/Ke ≈ 4.97 mV per rad/s

and 0.793 V / 4.97 mV per rad/s = 160 rad/s = **1,524 RPM**. The simulated drop is **2,357 RPM**, so V_comm explains
about 65 % of it (the hand calc is 35 % low). The rest is **not explained**. (A full nonlinear solve of
the same balance gives 1,520 RPM, so the linear slope is not the problem. One possibility, not checked: V_comm uses
I = ibat_avg/D and one Lph·I volt-second loss per commutation, which may undercount the commutation interval at large
Lph. The 36 % shortfall in the hand calc 2 copper-loss level at 30u points the same way.)

## Discontinuous conduction (Sync=0)

The current touches zero when `dI/2 ≥ I`, with `I = ibat_avg / D`.

| Lph (Sync=0) | dI/2 (A) | I (A) | Margin I − dI/2 (A) | Status | rpm_final (RPM) |
|---:|---:|---:|---:|---|---:|
| 3.75u | 5.278 | 6.757 | 1.479 | continuous | 14,376.2 |
| 7.5u | 2.639 | 5.869 | 3.230 | continuous | 13,706.3 |
| 15u | 1.319 | 4.913 | 3.594 | continuous | 12,970.9 |
| 30u | 0.660 | 3.948 | 3.288 | continuous | 11,936.1 |

No Sync=0 case is at or past the boundary; all remain continuous, with the smallest margin (1.48 A) at
`Lph = 3.75u`. The 3.75u case does have the highest rpm (14,376.2), but since `dI/2 = 5.28 A` is still
below `I = 6.76 A`, its rpm is not unexpectedly high because of discontinuous conduction.

## Which effect wins

Efficiency, Sync=1: 85.75 % (3.75u) → 87.49 % (7.5u) → 88.03 % (15u) → 88.07 % (30u). It rises with Lph and is flat
from 15u to 30u, so the best value in this sweep is **30u at 88.07 %**, with 15u within 0.04 points.
Sync=0 peaks at 15u (83.73 %) and is 0.22 points lower at 30u (83.51 %). That difference is small, and this sweep
does not show its cause.

Two different things change with Lph, and only one of them is a loss:
- **Copper loss falls**, mostly because the motor runs slower and draws less current (hand calc 2 review note),
  and partly because the ripple shrinks.
- **The commutation volt-seconds (V_comm) are mostly not dissipated.** When a phase turns off, its inductor's stored
  energy flows back to the supply through the diodes (only their small drop is lost). So V_comm mainly lowers the
  *speed* at a given duty rather than the efficiency. At 30u the motor gives
  16 % less speed (12,319 vs 14,676 RPM, Sync=1), so it needs more throttle for the same thrust.

So a larger Lph buys a little efficiency at a fixed duty, mainly by running the motor slower. A fair comparison of
efficiency would hold the **speed** constant (adjust Duty per Lph), which this sweep does not do.

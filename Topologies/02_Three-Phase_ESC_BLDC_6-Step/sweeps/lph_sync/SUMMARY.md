# Phase-inductance × Sync sweep — 02 Three-Phase ESC + BLDC

Parallel sweep of `ThreePhase_ESC_BLDC.asc`: `Lph = 3.75u, 7.5u, 15u, 30u` × `Sync = 0, 1`,
8 LTspice runs, 8 at a time, finished in 412 s. Full precision is in `results.csv`; the tables below
round those entries. Constants used for the hand calculations: `Vbus = 15.2 V`, `D = 0.5`,
`Fsw = 48 kHz`, `Rph = 0.05 Ω`, `Ke = 60/(2π·2300) = 4.1519e-3 V·s/rad`, `Pp = 7`.

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
**−3.432 W**. The hand calc accounts for only 26.6 % of the simulated drop; the remaining 73.4 % is a
>20 % disagreement. The hand calc is a ripple-only estimate while `pcu` is the total copper loss, but
the size of the extra simulated drop is **not explained**.

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
14,675.7 → 12,318.8 RPM (Δ = 2,356.9 RPM). So the direction agrees. For the size, `ΔV_comm / Ke`
predicts a 1,823 RPM drop; the simulated drop is 2,357 RPM. That is the same rough size, with the hand
calc about 23 % low (the observed drop is 29 % larger).

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

As `Lph` grows, less PWM ripple cuts the ripple copper loss, while more commutation loss adds a growing
`V_comm` and reduces speed and power. In Sync=1 the efficiency rises from 85.75 % at 3.75u to 88.03 % at
15u and then essentially plateaus at 88.07 % at 30u: over this range the ripple-loss reduction wins,
but the gain is exhausted by 15–30u. The best Sync=1 efficiency is **30u at 88.07 %**, barely ahead of
15u at 88.03 %. In Sync=0 the same trade peaks earlier, at 15u (83.73 %), and 30u is lower (83.51 %),
so in that mode the added commutation loss has already overtaken the ripple-loss saving at 30u.

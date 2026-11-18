# Design exploration log

A running series of quick design experiments on the 54x18 heavy-lift rotor, one per entry. Each one is a BEMT/momentum
study (no CFD), with a script in `src/explore/`, results in `results/explore/`, a hand check, and the next ideas.

**Rules for every entry:**
- Same polars, hot-day atmosphere and 10 nmi mission as Phase 2.
- Before trusting anything new, the script reproduces a known number (a regression check).
- Baseline: the Phase 2 tricopter, open fixed-pitch rotor, pack **7475 Wh**.
- Coaxial reference: the Phase 2 blade as a pair at h = 0.2 D (`CONFIG_STUDY.md`), pack **5969 Wh**, payload −0.8 kg with half-size motors.

## Queue

1. ~~Coaxial blade redesigned for half the thrust per rotor~~ (entry 01)
2. ~~Two-point (hover + cruise) refinement of the coaxial blade~~ (entry 02)
2b. ~~**Blade structure and mass model.**~~ (entry 03) Entry 02's payload gain comes from blade mass ∝ volume. Add a fixed part (spar, root fitting, erosion strip) and the 50 N / 1.2 mm flex requirement as a constraint, then re-run entries 01–02.
3. ~~Different upper and lower blades: the lower rotor works in the upper wake inboard, so it wants more pitch there~~ (entry 04: no gain, keep one blade)
4. Upper/lower diameter split: a smaller lower rotor that sits inside the upper's contracted wake, or a larger one that reaches past it
5. Coaxial spacing in cruise: the wake-overlap fraction against h/D, against the hover mast and its mass
6. 3-blade coaxial: vibration (3P against 2P hub loads) and solidity per blade
7. Planar hexacopter against Y6: six isolated disks need a bigger frame, but they have no interference
8. Cruise speed per configuration: the coaxial pair's lower induced power moves the minimum-energy speed
9. Camber (64xx) for the coaxial blade: the blade trade study found camber pays mostly in cruise
10. Tip-speed limit: is 0.60 Mach still the right cap for the slower coaxial rotors (noise)?

## Entries

### 01 · 2026-11-18 · Coaxial blade designed for half thrust (`src/explore/e01_coax_blade.py`)

**Question.** The configuration study put the Phase 2 blade, designed for 415 N, into a coaxial pair where each rotor carries about 208 N. Does a blade designed for that half thrust do better?

**Method.** Run the Phase 2 hover design procedure for T_arm/2 = 208 N, isolated: minimum-induced-loss (MIL) blade at section cl 1.0, chord cap, root shank, re-twist. Do it at eight design RPMs, 1000–2112. Evaluate each design as a coaxial pair at h = 0.2 D: vortex-cylinder BEMT in hover with equal torque, and the wake-overlap estimate in cruise. Then compute the mission pack energy and the payload with half-size motors. Blade mass scales with blade volume from the 0.47 kg vendor blade.

**Regression check.** The Phase 2 blade as a pair gives 5969 Wh, exactly matching the configuration study. The first run gave 6316 Wh, which caught a bug: the climb power ratio had been multiplied by 3 twice.

| Design RPM | Solidity | Chord at 0.75 R [mm] | Hover stall margin [°] | T/W at Mach limit | Arm hover [W] | Cruise [W] | Pack [Wh] | Payload vs baseline [kg] |
|---|---|---|---|---|---|---|---|---|
| Phase 2 blade | 0.104 | 109 | 8.3 | 4.98 | 5500 | 9309 | **5969** | −0.8 |
| 1000 | 0.116 | 151 | 7.5 | 7.22 | 5815 | 9531 | 6155 | −2.3 |
| 1150 | 0.109 | 128 | 7.3 | 6.31 | 5651 | 9500 | 6099 | −1.6 |
| 1300 | 0.099 | 98 | 6.6 | 5.28 | 5550 | 9556 | 6102 | −0.9 |
| 1450 | 0.088 | 78 | 5.8 | 4.37 | 5503 | 9674 | 6148 | −0.2 |
| 1600 | 0.078 | 63 | 5.0 | 3.63 | 5490 | 9831 | 6222 | +0.3 |
| 1750 | 0.069 | 52 | 4.5 | 3.05 | 5498 | 10009 | 6311 | +0.7 |
| 1900 | 0.058 | 44 | 4.2 | 2.59 | 5532 | 10231 | 6428 | **+1.2** |
| 2112 | 0.047 | 35 | 3.7 (fails the 4° rule) | 2.09 | 5608 | 10557 | 6605 | +1.4 |

**Hand check: solidity scales with thrust.** Blade-element theory with uniform inflow gives CT/σ = cl_mean/6. At a fixed RPM and design cl, halving T should therefore halve σ. The code gives mean cl 0.998 at 1750 rpm, so the design cl holds. But the solidity ratio is 0.069/0.104 = **0.66, not 0.5**. The reason is the Phase 2 blade's inboard chord cap (0.22 R = 151 mm): the full-thrust blade is clipped there and the half-thrust blade is not, and the root shank and minimum tip chord are fixed sizes. Away from those limits the scaling holds: the chord at 0.75 R is 52 mm against 109 mm, a ratio of **0.48** against the hand value 0.5.

**Finding.**
- **On energy, the redesign loses.** The best design (1150 rpm, 6099 Wh) is 2.2 % worse than simply reusing the Phase 2 blade. This mission is 82 % cruise by energy, and the Phase 2 blade went through a two-point (hover + cruise) twist refinement; MIL designs are hover-optimal only. More hover efficiency can't pay for lost cruise efficiency here.
- **On payload, it wins a little.** Higher design RPM means a smaller, lighter blade. At 1900 rpm the blade set is 39 % of the Phase 2 blade's volume, and payload goes from −0.8 to **+1.2 kg** against the tricopter baseline, even with 8 % more pack energy than the Phase 2 blade pair. Caveat: blade mass ∝ volume is optimistic for small blades, because the spar, root fitting and erosion strip don't shrink with chord.
- The two criteria pull in opposite directions: energy wants big, slow blades, and payload wants small, fast ones.

**Next.** Entry 02: give the coaxial blade the same two-point (hover + cruise) refinement Phase 2 used, at the 1600–1900 rpm designs, to see whether a light blade can also cruise well.

### 02 · 2026-11-18 · Two-point refinement of the coaxial blade, objective payload (`src/explore/e02_coax_two_point.py`)

**Question.** Entry 01 found that energy wants big, slow blades and payload wants small, fast ones. Can reshaping the blade (twist and chord) get both?

**Method.** Nelder–Mead on four variables, 160 evaluations each, from four starting blades: the Phase 2 blade, and entry 01's MIL blades at 1450, 1750 and 1900 rpm.

    chord(x) = s · c(x) · (1 + e₁ (x − 0.75)),    twist(x) = θ(x) + d₀ + d₁ (x − 0.75),    x = r/R

- **Objective:** payload change against the tricopter, with half-size motors and blade mass ∝ volume.
- **Penalties:** hover stall margin under 4°; T/W under 2 at the tip-Mach RPM (on each rotor's own T/2); tip chord under the minimum.
- **Speed:** a full coaxial trim takes about 20 s. Inside the optimiser, the pair's hover power is replaced by 2 × (isolated rotor at T/2) × k, where k = P_pair / (2 P_iso) is computed once for the starting blade. The final designs are then re-run through the full coaxial model.

**Surrogate check.** k moved by at most 1.5 % over the optimisation (1.381 → 1.369 for the Phase 2 start). The pack energy from the surrogate and from the full model agree to 0.3 % at every end point.

| Start | Payload start → end [kg] | Pack start → end [Wh] | Solidity start → end | Blade volume end [cm³] | d₀ [°] | d₁ [°] | e₁ | s |
|---|---|---|---|---|---|---|---|---|
| Phase 2 blade | −0.76 → +2.31 | 5969 → 6237 | 0.104 → 0.060 | 295 | −2.3 | +3.3 | 1.07 | 0.80 |
| MIL 1450 rpm | −0.23 → **+2.40** | 6148 → 6314 | 0.088 → 0.053 | 235 | −2.6 | −6.1 | 1.11 | 0.88 |
| MIL 1750 rpm | +0.68 → +2.32 | 6311 → 6379 | 0.069 → 0.050 | 211 | −2.1 | −7.1 | 1.20 | 1.19 |
| MIL 1900 rpm | +1.15 → +2.35 | 6428 → 6375 | 0.058 → 0.050 | 207 | −0.8 | −5.8 | 1.21 | 1.40 |

**Hand check: hover RPM from blade-element theory.** With linear lift and uniform inflow, CT/σ = (a/6)(θ₇₅ − α₀ − 1.5√(CT/2)), with a = 5.73 /rad and α₀ = −4° (NACA 44xx). Solve for CT at T/2. Since CT = T / (ρA(ΩR)²), the RPM ratio is √(CT_old / CT_new).
- **With plain solidity** (blade area / disk area), the predicted RPM rise is 15–19 % too high in all four runs.
- **The reason:** every optimiser pushed chord outboard (e₁ ≈ 1.1–1.2, so the chord at 0.25 R falls to ~0.45 of its start while the tip grows). Plain solidity counts inboard area that makes little thrust.
- **The right measure** is the thrust-weighted solidity σₑ = 3∫σ(x) x² dx, because thrust grows as x². With σₑ the hand ratios are 1.250 / 1.226 / 1.085 / 0.953, against BEMT 1.233 / 1.190 / 1.064 / 0.950: within 0.3–3 %. (`src/explore/e02_hand_check.py`.)

**Finding.**
- All four starts end on the same plateau: payload about **+2.3 to +2.4 kg**, solidity about 0.05, blade volume 210–295 cm³. That's three kilograms better than reusing the Phase 2 blade in the pair, and 2.4 kg better than the tricopter baseline.
- **The gain is all blade mass, and energy gets worse.** The pack grows 4–6 % against the Phase 2 blade pair (6237–6379 Wh against 5969). Payload still improves because twelve blades lose about 75 % of their volume: 4.3 kg at 0.47 kg per Phase 2 blade.
- **So this result is only as good as "blade mass ∝ volume".** The optimiser found the weak spot in the model: it stripped the thick inboard chord, where volume (∝ chord² × t/c) is cheapest to cut. A real blade keeps a spar and root fitting, and must still pass the 50 N / 1.2 mm flex test. **Don't adopt this blade until the mass model has a structural floor (queue item 2b).**
- Useful anyway: the twist moves are consistent across starts (offset about −2°, more washout), and the hand check now teaches the thrust-weighted solidity.

**Next.** Queue item 2b: a blade mass model with a fixed spar and root fitting plus a flex-stiffness constraint, then re-run entries 01–02 under it.

### 03 · 2026-11-18 · Blade mass from a sized spar; entries 01–02 re-scored and re-optimised (`src/explore/blade_structure.py`, `src/explore/e03_structural_mass.py`)

**Question.** Entry 02's payload gain came from "blade mass ∝ volume". What does a blade actually weigh once it has to pass the 50 N / 1.2 mm tip-deflection test?

**Structure model.**
- **Section:** two UD-carbon spar caps (E = 130 GPa), a 0.6 mm ±45° skin, a 60 kg/m³ foam core, and an 80 g root fitting.
- **Root:** inboard of 0.18 R a metal root insert carries the load (Phase 3 thickens the root to 30 % t/c there).
- **Minimum-mass sizing by Lagrange multiplier.** In segment i, the caps' mass m_i gives EI_i = E h_i² m_i / (4ρ Δs). The unit-load method gives the tip deflection:

      δ = Σ F (L − s_i)² Δs / EI_i = Σ a_i / m_i,     a_i = 4ρF (L − s_i)² Δs² / (E h_i²)

  Minimising Σm_i with Σa_i/m_i = δ: ∂/∂m_i [m_i + λ a_i/m_i] = 0 gives m_i ∝ √a_i, so **m_total = (Σ√a_i)² / δ**. Material goes where (L − s)/h is large: near the root and in deep sections.
- **Limits per section:** a minimum gauge of two plies; caps widen up to 0.6 c before they thicken past t/3. (A cap thicker than t/3 loses more lever arm than it adds area: E·b·t_cap(t − t_cap)²/2 peaks at t_cap = t/3.)

**Hand checks.**
- **Closed form.** A deep uniform test section (100 × 40 mm): the code gives 0.0540 kg of caps, and the closed form (Σ√a_i)²/δ gives 0.0540 kg.
- **Optimum versus uniform beam.** A uniform-EI beam needs cap mass ∝ L·L³/3; the optimum needs ∝ (L²/2)². The ratio is 3/4, and the code gives 0.750.
- **Calibration.** The Phase 2 blade sizes to exactly 1.20 mm at **0.505 kg** (caps 0.242, skin 0.130, core 0.053, fitting 0.080). The vendor-scaled value is 0.47 kg, so the model is 7 % heavier.
- **Why the optimum went wide.** The chord scale is about 1.5, so t ∝ c rises 1.5× and h² about 2.25×. Cap mass should fall to about 0.242 / 2.25 = 0.107 kg; the code gives 0.085 kg (the chord taper also moves depth outboard).

**Re-scoring entries 01–02** (pack energies unchanged, only the blade mass is new):

| Design | Blade kg (∝ volume) | Blade kg (sized spar) | Deflection at that mass [mm] | Meets 1.2 mm | Payload (volume model) [kg] | Payload (spar) [kg] |
|---|---|---|---|---|---|---|
| Phase 2 blade (tricopter and pair) | 0.470 | 0.505 | 1.20 | yes | -0.76 | -1.18 |
| e01 MIL 1000 rpm | 0.544 | 0.437 | 1.20 | yes | -2.26 | -0.98 |
| e01 MIL 1150 rpm | 0.504 | 0.457 | 1.20 | yes | -1.59 | -1.04 |
| e01 MIL 1300 rpm | 0.443 | 0.566 | 1.20 | yes | -0.88 | -2.35 |
| e01 MIL 1450 rpm | 0.376 | 0.846 | 1.76 | **no** | -0.23 | -5.86 |
| e01 MIL 1600 rpm | 0.313 | 0.703 | 3.82 | **no** | +0.29 | -4.39 |
| e01 MIL 1750 rpm | 0.256 | 0.575 | 7.85 | **no** | +0.68 | -3.15 |
| e01 MIL 1900 rpm | 0.185 | 0.445 | 15.36 | **no** | +1.15 | -1.98 |
| e01 MIL 2112 rpm | 0.118 | 0.325 | 36.31 | **no** | +1.36 | -1.12 |
| e02 optimum from Phase 2 blade | 0.141 | 0.436 | 8.80 | **no** | +2.31 | -1.24 |
| e02 optimum from MIL 1450 rpm | 0.112 | 0.368 | 9.33 | **no** | +2.40 | -0.67 |
| e02 optimum from MIL 1750 rpm | 0.101 | 0.339 | 9.58 | **no** | +2.32 | -0.54 |
| e02 optimum from MIL 1900 rpm | 0.099 | 0.335 | 9.93 | **no** | +2.35 | -0.48 |

Every blade lighter than about 0.45 kg under the volume model fails the flex test: entry 02's optimum blades deflect 9–10 mm, and entry 01's 2112 rpm blade 36 mm. The payload ranking reverses.

**Re-optimised with the spar model** (same four variables and penalties as entry 02, plus a penalty on deflection over 1.2 mm):

| Start | Payload start → end [kg] | Pack [Wh] | Solidity | Blade [kg] | Caps [kg] | Hover RPM (isolated) | T/W at Mach limit |
|---|---|---|---|---|---|---|---|
| Phase 2 blade | -1.18 → **+0.24** | 5969 → 5779 | 0.104 → 0.140 | 0.505 → 0.438 | 0.085 | 1269 | 5.8 |
| MIL 1150 rpm | -1.04 → **+0.26** | 6099 → 5778 | 0.109 → 0.141 | 0.457 → 0.438 | 0.085 | 1269 | 5.8 |
| MIL 1450 rpm | -5.86 → **+0.22** | 6148 → 5783 | 0.088 → 0.139 | 0.846 → 0.440 | 0.085 | 1271 | 5.8 |
| MIL 1750 rpm | -3.15 → **+0.19** | 6311 → 5795 | 0.069 → 0.139 | 0.575 → 0.439 | 0.086 | 1269 | 5.8 |

**Finding.**
- **All four starts converge on the same blade.** Solidity is about 0.14, mass 0.44 kg (only 0.085 kg of it spar), and it hovers slowly at about 1270 rpm. That's the opposite of entry 02's thin blades. A deep, wide section is the cheapest way to be stiff, and a big, slow blade also cruises better.
- **Pack 5780 Wh:** 3.2 % better than the Phase 2 blade in the pair (5969 Wh), and 22.7 % below the tricopter (7475 Wh).
- **Payload +0.2 kg** against the tricopter with half-size motors: payload-neutral, as before. The coaxial arm's case is still range (about 29 % more on the same pack), yaw balance and redundancy, not payload.
- **Lesson for the whole project:** an optimiser finds the weakest assumption in its objective. Entry 02's "gain" was a mass model without a stiffness floor. With one, the design direction flipped.
- **Caveats:** T/W at the tip-Mach limit is 5.8, so this blade has far more thrust margin than needed. The motor is now the limit, not the blade, and the half-size-motor mass assumption decides the payload. Fatigue, the centrifugal load path and the flapping (in-flight) deflection are not modelled.

**Next.** Queue item 3: different upper and lower blades, sized with this spar model.

### 04 · 2026-11-18 · Different upper and lower blades (`src/explore/e04_upper_lower_blades.py`, `e04_hand_check.py`)

**Question.** Inboard of the upper wake edge (r_w = 0.85 R at h = 0.2 D), the lower rotor sees the upper rotor's wake, w ≈ 9.7 m/s. Does a lower blade with more pitch there save energy?

**Method.**
- **Upper blade:** entry 03's winner (σ 0.14, 0.44 kg).
- **Lower blade:** the same planform, re-twisted as Δθ(x) = d0 + d_in·g(x), where g = 1 inboard of 0.75 R and blends to 0 at 0.90 R with a cosine. Twist does not change the spar-sized mass, so payload follows pack energy.
- **Grid:** d0 ∈ {−2, −1, 0, +1, +2}°, d_in ∈ {0, 1.5, 3, 4.5}°. 20 cases.
- **Model:** the full coaxial model with two different blades: vortex-cylinder interference, both RPMs trimmed for equal torque and total thrust; cruise at T/6 per rotor plus the wake-overlap term; the 10 nmi mission.
- **Regression check:** identical blades give **5778 Wh**, entry 03's number exactly.

| d0 [°] | d_in [°] | Pack [Wh] | vs identical | Upper thrust share | Lower stall margin [°] |
|---|---|---|---|---|---|
| +1 | 0 | 5777 | −0.01 % | 0.543 | 10.7 |
| 0 | 0 | **5778** | 0 | 0.530 | 11.2 |
| 0 | 1.5 | 5785 | +0.12 % | 0.544 | 11.3 |
| −1 | 1.5 | 5786 | +0.14 % | 0.533 | 11.7 |
| +2 | 0 | 5786 | +0.15 % | 0.554 | 10.2 |
| +2 | 4.5 | 5930 | **+2.6 %** | | 10.4 |

All 20 cases converged. The spread is 153 Wh, and every change from identical blades costs energy or is a wash.

**Why: the RPM trim already does the job that the extra twist was meant to do.**

The naive argument is "more inflow → larger inflow angle φ → lower α → add twist to compensate." At fixed Ω, the hand estimate at 0.5 R is

  Δφ = atan((w + v_l)/(Ωr)) − atan(v_iso/(Ωr)) = atan(14.0/53.3) − atan(7.96/53.3) = **6.2°**

That would call for about 6° of extra inboard twist. But a fixed-pitch rotor is not run at fixed Ω. The equal-torque trim lets each rotor find its own speed. The velocity triangles at 0.5 R with the trimmed speeds (`e04_hand_check.py`; mean inflows from the vortex-cylinder model, k = h/√(R² + h²) = 0.371):

| | Inflow [m/s] | RPM | Ωr [m/s] | φ [°] |
|---|---|---|---|---|
| Upper | v_u + (1 − k)·v_l = 7.09 + 2.68 = 9.77 | 1423 | 49.3 | **11.2** |
| Lower | v_l + w = 4.26 + 9.73 = 13.99 | 1540 | 53.3 | **14.7** |
| Lower at the upper's RPM | 13.99 | 1423 | 49.3 | 15.9 |

- **Same twist on both blades**, so α_lower − α_upper = −(φ_l − φ_u) = **−3.5°** (hand) against **−2.2°** from BEMT. The hand number uses the mean inflow; BEMT uses each blade's local induced velocity at 0.5 R. That is a fair match.
- **The lower rotor takes less of its inflow from itself.** v_l is 4.3 m/s against 8.0 for an isolated rotor at the same thrust, because the upper wake already carries momentum. Its α is lower, but that is the right operating point: it makes 47 % of the thrust while running 8 % faster.
- **Twist and pitch here only shift load between the rotors.** That moves the thrust share from 0.53 to 0.55 at most. Two things hold the power nearly constant:
  1. Induced power is fixed by the interference (κ_int, momentum theory), not by the blade.
  2. The profile power sits on the flat bottom of the drag bucket.
- **Large inboard twist makes it worse.** Inboard of 0.75 R, the lower blade is pushed toward the upper wake edge, and the loading becomes less uniform: more induced loss.

**Finding.** Keep one blade for both rotors. That is also the better production outcome: one mould, one balance spec, spares that fit either position. The ±1° pitch offset is a wash (−0.01 %). It is not worth a second part number, but a set-screw pitch adjustment at the hub could trim the torque split for yaw if needed.

**Next.** Queue item 4: diameter split. Twist cannot change the wake-edge effect, but radius can. A lower rotor whose tip sits at r_w would avoid the "half in the wake, half clean" loading mismatch. A larger lower rotor would reach clean air. The spar model sets each blade's mass.

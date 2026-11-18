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
4. ~~Upper/lower diameter split: a smaller lower rotor that sits inside the upper's contracted wake, or a larger one that reaches past it~~ (entry 05: keep 54/54 in)
5. ~~Coaxial spacing in cruise: the wake-overlap fraction against h/D, against the hover mast and its mass~~ (entry 06: h/D 0.4 if the overlap model holds)
6. 3-blade coaxial: vibration (3P against 2P hub loads) and solidity per blade
7. ~~Planar hexacopter against Y6: six isolated disks need a bigger frame, but they have no interference~~ (entry 09: hex best on energy, all three tie on payload)
8. Cruise speed per configuration: the coaxial pair's lower induced power moves the minimum-energy speed
9. Camber (64xx) for the coaxial blade: the blade trade study found camber pays mostly in cruise
10. Tip-speed limit: is 0.60 Mach still the right cap for the slower coaxial rotors (noise)?
11. ~~Check the cruise wake-overlap model with a prescribed-wake (Biot–Savart) calculation~~ (entry 07: the lens model was optimistic; use the vortex-wake / biplane σ from now on)
12. Mast structure at h/D 0.4–0.5: bending under motor-out and gust loads, first bending mode against 1P/2P, gyroscopic moments
13. Re-state the coaxial case (CONFIG_STUDY headline, entries 01–06 payloads) with the vortex-wake cruise term: at h/D 0.2 the coax is −12 % energy and −2.4 kg payload, not −22 % and +0.1 kg
14. ~~Stagger: offset the lower rotor forward along the flight path (tilted mast)~~ (entry 08: modest gain; large stagger turns into the planar layout, item 7)
15. ~~Faired (aerofoil) arms and masts~~ (entry 14: worth only +0.07 kg on the hex and +0.16 kg on the y6 once fairing mass and hover download count; −4.6 % energy on the hex)
16. ~~Motor and fitting mass: find real catalogue numbers~~ (entry 10: motors sized by torque; hex ties the tri, y6 −3.3 kg)
17. ~~Re-optimise the blade with motor mass ∝ peak torque in the objective~~ (entry 11: hex blade 1780 rpm, payload +2.3 kg vs tri)
18. ~~U15XL torque margin~~ (entry 13: the tri blade re-optimised with the motor gains +1.9 kg and fits the U15XL at T/W 1.99; the hex's lead falls to +0.4 kg)
19. ~~Y6 blade with the motor in the objective~~ (entry 12: y6 −0.4 kg vs tri; the hex leads by 2.7 kg and 19 % energy)
20. Tip-Mach sensitivity of the tri: its optimum sits on the 0.60 cap, so d(payload)/d(M_cap) prices the noise limit (pairs with item 10)
22. Lighter fairing construction (skin < 0.39 kg/m² is the break-even) and thicker sections (t/c 0.5 won at the edge of the sweep)
21. Re-run entry 09's layout ranking with all three re-optimised blades and real motors (uncertainty band from the ±0.9 kg motor fit)

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

### 05 · 2026-11-18 · Upper/lower diameter split (`src/explore/e05_diameter_split.py`, `e05_hand_check.py`)

**Question.** Entry 04 showed that twist can't change how the lower rotor sits in the upper wake, but radius can. Two ideas:
- A smaller lower rotor with its tip at the wake edge (r_w ≈ 0.85 R_u) would be fully inside the wake, with no "half in, half clean" mismatch.
- A larger lower rotor would reach clean air past the wake.

**Method.**
- **Blades:** entry 03's blade for both rotors (entry 04: one blade is enough), scaled geometrically about the hub to the new radius. Chord scales with radius, so solidity and the twist against r/R stay the same.
- **Mass:** each blade's mass comes from the spar model, sized for 50 N / 1.2 mm.
- **Coaxial model:** generalised to two radii:
  - on the upper disk (r < R_l), the lower rotor adds (1 − k_l)·v_l, with k_l = h/√(R_l² + h²);
  - on the lower disk (r < r_w = R_u√(v_u/w)), the upper wake adds w = (1 + k_u)·v_u.
  Equal-torque trim. The mast height stays h = 0.2 × 54 in.
- **Two families:**
  - **(a) Lower rotor resized**, the upper stays 54 in: s = R_l/R_u from 0.80 to 1.15. For s > 1 the footprint grows; the bigger frame is not counted.
  - **(b) Fixed 54 in footprint:** the lower stays 54 in and the upper shrinks to 54/s in.
- **Regression check:** s = 1 gives **5778 Wh**, matching entries 03 and 04.

| Family | D_upper / D_lower [in] | Lower in wake (r_w/R_l) | RPM upper/lower | Pack [Wh] | vs 54/54 | Payload [kg] |
|---|---|---|---|---|---|---|
| (a) | 54 / 43.2 | 1.07 (fully inside) | 1343 / 2444 | 6039 | +4.5 % | +0.24 |
| (a) | 54 / 45.9 | 1.00 (tip at the wake edge) | 1366 / 2181 | 5907 | +2.2 % | +0.49 |
| (a) | 54 / 48.6 | 0.95 | 1390 / 1940 | 5820 | +0.7 % | +0.58 |
| (a) | 54 / 51.3 | 0.90 | 1408 / 1717 | 5767 | −0.2 % | +0.52 |
| ref | **54 / 54** | 0.85 | 1423 / 1540 | **5778** | 0 | +0.26 |
| (a) | 54 / 56.7 | 0.81 | 1429 / 1376 | 5639 | −2.4 % | +0.47 |
| (a) | 54 / 59.4 | 0.78 | 1437 / 1246 | 5530 | −4.3 % | +0.55 |
| (a) | 54 / 62.1 | 0.74 | 1443 / 1130 | 5430 | −6.0 % | +0.61 |
| (b) | 51.4 / 54 | 0.81 | 1571 / 1520 | 5809 | +0.5 % | +0.37 |
| (b) | 49.1 / 54 | 0.77 | 1728 / 1513 | 5871 | +1.6 % | +0.37 |
| (b) | 47.0 / 54 | 0.73 | 1885 / 1479 | 5918 | +2.4 % | +0.37 |

**Hand check: three estimates of the arm's induced power, as ratios to 54/54.**

1. **Disk area only.** Each rotor carries T/2 with ideal power (T/2)^1.5/√(2ρA). Since √A ∝ D, the ratio is

   P/P₀ = (D₀/D_u + D₀/D_l)/2.

   At 54/62.1 that is (1 + 0.870)/2 = **0.935**.
2. **Momentum with interference** (`hand()` in the script). It uses the BEMT thrust split, w and r_w, and one uniform "own" inflow v_l over the lower disk. The core inside r_w moves at w + v_l and carries T = 2ρA(w + v_l)v_l; the clean annulus carries 2ρA·v_l². The lower rotor's power is the sum of dT × (axial velocity through the disk).
3. **BEMT induced power** Σ dT·(v + v_i), from the full model.

| D_u / D_l | Area only | Momentum | BEMT induced |
|---|---|---|---|
| 54 / 43.2 | 1.125 | 1.054 | 1.142 |
| 54 / 45.9 | 1.088 | 1.034 | 1.112 |
| 54 / 62.1 | 0.935 | 0.957 | 0.897 |
| 47.0 / 54 | 1.075 | 1.102 | **1.014** |

At 54/54 the momentum estimate is 5252 W per arm against 5050 W from BEMT, 4 % apart. The trends tell the story:

- **Family (a) follows the disk-area estimate.** BEMT is a little steeper. There is no kink at r_w/R_l = 1, so the "tuck the lower rotor into the wake" idea finds no sweet spot. A smaller lower rotor simply has a higher disk loading (T/A), and induced power goes as √(T/A). It also has to spin 1.4–1.6× faster to make its share of the thrust.
- **The larger lower rotor helps only by adding disk area.** It does that by growing the footprint: frame spacing is 1.10 D, so arms get about 15 % longer at 62 in. That gives the same gain as making both rotors bigger, which was the Phase 1 diameter trade, not a coaxial effect.
- **Family (b) holds the one real interference effect.** At a fixed footprint, shrinking the upper to 47 in costs only +1.4 % induced power, where disk area alone predicts +7.5 %. A smaller upper rotor's contracted wake covers only the middle 73 % of the lower radius. The clean annulus outside it can then carry thrust at low inflow, which BEMT captures: dT/dr peaks outboard of r_w in the plot.
- **The momentum hand check misses that effect.** It forces one uniform v_l over the whole lower disk, so the in-wake core keeps carrying its share at high velocity, and it overestimates the penalty (1.102). That is a modelling lesson: a uniform-inflow momentum model cannot represent a rotor that redistributes its load radially.
- **Even so, (b) is a net loss:** +0.5 to +2.4 % pack energy. The smaller upper rotor runs faster (up to 1885 rpm), so its profile and cruise power rise.

**Finding.**
- **Keep equal 54 in diameters.** Inside the footprint, a smaller upper or a smaller lower rotor costs energy. A larger lower rotor saves energy only by enlarging the footprint, which is the same trade as just using bigger rotors.
- **Payload moves within ±0.35 kg in every case,** below the model's accuracy. Blade mass falls with diameter because the 1.2 mm bench limit is held fixed (which is conservative for short blades), and that roughly offsets the energy change.
- **Caveat:** the cruise overlap term uses the smaller disk's area, which flatters the small-lower-rotor cases slightly. The 54/51.3 case's −0.2 % is cruise only, and is within that uncertainty.

**Next.** Queue item 5: coaxial spacing in cruise. The wake-overlap fraction against h/D, weighed against the hover interference (κ_int falls with spacing) and the mast's mass and drag.

### 06 · 2026-11-18 · Coaxial spacing: hover, cruise and the mast (`src/explore/e06_coax_spacing.py`, `e06_hand_check.py`)

**Question.** Every entry so far used h/D = 0.2 (a 27 cm mast). Spacing affects three things:
- **Hover interference:** the upper wake contracts and speeds up before it reaches the lower rotor.
- **Cruise wake overlap:** the upper wake is swept back, and with enough height it misses the lower disk.
- **The mast:** its mass and drag grow with height.

Where is the best spacing?

**Method.**
- **Rotors:** entry 03's blade on both, 54 in. Sweep h/D = 0.10–0.75.
- **Hover:** the full coaxial model (e05 `coax_split`).
- **Cruise:** each rotor at T/6, plus the overlap penalty 3·f·(P_ind,one disk − 2·P_ind). The overlap fraction f is the lens area of two circles of radius R whose centres sit d = h·tan χ apart, where χ = atan(μ/λ) is the wake skew angle.
- **Mast assumptions:**
  - 40 mm × 2 mm carbon tube plus 30 % for fittings: 0.51 kg/m per arm, counted relative to h/D 0.2.
  - Cylinder drag: Cd 1.2 (Re ≈ 4·10⁴).
  - That drag is paid through the rotors at a propulsive efficiency of 0.8.
- **Regression check:** at h/D 0.2, cruise without the mast is 8865 W and hover 16812 W, both identical to entries 03–05. The pack reads 5823 Wh instead of 5778 because the mast drag (92 W) is now counted.

| h/D | Mast [cm] | Hover [W] | κ_int (BEMT) | Overlap f | Overlap penalty [W] | Mast drag [W] | Cruise [W] | Pack [Wh] | vs 0.2 | Payload [kg] |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.10 | 14 | 17003 | 1.413 | 0.685 | 3298 | 46 | 10325 | 6507 | +11.7 % | −1.94 |
| 0.15 | 21 | 16930 | 1.406 | 0.534 | 2571 | 69 | 9622 | 6157 | +5.7 % | −0.89 |
| **0.20** | 27 | 16812 | 1.394 | 0.391 | 1883 | 92 | 8957 | **5823** | 0 | +0.11 |
| 0.25 | 34 | 16635 | 1.379 | 0.260 | 1251 | 116 | 8348 | 5511 | −5.4 % | +1.03 |
| 0.30 | 41 | 16397 | 1.358 | 0.145 | 696 | 139 | 7816 | 5232 | −10.2 % | +1.85 |
| **0.40** | 55 | 16121 | 1.332 | 0.000 | 0 | 185 | 7166 | **4892** | **−16.0 %** | **+2.76** |
| 0.50 | 69 | 16156 | 1.331 | 0 | 0 | 231 | 7212 | 4917 | −15.6 % | +2.46 |
| 0.75 | 103 | 15774 | 1.294 | 0 | 0 | 347 | 7328 | 4943 | −15.1 % | +1.86 |

**Hand check 1: the cruise overlap.** At 15 m/s the rotor's advance ratio is μ = 0.193 and its inflow ratio λ = 0.077, so

  tan χ = μ/λ = 2.50 and χ = 68.2°.

At h = 0.2 D = 0.4 R, the wake centre is displaced d = 0.4 R × 2.50 = **1.00 R** at the lower disk. Two unit circles one radius apart overlap by (2π/3 − √3/2)/π = **0.391**, exactly the f in the table. The overlap disappears when d = 2R, at h/D = 2R/(2R·tan χ) = 1/2.5 = **0.40**. That matches the sweep: f = 0 from 0.40 on. The cruise penalty is the biggest term in this study (1.9 kW of vehicle power at h/D 0.2), and it is linear in f.

**Hand check 2: hover interference from a two-region momentum model** (`e06_hand_check.py`).

The first attempt reused e05's `hand()`. It gave κ ≈ 1.59 at every spacing, and its h → 0 limit came out at 1.62 instead of √2. That revealed a bug in e05's hand check: it computed the upper rotor's own induced velocity from still-air momentum (T_u = 2ρA·v_u²). But the lower rotor also pulls flow through the upper disk, so the upper rotor's mass flow is larger. The corrected equations, with k = h/√(R² + h²):

- **Upper:** T_u = 2ρA·v_u·(v_u + (1−k)·v̄_l) and P_u = T_u·(v_u + (1−k)·v̄_l).
- **Upper wake at the lower disk:** speed w = (1+k)·v_u over the core area A_w = A/(1+k). Continuity: A_w·w = A·v_u.
- **Lower:** core (own velocity v_c) plus clean annulus (own v_a):
  - T_l = 2ρ[A_w(w+v_c)·v_c + (A−A_w)·v_a²]
  - P_l = 2ρ[A_w(w+v_c)²·v_c + (A−A_w)·v_a³]
  - v̄_l = (A_w·v_c + (A−A_w)·v_a)/A.
- **Two closures for the lower rotor:**
  - **uniform:** v_c = v_a, a blade that ignores the wake;
  - **optimal:** the same marginal cost dP/dT in both regions, so no thrust can be moved between them to save power:
    (w+v_c)(w+3v_c)/(w+2v_c) = 1.5·v_a.

| | h → 0 | h/D 0.2 | h/D 0.4 | h/D 0.75 | far wake |
|---|---|---|---|---|---|
| Uniform lower loading | **1.414 = √2** ✓ | 1.443 | 1.493 | 1.552 | 1.618 |
| Optimal lower loading | **1.414 = √2** ✓ | 1.344 | 1.291 | 1.238 | 1.206 |
| BEMT (real fixed-pitch blade) | | 1.394 | 1.332 | 1.294 | |

- **Uniform limit.** At h → 0 both rotors are one disk with the total thrust, so κ = 2^1.5/2 = √2 exactly. Both closures reproduce it.
- **Far-wake limit with uniform loading:** the equations reduce to v_l² + v_u·v_l − v_u² = 0, so v_l = 0.618·v_u and κ = 1.618 (the golden ratio, an amusing coincidence).
- **Optimal loading lets the lower rotor do better with height.** It moves its thrust into the clean annulus: v_c/v_a falls from 0.44 at h/D 0.1 to 0.08 at 0.75. The core, which already moves fast, gets almost no extra push.
- **BEMT sits between the two closures, 3–5 % above the optimum, at every spacing.** A fixed-twist blade cannot reach the optimal loading, but its load does peak outboard of r_w (entries 04 and 05). That bracketing is the hand check of the BEMT κ trend.
- **The textbook far-wake value of 1.281 (Leishman) assumes a fully mixed lower wake;** it falls inside the same bracket.
- **This also corrects entry 05's hand check.** Its "momentum" column used the uncorrected upper momentum. Its trend conclusions stand, but its 4 % absolute agreement at 54/54 in was partly luck.

> **Superseded by entry 07:** the lens cruise model used here is optimistic. With a vortex wake the h/D 0.4 pack is 5715 Wh (not 4892) and the payload is +0.05 kg (not +2.8). The hover numbers and the hand checks in this entry stand.

**Finding.**
- **Spacing is the biggest lever found yet, and nearly all of it is cruise.** Going from h/D 0.2 to 0.4:
  - cruise wake overlap: −1.9 kW of vehicle power;
  - hover: −4 % (κ 1.394 → 1.332);
  - mast drag: +93 W;
  - mast mass: +0.42 kg in total.
  Pack −16 % (4892 Wh), payload +2.8 kg against the tricopter: the first clearly positive payload in this series.
- **Beyond 0.4 there is no overlap left to remove,** so mast drag and mass win, and the pack rises slowly.
- **The result rests on a crude cruise model.** It is a straight, rigid wake from the disk centre, with a penalty linear in the lens area. Real skewed wakes roll up into two tip vortices and deflect downward more aft. The configuration study bracketed the coaxial cruise between "one disk" and "no interference", and this result sits at the optimistic end. **Do not change the design on this yet:** queue item 11 checks the overlap with a prescribed-wake Biot–Savart calculation.
- **A 55 cm mast is a real structural item.** It carries a 25 kg-thrust rotor, motor-out loads and gyroscopic moments, and its bending mode must stay clear of 1P/2P. That is queue item 12.
- **Cruise speed matters:** at 12 m/s χ is smaller, so the same spacing leaves more overlap. Queue item 8 (cruise speed per configuration) should use the spacing from item 11.

**Next.** Queue item 11: a prescribed-wake model of the upper rotor in cruise. Free-stream plus a skewed helical vortex wake, Biot–Savart on the lower disk. It gives the lower rotor's actual inflow map, which replaces the lens-area estimate.

### 07 · 2026-11-18 · Cruise wake interference from a prescribed vortex wake (`src/explore/e07_cruise_wake.py`, `e07_hand_check.py`)

**Question.** Entry 06's 16 % gain at h/D 0.4 came from a lens model of the cruise wake. That model treats the upper wake as a rigid tube: the lower rotor feels it only where the tube crosses the lower disk, and feels the fully developed 2·v_i there. Is that right?

**Method: the skewed vortex cylinder.** This is the standard model of a uniformly loaded rotor in forward flight (Coleman, Castles–de Leeuw):
- **Geometry:** each rotor's wake is a stack of horizontal vortex rings of radius R, whose centres run down the skew axis e = (sin χ, 0, −cos χ), with tan χ = μ/λ = 2.50 (χ = 68.2°).
- **Strength:** set so the rotor's own normal induced velocity at its hub equals the BEMT cruise value v_i0.
- **Velocity field:** straight-segment Biot–Savart with a smooth core of 0.05 R, a wake length of 30 R and rings 0.05 R apart. The velocities are evaluated over the other rotor's disk on a 10 × 36 polar grid.
- **Interference power:** with uniform loading (dT = T·dA/A), each rotor's extra induced power is T × (area-mean normal velocity from the other rotor's wake):

  ΔP_arm = T_l·w̄_l + T_u·w̄_u

  This replaces the lens term. Both directions count. The lens model ignored the lower rotor's effect on the upper.

**Checks on the Biot–Savart code (hand formulas).**

1. **Hover (χ = 0), on the axis a distance z below the disk.** The semi-infinite cylinder gives w(z)/w(0) = 1 + z/√(R² + z²):

   | z/R | 0.1 | 0.2 | 0.4 | 1.0 | 2.0 |
   |---|---|---|---|---|---|
   | Biot–Savart | 1.0996 | 1.1964 | 1.3719 | 1.7077 | 1.8950 |
   | Hand | 1.0995 | 1.1961 | 1.3714 | 1.7071 | 1.8944 |

2. **Cruise, the rotor's own wake over its own disk.**
   - Coleman's linear inflow v = v₀(1 + K_x·(r/R)·cos ψ) has a hub slope K_x = tan(χ/2) = **0.677**. The fitted slope near the hub is **0.693** (2 % off).
   - The Pitt–Peters whole-disk value is (15π/32)·tan(χ/2) = 0.997. A whole-disk fit gives 1.092. The exact field steepens toward the trailing edge, which is why a hub slope and a whole-disk fit differ.

3. **Prandtl's biplane factor.** In cruise a rotor is a lifting surface of span b = 2R. Glauert's induced power is P_i = T²/(2ρA·V′), the same as an elliptic wing's (L²/(πqb²))·V. Two wings a gap G apart have

   P = (T_u² + 2σ·T_u·T_l + T_l²)/(2ρA·V′),  σ = (1 − 0.66·G/b)/(1.055 + 3.7·G/b)

   so the interference per arm is 2σ·P_i. The vortex wake's equivalent is σ = (w̄_l + w̄_u)/(2·v_i0). Here G/b = h/D:

   | G/b | 0.10 | 0.20 | 0.30 | **0.40** | **0.50** | **0.75** |
   |---|---|---|---|---|---|---|
   | σ, Prandtl | 0.655 | 0.484 | 0.370 | **0.290** | **0.231** | **0.132** |
   | σ, vortex wake | 0.791 | 0.594 | 0.419 | **0.292** | **0.232** | **0.142** |
   | lens-model equivalent (f) | 0.685 | 0.391 | 0.145 | 0 | 0 | 0 |

   From G/b 0.4 upward the vortex wake reproduces Prandtl's 1924 biplane result within 1–7 %. Below that the vortex wake is higher, as it should be: Prandtl's formula assumes flat wakes, while here the lower disk is still partly inside the upper rotor's wake column.

**Why the lens model was wrong.** A horizontal ring stacked along a skewed axis has a vorticity component along that axis at its two lateral edges (ψ = ±90°). So the skewed wake carries two counter-rotating trailing vortices, the start of the wing-like roll-up. A vortex pair induces downwash everywhere on its symmetry plane, above and below it, not only inside the wake tube. The lower disk keeps feeling it long after the tube has passed aft of it. At large gaps the field is that of a pair, which is symmetric in z, so the upper rotor sees the same mean downwash from the lower wake as the lower sees from the upper (0.292 and 0.291 at h/D 0.4). The polar map in the plot shows it: the aft half of the lower disk is inside the wake at h/D 0.2, but the forward half still sees about 0.2–0.5·v_i0.

**Corrected results** (hover and mast from entry 06; only the cruise interference term changes):

| h/D | Penalty, lens [W] | Penalty, vortex wake [W] | Cruise [W] | Pack [Wh] | vs tricopter (7475 Wh) | Payload vs tricopter [kg] |
|---|---|---|---|---|---|---|
| 0.10 | 3298 | 4556 | 11584 | 7121 | −4.7 % | −3.96 |
| 0.20 | 1883 | 3422 | 10496 | **6575** | **−12.0 %** | **−2.37** |
| 0.30 | 696 | 2415 | 9535 | 6071 | −18.8 % | −0.92 |
| 0.40 | 0 | 1685 | 8851 | **5715** | **−23.6 %** | **+0.05** |
| 0.50 | 0 | 1338 | 8551 | 5571 | −25.5 % | +0.31 |
| 0.75 | 0 | 817 | 8145 | 5342 | −28.5 % | +0.54 |

**Finding.**
- **The lens model was optimistic at every spacing above 0.15 D.** At the old design point (h/D 0.2) the coaxial arm's cruise interference is 3.4 kW, not 1.9. The coaxial vehicle needs 12 % less pack energy than the tricopter, not 22 %, and loses 2.4 kg of payload.
  - The configuration study's "payload-neutral" coax claim, and the payload numbers in entries 01–06 (all at h/D 0.2), carry this error. Queue item 13 re-states them.
  - Entries 01–05 compared blades at a fixed spacing, so their *rankings* stand. Only the absolute coax-versus-tricopter numbers move.
- **Spacing still matters, and more smoothly than entry 06 said.** No spacing makes the interference vanish; it decays like a biplane's, σ ≈ 1/(1 + 5.6·G/b).
  - h/D 0.4 (55 cm mast): −23.6 % energy against the tricopter, payload neutral (+0.05 kg).
  - h/D 0.5: one more step (−25.5 %, +0.3 kg).
  - Beyond that, the mast becomes a structural problem before the energy pays off. The mast has to come next (queue item 12).
- **What to keep from this:** a check that changes a headline by a factor of two is worth more than the next design idea. Prandtl's 1924 biplane factor, two lines of algebra, would have caught entry 06's error. Every later entry uses the vortex-wake / biplane term for cruise interference.
- **Remaining assumptions:**
  - The wake is rigid and straight: no roll-up, no further downward deflection by its own induction. Roll-up mostly moves vorticity to the edges, where the biplane far-field already puts it, so this mainly affects the small-gap end.
  - The loading is uniform. A real rotor's lift is biased to the advancing side, which skews the trailing vortices laterally; that is not modelled.

**Next.**
- **Queue item 14, stagger.** Mount the lower rotor forward of the upper along the flight path, on a mast tilted forward. Then the swept-back upper wake and its trailing pair pass farther behind the lower rotor. For biplanes, positive stagger lowers σ. The same vortex code can test it in one evening's run, so it goes before item 12.
- **Then item 12 (mast structure) and item 13 (re-state the coaxial case).**

### 08 · 2026-11-18 · Stagger: the lower rotor forward of the upper (`src/explore/e08_stagger.py`, `e08_hand_check.py`)

**Question.** Entry 07 showed the cruise interference decays like a biplane's. Biplanes gain from stagger, one wing set ahead of the other. Does it help to mount the lower rotor a distance s forward of the upper, on a mast tilted forward?

**Method.**
- **Geometry:** upper hub at the origin, lower hub at (−s, 0, −h) (x points aft). The mast has length L = √(h² + s²). Grid: h/D ∈ {0.2, 0.3, 0.4}, s/R ∈ {−0.5, 0, 0.25, 0.5, 0.75, 1.0, 1.5}.
- **Cruise:** entry 07's skewed vortex wakes, with the lower rotor's wake starting at its new hub.
- **Hover:** the wakes are vertical, so stagger moves part of the lower disk out of the upper wake. Entry 06's two-region momentum model (optimal lower loading), with geometric overlaps:
  - core area = intersection of the wake circle r_w = R/√(1+k) with the offset lower disk;
  - the upper rotor feels the lower's inflow over the two disks' overlap fraction φ.

  The ratio κ(s)/κ(0) scales the BEMT induced power from entry 06. At s = 0 the model gives κ = 1.344 (entry 06's value), and 1.00 once the disks no longer overlap (s ≥ 2R).
- **Mast:** 0.51 kg/m. Cross-flow drag: only the velocity component normal to the mast loads it, so D = q·C_d·d·L·sin²θ = q·C_d·d·h²/L.
- **Regression check:** s = 0 reproduces entry 07 exactly (6575 / 6071 / 5715 Wh).
- **Bug found during the run:** aft stagger (s < 0) passed a signed distance into the circle-intersection formula, so it scored as fully overlapped in hover. Fixed (|s|) and re-run; only the s < 0 rows changed.

**Hand check: Munk's stagger theorem in the Trefftz plane.**
- Munk (1923): the total induced drag of lifting surfaces with fixed loads does not change when they are moved along the direction their wakes trail in. Only their positions in the Trefftz plane, far downstream and normal to the wake, matter.
- Here the wakes trail along e = (sin χ, 0, −cos χ), at 68° from the shaft, not along the flight path. The Trefftz-plane normal in the x–z plane is n = (cos χ, 0, sin χ). The lower hub at (−s, 0, −h) therefore sits a Trefftz distance

  **G_eff = |s·cos χ + h·sin χ| = |0.372·s + 0.928·h|**

  from the upper.
- Two predictions follow:
  1. σ depends on G_eff alone.
  2. Forward stagger buys only 0.372/0.928 = **40 %** as much as the same length of extra mast height. Aft stagger moves the lower rotor back toward the upper wake (G_eff → 0 at s = −2.5·h).

| (h/D, s/R) | G_eff/b | σ, vortex wake | σ, Prandtl at G_eff |
|---|---|---|---|
| (0.2, 0) and (0.3, −0.5) | 0.186 | **0.594, 0.594** | 0.504 |
| (0.2, 0.5), (0.3, 0) and (0.4, −0.5) | 0.279 | **0.419, 0.419, 0.419** | 0.391 |
| (0.2, 1.0), (0.3, 0.5) and (0.4, 0) | 0.371 | **0.292, 0.292, 0.292** | 0.311 |
| (0.2, 1.5), (0.3, 1.0) and (0.4, 0.5) | 0.464 | **0.232, 0.232, 0.232** | 0.250 |

- **Prediction 1 holds to all three decimals:** geometries with the same G_eff give the same σ. The vortex-wake code obeys Munk's theorem exactly, which is a strong check on it, because nothing in the code was written to make that happen.
- **Prandtl's formula is 5–15 % off at G_eff,** and better above G_eff/b ≈ 0.3. His σ is a curve fit for elliptic wings of the same span, not circular disks. So **entry 07's "1 % match" at G = h was partly luck:** the right gap is G_eff = 0.93·h. The vortex-wake numbers stand; the biplane formula is a sanity check, good to about 10 %.
- **Munk also says how the interference is shared.** The front surface sits in the rear one's upwash, and the rear one in the front one's downwash. With the lower rotor ahead (s ≥ R), the lower sees an upwash (w̄_l < 0) and the upper takes the downwash. The total is set by G_eff alone.

**Results (selected):**

| h/D | s/R | Mast [cm], tilt | σ cruise | κ hover | Cruise [W] | Hover [W] | Pack [Wh] | Payload [kg] |
|---|---|---|---|---|---|---|---|---|
| 0.4 | 0 | 55, 0° | 0.292 | 1.291 | 8851 | 16121 | 5715 | +0.05 |
| 0.3 | 0.5 | 54, 40° | 0.292 | 1.236 | 8772 | 15507 | **5626** | **+0.36** |
| 0.4 | 0.5 | 65, 32° | 0.232 | 1.220 | 8476 | 15324 | 5467 | +0.71 |
| 0.3 | 0.75 | 66, 51° | 0.259 | 1.175 | 8562 | 14825 | 5468 | +0.69 |
| 0.4 | 1.0 | 88, 51° | 0.189 | 1.107 | 8184 | 14051 | 5220 | +1.17 |
| 0.4 | 1.5 | 117, 62° | 0.155 | 1.029 | 7964 | 13183 | 5041 | +1.32 |
| 0.4 | −0.5 | 65, −32° | 0.419 | 1.220 | 9553 | 15324 | 5993 | −1.02 |

**Finding.**
- **The fair comparison is at equal mast length,** since mast length is the structural cost (queue item 12). At about 55 cm, the tilted mast (h/D 0.3, s = R/2) beats the vertical one (h/D 0.4) by **1.6 %** energy and 0.3 kg of payload:
  - cruise: the same σ, by Munk, because both have the same G_eff;
  - hover: the gain is all here. The lower disk is partly out from under the upper wake, so κ drops from 1.29 to 1.24.

  At about 65 cm the two layouts tie (5467 against 5468 Wh). Stagger is a small refinement, not a new lever.
- **Large stagger turns into a different configuration.** At s ≥ R the rotors barely overlap in plan (κ → 1). The 0.9–1.2 m "mast" is then a cantilever arm carrying a rotor, and the arm becomes a tandem pair: queue item 7 (planar hexacopter) in disguise. Its apparent gains (−30 % energy against the tricopter) come mostly from adding planform area, the same lesson as entry 05. They need a real frame-mass model, not 0.51 kg/m of tube.
- **Aft stagger is worse in every case,** as Munk predicts: the lower rotor moves back toward the wake.
- **Stagger only works in one flight direction.** Flying sideways, or with a crosswind component, the Trefftz gap falls back toward h·sin χ, and flying backwards gives aft stagger. A cargo drone that holds its heading in cruise can use it; one that crabs into crosswinds will see the benefit shrink.
- **Trim cost:** forward stagger moves the arm's centre of thrust forward by about s/2 (about 17 cm at s = R/2). The CG has to follow, or the rotors must trim it with differential thrust.

**Next.** The planar layout is now the natural comparison. **Queue item 7: planar hexacopter against Y6**, with a frame-mass model that scales with arm length. That model also covers the long-mast and large-stagger limits seen here. Item 12 (mast structure) follows, because it prices every option in entries 06–08.

### 09 · 2026-11-18 · Tricopter vs Y6 vs planar hexacopter (`src/explore/e09_hex_vs_y6.py`)

**Question.** Entries 01–08 refined the coaxial (Y6) arm. Six rotors could also sit side by side in one plane, a hexacopter: no stacked interference, but longer arms and a wider footprint. Which layout wins once the arms are sized and every rotor's wake acts on every other rotor?

**Configurations.** All use 54 in rotors with 1.10 D between neighbouring hubs (`arm_clearance_factor`).

| | Rotors | Blade, motors | Hub circle | Span |
|---|---|---|---|---|
| tri | 3 at T/3 | Phase 2 blade, U15XL, tilt servo | 0.635 D = 0.87 m | 3.11 m |
| y6 | 3 arms × 2 at T/6, vertical mast h/D 0.4 | entry 03 blade, half-size motors | 0.87 m | 3.11 m |
| hex0 | 6 at T/6 in one plane, one arm on the flight line | entry 03 blade, half-size motors | 1.10 D = 1.51 m | **4.39 m** |
| hex30 | the same, rotated 30° (rotors in side-by-side pairs) | | | 4.39 m |

**Method.**
- **Hover:**
  - tri: Phase 2 numbers;
  - y6: entry 06 (BEMT coaxial model at h/D 0.4);
  - hex: six isolated BEMT rotors at T/6. Interference between neighbouring coplanar rotors with a 10 % tip gap is neglected.
- **Cruise:** each rotor edgewise at its share of the trimmed thrust. On top of that:
  - the vortex-wake interference (entry 07) of every rotor on every other disk: 6, 30, 30 and 30 pairs;
  - cross-flow drag of the arm tubes (Cd 1.2, only the velocity component normal to each arm);
  - y6 mast drag.
- **Mass, relative to the tri:**
  - motors, ESCs, blades, hubs and tilt servo as in earlier entries;
  - y6 masts at 0.51 kg/m, now counted in full;
  - **arms sized as carbon tubes** (below);
  - fuselage, gear, payload mount and avionics common to all.
- **Regression checks:**
  - The tri with the interference and arm-drag terms removed gives **7475 Wh**, the Phase 2 baseline.
  - The y6's within-arm wake numbers come out 0.294 / 0.291, the same as entry 07 at h/D 0.4.

**Hand check: sizing the arm tube.** A cantilever from the fuselage edge (0.25 m) to the hub. Quasi-isotropic carbon, E = 70 GPa, allowable stress 300 MPa, wall at least 1 mm, d/t ≤ 50 against local buckling, plus 0.6 kg of fittings per arm (hinge, clamps, motor mount).
- **Stiffness** (tip deflection ≤ 1 % of L under hover thrust): T·L³/(3EI) ≤ 0.01·L, so I ≥ T·L²/(0.03·E).
  - tri arm: T = 415 N, L = 0.621 m, giving I ≥ 415 × 0.386/(2.1·10⁹) = 7.63·10⁻⁸ m⁴.
  - With d/t = 50, I = πd³t/8 = πd⁴/400, so d = (400·I/π)^¼ = **56 mm**, t = **1.12 mm**.
  - Mass: ρπdtL = 1550 × π × 0.056 × 0.00112 × 0.621 = **0.19 kg**. The code gives 56 mm, 1.12 mm, 0.190 kg.
- **Strength at T/W 2:** M = 830 N × 0.621 m = 515 N·m, so σ = M(d/2)/I = 515 × 0.028/7.63·10⁻⁸ = **189 MPa** < 300. The arm is stiffness-driven.
- **Scaling law.** With stiffness governing and d/t fixed, I ∝ d⁴ ∝ T·L², so d ∝ (T·L²)^¼, and mass per metre ∝ d·t ∝ d², giving **mass ∝ T^½·L²**.
  - hex arm: half the thrust on 2.03× the length: 0.707 × 2.03² = 2.91× the tri tube, i.e. 0.55 kg. The code gives 0.56 kg (66 mm × 1.39 mm).
  - Six of them against three: **5.9× the tube mass**.
  - With fittings the arms come to 1.16 kg per hex arm against 0.79 kg per tri arm, **+4.6 kg** for the hex.
- **Hover by momentum.** The hex has twice the tri's disk area at the same total thrust. Ideal power ∝ T^1.5/√A, so the hex needs 1/√2 = 0.707 of the tri's induced power, a 29.3 % reduction. BEMT gives 12030/16764 = 0.718, a **28.2 %** reduction (the hex rotors run at a lower FoM). The y6 against the hex: same disk count, but κ_int = 1.29 on the induced part. Its hover is 16121/12030 = **1.34×**: the 29 % interference plus a little profile power.

**Results:**

| | Hover [W] | Cruise [W] | Interference [W] | Arm + mast drag [W] | Pack [Wh] | vs tri | Range on the same pack | Hardware vs tri [kg] | Payload vs tri row [kg] |
|---|---|---|---|---|---|---|---|---|---|
| tri | 16764 | 12457 | −37 | 147 | **7528** | 0 | 1.00× | 0 | 0 |
| y6 (h/D 0.4) | 16121 | 9518 | 2205 | 332 | 6040 | −19.8 % | 1.25× | +6.18 | **−1.27** |
| hex0 | 12030 | 7640 | −41 | 700 | **4789** | **−36.4 %** | **1.57×** | +9.94 | **−0.90** |
| hex30 | 12030 | 7746 | +65 | 700 | 4841 | −35.7 % | 1.56× | +9.94 | −1.07 |

**What the interference column says.**
- **Planar layouts barely interfere in cruise.** At a 1.1 D hub spacing, the tri's three rotors, and the hex's six, sit far apart in the Trefftz plane.
  - Side-by-side rotors are even slightly favourable: like formation flight, each sits in the other's tip upwash.
  - The fore-aft pairs of hex0 cost little: a fore-aft spacing of 1.9 D puts them 0.7 D apart in the Trefftz plane (×cos χ, entry 08).
- **The y6's 2.2 kW is 1.7 kW from the stacked pairs** (entry 07) plus 0.5 kW between arms.

**Finding.**
- **On energy the planar hex wins clearly.** It needs 36 % less pack energy than the tri and 21 % less than the y6, so it flies 1.57× the tri's range on the same pack. The reasons:
  1. six unshared disks (no κ_int);
  2. the big, slow entry 03 blade, which also cruises better than the Phase 2 blade;
  3. almost no interference.
- **On payload, the three layouts are tied** within about 1.3 kg (2 % of the 61 kg payload). This model can't separate differences that small. Battery saved on the hex (2.7 kWh = 9.0 kg) is almost exactly spent on hardware (+9.9 kg). That hardware is mostly six half-size motors at 1.15× the specific mass, plus three extra arms and fittings. The tube itself is only 2.8 kg of it.
- **The ranking hangs on two assumptions:**
  - **Motors:** at the U15XL's own specific mass (scale 0.5 instead of 0.575), both six-rotor layouts gain 2.0 kg of payload and beat the tri.
  - **Fittings:** ±0.3 kg per arm fitting moves the hex by ∓0.9 kg against the y6.
  - Queue item 16 replaces both with catalogue numbers.
- **Arm drag is now a real term.** The hex's six bare tubes cost 700 W in cruise. Faired arms (Cd ≈ 0.2) would recover about 580 W, which is roughly 260 Wh (≈ 0.45 Wh per W of cruise, from entries 06–08), or about 0.9 kg. Queue item 15.
- **The catch is size.** A 4.4 m span against 3.1 m (+41 %) affects ground handling, transport and landing zones. If the footprint is capped near today's 3.1 m, the y6 is the best six-rotor option. If it isn't, the planar hex is the most efficient layout found so far.
- **The tri's place:** it is the lightest and simplest (three motors), but it has the worst range of the four, by a wide margin.

**Next.**
- **Queue item 16:** real motor and ESC masses for the half-size class. It decides the payload ranking.
- **Queue item 15:** faired arms and masts.
- **Queue item 8:** cruise speed per configuration. The hex's low induced power should push its best-range speed up.

### 10 · 2026-11-18 · Motor and fitting masses from catalogue data (`src/explore/e10_motor_mass.py`)

**Question.** Entry 09's payload ranking depended on two assumed numbers: a half-size motor weighs 0.5 × U15XL × 1.15, and each arm fitting weighs 0.6 kg. What do catalogue data say?

**What sizes a motor.** An electric motor's torque is roughly (rotor volume) × (magnetic shear stress in the air gap). At a given technology and cooling, **mass scales with peak torque, not with power**: power is torque × speed, and speed is nearly free. So the motor fit is mass against the 100 %-throttle torque in the vendor test tables (T-Motor, accessed 2026-11-18):

| Motor | Mass [kg] | Test point | Torque [N·m] | N·m/kg | Check: τω / VI |
|---|---|---|---|---|---|
| [U13II KV65](https://store.tmotor.com/product/u13-v2-kv65-motor-u-power.html) | 0.975 | G32×11, 98 V, 4397 rpm | 11.4 | 11.7 | 5.25 / 6.73 kW = 0.78 |
| [U15II KV80](https://store.tmotor.com/goods.php?id=732) | 1.740 | G40×13.1, 60 V, 3546 rpm | 18.0 | 10.3 | 6.68 / 8.58 kW = 0.78 |
| [U15XL KV38](https://ligpower.com/product/u15xl-manned-aircraft-combo.html) | 4.408 | 52×20, 96 V, 2910 rpm | 50.4 | 11.4 | 15.36 / 16.89 kW = 0.91 |

The last column checks that each table row is self-consistent: shaft power τω against electrical power VI gives a plausible efficiency in every row. The automated page reading had swapped the U15II's thrust and RPM columns, and this check caught it.

- **Fit:** log-log least squares gives m = 0.0909·τ^**0.996**. Torque density is flat at about 11 N·m/kg across a 4.4× torque range, so **this family shows no small-motor penalty.**
- **The ×1.15 assumption is not supported.** Pairwise exponents bracket the fit: 0.90 (U15II–U15XL) to 1.02 (U13II–U15XL). One caveat: the U15II row is at 60 V, below its 24S limit, so it is a test point rather than a torque ceiling. That makes 0.90 the pessimistic end.

**Required torque.** BEMT hover trim at T/W = 2 on a hot day (thrust 2 × T_rotor). For the y6 the full coaxial model is used at twice the arm thrust; with equal torque, both motors see the same torque.

**Hand check:** a fixed-pitch rotor's thrust and torque both scale with Ω² (constant C_T and C_Q), so torque is proportional to thrust:

  Q_max = 2·Q_hover = 2·P_hover/Ω_hover

| Rotor | Q_hover × 2 (hand) [N·m] | Q_max, BEMT [N·m] | rpm at max | Motor from the fit [kg] | Old assumption [kg] |
|---|---|---|---|---|---|
| tri (Phase 2 blade, T/3) | 55.2 | **55.8** | 2693 | 4.99 | 4.41 (U15XL) |
| hex (entry 03 blade, T/6) | 30.2 | **30.2** | 1786 | **2.70** | 2.53 |
| y6 (entry 03 blade, coaxial at h/D 0.4) | n/a | **34.9** | 1941 / lower | **3.13** | 2.53 |

The hand estimate is within 1 % (the small difference comes from Reynolds-number effects on C_Q).

**Why the six-rotor motors are not "half-size":**
- **hex:** half the thrust on the same diameter, but entry 03's blade is wide and slow (1270 rpm in hover), so it needs **54 %** of the tri's torque, not 50 %. Torque is P/Ω, and a slow rotor needs more of it for the same power.
- **y6:** the coaxial interference raises the power at the same thrust (κ_int), and the equal-torque trim shares it, so each motor needs **63 %**.

**Fittings** per arm = folding joint + motor mount + root clamp.
- **Joint:** [retail listings](https://rcdrone.top/sv/products/rjxhobby-30mm-40mm-50mm-vikbar-dronare-arm-kol-ror-koppling-klamma-sjalvlas-for-lantbruksdronare) give 257 g at 40 mm and 334 g at 50 mm. Scaled with d² to entry 09's tubes, that is 0.42 kg at 56 mm and 0.58 kg at 66 mm.
- **Motor mount:** 0.20 kg per full-size motor, 0.12 kg per half-size one.
- **Root clamp:** 0.10 kg.
- **Totals:** tri 0.72 kg, y6 arm 0.76 kg, hex arm 0.80 kg, against 0.6 kg assumed for all.
- **ESC:** mass ∝ (peak power)^0.7 from the 0.87 kg 300 A unit. That exponent is an assumption; there is no catalogue series behind it.

**Entry 09 re-scored** (pack energies unchanged; only mass changes):

| | Hardware [kg] | vs tri | Pack [Wh] | Payload vs tri, entry 09 [kg] | **Payload vs tri, now [kg]** |
|---|---|---|---|---|---|
| tri | 24.52 | 0 | 7528 | 0 | 0 |
| y6 (h/D 0.4) | 32.76 | +8.24 | 6040 | −1.27 | **−3.33** |
| hex0 | 33.99 | +9.48 | 4789 | −0.91 | **−0.44** |
| hex30 | 33.99 | +9.48 | 4841 | −1.08 | −0.61 |

Sensitivity of the hex payload to the motor fit: −0.9 kg (exponent 0.90) to +0.2 kg (1.02).

**Finding.**
- **The planar hex ties the tricopter on payload** (−0.4 kg, within ±0.9 kg of model uncertainty) **while needing 36 % less energy.** On the payload metric it is now **2.9 kg ahead of the y6**. The y6 fell back because its coaxial interference costs torque as well as energy, so its motors are 0.4 kg heavier each than the hex's.
- **Motor torque couples blade design to vehicle mass.** That coupling was missing from entries 01–03, whose optimisers counted the slow, wide blade's energy savings but not its motor. A slow rotor needs torque, and torque is mass, at about 11 N·m per kg. Queue item 17 re-optimises the blade with motor mass ∝ Q_max in the objective. It will probably move back toward a somewhat faster, narrower blade.
- **Side finding (queue item 18).** The tri at T/W 2 on a hot day needs 55.8 N·m, but the U15XL's 96 V test delivers 50.4 N·m. On that test point the tri reaches T/W ≈ 2 × 50.4/55.8 = **1.8**: still above the 1.5 requirement, below the 2.0 target. Phase 1 sized the T/W target at the tip-Mach limit; the motor's torque limit is the tighter constraint.
- **Data quality:** vendor test tables, accessed today, are vendor claims. The ESC exponent and the motor-mount masses are assumptions. All of them are logged in `results/explore/e10_motor_mass.json`.

**Next.** Queue item 17: the blade re-optimisation with the motor in the objective, for the hex (now the leading layout) and for the y6.

### 11 · 2026-11-18 · Hexacopter blade re-optimised with torque-sized motors (`src/explore/e11_blade_with_motor.py`)

**Question.** Entry 10 showed motor mass follows peak torque (about 11 N·m/kg), and Q = P/Ω, so a slow blade needs a heavy motor. Entries 02–03 optimised the blade with the motor mass frozen. What blade does the planar hex want once the motor follows the blade?

**Method.**
- **Objective:** payload against the tricopter, with everything the blade changes:
  - pack energy: six isolated rotors in hover, edgewise cruise, entry 09's interference (−41 W) and arm drag (700 W);
  - blade mass from the spar model (50 N / 1.2 mm);
  - motor mass from the peak torque at T/W 2 (entry 10 fit);
  - ESC mass from the peak power.
- **Variables and penalties:** the same four variables and penalties as entries 02–03: stall margin, T/W ≥ 2 below the tip-Mach RPM, flex.
- **Runs:** two starts (entry 03's blade, entry 01's MIL 1750 rpm blade) × two objectives:
  - **motor:** the motor and ESC follow the blade;
  - **fixed:** they are frozen at the start blade's values.

  Every end point is re-scored with the motor following the blade ("true" payload).
- **Regression check:** entry 03's blade scores −0.44 kg and 4789 Wh, identical to entry 10.

| Start | Objective | Hover rpm | Solidity | Q_max [N·m] | Motor [kg] | Blade [kg] | Pack [Wh] | Payload vs tri, true [kg] | Payload the optimiser saw [kg] |
|---|---|---|---|---|---|---|---|---|---|
| e03 blade | (start) | 1269 | 0.141 | 30.2 | 2.70 | 0.438 | 4789 | −0.44 | |
| e03 blade | fixed | 1264 | 0.141 | 30.3 | 2.72 | 0.438 | 4788 | −0.52 | −0.44 |
| MIL 1750 | (start) | 1758 | 0.069 | | 1.96 | 0.575 | 5346 | +0.56 | |
| MIL 1750 | fixed | 1263 | 0.139 | 30.4 | 2.73 | 0.439 | 4799 | **−0.64** | **+4.00** |
| e03 blade | **motor** | **1775** | 0.121 | 22.9 | 2.06 | 0.434 | 5153 | **+2.17** | +2.17 |
| MIL 1750 | **motor** | **1783** | 0.128 | 22.6 | 2.03 | 0.451 | 5113 | **+2.28** | +2.28 |

**Finding.**
- **Each objective has one answer, whichever start it is given.**
  - **Frozen motor:** both starts go to entry 03's blade (1265 rpm, σ 0.14). That independently reproduces entry 03's convergence.
  - **Motor in the objective:** both starts go to a **faster, narrower blade at about 1780 rpm hover, σ ≈ 0.12–0.13**, with peak torque down from 30 to 22.7 N·m.
- **The trade:**
  - battery: +6.8 % pack energy (5113 against 4789 Wh), which costs 1.1 kg;
  - motors: lighter by 6 × 0.67 = **4.0 kg**.

  Net payload: **+2.3 kg against the tricopter**, a 2.7 kg swing on entry 10's verdict. The hex now beats the tricopter on payload **and** on energy (−32 %, 1.47× range).
- **Same lesson as entry 03, again:** what an objective holds fixed, the optimiser treats as free. With the motor frozen at the MIL blade's small 1.96 kg, the optimiser "found" +4.0 kg by slowing the rotor down. Re-scored honestly it is −0.64 kg. Every mass that depends on the design must be inside the objective.

**Hand check: the marginal balance at the optimum.** At an interior optimum, a small change in hover speed Ω (a ±3 % chord scale at fixed thrust) changes payload by zero, so the mass terms must cancel. Finite differences at the best blade:

| Term (6 rotors) | d(mass)/dΩ [kg per rad/s] |
|---|---|
| motors, finite difference | −0.072 |
| motors, hand: d/dΩ [6·c·2P_h/Ω] = −12·c·P_h/Ω², c = 0.089 kg/N·m, P_h = 2.0 kW, Ω = 186 rad/s | −0.064 |
| battery (pack/303 Wh/kg) | +0.036 |
| blades: a narrower chord means a thinner section and a heavier spar | +0.040 |
| **payload** = −(sum) | **−0.003 ≈ 0** ✓ |

- **Torque at the optimum:** Q_max = 2·P_h/Ω (entry 10) gives 22.4 N·m by hand against 22.6 from BEMT.
- **Why the hand motor slope is 11 % low:** it holds P_h fixed. Spinning faster also adds profile power, which nudges torque, and the chord scale changes the blade's C_Q.
- **What the balance shows:** each rad/s of extra speed saves 0.072 kg of motor and costs 0.076 kg of battery and blade, so the blade sits where those two meet. The spar model and the motor fit are both in the answer: drop either one and the optimum moves.

**Caveats.**
- The payload advantage (+2.3 kg, about 4 % of the payload) is about 2.5× the motor-fit uncertainty from entry 10 (±0.9 kg), so the hex's lead is real, but not by a wide margin.
- At about 2500 rpm at T/W 2, the faster blade's tip Mach is about 0.52. That is inside the 0.60 cap, but louder than entry 03's blade (queue item 10).

**Next.** Queue item 19: the same optimisation for the y6 arm, so the y6–hex comparison is like for like. The y6's coaxial interference makes its torque higher, so it should benefit at least as much.

## 12 — Y6 blade re-optimised with torque-sized motors (2026-11-18)

**Question.** Entry 11 gave the hex +2.7 kg by letting the blade speed up once motor mass (∝ peak torque) was in the objective. Does the y6 arm gain as much, so that the y6–hex ranking is like for like?

**Method** (`src/explore/e12_y6_blade_with_motor.py`). Entry 11's optimiser (spar mass model, 1.2 mm flex test, catalogue motor fit m = 0.0909·τ^0.996, ESC ∝ P_max^0.7), applied to the y6 arm at h/D 0.4:
- **Coaxial surrogate.** A full coaxial trim per evaluation is too slow (≈ 3 s), so each run calibrates three ratios on its start blade with the full vortex-cylinder model (entry 05's `coax_split`, equal-torque trim):
  - k_P = P_pair / (2·P_iso) at hover (the coaxial power penalty),
  - k_Q = Q_coax,max / Q_iso,max at T/W 2 (the torque penalty that sizes the motor),
  - k_P,max = max(P_upper, P_lower) / P_iso at T/W 2 (sizes the ESC).
  The optimiser then works on isolated-rotor BEMT × these ratios, and the end blade is re-scored with the full coaxial model.
- **Lower-rotor tip Mach.** At T/W 2 the lower rotor, sitting in the upper's wake, spins about 15 % faster than the upper and 26 % faster than an isolated rotor. The first run ignored that and finished at **M 0.65** on the lower tip, above the 0.60 cap. The rerun applies the cap to rpm_lower,max = r_lower·rpm_iso,max (r_lower from the start blade's coaxial trim).
- Two starts: entry 03's blade (σ 0.141, 1269 rpm), and entry 11's hex optimum.

**Results** (full-model re-score; payload against the tricopter, same bookkeeping as entries 10–11):

| Start | Mach cap on lower | Hover rpm (iso) | σ | Q_max [N·m] | Motor [kg] | Pack [Wh] | Lower tip M at T/W 2 | Payload vs tri [kg] | Surrogate saw [kg] |
|---|---|---|---|---|---|---|---|---|---|
| e03 blade | (start) | 1269 | 0.141 | 34.9 | 3.13 | 6040 | 0.44 | −3.33 | |
| e03 blade | no | 1794 | 0.120 | 26.5 | 2.38 | 6489 | 0.65 ✗ | −0.52 | −0.19 |
| e03 blade | yes | 1726 | 0.121 | 27.1 | 2.43 | 6404 | 0.61 | −0.50 | −0.23 |
| e11 hex opt. | (start) | 1783 | 0.128 | 26.4 | 2.37 | 6420 | 0.63 ✗ | −0.38 | |
| e11 hex opt. | no | 1800 | 0.128 | 26.2 | 2.35 | 6431 | — | −0.38 | −0.38 |
| e11 hex opt. | **yes** | **1690** | 0.130 | 27.2 | 2.44 | **6306** | **0.595** | **−0.43** | −0.47 |

**Finding.**
- **The y6 gains as much as the hex did** (−3.3 → −0.4 kg, a 2.9 kg swing, against the hex's 2.7 kg), and for the same reason: motors at 11 N·m/kg make a slow, wide blade expensive. It lands on nearly the same blade as the hex (σ 0.13, ≈ 1700–1800 rpm).
- **But the ranking does not change.** Like for like, **hex +2.3 kg, y6 −0.4 kg** against the tricopter: the hex leads by **2.7 kg** of payload and uses **19 % less energy** (5113 vs 6306 Wh). The y6's 2.2 kW cruise interference and its 1.37× hover power penalty are paid in battery, and the motor trade cannot buy that back.
- **The y6 is the first layout to hit the tip-Mach cap.** Its lower rotor is the fastest rotor on the vehicle. The cap costs only 0.05 kg here (the payload is flat near the optimum), but it binds: entry 11's hex blade, bolted onto a y6 arm, would run its lower tip at M 0.63.
- **Both starts converge within 0.07 kg of payload**, and the e03 run stops just above the cap (0.612: the penalty is soft). The surrogate's payload error is 0.3 kg from a far start and < 0.05 kg from a near one, because k_P drifts as the blade changes (1.340 → 1.374). That is small against the 2.7 kg gap, so the verdict doesn't depend on it.

**Hand check 1: torque penalty → power penalty.** In an equal-torque trim both motors deliver the same Q, so the pair's power is Q·(Ω_u + Ω_l), against 2·Q_iso·Ω_iso for two isolated rotors at the same total thrust. Hence

  k_P = P_pair / (2·P_iso) = (Q/Q_iso)·(Ω_u + Ω_l)/(2·Ω_iso) = k_Q·(Ω_u + Ω_l)/(2·Ω_iso).

At T/W 2 on the start blade: 1.157 × (1941 + 2206)/(2 × 1786) = **1.343**, against the coaxial model's 1.343 ✓. On the constrained end blade: 1.165 × (2641 + 3045)/(2 × 2419) = **1.369** vs 1.369 ✓. The identity is exact. It is a good check that the model's power, torque and speed agree. It also shows why the torque penalty (1.16) is smaller than the power penalty (1.37): the lower rotor pays most of its penalty in speed, not torque.

**Hand check 2: lower tip Mach.** For a fixed-pitch rotor, tip Mach scales with rpm, so M_lower = 0.60 × rpm_lower,max / rpm(M 0.60) = 0.60 × 2964 / 2987 = **0.595** ✓. That also checks the hot-day speed of sound: rpm(M 0.60) = 2987 means V_tip = 2987 × 2π/60 × 0.686 m = 214.5 m/s, so a = 357.5 m/s, T = a²/(γR) = 357.5²/401.9 = 318 K, the 45 °C hot day in params.yaml ✓.

**Takeaways.**
- Like for like, the planar hex beats the y6 on both payload (+2.7 kg) and energy (−19 %). **The y6 is now ranked third**, behind the hex and the tri (it keeps its compact footprint, 3.11 m against 4.39 m span).
- With the motor in the objective, every layout's blade converges to σ ≈ 0.12–0.13 at ≈ 1700–1800 rpm hover. **That blade, not entry 03's, is the new baseline** for the remaining queue items.
- Coaxial designs must check the **lower** rotor's tip Mach at T/W 2, not the isolated one.

**Next.** Queue item 18 (U15XL torque margin): the tri's hot-day T/W 2 needs 55.8 N·m against 50.4 N·m tested. The tri is the reference for every payload number, so its motor must be sized consistently with the hex's (by torque, from the same fit) before item 8 (cruise speed per configuration).

## 13 — The tricopter reference re-optimised with torque-sized motors; the U15XL torque margin (2026-11-18)

**Question.** Every payload figure in entries 09–12 is measured against the tricopter with its Phase 2 blade. Entries 11–12 let the hex and y6 blades re-optimise with motor mass ∝ peak torque in the objective, but the tri did not. Two linked questions:
- (a) The Phase 2 tri needs 55.8 N·m per rotor at T/W 2 on the hot day, but the U15XL's 96 V test delivers 50.4 N·m. What T/W does the real motor give?
- (b) If the tri blade is re-optimised the same way, how much of the hex's +2.3 kg lead is left?

**Method** (`src/explore/e13_tri_torque_margin.py`). Entry 11's model for 3 rotors at W/3:
- pack from 3 isolated rotors in hover and 3 edgewise rotors in cruise, plus entry 09's tri interference (−37 W) and arm drag (147 W);
- hardware 3 × (motor + ESC + 2 blades + hub) + tilt servo + arms, with the motor from the entry 10 fit at Q_max and the spar blade-mass model;
- constraints: stall margin, flex test, and T/W ≥ 2 reachable below the 0.60 tip-Mach rpm.

Payload is reported as the change against the Phase 2 blade scored with this same model, so model offsets cancel. The model reproduces the reference exactly: pack **7528 Wh** and Q_max **55.8 N·m**, both as in entries 09–10. Two starts: the Phase 2 blade, and entry 11's hex optimum.

**Results.**

| Start | | Hover rpm | σ | Q_max [N·m] | Motor (fit) [kg] | Pack [Wh] | Tip M at T/W 2 | U15XL T/W | Δpayload [kg] |
|---|---|---|---|---|---|---|---|---|---|
| Phase 2 blade | start | 1932 | 0.104 | 55.8 | 4.99 | 7528 | 0.54 | 1.81 | 0 |
| Phase 2 blade | optimum | 2142 | 0.127 | 50.8 | 4.54 | 7476 | **0.600** | 1.99 | +1.82 |
| e11 hex optimum | start | 2497 | 0.128 | 45.5 | 4.07 | 7819 | 0.70 ✗ | 2.22 | (+2.02, infeasible: T/W 1.45 at the Mach cap) |
| e11 hex optimum | **optimum** | **2141** | 0.140 | **50.6** | 4.53 | **7422** | **0.601** | **1.99** | **+1.89** |

**Finding.**
- **(a) The real motor gives T/W 1.81 with the Phase 2 blade.** That meets the 1.5 requirement but misses the 2.0 target.
- **(b) The tri blade gains +1.9 kg**, nearly as much as the hex blade gained in entry 11 (+2.7 kg), for the same reason: a faster blade needs less torque, and torque is motor mass. Both starts converge to the same point, about 2140 rpm hover with Q_max 50.7 N·m, within 0.07 kg.
- **The tri's optimum sits on the tip-Mach cap.** The tri rotor carries twice the hex rotor's thrust, so at T/W 2 it reaches M 0.60 before the motor and battery terms balance. That was not true for the hex (entry 11, M 0.52 at its optimum). The cap is now what limits the tri, and queue item 20 prices it.
- **A coincidence that matters:** the optimum needs 50.6 N·m, and the U15XL is tested at 50.4 N·m. So with the re-optimised blade, **the existing U15XL reaches T/W 1.99**, and item 18's torque shortfall disappears. The catalogue motor (4.41 kg) is also 0.12 kg lighter than the fit at that torque (4.51 kg); that is within the fit's scatter and not counted.
- **The layout ranking narrows sharply.** Against the re-optimised tri (the re-optimisation is a constant shift of the reference, so entries 11–12's optima stand):

| Layout (all blades re-optimised with the motor) | Payload vs tri [kg] | Pack [Wh] | Energy vs tri |
|---|---|---|---|
| tri | 0 | 7422 | — |
| **hex** | **+0.39** | **5113** | **−31 %** |
| y6 | −2.32 | 6306 | −15 % |

  - The hex's payload lead (+0.4 kg) is now **smaller than the motor-fit uncertainty** (±0.9 kg, entry 10). On payload, **the hex and the tri tie**.
  - The hex still has **31 % less energy, i.e. 1.45× the range** at equal payload. That margin is large and robust.
  - The y6 is clearly third on payload.
- **Lesson.** A comparison is only as fair as its reference. Entry 11 optimised one side of the comparison and reported a +2.3 kg lead. Most of that lead (1.9 kg) came from not optimising the other side.

**Hand check 1: T/W at a torque limit.** For a fixed-pitch rotor, T = C_T·ρA(ΩR)² and Q = C_Q·ρA(ΩR)²R. When C_T and C_Q barely change with rpm, T ∝ Q, so

  T/W at Q_lim = 2 × Q_lim / Q(T/W 2).

- Phase 2 blade: 2 × 50.4 / 55.8 = **1.807**, against BEMT (root-solved for Q = 50.4 N·m) **1.811** ✓.
- Optimum: 2 × 50.4 / 50.64 = **1.991**, against BEMT **1.991** ✓.

The 0.2 % gap on the Phase 2 blade is the slow rise of C_T/C_Q with Reynolds number as rpm goes up. The same effect gives Q_max = 55.8 against 2·Q_hover = 55.2 N·m.

**Hand check 2: why 50.7 N·m is the floor at the Mach cap.** At the cap, the rotor's maximum speed is fixed: Ω_cap = M·a/R = 0.60 × 357.6 / 0.686 = **312.8 rad/s** (2987 rpm). The torque needed at T/W 2 is the power divided by that speed, and momentum theory gives the power through the figure of merit:

  P = T^1.5 / (FM·√(2ρA)),  T = 2W/3 = 830 N, ρ = 1.109 kg/m³ (45 °C), A = 1.478 m²
  P_ideal = 830^1.5 / √(2 × 1.109 × 1.478) = **13.21 kW**.

With the BEMT power of 15.86 kW at that point, FM = 13.21 / 15.86 = **0.83**, a well-loaded rotor. Then Q = 15.86 kW / 312.8 = **50.7 N·m**, against 50.6 from BEMT ✓.

So once the speed is capped, the only remaining way to reduce torque is a better figure of merit. Each +0.01 of FM is about −0.6 N·m, or −0.05 kg of motor per rotor. That is why the optimiser stops here, and why the cap (item 20) is now the tri's most valuable lever.

**Next.**
- **Queue item 15, faired arms.** The hex's six bare arms cost 700 W of cruise drag against the tri's 147 W. Fairing them at Cd ≈ 0.2 is worth about 0.9 kg (entry 09). With the payload ranking now within the uncertainty, that is the term that can decide it.
- Then item 20 (the tri's tip-Mach sensitivity), and item 21 (re-rank all layouts with consistent blades and an uncertainty band).

## 14 — Faired arms and masts, with hover download (2026-11-18)

**Question.** Entry 09 charged the hex's six bare arm tubes 700 W of cruise drag, against 147 W for the tri, and estimated a fairing would win back about 0.9 kg. With the payload ranking now inside the uncertainty (entry 13), is that the term that decides it? Entry 09 left out two things:
- **the fairing's own mass**;
- **hover download.** Each arm sits in its own rotor's downwash, and a fairing whose chord lies in the flight plane is broadside to that downwash.

**Method** (`src/explore/e14_faired_arms.py`). No BEMT re-run is needed. The script takes each layout's best blade so far (entry 13 tri, entry 11 hex, entry 12 y6), replaces entry 09's arm and mast terms, re-prices the pack with the mission model, and adds the fairing mass. Four options for each arm:
- **bare**: tube, Cd 1.2 on the diameter d.
- **full**: fixed fairing over the whole arm, chord in the flight plane.
- **outboard**: fixed fairing only on the part of the arm outside the rotor disk. This gains in cruise with no extra download.
- **swivel**: a trailing fairing free to weathervane about the tube, like a towed-cable fairing. It lines up with the downwash in hover and with the free stream in cruise.

Each fairing option is run at t/c 0.25, 0.33 and 0.5. Y6 masts are vertical, so the downwash runs along them, and a fixed mast fairing costs nothing in hover.

**The physics, step by step.**
1. **Cruise drag of a yawed cylinder (cross-flow principle).** Only the velocity component normal to the axis, V·sin φ, makes a section force. That force is q·Cd·d·sin²φ per metre, and its component along the flight path carries one more sin φ:
   D' = q·Cd·d·sin³φ.
   Entry 09 used sin²φ, which overstates the oblique arms. For the hex (arms at 0°, ±60°, ±120°, 180°): Σsin³ = 4 × 0.866³ = **2.60** against Σsin² = **3.00**, so the bare arms cost **606 W, not 700 W**.
2. **Fairing section drag** (Hoerner's formula for a streamlined 2-D section in attached flow, with turbulent skin friction because the arm sits in rotor wash):
   Cd_c = 2·C_f·[1 + 2(t/c) + 60(t/c)⁴],  C_f = 0.074·Re_c^(−0.2),  Cd_t = Cd_c·c/t.
   - The three terms are friction on the wetted area, the extra friction from supervelocity over thickness, and pressure drag from the thickness.
   - For the hex arm at t/c 0.33: c = 0.200 m, Re = 15 × 0.200 / 1.75×10⁻⁵ = 1.71×10⁵, C_f = 0.00665, Cd_c = 0.0133 × 2.372 = 0.0316, so **Cd_t = 0.096**: a 12.6× cut from the bare tube's 1.2.
3. **Hover download.**
   - **Wake speed.** The hex rotor at W/6 has v_i = √(T/(2ρA)) = √(207.6 / (2 × 1.109 × 1.478)) = **7.96 m/s**. At the arm, Z = 0.12 m below the disk, the vortex-cylinder formula gives w = v_i(1 + Z/√(R² + Z²)) = 1.17·v_i = **9.33 m/s**, so q_w = 48.3 Pa.
   - **Area in the wake.** The downwash acts on the arm length under the disk, from the hub out to 0.2 R: 0.55 m.
   - **Bare tube.** Download per arm = 48.3 × 1.2 × 0.066 × 0.549 = **2.10 N**. Six arms give 12.6 N, **1.0 % of the weight**.
   - **Power cost.** The rotors must lift W + D, and P ∝ T^1.5, so hover power rises by (1 + D/W)^1.5: **+1.5 %**.
   - **Fixed fairing.** A broadside fairing (Cd 1.5 on the chord) multiplies the download by 1.5c / (1.2d) = 1.25/(t/c): **×3.8** at t/c 0.33.
4. **Fuselage download.** The tri and y6 disks reach a 0.25 m fuselage radius (0.039 m² of overlap in total, about 3.8 N). The hex disks start 0.82 m out and do not. This is reported for completeness but is small.
5. **Mass.** Skin of 0.35 kg/m² × 1.15 (ribs and bonding) over the wetted perimeter aft of the tube, 2c − 0.57d. The swivel adds 0.05 kg of collars per arm.

**Results** (payload against entry 13's re-optimised tri with bare arms; best t/c for each option):

| Layout | Option | Arm + mast cruise drag [W] | Download [% W] | Pack [Wh] | Fairing [kg] | Payload [kg] |
|---|---|---|---|---|---|---|
| tri | **bare** | 127 | 0.86 (+0.3 fuselage) | 7436 | 0 | **−0.05** |
| tri | full, t/c 0.5 | 18 | 2.14 | 7410 | 0.14 | −0.10 |
| tri | swivel, t/c 0.5 | 18 | 0.12 | 7368 | 0.29 | −0.12 |
| hex | bare | 606 | 1.01 | 5083 | 0 | +0.49 |
| hex | **full, t/c 0.5** | 84 | 2.53 | **4852** | 0.69 | **+0.56** |
| hex | outboard, t/c 0.5 | 368 | 1.01 | 4967 | 0.31 | +0.56 |
| hex | swivel, t/c 0.5 | 84 | 0.14 | 4815 | 0.99 | +0.38 |
| y6 | bare | 127 + 185 | 0.84 | 6320 | 0 | −2.36 |
| y6 | **masts only, t/c 0.5** | 127 + 26 | 0.84 | 6243 | 0.09 | **−2.20** |

**Finding.**
- **Fairings are nearly payload-neutral.** On the hex the best fairing buys back only **+0.07 kg**, not the 0.9 kg entry 09 estimated. Two things eat the gain:
  - the fairing's own mass: 0.69 kg against 0.76 kg of battery saved;
  - entry 09's 700 W was 15 % high (sin² against sin³).
- **Fairings save energy.** At equal payload the faired hex needs **4.6 % less energy** (4852 against 5083 Wh). If the mission is range rather than payload, faired arms pay.
- **Hover download, newly modelled, costs about 1 % of the thrust for bare arms.** That is small in payload because hover is a short part of the mission. A fixed fairing can triple it, which is why the thickest section (t/c 0.5, short chord) wins.
- **On the tri, fairings never pay.** Its arms (0.62 m) lie entirely under its disks, and the bare arms are cheap in cruise anyway.
- **On the y6, faired masts pay** (+0.16 kg for 0.09 kg of fairing), because a vertical mast has no download.
- **The swivelling fairing is the best aerodynamic option but the heaviest**, and it carries a flutter risk. It does not pay at this skin weight.
- **Updated ranking**, each layout with its best option:

| Layout | Payload vs tri [kg] | Pack [Wh] | Energy vs tri |
|---|---|---|---|
| tri (bare) | 0 | 7436 | — |
| **hex (full t/c 0.5)** | **+0.61** | **4852** | **−35 %** |
| y6 (masts faired) | −2.15 | 6243 | −16 % |

  The hex's payload lead is still inside the ±0.9 kg motor-fit band. Its energy lead (1.53× range) has grown.

**Hand check: the energy bookkeeping.** By finite differences of the mission model, each watt of hover power costs **0.082 Wh** of pack (≈ 4.9 min of hover) and each watt of cruise costs **0.488 Wh** (≈ 29 min). For the hex full fairing at t/c 0.5:
- cruise saving (606 − 84) × 0.488 = **255 Wh**;
- hover penalty (13042 − 12754) × 0.082 = **24 Wh**;
- net **−231 Wh**, so 5083 − 231 = **4852 Wh** ✓ (the model gives 4852);
- payload: 231 / 303.3 = 0.76 kg of battery, minus the 0.69 kg fairing, gives **+0.07 kg** ✓ (+0.49 → +0.56).

The asymmetry (0.49 against 0.08 Wh/W) is why a fairing that triples the hover download can still pay: cruise is six times longer than hover.

**Sensitivities.**
- **Broadside Cd.** At t/c 0.33 the hex full fairing gains +0.18 kg with Cd 1.2 and +0.07 kg with Cd 2.0.
- **Skin weight.** The payload gain scales as 0.76 − 0.69 × (skin / 0.35), so the break-even is **0.39 kg/m²**. At 0.2 kg/m² (one ply of 100 g/m² fabric with film adhesive) the faired hex gains +0.37 kg (queue item 22).

**Next.** Queue item 20: the tri's tip-Mach sensitivity. Its optimum sits on the 0.60 cap (entry 13), so d(payload)/d(M_cap) says what the noise limit costs. That is the tri's remaining lever in a payload race now within a kilogram.


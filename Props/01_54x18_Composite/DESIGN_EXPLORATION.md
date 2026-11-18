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
6. ~~3-blade rotors~~ (entry 21: −2.2 kg tri, −4.3 kg hex, driven by the per-blade 50 N / 1.2 mm flex test; hub roll ripple −89 %)
7. ~~Planar hexacopter against Y6: six isolated disks need a bigger frame, but they have no interference~~ (entry 09: hex best on energy, all three tie on payload)
8. ~~Cruise speed per configuration~~ (entry 16: best-range speeds 21–25 m/s for all layouts; at its best speed the tri wins payload by 3.4 kg, the hex still wins energy by 25 %)
9. ~~Camber (64xx)~~ (entry 20: loses with torque-sized motors: hybrid −0.14/−0.18 kg, full 64xx −0.9/−1.1 kg for tri/hex; keep 44xx)
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
20. ~~Tip-Mach sensitivity of the tri~~ (entry 15: 0.71 kg per 0.05 of cap below 0.60; the hex is insensitive down to 0.50, so a stricter cap favours the hex)
22. Lighter fairing construction (skin < 0.39 kg/m² is the break-even) and thicker sections (t/c 0.5 won at the edge of the sweep)
23. ~~Re-optimise each layout's blade at its own best-range speed~~ (entry 17: −0.14 kg tri, −0.07 kg hex; the blades are set by hover sizing; tri leads by 3.2 kg at free speed). Still open: re-state the 15 m/s requirement as a minimum
24. ~~Fuselage drag against pitch attitude~~ (entry 18: a bluff body costs the tri 2.5 kg and the hex 1.5 kg at free speed; a body built nose-down at the cruise attitude recovers it; the tri still leads by 2.2–3.4 kg)
21. ~~Consolidated layout ranking with uncertainty bands~~ (entry 19: the speed requirement decides it; hex wins at 15 m/s for any pack below 338 Wh/kg, tri wins at free speed for any pack above 177 Wh/kg)
25. Pack specific energy as a design input: which cell (semi-solid 303 vs LiPo 200 Wh/kg) is planned? It swings the 15 m/s result by 4.4 kg
26. ~~3-blade for the tri and hex~~ (entry 21)
28. Is the 50 N / 1.2 mm flex test a per-blade handling spec, or should it scale with blade load? It alone decides the 3-blade case
27. ~~A less-cambered section (24xx)~~ (entry 22: hex +1.0 kg with 24xx full span, tri +0.25 kg with the 44/24 hybrid)
29. Camber sweep below 2 % (14xx, 00xx outboard) for the hex: the trend in entries 20–22 points to still less camber
30. Re-run the entry 14–19 chain (arms, speed, body, ranking) with the 24xx blades

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

## 15 — What the tip-Mach cap costs (2026-11-18)

**Question.** Entry 13 found the re-optimised tri sitting on the 0.60 tip-Mach cap at T/W 2 (hot day), while the hex's optimum sits at M 0.52, below it. How much payload does the cap cost each layout, and is 0.60 the right number?

**Method** (`src/explore/e15_tip_mach_cap.py`). The entry 13 (tri) and entry 11 (hex) optimisers are re-run with the cap at 0.50, 0.55, 0.60, 0.65 and 0.70, each starting from its own optimum; the motor and battery are in the objective throughout. Payload is measured against the Phase 2 tri, as in entries 10–13. **Caveat:** the XFOIL polar grid stops at M 0.60 and the lookup clips above it. Above 0.60 the tip keeps its M 0.60 drag, with no drag rise, so those rows are optimistic.

**Results.**

| Cap | Tri payload [kg] | Tri hover rpm | Tri σ | Tri Q_max [N·m] | Tri motor [kg] | Tri pack [Wh] | Hex payload [kg] | **Hex − tri [kg]** |
|---|---|---|---|---|---|---|---|---|
| 0.50 | −0.10 | 1783 | 0.160 | 60.3 | 5.39 | 7230 | +2.28 (M 0.50) | **+2.38** |
| 0.55 | +1.18 | 1962 | 0.150 | 54.7 | 4.89 | 7308 | +2.28 (M 0.50) | **+1.10** |
| 0.60 | +1.89 | 2141 | 0.143 | 50.6 | 4.52 | 7410 | +2.28 (M 0.52) | **+0.39** |
| 0.65* | +2.21 | 2327 | 0.138 | 47.0 | 4.21 | 7520 | (unchanged) | +0.07 |
| 0.70* | +2.25 (M 0.68, unbound) | 2443 | 0.135 | 45.4 | 4.07 | 7625 | (unchanged) | +0.03 |

\* polar clipped above M 0.60: optimistic.

**Finding.**
- **The cap is the tri's biggest lever, and the hex barely feels it.**
  - Tri: 0.71 kg of payload per 0.05 of cap between 0.55 and 0.60, and 1.3 kg between 0.50 and 0.55.
  - Hex: it carries half the thrust per rotor, so its optimum is set by the motor–battery balance, not by the cap. It loses nothing down to 0.50.
- **So the noise limit decides the payload ranking.** At 0.60 the hex leads by 0.4 kg, a tie within the ±0.9 kg uncertainty. At **0.55 it leads by 1.1 kg, and at 0.50 by 2.4 kg.** Above 0.60 the tri catches up, but only in the clipped-polar region (see the next point). Its own optimum unbinds near M 0.68.
- **0.60 is about where the physics stops the tri anyway.** The critical Mach of the tip section, from hand check 2, is 0.58–0.62 for the suction peaks it sees at T/W 2. Beyond that, shocks and drag rise would erode the +0.3 kg the clipped model shows at 0.65–0.70. **Keep 0.60 as the hard cap.** The real question (item 10) is whether noise wants a lower one, and every step down costs the tri, not the hex.
- **Hover tip speed (what people hear most):** tri 0.60 × 2141/2987 = **M 0.43**, hex 0.60 × 1784/2987 = **M 0.36**. The hex's rotors run 17 % slower in hover.

**Hand check 1: torque on the cap.** On the cap the top speed is fixed, Ω_cap = M·a/R, so Q_max = P_max/Ω_cap. If the figure of merit (and so P_max) stays put, Q_max ∝ 1/M:
- Q(0.55)/Q(0.60): hand 0.60/0.55 = **1.091**, model 54.7/50.6 = **1.082** ✓. The model's ratio is slightly lower because the optimiser widens the blade (σ 0.143 → 0.150), which raises FM a little at the lower tip speed.
- Motor mass m ∝ Q ∝ 1/M, so d(3m)/dM = −3m/M = −3 × 4.52/0.60 = **−22.6 kg per unit Mach**, against **−22.2** by finite difference ✓.
- **The payload budget per 0.05 of cap (0.55 → 0.60):** motors +1.11 kg, battery −(7410 − 7308)/303 = −0.34 kg (a faster rotor has more profile power), blades and ESCs −0.06 kg; net **+0.71 kg** ✓ (the model's slope is 14.2 kg/M). The same motor–battery trade as entry 11, but here the cap stops it before the two terms balance.

**Hand check 2: the critical Mach number of the tip section.** A section first goes sonic where its suction peak, corrected for compressibility, reaches the sonic pressure coefficient.
- **Kármán–Tsien correction** of the incompressible peak Cp₀: Cp = Cp₀ / [√(1−M²) + M²/(1+√(1−M²))·Cp₀/2].
- **Sonic Cp** from the isentropic relations: Cp* = 2/(γM²)·[((2 + (γ−1)M²)/(γ+1))^(γ/(γ−1)) − 1].
- Setting the two equal and solving for M:

| Cp₀,min (incompressible) | −0.6 | −0.8 | −1.0 | −1.2 |
|---|---|---|---|---|
| M_crit | 0.671 | 0.623 | 0.585 | 0.553 |

A 9 % thick cambered tip section at the high lift of T/W 2 has Cp₀,min of about −0.8 to −1.0, so **M_crit ≈ 0.58–0.62**. Drag divergence follows slightly above M_crit. That is why 0.60 is a sound hard cap, and why the polar grid stops there.

**Hand check 3: noise rule of thumb.** Rotational loading noise scales roughly as V_tip⁶ at constant thrust, so ΔSPL = 60·log₁₀(M₂/M₁):

| Cap | ΔSPL vs 0.60 |
|---|---|
| 0.50 | −4.8 dB |
| 0.55 | −2.3 dB |
| 0.65 | +2.1 dB |
| 0.70 | +4.0 dB |

For the tri, each 2.3 dB of quiet costs 0.71 kg of payload.

**Next.**
- **Queue item 8: cruise speed per configuration.** All layouts so far cruise at 15 m/s. The hex's low disk loading should move its best-range speed, and with it the energy lead.
- Then **item 21**, the consistent re-ranking with an uncertainty band. It should now include the cap as a scenario (0.55 / 0.60).

## 16 — Cruise speed per configuration (2026-11-18)

**Question.** Entries 01–15 all cruised at the 15 m/s design point. The mission is a fixed 10 nmi, so what matters is energy per metre, (P + P_avionics)/V, not power. Where is each layout's best-range speed, and does it change the ranking?

**Method** (`src/explore/e16_cruise_speed.py`). Each layout keeps its best design so far (blades from entries 11–13, arm option from entry 14). At each speed from 10 to 30 m/s:
- the trim is re-solved as in Phase 2: body drag (CdA 0.60 m²) plus rotor H-forces plus arm and mast drag set the shaft tilt;
- BEMT edgewise gives the power at that thrust and tilt;
- the y6's inter-rotor interference is scaled as 15/V, because induced power goes as T·v_i and v_i ∝ 1/V;
- the mission model gives the pack, with hover and climb from entry 14 and hardware unchanged (hover sizes the motors).

The advancing-tip Mach stays ≤ 0.53 and the largest section angle ≤ 8.4°, so there is no compressibility or retreating-side stall problem anywhere in the sweep. At 15 m/s the model is within 1 % of entry 14's packs: 7508 against 7436 Wh for the tri, 4903 against 4852 for the hex. The small difference is that arm drag now enters the trim instead of being added as D·V/0.8.

**Results** (10 nmi pack energy [Wh]):

| V [m/s] | 10 | 12 | 15 | 18 | 20 | 22 | 24 | 26 | 30 | **Best V** | **Best pack** | Gain vs 15 m/s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| tri | 11905 | 9606 | 7508 | 6371 | 5944 | 5702 | 5603 | 5621 | 5951 | **24.7** | **5596** | −25 %, +6.30 kg |
| hex | 7678 | 6142 | 4903 | 4357 | 4223 | 4220 | 4329 | 4540 | 5286 | **21.0** | **4207** | −14 %, +2.29 kg |
| y6 | 10393 | 8138 | 6313 | 5451 | 5181 | 5079 | 5114 | 5270 | 5929 | **22.5** | **5075** | −20 %, +4.08 kg |

**Finding.**
- **15 m/s is far below the best-range speed of every layout.** All three are best at 21–25 m/s. Flying there saves 14–25 % of the pack and also cuts the trip time by 30–40 %.
- **It reverses the payload ranking.** Each layout at its own best speed, with hardware from entries 11–14:

| Layout | Best V [m/s] | Pack [Wh] | Energy vs tri | Payload vs tri [kg] |
|---|---|---|---|---|
| **tri** | 24.7 | 5596 | — | **0** |
| hex | 21.0 | 4207 | **−25 %** | **−3.4** |
| y6 | 22.5 | 5075 | −9 % | −4.4 |

  - The tri gains the most from speed because its penalty is **induced power**, which falls with speed. With half the disk area, its induced velocity at 15 m/s is about twice the hex's (7.5 against 4.1 m/s).
  - The hex's penalties are **profile power** (twice the blade area: P₀ ≈ 1.6 against 1.0 kW) and **arm drag**, and both rise with speed.
  - At 15 m/s the hex's battery is 2584 Wh (8.5 kg) lighter, which more than pays for its 7.9 kg of extra frame, arms and motors (8.5 − 7.9 = +0.6 kg, entry 14). At best-range speed its battery saving shrinks to 1389 Wh = 4.6 kg, and the 7.9 kg hardware penalty wins.
- **What to take from it:**
  - **On payload at a free cruise speed, the tri leads by about 3.4 kg.** That is well outside the ±0.9 kg motor-fit band.
  - **On energy or range at equal payload, the hex still leads by 25 %.**
  - **If the 15 m/s design point is a hard requirement, entry 14's ranking stands.**
  - **The choice is now a requirements question, not an aerodynamics one** (queue item 23).
- **Caveats:**
  - The blades were optimised at 15 m/s. Re-optimising at each layout's own speed (item 23) will move all three, the tri most.
  - At 24 m/s the tri flies with 13° of shaft tilt, and CdA 0.60 m² is held fixed. A real fuselage's drag rises with pitch attitude (item 24).

**Hand check 1: the power-required curve.** Build it from three terms:

  P(V) = κ·W·v_i(V) + P₀·(1 + 4.65μ²) + ½·ρ·V³·f

- **Induced**, from the full Glauert inflow v_i = v_h²/√(V² + v_i²), with v_h = √(W/(2ρA_tot)) the hover value. **Lesson:** at 15 m/s these rotors are *not* in the high-speed limit v_i ≈ v_h²/V. The tri has v_h = 11.25 m/s, and the full solution gives v_i = 7.54 against 8.44 m/s from the limit formula. Using the limit, as the first version of this script did, overstates induced power by 12 %.
- **Profile:** P₀ = P_hover − κW^1.5/√(2ρA_tot), the hover power that is not induced, with the standard 1 + 4.65μ² growth (μ = V/ΩR).
- **Parasite:** f = CdA_body + arm-drag area.

| V [m/s] | 10 | 15 | 20 | 24 | 30 |
|---|---|---|---|---|---|
| tri, hand [kW] | 14.7 | 13.1 | 12.7 | 13.5 | 17.0 |
| tri, BEMT [kW] | 14.2 | 12.4 | 12.2 | 13.6 | 18.5 |
| hex, hand [kW] | 10.0 | 8.8 | 9.2 | 10.6 | 14.8 |
| hex, BEMT [kW] | 8.9 | 7.7 | 8.5 | 10.5 | 17.1 |

- **Agreement:** the hand curve tracks BEMT within 6 % for the tri up to 24 m/s, and within 13 % for the hex.
- **Where it drifts:** at low speed P₀ also carries the hover download and non-uniform inflow, so it is too high. At high speed the 4.65μ² term under-predicts the advancing-side drag growth.
- **Best speed:** minimising (P + P_av)/V by hand gives V* = 26.8 m/s for the tri and 23.4 for the hex, against 24.7 and 21.0 from BEMT. The ordering and the ≈ 3.5 m/s gap between the layouts are reproduced.
- **Why the hex is slower:** with only induced and parasite terms, d/dV[a/V² + ½ρfV²] = 0 gives V*⁴ = 2a/(ρf), where a = κW²/(2ρA_tot). Doubling the disk area halves a, so V* falls by 2^(1/4) = 1.19. That is the hex's lower best-range speed (22.5 against 26.6 m/s in that limit).
- **The y6 hand curve does not fit** (13.4 against 9.9 kW at 15 m/s). Its "profile" P₀ = 5.7 kW is really its coaxial hover interference, which does not grow with speed. The two-term split is only valid for isolated rotors.

**Hand check 2: the tri's 1.9 kWh saving.**
- Cruise time: 18 520 m / 15 m/s = 1235 s, against 18 520 / 24 m/s = 772 s.
- Cruise shaft energy: 12 355 W × 1235 s = 4239 Wh at 15 m/s, against 13 608 W × 772 s = 2918 Wh at 24 m/s.
- To electrical: 1321 Wh / (0.905 × 0.97) = 1505 Wh. Avionics: 150 W × 463 s = 19 Wh. Total 1524 Wh.
- To pack with the 20 % reserve: 1524 / 0.8 = **1905 Wh**, against 7508 − 5603 = **1905 Wh** from the model ✓.

**Next.** Queue item 23: re-optimise each layout's blade at its own best-range speed, with the motor in the objective. Hover sizing stays the same, so the hover blade trade from entries 11–13 now competes with a faster cruise point, and the tri's lead should be re-checked there. Then item 24: fuselage drag against pitch attitude, which caps how fast the tri can usefully go.

## 17 — Blades re-optimised for cruise at each layout's best-range speed (2026-11-18)

**Question.** Entry 16 moved every layout's cruise to 21–25 m/s, but each blade was still optimised for a 15 m/s cruise. With the cruise point at the layout's own best-range speed, does the blade change, and does the tri's 3.4 kg payload lead hold?

**Method** (`src/explore/e17_blade_at_best_speed.py`). Entry 11/13's optimiser, with the cruise point moved to each layout's best-range speed: tri 24.7 m/s, hex 21.0 m/s.
- At every evaluation the trim is re-solved for that blade (body CdA + rotor H-forces + arm force, as in entry 16).
- The rest is unchanged from entries 11–14: hover with entry 14's download, motor ∝ peak torque at T/W 2, ESC, spar blade mass, arms, fairing (hex), tilt servo (tri).
- Added constraint: largest cruise section angle ≤ 11°.
- The objective is hardware + battery mass (lower is better), and the layout difference is the payload difference.
- After optimising, the speed is swept again ±5 m/s.
- **Regression:** the start blades reproduce entry 16's packs at those speeds (5597 and 4206 Wh against 5596 and 4207).
- The y6 is left out: it trails at every speed, and its coaxial surrogate was built for 15 m/s.

**Results.**

| Layout | | Hover rpm | Cruise rpm | σ | Q_max [N·m] | Motor [kg] | Pack [Wh] | Hardware + battery [kg] | Best V after re-sweep |
|---|---|---|---|---|---|---|---|---|---|
| tri | 15 m/s blade | 2141 | 2018 | 0.140 | 50.6 | 4.53 | 5597 | 41.64 | 24.7 |
| tri | **re-optimised** | 2141 | 2034 | 0.123 | 50.7 | 4.53 | 5580 | **41.50** (−0.14) | 24.7 |
| hex | 15 m/s blade | 1783 | 1580 | 0.128 | 22.6 | 2.03 | 4206 | 44.76 | 21.0 |
| hex | **re-optimised** | 1821 | 1619 | 0.122 | 22.3 | 2.00 | 4224 | **44.69** (−0.07) | 21.0 |

**Finding.**
- **The blades barely change: −0.14 kg on the tri and −0.07 kg on the hex.** Each layout's blade is set by **hover sizing**, not by the cruise point:
  - the T/W 2 torque, through the motor (both layouts);
  - the tip-Mach cap (tri).

  Both re-optimised blades lose some inboard chord (lower σ), which a faster, lighter-loaded cruise can afford. Hover rpm and peak torque stay where entries 11 and 13 put them.
- **The ranking holds:** at its own best speed, **the tri carries 3.19 kg more payload than the hex**, and **the hex uses 24 % less energy** (4224 against 5580 Wh).
- **The best-range speeds don't move** (24.7 and 21.0 m/s): the speed optimum is just as flat as the blade optimum.
- **What this closes off:** a blade tuned for the cruise point can't reverse the speed effect. The design levers left are **requirements** (is 15 m/s a floor or a design point? range or payload?) and the **airframe** (fuselage drag at 13° pitch, item 24).

**Hand check: why the tri gains only 0.14 kg.**
- **Marginal value of cruise power.** At 24.7 m/s, cruise lasts 18 520/24.7 = 750 s. One watt of cruise shaft power costs 750/3600 h ÷ (0.905 × 0.97) ÷ 0.8 (reserve) ÷ 303.3 Wh/kg = **9.8×10⁻⁴ kg per W**.
- **What the new blade saves:**
  - 57 W of cruise power (13 989 → 13 933 W) is 0.056 kg;
  - 10 W of hover (17 120 → 17 111) is ≈ 0.002 kg;
  - a lighter blade and hub hardware, 23.191 → 23.104 kg, is 0.087 kg.
- **Total:** 0.056 + 0.002 + 0.087 = **0.145 kg** ✓ (the model gives 41.645 − 41.500 = 0.145 kg).
- **Why it's small:** a 4 % cut in cruise profile power is worth only about 0.06 kg. The blade's big terms (motor torque, battery for hover) were already balanced in entry 13, and the cruise point doesn't touch them.

**Next.** Queue item 24: fuselage drag against pitch attitude. At 24.7 m/s the tri flies with 13° of shaft tilt. A real fuselage's CdA rises with incidence (crossflow on the fuselage underside), which will pull the tri's best speed down and shrink its lead. That is the last physical term in the payload-at-free-speed comparison.

## 18 — Fuselage drag against pitch attitude (2026-11-18)

**Question.** Entries 16–17 held the body drag area at CdA₀ = 0.60 m² at every speed. A multirotor's fuselage pitches nose-down with its rotor shafts, though: about 13° for the tri at 24.7 m/s and 10° for the hex at 21 m/s. How much does the body's drag grow at that attitude? And does it undo the tri's payload lead at free cruise speed (entry 16)?

**Method** (`src/explore/e18_body_incidence.py`). There is no airframe geometry yet, so the study brackets the body with two models, written in terms of the body incidence α_b (shaft tilt minus any built-in nose-down pre-tilt):
- **Streamlined** (cross-flow theory, Allen–Perkins/Hoerner): only the velocity component normal to the body axis makes extra force. Normal force ∝ sin²α_b, and its drag component carries one more sin:
  f = f₀ + Cd_c·A_plan·|sin α_b|³, with A_plan = 1.2 m² and Cd_c = 1.0.
- **Bluff box:** the drag follows the projected frontal area:
  f = f₀·(cos α_b + r·sin α_b), with r = A_plan/A_front = 2.0 (A_front = 0.6 m² at Cd 1.0).
- **Bluff, pre-tilted:** the same box built 13° nose-down on the frame, so it is level at the tri's cruise attitude.

The trim is iterated with f(α), since more drag means more tilt and more tilt means more drag. Blades, hover, motors, arms and fairings are all as in entry 17. Speeds 14–30 m/s.

**Results** (hardware + battery: lower is more payload):

| Body model | Tri best V [m/s] | Tri tilt | Tri f [m²] | Tri pack [Wh] | Tri hw + batt [kg] | Hex best V | Hex f | Hex pack | Hex hw + batt | **Hex − tri payload, free speed** | Hex − tri at 15 m/s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| constant (entries 16–17) | 24.8 | 13.5° | 0.600 | 5581 | 41.50 | 21.1 | 0.600 | 4225 | 44.69 | **−3.19** | +0.86 |
| streamlined | 24.3 | 13.2° | 0.614 | 5628 | 41.65 | 20.9 | 0.606 | 4240 | 44.74 | **−3.09** | +0.86 |
| bluff box | 21.2 | 13.2° | 0.857 | 6345 | 44.01 | 18.6 | 0.798 | 4679 | 46.17 | **−2.16** | +0.83 |
| bluff, pre-tilted 13° | 24.1 | 12.9° | 0.607 | 5609 | 41.57 | 22.3 | 0.630 | 4326 | 45.02 | **−3.45** | +0.81 |

**Finding.**
- **A streamlined body barely notices its pitch attitude:** +0.014 m² at 13°, 0.15 kg on the tri. The sin³ makes small incidences nearly free.
- **A bluff body costs a lot.**
  - **Tri:** +43 % drag area at 13°, best-range speed down 3.6 m/s, **2.5 kg** of payload lost.
  - **Hex:** it flies slower and at a shallower tilt, so it loses **1.5 kg**.
  - **The lead:** the tri's free-speed lead shrinks from 3.2 to **2.2 kg**, but **the ranking holds**.
- **Building the body nose-down at the cruise attitude recovers almost all of it.** That is a cheap, real design rule: the tri gets back to 41.57 kg, within 0.07 kg of the constant-drag case.
  - The 13° pre-tilt suits the tri but over-tilts the hex, whose cruise tilt is about 10°. Each layout would pick its own angle, and at 10° the hex would land near its constant-drag 44.7 kg.
  - The cost is hover and ground attitude: the body sits 13° nose-up in hover. That matters for landing gear, payload release, and download on the body's sloped underside.
- **At the 15 m/s design point the body model hardly matters.** The tilt there is only about 6° (hex ahead by 0.8–0.9 kg in all four cases).
- **Summary of where the layout choice stands:**

| Requirement | Winner | Margin |
|---|---|---|
| Fly at the 15 m/s design point | hex | +0.8 kg (≈ the ±0.9 kg uncertainty), −35 % energy |
| Cruise speed free (≥ 15 m/s), payload | **tri** | +2.2 kg (bluff body) to +3.4 kg (pre-tilted) |
| Cruise speed free, range at equal payload | **hex** | −23 to −26 % energy |
| Stricter noise cap (≤ 0.55) | **hex** | +1.1 kg or more at 15 m/s (entry 15) |

**Hand check 1: drag-area growth.**
- **Bluff model** at the tri's best-speed tilt of 13.2°: f/f₀ = cos 13.2° + 2·sin 13.2° = 0.974 + 0.457 = **1.430**, so f = 0.600 × 1.430 = **0.858 m²** ✓ (the model gives 0.857).
- **Streamlined model** at 13°: Cd_c·A_plan·sin³13° = 1.0 × 1.2 × 0.01138 = **0.0137 m²** ✓.

**Hand check 2: why the best speed falls more than the −1/4 law predicts.**
- **The simple estimate.** In the induced/parasite limit (entry 16), V*⁴ = 2a/(ρf). A 43 % larger f should lower V* by 1.430^(−1/4) = 0.915, from 24.8 to **22.7 m/s**. The model gives **21.2 m/s**.
- **The missing feedback:** here f is not a constant. It grows with speed, because the tilt grows as tan α = D/W.
- **Why that lowers V\*:** minimising P/V = a/V² + ½ρf(V)V² gives

    d/dV(P/V) = −2a/V³ + ρfV + ½ρV²·df/dV = 0.

  The extra term ½ρV²·df/dV is positive, so the optimum comes at a lower speed than with f held fixed.
- **Lesson:** in a trimmed vehicle, drag and attitude are coupled, and a fixed-CdA analysis overstates the best cruise speed of any bluff multirotor.

**Next.** Queue item 21: the consolidated layout ranking, with the uncertainty bands collected from entries 10–18 (motor fit ±0.9 kg, body model, tip-Mach cap, speed requirement) in one table and plot. Then items 9 (camber) and 6 (3-blade), the two blade ideas still untried.

## 19 — Consolidated tri vs hex ranking, with the uncertainty bands (2026-11-18)

**Question.** Entries 10–18 each moved the tri–hex payload comparison by a kilogram or more. Which way does it fall across the open requirements and assumptions, and what single number would settle it?

**Method** (`src/explore/e19_ranking.py`). No new aerodynamics. Entry 18 already holds, for both layouts and all four body models, the hardware mass and the pack energy at every cruise speed from 14 to 30 m/s. Those rows include entry 17's blades, entry 14's arms and fairings, hover download, and torque-sized motors. The payload difference is

  Δpayload (hex − tri) = −(Δhw + Δpack / e_b),  e_b = pack specific energy [Wh/kg].

It is evaluated over four axes:
- **speed:** 15 m/s, or free (each layout at its own best speed);
- **body:** constant, streamlined, bluff, or bluff pre-tilted (entry 18);
- **battery:** 303.3 Wh/kg (the vendor's semi-solid pack) or 200 Wh/kg (conventional LiPo, from params);
- **tip-Mach cap:** 0.60, or 0.55 (entry 15: +0.71 kg against the tri).

The band is the motor-mass fit from entry 10, −0.89 / +0.21 kg on the hex.

**Results** (hex payload minus tri payload [kg]; motor-fit band in brackets; cap 0.60 unless noted):

| Speed | Body | 303 Wh/kg | 200 Wh/kg | Energy hex vs tri | Break-even e_b |
|---|---|---|---|---|---|
| 15 m/s | (any, ±0.06) | **+0.86** [−0.02, +1.07] | **+5.27** [+4.38, +5.48] | −34 % | **338 Wh/kg** |
| 15 m/s, cap 0.55 | | **+1.57** [+0.69, +1.78] | +5.98 | −34 % | 372 |
| free | constant | **−3.19** [−4.08, −2.98] | **−0.88** [−1.77, −0.67] | −24 % | **177** |
| free | streamlined | −3.09 | −0.73 | −25 % | 181 |
| free | bluff | −2.16 [−3.05, −1.95] | **+0.68** [−0.21, +0.89] | −26 % | 217 |
| free | bluff pre-tilted | −3.45 | −1.27 | −23 % | 167 |
| free, cap 0.55 | constant | −2.48 | −0.17 [−1.06, +0.04] | −24 % | 195 |

**Finding.**
- **The speed requirement decides it.**
  - **At the 15 m/s design point, the hex wins** for any pack below **338 Wh/kg**. That covers every pack available today, though at the vendor's 303 Wh/kg only by +0.9 kg, inside the band.
  - **With cruise speed free, the tri wins** for any pack above **177 Wh/kg**, by 2–3.5 kg at 303 Wh/kg.
  - Every realistic pack sits between those two break-evens. So for 180–330 Wh/kg packs, **the answer is set by the speed requirement alone**.
- **The battery is the second lever.**
  - At 200 Wh/kg the hex's 34 % energy saving is worth 4.4 kg more than at 303 Wh/kg. At 15 m/s that makes the hex **+5.3 kg**, outside every band.
  - Even at free speed it brings the race back to within a kilogram. With a bluff body the hex then wins by +0.7 kg.
  - **The planned cell chemistry is now a first-order input** (queue item 25).
- **The noise cap and the body shape each move the result by about 1 kg.** Each can flip a near-tie but not a clear result. Every margin above 2 kg survives the motor-fit band.
- **The hex always uses 23–34 % less energy.** If the requirement is range at fixed payload, the hex wins under every assumption.

**Hand check 1: the break-even specific energy.** The hex carries heavier hardware (Δhw = +7.66 kg: six motors, ESCs and longer arms, against the tri's three motors and tilt servo) and a smaller pack (Δpack < 0). The two tie when the battery saved weighs exactly the extra hardware, Δpack/e_b = −Δhw, so

  e_b* = −Δpack / Δhw.

- **15 m/s:** 2586 / 7.66 = **337.6 Wh/kg** ✓ (the curve's zero crossing is at 337.6).
- **Free speed:** 1357 / 7.66 = **177.2 Wh/kg** ✓ (177.1).
- **Reading it:** below e_b* each Wh is heavy, so the layout that saves energy (the hex) wins; above it, the layout with lighter hardware (the tri) wins.
- **Cap 0.55:** the tri's hardware grows by 0.71 kg, so Δhw = 6.95 kg and e_b* = 2586 / 6.95 = 372 Wh/kg ✓.

**Hand check 2: why the best speed does not depend on the battery.** The objective is hw + pack(V)/e_b. Hardware is sized by hover and does not depend on V, so

  d/dV[hw + pack/e_b] = (1/e_b)·d(pack)/dV = 0  ⇔  d(pack)/dV = 0,

and the best-range speed is the minimum-pack speed for any e_b. The 200 Wh/kg runs land on the same 24.8 and 21.1 m/s ✓. That would change only if hardware depended on speed, for example motors sized by a fast-cruise power instead of by hover torque.

**Recommendation.**
- **The two inputs that settle the layout are the 15 m/s requirement (a design point, or a minimum?) and the planned pack chemistry.** Both are for the project owner.
- Until they are fixed, the hex is the safer choice. It wins or ties at the stated design point for every pack, and it always has the range.
- The tri is the payload choice only if the vehicle is allowed to cruise at 21–25 m/s and the body is pre-tilted or streamlined.

**Next.**
- Queue item 9: camber for the blades. The blade trade study found camber pays mostly in cruise, and entry 17 showed cruise is the weak lever, so this is a quick check.
- Then item 6 (3-blade rotors), the last blade idea still untried. Both now get run for the tri as well (item 26).

## 20 — Camber with torque-sized motors (2026-11-18)

**Question.** The Phase 2 blade uses NACA 44xx (4 % camber at 40 % chord). The blade trade study found that more camber (64xx) pays mostly in cruise. With the motor now in the objective (entries 11 and 13), does a more cambered section still help, for the tri or the hex?

**Method** (`src/explore/e20_camber.py`). Entries 11 (hex) and 13 (tri) are re-run with two other section families, starting from their 44xx optima, at the 15 m/s design point:
- **64/44 hybrid:** 6 % camber where t/c ≥ 15 % (inboard), 4 % where t/c ≤ 12 %, blended between, as in the blade trade study.
- **64xx:** 6 % camber over the whole span.

The XFOIL 64xx polars come from the blade trade study's cache, on the same Re/Mach grid. Seven of the 80 cases are only partly converged (9–31 points), and the interpolant bridges them. Payload is scored on the same absolute bookkeeping as entries 11 and 13: the tri against its 44xx reference, the hex against the Phase 2 tri.

**Results** (payload change against each layout's 44xx optimum):

| Layout | Section | Hover rpm | σ | Q_max [N·m] | Motor [kg] | Blade [kg] | Pack [Wh] | **Δ payload [kg]** |
|---|---|---|---|---|---|---|---|---|
| tri | 44xx (entry 13) | 2141 | 0.140 | 50.6 | 4.53 | 0.475 | 7422 | 0 |
| tri | 64/44 hybrid | 2142 | 0.135 | 50.9 | 4.55 | 0.471 | 7453 | **−0.14** |
| tri | 64xx | 2146 | 0.142 | 51.2 | 4.58 | 0.529 | 7554 | **−0.93** |
| hex | 44xx (entry 11) | 1783 | 0.128 | 22.6 | 2.03 | 0.451 | 5113 | 0 |
| hex | 64/44 hybrid | 1774 | 0.128 | 22.8 | 2.05 | 0.451 | 5131 | **−0.18** |
| hex | 64xx | 1646 | 0.130 | 24.3 | 2.18 | 0.454 | 5177 | **−1.14** |

**Finding.**
- **Camber loses on both layouts. Keep 44xx.** The hybrid costs about 0.15 kg. Full-span 64xx costs about 1 kg, through both a larger pack and a heavier motor.
- **Why, in one line:** a cambered section is best at a high lift coefficient, but **torque-sized motors push the rotor to spin fast at a low lift coefficient**.
  - At the optimum, the sections run at Cl ≈ 0.6–0.9. There the 64xx has **13–36 % more drag** than the 44xx (hand check 2).
  - The alternative is to let the 64xx run at its own best Cl, which slows the rotor. On the hex 64xx that drops hover to 1646 rpm, and the torque and motor mass rise (+0.15 kg per rotor).
- **This reverses the blade trade study's lean towards camber.** That study held the motor fixed, which is the same "what the objective holds fixed is free" lesson as entries 03 and 11.
- **The opposite direction may pay:** a *less* cambered outboard section (24xx) whose drag bucket sits at Cl 0.6–0.8 (queue item 27).

**Hand check 1: thin-airfoil zero-lift angle.** For the NACA 4-digit camber line (maximum camber m at chord position p), dz/dx = (2m/p²)(p − x) forward of p and (2m/(1−p)²)(p − x) aft of it. With x = ½(1 − cos θ),

  α_L0 = −(1/π) ∫₀^π (dz/dx)(cos θ − 1) dθ.

- **44xx:** α_L0 = **−4.15°** (the published NACA 4412 value is about −4.0°).
- **64xx:** α_L0 = **−6.23°**.

α_L0 is linear in m, so the extra 2 % of camber is equivalent to **2.08° more pitch** at the same geometric twist.

**Hand check 2: the drag at the lift where the rotor runs.** From the polars at Re 6×10⁵, M 0.30:

| Cl | 44xx t/c 9 % | 64xx t/c 9 % | 44xx t/c 12 % | 64xx t/c 12 % |
|---|---|---|---|---|
| 0.6 | 0.00620 | 0.00843 (+36 %) | 0.00706 | 0.00929 (+32 %) |
| 0.8 | 0.00727 | 0.00811 (+12 %) | 0.00799 | 0.00942 (+18 %) |
| 1.0 | 0.00853 | 0.00821 (−4 %) | 0.00914 | 0.00940 (+3 %) |
| best Cl^1.5/Cd | 122.7 at Cl 1.11 | **150.6** at Cl 1.44 | 124.4 at Cl 1.22 | **142.5** at Cl 1.49 |

- **Where 64xx wins:** at its own best point, by about 20 % on Glauert's hover section figure Cl^1.5/Cd. That figure is the right one when the rpm is free and nothing else costs. Profile power at fixed thrust goes as σ·Cd with σ ∝ 1/Cl (C_T = σ·Cl/6), and induced power is fixed.
- **Where it loses:** only above Cl ≈ 1.0. Running a blade at Cl 1.4 means a slower rotor and more torque, which the motor term forbids.

**Hand check 3: the torque cost of the extra camber at fixed geometry.** At fixed thrust, the 64xx start blade (the 44xx optimum's geometry) behaves as if pitched up 2.08°, so it trims at lower rpm. Shaft power is mostly induced and barely changes, so

  Q = P/Ω ∝ 1/Ω,  hand Q₆₄/Q₄₄ = 1783/1574 = **1.13**, model 25.07/22.62 = **1.11** ✓.

The optimiser then strips the extra pitch back out (hover 1574 → 1646 rpm). That puts the sections at low Cl, where the 64xx section drags more, and leaves the blade worse than the 44xx at either end.

**Next.** Queue item 6 / 26: 3-blade rotors for the tri and hex. A third blade at the same solidity lowers the tip-loss factor and the hub vibration (3P), at the cost of a heavier hub and narrower chords, which are harder on the spar model.

## 21 — 3-blade rotors with torque-sized motors (2026-11-18)

**Question.** A third blade at the same solidity cuts tip loss and moves the hub vibration from 2P to 3P. The blade trade study saw no energy gain, but it held the motor fixed. With the motor and the spar model in the objective, does a 3-blade rotor pay on the tri or the hex?

**Method** (`src/explore/e21_three_blade.py`). Each layout's 2-blade optimum (entries 11 and 13) is the start, with N = 3 and the chord scaled by 2/3, so the solidity and C_T/σ are unchanged. It is then re-optimised with the entry 11/13 optimisers at 15 m/s. For three blades the bookkeeping adds:
- the third blade (spar model, each blade passing the 50 N / 1.2 mm flex test of params `structure_prelim`, plus its own root fitting);
- 0.10 kg of hub per rotor for the third grip and pitch link (an assumption).

The script also prints the cruise hub-load ripple with blade_trade_study's `hub_ripple`, which superposes one blade's azimuthal loads at N phase offsets.

**Results.**

| Layout | Blades | Hover rpm | σ | Blade [kg each] | Q_max [N·m] | Motor [kg] | Pack [Wh] | FM | Payload change [kg] | Hub roll ripple [N·m] | Thrust ripple [N] |
|---|---|---|---|---|---|---|---|---|---|---|---|
| tri | 2 (entry 13) | 2141 | 0.140 | 0.475 | 50.6 | 4.53 | 7422 | 0.833 | 0 | 54.3 (2P) | 29.0 |
| tri | 3, same σ (start) | 2125 | 0.140 | **0.936** | 50.4 | 4.51 | 7477 | 0.840 | −5.97 | | |
| tri | **3, optimised** | 2123 | **0.198** | 0.460 | 52.7 | 4.72 | 7426 | 0.804 | **−2.22** | **6.1 (3P)** | **1.6** |
| hex | 2 (entry 11) | 1783 | 0.128 | 0.451 | 22.6 | 2.03 | 5113 | 0.789 | 0 | 31.8 (2P) | 20.1 |
| hex | 3, same σ (start) | 1771 | 0.128 | **0.777** | 22.7 | 2.03 | 5194 | 0.787 | −9.46 | | |
| hex | **3, optimised** | 1577 | **0.191** | 0.445 | 25.7 | 2.30 | 4933 | 0.781 | **−4.26** | **4.6 (3P)** | **0.9** |

**Finding.**
- **The 3-blade rotor loses heavily: −2.2 kg on the tri, −4.3 kg on the hex. Keep two blades.**
- **The cause is structural, not aerodynamic.**
  - The flex test is a **per-blade** bench requirement: 50 N at the tip, at most 1.2 mm of deflection. A blade with 2/3 of the chord and the same t/c has a spar about 2/3 as deep, and EI ∝ depth². To stay stiff it needs about twice the spar: blade mass **0.475 → 0.936 kg**.
  - The optimiser escapes by **widening each blade back to nearly the 2-blade chord**, which gives σ 0.20. The blades are then light again (0.46 kg each), but the rotor now carries 40 % more blade area. That costs profile power (FM 0.83 → 0.80), and on the hex it costs torque too.
  - On top of that come one extra blade, its root fitting and a heavier hub per rotor: 3 × 0.56 kg on the tri and 6 × 0.55 kg on the hex.
- **It is still a ride-quality win:** hub roll ripple falls **−89 %** (54 → 6 N·m) and thrust ripple −95 %. Those are the 2P loads a 2-blade rotor passes to the airframe in forward flight (hand check 2). If vibration or camera stability becomes a requirement, the price is about 2 kg on the tri.
- **The answer depends entirely on one requirement** (queue item 28). If the 50 N bench load stood for *blade load*, it would scale with thrust per blade (×2/3 for three blades) and the 3-blade spar penalty would mostly vanish. That is a question for whoever owns the test spec.

**Hand check 1: tip loss against Reynolds number at equal solidity.** Prandtl's effective-radius tip loss is R_e/R = 1 − √(2C_T)/B, and ideal induced power at fixed thrust goes as 1/R_e.
- **Tri:** C_T = 415 / (1.109 × 1.478 × 153.8²) = 0.0107, so √(2C_T) = 0.146. Then P_i3/P_i2 = (1 − 0.073)/(1 − 0.049) = **0.974**: a 2.6 % induced-power saving, **−120 W** per rotor.
- **BEMT at the same σ:** only **−50 W**.
- **The difference is the narrower chord's Reynolds number.** Re drops by 2/3, and turbulent-ish section drag goes as Re^(−0.2), so Cd rises by (3/2)^0.2 = 1.084. Profile power is (1 − FM) × P ≈ 0.17 × 5588 = 950 W per rotor, so the 8.4 % rise is **+80 W**. Net −120 + 80 = **−40 W**, against BEMT's −50 W ✓.
- **Hex:** lower C_T means less tip loss to recover (−36 W). The Re penalty, 0.21 × 2094 × 0.084 = +37 W, cancels it. Net ≈ 0, against BEMT's +6 W ✓.
- **So at this size a third blade has no aerodynamic payoff.**

**Hand check 2: why the ripple collapses.** One blade's loads in forward flight vary around the azimuth as a Fourier series in ψ. With N equally spaced blades, the hub sum Σₖ f(ψ + 2πk/N) cancels every harmonic except multiples of N. So a 2-blade rotor passes 2P, 4P, …, a 3-blade rotor passes 3P, 6P, …, and a blade's load harmonics fall off quickly with order (roughly as μⁿ). The model's 2P → 3P drop of about 9× in roll ripple and 18× in thrust ripple is that fall-off.

**Next.** Queue item 27: a less-cambered outboard section (24xx). Entry 20 found the motor-sized optimum runs at Cl 0.6–0.9, below the 44xx drag bucket, so the next airfoil to try goes the other way from 64xx. That needs new XFOIL polars, which are light runs but must wait if a foamRun is active.

## 22 — Less camber outboard: NACA 24xx (2026-11-18)

**Question.** Entry 20 found that torque-sized motors push the blade to spin fast at low lift (Cl ≈ 0.6–0.9), where the more cambered 64xx drags more than the baseline 44xx. Does a *less* cambered section, whose low-drag range sits lower, pay?

**Method** (`src/explore/e22_less_camber.py`).
- **New polars:** XFOIL for NACA 24xx (2 % camber at 40 % chord), t/c 9–18 %, on the 44xx Re/Mach grid. All 80 cases converged in 5 min on 4 cores; no foamRun was active. They are cached in `results/polars`.
- **Same optimisers and bookkeeping as entry 20** (motor in the objective, 15 m/s design point, start from the 44xx optima). Two families:
  - **44/24 hybrid:** 4 % camber where t/c ≥ 15 % (the thick inboard part), 2 % where t/c ≤ 12 %.
  - **24xx:** 2 % camber over the whole span.
- **Extra check:** the retreating-side stall margin in cruise, because 24xx stalls earlier (Cl_max 1.21 against 1.39 at t/c 9 %).

**Results** (payload change against each layout's 44xx optimum):

| Layout | Section | Hover rpm | σ | Q_max [N·m] | Motor [kg] | Pack [Wh] | Hover stall margin | Cruise stall margin (15 / 21 m/s) | **Δ payload [kg]** |
|---|---|---|---|---|---|---|---|---|---|
| tri | 44xx (entry 13) | 2141 | 0.140 | 50.6 | 4.53 | 7422 | 10.3° | 6.5° / 6.2° | 0 |
| tri | **44/24 hybrid** | 2135 | 0.151 | 50.6 | 4.53 | 7367 | 8.3° | 5.7° / 5.8° | **+0.25** |
| tri | 24xx | 2136 | 0.156 | 50.7 | 4.53 | 7375 | 8.3° | 5.8° / 6.2° | +0.16 |
| hex | 44xx (entry 11) | 1783 | 0.128 | 22.6 | 2.03 | 5113 | 12.6° | 7.4° / 7.9° | 0 |
| hex | 44/24 hybrid | 1926 | 0.129 | 20.9 | 1.88 | 5119 | 9.4° | 7.1° / 8.0° | +0.94 |
| hex | **24xx** | 1973 | 0.131 | 20.5 | 1.84 | 5139 | 9.4° | 7.1° / 8.0° | **+1.03** |

**Finding.**
- **Less camber pays, on the hex in particular: +1.0 kg** with 24xx over the whole span. The hex rotor spins 11 % faster in hover (1783 → 1973 rpm) and needs 9 % less peak torque. That makes each of its six motors 0.19 kg lighter (−1.15 kg), for only +26 Wh of pack (+0.09 kg).
- **The tri gains only +0.25 kg** (44/24 hybrid). It is already on the tip-Mach cap (entry 13), so it cannot spin faster. Its gain is in the pack (−55 Wh), from lower profile drag at its operating Cl, not in the motor.
- **This reverses entry 20's "keep 44xx".** Within the families tried (2, 4 and 6 % camber), the motor-sized optimum wants the **least** camber. The rule is: **pick the section whose drag bucket sits at the Cl the motor-sized rotor wants to run at**, and with torque-sized motors that Cl is low.
- **Stall margins stay healthy.** The lowest is 5.7° on the retreating side in cruise (tri hybrid) and 8.3° in hover. The lower Cl_max of 24xx costs about 2° of hover margin, which the faster rotor doesn't need.
- **Effect on the ranking** (estimate; the speed/body chain of entries 16–19 is not re-run, queue item 30):
  - At 15 m/s the hex lead grows by 1.03 − 0.25 = +0.78 kg, to about **+1.6 kg**. That is now outside the motor-fit band (lower edge ≈ +0.8 kg).
  - At free speed the tri's lead shrinks from 3.2 to about 2.4 kg.

**Hand check 1: zero-lift angle and effective pitch.** Thin-airfoil theory (entry 20's integral) for the 24xx line gives α_L0 = **−2.08°**, against −4.15° for 44xx. At the same geometric twist, the 24xx blade has **2.08° less effective pitch**, so it trims faster at the same thrust. The model's start blades show it: the hex start (44xx geometry, 24xx sections) already gained +0.74 kg, at higher rpm, before the optimiser moved anything.

**Hand check 2: where the motor saving comes from.** At fixed thrust and roughly fixed power (induced-dominated), Q = P/Ω ∝ 1/Ω:
- hand Q₂₄/Q₄₄ = 1783/1973 = **0.904**, so Q = 22.6 × 0.904 = **20.4 N·m**, against the model's **20.5** ✓;
- motor mass at 0.0909 kg/(N·m) (entry 10): 6 × 0.0909 × (22.6 − 20.5) = **1.15 kg** ✓, as in the table.

**Hand check 3: why 44xx couldn't just spin faster.** At the same section drag table (Re 6×10⁵, M 0.30):

| Cl | 44xx t/c 9 % | 24xx t/c 9 % | 44xx t/c 12 % | 24xx t/c 12 % |
|---|---|---|---|---|
| 0.4 | 0.00632 | **0.00560** (−11 %) | 0.00821 | **0.00666** (−19 %) |
| 0.6 | **0.00620** | 0.00682 (+10 %) | **0.00706** | 0.00743 (+5 %) |
| 0.8 | **0.00727** | 0.00941 (+29 %) | **0.00799** | 0.00869 (+9 %) |
| Cl_max | 1.39 | 1.21 | 1.46 | 1.31 |

- **Below Cl ≈ 0.5, the 44xx's drag climbs** (it leaves its low-drag range on the low side), while the 24xx's is lowest there.
- So a 44xx rotor that spins faster pays in profile drag, and the optimiser stopped at 1783 rpm. The 24xx moves the low-drag range to Cl ≈ 0.4, and the faster, lighter-motor rotor then costs almost nothing in drag.
- This is the same logic as entry 20, in the other direction.

**Next.** Queue item 29: does still less camber (14xx, or a symmetric 00xx outboard) keep paying on the hex? The trend says the hex wants Cl ≈ 0.4 sections. Then item 30: re-run the arms, speed, body and ranking chain (entries 14–19) with the 24xx blades, so the layout table uses the best blades.


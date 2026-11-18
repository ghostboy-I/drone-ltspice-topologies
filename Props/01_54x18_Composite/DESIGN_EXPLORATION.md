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
2b. **Blade structure and mass model.** Entry 02's payload gain comes from blade mass ∝ volume. Add a fixed part (spar, root fitting, erosion strip) and the 50 N / 1.2 mm flex requirement as a constraint, then re-run entries 01–02.
3. Different upper and lower blades: the lower rotor works in the upper wake inboard, so it wants more pitch there
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

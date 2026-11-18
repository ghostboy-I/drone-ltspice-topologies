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
2. Two-point (hover + cruise) refinement of the coaxial blade: Phase 2's refinement gained 1.9 % on the single rotor
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

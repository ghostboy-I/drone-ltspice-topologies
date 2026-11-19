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
10. ~~Tip speed and noise~~ (entry 27: the hex is 6–7 dBA quieter in tonal loading noise; quieting the tri to match costs it > 2 kg, which removes most of its free-speed lead)
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
29. ~~Camber sweep below 2 % (14xx, 00xx outboard)~~ (entry 23: 2 % is the optimum; 14xx −0.11 kg, 00xx −0.94 kg on the hex vs 24xx; tri prefers 44/24)
30. ~~Re-run the entry 14–19 chain with the best-camber blades~~ (entry 24: hex leads by +1.73 kg at 15 m/s, now outside the motor-fit band; tri leads by 2.2 kg at free speed; break-even batteries 382 / 204 Wh/kg)
31. ~~A section designed for Cl ≈ 0.3 (NACA 230xx)~~ (entry 25: −1.1 kg hex, −0.9 kg tri vs 24xx; its forward camber peak moves transition from 76 % to 37 % chord. 24xx's bucket is already at Cl 0.25–0.30)
32. ~~Camber further aft at 2 % (NACA 25xx, 26xx)~~ (entry 26: 25xx ties 24xx (−0.04 / −0.00 kg), 26xx −0.2 kg; upper-surface transition moves aft but the lower surface's moves forward and cancels it)
34. ~~A noise-constrained ranking~~ (entry 28: at the hex's own hover level the tri loses 2.8 kg and the hex wins every scenario; with the 303 Wh/kg pack at free speed the tri wins only if the limit is looser than 40.6–43.5 dBA)
35. ~~Broadband rotor noise scaling~~ (entry 29: on trailing-edge scaling the tri is 1.0 dB *quieter* than the hex at cap 0.60, though 7 dBA louder in tones; which one dominates decides what a noise limit costs)
36. ~~Absolute broadband level (BPM TBL-TE)~~ (entry 30: broadband sets the dBA for both layouts; total hex 49.8 against tri 52.0 dBA; equal total noise costs the tri 1.9 kg, so the tri keeps a narrow free-speed lead at 303 Wh/kg with a constant or streamlined body)
37. ~~Tip-vortex formation noise (BPM section 5.3)~~ (entry 31: from negligible to +2.4 dBA on the tri depending on how the tip angle is defined; the hex moves at most 0.5 dB; with flat tips the tri cannot reach the hex's level within cap 0.45)
38. Leading-edge noise from the rotor ingesting its own recirculating wake turbulence in hover (Amiet's model). This needs a turbulence intensity and length scale for the ingested flow, from the literature or from the toroid CFD case's hover field
39. ~~Tip chord bound with flat or rounded tip~~ (entry 32: a bounded tip chord does not help. Loading per unit span is fixed by thrust, so a narrower outboard blade runs at a higher α* and its trailing-edge noise rises more than its tip noise falls. The rounded tip itself is the lever)
40. ~~Trailing-edge serrations~~ (entry 33: at a hex-level noise limit, serrations cut the tri's noise cost from 2.15 kg to 0.16–0.95 kg, so the tri regains a 1.2–2.0 kg free-speed lead at 303 Wh/kg; under tighter limits both layouts need them and the hex quiets more cheaply)
42. Serration effectiveness for this rotor: the bracket D = 2–6 dB spans the payload answer. A BPM-compatible serration model calibrated on published rotor data (Lyu–Azarpeyvand theory or a measured propeller test) would narrow it
41. ~~Wider blade for low α*~~ (entry 34: at the same tip speed, a 15–50 % wider chord cuts the tri's total by only 0.3–0.7 dBA at 0.6–2.7 kg/dB, and the hex's by at most 0.3 dBA. The angle term falls, but the thicker boundary layer raises the suction- and pressure-side terms. Not worth it next to serrations at about 0.1 kg/dB)
33. ~~Laminar-flow section from coordinates~~ (entry 35: NACA 24xx-64 gains the hex 0.34 kg and the tri 0.06 kg; 24xx-65 loses 0.4–0.6 kg. Aft thickness pays above Re ≈ 7 × 10⁵ and costs below it, and this rotor sits at that crossover)
43. ~~Section by spanwise Reynolds number~~ (entry 36: banding the -64 to 0.45–0.93R changes nothing, −0.03 kg; the -65 band still loses. The -64's gain comes from lower drag at T/W 2, where Re is higher, through a lighter torque-sized motor, and not from mission energy)
45. A section designed for the T/W-2 point: entry 36 shows the motor-sizing condition, at about 1.4 × hover rpm and Re ≈ 1.1 × 10⁶, is where section drag pays on the hex. A true 6-series (63-2xx/64-2xx, Theodorsen mapping) or an XFOIL inverse design centred on C_l ≈ 0.35 at Re 1.1 × 10⁶ could push this further; worth it only if the motor model's torque exponent (≈ 1) holds
46. ~~Motors between 18 and 50 N·m~~ (entry 38: real 24S motors fill the gap at 0.057–0.064 kg/N·m, against the fit's 0.090. The hex on the T-Motor MN1123 (1.425 kg, 22.2 N·m) gets +6.37 kg; the tri on the Hobbywing V13828 (2.465 kg, 43.1 N·m) gets +6.87 kg, but only by lifting its cap to 0.70. At 15 m/s the layouts are tied (hex +0.06 kg), and at equal noise the hex wins by 7.4 dBA. Both optima use 100 % of the motor's test-point torque.)
47. ~~Torque margin on catalogue motors~~ (entry 39: with a 12 % reserve the hex on the MN1123 drops to +5.06 kg at 50.8 dBA; the tri on the V13828 needs tip Mach 0.84 at T/W 2 for +4.37 kg at 61.4 dBA. The hex leads by ≈ 1.2 kg and is 10.5 dBA quieter. The free-speed and 200 Wh/kg scenarios are still open, now item 50.)
48. **Equal-noise comparison with the V13828 tri:** the tri's catalogue gain needs tip Mach 0.70 and costs it 3.8 dBA (52.1 → 55.9). Compare the tri at the hex's 48.5 dBA (serrations from entry 33, or a lower cap with the U15XL) against the hex on the MN1123.
49. ~~Tri on the U15XL with the 12 % reserve~~ (entry 40: +1.68 kg at 55.5 dBA, cap 0.70; it trades 2.7 kg for 5.9 dB against the V13828 tri. The hex on the MN1123, +5.06 kg at 50.8 dBA, beats every tri variant on payload *and* noise.)
51. **Hex payload against noise between the MN1123 and the MN1320** (entry 40): MN1123 with the reserve, +5.06 kg at 50.8 dBA; MN1320, +2.95 kg at 46.3 dBA (0.47 kg/dB). Try the MN1123 at a lower cap and the V13823 (34.4 N·m, 2.16 kg).
50. ~~Free-speed and 200 Wh/kg scenarios with the catalogue motors~~ (entry 41: at 15 m/s the hex wins every case, +0.7 to +8.1 kg. At free speed with 303 Wh/kg the V13828 tri wins by 2.8–4.1 kg, but at 61.4 dBA; held to a ≈ 55 dBA limit (U15XL tri) it is a tie, −0.7 to +0.6 kg. Break-even batteries: 15 m/s 328 Wh/kg (V13828) or none (U15XL); free speed 174 / 277 Wh/kg.)
52. ~~Free-speed break-even noise limit~~ (entry 42: with a 12 % reserve the tri's noise is set by its motor, not its cap. The U15XL designs at caps 0.65–0.80 all land at 55.2–55.6 dBA (torque-limited at tip Mach 0.70), and the V13828 at 61.4. At free speed with 303 Wh/kg the hex wins below ≈ 55.5 dBA, it is a tie at 55.2–55.6 (−0.42 to +0.14 kg), and only the V13828's 61.4 dBA gives the tri a clear win.)
53. **Reserve as the tri's noise knob:** between 0 % reserve (V13828 at 55.9 dBA, +6.87 kg, entry 38) and 12 % (61.4 dBA, +4.37 kg) the reserve moves the tri's noise by 5.5 dB. Sweep the reserve (0–15 %) for both layouts on the free-speed/303 case, and decide on a reserve from a gust/sag requirement rather than a round number.
44. ~~BEMT calibration on CFD~~ (entry 43: on the toroid session's 2-blade reference, CFD at equal thrust needs 1.16 × the rpm, 1.23 × the torque and 1.42 × the power of plain BEMT. If the CFD torque holds, the hex moves from the MN1123 to the MN1320 and the tri has no 24S motor that holds T/W 2 with a reserve. The additive Δc_d fit, 0.033, does not transfer to other loadings: it doubles the hex's hover power.)
54. ~~Re-optimise under the CFD factors~~ (entry 44: the hex on the MN1320 keeps its 12 % reserve at 48.0 dBA, losing ≈ 4.3 kg; the tri flies only on the U15XL with no reserve, at tip Mach 0.86 and 57.5 dBA, also losing ≈ 4.3 kg. Hex − tri: +3.4 kg at 15 m/s and 303 Wh/kg, −1.1 at free speed and 303, +1.9 to +8.6 with 200 Wh/kg.) Original: the torque and power factors at equal thrust (×1.23, ×1.42) or a loading-dependent correction. The hex would be on the MN1320 or V13828; the tri on the U15XL with no reserve, or not feasible. This gives new absolute payloads; the old ones are 5–10 kg optimistic.
55. **A second CFD point to separate thrust and torque error** (needs the CFD machine time, so it is the user's and the toroid session's call): a refined leading-edge mesh of the 2-blade reference (the CT validation found coarse noses inflate torque), or the same mesh at a second rpm or loading, to show whether the 23 % torque excess is physical (3-D, root and tip losses) or a mesh artefact.

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



## 23 — Camber below 2 %: NACA 14xx and symmetric 00xx (2026-11-18)

**Question.** Entries 20 and 22 went 6 % → 4 % → 2 % camber and each step gained payload. Does less still pay? New XFOIL polars for **14xx** (1 % camber at 40 % chord) and **00xx** (symmetric), t/c 9–18 %, same Re/Mach grid as before. All 160 new cases converged. The same optimisers as entries 20–22 (motor in the objective, 15 m/s design point), started from the 44xx optima. Script `src/explore/e23_camber_sweep.py`, results `results/explore/e23_camber_sweep.json` / `.png`.

| Layout | Section | Hover rpm | σ | Q_max [N·m] | Motor [kg] | Pack [Wh] | Hover stall margin | **Δ payload vs 44xx [kg]** | vs best of entry 22 |
|---|---|---|---|---|---|---|---|---|---|
| hex | 24xx (entry 22) | 1973 | 0.131 | 20.5 | 1.84 | 5139 | 9.4° | **+1.03** | 0 |
| hex | 14xx | 2059 | 0.132 | 20.1 | 1.80 | 5245 | 8.1° | +0.93 | −0.11 |
| hex | 24/00 hybrid | 2056 | 0.134 | 20.6 | 1.85 | 5347 | 6.7° | +0.27 | −0.76 |
| hex | 00xx | 2063 | 0.134 | 20.6 | 1.85 | 5396 | 6.7° | +0.10 | −0.94 |
| tri | 44/24 hybrid (entry 22) | 2135 | 0.151 | 50.6 | 4.53 | 7367 | 8.3° | **+0.25** | 0 |
| tri | 44/14 hybrid | 2135 | 0.157 | 51.3 | 4.59 | 7400 | 7.5° | −0.10 | −0.35 |
| tri | 14xx | 2136 | 0.165 | 51.4 | 4.60 | 7425 | 7.6° | −0.31 | −0.56 |

Payload against full-span camber (hex): 0 % +0.10, 1 % +0.93, **2 % +1.03**, 4 % 0, 6 % −1.14 kg. The curve has its peak between 1 and 2 %, and it is flat there (0.1 kg between them).

**Finding.**
- **The trend stops at 2 %.** NACA 24xx stays the best hex section, and the 44/24 hybrid the best tri section. Going to 1 % costs the hex 0.11 kg and the tri 0.35–0.56 kg; symmetric sections cost the hex 0.9 kg.
- **Why the hex stops gaining.** With less camber the hex rotor spins faster again (1973 → 2059 rpm), but the torque saving is now small: 20.5 → 20.1 N·m, so only −0.04 kg of motor per rotor. Faster spinning at the same thrust lowers the section Cl (mean 0.29 → 0.26), and below Cl ≈ 0.3 even the 14xx section is past its low-drag range. Hover power rises 345 W and the pack grows 106 Wh. The trade in kilograms: hardware −0.25 kg, pack +106 Wh / 303.3 Wh/kg = +0.35 kg, net **−0.10 kg** ✓ (model −0.11).
- **Why the tri loses straight away.** It is pinned on the tip-Mach cap (2136 rpm in every case; T/W at the cap 1.99), so it cannot use the lower effective pitch to spin faster. The optimiser instead adds chord (σ 0.151 → 0.165) to hold thrust at the same rpm, and the section works at Cl ≈ 0.4 where 14xx drags 10 % more than 24xx. Torque, motor and pack all rise.
- **Symmetric sections are poor here** for two reasons: drag at Cl 0.3–0.4 is 28–38 % above 24xx (thin 9 % section), and Cl_max drops to 0.95, cutting the hover stall margin to 6.7°.
- **The general lesson.** The best camber is the one whose drag bucket matches the Cl that the *motor-and-Mach-constrained* rotor runs at. The hex runs at Cl ≈ 0.3, the tri at ≈ 0.4. Within the NACA 4-digit family, the 2 % sections are closest to both. The remaining lever is a section whose bucket is centred lower (queue item 31), not still less camber.
- **No change to the ranking** from entry 22's estimate: hex +1.6 kg at 15 m/s, tri +2.4 kg at free speed (still estimates until queue item 30).

**Hand check 1: zero-lift angle is linear in camber.** Thin-airfoil theory gives α_L0 = −(1/π)∫(dz/dx)(cos θ − 1) dθ, and dz/dx is proportional to m, so α_L0 ∝ m:

| Section | Thin-airfoil α_L0 | XFOIL α_L0 (t/c 9 %) | XFOIL α_L0 (t/c 12 %) |
|---|---|---|---|
| 24xx | −2.08° | −2.27° | −2.22° |
| 14xx | **−1.04°** (half) | −0.96° | −0.92° |
| 00xx | 0 | 0.00° | 0.00° |

Thin-airfoil theory is within 0.2° of XFOIL. The viscous solution's ratio 14xx/24xx is 0.42 rather than 0.5, because the boundary layer at Re 6×10⁵ adds a little effective camber to the 2 % section and removes a little from the 1 % one. Each 1 % of camber is worth about 1° of effective pitch, which is why the hex start blade spins faster the less camber it has (start rpm 2345 for 14xx, 2661 for 00xx, against 1783 for the 44xx optimum).

**Hand check 2: hover profile power, 24xx → 14xx (hex).** Profile power of a rotor with a uniform section Cd: P₀ = ρA(ΩR)³·σ·Cd/8.
- **24xx:** ΩR = 1973·π/30 × 0.6858 = 141.7 m/s; Cd at the mean Cl 0.29 (t/c 9 %) = 0.00529; P₀ = 1.109 × 1.478 × 141.7³ × 0.131 × 0.00529 / 8 = **404 W** per rotor.
- **14xx:** ΩR = 147.9 m/s; Cd at Cl 0.26 ≈ 0.00547 (extrapolated from the table below); P₀ = 1.109 × 1.478 × 147.9³ × 0.132 × 0.00547 / 8 = **479 W** per rotor.
- **Hand ΔP₀ = 6 × 75 = +450 W**, against the model's total hover change of **+345 W**. The sign and size agree. The hand figure is about 30 % high because it uses one Cl and one t/c for the whole blade; the thick inboard sections and the lower induced power at the higher tip speed are not in it.
- The (ΩR)³ term is the point: **a 4.4 % rpm rise costs 14 % in profile power before Cd moves at all**, which is why spinning faster stops paying once the motor-torque saving gets small.

**Hand check 3: section drag at the operating Cl** (Re 6×10⁵, M 0.30, from the polar tables):

| Cl | 24xx 9 % | 14xx 9 % | 00xx 9 % | 24xx 12 % | 14xx 12 % | 00xx 12 % |
|---|---|---|---|---|---|---|
| 0.3 | **0.00529** | 0.00565 | 0.00677 | **0.00633** | 0.00660 | 0.00736 |
| 0.4 | **0.00560** | 0.00615 | 0.00773 | **0.00666** | 0.00714 | 0.00822 |
| 0.6 | **0.00682** | 0.00833 | 0.01086 | **0.00743** | 0.00825 | 0.01016 |
| 0.8 | **0.00941** | 0.01257 | 0.01622 | **0.00869** | 0.01068 | 0.01271 |
| Cl_max | 1.21 | 1.09 | 0.95 | 1.31 | 1.23 | 1.13 |

24xx has the lowest drag at every Cl from 0.3 up. Less camber would only win if the rotor ran below Cl ≈ 0.25, and spinning that fast costs more in (ΩR)³ than the section saves.

**Next.** Queue item 30: re-run the arms, speed, body and ranking chain (entries 14–19) with the 24xx hex blade and the 44/24 tri blade, so the layout ranking uses the best blades. Item 31 (a section with its bucket at Cl ≈ 0.3) is the remaining aerofoil lever.


## 24 — The layout ranking re-run with the best-camber blades (2026-11-18)

**Question.** Entries 16–19 ranked tri against hex with 4 % camber (44xx) blades. Entries 22–23 found 2 % camber better: the hex with 24xx full span, the tri with the 44/24 hybrid. Entry 22 only *estimated* the effect on the ranking. Here those blades, each with its own polar set, go through entry 18's full vehicle model: entry 17's bookkeeping (arms and fairings of entry 14, hover download, torque-sized motors, ESCs, spar blades) and cruise trimmed with each fuselage-drag model, at 14–30 m/s. The results then go through entry 19's ranking (tip-Mach cap 0.60). Script `src/explore/e24_chain_best_blades.py`, results `results/explore/e24_chain_best_blades.json` / `.png`. The blades are not re-optimised at each layout's best speed, because entry 17 showed that step is worth under 0.15 kg.

**Regression check.** The same script run on the old entry-17 blades with 44xx polars reproduces every one of entry 18's 136 rows to **0.0000 kg**. So the polar swap is the only thing that changed.

**Hex payload minus tri payload [kg]** (positive: hex wins; brackets: the motor-fit band of entry 10):

| Speed | Body | Battery | 44xx blades (entry 19) | **Best-camber blades** | Change | Break-even battery |
|---|---|---|---|---|---|---|
| 15 m/s | any (entry 18: < 0.06 kg) | 303 Wh/kg | +0.86 [−0.02, +1.07] | **+1.73 [+0.85, +1.94]** | +0.87 | 338 → **382 Wh/kg** |
| 15 m/s | any | 200 Wh/kg | +5.27 | **+6.07** | +0.80 | |
| free | constant | 303 Wh/kg | −3.19 | **−2.19** | +1.00 | 177 → **204 Wh/kg** |
| free | constant | 200 Wh/kg | −0.88 | **+0.11** (tie) | +0.99 | |
| free | streamlined | 303 Wh/kg | −3.09 | −2.08 | +1.01 | 181 → 208 |
| free | bluff | 303 Wh/kg | −2.16 | −1.11 | +1.05 | 217 → 252 |
| free | bluff | 200 Wh/kg | +0.68 | +1.76 | +1.08 | |
| free | bluff pre-tilted | 303 Wh/kg | −3.45 | −2.40 | +1.05 | 167 → 196 |

Best-range speeds barely move (tri 24.8 → 24.6, hex 21.1 → 21.0 m/s with the constant body). The hex still uses 23–34 % less energy in every case.

**Finding.**
- **Better blades help the hex about 1 kg more than the tri, in every scenario.** At 15 m/s the hex now leads by **+1.73 kg**, and the whole motor-fit band (+0.85 to +1.94) is above zero. This is the first time a 15 m/s result is robust to the motor-mass uncertainty.
- **At free speed the tri still leads with the 303 Wh/kg pack, by 1.1–2.4 kg** depending on the body. With a 200 Wh/kg LiPo the free-speed case is now a **tie** (constant or streamlined body) or a **hex win** (+1.8 kg, bluff body).
- **The break-even batteries rise by 27–44 Wh/kg.** The hex now wins at 15 m/s for any pack below 382 Wh/kg, and at free speed for any pack below about 200 Wh/kg. A typical LiPo (≈ 200 Wh/kg) now sits right on the free-speed break-even.
- **Where the hex's gain comes from:** six motors that each lose 0.16 kg (2.004 → 1.841 kg). Torque falls because the 2 % blade spins faster in hover (entry 22). The tri cannot follow, because it is pinned on the tip-Mach cap.
- **The decision still turns on the two open questions** (is 15 m/s a requirement or only a minimum? which battery?). But the hex's region has grown: it now wins at 15 m/s with any plausible battery, and ties or wins at free speed with a LiPo.

**Hand check 1: decomposing the 15 m/s shift.** The payload difference is −(Δhw + Δpack/e_b). With e_b = 303.3 Wh/kg:

| | Tri (hw, pack) | Hex (hw, pack) | hex − tri |
|---|---|---|---|
| 44xx blades | 23.104 kg, 7515 Wh | 30.766 kg, 4929 Wh | Δhw +7.662 kg, Δpack −2586 Wh |
| Best camber | 23.121 kg, 7482 Wh | 29.774 kg, 4938 Wh | Δhw +6.653 kg, Δpack −2544 Wh |

Change in (hex − tri) payload = −(6.653 − 7.662) − (−2544 + 2586)/303.3 = +1.009 − 0.139 = **+0.870 kg** ✓ (model +0.870). The hardware term is almost all motors: 6 × (2.004 − 1.841) = **0.978 kg**.

**Hand check 2: against entry 22's estimate.** Entry 22 estimated the shift as hex gain − tri gain = 1.03 − 0.25 = **+0.78 kg**. The full chain gives **+0.87 kg**. The gap is all on the tri side:
- In this frame the tri gains only 0.09 kg (mass 47.883 → 47.790 kg), not 0.25 kg.
- The reason is the baseline. Entry 22 compared against entry 13's tri blade, optimised for 15 m/s. This frame's baseline is entry 17's tri blade, already re-optimised for cruise at 24.7 m/s. That blade had already taken part of the profile-drag saving that the 44/24 hybrid offers.
- The hex gains 0.96 kg here against 1.03 in entry 22; its entry-17 blade had moved less.
- **Lesson:** gains measured against different baselines don't add exactly. That is why the chain had to be re-run rather than the estimate kept.

**Hand check 3: break-even battery.** The layouts tie when Δhw = −Δpack/e_b, so e_b* = −Δpack/Δhw = 2544 / 6.653 = **382 Wh/kg** ✓ (model 382.4). The break-even rises because the hex's hardware penalty fell by 1.0 kg while its energy advantage (≈ 2540 Wh) is unchanged: the same energy saving now pays for less extra hardware.

**Next.**
- Queue item 31: a custom outboard section with its drag bucket at Cl ≈ 0.3 (thinner 2 % section, or a laminar 6-series section). This is the remaining aerofoil lever, and from this entry it is worth more to the hex than to the tri.
- Queue item 10: tip speed against noise. The hex now runs faster (1973 rpm hover), which raises its tip Mach and noise. That should be in the ranking if noise is a requirement.
- Still waiting on the user: the 15 m/s requirement and the battery chemistry. With the new break-evens, a LiPo pack would make the hex the choice in nearly every scenario.


## 25 — NACA 230xx: a section designed for Cl 0.3 (2026-11-18)

**Question.** Entry 23 found that the hex rotor runs its sections at Cl ≈ 0.3 and the tri at ≈ 0.4, and queue item 31 asked for a section "with its drag bucket at Cl ≈ 0.3". The NACA 5-digit family is specified by exactly that: the first digit L sets the design lift coefficient Cl_i = 0.15 L, so **230xx is designed for Cl_i = 0.30**, with its camber peak forward at 15 % chord. New XFOIL polars for 230xx, t/c 9–18 %, same grid (80 cases, all converged, 684 s). Same optimisers as entries 20–23 (motor in the objective, 15 m/s), started from the 44xx optima. Script `src/explore/e25_naca230.py`, results `results/explore/e25_naca230.json` / `.png`.

| Layout | Section | Hover rpm | σ | Q_max [N·m] | Motor [kg] | Pack [Wh] | Hover stall margin | Δ payload vs 44xx | **vs best 2 % (24xx / 44-24)** |
|---|---|---|---|---|---|---|---|---|---|
| hex | 24xx (entry 22) | 1973 | 0.131 | 20.5 | 1.84 | 5139 | 9.4° | +1.03 | 0 |
| hex | 230xx | 1944 | 0.134 | 21.5 | 1.93 | 5304 | 9.5° | −0.09 | **−1.13** |
| hex | 24/230 hybrid | 1956 | 0.133 | 21.3 | 1.91 | 5286 | 9.4° | +0.06 | **−0.97** |
| tri | 44/24 hybrid (entry 22) | 2135 | 0.151 | 50.6 | 4.53 | 7367 | 8.3° | +0.25 | 0 |
| tri | 230xx | 2128 | 0.158 | 51.9 | 4.64 | 7505 | 8.4° | −0.69 | **−0.94** |
| tri | 44/230 hybrid | 2131 | 0.153 | 51.8 | 4.63 | 7489 | 8.3° | −0.54 | **−0.79** |

**Finding.**
- **The 230xx loses about 1 kg on both layouts** against the 2 % 4-digit sections. Its section drag at Cl 0.3 is **36 % higher** at t/c 9 % (0.00717 against 0.00529) and **27 % higher** at 12 %. Hover power rises 544 W on the hex. The motors also get heavier, because the higher drag torque slows the rotor slightly (1973 → 1944 rpm).
- **"Design Cl" is not where the drag bucket is.** The 5-digit design (ideal) lift coefficient is a thin-airfoil, inviscid idea: the angle at which the flow meets the leading edge smoothly, with no leading-edge suction spike. At Reynolds numbers of a few hundred thousand, section drag is set mostly by **how far back the boundary layer stays laminar**, and that depends on how long the upper-surface pressure keeps falling. The 230's camber peak at 15 % chord puts the suction peak forward and starts the adverse gradient early. XFOIL's transition point at Cl ≈ 0.3 is:

  | Section (Re 6×10⁵, M 0.3) | Cl | Upper transition x/c | Lower transition x/c | Cd |
  |---|---|---|---|---|
  | 2409 | 0.24 / 0.33 | **0.78 / 0.74** | 0.95 / 1.00 | 0.0052 / 0.0054 |
  | 23009 | 0.26 / 0.36 | **0.41 / 0.33** | 0.98 / 1.00 | 0.0069 / 0.0076 |

- **The 24xx already has its bucket where the hex works.** Its minimum-drag Cl is 0.24 at t/c 9 % and 0.30 at 12 %. The premise of queue item 31, that the 4-digit sections have their bucket too high, was wrong for the 2 % section. Entry 23 had already shown this indirectly: less camber didn't help.
- **The stall margins are fine** (8.3–9.5°), so the 230's known abrupt leading-edge stall isn't what decides it here; drag is.
- **No change to the ranking** of entry 24. The lever left is pressure distribution, not design Cl: camber further aft (queue item 32), or a true laminar section (item 33).

**Hand check 1: the 5-digit mean line (thin-airfoil theory).** The 230 mean line is y = (k₁/6)(x³ − 3m x² + m²(3 − m)x) for x < m, and (k₁m³/6)(1 − x) behind it, with m = 0.2025 and k₁ = 15.957. Substituting x = ½(1 − cos θ) and integrating numerically:
- maximum camber **1.84 % at x = 0.15** (as the name says: "3" → 0.05 × 3);
- zero-lift angle α_L0 = −(1/π)∫(dz/dx)(cos θ − 1)dθ = **−1.09°**. XFOIL gives −1.33° (9 %) and −1.25° (12 %);
- ideal angle (where the Fourier coefficient A₀ = 0, i.e. no leading-edge singularity) α_i = (1/π)∫(dz/dx)dθ = **+1.64°**;
- design lift Cl_i = 2π(α_i − α_L0) = 2π × (1.64° + 1.09°) in radians = **0.300** ✓. So the mean line is right, and the section really is "designed for Cl 0.3". The loss comes from the viscous behaviour.

**Hand check 2: drag from the transition point (flat-plate friction with a laminar run).** A surface laminar up to x_t and turbulent behind it has the mixed friction coefficient (Prandtl–Schlichting):

  C_F(x_t) = 0.074 Re^(−1/5) − x_t·[0.074 (x_t Re)^(−1/5) − 1.328 (x_t Re)^(−1/2)]

This is the all-turbulent plate, with the turbulent friction of the first x_t replaced by Blasius laminar friction. At Re = 6×10⁵: C_F(0.757) = 0.00252, C_F(0.975) = 0.00180, C_F(0.37) = 0.00388, C_F(0.99) = 0.00175. Section drag ≈ form factor × (upper + lower), with Hoerner's FF = 1 + 2t/c + 60(t/c)⁴ = 1.184 at t/c 9 %:
- **2409:** 1.184 × (0.00252 + 0.00180) = **0.00512** (XFOIL 0.0052–0.0054) ✓
- **23009:** 1.184 × (0.00388 + 0.00175) = **0.00667** (XFOIL 0.0069–0.0072) ✓
- Ratio: hand **+30 %**, XFOIL **+30–36 %**. Moving upper-surface transition from 76 % to 37 % chord accounts for almost the whole penalty.

**Lesson.** At this Reynolds number, choose a section by where its pressure keeps falling (its laminar run), not by its inviscid design lift coefficient. Forward camber (5-digit) shortens the laminar run; aft camber should lengthen it.

**Next.** Queue item 32: 2 % camber further aft (25xx, 26xx). These are cheap 4-digit XFOIL cases and test the transition argument directly: transition should move further back at Cl 0.3–0.4, and the tri, at Cl 0.4, might gain too. Then item 10 (tip speed and noise).


## 26 — 2 % camber moved aft: NACA 25xx and 26xx (2026-11-18)

**Question.** Entry 25 found that drag at Re ≈ 6×10⁵ is set by how far back the boundary layer stays laminar, and that forward camber (230xx) cut the laminar run short. Does the converse work? Keep 2 % camber and move its peak from 40 % chord (24xx) to 50 % (25xx) and 60 % (26xx). New XFOIL polars (160 cases, all converged, 936 s). Same optimisers as entries 20–25. Script `src/explore/e26_aft_camber.py`, results `results/explore/e26_aft_camber.json` / `.png`.

| Layout | Section | Hover rpm | σ | Q_max [N·m] | Motor [kg] | Pack [Wh] | Hover [W] | Hover stall margin | Δ vs 44xx | **vs best 2 %** |
|---|---|---|---|---|---|---|---|---|---|---|
| hex | 24xx (entry 22) | 1973 | 0.131 | 20.5 | 1.84 | 5139 | 12678 | 9.4° | +1.03 | 0 |
| hex | 25xx | 1957 | 0.130 | 20.6 | 1.85 | 5138 | 12596 | 9.4° | +0.99 | **−0.04** |
| hex | 26xx | 1967 | 0.130 | 20.6 | 1.85 | 5212 | 12734 | 9.5° | +0.81 | **−0.22** |
| tri | 44/24 hybrid (entry 22) | 2135 | 0.151 | 50.6 | 4.53 | 7367 | 16924 | 8.3° | +0.25 | 0 |
| tri | 44/25 hybrid | 2138 | 0.151 | 50.5 | 4.51 | 7378 | 16839 | 8.1° | +0.25 | **−0.00** |
| tri | 44/26 hybrid | 2144 | 0.150 | 50.6 | 4.53 | 7413 | 16883 | 8.3° | +0.10 | **−0.15** |

**Finding.**
- **Moving the camber aft doesn't pay.** 25xx ties 24xx on both layouts (within 0.04 kg, below the optimiser's resolution), and 26xx loses 0.15–0.22 kg. The 2 % camber optimum is flat from 40 to 50 % chord and falls off by 60 %.
- **The transition argument holds, but it works on both surfaces.** Moving the camber aft does push the upper-surface transition back, as entry 25 predicted. But it also makes the aft lower surface concave, which starts the lower-surface adverse gradient earlier, so the lower transition moves *forward*. The two nearly cancel:

  | Section (t/c 9 %, Re 6×10⁵, M 0.3) | Cl | Upper x_tr | Lower x_tr | Cd | Cm (XFOIL) |
  |---|---|---|---|---|---|
  | 2409 | 0.33 | 0.74 | **1.00** | 0.0054 | −0.059 |
  | 2509 | 0.27 | 0.83 | 0.87 | 0.0052 | −0.065 |
  | 2609 | 0.31 | **0.88** | 0.72 | 0.0057 | −0.081 |

  At Cl 0.4 (where the tri works) aft camber does a little better: 26xx at t/c 9 % has Cd 0.00524 against 0.00560. But the thick 12 % sections, which carry the mid-span, don't improve, and the optimum is unchanged.
- **Aft camber costs in pitching moment**, which loads the blade in torsion and the pitch link and grip. It is 10 % more nose-down for 25xx and 37 % for 26xx (XFOIL). With no drag gain, that settles it: **keep 24xx**.
- **The NACA 4- and 5-digit families are exhausted** for this rotor: 0–6 % camber (entries 20, 22, 23), camber position 15–60 % (entries 25, 26). The best is 2 % at 40–50 %, flat to within 0.05 kg. Further section gains need a true laminar-flow section (queue item 33), with its thickness peak further aft so that both surfaces see a favourable gradient. That needs section coordinates generated outside XFOIL's NACA command.

**Hand check 1: thin-airfoil zero-lift angle and pitching moment (NACA 4-digit mean line, m = 0.02).** The Fourier coefficients A_n = (2/π)∫(dz/dx) cos(nθ) dθ give α_L0 = −(1/π)∫(dz/dx)(cos θ − 1)dθ and Cm_c/4 = (π/4)(A₂ − A₁):

| Section | p | α_L0 thin | α_L0 effect | Cm_c/4 thin | Cm XFOIL (t/c 9 %, Cl ≈ 0.3) |
|---|---|---|---|---|---|
| 24xx | 0.4 | −2.08° | | −0.053 | −0.059 |
| 25xx | 0.5 | −2.29° | +0.21° effective pitch | **−0.063** (exactly −πm, for p = ½) | −0.065 |
| 26xx | 0.6 | −2.59° | +0.51° | −0.075 | −0.081 |

Thin-airfoil theory gets the moment trend right to within 0.006. Aft camber weights the camber slope toward the trailing edge, where the cos θ terms in A₁ and A₂ are most negative, so the moment grows. For p = ½ the mean line is symmetric about mid-chord, and the integrals give exactly Cm = −πm.

**Hand check 2: drag from both transition points (entry 25's mixed-plate model).** C_F(x_t) = 0.074 Re^(−1/5) − x_t[0.074 (x_t Re)^(−1/5) − 1.328 (x_t Re)^(−1/2)], with Cd ≈ (1 + 2t/c + 60(t/c)⁴)(C_F,upper + C_F,lower) = 1.184 × (…) at t/c 9 %:

| Section | C_F upper | C_F lower | Cd hand | Cd XFOIL |
|---|---|---|---|---|
| 2409 | 0.00260 (x_t 0.74) | 0.00173 (x_t 1.00) | **0.00512** | 0.0054 |
| 2509 | 0.00228 (0.83) | 0.00213 (0.87) | **0.00522** | 0.0052 |
| 2609 | 0.00210 (0.88) | 0.00264 (0.72) | **0.00561** | 0.0057 |

The hand model reproduces the 26xx penalty: +0.0005, against XFOIL's +0.0003 to +0.0005. It ranks 24xx and 25xx within 0.0001 of each other, the same tie the optimiser finds. The upper surface saves 0.0005 in C_F, the lower loses 0.0009: **friction is roughly linear in the turbulent length, so moving transition by the same distance on the other surface simply moves the drag there.** (The XFOIL points sit at slightly different Cl, 0.27–0.33, which is the main scatter in this check.)

**Next.** Queue item 10: tip speed and noise. The 2 % blades raise the hex's hover speed to 1973 rpm (tip Mach 0.40 in hover, about 0.56 at T/W 2 since rpm ∝ √T), so a noise requirement is the next thing that could move the ranking. Item 33 (a laminar section from coordinates) stays open as the last aerofoil lever.


## 27 — Hover noise of the tri and hex: Gutin steady-loading tones, A-weighted (2026-11-18)

**Question.** Queue item 10: would a noise requirement move the ranking? Both layouts weigh the same. The tri carries the weight on 3 rotors at twice the thrust each and spins faster in hover (2135 against 1973 rpm). The hex has twice as many sources. Script `src/explore/e27_rotor_noise.py` (runs in about a second), results `results/explore/e27_rotor_noise.json` / `.png`. Blades: the best 2 % blades of entries 22/24 (hex 24xx, tri 44/24 hybrid).

**Model: Gutin's steady-loading noise.** A rotor's steady thrust and torque, spinning, are a rotating force pattern. Far away it radiates tones at multiples of the blade-passing frequency f_m = mBΩ/2π. With the loading distributed along the span (BEMT dT/dr and dQ/dr), the rms pressure of harmonic m at distance S and angle θ from the thrust axis is

  p_m = mBΩ / (2√2 π a S) · | ∫ [ −cos θ · dT + (a / Ω r²) · dQ ] · J_mB(mBΩ r sin θ / a) |

- The thrust term radiates along and below the disk (cos θ < 0 below a hovering rotor), and the torque (drag) term radiates in the plane.
- The Bessel function J_mB carries the tip-Mach dependence: it is tiny for small arguments, so slow rotors are quiet in their tones.
- Straight below (θ = 180°), J_mB(0) = 0. Steady loading makes no sound on the axis, and the loudest direction is about 20–25° below the disk plane.
- Above the disk (θ < 90°), −cos θ·T is negative and cancels the torque term. The plot shows that null at θ ≈ 65–75°, where T cos θ = Q a / (Ω R_e²); above a hovering rotor it is quieter than below by 12–15 dB.
- The n rotors run at slightly different rpm, so their tones add incoherently (+10 log₁₀ n). Harmonics 1–20 are summed, then A-weighted (IEC 61672). The observer is at 50 m.

**What Gutin leaves out:** thickness noise (small below tip Mach ≈ 0.5), broadband noise (turbulence, trailing edge) and unsteady loading (blade–wake interaction, arms in the downwash). For large, slow rotors those often set the A-weighted level. **The absolute dBA here are a lower bound; the comparison between layouts is the result.**

| Point | Layout | rpm | Tip Mach | T per rotor [N] | Q [N·m] | BPF [Hz] | Max OASPL [dB] | **Max tonal level [dBA]** | at θ |
|---|---|---|---|---|---|---|---|---|---|
| hover | tri | 2135 | 0.429 | 415 | 25.2 | 71 | 69.7 | **46.8** | 112° |
| hover | hex | 1973 | 0.396 | 208 | 10.2 | 66 | 64.2 | **39.9** | 115° |
| T/W 2 | tri | 2992 | 0.601 | 830 | 50.6 | 100 | 83.5 | **67.7** | 112° |
| T/W 2 | hex | 2763 | 0.555 | 415 | 20.5 | 92 | 78.0 | **60.5** | 112° |

**Finding.**
- **The hex is 5.5 dB quieter unweighted and 6.9–7.2 dBA quieter A-weighted**, in hover and at full thrust. It has twice the sources (+3 dB), but each carries half the thrust (−6 dB), and it spins 8 % slower (−2 dB from 60 log₁₀, see hand check 2). The A-weighted gap is bigger than the unweighted one because the tri's higher harmonics sit a little higher in frequency, where the A-curve is less severe.
- **A-weighting removes most of the fundamental.** At 66–100 Hz the A-curve is −19 to −26 dB, so the dBA level is set by harmonics 3–10 (200–700 Hz). Those harmonics grow fastest with tip Mach (J_mB with mB = 6–20), which is why tip speed matters so much more for dBA than for OASPL.
- **What noise parity would cost the tri (estimate).** To be as quiet as the hex in tonal noise, the tri would need about 7 dB less, i.e. a rotor speed lower by a factor 10^(−7/60) = 0.76 (tip Mach at T/W 2: 0.60 → 0.46). Entry 15's tip-Mach sweep (44xx blades) shows that even a 0.50 cap costs the tri **2.0 kg** (its hover speed falls to 1782 rpm). At that speed it would be roughly level with the hex: +0.4 dB on the first harmonic (+6 − 3 + 60 log₁₀(1782/1973) = +6 − 3 − 2.7), or about +2 dBA if the A-weighted gap only fell as 60 log₁₀ (the higher harmonics fall faster, so the truth lies between).
  - So a noise requirement set at the hex's level costs the tri **more than 2 kg**. That removes most of its free-speed lead (1.1–2.4 kg, entry 24) and adds to the hex's 15 m/s lead (+1.7 kg).
  - This is an extrapolation of entry 15 below its range; queue item 34 re-optimises with a noise cap directly.
- **Ranking:** the hex is better or equal on payload at 15 m/s, on energy everywhere, and on tonal noise everywhere. The tri's only win is payload at free cruise speed with a high-energy pack, and a noise limit would cut into that.

**Hand check 1: Gutin's concentrated form for the first harmonic (θ = 120°, observer 30° below the disk plane, one rotor).** Put all the load at the classic effective radius R_e = 0.8R = 0.549 m:
- **Hex:** Ω = 1973·π/30 = 206.6 rad/s; Bessel argument x = BΩR_e sin θ / a = 2 × 206.6 × 0.549 × 0.866 / 357.6 = **0.549**; J₂(0.549) = **0.0368** (small-argument form (x/2)²/2! = 0.0377).
  - Thrust term −T cos θ = 207.6 × 0.5 = 103.8 N.
  - Torque term Q·a/(ΩR_e²) = 10.2 × 357.6 / (206.6 × 0.301) = 58.8 N.
  - p₁ = 2 × 206.6 / (2√2 π × 357.6 × 50) × (103.8 + 58.8) × 0.0368 = **0.0155 Pa → 57.8 dB** per rotor, **65.6 dB** for six.
  - The distributed model gives **64.0 dB** for six.
- **Tri:** x = 0.594, J₂ = 0.0428, p₁ = 0.0412 Pa → 66.3 dB per rotor, **71.0 dB** for three. The model gives **69.5 dB**.
- **The concentrated form is 1.6 dB high on both.** The reason: the BEMT thrust centroid is at 0.65R, not 0.8R. For harmonic 1, J₂ ∝ r² weights the loading by r², so the effective radius is about 0.7R. On the thrust term that is 20 log₁₀((0.7/0.8)²) ≈ −2.3 dB, partly offset by the torque term's 1/R_e². The 0.8R rule of thumb comes from propellers with more outboard-loaded blades.

**Hand check 2: why tones scale as 60 log₁₀ of the rotor speed at fixed thrust.** For small x, J_B(x) ≈ (x/2)^B / B!, so with B = 2 the first harmonic goes as p₁ ∝ Ω (prefactor) × T × Ω² (Bessel) = T·Ω³: **+60 log₁₀ Ω at fixed thrust** (the torque term scales the same way, since Q·a/Ω ∝ T). Tri against hex, first harmonic, whole vehicle:
- thrust per rotor ×2: +6.0 dB;
- half the rotors: −3.0 dB;
- rpm ratio 2135/1973: 60 log₁₀(1.082) = +2.1 dB;
- hand total **+5.1 dB**, against the model's **+5.4 dB** ✓.

This is the same 60 log₁₀ rule entry 15 used, now derived from Gutin.

**Next.** Queue item 34: a noise-capped re-optimisation, with the tri and hex blades optimised under an equal-dBA cap instead of the tip-Mach cap, plus a broadband estimate, since tones are only the lower bound. Still open for the user: is there a noise requirement (e.g. dBA at a distance)? It would now be the third input that decides the layout, after the speed requirement and the battery chemistry.


## 28 — Payload against noise: both layouts re-optimised at tip-Mach caps 0.45–0.60 (2026-11-18)

**Question.** Entry 27 found the hex 6.9 dBA quieter in hover tones. It estimated, by extrapolating entry 15 (44xx blades), that quieting the tri to match would cost it more than 2 kg. This entry does it properly:
- **Method:** entries 11 (hex) / 13 (tri) optimisers, with the best-camber polars (hex 24xx, tri 44/24 hybrid), started from the entry-22 optima, at tip-Mach caps 0.45, 0.50, 0.55 and 0.60 (at T/W 2, hot day). Each optimum's hover and T/W 2 tonal level then comes from entry 27's Gutin model (50 m, A-weighted).
- **Combining with the ranking:** the payload change from each layout's own cap-0.60 optimum is added to entry 24's full-chain ranking. That transfers a 15 m/s-frame change into entry 24's frame, which is a fair approximation since the change is almost all motor and blade hardware.
- **Files:** script `src/explore/e28_noise_cap.py`, results `results/explore/e28_noise_cap.json` / `.png`.

| Layout | Cap | Hover rpm | σ | Q_max [N·m] | Motor [kg] | Pack [Wh] | Hover [dBA] | T/W 2 [dBA] | **Δ payload vs own 0.60 [kg]** |
|---|---|---|---|---|---|---|---|---|---|
| tri | 0.60 | 2135 | 0.151 | 50.6 | 4.53 | 7365 | 46.8 | 67.7 | 0 |
| tri | 0.55 | 1955 | 0.161 | 55.2 | 4.93 | 7284 | 43.7 | 64.2 | **−1.01** |
| tri | 0.50 | 1777 | 0.174 | 60.8 | 5.44 | 7220 | 40.4 | 60.5 | **−2.47** |
| tri | 0.45 | 1601 | 0.182 | 68.1 | 6.08 | 7217 | 36.9 | 56.8 | **−4.58** |
| hex | 0.60 (not binding: M 0.555) | 1973 | 0.131 | 20.5 | 1.84 | 5140 | 39.8 | 60.5 | 0 |
| hex | 0.55 | 1955 | 0.131 | 20.6 | 1.85 | 5127 | 39.5 | 60.2 | −0.00 |
| hex | 0.50 | 1769 | 0.133 | 22.1 | 1.99 | 5017 | 35.7 | 56.2 | **−0.29** |
| hex | 0.45 | 1587 | 0.137 | 24.2 | 2.17 | 4944 | 31.7 | 52.0 | **−1.09** |

**Hex minus tri payload at the tri held to the hex's own hover level (39.8 dBA; tri −2.80 kg, hex 0):**

| Scenario | 303 Wh/kg | 200 Wh/kg |
|---|---|---|
| 15 m/s | **+4.54 kg** (was +1.73) | **+8.87** (was +6.07) |
| free speed, constant body | **+0.61** (was −2.19) | **+2.91** (was +0.11) |
| free speed, streamlined body | +0.72 (was −2.08) | +3.09 |
| free speed, bluff body | +1.69 (was −1.11) | +4.56 |
| free speed, bluff pre-tilted | +0.41 (was −2.40) | +2.61 |

**Finding.**
- **Quieting the tri is expensive; quieting the hex is cheap.** Each 0.05 of tip Mach costs the tri 1.0–2.1 kg (a steepening curve) and the hex 0.0–0.8 kg. The tri's motors carry twice the torque each, and a lower cap raises that torque by 1/M (hand check 1), so its motor mass climbs from 4.53 to 6.08 kg per motor at 0.45. The hex at 0.60 isn't even on the cap (its T/W 2 tip Mach is 0.555), so its first 0.05 is free.
- **At equal noise the hex wins every scenario.** Held to the hex's hover level, the tri gives up 2.80 kg, and its free-speed lead (1.1–2.4 kg with the 303 Wh/kg pack) turns into a hex lead of 0.4–1.7 kg.
- **Break-even noise limits.** With the 303 Wh/kg pack at free speed, the tri wins only if the hover tonal limit is looser than **40.6–43.5 dBA** (by body model). That is any limit less than 3–6 dB below the tri's unconstrained 46.8 dBA. With a 200 Wh/kg pack the hex wins at every limit in the range, except a bluff pre-tilted body above 46.2 dBA.
- **So a noise requirement, if there is one, decides for the hex** unless it is looser than the tri's natural level. The decision inputs are now: speed requirement, battery, noise. The hex wins on two of the three in almost every combination.
- **Caveat:** absolute dBA are Gutin steady-loading tones only (a lower bound; broadband and unsteady loading are missing, queue item 35). The limits above are in that metric. What carries over to any real noise metric is the *ordering*, and the slope: payload per dB, 0.3–0.6 kg/dB for the tri against 0.1–0.2 kg/dB for the hex.

**Hand check 1: motor mass ∝ 1/M on the cap.** On the cap the top rotor speed is Ω_cap = M a / R, and Q_max = P_max / Ω_cap. With P_max roughly constant, Q ∝ 1/M, and the torque-sized motor too (m ≈ 0.0909 τ). Tri from 0.60 to 0.55:
- hand 0.60/0.55 = **1.091**;
- optimiser 4.93/4.53 = **1.089** ✓.

At lower caps the ratio rises faster than 1/M (0.45: 6.08/4.53 = 1.34 against 1.33), because P_max creeps up too: a slower rotor needs more solidity, and its profile power grows.

**Hand check 2: why dBA falls faster than 60 log₁₀ rpm.** Entry 27 derived p₁ ∝ T Ω³ for the first harmonic. But the dBA level is carried by harmonics 3–10, and for harmonic m the small-argument Bessel term gives p_m ∝ Ω · (Ω)^(mB) at fixed thrust, i.e. 20(mB + 1) log₁₀ Ω. With B = 2, harmonic 3 already scales as 140 log₁₀ Ω. So the A-weighted level falls faster than the 60 log₁₀ rule:

| Tri cap | rpm ratio vs 0.60 | 60 log₁₀ (first harmonic) | Model dBA | Effective exponent |
|---|---|---|---|---|
| 0.55 | 1955/2135 | −2.3 dB | **−3.1 dB** | 82 log₁₀ |
| 0.50 | 1777/2135 | −4.8 dB | **−6.5 dB** | 81 log₁₀ |
| 0.45 | 1601/2135 | −7.5 dB | **−9.9 dB** | 79 log₁₀ |

The model's A-weighted level falls as about **80 log₁₀ rpm**, between the first-harmonic 60 and the higher harmonics' 100+. The larger solidity at low caps spreads the load over more chord but doesn't change the Gutin sources, which depend only on dT and dQ along the radius. This makes quieting a rotor cheaper per dB than entry 15's 60 log rule suggested, but not cheap enough to save the tri.

**Next.** Queue item 35: a broadband estimate. Trailing-edge and vortex noise scale as about V⁶ × blade area, so the tri's larger solidity at low caps adds broadband noise and might narrow the hex's advantage. Then item 33 (laminar section from coordinates), or item 13 (restating the coaxial case).


## 29 — Broadband (trailing-edge) noise scaling on the entry-28 optima (2026-11-18)

**Question.** Entries 27–28 used only Gutin's steady-loading tones and found the hex 7 dBA quieter. For large, slow rotors the A-weighted level is often set by **broadband** noise instead, mostly turbulent-boundary-layer trailing-edge noise. Does broadband change the comparison? There is no calibrated broadband model in the repo, so this entry compares the layouts by the physical scaling of edge noise and reports **level differences only**. Script `src/explore/e29_broadband.py` (seconds), results `results/explore/e29_broadband.json` / `.png`.

**Model (scaling only).**
- **Edge noise** (Ffowcs Williams & Hall, 1970): turbulence convecting past a sharp trailing edge radiates far more efficiently than turbulence in open flow. Its intensity per unit span is dI ∝ ρ² W⁵ δ* dr / (a r²). The exponent is 5, not the 8 of free turbulence (Lighthill), because the edge scatters the near field.
- **Boundary-layer thickness:** turbulent flat plate, δ* = 0.046 c Re_c^(−1/5) per side, both sides counted.
- **Whole vehicle:** n rotors × B blades, adding incoherently.
- **Peak frequency:** f_p ≈ 0.02 W / δ* (Brooks–Pope–Marcolini Strouhal scaling).
- **Cross-check:** the older Schlegel–King–Mull "vortex noise" law, ∝ W₀.₇⁶ × blade area.

**Hover levels against the hex at cap 0.60 [dB]:**

| Layout | Cap | rpm | σ | Δ payload [kg] | **Tonal (Gutin, dBA)** | **Trailing-edge broadband** | SKM scaling | f_peak at 0.75R | A-weight at f_peak |
|---|---|---|---|---|---|---|---|---|---|
| hex | 0.60 | 1973 | 0.131 | 0 | 0 | 0 | 0 | 5.9 kHz | +0.1 dB |
| hex | 0.50 | 1769 | 0.133 | −0.29 | −4.2 | −2.0 | −2.5 | 4.8 kHz | +0.6 |
| hex | 0.45 | 1587 | 0.137 | −1.09 | −8.2 | −3.9 | −4.9 | 3.9 kHz | +1.0 |
| tri | 0.60 | 2135 | 0.151 | 0 | **+7.0** | **−1.0** | −0.5 | 5.8 kHz | +0.2 |
| tri | 0.55 | 1955 | 0.161 | −1.01 | +3.8 | −2.3 | −2.1 | 4.6 kHz | +0.7 |
| tri | 0.50 | 1777 | 0.174 | −2.47 | +0.5 | −3.7 | −3.8 | 3.6 kHz | +1.1 |
| tri | 0.45 | 1601 | 0.182 | −4.58 | −2.9 | −5.3 | −5.8 | 2.8 kHz | +1.3 |

**Finding.**
- **In broadband the tri is the quieter layout**, by 1.0 dB at cap 0.60 (0.5 dB on the SKM law). Trailing-edge noise counts blade edge length times speed to the fifth, and the tri has half the blades (−3 dB), spinning only 8 % faster (+1.7 dB). Tones go the other way, because they depend on the *loading per blade*, and each tri blade carries twice the thrust.
- **So entry 28's verdict holds only if tones dominate the A-weighted level.** If broadband dominates, the tri needs no quieting to match the hex, and its free-speed lead (1.1–2.4 kg at 303 Wh/kg) stands. Entry 28's ranking-at-equal-noise is an upper bound on what a noise limit costs the tri.
- **Why it isn't obvious which dominates.** The tones sit at 66–100 Hz and their harmonics at 200–700 Hz, where A-weighting removes 5–26 dB. The broadband peak is at 3–6 kHz, where A-weighting adds about +1 dB. Measured multirotor spectra often show the tonal peaks standing above a broadband floor in the unweighted spectrum, but the A-weighted total can be carried by either. Only an absolute broadband level can tell, which needs a calibrated model (queue item 36: BPM, NASA RP-1218) or a measurement.
- **Quieting a rotor in broadband costs more payload per dB than in tones.** Broadband falls only as about 50 log₁₀ rpm (W⁵, slightly offset by the larger chord at low caps), tones as about 80 log₁₀ (entry 28). Over caps 0.60 → 0.45:
  - tri: 1.1 kg/dB in broadband (4.3 dB for 4.58 kg), against 0.46 kg/dB in tones;
  - hex: 0.28 kg/dB in broadband, against 0.13 kg/dB in tones.

  If broadband sets the limit, slowing the rotor is a poor way to meet it. Blade-edge treatments (serrations, porous trailing edges) target broadband directly and would be the cheaper lever.
- **Decision status:**
  - The hex wins on payload at 15 m/s, on energy everywhere, and on tonal noise.
  - The tri wins on payload at free speed with a high-energy pack, and is slightly quieter in broadband.
  - A noise requirement only decides for the hex if the noise that counts is tonal: low-frequency, propagating far, as a community-noise metric usually weights it.

**Hand check: tri vs hex trailing-edge difference at cap 0.60 from blade count, speed and chord.** Since δ* ∝ c (W c)^(−1/5), the integrand W⁵ δ* ∝ W^4.8 c^0.8. Taking the ratios at 0.75R (rpm 2135/1973, chord 135/119 mm):
- blade count, 3 × 2 against 6 × 2 blades: 10 log₁₀(½) = **−3.01 dB**;
- speed: 50 log₁₀(2135/1973) = **+1.71 dB**;
- Reynolds-number correction on δ*: −2 log₁₀(1.082) = **−0.07 dB**;
- chord: 8 log₁₀(135/119) = **+0.45 dB**;
- hand total **−0.92 dB**, against the model's spanwise integral **−1.00 dB** ✓.

The chord enters only weakly (power 0.8 and inside a log), so the tri's wider blades at low caps (σ 0.151 → 0.182) add just 0.6 dB while the speed drop removes 3.9 dB.

**Lesson.** Rotor noise has two scalings with different physics: tones scale with loading per blade and rotor speed to a high power; broadband scales with total edge length and section speed to the fifth. A design that wins one can lose the other. Before a noise requirement can rank layouts, it has to say which metric it uses (dBA, or a tone-corrected metric such as EPNL or PNLT) and at what distance.

**Next.**
- Queue item 36: calibrated BPM trailing-edge noise for absolute levels. It is a self-contained model with published constants and a published validation case (NACA 0012), which fits this project's verify-against-a-reference approach.
- For the user: does the vehicle have a noise requirement, and in which metric? That answer now decides whether noise favours the hex or is neutral.


## 30 — Absolute broadband noise (BPM trailing-edge model) against the Gutin tones (2026-11-18)

**Question.** Entry 29 compared broadband noise by scaling only and found the tri 1 dB *quieter*. Entry 28's noise ranking assumed tones set the dBA. Which is right needs an absolute broadband level. This entry implements the Brooks–Pope–Marcolini turbulent-boundary-layer trailing-edge model (NASA RP-1218, 1989) and applies it to entry 28's rotors.
- **Model:** `src/explore/bpm.py`, with the equations transcribed from the report's scanned pages:
  - untripped boundary-layer fits, eqs. 5–6, 9, 12/15;
  - SPL_p, SPL_s and SPL_α, eqs. 24–30;
  - Strouhal numbers, eqs. 31–34;
  - spectral shapes A and B, eqs. 35–46;
  - K₁, ΔK₁ and K₂, eqs. 47–50;
  - directivity D̄_h and D̄_l, eqs. B1–B2.
- **Rotor study:** `src/explore/e30_bpm_rotor.py`, results `results/explore/e30_bpm_rotor.json` / `.png`.

**Validation against the report.** The report's Figure 44 shows its own predictions for a 30.48 cm NACA 0012, untripped, α = 0, 45.72 cm span, observer 1.22 m at 90°. Our code gives:

| U [m/s] | Our total peak (1/3 octave) | Figure 44 prediction (read off the plot) | Our suction-side peak | Figure 44 |
|---|---|---|---|---|
| 71.3 | 59.7 dB at 3.15 kHz | ≈ 59–60 dB at 2.5–3 kHz | 56.7 dB | ≈ 56–57 |
| 55.5 | 54.5 dB at 3.15 kHz | ≈ 53–54 dB | 51.5 | ≈ 51 |
| 39.6 | 47.6 dB at 2.5 kHz | ≈ 47 dB | 44.6 | ≈ 44 |
| 31.7 | 43.8 dB at 2.0 kHz | ≈ 43–44 dB | 40.8 | ≈ 40 |

Agreement is within the ≈ 1 dB that reading a scanned plot allows. (The report's predictions themselves match its measured data within a few dB for this airfoil.)

**Applying it to a rotor.**
- **Strips:** each blade strip outboard of 0.25R is treated as a BPM airfoil segment: chord c, span dr, local speed W, untripped boundary layer.
- **Angle of attack:** α* is the effective angle measured from **zero lift**, α − α_L0. BPM was fitted on the symmetric NACA 0012, so this is the usual adaptation for cambered sections.
- **Observer:** 50 m, 30° below the disk plane (θ = 120°, near the tonal maximum).
- **Directivity:** D̄_h is evaluated in each strip's own trailing-edge frame at 24 azimuth positions and averaged (time-averaged mean square), with Doppler frequency shift neglected.
- **Summing:** n rotors × B blades, added incoherently, in 1/3-octave bands from 100 Hz to 20 kHz, then A-weighted.

**Hover levels at 50 m, 30° below the disk:**

| Layout | Cap | rpm | Broadband [dBA] (peak band) | Tonal [dBA] | **Total [dBA]** | Δ payload [kg] |
|---|---|---|---|---|---|---|
| hex | 0.60 | 1973 | 49.4 (8 kHz) | 39.7 | **49.8** | 0 |
| hex | 0.50 | 1769 | 48.5 (6.3 kHz) | 35.5 | **48.7** | −0.29 |
| hex | 0.45 | 1587 | 47.5 (4 kHz) | 31.5 | **47.6** | −1.09 |
| tri | 0.60 | 2135 | 50.5 (5 kHz) | 46.6 | **52.0** | 0 |
| tri | 0.55 | 1955 | 49.7 (4 kHz) | 43.4 | **50.6** | −1.01 |
| tri | 0.50 | 1777 | 48.7 (3.15 kHz) | 40.0 | **49.2** | −2.47 |
| tri | 0.45 | 1601 | 47.6 (2.5 kHz) | 36.5 | **47.9** | −4.58 |

**Finding.**
- **Broadband sets the A-weighted level for both layouts.** For the hex, broadband is 9.7 dB above the tones; for the tri, 3.9 dB. The tones are 18–20 dB louder unweighted, but they sit at 66–700 Hz where A-weighting removes most of them. The broadband peak is at 2.5–8 kHz, where A-weighting is about 0 dB.
- **The hex is still quieter in total, by 2.2 dBA (not 7).** Entry 29's scaling had the tri 1 dB quieter in broadband. BPM puts it **1.1 dB louder**, because of the **angle-of-attack term SPL_α**, which entry 29's zero-α scaling left out. Each tri blade carries twice the thrust, so it runs at α* = 4.2° at 0.75R against the hex's 2.9°. The suction-side boundary layer thickens with α* (δ*_s = 1.05 against 0.81 mm), and SPL_α grows with it. Per blade the tri is 3.6 dB louder (its 0.76R strip 4.1 dB). With half as many blades (−3 dB) the vehicle is 0.6 dB louder unweighted and 1.1 dBA louder A-weighted, because the tri's spectrum peaks lower: at 5 kHz A-weighting adds 0.5 dB, while the hex's 8 kHz peak loses 1.1 dB.
- **Noise parity on total dBA costs the tri 1.9 kg** (it needs 49.8 dBA: cap ≈ 0.52), not entry 28's 2.8 kg. Applied to entry 24's ranking (hex − tri payload):

  | Scenario | No noise limit | Equal total dBA (BPM + Gutin) | Equal tonal dBA (entry 28) |
  |---|---|---|---|
  | 15 m/s, 303 Wh/kg | +1.73 | **+3.59** | +4.54 |
  | free, constant body, 303 | −2.19 | **−0.33** | +0.61 |
  | free, streamlined, 303 | −2.08 | **−0.22** | +0.72 |
  | free, bluff, 303 | −1.11 | **+0.75** | +1.69 |
  | free, bluff pre-tilted, 303 | −2.40 | **−0.54** | +0.41 |
  | free, constant body, 200 | +0.11 | **+1.97** | +2.91 |

  With the more complete noise model, a noise limit at the hex's level turns the free-speed case into a **near tie** with the 303 Wh/kg pack (the tri by 0.2–0.5 kg, or the hex by 0.75 kg with a bluff body). Everywhere else the hex leads.
- **Quieting either rotor is now slow going.** Broadband falls only about 1 dB per 0.05 of cap. The tri pays 1.9 kg for 2.2 dB, and the hex 1.1 kg for 2.2 dB. Edge treatments (serrations) aimed directly at SPL_α and SPL_s would likely be the cheaper lever for both.
- **Caveats:**
  - BPM is a 2-D, NACA 0012-based empirical model, applied here with α measured from zero lift.
  - Doppler and rotational effects are neglected.
  - Two broadband sources are missing: **tip-vortex noise** and **leading-edge noise from ingested turbulence** (in hover the rotor re-ingests its own recirculating wake). Both grow with blade loading and would add more to the tri than to the hex (queue item 37). The 2.2 dB gap is therefore more likely a lower bound than an upper one.

**Hand check: one strip at its peak Strouhal number.** BPM's spectrum shape A equals 0 dB at St = St₁, so the suction-side band level at the peak is simply

  SPL_s,peak = 10 log₁₀(δ*_s M⁵ L D̄_h / r_e²) + K₁ − 3

For the tri at 0.76R (W = 116.2 m/s, c = 135 mm, α* = 4.2°):
- M = 116.2/357.6 = **0.325**, so M⁵ = 3.62 × 10⁻³;
- R_c = W c/ν = 9.0 × 10⁵ > 8 × 10⁵, so **K₁ = 128.5** (eq. 47, the high-Re plateau);
- δ*_s = **1.05 mm** (eq. 6 at R_c, × 10^(0.0679 α*) from eq. 15);
- L = the strip width, 21.8 mm; D̄_h = 1; r_e = 50 m;
- SPL_s,peak = 10 log₁₀(1.05×10⁻³ × 3.62×10⁻³ × 0.0218 / 2500) + 125.5 = **20.71 dB**;
- peak frequency f = St₁ W / δ*_s with St₁ = 0.02 M^(−0.6) = 0.0393, so f = 0.0393 × 116.2 / 1.05×10⁻³ = **4.3 kHz**.

The code gives **20.64 dB in the 4 kHz band** (which spans 3.55–4.47 kHz) ✓. The same strip's angle term SPL_α peaks at **24.4 dB**, 3.7 dB above the suction side, which confirms that the angle-of-attack contribution sets the level here.

**Lesson.** At these blade loadings, broadband noise depends on loading per blade too, through α*, and not only on blade count and speed. Entry 29's zero-angle scaling had the sign of the tri–hex difference wrong. A model with the right physics in it (here, BPM's angle term), checked against a published reference before use, changed the answer.

**Next.**
- Queue item 37 (tip-vortex and ingested-turbulence noise).
- Item 33 (laminar section from coordinates).
- Item 13 (restate the coaxial case).
- Still waiting on the user: speed requirement, battery chemistry, and noise metric. Two of the three now decide the layout only at the margins: with a noise limit, free speed and 303 Wh/kg is a near tie.


## 31 — Tip-vortex formation noise (BPM section 5.3) (2026-11-18)

**Question.** Entry 30 left out the second BPM broadband source that grows with blade loading: noise from the **tip vortex forming** at the blade tip. Turbulence in the vortex core passes over the trailing edge near the tip. Does it change the tri–hex noise ranking?
- **Model:** `bpm.tip_vortex`, eqs. 61–67 transcribed from the report (pages 71–73).
- **Rotor study:** `src/explore/e31_tip_noise.py`, results `results/explore/e31_tip_noise.json` / `.png`.

**The model.**

  SPL_TIP = 10 log₁₀(M² M_max³ ℓ² D̄_h / r_e²) − 30.5 (log₁₀ St″ + 0.3)² + 126,   St″ = f ℓ / U_max

- **ℓ** is the spanwise size of the separated vortex core at the trailing edge:
  - rounded tip: ℓ/c = 0.008 α′_TIP;
  - flat (square) tip: ℓ/c = 0.0378 + 0.0095 α′_TIP for α′ > 2°. The report notes this flat-tip definition is not yet confirmed by experiment.
- **M_max** = M(1 + 0.036 α′_TIP) is the peak Mach number in the vortex.
- **Spectrum shape:** a parabola in log St″ with its peak at St″ = 0.5, so f_peak = 0.5 U_max/ℓ. A small core radiates high in frequency.
- **Level:** it grows as ℓ², so tip noise grows quickly with tip chord and tip angle.
- **The awkward input is α′_TIP** (eq. 66). It is the tip angle, scaled by how steeply the lift per unit span falls off at the tip compared with the report's reference wing. That reference loading is not given, so this entry brackets α′_TIP three ways:
  1. **edge angle:** α* of the outermost BEMT strip (r/R = 0.999). Prandtl's tip loss has already unloaded it, so α* ≈ 0.8–1.1°;
  2. **max-Γ angle:** α* at the station of peak bound circulation Γ = ½ W c C_l. The vortex rolls up the blade's bound circulation, so this is its strength in angle terms. Tri 6.7–8.0°, hex 3.9–4.8°;
  3. **circulation-equivalent angle:** the angle at which the tip section alone would carry that circulation, 2Γ_max/(2π W_tip c_tip). Tri 8.7–10.2°, hex 5.7–7.1°. This is not run; it would be louder than case 2.

**Validation.** The report's Figure 91 case is a rounded-tip model, 15.24 cm chord, U = 71.3 m/s, α′_TIP = 0.71 × 10.8° = 7.7°, observer at 1.22 m and 90°.
- Our code gives a peak of **52.9 dB at 4.9 kHz**. The report's prediction (open circles) peaks at **≈ 50.5 dB around 5–6 kHz**, with the same shape.
- This is about 2 dB high. Fig. 44 matched within 1 dB, so part of this offset may be in reading the figure, but the tip level carries at least ±2 dB here.

**Results at 50 m, 30° below the disk (tip-vortex dBA; total = trailing edge + tip + tones):**

| Layout | Cap | Tip chord [mm] | α* at max Γ | Tip, edge angle, flat | Tip, max-Γ, rounded | Tip, max-Γ, flat | TE (entry 30) | **Total, max-Γ flat** | Entry 30 total |
|---|---|---|---|---|---|---|---|---|---|
| tri | 0.45 | 110 | 8.0° | 30.9 | 39.4 | 46.5 | 47.6 | **50.3** | 47.9 |
| tri | 0.50 | 89 | 7.9° | 29.2 | 38.1 | 46.0 | 48.7 | **50.9** | 49.2 |
| tri | 0.55 | 71 | 7.1° | 27.2 | 34.1 | 43.7 | 49.7 | **51.4** | 50.6 |
| tri | 0.60 | 57 | 6.7° | 24.6 | 30.1 | 41.4 | 50.5 | **52.4** | 52.0 |
| hex | 0.45 | 67 | 4.8° | 25.7 | 25.6 | 38.3 | 47.5 | **48.1** | 47.6 |
| hex | 0.50 | 59 | 4.3° | 24.1 | 22.2 | 37.2 | 48.5 | **49.0** | 48.7 |
| hex | 0.55 | 52 | 3.9° | 22.3 | 18.8 | 36.2 | 49.3 | **49.9** | 49.7 |
| hex | 0.60 | 52 | 4.3° | 22.1 | 20.7 | 37.0 | 49.4 | **50.0** | 49.8 |

Equal-noise payload cost to the tri (tri held to the hex's cap-0.60 total):

| α′_TIP definition, tip shape | Hex total [dBA] | Tri total at cap 0.60 [dBA] | Tri payload cost [kg] |
|---|---|---|---|
| edge angle (≈ entry 30), rounded or flat | 49.8 | 52.0 | 1.86–1.89 |
| max-Γ, rounded | 49.8 | 52.0 | 2.15 |
| max-Γ, flat | 50.0 | 52.4 | **out of range**: the tri's quietest point (cap 0.45, 50.3 dBA) is still louder than the hex |

**Findings.**
- **Tip noise ranges from negligible to as loud as the trailing edge, depending on α′_TIP.** BPM's eq. 66 leaves the tip angle open for a rotor. A BEMT strip at the very tip reads about 1°, because tip loss has unloaded it. The physical vortex strength is the peak circulation, which corresponds to 4–10°. Since level grows as ℓ² ∝ α′², this choice moves the result by about 20 dB.
- **Under the loading-based reading, tip noise hurts the tri and barely touches the hex.** Each tri blade carries about twice the circulation, so its vortex is stronger: Γ_max is 4.9 against 2.31 m²/s at cap 0.60. The tri's total rises by 0.4–2.4 dB; the hex's by 0.2–0.5 dB.
- **Slowing the tri down makes its tip noise *worse*.** At lower caps the optimiser widens the blade, including the tip: 57 mm at cap 0.60, 110 mm at cap 0.45. A wider tip means a larger vortex core ℓ (ℓ ∝ c) and a lower peak frequency, 16 kHz down to 6 kHz. That moves the noise from where A-weighting removes 6.6 dB into the band where it counts fully. With flat tips, the tri's quieting curve flattens: going from cap 0.60 to 0.45 buys only 2.1 dBA for 4.6 kg, and the tri never reaches the hex's 50.0 dBA.
- **Tip shape is a real design lever.** A rounded tip has a much smaller core (ℓ/c = 0.008α against about 0.1 for flat) and stays 7–16 dB below the flat tip. That is consistent with rounded or swept tips on quiet rotors. Queue item 39 prices a rounded tip with a bounded tip chord for the tri.
- **Ranking:** the hex's noise advantage is 2.2 dBA (entry 30) to 2.4 dBA in total. With flat tips at the loading-based angle, a hex-level noise limit is unreachable for the tri. With rounded tips it costs 2.15 kg. At free speed with the 303 Wh/kg pack, that turns entry 30's near tie (tri ahead by 0.2–0.5 kg) into a hex lead of up to ≈ 0.1 kg (−2.19 + 2.15 = −0.04 for the constant body: an exact tie).

**Hand checks.**
- **Tip formula, tri cap 0.60, flat tip, max-Γ angle α′ = 6.69°**, tip chord 57.2 mm, W_tip = ΩR = 153.3 m/s:
  - ℓ = 0.0572 × (0.0378 + 0.0095 × 6.69) = **5.80 mm**;
  - M = 153.3/357.6 = 0.4288, and M_max = 0.4288 × (1 + 0.036 × 6.69) = 0.5321;
  - one tip at 50 m with D̄_h = 1: 10 log₁₀(0.4288² × 0.5321³ × 0.00580² / 2500) + 126 = **31.7 dB**, at f = 0.5 × 357.6 × 0.5321 / 0.00580 = **16.5 kHz**;
  - the code's single-source peak is 31.71 dB at 16.45 kHz ✓;
  - from peak band to vehicle dBA *(corrected in entry 33: an earlier version counted nine tips; the tri has 3 rotors × 2 blades = 6)*:
    - summing the whole parabolic spectrum of one tip adds +6.7 dB (OASPL 38.4 dB), and A-weighting it gives **34.8 dBA**;
    - six tips add 10 log₁₀ 6 = **+7.8 dB**;
    - the azimuth-averaged directivity D̄_h is 0.75, so **−1.2 dB**;
    - 34.8 + 7.8 − 1.2 = **41.4 dBA**, which matches the model exactly ✓.
- **Circulation ratio.** By Kutta–Joukowski, a strip at radius r makes thrust ρ (Ωr) Γ dr. With near-uniform Γ, blade thrust is T_b ≈ ρ Ω Γ (R² − r₀²)/2, so Γ ∝ T_b/Ω. Each tri blade carries 2× the thrust at 2135/1973 = 1.082× the hex's rpm, so Γ_tri/Γ_hex ≈ 2/1.082 = **1.85**. BEMT gives 4.90/2.31 = **2.12**. The remaining 15 % is because Γ is not uniform: the max-Γ value sits above the mean, more so for the tri's more peaked distribution.

**Lesson.** An empirical model is only as good as its least-defined input. Here BPM's tip angle has no unique meaning for a rotor with Prandtl tip loss: one reasonable reading makes the source vanish, another makes it dominant. The useful output is then the **bracket and the trend**. Whatever definition is used, tip noise penalises the tri, and it penalises the tri more as it slows down with a wider tip. This points to a design lever (the tip shape) rather than a single number.

**Next.**
- Queue item 39: rounded tip with a bounded tip chord for the tri; does it recover the 2.15 kg?
- Item 38: ingested-turbulence leading-edge noise.
- Item 33: laminar section.
- Still waiting on the user: speed requirement, battery chemistry, noise metric and distance.


## 32 — Bounding the tri's tip chord, flat and rounded tips (2026-11-18)

**Question.** Entry 31 found that the tri widens its tip as it slows down (57 → 110 mm from cap 0.60 to 0.45). Tip-vortex noise grows as ℓ² with ℓ ∝ c_tip, and moves into the A-weighted band. Does an upper bound on the tip chord let the tri reach the hex's noise level more cheaply?
- **Method:** the entry 13 tri optimiser (best-camber 44/24 blade, torque-sized motor, 15 m/s frame as in entry 28) re-run at caps 0.45, 0.50 and 0.55, with the chord at r = R bounded to ≤ 65 mm and ≤ 45 mm. The bound is enforced by rejecting any blade above it, and the start blade is tapered inside it. Six runs in 6 minutes on 4 cores.
- **Scoring:** each optimum scored for total hover dBA at 50 m, 30° below the disk. Total = BPM trailing edge (entry 30) + BPM tip vortex at the max-Γ angle, flat and rounded tip (entry 31) + Gutin tones.
- **Files:** `src/explore/e32_tip_chord.py`, `results/explore/e32_tip_chord.json` / `.png`.

**Results** (payload relative to the unbounded cap-0.60 tri optimum):

| Cap | Tip chord | Payload [kg] | TE [dBA] | Tip, flat | Tip, rounded | **Total, flat** | **Total, rounded** |
|---|---|---|---|---|---|---|---|
| 0.60 | free (57 mm) | 0 | 50.5 | 41.4 | 30.1 | 52.4 | 52.0 |
| 0.55 | free (71) | −1.01 | 49.7 | 43.7 | 34.1 | 51.4 | 50.7 |
| 0.55 | ≤ 65 | −1.02 | 49.8 | 42.4 | 32.4 | 51.3 | 50.7 |
| 0.55 | ≤ 45 | −1.18 | 50.8 | 36.9 | 25.7 | 51.7 | 51.5 |
| 0.50 | free (89) | −2.47 | 48.7 | 46.0 | 38.1 | 50.9 | **49.6** |
| 0.50 | ≤ 65 | −2.59 | 49.4 | 42.0 | 33.2 | 50.6 | 50.0 |
| 0.50 | ≤ 45 | −2.87 | 50.9 | 36.3 | 26.1 | 51.3 | 51.2 |
| 0.45 | free (110) | −4.58 | 47.6 | 46.5 | 39.4 | 50.3 | 48.5 |
| 0.45 | ≤ 65 | −4.96 | 49.4 | 41.2 | 33.4 | **50.2** | 49.7 |
| 0.45 | ≤ 45 | −5.44 | 51.0 | 35.6 | 26.5 | 51.3 | 51.2 |
| hex 0.60 | free (52) | (+1.73 over the tri at 15 m/s) | 49.4 | 37.0 | 20.7 | **50.0** | **49.8** |

**Findings.**
- **A tip-chord bound does not buy the tri its way to the hex's level.**
  - *Flat tips:* the 65 mm bound shifts the tri's curve about 0.3–0.4 dB quieter at caps 0.50–0.55. The best point is still 50.2 dBA at −4.96 kg, above the hex's 50.0. The 45 mm bound is worse at every cap.
  - *Rounded tips:* every bound makes the tri louder. The best tri at or below the hex's 49.8 dBA is the unbounded cap-0.50 blade (49.6 dBA, −2.47 kg); interpolating gives ≈ −2.15 kg (entry 31).
- **Why: the load has to go somewhere.** Lift per unit span is L′ = ½ρW²c C_l. At a given radius, thrust fixes L′ and the rpm fixes W, so **c × C_l is fixed**. A narrower outboard blade must run at a higher lift coefficient, so a higher α*. In the cap-0.45 optimum at 0.9R:

  | Tip bound | Chord at 0.9R | α* at 0.9R | Strip OASPL |
  |---|---|---|---|
  | free | 188 mm | 4.0° | 27.6 dB |
  | ≤ 65 mm | 122 mm | 5.8° | 29.8 dB |
  | ≤ 45 mm | 94 mm | 7.0° | 32.1 dB |

  BPM's SPL_α term (entry 30) grows with α*. The narrower chord also gives a thinner boundary layer, which moves the trailing-edge peak up (2.5 → 5 kHz) into the band A-weighting counts fully. **Trailing-edge noise rises 1.8–3.4 dB while tip noise falls 5–11 dB.** Trailing-edge noise was already the larger term, so the total gets worse.
- **The tip shape is the lever, not the tip size.** At the same blade, a rounded tip is 7–11 dB quieter than a flat one (ℓ/c = 0.008α against about 0.1). It costs nothing in BEMT terms, though it slightly reduces effective radius in practice. Specify rounded or swept tips for either layout.
- **Ranking unchanged:**
  - noise parity with rounded tips costs the tri ≈ 2.15 kg (2.47 kg at the nearest computed point);
  - with flat tips, parity is unreachable.
  - At free speed with the 303 Wh/kg pack the layouts are tied under a hex-level noise limit; everywhere else the hex leads.
- **What would help:** treating the trailing edge itself (queue item 40, serrations), or a planform optimised for low α* outboard (item 41). Both act on the term that now sets the dBA.

**Hand checks.**
- **c × C_l is fixed.** At 0.9R, halving the chord from 188 to 94 mm (same W within 0.4 %) should double C_l. With a lift slope near 0.1/deg that is roughly α* 4.0° → 8°. BEMT gives 7.0°: part of the load moves inboard, where the chord bound does not bite, and the induced inflow changes slightly. ✓ (direction and magnitude)
- **ℓ² scaling of tip noise** (flat tip, cap 0.45, free → ≤ 65 mm):
  - ℓ = c(0.0378 + 0.0095 α′): 0.1103 × 0.1135 = **12.5 mm** against 0.065 × 0.1222 = **7.94 mm** (code: 12.52 and 7.94 mm) ✓;
  - level: 20 log₁₀(12.52/7.94) = −3.95 dB from ℓ², plus 30 log₁₀(1.320/1.287) = +0.33 dB from the higher α′ in M_max³: **−3.6 dB** unweighted;
  - peak frequency f = 0.5 U_max/ℓ rises 5.9 → 9.6 kHz, where A-weighting goes from −0.1 dB to about −1.6 dB (interpolated; −2.5 dB at 10 kHz);
  - by hand ≈ **−5.1 dBA**; the model gives 46.5 → 41.2 = **−5.3 dBA** ✓.

**Lesson.** For a fixed thrust, a blade's lift has to be carried by chord × lift coefficient at each radius. Shrinking one factor raises the other. Noise sources that scale with one of them (tip noise with chord, trailing-edge noise with angle) trade against each other, so a constraint on one rarely reduces the total. The quieting has to come from a mechanism that lowers a source *without* moving load: tip shape, edge treatment, or lower tip speed.

**Next.**
- Item 40: trailing-edge serrations.
- Item 41: low-α* planform.
- Item 38: ingested turbulence.
- Item 33: laminar section.
- Still waiting on the user: speed requirement, battery chemistry, noise metric and distance.


## 33 — Trailing-edge serrations (2026-11-18)

**Question.** Entries 30–32 found that trailing-edge noise sets the A-weighted hover level of every design, and that planform changes only trade it against tip noise. Serrated (sawtooth) trailing edges reduce the trailing-edge source directly. What do they buy each layout under a noise limit, after paying for their drag and mass?
- **Files:** `src/explore/e33_serrations.py`, `results/explore/e33_serrations.json` / `.png`.

**Model (an engineering bracket, not a theory).**
- **Why serrations work:** a straight trailing edge scatters boundary-layer turbulence into sound most efficiently when the eddies cross the edge squarely. Teeth make the edge oblique to the flow, so the scattering is less efficient.
- **What theory and tests say:**
  - Howe's (1991) sawtooth theory gives a high-frequency reduction of about 10 log₁₀(1 + (4h/λ)²): 10–20 dB for typical teeth. It over-predicts badly.
  - Tests (Oerlemans et al. 2009 full-scale wind turbine; Gruber 2012 airfoils) measure **2–6 dB** in the mid band, with a slight *increase* above a crossover near f δ/U ≈ 1, where δ is the boundary-layer thickness.
- **How it is applied here, for each BPM strip and 1/3-octave band:**
  - SPL_p and SPL_s are reduced by **D** dB below the crossover f_c = U/δ (with δ ≈ 8 δ*, the 1/7-power-law profile) and raised by 1 dB above it;
  - the angle term SPL_α is reduced by only **D/2**, since tests show serrations are less effective at incidence;
  - scenarios D = 2, 4 and 6 dB;
  - tip vortex (rounded tip, max-Γ angle, entry 31) and Gutin tones are unchanged.
- **Cost:**
  - profile drag C_d × 1.03 (× 1.06 as sensitivity), re-run through BEMT hover;
  - pack energy scaled with hover power;
  - plus 15 g of serration per blade.

**Results at 50 m, 30° below the disk.** Cap-0.60 rotors, trailing-edge level / total [dBA]:

| Layout | D = 0 | D = 2 | D = 4 | D = 6 |
|---|---|---|---|---|
| tri | 50.5 / **52.0** | 49.1 / 51.1 | 47.8 / 50.3 | 46.6 / 49.6 |
| hex | 49.4 / **49.8** | 47.8 / 48.4 | 46.2 / 47.1 | 44.7 / 45.9 |

- **The trailing-edge level falls by less than D: tri 1.4 dB per 2 dB, hex 1.6 dB.** The tri's sections run at higher α*, so the SPL_α term, which gets only D/2, carries more of its energy.
- **The total falls by less still for the tri: 0.9 dB per 2 dB.** Its tones (46.6 dBA) are only 4 dB below its broadband, and serrations do nothing to tones.

**Cost of serrations** (cap 0.60, C_d × 1.03):

| | Profile share of hover power | Hover power | Pack | Serration mass | **Payload** |
|---|---|---|---|---|---|
| tri | 9.1 % | +0.28 % | +20.7 Wh | 6 × 15 g | **−0.16 kg** |
| hex | 16.4 % | +0.50 % | +25.9 Wh | 12 × 15 g | **−0.27 kg** |

With C_d × 1.06 the costs are −0.23 and −0.35 kg. The hex pays more, because it has twice the blades and a larger profile-power share: its sections run at lower C_l (0.34 against 0.50 at 0.75R), so drag is a larger part of its power.

**Under an absolute noise limit** (each layout picks its cap, and serrations if they pay off): hex − tri payload margin in kg, where a positive number means the hex leads.

| Limit [dBA] | No serrations: 15 m/s / free, 303 | D = 2 | D = 4 | D = 6 |
|---|---|---|---|---|
| none | +1.73 / −2.19 | — | — | — |
| 52 | +1.75 / −2.17 | +1.75 / −2.17 | +1.75 / −2.17 | +1.75 / −2.17 |
| 51 | +2.51 / −1.41 | +1.96 / −1.96 | +1.89 / −2.03 | +1.89 / −2.03 |
| **50** | +3.65 / −0.27 | +2.68 / −1.24 | +2.09 / −1.83 | +1.89 / −2.03 |
| 49 | +5.13 / +1.21 | +3.59 / −0.33 | +2.54 / −1.38 | +2.07 / −1.85 |
| 48 | tri unreachable | +5.26 / +1.34 | +3.65 / −0.27 | +2.64 / −1.28 |
| 47 | neither can comply | tri unreachable | +5.65 / +1.73 | +3.92 / −0.00 |

**Findings.**
- **At a limit near the hex's natural level (50 dBA), serrations restore the tri's free-speed lead.** The hex meets 50 dBA without them. The tri's noise cost falls from 1.92 kg (rounded tips, no serrations; 2.15 kg at exactly the hex's 49.8 dBA) to 0.95, 0.36 or 0.16 kg at D = 2, 4 or 6. At D = 6 it can stay at its full-speed cap and pays only the drag and mass. At free speed with the 303 Wh/kg pack, the tri leads by 1.2–2.0 kg instead of 0.3 kg without serrations. At 15 m/s the hex still leads by 1.9–2.7 kg.
- **Under tighter limits (47–48 dBA) both layouts need serrations, and the hex quiets more cheaply.** The hex reaches 47 dBA for just its 0.27 kg serration cost. The tri must also slow down, at 1–2.5 kg per dB. Below about 47–48 dBA (depending on D) the tri cannot comply at any cap tested.
- **Serrations are cheap for what they give.** At 0.16–0.27 kg, they are worth about 0.1 kg/dB for the hex and 0.04–0.16 kg/dB for the tri. Slowing the rotor costs 0.5–1 kg/dB for the tri (entry 28). Specify them, with rounded tips, for whichever layout is chosen, if any noise limit applies.
- **The answer depends on D,** which this model cannot pin down for a rotor at Mach 0.3–0.43. A 2 dB and a 6 dB serration lead to different free-speed winners at the 48 dBA limit. Queue item 42 is to calibrate D.

**Hand checks.**
- **Why the trailing-edge level falls by less than D** (tri cap 0.60, 0.76R strip at its peak band): the levels are SPL_α = 24.4, SPL_s = 20.6 and SPL_p = 14.4 dB, so mean-square shares of 0.66, 0.27 and 0.07.
  - With D = 2: the α share drops by 1 dB, the others by 2 dB, so 0.66 × 10^(−0.1) + 0.34 × 10^(−0.2) = 0.524 + 0.215 = 0.739, which is **−1.31 dB**.
  - The model gives −1.4 dB for the whole rotor ✓.
- **Profile power from a strip sum,** P₀ = B Σ ½ρW³ c C_d dr: tri 511 W against 5641 W per rotor (9.1 %), hex 347 W against 2113 W (16.4 %). A 3 % C_d increase should then add 0.27 % and 0.49 % of hover power; BEMT gives **0.28 % and 0.50 %** ✓.
- **Payload penalty, tri:** 0.28 % × 7365 Wh = 20.7 Wh; 20.7/303.3 = 0.068 kg of pack, plus 6 × 0.015 = 0.090 kg of serrations, so **0.158 kg** ✓.
- **Correction to entry 31.** That entry's hand check counted nine tips for the tri, but the tri has 3 rotors × 2 blades = 6. Six tips give +7.8 dB, not +9.5. The corrected chain matches the model exactly (34.8 dBA for one tip, + 7.8 dB, − 1.2 dB for the mean directivity, = 41.4 dBA). The entry has been corrected; no results change, because the code always used n × B.

**Lesson.** A treatment that acts on one noise source helps a design only in proportion to that source's share of the total. The hex's noise is almost all trailing-edge, so serrations work fully. The tri's has an angle-dominated trailing-edge term (half effective) and tones close behind (not affected), so the same serration helps it less per dB. Yet at a given limit it still helps the tri more in *kilograms*, because the tri's alternative, slowing down, is so expensive. How much a fix is worth depends on what it replaces.

**Next.**
- Item 42: calibrate serration effectiveness.
- Item 41: low-α* planform.
- Item 38: ingested turbulence.
- Item 33: laminar section.
- Still waiting on the user: speed requirement, battery chemistry, noise metric and limit.


## 34 — A wider blade at the same tip speed, to lower α* (2026-11-18)

**Question.** BPM's angle-of-attack term SPL_α carries about two-thirds of the tri's trailing-edge noise (entry 33). At each radius thrust fixes c × C_l (entry 32), so a **wider** blade at the **same rpm** must run at a lower C_l and α*. Does that make the rotor quieter, and at what payload cost?
- **Method:** scale the whole chord distribution of the entry 28 optima by s = 0.85 to 1.5. For each s, re-solve the collective pitch (a uniform twist offset, by Brent's method) so the hover rpm is unchanged. Tip speed is then fixed, so the Gutin tones barely move.
- **Scoring:**
  - payload by the entry 13 (tri) or entry 11 (hex) mission evaluation: blade mass, profile power and torque-sized motor all included;
  - noise as the total hover dBA at 50 m, 30° below the disk: BPM trailing edge + rounded-tip vortex + tones.
- **Files:** `src/explore/e34_solidity_alpha.py`, `results/explore/e34_solidity_alpha.json` / `.png`.

**Results** (Δ relative to each optimum at s = 1):

| Case | s | Solidity | Collective | α* at 0.75R | TE [dBA] | Total [dBA] | Δ total | Δ payload [kg] | kg per dB |
|---|---|---|---|---|---|---|---|---|---|
| tri, cap 0.60 | 0.85 | 0.128 | +0.72° | 4.90° | 51.6 | 52.8 | +0.80 | −0.30 | — |
| | **1.00** | 0.151 | 0 | 4.20° | 50.5 | **52.0** | 0 | 0 | — |
| | 1.15 | 0.174 | −0.52° | 3.68° | 50.1 | 51.7 | −0.31 | −0.19 | 0.61 |
| | 1.30 | 0.196 | −0.94° | 3.27° | 49.9 | 51.6 | −0.47 | −0.65 | 1.40 |
| | 1.50 | 0.226 | −1.43° | 2.80° | 49.7 | 51.5 | −0.55 | −1.48 | 2.72 |
| tri, cap 0.50 | 0.85 | 0.148 | +0.90° | 5.61° | 49.8 | 50.4 | +0.85 | −0.26 | — |
| | **1.00** | 0.174 | 0 | 4.77° | 48.7 | **49.6** | 0 | 0 | — |
| | 1.15 | 0.200 | −0.61° | 4.17° | 48.2 | 49.2 | −0.38 | −0.23 | 0.61 |
| | 1.30 | 0.226 | −1.08° | 3.69° | 47.9 | 49.0 | −0.56 | −0.66 | 1.18 |
| | 1.50 | 0.260 | −1.61° | 3.19° | 47.8 | 48.9 | −0.67 | −1.42 | 2.13 |
| hex, cap 0.60 | 0.85 | 0.111 | +0.46° | 3.43° | 50.0 | 50.4 | +0.56 | −0.75 | — |
| | **1.00** | 0.131 | 0 | 2.95° | 49.4 | **49.8** | 0 | 0 | — |
| | 1.15 | 0.151 | −0.37° | 2.57° | 49.1 | 49.5 | −0.27 | −0.38 | 1.38 |
| | 1.30 | 0.170 | −0.69° | 2.26° | 49.1 | 49.6 | −0.22 | −1.16 | 5.3 |
| | 1.50 | 0.197 | −1.02° | 1.93° | 49.4 | 49.9 | +0.04 | −2.58 | — |

Stall margin rises with s (tri 8.3 → 9.7°) and T/W at the cap is held (1.99–2.02, hex 2.34–2.38), so no constraint binds.

**Findings.**
- **Widening the blade lowers α* as expected, but the noise hardly moves.** The tri gains 0.3–0.7 dBA and the hex at most 0.3 dBA; the hex gets *louder* again at s = 1.5.
- **Why:** BPM's trailing-edge source has three parts, and α* trades them against each other. At the tri's 0.76R strip (s = 1 → 1.5):

  | Term | Peak [dB], s = 1 | s = 1.5 | Change | What drives it |
  |---|---|---|---|---|
  | SPL_α (angle) | 24.40 | 20.57 | **−3.83** | K₂ falls with α* (−4.19 dB), δ*_s +0.35 dB |
  | SPL_s (suction side) | 20.65 | 21.06 | **+0.41** | δ*_s grows with chord faster than it shrinks with α* |
  | SPL_p (pressure side) | 14.43 | 17.55 | **+3.12** | δ*_p grows with chord *and* with lower α* (0.376 → 0.568 mm) |
  | strip OASPL | 32.89 | 32.03 | **−0.86** | |

  Once the angle term falls to the level of the suction-side term, the suction-side boundary layer sets a floor. That floor grows with chord (δ* ∝ c^0.72 at R_c ≈ 10⁶). The hex starts with the angle term already weaker (α* 2.95°), so it reaches that floor at once.
- **The payload cost is the usual solidity cost.** Blade mass (0.47 → 0.69 kg per blade), profile power and a heavier motor (more chord at lower pitch means more torque at T/W 2) all grow. Narrowing the blade also loses payload, so s = 1 is the payload optimum in both directions. That confirms entries 13 and 11 had converged in chord scale.
- **As a quieting lever** it costs 0.6–2.7 kg/dB for the tri, the same as or worse than slowing down (0.5–1 kg/dB, entry 28), and far worse than serrations (about 0.04–0.16 kg/dB, entry 33). **Ranking unchanged.** The noise levers in order of cost are serrations, rounded tips (free), lower tip speed, then planform.

**Hand checks.**
- **α* change:** c × C_l is fixed, so C_l(1.5) = C_l(1)/1.5. At the tri's 0.75R strip, C_l = 0.495 → 0.330, ΔC_l = −0.165. With a lift slope of about 0.11/deg, Δα* ≈ −1.5°, so 4.20 → 2.70°. BEMT gives **2.80°** ✓. The small difference is the change in induced inflow from the larger solidity.
- **K₂ (eq. 49–50) at M = 0.325:**
  - γ = 27.094M + 3.31 = 12.11, γ₀ = 23.43M + 4.651 = 12.27, β = 72.65M + 10.74 = 34.35, β₀ = −34.19M − 13.82 = −24.93;
  - K₂ − K₁ = √(β² − (β/γ)²(α* − γ₀)²) + β₀;
  - at α* = 4.20°: √(1180 − 8.05 × 65.1) − 24.93 = **+0.70 dB**; at 2.80°: √(1180 − 8.05 × 89.7) − 24.93 = **−3.49 dB**;
  - change **−4.19 dB**, plus 10 log₁₀(δ*_s ratio 1.141/1.052) = +0.35 dB, giving **−3.84 dB**. The code gives −3.83 dB ✓.
- **δ*_s scaling with chord:** eq. 6 gives δ*₀/c = 10^(3.0187 − 1.5397 L + 0.1059 L²) with L = log₁₀ R_c. Its slope at L = 5.95 is d log(δ*₀/c)/dL = −1.5397 + 2 × 0.1059 × 5.95 = −0.279, so δ*₀ ∝ c^0.72. Then:
  - ×1.5 chord gives 1.5^0.72 = 1.339 (+1.27 dB);
  - α* 4.20 → 2.80° gives 10^(0.0679 × (−1.40)) = 0.803 (−0.95 dB);
  - net δ*_s ×1.075 (+0.32 dB). The code gives 1.141/1.052 = 1.085 ✓.

**Lesson.** Lowering α* attacks only one of the three trailing-edge terms. Before reducing a noise source by changing the design, check what grows in its place. Here the suction-side boundary layer, which scales with chord, takes over as soon as the angle term drops, and the noise barely moves. Serrations work on all three parts at once, which is why they are cheaper.

**Next.**
- Item 42: calibrate serration effectiveness.
- Item 38: ingested turbulence.
- Item 33: laminar section.
- Items 13 and 22 (coaxial restatement, lighter fairing).
- Still waiting on the user: speed requirement, battery chemistry, noise metric and limit.


## 35 — Max thickness moved aft: NACA 4-digit-modified sections 24xx-64 and 24xx-65 (2026-11-18)

**Question** (queue item 33). A "laminar" section keeps the pressure falling (a favourable gradient) further back along the chord, so the boundary layer stays laminar longer and skin friction drops. The cheapest way to try this here is to move the maximum thickness aft. Do NACA 24xx-64 and 24xx-65 sections (max thickness at 40 % and 50 % chord) beat the ordinary 24xx (30 %)?
- **Files:**
  - `src/explore/naca_mod4.py`: section coordinates;
  - `src/explore/xfoil_coords.py`: XFOIL polars from coordinates, with the same recipe and cache format as `airfoils.run_xfoil`;
  - `src/explore/e35_mod4_laminar.py`: the study;
  - `results/explore/e35_mod4_laminar.json` / `.png`;
  - 160 new polars in `results/polars/naca24tt-6[45]_*.json`.

**Generating the sections.** XFOIL's NACA command builds only 4- and 5-digit sections, so the coordinates are generated here. The NACA 4-digit-modified thickness (Abbott & von Doenhoff, §6.4), written for t = 0.20 and scaled by t/0.20:
- ahead of the max-thickness station m: y = a₀√x + a₁x + a₂x² + a₃x³;
- behind it: y = d₀ + d₁(1−x) + d₂(1−x)² + d₃(1−x)³;
- d₀ = 0.002 (trailing-edge half thickness); d₁ is the trailing-edge slope, tabulated against m (0.234 at m = 0.3, 0.315 at 0.4, 0.465 at 0.5);
- d₂ = (0.294 − 2(1−m)d₁)/(1−m)², d₃ = (−0.196 + (1−m)d₁)/(1−m)³. These make y(m) = 0.1 and y′(m) = 0 automatically (expanded below);
- a₀ = 0.296904 × I/6 sets the leading-edge radius (I = 6 is the normal radius);
- a₁, a₂, a₃ come from a 3 × 3 linear solve: y(m) = 0.1, y′(m) = 0, and y″(m) matching the aft polynomial (smooth curvature).

Camber is the ordinary 4-digit mean line (2 % at 40 %).

**Checks on the generator and on the coordinate route:**
- **-63 reproduces the 4-digit thickness:** the maximum difference is 0.31 % chord (at x = 0.63), with the maximum exactly at 30 %. That is the definition: the -63 section is the ordinary 4-digit section in modified form.
- **The aft polynomial meets the conditions at m** (with q = 1 − m):
  - value: 0.002 + d₁q + (0.294 − 2qd₁) + (−0.196 + qd₁) = **0.100** ✓;
  - slope: −d₁ − (0.588 − 4qd₁)/q − (−0.588 + 3qd₁)/q = −d₁ + d₁ = **0** ✓.
- **XFOIL from coordinates against XFOIL's built-in 2412** (Re 1.2 × 10⁶, M 0.3): the 2412-63 gives C_l 0.258 / C_d 0.00563 at α = 0, against 0.251 / 0.00586 built-in; at α = 4°, 0.744 / 0.00740 against 0.756 / 0.00702. The two routes agree within the small geometric difference ✓.

**Section results: aft thickness pays at high Reynolds number and costs at low.** C_d at C_l = 0.3, M 0.30, with transition x/c (upper/lower):

| t/c | Re | 24xx | 24xx-64 | 24xx-65 |
|---|---|---|---|---|
| 0.09 | 3 × 10⁵ | 0.00704 (0.85/1.00) | 0.00878 (0.92/1.00) | 0.01321 (0.94/1.00) |
| 0.09 | 6 × 10⁵ | **0.00530** (0.75/0.98) | 0.00560 | 0.00728 |
| 0.09 | 1.2 × 10⁶ | 0.00456 (0.65/0.88) | **0.00404** (0.79/0.93) | 0.00422 (0.87/0.94) |
| 0.09 | 2.4 × 10⁶ | 0.00481 (0.56/0.59) | 0.00367 (0.72/0.78) | **0.00314** (0.82/0.88) |
| 0.12 | 3 × 10⁵ | **0.00822** | 0.01032 | 0.01766 |
| 0.12 | 6 × 10⁵ | 0.00632 | **0.00624** | 0.00850 |
| 0.12 | 1.2 × 10⁶ | 0.00576 (0.58/0.68) | **0.00464** (0.75/0.85) | 0.00472 (0.85/0.91) |
| 0.12 | 2.4 × 10⁶ | 0.00556 | 0.00421 | **0.00351** (0.80/0.86) |

- **At high Re** the aft-thick sections hold laminar flow 15–30 % of chord longer: 37 % less drag for the -65 at 2.4 × 10⁶.
- **At low Re** the same steep recovery behind the thick point makes the laminar layer *separate* before it transitions (a laminar separation bubble). Its pressure drag more than doubles the -65's drag at 3 × 10⁵.
- **The crossover** is near Re ≈ 6–8 × 10⁵ for the -64 and about 10⁶ for the -65.
- **The rotor straddles it:** Re ≈ 7–10 × 10⁵ at 0.75R, and lower at the narrow tip and inboard.
- **The aft sections also lose maximum lift:** C_l,max 1.26 for the 24xx, 1.15 for -64, 1.08 for -65 (t/c 0.108, Re 8 × 10⁵). Their drag rises sooner above C_l 0.6: the "laminar bucket" in the figure's middle panel.

**Blade results** (entry 28 setup, tip-Mach cap 0.60, each layout's optimiser re-run from its best-camber blade):

| Layout | Section | Payload [kg] | Δ vs 24xx | Pack [Wh] | Hardware [kg] | Hover rpm | Solidity | C_l / C_d at 0.75R |
|---|---|---|---|---|---|---|---|---|
| hex | 24xx | +3.31 | 0 | 5140 | 29.09 | 1973 | 0.131 | 0.335 / 0.00579 |
| hex | **24xx-64** | **+3.65** | **+0.34** | 5199 | 28.55 | 2052 | 0.129 | 0.301 / 0.00535 |
| hex | 24xx-65 | +2.89 | −0.42 | 5407 | 28.62 | 2108 | 0.132 | 0.279 / 0.00618 |
| tri | 24xx | +2.14 | 0 | 7365 | 23.13 | 2135 | 0.151 | 0.495 / 0.00605 |
| tri | 24xx-64 | +2.20 | +0.06 | 7359 | 23.08 | 2132 | 0.156 | 0.446 / 0.00523 |
| tri | 24xx-65 | +1.56 | −0.58 | 7511 | 23.23 | 2113 | 0.163 | 0.430 / 0.00536 |

The tri uses its 44xx/new-section hybrid, with the new section outboard of t/c 0.12.

*(Entry 36 refines this: the -64's gain comes through motor sizing at T/W 2, not mission energy.)*

**Is the hex gain the section or the optimiser?** Evaluating each geometry with each set of polars (hex payload, kg):

| Geometry ↓ / polars → | 24xx | 24xx-64 | 24xx-65 |
|---|---|---|---|
| 24xx optimum | **+3.31** | +3.53 | +2.13 |
| 24xx-64 optimum | +3.18 | **+3.65** | +2.64 |
| 24xx-65 optimum | +2.80 | +3.53 | **+2.89** |

- **On the unchanged 24xx blade, the -64 section alone adds +0.22 kg.** Re-optimising for it adds 0.12 kg more. The optimiser trades the lower drag for a higher rpm (1973 → 2052) and a lighter motor (less torque at T/W 2). So the gain is real and mostly the section.
- **Each optimum is best with its own polars:** the 24xx geometry scores 3.31 with 24xx polars against 3.18 for the -64 geometry. So the 24xx baseline had converged.
- **-65 loses on any geometry,** because the hover strips inboard and at the tip run below its Re crossover.
- **The tri gains only 0.06 kg** because it works at C_l ≈ 0.45–0.50, on the upper edge of the -64's low-drag range. It also uses the -64 only outboard, where the hybrid puts the 24-family sections.
- **Caveat:** the -65's stall-margin routine returns NaN (its lift curve flattens before C_l,max), so the optimiser's stall constraint was not enforced for the -65. It still lost, so the conclusion stands, but the -65 numbers are not constrained optima.

**Ranking effect.** The +0.34 kg for the hex (+0.06 kg for the tri) moves every hex − tri margin by +0.28 kg:
- 15 m/s with the 303 Wh/kg pack: +1.73 → about +2.0 kg (hex);
- free speed, constant body, 303 Wh/kg: −2.19 → −1.9 kg (tri still ahead).

This is assuming the -64 gain carries over to the free-speed blades, which are optimised at their best-range speed (entries 17 and 24); the cruise sections run at lower C_l, where the -64 low-drag range applies, so it plausibly does.

**Hand check: drag from the transition location** (Re 1.2 × 10⁶, t/c 0.12, C_l 0.3). Mixed laminar/turbulent flat-plate friction for transition at x_t (entry 26):
- C_F(x_t) = 0.074 Re^(−0.2) − x_t [0.074 (x_t Re)^(−0.2) − 1.328 (x_t Re)^(−0.5)];
- C_d ≈ FF × (C_F,upper + C_F,lower), with FF = 1 + 2t/c + 60(t/c)⁴ = 1.252.

| Section | x_t upper / lower | C_F upper | C_F lower | Hand C_d | XFOIL C_d |
|---|---|---|---|---|---|
| 2412 | 0.58 / 0.68 | 0.00251 | 0.00219 | **0.00590** | 0.00576 ✓ (2.4 %) |
| 2412-64 | 0.75 / 0.85 | 0.00198 | 0.00167 | **0.00456** | 0.00464 ✓ (1.7 %) |
| 2412-65 | 0.85 / 0.91 | 0.00167 | 0.00148 | 0.00395 | 0.00472 ✗ |

- The 2412 and the -64 are friction-dominated, and the hand formula gets them within 2.5 %.
- For the -65, friction alone falls a further 0.0006, but XFOIL's drag does not follow. The 0.0008 gap is **pressure drag** from the steep aft recovery. FF = 1 + 2t/c + 60(t/c)⁴ was fitted to ordinary sections with max thickness near 30 % and does not see an aft-loaded thickness. This is the same physics that hurts the -65 at low Re: the closer the max thickness gets to the trailing edge, the harder the recovery.

**Lesson.**
- A "laminar" section is a bet on Reynolds number. Its low-drag range is real above the crossover Re and a liability below it, where laminar separation turns friction savings into pressure drag.
- A 1.37 m rotor in hover straddles that crossover, so the moderate change (-64) wins and the aggressive one (-65) loses.
- The swap test (old geometry, new polars) separates a section's own gain from the optimiser's re-tuning. Run it whenever a re-optimised result looks better for reasons that don't match the physics.

**Absolute-level caveat** (new queue item 44). The toroid session's CFD reports its rotor at 436 N against BEMT's 620 N. The same 30 % BEMT optimism showed in the earlier Caradonna–Tung check. Every comparison in this log is relative and is less exposed, but absolute payloads and the motor sizing at T/W 2 should be re-based on a CFD-corrected thrust once the toroid session's 2-blade reference solve (same mesh) reports.

**Next.**
- Item 43: section chosen by spanwise Reynolds number.
- Item 42: serration calibration.
- Item 38: ingested turbulence.
- Items 13 and 22.
- Still waiting on the user: speed requirement, battery chemistry, noise metric and limit.


## 36 — The aft-thick section only where Re is high; where the -64's gain actually comes from (2026-11-18)

**Question** (queue item 43). Entry 35's sections beat the 24xx above Re ≈ 7 × 10⁵ to 10⁶ and lose below it. Along the hover blade, Re peaks at 0.7–0.9R (hex 8 × 10⁵, tri 10⁶) and falls toward the narrow tip (4.7–6 × 10⁵) and the root. So: use the aft-thick section only in the high-Re band.
- **Method:** the BEMT polar lookup sees (t/c, Re, M, α) but not radius. t/c falls monotonically from root to tip (0.18 → 0.09), so the band is keyed on t/c:
  - ordinary 24xx at the tip (t/c < 0.097, r ≳ 0.93R);
  - the -64 or -65 in the band 0.097 ≤ t/c ≤ 0.15 (about 0.45–0.93R);
  - 24xx inboard on the hex, 44xx on the tri (through its existing hybrid);
  - linear ramps 0.005 wide in t/c between them.
- **Runs:** blades re-optimised at cap 0.60 as in entry 35, on 2 cores at nice 19 while the toroid session's CFD used 10.
- **Files:** `src/explore/e36_re_band.py`, `results/explore/e36_re_band.json`.

**Results** (payload, kg):

| Layout | Section layout | Payload | vs all-24xx | vs the same section uniform |
|---|---|---|---|---|
| hex | all 24xx (entry 35) | +3.31 | 0 | — |
| hex | 24xx tip + **-64 band** | +3.63 | +0.32 | **−0.03** |
| hex | all -64 (entry 35) | +3.65 | +0.34 | 0 |
| hex | 24xx tip + -65 band | +3.18 | −0.13 | +0.29 |
| tri | all 24xx outboard (entry 35) | +2.14 | 0 | — |
| tri | 24xx tip + -64 band | +2.14 | 0.00 | −0.06 |
| tri | 24xx tip + -65 band | +1.63 | −0.51 | +0.07 |

The stall margin now evaluates for the -65 cases (9.4° hex, 8.8° tri). Entry 35's NaN came from the -65 at the tip.

**Finding 1: the tip section does not matter, because little of the profile power is there.** Hex -64 blade in hover, BEMT strip sums (P_profile = B Σ ½ρW³ c C_d dr, power-weighted C_d):

| Span | Share of profile power | Re | C_d 24xx | C_d -64 | C_d -65 |
|---|---|---|---|---|---|
| 0–0.45R | 10.4 % | 0.6–6.3 × 10⁵ | 0.00800 | 0.00795 | 0.01174 |
| **0.45–0.93R** | **73.5 %** | 6.5–8.1 × 10⁵ | 0.00582 | **0.00552** (−5.2 %) | 0.00692 |
| 0.93R–tip | 16.1 % | 4.6–6.6 × 10⁵ | 0.00583 | 0.00614 (+5.3 %) | 0.00829 |

Profile power is 384 W of 2145 W per rotor (17.9 %).

*Hand estimate:*
- the -64 in the band saves 0.735 × 0.052 × 384 = **14.7 W** per rotor;
- the -64 at the tip costs 0.161 × 0.053 × 384 = **3.3 W**;
- banding (24xx tip) therefore saves 3.3 W × 6 = 20 W of hover, 0.16 % of the 12.7 kW hover power. That is about 8 Wh of pack, or **0.03 kg**. The optimiser gives −0.03 kg: the difference between "band" and "uniform" is at the noise level either way ✓.
- **The -65 loses even in the band.** At Re 6.5–8 × 10⁵ the band itself is below its crossover (entry 35: about 10⁶), so its power-weighted C_d there is 19 % *above* the 24xx.

**Finding 2: the -64's gain does not come from mission energy at all.** Entry 35's swap test (24xx geometry, -64 polars) left the pack unchanged (5140 Wh) and cut the hardware by 0.22 kg. The breakdown:

| Hex, 24xx geometry | Hover [W] | Cruise [W] | Pack [Wh] | P_max at T/W 2 [W] | Q_max [Nm] | Motor [kg] | ESC [kg] | Payload |
|---|---|---|---|---|---|---|---|---|
| 24xx polars | 12678 | 8250 | 5140 | 5932 | 20.51 | 1.841 | 0.440 | +3.31 |
| -64 polars | 12640 (−39) | 8258 (+8) | 5140 | 5826 (−1.8 %) | 20.16 (−1.7 %) | 1.810 | 0.434 | +3.53 |

- **The motors are sized at T/W 2.** There the rotor turns 2762 rpm, 1.40 × hover, so the outboard Re is about 1.1 × 10⁶. That is above the -64's crossover, and its drag advantage at 0.75R is **13 %** (C_d 0.00496 against 0.00571, C_l ≈ 0.34). In hover at Re 8 × 10⁵ it is only 5 %.
- Lower drag at full thrust means lower maximum power and torque, so a lighter torque-sized motor and ESC: 6 × (0.031 + 0.006) = **0.22 kg** ✓.
- **In the mission the section is a wash.** Hover saves 39 W, but cruise costs 8 W more, because the cruise sections run at lower C_l, where the -64 is draggier (it is worse below C_l ≈ 0.2: see the polar). The two cancel in the pack.

*Hand check, motor scaling:* the motor fit is m ∝ Q^n. With Q 20.51 → 20.16 Nm (ratio 0.9832) and motor 1.841 → 1.810 kg (ratio 0.9833), **n ≈ 1.0**. The payload gain is therefore directly proportional to the max-torque drop.

**What this means.**
- The -64's +0.34 kg on the hex is real, but it hangs on the motor model. It is the T/W-2 sizing condition, not the mission, that rewards low drag at Re ≈ 10⁶. If motors were chosen from a catalogue in steps, a 1.7 % torque drop might not move the choice at all, and the gain would vanish.
- **Ranking:** it adds to the hex's lead by up to about 0.3 kg, with that caveat.
- **Design rule:** choose sections at the condition that sizes the hardware, not only at the condition that uses the energy. For this vehicle those are T/W 2 (motors) and hover/cruise (pack), at different Reynolds numbers.

**Lesson.** A spanwise refinement only pays where the quantity it changes is concentrated. Three-quarters of the profile power sits at 0.45–0.93R, so the tip section hardly matters. And before crediting a gain to "lower drag", trace which term of the objective actually moved. Here it was the motor, not the battery.

**Next.**
- Item 45: a section designed for the T/W-2 point, only if catalogue motor steps don't swallow it.
- Item 42: serration calibration.
- Item 38: ingested turbulence.
- Items 13 and 22.
- Still waiting on the user: speed requirement, battery chemistry, noise metric and limit.


## 37 — Catalogue motors instead of the continuous mass fit: the ranking flips at 15 m/s (2026-11-18)

**Question** (raised by entry 36). Since entry 10, every optimiser has sized its motor continuously, m = 0.0909 τ^0.996 kg, fitted through three T-Motor units: U13II 0.975 kg / 11.4 N·m, U15II 1.740 kg / 18.0 N·m, U15XL 4.408 kg / 50.4 N·m (100 %-throttle test torques).
- The tri's optimum needs 50.6 N·m and lands on the U15XL (entry 13).
- The hex's optimum needs 20.5 N·m, between the U15II and the U15XL, so **its fitted 1.84 kg motor does not exist in this list.**

What happens with motors you can actually pick?
- **Method:**
  - re-score the cap-0.60 optima with the lightest listed motor whose test torque covers Q_max at T/W 2 (1 % tolerance);
  - re-optimise the hex to fit the U15II: motor mass fixed at 1.740 kg, a penalty on Q_max > 18.0 N·m, tip-Mach caps 0.60, 0.65 and 0.70;
  - a second pass with a 20× penalty, so the limit binds;
  - the tri likewise to the U15XL;
  - ESC mass keeps its P^0.7 scaling, and noise is scored as in entry 34.
  - 2 cores at nice 19, beside the toroid session's CFD.
- **Files:** `src/explore/e37_catalogue_motor.py`, `results/explore/e37_catalogue_motor.json`.

**Re-scoring the existing optima with catalogue motors:**

| Optimum | Q_max at T/W 2 | Fitted motor | Catalogue motor | Payload, fit | **Payload, catalogue** |
|---|---|---|---|---|---|
| tri, cap 0.60 (entry 28) | 50.6 N·m | 4.53 kg | U15XL 4.41 kg | +2.14 | **+2.50** |
| hex, cap 0.60 (entry 28) | 20.5 N·m | 1.84 kg | U15XL 4.41 kg (nothing between) | +3.31 | **−12.09** |

**Re-optimised to fit a catalogue motor:**

| Case | Penalty | Q_max [N·m] | Fits? | Payload [kg] | Hover / max rpm | Tip Mach at T/W 2 | T/W at cap | Solidity | Total dBA |
|---|---|---|---|---|---|---|---|---|---|
| hex → U15II, cap 0.60 | soft | 18.94 | no (+5 %) | +2.42 | 2148 / 3001 | 0.603 | 1.98 | 0.121 | 51.2 |
| hex → U15II, cap 0.60 | hard | 18.24 | no | +0.04 | 2259 / 3152 | — | **1.79** | 0.109 | 51.9 |
| hex → U15II, cap 0.65 | soft | 18.27 | no (+1.5 %) | +1.81 | 2325 / 3237 | — | 2.00 | 0.123 | 52.1 |
| **hex → U15II, cap 0.65** | **hard** | **18.00** | **yes** | **+0.86** | 2342 / 3264 | 0.656 | 1.96 | 0.115 | **52.4** |
| hex → U15II, cap 0.70 | soft | 18.22 | no (+1.2 %) | +1.73 | 2347 / 3266 | — | 2.30 | 0.123 | 52.2 |
| **tri → U15XL, cap 0.60** | soft | **50.49** | **yes** | **+2.47** | 2138 / 2995 | 0.602 | 1.99 | 0.149 | **52.1** |

(Hex payloads are in entry 11's frame and tri payloads in entry 13's; compare each layout's *change* against its own continuous-fit optimum, as below.)

**Findings.**
- **With catalogue motors, the hex fits the U15II only by spinning faster, at cap 0.65.** Torque is Q = P/Ω. At about 6 kW peak, 18 N·m needs Ω ≥ 331 rad/s (3160 rpm), a tip Mach of 0.63, above the 0.60 cap. At cap 0.60 the hex can only fit by cutting peak power: it gives up T/W (1.79) and still misses.
- **The cost is 2.45 kg for the hex** (+3.31 → +0.86): faster rotors draw more profile power (pack 5140 → 5462 Wh), the blades grow heavier for the flex test at higher rpm (hardware +1.4 kg), and the noise rises to 52.4 dBA.
- **The tri gains 0.33 kg** (+2.14 → +2.47), because the real U15XL is 0.12 kg lighter per arm than the fitted one at the same torque.
- **The hex − tri margin moves by −2.78 kg:**

  | Scenario | Continuous fit (entries 24/35) | **Catalogue motors** |
  |---|---|---|
  | 15 m/s, 303 Wh/kg | hex +1.73 | **tri +1.05** |
  | free speed, constant body, 303 | tri +2.19 | **tri +4.97** |
  | free speed, constant body, 200 | hex +0.11 | **tri +2.67** |

  The free-speed rows are shifted by the same hover-sized hardware change; the cruise-optimised blades would need a re-run for exact numbers.
- **The hex's noise advantage disappears too:** 52.4 dBA (hex at cap 0.65) against 52.1 (tri at 0.60). Entries 27–34 found the hex 2.2 dBA quieter at the same cap. Fitting the motor costs it that margin.
- **This is the largest single swing in the log:** larger than camber, sections, noise limits or body drag. It comes from a gap in a three-motor list, not from aerodynamics. **The layout choice now hinges on whether a ≈ 20–25 N·m, ≈ 2 kg motor exists** (queue item 46).
  - The U15II's 18.0 N·m is a 60 V *test point*, not a rated ceiling. Torque scales with current, so 20.5 N·m needs ≈ 143 A × 20.5/18.0 ≈ **163 A**. If its peak current at 24S allows that, the hex keeps its continuous-fit result (+3.31 kg), and with it the lead at 15 m/s.

**Hand checks.**
- **Torque from power and speed,** Q = P/Ω:
  - hex continuous fit: 5932 W at 2762 rpm (289.2 rad/s) gives **20.51 N·m** ✓;
  - hex at cap 0.65, hard penalty: 6152 W at 3264 rpm (341.8 rad/s) gives **18.00 N·m** ✓, tip Mach 341.8 × 0.6858 / 357.6 = 0.656;
  - tri: 15835 W at 2995 rpm gives **50.49 N·m** ✓.
- **Why cap 0.60 cannot fit:** Ω_needed = P/Q = 5950/18.0 = 330.6 rad/s, so tip Mach 330.6 × 0.6858/357.6 = **0.634 > 0.60** ✓. That matches the optimiser: at cap 0.60 it either violates torque (soft) or gives up T/W (hard).
- **Current for 20.5 N·m on the U15II:**
  - ideal motor constant K_t = 60/(2π·KV) = 0.1194 N·m/A, so the test point's 143 A gives 17.1 N·m by K_t against 18.0 measured (5 % above ideal, typical);
  - scaling the measured point: I ≈ 143 × 20.51/18.0 = **163 A**.
  - For the U15XL, the same check gives 175 A × 0.2513 = 44.0 N·m against 50.4 measured (+15 %): K_t from KV understates the larger motor more. So the measured test points, not K_t, are the reference.

**Lesson.** A smooth sizing law is a model of a *continuous* market. Before trusting an optimum built on one, check where it lands between real products. Here the hex landed in a 18–50 N·m gap, and the cost of falling back to a real motor (2.5 kg) outweighs everything the aerodynamic refinements of entries 20–36 found. The tri, by luck of entry 13, already sits on a real motor.

**Next.**
- **Item 46: survey 18–30 N·m motors** (other vendors) and the U15II's peak current. This decides the layout.
- The user's open questions (speed requirement, battery chemistry, noise limit) remain the other deciders.
- After that: items 45, 42, 38, 13, 22.

## 38 — Motor survey: real 24S motors fill the 18–50 N·m gap, and both layouts gain 3–5 kg (2026-11-18)

**Question.** Entry 37 found that the hex needs 20.5 N·m, which falls between the U15II (18 N·m) and the U15XL (50.4 N·m). Falling back to the U15II cost it 2.45 kg. Two questions follow. Can the U15II run above its 18 N·m test point? And does any real motor fill the gap?

**Method.**
- I surveyed vendor data sheets for 24S heavy-lift motors.
- Each motor is rated by its 100 %-throttle test-point torque, and its mass includes cables.
- Each motor's measured test current is checked against the ideal motor constant K_t.
- Two steps follow (src/explore/e38_motor_survey.py, reusing e37's machinery):
  - (1) re-score the entry-28 cap-0.60 optima with the surveyed list;
  - (2) re-optimise the blades (e11/e13 Nelder–Mead) with each candidate's mass fixed and a hard torque penalty at its test torque.
- The run was niced on 2 cores, because the toroid session's foamRun was running.

| Motor | Mass [kg] | Test torque [N·m] | Test current [A] | Test point | Rated current | kg per N·m |
|---|---|---|---|---|---|---|
| T-Motor U13II KV65 | 0.975 | 11.4 | — | (entry 37) | — | 0.086 |
| T-Motor U15II KV80 | 1.740 | 18.0 | 143 | 3546 rpm, 60 V, G40×13.1 | 143 A max continuous; **no peak listed** | 0.097 |
| **T-Motor MN1123 KV53** | **1.425** | **22.19** | 108.65 | 3632 rpm, 92 V, VZ42×16.5, 47.5 kgf | 108 A peak | **0.064** |
| T-Motor MN1320 KV49 | 2.070 | 32.44 | 148.96 | 3218 rpm, 92 V, NS45×17.5 | 150 A peak | 0.064 |
| Hobbywing V13823 60KV | 2.160 | 34.44 | 212.9 | 4260 rpm, 92 V, 42×16.5 | 213 A max | 0.063 |
| **Hobbywing V13828 55KV** | **2.465** | **43.09** | 244.9 | 3878 rpm, 92 V, 45×18 | 245 A max | **0.057** |
| T-Motor U15XL KV38 | 4.408 | 50.4 | 175 | (entry 13) | — | 0.087 |

Sources:
- T-Motor U15II: store.tmotor.com/goods.php?id=732
- T-Motor MN1123: uav-en.tmotor.com/2026/navigato_0403/1372.html
- T-Motor MN1320: uav-en.tmotor.com/2026/navigato_0403/1375.html
- Hobbywing V13823: hobbywing.com/en/products/v13823
- Hobbywing V13828: hobbywing.com/en/products/v13828

Rejected candidates:
- MAD M40C30 PRO (3.46 kg, 47.4 N·m): its figures come only from a reseller.
- Hobbywing X11 Plus: it runs on 12–14S, not this 24S bus.

**The U15II question.**
- The U15II's 143 A is its *maximum continuous* current, and no peak is published.
- 20.5 N·m would need ≈ 143 × 20.5/18.0 = 163 A, which is 114 % of that rating.
- Copper loss would rise by (163/143)² = 1.30.
- Running it there is not a sound design basis, so the U15II stays capped at 18 N·m.

**Results.**

Step 1, re-scoring the entry-28 optima. The blades stay the same; only the motor changes:

| Layout | Q_max needed | Fit mass | Catalogue pick | Payload (fit → catalogue) |
|---|---|---|---|---|
| hex | 20.51 N·m | 1.84 kg | MN1123, 1.425 kg | +3.31 → **+5.81** |
| tri | 50.62 N·m | 4.53 kg | U15XL, 4.408 kg | +2.14 → +2.50 |

Step 2, re-optimising with each motor's mass fixed and the hard torque penalty:

| Layout, motor, cap | Q_max / limit [N·m] | Fits | Payload [kg] | rpm hover / max | P_max [W] | Pack [Wh] | Hardware [kg] | σ | T/W at cap | Total [dBA] |
|---|---|---|---|---|---|---|---|---|---|---|
| **hex, MN1123, 0.60** | 22.19 / 22.19 | yes | **+6.37** | 1768 / 2489 | 5783 | 4989 | 26.52 | 0.141 | 2.93 | **48.5** |
| hex, MN1320, 0.60 | 26.83 / 32.4 | yes | +2.95 | 1427 / 2020 | 5674 | 4886 | 30.28 | 0.143 | 4.48 | 46.3 |
| tri, V13828, 0.60 | 43.94 / 43.1 | no (+1.9 %) | (+6.20) | 2468 / 3439 | 15821 | 7684 | 18.02 | 0.107 | 1.49 | 55.8 |
| tri, V13828, 0.65 | 43.42 / 43.1 | yes (within 1 %) | +6.22 | 2502 / 3486 | 15850 | 7694 | 17.96 | 0.106 | 1.71 | 56.0 |
| **tri, V13828, 0.70** | 43.10 / 43.1 | yes | **+6.87** | 2535 / 3530 | 15932 | 7654 | 17.45 | 0.115 | 1.95 | **55.9** |
| *(entry 37) hex, U15II, 0.65* | 18.00 / 18.0 | yes | +0.86 | 2342 / 3264 | 6152 | 5462 | — | 0.115 | 1.96 | 52.4 |
| *(entry 37) tri, U15XL, 0.60* | 50.49 / 50.4 | yes | +2.47 | 2138 / 2995 | 15835 | — | — | 0.149 | 1.99 | 52.1 |

(Hex payloads are in entry 11's frame and tri payloads in entry 13's. Compare each layout's change against its own continuous-fit optimum: hex +3.31, tri +2.14.)

**Findings.**
- **The gap was a list artefact, not a market gap.** The newer integrated 24S motors weigh 0.057–0.064 kg per N·m. The U15 line weighs 0.087–0.097, and the continuous fit (0.0909 τ^0.996) gives 0.090.
  - The fit was calibrated on the U-series, so it overstates the motor mass of *both* layouts by about 30 %.
- **The hex on the MN1123 gains +3.06 kg** over its continuous fit (+3.31 → +6.37 kg). This is +5.5 kg over its entry-37 U15II result.
  - The optimiser uses the extra 8 % torque headroom (22.19 against 20.5) to spin *slower*: hover 1973 → 1768 rpm, solidity 0.131 → 0.141. The lower profile power cuts the pack from 5140 to 4989 Wh.
  - It stays at cap 0.60, and the noise falls from 52.4 to **48.5 dBA**.
- **The tri gains even more, +4.73 kg (+2.14 → +6.87 kg), but by spinning faster.**
  - 43.1 N·m is 15 % below the 50.6 N·m it needed, and Q = P/Ω, so it must turn ≈ 15 % faster. The tip Mach rises to 0.70, and only at cap 0.70 does it reach T/W 1.95.
  - Each arm sheds 2.06 kg of motor (4.53 → 2.465 kg), which outweighs the +290 Wh of extra pack.
  - The cost is noise: **55.9 dBA**, +3.8 dB over the tri's U15XL design and +7.4 dB over the hex.
  - At cap 0.60 it cannot fit the torque (43.9 N·m, +1.9 %).
- **The MN1320 is the wrong choice for the hex** (+2.95 kg). It has 32 N·m but needs only 27, so 0.65 kg per arm of torque goes unused. Even so, it is the quietest design (46.3 dBA, hover 1427 rpm).
- **The hex − tri margin at 15 m/s and 303 Wh/kg** (continuous fit: hex +1.73 kg):

  | Comparison | Δhex | Δtri | Margin |
  |---|---|---|---|
  | entry 37 (U15II / U15XL) | −2.45 | +0.33 | tri +1.05 |
  | **free cap: hex MN1123 at 0.60, tri V13828 at 0.70** | +3.06 | +4.73 | **hex +0.06, a tie** |
  | equal cap 0.65 for the tri (V13828) | +3.06 | +4.08 | hex +0.71 |
  | equal noise: tri kept on the U15XL (52.1 dBA) vs hex 48.5 dBA | +3.06 | +0.36 | hex +4.4 |

  So on payload alone the layouts are tied, while on noise the hex is 7.4 dBA quieter. Entry 33 priced the tri's noise at 0.16–2.15 kg per few dB (serrations or a lower cap). At any noise limit below ≈ 55 dBA, **the hex leads by ≈ 1–4 kg**.
- **The free-speed and 200 Wh/kg rows** were not re-run (queue item 47). The motor saving is a hardware-mass change, so it shifts every scenario by about the same Δhex − Δtri = −1.67 kg against the continuous fit, provided the tri accepts cap 0.70.
- **Caveats:**
  - Both optimum layouts sit at *exactly* 100 % of the motor's test-point torque. The MN1123 test point is 108.65 A against a 108 A peak, and the V13828 is 245 A against a 245 A maximum.
  - That is the T/W-2 transient point. Hover runs at ≈ (T/W)^−1 of the peak thrust, about half the peak torque, so the continuous rating matters less. Even so, a 10–15 % reserve is the sound design basis (item 47).
  - The absolute payloads still carry BEMT's ≈ 30 % thrust optimism (item 44); the layout differences carry less of it.

**Hand checks.**
- **Motor constant K_t = 60/(2π·KV) against the measured test points.** These are the vendors' measurements at full throttle.

  | Motor | K_t [N·m/A] | K_t × I | Measured | Measured vs ideal |
  |---|---|---|---|---|
  | U15II KV80 | 0.1194 | 17.07 | 18.0 | +5 % |
  | MN1123 KV53 | 0.1802 | 19.58 | 22.19 | +13 % |
  | MN1320 KV49 | 0.1949 | 29.03 | 32.44 | +12 % |
  | V13823 60KV | 0.1592 | 33.88 | 34.44 | +1.6 % |
  | V13828 55KV | 0.1736 | 42.52 | 43.09 | +1.3 % |

  - The ideal K_t comes from the back-EMF: e = Ω/ω_KV with ω_KV = KV × 2π/60 rad/s per volt, and energy balance gives τ·Ω = e·I, so K_t = 1/ω_KV.
  - Real motors exceed this ideal because the published KV is usually measured at no load. The waveform and saturation also shift K_t, by up to ≈ 15 % here.
  - So torque at a new operating point is scaled from the *measured* test point (I ∝ Q), not from K_t.
- **Q = P/Ω for the optima:**
  - hex on the MN1123: 5783 W / (2489 × 2π/60 = 260.6 rad/s) = **22.19 N·m** ✓;
  - tri on the V13828 at cap 0.70: 15932 / (3530 × 0.10472 = 369.7) = **43.10 N·m** ✓;
  - hex on the MN1320: 5674 / (2020 × 0.10472 = 211.5) = 26.83 N·m ✓.
- **Why the tri needs cap 0.70 on the V13828:**
  - Ω = P/Q = 15900/43.1 = 368.9 rad/s, so the tip Mach is 368.9 × 0.6858/357.6 = **0.707** ✓ (log: 0.709).
  - At cap 0.60 the most it can reach is Ω = 0.60 × 357.6/0.6858 = 312.9 rad/s. That would need 15900/312.9 = 50.8 N·m, which is the U15XL again.
- **Payload change from hardware alone:**
  - Hex: 6 × (1.84 − 1.425) = 2.49 kg of motor saved, plus 150 Wh less pack at 303 Wh/kg = 0.50 kg, gives 2.99 kg against **3.06** from the optimiser ✓. The remainder is the ESC (∝ P^0.7) and the blade.
  - Tri: 3 × (4.53 − 2.465) = 6.20 kg of motor saved, minus 287 Wh more pack (0.95 kg), gives 5.25 kg against **4.73**. The remaining 0.5 kg is the heavier ESC and the hover-flex blade mass at higher rpm (hardware falls 23.13 → 17.45 kg, −5.68 kg, not −6.20) ✓.
- **Current check for the hex:**
  - at 22.19 N·m the MN1123 draws its test current, 108.65 A, its full 108 A peak;
  - at hover thrust (T/W 1) the torque is ≈ Q_max × (P_h/P_max) ≈ 22.19 × 0.45 ≈ 10 N·m, so ≈ 49 A, well within any continuous rating.

**Lesson.** Entry 37's lesson, "check where the fit lands between products", applies in both directions. The fit came from one product line, and a newer product generation is 30 % lighter per N·m. With real catalogue points, the motor is *where the optimiser chooses its rotor speed*: a motor with more torque than needed lets the rotor spin slower and quieter, while one with less forces it faster and louder. The layout decision is now less about payload, where the two are tied, than about noise, where the hex is ≈ 7 dBA quieter.

**Next.**
- Item 47: re-optimise with a 10–15 % torque reserve, and re-run the free-speed and 200 Wh/kg scenarios with these motors.
- Item 48: equal-noise comparison with the V13828 tri.
- The user's open questions (cruise speed, battery chemistry, noise limit) now decide between a payload tie and a 7 dBA noise advantage.
- After that: items 45, 42, 38.

## 39 — A 12 % torque reserve on the catalogue motors: the hex keeps a lead, and the tri is pushed past tip Mach 0.8 (2026-11-18)

**Question.** In entry 38 both re-optimised layouts ended at exactly 100 % of their motor's 100 %-throttle test torque:
- the MN1123 at 108.65 A against its 108 A peak;
- the V13828 at 245 A against its 245 A maximum.

A real design needs headroom for gusts, battery sag at the end of the flight, motor heating and model error. How much payload does a reserve cost each layout?

**Method.**
- The script is src/explore/e39_torque_reserve.py. It reuses e37's optimiser with the catalogue torques scaled by 0.88, a 12 % reserve.
- Torque is proportional to current (Q ≈ K_t I), so this also caps the current at 88 % of the test current:
  - MN1123: 0.88 × 22.19 = **19.53 N·m** (95.6 A);
  - V13828: 0.88 × 43.10 = **37.93 N·m** (215.5 A).
- The caps were chosen by hand:
  - The hex needed 20.5 N·m at cap 0.60 on the continuous fit, so it must spin a little faster. I ran caps 0.60 and 0.65.
  - The tri needs Ω ≈ 15 900 / 37.9 ≈ 419 rad/s, a tip Mach of about 0.80. I ran caps 0.75 and 0.80.
- The hex on the MN1320 already has a 17 % reserve (26.8 of 32.4 N·m in entry 38), so it carries over unchanged: +2.95 kg, 46.3 dBA.
- The run used 2 cores at nice 19, because the toroid session's foamRun was running.

| Layout, motor, cap | Q_max / limit [N·m] | Fits | Payload [kg] | rpm hover / max | P_max [W] | Pack [Wh] | σ | Tip Mach at T/W 2 | Total [dBA] |
|---|---|---|---|---|---|---|---|---|---|
| *hex, MN1123, 0.60, no reserve (entry 38)* | 22.19 / 22.19 | yes | *+6.37* | 1768 / 2489 | 5783 | 4989 | 0.141 | 0.50 | *48.5* |
| hex, MN1123, 0.60, reserve | 19.53 / 19.53 | yes | +4.96 | 2146 / 2989 | 6112 | 5312 | 0.121 | 0.60 | 50.9 |
| **hex, MN1123, 0.65, reserve** | 19.53 / 19.53 | yes | **+5.06** | 2139 / 2982 | 6099 | 5274 | 0.130 | 0.60 | **50.8** |
| hex, MN1320, 0.60 (17 % reserve already) | 26.83 / 32.4 | yes | +2.95 | 1427 / 2020 | 5674 | 4886 | 0.143 | 0.41 | 46.3 |
| *tri, V13828, 0.70, no reserve (entry 38)* | 43.10 / 43.1 | yes | *+6.87* | 2535 / 3530 | 15932 | 7654 | 0.115 | 0.71 | *55.9* |
| tri, V13828, 0.75, reserve | 38.65 / 37.93 | no (+1.9 %) | (+4.29) | 2918 / 4053 | 16407 | 7951 | 0.101 | 0.81 | 60.4 |
| **tri, V13828, 0.80, reserve** | 38.07 / 37.93 | yes (within 1 %) | **+4.37** | 2993 / 4159 | 16582 | 8024 | 0.102 | **0.835** | **61.4** |

(Payload frames are as before: compare each layout's change against its own continuous-fit optimum, hex +3.31 and tri +2.14.)

**Findings.**
- **The reserve costs the hex 1.3–1.4 kg** (+6.37 → +5.06 kg, still +1.75 over its continuous fit).
  - With 12 % less torque, the hex must turn 13.6 % faster at the same power. Hover rises from 1768 to 2140 rpm, the pack from 4989 to 5274 Wh (+0.94 kg) and the blades get heavier.
  - At cap 0.60 the T/W-2 point sits exactly on the cap (tip Mach 0.600). Cap 0.65 is only 0.1 kg better: the motor, not the cap, is now the limit.
  - Noise rises from 48.5 to 50.8 dBA.
- **The reserve costs the tri 2.5 kg and 5.5 dBA** (+6.87 → +4.37 kg; 55.9 → 61.4 dBA).
  - Its T/W-2 point now needs a tip Mach of 0.835. The tri's cap only binds near hover thrust (T/W at cap 1.83).
  - A tip Mach of 0.835 is beyond where this BEMT's compressibility model can be trusted: the polars stop at M 0.6 for profile drag and above that are extrapolated. So the true tri result is probably worse.
- **The margin at 15 m/s and 303 Wh/kg** (continuous fit: hex +1.73 kg):

  | Comparison | Δhex | Δtri | Margin |
  |---|---|---|---|
  | entry 38, no reserve | +3.06 | +4.73 | hex +0.06 (tie) |
  | **12 % reserve, both** | **+1.75** | **+2.23** | **hex +1.25** |
  | 12 % reserve, tri limited to its U15XL design at 52.1 dBA (entry 37, no reserve, so an upper bound) | +1.75 | +0.33 | hex +3.15 |

  The hex leads by ≈ 1.2 kg *and* is 10.6 dBA quieter. With a realistic reserve, the tri's catalogue gain from entry 38 came almost entirely from running its motor to the limit at very high tip speed.
- **External check on the absolute level (toroid session's CFD, 2026-11-18).** The reference solve is not finished but has stopped changing.
  - The 2-blade 54x18 (Phase 3 prop_ccw) makes **437 N and 35.9 N·m** at 2280 rpm in hot-day air. BEMT gives 585 N at the same point, so CFD is **25 % lower**.
  - Scaled at constant C_T to 2554 rpm on the U15XL, that is ≈ 549 N, T/W ≈ 1.32, at 45.0 N·m, right at the U15XL's 180 A × K_t ≈ 45.2 N·m.
  - This agrees with the 25–31 % BEMT over-prediction against Caradonna–Tung (item 44).
  - Caveat: the mesh's leading-edge cells (0.63 mm) are coarse, and coarse noses inflate torque in our CT run, so the CFD torque may be pessimistic.
  - **Consequence:** every absolute payload in entries 10–39 is optimistic, perhaps by several kg. A 25 % thrust shortfall at fixed rpm means the T/W-2 point needs ≈ (1/0.75)^(1/2) = 1.15 × the rpm, or more solidity. The 12 % torque reserve chosen here is *smaller* than that model error. Both layouts are hit, so the hex–tri comparison holds better than the absolute numbers. The torque-sized motors, though, would grow for both.

**Hand checks.**
- **Q = P/Ω:**
  - hex at cap 0.65 with reserve: 6099 W / (2982 × 0.10472 = 312.3 rad/s) = **19.53 N·m** ✓, tip Mach 312.3 × 0.6858/357.6 = **0.599** ✓;
  - tri at cap 0.80 with reserve: 16582 / (4159 × 0.10472 = 435.5) = **38.07 N·m** ✓, tip Mach 435.5 × 0.6858/357.6 = **0.835** ✓.
- **How much faster the reserve forces the rotor:**
  - Ω = P/Q. At the same power, a 0.88 torque limit means 1/0.88 = 1.136 × Ω.
  - Hex: rpm_max 2489 → 2982 = 1.198 ×, and P_max 5783 → 6099 = 1.055 ×. Then 1.136 × 1.055 = **1.199** ✓. The extra power is the profile power of the faster rotor (∝ Ω³ σ, with σ falling 0.141 → 0.130).
  - Tri: 3530 → 4159 = 1.178 ×; 43.10/38.07 × 16582/15932 = 1.132 × 1.041 = **1.178** ✓.
- **Current with the reserve:**
  - MN1123: 108.65 × 19.53/22.19 = **95.6 A**, against its 108 A peak (88 %).
  - V13828: 244.9 × 38.07/43.09 = **216 A**, against 245 A (88 %).
- **The hex's payload loss:** pack +285 Wh at 303 Wh/kg = 0.94 kg, plus blade mass 6 × 2 × (0.473 − 0.450) = 0.28 kg. That gives 1.22 kg against the optimiser's **1.31** ✓. The rest is ESC mass (∝ P^0.7, +5.5 % power).

**Lesson.** A margin is not free, and who pays more depends on how far the design already sits from its motor's limit. Without a reserve, entry 38's tri looked as good as the hex only because it ran its motor to the edge at tip Mach 0.71. With a 12 % reserve it needs 0.84, which is aerodynamically and acoustically unreasonable. The hex absorbs the same reserve with a 20 % rpm increase at tip Mach 0.60. Put the reserve into a design study *before* comparing options; otherwise the option nearest its limit looks best.

**Next.**
- Item 49: the tri on the U15XL with the same reserve.
- Item 50: the free-speed and 200 Wh/kg scenarios with the catalogue motors and the reserve.
- Item 44: fold the CFD's 25 % thrust shortfall into the sizing, for example by calibrating BEMT's lift slope or tip loss on the toroid session's 2-blade result when it finishes, then re-size the motors for both layouts.
- The user's open questions (cruise speed, battery chemistry, noise limit) remain.

## 40 — The tri on the heavier U15XL with the same reserve: quieter, but the hex still dominates (2026-11-18)

**Question.** With the 12 % torque reserve of entry 39, the tri on the V13828 (37.9 N·m) had to reach tip Mach 0.84 at T/W 2 and made 61.4 dBA. The U15XL (4.408 kg, 50.4 N·m) allows 0.88 × 50.4 = **44.35 N·m** under the same reserve. More torque lets the rotor spin slower for the same power (Ω = P/Q), at 1.94 kg more motor per arm. Is the heavier, slower, quieter tri better?

**Method.** src/explore/e40_tri_u15xl_reserve.py reuses e37's optimiser with e39's scaled catalogue, at caps 0.65 and 0.70 with the hard torque penalty. It ran on 2 cores at nice 19, because the toroid session's CFD was running.

| Tri design (12 % reserve) | Q_max / limit [N·m] | Payload [kg] | rpm hover / max | P_max [W] | Pack [Wh] | Hardware [kg] | σ | Tip Mach at T/W 2 | TE / tonal / total [dBA] |
|---|---|---|---|---|---|---|---|---|---|
| U15XL, cap 0.65 | 44.35 / 44.35 | +0.78 | 2443 / 3405 | 15816 | 7662 | 23.51 | 0.110 | 0.68 | 53.2 / 51.8 / 55.6 |
| **U15XL, cap 0.70** | 44.35 / 44.35 | **+1.68** | 2509 / 3486 | 16192 | 7636 | 22.69 | 0.125 | **0.70** | 51.8 / 53.1 / **55.5** |
| V13828, cap 0.80 (entry 39) | 38.07 / 37.93 | +4.37 | 2993 / 4159 | 16582 | 8024 | 18.73 | 0.102 | 0.835 | — / — / 61.4 |
| *for comparison: hex, MN1123, cap 0.65 (entry 39)* | 19.53 / 19.53 | *+5.06* | 2139 / 2982 | 6099 | 5274 | 26.89 | 0.130 | 0.60 | — / — / *50.8* |

(The tri payload is in entry 13's frame; its continuous-fit optimum is +2.14 kg.)

**Findings.**
- **The U15XL tri trades 2.7 kg of payload for 5.9 dB** against the V13828 tri: +1.68 kg at 55.5 dBA against +4.37 kg at 61.4. That is 0.46 kg per dB.
- **Cap 0.65 is worse than cap 0.70 on both counts** (+0.78 kg, 55.6 dBA). At the lower cap the optimiser cuts solidity (0.125 → 0.110) to save blade mass, so the blades work at a higher angle of attack, and the trailing-edge term rises 1.4 dB (entry 34's mechanism). The tonal term falls only 1.3 dB.
- **The hex dominates every tri variant with a reserve.** It has more payload than the best tri and is 4.7 dB quieter than the quietest:

  | 15 m/s, 303 Wh/kg, 12 % reserve | Δhex | Δtri | Margin | Noise (hex / tri) |
  |---|---|---|---|---|
  | tri on the V13828 | +1.75 | +2.23 | **hex +1.25 kg** | 50.8 / 61.4 dBA |
  | tri on the U15XL | +1.75 | −0.46 | **hex +3.67 kg** | 50.8 / 55.5 dBA |

  (Margin = hex +1.73 kg on the continuous fit + Δhex − Δtri.)
- **Why the tri has no good motor:** at T/W 2 it needs about 16 kW per rotor, three times the hex's per-rotor power. A motor sized with a reserve at a quiet tip Mach of 0.60 would need Q = 16 000 / 312.9 ≈ 51 N·m / 0.88 ≈ **58 N·m** of test torque. Nothing in the surveyed catalogue has that, and the U15XL's 50.4 is the ceiling. The hex needs 19.5 N·m per rotor, which sits in the densest part of the 24S market.
- **The BEMT caveat from entry 39 applies here too:** absolute payloads are optimistic, because CFD puts BEMT thrust 25 % high. A thrust correction raises every motor's torque requirement and pushes the tri even further past its catalogue ceiling. The hex has room: the MN1320 (32.4 N·m, 2.07 kg) is the next step up.

**Hand checks.**
- **Q = P/Ω:** 16192 W / (3486 × 2π/60 = 365.05 rad/s) = **44.36 N·m** ✓. Tip Mach = 365.05 × 0.6858 / 357.6 = **0.700** ✓.
- **Predicted rpm from torque alone:** Ω = P/Q = 15900 / 44.35 = 358.5 rad/s, about 3424 rpm, so tip Mach ≈ 0.688. The optimiser landed at 3486 rpm, 1.8 % higher, because peak power also rose 1.8 % (15900 → 16192 W) ✓.
- **Current:** 175 A × 44.35/50.4 = **154 A**.
- **Payload against the V13828 tri, from mass alone:**
  - hardware +3.96 kg (22.69 − 18.73);
  - pack −388 Wh at 303 Wh/kg = −1.28 kg;
  - net −2.68 kg, against the optimiser's **−2.69** ✓.
  - The hardware difference is smaller than the motor difference alone (3 × 1.943 = 5.83 kg), because the slower rotor needs lighter blades and the lower power needs smaller ESCs.
- **Noise per payload:** (4.37 − 1.68) / (61.4 − 55.5) = **0.46 kg/dB**. That is cheaper than entry 34's wider chord (0.6–2.7 kg/dB) and in the range of entry 33's serrations.

**Lesson.** Size the motor with a reserve, then ask which layout's motor lands in a populated part of the catalogue. The tri needs 3 × 16 kW rotors, which push past the largest 24S motors, so every way of fitting them costs payload, noise or both. The hex's 6 × 6 kW rotors sit where many motors exist, so it can choose torque headroom (MN1320) or low mass (MN1123). **With realistic motor reserves, the hex is the better layout at 15 m/s and 303 Wh/kg, by 1.3–3.7 kg and 4.7–10.6 dBA.**

**Next.**
- Item 50: re-run the free-speed and 200 Wh/kg scenarios with the catalogue motors and the reserve. Before entry 37 the tri led at free speed and 303 Wh/kg by 2.19 kg, so that row is where the tri could still win.
- Item 44: calibrate BEMT on the toroid session's 2-blade CFD (437 N against 585 N), then re-size the motors.
- Also: the hex on the MN1320 with the reserve already built in, +2.95 kg at 46.3 dBA, is the quiet option. Map the hex's payload–noise curve between the MN1123 and the MN1320 (item 51).

## 41 — All scenarios with catalogue motors and a 12 % reserve: the speed question decides again, and noise now sets the size of the tri's win (2026-11-18)

**Question.** Entries 37–40 compared the catalogue-motor designs exactly only at 15 m/s with the 303 Wh/kg pack. The other scenarios were estimated by shifting each layout's change against its own optimum. Item 50 asks how the full set of scenarios ranks: free cruise speed, the four body models and the 200 Wh/kg LiPo.

**Method.** src/explore/e41_scenarios_catalogue.py runs entry 24's full chain, the entry 17/18 vehicle model:
- arms, fairings, hover download and torque-sized ESCs;
- cruise trim at 14–30 m/s for each body model (constant, streamlined, bluff, bluff pre-tilted);
- mission energy.

Then entry 19's ranking picks each layout's best speed for each battery. The fitted motor mass is swapped for the catalogue mass, mass_sum −= n (m_fit − m_cat). The variants are:
- **base:** entry 24's blades with the continuous motor fit, as a regression check;
- **hex:** the MN1123 cap-0.65 blade from entry 39;
- **tri-V:** the V13828 cap-0.80 blade from entry 39;
- **tri-XL:** the U15XL cap-0.70 blade from entry 40.

That is 340 points on 2 cores at nice 19, beside the toroid CFD.

**Regression check.** The base variant reproduces entry 24's ranking to the printed hundredth in all ten scenarios. For example, at 15 m/s with 303 Wh/kg it gives +1.73 kg, and at free speed with a constant body it gives −2.19 kg, against entry 24's +1.73 and −2.19 ✓. The catalogue swap is the only change.

**Results** (hex payload minus tri payload in kg; positive means the hex wins):

| Speed, body | Battery [Wh/kg] | Continuous fit (entry 24) | **Hex MN1123 vs tri V13828** (50.8 vs 61.4 dBA) | **Hex MN1123 vs tri U15XL** (50.8 vs 55.5 dBA) |
|---|---|---|---|---|
| 15 m/s, constant body | 303 | +1.73 | **+0.73** | **+3.66** |
| 15 m/s, constant body | 200 | +6.07 | +5.68 | +8.08 |
| free, constant body | 303 | −2.19 | **−3.77** | **−0.42** |
| free, constant body | 200 | +0.11 | −1.15 | +1.88 |
| free, streamlined body | 303 | −2.08 | −3.69 | −0.34 |
| free, streamlined body | 200 | +0.29 | −1.03 | +2.02 |
| free, bluff body | 303 | −1.11 | −2.75 | +0.57 |
| free, bluff body | 200 | +1.76 | +0.40 | +3.39 |
| free, bluff pre-tilted | 303 | −2.40 | −4.08 | −0.72 |
| free, bluff pre-tilted | 200 | −0.20 | −1.62 | +1.44 |
| break-even battery, 15 m/s | | 382 | **328** | none (hex at any e_b) |
| break-even battery, free | | 203 | **174** | **277** |

The other quantities behind the ranking:
- Best speeds (tri / hex), free, constant body: 24.7 / 20.9 m/s (tri-V) and 24.5 / 20.9 m/s (tri-XL).
- Packs (tri / hex), constant body:

  | Pairing | 15 m/s | Free speed |
  |---|---|---|
  | tri-V / hex | 7963 / 5056 Wh | 5906 / 4363 Wh |
  | tri-XL / hex | 7650 / 5056 Wh | 5719 / 4363 Wh |

- Hardware difference, hex − tri: +8.85 kg (tri-V), +4.89 kg (tri-XL), +6.65 kg (fit).

**Findings.**
- **At a fixed 15 m/s the hex wins every catalogue case.** Its lead is +0.7 to +5.7 kg against the light V13828 tri and +3.7 to +8.1 kg against the U15XL tri, and it is 4.7–10.6 dBA quieter. Against the U15XL tri there is no break-even battery: the hex has both less hardware penalty and much less energy.
- **At free speed with the 303 Wh/kg pack, the catalogue makes the tri's win larger, if noise is free.**
  - The V13828 tri sheds 3 × (4.53 − 2.465) = 6.2 kg of motor, the hex only 6 × (1.84 − 1.425) = 2.5 kg. The hex's hardware penalty grows from 6.65 to 8.85 kg.
  - At free speed both layouts fly where the pack is small (tri 24.7 m/s, hex 20.9 m/s), so the hardware difference dominates.
  - The tri wins by **2.8–4.1 kg**, against 1.1–2.4 kg on the continuous fit.
- **Noise sets the size of the free-speed win.** The light tri is 61.4 dBA. Held to the U15XL design (55.5 dBA, 4.7 dB above the hex), the free-speed case becomes a **tie**, −0.7 to +0.6 kg depending on the body. At 200 Wh/kg the hex then wins every scenario, by +1.4 to +3.4 kg. So the tri's free-speed advantage is worth about (4.08 − 0.72)/(61.4 − 55.5) ≈ **0.57 kg per dB** of noise allowance (constant body: 3.35 kg / 5.9 dB). Entry 40's like-for-like hover estimate was 0.46.
- **The entry-39 shortcut was close but not exact.** It gave the hex − tri-V margin at 15 m/s with 303 Wh/kg as +1.25 kg; the full chain gives +0.73. For the tri-XL the shortcut gave +3.67, the chain +3.66.
  - The 0.5 kg difference for the tri-V is a frame effect. Entries 11 and 13 optimised the blades with their own hover and arm bookkeeping, and the chain adds the entry-14 fairings and hover download, which cost the fast-spinning V13828 tri more.
- **The decision table (with a 12 % torque reserve):**

  | Requirement | 303 Wh/kg | 200 Wh/kg |
  |---|---|---|
  | 15 m/s fixed, any noise limit | **hex** (+0.7 to +3.7 kg) | **hex** (+5.7 to +8.1 kg) |
  | free speed, no noise limit | **tri** (V13828, +2.8 to +4.1 kg) | **tri** (V13828, +1.0 to +1.6 kg), except bluff body: hex +0.4 |
  | free speed, ≈ 55 dBA limit | tie (−0.7 to +0.6 kg) | **hex** (+1.4 to +3.4 kg) |
  | free speed, limit ≤ 51 dBA | **hex**: no catalogue tri reaches it | **hex** |

**Hand checks.**
- **Payload difference from hardware and pack:** hex − tri = −(Δhw + Δpack/e_b), with Δ = hex − tri.
  - V13828, free speed, constant body, 303 Wh/kg: Δpack = 4363 − 5906 = −1543 Wh, so −(8.85 − 1543/303.3) = −(8.85 − 5.09) = **−3.76 kg** ✓ (printed −3.77).
  - The same at 15 m/s: Δpack = 5056 − 7963 = −2907 Wh, so −(8.85 − 9.58) = **+0.73 kg** ✓.
- **Break-even battery:** e_b* = −Δpack/Δhw, the specific energy at which the pack saving exactly pays for the extra hardware.
  - V13828, free: 1543 / 8.85 = **174 Wh/kg** ✓.
  - U15XL, free: (5719 − 4363)/4.89 = 1356/4.89 = **277 Wh/kg** ✓.
  - U15XL at 15 m/s: (7650 − 5056)/4.89 = 530 Wh/kg ✓ (printed 531). That is outside the 150–450 sweep, so the curve finds no crossing and the hex wins at every plausible battery.
- **Hardware swap:**
  - Δhw = 6.65 + [3 (4.53 − 2.465) − 6 (1.84 − 1.425)] = 6.65 + 6.20 − 2.49 = 10.36 kg, against the chain's **8.85**.
  - The 1.5 kg remainder is the re-optimised blades and ESCs. The V13828 tri runs at 1.18 × rpm and 1.04 × power, with heavier hover-flex blades; the hex runs at a higher rpm with blades 0.02 kg heavier each. Both change with the new designs, so the motor swap alone overstates the gap.
  - For the U15XL tri: 6.65 + 3 (4.53 − 4.408) − 2.49 = 4.53, against **4.89** ✓, within the blade and ESC changes.

**Lesson.** The same hardware change shows up very differently across scenarios. A lighter motor helps whichever layout is hardware-limited (the tri at free speed). A quieter, lower-energy design helps the energy-limited one (the hex at 15 m/s, or with a LiPo). With real catalogue motors and a reserve, three questions decide the layout: the speed requirement, the battery and the noise limit. **At 15 m/s or with a LiPo, the hex wins. At free speed with the semi-solid pack, the tri wins only if 55–61 dBA in hover is acceptable.**

**Next.**
- Item 52: the free-speed break-even noise limit, from a tri family between 55.5 and 61.4 dBA.
- Item 44: BEMT calibration on the toroid session's 2-blade CFD (437 N against 585 N).
- Item 51: the hex's payload–noise curve (MN1123 to MN1320).
- The three user questions now map directly onto the decision table above.

## 42 — The tri's noise is quantised by its motor: the free-speed case is a tie up to ≈ 55.5 dBA (2026-11-18)

**Question.** Entry 41 found that at free speed with the 303 Wh/kg pack and a constant body, the tri wins only by being loud:
- the V13828 tri at 61.4 dBA beats the hex MN1123 (50.8 dBA) by 3.77 kg;
- the U15XL tri at 55.5 dBA beats it by only 0.42 kg.

Item 52 asks for the noise limit at which the two tie. The plan was a tri family that spans the range between those two designs.

**Method.** src/explore/e42_tri_noise_family.py:
- re-optimises the U15XL tri with the 12 % reserve at caps 0.75 and 0.80, joining caps 0.65 and 0.70 from entry 40 and the V13828 at cap 0.80 from entry 39;
- runs each design through entry 41's chain (constant body, 14–30 m/s) and entry 19's best-speed pick at 303.3 and 200 Wh/kg;
- reuses the hex MN1123 points from entry 41.

It ran on 2 cores at nice 19, beside the toroid CFD.

| Tri design (12 % reserve) | Q_max [N·m] | rpm hover / max | Tip Mach at T/W 2 | σ | TE / tonal / total [dBA] | V_best [m/s] | hex − tri, free, 303 | free, 200 | 15 m/s, 303 |
|---|---|---|---|---|---|---|---|---|---|
| U15XL, cap 0.65 | 44.35 | 2443 / 3405 | 0.68 | 0.110 | 53.2 / 51.8 / 55.6 | 25.1 | **+0.14** | +2.32 | +4.53 |
| U15XL, cap 0.70 | 44.35 | 2509 / 3486 | 0.70 | 0.125 | 51.8 / 53.1 / 55.5 | 24.5 | −0.42 | +1.88 | +3.66 |
| U15XL, cap 0.75 | 44.35 | 2513 / 3493 | 0.70 | 0.124 | 51.7 / 53.0 / 55.4 | 24.5 | −0.40 | +1.93 | +3.69 |
| U15XL, cap 0.80 | 44.35 | 2499 / 3476 | 0.70 | 0.135 | 51.6 / 52.7 / 55.2 | 24.5 | −0.34 | +1.95 | +3.71 |
| V13828, cap 0.80 | 38.07 | 2993 / 4159 | 0.835 | 0.102 | 53.0 / 60.7 / 61.4 | 24.7 | **−3.77** | −1.15 | +0.73 |

(The table gives the tri's figures. Positive hex − tri means the hex carries more payload. The hex MN1123 is 50.8 dBA throughout.)

**Findings.**
- **The family does not span the range: it collapses onto the motor.**
  - Above cap 0.70 the U15XL's cap no longer binds. The torque limit sets the T/W-2 rotor speed: Ω = P/Q = 16 200/44.35 = 365 rad/s, a tip Mach of 0.70, whatever the cap.
  - So caps 0.70, 0.75 and 0.80 return the same design to within 0.1 kg and 0.3 dB.
  - With a fixed reserve, **the tri's noise is quantised by the motor catalogue:** ≈ 55.4 dBA on the U15XL, 61.4 dBA on the V13828, and nothing in between.
  - The "break-even noise" of 55.5 dBA from the linear fit (slope −0.59 kg/dB) is just the U15XL cluster's own level.
- **At free speed with 303 Wh/kg, the result by noise limit:**
  - below ≈ 55 dBA: the hex wins, since no catalogue tri gets there;
  - 55.2–55.6 dBA: a **tie**, −0.42 to +0.14 kg, well inside the motor-fit and BEMT bands;
  - at 61.4 dBA: the tri wins by 3.8 kg.
  - At 200 Wh/kg the hex wins against every U15XL design (+1.9 to +2.3 kg).
- **Why the V13828 tri is so loud:** its tonal term (60.7 dBA) dominates. Gutin's steady-loading tones grow very steeply with tip Mach, roughly 40 log₁₀ M at these numbers, and the V13828 needs M ≈ 0.835 at T/W 2. Its hover tip Mach, 2993/4159 × 0.835 = 0.60, is still above the U15XL's 0.50 (2499/3476 × 0.70). The BPM trailing-edge term barely changes (53.0 against 51.6), because loading per unit span is fixed by thrust.
- **Cap 0.65 on the U15XL is a slightly different design:** it binds below T/W 2 (T/W at cap 1.80), so it is lighter (σ 0.110) and faster-cruising (25.1 m/s). It is the only tri that loses to the hex at free speed, by 0.14 kg.
- **The reserve is now the tri's real noise knob.** Entry 38's V13828 tri with *no* reserve was 55.9 dBA at +6.87 kg (entry-13 frame), about as quiet as today's U15XL design but 5 kg better. The 12 % reserve is what drove it to tip Mach 0.84. So the size of the reserve, which should come from a gust and battery-sag requirement rather than a round number, now matters as much as the motor choice (item 53).
- **External: the toroid session's final reference CFD**, converged at 1500 iterations (Props/02_Toroidal_Rotor, read-only for this log).
  - The 2-blade 54x18 makes 437.4 N and 35.88 N·m at 2280 rpm, figure of merit 0.590.
  - On the U15XL it reaches only T/W 1.32 (2554 rpm at 45.0 N·m).
  - The toroid session fitted a pitch-loss / extra-drag correction to its CFD: a₀ = 3.97°, Δc_d = 0.0327 for the 2-blade, and 4.64° / 0.0358 for the toroid. So most of the BEMT gap is the method, not the geometry.
  - Its calibrated chord × collective sweep of the 2-blade gives at best T/W 1.44 on the U15XL (0.6 × chord, +6°), torque-bound at the edge of the sweep.
  - For this log: a calibrated BEMT will raise every torque requirement by roughly 20–30 %. That pushes the tri past the U15XL (no larger 24S motor in the survey) and the hex from the MN1123 toward the MN1320 (32.4 N·m), which entry 38 showed still works (+2.95 kg at 46.3 dBA). Item 44 is now the most important next step.

**Hand checks.**
- **Why caps above 0.70 make no difference:** the T/W-2 rotor speed comes from torque. Ω = P_max/Q_max = 16143/44.35 = **364.0 rad/s**, so tip Mach = 364.0 × 0.6858/357.6 = **0.698** (log: 0.698 at cap 0.80, 0.702 at 0.75). Any cap above 0.70 is inactive ✓.
- **Free-speed payload difference for U15XL cap 0.80:**
  - From entry 41, the hex's free-speed hardware is 22.69 + 4.89 = 27.58 kg and its pack 4363 Wh.
  - Δhw = 27.58 − 22.80 = 4.78 kg; Δpack = 4363 − 5712 = −1349 Wh.
  - hex − tri = −(4.78 − 1349/303.3) = −(4.78 − 4.45) = **−0.33 kg** ✓ (printed −0.34).
- **The tonal gap:** at fixed thrust and B·Ω scaling, Gutin's far-field level rises ≈ 40 log₁₀(M₁/M₂) dB in this tip-Mach range (entry 27's fit).
  - At the *hover* tip Mach: V13828 2993 rpm → M_h = 2993 × 0.10472 × 0.6858/357.6 = 0.601; U15XL 2499 rpm → 0.502.
  - 40 log₁₀(0.601/0.502) = 40 × 0.078 = **3.1 dB** from tip speed. The printed tonal gap is 60.7 − 52.7 = 8.0 dB; the other 4.9 dB comes from the V13828 tri's lower solidity, σ 0.102 against 0.135, which raises the blade loading coefficient and the harmonic amplitude.
  - The hover tip Mach alone explains less than half the tonal gap. The rest is blade loading, an effect entry 27's derivation lists, though I have not verified its size separately.
- **The linear break-even:** fitting all five points gives −0.59 kg/dB, crossing zero at 55.49 dBA. That is in the middle of the U15XL cluster, as expected for a two-cluster data set.

**Lesson.** A continuous sweep of a design knob (here the tip-Mach cap) can collapse when another limit binds first (here motor torque). The family then reports one point several times. Before reading a trade curve, check which constraint is active at each point. Here only the motor and its reserve move the tri's noise; the cap does not.

**Next.**
- Item 44, now the priority: apply the toroid session's calibration (a₀ ≈ 4°, Δc_d ≈ 0.033) to this BEMT. Re-check against the 437 N / 35.9 N·m point, then re-size both layouts' motors. The tri may have no catalogue motor left.
- Item 53: sweep the reserve.
- Item 51: the hex's payload–noise curve.

## 43 — BEMT calibrated on the 2-blade CFD: the thrust gap is a pitch loss, but the torque gap decides the motors (2026-11-18)

**Question.** The toroid session's OpenFOAM solve of this program's final 2-blade blade (results/blade_final.csv) converged at 1500 iterations:
- conditions: 2280 rpm, 45 °C sea-level air;
- result: **T = 437.4 N, Q = 35.88 N·m, FoM 0.590**;
- plain BEMT gives 584.8 N and 39.02 N·m.

How should the BEMT be corrected? What does the correction do to the designs and motors of entries 38–42?

**Method.** src/explore/e43_cfd_calibration.py.
- **Data source.** The CFD totals come from the toroid session's results/cfd_reference.json. I only read that folder; nothing there is changed.
- **Correction model** (the toroid session's): effective pitch θ − a₀, and section drag c_d + Δc_d. There are two fits:
  - **Full:** a₀ and Δc_d fitted to both thrust and torque;
  - **Thrust only:** a₀ fitted to thrust, with Δc_d = 0.
- **Designs tested** in entry 41's chain (constant body, 15 m/s), each against its catalogue motor's 12 % reserve torque:
  - the hex on the MN1123 (entry 39) and on the MN1320 (entry 38);
  - the tri on the V13828 (entry 39) and on the U15XL (entry 40).
- **Four ways to apply the correction:**
  - **plain:** no correction;
  - **as built:** a₀ and Δc_d both applied;
  - **re-pitched:** Δc_d only, because a designer would add a₀ of collective back;
  - **thrust only:** a₀ alone.
- It ran as one process at nice 19, because the toroid CFD was running.

**Calibration** (our blade, our polars, the same air: ρ = 1.1095 kg/m³, a = 357.6 m/s):

| Model | a₀ [°] | Δc_d | T [N] | Q [N·m] |
|---|---|---|---|---|
| plain BEMT | 0 | 0 | 584.8 | 39.02 |
| thrust only | 3.20 | 0 | 437.4 | **25.47** |
| full | **3.05** | **0.0333** | 437.4 | 35.88 |
| CFD | | | **437.4** | **35.88** |

The full fit reproduces the toroid session's uniform-a₀ (a1 = 0) values exactly (3.046° and 0.0333) ✓. That is a cross-check that both scripts use the same blade, polars and air.

**Design checks** (catalogue motor mass; mass_sum = hardware + pack/303.3; 15 m/s, constant body):

| Design | Model | Hover [W] | Pack [Wh] | Q_max / limit [N·m] | Fits | T/W at the limit |
|---|---|---|---|---|---|---|
| hex MN1123 | plain | 13 514 | 5 056 | 19.53 / 19.53 | yes | 2.00 |
| | thrust only, as built | 20 339 | 7 028 | 19.86 / 19.53 | no (+1.7 %) | 1.97 |
| | re-pitched (Δc_d only) | 28 050 | 10 711 | 39.31 / 19.53 | no | < 1 |
| hex MN1320 | plain | 12 582 | 4 753 | 26.83 / 28.51 | yes | 2.13 |
| | thrust only, as built | 13 359 | 4 913 | 22.90 / 28.51 | yes | 2.48 |
| | re-pitched | 19 115 | 7 547 | 40.45 / 28.51 | no | 1.41 |
| tri V13828 | plain | 18 047 | 7 963 | 38.07 / 37.93 | yes | 1.99 |
| | re-pitched | 32 871 | 14 851 | 67.40 / 37.93 | no | 1.12 |
| tri U15XL | plain | 17 557 | 7 650 | 44.35 / 44.35 | yes | 2.00 |
| | re-pitched | 29 803 | 13 282 | 73.13 / 44.35 | no | 1.21 |

The "as built" rows with both corrections are worse still: hover power rises 3–4 ×, because a 3° pitch loss on a lightly loaded blade drives it toward zero lift. They are left out of the table; the JSON has them.

**Findings.**
- **The thrust gap is a pitch loss, and a pitch loss is free to fix.** BEMT's 34 % thrust excess at fixed rpm is matched exactly by a uniform 3.2° loss of effective pitch. That is inflow the strip model does not see: 3-D tip relief and the root. A designer recovers it by building the blade 3.2° steeper. With a₀ alone and the pitch restored, every design is identical to plain BEMT. So **if only the thrust is wrong, entries 10–42 stand as they are**, apart from a 3° collective offset.
- **The torque gap is what matters, and it is large.**
  - With a₀ alone, BEMT gives 25.5 N·m at the CFD point, where CFD gives 35.9 N·m.
  - At equal thrust, CFD needs **1.16 × the rpm, 1.23 × the torque and 1.42 × the power** of plain BEMT (hand check below).
  - FoM 0.59 against 0.84. Our blades are designed at FoM ≈ 0.80–0.84, and real 1.4 m rotors measure 0.65–0.75.
- **The additive Δc_d does not transfer.** Fitted at one point it is 0.033, five times the section drag. Applied to the other designs it doubles the hex's hover power (13.5 → 28 kW), against the 1.42 × that the CFD itself implies at equal thrust.
  - A constant Δc_d penalises in proportion to σ V_tip³, so it hits fast, lightly loaded rotors hardest.
  - It absorbs whatever caused the CFD's extra torque, including the coarse leading-edge mesh (0.63 mm cells). The Caradonna–Tung validation found coarse noses inflate torque.
  - **So the Δc_d rows above are a lower bound on performance, not a prediction.**
- **What a CFD-consistent torque does to the motors.** Scale each design's T/W-2 torque by the CFD's 1.23 at equal thrust and compare with the 12 % reserve limits:

  | Design | Q_max plain | × 1.23 | Fits its motor? | Next catalogue motor that fits |
  |---|---|---|---|---|
  | hex MN1123 | 19.53 | **24.0** | no (19.5) | **MN1320** (28.5 limit, 2.07 kg) |
  | hex MN1320 | 26.83 | **33.0** | no (28.5) | **V13828** (37.9 limit, 2.465 kg) |
  | tri V13828 | 38.07 | **46.8** | no (37.9) | U15XL only without a reserve (50.4) |
  | tri U15XL | 44.35 | **54.5** | no (44.35) | **none**, no larger 24S motor in the survey |

  If the CFD torque is right, **the tri has no 24S motor that holds T/W 2 with a reserve**. The hex steps up one motor size, +0.65 kg per arm, to a design entry 38 already showed works.
- **The pack grows too** (*corrected in entry 44: the mission has little hover, so the pack grows only ≈ 2.5 %; the payload loss comes from heavier motors and ESCs*): 1.42 × the hover power is ≈ +40 % hover energy. That is roughly +2000 Wh for the hex and +3200 Wh for the tri at 15 m/s, about **+7 kg and +10 kg** of battery at 303 Wh/kg. The absolute payloads of entries 10–42 are likely **5–10 kg optimistic**, more for the tri. Cruise is less affected (lower C_T, profile-dominated), so the free-speed rows would shift less; that is not computed here.

**Hand checks.**
- **Equal-thrust ratios.** At fixed geometry, BEMT thrust goes as rpm² and power as rpm³, to first order.
  - Plain BEMT reaches CFD's 437.4 N at 2280 × √(437.4/584.8) = **1972 rpm**.
  - Its power there is 9318 × (1972/2280)³ = **6027 W**, and its torque 6027/(1972 × π/30 = 206.5) = **29.19 N·m**.
  - CFD: 8567 W and 35.88 N·m at 2280 rpm. So the power ratio is 8567/6027 = **1.42**, the torque ratio 35.88/29.19 = **1.23**, and the rpm ratio 2280/1972 = **1.16** ✓.
  - The rpm² and rpm³ scaling ignores Re and Mach effects over a 14 % rpm change, a ≈ 1–2 % error.
- **Figure of merit:** ideal power T^1.5/√(2ρA) = 437.4^1.5/√(2 × 1.1095 × 1.4776) = **5051 W**.
  - CFD: 5051/8567 = **0.590** ✓ (as printed).
  - Plain BEMT at equal thrust: 5051/6027 = **0.838**.
- **The thrust-only fit leaves the torque untouched:** a 3.2° pitch loss lowers the inflow angle, so the torque at 2280 rpm falls with the thrust (39.0 → 25.5 N·m). It does not explain the CFD's 35.9.
- **The motor table:** 19.53 × 1.229 = 24.0, 26.83 × 1.229 = 33.0, 38.07 × 1.229 = 46.8, 44.35 × 1.229 = 54.5 N·m ✓.

**Lesson.** A one-point calibration with two free parameters always fits, so the test is whether it *transfers*. Here the two corrections behave very differently:
- The **pitch loss** is a real, transferable correction (a known 3-D effect), and a designer can absorb it entirely.
- The **drag shift** is a catch-all. It contains a possible mesh artefact, and as a constant Δc_d it scales with the wrong variable.

The equal-thrust torque and power factors (1.23, 1.42) are the more honest way to carry the CFD into sizing. A second CFD point (refined nose, or another loading) is what would separate physics from mesh. Until then, the conclusion that does not depend on the torque question is this: **the hex has a catalogue motor one size up, and the tri has none.** So the CFD's torque gap, if real, settles the layout for the hex.

**Next.**
- Item 54: re-optimise both layouts under the ×1.23 torque, ×1.42 power model: hex on the MN1320 or V13828, tri on the U15XL with no reserve.
- Item 55: a refined-nose or second-loading CFD of the 2-blade reference to settle the torque. This needs the CFD machine time, so it is the user's and the toroid session's call.
- The user's open questions remain: cruise speed, battery and noise limit.

## 44 — Both layouts re-optimised with the CFD's equal-thrust factors: the hex keeps its reserve, and the tri survives only without one (2026-11-18)

**Question.** Entry 43 found that the toroid session's 2-blade reference CFD needs more than plain BEMT to make the same thrust:

| Quantity | CFD ÷ plain BEMT |
|---|---|
| rpm | **1.156 ×** |
| torque | **1.229 ×** |
| power | **1.421 ×** |

If that holds for every rotor, which motors do the two layouts end up on, and how do they rank?

**Method.** src/explore/e44_cfd_factors.py wraps bemt.hover_at_thrust so that every hover and T/W-2 point carries those three factors. The spanwise arrays are left untouched. The wrap applies in all the optimisers (e11/e13 through e37's job()) and in entry 41's chain. Assumptions:
- The factors are constant across loading and rotor, since they come from one CFD point.
- Cruise (edgewise) stays plain: no CFD exists for it, and it is profile- and parasite-dominated.

Jobs, all with the hard torque penalty:
- hex on the MN1320 with the 12 % reserve (28.5 N·m), caps 0.60 and 0.65;
- hex on the V13828 with the reserve (37.9 N·m), cap 0.60;
- tri on the U15XL with **no** reserve (50.4 N·m), and with the reserve (44.35 N·m), both at cap 0.70.

The best feasible hex and tri then go through the chain (constant body, 14–30 m/s). It ran on 2 cores at nice 19, beside the toroid CFD.

| Design (CFD factors) | Q_max / limit [N·m] | Fits | Payload [kg] | rpm hover / max | Tip Mach at T/W 2 | P_max [W] | Pack [Wh] | Hardware [kg] | σ | Total [dBA] |
|---|---|---|---|---|---|---|---|---|---|---|
| **hex MN1320, 12 % reserve, cap 0.60 / 0.65** | 28.51 / 28.51 | yes | **+0.79** | 1936 / 2733 | 0.55 | 8160 | 5342 | 30.94 | 0.135 | **48.0** |
| hex V13828, 12 % reserve, cap 0.60 | 33.11 / 37.93 | yes | −1.33 | 1643 / 2324 | 0.47 | 8057 | 5251 | 33.36 | 0.143 | 46.3 |
| **tri U15XL, no reserve, cap 0.70** | 50.62 / 50.4 | yes (within 1 %) | **−2.64** | 3087 / 4294 | **0.86** | 22762 | 8289 | 24.86 | 0.102 | **57.5** |
| tri U15XL, 12 % reserve, cap 0.70 | 46.55 / 44.35 | **no** (+5 %) | (−5.31) | 3483 / 4840 | 0.97 | 23596 | 8578 | 26.57 | 0.100 | 61.6 |
| *plain BEMT, hex MN1123 + reserve (entry 39)* | 19.53 | yes | *+5.06* | 2139 / 2982 | 0.60 | 6099 | 5274 | 26.89 | 0.130 | *50.8* |
| *plain BEMT, tri U15XL + reserve (entry 40)* | 44.35 | yes | *+1.68* | 2509 / 3486 | 0.70 | 16192 | 7636 | 22.69 | 0.125 | *55.5* |

(The hex payload is in entry 11's frame and the tri's in entry 13's. Compare each layout's change from its plain-BEMT row.)

The chain gives the full-vehicle comparison: hex MN1320 (12 % reserve) against tri U15XL (no reserve), constant body.

| Scenario | hex − tri [kg] | hex / tri mass sum [kg] | Packs [Wh] | Best V [m/s] | Plain BEMT (entries 41/42), tri with reserve |
|---|---|---|---|---|---|
| 15 m/s, 303 Wh/kg | **+3.39** | 48.72 / 52.11 | 5185 / 8265 | 15 / 15 | +3.66 |
| free, 303 Wh/kg | **−1.06** | 46.47 / 45.42 | 4504 / 6234 | 21.2 / 25.0 | −0.42 |
| 15 m/s, 200 Wh/kg | +8.64 | 57.55 / 66.19 | | | +8.08 |
| free, 200 Wh/kg | +1.89 | 54.14 / 56.03 | | | +1.88 |

**Findings.**
- **Both layouts lose about 4.3 kg, and the cause is mostly hardware, not battery.**
  - Hex: +5.06 → +0.79 kg. Its hardware rises 4.05 kg: six MN1320s at +0.645 kg each = 3.87 kg, plus ESCs sized for 8.2 kW instead of 6.1. The pack rises only 68 Wh.
  - Tri: +1.68 → −2.64 kg. Its hardware rises 2.17 kg (ESCs for 22.8 kW instead of 16.2) and its pack 653 Wh.
- **Correction to entry 43.** Entry 43 estimated the pack would grow by ≈ 40 % (+7 to +10 kg) because hover power grows 1.42 ×. That was wrong. The mission has only about 1.5 min of hover (as entry 16 recorded), so a 42 % rise in hover power adds only ≈ 130 Wh to the hex's pack at 15 m/s (5056 → 5185 Wh, +2.5 %). The CFD's cost is in the **torque- and power-sized hardware**: motors, ESCs and blade structure. Cruise energy dominates the pack and was not corrected.
- **The hex keeps its 12 % reserve on the MN1320 at 48.0 dBA.**
  - It is torque-bound at T/W 2 (28.51 N·m), so caps 0.60 and 0.65 give the same design.
  - Moving up again to the V13828 costs 2.1 kg more for 1.7 dB less noise, which is not worth it.
- **The tri flies only with no torque reserve.**
  - On the U15XL at its full 50.4 N·m test torque, the T/W-2 point needs a tip Mach of **0.86** (Ω = 22 762/50.62 = 449.7 rad/s), and it makes 57.5 dBA.
  - With the 12 % reserve it misses even at tip Mach 0.97.
  - Tip Mach 0.86 is far beyond this BEMT's polar range (M ≤ 0.6) and near drag divergence for a 9–10 % thick section. In reality it would be worse still.
- **On payload alone the ranking barely moves:** +3.39 kg (hex) at 15 m/s against +3.66 under plain BEMT, and −1.06 kg (tri) at free speed against −0.42.
  - But it now compares a hex with a 12 % reserve at 48 dBA against a tri with **no reserve** at 57.5 dBA and tip Mach 0.86.
  - At equal reserve the tri is not feasible at all with a catalogue 24S motor.
- **Robustness verdict.** Under the CFD's torque and power, the hex is the only layout with a feasible, reserved, quiet design. The tri's free-speed lead of 1.1 kg with a 303 Wh/kg pack rests on running its motor at 100 % of test torque at tip Mach 0.86. If the CFD's torque is real (item 55), this settles the layout for the hex. If it is a mesh artefact, entries 41–42 stand.

**Hand checks.**
- **Q = P/Ω:**
  - hex: 8160 W / (2733 × π/30 = 286.2 rad/s) = **28.51 N·m** ✓;
  - tri: 22 762 / (4294 × π/30 = 449.7) = **50.62 N·m** ✓.
- **Tip Mach at T/W 2:**
  - tri: 449.7 × 0.6858 / 357.6 = **0.862** ✓;
  - hex: 286.2 × 0.6858/357.6 = **0.549** ✓, below cap 0.60, which is why the cap is inactive.
- **The hex's hardware change:**
  - motors: 6 × (2.070 − 1.425) = **3.87 kg**;
  - ESCs: mass ∝ P^0.7, so the ratio is (8160/6099)^0.7 = 1.226, about +23 % on the ESC mass. With entry 10's ESC mass this adds ≈ 0.2 kg over six arms.
  - Total ≈ 4.07 kg, against **4.05** from the optimiser ✓.
- **The pack, hover only:**
  - ΔE_pack ≈ (K_P − 1) × P_hover × t_hover / η_batt. Hex: 0.421 × 13.5 kW = +5.7 kW. The 129 Wh rise corresponds to about 81 s of hover-equivalent energy (5.7 kW × 81 s / 3600 = 128 Wh).
  - That is consistent with the mission's hover-and-climb phases. Cruise at 15 m/s is uncorrected and holds the rest of the ≈ 5 kWh.
- **Payload comparison from mass sums:** hex − tri = sum_tri − sum_hex.
  - 15 m/s, 303: 52.11 − 48.72 = **+3.39** ✓.
  - Free, 303: 45.42 − 46.47 = **−1.05** ✓.

**Lesson.** Before propagating a correction, ask where it enters the objective. A 42 % hover-power penalty sounds catastrophic, but this mission spends 1.5 min in hover and 30+ min in cruise. The correction mostly acts through the *peak* sizing (motor torque, ESC power, tip speed at T/W 2), not through energy. That sizing is exactly where a layout already at the top of its motor range (the tri) breaks.

**Next.**
- Item 55, the deciding input: a refined-nose or second-loading CFD of the 2-blade reference, to tell whether the 23 % torque excess is real. This needs the CFD machine, so it is the user's and the toroid session's call; the toroid chain runs until about 23:00.
- A cruise (edgewise) correction is unknown and would move the free-speed rows. A forward-flight CFD point would be needed.
- Item 53: sweep the reserve. Item 51: the hex's payload–noise curve on the MN1320.

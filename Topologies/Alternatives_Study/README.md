# Parts Alternatives: ESC + Avionics boards

A trade study of every section of the topology 10/11 boards against the parts and methods that could replace them.
Each option is judged at topology 09's hover (iq 145 A, 86 V) and punch (iq 210 A) operating points, with one loss
method applied to every part.

**Document:** `Alternatives_Study.pdf` (7 pages: method, equations, tables, loss chart, recommendations).

| File | What it is |
|---|---|
| `alternatives_calc.py` | All numbers (`python3 alternatives_calc.py`): inverter loss per FET option, DC-link ripple per capacitor, aux-supply comparison, sensor range |
| `make_design_doc.py` | Builds the PDF and `inverter_losses.png` |

## Findings, in order of importance
1. **DC-link capacitors are under-rated.** 61.7 A rms of ripple at hover across 16 caps is 3.86 A each, 1.10× the 3.5 A spec (5.22 A at punch). Use about 23 caps at a derated 2.8 A, a higher-ripple 125 V series, or add film / MLCC.
2. **ACS770LCB-200B is out of range at punch** (210 A against ±200 A). ACS772ECB-250B uses the same CB footprint and covers ±250 A at 8 mV/A.
3. **Avionics TVS:** SMBJ110A clamps at 177 V (3.4 A), above the LTC7801's 150 V. Use an LTC4366 surge stopper or a clamp sized to stay under 150 V.
4. **Inverter FETs:** OptiMOS 5 stores 6–11× less reverse-recovery charge than IPB065N15N3 (478 nC). With the same 24 FETs, IPB044N15N5 (TO-263-7) gives 93 W at hover instead of 124 W. GaN (3 × EPC2305 per switch with an LMG1210) gives 46 W, but it is a board redesign.
5. **Gate resistors:** 10 Ω → 3.3 Ω per FET saves 16 W at hover; check the ringing.
6. **Keep** the LTC7063 drivers and the LTC7801 aux supply. The 120 V drivers and the LM5169 are too close to the bus, and the 6ED2742S01Q is last-time-buy.
7. **Topology 09's loss model is optimistic.** It gives 77 W at hover against 124 W from datasheet Qsw and hot Rds(on). Size heatsinks on the higher number until it is measured.

## Sources
- Infineon: [IPB065N15N3 G](https://www.infineon.com/assets/row/public/documents/24/49/infineon-ipb065n15n3g-ds-en.pdf), [IPB060N15N5](https://www.infineon.com/assets/row/public/documents/24/49/infineon-ipb060n15n5-datasheet-en.pdf), [IPB044N15N5](https://www.infineon.com/assets/row/public/documents/24/49/infineon-ipb044n15n5-datasheet-en.pdf), [IPT039N15N5](https://www.infineon.com/assets/row/public/documents/24/49/infineon-ipt039n15n5-datasheet-en.pdf), [IPT034N15NM6](https://www.infineon.com/assets/row/public/documents/24/49/infineon-ipt034n15nm6-datasheet-cn.pdf), [OptiMOS 6 150 V family](https://www.infineon.com/cms/en/product/power/mosfet/n-channel/optimos-and-strongirfet-latest-family-selection-guide/optimos-6-power-mosfet-150-v/), [6ED2742S01Q](https://www.infineon.com/assets/row/public/documents/24/49/infineon-6ed2742s01q-datasheet-en.pdf), [IRS2186](https://www.infineon.com/assets/row/public/documents/24/49/infineon-irs2186-datasheet-en.pdf)
- EPC: [EPC2305](https://epc-co.com/epc/documents/datasheets/EPC2305_datasheet.pdf)
- TI: [LM5168/LM5169](https://www.ti.com/document-viewer/LM5168/datasheet), [INA241](https://www.ti.com/lit/gpn/ina241b), [UCC27301A](https://www.ti.com/lit/gpn/ucc27301a), [LMG1210](https://www.ti.com/product/LMG1210)
- ADI: [LTC7063](https://www.analog.com/en/products/ltc7063.html), [LTC7138](https://www.radiolocman.com/datasheet/data.html?di=520625), [LTC4366](https://www.radiolocman.com/datasheet/data.html?di=400123)
- Allegro: [ACS770](https://www.allegromicro.com/-/media/files/datasheets/acs770-datasheet.pdf), [ACS772](https://www.allegromicro.com/-/media/files/datasheets/acs772-datasheet.pdf), [ACS37610](https://www.allegromicro.com/en/products/sense/current-sensor-ics/field-current-sensors)
- Littelfuse [SMBJ110A](https://www.digikey.com/en/products/detail/littelfuse-inc/SMBJ110A/688301); [Nichicon hybrid polymer to 125 V](https://www.elektormagazine.com/news/hybrid-aluminum-solid-electrolytic-capacitors-nichicon)
- Isolated bricks: [TRACO TEN 40WIR](https://tracopower.com/series/ten-40wir), [Cincon ECLB40W-110S12](https://www.digikey.com/en/products/detail/cincon-electronics-co-ltd/ECLB40W-110S12/9684559)
- Benchmarks: [Hobbywing XRotor H150A 24S FOC](https://www.hobbywing.com/en/products/xrotor-h150a-24s-foc-v1125), [TI TIDA-00916 drone ESC](https://ti.com/tool/TIDA-00916)

Assumptions (named in the code): Rds(on) ×1.6 hot (×1.5 GaN), capacitor ripple multiplier 0.8 below 100 kHz, LMG1210-class drive for GaN, Qrr taken at each datasheet's own test condition.

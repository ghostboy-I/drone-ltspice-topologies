# System flow chart: the whole series with part numbers

`System_Flowchart.pdf` (vector, zoom in freely), `System_Flowchart.png`, `System_Flowchart.svg`.
Rebuild with `python3 make_flowchart.py`. The script fails if any text spills out of its box.

What it shows:
- **Power path, one channel in full detail:** 24S pack → PDB → 8 AWG harness → ESC board 1 (AS150 input → DC link →
  3-phase inverter of 24 × IPB065N15N3 → ACS772 current sensors) → U15XL motor. Channels 2 and 3 are the same circuit.
- **Inside the ESC board:** LTC7801 aux buck → +12 V → LTC7063 gate drivers and LT1763-5 → LT1763-3.3 → STM32G431 MCU;
  PWM / enable / fault between the MCU and the drivers; current, bus-voltage and temperature sensing into the MCU's ADC pins;
  the AS5047P encoder over SPI.
- **Avionics power board:** Micro-Fit pack inputs → fuses → ES1D diode-OR → LTC7801 12 V → LT8641 5 V → LT3045 3.3 V,
  feeding the video transmitter, the flight controller + receiver and the sensors. The flight controller sends DShot to each ESC.
- **The series:** every block is tagged with the topologies (01–11) where that circuit was designed and verified.

Part numbers come from `../10_Hardware_Schematics_ESC_Avionics/*_BOM.csv`; MCU pin names from `ESC_Netlist.csv`.

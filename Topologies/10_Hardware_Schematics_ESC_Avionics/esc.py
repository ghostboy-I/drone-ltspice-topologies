"""ESC BOARD (one per motor): 24S -> DC link -> 3 x LTC7063 + 24 x IPB065N15N3 inverter -> U15XL, with its own
LTC7801 12 V aux supply, LT1763 5 V / 3.3 V, two ACS772 phase-current sensors and an STM32G431 running FOC.
python3 esc.py  ->  ESC_Board.asc (hover + throttle punch, starts at speed), ESC_BOM.csv, ESC_Netlist.csv
In LTspice the STM32 is a behavioural FOC block (topology 03/09) that reads the same ADC nets the real MCU would."""
import sys, math
from board import Board, Part
import hand_calc as h
from avionics import R, C, R0603, R0805, R1206, R2512, C0603, C0805, C1206, C1210

h09 = h.h09; A = h.AUX
g = lambda v: f"{v:.4g}"
FET = "IPB065N15N3"


def build(block=False):
    """block=True: the sheet used inside Power_System.asc (no test pack/harness, VBUS is a port, no directives)."""
    B = Board("ESC", "ESC BOARD")
    hv = h09.hover(); mp = hv["mp"]; iq0 = mp["iq"]; vb0 = hv["vbus"]
    # ================================================================== 1 power input, DC link, sensing of bus and temperature
    b = B.block("1  POWER INPUT + DC LINK: AS150 anti-spark connector, 24 x 150 µF polymer + 10 x 2.2 µF ceramic, bus and NTC sense",
                0, 0, 3000, 900)
    if not block:
        B.add(b, Part("V_PACK", "voltage", g(h.V_NOM), {"+": "VP", "-": "0"}, sim=True, spice=f"Rser={g(h09.Rpk)}"))
        B.add(b, Part("L_HARN", "ind", g(h09.Lh), {"1": "VP", "2": "VBUS"}, sim=True, spice=f"Rser={g(h09.Rh)}"))
    B.add(b, Part("J1", None, "", {"+": "VBUS", "-": "0"}, desc="Battery input, anti-spark", pn="AMASS AS150 with factory 8 AWG pigtail (male)",
                  fp="Drone_Power:AMASS_AS150_Pigtail_2x8AWG_P15mm", rating="150 A, 24S", note="anti-spark contact limits plug-in current"))
    B.add(b, Part("C1", "cap", "150µ", {"1": "VBUS", "2": "0"}, spice="Rser=20m", mult=16, desc="DC-link bulk, hybrid polymer",
                  pn="150 µF 125 V hybrid polymer, ≥3.5 A ripple, ESR ≤ 20 mΩ", fp="Capacitor_SMD:CP_Elec_10x12.5 (check the can size of the chosen part)", rating="125 V"))
    B.add(b, Part("C17", "cap", "1.1µ", {"1": "VBUS", "2": "0"}, spice="Rser=5m", mult=10, bomval="2.2µ", desc="DC-link ceramic, at the FETs",
                  pn="2.2 µF X7R 1210 (≈1.1 µF at 90 V)", fp=C1210, rating="250 V"))
    # 8 more bulk caps (Alternatives_Study): 16 carried 3.86 A rms each at hover, over their 3.5 A rating; 24 carry 2.57 A
    B.add(b, Part("C65", "cap", "150µ", {"1": "VBUS", "2": "0"}, spice="Rser=20m", mult=h.N_BULK - 16,
                  desc="DC-link bulk, hybrid polymer (ripple: 24 caps share 61.7 A rms at hover)",
                  pn="150 µF 125 V hybrid polymer, ≥3.5 A ripple, ESR ≤ 20 mΩ", fp="Capacitor_SMD:CP_Elec_10x12.5 (check the can size of the chosen part)", rating="125 V"))
    B.add(b, R("R1", "330k", "VBUS", "VS1", fp=R1206, rating="200 V", desc="Bus sense divider (3 in series for voltage rating)"))
    B.add(b, R("R2", "330k", "VS1", "VS2", fp=R1206, rating="200 V", desc="Bus sense divider (3 in series for voltage rating)"))
    B.add(b, R("R3", "330k", "VS2", "VBUS_SNS", fp=R1206, rating="200 V", desc="Bus sense divider (3 in series for voltage rating)"))
    B.add(b, R("R4", "33k", "VBUS_SNS", "0", desc="Bus sense divider bottom (100.8 V -> 3.25 V)"))
    B.add(b, C("C27", "10n", "VBUS_SNS", "0", desc="ADC filter"))
    B.add(b, R("R5", "10k", "+3V3", "TEMP", desc="NTC pull-up"))
    B.add(b, R("R6", "10k", "TEMP", "0", desc="NTC thermistor 10k B3950 (on the FET heatsink)", pn="NTC 10 kΩ B3950", fp=R0603))
    B.add(b, C("C28", "100n", "TEMP", "0", desc="ADC filter"))

    # ================================================================== 2 aux 12 V
    b = B.block("2  ESC AUX SUPPLY 12 V / 0.3 A  (U1 LTC7801, 440 kHz): gate drivers + logic. Each ESC makes its own (topology 07 lesson)",
                0, 1000, 3000, 1500)
    B.add(b, Part("U1", "LTC7801", "LTC7801", {
        "VIN": "VBUS", "RUN": "RUN_AUX", "OVLO": "OVLO_AUX", "SENSE+": "SNS_AUX", "SENSE-": "+12V", "SS": "SS_AUX", "VFB": "FB_AUX",
        "ITH": "ITH_AUX", "MODE": "0", "CPUMP_EN": "INTVCC_AUX", "PLLIN": "0", "PGOOD": "PG_AUX", "FREQ": "FREQ_AUX",
        "DRVSET": "DRVSET_AUX", "DRVUV": "0", "TG": "TG_AUX", "SW": "SW_AUX", "BOOST": "BST_AUX", "BG": "BG_AUX", "DRVCC": "DRVCC_AUX",
        "NDRV": "NDRV_AUX", "EXTVCC": "+12V", "INTVCC": "INTVCC_AUX", "GND": "0"},
        desc="150 V synchronous buck controller", pn="LTC7801EFE (TSSOP-24 with exposed pad)", fp="Drone_Power:Linear_HTSSOP-24-1EP_4.4x7.8mm_P0.65mm_EP2.74x3.25mm",
        rating="150 V"), dx=260)
    B.add(b, Part("Q1", "nmos", "BSC520N15NS3", {"D": "VBUS", "G": "TG_AUX", "S": "SW_AUX"}, desc="N-MOSFET 150 V 52 mΩ (top)",
                  pn="Infineon BSC520N15NS3", fp="Package_TO_SOT_SMD:TDSON-8-1", rating="150 V 21 A"))
    B.add(b, Part("Q2", "nmos", "BSC360N15NS3", {"D": "SW_AUX", "G": "BG_AUX", "S": "0"}, desc="N-MOSFET 150 V 36 mΩ (bottom)",
                  pn="Infineon BSC360N15NS3", fp="Package_TO_SOT_SMD:TDSON-8-1", rating="150 V 30 A"))
    B.add(b, Part("Q3", "nmos", "BSP89", {"D": "VBUS", "G": "NDRV_AUX", "S": "DRVCC_AUX"}, desc="N-MOSFET 240 V, DRVCC pre-regulator",
                  pn="Infineon BSP89", fp="Package_TO_SOT_SMD:SOT-223-3_TabPin2", rating="240 V"))
    B.add(b, Part("L1", "ind", "150µ", {"1": "SW_AUX", "2": "SNS_AUX"}, spice=f"Rser={g(A.dcr)}", desc="Power inductor 150 µH",
                  pn="shielded, Isat ≥ 1 A, DCR ≤ 0.4 Ω", fp="Inductor_SMD:L_Bourns_SRR1260", rating="Isat 1 A"))
    B.add(b, R("R7", "0.1", "SNS_AUX", "+12V", fp=R0805, pn="current sense 1 %", rating="0.25 W", desc="Current sense"))
    B.add(b, C("C29", "1n", "SNS_AUX", "+12V", desc="Sense filter"))
    B.add(b, C("C30", "0.1µ", "BST_AUX", "SW_AUX", rating="25 V", desc="Boost"))
    B.add(b, C("C31", "4.7µ", "DRVCC_AUX", "0", fp=C0805, rating="25 V", desc="DRVCC"))
    B.add(b, C("C32", "0.1µ", "INTVCC_AUX", "0", desc="INTVCC"))
    B.add(b, R("R8", g(h.R_RUN[0]), "VBUS", "RUN_AUX", fp=R1206, rating="200 V", desc="RUN divider (UVLO 59.8 V)"))
    B.add(b, R("R9", g(h.R_RUN[1]), "RUN_AUX", "0", desc="RUN divider bottom"))
    B.add(b, R("R10", g(h.R_OVLO[0]), "VBUS", "OVLO_AUX", fp=R1206, rating="200 V", desc="OVLO divider (118.8 V)"))
    B.add(b, R("R11", g(h.R_OVLO[1]), "OVLO_AUX", "0", desc="OVLO divider bottom"))
    B.add(b, R("R12", "64.9k", "FREQ_AUX", "0", desc="FREQ (≈ 435 kHz)"))
    B.add(b, C("C33", g(A.css), "SS_AUX", "0", desc="Soft-start (0.8 ms)"))
    B.add(b, R("R13", g(A.rtop), "+12V", "FB_AUX", desc="Feedback top"))
    B.add(b, R("R14", g(A.rbot), "FB_AUX", "0", desc="Feedback bottom"))
    B.add(b, R("R15", g(A.rith), "ITH_AUX", "ITHC_AUX", desc="Compensation RITH"))
    B.add(b, C("C34", g(A.cith), "ITHC_AUX", "0", desc="Compensation CITH"))
    B.add(b, C("C35", g(A.cithb), "ITH_AUX", "0", desc="Compensation CITHB"))
    B.add(b, R("R16", "100k", "INTVCC_AUX", "PG_AUX", desc="PGOOD pull-up"))
    B.add(b, R("R17", "100k", "DRVSET_AUX", "0", desc="DRVSET: 10 V gate drive"))
    for r in ("C36", "C37"):
        B.add(b, C(r, "5µ", "+12V", "0", fp=C1210, pn="10 µF X7R 1210 (5 µF at 12 V)", rating="25 V", desc="12 V output", spice="Rser=3m", bomval="10µ"))
    B.add(b, C("C64", "22µ", "+12V", "0", fp=C1210, pn="47 µF X7R 1210 (≈22 µF at 12 V)", rating="25 V", spice="Rser=3m", bomval="47µ",
               desc="12 V bulk: absorbs the bootstrap charge (3 x 1 µF) when the drivers enable"))
    for r in ("C38", "C39"):
        B.add(b, C(r, "1.1µ", "VBUS", "0", fp=C1210, pn="2.2 µF X7R 1210 (≈1.1 µF at 90 V)", rating="250 V", desc="Aux input, at Q1", spice="Rser=5m", bomval="2.2µ"))

    # ================================================================== 3 LDOs
    b = B.block("3  LOGIC SUPPLIES: U2 LT1763-5 (sensors, encoder), U3 LT1763-3.3 (MCU)", 3100, 1000, 1500, 1500)
    B.add(b, Part("U2", "LT1763-5", "LT1763-5", {"IN": "+12V", "_SHDN": "+12V", "OUT": "+5V", "Sense": "+5V", "BYP": "BYP5", "GND": "0"},
                  desc="500 mA low-noise LDO, 5 V", pn="LT1763CS8-5 (SO-8)", fp="Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", rating="20 V"), dx=200)
    B.add(b, C("C40", "1µ", "+12V", "0", fp=C0805, rating="25 V", desc="LDO input"))
    B.add(b, C("C41", "10µ", "+5V", "0", fp=C0805, rating="10 V", desc="LDO output", spice="Rser=5m"))
    B.add(b, Part("C42", None, "", {"1": "+5V", "2": "BYP5"}, desc="LDO bypass, DO NOT FIT (10 nF lowers noise but slows start-up to several ms)",
                  pn="10 nF X7R, DNP", fp=C0603))
    B.add(b, Part("U3", "LT1763-3.3", "LT1763-3.3", {"IN": "+5V", "_SHDN": "+5V", "OUT": "+3V3", "Sense": "+3V3", "BYP": "BYP33", "GND": "0"},
                  desc="500 mA low-noise LDO, 3.3 V", pn="LT1763CS8-3.3 (SO-8)", fp="Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", rating="20 V"), dx=200)
    B.add(b, C("C43", "1µ", "+5V", "0", fp=C0805, rating="10 V", desc="LDO input"))
    B.add(b, C("C44", "10µ", "+3V3", "0", fp=C0805, rating="10 V", desc="LDO output", spice="Rser=5m"))
    B.add(b, Part("C45", None, "", {"1": "+3V3", "2": "BYP33"}, desc="LDO bypass, DO NOT FIT (10 nF lowers noise but slows start-up to several ms)",
                  pn="10 nF X7R, DNP", fp=C0603))

    # ================================================================== 4 + 5 gate drivers and inverter legs
    nxt = dict(D=1, C=46, R=18, Q=4)
    def take(k, n=1):
        v = nxt[k]; nxt[k] += n; return v
    for i, ph in enumerate("ABC"):
        b = B.block(f"{4 + i}  LEG {ph}: U{4 + i} LTC7063 150 V half-bridge driver (bootstrap) + 2 x 4 IPB065N15N3", 0 + 1600 * i, 2600, 1550, 1700)
        u = f"U{4 + i}"
        B.add(b, Part(u, "LTC7063", "LTC7063", {
            "PWM": f"PWM_{ph}", "EN": "DRV_EN", "_FLT": "FAULT_N", "DT": f"DT_{ph}", "Vcc": "+12V", "BGVcc": "+12V", "BGRTN": "0",
            "BG": f"BG_{ph}", "SW": f"PH_{ph}", "TG": f"TG_{ph}", "BST": f"BST_{ph}", "SGND": "0"},
            desc="150 V half-bridge gate driver, floating grounds", pn="LTC7063EMSE (MSOP-12)", fp="Package_SO:MSOP-12-1EP_3x4.039mm_P0.65mm_EP1.651x2.845mm",
            rating="150 V", note="no KiCad library symbol"), dx=220)
        B.add(b, Part(f"D{take('D')}", "diode", "ES1D", {"A": "+12V", "K": f"BST_{ph}"}, desc="Bootstrap diode, ultrafast 200 V",
                      pn="ES1D", fp="Diode_SMD:D_SMA", rating="200 V 1 A"))
        B.add(b, C(f"C{take('C')}", "1µ", f"BST_{ph}", f"PH_{ph}", fp=C0805, rating="25 V", desc="Bootstrap capacitor (Qg/C = 0.3 V)"))
        B.add(b, C(f"C{take('C')}", "1µ", "+12V", "0", fp=C0805, rating="25 V", desc="Driver Vcc / BGVcc decoupling"))
        B.add(b, R(f"R{take('R')}", "{Rdt}", f"DT_{ph}", "0", desc="Dead-time resistor (≈140 ns at the FET threshold)", bomval="150k"))
        for side, pin, gate, d, s in (("high", "TG", f"G{ph}H*", "VBUS", f"PH_{ph}"), ("low", "BG", f"G{ph}L*", f"PH_{ph}", "0")):
            B.add(b, Part(f"R{take('R', 4)}", "res", g(h.RG_EACH / h.N_PAR), {"1": f"{pin}_{ph}", "2": gate}, mult=h.N_PAR, simm=False,
                          bomval=g(h.RG_EACH), desc=f"Gate resistor, one per FET ({side} side)", pn="1 %", fp=R0603))
            B.add(b, Part(f"R{take('R', 4)}", "res", g(10e3 / h.N_PAR), {"1": gate, "2": s}, mult=h.N_PAR, simm=False, bomval="10k",
                          desc="Gate-source pull-down, one per FET (keeps the FETs off while the driver is unpowered)", pn="1 %", fp=R0603))
            B.add(b, Part(f"Q{take('Q', 4)}", "nmos", FET, {"D": d, "G": gate, "S": s}, mult=h.N_PAR,
                          desc="N-MOSFET 150 V 6.5 mΩ, 4 in parallel per switch", pn="Infineon IPB065N15N3 G", fp="Package_TO_SOT_SMD:TO-263-2",
                          rating="150 V 130 A"))
    B.add(B.blocks[3], R(f"R{take('R')}", "10k", "+3V3", "FAULT_N", desc="Driver fault pull-up (open drain, wired-OR)"))

    # ================================================================== 7 current sense
    b = B.block("7  PHASE CURRENT: U7, U8 ACS772 ±250 A Hall sensors in phases A, B; 2/3 divider into the 3.3 V ADC", 4700, 1000, 2000, 1500)
    for ph, u in (("A", "U7"), ("B", "U8")):
        B.add(b, Part(f"R_CS{ph}", "res", "100µ", {"1": f"PH_{ph}", "2": f"MOT_{ph}"}, sim=True))          # the sensor's 100 µΩ conductor
        B.add(b, Part(f"B_CS{ph}", "bv", f"V=V(+5V)/5*({h.ACS_ZERO}+{h.ACS_GAIN}*I(R_CS{ph}))", {"+": f"ACSI_{ph}", "-": "0"}, sim=True))
        # 200 kHz bandwidth with a low output resistance (a 1 kOhm version lost 3 % into the 30 kOhm ADC divider)
        B.add(b, Part(f"R_BW{ph}", "res", "10", {"1": f"ACSI_{ph}", "2": f"ACS_{ph}"}, sim=True))
        B.add(b, Part(f"C_BW{ph}", "cap", g(1 / (2 * math.pi * 10 * h.ACS_BW)), {"1": f"ACS_{ph}", "2": "0"}, sim=True))
        B.add(b, Part(u, None, "", {"IP+": f"PH_{ph}", "IP-": f"MOT_{ph}", "VCC": "+5V", "VIOUT": f"ACS_{ph}", "GND": "0"},
                      desc=f"Hall current sensor phase {ph}, ±250 A, 8 mV/A", pn="Allegro ACS772ECB-250B-PFF-T",
                      fp="Sensor_Current:Allegro_CB_PFF", rating="±250 A"))
        B.add(b, Part(f"B_ACSQ{ph}", "bi", f"I={h.I_ACS}*limit(V(+5V)/4.5,0,1)", {"+": "+5V", "-": "0"}, sim=True))
        B.add(b, C(f"C{take('C')}", "100n", "+5V", "0", desc=f"{u} decoupling"))
        B.add(b, R(f"R{take('R')}", "10k", f"ACS_{ph}", f"ISNS_{ph}", desc="ADC scaling (2/3), top"))
        B.add(b, R(f"R{take('R')}", "20k", f"ISNS_{ph}", "0", desc="ADC scaling (2/3), bottom"))
        B.add(b, C(f"C{take('C')}", "1n", f"ISNS_{ph}", "0", desc="ADC anti-alias (24 kHz with 6.7 kΩ)"))

    # ================================================================== 8 MCU + connectors
    b = B.block("8  MCU U9 STM32G431CBT6 (FOC firmware) + connectors.  In simulation: the behavioural FOC block below", 4700, 2600, 2000, 1700)
    mcu = {"PA8": "PWM_A", "PA9": "PWM_B", "PA10": "PWM_C", "PA0": "ISNS_A", "PA1": "ISNS_B", "PA2": "VBUS_SNS", "PA3": "TEMP",
           "PB0": "DRV_EN", "PB12": "FAULT_N", "PA4": "ENC_CS", "PA5": "ENC_SCK", "PA6": "ENC_MISO", "PA7": "ENC_MOSI",
           "PA15": "SIG_IN", "PB6": "TLM_TX", "PA13": "SWDIO", "PA14": "SWCLK", "PG10": "NRST", "PB8": "BOOT0", "VBAT": "+3V3",
           "PC13": "LED", "VDD": "+3V3", "VDDA": "VDDA", "VREF+": "VDDA", "VSS": "0", "VSSA": "0"}
    B.add(b, Part("U9", None, "", mcu, desc="MCU, Cortex-M4F 170 MHz (FOC)", pn="ST STM32G431CBT6 (LQFP-48)",
                  fp="Package_QFP:LQFP-48_7x7mm_P0.5mm", note="pin map proposed: check alternate functions in STM32CubeMX"))
    for k in range(4): B.add(b, C(f"C{take('C')}", "100n", "+3V3", "0", desc="MCU VDD decoupling (one per VDD pin)"))
    B.add(b, C(f"C{take('C')}", "4.7µ", "+3V3", "0", fp=C0805, rating="10 V", desc="MCU bulk"))
    B.add(b, Part("FB1", "res", "0.1", {"1": "+3V3", "2": "VDDA"}, desc="Ferrite bead 600 Ω @ 100 MHz", bomval="600R@100MHz", pn="Murata BLM18PG601SN1",
                  fp="Inductor_SMD:L_0603_1608Metric"))
    B.add(b, C(f"C{take('C')}", "1µ", "VDDA", "0", desc="VDDA"))
    B.add(b, C(f"C{take('C')}", "100n", "VDDA", "0", desc="VDDA"))
    B.add(b, C(f"C{take('C')}", "100n", "NRST", "0", desc="Reset"))
    B.add(b, R(f"R{take('R')}", "10k", "BOOT0", "0", desc="BOOT0 pull-down"))
    B.add(b, R(f"R{take('R')}", "1k", "LED", "LED_K", desc="LED series"))
    B.add(b, Part(f"D{take('D')}", "diode", "QTLP690C", {"A": "+3V3", "K": "LED_K"}, desc="Status LED (green, 0603)", pn="any 0603 green LED",
                  fp="LED_SMD:LED_0603_1608Metric", spice=""))
    B.add(b, R(f"R{take('R')}", "100", "SIG_EXT", "SIG_IN", desc="Signal input series (DShot / PWM)"))
    B.add(b, Part("J2", None, "", {"1": "MOT_A"}, desc="Motor phase A (8 mm bullet or solder pad)", pn="8 AWG lead pad (8 mm bullet on the lead)", fp="Drone_Power:SolderWire-8AWG_1x01_D4.2mm_OD7mm"))
    B.add(b, Part("J3", None, "", {"1": "MOT_B"}, desc="Motor phase B", pn="8 AWG lead pad (8 mm bullet on the lead)", fp="Drone_Power:SolderWire-8AWG_1x01_D4.2mm_OD7mm"))
    B.add(b, Part("J4", None, "", {"1": "PH_C"}, desc="Motor phase C", pn="8 AWG lead pad (8 mm bullet on the lead)", fp="Drone_Power:SolderWire-8AWG_1x01_D4.2mm_OD7mm"))
    B.add(b, Part("J5", None, "", {"1": "SIG_EXT", "2": "TLM_TX", "3": "0"}, desc="Signal from flight controller (DShot in, telemetry out)",
                  pn="JST GH 3 pin", fp="Connector_JST:JST_GH_BM03B-GHS-TBT_1x03-1MP_P1.25mm_Vertical"))
    B.add(b, Part("J6", None, "", {"1": "+5V", "2": "0", "3": "ENC_CS", "4": "ENC_SCK", "5": "ENC_MISO", "6": "ENC_MOSI"},
                  desc="Rotor encoder (AS5047P on the motor, SPI)", pn="JST GH 6 pin", fp="Connector_JST:JST_GH_BM06B-GHS-TBT_1x06-1MP_P1.25mm_Vertical"))
    B.add(b, Part("J7", None, "", {"1": "+3V3", "2": "SWDIO", "3": "NRST", "4": "SWCLK", "5": "0"},
                  desc="SWD programming, Tag-Connect TC2030 pad order (6 = SWO, unused)",
                  pn="Tag-Connect TC2030-NL", fp="Connector:Tag-Connect_TC2030-IDC-NL_2x03_P1.27mm_Vertical"))
    B.add(b, Part("B_MCU", "bi", f"I={h.I_MCU}*limit(V(+3V3)/3,0,1)", {"+": "+3V3", "-": "0"}, sim=True))
    B.add(b, Part("B_ENC", "bi", f"I={h.I_ENC}*limit(V(+5V)/4.5,0,1)", {"+": "+5V", "-": "0"}, sim=True))

    # ================================================================== motor (simulation only)
    b = B.block("SIM: U15XL PMSM + prop (topology 09) on MOT_A / MOT_B / PH_C", 0, 4400, 3000, 700)
    for k, ph in enumerate("abc"):
        node = {"a": "MOT_A", "b": "MOT_B", "c": "PH_C"}[ph]; shift = f"-{2*k}*pi/3" if k else ""
        B.add(b, Part(f"L{ph}", "ind", "{Lph}", {"1": node, "2": f"r{ph}"}, sim=True))
        B.add(b, Part(f"R{ph}_M", "res", "{Rph}", {"1": f"r{ph}", "2": f"x{ph}"}, sim=True))
        B.add(b, Part(f"B_E{ph.upper()}", "bv", f"V=-{{Kph}}*V(omega)*sin(V(the){shift})", {"+": f"x{ph}", "-": "n"}, sim=True))
    sims = [("B_TE", "bv", "V=-{Kph}*(sin(V(the))*I(La)+sin(V(the)-2*pi/3)*I(Lb)+sin(V(the)-4*pi/3)*I(Lc))", {"+": "te", "-": "0"}),
            ("B_TM", "bi", "I=V(te)", {"+": "0", "-": "omega"}), ("C_J", "cap", "{Jrot}", {"1": "omega", "2": "0"}),
            ("B_TP", "bi", "I={Kprop}*V(omega)*abs(V(omega))+{Bfric}*V(omega)", {"+": "omega", "-": "0"}),
            ("R_LK", "res", "100Meg", {"1": "omega", "2": "0"}), ("B_DTH", "bi", "I=V(omega)", {"+": "0", "-": "theta"}),
            ("C_TH", "cap", "1", {"1": "theta", "2": "0"}), ("R_LK2", "res", "1G", {"1": "theta", "2": "0"}),
            ("B_THE", "bv", "V={Pp}*V(theta)", {"+": "the", "-": "0"}), ("B_RPM", "bv", "V=V(omega)*60/(2*pi)", {"+": "rpm", "-": "0"}),
            ("B_WE", "bv", "V={Pp}*V(omega)", {"+": "we", "-": "0"})]
    for ref, sym, val, nets in sims: B.add(b, Part(ref, sym, val, nets, sim=True))

    # ================================================================== MCU FOC firmware, behavioural (simulation only)
    b = B.block("SIM: STM32 FOC firmware (behavioural): reads ISNS_A/B, VBUS_SNS (ADC nets) and the encoder angle, writes PWM_A/B/C, DRV_EN",
                3100, 4400, 3600, 1000)
    adc_i = lambda ph: f"((V(ISNS_{ph})/{h.K_DIV:.6f}-{h.ACS_ZERO})/{h.ACS_GAIN})"
    fw = [("B_IA", f"V={adc_i('A')}", "ia"), ("B_IB", f"V={adc_i('B')}", "ib"),
          ("B_VB", f"V=V(VBUS_SNS)*{(h.R_VBUS_TOP + h.R_VBUS_BOT) / h.R_VBUS_BOT:.6f}", "vbusm"),
          ("B_EN", "V=V(DRV_EN)/3.3", "en"),
          ("B_IQREF", "V=limit({Kpw}*(V(wref)-V(omega))+{Kiw}*idt(V(en)*(V(wref)-V(omega)),{Iq0/Kiw}),-{Imax},{Imax})", "iqref"),
          ("B_IAL", "V=V(ia)", "ial"), ("B_IBE", "V=(V(ia)+2*V(ib))/sqrt(3)", "ibe"),
          ("B_ID", "V=V(ial)*cos(V(the))+V(ibe)*sin(V(the))", "id"), ("B_IQ", "V=-V(ial)*sin(V(the))+V(ibe)*cos(V(the))", "iq"),
          ("B_VD", "V={Kpi}*(0-V(id))+{Kii}*idt(V(en)*(0-V(id))) - V(we)*{Lph}*V(iq)", "vd"),
          ("B_VQ", "V={Kpi}*(V(iqref)-V(iq))+{Kii}*idt(V(en)*(V(iqref)-V(iq)),{Rph*Iq0/Kii}) + V(we)*{Lph}*V(id)+{Kph}*V(omega)", "vq"),
          ("B_VAL", "V=V(vd)*cos(V(the))-V(vq)*sin(V(the))", "val"), ("B_VBE", "V=V(vd)*sin(V(the))+V(vq)*cos(V(the))", "vbe"),
          ("B_VA", "V=V(val)", "va"), ("B_VBB", "V=-V(val)/2+sqrt(3)/2*V(vbe)", "vb"), ("B_VC", "V=-V(val)/2-sqrt(3)/2*V(vbe)", "vc"),
          ("B_VOFF", "V=(max(max(V(va),V(vb)),V(vc))+min(min(V(va),V(vb)),V(vc)))/2", "voff"),
          ("B_DRVEN", "V=3.3*(1+tanh((time-{Ten})/1u))/2", "DRV_EN")]     # MCU enables the drivers once 3.3 V is up
    for ref, val, node in fw: B.add(b, Part(ref, "bv", val, {"+": node, "-": "0"}, sim=True))
    B.add(b, Part("V_WREF", "voltage", "PWL(0 {W0} {Tpunch} {W0} {Tpunch+10u} {Wpunch})", {"+": "wref", "-": "0"}, sim=True))
    B.add(b, Part("V_TRI", "voltage", "PULSE(0 1 0 {Tsw/2} {Tsw/2} 0 {Tsw})", {"+": "tri", "-": "0"}, sim=True))
    B.add(b, Part("R_VBF", "res", "1k", {"1": "vbusm", "2": "vbusf"}, sim=True))
    B.add(b, Part("C_VBF", "cap", g(1 / (2 * math.pi * 1e3 * 3e3)), {"1": "vbusf", "2": "0"}, sim=True))
    for ph in "ABC":
        p = ph.lower()
        B.add(b, Part(f"B_D{ph}", "bv", f"V=limit(0.5+(V(v{p})-V(voff))/V(vbusf),0.01,0.99)", {"+": f"du{p}", "-": "0"}, sim=True))
        B.add(b, Part(f"B_PWM{ph}", "bv", f"V=3.3*(1+tanh(500*(V(du{p})-V(tri))))/2", {"+": f"PWM_{ph}", "-": "0"}, sim=True))

    if block:
        B.directives = ["; ESC board as a block of Power_System.asc. Port: VBUS (and the global ground). Parameters are set on the top sheet."]
        return B
    # ================================================================== directives
    W, WP = "FROM {Tw1} TO {Tw2}", "FROM {Tp1} TO {Tp2}"
    sw_loss = " + ".join(f"V(VBUS,PH_{ph})*Id(Q{q})+V(PH_{ph})*Id(Q{q + 4})" for ph, q in zip("ABC", (4, 12, 20)))
    B.directives = [
        "; === 10  ESC BOARD, one per motor. Cold start of the electronics with the rotor already at hover speed (flying start):",
        ";     aux 12 V and LDOs soft-start, MCU enables the drivers at Ten, FOC catches the motor; throttle punch at Tpunch ===",
        "; Parts named V_..., L_HARN, R_CS.., B_..., C_BW.., R_BW.., C_J, C_TH, R_LK.., La/Lb/Lc, R?_M, R_VBF, C_VBF are simulation only.",
        f"!.param KV={h09.KV} Ke={{60/(2*pi*KV)}} Kph={{Ke/sqrt(3)}} Pp={h09.Pp} Rph={g(h09.Rph)} Lph={g(h09.Lph)}",
        f"!.param Jrot={h09.Jrot} Kprop={g(h09.Kprop)} Bfric={g(h09.Bfric)}",
        f"!.param Fsw={g(h09.Fsw)} Tsw={{1/Fsw}} Rdt=150k",
        f"!.param W0={g(h09.W_HOVER)} Wpunch={g(h09.RPM_TW2*2*math.pi/60)} Iq0={g(iq0)} Imax={h09.Imax}",
        f"!.param Kpi={g(h09.Kpi)} Kii={g(h09.Kii)} Kpw={g(h09.Kpw)} Kiw={g(h09.Kiw)}",
        "!.param Ten=1.5m Tpunch=7m Tw1=4m Tw2=7m Tp1=10m Tp2=13m",
        "!.ic V(omega)={W0} V(theta)=0 V(SS_AUX)=0 V(+12V)=0 V(+5V)=0 V(+3V3)=0 I(L1)=0   ; electronics cold (soft-start empty), pack connected, rotor at hover",
        "!.tran 0 13m 0",
        "!.save V(VBUS) V(+12V) V(+5V) V(+3V3) V(PH_A) V(PH_B) V(PH_C) V(BST_A) V(TG_A) V(BG_A) V(GAH) V(GAL) V(PWM_A) "
        "V(ISNS_A) V(ISNS_B) V(ia) V(ib) V(id) V(iq) V(iqref) V(vd) V(vq) V(dua) V(omega) V(rpm) V(te) V(the) V(wref) V(vbusm) "
        "I(La) I(Lb) I(Lc) I(L_HARN) I(C1) I(C65) I(C17) I(L1) I(D1) I(D2) I(D3) Id(Q4) Id(Q8) Id(Q12) Id(Q16) Id(Q20) Id(Q24) V(SW_AUX) V(FAULT_N) V(DRV_EN)",
        f"!.meas TRAN RPM_h AVG V(rpm) {W}", f"!.meas TRAN Iq_h AVG V(iq) {W}", f"!.meas TRAN Id_h AVG V(id) {W}",
        f"!.meas TRAN Vq_h AVG V(vq) {W}", f"!.meas TRAN Vd_h AVG V(vd) {W}",
        f"!.meas TRAN Vbus_h AVG V(VBUS) {W}", f"!.meas TRAN Vbus_pp PP V(VBUS) {W}", f"!.meas TRAN Iesc_h AVG I(L_HARN) {W}",
        f"!.meas TRAN Pin_esc AVG V(VBUS)*I(L_HARN) {W}", f"!.meas TRAN Pshaft AVG {{Kprop}}*V(omega)**3 {W}",
        f"!.meas TRAN Pcu AVG {{Rph}}*(I(La)**2+I(Lb)**2+I(Lc)**2) {W}",
        f"!.meas TRAN Pfet AVG {sw_loss} {W}",
        "!.meas TRAN Eff_drive PARAM Pshaft/Pin_esc",
        f"!.meas TRAN Icap_rms RMS I(C1)+I(C65)+I(C17) {W}", f"!.meas TRAN Icap_bulk RMS I(C1)+I(C65) {W}", f"!.meas TRAN Iph_rms RMS I(La) {W}",
        f"!.meas TRAN V12 AVG V(+12V) {W}", f"!.meas TRAN V12_pp PP V(+12V) {W}", f"!.meas TRAN V5 AVG V(+5V) {W}", f"!.meas TRAN V33 AVG V(+3V3) {W}",
        f"!.meas TRAN I12 AVG I(L1) {W}", f"!.meas TRAN Iboot AVG I(D1)+I(D2)+I(D3) {W}",
        f"!.meas TRAN Vboot_min MIN V(BST_A,PH_A) {W}", f"!.meas TRAN Vboot_max MAX V(BST_A,PH_A) {W}",
        f"!.meas TRAN Vgh_max MAX V(GAH,PH_A) {W}", f"!.meas TRAN Vgl_max MAX V(GAL) {W}",
        f"!.meas TRAN Ia_err_rms RMS V(ia)-I(La) {W}",
        f"!.meas TRAN Fault_min MIN V(FAULT_N) {W}",
        f"!.meas TRAN Iq_p AVG V(iq) {WP}", f"!.meas TRAN Iesc_p AVG I(L_HARN) {WP}", f"!.meas TRAN Vbus_p AVG V(VBUS) {WP}",
        "!.meas TRAN T_iq90 TRIG V(wref) VAL={W0+1} RISE=1 TARG V(iq) VAL={Iq0+0.9*(Imax-Iq0)} RISE=1",
        "!.meas TRAN V12_min_p MIN V(+12V) FROM {Tpunch} TO {Tp2}",
        "!.meas TRAN T12 WHEN V(+12V)=10.8 RISE=1", "!.meas TRAN T5 WHEN V(+5V)=4.5 RISE=1", "!.meas TRAN T33 WHEN V(+3V3)=3.0 RISE=1",
        "!.meas TRAN T_iq_catch TRIG V(DRV_EN) VAL=1.65 RISE=1 TARG V(iq) VAL={0.9*Iq0} RISE=1",
        "!.meas TRAN Vboot_en MAX V(BST_A,PH_A) FROM {Ten-0.05m} TO {Ten+0.1m}",
        "!.meas TRAN V12_en_min MIN V(+12V) FROM {Ten} TO {Ten+0.5m}",
    ]
    return B


if __name__ == "__main__":
    B = build(); n = B.check_refs(); B.write_asc("ESC_Board.asc")
    nb = B.write_bom("ESC_BOM.csv"); nn, single = B.write_netlist("ESC_Netlist.csv")
    print(f"wrote ESC_Board.asc ({n} PCB parts), BOM ({nb} lines), net list ({nn} nets); single-pin nets: {single}")

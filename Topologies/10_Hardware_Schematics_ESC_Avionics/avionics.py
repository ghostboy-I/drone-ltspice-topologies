"""AVIONICS POWER BOARD (one per aircraft): three 24S packs -> diode-OR -> LTC7801 12 V / 5 A -> LT8641 5 V / 3 A -> LT3045 3.3 V.
python3 avionics.py  ->  Avionics_Board.asc, Avionics_BOM.csv, Avionics_Netlist.csv
python3 avionics.py loop  ->  Avionics_LoopTest.asc (12 V stage only, transient loop-gain injection)"""
import sys
from board import Board, Part
import hand_calc as h

U1, L8641, L3045 = h.U1, h.LT8641, h.LT3045
g = lambda v: f"{v:.4g}"
R0603, R0805, R1206, R2512 = ("Resistor_SMD:R_0603_1608Metric", "Resistor_SMD:R_0805_2012Metric",
                              "Resistor_SMD:R_1206_3216Metric", "Resistor_SMD:R_2512_6332Metric")
C0603, C0805, C1206, C1210 = ("Capacitor_SMD:C_0603_1608Metric", "Capacitor_SMD:C_0805_2012Metric",
                              "Capacitor_SMD:C_1206_3216Metric", "Capacitor_SMD:C_1210_3225Metric")


def R(ref, val, a, b, fp=R0603, pn="1 %, thick film", rating="", desc="Resistor", **k):
    return Part(ref, "res", val, {"1": a, "2": b}, desc=desc, pn=pn, fp=fp, rating=rating, **k)


def C(ref, val, a, b, fp=C0603, pn="X7R", rating="", desc="Capacitor", spice="", **k):
    return Part(ref, "cap", val, {"1": a, "2": b}, desc=desc, pn=pn, fp=fp, rating=rating, spice=spice, **k)
# (a derated ceramic is simulated at its effective value; pass bomval= with the value you buy)


MODELS = [   # ES1D, BSC520N15NS3, BSC360N15NS3 and BSP89 are vendor models in LTspice's own library; only the TVS is approximated
    "!.model SMBJ110A D(Is=1p Rs=0.5 N=1 BV=122 IBV=1m)   ; 600 W TVS, 110 V stand-off (approx. datasheet)",
]


def build(loop_test=False, block=False):
    """block=True: the sheet used inside Power_System.asc (packs come in on ports PACK1+..PACK3+)."""
    B = Board("Avionics", "AVIONICS POWER BOARD")
    # ------------------------------------------------------------------ inputs
    if not loop_test:
        b = B.block("1  PACK INPUTS: fuse, diode-OR (any pack can feed the avionics), TVS, input filter", 0, 0, 2000, 900)
        for k in (1, 2, 3):
            if not block: B.add(b, Part(f"V_PACK{k}", "voltage", f"PWL(0 {h.V_NOM} {{Tpull}} {h.V_NOM} {{Tpull+20u}} 0)" if k == 1 else f"{h.V_NOM}",
                          {"+": f"VP{k}", "-": "0"}, sim=True, spice="Rser=30m"))
            if not block: B.add(b, Part(f"R_LEAD{k}", "res", "50m", {"1": f"VP{k}", "2": f"PACK{k}+"}, sim=True))
            B.add(b, Part(f"J{k}", None, "", {"1": f"PACK{k}+", "2": "0"}, desc=f"Pack {k} input (from that pack's PDB tap)",
                          pn="Molex Micro-Fit 3.0, 2 pin (600 V, 5 A)", fp="Connector_Molex:Molex_Micro-Fit_3.0_43650-0215_1x02_P3.00mm_Vertical",
                          rating="≥150 V"))
            B.add(b, Part(f"F{k}", "res", g(h.R_FUSE), {"1": f"PACK{k}+", "2": f"PACK{k}_F"}, desc="Fuse, fast, 0.5 A", bomval="0.5 A",
                          pn="Littelfuse 0451.500 (NANO2, 125 V DC)", fp="Fuse:Fuse_1206_3216Metric", rating="125 V DC"))
            B.add(b, Part(f"D{k}", "diode", "ES1D", {"A": f"PACK{k}_F", "K": "VIN_AV"}, desc="Diode-OR, ultrafast 200 V 1 A",
                          pn="ES1D", fp="Diode_SMD:D_SMA", rating="200 V 1 A"))
        B.add(b, Part("D4", "zener", "SMBJ110A", {"A": "0", "K": "VIN_AV"}, desc="TVS 600 W, 110 V stand-off", pn="SMBJ110A",
                      fp="Diode_SMD:D_SMB", rating="VBR 122 V"))
        B.add(b, C("C1", "33µ", "VIN_AV", "0", fp="Capacitor_THT:CP_Radial_D10.0mm_P5.00mm", pn="Aluminium electrolytic, low ESR",
                   rating="160 V", desc="Input bulk (damps the input filter)", spice="Rser=0.8"))
        for r in ("C2", "C3"):
            B.add(b, C(r, "2.2µ", "VIN_AV", "0", fp=C1210, pn="X7R 1210", rating="250 V", desc="Input ceramic (near Q1)", spice="Rser=5m"))
        vin12 = "VIN_AV"
    else:
        b = B.block("LOOP TEST: 12 V stage alone, 88.8 V input, sine injected in series with the feedback divider", 0, 0, 2000, 500)
        B.add(b, Part("V_IN", "voltage", f"{h.V_NOM}", {"+": "VIN_AV", "-": "0"}, sim=True))
        B.add(b, C("C2", "2.2µ", "VIN_AV", "0", fp=C1210, spice="Rser=5m")); B.add(b, C("C3", "2.2µ", "VIN_AV", "0", fp=C1210, spice="Rser=5m"))
        vin12 = "VIN_AV"

    # ------------------------------------------------------------------ 12 V
    b = B.block("2  12 V / 5 A BUCK  (U1 LTC7801, peak current mode, 148 kHz): video/telemetry TX + feeds the 5 V stage", 0, 1000, 3400, 1500)
    fb_top = "+12V_INJ" if loop_test else "+12V"
    B.add(b, Part("U1", "LTC7801", "LTC7801", {
        "VIN": vin12, "RUN": "RUN12", "OVLO": "OVLO12", "SENSE+": "SNS12", "SENSE-": "+12V", "SS": "SS12", "VFB": "FB12",
        "ITH": "ITH12", "MODE": "INTVCC12", "CPUMP_EN": "INTVCC12", "PLLIN": "0", "PGOOD": "PG12", "FREQ": "FREQ12",
        "DRVSET": "DRVSET12", "DRVUV": "0", "TG": "TG12", "SW": "SW12", "BOOST": "BST12", "BG": "BG12", "DRVCC": "DRVCC12",
        "NDRV": "NDRV12", "EXTVCC": "+12V", "INTVCC": "INTVCC12", "GND": "0"},
        desc="150 V synchronous buck controller", pn="LTC7801EFE (TSSOP-24 with exposed pad)", fp="Package_SO:HTSSOP-24-1EP_4.4x7.8mm_P0.65mm_EP3.2x5mm (check EP size vs ADI FE24 drawing)",
        rating="150 V", note="no KiCad library symbol: use ADI/SnapEDA"), dx=260)
    B.add(b, Part("Q1", "nmos", "BSC520N15NS3", {"D": vin12, "G": "TG12", "S": "SW12"}, desc="N-MOSFET 150 V 52 mΩ (top)",
                  pn="Infineon BSC520N15NS3", fp="Package_TO_SOT_SMD:TDSON-8-1", rating="150 V 21 A"))
    B.add(b, Part("Q2", "nmos", "BSC360N15NS3", {"D": "SW12", "G": "BG12", "S": "0"}, desc="N-MOSFET 150 V 36 mΩ (bottom)",
                  pn="Infineon BSC360N15NS3", fp="Package_TO_SOT_SMD:TDSON-8-1", rating="150 V 30 A"))
    B.add(b, Part("Q3", "nmos", "BSP89", {"D": vin12, "G": "NDRV12", "S": "DRVCC12"}, desc="N-MOSFET 240 V, DRVCC pre-regulator",
                  pn="Infineon BSP89", fp="Package_TO_SOT_SMD:SOT-223-3_TabPin2", rating="240 V"))
    B.add(b, Part("L1", "ind", "47µ", {"1": "SW12", "2": "SNS12"}, spice=f"Rser={g(U1.dcr)}", desc="Power inductor 47 µH",
                  pn="shielded 10x10 mm (e.g. Coilcraft XAL1010 family), Isat ≥ 9.2 A, DCR ≤ 30 mΩ", fp="Inductor_SMD:L_Coilcraft_XAL1010-XXX", rating="Isat 9.2 A"))
    B.add(b, R("R1", "10m", "SNS12", "+12V", fp=R2512, pn="current sense, 1 %, 1 W", rating="1 W", desc="Current sense"))
    B.add(b, C("C4", "1n", "SNS12", "+12V", desc="Sense filter"))
    B.add(b, C("C5", "0.1µ", "BST12", "SW12", fp=C0603, rating="25 V", desc="Boost"))
    B.add(b, C("C6", "4.7µ", "DRVCC12", "0", fp=C0805, rating="25 V", desc="DRVCC"))
    B.add(b, C("C7", "0.1µ", "INTVCC12", "0", desc="INTVCC"))
    B.add(b, R("R2", g(h.R_RUN[0]), vin12, "RUN12", fp=R1206, rating="200 V", desc="RUN divider (UVLO 59.8 V)"))
    B.add(b, R("R3", g(h.R_RUN[1]), "RUN12", "0", desc="RUN divider bottom"))
    B.add(b, R("R4", g(h.R_OVLO[0]), vin12, "OVLO12", fp=R1206, rating="200 V", desc="OVLO divider (118.8 V)"))
    B.add(b, R("R5", g(h.R_OVLO[1]), "OVLO12", "0", desc="OVLO divider bottom"))
    B.add(b, R("R6", g(U1.rfreq), "FREQ12", "0", desc="FREQ (148 kHz)"))
    B.add(b, C("C8", g(U1.css), "SS12", "0", desc="Soft-start (2.6 ms)"))
    B.add(b, R("R7", g(U1.rtop), fb_top, "FB12", desc="Feedback top"))
    B.add(b, R("R8", g(U1.rbot), "FB12", "0", desc="Feedback bottom"))
    B.add(b, R("R9", g(U1.rith), "ITH12", "ITHC12", desc="Compensation RITH"))
    B.add(b, C("C9", g(U1.cith), "ITHC12", "0", desc="Compensation CITH"))
    B.add(b, C("C10", g(U1.cithb), "ITH12", "0", desc="Compensation CITHB"))
    B.add(b, R("R10", "100k", "INTVCC12", "PG12", desc="PGOOD pull-up"))
    B.add(b, R("R20", "100k", "DRVSET12", "0", desc="DRVSET: DRVCC = 5 x 20 µA x R = 10 V"))
    for r in ("C11", "C12"):
        B.add(b, C(r, "47µ", "+12V", "0", fp="Capacitor_SMD:CP_Elec_6.3x7.7", pn="Polymer, ESR ≤ 15 mΩ", rating="25 V",
                   desc="Output bulk", spice="Rser=15m"))
    for r in ("C13", "C14"):
        B.add(b, C(r, "5µ", "+12V", "0", fp=C1210, pn="10 µF X7R 1210 (5 µF at 12 V bias)", rating="25 V", desc="Output ceramic",
                   spice="Rser=3m", bomval="10µ"))
    if loop_test:
        B.add(b, Part("V_INJ", "voltage", "SINE(0 {Ainj} {Finj})", {"+": "+12V_INJ", "-": "+12V"}, sim=True))
        B.add(b, Part("R_LOAD12", "res", "{12/Iload}", {"1": "+12V", "2": "0"}, sim=True))
        B.directives = ["; === 10  LOOP-GAIN TEST of the 12 V stage (U1 LTC7801): sine in series with the divider, T = -V(+12V_INJ)/V(+12V) at Finj ===",
                        "!.param Iload=2.4 Ainj=20m", "!.step param Finj list 3k 6k 12k 24k",
                        "!.tran 0 {4.5m+8/Finj} 3.5m", "!.save V(+12V) V(+12V_INJ) V(ITH12) I(L1)"] + MODELS
        return B

    # ------------------------------------------------------------------ 12 V output
    b = B.block("3  12 V OUTPUT: video / telemetry transmitter", 3500, 1000, 1500, 700)
    B.add(b, Part("F4", "res", "0.05", {"1": "+12V", "2": "VTX_12V"}, desc="PTC resettable fuse 2 A hold", bomval="2 A", pn="Bourns MF-MSMF200 (1812)",
                  fp="Fuse:Fuse_1812_4532Metric", rating="2 A hold, 16 V"))
    B.add(b, Part("J4", None, "", {"1": "VTX_12V", "2": "0"}, desc="12 V transmitter output", pn="JST XH 2 pin (3 A)",
                  fp="Connector_JST:JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical"))
    B.add(b, Part("C_VTX", "cap", "10µ", {"1": "VTX_12V", "2": "0"}, sim=True, spice="Rser=10m"))
    B.add(b, Part("B_VTX", "bi", f"I={h.I_VTX}*(1+tanh((time-{{Tvtx}})/2u))/2*limit(V(VTX_12V)/10,0,1)", {"+": "VTX_12V", "-": "0"}, sim=True))

    # ------------------------------------------------------------------ 5 V
    b = B.block("4  5 V / 3 A BUCK  (U2 LT8641, 1 MHz, internally compensated): flight controller + receiver; enabled by 12 V PGOOD",
                0, 2600, 3400, 1000)
    B.add(b, Part("U2", "LT8641", "LT8641", {"Vin1": "+12V", "Vin2": "+12V", "EN/UV": "PG12", "Bias": "+5V", "INTVcc": "INTVCC5",
                                            "BST": "BST5", "SW": "SW5", "GND1": "0", "GND2": "0", "GND": "0", "Rt": "RT5",
                                            "TR/SS": "SS5", "Sync/Mode": "0", "PG": "PG5", "FB": "FB5"},
                  desc="65 V 3.5 A synchronous buck", pn="LT8641EV (LQFN-18 3x4)", fp="custom: LQFN-18 3x4 mm (ADI package drawing; no stock KiCad footprint)",
                  rating="65 V", note="no KiCad library symbol: use ADI/SnapEDA"), dx=240)
    B.add(b, Part("L2", "ind", "3.3µ", {"1": "SW5", "2": "+5V"}, spice=f"Rser={g(L8641['dcr'])}", desc="Power inductor 3.3 µH",
                  pn="shielded, Isat ≥ 6 A, DCR ≤ 10 mΩ", fp="Inductor_SMD:L_Coilcraft_XAL4020-XXX", rating="Isat 6 A"))
    for r in ("C15", "C16"):
        B.add(b, C(r, "4.7µ", "+12V", "0", fp=C0805, rating="25 V", desc="U2 input (one at each VIN pin)", spice="Rser=3m"))
    B.add(b, C("C17", "0.1µ", "BST5", "SW5", desc="Boost"))
    B.add(b, C("C18", "1µ", "INTVCC5", "0", desc="INTVCC"))
    B.add(b, R("R11", g(L8641["rt"]), "RT5", "0", desc="RT (1 MHz)"))
    B.add(b, C("C19", g(L8641["css"]), "SS5", "0", desc="Soft-start"))
    B.add(b, R("R12", g(L8641["rtop"]), "+5V", "FB5", desc="Feedback top"))
    B.add(b, R("R13", g(L8641["rbot"]), "FB5", "0", desc="Feedback bottom"))
    B.add(b, C("C20", g(L8641["cff"]), "+5V", "FB5", desc="Feed-forward"))
    B.add(b, R("R14", "100k", "INTVCC5", "PG5", desc="PG pull-up"))
    for r in ("C21", "C22"):
        B.add(b, C(r, "47µ", "+5V", "0", fp=C1210, pn="X7R 1210 (~30 µF at 5 V)", rating="10 V", desc="Output ceramic", spice="Rser=2m"))
    B.add(b, Part("J5", None, "", {"1": "+5V", "2": "+5V", "3": "0", "4": "0"}, desc="5 V to flight controller + receiver",
                  pn="JST GH 4 pin (2 pins per rail, 1 A/pin)", fp="Connector_JST:JST_GH_BM04B-GHS-TBT_1x04-1MP_P1.25mm_Vertical"))
    B.add(b, Part("B_FC", "bi", f"I=({h.I_FC_IDLE}+{h.I_FC + h.I_RX - h.I_FC_IDLE}*(1+tanh((time-{{Tfc}})/2u))/2)*limit(V(+5V)/4,0,1)",
                  {"+": "+5V", "-": "0"}, sim=True))

    # ------------------------------------------------------------------ 3.3 V
    b = B.block("5  3.3 V / 0.3 A ULTRALOW-NOISE LDO  (U3 LT3045): sensors; enabled by 5 V PG", 3500, 1800, 1500, 1800)
    B.add(b, Part("U3", "LT3045", "LT3045", {"IN": "+5V", "EN/UV": "PG5", "PG": "PG33", "ILIM": "ILIM33", "PGFB": "PGFB33",
                                            "SET": "SET33", "GND": "0", "OUTS": "+3V3", "OUT": "+3V3"},
                  desc="20 V 500 mA ultralow-noise LDO", pn="LT3045EDD (DFN-10 3x3)", fp="Package_DFN_QFN:DFN-10-1EP_3x3mm_P0.5mm_EP1.65x2.38mm",
                  rating="20 V"), dx=200)
    B.add(b, R("R15", g(L3045["rset"]), "SET33", "0", pn="0.1 %, 25 ppm", desc="RSET (Vout = 100 µA x RSET)"))
    B.add(b, C("C23", g(L3045["cset"]), "SET33", "0", desc="CSET (noise filter / soft-start)"))
    B.add(b, R("R16", g(L3045["rilim"]), "ILIM33", "0", desc="Current limit 300 mA"))
    B.add(b, R("R17", "450k", "+3V3", "PGFB33", desc="PGFB divider top")); B.add(b, R("R18", "50k", "PGFB33", "0", desc="PGFB divider bottom"))
    B.add(b, R("R19", "100k", "+5V", "PG33", desc="PG pull-up"))
    B.add(b, C("C24", "4.7µ", "+5V", "0", fp=C0805, rating="10 V", desc="U3 input"))
    B.add(b, C("C25", "4.7µ", "+3V3", "0", fp=C0805, rating="10 V", desc="U3 output", spice="Rser=3m"))
    B.add(b, Part("J6", None, "", {"1": "+3V3", "2": "0"}, desc="3.3 V sensor output", pn="JST GH 2 pin",
                  fp="Connector_JST:JST_GH_BM02B-GHS-TBT_1x02-1MP_P1.25mm_Vertical"))
    B.add(b, Part("B_SENS", "bi", f"I={h.I_33}*limit(V(+3V3)/3,0,1)", {"+": "+3V3", "-": "0"}, sim=True))

    if block:
        B.directives = ["; Avionics board as a block of Power_System.asc. Ports: PACK1+, PACK2+, PACK3+, +12V, +5V, +3V3. Parameters on the top sheet."]
        return B
    W = "FROM {Tw1} TO {Tw2}"
    B.directives = [
        "; === 10  AVIONICS POWER BOARD: three 24S packs -> diode-OR -> 12 V (LTC7801) -> 5 V (LT8641) -> 3.3 V (LT3045) ===",
        "; Parts named V_..., R_LEAD.., B_..., C_VTX are simulation stimulus/loads, not board parts. Everything else is in Avionics_BOM.csv",
        "!.param Tvtx=6.0m Tfc=6.5m Tw1=6.8m Tw2=7.0m Tpull=7.1m",
        "!.tran 0 8.0m 0 startup",
        "!.save V(VIN_AV) V(PACK1+) V(PACK2+) V(+12V) V(+5V) V(+3V3) V(SW12) V(SW5) V(PG12) V(PG5) V(PG33) V(SS12) V(ITH12) "
        "I(L1) I(L2) I(D1) I(D2) I(D3) I(R_LEAD1) I(R_LEAD2) I(R_LEAD3) V(VTX_12V) I(B_VTX) I(B_FC) I(B_SENS)",
        "!.meas TRAN T12 WHEN V(+12V)=10.8 RISE=1", "!.meas TRAN T5 WHEN V(+5V)=4.5 RISE=1", "!.meas TRAN T33 WHEN V(+3V3)=3.0 RISE=1",
        f"!.meas TRAN V12 AVG V(+12V) {W}", f"!.meas TRAN V5 AVG V(+5V) {W}", f"!.meas TRAN V33 AVG V(+3V3) {W}",
        f"!.meas TRAN Rip12 PP V(+12V) {W}", f"!.meas TRAN Rip5 PP V(+5V) {W}", f"!.meas TRAN Rip33 PP V(+3V3) {W}",
        f"!.meas TRAN IL1pp PP I(L1) {W}", f"!.meas TRAN IL2pp PP I(L2) {W}",
        f"!.meas TRAN Vin_av AVG V(VIN_AV) {W}",
        f"!.meas TRAN Pin AVG V(VIN_AV)*(I(D1)+I(D2)+I(D3)) {W}",
        f"!.meas TRAN Ppk AVG {h.V_NOM}*(I(R_LEAD1)+I(R_LEAD2)+I(R_LEAD3)) {W}",
        f"!.meas TRAN P12 AVG V(+12V)*I(L1) {W}", f"!.meas TRAN P5 AVG V(+5V)*I(L2) {W}",
        f"!.meas TRAN Pload AVG V(VTX_12V)*I(B_VTX)+V(+5V)*I(B_FC)+V(+3V3)*I(B_SENS) {W}",
        f"!.meas TRAN I1 AVG I(D1) {W}", f"!.meas TRAN I2 AVG I(D2) {W}", f"!.meas TRAN I3 AVG I(D3) {W}",
        "!.meas TRAN Eff12 PARAM P12/Pin", "!.meas TRAN Eff_board PARAM Pload/Ppk",
        "!.meas TRAN V12_pre AVG V(+12V) FROM {Tvtx-0.2m} TO {Tvtx}", "!.meas TRAN Dip_vtx MIN V(+12V) FROM {Tvtx} TO {Tvtx+0.3m}",
        "!.meas TRAN V5_pre AVG V(+5V) FROM {Tfc-0.2m} TO {Tfc}", "!.meas TRAN Dip_fc MIN V(+5V) FROM {Tfc} TO {Tfc+0.2m}",
        "!.meas TRAN V12_pull MIN V(+12V) FROM {Tpull} TO {Tpull+0.8m}", "!.meas TRAN I2_after AVG I(D2) FROM {Tpull+0.5m} TO {Tpull+0.9m}",
        "!.meas TRAN I1_after AVG I(D1) FROM {Tpull+0.5m} TO {Tpull+0.9m}",
    ] + MODELS
    return B


if __name__ == "__main__":
    if "loop" in sys.argv:
        build(loop_test=True).write_asc("Avionics_LoopTest.asc"); print("wrote Avionics_LoopTest.asc")
    else:
        B = build(); B.write_asc("Avionics_Board.asc")
        n = B.write_bom("Avionics_BOM.csv"); nn, single = B.write_netlist("Avionics_Netlist.csv")
        print(f"wrote Avionics_Board.asc, BOM ({n} lines), net list ({nn} nets); single-pin nets: {single}")

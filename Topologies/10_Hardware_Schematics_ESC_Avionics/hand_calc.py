"""Hand calculations for topology 10: the two PCBs that implement topology 09 with real parts.
Every value the schematics (avionics.py, esc.py) use comes from here. Run it to print the design."""
import math, json, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
import importlib.util
_spec = importlib.util.spec_from_file_location("hand_calc_09", os.path.join(HERE, "..", "09_24S_FOC_Drive_Low-Voltage_Rails", "hand_calc.py"))
h09 = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(h09)   # motor, pack, inverter, loads from topology 09

V_EMPTY, V_NOM, V_FULL = h09.V_EMPTY, h09.V_NOM, h09.V_FULL
E96, E12, snap = h09.E96, h09.E12, h09.snap


# ======================================================================================================
# AVIONICS BOARD
# ======================================================================================================
# loads (topology 09, with the 3.3 V rail resized: real IMU/baro/mag draw tens of mA, the 0.5 A of 09 was generous)
I_VTX, I_FC_IDLE, I_FC, I_RX, I_33 = 1.5, 0.8, 1.5, 0.3, 0.2

# ---- input: three packs, diode-OR (0.35 A total at 88 V, so plain diodes are fine; 08 needed ideal diodes at 3 A / 15 V)
VF_OR = 0.75                     # ES1D at ~0.1-0.4 A (datasheet curve), ultrafast 200 V 1 A
R_FUSE = 0.15                    # 0.5 A fast fuse, cold resistance

# ---- U1 LTC7801: 72-100.8 V -> 12 V / 5 A, peak current mode
class LTC7801:
    VFB, GM, ISS, VSENSE = 0.800, 2e-3, 10e-6, (66e-3, 75e-3, 84e-3)    # datasheet (Rev. A) values used by Hardware/06
    FREQ_TABLE = [(25e3, 105e3), (65e3, 440e3), (105e3, 835e3)]          # RFREQ -> f, datasheet table
    A_ITH = 1 / 12            # ASSUMED ITH-to-sense gain dVsense/dVith; checked by the transient loop-gain test

    def __init__(self, vout, iout, iout_typ, rfreq, L, dcr, rsense, cout_bulk, esr_bulk, cout_cer, rtop, rbot, css, fc,
                 qg_top, qg_bot, drvcc=10.0):
        self.__dict__.update(locals()); del self.__dict__["self"]
        (r1, f1), (r2, f2) = self.FREQ_TABLE[:2]
        self.fsw = f1 + (rfreq - r1) * (f2 - f1) / (r2 - r1)
        self.vset = self.VFB * (1 + rtop / rbot)
        self.C = cout_bulk + cout_cer; self.ESR = esr_bulk
        self.tss = self.VFB * css / self.ISS
        # Type II on ITH: RITH sets fc, CITH zero at fc/8, CITHB pole at fsw/2
        self.rith_ideal = 2 * math.pi * fc * self.C * vout * rsense / (self.GM * self.VFB * self.A_ITH)
        self.rith = snap(self.rith_ideal, E96)
        self.cith = snap(1 / (2 * math.pi * self.rith * fc / 8), E12)
        self.cithb = snap(1 / (2 * math.pi * self.rith * self.fsw / 2), E12)

    def ripple(self, vin):
        D = self.vout / vin; dI = (vin - self.vout) * D / (self.L * self.fsw)
        return D, dI, dI / (8 * self.fsw * self.C) + dI * self.ESR

    def ilim(self):
        _, dI, _ = self.ripple(V_FULL)
        return {k: v / self.rsense - dI / 2 for k, v in zip(("min", "typ", "max"), self.VSENSE)}

    def loop(self, f, Rload=None):
        """Current-mode loop: T = gm Zith (VFB/Vout) (A/Rsense) Zout, Zith = (RITH + 1/sCITH) || 1/sCITHB."""
        Rload = Rload or self.vout / self.iout
        s = 2j * math.pi * np.asarray(f, float)
        za = self.rith + 1 / (s * self.cith); zith = za / (1 + s * self.cithb * za)
        zc = self.ESR + 1 / (s * self.C); zout = zc * Rload / (zc + Rload)
        # current-mode modulators act once per switching period: about one period of pure delay (found with the
        # transient loop-gain test, where the extra phase lag grew in proportion to f: 27 deg at 12 kHz, 56 deg at 24 kHz)
        return self.GM * zith * (self.VFB / self.vout) * (self.A_ITH / self.rsense) * zout * np.exp(-s / self.fsw)

    def margins(self, Rload=None):
        f = np.logspace(2, 6, 4000); T = self.loop(f, Rload); i = int(np.argmax(np.abs(T) < 1))
        return f[i], 180 + float(np.degrees(np.angle(T[i])))

    def losses(self, vin, iout):
        D, dI, _ = self.ripple(vin)
        top, bot = FETS["BSC520N15NS3"], FETS["BSC360N15NS3"]
        irms2 = iout ** 2 + dI ** 2 / 12
        cond = D * irms2 * top["Ron"] + (1 - D) * irms2 * bot["Ron"]
        sense = irms2 * self.rsense; dcr = irms2 * self.dcr
        ig = 1.5                                                              # LTC7801 TG ~1.5 A pull-up / pull-down (typ.)
        sw = vin * iout * (top["Qgd"] / ig) * self.fsw                         # one rise + one fall, each Qgd/Ig long
        oss = 0.5 * (top["Coss"] + bot["Coss"]) * vin ** 2 * self.fsw
        dead = 2 * 0.8 * iout * 30e-9 * self.fsw
        gate = (self.qg_top + self.qg_bot) * self.fsw * self.vout          # EXTVCC = 12 V output feeds the gate supply
        tot = cond + sense + dcr + sw + oss + dead + gate
        po = self.vset * iout
        return dict(cond=cond, sense=sense, dcr=dcr, sw=sw, oss=oss, dead=dead, gate=gate, total=tot, eff=po / (po + tot))


# FET data for the hand calcs. Ron is what LTspice's vendor model gives at Vgs = 10 V, 25 C (measured with a 1 V / 1 mOhm
# test, see the design doc); the other values are datasheet typicals.
FETS = {
    "BSC520N15NS3": dict(Ron=43e-3, Qg=9e-9, Qgd=2e-9, Coss=60e-12, Vds=150),     # top, SuperSO8 (datasheet max 52 mOhm)
    "BSC360N15NS3": dict(Ron=32e-3, Qg=11e-9, Qgd=2.5e-9, Coss=80e-12, Vds=150),  # bottom, SuperSO8 (max 36 mOhm)
    "IPB065N15N3": dict(Ron=5.6e-3, Vds=150),                                     # ESC switch, D2PAK (max 6.5 mOhm), 4 in parallel
}

U1 = LTC7801(vout=12.0, iout=5.0, iout_typ=2.5, rfreq=30.1e3, L=47e-6, dcr=30e-3, rsense=10e-3,
             cout_bulk=2 * 47e-6, esr_bulk=15e-3 / 2, cout_cer=2 * 10e-6 * 0.5, rtop=140e3, rbot=10e3, css=33e-9, fc=12e3,
             qg_top=9e-9, qg_bot=11e-9)

# RUN / OVLO dividers (1.2 V thresholds)
R_RUN = (976e3, 20e3); R_OVLO = (1e6, 10.2e3)
V_RUN = 1.2 * (1 + R_RUN[0] / R_RUN[1]); V_OVLO = 1.2 * (1 + R_OVLO[0] / R_OVLO[1])

# ---- U2 LT8641: 12 V -> 5 V / 3 A, internally compensated (values from the ADI application circuit, retargeted to 12 V in)
LT8641 = dict(rt=41.2e3, fsw=1e6, L=3.3e-6, dcr=10e-3, cout=2 * 47e-6, rtop=1e6, rbot=191e3, cff=4.7e-12, css=2.2e-9, vref=0.8,
              eff_ds=0.92)            # ~92 % at 12 V in, 5 V, 2-3 A, 1 MHz: datasheet efficiency curve (typical)
V5 = LT8641["vref"] * (1 + LT8641["rtop"] / LT8641["rbot"])

# ---- U3 LT3045: 5 V -> 3.3 V / 0.2 A ultralow-noise LDO: Vout = 100 uA x RSET
LT3045 = dict(rset=33.2e3, cset=47e-9, rilim=499.0, iset=100e-6, cout=4.7e-6)
V33 = LT3045["iset"] * LT3045["rset"]
I_LIM_33 = 150e-3 * 1e3 / LT3045["rilim"]          # ILIM: 150 mA*kOhm / RILIM


def avionics():
    i5 = I_FC + I_RX + I_33
    p5 = V5 * i5; p12_for_5 = p5 / LT8641["eff_ds"]
    i12 = I_VTX + p12_for_5 / U1.vset
    l = U1.losses(V_NOM, i12)
    p_in = U1.vset * i12 + l["total"]
    i_in = p_in / (V_NOM - VF_OR)
    return dict(i5=i5, p5=p5, i12=i12, l12=l, p_in=p_in, i_in=i_in, p_or=VF_OR * i_in, p_ldo=(V5 - V33) * I_33,
                t12=U1.tss, eff_total=(12 * I_VTX + V5 * (I_FC + I_RX) + V33 * I_33) / p_in)


if __name__ == "__main__":
    print(f"U1 LTC7801: fsw {U1.fsw/1e3:.1f} kHz  Vset {U1.vset:.3f} V  tss {U1.tss*1e3:.2f} ms  C {U1.C*1e6:.0f} uF")
    for v in (V_EMPTY, V_NOM, V_FULL):
        D, dI, dV = U1.ripple(v); print(f"   Vin {v:5.1f}: D {D:.3f} ton {D/U1.fsw*1e9:.0f} ns dI {dI:.2f} A dV {dV*1e3:.1f} mV")
    print(f"   Ilim (min/typ/max output) {', '.join(f'{k} {v:.2f}' for k, v in U1.ilim().items())} A  Isat >= {U1.VSENSE[2]/U1.rsense*1.1:.1f} A")
    print(f"   ITH: RITH {U1.rith:.4g} (ideal {U1.rith_ideal:.4g})  CITH {U1.cith*1e9:.3g} nF  CITHB {U1.cithb*1e12:.3g} pF")
    fc, pm = U1.margins(); fcl, pml = U1.margins(12 / 0.5)
    print(f"   loop: fc {fc/1e3:.2f} kHz PM {pm:.1f}  (0.5 A: fc {fcl/1e3:.2f} PM {pml:.1f})")
    print(f"   RUN {V_RUN:.1f} V  OVLO {V_OVLO:.1f} V")
    a = avionics(); l = a["l12"]
    print(f"   at {a['i12']:.2f} A: " + ", ".join(f"{k} {v*1e3:.0f}m" for k, v in l.items() if k not in ('total', 'eff')) + f"  eff {l['eff']*100:.1f} %")
    print(f"U2 LT8641: V5 {V5:.3f}  dI {(12-V5)*(V5/12)/(LT8641['L']*LT8641['fsw']):.2f} A")
    print(f"U3 LT3045: V33 {V33:.3f}  Ilim {I_LIM_33*1e3:.0f} mA  P {a['p_ldo']:.2f} W  tss {LT3045['cset']*V33/LT3045['iset']*1e3:.2f} ms")
    print(f"Board: I5 {a['i5']:.2f}  I12 {a['i12']:.2f}  Pin {a['p_in']:.1f} W  Iin {a['i_in']:.3f} A  OR loss {a['p_or']:.2f} W  overall {a['eff_total']*100:.1f} %")


# ======================================================================================================
# ESC BOARD (one per motor)
# ======================================================================================================
N_PAR = 4                                        # FETs in parallel per switch position (topology 09's ESC150 = 4 x one FET)
FET1 = {k: (v * N_PAR if k in ("Rd", "Rs", "Rb") else v / N_PAR if k in ("Kp", "Cgs", "Cgdmax", "Cgdmin", "Cjo", "Is", "Qg") else v)
        for k, v in h09.ESC.items()}             # one IPB048N15N5-class FET: 4.2 mOhm, ~75 nC
QG_SWITCH = 302e-9                               # bench-measured gate charge of one switch position (4 FETs), topology 09
FSW_INV = h09.Fsw
I_GATE = 6 * QG_SWITCH * FSW_INV                 # 36 mA: every switch position charged once per period
RG_EACH = 10.0                                   # gate resistor per FET; 4 in parallel -> 2.5 Ohm per position

# loads on the ESC's 5 V and 3.3 V (typical datasheet supply currents)
I_ACS770 = 10e-3                                 # Allegro ACS770, 5 V, typ.
I_ENC = 12e-3                                    # ams AS5047P at 5 V, typ.
I_MCU = 50e-3                                    # STM32G431 at 170 MHz with peripherals, typ. order of magnitude
I_LED, I_DRV_Q = 2e-3, 3 * 1e-3                  # status LED; LTC7063 quiescent, 3 drivers
I_3V3 = I_MCU + I_LED
I_5V = 2 * I_ACS770 + I_ENC + I_3V3
I_12V = I_GATE + I_DRV_Q + I_5V

AUX = LTC7801(vout=12.0, iout=0.3, iout_typ=I_12V, rfreq=65e3, L=150e-6, dcr=0.4, rsense=0.1,
              cout_bulk=22e-6, esr_bulk=3e-3, cout_cer=2 * 10e-6 * 0.5, rtop=140e3, rbot=10e3, css=10e-9, fc=20e3,
              # cout_bulk: one 47 uF 25 V X7R (~22 uF at 12 V), added after the first run dipped +12V to 7.4 V when the
              # three 1 uF bootstrap capacitors all charged at driver enable
              qg_top=9e-9, qg_bot=11e-9)
P_LDO5 = (12 - 5) * I_5V; P_LDO33 = (5 - 3.3) * I_3V3

# current sense: ACS770LCB-200B, 10 mV/A at 5 V supply, 2.5 V zero, 120 kHz bandwidth; 2/3 divider into the 3.3 V ADC
ACS_GAIN, ACS_ZERO, ACS_BW, K_DIV = 10e-3, 2.5, 120e3, 2 / 3
I_RANGE = (3.3 / K_DIV - ACS_ZERO) / ACS_GAIN          # +/- current that still fits the ADC
ADC_A_PER_LSB = 3.3 / 4096 / (ACS_GAIN * K_DIV)

# bus voltage sense: 3 x 330k (1206, 200 V each) + 33k into the ADC
R_VBUS_TOP, R_VBUS_BOT = 3 * 330e3, 33e3
VBUS_ADC_FULL = V_FULL * R_VBUS_BOT / (R_VBUS_TOP + R_VBUS_BOT)


def esc():
    hv = h09.hover()
    l_aux = AUX.losses(hv["vbus"], I_12V)
    return dict(hv=hv, l_aux=l_aux, p_aux_in=12 * I_12V / l_aux["eff"])


if __name__ == "__main__" and "esc" in sys.argv:
    print(f"ESC FET (1 of 4): Ron {FET1['Rd']+FET1['Rs']+1/(FET1['Kp']*(12-FET1['Vto'])):.4f} Ohm  Qg {QG_SWITCH/N_PAR*1e9:.0f} nC (bench/4)")
    print(f"Gate {I_GATE*1e3:.1f} mA  5V load {I_5V*1e3:.0f} mA  3V3 {I_3V3*1e3:.0f} mA  12V total {I_12V*1e3:.0f} mA")
    print(f"AUX LTC7801: fsw {AUX.fsw/1e3:.0f} kHz  ton(100.8V) {12/100.8/AUX.fsw*1e9:.0f} ns  dI {AUX.ripple(V_FULL)[1]*1e3:.0f} mA  "
          f"Ilim min {AUX.ilim()['min']:.2f} A  RITH {AUX.rith:.4g} CITH {AUX.cith*1e9:.3g}n CITHB {AUX.cithb*1e12:.3g}p  tss {AUX.tss*1e3:.2f} ms")
    fc, pm = AUX.margins(12 / I_12V); print(f"   loop at {I_12V*1e3:.0f} mA: fc {fc/1e3:.1f} kHz PM {pm:.1f}")
    e = esc(); print(f"   eff {e['l_aux']['eff']*100:.1f} %  Pin {e['p_aux_in']:.2f} W   LDO5 {P_LDO5:.2f} W  LDO3.3 {P_LDO33:.3f} W")
    print(f"ACS770: +/-{I_RANGE:.0f} A fits the ADC, {ADC_A_PER_LSB*1e3:.0f} mA/LSB;  Vbus ADC at 100.8 V = {VBUS_ADC_FULL:.3f} V")

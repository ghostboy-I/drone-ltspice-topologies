"""Hand calculations for topology 09: one 24S channel of the tricopter.
  24S pack -> PDB -> harness -> ESC DC link -> 150 V inverter + FOC (topology 03) -> T-Motor U15XL + 54x18 prop
  ESC aux supply   : DC link -> AUX12 buck (12 V, 0.5 A) -> bootstrap gate drivers + 3.3 V LDO (ESC microcontroller)
  Avionics supply  : PDB -> HV12 buck (12 V, 5 A) -> video/telemetry TX (12 V)
                                               -> BEC5 = topology 06 buck (5 V, 3 A) -> controller + receiver
                                                                                     -> 3.3 V LDO (sensors)
Every number the schematics and the design document use comes from here. Run it to print the design.
"""
import math, json, os
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
Vt = 0.02585

# ======================================================================================================
# 1. Pack, harness, DC link
# ======================================================================================================
CELLS = 24
V_EMPTY, V_NOM, V_FULL = 3.0 * CELLS, 3.7 * CELLS, 4.2 * CELLS       # 72.0 / 88.8 / 100.8 V
Rpk = 30e-3            # assumption: 24 x 1.0 mOhm (55 Ah semi-solid cell) + 6 mOhm interconnect and connector
Rh, Lh = 4.1e-3, 0.73e-6   # 8 AWG pair, 1 m each way: 2 x 2.06 mOhm; loop L = (mu0/pi) ln(s/r) = 0.73 uH/m (s 10 mm, r 1.63 mm)
CBULK, ESR_BULK = 16 * 150e-6, 20e-3 / 16    # 16 x 150 uF 125 V hybrid polymer (3.5 A ripple each)
CCER = 20e-6                                  # 10 x 2.2 uF 250 V X7R near the FETs

# ======================================================================================================
# 2. Motor, prop and FOC drive (topology 03 scaled to the U15XL)
# ======================================================================================================
KV = 38                                        # vendor (ligpower U15XL page)
R_LL = 17e-3                                   # vendor, line-line
Rph = R_LL / 2
Lph = 25e-6                                    # ASSUMPTION (no vendor value): measure line-line L with an LCR meter, Lph = L_LL/2
Pp = 21                                        # ASSUMPTION: 36N42P stator/magnet count typical of the U15 series
Jrot = 0.15                                    # ASSUMPTION: 2 x 0.47 kg blades as rods to R = 0.686 m (0.147) + rotor bell
Ke = 60 / (2 * math.pi * KV); Kph = Ke / math.sqrt(3); Kt = 1.5 * Kph
RPM_HOVER, Q_HOVER = 1824.0, 29.6              # Props/01 Phase 2, selected 1750-rpm design, hover hot day (BEMT)
RPM_TW2, Q_TW2 = 2217.0, 44.6                  # same design at thrust/weight 2
W_HOVER = RPM_HOVER * 2 * math.pi / 60
Kprop = Q_HOVER / W_HOVER ** 2                 # prop torque Q = Kprop w^2
# Iron + bearing + windage loss, calibrated on the vendor bench point (U15XL + 52x20, 50 % throttle):
VEND = dict(V=98.0, I=41.30, rpm=1836.0, Q=18.46)
w_v = VEND["rpm"] * 2 * math.pi / 60
iq_v = VEND["Q"] / Kt
P_vend_loss = VEND["V"] * VEND["I"] - VEND["Q"] * w_v
P_vend_cu = 1.5 * Rph * iq_v ** 2
P_vend_inv_est = 20.0                          # ESC loss at that point, from esc_loss() below (iterated once by hand)
Bfric = (P_vend_loss - P_vend_cu - P_vend_inv_est) / w_v ** 2     # drag torque Bfric*w, so drag power = Bfric w^2

# inverter: 150 V FETs, four in parallel per switch, modelled as one equivalent VDMOS (ESC150)
Fsw, Tdead, Vdrv, Rdrv = 20e3, 300e-9, 12.0, 4.7
ESC = dict(Rd=0.9e-3, Rs=0.15e-3, Vto=3.5, Kp=800, Is=10e-12, N=1.05, Rb=1e-3, Tt=50e-9,
           Cgs=20e-9, Cgdmax=4e-9, Cgdmin=80e-12, Cjo=8e-9, Vds=150, Qg=276e-9)
Imax = 210.0                                   # iq limit (A amplitude), = Q_TW2 + drag on the shaft
Fci = 1e3; Kpi = Lph * 2 * math.pi * Fci; Kii = Rph * 2 * math.pi * Fci          # current PI, pole-zero cancellation
Fcw = 10.0; Kpw = Jrot * 2 * math.pi * Fcw / Kt; Kiw = Kpw * 2 * math.pi * Fcw / 4  # speed PI

ron_esc = ESC["Rd"] + ESC["Rs"] + 1 / (ESC["Kp"] * (Vdrv - ESC["Vto"]))


def drag(w): return Bfric * w
def load_torque(w): return Kprop * w * abs(w) + drag(w)


def qgd_esc(vds):
    """Gate-drain charge between Vds and ~0 for the VDMOS Cgd model: Cgdmin when Vdg is large, Cgdmax near zero.
    Crude two-segment estimate: Cgdmin over the whole swing + Cgdmax over the last ~Vplateau volts."""
    return ESC["Cgdmin"] * vds + ESC["Cgdmax"] * 5.0


def esc_loss(iq, vbus):
    """Inverter loss for a sinusoidal phase current of amplitude iq on bus vbus (same method as topology 07)."""
    iabs = 2 / math.pi * iq
    cond = 1.5 * iq ** 2 * ron_esc
    vf = ESC["N"] * Vt * math.log(max(iabs, 1e-3) / ESC["Is"]) + iabs * ESC["Rb"]
    dead = 3 * 2 * Tdead * Fsw * vf * iabs
    rr = 3 * vbus * ESC["Tt"] * iabs * Fsw
    vplat = ESC["Vto"] + math.sqrt(2 * max(iabs, 0.1) / ESC["Kp"])
    q = qgd_esc(vbus)
    t_on, t_off = q * Rdrv / (Vdrv - vplat), q * Rdrv / vplat
    sw = 3 * 0.5 * vbus * iabs * (t_on + t_off) * Fsw
    qoss = 2 * ESC["Cjo"] * (math.sqrt(1 + vbus) - 1)          # body-diode junction, Vj = 1 V, M = 0.5
    oss = 3 * qoss * vbus * Fsw
    return dict(cond=cond, dead=dead, rr=rr, sw=sw, oss=oss, total=cond + dead + rr + sw + oss, t_on=t_on, t_off=t_off, vf=vf)


def motor_point(w, Te, vbus):
    """dq steady state with id = 0: vd = -we L iq, vq = R iq + Kph w."""
    iq = Te / Kt; we = Pp * w
    vd, vq = -we * Lph * iq, Rph * iq + Kph * w
    vm = math.hypot(vd, vq)
    p_el = 1.5 * vq * iq
    inv = esc_loss(iq, vbus)
    return dict(iq=iq, vd=vd, vq=vq, vm=vm, M=vm / (vbus / 2), vlim=vbus / math.sqrt(3), p_el=p_el,
                p_cu=1.5 * Rph * iq ** 2, p_shaft=Kprop * w ** 3, p_drag=drag(w) * w, inv=inv, p_in=p_el + inv["total"],
                phi=math.atan2(-vd, vq))


def kolar(iq, vd, vq, vbus):
    """RMS of the AC part of the inverter's DC-link current (Kolar & Round), sinusoidal currents, SVPWM."""
    Vm = math.hypot(vd, vq); phi = math.atan2(-vd, vq); M = Vm / (vbus / 2)
    return iq / math.sqrt(2) * math.sqrt(max(2 * M * (math.sqrt(3) / (4 * math.pi) +
                                                       math.cos(phi) ** 2 * (math.sqrt(3) / math.pi - 9 * M / 16)), 0))


# ======================================================================================================
# 3. Synchronous buck converters: one design procedure (topology 06), used three times
# ======================================================================================================
E96 = [100, 102, 105, 107, 110, 113, 115, 118, 121, 124, 127, 130, 133, 137, 140, 143, 147, 150, 154, 158, 162, 165, 169,
       174, 178, 182, 187, 191, 196, 200, 205, 210, 215, 221, 226, 232, 237, 243, 249, 255, 261, 267, 274, 280, 287, 294,
       301, 309, 316, 324, 332, 340, 348, 357, 365, 374, 383, 392, 402, 412, 422, 432, 442, 453, 464, 475, 487, 499, 511,
       523, 536, 549, 562, 576, 590, 604, 619, 634, 649, 665, 681, 698, 715, 732, 750, 768, 787, 806, 825, 845, 866, 887,
       909, 931, 953, 976]
E12 = [10, 12, 15, 18, 22, 27, 33, 39, 47, 56, 68, 82]


def snap(x, series):
    d = 10 ** math.floor(math.log10(x)); m = x / d
    best = min(series + [series[0] * 10], key=lambda s: abs(math.log(m / (s / series[0]))))
    return best / series[0] * d


# FET models (VDMOS, inline because the LTspice libraries are encoded)
FETS = {
    # 150 V, approximations of Infineon BSC520N15NS3 (top) and BSC360N15NS3 (bottom), the parts the 24S hardware BEC uses
    "HV_TOP": dict(Rd=40e-3, Rs=5e-3, Vto=3.0, Kp=15, Cgdmax=200e-12, Cgdmin=3e-12, Cgs=650e-12, Cjo=250e-12, Rb=60e-3, Vds=150, Qg=9e-9),
    "HV_BOT": dict(Rd=28e-3, Rs=4e-3, Vto=3.0, Kp=20, Cgdmax=250e-12, Cgdmin=4e-12, Cgs=850e-12, Cjo=330e-12, Rb=40e-3, Vds=150, Qg=11e-9),
    # 30 V, topology 06
    "BUCK_FET": dict(Rd=3e-3, Rs=1e-3, Vto=1.6, Kp=60, Cgdmax=400e-12, Cgdmin=60e-12, Cgs=900e-12, Cjo=500e-12, Rb=6e-3, Vds=30, Qg=10e-9),
}


def vdmos_line(name, f, tt="20n"):
    return (f"!.model {name} VDMOS(Rd={f['Rd']:g} Rs={f['Rs']:g} Vto={f['Vto']:g} Kp={f['Kp']:g} Cgdmax={f['Cgdmax']:g} "
            f"Cgdmin={f['Cgdmin']:g} Cgs={f['Cgs']:g} Cjo={f['Cjo']:g} Vj=1 M=0.5 Is={f.get('Is', 2e-12):g} N=1.05 Rb={f['Rb']:g} Tt={tt} "
            f"Vds={f['Vds']:g} Qg={f['Qg']:g} mfg=Learning)")


class Buck:
    """Voltage-mode synchronous buck with input feed-forward (ramp = Vin/KFF) and a Type III compensator."""
    Vref, Rbot, KFF = 0.8, 10e3, 10.0

    def __init__(self, name, vin, vin_min, vin_max, vout, iout, iout_typ, fsw, L, DCR, c_each, n_c, derate, esr_each,
                 cin, fc, top, bot, vdrv, tdead, RgH, RgL, Fff, parts=None):
        self.__dict__.update(locals()); del self.__dict__["self"]
        self.C = c_each * n_c * derate; self.ESR = esr_each / n_c
        self.Rtop = snap(self.Rbot * (vout / self.Vref - 1), E96)
        self.vset = self.Vref * (1 + self.Rtop / self.Rbot)
        self.f0 = 1 / (2 * math.pi * math.sqrt(L * self.C))
        self.fesr = 1 / (2 * math.pi * self.ESR * self.C)
        self.ideal = self._solve_r2()
        self.parts = parts or self._snap_parts(self.ideal)

    # ---- small-signal ----
    def plant(self, f, Rload):
        s = 2j * math.pi * np.asarray(f, dtype=float)
        Zc = self.ESR + 1 / (s * self.C); Zo = 1 / (1 / Zc + 1 / Rload)
        return Zo / (Zo + self.DCR + s * self.L)

    def comp(self, f, R2, C1, C2, R3, C3):
        s = 2j * math.pi * np.asarray(f, dtype=float); R1 = self.Rtop
        Zf = (R2 + 1 / (s * C1)) * (1 / (s * C2)) / (R2 + 1 / (s * C1) + 1 / (s * C2))
        Zi = 1 / (1 / R1 + 1 / (R3 + 1 / (s * C3)))
        return -Zf / Zi

    def loop(self, f, parts=None, Rload=None):
        Rload = Rload or self.vout / self.iout
        return -self.KFF * self.plant(f, Rload) * self.comp(f, *(parts or self.parts))

    def _design(self, R2):
        fz1, fz2 = 0.5 * self.f0, 0.7 * self.f0
        fp1, fp2 = min(self.fesr, self.fsw / 2), self.fsw / 2
        C1 = 1 / (2 * math.pi * R2 * fz1); C2 = 1 / (2 * math.pi * R2 * fp1)
        C3 = 1 / (2 * math.pi * self.Rtop * fz2); R3 = 1 / (2 * math.pi * C3 * fp2)
        return (R2, C1, C2, R3, C3)

    def _solve_r2(self):
        lo, hi = 1e2, 1e7
        for _ in range(100):
            mid = math.sqrt(lo * hi)
            if abs(self.loop(self.fc, self._design(mid))) > 1: hi = mid
            else: lo = mid
        return self._design(math.sqrt(lo * hi))

    @staticmethod
    def _snap_parts(p):
        return (snap(p[0], E96), snap(p[1], E12), snap(p[2], E12), snap(p[3], E96), snap(p[4], E12))

    def margins(self, Rload=None, parts=None):
        f = np.logspace(2, 6.5, 6000); T = self.loop(f, parts, Rload)
        i = int(np.argmax(np.abs(T) < 1))
        return f[i], 180 + float(np.degrees(np.angle(T[i])))

    def line_cl(self, f, vin=None, ff=True, Rload=None):
        """Closed-loop Vout/Vin (audio susceptibility). Feed-forward through a first-order sense filter leaves (1 - F)."""
        vin = vin or self.vin; Rload = Rload or self.vout / self.iout
        s = 2j * math.pi * np.asarray(f, dtype=float)
        F = 1 / (1 + s / (2 * math.pi * self.Fff)) if ff else 0
        return (self.vout / vin) * self.plant(f, Rload) * (1 - F) / (1 + self.loop(f, None, Rload))

    def step_peak(self, dVin, trise, vin=None):
        """Peak output deviation for an input ramp of dVin over trise (inverse FFT of line_cl, as in topology 06)."""
        N, dt = 2 ** 16, 50e-9
        t = np.arange(N) * dt; u = np.clip(t / trise, 0, 1) * dVin
        f = np.fft.rfftfreq(N, dt); Hf = self.line_cl(np.maximum(f, 1.0), vin)
        y = np.fft.irfft(np.fft.rfft(u) * Hf, n=N)
        return float(np.max(np.abs(y[: N // 2])))

    def zout_cl(self, f, Rload=None):
        """Closed-loop output impedance: open-loop Zout / (1 + T)."""
        Rload = Rload or self.vout / self.iout
        s = 2j * math.pi * np.asarray(f, dtype=float)
        Zc = self.ESR + 1 / (s * self.C); Zl = self.DCR + s * self.L
        Zo = 1 / (1 / Zc + 1 / Zl + 1 / Rload)
        return Zo / (1 + self.loop(f, None, Rload))

    # ---- large-signal ----
    def ripple(self, vin=None):
        vin = vin or self.vin; D = self.vout / vin
        dI = (vin - self.vout) * D / (self.L * self.fsw)
        return D, dI, dI / (8 * self.fsw * self.C) + dI * self.ESR

    def step_dip(self, dI):
        """Load-step dip estimate (06): the loop answers within ~1/(2 pi fc); until then the capacitor supplies dI."""
        return dI / (2 * math.pi * self.fc_actual() * self.C)

    def fc_actual(self):
        return self.margins()[0]

    def losses(self, iout, vin=None):
        """Loss budget; the switching model drives its gates from ideal sources, so 'gate' is not in the simulated Pin."""
        vin = vin or self.vin; D, dI, _ = self.ripple(vin)
        T, B = FETS[self.top], FETS[self.bot]
        ron = lambda f: f["Rd"] + f["Rs"] + 1 / (f["Kp"] * (self.vdrv - f["Vto"]))
        irms2 = iout ** 2 + dI ** 2 / 12
        hs = D * irms2 * ron(T); ls = (1 - D) * irms2 * ron(B); dcr = irms2 * self.DCR
        i_on, i_off = max(iout - dI / 2, 0), iout + dI / 2          # current at hard turn-on / turn-off of the top FET
        vplat = T["Vto"] + math.sqrt(2 * max(i_off, 0.05) / T["Kp"])
        qgd = T["Cgdmin"] * vin + T["Cgdmax"] * 3.0
        t_on = qgd * self.RgH / max(self.vdrv - vplat, 0.5); t_off = qgd * self.RgH / vplat
        sw = 0.5 * vin * (i_on * t_on + i_off * t_off) * self.fsw
        qoss = sum(2 * f["Cjo"] * (math.sqrt(1 + vin) - 1) for f in (T, B))
        oss = 0.5 * qoss * vin * self.fsw
        vf = 0.75
        dead = 2 * vf * iout * self.tdead * self.fsw
        gate = (T["Qg"] + B["Qg"]) * self.vdrv * self.fsw
        pout = self.vset * iout
        sim = hs + ls + dcr + sw + oss + dead
        return dict(D=D, dI=dI, hs=hs, ls=ls, dcr=dcr, sw=sw, oss=oss, dead=dead, gate=gate, total_sim=sim,
                    total=sim + gate, pout=pout, eta_sim=pout / (pout + sim), eta=pout / (pout + sim + gate),
                    pin_sim=pout + sim, t_on=t_on, t_off=t_off)

    def summary(self):
        fc, pm = self.margins(); fcl, pml = self.margins(Rload=self.vout / (0.1 * self.iout))
        D, dI, dV = self.ripple()
        return dict(name=self.name, Rtop=self.Rtop, vset=self.vset, C=self.C, ESR=self.ESR, f0=self.f0, fesr=self.fesr,
                    parts=self.parts, ideal=self.ideal, fc=fc, pm=pm, fc_light=fcl, pm_light=pml, D=D, dI=dI, dV=dV,
                    D_min=self.vout / self.vin_max, D_max=self.vout / self.vin_min,
                    ton_min=self.vout / self.vin_max / self.fsw)


# ---- the three converters ----
AUX12 = Buck("AUX12", vin=86.0, vin_min=V_EMPTY, vin_max=V_FULL, vout=12.0, iout=0.5, iout_typ=0.17, fsw=250e3,
             L=220e-6, DCR=0.45, c_each=10e-6, n_c=2, derate=0.55, esr_each=5e-3, cin=2.2e-6, fc=20e3,
             top="HV_TOP", bot="HV_BOT", vdrv=10.0, tdead=40e-9, RgH=10, RgL=1, Fff=50e3)
HV12 = Buck("HV12", vin=88.0, vin_min=V_EMPTY, vin_max=V_FULL, vout=12.0, iout=5.0, iout_typ=2.75, fsw=200e3,
            L=33e-6, DCR=15e-3, c_each=22e-6, n_c=4, derate=0.6, esr_each=5e-3, cin=8.8e-6, fc=20e3,
            top="HV_TOP", bot="HV_BOT", vdrv=10.0, tdead=40e-9, RgH=10, RgL=1, Fff=50e3)
# BEC5 is topology 06 unchanged (same L, C, Type III parts); only its input moves from the 4S bus to the 12 V rail
BEC5 = Buck("BEC5", vin=12.0, vin_min=11.0, vin_max=12.6, vout=5.0, iout=3.0, iout_typ=2.3, fsw=500e3,
            L=6.8e-6, DCR=15e-3, c_each=22e-6, n_c=3, derate=0.6, esr_each=5e-3, cin=10e-6, fc=50e3,
            top="BUCK_FET", bot="BUCK_FET", vdrv=5.0, tdead=20e-9, RgH=10, RgL=1, Fff=100e3,
            parts=(18.7e3, 1.8e-9, 33e-12, 1.43e3, 470e-12))
BUCKS = [AUX12, HV12, BEC5]

# ======================================================================================================
# 4. Loads, LDOs, gate drive
# ======================================================================================================
I_VTX = 1.5          # video / telemetry transmitter, 12 V
I_FC, I_RX = 1.5, 0.3   # flight controller (+ GPS, peripherals) and RC receiver, 5 V
I_SENS = 0.5         # 3.3 V sensors (IMU, baro, mag) from the FC LDO
I_MCU = 0.08         # ESC microcontroller + encoder, 3.3 V from the ESC LDO
IQ_LDO, VDO = 1e-3, 0.25
V33 = 3.3
I_DRV_Q = 5e-3       # gate-driver IC quiescent current, from 12 V
CBOOT, RBOOT = 1e-6, 2.0


VPLAT_HAND = ESC["Vto"] + math.sqrt(2 * 92.4 / ESC["Kp"])      # plateau at the hover <|i|> (Vgs where Id = Kp/2 (Vgs-Vto)^2)


def qg_esc_hand(vds=V_NOM):
    """Gate charge to Vdrv: Cgs*Vdrv (gate-source) + Cgdmin*Vds (Miller plateau, drain falling from Vds)
    + Cgdmax*(Vdrv - Vplat) (after the plateau the drain sits near 0 and Cgd is at its large value)."""
    return ESC["Cgs"] * Vdrv + ESC["Cgdmin"] * vds + ESC["Cgdmax"] * (Vdrv - VPLAT_HAND)


def gate_drive(qg):
    igd = 6 * qg * Fsw                       # every switch is charged once per PWM period
    return dict(qg=qg, igd=igd, i12=igd + I_DRV_Q + I_MCU + IQ_LDO, dv_boot=qg / CBOOT,
                tau_boot=RBOOT * CBOOT, p_ldo_esc=(12.0 - V33) * I_MCU)


# ======================================================================================================
# 5. The whole chain at hover
# ======================================================================================================
def avionics():
    """Power budget of the avionics supply, from the loads back to the PDB."""
    i5 = I_FC + I_RX + I_SENS + IQ_LDO
    l5 = BEC5.losses(i5); p5_in = l5["pout"] + l5["total_sim"]
    i12 = I_VTX + p5_in / HV12.vset
    l12 = HV12.losses(i12); p12_in = l12["pout"] + l12["total_sim"]
    return dict(i5=i5, l5=l5, p5_in=p5_in, i12=i12, l12=l12, p12_in=p12_in,
                p_loads=12 * I_VTX + 5 * (I_FC + I_RX) + V33 * I_SENS, p_ldo=(BEC5.vset - V33) * I_SENS)


def solve_chain(Te, w, vpk=V_NOM, qg=None):
    """Bus voltage and pack current with the drive and the avionics both drawing constant power.
    PDB: V_pdb = Vpk - (I_esc + I_av) Rpk;  ESC bus: V_bus = V_pdb - I_esc Rh."""
    qg = qg or qg_esc_hand()
    av = avionics(); gd = gate_drive(qg)
    vbus = vpk
    for _ in range(50):
        mp = motor_point(w, Te, vbus)
        l_aux = AUX12.losses(gd["i12"], vin=vbus); p_aux = l_aux["pout"] + l_aux["total_sim"]
        p_esc = mp["p_in"] + p_aux
        i_esc = p_esc / vbus
        vpdb = vpk - (i_esc + av["p12_in"] / vpk) * Rpk
        for _ in range(5):
            vpdb = vpk - (i_esc + av["p12_in"] / vpdb) * Rpk
        vbus = vpdb - i_esc * Rh
    i_av = av["p12_in"] / vpdb
    return dict(mp=mp, av=av, gd=gd, l_aux=l_aux, p_aux=p_aux, p_esc=p_esc, i_esc=i_esc, i_av=i_av, i_pk=i_esc + i_av,
                vpdb=vpdb, vbus=vbus, p_pk_loss=(i_esc + i_av) ** 2 * Rpk, p_harn=i_esc ** 2 * Rh,
                p_chem=vpk * (i_esc + i_av), icap=kolar(mp["iq"], mp["vd"], mp["vq"], vbus))


def hover():
    return solve_chain(load_torque(W_HOVER), W_HOVER)


def punch():
    """Throttle punch: iq hits Imax while the speed is still ~hover (the 0.15 kg m^2 rotor needs ~0.5 s to speed up)."""
    return solve_chain(Kt * Imax, W_HOVER)


def iq_rise():
    """Current loop with pole-zero cancellation is first order at Fci: 10-90 % rise = ln 9 / (2 pi Fci)."""
    return math.log(9) / (2 * math.pi * Fci)


def bus_ripple(icap, vbus):
    """DC-link ripple estimate: the Kolar RMS current as a triangle-ish wave at 2*Fsw into C, plus ESR."""
    return icap * math.sqrt(12) / 2 / (2 * 2 * Fsw * (CBULK + CCER)) + icap * math.sqrt(2) * ESR_BULK


def hotplug_energy(v=V_FULL):
    return 0.5 * (CBULK + CCER) * v ** 2


def collect():
    h, p = hover(), punch()
    out = dict(hover=h, punch=p, bucks={b.name: b.summary() for b in BUCKS}, Kprop=Kprop, Bfric=Bfric, Kt=Kt, Kph=Kph,
               W_HOVER=W_HOVER, iq_rise=iq_rise(), ripple=bus_ripple(h["icap"], h["vbus"]), hotplug=hotplug_energy(),
               vend=dict(loss=P_vend_loss, cu=P_vend_cu, iq=iq_v))
    return out


def _clean(o):
    if isinstance(o, dict): return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [_clean(v) for v in o]
    if isinstance(o, (np.floating, np.integer)): return float(o)
    return o


if __name__ == "__main__":
    c = collect(); h, p = c["hover"], c["punch"]; mp = h["mp"]
    print(f"Motor: Ke {Ke:.4f}  Kph {Kph:.4f}  Kt {Kt:.4f} N m/A   Kprop {Kprop:.3e}   Bfric {Bfric:.4f} (vendor loss {P_vend_loss:.0f} W, cu {P_vend_cu:.0f} W)")
    print(f"Hover: w {W_HOVER:.1f} rad/s  Te {load_torque(W_HOVER):.2f} N m  iq {mp['iq']:.1f} A  vd {mp['vd']:.2f} vq {mp['vq']:.2f} |v| {mp['vm']:.2f} "
          f"(limit {mp['vlim']:.1f})  M {mp['M']:.3f}")
    print(f"       shaft {mp['p_shaft']:.0f} W  drag {mp['p_drag']:.0f}  cu {mp['p_cu']:.0f}  inverter {mp['inv']['total']:.1f} {{"
          + ", ".join(f"{k} {v:.2f}" for k, v in mp['inv'].items() if k not in ('total', 't_on', 't_off', 'vf')) + "}")
    print(f"       Vbus {h['vbus']:.3f}  Vpdb {h['vpdb']:.3f}  I_esc {h['i_esc']:.2f}  I_av {h['i_av']:.3f}  I_pk {h['i_pk']:.2f}  Icap_rms {h['icap']:.1f}  ripple {c['ripple']:.3f} V")
    print(f"       drive eff (shaft / ESC input) {mp['p_shaft']/h['p_esc']:.4f}   system eff (shaft+avionics loads / chemical) "
          f"{(mp['p_shaft']+h['av']['p_loads'])/h['p_chem']:.4f}")
    pm = p["mp"]
    print(f"Punch: iq {pm['iq']:.0f}  |v| {pm['vm']:.2f} limit {pm['vlim']:.2f}  Vbus {p['vbus']:.3f}  I_esc {p['i_esc']:.2f}  iq rise {c['iq_rise']*1e6:.0f} us")
    gd = h["gd"]
    print(f"Gate drive: Qg(hand) {gd['qg']*1e9:.0f} nC  Igd {gd['igd']*1e3:.1f} mA  I12 {gd['i12']*1e3:.1f} mA  dV_boot {gd['dv_boot']:.3f} V  ESC LDO {gd['p_ldo_esc']:.2f} W")
    av = h["av"]
    print(f"Avionics: I5 {av['i5']:.3f}  P5in {av['p5_in']:.2f} W  I12 {av['i12']:.3f}  P12in {av['p12_in']:.2f} W  loads {av['p_loads']:.1f} W  FC LDO {av['p_ldo']:.2f} W")
    print(f"Hot-plug energy at 100.8 V: {c['hotplug']:.1f} J")
    for b in BUCKS:
        s = b.summary()
        print(f"{b.name}: Rtop {s['Rtop']:.4g} Vset {s['vset']:.3f}  C {s['C']*1e6:.1f}u f0 {s['f0']/1e3:.2f} kHz fesr {s['fesr']/1e3:.0f} kHz  "
              f"D {s['D_min']:.3f}-{s['D_max']:.3f} ton_min {s['ton_min']*1e9:.0f} ns  dI {s['dI']:.3f} dV {s['dV']*1e3:.2f} mV")
        print(f"     parts R2 C1 C2 R3 C3 = " + " ".join(f"{x:.4g}" for x in s['parts']) + "   (ideal " + " ".join(f"{x:.3g}" for x in s['ideal']) + ")")
        print(f"     fc {s['fc']/1e3:.1f} kHz PM {s['pm']:.1f}   light load fc {s['fc_light']/1e3:.1f} PM {s['pm_light']:.1f}")
        l = b.losses(b.iout_typ)
        print(f"     at {b.iout_typ} A: " + ", ".join(f"{k} {v*1e3:.0f}m" for k, v in l.items() if k in ('hs', 'ls', 'dcr', 'sw', 'oss', 'dead', 'gate'))
              + f"  eta_sim {l['eta_sim']:.4f} eta {l['eta']:.4f}")
        print(f"     |line| at {Fsw/1e3:.0f} kHz: {abs(b.line_cl(Fsw)):.4f}   (no FF {abs(b.line_cl(Fsw, ff=False)):.4f})")
    json.dump(_clean(c), open(os.path.join(HERE, "hand_calc.json"), "w"), indent=1)

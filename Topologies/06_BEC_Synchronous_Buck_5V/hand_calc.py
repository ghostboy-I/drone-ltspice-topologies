"""Hand design of the BEC: 4S -> 5 V / 3 A synchronous buck, voltage mode, Type-III compensation, input feed-forward."""
import math, numpy as np

Vin, Vin_min, Vin_max = 15.2, 12.8, 16.8          # 4S: nominal, empty (3.2 V/cell), full (4.2 V/cell)
Vout, Iout, Iout_min = 5.0, 3.0, 0.3
fsw = 500e3
L, DCR = 6.8e-6, 15e-3
Cnom, Ncap, derate, ESRc = 22e-6, 3, 0.6, 5e-3    # 3 x 22 uF X7R, ~40 % lost to DC bias at 5 V
C = Cnom * Ncap * derate; ESR = ESRc / Ncap
Vref = 0.8; Rbot = 10e3; Rtop = 52.3e3                 # E96: Vout = 0.8*(1 + 52.3/10) = 4.984 V
Vout_set = Vref * (1 + Rtop / Rbot)
KFF = 10.0                                         # feed-forward: ramp amplitude = Vin / KFF  ->  modulator gain = KFF
fc_target, Cin = 50e3, 10e-6

D = Vout / Vin
dI = (Vin - Vout) * D / (L * fsw)
dV = dI / (8 * fsw * C) + dI * ESR
f0 = 1 / (2 * math.pi * math.sqrt(L * C)); w0 = 2 * math.pi * f0
fesr = 1 / (2 * math.pi * ESR * C)
Iin_rms = Iout * math.sqrt(D * (1 - D))           # input capacitor RMS current (ripple of the switched input current)

def plant(f, Rload):
    """Duty -> Vout transfer of the averaged buck, normalised by Vin (the modulator gain KFF*Vin/Vin is applied separately)."""
    s = 2j * math.pi * np.asarray(f)
    Zc = ESR + 1 / (s * C); Zo = 1 / (1 / Zc + 1 / Rload)
    return Zo / (Zo + DCR + s * L)

# ---- Type III placement: zeros at f0 (cancel the double pole), poles at the ESR zero and fsw/2 ----
R1 = Rtop
fz1, fz2 = 0.5 * f0, 0.7 * f0          # zeros a little below f0 buy phase margin
fp1, fp2 = min(fesr, fsw / 2), fsw / 2
def comp(f, R2, C1, C2, R3, C3):
    s = 2j * math.pi * np.asarray(f)
    Zf = (R2 + 1 / (s * C1)) * (1 / (s * C2)) / (R2 + 1 / (s * C1) + 1 / (s * C2))   # feedback: (R2 + C1) || C2
    Zi = 1 / (1 / R1 + 1 / (R3 + 1 / (s * C3)))                                       # input: R1 || (R3 + C3)
    return -Zf / Zi                                                                   # inverting error amplifier
def design(R2):
    C1 = 1 / (2 * math.pi * R2 * fz1)
    C2 = 1 / (2 * math.pi * R2 * fp1)
    C3 = 1 / (2 * math.pi * R1 * fz2)
    R3 = 1 / (2 * math.pi * C3 * fp2)
    return R2, C1, C2, R3, C3
def loop(f, parts, Rload=Vout / Iout):
    return -KFF * plant(f, Rload) * comp(f, *parts)   # minus: the error amp inverts, the loop sign is restored
# pick R2 so that |T| = 1 at fc_target
lo, hi = 1e2, 1e6
for _ in range(80):
    mid = math.sqrt(lo * hi)
    if abs(loop(fc_target, design(mid))) > 1: hi = mid
    else: lo = mid
PARTS_IDEAL = design(math.sqrt(lo * hi))
PARTS = (18.7e3, 1.8e-9, 33e-12, 1.43e3, 470e-12)     # snapped to E96 / E12 values: R2, C1, C2, R3, C3

def margins(parts, Rload):
    f = np.logspace(2, 6, 4000); T = loop(f, parts, Rload)
    i = np.argmax(np.abs(T) < 1); fc = f[i]
    return fc, 180 + np.degrees(np.angle(T[i]))          # phase margin = 180 deg + phase of T at |T| = 1

if __name__ == "__main__":
    print(f"D={D:.3f} dI={dI:.3f} A  dV={dV*1e3:.2f} mV  C_eff={C*1e6:.1f} uF  f0={f0/1e3:.2f} kHz  fesr={fesr/1e3:.0f} kHz  Rtop={Rtop:.0f}")
    print("ideal R2 C1 C2 R3 C3 =", ["%.4g" % p for p in PARTS_IDEAL], " used:", PARTS)
    for R in (Vout / Iout, Vout / Iout_min):
        print("Rload", R, "fc, PM =", margins(PARTS, R))

# ---- line (input) disturbance rejection: closed-loop audio susceptibility ----
Fff = 100e3                                         # feed-forward sense filter
def line_cl(f, ff, parts=None, Rload=Vout / Iout):
    """Vout/Vin transfer with the loop closed. Without feed-forward the modulator passes D*Vin variations straight to the
    LC filter; ideal feed-forward cancels them (d*Vin fixed), a filtered one leaves (1 - F) of them."""
    parts = PARTS if parts is None else parts
    s = 2j * math.pi * np.asarray(f)
    F = 1 / (1 + s / (2 * math.pi * Fff)) if ff else 0
    return D * plant(f, Rload) * (1 - F) / (1 + loop(f, parts, Rload))
def step_peak(dVin, ff, trise=50e-6):
    """Peak output deviation for an input ramp-step of dVin (numerical inverse FFT of the hand transfer function)."""
    N, dt = 2 ** 16, 50e-9
    t = np.arange(N) * dt; u = np.clip(t / trise, 0, 1) * dVin
    f = np.fft.rfftfreq(N, dt); Hf = line_cl(np.maximum(f, 1.0), ff)
    y = np.fft.irfft(np.fft.rfft(u - u[-1] * 0) * Hf, n=N)
    return float(np.max(np.abs(y[: N // 2])))

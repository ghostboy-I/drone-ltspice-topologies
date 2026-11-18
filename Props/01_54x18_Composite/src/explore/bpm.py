"""BPM turbulent-boundary-layer trailing-edge (TBL-TE) noise, from Brooks, Pope & Marcolini, "Airfoil Self-Noise and
Prediction", NASA RP-1218 (1989). Equation numbers refer to that report.

Implemented: untripped (natural transition) boundary-layer thickness fits (eqs. 5-6, 9, 12/15), the TBL-TE spectrum
SPL_p, SPL_s, SPL_alpha (eqs. 24-27), the stalled form (28-30), the Strouhal numbers (31-34), spectral shapes A and B
(35-46), the amplitude functions K1, dK1, K2 (47-50), and the high/low-frequency directivity D_h, D_l (B1, B2).
Not implemented: laminar vortex shedding, tip vortex and bluntness noise (other BPM sources).
Units SI; angles in degrees where the report uses degrees.
"""
import math
import numpy as np

C0 = 340.46           # speed of sound used in the report [m/s]
NU = 1.4529e-5        # kinematic viscosity used in the report [m^2/s]
BANDS = np.array([100, 125, 160, 200, 250, 315, 400, 500, 630, 800, 1000, 1250, 1600, 2000, 2500, 3150, 4000, 5000,
                  6300, 8000, 10000, 12500, 16000, 20000], float)


def bl_untripped(c, U, alpha_deg, nu=NU):
    """delta*_p, delta*_s [m] at the trailing edge, untripped BL, eqs. (6), (9), (12)/(15)."""
    Rc = U * c / nu; lr = math.log10(Rc)
    ds0 = c * 10 ** (3.0187 - 1.5397 * lr + 0.1059 * lr * lr)
    a = abs(alpha_deg)
    dp = ds0 * 10 ** (-0.0432 * a + 0.00113 * a * a)
    if a <= 7.5:
        ds = ds0 * 10 ** (0.0679 * a)
    elif a <= 12.5:
        ds = ds0 * 0.0162 * 10 ** (0.3066 * a)
    else:
        ds = ds0 * 52.42 * 10 ** (0.0258 * a)
    return dp, ds


def _amin(a):
    if a < 0.204: return math.sqrt(max(67.552 - 886.788 * a * a, 0.0)) - 8.219
    if a <= 0.244: return -32.665 * a + 3.981
    return -142.795 * a ** 3 + 103.656 * a * a - 57.757 * a + 6.006


def _amax(a):
    if a < 0.13: return math.sqrt(max(67.552 - 886.788 * a * a, 0.0)) - 8.219
    if a <= 0.321: return -15.901 * a + 1.098
    return -4.669 * a ** 3 + 3.491 * a * a - 16.699 * a + 1.149


def A_shape(st, st_peak, Rc):
    a = abs(math.log10(st / st_peak))
    if Rc < 9.52e4: a0 = 0.57
    elif Rc <= 8.57e5: a0 = -9.57e-13 * (Rc - 8.57e5) ** 2 + 1.13
    else: a0 = 1.13
    AR = (-20 - _amin(a0)) / (_amax(a0) - _amin(a0))
    return _amin(a) + AR * (_amax(a) - _amin(a))


def _bmin(b):
    if b < 0.13: return math.sqrt(max(16.888 - 886.788 * b * b, 0.0)) - 4.109
    if b <= 0.145: return -83.607 * b + 8.138
    return -817.810 * b ** 3 + 355.210 * b * b - 135.024 * b + 10.619


def _bmax(b):
    if b < 0.10: return math.sqrt(max(16.888 - 886.788 * b * b, 0.0)) - 4.109
    if b <= 0.187: return -31.330 * b + 1.854
    return -80.541 * b ** 3 + 44.174 * b * b - 39.381 * b + 2.344


def B_shape(st, st2, Rc):
    b = abs(math.log10(st / st2))
    if Rc < 9.52e4: b0 = 0.30
    elif Rc <= 8.57e5: b0 = -4.48e-13 * (Rc - 8.57e5) ** 2 + 0.56
    else: b0 = 0.56
    BR = (-20 - _bmin(b0)) / (_bmax(b0) - _bmin(b0))
    return _bmin(b) + BR * (_bmax(b) - _bmin(b))


def K1(Rc):
    if Rc < 2.47e5: return -4.31 * math.log10(Rc) + 156.3
    if Rc <= 8.0e5: return -9.0 * math.log10(Rc) + 181.6
    return 128.5


def dK1(alpha, Rdp):
    return alpha * (1.43 * math.log10(Rdp) - 5.29) if Rdp <= 5000 else 0.0


def K2(alpha, M, Rc):
    g, g0 = 27.094 * M + 3.31, 23.43 * M + 4.651
    be, be0 = 72.65 * M + 10.74, -34.19 * M - 13.82
    if alpha < g0 - g: k = -1000.0
    elif alpha <= g0 + g: k = math.sqrt(max(be * be - (be / g) ** 2 * (alpha - g0) ** 2, 0.0)) + be0
    else: k = -12.0
    return K1(Rc) + k


def D_h(theta, phi, M, Mc):
    return 2 * math.sin(theta / 2) ** 2 * math.sin(phi) ** 2 / ((1 + M * math.cos(theta)) * (1 + (M - Mc) * math.cos(theta)) ** 2)


def D_l(theta, phi, M):
    return math.sin(theta) ** 2 * math.sin(phi) ** 2 / (1 + M * math.cos(theta)) ** 4


def tbl_te(c, L, U, alpha_deg, re, theta=math.pi / 2, phi=math.pi / 2, freqs=BANDS, c0=C0, nu=NU):
    """1/3-octave SPL [dB] of TBL-TE noise for one span segment. Returns dict of arrays: total, p, s, alpha."""
    M = U / c0; Mc = 0.8 * M; Rc = U * c / nu; a = abs(alpha_deg)
    dp, ds = bl_untripped(c, U, a, nu); Rdp = U * dp / nu
    Dh, Dl = D_h(theta, phi, M, Mc), D_l(theta, phi, M)
    st1 = 0.02 * M ** -0.6
    st2 = st1 * (1.0 if a < 1.33 else (10 ** (0.0054 * (a - 1.33) ** 2) if a <= 12.5 else 4.72))
    st1b = (st1 + st2) / 2
    k1, k2 = K1(Rc), K2(a, M, Rc)
    g0 = 23.43 * M + 4.651
    stalled = a > min(g0, 12.5)
    out = {"p": [], "s": [], "alpha": [], "total": []}
    for f in freqs:
        stp, sts = f * dp / U, f * ds / U
        if not stalled:
            Lp = 10 * math.log10(dp * M ** 5 * L * Dh / re ** 2) + A_shape(stp, st1, Rc) + (k1 - 3) + dK1(a, Rdp)
            Ls = 10 * math.log10(ds * M ** 5 * L * Dh / re ** 2) + A_shape(sts, st1, Rc) + (k1 - 3)
            La = 10 * math.log10(ds * M ** 5 * L * Dh / re ** 2) + B_shape(sts, st2, Rc) + k2
        else:
            Lp = Ls = -1e9
            La = 10 * math.log10(ds * M ** 5 * L * Dl / re ** 2) + A_shape(sts, st2, 3 * Rc) + k2
        tot = 10 * math.log10(10 ** (Lp / 10) + 10 ** (Ls / 10) + 10 ** (La / 10))
        for k, v in (("p", Lp), ("s", Ls), ("alpha", La), ("total", tot)): out[k].append(v)
    out = {k: np.array(v) for k, v in out.items()}
    out.update({"st1": st1, "dstar_p": dp, "dstar_s": ds, "K1": k1, "Rc": Rc, "M": M})
    return out


def tip_vortex(c, U, alpha_tip_deg, re, theta=math.pi / 2, phi=math.pi / 2, freqs=BANDS, c0=C0, rounded=True):
    """1/3-octave SPL [dB] of tip-vortex formation noise, eqs. (61)-(67). alpha_tip_deg is alpha'_TIP (eq. 66),
    the tip angle already scaled by the tip-loading ratio. rounded: eq. (63) l/c = 0.008 alpha; else flat tip, eq. (67)."""
    a = abs(alpha_tip_deg); M = U / c0
    if rounded: l = 0.008 * a * c
    else: l = c * (0.0230 + 0.0169 * a if a <= 2 else 0.0378 + 0.0095 * a)
    Mmax = M * (1 + 0.036 * a); Umax = c0 * Mmax
    Dh = D_h(theta, phi, M, 0.8 * M)
    base = 10 * math.log10(M * M * Mmax ** 3 * l * l * Dh / re ** 2) + 126
    spl = np.array([base - 30.5 * (math.log10(f * l / Umax) + 0.3) ** 2 for f in freqs])
    return {"spl": spl, "l": l, "Mmax": Mmax, "Umax": Umax, "f_peak": 0.5012 * Umax / l, "peak": base}

"""Hand calculations for topology 04 (shared by plot_results.py and make_design_doc.py)."""
import math, numpy as np

mu0 = 4e-7 * math.pi
R_AWG14 = 8.28e-3                     # ohm/m, 14 AWG copper at 20 C
r_cond = 0.81e-3                      # 14 AWG conductor radius (m)
R_XT60 = 1e-3                         # connector pair, loop
Rbatt, ESRc, ESLc, Ccer, ESRb, ESLb, Cbulk = 20e-3, 2e-3, 2e-9, 10e-6, 30e-3, 10e-9, 470e-6
Rsig = 27e-3                          # 20 cm of 26 AWG (133 ohm/km)
Fsw = 48e3
Pp, Rph, Lph, KV = 7, 50e-3, 7.5e-6, 2300
Kph = 60 / (2 * math.pi * KV) / math.sqrt(3)

CH = [dict(k=1, Vb=15.2, len=0.10, s=2.6e-3, rpm=14000, iq=7.28, desc="10 cm, wires side by side"),
      dict(k=2, Vb=15.0, len=0.30, s=2.6e-3, rpm=20000, iq=14.6, desc="30 cm, wires side by side"),
      dict(k=3, Vb=14.8, len=0.60, s=20e-3, rpm=10000, iq=3.80, desc="60 cm, wires 20 mm apart")]
IQ3_STEP = 25.0

def harness(c):
    Lp = mu0 / math.pi * math.log(c["s"] / r_cond)            # loop inductance per metre of a two-wire line
    return 2 * c["len"] * R_AWG14 + R_XT60, Lp * c["len"], Lp

def op_point(c, iq=None):
    iq = c["iq"] if iq is None else iq
    w = c["rpm"] * 2 * math.pi / 60; we = Pp * w
    vq = Rph * iq + Kph * w; vd = -we * Lph * iq
    P = 1.5 * vq * iq                                        # = 1.5 (vd id + vq iq), id = 0
    Rl, Ll, _ = harness(c)
    Vbus = c["Vb"]
    for _ in range(30):
        I = P / Vbus; Vbus = c["Vb"] - I * (Rbatt + Rl)
    Vm = math.hypot(vd, vq); phi = math.atan2(-vd, vq)      # voltage leads current by phi
    M = Vm / (Vbus / 2)                                      # modulation index (phase peak / half bus)
    Iph = iq / math.sqrt(2)
    # Kolar & Round: RMS of the AC part of a 3-phase PWM inverter's DC-link current (sinusoidal currents, continuous SVPWM)
    Ic = Iph * math.sqrt(2 * M * (math.sqrt(3) / (4 * math.pi) + math.cos(phi) ** 2 * (math.sqrt(3) / math.pi - 9 * M / 16)))
    Iinv_rms = math.hypot(I, Ic)
    return dict(P=P, Ibat=I, Vbus=Vbus, vq=vq, vd=vd, Vm=Vm, phi=phi, M=M, Ic=Ic, Iinv_rms=Iinv_rms,
                Pcable=I ** 2 * Rl, Pbatt=I ** 2 * Rbatt, drop=I * (Rbatt + Rl))

def hotplug(c, bulk):
    """Series R-L-C step response: battery switched onto the (uncharged) ESC capacitors."""
    Rl, Ll, _ = harness(c)
    if not bulk:
        C, R, L = Ccer, Rbatt + Rl + ESRc, Ll + ESLc
    else:
        C, R, L = Ccer + Cbulk, Rbatt + Rl + ESRb, Ll + ESLb     # bulk ESR dominates the damping
    Z0 = math.sqrt(L / C); zeta = R / (2 * Z0); w0 = 1 / math.sqrt(L * C)
    if zeta < 1:
        os_ = math.exp(-math.pi * zeta / math.sqrt(1 - zeta ** 2))
        wd = w0 * math.sqrt(1 - zeta ** 2); a = zeta * w0
        tpk = math.atan(wd / a) / wd
        Ipk = c["Vb"] / (wd * L) * math.exp(-a * tpk) * math.sin(wd * tpk)
    else:
        os_, Ipk = 0.0, c["Vb"] / R                              # overdamped: bounded by V/R
    return dict(C=C, R=R, L=L, Z0=Z0, zeta=zeta, f0=w0 / (2 * math.pi), Vpk=c["Vb"] * (1 + os_), Ipk=Ipk, Q=Z0 / R)

def z_bus(c, f, bulk):
    """Impedance the ESC switching current sees: battery+harness path in parallel with the capacitors."""
    s = 2j * np.pi * f
    Rl, Ll, _ = harness(c)
    zb = Rbatt + Rl + s * Ll
    zc = ESRc + s * ESLc + 1 / (s * Ccer)
    y = 1 / zb + 1 / zc
    if bulk: y = y + 1 / (ESRb + s * ESLb + 1 / (s * Cbulk))
    return 1 / y

def ground_loop(Ibat):
    """DC current split when the three battery negatives are tied (1 mOhm each) AND the ESCs share a signal ground.
    Nodes: g1..g3 (ESC grounds), bn1..bn3 (battery negatives), tie, fc (flight controller ground = reference)."""
    Rneg = [harness(c)[0] / 2 for c in CH]; Rtie = 1e-3
    names = ["g1", "g2", "g3", "bn1", "bn2", "bn3", "tie"]; idx = {n: i for i, n in enumerate(names)}
    G = np.zeros((7, 7)); J = np.zeros(7)
    def r(a, b, R):
        g = 1 / R
        for p, q in ((a, b), (b, a)):
            if p != "fc": G[idx[p], idx[p]] += g
            if p != "fc" and q != "fc": G[idx[p], idx[q]] -= g
    for k in range(3):
        r(f"g{k+1}", f"bn{k+1}", Rneg[k]); r(f"g{k+1}", "fc", Rsig); r(f"bn{k+1}", "tie", Rtie)
        # each channel's load current enters its ESC ground and must leave its battery negative (battery is a floating source)
        J[idx[f"g{k+1}"]] += Ibat[k]; J[idx[f"bn{k+1}"]] -= Ibat[k]
    v = np.linalg.solve(G, J)
    Ineg = [(v[idx[f"g{k+1}"]] - v[idx[f"bn{k+1}"]]) / Rneg[k] for k in range(3)]
    Isig = [v[idx[f"g{k+1}"]] / Rsig for k in range(3)]
    return Ineg, Isig

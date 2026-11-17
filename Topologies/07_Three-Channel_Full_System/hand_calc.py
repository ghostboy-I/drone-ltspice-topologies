"""Hand calculations for topology 07 (shared by plot_results.py and make_design_doc.py).
Every number here is computed from the same parameters as the schematics, without running LTspice."""
import math
import numpy as np

# ---------------- parameters (identical to gen_schematic.py) ----------------
Rbatt = 20e-3
VB = [15.2, 15.0, 14.8]
RLOOP = [2.66e-3, 5.97e-3, 10.94e-3]
LLOOP = [47e-9, 140e-9, 770e-9]
Rcon = 50e-6                                    # connector modelled as a 50 uOhm switch (XT60 is already in Rloop)
Rsig, Rbgnd = 27e-3, 10.6e-3
RPM = [14000, 20000, 10000]; RPM3P = 16000
KV, Pp, Rph, Lph = 2300, 7, 50e-3, 7.5e-6
Ke = 60 / (2 * math.pi * KV); Kph = Ke / math.sqrt(3); Kt = 1.5 * Kph
Jrot, Kprop, Bfric = 5e-6, 1.15e-8, 1e-6
Fsw, Tdead, Vdrv, Rg_esc = 48e3, 100e-9, 10.0, 4.7
Imax, Vuvlo, Fvf = 30.0, 9.0, 3e3
Fcw = 30.0; Kpw = Jrot * 2 * math.pi * Fcw / Kt; Kiw = Kpw * 2 * math.pi * Fcw / 4
# ESC_FET (VDMOS): Rd 2.5m Rs 0.5m Vto 1.8 Kp 120, body diode Is 5p N 1.05 Rb 4m Tt 20n
ESC = dict(Rd=2.5e-3, Rs=0.5e-3, Vto=1.8, Kp=120, Is=5e-12, N=1.05, Rb=4e-3, Tt=20e-9, Qgd=6e-9, Qoss=10e-9)
# PROT_FET: Rd 0.4m Rs 0.2m Vto 2.5 Kp 300
PROT = dict(Rd=0.4e-3, Rs=0.2e-3, Vto=2.5, Kp=300, Cgs=6e-9)
Rgate, Cm, Cgsx, Rgs, Vz = 12e3, 100e-9, 2.2e-6, 100e3, 12.0
CCER, CBULK, CBEC_IN = 10e-6, 470e-6, 20e-6
CDC = [CCER + CBULK + CBEC_IN, CCER + CBULK, CCER + CBULK]
V5set, I5, Eta, Dmax, Rbo, Vbec_uv = 4.984, 3.0, 0.97, 0.95, 5e-3, 6.0
Rav = V5set / I5
TON = [0.5e-3, 1.5e-3, 2.5e-3]; TARM, TRAMP = 10e-3, 120e-3      # plug-in run
TPUNCH, TOFF = 8e-3, 16e-3                                        # flight run
Vt = 0.02585

ron_esc = ESC["Rd"] + ESC["Rs"] + 1 / (ESC["Kp"] * (Vdrv - ESC["Vto"]))
ron_prot = lambda vgs: PROT["Rd"] + PROT["Rs"] + 1 / (PROT["Kp"] * (vgs - PROT["Vto"]))


def load_torque(w): return Kprop * w * abs(w) + Bfric * w


def esc_loss(iq, vbus):
    """Inverter loss for a sinusoidal phase current of amplitude iq (A) on a bus vbus (V).
    Returns a dict of the parts. <|i|> over a period of a sine = 2/pi * amplitude."""
    iabs = 2 / math.pi * iq
    cond = 1.5 * iq ** 2 * ron_esc                                         # 3 phases x Irms^2 x Ron
    vf = ESC["N"] * Vt * math.log(max(iabs, 1e-3) / ESC["Is"]) + iabs * ESC["Rb"]
    dead = 3 * 2 * Tdead * Fsw * vf * iabs                                 # body diode during both dead times
    rr = 3 * vbus * ESC["Tt"] * iabs * Fsw                                 # reverse recovery: Qrr = Tt * I per hard turn-on
    vplat = ESC["Vto"] + math.sqrt(2 * max(iabs, 0.1) / ESC["Kp"])
    t_on, t_off = ESC["Qgd"] * Rg_esc / (Vdrv - vplat), ESC["Qgd"] * Rg_esc / vplat
    sw = 3 * 0.5 * vbus * iabs * (t_on + t_off) * Fsw                       # one hard turn-on + one hard turn-off per leg per period
    oss = 3 * ESC["Qoss"] * vbus * Fsw                                     # output charge dumped at each hard turn-on
    return dict(cond=cond, dead=dead, rr=rr, sw=sw, oss=oss, total=cond + dead + rr + sw + oss, t_on=t_on, t_off=t_off, vf=vf)


def bec():
    """Averaged BEC: 4.984 V source, 5 mOhm output R, 10.6 mOhm + lead, avionics R, 10.6 mOhm - lead (= Lsig1)."""
    iout = V5set / (Rbo + Rbgnd + Rav + Rbgnd)
    v5fc = iout * Rav
    v5esc = V5set - iout * Rbo
    pout_src = V5set * iout                                   # power the converter delivers at its switch node
    return dict(iout=iout, v5fc=v5fc, v5esc=v5esc, pav=v5fc * iout, pin=pout_src / Eta, pleads=iout ** 2 * (2 * Rbgnd + Rbo))


def solve_bus(k, pin, vgs=Vz):
    """Battery current and bus voltage for a constant power drawn at the ESC bus: V = Vb - I*Rtot, P = V*I."""
    Rp = 2 * ron_prot(vgs)
    Rtot = Rbatt + Rcon + RLOOP[k] + Rp
    I = (VB[k] - math.sqrt(VB[k] ** 2 - 4 * Rtot * pin)) / (2 * Rtot)
    return dict(I=I, Vbus=VB[k] - I * Rtot, Rtot=Rtot, Rp=Rp, Vbt=VB[k] - I * Rbatt, harn=I * RLOOP[k],
                Pprot=I ** 2 * Rp, Pharn=I ** 2 * RLOOP[k], Pint=I ** 2 * Rbatt, Pchem=VB[k] * I, Pterm=(VB[k] - I * Rbatt) * I)


def cap_loss(k, iq, vq, vd, vbus):
    """DC-link ripple (Kolar & Round, as in topology 04) and the I^2*ESR loss it causes in the link capacitors.
    At 48 kHz the ripple splits between the capacitors by their impedances."""
    Vm = math.hypot(vd, vq); phi = math.atan2(-vd, vq); M = Vm / (vbus / 2); Iph = iq / math.sqrt(2)
    Ic = Iph * math.sqrt(max(2 * M * (math.sqrt(3) / (4 * math.pi) + math.cos(phi) ** 2 * (math.sqrt(3) / math.pi - 9 * M / 16)), 0))
    w = 2 * math.pi * Fsw
    caps = [(2e-3, 0, CCER), (30e-3, 10e-9, CBULK)] + ([(3e-3, 0.5e-9, CBEC_IN)] if k == 0 else [])
    Z = [complex(r, w * l - 1 / (w * c)) for r, l, c in caps]
    Y = sum(1 / z for z in Z)
    P = sum(abs((1 / z) / Y * Ic) ** 2 * c[0] for z, c in zip(Z, caps))
    return Ic, P


def steady(k, rpm=None, vgs=Vz):
    w = (rpm or RPM[k]) * math.pi / 30
    T = load_torque(w); iq = T / Kt
    pm = T * w; pcu = 1.5 * Rph * iq ** 2
    vq = Rph * iq + Kph * w; vd = -Pp * w * Lph * iq
    vbus = VB[k]
    for _ in range(20):                                       # ESC loss depends weakly on Vbus: iterate
        el = esc_loss(iq, vbus)
        pinv = pm + pcu + el["total"]
        Ic, pcap = cap_loss(k, iq, vq, vd, vbus)
        pin = pinv + pcap + (bec()["pin"] if k == 0 else 0)
        b = solve_bus(k, pin, vgs); vbus = b["Vbus"]
    return dict(w=w, T=T, iq=iq, pm=pm, pcu=pcu, vq=vq, vd=vd, esc=el, pinv=pinv, Ic=Ic, pcap=pcap, pin=pin, **b)


def system():
    S = [steady(k) for k in range(3)]
    B = bec()
    pchem = sum(s["Pchem"] for s in S)
    puse = sum(s["pm"] for s in S) + B["pav"]
    return S, B, dict(pchem=pchem, puse=puse, eff=puse / pchem)


# ---------------- plug-in: Miller soft-start (topology 05) ----------------
def plugin(k, I_guess=5.0):
    Vb, C = VB[k], CDC[k]
    vplat = PROT["Vto"] + math.sqrt(2 * I_guess / PROT["Kp"])
    I_in = (Vb - vplat) * C / (Rgate * Cm)
    t_ramp = C * Vb / I_in
    kick = Vb * Cm / (Cm + PROT["Cgs"] + Cgsx)
    tau_g = Rgate * (Cm + Cgsx + PROT["Cgs"])
    t_d = tau_g * math.log((Vb - kick) / (Vb - vplat))
    # after the plateau, the gate charges from Vplat toward the Thevenin voltage of Rgate/Rgs, clamped by the zener
    Vth, Rth = Vb * Rgs / (Rgs + Rgate), Rgate * Rgs / (Rgs + Rgate)
    tau_on = Rth * (Cm + Cgsx + PROT["Cgs"])
    t_end = TON[k] + t_d + t_ramp
    vgs_at = lambda t: min(Vz, Vth - (Vth - vplat) * math.exp(-(t - t_end) / tau_on)) if t > t_end else vplat
    E = 0.5 * C * Vb ** 2
    # channel 1: the BEC starts during the ramp (UVLO 6 V, then a 0.3 ms RC soft-start). Its input current also flows
    # through Q2, which still drops Vb - Vbus. Step the linear voltage ramp in time and track the soft-start state.
    Ebec = Ibec = 0.0
    if k == 0:
        dt, ss, acc, n = 1e-7, 0.0, [], 0
        for t in np.arange(0, t_ramp, dt):
            v = I_in / C * t
            en = (1 + math.tanh(4 * (v - Vbec_uv))) / 2
            ss += (en - ss) * dt / 0.3e-3
            ib = ss * bec()["pin"] / max(v, 2)
            Ebec += ib * (Vb - v) * dt
            if 0.1 * Vb <= v <= 0.9 * Vb: acc.append(ib)
        Ibec = float(np.mean(acc))
    return dict(vplat=vplat, I_in=I_in, t_ramp=t_ramp, kick=kick, t_d=t_d, T10=TON[k] + t_d + 0.1 * t_ramp,
                T90=TON[k] + t_d + 0.9 * t_ramp, E=E, Ebec=Ebec, Ibec=Ibec, vgs_at=vgs_at, tau_on=tau_on, Vth=Vth)


# ---------------- spin-up after arming: linear model of the speed loop (PI + inertia, current loop ideal) ----------------
def spinup(k, t_end=20e-3, dt=1e-6):
    W = RPM[k] * math.pi / 30; alpha = W / TRAMP
    w = integ = 0.0; out = []
    for t in np.arange(TARM, t_end, dt):
        wref = alpha * (t - TARM)
        e = wref - w; integ += e * dt
        iq = max(-Imax, min(Imax, Kpw * e + Kiw * integ))
        w += (Kt * iq - load_torque(w)) / Jrot * dt
        out.append((t, wref, w, iq))
    a = np.array(out)
    return dict(t=a[:, 0], wref=a[:, 1], w=a[:, 2], iq=a[:, 3], alpha=alpha, iq_ff=Jrot * alpha / Kt)


def spin_power(k, w, iq, vbus):
    """Bus power while spinning up: Te*w + copper + ESC loss (ESC loss at low speed is mostly conduction + switching)."""
    return Kt * iq * w + 1.5 * Rph * iq ** 2 + esc_loss(abs(iq), vbus)["total"]


# ---------------- throttle punch on motor 3: current-limited acceleration ----------------
def punch(w0, t0, t1, dt=1e-6):
    w = w0
    for _ in np.arange(t0, t1, dt):
        w += (Kt * Imax - load_torque(w)) / Jrot * dt
    return w


# ---------------- pack 1 pulled: hold-up of ESC 1 bus with constant-power loads ----------------
def holdup():
    S, B, _ = system()
    C = CDC[0]; V0 = S[0]["Vbus"]
    P1 = S[0]["pinv"] + B["pin"]                         # ESC 1 + BEC
    t_uvlo = C * (V0 ** 2 - Vuvlo ** 2) / (2 * P1)       # 1/2 C (V0^2 - V^2) = P t
    lag = 1 / (2 * math.pi * Fvf)                         # the UVLO sees the bus through a 3 kHz filter: ~53 us late
    # the bus drops further during the lag (approximately at the same rate)
    v_at = math.sqrt(max(Vuvlo ** 2 - 2 * P1 * lag / C, 0))
    t_bec = C * (v_at ** 2 - Vbec_uv ** 2) / (2 * B["pin"])
    Vll = Ke * S[0]["w"]                                  # line-line peak back-EMF of motor 1 (diode-bridge source)
    return dict(V0=V0, P1=P1, t_uvlo=t_uvlo, lag=lag, v_at=v_at, t_bec=t_bec, t_rail=t_uvlo + lag + t_bec, Vll=Vll)


if __name__ == "__main__":
    S, B, T = system()
    for k, s in enumerate(S):
        print(f"ch{k+1}: w={s['w']:.0f} T={s['T']*1e3:.2f} mNm iq={s['iq']:.2f} Pm={s['pm']:.2f} Pcu={s['pcu']:.2f} "
              f"Pesc={s['esc']['total']:.2f} ({', '.join(f'{n}={s['esc'][n]:.3f}' for n in ('cond','dead','rr','sw','oss'))}) "
              f"Pinv={s['pinv']:.2f} I={s['I']:.3f} Vbus={s['Vbus']:.3f} harn={s['harn']*1e3:.1f}mV Pprot={s['Pprot']*1e3:.1f}mW")
    print("BEC", {k: round(v, 4) for k, v in B.items()}); print("system", T)
    for k in range(3):
        p = plugin(k); print(f"plug ch{k+1}: Iin={p['I_in']:.2f} td={p['t_d']*1e3:.2f}ms ramp={p['t_ramp']*1e3:.2f}ms T90={p['T90']*1e3:.2f}ms E={p['E']*1e3:.1f}mJ Ebec={p['Ebec']*1e3:.1f}mJ vgs(10ms)={p['vgs_at'](10e-3):.2f} vgs(20ms)={p['vgs_at'](20e-3):.2f}")
        sp = spinup(k); i = -1
        print(f"  spin: iq_ff={sp['iq_ff']:.2f} iq(15-20ms)={sp['iq'][sp['t']>=15e-3].mean():.2f} rpm(20ms)={sp['w'][-1]*30/math.pi:.0f}")
    w3 = RPM[2] * math.pi / 30
    print("punch: w(10ms)", punch(w3, 8e-3, 10e-3), "w(15ms)", punch(w3, 8e-3, 15e-3), "w(23ms)", punch(w3, 8e-3, 23e-3))
    print("holdup", holdup())

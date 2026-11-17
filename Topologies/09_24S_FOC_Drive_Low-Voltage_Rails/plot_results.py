"""Plots for topology 09 (python3 plot_results.py [drive] [rails] [ac] [qg]). Also writes extra_metrics.json
(numbers that need the waveforms, not just the .meas lines)."""
import sys, os, json, math
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from ltraw import read_raw, split_steps
import hand_calc as h

C = dict(a="#2a78d6", b="#e07b39", c="#3a9e5c", k="#222222", g="#8a8a8a", r="#c8443a", p="#7b5ab6")
plt.rcParams.update({"font.size": 8.5, "axes.grid": True, "grid.alpha": 0.3, "axes.spines.top": False, "axes.spines.right": False})
EXTRA = "extra_metrics.json"


def metrics(update):
    m = json.load(open(EXTRA)) if os.path.exists(EXTRA) else {}
    m.update(update); json.dump(m, open(EXTRA, "w"), indent=1)


def win(d, t0, t1):
    t = d["time"]; s = (t >= t0) & (t <= t1); return {k: v[s] for k, v in d.items()}


def drive():
    d = read_raw("Drive_24S.raw"); t = d["time"] * 1e3
    fig, ax = plt.subplots(3, 2, figsize=(10, 8.2)); ax = ax.ravel()
    z = win(d, 6.0e-3, 7.6e-3); tz = z["time"] * 1e3
    for ph, c in zip("abc", "abc"):
        ax[0].plot(tz, z[f"I(L{ph})"], color=C[c], lw=0.8, label=f"i{ph}")
    ax[0].set(title="Phase currents at hover (1824 RPM, 29.6 N m)", xlabel="ms", ylabel="A"); ax[0].legend(ncol=3, loc="upper right")
    ax[1].plot(t, d["V(iq)"], color=C["a"], lw=0.6, label="iq"); ax[1].plot(t, d["V(id)"], color=C["b"], lw=0.6, label="id")
    ax[1].plot(t, d["V(iqref)"], color=C["k"], lw=0.8, ls="--", label="iq*")
    ax[1].axhline(h.hover()["mp"]["iq"], color=C["g"], lw=0.7, ls=":"); ax[1].axhline(h.Imax, color=C["g"], lw=0.7, ls=":")
    ax[1].set(title="FOC: hover, punch at 8 ms (iq to its 210 A limit)", xlabel="ms", ylabel="A"); ax[1].legend(ncol=3, loc="center right")
    ax[2].plot(t, d["V(bus)"], color=C["a"], lw=0.5, label="ESC DC link")
    ax[2].plot(t, d["V(pdb)"], color=C["b"], lw=0.7, label="PDB (avionics tap)")
    ax[2].set(title="Bus: ESC DC link vs. PDB (harness L filters the ripple)", xlabel="ms", ylabel="V"); ax[2].legend(loc="upper right")
    ax[3].plot(t, d["I(Rpk)"], color=C["a"], lw=0.6, label="pack"); ax[3].plot(t, d["I(Lh)"], color=C["b"], lw=0.5, label="ESC harness")
    ax[3].set(title="Pack and ESC harness currents (avionics = 0.35 A)", xlabel="ms", ylabel="A"); ax[3].legend(loc="center right")
    zb = win(d, 6.20e-3, 6.30e-3); tb = zb["time"] * 1e3
    ax[4].plot(tb, zb["V(boota)"] - zb["V(pa)"], color=C["p"], lw=1.0, ls="--", label="Cboot voltage (boot - pa)")
    ax[4].plot(tb, zb["V(gha)"] - zb["V(pa)"], color=C["a"], lw=0.6, label="high-side Vgs")
    ax[4].plot(tb, zb["V(gla)"], color=C["b"], lw=0.6, label="low-side Vgs")
    ax[4].set(title="Bootstrap gate drive, leg A (two PWM periods)", xlabel="ms", ylabel="V", ylim=(-1, 13.5)); ax[4].legend(loc="center right", fontsize=7)
    zb2 = win(d, 6.20e-3, 6.30e-3)
    ax[5].plot(zb2["time"] * 1e3, zb2["V(pa)"], color=C["k"], lw=0.8, label="switch node pa")
    a2 = ax[5].twinx(); a2.plot(zb2["time"] * 1e3, zb2["I(Rboota)"] * 1e3, color=C["r"], lw=0.8, label="Dboot current (mA)")
    a2.set_ylabel("mA (clipped: the edge spikes are diode recovery)", color=C["r"]); a2.grid(False); a2.set_ylim(-50, 200)
    ax[5].set(title="Cboot recharges while the low side is on (pa near 0 V)", xlabel="ms", ylabel="V")
    ax[5].legend(loc="upper left", fontsize=7); a2.legend(loc="upper right", fontsize=7)
    fig.tight_layout(); fig.savefig("Drive_24S_results.png", dpi=150); plt.close(fig)

    # waveform metrics: bootstrap droop per high-side turn-on, ripple at the bus, gate charge from the rail
    hv = win(d, 4e-3, 8e-3); vboot = hv["V(boota)"] - hv["V(pa)"]
    ib = np.trapezoid(hv["I(Rboota)"], hv["time"]) / (hv["time"][-1] - hv["time"][0])
    i12 = np.trapezoid(hv["I(Raux)"], hv["time"]) / (hv["time"][-1] - hv["time"][0])
    tt, te = hv["time"], np.interp(np.linspace(4e-3, 8e-3, 400001), hv["time"], hv["V(te)"])
    # punch: iq 10-90 % rise time, iq averaged over one PWM period to remove the switching ripple
    tt = np.linspace(7.5e-3, 9.5e-3, 200001); y = np.interp(tt, d["time"], d["V(iq)"])
    n = int(round(1 / h.Fsw / (tt[1] - tt[0]))); ys = np.convolve(y, np.ones(n) / n, "same")
    iq0 = h.hover()["mp"]["iq"]; lv = lambda f: iq0 + f * (h.Imax - iq0)
    t10 = tt[np.argmax((tt > 8e-3) & (ys > lv(0.1)))]; t90 = tt[np.argmax((tt > 8e-3) & (ys > lv(0.9)))]
    metrics(dict(iq_rise_us=float((t90 - t10) * 1e6)))
    metrics(dict(drive=dict(iboot_a=float(ib), i12=float(i12), qg_eff_boot=float(ib / h.Fsw),
                            igate_total=float(i12 - (h.I_MCU + h.IQ_LDO + h.I_DRV_Q)),
                            vboot_mean=float(vboot.mean()), te_std=float(np.std(te)))))


def rails():
    d = read_raw("Rails_Switching.raw"); steps = split_steps(d)
    names = ["72 V (empty)", "88.8 V (nominal)", "100.8 V (full)"]     # LTspice sorts the .step list
    fig, ax = plt.subplots(4, 2, figsize=(10, 10.8)); ax = ax.ravel()
    s = steps[1]; t = s["time"] * 1e3
    for n, c, lab in (("V(v12e)", "p", "ESC 12 V (AUX12)"), ("V(v12a)", "a", "avionics 12 V (HV12)"), ("V(v5)", "b", "5 V (BEC5)"),
                      ("V(v33)", "c", "3.3 V sensors (LDO)"), ("V(v33e)", "k", "ESC 3.3 V (LDO)")):
        ax[0].plot(t, s[n], color=C[c], lw=0.7, label=lab)
    ax[0].set(title="Start-up at 88.8 V: 12 V rails soft-start, 5 V waits for 12 V power-good", xlabel="ms", ylabel="V", xlim=(0, 2.2))
    ax[0].legend(fontsize=7, loc="lower right")
    for st, nm, c in zip(steps, names, "abc"):
        z = win(st, 2.5e-3, 2.85e-3); ax[1].plot(z["time"] * 1e3, z["V(v12a)"], color=C[c], lw=0.7, label=nm)
    ax[1].set(title="Avionics 12 V: video TX switches on (0 -> 1.5 A) at 2.6 ms", xlabel="ms", ylabel="V"); ax[1].legend(fontsize=7)
    for st, nm, c in zip(steps, names, "abc"):
        z = win(st, 2.9e-3, 3.2e-3); ax[2].plot(z["time"] * 1e3, z["V(v5)"], color=C[c], lw=0.7, label=nm)
    ax[2].set(title="5 V: controller load step 0.8 -> 1.8 A at 3.0 ms", xlabel="ms", ylabel="V"); ax[2].legend(fontsize=7)
    z = win(s, 3.6e-3, 5.0e-3); tz = z["time"] * 1e3
    ax[3].plot(tz, z["V(bus)"], color=C["a"], lw=0.4, label="ESC DC link"); ax[3].plot(tz, z["V(pdb)"], color=C["b"], lw=0.7, label="PDB")
    ax[3].set(title="Throttle punch 3.8-4.6 ms: 74 -> 111 A", xlabel="ms", ylabel="V"); ax[3].legend(fontsize=7)
    tp = np.arange(3.6e-3, 5.0e-3, 10e-9); na = 100; dev = {}
    for nm, c, lab, off in (("V(v12e)", "p", "ESC 12 V", 12.0), ("V(v12a)", "a", "avionics 12 V", 12.0), ("V(v5)", "b", "5 V", 4.984)):
        ya_ = np.convolve(np.interp(tp, s["time"], s[nm]), np.ones(na) / na, "same")[na:-na]
        ax[4].plot(tp[na:-na] * 1e3, (ya_ - off) * 1e3, color=C[c], lw=0.7, label=lab)
        k = (tp[na:-na] > 3.8e-3) & (tp[na:-na] < 4.9e-3); dev[nm] = float(ya_[k].max() - ya_[k].min())
    ax[4].set(title="Rails during the punch (1 us average, minus set point)", xlabel="ms", ylabel="mV"); ax[4].legend(fontsize=7)
    # ESC 12 V rail: gate-charge pulses (6 per PWM period), raw and averaged over 1 us
    zz = win(s, 3.40e-3, 3.50e-3); tu = np.linspace(3.40e-3, 3.50e-3, 100001); y = np.interp(tu, zz["time"], zz["V(v12e)"])
    n = int(round(1e-6 / (tu[1] - tu[0]))); ya = np.convolve(y, np.ones(n) / n, "same")
    ax[5].plot(tu * 1e3, y, color=C["g"], lw=0.5, label="raw (ESL spikes at each pulse edge)")
    ax[5].plot(tu[n:-n] * 1e3, ya[n:-n], color=C["p"], lw=1.0, label="1 us average")
    ax[5].set(title="ESC 12 V: gate-charge pulses (120 kHz) vs. 250 kHz PWM", xlabel="ms", ylabel="V"); ax[5].legend(fontsize=7)
    zz = win(s, 3.50e-3, 3.52e-3)
    ax[6].plot(zz["time"] * 1e6, zz["V(hv12sw)"], color=C["a"], lw=0.7, label="HV12 switch node")
    ax[6].plot(zz["time"] * 1e6, zz["V(bec5sw)"] * 5, color=C["b"], lw=0.7, label="BEC5 switch node x5")
    ax[6].set(title="Switch nodes: 86.6 V -> 12 V at D = 0.14 (0.69 us on-time)", xlabel="us", ylabel="V"); ax[6].legend(fontsize=7)
    from ltraw import read_meas
    mm = read_meas("Rails_Switching.log"); x = np.arange(3)
    for i, (k, nm, c) in enumerate((("eff_aux", "AUX12 (0.12 A)", "p"), ("eff_hv", "HV12 (2.5 A)", "a"), ("eff_5", "BEC5 (2.3 A)", "b"))):
        ax[7].bar(x + (i - 1) * 0.27, np.array(mm[k]) * 100, 0.27, color=C[c], label=nm)
    ax[7].set(xticks=x, xticklabels=["72 V", "88.8 V", "100.8 V"], ylim=(85, 100), ylabel="%", title="Converter efficiency vs pack voltage (gate drive excluded)")
    ax[7].legend(fontsize=7, loc="lower left")
    fig.tight_layout(); fig.savefig("Rails_results.png", dpi=150); plt.close(fig)
    zz = win(s, 0.3e-3, 0.7e-3); lag = np.interp(8.0, zz["V(v12a)"], zz["time"]) - (10e-6 + 0.8e-3 * 8 / 12)
    metrics(dict(rails=dict(rip12e_avg=float(ya[n:-n].max() - ya[n:-n].min()), rip12e_raw=float(y.max() - y.min()), soft_lag_us=float(lag * 1e6), punch_pp_avg=dev)))


def ac_split():
    d = read_raw("Rails_AC.raw"); f = d["frequency"]; T = -d["V(out)"] / d["V(x)"]
    st = [0] + [i for i in range(1, len(f)) if f[i] < f[i - 1]] + [len(f)]
    return [(f[a:b], T[a:b]) for a, b in zip(st[:-1], st[1:])]


def ac():
    fig, ax = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
    res = {}
    for k, (f, T) in enumerate(ac_split()):
        b = h.BUCKS[k // 2]; full = k % 2 == 0; R = b.vout / (b.iout * (1 if full else 0.1))
        c = C["abc"[k // 2]]
        Th = b.loop(f, None, R)
        ax[0].semilogx(f, 20 * np.log10(np.abs(T)), color=c, lw=1.2 if full else 0.7, ls="-" if full else ":",
                       label=f"{b.name} {'full' if full else '10 %'} load")
        ax[1].semilogx(f, np.degrees(np.angle(T)), color=c, lw=1.2 if full else 0.7, ls="-" if full else ":")
        if full:
            ax[0].semilogx(f, 20 * np.log10(np.abs(Th)), color=c, lw=0.7, ls="--")
        i = int(np.argmax(np.abs(T) < 1)); fh, pmh = b.margins(Rload=R)
        res[f"{b.name}_{'full' if full else 'light'}"] = dict(fc=float(f[i]), pm=float(180 + np.degrees(np.angle(T[i]))), fc_hand=float(fh), pm_hand=float(pmh))
    ax[0].axhline(0, color=C["k"], lw=0.6); ax[0].set(ylabel="|T| (dB)", title="Loop gain of the three bucks: LTspice (solid / dotted), hand model (dashed)", ylim=(-60, 80))
    ax[0].legend(fontsize=7, ncol=3)
    ax[1].axhline(-180, color=C["k"], lw=0.6); ax[1].set(ylabel="phase (deg)", xlabel="Hz", ylim=(-270, 0))
    fig.tight_layout(); fig.savefig("Rails_loop_gain.png", dpi=150); plt.close(fig)
    metrics(dict(ac=res))


def qg():
    d = read_raw("GateCharge.raw"); t = d["time"]
    q = 10e-3 * t * 1e9
    fig, ax = plt.subplots(figsize=(10, 3.2))
    ax.plot(q, d["V(g)"], color=C["a"], lw=1.2, label="Vgs")
    a2 = ax.twinx(); a2.plot(q, d["V(d)"], color=C["b"], lw=1.0, label="Vds"); a2.set_ylabel("Vds (V)", color=C["b"]); a2.grid(False)
    ax.set(xlabel="gate charge (nC)", ylabel="Vgs (V)", title="Gate charge of one inverter switch (4 x 150 V FETs): 10 mA into the gate, 92 A clamped load at 88.8 V",
           xlim=(0, 330), ylim=(0, 13))
    ax.axhline(12, color=C["g"], ls=":", lw=0.8)
    fig.tight_layout(); fig.savefig("GateCharge.png", dpi=150); plt.close(fig)


if __name__ == "__main__":
    want = sys.argv[1:] or ["drive", "rails", "ac", "qg"]
    for w, fn in (("drive", drive), ("rails", rails), ("ac", ac), ("qg", qg)):
        if w in want: fn(); print("plotted", w)

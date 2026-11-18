"""Plots for topology 10 (python3 plot_results.py [avionics] [loop] [esc]); also writes extra_metrics.json."""
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


def K(d, name):
    return d[[k for k in d if k.lower() == name.lower()][0]]


def win(d, t0, t1):
    t = d["time"]; s = (t >= t0) & (t <= t1); return {k: v[s] for k, v in d.items()}


def avionics():
    d = read_raw("Avionics_Board.raw"); t = d["time"] * 1e3
    fig, ax = plt.subplots(3, 2, figsize=(10, 8.4)); ax = ax.ravel()
    for n, c, lab in (("V(+12V)", "a", "+12V (U1 LTC7801)"), ("V(+5V)", "b", "+5V (U2 LT8641)"), ("V(+3V3)", "c", "+3V3 (U3 LT3045)")):
        ax[0].plot(t, K(d, n), color=C[c], lw=0.8, label=lab)
    ax[0].plot(t, K(d, "V(PG12)"), color=C["g"], lw=0.6, ls="--", label="PG12 -> U2 enable")
    ax[0].set(title="Cold start: 12 V soft-start, then 5 V (on 12 V PGOOD), then 3.3 V", xlabel="ms", ylabel="V", xlim=(0, 5)); ax[0].legend(fontsize=7)
    z = win(d, 5.8e-3, 6.4e-3)
    ax[1].plot(z["time"] * 1e3, K(z, "V(+12V)"), color=C["a"], lw=0.7)
    ax[1].set(title="+12V: video TX switches on (0 -> 1.5 A) at 6.0 ms", xlabel="ms", ylabel="V")
    z = win(d, 6.3e-3, 6.8e-3)
    ax[2].plot(z["time"] * 1e3, K(z, "V(+5V)"), color=C["b"], lw=0.7)
    ax[2].set(title="+5V: controller load step 0.8 -> 1.8 A at 6.5 ms", xlabel="ms", ylabel="V")
    z = win(d, 6.8e-3, 8.0e-3)
    tt = np.arange(6.8e-3, 8.0e-3, 0.2e-6); n50 = 250                       # 50 us moving average: removes the 148 kHz pulses
    for k_, c, ls in zip((1, 2, 3), "abc", ("-", "-", "--")):
        y = np.convolve(np.interp(tt, d["time"], K(d, f"I(D{k_})")), np.ones(n50) / n50, "same")[n50:-n50]
        ax[3].plot(tt[n50:-n50] * 1e3, y * 1e3, color=C[c], lw=1.2, ls=ls, label=f"pack {k_} (D{k_}), 50 µs average")
    ax[3].set(title="Pack 1 pulled at 7.1 ms: packs 2 and 3 take over (diode-OR)", xlabel="ms", ylabel="mA"); ax[3].legend(fontsize=7)
    z = win(d, 6.90e-3, 6.92e-3)
    ax[4].plot(z["time"] * 1e6, K(z, "V(SW12)"), color=C["a"], lw=0.8, label="SW12 (148 kHz, D = 0.14)")
    ax[4].plot(z["time"] * 1e6, K(z, "V(SW5)") * 5, color=C["b"], lw=0.6, label="SW5 x5 (1 MHz)")
    ax[4].set(title="Switch nodes", xlabel="µs", ylabel="V"); ax[4].legend(fontsize=7)
    loop_panel(ax[5])
    fig.tight_layout(); fig.savefig("Avionics_results.png", dpi=150); plt.close(fig)


def loop_points():
    d = read_raw("Avionics_LoopTest.raw"); steps = split_steps(d); F = [3e3, 6e3, 12e3, 24e3]; out = []
    for f, s in zip(F, steps):
        t = s["time"]; tt = np.linspace(t[-1] - 8 / f, t[-1], 3200, endpoint=False)
        x = np.interp(tt, t, K(s, "V(+12V)")); y = np.interp(tt, t, K(s, "V(+12V_INJ)"))
        ph = np.exp(-2j * np.pi * f * tt); out.append((f, -np.mean(x * ph) / np.mean(y * ph)))
    return out


def loop_panel(ax):
    pts = loop_points(); f = np.logspace(3, 5, 400); T = h.U1.loop(f, 12 / 2.4)
    ax.semilogx(f, 20 * np.log10(np.abs(T)), color=C["a"], lw=1, label="hand |T| (with 1-period delay)")
    ax.semilogx([p[0] for p in pts], [20 * np.log10(abs(p[1])) for p in pts], "o", color=C["a"], ms=5, label="LTspice |T| (injection)")
    a2 = ax.twinx(); a2.semilogx(f, np.degrees(np.unwrap(np.angle(T))), color=C["r"], lw=1, ls="--")
    a2.semilogx([p[0] for p in pts], [np.degrees(np.angle(p[1])) for p in pts], "s", color=C["r"], ms=4)
    a2.set_ylabel("phase (deg)", color=C["r"]); a2.grid(False); a2.set_ylim(-260, -60)
    ax.axhline(0, color=C["k"], lw=0.6); ax.set(title="U1 loop gain at 2.4 A: hand vs. transient injection", xlabel="Hz", ylabel="dB")
    ax.legend(fontsize=7, loc="lower left")
    lf = np.log([p[0] for p in pts]); lg = np.log([abs(p[1]) for p in pts]); fc = float(np.exp(np.interp(0, -lg, lf)))
    pm = 180 + float(np.interp(np.log(fc), lf, [np.degrees(np.angle(p[1])) for p in pts]))
    fch, pmh = h.U1.margins(12 / 2.4)
    metrics(dict(loop=dict(fc=fc, pm=pm, fc_hand=float(fch), pm_hand=float(pmh),
                           points=[[float(p[0]), float(abs(p[1])), float(np.degrees(np.angle(p[1])))] for p in pts])))


def esc():
    d = read_raw("ESC_Board.raw"); t = d["time"] * 1e3
    fig, ax = plt.subplots(3, 2, figsize=(10, 8.4)); ax = ax.ravel()
    for n, c, lab in (("V(+12V)", "a", "+12V (U1 LTC7801 aux)"), ("V(+5V)", "b", "+5V (U2)"), ("V(+3V3)", "c", "+3V3 (U3)"),
                      ("V(FAULT_N)", "r", "FAULT_N (drivers ready)")):
        ax[0].plot(t, K(d, n), color=C[c], lw=0.8, label=lab)
    ax[0].set(title="Cold start of the ESC electronics, rotor already at hover", xlabel="ms", ylabel="V", xlim=(0, 3)); ax[0].legend(fontsize=7)
    ax[1].plot(t, K(d, "V(iq)"), color=C["a"], lw=0.5, label="iq (from the ACS772 ADC nets)")
    ax[1].plot(t, K(d, "V(id)"), color=C["b"], lw=0.5, label="id")
    ax[1].plot(t, K(d, "I(L_HARN)"), color=C["k"], lw=0.6, label="battery current")
    ax[1].set(title="Flying start at 1.5 ms, throttle punch at 7 ms", xlabel="ms", ylabel="A", ylim=(-50, 260)); ax[1].legend(fontsize=7)
    z = win(d, 5.0e-3, 6.6e-3); tz = z["time"] * 1e3
    ax[2].plot(tz, K(z, "I(La)"), color=C["a"], lw=0.8, label="true phase A current")
    ax[2].plot(tz, K(z, "V(ia)"), color=C["r"], lw=0.6, ls="--", label="MCU's reading (ACS772 -> 2/3 -> ADC)")
    ax[2].set(title="Current sensing chain", xlabel="ms", ylabel="A"); ax[2].legend(fontsize=7)
    z = win(d, 6.20e-3, 6.30e-3); tz = z["time"] * 1e3
    ax[3].plot(tz, K(z, "V(BST_A)") - K(z, "V(PH_A)"), color=C["p"], lw=1, ls="--", label="Cboot (BST_A - PH_A)")
    ax[3].plot(tz, K(z, "V(GAH)") - K(z, "V(PH_A)"), color=C["a"], lw=0.7, label="high-side Vgs")
    ax[3].plot(tz, K(z, "V(GAL)"), color=C["b"], lw=0.7, label="low-side Vgs")
    ax[3].set(title="Leg A: LTC7063 bootstrap drive", xlabel="ms", ylabel="V", ylim=(-1, 13.5)); ax[3].legend(fontsize=7, loc="center right")
    z = win(d, 6.2e-3, 6.4e-3)
    gl = K(z, "V(GAL)"); tz = z["time"]
    i = int(np.where(np.diff((gl > 3).astype(int)) == -1)[0][0]) + 1; t0 = tz[i]          # first low-side turn-off
    zz = win(d, t0 - 0.3e-6, t0 + 0.6e-6); tt = (zz["time"] - t0) * 1e9
    ax[4].plot(tt, K(zz, "V(GAL)"), color=C["b"], lw=1, label="low-side Vgs")
    ax[4].plot(tt, K(zz, "V(GAH)") - K(zz, "V(PH_A)"), color=C["a"], lw=1, label="high-side Vgs")
    ax[4].plot(tt, K(zz, "V(PH_A)") / 10, color=C["k"], lw=0.8, label="PH_A / 10")
    ax[4].axhline(3, color=C["g"], ls=":", lw=0.8)
    ax[4].set(title="Dead time (DT = 150 kΩ): both FETs off between edges", xlabel="ns", ylabel="V"); ax[4].legend(fontsize=7)
    z = win(d, 2.0e-3, 13e-3)
    ax[5].plot(z["time"] * 1e3, K(z, "V(VBUS)"), color=C["a"], lw=0.4, label="VBUS (DC link)")
    a2 = ax[5].twinx(); a2.plot(z["time"] * 1e3, K(z, "V(+12V)"), color=C["p"], lw=0.6, label="+12V aux"); a2.set_ylim(11, 13); a2.grid(False)
    a2.set_ylabel("+12V (V)", color=C["p"])
    ax[5].set(title="Bus sag on the punch; the aux 12 V does not notice", xlabel="ms", ylabel="V"); ax[5].legend(fontsize=7, loc="lower left")
    fig.tight_layout(); fig.savefig("ESC_results.png", dpi=150); plt.close(fig)
    # dead times at the 3 V threshold, median over the hover window
    w = win(d, 4e-3, 7e-3); tw = w["time"]; gh = K(w, "V(GAH)") - K(w, "V(PH_A)"); gl = K(w, "V(GAL)")
    def dt(a, b):
        idx = np.where(np.r_[False, np.diff((a > 3).astype(int)) == -1])[0][:40]
        return float(np.median([(tw[i + np.argmax(b[i:] > 3)] - tw[i]) * 1e9 for i in idx]))
    hv = win(d, 4e-3, 7e-3); th = hv["time"]; T = th[-1] - th[0]
    avg = lambda y: float(np.trapezoid(y, th) / T)
    the = K(hv, "V(the)"); ia, ib = K(hv, "I(La)"), K(hv, "I(Lb)"); ibe = (ia + 2 * ib) / np.sqrt(3)
    iq_t = -ia * np.sin(the) + ibe * np.cos(the); id_t = ia * np.cos(the) + ibe * np.sin(the)
    om = K(hv, "V(omega)"); E = 0.5 * h.h09.Jrot * om ** 2
    metrics(dict(esc=dict(dead_bg_tg=dt(gl, gh), dead_tg_bg=dt(gh, gl),
                          ia_err_rms=float(np.sqrt(np.mean((K(hv, "V(ia)") - ia) ** 2))),
                          iq_true=avg(iq_t), id_true=avg(id_t), omega_h=avg(om), omega0=float(om[0]), omega1=float(om[-1]),
                          p_kin=float((E[-1] - E[0]) / T), p_em=1.5 * h.h09.Kph * avg(om * iq_t))))


def surge():
    """Avionics_SurgeTest.asc: start-up of the LTC4366 and a 20 ms, 200 V surge on pack 1."""
    d = read_raw("Avionics_SurgeTest.raw"); t = np.abs(d["time"]) * 1e3
    su = h.surge()
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.4))
    for a, (t0, t1), title in ((ax[0], (0, 200), "Start-up: Q4's gate ramps, VIN_PROT follows"),
                               (ax[1], (245, 280), "Surge: pack 1 at 200 V behind 4 Ω for 20 ms")):
        m = (t >= t0) & (t <= t1)
        a.plot(t[m], K(d, "V(VIN_AV)")[m], color=C["r"], lw=1, label="VIN_AV (after diode-OR, at the TVS)")
        a.plot(t[m], K(d, "V(VIN_PROT)")[m], color=C["a"], lw=1.2, label="VIN_PROT (LTC7801 input)")
        a.axhline(150, color=C["k"], ls=":", lw=0.8); a.text(t0 + 1, 152, "LTC7801 VIN max 150 V", fontsize=7.5)
        a.axhline(su["vreg"], color=C["g"], ls="--", lw=0.8); a.text(t0 + 1, su["vreg"] - 9, f"VREG hand {su['vreg']:.1f} V", fontsize=7.5)
        a.set_xlabel("time (ms)"); a.set_ylabel("V"); a.set_title(title, fontsize=9, loc="left"); a.set_ylim(0, 195)
    ax[0].legend(fontsize=7.5, loc="lower right")
    fig.tight_layout(); fig.savefig("Avionics_surge.png", dpi=150); plt.close(fig)


if __name__ == "__main__":
    want = sys.argv[1:] or ["avionics", "esc", "surge"]
    if "avionics" in want: avionics(); print("plotted avionics")
    if "esc" in want: esc(); print("plotted esc")
    if "surge" in want: surge(); print("plotted surge")

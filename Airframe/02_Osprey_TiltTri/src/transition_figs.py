"""Figures from results/transition.json: conversion corridor, power vs speed, prop efficiency, transition time history."""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from tiltcfg import jload, RESULTS

LIMC = {"front rpm": "C3", "tail rpm": "C1", "pitch": "C4", "tail lift": "C5", "wing stall": "C0", "tail thrust < 0": "C6",
        "front rotor windmilling": "C8", "BEMT not converged": "0.5", "no trim": "k"}


def corridor(ax, r):
    pts = r["points"]; used = set()
    Vs = sorted({o["V"] for o in pts}); ds = sorted({o["delta"] for o in pts})
    for V in Vs:
        for d in ds:
            c = [o for o in pts if o["V"] == V and o["delta"] == d]
            if any(o["ok"] for o in c):
                ax.plot(V, d, "s", color="C2", ms=5)
            else:
                why = [l for o in c if o["solved"] for l in o["limits"]] or ["no trim"]
                lab = max(LIMC, key=lambda k: (why.count(k), -list(LIMC).index(k)))   # most frequent, ties by LIMC order
                used.add(lab)
                ax.plot(V, d, "x", color=LIMC.get(lab, "k"), ms=4)
    s = r["schedule"]; ax.plot(s["V"], s["delta"], "k-", lw=2, label="schedule (monotonic)")
    ax.plot([o["V"] for o in r["best"]], [o["delta"] for o in r["best"]], "k:", lw=1.2, label="min-power angle")
    for lab, col in LIMC.items():
        if lab in used: ax.plot([], [], "x", color=col, label=f"blocked: {lab}")
    ax.plot([], [], "s", color="C2", label="trims inside limits")
    ax.axvline(r["V_wing10"], color="0.6", ls=":", lw=1)
    ax.set_xlabel("airspeed V [m/s]"); ax.set_ylabel("nacelle angle [deg] (90 hover, 0 airplane)")
    ax.set_title(f"Conversion corridor, {r['mass_kg']:.0f} kg"); ax.set_ylim(-3, 93)
    return used


def main():
    J = jload(os.path.join(RESULTS, "transition.json"))
    cases = [J[k] for k in ("design", "current") if k in J]
    # 1 corridor
    fig, axs = plt.subplots(1, len(cases), figsize=(6.2 * len(cases), 5.6))
    used = set().union(*[corridor(ax, r) for ax, r in zip(np.atleast_1d(axs), cases)])
    h, l = np.atleast_1d(axs)[-1].get_legend_handles_labels()
    for lab in used - {l_[9:] for l_ in l if l_.startswith("blocked: ")}:
        h.append(plt.Line2D([], [], ls="", marker="x", color=LIMC[lab])); l.append(f"blocked: {lab}")
    fig.legend(h, l, loc="lower center", ncol=4, fontsize=7.5, frameon=False)
    fig.tight_layout(rect=(0, 0.12, 1, 1)); fig.savefig(os.path.join(RESULTS, "fig_corridor.png"), dpi=150); plt.close(fig)
    # 2 power vs speed and prop efficiency
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.6))
    for r, ls in zip(cases, ("-", "--")):
        m = f"{r['mass_kg']:.0f} kg"
        for L, lab, col in ((r["heli_mode"], "nacelles up (90)", "C3"), (r["airplane_mode"], "airplane (0)", "C0"), (r["best"], "best over angle", "k")):
            a1.plot([o["V"] for o in L], [o["P_batt"] / 1e3 for o in L], ls, color=col, label=f"{lab}, {m}")
        A = r["airplane_mode"]
        a2.plot([o["V"] for o in A], [o["eta_prop"] for o in A], ls, color="C0", label=f"BEMT, airplane, {m}")
        a2.plot([o["V"] for o in A], [2 / (1 + np.sqrt(1 + o["T_f"] / (0.5 * r["rho"] * o["V"] ** 2 * r["disk_area_m2"]))) for o in A], ls,
                color="0.6", label=f"ideal (momentum), {m}")
    a1.set_xlabel("V [m/s]"); a1.set_ylabel("battery power [kW]"); a1.set_title("Level-flight power"); a1.legend(fontsize=7); a1.grid(alpha=0.3)
    a2.set_xlabel("V [m/s]"); a2.set_ylabel("propulsive efficiency T V / P"); a2.set_title("Front props in airplane mode")
    a2.set_ylim(0, 1); a2.legend(fontsize=7); a2.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(RESULTS, "fig_power_speed.png"), dpi=150); plt.close(fig)
    # 3 transition time histories (design mass)
    r = cases[0]
    fig, axs = plt.subplots(2, 2, figsize=(12, 7.2), sharex="col")
    pr = r["paths"]["airplane"]
    for col, tr, ttl in ((0, pr[0], "Out: hover to cruise speed (then nacelles to 0)"), (1, pr[1], "Back: cruise to hover")):
        P = tr["points"]; t = np.array([o["t"] for o in P])
        if tr["a"] < 0: t = t[-1] - t                       # decelerating: time runs from cruise speed down
        a = axs[0, col]
        a.plot(t, [o["V"] for o in P], "k-", label="V [m/s]"); a.plot(t, [o["delta"] for o in P], "C0-", label="nacelle [deg]")
        a.plot(t, [o["theta"] for o in P], "C4-", label="pitch [deg]"); a.plot(t, [o["de"] for o in P], "C5:", label="elevator [deg]")
        a.set_title(f"{ttl}, a = {tr['a']:+.2f} m/s^2: {tr['time_s']:.0f} s, {tr['energy_wh']:.0f} Wh", fontsize=10); a.legend(fontsize=7); a.grid(alpha=0.3)
        a = axs[1, col]
        a.plot(t, [o["P_batt"] / 1e3 for o in P], "k-", label="battery power [kW]")
        a.plot(t, [o["L_wing"] / r["W_n"] * 10 for o in P], "C0-", label="wing lift / W x 10")
        a.plot(t, [o["rpm_f"] / 1e3 for o in P], "C3-", label="front rpm / 1000")
        a.plot(t, [o["rpm_t"] / 1e3 for o in P], "C1-", label="tail rpm / 1000")
        a.set_xlabel("t [s]"); a.legend(fontsize=7); a.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(RESULTS, "fig_transition.png"), dpi=150); plt.close(fig)


if __name__ == "__main__":
    main()

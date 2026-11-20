"""Figures from results/transition.json: conversion corridors, power vs speed, prop efficiency, transition histories."""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from tiltcfg import jload, RESULTS

LIMC = {"front rpm": "C3", "tail rpm": "C1", "motor torque": "C9", "pitch": "C4", "tail lift": "C5", "wing stall": "C0",
        "tail thrust < 0": "C6", "front rotor windmilling": "C8", "BEMT not converged": "0.5", "no trim": "k"}
CASES = (("design", "hex blade, 127 kg"), ("design_54x18", "54x18 tilting blades, 127 kg"), ("current", "hex blade, current mass"))


def corridor(ax, r, title):
    pts = r["points"]
    Vs = sorted({o["V"] for o in pts}); ds = sorted({o["delta"] for o in pts})
    used = set()
    for V in Vs:
        for d in ds:
            c = [o for o in pts if o["V"] == V and o["delta"] == d]
            if any(o["ok"] for o in c):
                ax.plot(V, d, "s", color="C2", ms=4)
            else:
                why = [l for o in c if o["solved"] for l in o["limits"]] or ["no trim"]
                lab = max(set(why), key=why.count); used.add(lab)
                ax.plot(V, d, "x", color=LIMC.get(lab, "k"), ms=4)
    ax.plot([o["V"] for o in r["best"]], [o["delta"] for o in r["best"]], "k-", lw=1.6, label="min-power angle")
    for lab in [l for l in LIMC if l in used]:
        ax.plot([], [], "x", color=LIMC[lab], label=f"blocked: {lab}")
    ax.plot([], [], "s", color="C2", label="trims inside limits")
    ax.set_xlabel("airspeed V [m/s]"); ax.set_ylabel("nacelle angle [deg] (90 hover, 0 airplane)")
    ax.set_title(title, fontsize=10); ax.set_ylim(-5, 95); ax.legend(fontsize=6.5, loc="lower left")


def main():
    J = jload(os.path.join(RESULTS, "transition.json"))
    cases = [(J[k], t) for k, t in CASES if k in J]
    fig, axs = plt.subplots(1, len(cases), figsize=(5.4 * len(cases), 4.8))
    for ax, (r, t) in zip(np.atleast_1d(axs), cases): corridor(ax, r, t)
    fig.tight_layout(); fig.savefig(os.path.join(RESULTS, "fig_corridor.png"), dpi=150); plt.close(fig)

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.6))
    for (r, t), col in zip(cases, ("C3", "C0", "C7")):
        a1.plot([o["V"] for o in r["best"]], [o["P_batt"] / 1e3 for o in r["best"]], "-", color=col, lw=2, label=f"best angle, {t}")
        a1.plot([o["V"] for o in r["heli_mode"]], [o["P_batt"] / 1e3 for o in r["heli_mode"]], ":", color=col, lw=1.2, label=f"nacelles up, {t}")
        if r["airplane_mode"]:
            a1.plot([o["V"] for o in r["airplane_mode"]], [o["P_batt"] / 1e3 for o in r["airplane_mode"]], "--", color=col, lw=1.2, label=f"airplane mode, {t}")
        B = [o for o in r["best"] if o["V"] > 0]
        a2.plot([o["V"] for o in B], [o["P_batt"] / o["V"] / 3.6 for o in B], "-", color=col, lw=2, label=t)
    a1.set_xlabel("V [m/s]"); a1.set_ylabel("battery power [kW]"); a1.set_title("Level-flight power"); a1.legend(fontsize=6.5); a1.grid(alpha=0.3)
    a2.set_xlabel("V [m/s]"); a2.set_ylabel("Wh/km"); a2.set_ylim(0, 300); a2.set_title("Energy per km at the best nacelle angle")
    a2.legend(fontsize=7); a2.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(RESULTS, "fig_power_speed.png"), dpi=150); plt.close(fig)

    fig, axs = plt.subplots(2, 2, figsize=(12, 7.2), sharex="col")
    for col, (key, kind, ttl) in enumerate((("design", "partial", "Hex blade: hover to partial-conversion cruise"),
                                            ("design_54x18", "airplane", "54x18 tilting blades: hover to 22 m/s (then nacelles to 0 at constant speed)"))):
        r = J.get(key)
        if not r or kind not in r.get("paths", {}): continue
        tr = r["paths"][kind][0]
        P = tr["points"]; t = np.array([o["t"] for o in P])
        a = axs[0, col]
        a.plot(t, [o["V"] for o in P], "k-", label="V [m/s]"); a.plot(t, [o["delta"] for o in P], "C0-", label="nacelle [deg]")
        a.plot(t, [o["theta"] for o in P], "C4-", label="pitch [deg]"); a.plot(t, [o["de"] for o in P], "C5:", label="elevator [deg]")
        a.set_title(f"{ttl}\na = {tr['a']:+.2f} m/s^2: {tr['time_s']:.0f} s, {tr['energy_wh']:.0f} Wh", fontsize=9); a.legend(fontsize=7); a.grid(alpha=0.3)
        a = axs[1, col]
        a.plot(t, [o["P_batt"] / 1e3 for o in P], "k-", label="battery power [kW]")
        a.plot(t, [o["L_wing"] / r["W_n"] * 10 for o in P], "C0-", label="wing lift / W x 10")
        a.plot(t, [o["rpm_f"] / 1e3 for o in P], "C3-", label="tilting rpm / 1000")
        a.plot(t, [o["rpm_t"] / 1e3 for o in P], "C1-", label="aft rpm / 1000")
        a.set_xlabel("t [s]"); a.legend(fontsize=7); a.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(RESULTS, "fig_transition.png"), dpi=150); plt.close(fig)


if __name__ == "__main__":
    main()

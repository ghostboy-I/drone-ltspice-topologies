#!/usr/bin/env python3
"""Topology 02 experiment: how does the PWM switching frequency change ESC efficiency, FET loss and torque ripple?

Sweeps Fsw x Sync (diode freewheel vs complementary PWM) with tools/sweep.py, running several LTspice copies at once,
then compares the results with two hand calculations:

  1. PWM current ripple. During one PWM period the two conducting phases (2*Lph in series) see Vbus for D*Tsw and
     ~0 V (freewheel) for (1-D)*Tsw. Volt-second balance gives the peak-to-peak ripple
         dI = Vbus * D * (1 - D) / (2 * Lph * Fsw)          -> falls as 1/Fsw
     and since Te = Ke * I in 6-step drive (two phases at Ke/2 each), the PWM part of the torque ripple is Ke * dI.
     The measured Te_ripple also contains the commutation dips (~16 mN*m, set by commutation, not by Fsw), so the
     prediction is  Te_pp ~ Ke*dI + 16 mN*m.
  2. Ripple copper loss. A triangle ripple of p-p dI adds dI^2/12 to the squared RMS current, in the two conducting
     phases (2*Rph):  P_cu_ripple = 2 * Rph * dI^2 / 12   -> falls as 1/Fsw^2. This, not FET loss, sets the trend here.
  3. Switching loss grows linearly with Fsw:  P_sw ~ (E_on + E_off) * Fsw  per switching FET. We fit the line
     P_fet_hi(Fsw) = P_cond + k * Fsw  to the simulated points and report k (energy per PWM period, in uJ).

Usage (from the Topologies folder or this folder):
    python3 sweep_fsw.py                       # default grid, default number of parallel jobs
    python3 sweep_fsw.py --jobs 6 --fsw 16k,32k,64k
    python3 sweep_fsw.py --plot-only           # re-plot from sweeps/fsw_sync/results.csv
"""
import argparse, csv, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
from sweep import run_sweep, default_jobs

ASC = os.path.join(HERE, "ThreePhase_ESC_BLDC.asc")
NAME = "fsw_sync"
OUT = os.path.join(HERE, "sweeps", NAME)
# values copied from the schematic's .param lines
VBATT, LPH, RPH, DUTY, KV = 15.2, 7.5e-6, 50e-3, 0.5, 2300
KE = 60 / (2 * np.pi * KV)
TE_COMM = 16e-3   # commutation-dip torque ripple from the README (does not depend on Fsw)


def si(s):
    """'48k' -> 48000.0 (LTspice suffixes)."""
    mult = {"f": 1e-15, "p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3, "k": 1e3, "meg": 1e6, "g": 1e9}
    s = str(s).strip().lower()
    for suf in sorted(mult, key=len, reverse=True):
        if s.endswith(suf):
            return float(s[: -len(suf)]) * mult[suf]
    return float(s)


def load():
    rows = list(csv.DictReader(open(os.path.join(OUT, "results.csv"))))
    rows = [r for r in rows if r.get("efficiency")]
    for r in rows:
        r["fsw"] = si(r["Fsw"])
        r["sync"] = int(r["Sync"])
        for k in list(r):
            try:
                r[k] = float(r[k]) if k not in ("Fsw", "Sync", "status") else r[k]
            except (TypeError, ValueError):
                pass
    return sorted(rows, key=lambda r: (r["sync"], r["fsw"]))


def report(rows):
    print("\n Sync   Fsw    RPM     Eff%   P_hi W  P_lo W  Te_pp mN*m  hand Te_pp  ripple err")
    for r in rows:
        dI = VBATT * DUTY * (1 - DUTY) / (2 * LPH * r["fsw"])
        hand = KE * dI + TE_COMM
        r["te_hand"] = hand
        print("  %d  %5.0fk  %6.0f  %5.1f  %6.2f  %6.2f   %7.1f    %7.1f    %+5.0f %%" % (
            r["sync"], r["fsw"] / 1e3, r["rpm_final"], 100 * r["efficiency"], r["pfet_hi"], r["pfet_lo"],
            1e3 * r["te_ripple"], 1e3 * hand, 100 * (r["te_ripple"] / hand - 1)))
    for s in (0, 1):
        pts = [r for r in rows if r["sync"] == s]
        if len(pts) >= 2:
            k, p0 = np.polyfit([r["fsw"] for r in pts], [r["pfet_hi"] for r in pts], 1)
            print("Sync=%d: high-side FET loss = %.2f W + %.2f uJ x Fsw   (fit to %d points)" % (s, p0, k * 1e6, len(pts)))
            lo, hi = pts[0], pts[-1]
            rip = lambda f: 2 * RPH * (VBATT * DUTY * (1 - DUTY) / (2 * LPH * f)) ** 2 / 12
            print("Sync=%d: copper loss %.0fk -> %.0fk falls %.2f W in LTspice; ripple hand calc 2*Rph*dI^2/12 predicts %.2f W"
                  % (s, lo["fsw"] / 1e3, hi["fsw"] / 1e3, lo["pcu"] - hi["pcu"], rip(lo["fsw"]) - rip(hi["fsw"])))


def plot(rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(2, 2, figsize=(11, 7.5))
    style = {0: dict(color="#c0504d", marker="o", label="Sync=0 (diode freewheel)"),
             1: dict(color="#1f6fb2", marker="s", label="Sync=1 (complementary)")}
    for s in (0, 1):
        pts = [r for r in rows if r["sync"] == s]
        if not pts:
            continue
        f = np.array([r["fsw"] for r in pts]) / 1e3
        ax[0, 0].plot(f, [100 * r["efficiency"] for r in pts], **style[s])
        ax[0, 1].plot(f, [r["pfet_hi"] for r in pts], ls="-", **style[s])
        ax[0, 1].plot(f, [r["pfet_lo"] for r in pts], ls="--", color=style[s]["color"], marker=style[s]["marker"],
                      mfc="none")
        ax[1, 0].plot(f, [1e3 * r["te_ripple"] for r in pts], **style[s])
        ax[1, 1].plot(f, [r["rpm_final"] for r in pts], **style[s])
    fs = np.linspace(min(r["fsw"] for r in rows), max(r["fsw"] for r in rows), 200)
    ax[1, 0].plot(fs / 1e3, 1e3 * (KE * VBATT * DUTY * (1 - DUTY) / (2 * LPH * fs) + TE_COMM), "k:",
                  label="hand: Ke·Vbus·D(1-D)/(2·Lph·Fsw) + 16 mN·m")
    ax[0, 0].set_ylabel("efficiency  Pmech/Pin  [%]")
    ax[0, 1].set_ylabel("FET loss [W]")
    ax[0, 1].set_title("solid: high-side FETs   dashed: low-side FETs", fontsize=9)
    ax[1, 0].set_ylabel("torque ripple p-p [mN·m]")
    ax[1, 1].set_ylabel("speed [RPM]")
    for a in ax.flat:
        a.set_xlabel("PWM frequency Fsw [kHz]")
        a.grid(alpha=0.3)
        a.legend(fontsize=8)
    fig.suptitle("Topology 02 ESC: PWM frequency sweep (Duty=%.1f, Vbatt=%.1f V)" % (DUTY, VBATT))
    fig.tight_layout()
    path = os.path.join(OUT, "fsw_sweep.png")
    fig.savefig(path, dpi=130)
    print("plot ->", path)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fsw", default="16k,24k,32k,48k,64k,96k")
    ap.add_argument("--sync", default="0,1")
    ap.add_argument("--jobs", type=int, default=None, help="parallel LTspice runs (default %d)" % default_jobs())
    ap.add_argument("--plot-only", action="store_true")
    a = ap.parse_args()
    if not a.plot_only:
        run_sweep(ASC, {"Fsw": a.fsw.split(","), "Sync": a.sync.split(",")}, jobs=a.jobs, name=NAME)
    rows = load()
    report(rows)
    plot(rows)

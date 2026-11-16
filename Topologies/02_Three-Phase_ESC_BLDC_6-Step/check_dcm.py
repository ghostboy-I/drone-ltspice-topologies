#!/usr/bin/env python3
"""Topology 02: is the Sync=0 speed rise at low Fsw caused by discontinuous conduction (DCM)? Check it on the waveforms.

Re-runs three cases with their .raw files kept (sweeps/dcm_F*_S*/, ~0.85 GB each; results in sweeps/dcm_check/):  16 kHz Sync=0 (suspect), 48 kHz Sync=0 (reference),
16 kHz Sync=1 (complementary PWM, which cannot go discontinuous because the low FET lets current reverse).

The test, inside the 120-degree interval where phase A is the PWM-chopped (high) phase:
  * PWM off-time, CCM: the phase current freewheels through A's low-side body diode, so V(pa) ~ -0.8 V and I(La) > 0.
  * PWM off-time, DCM: I(La) reaches 0, the diode turns off, and V(pa) floats up to the motor's back-EMF.
    The motor then sees a higher average line voltage than D*Vbus, so it spins faster.
Hand calc for the DCM boundary: the current reaches zero when the ripple half-amplitude exceeds the average:
    dI/2 >= I_avg,   dI = Vbus*D*(1-D)/(2*Lph*Fsw)   ->   Fsw_boundary = Vbus*D*(1-D)/(4*Lph*I_avg)
with I_avg the phase current while conducting (taken from the LTspice run).

    python3 check_dcm.py              # runs the 3 cases in parallel (~6 min), then analyses
    python3 check_dcm.py --analyse    # analyse existing .raw files only
"""
import argparse, glob, json, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
from sweep import run_sweep
from ltraw import read_raw

ASC = os.path.join(HERE, "ThreePhase_ESC_BLDC.asc")
OUT = os.path.join(HERE, "sweeps", "dcm_check")
VBATT, LPH, DUTY, TDEAD = 15.2, 7.5e-6, 0.5, 100e-9
CASES = [("16k", "0"), ("48k", "0"), ("16k", "1")]
T0, T1 = 0.280, 0.300   # steady-state window, same as the .meas lines


def run():
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(3) as pool:
        list(pool.map(lambda c: run_sweep(ASC, {"Fsw": [c[0]], "Sync": [c[1]]}, name="dcm_F%s_S%s" % c,
                                          keep_raw=True, jobs=1), CASES))


def analyse(fsw_s, sync):
    path = glob.glob(os.path.join(HERE, "sweeps", "dcm_F%s_S%s" % (fsw_s, sync), "case_001", "*.raw"))
    path = [p for p in path if not p.endswith((".op.raw", ".log.raw"))][0]
    d = read_raw(path)
    t = d["time"]
    m = (t >= T0) & (t <= T1)
    t, ia, va, the, tri, duty = (d[k][m] for k in ("time", "I(La)", "V(pa)", "V(the)", "V(tri)", "V(duty)"))
    vbus = d["V(bus)"][m]
    w = np.gradient(t)                                    # time weights: LTspice time steps are not uniform
    fsw = 1e3 * float(fsw_s[:-1])
    db = TDEAD * fsw
    a_high = np.sin(the) > 0.5                             # phase A is the chopped phase (Hall logic in the schematic)
    pwm_on = (duty - db) > tri
    off = a_high & ~pwm_on
    sgn = np.sign(np.average(ia[a_high], weights=w[a_high]))   # orient I(La) so conduction current is positive
    i = sgn * ia
    zero = off & (np.abs(i) < 0.2)
    neg = a_high & (i < -0.2)
    i_avg = np.average(i[a_high], weights=w[a_high])
    dI = VBATT * DUTY * (1 - DUTY) / (2 * LPH * fsw)
    r = dict(case="%s Sync=%s" % (fsw_s, sync), fsw=fsw, sync=int(sync),
             i_avg=i_avg, dI_hand=dI, fsw_boundary=VBATT * DUTY * (1 - DUTY) / (4 * LPH * i_avg),
             frac_off_zero=np.sum(w[zero]) / np.sum(w[off]),         # share of the PWM off-time with I ~ 0
             frac_neg=np.sum(w[neg]) / np.sum(w[a_high]),            # share of the A-high interval with I < 0
             va_off=np.average(va[off], weights=w[off]),             # mean V(pa) during off-time
             va_high=np.average(va[a_high], weights=w[a_high]),      # mean applied phase voltage while A is high
             vbus=np.average(vbus, weights=w))
    r["v_ccm_hand"] = DUTY * r["vbus"] - (1 - DUTY) * (0.8 if sync == "0" else 0.0)
    # waveform snippet: up to 4 PWM periods centred on the middle of a complete A-high interval near the end,
    # clipped to that interval (at 16 kHz the interval, 120 electrical degrees, is only ~3 PWM periods long; outside it
    # phase A is floating or is the low phase, and its ringing there is not DCM)
    k = np.where(a_high & (np.sin(the) > 0.995) & (t < T1 - 0.5e-3))[0][-1]
    lo = k - np.argmin(a_high[k::-1])          # first index of this A-high run
    hi = k + np.argmin(a_high[k:])             # one past its last index
    tc = t[k]
    s = (t > max(tc - 2 / fsw, t[lo])) & (t < min(tc + 2 / fsw, t[hi - 1]))
    r["wave"] = dict(t=(t[s] - tc) * 1e6, i=i[s], v=va[s], on=pwm_on[s])
    return r


def plot(rs):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(len(rs), 1, figsize=(10, 2.6 * len(rs)), sharex=False)
    for a, r in zip(ax, rs):
        wv = r["wave"]
        a.fill_between(wv["t"], -2, 0, where=~wv["on"], step="mid", color="0.88", label="PWM off-time")
        a.plot(wv["t"], wv["i"], color="#1f6fb2", lw=1.3, label="I(La)  [A]")
        a.axhline(0, color="k", lw=0.6)
        a.set_ylabel("I(La) [A]", color="#1f6fb2")
        a.set_ylim(min(-2, wv["i"].min() - 1), wv["i"].max() + 1)
        b = a.twinx()
        b.plot(wv["t"], wv["v"], color="#c0504d", lw=1.0, label="V(pa)  [V]")
        b.set_ylabel("V(pa) [V]", color="#c0504d")
        b.set_ylim(-3, 18)
        a.set_title("%s:  I=0 for %.0f %% of PWM off-time,  mean V(pa) while chopped = %.2f V  (CCM hand calc %.2f V)"
                    % (r["case"], 100 * r["frac_off_zero"], r["va_high"], r["v_ccm_hand"]), fontsize=9.5)
        a.set_xlabel("time from middle of a phase-A-high interval [µs]")
        a.grid(alpha=0.3)
    h1, l1 = ax[0].get_legend_handles_labels()
    ax[0].legend(h1 + [plt.Line2D([], [], color="#c0504d")], l1 + ["V(pa)  [V]"], fontsize=8, loc="upper right")
    fig.suptitle("Topology 02: phase-A current and voltage while A is the chopped phase (Duty=0.5)")
    fig.tight_layout()
    p = os.path.join(OUT, "dcm_check.png")
    fig.savefig(p, dpi=130)
    print("plot ->", p)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--analyse", action="store_true")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    if not a.analyse:
        run()
    rs = [analyse(*c) for c in CASES]
    print("\n case           I_avg A  dI_hand A  Fsw_boundary  I=0 in off-time  I<0 share  V(pa) off  V(pa) chopped  CCM hand")
    for r in rs:
        print(" %-13s  %6.2f   %7.2f    %7.1f kHz     %5.1f %%        %5.1f %%    %6.2f V   %6.2f V       %6.2f V" % (
            r["case"], r["i_avg"], r["dI_hand"], r["fsw_boundary"] / 1e3, 100 * r["frac_off_zero"], 100 * r["frac_neg"],
            r["va_off"], r["va_high"], r["v_ccm_hand"]))
    json.dump([{k: v for k, v in r.items() if k != "wave"} for r in rs], open(os.path.join(OUT, "dcm_check.json"), "w"),
              indent=1)
    plot(rs)

"""Exploration 27: tonal hover noise of the tri and hex with their best blades (Gutin steady-loading noise, A-weighted).

Queue item 10: does a noise requirement move the tri vs hex ranking? Both layouts carry the same weight. The tri has 3
rotors at twice the thrust and torque each, and spins faster in hover (2135 rpm) than the hex (1973 rpm). The hex has
twice as many sources.

Model: Gutin's far-field steady-loading noise (compact chord, distributed along the span from the BEMT dT/dr, dQ/dr).
The m-th harmonic of the blade-passing frequency f_m = m B Omega / 2 pi has rms pressure
    p_m = m B Omega / (2 sqrt(2) pi a S) * | int [ -cos(theta) dT/dr + a / (Omega r^2) dQ/dr ] J_mB(m B Omega r sin(theta) / a) dr |
theta from the thrust axis (theta = 180 deg: straight below a hovering rotor), S the distance. n rotors at slightly
different rpm add incoherently (+10 log10 n). Harmonics 1-20 are summed into OASPL and A-weighted (IEC 61672 curve).
Points: hover (W / n per rotor) and full thrust (T/W 2, take-off / gust). Observer distance 50 m.
Variants: each layout at the entry-15 tip-Mach caps (the cap changes the rotor speed at T/W 2 only through the blade
design; here we keep the best blades and report the tip Mach each point actually runs at).

What Gutin leaves out: thickness noise (small below tip Mach 0.5), broadband (turbulence and trailing-edge noise), and
unsteady loading (blade-wake interaction, arms in the downwash). For large, slow rotors those often dominate the
A-weighted level, so the absolute dBA here are a lower bound; the layout comparison of the tonal part is the result.

Hand checks: (1) Gutin's concentrated form at the effective radius 0.8 R for the first harmonic at theta = 120 deg;
(2) the scaling p_1 ~ T * mB M_e sin(theta) / ... for small Bessel arguments, J_B(x) ~ (x/2)^B / B!, so the first
harmonic of a 2-blade rotor grows as M_e^2 at fixed thrust: 40 log10 (M ratio) dB.
"""
import json, math, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from scipy.special import jv
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import bemt
import e01_coax_blade as e01
import e02_coax_two_point as e02
import e24_chain_best_blades as e24
from common import RESULTS, save_json

OUT = os.path.join(RESULTS, "explore")
S_OBS = 50.0
P_REF = 2e-5
HARM = 20
THETAS = np.radians(np.arange(5.0, 180.0, 2.5))


def a_weight(f):
    f2 = f * f
    ra = 12194 ** 2 * f2 * f2 / ((f2 + 20.6 ** 2) * math.sqrt((f2 + 107.7 ** 2) * (f2 + 737.9 ** 2)) * (f2 + 12194 ** 2))
    return 20 * math.log10(ra) + 2.00


def gutin(h, B, a, theta, S=S_OBS, harm=HARM):
    om = h["omega"]; r, dr = h["r"], h["dr"]; dT, dQ = h["dT_dr"] * dr, h["dQ_dr"] * dr; out = []
    for m in range(1, harm + 1):
        k = m * B * om / a
        integ = np.sum((-math.cos(theta) * dT + a / (om * r * r) * dQ) * jv(m * B, k * r * math.sin(theta)))
        p = m * B * om / (2 * math.sqrt(2) * math.pi * a * S) * abs(integ)
        out.append((m * B * om / (2 * math.pi), p))
    return out


def spl(p): return 20 * math.log10(max(p, 1e-30) / P_REF)


def levels(h, B, a, n, theta):
    hs = gutin(h, B, a, theta); tot = sum(p * p for _, p in hs) * n; tota = sum((p * p) * 10 ** (a_weight(f) / 10) for f, p in hs) * n
    return {"oaspl": 10 * math.log10(tot / P_REF ** 2) if tot > 0 else -99, "dba": 10 * math.log10(tota / P_REF ** 2) if tota > 0 else -99,
            "harmonics": [{"f": f, "spl_n": spl(p) + 10 * math.log10(n), "dba_n": spl(p) + 10 * math.log10(n) + a_weight(f)} for f, p in hs[:6]]}


def run():
    t0 = time.time(); e01.init(); G = e01.G; p, hot = G["p"], G["hot"]; W = G["ph1"]["vehicle"]["weight_n"]; a = hot["a"]
    Rr = p["rotor"]["diameter_in"] * p["constants"]["inch_to_m"] / 2; tw = p["vehicle"]["tw_target"]
    out = {"observer_m": S_OBS, "cases": {}}
    for c, n in (("tri", 3), ("hex0", 6)):
        db = e24.db_for(c, "best"); bd = e24.blade_for(c, "best")
        b = e02.blade_from(bd, Rr, p["rotor"]["hub_radius_m"])
        for pt, T in (("hover", W / n), ("T/W 2", tw * W / n)):
            h = bemt.hover_at_thrust(b, db, hot, T)
            dirn = [levels(h, b.N, a, n, th) for th in THETAS]
            i = int(np.argmax([d["dba"] for d in dirn])); j = int(np.argmin(abs(np.degrees(THETAS) - 120)))
            Re = float(np.sum(h["r"] * h["dT_dr"] * h["dr"]) / h["T"])
            out["cases"][f"{c}|{pt}"] = {"n": n, "B": b.N, "rpm": h["rpm"], "T": h["T"], "Q": h["Q"], "tip_mach": h["tip_mach"], "R_thrust_centroid_over_R": Re / Rr,
                                         "bpf_hz": b.N * h["rpm"] / 60, "theta_deg": np.degrees(THETAS).tolist(), "oaspl": [d["oaspl"] for d in dirn],
                                         "dba": [d["dba"] for d in dirn], "max_dba": dirn[i]["dba"], "theta_max_deg": float(np.degrees(THETAS[i])),
                                         "max_oaspl": max(d["oaspl"] for d in dirn), "at_120": dirn[j]}
            C = out["cases"][f"{c}|{pt}"]
            print(f"  {c:4s} {pt:6s}: rpm {h['rpm']:.0f}, M_tip {h['tip_mach']:.3f}, T {h['T']:.0f} N, Q {h['Q']:.1f} N m, BPF {C['bpf_hz']:.1f} Hz, thrust centroid {Re/Rr:.3f} R;"
                  f" max OASPL {C['max_oaspl']:.1f} dB, max {C['max_dba']:.1f} dBA at {C['theta_max_deg']:.0f} deg; at 120 deg: {dirn[j]['oaspl']:.1f} dB / {dirn[j]['dba']:.1f} dBA", flush=True)
    # hand check: concentrated Gutin at R_e = 0.8 R, first harmonic, theta = 120 deg, one rotor
    hc = {}
    for c in ("tri", "hex0"):
        C = out["cases"][f"{c}|hover"]; om = C["rpm"] * math.pi / 30; B = C["B"]; th = math.radians(120); Re = 0.8 * Rr
        x = B * om * Re * math.sin(th) / a
        p1 = B * om / (2 * math.sqrt(2) * math.pi * a * S_OBS) * abs(-C["T"] * math.cos(th) + C["Q"] * a / (om * Re * Re)) * jv(B, x)
        hc[c] = {"bessel_arg": x, "J_B": float(jv(B, x)), "J_B_small_arg": (x / 2) ** B / math.factorial(B), "thrust_term": -C["T"] * math.cos(th),
                 "torque_term": C["Q"] * a / (om * Re * Re), "p1_pa": p1, "spl1_one_rotor": spl(p1), "spl1_n_rotors": spl(p1) + 10 * math.log10(C["n"]),
                 "model_spl1_n_rotors": C["at_120"]["harmonics"][0]["spl_n"], "a_weight_bpf": a_weight(C["bpf_hz"])}
    t, h = out["cases"]["tri|hover"], out["cases"]["hex0|hover"]
    hc["mach_scaling"] = {"tri_minus_hex_first_harmonic_model": hc["tri"]["model_spl1_n_rotors"] - hc["hex0"]["model_spl1_n_rotors"],
                          "hand": 20 * math.log10(2) - 10 * math.log10(2) + 20 * math.log10(t["rpm"] / h["rpm"]) + 40 * math.log10(t["rpm"] / h["rpm"])}
    out["hand_check"] = hc; out["runtime_s"] = time.time() - t0
    print(f"  hand: {json.dumps(hc, indent=1)}")
    save_json(os.path.join("explore", "e27_rotor_noise.json"), out); plot(out)
    print(f"  wrote results/explore/e27_rotor_noise.json in {out['runtime_s']:.0f} s")


def plot(o):
    fig, axs = plt.subplots(1, 2, figsize=(10, 3.6)); col = {"tri": "#0b0b0b", "hex0": "#2a78d6"}; ls = {"hover": "-", "T/W 2": "--"}
    for k, C in o["cases"].items():
        c, pt = k.split("|")
        axs[0].plot(C["theta_deg"], C["dba"], ls[pt], color=col[c], label=f"{c} {pt} ({C['rpm']:.0f} rpm)")
        axs[1].plot(C["theta_deg"], C["oaspl"], ls[pt], color=col[c], label=f"{c} {pt}")
    for ax, lab in ((axs[0], "A-weighted tonal level [dBA]"), (axs[1], "unweighted tonal OASPL [dB]")):
        ax.set_xlabel("observer angle from thrust axis [deg]  (180 = straight below)"); ax.set_ylabel(lab); ax.grid(alpha=.3); ax.axvline(90, color="#888", lw=0.8)
    axs[0].legend(fontsize=7)
    fig.suptitle(f"Exploration 27: Gutin steady-loading noise of the whole vehicle at {o['observer_m']:.0f} m (harmonics 1-{HARM})", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "e27_rotor_noise.png"), dpi=140); plt.close(fig)


if __name__ == "__main__":
    run()

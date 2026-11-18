"""Exploration 19: consolidated tri vs hex ranking with the uncertainty bands of entries 10-18, and the battery break-even.

No new aerodynamics: the rows of entry 18 (blades of entry 17, arms/fairings of entry 14, hover download, torque-sized
motors) hold hardware mass and pack energy against cruise speed for both layouts and four body models. Here:
  payload difference (hex - tri) = -(dhw + dpack / e_b)        e_b = pack specific energy [Wh/kg]
evaluated for each scenario:
  speed     '15 m/s' (design point) or 'free' (each layout at the speed that minimises hw + pack / e_b)
  body      constant / streamlined / bluff / bluff pre-tilted (entry 18)
  battery   303.3 Wh/kg (vendor, semi-solid) or 200 Wh/kg (conventional LiPo, params 'conservative')
  tip-Mach  0.60, or 0.55 (entry 15: tri hardware + battery +0.71 kg, hex unchanged)
Band: the motor-mass fit (entry 10: -0.89 / +0.21 kg on the hex's payload).
Break-even battery: e_b* = -dpack / dhw, where the two layouts tie (hex wins below it, since it carries the heavier
hardware and the smaller pack).
"""
import json, math, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from common import RESULTS, save_json

OUT = os.path.join(RESULTS, "explore")
EB_CITED, EB_CONS = 303.3, 200.0
TRI_MACH055_KG = 0.71


def rows(e18, c, m):
    rs = e18["cases"][f"{c}|{m}"]["rows"]
    return [{"V": r["V"], "pack": r["pack"], "hw": r["mass_sum"] - r["pack"] / EB_CITED} for r in rs]


def best(rs, eb, v=None):
    if v is not None:
        r = next(r for r in rs if r["V"] == v); return {"V": v, "pack": r["pack"], "hw": r["hw"], "sum": r["hw"] + r["pack"] / eb}
    s = np.array([r["hw"] + r["pack"] / eb for r in rs]); V = np.array([r["V"] for r in rs]); i = int(np.argmin(s)); j = min(max(i, 1), len(rs) - 2)
    a2, a1, a0 = np.polyfit(V[j - 1:j + 2], s[j - 1:j + 2], 2); vb = -a1 / (2 * a2)
    pk = float(np.interp(vb, V, [r["pack"] for r in rs])); hw = float(np.interp(vb, V, [r["hw"] for r in rs]))
    return {"V": vb, "pack": pk, "hw": hw, "sum": a0 + a1 * vb + a2 * vb * vb}


def run():
    e18 = json.load(open(os.path.join(OUT, "e18_body_incidence.json"))); e10 = json.load(open(os.path.join(OUT, "e10_motor_mass.json")))
    band = sorted(v["hex_payload_shift_kg"] for v in e10["sensitivity_motor_fit"].values())
    sc = []
    for speed in ("15 m/s", "free"):
        for body in ("constant", "streamlined", "bluff", "bluff pre-tilted"):
            if speed == "15 m/s" and body != "constant": continue      # body model moves 15 m/s by < 0.06 kg (entry 18)
            for eb in (EB_CITED, EB_CONS):
                for mach in (0.60, 0.55):
                    v = 15.0 if speed == "15 m/s" else None
                    t, h = best(rows(e18, "tri", body), eb, v), best(rows(e18, "hex0", body), eb, v)
                    dsum = t["sum"] + (TRI_MACH055_KG if mach == 0.55 else 0.0) - h["sum"]
                    dhw = h["hw"] - t["hw"] - (TRI_MACH055_KG if mach == 0.55 else 0.0); dpack = h["pack"] - t["pack"]
                    sc.append({"speed": speed, "body": body, "e_b": eb, "mach_cap": mach, "hex_minus_tri_kg": dsum,
                               "band_kg": [dsum + band[0], dsum + band[1]], "V_tri": t["V"], "V_hex": h["V"], "pack_tri": t["pack"], "pack_hex": h["pack"],
                               "energy_hex_vs_tri": h["pack"] / t["pack"] - 1, "dhw_kg": dhw, "dpack_wh": dpack, "e_b_breakeven": -dpack / dhw})
    for s in sc:
        print(f"  {s['speed']:7s} {s['body']:17s} {s['e_b']:5.0f} Wh/kg M{s['mach_cap']:.2f}: hex - tri {s['hex_minus_tri_kg']:+5.2f} kg [{s['band_kg'][0]:+.2f}, {s['band_kg'][1]:+.2f}],"
              f" V {s['V_tri']:.1f}/{s['V_hex']:.1f}, energy {100*s['energy_hex_vs_tri']:+.0f} %, dhw {s['dhw_kg']:+.2f} kg, dpack {s['dpack_wh']:+.0f} Wh, break-even {s['e_b_breakeven']:.0f} Wh/kg")
    # break-even curve: hex - tri against e_b, for the two speed cases (constant body, M 0.60)
    ebs = np.linspace(150, 450, 31); curve = {}
    for speed, v in (("15 m/s", 15.0), ("free", None)):
        curve[speed] = [best(rows(e18, "tri", "constant"), eb, v)["sum"] - best(rows(e18, "hex0", "constant"), eb, v)["sum"] for eb in ebs]
    def cross(ys): i = np.where(np.diff(np.sign(ys)))[0]; return float(np.interp(0, [ys[i[0] + 1], ys[i[0]]], [ebs[i[0] + 1], ebs[i[0]]])) if len(i) else None
    be = {k: cross(np.array(v)) for k, v in curve.items()}
    print(f"  break-even battery (constant body, M 0.60, speed re-optimised at each e_b): {be}")
    out = {"scenarios": sc, "motor_fit_band_kg": band, "breakeven_curve": {"e_b": ebs.tolist(), **curve}, "breakeven_e_b": be}
    save_json(os.path.join("explore", "e19_ranking.json"), out); plot(out)


def plot(o):
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.2), gridspec_kw={"width_ratios": [1.4, 1]})
    S = [s for s in o["scenarios"] if s["mach_cap"] == 0.60]
    lab = [f"{s['speed']}, {s['body']}, {s['e_b']:.0f} Wh/kg" for s in S]; y = np.arange(len(S))
    x = [s["hex_minus_tri_kg"] for s in S]; lo = [s["hex_minus_tri_kg"] - s["band_kg"][0] for s in S]; hi = [s["band_kg"][1] - s["hex_minus_tri_kg"] for s in S]
    axs[0].barh(y, x, color=["#2a78d6" if v > 0 else "#0b0b0b" for v in x], xerr=[lo, hi], capsize=2, ecolor="#888")
    axs[0].set_yticks(y); axs[0].set_yticklabels(lab, fontsize=6); axs[0].axvline(0, color="#888", lw=0.8); axs[0].invert_yaxis()
    axs[0].set_xlabel("hex payload minus tri payload [kg]  (blue: hex wins, black: tri wins; bars: motor-fit band)"); axs[0].grid(axis="x", alpha=.3)
    c = o["breakeven_curve"]
    for k, col in (("15 m/s", "#2a78d6"), ("free", "#0b0b0b")):
        axs[1].plot(c["e_b"], c[k], color=col, label=f"{k} (break-even {o['breakeven_e_b'][k]:.0f} Wh/kg)" if o["breakeven_e_b"][k] else k)
    axs[1].axhline(0, color="#888", lw=0.8); axs[1].axvline(303.3, color="#888", ls=":", lw=0.8); axs[1].axvline(200, color="#888", ls=":", lw=0.8)
    axs[1].set_xlabel("pack specific energy [Wh/kg]"); axs[1].set_ylabel("hex minus tri payload [kg]"); axs[1].legend(fontsize=7); axs[1].grid(alpha=.3)
    fig.suptitle("Exploration 19: tri vs hex across requirements and assumptions (tip-Mach cap 0.60)", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "e19_ranking.png"), dpi=140); plt.close(fig)


if __name__ == "__main__":
    run()

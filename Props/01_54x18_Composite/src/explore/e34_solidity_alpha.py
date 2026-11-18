"""Exploration 34: a wider blade at the same tip speed, to lower alpha* and the BPM angle term (queue item 41).

Entries 30-33: trailing-edge (TE) noise sets the dBA, and its dominant part for the tri is BPM's angle-of-attack term
SPL_alpha. At a given radius thrust fixes c x Cl (entry 32), so a WIDER chord at the same rpm needs a lower Cl, i.e. a
lower alpha*. This entry scales the whole chord distribution of the entry-28 optima by s = 0.85 ... 1.5 and re-solves the
collective pitch (twist offset) so that the hover rpm stays at the baseline value (same tip speed, so the Gutin tones and
the tip Mach stay roughly fixed), then scores
  payload: the entry 13 (tri) / entry 11 (hex) mission evaluation, change relative to s = 1 (blade mass, profile power,
           motor torque sizing all included);
  noise:   total hover dBA at 50 m, 30 deg below the disk = BPM TE (entry 30) + BPM tip vortex, rounded tip, max-Gamma
           angle (entry 31) + Gutin tones.
Cases: tri cap 0.60, tri cap 0.50, hex cap 0.60.

Hand check: c x Cl = const at fixed W -> Cl(s) = Cl(1)/s; with a lift slope a: d alpha* = Cl(1)(1/s - 1)/a at 0.75R.
"""
import json, math, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from multiprocessing import Pool
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SCALES = (0.85, 1.0, 1.15, 1.3, 1.5)
CASES = (("tri", 0.60), ("tri", 0.50), ("hex", 0.60))


def job(args):
    c, cap, s = args
    from scipy.optimize import brentq
    import bemt, e01_coax_blade as e01, e02_coax_two_point as e02, e11_blade_with_motor as e11, e13_tri_torque_margin as e13
    import e24_chain_best_blades as e24, e30_bpm_rotor as e30, e31_tip_noise as e31
    e01.init(); G = e01.G; p, hot = G["p"], G["hot"]; db = e24.db_for(e30.LAY[c][0], "best"); G["db"] = db; p["rotor"]["tip_mach_max"] = cap
    n = e30.LAY[c][1]; Wv = G["ph1"]["vehicle"]["weight_n"]; R = p["rotor"]["diameter_in"] * p["constants"]["inch_to_m"] / 2
    e28 = json.load(open(os.path.join(e30.OUT, "e28_noise_cap.json"))); row = next(x for x in e28["rows"] if x["layout"] == c and x["cap"] == cap)
    b0 = e02.blade_from(row["blade"], R, p["rotor"]["hub_radius_m"]); rpm0 = bemt.hover_at_thrust(b0, db, hot, Wv / n)["rpm"]
    def f(d0):                                      # unreachable thrust = pitch far too low = rpm "above the ceiling"
        try: return bemt.hover_at_thrust(e02.shape(b0, [d0, 0.0, 0.0, s]), db, hot, Wv / n)["rpm"] - rpm0
        except ValueError: return 1e4
    d0 = 0.0 if s == 1.0 else brentq(f, math.radians(-8), math.radians(6), xtol=1e-5)
    b = e02.shape(b0, [d0, 0.0, 0.0, s])
    if c == "tri":
        S = e13.setup(); ev = e13.evaluate(b, S); pay_raw = -(ev["hw"] + ev["pack"] / p["mass"]["pack_wh_per_kg_cited"])
    else:
        S = e11.setup(); ev = e11.evaluate(b, S); pay_raw = ev["payload"]
    bd = e13.as_dict(b)
    te = e30.rotor_bpm(c, bd); tip = e31.tip_rotor(c, bd)
    bb = e31.dba(10 ** (np.array(te["spectrum"]) / 10) + 10 ** (np.array(tip["rounded_G"]["spectrum"]) / 10))
    tot = 10 * math.log10(10 ** (bb / 10) + 10 ** (te["tonal_dba"] / 10))
    st = min(te["strips"], key=lambda q: abs(q["r_over_R"] - 0.75))
    out = {"layout": c, "cap": cap, "s": s, "d0_deg": math.degrees(d0), "rpm": te["rpm"], "rpm0": rpm0, "pay_raw": pay_raw, "pack": ev["pack"], "hw": ev["hw"],
           "blade_kg": ev["blade_kg"], "motor_kg": ev["motor_kg"], "margin": ev["margin"], "tw_mach": ev["tw_mach"], "solidity": b.solidity(),
           "te_dba": te["dba"], "tip_dba": tip["rounded_G"]["dba"], "tonal_dba": te["tonal_dba"], "total_dba": tot, "f_peak": te["f_peak"],
           "alpha_star_075": st["alpha_star"], "c_075": st["c"], "W_075": st["W"], "strip_oaspl_075": st["oaspl"], "blade": bd}
    print(f"  {c} cap {cap:.2f} s {s:.2f}: d0 {math.degrees(d0):+.2f} deg, rpm {te['rpm']:.0f}, sigma {b.solidity():.3f}, a*(0.75R) {st['alpha_star']:.2f},"
          f" TE {te['dba']:.1f}, tip {tip['rounded_G']['dba']:.1f}, tones {te['tonal_dba']:.1f}, total {tot:.1f} dBA; pack {ev['pack']:.0f} Wh, hw {ev['hw']:.2f} kg,"
          f" margin {ev['margin']:.1f}, T/W at cap {ev['tw_mach']:.2f}", flush=True)
    return out


def run():
    from common import RESULTS, save_json
    OUT = os.path.join(RESULTS, "explore")
    with Pool(4) as pool:
        rows = pool.map(job, [(c, cap, s) for c, cap in CASES for s in SCALES])
    summ = {}
    for c, cap in CASES:
        rs = [r for r in rows if r["layout"] == c and r["cap"] == cap]; r1 = next(r for r in rs if r["s"] == 1.0)
        for r in rs:
            r["dpayload"] = r["pay_raw"] - r1["pay_raw"]; r["ddba"] = r["total_dba"] - r1["total_dba"]
            r["kg_per_db"] = (r["dpayload"] / r["ddba"]) if r["s"] > 1 and r["ddba"] < 0 else None
        summ[f"{c} {cap:.2f}"] = [{k: r[k] for k in ("s", "dpayload", "ddba", "kg_per_db", "total_dba", "te_dba", "alpha_star_075", "tw_mach", "margin")} for r in sorted(rs, key=lambda r: r["s"])]
    print(json.dumps(summ, indent=1))
    save_json(os.path.join("explore", "e34_solidity_alpha.json"), {"rows": rows, "summary": summ}); plot(rows, OUT)
    print("  wrote results/explore/e34_solidity_alpha.json")


def plot(rows, OUT):
    fig, axs = plt.subplots(1, 2, figsize=(10, 3.6)); sty = {("tri", 0.60): ("#0b0b0b", "o-"), ("tri", 0.50): ("#0b0b0b", "s--"), ("hex", 0.60): ("#2a78d6", "o-")}
    for (c, cap), (col, ls) in sty.items():
        rs = sorted((r for r in rows if r["layout"] == c and r["cap"] == cap), key=lambda r: r["s"])
        axs[0].plot([r["s"] for r in rs], [r["alpha_star_075"] for r in rs], ls, color=col, label=f"{c} cap {cap:.2f}")
        axs[1].plot([r["total_dba"] for r in rs], [r["dpayload"] for r in rs], ls, color=col, label=f"{c} cap {cap:.2f}")
        for r in rs: axs[1].annotate(f"{r['s']:.2f}", (r["total_dba"], r["dpayload"]), fontsize=6, xytext=(3, 2), textcoords="offset points")
    axs[0].set_xlabel("chord scale s (same hover rpm)"); axs[0].set_ylabel("alpha* at 0.75 R [deg]"); axs[0].grid(alpha=.3); axs[0].legend(fontsize=6)
    axs[1].set_xlabel("total hover level [dBA] at 50 m"); axs[1].set_ylabel("payload vs s = 1 [kg]"); axs[1].grid(alpha=.3); axs[1].legend(fontsize=6)
    fig.suptitle("Exploration 34: wider chord at the same tip speed (lower alpha*), rounded tips", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "e34_solidity_alpha.png"), dpi=140); plt.close(fig)


if __name__ == "__main__":
    run()

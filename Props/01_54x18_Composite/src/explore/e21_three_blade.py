"""Exploration 21: 3-blade rotors for the tri and hex, with the motor in the objective (entries 11 and 13's optimisers).

Start: each layout's 2-blade optimum with the chord scaled by 2/3 (same solidity, so the same C_T/sigma), N = 3.
Changes to the bookkeeping for N = 3: one more blade per rotor (spar model, its own 50 N / 1.2 mm flex test, so the
narrower chord needs a relatively heavier spar) and a heavier hub: HUB_3 = hub + 0.10 kg (third grip and pitch link;
assumption). Motors, ESCs, arms, pack model as in entries 11/13 (15 m/s design point).
Also printed: the hub load ripple in cruise (blade_trade_study.hub_ripple: N-per-rev roll moment and thrust), the main
non-energy argument for a third blade.

Hand check: Prandtl's effective-radius tip loss, R_e / R = 1 - sqrt(2 C_T) / B, so the ideal induced power at fixed thrust
scales as (R_e)^-1: P_i3 / P_i2 = (1 - sqrt(2 C_T)/2) / (1 - sqrt(2 C_T)/3), against the BEMT's induced share.
"""
import json, math, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from multiprocessing import Pool
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import bemt
import e01_coax_blade as e01
import e02_coax_two_point as e02
import e11_blade_with_motor as e11
import e13_tri_torque_margin as e13
from blade_trade_study import hub_ripple
from common import RESULTS, save_json

OUT = os.path.join(RESULTS, "explore")
N_B = 3
HUB_EXTRA = 0.10


def patch():
    e02.blade_from = lambda d, R, rh: bemt.Blade(R, rh, N_B, d["r"], d["chord"], np.radians(d["twist_deg"]), d["tc"])
    f11, f13 = e11.evaluate, e13.evaluate
    def ev11(b, S, frozen=None):
        r = f11(b, S, frozen)
        if b.N == 3:
            add = 6 * (r["blade_kg"] + HUB_EXTRA); r["hw"] += add; r["payload"] -= add
        return r
    def ev13(b, S, ref=None):
        r = f13(b, S, ref)
        if b.N == 3:
            add = 3 * (r["blade_kg"] + HUB_EXTRA); r["hw"] += add
            if "dpayload" in r: r["dpayload"] -= add
        return r
    e11.evaluate, e13.evaluate = ev11, ev13


def job(layout):
    e01.init(); patch()
    e13r = json.load(open(os.path.join(OUT, "e13_tri_torque_margin.json"))); e11r = json.load(open(os.path.join(OUT, "e11_blade_with_motor.json")))
    if layout == "tri":
        bd = dict(max(e13r["runs"], key=lambda r: r["end"]["dpayload"])["blade"])
    else:
        bd = dict(max((x for x in e11r["runs"] if x["mode"] == "motor"), key=lambda x: x["end"]["payload"])["blade"])
    bd["chord"] = [c * 2 / 3 for c in bd["chord"]]
    if layout == "tri":
        r = e13.optimise(("tri 3-blade", bd)); pay = lambda e: e["dpayload"]
    else:
        r = e11.optimise(("hex 3-blade", bd, "motor")); pay = lambda e: e["payload"]
    return {"layout": layout, "payload_start": pay(r["start"]), "payload_end": pay(r["end"]), "start": {k: r["start"][k] for k in ("pack", "hw", "Q_max", "rpm_hover", "solidity", "blade_kg", "motor_kg")},
            "end": {k: r["end"][k] for k in ("pack", "hover", "hw", "Q_max", "rpm_hover", "solidity", "blade_kg", "motor_kg", "defl_mm", "margin", "tw_mach")},
            "blade": r["blade"], "runtime_s": r["runtime_s"]}


def loads(layout, blade_d, N):
    """Hover C_T, induced share and cruise hub ripple for one blade set."""
    G = e01.G; p, ph1, db, hot = G["p"], G["ph1"], G["db"], G["hot"]; W = ph1["vehicle"]["weight_n"]; n = 3 if layout == "tri" else 6
    Rr = p["rotor"]["diameter_in"] * p["constants"]["inch_to_m"] / 2
    b = bemt.Blade(Rr, p["rotor"]["hub_radius_m"], N, blade_d["r"], blade_d["chord"], np.radians(blade_d["twist_deg"]), blade_d["tc"])
    h = bemt.hover_at_thrust(b, db, hot, W / n); om = h["rpm"] * 2 * math.pi / 60; A = math.pi * Rr ** 2
    ct = (W / n) / (hot["rho"] * A * (om * Rr) ** 2); p_ideal = (W / n) ** 1.5 / math.sqrt(2 * hot["rho"] * A)
    ctx = e02.context()
    e = bemt.edgewise_at_thrust(b, db, hot, ctx["t_tot"] / n, p["mission"]["cruise_speed_ms"], ctx["alpha"], kappa=p["rotor"]["kappa"])
    return {"C_T": ct, "P_hover": h["P"], "P_ideal": p_ideal, "FM": p_ideal / h["P"], "rpm": h["rpm"], "ripple": hub_ripple(e, N), "solidity": b.solidity()}


def run():
    t0 = time.time(); e01.init()
    with Pool(2) as pool:
        rows = pool.map(job, ["tri", "hex"])
    e13r = json.load(open(os.path.join(OUT, "e13_tri_torque_margin.json"))); e11r = json.load(open(os.path.join(OUT, "e11_blade_with_motor.json")))
    b2 = {"tri": max(e13r["runs"], key=lambda r: r["end"]["dpayload"]), "hex": max((x for x in e11r["runs"] if x["mode"] == "motor"), key=lambda x: x["end"]["payload"])}
    base = {"tri": b2["tri"]["end"]["dpayload"], "hex": b2["hex"]["end"]["payload"]}
    hc = {}
    for r in rows:
        L = r["layout"]; r["payload_vs_2blade"] = r["payload_end"] - base[L]
        two = loads(L, b2[L]["blade"], 2); three = loads(L, r["blade"], 3)
        # same-solidity comparison: the 2-blade optimum with chord x 2/3 and N = 3, untrimmed geometry
        bd = dict(b2[L]["blade"]); bd["chord"] = [c * 2 / 3 for c in bd["chord"]]; same = loads(L, bd, 3)
        ct = two["C_T"]; hand_ratio = (1 - math.sqrt(2 * ct) / 2) / (1 - math.sqrt(2 * ct) / 3)
        hc[L] = {"C_T": ct, "hand_Pi3_over_Pi2": hand_ratio, "hand_dP_w": (hand_ratio - 1) * two["P_ideal"] * 1.0,
                 "bemt_dP_same_solidity_w": same["P_hover"] - two["P_hover"], "FM_2": two["FM"], "FM_3_same_sigma": same["FM"], "FM_3_opt": three["FM"],
                 "ripple_2": two["ripple"], "ripple_3": three["ripple"]}
        print(f"  {L}: 3-blade payload {r['payload_start']:+.2f} -> {r['payload_end']:+.2f} kg (2-blade {base[L]:+.2f}; change {r['payload_vs_2blade']:+.2f}),"
              f" pack {r['end']['pack']:.0f} Wh, rpm_h {r['end']['rpm_hover']:.0f}, sigma {r['end']['solidity']:.3f}, blade {r['end']['blade_kg']:.3f} kg x3,"
              f" motor {r['end']['motor_kg']:.2f}; FM {two['FM']:.3f} -> {same['FM']:.3f} (same sigma) / {three['FM']:.3f} (opt);"
              f" hub roll ripple {two['ripple']['roll_ripple']:.1f} -> {three['ripple']['roll_ripple']:.1f} N m", flush=True)
    out = {"rows": rows, "baseline_2blade": base, "hand_check": hc, "hub_extra_kg": HUB_EXTRA, "runtime_s": time.time() - t0}
    print(f"  hand: {hc}")
    save_json(os.path.join("explore", "e21_three_blade.json"), out); plot(out, b2)
    print(f"  wrote results/explore/e21_three_blade.json in {out['runtime_s']:.0f} s")


def plot(o, b2):
    fig, ax = plt.subplots(1, 2, figsize=(9, 3.3)); col = {"tri": "#0b0b0b", "hex": "#2a78d6"}
    for r in o["rows"]:
        L = r["layout"]
        for bd, ls, lab in ((b2[L]["blade"], "-", "2-blade"), (r["blade"], "--", "3-blade")):
            x = np.array(bd["r"]) / max(bd["r"])
            ax[0].plot(x, 1000 * np.array(bd["chord"]), ls, color=col[L], label=f"{L} {lab}"); ax[1].plot(x, bd["twist_deg"], ls, color=col[L])
    ax[0].set_xlabel("r / R"); ax[0].set_ylabel("chord [mm]"); ax[0].legend(fontsize=6); ax[0].grid(alpha=.3)
    ax[1].set_xlabel("r / R"); ax[1].set_ylabel("twist [deg]"); ax[1].grid(alpha=.3)
    fig.suptitle("Exploration 21: 3-blade rotors with torque-sized motors", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "e21_three_blade.png"), dpi=140); plt.close(fig)


if __name__ == "__main__":
    run()

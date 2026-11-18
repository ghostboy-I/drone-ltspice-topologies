"""Exploration 13: the tricopter reference re-optimised with torque-sized motors, and the U15XL torque margin.

Two questions about the reference every payload number is measured against:
  (a) Entry 10 noted that the tri at T/W 2 on the hot day needs 55.8 N m per rotor, but the U15XL's 96 V vendor test
      delivers 50.4 N m. What T/W does the real motor give with the Phase 2 blade?
  (b) Entries 11-12 re-optimised the hex and y6 blades with motor mass ~ peak torque in the objective; the tri kept its
      Phase 2 blade. If the tri blade gains too, the hex's +2.3 kg lead shrinks. Re-optimise it the same way.

Model (entry 11's, for 3 rotors at W/3):
    pack: 3 isolated rotors in hover, 3 edgewise rotors in cruise + entry 09's tri interference and arm drag
    hardware: 3 x (motor + ESC + 2 blades + hub) + tilt servo + arms (entry 10), motor = a Q_max^n (entry 10 fit),
              ESC = 0.870 kg (P_max / P_max,tri)^0.7, blade mass from the spar model (50 N / 1.2 mm)
    payload is reported as the change against the Phase 2 blade scored with this same model (so model offsets cancel)
Constraints: stall margin, T/W >= 2 reachable below the tip-Mach rpm, flex test, tip chord floor.
Starts: the Phase 2 blade, and entry 11's hex optimum (scaled to the tri's thrust it is a narrow, fast blade).
Discrete-motor check: with the real U15XL (4.408 kg, 50.4 N m), the T/W at that torque, from BEMT.

Hand check: for a fixed-pitch rotor T and Q both scale with Omega^2, so T/W at a torque limit is
    T/W(Q_lim) = 2 x Q_lim / Q(T/W 2) .
"""
import json, math, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from multiprocessing import Pool
from scipy.optimize import minimize, brentq
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import bemt, design_opt as do, momentum as mt
from config_study import mission_pack, load_final_blade
from blade_structure import blade_mass
import e01_coax_blade as e01
import e02_coax_two_point as e02
import e10_motor_mass as e10
from e11_blade_with_motor import motor_fit
from common import RESULTS, save_json

OUT = os.path.join(RESULTS, "explore")
U15XL_KG, U15XL_NM = 4.408, 50.4


def as_dict(b):
    return {"r": b.r_def.tolist(), "chord": b.c_def.tolist(), "twist_deg": np.degrees(b.th_def).tolist(), "tc": b.tc_def.tolist()}


def setup():
    e9 = json.load(open(os.path.join(OUT, "e09_hex_vs_y6.json"))); e10r = json.load(open(os.path.join(OUT, "e10_motor_mass.json")))
    return {"ctx": e02.context(), "inter_w": e9["configs"]["tri"]["interference_w"], "arm_drag_w": e9["configs"]["tri"]["arm_drag_w"],
            "arms_kg": e10r["configs"]["tri"]["arms_kg"], "P_max_tri": e10r["required"]["tri"]["P_max"], "fit": motor_fit()}


def evaluate(b, S, ref=None):
    G = e01.G; p, ph1, db, hot = G["p"], G["ph1"], G["db"], G["hot"]
    W = ph1["vehicle"]["weight_n"]; tw = p["vehicle"]["tw_target"]; V = p["mission"]["cruise_speed_ms"]; ctx = S["ctx"]
    iso = bemt.hover_at_thrust(b, db, hot, W / 3); mx = bemt.hover_at_thrust(b, db, hot, tw * W / 3)
    e = bemt.edgewise_at_thrust(b, db, hot, ctx["t_tot"] / 3, V, ctx["alpha"], kappa=p["rotor"]["kappa"])
    hover = 3 * iso["P"]; cruise = 3 * e["P"] + S["inter_w"] + S["arm_drag_w"]
    pack = mission_pack(p, ph1, hover, ctx["base_climb"] * hover / ctx["base_hover"], cruise)[0]
    a, n = S["fit"]
    motor = a * mx["Q"] ** n; esc = e10.ESC_KG * (mx["P"] / S["P_max_tri"]) ** e10.ESC_EXP
    ms = blade_mass(b.r_def, b.c_def, b.tc_def, b.r_hub, b.R)
    hw = 3 * (motor + esc + 2 * ms["total_kg"] + ctx["hub"]) + ctx["tilt"] + S["arms_kg"]
    rpm_mach = mt.rpm_from_vtip(p["rotor"]["tip_mach_max"] * hot["a"], 2 * b.R)
    tw_mach = bemt.axial(b, db, hot, rpm_mach)["T"] / (W / 3)
    r = {"pack": pack, "hover": hover, "cruise": cruise, "hw": hw, "motor_kg": motor, "esc_kg": esc, "blade_kg": ms["total_kg"],
         "defl_mm": ms["tip_deflection_mm"], "Q_max": mx["Q"], "P_max": mx["P"], "rpm_hover": iso["rpm"], "rpm_max": mx["rpm"],
         "P_hover_rotor": iso["P"], "Q_hover": iso["Q"], "tw_mach": tw_mach, "tip_mach_max": p["rotor"]["tip_mach_max"] * mx["rpm"] / rpm_mach,
         "margin": do.stall_margin_deg(db, iso, b.R), "solidity": b.solidity()}
    if ref is not None:
        r["dpayload"] = -(hw - ref["hw"] + (pack - ref["pack"]) / p["mass"]["pack_wh_per_kg_cited"])
    return r


def tw_at_torque(b, q_lim):
    """BEMT: thrust-to-weight at which the rotor's hot-day torque reaches q_lim (fixed pitch, rpm is the free variable)."""
    G = e01.G; db, hot, W = G["db"], G["hot"], G["ph1"]["vehicle"]["weight_n"]
    rpm = brentq(lambda n: bemt.axial(b, db, hot, n)["Q"] - q_lim, 500, 6000, xtol=0.1)
    return bemt.axial(b, db, hot, rpm)["T"] / (W / 3), rpm


def optimise(args):
    label, bd = args
    t0 = time.time(); G = e01.G; p = G["p"]; S = setup()
    R = p["rotor"]["diameter_in"] * p["constants"]["inch_to_m"] / 2
    ref = evaluate(load_final_blade(p), S)
    b0 = e02.blade_from(bd, R, p["rotor"]["hub_radius_m"]); r0 = evaluate(b0, S, ref); hist = []

    def obj(x):
        try:
            b = e02.shape(b0, x)
            if float(np.min(b.c_def)) < p["design"]["chord_tip_min_m"] * 0.999: return 1e3
            r = evaluate(b, S, ref)
            pen = 5 * max(0.0, p["design"]["min_stall_margin_deg"] - r["margin"]) ** 2 + 200 * max(0.0, p["vehicle"]["tw_target"] - r["tw_mach"]) ** 2
            pen += 50 * max(0.0, r["defl_mm"] / 1.2 - 1.0)
            hist.append((list(map(float, x)), r["dpayload"], pen)); return -r["dpayload"] + pen
        except Exception:
            return 1e3
    x0 = [0.0, 0.0, 0.0, 1.0]
    simplex = [x0, [math.radians(1), 0, 0, 1], [0, math.radians(3), 0, 1], [0, 0, 0.3, 1], [0, 0, 0, 0.85]]
    res = minimize(obj, x0, method="Nelder-Mead", options={"initial_simplex": simplex, "xatol": 2e-4, "fatol": 0.005, "maxfev": 180})
    b1 = e02.shape(b0, res.x); r1 = evaluate(b1, S, ref)
    tw0, rpm0 = tw_at_torque(b0, U15XL_NM); tw1, rpm1 = tw_at_torque(b1, U15XL_NM)
    out = {"label": label, "x": list(map(float, res.x)), "evaluations": int(res.nfev), "start": r0, "end": r1,
           "u15xl_tw_start": tw0, "u15xl_rpm_start": rpm0, "u15xl_tw_end": tw1, "u15xl_rpm_end": rpm1, "history": hist,
           "blade": as_dict(b1), "runtime_s": time.time() - t0}
    print(f"  {label}: dpayload {r0['dpayload']:+.2f} -> {r1['dpayload']:+.2f} kg, pack {r0['pack']:.0f} -> {r1['pack']:.0f} Wh,"
          f" rpm_h {r0['rpm_hover']:.0f} -> {r1['rpm_hover']:.0f}, sigma {r0['solidity']:.3f} -> {r1['solidity']:.3f}, Q_max {r0['Q_max']:.1f} -> {r1['Q_max']:.1f},"
          f" motor {r0['motor_kg']:.2f} -> {r1['motor_kg']:.2f}, tip M {r0['tip_mach_max']:.3f} -> {r1['tip_mach_max']:.3f}; U15XL T/W {tw0:.2f} -> {tw1:.2f} [{out['runtime_s']:.0f}s]", flush=True)
    return out


def run():
    t0 = time.time(); e01.init(); p = e01.G["p"]
    e11 = json.load(open(os.path.join(OUT, "e11_blade_with_motor.json")))
    hexopt = max((r for r in e11["runs"] if r["mode"] == "motor"), key=lambda r: r["end"]["payload"])
    starts = [("Phase 2 blade", as_dict(load_final_blade(p))), ("e11 hex optimum", hexopt["blade"])]
    with Pool(2, initializer=e01.init) as pool:
        runs = pool.map(optimise, starts)
    S = setup(); ref = evaluate(load_final_blade(p), S); e10r = json.load(open(os.path.join(OUT, "e10_motor_mass.json")))
    best = max(runs, key=lambda r: r["end"]["dpayload"])
    hc = {"Q_max_ref": ref["Q_max"], "Q_max_ref_e10": e10r["required"]["tri"]["Q_max"],
          "hand_tw_u15xl_ref": 2 * U15XL_NM / ref["Q_max"], "bemt_tw_u15xl_ref": runs[0]["u15xl_tw_start"],
          "hand_Q_max_2Qh_ref": 2 * ref["Q_hover"], "hand_tw_u15xl_best": 2 * U15XL_NM / best["end"]["Q_max"], "bemt_tw_u15xl_best": best["u15xl_tw_end"],
          "ref_pack_this_model": ref["pack"], "ref_pack_e09": json.load(open(os.path.join(OUT, "e09_hex_vs_y6.json")))["configs"]["tri"]["pack_wh"],
          "ref_motor_fit_kg": ref["motor_kg"], "u15xl_kg": U15XL_KG}
    e12 = json.load(open(os.path.join(OUT, "e12_y6_blade_with_motor.json")))
    y6best = max(r["end_full"]["payload"] for r in e12["runs"])
    rank = {"hex_vs_new_tri": hexopt["end"]["payload"] - best["end"]["dpayload"], "y6_vs_new_tri": y6best - best["end"]["dpayload"],
            "hex_pack": hexopt["end"]["pack"], "tri_pack_new": best["end"]["pack"]}
    out = {"runs": runs, "reference": ref, "best": best["label"], "hand_check": hc, "ranking_vs_reoptimised_tri": rank, "runtime_s": time.time() - t0}
    save_json(os.path.join("explore", "e13_tri_torque_margin.json"), out); plot(out)
    print(f"  hand check: {hc}\n  ranking: {rank}\n  wrote results/explore/e13_tri_torque_margin.json in {out['runtime_s']:.0f} s")


def plot(o):
    fig, axs = plt.subplots(1, 3, figsize=(12, 3.3)); ls = {"Phase 2 blade": "-", "e11 hex optimum": "--"}
    for r in o["runs"]:
        b = r["blade"]; x = np.array(b["r"]) / max(b["r"])
        axs[0].plot(x, 1000 * np.array(b["chord"]), color="#0b0b0b", ls=ls[r["label"]], label=f"{r['label']} -> optimum")
        axs[1].plot(x, b["twist_deg"], color="#0b0b0b", ls=ls[r["label"]], label=r["label"])
        h = np.array([q[1] - q[2] for q in r["history"]]); axs[2].plot(np.maximum.accumulate(h), color="#0b0b0b", ls=ls[r["label"]], label=r["label"])
    p = e01.G["p"] if e01.G else None
    ref = o["reference"]
    axs[0].set_xlabel("r / R"); axs[0].set_ylabel("chord [mm]"); axs[0].legend(fontsize=6); axs[0].grid(alpha=.3)
    axs[1].set_xlabel("r / R"); axs[1].set_ylabel("twist [deg]"); axs[1].grid(alpha=.3)
    axs[2].set_xlabel("evaluation"); axs[2].set_ylabel("best objective (dpayload - penalty) [kg]"); axs[2].set_ylim(-4, 3); axs[2].grid(alpha=.3)
    axs[2].axhline(0, color="#2a78d6", lw=0.8); axs[2].legend(fontsize=6)
    fig.suptitle(f"Exploration 13: tricopter blade with torque-sized motors (reference Q_max {ref['Q_max']:.1f} N m)", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "e13_tri_torque_margin.png"), dpi=140); plt.close(fig)


if __name__ == "__main__":
    if sys.argv[1:] == ["plot"]:
        plot(json.load(open(os.path.join(OUT, "e13_tri_torque_margin.json"))))
    else:
        run()

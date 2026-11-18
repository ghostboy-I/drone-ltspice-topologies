"""Exploration 12: the Y6 (coaxial, h/D 0.4) blade re-optimised with torque-sized motors, like entry 11 for the hex.

The full coaxial trim costs about 20 s per call, too slow inside Nelder-Mead, so (as in entry 02) the optimiser uses
surrogates calibrated once on the start blade and checked again on the end blade:
  hover power      P_pair = k_P x 2 P_iso(T_arm / 2)                     k_P = P_pair / (2 P_iso)     at the start
  peak torque      Q_max  = k_Q x Q_iso(T/W 2 x T_arm / 2)               k_Q = Q_pair,max / Q_iso,max at the start
  cruise           6 P_edgewise(T/6) + interference + arm and mast drag
                   interference = 3 T v_i0 (m_l + m_u)  within the arm (entry 07: m depends only on the geometry)
                                + the inter-arm part from entry 09, scaled with v_i0 (wake strength ~ own induced velocity)
Tip Mach: at T/W 2 the lower rotor spins about 25 % faster than an isolated one, so the 0.60 cap is applied to it
(rpm_lower,max = r_lower x rpm_iso,max, r_lower calibrated on the start blade; the first run without it ended at M 0.65).
Mass and payload bookkeeping as in entries 10-11 (y6 arms with two motor mounts, masts at 0.51 kg/m).

Hand check: the pair runs at equal torque Q, but the lower rotor spins faster (it sits in the upper wake), so with P = Q Omega
    P_pair = Q (Omega_u + Omega_l)   and   2 P_iso = 2 Q_iso Omega_iso   ->   k_P = k_Q (Omega_u + Omega_l) / (2 Omega_iso)
The torque penalty k_Q is smaller than the power penalty k_P by the mean speed-up of the pair. That is why the coaxial motors
are only 16 % heavier than the hex's, not 34 %.
"""
import json, math, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from multiprocessing import Pool
from scipy.optimize import minimize
import bemt, design_opt as do, momentum as mt
from config_study import mission_pack
from blade_structure import blade_mass
import e01_coax_blade as e01
import e02_coax_two_point as e02
from e05_diameter_split import coax_split
from e06_coax_spacing import blade_e03
import e10_motor_mass as e10
from e11_blade_with_motor import motor_fit
from common import RESULTS, save_json

OUT = os.path.join(RESULTS, "explore")
H_D = 0.4
M_WITHIN = 0.294 + 0.291          # entry 07 at h/D 0.4: mean w on lower + on upper, per unit v_i0


def setup():
    e9 = json.load(open(os.path.join(OUT, "e09_hex_vs_y6.json"))); e10r = json.load(open(os.path.join(OUT, "e10_motor_mass.json")))
    y = e9["configs"]["y6"]
    ctx = e02.context(); T_rot = ctx["t_tot"] / 6
    vi0_ref = e9["op_six"]["vi0"]
    within_ref = 3 * T_rot * vi0_ref * M_WITHIN
    return {"ctx": ctx, "inter_arms_ref": y["interference_w"] - within_ref, "vi0_ref": vi0_ref, "drag_w": y["arm_drag_w"] + y["mast_drag_w"],
            "arms_kg": e10r["configs"]["y6"]["arms_kg"], "mast_kg": 3 * 0.51 * H_D * 2 * 0.6858, "hw_tri": e10r["configs"]["tri"]["hardware_kg"],
            "pack_tri": e9["configs"]["tri"]["pack_wh"], "P_max_tri": e10r["required"]["tri"]["P_max"], "fit": motor_fit(), "within_ref_w": within_ref}


def full_coax(b):
    G = e01.G; p, ph1, db, hot = G["p"], G["ph1"], G["db"], G["hot"]
    W = ph1["vehicle"]["weight_n"]; tw = p["vehicle"]["tw_target"]; h = H_D * 2 * b.R
    hov = coax_split(b, b, db, hot, W / 3, h); mx = coax_split(b, b, db, hot, tw * W / 3, h)
    iso = bemt.hover_at_thrust(b, db, hot, W / 6); iso_m = bemt.hover_at_thrust(b, db, hot, tw * W / 6)
    return {"P_pair": hov["P"], "k_P": hov["P"] / (2 * iso["P"]), "Q_max": mx["upper"]["Q"], "P_max": max(mx["upper"]["P"], mx["lower"]["P"]),
            "k_Q": mx["upper"]["Q"] / iso_m["Q"], "k_P_max": max(mx["upper"]["P"], mx["lower"]["P"]) / iso_m["P"], "k_P_pair_max": mx["P"] / (2 * iso_m["P"]),
            "rpm_upper": hov["upper"]["rpm"], "rpm_lower": hov["lower"]["rpm"], "rpm_upper_max": mx["upper"]["rpm"], "rpm_lower_max": mx["lower"]["rpm"],
            "rpm_iso_max": iso_m["rpm"], "hand_k_P_from_k_Q": mx["upper"]["Q"] / iso_m["Q"] * (mx["upper"]["rpm"] + mx["lower"]["rpm"]) / (2 * iso_m["rpm"])}


def evaluate(b, S, k_P, k_Q, k_Pm, coax=None):
    G = e01.G; p, ph1, db, hot = G["p"], G["ph1"], G["db"], G["hot"]
    W = ph1["vehicle"]["weight_n"]; tw = p["vehicle"]["tw_target"]; V = p["mission"]["cruise_speed_ms"]; ctx = S["ctx"]
    iso = bemt.hover_at_thrust(b, db, hot, W / 6)
    if coax is None:
        iso_m = bemt.hover_at_thrust(b, db, hot, tw * W / 6)
        hover = 3 * k_P * 2 * iso["P"]; Q_max = k_Q * iso_m["Q"]; P_max = k_Pm * iso_m["P"]
        rpm_lower_max = S.get("r_lower", 1.0) * iso_m["rpm"]
    else:
        hover = 3 * coax["P_pair"]; Q_max = coax["Q_max"]; P_max = coax["P_max"]; rpm_lower_max = coax["rpm_lower_max"]
    e = bemt.edgewise_at_thrust(b, db, hot, ctx["t_tot"] / 6, V, ctx["alpha"], kappa=p["rotor"]["kappa"])
    vi0 = e["lam0"] * e["rpm"] * 2 * math.pi / 60 * b.R; T_rot = ctx["t_tot"] / 6
    inter = 3 * T_rot * vi0 * M_WITHIN + S["inter_arms_ref"] * vi0 / S["vi0_ref"]
    cruise = 6 * e["P"] + inter + S["drag_w"]
    pack = mission_pack(p, ph1, hover, ctx["base_climb"] * hover / ctx["base_hover"], cruise)[0]
    a, n = S["fit"]; motor = a * Q_max ** n; esc = e10.ESC_KG * (P_max / S["P_max_tri"]) ** e10.ESC_EXP
    ms = blade_mass(b.r_def, b.c_def, b.tc_def, b.r_hub, b.R)
    hw = 6 * (motor + esc + 2 * ms["total_kg"] + ctx["hub"]) + S["arms_kg"] + S["mast_kg"]
    payload = -(hw - S["hw_tri"] + (pack - S["pack_tri"]) / p["mass"]["pack_wh_per_kg_cited"])
    rpm_mach = mt.rpm_from_vtip(p["rotor"]["tip_mach_max"] * hot["a"], 2 * b.R)
    tw_mach = bemt.axial(b, db, hot, rpm_mach)["T"] / (W / 6)
    return {"payload": payload, "pack": pack, "hover": hover, "cruise": cruise, "interference_w": inter, "hw": hw, "motor_kg": motor, "esc_kg": esc,
            "blade_kg": ms["total_kg"], "defl_mm": ms["tip_deflection_mm"], "Q_max": Q_max, "rpm_iso_hover": iso["rpm"], "tw_mach": tw_mach,
            "margin": do.stall_margin_deg(db, iso, b.R), "solidity": b.solidity(),
            "rpm_lower_max": rpm_lower_max, "rpm_mach": rpm_mach, "tip_mach_lower_max": p["rotor"]["tip_mach_max"] * rpm_lower_max / rpm_mach}


def optimise(args):
    label, bd = args
    t0 = time.time(); p = e01.G["p"]; S = setup()
    R = p["rotor"]["diameter_in"] * p["constants"]["inch_to_m"] / 2
    b0 = e02.blade_from(bd, R, p["rotor"]["hub_radius_m"])
    c0 = full_coax(b0); k = (c0["k_P"], c0["k_Q"], c0["k_P_max"])
    S["r_lower"] = c0["rpm_lower_max"] / c0["rpm_iso_max"]      # the lower rotor at T/W 2 spins this much faster than an isolated one
    r0_full = evaluate(b0, S, *k, coax=c0); r0_sur = evaluate(b0, S, *k)
    hist = []

    def obj(x):
        try:
            b = e02.shape(b0, x)
            if float(np.min(b.c_def)) < p["design"]["chord_tip_min_m"] * 0.999: return 1e3
            r = evaluate(b, S, *k)
            pen = 5 * max(0.0, p["design"]["min_stall_margin_deg"] - r["margin"]) ** 2 + 200 * max(0.0, p["vehicle"]["tw_target"] - r["tw_mach"]) ** 2
            pen += 50 * max(0.0, r["defl_mm"] / 1.2 - 1.0)
            pen += 200 * max(0.0, r["rpm_lower_max"] / r["rpm_mach"] - 1.0) ** 2 * 100      # lower rotor's tip Mach at T/W 2
            hist.append((list(map(float, x)), r["payload"], pen)); return -r["payload"] + pen
        except Exception:
            return 1e3
    x0 = [0.0, 0.0, 0.0, 1.0]
    simplex = [x0, [math.radians(1), 0, 0, 1], [0, math.radians(3), 0, 1], [0, 0, 0.3, 1], [0, 0, 0, 0.85]]
    res = minimize(obj, x0, method="Nelder-Mead", options={"initial_simplex": simplex, "xatol": 2e-4, "fatol": 0.005, "maxfev": 180})
    b1 = e02.shape(b0, res.x); c1 = full_coax(b1)
    r1_sur = evaluate(b1, S, *k); r1_full = evaluate(b1, S, *k, coax=c1)
    out = {"label": label, "x": list(map(float, res.x)), "evaluations": int(res.nfev), "k_start": c0, "k_end": c1,
           "start_full": r0_full, "start_surrogate": r0_sur, "end_surrogate": r1_sur, "end_full": r1_full, "history": hist,
           "blade": {"r": b1.r_def.tolist(), "chord": b1.c_def.tolist(), "twist_deg": np.degrees(b1.th_def).tolist(), "tc": b1.tc_def.tolist()},
           "runtime_s": time.time() - t0}
    print(f"  {label}: payload {r0_full['payload']:+.2f} -> {r1_full['payload']:+.2f} kg (full; surrogate {r1_sur['payload']:+.2f}), pack {r0_full['pack']:.0f} -> {r1_full['pack']:.0f} Wh,"
          f" rpm_iso {r0_full['rpm_iso_hover']:.0f} -> {r1_full['rpm_iso_hover']:.0f}, sigma {r0_full['solidity']:.3f} -> {r1_full['solidity']:.3f}, Q_max {r0_full['Q_max']:.1f} -> {r1_full['Q_max']:.1f},"
          f" motor {r0_full['motor_kg']:.2f} -> {r1_full['motor_kg']:.2f}, lower tip M at T/W 2 {r1_full['tip_mach_lower_max']:.3f}; k_P {c0['k_P']:.3f}->{c1['k_P']:.3f}, k_Q {c0['k_Q']:.3f}->{c1['k_Q']:.3f} [{out['runtime_s']:.0f}s]", flush=True)
    return out


def run():
    t0 = time.time(); e01.init(); p = e01.G["p"]
    b3 = blade_e03(p)
    e11 = json.load(open(os.path.join(OUT, "e11_blade_with_motor.json")))
    hexbest = max((r for r in e11["runs"] if r["mode"] == "motor"), key=lambda r: r["end"]["payload"])["blade"]
    starts = [("e03 blade", {"r": b3.r_def.tolist(), "chord": b3.c_def.tolist(), "twist_deg": np.degrees(b3.th_def).tolist(), "tc": b3.tc_def.tolist()}),
              ("e11 hex optimum", hexbest)]
    with Pool(2, initializer=e01.init) as pool:
        runs = pool.map(optimise, starts)
    out = {"h_over_D": H_D, "runs": runs, "runtime_s": time.time() - t0}
    save_json(os.path.join("explore", "e12_y6_blade_with_motor.json"), out)
    print(f"  wrote results/explore/e12_y6_blade_with_motor.json in {out['runtime_s']:.0f} s")


if __name__ == "__main__":
    run()

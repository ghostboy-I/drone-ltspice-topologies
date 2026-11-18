"""Exploration 02: two-point (hover + cruise) refinement of the coaxial blade, objective = payload.

Start from entry 01's half-thrust MIL blades (and from the Phase 2 blade) and let Nelder-Mead move four variables:
twist offset d0, twist slope d1 (per unit r/R about 0.75 R), chord taper e1 and an overall chord scale s:
    chord(x) = s c(x) (1 + e1 (x - 0.75)),   twist(x) = theta(x) + d0 + d1 (x - 0.75)
Objective: payload change against the tricopter baseline (half-size motors, blade mass from volume), with penalties
for < 4 deg hover stall margin, T/W < 2 on the rotor's own half thrust at the tip-Mach RPM, and a tip chord under the minimum.

Speed: the full coaxial trim (about 20 s) is replaced inside the optimiser by an isolated rotor at T/2 times the pair's
interference ratio k = P_pair / (2 P_isolated), computed once for the starting blade. The winners are then re-run through
the full coaxial model, which also checks that k barely moves with the blade.

Hand check (blade-element theory, linear lift, uniform inflow): CT/sigma = (a/6)(theta_75 - 1.5 lambda), lambda = sqrt(CT/2),
theta_75 from the zero-lift line. At fixed thrust, a pitch change d theta_75 changes CT = T / (rho A (Omega R)^2), so it
predicts the hover RPM shift of the optimised blade, which is compared with the BEMT.
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
from phase2 import Rotor
from config_study import load_final_blade, coax_pair, mission_pack
import e01_coax_blade as e01
from common import RESULTS, load_catalog, save_json

OUT = os.path.join(RESULTS, "explore")


def blade_from(d, R, rh):
    return bemt.Blade(R, rh, 2, d["r"], d["chord"], np.radians(d["twist_deg"]), d["tc"])


def shape(b, x):
    d0, d1, e1, s = x
    xx = b.r_def / b.R
    return bemt.Blade(b.R, b.r_hub, b.N, b.r_def, s * b.c_def * (1 + e1 * (xx - 0.75)), b.th_def + d0 + d1 * (xx - 0.75), b.tc_def)


def context():
    G = e01.G; p, ph1, db, A = G["p"], G["ph1"], G["db"], G["A"]
    dkey = p["design_atmosphere"]; mis = p["mission"]
    bb = load_final_blade(p); base = Rotor("baseline", bb, db, p, A, ph1)
    bh, bc, be = base.hover(dkey), base.climb(dkey, mis["climb_rate_ms"]), base.cruise(dkey, mis["cruise_speed_ms"])
    cat = load_catalog(); m = p["config_study"]["masses"]
    mot, esc = cat["motors"]["tmotor_u15xl_kv38"]["mass_kg"], cat["escs"]["tmotor_thunder_300a_24s"]["mass_kg"]
    return {"alpha": be["alpha_shaft"], "t_tot": 3 * be["T"], "base_hover": 3 * bh["P"], "base_climb": 3 * bc["P"],
            "p_ind_one_disk": be["T"] * be["lam0"] * be["rpm"] * 2 * math.pi / 60 * bb.R,
            "base_pack": mission_pack(p, ph1, 3 * bh["P"], 3 * bc["P"], be["shaft_total"])[0],
            "vol0": 1e6 * do.blade_volume(bb), "bkg": ph1["mass_budget"]["blade_kg"], "hub": p["mass"]["hub_hardware_kg_per_rotor"],
            "arm_single": mot + esc + 2 * ph1["mass_budget"]["blade_kg"] + p["mass"]["hub_hardware_kg_per_rotor"],
            "motors_pair": 2 * (mot * m["coax_motor_mass_scale"] + esc * m["coax_esc_mass_scale"]), "tilt": m["tilt_servo_kg"]}


def payload(ctx, vol_cm3, pack, whkg):
    prop = 2 * ctx["bkg"] * vol_cm3 / ctx["vol0"] + ctx["hub"]
    hw = 3 * (ctx["motors_pair"] + 2 * prop - ctx["arm_single"]) - ctx["tilt"]
    return -(hw + (pack - ctx["base_pack"]) / whkg), hw


def fast_eval(b, ctx, k_pair):
    """Mission pack with the isolated-rotor surrogate for the pair's hover power."""
    G = e01.G; p, ph1, db, hot = G["p"], G["ph1"], G["db"], G["hot"]
    R = b.R; t_h = ph1["vehicle"]["weight_n"] / 3; V = p["mission"]["cruise_speed_ms"]
    iso = bemt.hover_at_thrust(b, db, hot, t_h / 2)
    e = bemt.edgewise_at_thrust(b, db, hot, ctx["t_tot"] / 6, V, ctx["alpha"], kappa=p["rotor"]["kappa"])
    om = e["rpm"] * 2 * math.pi / 60; p_ind_c = e["T"] * e["lam0"] * om * R
    lam = e["lam0"] + V * math.sin(ctx["alpha"]) / (om * R)
    d = min(0.4 * R * math.tan(math.atan2(e["mu"], lam)), 2 * R)
    f = (2 * R * R * math.acos(d / (2 * R)) - d / 2 * math.sqrt(4 * R * R - d * d)) / (math.pi * R * R)
    cruise = 6 * e["P"] + 3 * f * (ctx["p_ind_one_disk"] - 2 * p_ind_c)
    hover = 3 * k_pair * 2 * iso["P"]
    pack = mission_pack(p, ph1, hover, ctx["base_climb"] * hover / ctx["base_hover"], cruise)[0]
    rpm_mach = mt.rpm_from_vtip(p["rotor"]["tip_mach_max"] * hot["a"], 2 * R)
    tw = bemt.axial(b, db, hot, rpm_mach)["T"] / (t_h / 2)
    return {"pack": pack, "hover": hover, "cruise": cruise, "iso": iso, "tw": tw, "margin": do.stall_margin_deg(db, iso, R), "vol": 1e6 * do.blade_volume(b)}


def optimise(args):
    label, bd = args
    G = e01.G; p, ph1, db, hot = G["p"], G["ph1"], G["db"], G["hot"]
    t0 = time.time(); ctx = context(); whkg = p["mass"]["pack_wh_per_kg_cited"]
    R = p["rotor"]["diameter_in"] * p["constants"]["inch_to_m"] / 2
    b0 = blade_from(bd, R, p["rotor"]["hub_radius_m"])
    t_h = ph1["vehicle"]["weight_n"] / 3
    pair0 = coax_pair(b0, db, hot, t_h, 0.4 * R)
    iso0 = bemt.hover_at_thrust(b0, db, hot, t_h / 2)
    k_pair = pair0["P"] / (2 * iso0["P"])
    hist = []

    def obj(x):
        try:
            b = shape(b0, x)
            if float(np.min(b.c_def)) < p["design"]["chord_tip_min_m"] * 0.999: return 1e3
            r = fast_eval(b, ctx, k_pair)
            pl, _ = payload(ctx, r["vol"], r["pack"], whkg)
            pen = 5 * max(0.0, p["design"]["min_stall_margin_deg"] - r["margin"]) ** 2 + 200 * max(0.0, p["vehicle"]["tw_target"] - r["tw"]) ** 2
            hist.append((list(map(float, x)), pl, pen))
            return -pl + pen
        except Exception:
            return 1e3
    x0 = [0.0, 0.0, 0.0, 1.0]
    simplex = [x0, [math.radians(1), 0, 0, 1], [0, math.radians(3), 0, 1], [0, 0, 0.3, 1], [0, 0, 0, 0.85]]
    res = minimize(obj, x0, method="Nelder-Mead", options={"initial_simplex": simplex, "xatol": 2e-4, "fatol": 0.01, "maxfev": 160})
    out = {"label": label, "k_pair_start": k_pair, "x": {"twist_offset_deg": math.degrees(res.x[0]), "twist_slope_deg": math.degrees(res.x[1]),
                                                         "chord_taper": float(res.x[2]), "chord_scale": float(res.x[3])},
           "evaluations": int(res.nfev), "history": hist}
    for tag, b in (("start", b0), ("end", shape(b0, res.x))):
        r = fast_eval(b, ctx, k_pair)
        pair = coax_pair(b, db, hot, t_h, 0.4 * R)                                  # full model check of the surrogate
        hov_full = 3 * pair["P"]
        pack_full = mission_pack(p, ph1, hov_full, ctx["base_climb"] * hov_full / ctx["base_hover"], r["cruise"])[0]
        pl, hw = payload(ctx, r["vol"], pack_full, whkg)
        out[tag] = {"pack_fast": r["pack"], "pack_full": pack_full, "hover_full_w": hov_full, "hover_fast_w": r["hover"], "cruise_w": r["cruise"],
                    "k_pair": pair["P"] / (2 * r["iso"]["P"]), "iso_rpm": r["iso"]["rpm"], "tw": r["tw"], "margin": r["margin"], "vol_cm3": r["vol"],
                    "solidity": b.solidity(), "payload_kg": pl, "hardware_kg": hw,
                    "theta75_deg": math.degrees(float(np.interp(0.75 * R, b.r_def, b.th_def))),
                    "blade": {"r": b.r_def.tolist(), "chord": b.c_def.tolist(), "twist_deg": np.degrees(b.th_def).tolist()}}
    out["runtime_s"] = time.time() - t0
    print(f"  {label}: payload {out['start']['payload_kg']:+.2f} -> {out['end']['payload_kg']:+.2f} kg, pack {out['start']['pack_full']:.0f} -> {out['end']['pack_full']:.0f} Wh,"
          f" k {out['start']['k_pair']:.3f} -> {out['end']['k_pair']:.3f}, x {out['x']} [{out['runtime_s']:.0f}s]", flush=True)
    return out


def hand_rpm(theta75_old, theta75_new, rpm_old, sigma_old, sigma_new, T, rho, R, a=5.73, alpha0=math.radians(-4.0)):
    """Blade-element hover: CT/sigma = (a/6)(theta - 1.5 sqrt(CT/2)), theta from the zero-lift line. Solve CT, then RPM."""
    def ct(theta, sig):
        return brentq(lambda c: c / sig - (a / 6) * (theta - alpha0 - 1.5 * math.sqrt(c / 2)), 1e-6, 0.05)
    A = math.pi * R * R
    rpm = lambda c: math.sqrt(T / (rho * A * c)) / R * 60 / (2 * math.pi)
    c_old, c_new = ct(theta75_old, sigma_old), ct(theta75_new, sigma_new)
    return {"ct_old": c_old, "ct_new": c_new, "rpm_ratio_hand": rpm(c_new) / rpm(c_old), "rpm_old_hand": rpm(c_old)}


def run():
    t0 = time.time()
    e01.init()
    e1 = json.load(open(os.path.join(OUT, "e01_coax_blade.json")))
    p = e01.G["p"]; R = p["rotor"]["diameter_in"] * p["constants"]["inch_to_m"] / 2
    bb = load_final_blade(p)
    starts = [("Phase 2 blade", {"r": bb.r_def.tolist(), "chord": bb.c_def.tolist(), "twist_deg": np.degrees(bb.th_def).tolist(), "tc": bb.tc_def.tolist()})]
    starts += [(f"MIL {s['design_rpm']} rpm", s["blade"]) for s in e1["sweep"] if s.get("design_rpm") in (1450, 1750, 1900)]
    with Pool(4, initializer=e01.init) as pool:
        res = pool.map(optimise, starts)
    G = e01.G; hot = G["hot"]; t_h = G["ph1"]["vehicle"]["weight_n"] / 3
    for r in res:
        s, e = r["start"], r["end"]
        r["hand"] = hand_rpm(math.radians(s["theta75_deg"]), math.radians(e["theta75_deg"]), s["iso_rpm"], s["solidity"], e["solidity"], t_h / 2, hot["rho"], R)
        r["hand"]["rpm_ratio_bemt"] = e["iso_rpm"] / s["iso_rpm"]
    best = max(res, key=lambda r: r["end"]["payload_kg"])
    out = {"runs": res, "best": best["label"], "runtime_s": time.time() - t0}
    save_json(os.path.join("explore", "e02_coax_two_point.json"), out)
    plot(res)
    print(f"  best {best['label']}; wrote results/explore/e02_coax_two_point.json in {out['runtime_s']:.0f} s")


def plot(res):
    fig, axs = plt.subplots(1, 3, figsize=(12, 3.3))
    cols = ["#2a78d6", "#0b0b0b", "#c0392b", "#e08e0b"]
    for r, c in zip(res, cols):
        h = [q for q in r["history"] if q[2] < 1e-3]
        axs[0].plot(range(len(r["history"])), np.maximum.accumulate([q[1] - q[2] for q in r["history"]]), color=c, label=r["label"])
        for tag, ls in (("start", "--"), ("end", "-")):
            b = r[tag]["blade"]; x = np.array(b["r"]) / max(b["r"])
            axs[1].plot(x, 1000 * np.array(b["chord"]), color=c, ls=ls)
            axs[2].plot(x, b["twist_deg"], color=c, ls=ls)
    axs[0].set_xlabel("evaluation"); axs[0].set_ylabel("best payload change [kg]"); axs[0].legend(fontsize=6); axs[0].grid(alpha=.3)
    axs[1].set_xlabel("r / R"); axs[1].set_ylabel("chord [mm] (dashed start, solid end)"); axs[1].grid(alpha=.3)
    axs[2].set_xlabel("r / R"); axs[2].set_ylabel("twist [deg]"); axs[2].grid(alpha=.3)
    fig.suptitle("Exploration 02: two-point refinement of the coaxial blade (objective: payload, half-size motors)", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "e02_coax_two_point.png"), dpi=140); plt.close(fig)


if __name__ == "__main__":
    run()

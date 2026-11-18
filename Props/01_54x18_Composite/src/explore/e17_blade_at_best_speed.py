"""Exploration 17: tri and hex blades re-optimised for a cruise at their own best-range speed (motor in the objective).

Entry 16: every layout's best-range speed is 21-25 m/s, but its blade was optimised for 15 m/s. Here the cruise point
of the objective moves to each layout's entry-16 best speed (tri 24.7, hex 21.0 m/s), with the trim re-solved for each
blade (body CdA + rotor H-forces + arm force, as entry 16), and everything else as entries 11/13/14:
    hover (n isolated rotors, entry 14 download factor), motor ~ peak torque at T/W 2, ESC ~ P_max^0.7, spar blade mass,
    arms (entry 10) and fairing (entry 14 best option), tilt servo (tri)
After the optimisation the end blade's speed is swept again (entry 16 method) to find its new best-range speed.
The y6 is left out: it is 1 kg behind at every speed so far, and its coaxial surrogate (entry 12) was built at 15 m/s.

Payload between layouts: -(hw + pack / whkg) differences in the common entry 10 frame (both sides use the same parts list).
Constraints: hover stall margin, T/W 2 below the tip-Mach rpm, flex test, chord floor, cruise max section angle <= 11 deg.

Hand check: with the cruise point now at the speed where (P + P_av)/V is flat, the blade trade between hover and cruise is
weighted by time: hover-like segments (take-off, climb, descent, delivery, landing) against cruise = range / V. Printed.
"""
import json, math, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from multiprocessing import Pool
from scipy.optimize import minimize
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import bemt, design_opt as do, momentum as mt
import mission as ms
from blade_structure import blade_mass
import e01_coax_blade as e01
import e02_coax_two_point as e02
import e10_motor_mass as e10
from e11_blade_with_motor import motor_fit
from e16_cruise_speed import VehV, arm_force_per_q, blades
from common import RESULTS, save_json

OUT = os.path.join(RESULTS, "explore")
N = {"tri": 3, "hex0": 6}
SWEEP = np.arange(-5.0, 5.01, 1.0)


def setup(c):
    G = e01.G; p = G["p"]
    e9 = json.load(open(os.path.join(OUT, "e09_hex_vs_y6.json"))); e10r = json.load(open(os.path.join(OUT, "e10_motor_mass.json")))
    e14 = json.load(open(os.path.join(OUT, "e14_faired_arms.json"))); e16 = json.load(open(os.path.join(OUT, "e16_cruise_speed.json")))
    C = e14["configs"][c]; row = C["rows"][e14["best_option"][c]["option"]]
    f_arm, _ = arm_force_per_q(c)
    return {"ctx": e02.context(), "n": N[c], "V": e16["layouts"][c]["v_best"], "f_arm": f_arm, "inter15": e9["configs"][c]["interference_w"],
            "dl_factor": row["hover_w"] / C["start"]["hover"], "fair_kg": row["fairing_kg"], "arms_kg": e10r["configs"][c]["arms_kg"],
            "tilt": e02.context()["tilt"] if c == "tri" else 0.0, "P_max_tri": e10r["required"]["tri"]["P_max"], "fit": motor_fit()}


def cruise(b, S, V):
    G = e01.G; p, ph1, db, hot = G["p"], G["ph1"], G["db"], G["hot"]; W = ph1["vehicle"]["weight_n"]; n = S["n"]
    q = 0.5 * hot["rho"] * V * V; h = 0.0
    for _ in range(5):
        drag = q * (p["vehicle"]["cda_m2"] + S["f_arm"]) + n * h
        al, t_tot = math.atan2(drag, W), math.hypot(W, drag)
        e = bemt.edgewise_at_thrust(b, db, hot, t_tot / n, V, al, kappa=p["rotor"]["kappa"]); h = e["H"]
    return n * e["P"] + S["inter15"] * 15.0 / V, e


def evaluate(b, S, V=None):
    G = e01.G; p, ph1, db, hot = G["p"], G["ph1"], G["db"], G["hot"]
    W = ph1["vehicle"]["weight_n"]; tw = p["vehicle"]["tw_target"]; n = S["n"]; ctx = S["ctx"]; V = V or S["V"]
    iso = bemt.hover_at_thrust(b, db, hot, W / n); mx = bemt.hover_at_thrust(b, db, hot, tw * W / n)
    hover = n * iso["P"] * S["dl_factor"]; P_cr, e = cruise(b, S, V)
    m = ms.mission_energy(VehV(p, hover, ctx["base_climb"] * hover / ctx["base_hover"], lambda v: P_cr), p["mission"], ph1["vehicle"]["range_m"], V)
    a, nn = S["fit"]; motor = a * mx["Q"] ** nn; esc = e10.ESC_KG * (mx["P"] / S["P_max_tri"]) ** e10.ESC_EXP
    ms_ = blade_mass(b.r_def, b.c_def, b.tc_def, b.r_hub, b.R)
    hw = n * (motor + esc + 2 * ms_["total_kg"] + ctx["hub"]) + S["tilt"] + S["arms_kg"] + S["fair_kg"]
    rpm_mach = mt.rpm_from_vtip(p["rotor"]["tip_mach_max"] * hot["a"], 2 * b.R)
    return {"V": V, "pack": m["pack_wh"], "mass_sum": hw + m["pack_wh"] / p["mass"]["pack_wh_per_kg_cited"], "hw": hw, "hover": hover, "cruise": P_cr,
            "motor_kg": motor, "esc_kg": esc, "blade_kg": ms_["total_kg"], "defl_mm": ms_["tip_deflection_mm"], "Q_max": mx["Q"],
            "rpm_hover": iso["rpm"], "rpm_cruise": e["rpm"], "rpm_max": mx["rpm"], "tw_mach": bemt.axial(b, db, hot, rpm_mach)["T"] / (W / n),
            "tip_mach_max": p["rotor"]["tip_mach_max"] * mx["rpm"] / rpm_mach, "margin": do.stall_margin_deg(db, iso, b.R),
            "alpha_max_cruise": e["alpha_max_deg"], "tip_mach_adv": e["tip_mach_adv"], "solidity": b.solidity(),
            "hover_time_share": m["hover_time_share"], "hover_energy_share": m["hover_energy_share"]}


def optimise(c):
    t0 = time.time(); G = e01.G; p = G["p"]; S = setup(c); b0 = blades()[c]
    r0 = evaluate(b0, S); r15 = evaluate(b0, S, 15.0); hist = []

    def obj(x):
        try:
            b = e02.shape(b0, x)
            if float(np.min(b.c_def)) < p["design"]["chord_tip_min_m"] * 0.999: return 1e3
            r = evaluate(b, S)
            pen = 5 * max(0.0, p["design"]["min_stall_margin_deg"] - r["margin"]) ** 2 + 200 * max(0.0, p["vehicle"]["tw_target"] - r["tw_mach"]) ** 2
            pen += 50 * max(0.0, r["defl_mm"] / 1.2 - 1.0) + 5 * max(0.0, r["alpha_max_cruise"] - 11.0) ** 2
            hist.append((list(map(float, x)), r["mass_sum"], pen)); return r["mass_sum"] + pen
        except Exception:
            return 1e3
    x0 = [0.0, 0.0, 0.0, 1.0]
    simplex = [x0, [math.radians(1), 0, 0, 1], [0, math.radians(3), 0, 1], [0, 0, 0.3, 1], [0, 0, 0, 0.85]]
    res = minimize(obj, x0, method="Nelder-Mead", options={"initial_simplex": simplex, "xatol": 2e-4, "fatol": 0.005, "maxfev": 160})
    b1 = e02.shape(b0, res.x); r1 = evaluate(b1, S)
    sweep = [evaluate(b1, S, S["V"] + dv) for dv in SWEEP]
    sweep0 = [evaluate(b0, S, S["V"] + dv) for dv in SWEEP]
    out = {"layout": c, "V_design": S["V"], "x": list(map(float, res.x)), "evaluations": int(res.nfev), "start": r0, "start_at_15": r15, "end": r1,
           "sweep_end": sweep, "sweep_start": sweep0, "history": hist, "runtime_s": time.time() - t0,
           "blade": {"r": b1.r_def.tolist(), "chord": b1.c_def.tolist(), "twist_deg": np.degrees(b1.th_def).tolist(), "tc": b1.tc_def.tolist()}}
    best = min(sweep, key=lambda r: r["mass_sum"]); best0 = min(sweep0, key=lambda r: r["mass_sum"])
    print(f"  {c}: V {S['V']:.1f}: mass_sum {r0['mass_sum']:.2f} -> {r1['mass_sum']:.2f} kg, pack {r0['pack']:.0f} -> {r1['pack']:.0f} Wh, rpm_h {r0['rpm_hover']:.0f} -> {r1['rpm_hover']:.0f},"
          f" rpm_cr {r0['rpm_cruise']:.0f} -> {r1['rpm_cruise']:.0f}, sigma {r0['solidity']:.3f} -> {r1['solidity']:.3f}, motor {r0['motor_kg']:.2f} -> {r1['motor_kg']:.2f},"
          f" tipM {r1['tip_mach_max']:.3f}, a_max_cr {r1['alpha_max_cruise']:.1f}; re-swept best V {best['V']:.1f} (start blade {best0['V']:.1f}) [{out['runtime_s']:.0f}s]", flush=True)
    return out


def run():
    t0 = time.time(); e01.init()
    with Pool(2, initializer=e01.init) as pool:
        runs = pool.map(optimise, list(N))
    R = {r["layout"]: r for r in runs}; whkg = e01.G["p"]["mass"]["pack_wh_per_kg_cited"]
    bestm = lambda sw: min(sw, key=lambda r: r["mass_sum"])
    rank = {"start_blades_own_speed": R["tri"]["start"]["mass_sum"] - R["hex0"]["start"]["mass_sum"],
            "start_blades_15": R["tri"]["start_at_15"]["mass_sum"] - R["hex0"]["start_at_15"]["mass_sum"],
            "reopt_blades_own_speed": bestm(R["tri"]["sweep_end"])["mass_sum"] - bestm(R["hex0"]["sweep_end"])["mass_sum"],
            "pack_tri": bestm(R["tri"]["sweep_end"])["pack"], "pack_hex": bestm(R["hex0"]["sweep_end"])["pack"]}
    out = {"runs": runs, "hex_payload_vs_tri_kg": rank, "runtime_s": time.time() - t0}
    print(f"  hex payload vs tri (= tri mass_sum - hex mass_sum): {rank}")
    save_json(os.path.join("explore", "e17_blade_at_best_speed.json"), out); plot(out)


def plot(o):
    fig, axs = plt.subplots(1, 3, figsize=(12, 3.3)); col = {"tri": "#0b0b0b", "hex0": "#2a78d6"}
    for r in o["runs"]:
        c = r["layout"]; b = r["blade"]; x = np.array(b["r"]) / max(b["r"])
        axs[0].plot(x, 1000 * np.array(b["chord"]), color=col[c], label=f"{c} at {r['V_design']:.1f} m/s")
        axs[1].plot(x, b["twist_deg"], color=col[c], label=c)
        axs[2].plot([s["V"] for s in r["sweep_start"]], [s["mass_sum"] for s in r["sweep_start"]], "--", color=col[c], label=f"{c} 15 m/s blade")
        axs[2].plot([s["V"] for s in r["sweep_end"]], [s["mass_sum"] for s in r["sweep_end"]], "o-", color=col[c], label=f"{c} re-optimised")
    axs[0].set_xlabel("r / R"); axs[0].set_ylabel("chord [mm]"); axs[0].legend(fontsize=6); axs[0].grid(alpha=.3)
    axs[1].set_xlabel("r / R"); axs[1].set_ylabel("twist [deg]"); axs[1].grid(alpha=.3)
    axs[2].set_xlabel("cruise speed [m/s]"); axs[2].set_ylabel("hardware + battery [kg]"); axs[2].legend(fontsize=6); axs[2].grid(alpha=.3)
    fig.suptitle("Exploration 17: blades re-optimised at each layout's best-range speed", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "e17_blade_at_best_speed.png"), dpi=140); plt.close(fig)


if __name__ == "__main__":
    if sys.argv[1:] == ["plot"]:
        plot(json.load(open(os.path.join(OUT, "e17_blade_at_best_speed.json"))))
    else:
        run()

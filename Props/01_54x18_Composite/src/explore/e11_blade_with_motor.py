"""Exploration 11: re-optimise the hexacopter blade with the motor in the objective.

Entry 10: motor mass ~ peak torque (m = a tau^0.996, about 11 N m/kg). A slow, wide blade saves energy but needs torque,
because Q = P / Omega. Entries 02-03 optimised without that term. Here the planar hex (entry 09/10's leading layout) is
optimised for payload against the tricopter with everything that the blade changes:
    pack energy (6 isolated rotors in hover, edgewise cruise, entry 09's interference and arm drag),
    blade mass (spar model, 50 N / 1.2 mm), motor mass from the peak torque at T/W 2 (entry 10 fit),
    ESC mass from the peak power (entry 10)
Variables as in entries 02-03: twist offset, twist slope, chord taper, chord scale (Nelder-Mead).
Two objectives from two starts (entry 03's blade, entry 01's MIL 1750 rpm blade):
    'motor'  - motor and ESC mass follow the blade (the new model)
    'fixed'  - motor and ESC mass frozen at the start blade's values (what entries 02-03 effectively assumed)
Constraints (penalties): stall margin, T/W >= 2 reachable below the tip-Mach RPM, blade flex feasibility.

Hand check: at the optimum, the marginal payload of a small RPM change is zero. With Q_max = 2 P_h / Omega_h (entry 10)
and m_motor = c Q_max (c = 1/11 kg per N m), the motor term per rotor is d m / d Omega = -2 c P_h / Omega^2, while the
energy term is (d pack / d P_h) (d P_h / d Omega) / whkg. Printed at the optimum to show the two balance.
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
from config_study import mission_pack
from blade_structure import blade_mass
import e01_coax_blade as e01
import e02_coax_two_point as e02
from e06_coax_spacing import blade_e03
import e10_motor_mass as e10
from common import RESULTS, save_json

OUT = os.path.join(RESULTS, "explore")


def motor_fit():
    tau = np.array([m[2] for m in e10.MOTORS]); mass = np.array([m[1] for m in e10.MOTORS])
    n, lna = np.polyfit(np.log(tau), np.log(mass), 1); return math.exp(lna), n


def setup():
    G = e01.G; p, ph1 = G["p"], G["ph1"]
    e9 = json.load(open(os.path.join(OUT, "e09_hex_vs_y6.json"))); e10r = json.load(open(os.path.join(OUT, "e10_motor_mass.json")))
    return {"ctx": e02.context(), "inter_w": e9["configs"]["hex0"]["interference_w"], "arm_drag_w": e9["configs"]["hex0"]["arm_drag_w"],
            "arms_kg": e10r["configs"]["hex0"]["arms_kg"], "hw_tri": e10r["configs"]["tri"]["hardware_kg"], "pack_tri": e9["configs"]["tri"]["pack_wh"],
            "P_max_tri": e10r["required"]["tri"]["P_max"], "fit": motor_fit()}


def evaluate(b, S, frozen=None):
    G = e01.G; p, ph1, db, hot = G["p"], G["ph1"], G["db"], G["hot"]
    W = ph1["vehicle"]["weight_n"]; tw = p["vehicle"]["tw_target"]; V = p["mission"]["cruise_speed_ms"]; ctx = S["ctx"]
    iso = bemt.hover_at_thrust(b, db, hot, W / 6); mx = bemt.hover_at_thrust(b, db, hot, tw * W / 6)
    e = bemt.edgewise_at_thrust(b, db, hot, ctx["t_tot"] / 6, V, ctx["alpha"], kappa=p["rotor"]["kappa"])
    hover = 6 * iso["P"]; cruise = 6 * e["P"] + S["inter_w"] + S["arm_drag_w"]
    pack = mission_pack(p, ph1, hover, ctx["base_climb"] * hover / ctx["base_hover"], cruise)[0]
    a, n = S["fit"]
    motor = a * mx["Q"] ** n; esc = e10.ESC_KG * (mx["P"] / S["P_max_tri"]) ** e10.ESC_EXP
    if frozen: motor, esc = frozen
    ms = blade_mass(b.r_def, b.c_def, b.tc_def, b.r_hub, b.R)
    hw = 6 * (motor + esc + 2 * ms["total_kg"] + ctx["hub"]) + S["arms_kg"]
    payload = -(hw - S["hw_tri"] + (pack - S["pack_tri"]) / p["mass"]["pack_wh_per_kg_cited"])
    rpm_mach = mt.rpm_from_vtip(p["rotor"]["tip_mach_max"] * hot["a"], 2 * b.R)
    tw_mach = bemt.axial(b, db, hot, rpm_mach)["T"] / (W / 6)
    return {"payload": payload, "pack": pack, "hover": hover, "cruise": cruise, "hw": hw, "motor_kg": motor, "esc_kg": esc, "blade_kg": ms["total_kg"],
            "defl_mm": ms["tip_deflection_mm"], "feasible": ms["feasible"], "Q_max": mx["Q"], "P_max": mx["P"], "rpm_hover": iso["rpm"], "rpm_max": mx["rpm"],
            "P_hover_rotor": iso["P"], "tw_mach": tw_mach, "margin": do.stall_margin_deg(db, iso, b.R), "solidity": b.solidity()}


def optimise(args):
    label, bd, mode = args
    t0 = time.time(); G = e01.G; p = G["p"]; S = setup()
    R = p["rotor"]["diameter_in"] * p["constants"]["inch_to_m"] / 2
    b0 = e02.blade_from(bd, R, p["rotor"]["hub_radius_m"])
    r0 = evaluate(b0, S); frozen = (r0["motor_kg"], r0["esc_kg"]) if mode == "fixed" else None
    hist = []

    def obj(x):
        try:
            b = e02.shape(b0, x)
            if float(np.min(b.c_def)) < p["design"]["chord_tip_min_m"] * 0.999: return 1e3
            r = evaluate(b, S, frozen)
            pen = 5 * max(0.0, p["design"]["min_stall_margin_deg"] - r["margin"]) ** 2 + 200 * max(0.0, p["vehicle"]["tw_target"] - r["tw_mach"]) ** 2
            pen += 50 * max(0.0, r["defl_mm"] / 1.2 - 1.0)
            hist.append((list(map(float, x)), r["payload"], pen)); return -r["payload"] + pen
        except Exception:
            return 1e3
    x0 = [0.0, 0.0, 0.0, 1.0]
    simplex = [x0, [math.radians(1), 0, 0, 1], [0, math.radians(3), 0, 1], [0, 0, 0.3, 1], [0, 0, 0, 0.85]]
    res = minimize(obj, x0, method="Nelder-Mead", options={"initial_simplex": simplex, "xatol": 2e-4, "fatol": 0.005, "maxfev": 180})
    b1 = e02.shape(b0, res.x)
    end_true = evaluate(b1, S)                  # always re-scored with the motor following the blade
    out = {"label": label, "mode": mode, "x": list(map(float, res.x)), "evaluations": int(res.nfev), "start": r0, "end": end_true,
           "end_as_optimised": evaluate(b1, S, frozen), "history": hist,
           "blade": {"r": b1.r_def.tolist(), "chord": b1.c_def.tolist(), "twist_deg": np.degrees(b1.th_def).tolist(), "tc": b1.tc_def.tolist()},
           "runtime_s": time.time() - t0}
    print(f"  {label} [{mode}]: payload {r0['payload']:+.2f} -> {end_true['payload']:+.2f} kg (true), pack {r0['pack']:.0f} -> {end_true['pack']:.0f} Wh,"
          f" rpm_h {r0['rpm_hover']:.0f} -> {end_true['rpm_hover']:.0f}, sigma {r0['solidity']:.3f} -> {end_true['solidity']:.3f}, motor {r0['motor_kg']:.2f} -> {end_true['motor_kg']:.2f} kg,"
          f" blade {r0['blade_kg']:.3f} -> {end_true['blade_kg']:.3f} kg [{out['runtime_s']:.0f}s]", flush=True)
    return out


def run():
    t0 = time.time(); e01.init(); p = e01.G["p"]
    b3 = blade_e03(p)
    e1 = json.load(open(os.path.join(OUT, "e01_coax_blade.json")))
    mil = next(s["blade"] for s in e1["sweep"] if s.get("design_rpm") == 1750)
    starts = [("e03 blade", {"r": b3.r_def.tolist(), "chord": b3.c_def.tolist(), "twist_deg": np.degrees(b3.th_def).tolist(), "tc": b3.tc_def.tolist()}), ("MIL 1750 rpm", mil)]
    jobs = [(l, bd, m) for l, bd in starts for m in ("motor", "fixed")]
    with Pool(4, initializer=e01.init) as pool:
        runs = pool.map(optimise, jobs)
    # hand check at the best 'motor' optimum
    best = max((r for r in runs if r["mode"] == "motor"), key=lambda r: r["end"]["payload"])
    S = setup(); a, n = S["fit"]; e = best["end"]; whkg = p["mass"]["pack_wh_per_kg_cited"]
    om = e["rpm_hover"] * 2 * math.pi / 60
    # finite differences of pack and power against a uniform chord scale (moves the hover RPM at fixed thrust)
    R = p["rotor"]["diameter_in"] * p["constants"]["inch_to_m"] / 2
    bb = e02.blade_from(best["blade"], R, p["rotor"]["hub_radius_m"])
    lo, hi = evaluate(e02.shape(bb, [0, 0, 0, 0.97]), S), evaluate(e02.shape(bb, [0, 0, 0, 1.03]), S)
    d_om = (hi["rpm_hover"] - lo["rpm_hover"]) * 2 * math.pi / 60
    hc = {"c_kg_per_Nm": a * n * e["Q_max"] ** (n - 1), "Q_max_hand_2P_over_Omega": 2 * e["P_hover_rotor"] / om, "Q_max_bemt": e["Q_max"],
          "dmotor_dOmega_hand_kg_per_rad_s": -6 * a * n * e["Q_max"] ** (n - 1) * 2 * e["P_hover_rotor"] / om ** 2,
          "dmotor_dOmega_fd": 6 * (hi["motor_kg"] - lo["motor_kg"]) / d_om, "dbattery_dOmega_fd": (hi["pack"] - lo["pack"]) / whkg / d_om,
          "dblade_dOmega_fd": 12 * (hi["blade_kg"] - lo["blade_kg"]) / d_om, "dpayload_dOmega_fd": (hi["payload"] - lo["payload"]) / d_om}
    out = {"runs": runs, "best": f"{best['label']} [motor]", "hand_check": hc, "runtime_s": time.time() - t0}
    save_json(os.path.join("explore", "e11_blade_with_motor.json"), out)
    plot(out)
    print(f"  hand check: {hc}\n  wrote results/explore/e11_blade_with_motor.json in {out['runtime_s']:.0f} s")


def plot(o):
    fig, axs = plt.subplots(1, 3, figsize=(12, 3.3)); col = {"motor": "#0b0b0b", "fixed": "#2a78d6"}; ls = {"e03 blade": "-", "MIL 1750 rpm": "--"}
    for r in o["runs"]:
        b = r["blade"]; x = np.array(b["r"]) / max(b["r"])
        lab = f"{r['label']} [{r['mode']}]"
        axs[0].plot(x, 1000 * np.array(b["chord"]), color=col[r["mode"]], ls=ls[r["label"]], label=lab)
        axs[1].plot(x, b["twist_deg"], color=col[r["mode"]], ls=ls[r["label"]], label=lab)
        h = np.array([q[1] - q[2] for q in r["history"]]); axs[2].plot(np.maximum.accumulate(h), color=col[r["mode"]], ls=ls[r["label"]], label=lab)
    axs[0].set_xlabel("r / R"); axs[0].set_ylabel("chord [mm]"); axs[0].legend(fontsize=6); axs[0].grid(alpha=.3)
    axs[1].set_xlabel("r / R"); axs[1].set_ylabel("twist [deg]"); axs[1].grid(alpha=.3)
    axs[2].set_xlabel("evaluation"); axs[2].set_ylabel("best objective (payload - penalty) [kg]"); axs[2].set_ylim(-3, 5); axs[2].grid(alpha=.3)
    fig.suptitle("Exploration 11: hexacopter blade optimised with torque-sized motors (black) vs motors frozen (blue)", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "e11_blade_with_motor.png"), dpi=140); plt.close(fig)


if __name__ == "__main__":
    if sys.argv[1:] == ["plot"]:
        plot(json.load(open(os.path.join(OUT, "e11_blade_with_motor.json"))))
    else:
        run()

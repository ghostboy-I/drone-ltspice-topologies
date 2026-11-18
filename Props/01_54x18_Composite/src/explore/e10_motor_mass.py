"""Exploration 10: motor and arm-fitting masses from catalogue data, then entry 09 re-scored.

Entries 01-09 used 'half-size motor = 0.5 x U15XL x 1.15' and 0.6 kg per arm fitting. Here:

MOTORS: what sizes a motor is the peak shaft torque it must deliver (torque ~ rotor volume x magnetic shear stress), so
motor mass is fitted against the 100 %-throttle torque in the vendor test tables (T-Motor, accessed 2026-11-18):
    U13II KV65   0.975 kg   11.4 N m at 4397 rpm (G32x11, 98 V)      store.tmotor.com/product/u13-v2-kv65-motor-u-power.html
    U15II KV80   1.740 kg   18.0 N m at 3546 rpm (G40x13.1, 60 V)    store.tmotor.com/goods.php?id=732
    U15XL KV38   4.408 kg   50.4 N m at 2910 rpm (52x20, 96 V)       ligpower.com/product/u15xl-manned-aircraft-combo.html
  Check of each row: shaft power tau omega against electrical power V I gives 78 %, 78 % and 91 % efficiency.
  Fit m = a tau^n (least squares in log-log). Caveat: the U15II row is at 60 V, below its 24S limit, so its torque is a
  test point, not a ceiling.
  Required torque per rotor: BEMT hover trim at T/W = 2 (hot day), i.e. thrust 2 x T_rotor; for the y6 the full coaxial
  model at twice the arm thrust (equal torque, so both motors see the same torque).
ESC: mass scales with peak current at the same voltage, i.e. with peak electrical power: m_esc = 0.870 kg x (P / P_tri)^0.7
  (assumption: no catalogue series, exponent from 'fixed overhead plus copper').
FITTINGS per arm: folding joint + motor mount + root clamp. Joint mass from retail listings of folding carbon-tube joints
  (RJXHobby: 257 g at 40 mm, 334 g at 50 mm), scaled with d^2 to the tube diameter from entry 09; motor mount 0.2 kg per
  full-size motor (0.12 kg for a half-size one); root clamp 0.10 kg.

Hand check: for a fixed-pitch rotor T and Q both scale with Omega^2 (constant C_T, C_Q), so Q is proportional to T:
    Q_max = (T_max / T_hover) Q_hover = 2 Q_hover,   Q_hover = P_hover / Omega_hover
"""
import json, math, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import bemt
from config_study import load_final_blade
from blade_structure import blade_mass
import e01_coax_blade as e01
import e02_coax_two_point as e02
from e05_diameter_split import coax_split
from e06_coax_spacing import blade_e03
from common import RESULTS, save_json

OUT = os.path.join(RESULTS, "explore")
MOTORS = [("U13II KV65", 0.975, 11.4, 4397, 98.22, 68.5), ("U15II KV80", 1.740, 18.0, 3546, 60.0, 143.0), ("U15XL KV38", 4.408, 50.4, 2910, 96.0, 175.08)]
ESC_KG, ESC_EXP = 0.870, 0.7
JOINT_50MM_KG, MOUNT_FULL, MOUNT_HALF, CLAMP = 0.334, 0.20, 0.12, 0.10


def run():
    t0 = time.time()
    e01.init(); G = e01.G; p, ph1, db, hot = G["p"], G["ph1"], G["db"], G["hot"]
    ctx = e02.context(); whkg = p["mass"]["pack_wh_per_kg_cited"]; W = ph1["vehicle"]["weight_n"]; tw = p["vehicle"]["tw_target"]
    # ---- motor fit ----
    tau = np.array([m[2] for m in MOTORS]); mass = np.array([m[1] for m in MOTORS])
    n, lna = np.polyfit(np.log(tau), np.log(mass), 1); a = math.exp(lna)
    fit = lambda t: a * t ** n
    eff = [m[2] * m[3] * 2 * math.pi / 60 / (m[4] * m[5]) for m in MOTORS]
    for m, e in zip(MOTORS, eff): print(f"  {m[0]}: {m[1]} kg, {m[2]} N m -> {m[2]/m[1]:.1f} N m/kg, eta {e:.2f}, fit {fit(m[2]):.3f} kg")
    print(f"  fit: m = {a:.4f} tau^{n:.3f}")
    # ---- required torque ----
    bb = load_final_blade(p); b3 = blade_e03(p)
    tri_h = bemt.hover_at_thrust(bb, db, hot, W / 3); tri_m = bemt.hover_at_thrust(bb, db, hot, tw * W / 3)
    six_h = bemt.hover_at_thrust(b3, db, hot, W / 6); six_m = bemt.hover_at_thrust(b3, db, hot, tw * W / 6)
    y6_m = coax_split(b3, b3, db, hot, tw * W / 3, 0.4 * 2 * b3.R)
    req = {"tri": {"Q_max": tri_m["Q"], "P_max": tri_m["P"], "rpm_max": tri_m["rpm"], "Q_hover": tri_h["Q"], "rpm_hover": tri_h["rpm"], "tip_mach_max": tri_m["tip_mach"]},
           "hex": {"Q_max": six_m["Q"], "P_max": six_m["P"], "rpm_max": six_m["rpm"], "Q_hover": six_h["Q"], "rpm_hover": six_h["rpm"], "tip_mach_max": six_m["tip_mach"]},
           "y6": {"Q_max": y6_m["upper"]["Q"], "P_max": max(y6_m["upper"]["P"], y6_m["lower"]["P"]), "rpm_max": y6_m["upper"]["rpm"], "rpm_lower_max": y6_m["lower"]["rpm"]}}
    for k, r in req.items():
        r["motor_kg_fit"] = fit(r["Q_max"]); r["esc_kg"] = ESC_KG * (r["P_max"] / req["tri"]["P_max"]) ** ESC_EXP
        if "Q_hover" in r: r["hand_Q_max_2Qh"] = 2 * r["Q_hover"]
        print(f"  {k}: Q_max {r['Q_max']:.1f} N m at {r['rpm_max']:.0f} rpm, P_max {r['P_max']:.0f} W -> motor {r['motor_kg_fit']:.3f} kg, ESC {r['esc_kg']:.3f} kg"
              + (f"; hand 2 Q_hover = {r['hand_Q_max_2Qh']:.1f} N m" if "Q_hover" in r else ""), flush=True)
    # ---- fittings ----
    e9 = json.load(open(os.path.join(OUT, "e09_hex_vs_y6.json")))
    joint = lambda d_mm: JOINT_50MM_KG * (d_mm / 50.0) ** 2
    fit_tri = joint(e9["arm_tri"]["d_mm"]) + MOUNT_FULL + CLAMP
    fit_six_arm_y6 = joint(e9["arm_tri"]["d_mm"]) + 2 * MOUNT_HALF + CLAMP           # y6 arm carries two half-size motors
    fit_hex = joint(e9["arm_hex"]["d_mm"]) + MOUNT_HALF + CLAMP
    # ---- re-score entry 09 ----
    mb3 = blade_mass(b3.r_def, b3.c_def, b3.tc_def, b3.r_hub, b3.R)["total_kg"]
    tri_rotor = req["tri"]["motor_kg_fit"] + req["tri"]["esc_kg"] + 2 * ctx["bkg"] + ctx["hub"]
    six_rotor = lambda k: req[k]["motor_kg_fit"] + req[k]["esc_kg"] + 2 * mb3 + ctx["hub"]
    arms = {"tri": 3 * (e9["arm_tri"]["tube_kg"] + fit_tri), "y6": 3 * (e9["arm_tri"]["tube_kg"] + fit_six_arm_y6),
            "hex0": 6 * (e9["arm_hex"]["tube_kg"] + fit_hex), "hex30": 6 * (e9["arm_hex"]["tube_kg"] + fit_hex)}
    hw = {"tri": 3 * tri_rotor + ctx["tilt"] + arms["tri"], "y6": 6 * six_rotor("y6") + arms["y6"] + 3 * 0.51 * 0.4 * 2 * b3.R,
          "hex0": 6 * six_rotor("hex") + arms["hex0"], "hex30": 6 * six_rotor("hex") + arms["hex30"]}
    rows = {}
    for c, r9 in e9["configs"].items():
        rows[c] = {"pack_wh": r9["pack_wh"], "hardware_kg": hw[c], "hardware_vs_tri_kg": hw[c] - hw["tri"],
                   "payload_vs_tri_kg": -(hw[c] - hw["tri"] + (r9["pack_wh"] - e9["configs"]["tri"]["pack_wh"]) / whkg),
                   "payload_vs_tri_kg_e09": r9["payload_vs_tri_kg"] - e9["configs"]["tri"]["payload_vs_tri_kg"], "arms_kg": arms[c]}
        print(f"  {c:5s}: hardware {hw[c]:.2f} kg ({rows[c]['hardware_vs_tri_kg']:+.2f}), pack {r9['pack_wh']:.0f} Wh, payload vs tri {rows[c]['payload_vs_tri_kg']:+.2f} kg"
              f" (entry 09: {rows[c]['payload_vs_tri_kg_e09']:+.2f})", flush=True)
    # sensitivity: motor exponent from the two T-Motor U15 points only, and from the U13-U15XL pair
    sens = {}
    for name, (i, j) in {"U15II-U15XL": (1, 2), "U13II-U15XL": (0, 2)}.items():
        nn = math.log(mass[j] / mass[i]) / math.log(tau[j] / tau[i]); f2 = lambda t: mass[j] * (t / tau[j]) ** nn
        dm = 6 * (f2(req["hex"]["Q_max"]) - req["hex"]["motor_kg_fit"]) - 3 * (f2(req["tri"]["Q_max"]) - req["tri"]["motor_kg_fit"])
        sens[name] = {"n": nn, "hex_payload_shift_kg": -dm}
    out = {"motors": [dict(zip(("name", "kg", "tau_nm", "rpm", "volts", "amps"), m), eta=e) for m, e in zip(MOTORS, eff)],
           "fit": {"a": a, "n": n}, "required": req, "fittings": {"tri": fit_tri, "y6_arm": fit_six_arm_y6, "hex": fit_hex},
           "configs": rows, "sensitivity_motor_fit": sens, "runtime_s": time.time() - t0}
    print(f"  fittings: tri {fit_tri:.3f}, y6 arm {fit_six_arm_y6:.3f}, hex {fit_hex:.3f} kg; motor-fit sensitivity {sens}")
    save_json(os.path.join("explore", "e10_motor_mass.json"), out)
    print(f"  wrote results/explore/e10_motor_mass.json in {out['runtime_s']:.0f} s")


if __name__ == "__main__":
    run()

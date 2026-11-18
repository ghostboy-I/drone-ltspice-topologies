"""Exploration 01: a blade designed for the coaxial pair (half the arm thrust per rotor) instead of the Phase 2 blade at half load.

Each design RPM gets the Phase 2 hover design procedure (minimum-induced-loss blade at cl_design, chord cap, root shank,
re-twist) for T_arm / 2 isolated, then is evaluated as a coaxial pair at h = 0.2 D with the config-study models: vortex-
cylinder BEMT in hover (equal torque), and the wake-overlap estimate in cruise. Selection rule as in Phase 2: lowest mission
pack energy among designs with >= 4 deg hover stall margin that reach T/W 2 on their own half thrust inside the tip-Mach limit.

Hand check (MIL scaling). For a hover-optimal blade, blade loading CT / sigma = cl_mean / 6 (blade-element theory with uniform
inflow), so at a fixed RPM and design cl the solidity scales with thrust: halving thrust should halve the blade area.
"""
import json, math, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import numpy as np
from multiprocessing import Pool
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import airfoils, bemt, design_opt as do, atmosphere as atm, momentum as mt
from phase2 import Rotor
from config_study import load_final_blade, coax_pair, mission_pack
from common import RESULTS, load_params, load_catalog, save_json

OUT = os.path.join(RESULTS, "explore"); os.makedirs(OUT, exist_ok=True)
G = {}


def init():
    p = load_params(); ph1 = json.load(open(os.path.join(RESULTS, "phase1.json")))
    db, _ = airfoils.build_db(p, n_proc=1)
    A = {k: atm.state(v["temp_c"], v["alt_m"]) for k, v in p["atmospheres"].items()}
    G.update(p=p, ph1=ph1, db=db, A=A, hot=A[p["design_atmosphere"]])


def evaluate(blade, ctx, label):
    p, ph1, db, hot = G["p"], G["ph1"], G["db"], G["hot"]
    R = blade.R; t_h = ph1["vehicle"]["weight_n"] / 3; n = 3; V = p["mission"]["cruise_speed_ms"]
    iso = bemt.hover_at_thrust(blade, db, hot, t_h / 2)
    rpm_mach = mt.rpm_from_vtip(p["rotor"]["tip_mach_max"] * hot["a"], 2 * R)
    tw_mach = bemt.axial(blade, db, hot, rpm_mach)["T"] / (t_h / 2)
    c = coax_pair(blade, db, hot, t_h, 0.2 * 2 * R)
    e = bemt.edgewise_at_thrust(blade, db, hot, ctx["t_tot"] / (2 * n), V, ctx["alpha"], kappa=p["rotor"]["kappa"])
    om = e["rpm"] * 2 * math.pi / 60
    p_ind_c = e["T"] * e["lam0"] * om * R
    lam = e["lam0"] + V * math.sin(ctx["alpha"]) / (om * R)
    chi = math.atan2(e["mu"], lam); d = min(0.4 * R * math.tan(chi), 2 * R)
    f = (2 * R * R * math.acos(d / (2 * R)) - d / 2 * math.sqrt(4 * R * R - d * d)) / (math.pi * R * R)
    cruise = 2 * n * e["P"] + n * f * (ctx["p_ind_one_disk"] - 2 * p_ind_c)
    hover = n * c["P"]; climb = ctx["base_climb"] * hover / ctx["base_hover"]
    pack = mission_pack(p, ph1, hover, climb, cruise)[0]
    vol = do.blade_volume(blade)
    return {"label": label, "solidity": blade.solidity(), "chord_max_mm": 1000 * float(blade.c_def.max()),
            "chord_75_mm": 1000 * float(np.interp(0.75 * R, blade.r_def, blade.c_def)),
            "twist75_deg": math.degrees(float(np.interp(0.75 * R, blade.r_def, blade.th_def))), "blade_volume_cm3": 1e6 * vol,
            "iso_hover_rpm": iso["rpm"], "iso_fom": iso["FoM"], "stall_margin_deg": do.stall_margin_deg(db, iso, R), "tw_at_mach_limit": tw_mach,
            "arm_hover_w": c["P"], "rpm_upper": c["rpm_upper"], "rpm_lower": c["rpm_lower"], "split_upper": c["split_upper"],
            "cruise_w": cruise, "cruise_rpm": e["rpm"], "overlap_fraction": f, "climb_w": climb, "hover_w": hover, "pack_wh": pack,
            "mean_cl_iso": float(np.sum(iso["cl"] * iso["dT_dr"] * iso["dr"]) / iso["T"])}


def design(args):
    rpm, ctx = args
    p, ph1, hot, db = G["p"], G["ph1"], G["hot"], G["db"]
    R = p["rotor"]["diameter_in"] * p["constants"]["inch_to_m"] / 2
    t_h = ph1["vehicle"]["weight_n"] / 3
    try:
        blade, raw = do.design_hover_blade(R, p["rotor"]["hub_radius_m"], 2, rpm, t_h / 2, hot, db, p["design"], p["design"]["cl_design"])
        o = evaluate(blade, ctx, f"coax blade {rpm} rpm"); o["design_rpm"] = rpm
        o["blade"] = {"r": blade.r_def.tolist(), "chord": blade.c_def.tolist(), "twist_deg": np.degrees(blade.th_def).tolist(), "tc": blade.tc_def.tolist()}
        return o
    except ValueError as ex:
        return {"design_rpm": rpm, "error": str(ex)}


def run():
    t0 = time.time()
    init(); p, ph1, db, A, hot = G["p"], G["ph1"], G["db"], G["A"], G["hot"]
    dkey = p["design_atmosphere"]; mis = p["mission"]
    base_blade = load_final_blade(p)
    base = Rotor("baseline", base_blade, db, p, A, ph1)
    bh, bc, be = base.hover(dkey), base.climb(dkey, mis["climb_rate_ms"]), base.cruise(dkey, mis["cruise_speed_ms"])
    ctx = {"alpha": be["alpha_shaft"], "t_tot": 3 * be["T"], "base_hover": 3 * bh["P"], "base_climb": 3 * bc["P"],
           "p_ind_one_disk": be["T"] * be["lam0"] * be["rpm"] * 2 * math.pi / 60 * base_blade.R}
    base_pack = mission_pack(p, ph1, 3 * bh["P"], 3 * bc["P"], be["shaft_total"])[0]
    ref = evaluate(base_blade, ctx, "Phase 2 blade in the pair (config study)")
    print(f"  regression: Phase 2 blade as a pair -> pack {ref['pack_wh']:.0f} Wh (config study 5969) [{time.time()-t0:.0f}s]", flush=True)
    rpms = [1000, 1150, 1300, 1450, 1600, 1750, 1900, 2112]
    with Pool(min(4, len(rpms)), initializer=init) as pool:
        sweep = pool.map(design, [(r, ctx) for r in rpms])
    for s in sweep:
        if "error" in s: print(f"  {s['design_rpm']}: {s['error']}"); continue
        print(f"  design {s['design_rpm']}: sigma {s['solidity']:.3f} FoM_iso {s['iso_fom']:.3f} margin {s['stall_margin_deg']:.1f} T/W@Mach {s['tw_at_mach_limit']:.2f}"
              f" arm hover {s['arm_hover_w']:.0f} W cruise {s['cruise_w']:.0f} W pack {s['pack_wh']:.0f} Wh", flush=True)
    ok = [s for s in sweep if "error" not in s and s["stall_margin_deg"] >= p["design"]["min_stall_margin_deg"] and s["tw_at_mach_limit"] >= p["vehicle"]["tw_target"]]
    best = min(ok, key=lambda s: s["pack_wh"]) if ok else None
    # hand check: MIL solidity scales with thrust at a fixed RPM and cl
    p2 = next((s for s in sweep if s.get("design_rpm") == 1750 and "error" not in s), None)
    hc = {"solidity_phase2_blade": base_blade.solidity(), "solidity_coax_1750": p2 and p2["solidity"],
          "solidity_ratio": p2 and p2["solidity"] / base_blade.solidity(), "solidity_ratio_hand": 0.5,
          "ct_over_sigma_hand_note": "CT/sigma = cl_mean/6 at fixed RPM and cl -> sigma proportional to T",
          "mean_cl_coax_1750": p2 and p2["mean_cl_iso"]}
    # blade mass and payload, half-size motors, against the config study's accounting
    cat = load_catalog(); m = p["config_study"]["masses"]
    mot, esc = cat["motors"]["tmotor_u15xl_kv38"]["mass_kg"], cat["escs"]["tmotor_thunder_300a_24s"]["mass_kg"]
    bkg = ph1["mass_budget"]["blade_kg"]; hub = p["mass"]["hub_hardware_kg_per_rotor"]; vol0 = 1e6 * do.blade_volume(base_blade)
    arm_single = mot + esc + 2 * bkg + hub
    def hardware(s):
        prop = 2 * bkg * s["blade_volume_cm3"] / vol0 + hub
        return 3 * (2 * (mot * m["coax_motor_mass_scale"] + esc * m["coax_esc_mass_scale"] + prop) - arm_single) - m["tilt_servo_kg"]
    whkg = p["mass"]["pack_wh_per_kg_cited"]
    for s in [ref] + [s for s in sweep if "error" not in s]:
        s["hardware_kg"] = hardware(s)
        s["payload_change_kg"] = -(s["hardware_kg"] + (s["pack_wh"] - base_pack) / whkg)
    out = {"baseline_pack_wh": base_pack, "reference_phase2_blade_pair": ref, "sweep": sweep, "selected": best and best["design_rpm"],
           "hand_check": hc, "runtime_s": time.time() - t0}
    save_json(os.path.join("explore", "e01_coax_blade.json"), out)
    plot(out, base_blade)
    print(f"  selected {out['selected']} rpm; wrote results/explore/e01_coax_blade.json in {out['runtime_s']:.0f} s")
    return out


def plot(o, base_blade):
    fig, axs = plt.subplots(1, 3, figsize=(12, 3.3))
    ok = [s for s in o["sweep"] if "error" not in s]
    x = [s["design_rpm"] for s in ok]
    axs[0].plot(x, [s["pack_wh"] for s in ok], "o-", color="#0b0b0b", label="redesigned coax blade")
    axs[0].axhline(o["reference_phase2_blade_pair"]["pack_wh"], color="#2a78d6", ls="--", label="Phase 2 blade as a pair")
    axs[0].axhline(o["baseline_pack_wh"], color="#c0392b", ls=":", label="baseline tricopter")
    axs[0].set_xlabel("design hover RPM"); axs[0].set_ylabel("mission pack [Wh]"); axs[0].legend(fontsize=7); axs[0].grid(alpha=.3)
    axs[1].plot(x, [s["payload_change_kg"] for s in ok], "o-", color="#0b0b0b"); axs[1].axhline(o["reference_phase2_blade_pair"]["payload_change_kg"], color="#2a78d6", ls="--")
    axs[1].axhline(0, color="#c0392b", ls=":"); axs[1].set_xlabel("design hover RPM"); axs[1].set_ylabel("payload change [kg], half-size motors"); axs[1].grid(alpha=.3)
    r0 = base_blade.r_def / base_blade.R
    axs[2].plot(r0, 1000 * base_blade.c_def, color="#2a78d6", ls="--", label="Phase 2 blade")
    if o["selected"]:
        s = next(q for q in ok if q["design_rpm"] == o["selected"])
        axs[2].plot(np.array(s["blade"]["r"]) / base_blade.R, 1000 * np.array(s["blade"]["chord"]), color="#0b0b0b", label=f"coax blade {o['selected']} rpm")
    axs[2].set_xlabel("r / R"); axs[2].set_ylabel("chord [mm]"); axs[2].legend(fontsize=7); axs[2].grid(alpha=.3)
    fig.suptitle("Exploration 01: blade designed for the coaxial pair (half thrust per rotor), h = 0.2 D, hot day", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "e01_coax_blade.png"), dpi=140); plt.close(fig)


if __name__ == "__main__":
    run()

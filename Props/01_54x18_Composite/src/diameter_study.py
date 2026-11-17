"""Diameter study: repeat the Phase 2 hover design (MIL + constraints, no two-point refinement) at several diameters
and match each against the catalog motors. Writes results/diameter_study.json and a plot."""
import json, math, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import airfoils, design_opt as do, atmosphere as atm, momentum as mt
from phase2 import Rotor, SCAL
from common import RESULTS, load_params, load_catalog, save_json


def run():
    t0 = time.time()
    p, cat = load_params(), load_catalog()
    ph1 = json.load(open(os.path.join(RESULTS, "phase1.json")))
    c, rot, d, el, mass, ds = p["constants"], p["rotor"], p["design"], p["electrical"], p["mass"], p["diameter_study"]
    db, _ = airfoils.build_db(p)
    A = {k: atm.state(v["temp_c"], v["alt_m"]) for k, v in p["atmospheres"].items()}
    dkey = p["design_atmosphere"]; hot = A[dkey]
    t_h, mtow = ph1["vehicle"]["t_hover"], ph1["vehicle"]["mtow_kg"]
    v_sag = el["cells_baseline"] * el["v_cell_sag"]
    v_fresh = ph1["motor_match"]["catalog_motors"]["tmotor_u15xl_kv38"]["v_fresh_loaded"]
    bm = cat["props"]["blade_mass_g"]
    esc_kg = cat["escs"]["tmotor_thunder_300a_24s"]["mass_kg"]
    d_ref = rot["diameter_in"]
    out = {"v_sag": v_sag, "v_fresh": v_fresh, "diameters": {}}
    for d_in in ds["diameters_in"]:
        R = d_in * c["inch_to_m"] / 2
        designs = []
        for rpm0 in d["hover_rpm_sweep"]:
            rpm = rpm0 * d_ref / d_in
            blade, _ = do.design_hover_blade(R, rot["hub_radius_m"], rot["n_blades"], rpm, t_h, hot, db, d, d["cl_design"])
            r_ = Rotor(f"{d_in} in, {rpm:.0f} rpm", blade, db, p, A, ph1)
            h = r_.hover(dkey)
            rec = {"design_rpm": rpm, "hover": SCAL(h), "stall_margin_deg": do.stall_margin_deg(db, h, R), "solidity": blade.solidity(),
                   "pitch75_in": do.equivalent_pitch(blade) / c["inch_to_m"], "chord_max_mm": 1000 * float(blade.c_def.max()),
                   "volume_cm3": 1e6 * do.blade_volume(blade),
                   "tw_at_mach_limit": r_.at_rpm(dkey, mt.rpm_from_vtip(rot["tip_mach_max"] * hot["a"], 2 * R))["T"] / t_h, "motors": {}}
            for mname in ds["motors"]:
                m = cat["motors"][mname]
                rec["motors"][mname] = {"sag": r_.motor_tw(dkey, m["kv"], m["peak_current_a"], v_sag), "fresh": r_.motor_tw(dkey, m["kv"], m["peak_current_a"], v_fresh)}
            rec["_rotor"] = r_
            designs.append(rec)
        entry = {"R": R, "disk_loading": t_h / (math.pi * R * R), "rpm_mach_limit": mt.rpm_from_vtip(rot["tip_mach_max"] * hot["a"], 2 * R),
                 "arm_m": p["vehicle"]["arm_clearance_factor"] * 2 * R / math.sqrt(3), "best": {}}
        blade_kg = (bm[52] + (d_in - 52) / (57 - 52) * (bm[57] - bm[52])) / 1000      # linear in diameter; extrapolated above 57 in
        frame_kg = mass["frame_fraction_of_mtow"] * mtow * ((d_in / d_ref) if ds["frame_scales_with_diameter"] else 1.0)
        for mname in ds["motors"]:
            ok = [r for r in designs if r["stall_margin_deg"] >= d["min_stall_margin_deg"]]
            b = max(ok, key=lambda r: r["motors"][mname]["sag"]["tw"])
            r_ = b["_rotor"]
            mis = r_.mission(p["mission"]["atmosphere"])
            cr = {f"{v:.0f}": SCAL(r_.cruise(dkey, v)) for v in p["mission"]["cruise_speeds_ms"]}
            m = cat["motors"][mname]
            fixed = 3 * (m["mass_kg"] + esc_kg + rot["n_blades"] * blade_kg + mass["hub_hardware_kg_per_rotor"]) + frame_kg + mass["avionics_wiring_kg"]
            budg = {}
            for tag, e in (("cited_303", mass["pack_wh_per_kg_cited"]), ("conservative_200", mass["pack_wh_per_kg_conservative"])):
                batt = mis["pack_wh"] / e
                budg[tag] = {"battery_kg": batt, "drone_kg": fixed + batt, "drone_lb": (fixed + batt) / c["lb_to_kg"],
                             "payload_kg": mtow - fixed - batt, "payload_lb": (mtow - fixed - batt) / c["lb_to_kg"]}
            tw2 = None
            try:
                s2 = r_.hover(dkey, p["vehicle"]["tw_target"]); tw2 = {"rpm": s2["rpm"], "P": s2["P"], "Q": s2["Q"], "tip_mach": s2["tip_mach"]}
            except ValueError:
                pass
            entry["best"][mname] = {k: v for k, v in b.items() if k not in ("_rotor", "motors")}
            entry["best"][mname].update(tw_sag=b["motors"][mname]["sag"], tw_fresh=b["motors"][mname]["fresh"], pack_wh=mis["pack_wh"],
                                        hover_energy_share=mis["hover_energy_share"], cruise=cr, tw_target_point=tw2,
                                        hover_elec_over_rated=b["hover"]["P"] / el["eta_motor_esc"] / m["rated_power_w"],
                                        hover_bus_current_sag=b["hover"]["P"] / el["eta_motor_esc"] / v_sag,
                                        blade_kg=blade_kg, frame_kg=frame_kg, fixed_non_battery_kg=fixed, budget=budg,
                                        hover_hot_high=SCAL(r_.hover("hot_high")))
        entry["designs"] = [{k: v for k, v in r.items() if k != "_rotor"} for r in designs]
        out["diameters"][str(d_in)] = entry
        print(f"  {d_in} in done [{time.time()-t0:.0f}s]: " + "; ".join(f"{mn.split('_')[1]} T/W {e['tw_sag']['tw']:.2f}/{e['tw_fresh']['tw']:.2f} pack {e['pack_wh']:.0f} payload {e['budget']['cited_303']['payload_lb']:.0f} lb" for mn, e in entry["best"].items()), flush=True)
    save_json("diameter_study.json", out)

    INK, ACC, RED = "#0b0b0b", "#2a78d6", "#c0392b"
    D = [int(k) for k in out["diameters"]]
    fig, axs = plt.subplots(1, 3, figsize=(9.5, 3.1))
    for mname, col in zip(ds["motors"], (INK, ACC)):
        B = [out["diameters"][str(k)]["best"][mname] for k in D]; lab = mname.split("_")[1].upper() + " KV" + mname.split("kv")[1]
        axs[0].plot(D, [b["pack_wh"] / 1000 for b in B], "o-", color=col, label=lab)
        axs[1].plot(D, [b["tw_sag"]["tw"] for b in B], "o-", color=col, label=lab + f", {out['v_sag']:.0f} V"); axs[1].plot(D, [b["tw_fresh"]["tw"] for b in B], "o--", color=col, label=lab + f", {out['v_fresh']:.0f} V")
        axs[2].plot(D, [b["budget"]["cited_303"]["payload_lb"] for b in B], "o-", color=col, label=lab + ", 303 Wh/kg"); axs[2].plot(D, [b["budget"]["conservative_200"]["payload_lb"] for b in B], "o--", color=col, label=lab + ", 200 Wh/kg")
    axs[1].axhline(p["vehicle"]["tw_required"], color=RED, lw=1); axs[1].axhline(p["vehicle"]["tw_target"], color=RED, lw=1, ls=":")
    axs[0].set_ylabel("mission pack energy [kWh]"); axs[1].set_ylabel("T/W at 100 % throttle, hot day"); axs[2].set_ylabel("payload at 280 lb MTOW [lb]")
    for a in axs: a.set_xlabel("prop diameter [in]"); a.grid(alpha=.3); a.legend(fontsize=6); a.set_xticks(D)
    fig.suptitle("Diameter study (BEMT, hot day, best design per motor)", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(RESULTS, "diameter_study.png"), dpi=150); plt.close(fig)
    return out


if __name__ == "__main__":
    run(); print("wrote results/diameter_study.json")

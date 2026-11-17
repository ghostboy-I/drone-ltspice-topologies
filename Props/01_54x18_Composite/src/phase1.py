"""Phase 1 driver: sizing and hand calculations. Writes results/phase1.json and plots. No numbers are typed in
here; everything comes from params.yaml, data/catalog.yaml and data/*.csv."""
import csv, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import atmosphere as atm
import momentum as mt
import motor_match as mm
import mission as ms
import prelim_checks as pc
from common import ROOT, RESULTS, load_params, load_catalog, save_json


def run(p=None, write=True):
    p = p or load_params()
    cat = load_catalog()
    c, veh, rot, el, mis, mass = p["constants"], p["vehicle"], p["rotor"], p["electrical"], p["mission"], p["mass"]
    out = {}

    # ---- 1. atmospheres ---------------------------------------------------------------------------------
    A = {k: dict(atm.state(v["temp_c"], v["alt_m"]), label=v["label"]) for k, v in p["atmospheres"].items()}
    hot = A[p["design_atmosphere"]]
    humid = atm.state(hot["temp_c"], hot["alt_m"], p["humidity_sens_rh"])
    out["atmospheres"] = A
    out["humid_hot"] = dict(humid, drho_pct=100 * (humid["rho"] / hot["rho"] - 1))

    # ---- 2. vehicle and disk ----------------------------------------------------------------------------
    mtow = veh["mtow_lb"] * c["lb_to_kg"]
    drone_max = veh["drone_max_lb"] * c["lb_to_kg"]
    W = mtow * c["g0"]
    n = veh["n_rotors"]
    D = rot["diameter_in"] * c["inch_to_m"]
    R, area = D / 2, mt.disk_area(D)
    t_hover = W / n
    out["vehicle"] = {"mtow_kg": mtow, "drone_max_kg": drone_max, "payload_kg": mtow - drone_max,
                      "payload_fraction": 1 - drone_max / mtow, "weight_n": W, "n_rotors": n, "D": D, "R": R,
                      "disk_area": area, "t_hover": t_hover, "t_tw_required": veh["tw_required"] * t_hover,
                      "t_tw_target": veh["tw_target"] * t_hover, "disk_loading": t_hover / area,
                      "range_m": mis["range_nmi"] * c["nmi_to_m"]}

    # ---- 3. rotor sizing: the T/W target is reached exactly at the tip-Mach limit on the hot day --------
    vtip_max = rot["tip_mach_max"] * hot["a"]
    rpm_max = mt.rpm_from_vtip(vtip_max, D)
    t_size = rot["sizing_tw_at_mach_limit"] * t_hover
    ct_h = mt.ct_heli(t_size, hot["rho"], area, vtip_max)
    ct = mt.ct_heli_to_prop(ct_h)
    sigma = mt.solidity_for_blade_loading(ct_h, rot["mean_cl_hover"])
    chord = mt.mean_chord(sigma, rot["n_blades"], R)
    theta75 = mt.collective_for_ct(ct_h, sigma, rot["lift_slope_per_rad"])
    fom_model = mt.fom_model(ct_h, sigma, rot["kappa"], rot["cd0"])
    fom = rot["fom_assumed"]
    cp = ct ** 1.5 / (math.sqrt(2 * math.pi) * fom)      # from P = T^1.5/sqrt(2 rho A)/FoM with A = pi D^2/4
    out["sizing"] = {"vtip_max": vtip_max, "rpm_max": rpm_max, "t_size": t_size, "ct_heli": ct_h, "ct_prop": ct,
                     "cp_prop": cp, "cq_prop": mt.cq_prop_from_cp(cp), "sigma": sigma, "mean_chord": chord,
                     "blade_aspect_ratio": R / chord, "theta75_deg": math.degrees(theta75),
                     "fom_model": fom_model, "fom_assumed": fom,
                     "chord_3_blades": mt.mean_chord(sigma, 3, R)}

    # ---- 4. operating points per atmosphere -------------------------------------------------------------
    pts = []
    for key, a in A.items():
        t_mach = ct_h * a["rho"] * area * (rot["tip_mach_max"] * a["a"]) ** 2
        for tw in (1.0, veh["tw_required"], veh["tw_target"]):
            T = tw * t_hover
            rpm = mt.rpm_for_thrust(T, a["rho"], ct, D)
            vt = mt.vtip_from_rpm(rpm, D)
            p_id = mt.ideal_hover_power(T, a["rho"], area)
            p_sh = p_id / fom
            pts.append({"atm": key, "tw": tw, "thrust": T, "rpm": rpm, "vtip": vt, "tip_mach": vt / a["a"],
                        "vi": mt.hover_vi(T, a["rho"], area), "p_ideal": p_id, "p_shaft": p_sh,
                        "torque": p_sh / (2 * math.pi * rpm / 60), "re_75": 0.75 * vt * chord / a["nu"],
                        "re_tip": vt * chord / a["nu"], "mach_ok": vt / a["a"] <= rot["tip_mach_max"] + 1e-9,
                        "tw_at_mach_limit": t_mach / t_hover})
    out["operating_points"] = pts
    P = {(q["atm"], q["tw"]): q for q in pts}
    hov_hot = P[(p["design_atmosphere"], 1.0)]
    out["span_reynolds_hot_hover"] = [{"r_over_R": x, "v": x * hov_hot["vtip"], "mach": x * hov_hot["vtip"] / hot["a"],
                                       "re": x * hov_hot["vtip"] * chord / hot["nu"]} for x in (0.2, 0.4, 0.6, 0.75, 0.9, 1.0)]

    # ---- 5. candidates (section 3.1), first-order only --------------------------------------------------
    cands = []
    for cd in p["candidates"]:
        d = cd["d_in"] * c["inch_to_m"]; a_ = mt.disk_area(d)
        cands.append({"name": cd["name"], "D": d, "d_over_p": cd["d_in"] / cd["p_in"], "disk_loading": t_hover / a_,
                      "pitch75_deg": math.degrees(mt.geometric_pitch_angle(cd["p_in"] * c["inch_to_m"], d / 2)),
                      "p_ideal_hover_hot": mt.ideal_hover_power(t_hover, hot["rho"], a_),
                      "rpm_at_mach_limit": mt.rpm_from_vtip(vtip_max, d),
                      "tw_at_mach_limit_same_cth": ct_h * hot["rho"] * a_ * vtip_max ** 2 / t_hover})
    out["candidates"] = cands

    # ---- 6. vendor bench data cross-check (T-Motor U15XL + 52x20) ---------------------------------------
    rows = []
    with open(os.path.join(ROOT, "data", "tmotor_u15xl_52x20.csv")) as f:
        rd = csv.DictReader(l for l in f if not l.startswith("#"))
        b = atm.state(32.0, 0.0)                  # ambient stated by vendor; sea-level pressure is an assumption
        d52 = 52 * c["inch_to_m"]; a52 = mt.disk_area(d52)
        for r in rd:
            T = float(r["thrust_g"]) / 1000 * c["g0"]; rpm = float(r["rpm"])
            p_sh = float(r["torque_nm"]) * 2 * math.pi * rpm / 60
            vt = mt.vtip_from_rpm(rpm, d52)
            rows.append({"throttle": float(r["throttle_pct"]), "thrust": T, "rpm": rpm, "p_shaft": p_sh,
                         "p_elec": float(r["power_w"]), "volts": float(r["voltage_v"]), "current": float(r["current_a"]),
                         "ct_heli": mt.ct_heli(T, b["rho"], a52, vt), "tip_mach": vt / b["a"],
                         "fom": mt.ideal_hover_power(T, b["rho"], a52) / p_sh, "eta_drive": p_sh / float(r["power_w"]),
                         "p_shaft_model_fom": mt.ideal_hover_power(T, b["rho"], a52) / fom})
    full = rows[-1]
    kv_xl = cat["motors"]["tmotor_u15xl_kv38"]["kv"]
    near = min(rows, key=lambda r: abs(r["thrust"] - t_hover))
    out["vendor_check"] = {"rows": rows, "k_load_100": full["rpm"] / (kv_xl * full["volts"]),
                           "eta_drive_mean": float(np.mean([r["eta_drive"] for r in rows[4:]])),
                           "fom_mean_50_100": float(np.mean([r["fom"] for r in rows[4:]])),
                           "ct_heli_100": full["ct_heli"], "near_hover_row": near,
                           "near_hover_pdiff_pct": 100 * (near["p_shaft_model_fom"] / near["p_shaft"] - 1)}

    # ---- 7. motor / ESC matching ------------------------------------------------------------------------
    match = {}
    for tag, tw in (("required", veh["tw_required"]), ("target", veh["tw_target"])):
        q = P[(p["design_atmosphere"], tw)]
        match[tag] = {"tw": tw, "rpm": q["rpm"], "p_shaft": q["p_shaft"], "torque": q["torque"],
                      "p_elec": q["p_shaft"] / el["eta_motor_esc"],
                      "at_sag": mm.pack_table(q["p_shaft"], q["rpm"], el["cells_options"], el["v_cell_sag"],
                                              el["eta_motor_esc"], el["k_load"], el["esc_margin"]),
                      "at_empty": mm.pack_table(q["p_shaft"], q["rpm"], el["cells_options"], el["v_cell_empty"],
                                                el["eta_motor_esc"], el["k_load"], el["esc_margin"])}
    v_sag = el["cells_baseline"] * el["v_cell_sag"]
    motors = {}
    for name, m in cat["motors"].items():
        rpm_av = mm.loaded_rpm(m["kv"], v_sag, el["k_load"])
        tw_rpm = ct * hot["rho"] * (min(rpm_av, rpm_max) / 60) ** 2 * D ** 4 / t_hover
        p_sh_lim = m["peak_current_a"] * v_sag * el["eta_motor_esc"]
        t_cur = (p_sh_lim * fom * math.sqrt(2 * hot["rho"] * area)) ** (2 / 3)
        v_full_loaded = full["volts"]                         # vendor bus voltage at 100 % throttle on a fresh pack
        rpm_full = min(mm.loaded_rpm(m["kv"], v_full_loaded, el["k_load"]), rpm_max)
        vt_av = mt.vtip_from_rpm(rpm_av, D)
        ct_need = mt.ct_heli(veh["tw_required"] * t_hover, hot["rho"], area, vt_av)
        motors[name] = {"kv": m["kv"], "mass_kg": m["mass_kg"], "rpm_available_sag": rpm_av, "tw_rpm_limit": tw_rpm,
                        "tw_rpm_limit_fresh_pack": ct * hot["rho"] * (rpm_full / 60) ** 2 * D ** 4 / t_hover,
                        "tw_current_limit_fresh_pack": (m["peak_current_a"] * v_full_loaded * el["eta_motor_esc"] * fom
                                                        * math.sqrt(2 * hot["rho"] * area)) ** (2 / 3) / t_hover,
                        "v_fresh_loaded": v_full_loaded, "ct_heli_needed_for_tw_required": ct_need,
                        "blade_loading_needed": ct_need / sigma,
                        "tw_current_limit": t_cur / t_hover, "tw_achievable": min(tw_rpm, t_cur / t_hover),
                        "peak_current_a": m["peak_current_a"], "rated_power_w": m["rated_power_w"],
                        "hover_elec_over_rated": hov_hot["p_shaft"] / el["eta_motor_esc"] / m["rated_power_w"],
                        "kt": mm.kt_from_kv(m["kv"])}
    out["motor_match"] = {"v_sag": v_sag, "cases": match, "catalog_motors": motors,
                          "hover_bus_current_sag": mm.bus_current(hov_hot["p_shaft"], el["eta_motor_esc"], v_sag)}

    # ---- 8. yaw trim by tail tilt -----------------------------------------------------------------------
    r_arm = veh["arm_clearance_factor"] * D / math.sqrt(3)       # equilateral layout, hub spacing = factor * D
    q_over_t = hov_hot["torque"] / hov_hot["thrust"]             # constant with RPM for a fixed-pitch prop
    yaw = {"r_arm": r_arm, "q_over_t": q_over_t, "layouts": {}}
    for name, n_net in (("2+1 (two one way, one the other)", 1), ("3 same direction", 3)):
        s = n_net * q_over_t / r_arm
        th = math.asin(s)
        yaw["layouts"][name] = {"net_torque_hover": n_net * hov_hot["torque"], "tilt_deg": math.degrees(th),
                                "tail_lift_loss_pct": 100 * (1 - math.cos(th)), "side_force_hover": t_hover * math.tan(th),
                                "roll_trim_deg": math.degrees(math.atan(t_hover * math.tan(th) / W)),
                                "tw_after_tilt_required": veh["tw_required"] * (2 + math.cos(th)) / 3,
                                "tw_after_tilt_target": veh["tw_target"] * (2 + math.cos(th)) / 3}
    out["yaw_trim"] = yaw

    # ---- 9. mission energy and mass budget --------------------------------------------------------------
    ma = A[mis["atmosphere"]]
    hov_m = P[(mis["atmosphere"], 1.0)]

    def vehicle(fom_=fom, cda_=veh["cda_m2"], rho_=ma["rho"]):
        return ms.Vehicle(W, n, area, rho_, fom_, rot["kappa"], hov_m["vtip"], cda_, el["eta_motor_esc"],
                          el["eta_battery_wiring"], mis["avionics_w"])
    rng = out["vehicle"]["range_m"]
    base = ms.mission_energy(vehicle(), mis, rng, mis["cruise_speed_ms"])
    out["mission"] = base
    out["mission"]["hover_shaft_total"] = vehicle().hover_shaft()
    out["mission"]["hover_elec_total"] = vehicle().electrical(vehicle().hover_shaft())
    out["mission"]["speed_sweep"] = [dict(v=v, **{k: ms.mission_energy(vehicle(), mis, rng, v)[k] for k in ("energy_wh", "pack_wh")},
                                          cruise_shaft=vehicle().cruise(v)["shaft_total"], alpha_deg=math.degrees(vehicle().cruise(v)["alpha"]),
                                          vi=vehicle().cruise(v)["vi"], wh_per_km=vehicle().electrical(vehicle().cruise(v)["shaft_total"]) / v / 3.6)
                                     for v in mis["cruise_speeds_ms"]]
    sens = [{"case": "baseline", "pack_wh": base["pack_wh"]}]
    for f_ in rot["fom_sens"]:
        sens.append({"case": f"FoM {f_:.2f}", "pack_wh": ms.mission_energy(vehicle(fom_=f_), mis, rng, mis["cruise_speed_ms"])["pack_wh"]})
    for cd_ in veh["cda_sens"]:
        sens.append({"case": f"CdA {cd_:.2f} m2", "pack_wh": ms.mission_energy(vehicle(cda_=cd_), mis, rng, mis["cruise_speed_ms"])["pack_wh"]})
    sens.append({"case": "ISA sea level", "pack_wh": ms.mission_energy(vehicle(rho_=A["isa_sl"]["rho"]), mis, rng, mis["cruise_speed_ms"])["pack_wh"]})
    for s_ in sens:
        s_["delta_pct"] = 100 * (s_["pack_wh"] / base["pack_wh"] - 1)
    out["mission"]["sensitivity"] = sens
    peak_el = n * match["target"]["p_elec"]
    out["mission"]["c_rate_hover"] = out["mission"]["hover_elec_total"] / base["pack_wh"]
    out["mission"]["c_rate_peak_target"] = peak_el / base["pack_wh"]
    out["mission"]["peak_elec_total_target"] = peak_el

    bm = cat["props"]["blade_mass_g"]
    blade_kg = (bm[52] + (rot["diameter_in"] - 52) / (57 - 52) * (bm[57] - bm[52])) / 1000    # linear in diameter
    frame_kg = mass["frame_fraction_of_mtow"] * mtow
    esc_kg = cat["escs"]["tmotor_thunder_300a_24s"]["mass_kg"]
    budgets = {}
    for tag, mname in (("required_tw1.5", "tmotor_u15xl_kv38"), ("target_tw2.0", "tmotor_u15xxl_kv29")):
        for etag, e in (("cited_303", mass["pack_wh_per_kg_cited"]), ("conservative_200", mass["pack_wh_per_kg_conservative"])):
            b_ = ms.mass_budget(base["pack_wh"], e, cat["motors"][mname]["mass_kg"], esc_kg, blade_kg, rot["n_blades"],
                                mass["hub_hardware_kg_per_rotor"], n, frame_kg, mass["avionics_wiring_kg"])
            b_.update(motor=mname, wh_per_kg=e, non_battery=b_["total"] - b_["battery"], total_lb=b_["total"] / c["lb_to_kg"],
                      over_budget_kg=b_["total"] - drone_max, payload_kg=mtow - b_["total"],
                      payload_lb=(mtow - b_["total"]) / c["lb_to_kg"])
            budgets[f"{tag}/{etag}"] = b_
    out["mass_budget"] = {"drone_max_kg": drone_max, "blade_kg": blade_kg, "cases": budgets}

    # payload-range at fixed MTOW (best case hardware: T/W 1.5 motor)
    fixed = budgets["required_tw1.5/cited_303"]["non_battery"]
    ranges = np.linspace(0, 40e3, 41)
    pr = []
    for r_ in ranges:
        e_ = ms.mission_energy(vehicle(), mis, float(r_), mis["cruise_speed_ms"])["pack_wh"]
        pr.append({"range_km": r_ / 1000, "pack_wh": e_,
                   "payload_kg_303": mtow - fixed - e_ / mass["pack_wh_per_kg_cited"],
                   "payload_kg_200": mtow - fixed - e_ / mass["pack_wh_per_kg_conservative"]})
    out["payload_range"] = {"fixed_non_battery_kg": fixed, "curve": pr,
                            "battery_allowance_at_55lb_kg": drone_max - fixed}

    # ---- 10. section 3 first-pass checks ----------------------------------------------------------------
    bp, sp = p["balance_prelim"], p["structure_prelim"]
    rotor_mass = rot["n_blades"] * blade_kg + mass["hub_hardware_kg_per_rotor"]
    bal = {"rotor_mass_kg": rotor_mass, "rpm_max": rpm_max,
           "tip_speed_at_brief_rpm": pc.tip_speed(D, bp["brief_rpm"]),
           "tip_mach_at_brief_rpm": pc.tip_speed(D, bp["brief_rpm"]) / A["isa_sl"]["a"],
           "brief_0p1g_at_tip_gmm": pc.unbalance_from_mass(bp["brief_imbalance_g"], R * 1000),
           "brief_0p03g_at_tip_gmm": pc.unbalance_from_mass(bp["brief_match_g"], R * 1000), "grades": [], "offsets": []}
    for g in bp["iso_grades_mm_s"]:
        e_um, u = pc.iso_permissible_unbalance(g, rpm_max, rotor_mass)
        bal["grades"].append({"grade": g, "e_per_um": e_um, "u_per_gmm": u, "force_n": pc.unbalance_force(u, rpm_max),
                              "equiv_tip_mass_g": u / (R * 1000)})
    for off in bp["hub_offset_mm"]:
        u = pc.offset_unbalance(rotor_mass, off)
        bal["offsets"].append({"offset_mm": off, "u_gmm": u, "force_n_max_rpm": pc.unbalance_force(u, rpm_max),
                               "force_n_hover": pc.unbalance_force(u, hov_hot["rpm"]),
                               "ratio_to_g6p3": u / bal["grades"][-1]["u_per_gmm"]})
    bal["force_brief_0p1g_tip_max_rpm"] = pc.unbalance_force(bal["brief_0p1g_at_tip_gmm"], rpm_max)
    out["balance_prelim"] = bal

    L = R - rot["hub_radius_m"]
    flex = {"L_brief": 0.6, "L_actual": L, "cases": []}
    for Lx in (0.6, L):
        ei = pc.required_ei(sp["flex_load_n"], Lx, sp["flex_limit_mm"] / 1000)
        row = {"L": Lx, "ei_required": ei}
        for mat, e_gpa in (("carbon_ud", sp["e_ud_carbon_gpa"]), ("glass_ud", sp["e_glass_gpa"]), ("aluminum", sp["e_aluminum_gpa"])):
            t = pc.rect_thickness_for_ei(ei, e_gpa * 1e9, chord)
            row[mat] = {"t_mm": 1000 * t, "t_over_c": t / chord}
        flex["cases"].append(row)
    # same geometry, other materials: deflection scales with 1/E
    flex["deflection_ratio_glass"] = sp["e_ud_carbon_gpa"] / sp["e_glass_gpa"]
    flex["deflection_ratio_aluminum"] = sp["e_ud_carbon_gpa"] / sp["e_aluminum_gpa"]
    out["flex_prelim"] = flex

    dth = math.radians(1.1)
    ct_up = mt.ct_for_collective(theta75 + dth, sigma, rot["lift_slope_per_rad"])
    ct_dn = mt.ct_for_collective(theta75 - dth, sigma, rot["lift_slope_per_rad"])
    out["pitch_vs_density"] = {"density_change_pct": 100 * (hot["rho"] / A["isa_sl"]["rho"] - 1),
                               "thrust_change_pitch_plus_pct": 100 * (ct_up / ct_h - 1),
                               "thrust_change_pitch_minus_pct": 100 * (ct_dn / ct_h - 1),
                               "pitch_for_9pct_deg": None}
    lo, hi = 0.0, dth                                    # pitch loss that alone costs 9 % thrust
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if mt.ct_for_collective(theta75 - mid, sigma, rot["lift_slope_per_rad"]) / ct_h > 0.91: lo = mid
        else: hi = mid
    out["pitch_vs_density"]["pitch_for_9pct_deg"] = math.degrees(lo)

    # ---- brief's own rough numbers, for the claims register ---------------------------------------------
    isa = A["isa_sl"]
    out["brief_checks"] = {"p_ideal_isa": mt.ideal_hover_power(t_hover, isa["rho"], area),
                           "p_fom_isa": mt.ideal_hover_power(t_hover, isa["rho"], area) / fom,
                           "p_total_isa": n * mt.ideal_hover_power(t_hover, isa["rho"], area) / fom,
                           "cruise_time_min": rng / mis["cruise_speed_ms"] / 60}

    if write:
        save_json("phase1.json", out)
        plots(out, p)
    return out


def plots(o, p):
    INK, ACC, RED = "#0b0b0b", "#2a78d6", "#c0392b"
    # payload-range
    pr = o["payload_range"]["curve"]; v = o["vehicle"]
    fig, ax = plt.subplots(figsize=(6.5, 3.6))
    ax.plot([r["range_km"] for r in pr], [r["payload_kg_303"] for r in pr], color=ACC, label="303 Wh/kg pack (vendor claim)")
    ax.plot([r["range_km"] for r in pr], [r["payload_kg_200"] for r in pr], color=INK, ls="--", label="200 Wh/kg pack (assumed LiPo)")
    ax.axhline(v["payload_kg"], color=RED, lw=1); ax.text(0.5, v["payload_kg"] + 1.5, "brief: 225 lb payload", color=RED, fontsize=8)
    ax.axvline(v["range_m"] / 1000, color=RED, lw=1, ls=":"); ax.text(v["range_m"] / 1000 + 0.4, 5, "10 nmi", color=RED, fontsize=8)
    ax.set_xlabel("One-way range at MTOW [km]"); ax.set_ylabel("Payload [kg]"); ax.set_ylim(0, 110); ax.grid(alpha=.3)
    ax.set_title("Payload vs range at fixed 280 lb MTOW (hot day, 15 m/s, 20 % reserve)", fontsize=9); ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(RESULTS, "phase1_payload_range.png"), dpi=150); plt.close(fig)
    # vendor cross-check
    rows = o["vendor_check"]["rows"]
    fig, axs = plt.subplots(1, 2, figsize=(6.5, 3.0))
    axs[0].plot([r["thrust"] for r in rows], [r["p_shaft"] / 1000 for r in rows], "o-", color=INK, ms=3, label="vendor bench (torque x speed)")
    axs[0].plot([r["thrust"] for r in rows], [r["p_shaft_model_fom"] / 1000 for r in rows], color=ACC, label=f"momentum theory / FoM {o['sizing']['fom_assumed']:.2f}")
    axs[0].set_xlabel("Thrust [N]"); axs[0].set_ylabel("Shaft power [kW]"); axs[0].legend(fontsize=7); axs[0].grid(alpha=.3)
    axs[1].plot([r["thrust"] for r in rows], [r["fom"] for r in rows], "o-", color=INK, ms=3)
    axs[1].axhline(o["sizing"]["fom_assumed"], color=ACC); axs[1].set_ylim(0.5, 1.0)
    axs[1].set_xlabel("Thrust [N]"); axs[1].set_ylabel("Implied figure of merit"); axs[1].grid(alpha=.3)
    fig.suptitle("Cross-check against T-Motor U15XL + 52x20 bench data (32 C)", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(RESULTS, "phase1_vendor_check.png"), dpi=150); plt.close(fig)
    # mass budget bars
    cases = o["mass_budget"]["cases"]
    keys = ["battery", "motors", "escs", "props", "frame", "avionics_wiring"]
    fig, ax = plt.subplots(figsize=(6.5, 3.2)); left = np.zeros(len(cases))
    cols = ["#2a78d6", "#52514e", "#8e8d88", "#c0392b", "#d6a12a", "#3a9a5c"]
    for k, col in zip(keys, cols):
        vals = np.array([cs[k] for cs in cases.values()]); ax.barh(list(cases.keys()), vals, left=left, color=col, label=k); left += vals
    ax.axvline(o["mass_budget"]["drone_max_kg"], color="k", lw=1.5); ax.text(o["mass_budget"]["drone_max_kg"] + 0.5, -0.45, "55 lb limit", fontsize=8)
    ax.set_xlabel("Drone mass [kg]"); ax.legend(fontsize=7, ncol=6, loc="lower center", bbox_to_anchor=(0.4, 1.0), frameon=False, columnspacing=1.0, handlelength=1.2); ax.tick_params(axis="y", labelsize=7)
    fig.tight_layout(); fig.savefig(os.path.join(RESULTS, "phase1_mass_budget.png"), dpi=150); plt.close(fig)


if __name__ == "__main__":
    o = run()
    print("wrote results/phase1.json")

"""Conceptual sizing of the Osprey-style tilt-HEX: wing, rotor layout, tail, drag, cruise thrust, download, gusts.

Rotors (hexrotor.py): six of the decision matrix's hex rotor (Props entry 46, 54 in, 24xx, MN1123 KV53). Four tilt on
the wing (a tip head and an inboard head per side, side by side, all at equal thrust), two are fixed lift rotors aft on a
tail cross-beam. The wing, fuselage and tail methods are Airframe 02's.

Everything here is a hand calculation (textbook methods, each stated where it is used); the frame FE model
(tiltframe.py) and the CFD cases check the parts the hand methods cannot.

Coordinates: x forward, y left, z up. Origin at the wing root quarter-chord, on the spar-box axis.

1. Wing section (XFOIL, Re and Mach of the cruise point, hot day). Candidates are NACA 4- and 5-digit sections and
   NASA general-aviation sections from coordinate files (wing_sections.py), all with t/c >= 15 % (spar depth). The
   section with the largest TRIPPED clmax wins (smallest wing); cd at the cruise cl (free transition) is reported.
   Incidence: the root chord is set at the angle that gives CL_cruise with the fuselage level,
       i_w = alpha_L0 + CL_cr / a_w   (untwisted wing, a_w Helmbold).
2. Wing area: the smallest wing that cruises at >= 1.2 x its stall speed (light-aircraft practice, Raymer ch. 5):
       CL_max,3D = 0.9 clmax  (Raymer eq. 12.15, unswept, untwisted),   CL_cr = CL_max,3D / 1.2^2,
       S = W / (q CL_cr),   q = rho V^2 / 2.   b = sqrt(AR S) with the V-22 aspect ratio 5.5.
3. Drag build-up (Raymer ch. 12): every body gets C_f (turbulent flat plate, 0.455 / (log10 Re)^2.58) x form factor
   x wetted area x interference; the wing uses its XFOIL cd. Induced drag CL^2 / (pi e AR). Leakage + protuberances +10 %.
4. Cruise thrust: the four tilting rotors in axial flight at the motor's speed limit (Props BEMT, bemt.axial on the
   tilting blade); eta = T V / P. With the hex blade the zero-thrust speed is below the stall speed, which is reported.
5. Rotor layout in hover: equal thrust on all six rotors needs the CG at the mean of the hub positions,
       x_cg = (2 x_tip + 2 x_in + 2 x_t) / 6.
   The aft disks clear the wing trailing edge in plan (x_t <= x_TE - gap - R); the inboard disks clear the leading edge
   (x_in >= x_LE(y_in) + gap + R); x_tip follows from the CG. The two disks on a wing half are 2R + gap apart.
6. Wing download under the front disks (strip theory): q_w = rho v^2 / 2 with v = v_i (1 + z / sqrt(z^2 + R^2))
   (momentum theory on the wake axis, z below the disk), D = Cd_90 q_w A_overlap. The overlap (how far the disk reaches
   inboard of the wing tip) is the largest one that keeps D <= 5 % of the rotor thrust.
7. Airplane-mode static stability (Etkin / Raymer ch. 16): neutral point
       h_n = h_ac,wb + eta V_h (a_t / a_w) (1 - d eps / d alpha),   d eps / d alpha = 2 a_w / (pi AR),
   a = 2 pi AR / (2 + sqrt(AR^2 + 4)) (Helmbold), fuselage shift dh = -Cm_alpha,fus / CL_alpha,w with
   Cm_alpha,fus = K_f W_f^2 L_f / (c S) per degree (Raymer eq. 16.25). The H-tail volume V_h is solved for the
   required static margin with the airplane-mode CG (nacelles tilted forward).
8. Gust load factor, FAR 23.341: n = 1 + K_g U V a rho / (2 W/S),  K_g = 0.88 mu / (5.3 + mu),  mu = 2 (W/S) / (rho c a g).
"""
import math, os, sys
import numpy as np
from concurrent.futures import ProcessPoolExecutor
from tiltcfg import params, af01_params, props_params, jload, save, PROPS, AF01, RESULTS, G0, LB
import hexrotor as hr

import atmosphere as atm   # Props program


# ------------------------------------------------------------------ polars ------------------------------------------
def _xfoil(args):
    name, re, mach, ncrit, trip = args
    os.nice(19)
    import wing_sections as ws
    d = ws.run(name, re, mach, ncrit=ncrit, xtr=ws.XTR_TRIP if trip else (1.0, 1.0))
    return name, re, trip, (d.tolist() if len(d) else [])


def wing_polars(names, re, mach, ncrit, trip=False, workers=2):
    """XFOIL polars (alpha, cl, cd, cdp, cm, xtr_top, xtr_bot), sorted by alpha. Cached by (name, Re rounded to 1e4,
    free or tripped transition). Names are NACA codes or coordinate files in geometry/airfoils (wing_sections.py)."""
    cache = os.path.join(RESULTS, "wing_polars.json")
    data = jload(cache) if os.path.exists(cache) else {}
    key = lambda n, r, t: f"{n}@{round(r, -4):.0f}" + ("@trip" if t else "")
    jobs = [(n, re, mach, ncrit, trip) for n in names if key(n, re, trip) not in data]
    if jobs:
        import multiprocessing as mp
        with ProcessPoolExecutor(max_workers=workers, mp_context=mp.get_context("fork")) as ex:
            for n, r, t, rows in ex.map(_xfoil, jobs):
                data[key(n, r, t)] = sorted(rows)
        save("wing_polars.json", data)
    return {n: np.array(data[key(n, re, trip)]) for n in names}


def polar_summary(name, P):
    if len(P) < 10: return None
    a, cl, cd, cm = P[:, 0], P[:, 1], P[:, 2], P[:, 4]
    i = int(np.argmax(cl))
    lin = (a >= -2) & (a <= 4)
    slope, a0 = np.polyfit(a[lin], cl[lin], 1)
    import wing_sections as ws
    tc = round(ws.thickness(name), 4)
    return {"name": name, "tc": tc, "clmax": float(cl[i]), "alpha_clmax": float(a[i]), "cl_alpha_per_deg": float(slope),
            "stall_found": bool(i < len(a) - 2),                     # peak inside the sweep, not at its 20 deg end
            "alpha_L0": float(-a0 / slope), "cm0": float(np.interp(0.0, cl, cm)) if np.all(np.diff(cl[: i + 1]) > -0.05) else float(cm[np.argmin(abs(cl))]),
            "a": a, "cl": cl, "cd": cd, "cm": cm, "i_max": i}


def cd_at_cl(s, cl):
    """Profile drag at a lift coefficient, on the attached branch (alpha below clmax)."""
    i = s["i_max"]
    cl_, cd_ = s["cl"][: i + 1], s["cd"][: i + 1]
    o = np.argsort(cl_)
    return float(np.interp(cl, cl_[o], cd_[o]))


# ------------------------------------------------------------------ helpers -----------------------------------------
def helmbold(AR):          # 3-D lift slope per radian, low-sweep wing (Helmbold / DATCOM form)
    return 2 * math.pi * AR / (2 + math.sqrt(AR * AR + 4))


def cf_turb(re):           # Raymer eq. 12.27 (M ~ 0)
    return 0.455 / math.log10(re) ** 2.58


def disk_wing_overlap_area(y_hub, x_hub, R, b, c, sweep, n=400):
    """Plan area of the wing (|y| <= b/2, chord band from the local LE to TE) inside the disk centred (x_hub, y_hub)."""
    xs = np.linspace(x_hub - R, x_hub + R, n); ys = np.linspace(y_hub - R, y_hub + R, n)
    X, Y = np.meshgrid(xs, ys)
    inside = (X - x_hub) ** 2 + (Y - y_hub) ** 2 <= R * R
    xqc = np.abs(Y) * math.tan(math.radians(-sweep))            # forward sweep: the quarter-chord line moves forward
    on_wing = (np.abs(Y) <= b / 2) & (X <= xqc + 0.25 * c) & (X >= xqc - 0.75 * c)
    dA = (xs[1] - xs[0]) * (ys[1] - ys[0])
    return float(np.sum(inside & on_wing) * dA)


# ------------------------------------------------------------------ main --------------------------------------------
def derive(verbose=True):
    p, a1, pp = params(), af01_params(), props_params()
    p2 = jload(os.path.join(PROPS, "results", "phase2.json"))
    fd = p2["candidates"]["final design"]
    req01 = jload(os.path.join(AF01, "results", "requirements.json"))
    out = {"inputs_read": {"props_phase2": "Props/01_54x18_Composite/results/phase2.json",
                           "af01_requirements": "Airframe/01_Tricopter_Fuselage/results/requirements.json",
                           "af01_params": "Airframe/01_Tricopter_Fuselage/params.yaml"}}

    hot = pp["atmospheres"][pp["design_atmosphere"]]
    air = atm.state(hot["temp_c"], hot["alt_m"])
    rho, mu, a_snd = air["rho"], air["mu"], air["a"]
    v = p["vehicle"]
    W = v["mtow_lb"] * LB * G0
    V = v["cruise_speed_ms"]
    q = 0.5 * rho * V * V
    R = a1["vehicle"]["rotor_radius_m"]; D = 2 * R
    NR = v["n_rotors"]
    T_h = W / NR
    out["air"] = {"name": hot["label"], "rho": rho, "mu": mu, "a": a_snd}
    out["W_n"], out["q_cruise_pa"], out["T_hover_n"] = W, q, T_h

    # ---- hex rotor and motor (Props entry 46 row): loaded speed limit and torque from that row; hover re-solved
    el = pp["electrical"]
    HX = hr.setup(); rp = p["rotors"]
    rpm_max = HX["rpm_max"]
    hov = hr.hover("hex", T_h)
    cap = hr.thrust_cap("hex")
    out["motor"] = {"name": rp["motor"], "rpm_max": rpm_max, "Q_max_nm": HX["Q_max"], "motor_kg": HX["motor_kg"],
                    "source": f"Props results/explore/{rp['source_entry']}.json (cap {rp['cap']})"}
    out["rotor"] = {"blade": "Props entry 46 hex blade (24xx)", "solidity": HX["solidity"], "hover_rpm": hov["rpm"], "hover_rpm_props": HX["rpm_hover_row"],
                    "hover_P_w": hov["P"], "hover_Q_nm": hov["Q"], "thrust_cap_n": cap["T"], "T_over_W_cap": NR * cap["T"] / W,
                    "FoM": (T_h ** 1.5 / math.sqrt(2 * rho * math.pi * R * R)) / hov["P"]}
    h54 = hr.hover("54x18", T_h); cap54 = hr.thrust_cap("54x18")
    out["rotor"]["cap_limit"] = cap["limit"]
    out["rotor_54x18_on_mn1123"] = {"hover_rpm": h54["rpm"], "hover_P_w": h54["P"], "hover_Q_nm": h54["Q"],
                                    "FoM": (T_h ** 1.5 / math.sqrt(2 * rho * math.pi * R * R)) / h54["P"],
                                    "thrust_cap_n": cap54["T"], "cap_rpm": cap54["rpm"], "cap_limit": cap54["limit"], "T_over_W_cap": NR * cap54["T"] / W}
    cx = hr.coax("hex", 2 * T_h)
    out["coax_alternative"] = {"thrust_pair_n": 2 * T_h, "P_pair_w": cx["P"], "P_two_isolated_w": cx["P_isolated_pair"], "power_ratio": cx["power_ratio"],
                               "kappa_int": cx["kappa_int"], "split_upper": cx["split_upper"], "rpm_upper": cx["rpm_upper"], "rpm_lower": cx["rpm_lower"],
                               "h_m": cx["h"], "hover_total_w": 2 * cx["P"] + 2 * hov["P"], "hover_planar_w": NR * hov["P"],
                               "note": "costed and rejected (user, 2026-11-20): four tilting rotors planar on the wing instead"}

    # ---- V-22 proportions (look)
    g = p["v22"]
    out["v22"] = {"hub_spacing_over_D": (g["width_rotors_m"] - g["rotor_D_m"]) / g["rotor_D_m"],
                  "fuselage_L_over_D": g["fuselage_L_m"] / g["rotor_D_m"],
                  "AR": g["wing_span_m"] ** 2 / g["wing_area_m2"],
                  "chord_over_D": g["wing_area_m2"] / g["wing_span_m"] / g["rotor_D_m"],
                  "wing_loading_n_m2": 27443 * G0 / g["wing_area_m2"]}   # 27,443 kg MTOW (VTOL), NAVAIR fact file
    hubs_v22 = out["v22"]["hub_spacing_over_D"] * D
    S_v22 = out["v22"]["chord_over_D"] * D * hubs_v22
    out["v22_scaled"] = {"hub_spacing_m": hubs_v22, "wing_area_m2": S_v22,
                         "speed_for_CL1_ms": math.sqrt(2 * W / (rho * S_v22 * 1.0))}
    R = HX["R"]; D = 2 * R

    # ---- tilting rotors in axial flight (airplane mode): Props BEMT at the motor limit, both candidate blades
    import bemt
    from scipy.optimize import brentq
    n_max = rpm_max / 60
    out["prop_airplane"] = {}
    for bn in ("hex", "54x18"):
        bb, dbb = hr.blade(bn)
        ax_ = lambda vv, rpm=rpm_max: bemt.axial(bb, dbb, HX["air"], rpm, vv)
        v0 = brentq(lambda vv: ax_(vv)["T"], 1.0, 60.0, xtol=0.01)
        out["prop_airplane"][bn] = {"v_zero_thrust_at_rpm_max": v0, "J_zero_thrust": v0 / (n_max * D)}
    tilt_b = rp["tilt_blade"]
    bt, dbt = hr.blade(tilt_b)
    def thrust_rpm(rpm, vv): return bemt.axial(bt, dbt, HX["air"], rpm, vv)

    # ---- 1-2. airfoil and wing area
    # Each section gets two XFOIL polars: free transition (e^N, ncrit 9) and tripped (5 % / 10 % chord). The wing is
    # sized on the TRIPPED clmax (a dirty or rain-wet wing must still lift; for these sections it is 0-3 % below the
    # free value), cruise drag uses the free polar (a clean composite wing). Pick: the largest tripped clmax among the
    # sections thick enough for the spar box, i.e. the smallest wing, with the stall found inside the sweep.
    w = p["wing"]
    AR = w["aspect_ratio"]
    S_guess = 4.0
    for _ in range(4):
        c_guess = math.sqrt(S_guess / AR)
        re = rho * V * c_guess / mu
        pol = wing_polars(w["airfoils"], re, V / a_snd, w["ncrit"])
        pol_t = wing_polars(w["airfoils"], re, V / a_snd, w["ncrit"], trip=True)
        cands = []
        for n, P in pol.items():
            s, st_ = polar_summary(n, P), polar_summary(n, pol_t[n])
            if s is None or st_ is None: continue
            CLmax = w["clmax_3d_factor"] * st_["clmax"]
            CL = CLmax / w["stall_margin"] ** 2
            S = W / (q * CL)
            cands.append(dict(s, clmax_free=s["clmax"], clmax=st_["clmax"], stall_found=st_["stall_found"],
                              alpha_clmax=st_["alpha_clmax"], alpha_L0_trip=st_["alpha_L0"], cm0_trip=st_["cm0"],
                              CLmax3d=CLmax, CL_cruise=CL, S=S, cd_cruise=cd_at_cl(s, CL), cd_cruise_trip=cd_at_cl(st_, CL)))
        for c_ in cands:
            c_["DA_wing"] = c_["S"] * (c_["cd_cruise"] + c_["CL_cruise"] ** 2 / (math.pi * w["e_oswald"] * AR))
        ok = [c_ for c_ in cands if c_["tc"] >= w["t_c_min"] and c_["stall_found"]]
        best = max(ok, key=lambda c_: c_["clmax"])
        if abs(best["S"] / S_guess - 1) < 0.01: break
        S_guess = best["S"]
    S, CL = best["S"], best["CL_cruise"]
    b = math.sqrt(AR * S); c = S / b
    # Incidence: the fuselage flies level at the cruise point, so the wing root chord is set at the wing angle of attack
    # that gives CL_cruise. Untwisted wing: CL = a_w (alpha - alpha_L0), alpha_L0 of the section (tripped polar: the
    # fully turbulent CFD agrees with it, the free polar sits 13-17 % high in lift), a_w the Helmbold 3-D slope.
    aw_ = helmbold(AR)
    inc = best["alpha_L0_trip"] + math.degrees(CL / aw_)
    out["wing_re"] = re
    out["airfoil_table"] = [{k: c_[k] for k in ("name", "tc", "clmax", "clmax_free", "stall_found", "alpha_clmax", "alpha_L0_trip",
                                                 "cm0", "CLmax3d", "CL_cruise", "S", "cd_cruise", "cd_cruise_trip", "DA_wing")}
                            for c_ in sorted(cands, key=lambda c_: -c_["clmax"])]
    out["wing"] = {"airfoil": best["name"], "tc": best["tc"], "S": S, "b": b, "c": c, "AR": AR, "CL_cruise": CL,
                   "CLmax3d": best["CLmax3d"], "v_stall_ms": math.sqrt(2 * W / (rho * S * best["CLmax3d"])),
                   "cd_profile": best["cd_cruise"], "cm0": best["cm0"], "wing_loading_n_m2": W / S,
                   "sweep_deg": w["sweep_deg"], "dihedral_deg": w["dihedral_deg"],
                   "a_per_rad": aw_, "incidence_deg": inc, "alpha_L0_deg": best["alpha_L0_trip"],
                   "alpha_stall_3d_deg": best["alpha_L0_trip"] + math.degrees(best["CLmax3d"] / aw_)}

    # ---- 5 + 7. layout and airplane-mode stability, solved together
    # Given the tail volume (Raymer), the neutral point is fixed; the CG must sit SM ahead of it in airplane mode. The
    # airplane CG is the hover CG plus the forward swing of the four tilting heads. Equal thrust on six rotors puts the
    # hover CG at the mean hub x. The aft hubs are pinned just behind the wing TE, the inboard hubs just ahead of the LE
    # (disk clear of the wing in plan: no download), so the tip hubs follow:
    #     x_tip = 3 x_cg,hover - x_in - x_t
    nac, t, fz = p["nacelle"], p["tail"], p["fuselage"]
    a01m = a1["masses"]
    m = v["mtow_lb"] * LB
    m_head = HX["motor_kg"] + 2 * a01m["blade_kg"] + a01m["hub_kg"] + a01m["motor_mount_kg"] + nac["head_fairing_kg"]
    arm = nac["head_arm_m"]
    dx_conv = 4 * m_head * arm / m                                  # hubs: above the pivots (hover) -> ahead of them (airplane)
    dz_conv = -4 * m_head * arm / m
    x_mac = (b / 4) * math.tan(math.radians(-w["sweep_deg"]))      # qc of the MAC (constant chord: MAC at b/4)
    x_le_mac = x_mac + 0.25 * c
    h = lambda x: (x_le_mac - x) / c
    aw = helmbold(AR); at = helmbold(t["horizontal_AR"])
    deps = 2 * aw / (math.pi * AR)
    Lf = fz["length_over_D"] * D; Wf = fz["width_m"]
    K_f = 0.015                                                    # Raymer fig. 16.14 at ~40-50 % (read off the plot)
    Cma_fus = K_f * Wf ** 2 * Lf / (c * S)                         # per degree
    dh_fus = Cma_fus / (aw * math.pi / 180)
    h_acwb = 0.25 + dh_fus
    V_h = t["horizontal_volume"]
    h_n = h_acwb + t["eta_tail"] * V_h * (at / aw) * (1 - deps)
    h_cg = h_n - t["static_margin"]
    x_cg_air = x_le_mac - h_cg * c
    x_cg_hover = x_cg_air - dx_conv
    x_TE_root = -0.75 * c
    x_t = x_TE_root - t["rotor_gap_m"] - R
    y_t = R + t["aft_rotor_gap_m"] / 2                              # two aft disks side by side, tip gap over the boom
    tsw = math.tan(math.radians(-w["sweep_deg"]))
    x_tip_qc = (b / 2) * tsw
    g_rr, g_le = rp["rotor_gap_m"], rp["inboard_le_gap_m"]
    S_h = 0.5
    for _ in range(50):
        c_h = math.sqrt(S_h / t["horizontal_AR"])
        x_ht = x_t - R - t["rotor_gap_m"] - 0.25 * c_h             # H-tail aft of the aft disks, no download
        l_h = x_mac - x_ht
        S_h_new = V_h * S * c / l_h
        if abs(S_h_new - S_h) < 1e-6: break
        S_h = S_h_new
    S_v = t["vertical_volume"] * S * b / l_h

    # ---- 6. hub span positions: the tip hub by overlap vs download (as Airframe 02), the inboard hub 2R + gap inboard
    # of it (side by side in span even though the two are staggered in x), its disk ahead of the leading edge. Iterated: x_tip depends on
    # x_in, which depends on y_in (forward sweep moves the LE), which depends on the tip hub.
    vi = math.sqrt(T_h / (2 * rho * math.pi * R * R))
    v_w = vi * (1 + arm / math.sqrt(arm * arm + R * R))
    q_w = 0.5 * rho * v_w ** 2
    y_tip = b / 2 + 0.5 * R
    y_in = y_tip - (2 * R + g_rr)
    for it_ in range(60):
        x_in = abs(y_in) * tsw + 0.25 * c + g_le + R                 # disk clear of the local leading edge
        x_tip = 3 * x_cg_hover - x_in - x_t
        dy_need = 2 * R + g_rr                                       # side by side (user): full span clearance, so neither
                                                                     # disk sits in the other's wake in airplane mode
        scan = []
        for ov in np.linspace(0.0, 1.0, 41):
            yh = b / 2 + R * (1 - ov)
            A_ = disk_wing_overlap_area(yh, x_tip, R, b, c, w["sweep_deg"])
            Dn = nac["download_cd_wing"] * q_w * A_
            scan.append({"overlap": float(ov), "y_hub": yh, "A_m2": A_, "download_n": Dn, "frac": Dn / T_h})
        ok_ = [s_ for s_ in scan if s_["frac"] <= nac["download_max_frac"]]
        pick = max(ok_, key=lambda s_: s_["overlap"])
        x_le_tip = x_tip_qc + 0.25 * c
        if x_tip + arm < x_le_tip + g_rr:
            # airplane mode: the tilted disk stands at x_tip + arm, behind the tip leading edge, so any inboard overlap
            # would put the blades through the wing: the disk goes fully outboard of the tip (plus the gap)
            yh = b / 2 + R + g_rr
            pick = {"overlap": -g_rr / R, "y_hub": yh, "A_m2": 0.0, "download_n": 0.0, "frac": 0.0,
                    "why": f"airplane-mode blade clearance: disk plane x {x_tip + arm:+.3f} behind the tip LE {x_le_tip:+.3f}"}
        y_in_new = pick["y_hub"] - dy_need
        done = abs(pick["y_hub"] - y_tip) < 1e-7 and abs(y_in_new - y_in) < 1e-7
        y_tip, y_in = pick["y_hub"], y_in_new
        if done: break
    x_in = abs(y_in) * tsw + 0.25 * c + g_le + R
    x_tip = 3 * x_cg_hover - x_in - x_t
    A_in = disk_wing_overlap_area(y_in, x_in, R, b, c, w["sweep_deg"])
    v22 = disk_wing_overlap_area(b / 2, x_tip_qc - 0.125 * c, R, b, c, w["sweep_deg"])
    out["download"] = {"vi_ms": vi, "z_m": arm, "v_wing_ms": v_w, "q_wing_pa": q_w, "scan": scan, "chosen": pick,
                       "inboard": {"A_m2": A_in, "download_n": nac["download_cd_wing"] * q_w * A_in, "frac": nac["download_cd_wing"] * q_w * A_in / T_h},
                       "v22_like": {"A_m2": v22, "frac": nac["download_cd_wing"] * q_w * v22 / T_h,
                                    "note": "hub on the wing-tip spar, as on the V-22"}}
    pod_len = (x_tip - (x_tip_qc - 0.75 * c)) + 0.10                 # tip pod from behind the wing TE to the head pivot
    x_spar_in = abs(y_in) * tsw - c * ((p["wing"]["spar_front_xc"] + p["wing"]["spar_rear_xc"]) / 2 - 0.25)
    pylon_len = x_in - x_spar_in                                    # inboard pylon from the spar box forward to the pivot
    hub_gap = math.hypot(x_in - x_tip, y_tip - y_in) - 2 * R
    xs_h = [x_tip, x_tip, x_in, x_in, x_t, x_t]
    out["layout"] = {"x_front_hub": x_tip, "y_front_hub": y_tip, "x_inboard_hub": x_in, "y_inboard_hub": y_in, "x_tail_hub": x_t, "y_tail_hub": y_t,
                     "x_cg_hover": x_cg_hover, "x_cg_hub_mean": sum(xs_h) / 6, "tip_inboard_disk_gap_m": hub_gap,
                     "inboard_disk_inner_edge_y": y_in - R,
                     "hub_spacing_front_m": 2 * y_tip, "head_ahead_of_tip_LE_m": x_tip - (x_tip_qc + 0.25 * c), "pod_length_m": pod_len,
                     "inboard_pylon_length_m": pylon_len, "overall_width_m": 2 * (y_tip + R), "x_tip_qc": x_tip_qc}
    x_nose = x_cg_hover + 0.45 * Lf                                # payload bay centred on the CG
    out["layout"]["inboard_disk_vs_fuselage"] = "clear" if y_in - R > Wf / 2 else "OVERLAPS the fuselage"
    out["layout"]["inboard_disk_ahead_of_nose_m"] = (x_in - R) - x_nose
    # aft-disk download: each aft disk (centre y = +-y_t) over the boom and the aft fuselage cone (strip theory, as
    # Airframe 02 with the lateral offset): overlap chord at station x is the y-interval shared by the disk and the body.
    sel = os.path.join(os.path.dirname(RESULTS), "designs", "selected.json")
    D_boom = jload(sel)["boom"]["D"] if os.path.exists(sel) else 0.12
    z_t = t["pylon_height_m"] + 0.10
    v_t = vi * (1 + z_t / math.sqrt(z_t ** 2 + R ** 2)); q_t = 0.5 * rho * v_t ** 2
    x_tail_f = x_nose - Lf
    xs_ = np.linspace(x_t - R, x_t + R, 400); dx_s = xs_[1] - xs_[0]
    half = np.sqrt(np.clip(R ** 2 - (xs_ - x_t) ** 2, 0, None))
    s_f = (x_nose - xs_) / Lf
    w_f = np.where((s_f >= 1 - fz["tail_frac"]) & (s_f <= 1), Wf * (1 - 0.65 * (s_f - (1 - fz["tail_frac"])) / fz["tail_frac"]),
                   np.where((s_f >= 0) & (s_f < 1 - fz["tail_frac"]), Wf, 0.0))
    ov = lambda wb: np.clip(np.minimum(y_t + half, wb / 2) - np.maximum(y_t - half, -wb / 2), 0, None)
    A_f = float(np.sum(ov(w_f)) * dx_s)
    A_b = float(np.sum(np.where(xs_ < x_tail_f, ov(D_boom), 0.0)) * dx_s)
    D_tail = 0.5 * q_t * A_f + 1.17 * q_t * A_b
    out["download_tail"] = {"z_m": z_t, "q_pa": q_t, "A_fuselage_m2": A_f, "A_boom_m2": A_b, "D_boom_m": D_boom,
                            "download_n": D_tail, "frac": D_tail / T_h, "per": "each aft rotor"}
    out["download_total_frac"] = (2 * pick["download_n"] + 2 * out["download"]["inboard"]["download_n"] + 2 * D_tail) / W
    out["stability"] = {"x_cg_air": x_cg_air, "dx_conversion": dx_conv, "dz_conversion": dz_conv, "h_cg_air": h_cg,
                        "h_cg_hover": h(x_cg_hover), "h_ac_wb": h_acwb, "dh_fuselage": dh_fus, "K_f": K_f,
                        "root_qc_frac_of_fuselage": x_nose / Lf, "m_head": m_head, "n_tilt_heads": 4,
                        "a_w": aw, "a_t": at, "deps_dalpha": deps, "V_h": V_h, "S_h": S_h, "c_h": c_h, "b_h": S_h / c_h,
                        "x_ht_ac": x_ht, "l_h": l_h, "S_v_total": S_v, "h_n": h_n, "static_margin": h_n - h_cg,
                        "note": "prop/nacelle normal force (destabilising in airplane mode) is not in this estimate"}
    out["fuselage"] = {"L": Lf, "W": Wf, "H": fz["height_m"], "x_nose": x_nose, "x_tail": x_nose - Lf}

    # ---- 3. drag build-up, airplane mode, 25 m/s hot day
    ReL = lambda L: rho * V * L / mu
    parts = {}
    # fuselage
    Hf = fz["height_m"]
    d_eq = math.sqrt(4 / math.pi * Wf * Hf); f_ = Lf / d_eq
    Swet_f = 3.4 * (0.8 * Lf * Wf + 0.8 * Lf * Hf) / 2
    parts["fuselage"] = cf_turb(ReL(Lf)) * (1 + 60 / f_ ** 3 + f_ / 400) * Swet_f
    u = math.radians(15.0)                                          # V-22-style upswept aft ramp (look assumption)
    parts["fuselage upsweep"] = 3.83 * u ** 2.5 * (math.pi / 4 * Wf * Hf)   # Raymer eq. 12.36
    # tip pods (fixed): cylinder from behind the wing TE to the head, plus the head in airplane mode; inboard pylons
    dn, ln = nac["pod_diameter_m"], pod_len + arm
    parts["tip nacelles x2"] = 2 * 1.3 * cf_turb(ReL(ln)) * (1 + 0.35 / (ln / dn)) * (math.pi * dn * ln)
    dpy, lpy = nac["pylon_diameter_m"], pylon_len + arm
    parts["inboard pylons x2"] = 2 * 1.3 * cf_turb(ReL(lpy)) * (1 + 0.35 / (lpy / dpy)) * (math.pi * dpy * lpy)
    # tail boom
    lb = x_cg_hover - 0.55 * Lf - x_ht + 0.3; db_ = 0.10
    parts["tail boom"] = cf_turb(ReL(max(lb, 0.2))) * (1 + 60 / (lb / db_) ** 3 + (lb / db_) / 400) * math.pi * db_ * lb
    # tail surfaces
    ff_t = 1 + 0.6 / 0.3 * t["tc_tail"] + 100 * t["tc_tail"] ** 4
    c_v = math.sqrt(S_v / 2 / 1.5)
    parts["H-tail"] = cf_turb(ReL(c_h)) * ff_t * 2.04 * S_h * 1.05
    parts["fins x2"] = cf_turb(ReL(c_v)) * ff_t * 2.04 * S_v * 1.05
    # tail rotor stopped, blades parked fore-aft; hub + pylon as a bluff body
    sig = HX["solidity"]
    c75 = float(np.interp(0.75 * R, hr.blade("hex")[0].r_def, hr.blade("hex")[0].c_def))
    parts["aft rotor blades x2 (parked)"] = 2 * cf_turb(ReL(c75)) * (1 + 0.6 / 0.3 * 0.12 + 100 * 0.12 ** 4) * 2 * sig * math.pi * R * R
    parts["aft rotor hubs + pylons x2"] = 2 * 1.0 * 0.10 * t["pylon_height_m"]   # Cd 1.0 on 0.1 m x pylon height (assumption)
    parts["aft cross-beam"] = 0.15 * 0.06 * 2 * y_t                           # 60 mm tube in a strut fairing: Cd 0.15 on frontal area incl. interference (assumption; Hoerner faired strut ~0.06-0.1)
    # fixed tricycle gear: three 150 x 60 mm wheels (Raymer table 12.6 D/q = 0.25 per frontal area) + round struts
    parts["gear"] = 3 * 0.25 * 0.15 * 0.06 + 3 * 1.17 * 0.03 * 0.30
    parasite_bodies = sum(parts.values())
    parts["leakage + protuberances (10 %)"] = 0.10 * parasite_bodies
    wing_profile = best["cd_cruise"] * S
    induced = CL ** 2 / (math.pi * w["e_oswald"] * AR) * S
    CDA = parasite_bodies * 1.10 + wing_profile + induced
    Dr = q * CDA
    out["drag"] = {"parts_m2": parts, "wing_profile_m2": wing_profile, "induced_m2": induced, "CDA_total_m2": CDA,
                   "drag_n": Dr, "L_over_D": W / Dr,
                   "CD0": (parasite_bodies * 1.10 + wing_profile) / S}
    CD0 = out["drag"]["CD0"]
    out["drag"]["CL_LDmax"] = math.sqrt(math.pi * w["e_oswald"] * AR * CD0)
    out["drag"]["LD_max"] = 0.5 * math.sqrt(math.pi * w["e_oswald"] * AR / CD0)

    # ---- 4. cruise thrust and power: four tilting rotors in axial flight (airplane mode)
    T_av = 4 * thrust_rpm(rpm_max, V)["T"]
    elec = el["eta_motor_esc"] * el["eta_battery_wiring"]
    mc = fd["cruise"]["15"]
    out["cruise"] = {"V": V, "tilt_blade": tilt_b, "thrust_available_n": T_av, "thrust_required_n": Dr, "thrust_margin": T_av / Dr,
                     "multirotor_15ms_shaft_w": mc["shaft_total"], "multirotor_wh_per_km": mc["shaft_total"] / elec / (15 * 3.6),
                     "airplane_mode_possible": bool(T_av > Dr)}
    if T_av > Dr:
        rpm_cr = brentq(lambda rpm: 4 * thrust_rpm(rpm, V)["T"] - Dr, 300.0, rpm_max)
        a_ = thrust_rpm(rpm_cr, V)
        P_shaft = 4 * a_["P"]
        out["cruise"].update(rpm=rpm_cr, J=V / (rpm_cr / 60 * D), shaft_power_w=P_shaft, prop_eta=Dr * V / P_shaft,
                             battery_power_w=P_shaft / elec, wh_per_km=P_shaft / elec / (V * 3.6),
                             tip_mach=math.hypot(2 * math.pi * rpm_cr / 60 * R, V) / a_snd)
    else:
        out["cruise"]["note"] = (f"the {tilt_b} blade's zero-thrust speed at the motor limit is "
                                 f"{out['prop_airplane'][tilt_b]['v_zero_thrust_at_rpm_max']:.1f} m/s: no airplane-mode cruise at {V:.0f} m/s; "
                                 "the forward-flight trim (transition.py) finds the partial-conversion cruise")
        out["cruise"].update(rpm=rpm_max, shaft_power_w=None)

    # ---- 8. gust load factor (FAR 23.341)
    WS = W / S
    mu_g = 2 * WS / (rho * c * aw * G0)
    Kg = 0.88 * mu_g / (5.3 + mu_g)
    U = p["loads"]["gust_ms"]
    n_gust = 1 + Kg * U * V * aw * rho / (2 * WS)
    out["gust"] = {"mu_g": mu_g, "K_g": Kg, "U_ms": U, "n_gust": n_gust,
                   "n_design_airplane": max(n_gust, p["loads"]["n_z_maneuver_airplane"])}

    # ---- nacelle tilt actuator torque (hand estimate, sizes the assumed actuator)
    Jp = 2 * a01m["blade_kg"] * R ** 2 / 3
    om = 2 * math.pi * rpm_max / 60
    gyro = Jp * om * math.radians(60.0)          # 60 deg/s body pitch/yaw rate (assumption)
    weight_mom = m_head * G0 * arm * 0.6   # head CG ~60 % of the way from pivot to hub (motor is the bulk)
    out["tilt_actuator"] = {"rotor_polar_inertia": Jp, "gyro_moment_nm": gyro, "weight_moment_nm": weight_mom,
                            "hold_torque_nm": gyro + weight_mom}
    out["v_wing_area_ratio_v22"] = S / S_v22
    save("sizing.json", out)
    if verbose: report(out)
    return out


def report(o):
    w, L, s, d, cr, ro, cx = o["wing"], o["layout"], o["stability"], o["drag"], o["cruise"], o["rotor"], o["coax_alternative"]
    print(f"Hex rotor: hover {ro['hover_rpm']:.1f} rpm (Props row {ro['hover_rpm_props']:.1f}), {ro['hover_P_w']:.0f} W, FoM {ro['FoM']:.3f}, "
          f"cap {ro['thrust_cap_n']:.0f} N (T/W {ro['T_over_W_cap']:.2f}); motor limit {o['motor']['rpm_max']:.0f} rpm")
    print(f"Coax alternative: pair {cx['P_pair_w']:.0f} W vs two isolated {cx['P_two_isolated_w']:.0f} W (x{cx['power_ratio']:.3f}, kappa_int {cx['kappa_int']:.3f}); "
          f"vehicle {cx['hover_total_w']:.0f} W vs planar {cx['hover_planar_w']:.0f} W")
    print("Airplane-mode zero-thrust speed at the motor limit:", {k: round(v["v_zero_thrust_at_rpm_max"], 1) for k, v in o["prop_airplane"].items()})
    print("Airfoils (Re %.2e):" % o["wing_re"])
    for r in o["airfoil_table"][:4]:
        print(f"  {r['name']:9s} t/c {r['tc']:.2f} clmax {r['clmax']:.3f} CL_cr {r['CL_cruise']:.3f} S {r['S']:.2f} m2 cd {r['cd_cruise']:.5f}")
    print(f"Wing {w['airfoil']} (incidence {w['incidence_deg']:.1f} deg): S {w['S']:.2f} m2, b {w['b']:.2f} m, c {w['c']:.3f} m, CL {w['CL_cruise']:.3f}, Vs {w['v_stall_ms']:.1f} m/s")
    ch, ib = o["download"]["chosen"], o["download"]["inboard"]
    print(f"Download: tip overlap {ch['overlap']:.2f} R -> {ch['download_n']:.0f} N ({100*ch['frac']:.1f} %); inboard {ib['download_n']:.1f} N ({100*ib['frac']:.1f} %)")
    dt = o["download_tail"]
    print(f"Aft-disk download each: fuselage {dt['A_fuselage_m2']:.3f} m2 + boom {dt['A_boom_m2']:.3f} m2 -> {dt['download_n']:.1f} N ({100*dt['frac']:.1f} %); vehicle {100*o['download_total_frac']:.1f} %")
    print(f"Layout: tip hubs x {L['x_front_hub']:+.3f} y +-{L['y_front_hub']:.3f}; inboard x {L['x_inboard_hub']:+.3f} y +-{L['y_inboard_hub']:.3f} "
          f"(disk gap {L['tip_inboard_disk_gap_m']:.3f}, inner edge y {L['inboard_disk_inner_edge_y']:.2f}, {L['inboard_disk_vs_fuselage']}, ahead of nose {L['inboard_disk_ahead_of_nose_m']:+.2f}); "
          f"aft x {L['x_tail_hub']:+.3f} y +-{L['y_tail_hub']:.3f}; CG {L['x_cg_hover']:+.3f} (hub mean {L['x_cg_hub_mean']:+.3f}); pylon {L['inboard_pylon_length_m']:.2f} m, width {L['overall_width_m']:.2f} m")
    print(f"Stability: h_cg {s['h_cg_air']:.3f} V_h {s['V_h']:.3f} S_h {s['S_h']:.3f} m2 l_h {s['l_h']:.2f} SM {s['static_margin']:.3f}, dx_conv {s['dx_conversion']:.3f}")
    print("Drag parts (m2): " + ", ".join(f"{k} {v:.4f}" for k, v in d["parts_m2"].items()))
    print(f"  CDA {d['CDA_total_m2']:.3f} m2 -> D {d['drag_n']:.0f} N, L/D {d['L_over_D']:.1f}")
    print(f"Cruise ({cr['tilt_blade']} blade): thrust avail {cr['thrust_available_n']:.0f} N vs req {cr['thrust_required_n']:.0f} N; "
          + (f"{cr['rpm']:.0f} rpm, P_shaft {cr['shaft_power_w']:.0f} W, eta {cr['prop_eta']:.2f}, {cr['wh_per_km']:.1f} Wh/km" if cr["airplane_mode_possible"] else cr["note"]))
    g = o["gust"]
    print(f"Gust n {g['n_gust']:.2f}; tilt actuator hold {o['tilt_actuator']['hold_torque_nm']:.1f} N m")


if __name__ == "__main__":
    derive()

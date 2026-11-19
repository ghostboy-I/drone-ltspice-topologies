"""Conceptual sizing of the Osprey-style tilt-tricopter: wing, rotor layout, tail, drag, cruise thrust, download, gusts.

Everything here is a hand calculation (textbook methods, each stated where it is used); the frame FE model
(tiltframe.py) and the CFD cases check the parts the hand methods cannot.

Coordinates: x forward, y left, z up. Origin at the wing root quarter-chord, on the spar-box axis.

1. Wing section (XFOIL, Re and Mach of the cruise point, hot day). Candidates are NACA 4- and 5-digit sections with
   t/c >= 15 % (spar depth). The section sets clmax (stall) and cd at the cruise cl (profile drag).
2. Wing area: the smallest wing that cruises at >= 1.2 x its stall speed (light-aircraft practice, Raymer ch. 5):
       CL_max,3D = 0.9 clmax  (Raymer eq. 12.15, unswept, untwisted),   CL_cr = CL_max,3D / 1.2^2,
       S = W / (q CL_cr),   q = rho V^2 / 2.   b = sqrt(AR S) with the V-22 aspect ratio 5.5.
3. Drag build-up (Raymer ch. 12): every body gets C_f (turbulent flat plate, 0.455 / (log10 Re)^2.58) x form factor
   x wetted area x interference; the wing uses its XFOIL cd. Induced drag CL^2 / (pi e AR). Leakage + protuberances +10 %.
4. Cruise thrust: two 54 in props at the motor's speed limit, CT(J) from the prop program's own BEMT advance curve
   (Props phase2.json). Shaft power from CP(J); eta = T V / P.
5. Rotor layout in hover: equal thrust on all three rotors needs the CG at the centroid of the hub triangle,
       x_cg = (2 x_f + x_t) / 3.
   The tail disk must clear the wing trailing edge in plan (no download): x_t <= x_TE - gap - R.
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

import atmosphere as atm   # Props program


# ------------------------------------------------------------------ polars ------------------------------------------
def _xfoil(args):
    naca, re, mach, ncrit = args
    os.nice(19)
    import airfoils
    d = airfoils.run_xfoil(naca, re, mach, a_pos=(0.0, 20.0), a_neg=(-0.5, -6.0), step=0.5, ncrit=ncrit, iters=200)
    return naca, re, (d.tolist() if len(d) else [])


def wing_polars(names, re, mach, ncrit, workers=2):
    """XFOIL polars (alpha, cl, cd, cdp, cm, xtr_top, xtr_bot), sorted by alpha. Cached by (name, Re rounded to 1e4)."""
    cache = os.path.join(RESULTS, "wing_polars.json")
    data = jload(cache) if os.path.exists(cache) else {}
    jobs = [(n, re, mach, ncrit) for n in names if f"{n}@{round(re, -4):.0f}" not in data]
    if jobs:
        import multiprocessing as mp
        with ProcessPoolExecutor(max_workers=workers, mp_context=mp.get_context("fork")) as ex:
            for n, r, rows in ex.map(_xfoil, jobs):
                data[f"{n}@{round(r, -4):.0f}"] = sorted(rows)
        save("wing_polars.json", data)
    return {n: np.array(data[f"{n}@{round(re, -4):.0f}"]) for n in names}


def polar_summary(name, P):
    if len(P) < 10: return None
    a, cl, cd, cm = P[:, 0], P[:, 1], P[:, 2], P[:, 4]
    i = int(np.argmax(cl))
    lin = (a >= -2) & (a <= 4)
    slope, a0 = np.polyfit(a[lin], cl[lin], 1)
    tc = int(name[-2:]) / 100
    return {"name": name, "tc": tc, "clmax": float(cl[i]), "alpha_clmax": float(a[i]), "cl_alpha_per_deg": float(slope),
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
    T_h = W / 3
    out["air"] = {"name": hot["label"], "rho": rho, "mu": mu, "a": a_snd}
    out["W_n"], out["q_cruise_pa"], out["T_hover_n"] = W, q, T_h

    # ---- motor speed limit (same rule as Props phase2.motor_tw): k_load KV V_sag
    el = pp["electrical"]
    kv = 38.0                                                          # U15XL KV38 (Props catalog tmotor_u15xl_kv38)
    rpm_max = el["k_load"] * kv * el["cells_baseline"] * el["v_cell_sag"]
    out["motor"] = {"kv": kv, "volts_sag": el["cells_baseline"] * el["v_cell_sag"], "k_load": el["k_load"], "rpm_max": rpm_max,
                    "rpm_mach_limit": fd["rpm_mach_limit"]}

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

    # ---- prop in axial flight (airplane mode): CT(J), CP(J) from the prop program's BEMT
    adv = p2["axial_advance_curves"]
    J_ = np.array([x["J"] for x in adv]); CT_ = np.array([x["CT"] for x in adv]); CP_ = np.array([x["CP"] for x in adv])
    J_zero = float(np.interp(0.0, CT_[::-1], J_[::-1]))
    n_max = rpm_max / 60
    def thrust(n, vv): return float(np.interp(vv / (n * D), J_, CT_)) * rho * n * n * D ** 4
    out["prop_airplane"] = {"J_zero_thrust": J_zero, "v_zero_thrust_at_rpm_max": J_zero * n_max * D,
                            "source": "Props phase2.json axial_advance_curves (BEMT at hover rpm, hot day)"}

    # ---- 1-2. airfoil and wing area
    w = p["wing"]
    AR = w["aspect_ratio"]
    S_guess = 4.0
    for _ in range(3):
        c_guess = math.sqrt(S_guess / AR)
        re = rho * V * c_guess / mu
        pol = wing_polars(w["airfoils"], re, V / a_snd, w["ncrit"])
        cands = []
        for n, P in pol.items():
            s = polar_summary(n, P)
            if s is None: continue
            CLmax = w["clmax_3d_factor"] * s["clmax"]
            CL = CLmax / w["stall_margin"] ** 2
            S = W / (q * CL)
            cands.append(dict(s, CLmax3d=CLmax, CL_cruise=CL, S=S, cd_cruise=cd_at_cl(s, CL)))
        ok = [c_ for c_ in cands if c_["tc"] >= w["t_c_min"]]
        # pick: least wing drag area (S cd + induced) among the sections thick enough for the spar
        for c_ in cands:
            c_["DA_wing"] = c_["S"] * (c_["cd_cruise"] + c_["CL_cruise"] ** 2 / (math.pi * w["e_oswald"] * AR))
        best = min(ok, key=lambda c_: c_["DA_wing"])
        if abs(best["S"] / S_guess - 1) < 0.01: break
        S_guess = best["S"]
    S, CL = best["S"], best["CL_cruise"]
    b = math.sqrt(AR * S); c = S / b
    out["wing_re"] = re
    out["airfoil_table"] = [{k: c_[k] for k in ("name", "tc", "clmax", "alpha_clmax", "cm0", "CLmax3d", "CL_cruise", "S", "cd_cruise", "DA_wing")}
                            for c_ in sorted(cands, key=lambda c_: c_["DA_wing"])]
    out["wing"] = {"airfoil": best["name"], "tc": best["tc"], "S": S, "b": b, "c": c, "AR": AR, "CL_cruise": CL,
                   "CLmax3d": best["CLmax3d"], "v_stall_ms": math.sqrt(2 * W / (rho * S * best["CLmax3d"])),
                   "cd_profile": best["cd_cruise"], "cm0": best["cm0"], "wing_loading_n_m2": W / S,
                   "sweep_deg": w["sweep_deg"], "dihedral_deg": w["dihedral_deg"],
                   "a_per_rad": helmbold(AR)}

    # ---- 5 + 7. layout and airplane-mode stability, solved together
    # Given the tail volume (Raymer), the neutral point is fixed; the CG must sit SM ahead of it in airplane mode. The
    # airplane CG is the hover CG plus the forward swing of the two rotor heads. The hover CG must be the hub-triangle
    # centroid (equal thrust), and the tail hub is pinned just behind the wing trailing edge, so the front hub x follows:
    #     x_f = (3 x_cg,hover - x_t) / 2
    nac, t, fz = p["nacelle"], p["tail"], p["fuselage"]
    a01m = a1["masses"]
    m = v["mtow_lb"] * LB
    m_head = a01m["motor_kg"] + 2 * a01m["blade_kg"] + a01m["hub_kg"] + a01m["motor_mount_kg"] + nac["head_fairing_kg"]
    arm = nac["head_arm_m"]
    dx_conv = 2 * m_head * arm / m                                  # hub: above the pivot (hover) -> ahead of it (airplane)
    dz_conv = -2 * m_head * arm / m
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
    x_f = (3 * x_cg_hover - x_t) / 2
    S_h = 0.5
    for _ in range(50):
        c_h = math.sqrt(S_h / t["horizontal_AR"])
        x_ht = x_t - R - t["rotor_gap_m"] - 0.25 * c_h             # H-tail aft of the tail disk, no download
        l_h = x_mac - x_ht
        S_h_new = V_h * S * c / l_h
        if abs(S_h_new - S_h) < 1e-6: break
        S_h = S_h_new
    S_v = t["vertical_volume"] * S * b / l_h
    x_tip_qc = (b / 2) * math.tan(math.radians(-w["sweep_deg"]))

    # ---- 6. hub span position: overlap vs download (head at x_f)
    vi = math.sqrt(T_h / (2 * rho * math.pi * R * R))
    v_w = vi * (1 + arm / math.sqrt(arm * arm + R * R))
    q_w = 0.5 * rho * v_w ** 2
    scan = []
    for ov in np.linspace(0.0, 1.0, 41):
        y_hub = b / 2 + R * (1 - ov)
        A = disk_wing_overlap_area(y_hub, x_f, R, b, c, w["sweep_deg"])
        Dn = nac["download_cd_wing"] * q_w * A
        scan.append({"overlap": float(ov), "y_hub": y_hub, "A_m2": A, "download_n": Dn, "frac": Dn / T_h})
    ok = [s_ for s_ in scan if s_["frac"] <= nac["download_max_frac"]]
    pick = max(ok, key=lambda s_: s_["overlap"])
    y_f = pick["y_hub"]
    v22 = disk_wing_overlap_area(b / 2, x_tip_qc - 0.125 * c, R, b, c, w["sweep_deg"])
    out["download"] = {"vi_ms": vi, "z_m": arm, "v_wing_ms": v_w, "q_wing_pa": q_w, "scan": scan, "chosen": pick,
                       "v22_like": {"A_m2": v22, "frac": nac["download_cd_wing"] * q_w * v22 / T_h,
                                    "note": "hub on the wing-tip spar, as on the V-22"}}
    d_hubs = math.hypot(x_f - x_t, y_f)
    pod_len = (x_f - (x_tip_qc - 0.75 * c)) + 0.10                  # pod from behind the wing TE to the head pivot
    out["layout"] = {"x_front_hub": x_f, "y_front_hub": y_f, "x_tail_hub": x_t, "x_cg_hover": x_cg_hover,
                     "hub_spacing_front_m": 2 * y_f, "front_to_tail_hub_m": d_hubs, "front_to_tail_over_D": d_hubs / D,
                     "head_ahead_of_tip_LE_m": x_f - (x_tip_qc + 0.25 * c), "pod_length_m": pod_len,
                     "overall_width_m": 2 * (y_f + R),
                     "x_tip_qc": x_tip_qc}
    x_nose = x_cg_hover + 0.45 * Lf                                # payload bay centred on the CG
    # tail-disk download: the boom runs under the whole tail disk, and the aft fuselage cone reaches into it.
    # Strip theory as for the wing, with Cd 1.17 for the boom (cylinder) and 0.5 for the rounded cone (Airframe/01).
    sel = os.path.join(os.path.dirname(RESULTS), "designs", "selected.json")
    D_boom = jload(sel)["boom"]["D"] if os.path.exists(sel) else 0.12
    z_t = t["pylon_height_m"] + 0.10
    v_t = vi * (1 + z_t / math.sqrt(z_t ** 2 + R ** 2)); q_t = 0.5 * rho * v_t ** 2
    x_tail_f = x_nose - Lf
    xs_ = np.linspace(x_t - R, x_t + R, 400); dx_ = xs_[1] - xs_[0]
    half = np.sqrt(np.clip(R ** 2 - (xs_ - x_t) ** 2, 0, None))
    s_f = (x_nose - xs_) / Lf                                      # fuselage station 0 (nose) .. 1 (tail)
    w_f = np.where((s_f >= 1 - fz["tail_frac"]) & (s_f <= 1), Wf * (1 - 0.65 * (s_f - (1 - fz["tail_frac"])) / fz["tail_frac"]),
                   np.where((s_f >= 0) & (s_f < 1 - fz["tail_frac"]), Wf, 0.0))
    A_f = float(np.sum(np.minimum(w_f, 2 * half)) * dx_)
    A_b = float(np.sum(np.where(xs_ < x_tail_f, np.minimum(D_boom, 2 * half), 0.0)) * dx_)
    D_tail = 0.5 * q_t * A_f + 1.17 * q_t * A_b
    out["download_tail"] = {"z_m": z_t, "q_pa": q_t, "A_fuselage_m2": A_f, "A_boom_m2": A_b, "D_boom_m": D_boom,
                            "download_n": D_tail, "frac": D_tail / T_h}
    out["download_total_frac"] = (2 * pick["download_n"] + D_tail) / W
    out["stability"] = {"x_cg_air": x_cg_air, "dx_conversion": dx_conv, "dz_conversion": dz_conv, "h_cg_air": h_cg,
                        "h_cg_hover": h(x_cg_hover), "h_ac_wb": h_acwb, "dh_fuselage": dh_fus, "K_f": K_f,
                        "root_qc_frac_of_fuselage": x_nose / Lf, "m_head": m_head,
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
    # pods (fixed): cylinder from behind the wing TE to the head, plus the head in airplane mode
    dn, ln = nac["pod_diameter_m"], pod_len + arm
    parts["nacelles x2"] = 2 * 1.3 * cf_turb(ReL(ln)) * (1 + 0.35 / (ln / dn)) * (math.pi * dn * ln)
    # tail boom
    lb = x_cg_hover - 0.55 * Lf - x_ht + 0.3; db_ = 0.10
    parts["tail boom"] = cf_turb(ReL(max(lb, 0.2))) * (1 + 60 / (lb / db_) ** 3 + (lb / db_) / 400) * math.pi * db_ * lb
    # tail surfaces
    ff_t = 1 + 0.6 / 0.3 * t["tc_tail"] + 100 * t["tc_tail"] ** 4
    c_v = math.sqrt(S_v / 2 / 1.5)
    parts["H-tail"] = cf_turb(ReL(c_h)) * ff_t * 2.04 * S_h * 1.05
    parts["fins x2"] = cf_turb(ReL(c_v)) * ff_t * 2.04 * S_v * 1.05
    # tail rotor stopped, blades parked fore-aft; hub + pylon as a bluff body
    sig = fd["solidity"]
    parts["tail rotor blades (parked)"] = cf_turb(ReL(fd["chord_75_mm"] / 1000)) * (1 + 0.6 / 0.3 * 0.12 + 100 * 0.12 ** 4) * 2 * sig * math.pi * R * R
    parts["tail rotor hub + pylon"] = 1.0 * 0.10 * t["pylon_height_m"]          # Cd 1.0 on 0.1 m x pylon height (assumption)
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

    # ---- 4. cruise thrust and power
    T_av = 2 * thrust(n_max, V)
    from scipy.optimize import brentq
    n_cr = brentq(lambda n: 2 * thrust(n, V) - Dr, V / (J_zero * D) * 1.0001, n_max * 2)
    J_cr = V / (n_cr * D)
    CP = float(np.interp(J_cr, J_, CP_))
    P_shaft = 2 * CP * rho * n_cr ** 3 * D ** 5
    eta_p = Dr * V / P_shaft
    elec = el["eta_motor_esc"] * el["eta_battery_wiring"]
    mc = fd["cruise"]["15"]
    out["cruise"] = {"V": V, "thrust_available_n": T_av, "thrust_required_n": Dr, "thrust_margin": T_av / Dr,
                     "rpm": 60 * n_cr, "J": J_cr, "shaft_power_w": P_shaft, "prop_eta": eta_p, "battery_power_w": P_shaft / elec,
                     "wh_per_km": P_shaft / elec / (V * 3.6),
                     "multirotor_15ms_shaft_w": mc["shaft_total"], "multirotor_wh_per_km": mc["shaft_total"] / elec / (15 * 3.6),
                     "tip_mach": math.hypot(2 * math.pi * n_cr * R, V) / a_snd}

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
    w, L, s, d, cr = o["wing"], o["layout"], o["stability"], o["drag"], o["cruise"]
    print(f"V-22 scaled to 54 in rotors: hubs {o['v22_scaled']['hub_spacing_m']:.2f} m apart, wing {o['v22_scaled']['wing_area_m2']:.2f} m2"
          f" -> needs {o['v22_scaled']['speed_for_CL1_ms']:.0f} m/s at CL 1.0;  prop zero thrust at {o['prop_airplane']['v_zero_thrust_at_rpm_max']:.1f} m/s")
    print("Airfoils (Re %.2e):" % o["wing_re"])
    for r in o["airfoil_table"]:
        print(f"  NACA {r['name']:6s} t/c {r['tc']:.2f} clmax {r['clmax']:.3f} CL_cr {r['CL_cruise']:.3f} S {r['S']:.2f} m2 cd {r['cd_cruise']:.5f} cm0 {r['cm0']:+.3f} DA {r['DA_wing']:.4f}")
    print(f"Wing NACA {w['airfoil']}: S {w['S']:.2f} m2, b {w['b']:.2f} m, c {w['c']:.3f} m, CL {w['CL_cruise']:.3f}, Vs {w['v_stall_ms']:.1f} m/s, W/S {w['wing_loading_n_m2']:.0f} N/m2")
    ch = o["download"]["chosen"]
    print(f"Download: overlap {ch['overlap']:.2f} R -> {ch['download_n']:.0f} N ({100*ch['frac']:.1f} %); V-22 hub on the tip spar -> {100*o['download']['v22_like']['frac']:.1f} %")
    dt = o["download_tail"]
    print(f"Tail-disk download: fuselage {dt['A_fuselage_m2']:.3f} m2 + boom {dt['A_boom_m2']:.3f} m2 -> {dt['download_n']:.0f} N ({100*dt['frac']:.1f} % of the tail rotor); vehicle {100*o['download_total_frac']:.1f} %")
    print(f"Layout: front hubs x {L['x_front_hub']:+.3f} y +-{L['y_front_hub']:.3f}; tail hub x {L['x_tail_hub']:+.3f}; CG hover x {L['x_cg_hover']:+.3f}; front-tail {L['front_to_tail_over_D']:.2f} D; head {L['head_ahead_of_tip_LE_m']:+.2f} m ahead of tip LE, pod {L['pod_length_m']:.2f} m, width {L['overall_width_m']:.2f} m")
    print(f"Stability: h_cg {s['h_cg_air']:.3f} h_acwb {s['h_ac_wb']:.3f} V_h {s['V_h']:.3f} S_h {s['S_h']:.3f} m2 (b_h {s['b_h']:.2f}) l_h {s['l_h']:.2f} S_v {s['S_v_total']:.3f} SM {s['static_margin']:.3f}")
    print("Drag parts (m2): " + ", ".join(f"{k} {v:.4f}" for k, v in d["parts_m2"].items()))
    print(f"  wing profile {d['wing_profile_m2']:.4f} induced {d['induced_m2']:.4f}  CDA {d['CDA_total_m2']:.3f} m2 -> D {d['drag_n']:.0f} N, L/D {d['L_over_D']:.1f} (max {d['LD_max']:.1f} at CL {d['CL_LDmax']:.2f})")
    print(f"Cruise: thrust avail {cr['thrust_available_n']:.0f} N vs req {cr['thrust_required_n']:.0f} N (x{cr['thrust_margin']:.2f}); {cr['rpm']:.0f} rpm J {cr['J']:.3f} "
          f"P_shaft {cr['shaft_power_w']:.0f} W eta {cr['prop_eta']:.2f};  {cr['wh_per_km']:.1f} Wh/km vs multirotor {cr['multirotor_wh_per_km']:.1f} Wh/km")
    g = o["gust"]
    print(f"Gust: mu {g['mu_g']:.1f} Kg {g['K_g']:.3f} n {g['n_gust']:.2f}; tilt actuator hold {o['tilt_actuator']['hold_torque_nm']:.1f} N m")


if __name__ == "__main__":
    derive()

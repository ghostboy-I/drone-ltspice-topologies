"""Phase 5.0 configuration study: should the 54x18 tricopter change its rotor configuration?

Four ideas against the Phase 2 baseline (open, fixed-pitch, 2 blades, one rotor per arm), all on the same blade, the same
polars and the same mission model as Phase 2, so the columns compare like with like:

  1. Re-pitched fixed blade   the whole blade rotated by a constant d_theta (one new setting for the whole mission)
  2. Variable (collective) pitch   d_theta re-chosen in every mission segment, plus the T/W it unlocks at the motor limits
  3. Ducted rotor            a straight duct around each rotor (exit area ratio sigma_e), momentum theory + blade elements
  4. Coaxial pair per arm    two counter-rotating rotors on each arm, offset vertically by h (Y6 layout), BEMT with a
                             vortex-cylinder model of the upper wake

MOMENTUM THEORY, DUCTED ROTOR (Pereira 2008; Leishman 2006 sec. 15.4). Disk area A, far-wake area sigma_e A, disk
velocity v_d, far wake v_d / sigma_e (continuity). Total thrust is the momentum flux of the far wake:
    T = rho A v_d (v_d / sigma_e)      ->   v_d = sqrt(sigma_e T / (rho A))
The rotor only supplies the pressure jump, which sets the far-wake energy:  T_rotor A^-1 = 0.5 rho (v_d / sigma_e)^2, so
    T_rotor / T = 1 / (2 sigma_e)       (the duct lip carries the rest, by suction on its rounded inlet)
    P_ideal = T v_d / 1 ... = T^1.5 / sqrt(4 sigma_e rho A)   against  T^1.5 / sqrt(2 rho A) open: ratio 1 / sqrt(2 sigma_e)
The blade elements are run with this prescribed axial velocity (no momentum equation of their own, which would count the
inflow twice), swirl from angular momentum dQ = 4 pi rho v_d r^2 v_t dr, and no tip loss (small tip gap). A sensitivity
keeps the open-rotor Prandtl factor on lift (a large tip gap).

COAXIAL PAIR. A semi-infinite vortex cylinder of radius R (uniform disk loading, induced velocity v_i at the disk)
induces on its axis, a distance z downstream / upstream of the disk:
    w(z) = v_i (1 + z / sqrt(R^2 + z^2))          w(-z) = v_i (1 - z / sqrt(R^2 + z^2))
so the far wake is 2 v_i and, by continuity, the slipstream radius at z is r_w = R sqrt(v_i / w(z)) (R / sqrt 2 far down).
The lower rotor sees w(h) as an extra axial velocity inside r_w(h) and nothing outside it; the upper rotor sees the lower
rotor's upstream induction w(-h). Both are solved with the Phase 2 BEMT (the lower one with a radially varying inflow),
iterated until the mean induced velocities stop changing, and trimmed to the arm's thrust with equal torque on the two
rotors (yaw balance, no tilt servo needed). Interference factor (Leishman 2006, sec. 6.9):
    kappa_int = (P_induced upper + P_induced lower) / (2 P_induced isolated rotor at T / 2)
with P_induced = sum (V + v_i) dT, so the lower rotor's work against the upper wake counts as induced loss.
Hand check, uniform loading, h -> infinity, equal thrust: upper P = T v_h; lower inner half (sees 2 v_h): 2 rho (2 v_h + v) v
= 2 rho v_h^2 -> v = (sqrt 2 - 1) v_h, through-velocity (1 + sqrt 2) v_h; outer half: v = v_h. So P_lower = T v_h
(1 + sqrt 2 + 1) / 2 and kappa_int = (1 + (2 + sqrt 2) / 2) / 2 = 1.354. Leishman's momentum value is 1.281 for a lower
rotor that works on the whole system mass flow; measured coaxial rotors fall near 1.16-1.3 depending on spacing.

FORWARD FLIGHT. Ducts and coaxial wakes in edgewise flight are not modelled by the Phase 2 BEMT. Each is bracketed: the
duct between "no credit for edgewise inflow" (hover-like induced power plus momentum drag) and "same induced-power drop as
the open rotor"; the coaxial pair between "isolated rotors" and "hover interference factor on the induced part".
Every penalty mass is an assumption in params.yaml (config_study), each with a sensitivity.
"""
import json, math, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from scipy.optimize import brentq
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import airfoils, bemt, atmosphere as atm, momentum as mt, mission as ms
from phase2 import Rotor
from common import RESULTS, load_params, load_catalog, save_json


def load_final_blade(p):
    d = np.loadtxt(os.path.join(RESULTS, "blade_final.csv"), delimiter=",", comments="#", skiprows=2)
    R = p["rotor"]["diameter_in"] * p["constants"]["inch_to_m"] / 2
    return bemt.Blade(R, p["rotor"]["hub_radius_m"], p["rotor"]["n_blades"], d[:, 0], d[:, 2], np.radians(d[:, 3]), d[:, 4])


class Veh:
    """Mission-model interface (see mission.mission_energy) built from per-vehicle shaft-power functions."""
    def __init__(self, p, hover_w, climb_w, cruise_w):
        self.p, self.h, self.c, self.cr = p, hover_w, climb_w, cruise_w
    def hover_shaft(self): return self.h
    def climb_shaft(self, vc): return self.c
    def cruise(self, v): return {"shaft_total": self.cr}
    def electrical(self, psh):
        el = self.p["electrical"]
        return psh / (el["eta_motor_esc"] * el["eta_battery_wiring"]) + self.p["mission"]["avionics_w"]


def mission_pack(p, ph1, hover_w, climb_w, cruise_w):
    m = ms.mission_energy(Veh(p, hover_w, climb_w, cruise_w), p["mission"], ph1["vehicle"]["range_m"], p["mission"]["cruise_speed_ms"])
    return m["pack_wh"], m


def induced(sol, v=0.0):
    return float(np.sum((v + sol["vi"]) * sol["dT_dr"] * sol["dr"]))


def cruise_margin(db, rot_hover, e):
    """Smallest stall margin over r > 0.3 R in cruise: section stall angle (at the hover Re and Mach of that radius) minus
    the largest angle of attack it reaches around the azimuth."""
    a_st = db.prop("alpha_stall", rot_hover["tc"], rot_hover["re"], rot_hover["mach"])
    a_st = np.interp(e["r"], rot_hover["r"], a_st)
    m = (e["r"] > 0.3 * rot_hover["r"].max()) & (e["r"] < 0.95 * rot_hover["r"].max())
    return float(np.min(a_st[m] - np.degrees(e["alpha"].max(axis=0))[m]))


# ---- 1 + 2: pitch ---------------------------------------------------------------------------------------------
def pitch_study(p, ph1, blade, db, A, cs, t0):
    dkey = p["design_atmosphere"]; mis = p["mission"]; cat = load_catalog()["motors"]["tmotor_u15xl_kv38"]; el = p["electrical"]
    rows = []
    for dth in cs["pitch_offsets_deg"]:
        r_ = Rotor(f"d_theta {dth:+.0f}", blade.with_changes(twist_add=math.radians(dth)), db, p, A, ph1)
        row = {"d_theta_deg": dth}
        try:
            h = r_.hover(dkey); row["hover_w"] = 3 * h["P"]; row["hover_rpm"] = h["rpm"]; row["hover_fom"] = h["FoM"]
            row["stall_margin_hover_deg"] = float(__import__("design_opt").stall_margin_deg(db, h, blade.R))
            row["climb_w"] = 3 * r_.climb(dkey, mis["climb_rate_ms"])["P"]
            e = r_.cruise(dkey, mis["cruise_speed_ms"]); row["cruise_w"] = e["shaft_total"]; row["cruise_rpm"] = e["rpm"]
            row["cruise_stall_margin_deg"] = cruise_margin(db, h, e); row["cruise_alpha_max_deg"] = e["alpha_max_deg"]
            row["pack_wh"] = mission_pack(p, ph1, row["hover_w"], row["climb_w"], row["cruise_w"])[0]
            row["motor"] = r_.motor_tw(dkey, cat["kv"], cat["peak_current_a"], el["cells_baseline"] * el["v_cell_sag"])
            row["tw"] = row["motor"]["tw"]
            row["tip_mach_hover"] = h["tip_mach"]
        except ValueError as ex:
            row["error"] = str(ex)
        rows.append(row)
        print(f"  pitch {dth:+.0f} deg: hover {row.get('hover_w', float('nan')):.0f} W, cruise {row.get('cruise_w', float('nan')):.0f} W,"
              f" pack {row.get('pack_wh', float('nan')):.0f} Wh, T/W {row.get('tw', float('nan')):.2f},"
              f" margins {row.get('stall_margin_hover_deg', float('nan')):.1f} / {row.get('cruise_stall_margin_deg', float('nan')):.1f} deg [{time.time()-t0:.0f}s]", flush=True)
    ok = lambda r, seg: "error" not in r and r["stall_margin_hover_deg"] >= p["design"]["min_stall_margin_deg"] and (seg != "cruise" or r["cruise_stall_margin_deg"] >= cs["cruise_min_stall_margin_deg"])
    base = next(r for r in rows if r["d_theta_deg"] == 0)
    fixed = [r for r in rows if ok(r, "cruise") and r["tw"] >= p["vehicle"]["tw_required"]]
    best_fixed = min(fixed, key=lambda r: r["pack_wh"])

    def vertex(key, seg):
        """Grid minimum refined by a parabola through it and its neighbours (only over admissible settings)."""
        cand = [r for r in rows if ok(r, seg)]
        i = min(range(len(cand)), key=lambda k: cand[k][key])
        if 0 < i < len(cand) - 1:
            x = [cand[i + k]["d_theta_deg"] for k in (-1, 0, 1)]; y = [cand[i + k][key] for k in (-1, 0, 1)]
            a, b, c = np.polyfit(x, y, 2)
            if a > 0: return float(-b / (2 * a)), float(c - b * b / (4 * a))
        return cand[i]["d_theta_deg"], cand[i][key]

    var = {seg: vertex(f"{seg}_w", seg) for seg in ("hover", "climb", "cruise")}
    pack_var, m_var = mission_pack(p, ph1, var["hover"][1], var["climb"][1], var["cruise"][1])
    tw_best = max((r for r in rows if "error" not in r), key=lambda r: r["tw"])
    return {"rows": rows, "baseline": base, "best_fixed": best_fixed,
            "variable": {"settings_deg": {k: v[0] for k, v in var.items()}, "shaft_w": {k: v[1] for k, v in var.items()},
                         "pack_wh": pack_var, "tw_max": tw_best["tw"], "tw_max_at_deg": tw_best["d_theta_deg"]}}


# ---- 3: duct --------------------------------------------------------------------------------------------------
def ducted_blade(blade, db, air, rpm, v_d, tip_loss=False, n=40):
    """Blade elements with a prescribed axial velocity v_d at the disk; swirl from angular momentum."""
    rho, mu, a = air["rho"], air["mu"], air["a"]
    om = rpm * 2 * math.pi / 60
    r, dr, c, th, tc = blade.stations(n)
    vt = np.zeros_like(r)
    for _ in range(40):
        UT = om * r - vt; phi = np.arctan2(v_d, UT); W = np.hypot(UT, v_d)
        cl, cd = db.lookup(tc, rho * W * c / mu, W / a, th - phi)
        F = bemt.prandtl(blade.N, r, blade.R, blade.r_hub, np.sin(phi), True, True) if tip_loss else 1.0
        q = 0.5 * rho * W ** 2 * blade.N * c
        dT = q * (cl * F * np.cos(phi) - cd * np.sin(phi)) * dr
        dQ = q * (cl * F * np.sin(phi) + cd * np.cos(phi)) * r * dr
        vt_new = (dQ / dr) / (4 * math.pi * r * r * rho * v_d)
        if np.max(np.abs(vt_new - vt)) < 1e-6: break
        vt = 0.5 * vt + 0.5 * vt_new
    T, Q = float(dT.sum()), float(dQ.sum())
    return {"rpm": rpm, "T": T, "Q": Q, "P": Q * om, "alpha": th - phi, "r": r, "tip_mach": om * blade.R / a,
            "profile": float(np.sum(0.5 * rho * W ** 3 * blade.N * c * cd * dr))}


def ducted_hover(blade, db, air, thrust, sigma_e, tip_loss=False):
    A = math.pi * blade.R ** 2
    v_d = math.sqrt(sigma_e * thrust / (air["rho"] * A))
    t_r = thrust / (2 * sigma_e)
    rpm = brentq(lambda n: ducted_blade(blade, db, air, n, v_d, tip_loss)["T"] - t_r, 300, 6000, xtol=0.05)
    s = ducted_blade(blade, db, air, rpm, v_d, tip_loss)
    s.update(v_d=v_d, T_rotor=t_r, T_duct=thrust - t_r, T_total=thrust,
             P_ideal=thrust ** 1.5 / math.sqrt(4 * sigma_e * air["rho"] * A), FoM_open_def=thrust ** 1.5 / math.sqrt(2 * air["rho"] * A) / s["P"])
    return s


def duct_study(p, ph1, blade, db, A, cs, base_rotor, t0):
    dkey = p["design_atmosphere"]; air = A[dkey]; mis = p["mission"]; dc = cs["duct"]
    W, n = ph1["vehicle"]["weight_n"], p["vehicle"]["n_rotors"]; t_h = W / n
    R = blade.R; D = 2 * R; Ad = math.pi * R * R; V = mis["cruise_speed_ms"]
    # duct mass: inner + outer skin of a ring of length L, plus lip, struts and attachment
    L = dc["length_over_D"] * D
    m_duct = dc["areal_density_kg_m2"] * 2 * math.pi * D * L * (1 + dc["struts_lip_fraction"])
    out = {"duct_length_m": L, "duct_mass_kg_each": m_duct, "cases": []}
    oh = base_rotor.hover(dkey); ob = base_rotor.cruise(dkey, V)
    vh = mt.hover_vi(t_h, air["rho"], Ad)
    # open rotor, hover -> cruise: induced power per newton falls by this ratio (edgewise flow brings fresh air through the disk)
    ind_ratio = (ob["T"] * ob["lam0"] * ob["rpm"] * 2 * math.pi / 60 * R / ob["T"]) / (induced(oh) / oh["T"])
    out["open_rotor_induced_ratio_cruise_over_hover"] = ind_ratio
    for sig in dc["sigma_e"]:
        for tl in (False, True):
            h = ducted_hover(blade, db, air, t_h, sig, tl)
            climb_w = n * (h["P"] + t_h * mis["climb_rate_ms"])         # climb at 2.5 m/s: hover + T vc (no climb credit, conservative)
            # cruise, bracketed (see module docstring). Drag per duct: momentum drag rho A v_d V + ring side drag.
            ring = 0.5 * air["rho"] * V * V * dc["ring_cd"] * D * L
            mom = air["rho"] * Ad * h["v_d"] * V
            drag_f = 0.5 * air["rho"] * V * V * p["vehicle"]["cda_m2"]
            res = {}
            # pessimistic: hover-like disk velocity in cruise; optimistic: disk velocity and induced power drop like the open rotor's
            for tag, f in (("pessimistic", 1.0), ("optimistic", ind_ratio)):
                drag = drag_f + n * (ring + f * mom)
                al, t_tot = math.atan2(drag, W), math.hypot(W, drag)
                hc = ducted_hover(blade, db, air, t_tot / n, sig, tl)
                p_ind_d = (hc["P"] - hc["profile"]) * f
                mu_ = V / (hc["rpm"] * 2 * math.pi / 60 * R)
                res[tag] = n * (p_ind_d + hc["profile"] * (1 + 4.65 * mu_ ** 2)) + drag * V
                res[tag + "_drag_n"] = drag
            pack_p = mission_pack(p, ph1, n * h["P"], climb_w, res["pessimistic"])[0]
            pack_o = mission_pack(p, ph1, n * h["P"], climb_w, res["optimistic"])[0]
            case = {"sigma_e": sig, "tip_loss": tl, "hover_w": n * h["P"], "hover_rpm": h["rpm"], "hover_tip_mach": h["tip_mach"],
                    "rotor_thrust_share": h["T_rotor"] / t_h, "v_d": h["v_d"], "v_open_momentum": vh,
                    "P_ideal_w": n * h["P_ideal"], "fom_open_definition": h["FoM_open_def"], "profile_w": n * h["profile"],
                    "climb_w": climb_w, "cruise_w": res, "ring_drag_n_each": ring, "momentum_drag_n_each": mom,
                    "pack_wh_pessimistic": pack_p, "pack_wh_optimistic": pack_o}
            out["cases"].append(case)
            print(f"  duct sigma_e {sig} tip loss {tl}: hover {case['hover_w']:.0f} W (rotor share {case['rotor_thrust_share']:.2f}),"
                  f" cruise {res['optimistic']:.0f}-{res['pessimistic']:.0f} W, pack {pack_o:.0f}-{pack_p:.0f} Wh [{time.time()-t0:.0f}s]", flush=True)
    return out


# ---- 4: coaxial -----------------------------------------------------------------------------------------------
def coax_pair(blade, db, air, thrust, h, split=None, n=40, passes=6):
    """Upper + lower rotor (same blade, counter-rotating) carrying `thrust` together, vertical offset h.
    split=None trims to equal torque; a number fixes the upper rotor's thrust share."""
    R, A = blade.R, math.pi * blade.R ** 2
    r = blade.stations(n)[0]
    viu = vil = mt.hover_vi(thrust / 2, air["rho"], A)
    k = h / math.sqrt(R * R + h * h)
    mean_vi = lambda s: float(np.sum(s["vi"] * 2 * math.pi * s["r"] * s["dr"]) / A)
    for _ in range(passes):
        v_up = vil * (1 - k)                                      # lower rotor's induction at the upper disk
        w = viu * (1 + k); rw = R * math.sqrt(viu / w)            # upper wake at the lower disk
        v_lo = np.where(r < rw, w, 0.0)
        up = lambda rpm: bemt.axial(blade, db, air, rpm, v_up, n=n)
        lo = lambda rpm: bemt.axial(blade, db, air, rpm, v_lo, n=n)

        def solve(s):
            return bemt.trim_rpm(up, s * thrust), bemt.trim_rpm(lo, (1 - s) * thrust)
        if split is None:
            s = brentq(lambda s: (lambda u, l: u["Q"] - l["Q"])(*solve(s)), 0.30, 0.80, xtol=1e-4)
        else:
            s = split
        u, l = solve(s)
        viu_new, vil_new = mean_vi(u), mean_vi(l)
        done = abs(viu_new - viu) < 1e-3 and abs(vil_new - vil) < 1e-3
        viu, vil = viu_new, vil_new
        if done: break
    p_ind = induced(u, v_up) + float(np.sum((v_lo + l["vi"]) * l["dT_dr"] * l["dr"]))
    return {"h": h, "split_upper": s, "upper": u, "lower": l, "P": u["P"] + l["P"], "P_induced": p_ind,
            "v_upper_extra": v_up, "w_at_lower": w, "r_wake_at_lower": rw, "viu": viu, "vil": vil,
            "rpm_upper": u["rpm"], "rpm_lower": l["rpm"], "Q_upper": u["Q"], "Q_lower": l["Q"]}


def coax_study(p, ph1, blade, db, A, cs, base_rotor, t0):
    dkey = p["design_atmosphere"]; air = A[dkey]; mis = p["mission"]; cx = cs["coax"]
    W, n = ph1["vehicle"]["weight_n"], p["vehicle"]["n_rotors"]; t_h = W / n
    R = blade.R; V = mis["cruise_speed_ms"]
    iso = bemt.hover_at_thrust(blade, db, air, t_h / 2)
    p_ind_iso = induced(iso)
    single = base_rotor.hover(dkey)
    rows = []
    for hd in cx["spacing_over_D"]:
        c = coax_pair(blade, db, air, t_h, hd * 2 * R)
        ce = coax_pair(blade, db, air, t_h, hd * 2 * R, split=0.5)
        rows.append({"h_over_D": hd, "hover_w_arm": c["P"], "split_upper": c["split_upper"], "rpm_upper": c["rpm_upper"], "rpm_lower": c["rpm_lower"],
                     "kappa_int": c["P_induced"] / (2 * p_ind_iso), "kappa_int_equal_thrust": ce["P_induced"] / (2 * p_ind_iso),
                     "vs_isolated_pair": c["P"] / (2 * iso["P"]), "vs_single_rotor": c["P"] / single["P"],
                     "r_wake_over_R": c["r_wake_at_lower"] / R, "w_over_viu": c["w_at_lower"] / c["viu"],
                     "torque_upper": c["Q_upper"], "torque_lower": c["Q_lower"], "tip_mach_upper": c["upper"]["tip_mach"]})
        print(f"  coax h/D {hd}: arm hover {c['P']:.0f} W vs single {single['P']:.0f} W, kappa_int {rows[-1]['kappa_int']:.3f}"
              f" (equal thrust {rows[-1]['kappa_int_equal_thrust']:.3f}), upper share {c['split_upper']:.3f} [{time.time()-t0:.0f}s]", flush=True)
    # hand check: uniform loading, far spacing, equal thrust -> 1.354 (module docstring)
    far = coax_pair(blade, db, air, t_h, 20 * R, split=0.5)
    hand = {"kappa_int_uniform_far_hand": (1 + (2 + math.sqrt(2)) / 2) / 2, "kappa_int_bemt_far": far["P_induced"] / (2 * p_ind_iso),
            "r_wake_far_over_R": far["r_wake_at_lower"] / R, "r_wake_far_hand": 1 / math.sqrt(2),
            "leishman_momentum_equal_thrust": 1.2808}
    sel = next(r for r in rows if r["h_over_D"] == cx["design_spacing_over_D"])
    # cruise. Edgewise induced power goes as T^2 / (2 rho A V), so it depends on how much fresh air each disk gets:
    #   isolated (best):         both rotors of a pair in clean air, each at T_arm / 2       -> induced halves
    #   one disk (worst):        the pair works on one disk's mass flow, like the open rotor at T_arm
    #   overlap (estimate):      blend the two by the fraction f of the lower disk inside the upper wake, which has skewed
    #                            back by d = h tan(chi), tan(chi) = mu / lambda (wake skew from the shaft axis).
    #                            f = circle-circle overlap at centre distance d: [2 R^2 acos(d / 2R) - (d / 2) sqrt(4 R^2 - d^2)] / (pi R^2)
    e_open = base_rotor.cruise(dkey, V)
    al, t_tot = e_open["alpha_shaft"], n * e_open["T"]
    e = bemt.edgewise_at_thrust(blade, db, air, t_tot / (2 * n), V, al, kappa=p["rotor"]["kappa"])
    om_e, om_o = e["rpm"] * 2 * math.pi / 60, e_open["rpm"] * 2 * math.pi / 60
    p_ind_c = e["T"] * e["lam0"] * om_e * R                             # one coaxial rotor, isolated, at T_arm / 2
    p_ind_one_disk = e_open["T"] * e_open["lam0"] * om_o * R            # open rotor at T_arm: one disk's worth of air
    lam = e["lam0"] + V * math.sin(al) / (om_e * R)
    chi = math.atan2(e["mu"], lam); hgt = cx["design_spacing_over_D"] * 2 * R; dsk = min(hgt * math.tan(chi), 2 * R)
    f_ov = (2 * R * R * math.acos(dsk / (2 * R)) - dsk / 2 * math.sqrt(4 * R * R - dsk * dsk)) / (math.pi * R * R)
    cruise_iso = 2 * n * e["P"]
    cruise_one = cruise_iso + n * (p_ind_one_disk - 2 * p_ind_c)
    cruise_ov = cruise_iso + n * f_ov * (p_ind_one_disk - 2 * p_ind_c)
    hov_w = n * sel["hover_w_arm"]
    base_h, base_c = base_rotor.hover(dkey)["P"], base_rotor.climb(dkey, mis["climb_rate_ms"])["P"]
    climb_w = n * base_c * sel["hover_w_arm"] / base_h                 # climb scaled from the open rotor by the hover ratio
    pk = {k: mission_pack(p, ph1, hov_w, climb_w, w)[0] for k, w in (("optimistic", cruise_iso), ("overlap", cruise_ov), ("pessimistic", cruise_one))}
    # motor-out: with one rotor of a pair failed, the other must carry the arm's hover thrust alone
    tw_single = base_rotor.motor_tw(dkey, *(lambda c: (c["kv"], c["peak_current_a"]))(load_catalog()["motors"]["tmotor_u15xl_kv38"]),
                                    p["electrical"]["cells_baseline"] * p["electrical"]["v_cell_sag"])["tw"]
    motor_out = {"six_u15xl_max_thrust_over_arm_hover": tw_single,
                 "half_size_max_thrust_over_arm_hover": tw_single * cs["masses"]["coax_motor_mass_scale"] / 1.15,
                 "note": "half-size motor assumed to reach the same T/W on its half of the arm thrust as the U15XL does on the full"}
    return {"rows": rows, "hand_check": hand, "isolated_half_thrust": {"P": iso["P"], "P_induced": p_ind_iso, "rpm": iso["rpm"]},
            "single_rotor_hover_w": single["P"], "design_spacing_over_D": cx["design_spacing_over_D"], "selected": sel,
            "hover_w": hov_w, "climb_w": climb_w,
            "cruise": {"isolated_w": cruise_iso, "overlap_w": cruise_ov, "one_disk_w": cruise_one, "rpm": e["rpm"], "mu": e["mu"],
                       "wake_skew_deg": math.degrees(chi), "wake_shift_m": dsk, "overlap_fraction": f_ov,
                       "p_induced_isolated_rotor_w": p_ind_c, "p_induced_one_disk_w": p_ind_one_disk},
            "pack_wh": pk, "motor_out": motor_out}


# ---- vehicle bookkeeping -----------------------------------------------------------------------------------------
def payload_delta(pack_wh, base_wh, hardware_kg, whkg):
    return -(hardware_kg + (pack_wh - base_wh) / whkg)


def run():
    t0 = time.time()
    p, ph1 = load_params(), json.load(open(os.path.join(RESULTS, "phase1.json")))
    cs = p["config_study"]
    db, _ = airfoils.build_db(p, n_proc=1)
    A = {k: atm.state(v["temp_c"], v["alt_m"]) for k, v in p["atmospheres"].items()}
    dkey = p["design_atmosphere"]
    blade = load_final_blade(p)
    base = Rotor("baseline", blade, db, p, A, ph1)
    mis = p["mission"]
    bh, bc, be = base.hover(dkey), base.climb(dkey, mis["climb_rate_ms"]), base.cruise(dkey, mis["cruise_speed_ms"])
    base_pack, base_m = mission_pack(p, ph1, 3 * bh["P"], 3 * bc["P"], be["shaft_total"])
    print(f"  baseline: hover {3*bh['P']:.0f} W, cruise {be['shaft_total']:.0f} W, pack {base_pack:.0f} Wh (Phase 2: 7475) [{time.time()-t0:.0f}s]", flush=True)
    out = {"baseline": {"hover_w": 3 * bh["P"], "climb_w": 3 * bc["P"], "cruise_w": be["shaft_total"], "pack_wh": base_pack, "hover_fom": bh["FoM"],
                        "hover_rpm": bh["rpm"], "segments": base_m["segments"], "hover_energy_share": base_m["hover_energy_share"]}}
    out["pitch"] = pitch_study(p, ph1, blade, db, A, cs, t0)
    out["duct"] = duct_study(p, ph1, blade, db, A, cs, base, t0)
    out["coax"] = coax_study(p, ph1, blade, db, A, cs, base, t0)

    # ---- one table: energy, mass, payload ----------------------------------------------------------------------
    cat = load_catalog(); mot, esc = cat["motors"]["tmotor_u15xl_kv38"]["mass_kg"], cat["escs"]["tmotor_thunder_300a_24s"]["mass_kg"]
    prop_kg = p["rotor"]["n_blades"] * ph1["mass_budget"]["blade_kg"] + p["mass"]["hub_hardware_kg_per_rotor"]
    n = p["vehicle"]["n_rotors"]; m = cs["masses"]
    duct_case = next(c for c in out["duct"]["cases"] if c["sigma_e"] == cs["duct"]["design_sigma_e"] and not c["tip_loss"])
    vp = out["pitch"]["variable"]; bf = out["pitch"]["best_fixed"]
    arm_single = mot + esc + prop_kg
    arm_coax_scaled = 2 * (mot * m["coax_motor_mass_scale"] + esc * m["coax_esc_mass_scale"] + prop_kg)
    cx = out["coax"]["pack_wh"]
    configs = [
        ("Baseline: open, fixed pitch", base_pack, base_pack, 0.0, "Phase 2 design"),
        (f"Re-pitched fixed blade ({bf['d_theta_deg']:+.0f} deg)", bf["pack_wh"], bf["pack_wh"], 0.0, "one new blade setting"),
        ("Variable (collective) pitch", vp["pack_wh"], vp["pack_wh"], n * m["pitch_mechanism_kg_per_rotor"], "pitch hub + servo per rotor"),
        (f"Ducted (sigma_e {duct_case['sigma_e']})", duct_case["pack_wh_optimistic"], duct_case["pack_wh_pessimistic"],
         n * out["duct"]["duct_mass_kg_each"], "duct shell, lip and struts"),
        (f"Coaxial pair per arm (h/D {out['coax']['design_spacing_over_D']}), half-size motors", out["coax"]["pack_wh"]["optimistic"],
         out["coax"]["pack_wh"]["pessimistic"], n * (arm_coax_scaled - arm_single) - m["tilt_servo_kg"], "3 more motors, ESCs, props; no yaw tilt servo"),
        (f"Coaxial pair per arm (h/D {out['coax']['design_spacing_over_D']}), six U15XL", out["coax"]["pack_wh"]["optimistic"],
         out["coax"]["pack_wh"]["pessimistic"], n * arm_single - m["tilt_servo_kg"], "motor-out tolerant at hover"),
    ]
    whkg = [p["mass"]["pack_wh_per_kg_cited"], p["mass"]["pack_wh_per_kg_conservative"]]
    out["summary"] = [{"config": name, "pack_wh_best": lo, "pack_wh_worst": hi, "pack_wh_estimate": cx["overlap"] if name.startswith("Coaxial") else (lo + hi) / 2 if name.startswith("Ducted") else lo, "pack_change_pct_best": 100 * (lo / base_pack - 1),
                       "pack_change_pct_worst": 100 * (hi / base_pack - 1), "hardware_kg": hw, "note": note,
                       "payload_change_kg": {f"{w:.0f}": [payload_delta(lo, base_pack, hw, w), payload_delta(hi, base_pack, hw, w)] for w in whkg}}
                      for name, lo, hi, hw, note in configs]
    out["mass_refs"] = {"arm_single_kg": arm_single, "arm_coax_scaled_kg": arm_coax_scaled,
                        "hobbywing_h13_pair_kg": 8.01, "note": "Hobbywing H13 coaxial pair (data/catalog.yaml): 8.01 kg per arm incl. props, rated 45 kgf, max 113 kgf"}
    out["runtime_s"] = time.time() - t0
    save_json("config_study.json", out)
    plot(out)
    return out


def plot(o):
    fig, axs = plt.subplots(1, 3, figsize=(12, 3.4))
    rows = [r for r in o["pitch"]["rows"] if "error" not in r]
    x = [r["d_theta_deg"] for r in rows]
    axs[0].plot(x, [r["hover_w"] / 1000 for r in rows], "o-", color="#0b0b0b", label="hover (3 rotors)")
    axs[0].plot(x, [r["cruise_w"] / 1000 for r in rows], "s-", color="#2a78d6", label="cruise 15 m/s")
    ax2 = axs[0].twinx(); ax2.plot(x, [r["tw"] for r in rows], "^--", color="#c0392b", label="T/W (U15XL, 84 V)"); ax2.set_ylabel("T/W", color="#c0392b")
    axs[0].set_xlabel("blade pitch change [deg]"); axs[0].set_ylabel("shaft power [kW]"); axs[0].legend(fontsize=7, loc="upper left"); axs[0].grid(alpha=.3)
    axs[0].set_title("Pitch", fontsize=9)
    cr = o["coax"]["rows"]
    axs[1].plot([r["h_over_D"] for r in cr], [r["kappa_int"] for r in cr], "o-", color="#0b0b0b", label="equal torque")
    axs[1].plot([r["h_over_D"] for r in cr], [r["kappa_int_equal_thrust"] for r in cr], "s--", color="#2a78d6", label="equal thrust")
    axs[1].axhline(o["coax"]["hand_check"]["leishman_momentum_equal_thrust"], color="#999", ls=":", label="Leishman momentum 1.281")
    axs[1].axhline(o["coax"]["hand_check"]["kappa_int_uniform_far_hand"], color="#e08e0b", ls=":", label="hand, uniform, far 1.354")
    axs[1].set_xlabel("vertical offset h / D"); axs[1].set_ylabel("interference factor kappa_int"); axs[1].legend(fontsize=6); axs[1].grid(alpha=.3)
    axs[1].set_title("Coaxial pair", fontsize=9)
    s = o["summary"]; names = [q["config"].split(" (")[0].replace("Coaxial pair per arm", "Coaxial") + ("\n" + q["config"].split("), ")[1] if "), " in q["config"] else "") for q in s]
    y = np.arange(len(s))
    lo = [q["payload_change_kg"]["303"][0] for q in s]; hi = [q["payload_change_kg"]["303"][1] for q in s]
    axs[2].barh(y, lo, color="#2a78d6", alpha=0.85, label="best case")
    axs[2].barh(y, hi, color="none", edgecolor="#0b0b0b", label="worst case")
    axs[2].set_yticks(y); axs[2].set_yticklabels(names, fontsize=6); axs[2].invert_yaxis(); axs[2].axvline(0, color="#0b0b0b", lw=0.8)
    axs[2].set_xlabel("payload change vs baseline [kg] (303 Wh/kg)"); axs[2].legend(fontsize=6); axs[2].grid(alpha=.3, axis="x")
    axs[2].set_title("Vehicle", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(RESULTS, "config_study.png"), dpi=150); plt.close(fig)


if __name__ == "__main__":
    o = run(); print(f"wrote results/config_study.json in {o['runtime_s']:.0f} s")

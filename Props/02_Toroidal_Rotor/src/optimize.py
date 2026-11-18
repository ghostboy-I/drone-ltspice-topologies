"""Toroidal rotor optimisation, step 1: a blade-element model anchored to the toroid CFD, and a sweep of the cheap levers.

    python3 src/optimize.py calibrate     # fit the model to the CFD spanwise thrust and total torque
    python3 src/optimize.py sweep         # collective pitch x leg chord: lightest loop that meets T/W 1.5 inside the motor

WHY A CALIBRATED MODEL. One CFD run costs ~5 h here. The plain blade-element model (BEMT) put the loop at 620 N; CFD says
436 N, with the shortfall spread over the whole span (and a larger one on the trailing leg outboard). The same BEMT
over-predicted the Caradonna-Tung rotor by ~31 % while CFD matched the experiment, so the CFD is taken as the truth and
the BEMT is corrected to reproduce it:
    theta_eff(r) = theta(r) - (a0 + a1 (r/R - 0.6))     effective pitch loss: inflow the strip model does not see
    cd_eff       = cd + dcd                             extra section drag: form drag, interference, the turns
a0, a1, dcd are fitted by least squares to the CFD thrust per unit span (both legs averaged) and the total torque. The
corrected model then predicts what changing collective pitch or chord does, ON THE ASSUMPTION that the corrections stay
put. That holds for small changes; geometry changes that alter the leg-to-leg interference (gap, sweep) are not
predicted and need CFD. Every candidate from the sweep is therefore re-checked by CFD before it counts.

MOTOR ENVELOPE (U15XL KV38 on a sagged 24S pack, hot day): speed <= k_load KV V = 2554 rpm, torque <= k_t I_peak
= 0.2513 x 180 = 45.2 N m. T/W 1.5 is met if some speed inside that gives T >= 622.8 N with Q inside the torque limit.
"""
import json, math, os, sys, copy
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import toroid as T
import bemt

P, P01 = T.load_params()


class DragShift:
    """Wraps a polar database: same lift, drag + dcd."""
    def __init__(self, db, dcd): self.db, self.dcd = db, dcd
    def lookup(self, tc, re, mach, alpha):
        cl, cd = self.db.lookup(tc, re, mach, alpha)
        return cl, cd + self.dcd
    def prop(self, *a): return self.db.prop(*a)


def variant(p, **kw):
    q = copy.deepcopy(p)
    for k, v in kw.items(): q["rotor"][k] = v
    return q


def corrected_blade(p, a0, a1):
    b = T.leg_blade(p)
    x = b.r_def / b.R
    return bemt.Blade(b.R, b.r_hub, b.N, b.r_def, b.c_def, b.th_def - np.radians(a0 + a1 * (x - 0.6)), b.tc_def)


def solve(p, db, air, rpm, a0, a1, dcd, n=60):
    return bemt.axial(corrected_blade(p, a0, a1), DragShift(db, dcd), air, rpm, 0.0, n=n)


def stage_calibrate():
    from scipy.optimize import least_squares
    s = T.load_json("sizing.json"); L = T.load_json("loads_toroid.json"); C = T.load_json("cfd_toroid.json")
    air = s["inputs"]["air"]; rpm = s["cfd_rpm"]; db = T.build_polars(P01)
    rm = np.array(L["span"]["r"]); dr = np.gradient(rm)
    cfd_leg = 0.5 * (np.array(L["span"]["leading leg"]["dT_dr"]) + np.array(L["span"]["trailing leg"]["dT_dr"]))
    T_cfd, Q_cfd = C["T"], C["Q"]
    N = T.leg_blade(P).N

    def res(x):
        b = solve(P, db, air, rpm, *x)
        leg = np.interp(rm, b["r"], b["dT_dr"]) / N
        r1 = (leg - cfd_leg) * dr * N / T_cfd                       # spanwise shape, as a share of the total thrust
        return np.concatenate([r1, [3 * (b["T"] / T_cfd - 1), 3 * (b["Q"] / Q_cfd - 1)]])
    fit = least_squares(res, x0=[2.0, 0.0, 0.01], bounds=([-5, -10, -0.02], [10, 10, 0.2]))
    a0, a1, dcd = fit.x
    b0 = solve(P, db, air, rpm, 0, 0, 0); b = solve(P, db, air, rpm, a0, a1, dcd)
    out = {"a0_deg": a0, "a1_deg": a1, "dcd": dcd, "cost": float(fit.cost), "rpm": rpm,
           "cfd": {"T": T_cfd, "Q": Q_cfd, "FoM": C["FoM"]},
           "plain_bemt": {k: float(b0[k]) for k in ("T", "Q", "FoM")}, "calibrated": {k: float(b[k]) for k in ("T", "Q", "FoM")},
           "span_rms_error_pct_of_peak": float(100 * np.sqrt(np.mean((np.interp(rm, b["r"], b["dT_dr"]) / N - cfd_leg) ** 2)) / cfd_leg.max()),
           "alpha_eff_deg_at_075R": float(np.degrees(np.interp(0.75 * b["r"][-1] / (b["r"][-1] / T.leg_blade(P).R), b["r"], b["alpha"])))}
    T.save_json("opt_calibration.json", out)
    print(json.dumps(out, indent=1))
    return out


def stage_bias():
    """Same correction model fitted to BOTH CFD runs on totals only (thrust and torque at 2280 rpm; a1 held at a common
    value, so two unknowns a0 and dcd for two equations). The 2-blade reference shares the mesh recipe and the solver, so its
    corrections measure the method (mesh, strip theory); the toroid's excess over them is what the loop itself costs."""
    from scipy.optimize import least_squares
    s = T.load_json("sizing.json"); air = s["inputs"]["air"]; rpm = s["cfd_rpm"]; db = T.build_polars(P01)
    rows = {}
    for a1 in (0.0, T.load_json("opt_calibration.json")["a1_deg"]):
        for name, blade_fn in (("reference", lambda a0: T.reference_blade(P01)), ("toroid", lambda a0: T.leg_blade(P))):
            C = T.load_json(f"cfd_{name}.json")
            def run(x):
                b = blade_fn(0); xr = b.r_def / b.R
                bb = bemt.Blade(b.R, b.r_hub, b.N, b.r_def, b.c_def, b.th_def - np.radians(x[0] + a1 * (xr - 0.6)), b.tc_def)
                return bemt.axial(bb, DragShift(db, x[1]), air, rpm, 0.0, n=60)
            fit = least_squares(lambda x: [run(x)["T"] / C["T"] - 1, run(x)["Q"] / C["Q"] - 1], x0=[3.0, 0.02], bounds=([-5, -0.02], [12, 0.2]))
            r_ = run(fit.x)
            rows.setdefault(f"a1={a1:.2f}", {})[name] = {"a0_deg": float(fit.x[0]), "dcd": float(fit.x[1]), "T_fit": float(r_["T"]), "Q_fit": float(r_["Q"]),
                                                         "T_cfd": C["T"], "Q_cfd": C["Q"]}
    T.save_json("opt_bias.json", rows)
    print(json.dumps(rows, indent=1))


def stage_sweep_reference():
    """The same CFD-anchored sweep for the 2-blade reference (its own fitted corrections from `bias`, a1 as for the
    toroid): chord scale x collective. Blade mass scales with chord (wetted area) or chord^2 (volume) from 0.94 kg."""
    from scipy.optimize import brentq
    s = T.load_json("sizing.json"); I = s["inputs"]; air = I["air"]; db = T.build_polars(P01)
    a1 = T.load_json("opt_calibration.json")["a1_deg"]; cal = T.load_json("opt_bias.json")[f"a1={a1:.2f}"]["reference"]
    base = T.reference_blade(P01); xr = base.r_def / base.R
    q_max, rpm_max = I["kt"] * I["i_peak"], I["rpm_available_sag"]
    rows = []
    for fs in (0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1):
        for co in np.arange(-2.0, 10.01, 1.0):
            b = bemt.Blade(base.R, base.r_hub, base.N, base.r_def, base.c_def * fs, base.th_def + np.radians(co) - np.radians(cal["a0_deg"] + a1 * (xr - 0.6)), base.tc_def)
            f = lambda rpm: bemt.axial(b, DragShift(db, cal["dcd"]), air, rpm, 0.0, n=40)
            top = f(rpm_max)
            if top["Q"] > q_max:
                r_q = brentq(lambda r: f(r)["Q"] - q_max, 600, rpm_max, xtol=1.0); lim = f(r_q); limit = "torque"
            else:
                r_q, lim, limit = rpm_max, top, "speed"
            rows.append({"chord_scale": fs, "collective_add_deg": float(co), "tw_max": lim["T"] / I["T_hover"], "limit": limit, "rpm_limit": r_q,
                         "FoM_at_limit": float(lim["FoM"]), "mass_area_kg": P["mass"]["reference_blade_set_kg"] * fs,
                         "mass_volume_kg": P["mass"]["reference_blade_set_kg"] * fs ** 2, "solidity": b.solidity()})
        best = max((r for r in rows if r["chord_scale"] == fs), key=lambda r: r["tw_max"])
        print(f"2-blade chord x{fs:.1f}: best T/W {best['tw_max']:.3f} at coll {best['collective_add_deg']:+.0f} ({best['limit']}), FoM {best['FoM_at_limit']:.3f}, "
              f"mass {best['mass_area_kg']:.2f} kg (area) / {best['mass_volume_kg']:.2f} kg (volume)", flush=True)
    check = [r for r in rows if r["chord_scale"] == 1.0 and r["collective_add_deg"] == 0.0][0]
    T.save_json("opt_sweep_reference.json", {"calibration": cal, "a1_deg": a1, "rows": rows, "as_built_check": check,
                                              "best": max(rows, key=lambda r: r["tw_max"])})
    print("as built (x1.0, +0):", {k: round(v, 3) if isinstance(v, float) else v for k, v in check.items()})


def blade_area_volume(p):
    """Wetted area and solid volume of the loop set from the section integrals (checked against the STL within 0.5 %)."""
    path = T.loop_path(p)
    C = np.column_stack([path["r"] * np.cos(path["psi"]), path["r"] * np.sin(path["psi"]), path["z"]])
    seg = np.linalg.norm(np.roll(C, -1, axis=0) - C, axis=1); ds = 0.5 * (seg + np.roll(seg, 1))
    cache = {}
    def props(tc):
        k = round(float(tc), 4)
        if k not in cache: cache[k] = T.unit_section_props(k, n=200)
        return cache[k]
    pr = np.array([props(t) for t in path["tc"]])
    nl = p["rotor"]["n_loops"]
    return nl * float(np.sum(pr[:, 1] * path["chord"] * ds)), nl * float(np.sum(pr[:, 0] * path["chord"] ** 2 * ds))


def motor_check(p, db, air, cal, I, rpm_lo=600.0, slope=0.0):
    """Speed for T/W 1.5 and the torque there; thrust at the motor's limit (speed or torque, whichever binds first)."""
    from scipy.optimize import brentq
    a0, a1, dcd = cal["a0_deg"], cal["a1_deg"], cal["dcd"]
    f = lambda rpm: solve(p, db, air, rpm, a0, a1 - slope, dcd, n=40)      # slope: added twist per unit r/R about 0.6 R
    rpm_max, q_max = I["rpm_available_sag"], I["kt"] * I["i_peak"]
    top = f(rpm_max)
    out = {"T_at_rpm_max": top["T"], "Q_at_rpm_max": top["Q"], "FoM_at_rpm_max": top["FoM"]}
    if top["Q"] > q_max:                                             # torque binds first: find the speed where Q = q_max
        r_q = brentq(lambda r: f(r)["Q"] - q_max, rpm_lo, rpm_max, xtol=1.0)
        lim = f(r_q); out.update(limit="torque", rpm_limit=r_q)
    else:
        lim = top; out.update(limit="speed", rpm_limit=rpm_max)
    out["T_max_motor"] = lim["T"]; out["tw_max"] = lim["T"] / I["T_hover"]
    if top["T"] >= I["T_required"]:
        r15 = brentq(lambda r: f(r)["T"] - I["T_required"], rpm_lo, rpm_max, xtol=1.0); at = f(r15)
        out.update(rpm_tw15=r15, Q_tw15=at["Q"], amps_tw15=at["Q"] / I["kt"], FoM_tw15=at["FoM"], P_tw15=at["P"], cl_mean_tw15=float(np.sum(at["cl"] * at["dT_dr"] * at["dr"]) / at["T"]))
    out["meets_tw15"] = bool(out["tw_max"] >= P["vehicle"]["tw_required"])
    return out


def stage_sweep():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    s = T.load_json("sizing.json"); I = s["inputs"]; air = I["air"]; db = T.build_polars(P01)
    cal = T.load_json("opt_calibration.json")
    m_ref, A_ref, V_ref = P["mass"]["reference_blade_set_kg"], None, None
    g = T.load_json("geometry.json")["mass"]; A_ref, V_ref = g["reference_area_m2"], g["reference_volume_cm3"] / 1e6
    rows = []
    fracs = [0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50, 0.60]
    colls = np.arange(0.0, 12.01, 1.0)
    slopes = [-6.0, -3.0, 0.0, 3.0]          # added twist per unit r/R about 0.6 R (negative = more pitch inboard)
    for fr in fracs:
        q0 = variant(P, chord_fraction=fr, chord_min_m=min(P["rotor"]["chord_min_m"], 0.040 * fr / 0.5))
        A, V = blade_area_volume(q0)
        for sl in slopes:
            for co in colls:
                q = variant(q0["rotor"] and q0, collective_offset_deg=float(co))
                mc = motor_check(q, db, air, cal, I, slope=sl)
                rows.append({"chord_fraction": fr, "collective_add_deg": float(co), "twist_slope_deg": sl, "area_m2": A, "volume_cm3": 1e6 * V,
                             "mass_area_kg": m_ref * A / A_ref, "mass_volume_kg": m_ref * V / V_ref, **mc})
            best = max((r for r in rows if r["chord_fraction"] == fr and r["twist_slope_deg"] == sl), key=lambda r: r["tw_max"])
            print(f"f {fr:.2f} slope {sl:+.0f}: best T/W max {best['tw_max']:.3f} at coll {best['collective_add_deg']:+.0f} ({best['limit']}), "
                  f"FoM@max {best['FoM_at_rpm_max']:.3f}, area {A:.3f} m^2", flush=True)
    ok = [r for r in rows if r["meets_tw15"]]
    best_area = min(ok, key=lambda r: r["area_m2"]) if ok else None
    best_tw = max(rows, key=lambda r: r["tw_max"])
    T.save_json("opt_sweep.json", {"calibration": cal, "rows": rows, "n_feasible": len(ok), "lightest_feasible": best_area, "highest_tw": best_tw})
    fig, axs = plt.subplots(1, 2, figsize=(11, 3.8))
    for fr in fracs:
        rr = [r for r in rows if r["chord_fraction"] == fr and r["twist_slope_deg"] == 0.0]
        axs[0].plot([r["collective_add_deg"] for r in rr], [r["tw_max"] for r in rr], marker="o", ms=3, label=f"chord x{fr:.2f}")
        axs[1].plot([r["collective_add_deg"] for r in rr], [r["FoM_at_rpm_max"] for r in rr], marker="o", ms=3, label=f"chord x{fr:.2f}")
    axs[0].axhline(P["vehicle"]["tw_required"], color="#c0392b", ls="--", label="T/W 1.5")
    axs[0].set_ylabel("T/W at the motor limit"); axs[1].set_ylabel("figure of merit at 2554 rpm")
    for a_ in axs: a_.set_xlabel("collective pitch added [deg]"); a_.grid(alpha=.3); a_.legend(fontsize=7)
    fig.suptitle("Toroid, CFD-calibrated blade-element model: collective pitch x leg chord, no twist change (U15XL, 84 V, 180 A)", fontsize=9); fig.tight_layout()
    fig.savefig(os.path.join(T.RESULTS, "fig_opt_sweep.png"), dpi=140); plt.close(fig)
    print("feasible:", len(ok), "lightest:", json.dumps(best_area, default=float)[:400] if best_area else None)
    print("highest T/W:", json.dumps(best_tw, default=float)[:400])


def stage_predict(rotor):
    """The calibrated model's forecast for a design variant, written BEFORE its CFD exists, so the CFD tests the model."""
    s = T.load_json("sizing.json"); I = s["inputs"]; air = I["air"]; db = T.build_polars(P01); cal = T.load_json("opt_calibration.json")
    v = P["variants"][rotor]; q = T.rotor_params(P, rotor); rpm = v.get("cfd_rpm") or s["cfd_rpm"]
    slope = q["rotor"].get("twist_slope_deg", 0.0); q0 = variant(q, twist_slope_deg=0.0)         # the model adds the slope itself
    at = solve(q0, db, air, rpm, cal["a0_deg"], cal["a1_deg"] - slope, cal["dcd"])
    plain = bemt.axial(T.leg_blade(q), db, air, rpm, 0.0, n=60)
    out = {"rotor": rotor, "rpm": rpm, "overrides": v, "calibration": cal,
           "model_at_cfd_rpm": {"T": float(at["T"]), "Q": float(at["Q"]), "FoM": float(at["FoM"]), "amps": float(at["Q"] / I["kt"])},
           "plain_bemt_at_cfd_rpm": {"T": float(plain["T"]), "Q": float(plain["Q"]), "FoM": float(plain["FoM"])},
           "motor": motor_check(q0, db, air, cal, I, slope=slope)}
    T.save_json(f"opt_predict_{rotor}.json", out)
    print(json.dumps({k: out[k] for k in ("rpm", "model_at_cfd_rpm", "plain_bemt_at_cfd_rpm", "motor")}, indent=1, default=float))


if __name__ == "__main__":
    {"calibrate": stage_calibrate, "sweep": stage_sweep, "predict": stage_predict, "bias": stage_bias, "sweep_reference": stage_sweep_reference}[sys.argv[1]](*sys.argv[2:])

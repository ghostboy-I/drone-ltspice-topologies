"""Phase 2 driver: airfoil polars, BEMT, MIL design, design-RPM sweep, two-point refinement and the D:P trade.
Writes results/phase2.json, results/blade_final.csv and plots."""
import json, math, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.optimize import brentq, minimize
import airfoils, bemt, design_opt as do
import atmosphere as atm, momentum as mt, mission as ms
from common import ROOT, RESULTS, load_params, load_catalog, save_json

SCAL = lambda d: {k: (float(v) if isinstance(v, (np.floating, float)) else v) for k, v in d.items() if np.isscalar(v) or isinstance(v, (bool, str))}


class Rotor:
    """One blade design with cached BEMT evaluations for the vehicle-level questions."""
    def __init__(self, name, blade, db, p, A, ph1):
        self.name, self.b, self.db, self.p, self.A, self.ph1 = name, blade, db, p, A, ph1
        self.kappa = p["rotor"]["kappa"]
        self.W = ph1["vehicle"]["weight_n"]; self.n = p["vehicle"]["n_rotors"]; self.t_h = self.W / self.n
        self._c = {}

    def hover(self, atm_key, tw=1.0):
        k = ("h", atm_key, tw)
        if k not in self._c:
            self._c[k] = bemt.hover_at_thrust(self.b, self.db, self.A[atm_key], tw * self.t_h)
        return self._c[k]

    def at_rpm(self, atm_key, rpm):
        return bemt.axial(self.b, self.db, self.A[atm_key], rpm)

    def climb(self, atm_key, vc):
        return bemt.trim_rpm(lambda rpm: bemt.axial(self.b, self.db, self.A[atm_key], rpm, vc), self.t_h)

    def cruise(self, atm_key, v):
        k = ("c", atm_key, v)
        if k not in self._c:
            air, cda = self.A[atm_key], self.p["vehicle"]["cda_m2"]
            h = 0.0
            for _ in range(4):                                   # trim: fuselage drag + rotor H-forces set the tilt
                drag = 0.5 * air["rho"] * v * v * cda + self.n * h
                al, t_tot = math.atan2(drag, self.W), math.hypot(self.W, drag)
                e = bemt.edgewise_at_thrust(self.b, self.db, air, t_tot / self.n, v, al, kappa=self.kappa)
                h = e["H"]
            e0 = bemt.edgewise(self.b, self.db, air, e["rpm"], v, al, kappa=1.0)       # same RPM, ideal inflow, for reference
            e["P_ideal_inflow"], e["shaft_total"], e["drag_total"] = e0["P"] * (t_tot / self.n) / e0["T"], self.n * e["P"], drag
            e["equiv_LD"] = self.W * v / e["shaft_total"]
            self._c[k] = e
        return self._c[k]

    # interface used by mission.mission_energy
    def mission_vehicle(self, atm_key):
        rot, el, mis = self, self.p["electrical"], self.p["mission"]

        class V:
            def hover_shaft(s): return rot.n * rot.hover(atm_key)["P"]
            def climb_shaft(s, vc): return rot.n * rot.climb(atm_key, vc)["P"]
            def cruise(s, v): return rot.cruise(atm_key, v)
            def electrical(s, psh): return psh / (el["eta_motor_esc"] * el["eta_battery_wiring"]) + mis["avionics_w"]
        return V()

    def mission(self, atm_key, v=None):
        mis = self.p["mission"]
        m = ms.mission_energy(self.mission_vehicle(atm_key), mis, self.ph1["vehicle"]["range_m"], v or mis["cruise_speed_ms"])
        m["cruise"] = SCAL(m["cruise"])
        return m

    def motor_tw(self, atm_key, kv, i_peak, volts):
        """T/W this rotor reaches on a given motor: RPM limit (k_load KV V, capped at the tip-Mach limit) and current limit."""
        el, air = self.p["electrical"], self.A[atm_key]
        rpm_mach = mt.rpm_from_vtip(self.p["rotor"]["tip_mach_max"] * air["a"], 2 * self.b.R)
        rpm_av = min(el["k_load"] * kv * volts, rpm_mach)
        t_rpm = self.at_rpm(atm_key, rpm_av)["T"]
        p_lim = i_peak * volts * el["eta_motor_esc"]
        f = lambda rpm: self.at_rpm(atm_key, rpm)["P"] - p_lim
        rpm_cur = brentq(f, 300, 6000, xtol=0.5) if f(6000) > 0 else 6000
        t_cur = self.at_rpm(atm_key, rpm_cur)["T"]
        return {"volts": volts, "rpm_available": rpm_av, "tw_rpm_limit": t_rpm / self.t_h, "rpm_at_current_limit": rpm_cur,
                "tw_current_limit": t_cur / self.t_h, "tw": min(t_rpm, t_cur) / self.t_h}

    def summary(self, full=True):
        p, rot = self.p, self.p["rotor"]
        dkey = p["design_atmosphere"]; hot = self.A[dkey]
        h = self.hover(dkey)
        o = {"name": self.name, "D_in": 2 * self.b.R / p["constants"]["inch_to_m"], "pitch75_in": do.equivalent_pitch(self.b) / p["constants"]["inch_to_m"],
             "solidity": self.b.solidity(), "chord_max_mm": 1000 * float(self.b.c_def.max()), "chord_75_mm": 1000 * float(np.interp(0.75 * self.b.R, self.b.r_def, self.b.c_def)),
             "twist75_deg": math.degrees(float(np.interp(0.75 * self.b.R, self.b.r_def, self.b.th_def))),
             "volume_cm3": 1e6 * do.blade_volume(self.b), "mass_solid_g": 1000 * do.blade_volume(self.b) * p["design"]["laminate_density_kg_m3"],
             "hover": SCAL(h), "stall_margin_deg": do.stall_margin_deg(self.db, h, self.b.R),
             "mean_cl_hover": float(np.sum(h["cl"] * h["dT_dr"] * h["dr"]) / h["T"])}
        rpm_mach = mt.rpm_from_vtip(rot["tip_mach_max"] * hot["a"], 2 * self.b.R)
        o["rpm_mach_limit"] = rpm_mach
        o["tw_at_mach_limit"] = self.at_rpm(dkey, rpm_mach)["T"] / self.t_h
        for tag, tw in (("tw_required", p["vehicle"]["tw_required"]), ("tw_target", p["vehicle"]["tw_target"])):
            try:
                s = self.hover(dkey, tw)
                o[tag] = dict(SCAL(s), mach_ok=bool(s["tip_mach"] <= rot["tip_mach_max"] + 1e-9),
                              thrust_share_above_m05=float(np.sum((s["dT_dr"] * s["dr"])[s["mach"] > 0.5]) / s["T"]))
            except ValueError:
                o[tag] = None
        cat = load_catalog()["motors"]["tmotor_u15xl_kv38"]; el = p["electrical"]
        o["motor_u15xl_sag"] = self.motor_tw(dkey, cat["kv"], cat["peak_current_a"], el["cells_baseline"] * el["v_cell_sag"])
        o["motor_u15xl_fresh"] = self.motor_tw(dkey, cat["kv"], cat["peak_current_a"], self.ph1["motor_match"]["catalog_motors"]["tmotor_u15xl_kv38"]["v_fresh_loaded"])
        o["cruise"] = {f"{v:.0f}": SCAL(self.cruise(dkey, v)) for v in p["mission"]["cruise_speeds_ms"]}
        m = self.mission(p["mission"]["atmosphere"])
        o["mission"] = {k: m[k] for k in ("energy_wh", "pack_wh", "hover_energy_share", "segments")}
        if full:
            o["hover_by_atmosphere"] = {k: SCAL(self.hover(k)) for k in self.A}
            hh = self.A["hot_high"]
            o["tw_at_mach_limit_hot_high"] = self.at_rpm("hot_high", mt.rpm_from_vtip(rot["tip_mach_max"] * hh["a"], 2 * self.b.R))["T"] / self.t_h
            o["mission_by_speed"] = {f"{v:.0f}": self.mission(p["mission"]["atmosphere"], v)["pack_wh"] for v in p["mission"]["cruise_speeds_ms"]}
        return o


def run():
    t0 = time.time()
    p, ph1 = load_params(), json.load(open(os.path.join(RESULTS, "phase1.json")))
    c, rot, d, veh = p["constants"], p["rotor"], p["design"], p["vehicle"]
    db, comparison = airfoils.build_db(p)
    A = {k: atm.state(v["temp_c"], v["alt_m"]) for k, v in p["atmospheres"].items()}
    dkey = p["design_atmosphere"]; hot = A[dkey]
    R, rh, N = rot["diameter_in"] * c["inch_to_m"] / 2, rot["hub_radius_m"], rot["n_blades"]
    t_h = ph1["vehicle"]["t_hover"]
    out = {"airfoil_comparison": comparison, "polar_failed_cases": [list(f) for f in db.failed],
           "polar_summary": [dict(tc=k[0], re=k[1], mach=k[2], **s) for k, s in sorted(db.summary.items())],
           "naca4_area_factor": do.naca4_area_factor()}
    mk = lambda name, blade: Rotor(name, blade, db, p, A, ph1)

    # ---- design-RPM sweep (MIL hover designs at cl_design) -----------------------------------------------
    sweep, rotors = [], {}
    for rpm in d["hover_rpm_sweep"]:
        blade, raw = do.design_hover_blade(R, rh, N, rpm, t_h, hot, db, d, d["cl_design"])
        r_ = mk(f"MIL {rpm} rpm", blade); s = r_.summary(full=False); s["design_rpm"] = rpm; s["cl_design"] = d["cl_design"]
        s["raw_chord_max_mm"] = 1000 * float(raw["chord"].max()); s["mil_w"] = raw["w"]
        sweep.append(s); rotors[rpm] = r_
        print(f"  sweep {rpm}: hover {s['hover']['rpm']:.0f} rpm FoM {s['hover']['FoM']:.3f} T/W(U15XL,84V) {s['motor_u15xl_sag']['tw']:.2f} pack {s['mission']['pack_wh']:.0f} Wh [{time.time()-t0:.0f}s]", flush=True)
    out["rpm_sweep"] = sweep
    ok = [s for s in sweep if s["stall_margin_deg"] >= d["min_stall_margin_deg"] and s["tw_target"] and s["tw_target"]["mach_ok"]]
    best = max(ok, key=lambda s: s["motor_u15xl_sag"]["tw"])
    out["selection"] = {"rule": "largest T/W on the U15XL at the sagged pack voltage, among designs that keep the stall margin and reach T/W 2.0 inside the tip-Mach limit",
                        "design_rpm": best["design_rpm"], "n_eligible": len(ok)}
    base = rotors[best["design_rpm"]]

    cl_sweep = []
    for cl_d in d["cl_design_sweep"]:
        blade, _ = do.design_hover_blade(R, rh, N, best["design_rpm"], t_h, hot, db, d, cl_d)
        s = mk(f"cl {cl_d}", blade).summary(full=False); s["cl_design"] = cl_d; cl_sweep.append(s)
    out["cl_sweep"] = cl_sweep

    # ---- two-point refinement: twist offset, twist slope, chord taper; objective = mission pack energy ----
    vol0, m0 = do.blade_volume(base.b), base.mission(p["mission"]["atmosphere"])["pack_wh"]
    hist = []

    def objective(x):
        try:
            r_ = mk("trial", do.modify(base.b, *x))
            e = r_.mission(p["mission"]["atmosphere"])["pack_wh"]
            h = r_.hover(dkey); cr = r_.cruise(dkey, p["mission"]["cruise_speed_ms"])
            pen = 0.0
            pen += 50 * max(0.0, d["min_stall_margin_deg"] - do.stall_margin_deg(db, h, R)) ** 2
            pen += 2e3 * max(0.0, do.blade_volume(r_.b) / vol0 - 1.0)                 # no heavier than the starting blade
            pen += 2e3 * max(0.0, base.motor_tw(dkey, 38, 180, 84.0)["tw"] - r_.motor_tw(dkey, 38, 180, 84.0)["tw"] - 0.02)
            if float(np.min(r_.b.c_def)) < d["chord_tip_min_m"] * 0.999: pen += 1e3
        except Exception:
            return 1e9
        hist.append((list(map(float, x)), float(e), float(pen)))
        return e + pen
    res = minimize(objective, [0.0, 0.0, 0.0], method="Nelder-Mead",
                   options={"initial_simplex": [[0, 0, 0], [math.radians(1), 0, 0], [0, math.radians(3), 0], [0, 0, 0.3]], "xatol": 2e-4, "fatol": 0.5, "maxfev": 220})
    opt = mk("two-point optimised", do.modify(base.b, *res.x))
    out["two_point"] = {"x_twist_offset_deg": math.degrees(res.x[0]), "x_twist_slope_deg": math.degrees(res.x[1]), "x_chord_taper": float(res.x[2]),
                        "pack_wh_start": m0, "pack_wh_end": opt.mission(p["mission"]["atmosphere"])["pack_wh"], "evaluations": int(res.nfev),
                        "objective_end": float(res.fun), "converged": bool(res.success)}
    out["two_point"]["gain_pct"] = 100 * (1 - out["two_point"]["pack_wh_end"] / m0)
    print(f"  two-point: {out['two_point']} [{time.time()-t0:.0f}s]", flush=True)
    final = opt if (out["two_point"]["gain_pct"] > 0.3 and res.fun < m0) else base
    final.name = "final design"
    out["two_point"]["adopted"] = final is opt

    # ---- candidates (section 3.1): same planform, constant geometric pitch --------------------------------
    cands = {"final design": final}
    for cd in p["candidates"]:
        cands[cd["name"]] = mk(cd["name"], do.constant_pitch(final.b, cd["p_in"] * c["inch_to_m"], d, radius=cd["d_in"] * c["inch_to_m"] / 2))
    out["candidates"] = {}
    for k, r_ in cands.items():
        out["candidates"][k] = r_.summary()
        s = out["candidates"][k]
        print(f"  {k}: hover {s['hover']['rpm']:.0f} rpm FoM {s['hover']['FoM']:.3f} margin {s['stall_margin_deg']:.1f} pack {s['mission']['pack_wh']:.0f} Wh [{time.time()-t0:.0f}s]", flush=True)

    # ---- final design details ----------------------------------------------------------------------------
    fs = out["candidates"]["final design"]
    h = final.hover(dkey)
    out["final_span"] = {k: h[k].tolist() for k in ("r", "chord", "twist", "tc", "phi", "alpha", "cl", "cd", "re", "mach", "F", "vi", "dT_dr", "dQ_dr")}
    out["final_span"]["alpha_stall_deg"] = db.prop("alpha_stall", h["tc"], h["re"], h["mach"]).tolist()
    with open(os.path.join(RESULTS, "blade_final.csv"), "w") as f:
        f.write("# final Phase 2 blade, definition stations. twist = chord line above the disk plane\nr_m,r_over_R,chord_m,twist_deg,t_over_c\n")
        for r_, c_, th_, tc_ in zip(final.b.r_def, final.b.c_def, final.b.th_def, final.b.tc_def):
            f.write(f"{r_:.5f},{r_/R:.4f},{c_:.5f},{math.degrees(th_):.3f},{tc_:.4f}\n")
    curves = []
    for rpm in np.arange(800, 3001, 200):
        s = final.at_rpm(dkey, float(rpm)); curves.append({k: float(s[k]) for k in ("rpm", "T", "Q", "P", "CT", "CQ", "CP", "CT_h", "FoM", "tip_mach")})
    out["static_curves"] = curves
    adv = []
    for v in (0.0, 2.5, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0):
        s = bemt.axial(final.b, db, hot, fs["hover"]["rpm"], v)
        adv.append({"v": v, "J": v / (fs["hover"]["rpm"] / 60 * 2 * R), "T": s["T"], "P": s["P"], "CT": s["CT"], "CP": s["CP"], "eta": s["eta"] if s["T"] > 0 else float("nan")})
    out["axial_advance_curves"] = adv

    # ---- hand calc (Phase 1) vs BEMT ----------------------------------------------------------------------
    P1 = {(q["atm"], q["tw"]): q for q in ph1["operating_points"]}
    hc = []
    def row(q, hand, method, sim, note):
        hc.append({"quantity": q, "hand": hand, "method": method, "bemt": sim, "diff_pct": 100 * (sim / hand - 1), "note": note})
    row("Hover RPM, hot day", P1[(dkey, 1.0)]["rpm"], "CT from the Mach-limit sizing rule", fs["hover"]["rpm"], "design RPM was re-chosen in Phase 2 to match the motor")
    row("Hover shaft power per rotor, hot [W]", P1[(dkey, 1.0)]["p_shaft"], "momentum / FoM 0.70", fs["hover"]["P"], "BEMT FoM is higher than the assumed 0.70")
    row("Hover figure of merit", ph1["sizing"]["fom_assumed"], "assumed", fs["hover"]["FoM"], "XFOIL sections have high L/D; vendor data implies about the same")
    row("Hover FoM vs kappa/cd0 model", ph1["sizing"]["fom_model"], "kappa 1.15, cd0 0.011", fs["hover"]["FoM"], "")
    row("Hover torque, hot [N m]", P1[(dkey, 1.0)]["torque"], "P / omega", fs["hover"]["Q"], "lower RPM raises torque, lower power reduces it")
    row("Induced velocity in hover [m/s]", P1[(dkey, 1.0)]["vi"], "sqrt(T / 2 rho A)", float(np.sum(h["vi"] * h["dT_dr"] * h["dr"]) / h["T"]), "thrust-weighted mean; non-uniform inflow and tip loss raise it")
    if fs["tw_target"]:
        row("T/W 2.0 RPM, hot", P1[(dkey, 2.0)]["rpm"], "n ~ sqrt(T)", fs["tw_target"]["rpm"], "")
        row("T/W 2.0 shaft power, hot [W]", P1[(dkey, 2.0)]["p_shaft"], "P ~ T^1.5 at FoM 0.70", fs["tw_target"]["P"], "BEMT has no drag-rise model above the critical Mach number, so this is optimistic")
    c15 = fs["cruise"]["15"]
    row("Cruise shaft power at 15 m/s, total [W]", ph1["mission"]["cruise"]["shaft_total"], "Glauert + profile from FoM 0.70", c15["shaft_total"], "lower profile power; same kappa")
    row("Cruise shaft tilt at 15 m/s [deg]", math.degrees(ph1["mission"]["cruise"]["alpha"]), "atan(D/W)", math.degrees(c15["alpha_shaft"]), "rotor H-force adds drag")
    row("Mission pack energy [Wh]", ph1["mission"]["pack_wh"], "Phase 1 mission model", fs["mission"]["pack_wh"], "follows from the two power differences")
    ct_h_hand = t_h / (hot["rho"] * math.pi * R * R * mt.vtip_from_rpm(fs["hover"]["rpm"], 2 * R) ** 2)
    row("Mean lift coefficient (6 CT_h / sigma)", 6 * ct_h_hand / fs["solidity"], "blade-loading formula at the BEMT RPM", fs["mean_cl_hover"], "the formula assumes constant chord and uniform cl; this blade is tapered")
    out["hand_vs_bemt"] = hc

    # ---- updated mass budget (decision: keep MTOW, payload is an output) ----------------------------------
    cat = load_catalog(); mass = p["mass"]; mtow = ph1["vehicle"]["mtow_kg"]
    fixed = ph1["payload_range"]["fixed_non_battery_kg"]
    mbs = {}
    for tag, e in (("cited_303", mass["pack_wh_per_kg_cited"]), ("conservative_200", mass["pack_wh_per_kg_conservative"])):
        batt = fs["mission"]["pack_wh"] / e
        mbs[tag] = {"battery_kg": batt, "non_battery_kg": fixed, "drone_kg": fixed + batt, "drone_lb": (fixed + batt) / c["lb_to_kg"],
                    "payload_kg": mtow - fixed - batt, "payload_lb": (mtow - fixed - batt) / c["lb_to_kg"]}
    out["mass_budget"] = mbs
    out["runtime_s"] = time.time() - t0
    save_json("phase2.json", out)
    plots(out, p, db, final)
    return out


def plots(o, p, db, final):
    INK, ACC, RED, GRY = "#0b0b0b", "#2a78d6", "#c0392b", "#8e8d88"
    al = np.radians(np.arange(-6, 20.01, 0.25))
    fig, axs = plt.subplots(1, 3, figsize=(9.5, 3.0))
    for tc, col in ((0.09, ACC), (0.12, INK), (0.18, RED)):
        for re, ls in ((3e5, ":"), (1.2e6, "-")):
            cl, cd = db.lookup(tc, re, 0.3, al)
            axs[0].plot(np.degrees(al), cl, ls, color=col, label=f"44{int(tc*100):02d} Re {re:.1e}"); axs[1].plot(cd, cl, ls, color=col); axs[2].plot(np.degrees(al), cl / cd, ls, color=col)
    axs[0].set_xlabel("alpha [deg]"); axs[0].set_ylabel("cl"); axs[1].set_xlabel("cd"); axs[1].set_xlim(0, 0.04); axs[1].set_ylabel("cl"); axs[2].set_xlabel("alpha [deg]"); axs[2].set_ylabel("cl / cd")
    axs[0].legend(fontsize=6); [a.grid(alpha=.3) for a in axs]; fig.suptitle("XFOIL polars, NACA 44xx, Mach 0.30 (Viterna beyond stall)", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(RESULTS, "phase2_polars.png"), dpi=150); plt.close(fig)

    sp = o["final_span"]; x = np.array(sp["r"]) / final.b.R
    fig, axs = plt.subplots(2, 3, figsize=(9.5, 5.2))
    axs[0, 0].plot(x, 1000 * np.array(sp["chord"]), color=INK); axs[0, 0].set_ylabel("chord [mm]")
    axs[0, 1].plot(x, np.degrees(sp["twist"]), color=INK, label="twist"); axs[0, 1].plot(x, np.degrees(sp["phi"]), color=ACC, label="inflow angle"); axs[0, 1].set_ylabel("[deg]"); axs[0, 1].legend(fontsize=7)
    axs[0, 2].plot(x, 100 * np.array(sp["tc"]), color=INK); axs[0, 2].set_ylabel("t/c [%]")
    axs[1, 0].plot(x, np.degrees(sp["alpha"]), color=INK, label="alpha"); axs[1, 0].plot(x, sp["alpha_stall_deg"], color=RED, ls="--", label="stall"); axs[1, 0].set_ylabel("[deg]"); axs[1, 0].set_ylim(-4, 20); axs[1, 0].legend(fontsize=7)
    axs[1, 1].plot(x, sp["dT_dr"], color=INK); axs[1, 1].set_ylabel("dT/dr [N/m]")
    axs[1, 2].plot(x, np.array(sp["re"]) / 1e6, color=INK, label="Re / 1e6"); axs[1, 2].plot(x, sp["mach"], color=ACC, label="Mach"); axs[1, 2].legend(fontsize=7)
    for a in axs.flat: a.set_xlabel("r / R"); a.grid(alpha=.3)
    fig.suptitle("Final Phase 2 blade and its hover solution (hot day, MTOW)", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(RESULTS, "phase2_blade.png"), dpi=150); plt.close(fig)

    cv = o["static_curves"]
    fig, axs = plt.subplots(1, 3, figsize=(9.5, 2.9))
    axs[0].plot([q["rpm"] for q in cv], [q["CT"] for q in cv], color=INK, label="CT"); axs[0].plot([q["rpm"] for q in cv], [10 * q["CP"] for q in cv], color=ACC, label="10 x CP"); axs[0].plot([q["rpm"] for q in cv], [100 * q["CQ"] for q in cv], color=GRY, label="100 x CQ")
    axs[0].set_xlabel("RPM (static)"); axs[0].legend(fontsize=7)
    axs[1].plot([q["rpm"] for q in cv], [q["FoM"] for q in cv], color=INK); axs[1].set_xlabel("RPM (static)"); axs[1].set_ylabel("FoM"); axs[1].set_ylim(0.6, 0.9)
    ad = o["axial_advance_curves"]
    axs[2].plot([q["J"] for q in ad], [q["CT"] for q in ad], color=INK, label="CT"); axs[2].plot([q["J"] for q in ad], [10 * q["CP"] for q in ad], color=ACC, label="10 x CP"); axs[2].plot([q["J"] for q in ad], [q["eta"] for q in ad], color=RED, label="eta")
    axs[2].set_xlabel("advance ratio J = V / nD (axial)"); axs[2].legend(fontsize=7); axs[2].set_ylim(0, 1)
    [a.grid(alpha=.3) for a in axs]; fig.suptitle("Final blade: coefficients (propeller convention), hot day", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(RESULTS, "phase2_curves.png"), dpi=150); plt.close(fig)

    sw = o["rpm_sweep"]
    fig, ax = plt.subplots(figsize=(6.5, 3.6))
    scat = ax.scatter([s["hover"]["FoM"] for s in sw], [s["cruise"]["15"]["equiv_LD"] for s in sw], c=[s["mass_solid_g"] for s in sw], s=70, cmap="viridis", edgecolor="k")
    for s in sw: ax.annotate(f"{s['design_rpm']}", (s["hover"]["FoM"], s["cruise"]["15"]["equiv_LD"]), textcoords="offset points", xytext=(6, 4), fontsize=7)
    for k, s in o["candidates"].items(): 
        ax.scatter(s["hover"]["FoM"], s["cruise"]["15"]["equiv_LD"], marker="s", s=50, color=RED); ax.annotate(k, (s["hover"]["FoM"], s["cruise"]["15"]["equiv_LD"]), textcoords="offset points", xytext=(6, -10), fontsize=7, color=RED)
    fig.colorbar(scat, label="solid-section blade mass [g] (upper bound)")
    ax.set_xlabel("hover figure of merit"); ax.set_ylabel("cruise W V / P_shaft at 15 m/s"); ax.grid(alpha=.3)
    ax.set_title("Design-RPM sweep (labels: design hover RPM) and D:P candidates (red)", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(RESULTS, "phase2_pareto.png"), dpi=150); plt.close(fig)


if __name__ == "__main__":
    o = run()
    print(f"wrote results/phase2.json in {o['runtime_s']:.0f} s")

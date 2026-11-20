"""Conversion corridor and transition of the Osprey-style tilt-tricopter, flown on the prop program's own 54 x 18 blade.

Proof of concept: how well do the props designed for hover (Props/01_54x18_Composite) carry this airframe from hover
through conversion to wing-borne cruise, and back?

Model (pitch plane, quasi-steady, level flight path; x forward, z up, origin at the wing-root quarter chord):
  Unknowns per trim point (airspeed V, nacelle angle delta: 90 = hover, 0 = airplane):
    mode A (tail rotor running, elevator neutral): front-rotor rpm, body pitch theta, tail-rotor rpm
    mode B (tail rotor parked fore-aft, elevator trims):  front-rotor rpm, body pitch theta, elevator delta_e
  Equations:  sum F_x = m a,   sum F_z = W,   sum M_cg = 0.
  Rotors: Props bemt.edgewise() for every rotor at its own disk angle to the airflow. Front rotors: thrust axis at
    gamma = delta + theta above the flight path, so the disk tilt the BEMT sees is alpha_s = 90 deg - gamma (0 = hover,
    90 = airplane). Tail rotor: vertical in the body, alpha_s = -theta. Each returns thrust T along the shaft and the
    in-plane H-force. Hub moments of the rigid prop are not included.
  Wing: CL = a_w (alpha_w - alpha_L0), alpha_w = theta + i_w, capped at CL_max,3D and blended to a flat plate
    (CL = CD90/2 sin 2a, CD = CD90 sin^2 a) over 8 deg past stall. CD = cd(CL) [XFOIL, free transition] + CL^2/(pi e AR).
    cm0 about the wing-body aerodynamic centre (sizing.py, Raymer fuselage shift included).
  H-tail: CL_t = a_t (theta + i_t - eps + tau delta_e), eps = (d eps/d alpha) CL / a_w, tau = 0.5; the incidence i_t is
    rigged so the elevator is neutral in airplane-mode cruise at 25 m/s and the design mass (rig_tail()).
  Rest of the vehicle: CDA from the sizing drag build-up (fuselage, gear, nacelles, tail, parked tail rotor, leakage).
  Download (sizing.py strip theory, hover): front 4.6 %, tail 8.7 % of the rotor's thrust, fading as the wake is blown
    aft: f(V) = f_0 sin^2(delta) v_i^2 / (v_i^2 + V^2) (front), f_0 v_i^2 / (v_i^2 + V^2) (tail).
  CG: the hover CG plus the two rotor heads swinging forward on their 0.35 m arms.
Limits that bound the corridor: rotor rpm <= the motor's loaded speed (k_load KV V_sag), theta within [-10, +15] deg
  (ASSUMED cabin/payload limits), |delta_e| <= 25 deg and |CL_t| <= 1.0, wing below stall once it could carry 10 % of
  the weight (below that speed a stalled wing is a drag item, not a boundary), trim converged.
Accelerating/decelerating transition: the same trim with m a in the x equation, along the minimum-power nacelle
  schedule, at the fastest of 1, 0.5, 0.25 m/s^2 (ASSUMED rates) that trims at every speed; time from dV = a dt.
Missions (same 10 km leg, 60 s hover): full conversion (cruise in airplane mode), partial conversion (cruise at the
  minimum-power nacelle angle), nacelles up (90 deg throughout). Not modelled: rotor/wing wake interaction beyond the download, the wing in the slipstream, dynamics,
  control laws, gusts, hub moments.
"""
import json, math, os, sys, time
import numpy as np
from scipy.optimize import root
from tiltcfg import params, props_params, jload, save, RESULTS, PROPS, G0, LB
import wing_sections as wsec

import airfoils, bemt, atmosphere as atm                      # Props program (tiltcfg puts its src on the path)

DELTAS = list(range(90, -1, -5))
VS = [float(v) for v in range(0, 35)]
THETA_LIM = (-10.0, 15.0)
DE_MAX, CLT_MAX, TAU_E = 25.0, 1.0, 0.5
V_RIG = 25.0                                                  # tail incidence rigged for zero elevator here
BLEND = 8.0                                                   # deg past stall to the flat plate
RATES = (1.0, 0.5, 0.25)                                      # m/s^2: each path uses the fastest that trims at every speed


def eta_front(T, H, g, V, P):
    """Propulsive efficiency of a front rotor: the forward component of its force (thrust and in-plane H) times V, over shaft power."""
    return (T * math.cos(g) - H * math.sin(g)) * V / P if P > 1 and V > 0 else 0.0


class Craft:
    def __init__(self, mass_kg, label, i_t_deg=0.0):
        p, pp = params(), props_params()
        sz = jload(os.path.join(RESULTS, "sizing.json")); fn = jload(os.path.join(RESULTS, "final.json"))
        self.label, self.m, self.i_t = label, mass_kg, math.radians(i_t_deg)
        self.W = mass_kg * G0
        hot = pp["atmospheres"][pp["design_atmosphere"]]
        self.air = atm.state(hot["temp_c"], hot["alt_m"]); self.rho = self.air["rho"]
        d = np.loadtxt(os.path.join(PROPS, "results", "blade_final.csv"), delimiter=",", comments="#", skiprows=2)
        R = pp["rotor"]["diameter_in"] * pp["constants"]["inch_to_m"] / 2
        self.blade = bemt.Blade(R, pp["rotor"]["hub_radius_m"], pp["rotor"]["n_blades"], d[:, 0], d[:, 2], np.radians(d[:, 3]), d[:, 4])
        self.db, _ = airfoils.build_db(pp, n_proc=1)
        self.kappa, self.R, self.A = pp["rotor"]["kappa"], R, math.pi * R * R
        self.rpm_max = sz["motor"]["rpm_max"]
        el = pp["electrical"]; self.eta_el = el["eta_motor_esc"] * el["eta_battery_wiring"]
        w, L, st = sz["wing"], sz["layout"], sz["stability"]
        self.w, self.S, self.c, self.b, self.AR = w, w["S"], w["c"], w["b"], w["AR"]
        self.i_w, self.aL0, self.a_w = math.radians(w["incidence_deg"]), math.radians(w["alpha_L0_deg"]), w["a_per_rad"]
        self.CLmax, self.cm0, self.e = w["CLmax3d"], w["cm0"], p["wing"]["e_oswald"]
        self.CD90 = p["nacelle"]["download_cd_wing"]
        tsw, tdi = math.tan(math.radians(-w["sweep_deg"])), math.tan(math.radians(w["dihedral_deg"]))
        x_le_mac = self.b / 4 * tsw + 0.25 * self.c
        self.r_ac = np.array([x_le_mac - st["h_ac_wb"] * self.c, self.b / 4 * tdi])
        z_tip = self.b / 2 * tdi
        self.pivot = np.array([L["x_front_hub"], z_tip]); self.arm = p["nacelle"]["head_arm_m"]
        z_top = wsec.fuselage_top_z(sz, p["wing"]); z_b = z_top - 0.10
        self.r_tail = np.array([L["x_tail_hub"], z_b + p["tail"]["pylon_height_m"]])
        self.r_ht = np.array([st["x_ht_ac"], z_b]); self.S_h, self.a_t, self.eta_t = st["S_h"], st["a_t"], p["tail"]["eta_tail"]
        self.deps = st["deps_dalpha"]
        self.r_dw = np.array([L["x_tip_qc"], z_tip]); self.r_dt = np.array([L["x_tail_hub"], z_b])
        self.f_w, self.f_t = sz["download"]["chosen"]["frac"], sz["download_tail"]["frac"]
        dr = sz["drag"]; self.CDA_par = dr["CDA_total_m2"] - dr["wing_profile_m2"] - dr["induced_m2"]
        self.cg_h = np.array([fn["cg_hover"][0], fn["cg_hover"][2]]); self.k_head = 2 * st["m_head"] * self.arm / mass_kg
        # wing section drag polar (free transition, sizing Re): cd(cl) on the attached branch
        pol = jload(os.path.join(RESULTS, "wing_polars.json"))[f"{w['airfoil']}@{round(sz['wing_re'], -4):.0f}"]
        P = np.array(pol); i = int(np.argmax(P[:, 1])); o = np.argsort(P[: i + 1, 1])
        self.cl_tab, self.cd_tab = P[: i + 1, 1][o], P[: i + 1, 2][o]
        self.a_s = math.radians(w["alpha_stall_3d_deg"]); self.a_neg = self.aL0 - 0.8 * self.CLmax / self.a_w
        self.V_wing10 = math.sqrt(2 * 0.1 * self.W / (self.rho * self.S * self.CLmax))

    # --------------------------------------------------------------------------------------------------- pieces ----
    def cg(self, d):
        return self.cg_h + self.k_head * np.array([math.cos(d), math.sin(d) - 1.0])

    def hub(self, d):
        return self.pivot + self.arm * np.array([math.cos(d), math.sin(d)])

    def wing(self, a):
        """CL, CD, stalled flag at wing angle of attack a [rad]."""
        lin = self.a_w * (a - self.aL0)
        att_cl = min(max(lin, self.a_w * (self.a_neg - self.aL0)), self.CLmax)
        cd_att = lambda cl: float(np.interp(cl, self.cl_tab, self.cd_tab)) + cl * cl / (math.pi * self.e * self.AR)
        fp_cl, fp_cd = 0.5 * self.CD90 * math.sin(2 * a), self.CD90 * math.sin(a) ** 2 + float(self.cd_tab.min())
        past = max(a - self.a_s, self.a_neg - a, 0.0)
        k = min(past / math.radians(BLEND), 1.0)
        cl = (1 - k) * att_cl + k * fp_cl
        cd = (1 - k) * cd_att(att_cl) + k * max(fp_cd, cd_att(att_cl))
        return cl, cd, past > 0

    def rotor(self, rpm, V, alpha_s):
        return bemt.edgewise(self.blade, self.db, self.air, max(rpm, 150.0), V, alpha_s, kappa=self.kappa)

    # --------------------------------------------------------------------------------------------------- balance ---
    def balance(self, V, d, th, rpm_f, mode, ctl, a_x=0.0, detail=False):
        """Residuals [F_x - m a, F_z - W, M_cg] / (W, W, W x 1 m). mode 'A': ctl = tail rpm; 'B': ctl = elevator [rad]."""
        q = 0.5 * self.rho * V * V
        cg = self.cg(d)
        c_, s_ = math.cos(th), math.sin(th)
        rot = lambda r: np.array([c_ * (r[0] - cg[0]) - s_ * (r[1] - cg[1]), s_ * (r[0] - cg[0]) + c_ * (r[1] - cg[1])])
        F = np.zeros(2); M = 0.0; parts = {}
        def add(name, f, r):
            nonlocal F, M
            f = np.asarray(f, float); rr = rot(r); F += f; M += rr[0] * f[1] - rr[1] * f[0]
            parts[name] = f.tolist()
        # front rotors (two)
        g = d + th
        ef = self.rotor(rpm_f, V, math.pi / 2 - g)
        tvec, pvec = np.array([math.cos(g), math.sin(g)]), np.array([-math.sin(g), math.cos(g)])
        add("front rotors", 2 * (ef["T"] * tvec + ef["H"] * pvec), self.hub(d))
        vi_f = math.sqrt(max(ef["T"], 0) / (2 * self.rho * self.A))
        dwf = 2 * max(ef["T"], 0) * self.f_w * math.sin(d) ** 2 * vi_f ** 2 / (vi_f ** 2 + V * V + 1e-9)
        add("front download", [0.0, -dwf], self.r_dw)
        # tail rotor
        et = None; de = 0.0
        if mode == "A":
            gt = math.pi / 2 + th
            et = self.rotor(ctl, V, -th)
            add("tail rotor", et["T"] * np.array([math.cos(gt), math.sin(gt)]) + et["H"] * np.array([-math.sin(gt), math.cos(gt)]), self.r_tail)
            vi_t = math.sqrt(max(et["T"], 0) / (2 * self.rho * self.A))
            add("tail download", [0.0, -max(et["T"], 0) * self.f_t * vi_t ** 2 / (vi_t ** 2 + V * V + 1e-9)], self.r_dt)
        else:
            de = ctl
        # wing (lift up, drag aft: the flight path is level) and its moment
        aw = th + self.i_w
        CL, CD, stalled = self.wing(aw)
        add("wing", [-q * self.S * CD, q * self.S * CL], self.r_ac)
        M += q * self.S * self.c * self.cm0
        # H-tail
        at = th + self.i_t - self.deps * max(CL, 0.0) / self.a_w
        CLt = self.a_t * (at + TAU_E * de)
        add("H-tail", [0.0, self.eta_t * q * self.S_h * CLt], self.r_ht)
        add("parasite", [-q * self.CDA_par, 0.0], cg)
        add("weight", [0.0, -self.W], cg)
        res = np.array([(F[0] - self.m * a_x) / self.W, F[1] / self.W, M / self.W])
        if not detail: return res
        P = 2 * ef["P"] + (et["P"] if et else 0.0)
        return dict(res=res.tolist(), V=V, delta=math.degrees(d), theta=math.degrees(th), mode=mode, rpm_f=ef["rpm"], T_f=ef["T"], H_f=ef["H"],
                    P_f=ef["P"], rpm_t=(et["rpm"] if et else 0.0), T_t=(et["T"] if et else 0.0), P_t=(et["P"] if et else 0.0),
                    de=math.degrees(de), CL=CL, alpha_w=math.degrees(aw), stalled=stalled, CL_t=CLt, L_wing=q * self.S * CL,
                    P_shaft=P, P_batt=P / self.eta_el, download=dwf, a_x=a_x, mu_f=ef["mu"], conv=bool(ef["converged"] and (et is None or et["converged"])),
                    eta_prop=eta_front(ef["T"], ef["H"], g, V, ef["P"]), parts=parts)

    def trim(self, V, d_deg, mode, x0, a_x=0.0):
        d = math.radians(d_deg)
        sc = np.array([1000.0, 0.1, 1000.0 if mode == "A" else 0.2])
        f = lambda z: self.balance(V, d, z[1] * sc[1], z[0] * sc[0], mode, z[2] * sc[2], a_x)
        sol = root(f, np.asarray(x0) / sc, method="hybr", options={"xtol": 1e-8, "maxfev": 200})
        z = sol.x * sc
        out = self.balance(V, d, z[1], z[0], mode, z[2], a_x, detail=True)
        out["x"] = z.tolist()
        out["solved"] = bool(np.max(np.abs(out["res"])) < 1e-4)
        out["limits"] = self.limits(out)
        out["ok"] = out["solved"] and not out["limits"]
        return out

    def limits(self, o):
        lim = []
        if not o["conv"]: lim.append("BEMT not converged")
        if o["rpm_f"] > self.rpm_max: lim.append("front rpm")
        if o["mode"] == "A" and o["rpm_t"] > self.rpm_max: lim.append("tail rpm")
        if o["mode"] == "A" and o["T_t"] < 0: lim.append("tail thrust < 0")
        if not THETA_LIM[0] <= o["theta"] <= THETA_LIM[1]: lim.append("pitch")
        if abs(o["de"]) > DE_MAX or abs(o["CL_t"]) > CLT_MAX: lim.append("tail lift")
        if o["stalled"] and o["V"] >= self.V_wing10: lim.append("wing stall")
        if o["rpm_f"] < 300: lim.append("front rotor windmilling")
        return lim


# ------------------------------------------------------------------------------------------------------- sweeps -------
SEEDS = {"A": [[1900.0, 0.0, 1900.0], [2300.0, -5.0, 1200.0], [2100.0, 5.0, 1600.0], [2500.0, -8.0, 600.0]],
         "B": [[2200.0, 0.0, 0.0], [2400.0, -5.0, 0.1], [2000.0, 4.0, -0.1], [2550.0, -8.0, 0.2]]}


def trim_best(cr, V, d_deg, mode, x_prev, a_x=0.0):
    """Trim from the continuation guess; if that lands outside the limits, try the fixed seeds and keep the best
    feasible root (several roots exist: e.g. a deep-stall branch with the elevator hard over)."""
    o = cr.trim(V, d_deg, mode, x_prev, a_x) if x_prev is not None else None
    if o is not None and o["ok"]: return o
    best = o
    for sd in SEEDS[mode]:
        x0 = [sd[0], math.radians(sd[1]), sd[2]]
        o2 = cr.trim(V, d_deg, mode, x0, a_x)
        if o2["ok"] and (best is None or not best["ok"] or o2["P_batt"] < best["P_batt"]): best = o2
        elif best is None or (not best["ok"] and o2["solved"] and not best["solved"]): best = o2
    return best


def _sweep_delta(args):
    mass, label, d_deg, a_x, i_t = args
    os.nice(19)
    cr = Craft(mass, label, i_t)
    out = []
    for mode, order in (("A", VS), ("B", VS[::-1])):        # A up from hover, B down from cruise (wing-borne branch)
        x = None
        for V in order:
            if mode == "B" and V < 8: continue                # no elevator authority near hover
            o = trim_best(cr, V, d_deg, mode, x, a_x)
            x = o["x"] if o["ok"] else x
            o.pop("parts")
            out.append(o)
    return out


def rig_tail(mass):
    """Tail incidence [deg] that trims airplane-mode cruise at V_RIG with the elevator neutral: solve mode B with i_t = 0,
    then i_t = tau delta_e (the tail sees the same angle either way; the small change in the wing's share is iterated)."""
    i_t = 0.0
    for _ in range(4):
        cr = Craft(mass, "rig", i_t)
        o = trim_best(cr, V_RIG, 0, "B", None)
        i_t += TAU_E * o["de"]
    return i_t, o


def grid(mass, label, i_t, a_x=0.0, workers=2):
    import multiprocessing as mp
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(max_workers=workers, mp_context=mp.get_context("fork")) as ex:
        res = list(ex.map(_sweep_delta, [(mass, label, d, a_x, i_t) for d in DELTAS]))
    return [o for r in res for o in r]


def best_per_speed(pts):
    """Minimum battery power over nacelle angle and mode at each speed (feasible points only)."""
    out = {}
    for o in pts:
        if o["ok"] and (o["V"] not in out or o["P_batt"] < out[o["V"]]["P_batt"]): out[o["V"]] = o
    return [out[v] for v in sorted(out)]


def schedule(best):
    """Nacelle schedule along the minimum-power envelope, made monotonic (nacelles only tilt forward as speed rises)."""
    V = [o["V"] for o in best]; d = [o["delta"] for o in best]
    dm = list(np.minimum.accumulate(d))
    return V, dm


def path(cr, V_end, sched_V, sched_d, a_x, only=None):
    """Quasi-steady accelerating (a_x > 0) or decelerating (a_x < 0) transition along the schedule; at each speed the
    nacelle angle nearest the schedule that trims with the inertia term is used (only = a fixed nacelle angle)."""
    hist = []
    x = {"A": None, "B": None}
    for V in [v for v in VS if v <= V_end]:
        dt = float(np.interp(V, sched_V, sched_d))
        cands = [only] if only is not None else sorted(set(DELTAS), key=lambda d_: abs(d_ - dt))
        got = None
        for d_ in cands[:6]:
            for mode in (("A", "B") if V >= 8 else ("A",)):
                o = trim_best(cr, V, d_, mode, x[mode], a_x)
                if o["ok"] and (got is None or o["P_batt"] < got["P_batt"] - 1e-9 and abs(d_ - dt) <= abs(got["delta"] - dt)):
                    got = o
            if got: break
        if got is None:
            hist.append({"V": V, "ok": False}); continue
        x[got["mode"]] = got["x"]; got.pop("parts"); hist.append(got)
    # time and energy: dt = dV / |a| between grid speeds (trapezoid on battery power)
    ok = [h for h in hist if h.get("ok")]
    t, E = [0.0], 0.0
    for h0, h1 in zip(ok[:-1], ok[1:]):
        dtt = (h1["V"] - h0["V"]) / abs(a_x); t.append(t[-1] + dtt); E += 0.5 * (h0["P_batt"] + h1["P_batt"]) * dtt
    for h, tt in zip(ok, t): h["t"] = tt
    miss = [h["V"] for h in hist if not h.get("ok")]
    d = sum(0.5 * (a["V"] + b["V"]) * (b["t"] - a["t"]) for a, b in zip(ok[:-1], ok[1:]))
    return {"a": a_x, "points": ok, "missing_V": miss, "complete": not miss, "time_s": t[-1], "energy_wh": E / 3600, "distance_km": d / 1000}


def path_any(cr, V_end, sV, sd, sign, only=None):
    """The fastest rate in RATES (sign +1 accelerate, -1 decelerate) that trims at every speed; the slowest if none does."""
    for a in RATES:
        p = path(cr, V_end, sV, sd, sign * a, only)
        if p["complete"]: return p
    return p


# ------------------------------------------------------------------------------------------------------- checks -------
def hand_checks(cr, pts):
    sz = jload(os.path.join(RESULTS, "sizing.json"))
    out = {}
    # H1 hover: theta = 0 by x-balance; two linear equations in T_f, T_t (vertical forces and moments about the CG)
    d = math.pi / 2; cg = cr.cg(d); xh, xt, xw, xdt = cr.hub(d)[0] - cg[0], cr.r_tail[0] - cg[0], cr.r_dw[0] - cg[0], cr.r_dt[0] - cg[0]
    A = np.array([[2 * (1 - cr.f_w), 1 - cr.f_t], [2 * (xh - cr.f_w * xw), xt - cr.f_t * xdt]])
    Tf, Tt = np.linalg.solve(A, [cr.W, 0.0])
    h = next(o for o in pts if o["V"] == 0 and o["delta"] == 90 and o["mode"] == "A")
    Pid = Tf ** 1.5 / math.sqrt(2 * cr.rho * cr.A)
    out["H1_hover"] = {"T_f_hand": Tf, "T_t_hand": Tt, "T_f_trim": h["T_f"], "T_t_trim": h["T_t"], "theta_trim_deg": h["theta"],
                       "P_f_bemt_w": h["P_f"], "P_ideal_w": Pid, "FoM": Pid / h["P_f"], "rpm_f": h["rpm_f"], "rpm_t": h["rpm_t"]}
    # H2 airplane cruise 25 m/s: drag and power against sizing.py (axial BEMT CT(J) curves) and the annulus BEMT
    c = [o for o in pts if o["V"] == 25.0 and o["delta"] == 0 and o["ok"]]
    if c:
        c = min(c, key=lambda o: o["P_batt"])
        T_need = c["T_f"]
        ax = bemt.trim_rpm(lambda rpm: bemt.axial(cr.blade, cr.db, cr.air, rpm, 25.0), T_need)
        out["H2_cruise"] = {"thrust_per_rotor_trim_n": T_need, "sizing_thrust_total_n": sz["cruise"]["thrust_required_n"],
                            "P_shaft_trim_w": c["P_shaft"], "sizing_P_shaft_w": sz["cruise"]["shaft_power_w"],
                            "P_axial_bemt_same_T_w": 2 * ax["P"], "rpm_trim": c["rpm_f"], "rpm_axial_same_T": ax["rpm"],
                            "theta_deg": c["theta"], "CL": c["CL"], "sizing_CL": sz["wing"]["CL_cruise"], "eta_prop": c["eta_prop"],
                            "eta_ideal": 2 / (1 + math.sqrt(1 + T_need / (0.5 * cr.rho * 25.0 ** 2 * cr.A)))}
    # H3 statics closure: re-sum the parts of one mid-conversion point independently
    m = [o for o in pts if o["ok"] and 30 <= o["delta"] <= 60 and o["V"] >= 10]
    if m:
        o = m[len(m) // 2]
        full = cr.balance(o["V"], math.radians(o["delta"]), math.radians(o["theta"]), o["x"][0], o["mode"], o["x"][2] if o["mode"] == "A" else math.radians(o["de"]), detail=True)
        Fs = np.sum([v for v in full["parts"].values()], axis=0)
        out["H3_statics"] = {"V": o["V"], "delta": o["delta"], "sum_Fx_N": float(Fs[0]), "sum_Fz_N": float(Fs[1]), "W_N": cr.W,
                             "parts_N": full["parts"], "moment_residual": full["res"][2]}
    # H4 rotor energy budget, P = F_prop V + kappa T v_i + P_0: v_i from Glauert's equation (solved by fixed point) and
    # profile power P_0 = P_0,hover (Omega/Omega_h)^3 (1 + 4.65 mu^2), with P_0,hover = P_hover - kappa T v_i,hover
    vh = math.sqrt(h["T_f"] / (2 * cr.rho * cr.A)); P0h = h["P_f"] - cr.kappa * h["T_f"] * vh
    rows = []
    for o in [o for o in pts if o["ok"] and o["V"] in (10.0, 20.0, 25.0) and o["delta"] in (90, 45, 0)]:
        g = math.radians(o["delta"] + o["theta"]); a = math.pi / 2 - g; V = o["V"]
        vi = vh
        for _ in range(200): vi = 0.5 * vi + 0.5 * o["T_f"] / (2 * cr.rho * cr.A * math.hypot(V * math.cos(a), V * math.sin(a) + vi))
        Fp = (o["T_f"] * math.cos(g) - o["H_f"] * math.sin(g)) * V
        P0 = P0h * (o["rpm_f"] / h["rpm_f"]) ** 3 * (1 + 4.65 * o["mu_f"] ** 2)
        rows.append({"V": V, "delta": o["delta"], "mode": o["mode"], "T_f": o["T_f"], "F_prop_V_w": Fp, "P_induced_w": cr.kappa * o["T_f"] * vi,
                     "P_profile_w": P0, "P_hand_w": Fp + cr.kappa * o["T_f"] * vi + P0, "P_bemt_w": o["P_f"]})
    out["H4_energy"] = {"P0_hover_w": P0h, "rows": rows}
    return out


def blade_loads(cr, r):
    """Edgewise penalty of a fixed-pitch prop: one blade's root flap moment (mean and 1P) and the hub roll/pitch moments
    at the cruise points of the three strategies, against hover. The trim leaves the hub moments out; these show their size."""
    h = next(o for o in r["heli_mode"] if o["V"] == 0)
    eh = cr.rotor(h["rpm_f"], 0.0, 0.0)
    out = {"hover": {"rpm": h["rpm_f"], "M_mean": eh["blade_M_mean"], "M_1P": eh["blade_M_1P"]}}
    for k, b in (("airplane", "best_range_airplane"), ("partial", "best_range_any"), ("nacelles_up", "best_range_heli")):
        if not r.get(b): continue
        c = min([o for o in r["points"] if o["ok"] and o["V"] == r[b]["V"] and (k != "airplane" or o["delta"] == 0) and (k != "nacelles_up" or o["delta"] == 90)
                 and (k != "partial" or round(o["delta"]) == round(r[b]["delta"]))], key=lambda o: o["P_batt"])
        a_s = math.radians(90 - c["delta"] - c["theta"])
        e = cr.rotor(c["rpm_f"], c["V"], a_s)
        out[k] = {"V": c["V"], "delta": c["delta"], "alpha_s_deg": math.degrees(a_s), "rpm": c["rpm_f"], "M_mean": e["blade_M_mean"], "M_1P": e["blade_M_1P"],
                  "M_roll": e["M_roll"], "M_pitch": e["M_pitch"], "alpha_max_deg": e["alpha_max_deg"], "tip_mach_adv": e["tip_mach_adv"]}
    return out


# ------------------------------------------------------------------------------------------------------- main ---------
def run_case(mass, label, i_t):
    t0 = time.time()
    pts = grid(mass, label, i_t)
    res = post(mass, label, i_t, pts)
    res["runtime_s"] = time.time() - t0
    return res


def post(mass, label, i_t, pts):
    cr = Craft(mass, label, i_t)
    for o in pts:
        if "T_f" in o: o["eta_prop"] = eta_front(o["T_f"], o["H_f"], math.radians(o["delta"] + o["theta"]), o["V"], o["P_f"])
    best = best_per_speed(pts)
    sV, sd = schedule(best)
    ok = [o for o in pts if o["ok"]]
    heli = sorted([o for o in ok if o["delta"] == 90], key=lambda o: (o["V"], o["P_batt"]))
    air = sorted([o for o in ok if o["delta"] == 0], key=lambda o: (o["V"], o["P_batt"]))
    lo = lambda L: {v: min((o for o in L if o["V"] == v), key=lambda o: o["P_batt"]) for v in sorted({o["V"] for o in L})}
    H, Ap = lo(heli), lo(air)
    res = {"label": label, "mass_kg": mass, "W_n": cr.W, "rpm_max": cr.rpm_max, "points": pts, "best": best, "schedule": {"V": sV, "delta": sd},
           "heli_mode": list(H.values()), "airplane_mode": list(Ap.values()), "V_wing10": cr.V_wing10, "i_t_deg": i_t, "rho": cr.rho, "disk_area_m2": cr.A}
    res["airplane_V_min"] = min(Ap) if Ap else None; res["airplane_V_max"] = max(Ap) if Ap else None
    res["heli_V_max"] = max(H) if H else None
    if Ap:
        br = min(Ap.values(), key=lambda o: o["P_batt"] / max(o["V"], 1e-6))
        res["best_range_airplane"] = {"V": br["V"], "P_batt_w": br["P_batt"], "wh_per_km": br["P_batt"] / br["V"] / 3.6, "eta_prop": br["eta_prop"]}
    if H:
        hm = [o for o in H.values() if o["V"] > 0]
        bh = min(hm, key=lambda o: o["P_batt"] / o["V"]) if hm else None
        if bh: res["best_range_heli"] = {"V": bh["V"], "P_batt_w": bh["P_batt"], "wh_per_km": bh["P_batt"] / bh["V"] / 3.6}
    bp = min([o for o in best if o["V"] > 0], key=lambda o: o["P_batt"] / o["V"])
    res["best_range_any"] = {"V": bp["V"], "delta": bp["delta"], "mode": bp["mode"], "P_batt_w": bp["P_batt"], "wh_per_km": bp["P_batt"] / bp["V"] / 3.6,
                             "eta_prop": bp["eta_prop"], "wing_lift_frac": bp["L_wing"] / cr.W}
    res["paths"] = {}
    if res.get("best_range_airplane"):
        Vc = res["best_range_airplane"]["V"]
        res["paths"]["airplane"] = (path_any(cr, Vc, sV, sd, +1), path_any(cr, Vc, sV, sd, -1))
        d_end = float(np.interp(Vc, sV, sd))           # the last step tilts the nacelles to 0 at constant speed
        at_Vc = {round(o["delta"]) for o in ok if o["V"] == Vc}
        res["convert_at_cruise"] = {"V": Vc, "from_delta": d_end, "all_angles_trim": all(d_ in at_Vc for d_ in DELTAS if d_ <= d_end + 1e-6),
                                    "angles_trimming": sorted(at_Vc)}
    res["paths"]["partial"] = (path_any(cr, bp["V"], sV, sd, +1), path_any(cr, bp["V"], sV, sd, -1))
    if res.get("best_range_heli"):
        Vh = res["best_range_heli"]["V"]
        res["paths"]["nacelles_up"] = (path_any(cr, Vh, sV, sd, +1, only=90), path_any(cr, Vh, sV, sd, -1, only=90))
    res["hand_checks"] = hand_checks(cr, pts)
    res["blade_loads"] = blade_loads(cr, res)
    return res


def mission(r, pp, cruise_km=10.0, hover_s=60.0):
    """Same leg both ways: hover (take-off + landing), accelerate, cruise at best range, decelerate. Tilt-rotor: along the
    nacelle schedule to airplane mode. Nacelles-up: the same accelerations with the nacelles fixed at 90 deg."""
    h0 = next(o for o in r["heli_mode"] if o["V"] == 0)
    E_h = h0["P_batt"] * hover_s / 3600
    out = {"hover_s": hover_s, "cruise_km": cruise_km, "hover_wh": E_h}
    def leg(best, to, ti):
        d_tr = to["distance_km"] + ti["distance_km"]
        E_c = best["wh_per_km"] * max(cruise_km - d_tr, 0)
        return {"V_cruise": best["V"], "wh_per_km": best["wh_per_km"], "accel_wh": to["energy_wh"], "decel_wh": ti["energy_wh"], "decel_a": ti["a"],
                "transition_km": d_tr, "transition_s": to["time_s"] + ti["time_s"], "cruise_wh": E_c,
                "total_wh": E_h + to["energy_wh"] + ti["energy_wh"] + E_c, "complete": to["complete"] and ti["complete"]}
    for k, b in (("airplane", "best_range_airplane"), ("partial", "best_range_any"), ("nacelles_up", "best_range_heli")):
        if k in r["paths"] and r.get(b): out[k] = leg(r[b], *r["paths"][k]) | {"accel_a": r["paths"][k][0]["a"]}
    return out


def main(post_only=False):
    p, pp = params(), props_params()
    sz = jload(os.path.join(RESULTS, "sizing.json")); fn = jload(os.path.join(RESULTS, "final.json"))
    cases = [(sz["W_n"] / G0, "sizing MTOW (280 lb)"), (fn["mass_model_kg"], "current mass estimate")]
    out = {"assumptions": {"theta_lim_deg": THETA_LIM, "de_max_deg": DE_MAX, "CLt_max": CLT_MAX, "tau_e": TAU_E, "V_rig": V_RIG,
                           "rates_ms2": RATES, "blend_deg": BLEND, "deltas": DELTAS, "V": VS}}
    old = jload(os.path.join(RESULTS, "transition.json")) if post_only else None
    if post_only:
        out["tail_rig"] = old["tail_rig"]; i_t = old["tail_rig"]["i_t_deg"]
    else:
        i_t, rig = rig_tail(cases[0][0])
        out["tail_rig"] = {"i_t_deg": i_t, "V": V_RIG, "theta_deg": rig["theta"], "de_deg": rig["de"], "CL": rig["CL"], "CL_t": rig["CL_t"]}
    print("tail rig:", out["tail_rig"], flush=True)
    for mass, label in cases:
        print(f"{label}: {mass:.1f} kg", flush=True)
        key = "design" if label.startswith("sizing") else "current"
        if post_only:
            t0 = time.time(); r = post(mass, label, i_t, old[key]["points"]); r["runtime_s"] = old[key].get("runtime_s", 0) + time.time() - t0
        else:
            r = run_case(mass, label, i_t)
        r["mission"] = mission(r, pp)
        out[key] = r
        ok = [o for o in r["points"] if o["ok"]]
        print(f"  {len(ok)}/{len(r['points'])} trim points feasible, {r['runtime_s']:.0f} s; airplane mode {r['airplane_V_min']}-{r['airplane_V_max']} m/s, "
              f"nacelles-up to {r['heli_V_max']} m/s", flush=True)
        if r.get("best_range_airplane"): print("  best range airplane:", {k: round(v, 3) for k, v in r["best_range_airplane"].items()})
        if r.get("best_range_heli"): print("  best range nacelles-up:", {k: round(v, 3) for k, v in r["best_range_heli"].items()})
        print("  best range any angle:", {k: (round(v, 3) if isinstance(v, float) else v) for k, v in r["best_range_any"].items()})
        print("  convert at cruise:", r.get("convert_at_cruise"))
        for k, pr in r["paths"].items():
            for p_ in pr: print(f"  {k}: a {p_['a']:+.2f}, {p_['time_s']:.1f} s, {p_['energy_wh']:.1f} Wh, {p_['distance_km']:.3f} km, missing V {p_['missing_V']}")
        print("  hand checks:", json.dumps(r["hand_checks"], default=float)[:1500], flush=True)
        print("  mission:", json.dumps(r["mission"], default=float), flush=True)
    save("transition.json", out)


if __name__ == "__main__":
    main(post_only="--post" in sys.argv)

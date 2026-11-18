"""Hand check for exploration 06: a two-region momentum model of the coaxial pair, solved by hand-sized equations.

Notation: A = disk area, k = h / sqrt(R^2 + h^2) (vortex cylinder), rho = density.
Upper rotor (own induced v_u, plus the lower rotor's inflow (1 - k) vbar_l felt at the upper disk):
    T_u = 2 rho A v_u (v_u + (1 - k) vbar_l)                    momentum: mass flow x far-wake increment 2 v_u
    P_u = T_u (v_u + (1 - k) vbar_l)                           power = thrust x velocity through the disk
Upper wake at the lower disk: w = (1 + k) v_u over the core area A_w = A / (1 + k) (continuity: A_w w = A v_u, the upper's own flow).
Lower rotor, core (inside the wake, own v_c) and clean annulus (own v_a):
    T_l = 2 rho [A_w (w + v_c) v_c + (A - A_w) v_a^2]
    P_l = 2 rho [A_w (w + v_c)^2 v_c + (A - A_w) v_a^3]
    vbar_l = (A_w v_c + (A - A_w) v_a) / A
Two closures for the lower rotor:
    uniform: v_c = v_a (a blade that loads the disk as if the wake were not there)
    optimal: equal marginal cost dP/dT in both regions:
             (w + v_c)(w + 3 v_c) / (w + 2 v_c) = 1.5 v_a
kappa_int = (P_u + P_l) / (2 (T/2)^1.5 / sqrt(2 rho A))  with the thrust split from BEMT (or 50/50 for the textbook limits).
Limits: h -> 0 (k = 0, A_w = A) gives kappa = sqrt(2) exactly; far wake (k = 1) gives 1.618 (uniform) or less (optimal).
"""
import json, math, os
import numpy as np
from scipy.optimize import fsolve
here = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(here, "..", "..", "results", "explore")


def pair(T, split, k, R, rho, closure):
    A = math.pi * R * R; Aw = A / (1 + k); Tu, Tl = split * T, (1 - split) * T
    v0 = math.sqrt(T / (2 * rho * A))

    def eqs(x):
        vu, vc, va = x
        if closure == "uniform": va_ = vc
        else: va_ = va
        vbar = (Aw * vc + (A - Aw) * va_) / A; w = (1 + k) * vu
        e1 = 2 * rho * A * vu * (vu + (1 - k) * vbar) - Tu
        e2 = 2 * rho * (Aw * (w + vc) * vc + (A - Aw) * va_ ** 2) - Tl
        e3 = (va - vc) if closure == "uniform" else ((w + vc) * (w + 3 * vc) / (w + 2 * vc) - 1.5 * va)
        return [e1 / T, e2 / T, e3 / v0]
    vu, vc, va = fsolve(eqs, [0.6 * v0, 0.4 * v0, 0.6 * v0], xtol=1e-12)
    vbar = (Aw * vc + (A - Aw) * va) / A; w = (1 + k) * vu
    Pu = Tu * (vu + (1 - k) * vbar)
    Pl = 2 * rho * (Aw * (w + vc) ** 2 * vc + (A - Aw) * va ** 3)
    P_iso2 = 2 * (T / 2) ** 1.5 / math.sqrt(2 * rho * A)
    return {"v_u": vu, "v_core": vc, "v_annulus": va, "w": w, "P": Pu + Pl, "kappa": (Pu + Pl) / P_iso2}


if __name__ == "__main__":
    o = json.load(open(os.path.join(RES, "e06_coax_spacing.json")))
    R = 0.6858
    rows = [r for r in o["rows"] if "error" not in r]
    T, rho = 1000.0, 1.0      # kappa is independent of T and rho in this model: every velocity scales with v0 = sqrt(T / (2 rho A))
    out = {"limits": {}, "rows": []}
    for name, k in (("h -> 0", 0.0), ("far wake", 1.0)):
        out["limits"][name] = {c: pair(T, 0.5, k, R, rho, c)["kappa"] for c in ("uniform", "optimal")}
    print("  limits (50/50 split):", {n: {c: round(v, 4) for c, v in d.items()} for n, d in out["limits"].items()}, " exact: sqrt2 =", round(math.sqrt(2), 4), ", Leishman far 1.2808")
    print(f"  {'h/D':>5s} {'k':>6s} {'split':>6s} | {'uniform':>8s} {'optimal':>8s} {'BEMT':>7s}")
    for r in rows:
        u = pair(T, r["split_upper"], r["k"], R, rho, "uniform"); op = pair(T, r["split_upper"], r["k"], R, rho, "optimal")
        q = {"h_over_D": r["h_over_D"], "k": r["k"], "split_upper": r["split_upper"], "kappa_uniform": u["kappa"], "kappa_optimal": op["kappa"],
             "kappa_bemt": r["kappa_bemt"], "v_core_over_v_annulus_optimal": op["v_core"] / op["v_annulus"]}
        out["rows"].append(q)
        print(f"  {q['h_over_D']:5.2f} {q['k']:6.3f} {q['split_upper']:6.3f} | {q['kappa_uniform']:8.3f} {q['kappa_optimal']:8.3f} {q['kappa_bemt']:7.3f}   v_c/v_a opt {q['v_core_over_v_annulus_optimal']:.2f}")
    # cruise overlap: lens area at the reference spacing, by hand
    ref = next(r for r in rows if r["h_over_D"] == 0.2)
    chi = math.atan2(ref["mu"], ref["lam"]); d = 0.2 * 2 * R * math.tan(chi)
    f = (2 * R * R * math.acos(d / (2 * R)) - d / 2 * math.sqrt(4 * R * R - d * d)) / (math.pi * R * R)
    out["cruise_overlap_ref"] = {"mu": ref["mu"], "lambda": ref["lam"], "chi_deg": math.degrees(chi), "d_over_R": d / R, "f": f,
                                 "f_at_d_eq_R_exact": (2 * math.pi / 3 - math.sqrt(3) / 2) / math.pi,
                                 "h_over_D_for_zero_overlap": 2 * R / math.tan(chi) / (2 * R)}
    print("  cruise overlap at h/D 0.2:", {k: round(v, 4) for k, v in out["cruise_overlap_ref"].items()})
    json.dump(out, open(os.path.join(RES, "e06_hand_check.json"), "w"), indent=1)

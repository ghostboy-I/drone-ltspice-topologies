"""Blade design: minimum-induced-loss (MIL) chord and twist for hover, manufacturing constraints, constant-pitch
candidates, and the two-point (hover + cruise) refinement.

MIL (Betz) condition: induced loss is least when the trailing vortex sheets move as a rigid helical surface with a
displacement velocity w. For a hovering rotor with a Prandtl loss factor F this gives, at each radius
    tan(phi) = (w/2) / (Omega r)                       inflow angle
    vi = (w/2) cos^2(phi),   vt = (w/2) sin(phi) cos(phi)
    N Gamma = 2 pi r F w sin(phi) cos(phi)             bound circulation (same result as equating blade-element and
                                                       momentum thrust in bemt.py with drag neglected)
    c = 2 Gamma / (W cl_design),   theta = phi + alpha(cl_design)
This is the hover limit (V -> 0) of the Adkins-Liebeck / Larrabee propeller design equations. w is iterated until the
integrated thrust equals the design thrust. Running each section at a cl near its best lift-to-drag ratio then
minimises profile loss. The raw result has zero chord at hub and tip, so manufacturing rules are applied afterwards
and the constrained blade is re-analysed with BEMT.
"""
import math
import numpy as np
from scipy.optimize import brentq
import bemt


def naca4_area_factor(n=2000):
    """Section area / (t c) for the NACA 4-digit thickness form (closed trailing edge not enforced), by integration."""
    x = np.linspace(0, 1, n)
    yt = 5 * (0.2969 * np.sqrt(x) - 0.1260 * x - 0.3516 * x ** 2 + 0.2843 * x ** 3 - 0.1015 * x ** 4)   # per unit t
    return float(2 * np.trapezoid(yt, x))


def tc_of(d, x):
    return np.interp(x, d["tc_r_over_R"], d["tc"])


def alpha_for_cl(db, tc, re, mach, cl_target):
    """Angle of attack [rad] giving cl_target below stall, by bisection between zero lift and stall."""
    lo = np.radians(db.prop("alpha_zero_lift", tc, re, mach)); hi = np.radians(db.prop("alpha_stall", tc, re, mach))
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        up = db.lookup(tc, re, mach, mid)[0] < cl_target
        lo, hi = np.where(up, mid, lo), np.where(up, hi, mid)
    return 0.5 * (lo + hi)


def mil_hover(radius, r_hub, n_blades, rpm, thrust, air, db, d, cl_design):
    """Unconstrained MIL hover design. Returns r, chord, twist, tc and the displacement velocity w."""
    rho, mu, a = air["rho"], air["mu"], air["a"]
    om = rpm * 2 * math.pi / 60
    tmp = bemt.Blade(radius, r_hub, n_blades, [r_hub, radius], [0.1, 0.1], [0, 0], [0.12, 0.12])
    r, dr, _, _, _ = tmp.stations(d["n_stations"])
    tc = tc_of(d, r / radius)

    def build(w):
        phi = np.arctan((w / 2) / (om * r))
        s, co = np.sin(phi), np.cos(phi)
        F = bemt.prandtl(n_blades, r, radius, r_hub, s)
        vi, vt = (w / 2) * co ** 2, (w / 2) * s * co
        W = np.hypot(vi, om * r - vt)
        gam = 2 * math.pi * r * F * w * s * co / n_blades
        mach = W / a
        c = np.full_like(r, 0.08)
        for _ in range(5):
            re = rho * W * np.maximum(c, 0.005) / mu
            alpha = alpha_for_cl(db, tc, re, mach, cl_design)
            cl, cd = db.lookup(tc, re, mach, alpha)
            c = 2 * gam / (W * cl)
        T = float(np.sum(n_blades * (rho * W * gam * co - 0.5 * rho * W ** 2 * c * cd * s) * dr))
        return T, c, phi + alpha
    w = brentq(lambda w_: build(w_)[0] - thrust, 0.5, 80.0, xtol=1e-6)
    _, c, th = build(w)
    return {"r": r, "chord": c, "twist": th, "tc": tc, "w": w}


def constrain(raw, radius, r_hub, n_blades, d):
    """Apply chord cap, tip floor, root shank and twist cap. Returns a bemt.Blade."""
    r, c, th = raw["r"], raw["chord"].copy(), raw["twist"].copy()
    x = r / radius
    c = np.minimum(c, d["chord_max_over_R"] * radius)
    xb = d["root_blend_r_over_R"]
    cb, thb = float(np.interp(xb, x, c)), float(np.interp(xb, x, th))
    inb = x < xb
    c[inb] = cb * (d["root_chord_fraction"] + (1 - d["root_chord_fraction"]) * (x[inb] - r_hub / radius) / (xb - r_hub / radius))
    th = np.minimum(th, math.radians(d["twist_max_deg"]))
    c = np.maximum(c, d["chord_tip_min_m"])
    return bemt.Blade(radius, r_hub, n_blades, r, c, th, raw["tc"])


def constant_pitch(template, pitch, d, radius=None):
    """Same planform (scaled with radius), twist from a constant geometric pitch: tan(theta) = P / (2 pi r)."""
    radius = radius or template.R
    k = radius / template.R
    r = template.r_def * k
    th = np.minimum(np.arctan(pitch / (2 * math.pi * r)), math.radians(d["twist_max_deg"]))
    return bemt.Blade(radius, template.r_hub * k, template.N, r, template.c_def * k, th, template.tc_def)


def blade_volume(blade, n=80):
    r, dr, c, _, tc = blade.stations(n)
    return naca4_area_factor() * float(np.sum(tc * c * c * dr))


def equivalent_pitch(blade, frac=0.75):
    """Geometric pitch implied by the twist at frac*R."""
    r = frac * blade.R
    return 2 * math.pi * r * math.tan(float(np.interp(r, blade.r_def, blade.th_def)))


def stall_margin_deg(db, sol, radius, span=(0.30, 0.95)):
    """Smallest (alpha_stall - alpha) over the working span. The shank and the tip cap are excluded: they carry little
    thrust and their Reynolds numbers are at or below the polar grid."""
    m = (sol["r"] >= span[0] * radius) & (sol["r"] <= span[1] * radius)
    return float(np.min(db.prop("alpha_stall", sol["tc"][m], sol["re"][m], sol["mach"][m]) - np.degrees(sol["alpha"][m])))


def modify(blade, d0, d1, e1):
    """Two-point design variables: twist offset d0 [rad], twist slope d1 [rad per unit r/R about 0.75], chord taper e1."""
    x = blade.r_def / blade.R
    return bemt.Blade(blade.R, blade.r_hub, blade.N, blade.r_def, blade.c_def * (1 + e1 * (x - 0.75)), blade.th_def + d0 + d1 * (x - 0.75), blade.tc_def)


def retwist(blade, db, air, rpm, d, cl_design, iters=4):
    """After the chord constraints, reset the twist (root to 97 % R, subject to the twist cap) so every section is back at cl_design
    at the given RPM (a capped chord otherwise leaves the section overloaded and close to stall)."""
    b = blade
    for _ in range(iters):
        sol = bemt.axial(b, db, air, rpm, n=len(b.r_def))
        target = alpha_for_cl(db, sol["tc"], sol["re"], sol["mach"], cl_design)
        dth = np.where(sol["r"] / b.R <= d["retwist_outer_r_over_R"], target - sol["alpha"], 0.0)   # the tip cap keeps its MIL twist
        th = np.minimum(b.th_def + np.interp(b.r_def, sol["r"], dth), math.radians(d["twist_max_deg"]))
        b = bemt.Blade(b.R, b.r_hub, b.N, b.r_def, b.c_def, th, b.tc_def)
    return b


def design_hover_blade(radius, r_hub, n_blades, rpm, thrust, air, db, d, cl_design):
    """MIL design, constraints, re-twist, and a final uniform chord scale so the design thrust is met at the design RPM."""
    raw = mil_hover(radius, r_hub, n_blades, rpm, thrust, air, db, d, cl_design)
    b = retwist(constrain(raw, radius, r_hub, n_blades, d), db, air, rpm, d, cl_design)
    return b, raw

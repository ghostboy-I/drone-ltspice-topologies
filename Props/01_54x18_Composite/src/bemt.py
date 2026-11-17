"""Blade-element momentum theory (BEMT) for a fixed-pitch rotor: axial flow (hover, climb) and edgewise forward flight.

AXIAL FLOW. Each annulus r..r+dr is treated on its own. Unknown: the inflow angle phi between the resultant velocity W
and the disk plane. With induced axial velocity vi and induced swirl vt at the disk:
    W sin(phi) = V + vi,        W cos(phi) = Omega r - vt,        alpha = theta - phi
Blade element (N blades, chord c, section cl, cd at alpha):
    dT = 0.5 rho W^2 N c cn dr,   cn = cl cos(phi) - cd sin(phi)
    dQ = 0.5 rho W^2 N c ct r dr, ct = cl sin(phi) + cd cos(phi)
Momentum, with Prandtl's loss factor F for a finite number of blades:
    dT = 4 pi r rho F (V + vi) vi dr,   dQ = 4 pi r^2 rho F (V + vi) vt dr
Equating them with sigma' = N c / (2 pi r) and k = sigma' / (4 F):
    vi = k W cn / sin(phi),   vt = k W ct / sin(phi)
and eliminating W gives one equation in phi that stays well behaved in hover (V = 0):
    R(phi) = V (sin phi cos phi + k ct) - Omega r (sin phi |sin phi| - k cn) = 0
Prandtl:  F = F_tip F_hub,  F_tip = (2/pi) acos(exp(-N (R - r) / (2 r |sin phi|))),  hub likewise.
The root is bracketed and found by bisection on all stations at once.
Limits: annuli are independent (no radial flow), wake contraction is ignored, polars are 2-D, and the Reynolds and Mach
numbers for the polar lookup use sqrt((Omega r)^2 + V^2) (induced velocities change it by well under 1 %).

EDGEWISE FLIGHT. Blade elements are integrated over radius and azimuth with a prescribed inflow:
    U_T = Omega r + V cos(a_s) sin(psi),   U_P = V sin(a_s) + lambda_i(r, psi) Omega R,   psi = 0 downstream
    lambda_i = lambda_0 (1 + kx x cos(psi) + ky x sin(psi))      (Drees linear inflow, x = r/R)
lambda_0 = kappa * (Glauert momentum value), iterated until it is consistent with the integrated thrust. kappa is an
empirical induced-power factor: a prescribed momentum inflow is the ideal minimum, so kappa > 1 restores the losses
from non-uniform loading. Only the longitudinal Drees gradient kx is used. The lateral gradient ky = -2 mu assumes a
roll-trimmed (flapping or cyclic) rotor; on a rigid fixed-pitch prop, which carries more lift on the advancing side,
it would pair low inflow with high lift and under-predict power, so it is switched off by default.
Tip loss is applied as a Prandtl factor on lift using the mean inflow. Limits: rigid blade (no flapping), no
radial-flow or dynamic-stall effects, no wake distortion, no rotor-rotor interference. It is an azimuthally resolved
first estimate, to be checked by CFD in Phase 4.
"""
import math
import numpy as np
import momentum as mt


class Blade:
    def __init__(self, radius, r_hub, n_blades, r, chord, twist, tc):
        """r, chord, twist [rad, chord line above the disk plane], tc: arrays at the definition stations."""
        self.R, self.r_hub, self.N = radius, r_hub, n_blades
        self.r_def, self.c_def, self.th_def, self.tc_def = map(lambda a: np.asarray(a, float), (r, chord, twist, tc))

    def stations(self, n=40):
        beta = np.linspace(0.0, math.pi, n + 1)
        edges = self.r_hub + (self.R - self.r_hub) * (1 - np.cos(beta)) / 2        # cosine spacing: fine at root and tip
        r = 0.5 * (edges[1:] + edges[:-1])
        return r, np.diff(edges), np.interp(r, self.r_def, self.c_def), np.interp(r, self.r_def, self.th_def), np.interp(r, self.r_def, self.tc_def)

    def solidity(self):
        r, dr, c, _, _ = self.stations(80)
        return self.N * float(np.sum(c * dr)) / (math.pi * self.R ** 2)       # thrust-unweighted: blade area / disk area

    def with_changes(self, twist_add=0.0, chord_scale=1.0):
        return Blade(self.R, self.r_hub, self.N, self.r_def, self.c_def * chord_scale, self.th_def + twist_add, self.tc_def)


def prandtl(N, r, R, r_hub, sphi, tip_loss=True, hub_loss=True):
    s = np.maximum(np.abs(sphi), 1e-6)
    F = np.ones_like(r)
    if tip_loss:
        F = F * (2 / math.pi) * np.arccos(np.clip(np.exp(-N * (R - r) / (2 * r * s)), 0, 1))
    if hub_loss and r_hub > 0:
        F = F * (2 / math.pi) * np.arccos(np.clip(np.exp(-N * (r - r_hub) / (2 * r_hub * s)), 0, 1))
    return np.maximum(F, 1e-4)


def axial(blade, polar, air, rpm, v=0.0, n=40, tip_loss=True, hub_loss=True):
    """Hover (v = 0) or axial climb. air = dict(rho, mu, a). Returns totals, coefficients and spanwise arrays."""
    rho, mu, a = air["rho"], air["mu"], air["a"]
    om = rpm * 2 * math.pi / 60
    r, dr, c, th, tc = blade.stations(n)
    N, R = blade.N, blade.R
    w_ref = np.hypot(om * r, v)
    re, mach = rho * w_ref * c / mu, w_ref / a
    sig = N * c / (2 * math.pi * r)

    def resid(phi):
        s, co = np.sin(phi), np.cos(phi)
        cl, cd = polar.lookup(tc, re, mach, th - phi)
        k = sig / (4 * prandtl(N, r, R, blade.r_hub, s, tip_loss, hub_loss))
        return v * (s * co + k * (cl * s + cd * co)) - om * r * (s * np.abs(s) - k * (cl * co - cd * s))

    eps = 1e-4
    pos = resid(np.full_like(r, eps)) > 0                   # lifting stations have their root in (0, pi/2)
    lo = np.where(pos, eps, -math.pi / 2 + eps)
    hi = np.where(pos, math.pi / 2 - eps, -eps)
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        up = resid(mid) > 0
        lo, hi = np.where(up, mid, lo), np.where(up, hi, mid)
    phi = 0.5 * (lo + hi)
    s, co = np.sin(phi), np.cos(phi)
    alpha = th - phi
    cl, cd = polar.lookup(tc, re, mach, alpha)
    F = prandtl(N, r, R, blade.r_hub, s, tip_loss, hub_loss)
    k = sig / (4 * F)
    cn, ct = cl * co - cd * s, cl * s + cd * co
    W = om * r / (co + k * ct / np.maximum(np.abs(s), 1e-9))
    dT = 0.5 * rho * W ** 2 * N * c * cn * dr
    dQ = 0.5 * rho * W ** 2 * N * c * ct * r * dr
    vi, vt = W * s - v, om * r - W * co
    T, Q = float(dT.sum()), float(dQ.sum())
    P, area, nrev, D = Q * om, math.pi * R * R, rpm / 60, 2 * R
    out = {"rpm": rpm, "v": v, "T": T, "Q": Q, "P": P, "omega": om,
           "CT": T / (rho * nrev ** 2 * D ** 4), "CQ": Q / (rho * nrev ** 2 * D ** 5), "CP": P / (rho * nrev ** 3 * D ** 5),
           "CT_h": T / (rho * area * (om * R) ** 2), "tip_mach": om * R / a,
           "FoM": (T ** 1.5 / math.sqrt(2 * rho * area) / P) if (T > 0 and P > 0) else float("nan"),
           "eta": T * v / P if P > 0 else float("nan"),
           "momentum_T": float(np.sum(4 * math.pi * r * rho * F * (v + vi) * vi * dr)),
           "r": r, "dr": dr, "chord": c, "twist": th, "tc": tc, "phi": phi, "alpha": alpha, "cl": cl, "cd": cd, "W": W,
           "re": rho * W * c / mu, "mach": W / a, "F": F, "vi": vi, "vt": vt, "dT_dr": dT / dr, "dQ_dr": dQ / dr,
           "n_negative_stations": int((~pos).sum())}
    return out


def trim_rpm(fn, thrust, lo=300.0, hi=6000.0):
    """Find the RPM at which fn(rpm)['T'] equals thrust (thrust rises monotonically with RPM for a fixed-pitch rotor)."""
    from scipy.optimize import brentq
    f = lambda rpm: fn(rpm)["T"] - thrust
    if f(hi) < 0:
        raise ValueError("thrust not reachable below the RPM ceiling")
    return fn(brentq(f, lo, hi, xtol=0.05))


def hover_at_thrust(blade, polar, air, thrust, **kw):
    return trim_rpm(lambda rpm: axial(blade, polar, air, rpm, 0.0, **kw), thrust)


def edgewise(blade, polar, air, rpm, v, alpha_shaft, n=30, n_psi=36, inflow="drees", tip_loss=True, max_iter=80, kappa=1.0, lateral=False):
    """Forward flight with the disk tilted nose-down by alpha_shaft [rad]. Returns mean loads, hub forces and moments,
    and the per-revolution harmonics of one blade's thrust and root flap moment."""
    rho, mu, a = air["rho"], air["mu"], air["a"]
    om = rpm * 2 * math.pi / 60
    r, dr, c, th, tc = blade.stations(n)
    N, R = blade.N, blade.R
    area, vt_tip = math.pi * R * R, om * R
    psi = np.arange(n_psi) * 2 * math.pi / n_psi
    rr, pp = np.meshgrid(r, psi)                              # shape (n_psi, n)
    x = rr / R
    mu_adv, lam_c = v * math.cos(alpha_shaft) / vt_tip, v * math.sin(alpha_shaft) / vt_tip
    UT = om * rr + v * math.cos(alpha_shaft) * np.sin(pp)
    lam0 = mt.hover_vi(max(blade.solidity() * 0.6 / 6 * rho * area * vt_tip ** 2, 1.0), rho, area) / vt_tip   # first guess
    T = 0.0
    for it in range(max_iter):
        if inflow == "drees" and mu_adv > 1e-6:
            chi = math.atan2(mu_adv, lam_c + lam0)
            kx, ky = (4.0 / 3.0) * (1 - math.cos(chi) - 1.8 * mu_adv ** 2) / math.sin(chi), (-2.0 * mu_adv if lateral else 0.0)
        else:
            kx = ky = 0.0
        lam_i = lam0 * (1 + kx * x * np.cos(pp) + ky * x * np.sin(pp))
        UP = v * math.sin(alpha_shaft) + lam_i * vt_tip
        U = np.hypot(UT, UP)
        phi = np.arctan2(UP, UT)
        cl, cd = polar.lookup(tc[None, :], rho * U * c[None, :] / mu, U / a, th[None, :] - phi)
        if tip_loss:
            F = (2 / math.pi) * np.arccos(np.clip(np.exp(-N * (1 - x) / (2 * max(lam_c + lam0, 1e-4))), 0, 1))
        else:
            F = 1.0
        q = 0.5 * rho * U ** 2 * c[None, :] * dr[None, :]
        dFz = q * (cl * F * np.cos(phi) - cd * np.sin(phi))
        dFx = q * (cl * F * np.sin(phi) + cd * np.cos(phi))
        T_new = N * float(dFz.sum(axis=1).mean())
        lam_new = kappa * (mt.glauert_vi(max(T_new, 1e-3), rho, area, v, alpha_shaft) if v > 1e-6 else mt.hover_vi(max(T_new, 1e-3), rho, area)) / vt_tip
        done = abs(T_new - T) <= 1e-6 * max(abs(T_new), 1.0) and abs(lam_new - lam0) < 1e-8
        T, lam0 = T_new, 0.5 * lam0 + 0.5 * lam_new
        if done:
            break
    Q = N * float((dFx * rr).sum(axis=1).mean())
    blade_T = dFz.sum(axis=1)                                   # one blade's thrust vs azimuth
    blade_M = (dFz * (rr - blade.r_hub)).sum(axis=1)            # one blade's root flap moment vs azimuth
    harm = lambda y: [float(2 * abs(np.fft.rfft(y)[k]) / len(y)) for k in (1, 2)]
    nrev, D = rpm / 60, 2 * R
    alpha_sec = th[None, :] - phi
    return {"rpm": rpm, "v": v, "alpha_shaft": alpha_shaft, "T": T, "Q": Q, "P": Q * om, "mu": mu_adv, "lam0": lam0, "iterations": it + 1,
            "converged": bool(done),
            "H": N * float((dFx * np.sin(pp)).sum(axis=1).mean()), "Y": -N * float((dFx * np.cos(pp)).sum(axis=1).mean()),
            "M_roll": N * float((dFz * rr * np.sin(pp)).sum(axis=1).mean()), "M_pitch": -N * float((dFz * rr * np.cos(pp)).sum(axis=1).mean()),
            "CT": T / (rho * nrev ** 2 * D ** 4), "CP": Q * om / (rho * nrev ** 3 * D ** 5), "CT_h": T / (rho * area * vt_tip ** 2),
            "blade_T_mean": float(blade_T.mean()), "blade_T_1P": harm(blade_T)[0], "blade_T_2P": harm(blade_T)[1],
            "blade_M_mean": float(blade_M.mean()), "blade_M_1P": harm(blade_M)[0], "blade_M_2P": harm(blade_M)[1],
            "tip_mach_adv": (vt_tip + v * math.cos(alpha_shaft)) / a, "alpha_max_deg": float(np.degrees(alpha_sec[:, r > 0.3 * R].max())),
            "psi": psi, "r": r, "alpha": alpha_sec, "dFz": dFz}


def edgewise_at_thrust(blade, polar, air, thrust, v, alpha_shaft, **kw):
    return trim_rpm(lambda rpm: edgewise(blade, polar, air, rpm, v, alpha_shaft, **kw), thrust)

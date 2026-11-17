"""Momentum (actuator-disk) theory and first-order rotor sizing.

Hover:      T = 2 rho A vi^2            ->  vi = sqrt(T / (2 rho A)),  P_ideal = T vi = T^1.5 / sqrt(2 rho A)
Axial climb at Vc:  T = 2 rho A (Vc + vi) vi   ->  vi = -Vc/2 + sqrt((Vc/2)^2 + vh^2)
Forward flight (Glauert):  T = 2 rho A vi sqrt((V cos a)^2 + (V sin a + vi)^2),  a = disk tilt into the wind
Figure of merit:  FoM = P_ideal / P_actual

Coefficient conventions (both are used in the literature; do not mix them):
    propeller:   T = CT rho n^2 D^4,  Q = CQ rho n^2 D^5,  P = CP rho n^3 D^5,   n in rev/s,  CP = 2 pi CQ
    helicopter:  T = CT_h rho A (Omega R)^2,  P = CP_h rho A (Omega R)^3
    CT = (pi^3/4) CT_h,   CP = (pi^4/4) CP_h

Blade-element estimate (uniform inflow, linear twist, small angles; Leishman, Principles of Helicopter
Aerodynamics, ch. 3):
    CT_h = sigma * CLbar / 6                     (mean lift coefficient CLbar)
    CT_h = (sigma a / 2) (theta75/3 - lambda/2), lambda = sqrt(CT_h / 2)
    CP_h = kappa CT_h^1.5 / sqrt(2) + sigma cd0 / 8
"""
import math


def disk_area(d):
    return math.pi * d * d / 4.0


def hover_vi(thrust, rho, area):
    return math.sqrt(thrust / (2.0 * rho * area))


def ideal_hover_power(thrust, rho, area):
    return thrust ** 1.5 / math.sqrt(2.0 * rho * area)


def climb_vi(thrust, rho, area, vc):
    vh = hover_vi(thrust, rho, area)
    return -vc / 2.0 + math.sqrt((vc / 2.0) ** 2 + vh * vh)


def glauert_vi(thrust, rho, area, v, alpha):
    """Induced velocity in forward flight. alpha = disk tilt [rad], positive nose-down (flow through the disk)."""
    vh2 = thrust / (2.0 * rho * area)
    vx, vz = v * math.cos(alpha), v * math.sin(alpha)
    f = lambda vi: vi - vh2 / math.sqrt(vx * vx + (vz + vi) ** 2)
    lo, hi = 0.0, 2.0 * math.sqrt(vh2) + abs(vz)
    if f(lo) >= 0.0:
        raise ValueError("no positive root (descending flight outside momentum theory)")
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if f(mid) < 0.0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


# ---- coefficient conventions ------------------------------------------------------------------------------
def ct_heli_to_prop(ct_h): return ct_h * math.pi ** 3 / 4.0
def ct_prop_to_heli(ct): return ct * 4.0 / math.pi ** 3
def cp_heli_to_prop(cp_h): return cp_h * math.pi ** 4 / 4.0
def cq_prop_from_cp(cp): return cp / (2.0 * math.pi)


def ct_heli(thrust, rho, area, vtip):
    return thrust / (rho * area * vtip * vtip)


def rpm_from_vtip(vtip, d):
    return vtip / (math.pi * d) * 60.0


def vtip_from_rpm(rpm, d):
    return math.pi * d * rpm / 60.0


def rpm_for_thrust(thrust, rho, ct_prop, d):
    """Fixed-pitch static prop: CT is constant, so n = sqrt(T / (CT rho D^4))."""
    return 60.0 * math.sqrt(thrust / (ct_prop * rho * d ** 4))


# ---- blade-element first-order estimates --------------------------------------------------------------------
def solidity_for_blade_loading(ct_h, mean_cl):
    return 6.0 * ct_h / mean_cl


def mean_chord(sigma, n_blades, radius):
    """sigma = N c / (pi R) for a constant-chord-equivalent blade."""
    return sigma * math.pi * radius / n_blades


def cp_heli_model(ct_h, sigma, kappa, cd0):
    return kappa * ct_h ** 1.5 / math.sqrt(2.0) + sigma * cd0 / 8.0


def fom_model(ct_h, sigma, kappa, cd0):
    return (ct_h ** 1.5 / math.sqrt(2.0)) / cp_heli_model(ct_h, sigma, kappa, cd0)


def collective_for_ct(ct_h, sigma, a):
    """Pitch at 75 % R (from the zero-lift line) that gives ct_h in hover."""
    return 3.0 * (2.0 * ct_h / (sigma * a) + math.sqrt(ct_h / 2.0) / 2.0)


def ct_for_collective(theta75, sigma, a):
    """Inverse of collective_for_ct: with x = sqrt(CT/2), 2 x^2 + (k/2) x - k theta/3 = 0, k = sigma a / 2."""
    k = sigma * a / 2.0
    x = (-k / 2.0 + math.sqrt(k * k / 4.0 + 8.0 * k * theta75 / 3.0)) / 4.0
    return 2.0 * x * x


def geometric_pitch_angle(pitch, radius, frac=0.75):
    """Helix angle of a constant-pitch blade at frac*R: tan(theta) = pitch / (2 pi r)."""
    return math.atan(pitch / (2.0 * math.pi * frac * radius))

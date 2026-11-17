"""Atmosphere model: ISA pressure at a pressure altitude, with an arbitrary outside-air temperature.

Equations (troposphere, h < 11 km):
    T_isa(h) = T0 - L h                       T0 = 288.15 K, L = 6.5 K/km
    p(h)     = p0 (T_isa/T0)^(g0 / (L R))     hydrostatic balance + ideal gas
    rho      = p / (R T)                      T = actual outside-air temperature, not T_isa
    a        = sqrt(gamma R T)
    mu       = Sutherland's law
Humid air (sensitivity only): rho = (p - pv)/(Rd T) + pv/(Rv T), pv = RH * p_sat(T) (Magnus formula).

Assumption: the "1000 m" design case is a pressure altitude, so pressure comes from the ISA column and the
temperature is imposed on top of it. That is how hot-day performance is normally quoted.
"""
import math

R_AIR = 287.05287      # J/(kg K), dry air
R_VAPOR = 461.495      # J/(kg K), water vapor
GAMMA = 1.4
G0 = 9.80665
P0 = 101325.0
T0 = 288.15
LAPSE = 0.0065


def isa_pressure(h_m):
    if not -1000.0 <= h_m <= 11000.0:
        raise ValueError("troposphere model only")
    return P0 * ((T0 - LAPSE * h_m) / T0) ** (G0 / (LAPSE * R_AIR))


def sutherland_viscosity(t_k):
    return 1.716e-5 * (t_k / 273.15) ** 1.5 * (273.15 + 110.4) / (t_k + 110.4)


def saturation_pressure(temp_c):
    """Magnus formula over water, Pa."""
    return 610.94 * math.exp(17.625 * temp_c / (temp_c + 243.04))


def state(temp_c, alt_m=0.0, rh=0.0):
    """Air state at outside-air temperature temp_c [C], pressure altitude alt_m [m], relative humidity rh [0-1]."""
    t = temp_c + 273.15
    p = isa_pressure(alt_m)
    pv = rh * saturation_pressure(temp_c)
    rho = (p - pv) / (R_AIR * t) + pv / (R_VAPOR * t)
    mu = sutherland_viscosity(t)
    return {"temp_c": temp_c, "alt_m": alt_m, "rh": rh, "T": t, "p": p, "rho": rho, "mu": mu,
            "nu": mu / rho, "a": math.sqrt(GAMMA * R_AIR * t)}

"""First-pass numbers for the section 3 conflicts (balance, misalignment, flex, pitch sensitivity).
These are hand-calc level. The full treatments are Phase 5 (structures), 6 (thermal) and 7 (balance)."""
import math


def tip_speed(d, rpm):
    return math.pi * d * rpm / 60.0


def iso_permissible_unbalance(grade_mm_s, rpm, rotor_mass_kg):
    """ISO 21940-11: e_per = G / omega [mm], U_per = e_per * m. Returns (e_per in um, U_per in g mm)."""
    omega = 2.0 * math.pi * rpm / 60.0
    e_mm = grade_mm_s / omega
    return e_mm * 1000.0, e_mm * rotor_mass_kg * 1000.0


def unbalance_from_mass(mass_g, radius_mm):
    return mass_g * radius_mm          # g mm


def unbalance_force(u_gmm, rpm):
    """F = U omega^2, with U converted from g mm to kg m."""
    omega = 2.0 * math.pi * rpm / 60.0
    return u_gmm * 1e-6 * omega * omega


def offset_unbalance(rotor_mass_kg, offset_mm):
    return rotor_mass_kg * 1000.0 * offset_mm     # g mm


def required_ei(force, length, deflection):
    """Uniform cantilever, tip load: delta = F L^3 / (3 E I)."""
    return force * length ** 3 / (3.0 * deflection)


def tip_deflection(force, length, ei):
    return force * length ** 3 / (3.0 * ei)


def rect_thickness_for_ei(ei, e_mod, width):
    """Solid rectangle b x t: I = b t^3 / 12."""
    return (12.0 * ei / (e_mod * width)) ** (1.0 / 3.0)

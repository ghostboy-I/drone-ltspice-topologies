"""Blade mass from a sized structure instead of 'mass proportional to volume'.

Section model (per radius): two UD carbon spar caps of area A at +-h/2 (h = section thickness t less one cap thickness),
a +-45 carbon skin over the perimeter (~2.04 c for a 4-digit section), a foam core filling the section (area 0.685 t c),
and a fixed root fitting per blade. Inboard of insert_r_over_R (the Phase 3 root transition, where the section thickens
to 30 % t/c into the hub) a metal root insert carries the load: it is in root_fitting_kg and taken as rigid.

Stiffness requirement: the 50 N bench load at the tip deflects the blade no more than 1.2 mm (brief, Phase 1 A-flex).

MINIMUM-MASS SIZING (Lagrange multiplier). In segment i (length ds), the two caps of mass m_i = 2 rho A_i ds give
    EI_i = 2 E A_i (h_i / 2)^2 = E h_i^2 m_i / (4 rho ds)
The tip deflection under a tip load F, by the unit-load method (M = F (L - s), unit-load moment (L - s)):
    delta = sum F (L - s_i)^2 ds / EI_i = sum a_i / m_i,      a_i = 4 rho F (L - s_i)^2 ds^2 / (E h_i^2)
Minimise sum m_i subject to sum a_i / m_i = delta: d/dm_i [m_i + lam a_i / m_i] = 0 -> m_i = sqrt(lam a_i), so
    m_i = sqrt(a_i) (sum_j sqrt(a_j)) / delta,         total cap mass = (sum sqrt(a_i))^2 / delta
Material goes where it buys the most stiffness: near the root (large L - s) and in deep sections (large h). A minimum gauge
(two plies) applies; segments held at the gauge are fixed and the rest is redistributed. h depends on the cap thickness
itself, and a cap thicker than t/3 loses its own lever arm, so the caps widen (up to cap_width_max_c) before they thicken
past t/3. Both are iterated.
"""
import numpy as np

DEFAULTS = {"E_ud": 130e9, "rho_ud": 1550.0, "rho_skin": 1550.0, "t_skin": 0.0006, "rho_core": 60.0, "cap_width_c": 0.30,
            "cap_width_max_c": 0.60, "t_cap_min": 0.0005, "root_fitting_kg": 0.08, "F": 50.0, "delta": 0.0012,
            "perimeter_c": 2.04, "area_factor": 0.685, "insert_r_over_R": 0.18}


def size_caps(c, t, s, ds, L, k):
    E, rho, F, delta = k["E_ud"], k["rho_ud"], k["F"], k["delta"]
    tcap = np.full_like(c, k["t_cap_min"])
    m_max = 2 * rho * k["cap_width_max_c"] * c * (t / 3) * ds        # widest caps at t/3: the most a section can hold
    for _ in range(60):
        h = t - np.minimum(tcap, t / 3)
        a = 4 * rho * F * (L - s) ** 2 * ds ** 2 / (E * h * h)
        m_min = 2 * rho * k["t_cap_min"] * k["cap_width_c"] * c * ds
        lo_fix = np.zeros_like(c, bool); hi_fix = np.zeros_like(c, bool)
        for _ in range(2 * len(c)):                                # hold gauge-limited and full sections, redistribute the rest
            free = ~(lo_fix | hi_fix)
            d_left = delta - np.sum(a[lo_fix] / m_min[lo_fix]) - np.sum(a[hi_fix] / m_max[hi_fix])
            if d_left <= 0 or not free.any():
                m = np.where(lo_fix, m_min, m_max); break             # cannot meet the limit: every free section is full
            m = np.where(lo_fix, m_min, np.where(hi_fix, m_max, np.sqrt(a) * np.sum(np.sqrt(a[free])) / d_left))
            new_lo, new_hi = free & (m < m_min), free & (m > m_max)
            if not (new_lo.any() or new_hi.any()): break
            lo_fix |= new_lo; hi_fix |= new_hi
        A = m / (2 * rho * ds)
        b = np.clip(A / (t / 3), k["cap_width_c"] * c, k["cap_width_max_c"] * c)   # widen before thickening past t/3
        tcap_new = A / b
        if np.max(np.abs(tcap_new - tcap)) < 1e-9: break
        tcap = 0.5 * tcap + 0.5 * tcap_new
    return m, tcap, b


def blade_mass(r, chord, tc, r_hub, R, k=None, n=200):
    """r, chord, tc arrays (definition stations). Returns total mass and its parts, plus feasibility."""
    k = dict(DEFAULTS, **(k or {}))
    s_edges = np.linspace(r_hub, R, n + 1); rr = 0.5 * (s_edges[1:] + s_edges[:-1]); ds = np.diff(s_edges)
    c = np.interp(rr, r, chord); t = np.interp(rr, r, tc) * c
    L = R - r_hub; s = rr - r_hub
    comp = rr >= k["insert_r_over_R"] * R
    m, tcap, b = size_caps(c[comp], t[comp], s[comp], ds[comp], L, k)
    caps = float(m.sum())
    skin = float(np.sum((k["rho_skin"] * k["t_skin"] * k["perimeter_c"] * c * ds)[comp]))
    core = float(np.sum((k["rho_core"] * k["area_factor"] * t * c * ds)[comp]))
    EI = 2 * k["E_ud"] * tcap * b * (np.maximum(t[comp] - tcap, 1e-4) / 2) ** 2
    delta = float(np.sum(k["F"] * (L - s[comp]) ** 2 / EI * ds[comp]))
    fill = 2 * tcap / t[comp]
    return {"total_kg": caps + skin + core + k["root_fitting_kg"], "caps_kg": caps, "skin_kg": skin, "core_kg": core,
            "fitting_kg": k["root_fitting_kg"], "tip_deflection_mm": 1000 * delta, "max_cap_fill": float(fill.max()),
            "max_cap_width_c": float((b / c[comp]).max()),
            "feasible": bool(delta <= k["delta"] * 1.02 and fill.max() <= 0.70),
            "r": rr[comp].tolist(), "t_cap_mm": (1000 * tcap).tolist(), "cap_width_mm": (1000 * b).tolist()}

"""NACA 4-digit-modified sections, e.g. NACA 2412-65 (Abbott & von Doenhoff, 'Theory of Wing Sections', sec. 6.4;
coefficients as in Ladson et al., NASA TM-4741). Suffix '-IT': I = leading-edge radius index (6 = normal 4-digit radius),
T = chordwise position of maximum thickness in tenths.

Thickness for t = 0.20, scaled linearly by t/0.20:
  ahead of m:  y = a0 sqrt(x) + a1 x + a2 x^2 + a3 x^3
  behind m:    y = d0 + d1 (1-x) + d2 (1-x)^2 + d3 (1-x)^3
  d0 = 0.002 (trailing-edge half thickness), d1 = trailing-edge slope from the table below,
  d2 = (0.294 - 2 (1-m) d1)/(1-m)^2, d3 = (-0.196 + (1-m) d1)/(1-m)^3   -> y(m) = 0.1, y'(m) = 0 automatically;
  a0 = 0.296904 I/6 (leading-edge radius rho = 1.1019 (t I/6)^2); a1..a3 from y(m) = 0.1, y'(m) = 0 and matching y''(m).
Camber: the ordinary 4-digit mean line (max camber m_c at p_c).
"""
import math
import numpy as np

D1 = {0.2: 0.200, 0.3: 0.234, 0.4: 0.315, 0.5: 0.465, 0.6: 0.700}


def coeffs(I, m):
    d1 = D1[round(m, 1)]; d0 = 0.002; q = 1 - m
    d2 = (0.294 - 2 * q * d1) / q ** 2; d3 = (-0.196 + q * d1) / q ** 3
    a0 = 0.296904 * I / 6.0
    ypp = 2 * d2 + 6 * d3 * q                                         # y'' at m from the aft polynomial
    A = np.array([[m, m * m, m ** 3], [1, 2 * m, 3 * m * m], [0, 2, 6 * m]])
    rhs = np.array([0.1 - a0 * math.sqrt(m), -a0 / (2 * math.sqrt(m)), ypp + a0 / (4 * m ** 1.5)])
    a1, a2, a3 = np.linalg.solve(A, rhs)
    return (a0, a1, a2, a3), (d0, d1, d2, d3)


def thickness(x, t, I, m):
    (a0, a1, a2, a3), (d0, d1, d2, d3) = coeffs(I, m); x = np.asarray(x, float)
    fwd = a0 * np.sqrt(x) + a1 * x + a2 * x ** 2 + a3 * x ** 3
    aft = d0 + d1 * (1 - x) + d2 * (1 - x) ** 2 + d3 * (1 - x) ** 3
    return t / 0.2 * np.where(x <= m, fwd, aft)


def thickness_4digit(x, t):
    x = np.asarray(x, float)
    return 5 * t * (0.2969 * np.sqrt(x) - 0.1260 * x - 0.3516 * x ** 2 + 0.2843 * x ** 3 - 0.1015 * x ** 4)


def camber(x, mc, pc):
    x = np.asarray(x, float)
    if mc == 0: return np.zeros_like(x), np.zeros_like(x)
    yc = np.where(x < pc, mc / pc ** 2 * (2 * pc * x - x * x), mc / (1 - pc) ** 2 * (1 - 2 * pc + 2 * pc * x - x * x))
    dy = np.where(x < pc, 2 * mc / pc ** 2 * (pc - x), 2 * mc / (1 - pc) ** 2 * (pc - x))
    return yc, dy


def coords(name, n=161):
    """name like '2412-65' -> (N, 2) array, Selig order (upper TE -> LE -> lower TE)."""
    base, suf = name.split("-")
    mc, pc, t = int(base[0]) / 100, int(base[1]) / 10, int(base[2:]) / 100
    I, m = int(suf[0]), int(suf[1]) / 10
    b = np.linspace(0, math.pi, n); x = 0.5 * (1 - np.cos(b))
    yt = thickness(x, t, I, m); yc, dy = camber(x, mc, pc); th = np.arctan(dy)
    xu, yu = x - yt * np.sin(th), yc + yt * np.cos(th); xl, yl = x + yt * np.sin(th), yc - yt * np.cos(th)
    return np.vstack([np.column_stack([xu[::-1], yu[::-1]]), np.column_stack([xl[1:], yl[1:]])])

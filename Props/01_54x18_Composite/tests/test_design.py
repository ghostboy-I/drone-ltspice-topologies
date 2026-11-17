"""Airfoil database and design code. These need the XFOIL polar cache (results/polars); they are skipped if XFOIL
has never been run on this machine."""
import math, os
import numpy as np
import conftest  # noqa: F401
import airfoils, bemt, design_opt as do
from common import load_params

P = load_params()
HAVE = os.path.isdir(airfoils.POLAR_DIR) and len(os.listdir(airfoils.POLAR_DIR)) > 0
DB = airfoils.build_db(P)[0] if HAVE else None
AIR = {"rho": 1.1095, "mu": 1.9306e-5, "a": 357.57}
R, RH = 0.6858, 0.05


def test_naca4_area_factor():
    assert abs(do.naca4_area_factor() - 0.685) < 0.001          # textbook value for the 4-digit thickness form


def test_viterna_matches_stall_point_and_flat_plate():
    cl, cd = airfoils.viterna(np.array([12.0, 90.0]), 12.0, 1.4, 0.03, 1.2)
    assert math.isclose(cl[0], 1.4, rel_tol=1e-9) and math.isclose(cd[0], 0.03, rel_tol=1e-9)
    assert abs(cl[1]) < 1e-9 and math.isclose(cd[1], 1.2, rel_tol=1e-9)


def test_constant_pitch_twist():
    r = np.linspace(RH, R, 20)
    t = bemt.Blade(R, RH, 2, r, np.full_like(r, 0.1), np.zeros_like(r), np.full_like(r, 0.12))
    b = do.constant_pitch(t, 0.4572, P["design"])
    assert math.isclose(do.equivalent_pitch(b), 0.4572, rel_tol=2e-3)
    b60 = do.constant_pitch(t, 0.33, P["design"], radius=0.762)
    assert math.isclose(b60.c_def[0] / t.c_def[0], 0.762 / R, rel_tol=1e-12)


def test_database_reproduces_xfoil_point():
    if not HAVE: return
    import json
    rec = json.load(open(os.path.join(airfoils.POLAR_DIR, "naca4412_re1200000_m0.30.json")))
    pt = min(rec["points"], key=lambda q: abs(q[0] - 4.0))
    cl, cd = DB.lookup(0.12, 1.2e6, 0.30, math.radians(pt[0]))
    assert math.isclose(float(cl), pt[1], rel_tol=1e-6) and math.isclose(float(cd), pt[2], rel_tol=1e-6)


def test_polar_sanity():
    if not HAVE: return
    cl0, _ = DB.lookup(0.12, 1.2e6, 0.1, 0.0)
    assert 0.35 < float(cl0) < 0.60                               # 4 % camber: thin-airfoil theory gives cl(0) = 2 pi * 4.15 deg = 0.455
    cl90, cd90 = DB.lookup(0.12, 1.2e6, 0.1, math.pi / 2)
    assert abs(float(cl90)) < 0.05 and float(cd90) > 1.0
    assert 8 < float(DB.prop("alpha_stall", 0.12, 1.2e6, 0.3)) < 20


def test_mil_design_is_recovered_by_analysis():
    """Design and analysis are separate code paths: BEMT on the raw MIL blade must return the design thrust and cl."""
    if not HAVE: return
    d, thrust, rpm = P["design"], 415.0, 1900.0
    raw = do.mil_hover(R, RH, 2, rpm, thrust, AIR, DB, d, 1.0)
    b = bemt.Blade(R, RH, 2, raw["r"], raw["chord"], raw["twist"], raw["tc"])
    s = bemt.axial(b, DB, AIR, rpm)
    assert abs(s["T"] / thrust - 1) < 0.02
    mid = (s["r"] > 0.3 * R) & (s["r"] < 0.95 * R)
    assert np.max(np.abs(s["cl"][mid] - 1.0)) < 0.06
    assert np.std(s["vi"][mid] / np.cos(s["phi"][mid]) ** 2) / np.mean(s["vi"][mid]) < 0.03    # Betz: vi / cos^2(phi) = w/2 is constant


def test_retwist_restores_design_cl():
    if not HAVE: return
    d = P["design"]
    b, _ = do.design_hover_blade(R, RH, 2, 1750.0, 415.0, AIR, DB, d, 1.0)
    s = bemt.axial(b, DB, AIR, 1750.0)
    mid = (s["r"] > 0.3 * R) & (s["r"] < 0.95 * R)
    assert np.max(np.abs(s["cl"][mid] - 1.0)) < 0.03
    assert float(b.c_def.max()) <= d["chord_max_over_R"] * R + 1e-9

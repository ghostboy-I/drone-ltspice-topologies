"""BEMT against closed-form limits, using an idealised section (cl = a*alpha, constant cd) so the answers are known."""
import math
import numpy as np
import conftest  # noqa: F401
import bemt
from airfoils import AnalyticPolar

AIR = {"rho": 1.225, "mu": 1.789e-5, "a": 340.3}
R, RH, NB = 0.6858, 0.10, 2
SLOPE = 5.73


def ideal_twist_blade(theta_tip=math.radians(4.0), chord=0.05):
    r = np.linspace(RH, R, 200)
    return bemt.Blade(R, RH, NB, r, np.full_like(r, chord), theta_tip * R / r, np.full_like(r, 0.12)), theta_tip, NB * chord / (math.pi * R)


def test_hover_ideal_twist_matches_closed_form():
    # Leishman: ideal twist theta = theta_tip / x gives uniform inflow, lambda = (sigma a/16)(sqrt(1 + 32 theta_tip/(sigma a)) - 1), CT = 2 lambda^2
    b, tt, sigma = ideal_twist_blade()
    o = bemt.axial(b, AnalyticPolar(SLOPE), AIR, 2000.0, tip_loss=False, hub_loss=False, n=80)
    lam = sigma * SLOPE / 16 * (math.sqrt(1 + 32 * tt / (sigma * SLOPE)) - 1)
    ct_exact = 2 * lam * lam * (1 - (RH / R) ** 2)          # annulus area only
    assert abs(o["CT_h"] / ct_exact - 1) < 0.03
    outer = o["r"] > 0.4 * R
    assert np.std(o["vi"][outer]) / np.mean(o["vi"][outer]) < 0.03       # inflow is uniform


def test_no_drag_no_tip_loss_is_near_ideal():
    b, _, _ = ideal_twist_blade()
    o = bemt.axial(b, AnalyticPolar(SLOPE), AIR, 2000.0, tip_loss=False, hub_loss=False, n=80)
    area_ratio = 1 - (RH / R) ** 2
    fom_annulus = o["FoM"] / math.sqrt(area_ratio)          # FoM is referenced to the full disk; the annulus is smaller
    assert 0.95 < fom_annulus <= 1.0 + 1e-6


def test_blade_element_and_momentum_thrust_agree():
    b, _, _ = ideal_twist_blade()
    o = bemt.axial(b, AnalyticPolar(SLOPE, cd=0.01), AIR, 2200.0)
    assert math.isclose(o["T"], o["momentum_T"], rel_tol=1e-6)
    oc = bemt.axial(b, AnalyticPolar(SLOPE, cd=0.01), AIR, 2200.0, v=5.0)
    assert math.isclose(oc["T"], oc["momentum_T"], rel_tol=1e-6)


def test_tip_loss_and_drag_reduce_performance():
    b, _, _ = ideal_twist_blade()
    p = AnalyticPolar(SLOPE)
    full, lossy = bemt.axial(b, p, AIR, 2000.0, tip_loss=False, hub_loss=False), bemt.axial(b, p, AIR, 2000.0)
    assert lossy["T"] < full["T"]
    assert bemt.axial(b, AnalyticPolar(SLOPE, cd=0.02), AIR, 2000.0)["FoM"] < lossy["FoM"]


def test_affinity_laws_for_re_independent_section():
    b, _, _ = ideal_twist_blade()
    p = AnalyticPolar(SLOPE, cd=0.01)
    a, c = bemt.axial(b, p, AIR, 1500.0), bemt.axial(b, p, AIR, 3000.0)
    assert math.isclose(c["T"] / a["T"], 4.0, rel_tol=1e-6) and math.isclose(c["P"] / a["P"], 8.0, rel_tol=1e-6)
    thin = dict(AIR, rho=0.6125)
    assert math.isclose(bemt.axial(b, p, thin, 1500.0)["T"] / a["T"], 0.5, rel_tol=1e-6)


def test_axial_flight_below_froude_efficiency():
    r = np.linspace(RH, R, 100)
    b = bemt.Blade(R, RH, NB, r, np.full_like(r, 0.05), np.arctan(1.0 / (2 * math.pi * r)) + math.radians(3), np.full_like(r, 0.12))   # 1 m pitch
    v = 30.0
    o = bemt.axial(b, AnalyticPolar(SLOPE), AIR, 2400.0, v=v)
    assert o["T"] > 0
    eta_ideal = 2 / (1 + math.sqrt(1 + o["T"] / (0.5 * AIR["rho"] * math.pi * R * R * v * v)))
    assert 0.85 * eta_ideal < o["eta"] < eta_ideal


def test_trim_rpm_hits_thrust():
    b, _, _ = ideal_twist_blade()
    o = bemt.hover_at_thrust(b, AnalyticPolar(SLOPE, cd=0.01), AIR, 100.0)
    assert math.isclose(o["T"], 100.0, rel_tol=1e-4)


def test_edgewise_reduces_to_hover():
    b, _, _ = ideal_twist_blade()
    p = AnalyticPolar(SLOPE, cd=0.01)
    h = bemt.axial(b, p, AIR, 2000.0)
    e = bemt.edgewise(b, p, AIR, 2000.0, 1e-9, 0.0)
    assert e["converged"]
    assert abs(e["T"] / h["T"] - 1) < 0.05 and abs(e["P"] / h["P"] - 1) < 0.05
    assert abs(e["M_roll"]) < 1e-6 * h["T"] and abs(e["H"]) < 1e-6 * h["T"]


def test_edgewise_forward_flight_trends():
    b, _, _ = ideal_twist_blade()
    p = AnalyticPolar(SLOPE, cd=0.01)
    e0 = bemt.edgewise(b, p, AIR, 2000.0, 1e-9, 0.0)
    e = bemt.edgewise(b, p, AIR, 2000.0, 15.0, math.radians(4))
    assert e["converged"]
    assert e["T"] > e0["T"]                 # less induced inflow at the same RPM gives more thrust
    assert e["M_roll"] > 0                  # advancing side lifts more (rigid blade)
    assert e["H"] > 0                       # in-plane drag force points downstream
    assert e["blade_T_1P"] > e["blade_T_2P"] > 0

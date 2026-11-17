"""Momentum theory against its closed-form limits."""
import math
import conftest  # noqa: F401
import momentum as mt

RHO, A, T = 1.225, 1.5, 400.0


def close(a, b, rel=1e-9): return math.isclose(a, b, rel_tol=rel)


def test_hover_identities():
    vh = mt.hover_vi(T, RHO, A)
    assert close(2 * RHO * A * vh * vh, T)
    assert close(mt.ideal_hover_power(T, RHO, A), T * vh)


def test_glauert_limits():
    vh = mt.hover_vi(T, RHO, A)
    assert close(mt.glauert_vi(T, RHO, A, 1e-9, 0.0), vh, 1e-6)             # V -> 0 gives hover
    assert close(mt.glauert_vi(T, RHO, A, 200.0, 0.0), vh * vh / 200.0, 1e-3)  # high speed: vi -> vh^2 / V
    v = 15.0                                                                 # edgewise closed form: vi^4 + V^2 vi^2 - vh^4 = 0
    exact = math.sqrt((-v * v + math.sqrt(v ** 4 + 4 * vh ** 4)) / 2)
    assert close(mt.glauert_vi(T, RHO, A, v, 0.0), exact, 1e-9)


def test_glauert_axial_equals_climb_formula():
    assert close(mt.glauert_vi(T, RHO, A, 3.0, math.pi / 2), mt.climb_vi(T, RHO, A, 3.0), 1e-9)


def test_glauert_satisfies_momentum_equation():
    v, al = 12.0, 0.1
    vi = mt.glauert_vi(T, RHO, A, v, al)
    assert close(2 * RHO * A * vi * math.hypot(v * math.cos(al), v * math.sin(al) + vi), T, 1e-9)


def test_coefficient_conventions_round_trip():
    d, rpm, ct_h = 1.3716, 2500.0, 0.011
    area, vt = mt.disk_area(d), mt.vtip_from_rpm(rpm, d)
    thrust = ct_h * RHO * area * vt * vt
    n = rpm / 60
    assert close(mt.ct_heli_to_prop(ct_h) * RHO * n * n * d ** 4, thrust)
    assert close(mt.ct_prop_to_heli(mt.ct_heli_to_prop(ct_h)), ct_h)
    assert close(mt.rpm_for_thrust(thrust, RHO, mt.ct_heli_to_prop(ct_h), d), rpm)
    cp_h = 0.001
    assert close(mt.cp_heli_to_prop(cp_h) * RHO * n ** 3 * d ** 5, cp_h * RHO * area * vt ** 3)


def test_collective_inverse():
    th = mt.collective_for_ct(0.011, 0.11, 5.73)
    assert close(mt.ct_for_collective(th, 0.11, 5.73), 0.011, 1e-9)


def test_fom_model_limits():
    assert close(mt.fom_model(0.01, 0.1, 1.0, 0.0), 1.0)          # no losses -> ideal
    assert close(mt.fom_model(0.01, 0.1, 1.15, 0.0), 1 / 1.15)    # induced losses only
    assert close(mt.solidity_for_blade_loading(0.011, 0.6) * 0.6 / 6, 0.011)


def test_geometric_pitch():
    assert close(math.tan(mt.geometric_pitch_angle(0.4572, 0.6858)), 0.4572 / (2 * math.pi * 0.75 * 0.6858))

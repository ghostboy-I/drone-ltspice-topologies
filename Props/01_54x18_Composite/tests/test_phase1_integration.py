"""The Phase 1 driver must reproduce the brief's own hand numbers (section 2) from params.yaml."""
import math
import conftest  # noqa: F401
import phase1

O = phase1.run(write=False)


def within(a, b, pct): return abs(a / b - 1) * 100 <= pct


def test_brief_section2_numbers():
    v = O["vehicle"]
    assert within(v["weight_n"], 1246.0, 0.1)
    assert within(v["t_hover"], 415.0, 0.1)
    assert within(v["t_tw_required"], 623.0, 0.1) and within(v["t_tw_target"], 830.0, 0.1)
    assert within(v["disk_area"], 1.478, 0.1) and within(v["disk_loading"], 281.0, 0.1)
    assert within(O["brief_checks"]["p_ideal_isa"], 4400.0, 1.5)
    assert within(O["atmospheres"]["hot_sl"]["rho"], 1.110, 0.1)


def test_tip_mach_limit_respected_at_sizing_point():
    pts = {(q["atm"], q["tw"]): q for q in O["operating_points"]}
    assert math.isclose(pts[("hot_sl", 2.0)]["tip_mach"], 0.60, rel_tol=1e-9)
    assert not pts[("hot_high", 2.0)]["mach_ok"]


def test_fixed_pitch_scaling():
    pts = {(q["atm"], q["tw"]): q for q in O["operating_points"]}
    a, b = pts[("hot_sl", 1.0)], pts[("hot_sl", 2.0)]
    assert math.isclose(b["rpm"] / a["rpm"], math.sqrt(2), rel_tol=1e-9)        # T ~ n^2
    assert math.isclose(b["p_shaft"] / a["p_shaft"], 2 ** 1.5, rel_tol=1e-9)    # P ~ n^3
    assert math.isclose(b["torque"] / a["torque"], 2.0, rel_tol=1e-9)           # Q ~ n^2

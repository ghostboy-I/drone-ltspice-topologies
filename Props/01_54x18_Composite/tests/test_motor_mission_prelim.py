"""Motor matching, mission model and section 3 first-pass checks against closed forms."""
import math
import conftest  # noqa: F401
import momentum as mt
import motor_match as mm
import mission as ms
import prelim_checks as pc


def close(a, b, rel=1e-9): return math.isclose(a, b, rel_tol=rel)


def test_kt_kv_identity():
    # In SI units Kt [N m/A] equals Ke [V s/rad]; KV = 100 rpm/V -> Ke = 60/(2 pi 100)
    assert close(mm.kt_from_kv(100.0), 0.0954929658551372)
    assert close(mm.required_kv(3000.0, 100.0, 1.0), 30.0)
    assert close(mm.bus_current(9000.0, 0.9, 100.0), 100.0)
    assert close(mm.loaded_rpm(38, 96, mm.required_kv(2910, 96, 1.0) / 38), 2910.0)


def veh(fom=0.7):
    return ms.Vehicle(1245.5, 3, 1.4776, 1.1095, fom, 1.15, 151.7, 0.6, 0.905, 0.97, 150.0)


def test_hover_power_returns_assumed_fom():
    v = veh()
    ideal = 3 * mt.ideal_hover_power(v.t_hover, v.rho, v.area)
    assert close(ideal / v.hover_shaft(), 0.7, 1e-9)


def test_trim_force_balance():
    al, t, d = ms.trim(1000.0, 1.2, 15.0, 0.6)
    assert close(t * math.cos(al), 1000.0) and close(t * math.sin(al), d)
    assert close(d, 0.5 * 1.2 * 225 * 0.6)


def test_parasite_power_equals_drag_times_speed():
    c = veh().cruise(15.0)
    assert close(3 * c["parasite"], c["drag"] * 15.0, 1e-9)


def test_cruise_power_below_hover_at_design_speed():
    v = veh()
    assert v.cruise(15.0)["shaft_total"] < v.hover_shaft()


def test_mission_energy_adds_up_and_grows_with_range():
    m = dict(takeoff_hover_s=15, landing_hover_s=15, delivery_hover_s=120, cruise_alt_m=60, climb_rate_ms=2.5,
             descent_rate_ms=2.0, reserve_fraction=0.2)
    v = veh()
    e0, e1 = ms.mission_energy(v, m, 0.0, 15.0), ms.mission_energy(v, m, 18520.0, 15.0)
    assert e1["energy_wh"] > e0["energy_wh"]
    assert close(e1["energy_wh"], sum(s["energy_wh"] for s in e1["segments"]))
    assert close(e1["pack_wh"] * 0.8, e1["energy_wh"])
    cruise_wh = v.electrical(v.cruise(15.0)["shaft_total"]) * (18520.0 / 15.0) / 3600
    assert close(e1["energy_wh"] - e0["energy_wh"], cruise_wh, 1e-9)


def test_mass_budget_total():
    b = ms.mass_budget(3000.0, 300.0, 4.0, 1.0, 0.5, 2, 0.3, 3, 10.0, 2.0)
    assert close(b["battery"], 10.0) and close(b["total"], 10 + 12 + 3 + 3.9 + 10 + 2)


def test_brief_numbers():
    assert close(pc.required_ei(50.0, 0.6, 0.0012), 3000.0)                    # brief section 3.7
    assert close(pc.tip_speed(1.3716, 10000.0), 718.168, 1e-5)                 # brief section 3.2
    assert close(pc.tip_deflection(50.0, 0.6, 3000.0), 0.0012)


def test_iso_balance_definition():
    e_um, u = pc.iso_permissible_unbalance(6.3, 60 / (2 * math.pi) * 100.0, 2.0)   # omega = 100 rad/s
    assert close(e_um, 63.0) and close(u, 126.0)
    assert close(pc.unbalance_force(1e6, 60 / (2 * math.pi)), 1.0)                 # 1 kg m at 1 rad/s -> 1 N


def test_rect_section():
    t = pc.rect_thickness_for_ei(3000.0, 130e9, 0.1)
    assert close(130e9 * 0.1 * t ** 3 / 12, 3000.0)

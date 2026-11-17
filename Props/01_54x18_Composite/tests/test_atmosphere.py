"""Atmosphere against the ICAO standard atmosphere table values."""
import math
import conftest  # noqa: F401  (path setup; harmless under pytest, needed by run_tests.py)
import atmosphere as atm


def close(a, b, rel): return math.isclose(a, b, rel_tol=rel)


def test_isa_sea_level():
    s = atm.state(15.0, 0.0)
    assert close(s["rho"], 1.2250, 1e-4)
    assert close(s["a"], 340.294, 1e-5)
    assert close(s["mu"], 1.7894e-5, 1e-3)


def test_isa_pressure_table():
    assert close(atm.isa_pressure(1000.0), 89874.6, 1e-5)
    assert close(atm.isa_pressure(11000.0), 22632.0, 1e-4)


def test_density_scales_inverse_with_temperature():
    assert close(atm.state(45.0)["rho"] / atm.state(15.0)["rho"], 288.15 / 318.15, 1e-12)


def test_humid_air_is_lighter():
    assert atm.state(45.0, 0.0, 0.5)["rho"] < atm.state(45.0, 0.0, 0.0)["rho"]
    assert close(atm.saturation_pressure(100.0), 101325.0, 0.03)   # water boils at 1 atm


def test_out_of_range_altitude_raises():
    try:
        atm.isa_pressure(20000.0)
    except ValueError:
        return
    assert False

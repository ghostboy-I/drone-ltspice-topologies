"""Geometry helpers against known shapes (no gmsh needed)."""
import math
import numpy as np
import conftest  # noqa: F401
import geometry as geo
from common import load_params

P = load_params()


def cube():
    v = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0], [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]], float)
    f = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]
    return v[np.array(f)]


def ruled_wing(mirror):
    """Two sections joined by quads and closed with end caps: a small twisted wing lying along +x."""
    a = geo.section_points(P, 0.2, 0.10, math.radians(12), 0.12, mirror)
    b = geo.section_points(P, 0.4, 0.10, math.radians(12), 0.12, mirror)
    n, tris = len(a), []
    for i in range(n):
        j = (i + 1) % n
        tris += [[a[i], b[i], b[j]], [a[i], b[j], a[j]]]
    for sec, flip in ((a, False), (b, True)):
        c = sec.mean(axis=0)
        for i in range(n):
            j = (i + 1) % n
            tris.append([c, sec[i], sec[j]] if flip else [c, sec[j], sec[i]])
    return np.array(tris)


def test_naca4_shape():
    (xu, yu), (xl, yl) = geo.naca4(0.12, 0.04, 0.40, 201)
    camber = 0.5 * (yu + yl)
    assert abs(camber.max() - 0.04) < 5e-4 and abs(xu[np.argmax(camber)] - 0.40) < 0.02
    x = np.linspace(0.05, 0.95, 400)
    t = np.interp(x, xu, yu) - np.interp(x, xl, yl)
    assert abs(t.max() - 0.12) < 1.5e-3 and abs(x[np.argmax(t)] - 0.30) < 0.02
    assert 0 < yu[-1] - yl[-1] < 0.004                      # small blunt trailing edge


def test_mesh_stats_on_unit_cube():
    s = geo.mesh_stats(cube())
    assert s["edges_not_shared_by_two"] == 0 and s["edges_with_inconsistent_orientation"] == 0
    assert math.isclose(s["volume"], 1.0, rel_tol=1e-12)
    assert np.allclose(s["centroid"], [0.5, 0.5, 0.5])
    assert math.isclose(s["izz_unit_density"], 2.0 / 3.0, rel_tol=1e-12)      # integral of x^2 + y^2 over [0,1]^3
    assert math.isclose(s["surface_area"], 6.0, rel_tol=1e-12)


def test_open_mesh_is_detected():
    assert geo.mesh_stats(cube()[:-1])["edges_not_shared_by_two"] > 0


def test_slice_recovers_chord_twist_and_handedness():
    for mirror, sign in ((False, 1), (True, -1)):
        w = ruled_wing(mirror)
        assert geo.mesh_stats(w)["edges_not_shared_by_two"] == 0
        s = geo.slice_section(w, 0.3)
        assert abs(s["chord"] / 0.10 - 1) < 0.003
        assert abs(s["twist_deg"] - 12.0) < 0.3
        assert s["le_y_sign"] == sign and s["nose_up"] and s["camber_toward_plus_z"]


def test_mirror_is_a_reflection_not_a_rotation():
    a = geo.section_points(P, 0.3, 0.1, 0.2, 0.12, False)
    b = geo.section_points(P, 0.3, 0.1, 0.2, 0.12, True)
    assert np.allclose(a[:, [0, 2]], b[:, [0, 2]]) and np.allclose(a[:, 1], -b[:, 1])


def test_station_definition_limits():
    R = P["rotor"]["diameter_in"] * P["constants"]["inch_to_m"] / 2
    import os
    if not os.path.exists(os.path.join(geo.RESULTS, "blade_final.csv")): return
    st = geo.stations(P, R)
    assert np.all(np.diff(st["r"]) > 0) and math.isclose(st["r"][-1], R, rel_tol=1e-12)
    assert st["r"][0] < P["rotor"]["hub_radius_m"]                       # loft starts inside the hub
    assert np.all(st["chord"] > 0) and st["chord"].max() <= P["design"]["chord_max_over_R"] * R * 1.001

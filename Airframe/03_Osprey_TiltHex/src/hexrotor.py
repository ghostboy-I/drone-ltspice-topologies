"""The hex rotor (the decision matrix's winner), read from the Props program, plus the coaxial-pair model.

Rotor: Props exploration entry 46 (results/explore/e46_hex_noise_curve.json), the row picked by params rotors.motor and
rotors.cap: a 54 in, 2-blade blade designed for one-sixth of the weight, 24xx-family sections (its own polar set, built
by the Props airfoils.build_db with family "24"), on a T-Motor MN1123 KV53 with a 10 % torque reserve. Its hover rpm and
the motor's loaded speed limit are taken from that row; the hover point is re-solved here as a check.

The Phase 2 final blade (54x18, results/blade_final.csv, 44xx polars) is kept as the alternative for the TILTING rotors:
its higher pitch keeps pulling to ~33 m/s; the hex blade's zero-thrust speed at the motor limit is ~18 m/s.

Coaxial pair: Props config_study.coax_pair (vortex-cylinder upper wake on the lower disk, lower rotor's upstream
induction on the upper, BEMT on both, trimmed to equal torque). Interference factor
    kappa_int = (P_ind,upper + P_ind,lower) / (2 P_ind,isolated at T/2)
In forward flight the Props program brackets the pair between isolated rotors and the hover interference on the induced
part (config_study docstring); the trim here takes the pessimistic end: P_pair = 2 P_edge(T/2) + (kappa_int - 1) P_ind,
with P_ind = kappa T v_i from Glauert's equation, so the penalty fades as the wake is blown away.
"""
import json, math, os
import numpy as np
from tiltcfg import params, props_params, PROPS

_C = {}


def setup():
    """Blades, polar sets, air, motor numbers. Cached per process."""
    if _C: return _C
    import airfoils, bemt, atmosphere as atm
    p, pp = params(), props_params()
    rp = p["rotors"]
    rows = json.load(open(os.path.join(PROPS, "results", "explore", rp["source_entry"] + ".json")))["rows"]
    row = next(r for r in rows if r["motor"] == rp["motor"] and abs(r["cap"] - rp["cap"]) < 1e-9 and r["layout"] == "hex")
    R = pp["rotor"]["diameter_in"] * pp["constants"]["inch_to_m"] / 2
    d = row["blade"]
    hexb = bemt.Blade(R, pp["rotor"]["hub_radius_m"], 2, d["r"], d["chord"], np.radians(d["twist_deg"]), d["tc"])
    q = json.loads(json.dumps(pp)); q["airfoils"]["family"] = rp["section_family"]; q["airfoils"]["compare_sections"] = []
    db24 = airfoils.build_db(q, n_proc=1)[0]
    f = np.loadtxt(os.path.join(PROPS, "results", "blade_final.csv"), delimiter=",", comments="#", skiprows=2)
    b54 = bemt.Blade(R, pp["rotor"]["hub_radius_m"], pp["rotor"]["n_blades"], f[:, 0], f[:, 2], np.radians(f[:, 3]), f[:, 4])
    db44 = airfoils.build_db(pp, n_proc=1)[0]
    hot = pp["atmospheres"][pp["design_atmosphere"]]
    air = atm.state(hot["temp_c"], hot["alt_m"])
    _C.update(p=p, pp=pp, row=row, R=R, A=math.pi * R * R, air=air, kappa=pp["rotor"]["kappa"],
              blades={"hex": (hexb, db24), "54x18": (b54, db44)},
              rpm_max=row["rpm_max"], rpm_hover_row=row["rpm_hover"], motor_kg=row["motor_kg"], Q_max=row["Q_max"],
              solidity=row["solidity"])
    return _C


def blade(name):
    return setup()["blades"][name]


def hover(name, thrust):
    import bemt
    c = setup(); b, db = blade(name)
    return bemt.hover_at_thrust(b, db, c["air"], thrust)


def thrust_cap(name):
    """Static thrust ceiling (the LC2 'rotor at its ceiling'): the motor's loaded speed limit OR its torque limit
    (Props entry 46: 0.90 x test torque), whichever comes first. A high-pitch blade hits the torque limit first."""
    import bemt
    from scipy.optimize import brentq
    c = setup(); b, db = blade(name)
    a = bemt.axial(b, db, c["air"], c["rpm_max"], 0.0)
    if a["Q"] <= c["Q_max"]:
        a["limit"] = "rpm"; return a
    rpm = brentq(lambda r: bemt.axial(b, db, c["air"], r, 0.0)["Q"] - c["Q_max"], 300.0, c["rpm_max"], xtol=0.05)
    a = bemt.axial(b, db, c["air"], rpm, 0.0); a["limit"] = "torque"
    return a


def coax(name, thrust, h=None):
    """Hover coaxial pair carrying `thrust` (both rotors the same blade), equal-torque trim."""
    import config_study as cs, bemt
    c = setup(); b, db = blade(name)
    h = c["p"]["rotors"]["coax_spacing_over_D"] * 2 * c["R"] if h is None else h
    pr = cs.coax_pair(b, db, c["air"], thrust, h)
    iso = bemt.hover_at_thrust(b, db, c["air"], thrust / 2)
    pi_iso = cs.induced(iso)
    pr["kappa_int"] = pr["P_induced"] / (2 * pi_iso)
    pr["P_isolated_pair"] = 2 * iso["P"]
    pr["power_ratio"] = pr["P"] / (2 * iso["P"])
    return pr


def edgewise(name, rpm, V, alpha_s):
    import bemt
    c = setup(); b, db = blade(name)
    return bemt.edgewise(b, db, c["air"], max(rpm, 150.0), V, alpha_s, kappa=c["kappa"])


def glauert_vi(T, V, alpha_s, rho, A):
    """Mean induced velocity from Glauert's equation v = T / (2 rho A sqrt((V cos a)^2 + (V sin a + v)^2))."""
    vi = math.sqrt(max(T, 0.0) / (2 * rho * A))
    for _ in range(200):
        vi = 0.5 * vi + 0.5 * max(T, 0.0) / (2 * rho * A * math.hypot(V * math.cos(alpha_s), V * math.sin(alpha_s) + vi) + 1e-12)
    return vi

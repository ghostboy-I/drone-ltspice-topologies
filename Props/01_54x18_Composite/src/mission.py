"""Vehicle trim, forward-flight power, mission energy and mass budget (Phase 1, lower-order).

Trim (point-mass, steady level flight):  drag D = 0.5 rho V^2 CdA,  tilt alpha = atan(D / W),  T_total = sqrt(W^2 + D^2)
Rotor shaft power (energy method, Leishman ch. 5):
    P = kappa T vi  +  T V sin(alpha)  +  P0 (1 + 4.65 mu^2),     mu = V cos(alpha) / Vtip
      induced         climb/parasite       profile
T V sin(alpha) summed over the rotors equals D V, the parasite power. P0 is set so that the same model returns the
assumed figure of merit in hover:  P0 = T_h vh (1/FoM - kappa).
Limits: no rotor-rotor interference, no rotor H-force, RPM held at the hover value, quasi-steady segments.
"""
import math
import momentum as mt


def profile_power_from_fom(t_hover, rho, area, fom, kappa):
    if fom >= 1.0 / kappa:
        raise ValueError("FoM must be below 1/kappa")
    return t_hover * mt.hover_vi(t_hover, rho, area) * (1.0 / fom - kappa)


def trim(weight, rho, v, cda):
    drag = 0.5 * rho * v * v * cda
    return math.atan2(drag, weight), math.hypot(weight, drag), drag


def rotor_power(thrust, rho, area, v, alpha, kappa, p0, vtip):
    vi = mt.glauert_vi(thrust, rho, area, v, alpha) if v > 0 else mt.hover_vi(thrust, rho, area)
    mu = v * math.cos(alpha) / vtip
    return {"vi": vi, "mu": mu, "induced": kappa * thrust * vi, "parasite": thrust * v * math.sin(alpha),
            "profile": p0 * (1.0 + 4.65 * mu * mu),
            "total": kappa * thrust * vi + thrust * v * math.sin(alpha) + p0 * (1.0 + 4.65 * mu * mu)}


def climb_power(thrust, rho, area, vc, kappa, p0):
    vi = mt.climb_vi(thrust, rho, area, vc)
    return kappa * thrust * vi + thrust * vc + p0


class Vehicle:
    """Everything the mission model needs, in SI units."""
    def __init__(self, weight, n_rotors, area, rho, fom, kappa, vtip_hover, cda, eta_drive, eta_batt, avionics_w):
        self.weight, self.n, self.area, self.rho = weight, n_rotors, area, rho
        self.fom, self.kappa, self.vtip, self.cda = fom, kappa, vtip_hover, cda
        self.eta = eta_drive * eta_batt
        self.avionics = avionics_w
        self.t_hover = weight / n_rotors
        self.p0 = profile_power_from_fom(self.t_hover, rho, area, fom, kappa)

    def hover_shaft(self):
        return self.n * rotor_power(self.t_hover, self.rho, self.area, 0.0, 0.0, self.kappa, self.p0, self.vtip)["total"]

    def cruise(self, v):
        alpha, t_tot, drag = trim(self.weight, self.rho, v, self.cda)
        r = rotor_power(t_tot / self.n, self.rho, self.area, v, alpha, self.kappa, self.p0, self.vtip)
        r.update(alpha=alpha, drag=drag, shaft_total=self.n * r["total"])
        return r

    def climb_shaft(self, vc):
        return self.n * climb_power(self.t_hover, self.rho, self.area, vc, self.kappa, self.p0)

    def electrical(self, p_shaft):
        return p_shaft / self.eta + self.avionics


def mission_energy(veh, m, range_m, v_cruise):
    """Segment list and battery energy drawn. m = params['mission'] dict."""
    hov = veh.hover_shaft()
    cr = veh.cruise(v_cruise)
    segs = [
        ("takeoff hover", m["takeoff_hover_s"], hov),
        ("climb", m["cruise_alt_m"] / m["climb_rate_ms"], veh.climb_shaft(m["climb_rate_ms"])),
        ("cruise", range_m / v_cruise, cr["shaft_total"]),
        ("descent", m["cruise_alt_m"] / m["descent_rate_ms"], hov),
        ("delivery hover", m["delivery_hover_s"], hov),
        ("landing hover", m["landing_hover_s"], hov),
    ]
    rows, e_wh = [], 0.0
    for name, t, p_shaft in segs:
        p_el = veh.electrical(p_shaft)
        e = p_el * t / 3600.0
        e_wh += e
        rows.append({"segment": name, "time_s": t, "shaft_w": p_shaft, "electrical_w": p_el, "energy_wh": e})
    t_total = sum(r["time_s"] for r in rows)
    t_hoverlike = t_total - range_m / v_cruise
    return {"segments": rows, "energy_wh": e_wh, "pack_wh": e_wh / (1.0 - m["reserve_fraction"]),
            "time_s": t_total, "hover_time_share": t_hoverlike / t_total,
            "hover_energy_share": 1.0 - rows[2]["energy_wh"] / e_wh, "cruise": cr}


def mass_budget(pack_wh, wh_per_kg, motor_kg, esc_kg, blade_kg, n_blades, hub_kg, n_rotors, frame_kg, avionics_kg):
    items = {"battery": pack_wh / wh_per_kg, "motors": n_rotors * motor_kg, "escs": n_rotors * esc_kg,
             "props": n_rotors * (n_blades * blade_kg + hub_kg), "frame": frame_kg, "avionics_wiring": avionics_kg}
    items["total"] = sum(items.values())
    return items

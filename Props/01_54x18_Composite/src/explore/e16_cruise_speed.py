"""Exploration 16: cruise speed per configuration (best-range speed of the tri, hex and y6 with their current best designs).

The mission is a fixed 10 nmi, so cruise energy = P(V) x range / V (plus 150 W avionics for the flight time): the
best-range speed minimises (P + P_av) / V, not P. Entries 01-15 all flew 15 m/s (the stated design point).

Model per layout (blade and arm option from entries 11-14):
  trim at each V: drag = q CdA_body + sum of rotor H-forces + arm/mast drag force (cross-flow, sin^3, entry 14),
                  shaft tilt alpha = atan(drag / W), thrust per rotor = hypot(W, drag) / n   (as phase2.Rotor.cruise)
  rotor power: BEMT edgewise at that thrust, V and tilt (same call as entries 09-14)
  inter-rotor interference: entry 09's value at 15 m/s, scaled as 15/V (induced power ~ T v_i, v_i ~ T/(2 rho A V) at
                  high speed; the wake-skew geometry factor is held at its 15 m/s value: conservative for V > 15)
  hover/climb: entry 14's best rows (download included); hardware unchanged (hover sizes the motors).
Checks: advancing-tip Mach (flag > 0.70) and the largest section angle of attack (retreating-side stall).

Hand check: the classic power-required curve with a = kappa W^2 / (2 rho A_tot) (induced, Glauert high-speed),
    P0 (1 + 4.65 mu^2) (profile), 0.5 rho V^3 f (parasite, f = CdA + arms), P_av (avionics, electrical -> shaft)
and V* = argmin (P/V), with P0 = P_hover - kappa W^1.5 / sqrt(2 rho A_tot); induced from the full Glauert inflow
    v_i = v_h^2 / sqrt(V^2 + v_i^2) (at 15 m/s these rotors are NOT in the v_i << V regime). If only induced and parasite mattered,
    V* = (a / (1.5 rho f))^(1/4) ... d/dV [a/V^2 + 0.5 rho f V^2] = 0 -> V*^4 = 2a/(rho f)  (written out in the log)
"""
import json, math, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from multiprocessing import Pool
from scipy.optimize import minimize_scalar
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import bemt
import mission as ms
import e01_coax_blade as e01
import e02_coax_two_point as e02
from e09_hex_vs_y6 import layouts, CD_TUBE, MAST_OD, H_Y6, D, R
from common import RESULTS, save_json

OUT = os.path.join(RESULTS, "explore")
SPEEDS = (10.0, 12.0, 14.0, 15.0, 16.0, 18.0, 20.0, 22.0, 24.0, 26.0, 28.0, 30.0)
LAYOUTS = {"tri": 3, "hex0": 6, "y6": 6}


class VehV:
    def __init__(s, p, h, c, cruise_of_v): s.p, s.h, s.c, s.f = p, h, c, cruise_of_v
    def hover_shaft(s): return s.h
    def climb_shaft(s, vc): return s.c
    def cruise(s, v): return {"shaft_total": s.f(v)}
    def electrical(s, psh):
        el = s.p["electrical"]; return psh / (el["eta_motor_esc"] * el["eta_battery_wiring"]) + s.p["mission"]["avionics_w"]


def blades():
    G = e01.G; p = G["p"]; Rr = p["rotor"]["diameter_in"] * p["constants"]["inch_to_m"] / 2
    e11 = json.load(open(os.path.join(OUT, "e11_blade_with_motor.json"))); e12 = json.load(open(os.path.join(OUT, "e12_y6_blade_with_motor.json")))
    e13 = json.load(open(os.path.join(OUT, "e13_tri_torque_margin.json")))
    bd = {"tri": max(e13["runs"], key=lambda r: r["end"]["dpayload"])["blade"],
          "hex0": max((r for r in e11["runs"] if r["mode"] == "motor"), key=lambda r: r["end"]["payload"])["blade"],
          "y6": max(e12["runs"], key=lambda r: r["end_full"]["payload"])["blade"]}
    return {c: e02.blade_from(b, Rr, p["rotor"]["hub_radius_m"]) for c, b in bd.items()}


def arm_force_per_q(c):
    """Arm + mast drag force divided by dynamic pressure [m^2] at the e14 best option."""
    e9 = json.load(open(os.path.join(OUT, "e09_hex_vs_y6.json"))); e14 = json.load(open(os.path.join(OUT, "e14_faired_arms.json")))
    C = e14["configs"][c]; row = C["rows"][e14["best_option"][c]["option"]]
    q15, V15 = e14["constants"]["q_cruise_pa"], e14["constants"]["V"]
    eta = 0.8
    return (row["arm_drag_w"] + row["mast_drag_w"]) * eta / (V15 * q15), row


def point(args):
    c, V = args
    G = e01.G; p, ph1, db, hot = G["p"], G["ph1"], G["db"], G["hot"]; W = ph1["vehicle"]["weight_n"]
    b = blades()[c]; n = LAYOUTS[c]; f_arm, row = arm_force_per_q(c)
    e9 = json.load(open(os.path.join(OUT, "e09_hex_vs_y6.json")))
    inter15 = e9["configs"][c]["interference_w"]
    q = 0.5 * hot["rho"] * V * V; h = 0.0
    for _ in range(5):
        drag = q * (p["vehicle"]["cda_m2"] + f_arm) + n * h
        al, t_tot = math.atan2(drag, W), math.hypot(W, drag)
        e = bemt.edgewise_at_thrust(b, db, hot, t_tot / n, V, al, kappa=p["rotor"]["kappa"]); h = e["H"]
    P = n * e["P"] + inter15 * 15.0 / V
    return {"layout": c, "V": V, "P_shaft": P, "P_rotors": n * e["P"], "interference_w": inter15 * 15.0 / V, "alpha_deg": math.degrees(al), "rpm": e["rpm"],
            "mu": e["mu"], "tip_mach_adv": e["tip_mach_adv"], "alpha_max_deg": e["alpha_max_deg"], "drag_n": drag, "f_arm_m2": f_arm}


def run():
    t0 = time.time(); e01.init(); G = e01.G; p, ph1, hot = G["p"], G["ph1"], G["hot"]
    ctx = e02.context(); whkg = p["mass"]["pack_wh_per_kg_cited"]; rng = ph1["vehicle"]["range_m"]; W = ph1["vehicle"]["weight_n"]
    with Pool(4, initializer=e01.init) as pool:
        pts = pool.map(point, [(c, V) for c in LAYOUTS for V in SPEEDS])
    e14 = json.load(open(os.path.join(OUT, "e14_faired_arms.json")))
    out = {"layouts": {}, "speeds": SPEEDS}
    for c, n in LAYOUTS.items():
        rows = sorted((r for r in pts if r["layout"] == c), key=lambda r: r["V"])
        row14 = e14["configs"][c]["rows"][e14["best_option"][c]["option"]]
        hov = row14["hover_w"]; clb = ctx["base_climb"] * hov / ctx["base_hover"]
        Vs = np.array([r["V"] for r in rows]); Ps = np.array([r["P_shaft"] for r in rows])
        cr = lambda v: float(np.interp(v, Vs, Ps)) if v <= Vs[-1] else float(Ps[-1])
        for r in rows:
            m = ms.mission_energy(VehV(p, hov, clb, cr), p["mission"], rng, r["V"]); r["pack_wh"] = m["pack_wh"]
            r["cruise_wh"] = m["segments"][2]["energy_wh"]; r["wh_per_km_shaft"] = r["P_shaft"] / r["V"] / 3.6
        # best-range speed by a parabola through the three lowest-pack speeds
        i = int(np.argmin([r["pack_wh"] for r in rows])); j = min(max(i, 1), len(rows) - 2)
        xs = Vs[j - 1:j + 2]; ys = np.array([rows[k]["pack_wh"] for k in range(j - 1, j + 2)])
        a2, a1, a0 = np.polyfit(xs, ys, 2); v_best = -a1 / (2 * a2); pack_best = a0 + a1 * v_best + a2 * v_best ** 2
        r15 = next(r for r in rows if r["V"] == 15.0)
        out["layouts"][c] = {"rows": rows, "v_best": v_best, "pack_best": pack_best, "pack_15": r15["pack_wh"], "hover_w": hov,
                             "payload_gain_at_v_best_kg": (r15["pack_wh"] - pack_best) / whkg, "pack_e14_15": row14["pack_wh"]}
        print(f"  {c}: " + ", ".join(f"{r['V']:.0f}: {r['P_shaft']:.0f} W / {r['pack_wh']:.0f} Wh (adv M {r['tip_mach_adv']:.2f}, a_max {r['alpha_max_deg']:.1f})" for r in rows))
        print(f"     best-range V {v_best:.1f} m/s, pack {pack_best:.0f} Wh (15 m/s: {r15['pack_wh']:.0f}; entry 14 at 15: {row14['pack_wh']:.0f}),"
              f" gain {out['layouts'][c]['payload_gain_at_v_best_kg']:.2f} kg", flush=True)
    # hand check: classic power curve
    rho = hot["rho"]; A1 = math.pi * R * R; kap = p["rotor"]["kappa"]; el = p["electrical"]
    p_av_shaft = p["mission"]["avionics_w"] * el["eta_motor_esc"] * el["eta_battery_wiring"]
    hand = {}
    for c, n in LAYOUTS.items():
        L = out["layouts"][c]; A = n * A1; f = p["vehicle"]["cda_m2"] + L["rows"][0]["f_arm_m2"]
        p_ind_h = kap * W ** 1.5 / math.sqrt(2 * rho * A); P0 = L["hover_w"] - p_ind_h
        omR = L["rows"][3]["rpm"] * 2 * math.pi / 60 * R
        a = kap * W * W / (2 * rho * A); vh = math.sqrt(W / (2 * rho * A))
        def vi(V):                                   # full Glauert inflow: v_i = v_h^2 / sqrt(V^2 + v_i^2) (shaft tilt neglected)
            v = vh
            for _ in range(60): v = 0.5 * v + 0.5 * vh * vh / math.sqrt(V * V + v * v)
            return v
        Pv = lambda V: kap * W * vi(V) + P0 * (1 + 4.65 * (V / omR) ** 2) + 0.5 * rho * f * V ** 3
        res = minimize_scalar(lambda V: (Pv(V) + p_av_shaft) / V, bounds=(6, 30), method="bounded")
        hand[c] = {"A_tot": A, "f_m2": f, "a_induced": a, "P0_profile": P0, "omega_R": omR, "V_star_hand": res.x,
                   "V_star_ind_par_only": (2 * a / (rho * f)) ** 0.25, "P_hand_15": Pv(15.0), "P_bemt_15": L["rows"][3]["P_shaft"],
                   "v_h": vh, "v_i_15": vi(15.0), "v_i_15_highspeed": vh * vh / 15.0,
                   "P_hand_by_V": {V: Pv(V) for V in SPEEDS}, "P_bemt_by_V": {r["V"]: r["P_shaft"] for r in L["rows"]}}
    out["hand_check"] = hand
    print(f"  hand: {hand}")
    out["runtime_s"] = time.time() - t0
    save_json(os.path.join("explore", "e16_cruise_speed.json"), out); plot(out)
    print(f"  wrote results/explore/e16_cruise_speed.json in {out['runtime_s']:.0f} s")


def plot(o):
    fig, axs = plt.subplots(1, 2, figsize=(10, 3.4)); col = {"tri": "#0b0b0b", "hex0": "#2a78d6", "y6": "#c0392b"}
    for c, L in o["layouts"].items():
        V = [r["V"] for r in L["rows"]]
        axs[0].plot(V, [r["P_shaft"] / 1000 for r in L["rows"]], "o-", color=col[c], label=c)
        axs[1].plot(V, [r["pack_wh"] for r in L["rows"]], "o-", color=col[c], label=c)
        axs[1].plot([L["v_best"]], [L["pack_best"]], "*", color=col[c], ms=10)
    for a in axs: a.axvline(15, color="#888", lw=0.8, ls=":"); a.set_xlabel("cruise speed [m/s]"); a.grid(alpha=.3)
    axs[0].set_ylabel("cruise shaft power [kW]"); axs[1].set_ylabel("pack energy, 10 nmi mission [Wh]"); axs[0].legend(fontsize=7)
    fig.suptitle("Exploration 16: cruise speed per configuration (star: best-range speed; dotted: 15 m/s design point)", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "e16_cruise_speed.png"), dpi=140); plt.close(fig)


if __name__ == "__main__":
    if sys.argv[1:] == ["plot"]:
        plot(json.load(open(os.path.join(OUT, "e16_cruise_speed.json"))))
    else:
        run()

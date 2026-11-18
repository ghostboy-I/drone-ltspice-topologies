"""Exploration 18: fuselage drag against pitch attitude, and what it does to each layout's best-range speed and payload.

Entries 16-17 held the body drag area at CdA0 = 0.60 m^2 at every speed, but a multirotor's fuselage pitches nose-down
with the rotor shafts: 13 deg for the tri at 24.7 m/s, about 10 deg for the hex at 21 m/s. Two bounding body models
(alpha_b = body incidence = shaft tilt minus any built-in nose-down pre-tilt):
  'streamlined'  cross-flow theory (Hoerner / Allen-Perkins): extra drag of the body's plan area at incidence,
                 f = f0 + Cd_c A_plan |sin alpha_b|^3   (normal force ~ sin^2, its drag component one more sin)
  'bluff box'    drag follows the projected frontal area:  f = f0 (cos alpha_b + r sin alpha_b),  r = A_plan / A_front
  plus each with a body built nose-down by PRE_TILT_DEG (level at the tri's cruise attitude).
Assumptions (no airframe geometry yet): A_plan 1.2 m^2, Cd_c 1.0, r = 2.0 (A_front = 0.6 m^2 at Cd 1.0).
The trim is iterated with f(alpha); everything else (blades from entry 17, hover, motors, arms, fairings) is entry 17's.

Hand check: the trim tilt is tan(alpha) = D / W, so for the bluff model the drag area grows by
    f/f0 = cos a + r sin a ;  at a = 13 deg, r = 2:  0.974 + 0.450 = 1.424  (+42 %)
and the best-range speed scales roughly as f^(-1/4) in the induced/parasite limit (V*^4 = 2a/(rho f), entry 16):
    1.424^(-1/4) = 0.915  -> the tri's 24.7 m/s drops toward 22.6 m/s (before the feedback of f on alpha).
"""
import json, math, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from multiprocessing import Pool
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import bemt
import e01_coax_blade as e01
import e02_coax_two_point as e02
import e17_blade_at_best_speed as e17
from common import RESULTS, save_json

OUT = os.path.join(RESULTS, "explore")
A_PLAN, CD_C, R_BLUFF, PRE_TILT_DEG = 1.2, 1.0, 2.0, 13.0
MODELS = ("constant", "streamlined", "bluff", "bluff pre-tilted")
SPEEDS = tuple(float(v) for v in range(14, 31))


def body_f(model, f0, alpha):
    a = alpha - (math.radians(PRE_TILT_DEG) if "pre-tilted" in model else 0.0)
    if model == "constant": return f0
    if model == "streamlined": return f0 + CD_C * A_PLAN * abs(math.sin(a)) ** 3
    return f0 * (math.cos(a) + R_BLUFF * abs(math.sin(a)))


def make_cruise(model):
    def cruise(b, S, V):
        G = e01.G; p, ph1, db, hot = G["p"], G["ph1"], G["db"], G["hot"]; W = ph1["vehicle"]["weight_n"]; n = S["n"]
        q = 0.5 * hot["rho"] * V * V; h = 0.0; al = 0.0
        for _ in range(7):
            drag = q * (body_f(model, p["vehicle"]["cda_m2"], al) + S["f_arm"]) + n * h
            al, t_tot = math.atan2(drag, W), math.hypot(W, drag)
            e = bemt.edgewise_at_thrust(b, db, hot, t_tot / n, V, al, kappa=p["rotor"]["kappa"]); h = e["H"]
        e["alpha_shaft_deg"] = math.degrees(al); e["f_body"] = body_f(model, p["vehicle"]["cda_m2"], al)
        return n * e["P"] + S["inter15"] * 15.0 / V, e
    return cruise


def point(args):
    c, model, V = args
    e17.cruise = make_cruise(model)
    S = e17.setup(c); bd = json.load(open(os.path.join(OUT, "e17_blade_at_best_speed.json")))
    blade = next(r["blade"] for r in bd["runs"] if r["layout"] == c)
    p = e01.G["p"]; Rr = p["rotor"]["diameter_in"] * p["constants"]["inch_to_m"] / 2
    b = e02.blade_from(blade, Rr, p["rotor"]["hub_radius_m"])
    r = e17.evaluate(b, S, V); _, e = e17.cruise(b, S, V)
    return {"layout": c, "model": model, "V": V, "mass_sum": r["mass_sum"], "pack": r["pack"], "cruise_w": r["cruise"],
            "alpha_deg": e["alpha_shaft_deg"], "f_body": e["f_body"]}


def run():
    t0 = time.time(); e01.init()
    jobs = [(c, m, V) for c in ("tri", "hex0") for m in MODELS for V in SPEEDS]
    with Pool(4, initializer=e01.init) as pool:
        pts = pool.map(point, jobs)
    out = {"assumptions": {"A_plan": A_PLAN, "Cd_c": CD_C, "r_bluff": R_BLUFF, "pre_tilt_deg": PRE_TILT_DEG}, "cases": {}}
    for c in ("tri", "hex0"):
        for m in MODELS:
            rows = sorted((r for r in pts if r["layout"] == c and r["model"] == m), key=lambda r: r["V"])
            i = int(np.argmin([r["mass_sum"] for r in rows])); j = min(max(i, 1), len(rows) - 2)
            xs = np.array([rows[k]["V"] for k in (j - 1, j, j + 1)]); ys = np.array([rows[k]["mass_sum"] for k in (j - 1, j, j + 1)])
            a2, a1, a0 = np.polyfit(xs, ys, 2); vb = -a1 / (2 * a2); mb = a0 + a1 * vb + a2 * vb * vb
            r15 = next(r for r in rows if r["V"] == 15.0)
            out["cases"][f"{c}|{m}"] = {"rows": rows, "v_best": vb, "mass_best": mb, "mass_15": r15["mass_sum"], "pack_best": float(np.interp(vb, [r["V"] for r in rows], [r["pack"] for r in rows])),
                                        "alpha_best_deg": float(np.interp(vb, [r["V"] for r in rows], [r["alpha_deg"] for r in rows])),
                                        "f_best": float(np.interp(vb, [r["V"] for r in rows], [r["f_body"] for r in rows]))}
            C = out["cases"][f"{c}|{m}"]
            print(f"  {c:4s} {m:17s}: best V {vb:.1f} m/s, alpha {C['alpha_best_deg']:.1f} deg, f_body {C['f_best']:.3f} m2, pack {C['pack_best']:.0f} Wh,"
                  f" hw+batt {mb:.2f} kg (15 m/s: {r15['mass_sum']:.2f})", flush=True)
    rank = {}
    for m in MODELS:
        t, h = out["cases"][f"tri|{m}"], out["cases"][f"hex0|{m}"]
        rank[m] = {"hex_minus_tri_payload_free_speed": t["mass_best"] - h["mass_best"], "hex_minus_tri_payload_15": t["mass_15"] - h["mass_15"],
                   "hex_energy_vs_tri_free": h["pack_best"] / t["pack_best"] - 1}
    out["ranking"] = rank; print(f"  hex payload vs tri: {rank}")
    a = math.radians(13.0)
    out["hand_check"] = {"bluff_ratio_13deg": math.cos(a) + R_BLUFF * math.sin(a), "streamlined_extra_13deg_m2": CD_C * A_PLAN * math.sin(a) ** 3,
                         "v_scale_bluff": (math.cos(a) + R_BLUFF * math.sin(a)) ** -0.25, "v_tri_hand": 24.7 * (math.cos(a) + R_BLUFF * math.sin(a)) ** -0.25}
    print(f"  hand: {out['hand_check']}")
    out["runtime_s"] = time.time() - t0
    save_json(os.path.join("explore", "e18_body_incidence.json"), out); plot(out)
    print(f"  wrote results/explore/e18_body_incidence.json in {out['runtime_s']:.0f} s")


def plot(o):
    fig, axs = plt.subplots(1, 2, figsize=(10, 3.4)); col = {"tri": "#0b0b0b", "hex0": "#2a78d6"}
    ls = {"constant": "-", "streamlined": "--", "bluff": ":", "bluff pre-tilted": "-."}
    for k, C in o["cases"].items():
        c, m = k.split("|"); V = [r["V"] for r in C["rows"]]
        axs[0].plot(V, [r["mass_sum"] for r in C["rows"]], ls[m], color=col[c], label=f"{c} {m}")
        axs[0].plot([C["v_best"]], [C["mass_best"]], "o", color=col[c], ms=3)
        axs[1].plot(V, [r["alpha_deg"] for r in C["rows"]], ls[m], color=col[c], label=f"{c} {m}")
    axs[0].set_xlabel("cruise speed [m/s]"); axs[0].set_ylabel("hardware + battery [kg]"); axs[0].legend(fontsize=6); axs[0].grid(alpha=.3)
    axs[1].set_xlabel("cruise speed [m/s]"); axs[1].set_ylabel("shaft tilt in cruise [deg]"); axs[1].grid(alpha=.3)
    fig.suptitle("Exploration 18: body drag against pitch attitude (lower curve = more payload)", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "e18_body_incidence.png"), dpi=140); plt.close(fig)


if __name__ == "__main__":
    if sys.argv[1:] == ["plot"]:
        plot(json.load(open(os.path.join(OUT, "e18_body_incidence.json"))))
    else:
        run()

"""Exploration 24: the speed / body / ranking chain (entries 16-19) re-run with the best-camber blades of entries 22-23.

Entries 16-19 ranked tri vs hex with 44xx blades. Entries 22-23 found that 2 % camber is better: hex 24xx (+1.03 kg) and
tri 44/24 hybrid (+0.25 kg), both optimised at 15 m/s in the entry 11/13 frame. Here those blades (with their own polar
sets) go through entry 18's vehicle model (entry 17's bookkeeping: arms and fairings of entry 14, hover download, torque-
sized motors, ESCs, spar blades; cruise trim with the body drag model) at 14-30 m/s and all four body models, and then
through entry 19's ranking (15 m/s and free speed, 303.3 and 200 Wh/kg, tip-Mach cap 0.60, motor-fit band).
Not re-optimised at each layout's best speed: entry 17 showed that step is worth < 0.15 kg.

Regression check: the entry 17 blades on 44xx polars, run through this script's point(), must reproduce entry 18's rows.
Hand checks: (1) the payload shift at 15 m/s against entry 22's estimate (sum of the two layouts' blade gains);
(2) the break-even battery e_b* = -dpack / dhw from the two layouts' hardware and pack differences.
"""
import json, math, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from multiprocessing import Pool
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import airfoils
import e01_coax_blade as e01
import e02_coax_two_point as e02
import e17_blade_at_best_speed as e17
import e18_body_incidence as e18
import e19_ranking as e19
from blade_trade_study import HybridDB
from common import RESULTS, save_json

OUT = os.path.join(RESULTS, "explore")
SETS = ("44xx (entry 17)", "best camber (entry 22)")
_DB = {}


def db_for(c, bset):
    if bset.startswith("44xx"): return e01.G["db"]
    if "db24" not in _DB:
        q = json.loads(json.dumps(e01.G["p"])); q["airfoils"]["family"] = "24"; q["airfoils"]["compare_sections"] = []
        _DB["db24"] = airfoils.build_db(q, n_proc=1)[0]; _DB["db44"] = e01.G["db"]
    return _DB["db24"] if c == "hex0" else HybridDB(_DB["db24"], _DB["db44"])


def blade_for(c, bset):
    if bset.startswith("44xx"):
        return next(r["blade"] for r in json.load(open(os.path.join(OUT, "e17_blade_at_best_speed.json")))["runs"] if r["layout"] == c)
    fam = "24xx" if c == "hex0" else "44/24 hybrid"; L = "hex" if c == "hex0" else "tri"
    return next(r["blade"] for r in json.load(open(os.path.join(OUT, "e22_less_camber.json")))["rows"] if r["layout"] == L and r["family"] == fam)


def point(args):
    c, bset, model, V = args
    db44 = _DB["db44"] if "db44" in _DB else e01.G["db"]; e01.G["db"] = db_for(c, bset)
    e17.cruise = e18.make_cruise(model)
    S = e17.setup(c); p = e01.G["p"]; Rr = p["rotor"]["diameter_in"] * p["constants"]["inch_to_m"] / 2
    b = e02.blade_from(blade_for(c, bset), Rr, p["rotor"]["hub_radius_m"])
    try:
        r = e17.evaluate(b, S, V); _, e = e17.cruise(b, S, V)
    finally:
        e01.G["db"] = db44
    return {"layout": c, "set": bset, "model": model, "V": V, "mass_sum": r["mass_sum"], "pack": r["pack"], "hw": r["hw"], "cruise_w": r["cruise"],
            "hover_w": r["hover"], "motor_kg": r["motor_kg"], "alpha_deg": e["alpha_shaft_deg"], "f_body": e["f_body"]}


def ranking(cases):
    """Entry 19's scenarios (tip-Mach cap 0.60 only) on a cases dict shaped like entry 18's."""
    E = {"cases": cases}; e10 = json.load(open(os.path.join(OUT, "e10_motor_mass.json")))
    band = sorted(v["hex_payload_shift_kg"] for v in e10["sensitivity_motor_fit"].values()); sc = []
    for speed in ("15 m/s", "free"):
        for body in e18.MODELS:
            if speed == "15 m/s" and body != "constant": continue
            for eb in (e19.EB_CITED, e19.EB_CONS):
                v = 15.0 if speed == "15 m/s" else None
                t, h = e19.best(e19.rows(E, "tri", body), eb, v), e19.best(e19.rows(E, "hex0", body), eb, v)
                d = t["sum"] - h["sum"]; dhw = h["hw"] - t["hw"]; dpack = h["pack"] - t["pack"]
                sc.append({"speed": speed, "body": body, "e_b": eb, "hex_minus_tri_kg": d, "band_kg": [d + band[0], d + band[1]], "V_tri": t["V"], "V_hex": h["V"],
                           "pack_tri": t["pack"], "pack_hex": h["pack"], "energy_hex_vs_tri": h["pack"] / t["pack"] - 1, "dhw_kg": dhw, "dpack_wh": dpack,
                           "e_b_breakeven": -dpack / dhw if dhw else None})
    ebs = np.linspace(150, 450, 61); curve = {}
    for speed, v in (("15 m/s", 15.0), ("free", None)):
        curve[speed] = [e19.best(e19.rows(E, "tri", "constant"), eb, v)["sum"] - e19.best(e19.rows(E, "hex0", "constant"), eb, v)["sum"] for eb in ebs]
    def cross(ys):
        i = np.where(np.diff(np.sign(ys)))[0]
        return float(np.interp(0, [ys[i[0] + 1], ys[i[0]]], [ebs[i[0] + 1], ebs[i[0]]])) if len(i) else None
    return {"scenarios": sc, "band": band, "curve": {"e_b": ebs.tolist(), **curve}, "breakeven": {k: cross(np.array(v)) for k, v in curve.items()}}


def run():
    t0 = time.time(); e01.init()
    jobs = [(c, s, m, V) for c in ("tri", "hex0") for s in SETS for m in e18.MODELS for V in e18.SPEEDS]
    with Pool(4, initializer=e01.init) as pool:
        pts = pool.map(point, jobs, chunksize=4)
    out = {"sets": {}, "runtime_s": None}
    for s in SETS:
        cases = {}
        for c in ("tri", "hex0"):
            for m in e18.MODELS:
                rows = sorted((r for r in pts if r["layout"] == c and r["set"] == s and r["model"] == m), key=lambda r: r["V"])
                cases[f"{c}|{m}"] = {"rows": rows}
        rk = ranking(cases); out["sets"][s] = {"cases": cases, "ranking": rk}
        for x in rk["scenarios"]:
            print(f"  [{s}] {x['speed']:7s} {x['body']:17s} {x['e_b']:5.0f} Wh/kg: hex - tri {x['hex_minus_tri_kg']:+5.2f} kg [{x['band_kg'][0]:+.2f}, {x['band_kg'][1]:+.2f}],"
                  f" V {x['V_tri']:.1f}/{x['V_hex']:.1f}, energy {100*x['energy_hex_vs_tri']:+.0f} %, dhw {x['dhw_kg']:+.2f} kg, dpack {x['dpack_wh']:+.0f} Wh,"
                  f" break-even {x['e_b_breakeven']:.0f} Wh/kg", flush=True)
        print(f"  [{s}] break-even battery (constant body): {rk['breakeven']}", flush=True)
    # regression: the 44xx set must reproduce entry 18
    e18r = json.load(open(os.path.join(OUT, "e18_body_incidence.json"))); dev = 0.0
    for k, C in out["sets"][SETS[0]]["cases"].items():
        for r, q in zip(C["rows"], e18r["cases"][k]["rows"]): dev = max(dev, abs(r["mass_sum"] - q["mass_sum"]))
    out["regression_max_dev_kg"] = dev; print(f"  regression vs entry 18: max |d mass_sum| = {dev:.4f} kg")
    # hand check 1: shift at 15 m/s (constant body, 303 Wh/kg) against the sum of entry 22's blade gains
    g = lambda s: next(x for x in out["sets"][s]["ranking"]["scenarios"] if x["speed"] == "15 m/s" and x["e_b"] == e19.EB_CITED)
    e22r = json.load(open(os.path.join(OUT, "e22_less_camber.json")))
    gain = {L: max(r["payload_vs_44xx_opt"] for r in e22r["rows"] if r["layout"] == L) for L in ("tri", "hex")}
    out["hand_check"] = {"shift_15_model": g(SETS[1])["hex_minus_tri_kg"] - g(SETS[0])["hex_minus_tri_kg"], "shift_15_hand": gain["hex"] - gain["tri"],
                         "e22_gains": gain,
                         "breakeven_hand_15": {"dpack_wh": g(SETS[1])["dpack_wh"], "dhw_kg": g(SETS[1])["dhw_kg"], "e_b": g(SETS[1])["e_b_breakeven"]}}
    print(f"  hand: {out['hand_check']}")
    out["runtime_s"] = time.time() - t0
    save_json(os.path.join("explore", "e24_chain_best_blades.json"), out); plot(out)
    print(f"  wrote results/explore/e24_chain_best_blades.json in {out['runtime_s']:.0f} s")


def plot(o):
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.2), gridspec_kw={"width_ratios": [1.4, 1]})
    S0, S1 = [o["sets"][s]["ranking"]["scenarios"] for s in SETS]; y = np.arange(len(S1))
    lab = [f"{s['speed']}, {s['body']}, {s['e_b']:.0f} Wh/kg" for s in S1]
    x1 = [s["hex_minus_tri_kg"] for s in S1]; x0 = [s["hex_minus_tri_kg"] for s in S0]
    lo = [s["hex_minus_tri_kg"] - s["band_kg"][0] for s in S1]; hi = [s["band_kg"][1] - s["hex_minus_tri_kg"] for s in S1]
    axs[0].barh(y, x1, color=["#2a78d6" if v > 0 else "#0b0b0b" for v in x1], xerr=[lo, hi], capsize=2, ecolor="#888", label="best-camber blades")
    axs[0].plot(x0, y, "|", color="#d62a2a", ms=10, mew=2, label="44xx blades (entry 19)")
    axs[0].set_yticks(y); axs[0].set_yticklabels(lab, fontsize=6); axs[0].axvline(0, color="#888", lw=0.8); axs[0].invert_yaxis(); axs[0].legend(fontsize=7)
    axs[0].set_xlabel("hex payload minus tri payload [kg]  (blue: hex wins, black: tri wins)"); axs[0].grid(axis="x", alpha=.3)
    for s, ls in zip(SETS, (":", "-")):
        c = o["sets"][s]["ranking"]["curve"]
        for k, col in (("15 m/s", "#2a78d6"), ("free", "#0b0b0b")):
            be = o["sets"][s]["ranking"]["breakeven"][k]
            axs[1].plot(c["e_b"], c[k], ls, color=col, label=f"{k}, {s}" + (f" (break-even {be:.0f})" if be else ""))
    axs[1].axhline(0, color="#888", lw=0.8); axs[1].axvline(303.3, color="#888", ls=":", lw=0.8); axs[1].axvline(200, color="#888", ls=":", lw=0.8)
    axs[1].set_xlabel("pack specific energy [Wh/kg]"); axs[1].set_ylabel("hex minus tri payload [kg]"); axs[1].legend(fontsize=6); axs[1].grid(alpha=.3)
    fig.suptitle("Exploration 24: tri vs hex ranking with the best-camber blades (tip-Mach cap 0.60)", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "e24_chain_best_blades.png"), dpi=140); plt.close(fig)


if __name__ == "__main__":
    if sys.argv[1:] == ["plot"]:
        plot(json.load(open(os.path.join(OUT, "e24_chain_best_blades.json"))))
    else:
        run()

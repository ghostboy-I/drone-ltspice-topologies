"""Exploration 03: blade mass from a sized structure (src/explore/blade_structure.py), then entries 01-02 again.

Part A re-scores every stored design with the structural mass (no aerodynamics re-run: pack energies are unchanged).
Part B re-runs entry 02's payload optimiser with the structural mass in the objective. The 50 N / 1.2 mm flex limit is
built into the sizing, so a blade that is too thin simply comes out heavy (or infeasible, which is penalised).
"""
import json, math, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from multiprocessing import Pool
from scipy.optimize import minimize
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import bemt
from config_study import load_final_blade, coax_pair, mission_pack
from blade_structure import blade_mass
import e01_coax_blade as e01
import e02_coax_two_point as e02
from common import RESULTS, save_json

OUT = os.path.join(RESULTS, "explore")


def mass_of(b):
    return blade_mass(b.r_def, b.c_def, b.tc_def, b.r_hub, b.R)


def payload_struct(ctx, blade_kg, pack, whkg, n_blades=12):
    """Half-size motors. ctx['bkg'] is the vendor-scaled Phase 2 blade the baseline tricopter carries (6 blades)."""
    prop_pair = 2 * (2 * blade_kg + ctx["hub"])
    hw = 3 * (ctx["motors_pair"] + prop_pair - ctx["arm_single"]) - ctx["tilt"]
    return -(hw + (pack - ctx["base_pack"]) / whkg), hw


def optimise(args):
    label, bd = args
    G = e01.G; p, ph1, db, hot = G["p"], G["ph1"], G["db"], G["hot"]
    t0 = time.time(); ctx = e02.context(); whkg = p["mass"]["pack_wh_per_kg_cited"]
    R = p["rotor"]["diameter_in"] * p["constants"]["inch_to_m"] / 2
    b0 = e02.blade_from(bd, R, p["rotor"]["hub_radius_m"]); t_h = ph1["vehicle"]["weight_n"] / 3
    pair0 = coax_pair(b0, db, hot, t_h, 0.4 * R); iso0 = bemt.hover_at_thrust(b0, db, hot, t_h / 2)
    k_pair = pair0["P"] / (2 * iso0["P"])
    hist = []

    def obj(x):
        try:
            b = e02.shape(b0, x)
            if float(np.min(b.c_def)) < p["design"]["chord_tip_min_m"] * 0.999: return 1e3
            ms = mass_of(b)
            r = e02.fast_eval(b, ctx, k_pair)
            pl, _ = payload_struct(ctx, ms["total_kg"], r["pack"], whkg)
            pen = 5 * max(0.0, p["design"]["min_stall_margin_deg"] - r["margin"]) ** 2 + 200 * max(0.0, p["vehicle"]["tw_target"] - r["tw"]) ** 2
            pen += 50 * max(0.0, ms["tip_deflection_mm"] / 1.2 - 1.0)
            hist.append((list(map(float, x)), pl, pen))
            return -pl + pen
        except Exception:
            return 1e3
    x0 = [0.0, 0.0, 0.0, 1.0]
    simplex = [x0, [math.radians(1), 0, 0, 1], [0, math.radians(3), 0, 1], [0, 0, 0.3, 1], [0, 0, 0, 0.85]]
    res = minimize(obj, x0, method="Nelder-Mead", options={"initial_simplex": simplex, "xatol": 2e-4, "fatol": 0.01, "maxfev": 160})
    out = {"label": label, "x": {"twist_offset_deg": math.degrees(res.x[0]), "twist_slope_deg": math.degrees(res.x[1]),
                                 "chord_taper": float(res.x[2]), "chord_scale": float(res.x[3])}, "evaluations": int(res.nfev), "history": hist}
    for tag, b in (("start", b0), ("end", e02.shape(b0, res.x))):
        r = e02.fast_eval(b, ctx, k_pair); ms = mass_of(b)
        pair = coax_pair(b, db, hot, t_h, 0.4 * R); hov = 3 * pair["P"]
        pack = mission_pack(p, ph1, hov, ctx["base_climb"] * hov / ctx["base_hover"], r["cruise"])[0]
        pl, hw = payload_struct(ctx, ms["total_kg"], pack, whkg)
        out[tag] = {"pack_full": pack, "pack_fast": r["pack"], "cruise_w": r["cruise"], "hover_full_w": hov, "tw": r["tw"], "margin": r["margin"],
                    "solidity": b.solidity(), "blade_kg": ms["total_kg"], "caps_kg": ms["caps_kg"], "deflection_mm": ms["tip_deflection_mm"],
                    "feasible": ms["feasible"], "payload_kg": pl, "hardware_kg": hw, "iso_rpm": r["iso"]["rpm"],
                    "blade": {"r": b.r_def.tolist(), "chord": b.c_def.tolist(), "twist_deg": np.degrees(b.th_def).tolist()}}
    out["runtime_s"] = time.time() - t0
    print(f"  {label}: payload {out['start']['payload_kg']:+.2f} -> {out['end']['payload_kg']:+.2f} kg, pack {out['start']['pack_full']:.0f} -> {out['end']['pack_full']:.0f} Wh,"
          f" blade {out['start']['blade_kg']:.3f} -> {out['end']['blade_kg']:.3f} kg, defl {out['end']['deflection_mm']:.2f} mm, x {out['x']} [{out['runtime_s']:.0f}s]", flush=True)
    return out


def run():
    t0 = time.time()
    e01.init(); G = e01.G; p = G["p"]
    ctx = e02.context(); whkg = p["mass"]["pack_wh_per_kg_cited"]
    R = p["rotor"]["diameter_in"] * p["constants"]["inch_to_m"] / 2; rh = p["rotor"]["hub_radius_m"]
    bb = load_final_blade(p)
    # ---- Part A: re-score stored designs ----
    rescore = []
    base_m = mass_of(bb)
    rescore.append({"design": "Phase 2 blade (tricopter and pair)", "blade_kg_volume": ctx["bkg"], "blade_kg_struct": base_m["total_kg"],
                    "deflection_mm": base_m["tip_deflection_mm"], "feasible": base_m["feasible"]})
    e1 = json.load(open(os.path.join(OUT, "e01_coax_blade.json"))); e2 = json.load(open(os.path.join(OUT, "e02_coax_two_point.json")))
    tc = lambda r_: np.interp(r_, bb.r_def, bb.tc_def)
    for s in e1["sweep"]:
        if "error" in s: continue
        b = bemt.Blade(R, rh, 2, s["blade"]["r"], s["blade"]["chord"], np.radians(s["blade"]["twist_deg"]), s["blade"]["tc"]); ms = mass_of(b)
        pl, _ = payload_struct(ctx, ms["total_kg"], s["pack_wh"], whkg)
        rescore.append({"design": f"e01 MIL {s['design_rpm']} rpm", "pack_wh": s["pack_wh"], "blade_kg_volume": ctx["bkg"] * s["blade_volume_cm3"] / ctx["vol0"],
                        "blade_kg_struct": ms["total_kg"], "deflection_mm": ms["tip_deflection_mm"], "feasible": ms["feasible"],
                        "payload_volume_model": s["payload_change_kg"], "payload_struct": pl})
    for r in e2["runs"]:
        bl = r["end"]["blade"]; b = bemt.Blade(R, rh, 2, bl["r"], bl["chord"], np.radians(bl["twist_deg"]), tc(bl["r"])); ms = mass_of(b)
        pl, _ = payload_struct(ctx, ms["total_kg"], r["end"]["pack_full"], whkg)
        rescore.append({"design": f"e02 optimum from {r['label']}", "pack_wh": r["end"]["pack_full"], "blade_kg_volume": ctx["bkg"] * r["end"]["vol_cm3"] / ctx["vol0"],
                        "blade_kg_struct": ms["total_kg"], "deflection_mm": ms["tip_deflection_mm"], "feasible": ms["feasible"],
                        "payload_volume_model": r["end"]["payload_kg"], "payload_struct": pl})
    pl_ref, _ = payload_struct(ctx, base_m["total_kg"], e1["reference_phase2_blade_pair"]["pack_wh"], whkg)
    rescore[0].update(pack_wh=e1["reference_phase2_blade_pair"]["pack_wh"], payload_volume_model=e1["reference_phase2_blade_pair"]["payload_change_kg"], payload_struct=pl_ref)
    for q in rescore:
        print(f"  {q['design']}: blade {q['blade_kg_volume']:.3f} (volume) -> {q['blade_kg_struct']:.3f} kg (structure), defl {q['deflection_mm']:.2f} mm,"
              f" feasible {q['feasible']}, payload {q.get('payload_volume_model', float('nan')):+.2f} -> {q.get('payload_struct', float('nan')):+.2f} kg", flush=True)
    # ---- Part B: re-optimise ----
    starts = [("Phase 2 blade", {"r": bb.r_def.tolist(), "chord": bb.c_def.tolist(), "twist_deg": np.degrees(bb.th_def).tolist(), "tc": bb.tc_def.tolist()})]
    starts += [(f"MIL {s['design_rpm']} rpm", s["blade"]) for s in e1["sweep"] if s.get("design_rpm") in (1150, 1450, 1750)]
    with Pool(4, initializer=e01.init) as pool:
        runs = pool.map(optimise, starts)
    best = max(runs, key=lambda r: r["end"]["payload_kg"] if r["end"]["feasible"] else -1e9)
    out = {"phase2_blade_struct": {k: v for k, v in base_m.items()}, "rescore": rescore, "runs": runs, "best": best["label"], "runtime_s": time.time() - t0}
    save_json(os.path.join("explore", "e03_structural_mass.json"), out)
    plot(out, bb)
    print(f"  best {best['label']}; wrote results/explore/e03_structural_mass.json in {out['runtime_s']:.0f} s")


def plot(o, bb):
    fig, axs = plt.subplots(1, 3, figsize=(12, 3.3))
    m = o["phase2_blade_struct"]; x = np.array(m["r"]) / bb.R
    axs[0].plot(x, m["t_cap_mm"], color="#0b0b0b", label="cap thickness [mm]"); axs[0].plot(x, np.array(m["cap_width_mm"]) / 10, color="#2a78d6", label="cap width [cm]")
    axs[0].set_xlabel("r / R"); axs[0].set_title("Phase 2 blade: minimum-mass spar for 1.2 mm", fontsize=8); axs[0].legend(fontsize=7); axs[0].grid(alpha=.3)
    rs = o["rescore"]; y = np.arange(len(rs))
    axs[1].barh(y - 0.2, [q["blade_kg_volume"] for q in rs], 0.4, color="#2a78d6", alpha=.6, label="mass ~ volume")
    axs[1].barh(y + 0.2, [q["blade_kg_struct"] for q in rs], 0.4, color="#0b0b0b", label="sized structure")
    axs[1].set_yticks(y); axs[1].set_yticklabels([q["design"] for q in rs], fontsize=5); axs[1].invert_yaxis(); axs[1].set_xlabel("blade mass [kg]"); axs[1].legend(fontsize=6)
    axs[1].grid(alpha=.3, axis="x")
    for r, c in zip(o["runs"], ["#2a78d6", "#0b0b0b", "#c0392b", "#e08e0b"]):
        for tag, ls in (("start", "--"), ("end", "-")):
            b = r[tag]["blade"]; axs[2].plot(np.array(b["r"]) / bb.R, 1000 * np.array(b["chord"]), color=c, ls=ls, label=r["label"] if tag == "end" else None)
    axs[2].set_xlabel("r / R"); axs[2].set_ylabel("chord [mm] (dashed start, solid end)"); axs[2].legend(fontsize=6); axs[2].grid(alpha=.3)
    fig.suptitle("Exploration 03: blade mass from a sized spar (50 N, 1.2 mm), entries 01-02 re-scored and re-optimised", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "e03_structural_mass.png"), dpi=140); plt.close(fig)


if __name__ == "__main__":
    run()

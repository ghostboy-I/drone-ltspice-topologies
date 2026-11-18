"""Exploration 04: different upper and lower blades on the coaxial arm.

Upper blade: entry 03's winner (wide, spar-sized). Lower blade: the same planform with a twist change
    d_theta(x) = d0 + d_in * w(x),   w = 1 for x <= 0.75, cosine blend to 0 at x = 0.90
d_in adds pitch where the lower blade sits in the upper wake (r_w ~ 0.85 R at h = 0.2 D). Twist does not change the
spar-sized mass, so payload follows the pack energy.

Each case runs the full coaxial model with two different blades (vortex-cylinder wake, equal torque trim), cruise with
each rotor at T/6 plus the wake-overlap estimate, and the mission.

Hand check (velocity triangle): inside the upper wake the lower blade's inflow is w + v_l instead of v_l, so the inflow
angle at radius r rises by d_phi = atan((w + v_l) / (Omega r)) - atan(v_l' / (Omega r)) relative to a blade that sees only its own
induced flow v_l' (same thrust). Keeping alpha unchanged needs that much extra twist: the hand estimate of d_in at 0.5 R.
"""
import json, math, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from multiprocessing import Pool
from scipy.optimize import brentq
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import bemt, momentum as mt
from config_study import load_final_blade, mission_pack, induced
import e01_coax_blade as e01
import e02_coax_two_point as e02
from common import RESULTS, save_json

OUT = os.path.join(RESULTS, "explore")
H_D = 0.2


def coax_pair2(bu, bl, db, air, thrust, h, n=40, passes=6):
    """coax_pair with different upper and lower blades (same R), equal-torque trim."""
    R, A = bu.R, math.pi * bu.R ** 2
    r = bu.stations(n)[0]
    viu = vil = mt.hover_vi(thrust / 2, air["rho"], A)
    k = h / math.sqrt(R * R + h * h)
    mean_vi = lambda s: float(np.sum(s["vi"] * 2 * math.pi * s["r"] * s["dr"]) / A)
    for _ in range(passes):
        v_up = vil * (1 - k); w = viu * (1 + k); rw = R * math.sqrt(viu / w)
        v_lo = np.where(r < rw, w, 0.0)
        up = lambda rpm: bemt.axial(bu, db, air, rpm, v_up, n=n)
        lo = lambda rpm: bemt.axial(bl, db, air, rpm, v_lo, n=n)
        solve = lambda s: (bemt.trim_rpm(up, s * thrust), bemt.trim_rpm(lo, (1 - s) * thrust))
        s = brentq(lambda s: (lambda u, l: u["Q"] - l["Q"])(*solve(s)), 0.25, 0.85, xtol=1e-4)
        u, l = solve(s)
        nu, nl = mean_vi(u), mean_vi(l)
        done = abs(nu - viu) < 1e-3 and abs(nl - vil) < 1e-3
        viu, vil = nu, nl
        if done: break
    return {"P": u["P"] + l["P"], "split_upper": s, "upper": u, "lower": l, "w": w, "rw": rw, "v_lo": v_lo, "viu": viu, "vil": vil}


def lower_blade(bu, d0, d_in):
    x = bu.r_def / bu.R
    wgt = np.where(x <= 0.75, 1.0, np.where(x >= 0.90, 0.0, 0.5 * (1 + np.cos(math.pi * (x - 0.75) / 0.15))))
    return bemt.Blade(bu.R, bu.r_hub, bu.N, bu.r_def, bu.c_def, bu.th_def + math.radians(d0) + math.radians(d_in) * wgt, bu.tc_def)


def case(args):
    d0, d_in, bd = args
    G = e01.G; p, ph1, db, hot = G["p"], G["ph1"], G["db"], G["hot"]
    ctx = e02.context()
    R = p["rotor"]["diameter_in"] * p["constants"]["inch_to_m"] / 2
    bu = bemt.Blade(R, p["rotor"]["hub_radius_m"], 2, bd["r"], bd["chord"], np.radians(bd["twist_deg"]), bd["tc"])
    bl = lower_blade(bu, d0, d_in); t_h = ph1["vehicle"]["weight_n"] / 3; V = p["mission"]["cruise_speed_ms"]
    try:
        c = coax_pair2(bu, bl, db, hot, t_h, H_D * 2 * R)
        eu = bemt.edgewise_at_thrust(bu, db, hot, ctx["t_tot"] / 6, V, ctx["alpha"], kappa=p["rotor"]["kappa"])
        el = bemt.edgewise_at_thrust(bl, db, hot, ctx["t_tot"] / 6, V, ctx["alpha"], kappa=p["rotor"]["kappa"])
        om = eu["rpm"] * 2 * math.pi / 60
        p_ind = 0.5 * (eu["T"] * eu["lam0"] * om * R + el["T"] * el["lam0"] * el["rpm"] * 2 * math.pi / 60 * R)
        lam = eu["lam0"] + V * math.sin(ctx["alpha"]) / (om * R)
        d = min(0.4 * R * math.tan(math.atan2(eu["mu"], lam)), 2 * R)
        f = (2 * R * R * math.acos(d / (2 * R)) - d / 2 * math.sqrt(4 * R * R - d * d)) / (math.pi * R * R)
        cruise = 3 * (eu["P"] + el["P"]) + 3 * f * (ctx["p_ind_one_disk"] - 2 * p_ind)
        hover = 3 * c["P"]
        pack = mission_pack(p, ph1, hover, ctx["base_climb"] * hover / ctx["base_hover"], cruise)[0]
        lo = c["lower"]; m = (lo["r"] > 0.3 * R) & (lo["r"] < 0.95 * R)
        a_st = db.prop("alpha_stall", lo["tc"], lo["re"], lo["mach"])
        margin_l = float(np.min((a_st - np.degrees(lo["alpha"]))[m]))
        return {"d0": d0, "d_in": d_in, "hover_w": hover, "cruise_w": cruise, "pack_wh": pack, "split_upper": c["split_upper"],
                "rpm_upper": c["upper"]["rpm"], "rpm_lower": lo["rpm"], "margin_lower": margin_l, "cruise_rpm_lower": el["rpm"],
                "alpha_lower_deg": np.degrees(lo["alpha"]).tolist(), "r": lo["r"].tolist(), "w": c["w"], "rw": c["rw"], "vi_lower": lo["vi"].tolist(),
                "alpha_upper_deg": np.degrees(c["upper"]["alpha"]).tolist()}
    except Exception as ex:
        return {"d0": d0, "d_in": d_in, "error": str(ex)}


def run():
    t0 = time.time()
    e01.init(); p = e01.G["p"]
    e3 = json.load(open(os.path.join(OUT, "e03_structural_mass.json")))
    best = next(r for r in e3["runs"] if r["label"] == e3["best"])["end"]["blade"]
    bb = load_final_blade(p)
    bd = dict(best, tc=np.interp(best["r"], bb.r_def, bb.tc_def).tolist())
    grid = [(d0, din, bd) for d0 in (-2.0, -1.0, 0.0, 1.0, 2.0) for din in (0.0, 1.5, 3.0, 4.5)]
    with Pool(4, initializer=e01.init) as pool:
        rows = pool.map(case, grid)
    ok = [r for r in rows if "error" not in r]
    ref = next(r for r in ok if r["d0"] == 0 and r["d_in"] == 0)
    for r in sorted(ok, key=lambda q: q["pack_wh"])[:6]:
        print(f"  d0 {r['d0']:+.1f} d_in {r['d_in']:.1f}: pack {r['pack_wh']:.0f} Wh ({100*(r['pack_wh']/ref['pack_wh']-1):+.2f} %), hover {r['hover_w']:.0f} W, cruise {r['cruise_w']:.0f} W,"
              f" split {r['split_upper']:.3f}, lower margin {r['margin_lower']:.1f}", flush=True)
    print(f"  reference (identical blades): pack {ref['pack_wh']:.0f} Wh (entry 03: 5778)", flush=True)
    # hand check at 0.5 R with the reference lower rotor
    rr = np.array(ref["r"]); R = rr.max() / 0.99 if rr.max() < 0.7 else 0.6858
    i = int(np.argmin(np.abs(rr - 0.5 * 0.6858)))
    om = ref["rpm_lower"] * 2 * math.pi / 60; vl = ref["vi_lower"][i]; w = ref["w"]
    vl_iso = mt.hover_vi(e01.G["ph1"]["vehicle"]["weight_n"] / 6, e01.G["hot"]["rho"], math.pi * 0.6858 ** 2)
    dphi = math.degrees(math.atan((w + vl) / (om * rr[i])) - math.atan(vl_iso / (om * rr[i])))
    best_case = min(ok, key=lambda q: q["pack_wh"] if q["margin_lower"] >= p["design"]["min_stall_margin_deg"] else 1e9)
    hc = {"r_over_R": rr[i] / 0.6858, "w_upper_wake": w, "v_lower_own": vl, "v_isolated_same_thrust": vl_iso, "omega_r": om * rr[i],
          "d_phi_hand_deg": dphi, "alpha_change_ref_vs_upper_deg": ref["alpha_lower_deg"][i] - ref["alpha_upper_deg"][i],
          "best_d_in": best_case["d_in"], "best_d0": best_case["d0"]}
    out = {"upper_blade": "entry 03 winner", "h_over_D": H_D, "rows": rows, "reference": {k: v for k, v in ref.items() if not isinstance(v, list)},
           "best": {k: v for k, v in best_case.items() if not isinstance(v, list)}, "hand_check": hc, "runtime_s": time.time() - t0}
    save_json(os.path.join("explore", "e04_upper_lower_blades.json"), out)
    plot(out, ok, ref, best_case)
    print(f"  hand: {hc}\n  wrote results/explore/e04_upper_lower_blades.json in {out['runtime_s']:.0f} s")


def plot(o, ok, ref, best):
    fig, axs = plt.subplots(1, 2, figsize=(9.5, 3.3))
    d0s = sorted({r["d0"] for r in ok}); dins = sorted({r["d_in"] for r in ok})
    Z = np.full((len(dins), len(d0s)), np.nan)
    for r in ok: Z[dins.index(r["d_in"]), d0s.index(r["d0"])] = 100 * (r["pack_wh"] / ref["pack_wh"] - 1)
    im = axs[0].imshow(Z, origin="lower", cmap="RdBu_r", vmin=-np.nanmax(abs(Z)), vmax=np.nanmax(abs(Z)), aspect="auto",
                       extent=[d0s[0] - 0.5, d0s[-1] + 0.5, dins[0] - 0.75, dins[-1] + 0.75])
    for r in ok: axs[0].text(r["d0"], r["d_in"], f"{100*(r['pack_wh']/ref['pack_wh']-1):+.1f}", ha="center", va="center", fontsize=7)
    axs[0].set_xlabel("lower blade pitch offset d0 [deg]"); axs[0].set_ylabel("extra inboard twist d_in [deg]"); fig.colorbar(im, ax=axs[0], label="pack vs identical blades [%]")
    x = np.array(ref["r"]) / 0.6858
    axs[1].plot(x, ref["alpha_upper_deg"], color="#2a78d6", label="upper")
    axs[1].plot(x, ref["alpha_lower_deg"], color="#0b0b0b", ls="--", label="lower, identical blade")
    axs[1].plot(x, best["alpha_lower_deg"], color="#0b0b0b", label=f"lower, d0 {best['d0']:+.0f}, d_in {best['d_in']:.1f}")
    axs[1].axvline(ref["rw"] / 0.6858, color="#999", ls=":", label="upper wake edge")
    axs[1].set_xlabel("r / R"); axs[1].set_ylabel("angle of attack in hover [deg]"); axs[1].legend(fontsize=6); axs[1].grid(alpha=.3)
    fig.suptitle("Exploration 04: different upper and lower blades (coaxial, h = 0.2 D)", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "e04_upper_lower_blades.png"), dpi=140); plt.close(fig)


if __name__ == "__main__":
    run()

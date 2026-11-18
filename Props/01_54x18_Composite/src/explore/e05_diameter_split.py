"""Exploration 05: upper/lower diameter split on the coaxial arm (h = 0.2 D_upper).

Upper rotor: entry 03's blade, 54 in. Lower rotor: the same blade scaled geometrically about the hub to radius
R_l = s * R_u (chord scaled by the same factor, so solidity and twist vs r/R stay the same). Entry 04 found one blade
works for both rotors, so only the size changes here.
  s < 1: the lower rotor tucks into the upper's contracted wake (r_w = R_u sqrt(v_u / w) ~ 0.85 R_u). The footprint is unchanged.
  s > 1: the lower tip reaches clean air past the wake. The footprint grows; the frame mass for that is NOT counted.

Fixed-footprint variant (s > 1): the lower stays 54 in and the upper shrinks to 54/s in, so the larger disk sets the frame.
The mast height h stays 0.2 x 54 in throughout.

Interference (vortex cylinders, mean induced velocities):
  on the upper disk, r < R_l:  v = (1 - k_l) v_l,  k_l = h / sqrt(R_l^2 + h^2)
  on the lower disk, r < r_w:  w = (1 + k_u) v_u,  r_w = R_u sqrt(v_u / w)
Both RPMs trim to equal torque and total thrust. Blade mass comes from the spar model (blade_structure.py, 50 N / 1.2 mm).
That flex limit is a bench test on the 54 in blade, so it is applied unchanged to the scaled blade (conservative for s < 1).

Hand check: ideal (momentum) induced power with the BEMT thrust split. Upper: P_u = T_u (v_u + (1 - k_l) v_l).
Lower: uniform own velocity v_l over the disk, with the wake core A_w moving at w + v_l and the rest at v_l:
  T_l = 2 rho v_l [A_w' (w + v_l) + (A_l - A_w') v_l],   P_l = 2 rho v_l [A_w' (w + v_l)^2 + (A_l - A_w') v_l^2]   (sum of dT times the axial velocity through each part)
with A_w' = pi min(r_w, R_l)^2. The trend P_ind(s) / P_ind(1) is compared with the BEMT induced power sum dT (v + v_i).
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
from config_study import load_final_blade, mission_pack
from blade_structure import blade_mass
import e01_coax_blade as e01
import e02_coax_two_point as e02
from common import RESULTS, save_json

OUT = os.path.join(RESULTS, "explore")
H_D = 0.2
RATIOS = [0.80, 0.85, 0.90, 0.95, 1.00, 1.05, 1.10, 1.15]


def scaled(b, s):
    Rl = s * b.R; f = (Rl - b.r_hub) / (b.R - b.r_hub)
    return bemt.Blade(Rl, b.r_hub, b.N, b.r_hub + (b.r_def - b.r_hub) * f, b.c_def * s, b.th_def, b.tc_def)


def p_induced(o):
    return float(np.sum(o["dT_dr"] * o["dr"] * (o["v"] + o["vi"])))


def coax_split(bu, bl, db, air, thrust, h, n=40, passes=8):
    Ru, Rl = bu.R, bl.R
    ru, rl = bu.stations(n)[0], bl.stations(n)[0]
    viu = mt.hover_vi(thrust / 2, air["rho"], math.pi * Ru ** 2); vil = mt.hover_vi(thrust / 2, air["rho"], math.pi * Rl ** 2)
    ku, kl = h / math.sqrt(Ru ** 2 + h * h), h / math.sqrt(Rl ** 2 + h * h)
    mean_vi = lambda o, R: float(np.sum(o["vi"] * 2 * math.pi * o["r"] * o["dr"]) / (math.pi * R * R))
    for _ in range(passes):
        v_up = np.where(ru < Rl, vil * (1 - kl), 0.0)
        w = viu * (1 + ku); rw = Ru * math.sqrt(viu / w)
        v_lo = np.where(rl < rw, w, 0.0)
        up = lambda rpm: bemt.axial(bu, db, air, rpm, v_up, n=n)
        lo = lambda rpm: bemt.axial(bl, db, air, rpm, v_lo, n=n)
        solve = lambda s: (bemt.trim_rpm(up, s * thrust), bemt.trim_rpm(lo, (1 - s) * thrust))
        s = brentq(lambda s: (lambda u, l: u["Q"] - l["Q"])(*solve(s)), 0.2, 0.9, xtol=1e-4)
        u, l = solve(s)
        nu, nl = mean_vi(u, Ru), mean_vi(l, Rl)
        done = abs(nu - viu) < 1e-3 and abs(nl - vil) < 1e-3
        viu, vil = nu, nl
        if done: break
    return {"P": u["P"] + l["P"], "split_upper": s, "upper": u, "lower": l, "w": w, "rw": rw, "viu": viu, "vil": vil, "ku": ku, "kl": kl}


def hand(T, split, w, rw, vil, kl, Ru, Rl, rho):
    """Ideal induced power for the BEMT thrust split, w and r_w (momentum, uniform own inflow per disk)."""
    Tu, Tl = split * T, (1 - split) * T
    Au, Al = math.pi * Ru ** 2, math.pi * Rl ** 2
    Aw = math.pi * min(rw, Rl) ** 2
    # upper: own induced v_u from momentum on its own disk, plus the lower rotor's upwash-reduced inflow felt over min(Rl, Ru)
    v_u = mt.hover_vi(Tu, rho, Au)
    Pu = Tu * v_u + Tu * (1 - kl) * vil * min(1.0, Al / Au)
    # lower: solve T_l = 2 rho v [Aw (w + v) + (Al - Aw) v] for v (quadratic in v)
    a, b, c = 2 * rho * Al, 2 * rho * Aw * w, -Tl
    v = (-b + math.sqrt(b * b - 4 * a * c)) / (2 * a)
    Pl = 2 * rho * v * (Aw * (w + v) ** 2 + (Al - Aw) * v * v)      # sum of dT x (axial velocity through the disk)
    return {"v_u": v_u, "v_l": v, "P_u": Pu, "P_l": Pl, "P": Pu + Pl}


def case(arg):
    s, mode = arg if isinstance(arg, tuple) else (arg, "lower")
    G = e01.G; p, ph1, db, hot = G["p"], G["ph1"], G["db"], G["hot"]
    ctx = e02.context(); whkg = p["mass"]["pack_wh_per_kg_cited"]
    e3 = json.load(open(os.path.join(OUT, "e03_structural_mass.json")))
    bd = next(r for r in e3["runs"] if r["label"] == e3["best"])["end"]["blade"]
    bb = load_final_blade(p)
    R = p["rotor"]["diameter_in"] * p["constants"]["inch_to_m"] / 2
    bu = bemt.Blade(R, p["rotor"]["hub_radius_m"], 2, bd["r"], bd["chord"], np.radians(bd["twist_deg"]), np.interp(bd["r"], bb.r_def, bb.tc_def))
    if mode == "lower":
        bl = scaled(bu, s)
    else:                                   # fixed footprint: the lower stays 54 in and the upper shrinks to 54/s in
        bl = bu; bu = scaled(bu, 1 / s)
    t_h = ph1["vehicle"]["weight_n"] / 3; V = p["mission"]["cruise_speed_ms"]
    try:
        c = coax_split(bu, bl, db, hot, t_h, H_D * 2 * R)
        eu = bemt.edgewise_at_thrust(bu, db, hot, ctx["t_tot"] / 6, V, ctx["alpha"], kappa=p["rotor"]["kappa"])
        el = bemt.edgewise_at_thrust(bl, db, hot, ctx["t_tot"] / 6, V, ctx["alpha"], kappa=p["rotor"]["kappa"])
        om_u, om_l = (e["rpm"] * 2 * math.pi / 60 for e in (eu, el))
        p_ind = 0.5 * (eu["T"] * eu["lam0"] * om_u * bu.R + el["T"] * el["lam0"] * om_l * bl.R)
        lam = eu["lam0"] + V * math.sin(ctx["alpha"]) / (om_u * bu.R)
        Rm = min(bu.R, bl.R)       # overlap of the smaller disk with the skewed upper wake
        d = min(H_D * 2 * R * math.tan(math.atan2(eu["mu"], lam)), 2 * Rm)
        f = (2 * Rm * Rm * math.acos(d / (2 * Rm)) - d / 2 * math.sqrt(4 * Rm * Rm - d * d)) / (math.pi * R * R)
        cruise = 3 * (eu["P"] + el["P"]) + 3 * f * (ctx["p_ind_one_disk"] - 2 * p_ind)
        hover = 3 * c["P"]
        pack = mission_pack(p, ph1, hover, ctx["base_climb"] * hover / ctx["base_hover"], cruise)[0]
        mu_, ml_ = (blade_mass(b.r_def, b.c_def, b.tc_def, b.r_hub, b.R) for b in (bu, bl))
        hw = 3 * (ctx["motors_pair"] + 2 * (mu_["total_kg"] + ml_["total_kg"]) + 2 * ctx["hub"] - ctx["arm_single"]) - ctx["tilt"]
        payload = -(hw + (pack - ctx["base_pack"]) / whkg)
        lo = c["lower"]; m = (lo["r"] > 0.3 * bl.R) & (lo["r"] < 0.95 * bl.R)
        margin = float(np.min((db.prop("alpha_stall", lo["tc"], lo["re"], lo["mach"]) - np.degrees(lo["alpha"]))[m]))
        hc = hand(t_h, c["split_upper"], c["w"], c["rw"], c["vil"], c["kl"], bu.R, bl.R, hot["rho"])
        return {"s": s, "mode": mode, "D_upper_in": 2 * bu.R / p["constants"]["inch_to_m"], "D_lower_in": 2 * bl.R / p["constants"]["inch_to_m"], "hover_w": hover, "cruise_w": cruise, "pack_wh": pack,
                "payload_kg": payload, "hardware_kg": hw, "split_upper": c["split_upper"], "rpm_upper": c["upper"]["rpm"], "rpm_lower": lo["rpm"],
                "tip_mach_lower": lo["tip_mach"], "margin_lower": margin, "w": c["w"], "rw": c["rw"], "rw_over_Rl": c["rw"] / bl.R,
                "P_ind_bemt_arm": p_induced(c["upper"]) + p_induced(lo), "P_profile_arm": c["P"] - p_induced(c["upper"]) - p_induced(lo),
                "P_ind_hand_arm": hc["P"], "hand": hc, "blade_kg_upper": mu_["total_kg"], "blade_kg_lower": ml_["total_kg"],
                "defl_lower_mm": ml_["tip_deflection_mm"], "feasible_lower": ml_["feasible"], "overlap_f": f,
                "r_lower": (lo["r"] / bl.R).tolist(), "dT_lower": lo["dT_dr"].tolist(), "r_upper": (c["upper"]["r"] / R).tolist(), "dT_upper": c["upper"]["dT_dr"].tolist()}
    except Exception as ex:
        return {"s": s, "mode": mode, "error": repr(ex)}


def run():
    t0 = time.time()
    with Pool(4, initializer=e01.init) as pool:
        rows = pool.map(case, [(r, "lower") for r in RATIOS] + [(r, "footprint") for r in RATIOS if r > 1])
    for r in rows:
        if "error" in r: print("  ERROR", r)
    fp = [r for r in rows if "error" not in r and r["mode"] == "footprint"]
    ok = [r for r in rows if "error" not in r and r["mode"] == "lower"]
    ref = next(r for r in ok if r["s"] == 1.0)
    for r in ok + fp:
        print(f"  [{r['mode']}] s {r['s']:.2f} (D_u {r['D_upper_in']:.1f}, D_l {r['D_lower_in']:.1f} in): pack {r['pack_wh']:.0f} Wh ({100*(r['pack_wh']/ref['pack_wh']-1):+.2f} %), hover {r['hover_w']:.0f} W, cruise {r['cruise_w']:.0f} W,"
              f" payload {r['payload_kg']:+.2f} kg, split {r['split_upper']:.3f}, rpm {r['rpm_upper']:.0f}/{r['rpm_lower']:.0f}, r_w/R_l {r['rw_over_Rl']:.2f},"
              f" P_ind bemt/hand {r['P_ind_bemt_arm']:.0f}/{r['P_ind_hand_arm']:.0f} W, margin {r['margin_lower']:.1f}, blade_l {r['blade_kg_lower']:.3f} kg", flush=True)
    print(f"  reference s = 1: pack {ref['pack_wh']:.0f} Wh (entry 03/04: 5778)")
    out = {"h_over_D": H_D, "rows": rows, "runtime_s": time.time() - t0}
    save_json(os.path.join("explore", "e05_diameter_split.json"), out)
    plot(ok, ref, fp)
    print(f"  wrote results/explore/e05_diameter_split.json in {out['runtime_s']:.0f} s")


def plot(ok, ref, fp):
    fig, axs = plt.subplots(1, 3, figsize=(12, 3.3))
    s = [r["s"] for r in ok]
    axs[0].plot(s, [100 * (r["pack_wh"] / ref["pack_wh"] - 1) for r in ok], "o-", color="#0b0b0b", label="pack energy")
    axs[0].plot(s, [100 * (r["hover_w"] / ref["hover_w"] - 1) for r in ok], "s--", color="#2a78d6", label="hover power")
    axs[0].plot(s, [100 * (r["cruise_w"] / ref["cruise_w"] - 1) for r in ok], "^--", color="#c0392b", label="cruise power")
    axs[0].plot([r["s"] for r in fp], [100 * (r["pack_wh"] / ref["pack_wh"] - 1) for r in fp], "o:", color="#e08e0b", label="pack, fixed 54 in footprint (upper shrinks)")
    axs[0].axhline(0, color="#999", lw=.8); axs[0].set_xlabel("R_lower / R_upper"); axs[0].set_ylabel("change vs equal diameters [%]"); axs[0].legend(fontsize=7); axs[0].grid(alpha=.3)
    axs[1].plot(s, [r["P_ind_bemt_arm"] / ref["P_ind_bemt_arm"] for r in ok], "o-", color="#0b0b0b", label="BEMT induced")
    axs[1].plot(s, [r["P_ind_hand_arm"] / ref["P_ind_hand_arm"] for r in ok], "o--", color="#2a78d6", label="momentum hand check")
    axs[1].plot(s, [r["P_profile_arm"] / ref["P_profile_arm"] for r in ok], "^:", color="#c0392b", label="BEMT profile")
    axs[1].set_xlabel("R_lower / R_upper"); axs[1].set_ylabel("arm hover power / equal diameters"); axs[1].legend(fontsize=7); axs[1].grid(alpha=.3)
    for r, col in ((ok[0], "#2a78d6"), (ref, "#0b0b0b"), (ok[-1], "#c0392b")):
        axs[2].plot(r["r_lower"], r["dT_lower"], color=col, label=f"lower, s {r['s']:.2f}")
        axs[2].axvline(r["rw_over_Rl"], color=col, ls=":", lw=.8)
    axs[2].plot(ref["r_upper"], ref["dT_upper"], color="#999", label="upper")
    axs[2].set_xlabel("r / R (own rotor)"); axs[2].set_ylabel("dT/dr [N/m]"); axs[2].legend(fontsize=6); axs[2].grid(alpha=.3)
    fig.suptitle("Exploration 05: lower/upper diameter split (coaxial, h = 0.2 D_upper; dotted: upper wake edge)", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "e05_diameter_split.png"), dpi=140); plt.close(fig)


if __name__ == "__main__":
    run()

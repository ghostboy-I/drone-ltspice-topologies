"""Exploration 09: tricopter vs Y6 (coaxial arms) vs planar hexacopter, with sized arms and inter-rotor cruise interference.

Configurations (54 in rotors, hub spacing between neighbouring rotors 1.10 D as in params):
  tri    3 rotors at T/3 (Phase 2 blade, U15XL), hubs on a circle of radius 1.10 D / sqrt 3 = 0.635 D, tilt servo for yaw
  y6     3 coaxial arms at the tri positions, rotors at T/6 (entry 03 blade, half-size motors), vertical mast h/D = 0.4
  hex    6 rotors at T/6 in one plane (entry 03 blade, half-size motors), hubs on a circle of radius 1.10 D
         'hex0': an arm on the flight line (rotors fore and aft);  'hex30': rotated 30 deg (rotors in side-by-side pairs)
Power:
  hover  tri: Phase 2 baseline; y6: entry 06 (h/D 0.4, BEMT coax); hex: 6 isolated rotors at T/6 (BEMT). Hover interference
         between neighbouring planar rotors with a 10 % tip gap is neglected.
  cruise every rotor edgewise at its share of the trimmed thrust, plus the induced interference of every rotor's wake on every
         other disk: skewed vortex-cylinder wakes (entry 07), dP_i = T_i v_i0 sum_j mean(w_ij) / w0. Arm cross-flow drag and
         (y6) mast drag are added; the rest of the airframe drag is in the common trim.
Mass (relative to the tri): motors, ESCs, blades, hubs, tilt servo as in entries 01-08; arms sized as carbon tubes
(arm_tube below); y6 masts 0.51 kg/m; everything else (fuselage, gear, payload mount, avionics) common.

ARM TUBE (thin-walled carbon tube, cantilever from the fuselage edge to the hub):
  strength: M = T_max L (T_max = tw_target x T_hover), sigma = M (d/2) / I <= SIGMA_ALLOW,  I = pi d^3 t / 8
  stiffness: tip deflection under hover thrust T_h L^3 / (3 E I) <= DEFL_FRAC x L
  wall t >= T_MIN and d / t <= D_OVER_T_MAX (local buckling), d <= D_MAX; pick the lightest d
  mass = rho pi d t L + FITTING_KG (hinge, clamps, motor mount)
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
from config_study import load_final_blade, mission_pack
from blade_structure import blade_mass
import e01_coax_blade as e01
import e02_coax_two_point as e02
import e07_cruise_wake as e7
from e06_coax_spacing import blade_e03
from common import RESULTS, save_json

OUT = os.path.join(RESULTS, "explore")
R = e7.R; D = 2 * R
CLEAR = 1.10; FUSE_R = 0.25            # assumption: arms start at a 0.25 m fuselage radius
RHO_C, E_TUBE, SIGMA_ALLOW = 1550.0, 70e9, 300e6     # quasi-isotropic carbon tube, allowable with margin
DEFL_FRAC, T_MIN, D_OVER_T_MAX, D_MAX, FITTING_KG = 0.01, 0.001, 50.0, 0.080, 0.6
MAST_KG_PER_M, MAST_OD, CD_TUBE, ETA = 0.51, 0.040, 1.2, 0.8
H_Y6 = 0.4


def arm_tube(T_h, T_max, L):
    best = None
    for d in np.arange(0.020, D_MAX + 1e-9, 0.002):
        I_stiff = T_h * L ** 3 / (3 * E_TUBE * DEFL_FRAC * L)
        I_str = T_max * L * (d / 2) / SIGMA_ALLOW
        t = max(T_MIN, 8 * max(I_stiff, I_str) / (math.pi * d ** 3), d / D_OVER_T_MAX)
        m = RHO_C * math.pi * d * t * L
        if best is None or m < best["tube_kg"]:
            best = {"d_mm": 1000 * d, "t_mm": 1000 * t, "tube_kg": m, "driver": "stiffness" if I_stiff >= I_str else "strength",
                    "wall_rule": "min wall" if t == T_MIN else ("d/t" if t == d / D_OVER_T_MAX else "load")}
    best["kg"] = best["tube_kg"] + FITTING_KG; best["L_m"] = L
    return best


def layouts():
    rt, rh = CLEAR * D / math.sqrt(3), CLEAR * D
    tri = [(rt * math.cos(math.radians(a)), rt * math.sin(math.radians(a)), 0.0) for a in (180, 300, 60)]
    y6 = [p for (x, y, _) in tri for p in ((x, y, 0.0), (x, y, -H_Y6 * D))]
    hex0 = [(rh * math.cos(math.radians(a)), rh * math.sin(math.radians(a)), 0.0) for a in range(0, 360, 60)]
    hex30 = [(rh * math.cos(math.radians(a)), rh * math.sin(math.radians(a)), 0.0) for a in range(30, 390, 60)]
    return {"tri": tri, "y6": y6, "hex0": hex0, "hex30": hex30}, rt, rh


def pair(args):
    """Mean normal velocity on disk i from rotor j's wake, per unit of j's own hub induced velocity."""
    cfg, i, j, chi, pi_, pj = args
    a, b, g = e7.rings(chi, 0.0); w0 = float(e7.down(e7.biot_savart(a, b, g, np.array([[0, 0, -1e-4 * R]])))[0])
    off = np.array(pj); a, b = a + off, b + off
    x, wgt, _, _ = e7.disk_points(0.0); x = x + np.array(pi_)
    return cfg, i, j, float(np.sum(e7.down(e7.biot_savart(a, b, g, x)) * wgt)) / w0


def run():
    t0 = time.time()
    e01.init(); G = e01.G; p, ph1, db, hot = G["p"], G["ph1"], G["db"], G["hot"]
    ctx = e02.context(); whkg = p["mass"]["pack_wh_per_kg_cited"]; V = p["mission"]["cruise_speed_ms"]
    W = ph1["vehicle"]["weight_n"]; tw = p["vehicle"]["tw_target"]; q = 0.5 * hot["rho"] * V * V
    bb = load_final_blade(p); b3 = blade_e03(p)
    # cruise operating points
    e_tri = bemt.edgewise_at_thrust(bb, db, hot, ctx["t_tot"] / 3, V, ctx["alpha"], kappa=p["rotor"]["kappa"])
    e_six = bemt.edgewise_at_thrust(b3, db, hot, ctx["t_tot"] / 6, V, ctx["alpha"], kappa=p["rotor"]["kappa"])
    def op(e, b):
        om = e["rpm"] * 2 * math.pi / 60; lam = e["lam0"] + V * math.sin(ctx["alpha"]) / (om * b.R)
        return {"T": e["T"], "vi0": e["lam0"] * om * b.R, "chi": math.atan2(e["mu"], lam), "P": e["P"]}
    o_tri, o_six = op(e_tri, bb), op(e_six, b3)
    lay, rt, rh = layouts()
    chis = {"tri": o_tri["chi"], "y6": o_six["chi"], "hex0": o_six["chi"], "hex30": o_six["chi"]}
    tasks = [(c, i, j, chis[c], pos[i], pos[j]) for c, pos in lay.items() for i in range(len(pos)) for j in range(len(pos)) if i != j]
    with Pool(4) as pool:
        res = pool.map(pair, tasks)
    M = {c: np.zeros((len(pos), len(pos))) for c, pos in lay.items()}
    for c, i, j, m in res: M[c][i, j] = m
    # hover
    iso6 = bemt.hover_at_thrust(b3, db, hot, W / 6)
    r6 = next(r for r in json.load(open(os.path.join(OUT, "e06_coax_spacing.json")))["rows"] if r.get("h_over_D") == H_Y6)
    hover = {"tri": ctx["base_hover"], "y6": r6["hover_w"], "hex0": 6 * iso6["P"], "hex30": 6 * iso6["P"]}
    # arms
    arm_tri = arm_tube(W / 3, tw * W / 3, rt - FUSE_R); arm_hex = arm_tube(W / 6, tw * W / 6, rh - FUSE_R)
    arms = {"tri": (3, arm_tri), "y6": (3, arm_tri), "hex0": (6, arm_hex), "hex30": (6, arm_hex)}
    mb = blade_mass(b3.r_def, b3.c_def, b3.tc_def, b3.r_hub, b3.R)["total_kg"]
    rotor_hw_six = 3 * (ctx["motors_pair"] + 4 * mb + 2 * ctx["hub"]) - 3 * ctx["arm_single"] - ctx["tilt"]
    out = {"configs": {}, "arm_tri": arm_tri, "arm_hex": arm_hex, "op_tri": o_tri, "op_six": o_six, "iso6_hover_w": iso6["P"]}
    for c, pos in lay.items():
        o = o_tri if c == "tri" else o_six
        n = len(pos)
        inter = float(sum(o["T"] * o["vi0"] * M[c][i, j] for i in range(n) for j in range(n) if i != j))
        na, arm = arms[c]
        # arm cross-flow drag: q Cd d L sin^2(angle to the flight path), flight along -x
        arm_drag = sum(q * CD_TUBE * arm["d_mm"] / 1000 * arm["L_m"] * (y * y / (x * x + y * y)) for (x, y, z) in pos if z == 0.0) * V / ETA
        mast = 3 * q * CD_TUBE * MAST_OD * H_Y6 * D * V / ETA if c == "y6" else 0.0
        rotors = e_tri["P"] * 3 if c == "tri" else 6 * e_six["P"]
        base_cruise = rotors
        cruise = base_cruise + inter + arm_drag + mast
        hov = hover[c]
        pack = mission_pack(p, ph1, hov, ctx["base_climb"] * hov / ctx["base_hover"], cruise)[0]
        hw = 0.0 if c == "tri" else rotor_hw_six
        hw += na * arm["kg"] - 3 * arm_tri["kg"] + (3 * MAST_KG_PER_M * H_Y6 * D if c == "y6" else 0.0)
        out["configs"][c] = {"positions": pos, "hover_w": hov, "cruise_w": cruise, "cruise_rotors_w": base_cruise, "interference_w": inter,
                             "arm_drag_w": arm_drag, "mast_drag_w": mast, "pack_wh": pack, "hardware_vs_tri_kg": hw,
                             "payload_vs_tri_kg": -(hw + (pack - ctx["base_pack"]) / whkg), "pair_matrix": M[c].tolist(),
                             "span_m": 2 * (rt if c in ("tri", "y6") else rh) + D}
    tri_noint = mission_pack(p, ph1, hover["tri"], ctx["base_climb"], 3 * e_tri["P"])[0]
    out["regression"] = {"tri_pack_rotors_only": tri_noint, "y6_within_arm_lower": M["y6"][1, 0], "y6_within_arm_upper": M["y6"][0, 1], "e07_h04": [0.294, 0.291],
                         "tri_pack_no_interference": ctx["base_pack"]}
    out["runtime_s"] = time.time() - t0
    for c, r in out["configs"].items():
        print(f"  {c:5s}: hover {r['hover_w']:.0f} W, cruise {r['cruise_w']:.0f} W (interference {r['interference_w']:.0f}, arms {r['arm_drag_w']:.0f}, mast {r['mast_drag_w']:.0f}),"
              f" pack {r['pack_wh']:.0f} Wh, hardware {r['hardware_vs_tri_kg']:+.2f} kg, payload {r['payload_vs_tri_kg']:+.2f} kg, span {r['span_m']:.2f} m", flush=True)
    print(f"  arms: tri {arm_tri}\n        hex {arm_hex}")
    print(f"  regression y6 within-arm m: lower {M['y6'][1,0]:.3f}, upper {M['y6'][0,1]:.3f} (e07 at h/D 0.4: 0.294, 0.291); tri pack without interference {out['regression']['tri_pack_rotors_only']:.0f} vs Phase 2 {ctx['base_pack']:.0f}")
    save_json(os.path.join("explore", "e09_hex_vs_y6.json"), out)
    plot(out)
    print(f"  wrote results/explore/e09_hex_vs_y6.json in {out['runtime_s']:.0f} s")


def plot(o):
    fig, axs = plt.subplots(1, 3, figsize=(12, 3.6))
    cs = list(o["configs"]); col = {"tri": "#999999", "y6": "#0b0b0b", "hex0": "#2a78d6", "hex30": "#c0392b"}
    # layout sketch (the tri uses the y6 hub positions)
    for c, dx in (("y6", -2.4), ("hex0", 0.9), ("hex30", 4.6)):
        for (x, y, z) in o["configs"][c]["positions"]:
            axs[0].add_patch(plt.Circle((y + dx, -x), R, fill=False, ec=col[c], ls="-" if z == 0 else "--"))
            axs[0].plot([dx, y + dx], [0, -x], color="#bbb", lw=.8)
        axs[0].text(dx, -2.3, c, ha="center", fontsize=8)
    axs[0].set_aspect("equal"); axs[0].set_xlim(-4.6, 6.9); axs[0].set_ylim(-2.6, 2.4); axs[0].set_title("layouts (flight ↑; dashed: lower rotor)", fontsize=8); axs[0].axis("off")
    x = np.arange(len(cs))
    axs[1].bar(x - 0.2, [o["configs"][c]["hover_w"] / 1000 for c in cs], 0.4, color="#2a78d6", label="hover [kW]")
    axs[1].bar(x + 0.2, [o["configs"][c]["cruise_w"] / 1000 for c in cs], 0.4, color="#c0392b", label="cruise [kW]")
    axs[1].bar(x + 0.2, [o["configs"][c]["interference_w"] / 1000 for c in cs], 0.4, color="#0b0b0b", alpha=.35, label="of which interference")
    axs[1].set_xticks(x); axs[1].set_xticklabels(cs); axs[1].legend(fontsize=7); axs[1].grid(alpha=.3, axis="y")
    axs[2].bar(x - 0.2, [o["configs"][c]["pack_wh"] / 1000 for c in cs], 0.4, color="#0b0b0b", label="pack [kWh]")
    ax2 = axs[2].twinx(); ax2.bar(x + 0.2, [o["configs"][c]["payload_vs_tri_kg"] for c in cs], 0.4, color="#e08e0b", label="payload vs tri [kg]")
    ax2.axhline(0, color="#999", lw=.8); axs[2].set_xticks(x); axs[2].set_xticklabels(cs)
    axs[2].set_ylabel("pack [kWh]"); ax2.set_ylabel("payload vs tri [kg]", color="#e08e0b")
    fig.suptitle("Exploration 09: tricopter vs Y6 (h/D 0.4) vs planar hexacopter, sized arms, vortex-wake cruise interference", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "e09_hex_vs_y6.png"), dpi=140); plt.close(fig)


if __name__ == "__main__":
    if sys.argv[1:] == ["plot"]:
        plot(json.load(open(os.path.join(OUT, "e09_hex_vs_y6.json"))))
    else:
        run()

"""Exploration 08: stagger - the lower rotor moved forward (along the flight path) of the upper on a tilted mast.

Geometry (shaft frame, x aft, z up): upper disk centred at the origin, lower disk centred at (-s, 0, -h). s > 0 is forward
stagger. The mast runs between the two hubs, length L = sqrt(h^2 + s^2), tilted atan(s / h) forward.

Cruise: entry 07's skewed vortex-cylinder wakes (Biot-Savart), the lower wake now starting at (-s, 0, -h). The interference
power per arm is T (mean w on lower + mean w on upper), as in entry 07.
Hover: the wakes are vertical, so stagger moves part of the lower disk out of the upper wake. Entry 06's two-region momentum
model (optimal lower loading) with the overlap made geometric:
    core area A_w = intersection of the wake circle (radius r_w = R / sqrt(1 + k), centred under the upper hub) with the
                    lower disk (centre distance s)
    the lower rotor's inflow felt by the upper is (1 - k) vbar_l times phi = (overlap of the two disks) / A
Its kappa(s) / kappa(0) scales the BEMT induced power at s = 0 (entry 06), so s = 0 reproduces entry 07 exactly.
Mast: mass 0.51 kg/m x L per arm. Drag by the cross-flow principle: only the velocity component normal to the mast loads it,
    D = q Cd d L sin^2(angle to the flow) = q Cd d L (h / L)^2 = q Cd d h^2 / L
so tilting the mast forward makes it slightly cheaper in drag.

Hand check (e08 hand section): the Trefftz-plane view of Munk's stagger theorem. Far downstream only the wakes' positions in a
plane normal to the wake axis e matter, so the effective biplane gap is the separation normal to e:
    G_eff = h sin(chi) + s cos(chi)
and Prandtl's sigma(G_eff / b) should track the vortex-wake sigma as s changes.
"""
import json, math, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from multiprocessing import Pool
from scipy.optimize import fsolve
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from config_study import mission_pack
import e01_coax_blade as e01
import e02_coax_two_point as e02
import e07_cruise_wake as e7
from common import RESULTS, save_json

OUT = os.path.join(RESULTS, "explore")
R = e7.R
HD = [0.2, 0.3, 0.4]
S_R = [-0.5, 0.0, 0.25, 0.5, 0.75, 1.0, 1.5]
MAST_KG_PER_M, MAST_OD, MAST_CD, ETA = 0.51, 0.040, 1.2, 0.8


def lens2(r1, r2, d):
    """Intersection area of circles of radii r1, r2 with centres d apart."""
    d = abs(d)
    if d >= r1 + r2: return 0.0
    if d <= abs(r1 - r2): return math.pi * min(r1, r2) ** 2
    a1 = math.acos((d * d + r1 * r1 - r2 * r2) / (2 * d * r1)); a2 = math.acos((d * d + r2 * r2 - r1 * r1) / (2 * d * r2))
    return r1 * r1 * a1 + r2 * r2 * a2 - 0.5 * math.sqrt((-d + r1 + r2) * (d + r1 - r2) * (d - r1 + r2) * (d + r1 + r2))


def kappa_hover(k, s, split):
    """Two-region momentum (optimal lower loading) with geometric overlaps. T = 1, rho = 1, R = 1 (kappa is scale-free)."""
    A = math.pi; Tu, Tl = split, 1 - split; rw = 1 / math.sqrt(1 + k)
    Aw = lens2(rw, 1.0, s); phi = lens2(1.0, 1.0, s) / A; v0 = math.sqrt(1 / (2 * A))

    def eqs(x):
        vu, vc, va = x
        w = (1 + k) * vu; vbar = (Aw * vc + (A - Aw) * va) / A
        e1 = 2 * A * vu * (vu + (1 - k) * vbar * phi) - Tu
        e2 = 2 * (Aw * (w + vc) * vc + (A - Aw) * va ** 2) - Tl
        e3 = ((w + vc) * (w + 3 * vc) / (w + 2 * vc) - 1.5 * va) if Aw > 1e-9 else (vc - va)
        return [e1, e2, e3 / v0]
    vu, vc, va = fsolve(eqs, [0.6 * v0, 0.4 * v0, 0.6 * v0], xtol=1e-12)
    w = (1 + k) * vu; vbar = (Aw * vc + (A - Aw) * va) / A
    P = Tu * (vu + (1 - k) * vbar * phi) + 2 * (Aw * (w + vc) ** 2 * vc + (A - Aw) * va ** 3)
    return P / (2 * 0.5 ** 1.5 / math.sqrt(2 * A))


def cruise_interference(chi, h, s, w0):
    au, bu, gu = e7.rings(chi, 0.0)
    off = np.array([-s, 0.0, 0.0])
    al, bl, gl = e7.rings(chi, -h); al, bl = al + off, bl + off
    xl, wl, _, _ = e7.disk_points(-h); xl = xl + off
    xu, wu, _, _ = e7.disk_points(0.0)
    m_l = float(np.sum(e7.down(e7.biot_savart(au, bu, gu, xl)) * wl)) / w0
    m_u = float(np.sum(e7.down(e7.biot_savart(al, bl, gl, xu)) * wu)) / w0
    return m_l, m_u


def case(arg):
    hd, sr = arg
    G = e01.G; p, ph1, hot = G["p"], G["ph1"], G["hot"]; ctx = e02.context(); whkg = p["mass"]["pack_wh_per_kg_cited"]
    r6 = next(r for r in json.load(open(os.path.join(OUT, "e06_coax_spacing.json")))["rows"] if r.get("h_over_D") == hd)
    chi = math.atan2(r6["mu"], r6["lam"]); h = r6["h_m"]; s = sr * R; L = math.hypot(h, s)
    a, b, g = e7.rings(chi); w0 = float(e7.down(e7.biot_savart(a, b, g, np.array([[0, 0, -1e-4 * R]])))[0])
    T_rot = ctx["t_tot"] / 6; vi0 = r6["p_ind_rotor_cruise"] / T_rot
    m_l, m_u = cruise_interference(chi, h, s, w0)
    pen = 3 * T_rot * vi0 * (m_l + m_u)
    q = 0.5 * hot["rho"] * p["mission"]["cruise_speed_ms"] ** 2
    mast_drag = 3 * q * MAST_CD * MAST_OD * h * h / L * p["mission"]["cruise_speed_ms"] / ETA
    cruise = r6["cruise_rotors_w"] - r6["overlap_penalty_w"] + pen + mast_drag
    k = r6["k"]
    kap0, kap = kappa_hover(k, 0.0, r6["split_upper"]), kappa_hover(k, s / R, r6["split_upper"])
    hover = r6["hover_w"] - 3 * r6["P_ind_pair_arm"] * (1 - kap / kap0)
    pack = mission_pack(p, ph1, hover, ctx["base_climb"] * hover / ctx["base_hover"], cruise)[0]
    payload = r6["payload_kg"] - (pack - r6["pack_wh"]) / whkg - 3 * MAST_KG_PER_M * (L - h)
    return {"h_over_D": hd, "s_over_R": sr, "mast_len_m": L, "mast_tilt_deg": math.degrees(math.atan2(s, h)), "chi_deg": math.degrees(chi),
            "m_lower": m_l, "m_upper": m_u, "sigma_bs": (m_l + m_u) / 2, "cruise_penalty_w": pen, "mast_drag_w": mast_drag, "cruise_w": cruise,
            "kappa_hover_mom": kap, "kappa_hover_mom_s0": kap0, "hover_w": hover, "pack_wh": pack, "payload_kg": payload}


def run():
    t0 = time.time()
    grid = [(hd, sr) for hd in HD for sr in S_R]
    with Pool(4, initializer=e01.init) as pool:
        rows = pool.map(case, grid)
    e7rows = {r["h_over_D"]: r for r in json.load(open(os.path.join(OUT, "e07_cruise_wake.json")))["rows"]}
    for r in rows:
        tag = f"  (e07: {e7rows[r['h_over_D']]['pack_bs_wh']:.0f})" if r["s_over_R"] == 0 else ""
        print(f"  h/D {r['h_over_D']:.1f} s/R {r['s_over_R']:+.2f} (mast {100*r['mast_len_m']:.0f} cm, {r['mast_tilt_deg']:+.0f} deg): sigma {r['sigma_bs']:.3f}"
              f" (lower {r['m_lower']:.3f}, upper {r['m_upper']:.3f}), cruise {r['cruise_w']:.0f} W, kappa {r['kappa_hover_mom']:.3f}, hover {r['hover_w']:.0f} W,"
              f" pack {r['pack_wh']:.0f} Wh{tag}, payload {r['payload_kg']:+.2f} kg", flush=True)
    out = {"rows": rows, "runtime_s": time.time() - t0}
    save_json(os.path.join("explore", "e08_stagger.json"), out)
    plot(rows)
    print(f"  wrote results/explore/e08_stagger.json in {out['runtime_s']:.0f} s")


def plot(rows):
    fig, axs = plt.subplots(1, 3, figsize=(12, 3.3)); cols = {0.2: "#2a78d6", 0.3: "#0b0b0b", 0.4: "#c0392b"}
    for hd in HD:
        rr = [r for r in rows if r["h_over_D"] == hd]; s = [r["s_over_R"] for r in rr]
        axs[0].plot(s, [r["sigma_bs"] for r in rr], "o-", color=cols[hd], label=f"h/D {hd}")
        axs[1].plot(s, [r["kappa_hover_mom"] / r["kappa_hover_mom_s0"] for r in rr], "o-", color=cols[hd], label=f"h/D {hd}")
        axs[2].plot(s, [r["pack_wh"] for r in rr], "o-", color=cols[hd], label=f"h/D {hd}")
    hp = os.path.join(OUT, "e08_hand_check.json")
    if os.path.exists(hp):
        for q in json.load(open(hp))["curves"]:
            axs[0].plot(q["s_over_R"], q["sigma_prandtl_Geff"], ":", color=cols[q["h_over_D"]])
    axs[0].set_xlabel("stagger s / R (forward +)"); axs[0].set_ylabel("cruise interference σ (dotted: Prandtl at G_eff)"); axs[0].legend(fontsize=7); axs[0].grid(alpha=.3)
    axs[1].set_xlabel("stagger s / R"); axs[1].set_ylabel("hover κ / κ(s = 0), momentum"); axs[1].grid(alpha=.3)
    axs[2].axhline(7475, color="#999", ls="--", lw=.8); axs[2].text(S_R[0], 7475, "tricopter", fontsize=6, va="bottom")
    axs[2].set_xlabel("stagger s / R"); axs[2].set_ylabel("pack energy [Wh]"); axs[2].legend(fontsize=7); axs[2].grid(alpha=.3)
    fig.suptitle("Exploration 08: stagger - lower rotor forward of the upper on a tilted mast", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "e08_stagger.png"), dpi=140); plt.close(fig)


if __name__ == "__main__":
    if sys.argv[1:] == ["plot"]:
        plot(json.load(open(os.path.join(OUT, "e08_stagger.json")))["rows"])
    else:
        run()

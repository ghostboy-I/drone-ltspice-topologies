"""Selected design -> results/final.json (everything the design doc prints) + figures + hand checks of the FE model.

Hand checks (the FE model must agree with a free-body diagram before its margins are trusted):
  H1  wing root bending, hover pull-up LC1. Free body of the half wing + pod + head outboard of the root:
          M_root = T_front y_hub - n_eff g sum(m_i y_i)
      n_eff = (sum of thrusts) / W is the vertical load factor (inertia relief: every mass carries -m n g).
  H2  wing root bending, airplane gust LC5: the elliptic lift on a half wing has its centroid at 4/(3 pi) (b/2), so
          M_root = (L_w / 2) (4 / 3 pi)(b / 2) - n g sum(m_i y_i)      (discrete lumping changes the 4/3pi slightly)
  H3  wing-box bending stiffness, parallel-axis theorem on caps and webs:
          EI = 2 E_f t_f w (h/2)^2 + 2 E_w t_w h^3 / 12     (flanges width w, webs height h, membrane thicknesses t)
"""
import json, math, os, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from tiltcfg import ROOT, RESULTS, jload, params, G0
import tiltframe as tf
import materials as mat

INK, INK2, ACC, ACC2, WARN = "#0b0b0b", "#52514e", "#2a78d6", "#e08a2c", "#c23b3b"


def nodal_mass_z(M):
    ones = np.zeros(M.ndof); ones[2::6] = 1.0
    return (M.M @ ones)[2::6]


def wing_root_moment(M, info, u):
    """Internal bending moment (about the wing's chordwise axis) in the element just outboard of the root, +y side."""
    c = info["wing_nodes"][len(info["wing_nodes"]) // 2]
    for e, fe in zip(M.elems, M.element_forces(u)):
        if e["group"] == "wing" and e["n1"] == c:
            return fe[0], e
    raise RuntimeError("root element not found")


def outboard_moment(M, info, y0):
    """sum m_i y_i over the wing / pod / head nodes outboard of y0 on the +y side (gear excluded)."""
    mz = nodal_mass_z(M)
    gear = set(info["contacts"].values())
    s = 0.0; m_ = 0.0
    for i, x in enumerate(M.X):
        if x[1] > y0 + 1e-6 and i not in gear and abs(x[1]) > 0.0 and x[2] > info["z_floor"]:
            s += mz[i] * (x[1] - y0); m_ += mz[i]
    return s, m_


def hand_checks(ctx, r):
    out = {}
    M, info = r["_models"]["hover"]
    F = tf.hover_loads(M, info, ctx, np.array(r["thrust_LC1"]))
    u, _, _ = M.static_inertia_relief(F, hold_node=M.tags["centre"])
    fe, el = wing_root_moment(M, info, u)
    y0 = M.X[el["n1"]][1]
    W = M.total_mass() * G0
    n_eff = sum(r["thrust_LC1"]) / W
    smy, m_out = outboard_moment(M, info, y0)
    yh, yi = ctx["sz"]["layout"]["y_front_hub"], ctx["sz"]["layout"]["y_inboard_hub"]
    T_L, T_I = r["thrust_LC1"][0], r["thrust_LC1"][2]                 # rotor order: tip L, tip R, inboard L, inboard R, aft L, aft R
    M_hand = T_L * (yh - y0) + T_I * (yi - y0) - n_eff * G0 * smy
    M_fe = abs(fe[4])
    out["H1"] = {"T_front_n": T_L, "T_inboard_n": T_I, "y_hub": yh, "y_inboard": yi, "n_eff": n_eff, "m_outboard_kg": m_out, "sum_my": smy,
                 "M_hand_nm": M_hand, "M_fe_nm": M_fe, "diff_pct": 100 * (M_fe / M_hand - 1)}
    Ma, infa = r["_models"]["airplane"]
    n_air = ctx["sz"]["gust"]["n_design_airplane"]
    Fa, trim = tf.airplane_loads(Ma, infa, ctx, n_air)
    ua, _, _ = Ma.static_inertia_relief(Fa, hold_node=Ma.tags["centre"])
    fea, ela = wing_root_moment(Ma, infa, ua)
    y0a = Ma.X[ela["n1"]][1]
    b = ctx["sz"]["wing"]["b"]
    ys = np.array(infa["wing_y"]); wt = np.sqrt(np.clip(1 - (2 * ys / b) ** 2, 0, None))
    trib = np.zeros_like(ys); dy = np.diff(ys); trib[:-1] += dy / 2; trib[1:] += dy / 2
    wt = wt * trib; wt /= wt.sum()
    ybar_lumped = float(np.sum(wt[ys > y0a] * (ys[ys > y0a] - y0a)) / np.sum(wt[ys > y0a]))
    ybar_ell = 4 / (3 * math.pi) * (b / 2)
    Lhalf = trim["Lw"] * float(np.sum(wt[ys > y0a]))
    sma, ma_out = outboard_moment(Ma, infa, y0a)
    n_tot = (trim["Lw"] + trim["Lt"]) / (Ma.total_mass() * G0)
    Mh2 = Lhalf * ybar_ell - n_tot * G0 * sma
    out["H2"] = {"L_wing_n": trim["Lw"], "L_tail_n": trim["Lt"], "n": n_tot, "ybar_elliptic": ybar_ell, "ybar_lumped": ybar_lumped,
                 "M_hand_nm": Mh2, "M_hand_lumped_nm": Lhalf * ybar_lumped - n_tot * G0 * sma, "M_fe_nm": abs(fea[4]),
                 "diff_pct": 100 * (abs(fea[4]) / Mh2 - 1)}
    # H3 wing box EI
    d = r["design"]["wing"]; pm = ctx["pm"]
    sec = tf.wing_box(pm, ctx["sz"], d["n_ud_root"], d)
    side = mat.wall(pm, n_w45=d["n_w45"], core_t=d["core_mm"] * 1e-3)
    cap = mat.wall(pm, n_ud0=d["n_ud_root"], n_w45=d["n_w45"], core_t=d["core_mm"] * 1e-3)
    h, w = sec.depth, sec.width
    EI_hand = 2 * cap.Et * w * (h / 2) ** 2 + 2 * side.Et * h ** 3 / 12
    out["H3"] = {"depth_m": h, "width_m": w, "E_cap_gpa": cap.Ex / 1e9, "t_cap_mm": cap.t_mem * 1e3, "E_web_gpa": side.Ex / 1e9,
                 "EI_hand": EI_hand, "EI_section": sec.EIyy, "diff_pct": 100 * (sec.EIyy / EI_hand - 1),
                 "note": "the section integrates the flange through its own thickness and the corners; hand calc uses mid-planes"}
    return out


def figs(sz, r, final):
    # airfoil polars
    pol = jload(os.path.join(RESULTS, "wing_polars.json"))
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.8))
    re_key = f"{round(sz['wing_re'], -4):.0f}"
    for k, P in pol.items():
        P = np.array(P); parts = k.split("@"); name = parts[0]
        if len(P) < 5 or parts[1] != re_key: continue
        trip = len(parts) > 2
        sel = name == sz["wing"]["airfoil"]
        if trip and not sel: continue
        kw = dict(color=ACC if sel else "#9a9a9a", lw=2.2 if sel else 0.9, zorder=3 if sel else 1, ls="--" if trip else "-")
        ax[0].plot(P[:, 0], P[:, 1], **kw); ax[1].plot(P[:, 2], P[:, 1], **kw)
        if sel: ax[0].plot([], [], color=ACC, lw=2.2, ls=kw["ls"], label=f"{name} (selected){', tripped' if trip else ''}")
    ax[0].plot([], [], color="#9a9a9a", lw=0.9, label="other candidates")
    ax[0].axhline(sz["wing"]["CL_cruise"] / 1.0, color=ACC2, ls="--", lw=1); ax[0].text(-5.5, sz["wing"]["CL_cruise"] + 0.04, "cruise CL", color=ACC2, fontsize=8)
    ax[0].set_xlabel("alpha [deg]"); ax[0].set_ylabel("cl"); ax[0].legend(fontsize=8, frameon=False); ax[0].grid(alpha=0.25)
    ax[1].set_xlabel("cd"); ax[1].set_ylabel("cl"); ax[1].set_xlim(0, 0.03); ax[1].grid(alpha=0.25)
    fig.suptitle(f"XFOIL polars at Re {sz['wing_re']:.2e}, Ncrit 9, free transition; tripped 5/10 % dashed (hot day, 25 m/s, wing chord)", fontsize=10)
    fig.tight_layout(); fig.savefig(os.path.join(RESULTS, "fig_polars.png"), dpi=150); plt.close(fig)

    # download vs overlap, and prop thrust vs speed
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.6))
    sc = sz["download"]["scan"]
    ax[0].plot([s["overlap"] for s in sc], [100 * s["frac"] for s in sc], color=ACC, lw=2)
    ax[0].axhline(100 * params()["nacelle"]["download_max_frac"], color=WARN, ls="--", lw=1)
    ch = sz["download"]["chosen"]; ax[0].plot(ch["overlap"], 100 * ch["frac"], "o", color=INK)
    ax[0].annotate(f"chosen {ch['overlap']:.2f} R", (ch["overlap"], 100 * ch["frac"]), xytext=(10, 10), textcoords="offset points", fontsize=8)
    ax[0].set_xlabel("disk overlap inboard of the wing tip [R]  (1.0 = V-22, hub on the tip)"); ax[0].set_ylabel("wing download [% of rotor thrust]"); ax[0].grid(alpha=0.25)
    import hexrotor as hr, bemt
    HX = hr.setup(); rho = sz["air"]["rho"]
    V = np.linspace(0, 34, 60)
    for bn, col_, ls_ in (("hex", ACC, "-"), ("54x18", ACC, ":")):
        bb, dbb = hr.blade(bn)
        T = [4 * bemt.axial(bb, dbb, HX["air"], HX["rpm_max"], v)["T"] for v in V]
        ax[1].plot(V, T, color=col_, lw=2, ls=ls_, label=f"4 tilting props at the motor limit, {bn} blade")
    Dv = [0.5 * rho * v * v * sz["drag"]["CDA_total_m2"] * 0 + 0.5 * rho * v * v * (sz["drag"]["CDA_total_m2"] - sz["drag"]["induced_m2"]) +
          (sz["W_n"] ** 2 / (0.5 * rho * v * v * sz["wing"]["S"] * math.pi * params()["wing"]["e_oswald"] * sz["wing"]["AR"]) if v > 15 else np.nan) for v in V]
    ax[1].plot(V, Dv, color=ACC2, lw=2, label="airplane-mode drag (wing-borne)")
    ax[1].axvline(sz["wing"]["v_stall_ms"], color=INK2, ls=":", lw=1); ax[1].text(sz["wing"]["v_stall_ms"] + 0.3, 1200, "stall", fontsize=8, color=INK2)
    ax[1].axvline(25, color=INK2, ls="--", lw=1)
    ax[1].set_ylim(0, 1800); ax[1].set_xlabel("airspeed [m/s]"); ax[1].set_ylabel("force [N]"); ax[1].legend(fontsize=8, frameon=False); ax[1].grid(alpha=0.25)
    fig.tight_layout(); fig.savefig(os.path.join(RESULTS, "fig_download_thrust.png"), dpi=150); plt.close(fig)

    # modes vs bands
    fig, ax = plt.subplots(figsize=(10, 3.2))
    yrow = {"hover": 1, "airplane": 0}
    for mode, b in r["bands"]["nominal"].items():
        y = yrow[mode]
        ax.axvspan(b[1][0], b[1][1], ymin=(y + 0.08) / 2, ymax=(y + 0.92) / 2, color=ACC2, alpha=0.25, lw=0)
        ax.axvspan(b[2][0], b[2][1], ymin=(y + 0.08) / 2, ymax=(y + 0.92) / 2, color=ACC, alpha=0.20, lw=0)
    env = r["bands"]["envelope"]
    ax.axvspan(min(v[0] for v in env.values()), max(v[1] for v in env.values()), ymin=0.96, ymax=1.0, color=WARN, alpha=0.5, lw=0)
    for mode, mo in r["modes"].items():
        y = yrow[mode] + 0.5
        for f, pa, pi in zip(mo["hz"], mo["p_axial"], mo["p_inplane"]):
            if max(pa, pi) < 0.05: ax.plot(f, y, "|", color="#b0b0b0", ms=10)
            else: ax.plot(f, y, "o", color=ACC if pa >= pi else ACC2, ms=4 + 10 * min(max(pa, pi), 1))
    ax.set_yticks([0.5, 1.5]); ax.set_yticklabels(["airplane", "hover"]); ax.set_ylim(0, 2); ax.set_xlim(0, 90)
    ax.set_xlabel("frequency [Hz]   (bands: orange 1P in-plane, blue 2P axial, +-15 %; red strip = Airframe/01 envelope)")
    ax.set_title("Free-free modes; dots move a hub (size = participation; blue axial, orange in-plane), grey ticks do not", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(RESULTS, "fig_modes.png"), dpi=150); plt.close(fig)

    # mass breakdown vs budget
    fig, ax = plt.subplots(figsize=(10, 2.6))
    parts = final["vehicle_mass"]
    x0 = 0
    cols = ["#2a78d6", "#5b9be0", "#8fb9ea", "#e08a2c", "#efb06b", "#7d8590", "#b5bac0"]
    for (k, v), c_ in zip(parts.items(), cols):
        ax.barh(0, v, left=x0, color=c_, edgecolor="white"); ax.text(x0 + v / 2, 0, f"{k}\n{v:.1f}", ha="center", va="center", fontsize=7.5, color="white" if v > 12 else INK)
        x0 += v
    mt = final["mtow_kg"]
    ax.axvline(mt, color=WARN, lw=2); ax.text(mt, 0.5, f"280 lb MTOW {mt:.0f} kg", color=WARN, fontsize=8, ha="center")
    ax.set_ylim(-0.6, 0.7); ax.set_yticks([]); ax.set_xlabel("kg"); ax.set_title("Vehicle mass build-up (selected design) against the 280 lb MTOW", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(RESULTS, "fig_mass.png"), dpi=150); plt.close(fig)


def main():
    ctx = tf.context()
    d = json.load(open(os.path.join(ROOT, "designs", "selected.json")))
    r = tf.run(ctx, d)
    print(tf.summary(r))
    sz = ctx["sz"]; a1 = ctx["a1"]; ms = ctx["hm"]; p = ctx["p"]
    tip = ms["motor_kg"] + ms["esc_kg"] + 2 * ms["blade_kg"] + ms["hub_kg"] + ms["motor_mount_kg"]
    nac = p["nacelle"]
    tilt_hw = 4 * (nac["tilt_actuator_kg"] + nac["pivot_bearing_kg"] + nac["head_fairing_kg"])
    vm = {"payload": ms["payload_kg"], "battery": p["masses"]["battery_kg"], "airframe": r["mass_airframe_kg"],
          "propulsion (6 rotors)": 6 * tip, "tilt hardware": tilt_hw, "avionics": p["masses"]["avionics_kg"]}
    hc = hand_checks(ctx, r)
    mt = p["vehicle"]["mtow_lb"] * 0.45359237
    drone = sum(v for k, v in vm.items() if k != "payload")
    final = {"design": r["design"], "verdict": r["verdict"], "reasons": r["reasons"], "flags": r.get("modes_flags", []),
             "worst": r["worst"], "cases": r["cases"], "landing": r["landing"], "modes": r["modes"], "bands": r["bands"],
             "mass_breakdown": r["mass_breakdown"], "mass_airframe_kg": r["mass_airframe_kg"], "mass_model_kg": r["mass_total_kg"],
             "vehicle_mass": vm, "drone_kg": drone, "drone_budget_kg": p["vehicle"]["drone_lb"] * 0.45359237, "mtow_kg": mt,
             "x_payload": r["x_payload"], "cg_hover": r["cg_hover"], "cg_airplane": r["cg_airplane"],
             "thrust_LC1": r["thrust_LC1"], "thrust_LC2": r["thrust_LC2"], "airplane_trim": r["airplane_trim"],
             "hand_checks": hc, "tip_mass_kg": tip, "pod_D_m": nac["pod_diameter_m"],
             "stall_at_model_mass_ms": sz["wing"]["v_stall_ms"] * math.sqrt(r["mass_total_kg"] / mt),
             "wing_area_for_model_mass_m2": sz["wing"]["S"] * r["mass_total_kg"] / mt,
             "hover_thrust_per_rotor_model_n": r["mass_total_kg"] * G0 / 6}
    sw, sr = os.path.join(RESULTS, "sweep.json"), os.path.join(RESULTS, "sweep_random.json")
    if os.path.exists(sw) and os.path.exists(sr):          # random sweep, then a local refinement around its best
        A, B = jload(sr), jload(sw)
        final["sweep"] = {"n": A["n"] + B["n"], "n_pass": len(A["pass_masses"]) + len(B["pass_masses"]),
                          "random": {"n": A["n"], "n_pass": len(A["pass_masses"]), "fail_reasons": A["fail_reasons"]},
                          "refine": {"n": B["n"], "n_pass": len(B["pass_masses"]), "best_kg": min(B["pass_masses"]) if B["pass_masses"] else None}}
    with open(os.path.join(RESULTS, "final.json"), "w") as f: json.dump(final, f, indent=1, default=float)
    figs(sz, r, final)
    print(json.dumps(hc, indent=1))


if __name__ == "__main__":
    main()

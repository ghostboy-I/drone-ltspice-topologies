"""Exploration 14: faired arms and masts, with the hover download they cause.

Entry 09 charged every bare arm tube a cruise cross-flow drag q Cd d L sin^2(phi) (Cd 1.2) and ignored hover download.
A fairing cuts the cruise drag, but an arm sits in its own rotor's downwash in hover, and a fairing with its chord in the
flight plane is broadside to that downwash. This study prices both, per layout, using each layout's best blade so far
(entry 11 hex, entry 12 y6, entry 13 tri).

Drag in cruise (cross-flow principle): the flow component normal to the arm axis sets the section force,
    normal force per length = q Cd (V_n / V)^2 x width = q Cd w sin^2(phi);  its component along the flight path is x sin(phi)
    -> drag per length = q Cd w sin^3(phi)    (entry 09 used sin^2: a 13 % over-estimate on the oblique arms)
Section drag of a fairing (Hoerner's 2-D streamlined-section formula, turbulent skin friction, attached flow):
    Cd_c = 2 Cf [1 + 2 (t/c) + 60 (t/c)^4],  Cf = 0.074 Re_c^-0.2;   Cd_t = Cd_c c / t   (on thickness = tube diameter)
Download in hover: arm length under its own disk from the hub to 0.2 R (no wake inside the hub), at the wake speed a
    motor height Z_ARM below the disk, from the vortex-cylinder axial formula w(z) = v_i (1 + z / sqrt(R^2 + z^2)):
    D_dl = 0.5 rho w^2 Cd_n width l,  with the rotor thrust raised to T + D_dl: P ~ T^1.5 -> P' = P (1 + D_dl / T)^1.5
    bare tube Cd 1.2 on d;  fixed fairing broadside Cd 1.5 on the chord (sensitivity 1.2-2.0);  swivelling fairing Cd_t on d
Options per arm: 'bare'; 'full' (fixed fairing, chord in the flight plane, whole arm); 'outboard' (fixed fairing only on the
    part of the arm outside the rotor disk: cruise gain without download); 'swivel' (trailing fairing free to weathervane
    about the tube, like a towed-cable fairing: aligned with the downwash in hover and with the free stream in cruise).
Mass: fairing skin 0.35 kg/m2 x 1.15 (ribs, bond) over the wetted perimeter aft of the tube, 2c - 0.57 d; swivel adds two
    bearing collars per arm (0.05 kg).
Y6 masts are vertical: the downwash runs along them, so a fixed fairing has no download cost.
Fuselage download (tri and y6 only: their disks overlap a 0.25 m fuselage radius; the hex's do not) is reported but no
    fairing changes it.
"""
import json, math, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from config_study import mission_pack
import e01_coax_blade as e01
import e02_coax_two_point as e02
from e09_hex_vs_y6 import layouts, CD_TUBE, ETA, MAST_OD, H_Y6, FUSE_R, R, D
from common import RESULTS, save_json

OUT = os.path.join(RESULTS, "explore")
Z_ARM, HUB_FRAC = 0.12, 0.2
CD_BROAD, CD_BROAD_SENS = 1.5, (1.2, 2.0)
SKIN_KG_M2, SKIN_FACTOR, SWIVEL_KG = 0.35, 1.15, 0.05
CD_FUSE = 1.0
TC_OPTIONS = (0.25, 0.33, 0.5)
NU_HOT = 1.75e-5


def cd_t(tc, chord, V):
    re = V * chord / NU_HOT; cf = 0.074 * re ** -0.2
    return 2 * cf * (1 + 2 * tc + 60 * tc ** 4) / tc


def fairing_kg_per_m(d, tc):
    return SKIN_KG_M2 * SKIN_FACTOR * (2 * d / tc - 0.57 * d)


def lens(d, r1, r2):
    if d >= r1 + r2: return 0.0
    if d <= abs(r2 - r1): return math.pi * min(r1, r2) ** 2
    a1 = r1 * r1 * math.acos((d * d + r1 * r1 - r2 * r2) / (2 * d * r1)); a2 = r2 * r2 * math.acos((d * d + r2 * r2 - r1 * r1) / (2 * d * r2))
    return a1 + a2 - 0.5 * math.sqrt((-d + r1 + r2) * (d + r1 - r2) * (d - r1 + r2) * (d + r1 + r2))


def run():
    e01.init(); G = e01.G; p, ph1, hot = G["p"], G["ph1"], G["hot"]
    ctx = e02.context(); whkg = p["mass"]["pack_wh_per_kg_cited"]; V = p["mission"]["cruise_speed_ms"]; W = ph1["vehicle"]["weight_n"]
    rho = hot["rho"]; q = 0.5 * rho * V * V; A = math.pi * R * R
    e9 = json.load(open(os.path.join(OUT, "e09_hex_vs_y6.json")))
    e11 = json.load(open(os.path.join(OUT, "e11_blade_with_motor.json"))); e12 = json.load(open(os.path.join(OUT, "e12_y6_blade_with_motor.json")))
    e13 = json.load(open(os.path.join(OUT, "e13_tri_torque_margin.json")))
    hexb = max((r for r in e11["runs"] if r["mode"] == "motor"), key=lambda r: r["end"]["payload"])["end"]
    y6b = max(e12["runs"], key=lambda r: r["end_full"]["payload"])["end_full"]
    trib = max(e13["runs"], key=lambda r: r["end"]["dpayload"])["end"]
    best = {"tri": (trib["hover"], trib["cruise"], trib["pack"], 0.0),       # payload measured against this (entry 13's) tri
            "hex0": (hexb["hover"], hexb["cruise"], hexb["pack"], hexb["payload"] - trib["dpayload"]),
            "y6": (y6b["hover"], y6b["cruise"], y6b["pack"], y6b["payload"] - trib["dpayload"])}
    lay, rt, rh = layouts()
    arm = {"tri": e9["arm_tri"], "y6": e9["arm_tri"], "hex0": e9["arm_hex"]}
    n_rot = {"tri": 3, "y6": 6, "hex0": 6}
    out = {"configs": {}, "constants": {"q_cruise_pa": q, "rho": rho, "V": V}}
    for c in ("tri", "hex0", "y6"):
        hov0, cru0, pack0, pay0 = best[c]
        d = arm[c]["d_mm"] / 1000; L = arm[c]["L_m"]
        arms_xy = [(x, y) for (x, y, z) in lay[c] if z == 0.0]
        T_rot = W / 3 if c == "tri" else W / 6
        v_i = math.sqrt(T_rot / (2 * rho * A))
        w = v_i * (1 + Z_ARM / math.sqrt(R * R + Z_ARM ** 2))
        if c == "y6":       # arm under the upper rotor and in the lower rotor's inflow 0.4 D - Z_ARM above it
            zl = H_Y6 * D - Z_ARM; w += v_i * (1 - zl / math.sqrt(R * R + zl * zl))
        q_w = 0.5 * rho * w * w
        l_under = min(L, (1 - HUB_FRAC) * R); l_out = max(0.0, L - R)
        sin3 = sum((y * y / (x * x + y * y)) ** 1.5 for x, y in arms_xy); sin2 = sum(y * y / (x * x + y * y) for x, y in arms_xy)
        T_total = W                                      # hover: all rotors together carry W
        fuse = n_rot[c] // (2 if c == "y6" else 1) * lens(rt if c != "hex0" else rh, FUSE_R, R)
        D_fuse = q_w * CD_FUSE * fuse
        mast0 = 3 * q * CD_TUBE * MAST_OD * H_Y6 * D * V / ETA if c == "y6" else 0.0
        e9_terms = e9["configs"][c]["arm_drag_w"] + e9["configs"][c]["mast_drag_w"]
        rows = {}
        for opt in ("bare", "full", "outboard", "swivel"):
            for tc in (TC_OPTIONS if opt != "bare" else (None,)):
                chord = d / tc if tc else d
                cdt = cd_t(tc, chord, V) if tc else CD_TUBE
                if opt == "bare":   l_f, cd_cr_f, dl_f = 0.0, CD_TUBE, CD_TUBE * d
                # cruise: faired length at Cd_t, the rest bare; download per arm on the part under the disk
                if opt == "full":     l_f = L;     dl = CD_BROAD * chord * l_under
                elif opt == "outboard": l_f = l_out; dl = CD_TUBE * d * l_under
                elif opt == "swivel": l_f = L;     dl = cdt * d * l_under
                else:                 dl = CD_TUBE * d * l_under
                arm_w = q * d * (cdt * l_f + CD_TUBE * (L - l_f)) * sin3 * V / ETA
                mast_w = (3 * q * cdt * MAST_OD * H_Y6 * D * V / ETA if opt != "bare" else mast0) if c == "y6" else 0.0
                D_dl = len(arms_xy) * q_w * dl
                hover = hov0 * (1 + (D_dl + D_fuse) / T_total) ** 1.5
                cruise = cru0 - e9_terms + arm_w + mast_w
                pack = mission_pack(p, ph1, hover, ctx["base_climb"] * hover / ctx["base_hover"], cruise)[0]
                fair_kg = (len(arms_xy) * l_f * fairing_kg_per_m(d, tc) + (3 * H_Y6 * D * fairing_kg_per_m(MAST_OD, tc) if c == "y6" else 0.0)) if tc else 0.0
                fair_kg += len(arms_xy) * SWIVEL_KG if opt == "swivel" else 0.0
                payload = pay0 - fair_kg - (pack - pack0) / whkg
                key = opt if not tc else f"{opt} t/c {tc}"
                rows[key] = {"opt": opt, "tc": tc, "chord_m": chord, "cd_t": cdt, "arm_drag_w": arm_w, "mast_drag_w": mast_w, "download_n": D_dl,
                             "download_frac": D_dl / T_total, "hover_w": hover, "cruise_w": cruise, "pack_wh": pack, "fairing_kg": fair_kg, "payload_vs_tri_e13_kg": payload}
        # broadside-Cd sensitivity for the best 'full' fairing
        out["configs"][c] = {"rows": rows, "v_i": v_i, "w_arm": w, "q_w": q_w, "l_under": l_under, "l_out": l_out, "sin3_sum": sin3, "sin2_sum": sin2,
                             "fuse_overlap_m2": fuse, "fuse_download_n": D_fuse, "start": {"hover": hov0, "cruise": cru0, "pack": pack0, "payload": pay0},
                             "e09_arm_mast_w": e9_terms}
        print(f"  {c}: v_i {v_i:.2f}, w_arm {w:.2f} m/s, q_w {q_w:.1f} Pa, l_under {l_under:.3f} m, l_out {l_out:.3f} m, sin3 {sin3:.2f} (sin2 {sin2:.2f}),"
              f" fuselage overlap {fuse:.4f} m2 -> {D_fuse:.1f} N")
        for k, r in rows.items():
            print(f"     {k:18s} Cd_t {r['cd_t']:.3f}  arm {r['arm_drag_w']:6.0f} W  mast {r['mast_drag_w']:5.0f} W  download {r['download_n']:5.1f} N ({100*r['download_frac']:.2f} %)"
                  f"  hover {r['hover_w']:6.0f}  pack {r['pack_wh']:5.0f} Wh  fairing {r['fairing_kg']:.2f} kg  payload {r['payload_vs_tri_e13_kg']:+.2f} kg", flush=True)
    # Cd_broadside sensitivity of hex 'full t/c 0.33'
    sens = {}
    c = "hex0"; C = out["configs"][c]; r = C["rows"]["full t/c 0.33"]; hov0, cru0, pack0, pay0 = best[c]
    for cdb in CD_BROAD_SENS:
        D_dl = r["download_n"] * cdb / CD_BROAD; hover = hov0 * (1 + (D_dl + C["fuse_download_n"]) / W) ** 1.5
        pack = mission_pack(p, ph1, hover, ctx["base_climb"] * hover / ctx["base_hover"], r["cruise_w"])[0]
        sens[cdb] = pay0 - r["fairing_kg"] - (pack - pack0) / whkg
    out["hex_full_broadside_cd_sensitivity"] = sens
    # hand checks
    hx = out["configs"]["hex0"]; dh = e9["arm_hex"]["d_mm"] / 1000
    out["hand_check"] = {"e09_hex_arm_w": q * CD_TUBE * dh * e9["arm_hex"]["L_m"] * hx["sin2_sum"] * V / ETA,
                         "hex_bare_sin3_w": q * CD_TUBE * dh * e9["arm_hex"]["L_m"] * hx["sin3_sum"] * V / ETA,
                         "hex_v_i_momentum": math.sqrt(W / 6 / (2 * rho * A)),
                         "hex_bare_download_per_arm_n": hx["q_w"] * CD_TUBE * dh * hx["l_under"],
                         "cd_t_033_hex": cd_t(0.33, dh / 0.33, V), "re_033_hex": V * dh / 0.33 / NU_HOT}
    h0, c0 = best["hex0"][0], best["hex0"][1]; pk = lambda h, cr: mission_pack(p, ph1, h, ctx["base_climb"] * h / ctx["base_hover"], cr)[0]
    out["hand_check"]["wh_per_w_hover"] = (pk(h0 + 100, c0) - pk(h0, c0)) / 100
    out["hand_check"]["wh_per_w_cruise"] = (pk(h0, c0 + 100) - pk(h0, c0)) / 100
    bt = {c: min(C["rows"].values(), key=lambda r: -r["payload_vs_tri_e13_kg"]) for c, C in out["configs"].items()}
    out["best_option"] = {c: {"option": [k for k, v in out["configs"][c]["rows"].items() if v is r][0], "payload_vs_tri_e13_kg": r["payload_vs_tri_e13_kg"],
                              "payload_vs_best_tri_kg": r["payload_vs_tri_e13_kg"] - bt["tri"]["payload_vs_tri_e13_kg"], "pack_wh": r["pack_wh"]} for c, r in bt.items()}
    print(f"  best options: {out['best_option']}")
    print(f"  broadside-Cd sensitivity (hex full t/c 0.33): {sens}\n  hand: {out['hand_check']}")
    save_json(os.path.join("explore", "e14_faired_arms.json"), out); plot(out)


def plot(o):
    fig, ax = plt.subplots(figsize=(8, 3.4)); cols = {"tri": "#0b0b0b", "hex0": "#2a78d6", "y6": "#c0392b"}
    keys = list(o["configs"]["hex0"]["rows"].keys()); x = np.arange(len(keys))
    for i, (c, C) in enumerate(o["configs"].items()):
        ax.bar(x + (i - 1) * 0.27, [C["rows"][k]["payload_vs_tri_e13_kg"] for k in keys], 0.27, color=cols[c], label=c)
    ax.set_xticks(x); ax.set_xticklabels(keys, rotation=30, ha="right", fontsize=7); ax.axhline(0, color="#888", lw=0.8)
    ax.set_ylabel("payload vs re-optimised bare tri [kg]"); ax.legend(fontsize=7); ax.grid(axis="y", alpha=.3)
    ax.set_title("Exploration 14: arm/mast fairings with hover download", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "e14_faired_arms.png"), dpi=140); plt.close(fig)


if __name__ == "__main__":
    if sys.argv[1:] == ["plot"]:
        plot(json.load(open(os.path.join(OUT, "e14_faired_arms.json"))))
    else:
        run()

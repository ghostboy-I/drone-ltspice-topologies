"""Weight-first decision matrix across the rotor and vehicle options of the program.

    python3 src/matrix.py        # -> results/decision_matrix.json, results/fig_decision_matrix.png, DECISION_MATRIX.md

MASS is the 50 % criterion: the change in (propulsion + arms + fairing hardware) + (mission pack at 303 Wh/kg) against the
tricopter with 2-blade 54 in rotors, for the 10 nmi mission at 15 m/s on a hot day. It is READ from the result files of
the projects that computed it (Props/01 design-exploration entries, the diameter study, Airframe 01/02, this project's
CFD), in two bases where both exist:
    BEMT   entry 48: plain blade-element, catalogue motors with a 10 % torque reserve (tri on V13828, hex on MN1123)
    CFD    entry 44: the same chain with the 2-blade CFD's equal-thrust factors (rpm x1.156, torque x1.229, power x1.421)
The CFD factors came from the reference run on the coarse-nose mesh, which reads torque high (Caradonna-Tung: +17-28 %),
so the truth is expected between the two columns. Rows with only one basis carry it into both.

The toroid row is built here from the two CFD runs (same mesh, same rpm): at equal thrust the loop needs P_t/P_r = FoM_r/FoM_t
more power and Q_t/Q_r = (P_t/P_r)/sqrt(CT_r/CT_t) more torque, plus the flex-test blade mass from Props/01's spar model.

The other criteria are scored 0-10 in matrix_inputs.yaml with a reason for each score. Mass is scored linearly between the
lightest and heaviest feasible option; an infeasible option scores 0. Total = sum of weight x score.
"""
import json, math, os, sys
import numpy as np
import yaml

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); REPO = os.path.join(ROOT, "..", "..")
P01 = os.path.join(ROOT, "..", "01_54x18_Composite")
J = lambda *p: json.load(open(os.path.join(*p)))
RES = os.path.join(ROOT, "results")


def build(scen="15 m/s"):
    inp = yaml.safe_load(open(os.path.join(ROOT, "matrix_inputs.yaml")))
    p01 = yaml.safe_load(open(os.path.join(P01, "params.yaml")))
    e48 = J(P01, "results", "explore", "e48_chain_10pct.json")["ranking"][f"24xx | {scen} | 303"]
    e44 = J(P01, "results", "explore", "e44_cfd_factors.json")["ranking"][f"{scen} 303"]
    e49 = J(P01, "results", "explore", "e49_decision_curves.json")["y6"]
    e21 = J(P01, "results", "explore", "e21_three_blade.json")
    dia = J(P01, "results", "diameter_study.json")["diameters"]
    pts = J(P01, "results", "explore", "e48_chain_10pct.json")["points"]
    tri15 = next(q for q in pts if q["key"] == "tri 24xx" and q["V"] == 15.0)
    cr, cf = J(RES, "cfd_reference.json"), J(RES, "cfd_toroid.json")
    bsm = J(RES, "blade_structure_mass.json")
    a1, a2 = J(REPO, "Airframe", "01_Tricopter_Fuselage", "results", "final.json"), J(REPO, "Airframe", "02_Osprey_TiltTri", "results", "final.json")
    s2 = J(REPO, "Airframe", "02_Osprey_TiltTri", "results", "sizing.json")
    eb = p01["mass"]["pack_wh_per_kg_cited"]; reserve = p01["mission"]["reserve_fraction"]
    range_m = p01["mission"]["range_nmi"] * p01["constants"]["nmi_to_m"]; V = p01["mission"]["cruise_speed_ms"]
    hover_s = 204.0                                          # entry 44: hover-power time of the mission (15 + 120 + 15 s + climb + descent)
    rows = {}

    def row(key, bemt, cfd, src, extra=None, basis="both"):
        rows[key] = {"d_bemt": bemt, "d_cfd": cfd, "source": src, "basis": basis, **(extra or {})}

    row("tri_2blade", 0.0, 0.0, "reference (entry 48 tri V13828 24xx: %.2f kg; entry 44 tri U15XL: %.2f kg)" % (e48["sum_tri"], e44["sum_tri"]),
        {"sum_bemt": e48["sum_tri"], "sum_cfd": e44["sum_tri"]})
    row("hex_2blade", -e48["hex_minus_tri"], -e44["hex_minus_tri"], "entries 48 / 44 (hex - tri payload)", {"sum_bemt": e48["sum_hex"], "sum_cfd": e44["sum_hex"]})
    tri_gain_e47 = 2.76                                      # DESIGN_EXPLORATION.md entry 49: the tri gains +2.76 kg in the same catalogue move (entry 47)
    y6 = -(e49["payload_vs_tri_fit"] + e49["payload_change"] - tri_gain_e47)
    row("y6_2blade", y6, y6, "entry 49: Y6 %.2f + %.2f vs the tri's +%.2f catalogue gain" % (e49["payload_vs_tri_fit"], e49["payload_change"], tri_gain_e47), basis="bemt_only")
    r3 = {r_["layout"]: r_ for r_ in e21["rows"]}
    d3t = e21["baseline_2blade"]["tri"] - r3["tri"]["payload_end"]; d3h = e21["baseline_2blade"]["hex"] - r3["hex"]["payload_end"]
    row("tri_3blade", d3t, d3t, "entry 21: 3-blade payload change on the tri", basis="bemt_only")
    row("hex_3blade", -e48["hex_minus_tri"] + d3h, -e44["hex_minus_tri"] + d3h, "entry 21 (hex 3-blade change, BEMT) on top of the hex row", basis="mixed")
    b54, b60 = dia["54"]["best"]["tmotor_u15xl_kv38"]["budget"]["cited_303"], dia["60"]["best"]["tmotor_u15xl_kv38"]["budget"]["cited_303"]
    d60 = b60["drone_kg"] - b54["drone_kg"]
    row("tri_60in", d60, d60, "diameter study: drone mass 60 in %.2f vs 54 in %.2f kg (U15XL, 303 Wh/kg)" % (b60["drone_kg"], b54["drone_kg"]), basis="bemt_only")
    # toroid, from the two CFD runs at equal thrust
    p_ratio = cr["FoM"] / cf["FoM"]; q_ratio = p_ratio / math.sqrt(cr["CT_h"] / cf["CT_h"])
    blades = 3 * (bsm["toroid"]["fixed-guided equivalent (6.25 N)"]["set_kg"] - bsm["reference_set"])
    q_tri = 0.90 * 43.1                                       # entry 48 tri: V13828 (43.1 N m test torque) at the 10 % reserve
    motor = 3 * (q_ratio - 1) * q_tri * 0.0605                # entry 38: catalogue 24S motors 0.057-0.064 kg per N m
    motor_step = 3 * (4.408 - 2.465)                          # catalogue step V13828 -> U15XL if no re-optimisation absorbs it
    esc = 3 * 0.870 * (p_ratio ** 0.7 - 1)                    # entry 10: ESC 0.870 kg x (P/P_tri)^0.7
    pack_h = tri15["hover_w"] * hover_s / 3600 * (p_ratio - 1) / (1 - reserve) / eb
    pack_c = tri15["cruise_w"] * range_m / V / 3600 * (p_ratio - 1) / (1 - reserve) / eb
    lo, hi = blades + motor + esc + pack_h, blades + motor + esc + pack_h + pack_c
    row("tri_toroid", lo, hi, "this project's CFD pair + Props/01 spar model; low: cruise power as the 2-blade, high: cruise +%.1f %% like hover" % (100 * (p_ratio - 1)),
        {"parts": {"power_ratio": p_ratio, "torque_ratio": q_ratio, "blades_flex_test": blades, "motors": motor, "motor_catalogue_step_worst": motor_step,
                   "escs": esc, "pack_hover": pack_h, "pack_cruise_if_penalised": pack_c}}, basis="range")
    row("tri_toroid_opt1", None, None, "infeasible: legs fail the 50 N / 1.2 mm flex test even with frame action (%.1f mm)" %
        bsm["toroid_opt1"]["fixed-guided equivalent (6.25 N)"]["leg_deflection_mm"])
    # tilt-tricopter: heavier airframe, much cheaper cruise (wing-borne at 25 m/s)
    e_tilt = range_m / 1000 * s2["cruise"]["wh_per_km"] + tri15["hover_w"] * hover_s / 3600
    pack_tilt = e_tilt / (1 - reserve)
    d_tilt = (a2["mass_airframe_kg"] + a2["vehicle_mass"]["tilt hardware"] - a1["mass_airframe_kg"]) + (pack_tilt - e48["pack_tri"]) / eb
    row("tilt_tri", d_tilt, d_tilt, "Airframe 02 frame %.1f + tilt %.1f kg vs Airframe 01 frame %.1f kg; pack %.0f Wh (%.1f Wh/km cruise) vs the tri's %.0f Wh; sized at 127 kg, real ~185 kg" %
        (a2["mass_airframe_kg"], a2["vehicle_mass"]["tilt hardware"], a1["mass_airframe_kg"], pack_tilt, s2["cruise"]["wh_per_km"], e48["pack_tri"]), basis="bemt_only")
    # scores
    w = inp["weights"]; mid = {k: (0.5 * (r_["d_bemt"] + r_["d_cfd"]) if r_["d_bemt"] is not None else None) for k, r_ in rows.items()}
    feas = [v for v in mid.values() if v is not None]; dmin, dmax = min(feas), max(feas)
    out = []
    for k, o in inp["options"].items():
        r_ = rows[k]; m = mid[k]
        ms = 0.0 if m is None else 10 * (dmax - m) / (dmax - dmin)
        sc = {"mass": ms, "tw15": o["tw15"]["score"], "noise": o["noise"]["score"], "evidence": o["evidence"]["score"], "risk": o["risk"]["score"]}
        out.append({"key": k, "label": o["label"], "mass_delta_bemt": r_["d_bemt"], "mass_delta_cfd": r_["d_cfd"], "mass_delta_mid": m, "basis": r_["basis"],
                    "mass_source": r_["source"], "scores": sc, "total": sum(w[c] * sc[c] for c in w), "why": {c: o[c]["why"] for c in ("tw15", "noise", "evidence", "risk")},
                    **({"parts": r_["parts"]} if "parts" in r_ else {}), **({k2: r_[k2] for k2 in ("sum_bemt", "sum_cfd") if k2 in r_})})
    out.sort(key=lambda r_: -r_["total"])
    # sensitivity: mass weight 0.3-0.7, the rest scaled to fill
    sens = {}
    for wm in (0.3, 0.4, 0.5, 0.6, 0.7):
        rest = {c: w[c] * (1 - wm) / (1 - w["mass"]) for c in w if c != "mass"}; ww = {"mass": wm, **rest}
        rank = sorted(out, key=lambda r_: -sum(ww[c] * r_["scores"][c] for c in ww))
        sens[f"{wm:.1f}"] = [r_["key"] for r_ in rank]
    # cross-cutting levers (not options): what the requirements themselves move, tri / hex, from the same chains
    e48a = J(P01, "results", "explore", "e48_chain_10pct.json")["ranking"]
    levers = [
        {"lever": "Battery 303 -> 200 Wh/kg (LiPo)", "tri": e48a["24xx | 15 m/s | 200"]["sum_tri"] - e48["sum_tri"], "hex": e48a["24xx | 15 m/s | 200"]["sum_hex"] - e48["sum_hex"], "source": "entry 48"},
        {"lever": "Cruise 15 m/s -> free (best range, ~21-25 m/s)", "tri": e48a["24xx | free | 303"]["sum_tri"] - e48["sum_tri"], "hex": e48a["24xx | free | 303"]["sum_hex"] - e48["sum_hex"], "source": "entry 48"},
        {"lever": "CFD torque factors (if the coarse-mesh torque is real)", "tri": e44["sum_tri"] - e48["sum_tri"], "hex": e44["sum_hex"] - e48["sum_hex"], "source": "entries 44 vs 48 (different tri motor)"},
        {"lever": "Motors and ESCs sized for T/W 1.5 instead of 2.0 (estimate)", "tri": -(3 * 0.25 * q_tri * 0.0605 + 3 * 0.870 * (1 - 0.75 ** 0.7)),
         "hex": -(6 * 0.25 * 0.90 * 22.19 * 0.0605 + 6 * 0.870 * (1 - 0.75 ** 0.7) * 0.5), "source": "torque and power scale with thrust; entry 38 / 10 slopes"},
        {"lever": "Toroidal instead of 2-blade rotors (tri)", "tri": 0.5 * (lo + hi), "hex": None, "source": "this matrix"},
    ]
    res = {"weights": w, "basis": inp["mission_basis"], "rows": out, "sensitivity_mass_weight": sens, "levers": levers,
           "mass_range": [dmin, dmax], "drone_budget_kg": p01["vehicle"]["drone_max_lb"] * p01["constants"]["lb_to_kg"]}
    res["scenario"] = scen
    if scen == "15 m/s":
        json.dump(res, open(os.path.join(RES, "decision_matrix.json"), "w"), indent=1, default=float)
    return res


def plot(res):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rows = res["rows"][::-1]; w = res["weights"]
    cols = {"mass": "#2a78d6", "tw15": "#0b0b0b", "noise": "#7f8c8d", "evidence": "#c0a062", "risk": "#c0392b"}
    names = {"mass": "mass (50 %)", "tw15": "T/W 1.5 (20 %)", "noise": "noise (10 %)", "evidence": "evidence (10 %)", "risk": "risk / safety (10 %)"}
    fig, axs = plt.subplots(1, 2, figsize=(13, 4.8), gridspec_kw={"width_ratios": [1.5, 1]})
    y = np.arange(len(rows)); left = np.zeros(len(rows))
    for c in ("mass", "tw15", "noise", "evidence", "risk"):
        v = np.array([w[c] * r_["scores"][c] for r_ in rows])
        axs[0].barh(y, v, left=left, color=cols[c], label=names[c], height=0.6); left += v
    for i, r_ in enumerate(rows): axs[0].text(left[i] + 0.08, i, f"{r_['total']:.1f}", va="center", fontsize=8)
    axs[0].set_yticks(y, [r_["label"] for r_ in rows], fontsize=7.5); axs[0].set_xlabel("weighted score (0-10)"); axs[0].legend(fontsize=7, loc="lower right"); axs[0].grid(alpha=.3, axis="x")
    for i, r_ in enumerate(rows):
        if r_["mass_delta_mid"] is None:
            axs[1].text(0, i, "infeasible (flex test)", va="center", fontsize=7, color="#c0392b"); continue
        lo, hi = sorted([r_["mass_delta_bemt"], r_["mass_delta_cfd"]])
        axs[1].plot([lo, hi], [i, i], color="#2a78d6", lw=5, solid_capstyle="butt"); axs[1].plot([r_["mass_delta_mid"]], [i], "o", color="#0b0b0b", ms=4)
    axs[1].axvline(0, color="#52514e", lw=0.8); axs[1].set_yticks(y, [""] * len(rows)); axs[1].set_xlabel("mass vs. tricopter 2-blade [kg] (bar: BEMT .. CFD-factor basis)")
    axs[1].grid(alpha=.3, axis="x")
    fig.suptitle("Weight-first decision matrix: 280 lb vehicle, 10 nmi at 15 m/s, 303 Wh/kg pack, hot day", fontsize=10); fig.tight_layout()
    fig.savefig(os.path.join(RES, "fig_decision_matrix.png"), dpi=140); plt.close(fig)


BASIS_NOTE = ("† blade-element only: the same difference is repeated in the CFD column. The differences are taken against the tri on the "
              "same basis, so a CFD penalty that hits every layout alike cancels; in entry 44 the CFD factors improved the hex's difference "
              "(-0.5 to -3.4 kg) because the tri suffered more, so a repeated cell is neutral if the option behaves like the tri and pessimistic if "
              "it behaves like the hex. ◊ hex basis plus a blade-element 3-blade increment. ‡ not two bases: the toroid's own range, from cruise "
              "power equal to the 2-blade's (low) to cruise carrying the same +7.8 % as hover (high), derived from the CFD pair.")


def markdown(res, alt=None):
    f = lambda x: "-" if x is None else f"{x:+.1f}"
    L = ["# Decision matrix (weight first)", "", "Generated by `src/matrix.py` from the result files named in each row; scores and weights in "
         "`matrix_inputs.yaml`. Do not edit by hand.", "", f"Basis: {res['basis']}. Mass = change in propulsion + arms + fairing + mission "
         "pack against the tricopter with 2-blade 54 in rotors, in kg (negative is lighter), on the plain blade-element basis (entry 48) and "
         "the CFD-factor basis (entry 44); the coarse-nose CFD reads torque high, so the truth is expected between the two.", "",
         "| Rank | Option | Mass Δ BEMT / CFD [kg] | Mass | T/W 1.5 | Noise | Evidence | Risk | **Total** |", "|---|---|---|---|---|---|---|---|---|"]
    mark = {"both": "", "bemt_only": " †", "mixed": " ◊", "range": " ‡"}
    for i, r_ in enumerate(res["rows"], 1):
        s = r_["scores"]
        L.append(f"| {i} | {r_['label']} | {f(r_['mass_delta_bemt'])} / {f(r_['mass_delta_cfd'])}{mark.get(r_.get('basis'), '')} | {s['mass']:.1f} | {s['tw15']} | {s['noise']} | {s['evidence']} | {s['risk']} | **{r_['total']:.2f}** |")
    L += ["", BASIS_NOTE]
    L += ["", "Weights: " + ", ".join(f"{k} {v:.0%}" for k, v in res["weights"].items()) + ".", "",
          "Ranking against the mass weight (others scaled to fill): " + "; ".join(f"{k}: {' > '.join(v[:3])}" for k, v in res["sensitivity_mass_weight"].items()) + ".", ""]
    if alt:
        L += ["**If the cruise speed is free** (each layout at its best-range speed, ~21-25 m/s; only the tri and hex rows have numbers "
              "for it, the others keep their 15 m/s deltas): " + "; ".join(f"{i}. {r_['label']} ({f(r_['mass_delta_mid'])} kg, {r_['total']:.2f})" for i, r_ in enumerate(alt["rows"][:5], 1)) + ".", ""]
    L += [
          "## What moves the mass most (levers, not options)", "", "| Lever | Tri [kg] | Hex [kg] | Source |", "|---|---|---|---|"]
    for lv in res["levers"]:
        L.append(f"| {lv['lever']} | {f(lv['tri'])} | {f(lv['hex'])} | {lv['source']} |")
    L += ["", "## Why each score", ""]
    for r_ in res["rows"]:
        L.append(f"**{r_['label']}** (total {r_['total']:.2f}). Mass: {r_['mass_source']}.")
        for c in ("tw15", "noise", "evidence", "risk"):
            L.append(f"- {c}: {r_['scores'][c]} — {r_['why'][c]}")
        if "parts" in r_:
            pt = r_["parts"]
            L.append(f"- mass parts: power x{pt['power_ratio']:.3f}, torque x{pt['torque_ratio']:.3f} at equal thrust; blades (flex test) {pt['blades_flex_test']:+.2f}, "
                     f"motors {pt['motors']:+.2f} (catalogue step worst case {pt['motor_catalogue_step_worst']:+.2f}), ESCs {pt['escs']:+.2f}, pack hover {pt['pack_hover']:+.2f}, "
                     f"pack cruise 0 to {pt['pack_cruise_if_penalised']:+.2f} kg")
        L.append("")
    L += [f"The 55 lb drone limit is {res['drone_budget_kg']:.1f} kg. The propulsion, arms and pack alone are "
          f"{res['rows'][0].get('sum_bemt', float('nan')):.0f}-{max(r_.get('sum_cfd', 0) for r_ in res['rows']):.0f} kg in the best options, before the keel, gear and avionics."]
    open(os.path.join(ROOT, "DECISION_MATRIX.md"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    r = build(); plot(r); alt = build("free"); markdown(r, alt)
    json.dump(alt, open(os.path.join(RES, "decision_matrix_free_speed.json"), "w"), indent=1, default=float)
    print("free speed:", [(x["key"], round(x["total"], 2), None if x["mass_delta_mid"] is None else round(x["mass_delta_mid"], 2)) for x in alt["rows"]])
    for i, x in enumerate(r["rows"], 1):
        m = "-" if x["mass_delta_mid"] is None else "%+.2f" % x["mass_delta_mid"]
        print(f"{i}. {x['label']:46s} mass {m:>6} kg  total {x['total']:.2f}  {x['scores']}")
    print("sensitivity:", json.dumps(r["sensitivity_mass_weight"]))
    print("levers:", json.dumps(r["levers"], default=float))

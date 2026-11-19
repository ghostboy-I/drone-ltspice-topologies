"""Exploration 53: re-state the coaxial results of CONFIG_STUDY and entries 01-06 with the vortex-wake cruise term
(queue item 13, 2026-11-18). No new BEMT.

Entry 07 replaced the lens model of cruise wake interference with a prescribed vortex wake. At the h/D 0.2 spacing that all
of entries 01-05 and the configuration study used, the arm-pair interference rose from 1883 W to 3422 W (vehicle).
The interference is an induced-power term, P_int = 2 sigma T_u T_l / (2 rho A V'), set by the rotor thrusts, disk area,
spacing and flight state, not by the blade shape. Every equal-diameter coaxial design at h/D 0.2 carries the same thrusts in
cruise, so the correction is the same additive constant for all of them:
    d pack = (pack_bs - pack_lens) at h/D 0.2 (entry 07: the mission model's own conversion of 1539 W of cruise power)
    d payload = - d pack / e_b
Entry 05's diameter splits change the disk areas and the lens overlap fraction, so a constant does not apply there. They are
bounded with Prandtl's unequal-span biplane estimate: sigma scales with the gap over the mean span, and the interference
with T^2/(rho A) of each disk.
"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from common import RESULTS, save_json, load_params

OUT = os.path.join(RESULTS, "explore")


def run():
    p = load_params(); eb = p["mass"]["pack_wh_per_kg_cited"]
    r7 = next(x for x in json.load(open(os.path.join(OUT, "e07_cruise_wake.json")))["rows"] if abs(x["h_over_D"] - 0.2) < 1e-9)
    dP = r7["penalty_bs_w"] - r7["penalty_lens_w"]; dpack = r7["pack_bs_wh"] - r7["pack_lens_wh"]; k = dpack / dP; dpay = -dpack / eb
    print(f"  h/D 0.2: interference {r7['penalty_lens_w']:.0f} -> {r7['penalty_bs_w']:.0f} W (+{dP:.0f}), pack {r7['pack_lens_wh']:.0f} -> {r7['pack_bs_wh']:.0f} Wh"
          f" (+{dpack:.0f}, {k:.4f} Wh per W), payload {dpay:+.2f} kg at {eb} Wh/kg", flush=True)
    e06 = {round(x["h_over_D"], 2): x for x in json.load(open(os.path.join(OUT, "e06_coax_spacing.json")))["rows"]}
    e04 = json.load(open(os.path.join(OUT, "e04_upper_lower_blades.json")))["reference"]
    base = 7474.8
    # headline payloads vs the tricopter at h/D 0.2, as published (lens model)
    rows = [("CONFIG_STUDY: Phase 2 blade pair, half-size motors", -0.8, 5969.0),
            ("Entry 03: spar-sized coax blade (best of entries 01-03)", 0.2, None),
            ("Entry 04/05 reference: entry 03 blade, 54/54 in", 0.26, e04["pack_wh"]),
            ("Entry 06: entry 03 blade with mast mass and drag, h/D 0.2", e06[0.2]["payload_kg"], e06[0.2]["pack_wh"])]
    out = []
    for name, pay, pack in rows:
        o = {"case": name, "payload_lens": pay, "payload_vortex": pay + dpay}
        if pack: o.update(pack_lens=pack, pack_vortex=pack + dpack, energy_vs_tri_lens=pack / base - 1, energy_vs_tri_vortex=(pack + dpack) / base - 1)
        out.append(o)
        print(f"  {name:58s}: payload {pay:+.2f} -> {pay + dpay:+.2f} kg" + (f", pack {pack:.0f} -> {pack + dpack:.0f} Wh ({100 * (pack / base - 1):+.1f} % -> {100 * ((pack + dpack) / base - 1):+.1f} % vs tri)" if pack else ""), flush=True)
    # entry 05 diameter splits: Prandtl unequal-span scaling of the vortex-wake term, relative to 54/54
    e05 = json.load(open(os.path.join(OUT, "e05_diameter_split.json")))["rows"]; e07all = json.load(open(os.path.join(OUT, "e07_cruise_wake.json")))["rows"]
    sig = lambda g: (1 - 0.66 * g) / (1.055 + 3.7 * g)
    h = 0.2 * 54.0; splits = []
    for x in e05:
        Du, Dl = x["D_upper_in"], x["D_lower_in"]; bm = 0.5 * (Du + Dl)
        # P_int = 2 sigma(G/b) T_u T_l / (2 rho V' sqrt(A_u A_l)) -> relative to 54/54: sigma ratio x 54^2 / (Du Dl)
        f = sig(h / bm) / sig(0.2) * 54.0 ** 2 / (Du * Dl)
        P_bs = r7["penalty_bs_w"] * f; P_lens = r7["penalty_lens_w"] * x["overlap_f"] / r7["f_lens"] * 1.0   # lens term scaled by its overlap fraction (same w)
        d = (P_bs - P_lens) * k
        splits.append({"family": x["mode"], "D_upper_in": Du, "D_lower_in": Dl, "payload_lens": x["payload_kg"], "f_prandtl": f, "P_int_bs_est": P_bs, "P_int_lens_est": P_lens,
                       "payload_vortex_est": x["payload_kg"] - d / eb})
        print(f"  e05 {x['mode']:5s} {Du:5.1f}/{Dl:5.1f}: payload {x['payload_kg']:+.2f} -> {x['payload_kg'] - d / eb:+.2f} kg (interference lens {P_lens:.0f} W -> vortex {P_bs:.0f} W, f {f:.3f})", flush=True)
    save_json(os.path.join("explore", "e53_coax_restatement.json"), {"dP_w": dP, "dpack_wh": dpack, "wh_per_w": k, "dpayload_kg": dpay, "rows": out, "e05": splits,
                                                                   "spacing_e07": [{"h_over_D": x["h_over_D"], "pack_bs_wh": x["pack_bs_wh"]} for x in e07all]})
    print("  wrote results/explore/e53_coax_restatement.json")


if __name__ == "__main__":
    run()

"""Exploration 55: faired arms in the speed chain, and a correction to entry 54 (queue item 62, 2026-11-18).

Entry 54 priced hex and tri arm fairings against bare arms. But the vehicle chain since entry 17 (e16.arm_force_per_q,
e17 setup) already carries entry 14's best option per layout: the HEX WITH A FULL t/c 0.5 FAIRING (0.35 kg/m2 skin, its
download and mass) and the TRI BARE. Its arm term is a drag area f_arm = D/q, so it scales correctly with speed, and the
free-speed optimum of entries 48-50 already includes the hex fairing. The genuinely new options are:
  hex: the same fairing with a lighter skin (0.15 or 0.25 kg/m2): mass only, no aero change;
  tri: a fairing (t/c 0.5), which entry 14 rejected at 15 m/s but which gains with V^2.
Here: for each e48 point (24xx and 24xx-64, V = 14-30 m/s) add the tri fairing's cruise saving and download cost
(e54 model at that V) and the mass changes, convert with the mission model's k_c(V) = 0.4884 x 15/V Wh/W and 0.082 Wh/W
in hover, re-pick each layout's best speed, and redo hex - tri at 303 and 200 Wh/kg. Payload = -(mass sum).
"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e14_faired_arms import cd_t, CD_BROAD, SKIN_FACTOR
from common import RESULTS, save_json

OUT = os.path.join(RESULTS, "explore")
CD_TUBE, ETA, RHO, K_C15, K_H, W, E0 = 1.2, 0.8, 1.109, 0.4884, 0.082, 6 * 207.6, 303.3
TC = 0.5


def tri_fairing(V, hover_w, e9, C):
    d, L = e9["arm_tri"]["d_mm"] / 1000, e9["arm_tri"]["L_m"]; s3, qw, lu = C["sin3_sum"], C["q_w"], C["l_under"]; q = 0.5 * RHO * V * V; c = d / TC
    dP = q * (cd_t(TC, c, V) - CD_TUBE) * d * L * s3 * V / ETA
    dl0, dl = 3 * qw * CD_TUBE * d * lu, 3 * qw * CD_BROAD * c * lu; f = C["fuse_download_n"]
    dhov = hover_w * ((1 + (dl + f) / W) ** 1.5 - (1 + (dl0 + f) / W) ** 1.5)
    return dP * K_C15 * 15.0 / V + dhov * K_H, 3 * L * (2 * c - 0.57 * d) * SKIN_FACTOR      # d pack [Wh], skin area [m2]


def run():
    e9 = json.load(open(os.path.join(OUT, "e09_hex_vs_y6.json"))); e14 = json.load(open(os.path.join(OUT, "e14_faired_arms.json")))
    pts = json.load(open(os.path.join(OUT, "e48_chain_10pct.json")))["points"]; C = e14["configs"]["tri"]
    hexrow = e14["configs"]["hex0"]["rows"]["full t/c 0.5"]; hex_area = hexrow["fairing_kg"] / 0.35       # kg / (kg/m2) incl. 1.15
    out = {"cases": []}
    for sec in ("24xx", "24xx-64"):
        for eb in (303.3, 200.0):
            res = {}
            for lay in ("hex", "tri"):
                P = [q for q in pts if q["key"] == f"{lay} {sec}"]
                for opt, sk in ((("chain", None), ("skin 0.25", 0.25), ("skin 0.15", 0.15)) if lay == "hex" else (("bare", None), ("faired 0.35", 0.35), ("faired 0.15", 0.15))):
                    best = None; best15 = None
                    for q in P:
                        hw = q["mass_sum"] - q["pack"] / E0; pack = q["pack"]
                        if lay == "hex" and sk: hw -= (0.35 - sk) * hex_area
                        if lay == "tri" and sk:
                            dpk, area = tri_fairing(q["V"], q["hover_w"], e9, C); pack += dpk; hw += sk * area
                        m = hw + pack / eb; r = {"V": q["V"], "mass": m, "pack": pack, "hw": hw}
                        if best is None or m < best["mass"]: best = r
                        if q["V"] == 15.0: best15 = r
                    res[(lay, opt)] = {"free": best, "15": best15}
            for spd in ("15", "free"):
                for ho in ("chain", "skin 0.15"):
                    for to in ("bare", "faired 0.35", "faired 0.15"):
                        h, t = res[("hex", ho)][spd], res[("tri", to)][spd]
                        out["cases"].append({"section": sec, "e_b": eb, "speed": spd, "hex": ho, "tri": to, "hex_minus_tri": t["mass"] - h["mass"], "V_hex": h["V"], "V_tri": t["V"],
                                             "mass_hex": h["mass"], "mass_tri": t["mass"]})
            for spd in ("15", "free"):
                row = [c for c in out["cases"] if c["section"] == sec and c["e_b"] == eb and c["speed"] == spd]
                g = lambda ho, to: next(c for c in row if c["hex"] == ho and c["tri"] == to)
                a, b, cc, dd = g("chain", "bare"), g("chain", "faired 0.35"), g("skin 0.15", "faired 0.15"), g("skin 0.15", "bare")
                print(f"  {sec:7s} {eb:5.1f} Wh/kg {spd:4s}: e48 basis {a['hex_minus_tri']:+.2f} (V {a['V_hex']:.0f}/{a['V_tri']:.0f}); tri faired 0.35 {b['hex_minus_tri']:+.2f} (V tri {b['V_tri']:.0f});"
                      f" hex skin 0.15 vs tri bare {dd['hex_minus_tri']:+.2f}; both light skins {cc['hex_minus_tri']:+.2f} kg (V {cc['V_hex']:.0f}/{cc['V_tri']:.0f})", flush=True)
    out["hex_fairing_area_m2"] = hex_area
    save_json(os.path.join("explore", "e55_fairings_chain.json"), out); print("  wrote results/explore/e55_fairings_chain.json")


if __name__ == "__main__":
    run()

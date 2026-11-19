"""Exploration 54: arm fairings revisited at the free-speed cruise and with lighter skins (queue item 22, 2026-11-18).

Entry 14 found faired arms nearly payload-neutral on the hex (+0.07 kg) at 15 m/s with a 0.35 kg/m2 skin. Two things
it did not vary:
 (1) cruise speed. Arm drag power is q Cd S V = 1/2 rho V^3 Cd S, and the cruise lasts range / V, so the cruise ENERGY
     of the arms goes as V^2. At the free-speed optimum (hex 21 m/s, tri 24.8 m/s, entry 48) a fairing saves
     (21/15)^2 = 1.96x (hex) or 2.73x (tri) the energy it saved at 15 m/s.
     The best speed itself shifts when drag changes, but at an optimum the first-order effect of a parameter change is
     its effect at fixed speed (envelope theorem), so evaluating at the old best speed is correct to first order.
 (2) skin areal mass: 0.15 (one ply of light carbon or aramid over foam), 0.25, 0.35 (entry 14), 0.50 kg/m2.
and extends t/c to 0.75 and 1.0 (entry 14's optimum, 0.5, sat at the edge of its sweep).
Energy bookkeeping (entry 14's finite differences of the mission model, re-derived): each watt of cruise costs
    k_c(V) = (range / V) / 3600 / eta_pack / (1 - reserve) Wh = 0.4884 x 15 / V Wh/W,
and each watt of hover 0.082 Wh/W. Payload change = -(d pack) / e_b - fairing mass. Arm geometry, download model and
Hoerner section drag are entry 14's (imported); hover powers from entry 48 (10 % reserve chain, 24xx).
"""
import json, math, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e14_faired_arms import cd_t, CD_BROAD, SKIN_FACTOR
from common import RESULTS, save_json

OUT = os.path.join(RESULTS, "explore")
CD_TUBE, ETA, RHO = 1.2, 0.8, 1.109
K_C15, K_H = 0.4884, 0.082
SKINS = (0.15, 0.25, 0.35, 0.50)
TCS = (0.33, 0.5, 0.75, 1.0)


def run(e_b=303.3):
    e9 = json.load(open(os.path.join(OUT, "e09_hex_vs_y6.json"))); e14 = json.load(open(os.path.join(OUT, "e14_faired_arms.json")))
    pts = json.load(open(os.path.join(OUT, "e48_chain_10pct.json")))["points"]
    W = 6 * 207.6
    cases = {"hex": ("hex0", e9["arm_hex"], 6, (15.0, 21.0)), "tri": ("tri", e9["arm_tri"], 3, (15.0, 25.0))}
    rows = []
    for lay, (key, arm, narm, speeds) in cases.items():
        C = e14["configs"][key]; d, L = arm["d_mm"] / 1000, arm["L_m"]; s3 = C["sin3_sum"]; qw, lu = C["q_w"], C["l_under"]
        hov = next(q for q in pts if q["key"] == f"{lay} 24xx")["hover_w"]
        dl0 = narm * qw * CD_TUBE * d * lu; fuse = C["fuse_download_n"]
        for V in speeds:
            q = 0.5 * RHO * V * V; kc = K_C15 * 15.0 / V
            bare_w = q * CD_TUBE * d * L * s3 * V / ETA
            for tc in TCS:
                c = d / tc; cdt = cd_t(tc, c, V)
                fair_w = q * cdt * d * L * s3 * V / ETA
                dl = narm * qw * CD_BROAD * c * lu
                dhov = hov * ((1 + (dl + fuse) / W) ** 1.5 - (1 + (dl0 + fuse) / W) ** 1.5)
                dpack = (fair_w - bare_w) * kc + dhov * K_H
                area = narm * L * (2 * c - 0.57 * d) * SKIN_FACTOR          # skin area incl. the 1.15 for ribs and bonding
                for sk in SKINS:
                    m = sk * area
                    rows.append({"layout": lay, "V": V, "tc": tc, "skin_kg_m2": sk, "chord_m": c, "cd_t": cdt, "bare_w": bare_w, "faired_w": fair_w,
                                 "download_frac": dl / W, "d_hover_w": dhov, "d_pack_wh": dpack, "fairing_kg": m, "d_payload_kg": -dpack / e_b - m,
                                 "breakeven_skin_kg_m2": (-dpack / e_b) / area})
            b = max((r for r in rows if r["layout"] == lay and r["V"] == V), key=lambda r: r["d_payload_kg"])
            print(f"  {lay} V {V:4.1f}: bare arms {bare_w:5.0f} W (k_c {kc:.3f} Wh/W); best t/c {b['tc']}, skin {b['skin_kg_m2']}: arms {b['faired_w']:.0f} W,"
                  f" dpack {b['d_pack_wh']:+.0f} Wh, fairing {b['fairing_kg']:.2f} kg, dpayload {b['d_payload_kg']:+.2f} kg", flush=True)
            for tc in TCS:
                r35 = next(r for r in rows if r["layout"] == lay and r["V"] == V and r["tc"] == tc and r["skin_kg_m2"] == 0.35)
                r15 = next(r for r in rows if r["layout"] == lay and r["V"] == V and r["tc"] == tc and r["skin_kg_m2"] == 0.15)
                print(f"     t/c {tc:4.2f}: Cd_t {r35['cd_t']:.3f}, arms {r35['faired_w']:4.0f} W, download {100 * r35['download_frac']:.2f} %, dpack {r35['d_pack_wh']:+5.0f} Wh,"
                      f" dpayload {r35['d_payload_kg']:+.2f} (0.35) / {r15['d_payload_kg']:+.2f} (0.15) kg, break-even skin {r35['breakeven_skin_kg_m2']:.2f} kg/m2", flush=True)
    save_json(os.path.join("explore", "e54_fairings_speed.json"), {"e_b": e_b, "rows": rows}); print("  wrote results/explore/e54_fairings_speed.json")


if __name__ == "__main__":
    run()

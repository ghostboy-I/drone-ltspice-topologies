"""Exploration 52: unequal hover thrust in the opposite-pair mixed hex (queue item 60, 2026-11-18).

Entry 51: MN1123 rotors (A, torque-bound, louder) and MN1320 rotors (B, 8 % torque headroom, quieter) on opposite pairs
trim at equal thrust. On opposite pairs each spin direction holds the same mix, so yaw and roll/pitch also trim with
T_A != T_B, as long as both rotors of a pair match. The hover split is a free variable:
    n_A T_A + n_B T_B = W,   s = T_B / (W/6)  ->  T_A = (W - n_B s W/6) / n_A.
The T/W-2 ceiling does not depend on the hover split (fixed pitch, rpm control): at full throttle every rotor goes to its
own limit, so the ceiling is (2W/6)(n_A + n_B Q_lim,B/Q_max,B)/W, the same for every s.
For each s: BEMT hover of each blade at its thrust (bemt.hover_at_thrust), and the entry-46 noise model (BPM trailing edge +
rounded tip + Gutin tones, 50 m, 30 deg below) computed per rotor type at that thrust, then summed incoherently with
counts n_A, n_B. Hover power changes are converted to pack by two bounds: hover-only (the 204 s at hover power plus the
climb, of a 5000 Wh mission) and the whole pack scaled by the hover-power ratio (if the cruise split followed the hover
split).
1 process, nice 19.
"""
import json, math, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import bemt
from common import RESULTS, save_json

OUT = os.path.join(RESULTS, "explore")
S = (0.96, 1.00, 1.04, 1.08, 1.12, 1.16, 1.20)
T_HOVER_S = 204.0 + 60.0 / 2.5                                 # hover segments + climb at ~hover power [s]


def run():
    import e01_coax_blade as e01, e02_coax_two_point as e02, e24_chain_best_blades as e24, e37_catalogue_motor as e37
    e01.init(); G = e01.G; p, hot = G["p"], G["hot"]; W = G["ph1"]["vehicle"]["weight_n"]; whkg = p["mass"]["pack_wh_per_kg_cited"]
    db = e24.db_for("hex0", "best"); Rr = p["rotor"]["diameter_in"] * p["constants"]["inch_to_m"] / 2
    rows46 = json.load(open(os.path.join(OUT, "e46_hex_noise_curve.json")))["rows"]
    bl = {"A": next(r for r in rows46 if r["motor"].startswith("MN1123") and r["cap"] == 0.65), "B": next(r for r in rows46 if r["motor"].startswith("MN1320"))}
    cache = {}

    def per_rotor(k, t):
        key = (k, round(t, 3))
        if key in cache: return cache[key]
        b = e02.blade_from(bl[k]["blade"], Rr, p["rotor"]["hub_radius_m"]); h = bemt.hover_at_thrust(b, db, hot, t)
        w0 = G["ph1"]["vehicle"]["weight_n"]; G["ph1"]["vehicle"]["weight_n"] = 6 * t          # noise functions use W/6 per rotor
        try:
            nz = e37.noise("hex", bl[k]["blade"])
        finally:
            G["ph1"]["vehicle"]["weight_n"] = w0
        o = {"T": t, "rpm": h["rpm"], "P": h["P"], "Q": h["Q"], "tip_mach": h["rpm"] * 2 * math.pi / 60 * Rr / hot["a"],
             **{f"{x}_1": nz[x] - 10 * math.log10(6) for x in ("te_dba", "tonal_dba", "total_dba")}}
        cache[key] = o
        print(f"    {k} T {t:6.1f} N: rpm {o['rpm']:6.0f}, P {o['P']:6.0f} W, Q {o['Q']:5.2f} N m, one rotor {o['total_dba_1']:.2f} dBA", flush=True)
        return o

    lsum = lambda pairs: 10 * math.log10(sum(n * 10 ** (L / 10) for n, L in pairs))
    pack_ref = {"2+4": (2 * bl["A"]["pack"] + 4 * bl["B"]["pack"]) / 6, "4+2": (4 * bl["A"]["pack"] + 2 * bl["B"]["pack"]) / 6}
    pay_ref = {"2+4": (2 * bl["A"]["payload_cat"] + 4 * bl["B"]["payload_cat"]) / 6, "4+2": (4 * bl["A"]["payload_cat"] + 2 * bl["B"]["payload_cat"]) / 6}
    out = {"W": W, "t_hover_s": T_HOVER_S, "cases": {}}
    for mix, nA, nB in (("2+4", 2, 4), ("4+2", 4, 2)):
        rows = []
        for s in S:
            tB = s * W / 6; tA = (W - nB * tB) / nA
            a, b = per_rotor("A", tA), per_rotor("B", tB)
            P = nA * a["P"] + nB * b["P"]
            rows.append({"s": s, "T_A": tA, "T_B": tB, "rpm_A": a["rpm"], "rpm_B": b["rpm"], "P_hover": P,
                         "total_dba": lsum(((nA, a["total_dba_1"]), (nB, b["total_dba_1"]))), "tonal_dba": lsum(((nA, a["tonal_dba_1"]), (nB, b["tonal_dba_1"]))),
                         "te_dba": lsum(((nA, a["te_dba_1"]), (nB, b["te_dba_1"])))})
        P0 = next(r for r in rows if r["s"] == 1.0)["P_hover"]
        for r in rows:
            dP = r["P_hover"] - P0
            r["dpack_hover_only_wh"] = dP * T_HOVER_S / 3600 / (1 - p["mission"]["reserve_fraction"])
            r["dpack_scaled_wh"] = pack_ref[mix] * dP / P0
            r["payload_hi"] = pay_ref[mix] - r["dpack_hover_only_wh"] / whkg; r["payload_lo"] = pay_ref[mix] - r["dpack_scaled_wh"] / whkg
            print(f"  {mix} s {r['s']:.2f}: T_A {r['T_A']:.1f} / T_B {r['T_B']:.1f} N, rpm {r['rpm_A']:.0f}/{r['rpm_B']:.0f}, P_hover {r['P_hover']:.0f} W ({100 * dP / P0:+.2f} %),"
                  f" {r['total_dba']:.2f} dBA (TE {r['te_dba']:.1f}, tonal {r['tonal_dba']:.1f}), payload {r['payload_lo']:+.2f} to {r['payload_hi']:+.2f} kg", flush=True)
        tq = bl["B"]["motor_torque"] / bl["B"]["Q_max"]
        out["cases"][mix] = {"rows": rows, "tw_ceiling": (nA + nB * tq) * 2 / 6, "payload_ref": pay_ref[mix], "pack_ref": pack_ref[mix]}
    out["single"] = {f"{k}:{t}": v for (k, t), v in cache.items()}
    save_json(os.path.join("explore", "e52_mixed_hex_split.json"), out); print("  wrote results/explore/e52_mixed_hex_split.json")


if __name__ == "__main__":
    run()

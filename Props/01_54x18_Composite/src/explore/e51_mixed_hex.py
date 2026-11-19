"""Exploration 51: a hex with mixed motors (queue item 56, 2026-11-18). No new BEMT: entry 46's two optimised hex rotors,
A = MN1123 (cap 0.65, torque-bound, +5.46 kg, 50.3 dBA) and B = MN1320 (cap 0.60, free torque, +2.95 kg, 46.3 dBA), are
mixed on one hex frame. Both were designed for the same rotor thrust W/6 and the same T/W 2 in the same frame.

Two arrangements:
 (1) "alternating 3 + 3": A on arms 0/120/240 deg, B on 60/180/300. A hex alternates spin direction, so all A spin one
     way and all B the other. Yaw trim then needs 3 Q_A = 3 Q_B. For a fixed-pitch rotor in hover T and Q both scale
     with rpm^2, so Q = k T with k = Q_max / T_max. With T_max = 2W/6 for both rotors, k_B / k_A = Q_max,B / Q_max,A.
 (2) "opposite pairs": each type on diametrically opposite arms (one CW, one CCW per pair), e.g. A on 0/180, B on the
     other four. Each spin direction then holds the same motor mix, so yaw trims at equal thrust per type, and opposite
     rotors with equal thrust keep roll and pitch trimmed. Only 2 + 4 and 4 + 2 exist.
In (2) every rotor runs at its own design point, so hardware and pack are linear in the counts, and the payload is the
count-weighted mean. Noise: the rotors are incoherent sources at (nearly) the same distance, so the mean square pressures
add: L = 10 log10( sum n_i 10^(L_i/10) / 6 ).
"""
import json, math, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from common import RESULTS, save_json

OUT = os.path.join(RESULTS, "explore")


def esum(levels, counts):
    return 10 * math.log10(sum(n * 10 ** (L / 10) for L, n in zip(levels, counts)) / sum(counts))


def run():
    rows = json.load(open(os.path.join(OUT, "e46_hex_noise_curve.json")))["rows"]
    A = next(r for r in rows if r["motor"].startswith("MN1123") and r["cap"] == 0.65); B = next(r for r in rows if r["motor"].startswith("MN1320"))
    # (1) alternating 3 + 3
    kr = B["Q_max"] / A["Q_max"]                         # k_B / k_A
    tA = 2 * kr / (1 + kr)                               # T_A / (W/6) in yaw-trimmed hover (T_A + T_B = 2 W/6)
    tw = 1 + 1 / kr                                      # max T/W with A at its torque limit and yaw trimmed: 3 (2W/6)(1 + k_A/k_B) / W
    need = (2 / tw)                                      # A torque needed for T/W 2 relative to its limit (A sets the ceiling)
    alt = {"k_ratio": kr, "hover_TA_over_W6": tA, "hover_TB_over_W6": 2 - tA, "tw_max": tw, "A_torque_needed_x": need}
    print(f"  alternating 3+3: k_B/k_A {kr:.4f}; hover T_A {tA:.3f} / T_B {2 - tA:.3f} x W/6; T/W ceiling {tw:.3f}; A needs x{need:.3f} torque for T/W 2", flush=True)
    # (2) opposite pairs
    mixes = []
    sl = (A["payload_cat"] - B["payload_cat"]) / (A["total_dba"] - B["total_dba"])
    for nA in (0, 2, 4, 6):
        c = (nA, 6 - nA); L = esum((A["total_dba"], B["total_dba"]), c)
        pay = (nA * A["payload_cat"] + (6 - nA) * B["payload_cat"]) / 6
        hw = (nA * A["hw"] + (6 - nA) * B["hw"]) / 6; pack = (nA * A["pack"] + (6 - nA) * B["pack"]) / 6
        line = B["payload_cat"] + sl * (L - B["total_dba"])
        m = {"n_MN1123": nA, "n_MN1320": 6 - nA, "payload": pay, "hw": hw, "pack": pack, "total_dba": L,
             "tonal_dba": esum((A["tonal_dba"], B["tonal_dba"]), c), "te_dba": esum((A["te_dba"], B["te_dba"]), c), "chord_payload": line}
        mixes.append(m)
        print(f"  {nA} x MN1123 + {6 - nA} x MN1320: payload {pay:+.2f} kg (chord {line:+.2f}), hw {hw:.2f} kg, pack {pack:.0f} Wh, {L:.2f} dBA", flush=True)
    save_json(os.path.join("explore", "e51_mixed_hex.json"), {"A": {k: A[k] for k in ("motor", "cap", "payload_cat", "Q_max", "motor_torque", "hw", "pack", "total_dba", "tonal_dba", "te_dba")},
                                                            "B": {k: B[k] for k in ("motor", "cap", "payload_cat", "Q_max", "motor_torque", "hw", "pack", "total_dba", "tonal_dba", "te_dba")},
                                                            "alternating": alt, "opposite_pairs": mixes, "chord_kg_per_db": sl})
    print("  wrote results/explore/e51_mixed_hex.json")


if __name__ == "__main__":
    run()

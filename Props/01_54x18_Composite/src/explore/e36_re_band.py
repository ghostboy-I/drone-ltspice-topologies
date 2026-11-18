"""Exploration 36: the aft-thick section only where the Reynolds number is high (queue item 43).

Entry 35: NACA 24xx-64/-65 beat 24xx above Re ~ 7e5-1e6 and lose below it. Along the hover blade Re peaks at 0.7-0.9 R
(hex 8e5, tri 1.0e6) and falls toward the narrow tip (4.7-6e5) and the root. The BEMT polar lookup sees (t/c, Re, M, alpha)
but not the radius; t/c falls monotonically from root to tip (0.18 -> 0.09), so the section band is keyed on t/c:
  tip, t/c < 0.097 (r > ~0.93 R): ordinary 24xx;  band 0.097 <= t/c <= 0.15 (~0.45-0.93 R): 24xx-64 or -65;
  inboard (t/c > 0.15): 24xx (hex) or the 44xx of the tri hybrid. Linear ramps of 0.005 in t/c between them.
Blades re-optimised at tip-Mach cap 0.60 as in entry 35, compared with entry 35's uniform-section optima.
Runs on 2 cores at nice 19 (the toroid session's CFD is using 10 cores).
"""
import json, math, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from multiprocessing import Pool
import numpy as np

LO, HI, RAMP = 0.097, 0.15, 0.005


class BandDB:
    """base section outside lo <= t/c <= hi, band section inside, with linear ramps of width `ramp`."""
    def __init__(self, base, band, lo, hi, ramp=RAMP):
        self.a, self.b, self.lo, self.hi, self.ramp = base, band, lo, hi, ramp
        self.family = f"{getattr(base, 'family', '?')}|{band.family}[{lo:.3f}-{hi:.3f}]"

    def w(self, tc):
        tc = np.asarray(tc, float)
        return np.clip((tc - self.lo) / self.ramp + 0.5, 0, 1) * np.clip((self.hi - tc) / self.ramp + 0.5, 0, 1)

    def lookup(self, tc, re, mach, alpha):
        w = self.w(tc); cla, cda = self.a.lookup(tc, re, mach, alpha); clb, cdb = self.b.lookup(tc, re, mach, alpha)
        return (1 - w) * cla + w * clb, (1 - w) * cda + w * cdb

    def __getattr__(self, n):
        return getattr(self.a, n)


def make_db(layout, suffix):
    import e35_mod4_laminar as e35
    from blade_trade_study import HybridDB
    db24, db44 = e35.dbs(None); dbx, _ = e35.dbs(suffix)
    if layout == "hex": return BandDB(db24, dbx, LO, HI)
    return HybridDB(BandDB(db24, dbx, LO, 1.0), db44)              # tri: 24 tip | X band | X/44 blend 0.12-0.15 | 44 inboard


def job(args):
    layout, suffix = args
    import e01_coax_blade as e01, e11_blade_with_motor as e11, e13_tri_torque_margin as e13, e24_chain_best_blades as e24
    from common import RESULTS
    e01.init(); db = make_db(layout, suffix)
    bd = e24.blade_for("hex0" if layout == "hex" else "tri", "best")
    e01.G["db"] = db; e01.G["p"]["rotor"]["tip_mach_max"] = 0.60
    lab = f"{layout} 24xx tip + 24xx-{suffix} band"
    if layout == "tri":
        r = e13.optimise((lab, bd)); ref = json.load(open(os.path.join(RESULTS, "explore", "e13_tri_torque_margin.json")))["reference"]
        pay = -(r["end"]["hw"] - ref["hw"] + (r["end"]["pack"] - ref["pack"]) / e01.G["p"]["mass"]["pack_wh_per_kg_cited"])
    else:
        r = e11.optimise((lab, bd, "motor")); pay = r["end"]["payload"]
    e = r["end"]
    return {"layout": layout, "band": f"24xx-{suffix}", "payload": pay, "pack": e["pack"], "hw": e["hw"], "rpm_hover": e["rpm_hover"], "solidity": e["solidity"],
            "margin": e["margin"], "tw_mach": e["tw_mach"], "motor_kg": e["motor_kg"], "blade": r["blade"]}


def run():
    from common import RESULTS, save_json
    OUT = os.path.join(RESULTS, "explore"); e35j = json.load(open(os.path.join(OUT, "e35_mod4_laminar.json")))
    with Pool(2) as pool:
        rows = pool.map(job, [(l, s) for l in ("hex", "tri") for s in ("64", "65")])
    ref = {(r["layout"], r["section"]): r["payload"] for r in e35j["rows"]}
    for r in rows:
        r["d_vs_24xx"] = r["payload"] - ref[(r["layout"], "24xx")]; r["d_vs_uniform"] = r["payload"] - ref[(r["layout"], r["band"])]
        print(f"  {r['layout']} 24xx tip + {r['band']} band: payload {r['payload']:+.2f} kg (vs all-24xx {r['d_vs_24xx']:+.2f}, vs uniform {r['band']} {r['d_vs_uniform']:+.2f}),"
              f" pack {r['pack']:.0f} Wh, hw {r['hw']:.2f}, rpm {r['rpm_hover']:.0f}, sigma {r['solidity']:.3f}, margin {r['margin']}", flush=True)
    save_json(os.path.join("explore", "e36_re_band.json"), {"band_tc": [LO, HI], "ramp": RAMP, "rows": rows, "e35_reference": {f"{k[0]} {k[1]}": v for k, v in ref.items()}})
    print("  wrote results/explore/e36_re_band.json")


if __name__ == "__main__":
    run()

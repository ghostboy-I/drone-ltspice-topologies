"""Exploration 39: catalogue motors with a 12 % torque reserve (queue item 47, 2026-11-18).

Entry 38's re-optimised optima ended at exactly 100 % of each motor's 100 %-throttle test torque (MN1123: 22.19 N m at
108.65 A against a 108 A peak; V13828: 43.1 N m at 245 A against a 245 A maximum). A design basis needs headroom for
gusts, motor ageing, battery sag and the BEMT's optimism, so here the hard torque limit is set to 0.88 x the test
torque (a 12 % reserve, I_max ~ 0.88 x I_test since Q ~ I):
  MN1123 KV53: 0.88 x 22.19 = 19.53 N m   (hex needs 20.5 at cap 0.60 on the fit: it must spin a little faster)
  V13828 55KV: 0.88 x 43.10 = 37.93 N m   (tri: Omega = P/Q ~ 15900/37.9 = 419 rad/s, tip Mach ~ 0.80)
The hex on the MN1320 (entry 38: 26.8 of 32.4 N m, 17 % reserve already) is carried over unchanged.
Reuses e37.job() with the catalogue torques scaled. 2 cores, nice 19, while the toroid CFD runs.
"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from multiprocessing import Pool
import e37_catalogue_motor as e37
import e38_motor_survey as e38

RES = 0.88
CAT = [(n, m, t * RES) for n, m, t in e38.CAT]
JOBS = [("hex", 0.60, "MN1123 KV53", "hard"), ("hex", 0.65, "MN1123 KV53", "hard"), ("tri", 0.75, "V13828 55KV", "hard"), ("tri", 0.80, "V13828 55KV", "hard")]


def job(a):
    e37.CAT = CAT
    return e37.job(a)


def run():
    from common import save_json
    with Pool(2) as pool:
        rows = pool.map(job, JOBS)
    save_json(os.path.join("explore", "e39_torque_reserve.json"), {"reserve": RES, "catalogue": CAT, "rows": rows})
    print("  wrote results/explore/e39_torque_reserve.json")


if __name__ == "__main__":
    run()

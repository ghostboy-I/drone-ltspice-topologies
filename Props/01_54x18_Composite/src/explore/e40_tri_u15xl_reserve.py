"""Exploration 40: the tri on the U15XL with the same 12 % torque reserve (queue item 49, 2026-11-18).

Entry 39: with 0.88 x test torque, the tri on the V13828 (37.9 N m) needs tip Mach 0.84 at T/W 2 for +4.37 kg at
61.4 dBA. The U15XL (4.408 kg, 50.4 N m) with the same reserve allows 0.88 x 50.4 = 44.35 N m:
  Omega = P/Q ~ 15900/44.35 = 358.5 rad/s, tip Mach 358.5 x 0.6858/357.6 = 0.688,
at 1.94 kg more motor per arm (5.8 kg per aircraft). Is the heavier but slower-turning, quieter design better?
Caps 0.65 and 0.70, hard penalty, reusing e37.job() with e39's scaled catalogue. 2 cores, nice 19 (toroid CFD running).
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from multiprocessing import Pool
import e37_catalogue_motor as e37
import e39_torque_reserve as e39

JOBS = [("tri", 0.65, "U15XL KV38", "hard"), ("tri", 0.70, "U15XL KV38", "hard")]


def job(a):
    e37.CAT = e39.CAT
    return e37.job(a)


def run():
    from common import save_json
    with Pool(2) as pool:
        rows = pool.map(job, JOBS)
    save_json(os.path.join("explore", "e40_tri_u15xl_reserve.json"), {"reserve": e39.RES, "catalogue": e39.CAT, "rows": rows})
    print("  wrote results/explore/e40_tri_u15xl_reserve.json")


if __name__ == "__main__":
    run()

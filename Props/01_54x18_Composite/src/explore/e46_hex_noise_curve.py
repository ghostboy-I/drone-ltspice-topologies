"""Exploration 46: the hex's payload-noise curve across catalogue motors at a 10 % torque reserve (queue item 51).

Entry 45 set the reserve at ~10 % (NdFeB remanence loss ~0.12 %/K over ~80 K of magnet heating). A motor with more
torque lets the hex spin slower (Omega = P/Q) and quieter, at more motor mass. Optimised here (e37 job(), hard
penalty, plain BEMT), torque limits 0.90 x test torque:
  MN1123 (1.425 kg, 19.97 N m) at caps 0.55 and 0.65;  MN1320 (2.070 kg, 29.2 N m);  V13823 (2.160 kg, 31.0 N m);
  V13828 (2.465 kg, 38.8 N m), at cap 0.60.
All in entry 11's hex frame, so payloads compare directly. 2 cores, nice 19 (toroid CFD running).
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from multiprocessing import Pool
import e37_catalogue_motor as e37
import e38_motor_survey as e38
from common import save_json

RES = 0.10
JOBS = [("hex", 0.55, "MN1123 KV53"), ("hex", 0.65, "MN1123 KV53"), ("hex", 0.60, "MN1320 KV49"), ("hex", 0.60, "V13823 60KV"), ("hex", 0.60, "V13828 55KV")]


def job(a):
    e37.CAT = [(n, m, t * (1 - RES)) for n, m, t in e38.CAT]
    return e37.job(a + ("hard",))


def run():
    with Pool(2) as pool:
        rows = pool.map(job, JOBS)
    for r in rows: r["fits"] = bool(r["fits"])
    save_json(os.path.join("explore", "e46_hex_noise_curve.json"), {"reserve": RES, "rows": rows}); print("  wrote results/explore/e46_hex_noise_curve.json")


if __name__ == "__main__":
    run()

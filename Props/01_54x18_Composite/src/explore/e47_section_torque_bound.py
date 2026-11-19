"""Exploration 47: does a low-drag section help a torque-bound catalogue design? (narrowed queue item 45, 2026-11-18)

Entry 36: the NACA 24xx-64 section's gain on the hex (+0.34 kg) came from lower drag at the T/W-2 point (Re ~1.1e6),
which shrank the torque-sized motor on the continuous fit. With catalogue motors the motor mass is fixed and the
torque is a hard limit: a lower-drag section should instead let the rotor reach T/W 2 at less torque, i.e. spin a
little slower for the same limit (quieter, lighter blade). Test, at the 10 % reserve of entries 45-46 (plain BEMT):
  hex MN1123 (19.97 N m) at cap 0.65 with 24xx-64 sections   vs entry 46's 24xx design (+5.46 kg, 50.3 dBA)
  tri V13828 (38.79 N m) at cap 0.80 with 24xx and with 24xx-64 outboard (44xx inboard hybrid)
Polars: the 24xx-64 set from entry 35 (cached). e24.db_for is redirected in the workers so the optimiser and the noise
model both see the new section. 2 cores, nice 19 (toroid CFD running).
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from multiprocessing import Pool
import e37_catalogue_motor as e37
import e38_motor_survey as e38
from common import save_json

RES = 0.10
JOBS = [("hex", 0.65, "MN1123 KV53", "64"), ("tri", 0.80, "V13828 55KV", None), ("tri", 0.80, "V13828 55KV", "64")]


def job(a):
    lay, cap, motor, suffix = a
    import e24_chain_best_blades as e24, e35_mod4_laminar as e35
    from blade_trade_study import HybridDB
    if suffix:
        thin, db44 = e35.dbs(suffix); orig = e24.db_for
        e24.db_for = lambda c, bset: (thin if c == "hex0" else HybridDB(thin, db44)) if bset == "best" else orig(c, bset)
    e37.CAT = [(n, m, t * (1 - RES)) for n, m, t in e38.CAT]
    r = e37.job((lay, cap, motor, "hard")); r["section"] = "24xx" + (f"-{suffix}" if suffix else ""); r["fits"] = bool(r["fits"]); return r


def run():
    with Pool(2) as pool:
        rows = pool.map(job, JOBS)
    save_json(os.path.join("explore", "e47_section_torque_bound.json"), {"reserve": RES, "rows": rows}); print("  wrote results/explore/e47_section_torque_bound.json")


if __name__ == "__main__":
    run()

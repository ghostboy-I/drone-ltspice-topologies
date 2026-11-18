"""Exploration 38: a wider motor catalogue, from a survey of 24S heavy-lift motors (2026-11-18).

Entry 37 found the hex's optimum (20.5 N m at T/W 2) falls in a gap of a three-motor T-Motor list (U15II 18.0 N m,
U15XL 50.4 N m), costing it 2.45 kg. Survey of manufacturer pages (100 %-throttle test torque, the same basis as
entries 10-37; mass with cables):
  T-Motor U15II KV80    1.740 kg  18.0 N m @ 143 A, 60 V  (store.tmotor.com goods id 732; 143 A = max continuous)
  T-Motor MN1123 KV53   1.425 kg  22.2 N m @ 108.7 A, 92.0 V, VZ42x16.5  (uav-en.tmotor.com; 108 A peak)
  T-Motor MN1320 KV49   2.070 kg  32.4 N m @ 149 A, 91.8 V, NS45x17.5  (uav-en.tmotor.com; 150 A peak)
  Hobbywing V13823 60KV 2.160 kg  34.4 N m @ 213 A, 92 V, 42x16.5  (hobbywing.com/en/products/v13823; 213 A max)
  Hobbywing V13828 55KV 2.465 kg  43.1 N m @ 245 A, 92 V, 45x18    (hobbywing.com/en/products/v13828; 245 A max)
  T-Motor U15XL KV38    4.408 kg  50.4 N m  (entry 10)
(MAD M40C30 PRO, 3.46 kg / 47.4 N m, only from a reseller page: listed, not used.)

The new motors are much lighter per N m (0.064-0.057 kg/N m) than the U15 line the fit was built on (0.097-0.087).
Here: (1) re-score the entry-28 cap-0.60 optima with the extended list; (2) re-optimise the hex with the MN1123 fixed (22.2 N m, hard
penalty: 8 % above the 20.5 N m it needs) and with the MN1320 fixed (torque to spare, so the optimiser can trade rpm for torque); (3) re-optimise the tri to the V13828,
43.1 N m, at caps 0.60 / 0.65 / 0.70 with entry 37's hard penalty (it needs 50.6 N m at cap 0.60, so it must spin
faster: Q = P / Omega). Reuses e37's job(). 2 cores, nice 19, while the toroid CFD runs.
"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from multiprocessing import Pool
import e37_catalogue_motor as e37

CAT = [("U13II KV65", 0.975, 11.4), ("U15II KV80", 1.740, 18.0), ("MN1123 KV53", 1.425, 22.19), ("MN1320 KV49", 2.070, 32.4), ("V13823 60KV", 2.160, 34.4),
       ("V13828 55KV", 2.465, 43.1), ("U15XL KV38", 4.408, 50.4)]
SRC = {"U15II KV80": "https://store.tmotor.com/goods.php?id=732", "MN1123 KV53": "https://uav-en.tmotor.com/2026/navigato_0403/1372.html", "MN1320 KV49": "https://uav-en.tmotor.com/2026/navigato_0403/1375.html",
       "V13823 60KV": "https://www.hobbywing.com/en/products/v13823", "V13828 55KV": "https://www.hobbywing.com/en/products/v13828"}
TEST = {"U15II KV80": (143.0, 3546, 80), "MN1123 KV53": (108.65, 3632, 53), "MN1320 KV49": (148.96, 3218, 49), "V13823 60KV": (212.9, 4260, 60), "V13828 55KV": (244.9, 3878, 55)}  # A, rpm, KV
JOBS = [("hex", 0.60, "MN1123 KV53", "hard"), ("hex", 0.60, "MN1320 KV49", "hard"), ("tri", 0.60, "V13828 55KV", "hard"), ("tri", 0.65, "V13828 55KV", "hard"), ("tri", 0.70, "V13828 55KV", "hard")]


def job(a):
    e37.CAT = CAT
    return e37.job(a)


def run():
    from common import RESULTS, save_json
    e37.CAT = CAT
    e28 = json.load(open(os.path.join(RESULTS, "explore", "e28_noise_cap.json")))
    rs = []
    for x in e28["rows"]:
        if x["cap"] != 0.60: continue
        n = 6 if x["layout"] == "hex" else 3; name, m = e37.pick(x["Q_max"])
        rs.append({"layout": x["layout"], "Q_max": x["Q_max"], "motor_fit_kg": x["motor_kg"], "catalogue": name, "catalogue_kg": m,
                   "payload_fit": x["payload"], "payload_cat": x["payload"] + n * (x["motor_kg"] - m)})
        print("  rescore:", rs[-1], flush=True)
    kt = {k: {"I": I, "Q": next(c[2] for c in CAT if c[0] == k), "Kt_ideal": 60 / (2 * 3.141592653589793 * kv), "Q_by_Kt": I * 60 / (2 * 3.141592653589793 * kv)} for k, (I, rpm, kv) in TEST.items()}
    with Pool(2) as pool:
        rows = pool.map(job, JOBS)
    save_json(os.path.join("explore", "e38_motor_survey.json"), {"catalogue": CAT, "sources": SRC, "kt_check": kt, "rescore": rs, "rows": rows})
    print("  wrote results/explore/e38_motor_survey.json")


if __name__ == "__main__":
    run()

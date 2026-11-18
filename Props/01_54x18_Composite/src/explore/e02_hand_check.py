"""Entry 02 hand check with thrust-weighted solidity sigma_e = 3 int sigma(x) x^2 dx (sigma(x) = N c(x) / (pi R)).
Blade-element hover with linear lift: CT/sigma_e = (a/6)(theta_75 - alpha_0 - 1.5 sqrt(CT/2)). Writes the hand values into the e02 JSON."""
import json, math, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import numpy as np
from scipy.optimize import brentq
from common import RESULTS, save_json
f = os.path.join(RESULTS, "explore", "e02_coax_two_point.json"); o = json.load(open(f))
a, a0 = 5.73, math.radians(-4.0)
def sig_e(b):
    r = np.array(b["r"]); R = r.max(); x = r / R; s = 2 * np.array(b["chord"]) / (math.pi * R)
    return float(3 * np.trapezoid(s * x * x, x))
def ct(theta, s):
    return brentq(lambda c: c / s - (a / 6) * (theta - a0 - 1.5 * math.sqrt(c / 2)), 1e-7, 0.05)
for r in o["runs"]:
    s, e = r["start"], r["end"]
    se0, se1 = sig_e(s["blade"]), sig_e(e["blade"])
    c0, c1 = ct(math.radians(s["theta75_deg"]), se0), ct(math.radians(e["theta75_deg"]), se1)
    r["hand"].update(sigma_e_start=se0, sigma_e_end=se1, rpm_ratio_hand_sigma_e=math.sqrt(c0 / c1))
    print(f"{r['label']}: sigma {s['solidity']:.3f}->{e['solidity']:.3f}, sigma_e {se0:.3f}->{se1:.3f}; RPM ratio hand(sigma) {r['hand']['rpm_ratio_hand']:.3f},"
          f" hand(sigma_e) {math.sqrt(c0/c1):.3f}, BEMT {r['hand']['rpm_ratio_bemt']:.3f}")
save_json(os.path.join("explore", "e02_coax_two_point.json"), o)

"""Exploration 06: coaxial rotor spacing h/D, hover against cruise against the mast.

Blade: entry 03's blade on both rotors, 54 in (entries 04-05: one blade, equal diameters).
Per spacing h:
  hover  - full coaxial model (vortex-cylinder interference, equal torque), e05_diameter_split.coax_split with s = 1
  cruise - each rotor at T/6 edgewise, plus the wake-overlap penalty 3 f (P_ind_one_disk - 2 P_ind). The upper wake is
           skewed back by chi = atan(mu / lambda) from the shaft, so at the lower disk it is displaced d = h tan(chi). The
           overlap f is the lens area of two circles of radius R whose centres are d apart, over pi R^2:
               f = [2 R^2 acos(d / 2R) - (d / 2) sqrt(4 R^2 - d^2)] / (pi R^2)
           (f = 1 at d = 0: fully stacked; f = 0.391 at d = R; f = 0 at d = 2R)
  mast   - carbon tube between the two motors: MAST_KG_PER_M per arm, cylinder drag Cd MAST_CD on MAST_OD x h, paid at
           a propulsive efficiency ETA_PROP: dP = 3 * 0.5 rho V^3 Cd OD h / ETA_PROP
Payload is relative to the tricopter (e03 bookkeeping), with the mast mass counted relative to h/D = 0.2, the spacing every
earlier entry assumed (so 0.2 reproduces entry 03's payload).

Hand checks (e06 hand section): kappa_int = P_ind(pair) / (2 P_ind(isolated rotor at T/2)) from BEMT against the momentum
estimate (hand() in e05) with the BEMT split; and the lens-area overlap at h/D = 0.2 from chi.
"""
import json, math, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from multiprocessing import Pool
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import bemt, momentum as mt
from config_study import load_final_blade, mission_pack
from blade_structure import blade_mass
import e01_coax_blade as e01
import e02_coax_two_point as e02
from e05_diameter_split import coax_split, hand, p_induced
from common import RESULTS, save_json

OUT = os.path.join(RESULTS, "explore")
SPACINGS = [0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50, 0.75]
MAST_KG_PER_M = 0.51    # assumption: 40 mm OD x 2 mm carbon tube (0.39 kg/m) + 30 % for motor plates and clamps
MAST_OD = 0.040         # m
MAST_CD = 1.2           # subcritical cylinder, Re = V d / nu ~ 4e4
ETA_PROP = 0.8          # assumption: drag power paid through the rotors at this propulsive efficiency
H_REF = 0.20


def blade_e03(p):
    e3 = json.load(open(os.path.join(OUT, "e03_structural_mass.json")))
    bd = next(r for r in e3["runs"] if r["label"] == e3["best"])["end"]["blade"]
    bb = load_final_blade(p)
    R = p["rotor"]["diameter_in"] * p["constants"]["inch_to_m"] / 2
    return bemt.Blade(R, p["rotor"]["hub_radius_m"], 2, bd["r"], bd["chord"], np.radians(bd["twist_deg"]), np.interp(bd["r"], bb.r_def, bb.tc_def))


def lens(d, R):
    d = min(d, 2 * R)
    return (2 * R * R * math.acos(d / (2 * R)) - d / 2 * math.sqrt(4 * R * R - d * d)) / (math.pi * R * R)


def case(hd):
    G = e01.G; p, ph1, db, hot = G["p"], G["ph1"], G["db"], G["hot"]
    ctx = e02.context(); whkg = p["mass"]["pack_wh_per_kg_cited"]
    b = blade_e03(p); R = b.R; h = hd * 2 * R
    t_h = ph1["vehicle"]["weight_n"] / 3; V = p["mission"]["cruise_speed_ms"]
    try:
        c = coax_split(b, b, db, hot, t_h, h)
        e = bemt.edgewise_at_thrust(b, db, hot, ctx["t_tot"] / 6, V, ctx["alpha"], kappa=p["rotor"]["kappa"])
        om = e["rpm"] * 2 * math.pi / 60; p_ind = e["T"] * e["lam0"] * om * R
        lam = e["lam0"] + V * math.sin(ctx["alpha"]) / (om * R); chi = math.atan2(e["mu"], lam)
        f = lens(h * math.tan(chi), R)
        mast_drag_w = 3 * 0.5 * hot["rho"] * V ** 3 * MAST_CD * MAST_OD * h / ETA_PROP
        cruise_rot = 6 * e["P"] + 3 * f * (ctx["p_ind_one_disk"] - 2 * p_ind)
        cruise = cruise_rot + mast_drag_w
        hover = 3 * c["P"]
        pack = mission_pack(p, ph1, hover, ctx["base_climb"] * hover / ctx["base_hover"], cruise)[0]
        mb = blade_mass(b.r_def, b.c_def, b.tc_def, b.r_hub, b.R)["total_kg"]
        mast_kg = 3 * MAST_KG_PER_M * (h - H_REF * 2 * R)
        hw = 3 * (ctx["motors_pair"] + 4 * mb + 2 * ctx["hub"] - ctx["arm_single"]) - ctx["tilt"] + mast_kg
        payload = -(hw + (pack - ctx["base_pack"]) / whkg)
        hc = hand(t_h, c["split_upper"], c["w"], c["rw"], c["vil"], c["kl"], R, R, hot["rho"])
        return {"h_over_D": hd, "h_m": h, "hover_w": hover, "cruise_w": cruise, "cruise_rotors_w": cruise_rot, "mast_drag_w": mast_drag_w,
                "mast_kg_vs_ref": mast_kg, "pack_wh": pack, "payload_kg": payload, "split_upper": c["split_upper"],
                "rpm_upper": c["upper"]["rpm"], "rpm_lower": c["lower"]["rpm"], "w": c["w"], "rw_over_R": c["rw"] / R, "k": c["ku"],
                "P_ind_pair_arm": p_induced(c["upper"]) + p_induced(c["lower"]), "P_ind_hand_arm": hc["P"],
                "chi_deg": math.degrees(chi), "wake_offset_over_R": h * math.tan(chi) / R, "overlap_f": f,
                "overlap_penalty_w": 3 * f * (ctx["p_ind_one_disk"] - 2 * p_ind), "p_ind_one_disk": ctx["p_ind_one_disk"], "p_ind_rotor_cruise": p_ind,
                "mu": e["mu"], "lam": lam}
    except Exception as ex:
        return {"h_over_D": hd, "error": repr(ex)}


def run():
    t0 = time.time()
    e01.init(); G = e01.G; p = G["p"]
    b = blade_e03(p); t_h = G["ph1"]["vehicle"]["weight_n"] / 3
    iso = bemt.hover_at_thrust(b, G["db"], G["hot"], t_h / 2)
    p_iso_ind = p_induced(iso); p_iso_ideal = (t_h / 2) ** 1.5 / math.sqrt(2 * G["hot"]["rho"] * math.pi * b.R ** 2)
    with Pool(4, initializer=e01.init) as pool:
        rows = pool.map(case, SPACINGS)
    ok = [r for r in rows if "error" not in r]
    for r in rows:
        if "error" in r: print("  ERROR", r)
    ref = next(r for r in ok if r["h_over_D"] == H_REF)
    for r in ok:
        r["kappa_bemt"] = r["P_ind_pair_arm"] / (2 * p_iso_ind)
        r["kappa_hand"] = r["P_ind_hand_arm"] / (2 * p_iso_ideal)
        print(f"  h/D {r['h_over_D']:.2f} ({100*r['h_m']:.0f} cm): pack {r['pack_wh']:.0f} Wh ({100*(r['pack_wh']/ref['pack_wh']-1):+.2f} %), hover {r['hover_w']:.0f} W,"
              f" cruise {r['cruise_w']:.0f} W (overlap f {r['overlap_f']:.3f} -> {r['overlap_penalty_w']:.0f} W, mast {r['mast_drag_w']:.0f} W),"
              f" kappa bemt/hand {r['kappa_bemt']:.3f}/{r['kappa_hand']:.3f}, payload {r['payload_kg']:+.2f} kg", flush=True)
    print(f"  reference h/D 0.2: pack {ref['pack_wh']:.0f} Wh (entries 03-05: 5778); chi {ref['chi_deg']:.1f} deg, d/R {ref['wake_offset_over_R']:.3f}, f {ref['overlap_f']:.3f}")
    out = {"rows": rows, "isolated_T_half": {"P": iso["P"], "P_ind": p_iso_ind, "P_ideal": p_iso_ideal, "rpm": iso["rpm"]},
           "assumptions": {"mast_kg_per_m": MAST_KG_PER_M, "mast_od_m": MAST_OD, "mast_cd": MAST_CD, "eta_prop": ETA_PROP}, "runtime_s": time.time() - t0}
    save_json(os.path.join("explore", "e06_coax_spacing.json"), out)
    plot(ok, ref)
    print(f"  wrote results/explore/e06_coax_spacing.json in {out['runtime_s']:.0f} s")


def plot(ok, ref):
    hd = [r["h_over_D"] for r in ok]
    fig, axs = plt.subplots(1, 3, figsize=(12, 3.3))
    axs[0].plot(hd, [100 * (r["pack_wh"] / ref["pack_wh"] - 1) for r in ok], "o-", color="#0b0b0b", label="pack energy")
    axs[0].plot(hd, [100 * (r["hover_w"] / ref["hover_w"] - 1) for r in ok], "s--", color="#2a78d6", label="hover power")
    axs[0].plot(hd, [100 * (r["cruise_w"] / ref["cruise_w"] - 1) for r in ok], "^--", color="#c0392b", label="cruise power")
    axs[0].axhline(0, color="#999", lw=.8); axs[0].set_xlabel("h / D"); axs[0].set_ylabel("change vs h/D = 0.2 [%]"); axs[0].legend(fontsize=7); axs[0].grid(alpha=.3)
    axs[1].plot(hd, [r["kappa_bemt"] for r in ok], "o-", color="#0b0b0b", label="BEMT")
    hp = os.path.join(OUT, "e06_hand_check.json")
    if os.path.exists(hp):          # two-region momentum bounds (e06_hand_check.py); run that script, then plot() again
        hcr = json.load(open(hp))["rows"]
        axs[1].fill_between([q["h_over_D"] for q in hcr], [q["kappa_optimal"] for q in hcr], [q["kappa_uniform"] for q in hcr], color="#2a78d6", alpha=.15)
        axs[1].plot([q["h_over_D"] for q in hcr], [q["kappa_uniform"] for q in hcr], "--", color="#2a78d6", label="momentum, uniform lower loading")
        axs[1].plot([q["h_over_D"] for q in hcr], [q["kappa_optimal"] for q in hcr], ":", color="#2a78d6", label="momentum, optimal lower loading")
    axs[1].axhline(math.sqrt(2), color="#999", ls=":", lw=.8); axs[1].axhline(1.2808, color="#999", ls="--", lw=.8)
    axs[1].text(hd[-1], math.sqrt(2), "√2 (h → 0)", fontsize=6, ha="right", va="bottom"); axs[1].text(hd[-1], 1.2808, "1.281 (far wake, Leishman)", fontsize=6, ha="right", va="bottom")
    axs[1].set_xlabel("h / D"); axs[1].set_ylabel("hover interference κ_int"); axs[1].legend(fontsize=7); axs[1].grid(alpha=.3)
    axs[2].plot(hd, [r["overlap_penalty_w"] for r in ok], "o-", color="#c0392b", label="cruise wake overlap")
    axs[2].plot(hd, [r["mast_drag_w"] for r in ok], "s-", color="#e08e0b", label="mast drag")
    axs[2].plot(hd, [r["hover_w"] - ref["hover_w"] for r in ok], "^-", color="#2a78d6", label="hover power vs 0.2")
    axs[2].set_xlabel("h / D"); axs[2].set_ylabel("vehicle power [W]"); axs[2].legend(fontsize=7); axs[2].grid(alpha=.3)
    fig.suptitle("Exploration 06: coaxial spacing - hover interference, cruise wake overlap and the mast", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "e06_coax_spacing.png"), dpi=140); plt.close(fig)


if __name__ == "__main__":
    if sys.argv[1:] == ["plot"]:      # redraw from the saved results
        rows = [r for r in json.load(open(os.path.join(OUT, "e06_coax_spacing.json")))["rows"] if "error" not in r]
        plot(rows, next(r for r in rows if r["h_over_D"] == H_REF))
    else:
        run()

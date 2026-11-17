"""Blade-count and camber trade at 54 in: does a 3-blade rotor or a 64xx (6 % camber) section beat the Phase 2 blade?

Each case repeats the Phase 2 hover design exactly (MIL + manufacturing rules + re-twist, design-RPM sweep, same selection
rule), with no two-point refinement, so all columns compare like with like. The 2-blade 44xx case reproduces the
unrefined Phase 2 design and is the regression check (7622 Wh).

Cases
  2-blade 44xx           Phase 2 baseline
  3-blade 44xx           same rules, N = 3
  2-blade 64/44 hybrid   6 % camber where t/c >= 15 % (r < ~0.43 R), 4 % where t/c <= 12 % (r > 0.60 R), blended between
  2-blade 64xx           6 % camber full span (upper bound on what camber can give)
  3-blade 64/44 hybrid   both changes together

Hybrid section model: cl, cd and the section properties are blended linearly between the two families at the same
(t/c, Re, Mach, alpha). That is linear interpolation in camber between 4 % and 6 %, which is reasonable below stall
for NACA 4-digit sections (thin-airfoil theory: zero-lift angle and cm are linear in camber), less so near stall.

Hand checks written to the JSON:
  Tip loss (Prandtl, Leishman eq. 3.105): effective radius B = 1 - sqrt(2 CT) / N, induced power ~ 1/B, so going from
  2 to 3 blades at the same CT should cut induced power by 1 - B2/B3.
  Profile power: P0 = rho A (Omega R)^3 sigma cd0 / 8 with the BEMT's own thrust-weighted cd0, against BEMT P - Pi.
"""
import json, math, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import airfoils, design_opt as do, atmosphere as atm, momentum as mt
from phase2 import Rotor, SCAL
from common import RESULTS, load_params, save_json


class HybridDB:
    """Camber blended by thickness: weight on the 'thick' family w = clip((tc - tc_lo) / (tc_hi - tc_lo), 0, 1)."""
    def __init__(self, thin_db, thick_db, tc_lo=0.12, tc_hi=0.15):
        self.a, self.b, self.lo, self.hi = thin_db, thick_db, tc_lo, tc_hi
        self.family = f"{thick_db.family}/{thin_db.family}"

    def _w(self, tc):
        return np.clip((np.asarray(tc, float) - self.lo) / (self.hi - self.lo), 0.0, 1.0)

    def lookup(self, tc, re, mach, alpha):
        w = self._w(tc)
        cla, cda = self.a.lookup(tc, re, mach, alpha); clb, cdb = self.b.lookup(tc, re, mach, alpha)
        return (1 - w) * cla + w * clb, (1 - w) * cda + w * cdb

    def prop(self, name, tc, re, mach):
        w = self._w(tc)
        return (1 - w) * self.a.prop(name, tc, re, mach) + w * self.b.prop(name, tc, re, mach)


def hub_ripple(e, n_blades):
    """Hub roll-moment and thrust ripple (half peak-to-peak) from the per-azimuth loads of one blade in cruise.
    Blade k sits at psi + 2 pi k / N; with n_psi divisible by N that is an index shift."""
    psi, r, dFz = e["psi"], e["r"], e["dFz"]
    n_psi = len(psi); sh = n_psi // n_blades
    assert sh * n_blades == n_psi
    m1 = (dFz * r[None, :]).sum(axis=1) * np.sin(psi)          # one blade's roll-moment contribution vs azimuth
    t1 = dFz.sum(axis=1)
    M = sum(np.roll(m1, -k * sh) for k in range(n_blades)); T = sum(np.roll(t1, -k * sh) for k in range(n_blades))
    return {"roll_mean": float(M.mean()), "roll_ripple": float((M.max() - M.min()) / 2), "thrust_ripple": float((T.max() - T.min()) / 2),
            "ripple_freq_per_rev": n_blades}


def run(n_proc=4):
    t0 = time.time()
    p = load_params()
    ph1 = json.load(open(os.path.join(RESULTS, "phase1.json")))
    c, rot, d = p["constants"], p["rotor"], p["design"]
    db44, _ = airfoils.build_db(p)
    p64 = json.loads(json.dumps(p)); p64["airfoils"]["family"] = "64"; p64["airfoils"]["compare_sections"] = []
    db64, _ = airfoils.build_db(p64, n_proc=n_proc)            # XFOIL runs once, then cached in results/polars
    print(f"  polars ready [{time.time()-t0:.0f}s]; 64xx failed cases: {db64.failed}", flush=True)
    hyb = HybridDB(db44, db64)
    A = {k: atm.state(v["temp_c"], v["alt_m"]) for k, v in p["atmospheres"].items()}
    dkey = p["design_atmosphere"]; hot = A[dkey]
    R, rh, t_h = rot["diameter_in"] * c["inch_to_m"] / 2, rot["hub_radius_m"], ph1["vehicle"]["t_hover"]
    cases = [("2-blade 44xx", 2, db44), ("3-blade 44xx", 3, db44), ("2-blade 64/44 hybrid", 2, hyb),
             ("2-blade 64xx", 2, db64), ("3-blade 64/44 hybrid", 3, hyb)]
    out = {"polar_failed_64": [list(f) for f in db64.failed], "cases": {}}
    for name, N, db in cases:
        sweep = []
        for rpm in d["hover_rpm_sweep"]:
            blade, raw = do.design_hover_blade(R, rh, N, rpm, t_h, hot, db, d, d["cl_design"])
            r_ = Rotor(f"{name} {rpm}", blade, db, p, A, ph1)
            s = r_.summary(full=False); s["design_rpm"] = rpm; s["raw_chord_max_mm"] = 1000 * float(raw["chord"].max())
            h = r_.hover(dkey)
            pi = float(np.sum(h["vi"] * h["dT_dr"] * h["dr"]))                         # induced power, hover (V = 0)
            s["P_induced"], s["P_profile"] = pi, float(h["P"] - pi)
            s["cd0_thrust_weighted"] = float(np.sum(h["cd"] * h["dT_dr"] * h["dr"]) / h["T"])
            s["blade_volume_total_cm3"] = N * s["volume_cm3"]
            s["hub_15"] = hub_ripple(r_.cruise(dkey, p["mission"]["cruise_speed_ms"]), N)
            sweep.append(s)
            print(f"  {name} {rpm}: FoM {s['hover']['FoM']:.3f} T/W {s['motor_u15xl_sag']['tw']:.2f} pack {s['mission']['pack_wh']:.0f} Wh margin {s['stall_margin_deg']:.1f} [{time.time()-t0:.0f}s]", flush=True)
        ok = [s for s in sweep if s["stall_margin_deg"] >= d["min_stall_margin_deg"] and s["tw_target"] and s["tw_target"]["mach_ok"]]
        sel = max(ok, key=lambda s: s["motor_u15xl_sag"]["tw"]) if ok else None
        lowE = min(ok, key=lambda s: s["mission"]["pack_wh"]) if ok else None
        out["cases"][name] = {"n_blades": N, "family": getattr(db, "family", "?"), "sweep": sweep,
                              "selected_rpm": sel and sel["design_rpm"], "lowest_energy_rpm": lowE and lowE["design_rpm"], "n_eligible": len(ok)}

    # ---- hand checks ----------------------------------------------------------------------------------------
    base = next(s for s in out["cases"]["2-blade 44xx"]["sweep"] if s["design_rpm"] == out["cases"]["2-blade 44xx"]["selected_rpm"])
    hc = {}
    om = base["hover"]["rpm"] * 2 * math.pi / 60; vt = om * R; area = math.pi * R * R
    ct = t_h / (hot["rho"] * area * vt * vt)
    B2, B3 = 1 - math.sqrt(2 * ct) / 2, 1 - math.sqrt(2 * ct) / 3
    hc["CT_h_baseline"] = ct; hc["B2"], hc["B3"] = B2, B3
    hc["induced_cut_2_to_3_hand_pct"] = 100 * (1 - B2 / B3)
    for N_ in (2, 3):
        s = next(q for q in out["cases"][f"{N_}-blade 44xx"]["sweep"] if q["design_rpm"] == out["cases"]["2-blade 44xx"]["selected_rpm"])
        om_ = s["hover"]["rpm"] * 2 * math.pi / 60
        hc[f"profile_hand_W_{N_}"] = hot["rho"] * area * (om_ * R) ** 3 * s["solidity"] * s["cd0_thrust_weighted"] / 8
        hc[f"profile_bemt_W_{N_}"] = s["P_profile"]; hc[f"induced_bemt_W_{N_}"] = s["P_induced"]
    hc["note"] = "Profile hand calc uses the thrust-weighted cd from the BEMT solution and the BEMT hover RPM, at the 2-blade selected design RPM for both blade counts."
    s3 = next(q for q in out["cases"]["3-blade 44xx"]["sweep"] if q["design_rpm"] == out["cases"]["2-blade 44xx"]["selected_rpm"])
    hc["induced_cut_2_to_3_bemt_pct"] = 100 * (1 - s3["P_induced"] / base["P_induced"])
    out["hand_checks"] = hc
    out["regression_baseline_pack_wh"] = base["mission"]["pack_wh"]
    out["runtime_s"] = time.time() - t0
    save_json("blade_trade.json", out)
    plot(out, d)
    return out


def plot(out, d):
    cols = ["#0b0b0b", "#2a78d6", "#c0392b", "#e08e0b", "#5b8c3a"]
    fig, axs = plt.subplots(1, 3, figsize=(9.5, 3.1))
    for (name, cs), col in zip(out["cases"].items(), cols):
        sw = cs["sweep"]; x = [s["design_rpm"] for s in sw]
        axs[0].plot(x, [s["mission"]["pack_wh"] / 1000 for s in sw], "o-", color=col, label=name)
        axs[1].plot(x, [s["hover"]["FoM"] for s in sw], "o-", color=col)
        axs[2].plot(x, [s["motor_u15xl_sag"]["tw"] for s in sw], "o-", color=col)
        sel = cs["selected_rpm"]
        if sel:
            s = next(q for q in sw if q["design_rpm"] == sel)
            axs[0].plot(sel, s["mission"]["pack_wh"] / 1000, "s", ms=9, mfc="none", color=col)
    axs[0].set_ylabel("mission pack energy [kWh]"); axs[1].set_ylabel("hover figure of merit"); axs[2].set_ylabel("T/W on U15XL at 84 V")
    for a in axs: a.set_xlabel("design hover RPM"); a.grid(alpha=.3)
    axs[0].legend(fontsize=6)
    fig.suptitle("Blade count and camber trade, 54 in, hot day (squares: design picked by the Phase 2 rule)", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(RESULTS, "blade_trade.png"), dpi=150); plt.close(fig)


if __name__ == "__main__":
    o = run(); print(f"wrote results/blade_trade.json in {o['runtime_s']:.0f} s")

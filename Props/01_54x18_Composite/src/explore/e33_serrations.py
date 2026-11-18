"""Exploration 33: trailing-edge serrations as the noise lever, for the tri and hex hover rotors of entry 28.

Entries 30-32: BPM trailing-edge (TE) noise sets the A-weighted hover level of every design, and planform changes only
trade TE against tip noise. Serrations (sawtooth trailing edges) act on the TE source itself.

Serration model (engineering bracket, not a theory):
  * Howe (1991) sawtooth theory: for omega h / U_c >> 1 the TE spectrum falls by about 10 log10(1 + (4h/lambda)^2) dB
    (h half the tooth amplitude... here 2h = tooth root-to-tip length, lambda = tooth wavelength). Experiments get much less:
    wind-tunnel and full-scale wind-turbine tests (Oerlemans et al. 2009; Gruber 2012) show 2-6 dB in the mid band and a
    slight INCREASE above a crossover near f delta / U ~ 1 (delta = boundary-layer thickness ~ 8 delta*, 1/7-power law).
  * so per strip, per band: SPL_p and SPL_s are reduced by D dB for f < U / delta and raised by 1 dB above it; the
    angle-of-attack term SPL_alpha (suction-side, thickened BL) is reduced by D_alpha = D/2 (serrations are less effective
    at incidence; Gruber's alpha trend). Scenarios D = 2, 4, 6 dB.
  * cost: serrations are a thin extension of the TE; tests show a profile-drag increase of a few per cent. Modelled as
    Cd x 1.03 (sensitivity x 1.06), pack energy scaled with hover power (hover dominates the mission energy), plus a
    serration mass of 15 g per blade.
Tip vortex (entry 31, max-Gamma angle, rounded tip) and Gutin tones unchanged. Noise parity: tri cap that meets the hex's
cap-0.60 total (both serrated alike), payload interpolated along entry 28's cap sweep.
"""
import json, math, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from multiprocessing import Pool
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

DS = (0.0, 2.0, 4.0, 6.0)
UP = 1.0
CD_SCALES = (1.03, 1.06)
SERR_KG_PER_BLADE = 0.015


class CdScaled:
    def __init__(self, db, k): self.db, self.k = db, k
    def lookup(self, *a):
        cl, cd = self.db.lookup(*a); return cl, cd * self.k
    def __getattr__(self, n): return getattr(self.db, n)


def job(row):
    import bemt, bpm, e01_coax_blade as e01, e02_coax_two_point as e02, e24_chain_best_blades as e24, e30_bpm_rotor as e30, e31_tip_noise as e31
    e01.init(); G = e01.G; p, hot = G["p"], G["hot"]; c = row["layout"]; n = e30.LAY[c][1]; Wv = G["ph1"]["vehicle"]["weight_n"]
    db = e24.db_for(e30.LAY[c][0], "best"); Rr = p["rotor"]["diameter_in"] * p["constants"]["inch_to_m"] / 2
    b = e02.blade_from(row["blade"], Rr, p["rotor"]["hub_radius_m"]); h = bemt.hover_at_thrust(b, db, hot, Wv / n)
    nu = hot["mu"] / hot["rho"]
    obs = np.array([math.sin(e30.THETA), 0.0, math.cos(e30.THETA)]) * e30.S_OBS
    F = bpm.BANDS; msq = {D: np.zeros(len(F)) for D in DS}; hand = None
    for k in range(len(h["r"])):
        r, dr, ch, w, tc = float(h["r"][k]), float(h["dr"][k]), float(h["chord"][k]), float(h["W"][k]), float(h["tc"][k])
        if w <= 1 or r < 0.25 * Rr: continue
        astar = float(np.degrees(h["alpha"][k])) - e30.alpha_l0(db, tc, float(h["re"][k]), min(float(h["mach"][k]), 0.6))
        acc = {D: np.zeros(len(F)) for D in DS}
        for j in range(e30.NPSI):
            psi = 2 * math.pi * j / e30.NPSI
            pos = np.array([r * math.cos(psi), r * math.sin(psi), 0.0]); tang = np.array([-math.sin(psi), math.cos(psi), 0.0])
            xe, ye, ze = -tang, pos / r, np.array([0.0, 0.0, 1.0])
            d = obs - pos; re_ = float(np.linalg.norm(d)); x, y, z = d @ xe, d @ ye, d @ ze
            phi = math.atan2(abs(z), y); theta = math.atan2(y * math.cos(phi) + abs(z) * math.sin(phi), x)
            o = bpm.tbl_te(ch, dr, w, astar, re_, theta=theta, phi=phi, c0=hot["a"], nu=nu)
            fc = w / (8 * o["dstar_s"])                                    # crossover f = U / delta, delta ~ 8 delta*
            below = F < fc
            for D in DS:
                dps = np.where(below, -D, UP if D > 0 else 0.0); da = np.where(below, -D / 2, UP if D > 0 else 0.0)
                acc[D] += 10 ** ((o["p"] + dps) / 10) + 10 ** ((o["s"] + dps) / 10) + 10 ** ((o["alpha"] + da) / 10)
        for D in DS: msq[D] += acc[D] / e30.NPSI
        if hand is None and r / Rr >= 0.75:
            hand = {"r_over_R": r / Rr, "W": w, "dstar_s": o["dstar_s"], "f_cross": fc, "p": o["p"].tolist(), "s": o["s"].tolist(), "alpha": o["alpha"].tolist()}
    tip = e31.tip_rotor(c, row["blade"]); tip_msq = 10 ** (np.array(tip["rounded_G"]["spectrum"]) / 10)
    ton = e30.e27.levels(h, b.N, hot["a"], n, e30.THETA)
    out = {"layout": c, "cap": row["cap"], "dpayload_vs_060": row["dpayload_vs_060"], "tonal_dba": ton["dba"], "hand_strip": hand, "D": {}}
    for D in DS:
        te = msq[D] * n * b.N
        bb = e31.dba(te + tip_msq)
        out["D"][str(D)] = {"te_dba": e31.dba(te), "te_spectrum": (10 * np.log10(te)).tolist(), "broadband_dba": bb,
                            "total_dba": 10 * math.log10(10 ** (bb / 10) + 10 ** (ton["dba"] / 10))}
    out["P_hover"] = float(h["P"]) * n
    for kcd in CD_SCALES:
        out[f"P_hover_cd{kcd}"] = float(bemt.hover_at_thrust(b, CdScaled(db, kcd), hot, Wv / n)["P"]) * n
    out["n_blades"] = n * b.N
    print(f"  {c} cap {row['cap']:.2f}: TE dBA " + ", ".join(f"D{D:.0f} {out['D'][str(D)]['te_dba']:.1f}" for D in DS) +
          f"; total " + ", ".join(f"{out['D'][str(D)]['total_dba']:.1f}" for D in DS) + f"; P_hover {out['P_hover']:.0f} W, cd x1.03 {out['P_hover_cd1.03']:.0f} W", flush=True)
    return out


def run():
    from common import RESULTS, save_json
    import e01_coax_blade as e01
    OUT = os.path.join(RESULTS, "explore"); e28 = json.load(open(os.path.join(OUT, "e28_noise_cap.json")))
    with Pool(4) as pool:
        rows = pool.map(job, e28["rows"])
    e01.init(); whkg = e01.G["p"]["mass"]["pack_wh_per_kg_cited"]
    packs = {(r["layout"], r["cap"]): r["pack"] for r in e28["rows"]}
    par = {}
    for D in DS:
        key = str(D); hx = next(x for x in rows if x["layout"] == "hex" and x["cap"] == 0.60)
        tri = sorted((x for x in rows if x["layout"] == "tri"), key=lambda x: x["cap"])
        xs = [x["D"][key]["total_dba"] for x in tri]; ys = [x["dpayload_vs_060"] for x in tri]; lim = hx["D"][key]["total_dba"]
        cost = float(np.interp(lim, xs, ys)) if xs[0] <= lim <= xs[-1] else (0.0 if lim > xs[-1] else None)
        par[key] = {"hex_total_dba": lim, "tri_total_dba_060": tri[-1]["D"][key]["total_dba"], "tri_parity_cost_kg": cost}
    pen = {}
    for x in rows:
        if x["cap"] != 0.60: continue
        e = {}
        for kcd in CD_SCALES:
            frac = x[f"P_hover_cd{kcd}"] / x["P_hover"] - 1; dpack = frac * packs[(x["layout"], 0.60)]
            e[str(kcd)] = {"hover_power_frac": frac, "dpack_wh": dpack, "dpayload_kg": -(dpack / whkg + SERR_KG_PER_BLADE * x["n_blades"])}
        pen[x["layout"]] = e
    print("  parity:", json.dumps(par, indent=1)); print("  penalty:", json.dumps(pen, indent=1))
    save_json(os.path.join("explore", "e33_serrations.json"), {"scenarios_dB": DS, "up_dB": UP, "rows": rows, "parity": par, "penalty": pen, "whkg": whkg})
    plot(rows, par, OUT); print("  wrote results/explore/e33_serrations.json"); frontier()


def plot(rows, par, OUT):
    fig, axs = plt.subplots(1, 2, figsize=(10, 3.6)); col = {"tri": "#0b0b0b", "hex": "#2a78d6"}; F = [100, 125, 160, 200, 250, 315, 400, 500, 630, 800, 1000, 1250, 1600, 2000, 2500, 3150, 4000, 5000, 6300, 8000, 10000, 12500, 16000, 20000]
    for x in rows:
        if x["cap"] != 0.60: continue
        for D, ls in (("0.0", "-"), ("4.0", "--")):
            axs[0].semilogx(F, x["D"][D]["te_spectrum"], ls, color=col[x["layout"]], label=f"{x['layout']} TE, serration D = {float(D):.0f} dB")
    axs[0].set_xlabel("1/3-octave band [Hz]"); axs[0].set_ylabel("TE SPL [dB] at 50 m"); axs[0].set_ylim(0, 50); axs[0].grid(alpha=.3, which="both"); axs[0].legend(fontsize=6)
    for c in ("tri", "hex"):
        rs = sorted((x for x in rows if x["layout"] == c), key=lambda x: x["cap"])
        for D, ls in (("0.0", "o-"), ("4.0", "s--")):
            axs[1].plot([x["D"][D]["total_dba"] for x in rs], [x["dpayload_vs_060"] for x in rs], ls, color=col[c], label=f"{c}, D = {float(D):.0f} dB")
    axs[1].set_xlabel("total hover level [dBA] at 50 m"); axs[1].set_ylabel("payload vs own cap-0.60 optimum [kg]"); axs[1].grid(alpha=.3); axs[1].legend(fontsize=6)
    fig.suptitle("Exploration 33: trailing-edge serrations (BPM TE components reduced below f = U/delta), rounded tips", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "e33_serrations.png"), dpi=140); plt.close(fig)


if __name__ == "__main__":
    run()


def frontier(limits=np.arange(45.0, 52.01, 1.0)):
    """Best payload per layout under an absolute dBA limit, choosing the cap and the serration level D (penalty Cd x1.03 +
    mass when D > 0); hex - tri margins in the 15 m/s and free-speed (constant body, 303 Wh/kg) frames of entry 30."""
    from common import RESULTS, save_json
    OUT = os.path.join(RESULTS, "explore"); o = json.load(open(os.path.join(OUT, "e33_serrations.json")))
    base = {"15 m/s, 303": 1.73, "free, constant body, 303": -2.19, "free, bluff, 303": -1.11, "free, constant body, 200": 0.11}
    res = []
    for Dm, L in [(Dm, L) for Dm in o["scenarios_dB"][1:] for L in limits]:   # D is the assumed effectiveness; each layout picks none or D
        best = {}
        for c in ("tri", "hex"):
            rs = sorted((x for x in o["rows"] if x["layout"] == c), key=lambda x: x["cap"]); opts = []
            for D in ("0.0", str(Dm)):
                xs = [x["D"][D]["total_dba"] for x in rs]; ys = [x["dpayload_vs_060"] for x in rs]
                if L < xs[0]: continue
                pay = 0.0 if L >= xs[-1] else float(np.interp(L, xs, ys))
                if float(D) > 0: pay += o["penalty"][c]["1.03"]["dpayload_kg"]
                opts.append((pay, float(D)))
            best[c] = max(opts) if opts else None
        row = {"D_effectiveness": Dm, "limit_dba": float(L), "tri": best["tri"], "hex": best["hex"]}
        if best["tri"] and best["hex"]:
            row["hex_minus_tri"] = {k: v + best["hex"][0] - best["tri"][0] for k, v in base.items()}
        res.append(row)
        print(f"  D {Dm:.0f}, limit {L:.1f}: tri {best['tri']}, hex {best['hex']}" + (f"; hex-tri {row['hex_minus_tri']}" if "hex_minus_tri" in row else ""))
    o["frontier"] = res; save_json(os.path.join("explore", "e33_serrations.json"), o)

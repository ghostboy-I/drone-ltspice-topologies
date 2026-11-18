"""Exploration 07: check entry 06's cruise wake-overlap model with a prescribed skewed vortex wake (Biot-Savart).

Entry 06 modelled the upper rotor's cruise wake as a rigid tube: inside the lens where it crosses the lower disk the lower
rotor sees the fully developed far-wake velocity 2 v_i, outside it sees nothing. Penalty per arm = f x 2 P_ind(one rotor).

Here each rotor's wake is a skewed vortex cylinder (the classic Coleman / Castles-de Leeuw model of a uniformly loaded disk
in forward flight): a stack of horizontal vortex rings of radius R whose centres move down the wake axis
    e = (sin chi, 0, -cos chi)   (x aft, z up along the shaft),   tan chi = mu / lambda
The ring strength is scaled so that the rotor's own normal induced velocity at its hub equals v_i0 = lambda_i Omega R from
the BEMT cruise solution (the uniform-inflow value). The velocity is then computed by Biot-Savart (straight segments,
Rankine core 0.05 R) at points over the other rotor's disk:
    upper wake -> lower disk at z = -h:  w_l(r, psi),   lower wake -> upper disk at z = +h above its start:  w_u(r, psi)
With uniform loading (dT = T dA / A) the extra induced power of each rotor is T x (area-mean normal velocity):
    dP_arm = T_l mean(w_l) + T_u mean(w_u)
and that replaces the lens term. The rigid wake (no roll-up, no downward deflection by its own induction) is still an
assumption: it is the standard prescribed-wake level of fidelity, one step above the lens.

Checks on the Biot-Savart code (hand formulas):
  1. hover (chi = 0), on the axis a distance z below the disk: w(z) / w(0) = 1 + z / sqrt(R^2 + z^2)
  2. cruise, own wake over the own disk: Coleman's linear inflow v = v_0 (1 + K_x (r/R) cos psi) with K_x = tan(chi / 2)
"""
import json, math, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from config_study import mission_pack
import e01_coax_blade as e01
import e02_coax_two_point as e02
from common import RESULTS, save_json

OUT = os.path.join(RESULTS, "explore")
R = 0.6858
N_SEG, CORE, L_WAKE, DS = 72, 0.05, 30.0, 0.05      # segments per ring, core / R, wake length / R, ring spacing / R


def rings(chi, z0=0.0, R=R, length=L_WAKE * R, ds=DS * R):
    """Segment start/end points of the ring stack. Ring k centre z0-plane origin + s_k e. Ring circulation gamma*dz (gamma = 1)."""
    e = np.array([math.sin(chi), 0.0, -math.cos(chi)])
    s = np.arange(0.5 * ds, length, ds)
    th = np.linspace(0, 2 * math.pi, N_SEG + 1)
    circ = np.stack([R * np.cos(th), R * np.sin(th), np.zeros_like(th)], 1)            # counter-clockwise from above
    cen = s[:, None] * e[None, :] + np.array([0, 0, z0])
    pts = cen[:, None, :] + circ[None, :, :]                                           # (rings, N_SEG+1, 3)
    gam = np.full(len(s), ds * math.cos(chi))                                          # sheet strength per unit axial length
    return pts[:, :-1].reshape(-1, 3), pts[:, 1:].reshape(-1, 3), np.repeat(gam, N_SEG)


def biot_savart(a, b, g, x, core=CORE * R):
    """Velocity at points x (n,3) from straight segments a->b (m,3) with circulation g (m). Chunked over points."""
    out = np.zeros_like(x)
    for i in range(0, len(x), 16):
        p = x[i:i + 16, None, :]
        r1, r2 = p - a[None], p - b[None]; r0 = (b - a)[None]
        cr = np.cross(r1, r2); cr2 = np.sum(cr * cr, -1)
        n1, n2 = np.linalg.norm(r1, axis=-1), np.linalg.norm(r2, axis=-1)
        l0 = np.linalg.norm(r0, axis=-1)
        d2 = cr2 / np.maximum(l0 ** 2, 1e-30)                                           # squared distance to the segment line
        k = g[None] / (4 * math.pi) * np.sum(r0 * (r1 / n1[..., None] - r2 / n2[..., None]), -1) / np.maximum(cr2, 1e-30)
        k = k * d2 / np.sqrt(d2 * d2 + core ** 4)                                        # smooth core (Rankine-like, Vatistas n = 2)
        out[i:i + 16] = np.sum(k[..., None] * cr, 1)
    return out


def disk_points(z, nr=10, npsi=36, R=R):
    rr = (np.arange(nr) + 0.5) / nr * R; ps = np.arange(npsi) * 2 * math.pi / npsi
    Rg, Pg = np.meshgrid(rr, ps, indexing="ij")
    # psi = 0 at the tail (+x, downstream), counter-clockwise from above
    x = np.stack([Rg.ravel() * np.cos(Pg.ravel()), Rg.ravel() * np.sin(Pg.ravel()), np.full(Rg.size, z)], 1)
    wgt = (Rg * (R / nr)).ravel(); return x, wgt / wgt.sum(), Rg.ravel(), Pg.ravel()


def down(v):
    return -v[:, 2]                                                                      # normal velocity, positive down through the disk


def checks():
    out = {}
    # 1. hover cylinder on axis
    a, b, g = rings(0.0)
    zs = np.array([0.0, 0.1, 0.2, 0.4, 1.0, 2.0]) * R
    w = down(biot_savart(a, b, g, np.stack([np.zeros_like(zs), np.zeros_like(zs), -zs], 1)))
    out["hover_axis"] = [{"z_over_R": float(z / R), "ratio_bs": float(w[i] / w[0]), "ratio_hand": float(1 + z / math.sqrt(R * R + z * z))} for i, z in enumerate(zs)]
    return out


def own_disk(chi):
    a, b, g = rings(chi)
    x, wgt, rr, ps = disk_points(-1e-4 * R)
    w = down(biot_savart(a, b, g, x))
    w0 = float(down(biot_savart(a, b, g, np.array([[0, 0, -1e-4 * R]])))[0])
    # least-squares fit v = v0 (1 + Kx r/R cos psi + Ky r/R sin psi)
    A = np.stack([np.ones_like(rr), rr / R * np.cos(ps), rr / R * np.sin(ps)], 1)
    c = np.linalg.lstsq(A, w, rcond=None)[0]
    return w0, {"v0_fit": c[0], "Kx_fit": c[1] / c[0], "Ky_fit": c[2] / c[0], "Kx_coleman": math.tan(chi / 2), "mean_over_centre": float(np.sum(w * wgt) / w0)}


def interference(chi, h, w0_unit):
    """Area-mean normal velocity (per unit own-hub induced velocity) that each rotor's wake induces over the other disk."""
    au, bu, gu = rings(chi, 0.0)
    al, bl, gl = rings(chi, -h)
    xl, wl, rl, pl = disk_points(-h); xu, wu, ru, pu = disk_points(0.0)
    w_l = down(biot_savart(au, bu, gu, xl)) / w0_unit       # upper wake on the lower disk
    w_u = down(biot_savart(al, bl, gl, xu)) / w0_unit       # lower wake on the upper disk (ahead and above it)
    return float(np.sum(w_l * wl)), float(np.sum(w_u * wu)), w_l, w_u, rl, pl


def run():
    t0 = time.time()
    e06 = json.load(open(os.path.join(OUT, "e06_coax_spacing.json")))
    rows6 = [r for r in e06["rows"] if "error" not in r]
    r0 = rows6[0]; chi = math.atan2(r0["mu"], r0["lam"])
    ck = checks()
    for q in ck["hover_axis"]: print(f"  hover axis z/R {q['z_over_R']:.1f}: BS {q['ratio_bs']:.4f}  hand {q['ratio_hand']:.4f}")
    w0, col = own_disk(chi); ck["coleman"] = col
    print(f"  own disk at chi {math.degrees(chi):.1f} deg: Kx fit {col['Kx_fit']:.3f} vs tan(chi/2) {col['Kx_coleman']:.3f}, Ky {col['Ky_fit']:.3f}, mean/centre {col['mean_over_centre']:.3f}")
    e01.init(); G = e01.G; p, ph1 = G["p"], G["ph1"]; ctx = e02.context()
    T_rot = ctx["t_tot"] / 6
    rows = []
    for r in rows6:
        h = r["h_m"]; vi0 = r["p_ind_rotor_cruise"] / T_rot          # own uniform induced velocity from BEMT, P_ind = T v_i0
        ml, mu_, w_l, w_u, rl, pl = interference(chi, h, w0)
        dP = 3 * T_rot * vi0 * (ml + mu_)                             # vehicle: 3 arms, each rotor at T_rot
        lens = r["overlap_penalty_w"]
        cruise_bs = r["cruise_w"] - lens + dP
        pack_bs = mission_pack(p, ph1, r["hover_w"], ctx["base_climb"] * r["hover_w"] / ctx["base_hover"], cruise_bs)[0]
        rows.append({"h_over_D": r["h_over_D"], "vi0": vi0, "mean_w_lower_over_vi0": ml, "mean_w_upper_over_vi0": mu_, "penalty_bs_w": dP,
                     "penalty_lens_w": lens, "f_lens": r["overlap_f"], "lens_equiv_w_lower_over_vi0": 2 * r["overlap_f"],
                     "cruise_lens_w": r["cruise_w"], "cruise_bs_w": cruise_bs, "pack_lens_wh": r["pack_wh"], "pack_bs_wh": pack_bs,
                     "w_lower_map": w_l.tolist(), "r_map": (rl / R).tolist(), "psi_map": pl.tolist()})
        print(f"  h/D {r['h_over_D']:.2f}: lower sees {ml:+.3f} v_i0 (lens {2*r['overlap_f']:.3f}), upper sees {mu_:+.3f} v_i0;"
              f" penalty BS {dP:.0f} W vs lens {lens:.0f} W; pack {pack_bs:.0f} vs {r['pack_wh']:.0f} Wh", flush=True)
    out = {"chi_deg": math.degrees(chi), "mu": r0["mu"], "lambda": r0["lam"], "checks": ck, "rows": rows,
           "numerics": {"segments_per_ring": N_SEG, "core_over_R": CORE, "wake_length_over_R": L_WAKE, "ring_spacing_over_R": DS}, "runtime_s": time.time() - t0}
    save_json(os.path.join("explore", "e07_cruise_wake.json"), out)
    plot(out)
    print(f"  wrote results/explore/e07_cruise_wake.json in {out['runtime_s']:.0f} s")


def plot(o):
    rows = o["rows"]; hd = [r["h_over_D"] for r in rows]
    fig = plt.figure(figsize=(12, 3.5))
    ax0 = fig.add_subplot(1, 3, 1)
    ax0.plot(hd, [r["lens_equiv_w_lower_over_vi0"] for r in rows], "o--", color="#2a78d6", label="lens model (entry 06): 2 f")
    ax0.plot(hd, [r["mean_w_lower_over_vi0"] for r in rows], "o-", color="#0b0b0b", label="vortex wake: upper → lower")
    ax0.plot(hd, [r["mean_w_upper_over_vi0"] for r in rows], "s-", color="#c0392b", label="vortex wake: lower → upper")
    ax0.axhline(0, color="#999", lw=.8); ax0.set_xlabel("h / D"); ax0.set_ylabel("mean extra inflow / v_i0"); ax0.legend(fontsize=7); ax0.grid(alpha=.3)
    ax1 = fig.add_subplot(1, 3, 2)
    ax1.plot(hd, [r["pack_lens_wh"] for r in rows], "o--", color="#2a78d6", label="lens model (entry 06)")
    ax1.plot(hd, [r["pack_bs_wh"] for r in rows], "o-", color="#0b0b0b", label="prescribed vortex wake")
    ax1.set_xlabel("h / D"); ax1.set_ylabel("pack energy [Wh]"); ax1.legend(fontsize=7); ax1.grid(alpha=.3)
    ax2 = fig.add_subplot(1, 3, 3, projection="polar")
    r = next(q for q in rows if q["h_over_D"] == 0.2)
    nr = 10; npsi = len(r["psi_map"]) // nr
    Z = np.array(r["w_lower_map"]).reshape(nr, npsi); Rr = np.array(r["r_map"]).reshape(nr, npsi); Pp = np.array(r["psi_map"]).reshape(nr, npsi)
    m = ax2.pcolormesh(np.c_[Pp, Pp[:, :1] + 2 * math.pi], np.c_[Rr, Rr[:, :1]], np.c_[Z, Z[:, :1]], shading="gouraud", cmap="RdBu_r",
                       vmin=-np.abs(Z).max(), vmax=np.abs(Z).max())
    ax2.set_title("upper wake on the lower disk, h/D 0.2\n(w / v_i0; ψ = 0 aft)", fontsize=8); ax2.set_yticklabels([]); fig.colorbar(m, ax=ax2, fraction=0.046)
    fig.suptitle(f"Exploration 07: cruise wake interference, prescribed skewed vortex wake (χ = {o['chi_deg']:.1f}°) vs entry 06's lens model", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "e07_cruise_wake.png"), dpi=140); plt.close(fig)


if __name__ == "__main__":
    run()

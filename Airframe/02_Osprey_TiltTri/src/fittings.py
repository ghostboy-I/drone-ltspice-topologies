"""Hand sizing of the two fittings the fuselage shell FEM showed were missing: the wing carry-through and the boom socket.

    python3 src/fittings.py        -> results/fittings.json (read by fuselage_shell.py, which then checks the design)

Why. With the fairing floating (user, 2026-11-19), the keel-only shell model failed in two places only: where the boom
load was smeared over the last 3 cm of the keel, and where the wing was modelled as a clamp along the whole crown arc of
the two wing frames. Neither is a design. This file makes both into parts, sizes them by hand at ULTIMATE load (x 1.5,
the same free-body loads fuselage_shell.free_body() applies), and the shell model then re-runs with them in place.

1. Wing carry-through: four bolted lugs.
   The wing spar box runs unbroken over the fuselage (tiltframe.py). The fuselage hangs from it at the front and rear
   spar stations x_f, x_r, which are already frame stations, through two lugs per frame at y = +-Y_LUG on the crown.
   * Lug loads: four pins carry the fuselage resultant (F, M). Four points with 3 force components each is 12 unknowns
     for 6 equations, so the split needs a stiffness assumption. Equal pin stiffness gives the least-norm solution
         f = A^T (A A^T)^-1 [F; M],   A = [I ...; [r_i x] ...]
     (the "bolt-group" method). The shell model computes the real split from its own stiffness: check H1.
   * Bolt: double shear, n = 2 planes:  d >= sqrt( 4 P FF / (2 pi F_su) ),  FF = 1.15 fitting factor (FAR 23.625).
   * Lug: 7075-T6, edge distance e = 1.5 d, width w = 3 d; the tang thickness is the largest of
         net tension  t = P FF / ((w - d) F_tu)
         shear-out    t = P FF / (2 (e - d/2) F_su)
         bearing      t = P FF / (d F_bru)
   * Heavy frame: each wing frame is a closed ring (the fuselage section's perimeter) loaded in its own plane by the
     two lug reactions at the crown and by the keel at the two web feet. A closed ring is 3x statically indeterminate.
     Cut it at the crown; with redundants X = (H, V, M0) on the cut face the bending moment at arc position s is
         M(s) = M_open(s) + M0 + (y0 - y) V - (z0 - z) H
     and the cut must close (unit-load method, bending flexibility only, EI constant):
         int M dM/dX_i ds = 0,  i = 1..3   ->  a 3x3 linear system.
     Self-test: a circular ring under two opposite loads P must give M = P R / pi at the loads (Roark table 9.2 case 1).
     The frame is a flat strip of quasi-isotropic carbon (thickness t, depth d inward), as in fuselage_shell.py, so its
     edge strain is  eps = 6 M / (E t d^2) + N / (E t d).  Depth is capped at 50 mm by the payload clearance at the
     sides (fuselage width 0.56 = 0.45 m plates + 2 x 55 mm); t is the smallest that clears eps_allow with MS >= 0.10.
2. Boom socket: two bulkheads and two collars.
   The boom (D from the selected design) continues forward inside the tail cone to the frame at x = -0.671 m and is
   held at that frame and the one at -0.967 m (both aft of the payload, so they can be full sandwich bulkheads with a
   hole for the boom). Aluminium collars are bonded to the boom and bolted to the bulkheads. The aft collar is a slip
   fit (radial loads only); the forward one also takes the axial force and the torsion. That makes the socket
   statically determinate. With the boom rigid between the collars and the boom loads (F, M) known at the root point:
         radial:  F_aft + F_fwd = F_perp,   (r_aft - r_fwd) x F_aft = M_perp(about the forward collar)
   so the couple is ~ M / s with s = 0.296 m between the collars. The collar bond (shear over pi D w_c) and the
   collar-to-bulkhead bolts are checked by hand. The bulkhead itself is checked in the shell model.
   Mould line: the tail cone ends at a 0.196 x 0.124 m section, smaller than the boom. The floating fairing's aft
   closure has to open around the boom (geometry change, reported).
"""
import json, math, os, sys
import numpy as np
from tiltcfg import ROOT, RESULTS
import tiltframe as tf
import materials as mat
import fuselage_shell as fs
from geometry import fuselage_station

FF = 1.15                     # fitting factor, FAR 23.625 (on ultimate)
Y_LUG = 0.20                  # m, ASSUMED lug spanwise position: over the payload (r 0.225) and inside the crown
AL = dict(F_tu=572e6, F_su=331e6, F_bru_over_Ftu=1.30, rho=2810.0)   # 7075-T6 (MMPDS typical F_tu, F_su = 0.58 F_tu;
                                                                     # bearing at e/d 1.5 taken as 1.3 F_tu: ASSUMED)
BOLT = dict(F_su=0.6 * 1040e6, rho=7850.0)   # ISO 898-1 class 10.9 alloy steel bolt: F_tu 1040 MPa, F_su ~ 0.6 F_tu
D_STD = [0.006, 0.008, 0.010, 0.012]   # m; 6 mm minimum for primary-structure bolts (ASSUMED practice rule:
                                        # handling, wear and fatigue, not static strength, set the floor)
FRAME_D_MAX = 0.050           # m, payload clearance at the sides
X_SOCKET = (-0.671, -0.967)   # m, forward and aft collar stations (existing frame stations)
COLLAR = dict(w=0.040, t=0.004, adhesive_tau=10e6, n_bolts=8)   # ASSUMED collar width and wall, adhesive lap shear
                                                                 # design value (toughened epoxy, 10 MPa), flange bolts


def least_norm(P, F, M, r0=np.zeros(3)):
    return fs.patch_forces(np.asarray(P, float), np.asarray(F, float), np.asarray(M, float), r0)


def ring_moments(Y, Z, loads, flex=None):
    """Closed ring through the points (Y, Z) (in order, not repeated), in-plane point loads [(index, fy, fz)],
    self-equilibrated. Returns M and N at every point (cut at index 0, bending flexibility only). flex: 1/EI relative to
    the frame at each point (default 1 everywhere; ~0 where the frame is part of something much stiffer)."""
    n = len(Y)
    seg = np.hypot(np.roll(Y, -1) - Y, np.roll(Z, -1) - Z)
    ds = 0.5 * (seg + np.roll(seg, 1)) * (1.0 if flex is None else flex)
    Mo = np.zeros(n); Fy = np.zeros(n); Fz = np.zeros(n)
    acc = []
    for k in range(n):                                   # loads applied at points 0..k act on the part [0, k]
        acc += [(Y[i], Z[i], fy, fz) for i, fy, fz in loads if i == k]
        Mo[k] = sum((yj - Y[k]) * fz - (zj - Z[k]) * fy for yj, zj, fy, fz in acc)
        Fy[k] = sum(a[2] for a in acc); Fz[k] = sum(a[3] for a in acc)
    m = np.vstack([-(Z[0] - Z), (Y[0] - Y), np.ones(n)])  # dM/dH, dM/dV, dM/dM0
    K = (m * ds) @ m.T; rhs = -(m * ds) @ Mo
    H, V, M0 = np.linalg.solve(K, rhs)
    M = Mo + M0 + (Y[0] - Y) * V - (Z[0] - Z) * H
    ty, tz = np.roll(Y, -1) - np.roll(Y, 1), np.roll(Z, -1) - np.roll(Z, 1)
    tn = np.hypot(ty, tz); ty, tz = ty / tn, tz / tn
    N = -((Fy + H) * ty + (Fz + V) * tz)                  # force on the part [0, k] from the rest, along the tangent
    return M, N


def self_test():
    th = np.linspace(0, 2 * np.pi, 720, endpoint=False) + np.pi / 2
    R, P = 0.3, 1000.0
    Y, Z = R * np.cos(th), R * np.sin(th)
    M, _ = ring_moments(Y, Z, [(0, 0.0, -P), (360, 0.0, P)])   # pull the crown up... top load down, bottom up
    return {"ring_M_at_load_Nm": float(abs(M[0])), "roark_PR_over_pi": P * R / math.pi,
            "ring_M_at_90deg_Nm": float(abs(M[180])), "roark_PR_(1/2-1/pi)": P * R * (0.5 - 1 / math.pi)}


def main():
    ctx = tf.context()
    d = tf.merge(tf.DEFAULT, json.load(open(os.path.join(ROOT, "designs", "selected.json"))))
    r, fb = fs.free_body(ctx, d)
    sz = ctx["sz"]; fu = sz["fuselage"]; w = sz["wing"]; p = ctx["p"]; pm = ctx["pm"]
    z_top = -(w["c"] * w["tc"] / 2); z_boom = z_top - 0.10
    nfr, nt = p["fuselage"]["nose_frac"], p["fuselage"]["tail_frac"]
    me_st = fs.stations(ctx, d, fu, r["x_payload"])[1]
    x_f, x_r = me_st["x_f"], me_st["x_r"]
    qi = mat.strain_allowable(pm); E_qi, eps_allow = qi["Ex_qi"], qi["eps_allow"]
    st = self_test()
    out = {"self_test": st, "assumptions": dict(FF=FF, Y_LUG=Y_LUG, AL=AL, BOLT=BOLT, FRAME_D_MAX=FRAME_D_MAX, X_SOCKET=X_SOCKET, COLLAR=COLLAR),
           "x_f": x_f, "x_r": x_r, "z_boom": z_boom, "E_frame": E_qi, "eps_allow": eps_allow, "cases": {}}

    # ---------------- wing lugs
    rings = {}
    for tag, xk in (("front", x_f), ("rear", x_r)):
        x, P, g = fs.ring((fu["x_nose"] - xk) / fu["L"], fu, z_top, nfr, nt, d["keel"])
        top = np.where(P[:, 1] > g["zc"])[0]
        iL = top[np.argmin(abs(P[top, 0] - Y_LUG))]; iR = top[np.argmin(abs(P[top, 0] + Y_LUG))]
        rings[tag] = dict(x=x, P=P, g=g, lug=(iL, iR), web=(0, 2 * fs.NB))
    lug_pts = [(rings[t]["x"], *rings[t]["P"][i]) for t in ("front", "rear") for i in rings[t]["lug"]]
    out["lug_points"] = [list(map(float, q)) for q in lug_pts]
    worst_lug = 0.0
    frame_M = {"front": 0.0, "rear": 0.0}; frame_case = {}
    for name, cs in fb.items():
        F = sum(ld["L"][:3] for ld in cs["loads"]); M = sum(ld["L"][3:] + np.cross(ld["x"], ld["L"][:3]) for ld in cs["loads"])
        R = least_norm(lug_pts, -F, -M)                    # reactions on the fuselage at the four lugs
        c = {"F_fuselage_N": F.round(1).tolist(), "M_fuselage_Nm": M.round(1).tolist(), "lug_reactions_N": R.round(1).tolist(),
             "lug_max_N": float(np.linalg.norm(R, axis=1).max())}
        worst_lug = max(worst_lug, c["lug_max_N"])
        # each wing frame in its own plane: lug reactions (y, z) at the crown, keel at the web feet balancing them
        for k, tag in enumerate(("front", "rear")):
            rg = rings[tag]; P = rg["P"]
            Rl = R[2 * k:2 * k + 2]
            Fy, Fz = Rl[:, 1].sum(), Rl[:, 2].sum()
            Mx = sum(P[i, 0] * f[2] - P[i, 1] * f[1] for i, f in zip(rg["lug"], Rl))
            (yL, zL), (yR, zR) = P[rg["web"][0]], P[rg["web"][1]]
            fy = -Fy / 2                                     # lateral load shared by the two web feet
            # vertical at the feet: fzL + fzR = -Fz ;  yL fzL + yR fzR - (zL + zR) fy = -Mx
            A = np.array([[1, 1], [yL, yR]]); b = np.array([-Fz, -Mx + (zL + zR) * fy])
            fzL, fzR = np.linalg.solve(A, b)
            loads = [(rg["lug"][0], Rl[0, 1], Rl[0, 2]), (rg["lug"][1], Rl[1, 1], Rl[1, 2]),
                     (rg["web"][0], fy, fzL), (rg["web"][1], fy, fzR)]
            # cut at the crown centre: reorder the ring so index 0 is the topmost point
            i0 = int(np.argmax(P[:, 1] - 1e-6 * abs(P[:, 0])))
            Y, Z = np.roll(P[:, 0], -i0), np.roll(P[:, 1], -i0)
            loads = [((i - i0) % len(P), a, b_) for i, a, b_ in loads]
            M0_, N0_ = ring_moments(Y, Z, loads)
            # variant: the frame's lower arc between the keel web feet IS the keel box's bottom (shared with the flange,
            # 0.29 m wide sandwich, and the webs): treat it as rigid (flex 1e-3) and see how much of the hand-FE gap that is
            gk = rg["g"]; low = (Z < (gk["zc"] - gk["hh"]) + gk["dk"]) & (abs(Y) <= gk["wk"] + 1e-6)
            fl = np.where(low, 1e-3, 1.0)
            Mk_, _ = ring_moments(Y, Z, loads, fl)
            iLk, iRk = ((rg["lug"][0] - i0) % len(P), (rg["lug"][1] - i0) % len(P)); sk = np.sign(Y[iLk])
            mHk, _ = ring_moments(Y, Z, [(iLk, sk, 0.0), (iRk, -sk, 0.0)], fl)
            segk = np.hypot(np.roll(Y, -1) - Y, np.roll(Z, -1) - Z); dsk = 0.5 * (segk + np.roll(segk, 1)) * fl
            Hk = -float((Mk_ * mHk * dsk).sum() / (mHk * mHk * dsk).sum())
            Mk = np.where(low, 0.0, Mk_ + Hk * mHk)          # moment in the frame strip itself (the keel takes the rest)
            # arch thrust: both lugs bolt into the same (spanwise rigid) spar, so their y spacing cannot change. One more
            # redundant: a self-equilibrated pair H (outward at both lugs). Unit-load method:
            #   delta = int M0 mH ds / EI,  delta_H = int mH^2 ds / EI,  H = -delta / delta_H,  M = M0 + H mH
            iL_, iR_ = ((rg["lug"][0] - i0) % len(P), (rg["lug"][1] - i0) % len(P))
            sgnL = np.sign(Y[iL_])
            mH, nH = ring_moments(Y, Z, [(iL_, sgnL, 0.0), (iR_, -sgnL, 0.0)])
            seg = np.hypot(np.roll(Y, -1) - Y, np.roll(Z, -1) - Z); ds_ = 0.5 * (seg + np.roll(seg, 1))
            H = -float((M0_ * mH * ds_).sum() / (mH * mH * ds_).sum())
            Mr, Nr = M0_ + H * mH, N0_ + H * nH
            R[2 * k, 1] += H * np.sign(P[rg["lug"][0], 0]); R[2 * k + 1, 1] += H * np.sign(P[rg["lug"][1], 0])
            kmax = int(np.argmax(abs(Mr)))
            c[f"frame_{tag}"] = {"web_feet_N": [[fy, fzL], [fy, fzR]], "M_max_Nm": float(abs(Mr[kmax])), "arch_thrust_N": H,
                                 "keel_stiffened": {"M_max_Nm": float(abs(Mk).max()), "arch_thrust_N": Hk,
                                                    "at_yz": [float(Y[np.argmax(abs(Mk))]), float(Z[np.argmax(abs(Mk))])]},
                                 "M_max_no_thrust_Nm": float(abs(M0_).max()),
                                 "at_yz": [float(Y[kmax]), float(Z[kmax])], "N_at_Mmax_N": float(Nr[kmax]),
                                 "N_max_N": float(abs(Nr).max())}
            if abs(Mr[kmax]) > frame_M[tag]:
                frame_M[tag] = float(abs(Mr[kmax])); frame_case[tag] = (name, float(Nr[kmax]))
            rg.setdefault("M_by_case", {})[name] = Mr.tolist()
        c["lug_reactions_N"] = R.round(1).tolist(); c["lug_max_N"] = float(np.linalg.norm(R, axis=1).max())
        worst_lug = max(worst_lug, c["lug_max_N"])
        out["cases"][name] = c

    # bolt and lug: the equal-stiffness split is the first estimate; once the shell model has run with the lugs, its own
    # stiffness split governs if larger (check H1)
    shell = os.path.join(RESULTS, "fuselage_shell_model.json")
    fe_lug = 0.0
    if os.path.exists(shell):
        hh_ = jl = json.load(open(shell)).get("hand_H", {})
        fe_lug = max((v["lug_max_fe_N"] for v in hh_.values()), default=0.0)
    out["lug_fe_max_N"] = fe_lug
    P_ = max(worst_lug, fe_lug) * FF
    d_b = next(dd for dd in D_STD if 2 * math.pi * dd ** 2 / 4 * BOLT["F_su"] >= P_)
    e_, w_ = 1.5 * d_b, 3.0 * d_b
    t_net = P_ / ((w_ - d_b) * AL["F_tu"]); t_so = P_ / (2 * (e_ - d_b / 2) * AL["F_su"]); t_br = P_ / (d_b * AL["F_bru_over_Ftu"] * AL["F_tu"])
    t_lug = max(t_net, t_so, t_br, 0.003)
    t_lug = math.ceil(t_lug * 1e3) * 1e-3
    out["lug_design_source"] = "FE" if fe_lug > worst_lug else "hand"
    lug_vol = 2.5 * w_ * (e_ + 2 * d_b) * t_lug + 0.06 * 0.04 * 0.004   # tang (x2.5 for the clevis root) + base plate (ASSUMED)
    out["lug"] = {"P_ult_max_N": max(worst_lug, fe_lug), "P_hand_N": worst_lug, "P_design_N": P_, "bolt_d_m": d_b, "bolt_MS": 2 * math.pi * d_b ** 2 / 4 * BOLT["F_su"] / P_ - 1,
                  "e_m": e_, "w_m": w_, "t_required_m": {"net_tension": t_net, "shear_out": t_so, "bearing": t_br}, "t_m": t_lug,
                  "MS": {"net_tension": t_lug / t_net - 1, "shear_out": t_lug / t_so - 1, "bearing": t_lug / t_br - 1},
                  "mass_each_kg": lug_vol * AL["rho"] + math.pi * d_b ** 2 / 4 * 0.05 * BOLT["rho"]}

    # heavy frame section: depth FRAME_D_MAX, thinnest t (0.5 mm steps) with hand MS >= 0.10 in both frames
    sec = {}
    for tag in ("front", "rear"):
        Mx_, Nx_ = frame_M[tag], frame_case[tag][1]
        dd = FRAME_D_MAX
        for t_ in np.arange(0.004, 0.030, 0.0005):
            eps = 6 * Mx_ / (E_qi * t_ * dd ** 2) + abs(Nx_) / (E_qi * t_ * dd)
            if eps_allow / eps - 1 >= 0.10: break
        perim = float(np.sum(np.hypot(*np.diff(np.vstack([rings[tag]["P"], rings[tag]["P"][:1]]), axis=0).T)))
        sec[tag] = {"t_m": float(round(t_, 4)), "d_m": dd, "M_design_Nm": Mx_, "N_with_M_N": Nx_, "case": frame_case[tag][0],
                    "eps_hand": float(eps), "MS_hand": float(eps_allow / eps - 1), "perimeter_m": perim,
                    "mass_kg": perim * t_ * dd * pm["materials"]["ud"]["rho"], "lug_idx": [int(i) for i in rings[tag]["lug"]]}
    out["wing_frames"] = sec

    # ---------------- boom socket
    rb = np.array([fu["x_tail"] + 0.05, 0, z_boom])
    xs_f, xs_a = X_SOCKET; s = xs_f - xs_a
    pf, pa = np.array([xs_f, 0, z_boom]), np.array([xs_a, 0, z_boom])
    boom_D = d["boom"]["D"]
    socket = {}
    worst_col = 0.0
    for name, cs in fb.items():
        F = np.zeros(3); Mb = np.zeros(3)
        for ld in cs["loads"]:
            if ld["group"] in ("keel", "payload_link", "bat_link") or ld["group"].startswith("gear"): continue
            F += ld["L"][:3]; Mb += ld["L"][3:] + np.cross(ld["x"] - rb, ld["L"][:3])
        Fa, Ff, Tf = fs.socket_split(F, Mb, rb, xs_f, xs_a, z_boom)
        socket[name] = {"F_boom_N": F.round(1).tolist(), "M_boom_root_Nm": Mb.round(1).tolist(),
                        "F_aft_collar_N": Fa.round(1).tolist(), "F_fwd_collar_N": Ff.round(1).tolist(), "T_fwd_collar_Nm": float(Tf)}
        worst_col = max(worst_col, np.linalg.norm(Fa), np.linalg.norm(Ff))
    tau_bond = worst_col * FF / (math.pi * boom_D * COLLAR["w"])
    T_max = max(abs(v["T_fwd_collar_Nm"]) for v in socket.values())
    tau_bond_T = T_max * FF / (math.pi * boom_D * COLLAR["w"] * boom_D / 2)
    bolt_flange = next(dd for dd in [0.005] + D_STD if math.pi * dd ** 2 / 4 * BOLT["F_su"] * COLLAR["n_bolts"] / 2 >= worst_col * FF)
    m_collar = math.pi * (boom_D + COLLAR["t"]) * COLLAR["w"] * COLLAR["t"] * AL["rho"] + math.pi * (boom_D + 0.05) * 0.02 * 0.003 * AL["rho"]
    bsec = tf.tube(pm, boom_D, d["boom"]["n_w45"], d["boom"]["n_ud"])
    out["socket"] = {"x_fwd": xs_f, "x_aft": xs_a, "spacing_m": s, "boom_D_m": boom_D, "cases": socket, "collar_max_N": worst_col,
                     "bond_tau_Pa": tau_bond + tau_bond_T, "bond_MS": COLLAR["adhesive_tau"] / (tau_bond + tau_bond_T) - 1,
                     "flange_bolt_d_m": bolt_flange, "collar_mass_each_kg": m_collar,
                     "boom_extension_m": float(rb[0] - xs_f) * -1, "boom_extension_kg": float((rb[0] - xs_f) * -1 * bsec.mass_per_m),
                     "tail_end_section_m": [2 * fuselage_station(1.0, fu, z_top, nfr, nt)[1], 2 * fuselage_station(1.0, fu, z_top, nfr, nt)[2]]}
    ws = []
    for xk in X_SOCKET:
        x, hw, hh, zc = fuselage_station((fu["x_nose"] - xk) / fu["L"], fu, z_top, nfr, nt)
        ws.append({"x": xk, "top_gap_m": (zc + hh) - (z_boom + boom_D / 2), "half_width": hw, "half_height": hh, "zc": zc})
    out["socket"]["stations"] = ws
    with open(os.path.join(RESULTS, "fittings.json"), "w") as f: json.dump(out, f, indent=1)
    print(json.dumps({k: out[k] for k in ("self_test", "lug", "wing_frames")}, indent=1))
    print(json.dumps({k: v for k, v in out["socket"].items() if k != "cases"}, indent=1))
    for n_, c in socket.items(): print(n_, c)
    for n_, c in out["cases"].items(): print(n_, "lug max", round(c["lug_max_N"]), "frame M", round(c["frame_front"]["M_max_Nm"]), round(c["frame_rear"]["M_max_Nm"]))


if __name__ == "__main__":
    main()

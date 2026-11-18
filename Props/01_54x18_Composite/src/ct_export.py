"""Copy the Caradonna-Tung CFD results of one or more meshes into the shared, top-level CFD_Results/ folder:
CFD_Results/01_54x18_Composite/caradonna_tung_<mesh>/ gets a README with the key numbers and hand checks, the summary JSON,
the plots, the torque split and a force history CSV. No solver time or processor folders (those stay under cfd.run_root).
Usage: python3 src/ct_export.py coarse coarse_le"""
import csv, json, math, os, shutil, sys
from common import ROOT, RESULTS

REPO = os.path.dirname(os.path.dirname(ROOT))                 # Props/01_54x18_Composite -> repository root
OUT = os.path.join(REPO, "CFD_Results", os.path.basename(ROOT))
DESC = {"coarse": "baseline mesh: 3.1 mm blade cells, 1.6 mm on the sharp edges only (the leading edge stayed at 3.1 mm)",
        "coarse_le": "leading-edge mesh: coarse + a level-9 tube (0.78 mm cells) along each leading edge, to recover the leading-edge suction"}
NOTES = {"coarse": ["Torque was still rising at 600 iterations (CQ drift +0.73 %/100 it), so 83 N m is a lower bound for this mesh.",
                    "Diagnosis: the leading-edge cells (3.1 mm) were as big as the nose radius (3.0 mm), so the suction"
                    " peak that pulls the blade forward was under-resolved and showed up as extra pressure torque."],
         "coarse_le": ["Refining only the leading edge cut torque by 7.4 N m (83.2 -> 75.8, -9 %) with thrust unchanged (+0.7 %), and"
                       " the figure of merit rose from 0.318 to 0.353. The whole change is pressure torque (66.8 -> 58.4 N m);"
                       " friction torque rose slightly (16.4 -> 17.4 N m).",
                       "It is not the whole gap: the torque-split script estimates another ~11 N m of pressure torque would go if the"
                       " sections carried the leading-edge suction of an attached NACA 0012 at their CFD normal force"
                       " (that would give ~65 N m, near the 60-65 N m expected). The next step is a finer leading edge or finer blade"
                       " surface overall (the medium mesh), not more iterations: this run is converged (CQ drift -0.13 %/100 it).",
                       "Open question: the section suction peaks below read lower than on coarse (e.g. 0.89 vs 0.98 at r/R 0.8,"
                       " experiment 1.09), even though total pressure torque fell. The Cp sections are averaged in 80 chordwise bins"
                       " (2.4 mm) over a 4.7 mm radial band on both meshes, so the binning alone does not explain it. Check the"
                       " raw face values at the nose before trusting either mesh's peak."]}


def load(name):
    f = os.path.join(RESULTS, name)
    return json.load(open(f)) if os.path.exists(f) else None


def export(mesh):
    d = load(f"ct_cfd_{mesh}.json")
    if d is None: sys.exit(f"results/ct_cfd_{mesh}.json missing: run `python3 src/ct_validation.py post {mesh}` first")
    sp = load(f"ct_torque_split_{mesh}.json")
    dst = os.path.join(OUT, f"caradonna_tung_{mesh}")
    os.makedirs(dst, exist_ok=True)
    for f in (f"ct_cfd_{mesh}.json", f"ct_cp_{mesh}.png", f"ct_convergence_{mesh}.png", f"ct_torque_split_{mesh}.json",
              f"ct_guard_{mesh}.json", f"ct_case_{mesh}.json"):
        if os.path.exists(os.path.join(RESULTS, f)): shutil.copy(os.path.join(RESULTS, f), dst)
    h = d["history"]
    with open(os.path.join(dst, "force_history.csv"), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["iteration", "CT", "CQ"])
        for row in zip(h["iteration"], h["ct"], h["cq"]): w.writerow([int(row[0]), f"{row[1]:.6e}", f"{row[2]:.6e}"])
    # hand checks: the pressure + viscous split must add back to the solver's torque, FoM = CT^1.5 / (sqrt(2) CQ)
    q_visc = d["Q"] * d["viscous_torque_fraction"]; q_pres = d["Q"] - q_visc
    fom_hand = d["ct"] ** 1.5 / math.sqrt(2) / d["cq"]
    c = d["convergence"]; m = d["mesh_info"]
    lines = [f"# Caradonna-Tung hover rotor, `{mesh}` mesh", "",
             f"Validation case for the 54x18 prop CFD method: 2 blades, NACA 0012, R = 1.143 m, c = 0.1905 m, 8 deg collective,"
             f" tip Mach 0.439 (OpenFOAM 13, {d['solver']}, MRF, k-omega SST, {d['n_proc']} cores, {c['iterations']} iterations).",
             f"{DESC.get(mesh, mesh)[0].upper() + DESC.get(mesh, mesh)[1:]}. {m['cells']:,.0f} cells, layer coverage {m.get('layer_coverage_pct', float('nan')):.0f} %,"
             f" mean y+ {d['yplus'].get('average', float('nan')):.0f}.", "",
             "| Quantity | CFD | Reference | Difference |", "|---|---|---|---|",
             f"| CT | {d['ct']:.5f} | {d['experimental_ct']['central']:.5f} (experiment, from the report's sectional CL) | {d['ct_vs_exp_central_pct']:+.1f} % |",
             f"| CT | {d['ct']:.5f} | {d['ct_bemt']:.5f} (BEMT hand calc) | {d['ct_cfd_vs_bemt_pct']:+.1f} % |",
             f"| Thrust T | {d['T']:.1f} N | | |",
             f"| Torque Q | {d['Q']:.1f} N m | | |",
             f"| CQ | {d['cq']:.6f} | | |",
             f"| Figure of merit | {d['fom']:.3f} | {fom_hand:.3f} (CT^1.5 / (sqrt 2 CQ), by hand) | |", "",
             f"Torque split: pressure {q_pres:.1f} N m + viscous {q_visc:.1f} N m ({100 * d['viscous_torque_fraction']:.0f} %) = {d['Q']:.1f} N m."]
    if sp: lines.append(f"Check: the pvpython pressure-only surface integral (`ct_torque_split_{mesh}.json`) gives {-sp['Mz_total']:.1f} N m"
                        f" against {q_pres:.1f} N m from the solver ({100 * (-sp['Mz_total'] / q_pres - 1):+.1f} %).")
    lines += ["", f"Convergence over the last {c['window']} of {c['iterations']} iterations: CT drift {c['ct_drift_pct_per100']:+.2f} %/100 it,"
              f" CQ drift {c['cq_drift_pct_per100']:+.2f} %/100 it (converged means below 0.5): "
              + ("**torque converged**." if c["torque_converged"] else "**torque not converged**."), "",
              "| r/R | CN CFD | CL report | Difference | Suction peak CFD | Suction peak experiment |", "|---|---|---|---|---|---|"]
    for s in d["stations"]:
        lines.append(f"| {s['x']} | {s['cn_cfd']:.3f} | {s['cl_report']:.3f} | {s['cn_cfd_vs_report_pct']:+.1f} % | {s['suction_peak_cfd']:.2f} | {s['suction_peak_exp']:.2f} |")
    if mesh in NOTES: lines += ["", "## Takeaways", ""] + [f"- {n}" for n in NOTES[mesh]]
    lines += ["", f"![pressure coefficient](ct_cp_{mesh}.png)", "", f"![convergence](ct_convergence_{mesh}.png)", "",
              "Files: `ct_cfd_*.json` (full summary), `force_history.csv` (CT, CQ every 10 iterations), `ct_torque_split_*.json` (radial"
              " bands), `ct_case_*.json` (mesh recipe), `ct_guard_*.json` (runaway-guard limits). Regenerate with"
              f" `python3 src/ct_validation.py post {mesh}` then `python3 src/ct_export.py {mesh}` in `Props/01_54x18_Composite/`."]
    open(os.path.join(dst, "README.md"), "w").write("\n".join(lines) + "\n")
    print("wrote", os.path.relpath(dst, REPO))
    return mesh, d, q_pres, q_visc


def index(rows):
    lines = ["# 54x18 composite prop: CFD results", "",
             "Caradonna-Tung validation of the CFD method before it is used on the 54x18 blade. Each folder has its own README.", "",
             "| Case | Mesh | CT | CT vs experiment | Torque | Pressure / viscous torque | FoM | Torque converged |", "|---|---|---|---|---|---|---|---|"]
    for mesh, d, qp, qv in rows:
        lines.append(f"| [caradonna_tung_{mesh}](caradonna_tung_{mesh}/) | {DESC.get(mesh, mesh).split(':')[0]} | {d['ct']:.5f} |"
                     f" {d['ct_vs_exp_central_pct']:+.1f} % | {d['Q']:.1f} N m | {qp:.1f} / {qv:.1f} N m | {d['fom']:.3f} |"
                     f" {'yes' if d['convergence']['torque_converged'] else 'no'} |")
    open(os.path.join(OUT, "README.md"), "w").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    meshes = sys.argv[1:] or ["coarse", "coarse_le"]
    rows = [export(m) for m in meshes]
    have = [m for m in DESC if os.path.exists(os.path.join(RESULTS, f"ct_cfd_{m}.json"))]   # index lists every exported case
    index([r for r in rows] + [export(m) for m in have if m not in meshes])

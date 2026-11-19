"""The instant check and the design sweep.

    python3 src/screen.py check designs/selected.json     PASS/FAIL + margins for one design (~1 s)
    python3 src/screen.py sweep 1500                     random sweep + 4 refinement rounds, lightest PASS wins

Objective: airframe mass (the user's priority: weight first). A design is admissible only if it PASSES every check
in tiltframe.verdict. The sweep runs at nice 19 on 2 workers (the machine is shared with long CFD runs).
"""
import json, math, os, sys, time
import numpy as np
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor
from tiltcfg import ROOT, RESULTS
import tiltframe as tf

# (group, key, lo, hi, integer)
SPACE = [("wing", "n_w45", 1, 3, True), ("wing", "n_ud_root", 2, 16, True), ("wing", "n_ud_tip", 0, 6, True), ("wing", "core_mm", 0, 12, False),
         ("pod", "n_w45", 1, 5, True), ("pod", "n_ud", 0, 10, True),
         ("keel", "depth", 0.10, 0.26, False), ("keel", "width", 0.20, 0.42, False), ("keel", "n_w45", 1, 3, True), ("keel", "n_ud", 0, 8, True), ("keel", "core_mm", 0, 12, False),
         ("boom", "D", 0.08, 0.22, False), ("boom", "n_w45", 1, 4, True), ("boom", "n_ud", 0, 12, True),
         ("gear", "D", 0.03, 0.10, False), ("gear", "n_w45", 1, 3, True), ("gear", "n_ud", 2, 14, True), ("gear", "absorber_mm", 40, 140, False),
         ("gear", "clearance", 0.10, 0.25, False), ("gear", "main_track", 0.70, 1.30, False)]

_CTX = None


def _init():
    global _CTX
    os.nice(19)
    _CTX = tf.context()


def to_design(x):
    d = {}
    for (g, k, lo, hi, isint), v in zip(SPACE, x):
        v = min(max(v, lo), hi)
        d.setdefault(g, {})[k] = int(round(v)) if isint else float(v)
    if d["wing"]["n_ud_tip"] > d["wing"]["n_ud_root"]: d["wing"]["n_ud_tip"] = d["wing"]["n_ud_root"]
    return d


def evaluate(x):
    d = to_design(x)
    try:
        r = tf.run(_CTX, d)
    except Exception as e:  # noqa: BLE001  (an unbuildable design is just a failed design)
        return {"x": list(x), "ok": False, "mass": 1e9, "err": str(e)}
    nbad = len(r["reasons"])
    worst = min(min(w["strain"], w["buckling"]) for w in r["worst"].values())
    return {"x": list(map(float, x)), "ok": r["verdict"] == "PASS", "mass": r["mass_airframe_kg"], "n_fail": nbad,
            "worst_ms": worst, "reasons": r["reasons"][:6]}


def penalised(e):
    return e["mass"] if e["ok"] else e["mass"] + 100 + 5 * e.get("n_fail", 50)


def from_design(d):
    return np.array([float(d[g][k]) for g, k, *_ in SPACE])


def sweep(n, rounds=4, workers=2, seed=1, start=None):
    """Random sweep (start=None) or, with start = a design dict, a local cloud around it; then elite refinement."""
    rng = np.random.default_rng(seed)
    lo = np.array([s[2] for s in SPACE], float); hi = np.array([s[3] for s in SPACE], float)
    if start is None:
        X = lo + rng.random((n, len(SPACE))) * (hi - lo)
    else:
        x0 = from_design(start)
        X = np.clip(x0 + rng.normal(0, 0.08, (n, len(SPACE))) * (hi - lo), lo, hi); X[0] = x0
    t0 = time.time(); allres = []
    ctx = mp.get_context("fork")
    with ProcessPoolExecutor(max_workers=workers, mp_context=ctx, initializer=_init) as ex:
        res = list(ex.map(evaluate, X, chunksize=8)); allres += res
        print(f"random {n}: {sum(r['ok'] for r in res)} pass, best {min(penalised(r) for r in res):.2f} [{time.time()-t0:.0f} s]", flush=True)
        for k in range(rounds):
            elite = sorted(allres, key=penalised)[:10]
            scale = 0.25 * 0.6 ** k
            Y = []
            for e in elite:
                for _ in range(n // (10 * (rounds + 1)) + 4):
                    Y.append(np.array(e["x"]) + rng.normal(0, scale, len(SPACE)) * (hi - lo))
            res = list(ex.map(evaluate, Y, chunksize=4)); allres += res
            b = min(allres, key=penalised)
            print(f"round {k+1}: {len(Y)} evals, {sum(r['ok'] for r in res)} pass, best {penalised(b):.2f} kg ok={b['ok']} [{time.time()-t0:.0f} s]", flush=True)
    best = min(allres, key=penalised)
    with open(os.path.join(RESULTS, "sweep.json"), "w") as f:
        json.dump({"n": len(allres), "best": best, "space": SPACE,
                   "pass_masses": sorted(r["mass"] for r in allres if r["ok"]),
                   "fail_reasons": _count_reasons(allres)}, f, indent=1)
    os.makedirs(os.path.join(ROOT, "designs"), exist_ok=True)
    with open(os.path.join(ROOT, "designs", "selected.json"), "w") as f:
        json.dump(to_design(best["x"]), f, indent=1)
    print("best:", json.dumps(to_design(best["x"])), best["mass"], best["ok"], best.get("reasons"))
    return best


def _count_reasons(allres):
    c = {}
    for r in allres:
        for s in r.get("reasons", []):
            key = s.split(":")[0] if ":" in s else " ".join(s.split()[:1] + ["mode in band" if "band" in s else s.split()[-1]])
            c[key] = c.get(key, 0) + 1
    return dict(sorted(c.items(), key=lambda kv: -kv[1]))


if __name__ == "__main__":
    if sys.argv[1] == "check":
        ctx = tf.context()
        d = json.load(open(sys.argv[2])) if len(sys.argv) > 2 else None
        print(tf.summary(tf.run(ctx, d)))
    elif sys.argv[1] == "sweep":
        sweep(int(sys.argv[2]) if len(sys.argv) > 2 else 1500)
    elif sys.argv[1] == "refine":                   # python3 src/screen.py refine 400 designs/selected.json
        sweep(int(sys.argv[2]), start=json.load(open(sys.argv[3])), seed=2)

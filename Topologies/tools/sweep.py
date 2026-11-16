#!/usr/bin/env python3
"""Parallel LTspice parameter sweep: one LTspice process per case, several cases at once.

Why: a single transient run cannot be split across cores (every time step depends on the previous one), but separate
cases are completely independent. So we copy the schematic once per case, change the .param values in the copy, and
run N copies of LTspice at the same time, each in its own folder.

Command line (run from the Topologies folder):
    python3 tools/sweep.py 02_Three-Phase_ESC_BLDC_6-Step/ThreePhase_ESC_BLDC.asc \\
        --param Fsw=24k,48k,96k --param Sync=0,1 --jobs 6 --name fsw_sync

    --param NAME=v1,v2,...  one swept parameter (repeat it; the cases are every combination of the lists)
    --set NAME=value        change a parameter for every case without sweeping it
    --jobs N                how many LTspice runs at once (default: see default_jobs())
    --name NAME             output folder: <topology>/sweeps/<NAME>/  (default: "sweep")
    --keep-raw              keep each case's .raw file (they are ~0.85 GB each for the ESC, so off by default)
    --dry-run               write the case schematics, print the plan, run nothing

From Python:  from sweep import run_sweep;  rows = run_sweep(asc, {"Fsw": ["24k", "48k"]}, jobs=4)

Output: <topology>/sweeps/<name>/results.csv (one row per case: parameters, every .meas result, run time, status)
and case_NNN/ folders with each case's schematic and .log. A case whose .log already holds results is not run again,
so an interrupted sweep picks up where it stopped (delete the folder to start fresh).

How a parameter is changed in the copy:
  * defined on a `.param` line   -> its value on that line is replaced (NAME=old -> NAME=new)
  * stepped by a `.step` line     -> that .step line is commented out and `.param NAME=value` is added
  * not found anywhere            -> error (catches typos such as fsw vs Fsw: LTspice names are case-insensitive)
"""
import argparse, csv, itertools, json, os, re, shutil, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ltraw import read_meas

LTSPICE = os.path.expanduser("~/.wine/drive_c/Program Files/ADI/LTspice/LTspice.exe")


def default_jobs():
    """One job per 2 cores (each LTspice batch run keeps ~2 cores busy), capped by memory (budget 0.5 GB per run,
    measured ~0.17 GB for the ESC, keep 2 GB spare) and at 10."""
    cores = os.cpu_count() or 2
    try:
        avail_gb = int(open("/proc/meminfo").read().split("MemAvailable:")[1].split()[0]) / 1e6
    except Exception:
        avail_gb = 4
    return max(1, min(cores // 2, int((avail_gb - 2) / 0.5), 10))


# ---------------------------------------------------------------- schematic editing
def _text_lines(asc):
    """Indices of schematic TEXT lines that are SPICE directives (start with '!')."""
    return [i for i, l in enumerate(asc) if l.startswith("TEXT ") and re.search(r" !\.", l)]


def apply_params(asc_text, params):
    """Return a copy of the .asc text with each {name: value} applied (see module docstring)."""
    nl = "\r\n" if "\r\n" in asc_text else "\n"
    lines = asc_text.split(nl)
    added = []
    for name, value in params.items():
        pat = re.compile(r"(?<![\w.])(%s)\s*=\s*(\{[^}]*\}|[^\s;]+)" % re.escape(name), re.I)
        done = False
        for i in _text_lines(lines):
            body = lines[i].split("!", 1)[1]
            code, _, comment = body.partition(";")
            if re.match(r"\.param\b", code, re.I) and pat.search(code):
                code = pat.sub(lambda m: "%s=%s" % (m.group(1), value), code, count=1)
                lines[i] = lines[i].split("!", 1)[0] + "!" + code + (";" + comment if comment else "")
                done = True
            elif re.match(r"\.step\s+(param\s+)?%s\b" % re.escape(name), code, re.I):
                lines[i] = lines[i].replace(" !.", " ;.", 1)          # '!' directive -> ';' comment
                added.append(".param %s=%s" % (name, value))
                done = True
        if not done:
            raise ValueError("parameter %r is not on any .param or .step line of the schematic" % name)
    if added:   # place the new directives above the top-most text on the sheet so they overlap nothing
        x = int(lines[_text_lines(lines)[0]].split()[1])
        y = min(int(l.split()[2]) for l in lines if l.startswith("TEXT "))
        tail = []
        while lines and lines[-1] == "":
            tail.append(lines.pop())
        for k, d in enumerate(added):
            lines.append("TEXT %d %d Left 2 !%s" % (x, y - 32 * (k + 1), d))
        lines += tail
    return nl.join(lines)


# ---------------------------------------------------------------- running
def run_case(asc_path, timeout_s):
    """Run one schematic in batch mode; return (ok, seconds, message)."""
    env = dict(os.environ, WINEDEBUG="-all")
    t0 = time.time()
    try:
        p = subprocess.run(["wine", LTSPICE, "-b", os.path.basename(asc_path)], cwd=os.path.dirname(asc_path),
                           env=env, capture_output=True, text=True, timeout=timeout_s)
        ok, msg = p.returncode == 0, (p.stderr or "").strip()[-300:]
    except subprocess.TimeoutExpired:
        ok, msg = False, "timeout after %d s" % timeout_s
    return ok, time.time() - t0, msg


def _flatten(meas):
    """{name: [v]} -> {name: v};  {name: [v1, v2]} (schematic still has its own .step) -> {name_s1: v1, name_s2: v2}."""
    out = {}
    for k, vals in meas.items():
        if len(vals) == 1:
            out[k] = vals[0]
        else:
            out.update({"%s_s%d" % (k, j + 1): v for j, v in enumerate(vals)})
    return out


def _say(*args):
    """print() that flushes at once, so a log file shows progress while the sweep runs (stdout to a file is buffered)."""
    print(*args, flush=True)


def run_sweep(asc_path, grid, fixed=None, jobs=None, name="sweep", keep_raw=False, timeout_min=60, dry_run=False,
              log=_say):
    """Run every combination of `grid` ({param: [values]}) in parallel. Returns the list of result rows."""
    asc_path = os.path.abspath(asc_path)
    base = os.path.splitext(os.path.basename(asc_path))[0]
    src = open(asc_path, "r", encoding="latin-1", newline="").read()
    out_dir = os.path.join(os.path.dirname(asc_path), "sweeps", name)
    os.makedirs(out_dir, exist_ok=True)
    jobs = jobs or default_jobs()
    names = list(grid)
    combos = list(itertools.product(*[grid[n] for n in names]))

    cases = []
    for k, combo in enumerate(combos, 1):
        params = dict(fixed or {}, **dict(zip(names, combo)))
        cdir = os.path.join(out_dir, "case_%03d" % k)
        os.makedirs(cdir, exist_ok=True)
        casc = os.path.join(cdir, base + ".asc")
        text = apply_params(src, params)
        old = open(casc, encoding="latin-1", newline="").read() if os.path.exists(casc) else None
        if old != text:   # schematic changed: any old results in this folder are stale
            for f in os.listdir(cdir):
                os.remove(os.path.join(cdir, f))
            open(casc, "w", encoding="latin-1", newline="").write(text)
        json.dump(params, open(os.path.join(cdir, "params.json"), "w"))
        cases.append((k, params, casc))

    log("%d cases x 1 LTspice run each, %d at a time -> %s" % (len(cases), jobs, out_dir))
    if dry_run:
        for k, p, _ in cases:
            log("  case_%03d  %s" % (k, p))
        return []

    def work(case):
        k, params, casc = case
        logf = casc[:-4] + ".log"
        meas = read_meas(logf) if os.path.exists(logf) else {}
        if meas:
            return k, params, dict(status="cached", seconds=0), meas
        ok, secs, msg = run_case(casc, timeout_min * 60)
        meas = read_meas(logf) if os.path.exists(logf) else {}
        if not keep_raw:
            for f in os.listdir(os.path.dirname(casc)):
                if f.endswith(".raw"):
                    os.remove(os.path.join(os.path.dirname(casc), f))
        status = "ok" if ok and meas else ("no .meas results" if ok else "failed: " + msg)
        return k, params, dict(status=status, seconds=round(secs, 1)), meas

    rows, t0 = {}, time.time()
    with ThreadPoolExecutor(max_workers=jobs) as pool:   # threads are enough: each one just waits on its LTspice process
        futs = [pool.submit(work, c) for c in cases]
        for n, f in enumerate(as_completed(futs), 1):
            k, params, info, meas = f.result()
            rows[k] = dict(case=k, **params, **_flatten(meas), **info)
            log("[%2d/%d] case_%03d %-28s %-8s %6.0f s   (elapsed %.0f s)" % (
                n, len(cases), k, ", ".join("%s=%s" % kv for kv in params.items()), info["status"], info["seconds"],
                time.time() - t0))

    rows = [rows[k] for k in sorted(rows)]
    cols = list(dict.fromkeys(c for r in rows for c in r))
    with open(os.path.join(out_dir, "results.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    log("done in %.0f s -> %s" % (time.time() - t0, os.path.join(out_dir, "results.csv")))
    return rows


def _kv(s):
    if "=" not in s:
        raise argparse.ArgumentTypeError("expected NAME=value")
    return s.split("=", 1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("asc")
    ap.add_argument("--param", type=_kv, action="append", default=[], help="NAME=v1,v2,...  (repeatable)")
    ap.add_argument("--set", type=_kv, action="append", default=[], help="NAME=value for every case (repeatable)")
    ap.add_argument("--jobs", type=int, default=None)
    ap.add_argument("--name", default="sweep")
    ap.add_argument("--keep-raw", action="store_true")
    ap.add_argument("--timeout-min", type=float, default=60)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if not a.param:
        ap.error("give at least one --param NAME=v1,v2,...")
    run_sweep(a.asc, {n: v.split(",") for n, v in a.param}, dict(a.set), a.jobs, a.name, a.keep_raw,
              a.timeout_min, a.dry_run)

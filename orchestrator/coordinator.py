#!/usr/bin/env python3
"""Agent coordinator: parallel Claude Code workers plus offline local-model (Ollama) jobs, one git worktree per task.

    python3 orchestrator/coordinator.py run              # loop forever (what the systemd service runs)
    python3 orchestrator/coordinator.py once             # start what fits, wait for everything, exit
    python3 orchestrator/coordinator.py add "title" "instructions..." [--model M]
    python3 orchestrator/coordinator.py add-local "title" "instructions..." --files a.md,b.py [--output path] [--model M]
    python3 orchestrator/coordinator.py status

Two kinds of task:
  worker: claude  (default)  a full Claude Code agent: reads, edits, runs LTspice/python. Uses your Claude usage.
  worker: ollama             ONE prompt to a local model (offline, free): the listed files are pasted in, the answer is
                             written to `output:` (default ORCHESTRATOR_REPORT.md). No tools, so keep it to summaries,
                             drafts, explanations, checklists. Runs one at a time (one model fits the 4 GB GPU). Default model
                             qwen2.5:3b: fits the GPU fully, about 20 s per answer; qwen3 reasons out loud and is slower.

Task files are Markdown in orchestrator/queue/. Optional header lines, then a blank line, then the instructions:
    title: Summarise topology 06
    worker: ollama
    files: Topologies/06_BEC_Synchronous_Buck_5V/README.md
    output: Topologies/06_BEC_Synchronous_Buck_5V/SUMMARY.md
    model: qwen2.5:3b
    timeout_min: 30
Each task runs on branch `local/<task-id>` in worktree `.worktrees/local-<task-id>`, cut from main; whatever it changed is
committed there. The coordinator never pushes and never merges: review the branch, then merge it yourself.
"""
import json, os, re, shutil, signal, subprocess, sys, time, urllib.request
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.join(ROOT, "orchestrator")
QUEUE, STATE, LOGS = (os.path.join(HERE, d) for d in ("queue", "state", "logs"))
WT_DIR = os.path.join(ROOT, ".worktrees")
CONFIG = {"workers": 2, "local_workers": 1, "model": None, "local_model": "qwen2.5:3b", "local_ctx": 6144, "local_max_chars": 14000, "local_max_tokens": 1200,
          "ollama_url": "http://127.0.0.1:11434", "timeout_min": 120, "poll_s": 20, "base_branch": "main",
          "allowed_tools": [], "disallowed_tools": [], "permission_mode": "acceptEdits"}
_cfg = os.path.join(HERE, "config.json")
if os.path.exists(_cfg):
    CONFIG.update(json.load(open(_cfg)))
for d in (QUEUE, STATE, LOGS, WT_DIR):
    os.makedirs(d, exist_ok=True)
ENV = dict(os.environ)
ENV["PATH"] = os.pathsep.join([os.path.expanduser("~/.local/bin"), "/usr/local/bin", ENV.get("PATH", "/usr/bin:/bin")])

HOUSE_RULES = """You are a worker agent in the drone LTspice topology project. Rules:
- Work ONLY inside the current directory (a git worktree on your own branch). Do not touch other folders.
- Read CLAUDE.md first and follow it (topology folder naming, design-doc rules, how to run LTspice under Wine).
- Never run git push, git merge, git rebase, or git checkout of other branches. Do not commit; the coordinator commits for you.
- Keep LTspice runs short and use .save; never create files over 50 MB outside *.raw.
- Run shell commands plainly, one per call, without env-var prefixes or chains (e.g. `wine "<LTspice.exe>" -b file.asc`, not
  `cd x && WINEDEBUG=-all wine ...`): only allow-listed command prefixes are permitted and anything else is refused.
- When you finish, write a short report to ORCHESTRATOR_REPORT.md in the current directory: what you did, results, what failed.

Your task:
"""
LOCAL_SYSTEM = ("You are a careful technical writer helping with a power-electronics learning project "
                "(LTspice simulations of drone motor drives). Use only the files provided; if something is not in them, "
                "say so instead of guessing. Answer in Markdown, concisely. Output only the final answer.")

def git(*args, cwd=ROOT, check=True):
    return subprocess.run(["git", *args], cwd=cwd, env=ENV, check=check, capture_output=True, text=True).stdout.strip()

def parse_task(path):
    lines = open(path).read().splitlines(); opts = {}; i = 0
    while i < len(lines) and re.match(r"^(\w+):\s*(.*)$", lines[i]):
        k, v = re.match(r"^(\w+):\s*(.*)$", lines[i]).groups(); opts[k] = v.strip(); i += 1
    tid = os.path.splitext(os.path.basename(path))[0]
    worker = opts.get("worker", "claude")
    model = opts.get("model") or (CONFIG["local_model"] if worker == "ollama" else CONFIG["model"])
    return {"id": tid, "title": opts.get("title", tid), "worker": worker, "model": model,
            "files": [f.strip() for f in opts.get("files", "").split(",") if f.strip()],
            "output": opts.get("output", "ORCHESTRATOR_REPORT.md"),
            "timeout_min": float(opts.get("timeout_min", 30 if worker == "ollama" else CONFIG["timeout_min"])),
            "body": "\n".join(lines[i:]).strip(), "file": path}

def state_path(tid): return os.path.join(STATE, tid + ".json")
def load_state(tid):
    p = state_path(tid)
    return json.load(open(p)) if os.path.exists(p) else None
def save_state(st): json.dump(st, open(state_path(st["id"]), "w"), indent=1)

# ---------------- local (Ollama) job: runs as a child process so the loop can time it out like any worker ----------------
def ollama_job(task_file, wt):
    t = parse_task(task_file)
    parts, budget = [], CONFIG["local_max_chars"]
    for f in t["files"]:
        p = os.path.join(wt, f)
        txt = open(p, errors="replace").read() if os.path.exists(p) else "(file not found)"
        if len(txt) > budget:
            txt = txt[:budget] + "\n...[truncated to fit the local model's context]"
        budget -= len(txt); parts.append(f"===== FILE: {f} =====\n{txt}")
        if budget <= 0: break
    user = ("\n\n".join(parts) + "\n\n===== TASK =====\n" if parts else "") + t["body"]
    req = {"model": t["model"], "stream": False, "think": False,
           "options": {"num_predict": CONFIG["local_max_tokens"], "num_ctx": CONFIG["local_ctx"], "temperature": 0.4},   # hard cap: small models can ramble forever
           "messages": [{"role": "system", "content": LOCAL_SYSTEM},
                                                              {"role": "user", "content": user}]}
    t0 = time.time()
    r = urllib.request.urlopen(urllib.request.Request(CONFIG["ollama_url"] + "/api/chat", json.dumps(req).encode(),
                                                      {"Content-Type": "application/json"}), timeout=t["timeout_min"] * 60)
    d = json.load(r)
    text = re.sub(r"<think>.*?</think>", "", d["message"]["content"], flags=re.S).strip()
    out = os.path.join(wt, t["output"]); os.makedirs(os.path.dirname(out) or wt, exist_ok=True)
    header = f"<!-- written offline by local model {t['model']} via the coordinator, task {t['id']}; review before trusting -->\n\n"
    open(out, "w").write(header + text + "\n")
    print(json.dumps({"result": text[:2000], "local_model": t["model"], "prompt_tokens": d.get("prompt_eval_count"),
                      "output_tokens": d.get("eval_count"), "seconds": round(time.time() - t0, 1), "output": t["output"]}))

# ---------------- workers ----------------
def start(task):
    tid = task["id"]; branch = f"local/{tid}"; wt = os.path.join(WT_DIR, f"local-{tid}")
    if not os.path.exists(wt):
        git("worktree", "add", "-b", branch, wt, CONFIG["base_branch"])
    log = open(os.path.join(LOGS, tid + ".log"), "w")
    if task["worker"] == "ollama":
        cmd = [sys.executable, os.path.abspath(__file__), "ollama-job", task["file"], wt]
    else:
        # unattended Claude Code worker: edits auto-accepted, shell only from the allow-list, anything else refused
        cmd = ["claude", "-p", HOUSE_RULES + task["body"], "--permission-mode", CONFIG["permission_mode"], "--output-format", "json"]
        if task["model"]: cmd += ["--model", task["model"]]
        if CONFIG["allowed_tools"]: cmd += ["--allowedTools", *CONFIG["allowed_tools"]]
        if CONFIG["disallowed_tools"]: cmd += ["--disallowedTools", *CONFIG["disallowed_tools"]]
    proc = subprocess.Popen(cmd, cwd=wt, env=ENV, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    st = {"id": tid, "title": task["title"], "worker": task["worker"], "model": task["model"], "status": "running",
          "branch": branch, "worktree": wt, "pid": proc.pid, "started": datetime.now().isoformat(timespec="seconds"),
          "timeout_min": task["timeout_min"]}
    save_state(st)
    print(f"[{st['started']}] started {tid} ({task['worker']}, {task['model']}) pid {proc.pid}", flush=True)
    return proc

def finish(st, code, timed_out=False):
    wt = st["worktree"]
    git("add", "-A", cwd=wt)
    changed = git("status", "--porcelain", cwd=wt)
    if changed:
        git("commit", "-q", "-m", f"[{st['worker']} worker] {st['title']}\n\nTask {st['id']}, model {st['model']}, exit {code}"
            + (" (timed out)" if timed_out else ""), cwd=wt)
    st.update(status="timeout" if timed_out else ("done" if code == 0 else "failed"), exit_code=code,
              finished=datetime.now().isoformat(timespec="seconds"), commit=git("rev-parse", "--short", "HEAD", cwd=wt),
              changed_files=len(changed.splitlines()) if changed else 0)
    rep = os.path.join(wt, "ORCHESTRATOR_REPORT.md")
    st["report"] = open(rep).read()[:2000] if os.path.exists(rep) else None
    try:   # both worker kinds end their log with one JSON line (claude -p --output-format json / ollama-job)
        out = json.loads(open(os.path.join(LOGS, st["id"] + ".log")).read().strip().splitlines()[-1])
        st["result"] = str(out.get("result", ""))[:2000]
        for k_src, k_dst in (("total_cost_usd", "cost_usd"), ("num_turns", "turns"), ("seconds", "seconds"),
                             ("output_tokens", "output_tokens"), ("output", "output")):
            if k_src in out: st[k_dst] = out[k_src]
    except Exception:
        pass
    save_state(st)
    done_dir = os.path.join(QUEUE, "done"); os.makedirs(done_dir, exist_ok=True)
    src = os.path.join(QUEUE, st["id"] + ".md")
    if os.path.exists(src): shutil.move(src, os.path.join(done_dir, st["id"] + ".md"))
    print(f"[{st['finished']}] {st['id']}: {st['status']}, {st['changed_files']} files changed, branch {st['branch']} @ {st['commit']}", flush=True)

def pending():
    return [parse_task(os.path.join(QUEUE, f)) for f in sorted(os.listdir(QUEUE))
            if f.endswith(".md") and load_state(f[:-3]) is None]

def loop(forever=True):
    running = {}; stop = {"flag": False}
    signal.signal(signal.SIGTERM, lambda *a: stop.update(flag=True))
    while True:
        for tid, (proc, st) in list(running.items()):
            code = proc.poll()
            elapsed = (datetime.now() - datetime.fromisoformat(st["started"])).total_seconds() / 60
            if code is None and elapsed > st["timeout_min"]:
                os.killpg(proc.pid, signal.SIGTERM); proc.wait(30); finish(st, -1, timed_out=True); del running[tid]
            elif code is not None:
                finish(st, code); del running[tid]
        if stop["flag"]:
            for proc, st in running.values():
                os.killpg(proc.pid, signal.SIGTERM)
            break
        busy = {"claude": sum(1 for _, s in running.values() if s["worker"] != "ollama"),
                "ollama": sum(1 for _, s in running.values() if s["worker"] == "ollama")}
        cap = {"claude": CONFIG["workers"], "ollama": CONFIG["local_workers"]}
        for task in pending():
            kind = "ollama" if task["worker"] == "ollama" else "claude"
            if busy[kind] < cap[kind]:
                proc = start(task); running[task["id"]] = (proc, load_state(task["id"])); busy[kind] += 1
        if not forever and not running and not pending():
            break
        time.sleep(CONFIG["poll_s"])

def add(title, body, model=None, worker=None, files=None, output=None):
    tid = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40]
    hdr = f"title: {title}\n" + (f"worker: {worker}\n" if worker else "") + (f"model: {model}\n" if model else "") \
        + (f"files: {files}\n" if files else "") + (f"output: {output}\n" if output else "")
    open(os.path.join(QUEUE, tid + ".md"), "w").write(hdr + "\n" + body + "\n")
    print("queued", tid)

def status():
    for t in pending():
        print(f"QUEUED   {t['id']}  [{t['worker']}] {t['title']}")
    for f in sorted(os.listdir(STATE)):
        if f.endswith(".json"):
            r = json.load(open(os.path.join(STATE, f)))
            extra = (f" ${r['cost_usd']:.2f}" if r.get("cost_usd") else "") + (f" {r['seconds']}s" if r.get("seconds") else "")
            print(f"{r['status'].upper():8s} {r['id']}  [{r.get('worker', 'claude')}] {r['title']}  -> {r['branch']}"
                  + (f" @ {r.get('commit')}" if r.get("commit") else "") + extra)

if __name__ == "__main__":
    a = sys.argv[1:] or ["status"]
    opt = lambda name: a[a.index(name) + 1] if name in a else None
    if a[0] == "run": loop(True)
    elif a[0] == "once": loop(False)
    elif a[0] == "ollama-job": ollama_job(a[1], a[2])
    elif a[0] == "add": add(a[1], a[2], model=opt("--model"))
    elif a[0] == "add-local": add(a[1], a[2], model=opt("--model"), worker="ollama", files=opt("--files"), output=opt("--output"))
    else: status()

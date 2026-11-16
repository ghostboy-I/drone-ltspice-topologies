# Agent coordinator

An always-on queue with two kinds of worker. Each task runs in its own git worktree, on its own branch.

| | Claude worker (`add`) | Local job (`add-local`) |
|---|---|---|
| What it is | A full Claude Code agent: reads, edits, runs LTspice and Python | One prompt to a local Ollama model, with the listed files pasted in |
| Good for | Design, simulation, debugging, documents | Summaries, drafts, checklists, explaining a file |
| Speed / cost | Minutes; uses your Claude usage | About 20 s; offline and free |
| Runs at once | `workers` (2) | `local_workers` (1: one model fits the 4 GB GPU) |
The coordinator never pushes or merges. You review each branch and merge it yourself.

## Use it
```bash
python3 orchestrator/coordinator.py add "Sweep Lph in topology 02" "In Topologies/02_..., run the Experiments-to-try sweep of Lph = 5u, 7.5u, 15u ..."
python3 orchestrator/coordinator.py status          # QUEUED / RUNNING / DONE / FAILED / TIMEOUT, with branch names
journalctl --user -u drone-agents -f                # live coordinator log
```
- Local job example:
  `python3 orchestrator/coordinator.py add-local "Explain topology 05" "Explain the soft-start in plain English" --files Topologies/05_Channel_Protection_Soft-Start_Reverse-Polarity/README.md --output Topologies/05_Channel_Protection_Soft-Start_Reverse-Polarity/EXPLAINED_local.md`
  Each output file is stamped as written by a local model. Small models make small factual slips, so review before merging.
- A task can also be written by hand as `orchestrator/queue/<id>.md`. Optional header lines are `title:`, `worker:` (`claude` or `ollama`), `model:`, `files:` and `output:` (local jobs only), and `timeout_min:`. Then a blank line and the instructions.
- Results:
  - branch `local/<id>`, worktree `.worktrees/local-<id>`;
  - the worker's own report in `ORCHESTRATOR_REPORT.md` on that branch;
  - result text, turns and cost in `orchestrator/state/<id>.json`;
  - the full output in `orchestrator/logs/<id>.log`.
- Review a branch with `git log -p main..local/<id>`, then `git merge local/<id>`. Clean up with `git worktree remove .worktrees/local-<id>` and `git branch -d local/<id>`.

## Settings (`config.json`)
| Key | Meaning |
|---|---|
| `workers` | Tasks run at once. 2 is sensible: LTspice runs on this laptop's CPU. |
| `local_model` / `local_ctx` / `local_max_tokens` | `qwen2.5:3b`, 6144-token context, 1200-token answer cap |
| `model` | `null` uses your Claude default. Can be overridden per task. |
| `permission_mode` | `acceptEdits`: file edits are automatic; shell commands only from `allowed_tools` |
| `allowed_tools` / `disallowed_tools` | The allow-list: wine, python3, pdftoppm and read-only shell/git are allowed. push, merge, reset, checkout, commit, `rm -rf` and web access are blocked. A worker that needs anything else is refused, never left waiting. |
| `timeout_min` | Hard stop per task. Whatever the worker changed so far is still committed, with status `timeout`. |

## Service
- Installed as a systemd **user** service: `~/.config/systemd/user/drone-agents.service`, enabled at login.
- Stop it: `systemctl --user stop drone-agents`. Turn it off for good: `systemctl --user disable --now drone-agents`.
- To keep it running while you are logged out: `loginctl enable-linger $USER`.
- Each worker uses your Claude usage. An idle queue costs nothing. The smoke test cost $0.17 in 4 turns.

## Local models: what was tested
- **Local jobs, used here:** `qwen2.5:3b` fits 100 % on the GPU and answers in about 20 s.
- **`qwen3`, rejected:** it reasons out loud even with thinking disabled. It is slower, and once filled its whole answer budget with reasoning.

## Local models as full agents (OpenCode): tested, not usable here
- Tested `qwen2.5-coder:7b`, `qwen3:8b` and `qwen3:4b` with 16K context, using the Modelfiles in `models/`.
- The 4 GB RTX 3050 Ti spills 40–67 % of each model onto the CPU. Even the 4B model did not finish a one-file task in 25 minutes.
- They remain useful for chat: `ollama run qwen3:4b`, or `opencode web`.
- Workers would need roughly a 12–16 GB GPU to be practical.

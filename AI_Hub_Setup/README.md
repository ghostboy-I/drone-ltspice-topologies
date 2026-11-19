# Session summary: Discord AI hub, GitHub access and MacBook compute worker

Date: 2026-11-18. Configs: [`configs/`](configs/). Secrets (bot token, Discord IDs, Mac username) are **not** in
this repo; they live only in the local files listed under "Where things live".

## Where things stand

- A Discord bot (**Claude_API**) runs Claude Code on the Linux laptop through the official Claude Code Channels
  Discord plugin. It takes requests in one channel, answers in a second and sends repo files to a third.
- The bot has **read-only** access to this repo (local clone, pull before answering, no edits/commits/pushes).
- The **MacBook (M2 Pro, 16 GB)** is a compute worker: the orchestrator's local-model worker now runs
  `qwen3:8b` on the Mac's GPU over the LAN instead of `qwen2.5:3b` on the laptop.
- The laptop can SSH into the Mac with a key (`ssh mac`); Claude only changes Mac files inside
  `~/claude environment`.
- Not done: running the bot as a boot-time service, a fixed IP for the Mac, Ollama auto-start on the Mac,
  bot-to-bot messaging.

## Decisions you made

| Decision | Choice |
|---|---|
| How to connect Claude to Discord | Claude Code Channels + `discord@claude-plugins-official` (bot you own) |
| Channel layout | Separate request, answer and file channels; notes in answers point to the file post |
| Who can trigger the bot | Only you: DM allowlist + request channel restricted to your user ID |
| Repo access for the bot | Read and send files only; no edits, commits or pushes |
| How to use the Mac | As a worker (Ollama over LAN + SSH), not a second Claude/bot |
| Model on the Mac | Keep `qwen3:8b`, raise context to 16k (14B doesn't fit 16 GB well) |
| Limit on Claude's Mac access | A folder rule (`~/claude environment`), not a separate locked-down Mac user |

## 1. Discord bot (Claude Code Channels)

**Installed on the laptop:** Claude Code 2.1.326, Bun 1.4.4 (`~/.bun/bin`, linked into `~/.local/bin` so the
plugin can find it), plugin `discord@claude-plugins-official` v0.0.6.

**Discord side (Developer Portal, app "Claude_API"):**
1. Bot tab: Reset Token (copy once), Message Content Intent **on**, Public Bot off.
   Turning Public Bot off fails with "private app cannot have a default authorization link" until
   Installation → Install Link is set to **None**.
2. OAuth2 → URL Generator: scope `bot`; View Channels, Send Messages, Send Messages in Threads. Open the URL,
   pick the server, Authorize.

**Claude side:**
```bash
claude                      # then: /discord:configure <token>   (saved to ~/.claude/channels/discord/.env)
cd ~/claude-discord && claude --channels plugin:discord@claude-plugins-official
```
DM the bot → it replies with a 6-character code → `/discord:access pair <code>`, then lock down:
```
/discord:access policy allowlist
/discord:access group add <REQUESTS_ID> --no-mention --allow <YOUR_USER_ID>
```

**Channels** (`~/.claude/channels/discord/access.json`, sanitized copy in
[`configs/access.example.json`](configs/access.example.json)):

| Channel | Purpose | Trigger rule |
|---|---|---|
| requests | You give instructions | Every message (no @mention), only your user ID |
| answers | Text answers + "sent to #files" notes | Mention only (effectively output-only) |
| files | Attachments from the repo | Mention only (output-only) |

Channel IDs come from the browser URL `discord.com/channels/<server>/<channel>` (last number), so Developer Mode
isn't needed. The plugin ignores **all bot and webhook messages**, so two bots can't talk to each other
without patching it.

**Routing rules** live in `~/claude-discord/CLAUDE.md` (copy: [`configs/bot-CLAUDE.md`](configs/bot-CLAUDE.md));
Claude reads it at startup, so restart the bot after editing it. `access.json` changes apply immediately.

**Keeping it running:** the bot only works while that terminal session runs. Use tmux:
```bash
tmux new -s claude-bot      # start the bot inside, then Ctrl+B, D to detach
tmux attach -t claude-bot   # come back; /exit or `tmux kill-session -t claude-bot` to stop
```
Permission prompts the bot hits are relayed to Discord as 🔐 Allow/Deny buttons (allowlisted users only).

## 2. GitHub repo access (read-only)

- Clone: `~/claude-discord/drone-ltspice-topologies` (public repo, no auth needed to read).
- `~/claude-discord/.claude/settings.json` (copy: [`configs/bot-settings.json`](configs/bot-settings.json))
  pre-allows reads, `git pull/log/status/ls-files/show` and the Discord tools; **denies** edits, commits, pushes,
  `gh`, and reading the bot token / GitHub login / `.env` files. (The laptop is logged in to GitHub, so without the
  deny list the bot could change the repo.)
- Files go to the files channel; anything over Discord's upload limit (10 MB unboosted) is posted as a GitHub link.

## 3. MacBook as a compute worker

**Ollama on the Mac** (started from a Mac terminal; it stops if that window closes):
```bash
OLLAMA_HOST=0.0.0.0 OLLAMA_CONTEXT_LENGTH=32768 ollama serve
```
Each request shows there as `[GIN] ... | 200 | 4.67s | <laptop IP> | POST "/api/chat"`.

**Orchestrator change** (`orchestrator/config.json` on branch `prop-54x18`, uncommitted at the time of writing):

| Setting | Before | After |
|---|---|---|
| `ollama_url` | `http://127.0.0.1:11434` | `http://<MAC_IP>:11434` |
| `local_model` | `qwen2.5:3b` | `qwen3:8b` |
| `local_ctx` | 6144 | 16384 |
| `local_max_chars` | 14000 | 40000 |
| `local_max_tokens` | 1200 | 2500 |

**Measured on the M2 Pro:** qwen3:8b at 16k context = 6.9 GB, fully on GPU; ~30 tokens/s generation,
~150–240 tokens/s prompt reading; a short prompt round-trips in ~4.7 s (2.3 s of that is model load).
qwen3:14b + 16k would need ~11–12 GB against the ~10–11 GB GPU limit on a 16 GB Mac, so it would spill to CPU.

**Send a prompt to the Mac yourself (from the laptop):**
```bash
OLLAMA_HOST=<MAC_IP>:11434 ollama run qwen3:8b --think=false "your question"
```

**SSH into the Mac:** Remote Login on (System Settings → General → Sharing), then on the laptop
`ssh-keygen -t ed25519`, `ssh-copy-id <MACUSER>@<MAC_IP>`, and a `Host mac` entry in `~/.ssh/config`.
```bash
ssh mac                                  # Mac shell
ssh mac -t 'tmux new -A -s mac-claude'   # persistent session on the Mac
```

**Claude's folder on the Mac:** `~/claude environment`. The laptop helper
[`configs/macenv`](configs/macenv) runs every command from inside it (`macenv 'ls'`, or `macenv` for a shell).
This is a rule Claude follows, not an OS-enforced sandbox.

**Agents for qwen3:8b:** the orchestrator (one focused request with files inline) is the best fit; Aider
(`aider --model ollama_chat/qwen3:8b --edit-format whole`) for hands-on edits; Claude Code on qwen3:8b works only
for small supervised tasks and needs `OLLAMA_CONTEXT_LENGTH=32768`.

## Where things live

| What | Path (machine) |
|---|---|
| Bot token | `~/.claude/channels/discord/.env` (laptop) — never commit or share |
| Discord access / channels | `~/.claude/channels/discord/access.json` (laptop) |
| Bot folder, rules, permissions, repo clone | `~/claude-discord/` (laptop) |
| Orchestrator config | `orchestrator/config.json` in this repo |
| Mac helper | `~/.local/bin/macenv` (laptop), `~/.ssh/config` `Host mac` |
| Claude's Mac folder | `~/claude environment` (Mac) |

## Known limits and next steps

- The Mac must be awake and on the same Wi-Fi; reserve its IP in the router (or use Tailscale for off-LAN).
- Ollama on the Mac stops when its terminal closes; make it a login item or `brew services` with
  `OLLAMA_HOST=0.0.0.0`.
- The bot stops on reboot; a systemd user service wrapping tmux would bring it back automatically.
- Plugin updates overwrite `~/.claude/plugins/cache/...`; nothing there was modified.
- Ideas not built yet: one thread per task, orchestrator → Discord webhook status posts, an `#alerts`
  channel, a patched `#agent-bus` for bot-to-bot messages with loop limits.

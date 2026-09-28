# Apex Harness — Setup Guide

Complete installation and configuration instructions for **Linux, macOS, and Windows**.

---

## 1. Prerequisites

| Requirement | Details |
|---|---|
| Python | **3.10 or newer** — check with `python3 --version` (Linux/macOS) or `py --version` (Windows) |
| Python packages | [`requests`](https://pypi.org/project/requests/) and [`rich`](https://github.com/Textualize/rich) |
| Genspark account | A logged-in browser session on [genspark.ai](https://www.genspark.ai) — you'll export its cookies |
| OS | Linux, macOS, or Windows 10/11 (Windows under WSL also works — see §5) |

---

## 2. Install

### Step 1 — Get the code

```bash
git clone https://github.com/Alaqmar-morawala/apex-harness.git
cd apex-harness
```

### Step 2 — Install Python dependencies

**Linux / macOS:**
```bash
python3 -m pip install --user requests rich
# or, isolated:
python3 -m venv .venv
source .venv/bin/activate
pip install requests rich
```

**Windows (cmd or PowerShell):**
```cmd
py -m pip install requests rich
```

### Step 3 — Export your Genspark cookies

Apex authenticates to Genspark with your browser session cookies.

1. Log in to **genspark.ai** in Chrome/Firefox.
2. Open DevTools (**F12**) → **Application** tab (Firefox: **Storage**) → **Cookies** → `https://www.genspark.ai`.
3. Export the cookie list as a JSON array. The format Apex expects (this is the standard "EditThisCookie"/DevTools export shape):

```json
[
  { "name": "session_id", "value": "v2.prod-...", "domain": "www.genspark.ai", "path": "/" },
  { "name": "c1", "value": "...", "domain": "www.genspark.ai", "path": "/" },
  { "name": "c2", "value": "...", "domain": "www.genspark.ai", "path": "/" }
]
```

The critical cookies are **`session_id`, `c1`, and `c2`** — extra analytics cookies are harmless and ignored.

4. Save the file as **`cookies.json`** in the `apex-harness` folder.

> **Multiple accounts:** drop additional jars next to it as `cookies_2.json`, `cookies_3.json`, … Apex auto-discovers all `cookies*.json` files, deduplicates them, and round-robins requests with automatic 429 failover.

> **Security:** `cookies.json` is a live session credential. It is git-ignored by the repo's whitelist `.gitignore` — never commit it, paste it, or share it.

### Step 4 — Verify

```bash
# Linux / macOS
chmod +x apex
./apex --version        # -> apex 1.2.0
./apex -q "What is 2+2? One number."
```

```cmd
:: Windows
apex.cmd --version
apex.cmd -q "What is 2+2? One number."
```

If you see the numbered answer, you're done. Launch the interactive REPL with `./apex` (or `apex.cmd`).

---

## 3. Platform behavior

| | Linux / macOS | Windows |
|---|---|---|
| Shell backend | Persistent **bash** in a PTY (`pty` + `fork`) | Persistent **cmd.exe** with piped stdio (`/Q /K /D`, UTF-8 codepage) |
| State persistence | `cd`, exports, venvs survive across tool calls | `cd`, `set`, and per-process env survive across tool calls |
| Shell syntax for the model | bash (`ls`, `cat`, `rm`, …) | Windows (`dir`, `type`, `del`, `where`, …) — the system prompt tells the model automatically |
| `grep` tool | shell `grep -rn` | **native Python** recursive regex search (no grep binary needed) |
| Command history | readline, persisted at `~/.apex/history` | console-host line editing (no persistent history) |
| Launcher | `./apex` (bash wrapper) | `apex.cmd` (auto-picks `py` or `python`) |

Everything else — models, tools, undo, account pool, UI — behaves identically on every platform.

---

## 4. Optional configuration (environment variables)

| Variable | Purpose |
|---|---|
| `GENSPARK_COOKIES_JSON` | Pass the cookie jar as a JSON string instead of a file (CI/headless friendly) |
| `GENSPARK_RECAPTCHA_TOKEN` | Only needed if Genspark returns 403 with valid cookies — normally leave empty |

---

## 5. Windows via WSL (alternative)

If you prefer a full Linux environment on Windows, run Apex inside **WSL2** — the POSIX PTY path is used and behaves exactly like native Linux:

```bash
wsl --install            # once, from an elevated PowerShell, then reboot
# inside Ubuntu:
sudo apt update && sudo apt install -y python3-pip
git clone https://github.com/Alaqmar-morawala/apex-harness.git
cd apex-harness && python3 -m pip install --user requests rich
chmod +x apex && ./apex
```

Pick native Windows (§3, cmd.exe backend) for simplicity, or WSL when you need bash tooling (`apt`, `git` hooks, Linux-only CLIs).

---

## 6. Troubleshooting

**`RuntimeError: No Genspark cookies found`**
→ `cookies.json` is missing/empty or not in the working directory. Re-export per §2 Step 3, or set `GENSPARK_COOKIES_JSON`.

**`401 / 403 Unauthorized` on every request**
→ Your session expired or you logged out in the browser (logout invalidates `session_id`/`c1`/`c2`). Re-export fresh cookies. Apex auto-disables dead accounts and fails over; with only one jar, a re-export is required.

**Frequent `429` / `[pool] ... rate-limited → failover`**
→ Normal under load. The account cools down 60s and traffic rotates. Add more `cookies_N.json` jars to spread the load.

**`ModuleNotFoundError: requests` / `rich`**
→ `pip install requests rich` into the interpreter that runs Apex. On Windows use `py -m pip`, and make sure `py`/`python` is the same install you installed into.

**`apex.cmd` opens and closes instantly**
→ Run it from an existing cmd/PowerShell window to see the error; verify `py --version` works.

**Commands print garbage characters (Windows)**
→ Apex already switches cmd.exe to UTF-8 (`chcp 65001`). If your terminal still mangles output, switch the console font to a TrueType font or use Windows Terminal.

**Model uses bash syntax on Windows (`ls`, `cat` fail)**
→ The system prompt instructs the model to use Windows syntax. If it slips, just say: *"You are on Windows — use dir/type/del and the dedicated tools."*

---

## 7. Skills

Skills are markdown instruction packs the agent loads on demand. Bundled packs live in `skills/` (git-workflow, debugging, code-review, security-recon, python-testing, writing-docs).

**Add your own** — drop a `.md` file into `~/.apex/skills/` (all projects) or `<project>/.apex/skills/` (this project only):

```markdown
---
name: my-skill
description: One line the model sees when deciding whether to load it
---
Instructions for the agent...
```

Manage in the REPL: `/skills` lists what's installed; `/skill my-skill` forces it onto the next task. The model also self-loads matching skills via the `skill` tool.

---

## 8. Updating

```bash
git pull
pip install -U requests rich   # occasionally
```

Cookie refresh: re-export `cookies.json` whenever sessions expire — everything else is stateless.

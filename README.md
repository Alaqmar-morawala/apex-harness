# ⚡ Apex Harness

A native, single-file autonomous coding agent built for **Genspark models**. Apex owns the entire agent loop — no intermediary protocol translation, no shim layers — connecting directly to Genspark's streaming API and executing real tools on your local machine.

> **Why it exists:** Routing Genspark models through generic harnesses (Anthropic/OpenAI protocol shims) caused schema validation errors, token blowouts, and subagent stalls. Apex eliminates the translation layer: it speaks to Genspark natively and runs a ReAct loop with local tool execution.

---

## Features

- **Direct SSE streaming** to Genspark's `ask_proxy` endpoint with live token counter and single-pass compiled Markdown output
- **Multi-account pool** — auto-discovers `cookies*.json`, round-robin rotation, 429 cooldown with automatic failover, 401/403 account disablement, network-error failover
- **Persistent PTY shell** — `cd`, exports, and virtualenvs survive across tool calls; auto-restarts if the shell dies
- **Atomic file tools** — `write_file` / `edit_file` with automatic snapshots and instant `/undo` (50-deep stack)
- **Depth-aware tool parser** — handles nested `<tool>` examples inside file contents, ignores tool examples inside markdown code fences/backticks, salvages unclosed tags at end-of-stream
- **Context compaction** — 22k-char active budget with head/tail preservation and automatic tool-result summarization
- **30+ model catalog** — Opus 5.5 (default), Sonnet 5, GPT-5.6 Sol, Gemini 3.8 Flash, and more, switchable mid-session
- **Hardened UI** — bounded output truncation with honest counts, no terminal floods, Ctrl+C aborts the task but preserves the session

## Quickstart

```bash
# requires: python3 with `requests` and `rich`, plus a valid cookies.json
./apex                      # interactive REPL
./apex -q "create a flask hello world"        # single task
./apex --model gpt-5.6-sol --search           # pick model + web search
```

## REPL commands

`/model` · `/search` · `/accounts` · `/undo` · `/reset` · `/steps` · `/history` · `/clear` · `/help` · `/exit`

## Architecture

```
User prompt ──▶ AgentEngine (ReAct loop, max 30 steps)
                 │
                 ├─▶ GensparkClient ── POST ask_proxy (SSE)
                 │     └─ AccountPool (round-robin, 429/401/network failover)
                 │
                 └─▶ ToolRegistry ── local execution
                       ├─ bash        (persistent PTY, sentinel exit codes)
                       ├─ read_file   (line numbers, offset/limit)
                       ├─ write_file  (snapshots + /undo)
                       ├─ edit_file   (exact-match replace, unified diff)
                       ├─ list_dir    (native os.walk, depth-limited)
                       └─ grep        (regex + include filters)
```

Full engineering detail — including the six critical bugs solved during development and the production-hardening record — lives in [APEX_HARNESS_HANDOFF.md](APEX_HARNESS_HANDOFF.md). User guide: [APEX_HARNESS.md](APEX_HARNESS.md). Genspark API reference: [API.md](API.md).

## Security notes

- `cookies*.json` contains live Genspark session credentials (`session_id`, `c1`, `c2`) and is **git-ignored by whitelist** — never commit or share it.
- The repository uses a whitelist `.gitignore`: only the harness, launcher, and documentation are tracked.
- Apex runs in auto-execute mode: the model's bash commands run as your user. Use it in workspaces you trust.

## Requirements

- Python 3.10+ with [`requests`](https://pypi.org/project/requests/) and [`rich`](https://github.com/Textualize/rich)
- A Genspark account (export browser cookies to `cookies.json`)

---

*Status: v1.1.0 — QA-verified with 26/26 unit tests and an 11/11 live end-to-end acceptance suite.*

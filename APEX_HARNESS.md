# Apex Harness — Technical Documentation & User Guide

**Apex** is a native, dedicated autonomous coding agent harness purpose-built for Genspark models. It connects directly to Genspark's streaming API and orchestrates local command execution, code editing, and environment management with a persistent PTY shell, atomic diffs, and context management.

> **Platforms:** Linux, macOS, and Windows. First-time setup (dependencies, cookie export, per-platform notes): see **[SETUP.md](SETUP.md)**.

---

## 1. Quickstart

Launch the interactive REPL:
```bash
./apex
```

Execute a single prompt directly from the shell:
```bash
./apex -q "list python files and find all TODO comments"
```

Use a specific model:
```bash
./apex --model claude-sonnet-5
```

Enable web search capabilities:
```bash
./apex --search -q "What are the latest updates to Python 3.14?"
```

---

## 2. CLI Options

| Flag | Default | Description |
|---|---|---|
| `-q, --query <str>` | `None` | Run in non-interactive single-task mode |
| `--model <str>` | `claude-sonnet-5` | Select model from the catalog |
| `--cookies <path>` | `cookies.json` | Path to cookie file(s), comma-separated |
| `--search` | `False` | Enable Genspark AI Chat live web search |
| `--max-steps <int>` | `30` | Max ReAct iterations per task |
| `--version` | — | Display version information |

---

## 3. Interactive REPL Slash Commands

Inside `./apex`, the following commands are available:

- `/model [name]` — Show current model, display full catalog, or switch models on the fly.
- `/search [on|off]` — Toggle real-time search engine integration.
- `/accounts` — View status of all accounts in the pool (active, cooldowns, request counts, rate-limits).
- `/undo` — Revert the last file write or edit instantly.
- `/reset` — Clear conversation context and reset the upstream Genspark project thread.
- `/clear` — Clear the terminal viewport.
- `/steps [n]` — View or update the maximum ReAct step threshold.
- `/history` — Check conversation turn count, current char count, and memory budget usage.
- `/help` — Display command overview.
- `/exit` (or `/q`) — Terminate session and shut down the background PTY shell.

---

## 4. Architecture Overview

```
                      ┌───────────────────────────────────────┐
                      │              User Prompt              │
                      └──────────────────┬────────────────────┘
                                         │
                                         ▼
                      ┌───────────────────────────────────────┐
                      │         Apex Harness Engine           │
                      │   - Context Manager (Compactor)       │
                      │   - Tool Call Parser (XML/JSON/MD)    │
                      └──────────────────┬────────────────────┘
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 ▼                                               ▼
    ┌───────────────────────────┐                 ┌───────────────────────────┐
    │     Genspark Client       │                 │     Execution Engine      │
    │ - SSE Streaming Parser    │                 │ - Persistent PTY bash     │
    │ - Multi-Account Pool      │                 │ - Atomic File Diff/Undo   │
    │ - Auto 429 Failover       │                 │ - Truncated Output Bounds │
    └───────────────────────────┘                 └───────────────────────────┘
```

### § 1. GensparkClient & Account Pool
- **Direct Streaming**: Interacts with `POST https://www.genspark.ai/api/agent/ask_proxy` via Server-Sent Events (SSE). Streams tokens directly to stdout with minimal latency.
- **Thread Continuity**: Preserves conversations across steps using `project_id` and `last_seen_event_index`.
- **Multi-Account Pooling**: Auto-discovers all `cookies*.json` in the working directory. Performs round-robin rotation, handles HTTP 429 rate-limiting with 60-second cooldown queues, and automatically disables accounts encountering authentication errors (401/403).

### § 2. Execution Engine
- **Persistent PTY Shell**: Implemented with `pty.openpty()` + `os.fork()`. Terminal echo is disabled (`~termios.ECHO`) and a unique sentinel exit code tracker (`__APEX_<uuid>__:$?`) ensures reliable asynchronous command synchronization. Virtualenvs, directory changes (`cd`), and environment exports persist naturally across tool calls.
- **File Snapshots & `/undo`**: Every file written or modified by the agent is automatically snapshotted into an in-memory undo stack, allowing immediate rollback with `/undo`.
- **Tool Suite**:
  - `bash`: Run commands in the persistent PTY shell.
  - `read_file`: Read content with 1-indexed line numbers, offset, and limit.
  - `write_file`: Create or overwrite files atomically.
  - `edit_file`: Exact string replacement with unified diff output.
  - `list_dir`: Recursive file listing excluding noisy caches (`.git`, `node_modules`, `__pycache__`).
  - `grep`: Pattern searching across directories with file filtering.

### § 3. Hybrid Tool Parser
Supports multiple syntax formats emitted by different LLMs:
1. **XML Tags** (Primary): `<tool name="bash">ls -la</tool>`
2. **JSON Payloads**: `{"tool": "read_file", "path": "file.py"}` (with automatic trailing-comma repair and balanced-brace extraction)
3. **Markdown Code Blocks**: ` ```bash\ncommand\n``` `

### § 4. Context Compaction & Compiled Markdown UI
- **Live Terminal Markdown Compiler**: Uses `rich.markdown` and `rich.live` to compile and render Markdown in real-time as tokens stream in. Headers, bold/italic text, lists, and syntax-highlighted code blocks are fully compiled in the terminal instead of displaying raw `#`, `**`, or backtick fences. Tool XML tags (`<tool ...>`) are automatically intercepted and rendered into clean tool execution cards.
- **Context Compaction**: Maintains active character budget (default: 22,000 chars). Preserves system prompt, user intent, and recent working turns while auto-summarizing verbose tool outputs.

---

### § 5. Skill System
Skills are reusable instruction packs the model loads on demand (progressive disclosure — only the name/description list lives in the system prompt; full instructions enter context only when used).

- **Loading by the model**: `<tool name="skill" name="git-workflow">` returns the skill body prefixed with an activation header.
- **Loading by you**: `/skill <name>` queues a skill; it activates at the start of your next task. `/skills` lists everything installed.
- **Locations** (later overrides earlier on name clashes): bundled repo `skills/` → user-global `~/.apex/skills/` → project-local `<cwd>/.apex/skills/`.
- **Format**: markdown with optional frontmatter:
  ```markdown
  ---
  name: my-skill
  description: One line — shown to the model in the skills list
  ---
  Instructions for the agent...
  ```
- **Bundled packs** (internet-adapted, attributed): `test-driven-development` (Iron Law: no production code without a failing test first), `systematic-debugging` (4-phase root-cause process), `verification-before-completion` (evidence-before-claims gate function), `writing-plans` (verifiable numbered steps), `brainstorming` (design-before-code for ambiguous/large work), `git-workflow`, `code-review`, `python-testing`, `security-recon` (authorized testing only), `writing-docs`. Adapted from [obra/superpowers](https://github.com/obra/superpowers) (MIT) and tailored to Apex's tool contract (paged reads, one tool per step, write_file contract).

## 6. Model Catalog

Apex provides access to the complete Genspark model fleet, including:

- **Coding & General SOTA**: `claude-sonnet-5`, `claude-sonnet-4-6`, `gpt-5.6-sol`, `gpt-5.5`, `gpt-5.4`, `gemini-3.1-pro-preview`, `grok-4.6`, `deepseek-v4-pro`, `kimi-k3`
- **Reasoning**: `claude-opus-5-5` (**default** — Claude Opus 5.5; NOTE: hyphen id — dot variants like `opus-5.5` are fake ids that silently serve Sonnet 4.5), `claude-opus-5`, `claude-opus-4-8`, `gpt-5.5-pro`, `gpt-5.4-pro`, `gpt-5.2-pro`
- **Fast / Lightweight**: `claude-4-5-haiku`, `gemini-3.8-flash`, `gemini-3.7-flash`, `gpt-5.6-luna`, `gpt-5.4-nano`, `minimax-m3`
- **Mixture-of-Agents (MoA)**: Run multi-model consensus via `/model genspark-moa` (combining GPT-5.1, Claude Sonnet 4.6, and Gemini 3.1 Pro).

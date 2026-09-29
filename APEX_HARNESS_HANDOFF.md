# APEX HARNESS — COMPREHENSIVE ENGINEERING HANDOFF & ARCHITECTURE MANUAL
**Version:** 1.9.9  
**Date:** 2026-09-29  
**GitHub Repository:** [https://github.com/Alaqmar-morawala/apex-harness](https://github.com/Alaqmar-morawala/apex-harness) (Public, Branch `main`)  
**Host Environment:** Linux 7.1.5+kali-amd64 x64 (`Alaqmars-WorkStation`)  
**Primary Executable:** `apex` (globally symlinked to `~/.local/bin/apex`), backed by `/home/alaqmar/test/apex_harness.py`  
**Primary Workspaces:** `/home/alaqmar/test` and `/home/alaqmar/Desktop/Auto Bug Bounty`  

---

## 1. Executive Summary & Genesis

### Why Apex Exists (The Failure of Translation Shims)
Prior to Apex, the project attempted to bridge Genspark AI Chat models into Claude Code CLI using a custom Python translation proxy (`genspark_provider.py`, ~2,400 LOC) listening on `http://localhost:8788`. That approach failed structurally:
1. **Schema Validation Collapses**: Claude Code expects strict Anthropic tool-use schema blocks (`tool_use` with valid JSON `input`). Genspark is a raw streaming text model. Attempting to parse, repair, and translate streaming text into Anthropic JSON blocks produced recurring validation errors.
2. **Token Blowouts**: Re-assembling conversation history and feeding cumulative prompt transcripts into Claude Code caused catastrophic token explosions.
3. **Subagent Stall Loops**: Claude Code subagents repeatedly stalled on greeting turns or generic acknowledgments ("Understood, I will now...").
4. **Fragile JSON Salvaging**: When models emitted slightly malformed tool calls, regex salvaging continually drifted and broke.

### The Apex Solution: Native ReAct Agent Architecture
**Apex Harness** completely eliminates intermediary translation proxies. It connects directly to Genspark's reverse-engineered Server-Sent Events (SSE) endpoint (`POST https://www.genspark.ai/api/agent/ask_proxy`) and runs a native, local ReAct (Reasoning + Acting) loop directly on the developer's workstation. 

Apex owns:
- The streaming client connection and account pool.
- The stateful persistent PTY shell (Linux/macOS) and cmd.exe process (Windows).
- The atomic file tools with automatic undo snapshots.
- Context budgeting and active compaction.
- The single-pass compiled Markdown terminal user interface.
- Agentic subagent delegation and modular skill execution.

---

## 2. Complete File System & Workspace Inventory

```
/home/alaqmar/test/
├── apex                                # Executable Bash wrapper launcher (readlink-aware, chmod +x)
├── apex.cmd                            # Windows batch launcher (auto-picks py or python)
├── apex_harness.py                     # Single-file core Apex runtime (~3,000 LOC, v1.9.9)
├── APEX_HARNESS.md                     # User documentation and CLI reference manual
├── APEX_HARNESS_HANDOFF.md             # THIS FILE: Definitive engineering handoff and technical manual
├── API.md                              # Reverse-engineered Genspark API reference & protocol spec
├── SETUP.md                            # Comprehensive setup guide (Linux, macOS, Windows, WSL2)
├── README.md                           # Public repository landing page
├── .gitignore                          # Whitelist gitignore (strictly prevents credential & log leaks)
├── cookies.json                        # Account 1: earnybuddy@gmail.com (Plus Plan)
├── cookies_2.json                      # Account 2: alaqmarabbas7@gmail.com (Plus Plan)
├── cookies_3.json                      # Account 3: alaqmar04@gmail.com (Plus Plan)
├── skills/                             # Bundled modular skill packs (Agentic Skills Library)
│   ├── test-driven-development.md      # TDD Iron Law: red-green-refactor cycle
│   ├── systematic-debugging.md         # 4-phase root-cause debugging methodology
│   ├── verification-before-completion.md # Evidence-before-claims gate function
│   ├── writing-plans.md                # Actionable, verifiable implementation plans
│   ├── brainstorming.md                # Design-before-code for ambiguous/large tasks
│   ├── git-workflow.md                 # Atomic conventional commits & branch hygiene
│   ├── code-review.md                  # Defect-first code review checklist (P0-P3)
│   ├── python-testing.md               # Targeted pytest patterns & regression rules
│   ├── security-recon.md               # Authorized testing only, scope-gate first
│   └── writing-docs.md                 # Anti-doc-sprawl and single-purpose documentation
├── ~/.local/bin/apex                   # Global symlink pointing to /home/alaqmar/test/apex
├── ~/.apex/history                     # Persistent REPL readline command history
└── ~/.apex/session.json                # Persisted thread handle for lossless /resume
```

---

## 3. Architecture Deep Dive

```
                             ┌───────────────────────────────────┐
                             │            User Prompt            │
                             └─────────────────┬─────────────────┘
                                               │
                                               ▼
                             ┌───────────────────────────────────┐
                             │       ApexCLI & AgentEngine       │
                             │  - Multi-Turn Project Threading   │
                             │  - Single-Line Spinner (Rich)     │
                             │  - Single-Pass Markdown Compiler  │
                             │  - Character-Break Auto-Recovery  │
                             └──────┬─────────────────────┬──────┘
                                    │                     │
                     Step 1: System │                     │ Step 2+: Tool Results
                     + User Input   │                     │ (Only new deltas!)
                                    ▼                     ▼
                       ┌────────────────────────┐  ┌─────────────────────────┐
                       │    GensparkClient      │  │    Execution Engine     │
                       │ - POST ask_proxy (SSE) │  │ - Persistent PTY bash   │
                       │ - AccountPool (3 Accts)│  │   (Windows: cmd.exe)    │
                       │ - 30-min Usage Cooldown│  │ - Pure Python grep      │
                       │ - Thread-Account Pin   │  │ - Atomic os.replace     │
                       │ - Stream Finished Flag │  │ - FileSnapshot (/undo)  │
                       └────────────────────────┘  └─────────────────────────┘
```

### § 3.1. GensparkClient & Multi-Account Pool
- **Endpoint**: `POST https://www.genspark.ai/api/agent/ask_proxy`
- **Protocol**: Server-Sent Events (SSE). Streams JSON objects prepended with `data: `.
- **Authentication**: Cookie jar loaded from `cookies.json`, `cookies_2.json`, `cookies_3.json`, or environment variable `GENSPARK_COOKIES_JSON`.
- **Required Headers** (Mandatory for Cloudflare bypass without captcha tokens):
  ```python
  {
      "Content-Type": "application/json",
      "Origin": "https://www.genspark.ai",
      "Referer": "https://www.genspark.ai/agents?type=ai_chat",
      "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
      "X-Timezone": "Asia/Calcutta",
      "Accept": "text/event-stream"
  }
  ```
- **SSE Stream Lifecycle**:
  - `project_start`: Delivers `id` (`project_id`) representing the server-side conversation thread.
  - `message_field_delta`: Carries streaming token chunks in `delta`.
  - `message_result`: Contains authoritative final message content and `message.session_state._llm_model` (the actual served model) and `_llm_usage`.
  - `project_field` (`status=FINISHED`): Officially marks the end of the server stream.

### § 3.2. Multi-Turn Threading Protocol (CRITICAL RULE)
1. **Turn 1 (New Task)**:
   - Request passes `project_id = None` and `last_seen_event_index = -1`.
   - Query payload contains `_system_prompt(skills) + "\n\nUser: " + user_input`.
   - Genspark initializes the thread, binds it to the authenticated account (`project_owner`), and returns `project_id`.
2. **Turn 2+ (Subsequent Tool Invocations)**:
   - Request passes the active `project_id` and updated `last_seen_event_index`.
   - Query payload contains **ONLY** the new tool output:
     ```text
     Tool Result [{tool_name}]:
     {output}
     ```
   - **DO NOT RESEND CUMULATIVE TRANSCRIPTS**: Genspark maintains conversation state server-side. Resending cumulative history triggers safety refusals (*"I don't have tools, this was simulated"*) or causes empty stream termination.
3. **Thread-Account Pinning (`project_owner`)**:
   - A thread created on Account A **cannot** be continued by Account B. Cross-account continuation results in empty responses or 403 errors.
   - If Account A hits a rate limit or usage window mid-task, `GensparkClient` raises `ThreadResetByFailover`.
   - The engine catches this, resets the server thread (`project_id = None`), and immediately re-anchors the task onto Account B by sending the full compacted local context.

### § 3.3. Persistent Execution Engine
- **POSIX Backend (`_PosixShell`)**:
  - Spawns bash using `pty.openpty()` + `os.fork()`.
  - Terminal echo is disabled (`termios.ECHO` stripped) so sent commands never pollute stdout.
  - History expansion is disabled (`set +H`) so exclamation marks (`!`) do not corrupt command execution or exit codes.
  - Synchronized via sentinel exit-code marker: `command\n__apex_ec=$?\necho "__APEX_<uuid>__:$__apex_ec@CWD@$PWD"\n`.
  - Auto-restarts child bash if killed by an `exit` command.
  - Resolves timeouts cleanly: sends `\x03` (Ctrl+C) to PTY and re-sends the sentinel line. Interruptible commands stay alive and maintain `cd`/env state; unkillable commands cleanly restart the shell.
- **Windows Backend (`_WindowsShell`)**:
  - Spawns `cmd.exe /Q /K /D` with piped stdio and UTF-8 codepage (`chcp 65001`).
  - Reads output via daemon thread pushing lines to a thread-safe `queue.Queue`.
  - Sentinel tracks exit codes and current directory: `echo __APEX_<uuid>__:%errorlevel%@CWD@%CD%`.
- **Tool Suite**:
  - `bash`: Stateful command execution.
  - `read_file`: Line-numbered output with default 250-line paging (`READ_WINDOW = 250`). Emits explicit continuation hints (`offset=251 limit=250`) to prevent context blowouts.
  - `write_file`: Atomic writes via `.apex-<uuid>.tmp` + `os.replace`. Preserves existing CRLF line endings. Automatic file snapshotting.
  - `edit_file`: Strict single-match string replacement (`old_string` -> `new_string`). Unified diff output capped to avoid context explosion. Automatic file snapshotting. Refuses edits missing `---` separator or containing empty `old_string`.
  - `list_dir`: Native Python `os.walk` traversal (no shell pipes, no broken pipe errors). Filtered against `.git`, `node_modules`, `__pycache__`, `.venv`.
  - `grep`: Pure Python recursive regex search across all platforms (completely injection-proof; handles quotes, apostrophes, and spaces without shell involvement).
  - `skill`: Progressive disclosure loader for modular markdown skill packs.
  - `subagent`: Spawns isolated, independent child Apex instances.

---

## 4. Model Truth & Catalog

### How Model Truth Was Discovered
In earlier versions, the harness accepted model ID strings like `opus-5.5` or `claude-opus-5.5`. While Genspark returned HTTP 200, credit usage statements revealed that requests were secretly billed and executed on **Claude Sonnet 4.5**.

Deep inspection of raw SSE packets revealed that Genspark provides the **true server-served model** inside:
```
message_result -> message -> session_state -> _llm_model
```
By analyzing the hydration payload of `https://www.genspark.ai/agents?type=ai_chat`, the authoritative model ID strings were extracted:

| Web UI Name | True Genspark API ID | Serving Variant / Server Reported | Notes |
|---|---|---|---|
| **Claude Opus 5.5** | `claude-opus-5-5` | `claude-opus-5-5` | **Current Apex Default**. Hyphen ID (`-5-5`), not dot! |
| **Claude Opus 5** | `claude-opus-5` | `claude-opus-5` | Verified honored. |
| **Claude Opus 4.8** | `claude-opus-4-8` | `claude-opus-4-8-extended-cache` | Verified honored as extended cache variant. |
| **Claude Opus 4.7** | `claude-opus-4-7` | `claude-opus-4-7-extended-cache` | Verified honored as extended cache variant. |
| **Claude Sonnet 5** | `claude-sonnet-5` | `claude-sonnet-5` | Fast coding flagship. |
| **Claude Sonnet 4.6** | `claude-sonnet-4-6` | `claude-sonnet-4-6` | Reliable workhorse. |
| **Claude Haiku 4.5** | `claude-4-5-haiku` | `claude-4-5-haiku` | Fast, lightweight 1x tier. |
| **GPT-6 Sol** | `gpt-6-sol` | `gpt-6-sol` | Brand new flagship line (images + files supported). |
| **GPT-6 Luna** | `gpt-6-luna` | `gpt-6-luna` | Brand new fast tier (0.2x cost). |
| **GPT-5.6 Sol** | `gpt-5.6-sol` | `gpt-5.6-sol` | Flagship coding model. |
| **GPT-5.5 Pro** | `gpt-5.5-pro` | `gpt-5.5-pro-2026-04-23` | Deep reasoning 30x tier. |
| **GPT-5.4 Pro** | `gpt-5.4-pro` | `gpt-5.4-pro` | Deep reasoning 30x tier. |
| **GPT-5.5** | `gpt-5.5` | `gpt-5.5-2026-04-23` | Coding 5x tier. |
| **Gemini 3.8 Flash** | `gemini-3.8-flash` | `gemini-3.8-flash` | Ultra-fast generalist. |
| **Gemini 3.1 Pro** | `gemini-3.1-pro-preview` | `gemini-3.1-pro-preview` | Multimodal coding model. |

### The Silent Substitution Guard (`_model_matches`)
The engine contains an active guard:
```python
def _model_matches(requested: str, served: Optional[str]) -> bool:
    if not served:
        return True
    return served == requested or served.startswith(requested + "-")
```
If Genspark ever accepts an ID but secretly substitutes a different model family, Apex prints a loud red warning indicating both the requested and served model.

---

## 5. Mixture-of-Agents (MoA) Mechanics

### How MoA Works in Genspark
Genspark's Mixture-of-Agents runs multiple LLMs in parallel on the server, aggregates their independent answers, and synthesizes a single consensus output.

### The MoA Payload Protocol
Through reverse-engineering of `ask_proxy` callers in Genspark's JavaScript bundles, the exact required payload structure was identified:
```python
payload = {
    "type": "ai_chat",
    "use_moa_proxy": True,
    "moa_models": ["gpt-6-sol", "gpt-5.6-sol", "claude-opus-4-8"],
    "models": ["gpt-6-sol", "gpt-5.6-sol", "claude-opus-4-8"], # MUST BE PRESENT!
    "ai_chat_model": "gpt-6-sol",                               # MUST BE LEAD MODEL!
    ...
}
```
**Critical Discovery**: If `ai_chat_model` is left as the default (e.g. `claude-opus-5-5`), Genspark **ignores** MoA and executes as a plain single-model call! Setting `ai_chat_model` to the ensemble's first member and mirroring the list in `models` forces the server to execute the real multi-model pipeline.

### MoA Presets Available in Apex
1. **`hybrid-moa`** (`/model hybrid-moa`):
   - **Ensemble**: `gpt-6-sol` + `gpt-5.6-sol` + `claude-opus-4-8`
   - **Burn Rate**: ~13x credits.
   - **Purpose**: Cross-vendor intelligence. Combines OpenAI's two newest Sol flagships with Anthropic Opus reasoning. The best quality-to-cost ratio for heavy architecture work.
2. **`gpt-moa`** (`/model gpt-moa`):
   - **Ensemble**: `gpt-5.5-pro` + `gpt-5.4-pro` + `gpt-5.6-sol` + `gpt-6-sol`
   - **Burn Rate**: ~68x credits (30+30+4+4 — contains two 30x Pro models; the old `~4x` banner was wrong).
   - **Purpose**: Maximum raw reasoning power for the hardest mathematical, algorithmic, or security logic.
3. **`genspark-moa`** (`/model genspark-moa`):
   - **Ensemble**: `gpt-5.1-low` + `claude-sonnet-4-6` + `gemini-3.1-pro-preview`
   - **Burn Rate**: ~6x credits (1+3+2; `gpt-5.1-low` catalogued at 1x — unverified upstream tier).
   - **Purpose**: General consensus coding.
4. **Custom Ensembles**:
   - `/moa <model1> <model2> ...` (e.g. `/moa gpt-6-sol claude-sonnet-5 gemini-3.8-flash`).
   - `/moa off` disables MoA and restores the previous single model.

---

## 6. Subagent Architecture

### Purpose
Allows the primary model to delegate complex, research-heavy, or context-polluting sub-tasks to an independent child agent without bloating the main conversation transcript.

### The Subagent Contract
```xml
<tool name="subagent" prompt="Explore /tmp/target and count lines of code" model="claude-4-5-haiku" max_steps="8">
</tool>
```
- **Complete Isolation**:
  - The subagent receives its own fresh `GensparkClient` (inheriting pool cookies).
  - Its own dedicated `PersistentShell` (changes in `cd` or environment do not affect the parent).
  - Its own dedicated `FileSnapshot` undo stack.
  - Its own fresh `ContextManager`.
- **Parent-Child Boundary**:
  - The subagent **cannot** see the parent's conversation history. The prompt must be completely self-contained.
  - **Depth-1 Guard**: Subagents have `allow_subagent=False`. A subagent cannot spawn further subagents.
  - Only the subagent's **final text report** is returned to the parent as the tool output.
- **UI Delimiters**:
  ```
  ╔═ 🤖 SUBAGENT ═ claude-4-5-haiku · max 8 steps
  ║ task: Explore /tmp/target and count lines of code...
  ⚡ Step 1 ...
  ╚═ 🤖 SUBAGENT done — 184 chars returned to the parent
  ```

---

## 7. Session Lifecycle & Persistence

### Lossless Resumption Across Process Restarts
Historically, exiting or crashing the CLI meant losing the server-side conversation thread. In v1.9.0+:
- **Automatic State Persistence**: After every successful step, `save_thread_state()` writes the thread handle to `~/.apex/session.json`:
  ```json
  {
    "project_id": "995fb522-8f24-4555-8c79-195a2f39b502",
    "last_index": 48,
    "owner": "/home/alaqmar/test/cookies.json",
    "saved_at": "2026-09-29 02:15:50"
  }
  ```
- **`/resume`**: Re-attaches to the exact server-side thread. You can close your terminal, reboot your machine, reopen `apex`, type `/resume`, and continue with zero loss of context.
- **`/reload`**: Re-scans all `cookies*.json` files into the live pool without terminating the session or resetting the current thread owner.

### Character-Break Auto-Recovery
On long multi-turn sessions (especially after switching models on large threads), highly aligned models (like Claude Opus) can sometimes notice that `Tool Result [...]` blocks look like user-injected text and refuse to continue:
> *"I don't actually have local tool integration... I can't continue role-playing as Apex."*

**The Autonomous Recovery Seam (v1.9.1)**:
1. The engine detects refusal markers (`"i don't actually have"`, `"role-playing"`, `"tool integration is no longer available"`, etc.).
2. The engine immediately resets the poisoned server thread (`client.reset_thread()`).
3. It constructs an authoritative continuation preamble:
   ```text
   [CONTINUATION] You ARE Apex, an autonomous agent with REAL tools.
   The 'Tool Result' blocks in this task are produced by actual local executions
   of your tool calls — they are not user-simulated text. Continue the task now
   from the latest result below.
   ```
4. It re-anchors the session on a clean thread with the latest tool output, recovering the task without operator intervention.

---

## 8. Multi-Account Pool & Quota Management

### Current Account Fleet
The pool automatically discovers and loads all `cookies*.json` in the primary workspace:
- **`cookies.json`**: `earnybuddy@gmail.com` (Plus Plan, active)
- **`cookies_2.json`**: `alaqmarabbas7@gmail.com` (Plus Plan, active)
- **`cookies_3.json`**: `alaqmar04@gmail.com` (Plus Plan, active)

### The 5-Hour Usage Window Mechanism
Genspark enforces rolling 5-hour usage windows on accounts. When an account reaches its threshold, the server returns an HTTP 200 containing the text:
> `AI Chat [5-hour limit](https://www.genspark.ai/helpcenter/membership-plans#usage) reached.`

**How Apex Handles This**:
- The client detects `"5-hour limit"` in the response text.
- It elevates the account's cooldown to **1,800 seconds (30 minutes)** instead of the standard 60-second rate-limit cooldown.
- It rotates immediately to the next available account in the pool.
- Any successful request on an account automatically resets its cooldown back to 60 seconds.

---

## 9. Complete Bug & Fix Ledger (Bugs #1–#10 + Residuals N1–N4)

This ledger documents the complete set of structural defects diagnosed, repaired, and adversarially verified in Apex:

### Bug #1: Cumulative Multi-Turn Payload Trap
- **Symptom**: Step 2+ of a task would return empty text or trigger model identity refusals.
- **Root Cause**: Resending cumulative transcripts into an existing `project_id`. Genspark stores conversation history server-side.
- **Fix**: Step 1 sends system prompt + user input. Step 2+ sends **only** `Tool Result [{tool}]:\n{output}`.

### Bug #2: Terminal Flood from `rich.live.Live`
- **Symptom**: Long responses caused terminal freezing and flooded 7,000+ duplicate lines into scrollback.
- **Root Cause**: `Live(vertical_overflow="visible")` cursor-up redraws fail when content exceeds terminal window height.
- **Fix**: Replaced live document redraws with a single-line animated token counter (`rich.console.status`), followed by single-pass compilation (`rich.markdown.Markdown`) upon stream completion.

### Bug #3: Indented Edits & Missing Separator Deletion
- **Symptom**: Code written with indentation doubled its whitespace; edits missing `---` silently deleted matched code.
- **Root Cause**: Tag bodies preserved outer indentation; regex split failed on indented separators; fallback replaced `old_string` with `""`.
- **Fix**: `textwrap.dedent` applied to tool bodies; separator regex changed to `\n[ \t]*-{3,}[ \t]*\n`; missing separator returns `edit_error` and refuses to touch disk.

### Bug #4: Shell Timeout Desynchronization
- **Symptom**: After a single bash command timed out, all subsequent commands returned the output of the *previous* command.
- **Root Cause**: The timed-out command continued running in the background, consuming stdin and delaying sentinel output.
- **Fix**: On timeout, PTY writes `\x03` (Ctrl+C) to terminate the foreground process and re-sends the sentinel line. If unkillable, the shell process cleanly restarts.

### Bug #5: Parser Nesting & Tag Swallowing
- **Symptom**: Writing documentation or code containing `<tool` mentions truncated files and dumped the second half into chat.
- **Root Cause**: Non-greedy regex `.*?` matched the first inner `</tool>` tag.
- **Fix**: Depth-aware parser tracks nesting depth for valid `<tool name="...">` tags. Code blocks and inline backticks are masked prior to parsing. Minimal-combination backtracking resolves unclosed inner examples.

### Bug #6: Shell Injection via `grep`
- **Symptom**: Search patterns containing apostrophes hung the shell; crafted patterns could execute shell commands.
- **Root Cause**: Grep was implemented by interpolating arguments into a bash command string.
- **Fix**: Replaced shell grep with a pure Python recursive regex search across all operating systems.

### Bug #7: Execution of Truncated Streams
- **Symptom**: If an upstream connection dropped mid-tag, the harness wrote half-finished files.
- **Root Cause**: Stream completion was not gated on the official `FINISHED` status event.
- **Fix**: `GensparkClient` tracks `finished=True` only when `project_field status=FINISHED` is received. The engine verifies tag balance and retries severed streams.

### Bug #8: History Expansion & Crash Vectors
- **Symptom**: Commands containing `!` failed with wrong exit codes; non-numeric attributes (`offset="abc"`) crashed the process; unknown tool names ended the session.
- **Root Cause**: Bash interactive history expansion (`set -H`); unhandled `ValueError` in int coercion; unknown tools treated as non-tool final turns.
- **Fix**: Added `set +H` to bash initialization; added `_safe_int()` helper; unknown tools return self-correcting error messages listing available tools so the ReAct loop continues.

### Bug #9: Correctness Seams (CWD, CRLF, Atomic Writes, Thread Pinning)
- **Symptom**: Relative paths ignored bash `cd`; CRLF files were converted to LF; interrupted writes corrupted files; thread failover caused empty response loops.
- **Root Cause**: Python `Path` resolved against harness process CWD; `read_text()` normalized newlines; direct file opening without temp files; threads rotated across incompatible accounts.
- **Fix**:
  - Shell sentinel reports `$PWD` via `@CWD@`; all tool paths resolve against shell CWD.
  - `_read_preserved()` detects CRLF and preserves line endings upon write.
  - `_atomic_write()` writes to sibling `.tmp` file and atomically commits via `os.replace`.
  - `project_owner` pins threads to the creating account; account rotation raises `ThreadResetByFailover` to trigger a clean full-context re-anchor.

### Bug #10: Placeholder Nudge Induced Junk Loops (v1.9.9)
- **Symptom**: On a real Godot feature task the model finished the work and returned a summary with no tool call; the harness re-prompted demanding `pwd && ls`, the model obeyed, and ~10 of 30 steps were burned re-listing an unchanged directory until the step limit. A second, subtler form: the demanded body used an unbounded `[^\n]{0,60}` tail, so `run pytest -q and report` became `pytest -q and report` — an invalid command the model would dutifully attempt.
- **Root Cause**: The v1.9.6 once-per-step nudge assumed a no-tool reply meant laziness, and its body was a hardcoded placeholder. In reality, a no-tool reply *after* real tool work is a completion, and an invented command is worse than no command.
- **Fix**:
  - `_nudge_body_for()` derives the command from the task text: explicit path/shell invocation first (`./validate.sh --gpu`), else known tool + at most ONE known subcommand + flags — **never trailing prose**. `pwd && ls` is used only when the task names no command at all.
  - `_nudge_allowed()` (extracted to be testable) refuses on three independent grounds: no candidate tool, placeholder body after real tool work (`_tools_executed > 0`), or budget spent (`MAX_NUDGES_PER_TASK = 2`, `_nudges_used`, reset per task in `_run_loop`).
  - Greeting/refusal/upstream guards stay at the call site — they describe the *reply*, `_nudge_allowed` describes the *nudge*.
  - 14 new checks in the adversarial suite (90 → 104); unit 26/26, Windows shell 18/18.

### Residuals N1–N4:
- **N1**: Routed `edit_error` directly through `_exec`; blocked empty `old_string` from faking success on empty files.
- **N2**: Upgraded backtracking to test multi-trap combinations (up to 4 unclosed tags).
- **N3**: Malformed tags with unresolvable closes return explicit `parse_error` instead of salvaging message tails into files.
- **N4**: Re-sending sentinel after Ctrl+C preserves shell CWD and environment across normal command timeouts.

---

## 10. Cross-Platform Runtime & Global Setup

Apex runs natively on **Linux**, **macOS**, and **Windows 10/11** (as well as WSL2).

### Running Globally from Any Directory
Apex is symlinked to `~/.local/bin/apex` (which is on the user's `$PATH`):
```bash
# Launch interactive REPL from ANY project folder:
apex

# Run a single non-interactive task:
apex -q "Run pytest and report any failures"

# Select model or MoA preset:
apex --model hybrid-moa
apex --model gpt-moa
```

### Cookie Resolution Order
When running globally outside `/home/alaqmar/test`:
1. `./cookies*.json` in the current working directory (the whole fleet: `cookies.json`, `cookies_2.json`, ...).
2. Falls back automatically to the whole fleet next to `apex_harness.py` (`/home/alaqmar/test/cookies*.json` — v1.9.3 fix: the old fallback loaded only `cookies.json`, stranding the pool on 1 account).
3. `GENSPARK_COOKIES_JSON` env var (single jar or list of jars).

### Windows Native Support (`apex.cmd`)
- On Windows, `apex_harness.py` automatically initializes `_WindowsShell` (`cmd.exe /Q /K /D`) instead of PTY bash.
- PTY and termios imports are safely guarded under `if os.name == "posix":`.
- System prompt dynamically instructs the model to use Windows command syntax (`dir`, `type`, `del`, `where`).

---

## 11. Native File-Upload API Recon & Roadmap

### Reverse-Engineered Upload Flow
Audit of Genspark's live JavaScript bundles revealed the exact 3-step file upload architecture used by the web UI:

1. **Step 1: Obtain Presigned Upload URL**
   - **Endpoint**: `POST https://www.genspark.ai/api/agent-files/upload-url`
   - **Payload**: `{"agent_id": "<uuid>", "filename": "report.pdf"}`
   - **Response**: `{"status": "success", "data": {"upload_url": "https://...blob.core.windows.net/...", "token": "<token>"}}`
2. **Step 2: Binary Upload**
   - **Method**: `PUT <upload_url>`
   - **Headers**: `x-ms-blob-type: BlockBlob`, `Content-Type: <mime_type>`
   - **Body**: Raw binary payload.
3. **Step 3: Confirm Upload**
   - **Endpoint**: `POST https://www.genspark.ai/api/agent-files/confirm-upload`
   - **Format**: `multipart/form-data` (`agent_id`, `filename`, `token`, `mime_type`)
   - **Response**: `{"status": "success", "file": {"id": "<file_id>", "filename": "...", ...}}`
4. **Step 4: Attach to Chat**
   - In `ask_proxy`, files are attached under `attached_files` in the run configuration or `files` array inside message objects.

### Implementation Status
- **Current State**: Mapped and documented. The harness currently embeds file text into prompts.
- **Roadmap**: Implementing this client flow in `GensparkClient` will allow uploading large PDFs, spreadsheets, and binaries for server-side indexing, as well as enabling native multimodal vision support.

---

## 12. Operator Quick Reference

### In-REPL Commands
- `/model [name]` — View model catalog or switch active model / MoA preset.
- `/moa <id1> <id2> ...` — Configure a custom multi-model ensemble on the fly.
- `/moa off` — Disable MoA and return to single-model execution.
- `/skills` — List all installed skill packs and their discovery sources.
- `/skill <name>` — Queue a specific skill pack to inject into the next step.
- `/accounts` — Display real-time account pool health, cooldowns, and request counts.
- `/reload` — Re-scan cookie files on disk without losing conversation state.
- `/resume` — Re-attach to the last saved thread handle after a restart.
- `/undo` — Revert the last file modification made by the agent.
- `/reset` — Clear conversation context and start a clean thread handle.
- `/clear` — Clear terminal screen (`cls` on Windows).
- `/history` — Check token/character budget usage.
- `/exit` (or `/q`) — Exit cleanly.

### Testing & Verification Commands
```bash
# Run unit test suite (26 tests; suites are versioned in the repo at ~/test/tests/):
python3 ~/test/tests/apex_unit_tests.py

# Run Windows shell machinery test suite (18 tests):
python3 ~/test/tests/apex_win_tests.py

# Run adversarial bug verification suite (104 tests):
python3 ~/test/tests/apex_review_tests.py

# Run live end-to-end smoke test:
apex -q "Reply with one sentence confirming your model and tools."
```

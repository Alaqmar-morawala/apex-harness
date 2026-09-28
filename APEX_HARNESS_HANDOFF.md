# APEX HARNESS — COMPREHENSIVE AGENT HANDOFF DOCUMENT
**Date:** 2026-09-28  
**Project Location:** `/home/alaqmar/test`  
**Primary Executables:** `/home/alaqmar/test/apex` (Bash wrapper) & `/home/alaqmar/test/apex_harness.py` (Core Python runtime)  
**Primary Target Workspaces:** `/home/alaqmar/test` and `/home/alaqmar/Desktop/Auto Bug Bounty`  

---

## 1. Executive Summary & Purpose

### The Backstory: Why This Exists
The user previously attempted to use Genspark AI Chat models through Claude Code CLI using a custom translation proxy (`genspark_provider.py`, ~2,400 LOC). That project was declared a **failure** because adapting Genspark's text/SSE API into Claude Code's strict Anthropic Messages format caused cascading structural failures:
- Anthropic schema validation errors on tool calls
- Severe token budget blowouts from prompt re-assembly
- Subagent stall loops and "acknowledged" dead turns
- Fragile JSON parsing and truncated tool block salvaging

### The Solution: Apex Harness
Instead of forcing Genspark through an external intermediary harness, **Apex Harness** is a dedicated, native autonomous coding agent runtime designed specifically for Genspark's reverse-engineered API. It directly manages the ReAct agent loop, connects straight to the upstream SSE endpoint, and runs tools locally with real-time execution authority.

---

## 2. Complete File System & Workspace Inventory

```
/home/alaqmar/test/
├── apex                                # Executable wrapper launcher (chmod +x)
├── apex_harness.py                     # The complete single-file Apex harness (~1,280 lines)
├── APEX_HARNESS.md                     # End-user documentation and command reference
├── APEX_HARNESS_HANDOFF.md             # THIS FILE: Comprehensive engineering handoff
├── API.md                              # Reverse-engineered Genspark API reference & protocol spec
├── cookies.json                        # ACTIVE Genspark credentials (session_id, c1, c2, etc.)
├── cookies_2.json.bak                  # Backup of older expired cookie set
├── cookies_3.json.bak                  # Backup of older expired cookie set
├── GEMINI.md                           # User AI persona, system directives & communication style
├── genspark_provider.py                # Legacy dual OpenAI/Anthropic provider (archival/reference)
├── genspark_research.py                # Standalone headless research script (archival/reference)
├── model_mapping.json                  # Model catalog mapping (Genspark internal names to IDs)
├── queries.txt                         # Sample queries used for benchmarking
├── research_out.jsonl                  # Output logs from research tests
├── sniffer.mjs                         # Playwright script used to intercept Genspark web requests
├── start-provider.sh                   # Startup script for legacy provider
├── .env.example                        # Environment variable template
└── .zcode/plans/                       # Historical planning documents
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
                             │  - Full Markdown Compiler (Rich)  │
                             └──────┬─────────────────────┬──────┘
                                    │                     │
                     Step 1: System │                     │ Step 2+: Tool Results
                     + User Input   │                     │ (Only new deltas!)
                                    ▼                     ▼
                       ┌────────────────────────┐  ┌─────────────────────────┐
                       │    GensparkClient      │  │    Execution Engine     │
                       │ - POST ask_proxy (SSE) │  │ - Persistent PTY bash   │
                       │ - AccountPool (429 cd) │  │ - termios.ECHO disabled │
                       │ - Auto 401/403 disable │  │ - Python os.walk list   │
                       │ - Thread recovery      │  │ - FileSnapshot (/undo)  │
                       └────────────────────────┘  └─────────────────────────┘
```

### § 3.1. GensparkClient & Multi-Account Pool
- **Endpoint**: `POST https://www.genspark.ai/api/agent/ask_proxy`
- **Authentication**: Cookie jar loaded from `cookies.json` or `GENSPARK_COOKIES_JSON`. The critical cookies are `session_id`, `c1`, and `c2`.
- **Required Headers** (bypasses Cloudflare without extra tokens):
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
- **Payload Schema**:
  ```json
  {
      "ai_chat_model": "claude-opus-5-5",
      "ai_chat_enable_search": false,
      "ai_chat_disable_personalization": false,
      "use_moa_proxy": false,
      "moa_models": [],
      "writingContent": null,
      "sas_ask_origin": "typed",
      "type": "ai_chat",
      "project_id": "<uuid-or-null>",
      "messages": [{"role":"user","id":"<uuid>","content":"<query>","pending":true,"sendStatus":"sending","_deepDiveStateNegContent":"<query>"}],
      "user_s_input": "<query>",
      "client_message_id": "<uuid>",
      "g_recaptcha_token": "",
      "is_private": true,
      "push_token": "",
      "session_state": {"steps":[],"messages":[{"role":"user","id":"<uuid>","content":"<query>","pending":true,"sendStatus":"sending","_deepDiveStateNegContent":"<query>"}]},
      "last_seen_event_index": -1,
      "chat_session_id": null
  }
  ```
- **AccountPool Logic**:
  - Automatically loads and deduplicates cookie jars matching `cookies*.json`.
  - Rotates active accounts using thread-safe round-robin.
  - On **HTTP 429**: Marks the account with a 60-second cooldown timestamp and fails over immediately to the next available account.
  - On **HTTP 401 / 403**: Marks `account.auth_error = True`, permanently removing it from the active rotation, logs a warning, and fails over.

### § 3.2. Multi-Turn Threading Protocol (CRITICAL)
- **Step 1**: The harness passes `project_id = None` and `last_seen_event_index = -1`. The query contains the `_system_prompt()` concatenated with `User: {user_input}`. Genspark creates a project thread and returns `project_id` and `last_seen_event_index`.
- **Step 2 and Subsequent Tool Turns**: The harness passes the existing `project_id` and `last_seen_event_index`. The query contains **ONLY** the new tool output:
  ```text
  Tool Result [{tool_name}]:
  {output}
  ```
  **DO NOT RESEND CUMULATIVE TRANSCRIPTS TO AN EXISTING `project_id`!** (See Pitfall #1 below).
- **Session Recovery**: If Genspark drops a stream or returns an empty text response, the harness resets the thread (`client.reset_thread()`), falls back to the local `ContextManager`, and re-anchors the session with the compacted context.

### § 3.3. Persistent PTY Shell
- Built using `pty.openpty()` + `os.fork()` + `termios.tcsetattr`.
- **Echo Disabled**: `attrs[3] = attrs[3] & ~termios.ECHO` prevents slave terminal echo from polluting stdout with commands, carriage returns, or prompt strings.
- **Sentinel Exit Code Tracking**: Commands are executed with a unique per-session sentinel:
  ```bash
  {command}
  __apex_ec=$?
  echo "__APEX_{uuid}__:$__apex_ec"
  ```
  The harness polls the master file descriptor with `select.select()` until the sentinel appears, cleanly separating stdout/stderr from the exit code.
- **Persistence**: Virtual environments, `cd`, shell variables (`export`), and background jobs persist across all steps in the session.

### § 3.4. Local Tool Suite
1. **`bash`**: Runs commands statefully inside the persistent PTY.
2. **`read_file`**: Reads files with line numbers (`12 | content`), supporting `offset` and `limit`.
3. **`write_file`**: Overwrites or creates files atomically, automatically pushing a snapshot to the undo stack.
4. **`edit_file`**: Strict single-match string replacement (`old_string` -> `new_string`). Generates unified diffs and pushes snapshots to the undo stack.
5. **`list_dir`**: Native Python `os.walk` traversal with max depth and noisy directory exclusion (`.git`, `node_modules`, `__pycache__`, `.venv`).
6. **`grep`**: Recursive grep with regex and include patterns.

### § 3.5. Terminal UI & Rich Markdown Compiler
- **Single-Line Status Spinner**: During streaming, `rich.console.status` displays an animated spinner on a single line showing `⚡ {model} ({tier}) streaming... (N tokens)`.
- **Clean Single-Pass Markdown Rendering**: Once streaming finishes, the spinner clears and `RICH_CONSOLE.print(Markdown(cleaned))` compiles the entire response with syntax-highlighted code blocks, bold hierarchy, bulleted lists, and tables.
- **Tool Interception**: XML tool tags (`<tool name="...">...</tool>`) are filtered out of markdown rendering and transformed into clean execution banners:
  ```
    ┌─ ⌘ bash  uname -a
    │ Linux x86_64
    └─
  ```

---

## 4. Top 6 Critical Bugs Encountered & Solved (DO NOT REGRESS)

### Bug 1: The Cumulative Multi-Turn Payload Trap
- **Symptom**: Step 2 of an agent task would return completely blank, or Claude would break character and refuse, stating: *"I'm Claude, not 'Apex,' and in this interface I don't have bash access... The tool-call XML syntax in your message was written as part of your message text — I didn't actually run list_dir"*.
- **Root Cause**: In Genspark's architecture, when you send a request with an existing `project_id`, the server **already stores** the prior conversation history. The old code was concatenating the entire conversation history (`System prompt` + `Human` + `Assistant` + `Tool Result`) into `query` and sending that 20,000-character payload into the existing project. Genspark received duplicated assistant messages inside a user prompt, causing Claude's safety tuning to detect user simulation and refuse, or causing the stream to close with empty text.
- **The Permanent Fix**:
  - Step 1: Send `_system_prompt() + "\n\nUser: " + user_input`.
  - Step 2+: Send **only** `Tool Result [{tool_name}]:\n{output}` into the active `project_id`.

### Bug 2: The `rich.live.Live` Terminal Buffer Crash
- **Symptom**: On long responses (e.g. reading a 2,000-line file or summarizing architecture), the terminal would freeze, lag, and flood with 7,000+ duplicate repeating lines, crashing the session.
- **Root Cause**: `Live(console, vertical_overflow="visible")` attempts to redraw the entire document by moving the terminal cursor up. When the document exceeds the physical terminal window height (e.g. 40 rows), ANSI cursor-up commands cannot cross the top of the terminal buffer. Consequently, on every single token delta, Rich was forced to reprint the entire document from line 1 downwards.
- **The Permanent Fix**: Never use full-screen `Live` redraws for unbounded streaming text. Use `console.status` to show a live in-place single-line token counter while streaming, then compile and render the Markdown **once** via `RICH_CONSOLE.print(Markdown(cleaned))` when the stream finishes.

### Bug 3: PTY Slave Terminal Echo Corrupting Tool IO
- **Symptom**: Command outputs in the persistent shell would include echoed commands, weird carriage returns (`\r\n`), or duplicate command lines.
- **Root Cause**: Unix PTYs default to having `ECHO` enabled. Anything written to the master file descriptor was mirrored back as received output.
- **The Permanent Fix**: Explicitly disable terminal echo on the slave PTY before starting bash:
  ```python
  attrs = termios.tcgetattr(slave)
  attrs[3] = attrs[3] & ~termios.ECHO
  termios.tcsetattr(slave, termios.TCSANOW, attrs)
  ```

### Bug 4: `find: 'standard output': Broken pipe` in `list_dir`
- **Symptom**: `list_dir` would fail or output ugly stderr messages: `find: ‘standard output’: Broken pipe\nfind: write error`.
- **Root Cause**: Running `find ... | head -300` in bash causes `head` to close its input pipe after 300 lines. The still-running `find` process receives a `SIGPIPE` and logs write errors to stderr.
- **The Permanent Fix**: Replaced the shell command with native Python `os.walk`, providing clean relative paths, sorted folder hierarchies, and zero pipe errors.

### Bug 5: Premature Tag Termination in `write_file` (Inner `</tool>` Truncation)
- **Symptom**: Files containing code examples or documentation mentioning tools were cut in half on disk, and the remaining 10,000+ characters spilled directly into the terminal chat as unparsed text ("during writing files many things were filling out").
- **Root Cause**: Naive non-greedy regex `r'<tool\s+name=["\'](\w+)["\']([^>]*)>(.*?)</tool>'` terminated at the FIRST `</tool>` found inside the file body (such as an example `<tool name="bash">ls</tool>`). The parser cut the file in half, wrote the truncated fragment to disk, and dumped the second half into the chat viewport.
- **The Permanent Fix**: Implemented depth-aware tag matching in `ToolParser`. When scanning `write_file` or `edit_file`, inner `<tool>` tags increment depth, and only the matching outer `</tool>` closes the call. Also automatically salvages unclosed tool tags at EOF.

### Bug 6: Spurious Tool Execution Loops from Markdown Code Fences
- **Symptom**: When the model summarized a completed task and cited an example (e.g. `Here is the example: ```xml <tool name="bash">echo test</tool> ``` `), the harness extracted `echo test` as a live command and ran it in an infinite multi-step loop.
- **Root Cause**: Tool parser scanned the entire raw message without ignoring markdown code blocks (` ``` `) or inline backticks (` ` `).
- **The Permanent Fix**: Identified all code fence and backtick spans and masked them out before extracting tool tags. Any `<tool>` tag inside backticks or code blocks is treated strictly as documentation and never executed.

---

## 4.1 Production Hardening (v1.1.0) — Applied After Subagent E2E Test Suite

An independent QA subagent ran an 11-scenario live-API acceptance suite (`/tmp/apex_e2e/`): **11/11 PASS**, zero crashes, zero floods, zero refusals, zero broken pipes. The following hardening was applied before sign-off:

1. **SIGINT redesign** — Removed the global custom `signal.signal(SIGINT, ...)` handler that swallowed Ctrl+C (it made the engine's `except KeyboardInterrupt` dead code and let runaway streams keep burning tokens). Now: Ctrl+C during a task aborts only the task (`AgentEngine.run` wraps the whole loop) and the REPL session survives; Ctrl+C at the prompt clears the line without exiting; Ctrl+D exits.
2. **PTY death auto-restart** — `PersistentShell.run()` now retries once on `OSError`/EOF (e.g. a command ran `exit` or bash crashed): restarts the forked bash and re-runs the command. Unit-tested with an explicit `exit` command.
3. **Network failover** — Transient `ConnectionError`/`Timeout` now fail over to the next pool account exactly like 429s (2s backoff), instead of propagating immediately.
4. **Edit diff truncation** — `edit_file` diffs now pass through `_truncate` so a huge replacement can't blow up the model context.
5. **Multi-tool-call guard** — If the model emits several tool calls in one response, only the first executes and the tool result carries an explicit `[note] N additional tool call(s) ... IGNORED` so the model self-corrects to one-call-per-response.
6. **Markdown render cap** — `_render_markdown()` caps single-pass rendering at 20,000 chars with a visible truncation marker (defense-in-depth against terminal floods).
7. **Undo stack cap** — `FileSnapshot` keeps at most 50 snapshots (FIFO).
8. **Truncation honesty (E2E defect D1)** — Stacked truncation (tool layer 80/120 lines + UI layer 30/30) previously reported a misleading omission count. Now the tool layer notes include original totals (`[... 300 of 500 lines omitted ...]`), the UI always surfaces those notes, and the UI reports its own layer honestly (`… 143 display lines collapsed …`).
9. **POSIX trailing newline** — `write_file` appends a final `\n` when missing; line counts in the success message now count actual lines.
10. **UI banner details** — `list_dir` banners show `path (depth N)`; `grep` banners show `pattern in path`. Dead imports (`subprocess`, `field`, `Live`, `signal`) removed.

**Test artifacts**: unit suite `/tmp/apex_unit_tests.py` (26/26 PASS); E2E logs `/tmp/apex_e2e/`.

---

## 4.2 Windows Support & Setup Guide (v1.2.0)

1. **Import safety** — `pty`, `termios`, `fcntl`, `struct`, `select` are now imported inside a `if os.name == "posix":` guard (they don't exist on Windows and previously crashed at import). `readline` is a guarded optional import. The harness now imports cleanly on Windows.
2. **Platform-adaptive shell** — `PersistentShell` is now an alias: `_PosixShell` (unchanged PTY implementation) on POSIX, `_WindowsShell` on Windows. The Windows backend runs a persistent `cmd.exe /Q /K /D` with piped stdio (pipes don't echo, so no ECHO workaround needed), a daemon reader thread feeding a `queue.Queue` (Windows pipes don't support `select`), a `%errorlevel%` sentinel for exit codes, `chcp 65001` UTF-8, timeout desync re-sync, and auto-restart if cmd dies. Constructor accepts `shell_cmd`/`ec_expr` overrides for testability.
3. **Platform-aware model guidance** — `_system_prompt()` now uses `platform` instead of `os.uname()` (another latent Windows crash) and instructs the model to use Windows syntax (`dir`, `type`, `del`, `where`) on cmd.exe.
4. **Native Python grep** — `grep` uses a pure-Python recursive regex search (`_grep_python`, include-glob filtering, 2MB file cap, 80-result cap) on Windows instead of shell `grep`.
5. **UI/UX** — `/clear` runs `cls` on Windows; the banner shows the active shell backend; `apex.cmd` launcher auto-picks `py` or `python`.
6. **Setup guide** — `SETUP.md` covers dependencies, cookie export (with the exact JSON shape), multi-account jars, the platform behavior matrix, optional env vars, a WSL2 alternative, and troubleshooting.

---

## 4.3 Skill System (v1.4.0)

1. **SkillStore** — discovers markdown skill packs with `name`/`description` frontmatter from (in override order) bundled repo `skills/` → `~/.apex/skills/` → `<cwd>/.apex/skills/` → extra dirs. Name lookup is case-insensitive; missing frontmatter falls back to filename stem + first content line.
2. **`skill` tool** — `<tool name="skill" name="X">` returns the body prefixed with `[skill loaded: X — apply these instructions...]`. Unknown names error with the available list. Progressive disclosure: the system prompt carries only the name/description list; bodies enter context on load.
3. **REPL** — `/skills` lists packs with source dir and queued state; `/skill <name>` queues a pack which is injected into the step-1 prompt of the next task (`engine.pending_skills`).
4. **Bundled packs** (in `skills/`, git-whitelisted): `git-workflow`, `debugging`, `code-review`, `security-recon` (scope-gate first, authorized testing only), `python-testing`, `writing-docs`.
5. **Parsing safety** — skill bodies frequently contain tool examples; they are returned as tool results / prompt text (never re-parsed), and any fenced examples the model echoes back are handled by the existing code-fence masking.

## 4.5 External-Review Fixes (v1.7.0 → v1.7.1)

An independent code review found 7 defects; all were fixed and then re-verified by a hostile QA subagent (7/7 FIXED, 2 live E2E tasks PASS, and its 2 residual new-bugs also fixed):

- **#3 Edits**: tool bodies are dedented (uniform tag-relative indentation no longer corrupts files); the `---` separator is recognized when indented; a MISSING separator now refuses the edit (`edit_error` routed through `_exec`) instead of deleting the matched code; empty `old_string` is refused (no fake success on empty files).
- **#4 Timeout desync**: on timeout the harness sends Ctrl+C to the PTY and RE-SENDS the sentinel line — interruptible commands keep the shell's cwd/env state; only truly unkillable commands cost a shell restart. Either way the next command returns ITS OWN output.
- **#5 Parser nesting**: only tags with a valid `<tool name="...">` header affect nesting (bare `<tool…` mentions are content); unclosed nested opens are resolved by minimal-combination backtracking (1 skip, then pairs, capped); a pathological tag that still can't resolve becomes a `parse_error` result instead of salvaging the message tail into a file.
- **#6 grep de-shelled**: `grep` is pure Python on ALL platforms — patterns with quotes/apostrophes just work and crafted patterns (`'; touch x; '`) cannot execute commands.
- **#7 Truncated streams**: `stream()` reports `finished` (True only on the FINISHED event); the engine detects open/close tag imbalance and retries the step instead of executing a half-written file; a second cut-off ends the task.
- **#8 Exit codes/silent crashes**: `set +H` disables history expansion (`!` safe, truthful exit codes); non-numeric attributes are dropped via `_safe_int` (no task crash); unknown tool names become self-correcting error results listing available tools instead of ending the task; the parser itself is wrapped so it can never kill a task.
- **#9 Correctness**: file-tool paths resolve against the SHELL's cwd (sentinel carries `$PWD`/`%CD%`; a `cd` in bash redirects relative writes); CRLF files stay CRLF through edits; writes go through temp-file + `os.replace` (atomic, no `.apex-*.tmp` leftovers); conversation threads are PINNED to the account that owns them — rotation to another account raises `ThreadResetByFailover` and the engine re-sends full context on a fresh thread (this also explains historical "empty response" resets with multiple accounts).

Also added: per-step token usage line (`[tokens: prompt … · completion … · total … | served: …]`) from `session_state._llm_usage`, and cookie-expiry warnings at startup (expired `session_id` disables the account; <7 days warns).

## 4.3.1 MoA Payload Truth + Subagents (v1.7.6 → v1.8.0)

- **MoA billing fix (user-reported)**: selecting gpt-moa still billed opus — the harness sent only `moa_models`+`use_moa_proxy` while leaving `ai_chat_model` at the base model. The web UI's payload builder (extracted from the JS bundle) shows MoA mode ALSO sends the ensemble in a `models` field with `ai_chat_model` set to the ensemble LEAD. `stream()` now does exactly that; selecting any MoA sets the primary/billed model to the lead and `/moa off` restores the previous single model.
- **MoA presets**: `genspark-moa` (3 models) and `gpt-moa` = gpt-5.5-pro + gpt-5.4-pro + gpt-5.6-sol + **gpt-6-sol** (4-model ensemble works; gpt-6-sol/gpt-6-luna discovered in the live page payload and server-verified). Custom ensembles via `/moa id1 id2 ...`, `/moa off`. Substitution guard is skipped in MoA mode (ai_chat_model mismatch is expected there).
- **What "served model" means in MoA**: the stream contains exactly ONE `message_result` per turn — `_llm_model` names only the LEAD/synthesizer (or is absent). Ensemble members run server-side and are invisible to the client; they surface only on the billing/usage page. Verified by raw SSE capture.
- **Subagents (v1.8.0)**: `<tool name="subagent" prompt="..." model="..." max_steps="12">` spawns a fresh, isolated Apex instance — own Genspark thread, own PTY shell, own undo stack, same skills. It cannot see the parent conversation (prompts must be self-contained), cannot spawn further subagents (depth 1), and returns its final report as the tool result. UI: `╔═ 🤖 SUBAGENT` header/footer banners; sub-steps render inline.
- **Soft usage-limit failover**: Genspark returns per-account caps ("AI Chat [5-hour limit]") as normal 200 text. `stream()` detects this, marks the account cooldown, and fails over — instead of relaying the notice as an answer.

## 4.4 Internet-Sourced Skill Library (v1.5.0)

The bundled packs were upgraded from hand-rolled to **adaptations of the most-recommended open agent skills**, researched from the 2026 ecosystem (consensus sources: [obra/superpowers](https://github.com/obra/superpowers) — MIT, the most-praised methodology collection; [VoltAgent/awesome-agent-skills](https://github.com/VoltAgent/awesome-agent-skills) aggregate; Anthropic's official skills).

- **Adapted from superpowers (MIT, attributed in each pack)**: `test-driven-development` (Iron Law + mandatory RED/GREEN verification + rationalization table), `systematic-debugging` (4 phases, "no fixes without root cause", red-flag list — replaces the earlier hand-rolled `debugging.md`), `verification-before-completion` (evidence-before-claims gate + claim→evidence table), plus `writing-plans` and `brainstorming` adapted to Apex's auto-execute mode (plans/designs live in chat, not disk).
- **Apex-specific tailoring in every pack**: verification via fresh `bash` runs with quoted output, surgical `read_file` paging while tracing code, `grep` for finding working reference code, the write_file contract, and the no-unsolicited-files rule.
- **Upgraded in place**: `git-workflow` (branch finishing hygiene), `python-testing` (red-green regression rule, cross-linked to TDD). **Unchanged**: `code-review`, `security-recon`, `writing-docs` (already aligned with the canon's severity-based review format).
- Skill set is now 10 packs; `SkillStore` needed no code changes (pure content update).

---

## 5. Model Catalog Reference

The default model is **`claude-opus-5`** — verified via the server-reported `message_result.session_state._llm_model` field.

> **Model truth (v1.6.1, user-corrected):** the web UI's **"Claude Opus 5.5" maps to API id `claude-opus-5-5` (hyphen, not dot)** — verified: server-reported `_llm_model == claude-opus-5-5` and the model self-identifies as Opus 5.5. Dot-variant ids (`opus-5.5`, `claude-opus-5.5`) are **not real** — HTTP 200 but silently serve `claude-sonnet-4-5-20250929`. `claude-opus-4-8`/`-4-7` honor as `...-extended-cache` serving variants. The current model list is extractable from the agents-page payload: `GET /agents?type=ai_chat` and regex for `claude-opus[a-z0-9._-]*` (this is how `claude-opus-5-5` was found). The harness warns loudly on any silent substitution (`_model_matches()` guard).

| Model ID | Label | Tier | Class | Notes |
|---|---|---|---|---|
| `claude-opus-5-5` | Claude Opus 5.5 | **5x** | Reasoning | **Current Default**. Verified honored — hyphen id, dot id is fake |
| `claude-opus-5` | Claude Opus 5 | 5x | Reasoning | Honored |
| `claude-opus-4-8` | Claude Opus 4.8 | 5x | Reasoning | Honored (serves as `-extended-cache` variant) |
| `claude-opus-4-7` | Claude Opus 4.7 | 5x | Reasoning | Honored (serves as `-extended-cache` variant) |
| `claude-sonnet-5` | Claude Sonnet 5 | 2x | Coding | High speed, strong coding |
| `claude-sonnet-4-6` | Claude Sonnet 4.6 | 3x | Coding | Reliable coding workhorse |
| `claude-4-5-haiku` | Claude Haiku 4.5 | 1x | Fast | Fast, lightweight tasks |
| `gpt-5.6-sol` | GPT-5.6 Sol | 4x | Coding | OpenAI flagship coding model |
| `gpt-5.5-pro` | GPT-5.5 Pro | 30x | Reasoning | Deep reasoning, high credit cost |
| `gemini-3.8-flash` | Gemini 3.8 Flash | 0.75x | Fast | Fast, cheap generalist |
| `genspark-moa` | Mixture of Agents | — | MoA | Combines GPT-5.1 + Sonnet 4.6 + Gemini 3.1 Pro |

---

## 6. How to Run & Common Workflows

### Launching the Interactive REPL
```bash
cd /home/alaqmar/test
./apex
```

### Running Non-Interactive Single Tasks
```bash
./apex -q "Explore /home/alaqmar/Desktop/Auto Bug Bounty and list all active gates"
```

### Selecting a Specific Model
```bash
./apex --model gpt-5.6-sol -q "Refactor this function"
./apex --model claude-4-5-haiku  # Lightweight interactive session
```

### Enabling Web Search
```bash
./apex --search -q "Latest CVEs in Spring Framework September 2026"
```

### In-REPL Slash Commands
- `/model [name]` — Switch model or view catalog
- `/search [on|off]` — Toggle web search
- `/accounts` — View health and request counts of cookie accounts
- `/undo` — Revert the last file change
- `/reset` — Clear conversation and reset upstream Genspark thread
- `/clear` — Clear the terminal viewport
- `/steps [n]` — Update max steps (default: 30)
- `/history` — Check conversation turn count and character usage
- `/help` — Display help menu
- `/exit` (or `/q`) — Exit cleanly

---

## 7. Account Management & Cookie Rotation

- Active cookies are stored in `/home/alaqmar/test/cookies.json`.
- When the user provides fresh cookies:
  1. Save them directly to `/home/alaqmar/test/cookies.json` as a JSON array of cookie objects.
  2. The harness automatically discovers all `cookies*.json` in the directory.
  3. Ensure the cookies include `session_id`, `c1`, and `c2`.

---

## 8. Potential Next Tasks for Continuing Agents

1. **Auto-Cookie Refresh**: Build a lightweight background script using `sniffer.mjs` (Playwright) to automatically refresh cookies before expiration.
2. **Sub-Agent Fan-Out**: Add a `/delegate` command to spawn secondary `AgentEngine` instances for isolated parallel subtasks.
3. **Workspace Linking**: Apex is already verified working seamlessly inside `/home/alaqmar/Desktop/Auto Bug Bounty` (Auto Bug Bounty / Nyxstrike). You can run `./apex` directly against any directory on the workstation.

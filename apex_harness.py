#!/usr/bin/env python3
"""
Apex Harness — Elite autonomous coding agent for Genspark models.

Connects directly to Genspark's streaming API and runs a native ReAct agent
loop on your local machine with full tool support: persistent PTY shell,
atomic file editing with undo, smart context management, multi-account
pooling with 429 failover, and dynamic model switching.

Usage:
    ./apex                              # interactive REPL (Linux/macOS)
    apex.cmd                            # interactive REPL (Windows)
    python apex_harness.py              # works everywhere
    ./apex -q "create a flask app"      # single query
    ./apex --model claude-sonnet-5      # pick model
    ./apex --cookies cookies.json       # explicit cookie file
"""
from __future__ import annotations

import argparse
import atexit
import difflib
import fnmatch
import json
import os
import platform
import queue
import re
import subprocess
import sys
import textwrap
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import requests
from rich.console import Console
from rich.markdown import Markdown
from rich.theme import Theme

try:
    import readline  # POSIX line editing/history; absent on Windows
except ImportError:
    readline = None

_POSIX = os.name == "posix"
if _POSIX:
    import fcntl
    import pty
    import select
    import struct
    import termios

# ═══════════════════════════════════════════════════════════════════════════════
# § 1. CONSTANTS & CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

VERSION = "1.3.0"
GENSPARK_API = "https://www.genspark.ai/api/agent/ask_proxy"
DEFAULT_MODEL = "opus-5.5"
MAX_STEPS_DEFAULT = 30
SHELL_TIMEOUT = 120
OUTPUT_HEAD = 60
OUTPUT_TAIL = 100
MAX_OUTPUT_CHARS = 12_000
READ_WINDOW = 250
CONTEXT_BUDGET = 22_000
HISTORY_FILE = Path.home() / ".apex" / "history"
UNDO_STACK_LIMIT = 50
MAX_RENDER_CHARS = 20_000


class C:
    """ANSI escape helpers."""
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RED     = "\033[31m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    BLUE    = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN    = "\033[36m"
    WHITE   = "\033[37m"

    @staticmethod
    def s(text: str, *codes: str) -> str:
        return "".join(codes) + text + C.RESET


MODEL_CATALOG: Dict[str, Dict[str, str]] = {
    "opus-5.5":                   {"label": "Claude Opus 5.5",         "tier": "5x",   "cls": "reasoning"},
    "claude-opus-5.5":            {"label": "Claude Opus 5.5",         "tier": "5x",   "cls": "reasoning"},
    "claude-opus-5":              {"label": "Claude Opus 5",           "tier": "5x",   "cls": "reasoning"},
    "claude-opus-4-8":            {"label": "Claude Opus 4.8",         "tier": "5x",   "cls": "reasoning"},
    "claude-opus-4-7":            {"label": "Claude Opus 4.7",         "tier": "5x",   "cls": "reasoning"},
    "claude-opus-4-6":            {"label": "Claude Opus 4.6",         "tier": "5x",   "cls": "reasoning"},
    "claude-sonnet-5":            {"label": "Claude Sonnet 5",         "tier": "2x",   "cls": "coding"},
    "claude-sonnet-4-6":          {"label": "Claude Sonnet 4.6",       "tier": "3x",   "cls": "coding"},
    "claude-4-5-haiku":           {"label": "Claude Haiku 4.5",        "tier": "1x",   "cls": "fast"},
    "gpt-5.5-pro":                {"label": "GPT-5.5 Pro",             "tier": "30x",  "cls": "reasoning"},
    "gpt-5.4-pro":                {"label": "GPT-5.4 Pro",             "tier": "30x",  "cls": "reasoning"},
    "gpt-5.2-pro":                {"label": "GPT-5.2 Pro",             "tier": "21x",  "cls": "reasoning"},
    "gpt-5.6-sol":                {"label": "GPT-5.6 Sol",             "tier": "4x",   "cls": "coding"},
    "gpt-5.5":                    {"label": "GPT-5.5",                 "tier": "5x",   "cls": "coding"},
    "gpt-5.4":                    {"label": "GPT-5.4",                 "tier": "3x",   "cls": "coding"},
    "gpt-5.6-terra":              {"label": "GPT-5.6 Terra",           "tier": "2x",   "cls": "coding"},
    "gpt-5.4-mini":               {"label": "GPT-5.4 Mini",            "tier": "1x",   "cls": "fast"},
    "gpt-5.6-luna":               {"label": "GPT-5.6 Luna",            "tier": "0.2x", "cls": "fast"},
    "gpt-5.4-nano":               {"label": "GPT-5.4 Nano",            "tier": "0.2x", "cls": "fast"},
    "gemini-3.1-pro-preview":     {"label": "Gemini 3.1 Pro Preview",  "tier": "2x",   "cls": "coding"},
    "gemini-3.8-flash":           {"label": "Gemini 3.8 Flash",        "tier": "0.75x","cls": "fast"},
    "gemini-3.7-flash":           {"label": "Gemini 3.7 Flash",        "tier": "0.75x","cls": "fast"},
    "gemini-3.6-flash":           {"label": "Gemini 3.6 Flash",        "tier": "0.75x","cls": "fast"},
    "gemini-3.5-flash":           {"label": "Gemini 3.5 Flash",        "tier": "2x",   "cls": "coding"},
    "gemini-3-flash-preview":     {"label": "Gemini 3 Flash Preview",  "tier": "0.5x", "cls": "fast"},
    "gemini-3.1-flash-lite-preview": {"label": "Gemini 3.1 Flash Lite","tier": "0.3x", "cls": "fast"},
    "grok-4.6":                   {"label": "Grok 4.6",                "tier": "2x",   "cls": "coding"},
    "grok-4.5":                   {"label": "Grok 4.5",                "tier": "2x",   "cls": "coding"},
    "muse-spark-1.3":             {"label": "Muse Spark 1.3",          "tier": "1x",   "cls": "coding"},
    "deepseek-v4-pro":            {"label": "DeepSeek V4 Pro",         "tier": "2x",   "cls": "coding"},
    "kimi-k3":                    {"label": "Kimi K3",                 "tier": "3x",   "cls": "coding"},
    "minimax-m3":                 {"label": "Minimax M3",              "tier": "0.3x", "cls": "fast"},
    "glm-5.3":                    {"label": "GLM-5.3",                 "tier": "1x",   "cls": "coding"},
}

MOA_DEFAULT = ["gpt-5.1-low", "claude-sonnet-4-6", "gemini-3.1-pro-preview"]


# ═══════════════════════════════════════════════════════════════════════════════
# § 2. GENSPARK CLIENT — Multi-Account Pool, 429 Failover, SSE Streaming
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class CookieAccount:
    name: str
    session: requests.Session
    tag: str
    last_429: float = 0.0
    cooldown: float = 60.0
    req_count: int = 0
    ok_count: int = 0
    rl_count: int = 0
    auth_error: bool = False

    def available(self) -> bool:
        if self.auth_error:
            return False
        return self.last_429 <= 0 or (time.time() - self.last_429) > self.cooldown

    def remaining_cd(self) -> int:
        if self.available():
            return 0
        return max(0, int(self.cooldown - (time.time() - self.last_429)))

    def mark_429(self):
        self.last_429 = time.time()
        self.rl_count += 1

    def mark_auth_error(self):
        self.auth_error = True

    def mark_ok(self):
        self.ok_count += 1


class AccountPool:
    def __init__(self):
        self.accounts: List[CookieAccount] = []
        self._idx = 0
        self._lock = threading.Lock()

    def add(self, name: str, raw: List[Dict[str, Any]]):
        s = requests.Session()
        for c in raw:
            d = (c.get("domain") or "").lstrip(".")
            if d:
                try:
                    s.cookies.set(c["name"], c["value"], domain=d, path=c.get("path", "/"))
                except Exception:
                    pass
        sid = next((c.get("value", "") for c in raw if c.get("name") == "session_id"), "")
        tag_sid = f"{sid[:8]}..{sid[-6:]}" if len(sid) > 16 else sid
        self.accounts.append(CookieAccount(name=name, session=s, tag=f"{name}[{tag_sid}]"))

    def next_account(self) -> CookieAccount:
        with self._lock:
            if not self.accounts:
                raise RuntimeError("No Genspark accounts loaded")
            avail = [a for a in self.accounts if a.available()]
            if avail:
                acc = avail[self._idx % len(avail)]
                self._idx = (self._idx + 1) % len(avail)
                return acc
            non_dead = [a for a in self.accounts if not a.auth_error]
            if non_dead:
                best = min(non_dead, key=lambda a: a.last_429)
                return best
            raise RuntimeError("All Genspark accounts exhausted or unauthorized")

    def health(self) -> List[Dict[str, Any]]:
        return [
            {"name": a.name, "tag": a.tag, "available": a.available(),
             "auth_error": a.auth_error,
             "cooldown_sec": a.remaining_cd(), "requests": a.req_count,
             "successes": a.ok_count, "rate_limits": a.rl_count}
            for a in self.accounts
        ]


class GensparkClient:
    def __init__(self, cookie_spec: Optional[str] = None):
        self.pool = AccountPool()
        self._load_pool(cookie_spec)
        self.project_id: Optional[str] = None
        self.last_index: int = -1

    def _load_pool(self, spec: Optional[str]):
        # 1. env var
        env_json = os.getenv("GENSPARK_COOKIES_JSON")
        if env_json:
            try:
                raw = json.loads(env_json)
                if isinstance(raw, list) and raw:
                    if isinstance(raw[0], dict):
                        self.pool.add("env", raw)
                    elif isinstance(raw[0], list):
                        for i, jar in enumerate(raw, 1):
                            self.pool.add(f"env_{i}", jar)
            except Exception as e:
                print(C.s(f"  [warn] GENSPARK_COOKIES_JSON: {e}", C.YELLOW))

        # 2. file discovery
        candidates: List[Path] = []
        if spec and "," in spec:
            candidates = [Path(p.strip()) for p in spec.split(",") if p.strip()]
        elif spec and Path(spec).exists():
            candidates = [Path(spec)]

        search_dir = Path(spec or "cookies.json").parent if Path(spec or "cookies.json").parent.exists() else Path(".")
        for f in sorted(search_dir.glob("cookies*.json")):
            if f not in candidates:
                candidates.append(f)

        seen_paths: Set[Path] = set()
        seen_keys: Set[str] = set()
        for p in candidates:
            if not p.exists():
                continue
            rp = p.resolve()
            if rp in seen_paths:
                continue
            seen_paths.add(rp)
            try:
                raw = json.loads(p.read_text())
                if isinstance(raw, list):
                    sid = next((c.get("value", "") for c in raw if c.get("name") == "session_id"), "")
                    c1 = next((c.get("value", "") for c in raw if c.get("name") == "c1"), "")
                    key = f"{sid}:{c1}"
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    self.pool.add(p.name, raw)
            except Exception as e:
                print(C.s(f"  [warn] {p}: {e}", C.YELLOW))

        if not self.pool.accounts:
            raise RuntimeError(
                "No Genspark cookies found. Place cookies.json in the current directory "
                "or set GENSPARK_COOKIES_JSON."
            )

    def _headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Origin": "https://www.genspark.ai",
            "Referer": "https://www.genspark.ai/agents?type=ai_chat",
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
            "X-Timezone": "Asia/Calcutta",
            "Accept": "text/event-stream",
        }

    def stream(
        self,
        query: str,
        model: str,
        enable_search: bool = False,
        moa_models: Optional[List[str]] = None,
        on_delta: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, Any]:
        max_tries = max(1, len(self.pool.accounts))
        last_err: Optional[Exception] = None

        for attempt in range(max_tries):
            acc = self.pool.next_account()
            acc.req_count += 1

            mid = str(uuid.uuid4())
            msg = {
                "role": "user", "id": mid, "content": query,
                "pending": True, "sendStatus": "sending",
                "_deepDiveStateNegContent": query,
            }
            payload = {
                "ai_chat_model": model,
                "ai_chat_enable_search": enable_search,
                "ai_chat_disable_personalization": False,
                "use_moa_proxy": bool(moa_models),
                "moa_models": moa_models or [],
                "writingContent": None,
                "sas_ask_origin": "typed",
                "type": "ai_chat",
                "project_id": self.project_id,
                "messages": [msg],
                "user_s_input": query,
                "client_message_id": mid,
                "g_recaptcha_token": os.getenv("GENSPARK_RECAPTCHA_TOKEN", ""),
                "is_private": True,
                "push_token": "",
                "session_state": {"steps": [], "messages": [msg]},
                "last_seen_event_index": self.last_index,
                "chat_session_id": None,
            }

            try:
                r = acc.session.post(
                    GENSPARK_API, json=payload, headers=self._headers(),
                    stream=True, timeout=180,
                )
                if r.status_code in (401, 403):
                    acc.mark_auth_error()
                    last_err = requests.HTTPError(f"HTTP {r.status_code} Unauthorized", response=r)
                    print(C.s(
                        f"  [pool] {acc.tag} auth error ({r.status_code}) → disabled, failover "
                        f"({attempt+1}/{max_tries})", C.YELLOW
                    ))
                    if attempt + 1 < max_tries:
                        time.sleep(1.0)
                        continue
                    raise last_err
                if r.status_code == 429:
                    acc.mark_429()
                    last_err = requests.HTTPError("429", response=r)
                    print(C.s(
                        f"  [pool] {acc.tag} rate-limited → failover "
                        f"({attempt+1}/{max_tries})", C.YELLOW
                    ))
                    if attempt + 1 < max_tries:
                        time.sleep(1.5)
                        continue
                    raise last_err
                r.raise_for_status()

                text = ""
                for line in r.iter_lines(decode_unicode=True):
                    if not line or not line.startswith("data:"):
                        continue
                    try:
                        j = json.loads(line[5:].strip())
                    except json.JSONDecodeError:
                        continue
                    if "_event_index" in j:
                        try:
                            self.last_index = int(j["_event_index"])
                        except Exception:
                            pass
                    t = j.get("type")
                    if t == "project_start" and j.get("id"):
                        self.project_id = j["id"]
                    elif t == "message_field_delta":
                        d = j.get("delta", "")
                        if d:
                            text += d
                            if on_delta:
                                on_delta(d)
                    elif t == "message_field" and j.get("field_name") == "content":
                        v = j.get("field_value")
                        if isinstance(v, str) and not text:
                            text = v
                    elif t == "message_result":
                        m = j.get("message") or {}
                        if m.get("content"):
                            text = m["content"]
                    elif (t == "project_field"
                          and j.get("field_name") == "status"
                          and j.get("field_value") == "FINISHED"):
                        break

                acc.mark_ok()
                return {
                    "text": text,
                    "project_id": self.project_id,
                    "last_index": self.last_index,
                }

            except requests.HTTPError as e:
                resp = getattr(e, "response", None)
                if resp is not None and resp.status_code in (401, 403):
                    acc.mark_auth_error()
                    last_err = e
                    if attempt + 1 < max_tries:
                        time.sleep(1.0)
                        continue
                elif resp is not None and resp.status_code == 429:
                    acc.mark_429()
                    last_err = e
                    if attempt + 1 < max_tries:
                        time.sleep(1.5)
                        continue
                raise
            except (requests.exceptions.ConnectionError,
                    requests.exceptions.Timeout) as e:
                # Transient network failure — failover to the next account
                last_err = e
                print(C.s(
                    f"  [pool] {acc.tag} network error ({type(e).__name__}) → failover "
                    f"({attempt+1}/{max_tries})", C.YELLOW
                ))
                if attempt + 1 < max_tries:
                    time.sleep(2.0)
                    continue
                raise
            except Exception:
                raise

        if last_err:
            raise last_err
        raise RuntimeError("All accounts exhausted")

    def reset_thread(self):
        self.project_id = None
        self.last_index = -1


# ═══════════════════════════════════════════════════════════════════════════════
# § 3. EXECUTION ENGINE — Persistent PTY Shell, Atomic Editor, File Tools
# ═══════════════════════════════════════════════════════════════════════════════

class _PosixShell:
    """POSIX backend: PTY-backed bash. cd, exports, source, and virtualenvs persist across calls."""

    def __init__(self):
        self._master: Optional[int] = None
        self._child_pid: Optional[int] = None
        self._sentinel = f"__APEX_{uuid.uuid4().hex[:8]}__"
        self._lock = threading.Lock()
        self._start()

    def _start(self):
        master, slave = pty.openpty()
        # disable echo so input commands are not mirrored back onto master
        attrs = termios.tcgetattr(slave)
        attrs[3] = attrs[3] & ~termios.ECHO
        termios.tcsetattr(slave, termios.TCSANOW, attrs)
        # set terminal size
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 50, 200, 0, 0))

        pid = os.fork()
        if pid == 0:
            # child process
            os.close(master)
            os.setsid()
            os.dup2(slave, 0)
            os.dup2(slave, 1)
            os.dup2(slave, 2)
            if slave > 2:
                os.close(slave)
            env = dict(os.environ)
            env["TERM"] = "dumb"
            env["PS1"] = ""
            env["PS2"] = ""
            os.execvpe(
                "/bin/bash",
                ["/bin/bash", "--norc", "--noprofile", "-i"],
                env,
            )
        else:
            os.close(slave)
            self._master = master
            self._child_pid = pid
            time.sleep(0.3)
            self._drain(0.5)

    def _drain(self, timeout: float = 0.3) -> str:
        parts: List[str] = []
        while True:
            rd, _, _ = select.select([self._master], [], [], timeout)
            if not rd:
                break
            try:
                chunk = os.read(self._master, 16384)
                if not chunk:
                    break
                parts.append(chunk.decode("utf-8", errors="replace"))
            except OSError:
                break
        return "".join(parts)

    def run(self, command: str, timeout: int = SHELL_TIMEOUT) -> Tuple[str, int]:
        try:
            return self._run_once(command, timeout)
        except OSError:
            # Shell process died (e.g. a command ran `exit`). Restart and retry once.
            self.close()
            self._start()
            try:
                return self._run_once(command, timeout)
            except OSError:
                return "[shell error: persistent shell could not be restarted]", 1

    def _run_once(self, command: str, timeout: int) -> Tuple[str, int]:
        with self._lock:
            # send command + sentinel
            sentinel_cmd = (
                f"{command}\n"
                f"__apex_ec=$?\n"
                f"echo \"{self._sentinel}:$__apex_ec\"\n"
            )
            os.write(self._master, sentinel_cmd.encode())

            parts: List[str] = []
            t0 = time.time()
            exit_code = -1
            eof = False

            while True:
                elapsed = time.time() - t0
                left = timeout - elapsed
                if left <= 0:
                    parts.append(f"\n[timed out after {timeout}s]")
                    exit_code = 124
                    break

                rd, _, _ = select.select([self._master], [], [], min(left, 0.15))
                if rd:
                    try:
                        chunk = os.read(self._master, 32768)
                        if not chunk:
                            eof = True
                            break
                        parts.append(chunk.decode("utf-8", errors="replace"))
                    except OSError:
                        eof = True
                        break

                combined = "".join(parts)
                marker = f"{self._sentinel}:"
                if marker in combined:
                    idx = combined.rfind(marker)
                    tail = combined[idx + len(marker):].strip()
                    try:
                        exit_code = int(tail.split()[0].split("\n")[0].split("\r")[0])
                    except (ValueError, IndexError):
                        exit_code = 0
                    combined = combined[:idx]
                    parts = [combined]
                    break

            if eof and exit_code == -1:
                # bash died mid-command — surface it so the caller can restart
                raise OSError("shell process terminated unexpectedly")

            raw = "".join(parts)
            # strip ANSI escapes and carriage returns
            clean = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', raw)
            clean = re.sub(r'\x1b\][^\x07]*\x07', '', clean)
            clean = clean.replace('\r\n', '\n').replace('\r', '')

            # clean sentinel line and artifacts
            lines = clean.split("\n")
            out_lines: List[str] = []
            for ln in lines:
                if self._sentinel in ln or ln.startswith("__apex_ec="):
                    continue
                out_lines.append(ln)

            return "\n".join(out_lines).strip(), exit_code

    def close(self):
        if self._master is not None:
            try:
                os.write(self._master, b"exit\n")
                time.sleep(0.1)
                os.close(self._master)
            except Exception:
                pass
        if self._child_pid is not None:
            try:
                os.waitpid(self._child_pid, os.WNOHANG)
            except Exception:
                pass


_WINDOWS_CMD_DEFAULT = ["cmd.exe", "/Q", "/K", "/D"]


class _WindowsShell:
    """Windows backend: persistent cmd.exe with piped stdio and a reader thread.

    Pipes don't echo (no TTY), and a sentinel line captures %errorlevel%.
    State (cd, set, setx-per-process env) persists across run() calls.
    """

    def __init__(self, shell_cmd: Optional[List[str]] = None, ec_expr: str = "%errorlevel%"):
        self._shell_cmd = shell_cmd or _WINDOWS_CMD_DEFAULT
        self._ec_expr = ec_expr
        self._crlf = self._shell_cmd[0].lower().endswith("cmd.exe")
        self._nl = "\r\n" if self._crlf else "\n"
        self._proc = None
        self._sentinel = f"__APEX_{uuid.uuid4().hex[:8]}__"
        self._lock = threading.Lock()
        self._desync = False
        self._queue: "queue.Queue[str]" = queue.Queue()
        self._start()

    def _start(self):
        spawn_kwargs: Dict[str, Any] = {}
        if os.name == "nt":
            spawn_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        self._proc = subprocess.Popen(
            self._shell_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            **spawn_kwargs,
        )
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        if self._shell_cmd[0].lower().endswith("cmd.exe"):
            # UTF-8 codepage, and swallow the banner
            self._proc.stdin.write("chcp 65001 > nul\r\n")
            self._proc.stdin.flush()
        time.sleep(0.3)
        self._drain_startup()

    def _read_loop(self):
        assert self._proc and self._proc.stdout
        for line in self._proc.stdout:
            self._queue.put(line)
        self._queue.put(None)  # EOF marker

    def _drain_startup(self, timeout: float = 0.5):
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                item = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue
            if item is None:
                break

    def run(self, command: str, timeout: int = SHELL_TIMEOUT) -> Tuple[str, int]:
        with self._lock:
            if self._proc is None or self._proc.poll() is not None:
                self._start()
            if self._desync:
                # a previous command timed out; discard output until its sentinel appears
                self._resync()
            assert self._proc and self._proc.stdin
            marker = f"{self._sentinel}:"
            try:
                self._proc.stdin.write(f"{command}{self._nl}")
                self._proc.stdin.write(f"echo {marker}{self._ec_expr}{self._nl}")
                self._proc.stdin.flush()
            except OSError:
                self._start()
                assert self._proc and self._proc.stdin
                self._proc.stdin.write(f"{command}{self._nl}")
                self._proc.stdin.write(f"echo {marker}{self._ec_expr}{self._nl}")
                self._proc.stdin.flush()

            parts: List[str] = []
            t0 = time.time()
            exit_code = -1

            while True:
                left = timeout - (time.time() - t0)
                if left <= 0:
                    parts.append(f"\n[timed out after {timeout}s]")
                    exit_code = 124
                    self._desync = True
                    break
                try:
                    item = self._queue.get(timeout=min(left, 0.15))
                except queue.Empty:
                    continue
                if item is None:
                    # shell process died
                    self._start()
                    return "[shell restarted: previous shell process terminated]", 1
                s = item.rstrip("\r\n")
                if s.startswith(marker):
                    try:
                        exit_code = int(s[len(marker):].strip())
                    except ValueError:
                        exit_code = 0
                    break
                parts.append(s)

            return "\n".join(parts).strip(), exit_code

    def _resync(self, timeout: float = 3.0):
        t0 = time.time()
        marker = f"{self._sentinel}:"
        while time.time() - t0 < timeout:
            try:
                item = self._queue.get(timeout=0.2)
            except queue.Empty:
                self._desync = False
                return
            if item is None:
                self._start()
                self._desync = False
                return
            if item.rstrip("\r\n").startswith(marker):
                self._desync = False
                return

    def close(self):
        if self._proc is not None:
            try:
                self._proc.stdin.write(f"exit{self._nl}")
                self._proc.stdin.flush()
            except Exception:
                pass
            try:
                self._proc.terminate()
            except Exception:
                pass


PersistentShell = _PosixShell if _POSIX else _WindowsShell


class FileSnapshot:
    """Automatic file snapshots for /undo."""

    def __init__(self):
        self._stack: List[Tuple[str, Optional[str], str]] = []

    def save(self, path: str, action: str = "edit"):
        p = Path(path)
        old = None
        if p.exists():
            try:
                old = p.read_text()
            except Exception:
                pass
        self._stack.append((str(p.resolve()), old, action))
        if len(self._stack) > UNDO_STACK_LIMIT:
            self._stack.pop(0)

    def undo(self) -> Optional[str]:
        if not self._stack:
            return None
        path, old, action = self._stack.pop()
        if old is None:
            try:
                Path(path).unlink()
                return f"Removed newly created: {path}"
            except Exception as e:
                return f"Undo failed (delete) {path}: {e}"
        else:
            try:
                Path(path).write_text(old)
                return f"Restored: {path} (undid {action})"
            except Exception as e:
                return f"Undo failed {path}: {e}"

    @property
    def has_entries(self) -> bool:
        return bool(self._stack)


class ToolRegistry:
    """Local tool implementations."""

    def __init__(self, shell: PersistentShell, snaps: FileSnapshot):
        self.shell = shell
        self.snaps = snaps

    def bash(self, command: str, timeout: int = SHELL_TIMEOUT) -> str:
        output, code = self.shell.run(command, timeout=timeout)
        output = self._truncate(output)
        suffix = f"\n[exit code: {code}]" if code != 0 else ""
        return f"{output}{suffix}".strip() or "[no output]"

    def read_file(self, path: str, offset: int = 1, limit: int = 0) -> str:
        p = Path(path).expanduser()
        if not p.exists():
            return f"[error] File not found: {path}"
        if not p.is_file():
            return f"[error] Not a file: {path}"
        try:
            lines = p.read_text().splitlines()
            total = len(lines)
            start = max(0, offset - 1)
            # Default window: READ_WINDOW lines. Whole-file reads blow up the
            # upstream thread context — the model should page with offset/limit.
            if limit <= 0:
                limit = min(READ_WINDOW, max(total - start, 1))
            end = start + limit
            selected = lines[start:end]
            numbered = [f"{i+start+1:5d} | {l}" for i, l in enumerate(selected)]
            header = f"[{path}] {total} lines, showing {start+1}–{min(end, total)}"
            body = f"{header}\n" + "\n".join(numbered)
            if end < total:
                body += (
                    f"\n[... file continues — {total - end} more lines. "
                    f"Use offset={min(end + 1, total)} limit={READ_WINDOW} to page, "
                    f"or grep to locate specific content.]"
                )
            return body
        except Exception as e:
            return f"[error] {path}: {e}"

    def write_file(self, path: str, content: str) -> str:
        p = Path(path).expanduser()
        try:
            if content and not content.endswith("\n"):
                content += "\n"
            self.snaps.save(str(p), "write")
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
            n = content.count("\n")
            return f"[wrote {path} — {n} lines, {len(content)} bytes]"
        except Exception as e:
            return f"[error] write {path}: {e}"

    def edit_file(self, path: str, old_string: str, new_string: str) -> str:
        p = Path(path).expanduser()
        if not p.exists():
            return f"[error] File not found: {path}"
        try:
            text = p.read_text()
            count = text.count(old_string)
            if count == 0:
                return (
                    f"[error] old_string not found in {path}. "
                    "Read the file first to get exact content."
                )
            if count > 1:
                return f"[error] old_string matches {count} places in {path}. Be more specific."
            self.snaps.save(str(p), "edit")
            new_text = text.replace(old_string, new_string, 1)
            p.write_text(new_text)
            diff = "\n".join(difflib.unified_diff(
                old_string.splitlines(keepends=True),
                new_string.splitlines(keepends=True),
                fromfile=f"a/{p.name}", tofile=f"b/{p.name}", lineterm="",
            ))
            return f"[edited {path}]\n{self._truncate(diff)}"
        except Exception as e:
            return f"[error] edit {path}: {e}"

    def list_dir(self, path: str = ".", depth: int = 3) -> str:
        p = Path(path).expanduser().resolve()
        if not p.exists():
            return f"[error] Not found: {path}"
        if not p.is_dir():
            return f"[error] Not a directory: {path}"
        ignore = {".git", "node_modules", "__pycache__", ".venv", ".tox", ".idea", ".vscode"}
        lines: List[str] = []
        base_depth = len(p.parts)
        for root, dirs, files in os.walk(p):
            cur_parts = Path(root).parts
            cur_depth = len(cur_parts) - base_depth
            if cur_depth >= depth:
                dirs.clear()
                continue
            dirs[:] = [d for d in sorted(dirs) if d not in ignore]
            rel_dir = os.path.relpath(root, p)
            prefix = "" if rel_dir == "." else f"{rel_dir}/"
            for d in dirs:
                lines.append(f"{prefix}{d}/")
                if len(lines) >= 300:
                    break
            for f in sorted(files):
                lines.append(f"{prefix}{f}")
                if len(lines) >= 300:
                    break
            if len(lines) >= 300:
                break
        return "\n".join(lines[:300]) or "[empty]"

    def grep(self, pattern: str, path: str = ".", include: str = "") -> str:
        if not _POSIX:
            return self._grep_python(pattern, path, include)
        inc = f"--include='{include}'" if include else ""
        cmd = (
            f"grep -rn --color=never {inc} -E '{pattern}' '{path}' "
            f"--exclude-dir=.git --exclude-dir=node_modules "
            f"--exclude-dir=__pycache__ --exclude-dir=.venv "
            f"2>/dev/null | head -80"
        )
        out, _ = self.shell.run(cmd, timeout=15)
        return self._truncate(out) or "[no matches]"

    def _grep_python(self, pattern: str, path: str = ".", include: str = "",
                     max_results: int = 80) -> str:
        """Pure-Python recursive regex search (Windows path — no shell grep)."""
        try:
            rx = re.compile(pattern)
        except re.error as e:
            return f"[error] invalid regex: {e}"
        base = Path(path).expanduser()
        if not base.exists():
            return f"[error] Not found: {path}"
        ignore_dirs = {".git", "node_modules", "__pycache__", ".venv", ".tox", ".idea", ".vscode"}
        results: List[str] = []
        files = [base] if base.is_file() else []
        if not files:
            for root, dirs, names in os.walk(base):
                dirs[:] = [d for d in sorted(dirs) if d not in ignore_dirs]
                for n in sorted(names):
                    if include and not fnmatch.fnmatch(n, include):
                        continue
                    files.append(Path(root) / n)
                    if len(results) >= max_results:
                        break
                if len(results) >= max_results:
                    break
        for f in files:
            if len(results) >= max_results:
                break
            try:
                if f.stat().st_size > 2_000_000:
                    continue
                text = f.read_text(errors="ignore")
            except OSError:
                continue
            for i, ln in enumerate(text.splitlines(), 1):
                if rx.search(ln):
                    results.append(f"{f}:{i}: {ln.strip()[:300]}")
                    if len(results) >= max_results:
                        break
        return "\n".join(results) or "[no matches]"

    def _truncate(self, text: str) -> str:
        if not text:
            return text
        if len(text) > MAX_OUTPUT_CHARS:
            head = text[:12000]
            tail = text[-8000:]
            return f"{head}\n\n[... truncated: showing first 12000 + last 8000 of {len(text)} chars ...]\n\n{tail}"
        lines = text.splitlines()
        if len(lines) <= OUTPUT_HEAD + OUTPUT_TAIL + 10:
            return text
        head = "\n".join(lines[:OUTPUT_HEAD])
        tail = "\n".join(lines[-OUTPUT_TAIL:])
        omitted = len(lines) - OUTPUT_HEAD - OUTPUT_TAIL
        return f"{head}\n\n[... {omitted} of {len(lines)} lines omitted ...]\n\n{tail}"


# ═══════════════════════════════════════════════════════════════════════════════
# § 4. TOOL PARSER — Hybrid XML / Markdown / JSON
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ToolCall:
    name: str
    args: Dict[str, Any]
    raw: str = ""


class ToolParser:
    NAMES = {"bash", "read_file", "write_file", "edit_file", "list_dir", "grep"}

    MD_BASH_RE = re.compile(r'```(?:bash|sh|shell)\s*\n(.*?)\n\s*```', re.DOTALL)

    @classmethod
    def parse(cls, text: str) -> Tuple[str, List[ToolCall]]:
        calls: List[ToolCall] = []

        # Identify ranges of markdown code fences and inline backticks to avoid parsing examples as live tool calls
        masked_spans = []
        for m in re.finditer(r"```.*?```", text, re.DOTALL):
            masked_spans.append((m.start(), m.end()))
        for m in re.finditer(r"`[^`\n]+`", text):
            masked_spans.append((m.start(), m.end()))

        def is_masked(pos: int) -> bool:
            return any(s <= pos < e for s, e in masked_spans)

        cleaned_parts: List[str] = []
        last_end = 0
        i = 0

        # 1. Depth-aware XML tag parser (handles nested tool examples inside write_file/edit_file)
        while i < len(text):
            tag_start = text.find("<tool", i)
            if tag_start == -1:
                break

            # If this tag is inside a markdown code fence or backticks, it is documentation/example — skip it!
            if is_masked(tag_start):
                i = tag_start + 5
                continue

            tag_open_end = text.find(">", tag_start)
            if tag_open_end == -1:
                break

            header = text[tag_start:tag_open_end + 1]
            m = re.match(r'<tool\s+name=["\'](\w+)["\']([^>]*)>', header)
            if not m:
                i = tag_open_end + 1
                continue

            name = m.group(1).lower()
            attrs_str = m.group(2)
            if name not in cls.NAMES:
                i = tag_open_end + 1
                continue

            attrs = cls._attrs(attrs_str)

            # Balanced tag finder (handles nested <tool> inside write_file/edit_file)
            depth = 1
            pos = tag_open_end + 1
            body_start = pos
            closing_tag_end = len(text)
            body = text[body_start:]

            while pos < len(text):
                next_open = text.find("<tool", pos)
                next_close = text.find("</tool>", pos)

                if next_close == -1:
                    # Unclosed tool tag at end of message (e.g. truncated stream)
                    body = text[body_start:]
                    closing_tag_end = len(text)
                    pos = len(text)
                    break

                if next_open != -1 and next_open < next_close:
                    # Inner <tool tag (nested example inside code/docs)
                    depth += 1
                    pos = next_open + 5
                else:
                    depth -= 1
                    if depth == 0:
                        closing_tag_end = next_close + 7
                        body = text[body_start:next_close]
                        pos = closing_tag_end
                        break
                    else:
                        pos = next_close + 7

            cleaned_parts.append(text[last_end:tag_start])
            args = cls._build(name, attrs, body.strip())
            raw_tag = text[tag_start:closing_tag_end]
            calls.append(ToolCall(name=name, args=args, raw=raw_tag))
            last_end = closing_tag_end
            i = pos

        cleaned_parts.append(text[last_end:])
        cleaned = "".join(cleaned_parts).strip()

        if calls:
            return cleaned, calls

        # 2. JSON objects
        for obj in cls._json_objects(text):
            name = (obj.get("tool") or obj.get("name") or "").lower()
            if name not in cls.NAMES:
                continue
            a = obj.get("args") or obj.get("arguments") or obj.get("parameters") or {}
            if not isinstance(a, dict):
                a = {}
            for k in ("command", "path", "content", "old_string", "new_string",
                       "pattern", "include", "offset", "limit", "depth", "timeout"):
                if k in obj and k not in a:
                    a[k] = obj[k]
            calls.append(ToolCall(name=name, args=a))

        if calls:
            return cleaned.strip(), calls

        # 3. Markdown bash
        bm = cls.MD_BASH_RE.search(text)
        if bm:
            cmd = bm.group(1).strip()
            if cmd:
                calls.append(ToolCall(name="bash", args={"command": cmd}))
                cleaned = cleaned.replace(bm.group(0), "").strip()
                return cleaned, calls

        return text, []

    @classmethod
    def _json_objects(cls, text: str) -> List[Dict[str, Any]]:
        results = []
        brace = 0
        start = -1
        in_str = False
        esc = False
        for i, ch in enumerate(text):
            if ch == '"' and not esc:
                in_str = not in_str
            elif not in_str:
                if ch == '{':
                    if brace == 0:
                        start = i
                    brace += 1
                elif ch == '}':
                    brace -= 1
                    if brace == 0 and start != -1:
                        candidate = text[start:i+1]
                        obj = cls._safe_parse(candidate)
                        if isinstance(obj, dict):
                            results.append(obj)
                        start = -1
            esc = ch == '\\' and not esc
        return results

    @staticmethod
    def _safe_parse(s: str) -> Any:
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            pass
        try:
            return json.loads(s, strict=False)
        except json.JSONDecodeError:
            pass
        fixed = re.sub(r',\s*([}\]])', r'\1', s)
        try:
            return json.loads(fixed, strict=False)
        except json.JSONDecodeError:
            pass
        return None

    @staticmethod
    def _attrs(s: str) -> Dict[str, str]:
        return {m.group(1): m.group(2) for m in re.finditer(r'(\w+)\s*=\s*["\']([^"\']*)["\']', s)}

    @staticmethod
    def _build(name: str, attrs: Dict[str, str], body: str) -> Dict[str, Any]:
        if name == "bash":
            a: Dict[str, Any] = {"command": body}
            if "timeout" in attrs:
                a["timeout"] = attrs["timeout"]
            return a
        elif name == "read_file":
            path = attrs.get("path") or attrs.get("file") or attrs.get("filepath") or body
            a = {"path": path}
            if "offset" in attrs:
                a["offset"] = int(attrs["offset"])
            if "limit" in attrs:
                a["limit"] = int(attrs["limit"])
            return a
        elif name == "write_file":
            path = attrs.get("path") or attrs.get("file") or attrs.get("filepath") or ""
            if not path and body:
                lines = body.splitlines()
                first = lines[0].strip()
                if first.startswith(("# path:", "// path:", "path:", "file:", "# file:", "// file:")):
                    path = first.split(":", 1)[1].strip().strip("`\"'")
                    body = "\n".join(lines[1:]).strip()
            return {"path": path, "content": body}
        elif name == "edit_file":
            path = attrs.get("path") or attrs.get("file") or attrs.get("filepath") or ""
            parts = re.split(r'\n-{3,}\s*\n', body, maxsplit=1)
            if len(parts) == 2:
                return {"path": path, "old_string": parts[0], "new_string": parts[1]}
            try:
                j = json.loads(body)
                if isinstance(j, dict):
                    return {"path": path, **j}
            except Exception:
                pass
            return {"path": path, "old_string": body, "new_string": ""}
        elif name == "list_dir":
            a = {"path": attrs.get("path", body or ".")}
            if "depth" in attrs:
                a["depth"] = int(attrs["depth"])
            return a
        elif name == "grep":
            return {
                "pattern": attrs.get("pattern", body),
                "path": attrs.get("path", "."),
                "include": attrs.get("include", ""),
            }
        return {}


# ═══════════════════════════════════════════════════════════════════════════════
# § 5. CONTEXT MANAGER — History + Active Compaction
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Turn:
    role: str
    content: str
    tool_name: str = ""
    step: int = 0

    @property
    def size(self) -> int:
        return len(self.content)


class ContextManager:
    def __init__(self, budget: int = CONTEXT_BUDGET):
        self.history: List[Turn] = []
        self.budget = budget

    def add(self, role: str, content: str, tool_name: str = "", step: int = 0):
        self.history.append(Turn(role=role, content=content, tool_name=tool_name, step=step))
        self._compact()

    def _compact(self):
        total = sum(t.size for t in self.history)
        if total <= self.budget:
            return
        if len(self.history) <= 7:
            return

        # compress long tool results in middle
        for t in self.history[1:-6]:
            if t.role == "tool_result" and t.size > 2000:
                lines = t.content.splitlines()
                if len(lines) > 30:
                    head = "\n".join(lines[:10])
                    tail = "\n".join(lines[-10:])
                    t.content = f"{head}\n[... {len(lines)-20} lines compacted ...]\n{tail}"

        # drop oldest middle entries
        total = sum(t.size for t in self.history)
        while total > self.budget and len(self.history) > 8:
            removed = self.history.pop(1)
            total -= removed.size

    def build_prompt(self, system: str) -> str:
        parts = [system, ""]
        for t in self.history:
            if t.role == "user":
                parts.append(f"Human: {t.content}")
            elif t.role == "assistant":
                parts.append(f"Assistant: {t.content}")
            elif t.role == "tool_result":
                lbl = f"[{t.tool_name}]" if t.tool_name else "[tool]"
                parts.append(f"Tool Result {lbl}:\n{t.content}")
            parts.append("")
        return "\n".join(parts)

    def clear(self):
        self.history.clear()

    def stats(self) -> Tuple[int, int]:
        total = sum(t.size for t in self.history)
        return len(self.history), total


# ═══════════════════════════════════════════════════════════════════════════════
# § 6. AGENT ENGINE — ReAct Loop + System Prompt
# ═══════════════════════════════════════════════════════════════════════════════

def _system_prompt() -> str:
    cwd = os.getcwd()
    if _POSIX:
        plat = f"{platform.system()} {platform.machine()}"
        shell_line = "Shell: bash (persistent — cd, exports, source, venvs survive across tool calls)"
    else:
        plat = f"Windows {platform.release()} ({platform.machine()})"
        shell_line = (
            "Shell: cmd.exe (persistent — cd, set, and environment changes survive across tool calls). "
            "Use Windows command syntax: dir, type, del, copy, where, python. "
            "bash syntax (ls, cat, rm, grep) does NOT work — use the dedicated tools instead."
        )
    return textwrap.dedent(f"""\
    You are Apex, an autonomous coding agent executing directly on the user's workstation.
    You have active local tool integration: bash, read_file, write_file, edit_file, list_dir, grep.
    Your tool calls run immediately in the local environment and return real outputs.
    Accomplish engineering and coding tasks autonomously using tools.
    Never ask the user to run commands manually. Never claim you lack environment or tool access.

    Environment:
    - Working directory: {cwd}
    - Platform: {plat}
    - {shell_line}
    - Date: {time.strftime('%Y-%m-%d')}

    ## Tool Calling

    To use a tool, output an XML tag. You may include brief thinking before the tag.
    Call ONE tool per response, then wait for the result.

    ### bash — Execute a shell command
    <tool name="bash">
    ls -la
    </tool>

    ### read_file — Read a file with line numbers (paged: returns up to ~250 lines)
    <tool name="read_file" path="/absolute/path/to/file">
    </tool>
    With offset and limit for targeted reads (PREFERRED for large files):
    <tool name="read_file" path="/path/file" offset="50" limit="30">
    </tool>

    ### write_file — Create or overwrite a file
    <tool name="write_file" path="/path/to/file">
    file content here
    </tool>

    ### edit_file — Replace an exact string in a file (must match exactly once)
    <tool name="edit_file" path="/path/to/file">
    exact old text to find
    ---
    replacement new text
    </tool>

    ### list_dir — List directory tree
    <tool name="list_dir" path="." depth="3">
    </tool>

    ### grep — Search files with regex
    <tool name="grep" pattern="TODO|FIXME" path="src/" include="*.py">
    </tool>

    ## Rules
    1. ONE tool call per response. Wait for the result before calling the next.
    2. ALWAYS read a file before editing — never guess at content.
    3. When done, write a clear summary. No tool call in the final answer.
    4. If a command fails, analyze the error and try a different approach.
    5. Prefer edit_file over write_file for existing files.
    6. Use bash for: running code, tests, installs, git, process management.
    7. Use absolute paths. Resolve relative paths from the working directory.
    8. CRITICAL FILE CREATION RULE:
       To create or write a file, you MUST put the file content INSIDE the <tool name="write_file" path="...">content</tool> tag.
       NEVER output the file content as raw chat text or markdown blocks — the ONLY way files are created on disk is through the write_file tool.
    9. Complete file contents: Always provide the complete file content inside write_file.

    ## Working style (agentic discipline)
    - PLAN FIRST: for any multi-step task, your FIRST response is a short numbered plan (3-6 steps, one line each). Then execute it step by step. Never re-plan mid-task unless something failed.
    - BE SURGICAL with reads: files larger than ~250 lines are paged — use offset/limit to read only what you need, and grep to locate content before reading. Do NOT read entire large files.
    - CREATE ONLY WHAT WAS ASKED: never generate unsolicited summary, index, README, or "documentation about the work" files. The user reads your chat summary; extra files are noise.
    - FINISH CLEAN: when the task's goal is met, stop. Your final message is a short result summary (what changed, where, how verified) — not a restatement of everything you did.
    """)


class AgentEngine:
    def __init__(
        self,
        client: GensparkClient,
        tools: ToolRegistry,
        context: ContextManager,
        model: str = DEFAULT_MODEL,
        max_steps: int = MAX_STEPS_DEFAULT,
        search: bool = False,
    ):
        self.client = client
        self.tools = tools
        self.ctx = context
        self.model = model
        self.max_steps = max_steps
        self.search = search
        self.moa: Optional[List[str]] = None
        self._stop = False

    def run(self, user_input: str) -> str:
        try:
            return self._run_loop(user_input)
        except KeyboardInterrupt:
            # Ctrl+C during streaming OR during tool execution: abort the task,
            # keep the REPL session alive.
            self._stop = True
            print(C.s("\n  [task interrupted — session preserved]", C.YELLOW))
            return ""

    def _run_loop(self, user_input: str) -> str:
        self._stop = False
        self.ctx.add("user", user_input)
        system = _system_prompt()

        step = 0
        final = ""
        last_tc: Optional[ToolCall] = None
        last_out: str = ""

        while step < self.max_steps and not self._stop:
            step += 1
            if step == 1:
                if self.client.project_id is None:
                    prompt = f"{system}\n\nUser: {user_input}"
                else:
                    prompt = f"User: {user_input}"
            else:
                tc_name = last_tc.name if last_tc else "tool"
                prompt = f"Tool Result [{tc_name}]:\n{last_out}"

            _ui_step(step, self.model)

            renderer = StreamRenderer(RICH_CONSOLE)
            renderer.start(self.model)

            try:
                result = self.client.stream(
                    query=prompt,
                    model=self.model,
                    enable_search=self.search,
                    moa_models=self.moa,
                    on_delta=lambda d: renderer.on_delta(d, self.model),
                )
            except KeyboardInterrupt:
                renderer.stop()
                self._stop = True
                print(C.s("\n  [interrupted]", C.YELLOW))
                break
            except Exception as e:
                renderer.stop()
                msg = f"[upstream error: {e}]"
                print(C.s(f"\n  {msg}", C.RED))
                self.ctx.add("tool_result", msg, tool_name="error", step=step)
                break
            finally:
                renderer.stop()

            text = result.get("text", "")
            if not text.strip():
                # Server-side thread dropped or returned empty; reset and retry with compacted context
                print(C.s("\n  [empty response — resetting thread session and continuing with context...]", C.YELLOW))
                self.client.reset_thread()
                fallback_prompt = self.ctx.build_prompt(system)
                renderer = StreamRenderer(RICH_CONSOLE)
                renderer.start(self.model)
                try:
                    result = self.client.stream(
                        query=fallback_prompt,
                        model=self.model,
                        enable_search=self.search,
                        moa_models=self.moa,
                        on_delta=lambda d: renderer.on_delta(d, self.model),
                    )
                    text = result.get("text", "")
                except Exception as e:
                    print(C.s(f"\n  [recovery error: {e}]", C.RED))
                    break
                finally:
                    renderer.stop()

            cleaned, calls = ToolParser.parse(text)
            self.ctx.add("assistant", text, step=step)

            if not calls:
                _render_markdown(cleaned)
                final = cleaned or text
                break

            _render_markdown(cleaned)

            tc = calls[0]
            _ui_tool_start(tc)
            output = self._exec(tc)
            if len(calls) > 1:
                ignored = ", ".join(c.name for c in calls[1:])
                output += (
                    f"\n[note] {len(calls) - 1} additional tool call(s) in this response "
                    f"were IGNORED ({ignored}). Make ONE tool call per response."
                )
                print(C.s(f"  [warn] model emitted {len(calls)} tool calls — executed only {tc.name}", C.YELLOW))
            _ui_tool_output(output, tool=tc.name)
            self.ctx.add("tool_result", output, tool_name=tc.name, step=step)
            last_tc = tc
            last_out = output

        if step >= self.max_steps and not self._stop:
            print(C.s(f"\n  [step limit {self.max_steps} reached]", C.YELLOW))

        return final

    def _exec(self, tc: ToolCall) -> str:
        a = tc.args
        try:
            if tc.name == "bash":
                return self.tools.bash(
                    command=a.get("command", ""),
                    timeout=int(a.get("timeout", SHELL_TIMEOUT)),
                )
            elif tc.name == "read_file":
                return self.tools.read_file(
                    path=a.get("path", ""),
                    offset=int(a.get("offset", 1)),
                    limit=int(a.get("limit", 0)),
                )
            elif tc.name == "write_file":
                return self.tools.write_file(
                    path=a.get("path", ""),
                    content=a.get("content", ""),
                )
            elif tc.name == "edit_file":
                return self.tools.edit_file(
                    path=a.get("path", ""),
                    old_string=a.get("old_string", ""),
                    new_string=a.get("new_string", ""),
                )
            elif tc.name == "list_dir":
                return self.tools.list_dir(
                    path=a.get("path", "."),
                    depth=int(a.get("depth", 3)),
                )
            elif tc.name == "grep":
                return self.tools.grep(
                    pattern=a.get("pattern", ""),
                    path=a.get("path", "."),
                    include=a.get("include", ""),
                )
            else:
                return f"[error] Unknown tool: {tc.name}"
        except Exception as e:
            return f"[tool error] {tc.name}: {e}"

    def interrupt(self):
        self._stop = True


# ═══════════════════════════════════════════════════════════════════════════════
# § 7. TERMINAL UI
# ═══════════════════════════════════════════════════════════════════════════════

RICH_CONSOLE = Console(theme=Theme({
    "markdown.h1": "bold cyan",
    "markdown.h2": "bold bright_blue",
    "markdown.h3": "bold yellow",
    "markdown.code": "bold green",
    "markdown.code_block": "green",
}))


class StreamRenderer:
    def __init__(self, con: Console = RICH_CONSOLE):
        self.console = con
        self.buf = ""
        self.tokens = 0
        self.status = None

    def start(self, model: str):
        self.buf = ""
        self.tokens = 0
        tier = MODEL_CATALOG.get(model, {}).get("tier", "")
        label = f"{model} ({tier})" if tier else model
        self.status = self.console.status(f"[dim cyan]⚡ {label} streaming... (0 tokens)[/]", spinner="dots")
        self.status.start()

    def on_delta(self, d: str, model: str = ""):
        self.buf += d
        self.tokens += 1
        if self.status and (self.tokens % 5 == 0):
            tier = MODEL_CATALOG.get(model, {}).get("tier", "")
            label = f"{model} ({tier})" if tier else model
            self.status.update(f"[dim cyan]⚡ {label} streaming... ({self.tokens} tokens)[/]")

    def stop(self) -> str:
        if self.status:
            try:
                self.status.stop()
            except Exception:
                pass
            self.status = None
        return self.buf


def _render_markdown(text: str):
    """Compile markdown once, single-pass. Caps pathological outputs so the
    terminal can never flood (see handoff Bug #2)."""
    if not text or not text.strip():
        return
    if len(text) > MAX_RENDER_CHARS:
        RICH_CONSOLE.print(Markdown(text[:MAX_RENDER_CHARS]))
        RICH_CONSOLE.print(
            C.s(f"  [... output truncated — {len(text) - MAX_RENDER_CHARS} chars omitted ...]", C.YELLOW)
        )
    else:
        RICH_CONSOLE.print(Markdown(text))


def _ui_step(step: int, model: str):
    tier = MODEL_CATALOG.get(model, {}).get("tier", "?")
    print(f"\n{C.BOLD}{C.BLUE}{'━' * 60}{C.RESET}")
    print(f"  {C.BOLD}{C.CYAN}⚡ Step {step}{C.RESET}  {C.DIM}{model} ({tier}){C.RESET}")
    print(f"{C.BOLD}{C.BLUE}{'━' * 60}{C.RESET}\n")


def _ui_delta(delta: str):
    sys.stdout.write(delta)
    sys.stdout.flush()


def _ui_newline():
    sys.stdout.write("\n")
    sys.stdout.flush()


def _ui_tool_start(tc: ToolCall):
    icons = {
        "bash": "⌘", "read_file": "📄", "write_file": "✏️",
        "edit_file": "🔧", "list_dir": "📂", "grep": "🔍",
    }
    icon = icons.get(tc.name, "🔨")
    detail = ""
    if tc.name == "bash":
        cmd = tc.args.get("command", "")
        detail = cmd[:120] + ("…" if len(cmd) > 120 else "")
    elif tc.name in ("read_file", "write_file", "edit_file"):
        detail = tc.args.get("path", "")
    elif tc.name == "list_dir":
        d = tc.args.get("path", "")
        detail = f"{d} (depth {tc.args.get('depth', 3)})" if d else ""
    elif tc.name == "grep":
        detail = f"/{tc.args.get('pattern', '')}/ in {tc.args.get('path', '.')}"

    print(f"\n  {C.BOLD}{C.GREEN}┌─ {icon} {tc.name}{C.RESET}  {C.DIM}{detail}{C.RESET}")


def _ui_tool_output(output: str, tool: str = ""):
    # Reads/directory dumps are visual noise at full length — display a tighter window.
    half = 15 if tool in ("read_file", "list_dir", "grep") else 30
    lines = output.splitlines()
    limit = half * 2
    if len(lines) > limit:
        shown = limit
        hidden = len(lines) - shown
        for ln in lines[:half]:
            print(f"  {C.GREEN}│{C.RESET} {C.DIM}{ln}{C.RESET}")
        print(f"  {C.GREEN}│{C.RESET} {C.YELLOW}  … {hidden} display lines collapsed …{C.RESET}")
        # surface any truncation notes from the tool layer that would otherwise be hidden
        for i, ln in enumerate(lines):
            s = ln.strip()
            if (s.startswith("[...") and ("omitted" in s or "truncated" in s or "file continues" in s)
                    and half <= i < len(lines) - half):
                print(f"  {C.GREEN}│{C.RESET} {C.YELLOW}{s}{C.RESET}")
        for ln in lines[-half:]:
            print(f"  {C.GREEN}│{C.RESET} {C.DIM}{ln}{C.RESET}")
    else:
        for ln in lines:
            print(f"  {C.GREEN}│{C.RESET} {C.DIM}{ln}{C.RESET}")
    print(f"  {C.BOLD}{C.GREEN}└─{C.RESET}")


def _ui_banner(pool: AccountPool, model: str, max_steps: int):
    n = len(pool.accounts)
    tags = ", ".join(a.tag for a in pool.accounts)
    tier = MODEL_CATALOG.get(model, {}).get("tier", "?")
    shell_desc = "persistent PTY bash" if _POSIX else "persistent cmd.exe"
    print(f"""
{C.BOLD}{C.CYAN}╔══════════════════════════════════════════════════════════╗
║                    ⚡ APEX HARNESS ⚡                    ║
╚══════════════════════════════════════════════════════════╝{C.RESET}
  {C.DIM}v{VERSION} — Autonomous Coding Agent for Genspark Models{C.RESET}
  {C.GREEN}Model:{C.RESET}    {model}  ({tier})
  {C.GREEN}Accounts:{C.RESET} {n} loaded  [{tags}]
  {C.GREEN}Shell:{C.RESET}    {shell_desc}  |  {C.GREEN}Tools:{C.RESET} bash, read, write, edit, list, grep
  {C.GREEN}Steps:{C.RESET}    {max_steps} max  |  {C.GREEN}Mode:{C.RESET} auto-execute

  {C.DIM}Type a task, or /help for commands. Ctrl+C to interrupt.{C.RESET}
""")


# ═══════════════════════════════════════════════════════════════════════════════
# § 8. APEX CLI — Interactive REPL
# ═══════════════════════════════════════════════════════════════════════════════

class ApexCLI:
    def __init__(self, args: argparse.Namespace):
        self.client = GensparkClient(args.cookies)
        self.shell = PersistentShell()
        self.snaps = FileSnapshot()
        self.tools = ToolRegistry(self.shell, self.snaps)
        self.ctx = ContextManager()
        self.engine = AgentEngine(
            client=self.client,
            tools=self.tools,
            context=self.ctx,
            model=args.model,
            max_steps=args.max_steps,
            search=args.search,
        )
        self.query = args.query

        # readline history (POSIX; Windows console host provides basic line editing)
        if readline is not None:
            HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            try:
                readline.read_history_file(str(HISTORY_FILE))
            except FileNotFoundError:
                pass
            readline.set_history_length(2000)
            atexit.register(readline.write_history_file, str(HISTORY_FILE))
        atexit.register(self.shell.close)

    def run(self):
        _ui_banner(self.client.pool, self.engine.model, self.engine.max_steps)

        if self.query:
            self.engine.run(self.query)
            return

        while True:
            try:
                inp = input(f"{C.BOLD}{C.CYAN}apex ▸ {C.RESET}").strip()
            except EOFError:
                print(C.s("\n[goodbye]", C.CYAN))
                break
            except KeyboardInterrupt:
                # Ctrl+C at the prompt: clear the line, don't exit
                print(C.s("\n  [press /exit or Ctrl+D to quit]", C.YELLOW))
                continue

            if not inp:
                continue

            if inp.startswith("/"):
                if not self._cmd(inp):
                    break
            else:
                self.engine.run(inp)

    def _cmd(self, raw: str) -> bool:
        parts = raw.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if cmd in ("/exit", "/quit", "/q"):
            print(C.s("[goodbye]", C.CYAN))
            return False

        elif cmd == "/help":
            print(f"""
  {C.BOLD}Commands:{C.RESET}
  {C.CYAN}/model [name]{C.RESET}     View or switch model
  {C.CYAN}/search [on|off]{C.RESET}  Toggle web search
  {C.CYAN}/accounts{C.RESET}         Account pool health
  {C.CYAN}/undo{C.RESET}             Undo last file change
  {C.CYAN}/reset{C.RESET}            Clear conversation
  {C.CYAN}/clear{C.RESET}            Clear screen
  {C.CYAN}/steps [n]{C.RESET}        View/set max steps
  {C.CYAN}/history{C.RESET}          Context usage stats
  {C.CYAN}/help{C.RESET}             This help
  {C.CYAN}/exit{C.RESET}             Quit
""")

        elif cmd == "/model":
            if arg:
                if arg in MODEL_CATALOG:
                    old = self.engine.model
                    self.engine.model = arg
                    self.engine.moa = None
                    t = MODEL_CATALOG[arg]["tier"]
                    print(C.s(f"  {old} → {arg} ({t})", C.GREEN))
                elif arg == "genspark-moa":
                    self.engine.moa = MOA_DEFAULT
                    self.engine.model = "gpt-5.1-low"
                    print(C.s("  Switched to Mixture-of-Agents", C.GREEN))
                else:
                    print(C.s(f"  Unknown: {arg}", C.RED))
            else:
                cur = self.engine.model
                print(f"\n  {C.BOLD}Current:{C.RESET} {cur}")
                if self.engine.moa:
                    print(f"  {C.BOLD}MoA:{C.RESET} {', '.join(self.engine.moa)}")
                print(f"\n  {C.BOLD}Available:{C.RESET}")
                for mid, info in MODEL_CATALOG.items():
                    mark = " ◀" if mid == cur else ""
                    print(f"    {C.CYAN}{mid:40s}{C.RESET} {info['tier']:>5s}  {C.DIM}{info['cls']}{C.RESET}{C.GREEN}{mark}{C.RESET}")
                print()

        elif cmd == "/search":
            if arg.lower() in ("on", "true", "1"):
                self.engine.search = True
                print(C.s("  Search: ON", C.GREEN))
            elif arg.lower() in ("off", "false", "0"):
                self.engine.search = False
                print(C.s("  Search: OFF", C.YELLOW))
            else:
                st = "ON" if self.engine.search else "OFF"
                print(f"  Search: {st}  (/search on|off)")

        elif cmd == "/accounts":
            print(f"\n  {C.BOLD}Account Pool:{C.RESET}")
            for h in self.client.pool.health():
                dot = C.s("●", C.GREEN) if h["available"] else C.s(f"● cd {h['cooldown_sec']}s", C.RED)
                print(f"    {dot}  {h['tag']}  req={h['requests']} ok={h['successes']} 429={h['rate_limits']}")
            print()

        elif cmd == "/reset":
            self.ctx.clear()
            self.client.reset_thread()
            print(C.s("  Reset.", C.GREEN))

        elif cmd == "/clear":
            os.system("cls" if os.name == "nt" else "clear")

        elif cmd == "/undo":
            if self.snaps.has_entries:
                print(C.s(f"  {self.snaps.undo()}", C.GREEN))
            else:
                print(C.s("  Nothing to undo.", C.YELLOW))

        elif cmd == "/steps":
            if arg:
                try:
                    self.engine.max_steps = int(arg)
                    print(C.s(f"  Max steps: {self.engine.max_steps}", C.GREEN))
                except ValueError:
                    print(C.s("  Usage: /steps <number>", C.RED))
            else:
                print(f"  Max steps: {self.engine.max_steps}")

        elif cmd == "/history":
            n, sz = self.ctx.stats()
            pct = sz * 100 // self.ctx.budget if self.ctx.budget else 0
            print(f"  {n} turns, {sz} chars ({pct}% of budget)")

        else:
            print(C.s(f"  Unknown: {cmd}. /help", C.RED))

        return True


# ═══════════════════════════════════════════════════════════════════════════════
# § 9. ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    ap = argparse.ArgumentParser(
        description="Apex Harness — Autonomous coding agent for Genspark models",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
        Examples:
          ./apex                                    # interactive REPL
          ./apex -q "create a flask hello world"    # single task
          ./apex --model gpt-5.6-sol
          ./apex --model genspark-moa --search
          ./apex --cookies cookies.json,cookies_2.json
        """),
    )
    ap.add_argument("-q", "--query", help="Single query (non-interactive)")
    ap.add_argument(
        "--model", default=DEFAULT_MODEL,
        help=f"Model (default: {DEFAULT_MODEL})",
    )
    ap.add_argument("--cookies", default="cookies.json", help="Cookie file(s)")
    ap.add_argument("--search", action="store_true", help="Enable web search")
    ap.add_argument(
        "--max-steps", type=int, default=MAX_STEPS_DEFAULT,
        help=f"Max steps per task (default: {MAX_STEPS_DEFAULT})",
    )
    ap.add_argument("--version", action="version", version=f"apex {VERSION}")

    args = ap.parse_args()

    try:
        cli = ApexCLI(args)
        cli.run()
    except RuntimeError as e:
        print(C.s(f"\n[fatal] {e}", C.RED))
        sys.exit(1)
    except KeyboardInterrupt:
        print(C.s("\n[goodbye]", C.CYAN))


if __name__ == "__main__":
    main()

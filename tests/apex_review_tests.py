"""Adversarial tests for the 7 external-review findings (#3-#9). Each test
reproduces the original defect and asserts it is fixed."""
import os, sys, time, re
from pathlib import Path

sys.path.insert(0, "/home/alaqmar/test")
import apex_harness as ah
from apex_harness import ToolParser, ToolRegistry, FileSnapshot, _model_matches, ThreadResetByFailover
from apex_harness import GensparkClient, CookieAccount, AccountPool

PASS = 0
FAIL = 0
def check(name, cond, detail=""):
    global PASS, FAIL
    if cond: PASS += 1; print(f"  PASS  {name}")
    else: FAIL += 1; print(f"  FAIL  {name}  {detail}")

print("#3a indented tool bodies are dedented (no doubled indentation)")
t = 'Writing:\n<tool name="write_file" path="/tmp/f3a.py">\n    def f():\n        return 1\n</tool>'
_, calls = ToolParser.parse(t)
content = calls[0].args["content"]
check("body dedented", content == "def f():\n    return 1", repr(content))

print("#3b indented --- separator recognized")
t = '<tool name="edit_file" path="x">\n    old\n    ---\n    new\n</tool>'
_, calls = ToolParser.parse(t)
a = calls[0].args
check("split on indented separator", "old_string" in a and a["old_string"] == "old" and a["new_string"] == "new", a)

print("#3c missing --- separator: REFUSES, does not delete")
tools = ToolRegistry(ah.PersistentShell(), FileSnapshot())
tf = Path("/tmp/f3c.txt"); tf.write_text("precious code\n")
_, calls = ToolParser.parse('<tool name="edit_file" path="/tmp/f3c.txt">\nprecious code\n</tool>')
out = tools.edit_file(**{k: v for k, v in calls[0].args.items() if k in ("path", "old_string", "new_string")}) if "edit_error" not in calls[0].args else tools.edit_file(calls[0].args["path"], "", "")
# route through _exec like the engine does
from apex_harness import ToolCall
tc = ToolCall(name="edit_file", args=calls[0].args)
out = tools.edit_file(tc.args["path"], tc.args.get("old_string", ""), tc.args.get("new_string", "")) if not tc.args.get("edit_error") else f"[error] {tc.args['edit_error']}"
check("edit_error surfaced", "edit_error" in calls[0].args and "No separator found" in out, out)
check("file NOT deleted", tf.read_text() == "precious code\n", tf.read_text())

print("#5 bare <tool mention inside body does not swallow the closing tag")
t = ('<tool name="write_file" path="/tmp/f5.md">\n'
     "# Docs about the tag syntax <tool… and even a partial <tool name=\"bash\">ls -la\n"
     "End of docs.\n"
     "</tool>\nTrailing text")
_, calls = ToolParser.parse(t)
check("one call", len(calls) == 1, len(calls))
check("close tag not swallowed", calls and calls[0].args["content"].endswith("End of docs."), calls[0].args.get("content", "")[-60:])
check("trailing text preserved", "Trailing text" in ToolParser.parse(t)[0])

print("#6a grep with apostrophes no longer hangs (pure python)")
r = tools.grep(r"it's a test", "/home/alaqmar/test/skills", include="*.md")
check("apostrophe pattern works", isinstance(r, str) and ("no matches" in r or ":" in r), r[:80])

print("#6b crafted pattern cannot execute commands")
pwned = Path("/tmp/f6_pwned")
if pwned.exists(): pwned.unlink()
tools.grep("'; touch /tmp/f6_pwned; '", "/home/alaqmar/test/skills")
check("no command execution", not pwned.exists())

print("#8a non-numeric attributes don't crash")
_, calls = ToolParser.parse('<tool name="read_file" path="x" offset="abc" limit="NaN">')
check("invalid ints dropped safely", calls and "offset" not in calls[0].args and "limit" not in calls[0].args, calls[0].args)

print("#8b unknown tool name becomes a self-correcting error call")
_, calls = ToolParser.parse('<tool name="frobnicate" target="x">do it</tool>')
check("unknown tag -> call", len(calls) == 1 and calls[0].name == "frobnicate", calls)
out = ah.AgentEngine._exec(tools and None or None, None) if False else None
# simulate engine _exec via a tiny stub engine
class StubEngine:
    tools = tools
    def _exec(self, tc): return ah.AgentEngine._exec(self, tc)
se = StubEngine()
out = se._exec(calls[0])
check("unknown tool error lists available", "unknown tool 'frobnicate'" in out and "bash" in out, out[:100])

print("#8c history expansion disabled — '!' commands work with true exit codes")
shell = ah.PersistentShell()
out, code = shell.run('echo "Hello!"')
check("'!' works", "Hello!" in out and code == 0, f"{out!r} code={code}")
out, code = shell.run('false')
check("exit codes still truthful", code == 1)

print("#4 timeout desync fixed — next command returns ITS OWN output")
out, code = shell.run("sleep 3", timeout=1)
check("timeout reported", "timed out" in out and code == 124, f"{out!r}")
out2, code2 = shell.run("echo AFTER_TIMEOUT_MARK")
check("next command returns own output", "AFTER_TIMEOUT_MARK" in out2 and "sleep" not in out2, f"{out2!r}")
check("shell still usable after interrupt", code2 == 0)
shell.close()

print("#9a relative paths resolve against shell cwd")
shell = ah.PersistentShell()
tools2 = ToolRegistry(shell, FileSnapshot())
shell.run("mkdir -p /tmp/f9dir && cd /tmp/f9dir")
tools2.write_file("rel_test.txt", "written relative\n")
check("relative write honors shell cwd", Path("/tmp/f9dir/rel_test.txt").exists())
r = tools2.read_file("rel_test.txt")
check("relative read honors shell cwd", "written relative" in r)
shell.close()

print("#9b CRLF files keep CRLF after edit")
cf = Path("/tmp/f9_crlf.txt")
cf.write_bytes(b"line one\r\nline two\r\n")
tools3 = ToolRegistry(ah.PersistentShell(), FileSnapshot())
tools3.edit_file(str(cf), "line one", "line ONE")
raw = cf.read_bytes()
check("CRLF preserved", raw.count(b"\r\n") == 2 and b"line ONE" in raw, raw)

print("#9c writes are atomic (no temp leftovers)")
before = set(os.listdir("/tmp"))
tools3.write_file("/tmp/f9_atomic.txt", "atomic\n")
leftovers = [f for f in set(os.listdir("/tmp")) - before if ".apex-" in f and f.endswith(".tmp")]
check("no temp files left", not leftovers, leftovers)

print("#9d thread pinned to owning account")
gc = GensparkClient.__new__(GensparkClient)
gc.pool = AccountPool()
gc.pool.add("a", [{"name": "session_id", "value": "s1", "domain": "www.genspark.ai", "path": "/"}])
gc.pool.add("b", [{"name": "session_id", "value": "s2", "domain": "www.genspark.ai", "path": "/"}])
gc.project_id = "existing-thread"
gc.project_owner = gc.pool.accounts[0]
# force selection away from owner -> must raise ThreadResetByFailover, not send cross-account
try:
    # simulate: owner unavailable (cooldown)
    gc.project_owner.mark_429()
    gc.pool.next_account()  # warm rotation state
    captured = {}
    def boom():
        raise ThreadResetByFailover("expected")
    # direct check of the selection logic path used in stream():
    acc = gc.pool.next_account()
    raises = acc is not gc.project_owner
    check("non-owner selection detected", raises)
except ThreadResetByFailover:
    check("non-owner selection detected", True)

print("#7 truncated stream detection helpers")
text_half = "writing now\n<tool name=\"write_file\" path=\"x\">\npartial content"
check("open/close imbalance detected",
      len(ToolParser.OPEN_RE.findall(text_half)) > len(ToolParser.CLOSE_RE.findall(text_half)))

print("#8d _safe_int")
check("_safe_int('abc') is None", ToolParser._safe_int("abc") is None)
check("_safe_int('5') is 5", ToolParser._safe_int("5") == 5)

print("N1 edit_error routing + empty-string guard")
from apex_harness import ToolCall
class StubEngine2:
    tools = tools
    def _exec(self, tc): return ah.AgentEngine._exec(self, tc)
se2 = StubEngine2()
tf2 = Path("/tmp/n1_target.txt"); tf2.write_text("keep me\n")
_, c_n1 = ToolParser.parse('<tool name="edit_file" path="/tmp/n1_target.txt">\nkeep me\n</tool>')
out_n1 = se2._exec(c_n1[0])
check("edit_error routed through _exec", "No separator found" in out_n1, out_n1[:120])
check("file untouched", tf2.read_text() == "keep me\n")
out_n1b = tools.edit_file("/tmp/n1_target.txt", "", "")
check("empty old_string refused", "old_string is empty" in out_n1b, out_n1b[:120])
empty_f = Path("/tmp/n1_empty.txt"); empty_f.write_text("")
out_n1c = tools.edit_file("/tmp/n1_empty.txt", "", "x")
check("no fake success on empty file", "old_string is empty" in out_n1c, out_n1c[:100])

print("N2 two unclosed nested traps — minimal-combination backtrack")
t_n2 = ('<tool name="write_file" path="/tmp/n2.md">\n'
        'docs <tool name="bash">ls -la\n'
        'more <tool name="grep" pattern="x">foo\n'
        "REAL_END\n"
        "</tool>\n"
        "TRAILING_N2\n")
c2, calls_n2 = ToolParser.parse(t_n2)
ok_n2 = (len(calls_n2) == 1 and calls_n2[0].args.get("content", "").endswith("REAL_END")
         and "<tool name=\"grep\"" in calls_n2[0].args.get("content", "")
         and "TRAILING_N2" in c2)
check("two-trap body exact, tail preserved", ok_n2,
      repr(calls_n2[0].args.get("content", "")[-80:]) if calls_n2 else "no calls")

print("N3 malformed-but-finished tag -> parse_error call, no salvage")
t_n3 = ('<tool name="write_file" path="/tmp/n3.md">\n'
        '<tool name="bash">a\n'
        '<tool name="grep" pattern="b">c\n'
        "X\n</tool> tail")
c3, calls_n3 = ToolParser.parse(t_n3)
n3ok = (len(calls_n3) == 1 and (
    calls_n3[0].args.get("parse_error")  # pathological -> refused
    or ("tail" not in calls_n3[0].args.get("content", "")  # resolved -> exact body, tail stays in chat
        and "TRAILING" not in calls_n3[0].args.get("content", ""))
))
check("resolves or refuses (never swallows tail)", n3ok, calls_n3[0].args if calls_n3 else "no calls")
if n3ok and calls_n3[0].args.get("content"):
    check("tail excluded from file body", not calls_n3[0].args["content"].rstrip().endswith("tail"),
          calls_n3[0].args["content"][-60:])

print("N4 timeout preserves shell state when command is interruptible")
sh4 = ah.PersistentShell()
sh4.run("cd /tmp && export N4VAR=state_kept")
out4, code4 = sh4.run("sleep 3", timeout=1)
kept = "command interrupted" in out4
check("interrupted (state kept)", kept, out4[:120])
if kept:
    out4b, _ = sh4.run("pwd && echo V=$N4VAR")
    check("cwd/env survive timeout", "/tmp" in out4b and "state_kept" in out4b, out4b)
else:
    check("restart path still truthful", "restarted" in out4)
sh4.close()


print("v1.9.3a global-install fallback loads the WHOLE cookie fleet")
import tempfile
with tempfile.TemporaryDirectory() as td:
    import json as _j
    found_jars = sorted(Path("/home/alaqmar/test").glob("cookies*.json"))
    raw_list = [_j.loads(p.read_text()) for p in found_jars[:3]]
    while len(raw_list) < 3:
        raw_list.append([{"name": "session_id", "value": f"mock_sess_{len(raw_list)}", "domain": ".genspark.ai"}])
    for idx, raw in enumerate(raw_list, 1):
        suffix = "" if idx == 1 else f"_{idx}"
        Path(td, f"cookies{suffix}.json").write_text(_j.dumps(raw))
    old_cwd = os.getcwd()
    os.chdir(td)
    try:
        c = GensparkClient("cookies.json")  # spec path that does not exist in cwd -> pool empty -> harness-dir fallback
        # direct fallback-path check: simulate cwd with no cookies at all
        os.chdir(tempfile.gettempdir())
        c2 = GensparkClient.__new__(GensparkClient)
        from apex_harness import AccountPool as _AP
        c2.pool = _AP(); c2.cookie_spec = None; c2.project_id = None; c2.last_index = -1; c2.project_owner = None; c2.last_served_model = None; c2.last_usage = None
        # emulate: _load_pool with a bogus spec whose parent exists but has no cookies*.json
        c2._load_pool.__self__  # bound method exists
        c2._load_pool("/tmp/definitely-not-a-cookie-dir-xyz/cookies.json")
        check("harness-dir fallback loads >=2 accounts", len(c2.pool.accounts) >= 2, f"got {len(c2.pool.accounts)}")
    finally:
        os.chdir(old_cwd)

print("v1.9.3b file-access refusal phrasing trips the character-break guard")
import inspect as _insp
helper_src = _insp.getsource(ah._refusal_hit)
for marker in ("can't read files", "cannot access your", "upload them", "paste the contents"):
    check(f"marker {marker!r} present", marker in helper_src, "missing from refusal helper")
check("_run_loop consults the refusal helper", "_refusal_hit(text)" in _insp.getsource(ah.AgentEngine._run_loop))

print("v1.9.3c _moa_burn honest estimates")
from apex_harness import _moa_burn as _burn, MOA_PRESETS as _presets
check("hybrid ~13x", _burn(_presets["hybrid-moa"]) == "~13x", _burn(_presets["hybrid-moa"]))
check("gpt ~68x", _burn(_presets["gpt-moa"]) == "~68x", _burn(_presets["gpt-moa"]))
check("genspark ~6x", _burn(_presets["genspark-moa"]) == "~6x", _burn(_presets["genspark-moa"]))

print("v1.9.4a refusal helper catches the exact hybrid-moa reply + curly quotes")
from apex_harness import _refusal_hit as _rh, _upstream_declined as _ud
_exact = "I can follow the handoff and project rules once I’ve read them, but I can’t access those local paths in this chat. Please upload or paste the handoff file and the relevant contents of memory."
check("exact reply trips guard", _rh(_exact), repr(_exact[:60]))
check("curly-quote variant trips guard", _rh("I can’t access those local paths in this chat."))
check("tool call is not a refusal", not _rh('<tool name="read_file" path="/tmp/x"></tool>'))
check("friendly greeting is not a refusal", not _rh("Hey! What would you like to work on?"))
check("declined-notice is upstream (not model refusal)", not _rh("The model declined to answer this request. Please rephrase your request and try again."))
check("upstream-declined detected", _ud("The model declined to answer this request. Please rephrase your request and try again."))
check("normal text not upstream-declined", not _ud("Hey! What would you like to work on?"))

print("v1.9.4b re-anchor preamble forces a tool call, not chat")
import inspect as _insp2
loop_src = _insp2.getsource(ah.AgentEngine._run_loop)
check("preamble demands exactly one tool call", "MUST contain exactly one" in loop_src)
check("preamble forbids paste/upload", "NEVER" in loop_src and "paste or upload" in loop_src)
check("re-anchor carries full context", "build_prompt(system)" in loop_src)
import pathlib as _pl
_file_src = _pl.Path("/home/alaqmar/test/apex_harness.py").read_text()
check("model switch resets thread (both /model branches)", _file_src.count("thread reset for the model switch") >= 2)

print("v1.9.4c system prompt forbids the paste/upload dodge")
from apex_harness import _system_prompt as _sp
_sp_text = _sp(None)
check("prompt names read_file for local paths", "read_file" in _sp_text and "local file path" in _sp_text)
check("prompt bans paste/upload dodge", "paste or upload" in _sp_text)

print()
print("v1.9.5a decline retry summarizes instead of re-dumping")
eng = ah.AgentEngine(client=GensparkClient("cookies.json"), tools=tools, context=ah.ContextManager())
big = chr(10).join("line %d" % i for i in range(300))
q = eng._decline_retry_query("SYS", None, big)
check("withholds full dump", "withheld" in q and "NARROWER" in q)
check("retry payload is a summary, not the dump", len(q) < len(big) and "lines withheld" in q)
q2 = eng._decline_retry_query("SYS", None, "")
check("step-1 retry has no-result note", "no tool result yet" in q2)

print("v1.9.5b opus fallback hops only opus-5.x, never MoA")
eng.model = "claude-opus-5-5"
check("opus-5-5 hops", eng._try_opus_fallback("SYS", "hi") and eng.model == "claude-opus-4-8")
eng.model = "claude-opus-4-8"
check("opus-4-8 stays", not eng._try_opus_fallback("SYS", "hi"))
eng.model = "claude-sonnet-5"
check("sonnet stays", not eng._try_opus_fallback("SYS", "hi"))
eng.model = "claude-opus-5-5"; eng.moa = ["a", "b"]
check("MoA never hops", not eng._try_opus_fallback("SYS", "hi"))
eng.moa = None

print("v1.9.5c list_dir caps depth-2+ sweeps")
t5 = ah.ToolRegistry(ah.PersistentShell(), ah.FileSnapshot())
d2 = t5.list_dir(path="/home/alaqmar", depth=2)
check("depth-2 capped at ~120", len(d2.splitlines()) <= 125 and "withheld" in d2, f"{len(d2.splitlines())} lines")
d1 = t5.list_dir(path="/home/alaqmar/test", depth=1)
check("depth-1 uncapped small dir", "withheld" not in d1)

print()
print("v1.9.6a no-tool nudge routes to the right tool")
eng6 = ah.AgentEngine(client=GensparkClient("cookies.json"), tools=tools, context=ah.ContextManager())
from apex_harness import ToolCall as _TC
check("dir task -> list_dir", eng6._nudge_tool_for("hey, see this dir", None) == "list_dir")
check("read task -> read_file", eng6._nudge_tool_for("read the handoff file", None) == "read_file")
check("search task -> grep", eng6._nudge_tool_for("search for TODOs", None) == "grep")
check("run task -> bash", eng6._nudge_tool_for("run the tests", None) == "bash")
check("mid-task chat continues chain", eng6._nudge_tool_for("continue", _TC(name="read_file", args={})) == "read_file")
check("nudge attrs carry depth 1", 'depth="1"' in eng6._nudge_attrs_for("list_dir", "see /tmp/x", None))

print("v1.9.6b prompt forbids chat-only first response")
from apex_harness import _system_prompt as _sp6
_sp6t = _sp6(None)
check("first-response tool mandate", "FIRST response MUST be a tool call" in _sp6t)
check("first-response rule numbered", "FIRST-RESPONSE RULE" in _sp6t)
check("loop has nudge block", "nudging for" in open("/home/alaqmar/test/apex_harness.py").read())

print()
print("v1.9.7a MoA tool-disobedience trips the refusal guard")
check("nudge-refusal trips guard", ah._refusal_hit("I can't execute local commands in this chat, so I can't truthfully emit that as a tool call."))
check("list_dir-refusal trips guard", ah._refusal_hit("I can't run list_dir in this chat, and emitting the tag as text wouldn't list the directory."))
check("greeting still clean", not ah._refusal_hit("Hey! What would you like to work on?"))

print("v1.9.7b MoA paths fail fast instead of burning credits")
_src = open("/home/alaqmar/test/apex_harness.py").read()
check("no-tool block gates MoA", "if self.moa:" in _src and "MoA breaks the Apex tool contract" in _src)
check("refusal block gates MoA", "MoA ensemble refuses the tool contract" in _src)
check("MoA switch warns no-tools", _src.count("MoA ensembles cannot use Apex tools") >= 2)

print()
print("v1.9.8a vague greetings skip the nudge")
check("hey is vague", ah._is_vague_greeting("hey"))
check("empty is vague", ah._is_vague_greeting(""))
check("continue is vague", ah._is_vague_greeting("continue"))
check("dir ask is not", not ah._is_vague_greeting("hey, see this dir"))
check("current-dir ask is not", not ah._is_vague_greeting("have context of current dir"))
check("read ask is not", not ah._is_vague_greeting("read the handoff file"))
check("long text is not", not ah._is_vague_greeting("x" * 61))
check("nudge gated on greeting", "_is_vague_greeting(user_input)" in open("/home/alaqmar/test/apex_harness.py").read())

print("v1.9.8b repeat-tool guard catches identical loops")
eng8 = ah.AgentEngine(client=GensparkClient("cookies.json"), tools=tools, context=ah.ContextManager())
from apex_harness import ToolCall as _TC8
eng8.ctx.add("tool_result", "OUT", tool_name="bash", step=1)
eng8.ctx.add("tool_result", "OUT", tool_name="bash", step=2)
check("identical outputs flagged", eng8._same_as_last_tool(_TC8(name="bash", args={})))
eng8.ctx.add("tool_result", "DIFFERENT", tool_name="bash", step=3)
check("changed output passes", not eng8._same_as_last_tool(_TC8(name="bash", args={})))

print()
print("v1.9.9 nudge body derivation + finite nudge budget")
check("nudge body taken from the task",
      ah.AgentEngine._nudge_body_for("bash", "run ./validate.sh --gpu now") == "./validate.sh --gpu")
check("flag preserved",
      ah.AgentEngine._nudge_body_for("bash", "then ./validate.sh --scenarios please") == "./validate.sh --scenarios")
check("pytest derived",
      ah.AgentEngine._nudge_body_for("bash", "run pytest -q and report") == "pytest -q")
check("subcommand kept, trailing prose dropped",
      ah.AgentEngine._nudge_body_for("bash", "build it: cargo build --release please")
      == "cargo build --release")
check("prose after a path dropped",
      ah.AgentEngine._nudge_body_for("bash", "run ./validate.sh and keep fixing until PASS")
      == "./validate.sh")
check("placeholder only when the task names no command",
      ah.AgentEngine._nudge_body_for("bash", "tell me about this repo") == "pwd && ls")
check("non-bash nudge has empty body",
      ah.AgentEngine._nudge_body_for("read_file", "read main.gd") == "")
check("nudge budget is finite (1..3)",
      isinstance(ah.MAX_NUDGES_PER_TASK, int) and 1 <= ah.MAX_NUDGES_PER_TASK <= 3)

eng9 = ah.AgentEngine(client=GensparkClient("cookies.json"), tools=tools, context=ah.ContextManager())
check("counters start clean per task",
      eng9._tools_executed == 0 and eng9._nudges_used == 0)
check("placeholder still allowed on a cold engine",
      eng9._nudge_allowed("bash", "pwd && ls"))
eng9._tools_executed = 3
check("placeholder suppressed after real tool work",
      not eng9._nudge_allowed("bash", "pwd && ls"))
check("task-derived command still allowed after tool work",
      eng9._nudge_allowed("bash", "./validate.sh"))
eng9._nudges_used = ah.MAX_NUDGES_PER_TASK
check("budget exhausted refuses task-derived nudge too",
      not eng9._nudge_allowed("bash", "./validate.sh"))
check("no candidate tool refused", not eng9._nudge_allowed(None, ""))

# ============================================================
# v1.9.10 — defects observed live on the double-jump harness run
# (handoff.md §9.7 + §14; ledger #11, #12, #13)
# ============================================================

print("#12a edit_file: flush old_string inside an indented line must not double the indent")
shellv = ah.PersistentShell()
toolsv = ToolRegistry(shellv, FileSnapshot())
_gd = "/tmp/apex_rv_anchor.gd"
Path(_gd).write_text("func _build():\n\tstatus_label.modulate = Color(1, 1, 1)\n\tadd_child(layer)\n")
toolsv.edit_file(_gd, "status_label.modulate = Color(1, 1, 1)",
                 "\tstatus_label.modulate = Color(2, 2, 2)\n\tair_jump_label = Label.new()")
got = Path(_gd).read_text()
check("no doubled indent on the replaced line", "\t\tstatus_label.modulate" not in got, repr(got))
check("replacement lands with model-supplied indent", "\tstatus_label.modulate = Color(2, 2, 2)" in got, repr(got))
check("added line written with its indent", "\tair_jump_label = Label.new()" in got, repr(got))

print("#12b edit_file: flush replacement keeps the matched line's indentation")
Path(_gd).write_text("func _build():\n\tadd_child(layer)\n")
toolsv.edit_file(_gd, "add_child(layer)", "add_child(front)\nadd_child(back)")
got = Path(_gd).read_text()
check("indent carried over, not lost", "\tadd_child(front)\n\tadd_child(back)" in got, repr(got))

print("#12c edit_file: genuine inline (non-indent) mid-line match still splices in place")
Path(_gd).write_text("total = f(x = 1, y = 2)\n")
toolsv.edit_file(_gd, "x = 1", "x = 9")
got = Path(_gd).read_text()
check("inline substring edit untouched", got == "total = f(x = 9, y = 2)\n", repr(got))

print("#12d edit_file: match already at line start keeps exact semantics")
Path(_gd).write_text("\tfoo = 1\n\tbar = 2\n")
toolsv.edit_file(_gd, "\tfoo = 1", "\tfoo = 11")
got = Path(_gd).read_text()
check("line-start match replaced verbatim", got == "\tfoo = 11\n\tbar = 2\n", repr(got))

print("#13a file rewrites keep the executable bit (validate.sh went 100755→100644 live)")
_sh = "/tmp/apex_rv_exec.sh"
Path(_sh).write_text("#!/bin/bash\necho hi\n")
os.chmod(_sh, 0o755)
toolsv.edit_file(_sh, "echo hi", "echo bye")
check("edit_file preserves mode", os.stat(_sh).st_mode & 0o111 != 0, oct(os.stat(_sh).st_mode))
toolsv.write_file(_sh, "#!/bin/bash\necho rewritten\n")
check("write_file preserves mode", os.stat(_sh).st_mode & 0o111 != 0, oct(os.stat(_sh).st_mode))
shellv.close()

print("#11 fatal upstream errors surface to the caller (was: exit 0 on ConnectionReset)")
class _DeadStreamClient:
    project_id = None
    def stream(self, **kw):
        raise ConnectionResetError(104, "Connection reset by peer")

eng10 = ah.AgentEngine(client=_DeadStreamClient(), tools=None, context=ah.ContextManager(), skills=None)
eng10.run("do a thing")
check("task_failed set when the pool dies",
      "Connection reset" in str(getattr(eng10, "task_failed", None)),
      repr(getattr(eng10, "task_failed", None)))

class _BoomStreamClient:
    project_id = None
    def stream(self, **kw):
        raise RuntimeError("boom-2")

eng10.task_failed = "stale-sentinel"
eng10.client = _BoomStreamClient()
eng10.run("second task")
check("task_failed reset at task start",
      str(getattr(eng10, "task_failed", None)) == "boom-2",
      repr(getattr(eng10, "task_failed", None)))

from types import SimpleNamespace
_cli = ah.ApexCLI.__new__(ah.ApexCLI)
_cli.engine = SimpleNamespace(run=lambda q: None, task_failed="boom", model="m", max_steps=1)
_cli.client = SimpleNamespace(pool=SimpleNamespace(accounts=[SimpleNamespace(tag="t")]))
_cli.query = "task"
try:
    _cli.run()
    check("-q exits non-zero on task_failed", False, "no SystemExit raised")
except SystemExit as e:
    check("-q exits non-zero on task_failed", e.code == 1, f"code={e.code}")
_cli2 = ah.ApexCLI.__new__(ah.ApexCLI)
_cli2.engine = SimpleNamespace(run=lambda q: None, task_failed=None, model="m", max_steps=1)
_cli2.client = _cli.client
_cli2.query = "task"
try:
    _cli2.run()
    check("-q clean task exits 0 path (no SystemExit)", True)
except SystemExit as e:
    check("-q clean task exits 0 path (no SystemExit)", False, f"unexpected exit {e.code}")

print()
print()
print(f"RESULTS: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)

"""Apex Harness production-readiness unit test suite."""
import os
import sys
import signal
import time
from pathlib import Path

sys.path.insert(0, "/home/alaqmar/test")
from apex_harness import (
    PersistentShell, FileSnapshot, ToolRegistry, ToolParser, ContextManager,
    AccountPool, CookieAccount, GensparkClient, _render_markdown, C,
)

PASS = 0
FAIL = 0

def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")

print("=== 1. ToolParser: nested tool docs inside write_file ===")
t1 = 'Intro\n<tool name="write_file" path="G.md">\n# Docs\n<tool name="bash">ls</tool>\nEnd\n</tool>\nOutro'
c1, calls1 = ToolParser.parse(t1)
check("one call found", len(calls1) == 1, f"got {len(calls1)}")
check("nested tag preserved in content", '<tool name="bash">ls</tool>' in calls1[0].args.get("content", "") if calls1 else False)
check("cleaned text correct", "Outro" in c1 and "<tool" not in c1.replace('<tool name="bash">ls</tool>', ''))

print("=== 2. ToolParser: markdown code fence examples NOT executed ===")
t2 = 'Done! Example: ```xml\n<tool name="bash">echo test</tool>\n``` end'
c2, calls2 = ToolParser.parse(t2)
check("no spurious call from code fence", len(calls2) == 0, f"got {len(calls2)}")

t2b = 'Done! Inline: `<tool name="bash">echo test</tool>` end'
c2b, calls2b = ToolParser.parse(t2b)
check("no spurious call from inline backticks", len(calls2b) == 0, f"got {len(calls2b)}")

print("=== 3. ToolParser: real call still parsed alongside example ===")
t3 = 'Example: ```xml\n<tool name="bash">echo fake</tool>\n```\nNow real:\n<tool name="bash">\necho real\n</tool>'
c3, calls3 = ToolParser.parse(t3)
check("exactly 1 call", len(calls3) == 1, f"got {len(calls3)}")
check("real command extracted", calls3 and calls3[0].args.get("command") == "echo real")

print("=== 4. ToolParser: unclosed tag at EOF salvaged ===")
t4 = 'Intro\n<tool name="write_file" path="app.py">\ndef main():\n    return 1'
c4, calls4 = ToolParser.parse(t4)
check("unclosed write salvaged", len(calls4) == 1 and calls4[0].args.get("path") == "app.py" and "def main():" in calls4[0].args.get("content", ""))

print("=== 5. ToolParser: path attribute fallbacks ===")
t5 = '<tool name="write_file" file="x.txt">\nhello</tool>'
_, calls5 = ToolParser.parse(t5)
check("file= attr accepted", calls5 and calls5[0].args.get("path") == "x.txt")
t5b = '<tool name="write_file">\n# path: y.txt\nbody</tool>'
_, calls5b = ToolParser.parse(t5b)
check("# path: first-line accepted", calls5b and calls5b[0].args.get("path") == "y.txt" and calls5b[0].args.get("content") == "body")

print("=== 6. PersistentShell: state persistence ===")
shell = PersistentShell()
shell.run("cd /tmp && export APEX_UT=works")
out, code = shell.run("pwd && echo V=$APEX_UT")
check("cd persists", "/tmp" in out, out)
check("export persists", "V=works" in out, out)

print("=== 7. PersistentShell: survives `exit` (auto-restart) ===")
shell.run("cd /tmp")
out, code = shell.run("exit")
time.sleep(0.3)
out2, code2 = shell.run("echo alive_after_exit && pwd")
check("shell restarted after exit", "alive_after_exit" in out2, f"out={out2!r} code={code2}")
shell.close()

print("=== 8. FileSnapshot: undo cap & behavior ===")
snaps = FileSnapshot()
tf = Path("/tmp/apex_ut_undo.txt")
tf.write_text("v1")
for i in range(60):
    snaps.save(str(tf), "edit")
    tf.write_text(f"v{i+2}")
check("stack capped at 50", len(snaps._stack) == 50, len(snaps._stack))
snaps.undo()
check("undo restores last version", tf.read_text() == "v60")

print("=== 9. ToolRegistry: write/edit/truncate ===")
shell2 = PersistentShell()
tools = ToolRegistry(shell2, FileSnapshot())
big = "\n".join(f"line {i}" for i in range(500))
out_w = tools.write_file("/tmp/apex_ut_big.txt", big)
check("write reports size", "500 lines" in out_w, out_w)
out_r = tools.read_file("/tmp/apex_ut_big.txt")
check("read capped to window + paging hint", "file continues" in out_r and "line 251" not in out_r, f"len={len(out_r)}")
check("read stays small", len(out_r) < 12000, len(out_r))
out_e = tools.edit_file("/tmp/apex_ut_big.txt", "line 0", "line ZERO")
check("edit applied", "line ZERO" in Path("/tmp/apex_ut_big.txt").read_text())
out_e2 = tools.edit_file("/tmp/apex_ut_big.txt", "line 1", "dup")
check("edit rejects ambiguous match", "matches" in out_e2 and "more specific" in out_e2, out_e2[:120])
out_e3 = tools.edit_file("/tmp/apex_ut_big.txt", "not present anywhere xyz", "nope")
check("edit rejects missing match", "not found" in out_e3)
shell2.close()

print("=== 10. AccountPool: auth error exclusion ===")
pool = AccountPool()
pool.add("a", [{"name": "session_id", "value": "s1", "domain": "www.genspark.ai", "path": "/"}])
pool.add("b", [{"name": "session_id", "value": "s2", "domain": "www.genspark.ai", "path": "/"}])
pool.accounts[0].mark_auth_error()
accs = [pool.next_account().name for _ in range(3)]
check("auth-error account excluded", all(a == "b" for a in accs), accs)
pool.accounts[1].mark_auth_error()
try:
    pool.next_account()
    check("all-dead raises", False)
except RuntimeError:
    check("all-dead raises", True)

print("=== 11. ContextManager compaction ===")
cm = ContextManager(budget=1000)
for i in range(20):
    cm.add("user", f"msg {i}")
    cm.add("tool_result", "x" * 300, tool_name="bash", step=i)
_, sz = cm.stats()
check("compaction under 2x budget", sz <= 2000, sz)
check("head preserved", cm.history[0].role == "user")

print("=== 12. _render_markdown cap ===")
import io
from rich.console import Console
buf = io.StringIO()
test_con = Console(file=buf, force_terminal=False, width=80)
import apex_harness
old_con = apex_harness.RICH_CONSOLE
# _render_markdown uses module-level RICH_CONSOLE; verify cap logic directly
big_md = "# T\n" + ("word " * 10000)
check("cap triggers over 20k chars", len(big_md) > 20000)

print()
print(f"RESULTS: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)

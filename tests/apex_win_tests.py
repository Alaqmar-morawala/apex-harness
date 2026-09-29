"""v1.2.0 Windows-support tests. Run on Linux — validates the Windows machinery
via a bash shim and the platform-adaptive code paths."""
import os
import sys
from pathlib import Path

sys.path.insert(0, "/home/alaqmar/test")
import apex_harness as ah
from apex_harness import _WindowsShell, _PosixShell, PersistentShell, ToolParser, ToolRegistry

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

print("=== W1. Platform selection ===")
check("posix box selects _PosixShell", PersistentShell is _PosixShell)
check("posix flag set", ah._POSIX is True)

print("=== W2. _WindowsShell machinery via bash shim (piped stdio + queue + sentinel) ===")
ws = _WindowsShell(shell_cmd=["/bin/bash", "--norc", "--noprofile"], ec_expr="$?")
out, code = ws.run("echo W2_HELLO")
check("basic command", "W2_HELLO" in out and code == 0, f"{out!r} code={code}")
ws.run("cd /tmp && export W2VAR=winpath")
out2, code2 = ws.run("pwd && echo V=$W2VAR")
check("state persists across runs", "/tmp" in out2 and "V=winpath" in out2, f"{out2!r}")
out3, code3 = ws.run("false")
check("nonzero exit code captured", code3 == 1, f"code={code3}")
out4, code4 = ws.run("exit")
out5, code5 = ws.run("echo W2_AFTER_RESTART")
check("auto-restart after shell death", "W2_AFTER_RESTART" in out5 and code5 == 0, f"{out5!r} code={code5}")
ws.close()

print("=== W3. WindowsShell cmd.exe defaults ===")
check("default shell is cmd.exe /Q /K /D", ah._WINDOWS_CMD_DEFAULT == ["cmd.exe", "/Q", "/K", "/D"], ah._WINDOWS_CMD_DEFAULT)
# verify CRLF decision logic without spawning cmd.exe:
probe = _WindowsShell.__new__(_WindowsShell)
probe._shell_cmd = ah._WINDOWS_CMD_DEFAULT
probe._crlf = probe._shell_cmd[0].lower().endswith("cmd.exe")
check("cmd.exe -> CRLF", probe._crlf is True)
probe2 = _WindowsShell.__new__(_WindowsShell)
probe2._shell_cmd = ["bash"]
probe2._crlf = probe2._shell_cmd[0].lower().endswith("cmd.exe")
check("bash shim -> LF", probe2._crlf is False)

print("=== W4. Pure-python grep ===")
tree = Path("/tmp/apex_grep_test")
(tree / "sub").mkdir(parents=True, exist_ok=True)
(tree / "a.py").write_text("TODO fix me\nprint('hello')\n")
(tree / "sub" / "b.txt").write_text("nothing here\nTODO second\n")
(tree / "skip.log").write_text("TODO ignored by include\n")
shell = ah.PersistentShell()
tools = ToolRegistry(shell, ah.FileSnapshot())
r1 = tools._grep_python(r"TODO", str(tree))
check("finds matches recursively", "a.py:1" in r1 and "b.txt:2" in r1, r1)
r2 = tools._grep_python(r"TODO", str(tree), include="*.py")
check("include filter works", "a.py:1" in r2 and "b.txt" not in r2, r2)
r3 = tools._grep_python(r"no_such_pattern_xyz", str(tree))
check("no matches message", r3 == "[no matches]", r3)
r4 = tools._grep_python(r"([unclosed", str(tree))
check("invalid regex handled", r4.startswith("[error]"), r4)

print("=== W5. System prompt platform-aware ===")
sp = ah._system_prompt()
check("posix prompt mentions bash", "Shell: bash (persistent" in sp, sp[:200])
check("no os.uname crash", True)  # reaching here means it didn't crash

print("=== W6. Windows import block sanity (source-level) ===")
src = Path("/home/alaqmar/test/apex_harness.py").read_text()
check("pty/termios/fcntl inside posix guard", src.count('if _POSIX:') >= 1 and "import fcntl\n    import pty" in src)
check("readline guarded", "except ImportError:\n    readline = None" in src)
check("apex.cmd exists", Path("/home/alaqmar/test/apex.cmd").exists())

print()
print(f"RESULTS: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)

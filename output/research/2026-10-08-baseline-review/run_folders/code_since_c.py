"""Tracked code now against the diff each C folder saved: which files' uncommitted changes
differ. Read-only: `git diff HEAD` is printed to memory, nothing is written to the repo."""
import hashlib
import subprocess
import sys

from folders import ALL, REPO

sys.stdout.reconfigure(encoding="utf-8")
LF, CRLF = bytes([10]), bytes([13, 10])


def split(diff):
    out, name, buf = {}, None, []
    for line in diff.split(LF):
        if line.startswith(b"diff --git "):
            if name is not None:
                out[name] = LF.join(buf)
            name, buf = line.split(b" b/", 1)[1].decode("utf-8", "replace"), []
        buf.append(line)
    if name is not None:
        out[name] = LF.join(buf)
    return out


now = subprocess.run(["git", "diff", "HEAD", "--", "prod", "test", "tools", "pytest.ini", "refresh_graph.py"],
                     cwd=str(REPO), capture_output=True).stdout.replace(CRLF, LF)
now_files = split(now)
print(f"tracked code now: files with uncommitted changes {len(now_files)}   sha256 of the diff (LF) {hashlib.sha256(now).hexdigest()[:16]}")
for name in ("C.lucA", "D.v4_10", "C.vecAE", "C.luc", "C.vec"):
    f = sorted(ALL[name].glob("*.diff"))[0]
    then = split(f.read_bytes().replace(CRLF, LF))
    changed = sorted(k for k in set(then) | set(now_files) if then.get(k) != now_files.get(k))
    print(f"{name} {f.name}: files in its diff {len(then)}; files whose uncommitted change differs from now: {len(changed)}")
    for k in changed:
        a, b = then.get(k), now_files.get(k)
        state = "only now" if a is None else "only then" if b is None else "differs"
        c_then = 0 if a is None else a.count(b"cost_usd")
        c_now = 0 if b is None else b.count(b"cost_usd")
        print(f"      {k:<44} {state:<9} 'cost_usd' in its diff then {c_then}, now {c_now}")
for path in ("prod/harness/capture.py",):
    p = REPO / path
    print(f"untracked {path}: sha256 now {hashlib.sha256(p.read_bytes()).hexdigest()[:16]}   'cost_usd' occurrences now {p.read_bytes().count(b'cost_usd')}")

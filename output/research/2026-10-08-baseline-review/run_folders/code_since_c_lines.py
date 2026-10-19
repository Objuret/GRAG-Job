"""The added lines ('+' lines of the uncommitted diff) that the code has now and the newest
proof folder's saved diff has not, and the reverse, for the files that differ. Code lines only."""
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
                out[name] = buf
            name, buf = line.split(b" b/", 1)[1].decode("utf-8", "replace"), []
        buf.append(line)
    if name is not None:
        out[name] = buf
    return out


def plus(lines):
    return [x[1:].decode("utf-8", "replace").rstrip() for x in lines if x.startswith(b"+") and not x.startswith(b"+++")]


now = split(subprocess.run(["git", "diff", "HEAD", "--", "prod", "test", "tools", "pytest.ini", "refresh_graph.py"],
                           cwd=str(REPO), capture_output=True).stdout.replace(CRLF, LF))
ref = sys.argv[1] if len(sys.argv) > 1 else "C.vec"
then = split(sorted(ALL[ref].glob("*.diff"))[0].read_bytes().replace(CRLF, LF))
for k in sorted(set(then) | set(now)):
    if then.get(k) == now.get(k):
        continue
    a, b = plus(then.get(k, [])), plus(now.get(k, []))
    only_then = [x for x in a if x not in b and x.strip()]
    only_now = [x for x in b if x not in a and x.strip()]
    print(f"=== {k}: added lines only in {ref}'s diff {len(only_then)}, only now {len(only_now)}")
    for x in only_then:
        print("   then | " + x[:170])
    for x in only_now:
        print("   now  | " + x[:170])

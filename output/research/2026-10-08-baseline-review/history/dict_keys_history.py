"""String keys of dict literals in harness files, per git version: first seen, last seen, removed by.

For each file family (a list of paths the file lived under), every commit on any ref that touched it
is parsed with ast; the string keys of every dict literal and the string first-arguments of
`.get("…")`/subscripts are collected. A key written into a row or a manifest shows up here even
when it is not a dataclass field (e.g. "answered_at", "graph_census_sha256").

    python dict_keys_history.py            # the families below
Prints only; reads git and the working tree.
"""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

REPO = Path(r"C:\Coding\exjobbet\GRAG-Job")
FAMILIES = {
    "orchestrator": ["v3/orchestrator.py", "prod/harness/orchestrator.py"],
    "provenance": ["v3/provenance.py", "prod/harness/provenance.py"],
    "chat lane (nim.py → chat.py)": ["v3/nim.py", "prod/harness/nim.py", "prod/harness/chat.py"],
    "eval/ragas": ["v3/eval/ragas.py", "prod/eval/ragas.py"],
    "run.py": ["v3/run.py", "prod/run.py"],
    "arm lucene": ["v3/pipelines/lucene.py", "prod/arms/lucene.py"],
    "arm vector": ["v3/pipelines/vector.py", "prod/arms/vector.py"],
    "char_budget": ["v3/char_budget.py", "prod/harness/char_budget.py"],
    "capture": ["prod/harness/capture.py"],
    "embed": ["prod/harness/embed.py"],
}


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout


def dict_keys(source: str) -> set[str]:
    out: set[str] = set()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return out
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for k in node.keys:
                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                    out.add(k.value)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr in ("update", "setdefault") :
            for kw in node.keywords:
                if kw.arg:
                    out.add(kw.arg)
    return out


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for family, paths in FAMILIES.items():
        commits = []
        for path in paths:
            for line in git("log", "--all", "--format=%H|%cI|%s", "--", path).splitlines():
                sha, date, subject = line.split("|", 2)
                commits.append((date, sha, subject, path))
        commits.sort()
        first, last, removed = {}, {}, {}
        prev: set[str] = set()
        prev_path = None
        for date, sha, subject, path in commits:
            src = git("show", f"{sha}:{path}")
            if not src.strip():
                # the file left this path in this commit (moved or deleted); do not count as removal
                continue
            now = dict_keys(src)
            for k in now:
                first.setdefault(k, (date[:10], sha[:7]))
                last[k] = (date[:10], sha[:7])
                removed.pop(k, None)
            for k in prev - now:
                removed[k] = (date[:10], sha[:7])
            prev, prev_path = now, path
        wt: set[str] = set()
        for path in paths:
            p = REPO / path
            if p.is_file():
                wt |= dict_keys(p.read_text(encoding="utf-8"))
        print(f"\n=== {family}: {len(commits)} versions in git; working-tree file "
              f"{'present' if wt else 'ABSENT'}")
        print("key | first commit | last commit containing it | commit that dropped it | in working tree")
        for k in sorted(set(first) | wt, key=lambda x: (first.get(x, ('9999', ''))[0], x)):
            f = first.get(k)
            l = last.get(k)
            r = removed.get(k)
            print(f"{k} | {f[1] + ' ' + f[0] if f else 'working tree only'} | "
                  f"{l[1] + ' ' + l[0] if l else '—'} | {r[1] + ' ' + r[0] if r else ''} | "
                  f"{'yes' if k in wt else 'NO'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

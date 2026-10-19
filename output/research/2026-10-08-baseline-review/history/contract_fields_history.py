"""Every field any version of the harness contract ever had, with first and last commit.

Walks every commit (all refs) that touched a contract file (v3/contract.py, prod/harness/contract.py,
plus any path given with --path), parses each version with ast, and lists dataclass / NamedTuple /
TypedDict style class fields (annotated assignments in class bodies). For versions that only sketch
the shape in comments (the first v3/contract.py), the comment lines are printed as-is.

Prints: per (class, field): first commit (date), last commit where present (date), and whether the
working tree has it. Reads git only; writes nothing but stdout.
"""
from __future__ import annotations

import argparse
import ast
import subprocess
import sys
from collections import OrderedDict
from pathlib import Path

REPO = Path(r"C:\Coding\exjobbet\GRAG-Job")
DEFAULT_PATHS = ["v3/contract.py", "prod/harness/contract.py"]


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout


def class_fields(source: str) -> "OrderedDict[tuple[str, str], str]":
    out: "OrderedDict[tuple[str, str], str]" = OrderedDict()
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        print(f"    (does not parse: {exc})")
        return out
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                ann = ast.unparse(item.annotation)
                out[(node.name, item.target.id)] = ann
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", action="append", default=[])
    ap.add_argument("--show-versions", action="store_true", help="print each commit's field list")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    paths = args.path or DEFAULT_PATHS

    commits: list[tuple[str, str, str, str]] = []  # (date_iso, sha, subject, path)
    for path in paths:
        log = git("log", "--all", "--format=%H|%cI|%s", "--", path)
        for line in log.splitlines():
            sha, date, subject = line.split("|", 2)
            commits.append((date, sha, subject, path))
    commits.sort()

    first: dict[tuple[str, str], tuple[str, str]] = {}
    last: dict[tuple[str, str], tuple[str, str]] = {}
    ann: dict[tuple[str, str], str] = {}
    order: list[tuple[str, str]] = []
    prev: set[tuple[str, str]] = set()
    removed_at: dict[tuple[str, str], tuple[str, str, str]] = {}
    for date, sha, subject, path in commits:
        src = git("show", f"{sha}:{path}")
        if not src.strip():
            print(f"{date[:10]} {sha[:7]} {path}: (file absent / deleted) — {subject}")
            for key in prev:
                removed_at.setdefault(key, (date[:10], sha[:7], subject))
            prev = set()
            continue
        fields = class_fields(src)
        now = set(fields)
        for key in fields:
            if key not in first:
                first[key] = (date[:10], sha[:7])
                order.append(key)
            last[key] = (date[:10], sha[:7])
            ann[key] = fields[key]
            removed_at.pop(key, None)
        for key in prev - now:
            removed_at[key] = (date[:10], sha[:7], subject)
        added = [k for k in fields if k not in prev]
        gone = sorted(prev - now)
        print(f"{date[:10]} {sha[:7]} {path}: {len(fields)} fields — {subject}")
        if added:
            print("    + " + ", ".join(f"{c}.{f}" for c, f in added))
        if gone:
            print("    - " + ", ".join(f"{c}.{f}" for c, f in gone))
        if not fields:
            # the earliest version sketches shapes in comments only
            for ln in src.splitlines():
                if ln.strip().startswith("#"):
                    print("      " + ln.rstrip())
        if args.show_versions:
            for (c, f), a in fields.items():
                print(f"      {c}.{f}: {a}")
        prev = now

    # the working tree
    wt_fields: "OrderedDict[tuple[str, str], str]" = OrderedDict()
    for path in paths:
        p = REPO / path
        if p.is_file():
            wt_fields.update(class_fields(p.read_text(encoding="utf-8")))
    print()
    print("=== field | type (last seen) | first commit | last commit | removed by | in working tree")
    for key in order + [k for k in wt_fields if k not in first]:
        c, f = key
        fs = first.get(key, ("—", "working tree only"))
        ls = last.get(key, ("—", "—"))
        rm = removed_at.get(key)
        in_wt = "yes" if key in wt_fields else "NO"
        rm_s = f"{rm[1]} {rm[0]}" if rm else ""
        print(f"{c}.{f} | {ann.get(key) or wt_fields.get(key)} | {fs[1]} {fs[0]} | {ls[1]} {ls[0]} | {rm_s} | {in_wt}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""The inventory as compact tables, one per file kind, columns = folder groups.

Cell code per folder: Y = present, not null and not zero in every row; 0 = present, zero /
empty / false in every row; n = present, null in every row; - = key path absent;
otherwise nz=k (rows not zero) or nn=k (rows not null) of the folder's n rows.
A group cell lists its folders in the order of the header. Subtrees named in COLLAPSE are
shown as one line with their leaf names.
"""
import json
import sys
from pathlib import Path

from folders import GROUPS

sys.stdout.reconfigure(encoding="utf-8")
inv = json.loads((Path(__file__).resolve().parent / "inventory.json").read_text(encoding="utf-8"))

COLLAPSE = {
    "arm_outputs.jsonl": ["calls[].attempts[]", "calls[].envelope", "calls[].schema", "calls[].usage",
                          "meta.diagnostics", "meta.interpreter", "meta.provenance", "meta.scope",
                          "meta.chunk_ids"],
    "run_manifest.json": ["legs[].code_state", "legs[].index", "legs[].lane", "legs[].flags",
                          "legs[].code_version", "code_state.untracked_sha256", "generator.schema",
                          "generator.payload", "index.cache_cost_note", "lane", "graph",
                          "retrieval_flags", "env", "flags", "environment.packages"],
    "eval_manifest.json": ["judge_legs[].settings", "judge_settings.lane", "judge_settings.embedding",
                           "judge_legs[].usage", "judge_usage"],
    "eval_results.jsonl": [],
    "eval_calls.jsonl": ["attempts[]", "envelope", "usage"],
}


def kind_of(fname):
    return "code.*.diff" if fname.startswith("code.") and fname.endswith(".diff") else fname


def rec_of(name, kind):
    for fname, rec in inv[name].items():
        if kind_of(fname) == kind:
            return rec
    return None


def code(name, kind, path):
    rec = rec_of(name, kind)
    if rec is None or rec["n"] is None:
        return "x"
    a = rec["paths"].get(path)
    if a is None:
        return "-"
    n, p, nn, nz = rec["n"], a["present"], a["nonnull"], a["nonzero"]
    if p == nn == nz == n:
        return "Y"
    if p == n and nn == 0:
        return "n"
    if p == n and nn == n and nz == 0:
        return "0"
    if p == n and nn == n:
        return f"nz={nz}"
    if p == n:
        return f"nn={nn}"
    return f"p={p},nn={nn},nz={nz}"


def is_leaf(path, allp):
    return not any(q != path and (q.startswith(path + ".") or q.startswith(path + "[")) for q in allp)


def table(kind):
    names = [n for g in GROUPS.values() for n in g if rec_of(n, kind) is not None]
    allp = []
    for n in names:
        for p in rec_of(n, kind)["paths"]:
            if p not in allp:
                allp.append(p)
    types = {}
    for n in names:
        for p, a in rec_of(n, kind)["paths"].items():
            types.setdefault(p, set()).update(a["types"])
    heads = COLLAPSE.get(kind, [])
    print()
    print(f"### {kind}")
    ns = {n: rec_of(n, kind)["n"] for n in names}
    print("rows per folder: " + ", ".join(f"{n} {ns[n]}" for n in names))
    hdr = []
    for g, d in GROUPS.items():
        cols = [n.split(".", 1)[1] for n in d if n in names]
        if cols:
            hdr.append(f"{g} ({' '.join(cols)})")
    print("| key path | type | " + " | ".join(hdr) + " |")
    print("|---|---|" + "---|" * len(hdr))
    done = set()
    for p in sorted(allp):
        head = next((h for h in heads if p == h or p.startswith(h + ".") or p.startswith(h + "[")), None)
        if head is not None:
            if head in done:
                continue
            done.add(head)
            sub = [q for q in sorted(allp) if (q.startswith(head + ".") or q.startswith(head + "[")) and is_leaf(q, allp)]
            cells = []
            for g, d in GROUPS.items():
                cols = [n for n in d if n in names]
                if not cols:
                    continue
                bits = []
                for n in cols:
                    have = [q for q in sub if code(n, kind, q) not in ("-", "x")]
                    yes = [q for q in have if code(n, kind, q) == "Y"]
                    bits.append("-" if not have else f"{len(have)}({len(yes)}Y)")
                cells.append(" ".join(bits))
            tails = ", ".join(q[len(head):].lstrip(".") for q in sub)
            print(f"| `{head}` + {len(sub)} leaves: {tails} | | " + " | ".join(cells) + " |")
            continue
        if not is_leaf(p, allp):
            continue
        cells = []
        for g, d in GROUPS.items():
            cols = [n for n in d if n in names]
            if cols:
                cells.append(" ".join(code(n, kind, p) for n in cols))
        print(f"| `{p}` | {'/'.join(sorted(types[p]))} | " + " | ".join(cells) + " |")


for kind in ("arm_outputs.jsonl", "run_manifest.json", "eval_results.jsonl", "eval_manifest.json", "eval_calls.jsonl"):
    table(kind)

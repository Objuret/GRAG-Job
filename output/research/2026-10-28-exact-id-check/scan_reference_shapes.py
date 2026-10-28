"""Scan the 815 reference answers for machine-identifier-like tokens. Prints only generalized
shapes and counts: every alphabetic token outside a short list of structural words becomes its
class, every digit or hex run its class. Nothing of a reference is printed."""
import json
import re
from collections import Counter, defaultdict

REPO = "C:/Coding/exjobbet/GRAG-Job"
q = {}
for line in open(f"{REPO}/data/questions.jsonl", encoding="utf-8"):
    if line.strip():
        r = json.loads(line)
        q[r["id"]] = r
ids = [json.loads(l)["id"] for f in ("gold100", "answerable715")
       for l in open(f"{REPO}/data/{f}.jsonl", encoding="utf-8") if l.strip()]

KEEP = {"eid", "EMP", "CUST", "https", "http", "www", "github", "com", "pull", "sf", "internal",
        "slack", "archives", "docs", "demo", "salesforce", "org", "io", "net", "ai", "pulls",
        "issues", "commit", "blob", "tree"}
SPLIT = re.compile(r"([^A-Za-z0-9]+)")


def tok_class(t):
    if t in KEEP:
        return t
    if re.fullmatch(r"\d+", t):
        return r"\d{%d}" % len(t)
    if re.fullmatch(r"[0-9a-f]+", t) and re.search(r"\d", t):
        return "[0-9a-f]{%d}" % len(t)
    if re.fullmatch(r"[a-z]+", t):
        return "[a-z]+"
    if re.fullmatch(r"[A-Z]+", t):
        return "[A-Z]+"
    if re.fullmatch(r"[A-Za-z]+", t):
        return "[A-Za-z]+"
    return "[A-Za-z0-9]+"


def shape(s):
    parts = SPLIT.split(s)
    out = []
    for i, p in enumerate(parts):
        if i % 2 == 1:
            out.append(re.escape(p))
        elif p:
            out.append(tok_class(p))
    return "".join(out)


# a candidate: a whitespace token that holds a digit together with _ - / . : , or starts with
# http or www, or holds two or more underscores
CAND = re.compile(r"\S+")
shapes_tok = Counter()
shapes_refs = defaultdict(set)
by_type_with_cand = Counter()
by_type = Counter()
for qid in ids:
    r = q[qid]
    ref = " ".join(r["ground_truth"])
    by_type[r["type"]] += 1
    seen_any = False
    for m in CAND.finditer(ref):
        t = m.group(0).strip(".,;:!?()[]{}'\"`<>*")
        if not t:
            continue
        is_cand = (t.lower().startswith(("http", "www.")) or t.count("_") >= 2
                   or (re.search(r"\d", t) and re.search(r"[_\-/.:]", t) and re.search(r"[A-Za-z]", t)))
        if not is_cand:
            continue
        s = shape(t)
        shapes_tok[s] += 1
        shapes_refs[s].add(qid)
        seen_any = True
    if seen_any:
        by_type_with_cand[r["type"]] += 1

print("references:", len(ids))
print("question type -> references holding a candidate / all:",
      {k: f"{by_type_with_cand[k]}/{v}" for k, v in by_type.items()})
print("candidate tokens:", sum(shapes_tok.values()), "distinct shapes:", len(shapes_tok))
for s, c in shapes_tok.most_common(60):
    print(f"  tokens={c:5d} refs={len(shapes_refs[s]):4d}  {s}")

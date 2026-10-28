"""Extract the identifiers of each reference answer and check them against the corpus.
Writes the per-question identifier lists to a scratch pickle (scratch only, never printed).
Prints only patterns and counts."""
import pickle
import re
from collections import Counter

from common import corpus_identifiers, question_set, questions, reference

OUT = "C:/Users/jocke/AppData/Local/Temp/claude/c--Coding-exjobbet-GRAG-Job/9c164e78-008e-41e9-85f3-58c55027a64c/scratchpad/exact_check/ref_identifiers.pkl"

# the patterns, learned from the corpus formats (s05) and checked on the references (s06)
PATTERNS = {
    "employee id": r"(?<![A-Za-z0-9_])eid_[0-9a-f]{7,8}(?![A-Za-z0-9_])",
    "customer id": r"(?<![A-Za-z0-9_])CUST-\d{4}(?![A-Za-z0-9_])",
    "pull-request login EMP_": r"(?<![A-Za-z0-9_])EMP_\d{7,9}(?![A-Za-z0-9_])",
    "PR link": r"https://github\.com/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+/pull/\d+(?![0-9])",
    "URL (any, trailing .,;:!? cut)": r"https?://[^\s<>\"'\[\]()]+",
    "Slack message id": r"(?<![0-9])\d{8}-\d{1,3}-[0-9a-f]{5,6}(?![0-9a-f])",
    "Slack channel id": r"(?<![A-Za-z0-9_])ch-[A-Za-z0-9_-]*-[0-9a-f]{6}(?![0-9a-f])",
    "PR record id": r"github_com_[A-Za-z0-9_-]+_pull_\d+",
    "transcript record id": r"product_dev_[A-Za-z]+_\d{1,2}(?![0-9])",
    "planning transcript or chat id": r"[A-Za-z]+_planning_\d(?:_chat)?(?![0-9])",
}
TRAIL = re.compile(r"[.,;:!?]+$")
PR_FULL = re.compile(r"https://github\.com/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+/pull/\d+")

qs = questions()
ids = question_set()
refs = {i: reference(qs[i]) for i, _ in ids}

print("patterns: references (of 815) holding at least one match | matches with repeats")
for name, rx in PATTERNS.items():
    c = re.compile(rx)
    n_refs = sum(1 for r in refs.values() if c.search(r))
    n_m = sum(len(c.findall(r)) for r in refs.values())
    n_ci = sum(1 for r in refs.values() if re.search(rx, r, re.I))
    print(f"  {name:32s} refs={n_refs:4d} matches={n_m:5d} (refs case-insensitive={n_ci:4d})   {rx}")

# loose probes for variants the strict patterns would miss
probes = {
    "eid_ followed by any word chars": r"eid_\w+",
    "eid with another separator": r"(?i)\beid[\s:#-]+[0-9a-f]{6,}",
    "github.com without scheme": r"(?<![/A-Za-z0-9.])github\.com/",
    "http:// (not https)": r"http://",
    "www. without scheme": r"(?<![/A-Za-z0-9.])www\.",
    "CUST with other separator": r"(?i)\bcust[\s_#:]+\d{3,}",
    "PR number as #n": r"#\d+",
}
print("\nprobes (counts only):")
strict_eid = re.compile(PATTERNS["employee id"])
for name, rx in probes.items():
    c = re.compile(rx)
    n_m = sum(len(c.findall(r)) for r in refs.values())
    n_refs = sum(1 for r in refs.values() if c.search(r))
    print(f"  {name:34s} refs={n_refs:4d} matches={n_m:5d}   {rx}")
n_eid_loose = sum(len(re.findall(r"eid_\w+", r)) for r in refs.values())
n_eid_strict = sum(len(strict_eid.findall(r)) for r in refs.values())
print("  eid_ tokens not matched by the strict pattern:", n_eid_loose - n_eid_strict)

# the identifiers per question, distinct, with their kind
kinds = corpus_identifiers()
known = {
    "employee id": kinds["employee id"] | kinds["slack user id"] | kinds["pr login"],
    "customer id": kinds["customer id"],
    "PR link": kinds["pr link"],
    "other URL": kinds["url link"] | kinds["document link"] | kinds["pr link"],
}
per_q = {}
repeats = 0
kind_count = Counter()
unknown = Counter()
len_eid = Counter()
for i, _ in ids:
    r = refs[i]
    found = {}
    order = []
    for m in re.finditer(PATTERNS["employee id"], r):
        order.append((m.group(0), "employee id"))
        len_eid[len(m.group(0)) - 4] += 1
    for m in re.finditer(PATTERNS["customer id"], r):
        order.append((m.group(0), "customer id"))
    for m in re.finditer(PATTERNS["URL (any, trailing .,;:!? cut)"], r):
        u = TRAIL.sub("", m.group(0))
        order.append((u, "PR link" if PR_FULL.fullmatch(u) else "other URL"))
    for v, k in order:
        if v in found:
            repeats += 1
        else:
            found[v] = k
    for v, k in found.items():
        kind_count[k] += 1
        if v not in known[k]:
            unknown[k] += 1
    per_q[i] = found

with_ids = [i for i in per_q if per_q[i]]
print("\nreferences holding at least one identifier (union):", len(with_ids))
print("distinct identifiers by kind:", dict(kind_count), "| total", sum(kind_count.values()))
print("repeats of an identifier within one reference (counted once):", repeats)
print("identifiers that are not a value of their kind in the corpus:", dict(unknown))
print("employee ids by hex length:", dict(len_eid))
mix = Counter(tuple(sorted(set(per_q[i].values()))) for i in with_ids)
print("questions by the kinds they hold:", {"+".join(k): n for k, n in mix.items()})
print("identifiers per question: min", min(len(per_q[i]) for i in with_ids),
      "median", sorted(len(per_q[i]) for i in with_ids)[len(with_ids) // 2],
      "max", max(len(per_q[i]) for i in with_ids))
print("question types of the questions holding identifiers:",
      dict(Counter(qs[i]["type"] for i in with_ids)))
print("question types of the questions holding none:",
      dict(Counter(qs[i]["type"] for i in per_q if not per_q[i])))
in_question = sum(1 for i in with_ids for v in per_q[i] if v in qs[i]["question"])
print("reference identifiers that also stand in the question text (exact substring):", in_question)

pickle.dump(per_q, open(OUT, "wb"))
print("written (scratch):", OUT.split("/")[-1])

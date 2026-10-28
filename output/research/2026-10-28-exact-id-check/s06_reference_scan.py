"""Which identifier kinds stand in the 815 reference answers. Prints only kinds, patterns,
generalised signatures and counts, never a value."""
import re
from collections import Counter, defaultdict

from common import corpus_identifiers, question_set, questions, reference

qs = questions()
ids = question_set()
print("questions in the set:", len(ids), "| all in questions.jsonl:", all(i in qs for i, _ in ids))
refs = {i: reference(qs[i]) for i, _ in ids}
print("question types over the 815:", dict(Counter(qs[i]["type"] for i, _ in ids)))
print("ground_truth parts per question: min", min(len(qs[i]["ground_truth"]) for i, _ in ids),
      "max", max(len(qs[i]["ground_truth"]) for i, _ in ids))

# 1. dictionary scan: every corpus identifier value, exact substring in the reference
kinds = corpus_identifiers()
print("\n-- dictionary scan: corpus identifier values found letter for letter in the references")
for k in sorted(kinds):
    vals = kinds[k]
    # skip very short values that are substrings of ordinary words (none expected)
    n_refs = 0
    n_hits = 0
    for i, ref in refs.items():
        hit = [v for v in vals if v and v in ref]
        if hit:
            n_refs += 1
            n_hits += len(hit)
    print(f"   {k:24s} values={len(vals):6d}  references holding one={n_refs:4d}  values found={n_hits:5d}")

# 2. candidate regexes from the corpus formats
CAND = {
    "employee id": r"\beid_[0-9a-f]{7,8}\b",
    "pr login EMP": r"\bEMP_\d{7,9}\b",
    "customer id": r"\bCUST-\d{4}\b",
    "pr link": r"https://github\.com/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+/pull/\d+",
    "any URL": r"https?://[^\s<>\"')\]]+",
    "pr id": r"\bgithub_com_\S+?_pull_\d+\b",
    "slack message id": r"\b\d{8}-\d{1,3}-[0-9a-f]{5,6}\b",
    "slack channel id": r"\bch-[a-z0-9_-]*-[0-9a-f]{6}\b",
    "transcript id product_dev": r"\bproduct_dev_[A-Za-z]+_\d{1,2}\b",
    "planning id": r"\b[A-Za-z]+_planning_\d(?:_chat)?\b",
}
print("\n-- candidate regexes: references holding at least one match, matches in all")
for name, rx in CAND.items():
    c = re.compile(rx)
    n_refs = sum(1 for r in refs.values() if c.search(r))
    n_m = sum(len(c.findall(r)) for r in refs.values())
    print(f"   {name:28s} {rx}\n      references={n_refs}  matches={n_m}")

# 3. leftovers: identifier-like tokens not covered by the regexes above, by signature
covered = re.compile("|".join(f"(?:{rx})" for rx in CAND.values()))
LOOK = re.compile(r"\b(?=[A-Za-z0-9_\-./:]*[0-9_])(?=[A-Za-z0-9_\-./:]*[A-Za-z])[A-Za-z0-9][A-Za-z0-9_\-./:]*[A-Za-z0-9]\b")
FIXED = {"eid", "EMP", "CUST", "https", "http", "github", "com", "pull", "www", "sf", "internal",
         "slack", "archives", "docs", "demo", "ch", "product", "dev", "planning", "chat", "salesforce"}


def sig(tok):
    out = []
    for t in re.findall(r"[A-Za-z0-9]+|[^A-Za-z0-9]+", tok):
        if not t[0].isalnum():
            out.append(re.escape(t))
        elif t in FIXED:
            out.append(t)
        elif t.isdigit():
            out.append(r"\d{%d}" % len(t))
        elif re.fullmatch(r"[0-9a-f]+", t):
            out.append("[0-9a-f]{%d}" % len(t))
        elif t.isalpha():
            out.append("[A-Za-z]{%d}" % len(t))
        else:
            out.append("[A-Za-z0-9]{%d}" % len(t))
    return "".join(out)


left = Counter()
left_refs = defaultdict(set)
for i, r in refs.items():
    stripped = covered.sub(" ", r)
    for tok in LOOK.findall(stripped):
        s = sig(tok)
        left[s] += 1
        left_refs[s].add(i)
print("\n-- identifier-like tokens left after the regexes (letters and digits or _), by signature")
for s, n in left.most_common(60):
    print(f"   {n:5d} in {len(left_refs[s]):4d} refs   {s}")

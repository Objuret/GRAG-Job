"""Limits of the check, counts only:
1. where the exact-substring and whole-token readings differ, by kind and arm;
2. the identifiers in an answer but not in its context: is the PR number or the repository path
   in the context (booleans counted);
3. reachability: does each reference identifier stand, as a whole token, in at least one record
   text of the corpus (the record texts the three arms hand over, prod/harness/record_text.py)."""
import glob
import json
import pickle
import re
import sys
from collections import Counter

sys.path.insert(0, "C:/Coding/exjobbet/GRAG-Job/prod")
from harness.record_text import ARTIFACT_TYPES, record_text  # noqa: E402

from common import ARMS, CORPUS, RUNS, RUNS_DIR, read_jsonl  # noqa: E402

SCR = "C:/Users/jocke/AppData/Local/Temp/claude/c--Coding-exjobbet-GRAG-Job/9c164e78-008e-41e9-85f3-58c55027a64c/scratchpad/exact_check"
res = pickle.load(open(f"{SCR}/run_flags.pkl", "rb"))
per_q = pickle.load(open(f"{SCR}/ref_identifiers.pkl", "rb"))
qids = sorted({q for _, q in res})

# 1
diff = Counter()
for (arm, q), e in res.items():
    for where in ("ctx", "ans"):
        for k, f in zip(e["kinds"], e[where]):
            if f["plain"] != f["tok"]:
                diff[(where, arm, k, "substring yes, whole token no" if f["plain"] else "other")] += 1
print("1. exact substring yes but not as a whole token:")
for k, n in sorted(diff.items()):
    print("  ", k, n)

# 2
targets = []
for (arm, q), e in res.items():
    for i, (k, fc, fa) in enumerate(zip(e["kinds"], e["ctx"], e["ans"])):
        if fa["plain"] and not fc["plain"]:
            targets.append((arm, q, i, k))
print("\n2. in the answer but not in the context:", len(targets), "by arm and kind:",
      dict(Counter((a, k) for a, _, _, k in targets)))
want = {(a, q) for a, q, _, _ in targets}
by_arm_set = {}
for (arm, set_name), run in RUNS.items():
    for r in read_jsonl(f"{RUNS_DIR}/{run}/arm_outputs.jsonl"):
        if (arm, r["id"]) in want:
            by_arm_set[(arm, r["id"])] = "\n\n".join(r["contexts"] or [])
for arm, q, i, k in targets:
    v = list(per_q[q].keys())[i]
    m = re.fullmatch(r"https://github\.com/([^/]+/[^/]+)/pull/(\d+)", v)
    ctx = by_arm_set[(arm, q)]
    if m:
        repo, num = m.group(1), m.group(2)
        print(f"   {arm} {k}: repository path in context={('github.com/' + repo) in ctx}, "
              f"'/pull/{{n}}' of it in context={bool(re.search('/pull/' + num + r'(?![0-9])', ctx))}, "
              f"the number as a whole token in context={bool(re.search(r'(?<![0-9])' + num + r'(?![0-9])', ctx))}, "
              f"other PR links of the same repository in context={len(set(re.findall(re.escape('https://github.com/' + repo) + r'/pull/\d+', ctx)))}")

# 3
texts = []
seen = set()
for fp in sorted(glob.glob(f"{CORPUS}/products/*.json")):
    d = json.load(open(fp, encoding="utf-8"))
    for kind in ARTIFACT_TYPES:
        for rec in d.get(kind, []) or []:
            if rec.get("id") is None or rec["id"] in seen:
                continue
            seen.add(rec["id"])
            texts.append(record_text(kind, rec))
print("\n3. record texts built:", len(texts))
big = "\n\x00\n".join(texts)
BEFORE = r"(?<![A-Za-z0-9_])"
AFTER_ID = r"(?![A-Za-z0-9_])"
AFTER_URL = r"(?![A-Za-z0-9_\-])(?![/?#.%=&~+:@][A-Za-z0-9_\-])"
reach = Counter()
reach_q = Counter()
for q in qids:
    n_in = 0
    for v, k in per_q[q].items():
        after = AFTER_URL if k in ("PR link", "other URL") else AFTER_ID
        hit = bool(re.search(BEFORE + re.escape(v) + after, big))
        reach[(k, hit)] += 1
        n_in += hit
    n = len(per_q[q])
    reach_q["all in some record text" if n_in == n else "some" if n_in else "none"] += 1
print("   identifiers standing in at least one record text, by kind (True) or in none (False):")
for k, n in sorted(reach.items()):
    print("     ", k, n)
print("   questions by their identifiers' presence in the record texts:", dict(reach_q))

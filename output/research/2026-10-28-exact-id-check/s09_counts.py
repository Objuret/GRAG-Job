"""Counts from the flags: per arm (step 3) and arm against arm question by question (step 4).
Prints only counts, shares and medians."""
import pickle
from collections import Counter
from statistics import median

from common import ARMS

SCR = "C:/Users/jocke/AppData/Local/Temp/claude/c--Coding-exjobbet-GRAG-Job/9c164e78-008e-41e9-85f3-58c55027a64c/scratchpad/exact_check"
res = pickle.load(open(f"{SCR}/run_flags.pkl", "rb"))
qids = sorted({q for _, q in res})
VARIANTS = ("plain", "tok", "plain_ci", "tok_ci")
NAMES = {"plain": "exact substring", "tok": "exact whole token",
         "plain_ci": "case-insensitive substring", "tok_ci": "case-insensitive whole token"}
print("questions holding at least one identifier:", len(qids))


def per_arm(arm, var, kind=None):
    c = Counter()
    for q in qids:
        e = res[(arm, q)]
        idx = [i for i, k in enumerate(e["kinds"]) if kind is None or k == kind]
        if not idx:
            continue
        c["questions"] += 1
        inc = [e["ctx"][i][var] for i in idx]
        ina = [e["ans"][i][var] for i in idx]
        n = len(idx)
        c["identifiers"] += n
        c["in context"] += sum(inc)
        c["in answer"] += sum(ina)
        c["in context, not in answer"] += sum(1 for x, y in zip(inc, ina) if x and not y)
        c["in answer, not in context"] += sum(1 for x, y in zip(inc, ina) if y and not x)
        c["in both"] += sum(1 for x, y in zip(inc, ina) if x and y)
        c["in neither"] += sum(1 for x, y in zip(inc, ina) if not x and not y)
        for what, flags in (("context", inc), ("answer", ina)):
            s = sum(flags)
            c[f"questions: all in {what}"] += s == n
            c[f"questions: some in {what}"] += 0 < s < n
            c[f"questions: none in {what}"] += s == 0
    return c


ROWS = ["questions", "identifiers", "in context", "in answer", "in context, not in answer",
        "in answer, not in context", "in both", "in neither",
        "questions: all in context", "questions: some in context", "questions: none in context",
        "questions: all in answer", "questions: some in answer", "questions: none in answer"]

for var in VARIANTS:
    print(f"\n=== step 3, {NAMES[var]}")
    tab = {arm: per_arm(arm, var) for arm in ARMS}
    print(f"{'':32s}" + "".join(f"{a:>12s}" for a in ARMS))
    for row in ROWS:
        print(f"{row:32s}" + "".join(f"{tab[a][row]:12d}" for a in ARMS))

print("\n=== step 3 by kind, exact substring (identifiers | in context | in answer | ctx not ans | ans not ctx)")
for kind in ("employee id", "PR link", "other URL", "customer id"):
    for arm in ARMS:
        c = per_arm(arm, "plain", kind)
        print(f"  {kind:12s} {arm:9s} questions={c['questions']:4d} identifiers={c['identifiers']:5d} "
              f"ctx={c['in context']:5d} ans={c['in answer']:5d} ctx_not_ans={c['in context, not in answer']:5d} "
              f"ans_not_ctx={c['in answer, not in context']:5d} | q all/some/none ctx="
              f"{c['questions: all in context']}/{c['questions: some in context']}/{c['questions: none in context']}"
              f" ans={c['questions: all in answer']}/{c['questions: some in answer']}/{c['questions: none in answer']}")


def share(arm, q, where, var):
    e = res[(arm, q)]
    f = e[where]
    return sum(x[var] for x in f) / len(f)


print("\n=== step 4, arm against arm, question by question (466 questions)")
for var in ("plain", "tok", "plain_ci"):
    print(f"-- {NAMES[var]}")
    for a, b in (("artefact", "lucene"), ("artefact", "vector"), ("lucene", "vector")):
        for where, label in (("ctx", "share in context"), ("ans", "share in answer")):
            d = [share(a, q, where, var) - share(b, q, where, var) for q in qids]
            hi = [x for x in d if x > 1e-12]
            lo = [-x for x in d if x < -1e-12]
            eq = len(d) - len(hi) - len(lo)
            both = hi + lo
            print(f"  {a:8s} vs {b:7s} {label:17s} higher={len(hi):4d} lower={len(lo):4d} equal={eq:4d} | "
                  f"median of the difference where higher={median(hi) if hi else float('nan'):.3f} "
                  f"where lower={median(lo) if lo else float('nan'):.3f} "
                  f"| median |difference| where unequal={median(both) if both else float('nan'):.3f} "
                  f"| median signed difference over all={median(d):.3f}")

# equal-split: how many 'equal' questions are equal at 0, at 1, or in between
print("\n=== step 4, equal questions split by the shared share (exact substring)")
for a, b in (("artefact", "lucene"), ("artefact", "vector"), ("lucene", "vector")):
    for where, label in (("ctx", "context"), ("ans", "answer")):
        eqs = [share(a, q, where, "plain") for q in qids
               if abs(share(a, q, where, "plain") - share(b, q, where, "plain")) <= 1e-12]
        print(f"  {a:8s} vs {b:7s} {label:8s} equal={len(eqs):4d}: both 0={sum(1 for x in eqs if x == 0):4d} "
              f"both 1={sum(1 for x in eqs if x == 1):4d} both between={sum(1 for x in eqs if 0 < x < 1):4d}")

# where the readings differ: how many identifier checks change between the readings
print("\n=== identifier checks (466 questions x 3 arms) where two readings give a different result")
for where in ("ctx", "ans"):
    for v1, v2 in (("plain", "tok"), ("plain", "plain_ci"), ("tok", "tok_ci"), ("plain_ci", "tok_ci")):
        n = sum(1 for e in res.values() for f in e[where] if f[v1] != f[v2])
        print(f"  {where}: {NAMES[v1]} vs {NAMES[v2]}: {n}")

# probes: near forms that are not letter for letter
print("\n=== probes (identifiers absent by exact substring, present in a near form), per arm")
for arm in ARMS:
    p = Counter()
    for q in qids:
        e = res[(arm, q)]
        for where, pk in (("ctx", "probe_ctx"), ("ans", "probe_ans")):
            for f, pr in zip(e[where], e[pk]):
                if f["plain"]:
                    continue
                for name, hit in pr.items():
                    p[f"{where}: {name}"] += hit
    print(f"  {arm}: {dict(p)}")

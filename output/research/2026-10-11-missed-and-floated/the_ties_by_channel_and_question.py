"""For his 2026-10-12 goal "solve this": the cited records by their tie (`first_gold_rounds/ties.py`),
split by the kind of channel, on the gold hundred and on the 300 unused questions (the seeded
draw of `the_order_on_unused_questions`; the held-out hundred left as it is). Reads the records
and the questions' citations; no graph, no model call. Prints numbers only.

  1  Slack messages by the first word of their channel's name (planning, develop, bug) and their
     tie: messages a question | of them cited | share of the question's cited records
  2  the questions that cite a record the ties call not the product's own work: how many, and in
     how many of them the other project's name (the repository of the pull request) stands in
     the question word for word
  3  by the benchmark's own type of question: share of the cited records the ties call not the
     product's own work

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/the_ties_by_channel_and_question.py
"""
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test"), str(HERE / "first_gold_rounds")]
sys.stdout.reconfigure(encoding="utf-8")

import ties as TI  # noqa: E402
from harness import questions as HQ  # noqa: E402

SEED = 20261011
WORD = re.compile(r"[a-z0-9]+")
ids_of = {name: {json.loads(line)["id"] for line in (REPO / "data" / f"{name}.jsonl").read_text(encoding="utf-8").splitlines()
                 if line.strip()} for name in ("gold100", "heldout100")}
every = HQ.load_questions()
fresh = sorted((q for q in every if q.id not in ids_of["gold100"] | ids_of["heldout100"] and q.citations), key=lambda q: q.id)
sets = {"the gold hundred": [q for q in every if q.id in ids_of["gold100"]],
        "300 unused questions": random.Random(SEED).sample(fresh, 300)}
products = sorted(path.stem for path in TI.RAW.glob("*.json"))
holder = {}
for name in products:
    for rid in TI.product(name)["raw"]:
        holder.setdefault(rid, name)

for label, questions in sets.items():
    seen, cited_n = Counter(), Counter()
    with_apart, named = 0, 0
    by_type = defaultdict(lambda: [0, 0])
    total = 0
    for q in questions:
        cites = {str(c) for c in q.citations}
        owners = Counter(holder[c] for c in cites if c in holder)
        if not owners:
            continue
        P = TI.product(owners.most_common(1)[0][0])
        total += 1
        apart_cited = []
        for rid, (kind, r) in P["raw"].items():
            t = TI.tie(rid, P)
            key = (P["channel_of"][rid].split("-")[0], t) if kind == "slack" else ("", t if kind == "prs" else kind)
            seen[key] += 1
            if rid in cites:
                cited_n[key] += 1
                by_type[str(q.type)][0] += 1
                if t in TI.APART:
                    by_type[str(q.type)][1] += 1
                    apart_cited.append(rid)
        if apart_cited:
            with_apart += 1
            words = set(WORD.findall(q.question.lower()))
            other = set()
            for rid in apart_cited:
                prs = [rid] if rid in P["pr_own"] else sorted(P["links"][P["talk_of"][rid]][4]) if rid in P["talk_of"] else []
                for pr in prs:
                    other.update(WORD.findall(" ".join(P["raw"][pr][1]["link"].split("/")[3:5]).lower()))
            named += bool(words & other)
    cited_all = sum(cited_n.values())
    print(f"\n==== {label}: {total} questions ====")
    print("== 1: records a question | of them cited | share of the cited records ==")
    for key, count in sorted(seen.items(), key=lambda kv: (kv[0][0] == "", kv[0][0], -kv[1])):
        print(f"  {count / total:7.1f} | {cited_n[key] / count:6.2%} | {cited_n[key] / cited_all:5.1%}  "
              f"{(key[0] + ' channel, ') if key[0] else ''}{key[1]}")
    print(f"== 2: questions that cite a record the ties call not the product's own work: {with_apart} of {total}; "
          f"the other project's name stands in the question in {named} of them ==")
    print("== 3: by type of question: cited records | of them not the product's own work by the ties ==")
    for kind, (n, apart) in sorted(by_type.items()):
        print(f"  {kind:8s} {n:6d} | {apart / n:6.2%}")

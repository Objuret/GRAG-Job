"""Round 51, under his 2026-10-12 goal "solve this": what ties a question's cited conversations to
each other. Round 41: not standing next to each other. Round 43: not the same own thing by link.
Here: the name of the thing they are about, as the messages write it between quote marks (a
bug's title, a feature), read word for word from the records. The hundred and the 300 unused
questions; no graph, no model call; numbers only.

  a named thing   a run of two or more words between quote marks in a message
  1  own conversations of a product that hold a named thing; named things held by 2, 3, more
     conversations
  2  a question's cited conversations: share that hold a named thing; share that share one with
     another cited conversation of the same question
  3  from a cited conversation, the other conversations that share a named thing with it: share
     cited (of the same question); from an own conversation that is not cited: share cited
"""
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path("C:/Coding/exjobbet/GRAG-Job")
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
import ties as TI  # noqa: E402
from harness import questions as HQ  # noqa: E402

QUOTED = re.compile(r"(?<![A-Za-z0-9])['\"‘“]([A-Z][^'\"’”\n]{3,80}?)['\"’”](?![A-Za-z0-9])")
ids_of = {name: {json.loads(line)["id"] for line in (REPO / "data" / f"{name}.jsonl").read_text(encoding="utf-8").splitlines()
                 if line.strip()} for name in ("gold100", "heldout100")}
every = HQ.load_questions()
fresh = sorted((q for q in every if q.id not in ids_of["gold100"] | ids_of["heldout100"] and q.citations), key=lambda q: q.id)
sets = {"the gold hundred": [q for q in every if q.id in ids_of["gold100"]],
        "300 unused questions": random.Random(20261011).sample(fresh, 300)}
holder, named = {}, {}
for path in sorted(TI.RAW.glob("*.json")):
    P = TI.product(path.stem)
    for rid in P["raw"]:
        holder.setdefault(rid, path.stem)
    talks = defaultdict(list)
    for rid, t in P["talk_of"].items():
        if not TI.apart(rid, P):
            talks[t].append(rid)
    things = defaultdict(set)
    for t, rs in talks.items():
        for r in rs:
            for hit in QUOTED.findall(P["raw"][r][1]["Message"]["User"]["text"]):
                words = " ".join(hit.lower().split())
                if len(words.split()) >= 2:
                    things[words].add(t)
    of_talk = defaultdict(set)
    for thing, held in things.items():
        for t in held:
            of_talk[t].add(thing)
    named[path.stem] = (talks, things, of_talk)
sizes, with_thing, talks_all = Counter(), 0, 0
for talks, things, of_talk in named.values():
    talks_all += len(talks)
    with_thing += sum(1 for t in talks if of_talk[t])
    for held in things.values():
        sizes[min(len(held), 4)] += 1
print(f"1: own conversations over the 30 products: {talks_all}; holding a named thing: {with_thing / talks_all:.0%}; named things held "
      f"by 1, 2, 3, 4 or more conversations: {[sizes[k] for k in (1, 2, 3, 4)]}")
for label, questions in sets.items():
    cited_talks = holding = sharing = 0
    reach = Counter()
    for q in questions:
        cites = {str(c) for c in q.citations}
        owners = Counter(holder[c] for c in cites if c in holder)
        if not owners:
            continue
        talks, things, of_talk = named[owners.most_common(1)[0][0]]
        cited = {t for t, rs in talks.items() if cites & set(rs)}
        for t in talks:
            others = set().union(*[things[x] for x in of_talk[t]]) - {t} if of_talk[t] else set()
            if t in cited:
                cited_talks += 1
                holding += bool(of_talk[t])
                sharing += bool(others & cited)
            for o in others:
                reach[("cited" if t in cited else "not cited", o in cited)] += 1
    print(f"\n==== {label} ====")
    print(f"2: cited conversations: {cited_talks}; holding a named thing: {holding / cited_talks:.0%}; sharing one with another cited "
          f"conversation of the question: {sharing / cited_talks:.0%}")
    for start in ("cited", "not cited"):
        yes, no = reach[(start, True)], reach[(start, False)]
        print(f"3: from a conversation that is {start}: the conversations sharing a named thing with it: {yes + no}; of them cited: "
              f"{yes / max(yes + no, 1):.1%}")

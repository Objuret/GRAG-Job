"""Round 44, under his 2026-10-12 goal "solve this": talks about the same kind of own thing (the
versions of one document, own pull requests with the same title) shut each other out: from a
talk with a cited message none of the other 130 is cited (round 43). Which of them is the cited
one, by the order in time (his 2026-10-11 thought of nearness to "now" as a weight)? The hundred
and, with no order needed, the 300 unused questions; numbers only.

  groups with a cited talk: by what the thing is and how many talks the group has:
  the cited talk is the first in time | one in between | the last in time
  and for the own pull requests of such a group: merged or not, of the cited talk's and of the others'
"""
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path("C:/Coding/exjobbet/GRAG-Job")
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
import ties as TI  # noqa: E402
from harness import questions as HQ  # noqa: E402

ids_of = {name: {json.loads(line)["id"] for line in (REPO / "data" / f"{name}.jsonl").read_text(encoding="utf-8").splitlines()
                 if line.strip()} for name in ("gold100", "heldout100")}
every = HQ.load_questions()
fresh = sorted((q for q in every if q.id not in ids_of["gold100"] | ids_of["heldout100"] and q.citations), key=lambda q: q.id)
sets = {"the gold hundred": [q for q in every if q.id in ids_of["gold100"]],
        "300 unused questions": random.Random(20261011).sample(fresh, 300)}
holder = {}
for path in sorted(TI.RAW.glob("*.json")):
    for rid in TI.product(path.stem)["raw"]:
        holder.setdefault(rid, path.stem)


def kind_of_thing(thing, P):
    kind, r = P["raw"][thing]
    return ("document", r["type"]) if kind == "documents" else ("pull request", r["title"])


for label, questions in sets.items():
    where, merged, sizes, both = Counter(), Counter(), Counter(), 0
    asked = with_group = 0
    for q in questions:
        cites = {str(c) for c in q.citations}
        owners = Counter(holder[c] for c in cites if c in holder)
        if not owners:
            continue
        asked += 1
        P = TI.product(owners.most_common(1)[0][0])
        talks = defaultdict(list)
        for rid, t in P["talk_of"].items():
            if not TI.apart(rid, P):
                talks[t].append(rid)
        groups = defaultdict(set)
        for t in talks:
            for thing in P["links"][t][3]:
                groups[kind_of_thing(thing, P)].add((t, thing))
        hit = False
        for (what, _), members in groups.items():
            if len({t for t, _ in members}) < 2:
                continue
            when = {t: min(P["raw"][r][1]["Message"]["User"]["timestamp"] for r in talks[t]) for t, _ in members}
            line = sorted({t for t, _ in members}, key=lambda t: when[t])
            cited = [t for t in line if cites & set(talks[t])]
            if not cited:
                continue
            hit = True
            both += len(cited) > 1
            sizes[(what, len(line))] += 1
            for t in cited:
                at = line.index(t)
                where[(what, "the first in time" if at == 0 else "the last in time" if at == len(line) - 1 else "one in between")] += 1
            if what == "pull request":
                for t, thing in members:
                    merged[("cited" if t in cited else "not cited", str(P["raw"][thing][1]["merged"]))] += 1
        with_group += hit
    print(f"\n==== {label}: {asked} questions; {with_group} cite a talk that has another talk about the same kind of thing; "
          f"groups with more than one cited talk: {both} ====")
    print("  groups with a cited talk, by the thing and the number of talks:", dict(sorted(sizes.items())))
    for what in ("document", "pull request"):
        row = {k: where[(what, k)] for k in ("the first in time", "one in between", "the last in time")}
        print(f"  {what}: the cited talk is {row}")
    print("  own pull requests of those groups, (cited or not, merged):", dict(sorted(merged.items())))

"""For his 2026-10-12 goal "solve this" (the order): which other names of the product's own things a
question holds word for word, beside a company and a document type: the title of an own pull
request, and a name the messages write between quote marks (a bug's title, a feature). For each:
how many questions hold one, and the scope it picks by the records' ties. No graph read, no
model call; the gold hundred, the 300 unused questions and every question outside the two
hundreds; numbers only.

  a pull request's title   the scope: that pull request and the conversations linking to it
  a quoted name            two or more words between quote marks in a message of the product's
                           own conversations; the scope: the conversations holding it
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

OPEN, CLOSE = "'\"‘“", "'\"’”"
QUOTED = re.compile(r"(?<![A-Za-z0-9])[" + OPEN + r"]([A-Z][^" + OPEN + CLOSE + r"\n]{3,80}?)[" + CLOSE + r"](?![A-Za-z0-9])")


def plain(text):
    return " " + re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip() + " "


ids_of = {name: {json.loads(line)["id"] for line in (REPO / "data" / f"{name}.jsonl").read_text(encoding="utf-8").splitlines()
                 if line.strip()} for name in ("gold100", "heldout100")}
every = HQ.load_questions()
fresh = sorted((q for q in every if q.id not in ids_of["gold100"] | ids_of["heldout100"] and q.citations), key=lambda q: q.id)
sets = {"the gold hundred": [q for q in every if q.id in ids_of["gold100"]],
        "300 unused questions": random.Random(20261011).sample(fresh, 300),
        "every question outside the two hundreds": fresh}
holder, book = {}, {}
for path in sorted(TI.RAW.glob("*.json")):
    P = TI.product(path.stem)
    for rid in P["raw"]:
        holder.setdefault(rid, path.stem)
    talks = defaultdict(list)
    for rid, t in P["talk_of"].items():
        if not TI.apart(rid, P):
            talks[t].append(rid)
    quoted = defaultdict(set)
    for t, rs in talks.items():
        for r in rs:
            for hit in QUOTED.findall(P["raw"][r][1]["Message"]["User"]["text"]):
                if len(hit.split()) >= 2:
                    quoted[plain(hit)].add(t)
    titles = defaultdict(set)
    for rid, own in P["pr_own"].items():
        if own:
            titles[plain(P["raw"][rid][1]["title"])].add(rid)
    book[path.stem] = (P, talks, quoted, titles)

for label, questions in sets.items():
    rows = {"an own pull request's title": [0, 0, 0, 0, 0, Counter()], "a quoted name": [0, 0, 0, 0, 0, Counter()]}
    for q in questions:
        cites = {str(c) for c in q.citations}
        owners = Counter(holder[c] for c in cites if c in holder)
        if not owners:
            continue
        P, talks, quoted, titles = book[owners.most_common(1)[0][0]]
        words = plain(q.question)
        cited = {t for t, rs in talks.items() if cites & set(rs)}
        prs = set().union(*[rids for title, rids in titles.items() if title in words])
        scopes = {"an own pull request's title": {t for t in talks if P["links"][t][3] & prs} if prs else None,
                  "a quoted name": (set().union(*[ts for name, ts in quoted.items() if name in words])
                                    if any(name in words for name in quoted) else None)}
        for key, got in scopes.items():
            if got is None:
                continue
            row = rows[key]
            row[0] += 1
            row[1] += len(got)
            row[2] += len(got & cited)
            row[3] += len(cited)
            row[4] += len(cited & got)
            row[5][str(q.type)] += 1
    print(f"\n==== {label}: {len(questions)} questions ====")
    for key, (qs, reached, hit, cited_n, cited_in, types) in rows.items():
        print(f"  {qs:3d} questions hold {key} ({dict(types)}); its conversations: {reached / max(qs, 1):.1f} a question, "
              f"{hit / max(reached, 1):.0%} with a cited message; {cited_in / max(cited_n, 1):.0%} of those questions' cited "
              f"conversations among them")

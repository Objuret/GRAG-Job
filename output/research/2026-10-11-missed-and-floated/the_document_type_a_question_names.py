"""For his 2026-10-12 goal "solve this" (the order): after the company, the next name a question may
hold word for word is a document's type (the `type` of a document record and the
`document_type` of a meeting record: "Market Research Report" and so on). The scope it picks,
by the records' own ties: the documents of that type, the meetings about that type, and the
product's own conversations that link to a document of that type (a talk about another
company's document of the same type holds no such link). No graph read, no model call; the gold
hundred, the 300 unused questions and every question outside the two hundreds; numbers only.

  1  questions that hold a document type of their product
  2  for those: the conversations linking to a document of that type: how many a question,
     share with a cited message, share of the question's cited conversations among them
  3  the meetings about that type and the documents of that type: how many a question, share cited
  4  share of the question's cited records that lie in that whole scope, and the scope's size
     in characters
"""
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test"), str(HERE / "first_gold_rounds")]
sys.stdout.reconfigure(encoding="utf-8")

import ties as TI  # noqa: E402
from harness import questions as HQ  # noqa: E402


def plain(text):
    return " " + re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip() + " "


ids_of = {name: {json.loads(line)["id"] for line in (REPO / "data" / f"{name}.jsonl").read_text(encoding="utf-8").splitlines()
                 if line.strip()} for name in ("gold100", "heldout100")}
every = HQ.load_questions()
fresh = sorted((q for q in every if q.id not in ids_of["gold100"] | ids_of["heldout100"] and q.citations), key=lambda q: q.id)
sets = {"the gold hundred": [q for q in every if q.id in ids_of["gold100"]],
        "300 unused questions": random.Random(20261011).sample(fresh, 300),
        "every question outside the two hundreds": fresh}
holder = {}
for path in sorted(TI.RAW.glob("*.json")):
    for rid in TI.product(path.stem)["raw"]:
        holder.setdefault(rid, path.stem)

for label, questions in sets.items():
    named_q, types = 0, Counter()
    talks_n, talks_cited, cited_talks, cited_in = 0, 0, 0, 0
    meet_n, meet_cited, docs_n, docs_cited = 0, 0, 0, 0
    share, chars = [], []
    for q in questions:
        cites = {str(c) for c in q.citations}
        owners = Counter(holder[c] for c in cites if c in holder)
        if not owners:
            continue
        P = TI.product(owners.most_common(1)[0][0])
        words = plain(q.question)
        kinds = {plain(r["type"]) for kind, r in P["raw"].values() if kind == "documents"}
        named = {k for k in kinds if k in words}
        if not named:
            continue
        named_q += 1
        types[str(q.type)] += 1
        docs = {rid for rid, (kind, r) in P["raw"].items() if kind == "documents" and plain(r["type"]) in named}
        meetings = {rid for rid, (kind, r) in P["raw"].items()
                    if kind == "meeting_transcripts" and plain(r["document_type"]) in named}
        talks = defaultdict(list)
        for rid, t in P["talk_of"].items():
            if not TI.apart(rid, P):
                talks[t].append(rid)
        linked = {t for t in talks if P["links"][t][3] & docs}
        cited = {t for t, rs in talks.items() if cites & set(rs)}
        talks_n += len(linked)
        talks_cited += len(linked & cited)
        cited_talks += len(cited)
        cited_in += len(cited & linked)
        meet_n += len(meetings)
        meet_cited += len(meetings & cites)
        docs_n += len(docs)
        docs_cited += len(docs & cites)
        scope_records = docs | meetings | {r for t in linked for r in talks[t]}
        share.append(len(cites & scope_records) / len(cites))
        chars.append(sum(P["size"][r] for r in scope_records))
    print(f"\n==== {label}: {len(questions)} questions; {named_q} hold a document type of their product ({dict(types)}) ====")
    if named_q:
        print(f"  conversations linking to a document of that type: {talks_n / named_q:.1f} a question; {talks_cited / max(talks_n, 1):.0%} "
              f"with a cited message; {cited_in / max(cited_talks, 1):.0%} of the questions' cited conversations among them")
        print(f"  meetings about that type: {meet_n / named_q:.1f} a question, {meet_cited / max(meet_n, 1):.0%} cited; documents of that "
              f"type: {docs_n / named_q:.1f} a question, {docs_cited / max(docs_n, 1):.0%} cited")
        print(f"  share of a question's cited records inside that whole scope: mean {np.mean(share):.0%}, middle {np.median(share):.0%}; "
              f"the scope's size: {np.median(chars):,.0f} characters at the middle")

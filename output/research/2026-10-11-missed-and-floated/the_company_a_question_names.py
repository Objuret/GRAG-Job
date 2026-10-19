"""For his 2026-10-12 goal "solve this" (the order): a question never names a person, but 18 of the
hundred and 12 of the 300 unused questions hold a company's name (`the_people_a_question_names`).
The graph ties a company to its customers (Customer-[company]->Company, 120 customers, 10
companies); the messages name a customer by its id. So a company named in the question leads,
through the graph, to the customers and through them to the messages that speak of them: two
steps no nearness of words can take, since the question says the company and the message says
the id. Does it lead to the gold? No graph read here (the customers file is what the graph's
Customer nodes point into), no model call; numbers only.

  1  for the questions that hold a company's name: the product's own conversations with a
     message that names one of that company's customers: how many a question; share of them
     with a cited message; share of the question's cited conversations that are among them
  2  the same for conversations that name ANY customer (to see what the company adds)
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

META = REPO / "data" / "raw" / "Salesforce__HERB" / "metadata"
customers = json.loads((META / "customers_data.json").read_text(encoding="utf-8"))
CUST = re.compile(r"CUST-\d+")


def plain(text):
    return " " + re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip() + " "


of_company = defaultdict(set)
for row in customers:
    of_company[plain(row["company"])].add(row["id"])
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
    rows = {"of the named company": [0, 0, 0, 0], "of any company": [0, 0, 0, 0]}
    named_q, types, none_found = 0, Counter(), 0
    for q in questions:
        words = plain(q.question)
        named = [name for name in of_company if name in words]
        if not named:
            continue
        cites = {str(c) for c in q.citations}
        owners = Counter(holder[c] for c in cites if c in holder)
        if not owners:
            continue
        named_q += 1
        types[str(q.type)] += 1
        P = TI.product(owners.most_common(1)[0][0])
        wanted = set().union(*(of_company[name] for name in named))
        talks = defaultdict(list)
        for rid, t in P["talk_of"].items():
            if not TI.apart(rid, P):
                talks[t].append(rid)
        cited = {t for t, rs in talks.items() if cites & set(rs)}
        of_named, of_any = set(), set()
        for t, rs in talks.items():
            found = {c for r in rs for c in CUST.findall(P["raw"][r][1]["Message"]["User"]["text"])}
            if found & wanted:
                of_named.add(t)
            if found:
                of_any.add(t)
        none_found += not of_named
        for key, got in (("of the named company", of_named), ("of any company", of_any)):
            row = rows[key]
            row[0] += len(got)
            row[1] += len(got & cited)
            row[2] += len(cited)
            row[3] += len(cited & got)
    print(f"\n==== {label}: {len(questions)} questions, {named_q} hold a company's name ({dict(types)}); "
          f"no conversation names a customer of it on {none_found} ====")
    for key, (reached, hit, cited_n, cited_in) in rows.items():
        print(f"  conversations naming a customer {key}: {reached / max(named_q, 1):.1f} a question; {hit / max(reached, 1):.0%} of them "
              f"with a cited message; {cited_in / max(cited_n, 1):.0%} of the questions' cited conversations are among them")

"""For his 2026-10-12 goal "solve this" (the order): after the company (`the_company_a_question_names`),
the other names the graph holds beside the product's: a role (Employee-[role]->Role,
Customer-[role]->Role) and an org (Employee-[org]->Org). Does a question name one word for word,
and do the messages of the product's people with that role point at the gold? The gold hundred,
the 300 unused questions and every question outside the two hundreds; no graph read (the
employees file is what the graph's Employee nodes point into), no model call; numbers only.

  1  questions that hold a role's name; an org's name; which roles (the role names are the
     metadata's, not the questions')
  2  for the questions that hold an employee role: the product's own conversations in which a
     person with that role writes: how many a question, share with a cited message, share of
     the question's cited conversations among them; the same for the conversations such a
     person STARTS
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
employees = json.loads((META / "employee.json").read_text(encoding="utf-8"))
customers = json.loads((META / "customers_data.json").read_text(encoding="utf-8"))


def plain(text):
    return " " + re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip() + " "


with_role = defaultdict(set)
for eid, row in employees.items():
    with_role[plain(row["role"])].add(eid)
customer_roles = {plain(row["role"]) for row in customers}
orgs = {plain(row["org"]) for row in employees.values()}
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
print(f"employee roles: {len(with_role)}; customer roles: {len(customer_roles)}; orgs: {len(orgs)}")

for label, questions in sets.items():
    has, which = Counter(), Counter()
    writes, starts = [0, 0, 0, 0], [0, 0, 0, 0]
    named_q = 0
    for q in questions:
        words = plain(q.question)
        roles = [name for name in with_role if name in words]
        has["an employee role"] += bool(roles)
        has["a customer role"] += any(name in words for name in customer_roles)
        has["an org"] += any(name in words for name in orgs)
        for name in roles:
            which[name.strip()] += 1
        if not roles:
            continue
        cites = {str(c) for c in q.citations}
        owners = Counter(holder[c] for c in cites if c in holder)
        if not owners:
            continue
        named_q += 1
        P = TI.product(owners.most_common(1)[0][0])
        wanted = set().union(*(with_role[name] for name in roles))
        talks = defaultdict(list)
        for rid, t in P["talk_of"].items():
            if not TI.apart(rid, P):
                talks[t].append(rid)
        cited = {t for t, rs in talks.items() if cites & set(rs)}
        by_writer, by_starter = set(), set()
        for t, rs in talks.items():
            rs = sorted(rs, key=lambda r: P["raw"][r][1]["Message"]["User"]["timestamp"])
            who = [P["raw"][r][1]["Message"]["User"]["userId"] for r in rs]
            if wanted & set(who):
                by_writer.add(t)
            if who[0] in wanted:
                by_starter.add(t)
        for row, got in ((writes, by_writer), (starts, by_starter)):
            row[0] += len(got)
            row[1] += len(got & cited)
            row[2] += len(cited)
            row[3] += len(cited & got)
    print(f"\n==== {label}: {len(questions)} questions ====")
    print("1: questions that hold:", ", ".join(f"{k} {v}" for k, v in has.items()), "| roles:", dict(which.most_common(8)))
    for name, (reached, hit, cited_n, cited_in) in (("writes", writes), ("starts", starts)):
        if named_q:
            print(f"2: conversations a person with the named role {name}: {reached / named_q:.1f} a question; {hit / max(reached, 1):.0%} of "
                  f"them with a cited message; {cited_in / max(cited_n, 1):.0%} of the questions' cited conversations among them")

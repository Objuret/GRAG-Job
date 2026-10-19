"""For his 2026-10-12 goal "solve this" (the order): the graph holds the people (530 employees, 120
customers) and ties them to channels, meetings, documents and products; no arm reads those ties
for the order. Does a question name a person, a customer or a company, word for word, and if it
does, do that person's messages point at the gold? (His 2026-10-06 side thought: "what if we
allow names of people, products and channels to be tags from the query ... a match on one of
those does NOT pick/boost a chunk, it picks/boosts a scope"; 2026-10-11: "search-start or
search-range for that specific person".) The gold hundred and the 300 unused questions; no graph
read, no model call; the questions are read inside the script and only counts are printed.

  1  questions that hold: an employee's full name; an employee id; a customer's full name; a
     customer id; a company's name
  2  for the questions that hold an employee's full name: the product's own conversations in
     which a named person writes or is named: how many a question, share with a cited message;
     and the share of the question's cited conversations that are among them
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


name_of = {eid: plain(row["name"]) for eid, row in employees.items()}
eids_of_name = defaultdict(set)
for eid, name in name_of.items():
    eids_of_name[name].add(eid)
customer_names = {plain(row["name"]) for row in customers}
companies = {plain(row["company"]) for row in customers}
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
print(f"employees: {len(employees)}, distinct full names {len(eids_of_name)}; customers {len(customers)}, companies {len(companies)}")

for label, questions in sets.items():
    has = Counter()
    by_type = defaultdict(lambda: [0, 0])
    reached, reached_cited, cited_total, cited_in = 0, 0, 0, 0
    named_q = 0
    for q in questions:
        words = plain(q.question)
        named = {name for name in eids_of_name if name in words}
        has["an employee's full name"] += bool(named)
        has["an employee id"] += bool(re.search(r"eid_[0-9a-f]{6,}", q.question))
        has["a customer's full name"] += any(name in words for name in customer_names)
        has["a customer id"] += bool(re.search(r"CUST-\d+", q.question))
        has["a company's name"] += any(name in words for name in companies)
        by_type[str(q.type)][0] += 1
        by_type[str(q.type)][1] += bool(named)
        if not named:
            continue
        cites = {str(c) for c in q.citations}
        owners = Counter(holder[c] for c in cites if c in holder)
        if not owners:
            continue
        named_q += 1
        P = TI.product(owners.most_common(1)[0][0])
        wanted = set().union(*(eids_of_name[name] for name in named))
        talks = defaultdict(list)
        for rid, t in P["talk_of"].items():
            if not TI.apart(rid, P):
                talks[t].append(rid)
        cited = {t for t, rs in talks.items() if cites & set(rs)}
        with_person = set()
        for t, rs in talks.items():
            for r in rs:
                user = P["raw"][r][1]["Message"]["User"]
                if user["userId"] in wanted or any(name in plain(user["text"]) for name in named):
                    with_person.add(t)
                    break
        reached += len(with_person)
        reached_cited += len(with_person & cited)
        cited_total += len(cited)
        cited_in += len(cited & with_person)
    n = len(questions)
    print(f"\n==== {label}: {n} questions ====")
    print("1: questions that hold:", ", ".join(f"{k} {v}" for k, v in has.items()))
    print("   an employee's full name, by type of question:", ", ".join(f"{k} {v[1]} of {v[0]}" for k, v in sorted(by_type.items())))
    if named_q:
        print(f"2: over the {named_q} questions that name an employee: conversations where a named person writes or is named: "
              f"{reached / named_q:.1f} a question, {reached_cited / max(reached, 1):.0%} of them with a cited message; "
              f"{cited_in / max(cited_total, 1):.0%} of those questions' cited conversations are among them")

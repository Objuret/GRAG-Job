"""His 2026-10-11 "search-start or search-range for that specific person or whatever pointer", at the
level of a conversation: do the people of one gold conversation lead to the other gold
conversations of the same question.

A conversation is the posts of one channel on one calendar day; a document, a meeting or a pull
request is its own one-post conversation. Its people are every user, author, participant, pull
request author and reviewer on its posts. Two conversations are weighed by the people they
share, a person counting the less the more conversations of the product they are in (the log of
the product's conversations over the conversations with that person).

On the hundred, no model call, no query side at all. From a start conversation the others of the
product are ordered by that weight. Printed: starting from a gold conversation, how often the
nearest, the nearest three and the nearest five are gold, and how much of the question's other
gold conversations and gold posts lie among them; the same from a conversation that is not gold.

The gold ids are read inside this script; it prints numbers only.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/the_people_of_a_conversation.py [gold100]
"""
import json
import math
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _load_verified_doc  # noqa: E402
from graph.db import _driver  # noqa: E402
from harness import questions as HQ  # noqa: E402

SET = sys.argv[1] if len(sys.argv) > 1 else "gold100"
DEPTHS = (1, 3, 5, 10)
CYPHER = """
MATCH (f:File)-[:HAS_CHUNK]->(c:Chunk)-[:product]->(p:Product) WHERE c.desc_emb IS NOT NULL
RETURN DISTINCT p.name AS product, f.rel_path AS relpath, f.sha256 AS sha256, c.section AS section
"""


def stamp(value):
    if value is None:
        return None
    text = str(value).strip()
    try:
        return float(text)
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00").replace(" ", "T")).timestamp()
    except ValueError:
        return None


def people_of(record):
    found = set()
    user = ((record.get("Message") or {}).get("User") or {}).get("userId")
    if user:
        found.add(str(user))
    if record.get("author"):
        found.add(str(record["author"]))
    for who in record.get("participants") or []:
        found.add(str(who))
    login = (record.get("user") or {}).get("login") if isinstance(record.get("user"), dict) else None
    if login:
        found.add(str(login))
    for review in record.get("reviews") or []:
        login = (review.get("user") or {}).get("login")
        if login:
            found.add(str(login))
    return found


driver = _driver()
with driver.session(database=V.DATABASE) as session:
    rows = session.execute_read(lambda tx: [dict(r) for r in tx.run(CYPHER)])
driver.close()
files = defaultdict(lambda: {"sections": set()})
for row in rows:
    files[row["product"]].update(relpath=row["relpath"], sha256=row["sha256"])
    files[row["product"]]["sections"].add(row["section"])
docs, products = {}, {}
for product, spec in files.items():
    doc = _load_verified_doc(spec["relpath"], spec["sha256"], docs)
    talk_of, members, people = {}, defaultdict(list), defaultdict(set)
    for section in sorted(spec["sections"]):
        for record in doc[section]:
            if not isinstance(record, dict) or record.get("id") is None:
                continue
            rid = str(record["id"])
            message = record.get("Message") or {}
            when = stamp((message.get("User") or {}).get("timestamp")) if "Message" in record else None
            if "Channel" in record and when is not None:
                key = ("slack", (record.get("Channel") or {}).get("channelID"),
                       datetime.fromtimestamp(when, timezone.utc).date().isoformat())
            else:
                key = (section, rid)
            talk_of[rid] = key
            members[key].append(rid)
            people[key] |= people_of(record)
    keys = sorted(members, key=str)
    in_talks = Counter(person for key in keys for person in people[key])
    weight = {person: math.log(len(keys) / count) for person, count in in_talks.items()}
    with_person = defaultdict(set)
    for key in keys:
        for person in people[key]:
            with_person[person].add(key)
    products[product] = (talk_of, members, people, keys, weight, with_person)

wanted = [json.loads(line)["id"] for line in (REPO / "data" / f"{SET}.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
draw = random.Random(20261011)
cells = defaultdict(lambda: [0, 0])
reach, reach_posts = defaultdict(list), defaultdict(list)
facts = defaultdict(list)
for qid in wanted:
    q = by_id[qid]
    talk_of, members, people, keys, weight, with_person = products[qid.split("::")[0]]
    cites = {str(c) for c in q.citations if str(c) in talk_of}
    gold_talks = {talk_of[r] for r in cites}
    facts["conversations of the product"].append(len(keys))
    facts["gold conversations of the question"].append(len(gold_talks))
    facts["people in a gold conversation"].append(float(np.median([len(people[k]) for k in gold_talks])))
    others = [k for k in keys if k not in gold_talks]
    starts = [("a gold conversation", sorted(gold_talks, key=str)),
              ("a conversation that is not gold", draw.sample(others, min(len(gold_talks), len(others))))]
    for label, chosen in starts:
        for start in chosen:
            score = Counter()
            for person in people[start]:
                for key in with_person[person]:
                    if key != start:
                        score[key] += weight[person]
            ranked = sorted(score, key=lambda k: (-score[k], str(k)))
            rest_gold = gold_talks - {start}
            rest_posts = {r for r in cites if talk_of[r] != start}
            for depth in DEPTHS:
                top = ranked[:depth]
                cell = cells[label, depth]
                cell[0] += sum(1 for k in top if k in gold_talks)
                cell[1] += len(top)
                if label == "a gold conversation" and rest_gold:
                    reach[depth].append(sum(1 for k in top if k in rest_gold) / len(rest_gold))
                    got = {r for k in top for r in members[k]}
                    reach_posts[depth].append(len(got & rest_posts) / max(len(rest_posts), 1))

print(f"{SET}: {len(wanted)} questions")
for name, values in facts.items():
    q1, mid, q3 = np.percentile(values, [25, 50, 75])
    print(f"  {name}: {mid:.0f} ({q1:.0f}-{q3:.0f})")
print("\n== the conversations nearest by shared people: gold of conversations (share), from a gold conversation | "
      "from a conversation that is not gold | of the question's OTHER gold conversations among them, mean | of its "
      "other gold posts among them, mean ==")
for depth in DEPTHS:
    g, t = cells["a gold conversation", depth]
    g2, t2 = cells["a conversation that is not gold", depth]
    print(f"  the nearest {depth}: {g} of {t} ({(g / t if t else 0):.3f}) | {g2} of {t2} ({(g2 / t2 if t2 else 0):.3f}) | "
          f"{float(np.mean(reach[depth])):.3f} | {float(np.mean(reach_posts[depth])):.3f}")
print("done", flush=True)

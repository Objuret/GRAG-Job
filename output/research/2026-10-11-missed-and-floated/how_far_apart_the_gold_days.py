"""After `the_days_of_the_gold`: how far apart a question's gold days lie among the days the product
has posts on, and what a range of days around one gold day holds. On the hundred, no model call,
no query side. The product's days with posts are numbered in order; a step is one such day.

Printed per question (the middle and the quarters): from the first to the last gold day in steps;
and around the gold's fullest day, for a range of so many steps to each side: the share of the
gold posts inside it, and how many posts and characters the product has inside it.

The gold ids are read inside this script; it prints numbers only.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/how_far_apart_the_gold_days.py [gold100]
"""
import json
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
RANGES = (0, 1, 2, 3, 5, 7, 10)
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
    day_of, size_of = {}, {}
    for section in sorted(spec["sections"]):
        for record in doc[section]:
            if not isinstance(record, dict) or record.get("id") is None:
                continue
            message = record.get("Message") or {}
            when = (stamp((message.get("User") or {}).get("timestamp")) if "Message" in record
                    else stamp(record.get("date") if "date" in record else record.get("created_at")))
            if when is not None:
                rid = str(record["id"])
                day_of[rid] = datetime.fromtimestamp(when, timezone.utc).date().isoformat()
                size_of[rid] = len(json.dumps(record, ensure_ascii=False)) + 1
    days = sorted(set(day_of.values()))
    step = {day: k for k, day in enumerate(days)}
    posts_on, chars_on = Counter(), Counter()
    for rid, day in day_of.items():
        posts_on[step[day]] += 1
        chars_on[step[day]] += size_of[rid]
    products[product] = (day_of, step, posts_on, chars_on, len(days))

wanted = [json.loads(line)["id"] for line in (REPO / "data" / f"{SET}.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
facts = defaultdict(list)
inside = {r: defaultdict(list) for r in RANGES}
for qid in wanted:
    q = by_id[qid]
    day_of, step, posts_on, chars_on, n_days = products[qid.split("::")[0]]
    gold_steps = [step[day_of[r]] for r in map(str, q.citations) if r in day_of]
    if not gold_steps:
        continue
    counts = Counter(gold_steps)
    facts["days the product has posts on"].append(n_days)
    facts["gold days"].append(len(counts))
    facts["steps from the first to the last gold day"].append(max(counts) - min(counts) + 1)
    ordered = sorted(counts)
    facts["largest gap between two gold days that follow each other, in steps"].append(
        max((b - a for a, b in zip(ordered, ordered[1:])), default=0))
    centre = counts.most_common(1)[0][0]
    for r in RANGES:
        window = range(max(centre - r, 0), min(centre + r, n_days - 1) + 1)
        inside[r]["share of the gold posts"].append(sum(counts.get(s, 0) for s in window) / len(gold_steps))
        inside[r]["posts"].append(sum(posts_on.get(s, 0) for s in window))
        inside[r]["characters"].append(sum(chars_on.get(s, 0) for s in window))

print(f"{SET}: {len(wanted)} questions; the middle (a quarter - three quarters)")
for name, values in facts.items():
    q1, mid, q3 = np.percentile(values, [25, 50, 75])
    print(f"  {name}: {mid:.0f} ({q1:.0f}-{q3:.0f})")
print("\n== a range of days around the gold's fullest day: steps to each side | share of the gold posts inside | posts "
      "the product has inside | characters ==")
for r in RANGES:
    row = []
    for name, digits in (("share of the gold posts", 2), ("posts", 0), ("characters", 0)):
        q1, mid, q3 = np.percentile(inside[r][name], [25, 50, 75])
        row.append(f"{mid:,.{digits}f} ({q1:,.{digits}f}-{q3:,.{digits}f})")
    print(f"  {r}: " + " | ".join(row))
print("done", flush=True)

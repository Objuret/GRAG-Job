"""After `what_ties_the_gold_posts` (posts of the same day as a gold post are gold 75%, from a post
that is not gold 0.8%): is the day what holds a question's gold together across channels and
kinds, and do the chunks the first search lands on point at those days.

On the hundred, inside the gold's branch, cached query side, no model call. A post's day is the
calendar day of its own time (a message's timestamp, a document's or meeting's date, a pull
request's created_at).

Printed:
  - the days a question's gold lies on, how many posts the product has on those days and how
    many of them are gold;
  - from a gold post, posts of the same day in ANOTHER channel or kind: how many are gold;
  - the days ranked by the posts of the chunks the first order delivers (each post one vote for
    its day), then everything the product has on those days delivered day by day until 72,000
    characters: the cited records delivered. And the same with the days known from the gold, as
    the most this way could give.
The construction is the agent's own; the gold ids are read inside and only numbers are printed.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/the_days_of_the_gold.py [gold100]
"""
import json
import os
import sys
import warnings
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")
os.environ["HERB_V4_OFFLINE"] = "on"
os.environ["HERB_V4_SCOPE_STEP"] = "both"

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _load_verified_doc, _resolve_chunk  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402

SET = sys.argv[1] if len(sys.argv) > 1 else "gold100"
BUDGET = 72000
CACHE = REPO / "output/private/artefact_v4_cache/querytag"


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


wanted = [json.loads(line)["id"] for line in (REPO / "data" / f"{SET}.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("the days of the gold")
layer, n = p.layer, len(p.chunk_ids)
id_rank = layer["id_rank"]
et, ec = layer["edge_tag"], layer["edge_chunk"]
docs, chunk_ids, length, chunk_file, sections_of = {}, [], np.zeros(n, dtype=np.int64), [], defaultdict(set)
for i, row in enumerate(p.chunk_rows):
    text, ids = _resolve_chunk(row, docs)
    length[i] = len(text)
    chunk_ids.append([str(x) for x in ids])
    chunk_file.append(row["relpath"])
    sections_of[row["relpath"], row["sha256"]].add(json.loads(row["locator"])["section"])
record_sets = [frozenset(ids) for ids in chunk_ids]
branches = V.tree_level(p.tree, "product")
branch_of = np.full(n, -1, dtype=np.int64)
for b, (_, chunks) in enumerate(branches):
    branch_of[chunks] = b
posts = {}
for (relpath, sha), sections in sections_of.items():
    doc = _load_verified_doc(relpath, sha, docs)
    here = {}
    for section in sorted(sections):
        for record in doc[section]:
            if not isinstance(record, dict) or record.get("id") is None:
                continue
            message = record.get("Message") or {}
            when = (stamp((message.get("User") or {}).get("timestamp")) if "Message" in record
                    else stamp(record.get("date") if "date" in record else record.get("created_at")))
            here[str(record["id"])] = {
                "size": len(json.dumps(record, ensure_ascii=False)) + 1, "section": section,
                "channel": (record.get("Channel") or {}).get("channelID") if "Channel" in record else section,
                "day": datetime.fromtimestamp(when, timezone.utc).date().isoformat() if when is not None else None}
    on_day = defaultdict(list)
    for rid, post in here.items():
        if post["day"] is not None:
            on_day[post["day"]].append(rid)
    posts[relpath] = (here, on_day)


def cached_sides():
    out = []
    for f in CACHE.glob("*.json"):
        if f.name.endswith(".started.json"):
            continue
        try:
            j = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        got = j.get("raw")
        if j.get("ok") and isinstance(got, dict) and got.get("description") and got.get("tags"):
            out.append((f.stat().st_mtime, (j.get("signature") or {}).get("user") or "", got))
    return sorted(out, key=lambda row: -row[0])


SIDES = cached_sides()


def side_of(q):
    def names(rows):
        return list(dict.fromkeys(str(r["t"]).strip() for r in rows or []
                                  if isinstance(r, dict) and str(r.get("t", "")).strip()))
    for _, user, got in SIDES:
        if q.question in user:
            return str(got["description"]), names(got.get("tags")), names(got.get("query_tags"))
    raise SystemExit(f"no cached first call for {q.id}")


def kept_of(order):
    fits = np.cumsum(length[order]) <= BUDGET
    return int(fits.sum()) if fits.all() else int(np.argmin(fits))


def standing(x):
    mid = np.median(x)
    spread = 1.4826 * np.median(np.abs(x - mid))
    return (x - mid) / spread if spread > 0 else np.zeros_like(x)


facts = defaultdict(list)
across = Counter()
recall, sent, sent_gold, days_sent = (defaultdict(list) for _ in range(4))
done = 0
for qid in wanted:
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    description, tags, asked = side_of(q)
    answer, _, _ = V._tag_cosines(description, tags, p)
    rows, d_description = list(answer["tags"]), np.asarray(answer["description"], dtype=np.float64)
    if asked:
        rows += list(V._tag_cosines(description, asked, p)[0]["tags"])
    rows = np.array(rows, dtype=np.float64)
    d_question = np.asarray(V._query_cosines(q.question, [], p)[0]["query_description_cosines"], dtype=np.float64)
    gold = np.array([bool(record_sets[i] & cites) for i in range(n)])
    main = Counter(branch_of[np.flatnonzero(gold)].tolist()).most_common(1)[0][0]
    inside = np.flatnonzero(branch_of == main)
    here, on_day = posts[chunk_file[int(inside[0])]]
    gold_posts = [r for r in cites if r in here]
    gold_days = Counter(here[r]["day"] for r in gold_posts if here[r]["day"] is not None)
    on_gold_days = [r for day in gold_days for r in on_day[day]]
    facts["days the gold lies on"].append(len(gold_days))
    facts["days the product has posts on"].append(len(on_day))
    facts["posts the product has on the gold's days"].append(len(on_gold_days))
    facts["share of those posts that are gold"].append(
        sum(1 for r in on_gold_days if r in cites) / max(len(on_gold_days), 1))
    facts["share of the gold on its two fullest days"].append(
        sum(c for _, c in gold_days.most_common(2)) / max(len(gold_posts), 1))
    for r in gold_posts:
        day = here[r]["day"]
        if day is None:
            continue
        for other in on_day[day]:
            if other != r and here[other]["channel"] != here[r]["channel"]:
                across["reached"] += 1
                across["gold"] += int(other in cites)

    t_near, t_edge = WK.best_edges(rows[:, et].max(axis=0), ec, n)
    t_near = np.where(t_edge >= 0, t_near, t_near[t_edge >= 0].min())
    base = standing(t_near[inside]) + standing(d_description[inside]) + standing(d_question[inside])
    order = inside[np.lexsort((id_rank[inside], -base))]
    ended = order[:kept_of(order)].tolist()
    plain = set().union(*(record_sets[c] for c in ended)) if ended else set()
    recall["the chunks as they are"].append(len(cites & plain) / len(cites))
    sent["the chunks as they are"].append(len(plain))
    sent_gold["the chunks as they are"].append(len(cites & plain))
    days_sent["the chunks as they are"].append(0)

    def by_days(name, ranked_days):
        have, used, count = set(), 0, 0
        for day in ranked_days:
            fresh = [r for r in on_day[day] if r not in have]
            cost = sum(here[r]["size"] for r in fresh)
            if used + cost > BUDGET:
                break
            used += cost
            count += 1
            have.update(fresh)
        recall[name].append(len(cites & have) / len(cites))
        sent[name].append(len(have))
        sent_gold[name].append(len(cites & have))
        days_sent[name].append(count)

    for label, starts in (("the chunks the first order delivers", ended), ("the nearest 5 chunks", order[:5].tolist()),
                          ("the nearest chunk", order[:1].tolist())):
        votes = Counter()
        first_seen = {}
        for rank, c in enumerate(starts):
            for r in chunk_ids[c]:
                day = here.get(r, {}).get("day")
                if day is not None:
                    votes[day] += 1
                    first_seen.setdefault(day, rank)
        ranked = sorted(votes, key=lambda d: (-votes[d], first_seen[d], d))
        by_days(f"whole days, ranked by the posts of {label}", ranked)
        ranked = sorted(votes, key=lambda d: (first_seen[d], -votes[d], d))
        by_days(f"whole days, in the order {label} reach them", ranked)
    by_days("whole days, the gold's own days from the fullest (the most this way could give)",
            [d for d, _ in gold_days.most_common()])
    done += 1
    if done % 20 == 0:
        print(f"  ... {done} questions", flush=True)

print(f"\n{SET}: {len(wanted)} questions, inside the gold's branch; budget {BUDGET} characters")
print("== the gold and the days, per question, the middle (a quarter - three quarters) ==")
for name, values in facts.items():
    q1, mid, q3 = np.percentile(values, [25, 50, 75])
    digits = 2 if "share" in name else 0
    print(f"  {name}: {mid:.{digits}f} ({q1:.{digits}f}-{q3:.{digits}f})")
print(f"  from a gold post, posts of the same day in another channel or kind: {across['gold']} gold of "
      f"{across['reached']} ({(across['gold'] / across['reached'] if across['reached'] else 0):.3f})")
first = "the chunks as they are"
print("\n== delivered inside the budget: context_recall_id | against the chunks as they are: mean difference, its "
      "standard error, questions higher / lower | records delivered | of them cited | whole days delivered (middles) ==")
for name in recall:
    diff = np.asarray(recall[name]) - np.asarray(recall[first])
    print(f"  {float(np.mean(recall[name])):.3f} | {float(diff.mean()):+.3f}, "
          f"{float(diff.std(ddof=1) / np.sqrt(diff.size)):.3f}, {int((diff > 0).sum())} / {int((diff < 0).sum())} | "
          f"{np.median(sent[name]):.0f} | {np.median(sent_gold[name]):.0f} | {np.median(days_sent[name]):.0f}  {name}")
print("done", flush=True)

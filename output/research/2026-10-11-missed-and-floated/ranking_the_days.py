"""After `the_days_of_the_gold` (a question's gold lies on about 6 of a product's 170 days; those
days delivered whole give 0.985): how to rank the days without gold and without a model.

On the hundred, inside the gold's branch, cached query side, no model call. A day's value is made
from what the graph already gives each chunk (the three routes' standings added), carried to the
day by the chunk's posts: every post takes its chunk's value.
  sum      the day's posts' values added, counting only posts above the middle of the branch
  mean     the mean of the day's posts' values
  best     the day's highest post value
  top 3    the mean of the day's three highest post values
Beside them, as a diagnosis only: the question's own words against the whole day's text (BM25,
the day as one document among the product's days), alone and added to `sum` as a standing.

Days are delivered whole, the highest first, until 72,000 characters; delivery stops at the first
day that does not fit. Printed: context_recall_id, the place of the gold's fullest day, and how
many of the gold's days are among the delivered. The construction is the agent's own.

The gold ids and the question texts are read inside this script; it prints numbers only.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/ranking_the_days.py [gold100]
"""
import json
import math
import os
import re
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
K1, B = 1.2, 0.75
TOKEN = re.compile(r"[a-z0-9]+")


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


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)


wanted = [json.loads(line)["id"] for line in (REPO / "data" / f"{SET}.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("ranking the days")
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
                "size": len(json.dumps(record, ensure_ascii=False)) + 1,
                "words": Counter(TOKEN.findall(" ".join(strings(record)).lower())),
                "day": datetime.fromtimestamp(when, timezone.utc).date().isoformat() if when is not None else None}
    on_day = defaultdict(list)
    for rid, post in here.items():
        if post["day"] is not None:
            on_day[post["day"]].append(rid)
    day_words = {day: sum((here[r]["words"] for r in members), Counter()) for day, members in on_day.items()}
    held = Counter()
    for words in day_words.values():
        held.update(words.keys())
    size = {day: sum(words.values()) for day, words in day_words.items()}
    posts[relpath] = (here, on_day, day_words, held, size)


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
    x = np.asarray(x, dtype=np.float64)
    mid = np.median(x)
    spread = 1.4826 * np.median(np.abs(x - mid))
    return (x - mid) / spread if spread > 0 else np.zeros_like(x)


recall, place_of_fullest, gold_days_in, days_sent = (defaultdict(list) for _ in range(4))
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
    here, on_day, day_words, held, size = posts[chunk_file[int(inside[0])]]
    gold_days = Counter(here[r]["day"] for r in cites if r in here and here[r]["day"] is not None)
    fullest = gold_days.most_common(1)[0][0] if gold_days else None
    t_near, t_edge = WK.best_edges(rows[:, et].max(axis=0), ec, n)
    t_near = np.where(t_edge >= 0, t_near, t_near[t_edge >= 0].min())
    base = standing(t_near[inside]) + standing(d_description[inside]) + standing(d_question[inside])
    order = inside[np.lexsort((id_rank[inside], -base))]
    ended = order[:kept_of(order)].tolist()
    plain = set().union(*(record_sets[c] for c in ended)) if ended else set()
    recall["the chunks as they are"].append(len(cites & plain) / len(cites))
    # every post takes its chunk's value (the highest when several chunks hold it)
    value_of = {}
    for k, c in enumerate(inside.tolist()):
        for r in chunk_ids[c]:
            if r in here and (r not in value_of or base[k] > value_of[r]):
                value_of[r] = float(base[k])
    days = sorted(on_day)
    per_day = {day: sorted((value_of[r] for r in on_day[day] if r in value_of), reverse=True) for day in days}
    days = [day for day in days if per_day[day]]
    scores = {
        "sum of the posts above the middle": [sum(v for v in per_day[d] if v > 0) for d in days],
        "mean of the day's posts": [float(np.mean(per_day[d])) for d in days],
        "the day's best post": [per_day[d][0] for d in days],
        "mean of the day's three best posts": [float(np.mean(per_day[d][:3])) for d in days],
    }
    asked_words = set(TOKEN.findall(q.question.lower()))
    mean_size = float(np.mean([size[d] for d in days]))
    own = []
    for d in days:
        total = 0.
        for word in asked_words:
            tf = day_words[d].get(word, 0)
            if tf:
                idf = math.log(1. + (len(day_words) - held[word] + .5) / (held[word] + .5))
                total += idf * tf * (K1 + 1.) / (tf + K1 * (1. - B + B * size[d] / mean_size))
        own.append(total)
    scores["the question's own words against the day's text (diagnosis)"] = own
    scores["sum of the posts above the middle + the question's own words, standings added (diagnosis)"] = (
        standing(scores["sum of the posts above the middle"]) + standing(own)).tolist()
    scores["mean of the day's three best posts + the question's own words, standings added (diagnosis)"] = (
        standing(scores["mean of the day's three best posts"]) + standing(own)).tolist()
    for name, values in scores.items():
        ranked = [d for _, d in sorted(zip(values, days), key=lambda pair: (-pair[0], pair[1]))]
        have, used, count = set(), 0, 0
        for day in ranked:
            fresh = [r for r in on_day[day] if r not in have]
            cost = sum(here[r]["size"] for r in fresh)
            if used + cost > BUDGET:
                break
            used += cost
            count += 1
            have.update(fresh)
        recall[name].append(len(cites & have) / len(cites))
        days_sent[name].append(count)
        if fullest in ranked:
            place_of_fullest[name].append(1 + ranked.index(fullest))
        gold_days_in[name].append(sum(1 for d in ranked[:count] if d in gold_days) / max(len(gold_days), 1))
    done += 1
    if done % 20 == 0:
        print(f"  ... {done} questions", flush=True)

first = "the chunks as they are"
print(f"\n{SET}: {len(wanted)} questions, inside the gold's branch; whole days delivered inside {BUDGET} characters")
print("== context_recall_id | against the chunks as they are: mean difference, its standard error, questions higher / "
      "lower | days delivered, the middle | place of the gold's fullest day, the middle (a quarter - three quarters) "
      "| share of the gold's days among the delivered, mean ==")
for name in recall:
    diff = np.asarray(recall[name]) - np.asarray(recall[first])
    extra = ""
    if name != first:
        places = place_of_fullest[name]
        extra = (f" | {np.median(days_sent[name]):.0f} | {np.median(places):.0f} ({np.percentile(places, 25):.0f}-"
                 f"{np.percentile(places, 75):.0f}) | {float(np.mean(gold_days_in[name])):.2f}")
    print(f"  {float(np.mean(recall[name])):.3f} | {float(diff.mean()):+.3f}, "
          f"{float(diff.std(ddof=1) / np.sqrt(diff.size)):.3f}, {int((diff > 0).sum())} / {int((diff < 0).sum())}"
          f"{extra}  {name}")
print("done", flush=True)

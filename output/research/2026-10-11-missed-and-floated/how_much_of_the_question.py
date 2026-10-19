"""The agent's own idea, 2026-10-11: not how near one chunk is, but how much of the question a whole
day (or a chunk) answers. A question has about ten query tags. For a unit, each query tag takes
its best match among the unit's tags; the unit's value is those best matches added up over the
query tags, each first put on its own scale across the units (the value less the middle over the
spread), so one strong match cannot stand in for all the others.

On the hundred, inside the question's product, cached query side, no model call.
  days    a day's tags are the tags of every chunk with a post on that day; days are delivered
          whole, the highest first, until 72,000 characters
  chunks  the same reading per chunk, in place of the single best match the tags' route uses now,
          with the two description routes added as before
Printed: the place of the gold's fullest day, context_recall_id against the plain order, and how
many of a question's query tags have a same-thing match on the gold's fullest day against an
ordinary day.

The gold ids are read inside this script; it prints numbers only.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/how_much_of_the_question.py [gold100]
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
p = V.prepare_over_corpus("how much of the question")
layer, n = p.layer, len(p.chunk_ids)
id_rank = layer["id_rank"]
et, ec, eligible = layer["edge_tag"], layer["edge_chunk"], layer["eligible"]
same = next((h["same_thing_pairs"] for h in (getattr(p, "provenance", None), V.RETRIEVAL_FLAGS)
             if isinstance(h, dict) and isinstance(h.get("same_thing_pairs"), dict)), None)
SAME = float(same["level"])
docs, chunk_ids, length, chunk_days, post_day, post_size, chunk_file = {}, [], np.zeros(n, dtype=np.int64), [], {}, {}, []
for i, row in enumerate(p.chunk_rows):
    text, ids = _resolve_chunk(row, docs)
    length[i] = len(text)
    chunk_ids.append([str(x) for x in ids])
    chunk_file.append(row["relpath"])
    loc = json.loads(row["locator"])
    arr = _load_verified_doc(row["relpath"], row["sha256"], docs)[loc["section"]]
    days = set()
    for r in [arr[k] for k in (loc["indices"] if "indices" in loc else [loc["index"]])]:
        message = r.get("Message") or {}
        when = (stamp((message.get("User") or {}).get("timestamp")) if "Message" in r
                else stamp(r.get("date") if "date" in r else r.get("created_at")))
        if when is not None and r.get("id") is not None:
            day = datetime.fromtimestamp(when, timezone.utc).date().isoformat()
            days.add(day)
            post_day[row["relpath"], str(r["id"])] = day
            post_size[row["relpath"], str(r["id"])] = len(json.dumps(r, ensure_ascii=False)) + 1
    chunk_days.append(days)
record_sets = [frozenset(ids) for ids in chunk_ids]
branches = V.tree_level(p.tree, "product")
branch_of = np.full(n, -1, dtype=np.int64)
for b, (_, chunks) in enumerate(branches):
    branch_of[chunks] = b


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


def standing(x, axis=None):
    x = np.asarray(x, dtype=np.float64)
    mid = np.median(x, axis=axis, keepdims=axis is not None)
    spread = 1.4826 * np.median(np.abs(x - mid), axis=axis, keepdims=axis is not None)
    return np.where(spread > 0, (x - mid) / np.where(spread > 0, spread, 1.), 0.)


recall, places, facts = defaultdict(list), defaultdict(list), defaultdict(list)
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
    here = np.zeros(n, dtype=bool)
    here[inside] = True
    at = np.full(n, -1, dtype=np.int64)
    at[inside] = np.arange(inside.size)
    edges = np.flatnonzero(here[ec])
    # per query tag and chunk: the chunk's best match to that query tag
    fit = np.full((rows.shape[0], inside.size), rows[:, eligible].min())
    np.maximum.at(fit.T, at[ec[edges]], rows[:, et[edges]].T)
    relpath = chunk_file[int(inside[0])]
    days = sorted({d for c in inside.tolist() for d in chunk_days[c]})
    day_at = {d: k for k, d in enumerate(days)}
    day_fit = np.full((rows.shape[0], len(days)), fit.min())
    for k, c in enumerate(inside.tolist()):
        for d in chunk_days[c]:
            day_fit[:, day_at[d]] = np.maximum(day_fit[:, day_at[d]], fit[:, k])
    gold_days = Counter(post_day[relpath, r] for r in cites if (relpath, r) in post_day)
    fullest = gold_days.most_common(1)[0][0] if gold_days else None
    on_day = defaultdict(list)
    for (path, rid), d in post_day.items():
        if path == relpath:
            on_day[d].append(rid)
    covered = (day_fit >= SAME).sum(axis=0)
    if fullest in day_at:
        facts["query tags with a same-thing match on the gold's fullest day"].append(int(covered[day_at[fullest]]))
        facts["on a day of the product, the middle"].append(float(np.median(covered)))
        facts["query tags of the question"].append(rows.shape[0])
    scores = {
        "days by how much of the question they answer (best match per query tag, each on its own scale, added)":
            standing(day_fit, axis=1).sum(axis=0),
        "days by how many query tags have a same-thing match there": covered.astype(np.float64)
        + 1e-6 * standing(day_fit, axis=1).sum(axis=0),
        "days by their single best match": day_fit.max(axis=0),
    }
    base = standing(fit.max(axis=0)) + standing(d_description[inside]) + standing(d_question[inside])
    order = inside[np.lexsort((id_rank[inside], -base))]
    kept = order[:kept_of(order)]
    got = set().union(*(record_sets[i] for i in kept)) if kept.size else set()
    recall["chunks, the plain order"].append(len(cites & got) / len(cites))
    covering = standing(standing(fit, axis=1).sum(axis=0)) + standing(d_description[inside]) + standing(d_question[inside])
    order = inside[np.lexsort((id_rank[inside], -covering))]
    kept = order[:kept_of(order)]
    got = set().union(*(record_sets[i] for i in kept)) if kept.size else set()
    recall["chunks, the tags' part read as how much of the question the chunk answers"].append(len(cites & got) / len(cites))
    for name, values in scores.items():
        ranked = [d for _, d in sorted(zip(values.tolist(), days), key=lambda pair: (-pair[0], pair[1]))]
        have, used = set(), 0
        for d in ranked:
            fresh = [r for r in on_day[d] if r not in have]
            cost = sum(post_size[relpath, r] for r in fresh)
            if used + cost > BUDGET:
                break
            used += cost
            have.update(fresh)
        recall[name].append(len(cites & have) / len(cites))
        if fullest in ranked:
            places[name].append(1 + ranked.index(fullest))
    done += 1
    if done % 20 == 0:
        print(f"  ... {done} questions", flush=True)

print(f"\n{SET}: {len(wanted)} questions, inside the question's product")
for name, values in facts.items():
    q1, mid, q3 = np.percentile(values, [25, 50, 75])
    print(f"  {name}: {mid:.0f} ({q1:.0f}-{q3:.0f})")
first = "chunks, the plain order"
print("\n== context_recall_id | against the plain order: mean difference, its standard error, questions higher / "
      "lower | place of the gold's fullest day among the days, the middle (a quarter - three quarters); first on ==")
for name in recall:
    diff = np.asarray(recall[name]) - np.asarray(recall[first])
    extra = ""
    if places[name]:
        v = places[name]
        extra = (f" | {np.median(v):.0f} ({np.percentile(v, 25):.0f}-{np.percentile(v, 75):.0f}); "
                 f"{sum(1 for x in v if x == 1)} of {len(v)}")
    print(f"  {float(np.mean(recall[name])):.3f} | {float(diff.mean()):+.3f}, "
          f"{float(diff.std(ddof=1) / np.sqrt(diff.size)):.3f}, {int((diff > 0).sum())} / {int((diff < 0).sum())}"
          f"{extra}  {name}")
print("done", flush=True)

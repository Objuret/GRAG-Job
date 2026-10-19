"""His 2026-10-11 "should we not check time-nearness both to eachother and to "now" unless time is
mentioned in query, then nearness to that? and by that i mean using it as a ranking-weight".

On the hundred, inside the gold's branch, cached query side, no model call. Time is read post by
post (a message's timestamp, a document's or meeting's date, a pull request's created_at); a post
takes the value its chunk has in the first order (the three routes' standings added).

  to each other   a post's weight is the sum, over the posts of OTHER chunks, of their value
                  above the middle, each through a Gaussian kernel on the time between the two
                  posts; the kernel's width by Silverman's rule from the times of the posts with a
                  value above the middle. A chunk's weight is the mean over its posts.
  to each other,  the same with every post of a hit chunk counting one, whatever its value
    hits only
  to "now"        how late the chunk's posts are; "now" is the product's last post, since a
                  question carries no date of asking
Each weight is added to the first order as a standing. Printed: how many questions name a time,
where the gold lies on the product's timeline, and context_recall_id inside 72,000 against the
first order, question by question. The construction is the agent's reading of his sentence.

The gold ids and the question texts are read inside this script; it prints numbers only.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/time_as_a_weight.py [gold100]
"""
import json
import os
import re
import sys
import warnings
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
from scipy.stats import rankdata

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
K = V._k_nearest()
NAMES_A_TIME = {
    "a year": re.compile(r"\b(?:19|20)\d{2}\b"),
    "a month": re.compile(r"\b(?:january|february|march|april|may|june|july|august|september|october|november|"
                          r"december)\b", re.I),
    "a date": re.compile(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b"),
    "a weekday": re.compile(r"\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", re.I),
    "a quarter or week": re.compile(r"\bq[1-4]\b|\bquarter\b|\bweek\b", re.I),
    "latest, recent, current, newest": re.compile(r"\b(?:latest|recent|recently|current|currently|newest|now)\b", re.I),
    "first, initial, earliest, original": re.compile(r"\b(?:first|initial|initially|earliest|original|originally)\b", re.I),
    "last, final": re.compile(r"\b(?:last|final|finally)\b", re.I),
    "before, after, since, during": re.compile(r"\b(?:before|after|since|during|prior|following)\b", re.I),
}


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
p = V.prepare_over_corpus("time as a weight")
layer, n = p.layer, len(p.chunk_ids)
id_rank = layer["id_rank"]
et, ec, eligible = layer["edge_tag"], layer["edge_chunk"], layer["eligible"]
docs, chunk_ids, length, chunk_times, chunk_file = {}, [], np.zeros(n, dtype=np.int64), [], []
for i, row in enumerate(p.chunk_rows):
    text, ids = _resolve_chunk(row, docs)
    length[i] = len(text)
    chunk_ids.append([str(x) for x in ids])
    chunk_file.append((row["relpath"], row["sha256"]))
    loc = json.loads(row["locator"])
    arr = _load_verified_doc(row["relpath"], row["sha256"], docs)[loc["section"]]
    times = []
    for r in [arr[k] for k in (loc["indices"] if "indices" in loc else [loc["index"]])]:
        message = r.get("Message") or {}
        t = (stamp((message.get("User") or {}).get("timestamp")) if "Message" in r
             else stamp(r.get("date") if "date" in r else r.get("created_at")))
        if t is not None:
            times.append(t)
    chunk_times.append(np.asarray(times, dtype=np.float64))
record_sets = [frozenset(ids) for ids in chunk_ids]
record_time = {}
for ids, row in zip(chunk_ids, p.chunk_rows):
    pass
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


def standing(x):
    x = np.asarray(x, dtype=np.float64)
    mid = np.median(x)
    spread = 1.4826 * np.median(np.abs(x - mid))
    return (x - mid) / spread if spread > 0 else np.zeros_like(x)


def silverman(times):
    times = np.asarray(times, dtype=np.float64)
    if times.size < 2:
        return 1.
    q75, q25 = np.percentile(times, [75, 25])
    spread = min(times.std(ddof=1), (q75 - q25) / 1.34) or times.std(ddof=1) or 1.
    return 0.9 * spread * times.size ** (-0.2)


named = Counter()
any_time = 0
gold_standing, late_quarter, widths = [], [], []
recall = defaultdict(list)
done = 0
for qid in wanted:
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    hit_kinds = [name for name, pattern in NAMES_A_TIME.items() if pattern.search(q.question)]
    named.update(hit_kinds)
    any_time += int(bool(hit_kinds))
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
    place_of_tag = np.full(rows.shape, np.inf)
    place_of_tag[:, eligible] = np.array([rankdata(-row[eligible], method="min") for row in rows])
    best_place = np.full(n, np.inf)
    np.minimum.at(best_place, ec, place_of_tag[:, et].min(axis=0))
    t_near, t_edge = WK.best_edges(rows[:, et].max(axis=0), ec, n)
    t_near = np.where(t_edge >= 0, t_near, t_near[t_edge >= 0].min())
    base = standing(t_near[inside]) + standing(d_description[inside]) + standing(d_question[inside])
    found = ((best_place[inside] <= K) | (WK.levels(d_description[inside], K) == 1)
             | (WK.levels(d_question[inside], K) == 1))
    # the posts of the branch: time, the chunk they sit in, that chunk's value
    post_time = np.concatenate([chunk_times[c] for c in inside])
    post_chunk = np.concatenate([np.full(chunk_times[c].size, k, dtype=np.int64) for k, c in enumerate(inside)])
    if post_time.size < 3:
        continue
    post_value = np.maximum(base[post_chunk], 0.)
    post_hit = found[post_chunk].astype(np.float64)
    # where the gold lies on the product's timeline
    order_in_time = rankdata(post_time, method="average") / post_time.size
    is_gold_post = gold[inside][post_chunk]
    gold_standing.append(float(np.median(order_in_time[is_gold_post])) if is_gold_post.any() else np.nan)
    late_quarter.append(float((order_in_time[is_gold_post] > 0.75).mean()) if is_gold_post.any() else np.nan)

    def weight_from(mass, days=None):
        width = (days * 86400. if days is not None else
                 silverman(post_time[mass > 0]) if (mass > 0).sum() >= 2 else silverman(post_time))
        if days is None:
            widths.append(width / 86400.)
        gap = (post_time[:, None] - post_time[None, :]) / width
        kernel = np.exp(-0.5 * gap * gap)
        kernel[post_chunk[:, None] == post_chunk[None, :]] = 0.          # a chunk's own posts do not vote for it
        density = kernel @ mass
        out = np.full(inside.size, np.nan)
        sums = np.bincount(post_chunk, weights=density, minlength=inside.size)
        counts = np.bincount(post_chunk, minlength=inside.size)
        has = counts > 0
        out[has] = sums[has] / counts[has]
        out[~has] = np.nanmin(out[has])
        return out

    each_other = weight_from(post_value)
    each_other_hits = weight_from(post_hit)
    counts = np.bincount(post_chunk, minlength=inside.size)
    mean_time = np.where(counts > 0, np.bincount(post_chunk, weights=post_time, minlength=inside.size)
                         / np.maximum(counts, 1), post_time.min())

    def score(name, value):
        order = inside[np.lexsort((id_rank[inside], -value))]
        kept = order[:kept_of(order)]
        got = set().union(*(record_sets[i] for i in kept)) if kept.size else set()
        recall[name].append(len(cites & got) / len(cites))

    score("the first order: the three routes' standings added", base)
    score("+ time-nearness to each other (weighted by the other posts' values)", base + standing(each_other))
    score("+ time-nearness to each other (posts of hit chunks only)", base + standing(each_other_hits))
    score("time-nearness to each other alone", standing(each_other))
    for days in (0.25, 1., 3., 7.):
        score(f"+ time-nearness to each other, the kernel {days:g} days wide", base + standing(weight_from(post_value, days)))
        score(f"+ the same, every post of the branch counting one whatever its value ({days:g} days)", base + standing(weight_from(np.ones_like(post_value), days)))
    score("+ nearness to now (later counts for more)", base + standing(mean_time))
    score("+ the other way round (earlier counts for more)", base - standing(mean_time))
    done += 1
    if done % 20 == 0:
        print(f"  ... {done} questions", flush=True)

m = len(wanted)
print(f"\n{SET}: {m} questions")
print(f"== questions that name a time in some way: {any_time} of {m}; by kind: "
      + ", ".join(f"{name} {named[name]}" for name in NAMES_A_TIME) + " ==")
g = np.asarray([v for v in gold_standing if not np.isnan(v)])
lq = np.asarray([v for v in late_quarter if not np.isnan(v)])
print(f"== where the gold lies on the product's timeline (0 the first post, 1 the last): the middle of a question's "
      f"gold posts, over the questions: {np.median(g):.2f} ({np.percentile(g, 25):.2f}-{np.percentile(g, 75):.2f}); "
      f"share of the gold posts in the last quarter of the timeline, mean {float(lq.mean()):.2f} ==")
print(f"== the kernel's width, in days, the middle: {np.median(widths):.1f} ({np.percentile(widths, 25):.1f}-"
      f"{np.percentile(widths, 75):.1f}) ==")
first = "the first order: the three routes' standings added"
print("\n== inside 72,000 characters: context_recall_id | against the first order: mean difference, its standard error, "
      "questions higher / lower ==")
for name in recall:
    diff = np.asarray(recall[name]) - np.asarray(recall[first])
    print(f"  {float(np.mean(recall[name])):.3f} | {float(diff.mean()):+.3f}, "
          f"{float(diff.std(ddof=1) / np.sqrt(diff.size)):.3f}, {int((diff > 0).sum())} / {int((diff < 0).sum())}  {name}")
print("done", flush=True)

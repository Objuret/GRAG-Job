"""The agent's own question, 2026-10-11: are the graph's Slack batches cut in the wrong places. A
batch is cut by size; a conversation is the messages of one channel on one calendar day. If a
batch that is one conversation is found and floated more often than a batch that mixes several,
the cut matters.

On the hundred, inside the question's product, cached query side, no model call. For every Slack
batch: how many conversations its messages belong to, and the share of its messages in the
largest of them. For the gold Slack batches of a question: found (a picked tag, or the first of 5
clusters of the description nearness) and floated (inside 72,000 by the three routes' standings
added), by how mixed the batch is; and the share of its messages that are cited.

The gold ids are read inside this script; it prints numbers only.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/is_the_unit_wrong.py [gold100]
"""
import json
import os
import sys
import warnings
from collections import Counter, defaultdict
from datetime import datetime, timezone
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
BANDS = ("one conversation", "two, the larger at least three quarters", "two, more even", "three or more")


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
p = V.prepare_over_corpus("is the unit wrong")
layer, n = p.layer, len(p.chunk_ids)
id_rank = layer["id_rank"]
kind_names, kind_of = layer["kind_names"], layer["kind"]
et, ec, eligible = layer["edge_tag"], layer["edge_chunk"], layer["eligible"]
slack = kind_names.index("slack_thread_batch")
docs, records, length = {}, [], np.zeros(n, dtype=np.int64)
talks, largest, mixed, talk_keys = np.zeros(n, dtype=np.int64), np.zeros(n), [None] * n, [None] * n
for i, row in enumerate(p.chunk_rows):
    text, ids = _resolve_chunk(row, docs)
    records.append(frozenset(str(x) for x in ids))
    length[i] = len(text)
    if kind_of[i] != slack:
        continue
    loc = json.loads(row["locator"])
    arr = _load_verified_doc(row["relpath"], row["sha256"], docs)[loc["section"]]
    keys = {}
    for r in [arr[k] for k in (loc["indices"] if "indices" in loc else [loc["index"]])]:
        when = stamp(((r.get("Message") or {}).get("User") or {}).get("timestamp"))
        if when is not None and r.get("id") is not None:
            keys[str(r["id"])] = ((r.get("Channel") or {}).get("channelID"),
                                  datetime.fromtimestamp(when, timezone.utc).date().isoformat())
    count = Counter(keys.values())
    talk_keys[i] = keys
    talks[i] = len(count)
    largest[i] = max(count.values()) / max(sum(count.values()), 1) if count else 0.
    mixed[i] = (BANDS[0] if len(count) <= 1 else BANDS[3] if len(count) >= 3
                else BANDS[1] if largest[i] >= .75 else BANDS[2])
all_slack = np.flatnonzero(kind_of == slack)
print(f"Slack batches in the pool: {all_slack.size}; conversations a batch's messages belong to: "
      + ", ".join(f"{k}: {int((talks[all_slack] == k).sum())}" for k in sorted(set(talks[all_slack].tolist()))), flush=True)
print("  by how mixed: " + ", ".join(f"{band} {sum(1 for c in all_slack if mixed[c] == band)}" for band in BANDS), flush=True)
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
    mid = np.median(x)
    spread = 1.4826 * np.median(np.abs(x - mid))
    return (x - mid) / spread if spread > 0 else np.zeros_like(x)


cells = defaultdict(lambda: Counter())
cited_share = defaultdict(list)
gold_talks_in = defaultdict(list)
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
    gold = np.array([bool(records[i] & cites) for i in range(n)])
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
    order = inside[np.lexsort((id_rank[inside], -base))]
    floated = set(order[:kept_of(order)].tolist())
    for k, c in enumerate(inside.tolist()):
        if kind_of[c] != slack or not gold[c]:
            continue
        band = mixed[c]
        cells[band]["gold batches"] += 1
        cells[band]["found"] += int(found[k])
        cells[band]["floated"] += int(c in floated)
        keys = talk_keys[c] or {}
        cited_share[band].append(len(records[c] & cites) / max(len(records[c]), 1))
        # the conversations of the batch that hold a cited message, and whether the batch's largest one does
        cited_talks = {keys[r] for r in records[c] & cites if r in keys}
        gold_talks_in[band].append(len(cited_talks))
        if keys:
            top = Counter(keys.values()).most_common(1)[0][0]
            cells[band]["the cited messages are in its largest conversation"] += int(top in cited_talks)
    done += 1
    if done % 20 == 0:
        print(f"  ... {done} questions", flush=True)

print(f"\n{SET}: {len(wanted)} questions; the gold Slack batches by how mixed the batch is")
print("== gold batches | found | floated | share of its messages cited, the middle | the cited messages lie in its "
      "largest conversation ==")
for band in BANDS:
    c = cells[band]
    if not c["gold batches"]:
        continue
    g = c["gold batches"]
    print(f"  {band}: {g} | {c['found']} ({c['found'] / g:.2f}) | {c['floated']} ({c['floated'] / g:.2f}) | "
          f"{np.median(cited_share[band]):.2f} | {c['the cited messages are in its largest conversation']} "
          f"({c['the cited messages are in its largest conversation'] / g:.2f})")
print("done", flush=True)

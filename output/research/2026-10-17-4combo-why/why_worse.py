"""Why the 4-combo delivered less of the cited evidence than the clouds' order (his 2026-10-17 "why did i
tget worse?"). The arm is run over the hundred offline (no model call) with `v4_walk.storyline` watched:
per question, every chunk of the border with its ties to the chosen chunks, and whether one of its records
is cited (the hundred's citation ids; no question text is printed).

Prints, pooled over the hundred: how often the chosen chunks are cited; per way, how often a chunk it ties
is cited against one it does not tie; by strength, how often a chunk is cited; and where the cited chunks
stand in the clouds' order against the 4-combo's order.

    .venv/Scripts/python.exe output/research/2026-10-17-4combo-why/why_worse.py
"""
import json
import os
import sys
import warnings
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")
os.environ["HERB_V4_OFFLINE"] = "on"

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _load_verified_doc  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402

p = V.prepare_over_corpus("why worse")
docs, record_ids = {}, []
for row in p.chunk_rows:
    loc = json.loads(row["locator"])
    arr = _load_verified_doc(row["relpath"], row["sha256"], docs)[loc["section"]]
    recs = [arr[k] for k in (loc["indices"] if "indices" in loc else [loc["index"]])]
    record_ids.append({str(r["id"]) for r in recs if r.get("id") is not None})
wanted = [json.loads(line)["id"] for line in (REPO / "data/gold100.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}

seen = {}
real_storyline, real_combo = WK.storyline, WK.cloud_combo


def watched_storyline(n, start, pair_start, pair_chunk, *rest):
    out = real_storyline(n, start, pair_start, pair_chunk, *rest)
    seen.setdefault(threading_key(), {})["story"] = (np.asarray(start), np.asarray(pair_chunk), out)
    return out


def watched_combo(*a, **k):
    out = real_combo(*a, **k)
    seen.setdefault(threading_key(), {})["combo"] = out
    return out


def threading_key():
    import threading
    return threading.get_ident()


WK.storyline, WK.cloud_combo = watched_storyline, watched_combo
results = {}


def one(qid):
    q = by_id[qid]
    out = V.answer_one_question((qid, q.question), p, None, 50, 72000)
    got = seen.pop(threading_key())
    results[qid] = (out, got, {str(c) for c in q.citations})


with ThreadPoolExecutor(6) as pool:
    list(pool.map(one, wanted))

ways = ("scope", "entities", "time", "nearness")
tied = {w: [0, 0] for w in ways}      # [chunks, cited] among the tied
untied = {w: [0, 0] for w in ways}
chosen_stat, by_strength = [0, 0], defaultdict(lambda: [0, 0])
place_old, place_new, first_chunk = [], [], [0, 0]
for qid, (out, got, cites) in results.items():
    start, pair_chunk, story = got["story"]
    combo = got["combo"]
    cited = lambda i: bool(record_ids[i] & cites)  # noqa: E731
    for i in start:
        chosen_stat[0] += 1
        chosen_stat[1] += cited(int(i))
    for c in np.unique(pair_chunk):
        c = int(c)
        for w in ways:
            box = tied if story["ways"][w][c] > 0 else untied
            box[w][0] += 1
            box[w][1] += cited(c)
        s = int(story["strength"][c])
        by_strength[s][0] += 1
        by_strength[s][1] += cited(c)
    old = list(combo["order"])

    at = {cid: i for i, cid in enumerate(p.chunk_ids)}
    new = [at[c] for c in out.meta["ranking"]["ordered_chunk_ids"]]
    for order, into in ((old, place_old), (new, place_new)):
        into.extend(k + 1 for k, i in enumerate(order) if cited(i))
pct = lambda a: f"{a[1]}/{a[0]} ({100 * a[1] / a[0]:.1f}%)" if a[0] else "-"  # noqa: E731
print(f"\nthe hundred, offline: context_recall_id {np.mean([len(set(o.context_ids) & c) / len(c) for o, _, c in results.values() if c]):.4f}")
print(f"chosen chunks that hold a cited record: {pct(chosen_stat)}")
print("\n== per way, the other chunks of the border: tied by it, cited | not tied by it, cited ==")
for w in ways:
    print(f"   {w}: {pct(tied[w])} | {pct(untied[w])}")
print("\n== by strength (the ways added over the chosen chunks): chunks, cited ==")
for s in sorted(by_strength):
    print(f"   {s}: {pct(by_strength[s])}")
q = lambda xs: f"middle {np.median(xs):.0f} (quartiles {np.percentile(xs, 25):.0f}-{np.percentile(xs, 75):.0f})"  # noqa: E731
print(f"\nplaces of the chunks holding a cited record: in the clouds' order {q(place_old)}; in the 4-combo's order {q(place_new)}")
print("done")

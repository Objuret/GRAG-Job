"""After `what_is_on_top_when_not_gold` (his 2026-10-11 "it is INSANE if the top chunk is NOT a gold"):
three more readings of the first delivered unit, from the run folders, no model call.

  the baselines   lucene and vector on the same hundred deliver single records over the whole
                  corpus: is their first record a cited one, and where does the first cited
                  record stand. (A chunk of the artefact holds about ten records, so its first
                  chunk has about ten chances where a baseline's first record has one; the
                  baselines' first ten records are printed for that.)
  the same chunk on top for several questions
                  per run of the arm: how many questions have a first chunk that is also the
                  first chunk of another question of the same product, gold and not gold.
  mixed batches   the first chunk when it is a Slack batch: the conversations (one channel, one
                  day) it holds, gold and not gold.

The gold ids are read inside this script; it prints numbers only.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/what_is_on_top_more.py
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

from harness import questions as HQ  # noqa: E402

RUNS = REPO / "output" / "k=chars"
BASELINES = {"lucene": "lucene__gold100__cb72000__20260814T134547Z",
             "vector": "vector__gold100__cb72000__20260814T145615Z"}
ARM_RUNS = {"today's arm, name border": "artefact_v4__gold100__cb72000__20261011T164246Z_name",
            "the old arm, 10-06": "artefact_v4__gold100__cb72000__20261006T184959Z"}
by_id = {q.id: q for q in HQ.load_questions()}


def rows_of(name):
    return [json.loads(line) for line in (RUNS / name / "arm_outputs.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()]


print("== the baselines on the hundred (single records, the whole corpus): the first delivered record is a cited "
      "one | a cited record among the first three | among the first ten | no cited record delivered | records "
      "delivered, the middle | cited among them, the middle ==")
for label, name in BASELINES.items():
    first, three, ten, none, sent, sent_gold = [], [], [], [], [], []
    for row in rows_of(name):
        q = by_id.get(row["id"])
        ids = [str(x) for x in row.get("context_ids") or []]
        if q is None or not ids:
            continue
        cites = {str(c) for c in q.citations}
        hit = [i in cites for i in ids]
        first.append(hit[0])
        three.append(any(hit[:3]))
        ten.append(any(hit[:10]))
        none.append(not any(hit))
        sent.append(len(ids))
        sent_gold.append(sum(hit))
    print(f"  {label}: {sum(first)} of {len(first)} | {sum(three)} | {sum(ten)} | {sum(none)} | {np.median(sent):.0f} | "
          f"{np.median(sent_gold):.0f}")

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _load_verified_doc  # noqa: E402


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


p = V.prepare_over_corpus("what is on top, more")
layer, n = p.layer, len(p.chunk_ids)
id_rank, kind, kind_names = layer["id_rank"], layer["kind"], layer["kind_names"]
docs, record_sets, ordinal, talks = {}, [], np.zeros(n, dtype=np.int64), []
for i, row in enumerate(p.chunk_rows):
    loc = json.loads(row["locator"])
    arr = _load_verified_doc(row["relpath"], row["sha256"], docs)[loc["section"]]
    recs = [arr[k] for k in (loc["indices"] if "indices" in loc else [loc["index"]])]
    record_sets.append(frozenset(str(r["id"]) for r in recs if r.get("id") is not None))
    ordinal[i] = int(row["ordinal"])
    here = set()
    for r in recs:
        when = stamp(((r.get("Message") or {}).get("User") or {}).get("timestamp")) if "Message" in r else None
        channel = (r.get("Channel") or {}).get("channelID") if "Channel" in r else None
        if when is not None and channel is not None:
            here.add((channel, datetime.fromtimestamp(when, timezone.utc).date().isoformat()))
    talks.append(here)
branches = V.tree_level(p.tree, "product")
branch_of = np.full(n, -1, dtype=np.int64)
for b, (_, chunks) in enumerate(branches):
    branch_of[chunks] = b
chunks_of_record = defaultdict(list)
for i in range(n):
    for r in record_sets[i]:
        chunks_of_record[r].append(i)


def the_pool_chunk(records):
    hits = Counter(c for r in records for c in chunks_of_record.get(str(r), ()))
    if not hits:
        return None
    most = max(hits.values())
    return min((c for c, k in hits.items() if k == most), key=lambda c: (ordinal[c], id_rank[c]))


for label, name in ARM_RUNS.items():
    tops = []
    for row in rows_of(name):
        q = by_id[row["id"]]
        cites = {str(c) for c in q.citations}
        delivered = [the_pool_chunk(c) for c in ((row.get("meta") or {}).get("chunk_ids") or [])]
        delivered = [c for c in delivered if c is not None]
        tops.append((delivered[0], bool(record_sets[delivered[0]] & cites), set(delivered)))
    seen = Counter(top for top, _, _ in tops)
    per_product = Counter(int(branch_of[top]) for top, _, _ in tops)
    print(f"\n==== {label} ({name}) ====")
    print(f"  questions of the hundred per product, the middle: {np.median(list(per_product.values())):.0f} "
          f"({min(per_product.values())}-{max(per_product.values())}); products: {len(per_product)}")
    for which, flag in (("gold", True), ("not gold", False)):
        mine = [(top, others) for top, is_gold, others in tops if is_gold == flag]
        again = sum(1 for top, _ in mine if seen[top] > 1)
        # how many of the other questions of the same product deliver this chunk anywhere
        shares = []
        for top, _ in mine:
            rest = [d for t, _, d in tops if branch_of[t] == branch_of[top] and t is not top]
            same_product = [d for t, _, d in tops if branch_of[t] == branch_of[top]]
            if len(same_product) > 1:
                shares.append((sum(1 for d in same_product if top in d) - 1) / (len(same_product) - 1))
        slack = [top for top, _ in mine if kind_names[int(kind[top])] == "slack_thread_batch"]
        mixed = Counter("one conversation" if len(talks[c]) <= 1 else "two" if len(talks[c]) == 2 else "three or more"
                        for c in slack)
        print(f"  the first chunk when it is {which} ({len(mine)}): also the first chunk of another question on "
              f"{again}; delivered somewhere for {float(np.mean(shares)) if shares else 0.:.0%} of the other questions "
              f"of its product; as a Slack batch ({len(slack)}) it holds " + ", ".join(
                  f"{k}: {mixed[k]}" for k in ("one conversation", "two", "three or more")))
print("done", flush=True)

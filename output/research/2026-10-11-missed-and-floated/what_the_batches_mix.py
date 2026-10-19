"""For his 2026-10-12 goal "solve this": how the graph's chunks mix the product's own work with the
records that are not (`first_gold_rounds/ties.py`). No question, no gold, no model call; the graph
is read for the chunks.

  Slack batches and pull request batches of the pool: wholly own, mixed, wholly not own; the
  mixed ones by how much of them is not own; and for a pull request batch whether its LAST
  record, the one its description and tags were written from (found 2026-10-11), is the
  product's own pull request or another project's
"""
import json
import os
import sys
import warnings
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test"), str(HERE / "first_gold_rounds")]
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")
os.environ["HERB_V4_OFFLINE"] = "on"

import ties as TI  # noqa: E402
from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _resolve_chunk  # noqa: E402

p = V.prepare_over_corpus("what the batches mix")
cache, slack, prs, last = {}, Counter(), Counter(), Counter()
for row in p.chunk_rows:
    loc = json.loads(row["locator"])
    if "char_range" in loc or loc.get("section") not in ("slack", "prs"):
        continue
    _, ids = _resolve_chunk(row, cache)
    ids = [str(x) for x in ids]
    P = TI.product(str(row["parent"]).split(".")[1])
    flags = [TI.apart(r, P) for r in ids]
    share = sum(flags) / len(flags)
    key = ("wholly the product's own" if share == 0 else "wholly not the product's own" if share == 1 else
           "mixed: under a third not own" if share < 1 / 3 else "mixed: a third to two thirds not own" if share <= 2 / 3
           else "mixed: over two thirds not own")
    (slack if loc["section"] == "slack" else prs)[key] += 1
    if loc["section"] == "prs" and len(ids) > 1:
        last["its last pull request is another project's" if flags[-1] else "its last pull request is the product's own"] += 1
for name, table in (("Slack batches", slack), ("pull request batches", prs)):
    total = sum(table.values())
    print(f"== {name}: {total} ==")
    for key, n in sorted(table.items()):
        print(f"  {n:5d} | {n / total:4.0%}  {key}")
total = sum(last.values())
print(f"== pull request batches holding more than one pull request: {total} ==")
for key, n in last.items():
    print(f"  {n:5d} | {n / total:4.0%}  {key}")

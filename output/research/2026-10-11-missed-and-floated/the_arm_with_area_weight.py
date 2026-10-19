"""His 2026-10-11 "you do the scope first and then you scope the cloud, meaning the clouds give extra
weight to specific areas of the scope while perhaps still in the same branch", put on the arm
itself. The arm is run as it stands (the name border), retrieval only and offline, in four ways:
its own chain; the chain with the area weight; the chain with the old pick of tags (graph tags at
the same-thing level in place of each query tag's 5 nearest); and both.

The area weight, the agent's reading: an area is a parent (a channel or a file); every chunk gets,
added to its strength, the standing of its area's best strength among the chunks of its product
(the value less the product's middle over the product's spread). Nothing else of the chain is
touched; the order is the new value from the highest, and the name border cuts as before.

No model call (HERB_V4_OFFLINE=on). The gold ids are read inside this script; it prints numbers
only.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/the_arm_with_area_weight.py [gold100]
"""
import inspect
import json
import os
import sys
import warnings
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")
os.environ["HERB_V4_OFFLINE"] = "on"
os.environ.pop("HERB_V4_SCOPE_STEP", None)        # the step as it stands: the name border

from arms import artefact_v4 as V  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402

SET = sys.argv[1] if len(sys.argv) > 1 else "gold100"
BUDGET = 72000
PICK_LINE = "kth = np.array([np.sort(row[eligible])[::-1][min(k, int(eligible.sum())) - 1] for row in rows])"

wanted = [json.loads(line)["id"] for line in (REPO / "data" / f"{SET}.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("the arm with area weight")
layer = p.layer
n = len(p.chunk_ids)
same = next((h["same_thing_pairs"] for h in (getattr(p, "provenance", None), V.RETRIEVAL_FLAGS)
             if isinstance(h, dict) and isinstance(h.get("same_thing_pairs"), dict)), None)
source = inspect.getsource(WK.chain)
if PICK_LINE not in source:
    raise SystemExit("the pick line of v4_walk.chain is not what this script expects")
space = dict(vars(WK))
space["SAME_LEVEL"] = float(same["level"])
exec(source.replace(PICK_LINE, "kth = np.full(rows.shape[0], SAME_LEVEL)").replace("def chain(", "def chain_same("), space)
own_chain, same_chain = WK.chain, space["chain_same"]
parents = sorted({str(row["parent"]) for row in p.chunk_rows})
code = {name: k for k, name in enumerate(parents)}
area = np.array([code[str(row["parent"])] for row in p.chunk_rows], dtype=np.int64)
product = np.asarray(layer["product"], dtype=np.int64)
id_rank = layer["id_rank"]


def with_area(chain):
    def run(layer_, query, cos_noise, k):
        walked = dict(chain(layer_, query, cos_noise, k))
        strength = np.asarray(walked["strength"], dtype=np.float64)
        best = np.full(len(parents), -np.inf)
        np.maximum.at(best, area, strength)
        area_best = best[area]
        weight = np.zeros(n)
        for code_ in np.unique(product):
            here = product == code_
            mid = np.median(area_best[here])
            spread = 1.4826 * np.median(np.abs(area_best[here] - mid))
            weight[here] = (area_best[here] - mid) / spread if spread > 0 else 0.
        walked["order"] = np.lexsort((id_rank, -(strength + weight))).tolist()
        return walked
    return run


WAYS = {
    "the arm as it stands": own_chain,
    "+ the area weight": with_area(own_chain),
    "the old pick of tags": same_chain,
    "the old pick of tags + the area weight": with_area(same_chain),
}
recall = {name: [] for name in WAYS}
for n_done, qid in enumerate(wanted, 1):
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    for name, chain in WAYS.items():
        WK.chain = chain
        out = V.answer_one_question((qid, q.question), p, None, 50, BUDGET)
        recall[name].append(len(cites & {str(x) for x in out.context_ids}) / len(cites))
    WK.chain = own_chain
    if n_done % 20 == 0:
        print(f"  ... {n_done} questions", flush=True)

first = "the arm as it stands"
print(f"\n{SET}: {len(wanted)} questions, the arm with the name border, retrieval only, no model call")
print("== context_recall_id | against the arm as it stands: mean difference, its standard error, questions higher / "
      "lower ==")
for name in WAYS:
    diff = np.asarray(recall[name]) - np.asarray(recall[first])
    print(f"  {float(np.mean(recall[name])):.3f} | {float(diff.mean()):+.3f}, "
          f"{float(diff.std(ddof=1) / np.sqrt(diff.size)):.3f}, {int((diff > 0).sum())} / {int((diff < 0).sum())}  {name}")
np.save(HERE / f"the_arm_with_area_weight__{SET}.npy", recall, allow_pickle=True)
print("done", flush=True)

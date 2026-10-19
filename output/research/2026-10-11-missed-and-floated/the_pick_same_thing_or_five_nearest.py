"""After the hundred with the name border (0.487 against the old arm's 0.550, the border right on
all 100): the pick of tags is one of the things that changed in the order between 2026-10-07 and
now. The arm is run as it stands, retrieval only and offline, once with its own pick (each query
tag's 5 nearest graph tags) and once with the pick the old arm had: every graph tag that scores at
least what the graph's own same-thing pairs score at their 5% point. Nothing else differs; the
chain is the module's own source with the one line of the pick replaced.

No model call (HERB_V4_OFFLINE=on). The gold ids are read inside this script; it prints numbers
only.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/the_pick_same_thing_or_five_nearest.py [gold100]
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
p = V.prepare_over_corpus("the pick: same thing or five nearest")
same = next((h["same_thing_pairs"] for h in (getattr(p, "provenance", None), V.RETRIEVAL_FLAGS)
             if isinstance(h, dict) and isinstance(h.get("same_thing_pairs"), dict)), None)
LEVEL = float(same["level"])
source = inspect.getsource(WK.chain)
if PICK_LINE not in source:
    raise SystemExit("the pick line of v4_walk.chain is not what this script expects")
space = dict(vars(WK))
space["SAME_LEVEL"] = LEVEL
exec(source.replace(PICK_LINE, "kth = np.full(rows.shape[0], SAME_LEVEL)").replace("def chain(", "def chain_same("), space)
own_chain, same_chain = WK.chain, space["chain_same"]
print(f"the same-thing level: {LEVEL:.4f} (the 5% point of the graph's same-thing pairs)", flush=True)

recall = {"its own pick: each query tag's 5 nearest graph tags": [], "the old pick: graph tags at the same-thing level": []}
picked = {name: [] for name in recall}
for n_done, qid in enumerate(wanted, 1):
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    for name, chain in zip(recall, (own_chain, same_chain)):
        WK.chain = chain
        out = V.answer_one_question((qid, q.question), p, None, 50, BUDGET)
        delivered = {str(x) for x in out.context_ids}
        recall[name].append(len(cites & delivered) / len(cites))
        pick = (out.meta.get("diagnostics") or {}).get("pick") or (out.meta.get("ranking") or {}).get("pick") or {}
        picked[name].append(pick.get("graph_tags"))
    WK.chain = own_chain
    if n_done % 20 == 0:
        print(f"  ... {n_done} questions", flush=True)

names = list(recall)
a, b = np.asarray(recall[names[0]]), np.asarray(recall[names[1]])
print(f"\n{SET}: {len(wanted)} questions, the arm as it stands with the name border, retrieval only")
for name in names:
    tags = [t for t in picked[name] if t is not None]
    extra = f"; graph tags picked per question, the middle {np.median(tags):.0f}" if tags else ""
    print(f"  context_recall_id {float(np.mean(recall[name])):.3f}  {name}{extra}")
d = b - a
print(f"  the old pick minus its own: {d.mean():+.3f}, standard error {d.std(ddof=1) / np.sqrt(d.size):.3f}; questions "
      f"higher {int((d > 0).sum())}, lower {int((d < 0).sum())}, the same {int((d == 0).sum())}")
print("done", flush=True)

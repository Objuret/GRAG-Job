"""For his 2026-10-11 goal "Explore this more to find the closest first gold": the arm itself, as it
stands (the name border, the chain's order), retrieval only and offline, run twice: as it is,
and with the question's own vector made from the question WITHOUT the product's name (the name
replaced by "the product"). Only the question route's embedding differs; the border is still set
from the question as asked, and the first call's description and tags are the cached ones.
The arm's file is not changed: the embedding call is wrapped here.

Printed: on how many questions the first delivered chunk is gold, where the first gold chunk
stands in the delivery, and context_recall_id (share of the cited records delivered inside
72,000 characters).

No model call (HERB_V4_OFFLINE=on). The gold ids are read inside this script; it prints numbers
only.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/the_arm_without_the_name.py [gold100]
"""
import json
import os
import re
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
from harness import questions as HQ  # noqa: E402

SET = sys.argv[1] if len(sys.argv) > 1 else "gold100"
BUDGET = 72000
TOKEN = re.compile(r"[a-z0-9]+")

wanted = [json.loads(line)["id"] for line in (REPO / "data" / f"{SET}.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("the arm without the name")
n = len(p.chunk_ids)
original = V._query_cosines
state = {"question": None, "bare": None, "swapped": 0}


def without_the_names(question, names):
    out = question
    for name in names:
        parts = TOKEN.findall(name.lower())
        if not parts:
            continue
        pattern = re.compile(r"(?<![A-Za-z0-9])" + r"[^A-Za-z0-9]*".join(re.escape(part) for part in parts)
                             + r"(?![A-Za-z0-9])", re.IGNORECASE)
        out = pattern.sub("the product", out)
    return " ".join(out.split())


def wrapped(description, tags, prepared, role="query"):
    """The arm's embedding call; the question route's call (the question alone, no tags) is made with the
    question without the name when one is set."""
    if state["bare"] is not None and not tags and description == state["question"]:
        state["swapped"] += 1
        return original(state["bare"], tags, prepared, role)
    return original(description, tags, prepared, role)


V._query_cosines = wrapped
rows = {}
for label in ("the arm as it stands", "the arm with the question read without the product's name"):
    first, place, recall, none = [], [], [], 0
    state["swapped"] = 0
    for qid in wanted:
        q = by_id[qid]
        cites = {str(c) for c in q.citations}
        names = V.scope_by_name(q.question, p.tree, n)[1]["names_in_the_question"]
        state["question"] = q.question
        state["bare"] = without_the_names(q.question, names) if label.endswith("name") and names else None
        out = V.answer_one_question((qid, q.question), p, None, 50, BUDGET)
        delivered = {str(x) for x in out.context_ids}
        chunks = [[str(x) for x in c] for c in (out.meta.get("chunk_ids") or []) if c]
        whole = [c for c in chunks if set(c) <= delivered]
        gold = [bool(set(c) & cites) for c in whole]
        first.append(bool(gold and gold[0]))
        if any(gold):
            place.append(gold.index(True) + 1)
        else:
            none += 1
        recall.append(len(cites & delivered) / len(cites))
    rows[label] = (np.array(first), np.array(place), none, np.array(recall), state["swapped"])
    print(f"  ... {label}: done ({state['swapped']} question embeddings swapped)", flush=True)

print(f"\n{SET}: {len(wanted)} questions")
print("== first delivered chunk gold | first gold within the first 3 delivered | within 5 | no gold chunk delivered | "
      "context_recall_id ==")
for label, (first, place, none, recall, _) in rows.items():
    print(f"  {int(first.sum())} of {first.size} | {int((place <= 3).sum())} | {int((place <= 5).sum())} | {none} | "
          f"{float(recall.mean()):.3f}  {label}")
a, b = rows["the arm with the question read without the product's name"], rows["the arm as it stands"]
diff = a[3] - b[3]
print(f"first chunk gold with the name out and not as it stands on {int((a[0] & ~b[0]).sum())} questions, the other way on "
      f"{int((~a[0] & b[0]).sum())}; context_recall_id higher on {int((diff > 0).sum())}, lower on {int((diff < 0).sum())}, "
      f"mean difference {float(diff.mean()):+.3f} (standard error {float(diff.std(ddof=1) / np.sqrt(diff.size)):.3f})")
print("done", flush=True)

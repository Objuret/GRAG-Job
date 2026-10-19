"""Round 39, under his 2026-10-12 goal "solve this": the records that are not the product's own work
by their ties (ties.py: another project's pull request, a talk about another project's, the
planning team that does not continue) are cited 0.0% to 0.1% of the time (round 38). What that
does to the 72,000 characters. The hundred, inside the question's product, numbers only.

  1  the same count with a talk read by the id's own counter, beside one channel on one day
  2  the chunks the combo order as built delivers: share of their characters in such records
  3  the combo order as built, each chunk handed over WITHOUT those records (a chunk that is
     nothing else is left out), down the same order until 72,000 characters are full:
     chunks handed over, gold chunks among them, first chunk gold (of 100), context_recall_id
     (share of the cited records delivered inside 72,000 characters)
"""
import pickle
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path[:0] = [r"C:\Coding\exjobbet\GRAG-Job\prod", r"C:\Coding\exjobbet\GRAG-Job\test"]
from artefact import v4_walk as WK  # noqa: E402

import ties as TI  # noqa: E402
from explore import BUDGET, load, standing  # noqa: E402

HERE = Path(__file__).resolve().parent
T = load()
Q, KINDS = T["questions"], T["kind_names"]
with open(HERE / "first_gold_signals_tags__gold100.pkl", "rb") as handle:
    extra = pickle.load(handle)
for qid, d in Q.items():
    d.update(extra[qid])
WHOLE = ("document_part", "meeting_transcript_part")      # one record cut in parts: its length is the part's


def combo(d):
    D, Tg = np.asarray(d["question_bare"], dtype=np.float64), np.asarray(d["tags"], dtype=np.float64)
    step = (WK.levels(D, 5) + WK.levels(Tg, 5)).astype(np.float64)
    z = standing(D) + standing(Tg)
    hits = step <= 3 if (step <= 3).any() else step == step.min()
    ids = np.unique(d["parent"])
    held = np.array([int(hits[d["parent"] == a].sum()) for a in ids])
    total, last = 0, None
    for at in np.lexsort((ids, -held)):
        total += int(held[at])
        last = int(held[at])
        if total * 2 > int(held.sum()):
            break
    scope = np.isin(d["parent"], ids[held >= last])
    return np.lexsort((d["id_rank"], -z, ~scope, step))


def deliver(order, d, lengths, keep):
    """Down the order until the budget is full, the harness's way (the first that does not fit ends it)."""
    used, got, kept = 0, set(), []
    for k in order.tolist():
        if not keep[k]:
            continue
        if used + lengths[k] > BUDGET:
            break
        used += lengths[k]
        kept.append(k)
        got.update(keep[k])
    return kept, got, used


print("== 1: a talk read two ways: records a question | of them cited ==")
for talk in ("count", "day"):
    seen, cited_n = Counter(), Counter()
    for qid, d in Q.items():
        P = TI.product(qid.split("::")[0], talk)
        cited = set(d["cited_ids"])
        for k in range(d["gold"].size):
            for r in d["records"][k]:
                t = TI.tie(r, P)
                seen[t] += 1
                cited_n[t] += r in cited
    print(f"  a talk = {'from an id that counts 0 to the next' if talk == 'count' else 'one channel on one day'}:")
    for t, count in sorted(seen.items(), key=lambda kv: -kv[1]):
        print(f"    {count / len(Q):7.1f} | {cited_n[t] / count:5.2%}  {t}")

rows = {name: [] for name in ("as built", "without the records that are not the product's own work")}
share, left_out, shorter = [], [], []
for qid, d in Q.items():
    P = TI.product(qid.split("::")[0])
    m = d["gold"].size
    order = combo(d)
    cited = set(d["cited_ids"])
    whole = [list(d["records"][k]) for k in range(m)]
    own = [[r for r in d["records"][k] if not TI.apart(r, P)] for k in range(m)]
    length = d["length"].astype(np.int64)
    trimmed = length.copy()
    for k in range(m):
        if KINDS[d["kind"][k]] in WHOLE or len(own[k]) == len(whole[k]):
            continue
        # the arm's text is the records' JSON joined by a line break
        trimmed[k] = sum(P["size"][r] for r in own[k]) + max(len(own[k]) - 1, 0)
    kept, got, used = deliver(order, d, length, whole)
    apart_chars = sum(int(length[k] - trimmed[k]) for k in kept)
    share.append(apart_chars / max(used, 1))
    rows["as built"].append((len(kept), int(d["gold"][kept].sum()), bool(d["gold"][kept[0]]), len(cited & got) / d["cites"]))
    kept2, got2, used2 = deliver(order, d, trimmed, own)
    rows["without the records that are not the product's own work"].append(
        (len(kept2), int(d["gold"][kept2].sum()), bool(d["gold"][kept2[0]]), len(cited & got2) / d["cites"]))
    left_out.append(sum(1 for k in order[:len(kept2) + 5].tolist() if not own[k]))
    shorter.append(sum(1 for k in kept2 if trimmed[k] < length[k]))
print(f"\n== 2: of the characters the combo order as built delivers, in records that are not the product's own work: "
      f"{np.mean(share):.1%} at the mean, {np.median(share):.1%} at the middle ==")
print("\n== 3: chunks handed over, a question | gold chunks among them | first chunk gold (of 100) | context_recall_id ==")
for name, got in rows.items():
    a = np.array(got, dtype=np.float64)
    print(f"  {a[:, 0].mean():5.1f} | {a[:, 1].mean():4.2f} | {int(a[:, 2].sum()):3d} | {a[:, 3].mean():.3f}  {name}")
a, b = np.array(rows["as built"])[:, 3], np.array(rows["without the records that are not the product's own work"])[:, 3]
diff = b - a
print(f"  context_recall_id, the second less the first: {diff.mean():+.3f}, standard error {diff.std(ddof=1) / np.sqrt(diff.size):.3f}; "
      f"higher on {int((diff > 1e-9).sum())} questions, lower on {int((diff < -1e-9).sum())}")
print(f"  chunks handed over shorter than they are, a question: {np.mean(shorter):.1f}")

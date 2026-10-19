"""Round 65, under his 2026-10-12 goal "solve this" (the order): a batch that mixes the product's own
conversation with one about another project is described and tagged as the mix, and often as
the other project's talk (read off the graph for one support channel; 48% of the Slack batches
mix). So for a mixed batch the description's nearness says little about its own part. Tried
here: a mixed batch is read by its own part and not by its description: the nearness of the
own conversations it holds (their own vectors, `own_units`, the repo's embedder), the largest of
them, in place of the description's nearness; a batch that is wholly the product's own keeps
its description. The combo otherwise as built; handed over as the step as it stands. The
hundred, numbers only.

  C    the step as it stands
  M1   mixed Slack batches read by their own conversations' nearness (description side)
  M2   M1, and the tags' side of a mixed batch left out of the step (its level is the
       description side's twice), since its tags are the mix's too
  M3   every Slack batch read by its own conversations' nearness
first text holds a cited record: all, and over the questions whose cited messages come mostly
from the bug channels | context_recall_id
"""
import json
import pickle
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

sys.path[:0] = [r"C:\Coding\exjobbet\GRAG-Job\prod", r"C:\Coding\exjobbet\GRAG-Job\test"]
from artefact import v4_walk as WK  # noqa: E402

import ties as TI  # noqa: E402
from explore import BUDGET, load, standing  # noqa: E402

HERE = Path(__file__).resolve().parent
OWN = Path(r"C:\Coding\exjobbet\GRAG-Job\output\research\2026-10-11-missed-and-floated\own_units")
T = load()
Q, KINDS = T["questions"], T["kind_names"]
with open(HERE / "first_gold_signals_tags__gold100.pkl", "rb") as handle:
    extra = pickle.load(handle)
PARTS = ("document_part", "meeting_transcript_part")
rows = [json.loads(line) for line in open(OWN / "own_units.jsonl", encoding="utf-8")]
matrix = np.asarray(np.load(OWN / "own_units_query.npz", allow_pickle=True)["matrix"], dtype=np.float32)
unit_of_record = {}
for at, row in enumerate(rows):
    for r in row["records"]:
        unit_of_record[r] = at


def length_of(records, P):
    return sum(P["size"][r] for r in records) + max(len(records) - 1, 0)


def majority(hits, parent):
    ids = np.unique(parent)
    held = np.array([int(hits[parent == a].sum()) for a in ids])
    total, last = 0, None
    for at in np.lexsort((ids, -held)):
        total += int(held[at])
        last = int(held[at])
        if total * 2 > int(held.sum()):
            break
    return np.isin(parent, ids[held >= last])


results = defaultdict(list)
bug = []
for qid, d in Q.items():
    d.update(extra[qid])
    P = TI.product(qid.split("::")[0])
    m = d["gold"].size
    cited, cites = set(d["cited_ids"]), d["cites"]
    kind = [KINDS[x] for x in d["kind"]]
    own = [[r for r in d["records"][k] if not TI.apart(r, P)] for k in range(m)]
    chunk_len = d["length"].astype(np.int64)
    bare = np.asarray(d["bare_vector"], dtype=np.float32)
    D, Tg = np.asarray(d["question_bare"], dtype=np.float64), np.asarray(d["tags"], dtype=np.float64)
    is_slack = np.array([k_ == "slack_thread_batch" for k_ in kind])
    mixed = np.array([is_slack[k] and 0 < len(own[k]) < len(d["records"][k]) for k in range(m)])
    own_near = np.full(m, np.nan)
    for k in range(m):
        if is_slack[k] and own[k]:
            units = {unit_of_record[r] for r in own[k]}
            own_near[k] = max(float(matrix[u] @ bare) for u in units)
    per = Counter(P["channel_of"][r].split("-")[0] for r in cited if r in P["channel_of"])
    bug.append(bool(per) and per.most_common(1)[0][0] == "bug")
    talk_records = defaultdict(list)
    for k in sorted(range(m), key=lambda k: (int(d["parent"][k]), int(d["id_rank"][k]))):
        if kind[k] == "slack_thread_batch":
            for r in own[k]:
                talk_records[P["talk_of"][r]].append(r)

    def send(by):
        used, got, first, seen, sent = 0, set(), None, set(), set()
        for k in by.tolist():
            if not own[k]:
                continue
            if kind[k] != "slack_thread_batch":
                records = own[k]
                size = int(chunk_len[k]) if kind[k] in PARTS or len(own[k]) == len(d["records"][k]) else length_of(own[k], P)
                if kind[k] not in PARTS and not [r for r in records if r not in got]:
                    continue
            else:
                here = [t for t in dict.fromkeys(P["talk_of"][r] for r in own[k]) if t not in seen]
                records = [r for t in here for r in talk_records[t] if r not in sent]
                if not records:
                    continue
                size = length_of(records, P)
            if used + size > BUDGET:
                break
            used += size
            if kind[k] == "slack_thread_batch":
                seen.update(here)
                sent.update(records)
            got.update(records)
            if first is None:
                first = bool(cited & set(records))
        return bool(first), len(cited & got) / cites

    def combo(Dx, twice=None):
        lD, lT = WK.levels(Dx, 5), WK.levels(Tg, 5)
        sT = standing(Tg)
        if twice is not None:
            lT = np.where(twice, lD, lT)
            sT = np.where(twice, standing(Dx), sT)
        step = (lD + lT).astype(np.float64)
        z = standing(Dx) + sT
        hits = step <= 3 if (step <= 3).any() else step == step.min()
        return np.lexsort((d["id_rank"], -z, ~majority(hits, d["parent"]), step))

    # the own-part nearness is on another scale than the description's: each as its standing over
    # the chunks it is read for, then put where the description's standing is
    def swapped(which):
        take = which & np.isfinite(own_near)
        if not take.any():
            return D
        out = D.copy()
        mid, spread = np.median(D), 1.4826 * np.median(np.abs(D - np.median(D)))
        o = own_near[np.isfinite(own_near)]
        o_mid, o_spread = np.median(o), 1.4826 * np.median(np.abs(o - np.median(o)))
        if spread > 0 and o_spread > 0:
            out[take] = mid + (own_near[take] - o_mid) / o_spread * spread
        return out

    results["C   the step as it stands"].append(send(combo(D)))
    results["M1  mixed batches read by their own conversations' nearness"].append(send(combo(swapped(mixed))))
    results["M2  M1, and a mixed batch's tags' side left out of the step"].append(send(combo(swapped(mixed), mixed)))
    results["M3  every Slack batch read by its own conversations' nearness"].append(send(combo(swapped(is_slack))))

bug = np.array(bug)
print(f"questions whose cited messages come mostly from the bug channels: {int(bug.sum())}")
print("first text holds a cited record: of 100 | of those bug-channel questions | context_recall_id")
base = np.array([r[1] for r in results["C   the step as it stands"]])
for name, got in results.items():
    a = np.array(got, dtype=np.float64)
    diff = a[:, 1] - base
    print(f"  {int(a[:, 0].sum()):3d} | {int(a[bug, 0].sum()):2d} of {int(bug.sum())} | {a[:, 1].mean():.3f}  {name}"
          + ("" if name.startswith("C  ") else f"   [{diff.mean():+.3f}, standard error {diff.std(ddof=1) / 10:.3f}, higher on "
             f"{int((diff > 1e-9).sum())}, lower on {int((diff < -1e-9).sum())}]"))

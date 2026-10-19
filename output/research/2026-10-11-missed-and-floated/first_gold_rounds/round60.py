"""Round 60, under his 2026-10-12 goal "solve this" (the order): read off the graph for one bug
channel (no gold): a batch that is mostly a conversation about another project's bugs is
described as that conversation and tagged with the product's own bug titles it mentions, so it
stands first for a question about that bug, and what it hands over of the product's own is the
tail of some other conversation. On the hundred the first unit holds a cited record on 7 of the
26 questions whose cited messages come from the bug channels (round 59).

So a conversation should stand where the chunk that is ABOUT it stands, not where any chunk
holding a piece of it stands. Tried here: the hundred, the combo order as built, the records
that are not the product's own work left out, whole own conversations; numbers only.

  C    a conversation stands where the first chunk holding a piece of it stands (round 40)
  H1   a conversation stands where the chunk holding MOST of its messages stands
  H2   a conversation stands where the best-placed chunk stands among those in which it is the
       largest part of the chunk (any conversation counted, also one about another project's);
       a conversation that is the largest part of no chunk stands where the chunk holding most
       of it stands, after all the others
  H3   H2 without the last clause: such a conversation stands where the chunk holding most of it stands
"""
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
T = load()
Q, KINDS = T["questions"], T["kind_names"]
with open(HERE / "first_gold_signals_tags__gold100.pkl", "rb") as handle:
    extra = pickle.load(handle)
PARTS = ("document_part", "meeting_transcript_part")


def length_of(records, P):
    return sum(P["size"][r] for r in records) + max(len(records) - 1, 0)


def hand_over(units, cited, cites):
    used, got, first = 0, set(), None
    for records, chars, part in units:
        new = [r for r in records if r not in got]
        if not new and not part:
            continue
        if used + chars > BUDGET:
            break
        used += chars
        got.update(records)
        if first is None:
            first = bool(cited & set(records))
    return bool(first), len(cited & got) / cites


results = defaultdict(list)
stage_first = defaultdict(lambda: defaultdict(lambda: [0, 0]))
for qid, d in Q.items():
    d.update(extra[qid])
    P = TI.product(qid.split("::")[0])
    m = d["gold"].size
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
    order = np.lexsort((d["id_rank"], -z, ~scope, step))
    place = np.empty(m, dtype=np.int64)
    place[order] = np.arange(m)
    cited, cites = set(d["cited_ids"]), d["cites"]
    kind = [KINDS[x] for x in d["kind"]]
    own = [[r for r in d["records"][k] if not TI.apart(r, P)] for k in range(m)]
    chunk_len = d["length"].astype(np.int64)
    talk_records, in_chunk = defaultdict(list), defaultdict(Counter)
    largest = {}
    for k in sorted(range(m), key=lambda k: (int(d["parent"][k]), int(d["id_rank"][k]))):
        if kind[k] != "slack_thread_batch":
            continue
        every = Counter(P["talk_of"][r] for r in d["records"][k] if r in P["talk_of"])
        if every:
            top = max(every.values())
            largest[k] = {t for t, c in every.items() if c == top}
        for r in own[k]:
            t = P["talk_of"][r]
            talk_records[t].append(r)
            in_chunk[t][k] += 1
    others = [(int(place[k]), 0, own[k], (int(chunk_len[k]) if kind[k] in PARTS or len(own[k]) == len(d["records"][k])
                                           else length_of(own[k], P)), kind[k] in PARTS)
              for k in range(m) if kind[k] != "slack_thread_batch" and own[k]]

    def send(stand):
        units = list(others)
        for t, rs in talk_records.items():
            late, at = stand(t)
            units.append((at, late, rs, length_of(rs, P), False))
        units.sort(key=lambda u: (u[1], u[0]))
        return hand_over(((u[2], u[3], u[4]) for u in units), cited, cites)

    def first_piece(t):
        return 0, min(int(place[k]) for k in in_chunk[t])

    def most(t):
        top = max(in_chunk[t].values())
        return 0, min(int(place[k]) for k, c in in_chunk[t].items() if c == top)

    def about(t, late=1):
        mine = [int(place[k]) for k in in_chunk[t] if t in largest.get(k, ())]
        return (0, min(mine)) if mine else (late, most(t)[1])

    ways = {"C   where the first chunk holding a piece of it stands": first_piece,
            "H1  where the chunk holding most of its messages stands": most,
            "H2  where the best chunk it is the largest part of stands; the others after all": about,
            "H3  the same, the others where the chunk holding most of them stands": lambda t: about(t, late=0)}
    per = Counter(P["channel_of"][r].split("-")[0] for r in cited if r in P["channel_of"])
    stage = per.most_common(1)[0][0] if per else "none"
    for name, stand in ways.items():
        got = send(stand)
        results[name].append(got)
        row = stage_first[name][stage]
        row[0] += 1
        row[1] += got[0]

print("first handed over holds a cited record (of 100) | context_recall_id | first right by stage: develop, planning, bug")
base = np.array([r[1] for r in results["C   where the first chunk holding a piece of it stands"]])
for name, got in results.items():
    a = np.array(got, dtype=np.float64)
    diff = a[:, 1] - base
    stages = ", ".join(f"{stage_first[name][s][1]} of {stage_first[name][s][0]}" for s in ("develop", "planning", "bug"))
    print(f"  {int(a[:, 0].sum()):3d} | {a[:, 1].mean():.3f} | {stages}  {name}"
          + ("" if name.startswith("C  ") else f"   [{diff.mean():+.3f}, standard error {diff.std(ddof=1) / 10:.3f}, higher on "
             f"{int((diff > 1e-9).sum())}, lower on {int((diff < -1e-9).sum())}]"))

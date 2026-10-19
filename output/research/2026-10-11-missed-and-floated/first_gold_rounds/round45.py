"""Round 45, under his 2026-10-12 goal "solve this": talks about own pull requests with the same title
shut each other out, and the cited one is the later one 88% of the time on the hundred and 78%
on the 300 unused questions (round 44). His 2026-10-11 thought: nearness to "now" as a weight
unless the question names a time. Tried where it means something: among the versions of one
thing. The hundred, inside the question's product, numbers only.

  C   the combo order as built, the records that are not the product's own work left out,
      a talk handed over whole where it first shows (round 40)
  V1  C, and of two talks about own pull requests with the same title the later one is handed
      over where the first of the two shows; the earlier one where the second shows
  V2  C, and the earlier one is not handed over at all
"""
import pickle
import sys
from collections import defaultdict
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
PARTS = ("document_part", "meeting_transcript_part")


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


def hand_over(units, cited, cites):
    used, got, n, first = 0, set(), 0, None
    for records, chars, part in units:
        new = [r for r in records if r not in got]
        if not new and not part:
            continue
        if used + chars > BUDGET:
            break
        used += chars
        got.update(records)
        n += 1
        if first is None:
            first = bool(cited & set(records))
    return n, bool(first), len(cited & got) / cites


def length_of(records, P):
    return sum(P["size"][r] for r in records) + max(len(records) - 1, 0)


results = defaultdict(list)
types = []
for qid, d in Q.items():
    P = TI.product(qid.split("::")[0])
    m = d["gold"].size
    order = combo(d)
    cited, cites = set(d["cited_ids"]), d["cites"]
    kind = [KINDS[x] for x in d["kind"]]
    own = [[r for r in d["records"][k] if not TI.apart(r, P)] for k in range(m)]
    chunk_len = d["length"].astype(np.int64)

    def trimmed(k):
        if kind[k] in PARTS or len(own[k]) == len(d["records"][k]):
            return int(chunk_len[k])
        return length_of(own[k], P)

    talk_records = defaultdict(list)
    for k in sorted(range(m), key=lambda k: (int(d["parent"][k]), int(d["id_rank"][k]))):
        if kind[k] == "slack_thread_batch":
            for r in own[k]:
                talk_records[P["talk_of"][r]].append(r)
    when = {t: min(P["raw"][r][1]["Message"]["User"]["timestamp"] for r in rs) for t, rs in talk_records.items()}
    titled = defaultdict(set)
    for t in talk_records:
        for thing in P["links"][t][3]:
            if thing in P["pr_own"]:
                titled[P["raw"][thing][1]["title"]].add(t)
    later_of, earlier = {}, set()
    for members in titled.values():
        if len(members) > 1:
            line = sorted(members, key=lambda t: when[t])
            for t in line[:-1]:
                later_of[t] = line[-1]
                earlier.add(t)

    def whole_talks(way):
        seen, sent = set(), set()
        for k in order.tolist():
            if not own[k]:
                continue
            if kind[k] != "slack_thread_batch":
                yield own[k], trimmed(k), kind[k] in PARTS
                continue
            talks = []
            for t in dict.fromkeys(P["talk_of"][r] for r in own[k]):
                if way and t in later_of:
                    late = later_of[t]
                    pick = late if late not in seen else (None if way == "V2" else t)
                elif way and t in later_of.values():
                    first_seen = all(e in seen or later_of.get(e) != t for e in earlier)
                    pick = t if t not in seen else None
                    if pick is None and way == "V1":
                        # the later one went out where the earlier showed: the earlier one comes here
                        pick = next((e for e in earlier if later_of[e] == t and e not in seen), None)
                else:
                    pick = t
                if pick is not None and pick not in seen and pick not in talks:
                    talks.append(pick)
            seen.update(talks)
            records = [r for t in talks for r in talk_records[t] if r not in sent]
            if records:
                yield records, length_of(records, P), False
                sent.update(records)

    for name, way in (("C   whole own talks where they first show", None),
                      ("V1  C, the later of two talks about same-titled own pull requests first", "V1"),
                      ("V2  C, the earlier of the two not handed over", "V2")):
        results[name].append(hand_over(whole_talks(way), cited, cites))

print("units handed over, a question | first handed over holds a cited record (of 100) | context_recall_id")
base = np.array([r[2] for r in results["C   whole own talks where they first show"]])
for name, got in results.items():
    a = np.array(got, dtype=np.float64)
    diff = a[:, 2] - base
    print(f"  {a[:, 0].mean():5.1f} | {int(a[:, 1].sum()):3d} | {a[:, 2].mean():.3f}  {name}"
          + ("" if name.startswith("C  ") else f"   [against C: {diff.mean():+.3f}, standard error {diff.std(ddof=1) / 10:.3f}, "
             f"higher on {int((diff > 1e-9).sum())}, lower on {int((diff < -1e-9).sum())}]"))

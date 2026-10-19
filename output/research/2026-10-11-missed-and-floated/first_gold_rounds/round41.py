"""Round 41, under his 2026-10-12 goal "solve this": with the records that are not the product's own
work left out and the talk as what is handed over (round 40: context_recall_id 0.650 against
0.550), what the ties say about the ORDER, which those two did not touch (the first unit holds a
cited record on 50 of 100). The hundred, inside the question's product, numbers only.

  1  the own talks of a channel in the order they were held (the talks about another project's
     taken out): from a talk with a cited message, is the own talk before or after it cited too;
     the same from a handed-over talk with no cited message
  2  the first unit handed over when it holds no cited record: what it is, and how far it
     stands from a cited talk (the same channel, own talks apart)
  3  ways of handing over: C of round 40 (whole talks where they first show), and C with the own
     talk before and after each handed-over talk coming right behind it
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
    """units: (records, characters, a part of one record) in order; the first that does not fit ends it."""
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
near = Counter()
first_kind, first_far = Counter(), Counter()
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
    by_channel = defaultdict(list)                      # the own talks of a channel in the order held
    for t in talk_records:
        by_channel[t[0]].append(t)
    spot = {}
    for channel, talks in by_channel.items():
        talks.sort(key=lambda t: t[1])
        for at, t in enumerate(talks):
            spot[t] = (channel, at)
    has_cited = {t: bool(cited & set(rs)) for t, rs in talk_records.items()}

    def beside(t, far=1):
        channel, at = spot[t]
        talks = by_channel[channel]
        return [talks[x] for x in (at - far, at + far) if 0 <= x < len(talks)]

    def whole_talks(extra_beside):
        seen, sent = set(), set()
        for k in order.tolist():
            if not own[k]:
                continue
            if kind[k] != "slack_thread_batch":
                yield own[k], trimmed(k), kind[k] in PARTS
                continue
            here = list(dict.fromkeys(P["talk_of"][r] for r in own[k]))
            talks = [t for t in here if t not in seen]
            if extra_beside:
                talks += [b for t in here for b in beside(t) if b not in seen and b not in talks]
            seen.update(talks)
            records = [r for t in talks for r in talk_records[t] if r not in sent]
            if records:
                yield records, length_of(records, P), False
                sent.update(records)

    c_units = list(whole_talks(False))
    results["C  whole talks where they first show"].append(hand_over(c_units, cited, cites))
    results["G  C, and the own talk before and after each handed-over talk right behind it"].append(
        hand_over(whole_talks(True), cited, cites))

    # 1: the talk before and after, from a cited talk and from a handed-over talk with no cited message
    used, handed = 0, []
    for records, chars, part in c_units:
        if used + chars > BUDGET:
            break
        used += chars
        handed.append(records)
    handed_talks = {P["talk_of"][r] for records in handed for r in records if r in P["talk_of"]}
    for t in talk_records:
        if has_cited[t]:
            for b in beside(t):
                near[("from a talk with a cited message", has_cited[b])] += 1
        elif t in handed_talks:
            for b in beside(t):
                near[("from a handed-over talk with no cited message", has_cited[b])] += 1
        else:
            for b in beside(t):
                near[("from any other own talk", has_cited[b])] += 1

    # 2: the first unit handed over when it holds no cited record
    first = c_units[0][0]
    if not (cited & set(first)):
        talks = list(dict.fromkeys(P["talk_of"][r] for r in first if r in P["talk_of"]))
        if not talks:
            first_kind[{"document": "a document", "document_part": "a document", "meeting_transcript": "a meeting",
                        "meeting_transcript_part": "a meeting", "pr_batch": "pull requests",
                        "meeting_chat_batch": "a meeting chat", "url_batch": "urls"}[kind[int(order[0])]]] += 1
        else:
            first_kind["Slack talks"] += 1
            far = None
            for t in talks:
                channel, at = spot[t]
                for x, other in enumerate(by_channel[channel]):
                    if has_cited[other]:
                        far = abs(x - at) if far is None else min(far, abs(x - at))
            first_far["no cited talk in its channel" if far is None else
                      f"{far} own talk(s) from a cited talk" if far <= 3 else "more than 3 own talks from a cited talk"] += 1

print("== 1: the own talk before or after, in the same channel: how many | of them with a cited message ==")
for name in ("from a talk with a cited message", "from a handed-over talk with no cited message", "from any other own talk"):
    yes, no = near[(name, True)], near[(name, False)]
    print(f"  {yes + no:6d} | {yes / max(yes + no, 1):4.0%}  {name}")
print("\n== 2: the first unit handed over holds no cited record on", sum(first_kind.values()), "questions: what it is ==")
for name, count in first_kind.most_common():
    print(f"  {count:3d}  {name}")
print("   where the Slack ones stand:")
for name, count in sorted(first_far.items()):
    print(f"  {count:3d}  {name}")
print("\n== 3: units handed over, a question | first handed over holds a cited record (of 100) | context_recall_id ==")
base = np.array([r[2] for r in results["C  whole talks where they first show"]])
for name, got in results.items():
    a = np.array(got, dtype=np.float64)
    diff = a[:, 2] - base
    print(f"  {a[:, 0].mean():5.1f} | {int(a[:, 1].sum()):3d} | {a[:, 2].mean():.3f}  {name}"
          + ("" if name.startswith("C") else f"   [against C: {diff.mean():+.3f}, standard error {diff.std(ddof=1) / 10:.3f}, "
             f"higher on {int((diff > 1e-9).sum())}, lower on {int((diff < -1e-9).sum())}]"))

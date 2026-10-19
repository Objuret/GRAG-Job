"""Round 54, under his 2026-10-12 goal "solve this" (the order): the cited conversations that the
order does not reach inside 72,000 characters. Where they stand by their own nearness to the
question, and what ties them to the cited conversations that ARE handed over. The hundred, the
combo order as built with whole own conversations (C of round 40), numbers only.

  1  cited conversations a question: handed over | not; the not handed over ones' place among
     the product's own conversations by their own vector's nearness to the question
  2  a cited conversation that is not handed over, against the cited ones that are: share that
     has one in the same channel / that shares a poster with one / whose first poster is the
     first poster of one / that shares a named thing with one / that opens the same way as one
     / that is the nearest or among the three nearest conversations of one (own vectors)
  3  the same ties counted from a handed-over conversation to an own conversation not handed
     over: share of those reached that are cited, from one with a cited message and from one
     without (what the tie brings blind)
"""
import json
import pickle
import re
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
OPEN, CLOSE = "'\"\u2018\u201c", "'\"\u2019\u201d"
QUOTED = re.compile(r"(?<![A-Za-z0-9])[" + OPEN + r"]([A-Z][^" + OPEN + CLOSE + r"\n]{3,80}?)[" + CLOSE + r"](?![A-Za-z0-9])")
rows = [json.loads(line) for line in open(OWN / "own_units.jsonl", encoding="utf-8")]
kept = np.load(OWN / "own_units_query.npz", allow_pickle=True)
matrix = np.asarray(kept["matrix"], dtype=np.float32)
row_of_talk = {}
for at, row in enumerate(rows):
    kind, product, *rest = row["id"].split("|")
    if kind == "talk":
        row_of_talk[(product, rest[0], int(rest[1]))] = at


def opening(text):
    words = [w.lower().strip(".,!?:;") for w in text.split() if not any(c.isdigit() for c in w) and "@" not in w and "<" not in w]
    return " ".join(words[:5])


def length_of(records, P):
    return sum(P["size"][r] for r in records) + max(len(records) - 1, 0)


TIES = ("in the same channel", "shares a poster", "has the same first poster", "shares a named thing", "opens the same way",
        "is its nearest conversation", "is among its three nearest conversations")
handed_n, missed_n, places = 0, 0, []
has_tie, blind = Counter(), {name: [0, 0] for name in TIES}
from_cited = {name: [0, 0] for name in TIES}
for qid, d in Q.items():
    d.update(extra[qid])
    product = qid.split("::")[0]
    P = TI.product(product)
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
    cited = set(d["cited_ids"])
    kind = [KINDS[x] for x in d["kind"]]
    own = [[r for r in d["records"][k] if not TI.apart(r, P)] for k in range(m)]
    chunk_len = d["length"].astype(np.int64)
    talk_records = defaultdict(list)
    for k in sorted(range(m), key=lambda k: (int(d["parent"][k]), int(d["id_rank"][k]))):
        if kind[k] == "slack_thread_batch":
            for r in own[k]:
                talk_records[P["talk_of"][r]].append(r)
    used, handed, seen, sent, got = 0, set(), set(), set(), set()
    for k in order.tolist():
        if not own[k]:
            continue
        if kind[k] != "slack_thread_batch":
            size = int(chunk_len[k]) if kind[k] in PARTS or len(own[k]) == len(d["records"][k]) else length_of(own[k], P)
            if kind[k] not in PARTS and not [r for r in own[k] if r not in got]:
                continue
            if used + size > BUDGET:
                break
            used += size
            got.update(own[k])
            continue
        here = [t for t in dict.fromkeys(P["talk_of"][r] for r in own[k]) if t not in seen]
        rs = [r for t in here for r in talk_records[t] if r not in sent]
        if not rs:
            continue
        size = length_of(rs, P)
        if used + size > BUDGET:
            break
        used += size
        seen.update(here)
        sent.update(rs)
        got.update(rs)
        handed.update(here)
    talks = list(talk_records)
    at_of = {t: i for i, t in enumerate(talks)}
    vec = np.stack([matrix[row_of_talk[(product, t[0], t[1])]] for t in talks])
    bare = np.asarray(d["bare_vector"], dtype=np.float32)
    near_q = vec @ bare
    place = np.empty(len(talks), dtype=np.int64)
    place[np.argsort(-near_q)] = np.arange(1, len(talks) + 1)
    among = vec @ vec.T
    np.fill_diagonal(among, -1.)
    nearest = np.argsort(-among, axis=1)[:, :3]
    first_record = {t: min(rs, key=lambda r: P["raw"][r][1]["Message"]["User"]["timestamp"]) for t, rs in talk_records.items()}
    posters = {t: {P["raw"][r][1]["Message"]["User"]["userId"] for r in rs} - P["everywhere"] for t, rs in talk_records.items()}
    first_poster = {t: P["raw"][r][1]["Message"]["User"]["userId"] for t, r in first_record.items()}
    opens = {t: opening(P["raw"][r][1]["Message"]["User"]["text"]) for t, r in first_record.items()}
    things = {t: {" ".join(h.lower().split()) for r in rs for h in QUOTED.findall(P["raw"][r][1]["Message"]["User"]["text"])
                  if len(h.split()) >= 2} for t, rs in talk_records.items()}
    is_cited = {t: bool(cited & set(rs)) for t, rs in talk_records.items()}

    def tied(a, b):
        """Is b tied to a (a is the one handed over)?"""
        return {"in the same channel": a[0] == b[0], "shares a poster": bool(posters[a] & posters[b]),
                "has the same first poster": first_poster[a] == first_poster[b] and first_poster[a] not in P["everywhere"],
                "shares a named thing": bool(things[a] & things[b]), "opens the same way": opens[a] == opens[b],
                "is its nearest conversation": at_of[b] == int(nearest[at_of[a], 0]),
                "is among its three nearest conversations": at_of[b] in nearest[at_of[a]].tolist()}

    got_cited = [t for t in talks if is_cited[t] and t in handed]
    lost_cited = [t for t in talks if is_cited[t] and t not in handed]
    handed_n += len(got_cited)
    missed_n += len(lost_cited)
    places.extend((int(place[at_of[t]]), len(talks)) for t in lost_cited)
    for b in lost_cited:
        flags = Counter()
        for a in got_cited:
            for name, yes in tied(a, b).items():
                flags[name] |= yes
        for name in TIES:
            has_tie[name] += bool(flags[name])
    for a in handed:
        target = from_cited if is_cited[a] else blind
        for b in talks:
            if b in handed:
                continue
            for name, yes in tied(a, b).items():
                if yes:
                    target[name][0] += 1
                    target[name][1] += is_cited[b]
n = len(Q)
p = np.array([x[0] for x in places])
size = np.array([x[1] for x in places])
print(f"1: cited conversations a question: handed over {handed_n / n:.1f}, not {missed_n / n:.1f}; the ones not handed over stand, by "
      f"their own vector's nearness to the question, at place {np.median(p):.0f} (quarters {np.percentile(p, 25):.0f} to "
      f"{np.percentile(p, 75):.0f}) of {np.median(size):.0f} own conversations")
print("\n2: a cited conversation not handed over that is tied to a cited one that is: share | 3: reached by that tie from a "
      "handed-over conversation WITH a cited message: how many, of them cited | from one with NO cited message: how many, of them cited")
for name in TIES:
    a, b = from_cited[name], blind[name]
    print(f"  {has_tie[name] / max(missed_n, 1):4.0%} | {a[0]:6d}, {a[1] / max(a[0], 1):5.1%} | {b[0]:6d}, {b[1] / max(b[0], 1):5.1%}  {name}")

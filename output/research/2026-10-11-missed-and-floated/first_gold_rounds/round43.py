"""Round 43, under his 2026-10-12 goal "solve this": the ties that were sure so far are the ones that
say no (not the product's own work: cited 0.00%) and the one that completes a unit (a talk whole).
Here the ties that would say yes from a hit: talks about the same own thing. The hundred, inside
the question's product, the combo order as built with whole own talks (C of round 40), numbers only.

  the same thing     two talks that link to the same own pull request or the same document
  the same kind of thing  two talks that link to documents of the same type (the versions of one
                     document), or to own pull requests with the same title

  1  how many own talks have another talk about the same thing / the same kind of thing
  2  from a talk with a cited message: the other talks of its group, share with a cited message;
     the same from a handed-over talk with no cited message
  3  handing over: C, and C with the other talks of the group right behind each handed-over talk
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


def kind_of_thing(thing, P):
    kind, r = P["raw"][thing]
    return ("document", r["type"]) if kind == "documents" else ("pull request", r["title"])


results = defaultdict(list)
reach = Counter()
grouped = Counter()
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
    has_cited = {t: bool(cited & set(rs)) for t, rs in talk_records.items()}
    groups = {"the same thing": defaultdict(set), "the same kind of thing": defaultdict(set)}
    for t in talk_records:
        for thing in P["links"][t][3]:
            groups["the same thing"][thing].add(t)
            groups["the same kind of thing"][kind_of_thing(thing, P)].add(t)
    others = {name: defaultdict(set) for name in groups}
    for name, by in groups.items():
        for members in by.values():
            for t in members:
                others[name][t] |= members - {t}
        grouped[(name, "talks")] += len(talk_records)
        grouped[(name, "with another")] += sum(1 for t in talk_records if others[name][t])

    def whole_talks(extra):
        seen, sent = set(), set()
        for k in order.tolist():
            if not own[k]:
                continue
            if kind[k] != "slack_thread_batch":
                yield own[k], trimmed(k), kind[k] in PARTS
                continue
            here = list(dict.fromkeys(P["talk_of"][r] for r in own[k]))
            talks = [t for t in here if t not in seen]
            if extra:
                talks += [b for t in here for b in sorted(others[extra][t]) if b not in seen and b not in talks]
            seen.update(talks)
            records = [r for t in talks for r in talk_records[t] if r not in sent]
            if records:
                yield records, length_of(records, P), False
                sent.update(records)

    c_units = list(whole_talks(None))
    results["C  whole own talks where they first show"].append(hand_over(c_units, cited, cites))
    for name in groups:
        results[f"C, and the other talks about {name} right behind"].append(hand_over(whole_talks(name), cited, cites))
    used, handed = 0, set()
    for records, chars, part in c_units:
        if used + chars > BUDGET:
            break
        used += chars
        handed.update(P["talk_of"][r] for r in records if r in P["talk_of"])
    for name in groups:
        for t in talk_records:
            start = "a talk with a cited message" if has_cited[t] else "a handed-over talk with no cited message" if t in handed else None
            if start:
                for b in others[name][t]:
                    reach[(name, start, has_cited[b])] += 1

print("== 1: own talks, a question | of them with another talk in its group ==")
for name in ("the same thing", "the same kind of thing"):
    print(f"  {grouped[(name, 'talks')] / len(Q):6.1f} | {grouped[(name, 'with another')] / grouped[(name, 'talks')]:4.0%}  {name}")
print("\n== 2: the other talks of its group: how many | of them with a cited message ==")
for name in ("the same thing", "the same kind of thing"):
    for start in ("a talk with a cited message", "a handed-over talk with no cited message"):
        yes, no = reach[(name, start, True)], reach[(name, start, False)]
        print(f"  {yes + no:6d} | {yes / max(yes + no, 1):4.0%}  {name}, from {start}")
print("\n== 3: units handed over, a question | first handed over holds a cited record (of 100) | context_recall_id ==")
base = np.array([r[2] for r in results["C  whole own talks where they first show"]])
for name, got in results.items():
    a = np.array(got, dtype=np.float64)
    diff = a[:, 2] - base
    print(f"  {a[:, 0].mean():5.1f} | {int(a[:, 1].sum()):3d} | {a[:, 2].mean():.3f}  {name}"
          + ("" if name.startswith("C  ") else f"   [against C: {diff.mean():+.3f}, standard error {diff.std(ddof=1) / 10:.3f}, "
             f"higher on {int((diff > 1e-9).sum())}, lower on {int((diff < -1e-9).sum())}]"))

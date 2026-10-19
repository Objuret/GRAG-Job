"""Round 40, under his 2026-10-12 goal "solve this", after round 39 (the records that are not the
product's own work by their ties are cited 0.00%; leaving them out of what is handed over gives
context_recall_id 0.602 against 0.550). What the same ties give further, the hundred, inside the
question's product, the combo order as built, numbers only.

  A  as built
  B  each chunk without the records that are not the product's own work
  C  B, and a talk is handed over whole where it first shows (its messages in the chunk before
     or after come with it)
  D  B, and the own pull request a handed-over talk links to comes right after the chunk
     (the one record, not its batch)
  E  the talk as the unit: a talk stands where its chunks stand in the order (the best, the
     mean, the worst of them); a chunk that is not Slack stands where it stands
  F  C and D together

chunks or units handed over | first handed over holds a cited record (of 100) |
context_recall_id (share of the cited records delivered inside 72,000 characters)
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
    """units: (records, characters) in order. The harness's cut: the first that does not fit ends it."""
    used, got, n, first = 0, set(), 0, None
    for records, chars in units:
        new = [r for r in records if r not in got]
        if not new:
            continue
        if used + chars > BUDGET:
            break
        used += chars
        got.update(new)
        n += 1
        if first is None:
            first = bool(cited & set(new))
    return n, bool(first), len(cited & got) / cites


def length_of(records, P):
    return sum(P["size"][r] for r in records) + max(len(records) - 1, 0)


results = defaultdict(list)
talk_sizes, spans = [], []
for qid, d in Q.items():
    P = TI.product(qid.split("::")[0])
    m = d["gold"].size
    order = combo(d)
    place = np.empty(m, dtype=np.int64)
    place[order] = np.arange(m)
    cited, cites = set(d["cited_ids"]), d["cites"]
    kind = [KINDS[x] for x in d["kind"]]
    own = [[r for r in d["records"][k] if not TI.apart(r, P)] for k in range(m)]
    chunk_len = d["length"].astype(np.int64)

    def trimmed(k):
        if kind[k] in PARTS or len(own[k]) == len(d["records"][k]):
            return int(chunk_len[k])
        return length_of(own[k], P)

    talk_records = defaultdict(list)                     # own talks of the product: every message, in time order
    talk_chunks = defaultdict(set)
    for k in range(m):
        if kind[k] != "slack_thread_batch":
            continue
        for r in own[k]:
            talk_records[P["talk_of"][r]].append(r)
            talk_chunks[P["talk_of"][r]].add(k)
    for t, rs in talk_records.items():
        talk_sizes.append(len(rs))
        spans.append(len(talk_chunks[t]))

    results["A  as built"].append(hand_over(((d["records"][k], int(chunk_len[k])) for k in order.tolist()), cited, cites))
    results["B  without the records that are not the product's own work"].append(
        hand_over(((own[k], trimmed(k)) for k in order.tolist() if own[k]), cited, cites))

    def whole_talks(with_prs):
        seen_talks, sent = set(), set()
        for k in order.tolist():
            if not own[k]:
                continue
            if kind[k] != "slack_thread_batch":
                records = [r for r in own[k] if r not in sent] if kind[k] == "pr_batch" else own[k]
                if records:
                    yield records, (trimmed(k) if len(records) == len(own[k]) else length_of(records, P))
                    sent.update(records)
                continue
            records = []
            for r in own[k]:
                t = P["talk_of"][r]
                if t not in seen_talks:
                    seen_talks.add(t)
                    records.extend(talk_records[t])
            records = [r for r in dict.fromkeys(records) if r not in sent]
            if with_prs:
                for t in dict.fromkeys(P["talk_of"][r] for r in own[k]):
                    for thing in sorted(P["links"][t][3]):
                        if thing in P["pr_own"] and thing not in sent and thing not in records:
                            records.append(thing)
            if records:
                yield records, length_of(records, P)
                sent.update(records)

    results["C  B, a talk handed over whole where it first shows"].append(hand_over(whole_talks(False), cited, cites))
    results["F  C, and the own pull request a handed-over talk links to"].append(hand_over(whole_talks(True), cited, cites))

    def with_prs_only():
        sent = set()
        for k in order.tolist():
            if not own[k]:
                continue
            records = [r for r in own[k] if r not in sent] if kind[k] == "pr_batch" else list(own[k])
            if kind[k] == "slack_thread_batch":
                for t in dict.fromkeys(P["talk_of"][r] for r in own[k]):
                    for thing in sorted(P["links"][t][3]):
                        if thing in P["pr_own"] and thing not in sent and thing not in records:
                            records.append(thing)
            if records:
                size = trimmed(k) if kind[k] in PARTS else length_of(records, P)
                yield records, size
                sent.update(records)

    results["D  B, and the own pull request a handed-over talk links to"].append(hand_over(with_prs_only(), cited, cites))

    for name, pick in (("best", min), ("mean", lambda xs: sum(xs) / len(xs)), ("worst", max)):
        units = []
        for t, rs in talk_records.items():
            units.append((pick([int(place[k]) for k in talk_chunks[t]]), min(int(place[k]) for k in talk_chunks[t]),
                          rs, length_of(rs, P)))
        for k in range(m):
            if kind[k] != "slack_thread_batch" and own[k]:
                units.append((int(place[k]), int(place[k]), own[k], trimmed(k)))
        units.sort(key=lambda u: (u[0], u[1]))
        results[f"E  the talk as the unit, standing at the {name} place of its chunks"].append(
            hand_over(((u[2], u[3]) for u in units), cited, cites))

print(f"own talks of a product: {np.mean(talk_sizes):.1f} messages at the mean, {np.median(talk_sizes):.0f} at the middle; "
      f"in one chunk {np.mean(np.array(spans) == 1):.0%}, in two {np.mean(np.array(spans) == 2):.0%}, in more {np.mean(np.array(spans) > 2):.0%}")
print("\nchunks or units handed over, a question | first handed over holds a cited record (of 100) | context_recall_id")
base = np.array([r[2] for r in results["A  as built"]])
for name, got in results.items():
    a = np.array(got, dtype=np.float64)
    diff = a[:, 2] - base
    print(f"  {a[:, 0].mean():5.1f} | {int(a[:, 1].sum()):3d} | {a[:, 2].mean():.3f}  {name}"
          + ("" if name.startswith("A") else f"   [against A: {diff.mean():+.3f}, standard error {diff.std(ddof=1) / 10:.3f}, "
             f"higher on {int((diff > 1e-9).sum())}, lower on {int((diff < -1e-9).sum())}]"))

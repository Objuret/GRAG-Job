"""Round 55, under his 2026-10-12 goal "solve this" (the order): a tie is exact from a cited
conversation (its nearest conversations are cited 28 to 29%) and worthless from one that is not
(2%), and half of what is handed over first is not cited (round 54). Do the handed-over
conversations that point at EACH OTHER tell the cited ones? With whole conversations and their
own vectors (not batches). The hundred, numbers only.

  the first conversations: the own conversations in the order as built, as many as fit in
  72,000 characters (C of round 40), and beside it the first 10 and the first 20 of the order
  a pair holds together when one is among the other's three nearest conversations of the
  product (own vectors), or they share a named thing
  1  of the first conversations: those that hold together with another of them | those that do
     not: how many a question, share with a cited message
  2  the order rebuilt: the conversations that hold together first (in the order as built),
     then the rest; and that with each one's three nearest right behind it
"""
import json
import pickle
import re
import sys
from collections import defaultdict
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
matrix = np.asarray(np.load(OWN / "own_units_query.npz", allow_pickle=True)["matrix"], dtype=np.float32)
row_of_talk = {}
for at, row in enumerate(rows):
    kind, product, *rest = row["id"].split("|")
    if kind == "talk":
        row_of_talk[(product, rest[0], int(rest[1]))] = at


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


together = {name: [0, 0, 0, 0] for name in ("as many as fit in 72,000", "the first 10", "the first 20")}
results = defaultdict(list)
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
    cited, cites = set(d["cited_ids"]), d["cites"]
    kind = [KINDS[x] for x in d["kind"]]
    own = [[r for r in d["records"][k] if not TI.apart(r, P)] for k in range(m)]
    chunk_len = d["length"].astype(np.int64)
    talk_records = defaultdict(list)
    for k in sorted(range(m), key=lambda k: (int(d["parent"][k]), int(d["id_rank"][k]))):
        if kind[k] == "slack_thread_batch":
            for r in own[k]:
                talk_records[P["talk_of"][r]].append(r)
    # every unit in the order as built: a conversation its own unit
    units, seen = [], set()
    for k in order.tolist():
        if not own[k]:
            continue
        if kind[k] != "slack_thread_batch":
            size = int(chunk_len[k]) if kind[k] in PARTS or len(own[k]) == len(d["records"][k]) else length_of(own[k], P)
            units.append((None, own[k], size, kind[k] in PARTS))
            continue
        for t in dict.fromkeys(P["talk_of"][r] for r in own[k]):
            if t not in seen:
                seen.add(t)
                units.append((t, talk_records[t], length_of(talk_records[t], P), False))
    talks = list(talk_records)
    at_of = {t: i for i, t in enumerate(talks)}
    vec = np.stack([matrix[row_of_talk[(product, t[0], t[1])]] for t in talks])
    among = vec @ vec.T
    np.fill_diagonal(among, -1.)
    nearest = np.argsort(-among, axis=1)[:, :3]
    things = {t: {" ".join(h.lower().split()) for r in rs for h in QUOTED.findall(P["raw"][r][1]["Message"]["User"]["text"])
                  if len(h.split()) >= 2} for t, rs in talk_records.items()}
    is_cited = {t: bool(cited & set(rs)) for t, rs in talk_records.items()}

    def holds(a, b):
        return at_of[b] in nearest[at_of[a]].tolist() or at_of[a] in nearest[at_of[b]].tolist() or bool(things[a] & things[b])

    in_order = [u[0] for u in units if u[0] is not None]
    used, fit = 0, []
    for t, records, chars, part in units:
        if used + chars > BUDGET:
            break
        used += chars
        if t is not None:
            fit.append(t)
    for name, first in (("as many as fit in 72,000", fit), ("the first 10", in_order[:10]), ("the first 20", in_order[:20])):
        for a in first:
            yes = any(holds(a, b) for b in first if b != a)
            row = together[name]
            row[0 if yes else 2] += 1
            row[1 if yes else 3] += is_cited[a]
    results["as built, a conversation its own unit"].append(
        hand_over(((u[1], u[2], u[3]) for u in units), cited, cites))
    for name, first in (("of the first 10", in_order[:10]), ("of the first 20", in_order[:20])):
        firm = {a for a in first if any(holds(a, b) for b in first if b != a)}
        front = [u for u in units if u[0] in firm]
        rest = [u for u in units if u[0] not in firm]
        results[f"the conversations that hold together {name} first, then the rest"].append(
            hand_over(((u[1], u[2], u[3]) for u in front + rest), cited, cites))
        by_talk = {u[0]: u for u in units if u[0] is not None}
        wide, put = [], set()
        for u in front:
            for t in [u[0]] + [talks[i] for i in nearest[at_of[u[0]]].tolist()]:
                if t not in put:
                    put.add(t)
                    wide.append(by_talk[t])
        results[f"that, with each one's three nearest right behind it ({name})"].append(
            hand_over(((u[1], u[2], u[3]) for u in wide + [u for u in units if u[0] not in put]), cited, cites))

n = len(Q)
print("== 1: of the first conversations: holding together with another of them: a question | share cited ; not: a question | share cited ==")
for name, (a, b, c, e) in together.items():
    print(f"  {a / n:5.1f} | {b / max(a, 1):4.0%} ; {c / n:5.1f} | {e / max(c, 1):4.0%}  {name}")
print("\n== 2: first handed over holds a cited record (of 100) | context_recall_id ==")
base = np.array([r[1] for r in results["as built, a conversation its own unit"]])
for name, got in results.items():
    a = np.array(got, dtype=np.float64)
    diff = a[:, 1] - base
    print(f"  {int(a[:, 0].sum()):3d} | {a[:, 1].mean():.3f}  {name}"
          + ("" if name.startswith("as built") else f"   [{diff.mean():+.3f}, standard error {diff.std(ddof=1) / 10:.3f}, higher on "
             f"{int((diff > 1e-9).sum())}, lower on {int((diff < -1e-9).sum())}]"))

"""Round 46, under his 2026-10-12 goal "solve this" (the hook's word: the order is not fixed): with
the records that are not the product's own work out and conversations whole, the first unit
holds a cited record on 50 of 100. What stands first when it is wrong, beside what is cited, by
the kind of thing each is (read from the records: the first word of the channel's name and what
the conversation links to; a diagnosis, not a design). The hundred, the combo order as built,
numbers only.

  1  the cited records of a question by kind of thing: share of the cited records
  2  the first unit handed over by kind of thing: questions where it holds a cited record | where not
  3  when it does not: the kind that stands first against the kind most of the question's cited
     records are in (how often each pair)
  4  where the first unit of the RIGHT kind stands, and where the first unit holding a cited record
"""
import pickle
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

sys.path[:0] = [r"C:\Coding\exjobbet\GRAG-Job\prod", r"C:\Coding\exjobbet\GRAG-Job\test"]
from artefact import v4_walk as WK  # noqa: E402

import ties as TI  # noqa: E402
from explore import load, standing  # noqa: E402

HERE = Path(__file__).resolve().parent
T = load()
Q, KINDS = T["questions"], T["kind_names"]
with open(HERE / "first_gold_signals_tags__gold100.pkl", "rb") as handle:
    extra = pickle.load(handle)
for qid, d in Q.items():
    d.update(extra[qid])
PARTS = ("document_part", "meeting_transcript_part")
OTHER = {"document": "a document", "document_part": "a document", "meeting_transcript": "a meeting",
         "meeting_transcript_part": "a meeting", "pr_batch": "own pull requests", "meeting_chat_batch": "a meeting chat",
         "url_batch": "urls"}


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


def kind_of_talk(t, P):
    own, _, public, things, _ = P["links"][t]
    channel = t[0].split("-")[0]
    if things:
        what = "a document" if any(P["raw"][x][0] == "documents" for x in things) else "an own pull request"
        return f"{channel} channel: a conversation that links to {what}"
    return f"{channel} channel: a conversation with no own link"


cited_kind, first_kind, pairs = Counter(), Counter(), Counter()
where_kind, where_cited = [], []
for qid, d in Q.items():
    P = TI.product(qid.split("::")[0])
    m = d["gold"].size
    order = combo(d)
    cited = set(d["cited_ids"])
    kind = [KINDS[x] for x in d["kind"]]
    own = [[r for r in d["records"][k] if not TI.apart(r, P)] for k in range(m)]
    talk_records = defaultdict(list)
    for k in sorted(range(m), key=lambda k: (int(d["parent"][k]), int(d["id_rank"][k]))):
        if kind[k] == "slack_thread_batch":
            for r in own[k]:
                talk_records[P["talk_of"][r]].append(r)
    # the units as whole conversations, each conversation its own unit, in the order their chunks show
    units, seen = [], set()
    for k in order.tolist():
        if not own[k]:
            continue
        if kind[k] != "slack_thread_batch":
            units.append((OTHER[kind[k]], own[k]))
            continue
        here = [t for t in dict.fromkeys(P["talk_of"][r] for r in own[k]) if t not in seen]
        seen.update(here)
        if here:
            units.append(("+".join(sorted({kind_of_talk(t, P) for t in here})), [r for t in here for r in talk_records[t]]))
    per_kind = Counter()
    for k in range(m):
        for r in own[k]:
            if r in cited:
                per_kind[kind_of_talk(P["talk_of"][r], P) if r in P["talk_of"] else OTHER[kind[k]]] += 1
    for name, count in per_kind.items():
        cited_kind[name] += count
    main = per_kind.most_common(1)[0][0] if per_kind else "none"
    first_name, first_records = units[0]
    right = bool(cited & set(first_records))
    first_kind[(first_name, right)] += 1
    if not right:
        pairs[(first_name, main)] += 1
    where_kind.append(next((at for at, (name, _) in enumerate(units, 1) if main in name.split("+")), len(units) + 1))
    where_cited.append(next((at for at, (_, rs) in enumerate(units, 1) if cited & set(rs)), len(units) + 1))

total = sum(cited_kind.values())
print("== 1: the cited records by kind of thing: share of the cited records ==")
for name, count in cited_kind.most_common():
    print(f"  {count / total:5.1%}  {name}")
print("\n== 2: the first unit by kind of thing: questions where it holds a cited record | where it does not ==")
names = sorted({name for name, _ in first_kind}, key=lambda n: -(first_kind[(n, True)] + first_kind[(n, False)]))
for name in names:
    print(f"  {first_kind[(name, True)]:3d} | {first_kind[(name, False)]:3d}  {name}")
print("\n== 3: when it does not: what stands first  <-  what most of the cited records are (questions) ==")
for (first, main), count in pairs.most_common(16):
    print(f"  {count:3d}  {first}   <-   {main}")
a, b = np.array(where_kind), np.array(where_cited)
print(f"\n== 4: place of the first unit of the kind most of the cited records are in: 1 on {int((a == 1).sum())}, 2-3 on "
      f"{int(((a >= 2) & (a <= 3)).sum())}, further on {int((a > 3).sum())}; place of the first unit holding a cited record: "
      f"1 on {int((b == 1).sum())}, 2-3 on {int(((b >= 2) & (b <= 3)).sum())}, 4-6 on {int(((b >= 4) & (b <= 6)).sum())}, "
      f"further on {int((b > 6).sum())} ==")

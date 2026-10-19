"""Round 48, under his 2026-10-12 goal "solve this": how deep the cited records lie in the order once
the records that are not the product's own work are out and conversations are whole. The
hundred, the combo order as built, numbers only.

  1  share of a question's cited records inside the first 72,000 characters, the first 144,000,
     216,000, 360,000, and all (a mean over the 100 questions)
  2  what the first 72,000 characters are made of, by kind of thing: characters | cited records
  3  the same order with the kinds of thing in turn left for last (to see what each kind costs
     and brings; a diagnosis with the gold in hand, not a design)
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
PARTS = ("document_part", "meeting_transcript_part")
OTHER = {"document": "documents", "document_part": "documents", "meeting_transcript": "meetings",
         "meeting_transcript_part": "meetings", "pr_batch": "own pull requests", "meeting_chat_batch": "meeting chats",
         "url_batch": "urls"}
BUDGETS = (72000, 144000, 216000, 360000, 10 ** 9)


def length_of(records, P):
    return sum(P["size"][r] for r in records) + max(len(records) - 1, 0)


depth = {b: [] for b in BUDGETS}
made_chars, made_cited = Counter(), Counter()
last_kind = defaultdict(list)
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
    cited, cites = set(d["cited_ids"]), d["cites"]
    kind = [KINDS[x] for x in d["kind"]]
    own = [[r for r in d["records"][k] if not TI.apart(r, P)] for k in range(m)]
    chunk_len = d["length"].astype(np.int64)
    talk_records = defaultdict(list)
    for k in sorted(range(m), key=lambda k: (int(d["parent"][k]), int(d["id_rank"][k]))):
        if kind[k] == "slack_thread_batch":
            for r in own[k]:
                talk_records[P["talk_of"][r]].append(r)
    units, seen, sent = [], set(), set()
    for k in order.tolist():
        if not own[k]:
            continue
        if kind[k] != "slack_thread_batch":
            size = int(chunk_len[k]) if kind[k] in PARTS or len(own[k]) == len(d["records"][k]) else length_of(own[k], P)
            units.append((OTHER[kind[k]], own[k], size, kind[k] in PARTS))
            continue
        ids_ = []
        for r in own[k]:
            t = P["talk_of"][r]
            if t not in seen:
                seen.add(t)
                ids_.extend(talk_records[t])
        ids_ = [r for r in dict.fromkeys(ids_) if r not in sent]
        if ids_:
            units.append(("Slack conversations", ids_, length_of(ids_, P), False))
            sent.update(ids_)

    def run(units, budget, tally=False):
        used, got = 0, set()
        for name, records, chars, part in units:
            new = [r for r in records if r not in got]
            if not new and not part:
                continue
            if used + chars > budget:
                break
            used += chars
            got.update(records)
            if tally:
                made_chars[name] += chars
                made_cited[name] += len(cited & set(new))
        return len(cited & got) / cites

    for b in BUDGETS:
        depth[b].append(run(units, b, tally=b == 72000))
    for name in ("meetings", "documents", "own pull requests"):
        last_kind[name].append(run([u for u in units if u[0] != name] + [u for u in units if u[0] == name], 72000))
n = len(Q)
print("== 1: context_recall_id by how many characters are handed over, the same order ==")
for b in BUDGETS:
    print(f"  {np.mean(depth[b]):.3f}  " + ("everything" if b == 10 ** 9 else f"{b:,} characters"))
print("\n== 2: what the first 72,000 characters are made of: share of the characters | share of the cited records found in them ==")
tc, tr = sum(made_chars.values()), sum(made_cited.values())
for name, chars in made_chars.most_common():
    print(f"  {chars / tc:5.1%} | {made_cited[name] / tr:5.1%}  {name}")
print("\n== 3: context_recall_id inside 72,000 when one kind of thing is left for last (as built: "
      f"{np.mean(depth[72000]):.3f}) ==")
for name, got in last_kind.items():
    diff = np.array(got) - np.array(depth[72000])
    print(f"  {np.mean(got):.3f}  {name} last   [{diff.mean():+.3f}, standard error {diff.std(ddof=1) / 10:.3f}, higher on "
          f"{int((diff > 1e-9).sum())}, lower on {int((diff < -1e-9).sum())}]")

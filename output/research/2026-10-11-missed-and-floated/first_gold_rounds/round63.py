"""Round 63, under his 2026-10-12 goal "solve this" (the order): a company named in the question
leads through the graph (Customer-[company]->Company) to its customers, and the messages name a
customer by its id: 2.7 conversations a question, 39% of them cited, on the 18 questions of the
hundred that hold a company's name (`the_company_a_question_names`). His 2026-10-06 side
thought: "names of people, products and channels ... a match on one of those does NOT pick/boost
a chunk, it picks/boosts a scope". Tried here as that: the chunks holding a conversation that
names a customer of the named company are boosted. The hundred, the step as it stands (the combo
order, the product's own work, conversations whole); numbers only.

  C    the step as it stands
  N1   those chunks first inside a step (before the scope's chunks)
  N2   those chunks before every other chunk, in the combo's order among themselves
  N3   N2, the conversation that names the customer first among the chunk's conversations
each: first text holds a cited record | context_recall_id, over the questions that hold a
company's name, and over the hundred
"""
import json
import pickle
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

REPO = Path("C:/Coding/exjobbet/GRAG-Job")
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402

import ties as TI  # noqa: E402
from explore import BUDGET, load, standing  # noqa: E402

HERE = Path(__file__).resolve().parent
T = load()
Q, KINDS = T["questions"], T["kind_names"]
with open(HERE / "first_gold_signals_tags__gold100.pkl", "rb") as handle:
    extra = pickle.load(handle)
PARTS = ("document_part", "meeting_transcript_part")
CUST = re.compile(r"CUST-\d+")
asked = {q.id: q.question for q in HQ.load_questions()}
customers = json.loads((REPO / "data/raw/Salesforce__HERB/metadata/customers_data.json").read_text(encoding="utf-8"))


def plain(text):
    return " " + re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip() + " "


of_company = defaultdict(set)
for row in customers:
    of_company[plain(row["company"])].add(row["id"])


def length_of(records, P):
    return sum(P["size"][r] for r in records) + max(len(records) - 1, 0)


results = defaultdict(list)
named_questions = []
for qid, d in Q.items():
    d.update(extra[qid])
    P = TI.product(qid.split("::")[0])
    m = d["gold"].size
    cited, cites = set(d["cited_ids"]), d["cites"]
    kind = [KINDS[x] for x in d["kind"]]
    own = [[r for r in d["records"][k] if not TI.apart(r, P)] for k in range(m)]
    chunk_len = d["length"].astype(np.int64)
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
    words = plain(asked[qid])
    wanted = set().union(*[of_company[name] for name in of_company if name in words])
    named_questions.append(bool(wanted))
    talk_records = defaultdict(list)
    for k in sorted(range(m), key=lambda k: (int(d["parent"][k]), int(d["id_rank"][k]))):
        if kind[k] == "slack_thread_batch":
            for r in own[k]:
                talk_records[P["talk_of"][r]].append(r)
    names_it = {t for t, rs in talk_records.items()
                if wanted & {c for r in rs for c in CUST.findall(P["raw"][r][1]["Message"]["User"]["text"])}}
    boosted = np.array([kind[k] == "slack_thread_batch" and any(P["talk_of"][r] in names_it for r in own[k]) for k in range(m)])

    def send(by, named_first=False):
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
                if named_first:
                    here.sort(key=lambda t: t not in names_it)
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

    results["C   the step as it stands"].append(send(np.lexsort((d["id_rank"], -z, ~scope, step))))
    results["N1  the chunks naming a customer of the named company first inside a step"].append(
        send(np.lexsort((d["id_rank"], -z, ~scope, ~boosted, step))))
    results["N2  those chunks before every other chunk"].append(send(np.lexsort((d["id_rank"], -z, ~scope, step, ~boosted))))
    results["N3  N2, the conversation that names the customer first in its chunk"].append(
        send(np.lexsort((d["id_rank"], -z, ~scope, step, ~boosted)), named_first=True))

named = np.array(named_questions)
print(f"questions that hold a company's name: {int(named.sum())} of {named.size}")
print("over those questions: first text holds a cited record, context_recall_id | over the hundred: the same")
base = np.array([r[1] for r in results["C   the step as it stands"]])
for name, got in results.items():
    a = np.array(got, dtype=np.float64)
    diff = a[:, 1] - base
    print(f"  {int(a[named, 0].sum()):2d} of {int(named.sum())}, {a[named, 1].mean():.3f} | {int(a[:, 0].sum()):3d}, {a[:, 1].mean():.3f}  {name}"
          + ("" if name.startswith("C  ") else f"   [the hundred: {diff.mean():+.3f}, standard error {diff.std(ddof=1) / 10:.3f}, higher on "
             f"{int((diff > 1e-9).sum())}, lower on {int((diff < -1e-9).sum())}]"))

"""Round 64, under his 2026-10-12 goal "solve this" (the order): a company's name in the question
leads through the graph to the right conversations (round 63). The other names a question holds
are the graph's own TAGS that stand in it word for word (round 37: chunks carrying one of three
words or more are gold 46%, and reordering chunks by it moved nothing). With conversations whole
and the records that are not the product's own work left out, the same name can be looked for
in the conversation's own messages. The hundred, numbers only.

  a name   a tag of the product that stands in the question word for word, by how many words
  1  questions that hold one; own conversations whose messages hold that name word for word:
     how many a question | share with a cited message | share of the question's cited
     conversations among them
  2  the step as it stands with those conversations' chunks before every other chunk (names of
     two words or more; of three or more), and with the company's customers as in round 63
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


BANDS = (("two words or more", 2), ("three words or more", 3))
count = {name: [0, 0, 0, 0, 0] for name, _ in BANDS}
results = defaultdict(list)
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
    talk_records = defaultdict(list)
    for k in sorted(range(m), key=lambda k: (int(d["parent"][k]), int(d["id_rank"][k]))):
        if kind[k] == "slack_thread_batch":
            for r in own[k]:
                talk_records[P["talk_of"][r]].append(r)
    text_of = {t: plain(" ".join(P["raw"][r][1]["Message"]["User"]["text"] for r in rs)) for t, rs in talk_records.items()}
    is_cited = {t: bool(cited & set(rs)) for t, rs in talk_records.items()}
    names = [" " + " ".join(words) + " " if not isinstance(words, str) else plain(words) for words in d["named_tag_words"]]
    marked = {}
    for label, least in BANDS:
        mine = [n for n in names if len(n.split()) >= least]
        holds = {t for t, text in text_of.items() if any(n in text for n in mine)}
        marked[label] = holds
        row = count[label]
        row[0] += bool(mine)
        if mine:
            row[1] += len(holds)
            row[2] += sum(is_cited[t] for t in holds)
            row[3] += sum(is_cited.values())
            row[4] += sum(1 for t in holds if is_cited[t])
    words = plain(asked[qid])
    wanted = set().union(*[of_company[name] for name in of_company if name in words])
    by_company = {t for t, rs in talk_records.items()
                  if wanted & {c for r in rs for c in CUST.findall(P["raw"][r][1]["Message"]["User"]["text"])}}

    def flag(talks):
        return np.array([kind[k] == "slack_thread_batch" and any(P["talk_of"][r] in talks for r in own[k]) for k in range(m)])

    def send(by, first_talks=frozenset()):
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
                here.sort(key=lambda t: t not in first_talks)
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
    for label, _ in BANDS:
        b = flag(marked[label])
        results[f"T   chunks with a conversation holding a name of {label} before every other"].append(
            send(np.lexsort((d["id_rank"], -z, ~scope, step, ~b)), marked[label]))
    b = flag(by_company)
    results["N   chunks naming a customer of the named company before every other (round 63)"].append(
        send(np.lexsort((d["id_rank"], -z, ~scope, step, ~b)), by_company))
    both = by_company | marked["three words or more"]
    b = flag(both)
    results["NT  the company's and the names of three words or more, together"].append(
        send(np.lexsort((d["id_rank"], -z, ~scope, step, ~b)), both))

n = len(Q)
print("== 1: questions that hold a name | own conversations holding it, a question | of them with a cited message | "
      "share of those questions' cited conversations among them ==")
for label, (qs, reached, hit, cited_n, cited_in) in count.items():
    print(f"  {qs:3d} | {reached / max(qs, 1):5.1f} | {hit / max(reached, 1):4.0%} | {cited_in / max(cited_n, 1):4.0%}  names of {label}")
print("\n== 2: first text holds a cited record (of 100) | context_recall_id ==")
base = np.array([r[1] for r in results["C   the step as it stands"]])
for name, got in results.items():
    a = np.array(got, dtype=np.float64)
    diff = a[:, 1] - base
    print(f"  {int(a[:, 0].sum()):3d} | {a[:, 1].mean():.3f}  {name}"
          + ("" if name.startswith("C  ") else f"   [{diff.mean():+.3f}, standard error {diff.std(ddof=1) / 10:.3f}, higher on "
             f"{int((diff > 1e-9).sum())}, lower on {int((diff < -1e-9).sum())}]"))

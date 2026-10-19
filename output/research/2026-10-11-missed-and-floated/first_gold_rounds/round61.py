"""Round 61, under his 2026-10-12 goal "solve this" (the order): every vector reading lands at the
same place. The one reading of another kind is the question's own words in a unit's own text
(found on 2026-10-11: "the words that tell a case apart are in the chunk's text and the tags
plus description hold a fifth of them"; then counted over batches with the other projects' talk
in them: +0.048). Here over clean units: the records that are not the product's own work left
out, a conversation whole. The hundred, inside the question's product, the question without
the product's name; numbers only.

  the words' fit   BM25 of the question's words in the unit's own text, the units of the
                   product as the collection (the textbook form, k1 1.2 and b 0.75: its usual
                   settings, not chosen here)
  C    the combo order as built, whole own conversations as their chunks show
  W1   the units by the words' fit alone
  W2   the unit's standing by the words' fit and the combo's value of its best chunk, added
  W3   the combo's step and scope of the unit's best chunk first, W2 inside
  W4   C, the conversations of one chunk in the order of their words' fit
"""
import math
import pickle
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

REPO = Path("C:/Coding/exjobbet/GRAG-Job")
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402
from harness.record_text import record_text  # noqa: E402

import ties as TI  # noqa: E402
from explore import BUDGET, load, standing  # noqa: E402

HERE = Path(__file__).resolve().parent
T = load()
Q, KINDS = T["questions"], T["kind_names"]
with open(HERE / "first_gold_signals_tags__gold100.pkl", "rb") as handle:
    extra = pickle.load(handle)
PARTS = ("document_part", "meeting_transcript_part")
WORD = re.compile(r"[a-z0-9]+")
asked = {q.id: q.question for q in HQ.load_questions()}
K1, B = 1.2, 0.75


def without_the_name(question, name):
    parts = WORD.findall(name.lower())
    pattern = re.compile(r"(?<![A-Za-z0-9])" + r"[^A-Za-z0-9]*".join(map(re.escape, parts)) + r"(?![A-Za-z0-9])", re.IGNORECASE)
    return " ".join(pattern.sub("the product", question).split())


def text_of(rid, P):
    kind, r = P["raw"][rid]
    return r["Message"]["User"]["text"] if kind == "slack" else record_text(kind, r)


def bm25(query, docs):
    n = len(docs)
    df = Counter(w for doc in docs for w in set(doc))
    mean = sum(len(doc) for doc in docs) / max(n, 1)
    out = np.zeros(n)
    for w in set(query):
        if w not in df:
            continue
        idf = math.log(1. + (n - df[w] + .5) / (df[w] + .5))
        for i, doc in enumerate(docs):
            tf = doc[w] if isinstance(doc, Counter) else 0
            if tf:
                out[i] += idf * tf * (K1 + 1.) / (tf + K1 * (1. - B + B * sum(doc.values()) / mean))
    return out


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


def length_of(records, P):
    return sum(P["size"][r] for r in records) + max(len(records) - 1, 0)


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
    place = np.empty(m, dtype=np.int64)
    place[order] = np.arange(m)
    cited, cites = set(d["cited_ids"]), d["cites"]
    kind = [KINDS[x] for x in d["kind"]]
    own = [[r for r in d["records"][k] if not TI.apart(r, P)] for k in range(m)]
    chunk_len = d["length"].astype(np.int64)
    units, by_talk = [], {}
    for k in sorted(range(m), key=lambda k: (int(d["parent"][k]), int(d["id_rank"][k]))):
        if kind[k] == "slack_thread_batch":
            for r in own[k]:
                t = P["talk_of"][r]
                if t not in by_talk:
                    by_talk[t] = len(units)
                    units.append([[], None, False, k])
                u = units[by_talk[t]]
                u[0].append(r)
                if place[k] < place[u[3]]:
                    u[3] = k
        elif own[k]:
            size = int(chunk_len[k]) if kind[k] in PARTS or len(own[k]) == len(d["records"][k]) else length_of(own[k], P)
            units.append([own[k], size, kind[k] in PARTS, k])
    for u in units:
        if u[1] is None:
            u[1] = length_of(u[0], P)
    docs = [Counter(WORD.findall(" ".join(text_of(r, P) for r in dict.fromkeys(u[0])).lower())) for u in units]
    query = WORD.findall(without_the_name(asked[qid], product).lower())
    fit = bm25(query, docs)
    best = np.array([u[3] for u in units])
    spot = np.arange(len(units))
    send = lambda by: hand_over(((units[i][0], units[i][1], units[i][2]) for i in by.tolist()), cited, cites)  # noqa: E731
    results["C   the combo order as built, whole own conversations"].append(send(np.lexsort((spot, place[best]))))
    results["W1  the units by the words' fit alone"].append(send(np.lexsort((spot, -fit))))
    both = standing(fit) + standing(z[best])
    results["W2  the words' fit and the combo's value of the best chunk, as standings, added"].append(send(np.lexsort((spot, -both))))
    results["W3  the combo's step and scope of the best chunk first, W2 inside"].append(
        send(np.lexsort((spot, -both, ~scope[best], step[best]))))
    results["W4  C, the conversations of one chunk in the order of their words' fit"].append(
        send(np.lexsort((spot, -fit, place[best]))))

print("first handed over holds a cited record (of 100) | context_recall_id")
base = np.array([r[1] for r in results["C   the combo order as built, whole own conversations"]])
for name, got in results.items():
    a = np.array(got, dtype=np.float64)
    diff = a[:, 1] - base
    print(f"  {int(a[:, 0].sum()):3d} | {a[:, 1].mean():.3f}  {name}"
          + ("" if name.startswith("C  ") else f"   [{diff.mean():+.3f}, standard error {diff.std(ddof=1) / 10:.3f}, higher on "
             f"{int((diff > 1e-9).sum())}, lower on {int((diff < -1e-9).sum())}]"))

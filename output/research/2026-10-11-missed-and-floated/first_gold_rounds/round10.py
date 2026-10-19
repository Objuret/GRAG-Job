"""Round 10: do the readings fail on the same questions or on different ones? And can the reading to
trust be told per question from how far its first chunk stands out?"""
import pickle
from itertools import combinations
from pathlib import Path

import numpy as np

from explore import load, report, standing

HERE = Path(__file__).resolve().parent
data = load()
Q = data["questions"]
for name in ("more", "bare"):
    with open(HERE / f"first_gold_signals_{name}__gold100.pkl", "rb") as handle:
        extra = pickle.load(handle)
    for qid, d in Q.items():
        d.update(extra[qid])
KEPT = Path(r"C:\Coding\exjobbet\GRAG-Job\output\embed_local\20261007_rev113abe4acafa_float32")
corpus = np.load(KEPT / "corpus_passage.npz", allow_pickle=True)
row_of = {str(r): k for k, r in enumerate(corpus["ids"])}
matrix = np.asarray(corpus["matrix"], dtype=np.float32)
matrix = matrix / np.linalg.norm(matrix, axis=1, keepdims=True)
for d in Q.values():
    rows = [np.array([row_of[r] for r in recs if r in row_of], dtype=np.int64) for recs in d["records"]]
    near = [matrix[r] @ d["bare_vector"].astype(np.float32) if r.size else np.array([-1.], dtype=np.float32) for r in rows]
    d["record_best_bare"] = np.array([float(x.max()) for x in near])
    d["record_top2_bare"] = np.array([float(np.sort(x)[-2:].mean()) for x in near])

READ = {
    "question without the name against descriptions (own pairing)": lambda d: d["bare_to_passage"],
    "question without the name against the two closest records": lambda d: d["record_top2_bare"],
    "query tags against descriptions (own pairing), mean": lambda d: d["bare_tags_to_passage"].mean(axis=0),
    "query tags against the chunk's tags, mean": lambda d: d["fit"].mean(axis=0),
    "query description against descriptions": lambda d: d["description"],
    "the question's words on the chunk text": lambda d: d["words"],
}
names = list(READ)
ids = list(Q)
top = {name: {} for name in names}
for q in ids:
    d = Q[q]
    for name in names:
        top[name][q] = int(np.lexsort((d["id_rank"], -np.asarray(READ[name](d), dtype=np.float64)))[0])
gold_first = {name: np.array([bool(Q[q]["gold"][top[name][q]]) for q in ids]) for name in names}
print("== first chunk gold, each reading ==")
for name in names:
    print(f"  {int(gold_first[name].sum()):3d}  {name}")
print(f"\nat least one of the six has a gold chunk first on {int(np.any(list(gold_first.values()), axis=0).sum())} of 100; "
      f"all six on {int(np.all(list(gold_first.values()), axis=0).sum())}; none on "
      f"{int((~np.any(list(gold_first.values()), axis=0)).sum())}")
for a, b in combinations(names[:4], 2):
    both = int((gold_first[a] & gold_first[b]).sum())
    either = int((gold_first[a] | gold_first[b]).sum())
    same = sum(top[a][q] == top[b][q] for q in ids)
    same_gold = sum(top[a][q] == top[b][q] and Q[q]["gold"][top[a][q]] for q in ids)
    print(f"  {a[:44]:44s} & {b[:44]:44s}: both gold first {both}, either {either}; the same first chunk on {same}, "
          f"gold on {same_gold} of those")

# how many of the six agree on the first chunk, and is it gold then
agree = {}
for q in ids:
    counts = {}
    for name in names:
        counts[top[name][q]] = counts.get(top[name][q], 0) + 1
    chunk, votes = max(counts.items(), key=lambda kv: (kv[1], -Q[q]["id_rank"][kv[0]]))
    agree.setdefault(votes, []).append(bool(Q[q]["gold"][chunk]))
print("\n== the chunk most of the six readings put first: readings agreeing | questions | gold ==")
for votes in sorted(agree, reverse=True):
    print(f"  {votes} | {len(agree[votes])} | {sum(agree[votes])}")


def standout(d, name):
    v = np.sort(np.asarray(READ[name](d), dtype=np.float64))[::-1]
    spread = 1.4826 * np.median(np.abs(v - np.median(v)))
    return (v[0] - v[1]) / spread if spread > 0 else 0.


def trusted(d):
    """The first chunk of the reading whose first chunk stands furthest above its second; then the plain sum."""
    best = max(names, key=lambda name: standout(d, name))
    score = sum(standing(READ[name](d)) for name in names)
    lead = int(np.lexsort((d["id_rank"], -np.asarray(READ[best](d), dtype=np.float64)))[0])
    score = score.copy()
    score[lead] = score.max() + 1.
    return score


def most_agreed(d):
    """The chunk most readings put first, then the plain sum."""
    counts = {}
    for name in names:
        k = int(np.lexsort((d["id_rank"], -np.asarray(READ[name](d), dtype=np.float64)))[0])
        counts[k] = counts.get(k, 0) + 1
    score = sum(standing(READ[name](d)) for name in names)
    best = max(counts.items(), key=lambda kv: (kv[1], score[kv[0]]))[0]
    score = score.copy()
    score[best] = score.max() + 1.
    return score


print()
report({
    "the six readings' standings added": lambda d: sum(standing(READ[name](d)) for name in names),
    "the highest single standing a chunk has in any of the six": lambda d: np.max([standing(READ[name](d)) for name in names], axis=0),
    "the first chunk of the reading whose first stands out most, then the sum": trusted,
    "the chunk most readings put first, then the sum": most_agreed,
    "the first four readings' standings added": lambda d: sum(standing(READ[name](d)) for name in names[:4]),
    "the first three readings' standings added": lambda d: sum(standing(READ[name](d)) for name in names[:3]),
    "the first two readings' standings added": lambda d: sum(standing(READ[name](d)) for name in names[:2]),
}, data, sort=False)

# where it stands out: the standout of the best single reading against whether its first chunk is gold
values = np.array([standout(Q[q], names[0]) for q in ids])
order = np.argsort(-values)
print("\n== the question without the name against descriptions: questions ordered by how far its first chunk stands "
      "above its second; gold first in each quarter of them ==")
for k in range(4):
    part = order[k * 25:(k + 1) * 25]
    print(f"  quarter {k + 1}: gold first on {int(gold_first[names[0]][part].sum())} of 25 (standing out by "
          f"{values[part].min():.2f} to {values[part].max():.2f} spreads)")

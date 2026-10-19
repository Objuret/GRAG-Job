"""Round 8: the name taken out of the rest of the query side, and the question without the name against
the single records (the baseline's record vectors, passage mode)."""
import pickle
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
    for label, vector in (("bare", d["bare_vector"]), ("named", d["question_vector"])):
        near = [matrix[r] @ vector.astype(np.float32) if r.size else np.array([-1.], dtype=np.float32) for r in rows]
        d[f"record_best_{label}"] = np.array([float(x.max()) for x in near])
        d[f"record_mean_{label}"] = np.array([float(x.mean()) for x in near])
        d[f"record_top2_{label}"] = np.array([float(np.sort(x)[-2:].mean()) for x in near])
    d["rows_middle"] = np.array([matrix[r].mean(axis=0) @ d["bare_vector"].astype(np.float32) / max(float(np.linalg.norm(matrix[r].mean(axis=0))), 1e-9)
                                 if r.size else -1. for r in rows])


def K(key):
    return lambda d: d[key]


def add(*fs):
    return lambda d: sum(standing(f(d)) for f in fs)


singles = {
    "question without the name against descriptions, own pairing": K("bare_to_passage"),
    "closest record, question with the name": K("record_best_named"),
    "closest record, question without the name": K("record_best_bare"),
    "two closest records, question without the name": K("record_top2_bare"),
    "records on average, question without the name": K("record_mean_bare"),
    "the middle of the chunk's records, question without the name": K("rows_middle"),
    "query description without the name, query both sides": K("bare_description"),
    "query description without the name, as a query against passage": K("bare_description_to_passage"),
    "query description, query both sides": K("description"),
    "query tags without the name: mean of the chunk's closest tag": lambda d: d["bare_fit"].mean(axis=0),
    "query tags: mean of the chunk's closest tag": lambda d: d["fit"].mean(axis=0),
    "query tags without the name against descriptions (passage), mean": lambda d: d["bare_tags_to_passage"].mean(axis=0),
    "query tags without the name against descriptions (query), mean": lambda d: d["bare_tags_description"].mean(axis=0),
}
print("== single readings ==")
report(singles, data)

B, R = K("bare_to_passage"), K("record_best_bare")
T = singles["query tags without the name: mean of the chunk's closest tag"]
TD = singles["query tags without the name against descriptions (query), mean"]
joins = {
    "question without the name: descriptions (own pairing) + closest record": add(B, R),
    "the same + the chunk's tags (own pairing)": add(B, R, K("bare_to_tags_passage")),
    "the same + words on the chunk text": add(B, R, K("words")),
    "descriptions + closest record + query tags' mean": add(B, R, T),
    "descriptions + closest record + query tags' mean + query tags against descriptions": add(B, R, T, TD),
    "descriptions + closest record + query tags' mean + words": add(B, R, T, K("words")),
    "descriptions + query tags' mean + query tags against descriptions": add(B, T, TD),
    "descriptions + query tags against descriptions": add(B, TD),
    "descriptions twice + closest record + query tags' mean": lambda d: 2 * standing(B(d)) + standing(R(d)) + standing(T(d)),
    "descriptions + two closest records": add(B, K("record_top2_bare")),
    "descriptions + records on average": add(B, K("record_mean_bare")),
}
print("\n== joined ==")
report(joins, data)

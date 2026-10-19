"""Round 9, a diagnosis and not a design: the fitted check of round 3 again with the readings found
since (the question without the product's name in the embedder's own pairing, against the
descriptions and against the single records; the query tags against the descriptions in that
pairing). Held out by product in five folds, and the folds drawn five different ways."""
import pickle
import warnings
from pathlib import Path

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression

from explore import load, measure, standing

warnings.filterwarnings("ignore")
HERE = Path(__file__).resolve().parent
data = load()
Q = data["questions"]
for name in ("more", "bare"):
    with open(HERE / f"first_gold_signals_{name}__gold100.pkl", "rb") as handle:
        extra = pickle.load(handle)
    for qid, d in Q.items():
        d.update(extra[qid])
with open(HERE / "what_a_chunk_holds.pkl", "rb") as handle:
    HOLDS = pickle.load(handle)
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
KINDS = len(data["kind_names"])


def rel_place(x):
    order = np.argsort(-np.asarray(x, dtype=np.float64), kind="stable")
    place = np.empty(order.size)
    place[order] = np.arange(order.size)
    return np.log1p(place)


def features(d):
    old = {"tags_max": d["tags"], "tags_mean": d["fit"].mean(axis=0), "tagdesc_mean": d["tags_description"].mean(axis=0),
           "description": d["description"], "question": d["question"], "question_bare": d["question_bare"],
           "question_tags": d["question_tags"], "description_tags": d["description_tags"],
           "record_best": d["record_best"], "words": d["words"]}
    new = {"bare_to_passage": d["bare_to_passage"], "record_best_bare": d["record_best_bare"],
           "record_top2_bare": d["record_top2_bare"], "bare_tags_to_passage": d["bare_tags_to_passage"].mean(axis=0),
           "bare_to_tags_passage": d["bare_to_tags_passage"], "question_to_passage": d["question_to_passage"],
           "description_passage": d["description_passage_to_passage"], "tags_passage_mean": d["tags_passage_mean"],
           "words_on_both": d["words_on_both"]}
    parent_size = np.bincount(d["parent"])[d["parent"]]
    what = ([(d["kind"] == k).astype(float) for k in range(KINDS)]
            + [np.log(d["length"]), np.array([len(r) for r in d["records"]], dtype=float),
               d["spot"] / np.maximum(parent_size - 1, 1), np.log(parent_size)]
            + [HOLDS["table"][d["chunks"], k] for k in range(HOLDS["table"].shape[1])])
    groups = {
        "the readings of round 3": [standing(v) for v in old.values()] + [rel_place(v) for v in old.values()],
        "the readings found since": [standing(v) for v in new.values()] + [rel_place(v) for v in new.values()],
        "what the chunk is and holds": what,
    }
    return {name: np.column_stack(cols) for name, cols in groups.items()}


ids = list(Q)
built = {qid: features(Q[qid]) for qid in ids}
product = {qid: int(Q[qid]["chunks"].min()) for qid in ids}
names = sorted(set(product.values()))


def run(group_names, model, seed):
    draw = np.random.default_rng(seed).permutation(len(names))
    fold_of = {names[k]: int(i % 5) for i, k in enumerate(draw)}
    firsts, places, recalls = 0, [], []
    for fold in range(5):
        train = [q for q in ids if fold_of[product[q]] != fold]
        test = [q for q in ids if fold_of[product[q]] == fold]
        X = np.vstack([np.hstack([built[q][g] for g in group_names]) for q in train])
        y = np.concatenate([Q[q]["gold"] for q in train]).astype(int)
        clf = (LogisticRegression(C=1.0, max_iter=3000, class_weight="balanced") if model == "linear"
               else HistGradientBoostingClassifier(max_depth=3, max_iter=150, learning_rate=0.06,
                                                   class_weight="balanced", random_state=seed))
        clf.fit(X, y)
        for q in test:
            first, place, recall = measure(clf.predict_proba(np.hstack([built[q][g] for g in group_names]))[:, 1], Q[q])
            firsts += int(first)
            places.append(place)
            recalls.append(recall)
    places = np.array(places)
    return firsts, int((places <= 3).sum()), int((places <= 5).sum()), float(np.mean(recalls))


print("held out by product, five folds, the folds drawn five ways: first chunk gold (of 100), each draw | their mean | "
      "first gold within 3, mean | within 5, mean | context_recall_id, mean")
sets = (("the readings of round 3",), ("the readings found since",), ("the readings of round 3", "the readings found since"),
        ("the readings of round 3", "the readings found since", "what the chunk is and holds"))
for model in ("linear", "trees"):
    for group_names in sets:
        got = [run(list(group_names), model, seed) for seed in range(5)]
        print(f"  {[g[0] for g in got]} | {np.mean([g[0] for g in got]):.1f} | {np.mean([g[1] for g in got]):.1f} | "
              f"{np.mean([g[2] for g in got]):.1f} | {np.mean([g[3] for g in got]):.3f}  {model}: " + " + ".join(group_names))

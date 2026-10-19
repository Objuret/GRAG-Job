"""Round 3, a diagnosis and not a design: is there ANY reading in the table that tells the gold chunk
from the near misses? A ranker is fitted on the questions of 29 products' worth and tried on the
questions of the products left out (the products split in five folds), so what it shows is not
learned from the questions it is tried on. Groups of readings are added one at a time."""
import warnings

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression

from explore import load, measure, standing

warnings.filterwarnings("ignore")
data = load()
Q = data["questions"]
KINDS = len(data["kind_names"])


def hub(d):
    among = d["among"].astype(np.float64).copy()
    np.fill_diagonal(among, np.nan)
    return np.nanmean(among, axis=1)


def rel_place(x):
    order = np.argsort(-np.asarray(x, dtype=np.float64), kind="stable")
    place = np.empty(order.size)
    place[order] = np.arange(order.size)
    return np.log1p(place)


def neighbours(d):
    """Per chunk the indices of the chunk before and after it in its parent (-1 where none)."""
    before, after = np.full(d["gold"].size, -1), np.full(d["gold"].size, -1)
    at = {(int(p), int(s)): k for k, (p, s) in enumerate(zip(d["parent"], d["spot"]))}
    for k, (p, s) in enumerate(zip(d["parent"], d["spot"])):
        before[k] = at.get((int(p), int(s) - 1), -1)
        after[k] = at.get((int(p), int(s) + 1), -1)
    return before, after


def features(d):
    near = {
        "tags_max": d["tags"], "tags_mean": d["fit"].mean(axis=0),
        "tagdesc_mean": d["tags_description"].mean(axis=0), "tagdesc_max": d["tags_description"].max(axis=0),
        "description": d["description"], "question": d["question"], "question_bare": d["question_bare"],
        "question_tags": d["question_tags"], "description_tags": d["description_tags"],
        "question_bare_tags": d["question_bare_tags"],
    }
    text = {"record_best": d["record_best"], "record_mean": d["record_mean"], "words": d["words"]}
    kind_part = {"kind_tags": d["kind_tags"], "kind_description": d["kind_description"],
                 "kind_question": d["kind_question"]}
    groups = {}
    groups["the plain three"] = [standing(near[k]) for k in ("tags_max", "description", "question")]
    groups["every nearness reading of the layer"] = (
        [standing(v) for v in near.values()] + [rel_place(v) for v in near.values()])
    groups["the record vectors and the question's words"] = (
        [standing(v) for v in text.values()] + [rel_place(v) for v in text.values()])
    groups["the look-alikes in the other products"] = [standing(v) for v in kind_part.values()]
    edge = np.nan_to_num(d["edge"], nan=0.)
    groups["the five values on the edge to the closest tag"] = (
        [standing(edge[:, j]) for j in range(edge.shape[1])] + [np.isnan(d["edge"][:, 0]).astype(float)])
    m = d["gold"].size
    parent_size = np.bincount(d["parent"])[d["parent"]]
    groups["what the chunk is (kind, length, records, where in its parent)"] = (
        [(d["kind"] == k).astype(float) for k in range(KINDS)]
        + [np.log(d["length"]), np.array([len(r) for r in d["records"]], dtype=float),
           d["spot"] / np.maximum(parent_size - 1, 1), np.log(parent_size), (d["spot"] == 0).astype(float)])
    plain = sum(standing(near[k]) for k in ("tags_max", "description", "question"))
    before, after = neighbours(d)
    among = d["among"].astype(np.float64).copy()
    np.fill_diagonal(among, -np.inf)
    nearest = np.argsort(-among, axis=1)[:, :5]
    groups["the chunks around it (its neighbours in the parent, its five nearest by description, its parent)"] = [
        np.where(before >= 0, plain[np.maximum(before, 0)], np.median(plain)),
        np.where(after >= 0, plain[np.maximum(after, 0)], np.median(plain)),
        plain[nearest].mean(axis=1), plain[nearest].max(axis=1), standing(hub(d)),
        np.array([plain[d["parent"] == p].max() for p in d["parent"]]),
        np.array([plain[d["parent"] == p].mean() for p in d["parent"]]),
        np.array([np.sort(plain[d["parent"] == p])[::-1][:3].mean() for p in d["parent"]]),
    ]
    return {name: np.column_stack(cols) for name, cols in groups.items()}, plain


ids = list(Q)
built = {qid: features(Q[qid]) for qid in ids}
product = {qid: int(Q[qid]["parent"].min()) for qid in ids}       # parents are numbered by name, a product's lie together
# the product of a question: read off the smallest parent number is not safe across products; use the chunk set
product = {qid: int(Q[qid]["chunks"].min()) for qid in ids}
names = sorted(set(product.values()))
fold_of = {name: k % 5 for k, name in enumerate(names)}
order_of_groups = list(next(iter(built.values()))[0])


def run(group_names, model):
    firsts, places, recalls = 0, [], []
    for fold in range(5):
        train = [q for q in ids if fold_of[product[q]] != fold]
        test = [q for q in ids if fold_of[product[q]] == fold]
        X = np.vstack([np.hstack([built[q][0][g] for g in group_names]) for q in train])
        y = np.concatenate([Q[q]["gold"] for q in train]).astype(int)
        if model == "linear":
            clf = LogisticRegression(C=1.0, max_iter=2000, class_weight="balanced")
        else:
            clf = HistGradientBoostingClassifier(max_depth=3, max_iter=150, learning_rate=0.06,
                                                 class_weight="balanced", random_state=0)
        clf.fit(X, y)
        for q in test:
            score = clf.predict_proba(np.hstack([built[q][0][g] for g in group_names]))[:, 1]
            first, place, recall = measure(score, Q[q])
            firsts += int(first)
            places.append(place)
            recalls.append(recall)
    places = np.array(places)
    return firsts, int((places <= 3).sum()), int((places <= 5).sum()), float(np.median(places)), float(np.mean(recalls))


print("held out by product (five folds). first chunk gold (of 100) | first gold within 3 | within 5 | place of the "
      "first gold, the middle | context_recall_id")
plain_rows = [measure(built[q][1], Q[q]) for q in ids]
print(f"  {sum(r[0] for r in plain_rows):3d} | {sum(r[1] <= 3 for r in plain_rows):3d} | "
      f"{sum(r[1] <= 5 for r in plain_rows):3d} | {np.median([r[1] for r in plain_rows]):.0f} | "
      f"{np.mean([r[2] for r in plain_rows]):.3f}  the plain order, nothing fitted")
for model in ("linear", "trees"):
    taken = []
    for name in order_of_groups:
        taken.append(name)
        got = run(taken, model)
        print(f"  {got[0]:3d} | {got[1]:3d} | {got[2]:3d} | {got[3]:.0f} | {got[4]:.3f}  {model}: + {name}")
    for name in order_of_groups[1:]:
        got = run([name], model)
        print(f"  {got[0]:3d} | {got[1]:3d} | {got[2]:3d} | {got[3]:.0f} | {got[4]:.3f}  {model}: only {name}")

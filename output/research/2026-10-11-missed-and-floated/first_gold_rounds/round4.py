"""Round 4: on the questions whose first chunk (plain order) is not gold, set that chunk beside the first
gold chunk of the same order, reading by reading: on how many questions does the reading put the
gold one above the wrong one. A reading that knows nothing gives half."""
import numpy as np

from explore import load, standing

data = load()
Q = data["questions"]
FACETS = data["facets"]


def hub(d):
    among = d["among"].astype(np.float64).copy()
    np.fill_diagonal(among, np.nan)
    return np.nanmean(among, axis=1)


def readings(d):
    plain = standing(d["tags"]) + standing(d["description"]) + standing(d["question"])
    among = d["among"].astype(np.float64).copy()
    np.fill_diagonal(among, -np.inf)
    nearest = np.argsort(-among, axis=1)[:, :5]
    parent_size = np.bincount(d["parent"])[d["parent"]]
    at = {(int(p), int(s)): k for k, (p, s) in enumerate(zip(d["parent"], d["spot"]))}
    around = np.array([max([plain[at[(int(p), int(s) + step)]] for step in (-1, 1) if (int(p), int(s) + step) in at]
                           or [np.nan]) for p, s in zip(d["parent"], d["spot"])])
    out = {
        "tags, the closest query tag": d["tags"], "tags, the mean over the query tags": d["fit"].mean(axis=0),
        "tags, the worst query tag": d["fit"].min(axis=0),
        "query tags against the description, mean": d["tags_description"].mean(axis=0),
        "query tags against the description, closest": d["tags_description"].max(axis=0),
        "description": d["description"], "question": d["question"], "question without the name": d["question_bare"],
        "question against the chunk's tags": d["question_tags"],
        "query description against the chunk's tags": d["description_tags"],
        "closest record": d["record_best"], "records on average": d["record_mean"], "the question's words (BM25)": d["words"],
        "kind part of tags": d["kind_tags"], "kind part of description": d["kind_description"],
        "kind part of question": d["kind_question"],
        "specific part of description": d["description"] - d["kind_description"],
        "specific part of question": d["question"] - d["kind_question"],
        "how near the chunk is to every chunk": hub(d),
        "the plain value of its five nearest chunks, mean": plain[nearest].mean(axis=1),
        "the plain value of its best neighbour in the parent": around,
        "the best plain value in its parent": np.array([plain[d["parent"] == p].max() for p in d["parent"]]),
        "the mean plain value in its parent": np.array([plain[d["parent"] == p].mean() for p in d["parent"]]),
        "length": d["length"].astype(float), "records in it": np.array([len(r) for r in d["records"]], dtype=float),
        "chunks in its parent": parent_size.astype(float), "how far into its parent": d["spot"] / np.maximum(parent_size - 1, 1),
    }
    for j, facet in enumerate(FACETS):
        out[f"edge value: {facet}"] = d["edge"][:, j]
    return out, plain


wins, ties, count = {}, {}, 0
gaps, places_gold = [], []
same_parent = same_kind = 0
for d in Q.values():
    values, plain = readings(d)
    order = np.lexsort((d["id_rank"], -plain))
    if d["gold"][order[0]]:
        continue
    count += 1
    top = int(order[0])
    first_gold = int(order[np.argmax(d["gold"][order])])
    places_gold.append(int(np.argmax(d["gold"][order])) + 1)
    gaps.append(float(plain[top] - plain[first_gold]))
    same_parent += int(d["parent"][top] == d["parent"][first_gold])
    same_kind += int(d["kind"][top] == d["kind"][first_gold])
    for name, v in values.items():
        a, b = v[first_gold], v[top]
        if np.isnan(a) or np.isnan(b):
            continue
        wins[name] = wins.get(name, 0) + int(a > b)
        ties[name] = ties.get(name, 0) + int(a == b)
print(f"{count} questions whose first chunk is not gold; the first gold chunk stands at place {np.median(places_gold):.0f} "
      f"({np.percentile(places_gold, 25):.0f}-{np.percentile(places_gold, 75):.0f}); the wrong first chunk and the first "
      f"gold chunk are in the same parent on {same_parent}, of the same kind on {same_kind}; the plain value between "
      f"them: {np.median(gaps):.2f} ({np.percentile(gaps, 25):.2f}-{np.percentile(gaps, 75):.2f}) in units of one route's spread")
print("== the reading puts the first gold chunk above the wrong first chunk on how many of those questions (equal on) ==")
for name in sorted(wins, key=lambda k: -wins[k]):
    print(f"  {wins[name]:3d} ({ties[name]})  {name}")

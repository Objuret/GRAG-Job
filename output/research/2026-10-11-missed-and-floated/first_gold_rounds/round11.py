"""Round 11: the two lists of query tags (the first from the described content, the second from the
prompt itself), each alone; and the model-written description beside the raw question."""
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
sizes = [(d["first_list"], d["fit"].shape[0] - d["first_list"]) for d in Q.values()]
print(f"query tags a question: from the described content {np.median([a for a, _ in sizes]):.0f}, from the prompt "
      f"{np.median([b for _, b in sizes]):.0f}; questions with no second list: {sum(1 for _, b in sizes if b == 0)}")


def part(key, which, how):
    def make(d):
        rows = d[key][:d["first_list"]] if which == 1 else d[key][d["first_list"]:]
        if rows.shape[0] == 0:
            rows = d[key]
        return rows.mean(axis=0) if how == "mean" else rows.max(axis=0)
    return make


tries = {}
for key, label in (("fit", "against the chunk's closest tag"), ("tags_description", "against the chunk's description (query both sides)")):
    for which, name in ((1, "tags from the described content"), (2, "tags from the prompt")):
        for how in ("mean", "max"):
            tries[f"{name}, {label}, {'their mean' if how == 'mean' else 'the closest of them'}"] = part(key, which, how)
tries["the raw question without the name against descriptions (own pairing)"] = lambda d: d["bare_to_passage"]
tries["the raw question with the name against descriptions (own pairing)"] = lambda d: d["question_to_passage"]
tries["the model-written description against descriptions (as a query against passage)"] = lambda d: d["description_query_to_passage"]
tries["the model-written description against descriptions (passage both sides)"] = lambda d: d["description_passage_to_passage"]
tries["the model-written description against descriptions (query both sides)"] = lambda d: d["description"]
report(tries, data)

"""Round 12: after the name, is there more in the question that every chunk of the border shares? The
direction all the border's descriptions share (their middle) taken out of the QUESTION's vector
only, whole and in part; and the same for the question with the name still in."""
import pickle
from pathlib import Path

import numpy as np

from explore import load, report, standing

HERE = Path(__file__).resolve().parent
data = load()
Q = data["questions"]
with open(HERE / "first_gold_signals_more__gold100.pkl", "rb") as handle:
    extra = pickle.load(handle)
for qid, d in Q.items():
    d.update(extra[qid])
with open(HERE / "what_a_chunk_holds.pkl", "rb") as handle:
    CHUNK_IDS = pickle.load(handle)["chunk_ids"]
KEPT = Path(r"C:\Coding\exjobbet\GRAG-Job\output\embed_local\20261007_rev113abe4acafa_float32")
side = np.load(KEPT / "descriptions_passage.npz", allow_pickle=True)
desc_at = {str(c): k for k, c in enumerate(side["ids"])}
matrix = np.asarray(side["matrix"], dtype=np.float64)
matrix = matrix / np.linalg.norm(matrix, axis=1, keepdims=True)
whole_middle = matrix.mean(axis=0)
for d in Q.values():
    d["passage_rows"] = matrix[[desc_at[str(CHUNK_IDS[c])] for c in d["chunks"].tolist()]]


def out_of(vector_key, share, which="border"):
    def make(d):
        rows = d["passage_rows"]
        middle = rows.mean(axis=0) if which == "border" else whole_middle
        middle = middle / np.linalg.norm(middle)
        v = d[vector_key].astype(np.float64)
        v = v - share * (v @ middle) * middle
        return rows @ (v / np.linalg.norm(v))
    return make


tries = {
    "question without the name (own pairing), as it is": out_of("bare_vector", 0.),
    "the border's shared direction taken out of it": out_of("bare_vector", 1.),
    "half of it taken out": out_of("bare_vector", 0.5),
    "the whole pool's shared direction taken out of it": out_of("bare_vector", 1., "pool"),
    "question with the name (own pairing), as it is": out_of("question_vector", 0.),
    "the border's shared direction taken out of the question with the name": out_of("question_vector", 1.),
    "the whole pool's shared direction taken out of the question with the name": out_of("question_vector", 1., "pool"),
}
report(tries, data, sort=False)

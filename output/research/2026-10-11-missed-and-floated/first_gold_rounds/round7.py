"""Round 7: how solid is "the question without the product's name, in the embedder's own pairing"?
Paired counts against the same reading with the name, and against the plain order; the reading
with what all the questions share taken off; routes taken in turn."""
import pickle
from pathlib import Path

import numpy as np

from explore import load, measure, report, standing

data = load()
Q = data["questions"]
with open(Path(__file__).resolve().parent / "first_gold_signals_more__gold100.pkl", "rb") as handle:
    MORE = pickle.load(handle)
for qid, d in Q.items():
    d.update(MORE[qid])
ids = list(Q)


def K(key):
    return lambda d: d[key]


def add(*fs):
    return lambda d: sum(standing(f(d)) for f in fs)


def firsts(make):
    return np.array([measure(make(Q[q]), Q[q])[0] for q in ids])


def paired(a_name, a, b_name, b):
    x, y = firsts(a), firsts(b)
    print(f"  {a_name}: {int(x.sum())} | {b_name}: {int(y.sum())} | gold first with the first and not the second on "
          f"{int((x & ~y).sum())}, the other way on {int((~x & y).sum())}")


plain = add(K("tags"), K("description"), K("question"))
print("== paired, first chunk gold ==")
paired("question without the name, own pairing", K("bare_to_passage"), "question with the name, own pairing", K("question_to_passage"))
paired("question without the name, query both sides", K("question_bare"), "question with the name, query both sides", K("question"))
paired("question without the name, own pairing", K("bare_to_passage"), "the plain order", plain)
paired("question without the name, own pairing", K("bare_to_passage"), "question without the name, query both sides", K("question_bare"))

# by product, to see that it is not a few products
by_product = {}
for q in ids:
    key = int(Q[q]["chunks"].min())
    by_product.setdefault(key, []).append(q)
gain = [sum(measure(Q[q]["bare_to_passage"], Q[q])[0] for q in qs) - sum(measure(Q[q]["question_to_passage"], Q[q])[0] for q in qs)
        for qs in by_product.values()]
print(f"  by product (30): the reading without the name is ahead in {sum(g > 0 for g in gain)}, behind in "
      f"{sum(g < 0 for g in gain)}, level in {sum(g == 0 for g in gain)}")

# what all questions share, taken off the question vector (the middle of the other 99 questions' vectors)
bare_vectors = np.array([Q[q]["bare_vector"].astype(np.float64) for q in ids])
question_vectors = np.array([Q[q]["question_vector"].astype(np.float64) for q in ids])
at = {q: k for k, q in enumerate(ids)}
with open(Path(__file__).resolve().parent / "what_a_chunk_holds.pkl", "rb") as handle:
    CHUNK_IDS = pickle.load(handle)["chunk_ids"]


def less_the_shared(vectors, share):
    def make(d, vectors=vectors, share=share):
        k = at[d["_id"]]
        others = np.delete(vectors, k, axis=0).mean(axis=0)
        v = vectors[k] - share * others
        v = v / np.linalg.norm(v)
        rows = d["passage_rows"]
        return rows @ v
    return make


# passage description vectors of the product's chunks are needed for that; rebuild them from among_passage is not
# possible, so read them from the side file once
KEPT = Path(r"C:\Coding\exjobbet\GRAG-Job\output\embed_local\20261007_rev113abe4acafa_float32")
side = np.load(KEPT / "descriptions_passage.npz", allow_pickle=True)
desc_at = {str(c): k for k, c in enumerate(side["ids"])}
matrix = np.asarray(side["matrix"], dtype=np.float64)
matrix = matrix / np.linalg.norm(matrix, axis=1, keepdims=True)
for q in ids:
    d = Q[q]
    d["_id"] = q
    d["passage_rows"] = matrix[[desc_at[str(CHUNK_IDS[c])] for c in d["chunks"].tolist()]]
check = max(float(np.abs(Q[q]["passage_rows"] @ Q[q]["bare_vector"].astype(np.float64) - Q[q]["bare_to_passage"]).max()) for q in ids)
print(f"\n(check: the passage rows give back the stored reading to within {check:.5f})")


def in_turn(*fs):
    def make(d):
        orders = [np.lexsort((d["id_rank"], -np.asarray(f(d), dtype=np.float64))).tolist() for f in fs]
        seen, out = set(), []
        for step in range(d["gold"].size):
            for order in orders:
                k = order[step]
                if k not in seen:
                    seen.add(k)
                    out.append(k)
        score = np.zeros(d["gold"].size)
        score[np.array(out)] = -np.arange(len(out), dtype=np.float64)
        return score
    return make


def lead(first, rest):
    """The first route's best chunk first, then the other order."""
    def make(d):
        score = np.asarray(rest(d), dtype=np.float64).copy()
        top = int(np.lexsort((d["id_rank"], -np.asarray(first(d), dtype=np.float64)))[0])
        score[top] = score.max() + 1.
        return score
    return make


tags_mean = lambda d: d["fit"].mean(axis=0)
with_words = add(K("tags"), K("description"), K("question"), K("record_best"), K("words"))
tries = {
    "question without the name, own pairing": K("bare_to_passage"),
    "the same, less the middle of the other questions' vectors": less_the_shared(bare_vectors, 1.0),
    "the same, less half of it": less_the_shared(bare_vectors, 0.5),
    "question with the name, own pairing, less the middle of the other questions' vectors": less_the_shared(question_vectors, 1.0),
    "the plain order": plain,
    "in turn: question without the name (own pairing), tags' mean": in_turn(K("bare_to_passage"), tags_mean),
    "in turn: question without the name (own pairing), tags' mean, query description": in_turn(K("bare_to_passage"), tags_mean, K("description")),
    "in turn: question without the name (own pairing), the plain order": in_turn(K("bare_to_passage"), plain),
    "question without the name (own pairing) names the first chunk, then the plain order": lead(K("bare_to_passage"), plain),
    "question without the name (own pairing) names the first chunk, then plain + record + words": lead(K("bare_to_passage"), with_words),
    "plain with the question route swapped for it": add(K("tags"), K("description"), K("bare_to_passage")),
    "tags' mean + description + it": add(tags_mean, K("description"), K("bare_to_passage")),
    "it counted twice + tags' mean + description": lambda d: 2 * standing(d["bare_to_passage"]) + standing(tags_mean(d)) + standing(d["description"]),
    "it counted three times + tags' mean + description": lambda d: 3 * standing(d["bare_to_passage"]) + standing(tags_mean(d)) + standing(d["description"]),
    "it + tags' mean": add(K("bare_to_passage"), tags_mean),
    "it + words on the chunk text": add(K("bare_to_passage"), K("words")),
    "it + closest record": add(K("bare_to_passage"), K("record_best")),
    "it + words + closest record": add(K("bare_to_passage"), K("words"), K("record_best")),
}
print("\n== orders ==")
report(tries, data, sort=False)

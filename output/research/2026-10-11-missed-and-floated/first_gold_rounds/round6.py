"""Round 6: the embedder's own pairing (question behind "query: " against descriptions and tags behind
"passage: "), the old arm's pairing (passage against passage), and the question's words against
the layer's own text."""
import pickle
from pathlib import Path

import numpy as np

from explore import load, report, standing

data = load()
Q = data["questions"]
with open(Path(__file__).resolve().parent / "first_gold_signals_more__gold100.pkl", "rb") as handle:
    MORE = pickle.load(handle)
for qid, d in Q.items():
    d.update(MORE[qid])


def K(key):
    return lambda d: d[key]


def add(*fs):
    return lambda d: sum(standing(f(d)) for f in fs)


singles = {
    "query mode both sides: question": K("question"),
    "query mode both sides: question without the name": K("question_bare"),
    "query mode both sides: query description": K("description"),
    "query mode both sides: tags, closest": K("tags"),
    "query mode both sides: tags, mean": lambda d: d["fit"].mean(axis=0),
    "own pairing: question (query) against descriptions (passage)": K("question_to_passage"),
    "own pairing: question without the name (query) against descriptions (passage)": K("bare_to_passage"),
    "own pairing: query description (query) against descriptions (passage)": K("description_query_to_passage"),
    "passage both sides: query description against descriptions": K("description_passage_to_passage"),
    "passage both sides: tags, closest": K("tags_passage_closest"),
    "passage both sides: tags, mean": K("tags_passage_mean"),
    "passage both sides: query tags against descriptions, mean": lambda d: d["tags_passage_to_description"].mean(axis=0),
    "own pairing: question (query) against the chunk's tags (passage)": K("question_to_tags_passage"),
    "own pairing: question without the name against the chunk's tags (passage)": K("bare_to_tags_passage"),
    "the question's words on the description text": K("words_on_description"),
    "the question's words on the tags' names": K("words_on_tags"),
    "the question's words on description and tags": K("words_on_both"),
    "the question's words on the chunk text": K("words"),
}
print("== single readings ==")
report(singles, data)

S = singles
joins = {
    "plain, query mode (closest tag + description + question)": add(K("tags"), K("description"), K("question")),
    "the old arm's vectors: tags closest (passage) + description (passage) + question (own pairing)":
        add(K("tags_passage_closest"), K("description_passage_to_passage"), K("question_to_passage")),
    "the same with the tags' mean": add(K("tags_passage_mean"), K("description_passage_to_passage"), K("question_to_passage")),
    "the same with the tags' mean and the question without the name":
        add(K("tags_passage_mean"), K("description_passage_to_passage"), K("bare_to_passage")),
    "tags' mean (passage) + question without the name (own pairing)": add(K("tags_passage_mean"), K("bare_to_passage")),
    "tags' mean (query) + question without the name (own pairing)": add(S["query mode both sides: tags, mean"], K("bare_to_passage")),
    "question without the name (own pairing) + question without the name (query mode)": add(K("bare_to_passage"), K("question_bare")),
    "both questions without the name + both tags' means": add(K("bare_to_passage"), K("question_bare"), K("tags_passage_mean"),
                                                             S["query mode both sides: tags, mean"]),
    "both questions without the name + both tags' means + words on description and tags":
        add(K("bare_to_passage"), K("question_bare"), K("tags_passage_mean"), S["query mode both sides: tags, mean"],
            K("words_on_both")),
    "the same + words on the chunk text + closest record":
        add(K("bare_to_passage"), K("question_bare"), K("tags_passage_mean"), S["query mode both sides: tags, mean"],
            K("words_on_both"), K("words"), K("record_best")),
    "plain + words on description and tags": add(K("tags"), K("description"), K("question"), K("words_on_both")),
    "question without the name (own pairing) + words on description and tags": add(K("bare_to_passage"), K("words_on_both")),
}
print("\n== joined ==")
report(joins, data)

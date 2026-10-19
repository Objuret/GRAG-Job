"""Round 1: every single reading, and plain sums of them."""
import numpy as np

from explore import load, report, standing

data = load()


def S(key):
    return lambda d: d[key]


def hub(d):
    """How near a chunk's description is to the product's other chunks on average."""
    among = d["among"].astype(np.float64).copy()
    np.fill_diagonal(among, np.nan)
    return np.nanmean(among, axis=1)


def centred(vector_key):
    def make(d):
        rows = d["chunk_vectors"].astype(np.float64)
        middle = rows.mean(axis=0)
        off = rows - middle
        off /= np.linalg.norm(off, axis=1, keepdims=True)
        left = d[vector_key].astype(np.float64) - middle
        return off @ (left / np.linalg.norm(left))
    return make


singles = {
    "tags": S("tags"),
    "description": S("description"),
    "question": S("question"),
    "question against the chunk's tags": S("question_tags"),
    "query description against the chunk's tags": S("description_tags"),
    "query tags against the chunk's description, the closest": lambda d: d["tags_description"].max(axis=0),
    "query tags against the chunk's description, the mean": lambda d: d["tags_description"].mean(axis=0),
    "the mean over the query tags of the chunk's closest tag": lambda d: d["fit"].mean(axis=0),
    "question without the product's name": S("question_bare"),
    "question without the name against the chunk's tags": S("question_bare_tags"),
    "the chunk's closest record": S("record_best"),
    "the chunk's records on average": S("record_mean"),
    "the question's words (BM25)": S("words"),
    "kind part of tags": S("kind_tags"),
    "kind part of description": S("kind_description"),
    "kind part of question": S("kind_question"),
    "description, the product's middle taken off": centred("description_vector"),
    "question, the product's middle taken off": centred("question_vector"),
    "question without the name, the product's middle taken off": centred("bare_vector"),
    "description less how near the chunk is to every chunk": lambda d: standing(d["description"]) - standing(hub(d)),
    "question less how near the chunk is to every chunk": lambda d: standing(d["question"]) - standing(hub(d)),
    "how near the chunk is to every chunk (no question at all)": hub,
}
print("== single readings ==")
report(singles, data)


def plus(*keys):
    return lambda d: sum(standing(singles[k](d)) for k in keys)


sums = {
    "tags + description + question (the plain order)": plus("tags", "description", "question"),
    "tags + description + question without the name": plus("tags", "description", "question without the product's name"),
    "tags + description + both questions": plus("tags", "description", "question", "question without the product's name"),
    "plain + closest record": plus("tags", "description", "question", "the chunk's closest record"),
    "plain + words": plus("tags", "description", "question", "the question's words (BM25)"),
    "plain + closest record + words": plus("tags", "description", "question", "the chunk's closest record",
                                           "the question's words (BM25)"),
    "plain + query tags against description (closest)": plus("tags", "description", "question",
                                                           "query tags against the chunk's description, the closest"),
    "plain + query tags against description (mean)": plus("tags", "description", "question",
                                                        "query tags against the chunk's description, the mean"),
    "plain + question against tags": plus("tags", "description", "question", "question against the chunk's tags"),
    "plain + description against tags": plus("tags", "description", "question",
                                             "query description against the chunk's tags"),
    "plain + mean over query tags": plus("tags", "description", "question",
                                         "the mean over the query tags of the chunk's closest tag"),
    "plain, the two text routes with the product's middle taken off": plus(
        "tags", "description, the product's middle taken off", "question, the product's middle taken off"),
    "plain less how near the chunk is to every chunk": lambda d: plus("tags", "description", "question")(d)
    - standing(hub(d)),
    "plain less twice that": lambda d: plus("tags", "description", "question")(d) - 2 * standing(hub(d)),
    "all the direct readings": plus("tags", "description", "question", "question against the chunk's tags",
                                    "query description against the chunk's tags",
                                    "query tags against the chunk's description, the closest",
                                    "the chunk's closest record", "the question's words (BM25)"),
    "description + question": plus("description", "question"),
    "tags + question": plus("tags", "question"),
    "tags + description": plus("tags", "description"),
    "question + closest record + words (nothing from the first call)": plus(
        "question", "the chunk's closest record", "the question's words (BM25)"),
    "question + question against tags + record + words (nothing from the first call)": plus(
        "question", "question against the chunk's tags", "the chunk's closest record", "the question's words (BM25)"),
}
print("\n== sums of standings ==")
report(sums, data)

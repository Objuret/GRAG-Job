"""Round 2: how the query tags are put together (closest, mean, each on its own scale), and how routes
are joined (sum of standings, places, the worst place)."""
import numpy as np

from explore import load, places, report, standing

data = load()


def rows_standing(rows):
    rows = np.asarray(rows, dtype=np.float64)
    mid = np.median(rows, axis=1, keepdims=True)
    spread = 1.4826 * np.median(np.abs(rows - mid), axis=1, keepdims=True)
    return np.where(spread > 0, (rows - mid) / np.where(spread > 0, spread, 1.), 0.)


family = {}
for label, key in (("chunk's closest tag", "fit"), ("chunk's description", "tags_description")):
    family[f"query tags against the {label}: the closest of them"] = lambda d, key=key: d[key].max(axis=0)
    family[f"query tags against the {label}: their mean"] = lambda d, key=key: d[key].mean(axis=0)
    family[f"query tags against the {label}: their middle"] = lambda d, key=key: np.median(d[key], axis=0)
    family[f"query tags against the {label}: the worst of them"] = lambda d, key=key: d[key].min(axis=0)
    family[f"query tags against the {label}: each on its own scale, added"] = (
        lambda d, key=key: rows_standing(d[key]).sum(axis=0))
    family[f"query tags against the {label}: each on its own scale, the middle"] = (
        lambda d, key=key: np.median(rows_standing(d[key]), axis=0))
    family[f"query tags against the {label}: each as a place, the places added"] = (
        lambda d, key=key: -np.sum([places(r, d) for r in d[key]], axis=0).astype(np.float64))
    family[f"query tags against the {label}: each as a place, 1/(60+place) added"] = (
        lambda d, key=key: np.sum([1. / (60. + places(r, d)) for r in d[key]], axis=0))
print("== the query tags put together ==")
report(family, data)

T = family["query tags against the chunk's closest tag: their mean"]
TD = family["query tags against the chunk's description: their mean"]
TS = family["query tags against the chunk's closest tag: each on its own scale, added"]
TDS = family["query tags against the chunk's description: each on its own scale, added"]


def st(f):
    return lambda d: standing(f(d))


def K(key):
    return lambda d: d[key]


def add(*fs):
    return lambda d: sum(standing(f(d)) for f in fs)


def by_places(*fs):
    return lambda d: -np.sum([places(f(d), d) for f in fs], axis=0).astype(np.float64)


def worst_place(*fs):
    return lambda d: -np.max([places(f(d), d) for f in fs], axis=0).astype(np.float64)


def reciprocal(*fs):
    return lambda d: np.sum([1. / (60. + places(f(d), d)) for f in fs], axis=0)


joins = {
    "plain (closest tag + description + question)": add(K("tags"), K("description"), K("question")),
    "tags' mean + description + question": add(T, K("description"), K("question")),
    "tags' mean + description + question without the name": add(T, K("description"), K("question_bare")),
    "tags' mean + query tags against description (mean) + description + question without the name":
        add(T, TD, K("description"), K("question_bare")),
    "tags' mean + query tags against description (mean) + question without the name": add(T, TD, K("question_bare")),
    "tags' mean + query tags against description (mean)": add(T, TD),
    "tags' mean + question without the name": add(T, K("question_bare")),
    "query tags against description (mean) + question without the name": add(TD, K("question_bare")),
    "the four + closest record + words": add(T, TD, K("description"), K("question_bare"), K("record_best"), K("words")),
    "tags' mean + query tags against description (mean) + question without the name + record + words":
        add(T, TD, K("question_bare"), K("record_best"), K("words")),
    "tags on own scales + description + question without the name": add(TS, K("description"), K("question_bare")),
    "both tag readings on own scales + description + question without the name":
        add(TS, TDS, K("description"), K("question_bare")),
    "by places: tags' mean, query tags against description, description, question without the name":
        by_places(T, TD, K("description"), K("question_bare")),
    "by the worst place of those four": worst_place(T, TD, K("description"), K("question_bare")),
    "by the worst place of tags' mean, description, question without the name":
        worst_place(T, K("description"), K("question_bare")),
    "1/(60+place) of those four": reciprocal(T, TD, K("description"), K("question_bare")),
    "by the worst place of the plain three": worst_place(K("tags"), K("description"), K("question")),
    "1/(60+place) of the plain three": reciprocal(K("tags"), K("description"), K("question")),
}
print("\n== routes joined ==")
report(joins, data)

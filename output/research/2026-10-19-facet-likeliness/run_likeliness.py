"""His 2026-10-19 "Test using that number as its likeliness to be the correct similarity chunk so to
speak.." · "The embedded is a model, isn't it?": the similarity read as a likeliness, the facet as
odds on it, relative to the other chunks. A test, no model call (run with --flag
HERB_V4_OFFLINE=on); the arm is not changed, its places are replaced from outside, in this process.

Per chunk of the border: its closest edge to any query tag (the tags side's carrying edge) and that
query tag; its likeliness is the graph's own similarity of that edge's tag to the query tag,
(1 + cosine) / 2, between 0 and 1. Where the first call said the query tag's named facet matters,
the facet net's score of that same edge in that facet, less the mean of the border's chunks'
scores in that facet (each chunk's carrying edge), is its log-odds against the others (the net was
fitted so that score differences are the judge's log-odds). A chunk's standing is the log of its
likeliness plus those log-odds: the likeliness times the facet's odds. Its place is its rank by that.

FACET_TEST_FACETS=off  the control: the same, every named facet taken as not mattering
FACET_TEST_MODE=slot   the places go where the tags side's places go today (inside the steps)
FACET_TEST_MODE=above  besides that, the rest of the clouds after the chosen chunks is ordered by
                       the places instead of by the 4-combo's strength

Writes per question to <out>/likeliness.jsonl: the border's size, how many chunks changed place
against closeness alone, and the spread (interquartile range) of the log-likeliness and of the
facet log-odds over the border.

    FACET_TEST_MODE=slot .venv/Scripts/python.exe output/research/2026-10-19-facet-likeliness/run_likeliness.py \
        --arm artefact_v4 --set gold --char-budget 72000 --workers 6 --retrieval-only \
        --flag HERB_V4_OFFLINE=on --out output/k=chars/<folder>
"""
import json
import os
import sys
import threading
from pathlib import Path

import numpy as np
from scipy.stats import rankdata

ROOT = Path(__file__).resolve().parents[3]
for p in (ROOT / 'prod', ROOT / 'test'):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from artefact import v4_walk as WK  # noqa: E402

MODE = os.environ.get('FACET_TEST_MODE', 'slot')
if MODE not in ('slot', 'above'):
    raise SystemExit('FACET_TEST_MODE must be slot or above')
# FACET_TEST_FACETS=off: the control, every named facet taken as not mattering (likeliness alone)
FACETS_ON = os.environ.get('FACET_TEST_FACETS', 'on') == 'on'
_LOCAL = threading.local()
_LOCK = threading.Lock()
_OUT = None


def _iqr(x):
    x = np.asarray(x, dtype=np.float64)
    return float(np.percentile(x, 75) - np.percentile(x, 25)) if x.size else None


def likeliness_places(layer, cosines, facet_of, inside):
    rows = np.asarray(cosines, dtype=np.float64)
    facet_of = np.asarray(facet_of, dtype=np.int64)
    if not FACETS_ON:
        facet_of = np.full(facet_of.shape, -1, dtype=np.int64)
    inside = np.asarray(inside, dtype=np.int64)
    n = layer['chunks']
    tag_e, chunk_e, values = layer['edge_tag'], layer['edge_chunk'], layer['raw'][:, 1:]
    on_edge = rows[:, tag_e]
    best_q = on_edge.argmax(axis=0)
    near, edge = WK.best_edges(on_edge.max(axis=0), chunk_e, n)
    q_of = np.where(edge >= 0, best_q[np.maximum(edge, 0)], -1)
    near_in, edge_in, q_in = near[inside], edge[inside], q_of[inside]
    has = edge_in >= 0
    likeliness = np.where(has, (1. + np.nan_to_num(near_in, nan=-1.)) / 2., 0.)
    log_like = np.log(np.maximum(likeliness, 1e-12))
    odds = np.zeros(inside.size)
    for f in range(values.shape[1]):
        mean_f = float(values[edge_in[has], f].mean()) if has.any() else 0.
        mine = has & (q_in >= 0) & (facet_of[np.maximum(q_in, 0)] == f)
        odds[mine] = values[edge_in[mine], f] - mean_f
    standing = log_like + odds
    ids = layer['id_rank'][inside]
    place = np.full(n, np.inf)
    plain = np.full(n, np.inf)
    place[inside[np.lexsort((ids, -standing))]] = np.arange(1, inside.size + 1)
    plain[inside[np.lexsort((ids, -log_like))]] = np.arange(1, inside.size + 1)
    closeness_rank = np.full(n, np.nan)
    facet_rank = np.full(n, np.nan)
    closeness_rank[inside] = rankdata(-log_like, method='average')
    facet_rank[inside] = rankdata(-odds, method='average')
    _LOCAL.place = place
    _LOCAL.record = {'border': int(inside.size),
                     'changed': int((place[inside] != plain[inside]).sum()),
                     'log_likeliness_iqr': _iqr(log_like[has]),
                     'facet_log_odds_iqr': _iqr(odds[has & (odds != 0)])}
    return {'place': place, 'query_tag': q_of, 'edge': edge, 'closeness_rank': closeness_rank,
            'facet_rank': facet_rank, 'place_by_closeness': plain}


_order = WK.storyline_order


def storyline_order_above(combo_order, start, strength, region):
    """The chosen chunks first, then the rest of the clouds by the places, then the rest."""
    place = _LOCAL.place
    chosen = set(int(i) for i in start)
    inside = set(int(i) for i in region)
    at = {int(i): p for p, i in enumerate(combo_order)}
    first = [int(i) for i in combo_order if int(i) in chosen]
    cloud = sorted((int(i) for i in combo_order if int(i) in inside and int(i) not in chosen),
                   key=lambda i: (place[i], at[i]))
    rest = [int(i) for i in combo_order if int(i) not in inside and int(i) not in chosen]
    return first + cloud + rest


WK.facet_relative_places = likeliness_places
if MODE == 'above':
    WK.storyline_order = storyline_order_above

from arms import artefact_v4 as V  # noqa: E402

_answer = V.answer_one_question


def answer_one_question(question, *a, **k):
    out = _answer(question, *a, **k)
    with _LOCK:
        with open(_OUT, 'a', encoding='utf-8') as fh:
            fh.write(json.dumps({'id': question[0], 'mode': MODE, 'facets': FACETS_ON,
                                 **_LOCAL.record}) + '\n')
    return out


V.answer_one_question = answer_one_question
import run  # noqa: E402

if __name__ == '__main__':
    out_dir = sys.argv[sys.argv.index('--out') + 1]
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    _OUT = str(Path(out_dir) / 'likeliness.jsonl')
    run.main()

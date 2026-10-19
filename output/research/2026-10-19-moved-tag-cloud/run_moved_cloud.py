"""His 2026-10-19 "or what if we just move the fucking tags and let that be the new tagcloud that is
checked for overlap with the cluster?" (after "ok, what if we just moved something 1 step per
thing?"): the facets move the tags side's order before its cloud is cut; the tag cloud is taken
from the moved order, as many chunks as the bend of the tags side's closeness gives; the chosen
chunks are where that cloud meets the description side's cloud. A test, no model call (run with
--flag HERB_V4_OFFLINE=on); the arm is not changed, its steps are replaced from outside, in this
process only.

The tags side per chunk: its closest edge to any query tag and that query tag; its likeliness is
the graph's own similarity of that edge's tag to the query tag, (1 + cosine) / 2. The facet of a
chunk is the named facet of that query tag, where the first call said it matters.

MOVE_FORM=odds  the order by the log of the likeliness plus the facet net's score of the same edge
                in that facet, less the border's mean in that facet (the likeliness times the
                facet's odds against the others)
MOVE_FORM=step  "1 step per thing": the order by likeliness, then one step per neighbour: where
                every facet that matters for either of two neighbours ranks the lower one above
                the upper one (the net's scores on their own edges, facet by facet), they swap;
                pairs that would share a chunk are taken from the top down (the agent's choice),
                so a chunk moves one place at most
FACETS=off      the control: no facet matters, the order and the cloud by likeliness alone

Writes per question to <out>/moved.jsonl: the tag cloud's size, how many of its chunks the moves
changed against the cloud by closeness, and how many chosen chunks there are.

    MOVE_FORM=odds .venv/Scripts/python.exe output/research/2026-10-19-moved-tag-cloud/run_moved_cloud.py \
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

FORM = os.environ.get('MOVE_FORM', 'odds')
FACETS_ON = os.environ.get('FACETS', 'on') == 'on'
if FORM not in ('odds', 'step'):
    raise SystemExit('MOVE_FORM must be odds or step')
_LOCAL = threading.local()
_LOCK = threading.Lock()
_OUT = None


def moved_places(layer, cosines, facet_of, inside):
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
    e_in, q_in = edge[inside], q_of[inside]
    has = e_in >= 0
    log_like = np.where(has, np.log(np.maximum((1. + np.nan_to_num(near[inside], nan=-1.)) / 2., 1e-12)),
                        -np.inf)
    facet = np.where(has & (q_in >= 0), facet_of[np.maximum(q_in, 0)], -1)
    ids = layer['id_rank'][inside]
    plain = np.lexsort((ids, -log_like))
    if FORM == 'odds':
        odds = np.zeros(inside.size)
        for f in range(values.shape[1]):
            mean_f = float(values[e_in[has], f].mean()) if has.any() else 0.
            mine = facet == f
            odds[mine] = values[e_in[mine], f] - mean_f
        order = np.lexsort((ids, -(log_like + odds)))
    else:
        order = plain.copy()
        used = np.zeros(order.size, dtype=bool)
        for k in range(order.size - 1):
            a, b = order[k], order[k + 1]
            if used[k] or not (has[a] and has[b]):
                continue
            applies = {f for f in (facet[a], facet[b]) if f >= 0}
            if applies and all(values[e_in[b], f] > values[e_in[a], f] for f in applies):
                order[k], order[k + 1] = b, a
                used[k] = used[k + 1] = True
    place = np.full(n, np.inf)
    place[inside[order]] = np.arange(1, inside.size + 1)
    plain_place = np.full(n, np.inf)
    plain_place[inside[plain]] = np.arange(1, inside.size + 1)
    _LOCAL.place, _LOCAL.plain = place, plain_place
    rank = np.full(n, np.nan)
    rank[inside] = rankdata(-log_like, method='average')
    return {'place': place, 'query_tag': q_of, 'edge': edge, 'closeness_rank': rank,
            'facet_rank': place.copy(), 'place_by_closeness': plain_place}


def cloud_combo_moved(layer, cosines, d_near, inside, scope_of, tags_place=None):
    """`v4_walk.cloud_combo` with the tags side's cloud taken from the moved order: as many chunks
    as the bend of the tags side's closeness gives, the first of the moved order."""
    n = layer['chunks']
    d_near = np.asarray(d_near, dtype=np.float64)
    inside = np.asarray(inside, dtype=np.int64)
    scope_of = np.asarray(scope_of, dtype=np.int64)
    rows = np.asarray(cosines, dtype=np.float64)
    t_near, t_edge = WK.tags_nearness(layer, rows)
    place = np.asarray(tags_place, dtype=np.float64)
    query_tag = np.where(t_edge >= 0, rows[:, layer['edge_tag']].argmax(axis=0)[np.maximum(t_edge, 0)], -1)
    level = {name: np.zeros(n, dtype=np.int64) for name in ('tags', 'description')}
    lv_t, _ = WK.levels_of(t_near[inside])
    k = int((lv_t >= 1).sum())
    level['tags'][inside] = 2
    level['tags'][inside[np.argsort(place[inside], kind='stable')[:k]]] = 1
    lv_d, _ = WK.levels_of(d_near[inside])
    level['description'][inside] = np.where(lv_d >= 1, 1, 2)
    rank = {'tags': np.full(n, np.nan), 'description': np.full(n, np.nan)}
    rank['tags'][inside] = rankdata(place[inside], method='average')
    rank['description'][inside] = rankdata(-d_near[inside], method='average')
    middle = np.full(n, np.nan)
    middle[inside] = (rank['tags'][inside] + rank['description'][inside]) / 2.
    step = np.zeros(n, dtype=np.int64)
    step[inside] = level['tags'][inside] + level['description'][inside]
    lowest = int(step[inside].min())
    gauged_from = inside[step[inside] <= max(3, lowest)]
    hits = np.zeros(n, dtype=bool)
    hits[gauged_from] = True
    taken = WK.majority_scopes(hits[inside], scope_of[inside])
    in_scope = np.zeros(n, dtype=bool)
    in_scope[inside] = np.isin(scope_of[inside], taken)
    by = np.lexsort((layer['id_rank'][inside], middle[inside], ~in_scope[inside], step[inside]))
    steps, counts = np.unique(step[inside], return_counts=True)
    plain_cloud = set(inside[lv_t >= 1].tolist())
    moved_cloud = set(inside[level['tags'][inside] == 1].tolist())
    _LOCAL.record = {'tag_cloud': k, 'tag_cloud_changed': len(moved_cloud - plain_cloud),
                     'chosen': int((step[inside] == lowest).sum())}
    record = {'chunks': int(inside.size),
              'clouds': {name: int((level[name][inside] == 1).sum()) for name in level},
              'chunks_on_each_step': {int(s): int(c) for s, c in zip(steps, counts)},
              'scope_gauged_from_chunks': int(gauged_from.size),
              'scopes_taken': taken, 'chunks_in_scope': int(in_scope.sum())}
    return {'order': inside[by].tolist(), 'tags_nearness': t_near, 'description_nearness': d_near,
            'edge': t_edge, 'query_tag': query_tag, 'level': level, 'step': step,
            'in_scope': in_scope, 'rank': rank, 'middle_rank': middle, 'record': record}


WK.facet_relative_places = moved_places
WK.cloud_combo = cloud_combo_moved

from arms import artefact_v4 as V  # noqa: E402

_answer = V.answer_one_question


def answer_one_question(question, *a, **k):
    out = _answer(question, *a, **k)
    with _LOCK:
        with open(_OUT, 'a', encoding='utf-8') as fh:
            fh.write(json.dumps({'id': question[0], 'form': FORM, 'facets': FACETS_ON,
                                 **_LOCAL.record}) + '\n')
    return out


V.answer_one_question = answer_one_question
import run  # noqa: E402

if __name__ == '__main__':
    out_dir = sys.argv[sys.argv.index('--out') + 1]
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    _OUT = str(Path(out_dir) / 'moved.jsonl')
    run.main()

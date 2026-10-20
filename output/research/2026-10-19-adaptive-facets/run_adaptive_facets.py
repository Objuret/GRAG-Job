"""The facets read relative to the tag, acting where the arm reads the tags side: who is in the tag
cloud (his 2026-10-19 "ok, but can we make them adaptive easily deterministically?", "well do that
then", "if you realize you built it wrong, fucking dont do that then and fix it", "find the actual
relationship to what gets added and what gets lost with the facets ... and thus be able to maybe do
it adaptive", "ok, do that and run a smoke?"; earlier the same day "they are the RELEVANCE MODIFIER
OF THE TAGS TO THE CHUNKS", "if its withing the fucking range, that facet is concidered the "same"",
"what if we just moved something 1 step per thing?").

A test, no model call for the order (the first call's answers come from the cache); the arm is not
changed, two of its steps are replaced from outside, in this process only.

The arm's own order stays as it is with the facets off: the tags side's places by closeness alone
(`facet_relative_places` with no facet), and the tag cloud the chunks before the knee of their
closest tag's closeness (`levels_of` over `tags_nearness`), so the facets-off run is the arm's
facets-off run.

Where the first call names a facet that matters for the query tag that gives a chunk its closeness:
1. The chunk's edge to its closest tag gets a standing in that facet, read only against the same
   graph tag's other edges on chunks of the same kind inside the border (the tag's own level and the
   kind, which the structure gives, stay out): above them when it beats more of them than it loses
   to, below when it loses more, the same otherwise (one edge beats another when its value is higher
   by more than the facet's range stored on the FacetLayer node, the net's 24 refits; within it a
   half). A tag with no other chunk of that kind in the border: the same.
2. An edge whose graph tag is the query tag's own phrase (the same words) never stands below (the
   chunks the facets pushed out held gold most often when their tag was the query tag itself).
3. The chunk moves one level of its closeness nearer when its edge stands above, one level farther
   when below; the levels are those of `levels_of`, everything beyond the knee one level after the
   last. The tag cloud keeps the size the knee gives and takes the chunks first by moved level, then
   by closeness: the facets decide who is in it at its edge.
The rest is the arm's: the description cloud, the steps, the scope, the middle rank (by the closeness
places), the 4-combo and the hand-over.

FACETS=off  the control: no standing read; the arm's own order.

Writes per question to <out>/adaptive.jsonl: the tag cloud's size, chunks moved nearer and farther,
own-phrase edges kept from standing below, tag-cloud chunks changed against the arm's, chosen chunks.
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

FACETS_ON = os.environ.get('FACETS', 'on') == 'on'
_LOCAL = threading.local()
_LOCK = threading.Lock()
_OUT = None
_GAPS = None
_places = WK.facet_relative_places


def _gaps():
    """The facets' ranges from the FacetLayer node, read once."""
    global _GAPS
    if _GAPS is None:
        from graph.db import _driver
        d = _driver()
        try:
            with d.session(database='herb-eval-volmax', default_access_mode='READ') as s:
                row = s.run('MATCH (l:FacetLayer {run_id: $run}) RETURN l.equal_gap AS g, '
                            'l.equal_gap_facets AS f', run='pilot_full_herb').single()
        finally:
            d.close()
        if list(row['f']) != list(WK.RANKING_FACETS):
            raise SystemExit('The ranges are stored for other facets')
        _GAPS = np.asarray(row['g'], dtype=np.float64)
    return _GAPS


def wins(value, gap=0.):
    """Per item its wins over the others: the higher value wins when higher by more than gap, within
    it a half. Counted by sorting, not by pairs."""
    v = np.sort(value)
    below = np.searchsorted(v, value - gap, side='left')
    within = np.searchsorted(v, value + gap, side='right') - below
    return below + .5 * (within - 1)


def standings(values, groups, gap):
    """Per item +1 when it beats more of the other items of its group than it loses to, -1 when it
    loses more, 0 otherwise or alone."""
    out = np.zeros(values.size)
    order = np.argsort(groups, kind='stable')
    cuts = np.flatnonzero(np.diff(groups[order])) + 1
    for members in np.split(order, cuts):
        if members.size > 1:
            out[members] = np.sign(wins(values[members], gap) - (members.size - 1) / 2.)
    return out


def _norm(text):
    return ' '.join(str(text).lower().split())


def closeness_places(layer, cosines, facet_of, inside):
    """The arm's places by closeness alone; the named facets kept for the cloud step."""
    _LOCAL.facet_of = np.asarray(facet_of, dtype=np.int64) if FACETS_ON \
        else np.full(len(facet_of), -1, dtype=np.int64)
    return _places(layer, cosines, np.full(len(facet_of), -1, dtype=np.int64), inside)


def tag_cloud(layer, rows, t_near, t_edge, query_tag, inside):
    """The tag cloud: the arm's (the chunks before the knee), or with the facets the same number of
    chunks taken by level moved one by the standing, then closeness."""
    n = layer['chunks']
    lv, count = WK.levels_of(t_near[inside])
    base = inside[lv >= 1]
    record = {'tag_cloud': int(base.size), 'moved_nearer': 0, 'moved_farther': 0,
              'own_phrase_kept_from_below': 0, 'tag_cloud_changed': 0}
    facet_of = _LOCAL.facet_of
    if count == 0 or (facet_of < 0).all():
        return set(base.tolist()), record
    tag_e, chunk_e, raw, kind = layer['edge_tag'], layer['edge_chunk'], layer['raw'], layer['kind']
    in_border = np.zeros(n, dtype=bool)
    in_border[inside] = True
    keep = np.flatnonzero(in_border[chunk_e])
    tag_kind = tag_e[keep].astype(np.int64) * (int(kind.max()) + 1) + kind[chunk_e[keep]]
    gaps = _gaps()
    stand_of = {}
    for f in np.unique(facet_of[facet_of >= 0]):
        s = standings(raw[keep, 1 + f], tag_kind, gaps[f])
        stand_of[int(f)] = dict(zip(keep.tolist(), s.tolist()))
    level = np.where(lv >= 1, lv, count + 1).astype(np.float64)
    moved = level.copy()
    for j, c in enumerate(inside.tolist()):
        e, q = int(t_edge[c]), int(query_tag[c])
        if e < 0 or q < 0 or facet_of[q] < 0:
            continue
        s = stand_of[int(facet_of[q])].get(e, 0.)
        if s < 0 and _norm(_LOCAL.graph_tags[int(tag_e[e])]) == _norm(_LOCAL.phrases[q]):
            s = 0.
            record['own_phrase_kept_from_below'] += 1
        moved[j] = min(max(level[j] - s, 1.), count + 1.)
        record['moved_nearer'] += int(moved[j] < level[j])
        record['moved_farther'] += int(moved[j] > level[j])
    by = np.lexsort((layer['id_rank'][inside], -t_near[inside], moved))
    cloud = set(inside[by[:base.size]].tolist())
    record['tag_cloud_changed'] = len(cloud - set(base.tolist()))
    return cloud, record


def cloud_combo_edge(layer, cosines, d_near, inside, scope_of, tags_place=None):
    """`v4_walk.cloud_combo` with the tag cloud from `tag_cloud`; everything else as the arm's."""
    n = layer['chunks']
    d_near = np.asarray(d_near, dtype=np.float64)
    inside = np.asarray(inside, dtype=np.int64)
    scope_of = np.asarray(scope_of, dtype=np.int64)
    rows = np.asarray(cosines, dtype=np.float64)
    t_near, t_edge = WK.tags_nearness(layer, rows)
    tags_place = np.asarray(tags_place, dtype=np.float64)
    query_tag = np.where(t_edge >= 0, rows[:, layer['edge_tag']].argmax(axis=0)[np.maximum(t_edge, 0)], -1)
    level = {name: np.zeros(n, dtype=np.int64) for name in ('tags', 'description')}
    cloud, record_cloud = tag_cloud(layer, rows, t_near, t_edge, query_tag, inside)
    level['tags'][inside] = 2
    level['tags'][np.array(sorted(cloud), dtype=np.int64)] = 1
    lv_d, _ = WK.levels_of(d_near[inside])
    level['description'][inside] = np.where(lv_d >= 1, 1, 2)
    rank = {'tags': np.full(n, np.nan), 'description': np.full(n, np.nan)}
    rank['tags'][inside] = rankdata(tags_place[inside], method='average')
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
    _LOCAL.record = {**record_cloud, 'chosen': int((step[inside] == lowest).sum())}
    record = {'chunks': int(inside.size),
              'clouds': {name: int((level[name][inside] == 1).sum()) for name in level},
              'chunks_on_each_step': {int(s): int(c) for s, c in zip(steps, counts)},
              'scope_gauged_from_chunks': int(gauged_from.size),
              'scopes_taken': taken, 'chunks_in_scope': int(in_scope.sum())}
    return {'order': inside[by].tolist(), 'tags_nearness': t_near, 'description_nearness': d_near,
            'edge': t_edge, 'query_tag': query_tag, 'level': level, 'step': step,
            'in_scope': in_scope, 'rank': rank, 'middle_rank': middle, 'record': record}


WK.facet_relative_places = closeness_places
WK.cloud_combo = cloud_combo_edge

from arms import artefact_v4 as V  # noqa: E402

_answer = V.answer_one_question
_interpret = V._interpret
_ask = V._ask_graph


def interpret_kept(*a, **k):
    """The first call's answer, its query tags' phrases kept for this question."""
    out = _interpret(*a, **k)
    query = out[0]
    _LOCAL.phrases = [t.text for t in (*query.tags, *query.query_tags)]
    return out


def ask_kept(*a, **k):
    """The graph's answer, its graph tags' names kept for this question."""
    asked = _ask(*a, **k)
    _LOCAL.graph_tags = asked.graph_tags
    return asked


def answer_one_question(question, *a, **k):
    out = _answer(question, *a, **k)
    with _LOCK:
        with open(_OUT, 'a', encoding='utf-8') as fh:
            fh.write(json.dumps({'id': question[0], 'facets': FACETS_ON, **_LOCAL.record}) + '\n')
    return out


V._interpret = interpret_kept
V._ask_graph = ask_kept
V.answer_one_question = answer_one_question
import run  # noqa: E402

if __name__ == '__main__':
    out_dir = sys.argv[sys.argv.index('--out') + 1]
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    _OUT = str(Path(out_dir) / 'adaptive.jsonl')
    run.main()

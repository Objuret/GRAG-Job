"""The facets read relative to the tag (his 2026-10-19 "ok, but can we make them adaptive easily
deterministically?", "well do that then"; earlier the same day "they are the RELEVANCE MODIFIER OF
THE TAGS TO THE CHUNKS", "if its withing the fucking range, that facet is concidered the "same"",
"they all have to be included in the calculation").

A test, no model call (run with --flag HERB_V4_OFFLINE=on); the arm is not changed, its tags side is
replaced from outside, in this process only.

Per query tag: its closeness to the border's graph tags falls into levels where its list bends
(`levels_of`); the graph tags in a level are its picked tags, and their edges to the border's chunks
are its items. The base order of an item: its tag's closeness level, then the edge's topic level
(the topic values of the query tag's items cut where they bend), then the closeness; the same base
as the Elo test.

Where the first call names a facet that matters for the query tag:
1. Each item's standing in the facet is read only against the same graph tag's other edges on chunks
   of the same kind inside the border (the tag's own level and the kind, which the structure gives,
   stay out): above them when it beats more of them than it loses to, below when it loses more, the
   same otherwise (one edge beats another when its value is higher by more than the facet's range
   stored on the FacetLayer node, the net's 24 refits; within it a half). A tag with no other chunk
   of that kind in the border: the same. Only above / same / below counts, so how many chunks a tag
   is on does not.
2. The items of one closeness level (the clustering's equal range: equally close to the query tag)
   play every pair twice: topic (the higher topic level wins, the same level a half) and the facet
   (the higher standing wins, the same a half). An item's score is its wins over both games, every
   pair counted at once (in a round robin played to the end the order is the order of the scores,
   Zermelo 1929 / Bradley-Terry). The level's items take the places the level already holds in the
   base, ordered by score, ties by the base: a nearer level stays ahead of a farther one, and no
   other query tag's items move.
3. An item whose graph tag is the query tag's own phrase (the same words) may rise in its level but
   never falls below its place in the base (his 2026-10-19 "ok, do that and run a smoke?" on: the
   chunks the facets push out hold gold most often when their tag is the query tag itself).
A chunk's place on the tags side is its best item's place; the tag cloud is the first chunks of that
order, as many as the bend of the tags side's closeness gives; it meets the description cloud as now.
(First built with the facet only between the edges of one graph tag; the arm reads the tags side
only through who is in the tag cloud, and that cut falls between tags, so it could not act.)

FACETS=off  the control: the same base, no game played.

Writes per question to <out>/adaptive.jsonl: items, closeness levels where the facet plays, items in
them, items moved, tag-cloud chunks changed against the base, chosen chunks.
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
DUMP = os.environ.get('DUMP', 'off') == 'on'   # every edge of a query tag with a facet, for a check outside
_LOCAL = threading.local()
_LOCK = threading.Lock()
_OUT = None
_GAPS = None


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


def _levels(x):
    """Each value's level where its list bends, nearest 1; the values in no level last."""
    lv, count = WK.levels_of(x)
    return np.where(lv >= 1, lv, count + 1)


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


def _is_own_phrase(q, tag):
    """Whether graph tag `tag` is query tag `q`'s own phrase (the same words)."""
    return _norm(_LOCAL.graph_tags[int(tag)]) == _norm(_LOCAL.phrases[int(q)])


def floor_order(by_score, by_base, own):
    """The order by score, except that an item of `own` never stands below its place in the
    base: at each place, an own item whose base place it is goes there unless already placed."""
    due = {slot: int(k) for slot, k in enumerate(by_base) if int(k) in own}
    out, used = [], set()
    rest = iter(int(k) for k in by_score)
    for slot in range(len(by_score)):
        k = due.get(slot)
        if k is None or k in used:
            k = next(i for i in rest if i not in used)
        out.append(k)
        used.add(k)
    return out


def adaptive_places(layer, cosines, facet_of, inside):
    rows = np.asarray(cosines, dtype=np.float64)
    facet_of = np.asarray(facet_of, dtype=np.int64)
    if not FACETS_ON:
        facet_of = np.full(facet_of.shape, -1, dtype=np.int64)
    inside = np.asarray(inside, dtype=np.int64)
    gaps = _gaps()
    n = layer['chunks']
    in_border = np.zeros(n, dtype=bool)
    in_border[inside] = True
    tag_e, chunk_e, raw, kind = layer['edge_tag'], layer['edge_chunk'], layer['raw'], layer['kind']
    keep = in_border[chunk_e]
    tags_here = np.unique(tag_e[keep])
    items = []          # (query tag, edge, closeness level, topic level, closeness)
    for q in range(rows.shape[0]):
        close = rows[q, tags_here]
        lv, count = WK.levels_of(close)
        if count == 0:
            continue
        level_of_tag = dict(zip(tags_here.tolist(), lv.tolist()))
        mine = np.flatnonzero(keep & np.array([level_of_tag.get(int(t), 0) >= 1 for t in tag_e]))
        if not mine.size:
            continue
        c_level = np.array([level_of_tag[int(t)] for t in tag_e[mine]])
        t_level = _levels(raw[mine, 0]) if mine.size >= 3 else np.ones(mine.size, dtype=np.int64)
        for e, cl, tl in zip(mine.tolist(), c_level.tolist(), t_level.tolist()):
            items.append((q, e, cl, tl, float(rows[q, tag_e[e]])))
    place = np.full(n, np.inf)
    plain = np.full(n, np.inf)
    q_of = np.full(n, -1, dtype=np.int64)
    edge_of = np.full(n, -1, dtype=np.int64)
    groups = in_groups = moved = own_items = floored = 0
    _LOCAL.dump = [] if not DUMP else [
        (int(q), int(tag_e[e]), int(kind[chunk_e[e]]), layer['chunk_ids'][int(chunk_e[e])], int(facet_of[q]),
         [float(x) for x in raw[e, 1:]], int(cl), int(tl))
        for q, e, cl, tl, _c in items if facet_of[q] >= 0]
    level_chunks = []
    if items:
        arr = np.array([(cl, tl, -c) for _, _, cl, tl, c in items], dtype=np.float64)
        base = np.lexsort((arr[:, 2], arr[:, 1], arr[:, 0]))       # the base list
        pos = np.empty(len(items))
        pos[base] = np.arange(1, len(items) + 1)
        new = pos.copy()
        q_item = np.array([it[0] for it in items])
        e_item = np.array([it[1] for it in items])
        c_item = np.array([it[2] for it in items])
        t_item = np.array([it[3] for it in items], dtype=np.float64)
        for q in np.unique(q_item):
            if facet_of[q] < 0:
                continue
            mine = np.flatnonzero(q_item == q)
            e = e_item[mine]
            # the standing against the same graph tag's other edges on chunks of the same kind
            tag_kind = tag_e[e].astype(np.int64) * (int(kind.max()) + 1) + kind[chunk_e[e]]
            stand = standings(raw[e, 1 + facet_of[q]], tag_kind, gaps[facet_of[q]])
            for lv in np.unique(c_item[mine]):
                at = np.flatnonzero(c_item[mine] == lv)
                if at.size < 2:
                    continue
                m = mine[at]
                score = wins(-t_item[m]) + wins(stand[at])
                by_score = m[np.lexsort((pos[m], -score))]
                # an edge whose graph tag is the query tag's own phrase may rise, never fall
                own = {int(k) for k in m if _is_own_phrase(q, tag_e[e_item[k]])}
                by_base = m[np.argsort(pos[m])]
                floored += sum(1 for slot, k in enumerate(by_score) if int(k) in own
                               and slot > int(np.flatnonzero(by_base == k)[0]))
                by_score = np.array(floor_order(by_score, by_base, own))
                own_items += len(own)
                new[by_score] = np.sort(pos[m])
                groups += 1
                in_groups += m.size
                level_chunks.append(chunk_e[e_item[m]])
        moved = int((new != pos).sum())
        for k, (q, e, *_rest) in enumerate(items):
            c = int(chunk_e[e])
            if new[k] < place[c]:
                place[c], q_of[c], edge_of[c] = new[k], q, e
            plain[c] = min(plain[c], pos[k])
    # chunks no picked tag reaches stand after every reached chunk, by their closest tag
    far = inside[~np.isfinite(place[inside])]
    if far.size:
        near, edge = WK.tags_nearness(layer, rows)
        order = far[np.lexsort((layer['id_rank'][far], -near[far]))]
        top = np.nanmax(np.where(np.isfinite(place), place, np.nan)) if np.isfinite(place).any() else 0.
        top_plain = np.nanmax(np.where(np.isfinite(plain), plain, np.nan)) if np.isfinite(plain).any() else 0.
        place[order] = top + np.arange(1, far.size + 1)
        plain[order] = top_plain + np.arange(1, far.size + 1)
        edge_of[far] = edge[far]
    _LOCAL.place, _LOCAL.plain, _LOCAL.level_chunks = place, plain, level_chunks
    _LOCAL.record = {'items': len(items), 'groups': groups, 'items_in_groups': in_groups,
                     'items_moved': moved, 'own_phrase_items_in_groups': own_items,
                     'own_phrase_items_held_up': floored}
    return {'place': place, 'query_tag': q_of, 'edge': edge_of,
            'closeness_rank': rankdata(plain, method='average'), 'facet_rank': place.copy(),
            'place_by_closeness': plain}


def cloud_combo_moved(layer, cosines, d_near, inside, scope_of, tags_place=None):
    """`v4_walk.cloud_combo` with the tags side's cloud taken from the moved order (as in the Elo test)."""
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
    base_cloud = set(inside[np.argsort(_LOCAL.plain[inside], kind='stable')[:k]].tolist())
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
    cloud = set(inside[level['tags'][inside] == 1].tolist())
    # the closeness levels where the facet plays whose chunks the base cloud's edge cuts through
    split = sum(1 for g in _LOCAL.level_chunks if 0 < len(set(g.tolist()) & base_cloud) < len(set(g.tolist())))
    _LOCAL.record.update({'levels_cut_by_the_cloud_edge': split,
                          'tag_cloud': k, 'tag_cloud_changed': len(cloud - base_cloud),
                          'chosen': int((step[inside] == lowest).sum())})
    record = {'chunks': int(inside.size),
              'clouds': {name: int((level[name][inside] == 1).sum()) for name in level},
              'chunks_on_each_step': {int(s): int(c) for s, c in zip(steps, counts)},
              'scope_gauged_from_chunks': int(gauged_from.size),
              'scopes_taken': taken, 'chunks_in_scope': int(in_scope.sum())}
    return {'order': inside[by].tolist(), 'tags_nearness': t_near, 'description_nearness': d_near,
            'edge': t_edge, 'query_tag': query_tag, 'level': level, 'step': step,
            'in_scope': in_scope, 'rank': rank, 'middle_rank': middle, 'record': record}


WK.facet_relative_places = adaptive_places
WK.cloud_combo = cloud_combo_moved

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


V._interpret = interpret_kept
V._ask_graph = ask_kept


def answer_one_question(question, *a, **k):
    out = _answer(question, *a, **k)
    with _LOCK:
        with open(_OUT, 'a', encoding='utf-8') as fh:
            fh.write(json.dumps({'id': question[0], 'facets': FACETS_ON, **_LOCAL.record}) + '\n')
        if DUMP:
            with open(Path(_OUT).with_name('dump.jsonl'), 'a', encoding='utf-8') as fh:
                fh.write(json.dumps({'id': question[0], 'rows': _LOCAL.dump}) + '\n')
    return out


V.answer_one_question = answer_one_question
import run  # noqa: E402

if __name__ == '__main__':
    out_dir = sys.argv[sys.argv.index('--out') + 1]
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    _OUT = str(Path(out_dir) / 'adaptive.jsonl')
    run.main()

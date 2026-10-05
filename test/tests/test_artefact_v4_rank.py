"""artefact_v4's adjust_lower and multirank on toy arrays, and on one cached querytagger answer.

No live graph, no model call; the cached answer is read without its question.
"""
import json

import numpy as np
import pytest

from harness import chat
from harness.contract import BuildStats, ModelUsage
from arms import artefact_v4 as V
from artefact import query_content as Q
from artefact import v4_rank as R4
from artefact import v4_multikey as MK

# Graph tags ProductX (a product name), a, b, c; chunks c0..c4, c4 carrying no edge at all.
TAGS = ('ProductX', 'a', 'b', 'c')
CHUNKS = ('c0', 'c1', 'c2', 'c3', 'c4')
EDGE_TAG = np.array([0, 1, 1, 2, 3])          # (P,c3) (a,c0) (a,c1) (b,c1) (c,c2)
EDGE_CHUNK = np.array([3, 0, 1, 1, 2])
TOPIC = np.array([.5, .4, .3, .2, .6])
POS = np.array([[0., 0., .25, .5, 1.],
                [.25, .25, 0., 1., .75],
                [.5, .5, .5, .25, 0.],
                [.75, 1., 1., .75, .5],
                [1., .75, .75, 0., .25]])
SCORE = POS * 4.                               # a stored score column, any monotone scale
ELIGIBLE = np.array([False, True, True, True])
DD = np.array([.1, .2, .3, .4, .5])
DQ = np.array([.5, .5, .5, .5, .5])


def layer(gap=1.):
    return R4.build_layer(POS, SCORE, TOPIC, gap)


def prepared():
    return V.Prepared(
        chunk_rows=tuple({'chunkId': c} for c in CHUNKS), chunk_ids=CHUNKS,
        chunk_kinds=('pr',) * 5, graph_tags=TAGS, product_tags=('ProductX',),
        nonscope_eligible=ELIGIBLE, tag_vectors=np.eye(4), chunk_vectors=np.eye(5),
        edge_tag=EDGE_TAG, edge_chunk=EDGE_CHUNK, edge_topic=TOPIC, edge_pos=POS,
        landings=(), driver=None, cache_dir=None, provenance={},
        build_stats=BuildStats(0., ModelUsage(), []), rank_layer=layer(),
        multikey_layer=MK.build_layer(SCORE[:, 1:], (1., 1., 1., 1.), {}, {}),
        structure=MK.build_structure(
            {'ptr': np.zeros(len(CHUNKS) + 1, dtype=np.int64), 'members': np.zeros(0)},
            {'chunk_group_ptr': np.zeros(len(CHUNKS) + 1, dtype=np.int64),
             'chunk_groups': np.zeros(0), 'product': np.zeros(len(CHUNKS))}))


def lower_scores(query_tags, **kw):
    return R4.adjust_lower_scores(EDGE_TAG, EDGE_CHUNK, TOPIC, layer().pct, ELIGIBLE,
                                  query_tags, len(CHUNKS), **kw)


def multirank(query_tags, area=None):
    return R4.multirank_order(CHUNKS, EDGE_TAG, EDGE_CHUNK, TOPIC, layer(), ELIGIBLE,
                              query_tags, DD, DQ, area)


# --- the stored layer -------------------------------------------------------

def test_percentile_columns_are_never_zero_and_reach_one():
    pct = layer().pct
    n = len(TOPIC)
    assert pct.min() == pytest.approx(1 / n) and pct.min() > 0
    assert pct.max() == pytest.approx(1.)
    # the stored (r - 1) / (n - 1) read back as r / n
    assert R4.percentile_from_positions(np.array([0., .5, 1.]), 5).tolist() == pytest.approx(
        [.2, .6, 1.])


def test_the_stored_file_percentiles_follow_the_scores_in_range_and_the_gap_reads_one():
    path = V.LEARNED_DIR / 'scores.jsonl'
    if not path.exists() or not V.BANDS_FILE.exists():
        pytest.skip('round1 layer not on this machine')
    raw, pos = [], []
    with path.open(encoding='utf-8') as stream:
        for line in stream:
            row = json.loads(line)
            raw.append([row[f] for f in R4.ADJUST_FACETS])
            pos.append([row[f + '_pos'] for f in R4.ADJUST_FACETS])
    raw, pos = np.asarray(raw), np.asarray(pos)
    n = len(raw)
    pct = R4.percentile_from_positions(pos, n)
    assert pct.min() == pytest.approx(1 / n) and (pct > 0).all() and pct.max() <= 1.
    sample = np.arange(0, n, 97)
    for j in range(len(R4.ADJUST_FACETS)):
        order = sample[np.argsort(raw[sample, j], kind='stable')]
        assert (np.diff(raw[order, j]) >= 0).all()
        assert (np.diff(pct[order, j]) >= 0).all()      # a higher score, a higher percentile
        top, bottom = int(np.argmax(raw[:, j])), int(np.argmin(raw[:, j]))
        assert pct[top, j] == pytest.approx(1.) and pct[bottom, j] == pytest.approx(1 / n)
    gap, source = R4.read_flip_gap(V.BANDS_FILE)
    assert gap == 1.0 and source['row'] == 'pooled' and source['column'] == 'gap (same chunk)'


def test_facet_levels_step_by_the_gap_below_the_column_top():
    lv = layer(gap=1.).facet_levels
    # temporal column scores 0,1,2,4,3 -> levels 4,3,2,0,1
    assert lv[:, 0].tolist() == [4, 3, 2, 0, 1]
    assert layer(gap=4.).facet_levels[:, 0].tolist() == [1, 0, 0, 0, 0]


# --- adjust_lower -----------------------------------------------------------

FIT = np.array([.9, .5, .8, .7])


def test_q_f_zero_leaves_topic_unchanged():
    score, _, _ = lower_scores([(FIT, (.7, 0., 0., 0., 0.))])
    plain = np.zeros(len(CHUNKS))
    for e in np.flatnonzero(ELIGIBLE[EDGE_TAG]):
        plain[EDGE_CHUNK[e]] += FIT[EDGE_TAG[e]] * TOPIC[e]
    assert score.tolist() == pytest.approx(plain.tolist())
    off, _, _ = lower_scores([(FIT, (.7, 1., 1., 1., 1.))], facets_on=False)
    assert off.tolist() == pytest.approx(plain.tolist())


def test_the_facet_factor_is_the_weighted_geometric_mean_of_the_percentiles():
    pct = layer().pct
    even, _, _ = lower_scores([(FIT, (0., 1., 1., 1., 1.))])
    scaled, _, _ = lower_scores([(FIT, (0., .2, .2, .2, .2))])
    # c2 has one edge (tag c, edge 4); the readings' size does not matter, only their shares
    assert even[2] == pytest.approx(.7 * .6 * float(np.prod(pct[4])) ** .25)
    assert scaled[2] == pytest.approx(even[2])
    one, _, _ = lower_scores([(FIT, (0., 0., 1., 0., 0.))])
    assert one[2] == pytest.approx(.7 * .6 * pct[4, 1])
    factor = even[2] / (.7 * .6)
    assert pct[4].min() <= factor <= pct[4].max()


def test_qtopic_exp_raises_topic_to_the_topic_reading_and_a_zero_reading_leaves_it():
    off, _, _ = lower_scores([(FIT, (.5, 0., 0., 0., 0.))], qtopic='off')
    exp, _, _ = lower_scores([(FIT, (.5, 0., 0., 0., 0.))], qtopic='exp')
    zero, _, _ = lower_scores([(FIT, (0., 0., 0., 0., 0.))], qtopic='exp')
    assert off[2] == pytest.approx(.7 * .6)
    assert exp[2] == pytest.approx(.7 * .6 ** .5)
    assert zero[2] == pytest.approx(.7 * .6)


def test_edgecomb_max_takes_the_best_graph_tag_per_query_tag():
    total, _, _ = lower_scores([(FIT, (0.,) * 5)], edgecomb='sum')
    best, _, _ = lower_scores([(FIT, (0.,) * 5)], edgecomb='max')
    # c1 has edges (a, .3) and (b, .2): sum .5*.3 + .8*.2, max .8*.2
    assert total[1] == pytest.approx(.5 * .3 + .8 * .2)
    assert best[1] == pytest.approx(max(.5 * .3, .8 * .2))
    assert best[3] == 0. and best[4] == 0.


def test_edgecomb_best_is_the_single_largest_term_and_cuts_no_chunk():
    other = np.array([.2, -.3, .95, .1])
    rows = [(FIT, (0., 1., 0., 1., 0.)), (other, (0., 0., 1., 0., 1.))]
    best, reached, _ = lower_scores(rows, edgecomb='best')
    summed, reached_sum, _ = lower_scores(rows, edgecomb='sum')
    pct = layer().pct
    terms = {}
    for fit, readings in rows:
        w = np.asarray(readings)[1:]
        for e in np.flatnonzero(ELIGIBLE[EDGE_TAG]):
            factor = float(np.prod(pct[e] ** (w / w.sum())))
            terms.setdefault(int(EDGE_CHUNK[e]), []).append(fit[EDGE_TAG[e]] * TOPIC[e] * factor)
    assert sorted(terms) == [0, 1, 2]
    for c, values in terms.items():
        assert best[c] == pytest.approx(max(values))
        assert summed[c] == pytest.approx(sum(values))
    # c3 carries only the product-name edge, c4 no edge: unreached under both, never dropped
    assert reached.tolist() == reached_sum.tolist() == [True, True, True, False, False]
    assert best[3] == 0. and best[4] == 0.
    for descjoin in R4.DESCJOIN_MODES:
        order = R4.adjust_lower_order(CHUNKS, best, reached, DD, DQ, descjoin=descjoin)['order']
        assert sorted(order) == list(range(len(CHUNKS)))
        assert set(order[:3]) == {0, 1, 2}


def test_a_negative_fit_lowers_is_counted_and_no_chunk_is_cut_under_either_mode():
    bad = (np.array([-.9, -.8, -.7, -.6]), (0., 1., 1., 1., 1.))
    score, reached, stats = lower_scores([bad])
    # c3 carries only the product-name edge, c4 no edge and no rank row at all
    assert reached.tolist() == [True, True, True, False, False]
    assert (score[:3] < 0).all() and stats['reached_chunks_with_negative_score'] == 3
    assert stats['edge_terms_negative'] == 4
    for descjoin in R4.DESCJOIN_MODES:
        order = R4.adjust_lower_order(CHUNKS, score, reached, DD, DQ, descjoin=descjoin)['order']
        assert sorted(order) == list(range(len(CHUNKS)))
        assert set(order[:3]) == {0, 1, 2}          # reached, negative, still before unreached
    out = multirank([bad])
    assert sorted(out['order']) == list(range(len(CHUNKS)))
    assert set(out['order'][:3]) == {0, 1, 2} and not out['reached'][3] and not out['reached'][4]


def test_no_chunk_is_cut_by_landing_and_landing_acts_only_on_an_exact_tie():
    score = np.array([.5, .5, .9, .1, .1])
    reached = np.ones(5, dtype=bool)
    area = np.array([1, 0, 1, 1, 0])           # c1 and c4 in the meet
    order = R4.adjust_lower_order(CHUNKS, score, reached, np.zeros(5), np.zeros(5), area,
                                  descjoin='key')['order']
    assert [CHUNKS[i] for i in order] == ['c2', 'c1', 'c0', 'c4', 'c3']
    close = np.array([.5, .5 - 1e-9, .9, .1, .1])  # no longer a tie: the score decides
    order = R4.adjust_lower_order(CHUNKS, close, reached, np.zeros(5), np.zeros(5), area,
                                  descjoin='key')['order']
    assert [CHUNKS[i] for i in order][:3] == ['c2', 'c0', 'c1']
    order = multirank([(FIT, (1., 0., 0., 0., 0.))], area)['order']
    assert sorted(order) == list(range(5))


def test_the_tag_score_sorts_continuously_and_the_description_acts_only_on_a_tie():
    score = np.array([.5, .5 + 1e-6, .1, .5, .5])
    reached = np.ones(5, dtype=bool)
    dd = np.array([.3, .3, .9, .3, .2])
    dq = np.array([.1, .2, .9, .3, .9])
    order = R4.adjust_lower_order(CHUNKS, score, reached, dd, dq, descjoin='key')['order']
    assert [CHUNKS[i] for i in order] == ['c1', 'c3', 'c0', 'c4', 'c2']


def test_the_mul_join_multiplies_by_both_clipped_cosines():
    score = np.array([.5, .5, .5, .5, .5])
    reached = np.ones(5, dtype=bool)
    dd = np.array([.4, -.4, .2, .4, .4])
    dq = np.array([.5, .5, .5, .1, .5])
    lower = R4.adjust_lower_order(CHUNKS, score, reached, dd, dq, descjoin='mul')
    assert lower['score'].tolist() == pytest.approx([.1, 0., .05, .02, .1])
    assert [CHUNKS[i] for i in lower['order']] == ['c0', 'c4', 'c2', 'c3', 'c1']


# --- multirank --------------------------------------------------------------

def test_multirank_orders_the_columns_by_the_query_tag_readings():
    assert R4.facet_column_order((.1, .9, .5, .5, 0.)) == (1, 2, 3, 0, 4)


def test_multirank_chooses_and_keys_the_edge_by_one_strength():
    fit = np.array([.95, .6, .95, .899])
    out = multirank([(fit, (1., 0., 0., 0., 0.))])
    # c1: tag a .6 * .3 = .18 against tag b .95 * .2 = .19 -> b, by strength, not by fit alone
    assert out['best_edge'][1] == 3
    strength = {0: .6 * .4, 1: .95 * .2, 2: .899 * .6}
    assert out['best_strength_all'] == pytest.approx(strength[2])
    for c, value in strength.items():
        assert out['best_strength'][c] == pytest.approx(value)
        assert out['fit_level'][c] == int(np.floor((strength[2] - out['best_strength'][c])
                                                   / R4.COS_NOISE))
    assert [CHUNKS[i] for i in out['order']] == ['c2', 'c0', 'c1', 'c4', 'c3']


def test_multirank_lets_the_first_column_decide_inside_one_strength_level():
    fit = np.array([0., 1., 1., 1.])
    topic = np.array([.5, .4, .4, .4 + R4.COS_NOISE / 4, .4])
    lay = R4.build_layer(POS, SCORE, topic, 1.)
    # readings put temporal first: stored temporal scores c0 (edge 1) 1, c1 (edge 3) 4,
    # c2 (edge 4) 3 -> c1, c2, c0
    out = R4.multirank_order(CHUNKS, EDGE_TAG, EDGE_CHUNK, topic, lay, ELIGIBLE,
                             [(fit, (0., 1., 0., 0., 0.))], DD, DQ)
    assert out['fit_level'][:3].tolist() == [0, 0, 0]
    assert [CHUNKS[i] for i in out['order']][:3] == ['c1', 'c2', 'c0']


# --- the arm, both modes, on one cached querytagger answer ------------------

def _one_cached_raw():
    """The stored answer only; the signature, which holds the question, is never read out."""
    folder = V.cache_root() / 'querytag'
    if not folder.is_dir():
        return None
    for path in sorted(folder.glob('*.json')):
        if path.name.endswith('.started.json'):
            continue
        saved = json.loads(path.read_text(encoding='utf-8'))
        if saved.get('ok'):
            return saved['raw']
    return None


@pytest.mark.parametrize('sort', ['adjust_lower', 'multirank', 'multikey'])
def test_both_modes_run_on_a_cached_answer(sort, monkeypatch):
    raw = _one_cached_raw()
    if raw is None:
        pytest.skip('no cached querytagger answer on this machine')
    cleaned, _ = V._collapse_duplicate_tags(raw)
    query = Q.parse('placeholder question', cleaned)

    def no_call(*args, **kwargs):
        raise AssertionError('no model call in this test')

    monkeypatch.setattr(chat, 'post', no_call)
    rng = np.random.default_rng(0)

    def fake_cosines(description, tags, prep):
        fits = rng.uniform(-.2, .9, size=(len(tags), len(TAGS)))
        d = rng.uniform(-.1, .6, size=len(CHUNKS))
        return ({'query_tag_cosines': fits, 'query_description_cosines': d},
                ModelUsage(), {'vector_sha256': 'x'})

    monkeypatch.setattr(V, '_interpret', lambda t, prep: (query, ModelUsage(), []))
    monkeypatch.setattr(V, '_query_cosines', fake_cosines)
    monkeypatch.setattr(V, '_area_rank', lambda prep, t, mode: (
        np.array([1, 0, 1, 1, 0]), {'mode': mode, 'area': 2}))
    seen = {}

    def fake_budget(rows, budget, doc_cache):
        seen['rows'] = [r['chunkId'] for r in rows]
        return (['x'] * 3, [[]] * 3, [], {'budget': budget, 'chars': budget, 'kept': 3,
                'boundary': None, 'exhausted': False})

    monkeypatch.setattr(V, '_budget_contexts', fake_budget)
    for name in V.KNOB_ENV.values():
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('HERB_V4_SORT', sort)
    p = V.Prepared(**{**prepared().__dict__,
                      'casefold_eligible': np.array([False, True, True, False])})
    out = V.answer_one_question(('q', 'placeholder question'), p, None, 50, 100)
    assert sorted(seen['rows']) == sorted(CHUNKS)
    assert seen['rows'][-3:] and set(seen['rows'][-3:]) == {'c2', 'c3', 'c4'}  # unreached last
    recorded = out.meta['policy']['knobs_recorded']
    assert recorded['active']['HERB_V4_SORT'] == sort
    assert recorded['active']['HERB_V4_QTOPIC'] == 'off'
    assert recorded['active']['HERB_V4_EDGECOMB'] == 'sum'
    assert recorded['active']['HERB_V4_DESCJOIN'] == 'key'
    assert out.meta['policy']['flip_gap'] == (1. if sort == 'multirank' else None)
    assert out.meta['policy']['product_named_tags_excluded'] == 2
    assert out.meta['diagnostics']['product_named_tags_excluded_casefold'] == 2
    assert out.meta['area']['mode'] == ('landed' if sort == 'multikey' else 'first')
    if sort == 'multikey':
        assert out.meta['diagnostics']['landed_chunks'] == 2       # the fake area: c1 and c4
        assert out.meta['interpreter']['question_side_tags_read'] == len(query.query_tags)
        pairs = out.meta['diagnostics']['adjacent_pairs_in_the_window_separated_by']
        assert sum(pairs.values()) == out.meta['diagnostics']['adjacent_pairs_in_the_window']
    else:
        assert 'adjacent_credited_pairs_separated_by' in out.meta['diagnostics']


@pytest.mark.parametrize('sort', ['adjust_lower', 'multirank'])
def test_the_question_side_tags_reach_under_adjust_lower_only(sort, monkeypatch):
    raw = {'description': 'Sought content',
           'tags': [{'t': 'described', 'facets': dict.fromkeys(Q.FACETS, 0.)}],
           'query_tags': [{'t': 'asked', 'facets': dict.fromkeys(Q.FACETS, 0.)}]}
    query = Q.parse('placeholder question', raw)
    fits = {'described': [0., .5, .5, .1], 'asked': [0., .1, .1, .9]}

    def fake_cosines(text, tags, prep):
        return ({'query_tag_cosines': np.array([fits[t] for t in tags]).reshape(len(tags), 4),
                 'query_description_cosines': np.zeros(len(CHUNKS))},
                ModelUsage(), {'vector_sha256': 'x'})

    monkeypatch.setattr(V, '_interpret', lambda t, prep: (query, ModelUsage(), []))
    monkeypatch.setattr(V, '_query_cosines', fake_cosines)
    monkeypatch.setattr(V, '_area_rank', lambda prep, t, mode: (
        np.zeros(len(CHUNKS), dtype=np.int64), {'mode': mode}))
    monkeypatch.setattr(V, '_budget_contexts', lambda rows, budget, cache: (
        ['x'] * 3, [[]] * 3, [], {'budget': budget, 'chars': budget, 'kept': 3,
                                  'boundary': None, 'exhausted': False}))
    for name in V.KNOB_ENV.values():
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('HERB_V4_SORT', sort)
    monkeypatch.setenv('HERB_V4_FACETS', 'off')
    monkeypatch.setenv('HERB_V4_EDGECOMB', 'best')
    p = V.Prepared(**{**prepared().__dict__,
                      'casefold_eligible': np.array([False, True, True, True])})
    out = V.answer_one_question(('q', 'placeholder question'), p, None, 50, 100)
    interp = out.meta['interpreter']
    assert interp['description_side_tags'] == 1 and interp['question_side_tags_in_answer'] == 1
    if sort == 'adjust_lower':
        # best terms: c2 .9 * .6 through the question-side tag, c0 .5 * .4, c1 .5 * .3
        assert interp['question_side_tags_read'] == 1 and interp['query_tags'] == 2
        assert out.meta['ranking']['delivered_chunk_ids'] == ['c2', 'c0', 'c1']
        assert out.meta['ranking']['delivered_scores'] == pytest.approx([.54, .2, .15])
        assert out.meta['policy']['knobs_recorded']['active']['HERB_V4_EDGECOMB'] == 'best'
    else:
        assert interp['question_side_tags_read'] == 0 and interp['query_tags'] == 1


def test_adjust_lower_reads_its_own_knobs(monkeypatch):
    for name in V.KNOB_ENV.values():
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('HERB_V4_SORT', 'adjust_lower')
    read = V.knob_record(V.knobs())['read_by_active_sort']
    assert 'HERB_V4_FACETS' in read and 'HERB_V4_FITEQ' not in read


# --- the re-ask leaves another worker's marker alone ------------------------

def test_the_re_ask_never_deletes_a_marker_it_did_not_write(monkeypatch, tmp_path):
    key = 'k' * 64
    folder = tmp_path / 'querytag'
    folder.mkdir()
    marker = folder / (key + '.started.json')
    marker.write_text('{}', encoding='utf-8')

    def in_flight(*args, **kwargs):
        raise RuntimeError(f'Facet interpreter uncertain querytag attempt; key={key}')

    monkeypatch.setattr(V, '_cached_stage', in_flight)
    p = V.Prepared(**{**prepared().__dict__, 'cache_dir': tmp_path})
    with pytest.raises(RuntimeError):
        V._interpret('placeholder question', p)
    assert marker.exists()


def test_the_re_ask_removes_only_its_own_failed_attempt(monkeypatch, tmp_path):
    key = 'k' * 64
    folder = tmp_path / 'querytag'
    folder.mkdir()
    answer, marker = folder / (key + '.json'), folder / (key + '.started.json')
    calls = []

    def attempt(stage, system, user, validate, cache_dir, model=None):
        calls.append(1)
        if len(calls) == 1:
            marker.write_text('{}', encoding='utf-8')
            answer.write_text(json.dumps({'ok': False}), encoding='utf-8')
            raise RuntimeError(f'Facet interpreter querytag failed; key={key}; no retry')
        raw = {'description': 'd', 'tags': [{'t': 'x', 'facets': dict.fromkeys(Q.FACETS, 0)}]}
        return validate(raw), ModelUsage(), {'cache_hit': False, 'key': key}

    monkeypatch.setattr(V, '_cached_stage', attempt)
    p = V.Prepared(**{**prepared().__dict__, 'cache_dir': tmp_path})
    V._interpret('placeholder question', p)
    assert len(calls) == 2 and not answer.exists() and not marker.exists()

"""tools/walkthrough.py on toy arrays: what the tool does around the chain of
`artefact.v4_walk` - its checks, its walk, its examples and its guards. The chain's own tests
are in test/tests/test_artefact_v4_walk.py. No graph, no model call, no question set, no chunk
text."""
import inspect
import json
import math
from pathlib import Path
import re
import sys
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import walkthrough as W  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402


def test_the_tool_walks_the_chain_the_arm_sorts_by():
    for name in ('ALTERNATIVES', 'FIRST_GROUPINGS', 'GROUPINGS', 'MIDDLE', 'build_layer', 'chain',
                 'chance_corrected_best', 'chunk_values', 'structure_lifts'):
        assert getattr(W, name) is getattr(WK, name)
    assert set(W.ALTERNATIVE_TEXT) == set(WK.ALTERNATIVES)
    source = Path(W.__file__).read_text(encoding='utf-8')
    for name in ('positions', 'relevance', 'tag_value', 'text_side', 'group_lift',
                 'levels_and_order', 'build_layer', 'structure_lifts', 'chain'):
        assert f'def {name}(' not in source


# ------------------------------------------------------------------ M4: the tag count

def test_the_shuffled_check_sits_near_zero_corrected_and_above_it_uncorrected():
    rng = np.random.default_rng(5)
    n_chunks = 1500
    n_c = rng.integers(1, 30, size=n_chunks)
    edge_chunk = np.repeat(np.arange(n_chunks), n_c)
    weights = [np.clip(rng.normal(size=edge_chunk.size), 0., None) for _ in range(6)]
    corrected, uncorrected = W.shuffled_tag_count_check(weights, edge_chunk, n_chunks, 7)
    assert max(abs(r) for r in corrected) < 4 / math.sqrt(n_chunks - 1)
    assert min(uncorrected) > .3
    again, _ = W.shuffled_tag_count_check(weights, edge_chunk, n_chunks, 7)
    assert again == corrected


def test_the_three_shuffles_of_the_tag_count_dependence():
    rng = np.random.default_rng(15)
    tags, n_chunks = 300, 400
    n_c = rng.integers(1, 20, size=n_chunks)
    edge_chunk = np.repeat(np.arange(n_chunks), n_c)
    edge_tag = rng.integers(1, tags, size=edge_chunk.size)
    eligible = np.ones(tags, dtype=bool)
    eligible[0] = False
    fit = np.clip(rng.normal(size=(3, tags)), 0., None)
    fit[:, 0] = 0.
    factor = rng.uniform(.2, 1.8, size=(3, edge_chunk.size))
    got = W.tag_count_dependence(fit, factor, eligible, edge_tag, edge_chunk, n_chunks, 7)
    assert set(got) == set(W.WAYS) and all(set(v) == set(W.VALUES) for v in got.values())
    assert all(len(rows) == 3 for v in got.values() for rows in v.values())
    w = fit[:, edge_tag] * factor
    corrected, uncorrected = W.shuffled_tag_count_check(w, edge_chunk, n_chunks, 7)
    assert got['edges']['pooled'] == corrected and got['edges']['best'] == uncorrected
    counts = np.bincount(edge_chunk, minlength=n_chunks)
    for i in range(3):
        best = np.array([w[i][edge_chunk == c].max() for c in range(n_chunks)])
        assert got['observed']['best'][i] == pytest.approx(W.spearman(counts, best))
    assert min(got['edges']['best']) > .3 and min(got['edges']['total']) > .3
    assert got == W.tag_count_dependence(fit, factor, eligible, edge_tag, edge_chunk,
                                         n_chunks, 7)


def test_the_per_edge_form_is_free_of_the_tag_count_when_the_fits_are_shuffled():
    # an edge's factor goes with its chunk's tag count; the fits are independent of both
    rng = np.random.default_rng(16)
    tags, n_chunks = 6000, 1200
    n_c = np.where(np.arange(n_chunks) < 600, 1, 6)
    edge_chunk = np.repeat(np.arange(n_chunks), n_c)
    edge_tag = rng.permutation(np.arange(1, tags))[:edge_chunk.size]
    eligible = np.ones(tags, dtype=bool)
    eligible[0] = False
    fit = rng.exponential(size=(4, tags))
    fit[:, 0] = 0.
    factor = np.tile(np.where(n_c[edge_chunk] == 1, 1.5, .5), (4, 1))
    got = W.tag_count_dependence(fit, factor, eligible, edge_tag, edge_chunk, n_chunks, 3)
    assert edge_tag.size == edge_chunk.size == np.unique(edge_tag).size
    assert max(abs(r) for r in got['tags']['per_edge']) < 4 / math.sqrt(n_chunks - 1)
    assert max(got['tags']['pooled']) < -.3              # the pooled tail is not


def test_probe_dependence_reads_each_probe_as_a_query_tag():
    rng = np.random.default_rng(17)
    tags, n_chunks = 200, 150
    n_c = rng.integers(1, 12, size=n_chunks)
    edge_chunk = np.repeat(np.arange(n_chunks), n_c)
    edge_tag = rng.integers(1, tags, size=edge_chunk.size)
    eligible = np.ones(tags, dtype=bool)
    eligible[0] = False
    cosines = rng.normal(.1, .03, size=(5, tags))
    factor = rng.uniform(.2, 1.8, size=edge_chunk.size)
    got = W.probe_dependence(cosines, eligible, factor, edge_tag, edge_chunk, n_chunks)
    assert set(got) == {'fit', 'best', 'pooled', 'per_edge'}
    assert all(len(v) == 5 for v in got.values())
    z, _, _ = W.standing(cosines[2][eligible])
    fit = np.zeros(tags)
    fit[eligible] = np.clip(z, 0., None)
    top = np.array([fit[edge_tag][edge_chunk == c].max() for c in range(n_chunks)])
    assert got['fit'][2] == pytest.approx(W.spearman(n_c, top))
    best = np.array([(fit[edge_tag] * factor)[edge_chunk == c].max() for c in range(n_chunks)])
    assert got['best'][2] == pytest.approx(W.spearman(n_c, best))
    with pytest.raises(ValueError):
        W.probe_dependence(cosines[:, :5], eligible, factor, edge_tag, edge_chunk, n_chunks)


def test_the_probes_are_drawn_once_without_replacement():
    eligible = np.array([False] + [True] * 30)
    names = [f'tag_{i}' for i in range(31)]
    pick, texts = W.draw_probes(eligible, names, lambda s: s.replace('_', ' '), seed=5, size=10)
    assert pick.tolist() == sorted(set(pick.tolist())) and len(pick) == 10 and 0 not in pick
    assert texts == [f'tag {i}' for i in pick.tolist()]
    again, _ = W.draw_probes(eligible, names, str, seed=5, size=10)
    assert again.tolist() == pick.tolist()
    every, _ = W.draw_probes(eligible, names, str, seed=5, size=100)
    assert every.tolist() == list(range(1, 31))


# ------------------------------------------------------------------ M6: the random membership

def csr(rows):
    ptr = np.zeros(len(rows) + 1, dtype=np.int64)
    members = []
    for i, row in enumerate(rows):
        members += list(row)
        ptr[i + 1] = len(members)
    return ptr, np.array(members, dtype=np.int64)


def test_random_membership_recomputes_the_structure_on_permuted_values():
    inputs = toy_inputs(seed=10)
    layer, query = W.build_layer(inputs), toy_query(inputs)
    run = W.chain(layer, query, .002)
    got = W.random_membership(run['S'], layer, 5, 12)
    assert set(got) == {'product', 'near'}
    for kind in got:
        assert len(got[kind]['largest_lift']) == len(got[kind]['chunks_lifted']) == 12
        assert 0 <= got[kind]['tau2_above_0'] <= 12 and min(got[kind]['largest_lift']) >= 0
    assert got == W.random_membership(run['S'], layer, 5, 12)


# ------------------------------------------------------------------ the rank correlation

def test_spearman():
    assert W.spearman([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.)
    assert W.spearman([1, 2, 3, 4], [4, 3, 2, 1]) == pytest.approx(-1.)
    assert W.spearman([1, 1, 1], [1, 2, 3]) is None


# ------------------------------------------------------------------ the walk on a toy graph

def toy_inputs(seed=0, chunks=80, tags=50, products=4):
    rng = np.random.default_rng(seed)
    edge_tag, edge_chunk = [], []
    for c in range(chunks):
        mine = rng.choice(np.arange(1, tags), size=int(rng.integers(1, 7)), replace=False)
        edge_tag += mine.tolist()
        edge_chunk += [c] * mine.size
    edge_tag += [0, 0]                           # tag 0 is a product name: not eligible
    edge_chunk += [0, 1]
    edge_tag, edge_chunk = np.array(edge_tag), np.array(edge_chunk)
    eligible = np.ones(tags, dtype=bool)
    eligible[0] = False
    product = np.arange(chunks) % products
    channel_rows = [[c // 5] if c < 40 else [] for c in range(chunks)]
    channel_rows[3] = [0, 7]                     # one chunk in two channels
    channel_rows[39] = [50]                      # a channel of one chunk
    adjacency_rows = [[] for _ in range(chunks)]
    for a in list(range(0, 20)) + list(range(50, 60)):
        if a % 5 != 4:
            adjacency_rows[a].append(a + 1)
            adjacency_rows[a + 1].append(a)
    channel_ptr, channels = csr(channel_rows)
    adjacency_ptr, adjacency = csr(adjacency_rows)
    query_tags = 4
    readings = np.array([[1., .5, 1., 0., 0.], [0., 0., 0., 0., 0.], [.9, .2, .2, .8, .8],
                         [.5, .5, .5, .5, .5]])
    return {
        'question': 'a toy question', 'description': 'a toy description',
        'query_texts': [f'query tag {i}' for i in range(query_tags)],
        'query_lists': ['description-side'] * 3 + ['question-side'],
        'query_readings': readings,
        'query_tag_cosines': rng.normal(.1, .03, size=(query_tags, tags)),
        'query_tag_description_cosines': np.array([.6, .3, .45, -.1]),
        'd_description': rng.normal(.2, .06, size=chunks),
        'd_question': rng.normal(.18, .06, size=chunks),
        'chunk_ids': [f'{(c * 7919) % 1000:04d}' for c in range(chunks)],
        'chunk_kinds': ['slack_thread_batch' if c < 40 else 'document_part'
                        for c in range(chunks)],
        'graph_tags': ['ProductA'] + [f'tag {t}' for t in range(1, tags)],
        'eligible': eligible, 'edge_tag': edge_tag, 'edge_chunk': edge_chunk,
        'edge_topic': rng.normal(.22, .07, size=edge_tag.size),
        'edge_facets': rng.normal(size=(edge_tag.size, 4)),
        'product': product, 'product_names': [f'Product{p}' for p in range(products)],
        'channel_ptr': channel_ptr, 'channels': channels,
        'adjacency_ptr': adjacency_ptr, 'adjacency': adjacency, 'cos_noise': .002,
        'probe_tags': np.array([3, 9, 17, 21, 30, 44]),
        'probe_names': [f'tag {t}' for t in (3, 9, 17, 21, 30, 44)],
        'probe_cosines': rng.normal(.1, .03, size=(6, tags))}


def toy_query(inputs):
    return {'cosines': inputs['query_tag_cosines'], 'readings': inputs['query_readings'],
            'description_cosines': inputs['query_tag_description_cosines'],
            'd_description': inputs['d_description'], 'd_question': inputs['d_question']}


PROVENANCE = {'stamp': '20000101T000000Z', 'interpreter_model': 'none', 'cache_hit': None,
              'cache_key': None, 'asks': 0, 'saved_usage': None, 'stand_in': 'toy',
              'usage': {'calls': 0, 'tokens_in': 0, 'tokens_out': 0, 'cached_input_tokens': 0},
              'budget': {'budget': 72000, 'kept': 3, 'chars': 72000,
                         'boundary': {'id': '0007', 'chars_kept': 10, 'chars_full': 20}},
              'walkthrough_sha256': 'x', 'source_sha256': {'a.py': 'y'}}


def test_walk_and_render_on_the_toy_graph(tmp_path):
    inputs = toy_inputs(seed=6)
    result, order = W.walk(inputs)
    assert sorted(order) == list(range(80))
    assert result['counts']['eligible_edges'] == inputs['edge_tag'].size - 2
    assert result['order'] == [inputs['chunk_ids'][c] for c in order]
    assert [ex['rule'] for ex in result['examples']] == [1, 2, 3, 4, 5, 6, 7]
    found = [ex['detail']['chunk'] for ex in result['examples'] if ex['detail']]
    assert len(found) == len(set(found)) and found[0] == result['order'][0]
    assert set(result['alternatives']) == set(W.ALTERNATIVES)
    for row in result['first']:
        assert row['S_prime'] >= row['T'] + row['side'] - 1e-12
    first = result['examples'][0]['detail']
    assert first['position'] == 1 and first['level'] == 0
    assert first['w'] == pytest.approx(first['fit'] * first['factor'])
    assert first['T'] == pytest.approx(first['centrality'] * first['v'])
    assert first['S'] == pytest.approx(first['T'] + first['side'])
    assert set(first['lift']) == {'product', 'near'}
    assert first['S_prime'] == pytest.approx(first['S'] + sum(first['lift'].values()))
    assert first['first_form']['S_prime'] == pytest.approx(
        first['S'] + sum(first['first_form']['lift'].values()))
    assert set(first['position_under']) == set(W.ALTERNATIVES)
    assert first['pooled_tail']['v_star'] <= first['v']
    # the probes, the three-way table, the by-kind prints
    assert result['M4']['probes']['probes'] == 6
    assert set(result['M4']['probes']['values']) == {'fit', 'best', 'pooled', 'per_edge'}
    assert set(result['M4']['dependence']['table']) == set(W.WAYS)
    assert set(result['M3']['position_spearman_with_n_c']) == set(W.ALL_FACETS)
    assert sum(v['chunks'] for v in result['M5']['by_kind'].values()) == 80
    assert set(result['M3']['query_tags'][0]['factor_by_kind']) == set(result['kinds'])
    # the first 15 by record kind and product, for the PROPOSAL, its stages, every alternative
    rows = ([result['first_mix']['PROPOSAL']] + list(result['first_mix']['stages'].values())
            + [v['mix'] for v in result['alternatives'].values()])
    assert len(rows) == 1 + 3 + len(W.ALTERNATIVES)
    for row in rows:
        assert sum(row['kinds'].values()) + row['other'] == W.TOP
        assert 1 <= row['products'] <= 4
    kinds_of = dict(zip(result['per_chunk']['chunk'], result['per_chunk']['kind']))
    final = [kinds_of[c] for c in result['order'][:W.TOP]]
    assert result['first_mix']['PROPOSAL']['by_kind'] == {k: final.count(k)
                                                          for k in sorted(set(final))}
    # A7
    plain = sorted(range(80), key=lambda i: (-result['per_chunk']['S_prime'][i],
                                             result['per_chunk']['chunk'][i]))
    assert result['alternatives']['A7']['first'] == [result['per_chunk']['chunk'][i]
                                                     for i in plain[:W.TOP]]
    assert result['M7']['A7_positions_that_differ_among_the_first'] == sum(
        a != b for a, b in zip(result['order'][:W.TOP], result['alternatives']['A7']['first']))
    # the channel facts and the random membership
    corpus = result['M6']['corpus']
    assert corpus['near_groups'] == 6 and corpus['near_groups_of_more_than_one_kind'] == 0
    assert sum(v['near_groups'] for v in corpus['near_groups_by_their_channels'].values()) == 6
    assert corpus['near_groups_by_their_channels']['equal_to_one_channel']['near_groups'] == 4
    assert corpus['of_them_with_equal_channel_and_record_raw_under_A6d'] == corpus[
        'chunks_whose_near_group_is_one_channel'] == 20
    assert set(result['M6']['random_membership']) == {'product', 'near'}
    text = '\n'.join(W.render(result, PROVENANCE))
    for step in ('M1 -', 'M2 -', 'M3 -', 'M4 -', 'M5 -', 'M6 -', 'M7 -', 'EXAMPLES', 'RULE 7',
                 'ALT A3b', 'ALT A4e', 'ALT A6d', 'ALT A7', 'PROBES', 'near group'):
        assert step in text
    assert not re.search(r'\bnan\b', text)
    folder = W.write(tmp_path / 'out', result, PROVENANCE)
    saved = json.loads((folder / 'walkthrough.json').read_text(encoding='utf-8'))
    assert saved['order'] == result['order'] and saved['provenance']['stamp'] == PROVENANCE['stamp']
    assert (folder / 'walkthrough.txt').read_text(encoding='utf-8') == text + '\n'


def test_the_walk_is_the_same_twice_and_after_a_dump(tmp_path):
    inputs = toy_inputs(seed=7)
    first, order = W.walk(inputs)
    W.dump_inputs(inputs, tmp_path / 'arrays.npz')
    again, order_again = W.walk(W.read_inputs(tmp_path / 'arrays.npz'))
    assert order == order_again
    assert json.dumps(W._plain(first), sort_keys=True) == json.dumps(W._plain(again),
                                                                     sort_keys=True)


def test_the_walk_stops_when_the_check_leaves_zero(monkeypatch):
    def lifted(*args):
        return {way: {value: [.2, .3] for value in W.VALUES} for way in W.WAYS}

    monkeypatch.setattr(W, 'tag_count_dependence', lifted)
    with pytest.raises(W.Stop):
        W.walk(toy_inputs(seed=8))


def test_the_walk_runs_without_probes():
    inputs = toy_inputs(seed=8)
    for key in ('probe_tags', 'probe_names', 'probe_cosines'):
        del inputs[key]
    result, _ = W.walk(inputs)
    assert result['M4']['probes'] is None
    assert 'PROBES: not computed in this run' in '\n'.join(W.render(result, PROVENANCE))


# ------------------------------------------------------------------ the examples, the guards

def test_the_examples_follow_their_rules_in_order():
    order = [4, 2, 0, 1, 3, 5]
    facts = {'winner': np.array([1, 0, 1, 0, 1, 0]),
             'T': np.array([2., 0., 3., 1., 4., 1.]),
             'n_c': np.array([1, 1, 1, 9, 2, 1]),
             'slack': np.array([True, False, False, False, False, True]),
             'near_size': np.array([3, 0, 2, 0, 9, 9]),
             'product': np.array([0, 0, 0, 1, 0, 0]),
             'median_near_size': 5.}
    picked = W.select_examples(order, facts)
    assert [p['chunk'] for p in picked] == [4, 3, None, 0, 1, None, None]
    # rule 2 skips chunk 2 (the same query tag as chunk 4) and takes 3; rule 3 (n_c >= the
    # 90th percentile, 5.5) would take 3, already picked; rule 4 takes the Slack chunk 0 (near
    # group of 3, at most 5), not 5 (near group of 9); rule 5 takes 1, the first left with no
    # near group; rule 6 would take 1 and rule 7 would take 3, both already picked.
    assert picked[2]['text'].endswith('(5.5)')
    assert 'near group has at most the median near-group size (5)' in picked[3]['text']
    assert picked[4]['text'] == 'the first chunk with no near group'


def test_the_counts_must_be_the_spec_s():
    W.check_counts(dict(W.SPEC_COUNTS, edges=1))
    with pytest.raises(W.Stop, match='chunks 4,807'):
        W.check_counts(dict(W.SPEC_COUNTS, chunks=4807))


class StubArm:
    """An arm whose _interpret asks through _cached_stage and re-asks once on a RuntimeError,
    as artefact_v4._interpret does."""

    def __init__(self, outcomes):
        self.outcomes, self.asked = list(outcomes), 0
        self._cached_stage = self._stage

    def _stage(self, *args):
        self.asked += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def _interpret(self, question, prepared):
        for attempt in (1, 2):
            try:
                return self._cached_stage('querytag', question)
            except RuntimeError:
                if attempt == 2:
                    raise


def test_a_failed_answer_stops_before_the_arm_asks_again():
    guard = W._CallGuard(lambda *a, **k: None, 1)
    guard.calls, guard.answers = 1, [{'content': 'not json'}]
    arm = StubArm([RuntimeError('querytag failed; key=abc; no retry'), 'a second answer'])
    stage = arm._cached_stage
    with pytest.raises(W.Stop, match='model calls made 1') as stop:
        W.ask_once(arm, 'a question', None, guard)
    assert 'not json' in str(stop.value) and 'key=abc' in str(stop.value)
    assert arm.asked == 1 and arm._cached_stage == stage
    good = StubArm(['the answer'])
    assert W.ask_once(good, 'a question', None, guard) == 'the answer' and good.asked == 1

    class Refusing(StubArm):
        def _interpret(self, question, prepared):
            raise RuntimeError('no cached querytagger answer; no model call made')

    with pytest.raises(W.Stop, match='no cached querytagger answer'):
        W.ask_once(Refusing([]), 'a question', None, guard)


def test_a_cached_answer_s_own_usage_is_printed():
    result, _ = W.walk(toy_inputs(seed=6))
    provenance = dict(PROVENANCE, stand_in=None, cache_hit=True, cache_key='k',
                      saved_usage={'prompt_tokens': 123, 'completion_tokens': 45})
    text = '\n'.join(W.render(result, provenance))
    assert 'cache hit True' in text
    assert 'the cached answer\'s own call: tokens in 123, out 45' in text
    assert 'STAND-IN' not in text


def test_the_provenance_records_only_the_knobs_the_tool_reads():
    arm = SimpleNamespace(
        KNOB_ENV={'sort': 'HERB_V4_SORT', 'offline': 'HERB_V4_OFFLINE',
                  'walkfit': 'HERB_V4_WALK_FIT', 'walkequal': 'HERB_V4_WALK_EQUAL',
                  'walktagrole': 'HERB_V4_WALK_TAGROLE',
                  'walkdescrole': 'HERB_V4_WALK_DESCROLE',
                  'walkquestrole': 'HERB_V4_WALK_QUESTROLE'},
        knobs=lambda: {'sort': 'walk', 'offline': 'on', 'walkfit': 'raw', 'walkequal': 'off',
                       'walktagrole': 'the tags\'', 'walkdescrole': 'the description\'s',
                       'walkquestrole': 'the question\'s'})
    # the offline knob and the three role knobs, each under its own name, and no other knob
    assert W.knobs_read(arm) == {'HERB_V4_OFFLINE': 'on',
                                 'HERB_V4_WALK_TAGROLE': 'the tags\'',
                                 'HERB_V4_WALK_DESCROLE': 'the description\'s',
                                 'HERB_V4_WALK_QUESTROLE': 'the question\'s'}
    source = inspect.getsource(W.load_live)
    assert "'knobs_read': knobs_read(A)" in source and 'A.knobs()' not in source
    assert 'embed_query_side(A, query, prepared)' in source and "'roles': dict(roles)" in source
    assert "A._query_cosines(probe_names[0], probe_names, prepared, roles['tags'])" in source


def test_the_query_is_embedded_through_the_arm_s_role_plan():
    tag = lambda text: SimpleNamespace(text=text)
    rows = {'a': [1., 2.], 'b': [3., 4.], 'c': [5., 6.]}
    central = {'a': .1, 'b': .2, 'c': .3}
    flags = {'walktagrole': 'passage', 'walkdescrole': 'query', 'walkquestrole': 'the knob'}
    # the question alone: under the query role with no role named, under another with it
    for asked_in, asked in (('query', ('plain', 'the question', [], 'prepared')),
                            ('another', ('plain', 'the question', [], 'prepared', 'another'))):
        query = SimpleNamespace(description='the description', question='the question',
                                tags=[tag('a'), tag('b')], query_tags=[tag('c')])
        calls = []

        def walk_cosines(description, tags, prepared, roles):
            calls.append(('walk', description, tuple(tags), prepared, roles))
            return ({'query_tag_cosines': np.array([rows[t] for t in tags]),
                     'query_description_cosines': np.array([.7, .8, .9]),
                     'query_tag_description_cosines': np.array([central[t] for t in tags])},
                    SimpleNamespace(calls=2), {})

        def query_cosines(*args):
            calls.append(('plain',) + args)
            return ({'query_description_cosines': np.array([.4, .5, .6])},
                    SimpleNamespace(calls=1), {})

        plan = {'tags': 'the tags\'', 'description': 'the description\'s', 'question': asked_in,
                'centrality': 'the centrality\'s'}
        arm = SimpleNamespace(knobs=lambda: dict(flags),
                              walk_roles=lambda read, plan=plan: dict(plan, read=dict(read)),
                              _walk_cosines=walk_cosines, _query_cosines=query_cosines)
        roles, arrays, embedding_calls = W.embed_query_side(arm, query, 'prepared')
        # the roles are the arm's plan over the arm's knobs
        assert roles == dict(plan, read=flags)
        # each tag list through the arm's role plan, the raw question alone between them
        assert calls == [('walk', 'the description', ('a', 'b'), 'prepared', roles), asked,
                         ('walk', 'the description', ('c',), 'prepared', roles)]
        assert arrays['query_tag_cosines'].tolist() == [[1., 2.], [3., 4.], [5., 6.]]
        assert arrays['query_tag_description_cosines'].tolist() == [.1, .2, .3]
        assert arrays['d_description'].tolist() == [.7, .8, .9]
        assert arrays['d_question'].tolist() == [.4, .5, .6]
        assert embedding_calls == 5
        # no question-side list: one tag call
        del calls[:]
        query.query_tags = []
        _, arrays, embedding_calls = W.embed_query_side(arm, query, 'prepared')
        assert calls == [('walk', 'the description', ('a', 'b'), 'prepared', roles), asked]
        assert embedding_calls == 3 and arrays['query_tag_cosines'].shape == (2, 2)


def test_the_print_names_the_embedding_roles_when_the_provenance_carries_them():
    result, _ = W.walk(toy_inputs(seed=6))
    plain = '\n'.join(W.render(result, PROVENANCE))
    assert 'EMBEDDING ROLES' not in plain and 'embedded in the query role' in plain
    roles = {'tags': 'passage', 'description': 'query', 'question': 'passage',
             'centrality': 'query'}
    text = '\n'.join(W.render(result, dict(PROVENANCE, roles=roles)))
    assert ('EMBEDDING ROLES (artefact_v4.walk_roles; HERB_V4_WALK_TAGROLE, '
            'HERB_V4_WALK_DESCROLE, HERB_V4_WALK_QUESTROLE)') in text.splitlines()
    assert ('query tags against graph tags: passage | query description against chunk '
            'descriptions: query | raw question against chunk descriptions: passage | query '
            'tag against query description (centrality): query') in text
    assert 'embedded in the passage role (artefact_v4._query_cosines)' in text
    assert 'embedded in the query role' not in text
    # the roles add lines and change the probes' line; every other line is the same
    assert set(plain.splitlines()) - set(text.splitlines()) == {
        '  embedded in the query role (artefact_v4._query_cosines), each used as a query tag '
        'with five equal shares.'}


def test_the_call_guard_lets_one_call_through():
    calls = []
    guard = W._CallGuard(lambda *a, **k: calls.append(a) or {'ok': True}, 1)
    assert guard('/chat/completions', {}) == {'ok': True}
    with pytest.raises(RuntimeError, match='refused'):
        guard('/chat/completions', {})
    assert len(calls) == 1 and guard.calls == 1
    with pytest.raises(RuntimeError, match='refused'):
        W._CallGuard(lambda *a, **k: calls.append(a), 0)('/chat/completions', {})
    assert len(calls) == 1

"""One made-up question through the retrieval chain, step by step, as numbers.

The chain is `artefact.v4_walk`: M1 to M7, each step's PROPOSAL and the alternatives named
there (`ALTERNATIVES`). This file loads the graph and the query through artefact_v4's own
loaders, runs the PROPOSAL and each alternative - the whole chain with that one step exchanged -
and prints beside them:

  M4        the Spearman over the chunks between n_c and each of the four chunk values:
            observed; with each edge's fit and factor moved to another edge; with the fits
            permuted over the eligible tags; and for eligible graph tag names read as query
            tags (the probes)
  M6        the two groupings on S permuted over the chunks
  examples  the chunks shown in detail, each the first of the PROPOSAL order that meets its rule

The query is embedded as the arm's walk sort embeds it, each comparison in the role
HERB_V4_WALK_TAGROLE, HERB_V4_WALK_DESCROLE and HERB_V4_WALK_QUESTROLE name
(`artefact_v4.walk_roles`, `embed_query_side`); the probes are embedded in the role of the
query tags.

Chunk text is never written.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np
from scipy.stats import rankdata

ROOT = Path(__file__).resolve().parents[1]
for _path in (ROOT / 'prod', ROOT / 'test'):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from artefact.v4_rank import ADJUST_FACETS, ALL_FACETS
from artefact.v4_strength import best_edges, standing
from artefact.v4_walk import (ALTERNATIVES, FIRST_GROUPINGS, GROUPINGS, MIDDLE, build_layer,
                              chain, chance_corrected_best, chunk_values, structure_lifts)

QUESTION = ('Why did the EdgeForce team change the rollback procedure for model updates, and '
            'what had gone wrong with rollbacks before that?')
SPEC_COUNTS = {'chunks': 4808, 'graph_tags': 16654, 'eligible_graph_tags': 16609,
               'eligible_edges': 57204}
TOP = 15                 # "the first 15"
NEAREST = 5              # M1: a query tag's nearest eligible graph tags
LARGEST = 5              # M6: the groups with the largest lift
N_C_PERCENTILE = 90      # example rule 3
CHAR_BUDGET = 72000
SHUFFLE_SEED = 20261005  # every shuffle, the probe draw and the membership permutations
PROBES = 100             # M4: eligible graph tag names used as query tags
PERMUTATIONS = 200       # M6: S permuted over the chunks
KIND_COLUMNS = ('slack_thread_batch', 'document', 'document_part', 'pr_batch',
                'meeting_transcript')
OUT_ROOT = ROOT / 'output' / 'walkthrough'
LISTS = ('description-side', 'question-side')
VALUES = ('best', 'pooled', 'per_edge', 'total')
WAYS = ('observed', 'edges', 'tags')
STAGES = (('T', 'T alone'), ('S', 'S'), ('S_prime', 'S\''))
ALTERNATIVE_TEXT = {
    'A1': 'the raw cosine cos_q(t) as the fit',
    'A3': 'five equal shares',
    'A3b': 'no facet adjust (factor 1)',
    'A4a': 'pooled tail: v* in place of v',
    'A4b': 'per query tag the sum of w_q over the chunk\'s edges, then the max over q',
    'A4c': 'all query tags equal (centrality 1)',
    'A4d': 'the sum over q of centrality_q x v_q(c)',
    'A4e': 'per edge: v* (a fit) in place of v',
    'A5a': 'S = T alone',
    'A5b': 'side = D alone',
    'A5c': 'side clipped at 0',
    'A6a': 'S\' = S (no structure)',
    'A6b': 'trust = 1 everywhere',
    'A6c': 'near with reference 0',
    'A6d': 'product + channel + record, reference 0',
    'A7': 'no levels: S\' descending',
}


class Stop(Exception):
    """A condition under which the walk-through stops and reports."""


# ------------------------------------------------------------------ the checks, on arrays

def spearman(a, b):
    """The correlation of the average ranks of a and b; None when either is constant."""
    ra = rankdata(np.asarray(a, dtype=np.float64))
    rb = rankdata(np.asarray(b, dtype=np.float64))
    if ra.size != rb.size or ra.size < 2 or ra.std() == 0. or rb.std() == 0.:
        return None
    return float(np.corrcoef(ra, rb)[0, 1])


def shuffled_tag_count_check(weights, edge_chunk, n_chunks, seed):
    """Per query tag: its w permuted over the edges, then the Spearman over the chunks between
    n_c and the pooled-tail v* (corrected) and between n_c and v (uncorrected), 0 for a chunk
    with no edge. One generator from `seed`; one permutation per query tag, in the order
    given."""
    rng = np.random.default_rng(seed)
    corrected, uncorrected = [], []
    for w in weights:
        got = chance_corrected_best(rng.permutation(np.asarray(w, dtype=np.float64)),
                                    edge_chunk, n_chunks)
        plain = np.where(got['n_c'] > 0, got['v'], 0.)
        corrected.append(spearman(got['n_c'], got['v_star']))
        uncorrected.append(spearman(got['n_c'], plain))
    return corrected, uncorrected


def tag_count_dependence(fit_of_tag, factor, eligible, edge_tag, edge_chunk, n_chunks, seed):
    """Per query tag the Spearman over the chunks between n_c and each of the four chunk values
    of `chunk_values`, three ways: observed; edges, each edge's (fit, factor) pair moved to
    another edge by one permutation of the edges; tags, the fits permuted over the eligible
    tags with every edge's factor left in place. One generator per way from `seed`; one
    permutation per query tag, in the order given. fit_of_tag: (query tags, graph tags);
    factor: (query tags, edges)."""
    fit_of_tag = np.asarray(fit_of_tag, dtype=np.float64)
    factor = np.asarray(factor, dtype=np.float64)
    edge_tag = np.asarray(edge_tag, dtype=np.int64)
    edge_chunk = np.asarray(edge_chunk, dtype=np.int64)
    open_tags = np.flatnonzero(np.asarray(eligible, dtype=bool))
    n_c = np.bincount(edge_chunk, minlength=n_chunks)
    over_edges, over_tags = np.random.default_rng(seed), np.random.default_rng(seed)
    out = {way: {value: [] for value in VALUES} for way in WAYS}
    for i in range(fit_of_tag.shape[0]):
        fits = fit_of_tag[i][open_tags]
        mine = fit_of_tag[i][edge_tag]
        swap = over_edges.permutation(edge_tag.size)
        mixed = fit_of_tag[i].copy()
        mixed[open_tags] = over_tags.permutation(fits)
        for way, (fit, by) in (('observed', (mine, factor[i])),
                               ('edges', (mine[swap], factor[i][swap])),
                               ('tags', (mixed[edge_tag], factor[i]))):
            got = chunk_values(fit, by, fits, edge_chunk, n_chunks)
            out[way]['best'].append(spearman(n_c, got['best']))
            out[way]['pooled'].append(spearman(n_c, got['pooled']['v_star']))
            out[way]['per_edge'].append(spearman(n_c, got['per_edge']['v_star']))
            out[way]['total'].append(spearman(n_c, got['total']))
    return out


def probe_dependence(probe_cosines, eligible, factor, edge_tag, edge_chunk, n_chunks):
    """Per probe - a cosine row over the graph tags, read as a query tag with the one factor
    given per edge - the Spearman over the chunks between n_c and: fit, the chunk's largest
    fit; best, pooled, per_edge as `chunk_values`."""
    probe_cosines = np.asarray(probe_cosines, dtype=np.float64)
    eligible = np.asarray(eligible, dtype=bool)
    edge_tag = np.asarray(edge_tag, dtype=np.int64)
    edge_chunk = np.asarray(edge_chunk, dtype=np.int64)
    if probe_cosines.ndim != 2 or probe_cosines.shape[1] != eligible.size:
        raise ValueError('Expected one cosine row over the graph tags per probe')
    n_c = np.bincount(edge_chunk, minlength=n_chunks)
    out = {key: [] for key in ('fit', 'best', 'pooled', 'per_edge')}
    for row in probe_cosines:
        z, _, _ = standing(row[eligible])
        fit = np.zeros(eligible.size)
        fit[eligible] = np.clip(z, 0., None)
        mine = fit[edge_tag]
        top, _ = best_edges(mine, edge_chunk, n_chunks)
        got = chunk_values(mine, factor, fit[eligible], edge_chunk, n_chunks)
        out['fit'].append(spearman(n_c, np.where(n_c > 0, np.nan_to_num(top), 0.)))
        out['best'].append(spearman(n_c, got['best']))
        out['pooled'].append(spearman(n_c, got['pooled']['v_star']))
        out['per_edge'].append(spearman(n_c, got['per_edge']['v_star']))
    return out


# ------------------------------------------------------------------ the walk

def random_membership(strength, layer, seed, permutations):
    """M6's two groupings on S permuted over the chunks, `permutations` times from one
    generator: per grouping how often tau2 is above 0, and each time's largest lift and number
    of lifted chunks."""
    rng = np.random.default_rng(seed)
    strength = np.asarray(strength, dtype=np.float64)
    out = {kind: {'tau2_above_0': 0, 'largest_lift': [], 'chunks_lifted': []}
           for kind in GROUPINGS}
    for _ in range(permutations):
        parts, lifts = structure_lifts(rng.permutation(strength), layer)
        for kind in GROUPINGS:
            out[kind]['tau2_above_0'] += int(bool(parts[kind]['tau2']))
            out[kind]['largest_lift'].append(float(lifts[kind].max()))
            out[kind]['chunks_lifted'].append(int((lifts[kind] > 0).sum()))
    return out


def select_examples(order, facts):
    """The example chunks, each the first chunk of the order that meets its rule and was not
    picked by an earlier rule. facts: per chunk 'winner', 'T', 'n_c', 'slack', 'near_size'
    (the chunk's near group, 0 for none), 'product'; and 'median_near_size'."""
    first = order[0]
    threshold = float(np.percentile(facts['n_c'], N_C_PERCENTILE))
    rules = [
        ('the first chunk of the order', lambda c: True),
        ('the first chunk whose winning value comes from a different query tag than chunk 1\'s',
         lambda c: facts['T'][c] > 0 and facts['winner'][c] != facts['winner'][first]),
        (f'the first chunk whose n_c is at or above the {N_C_PERCENTILE}th percentile of n_c '
         f'over the chunks ({threshold:g})', lambda c: facts['n_c'][c] >= threshold),
        ('the first Slack chunk whose near group has at most the median near-group size '
         f'({facts["median_near_size"]:g})',
         lambda c: (facts['slack'][c] and 0 < facts['near_size'][c]
                    <= facts['median_near_size'])),
        ('the first chunk with no near group', lambda c: facts['near_size'][c] == 0),
        ('the first chunk with T(c) = 0', lambda c: facts['T'][c] == 0),
        ('the first chunk under a product other than the product of chunk 1',
         lambda c: facts['product'][c] != facts['product'][first]),
    ]
    picked, out = set(), []
    for number, (text, rule) in enumerate(rules, 1):
        found = next((c for c in order if c not in picked and rule(c)), None)
        if found is not None:
            picked.add(found)
        out.append({'rule': number, 'text': text, 'chunk': found})
    return out


def _decider(a, b, run, names):
    if run['level'][a] != run['level'][b]:
        return 'level'
    if run['has_edge'][a] != run['has_edge'][b]:
        return 'winning edge present'
    for slot in range(len(ADJUST_FACETS)):
        if run['slots'][a, slot] != run['slots'][b, slot]:
            fa = names[run['facet_orders'][run['winner'][a]][slot]]
            fb = names[run['facet_orders'][run['winner'][b]][slot]]
            return f'facet slot {slot + 1} ({fa} against {fb})'
    return 'chunk id'


def _five(values):
    return [float(v) for v in np.quantile(np.asarray(values, dtype=np.float64),
                                          [0., .05, .5, .95, 1.])]


def _stat(values):
    values = [v for v in values if v is not None]
    if not values:
        return {'median': None, 'min': None, 'max': None, 'n': 0}
    return {'median': float(np.median(values)), 'min': float(min(values)),
            'max': float(max(values)), 'n': len(values)}


def _spread(values):
    values = [v for v in values if v is not None]
    if not values:
        return {'median': None, 'p05': None, 'p95': None, 'min': None, 'max': None, 'n': 0}
    low, mid, high = np.quantile(values, [.05, .5, .95])
    return {'median': float(mid), 'p05': float(low), 'p95': float(high),
            'min': float(min(values)), 'max': float(max(values)), 'n': len(values)}


def _group_rows(part, kind, names, layer, limit):
    """The groups with the largest lift: per group its largest lift over its members."""
    if part is None or not part['groups']:
        return []
    top = np.zeros(part['groups'])
    np.maximum.at(top, part['node'], part['gain'])
    value = np.where(np.isnan(part['value']), -np.inf, part['value'])
    at = np.full(part['groups'], -1, dtype=np.int64)
    for m in np.lexsort((np.arange(value.size), -value)).tolist()[::-1]:
        at[part['node'][m]] = m
    reference = np.broadcast_to(np.asarray(part['reference'], dtype=np.float64),
                                (layer['chunks'],))
    rows = []
    for g in np.lexsort((np.arange(top.size), -top))[:limit].tolist():
        m = int(at[g])
        c = int(part['chunk'][m])
        members = part['chunk'][part['node'] == g]
        products = sorted({names['product'][layer['product'][i]] for i in members.tolist()})
        rows.append({'group': (names['product'][int(part['labels'][g])] if kind == 'product'
                               else int(part['labels'][g])),
                     'n_g': int(part['size'][g]),
                     'kinds': sorted({layer['kinds'][i] for i in members.tolist()}),
                     'reference': float(reference[c]),
                     'raw': None if np.isnan(part['raw'][m]) else float(part['raw'][m]),
                     'trust': float(part['trust'][g]), 'lift': float(top[g]),
                     'chunk': layer['chunk_ids'][c], 'products': products})
    return rows


def _own_group(part, c, names, layer, kind):
    """For one chunk: the group that gives its lift in this grouping (the largest
    trust x raw), with its size, reference, raw, trust and lift."""
    if part is None:
        return None
    mine = np.flatnonzero(part['chunk'] == c)
    if not mine.size:
        return None
    m = int(part['pick'][c])
    if m < 0:
        m = int(mine[0])
    g = int(part['node'][m])
    reference = np.broadcast_to(np.asarray(part['reference'], dtype=np.float64),
                                (layer['chunks'],))
    return {'group': (names['product'][int(part['labels'][g])] if kind == 'product'
                      else int(part['labels'][g])),
            'n_g': int(part['size'][g]),
            'groups_of_the_chunk': int(mine.size),
            'sizes_of_the_chunk_groups': [int(part['size'][part['node'][i]]) for i in mine],
            'reference': float(reference[c]),
            'raw': None if np.isnan(part['raw'][m]) else float(part['raw'][m]),
            'trust': float(part['trust'][g]), 'lift': float(part['lift'][c])}


def walk(inputs):
    """Every number of the walk-through from the arrays, as plain Python values."""
    layer = build_layer(inputs)
    n, ids = layer['chunks'], layer['chunk_ids']
    eligible, tag_e, chunk_e = layer['eligible'], layer['edge_tag'], layer['edge_chunk']
    edges = int(tag_e.size)
    graph_tags = [str(t) for t in inputs['graph_tags']]
    kinds, kind_names, kind = layer['kinds'], layer['kind_names'], layer['kind']
    names = {'product': [str(p) for p in inputs['product_names']]}
    texts = [str(t) for t in inputs['query_texts']]
    lists = [str(t) for t in inputs['query_lists']]
    query = {'cosines': np.asarray(inputs['query_tag_cosines'], dtype=np.float64),
             'readings': np.asarray(inputs['query_readings'], dtype=np.float64),
             'description_cosines': np.asarray(inputs['query_tag_description_cosines'],
                                               dtype=np.float64),
             'd_description': np.asarray(inputs['d_description'], dtype=np.float64),
             'd_question': np.asarray(inputs['d_question'], dtype=np.float64)}
    noise = float(inputs['cos_noise'])
    count = len(texts)
    n_c, id_rank, near = layer['n_c'], layer['id_rank'], layer['near']
    open_tags = np.flatnonzero(eligible)

    def head(values):
        return np.lexsort((id_rank, -np.asarray(values)))[:TOP].tolist()

    def mix(rows):
        found = [kinds[c] for c in rows]
        return {'kinds': {k: found.count(k) for k in KIND_COLUMNS},
                'other': sum(k not in KIND_COLUMNS for k in found),
                'by_kind': {k: found.count(k) for k in sorted(set(found))},
                'products': len({int(layer['product'][c]) for c in rows})}

    run = chain(layer, query, noise)
    order = run['order']
    place = np.empty(n, dtype=np.int64)
    place[order] = np.arange(1, n + 1)
    top = order[:TOP]
    stages = {key: {**mix(head(run[key])), 'overlap': len(set(top) & set(head(run[key])))}
              for key, _ in STAGES}
    alt = {}
    for name, switch in ALTERNATIVES.items():
        got = chain(layer, query, noise, **switch)
        where = np.empty(n, dtype=np.int64)
        where[got['order']] = np.arange(1, n + 1)
        alt[name] = {'order': got['order'], 'place': where, 'T': got['T'],
                     'overlap': len(set(top) & set(got['order'][:TOP])),
                     'negative_T': int((got['T'] < 0).sum()),
                     'mix': mix(got['order'][:TOP])}
        if name == 'A3b':
            alt[name]['stages'] = {key: mix(head(got[key])) for key, _ in STAGES}
        if name == 'A6d':
            alt[name].update(groups=got['groups'], lift=got['lift'], S_prime=got['S_prime'])

    result = {'question': str(inputs['question']), 'description': str(inputs['description']),
              'counts': {'chunks': n, 'graph_tags': int(eligible.size),
                         'eligible_graph_tags': int(eligible.sum()),
                         'edges': int(np.asarray(inputs['edge_tag']).size),
                         'eligible_edges': edges,
                         'chunks_with_an_eligible_edge': int((n_c > 0).sum())},
              'kinds': {k: kinds.count(k) for k in kind_names},
              'constants': {'cos_noise': noise, 'middle_position': MIDDLE, 'top': TOP,
                            'shuffle_seed': SHUFFLE_SEED, 'char_budget': CHAR_BUDGET,
                            'probes': PROBES, 'permutations': PERMUTATIONS}}
    folded = [t.strip().casefold() for t in texts]
    result['query_tags'] = [{'index': i, 'text': texts[i], 'list': lists[i],
                             'readings': query['readings'][i].tolist()} for i in range(count)]
    result['query_tags_repeated_across_the_lists'] = len(folded) - len(set(folded))

    # M1
    tag_chunks = np.bincount(np.asarray(inputs['edge_tag'], dtype=np.int64),
                             minlength=eligible.size)
    m1 = []
    for i in range(count):
        row = query['cosines'][i]
        close = open_tags[np.lexsort((open_tags, -row[open_tags]))[:NEAREST]]
        m1.append({'index': i, 'text': texts[i], 'list': lists[i],
                   'bulk': float(run['bulk'][i]), 'spread': float(run['spread'][i]),
                   'eligible_tags_with_a_positive_standing': int((run['z'][i, open_tags] > 0).sum()),
                   'eligible_tags_with_a_negative_cosine': int((row[open_tags] < 0).sum()),
                   'nearest': [{'tag': graph_tags[t], 'cosine': float(row[t]),
                                'standing': float(run['z'][i, t]),
                                'chunks': int(tag_chunks[t])} for t in close.tolist()]})
    result['M1'] = {'query_tags': m1, 'A1_top_overlap': alt['A1']['overlap'],
                    'A1_chunks_with_a_negative_T': alt['A1']['negative_T']}

    # M2
    result['M2'] = {'columns': list(ALL_FACETS),
                    'raw_median': np.median(layer['raw'], axis=0).tolist(),
                    'mean_position': float(layer['pos'].mean()),
                    'median_position': np.median(layer['pos'], axis=0).tolist(),
                    'smallest_position': layer['pos'].min(axis=0).tolist(),
                    'largest_position': layer['pos'].max(axis=0).tolist()}

    # M3
    r_equal = layer['pos'].mean(axis=1)
    edge_kind, edge_n_c = kind[chunk_e], n_c[chunk_e]

    def by_kind(values):
        out = {}
        for code, label in enumerate(kind_names):
            mine = values[edge_kind == code]
            out[label] = ([float(v) for v in np.quantile(mine, [.5, .05, .95])]
                          if mine.size else None)
        return out

    m3 = []
    for i in range(count):
        m3.append({'index': i, 'text': texts[i], 'readings': query['readings'][i].tolist(),
                   'shares': run['shares'][i].tolist(),
                   'equal_shares_because_the_sum_is_0': bool(run['equal_shares'][i]),
                   'facet_order': [ADJUST_FACETS[j] for j in run['facet_orders'][i]],
                   'spearman_with_equal_shares': spearman(run['R'][i], r_equal),
                   'factor_range': _five(run['R'][i] / MIDDLE),
                   'factor_by_kind': by_kind(run['R'][i] / MIDDLE),
                   'spearman_with_n_c': spearman(run['R'][i], edge_n_c)})
    pairs = [spearman(run['R'][i], run['R'][j]) for i in range(count)
             for j in range(i + 1, count)]
    result['M3'] = {'query_tags': m3, 'pair_spearman': _stat(pairs),
                    'equal_shares_factor_range': _five(r_equal / MIDDLE),
                    'equal_shares_factor_by_kind': by_kind(r_equal / MIDDLE),
                    'edges_by_kind': {label: int((edge_kind == code).sum())
                                      for code, label in enumerate(kind_names)},
                    'position_spearman_with_n_c': {
                        f: spearman(layer['pos'][:, k], edge_n_c)
                        for k, f in enumerate(ALL_FACETS)},
                    'R_spearman_with_n_c': _stat([row['spearman_with_n_c'] for row in m3]),
                    'equal_shares_spearman_with_n_c': spearman(r_equal, edge_n_c),
                    'A3_top_overlap': alt['A3']['overlap'],
                    'A3b_top_overlap': alt['A3b']['overlap']}

    # M4
    factor = run['R'] / MIDDLE
    dependence = tag_count_dependence(run['fit'], factor, eligible, tag_e, chunk_e, n,
                                      SHUFFLE_SEED)
    table = {way: {value: _stat(dependence[way][value]) for value in VALUES} for way in WAYS}
    low, high = table['edges']['pooled']['min'], table['edges']['pooled']['max']
    inside = bool(low is not None and low <= 0. <= high)
    probes = None
    cosines = inputs.get('probe_cosines')
    if cosines is not None and np.size(cosines):
        got = probe_dependence(cosines, eligible, r_equal / MIDDLE, tag_e, chunk_e, n)
        probes = {'seed': SHUFFLE_SEED, 'probes': int(np.asarray(cosines).shape[0]),
                  'names': [str(t) for t in inputs['probe_names']],
                  'values': {key: _spread(values) for key, values in got.items()},
                  'per_probe': got}
    wins = np.bincount(run['winner'][run['T'] > 0], minlength=count)
    result['M4'] = {
        'query_tags': [{'index': i, 'text': texts[i],
                        'description_cosine': float(query['description_cosines'][i]),
                        'centrality': float(run['centrality'][i]),
                        'edges_with_w_above_0': int((run['w'][i] > 0).sum()),
                        'chunks_with_v_above_0': int((np.nan_to_num(run['v'][i]) > 0).sum()),
                        'largest_w': float(run['w'][i].max()),
                        'chunks_it_wins': int(wins[i])} for i in range(count)],
        'n_c': {'min': int(n_c.min()), 'median': float(np.median(n_c)), 'max': int(n_c.max()),
                'percentile_90': float(np.percentile(n_c, N_C_PERCENTILE))},
        'chunks_with_T_0': int((run['T'] == 0).sum()),
        'chunks_with_T_0_and_an_eligible_edge': int(((run['T'] == 0) & (n_c > 0)).sum()),
        'spearman_n_c': {'PROPOSAL': spearman(n_c, run['T']),
                         **{a: spearman(n_c, alt[a]['T'])
                            for a in ('A4a', 'A4e', 'A4b', 'A4c', 'A4d')}},
        'top_overlap': {a: alt[a]['overlap'] for a in ('A4a', 'A4e', 'A4b', 'A4c', 'A4d')},
        'dependence': {'seed': SHUFFLE_SEED, 'table': table, 'per_query_tag': dependence,
                       'reference_sd_of_spearman_between_independent_lists':
                           float(1. / np.sqrt(n - 1)),
                       'zero_inside_pooled_min_max_under_the_edge_shuffle': inside},
        'probes': probes}
    if not inside:
        raise Stop('M4 check: with each edge\'s w moved to another edge the pooled-tail '
                   f'Spearman between n_c and v* is {table["edges"]["pooled"]["median"]} '
                   f'({low} - {high}) over the query tags; 0 lies outside that range')

    # M5
    by_s = head(run['S'])
    result['M5'] = {'bulk': run['text_bulk'], 'spread': run['text_spread'],
                    'largest': {'T': float(run['T'].max()), 'D': float(run['D'].max()),
                                'Qs': float(run['Qs'].max())},
                    'smallest': {'D': float(run['D'].min()), 'Qs': float(run['Qs'].min()),
                                 'side': float(run['side'].min())},
                    'side_median': float(np.median(run['side'])),
                    'chunks_taking_Qs': int((run['Qs'] > run['D']).sum()),
                    'first_by_S_with_T_0': int(sum(run['T'][c] == 0 for c in by_s)),
                    'spearman_T_side': spearman(run['T'], run['side']),
                    'by_kind': {label: {'chunks': int((kind == code).sum()),
                                        'T': float(run['T'][kind == code].mean()),
                                        'side': float(run['side'][kind == code].mean()),
                                        'S': float(run['S'][kind == code].mean())}
                                for code, label in enumerate(kind_names)},
                    'all': {'chunks': n, 'T': float(run['T'].mean()),
                            'side': float(run['side'].mean()), 'S': float(run['S'].mean())},
                    'top_overlap': {a: alt[a]['overlap'] for a in ('A5a', 'A5b', 'A5c')}}

    # M6
    slack = np.array(['slack' in k.casefold() for k in kinds])
    channel_chunk, channel_node = layer['groups']['channel']
    in_channel = np.zeros(n, dtype=bool)
    in_channel[channel_chunk] = True
    in_near = near >= 0
    size_of = np.bincount(channel_node) if channel_node.size else np.zeros(0, np.int64)
    channel_sizes = size_of[size_of > 0]
    near_sizes = np.bincount(near[in_near]) if in_near.any() else np.zeros(0, np.int64)
    near_size = np.where(in_near, near_sizes[np.maximum(near, 0)] if near_sizes.size else 0, 0)
    product_sizes = np.bincount(layer['product'])
    product_sizes = product_sizes[product_sizes > 0]
    channel_sets, channels_of = {}, {}
    for c, g in zip(channel_chunk.tolist(), channel_node.tolist()):
        channel_sets.setdefault(g, set()).add(c)
        channels_of.setdefault(c, set()).add(g)
    near_sets = {}
    for c in np.flatnonzero(in_near).tolist():
        near_sets.setdefault(int(near[c]), set()).add(c)
    relation = {'equal_to_one_channel': [0, 0], 'holding_more_than_one_channel': [0, 0],
                'other_with_a_channel_chunk': [0, 0], 'with_no_channel_chunk': [0, 0]}
    twin = {}
    for members in near_sets.values():
        touched = set().union(*(channels_of.get(c, set()) for c in members))
        whole = [g for g in touched if channel_sets[g] <= members]
        same = [g for g in touched if channel_sets[g] == members]
        if not touched:
            key = 'with_no_channel_chunk'
        elif same:
            key = 'equal_to_one_channel'
            for c in members:
                twin[c] = same[0]
        elif len(whole) > 1:
            key = 'holding_more_than_one_channel'
        else:
            key = 'other_with_a_channel_chunk'
        relation[key][0] += 1
        relation[key][1] += len(members)
    plural = [s for s in channel_sets.values() if len(s) >= 2]
    inside_one = sum(1 for s in plural
                     if len({int(near[c]) for c in s}) == 1 and near[next(iter(s))] >= 0)
    first = alt['A6d']['groups']
    at_channel = {pair: m for m, pair in enumerate(zip(
        first['channel']['chunk'].tolist(),
        first['channel']['labels'][first['channel']['node']].tolist()))}
    at_record = {c: m for m, c in enumerate(first['record']['chunk'].tolist())}
    equal_raw = sum(bool(np.isclose(first['channel']['raw'][at_channel[(c, g)]],
                                    first['record']['raw'][at_record[c]]))
                    for c, g in twin.items())
    mixed = sum(1 for members in near_sets.values() if len({kinds[c] for c in members}) > 1)
    shuffled = random_membership(run['S'], layer, SHUFFLE_SEED, PERMUTATIONS)
    m6 = {'groupings': {}, 'largest': {}, 'random_membership': {}}
    for group in GROUPINGS:
        part = run['groups'][group]
        per_kind = None
        if part['kind_reference'] is not None:
            per_kind = {}
            for code, row in part['kind_reference'].items():
                members = in_near & (kind == code)
                per_kind[kind_names[code]] = {
                    'reference': row['reference'], 'chunks': row['chunks'],
                    'groups': int(np.unique(near[members]).size)}
        m6['groupings'][group] = {
            'groups': part['groups'], 'memberships': part['memberships'],
            'x': ('S' if group == 'product' else 'S - the mean of S over the chunk\'s product'),
            'reference': (float(part['reference']) if group == 'product' else None),
            'reference_per_kind': per_kind,
            'mean_of_x_over_the_memberships': part['grand'],
            'sigma2': part['sigma2'], 'ssb': part['ssb'],
            'sum_n_g_squared_over_m': part['sum_sq_over_m'], 'tau2': part['tau2'],
            'chunks_with_a_lift_above_0': int((part['lift'] > 0).sum()),
            'largest_lift': float(part['lift'].max())}
        m6['largest'][group] = _group_rows(part, group, names, layer, LARGEST)
        mine = shuffled[group]
        m6['random_membership'][group] = {
            'permutations': PERMUTATIONS, 'seed': SHUFFLE_SEED,
            'permutations_with_tau2_above_0': int(mine['tau2_above_0']),
            'largest_lift_median': float(np.median(mine['largest_lift'])),
            'largest_lift_99pct': float(np.quantile(mine['largest_lift'], .99)),
            'largest_lift_max': float(max(mine['largest_lift'])),
            'chunks_lifted_median': float(np.median(mine['chunks_lifted']))}
    m6['first_form'] = {group: {'groups': first[group]['groups'], 'tau2': first[group]['tau2'],
                                'sigma2': first[group]['sigma2'],
                                'chunks_with_a_lift_above_0':
                                    int((alt['A6d']['lift'][group] > 0).sum()),
                                'largest_lift': float(alt['A6d']['lift'][group].max())}
                        for group in FIRST_GROUPINGS}
    m6['first_form']['chunks_lifted_by_channel_and_record'] = int(
        ((alt['A6d']['lift']['channel'] > 0) & (alt['A6d']['lift']['record'] > 0)).sum())
    by_final, by_base = head(run['S_prime']), head(run['S'])
    m6['first'] = {name: {'slack': int(slack[rows].sum()),
                          'with_a_channel': int(in_channel[rows].sum()),
                          'with_a_near_group': int(in_near[rows].sum())}
                   for name, rows in (('S_prime', by_final), ('S', by_base))}
    m6['first_by_kind'] = {'PROPOSAL': {key: stages[key] for key, _ in STAGES},
                           'A3b': alt['A3b']['stages']}
    m6['top_overlap'] = {a: alt[a]['overlap'] for a in ('A6a', 'A6b', 'A6c', 'A6d')}
    m6['corpus'] = {
        'chunks': n, 'slack_chunks': int(slack.sum()),
        'products': int(product_sizes.size),
        'product_size_median': float(np.median(product_sizes)),
        'product_size_min': int(product_sizes.min()), 'product_size_max': int(product_sizes.max()),
        'chunks_with_a_channel': int(in_channel.sum()),
        'chunks_in_more_than_one_channel': int((np.bincount(channel_chunk, minlength=n) > 1).sum()),
        'channels': int(channel_sizes.size),
        'channel_size_median': float(np.median(channel_sizes)) if channel_sizes.size else None,
        'channel_size_min': int(channel_sizes.min()) if channel_sizes.size else None,
        'channel_size_max': int(channel_sizes.max()) if channel_sizes.size else None,
        'channels_of_one_chunk': int((channel_sizes == 1).sum()),
        'channels_of_two_or_more_chunks': len(plural),
        'of_them_whole_inside_one_near_group': int(inside_one),
        'chunks_with_a_near_group': int(in_near.sum()),
        'near_groups': int(near_sizes.size),
        'near_size_median': float(np.median(near_sizes)) if near_sizes.size else None,
        'near_size_min': int(near_sizes.min()) if near_sizes.size else None,
        'near_size_max': int(near_sizes.max()) if near_sizes.size else None,
        'near_groups_by_their_channels': {key: {'near_groups': v[0], 'chunks': v[1]}
                                          for key, v in relation.items()},
        'chunks_whose_near_group_is_one_channel': len(twin),
        'of_them_with_equal_channel_and_record_raw_under_A6d': int(equal_raw),
        'near_groups_of_more_than_one_kind': int(mixed),
        'chunks_with_a_channel_and_a_near_group': int((in_channel & in_near).sum()),
        'chunks_with_neither': int((~in_channel & ~in_near).sum()),
        'slack_chunks_with_a_near_group': int((slack & in_near).sum())}
    result['M6'] = m6

    # M7
    levels = run['level']
    deciders = [_decider(a, b, run, ADJUST_FACETS) for a, b in zip(top, top[1:])]
    plain = alt['A7']['order'][:TOP]
    result['M7'] = {'step': float(run['step']),
                    'median_spread_of_the_query_tags': float(np.median(run['spread'])),
                    'cos_noise_in_description_spreads': noise / run['text_spread']['description'],
                    'cos_noise_in_question_spreads': noise / run['text_spread']['question'],
                    'levels_of_the_first': [int(levels[c]) for c in top],
                    'adjacent_pairs_sharing_a_level': int(sum(levels[a] == levels[b]
                                                              for a, b in zip(top, top[1:]))),
                    'adjacent_pairs': len(deciders), 'deciders': deciders,
                    'levels_in_all': int(np.unique(levels).size),
                    'largest_level': int(levels.max()),
                    'chunks_sharing_their_level': int((np.bincount(levels)[levels] > 1).sum()),
                    'A7_top_overlap': alt['A7']['overlap'],
                    'A7_positions_that_differ_among_the_first': int(
                        sum(a != b for a, b in zip(top, plain))),
                    'A7_positions_that_differ_in_all': int(
                        sum(a != b for a, b in zip(order, alt['A7']['order'])))}

    # the examples and the first rows
    facts = {'winner': run['winner'], 'T': run['T'], 'n_c': n_c, 'slack': slack,
             'near_size': near_size, 'product': layer['product'],
             'median_near_size': float(np.median(near_sizes)) if near_sizes.size else 0.}

    def detail(c):
        q, e = int(run['winner'][c]), int(run['win_edge'][c])
        row = {'chunk': ids[c], 'kind': kinds[c],
               'product': names['product'][layer['product'][c]], 'n_c': int(n_c[c]),
               'channels': int((channel_chunk == c).sum()),
               'channel_sizes': sorted(int(size_of[g]) for g in channel_node[channel_chunk == c])
               if channel_chunk.size else [],
               'near_group_size': int(near_size[c]) if in_near[c] else None}
        if e >= 0:
            t = int(tag_e[e])
            row.update({
                'winning_query_tag': {'index': q, 'text': texts[q], 'list': lists[q]},
                'winning_graph_tag': graph_tags[t], 'graph_tag_chunks': int(tag_chunks[t]),
                'cos': float(query['cosines'][q, t]), 'b_q': float(run['bulk'][q]),
                's_q': float(run['spread'][q]), 'standing': float(run['z'][q, t]),
                'fit': float(run['fit'][q, t]),
                'raw': dict(zip(ALL_FACETS, layer['raw'][e].tolist())),
                'pos': dict(zip(ALL_FACETS, layer['pos'][e].tolist())),
                'readings': dict(zip(ALL_FACETS, query['readings'][q].tolist())),
                'shares': dict(zip(ALL_FACETS, run['shares'][q].tolist())),
                'facet_order': [ADJUST_FACETS[j] for j in run['facet_orders'][q]],
                'R': float(run['R'][q, e]), 'factor': float(run['R'][q, e] / MIDDLE),
                'w': float(run['w'][q, e]), 'v': float(run['v'][q, c]),
                'centrality': float(run['centrality'][q]),
                'pooled_tail': {'edges_at_or_above_v': int(run['count'][q, c]),
                                'tail': float(run['tail'][q, c]), 'p': float(run['p'][q, c]),
                                'k': int(run['k'][q, c]), 'v_star': float(run['v_star'][q, c])},
                'per_edge': {'p': float(run['pe_p'][q, c]), 'k': int(run['pe_k'][q, c]),
                             'v_star': float(run['pe_v_star'][q, c])}})
        row.update({'T': float(run['T'][c]), 'D': float(run['D'][c]), 'Qs': float(run['Qs'][c]),
                    'side': float(run['side'][c]), 'S': float(run['S'][c]),
                    'lifts': {group: _own_group(run['groups'][group], c, names, layer, group)
                              for group in GROUPINGS},
                    'lift': {group: float(run['lift'][group][c]) for group in GROUPINGS},
                    'S_prime': float(run['S_prime'][c]), 'level': int(levels[c]),
                    'position': int(place[c]),
                    'first_form': {'lift': {group: float(alt['A6d']['lift'][group][c])
                                            for group in FIRST_GROUPINGS},
                                   'S_prime': float(alt['A6d']['S_prime'][c])},
                    'position_under': {a: int(alt[a]['place'][c]) for a in ALTERNATIVES}})
        return row

    picks = select_examples(order, facts)
    result['examples'] = [{'rule': p['rule'], 'text': p['text'],
                           'detail': None if p['chunk'] is None else detail(p['chunk'])}
                          for p in picks]
    result['first'] = [{'position': i + 1, 'chunk': ids[c], 'kind': kinds[c],
                        'product': names['product'][layer['product'][c]], 'n_c': int(n_c[c]),
                        'winning_query_tag': int(run['winner'][c]),
                        'T': float(run['T'][c]), 'side': float(run['side'][c]),
                        'lift': {group: float(run['lift'][group][c]) for group in GROUPINGS},
                        'S_prime': float(run['S_prime'][c]), 'level': int(levels[c])}
                       for i, c in enumerate(top)]
    result['first_mix'] = {'PROPOSAL': {**mix(top), 'overlap': TOP},
                           'stages': {key: stages[key] for key, _ in STAGES}}
    result['alternatives'] = {a: {'switch': ALTERNATIVES[a], 'text': ALTERNATIVE_TEXT[a],
                                  'top_overlap': alt[a]['overlap'], 'mix': alt[a]['mix'],
                                  'first': [ids[c] for c in alt[a]['order'][:TOP]]}
                              for a in ALTERNATIVES}
    result['per_chunk'] = {
        'chunk': ids, 'kind': kinds, 'n_c': n_c.tolist(), 'winner': run['winner'].tolist(),
        'T': run['T'].tolist(), 'D': run['D'].tolist(), 'Qs': run['Qs'].tolist(),
        'side': run['side'].tolist(), 'S': run['S'].tolist(),
        **{'lift_' + group: run['lift'][group].tolist() for group in GROUPINGS},
        'S_prime': run['S_prime'].tolist(), 'level': levels.tolist(), 'position': place.tolist()}
    result['order'] = [ids[c] for c in order]
    return result, order


# ------------------------------------------------------------------ the print

def _f(value, digits=4):
    if value is None:
        return '-'
    return f'{value:.{digits}f}'


def _e(value):
    return '-' if value is None else f'{value:.3e}'


def _span(stat, digits=4):
    return f'{_f(stat["median"], digits)} ({_f(stat["min"], digits)} - {_f(stat["max"], digits)})'


def _table(head, rows, left=()):
    cells = [[str(c) for c in head]] + [[str(c) for c in row] for row in rows]
    width = [max(len(r[i]) for r in cells) for i in range(len(head))]
    out = []
    for r in cells:
        out.append('  ' + '  '.join(r[i].ljust(width[i]) if i in left else r[i].rjust(width[i])
                                     for i in range(len(head))).rstrip())
    return out


def _mix_cells(row):
    return [row['kinds'][k] for k in KIND_COLUMNS] + [row['other'], row['products']]


MIX_HEAD = list(KIND_COLUMNS) + ['other', 'products']


def render(result, provenance):
    """The walk-through as lines of text: names and numbers."""
    c, m1, m2, m3 = result['counts'], result['M1'], result['M2'], result['M3']
    m4, m5, m6, m7 = result['M4'], result['M5'], result['M6'], result['M7']
    tags = result['query_tags']
    edges = c['eligible_edges']
    usage = provenance['usage']
    kind_names = list(result['kinds'])
    out = [f'WALK-THROUGH {provenance["stamp"]}', '',
           'Every PROPOSAL below is the orchestrator\'s calculation. ALT = the alternative '
           'printed beside it.',
           'Each alternative is the whole chain with that one step exchanged; every order is '
           f'over all {c["chunks"]:,} chunks.',
           f'"top-{TOP} overlap" = the chunks common to the first {TOP} of the final order '
           f'under the alternative and the first {TOP} of the final PROPOSAL order.',
           '',
           'QUESTION (made up, from no question set)', '  ' + result['question'], '',
           f'QUERYTAGGER ({provenance["interpreter_model"]}, artefact_v4._interpret)',
           f'  model calls {usage["calls"]}; cache hit {provenance["cache_hit"]}; asks '
           f'{provenance["asks"]}; tokens in {usage["tokens_in"]:,} (cached input '
           f'{usage["cached_input_tokens"]:,}), out {usage["tokens_out"]:,}',
           f'  cache key {provenance["cache_key"]}']
    if provenance.get('saved_usage') is not None:
        saved = provenance['saved_usage']
        out.append(f'  the cached answer\'s own call: tokens in {saved.get("prompt_tokens")}, '
                   f'out {saved.get("completion_tokens")}')
    if provenance.get('stand_in'):
        out.append('  STAND-IN INTERPRETATION, NOT THE QUERYTAGGER\'S: ' + provenance['stand_in'])
    out += ['  description: ' + result['description'], '  query tags, readings in the order '
            + ', '.join(ALL_FACETS) + ':']
    out += _table(['q', 'list', 'query tag'] + list(ALL_FACETS),
                  [[t['index'], t['list'], t['text']] + [_f(v, 2) for v in t['readings']]
                   for t in tags], left=(1, 2))
    out.append('  phrases standing in both lists: '
               f'{result["query_tags_repeated_across_the_lists"]}')
    roles = provenance.get('roles')
    if roles is not None:
        out += ['', 'EMBEDDING ROLES (artefact_v4.walk_roles; HERB_V4_WALK_TAGROLE, '
                'HERB_V4_WALK_DESCROLE, HERB_V4_WALK_QUESTROLE)',
                f'  query tags against graph tags: {roles["tags"]} | query description against '
                f'chunk descriptions: {roles["description"]} | raw question against chunk '
                f'descriptions: {roles["question"]} | query tag against query description '
                f'(centrality): {roles["centrality"]}']
    out += ['', 'COUNTS (artefact_v4.prepare_over_corpus)',
            f'  chunks {c["chunks"]:,} | graph tags {c["graph_tags"]:,} | eligible graph tags '
            f'{c["eligible_graph_tags"]:,} | edges {c["edges"]:,} | eligible edges (E) '
            f'{edges:,}',
            '  the spec\'s ' + ' / '.join(f'{SPEC_COUNTS[k]:,}' for k in SPEC_COUNTS)
            + ' (chunks / graph tags / eligible graph tags / eligible edges): '
            + ('match' if all(c[k] == v for k, v in SPEC_COUNTS.items()) else 'DIFFER'),
            f'  chunks with at least one eligible edge: {c["chunks_with_an_eligible_edge"]:,}',
            '  record kinds: ' + ', '.join(f'{k} {v:,}' for k, v in result['kinds'].items()),
            '',
            'Notation: q a query tag; t a graph tag; e = (t, c) an eligible edge; c a chunk; '
            f'n = {c["chunks"]:,} chunks; |E| = {edges:,}; N = {c["eligible_graph_tags"]:,} '
            'eligible graph tags.', '']

    out += ['=' * 100, 'M1 - closeness into a weight', '=' * 100,
            'PROPOSAL: over the eligible graph tags, b_q = median of cos_q, s_q = 1.4826 x '
            'median |cos_q - b_q|;',
            '          standing z_q(t) = (cos_q(t) - b_q) / s_q; fit_q(t) = max(z_q(t), 0).',
            'ALT A1:   the raw cosine cos_q(t) as the fit.', '']
    for t in m1['query_tags']:
        out.append(f'  q{t["index"]} "{t["text"]}" ({t["list"]}): b_q {_f(t["bulk"])}, s_q '
                   f'{_f(t["spread"])}; eligible graph tags with z > 0: '
                   f'{t["eligible_tags_with_a_positive_standing"]:,}; with cos < 0: '
                   f'{t["eligible_tags_with_a_negative_cosine"]:,}')
        out += ['    ' + line for line in _table(
            ['nearest eligible graph tag', 'cos (A1 fit)', 'standing (PROPOSAL fit)', 'chunks'],
            [[r['tag'], _f(r['cosine']), _f(r['standing'], 3), r['chunks']]
             for r in t['nearest']], left=(0,))]
    out += ['', f'  top-{TOP} overlap of A1 with the PROPOSAL: {m1["A1_top_overlap"]} of {TOP}',
            '  as computed under A1: every later step as written, the step of M7 included; '
            f'chunks with T < 0 under A1: {m1["A1_chunks_with_a_negative_T"]:,}', '']

    out += ['=' * 100, 'M2 - the edge\'s five values on one scale', '=' * 100,
            'PROPOSAL: for each of the five columns over E (topic = cos(tag, chunk description); '
            'temporal, why, activity,',
            '          concreteness = the edge\'s mean head score over the 24 refits) pos_k(e) = '
            '(average rank, ties sharing,',
            '          ascending so the largest value has the largest rank) / |E|, in (0, 1].',
            '']
    out += _table(['column', 'median raw value', 'median pos', 'smallest pos', 'largest pos'],
                  [[f, _f(m2['raw_median'][k]), _f(m2['median_position'][k], 6),
                    _f(m2['smallest_position'][k], 6), _f(m2['largest_position'][k], 6)]
                   for k, f in enumerate(ALL_FACETS)], left=(0,))
    out += [f'  as computed: scipy.stats.rankdata(method="average") / |E|; the mean position '
            f'of every column is (|E| + 1) / (2 |E|) = {_f(m2["mean_position"], 6)}',
            '  the raw values and positions of single edges: under EXAMPLES below', '']

    out += ['=' * 100, 'M3 - the query tag\'s five readings meet the edge\'s five values',
            '=' * 100,
            'PROPOSAL: share_q = readings_q / sum(readings_q) (five equal shares if the sum is 0);',
            '          R_q(e) = sum_k share_q[k] x pos_k(e); w_q(e) = fit_q(t) x R_q(e) / 0.5.',
            'ALT A3:   five equal shares (R_eq), same form.',
            'ALT A3b:  no facet adjust at all: w_q(e) = fit_q(t) (factor 1).', '',
            '  readings and shares in the order ' + ', '.join(ALL_FACETS) + '; facet order = '
            'artefact.v4_multikey.facet_order(readings); factor = R_q / 0.5 over E']
    out += _table(['q', 'readings', 'shares', 'facet order', 'Spearman(R_q, R_eq)',
                   'factor min', '5%', 'median', '95%', 'max'],
                  [[t['index'], ' '.join(_f(r, 2) for r in t['readings']),
                    ' '.join(_f(s, 3) for s in t['shares'])
                    + (' (sum 0)' if t['equal_shares_because_the_sum_is_0'] else ''),
                    ' > '.join(t['facet_order']), _f(t['spearman_with_equal_shares']),
                    *[_f(v, 3) for v in t['factor_range']]] for t in m3['query_tags']],
                  left=(1, 2, 3))
    pair = m3['pair_spearman']
    out += ['  equal shares (A3): factor R_eq / 0.5 over E: min, 5%, median, 95%, max = '
            + ', '.join(_f(v, 3) for v in m3['equal_shares_factor_range']),
            f'  Spearman over E between R_q and R_q\', all {pair["n"]} query-tag pairs: median '
            f'{_f(pair["median"])} (min {_f(pair["min"])} - max {_f(pair["max"])})', '',
            '  the factor R_q / 0.5 over the eligible edges, by the record kind of the edge\'s '
            'chunk: median (5% - 95%)']

    def cell(triple):
        if triple is None:
            return '-'
        return f'{_f(triple[0], 3)} ({_f(triple[1], 3)} - {_f(triple[2], 3)})'

    half = (len(kind_names) + 1) // 2
    for part in (kind_names[:half], kind_names[half:]):
        if not part:
            continue
        out += _table([''] + part,
                      [['edges'] + [f'{m3["edges_by_kind"][k]:,}' for k in part]]
                      + [[f'q{t["index"]}'] + [cell(t['factor_by_kind'][k]) for k in part]
                         for t in m3['query_tags']]
                      + [['R_eq'] + [cell(m3['equal_shares_factor_by_kind'][k]) for k in part]],
                      left=(0,))
    with_n = m3['R_spearman_with_n_c']
    out += ['', '  Spearman over E between a position column and the tag count n_c of the '
            'edge\'s chunk: '
            + '; '.join(f'{f} {_f(v)}' for f, v in m3['position_spearman_with_n_c'].items()),
            f'  the same for R_q: median {_f(with_n["median"])} (min {_f(with_n["min"])} - max '
            f'{_f(with_n["max"])}) over the query tags; for R_eq: '
            f'{_f(m3["equal_shares_spearman_with_n_c"])}',
            f'  top-{TOP} overlap with the PROPOSAL: A3 {m3["A3_top_overlap"]} of {TOP}; A3b '
            f'{m3["A3b_top_overlap"]} of {TOP}', '']

    out += ['=' * 100, 'M4 - what a chunk takes from its tags; the tag count; the query tags',
            '=' * 100,
            'PROPOSAL: per query tag q and chunk c with n_c >= 1 eligible edges: v_q(c) = max '
            'over c\'s eligible edges of w_q(e);',
            '          no correction for n_c. Chunks with no eligible edge: 0.',
            '          centrality_q = max(cos(q, query description), 0) / the largest such over '
            'the question\'s query tags;',
            '          T(c) = max over q of centrality_q x v_q(c).',
            'ALT A4a (pooled tail): tail_q(v) = (number of eligible edges e\' with w_q(e\') >= v) '
            '/ |E|; p = 1 - (1 - tail_q(v_q(c)))^n_c;',
            '          v*_q(c) = the k-th largest w_q over E, k = ceil(p x |E|) clipped to '
            '[1, |E|]; v* in place of v.',
            'ALT A4e (per edge): p_c = 1 - product over c\'s eligible edges i of (1 - '
            'G_q(v_q(c) / factor_i)), factor_i = R_q(i) / 0.5,',
            '          G_q(x) = (number of eligible graph tags t with fit_q(t) >= x) / N; '
            'v*_q(c) = the k-th largest fit_q over the eligible',
            '          graph tags, k = ceil(p_c x N) clipped to [1, N]: the fit a single middle '
            'edge would need; v* in place of v.',
            '          For n_c = 1 this returns fit, not fit x factor.',
            'ALT A4b:  per query tag the SUM of w_q over c\'s edges, then the same max over q.',
            'ALT A4c:  all query tags equal (centrality 1).',
            'ALT A4d:  SUM over q of centrality_q x v_q(c).', '']
    out += _table(['q', 'query tag', 'cos(q, description)', 'centrality', 'edges with w > 0',
                   'largest w', 'chunks with v > 0', 'chunks whose T it gives'],
                  [[t['index'], t['text'], _f(t['description_cosine']), _f(t['centrality']),
                    f'{t["edges_with_w_above_0"]:,}', _f(t['largest_w'], 3),
                    f'{t["chunks_with_v_above_0"]:,}', f'{t["chunks_it_wins"]:,}']
                   for t in m4['query_tags']], left=(1,))
    nc = m4['n_c']
    out += [f'  n_c over the chunks: min {nc["min"]}, median {nc["median"]:g}, 90th percentile '
            f'{nc["percentile_90"]:g}, max {nc["max"]}',
            f'  chunks with T = 0: {m4["chunks_with_T_0"]:,} (of them with at least one '
            f'eligible edge: {m4["chunks_with_T_0_and_an_eligible_edge"]:,})', '',
            f'  Spearman over the chunks between n_c and T; top-{TOP} overlap with the '
            'PROPOSAL:']
    out += _table(['', 'Spearman(n_c, T)', f'top-{TOP} overlap'],
                  [['PROPOSAL', _f(m4['spearman_n_c']['PROPOSAL']), f'{TOP} of {TOP}']]
                  + [[f'{a}: {ALTERNATIVE_TEXT[a]}', _f(m4['spearman_n_c'][a]),
                      f'{m4["top_overlap"][a]} of {TOP}']
                     for a in ('A4a', 'A4e', 'A4b', 'A4c', 'A4d')], left=(0,))
    dep = m4['dependence']
    label = {'best': 'PROPOSAL: v', 'pooled': 'A4a pooled tail: v*',
             'per_edge': 'A4e per edge: v*', 'total': 'A4b: the sum of w over the edges'}
    out += ['', '  Spearman over the chunks between n_c and the per-query-tag value, median '
            '(min - max) over the query tags, three ways',
            f'  (numpy default_rng({dep["seed"]}) for each shuffle, one permutation per query '
            'tag in the order above):']
    out += _table(['', 'observed', 'w shuffled over the edges',
                   'the fits shuffled over the tags'],
                  [[label[value]] + [_span(dep['table'][way][value]) for way in WAYS]
                   for value in VALUES], left=(0,))
    out += ['  w shuffled over the edges: each edge\'s fit and factor moved together to another '
            'edge; the fits shuffled over the tags:',
            '  each eligible tag takes another eligible tag\'s fit, every edge keeps its own '
            'factor.',
            '  1 / sqrt(n - 1), the standard deviation of a Spearman coefficient between two '
            'independent lists of n: '
            f'{_f(dep["reference_sd_of_spearman_between_independent_lists"])}',
            '  the stop rule as coded: stop when 0 lies outside the (min - max) of A4a with w '
            'shuffled over the edges; 0 inside: '
            f'{"yes" if dep["zero_inside_pooled_min_max_under_the_edge_shuffle"] else "NO"}', '']
    probes = m4['probes']
    if probes is None:
        out += ['  PROBES: not computed in this run', '']
    else:
        name = {'fit': '(i) the chunk\'s best fit (factor 1)',
                'best': '(ii) the chunk\'s best w (PROPOSAL)',
                'pooled': '(iii) A4a pooled tail: v*', 'per_edge': '(iv) A4e per edge: v*'}
        out += [f'  PROBES: {probes["probes"]} eligible graph tag names (numpy '
                f'default_rng({probes["seed"]}), without replacement; readable form as '
                'graph.db._readable),',
                f'  embedded in the {(roles or {}).get("tags", "query")} role '
                '(artefact_v4._query_cosines), each used as a query tag with five equal shares.',
                '  Spearman over the chunks between n_c and the probe\'s value per chunk, over '
                'the probes:']
        out += _table(['', 'median', '5%', '95%', 'min', 'max'],
                      [[name[key], _f(v['median']), _f(v['p05']), _f(v['p95']), _f(v['min']),
                        _f(v['max'])] for key, v in probes['values'].items()], left=(0,))
        out.append('')
    out += ['  as computed: A4a: k in whole numbers, |E| - floor((|E| - K)^n_c / |E|^(n_c - 1)), '
            'K the number of eligible edges with w_q >= v.',
            '               A4e: K_i = the number of eligible graph tags t with fit_q(t) x '
            'factor_i >= v (the product, so the edge\'s own tag counts);',
            '               k in whole numbers, N - floor(product_i (N - K_i) / N^(n_c - 1)).',
            '               The winning query tag of a chunk: the one with the largest '
            'centrality_q x v_q(c), the earlier query tag on an exact tie.',
            '               Its winning edge: that query tag\'s edge of the chunk with the '
            'largest w_q, the earlier edge on an exact tie.',
            '               A chunk with T = 0 and an eligible edge has no value above 0 from '
            'any pair; the same two rules give it q0 and q0\'s edge.',
            '               A4b and A4d: the tie-break of M7 reads the pair the same two rules '
            'give (the largest term; that query tag\'s edge with the largest w_q).', '']

    out += ['=' * 100, 'M5 - the description joins', '=' * 100,
            'PROPOSAL: D(c) = standing of cos(query description, chunk description) over the n '
            'chunks (median, 1.4826 x MAD, not clipped);',
            '          Qs(c) the same for cos(raw question, chunk description); side(c) = '
            'max(D(c), Qs(c)); S(c) = T(c) + side(c).',
            'ALT A5a:  S = T alone.   ALT A5b: side = D alone.   ALT A5c: side clipped at 0.', '',
            f'  query description: bulk {_f(m5["bulk"]["description"])}, spread '
            f'{_f(m5["spread"]["description"])}; raw question: bulk '
            f'{_f(m5["bulk"]["question"])}, spread {_f(m5["spread"]["question"])}',
            f'  largest T {_f(m5["largest"]["T"], 3)}; largest D {_f(m5["largest"]["D"], 3)}; '
            f'largest Qs {_f(m5["largest"]["Qs"], 3)}',
            f'  smallest D {_f(m5["smallest"]["D"], 3)}; smallest Qs '
            f'{_f(m5["smallest"]["Qs"], 3)}; smallest side {_f(m5["smallest"]["side"], 3)}; '
            f'median side {_f(m5["side_median"], 3)}; chunks where Qs > D: '
            f'{m5["chunks_taking_Qs"]:,}',
            f'  of the first {TOP} by S (descending, chunk id on an exact tie), with T = 0: '
            f'{m5["first_by_S_with_T_0"]}',
            f'  Spearman over the chunks between T and side: {_f(m5["spearman_T_side"])}',
            '  the mean of T, of side and of S by record kind:']
    out += _table(['record kind', 'chunks', 'mean T', 'mean side', 'mean S'],
                  [[k, f'{v["chunks"]:,}', _f(v['T'], 3), _f(v['side'], 3), _f(v['S'], 3)]
                   for k, v in m5['by_kind'].items()]
                  + [['all chunks', f'{m5["all"]["chunks"]:,}', _f(m5['all']['T'], 3),
                      _f(m5['all']['side'], 3), _f(m5['all']['S'], 3)]], left=(0,))
    out += [f'  top-{TOP} overlap with the PROPOSAL: '
            + '; '.join(f'{a} {m5["top_overlap"][a]} of {TOP}' for a in ('A5a', 'A5b', 'A5c')),
            '']

    co = m6['corpus']
    rel = co['near_groups_by_their_channels']
    out += ['=' * 100, 'M6 - the structure strengthens, never lowers, never removes',
            '=' * 100,
            'Groups: (P) product, a partition of the chunks; (N) the near group: the connected '
            'components of the file-adjacency graph,',
            '        singletons having no group.',
            f'The channel is not a grouping of its own. Of the {co["near_groups"]:,} near '
            'groups: '
            + '; '.join(f'{text} {rel[key]["near_groups"]:,} ({rel[key]["chunks"]:,} chunks)'
                        for key, text in (
                            ('equal_to_one_channel', 'the same members as one channel'),
                            ('holding_more_than_one_channel', 'holding more than one whole channel'),
                            ('other_with_a_channel_chunk', 'other, with a channel chunk'),
                            ('with_no_channel_chunk', 'with no channel chunk'))) + '.',
            f'  Channels of two or more chunks: {co["channels_of_two_or_more_chunks"]:,}; of '
            f'them whole inside one near group: {co["of_them_whole_inside_one_near_group"]:,}.',
            '  Under A6d the channel\'s raw and the record\'s raw are equal on '
            f'{co["of_them_with_equal_channel_and_record_raw_under_A6d"]:,} of the '
            f'{co["chunks_whose_near_group_is_one_channel"]:,} chunks whose near group has one '
            'channel\'s members.',
            'PROPOSAL: PRODUCT: x = S; reference = mean of S over all chunks.',
            '          NEAR: x = S - (mean of S over the chunk\'s product); reference(c) = the '
            'mean of x over all chunks of c\'s record kind',
            '                that sit in a near group (one number per kind).',
            '          others(c, g) = mean of x over the members of g other than c; raw(c, g) = '
            'others(c, g) - reference(c)',
            '          sigma2 = pooled within-group variance; tau2 = max(0, (SSB - (G - 1) x '
            'sigma2) / (M - sum n_g^2 / M)), SSB = sum_g n_g x',
            '                   (mean_g - mean)^2, G groups, M memberships; for NEAR both on x '
            'minus its kind reference',
            '          trust(g) = tau2 / (tau2 + sigma2 / (n_g - 1)); lift(c, g) = max(0, '
            'trust(g) x raw(c, g))',
            '          S\'(c) = S(c) + lift_P(c) + lift_N(c).',
            'ALT A6a:  S\' = S (no structure).   ALT A6b: trust = 1 everywhere.   ALT A6c: NEAR '
            'with reference 0.',
            'ALT A6d:  product, channel and record (= near group) as three groupings; channel '
            'and record on x with reference 0, a chunk in',
            '          several channels taking its largest; tau2 = max(0, variance of the group '
            'means (weighted by n_g) - groups x sigma2 /',
            '          memberships); S\' = S + lift_P + lift_C + lift_R.', '']
    out += [f'  corpus: {co["products"]} products (chunks per product: median '
            f'{co["product_size_median"]:g}, {co["product_size_min"]} - '
            f'{co["product_size_max"]});',
            f'          chunks with a channel {co["chunks_with_a_channel"]:,} (in more than one: '
            f'{co["chunks_in_more_than_one_channel"]:,}); channels {co["channels"]:,} (chunks '
            f'per channel: median {_f(co["channel_size_median"], 1)}, '
            f'{co["channel_size_min"]} - {co["channel_size_max"]}; channels of one chunk: '
            f'{co["channels_of_one_chunk"]:,});',
            f'          chunks with a near group {co["chunks_with_a_near_group"]:,}; near '
            f'groups {co["near_groups"]:,} (chunks per near group: median '
            f'{_f(co["near_size_median"], 1)}, {co["near_size_min"]} - '
            f'{co["near_size_max"]}); near groups holding more than one record kind: '
            f'{co["near_groups_of_more_than_one_kind"]:,};',
            f'          Slack chunks {co["slack_chunks"]:,} (with a near group: '
            f'{co["slack_chunks_with_a_near_group"]:,}); chunks with a channel and a near '
            f'group {co["chunks_with_a_channel_and_a_near_group"]:,}; with neither '
            f'{co["chunks_with_neither"]:,}', '']
    for group, g in m6['groupings'].items():
        out.append(f'  {group}: {g["groups"]:,} groups (G), {g["memberships"]:,} memberships '
                   f'(M); x = {g["x"]}'
                   + (f'; reference {_f(g["reference"])}' if g['reference'] is not None else ''))
        if g['reference_per_kind'] is not None:
            out.append('    reference per record kind: '
                       + '; '.join(f'{k} {_f(v["reference"])} ({v["groups"]:,} groups, '
                                   f'{v["chunks"]:,} chunks)'
                                   for k, v in g['reference_per_kind'].items()))
        out += [f'    sigma2 {_f(g["sigma2"])}; SSB {_f(g["ssb"], 2)}; sum n_g^2 / M '
                f'{_f(g["sum_n_g_squared_over_m"], 2)}; tau2 {_f(g["tau2"])}',
                f'    chunks with a lift above 0: {g["chunks_with_a_lift_above_0"]:,}; largest '
                f'lift {_f(g["largest_lift"], 3)}']
    out.append('')
    for group, text in (('product', 'products'), ('near', 'near groups')):
        out.append(f'  the {LARGEST} {text} with the largest lift (a group\'s lift = its '
                   'largest over its members; raw of that member):')
        if group == 'product':
            out += ['  ' + line for line in _table(
                ['product', 'n_g', 'raw', 'trust', 'lift', 'chunk with that lift'],
                [[r['group'], r['n_g'], _f(r['raw'], 3), _f(r['trust']), _f(r['lift'], 3),
                  r['chunk']] for r in m6['largest'][group]], left=(0, 5))]
        else:
            out += ['  ' + line for line in _table(
                ['near group', 'size', 'record kind', 'reference', 'raw', 'trust', 'lift',
                 'product', 'chunk with that lift'],
                [[f'#{r["group"]}', r['n_g'], ', '.join(r['kinds']), _f(r['reference'], 3),
                  _f(r['raw'], 3), _f(r['trust']), _f(r['lift'], 3), ', '.join(r['products']),
                  r['chunk']] for r in m6['largest'][group]], left=(0, 2, 7, 8))]
    some = next(iter(m6['random_membership'].values()))
    out += ['', f'  S permuted over the chunks, {some["permutations"]} permutations (numpy '
            f'default_rng({some["seed"]})), M6 recomputed each time, beside the unpermuted S:']
    out += _table(['grouping', 'permutations with tau2 > 0', 'largest lift: median', '99%',
                   'max', 'chunks lifted: median', 'unpermuted: tau2', 'largest lift',
                   'chunks lifted'],
                  [[group, f'{v["permutations_with_tau2_above_0"]} of {v["permutations"]}',
                    _f(v['largest_lift_median'], 3), _f(v['largest_lift_99pct'], 3),
                    _f(v['largest_lift_max'], 3), f'{v["chunks_lifted_median"]:g}',
                    _f(m6['groupings'][group]['tau2']),
                    _f(m6['groupings'][group]['largest_lift'], 3),
                    f'{m6["groupings"][group]["chunks_with_a_lift_above_0"]:,}']
                   for group, v in m6['random_membership'].items()], left=(0,))
    ff = m6['first_form']
    out += ['', '  A6d on the same S: '
            + '; '.join(f'{group}: tau2 {_f(ff[group]["tau2"])}, chunks lifted '
                        f'{ff[group]["chunks_with_a_lift_above_0"]:,}, largest lift '
                        f'{_f(ff[group]["largest_lift"], 3)}' for group in FIRST_GROUPINGS)
            + f'; chunks lifted by channel and by record: '
            f'{ff["chunks_lifted_by_channel_and_record"]:,}',
            '', f'  among the first {TOP} (descending, chunk id on an exact tie):']
    out += _table(['by', 'Slack chunks', 'with a channel', 'with a near group'],
                  [[name.replace('S_prime', 'S\''), v['slack'], v['with_a_channel'],
                    v['with_a_near_group']] for name, v in m6['first'].items()], left=(0,))
    out.append(f'  the first {TOP} by record kind and the number of distinct products among '
               'them, by T alone, by S, by S\' (descending, chunk id on an exact tie):')
    out += _table(['', 'by'] + MIX_HEAD,
                  [[who, text] + _mix_cells(m6['first_by_kind'][who][key])
                   for who in ('PROPOSAL', 'A3b') for key, text in STAGES], left=(0, 1))
    out += [f'  top-{TOP} overlap with the PROPOSAL: '
            + '; '.join(f'{a} {m6["top_overlap"][a]} of {TOP}'
                        for a in ('A6a', 'A6b', 'A6c', 'A6d')),
            '  as computed: the per-kind reference and both variances are taken again on the '
            'S of each alternative and of each permutation;',
            '               under A6c sigma2 and tau2 of NEAR are taken on x itself.', '']

    out += ['=' * 100, 'M7 - equal, and what breaks a tie', '=' * 100,
            'PROPOSAL: step = COS_NOISE / median over the question\'s query tags of s_q; '
            'level(c) = floor((max S\' - S\'(c)) / step).',
            '          Order: level; inside a level the chunks that have a winning edge first, '
            'by the positions pos_k of the winning edge',
            '          for temporal, why, activity, concreteness in the order '
            'facet_order(readings of the winning query tag), descending;',
            '          then chunk id.',
            'ALT A7:   no levels: the order is S\' descending, chunk id on exact ties.', '',
            f'  COS_NOISE {result["constants"]["cos_noise"]} (artefact_v4.COS_NOISE); median '
            f's_q {_f(m7["median_spread_of_the_query_tags"])}; step {_f(m7["step"])}',
            f'  the same COS_NOISE over the spread of the query description list: '
            f'{_f(m7["cos_noise_in_description_spreads"])}; of the raw question list: '
            f'{_f(m7["cos_noise_in_question_spreads"])}',
            f'  levels over all chunks: {m7["levels_in_all"]:,} distinct, the deepest '
            f'{m7["largest_level"]:,}; chunks sharing their level with another chunk: '
            f'{m7["chunks_sharing_their_level"]:,}',
            f'  levels of the first {TOP}: ' + ' '.join(str(v) for v in m7['levels_of_the_first']),
            f'  adjacent pairs among the first {TOP} sharing a level: '
            f'{m7["adjacent_pairs_sharing_a_level"]} of {m7["adjacent_pairs"]}',
            '  the key that decided each adjacent pair (positions 1-2, 2-3, ...): '
            + '; '.join(m7['deciders']),
            f'  A7: top-{TOP} overlap with the PROPOSAL {m7["A7_top_overlap"]} of {TOP}; '
            f'positions among the first {TOP} holding another chunk: '
            f'{m7["A7_positions_that_differ_among_the_first"]}; over all '
            f'{c["chunks"]:,} positions: {m7["A7_positions_that_differ_in_all"]:,}',
            '  as computed: a chunk has a winning edge when it has an eligible edge.', '']

    out += ['=' * 100, 'EXAMPLES - picked by rule from the PROPOSAL order (first match in the '
            'order; one already picked is skipped)', '=' * 100]
    for ex in result['examples']:
        out.append(f'RULE {ex["rule"]}: {ex["text"]}')
        d = ex['detail']
        if d is None:
            out += ['  no chunk meets this rule', '']
            continue
        out.append(f'  chunk {d["chunk"]} | kind {d["kind"]} | product {d["product"]} | n_c '
                   f'{d["n_c"]} | channels {d["channels"]} (sizes '
                   f'{", ".join(str(s) for s in d["channel_sizes"]) or "-"}) | near group size '
                   f'{d["near_group_size"] if d["near_group_size"] is not None else "-"}')
        if 'winning_query_tag' in d:
            q = d['winning_query_tag']
            lead = ('winning query tag' if d['T'] > 0
                    else 'T = 0, no pair gives a value above 0; kept for the tie-break:')
            pool, per = d['pooled_tail'], d['per_edge']
            out += [f'  M1  {lead} q{q["index"]} "{q["text"]}" ({q["list"]}) -> '
                    f'graph tag "{d["winning_graph_tag"]}" (on {d["graph_tag_chunks"]} chunks)',
                    f'      cos {_f(d["cos"])}; b_q {_f(d["b_q"])}; s_q {_f(d["s_q"])}; standing '
                    f'{_f(d["standing"], 3)}; fit {_f(d["fit"], 3)}',
                    '  M2  the winning edge, raw value / position: '
                    + '; '.join(f'{f} {_f(d["raw"][f])} / {_f(d["pos"][f])}' for f in ALL_FACETS),
                    '  M3  readings ' + ' '.join(_f(d['readings'][f], 2) for f in ALL_FACETS)
                    + '; shares ' + ' '.join(_f(d['shares'][f], 3) for f in ALL_FACETS)
                    + f'; R {_f(d["R"])}; factor R / 0.5 {_f(d["factor"])}; w = fit x factor '
                    f'{_f(d["w"], 3)}',
                    f'  M4  v {_f(d["v"], 3)}; centrality {_f(d["centrality"])}; T '
                    f'{_f(d["T"], 3)}',
                    f'      A4a, the same query tag: eligible edges with w_q >= v: '
                    f'{pool["edges_at_or_above_v"]:,}; tail {_e(pool["tail"])}; n_c {d["n_c"]}; '
                    f'p {_e(pool["p"])}; k {pool["k"]:,}; v* {_f(pool["v_star"], 3)}',
                    f'      A4e, the same query tag: p_c {_e(per["p"])}; k {per["k"]:,} of N; '
                    f'v* {_f(per["v_star"], 3)}']
        else:
            out.append(f'  M1-M4  no eligible edge; T {_f(d["T"], 3)}')
        out.append(f'  M5  D {_f(d["D"], 3)}; Qs {_f(d["Qs"], 3)}; side {_f(d["side"], 3)}; S '
                   f'{_f(d["S"], 3)}')
        for group in GROUPINGS:
            g = d['lifts'][group]
            lead = '  M6  ' if group == 'product' else '      '
            if g is None:
                out.append(f'{lead}{group}: no group; lift {_f(d["lift"][group], 3)}')
            elif group == 'product':
                out.append(f'{lead}product {g["group"]}: n_g {g["n_g"]}; reference '
                           f'{_f(g["reference"], 3)}; raw {_f(g["raw"], 3)}; trust '
                           f'{_f(g["trust"])}; lift {_f(g["lift"], 3)}')
            else:
                out.append(f'{lead}near group #{g["group"]}: size {g["n_g"]}; reference of the '
                           f'kind {_f(g["reference"], 3)}; raw {_f(g["raw"], 3)}; trust '
                           f'{_f(g["trust"])}; lift {_f(g["lift"], 3)}')
        old = d['first_form']
        out += [f'      S\' {_f(d["S_prime"], 3)}',
                '      A6d: lift P ' + _f(old['lift']['product'], 3) + '; lift C '
                + _f(old['lift']['channel'], 3) + '; lift R ' + _f(old['lift']['record'], 3)
                + '; S\' ' + _f(old['S_prime'], 3),
                f'  M7  level {d["level"]}; final position {d["position"]:,}'
                + (f'; facet order of the tie-break: {" > ".join(d["facet_order"])}'
                   if 'facet_order' in d else ''),
                '  position under each alternative: '
                + ' | '.join(f'{a} {d["position_under"][a]:,}' for a in ALTERNATIVES), '']

    out += ['=' * 100, f'THE FIRST {TOP} OF THE PROPOSAL ORDER', '=' * 100]
    out += _table(['pos', 'chunk id', 'kind', 'product', 'n_c', 'q', 'T', 'side', 'lift P',
                   'lift N', 'S\'', 'level'],
                  [[r['position'], r['chunk'], r['kind'], r['product'], r['n_c'],
                    r['winning_query_tag'], _f(r['T'], 3), _f(r['side'], 3),
                    _f(r['lift']['product'], 3), _f(r['lift']['near'], 3),
                    _f(r['S_prime'], 3), r['level']]
                   for r in result['first']], left=(1, 2, 3))
    fm = result['first_mix']
    out += ['  q = the winning query tag', '',
            f'  the first {TOP} under the PROPOSAL, its three stages and every alternative: '
            f'top-{TOP} overlap with the PROPOSAL, the count by record kind,',
            '  the number of distinct products (the stages: descending, chunk id on an exact '
            'tie):']
    out += _table(['', f'overlap of {TOP}'] + MIX_HEAD,
                  [['PROPOSAL', fm['PROPOSAL']['overlap']] + _mix_cells(fm['PROPOSAL'])]
                  + [[f'PROPOSAL, by {text}', fm['stages'][key]['overlap']]
                     + _mix_cells(fm['stages'][key]) for key, text in STAGES]
                  + [[f'{a}: {v["text"]}', v['top_overlap']] + _mix_cells(v['mix'])
                     for a, v in result['alternatives'].items()], left=(0,))
    budget = provenance.get('budget')
    out.append('')
    if budget is None:
        out.append(f'  the {CHAR_BUDGET:,}-character budget: not computed in this run')
    else:
        edge = budget['boundary']
        out.append(f'  the {budget["budget"]:,}-character budget (artefact_v2._budget_contexts '
                   f'on the PROPOSAL order, as artefact_v4.answer_one_question calls it): '
                   f'{budget["kept"]} whole chunks from the top, {budget["chars"]:,} characters'
                   + (f'; the next chunk {edge["id"]} is cut at {edge["chars_kept"]:,} of its '
                      f'{edge["chars_full"]:,} characters' if edge else ''))
    out += ['', 'PROVENANCE',
            f'  tools/walkthrough.py sha256 {provenance["walkthrough_sha256"]}',
            '  the arm\'s sources (artefact_v4 prepared.provenance["source_sha256"]):']
    out += [f'    {path}  {sha}' for path, sha in provenance['source_sha256'].items()]
    return out


# ------------------------------------------------------------------ loading and writing

class _CallGuard:
    """Stands in harness.chat.post: lets `allowed` calls through, refuses any further one."""

    def __init__(self, post, allowed):
        self.post, self.allowed, self.calls, self.answers = post, allowed, 0, []

    def __call__(self, *args, **kwargs):
        if self.calls >= self.allowed:
            raise RuntimeError(f'walkthrough: model call {self.calls + 1} refused; '
                               f'{self.allowed} allowed')
        self.calls += 1
        answer = self.post(*args, **kwargs)
        self.answers.append(answer)
        return answer


def ask_once(arm, question, prepared, guard):
    """`arm._interpret(question, prepared)` with one transport attempt at most: the first
    failure of `arm._cached_stage` - a failed call, an unusable answer, a failure already in
    the cache - stops here, before the arm's re-ask, and the cache keeps the transport's own
    record of it."""
    held = arm._cached_stage

    def stop(failure):
        return Stop(f'the querytagger call failed: {failure}; model calls made {guard.calls}; '
                    'answers received: ' + json.dumps(guard.answers, ensure_ascii=False))

    def once(*args, **kwargs):
        try:
            return held(*args, **kwargs)
        except RuntimeError as failure:
            raise stop(failure) from None

    arm._cached_stage = once
    try:
        return arm._interpret(question, prepared)
    except Stop:
        raise
    except Exception as failure:
        raise stop(failure) from None
    finally:
        arm._cached_stage = held


PRODUCT_OF_CHUNK = '''
MATCH (c:Chunk)-[:product]->(p:Product)
RETURN c.chunk_id AS chunkId, collect(DISTINCT p.name) AS names
'''


def check_counts(counts):
    wrong = {k: (counts[k], v) for k, v in SPEC_COUNTS.items() if counts[k] != v}
    if wrong:
        raise Stop('the counts differ from the spec\'s: '
                   + ', '.join(f'{k} {got:,} (spec {want:,})' for k, (got, want) in wrong.items()))


def _product_names(prepared, database):
    """Each product index of the arm's structure with its name, read from the graph."""
    at = {cid: i for i, cid in enumerate(prepared.chunk_ids)}
    with prepared.driver.session(database=database, default_access_mode='READ') as session:
        rows = session.execute_read(lambda tx: [(r['chunkId'], r['names'])
                                                for r in tx.run(PRODUCT_OF_CHUNK)])
    arm = np.asarray(prepared.structure.product)
    name_of, several = {}, 0
    for cid, found in rows:
        if cid not in at:
            continue
        several += len(found) > 1
        name_of.setdefault(int(arm[at[cid]]), set()).add(sorted(found)[0])
    if several or any(len(v) != 1 for v in name_of.values()) or set(name_of) != set(arm.tolist()):
        raise Stop('the product names do not match the arm\'s product partition: '
                   f'{several} chunks with more than one product, '
                   f'{sum(len(v) != 1 for v in name_of.values())} indices with several names')
    names = [next(iter(name_of[i])) if i in name_of else '' for i in range(int(arm.max()) + 1)]
    used = [name for name in names if name]
    if len(set(used)) != len(used):
        raise Stop('two product indices of the arm carry one name')
    return names


def knobs_read(arm):
    """The arm's knobs this tool reads, by environment name: HERB_V4_OFFLINE, through the arm's
    `_interpret`, and the walk sort's three role knobs, through `embed_query_side`. It reads no
    sort and no other knob of a sort: the walk-through runs the PROPOSAL and every alternative
    of `v4_walk.ALTERNATIVES` itself."""
    flags = arm.knobs()
    return {arm.KNOB_ENV[knob]: flags[knob]
            for knob in ('offline', 'walktagrole', 'walkdescrole', 'walkquestrole')}


def embed_query_side(arm, query, prepared):
    """The query's cosines through the arm's own embedding, each comparison in the role the
    walk sort embeds it in (`arm.walk_roles` of the arm's knobs, `arm._walk_cosines`): per
    query tag of both lists its cosines to the graph tags and its cosine to the query
    description; per chunk the cosines of the query description and of the raw question to
    the chunk description. Returns the roles, the arrays under the names `walk` reads, and
    the number of embedding calls."""
    roles = arm.walk_roles(arm.knobs())
    lists = [[t.text for t in query.tags], [t.text for t in query.query_tags]]
    first, used, _ = arm._walk_cosines(query.description, lists[0], prepared, roles)
    calls = used.calls
    if roles['question'] != 'query':
        asked, used, _ = arm._query_cosines(query.question, [], prepared, roles['question'])
    else:
        asked, used, _ = arm._query_cosines(query.question, [], prepared)
    calls += used.calls
    cosines = [np.asarray(first['query_tag_cosines'], dtype=np.float64)]
    central = [np.asarray(first['query_tag_description_cosines'], dtype=np.float64)]
    if lists[1]:
        second, used, _ = arm._walk_cosines(query.description, lists[1], prepared, roles)
        calls += used.calls
        cosines.append(np.asarray(second['query_tag_cosines'], dtype=np.float64))
        central.append(np.asarray(second['query_tag_description_cosines'], dtype=np.float64))
    return roles, {
        'query_tag_cosines': np.vstack(cosines),
        'query_tag_description_cosines': np.concatenate(central),
        'd_description': np.asarray(first['query_description_cosines'], dtype=np.float64),
        'd_question': np.asarray(asked['query_description_cosines'], dtype=np.float64)}, calls


def draw_probes(eligible, graph_tags, readable, seed=SHUFFLE_SEED, size=PROBES):
    """`size` eligible graph tags drawn without replacement by one generator from `seed`, in
    index order, and their names in readable form."""
    pool = np.flatnonzero(np.asarray(eligible, dtype=bool))
    rng = np.random.default_rng(seed)
    pick = np.sort(rng.choice(pool, size=min(size, pool.size), replace=False))
    return pick, [readable(graph_tags[i]) for i in pick.tolist()]


def load_live(question, stand_in=None):
    """The arrays of the walk-through through artefact_v4's loaders. With `stand_in` (a
    querytagger answer as a dict) no model is asked; without it `_interpret` asks at most once."""
    import arms.artefact_v4 as A
    from artefact import query_content
    from graph.db import _readable
    from harness import chat, orchestrator
    from harness.contract import ModelUsage

    guard = _CallGuard(chat.post, 0 if stand_in is not None else 1)
    chat.post = guard
    started = time.perf_counter()
    prepared = A.prepare_over_corpus(orchestrator.open_corpus(orchestrator.DEFAULT_CORPUS))
    try:
        eligible = np.asarray(prepared.casefold_eligible, dtype=bool)
        edge_tag = np.asarray(prepared.edge_tag)
        counts = {'chunks': len(prepared.chunk_ids), 'graph_tags': len(prepared.graph_tags),
                  'eligible_graph_tags': int(eligible.sum()), 'edges': int(edge_tag.size),
                  'eligible_edges': int(eligible[edge_tag].sum())}
        print(f'walkthrough: {counts["chunks"]} chunks, {counts["graph_tags"]} graph tags, '
              f'{counts["eligible_graph_tags"]} eligible, {counts["edges"]} edges, '
              f'{counts["eligible_edges"]} eligible edges '
              f'({time.perf_counter() - started:.1f}s)', flush=True)
        check_counts(counts)
        product_names = _product_names(prepared, A.DATABASE)
        print(f'walkthrough: {len(product_names)} product names match the arm\'s partition',
              flush=True)
        if stand_in is None:
            print(f'walkthrough: asking the querytagger ({A.INTERPRET_MODEL}), one call at most',
                  flush=True)
            query, usage, stages = ask_once(A, question, prepared, guard)
        else:
            query = query_content.parse(question, stand_in)
            usage, stages = ModelUsage(), [{'stage': 'stand-in', 'cache_hit': None, 'key': None,
                                            'asks': 0, 'offline': None,
                                            'duplicate_tags_dropped': None}]
        stage = stages[0]
        print(f'walkthrough: querytag cache_hit={stage["cache_hit"]} asks={stage["asks"]} '
              f'calls={usage.calls} tokens_in={usage.tokens_in} tokens_out={usage.tokens_out}',
              flush=True)
        saved = None
        if stage['cache_hit']:
            path = Path(prepared.cache_dir) / 'querytag' / (stage['key'] + '.json')
            saved = json.loads(path.read_text(encoding='utf-8')).get('usage')
        d_tags = [t.text for t in query.tags]
        q_tags = [t.text for t in query.query_tags]
        roles, embedded, embed_calls = embed_query_side(A, query, prepared)
        print(f'walkthrough: {len(d_tags)} description-side and {len(q_tags)} question-side '
              'query tags embedded; roles '
              + ', '.join(f'{name} {role}' for name, role in roles.items())
              + f' ({time.perf_counter() - started:.1f}s)', flush=True)
        probe_tags, probe_names = draw_probes(eligible, prepared.graph_tags, _readable)
        mp, used, _ = A._query_cosines(probe_names[0], probe_names, prepared, roles['tags'])
        embed_calls += used.calls
        print(f'walkthrough: {len(probe_names)} probes embedded in the {roles["tags"]} role '
              f'({len(set(probe_names))} distinct readable forms; '
              f'{time.perf_counter() - started:.1f}s)', flush=True)
        structure = prepared.structure
        inputs = {
            'question': query.question, 'description': query.description,
            'query_texts': d_tags + q_tags,
            'query_lists': [LISTS[0]] * len(d_tags) + [LISTS[1]] * len(q_tags),
            'query_readings': np.array([t.readings for t in query.tags]
                                       + [t.readings for t in query.query_tags],
                                       dtype=np.float64),
            **embedded,
            'probe_tags': probe_tags, 'probe_names': probe_names,
            'probe_cosines': np.asarray(mp['query_tag_cosines'], dtype=np.float64),
            'chunk_ids': list(prepared.chunk_ids), 'chunk_kinds': list(prepared.chunk_kinds),
            'graph_tags': list(prepared.graph_tags), 'eligible': eligible,
            'edge_tag': edge_tag, 'edge_chunk': np.asarray(prepared.edge_chunk),
            'edge_topic': np.asarray(prepared.edge_topic, dtype=np.float64),
            'edge_facets': np.asarray(prepared.multikey_layer.values, dtype=np.float64),
            'product': np.asarray(structure.product), 'product_names': product_names,
            'channel_ptr': np.asarray(structure.channel_ptr),
            'channels': np.asarray(structure.channels),
            'adjacency_ptr': np.asarray(structure.adjacency_ptr),
            'adjacency': np.asarray(structure.adjacency),
            'cos_noise': float(A.COS_NOISE)}
        provenance = {
            'interpreter_model': A.INTERPRET_MODEL, 'database': A.DATABASE,
            'usage': {'calls': int(usage.calls), 'tokens_in': int(usage.tokens_in),
                      'tokens_out': int(usage.tokens_out),
                      'cached_input_tokens': int(usage.cached_input_tokens),
                      'time_s': float(usage.time_s)},
            'model_calls_through_chat_post': guard.calls,
            'cache_hit': stage['cache_hit'], 'cache_key': stage['key'], 'asks': stage['asks'],
            'offline': stage['offline'],
            'duplicate_tags_dropped': stage['duplicate_tags_dropped'], 'saved_usage': saved,
            'stand_in': None,
            'embedding_calls': int(embed_calls), 'roles': dict(roles),
            'source_sha256': dict(prepared.provenance['source_sha256']),
            'knobs_read': knobs_read(A), 'counts': counts}
    except BaseException:
        prepared.close()
        raise
    return inputs, prepared, provenance


def budget_take(prepared, order, char_budget=CHAR_BUDGET):
    """How far the character budget reaches into the order, by the arm's own cut."""
    import arms.artefact_v4 as A
    rows = [prepared.chunk_rows[i] for i in order]
    _contexts, _id_lists, _context_ids, budget = A._budget_contexts(rows, char_budget, {})
    return {'budget': int(char_budget), 'kept': int(budget['kept']), 'chars': int(budget['chars']),
            'boundary': budget['boundary'], 'exhausted': bool(budget['exhausted'])}


STRING_KEYS = ('chunk_ids', 'chunk_kinds', 'graph_tags', 'product_names', 'query_texts',
               'query_lists', 'probe_names')


def dump_inputs(inputs, path):
    """The arrays `walk` reads, as one .npz: numbers, ids and names."""
    arrays = {k: np.asarray(v) for k, v in inputs.items() if k not in ('question', 'description')}
    np.savez_compressed(path, question=np.array(inputs['question']),
                        description=np.array(inputs['description']), **arrays)


def read_inputs(path):
    with np.load(path, allow_pickle=False) as archive:
        inputs = {k: archive[k] for k in archive.files}
    for key in STRING_KEYS:
        if key in inputs:
            inputs[key] = [str(v) for v in inputs[key]]
    for key in ('question', 'description'):
        inputs[key] = str(inputs[key])
    inputs['cos_noise'] = float(inputs['cos_noise'])
    return inputs


def _plain(value):
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, np.ndarray):
        return _plain(value.tolist())
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if not np.isfinite(value) else float(value)
    return value


def write(folder, result, provenance):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=False)
    lines = render(result, provenance)
    (folder / 'walkthrough.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    (folder / 'walkthrough.json').write_text(
        json.dumps(_plain({'provenance': provenance, **result}), ensure_ascii=False,
                   allow_nan=False, indent=1), encoding='utf-8')
    return folder


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--out', type=Path, default=None,
                        help='the folder to write; default output/walkthrough/<UTC stamp>')
    parser.add_argument('--stand-in', type=Path, default=None,
                        help='a querytagger answer as JSON, read in place of the model call; '
                             'needs --out')
    parser.add_argument('--dump', type=Path, default=None,
                        help='also save the arrays the walk-through reads to this .npz')
    args = parser.parse_args(argv)
    if args.stand_in is not None and args.out is None:
        parser.error('--stand-in writes only to an --out folder')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    stand_in = (None if args.stand_in is None
                else json.loads(args.stand_in.read_text(encoding='utf-8')))
    try:
        inputs, prepared, provenance = load_live(QUESTION, stand_in)
    except Stop as stop:
        print(f'walkthrough: STOP - {stop}', flush=True)
        return 2
    try:
        if args.stand_in is not None:
            provenance['stand_in'] = str(args.stand_in)
        if args.dump is not None:
            dump_inputs(inputs, args.dump)
            print(f'walkthrough: arrays saved to {args.dump}', flush=True)
        try:
            result, order = walk(inputs)
        except Stop as stop:
            print(f'walkthrough: STOP - {stop}', flush=True)
            return 2
        provenance['budget'] = budget_take(prepared, order)
    finally:
        prepared.close()
    provenance['stamp'] = stamp
    provenance['walkthrough_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    folder = write(args.out if args.out is not None else OUT_ROOT / stamp, result, provenance)
    print(f'walkthrough: wrote {folder / "walkthrough.txt"} and {folder / "walkthrough.json"}',
          flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

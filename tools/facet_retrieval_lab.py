"""Live and batch retrieval interventions on frozen inputs; gold joins after delivery.

No interpreter, answer generator or judge is called. This is an exploratory
construction laboratory, not a replacement serving arm or a held-out evaluation.
"""
from __future__ import annotations

import argparse
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import itertools
import json
import os
from pathlib import Path
import sys
import threading
import time
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'prod'), str(ROOT / 'test'), str(ROOT / 'tools')]
for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '4'
import numpy as np
from threadpoolctl import threadpool_limits
from arms import artefact_facet_joint as A
from artefact.facet_joint_candidate import FACETS
from artefact.facet_recruitment_candidate import _components
from facet_gold90_stage_budget import cut

BASE = ROOT / 'output/research/2026-09-22-retrieval-matrix'
INPUTS = BASE / 'inputs'
POINTERS = ROOT / 'output/research/2026-09-22-gold-source-trace'
FACTORS = {
    'match': ['product', 'minimum', 'maximum', 'tag_only', 'description_only'],
    'topology': ['none', 'adjacency', 'groups', 'both'],
    'graph_join': ['union', 'intersection', 'graph_only'],
    'facet': ['topic_only', 'same_path_sum', 'separate_facet_sum', 'separate_facet_streams'],
    'description': ['multiply', 'off', 'independent_union', 'independent_intersection'],
    'scope': ['all', 'equal_depth', 'area_first', 'area_only'],
    'recovery': ['on', 'off'],
}
LEXICAL = ['lex:' + ','.join(p) for p in itertools.permutations(FACETS)]
DEFAULT = dict(match='product', topology='both', graph_join='union',
               facet='separate_facet_sum', description='multiply', scope='equal_depth', recovery='on')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    os.replace(temp, path)


def policy_key(policy):
    return '|'.join(policy[k] for k in FACTORS)


def policies():
    for match, topology, facet, desc, scope, recovery in itertools.product(
            FACTORS['match'], FACTORS['topology'], FACTORS['facet'],
            FACTORS['description'], FACTORS['scope'], FACTORS['recovery']):
        for join in (FACTORS['graph_join'] if topology != 'none' else ['union']):
            yield dict(match=match, topology=topology, graph_join=join, facet=facet,
                       description=desc, scope=scope, recovery=recovery)
    # Ordering block: exhaust all 5! priorities with the canonical route construction.
    for facet, desc, scope, recovery in itertools.product(
            LEXICAL, FACTORS['description'], FACTORS['scope'], FACTORS['recovery']):
        yield {**DEFAULT, 'facet': facet, 'description': desc, 'scope': scope, 'recovery': recovery}


def competition(scores, mask=None):
    values = np.asarray(scores)
    n = len(values)
    supported = values > 0
    if mask is not None:
        supported &= mask
    ranks = np.full(n, n + 1, dtype=np.int64)
    ordered = np.sort(-values[supported])
    ranks[supported] = 1 + np.searchsorted(ordered, -values[supported], side='left')
    return ranks


def semantic_depth(streams, q, description, mask=None, lex_order=None):
    n = len(q)
    values = streams * q[None, :] if description == 'multiply' else streams
    if lex_order is None:
        depth = np.min(np.asarray([competition(s, mask) for s in values]), axis=0)
    else:
        active = np.any(values > 0, axis=0)
        if mask is not None:
            active &= mask
        indices = np.flatnonzero(active)
        # Stable chunk-index tiebreak is only for display; tied vectors share depth.
        ordering = np.lexsort(tuple([indices] + [-values[f, indices] for f in reversed(lex_order)]))
        ordered = indices[ordering]
        depth = np.full(n, n + 1, dtype=np.int64)
        if len(ordered):
            changed = np.r_[True, np.any(values[:, ordered[1:]] != values[:, ordered[:-1]], axis=0)]
            depth[ordered] = np.maximum.accumulate(np.where(changed, np.arange(len(ordered)) + 1, 0))
    if description.startswith('independent_'):
        qr = competition(q, mask)
        depth = np.minimum(depth, qr) if description == 'independent_union' else np.maximum(depth, qr)
    return depth


def schedule(streams, q, policy, area_mask, component_labels, id_order, cache=None):
    """Pure ordering: never receives gold, source identifiers, costs or outcomes."""
    n = len(q)
    lex_order = [FACETS.index(f) for f in policy['facet'][4:].split(',')] if policy['facet'].startswith('lex:') else None
    prefix = tuple(policy[k] for k in ('match', 'topology', 'graph_join', 'facet', 'description'))
    def depth_for(name, mask=None):
        key = prefix + (name,)
        if cache is not None and key in cache:
            return cache[key]
        value = semantic_depth(streams, q, policy['description'], mask, lex_order)
        if cache is not None:
            cache[key] = value
        return value
    global_depth = depth_for('global')
    scope = policy['scope']
    original = global_depth.copy()
    if area_mask is not None and scope != 'all':
        local = depth_for('area', area_mask)
        if scope == 'equal_depth':
            original = np.minimum(global_depth, local)
        elif scope == 'area_only':
            original = local
        elif scope == 'area_first':
            outside = depth_for('outside', ~area_mask)
            count = int(np.count_nonzero(local <= n))
            original = np.where(area_mask, local, np.where(outside <= n, count + outside, n + 1))
    depth = original.copy()
    if policy['recovery'] == 'on':
        minima = np.full(n, n + 1, dtype=np.int64)
        np.minimum.at(minima, component_labels, original)
        depth = minima[component_labels]
    supported = depth <= n
    if area_mask is not None and scope == 'area_only':
        supported &= area_mask  # Exclusive means exclusive even after record recovery.
    advanced = original != depth
    order = np.lexsort((id_order, advanced, depth))
    order = order[supported[order]]
    before = np.lexsort((id_order, global_depth))
    before = before[global_depth[before] <= n]
    return order, before, original, depth


class Lab:
    def __init__(self):
        self.prepared = A.prepare_over_corpus(ROOT / 'data/corpus/Salesforce__HERB')
        self.ids = [c['chunkId'] for c in self.prepared.chunks]
        self.at = {cid: i for i, cid in enumerate(self.ids)}
        self.n = len(self.ids)
        self.id_order = np.argsort(np.argsort(np.asarray(self.ids)))
        self.components = np.arange(self.n)
        components, _, _ = _components(self.prepared.chunks)
        for component in components:
            members = [self.at[m['chunk_id']] for m in component['members']]
            self.components[members] = min(members)
        verification = read(POINTERS / 'verification.json')
        assert digest(POINTERS / 'chunk_delivery_index.json') == verification['unit_index_sha256']
        assert digest(POINTERS / 'gold_source_index.json') == verification['index_sha256']
        self.units = read(POINTERS / 'chunk_delivery_index.json')
        self.gold = read(POINTERS / 'gold_source_index.json')
        assert set(self.units) == set(self.ids)
        self.cache = OrderedDict()
        self.lock = threading.RLock()

    def status(self):
        manifest_path = INPUTS / 'cases_manifest.json'
        manifest = read(manifest_path) if manifest_path.exists() else {'cases': [], 'expected_cases': 95}
        ready = [c for c in manifest['cases'] if (INPUTS / c['meta']).exists()]
        return {'ready_cases': len(ready), 'expected_cases': manifest['expected_cases'],
                'cases': [{k: c[k] for k in ('case_id', 'question_id', 'cohort')} for c in ready],
                'factors': {**FACTORS, 'facet': FACTORS['facet'] + LEXICAL},
                'default_policy': DEFAULT, 'status': 'ready' if ready else 'capturing_inputs',
                'batch': read(BASE / 'batch/status.json') if (BASE / 'batch/status.json').exists() else None,
                'mode': 'cached_retrieval_no_model_calls'}

    def case(self, case_id):
        if case_id in self.cache:
            self.cache.move_to_end(case_id)
            return self.cache[case_id]
        from artefact.facet_operator_matrix import score_families
        manifest = read(INPUTS / 'cases_manifest.json')
        rec = next((c for c in manifest['cases'] if c['case_id'] == case_id), None)
        if rec is None or not (INPUTS / rec['meta']).exists():
            raise ValueError('Case has not completed numeric capture')
        meta = read(INPUTS / rec['meta'])
        assert digest(INPUTS / rec['npz']) == meta['npz_sha256']
        with np.load(INPUTS / rec['npz'], allow_pickle=False) as arrays:
            matrices = {k: arrays[k].copy() for k in ('query_tag_cosines', 'query_chunk_cosines', 'query_description_cosines')}
            weights = arrays['query_facet_weights'].copy()
        with threadpool_limits(limits=4):
            families = {tuple(p[k] for k in ('match', 'topology', 'graph_join', 'facet')): s
                        for p, s in score_families(self.prepared, matrices, weights)}
        base = families[('product', 'both', 'union', 'separate_facet_sum')][0]
        expected = np.asarray(meta['expected_scores'])
        q = np.maximum(matrices['query_description_cosines'], 0)
        error = float(np.max(np.abs(base * q - expected)))
        if error > 1e-12:
            raise ValueError('Current score reconstruction failed: ' + str(error))
        area = meta['area']['chunk_ids']
        area_set = None if area is None else set(area)
        area_mask = None if area_set is None else np.asarray([cid in area_set for cid in self.ids])
        value = {'meta': meta, 'q': q, 'families': families, 'area_mask': area_mask,
                 'score_parity_error': error, 'cohort': rec['cohort'], 'depth_cache': {}}
        self.cache[case_id] = value
        while len(self.cache) > 2:
            self.cache.popitem(last=False)
        return value

    def validate(self, raw):
        policy = {**DEFAULT, **raw}
        if set(policy) != set(FACTORS):
            raise ValueError('Unknown policy field')
        for key, options in FACTORS.items():
            if policy[key] not in options and not (key == 'facet' and policy[key] in LEXICAL):
                raise ValueError('Unsupported ' + key)
        if policy['topology'] == 'none' and policy['graph_join'] != 'union':
            raise ValueError('No graph topology requires union join; graph-only/intersection have no graph support')
        return policy

    def retrieve(self, case, policy):
        facet = 'separate_facet_streams' if policy['facet'].startswith('lex:') else policy['facet']
        streams = case['families'][(policy['match'], policy['topology'], policy['graph_join'], facet)]
        order, before, nomination, recovered = schedule(streams, case['q'], policy, case['area_mask'], self.components, self.id_order, case['depth_cache'])
        order_ids = (self.ids[i] for i in order)
        # Only this delivery step sees lengths/source IDs; ordering is already complete.
        credited, full, budget = cut(order_ids, self.units)
        scalar = np.sum(streams, axis=0)
        if policy['description'] == 'multiply':
            scalar = scalar * case['q']
        return {'order': order, 'before': before, 'nomination': nomination, 'recovered': recovered,
                'credit': credited, 'full': full, 'budget': budget, 'score': scalar, 'streams': streams}

    def evaluate(self, case, result):
        # Gold is consulted only after retrieval and the 72k cut above have finished.
        gold = set(self.gold['questions'][case['meta']['question_id']])
        credit, budget = result['credit'], result['budget']
        hits = len(gold & credit)
        return {'recall_id': hits / len(gold) if gold else None,
                'precision_id': hits / len(credit) if credit else None,
                'hits': hits, 'gold_count': len(gold), 'retrieved_ids': len(credit),
                'delivered_chars': budget['chars'], 'full_chunks': len(result['full']),
                'partial_chunk_id': None if budget['boundary'] is None else budget['boundary']['id']}

    def replay(self, payload):
        started = time.perf_counter()
        with self.lock:
            case = self.case(payload['case_id'])
            policy = self.validate(payload.get('policy', {}))
            old_policy = self.validate(payload.get('compare_policy', DEFAULT))
            new, old = self.retrieve(case, policy), self.retrieve(case, old_policy)
            def positions(values):
                return {int(c): i + 1 for i, c in enumerate(values)}
            new_rank, old_rank = positions(new['before']), positions(old['before'])
            new_pos, old_pos = positions(new['order']), positions(old['order'])
            new_full, old_full = set(new['full']), set(old['full'])
            gold = set(self.gold['questions'][case['meta']['question_id']])
            linked = {cid: len(set(self.units[cid]['artifact_ids']) & gold) for cid in self.ids}
            movements = [{'chunk_id': cid, 'old_rank': old_rank.get(i), 'new_rank': new_rank.get(i),
                'old_position': old_pos.get(i), 'new_position': new_pos.get(i),
                'gold_pointer_count': linked[cid], 'old_delivered': cid in old_full,
                'new_delivered': cid in new_full, 'score': float(new['score'][i]),
                'old_score': float(old['score'][i]), 'in_area': bool(case['area_mask'][i]) if case['area_mask'] is not None else None,
                'nomination_depth': int(new['nomination'][i]) if new['nomination'][i] <= self.n else None,
                'recovered_depth': int(new['recovered'][i]) if new['recovered'][i] <= self.n else None,
                'stream_contributions': [float(x) for x in new['streams'][:, i]]}
                for i, cid in enumerate(self.ids)]
            movements.sort(key=lambda r: (r['new_position'] is None, r['new_position'] or self.n + 1))
            return {'case_id': payload['case_id'], 'policy': policy, 'comparison_policy': old_policy,
                'summary': self.evaluate(case, new), 'comparison_summary': self.evaluate(case, old),
                'movements': movements, 'gold_pointers': [{'artifact_id': aid,
                    'chunk_ids': list(self.gold['artifacts'][aid]), 'old_credited': aid in old['credit'],
                    'new_credited': aid in new['credit']} for aid in sorted(gold)],
                'timing_ms': round(1000 * (time.perf_counter() - started), 1),
                'score_parity_error': case['score_parity_error'],
                'mode': 'cached_retrieval_no_model_calls',
                'note': 'Scores are diagnostic sums for multi-stream/lexicographic policies; semantic position and delivery position govern admission. ID metrics are not exhaustive relevance judgments.'}


def serve(port):
    lab = Lab()
    static = ROOT / 'tools/retrieval_lab_static'
    class Handler(BaseHTTPRequestHandler):
        def send_json(self, value, status=200):
            body = json.dumps(value, allow_nan=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = urlparse(self.path).path
            if path == '/api/status':
                return self.send_json(lab.status())
            if path == '/api/batch':
                target = BASE / 'batch/summary.json'
                return self.send_json(read(target) if target.exists() else {'status': 'pending'})
            target = (static / ('index.html' if path == '/' else path.lstrip('/'))).resolve()
            if not target.is_relative_to(static.resolve()) or not target.is_file():
                return self.send_error(404)
            data = target.read_bytes()
            self.send_response(200)
            mime = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css'}.get(target.suffix, 'application/octet-stream')
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            if self.path != '/api/replay':
                return self.send_error(404)
            try:
                count = int(self.headers.get('Content-Length', '0'))
                if not 0 < count < 100_000:
                    raise ValueError('Invalid request size')
                value = lab.replay(json.loads(self.rfile.read(count)))
                self.send_json(value)
            except Exception as exc:
                self.send_json({'error': str(exc)}, 400)

        def log_message(self, *_):
            pass
    print(json.dumps({'phase': 'serving', 'url': f'http://127.0.0.1:{port}/'}), flush=True)
    ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8770)
    args = parser.parse_args()
    serve(args.port)

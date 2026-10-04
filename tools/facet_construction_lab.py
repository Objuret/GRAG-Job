"""Additive construction experiment: query support reduction, frozen 95 cases.

No model calls or database writes. Gold is read only by the inherited evaluator
after full ordering and the existing 72k cut. Existing modules stay unchanged.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import itertools
import json
from pathlib import Path
import sys

import facet_retrieval_lab as L
import numpy as np
from artefact.facet_operator_matrix import _reducer, _checked_relations, _graph_primitives

OUT = L.ROOT / 'output/research/2026-09-23-construction-query-reduction'
MODES = ('maximum', 'mean', 'minimum')


def combine_queries(combined, mode, unique):
    """[facet,query,chunk] -> one stream; equal query average is a hypothesis.

    Exact duplicate numeric query readings count once. This does not detect
    paraphrases or establish statistical independence of different query tags.
    """
    if mode not in MODES:
        raise ValueError('Unknown query reducer')
    values = combined[:, unique, :]
    if mode == 'minimum':
        winners = values.min(axis=1)
    elif mode == 'maximum':
        winners = values.max(axis=1)
    else:
        winners = values.mean(axis=1)
    return (np.asarray([1., .25, .25, .25, .25])[:, None] * winners).sum(axis=0, keepdims=True)


def numeric_support(prepared, matrices, weights, match, topology, join):
    n = len(prepared.chunks)
    m = np.maximum(matrices['query_tag_cosines'], 0)
    d = np.maximum(matrices['query_chunk_cosines'], 0)
    u = np.asarray(weights)
    if u.ndim != 2 or u.shape[1] != 5 or not len(u) or d.shape != (len(u), n):
        raise ValueError('Misaligned query inputs')
    if any(not np.isfinite(a).all() for a in (m, d, u)) or (u < 0).any():
        raise ValueError('Invalid query inputs')
    et, ec = prepared.edge_tag, prepared.edge_chunk
    f = prepared.reference.transform(prepared.edge_facets)
    em, ed = m[:, et], d[:, ec]
    a = em * ed if match == 'product' else np.maximum(em, ed)
    if match not in ('product', 'maximum') or topology not in ('both', 'groups') or join not in ('union', 'intersection'):
        raise ValueError('Unsupported structural context')
    reduce = _reducer(ec, n)
    direct = np.array([reduce(a * u[:, k, None] * f[None, :, k]) for k in range(5)])
    groups, source, target = _checked_relations(prepared, n)
    adjacent, grouped = _graph_primitives(direct, d, groups, source, target, _reducer(target, n))
    graph = grouped if topology == 'groups' else np.maximum(adjacent, grouped)
    combined = np.maximum(direct, graph) if join == 'union' else np.minimum(direct, graph)
    # No text or outcome enters duplicate detection; identical readings only.
    signatures = np.concatenate((matrices['query_tag_cosines'], matrices['query_chunk_cosines'], u), axis=1)
    _, unique = np.unique(signatures, axis=0, return_index=True)
    unique.sort()
    return combined, unique, {'direct': direct, 'adjacent': adjacent, 'grouped': grouped,
                              'graph': graph, 'u': u, 'f': f, 'alignment': a}


def contexts():
    for (match, topology, join), scope, recovery in itertools.product(
            [('product', 'both', 'union'), ('maximum', 'groups', 'intersection')],
            ['all', 'equal_depth', 'area_first'], ['off', 'on']):
        yield dict(match=match, topology=topology, graph_join=join,
                   facet='separate_facet_sum', description='multiply', scope=scope, recovery=recovery)


class ConstructionLab(L.Lab):
    def case(self, case_id):
        case = super().case(case_id)
        if 'construction' not in case:
            rec = next(c for c in L.read(L.INPUTS / 'cases_manifest.json')['cases'] if c['case_id'] == case_id)
            with np.load(L.INPUTS / rec['npz'], allow_pickle=False) as arrays:
                matrices = {k: arrays[k].copy() for k in ('query_tag_cosines', 'query_chunk_cosines', 'query_description_cosines')}
                weights = arrays['query_facet_weights'].copy()
            case['construction'] = {}
            for route in [('product', 'both', 'union'), ('maximum', 'groups', 'intersection')]:
                combined, unique, stages = numeric_support(self.prepared, matrices, weights, *route)
                modes = {mode: combine_queries(combined, mode, unique) for mode in MODES}
                reference = case['families'][route + ('separate_facet_sum',)]
                if not np.array_equal(modes['maximum'], reference):
                    raise ValueError('Maximum reducer reference parity failed')
                case['construction'][route] = (modes, combined, unique, stages)
            case['matrices'] = matrices
        return case

    def changed(self, case, policy, mode):
        route = tuple(policy[k] for k in ('match', 'topology', 'graph_join'))
        streams = case['construction'][route][0][mode]
        return {**case, 'families': {route + ('separate_facet_sum',): streams}, 'depth_cache': {}}

    def replay(self, payload):
        # Reuse existing full movement/credit trace and budget contract.
        with self.lock:
            mode = payload.get('reducer', 'mean')
            if mode not in MODES:
                raise ValueError('Unknown reducer')
            policy = self.validate(payload.get('policy', L.DEFAULT))
            if policy not in list(contexts()):
                raise ValueError('Use one of the declared construction contexts')
            case = self.case(payload['case_id'])
            old = self.retrieve(case, policy)
            new = self.retrieve(self.changed(case, policy, mode), policy)
            oldpos = {int(c): i + 1 for i, c in enumerate(old['order'])}
            newpos = {int(c): i + 1 for i, c in enumerate(new['order'])}
            gold = set(self.gold['questions'][case['meta']['question_id']])
            oldfull, newfull = set(old['full']), set(new['full'])
            route = tuple(policy[k] for k in ('match', 'topology', 'graph_join'))
            _, combined, unique, stages = case['construction'][route]
            movements = []
            for i, cid in enumerate(self.ids):
                movements.append({'chunk_id': cid, 'old_position': oldpos.get(i), 'new_position': newpos.get(i),
                    'old_delivered': cid in oldfull, 'new_delivered': cid in newfull,
                    'gold_pointer_count': len(gold & set(self.units[cid]['artifact_ids'])),
                    'old_score': float(old['score'][i]), 'new_score': float(new['score'][i]),
                    'nomination_depth': int(new['nomination'][i]), 'recovered_depth': int(new['recovered'][i]),
                    'in_area': None if case['area_mask'] is None else bool(case['area_mask'][i]),
                    'per_facet_query_support': combined[:, :, i].tolist()})
            movements.sort(key=lambda row: row['new_position'] or self.n + 1)
            return {'case_id': payload['case_id'], 'reducer': mode, 'policy': policy,
                    'summary': self.evaluate(case, new), 'comparison_summary': self.evaluate(case, old),
                    'candidate_access': {'old': len(old['order']), 'new': len(new['order']),
                        'added': len(set(newpos) - set(oldpos)), 'removed': len(set(oldpos) - set(newpos))},
                    'query_rows': combined.shape[1], 'distinct_numeric_query_rows': len(unique),
                    'budget': new['budget'], 'reference_budget': old['budget'], 'movements': movements}


def sealed_plan():
    manifest = L.read(L.INPUTS / 'cases_manifest.json')
    files = {Path(__file__), L.INPUTS / 'cases_manifest.json', L.POINTERS / 'verification.json',
        L.POINTERS / 'chunk_delivery_index.json', L.POINTERS / 'gold_source_index.json',
        Path(L.__file__), L.ROOT / 'test/artefact/facet_operator_matrix.py',
        L.ROOT / 'tools/facet_gold90_stage_budget.py'}
    files.update(L.ROOT / p for p in L.A.SMOKE_PROVENANCE_PATHS)
    for c in manifest['cases']:
        files.update((L.INPUTS / c['meta'], L.INPUTS / c['npz']))
    return {'case_ids': [c['case_id'] for c in manifest['cases']], 'reducers': list(MODES),
        'policies': list(contexts()), 'original_failed_question_ids': manifest['failed_question_ids'],
        'input_sha256': {str(p.relative_to(L.ROOT)): L.digest(p) for p in sorted(files)},
        'coefficients': [1, .25, .25, .25, .25], 'budget': 72000,
        'scope': 'Exploratory matched query aggregation comparison; no new scope discovery or multi-hop traversal.',
        'duplicate_policy': 'Exact duplicate numeric query readings count once; correlated distinct readings remain unresolved.',
        'runtime': {'python': sys.version.split()[0], 'numpy': np.__version__},
        'language_model_calls': 0, 'database_calls': 0}


def batch(out):
    out.mkdir(parents=True, exist_ok=True)
    plan = sealed_plan()
    if (out / 'plan.json').exists():
        if L.read(out / 'plan.json') != plan:
            raise ValueError('Sealed experiment inputs changed; choose new output')
    else:
        L.write_new(out / 'plan.json', plan)
    lock = out / 'writer.lock'
    L.write_new(lock, {'started': datetime.now(timezone.utc).isoformat()})
    try:
        lab = ConstructionLab()
        all_rows = []
        for ci, cid in enumerate(plan['case_ids']):
            target = out / 'cases' / (cid + '.json')
            if target.exists():
                rows = L.read(target)
            else:
                case = lab.case(cid)
                rows = []
                for pi, policy in enumerate(plan['policies']):
                    ref = lab.retrieve(case, policy)
                    refmetrics = lab.evaluate(case, ref)
                    for mode in MODES:
                        result = lab.retrieve(lab.changed(case, policy, mode), policy)
                        if mode == 'maximum' and not np.array_equal(result['order'], ref['order']):
                            raise ValueError('Full order reference parity failed')
                        metrics = lab.evaluate(case, result)
                        r, p = metrics['recall_id'], metrics['precision_id']
                        metrics['f1_id'] = 2*r*p/(r+p) if p is not None and r+p else 0.
                        rows.append({'case_id': cid, 'policy_index': pi, 'reducer': mode, **metrics,
                            'recall_delta': r-refmetrics['recall_id'],
                            'access': len(result['order']),
                            'access_added': len(set(result['order'])-set(ref['order'])),
                            'access_removed': len(set(ref['order'])-set(result['order'])),
                            'order_changed': not np.array_equal(result['order'],ref['order']),
                            'delivered_set_changed': set(result['full']) != set(ref['full']),
                            'full_chunk_ids': result['full'], 'budget': result['budget']})
                L.write_new(target, rows)
            all_rows.extend(rows)
            L.atomic(out / 'status.json', {'completed_cases': ci+1, 'expected_cases': len(plan['case_ids'])})
            print(json.dumps({'completed_cases': ci+1}), flush=True)
        report = []
        for pi, policy in enumerate(plan['policies']):
            for mode in MODES:
                rows = [r for r in all_rows if r['policy_index']==pi and r['reducer']==mode]
                row = {'policy_index': pi, 'policy': policy, 'reducer': mode, 'cases':len(rows)}
                for key in ('recall_id','precision_id','f1_id','recall_delta'):
                    values = [r[key] for r in rows if r[key] is not None]
                    row[key] = float(np.mean(values)) if values else None
                    row[key+'_defined'] = len(values)
                for label, predicate in [('wins',lambda r:r['recall_delta']>0),('losses',lambda r:r['recall_delta']<0),
                        ('ties',lambda r:r['recall_delta']==0),('order_changed',lambda r:r['order_changed']),
                        ('delivered_set_changed',lambda r:r['delivered_set_changed']),
                        ('access_changed',lambda r:r['access_added'] or r['access_removed'])]:
                    row[label] = sum(bool(predicate(r)) for r in rows)
                report.append(row)
        report.sort(key=lambda r:-r['recall_id'])
        L.atomic(out/'report.json',report)
        if sealed_plan() != plan:
            raise ValueError('Inputs changed during run')
        L.atomic(out/'status.json',{'status':'complete','completed_cases':len(plan['case_ids']),
            'evaluations':len(all_rows),'input_hashes_verified':True,'reference_full_order_parity':True})
    finally:
        lock.unlink()


def serve(port, out):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    lab = ConstructionLab()
    class Handler(BaseHTTPRequestHandler):
        def send(self, data, mime='application/json', code=200):
            body = data.encode() if isinstance(data,str) else json.dumps(data,allow_nan=False).encode()
            self.send_response(code); self.send_header('Content-Type',mime); self.send_header('Content-Length',str(len(body)))
            self.end_headers(); self.wfile.write(body)
        def do_GET(self):
            if self.path == '/api/status':
                return self.send({'cases':lab.status()['cases'],'policies':list(contexts()),'reducers':MODES})
            if self.path == '/api/leaderboard':
                return self.send(L.read(out/'report.json') if (out/'report.json').exists() else [])
            if self.path == '/':
                return self.send((L.ROOT/'tools/construction_lab.html').read_text(encoding='utf-8'),'text/html; charset=utf-8')
            self.send({'error':'Not found'},code=404)
        def do_POST(self):
            try:
                if self.path != '/api/replay': raise ValueError('Unknown endpoint')
                count=int(self.headers.get('Content-Length','0'))
                if not 0<count<100000: raise ValueError('Invalid size')
                self.send(lab.replay(json.loads(self.rfile.read(count))))
            except (ValueError,KeyError) as exc:
                self.send({'error':str(exc)},code=400)
        def log_message(self,*args): pass
    print(json.dumps({'url':f'http://127.0.0.1:{port}'}),flush=True)
    ThreadingHTTPServer(('127.0.0.1',port),Handler).serve_forever()


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['batch','serve','trace'])
    parser.add_argument('--out',type=Path,default=OUT)
    parser.add_argument('--port',type=int,default=8771)
    parser.add_argument('--case',default='case_001')
    args=parser.parse_args()
    if args.command=='batch': batch(args.out)
    elif args.command=='serve': serve(args.port,args.out)
    else:
        lab=ConstructionLab()
        result=lab.replay({'case_id':args.case,'reducer':'mean'})
        L.write_new(args.out/(args.case+'-trace.json'),result)
        case=lab.case(args.case)
        _,combined,unique,stages=case['construction'][('product','both','union')]
        numeric={k:v for k,v in stages.items() if k!='alignment'}
        numeric.update(combined=combined,unique_query_rows=unique,**case['matrices'])
        with (args.out/(args.case+'-stages.npz')).open('xb') as f:
            np.savez_compressed(f,**numeric)
        print(json.dumps({k:v for k,v in result.items() if k!='movements'}))

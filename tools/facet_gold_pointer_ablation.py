"""One fixed, cached-query auxiliary-off ablation; gold joined after delivery."""
from __future__ import annotations

import ast
from collections import Counter
import copy
import json
from pathlib import Path
import sys

import numpy as np
import facet_gold_trace as T

ROOT = T.ROOT
BASE = T.OUT
OUT = BASE / 'auxiliary_off'
sys.path[:0] = [str(ROOT / 'prod'), str(ROOT / 'test')]
from harness.char_budget import cut_at_budget
from artefact.facet_scope_recruitment import recruit_with_verified_area


def freeze(path, value):
    if path.exists():
        if T.read(path) != value:
            raise ValueError(f'Frozen input changed: {path}')
    else:
        T.write(path, value)


def budget_helper(chunks, units):
    resolve = T.resolver()
    namespace = resolve.__globals__
    docs, cache = {}, {}
    def cached(row, doc_cache):
        cid = row['chunkId']
        if cid not in cache:
            cache[cid] = resolve(row, doc_cache)
            text, ids = cache[cid]
            assert len(text) == units[cid]['serialized_chars']
            assert ids == units[cid]['artifact_ids']
        return cache[cid]
    namespace.update(_resolve_chunk=cached, cut_at_budget=cut_at_budget)
    path = ROOT / 'test/arms/artefact_v2.py'
    node, = [n for n in ast.parse(path.read_text(encoding='utf-8')).body
             if isinstance(n, ast.FunctionDef) and n.name == '_budget_contexts']
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), namespace)
    def deliver(order):
        return namespace['_budget_contexts']([chunks[c] for c in order], 72000, docs)
    return deliver


def source_case(qid, meta, ranked, scoped, order, credit, budget, index, units, graph):
    positions = {cid:i+1 for i,cid in enumerate(order)}
    costs, cumulative = {}, 0
    for cid in order:
        cumulative += units[cid]['serialized_chars']
        costs[cid] = cumulative
    full = set(order[:budget['kept']])
    boundary = budget['boundary']
    bid = boundary['id'] if boundary else None
    by_rank = {r['chunk_id']:r for r in ranked}
    nomination = {r['chunk_id']:r for r in scoped['recruitment']['nomination']['rows']}
    recovery = {r['chunk_id']:r for r in scoped['recruitment']['rows']}
    sources = []
    for aid in index['questions'][qid]:
        pointers = []
        for cid in index['artifacts'][aid]:
            row = by_rank[cid]
            status = ('full_unit' if cid in full else 'partial_unit' if cid == bid else
                      'outside_budget' if cid in positions else 'not_nominated')
            pointers.append({'chunk_id':cid,'score_rank':row['rank'],'score':row['score'],
                'nomination':nomination.get(cid),'recovery':recovery.get(cid),
                'delivery_position':positions.get(cid),'complete_unit_chars':costs.get(cid),
                'status':status,'boundary':boundary if cid==bid else None,
                'facet_paths':T.safe_witnesses(row['provenance'],graph)})
        status = ('credited' if aid in credit else 'partial_only' if any(p['status']=='partial_unit' for p in pointers)
                  else 'outside_budget' if any(p['status']=='outside_budget' for p in pointers)
                  else 'not_nominated' if pointers else 'not_in_frozen_graph')
        sources.append({'artifact_id':aid,'status':status,'credited':aid in credit,
            'first_score_rank':min((p['score_rank'] for p in pointers),default=None),
            'first_delivery_position':min((p['delivery_position'] for p in pointers if p['delivery_position'] is not None),default=None),
            'first_complete_unit_chars':min((p['complete_unit_chars'] for p in pointers if p['complete_unit_chars'] is not None),default=None),
            'chunks':pointers})
    return {'question_id':qid,'budget':budget['budget'],'delivered_chars':budget['chars'],
            'gold_sources':len(sources),'credited_sources':sum(s['credited'] for s in sources),'sources':sources}


def main():
    index = T.read(BASE / 'gold_source_index.json')
    units = T.read(BASE / 'chunk_delivery_index.json')
    verification = T.read(BASE / 'verification.json')
    assert T.sha(BASE/'gold_source_index.json') == verification['index_sha256']
    assert T.sha(BASE/'chunk_delivery_index.json') == verification['unit_index_sha256']
    graph = T.read(T.SNAPSHOT/'graph.json')
    chunks = {c['chunkId']:c for c in graph['chunks']}
    paths = [Path(__file__), ROOT/'docs/2026-09-22-gold-pointer-ablation-protocol.md',
             Path(T.__file__), ROOT/'tools/facet_gold_trace.html',
             BASE/'gold_source_index.json', BASE/'chunk_delivery_index.json', BASE/'run_traces.json',
             T.DEFAULT_RUN/'arm_outputs.jsonl', T.SNAPSHOT/'graph.json', T.SNAPSHOT/'arrays.npz']
    code_paths = ['test/arms/artefact_v2.py','prod/harness/char_budget.py',
                  'test/artefact/facet_scope_recruitment.py','test/artefact/facet_recruitment_candidate.py',
                  'test/artefact/facet_need_frontier.py','test/artefact/facet_retrieval_pipeline.py',
                  'test/artefact/facet_stream_envelope.py']
    paths += [ROOT/p for p in code_paths]
    manifest = {'input_sha256':{p.relative_to(ROOT).as_posix():T.sha(p) for p in paths},
                'conditions':{'saved_joint':[1,.25,.25,.25,.25],'auxiliary_off':[1,0,0,0,0]},
                'budget':72000,'gold_join':'After ranking, scope, recovery and delivery only.'}
    freeze(OUT/'plan.json',manifest)
    if (OUT/'comparison.json').exists():
        raise ValueError('Completed comparison exists; preserve it')
    deliver = budget_helper(chunks,units)
    originals = {c['question_id']:c for c in T.read(BASE/'run_traces.json')[0]['cases']}
    differences, cases, movement = [], [], []
    maximum_sum_error = 0.
    for saved in T.rows(T.DEFAULT_RUN/'arm_outputs.jsonl'):
        qid, meta = saved['id'], saved['meta']
        if qid not in originals:
            continue
        snap = meta['snapshot']
        for file,key in [('graph.json','graph_sha256'),('arrays.npz','arrays_sha256')]:
            assert snap['snapshot_sha256'][file] == index['provenance'][key] == T.sha(T.SNAPSHOT/file)
        saved_hashes = {k.replace('\\','/'):v for k,v in snap['source_sha256'].items()}
        for p in code_paths:
            assert saved_hashes[p] == manifest['input_sha256'][p], p
        ranks = meta['ranking']['rows']
        assert meta['ranking']['coefficients'] == [1,.25,.25,.25,.25]
        by_id = {r['chunk_id']:r for r in ranks}
        assert set(by_id) == set(chunks) and len(ranks)==len(chunks)
        for row in ranks:
            error=abs(row['score']-sum(w['contribution'] for w in row['provenance'].values() if w))
            maximum_sum_error=max(maximum_sum_error,error)
            assert error < 1e-12
        assert [r['chunk_id'] for r in sorted(ranks,key=lambda r:(-r['score'],r['chunk_id']))] == meta['ranking']['ranked_chunk_ids']
        area = meta['area']['area']
        def recruit(scores):
            return recruit_with_verified_area(chunk_rows=list(chunks.values()),joint_scores=scores,
                area_chunk_ids=area['chunk_ids'],area_provenance=area['provenance'],source_character_budget=None)
        baseline = recruit(np.array([by_id[c]['score'] for c in chunks]))
        assert baseline['recruitment'] == meta['recruitment']
        order = baseline['recruitment']['selected_chunk_ids']
        assert order == meta['full_recovered_order']
        texts, ids, credit, budget = deliver(order)
        assert texts == saved['contexts'] and credit == saved['context_ids'] and budget == meta['char_budget']
        # Freeze the treatment without consulting any gold source/target.
        off = copy.deepcopy(ranks)
        for row in off:
            w = row['provenance']['topic']
            row['score'] = w['contribution'] if w else 0.
            for facet in T.FACETS[1:]:
                if row['provenance'][facet]:
                    row['provenance'][facet]['coefficient']=0.
                    row['provenance'][facet]['contribution']=0.
        off.sort(key=lambda r:(-r['score'],r['chunk_id']))
        for rank,row in enumerate(off,1):row['rank']=rank
        off_by_id = {r['chunk_id']:r for r in off}
        scoped = recruit(np.array([off_by_id[c]['score'] for c in chunks]))
        order = scoped['recruitment']['selected_chunk_ids']
        _, _, credit, budget = deliver(order)
        # Gold only enters here, after both deliveries are fixed.
        case = source_case(qid,meta,off,scoped,order,set(credit),budget,index,units,graph)
        cases.append(case)
        original = originals[qid]
        on_ids = {s['artifact_id'] for s in original['sources'] if s['credited']}
        off_ids = {s['artifact_id'] for s in case['sources'] if s['credited']}
        n=case['gold_sources']
        differences.append({'question_id':qid,'gold_source_count':n,'joint_credited':len(on_ids),
            'off_credited':len(off_ids),'joint_only':sorted(on_ids-off_ids),'off_only':sorted(off_ids-on_ids),
            'joint_recall':len(on_ids)/n if n else None,'off_recall':len(off_ids)/n if n else None,
            'delta_joint_minus_off':(len(on_ids)-len(off_ids))/n if n else None,
            'joint_contexts':meta['returned'],'off_contexts':budget['kept']+bool(budget['boundary'])})
        orig_src={s['artifact_id']:s for s in original['sources']}
        for s in case['sources']:
            old=orig_src[s['artifact_id']]
            movement.append({'question_id':qid,'artifact_id':s['artifact_id'],
                'joint_status':old['status'],'off_status':s['status'],
                'joint_best_score_rank':old['first_score_rank'],'off_best_score_rank':s['first_score_rank'],
                'joint_earliest_delivery_position':old['first_delivery_position'],
                'off_earliest_delivery_position':s['first_delivery_position']})
    assert len(cases)==10
    valid=[d for d in differences if d['gold_source_count']]
    summary={'questions':len(cases),'baseline_full_recruitment_and_text_delivery_parity':len(cases),
        'maximum_contribution_sum_error':maximum_sum_error,
        'macro_joint_recall':sum(d['joint_recall'] for d in valid)/len(valid),
        'macro_off_recall':sum(d['off_recall'] for d in valid)/len(valid),
        'joint_only_source_links':sum(len(d['joint_only']) for d in valid),
        'off_only_source_links':sum(len(d['off_only']) for d in valid),
        'questions_joint_better':sum(d['delta_joint_minus_off']>0 for d in valid),
        'questions_off_better':sum(d['delta_joint_minus_off']<0 for d in valid),
        'questions_tied':sum(d['delta_joint_minus_off']==0 for d in valid),
        'model_calls':0,'embedding_calls':0,'new_answers':0,'condition':'Fixed auxiliary-off readout, same saved query and scope.'}
    T.write(OUT/'comparison.json',{'summary':summary,'questions':differences,'source_movements':movement})
    traces=T.read(BASE/'run_traces.json')+[{'run':'Counterfactual: auxiliaries off (saved queries, actual delivery)',
        'cases':cases,'summary':summary,'limits':'Controlled replay, not a new generated-answer/RAGAS run.'}]
    T.write(OUT/'run_traces.json',traces)
    T.render(OUT,index,traces)
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()

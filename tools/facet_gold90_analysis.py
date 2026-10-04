"""Replay the frozen remaining-90 comparison, streaming private harness records."""
from __future__ import annotations

import argparse
import asyncio
from collections import defaultdict
import importlib.metadata
import hashlib
import inspect
import json
import math
import os
from pathlib import Path

os.environ['RAGAS_DO_NOT_TRACK'] = 'true'
os.environ['RAGAS_DEBUG_TRACKING'] = 'false'
import numpy as np
import facet_gold_pointer_ablation as B
import facet_gold_trace as T
import facet_gold90_validation as V
from artefact.facet_scope_recruitment import recruit_with_verified_area
from ragas.dataset_schema import SingleTurnSample
from ragas.metrics._context_precision import IDBasedContextPrecision
from ragas.metrics._context_recall import IDBasedContextRecall


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def mean(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def aggregate(rows, total):
    result = {'planned_questions': total, 'successful_pairs': len(rows),
              'missing_retrievals': total-len(rows), 'conditions': {}, 'paired': {}}
    for condition in ('joint', 'auxiliaries_off'):
        selected = [r[condition] for r in rows]
        result['conditions'][condition] = {
            'context_precision_id': mean([r['context_precision_id'] for r in selected]),
            'precision_defined_cases': sum(r['context_precision_id'] is not None for r in selected),
            'context_recall_id': mean([r['context_recall_id'] for r in selected]),
            'recall_with_missing_retrieval_zero': sum(r['context_recall_id'] for r in selected)/total,
            'source_question_hits': sum(r['hits'] for r in selected),
            'source_question_retrieved': sum(r['retrieved_ids'] for r in selected)}
    for key in ('context_precision_id', 'context_recall_id'):
        delta = [r['joint'][key]-r['auxiliaries_off'][key] for r in rows
                 if r['joint'][key] is not None and r['auxiliaries_off'][key] is not None]
        result['paired'][key] = {'defined_pairs': len(delta), 'mean_joint_minus_off': mean(delta),
                                'joint_better': sum(d>0 for d in delta),
                                'joint_worse': sum(d<0 for d in delta),
                                'ties': sum(d==0 for d in delta)}
    return result


async def main(folder):
    folder = folder.resolve()
    assert folder.parent == V.RUN_ROOT.resolve() and folder.name.startswith(V.PREFIX)
    completed = T.read(folder/'retrieval_completed.json')
    assert completed['phase'] in ('completed', 'process_failed')
    assert completed['input_hashes_unchanged']
    plan = T.read(folder/'validation_plan.json')
    assert T.sha(folder/'validation_plan.json') == T.read(folder/'prepared.json')['plan_sha256']
    V.verify(plan)
    out = folder/'paired_id_analysis'
    if (out/'started.json').exists():
        raise ValueError('Analysis already started; preserve artifacts and inspect its process before retrying')
    paths = [Path(__file__), Path(B.__file__), Path(T.__file__),
             folder/'validation_plan.json', folder/'retrieval_completed.json',
             folder/'arm_outputs.jsonl', folder/'failures.jsonl',
             T.OUT/'gold_source_index.json', T.OUT/'chunk_delivery_index.json',
             Path(inspect.getfile(IDBasedContextPrecision)), Path(inspect.getfile(IDBasedContextRecall))]
    B.freeze(out/'plan.json', {'input_sha256': {str(p.relative_to(T.ROOT)): sha(p) for p in paths},
        'ragas_version': importlib.metadata.version('ragas'),
        'conditions': plan['conditions'], 'budget': 72000,
        'gold_join': 'Only after both conditions have completed ranking, recovery and delivery',
        'aggregation': 'Paired successful means, failure-inclusive recall over 90, and product-prefix groups',
        'model_calls': 0})
    T.write(out/'started.json', {'pid': os.getpid()})
    expected = V.ids(folder/'remaining90.jsonl')
    assert len(expected) == len(set(expected)) == 90
    failed = [r['id'] for r in T.rows(folder/'failures.jsonl')]
    assert len(failed) == len(set(failed)) and set(failed) <= set(expected)
    index = T.read(T.OUT/'gold_source_index.json')
    units = T.read(T.OUT/'chunk_delivery_index.json')
    verification = T.read(T.OUT/'verification.json')
    assert T.sha(T.OUT/'gold_source_index.json') == verification['index_sha256']
    assert T.sha(T.OUT/'chunk_delivery_index.json') == verification['unit_index_sha256']
    for source in index['provenance']['raw_files_verified']:
        assert T.sha(T.ROOT/'data/raw'/source['relpath']) == source['sha256']
    assert index['provenance']['questions_sha256'] == T.sha(T.ROOT/'data/questions.jsonl')
    graph = T.read(T.SNAPSHOT/'graph.json')
    chunks = {c['chunkId']:c for c in graph['chunks']}
    deliver = B.budget_helper(chunks, units)
    metrics = [('context_precision_id', IDBasedContextPrecision()),
               ('context_recall_id', IDBasedContextRecall())]
    rows, seen, max_error = [], set(), 0.
    with (out/'source_movements.jsonl').open('x', encoding='utf-8') as pointers:
        for saved in T.rows(folder/'arm_outputs.jsonl'):
            qid, meta = saved['id'], saved['meta']
            assert qid in expected and qid not in seen and qid not in failed
            seen.add(qid)
            assert not saved['answer'], 'Retrieval-only run must not contain generated answers'
            snap = meta['snapshot']
            for file, key in [('graph.json','graph_sha256'), ('arrays.npz','arrays_sha256')]:
                assert snap['snapshot_sha256'][file] == index['provenance'][key] == T.sha(T.SNAPSHOT/file)
            for path, value in snap['source_sha256'].items():
                assert T.sha(T.ROOT/path) == value
            ranks = meta['ranking']['rows']
            assert meta['ranking']['coefficients'] == [1,.25,.25,.25,.25]
            by_id = {r['chunk_id']:r for r in ranks}
            assert set(by_id) == set(chunks) and len(ranks) == len(chunks)
            sorted_ids = sorted(by_id, key=lambda c:(-by_id[c]['score'],c))
            assert sorted_ids == meta['ranking']['ranked_chunk_ids']
            assert all(by_id[c]['rank'] == rank for rank,c in enumerate(sorted_ids,1))
            for row in ranks:
                error = abs(row['score']-sum(w['contribution'] for w in row['provenance'].values() if w))
                max_error = max(max_error, error)
                assert error < 1e-12
            area = meta['area']['area']
            def recruit(scores):
                return recruit_with_verified_area(chunk_rows=list(chunks.values()), joint_scores=np.array(scores),
                    area_chunk_ids=area['chunk_ids'], area_provenance=area['provenance'], source_character_budget=None)
            baseline = recruit([by_id[c]['score'] for c in chunks])
            assert baseline['recruitment'] == meta['recruitment']
            on_order = baseline['recruitment']['selected_chunk_ids']
            assert on_order == meta['full_recovered_order']
            texts, _, on_credit, on_budget = deliver(on_order)
            assert texts == saved['contexts'] and on_credit == saved['context_ids'] and on_budget == meta['char_budget']
            off_scores = {c:(by_id[c]['provenance']['topic'] or {}).get('contribution',0.) for c in chunks}
            off = recruit([off_scores[c] for c in chunks])
            off_order = off['recruitment']['selected_chunk_ids']
            _, _, off_credit, off_budget = deliver(off_order)
            # Both treatments are now complete. Gold is only consulted below.
            gold = set(index['questions'][qid])
            assert gold, 'Failure-inclusive recall assumes nonempty reference ID sets'
            row = {'question_id':qid, 'product_group':qid.split('::')[0], 'gold_ids':len(gold)}
            for name, credit, budget in [('joint',on_credit,on_budget), ('auxiliaries_off',off_credit,off_budget)]:
                ids = set(map(str,credit)); hits = len(ids & gold)
                values = {'hits':hits, 'retrieved_ids':len(ids), 'delivered_chars':budget['chars']}
                assert budget['chars'] <= 72000
                sample = SingleTurnSample(retrieved_context_ids=credit, reference_context_ids=sorted(gold))
                for key, metric in metrics:
                    value = float(await metric.single_turn_ascore(sample))
                    denominator = len(ids) if key == 'context_precision_id' else len(gold)
                    assert (math.isnan(value) and not denominator) or abs(value-hits/denominator) < 1e-15
                    values[key] = value if math.isfinite(value) else None
                row[name] = values
            row['joint_only_gold_ids'] = sorted((set(on_credit)-set(off_credit)) & gold)
            row['off_only_gold_ids'] = sorted((set(off_credit)-set(on_credit)) & gold)
            rows.append(row)
            on_pos, off_pos = ({c:i+1 for i,c in enumerate(order)} for order in (on_order,off_order))
            off_rank = {c:i+1 for i,c in enumerate(sorted(chunks,key=lambda c:(-off_scores[c],c)))}
            for aid in sorted(gold):
                links = index['artifacts'][aid]
                pointers.write(json.dumps({'question_id':qid,'artifact_id':aid,
                    'joint_credited':aid in set(on_credit),'off_credited':aid in set(off_credit),
                    'chunks':[{'chunk_id':c,'joint_score_rank':by_id[c]['rank'],'off_score_rank':off_rank[c],
                               'joint_delivery_position':on_pos.get(c),'off_delivery_position':off_pos.get(c)} for c in links]})+'\n')
            print(json.dumps({'phase':'paired_replay','completed':len(rows),'expected_saved':completed['completed']}),flush=True)
    assert len(rows) == completed['completed'] and len(failed) == completed['failure_records']
    assert seen | set(failed) == set(expected)
    groups = defaultdict(list)
    for qid in expected:
        groups[qid.split('::')[0]].append(qid)
    summary = aggregate(rows, len(expected))
    result = {'summary':summary, 'product_groups':{g:aggregate([r for r in rows if r['question_id'] in ids],len(ids)) for g,ids in groups.items()},
              'questions':rows,'failed_question_ids':failed,'baseline_full_recruitment_and_text_delivery_parity':len(rows),
              'maximum_contribution_sum_error':max_error, 'ragas_version':importlib.metadata.version('ragas'),
              'deterministic_metric_evaluations':4*len(rows),'model_calls':0,
              'original_process_return_code':completed['return_code'],
              'limits':'Source-ID membership only; not exhaustive relevance, facet semantic validity, or answer quality.'}
    V.verify(plan)
    for path, expected_hash in T.read(out/'plan.json')['input_sha256'].items():
        assert sha(T.ROOT/path) == expected_hash
    T.write(out/'results.json',result)
    print(json.dumps({'phase':'completed',**summary,'product_groups':len(groups)},indent=2))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,required=True)
    args=parser.parse_args()
    asyncio.run(main(args.run))


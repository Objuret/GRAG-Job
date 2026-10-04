"""Run installed deterministic RAGAS ID metrics on the three frozen conditions.

No language models, question text, new answers or embeddings. The off condition's
source-ID list is reconstructed through the same saved scope and delivery helper.
"""
from __future__ import annotations
import asyncio
import gzip
import importlib.metadata
import json
import os
from pathlib import Path

os.environ['RAGAS_DO_NOT_TRACK']='true'
os.environ['RAGAS_DEBUG_TRACKING']='false'
import numpy as np
import facet_gold_pointer_ablation as B
import facet_gold_trace as T
from artefact.facet_scope_recruitment import recruit_with_verified_area
from ragas.dataset_schema import SingleTurnSample
from ragas.metrics._context_precision import IDBasedContextPrecision
from ragas.metrics._context_recall import IDBasedContextRecall

BASE=T.OUT
OUT=BASE/'id_metrics'


async def main():
    if (OUT/'results.json').exists():raise ValueError('Preserve completed metrics')
    numerical=T.read(BASE/'correspondence/numerical_outputs.json')
    for path,expected in numerical['input_sha256'].items():
        assert T.sha(T.ROOT/path)==expected, path
    verification=T.read(BASE/'verification.json')
    assert T.sha(BASE/'gold_source_index.json')==verification['index_sha256']
    assert T.sha(BASE/'chunk_delivery_index.json')==verification['unit_index_sha256']
    index=T.read(BASE/'gold_source_index.json')
    units=T.read(BASE/'chunk_delivery_index.json')
    graph=T.read(T.SNAPSHOT/'graph.json');chunks={c['chunkId']:c for c in graph['chunks']}
    paths=[Path(__file__),Path(B.__file__),Path(T.__file__),BASE/'gold_source_index.json',
           BASE/'chunk_delivery_index.json',BASE/'auxiliary_off/comparison.json',
           BASE/'correspondence/comparison.json',BASE/'correspondence/numerical_outputs.json']
    import inspect
    paths += [Path(inspect.getfile(IDBasedContextPrecision)),Path(inspect.getfile(IDBasedContextRecall))]
    B.freeze(OUT/'plan.json',{'source_sha256':{str(p.relative_to(T.ROOT)):T.sha(p) for p in paths},
        'ragas_version':importlib.metadata.version('ragas'),
        'metrics':['context_precision_id','context_recall_id'],
        'purpose':'Report both existing deterministic ID metrics, with no metric selection or ranking adjustment.',
        'conditions':['intended','auxiliaries_off','query_mismatch'],
        'aggregation':'Per-question metric then arithmetic mean; no pooling substituted.',
        'non_gold_policy':'Not in the citation set does not establish semantic irrelevance.',
        'no_calls':['Claude','generator','judge','embedder']})
    deliver=B.budget_helper(chunks,units)
    off_expected={r['question_id']:r for r in T.read(BASE/'auxiliary_off/comparison.json')['questions']}
    metrics=[('context_precision_id',IDBasedContextPrecision()),('context_recall_id',IDBasedContextRecall())]
    results=[]
    for record in numerical['records']:
        if record['condition']=='joint_symmetry':continue
        path=BASE/'correspondence'/record['file'];assert T.sha(path)==record['sha256']
        p=json.loads(gzip.decompress(path.read_bytes()))
        conditions=[('intended' if record['condition']=='baseline' else 'query_mismatch',p['credited_ids'],p['budget'])]
        if record['condition']=='baseline':
            ranked={r['chunk_id']:r for r in p['ranking_rows']}
            scores=np.array([(ranked[c]['provenance']['topic'] or {}).get('contribution',0.) for c in chunks])
            area=p['scoped']['area']
            off=recruit_with_verified_area(chunk_rows=list(chunks.values()),joint_scores=scores,
                area_chunk_ids=area['chunk_ids'],area_provenance=area['provenance'],source_character_budget=None)
            _,_,credit,budget=deliver(off['recruitment']['selected_chunk_ids'])
            conditions.append(('auxiliaries_off',credit,budget))
        for name,credit,budget in conditions:
            gold=index['questions'][p['question_id']]
            sample=SingleTurnSample(retrieved_context_ids=credit,reference_context_ids=gold)
            row={'question_id':p['question_id'],'condition':name,'retrieved_source_ids':len(set(credit)),
                 'gold_source_ids':len(set(gold)),'gold_source_hits':len(set(credit)&set(gold)),
                 'non_gold_source_ids':len(set(credit)-set(gold)),
                 'delivered_chars':budget['chars'],'metrics':{}}
            for alias,metric in metrics:
                # The public deterministic metric API receives IDs only.
                value=float(await metric.single_turn_ascore(sample))
                expected=row['gold_source_hits']/(row['retrieved_source_ids'] if alias=='context_precision_id' else row['gold_source_ids'])
                assert abs(value-expected)<1e-15
                row['metrics'][alias]=value
            if name=='auxiliaries_off':
                assert row['gold_source_hits']==off_expected[p['question_id']]['off_credited']
                assert row['metrics']['context_recall_id']==off_expected[p['question_id']]['off_recall']
            results.append(row)
    assert len(results)==30 and all(r['delivered_chars']==72000 for r in results)
    summary={}
    for name in ('intended','auxiliaries_off','query_mismatch'):
        subset=[r for r in results if r['condition']==name];assert len(subset)==10
        summary[name]={'questions':10,**{key:sum(r['metrics'][key] for r in subset)/10 for key,_ in metrics},
            'source_question_hits':sum(r['gold_source_hits'] for r in subset),
            'source_question_retrieved':sum(r['retrieved_source_ids'] for r in subset),
            'source_question_non_gold':sum(r['non_gold_source_ids'] for r in subset)}
    assert abs(summary['intended']['context_precision_id']-0.13196884098548148)<1e-14
    assert abs(summary['intended']['context_recall_id']-0.3305388769765506)<1e-14
    comparison=[]
    intended={r['question_id']:r for r in results if r['condition']=='intended'}
    for name in ('auxiliaries_off','query_mismatch'):
        subset=[r for r in results if r['condition']==name]
        comparison.append({'against':name,**{key:{'intended_better':sum(intended[r['question_id']]['metrics'][key]>r['metrics'][key] for r in subset),
            'intended_worse':sum(intended[r['question_id']]['metrics'][key]<r['metrics'][key] for r in subset),
            'ties':sum(intended[r['question_id']]['metrics'][key]==r['metrics'][key] for r in subset)} for key,_ in metrics}})
    output={'ragas_version':importlib.metadata.version('ragas'),'summary':summary,'paired_comparison':comparison,
        'rows':results,'deterministic_metric_evaluations':60,'language_model_calls':0,
        'baseline_reconciles_original_ragas':True,
        'meaning':'Both are actual installed RAGAS deterministic ID metrics; no new answer-quality or LLM judge evaluation.'}
    T.write(OUT/'results.json',output)
    print(json.dumps({k:output[k] for k in ('ragas_version','summary','paired_comparison','deterministic_metric_evaluations','language_model_calls','baseline_reconciles_original_ragas')},indent=2))


if __name__=='__main__':asyncio.run(main())

"""Reproduce cached smoke queries; one query/graph facet-correspondence control."""
from __future__ import annotations
import argparse
import dataclasses
import gzip
import json
import os
from pathlib import Path
import sys

for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[name]='4'
os.environ['HF_HUB_OFFLINE']='1'
os.environ['TRANSFORMERS_OFFLINE']='1'

import numpy as np
from threadpoolctl import threadpool_limits
import facet_gold_pointer_ablation as B
import facet_gold_trace as T
from arms import artefact_facet_joint as A
from artefact.facet_joint_candidate import FrozenFacetReference
from artefact.facet_retrieval_pipeline import retrieve_prepared_query
from artefact.facet_scope_recruitment import recruit_with_verified_area

ROOT,BASE=T.ROOT,T.OUT
OUT=BASE/'correspondence'
PERM=[0,2,3,4,1]


def save(path,obj):
    if path.exists():raise ValueError('Preserve existing output: '+str(path))
    T.write(path,obj)


def verify(hashes):
    for name,expected in hashes.items():
        assert T.sha(ROOT/name)==expected,'Input changed: '+name


def run():
    if (OUT/'started.json').exists():raise ValueError('Attempt exists; inspect it instead of silently restarting')
    source=T.DEFAULT_RUN/'arm_outputs.jsonl'
    prepared=A.prepare_over_corpus(ROOT/'data/corpus/Salesforce__HERB')
    paths=[Path(__file__),Path(A.__file__),Path(B.__file__),Path(T.__file__),source,
        ROOT/'docs/2026-09-22-gold-pointer-correspondence-protocol.md',BASE/'chunk_delivery_index.json']
    paths += [ROOT/p for p in prepared.provenance['source_sha256']]
    paths += [T.SNAPSHOT/p for p in ('graph.json','arrays.npz','graph_vectors.npz')]
    hashes={p.relative_to(ROOT).as_posix():T.sha(p) for p in paths}
    save(OUT/'plan.json',{'input_sha256':hashes,'permutation_new_column_from_old':PERM,
        'conditions':['baseline','query_only','joint_symmetry'],'coefficients':[1,.25,.25,.25,.25],
        'local_embedding_only':True,'language_model_calls':0,'gold_join':'Separate phase after numerical outputs.'})
    save(OUT/'started.json',{'status':'started','plan_sha256':T.sha(OUT/'plan.json')})
    units=T.read(BASE/'chunk_delivery_index.json')
    graph=T.read(T.SNAPSHOT/'graph.json')
    chunks={c['chunkId']:c for c in prepared.chunks}
    deliver=B.budget_helper(chunks,units)
    reference=FrozenFacetReference(tuple(prepared.reference.columns[i] for i in PERM))
    private=OUT/'private';private.mkdir(exist_ok=True)
    records=[]
    for case_number,saved in enumerate(T.rows(source),1):
        meta=saved['meta'];snap=meta['snapshot']
        for name,h in snap['source_sha256'].items():assert prepared.provenance['source_sha256'][name]==h
        assert snap['snapshot_sha256']==prepared.provenance['snapshot_sha256']
        interp=meta['interpreter'];tags=[r['t'] for r in interp['tags']]
        weights=np.array([[r['facets'][f] for f in T.FACETS] for r in interp['tags']])
        matrices,usage,recipe=A._query_cosines(interp['description'],tags,prepared)
        assert recipe['vector_sha256']==meta['embedding']['vector_sha256'],'Embedding reconstruction differs'
        np.savez_compressed(private/f'case_{case_number:02d}.npz',**matrices,query_facet_weights=weights)
        print(f'case {case_number}: local embedding hash matches',flush=True)
        area=meta['area']['area']
        original={r['chunk_id']:r for r in meta['ranking']['rows']}
        expected=np.array([original[c]['score'] for c in chunks])
        baseline=None
        for condition in ('baseline','query_only','joint_symmetry'):
            joint=condition=='joint_symmetry'
            with threadpool_limits(limits=4):
                result=retrieve_prepared_query(chunk_rows=prepared.chunks,coefficients=A.COEFFICIENTS,
                    source_character_budget=None,query_tag_ids=tags,edge_ids=prepared.edge_ids,
                    edge_tag_indices=prepared.edge_tag,edge_chunk_indices=prepared.edge_chunk,
                    edge_facets=prepared.edge_facets[:,PERM] if joint else prepared.edge_facets,
                    query_facet_weights=weights[:,PERM] if condition!='baseline' else weights,
                    reference=reference if joint else prepared.reference,
                    groups=prepared.groups,adjacency_pairs=prepared.adjacency_pairs,**matrices)
                scoped=recruit_with_verified_area(chunk_rows=prepared.chunks,joint_scores=result['ranking']['scores'],
                    area_chunk_ids=area['chunk_ids'],area_provenance=area['provenance'],source_character_budget=None)
            ranking=result['ranking'];order=scoped['recruitment']['selected_chunk_ids']
            contexts,_,credit,budget=deliver(order)
            error=float(np.max(np.abs(ranking['scores']-expected)))
            if condition=='baseline':
                assert error<1e-12
                assert ranking['ranked_chunk_ids']==meta['ranking']['ranked_chunk_ids']
                assert scoped['recruitment']==meta['recruitment']
                assert contexts==saved['contexts'] and credit==saved['context_ids'] and budget==meta['char_budget']
                baseline=(ranking['per_facet_scores'].copy(),scoped['recruitment'])
            elif joint:
                assert error<1e-12
                assert np.array_equal(ranking['per_facet_scores'],baseline[0][:,PERM])
                assert scoped['recruitment']==baseline[1]
                assert contexts==saved['contexts'] and credit==saved['context_ids'] and budget==meta['char_budget']
            safe_rows=[{**row,'provenance':T.safe_witnesses(row['provenance'],graph)} for row in ranking['rows']]
            payload={'question_id':saved['id'],'condition':condition,'ranking_rows':safe_rows,
                     'scoped':{k:scoped[k] for k in ('recruitment','area','stream_ids','policy')},
                     'order':order,'credited_ids':credit,'budget':budget}
            path=OUT/f'case_{case_number:02d}__{condition}.json.gz'
            with path.open('xb') as f:f.write(gzip.compress(json.dumps(payload,separators=(',',':')).encode(),mtime=0))
            records.append({'case':case_number,'question_id':saved['id'],'condition':condition,
                'file':path.name,'sha256':T.sha(path),'baseline_score_delta':error,
                'embedding_vector_hash_matched':True})
            print(f'case {case_number}: {condition} complete',flush=True)
    assert len(records)==30
    verify(hashes)
    save(OUT/'numerical_outputs.json',{'records':records,'input_sha256':hashes,
        'baseline_controls_passed':10,'symmetry_controls_passed':10,'language_model_calls':0,
        'local_embedding_reconstructions':10,'source_text_exported':False,'gold_joined':False})


def join():
    numerical=T.read(OUT/'numerical_outputs.json');verify(numerical['input_sha256'])
    index=T.read(BASE/'gold_source_index.json');units=T.read(BASE/'chunk_delivery_index.json')
    iv=T.read(BASE/'verification.json')
    assert T.sha(BASE/'gold_source_index.json')==iv['index_sha256']
    assert T.sha(BASE/'chunk_delivery_index.json')==iv['unit_index_sha256']
    graph=T.read(T.SNAPSHOT/'graph.json')
    originals={c['question_id']:c for c in T.read(BASE/'run_traces.json')[0]['cases']}
    cases,differences=[],[]
    for rec in numerical['records']:
        path=OUT/rec['file'];assert T.sha(path)==rec['sha256']
        if rec['condition']!='query_only':continue
        p=json.loads(gzip.decompress(path.read_bytes()))
        case=B.source_case(p['question_id'],{},p['ranking_rows'],p['scoped'],p['order'],
                          set(p['credited_ids']),p['budget'],index,units,graph)
        cases.append(case);old=originals[p['question_id']]
        left={s['artifact_id'] for s in old['sources'] if s['credited']}
        right={s['artifact_id'] for s in case['sources'] if s['credited']}
        n=case['gold_sources'];assert n
        differences.append({'question_id':p['question_id'],'gold_sources':n,
            'intended_recall':len(left)/n,'mismatch_recall':len(right)/n,
            'intended_only':sorted(left-right),'mismatch_only':sorted(right-left)})
    assert len(cases)==10
    summary={'questions':10,'baseline_controls':10,'joint_symmetry_controls':10,
        'macro_intended_recall':sum(d['intended_recall'] for d in differences)/10,
        'macro_mismatch_recall':sum(d['mismatch_recall'] for d in differences)/10,
        'intended_only_links':sum(len(d['intended_only']) for d in differences),
        'mismatch_only_links':sum(len(d['mismatch_only']) for d in differences),
        'questions_intended_better':sum(d['intended_recall']>d['mismatch_recall'] for d in differences),
        'questions_mismatch_better':sum(d['intended_recall']<d['mismatch_recall'] for d in differences),
        'questions_tied':sum(d['intended_recall']==d['mismatch_recall'] for d in differences),
        'language_model_calls':0,'local_embedding_reconstructions':10,'new_answers':0}
    save(OUT/'comparison.json',{'summary':summary,'questions':differences,
        'numerical_sha256':T.sha(OUT/'numerical_outputs.json'),
        'gold_index_sha256':T.sha(BASE/'gold_source_index.json')})
    traces=T.read(BASE/'auxiliary_off/run_traces.json')+[{'run':'Control: auxiliary query facets rotated (not a recommended policy)',
        'cases':cases,'summary':summary,'limits':'One correspondence control, not independent validation or a permutation distribution.'}]
    save(OUT/'run_traces.json',traces);T.render(OUT,index,traces)
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=['run','join']);args=parser.parse_args()
    (run if args.phase=='run' else join)()

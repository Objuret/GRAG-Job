"""Check concept dataflow on existing captures, without model calls or gold."""
import contextlib
import hashlib
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'prod'),str(ROOT/'test')]
OUT=ROOT/'output/research/2026-09-24-concept-baseline'
INPUTS=ROOT/'output/research/2026-09-22-retrieval-matrix/inputs'


def read(p):return json.loads(p.read_text(encoding='utf-8'))


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    import numpy as np
    rows=[]
    with (OUT/'verification.log').open('a',encoding='utf-8') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
        from arms import artefact_concept_baseline as A
        from artefact.concept_baseline import retrieve, ConceptGraph
        prepared=A.prepare_over_corpus(ROOT/'data/corpus/Salesforce__HERB')
        g=prepared.graph
        assert np.array_equal(g.topic,np.maximum(prepared.base.edge_facets[:,0],0))
        assert len(set(zip(g.edge_tag.tolist(),g.edge_chunk.tolist())))==len(g.edge_tag)
        cases=[c for c in read(INPUTS/'cases_manifest.json')['cases'] if c['cohort']=='smoke10']
        for case in cases:
            cid=case['case_id'];meta=read(INPUTS/case['meta'])
            private=read(ROOT/'output/research/2026-09-24-interpretation-comparison/private'/(cid+'.json'))
            assert hashlib.sha256((INPUTS/case['npz']).read_bytes()).hexdigest()==meta['npz_sha256']
            with np.load(INPUTS/case['npz'],allow_pickle=False) as data:
                matrices={k:data[k].copy() for k in ('query_tag_cosines','query_chunk_cosines','query_description_cosines')}
                weights=data['query_facet_weights'].copy()
            # Parser verification from already captured generation/score fields.
            raw={'description':private['description'],'tags':[{'t':t,'facets':dict(zip(A.J.FACETS,w.tolist()))} for t,w in zip(private['tags'],weights)]}
            parsed=A.parse_interpretation(raw)
            assert parsed['description']==private['description'] and len(parsed['tags'])==len(weights)
            r=A.rank_numeric(prepared,private['question'],matrices,weights)
            unique=r['unique_query_rows'];m=np.maximum(matrices['query_tag_cosines'][unique],0)
            expected=np.zeros(len(g.chunk_ids),bool)
            expected[g.edge_chunk[np.any(m[:,g.edge_tag]>0,axis=0)]]=True
            assert np.array_equal(expected,r['tag_candidates'])
            assert np.all(r['candidate'][expected])
            assert set(np.flatnonzero(r['candidate']))==set(r['order'].tolist())
            # Every adjusted edge contributes to its chunk; no max reducer.
            reconstructed=np.zeros_like(r['direct'])
            for qi in range(len(unique)):np.add.at(reconstructed[qi],g.edge_chunk,r['edge_values'][qi])
            assert np.array_equal(reconstructed,r['direct'])
            assert np.all(r['per_query']>=r['direct'])
            assert np.all((r['edge_adjustment']>=1)&(r['edge_adjustment']<=2))
            named=r['named'][r['order']]
            assert not np.any(np.diff(named.astype(int))>0)
            assert not g.topic.flags.writeable and not g.auxiliary.flags.writeable
            # Duplicate representation is not extra evidence.
            dup={k:(np.concatenate([v,v[:1]],axis=0) if k!='query_description_cosines' else v) for k,v in matrices.items()}
            duplicate=retrieve(g,dup,np.concatenate([weights,weights[:1]],axis=0),np.flatnonzero(r['named']).tolist())
            assert np.array_equal(r['scores'],duplicate['scores']) and np.array_equal(r['order'],duplicate['order'])
            # Full actual source serialization succeeds after ordering; never export text.
            ordered=[prepared.base.chunks[i] for i in r['order']]
            contexts,_,ids,budget=A._budget_contexts(ordered,72000,{})
            assert sum(map(len,contexts))==budget['chars']<=72000
            rows.append({'case_id':cid,'retained_all_tag_candidates':True,'all_edge_paths_accounted':True,
                         'raw_topic_preserved':True,'graph_never_reduces_direct_support':True,
                         'duplicate_query_invariant':True,'named_area_precedes_outside':True,
                         'delivery_resolved':True,'chunks':len(r['order']),'full_delivered':budget['kept'],
                         'characters':budget['chars'],'credited_source_ids':len(ids),
                         'order_sha256':hashlib.sha256(r['order'].tobytes()).hexdigest()})
            del contexts
        try:retrieve(prepared.base,matrices,weights)
        except TypeError:pass
        else:raise AssertionError('Rich input must be rejected')
    files=[ROOT/'test/artefact/concept_baseline.py',ROOT/'test/arms/artefact_concept_baseline.py',Path(__file__)]
    result={'status':'numeric_dataflow_verified_not_fresh_interpretation_or_quality','checks':rows,
            'cases':len(rows),'graph_areas':len(g.areas),'model_calls':0,'gold_read':False,
            'source_content_exported':False,'rich_input_rejected':True,
            'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    with (OUT/'verification.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps({'verified_cases':len(rows),'graph_areas':len(g.areas),'model_calls':0,'quality_evaluated':False}))


if __name__=='__main__':main()

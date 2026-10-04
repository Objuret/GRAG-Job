"""No-model exact ranking and source-delivery checks for both fixed leaders."""
import hashlib
import importlib
import json
import sys
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'prod'),str(ROOT/'test')]
from arms.artefact_v2 import _budget_contexts

def read(path):return json.loads(path.read_text(encoding='utf-8'))

def main():
    inputs=ROOT/'output/research/2026-09-22-retrieval-matrix/inputs'
    cases=[r for r in read(inputs/'cases_manifest.json')['cases'] if r['cohort']=='smoke10']
    assert len(cases)==10
    rows=[]
    for name,key in [('hits','best-total-hits'),('macro','best-macro-recall')]:
        arm=importlib.import_module('arms.artefact_facet_leader_'+name)
        prepared=arm.prepare_over_corpus(ROOT/'data/corpus/Salesforce__HERB')
        selection=read(ROOT/'output/research/2026-09-24-structural-selection-v3'/(key+'.json'))
        assert prepared.program==selection['program']
        for c in cases:
            meta=read(inputs/c['meta']);numeric=inputs/c['npz']
            assert hashlib.sha256(numeric.read_bytes()).hexdigest()==meta['npz_sha256']
            with np.load(numeric,allow_pickle=False) as data:
                matrices={k:data[k].copy() for k in ('query_tag_cosines','query_chunk_cosines','query_description_cosines')}
                weights=data['query_facet_weights'].copy()
            members=meta['area']['chunk_ids']
            area=None if members is None else np.array([x in set(members) for x in prepared.graph.chunk_ids])
            result,_=arm.rank_numeric(prepared,matrices,weights,area)
            old=next(r for r in read(ROOT/selection['source']/'cases'/(c['case_id']+'.json')) if r['program_id']==arm.SELECTED_ID)
            assert hashlib.sha256(result['order'].tobytes()).hexdigest()==old['order_sha256']
            ids=[prepared.graph.chunk_ids[i] for i in result['order']]
            at={chunk['chunkId']:chunk for chunk in prepared.base.chunks}
            contexts,source_lists,source_ids,budget=_budget_contexts([at[x] for x in ids],72000,{})
            assert ids[:budget['kept']]==old['full_chunk_ids'] and budget==old['budget']
            assert len(source_ids)==old['retrieved_ids']
            rows.append({'leader':name,'case_id':c['case_id'],'full_order_exact':True,'resolved_delivery_exact':True})
            print(json.dumps(rows[-1]),flush=True)
    out=ROOT/'output/research/2026-09-24-leader-gold-smokes/preflight.json'
    with out.open('x',encoding='utf-8') as f:json.dump({'checks':rows,'model_calls':0,'source_content_exported':False},f,indent=2)

if __name__=='__main__':main()

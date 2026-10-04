"""Verify all three frozen downstream controls before new SCORE calls."""
import contextlib
import hashlib
import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'prod'), str(ROOT/'test')]
from facet_interpretation_prepare import OUT, INPUTS, read, save


def main():
    import numpy as np
    rows = []
    with (OUT/'private/controls.log').open('a', encoding='utf-8') as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        from arms import artefact_facet_joint as joint
        from arms.artefact_v2 import _budget_contexts
        from artefact.facet_structural_landing import resolve_structural_area
        cases = [c for c in read(INPUTS/'cases_manifest.json')['cases'] if c['cohort']=='smoke10']
        for name in ('joint','hits','macro'):
            arm = joint if name=='joint' else importlib.import_module('arms.artefact_facet_leader_'+name)
            prepared = arm.prepare_over_corpus(ROOT/'data/corpus/Salesforce__HERB')
            base = prepared if name=='joint' else prepared.base
            by_id = {c['chunkId']: c for c in base.chunks}
            if name!='joint':
                key = 'best-total-hits' if name=='hits' else 'best-macro-recall'
                selected = read(ROOT/'output/research/2026-09-24-structural-selection-v3'/(key+'.json'))
                assert prepared.program==selected['program']
            for case in cases:
                cid=case['case_id']; meta=read(INPUTS/case['meta']); query=read(OUT/'private'/(cid+'.json'))
                with np.load(INPUTS/case['npz'],allow_pickle=False) as data:
                    matrices={k:data[k].copy() for k in ('query_tag_cosines','query_chunk_cosines','query_description_cosines')}
                    weights=data['query_facet_weights'].copy()
                assert np.array_equal(weights,query['historical_weights'])
                if name=='joint':
                    result=joint._rank(prepared,query['question'],query,weights,matrices)
                    ids=result['recruitment']['selected_chunk_ids']
                    assert ids==meta['baseline_order']
                    expected_budget=meta['baseline_budget']
                else:
                    area_ids,_=resolve_structural_area(query['question'],base.structural_index)
                    saved_ids=meta['area']['chunk_ids']
                    assert (None if area_ids is None else set(area_ids))==(None if saved_ids is None else set(saved_ids))
                    mask=None if area_ids is None else np.array([x in area_ids for x in prepared.graph.chunk_ids])
                    result,_=arm.rank_numeric(prepared,matrices,weights,mask)
                    old=next(r for r in read(ROOT/selected['source']/'cases'/(cid+'.json')) if r['program_id']==arm.SELECTED_ID)
                    assert hashlib.sha256(result['order'].tobytes()).hexdigest()==old['order_sha256']
                    ids=[prepared.graph.chunk_ids[i] for i in result['order']]
                    expected_budget=old['budget']
                contexts,_,credited,budget=_budget_contexts([by_id[c] for c in ids],72000,{})
                assert budget==expected_budget
                if name=='joint':
                    assert ids[:len(contexts)]==meta['baseline_delivered_chunk_ids']
                    assert credited==meta['baseline_context_ids']
                else:
                    assert ids[:budget['kept']]==old['full_chunk_ids']
                    assert len(credited)==old['retrieved_ids']
                rows.append({'program':name,'case_id':cid,'order_exact':True,'delivery_exact':True})
                del contexts
    assert len(rows)==30
    save(OUT/'control-verification.json',{'checks':rows,'new_model_calls':0,'source_text_exported':False})
    print(json.dumps({'exact_controls':len(rows),'programs':3,'cases':10,'model_calls':0}))


if __name__=='__main__':
    main()

"""Verify bridge delivery metrics, parent seals and unchanged full rankings."""
import argparse
import json
from pathlib import Path
from facet_program_lab import L
from verify_facet_program_results import verify


def check(out):
    plan=L.read(out/'plan.json');verification=verify(out)
    if not verification['population_complete']:raise ValueError('Population not complete')
    if L.read(out/'status.json')['status']!='complete':raise ValueError('Runner not terminal complete')
    for name,digest in plan['parent_sha256'].items():
        assert L.digest(L.ROOT/name)==digest,name
    parent=L.ROOT/'output/research/2026-09-24-query-priority'
    seed=next(p['integration_parent'] for p in plan['programs'] if p['id']=='query_priority_directed_0001')
    controls={'query_priority_directed_0000':'query_priority_reference','query_priority_directed_0001':seed}
    fields=('order_sha256','full_chunk_ids','budget','hits','gold_count','retrieved_ids','recall_id','precision_id','f1_id')
    checked=0
    for cid in plan['case_ids']:
        current={r['program_id']:r for r in L.read(out/'cases'/(cid+'.json'))}
        original={r['program_id']:r for r in L.read(parent/'cases'/(cid+'.json'))}
        for new,old in controls.items():
            for field in fields:assert current[new][field]==original[old][field],(cid,new,field)
            checked+=1
    return {'verification':verification,'parent_hashes_verified':True,'unchanged_full_order_delivery_comparisons':checked,
            'controls':controls,'smoke_only':plan.get('smoke_only',False)}


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,default=L.ROOT/'output/research/2026-09-24-query-priority-directed')
    a=ap.parse_args();result=check(a.out);L.write_new(a.out/'control-parity.json',result);print(json.dumps(result))

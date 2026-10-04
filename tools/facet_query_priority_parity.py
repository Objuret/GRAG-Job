"""Exact saved-order/delivery parity against the original tag-frontier population."""
import argparse
import json
from pathlib import Path
from facet_program_lab import L


def verify(out,parent):
    plan=L.read(out/'plan.json');oldplan=L.read(parent/'plan.json')
    assert set(plan['case_ids'])<=set(oldplan['case_ids'])
    controls={p['id']:p['id'].replace('query_priority_','tag_frontier_').replace('_scalar_', '_outgoing_max_queries_')
        for p in plan['programs'] if p.get('query_priority',{}).get('method')=='scalar' or p['id'].endswith('_control')}
    checked=0
    for cid in plan['case_ids']:
        current={r['program_id']:r for r in L.read(out/'cases'/(cid+'.json'))}
        previous={r['program_id']:r for r in L.read(parent/'cases'/(cid+'.json'))}
        for a,b in controls.items():
            x={k:v for k,v in current[a].items() if k not in ('program_id','seconds')}
            y={k:v for k,v in previous[b].items() if k not in ('program_id','seconds')}
            # Timing fields are implementation accounting, not semantic parity.
            fields=('order_sha256','full_chunk_ids','budget','hits','gold_count','retrieved_ids','recall_id','precision_id','f1_id')
            for k in fields:assert x[k]==y[k],(cid,a,k)
            checked+=1
    return {'cases':len(plan['case_ids']),'controls':len(controls),'exact_full_order_and_delivery_comparisons':checked,
            'parent':str(parent),'smoke_only':plan.get('smoke_only',False)}


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--parent',type=Path,default=L.ROOT/'output/research/2026-09-24-tag-frontier-programs')
    a=ap.parse_args();r=verify(a.out,a.parent);L.write_new(a.out/'control-parity.json',r);print(json.dumps(r))

"""Optimistic representation diagnosis on inspected labels, not a fitted candidate.

Ask whether any common nonnegative slopes can express every consistently decisive
reference order. A feasible answer is not validation; an infeasible answer shows
that retuning these five slopes cannot express this particular reference set.
Reference disagreements are not silently converted to consensus labels.
"""
from pathlib import Path
import argparse
import json
import numpy as np
from scipy.optimize import linprog

def feasible(x):
    if not len(x):return True
    r=linprog(np.zeros(x.shape[1]),A_ub=-x,b_ub=-np.ones(len(x)),bounds=(0,None),method='highs')
    if r.status not in (0,2):raise RuntimeError(r.message)
    if r.success and np.min(x@r.x)<1-1e-6:raise RuntimeError('Solver did not establish requested margins')
    return bool(r.success)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--source',type=Path,required=True)
    p=ap.parse_args().source;v=json.loads((p/'validation.json').read_text());cases=v['predictions']
    byid={cid:[c for c in cases if c['id']==cid] for cid in sorted({c['id'] for c in cases})}
    cc=[rs[0] for rs in byid.values() if len(rs)==2 and rs[0]['y']==rs[1]['y'] and rs[0]['y']<2]
    output={'protocol':__doc__,'consistent_decisive_comparisons':len(cc),
        'scale':'Strict positive margins can be rescaled to at least one; this is homogeneous feasibility, not a calibrated utility.',
        'sources':{}}
    for source in ('direct','frozen_reference','conditional'):
        x=np.array([np.array(c[source+'_features'])*(1 if c['y']==0 else -1) for c in cc])
        ok=feasible(x);core=list(range(len(cc)))
        if not ok:
            for i in list(core):
                smaller=[j for j in core if j!=i]
                if not feasible(x[smaller]):core=smaller
        output['sources'][source]={'common_nonnegative_coefficients_feasible':ok,
            'dominated_or_indistinguishable_preferred_candidates':[cc[i]['id'] for i,r in enumerate(x) if (r<=0).all()],
            'one_inclusion_minimal_infeasible_subset':[] if ok else [{'case':cc[i]['id'],'signed_features':x[i].tolist()} for i in core],
            'per_subject_feasible':{d:feasible(x[[c['domain']==d for c in cc]]) for d in sorted({c['domain'] for c in cc})}}
    (p/'feasibility.json').write_text(json.dumps(output,indent=2)+'\n',encoding='utf-8');print(json.dumps(output,indent=2))

if __name__=='__main__':main()

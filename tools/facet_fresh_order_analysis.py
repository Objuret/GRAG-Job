"""Evaluate the declared interval-order extension, without fitting any weights."""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'test'),str(ROOT/'tools')]
from artefact.facet_partial_order import interval_order
from facet_corpus_ordinal_analysis import reversals

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',type=Path,required=True)
    p=ap.parse_args().source
    validation=json.loads((p/'validation.json').read_text())
    baseline=json.loads((p/'description_baseline.json').read_text())
    if validation['manifest_sha256']!=baseline['manifest_sha256']:
        raise ValueError('Inputs refer to different manifests')
    scores=baseline['scores'];cases=validation['predictions'];rows=[]
    for c in cases:
        ids=[f"{c['domain']}_{c['qi']}_{c[s]}" for s in ('a','b')]
        lo,hi=zip(*(c['score_intervals'][s] for s in ('a','b')))
        order=interval_order(ids,lo,hi,[scores[cid] for cid in ids])
        base=sorted(ids,key=lambda cid:(-scores[cid],cid))
        rows.append({**{k:c[k] for k in ('id','domain','qi','repeat','y')},
            'baseline_sign':1 if base[0]==ids[0] else -1,
            'order_sign':1 if order[0]==ids[0] else -1,
            'strict_sign':c['strict_sign']})
    def summary(field):
        gap=np.array([r[field] for r in rows]);y=np.array([r['y'] for r in rows]);dec=y<2
        ok=((gap>0)&(y==0))|((gap<0)&(y==1))
        return {'correct_readings':int(ok[dec].sum()),'decisive_readings':int(dec.sum()),
            **reversals(cases,gap)}
    changed=[r for r in rows if r['baseline_sign']!=r['order_sign']]
    result={'protocol':__doc__,'plan':json.loads((p/'ranking_followup_plan.json').read_text()),
        'input_sha256':{name:hashlib.sha256((p/name).read_bytes()).hexdigest() for name in
            ('validation.json','description_baseline.json','ranking_followup_plan.json')},
        'methods':{name:summary(field) for name,field in [('description_baseline','baseline_sign'),('strict_interval_extension','order_sign')]},
        'changed_readings':len(changed),'changed_distinct_comparisons':len({r['id'] for r in changed}),
        'changes_to_reference_agreement':sum(r['y']<2 and (r['order_sign']>0)==(r['y']==0) for r in changed),
        'changes_away_from_reference':sum(r['y']<2 and (r['order_sign']>0)!=(r['y']==0) for r in changed),
        'predictions':rows}
    (p/'order_analysis.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='predictions'},indent=2))

if __name__=='__main__':main()

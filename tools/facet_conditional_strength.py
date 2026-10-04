"""Declared exploratory strength-times-compatibility follow-up; no new model calls."""
from pathlib import Path
import argparse
import json
import sys
import numpy as np
from threadpoolctl import threadpool_limits

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'test')]
from facet_conditional_match import CODES
from facet_tradeoff_experiment import FACETS,metrics
from artefact.facet_tradeoff import crossfit_nonnegative
from facet_corpus_ordinal_analysis import reversals

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--corpus',type=Path,required=True);ap.add_argument('--conditional',type=Path,required=True)
    args=ap.parse_args();p=args.conditional
    plan=json.loads((p/'strength_followup_plan.json').read_text())
    manifest=json.loads((p/'manifest.json').read_text());readings={}
    for j in manifest['jobs']:
        r=json.loads((p/(j['id']+'.json')).read_text())
        for cid,vs in r['answer'].items():readings.setdefault(cid,[]).append([CODES[vs[f]['status']] for f in FACETS])
    match={k:np.mean(v,axis=0) for k,v in readings.items()}
    original=json.loads((args.corpus/'analysis.json').read_text())
    cases=original['sources']['direct']['fitted_products']['predictions']
    a,b=[json.loads((args.corpus/f'graph_{i}.json').read_text())['answer'] for i in (0,1)]
    direct={k:np.array([np.mean([v[k][f] for v in (a,b) if k in v]) for f in FACETS]) for k in set(a)|set(b)}
    z=json.loads((args.corpus/'frozen_scores.json').read_text())
    sources={'direct':direct,'frozen_reference':dict(zip(z['keys'],np.array(z['values'])))}
    y=np.array([c['y'] for c in cases]);groups=np.array([c['domain'] for c in cases]);result={'plan':plan,'sources':{}}
    for name,edge in sources.items():
        X=[]
        for c in cases:
            q=np.array(original['query_values'][f"{c['domain']}_{c['qi']}"])
            a,b=[f"{c['domain']}_{c['qi']}_{c[side]}" for side in ('a','b')]
            va,vb=[edge[f"{c['domain']}_{c[side]}"] for side in ('a','b')]
            X.append(q*(va*match[a]-vb*match[b]))
        X=np.array(X);gap=X.sum(axis=1);decided=y<2
        equal={'correct':int((((gap>1e-12)&(y==0))|((gap < -1e-12)&(y==1)))[decided].sum()),
            'decisive':int(decided.sum()),'resolved':int((abs(gap[decided])>1e-12).sum()),**reversals(cases,gap)}
        fitted=crossfit_nonnegative(X,y,groups,penalties=[.001,.01,.1,1.])
        result['sources'][name]={'equal':equal,'fitted':{
            'metrics':metrics(fitted['probabilities'],y,fitted['gap'],np.ones(len(y))),
            **reversals(cases,fitted['gap']),'folds':fitted['folds']},
            'predictions':[{**c,'equal_gap':float(gap[i]),'fitted_gap':float(fitted['gap'][i]),
                'probabilities':fitted['probabilities'][i].tolist()} for i,c in enumerate(cases)]}
    (p/'strength_analysis.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({n:{'equal':r['equal'],'fitted':{k:v for k,v in r['fitted'].items() if k!='folds'}} for n,r in result['sources'].items()},indent=2))

if __name__=='__main__':
    with threadpool_limits(limits=1):main()

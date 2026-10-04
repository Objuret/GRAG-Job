"""Analyze the exploratory ordinal corpus probe without replacing earlier results."""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path
import sys

import numpy as np
from threadpoolctl import threadpool_limits

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'prod'),str(ROOT/'test'),str(ROOT/'tools')]
from artefact.facet_tradeoff import crossfit_nonnegative
from facet_tradeoff_experiment import FACETS, metrics, lex_direction


def reversals(cases,gap):
    byid={cid:[(i,c) for i,c in enumerate(cases) if c['id']==cid] for cid in {c['id'] for c in cases}}
    supported,ok=0,0
    for group in sorted({c['domain'] for c in cases}):
        query_ids=sorted({c['qi'] for c in cases if c['domain']==group})
        for qa,qb in itertools.combinations(query_ids,2):
            aa,bb=byid[f'{group}_{qa}_0_1'],byid[f'{group}_{qb}_0_1']
            ay,by=[c['y'] for _,c in aa],[c['y'] for _,c in bb]
            if len(ay)==len(by)==2 and len(set(ay))==len(set(by))==1 and {ay[0],by[0]}=={0,1}:
                supported+=1
                ga,gb=gap[aa[0][0]],gap[bb[0][0]]
                ok+=bool(abs(ga)>1e-12 and abs(gb)>1e-12 and ((ga>0)==(ay[0]==0)) and ((gb>0)==(by[0]==0)))
    return {'reader_supported_reversals':supported,'reversals_reproduced':ok}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--corpus',type=Path,required=True)
    ap.add_argument('--ordinal',type=Path,required=True)
    args=ap.parse_args()
    base=json.loads((args.corpus/'analysis.json').read_text())
    manifest=json.loads((args.ordinal/'manifest.json').read_text())
    cases=base['sources']['direct']['fitted_products']['predictions']
    y=np.array([c['y'] for c in cases]); groups=np.array([c['domain'] for c in cases])
    q=np.array([base['query_values'][f"{c['domain']}_{c['qi']}"] for c in cases])
    output={'protocol':manifest['protocol'],'analysis_prespecified':manifest['analysis_prespecified'],'variants':{}}
    for variant in ('plain','evidence'):
        reads={};checks=[]
        for job in manifest['jobs']:
            if job['variant']!=variant:
                continue
            r=json.loads((args.ordinal/(job['id']+'.json')).read_text())
            checks.extend(r['quote_checks'])
            for cid,choices in r['answer'].items():
                signs=[]
                for f in FACETS:
                    choice=choices[f] if variant=='plain' else choices[f]['choice']
                    win=None if choice=='equal' else job['orientation_not_sent'][cid][0 if choice=='A' else 1]
                    signs.append(0. if win is None else 1. if win==0 else -1.)
                reads.setdefault(cid,[]).append(signs)
        if set(reads)!=set(groups):
            raise RuntimeError('at least one tag pair has no ordinal reading')
        delta=np.array([np.mean(reads[c['domain']],axis=0) for c in cases])
        block={'pair_facet_signs':{k:np.mean(v,axis=0).tolist() for k,v in reads.items()},
               'orientation_consistency_by_facet':{f:float(np.mean([v[0][i]==v[1][i] for v in reads.values() if len(v)==2])) for i,f in enumerate(FACETS)},
               'quote_checks':{'total':len(checks),'not_exact':sum(not c['exact_substring'] for c in checks),'over_word_limit':sum(c['words']>40 for c in checks)},'methods':{}}
        for name,x in [('static_facets',delta),('equal_products',(q*delta).sum(axis=1,keepdims=True)),('fitted_products',q*delta)]:
            fitted=crossfit_nonnegative(x,y,groups,penalties=[.001,.01,.1,1.])
            block['methods'][name]={'metrics':metrics(fitted['probabilities'],y,fitted['gap'],np.ones(len(y))),
                'folds':fitted['folds'],**reversals(cases,fitted['gap']),
                'predictions':[{**c,'gap':float(fitted['gap'][i]),'probabilities':fitted['probabilities'][i].tolist()} for i,c in enumerate(cases)]}
        lex=np.array([lex_direction(qq,d) for qq,d in zip(q,delta)])
        decided=y<2;correct=((lex>0)&(y==0))|((lex<0)&(y==1))
        block['methods']['query_ordered_lexicographic']={'decided_direction_agreement':float(correct[decided].mean()),
            'unresolved':int((lex==0).sum()),**reversals(cases,lex)}
        output['variants'][variant]=block
    native_path=args.corpus/'native_reranker_analysis.json'
    if native_path.exists():
        native=json.loads(native_path.read_text())
        nc=native['predictions'];ng=np.array([c['gap'] for c in nc])
        output['native_reranker_control']={'metrics':native['metrics'],**reversals(nc,ng)}
    (args.ordinal/'analysis.json').write_text(json.dumps(output,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'variants':{v:{'consistency':b['orientation_consistency_by_facet'],'quotes':b['quote_checks'],
        'methods':{m:{k:x for k,x in r.items() if k not in ('folds','predictions')} for m,r in b['methods'].items()}} for v,b in output['variants'].items()},
        'native':output.get('native_reranker_control')},indent=2))


if __name__=='__main__':
    with threadpool_limits(limits=1):
        main()

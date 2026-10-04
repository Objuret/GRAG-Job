"""Evaluate frozen methods on fresh corpus judgements; never fit on these labels."""
from pathlib import Path
import argparse
from collections import Counter
import hashlib
import json
import sys
import numpy as np
from threadpoolctl import threadpool_limits

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'test'),str(ROOT/'prod')]
from facet_tradeoff_experiment import FACETS,frozen_scores,metrics,lex_direction
from facet_conditional_match import CODES
from facet_corpus_ordinal_analysis import reversals
from artefact.facet_tradeoff import comparison_probabilities

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',type=Path,required=True);ap.add_argument('--conditional',type=Path,required=True)
    args=ap.parse_args();p=args.source
    manifest=json.loads((p/'manifest.json').read_text());cases=[];values={};missing={};cost=0
    raw={}
    for j in manifest['jobs']:
        r=json.loads((p/(j['id']+'.json')).read_text())
        if any(r[k+'_sha256']!=hashlib.sha256(j[k].encode()).hexdigest() for k in ('system','user')):raise ValueError('Input signature changed')
        missing[j['id']]=r['missing_cases'];cost+=r['cost_usd_reported'];raw[j['id']]=r['answer']
        if j['role']=='preference':
            for cid,label in r['answer'].items():
                d,qi,a,b=cid.split('_');a,b=int(a),int(b)
                winner=None if label=='equal' else j['orientation_not_sent'][cid][0 if label=='A' else 1]
                cases.append({'id':cid,'domain':d,'qi':int(qi),'a':a,'b':b,'repeat':j['repeat'],
                    'y':2 if winner is None else 0 if winner==a else 1})
    for role in ('query','graph'):
        a,b=raw[role+'_0'],raw[role+'_1']
        expected=set(next(j['case_ids'] for j in manifest['jobs'] if j['id']==role+'_0'))
        if set(a)|set(b)!=expected:raise ValueError('A numerical input has no reading')
        values[role]={k:np.array([np.mean([r[k][f] for r in (a,b) if k in r]) for f in FACETS]) for k in expected}
    conditional_manifest=json.loads((args.conditional/'manifest.json').read_text());readings={};quality={};checks=[];conditional_cost=0
    for j in conditional_manifest['jobs']:
        r=json.loads((args.conditional/(j['id']+'.json')).read_text())
        if any(r[k+'_sha256']!=hashlib.sha256(j[k].encode()).hexdigest() for k in ('system','user')):raise ValueError('Conditional signature changed')
        missing[j['id']]=r['missing'];checks.extend(r['quote_checks']);conditional_cost+=r['cost_usd_reported']
        for cid in j['info_not_sent']:
            ranges=[]
            if cid in r['answer']:readings.setdefault(cid,[]).append([CODES[r['answer'][cid][f]['status']] for f in FACETS])
            for f in FACETS:
                if cid not in r['answer']:ranges.append((-1.,1.));continue
                v=r['answer'][cid][f];quote=v['quote'];code=CODES[v['status']]
                valid=quote in j['info_not_sent'][cid]['passage'] and len(quote.split())<=45 and bool(quote)==(v['status'] in ('supports','conflicts'))
                ranges.append((code,code) if valid else (-1.,1.))
            quality.setdefault(cid,[]).append(ranges)
    if set(readings)!=set(quality):raise ValueError('A conditional input has no reading')
    match={k:np.mean(v,axis=0) for k,v in readings.items()}
    lower={k:np.min(np.array(v)[:,:,0],axis=0) for k,v in quality.items()}
    upper={k:np.max(np.array(v)[:,:,1],axis=0) for k,v in quality.items()}
    z=frozen_scores(manifest,p);edge_sources={'direct':values['graph'],'frozen_reference':dict(zip(z['keys'],np.array(z['values'])))}
    features={k:[] for k in ('direct','frozen_reference','conditional')};robust=[];lex=[];score_intervals=[]
    for c in cases:
        q=values['query'][f"{c['domain']}_{c['qi']}"]
        a,b=[f"{c['domain']}_{c['qi']}_{c[s]}" for s in ('a','b')]
        delta=match[a]-match[b];features['conditional'].append(q*delta);lex.append(lex_direction(q,delta))
        lo=float(q@(lower[a]-upper[b]));hi=float(q@(upper[a]-lower[b]))
        robust.append(1 if lo>1e-12 else -1 if hi < -1e-12 else 0)
        score_intervals.append({'a':[float(q@lower[a]),float(q@upper[a])],
            'b':[float(q@lower[b]),float(q@upper[b])]})
        for source,edge in edge_sources.items():
            features[source].append(q*(edge[f"{c['domain']}_{c['a']}"]-edge[f"{c['domain']}_{c['b']}"]))
    y=np.array([c['y'] for c in cases]);byid={cid:[c['y'] for c in cases if c['id']==cid] for cid in {c['id'] for c in cases}}
    mass=np.array([1/len(byid[c['id']]) for c in cases]);decisive=y<2
    def direction(gap):
        gap=np.array(gap);ok=((gap>1e-12)&(y==0))|((gap < -1e-12)&(y==1));resolved=decisive&(abs(gap)>1e-12)
        return {'correct_readings':int(ok[decisive].sum()),'decisive_readings':int(decisive.sum()),
            'resolved_decisive_readings':int(resolved.sum()),'agreement_when_resolved':float(ok[resolved].mean()) if resolved.any() else None,
            **reversals(cases,gap)}
    result={'protocol':__doc__,'manifest_sha256':hashlib.sha256((p/'manifest.json').read_bytes()).hexdigest(),
        'preferences':{'readings':len(cases),'distinct':len(byid),'repeat_consistent':sum(len(v)==2 and v[0]==v[1] for v in byid.values()),'outcomes':dict(Counter(int(v) for v in y))},
        'missing':missing,'cost_usd_reported':{'numeric_and_preference':cost,'conditional':conditional_cost},
        'quote_checks':{'fields':len(checks),'not_exact':sum(not c['exact'] for c in checks),'too_long':sum(not c['within_limit'] for c in checks),'presence_mismatch':sum(not c['quote_presence_correct'] for c in checks)},
        'query_values':{k:v.tolist() for k,v in values['query'].items()},
        'methods':{'conditional_strict_envelope':direction(robust),'conditional_lex':direction(lex)},'predictions':cases}
    for name,x in features.items():
        x=np.array(x);gap=x.sum(axis=1);models=manifest['frozen_models'][name]
        prob=np.mean([comparison_probabilities(x,m['coefficients'],m['tie_log']) for m in models],axis=0)
        # The declared probability ensemble determines its prediction. A mean
        # utility-gap sign is a separate diagnostic, not silently substituted.
        pgap=prob[:,0]-prob[:,1]
        mean_gap=np.mean([x@np.array(m['coefficients']) for m in models],axis=0)
        result['methods'][name+'_equal']=direction(gap)
        result['methods'][name+'_frozen_ensemble']={'metrics':metrics(prob,y,pgap,mass),**direction(pgap),
            'mean_utility_vs_probability_sign_disagreements':int((np.sign(pgap)!=np.sign(mean_gap)).sum())}
        for i,c in enumerate(cases):c.update({name+'_features':x[i].tolist(),name+'_equal_gap':float(gap[i]),
            name+'_frozen_gap':float(pgap[i]),name+'_frozen_probabilities':prob[i].tolist()})
    for i,c in enumerate(cases):c.update({'strict_sign':int(robust[i]),'lex_sign':int(lex[i]),'score_intervals':score_intervals[i]})
    distinct={c['id']:c for c in cases}
    result['conditional_comparisons_with_opposing_advantages']=sum(any(v>1e-12 for v in c['conditional_features']) and any(v < -1e-12 for v in c['conditional_features']) for c in distinct.values())
    (p/'validation.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('query_values','predictions')},indent=2))

if __name__=='__main__':
    with threadpool_limits(limits=1):main()

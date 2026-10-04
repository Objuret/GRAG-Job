"""Corpus-inspired contrast diagnosis; constructed examples, not corpus facts.

Four subjects, two explicitly opposed requests each, and a fixed passage pair.
Repeat the pair with identical off-topic source material prepended to both sides.
Expected winners are declared from the constructed statements before collection.
Read scalar query/graph facets with the current prompt and a separate clarification
condition; compare a query-aware full-text preference control. No fitting or
benchmark gold. This tests necessary capabilities, not corpus retrieval quality.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import random
import sys

import numpy as np
from scipy.optimize import linprog

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'test'),str(ROOT/'prod')]
from facet_tradeoff_readings import jobs, run, PREFERENCE, FACETS
from facet_tradeoff_experiment import lex_direction

CLARIFICATION = """
Additional user clarification: a report that performs analysis and a record of
someone sharing that report can both carry activity. The query determines which
is useful. Do not rank one activity universally above the other merely for being
performed by the document versus recorded in it. This clarification does not
prescribe numerical scores or turn relevance into facet importance.
"""


def make_cases():
    corpus=json.loads((ROOT/'output/research/2026-09-21-facet-validity/corpus_tradeoff/manifest.json').read_text())
    d=next(d for d in corpus['cases']['domains'] if d['id']=='g2')
    distractor=d['texts'][0].split('Fix SHAP Value Calculation for Accurate Feature Attribution',1)[0].strip()
    rows=[
        ('data distribution',
         ['A record of an implemented correction to SHAP calculations for data distribution edge cases.',
          'A proposal for correcting SHAP calculations for data distribution edge cases, with implementation still pending.'],
         ['The SHAP calculation logic has been updated to account for data distribution edge cases. The fix has been tested against known outputs. Implementation and testing are complete.',
          'An update to the SHAP calculation logic is proposed to account for data distribution edge cases. Testing against known outputs is planned. Implementation and testing have not started.']),
        ('user satisfaction scores',
         ['A description of an operating process that currently collects user satisfaction scores.',
          'A description of a proposed process for collecting user satisfaction scores that has not started operating.'],
         ['User satisfaction scores are collected through quarterly surveys. The feedback process is in operation and its results are integrated into development sprints.',
          'User satisfaction scores will be collected through quarterly surveys. The feedback process is proposed and has not started operating; its results will be integrated into development sprints.']),
        ('incident response plan',
         ['A record that an incident response plan has already been established.',
          'A record that an incident response plan is proposed but has not yet been established.'],
         ['An incident response plan has been established to handle security breaches, including detection, containment, eradication, recovery, and communication with stakeholders.',
          'An incident response plan is proposed but has not yet been established. It would handle security breaches, including detection, containment, eradication, recovery, and communication with stakeholders.']),
        ('market research report',
         ['A record of someone sharing a market research report with colleagues.',
          'A market research report presenting its analysis of market demand and adoption trends.'],
         ['Emma shared the market research report with her colleagues in the planning channel. The message contains a link to the report; its analysis is not reproduced here.',
          'Market Research Report. Our analysis finds growing demand for workflow automation. Adoption is driven by the shift to remote work and the need for integrated communication tools. These findings identify a market opportunity for intelligent notifications.'])]
    domains=[]
    for i,(tag,descriptions,texts) in enumerate(rows):
        domains.append({'id':f'c{i}','tag':tag,'descriptions':descriptions,
            'texts':texts+[distractor+'\n\n'+s for s in texts],
            'expected_winners_not_sent':[0,1],
            'construction':'Status contrast' if i<3 else 'Activity-kind contrast; not a minimal tense edit'})
    return {'purpose':__doc__,'domains':domains,'distractor_source_chunk':d['source_chunks'][0],
            'distractor_exact_text':distractor}


def prepare(out):
    cases=make_cases()
    numeric=[j for j in jobs(cases) if j['role']!='preference']
    alljobs=[]
    for condition in ('current','clarified'):
        for j in numeric:
            alljobs.append({**j,'id':condition+'_'+j['id'],
                'system':j['system']+(CLARIFICATION if condition=='clarified' else ''),
                'condition':condition})
    for repeat in range(2):
        items=[]; orientation={}; expected={}
        rng=random.Random(92300)
        for d in cases['domains']:
            for qi,description in enumerate(d['descriptions']):
                for context,(a,b) in [('short',(0,1)),('mixed',(2,3))]:
                    cid=f"{d['id']}_{qi}_{context}"
                    ai,bi=(b,a) if rng.choice([False,True]) ^ bool(repeat) else (a,b)
                    orientation[cid]=[ai,bi]
                    expected[cid]=qi+(2 if context=='mixed' else 0)
                    items.append((cid,f"Case {cid}\nSought content: {description}\n\nPassage A:\n{d['texts'][ai]}\n\nPassage B:\n{d['texts'][bi]}"))
        random.Random(92300+repeat).shuffle(items)
        alljobs.append({'id':f'preference_{repeat}','role':'preference','system':PREFERENCE,
            'user':'\n\n'.join(v for _,v in items),'case_ids':[cid for cid,_ in items],
            'orientation_not_sent':orientation,'expected_winner_not_sent':expected})
    manifest={'protocol':__doc__,'model':'claude-opus-5','cases':cases,'jobs':alljobs,
        'analysis_prespecified':{
            'reference':'Fixed opposite winners from explicit statements; report all judge disagreements and missing readings.',
            'numeric':'Report both repeat vectors, query contrast size relative to repeat differences; equal products, query-ordered lexicographic, nonnegative strict feasibility only. Do not fit weights for deployment.',
            'nuisance':'Compare short and mixed context winner signs and per-facet score changes. Whole-chunk relevance can legitimately dilute; only retrieval winner preservation is hypothesized.',
            'conditions':'Current prompt versus appended user clarification; report both. No preference scores are provided to numeric readers.',
            'limits':'Four constructed subjects derived from inspected failures, not independent corpus validation; same model across tasks.'}}
    out.mkdir(parents=True,exist_ok=True)
    path=out/'manifest.json'
    if path.exists() and json.loads(path.read_text())!=manifest:
        raise ValueError('Contrast manifest changed')
    path.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    return manifest


def analyze(out,manifest):
    reads={j['id']:json.loads((out/(j['id']+'.json')).read_text()) for j in manifest['jobs']}
    for j in manifest['jobs']:
        r=reads[j['id']]
        if any(r[k+'_sha256']!=hashlib.sha256(j[k].encode()).hexdigest() for k in ('system','user')):
            raise ValueError('Response input differs')
    result={'protocol':__doc__,'preference':{},'conditions':{},
            'missing':{k:r['missing_cases'] for k,r in reads.items()},
            'cost_usd_reported':sum(r.get('cost_usd_reported',0) for r in reads.values())}
    control={}
    for j in manifest['jobs']:
        if j['role']!='preference': continue
        for cid,label in reads[j['id']]['answer'].items():
            winner=None if label=='equal' else j['orientation_not_sent'][cid][0 if label=='A' else 1]
            control.setdefault(cid,[]).append({'winner':winner,'expected':j['expected_winner_not_sent'][cid]})
    result['preference']={'readings':sum(map(len,control.values())),
        'correct':sum(r['winner']==r['expected'] for rs in control.values() for r in rs),
        'repeat_consistent_cases':sum(len(rs)==2 and rs[0]['winner']==rs[1]['winner'] for rs in control.values()),
        'cases':control}
    for condition in ('current','clarified'):
        values={}; contrasts={}; repeats={}
        for role in ('query','graph'):
            a,b=[reads[f'{condition}_{role}_{r}']['answer'] for r in (0,1)]
            if set(a)!=set(b):
                raise ValueError('Incomplete numeric contrasts; inspect retained responses')
            values[role]={k:np.array([np.mean([a[k][f],b[k][f]]) for f in FACETS]) for k in a}
            repeats[role]={k:[abs(a[k][f]-b[k][f]) for f in FACETS] for k in a}
        details=[];signed=[]
        for d in manifest['cases']['domains']:
            q0,q1=[values['query'][f"{d['id']}_{qi}"] for qi in (0,1)]
            contrasts[d['id']]={'opposite_query_absolute_difference':abs(q0-q1).tolist(),
                'query_values':[q0.tolist(),q1.tolist()]}
            for qi,q in enumerate((q0,q1)):
                for context,(a,b) in [('short',(0,1)),('mixed',(2,3))]:
                    delta=values['graph'][f"{d['id']}_{a}"]-values['graph'][f"{d['id']}_{b}"]
                    product=q*delta; target=1 if qi==0 else -1
                    signed.append(target*product)
                    details.append({'id':f"{d['id']}_{qi}_{context}",'expected_sign':target,
                        'equal_product_sign':int(np.sign(product.sum())),
                        'equal_product_gap':float(product.sum()),
                        'lex_sign':lex_direction(q,delta),'signed_products':(target*product).tolist()})
        X=np.array(signed)
        lp=linprog(np.zeros(5),A_ub=-X,b_ub=-np.ones(len(X)),bounds=(0,None),method='highs')
        if lp.status not in (0,2):raise RuntimeError(lp.message)
        block={'query_contrasts':contrasts,'repeat_absolute_differences':repeats,
            'mean_values':{role:{k:v.tolist() for k,v in vals.items()} for role,vals in values.items()},
            'comparisons':details,'common_positive_margin_nonnegative_weights_feasible':bool(lp.success),
            'equal_product_correct':sum(r['equal_product_sign']==r['expected_sign'] for r in details),
            'lex_correct':sum(r['lex_sign']==r['expected_sign'] for r in details),
            'comparisons_count':len(details)}
        block['preferred_alternative_dominated_in_product_coordinates']=[r['id'] for r in details if max(r['signed_products'])<=0]
        block['within_subject_common_coefficients_feasible']={}
        for d in manifest['cases']['domains']:
            xx=np.array([r['signed_products'] for r in details if r['id'].startswith(d['id']+'_')])
            probe=linprog(np.zeros(5),A_ub=-xx,b_ub=-np.ones(len(xx)),bounds=(0,None),method='highs')
            if probe.status not in (0,2):raise RuntimeError(probe.message)
            block['within_subject_common_coefficients_feasible'][d['id']]=bool(probe.success)
        for method in ('equal_product_sign','lex_sign'):
            byid={r['id']:r for r in details}
            block[method+'_opposite_queries_both_correct']=sum(
                all(byid[f"{d['id']}_{qi}_{context}"][method]==(1 if qi==0 else -1) for qi in (0,1))
                for d in manifest['cases']['domains'] for context in ('short','mixed'))
            block[method+'_context_sign_changes']=sum(
                byid[f"{d['id']}_{qi}_short"][method]!=byid[f"{d['id']}_{qi}_mixed"][method]
                for d in manifest['cases']['domains'] for qi in (0,1))
        result['conditions'][condition]=block
    (out/'analysis.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'preference':{k:v for k,v in result['preference'].items() if k!='cases'},
        'conditions':{c:{k:v for k,v in b.items() if k not in ('query_contrasts','repeat_absolute_differences','mean_values','comparisons')} for c,b in result['conditions'].items()},
        'cost':result['cost_usd_reported']},indent=2))


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--run',action='store_true')
    ap.add_argument('--analyze',action='store_true')
    args=ap.parse_args();manifest=prepare(args.out)
    print('Saved exact inputs for',len(manifest['jobs']),'calls',flush=True)
    if args.run:
        with ThreadPoolExecutor(max_workers=2) as pool:
            for f in as_completed([pool.submit(run,j,args.out,manifest['model']) for j in manifest['jobs']]):
                r=f.result();print(r['id'],len(r['answer']),r['missing_cases'],flush=True)
    if args.analyze:analyze(args.out,manifest)


if __name__=='__main__':main()

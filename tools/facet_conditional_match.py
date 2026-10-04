"""Exploratory pointwise query-evidence facet matching, separate from facet strength.

Classify each query/tag/passage relationship through each facet without seeing
another candidate, numerical facet values, or preference labels. Keep exact
supporting quotes. Both repeated readings are preserved; differing classifications
give a range of possible decision scores, not a statistical confidence interval.
The signed support/contradiction coding is a tested decision convention, not a
calibrated magnitude. Original corpus reuse is exploratory, not new validation.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile

import numpy as np
from threadpoolctl import threadpool_limits

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'prod'),str(ROOT/'test'),str(ROOT/'tools')]
from harness.chat import _CLAUDE_EXE
from facet_tradeoff_experiment import FACETS, lex_direction, metrics
from artefact.facet_tradeoff import crossfit_nonnegative
from facet_corpus_ordinal_analysis import reversals

CODES={'supports':1.,'conflicts':-1.,'unspecified':0.,'missing':0.}
SYSTEM="""Read each case independently. You receive a description of sought content,
a tag, and ONE candidate passage. Assess whether that passage provides what the
description calls for, concerning the tag, through each of five perspectives:
topic: subject matter; temporal: time relations or status, including completed,
pending or proposed; why: reasons, causes or purposes; activity: actions, processes
or events, including actions performed by a document and actions recorded in it;
concreteness: specific particulars versus general discussion.

This is query-to-evidence compatibility, NOT how strongly the passage carries a
facet. Both a report performing analysis and a record of sharing the report can
carry activity; the description determines which activity would be useful.

For each perspective choose exactly one status:
supports: the passage supplies content matching what the description seeks through
this perspective;
conflicts: explicit passage content is incompatible with a distinction the
description requires through this perspective;
unspecified: the description imposes no distinguishable requirement through this
perspective, so this perspective cannot favour or reject the passage;
missing: a relevant requirement is present but the passage leaves it unestablished.

Do not treat absence as contradiction. A proposal can support a request for a
proposal. A record of completed work can support a request for completed work.
Reading about a completed action does not require that the text physically enact
the action. Preserve the difference between proposing a process, operating a
process, and recording a particular execution. Ignore unrelated sections when
judging whether the relevant content is present. Do not invent facts.

Give an exact supporting quote from the passage (at most 45 words) for supports
or conflicts; use an empty quote for unspecified or missing. Return only JSON:
{"cases":{"case_id":{"topic":{"status":"supports|conflicts|unspecified|missing","quote":"..."},
"temporal":{...},"why":{...},"activity":{...},"concreteness":{...}},...}}.
Include every case and facet. No tools or extra commentary."""


def prepare(source,out,kind):
    source_body=json.loads((source/'manifest.json').read_text())
    domains=source_body['cases']['domains']; alljobs=[]
    # Two subjects per transport batch. No candidate-pair presentation; every
    # item carries its own query and one passage. Batching is not independence.
    for start in range(0,len(domains),2):
        batch=domains[start:start+2]
        for repeat in range(2):
            items=[];info={}
            for d in batch:
                for qi,description in enumerate(d['descriptions']):
                    for ti,passage in enumerate(d['texts']):
                        cid=f"{d['id']}_{qi}_{ti}"
                        info[cid]={'domain':d['id'],'qi':qi,'ti':ti,'passage':passage}
                        items.append((cid,f"Case {cid}\nSought content: {description}\nTag: {d['tag']}\nPassage:\n{passage}"))
            random.Random(92301+repeat).shuffle(items)
            alljobs.append({'id':f'match_{start}_{repeat}','system':SYSTEM,
                'user':'\n\n'.join(s for _,s in items),'info_not_sent':info,'repeat':repeat})
    manifest={'protocol':__doc__,'model':'claude-opus-5','kind':kind,
        'source_manifest_sha256':hashlib.sha256((source/'manifest.json').read_bytes()).hexdigest(),
        'jobs':alljobs,'analysis_prespecified':{
            'coding':CODES,'combination':'Mean of two readings; sum q_f*m_f without normalization; also robust lex over query-consistent facet orders.',
            'uncertainty':'Per coordinate min/max over two reads. Sum with nonnegative q. Strict nonoverlapping score intervals resolve robust order; these are observed-reading envelopes only.',
            'corpus':'Compare original 64 preference readings; all reused cases remain exploratory. Same nested subject folds for five nonnegative coefficients as previous experiments.',
            'contrast':'Use fixed expected opposites from constructed manifest; no fitted coefficients; require full pair reversals and distractor preservation.',
            'source_of_query_values':'Clarified-condition contrast query values; original direct corpus query values.',
            'limits':'One model, two repeats, selected diagnostic cases; exact quotes check provenance but not semantic validity. No deployment.'}}
    out.mkdir(parents=True,exist_ok=True);path=out/'manifest.json'
    if path.exists() and json.loads(path.read_text())!=manifest:raise ValueError('Conditional manifest changed')
    path.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    return manifest


def run(job,out,model):
    sig={k+'_sha256':hashlib.sha256(job[k].encode()).hexdigest() for k in ('system','user')}
    path=out/(job['id']+'.json');raw_path=out/(job['id']+'.raw.json')
    if path.exists():
        r=json.loads(path.read_text())
        if r['model']!=model or any(r[k]!=v for k,v in sig.items()):raise ValueError('Cached conditional response mismatch')
        return r
    if raw_path.exists():
        raw=json.loads(raw_path.read_text())
        if raw['model']!=model or any(raw[k]!=v for k,v in sig.items()):raise ValueError('Cached raw mismatch')
        envelope=raw['envelope']
    else:
        with tempfile.TemporaryDirectory(prefix='facet-conditional-') as cwd:
            r=subprocess.run([_CLAUDE_EXE,'-p','--model',model,'--effort','high',
                '--output-format','json','--tools','','--setting-sources','','--no-session-persistence',
                '--system-prompt',job['system']],input=job['user'],cwd=cwd,
                capture_output=True,text=True,encoding='utf-8',timeout=300)
        if r.returncode:raise RuntimeError(r.stderr[:400])
        envelope=json.loads(r.stdout)
        raw_path.write_text(json.dumps({'model':model,**sig,'envelope':envelope},indent=2)+'\n',encoding='utf-8')
    if envelope.get('is_error'):raise RuntimeError(str(envelope.get('result')))
    raw=envelope['result'].strip()
    if raw.startswith('```'):raw=raw.split('\n',1)[1].rsplit('```',1)[0].strip()
    answers=json.loads(raw)['cases'];checks=[]
    if set(answers)-set(job['info_not_sent']):raise ValueError('Unexpected conditional IDs')
    for cid,vs in answers.items():
        if set(vs)!=set(FACETS):raise ValueError('Missing conditional facet')
        for f,v in vs.items():
            if v['status'] not in CODES or not isinstance(v['quote'],str):raise ValueError('Bad conditional value')
            quote=v['quote'];expected_nonempty=v['status'] in ('supports','conflicts')
            checks.append({'id':cid,'facet':f,'exact':quote in job['info_not_sent'][cid]['passage'],
                'within_limit':len(quote.split())<=45,'quote_presence_correct':bool(quote)==expected_nonempty})
    result={'model':model,**sig,'id':job['id'],'answer':answers,'quote_checks':checks,
        'missing':sorted(set(job['info_not_sent'])-set(answers)),
        'usage':envelope.get('usage'),'cost_usd_reported':envelope.get('total_cost_usd'),
        'created_utc':datetime.now(timezone.utc).isoformat()}
    path.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result


def analyze(source,out,manifest):
    readings={};checks=[];cost=0;missing={}
    for j in manifest['jobs']:
        r=json.loads((out/(j['id']+'.json')).read_text())
        if any(r[k+'_sha256']!=hashlib.sha256(j[k].encode()).hexdigest() for k in ('system','user')):raise ValueError('Changed response')
        checks.extend(r['quote_checks']);cost+=r['cost_usd_reported'];missing[j['id']]=r['missing']
        for cid,vs in r['answer'].items():
            readings.setdefault(cid,[]).append([CODES[vs[f]['status']] for f in FACETS])
    domains=json.loads((source/'manifest.json').read_text())['cases']['domains']
    expected={f"{d['id']}_{qi}_{ti}" for d in domains for qi in range(len(d['descriptions'])) for ti in range(len(d['texts']))}
    if set(readings)!=expected:raise ValueError('No reading for a conditional case')
    mean={k:np.mean(v,axis=0) for k,v in readings.items()}
    lo={k:np.min(v,axis=0) for k,v in readings.items()};hi={k:np.max(v,axis=0) for k,v in readings.items()}
    analysis=json.loads((source/'analysis.json').read_text())
    if manifest['kind']=='corpus':
        qvalues=analysis['query_values'];cases=analysis['sources']['direct']['fitted_products']['predictions']
    else:
        qvalues=analysis['conditions']['clarified']['mean_values']['query'];cases=[]
        for d in domains:
            for qi in (0,1):
                for context,(a,b) in [('short',(0,1)),('mixed',(2,3))]:
                    cases.append({'id':f"{d['id']}_{qi}_{context}",'domain':d['id'],'qi':qi,'a':a,'b':b,'y':qi})
    X=[];gaps=[];lex=[];robust=[];pareto=[]
    for c in cases:
        q=np.array(qvalues[f"{c['domain']}_{c['qi']}"])
        a,b=[f"{c['domain']}_{c['qi']}_{c[side]}" for side in ('a','b')]
        delta=mean[a]-mean[b];X.append(q*delta);gaps.append(float(q@delta));lex.append(lex_direction(q,delta))
        lower=float(q@(lo[a]-hi[b]));upper=float(q@(hi[a]-lo[b]))
        robust.append(1 if lower>1e-12 else -1 if upper < -1e-12 else 0)
        lower_coordinates=q*(lo[a]-hi[b]);upper_coordinates=q*(hi[a]-lo[b])
        pareto.append(1 if (lower_coordinates>=-1e-12).all() and (lower_coordinates>1e-12).any()
            else -1 if (upper_coordinates<=1e-12).all() and (upper_coordinates < -1e-12).any() else 0)
    y=np.array([c['y'] for c in cases]);decided=y<2
    def direction(signs):
        signs=np.array(signs);ok=((signs>0)&(y==0))|((signs<0)&(y==1));resolved=decided&(signs!=0)
        return {'correct':int(ok[decided].sum()),'decisive':int(decided.sum()),'resolved':int(resolved.sum()),
            'agreement_when_resolved':float(ok[resolved].mean()) if resolved.any() else None}
    result={'protocol':__doc__,'cost_usd_reported':cost,'missing':missing,
        'quote_checks':{'fields':len(checks),'not_exact':sum(not c['exact'] for c in checks),
            'too_long':sum(not c['within_limit'] for c in checks),
            'presence_mismatch':sum(not c['quote_presence_correct'] for c in checks)},
        'repeat_same_code_fraction':float(np.mean([np.array(v[0])==v[1] for v in readings.values() if len(v)==2])),
        'reading_counts':{k:len(v) for k,v in readings.items()},'methods':{},
        'posthoc_analysis_note':'Pareto reading-envelope order was added after seeing contrast success and before corpus match results. It resolves only componentwise dominance for all observed readings; all strictly positive trade-off coefficients preserve that direction. This is not confidence or validation.',
        'predictions':[{**c,'equal_gap':gaps[i],'lex_sign':lex[i],'robust_sign':robust[i],'pareto_sign':pareto[i],'products':X[i].tolist()} for i,c in enumerate(cases)]}
    for name,signs in [('equal',np.sign(gaps)),('lex',lex),('robust_equal',robust),('pareto_observed_readings',pareto)]:
        result['methods'][name]=direction(signs)
        if manifest['kind']=='corpus':result['methods'][name].update(reversals(cases,signs))
        else:
            byid={c['id']:int(s) for c,s in zip(cases,signs)}
            result['methods'][name]['opposite_queries_both_correct']=sum(
                all(byid[f"{d['id']}_{qi}_{context}"]==(1 if qi==0 else -1) for qi in (0,1)) for d in domains for context in ('short','mixed'))
            result['methods'][name]['context_sign_changes']=sum(byid[f"{d['id']}_{qi}_short"]!=byid[f"{d['id']}_{qi}_mixed"] for d in domains for qi in (0,1))
    if manifest['kind']=='corpus':
        fitted=crossfit_nonnegative(np.array(X),y,np.array([c['domain'] for c in cases]),penalties=[.001,.01,.1,1.])
        result['methods']['fitted']={'metrics':metrics(fitted['probabilities'],y,fitted['gap'],np.ones(len(y))),
            **reversals(cases,fitted['gap']),'folds':fitted['folds']}
        for i,r in enumerate(result['predictions']):r.update({'fitted_gap':float(fitted['gap'][i]),'probabilities':fitted['probabilities'][i].tolist()})
    (out/'analysis.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('protocol','predictions','reading_counts','methods')},indent=2))
    print(json.dumps({n:{k:v for k,v in m.items() if k!='folds'} for n,m in result['methods'].items()},indent=2))


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--kind',choices=['corpus','contrast'],required=True)
    ap.add_argument('--run',action='store_true');ap.add_argument('--analyze',action='store_true')
    args=ap.parse_args();manifest=prepare(args.source,args.out,args.kind)
    print('Saved',len(manifest['jobs']),'conditional match inputs',flush=True)
    if args.run:
        with ThreadPoolExecutor(max_workers=2) as pool:
            for f in as_completed([pool.submit(run,j,args.out,manifest['model']) for j in manifest['jobs']]):
                r=f.result();print(r['id'],len(r['answer']),r['missing'],flush=True)
    if args.analyze:analyze(args.source,args.out,manifest)


if __name__=='__main__':
    with threadpool_limits(limits=1):main()

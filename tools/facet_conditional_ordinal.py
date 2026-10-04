"""Repair diagnostic: compare requested tag-related content per facet, not binary presence.

Uses inspected fresh-corpus pairs and explicit functional controls. This is not
new held-out validation. No coefficient fitting, production edits or DB writes.
All inputs are frozen before calls; case IDs are opaque and expectations hidden.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import argparse
import hashlib
import itertools
import json
import random
import subprocess
import sys
import tempfile
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'prod'),str(ROOT/'test')]
from harness.chat import _CLAUDE_EXE
from facet_tradeoff_experiment import FACETS,lex_direction
from facet_corpus_ordinal_analysis import reversals

SYSTEM="""Each case gives a description of sought content, one supplied tag, and
two candidate passages. Compare the content available concerning THIS TAG through
each facet separately. This is a query-conditioned comparison, not an overall
retrieval preference, not facet importance, and not the strength of the passage
in general. Do not use numerical scores or invent missing facts.

First establish whether the supplied tag is related to the described content and
to each passage. Faithful paraphrases and grounded references count; exact word
overlap is not required. A passage answering the description does not rescue an
unrelated supplied tag. If the tag is unrelated to the description, or unrelated
to BOTH passages, return equal for every facet with empty quotes.

Facets:
topic: what the requested tag-related content is about;
temporal: its time relations and status, such as before/after, done/pending/due;
why: its reasons, causes and purposes;
activity: what actually happens, including an activity performed by a document
(such as analysis) and an activity recorded in it (such as sharing that analysis);
concreteness: its specific particulars rather than general discussion.

For each facet identify what the description calls for through that perspective.
If it calls for no distinguishable content through that perspective, choose equal.
Otherwise compare how well the passages supply THAT content concerning the tag.
A passing mention and an explanation are not automatically equal just because
both contain something relevant. Extra words, repetition, names, headers, links,
and unrelated details confer no advantage. Actual relevant details can do so.
Preserve distinctions requested in the description, such as completed/proposed,
causes/purposes, or analyzing/sharing. Neither kind is universally preferable.
Do not favor a facet merely because the description calls it central: compare
only the content within each facet here. Any later combination is separate.

Choose A or B only for a clear advantage through that facet; equal for no clear
advantage; unknown if the comparison cannot be established. Give a brief reason
and the strongest relevant exact quote from each passage (at most 35 words each,
empty if no supporting passage exists). Quotes must be literal contiguous text.
Return only JSON, every case and every facet:
{"cases":{"case_id":{"query_link":true,"A_link":true,"B_link":true,
"facets":{"topic":{"requirement":"...","reason":"...","quote_A":"...",
"quote_B":"...","choice":"A|B|equal|unknown"},"temporal":{...},"why":{...},
"activity":{...},"concreteness":{...}}}}}. No tools or extra commentary."""

def controls():
    causes='The coolant pump stopped because grit jammed its impeller. It was installed to keep the test rig cool.'
    purposes='The coolant pump stopped. Its purpose was to keep the test rig within the sensor calibration temperature range so readings would remain comparable across runs.'
    report='The market research report compares three customer groups and analyzes their adoption barriers: cost, onboarding time, and missing integrations.'
    shared='Mira shared the market research report with the delivery team in the project chat and asked them to read it before the next meeting.'
    specs='The retry policy uses a maximum of four attempts, a 250 ms initial delay, and exponential backoff with a factor of two.'
    general='The retry policy has specific settings. The retry policy has specific settings. The retry policy has specific settings.'
    cases=[]
    def add(key,tag,description,texts,facet,winner):
        cases.append({'key':key,'tag':tag,'description':description,'texts':texts,
            'expected_not_sent':{'facet':facet,'winner':winner}})
    add('cause','coolant pump','An explanation of the causes of the coolant pump stopping.',[causes,purposes],'why',0)
    add('purpose','coolant pump','An explanation of the purposes served by the coolant pump.',[causes,purposes],'why',1)
    add('paraphrase','pump circulating cooling fluid','An explanation of the causes of the coolant pump stopping.',[causes,purposes],'why',0)
    add('irrelevant','orchard irrigation','An explanation of the causes of the coolant pump stopping.',[causes,purposes],'all',None)
    add('analysis','market research report','Analysis of customer groups and their adoption barriers in a market research report.',[report,shared],'activity',0)
    add('sharing','market research report','A record of sharing a market research report with a team.',[report,shared],'activity',1)
    add('particulars','retry policy','A specification of the actual settings of a retry policy.',[specs,general],'concreteness',0)
    add('distractor','retry policy','A specification of the actual settings of a retry policy.',[specs,general+' The unrelated building ventilation timer was changed because occupants complained about morning noise.'],'concreteness',0)
    return cases

def prepare(source,out):
    sm=json.loads((source/'manifest.json').read_text());cases=[]
    for d in sm['cases']['domains']:
        for qi,description in enumerate(d['descriptions']):
            cases.append({'key':f"{d['id']}_{qi}_0_1",'domain':d['id'],'qi':qi,
                'tag':d['tag'],'description':description,'texts':d['texts']})
    for c in cases:c['id']='c'+hashlib.sha256(('conditional-ordinal-927|'+c['key']).encode()).hexdigest()[:12]
    cc=controls()
    for c in cc:c['id']='c'+hashlib.sha256(('conditional-ordinal-927|'+c['key']).encode()).hexdigest()[:12]
    jobs=[]
    for role,items in [('corpus',cases),('control',cc)]:
        for start in range(0,len(items),8):
            for repeat in (0,1):
                info={};presented=[]
                for c in items[start:start+8]:
                    swap=int(hashlib.sha256(c['id'].encode()).hexdigest(),16)%2 ^ repeat
                    ai,bi=(1,0) if swap else (0,1)
                    info[c['id']]={**c,'orientation_not_sent':[ai,bi]}
                    presented.append(f"Case {c['id']}\nDescription: {c['description']}\nTag: {c['tag']}\nPassage A:\n{c['texts'][ai]}\nPassage B:\n{c['texts'][bi]}")
                random.Random(92630+repeat).shuffle(presented)
                jobs.append({'id':f'{role}_{start}_{repeat}','role':role,'repeat':repeat,
                    'system':SYSTEM,'user':'\n\n'.join(presented),'info_not_sent':info})
    manifest={'protocol':__doc__,'model':sm['model'],'source_manifest_sha256':hashlib.sha256((source/'manifest.json').read_bytes()).hexdigest(),
        'jobs':jobs,'analysis_prespecified':{'corpus':'Retain every previous preference reading. Use existing query relevance numbers unchanged. Compare query-ordered lexicographic order and equal query-weighted signed comparisons; no fits.',
        'robustness':'For every facet retain both orientation readings; unknown/missing/invalid quotes admit all three signs. Only resolve if all combinations and both query readings give the same nonzero lexicographic sign.',
        'controls':'Evaluate only the specified facet and winner, plus all-facet neutrality for the unrelated tag. No model-visible expectations or category names in IDs.',
        'limits':'Same model, already inspected corpus, query-conditioned pairwise measurements. Not stored graph strengths, cardinal utilities, or a validated full ranking. Controls sharing content may influence each other within a batch.'}}
    out.mkdir(parents=True,exist_ok=True);p=out/'manifest.json'
    if p.exists() and json.loads(p.read_text())!=manifest:raise ValueError('Changed manifest')
    p.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8');return manifest

def run(job,out,model):
    sig={k+'_sha256':hashlib.sha256(job[k].encode()).hexdigest() for k in ('system','user')}
    p=out/(job['id']+'.json');rawp=out/(job['id']+'.raw.json')
    if p.exists():
        r=json.loads(p.read_text())
        if r['model']!=model or any(r[k]!=v for k,v in sig.items()):raise ValueError('Changed saved reading')
        return r
    if rawp.exists():
        raw=json.loads(rawp.read_text())
        if raw['model']!=model or any(raw[k]!=v for k,v in sig.items()):raise ValueError('Changed raw reading')
        env=raw['envelope']
    else:
        with tempfile.TemporaryDirectory(prefix='facet-ordinal-match-') as cwd:
            proc=subprocess.run([_CLAUDE_EXE,'-p','--model',model,'--effort','high','--output-format','json',
                '--tools','','--setting-sources','','--no-session-persistence','--system-prompt',job['system']],
                input=job['user'],cwd=cwd,capture_output=True,text=True,encoding='utf-8',timeout=300)
        transport=out/(job['id']+'.transport.json')
        transport.write_text(json.dumps({'model':model,**sig,'returncode':proc.returncode,
            'stdout':proc.stdout,'stderr':proc.stderr,'created_utc':datetime.now(timezone.utc).isoformat()},indent=2)+'\n',encoding='utf-8')
        if proc.returncode:raise RuntimeError(f'CLI exit {proc.returncode}; full transport saved in {transport.name}')
        env=json.loads(proc.stdout)
        rawp.write_text(json.dumps({'model':model,**sig,'envelope':env},indent=2)+'\n',encoding='utf-8')
    if env.get('is_error'):raise RuntimeError(str(env.get('result')))
    body=env['result'].strip()
    if body.startswith('```'):body=body.split('\n',1)[1].rsplit('```',1)[0].strip()
    answer=json.loads(body)['cases'];checks=[]
    if set(answer)-set(job['info_not_sent']):raise ValueError('Unexpected case')
    for cid,r in answer.items():
        if any(type(r[k]) is not bool for k in ('query_link','A_link','B_link')) or set(r['facets'])!=set(FACETS):raise ValueError('Invalid schema')
        c=job['info_not_sent'][cid]
        for f,v in r['facets'].items():
            if v['choice'] not in ('A','B','equal','unknown'):raise ValueError('Invalid choice')
            for side,ti in zip(('A','B'),c['orientation_not_sent']):
                quote=v['quote_'+side]
                checks.append({'id':cid,'facet':f,'side':side,'valid':isinstance(quote,str) and quote in c['texts'][ti] and len(quote.split())<=35})
    r={'id':job['id'],'model':model,**sig,'answer':answer,'quote_checks':checks,
        'missing':sorted(set(job['info_not_sent'])-set(answer)),'cost_usd_reported':env.get('total_cost_usd'),
        'usage':env.get('usage'),'created_utc':datetime.now(timezone.utc).isoformat()}
    p.write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8');return r

def analyze(source,out,m):
    reads={};observed={};ranges={};missing={};checks=[];control=[];cost=0
    for j in m['jobs']:
        path=out/(j['id']+'.json')
        r=json.loads(path.read_text()) if path.exists() else {
            'answer':{},'missing':sorted(j['info_not_sent']),'quote_checks':[],'cost_usd_reported':0}
        missing[j['id']]=r['missing'];cost+=r['cost_usd_reported'];checks+=r['quote_checks']
        invalid={(c['id'],c['facet']) for c in r['quote_checks'] if not c['valid']}
        for cid,c in j['info_not_sent'].items():
            vals=r['answer'].get(cid,{}).get('facets',{});sign=[];possible=[]
            for f in FACETS:
                choice=vals.get(f,{}).get('choice','unknown')
                win=None if choice in ('unknown','equal') else c['orientation_not_sent'][0 if choice=='A' else 1]
                s=0 if win is None else 1 if win==0 else -1
                sign.append(s);possible.append([-1,0,1] if choice=='unknown' or (cid,f) in invalid else [s])
            if j['role']=='corpus':
                reads.setdefault(c['key'],[]).append(sign);ranges.setdefault(c['key'],[]).append(possible)
                if cid in r['answer']:
                    observed.setdefault(c['key'],[]).append([None if vals[f]['choice']=='unknown' else sign[i] for i,f in enumerate(FACETS)])
            else:
                expected=c['expected_not_sent'];fi=FACETS.index(expected['facet']) if expected['facet']!='all' else None
                ok=all(s==0 for s in sign) if fi is None else sign[fi]==(1 if expected['winner']==0 else -1)
                control.append({'case':c['key'],'repeat':j['repeat'],'signs':sign,'matches_expectation':ok,
                    'available':cid in r['answer'],'quote_valid':not any((cid,f) in invalid for f in FACETS)})
    v=json.loads((source/'validation.json').read_text());qreads=[json.loads((source/f'query_{i}.json').read_text())['answer'] for i in (0,1)]
    pred=[]
    for c in v['predictions']:
        cid=c['id'];qid=f"{c['domain']}_{c['qi']}";q=np.array(v['query_values'][qid]);delta=np.mean(reads[cid],axis=0)
        possibilities=[sorted({s for r in ranges[cid] for s in r[i]}) for i in range(5)]
        possible_orders={lex_direction(np.array([qr[qid][f] for f in FACETS]),np.array(ss)) for qr in qreads for ss in itertools.product(*possibilities)}
        robust=int(next(iter(possible_orders))) if len(possible_orders)==1 and 0 not in possible_orders else 0
        pred.append({**{k:c[k] for k in ('id','domain','qi','repeat','y')},'facet_signs':delta.tolist(),
            'weighted_gap':float(q@delta),'lex_sign':lex_direction(q,delta),'robust_sign':robust})
    def metric(field):
        y=np.array([c['y'] for c in pred]);g=np.array([c[field] for c in pred]);dec=y<2;res=dec&(abs(g)>1e-12)
        ok=((g>1e-12)&(y==0))|((g < -1e-12)&(y==1))
        return {'correct':int(ok[dec].sum()),'decisive':int(dec.sum()),'resolved':int(res.sum()),**reversals(pred,g)}
    a={'protocol':__doc__,'cost_usd_reported':cost,
        'jobs_without_parsed_results':[j['id'] for j in m['jobs'] if not (out/(j['id']+'.json')).exists()],
        'missing_cost_note':'Costs of calls without parsed responses are unavailable, not known to be zero.',
        'missing':missing,'quote_fields':len(checks),
        'invalid_quote_fields':sum(not c['valid'] for c in checks),
        'observed_corpus_readings':sum(len(r) for r in observed.values()),
        'corpus_pairs_with_both_orientations':sum(len(r)==2 for r in observed.values()),
        'facet_orientation_agreement':{f:float(np.mean(pairs)) if (pairs:=[r[0][i]==r[1][i] for r in observed.values()
            if len(r)==2 and r[0][i] is not None and r[1][i] is not None]) else None for i,f in enumerate(FACETS)},
        'methods':{f:metric(f) for f in ('weighted_gap','lex_sign','robust_sign')},'controls':control,'predictions':pred}
    (out/'analysis.json').write_text(json.dumps(a,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in a.items() if k not in ('predictions','controls')},indent=2))
    print('Controls',sum(c['matches_expectation'] and c['available'] for c in control),'/',len(control))

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--source',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--run',action='store_true');ap.add_argument('--analyze',action='store_true')
    args=ap.parse_args();m=prepare(args.source,args.out);print('Saved',len(m['jobs']),'ordinal comparison jobs',flush=True)
    if args.run:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures={pool.submit(run,j,args.out,m['model']):j for j in m['jobs']}
            for future in as_completed(futures):
                j=futures[future]
                try:
                    r=future.result();print(r['id'],len(r['answer']),r['missing'],flush=True)
                except Exception as exc:
                    failure={'job':j['id'],'type':type(exc).__name__,
                        'message':'Collector timeout' if isinstance(exc,subprocess.TimeoutExpired) else str(exc)[:1000],
                        'created_utc':datetime.now(timezone.utc).isoformat()}
                    (args.out/(j['id']+'.failed.json')).write_text(json.dumps(failure,indent=2)+'\n',encoding='utf-8')
                    print(j['id'],failure['type'],flush=True)
        analyze(args.source,args.out,m)
    elif args.analyze:
        analyze(args.source,args.out,m)

if __name__=='__main__':main()

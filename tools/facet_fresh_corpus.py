"""Freeze and collect a fresh cross-record-kind corpus validation.

Eight unseen tags, two unused held-out source chunks each, same product but
different record-kind families. Fixed hash selection, no score/label selection.
Four descriptions per subject request two facets and reverse their prominence.
All passages are verbatim export text and attached relationships are checked in
live Volmax before collection. No benchmark questions, gold, DB writes or refits.
"""
from pathlib import Path
import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
import hashlib
import itertools
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'prod'),str(ROOT/'test'),str(ROOT/'tools')]
from graph.facet_pairs import data as D
from graph.db import _driver
from facet_tradeoff_readings import jobs,run
from facet_contrast_diagnosis import CLARIFICATION

BASE=ROOT/'output/research/2026-09-21-facet-validity'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def order(salt,s):return hashlib.sha256((salt+s).encode()).hexdigest()
def family(c):return 'document' if c['kind'].startswith('document') else c['kind']


def prepare(out):
    if (out/'manifest.json').exists():return json.loads((out/'manifest.json').read_text())
    rows_path=ROOT/'output/facet_neural/rows_export.jsonl'
    scores_path=ROOT/'output/facet_pairs/rounds/round1/scores.jsonl'
    old=json.loads((BASE/'corpus_tradeoff/manifest.json').read_text())['cases']['domains']
    used={cid for d in old for cid in d['source_chunks']};oldtags={d['tag'] for d in old}
    scored={json.loads(line)['edge_id'] for line in scores_path.open(encoding='utf-8')}
    by=defaultdict(list)
    for c in D.load_chunks(str(rows_path)):
        if not D.is_heldout(c['chunk_id']) or c['chunk_id'] in used or not 500<=len(c['text'])<=5000:continue
        for t in set(c['tags']):
            if t not in oldtags and t==t.lower() and 2<=len(t.split())<=8 and len(t)<80 and D.edge_id(c['chunk_id'],t) in scored:
                by[t].append(c)
    domains=[]
    for tag in sorted(by,key=lambda t:order('fresh_facet_validation_20260922:',t)):
        pairs=[(a,b) for a,b in itertools.combinations(by[tag],2)
            if a['chunk_id'] not in used and b['chunk_id'] not in used
            and a.get('product') and a['product']==b.get('product') and family(a)!=family(b)]
        if not pairs:continue
        a,b=min(pairs,key=lambda ab:order('fresh_facet_pair_20260922:', '|'.join(sorted([c['chunk_id'] for c in ab]))))
        chosen=sorted([a,b],key=lambda c:order('fresh_facet_side_20260922:',c['chunk_id']))
        used.update(c['chunk_id'] for c in chosen)
        domains.append({'id':f'v{len(domains)}','tag':tag,'product_not_sent':a['product'],
            'descriptions':[
                f"An account of {tag} centred on its sequence, dependencies and current status, with the reasons and intended benefits as background context.",
                f"An account of {tag} centred on the reasons and intended benefits, with its sequence, dependencies and current status as background context.",
                f"An account of {tag} centred on actions actually performed, with specific quantities, identifiers or settings as supporting detail.",
                f"An account of {tag} centred on specific quantities, identifiers or settings, with actions actually performed as supporting context."],
            'texts':[c['text'] for c in chosen],'source_chunks':[c['chunk_id'] for c in chosen],
            'source_edges':[D.edge_id(c['chunk_id'],tag) for c in chosen],
            'source_kinds':[c['kind'] for c in chosen]})
        if len(domains)==8:break
    if len(domains)!=8:raise RuntimeError('Not enough disjoint fresh same-product cross-kind groups')
    requests=[{'chunk':c,'tag':d['tag']} for d in domains for c in d['source_chunks']]
    with _driver() as driver:
        with driver.session(database='herb-eval-volmax',default_access_mode='READ') as session:
            live=[dict(r) for r in session.run('UNWIND $pairs AS p MATCH (c:Chunk {chunk_id:p.chunk})-[:HAS_TAG]->(t:Tag {name:p.tag}) RETURN c.chunk_id AS chunk,t.name AS tag,size(c.desc_emb) AS chunk_dim,size(t.emb) AS tag_dim',pairs=requests)]
    if len(live)!=16 or {(r['chunk'],r['tag']) for r in live}!={(p['chunk'],p['tag']) for p in requests}:raise RuntimeError('Fresh relationship mismatch with live Volmax')
    cases={'purpose':__doc__,'domains':domains}
    jj=jobs(cases)
    for j in jj:
        if j['role']!='preference':j['system']+=CLARIFICATION
    # Repackage preferences for two subjects per transport batch; no prompt or
    # per-case comparison changes. Both presentation orientations are retained.
    batched=[j for j in jj if j['role']!='preference']
    for start in range(0,8,2):
        selected={d['id'] for d in domains[start:start+2]}
        for repeat in (0,1):
            group=[j for j in jj if j['role']=='preference' and j['repeat']==repeat and j['id'].split('_')[1] in selected]
            batched.append({'id':f'preference_batch{start}_{repeat}','role':'preference','repeat':repeat,
                'system':group[0]['system'],'user':'\n\n'.join(j['user'] for j in group),
                'case_ids':[cid for j in group for cid in j['case_ids']],
                'orientation_not_sent':{cid:v for j in group for cid,v in j['orientation_not_sent'].items()}})
    prior=json.loads((BASE/'opposing/analysis.json').read_text())
    conditional=json.loads((BASE/'opposing_conditional/analysis.json').read_text())
    models={source:[f['model'] for f in prior['sources'][source]['fitted_products']['folds']] for source in ('direct','frozen_reference')}
    models['conditional']=[f['model'] for f in conditional['methods']['fitted']['folds']]
    manifest={'protocol':__doc__,'created_utc':datetime.now(timezone.utc).isoformat(),
        'model':'claude-opus-5','cases':cases,'jobs':batched,'live_relationship_check':live,
        'source_sha256':{str(p):digest(p) for p in (rows_path,scores_path,BASE/'opposing/analysis.json',BASE/'opposing_conditional/analysis.json')},
        'frozen_models':models,
        'collection_deviations':'None planned. Retain missing and invalid readings; no content-selected retries.',
        'analysis_prespecified':{
            'primary':'Unchanged conditional matcher; equal sum of query relevance times mean match code. Also strict evidence-quality/repeat envelope. Missing evidence is not contradiction.',
            'frozen_transfer':'Equal probability ensemble of the six already saved opposing-subject fold models. No fit, penalty choice, calibration or model selection on fresh corpus preferences.',
            'comparators':'Direct query-times-strength with prior direct coefficients; frozen-reference query-times-strength with prior frozen coefficients. Raw equal sums and query-ordered lex as diagnostics.',
            'identifiability':'Count actual opposing-sign feature differences. Do not infer relative weights from only one-coordinate differences or ties.',
            'reference':'Two A/B orientations of usefulness judgement, blind to facets and scores. Report all readings, repeat disagreement and ties; count groups, not repeats, as sampling units.',
            'negative_controls':'Unrelated-tag pointwise controls on the same passages, with orchard irrigation or museum ticket refunds replacing the tag while description/text stay fixed. These counterfactual relationships are not claimed DB edges.',
            'scope':'Fresh corpus screen with the same model across reading tasks and repeated query templates; not whole-retrieval or set-selection validation. Same-product pairing controls one scope difference.',
            'frozen_artifact_hashes':{str(p):digest(p) for p in (ROOT/'tools/facet_conditional_match.py',ROOT/'tools/facet_tradeoff_readings.py')}}}
    out.mkdir(parents=True,exist_ok=True)
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    return manifest


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,required=True);ap.add_argument('--run',action='store_true')
    args=ap.parse_args();manifest=prepare(args.out)
    print(json.dumps([{'tag':d['tag'],'product':d['product_not_sent'],'kinds':d['source_kinds']} for d in manifest['cases']['domains']],indent=2),flush=True)
    print('Frozen inputs and prior models; calls:',len(manifest['jobs']),flush=True)
    if args.run:
        with ThreadPoolExecutor(max_workers=2) as pool:
            for f in as_completed([pool.submit(run,j,args.out,manifest['model']) for j in manifest['jobs']]):
                r=f.result();print(r['id'],len(r['answer']),r['missing_cases'],flush=True)

if __name__=='__main__':main()

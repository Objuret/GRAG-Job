"""Diagnose ignored tag input with exact, paraphrased and unrelated tags.

Three selected fresh-corpus subjects, two untouched passages each. Keep description
and passage fixed while changing only the supplied tag. Compare the current
conditional prompt with an appended explicit binding requirement. Both shuffled
readings are retained. This is a repair diagnostic on inspected failures, not
independent validation and not a change to production or frozen primary results.
"""
from pathlib import Path
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
import hashlib
import json
import random
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'prod'),str(ROOT/'test')]
from facet_conditional_match import SYSTEM,run,FACETS

BINDING="""
MANDATORY TAG BINDING: This is a judgement about the SUPPLIED TAG, not about the
passage or the description in general. First establish that the tag is relevant
to BOTH the described content and the actual passage. If either link is absent,
return missing with an empty quote for every facet. A passage answering the
description does not make an unrelated supplied tag relevant. Evidence about
other subjects must never count as support for the supplied tag.
Exact word overlap is not required: a faithful paraphrase or a clearly grounded
reference can establish the same concept. Do not reject a valid paraphrase merely
because its words differ. Do not invent a relation to rescue an unrelated tag.
Only after establishing both links assess query-to-evidence compatibility through
each facet. Every nonempty evidence quote must concern this tag's supported concept.
"""

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--run',action='store_true')
    ap.add_argument('--blind',action='store_true',help='Opaque IDs; separate variants so repeated passages do not expose the manipulation')
    args=ap.parse_args()
    source=json.loads((args.source/'manifest.json').read_text())
    paraphrases={'v1':'rules for encrypting data','v4':'efficient operation of the system','v6':'testing individual software components'}
    cases=[]
    for d in source['cases']['domains']:
        if d['id'] not in paraphrases:continue
        for ti,passage in enumerate(d['texts']):
            for label,tag in [('exact',d['tag']),('paraphrase',paraphrases[d['id']]),('unrelated','orchard irrigation')]:
                source_id=f"{d['id']}_{ti}_{label}"
                cid='c'+hashlib.sha256(('binding-blind-926|'+source_id).encode()).hexdigest()[:12] if args.blind else source_id
                cases.append({'id':cid,'tag_variant':label,'tag':tag,'passage':passage,'description':d['descriptions'][0]})
    jobs=[]
    for version in ('current','binding'):
        for repeat in (0,1):
            for variant in (('exact','paraphrase','unrelated') if args.blind else (None,)):
                items=[c for c in cases if variant is None or c['tag_variant']==variant]
                random.Random(92520+repeat).shuffle(items)
                jobs.append({'id':f'{version}_{repeat}'+('_'+variant if variant else ''),'version':version,'repeat':repeat,'system':SYSTEM+(BINDING if version=='binding' else ''),
                    'user':'\n\n'.join(f"Case {c['id']}\nSought content: {c['description']}\nTag: {c['tag']}\nPassage:\n{c['passage']}" for c in items),
                    'info_not_sent':{c['id']:c for c in items}})
    manifest={'protocol':__doc__,'model':source['model'],'source_manifest_sha256':hashlib.sha256((args.source/'manifest.json').read_bytes()).hexdigest(),
        'blind_protocol':args.blind,'jobs':jobs,'expectations_not_sent':{'unrelated':'No supports on any facet; absent tag relation is missing, not evidence of a conflict.',
            'exact_and_paraphrase':'Topic should remain supported when the supplied tag faithfully denotes the relevant concept; inspect deviations and quote validity. Do not require other facets when evidence is absent.'}}
    args.out.mkdir(parents=True,exist_ok=True);path=args.out/'manifest.json'
    if path.exists() and json.loads(path.read_text())!=manifest:raise ValueError('Tag binding inputs changed')
    path.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8');print(f'Saved {len(jobs)} binding probe inputs',flush=True)
    if args.run:
        with ThreadPoolExecutor(max_workers=2) as pool:
            for f in as_completed([pool.submit(run,j,args.out,manifest['model']) for j in jobs]):
                r=f.result();print(r['id'],len(r['answer']),r['missing'],flush=True)
        result={'protocol':__doc__,'versions':{}}
        for version in ('current','binding'):
            readings=[];checks=[];missing={};cost=0
            for j in jobs:
                if j['version']!=version:continue
                r=json.loads((args.out/(j['id']+'.json')).read_text());checks.extend(r['quote_checks']);missing[j['id']]=r['missing'];cost+=r['cost_usd_reported']
                for cid,vs in r['answer'].items():readings.append({'id':cid,'variant':j['info_not_sent'][cid]['tag_variant'],'values':vs})
            result['versions'][version]={'cost_usd_reported':cost,'missing':missing,'quote_failures':sum(not all(c[k] for k in ('exact','within_limit','quote_presence_correct')) for c in checks),
                'variants':{v:{'readings':sum(r['variant']==v for r in readings),
                    'topic_supports':sum(r['variant']==v and r['values']['topic']['status']=='supports' for r in readings),
                    'supports_by_facet':{f:sum(r['variant']==v and r['values'][f]['status']=='supports' for r in readings) for f in FACETS}} for v in ('exact','paraphrase','unrelated')}}
        (args.out/'analysis.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,indent=2))

if __name__=='__main__':main()

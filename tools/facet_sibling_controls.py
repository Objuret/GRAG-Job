"""Tag selectivity with two legitimate tags in the same description and passages.

Both candidates address both tags. Their advantages exchange between tags, so a
generic description-to-passage comparison cannot pass by ignoring the tag input.
The cases are constructed behavioral tests, not corpus preference labels.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import argparse
import hashlib
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from facet_conditional_ordinal import SYSTEM,run,FACETS

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--run',action='store_true')
    args=ap.parse_args()
    examples=[
        ('activity',('credential rotation','audit logging'),
         'A record of completed changes involving credential rotation and audit logging.',
         ['Credential rotation was completed: the operators replaced every exposed access key. Audit logging was proposed for the next maintenance window; no work on it has begun.',
          'Credential rotation was proposed for the next maintenance window; no work on it has begun. Audit logging was completed: the operators enabled the event collector and verified its records.']),
        ('concreteness',('compression policy','retry policy'),
         'A specification of the actual settings of the compression policy and the retry policy.',
         ['The compression policy uses 4 MiB blocks and compression level 3. The retry policy has settings, which are not specified in this note.',
          'The compression policy has settings, which are not specified in this note. The retry policy permits four attempts, starting with a 250 ms delay and doubling the delay after each failure.']),
        ('why',('response caching','payload compression'),
         'An explanation of the reasons for adopting response caching and payload compression.',
         ['Response caching was adopted because repeated reads overloaded the source service; reusing results reduces those reads. Payload compression was adopted, but this note does not give its reason.',
          'Response caching was adopted, but this note does not give its reason. Payload compression was adopted because large messages exhausted link capacity; smaller payloads reduce transfer time.'])]
    jobs=[]
    for variant in (0,1):
        for repeat in (0,1):
            info={};items=[]
            for facet,tags,description,texts in examples:
                key=f'{facet}:{variant}';cid='c'+hashlib.sha256(('sibling-928|'+key).encode()).hexdigest()[:12]
                swap=int(hashlib.sha256(cid.encode()).hexdigest(),16)%2 ^ repeat
                ai,bi=(1,0) if swap else (0,1)
                info[cid]={'tag':tags[variant],'description':description,'texts':texts,
                    'orientation_not_sent':[ai,bi],'target_facet':facet,'expected_winner':variant}
                items.append(f"Case {cid}\nDescription: {description}\nTag: {tags[variant]}\nPassage A:\n{texts[ai]}\nPassage B:\n{texts[bi]}")
            if repeat:items.reverse()
            jobs.append({'id':f'sibling_{variant}_{repeat}','repeat':repeat,'system':SYSTEM,
                'user':'\n\n'.join(items),'info_not_sent':info})
    m={'protocol':__doc__,'model':'claude-opus-5','jobs':jobs,
        'analysis_prespecified':'All three links should be true. Target facet should choose the passage that supplies the requested content for the given tag. Require both orientations and the tag-dependent reversal. Other facets are descriptive diagnostics. Invalid quotations and missing calls are retained, not retried selectively. Variants are in separate calls, with opaque case IDs.'}
    args.out.mkdir(parents=True,exist_ok=True);p=args.out/'manifest.json'
    if p.exists() and json.loads(p.read_text())!=m:raise ValueError('Changed sibling control inputs')
    p.write_text(json.dumps(m,indent=2)+'\n',encoding='utf-8');print('Saved four tag-selectivity jobs',flush=True)
    if not args.run:return
    with ThreadPoolExecutor(max_workers=2) as pool:
        for future in as_completed([pool.submit(run,j,args.out,m['model']) for j in jobs]):
            r=future.result();print(r['id'],len(r['answer']),r['missing'],flush=True)
    rows=[];cost=0;checks=[]
    for j in jobs:
        r=json.loads((args.out/(j['id']+'.json')).read_text());cost+=r['cost_usd_reported'];checks+=r['quote_checks']
        for cid,c in j['info_not_sent'].items():
            a=r['answer'].get(cid);choice=a['facets'][c['target_facet']]['choice'] if a else 'unknown'
            win=None if choice in ('equal','unknown') else c['orientation_not_sent'][0 if choice=='A' else 1]
            rows.append({'facet':c['target_facet'],'tag':c['tag'],'repeat':j['repeat'],
                'expected_winner':c['expected_winner'],'actual_winner':win,'correct':win==c['expected_winner'],
                'all_links_true':all(a.get(k) for k in ('query_link','A_link','B_link')) if a else False})
    a={'protocol':__doc__,'cost_usd_reported':cost,'correct':sum(r['correct'] for r in rows),
        'readings':len(rows),'all_links_true':sum(r['all_links_true'] for r in rows),
        'quote_fields':len(checks),'invalid_quote_fields':sum(not c['valid'] for c in checks),
        'tag_reversals_both_orientations':sum(all(r['correct'] for r in rows if r['facet']==f) for f in ('activity','concreteness','why')),
        'possible_tag_reversals':3,'results':rows}
    (args.out/'analysis.json').write_text(json.dumps(a,indent=2)+'\n',encoding='utf-8');print(json.dumps(a,indent=2))

if __name__=='__main__':main()

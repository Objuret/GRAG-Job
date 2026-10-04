"""Run preregistered unrelated-tag controls using the unchanged conditional reader."""
from pathlib import Path
import argparse
import hashlib
import json
import random
import sys
from concurrent.futures import ThreadPoolExecutor,as_completed
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'prod'),str(ROOT/'test')]
from facet_conditional_match import SYSTEM,run,FACETS

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--run',action='store_true')
    args=ap.parse_args();source=json.loads((args.source/'manifest.json').read_text());jobs=[]
    for repeat in (0,1):
        items=[];info={}
        for di,d in enumerate(source['cases']['domains']):
            tag=('orchard irrigation','museum ticket refunds')[di%2]
            for ti,text in enumerate(d['texts']):
                if tag in text.lower() or tag in d['descriptions'][0].lower():raise ValueError('Negative tag occurs in control source')
                cid=f"{d['id']}_0_{ti}"
                info[cid]={'domain':d['id'],'qi':0,'ti':ti,'passage':text,'counterfactual_tag':tag}
                items.append((cid,f"Case {cid}\nSought content: {d['descriptions'][0]}\nTag: {tag}\nPassage:\n{text}"))
        random.Random(92400+repeat).shuffle(items)
        jobs.append({'id':f'negative_{repeat}','repeat':repeat,'system':SYSTEM,
            'user':'\n\n'.join(s for _,s in items),'info_not_sent':info})
    manifest={'protocol':__doc__,'model':source['model'],'source_sha256':hashlib.sha256((args.source/'manifest.json').read_bytes()).hexdigest(),
        'jobs':jobs,'hypothesis':'The unrelated tag has no relevant evidence here. Count any supports classification, by facet and repeat; do not interpret missing as contradiction. These are counterfactual input controls, not stored DB edges.'}
    args.out.mkdir(parents=True,exist_ok=True);p=args.out/'manifest.json'
    if p.exists() and json.loads(p.read_text())!=manifest:raise ValueError('Negative control inputs changed')
    p.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print('Saved two exact negative-control inputs',flush=True)
    if args.run:
        with ThreadPoolExecutor(max_workers=2) as pool:
            for f in as_completed([pool.submit(run,j,args.out,manifest['model']) for j in jobs]):
                r=f.result();print(r['id'],len(r['answer']),r['missing'],flush=True)
        rows=[json.loads((args.out/(j['id']+'.json')).read_text()) for j in jobs]
        counts={f:sum(v[f]['status']=='supports' for r in rows for v in r['answer'].values()) for f in FACETS}
        result={'hypothesis':manifest['hypothesis'],'readings':sum(len(r['answer']) for r in rows),
            'supports_by_facet':counts,'missing':{r['id']:r['missing'] for r in rows},
            'cost_usd_reported':sum(r['cost_usd_reported'] for r in rows),
            'false_supports':[{'job':r['id'],'case':cid,'facet':f,**v[f]} for r in rows for cid,v in r['answer'].items() for f in FACETS if v[f]['status']=='supports']}
        (args.out/'analysis.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(result,indent=2))

if __name__=='__main__':main()

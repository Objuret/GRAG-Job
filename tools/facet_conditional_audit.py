"""Post-hoc evidence-validity and identifiability audit; no new reader calls.

Retain original results. For a conservative additional check, a missing repeat or
an invalid quote opens that coordinate to the full [-1,1] code range. This range
is an engineering decision envelope, not a statistical confidence interval.
Also check whether the available comparisons contain genuine cross-facet tradeoffs.
"""
from pathlib import Path
import argparse
import json
import sys
from collections import Counter
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'test'),str(ROOT/'prod')]
from facet_conditional_match import CODES,FACETS

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--corpus',type=Path,required=True);ap.add_argument('--conditional',type=Path,required=True)
    args=ap.parse_args();p=args.conditional
    manifest=json.loads((p/'manifest.json').read_text());states={};counts=Counter();bad=[]
    for j in manifest['jobs']:
        r=json.loads((p/(j['id']+'.json')).read_text())
        for cid in j['info_not_sent']:
            v=[]
            for f in FACETS:
                if cid not in r['answer']:
                    v.append((-1.,1.));continue
                a=r['answer'][cid][f];counts[f+'/'+a['status']]+=1
                quote=a['quote'];text=j['info_not_sent'][cid]['passage'];code=CODES[a['status']]
                valid=quote in text and len(quote.split())<=45 and bool(quote)==(a['status'] in ('supports','conflicts'))
                if not valid:
                    bad.append({'case':cid,'facet':f,'job':j['id'],
                        'exact':quote in text,'matches_after_whitespace_normalization':' '.join(quote.split()) in ' '.join(text.split()),'quote':quote})
                v.append((code,code) if valid else (-1.,1.))
            states.setdefault(cid,[]).append(v)
    lo={k:np.min(np.array(v)[:,:,0],axis=0) for k,v in states.items()}
    hi={k:np.max(np.array(v)[:,:,1],axis=0) for k,v in states.items()}
    original=json.loads((args.corpus/'analysis.json').read_text())
    result=json.loads((p/'analysis.json').read_text());rows=[]
    for c in result['predictions']:
        q=np.array(original['query_values'][f"{c['domain']}_{c['qi']}"])
        a,b=[f"{c['domain']}_{c['qi']}_{c[side]}" for side in ('a','b')]
        lower=float(q@(lo[a]-hi[b]));upper=float(q@(hi[a]-lo[b]))
        sign=1 if lower>1e-12 else -1 if upper < -1e-12 else 0
        products=np.array(c['products'])
        rows.append({**c,'strict_lower':lower,'strict_upper':upper,'strict_sign':sign,
            'nonzero_product_coordinates':int((abs(products)>1e-12).sum()),
            'contains_cross_facet_tradeoff':bool((products>1e-12).any() and (products < -1e-12).any())})
    distinct={r['id']:r for r in rows};decided=[r for r in rows if r['y']<2];resolved=[r for r in decided if r['strict_sign']]
    out={'protocol':__doc__,'category_counts':dict(counts),'quote_failures':bad,
        'strict_quality_envelope':{'resolved_decisive_readings':len(resolved),'decisive_readings':len(decided),
            'correct':sum((r['strict_sign']>0)==(r['y']==0) for r in resolved)},
        'distinct_comparisons':len(distinct),
        'distinct_comparisons_with_cross_facet_tradeoffs':sum(r['contains_cross_facet_tradeoff'] for r in distinct.values()),
        'distinct_nonzero_coordinate_histogram':dict(Counter(r['nonzero_product_coordinates'] for r in distinct.values())),
        'conclusion':'If no comparison trades off opposite-signed coordinates, this screen cannot identify relative positive facet weights from directional preferences. It can test matching, abstention and confidence calibration separately.',
        'predictions':rows}
    (p/'quality_audit.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in out.items() if k not in ('protocol','quote_failures','category_counts','predictions')},indent=2))

if __name__=='__main__':main()

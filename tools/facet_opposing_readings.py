"""Prospective opposing-facet screen; fictional passages, no benchmark material.

Both facets are requested and their prominence is reversed without changing the
candidate passages. A balanced third description is retained without prescribing
a preference. This tests whether query relevance and graph strengths can express
tradeoffs. It does not redefine relevance values as requested facet importance.
"""
from pathlib import Path
import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor,as_completed
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'test'),str(ROOT/'prod')]
from facet_tradeoff_readings import jobs,run
from facet_contrast_diagnosis import CLARIFICATION

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,required=True);ap.add_argument('--run',action='store_true')
    args=ap.parse_args();cases=json.loads((ROOT/'tools/facet_opposing_cases.json').read_text())
    base=jobs(cases);numeric=[{**j,'system':j['system']+CLARIFICATION} for j in base if j['role']!='preference']
    combined=[]
    for start in (0,3):
        selected={d['id'] for d in cases['domains'][start:start+3]}
        for repeat in (0,1):
            jj=[j for j in base if j['role']=='preference' and j['repeat']==repeat and j['id'].split('_')[1] in selected]
            combined.append({'id':f'preference_batch{start}_{repeat}','role':'preference','repeat':repeat,
                'system':jj[0]['system'],'user':'\n\n'.join(j['user'] for j in jj),
                'case_ids':[cid for j in jj for cid in j['case_ids']],
                'orientation_not_sent':{cid:v for j in jj for cid,v in j['orientation_not_sent'].items()}})
    manifest={'protocol':__doc__,'model':'claude-opus-5','cases':cases,'jobs':numeric+combined,
        'analysis_prespecified':{
            'reference':'Both A/B orientations, keep ties and disagreement; no expected winners sent. Inspect whether preference follows the changed central content.',
            'methods':'Original equal query-products, query-ordered lexicographic, nested nonnegative coefficients excluding each whole subject; original frozen reference and direct graph readings. Retain all methods.',
            'conditional_followup':'Pointwise conditional match with unchanged prompt, collected independently. Check whether actual feature differences contain opposing signs before interpreting fitted weights.',
            'penalty_grid':[.001,.01,.1,1],
            'feasibility':'Common nonnegative product coefficients satisfying all consistently decisive preferences; distinguish representation infeasibility from estimation failure.',
            'set_selection_limit':'Preferences are order-of-reading diagnostics, not proof that the other complementary passage should be excluded from retrieval.',
            'limits':'Six constructed subjects, two facet-pair structures, one model; no population or serving claim. A pass would require new corpus tests.'}}
    args.out.mkdir(parents=True,exist_ok=True);p=args.out/'manifest.json'
    if p.exists() and json.loads(p.read_text())!=manifest:raise ValueError('Opposing manifest changed')
    p.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print('Saved',len(manifest['jobs']),'exact inputs',flush=True)
    if args.run:
        with ThreadPoolExecutor(max_workers=2) as pool:
            for f in as_completed([pool.submit(run,j,args.out,manifest['model']) for j in manifest['jobs']]):
                r=f.result();print(r['id'],len(r['answer']),r['missing_cases'],flush=True)

if __name__=='__main__':main()

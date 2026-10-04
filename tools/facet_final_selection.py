"""Select fixed rules only from complete, verified, identical populations."""
import argparse
import json
from pathlib import Path
from facet_program_lab import L
from verify_facet_program_results import verify


def select(parents,out):
    candidates=[];case_ids=None;provenance={}
    for parent in parents:
        plan=L.read(parent/'plan.json');status=L.read(parent/'status.json')
        if plan.get('smoke_only') or status.get('status')!='complete':
            raise ValueError('Completed population required: '+str(parent))
        if not verify(parent)['population_complete']:raise ValueError('Incomplete verification')
        if case_ids is None:case_ids=plan['case_ids']
        elif case_ids!=plan['case_ids']:raise ValueError('Population mismatch')
        programs={p['id']:p for p in plan['programs']}
        for row in L.read(parent/'report.json'):
            if row['cases']!=len(case_ids):raise ValueError('Partial report row')
            candidates.append(dict(source=str(parent.relative_to(L.ROOT)),program=programs[row['program_id']],results=row))
        for file in (parent/'plan.json',parent/'report.json',parent/'independent-verification.json'):
            provenance[str(file.relative_to(L.ROOT))]=L.digest(file)
    if not candidates:raise ValueError('No candidates')
    out.mkdir(parents=True,exist_ok=True)
    selections={}
    for metric,other,name in [('total_gold_hits','recall_id','best-total-hits'),('recall_id','total_gold_hits','best-macro-recall')]:
        chosen=min(candidates,key=lambda c:(-c['results'][metric],-c['results'][other],c['source'],c['program']['id']))
        record={**chosen,'selection':{'primary_metric':metric,'secondary_metric':other,
                  'tie_rule':'Stable source/program identity after both metrics; no complexity or future-equivalence claim.',
                  'scope':'Gold-informed fixed-rule development selection. No per-case gold selector or held-out claim.'}}
        L.write_new(out/(name+'.json'),record);selections[name]={'source':chosen['source'],'program_id':chosen['program']['id'],
            'total_gold_hits':chosen['results']['total_gold_hits'],'macro_recall':chosen['results']['recall_id']}
    L.write_new(out/'selection-manifest.json',{'case_ids':case_ids,'parent_sha256':provenance,
        'reported_configurations':len(candidates),'selections':selections,
        'count_note':'Configurations include observational aliases; count is not structural coverage.'})
    return selections


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--parent',type=Path,action='append',required=True)
    ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
    print(json.dumps(select([p.resolve() for p in args.parent],args.out)))

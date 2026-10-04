"""Replay selected fixed rules, inspect serving-boundary ties and recovered cases."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from facet_combined_workbench import LiveLab
from facet_program_lab import L
from facet_program_catalog import build


def boundary_tie(result,cut):
    order=result['order'];final=result['final']
    if not 0<cut<len(order):return False,0
    if 'assembly_components' in result:
        from facet_record_assembly_inspection import ordering_audit
        audit=ordering_audit(order,final.original,result['assembly_components'],result['assembly_id_order'],cut)
        return audit['id_sensitive_serving_cut'],max((x['end']-x['start'] for x in audit['crossing_id_ties']),default=0)
    # Every numeric priority preceding stable ID must agree. Tag arrival and
    # explicit within-tier evidence may distinguish equal nomination depths.
    keys=[final.depth,final.original!=final.depth]
    for name in ('tag_arrival','tie_evidence'):
        if name in result:keys.append(result[name])
    a,b=order[cut-1],order[cut]
    if any(key[a]!=key[b] for key in keys):return False,0
    mask=np.ones(len(order),dtype=bool)
    for key in keys:mask &= key[order]==key[a]
    return True,int(mask.sum())


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--selection',type=Path,required=True)
    args=ap.parse_args();lab=LiveLab()
    programs={'reference':build({})};expected={};parents={};parent_checks=0
    for name in ('best-total-hits','best-macro-recall'):
        value=L.read(args.selection/(name+'.json'));programs[name]=value['program'];expected[name]=value['results']
        parents[name]=L.ROOT/value['source']
    rows=[]
    for item in lab.manifest['cases']:
        cid=item['case_id'];case=lab.load(cid)
        for name,program in programs.items():
            result=lab.execute(case,program)
            if name=='reference':lab.parity(case,result)
            delivery,metrics=lab.measured(case,result)
            order=result['order'];split,tier_size=boundary_tie(result,len(delivery['full']))
            rows.append({'case_id':cid,'cohort':item['cohort'],'selection':name,**metrics,
                'full_chunk_ids':delivery['full'],'budget':delivery['budget'],
                'order_sha256':hashlib.sha256(order.tobytes()).hexdigest(),
                'id_tie_split_by_budget':split,'split_tier_size':tier_size})
            if item['cohort']=='original95' and name in parents:
                old=next(r for r in L.read(parents[name]/'cases'/(cid+'.json')) if r['program_id']==program['id'])
                for key in ('order_sha256','full_chunk_ids','budget','hits','recall_id'):
                    if rows[-1][key]!=old[key]:raise ValueError('Exact selected parent mismatch: '+cid+' '+name+' '+key)
                parent_checks+=1
        print(json.dumps({'completed_cases':len(rows)//len(programs)}),flush=True)
    summary={}
    for cohort in ('original95','recovered4'):
        summary[cohort]={}
        for name in programs:
            held=[r for r in rows if r['cohort']==cohort and r['selection']==name]
            if not held:raise ValueError('Missing cohort')
            value={'cases':len(held),'total_gold_hits':sum(r['hits'] for r in held),
                   'total_gold_count':sum(r['gold_count'] for r in held),
                   'macro_recall':sum(r['recall_id'] for r in held)/len(held),
                   'boundary_tie_cases':sum(r['id_tie_split_by_budget'] for r in held),
                   'largest_split_tier':max(r['split_tier_size'] for r in held)}
            summary[cohort][name]=value
            if cohort=='original95' and name in expected:
                if value['total_gold_hits']!=expected[name]['total_gold_hits'] or not np.isclose(value['macro_recall'],expected[name]['recall_id'],rtol=0,atol=1e-14):
                    raise ValueError('Selected-rule reproduction failed')
    L.write_new(args.selection/'selected-rule-audit.json',{'summary':summary,'cases':rows,'exact_parent_case_checks':parent_checks,
        'note':'Original selection population reproduced; recovered cases remain a separate additional check, not random held-out validation. Gold joined after retrieval. One interpretation remains failed.'})
    print(json.dumps(summary),flush=True)

"""Verify integrated frontier/management routes and unchanged tag parents."""
import json
from facet_directed_frontier_lab import L,PARENT
from verify_facet_program_results import verify

OUT=L.ROOT/'output/research/2026-09-24-directed-frontier-programs'

def audit():
    if L.read(OUT/'status.json')['status']!='complete':raise ValueError('Population still running')
    v=verify(OUT)
    if not v['population_complete']:raise ValueError('Incomplete population')
    p=L.read(OUT/'plan.json');checks=[];allrows={}
    for cid in p['case_ids']:
        rows={r['program_id']:r for r in L.read(OUT/'cases'/(cid+'.json'))};allrows[cid]=rows
        old={r['program_id']:r for r in L.read(PARENT/'cases'/(cid+'.json'))}
        for index in (1,20):
            program=p['programs'][index];a=old[program['integration_parent']];b=rows[program['id']]
            for key in ('order_sha256','full_chunk_ids','budget','hits','recall_id','precision_id','f1_id'):
                if a[key]!=b[key]:raise ValueError('Tag parent parity failed: '+cid+':'+key)
            checks.append({'case_id':cid,'program_id':program['id'],'order_delivery_metrics_equal':True})
    report={r['program_id']:r for r in L.read(OUT/'report.json')};comparisons=[]
    for i,program in enumerate(p['programs']):
        if 'directed_choices' not in program:continue
        baseline=p['programs'][1 if i<20 else 20]['id']
        diffs=[r[program['id']]['hits']-r[baseline]['hits'] for r in allrows.values()]
        comparisons.append({'program_id':program['id'],'parent_id':baseline,**program['directed_choices'],
          'hits':report[program['id']]['total_gold_hits'],'macro_recall':report[program['id']]['recall_id'],
          'hit_delta':sum(diffs),'wins':sum(x>0 for x in diffs),'losses':sum(x<0 for x in diffs),'ties':sum(x==0 for x in diffs)})
    result={'verification':v,'parent_comparisons':len(checks),'parent_parity':checks,'matched_results':comparisons,
       'highest_integrated_hits':max(comparisons,key=lambda r:r['hits']),
       'highest_integrated_macro':max(comparisons,key=lambda r:r['macro_recall'])}
    L.atomic(OUT/'directed-frontier-audit.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('parent_parity','matched_results')}))

if __name__=='__main__':audit()

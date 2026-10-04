"""Verify directed comparison accounting and exact unchanged-parent replay."""
import json
from facet_directed_lab import L,SELECTION
from verify_facet_program_results import verify

OUT=L.ROOT/'output/research/2026-09-24-directed-programs'

def audit():
    if L.read(OUT/'status.json')['status']!='complete':raise ValueError('Population still running')
    verification=verify(OUT)
    if not verification['population_complete']:raise ValueError('Incomplete population')
    plan=L.read(OUT/'plan.json');rows={cid:{r['program_id']:r for r in L.read(OUT/'cases'/(cid+'.json'))} for cid in plan['case_ids']}
    parity=[]
    for name,pid in [('best-total-hits','directed_0001'),('best-macro-recall','directed_0026')]:
        selection=L.read(SELECTION/(name+'.json'))
        for cid,current in rows.items():
            old=next(r for r in L.read(L.ROOT/selection['source']/'cases'/(cid+'.json')) if r['program_id']==selection['program']['id'])
            for key in ('order_sha256','full_chunk_ids','budget','hits','recall_id','precision_id','f1_id'):
                if old[key]!=current[pid][key]:raise ValueError('Parent parity failed: '+cid+':'+key)
            parity.append({'case_id':cid,'program_id':pid,'full_order_delivery_metrics_equal':True})
    byid={r['program_id']:r for r in L.read(OUT/'report.json')};comparisons=[]
    for i,p in enumerate(plan['programs']):
        if 'directed_choices' not in p:continue
        baseline='directed_0001' if i<26 else 'directed_0026'
        diffs=[r[p['id']]['hits']-r[baseline]['hits'] for r in rows.values()]
        comparisons.append({'program_id':p['id'],'parent_id':baseline,**p['directed_choices'],
          'hits':byid[p['id']]['total_gold_hits'],'macro_recall':byid[p['id']]['recall_id'],
          'hit_delta':sum(diffs),'wins':sum(x>0 for x in diffs),'losses':sum(x<0 for x in diffs),'ties':sum(x==0 for x in diffs)})
    result={'verification':verification,'parent_parity_comparisons':len(parity),'parent_parity':parity,
       'matched_to_unchanged_parents':comparisons,'highest_directed_hits':max(comparisons,key=lambda x:x['hits']),
       'highest_directed_macro':max(comparisons,key=lambda x:x['macro_recall'])}
    L.atomic(OUT/'directed-audit.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('parent_parity','matched_to_unchanged_parents')}))

if __name__=='__main__':audit()

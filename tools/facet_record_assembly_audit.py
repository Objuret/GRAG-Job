"""Independent accounting and exact unchanged recovery-parent verification."""
import json
from facet_record_assembly_lab import L
from verify_facet_program_results import verify

OUT=L.ROOT/'output/research/2026-09-24-record-assembly-programs'

def audit():
    if L.read(OUT/'status.json')['status']!='complete':raise ValueError('Population still running')
    verification=verify(OUT)
    if not verification['population_complete']:raise ValueError('Incomplete deliveries')
    p=L.read(OUT/'plan.json');rows={cid:{r['program_id']:r for r in L.read(OUT/'cases'/(cid+'.json'))} for cid in p['case_ids']}
    checks=[];control={}
    for program in p['programs']:
        if program.get('record_assembly',{}).get('mode')!='late':continue
        parent=program['record_parent'];control[json.dumps(parent,sort_keys=True)]=program['id']
        for cid,r in rows.items():
            old=next(x for x in L.read(L.ROOT/parent['source']/'cases'/(cid+'.json')) if x['program_id']==parent['program_id'])
            if any(old[k]!=r[program['id']][k] for k in ('order_sha256','full_chunk_ids','budget','hits','recall_id','precision_id','f1_id')):raise ValueError('Parent parity failed')
            checks.append({'case_id':cid,'program_id':program['id'],'order_delivery_metrics_equal':True})
    report={r['program_id']:r for r in L.read(OUT/'report.json')};comparisons=[]
    for program in p['programs']:
        if 'record_parent' not in program:continue
        baseline=control[json.dumps(program['record_parent'],sort_keys=True)]
        differences=[r[program['id']]['hits']-r[baseline]['hits'] for r in rows.values()]
        comparisons.append({'program_id':program['id'],'parent':program['record_parent'],'mode':program['record_assembly']['mode'],
            'hits':report[program['id']]['total_gold_hits'],'macro_recall':report[program['id']]['recall_id'],
            'hit_delta':sum(differences),'wins':sum(x>0 for x in differences),'losses':sum(x<0 for x in differences),'ties':sum(x==0 for x in differences)})
    result={'verification':verification,'parent_parity_count':len(checks),'parent_parity':checks,'comparisons':comparisons,
            'best_hits':max(comparisons,key=lambda r:r['hits']),'best_macro':max(comparisons,key=lambda r:r['macro_recall'])}
    L.atomic(OUT/'record-assembly-audit.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('parent_parity','comparisons')}))

if __name__=='__main__':audit()

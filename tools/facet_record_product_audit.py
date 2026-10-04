"""Check Product recovery results and replay controls through the prior engine."""
import hashlib
import json
from pathlib import Path
from facet_record_assembly_lab import L,RecordLab,edge_gate,priority_gate,inject
from artefact.facet_tag_frontier_fast import run_program
from verify_facet_program_results import verify

OUT=L.ROOT/'output/research/2026-09-24-record-product-programs'

def audit():
    if L.read(OUT/'status.json')['status']!='complete':raise ValueError('Population still running')
    verification=verify(OUT)
    if not verification['population_complete']:raise ValueError('Incomplete deliveries')
    p=L.read(OUT/'plan.json');lab=RecordLab();graph=lab.route_graphs['product']
    if graph is lab.graph:raise ValueError('Product graph not selected')
    controls=[x for x in p['programs'] if x.get('record_assembly',{}).get('mode')=='late']
    allrows={};checks=[]
    for cid in p['case_ids']:
        rows={r['program_id']:r for r in L.read(OUT/'cases'/(cid+'.json'))};allrows[cid]=rows;case=lab.load(cid)
        for program in controls:
            gate,_=(priority_gate if 'query_priority' in program else edge_gate)(graph,case['matrices'],case['weights'],**(program.get('query_priority') or program['tag_frontier']))
            result=run_program(inject(program),graph,case['matrices'],case['weights'],case['area'],lab.components,lab.id_order,cache=None,frontier_gate=gate)
            delivered,metrics=lab.measured(case,result);held=rows[program['id']]
            if hashlib.sha256(result['order'].tobytes()).hexdigest()!=held['order_sha256'] or delivered['full']!=held['full_chunk_ids'] or delivered['budget']!=held['budget'] or any(held[k]!=v for k,v in metrics.items()):raise ValueError('Prior engine control differs')
            checks.append({'case_id':cid,'program_id':program['id'],'prior_engine_order_delivery_metrics_equal':True})
    report={r['program_id']:r for r in L.read(OUT/'report.json')};comparisons=[]
    for index,program in enumerate(p['programs'][1:],1):
        baseline=p['programs'][2 if index<=5 else 7]['id'];differences=[r[program['id']]['hits']-r[baseline]['hits'] for r in allrows.values()]
        comparisons.append({'program_id':program['id'],'parent_control':baseline,'mode':program['record_assembly']['mode'],
            'hits':report[program['id']]['total_gold_hits'],'macro_recall':report[program['id']]['recall_id'],
            'hit_delta':sum(differences),'wins':sum(x>0 for x in differences),'losses':sum(x<0 for x in differences),'ties':sum(x==0 for x in differences),
            'order_changes':sum(r[program['id']]['order_sha256']!=r[baseline]['order_sha256'] for r in allrows.values()),
            'delivery_changes':sum(r[program['id']]['full_chunk_ids']!=r[baseline]['full_chunk_ids'] for r in allrows.values())})
    result={'verification':verification,'prior_engine_parity_count':len(checks),'prior_engine_parity':checks,'comparisons':comparisons,
            'best_hits':max(comparisons,key=lambda r:r['hits']),'best_macro':max(comparisons,key=lambda r:r['macro_recall'])}
    L.atomic(OUT/'record-product-audit.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('prior_engine_parity','comparisons')}))

if __name__=='__main__':audit()

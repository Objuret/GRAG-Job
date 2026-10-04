"""Cross tag recruitment winners with explicit management-route traversal."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
from facet_directed_lab import L,SNAPSHOT,variant
from facet_directed_values import project
from facet_fast_resume import FastLab
from facet_program_lab import plan as base_plan
from facet_program_catalog import build
from artefact.facet_tag_frontier import edge_gate,inject
from artefact.facet_directed_frontier_engine import run_program
from verify_facet_program_results import verify
import facet_joint_search as runner

PARENT=L.ROOT/'output/research/2026-09-24-tag-frontier-programs'

def execute_directed_frontier(lab,case,program):
    if not hasattr(lab,'directed_routes'):lab.directed_routes=project(lab.graph.chunk_ids,L.read(SNAPSHOT))
    policy=program.get('tag_frontier');gate=None;state=None
    if policy:
        cache=case.setdefault('directed_frontier_cache',{});key=json.dumps(policy,sort_keys=True)
        if key not in cache:cache[key]=edge_gate(lab.graph,case['matrices'],case['weights'],**policy)
        gate,state=cache[key];program=inject(program)
    graph=lab.route_graphs[program['graph_route']] if 'graph_route' in program else lab.graph
    result=run_program(program,graph,case['matrices'],case['weights'],case['area'],lab.components,lab.id_order,
                       cache=case['cache'],frontier_gate=gate,directed_routes=lab.directed_routes)
    if state:
        result['tag_frontier']={k:v for k,v in state.items() if not hasattr(v,'shape')}
        result['tag_frontier_arrays']={k:v for k,v in state.items() if hasattr(v,'shape')}
        result['stages']['tag_frontier']={'op':'tag_frontier','inputs':['query_tag_cosines','query_facet_weights'],**result['tag_frontier'],'policy':policy}
    return result

class DirectedFrontierLab(FastLab):
    def execute(self,case,program):return execute_directed_frontier(self,case,program)

def plan(smoke=False):
    if L.read(PARENT/'status.json')['status']!='complete' or not verify(PARENT)['population_complete']:raise ValueError('Verified complete tag parent required')
    parent=L.read(PARENT/'plan.json');byid={p['id']:p for p in parent['programs']};report=L.read(PARENT/'report.json')
    seeds=[byid[max(report,key=lambda r:r[k])['program_id']] for k in ('total_gold_hits','recall_id')]
    programs=[{**build({}),'id':'reference','graph_route':'product_channel'}]
    for seed in seeds:
        control=deepcopy(seed);control['integration_parent']=seed['id'];programs.append(control)
        for route in ('employee_channel','employee_product'):
            for direction in ('forward','reverse','symmetric'):
                for placement in ('replace','before','parallel'):
                    p=variant(seed,route,direction,placement);p['integration_parent']=seed['id'];programs.append(p)
    for i,p in enumerate(programs):p['id']='directed_frontier_'+str(i).zfill(4)
    p=base_plan();p.update(programs=programs,smoke_only=smoke,parent_sha256={},coverage='Two tag-frontier winners crossed with channel/product management routes in forward/reverse/symmetric directions before/within/parallel existing walk; original tag-frontier parents retained.')
    if smoke:p['case_ids']=p['case_ids'][:1]
    p['input_sha256'].update(parent['input_sha256'])
    for f in [Path(__file__),L.ROOT/'tools/facet_directed_lab.py',L.ROOT/'tools/facet_directed_values.py',L.ROOT/'test/artefact/facet_directed_frontier_engine.py',SNAPSHOT]:p['input_sha256'][str(f.relative_to(L.ROOT))]=L.digest(f)
    for f in [PARENT/'plan.json',PARENT/'report.json',*[PARENT/'cases'/(cid+'.json') for cid in parent['case_ids']]]:p['parent_sha256'][str(f.relative_to(L.ROOT))]=L.digest(f)
    return p

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('command',choices=['plan','batch']);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--smoke',action='store_true');a=ap.parse_args()
    if a.command=='plan':
        p=plan(a.smoke);a.out.mkdir(parents=True,exist_ok=True);L.write_new(a.out/'plan.json',p);print(json.dumps({'programs':len(p['programs']),'cases':len(p['case_ids'])}))
    else:runner.RouteLab=DirectedFrontierLab;runner.batch(a.out)

"""Bounded recovery placement/assembly comparison; source delivery stays outside."""
import argparse
import json
from pathlib import Path
from facet_directed_lab import L,SNAPSHOT
from facet_directed_values import project
from facet_fast_resume import FastLab
from facet_program_lab import plan as base_plan
from facet_program_catalog import build
from facet_record_assembly_programs import transform,MODES
from artefact.facet_tag_frontier import edge_gate,inject
from artefact.facet_query_priority import edge_gate as priority_gate
from artefact.facet_record_assembly_engine import run_program
from verify_facet_program_results import verify
import facet_joint_search as runner

PARENTS=(('2026-09-24-tag-frontier-programs','total_gold_hits'),
         ('2026-09-24-query-priority','recall_id'),
         ('2026-09-24-directed-frontier-programs','total_gold_hits'))

def execute_record(lab,case,program):
    graph=getattr(lab,'route_graphs',{}).get(program.get('graph_route'),lab.graph)
    policy=program.get('query_priority') or program.get('tag_frontier');kind='priority' if 'query_priority' in program else 'tag'
    gate=None;state=None
    if policy:
        cache=case.setdefault('record_gate_cache',{});key=(kind,json.dumps(policy,sort_keys=True))
        if key not in cache:cache[key]=(priority_gate if kind=='priority' else edge_gate)(graph,case['matrices'],case['weights'],**policy)
        gate,state=cache[key]
        if not any(n['id']=='tag_frontier_gate' for n in program['nodes']):program=inject(program)
    routes=None
    if any(n['op']=='directed_propagate' for n in program['nodes']):
        if not hasattr(lab,'record_directed_routes'):lab.record_directed_routes=project(graph.chunk_ids,L.read(SNAPSHOT))
        routes=lab.record_directed_routes
    result=run_program(program,graph,case['matrices'],case['weights'],case['area'],lab.components,lab.id_order,
                       cache=case['cache'],frontier_gate=gate,directed_routes=routes)
    if state:
        result['stages']['record_tag_frontier']={'op':'tag_frontier' if kind=='tag' else 'query_priority',
            'inputs':['query_tag_cosines','query_facet_weights'],'policy':policy,
            **{k:v for k,v in state.items() if not hasattr(v,'shape')}}
    return result

class RecordLab(FastLab):
    def execute(self,case,program):return execute_record(self,case,program)

def plan(smoke=False):
    p=base_plan();p.update(programs=[{**build({}),'id':'record_reference','graph_route':'product_channel'}],parent_sha256={},smoke_only=smoke)
    for folder,metric in PARENTS:
        root=L.ROOT/'output/research'/folder
        if L.read(root/'status.json')['status']!='complete' or not verify(root)['population_complete']:raise ValueError('Verified parent required')
        parent=L.read(root/'plan.json');best=max(L.read(root/'report.json'),key=lambda row:row[metric]);seed=next(x for x in parent['programs'] if x['id']==best['program_id'])
        for mode in MODES:
            item=transform(seed,mode);item['id']='record_'+str(len(p['programs'])).zfill(4)
            item['record_parent']={'source':str(root.relative_to(L.ROOT)),'program_id':seed['id']}
            p['programs'].append(item)
        p['input_sha256'].update(parent['input_sha256'])
        for f in [root/'plan.json',root/'report.json',*[root/'cases'/(cid+'.json') for cid in parent['case_ids']]]:p['parent_sha256'][str(f.relative_to(L.ROOT))]=L.digest(f)
    for f in [Path(__file__),L.ROOT/'tools/facet_record_assembly_programs.py',L.ROOT/'test/artefact/facet_record_assembly.py',L.ROOT/'test/artefact/facet_record_assembly_engine.py',SNAPSHOT]:p['input_sha256'][str(f.relative_to(L.ROOT))]=L.digest(f)
    p['coverage']='Three fixed tag/query-priority/directed-tag parents crossed with off, existing late recovery, component-max before nomination, component-max before graph with late recovery, and component-contiguous assembly. Exact existing record components only; no cost/gold/body inputs. Shared serialized72k prefix unchanged.'
    if smoke:p['case_ids']=p['case_ids'][:1]
    return p

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('command',choices=['plan','batch']);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--smoke',action='store_true');a=ap.parse_args()
    if a.command=='plan':
        p=plan(a.smoke);a.out.mkdir(parents=True,exist_ok=True);L.write_new(a.out/'plan.json',p);print(json.dumps({'programs':len(p['programs']),'cases':len(p['case_ids'])}))
    else:runner.RouteLab=RecordLab;runner.batch(a.out)

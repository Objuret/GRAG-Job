"""Matched directions, placement and sponsor aggregation on live pinned routes."""
import argparse
from copy import deepcopy
from pathlib import Path
import json
from facet_fast_resume import FastLab
from facet_program_lab import L,plan as base_plan
from facet_program_catalog import build
from facet_directed_values import project
from artefact.facet_directed_engine import run_program
import facet_joint_search as runner

SNAPSHOT=L.ROOT/'output/research/2026-09-24-directed-routes/directed-snapshot.json'
SELECTION=L.ROOT/'output/research/2026-09-24-structural-selection'

def execute_directed(lab,case,program):
    if not hasattr(lab,'directed_routes'):lab.directed_routes=project(lab.graph.chunk_ids,L.read(SNAPSHOT))
    graph=lab.route_graphs[program['graph_route']] if 'graph_route' in program else lab.graph
    return run_program(program,graph,case['matrices'],case['weights'],case['area'],lab.components,lab.id_order,cache=case['cache'],directed_routes=lab.directed_routes)

class DirectedLab(FastLab):
    def execute(self,case,program):return execute_directed(self,case,program)

def variant(seed,route,direction,placement,aggregation='maximum'):
    p=deepcopy(seed);walks=[n for n in p['nodes'] if n['id'].startswith('walk_') and n['op']=='propagate']
    if not walks:raise ValueError('No walk nodes')
    params=dict(route=route,direction=direction,aggregation=aggregation,decay=.5)
    if placement=='replace':
        for node in walks:node['op']='directed_propagate';node['params']=params.copy()
    else:
        first=walks[0];pos=p['nodes'].index(first);source=first['inputs'][0]
        added=[dict(id='directed_entry',op='directed_propagate',inputs=list(first['inputs']),params=params)]
        if placement=='parallel':
            added.append(dict(id='directed_join',op='maximum',inputs=[source,'directed_entry']));first['inputs'][0]='directed_join'
        elif placement=='before':first['inputs'][0]='directed_entry'
        else:raise ValueError('Unknown placement')
        p['nodes'][pos:pos]=added
    p['directed_choices']=dict(route=route,direction=direction,placement=placement,aggregation=aggregation,
      self_policy='exclude same chunk',duplicate_policy='unique source-target chunk sponsors across employee paths')
    return p

def plan(smoke=False):
    programs=[{**build({}),'id':'directed_reference','graph_route':'product_channel'}]
    parents=[SELECTION/(x+'.json') for x in ('best-total-hits','best-macro-recall')]
    for file in parents:
        seed=L.read(file)['program'];programs.append(deepcopy(seed))
        for route in ('employee_channel','employee_product'):
            for direction in ('forward','reverse','symmetric'):
                for placement in ('replace','before','parallel'):programs.append(variant(seed,route,direction,placement))
        for direction in ('forward','reverse','symmetric'):
            for aggregation in ('mean','sum'):programs.append(variant(seed,'employee_channel',direction,'replace',aggregation))
    for i,p in enumerate(programs):p['id']='directed_'+str(i).zfill(4)
    p=base_plan();p.update(programs=programs,parent_sha256={str(f.relative_to(L.ROOT)):L.digest(f) for f in parents},smoke_only=smoke,
      coverage='Opaque chunk-employee-manages-employee-chunk forward/reverse/symmetric routes, before/within/parallel traversal; unique source chunk sponsors; self removed; both selected parents.')
    if smoke:p['case_ids']=p['case_ids'][:1]
    for f in [Path(__file__),L.ROOT/'tools/facet_directed_values.py',L.ROOT/'test/artefact/facet_directed_engine.py',SNAPSHOT]:p['input_sha256'][str(f.relative_to(L.ROOT))]=L.digest(f)
    return p

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('command',choices=['plan','batch']);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--smoke',action='store_true');args=ap.parse_args()
    if args.command=='plan':
        p=plan(args.smoke);args.out.mkdir(parents=True,exist_ok=True);L.write_new(args.out/'plan.json',p);print(json.dumps({'programs':len(p['programs']),'cases':len(p['case_ids'])}))
    else:runner.RouteLab=DirectedLab;runner.batch(args.out)

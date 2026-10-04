"""One verified query-priority seed crossed with management-route structure."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
from facet_directed_lab import L,SNAPSHOT,variant
from facet_directed_values import project
from facet_fast_resume import FastLab
from facet_program_lab import plan as base_plan
from facet_program_catalog import build
from artefact.facet_query_priority import edge_gate
from artefact.facet_tag_frontier import inject
from artefact.facet_directed_frontier_engine import run_program
from artefact.facet_construction_program import Signal,Nomination
from verify_facet_program_results import verify
import facet_joint_search as runner

PARENT=L.ROOT/'output/research/2026-09-24-query-priority'
OUT=L.ROOT/'output/research/2026-09-24-query-priority-directed'


def execute_numeric(program,graph,matrices,weights,area,components,id_order,directed_routes,cache=None):
    """Value-only execution: no source payload, gold or delivery sizes."""
    state=None;gate=None
    if 'query_priority' in program:
        gate,state=edge_gate(graph,matrices,weights,**program['query_priority'])
        if not any(n['id']=='tag_frontier_gate' for n in program['nodes']):program=inject(program)
    r=run_program(program,graph,matrices,weights,area,components,id_order,
                  cache=cache,frontier_gate=gate,directed_routes=directed_routes)
    if state is not None:
        r['query_priority_state']=state
        r['stages']['query_priority']={'op':'query_priority','policy':program['query_priority'],
            **{k:v for k,v in state.items() if not hasattr(v,'shape')}}
    return r


def execute(lab,case,program):
    if not hasattr(lab,'directed_routes'):lab.directed_routes=project(lab.graph.chunk_ids,L.read(SNAPSHOT))
    graph=lab.route_graphs[program['graph_route']] if 'graph_route' in program else lab.graph
    r=execute_numeric(program,graph,case['matrices'],case['weights'],case['area'],lab.components,
                      lab.id_order,lab.directed_routes,cache=case['cache'])
    r['states']={name:Signal(x.values,x.domain) if hasattr(x,'values') else
        Nomination(x.depth,x.original,x.sponsors) for name,x in r['states'].items()}
    r['final']=r['states'][program['output']]
    return r


class PriorityDirectedLab(FastLab):
    def execute(self,case,program):return execute(self,case,program)


def plan(smoke=False):
    if L.read(PARENT/'status.json')['status']!='complete' or not verify(PARENT)['population_complete']:
        raise ValueError('Verified complete query-priority parent required')
    parent=L.read(PARENT/'plan.json');report=L.read(PARENT/'report.json')
    chosen=max(report,key=lambda r:(r['recall_id'],r['total_gold_hits']))['program_id']
    seed=next(p for p in parent['programs'] if p['id']==chosen)
    if seed.get('query_priority',{}).get('method')!='lexicographic':raise ValueError('Expected lexicographic seed')
    programs=[{**build({}),'graph_route':'product_channel'},deepcopy(seed)]
    for route in ('employee_channel','employee_product'):
        for direction in ('forward','reverse','symmetric'):
            for placement in ('replace','before','parallel'):
                programs.append(variant(seed,route,direction,placement))
    for i,p in enumerate(programs):
        p['id']='query_priority_directed_'+str(i).zfill(4)
        if i:p['integration_parent']=chosen
    p=base_plan();p.update(programs=programs,smoke_only=smoke,parent_sha256={},
        coverage='One verified lexicographic-first tag-priority macro leader unchanged and crossed with 2 management bindings x 3 directions x 3 placements, plus canonical guard: 19 seed contexts, 20 programs. Fixed maximum sponsors, .5 decay and existing parent query/description/scope operations; not exhaustive combinations.')
    if smoke:p['case_ids']=p['case_ids'][:1]
    p['input_sha256'].update(parent['input_sha256'])
    for f in (Path(__file__),L.ROOT/'tools/facet_directed_lab.py',L.ROOT/'tools/facet_directed_values.py',L.ROOT/'test/artefact/facet_directed_frontier_engine.py',SNAPSHOT):
        p['input_sha256'][str(f.relative_to(L.ROOT))]=L.digest(f)
    for f in (PARENT/'plan.json',PARENT/'report.json',*[PARENT/'cases'/(c+'.json') for c in parent['case_ids']]):
        p['parent_sha256'][str(f.relative_to(L.ROOT))]=L.digest(f)
    return p


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('command',choices=('plan','batch'))
    ap.add_argument('--out',type=Path,default=OUT);ap.add_argument('--smoke',action='store_true');a=ap.parse_args()
    if a.command=='plan':
        p=plan(a.smoke);a.out.mkdir(parents=True,exist_ok=True);L.write_new(a.out/'plan.json',p)
        print(json.dumps({'programs':len(p['programs']),'cases':len(p['case_ids'])}))
    else:runner.RouteLab=PriorityDirectedLab;runner.batch(a.out)

"""Boundary follow-up for completed-population ordering leaders."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
from facet_ordering_programs import transform
from facet_program_catalog import build
from facet_program_lab import L,plan as base_plan
from facet_fast_resume import FastLab
import facet_joint_search as runner
from verify_facet_program_results import verify

PARENT=L.ROOT/'output/research/2026-09-23-ordering-programs-v2'
DEPTHS=(1,2,3,4,5,6,7,8,12,15,16,24,31,32)


def extend(seed, rounds, feedback):
    if not isinstance(rounds,int) or not 1<=rounds<=32 or feedback not in ('latest','retain_seed'):
        raise ValueError('Invalid finite-depth hypothesis')
    settings={**seed['ordering'],'rounds':1,'feedback':'latest','graph_route':seed['graph_route']}
    program=transform(seed['factors'],**settings)
    nodes=[];last=None
    for original in program['nodes']:
        node=deepcopy(original)
        if node['id']=='walk_1':
            start=node['inputs'][0];previous=start
            for step in range(1,rounds+1):
                walk=deepcopy(node);walk['id']='walk_'+str(step);walk['inputs'][0]=previous
                nodes.append(walk);previous=walk['id']
                if feedback=='retain_seed' and step<rounds:
                    previous='seed_feedback_'+str(step)
                    nodes.append(dict(id=previous,op='maximum',inputs=[start,walk['id']],params={}))
            last=previous
        else:
            if last is not None:node['inputs']=[last if x=='walk_1' else x for x in node['inputs']]
            nodes.append(node)
    return {**program,'nodes':nodes,'ordering':{**program['ordering'],'rounds':rounds,'feedback':feedback},
            'depth_seed':seed['id']}


def plan(smoke=False):
    if L.read(PARENT/'status.json')['status']!='complete' or not verify(PARENT)['population_complete']:
        raise ValueError('Completed verified parent required')
    parent=L.read(PARENT/'plan.json');report=L.read(PARENT/'report.json')
    # Preserve both aggregate objectives and all nondominated fixed rules.
    frontier=[r for r in report if not any(s['total_gold_hits']>=r['total_gold_hits'] and s['recall_id']>=r['recall_id']
                  and (s['total_gold_hits']>r['total_gold_hits'] or s['recall_id']>r['recall_id']) for s in report)]
    seeds=[p for p in parent['programs'] if p['id'] in {r['program_id'] for r in frontier}]
    programs=[{**build({}),'id':'depth_reference','graph_route':'product_channel','ordering':{'reference':True}}]
    for seed in seeds:
        for depth in DEPTHS:
            for feedback in ('latest','retain_seed'):
                if depth==1 and feedback=='retain_seed':continue
                p=extend(seed,depth,feedback);p['id']='depth_'+str(len(programs)).zfill(4);programs.append(p)
    p=base_plan();p.update(programs=programs,smoke_only=smoke,
        depth_seed_ids=[s['id'] for s in seeds],parent_sha256={},
        coverage='Odd/even and deeper finite walks with/without seed reinsertion, from the completed ordering Pareto frontier. No convergence or global-optimum claim.')
    if smoke:p['case_ids']=p['case_ids'][:1]
    for file in [PARENT/'plan.json',PARENT/'report.json',*[PARENT/'cases'/(cid+'.json') for cid in parent['case_ids']]]:
        p['parent_sha256'][str(file.relative_to(L.ROOT))]=L.digest(file)
    for file in [Path(__file__),L.ROOT/'tools/facet_ordering_programs.py',L.ROOT/'tools/facet_joint_search.py',
                 L.ROOT/'tools/facet_fast_resume.py',L.ROOT/'test/artefact/facet_construction_fast.py',
                 L.ROOT/'tools/facet_route_program_lab.py',L.ROOT/'tools/facet_structural_routes.py']:
        p['input_sha256'][str(file.relative_to(L.ROOT))]=L.digest(file)
    return p


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('command',choices=['plan','batch'])
    ap.add_argument('--out',type=Path,required=True);ap.add_argument('--smoke',action='store_true');args=ap.parse_args()
    if args.command=='plan':
        p=plan(args.smoke);args.out.mkdir(parents=True,exist_ok=True);L.write_new(args.out/'plan.json',p)
        print(json.dumps({'programs':len(p['programs']),'seeds':p['depth_seed_ids'],'cases':len(p['case_ids'])}))
    else:
        runner.RouteLab=FastLab;runner.batch(args.out)
        p=L.read(args.out/'plan.json');metadata={x['id']:x for x in p['programs']};rows=L.read(args.out/'report.json')
        for row in rows:row['ordering']=metadata[row['program_id']]['ordering']
        L.atomic(args.out/'report.json',rows)

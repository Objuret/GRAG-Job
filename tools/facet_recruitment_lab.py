"""Population comparison for recruitment evidence feeding graph traversal."""
import argparse
import json
from pathlib import Path
from facet_fast_resume import FastLab
from facet_scope_program_lab import ScopeOverride
from facet_recruitment_programs import recruit_before_walk
from facet_program_lab import L,plan as base_plan
from artefact.facet_construction_feedback import run_program
from facet_program_catalog import build
import facet_joint_search as runner
from verify_facet_program_results import verify

PARENT=L.ROOT/'output/research/2026-09-24-depth-programs'


def execute_feedback(lab,case,program):
    graph=lab.route_graphs[program['graph_route']] if 'graph_route' in program else lab.graph
    return run_program(program,graph,case['matrices'],case['weights'],case['area'],
                       lab.components,lab.id_order,cache=case['cache'])


class FeedbackBase(FastLab):
    def execute(self,case,program):return execute_feedback(self,case,program)


class FeedbackLab(ScopeOverride,FeedbackBase):
    pass


def plan(smoke=False):
    if L.read(PARENT/'status.json')['status']!='complete' or not verify(PARENT)['population_complete']:
        raise ValueError('Completed verified parent required')
    parent=L.read(PARENT/'plan.json');report=L.read(PARENT/'report.json')
    frontier=[r for r in report if not any(s['total_gold_hits']>=r['total_gold_hits'] and s['recall_id']>=r['recall_id']
       and (s['total_gold_hits']>r['total_gold_hits'] or s['recall_id']>r['recall_id']) for s in report)]
    seeds=[p for p in parent['programs'] if p['id'] in {r['program_id'] for r in frontier}]
    programs=[{**build({}),'id':'feedback_reference','graph_route':'product_channel'}]
    for seed in seeds:
        programs.append({**seed,'id':'feedback_'+str(len(programs)).zfill(4),'feedback_seed':seed['id']})
        for mode in ('sponsor_scores','inverse_sponsors','inverse_all'):
            for placement in ('graph_only','all_paths'):
                for method in ('best_rank','independent_batches'):
                    p=recruit_before_walk(seed,mode,placement,method)
                    p.update(id='feedback_'+str(len(programs)).zfill(4),feedback_seed=seed['id']);programs.append(p)
    p=base_plan();p.update(programs=programs,parent_sha256={},smoke_only=smoke,
        coverage='Early independent complete-tier recruitment feeding graph only or all paths; first sponsors versus all positive supporters; original scores versus inverse admission depth; final best rank versus independent batches. Both verified depth leaders retained.')
    if smoke:p['case_ids']=p['case_ids'][:1]
    p['input_sha256'].update(parent['input_sha256'])
    for file in [Path(__file__),L.ROOT/'tools/facet_recruitment_programs.py',
                 L.ROOT/'tools/facet_scope_program_lab.py',L.ROOT/'test/artefact/facet_construction_feedback.py',
                 L.ROOT/'test/artefact/facet_recruitment_feedback.py']:
        p['input_sha256'][str(file.relative_to(L.ROOT))]=L.digest(file)
    for file in [PARENT/'plan.json',PARENT/'report.json',*[PARENT/'cases'/(cid+'.json') for cid in parent['case_ids']]]:
        p['parent_sha256'][str(file.relative_to(L.ROOT))]=L.digest(file)
    return p


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('command',choices=['plan','batch'])
    ap.add_argument('--out',type=Path,required=True);ap.add_argument('--smoke',action='store_true');args=ap.parse_args()
    if args.command=='plan':
        p=plan(args.smoke);args.out.mkdir(parents=True,exist_ok=True);L.write_new(args.out/'plan.json',p)
        print(json.dumps({'programs':len(p['programs']),'cases':len(p['case_ids'])}))
    else:
        runner.RouteLab=FeedbackLab;runner.batch(args.out)

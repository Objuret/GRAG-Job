"""Cross verified ordering leaders with scope formation and graph relations."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from facet_depth_followup import extend
from facet_scope_program_lab import ScopeLab
from facet_program_lab import L,plan as base_plan
from facet_program_catalog import build
from facet_joint_search import ROUTES
import facet_joint_search as runner
from verify_facet_program_results import verify

DEPTH=L.ROOT/'output/research/2026-09-24-depth-programs'
SCOPES=L.ROOT/'output/research/2026-09-23-scope-programs'


def compose(seed,route,signature='frozen',policy=None,stage='after_paths',admission='area_first',recruitment=None):
    source=deepcopy(seed)
    source['factors'].update(scope_stage='after_paths',admission=admission,
                             recruitment=recruitment or seed['factors']['recruitment'])
    source['graph_route']=route
    p=extend(source,source['ordering']['rounds'],source['ordering']['feedback'])
    if stage=='before_paths':
        nodes=[];after=False
        for raw in p['nodes']:
            n=deepcopy(raw)
            if after:n['inputs']=['scope_before_paths' if x=='direct' else x for x in n['inputs']]
            nodes.append(n)
            if n['id']=='direct':
                nodes.append(dict(id='scope_before_paths',op='mask',inputs=['direct',p['area_node']],params={}))
                after=True
        p['nodes']=nodes
    elif stage!='after_paths':raise ValueError('Unknown scope stage')
    p['factors']['scope_stage']=stage;p['scope_input_signature']=signature
    if policy is not None:p['scope_policy']=policy
    return p


def plan(smoke=False):
    for parent in (DEPTH,SCOPES):
        if L.read(parent/'status.json')['status']!='complete' or not verify(parent)['population_complete']:
            raise ValueError('Verified completed parent required')
    dp=L.read(DEPTH/'plan.json');sp=L.read(SCOPES/'plan.json');report=L.read(DEPTH/'report.json')
    if dp['case_ids']!=sp['case_ids']:raise ValueError('Parent populations differ')
    frontier=[r for r in report if not any(s['total_gold_hits']>=r['total_gold_hits'] and s['recall_id']>=r['recall_id']
       and (s['total_gold_hits']>r['total_gold_hits'] or s['recall_id']>r['recall_id']) for s in report)]
    seeds=[p for p in dp['programs'] if p['id'] in {r['program_id'] for r in frontier}]
    programs=[{**build({}),'id':'integrated_reference','graph_route':'product_channel'}];seen=set()
    def add(p):
        key=json.dumps([p['nodes'],p['graph_route'],p.get('scope_policy')],sort_keys=True)
        if key in seen:return
        seen.add(key);p['id']='integrated_'+str(len(programs)).zfill(4);programs.append(p)
    for seed in seeds:
        for route in ROUTES:
            for signature,group in [('frozen',None),*sp['scope_mask_groups'].items()]:
                add(compose(seed,route,signature,None if group is None else group['policy']))
        for recruitment in ('joint','facets'):
            for admission in ('equal_depth','area_first','area_only'):
                for stage in ('before_paths','after_paths'):
                    add(compose(seed,seed['graph_route'],stage=stage,admission=admission,recruitment=recruitment))
    p=base_plan();p.update(programs=programs,parent_sha256={},smoke_only=smoke,
       integrated_seed_ids=[s['id'] for s in seeds],
       coverage='Complete scope-input by graph-route cross for both depth Pareto leaders; additional recruitment by admission by scope-timing cross in their frozen-scope graph context. Not an exhaustive cross of every dimension.')
    if smoke:p['case_ids']=p['case_ids'][:1]
    p['input_sha256'].update(dp['input_sha256']);p['input_sha256'].update(sp['input_sha256'])
    p['input_sha256'][str(Path(__file__).relative_to(L.ROOT))]=L.digest(Path(__file__))
    for parent,pp in ((DEPTH,dp),(SCOPES,sp)):
        for file in [parent/'plan.json',parent/'report.json',*[parent/'cases'/(cid+'.json') for cid in pp['case_ids']]]:
            p['parent_sha256'][str(file.relative_to(L.ROOT))]=L.digest(file)
    return p


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('command',choices=['plan','batch'])
    ap.add_argument('--out',type=Path,required=True);ap.add_argument('--smoke',action='store_true');args=ap.parse_args()
    if args.command=='plan':
        p=plan(args.smoke);args.out.mkdir(parents=True,exist_ok=True);L.write_new(args.out/'plan.json',p)
        print(json.dumps({'programs':len(p['programs']),'cases':len(p['case_ids']),'seeds':p['integrated_seed_ids']}))
    else:
        runner.RouteLab=ScopeLab;runner.batch(args.out)
        p=L.read(args.out/'plan.json');programs={x['id']:x for x in p['programs']};rows=L.read(args.out/'report.json')
        for row in rows:row['ordering']=programs[row['program_id']].get('ordering',{'reference':True})
        L.atomic(args.out/'report.json',rows)

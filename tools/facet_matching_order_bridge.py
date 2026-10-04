"""Bridge the completed matching findings into the verified ordering leaders."""
import argparse
import json
from pathlib import Path
from facet_program_lab import L,plan as base_plan
from facet_program_catalog import build,FACTORS
from facet_ordering_programs import transform
from verify_facet_program_results import verify


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
    depth=L.ROOT/'output/research/2026-09-24-depth-programs'
    joint=L.ROOT/'output/research/2026-09-23-joint-search-round1'
    for parent in (depth,joint):
        if L.read(parent/'status.json')['status']!='complete' or not verify(parent)['population_complete']:
            raise ValueError('Complete verified parents required')
    dp=L.read(depth/'plan.json');report=L.read(depth/'report.json')
    ids={max(report,key=lambda r:(r['total_gold_hits'],r['recall_id']))['program_id'],
         max(report,key=lambda r:(r['recall_id'],r['total_gold_hits']))['program_id']}
    programs=[{**build({}),'id':'bridge_reference','graph_route':'product_channel'}]
    for seed in dp['programs']:
        if seed['id'] not in ids:continue
        for matching in FACTORS['matching']:
            p=transform({**seed['factors'],'matching':matching},**seed['ordering'],graph_route=seed['graph_route'])
            p.update(id='bridge_'+str(len(programs)).zfill(3),bridge_seed=seed['id']);programs.append(p)
    p=base_plan();p.update(programs=programs,parent_sha256={},coverage='All five matching operators crossed with the two completed-population ordering leaders. Bridge of completed experiments, not an exhaustive new factor cross.')
    p['input_sha256'].update(dp['input_sha256'])
    for file in [Path(__file__),L.ROOT/'tools/facet_joint_search_fast.py']:
        p['input_sha256'][str(file.relative_to(L.ROOT))]=L.digest(file)
    for parent in (depth,joint):
        pp=L.read(parent/'plan.json')
        if pp['case_ids']!=p['case_ids']:raise ValueError('Population mismatch')
        for file in [parent/'plan.json',parent/'report.json',*[parent/'cases'/(cid+'.json') for cid in pp['case_ids']]]:
            p['parent_sha256'][str(file.relative_to(L.ROOT))]=L.digest(file)
    args.out.mkdir(parents=True,exist_ok=True);L.write_new(args.out/'plan.json',p)
    print(json.dumps({'programs':len(programs),'cases':len(p['case_ids'])}))

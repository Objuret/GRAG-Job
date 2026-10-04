"""Exercise record recovery where the existing product route reaches fragments."""
import argparse
import json
from copy import deepcopy
from pathlib import Path
from facet_record_assembly_lab import L,RecordLab
from facet_record_assembly_programs import transform,MODES
import facet_joint_search as runner

BASE=L.ROOT/'output/research/2026-09-24-record-assembly-programs'

def plan(smoke=False):
    old=L.read(BASE/'plan.json');p=deepcopy(old);p['programs']=[deepcopy(old['programs'][0])]
    for index in (2,7):
        seed=deepcopy(old['programs'][index]);seed['graph_route']='product'
        for mode in MODES:
            item=transform(seed,mode);item['id']='record_product_'+str(len(p['programs'])).zfill(4)
            item['record_context']='product_route_reaches_all_569_multirecord_chunks'
            p['programs'].append(item)
    p['smoke_only']=smoke
    if smoke:p['case_ids']=p['case_ids'][:1]
    p['coverage']='Graph-selected positive control: existing product groups reach all569 multiple-record chunks; product+channel groups reachnone. Two fixed tag/query-priority parents crossedwith5recordrecoverymodes; no gold-informed route choice.'
    for file in [Path(__file__),BASE/'plan.json',BASE/'component-route-inventory.json']:
        p['input_sha256'][str(file.relative_to(L.ROOT))]=L.digest(file)
    return p

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('command',choices=['plan','batch']);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--smoke',action='store_true');a=ap.parse_args()
    if a.command=='plan':
        p=plan(a.smoke);a.out.mkdir(parents=True,exist_ok=True);L.write_new(a.out/'plan.json',p);print(json.dumps({'programs':len(p['programs']),'cases':len(p['case_ids'])}))
    else:runner.RouteLab=RecordLab;runner.batch(a.out)

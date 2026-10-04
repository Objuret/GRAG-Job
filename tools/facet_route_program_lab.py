"""Matched structural-entity route comparisons over the graph-only program core."""
from pathlib import Path
import argparse
import hashlib
import itertools
import json
import os
import time
import numpy as np
from facet_program_lab import ProgramLab, L, build, plan as base_plan
from artefact.facet_construction_program import run_program
from facet_structural_routes import load_projections, inventory, SNAPSHOT

OUT=L.ROOT/'output/research/2026-09-23-entity-route-programs'


class RouteLab(ProgramLab):
 def __init__(self):
  super().__init__();self.route_graphs=load_projections(self.graph)
 def execute(self,case,program):
  graph=self.route_graphs[program['graph_route']] if 'graph_route' in program else self.graph
  return run_program(program,graph,case['matrices'],case['weights'],case['area'],
    self.components,self.id_order,cache=case['cache'])


def catalog():
 # Shared Channel equals shared Product+Channel in this pinned eligible graph;
 # verify this equality in batch and do not count its duplicate as a discovery.
 routes=['product_channel','product','employee_channel','employee_product',
         'employee_union','employee_intersection','product_channel_plus_employee']
 programs=[{**build({}),'id':'route_000','graph_route':'product_channel'}]
 for route in routes:
  for path,recruitment,join,admission in itertools.product(
    ['parallel','groups','adjacency_then_group','group_then_adjacency'],
    ['joint','facets'],['union','intersection'],['equal_depth','area_first']):
   program=build(dict(path=path,recruitment=recruitment,join=join,admission=admission))
   if route=='product_channel' and program['factors']==programs[0]['factors']:continue
   programs.append({**program,'id':f'route_{len(programs):03d}','graph_route':route})
 return programs


def plan():
 p=base_plan();p['programs']=catalog()
 for file in [Path(__file__),L.ROOT/'tools/facet_structural_routes.py',SNAPSHOT]:
  p['input_sha256'][str(file.relative_to(L.ROOT))]=L.digest(file)
 p['coverage']='Seven distinct shared-entity projections crossed with four route orderings, two recruitment rules, two joins and two scope admissions. Query reducer, facet coefficients and path sponsor maximum remain fixed for this matched route comparison.'
 p['relation_semantics']='Symmetric chunk-to-shared-entity-to-chunk projections. Actual graph memberships, not nearest employee names or corpus content. Directed traversal not claimed.'
 p['historical_limit']='Later structural capture checks eligible/Product/Channel identities but does not prove historical Employee edges.'
 return p


def report(out,rows,planned):
 summaries=[]
 for p in planned['programs']:
  group=[r for r in rows if r['program_id']==p['id']]
  if len(group)!=len(planned['case_ids']):continue
  s={'program_id':p['id'],'factors':p['factors'],'graph_route':p['graph_route'],'cases':len(group),
    'total_gold_hits':sum(r['hits'] for r in group),'total_gold_count':sum(r['gold_count'] for r in group)}
  s['micro_recall_id']=s['total_gold_hits']/s['total_gold_count']
  for k in ['recall_id','precision_id','f1_id','recall_delta']:
   values=[r[k] for r in group if r[k] is not None];s[k]=float(np.mean(values)) if values else None
  for name,check in [('wins',lambda r:r['recall_delta']>0),('losses',lambda r:r['recall_delta']<0),('ties',lambda r:r['recall_delta']==0),
    ('delivery_changed',lambda r:r['delivery_changed']),('access_changed',lambda r:r['access_changed'])]:s[name]=sum(bool(check(r)) for r in group)
  summaries.append(s)
 summaries.sort(key=lambda s:(-s['total_gold_hits'],-s['recall_id']));L.atomic(out/'report.json',summaries)
 baseline={json.dumps(s['factors'],sort_keys=True):s for s in summaries if s['graph_route']=='product_channel'}
 matched=[]
 for s in summaries:
  b=baseline[json.dumps(s['factors'],sort_keys=True)]
  matched.append({'program_id':s['program_id'],'graph_route':s['graph_route'],'reference_program':b['program_id'],
    'gold_hits_delta':s['total_gold_hits']-b['total_gold_hits'],'macro_recall_delta':s['recall_id']-b['recall_id']})
 L.atomic(out/'matched-routes.json',matched)


def batch(out,limit=None):
 out.mkdir(parents=True,exist_ok=True);planned=plan()
 if (out/'plan.json').exists():
  if L.read(out/'plan.json')!=json.loads(json.dumps(planned)):raise ValueError('Sealed route plan differs')
 else:L.write_new(out/'plan.json',planned)
 lock=out/'writer.lock';L.write_new(lock,{'pid':os.getpid()});start=time.perf_counter()
 try:
  lab=RouteLab();graphs=lab.route_graphs
  if tuple(graphs['channel'].groups.values())!=tuple(graphs['product_channel'].groups.values()):
   raise ValueError('Channel relation is distinct; revise plan to include it')
  L.atomic(out/'graph-inventory.json',inventory(graphs));all_rows=[];new=0
  for cid in planned['case_ids']:
   target=out/'cases'/(cid+'.json')
   if target.exists():rows=L.read(target)
   else:
    if limit is not None and new>=limit:break
    case=lab.load(cid);reference=lab.execute(case,build({}));lab.parity(case,reference)
    rd,rm=lab.measured(case,reference);reforder=reference['order'].copy();rows=[];del reference
    for program in planned['programs']:
     result=lab.execute(case,program);delivered,metrics=lab.measured(case,result)
     rows.append({'case_id':cid,'program_id':program['id'],**metrics,
       'recall_delta':metrics['recall_id']-rm['recall_id'],'candidate_access':len(result['order']),
       'access_changed':set(result['order'])!=set(reforder),'delivery_changed':set(delivered['full'])!=set(rd['full']),
       'full_chunk_ids':delivered['full'],'budget':delivered['budget'],
       'order_sha256':hashlib.sha256(result['order'].tobytes()).hexdigest()})
    if rows[0]['order_sha256']!=hashlib.sha256(reforder.tobytes()).hexdigest():raise ValueError('Projection reference differs')
    target.parent.mkdir(parents=True,exist_ok=True);L.atomic(target,rows);new+=1
   all_rows.extend(rows);status={'completed_cases':len(all_rows)//len(planned['programs']),'programs':len(planned['programs']),
     'elapsed_seconds':round(time.perf_counter()-start,2),'status':'running'}
   L.atomic(out/'status.json',status);print(json.dumps(status),flush=True)
  report(out,all_rows,planned)
  if plan()!=planned:raise ValueError('Sealed input changed during route experiment')
  status.update(status='complete' if len(all_rows)==len(planned['case_ids'])*len(planned['programs']) else 'checkpoint',
    evaluations=len(all_rows),input_hashes_verified=True,reference_parity_verified=True)
  L.atomic(out/'status.json',status)
 finally:lock.unlink()


if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,default=OUT);ap.add_argument('--limit-cases',type=int)
 args=ap.parse_args();batch(args.out,args.limit_cases)

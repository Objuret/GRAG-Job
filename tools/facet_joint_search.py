"""Evaluation-selected higher-order construction search, with a gold-free core.

Require completed parent populations; never choose seeds from a favorable partial
checkpoint. Keep Pareto seeds within recruitment/scope families, then test every
valid one-component neighbour, including the shared-entity graph relation.
This is a declared local search, not proof of a global optimum.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time
import os
from collections import defaultdict
from facet_route_program_lab import RouteLab, L
from facet_program_catalog import FACTORS, DEFAULT, build
from facet_program_lab import plan as base_plan
from verify_facet_program_results import verify

ROUTES=('product_channel','product','employee_channel','employee_product',
        'employee_union','employee_intersection','product_channel_plus_employee')


def key(factors,route):
 return json.dumps([factors,route],sort_keys=True)


def choose_seeds(candidates):
 """Protect differing recruitment/scope mechanisms from a single global winner.

 Pareto axes are total gold source hits and macro per-case recall. Collapse
 tied, observationally identical full-order sequences within each family only;
 this is an explicit search pruning rule, not a claim of semantic equivalence.
 """
 families=defaultdict(list)
 for c in candidates:families[c['factors']['recruitment'],c['factors']['scope']].append(c)
 result=[]
 for family,rows in sorted(families.items()):
  seen=set()
  for c in sorted(rows,key=lambda x:(len(x['program']['nodes']),x['candidate_key'])):
   if any(d['hits']>=c['hits'] and d['recall']>=c['recall'] and
          (d['hits']>c['hits'] or d['recall']>c['recall']) for d in rows):continue
   alias=(c['hits'],c['recall'],c['order_signature'])
   if alias in seen:continue
   seen.add(alias);result.append(c)
 return result


def make_plan(parents):
 candidates={};parent_hashes={};case_ids=None
 for parent in parents:
  p=L.read(parent/'plan.json');status=L.read(parent/'status.json')
  if status['status']!='complete' or status['completed_cases']!=len(p['case_ids']):
   raise ValueError('Parent population not complete: '+str(parent))
  verified=verify(parent)
  if not verified['population_complete']:raise ValueError('Parent independent verification incomplete')
  if case_ids is None:case_ids=p['case_ids']
  elif case_ids!=p['case_ids']:raise ValueError('Parent case populations differ')
  rows={r['id']:[] for r in p['programs']}
  for cid in case_ids:
   file=parent/'cases'/(cid+'.json');parent_hashes[str(file.relative_to(L.ROOT))]=L.digest(file)
   for r in L.read(file):rows[r['program_id']].append(r)
  for program in p['programs']:
   route=program.get('graph_route','product_channel');f=program['factors'];ck=key(f,route)
   held=rows[program['id']]
   if len(held)!=len(case_ids):raise ValueError('Missing parent program cases')
   record={'candidate_key':ck,'factors':f,'graph_route':route,'program':program,
    'hits':sum(r['hits'] for r in held),'recall':sum(r['recall_id'] for r in held)/len(held),
    'order_signature':hashlib.sha256(''.join(r['order_sha256'] for r in held).encode()).hexdigest(),
    'source':str(parent.relative_to(L.ROOT)),'source_program':program['id']}
   if ck in candidates and any(candidates[ck][k]!=record[k] for k in ('hits','recall','order_signature')):
    raise ValueError('Identical construction differs across parent experiments')
   candidates[ck]=record
  parent_hashes[str((parent/'plan.json').relative_to(L.ROOT))]=L.digest(parent/'plan.json')
 seeds=choose_seeds(list(candidates.values()));new={}
 def add(f,route,reason):
  try:program=build(f)
  except ValueError:return
  ck=key(f,route)
  if ck not in new:new[ck]={**program,'graph_route':route,'selection_reasons':[]}
  new[ck]['selection_reasons'].append(reason)
 add(DEFAULT,'product_channel','reference')
 for seed in seeds:
  f=seed['factors'];route=seed['graph_route'];name=seed['source']+'/'+seed['source_program']
  add(f,route,'seed:'+name)
  for factor,values in FACTORS.items():
   for value in values:
    if value!=f[factor]:add({**f,factor:value},route,'neighbour:'+name+':'+factor)
  for alternative in ROUTES:
   if alternative!=route:add(f,alternative,'neighbour:'+name+':graph_route')
 programs=[]
 for i,p in enumerate(new.values()):programs.append({**p,'id':f'joint_{i:04d}'})
 plan=base_plan();plan.update(programs=programs,case_ids=case_ids,
  coverage='All valid single-component neighbours of Pareto seeds within recruitment/scope families, including alternative shared-entity projections. Higher-order search, not exhaustive factorial.',
  selection='Gold-informed development selection on completed parent populations. Runtime rules do not receive gold. No held-out generalization claim.',
  seed_pruning='Within a family, tied full-order signatures collapse to a deterministic representative; future semantic equivalence is not claimed.',
  seeds=[{k:v for k,v in s.items() if k!='program'} for s in seeds],
  parent_sha256=parent_hashes)
 for file in [Path(__file__),L.ROOT/'tools/facet_route_program_lab.py',L.ROOT/'tools/facet_structural_routes.py',
              L.ROOT/'tools/verify_facet_program_results.py']:
  plan['input_sha256'][str(file.relative_to(L.ROOT))]=L.digest(file)
 return plan


def batch(out):
 planned=L.read(out/'plan.json')
 for name,sha in {**planned['input_sha256'],**planned['parent_sha256']}.items():
  if L.digest(L.ROOT/name)!=sha:raise ValueError('Sealed dependency changed: '+name)
 lock=out/'writer.lock';L.write_new(lock,{'pid':os.getpid()});start=time.perf_counter()
 try:
  lab=RouteLab();totals=defaultdict(list)
  for ci,cid in enumerate(planned['case_ids'],1):
   path=out/'cases'/(cid+'.json')
   if path.exists():rows=L.read(path)
   else:
    case=lab.load(cid);reference=lab.execute(case,build({}));lab.parity(case,reference)
    rd,rm=lab.measured(case,reference);reforder=reference['order'].copy();rows=[];del reference
    # Group by relation to preserve graph-local caches; file order stays declared.
    held={}
    for p in sorted(planned['programs'],key=lambda p:p['graph_route']):
     r=lab.execute(case,p);d,m=lab.measured(case,r)
     held[p['id']]={'case_id':cid,'program_id':p['id'],**m,'recall_delta':m['recall_id']-rm['recall_id'],
      'candidate_access':len(r['order']),'access_changed':set(r['order'])!=set(reforder),
      'delivery_changed':set(d['full'])!=set(rd['full']),'full_chunk_ids':d['full'],'budget':d['budget'],
      'order_sha256':hashlib.sha256(r['order'].tobytes()).hexdigest()}
    rows=[held[p['id']] for p in planned['programs']];path.parent.mkdir(parents=True,exist_ok=True);L.atomic(path,rows)
   for r in rows:totals[r['program_id']].append(r)
   status={'status':'running','completed_cases':ci,'programs':len(planned['programs']),
           'elapsed_seconds':round(time.perf_counter()-start,2)}
   L.atomic(out/'status.json',status);print(json.dumps(status),flush=True)
  summaries=[]
  for p in planned['programs']:
   held=totals[p['id']];s={'program_id':p['id'],'factors':p['factors'],'graph_route':p['graph_route'],'cases':len(held),
    'total_gold_hits':sum(r['hits'] for r in held),'total_gold_count':sum(r['gold_count'] for r in held)}
   s['micro_recall_id']=s['total_gold_hits']/s['total_gold_count']
   for k in ('recall_id','precision_id','f1_id','recall_delta'):
    values=[r[k] for r in held if r[k] is not None];s[k]=sum(values)/len(values) if values else None
   for name,sign in [('wins',1),('losses',-1),('ties',0)]:
    s[name]=sum((r['recall_delta']>0 if sign==1 else r['recall_delta']<0 if sign==-1 else r['recall_delta']==0) for r in held)
   summaries.append(s)
  L.atomic(out/'report.json',sorted(summaries,key=lambda s:(-s['total_gold_hits'],-s['recall_id'])))
  for name,sha in {**planned['input_sha256'],**planned['parent_sha256']}.items():
   if L.digest(L.ROOT/name)!=sha:raise ValueError('Dependency changed during run')
  status.update(status='complete',evaluations=sum(map(len,totals.values())),input_hashes_verified=True)
  L.atomic(out/'status.json',status)
 finally:lock.unlink()


if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('command',choices=['plan','batch'])
 ap.add_argument('--parent',type=Path,action='append');ap.add_argument('--out',type=Path,required=True)
 args=ap.parse_args()
 if args.command=='plan':
  if not args.parent:ap.error('At least one completed parent required')
  planned=make_plan([p.resolve() for p in args.parent]);args.out.mkdir(parents=True,exist_ok=True)
  L.write_new(args.out/'plan.json',planned);print(json.dumps({'programs':len(planned['programs']),'seeds':len(planned['seeds'])}))
 else:batch(args.out)

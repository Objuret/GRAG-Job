"""Resume identical programs with a verified faster query-row duplicate check.

Keep the original engine, plans, checkpoints and case hashes intact. Imported
cases retain explicit provenance; new cases use the optimized numerical engine.
"""
from pathlib import Path
from dataclasses import replace
import argparse
import hashlib
import json
import os
import shutil
import time
import numpy as np
from facet_route_program_lab import RouteLab, L
from artefact.facet_construction_fast import run_program


class FastLab(RouteLab):
 def __init__(self):
  super().__init__()
  # Queries are already numerical. Neither parity nor delivery needs the raw
  # snapshot records, description/tag embeddings or name-landing index here.
  self.prepared=replace(self.prepared,chunks=tuple({'chunkId':c} for c in self.ids),
    tag_vectors=np.empty((0,0)),chunk_vectors=np.empty((0,0)),structural_index=None)
 def execute(self,case,program):
  graph=self.route_graphs[program['graph_route']] if 'graph_route' in program else self.graph
  return run_program(program,graph,case['matrices'],case['weights'],case['area'],
    self.components,self.id_order,cache=case['cache'])


def check_inputs(plan):
 for name,sha in plan['input_sha256'].items():
  if L.digest(L.ROOT/name)!=sha:raise ValueError('Input changed: '+name)


def verify_case(source,cid):
 planned=L.read(source/'plan.json');check_inputs(planned)
 held={r['program_id']:r for r in L.read(source/'cases'/(cid+'.json'))}
 lab=FastLab();case=lab.load(cid);start=time.perf_counter()
 for p in planned['programs']:
  r=lab.execute(case,p);d,m=lab.measured(case,r);old=held[p['id']]
  if hashlib.sha256(r['order'].tobytes()).hexdigest()!=old['order_sha256']:raise ValueError('Full order mismatch: '+p['id'])
  if d['full']!=old['full_chunk_ids'] or d['budget']!=old['budget']:raise ValueError('Delivery mismatch')
  if any(old[k]!=v for k,v in m.items()):raise ValueError('Metric mismatch')
 result={'case_id':cid,'programs':len(planned['programs']),'full_order_hashes_equal':True,
  'delivery_and_metrics_equal':True,'elapsed_seconds':round(time.perf_counter()-start,2),
  'source_plan_sha256':L.digest(source/'plan.json'),
  'engine_sha256':L.digest(L.ROOT/'test/artefact/facet_construction_fast.py')}
 L.atomic(source/('fast-parity-'+cid+'.json'),result);print(json.dumps(result),flush=True)


def batch(source,out):
 source=source.resolve();out=out.resolve()
 out.mkdir(parents=True,exist_ok=True)
 if source==out:raise ValueError('Preserve original run separately')
 original=L.read(source/'plan.json');check_inputs(original)
 if not (source/'fast-parity-case_001.json').exists():raise ValueError('Verify first source case before resuming')
 parity=L.read(source/'fast-parity-case_001.json')
 if parity['engine_sha256']!=L.digest(L.ROOT/'test/artefact/facet_construction_fast.py'):raise ValueError('Parity used different engine')
 if (out/'plan.json').exists():planned=L.read(out/'plan.json');check_inputs(planned)
 else:
  planned={**original,'resumed_from':str(source.relative_to(L.ROOT)),
   'original_plan_sha256':L.digest(source/'plan.json'),'imported_case_sha256':{},
   'engine_change':'Exact first-occurrence query-row duplicate detection; all retrieval arithmetic and program wiring retained.'}
  planned['input_sha256']=dict(original['input_sha256'])
  for file in [Path(__file__),L.ROOT/'test/artefact/facet_construction_fast.py',
               L.ROOT/'tools/facet_route_program_lab.py',L.ROOT/'tools/facet_structural_routes.py']:
   planned['input_sha256'][str(file.relative_to(L.ROOT))]=L.digest(file)
  for cid in planned['case_ids']:
   old=source/'cases'/(cid+'.json')
   if old.exists():planned['imported_case_sha256'][cid]=L.digest(old)
  L.write_new(out/'plan.json',planned)
 if L.digest(source/'plan.json')!=planned['original_plan_sha256']:raise ValueError('Source plan changed')
 lock=out/'writer.lock';L.write_new(lock,{'pid':os.getpid()});start=time.perf_counter()
 try:
  (out/'cases').mkdir(exist_ok=True)
  for cid,sha in planned['imported_case_sha256'].items():
   old=source/'cases'/(cid+'.json');dest=out/'cases'/old.name
   if L.digest(old)!=sha:raise ValueError('Imported case changed')
   if not dest.exists():shutil.copyfile(old,dest)
   if L.digest(dest)!=sha:raise ValueError('Imported copy mismatch')
  lab=FastLab();rows_by_program={p['id']:[] for p in planned['programs']}
  for ci,cid in enumerate(planned['case_ids'],1):
   target=out/'cases'/(cid+'.json')
   if target.exists():rows=L.read(target)
   else:
    case=lab.load(cid)
    from facet_program_catalog import build
    reference=lab.execute(case,build({}));lab.parity(case,reference)
    rd,rm=lab.measured(case,reference);order=reference['order'].copy();rows=[];del reference
    for p in planned['programs']:
     r=lab.execute(case,p);d,m=lab.measured(case,r)
     rows.append({'case_id':cid,'program_id':p['id'],**m,'recall_delta':m['recall_id']-rm['recall_id'],
      'candidate_access':len(r['order']),'access_changed':set(r['order'])!=set(order),
      'delivery_changed':set(d['full'])!=set(rd['full']),'full_chunk_ids':d['full'],'budget':d['budget'],
      'order_sha256':hashlib.sha256(r['order'].tobytes()).hexdigest(),
      'stage_access':{k:v.get('supported_chunks') for k,v in r['stages'].items() if v.get('supported_chunks') is not None}})
    L.atomic(target,rows)
   for row in rows:rows_by_program[row['program_id']].append(row)
   status={'completed_cases':ci,'programs':len(planned['programs']),'status':'running',
     'imported_cases':len(planned['imported_case_sha256']),'elapsed_seconds':round(time.perf_counter()-start,2)}
   L.atomic(out/'status.json',status)
   if cid not in planned['imported_case_sha256']:print(json.dumps(status),flush=True)
  rows=[r for held in rows_by_program.values() for r in held]
  if all('graph_route' in p for p in planned['programs']):
   from facet_route_program_lab import report
  else:
   from facet_program_lab import report
  report(out,rows,planned);check_inputs(planned)
  status.update(status='complete',evaluations=len(rows),input_hashes_verified=True,reference_parity_verified=True)
  L.atomic(out/'status.json',status)
 finally:lock.unlink()


if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('command',choices=['verify','batch'])
 ap.add_argument('--source',type=Path,required=True);ap.add_argument('--out',type=Path);ap.add_argument('--case',default='case_001')
 args=ap.parse_args()
 if args.command=='verify':verify_case(args.source,args.case)
 else:
  if args.out is None:ap.error('--out required for batch')
  batch(args.source,args.out)

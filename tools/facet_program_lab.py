"""Executable retrieval programs, matched construction experiments and live traces."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import time
import facet_retrieval_lab as L
import numpy as np
from artefact.facet_construction_program import run_program, Signal
from artefact.facet_operator_matrix import score_families
from artefact.facet_graph_input import GraphInput
from facet_program_catalog import build,catalog,FACTORS,DEFAULT

OUT=L.ROOT/'output/research/2026-09-23-construction-programs'


class ProgramLab(L.Lab):
 def __init__(self):
  super().__init__();self.manifest=L.read(L.INPUTS/'cases_manifest.json');self.loaded={}
  # Evaluation-side adapter. The retrieval core receives none of this object's
  # corpus-bearing records, resolver access, gold, or serialized delivery sizes.
  products={}
  for ci,chunk in enumerate(self.prepared.chunks):
   for product in chunk['scope'].get('product',[]):products.setdefault(product['node_id'],[]).append(ci)
  self.graph=GraphInput(tuple(self.ids),self.prepared.edge_tag,self.prepared.edge_chunk,
    self.prepared.reference.transform(self.prepared.edge_facets),self.prepared.groups,
    self.prepared.adjacency_pairs,tuple(products.values()))
 def load(self,cid):
  if cid not in self.loaded:
   rec=next(r for r in self.manifest['cases'] if r['case_id']==cid);meta=L.read(L.INPUTS/rec['meta'])
   if L.digest(L.INPUTS/rec['npz'])!=meta['npz_sha256']:raise ValueError('Numeric input hash mismatch')
   with np.load(L.INPUTS/rec['npz'],allow_pickle=False) as z:
    matrices={k:z[k].copy() for k in ['query_tag_cosines','query_chunk_cosines','query_description_cosines']};weights=z['query_facet_weights'].copy()
   area_ids=meta['area']['chunk_ids'];area=None if area_ids is None else np.array([c in set(area_ids) for c in self.ids])
   self.loaded={cid:{'meta':meta,'matrices':matrices,'weights':weights,'area':area,'cache':{}}}
  return self.loaded[cid]
 def execute(self,case,program):
  return run_program(program,self.graph,case['matrices'],case['weights'],case['area'],self.components,self.id_order,cache=case['cache'])
 def delivery(self,result):
  credit,full,budget=L.cut((self.ids[i] for i in result['order']),self.units)
  return {'credit':credit,'full':full,'budget':budget}
 def measured(self,case,result):
  delivered=self.delivery(result);metrics=self.evaluate(case,delivered)
  r,p=metrics['recall_id'],metrics['precision_id'];metrics['f1_id']=2*r*p/(r+p) if p is not None and r+p else 0.
  return delivered,metrics
 def parity(self,case,result):
  family=next(s for p,s in score_families(self.prepared,case['matrices'],case['weights']) if p==dict(match='product',topology='both',graph_join='union',facet='separate_facet_sum'))
  q=np.maximum(case['matrices']['query_description_cosines'],0)
  error=float(np.max(np.abs(family[0]*q-np.asarray(case['meta']['expected_scores']))))
  actual=result['states']['description_at_destination'].values.reshape(-1,self.n)[0]
  if error>1e-12 or np.max(np.abs(actual-family[0]*q))>1e-12:raise ValueError('Reference score parity failed')
  order=L.schedule(family,q,L.DEFAULT,case['area'],self.components,self.id_order)[0]
  if not np.array_equal(order,result['order']):raise ValueError('Reference order parity failed')
  return error
 def replay(self,payload):
  with self.lock:
   case=self.load(payload['case_id']);program=payload.get('program') or build(payload.get('factors',{}))
   if len(program.get('nodes',[]))>100:raise ValueError('Interactive programs are limited to 100 operations, not candidates')
   old=self.execute(case,build({}));self.parity(case,old);new=self.execute(case,program)
   olddelivery,oldmetrics=self.measured(case,old);delivery,metrics=self.measured(case,new)
   gold=set(self.gold['questions'][case['meta']['question_id']])
   linked=np.array([bool(gold & set(self.units[c]['artifact_ids'])) for c in self.ids])
   stages={}
   for name,stage in new['stages'].items():
    stage=dict(stage);state=new['states'][name]
    if isinstance(state,Signal) and state.domain in ('chunk','mask','regions'):
     a=state.values;support=np.any(a>0,axis=tuple(range(a.ndim-1)))
     stage['gold_linked_access']=int((support & linked).sum())
    elif not isinstance(state,Signal):stage['gold_linked_access']=int(((state.depth<=self.n)&linked).sum())
    stages[name]=stage
   oldpos={int(c):i+1 for i,c in enumerate(old['order'])};newpos={int(c):i+1 for i,c in enumerate(new['order'])}
   full=set(delivery['full']);oldfull=set(olddelivery['full'])
   stream_state=new['states'].get(program.get('streams_node',''))
   streams=stream_state.values.reshape(-1,self.n) if isinstance(stream_state,Signal) else None
   movements=[]
   for i,cid in enumerate(self.ids):
    movements.append({'chunk_id':cid,'gold_pointer_count':len(gold & set(self.units[cid]['artifact_ids'])),
      'old_position':oldpos.get(i),'new_position':newpos.get(i),'old_delivered':cid in oldfull,'new_delivered':cid in full,
      'nomination_depth':int(new['final'].original[i]),'recovered_depth':int(new['final'].depth[i]),
      'nominating_streams':new['final'].sponsors[i],
      'stream_values':None if streams is None else streams[:,i].tolist()})
   movements.sort(key=lambda r:r['new_position'] or self.n+1)
   return {'case_id':payload['case_id'],'program':program,'summary':metrics,'comparison_summary':oldmetrics,
     'stages':stages,'movements':movements,'budget':delivery['budget'],
     'gold_pointers':[{'source_id':aid,'chunk_ids':self.gold['artifacts'][aid],
       'credited':aid in delivery['credit'],'previously_credited':aid in olddelivery['credit']} for aid in sorted(gold)],
     'candidate_access':{'reference':len(old['order']),'new':len(new['order'])},
     'note':'Reference source-ID retrieval metrics, not new RAGAS judge results. Gold joined after delivery.'}


def plan():
 manifest=L.read(L.INPUTS/'cases_manifest.json')
 files={Path(__file__),L.ROOT/'tools/facet_program_catalog.py',L.ROOT/'test/artefact/facet_construction_program.py',
   L.ROOT/'test/artefact/facet_construction_routes.py',L.ROOT/'test/artefact/facet_graph_input.py',Path(L.__file__),L.ROOT/'test/artefact/facet_operator_matrix.py',
   L.ROOT/'tools/facet_gold90_stage_budget.py',L.INPUTS/'cases_manifest.json',
   L.POINTERS/'chunk_delivery_index.json',L.POINTERS/'gold_source_index.json',L.POINTERS/'verification.json'}
 files.update(L.ROOT/p for p in L.A.SMOKE_PROVENANCE_PATHS)
 for c in manifest['cases']:files.update([L.INPUTS/c['npz'],L.INPUTS/c['meta']])
 return {'schema_version':1,'case_ids':[c['case_id'] for c in manifest['cases']], 'programs':catalog(),
   'coverage':'All valid single and two-factor changes around the reference; six declared multi-factor compositions and the previous best construction comparator. Higher-order factorial not exhausted.',
   'factors':FACTORS,'original_failed_question_ids':manifest['failed_question_ids'],
   'input_sha256':{str(p.relative_to(L.ROOT)):L.digest(p) for p in sorted(files)},
   'serving_characters':72000,'cache_bytes':256*1024*1024,'language_model_calls':0,'database_writes':0,
   'metric':'Macro reference source-ID recall/precision/F1; no new answer generation or RAGAS judging.'}


def report(out,rows,planned):
 summaries=[]
 for program in planned['programs']:
  subset=[r for r in rows if r['program_id']==program['id']]
  if len(subset)!=len(planned['case_ids']):continue
  summary={'program_id':program['id'],'factors':program['factors'],'cases':len(subset)}
  summary['total_gold_hits']=sum(r['hits'] for r in subset)
  summary['total_gold_count']=sum(r['gold_count'] for r in subset)
  summary['micro_recall_id']=summary['total_gold_hits']/summary['total_gold_count']
  for key in ['recall_id','precision_id','f1_id','recall_delta']:
   vals=[r[key] for r in subset if r[key] is not None];summary[key]=float(np.mean(vals)) if vals else None
   summary[key+'_denominator']=len(vals)
  for name,test in [('wins',lambda r:r['recall_delta']>0),('losses',lambda r:r['recall_delta']<0),('ties',lambda r:r['recall_delta']==0),
     ('delivery_changed',lambda r:r['delivery_changed']),('access_changed',lambda r:r['access_changed'])]:
   summary[name]=sum(bool(test(r)) for r in subset)
  summaries.append(summary)
 summaries.sort(key=lambda r:-r['recall_id']);L.atomic(out/'report.json',summaries)
 # Matched local interaction: pair effect minus both single-factor effects.
 byf={tuple(s['factors'].items()):s for s in summaries};base=byf.get(tuple(DEFAULT.items()))
 interactions=[]
 if base:
  for row in summaries:
   changes=[k for k in DEFAULT if row['factors'][k]!=DEFAULT[k]]
   if len(changes)!=2:continue
   a,b=changes;sa=byf.get(tuple({**DEFAULT,a:row['factors'][a]}.items()));sb=byf.get(tuple({**DEFAULT,b:row['factors'][b]}.items()))
   if sa and sb:interactions.append({'program_id':row['program_id'],'factors':changes,
      'recall_interaction_pp':100*(row['recall_id']-sa['recall_id']-sb['recall_id']+base['recall_id'])})
 interactions.sort(key=lambda r:-abs(r['recall_interaction_pp']));L.atomic(out/'interactions.json',interactions)


def batch(out,limit=None):
 out.mkdir(parents=True,exist_ok=True);planned=plan()
 if (out/'plan.json').exists():
  if L.read(out/'plan.json')!=json.loads(json.dumps(planned)):raise ValueError('Sealed plan differs; use a new output directory')
 else:L.write_new(out/'plan.json',planned)
 lock=out/'writer.lock';L.write_new(lock,{'pid':os.getpid(),'started_utc':datetime.now(timezone.utc).isoformat()})
 started=time.perf_counter()
 try:
  lab=ProgramLab();all_rows=[];new_cases=0
  for cid in planned['case_ids']:
   target=out/'cases'/(cid+'.json')
   if target.exists():rows=L.read(target)
   else:
    if limit is not None and new_cases>=limit:break
    case=lab.load(cid);reference=lab.execute(case,build({}));lab.parity(case,reference)
    rd,rm=lab.measured(case,reference);rows=[];reforder=reference['order'].copy();del reference
    for program in planned['programs']:
     result=lab.execute(case,program);delivery,metrics=lab.measured(case,result)
     rows.append({'case_id':cid,'program_id':program['id'],**metrics,
       'recall_delta':metrics['recall_id']-rm['recall_id'],'candidate_access':len(result['order']),
       'access_changed':set(result['order'])!=set(reforder),
       'delivery_changed':set(delivery['full'])!=set(rd['full']),
       'full_chunk_ids':delivery['full'],'budget':delivery['budget'],
       'order_sha256':hashlib.sha256(result['order'].tobytes()).hexdigest(),
       'stage_access':{k:v.get('supported_chunks') for k,v in result['stages'].items() if v.get('supported_chunks') is not None}})
    target.parent.mkdir(parents=True,exist_ok=True);L.atomic(target,rows);new_cases+=1
   all_rows.extend(rows)
   status={'completed_cases':len(all_rows)//len(planned['programs']),'programs':len(planned['programs']),
       'elapsed_seconds':round(time.perf_counter()-started,2),'status':'running'}
   L.atomic(out/'status.json',status);print(json.dumps(status),flush=True)
  report(out,all_rows,planned)
  if plan()!=planned:raise ValueError('Inputs changed during execution')
  status.update(status='complete' if len(all_rows)==len(planned['case_ids'])*len(planned['programs']) else 'checkpoint',
       evaluations=len(all_rows),input_hashes_verified=True,reference_parity_verified=True)
  L.atomic(out/'status.json',status)
 finally:lock.unlink()


def serve(out,port):
 from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
 lab=ProgramLab()
 class Handler(BaseHTTPRequestHandler):
  def send(self,obj,code=200,kind='application/json'):
   body=obj.encode() if isinstance(obj,str) else json.dumps(obj,allow_nan=False).encode()
   self.send_response(code);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(body)
  def do_GET(self):
   if self.path=='/':return self.send((L.ROOT/'tools/facet_program_lab.html').read_text(encoding='utf-8'),kind='text/html; charset=utf-8')
   if self.path=='/api/status':return self.send({'cases':[c['case_id'] for c in lab.manifest['cases']],'factors':FACTORS,'default':DEFAULT,'programs':catalog(),'status':L.read(out/'status.json') if (out/'status.json').exists() else {}})
   if self.path=='/api/leaderboard':return self.send(L.read(out/'report.json') if (out/'report.json').exists() else [])
   return self.send({'error':'Not found'},404)
  def do_POST(self):
   try:
    count=int(self.headers.get('Content-Length','0'))
    if not 0<count<200000:raise ValueError('Invalid request size')
    payload=json.loads(self.rfile.read(count))
    if self.path=='/api/compile':return self.send(build(payload.get('factors',{})))
    if self.path!='/api/replay':raise ValueError('Unknown endpoint')
    self.send(lab.replay(payload))
   except (ValueError,KeyError,StopIteration,TypeError) as exc:self.send({'error':str(exc)},400)
  def log_message(self,*args):pass
 print(json.dumps({'url':f'http://127.0.0.1:{port}'}),flush=True);ThreadingHTTPServer(('127.0.0.1',port),Handler).serve_forever()


if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('command',choices=['batch','serve','trace'])
 ap.add_argument('--out',type=Path,default=OUT);ap.add_argument('--limit-cases',type=int);ap.add_argument('--port',type=int,default=8772)
 ap.add_argument('--case',default='case_001');ap.add_argument('--program',type=Path)
 args=ap.parse_args()
 if args.command=='batch':batch(args.out,args.limit_cases)
 elif args.command=='serve':serve(args.out,args.port)
 else:
  lab=ProgramLab();value=lab.replay({'case_id':args.case,'program':L.read(args.program) if args.program else build({})})
  L.write_new(args.out/(args.case+'-trace.json'),value);print(json.dumps(value['summary']))

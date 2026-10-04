"""One page for operation wiring and structural-entity route comparisons."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from facet_program_lab import L, OUT as PROGRAM_OUT, FACTORS, DEFAULT, catalog, build
from facet_route_program_lab import OUT as ROUTE_OUT, catalog as route_catalog
from facet_recovered_lab import RecoveredLab as RouteLab
from facet_structural_routes import inventory
from facet_live_compare import compare
from facet_scope_program_lab import ScopeOverride
from facet_recruitment_lab import execute_feedback
from artefact.facet_nomination_ties import reorder
from facet_live_frontier import execute as execute_tag_frontier, compiled as compiled_frontier
from facet_directed_lab import execute_directed
from facet_live_edge_trace import enrich as enrich_edge_trace
from facet_query_priority_lab import execute as execute_query_priority
from facet_query_priority_directed import execute as execute_query_priority_directed
from facet_live_record import execute as execute_record

EXTRA_EXPERIMENTS = {
 'combined_search': L.ROOT/'output/research/2026-09-23-joint-search-round1',
 'ordering_dependencies': L.ROOT/'output/research/2026-09-23-ordering-programs-v2',
 'scope_formation': L.ROOT/'output/research/2026-09-23-scope-programs',
 'traversal_depth': L.ROOT/'output/research/2026-09-24-depth-programs',
 'integrated_choices': L.ROOT/'output/research/2026-09-24-integrated-programs',
 'recruitment_before_traversal': L.ROOT/'output/research/2026-09-24-recruitment-programs',
 'matching_and_order': L.ROOT/'output/research/2026-09-24-matching-order-bridge',
 'nomination_ties': L.ROOT/'output/research/2026-09-24-tie-programs',
 'tag_frontier_evidence': L.ROOT/'output/research/2026-09-24-tag-frontier-programs',
 'tag_frontier_admission': L.ROOT/'output/research/2026-09-24-tag-frontier-followup',
 'directed_relationships': L.ROOT/'output/research/2026-09-24-directed-programs',
 'query_facet_priority': L.ROOT/'output/research/2026-09-24-query-priority',
 'directed_tag_integration': L.ROOT/'output/research/2026-09-24-directed-frontier-programs',
 'directed_query_priority': L.ROOT/'output/research/2026-09-24-query-priority-directed',
 'record_assembly': L.ROOT/'output/research/2026-09-24-record-assembly-programs',
 'record_product_context': L.ROOT/'output/research/2026-09-24-record-product-programs',
}


class FeedbackAwareLab(RouteLab):
 def execute(self,case,program):
  if program.get('record_assembly'):
   result=execute_record(self,case,program)
  elif program.get('query_priority'):
   executor=execute_query_priority_directed if any(n['op']=='directed_propagate' for n in program['nodes']) else execute_query_priority
   result=executor(self,case,program)
   result['priority_inspection']=result['stages'].pop('query_priority')
  elif program.get('tag_frontier') or program.get('tag_frontier_followup'):
   result=execute_tag_frontier(self,case,program)
  elif any(n['op']=='directed_propagate' for n in program['nodes']):
   result=execute_directed(self,case,program)
  elif any(n['op']=='nomination_evidence' for n in program['nodes']):
   result=execute_feedback(self,case,program)
  else:result=super().execute(case,program)
  self._last_result=reorder(result,program,self.id_order)
  return self._last_result

 def replay(self,payload):
  with self.lock:
   result=super().replay(payload)
   enrich_edge_trace(result,self._last_result['states'],self.graph.edge_chunk,self.ids)
   if any(result['program'].get(k) for k in ('tag_frontier','tag_frontier_followup','query_priority')):
    result['program']=compiled_frontier(result['program'])
   if 'priority_inspection' in self._last_result:
    result['inspection_nodes']=[{'id':'query_priority','op':'query_priority','inputs':[],'params':self._last_result['priority_inspection']}]
   if 'record_frontier_inspection' in self._last_result:
    summary=self._last_result['record_frontier_inspection']
    result['inspection_nodes']=[{'id':'record_frontier_inspection','op':summary['op'],'inputs':[],'params':summary}]
   if 'tag_arrival' in self._last_result:
    arrival=self._last_result['tag_arrival'];at={cid:i for i,cid in enumerate(self.ids)}
    for row in result['movements']:row['tag_arrival']=int(arrival[at[row['chunk_id']]])
    result['inspection_nodes']=[{'id':'tag_batch_admission','op':'tag_batch_admission','inputs':[result['program']['output']],'params':result['program']['tag_frontier_followup']}]
   return result


class LiveLab(ScopeOverride,FeedbackAwareLab):
 def execute(self,case,program):
  if 'scope_policy' in program and case['meta']['case_id'] in ('case_096','case_097','case_098','case_100'):
   raise ValueError('Structural scope captures currently cover the original 95 cases only')
  return super().execute(case,program)


def current_output(out):
 fast=out.with_name(out.name+'-fast')
 return fast if (fast/'status.json').exists() else out


def serve(port):
 lab=LiveLab()
 class Handler(BaseHTTPRequestHandler):
  def send(self,value,code=200,kind='application/json'):
   body=value.encode('utf-8') if isinstance(value,str) else json.dumps(value,allow_nan=False).encode('utf-8')
   self.send_response(code);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(body)))
   self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(body)
  def do_GET(self):
   if self.path=='/':return self.send((L.ROOT/'tools/facet_program_lab.html').read_text(encoding='utf-8'),kind='text/html; charset=utf-8')
   if self.path=='/api/experimental-programs':
    rows=[]
    for name in ('nomination_ties','tag_frontier_evidence','tag_frontier_admission','directed_relationships','query_facet_priority','directed_tag_integration','directed_query_priority','record_assembly','record_product_context'):
     path=EXTRA_EXPERIMENTS[name]/'plan.json'
     if path.exists():rows.extend({'experiment':name,'program':p} for p in L.read(path)['programs'])
    return self.send(rows)
   if self.path=='/api/status':
    status=lambda out:L.read(current_output(out)/'status.json') if (current_output(out)/'status.json').exists() else {}
    return self.send({'cases':[c['case_id'] for c in lab.manifest['cases']],'factors':FACTORS,'default':DEFAULT,
      'programs':catalog(),'graph_routes':inventory(lab.route_graphs),'status':status(PROGRAM_OUT),
      'route_status':status(ROUTE_OUT),'extra_status':{name:status(out) for name,out in EXTRA_EXPERIMENTS.items()},'comparison_case_count':lab.manifest['original_cases'],
      'recovered_cases':[c['case_id'] for c in lab.manifest['cases'] if c['cohort']=='recovered4']})
   if self.path=='/api/leaderboard':
    rows=[]
    for experiment,out in [('operation_wiring',PROGRAM_OUT),('entity_routes',ROUTE_OUT),*EXTRA_EXPERIMENTS.items()]:
     out=current_output(out)
     if (out/'report.json').exists():
      programs={p['id']:p for p in L.read(out/'plan.json')['programs']} if experiment in EXTRA_EXPERIMENTS else {}
      rows.extend({**r,'experiment':experiment,**({'program':programs[r['program_id']]} if programs else {})} for r in L.read(out/'report.json'))
    return self.send(rows)
   if self.path=='/api/interactions':
    rows=[]
    for experiment,out in [('operation_wiring',PROGRAM_OUT),('entity_routes',ROUTE_OUT),*EXTRA_EXPERIMENTS.items()]:
     out=current_output(out);file=out/'structural-findings.json'
     if not file.exists():continue
     findings=L.read(file)
     if not findings['population_complete'] or findings.get('smoke_only'):continue
     programs={p['id']:p for p in L.read(out/'plan.json')['programs']}
     shown=set()
     for interaction in findings['matched_four_corner_reversals']:
      pair=(interaction['factor'],interaction['modifier'])
      if pair in shown:continue
      if len(shown)>=6:break
      shown.add(pair)
      for key in ('first_context','second_context'):
       effect=interaction[key]
       rows.append({**effect,'experiment':experiment,'modifier':interaction['modifier'],
                    'modifier_value':effect['context'][interaction['modifier']],
                    'left_program':programs[effect['left']], 'right_program':programs[effect['right']]})
    return self.send(rows)
   return self.send({'error':'Not found'},404)
  def do_POST(self):
   try:
    size=int(self.headers.get('Content-Length','0'))
    if not 0<size<200000:raise ValueError('Invalid request size')
    payload=json.loads(self.rfile.read(size))
    if self.path=='/api/compile':return self.send(build(payload.get('factors',{})))
    if self.path!='/api/replay':raise ValueError('Unknown endpoint')
    route=payload.get('graph_route','product_channel')
    if route not in lab.route_graphs:raise ValueError('Unknown graph relation projection')
    program=dict(payload.get('program') or build(payload.get('factors',{})));program['graph_route']=route
    self.send(compare(lab,{**payload,'program':program}))
   except (ValueError,KeyError,TypeError,StopIteration) as exc:self.send({'error':str(exc)},400)
  def log_message(self,*args):pass
 print(json.dumps({'url':f'http://127.0.0.1:{port}'}),flush=True)
 ThreadingHTTPServer(('127.0.0.1',port),Handler).serve_forever()


if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--port',type=int,default=8773)
 serve(ap.parse_args().port)

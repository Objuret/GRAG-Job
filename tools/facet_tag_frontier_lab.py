"""Compare complete graph-tag frontiers with the selected chunk-first programs.

The retrieval core sees GraphInput and numeric query readings only. Source
delivery and gold evaluation occur afterward in the existing evaluation adapter.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path

from facet_program_lab import ProgramLab, L, plan as base_plan
from facet_program_catalog import build
from artefact.facet_tag_frontier import edge_gate, inject
from artefact.facet_tag_frontier_engine import run_program as run_tag_frontier
import facet_joint_search as runner

SELECTION=L.ROOT/'output/research/2026-09-24-structural-selection'
OUT=L.ROOT/'output/research/2026-09-24-tag-frontier-programs'


class TagFrontierLab(ProgramLab):
 def execute(self,case,program):
  policy=program.get('tag_frontier')
  if policy is None:return super().execute(case,program)
  gate,frontier=edge_gate(self.graph,case['matrices'],case['weights'],**policy)
  result=run_tag_frontier(inject(program),self.graph,case['matrices'],case['weights'],
       case['area'],self.components,self.id_order,cache=None,frontier_gate=gate)
  result['tag_frontier']={k:v for k,v in frontier.items() if not hasattr(v,'shape')}
  result['tag_frontier_arrays']={k:v for k,v in frontier.items() if hasattr(v,'shape')}
  result['stages']['tag_frontier']={'op':'tag_frontier','inputs':['query_tag_cosines','query_facet_weights'],
       **result['tag_frontier'],'policy':policy}
  return result


def programs():
 reference=build({});reference['id']='tag_frontier_reference';reference['graph_route']='product_channel'
 result=[reference]
 for name in ('best-total-hits','best-macro-recall'):
  p=deepcopy(L.read(SELECTION/(name+'.json'))['program'])
  p['id']='tag_frontier_'+name+'_control'
  p['graph_route']='product_channel'
  result.append(p)
  for evidence in ('query_only','outgoing_max'):
   for streams in ('joint','facets','queries'):
    for sponsors in ('first','all'):
     v=deepcopy(p)
     v['id']='tag_frontier_'+name+'_'+evidence+'_'+streams+'_'+sponsors
     v['tag_frontier']={'evidence':evidence,'streams':streams,'sponsors':sponsors}
     result.append(v)
 return result


def plan(smoke=False):
 p=base_plan();p['programs']=programs();p['smoke_only']=smoke
 if smoke:p['case_ids']=p['case_ids'][:1]
 p['coverage']='Two fixed parent rules; complete tag-score tiers crossed with query-only/outgoing-facet qualification, joint/facet/query streams, first/all positive sponsors. All positive tier evidence feeds edge-to-chunk reduction and downstream traversal. No arbitrary k or claim of exhaustive tag-frontier search.'
 p['parent_sha256']={str(f.relative_to(L.ROOT)):L.digest(f) for f in
     (SELECTION/'best-total-hits.json',SELECTION/'best-macro-recall.json',SELECTION/'selection-manifest.json')}
 for f in (Path(__file__),L.ROOT/'test/artefact/facet_tag_frontier.py',
           L.ROOT/'test/artefact/facet_tag_frontier_engine.py',L.ROOT/'tools/facet_joint_search.py'):
  p['input_sha256'][str(f.relative_to(L.ROOT))]=L.digest(f)
 return p


def trace(case_id,program_id):
 lab=TagFrontierLab();case=lab.load(case_id)
 program=next(p for p in programs() if p['id']==program_id)
 r=lab.execute(case,program);delivery,metrics=lab.measured(case,r)
 frontier=r.get('tag_frontier_arrays',{})
 return {'case_id':case_id,'program_id':program_id,'summary':metrics,
         'budget':delivery['budget'],'order':[lab.ids[i] for i in r['order']],
         'stages':r['stages'],'frontier':r.get('tag_frontier'),
         'tag_depths':frontier.get('tag_depths').tolist() if frontier else None,
         'edge_depths':frontier.get('edge_depths').tolist() if frontier else None,
         'tag_frontier_gate':r['states'].get('tag_frontier_gate').values.tolist() if frontier else None,
         'note':'Gold joined only after value-only retrieval and 72k delivery.'}


if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('command',choices=('plan','batch','trace'))
 ap.add_argument('--out',type=Path,default=OUT);ap.add_argument('--smoke',action='store_true')
 ap.add_argument('--case',default='case_001');ap.add_argument('--program-id')
 a=ap.parse_args()
 if a.command=='plan':
  p=plan(a.smoke);a.out.mkdir(parents=True,exist_ok=True);L.write_new(a.out/'plan.json',p)
  print(json.dumps({'programs':len(p['programs']),'cases':len(p['case_ids'])}))
 elif a.command=='batch':
  runner.RouteLab=TagFrontierLab;runner.batch(a.out)
 else:
  if not a.program_id:ap.error('--program-id required')
  print(json.dumps(trace(a.case,a.program_id)))

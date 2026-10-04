"""Matched tag-frontier controls and explicit complete-tier chunk admission."""
import argparse
from copy import deepcopy
import json
from pathlib import Path

from facet_program_lab import ProgramLab,L,plan as base_plan
from facet_program_catalog import build
from artefact.facet_tag_frontier import edge_gate,inject
from artefact.facet_tag_frontier_controls import gate_from_depths,tag_arrival,tier_priority_order
from artefact.facet_tag_frontier_fast import run_program as run_tag_frontier
import facet_joint_search as runner

SELECTION=L.ROOT/'output/research/2026-09-24-structural-selection'
OUT=L.ROOT/'output/research/2026-09-24-tag-frontier-followup'


class FollowupLab(ProgramLab):
 def execute(self,case,program):
  policy=program.get('tag_frontier_followup')
  if policy is None:return super().execute(case,program)
  cache=case.setdefault('tag_frontier_followup_cache',{})
  if policy['streams'] not in cache:
   _,cache[policy['streams']]=edge_gate(self.graph,case['matrices'],case['weights'],
                     evidence='query_only',streams=policy['streams'],sponsors='all')
  state=cache[policy['streams']]
  key=(program['tag_frontier_parent'],policy['streams'],policy['sponsors'],policy['weighting'])
  if key not in cache:
   gate=gate_from_depths(state['edge_depths'],self.graph.edge_chunk,self.n,
                         sponsors=policy['sponsors'],weighting=policy['weighting'])
   base=run_tag_frontier(inject(program),self.graph,case['matrices'],case['weights'],
                        case['area'],self.components,self.id_order,cache=None,frontier_gate=gate)
   cache[key]=(base,int((gate>0).any(axis=(0,1)).sum()))
  base,positive_edges=cache[key]
  r={**base,'stages':dict(base['stages'])}
  r['frontier_control']={'policy':policy,'positive_tags':state['positive_tags'],
                         'positive_edges':positive_edges}
  if policy['arrival']!='none':
   arrival_key=('arrival',policy['streams'],policy['arrival'])
   if arrival_key not in cache:
    groups=[g for collection in self.graph.groups.values() for g in collection]
    cache[arrival_key]=tag_arrival(state['tag_scores'],self.graph.edge_tag,self.graph.edge_chunk,
                                   self.n,groups,self.components,policy=policy['arrival'])
   arrival,tag_depth=cache[arrival_key]
   r['order']=tier_priority_order(r['order'],arrival,case['area'])
   r['frontier_control'].update(arrival_depth=arrival,tag_depth=tag_depth)
   r['stages']['tag_batch_admission']={'op':'tag_batch_admission','policy':policy['arrival'],
       'complete_tiers':int(tag_depth[tag_depth<=state['tag_scores'].shape[-1]].max(initial=0)),
       'reached_chunks':int((arrival<=state['tag_scores'].shape[-1]).sum())}
  return r


def programs():
 reference=build({});reference['id']='tag_frontier_followup_reference';reference['graph_route']='product_channel'
 result=[reference]
 for name in ('best-total-hits','best-macro-recall'):
  parent=deepcopy(L.read(SELECTION/(name+'.json'))['program'])
  parent['id']='tag_frontier_followup_'+name+'_control';parent['graph_route']='product_channel'
  result.append(parent)
  for streams in ('joint','facets','queries'):
   for sponsors in ('first','all'):
    for weighting in ('binary','reciprocal'):
     for arrival in ('none','own','inherit'):
      p=deepcopy(parent)
      p['id']='tag_frontier_followup_'+name+'_'+streams+'_'+sponsors+'_'+weighting+'_'+arrival
      p['tag_frontier_parent']=name
      p['tag_frontier_followup']={'streams':streams,'sponsors':sponsors,
                                   'weighting':weighting,'arrival':arrival}
      result.append(p)
 return result


def plan(smoke=False):
 p=base_plan();p['programs']=programs();p['smoke_only']=smoke
 if smoke:p['case_ids']=p['case_ids'][:1]
 p['coverage']='Query-only tag score; both selected parents cross joint/facet/query tag streams, first/all tag sponsors, binary/reciprocal tier weight, and gate-only/own/inherited complete-tier arrival. Area-first remains outer admission stratum; downstream parent order breaks same-tier ties. No candidate cap.'
 p['parent_sha256']={str(f.relative_to(L.ROOT)):L.digest(f) for f in
     (SELECTION/'best-total-hits.json',SELECTION/'best-macro-recall.json',SELECTION/'selection-manifest.json')}
 for f in (Path(__file__),L.ROOT/'test/artefact/facet_tag_frontier.py',
           L.ROOT/'test/artefact/facet_tag_frontier_controls.py',
           L.ROOT/'test/artefact/facet_tag_frontier_fast.py',L.ROOT/'tools/facet_joint_search.py'):
  p['input_sha256'][str(f.relative_to(L.ROOT))]=L.digest(f)
 return p


if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('command',choices=('plan','batch'))
 ap.add_argument('--out',type=Path,default=OUT);ap.add_argument('--smoke',action='store_true')
 a=ap.parse_args()
 if a.command=='plan':
  p=plan(a.smoke);a.out.mkdir(parents=True,exist_ok=True);L.write_new(a.out/'plan.json',p)
  print(json.dumps({'programs':len(p['programs']),'cases':len(p['case_ids'])}))
 else:
  runner.RouteLab=FollowupLab;runner.batch(a.out)

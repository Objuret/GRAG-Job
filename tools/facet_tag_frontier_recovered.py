"""Additive four-recovered-case replay of fixed tag-frontier leaders."""
import argparse
from copy import deepcopy
import json
from pathlib import Path

from facet_recovered_lab import RecoveredLab,L,combined_manifest
from facet_program_lab import plan as base_plan
from facet_program_catalog import build
from artefact.facet_tag_frontier import edge_gate,inject
from artefact.facet_tag_frontier_fast import run_program as run_tag_frontier
import facet_joint_search as runner

SOURCE=L.ROOT/'output/research/2026-09-24-tag-frontier-programs'
SELECTION=L.ROOT/'output/research/2026-09-24-structural-selection'
OUT=L.ROOT/'output/research/2026-09-24-tag-frontier-recovered4'
LEADERS=('tag_frontier_best-macro-recall_query_only_queries_all',
         'tag_frontier_best-macro-recall_query_only_queries_first')


class RecoveredTagLab(RecoveredLab):
 def execute(self,case,program):
  policy=program.get('tag_frontier')
  if policy is None:return super().execute(case,program)
  graph=self.route_graphs[program['graph_route']]
  gate,_=edge_gate(graph,case['matrices'],case['weights'],**policy)
  return run_tag_frontier(inject(program),graph,case['matrices'],case['weights'],
                          case['area'],self.components,self.id_order,cache=None,frontier_gate=gate)


def plan():
 source=L.read(SOURCE/'plan.json');available={p['id']:p for p in source['programs']}
 reference=build({});reference['id']='tag_recovered_reference';reference['graph_route']='product_channel'
 parent=deepcopy(L.read(SELECTION/'best-macro-recall.json')['program'])
 parent['id']='tag_recovered_parent';parent['graph_route']='product_channel'
 programs=[reference,parent]
 for name in LEADERS:programs.append(deepcopy(available[name]))
 manifest=combined_manifest();cases=[c for c in manifest['cases'] if c['cohort']=='recovered4']
 p=base_plan();p.update(programs=programs,case_ids=[c['case_id'] for c in cases],
  case_metadata={c['case_id']:c['meta'] for c in cases},
  coverage='Additive four recovered numeric captures, same fixed tag-frontier leaders selected on original95. Not random held-out validation or a per-case selector.')
 for c in cases:
  for key in ('npz','meta'):p['input_sha256'][c[key]]=L.digest(L.ROOT/c[key])
 for file in (Path(__file__),L.ROOT/'tools/facet_recovered_lab.py',
              L.ROOT/'tools/facet_fast_resume.py',L.ROOT/'tools/facet_joint_search.py',
              L.ROOT/'test/artefact/facet_tag_frontier.py',L.ROOT/'test/artefact/facet_tag_frontier_fast.py',
              SOURCE/'plan.json',SOURCE/'report.json',SOURCE/'independent-verification.json',
              SELECTION/'best-macro-recall.json'):
  p['input_sha256'][str(file.relative_to(L.ROOT))]=L.digest(file)
 return p


if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('command',choices=('plan','batch'))
 ap.add_argument('--out',type=Path,default=OUT);a=ap.parse_args()
 if a.command=='plan':
  p=plan();a.out.mkdir(parents=True,exist_ok=True);L.write_new(a.out/'plan.json',p)
  print(json.dumps({'programs':len(p['programs']),'cases':len(p['case_ids'])}))
 else:
  runner.RouteLab=RecoveredTagLab;runner.batch(a.out)

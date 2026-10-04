"""Check the isolated injected engine against unchanged selected programs."""
import argparse
import json
import numpy as np

from facet_program_lab import ProgramLab,L
from artefact.facet_tag_frontier import inject
from artefact.facet_tag_frontier_engine import run_program as injected

SELECTION=L.ROOT/'output/research/2026-09-24-structural-selection'


def check(limit=None):
 lab=ProgramLab();parents=[L.read(SELECTION/(n+'.json'))['program'] for n in
                           ('best-total-hits','best-macro-recall')]
 cases=lab.manifest['cases'] if limit is None else lab.manifest['cases'][:limit]
 checks=0
 for item in cases:
  case=lab.load(item['case_id']);gate=np.ones((5,len(case['weights']),len(lab.graph.edge_tag)))
  for parent in parents:
   old=lab.execute(case,parent)
   new=injected(inject(parent),lab.graph,case['matrices'],case['weights'],case['area'],
                lab.components,lab.id_order,cache=None,frontier_gate=gate)
   if not np.array_equal(old['order'],new['order']):raise AssertionError('Full order differs')
   for node in ('edge_evidence','description_at_destination'):
    actual=new['states']['tag_frontier_edge_evidence' if node=='edge_evidence' else node].values
    np.testing.assert_allclose(actual,old['states'][node].values,rtol=0,atol=1e-12)
   checks+=1
 return {'cases':len(cases),'parent_programs':len(parents),'full_order_and_numeric_checks':checks}


if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--limit-cases',type=int)
 print(json.dumps(check(ap.parse_args().limit_cases)))

"""Compare slow and fast isolated tag-frontier engines on full orders and stages."""
import argparse
import json
import numpy as np

from facet_program_lab import ProgramLab,L
from artefact.facet_tag_frontier import edge_gate,inject
from artefact.facet_tag_frontier_engine import run_program as slow
from artefact.facet_tag_frontier_fast import run_program as fast

SELECTION=L.ROOT/'output/research/2026-09-24-structural-selection'


def check(limit=1):
 lab=ProgramLab();parents=[L.read(SELECTION/(n+'.json'))['program'] for n in
                           ('best-total-hits','best-macro-recall')]
 cases=lab.manifest['cases'][:limit];count=0
 for item in cases:
  case=lab.load(item['case_id'])
  for parent in parents:
   for evidence in ('query_only','outgoing_max'):
    for streams in ('joint','facets','queries'):
     for sponsors in ('first','all'):
      gate,_=edge_gate(lab.graph,case['matrices'],case['weights'],
                       evidence=evidence,streams=streams,sponsors=sponsors)
      args=(inject(parent),lab.graph,case['matrices'],case['weights'],case['area'],
            lab.components,lab.id_order)
      a=slow(*args,cache=None,frontier_gate=gate)
      b=fast(*args,cache=None,frontier_gate=gate)
      np.testing.assert_array_equal(a['order'],b['order'])
      assert a['states'].keys()==b['states'].keys()
      for name in a['states']:
       left,right=a['states'][name],b['states'][name]
       if hasattr(left,'values'):
        assert left.domain==right.domain
        np.testing.assert_allclose(left.values,right.values,rtol=0,atol=1e-12)
       else:
        np.testing.assert_array_equal(left.depth,right.depth)
        np.testing.assert_array_equal(left.original,right.original)
        assert left.sponsors==right.sponsors
      count+=1
 return {'cases':len(cases),'full_order_and_numeric_checks':count}


if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--limit-cases',type=int,default=1)
 print(json.dumps(check(ap.parse_args().limit_cases)))

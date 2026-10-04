import numpy as np
from artefact.facet_construction_program import Signal,Nomination
from artefact.facet_nomination_ties import reorder,METHODS

def test_evidence_breaks_ties_without_crossing_depth_or_recovery():
    depths=np.array([1,1,1,2]);original=np.array([1,1,2,2])
    result={'order':np.arange(4),'final':Nomination(depths,original,[[0],[0,1],[0,1],[0,1]]),
        'states':{'streams':Signal(np.array([[[1.,3.,100.,1000.]],[[0.,2.,100.,1000.]]]),'chunk'),
                  'whole_description':Signal(np.array([[[1.,3.,100.,1000.]]]),'chunk')}}
    for method in METHODS:
        ranked=reorder(result,{'streams_node':'streams','tie_break':method},np.arange(4))
        assert ranked['order'].tolist()==([0,1,2,3] if method=='id' else [1,0,2,3])
        assert ranked['final'] is result['final']

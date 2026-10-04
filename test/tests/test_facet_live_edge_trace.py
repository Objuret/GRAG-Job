import numpy as np
from artefact.facet_construction_program import Signal
from facet_live_edge_trace import enrich

def test_edge_access_counts_unique_endpoints_and_joins_gold_afterward():
    signal=Signal(np.array([[[1.,2.,0.,3.]]]),'edge')
    reply={'stages':{'gate':{}},'movements':[
        {'chunk_id':'a','gold_pointer_count':5},
        {'chunk_id':'b','gold_pointer_count':2},
        {'chunk_id':'c','gold_pointer_count':0}]}
    enrich(reply,{'gate':signal},np.array([0,0,1,2]),('a','b','c'))
    assert reply['stages']['gate']=={'supported_chunks':2,'gold_linked_access':1}
    np.testing.assert_array_equal(signal.values,[[[1,2,0,3]]])

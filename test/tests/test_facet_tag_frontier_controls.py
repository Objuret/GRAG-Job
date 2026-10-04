import numpy as np

from artefact.facet_tag_frontier_controls import gate_from_depths,tag_arrival,tier_priority_order


def test_sponsorship_and_tier_weighting_are_separate_axes():
    depth=np.array([[[1,2,2]]])
    chunks=np.array([0,0,1])
    assert gate_from_depths(depth,chunks,2,sponsors='first',weighting='binary').tolist()==[[[1,0,1]]]
    assert gate_from_depths(depth,chunks,2,sponsors='first',weighting='reciprocal').tolist()==[[[1,0,.5]]]
    assert gate_from_depths(depth,chunks,2,sponsors='all',weighting='binary').tolist()==[[[1,1,1]]]
    assert gate_from_depths(depth,chunks,2,sponsors='all',weighting='reciprocal').tolist()==[[[1,.5,.5]]]


def test_complete_tag_batches_change_chunk_arrival_and_group_inheritance():
    scores=np.array([[[1.,.5,0.]],[[0.,0.,0.]]])
    et=np.array([0,1,2]);ec=np.array([0,1,2]);components=np.arange(3)
    own,tag_depth=tag_arrival(scores,et,ec,3,[(0,1)],components,policy='own')
    inherited,_=tag_arrival(scores,et,ec,3,[(0,1)],components,policy='inherit')
    assert own.tolist()==[1,2,5]
    assert inherited.tolist()==[1,1,5]
    assert tier_priority_order(np.array([1,0,2]),own).tolist()==[0,1,2]
    assert tier_priority_order(np.array([1,0,2]),own,np.array([False,True,True])).tolist()==[1,2,0]

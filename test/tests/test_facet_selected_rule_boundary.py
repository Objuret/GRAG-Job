import numpy as np
from artefact.facet_construction_program import Nomination
from facet_selected_rule_audit import boundary_tie

def test_all_effective_priorities_must_tie_at_serving_boundary():
    r={'order':np.array([0,1,2]),'final':Nomination(np.array([1,1,1]),np.array([1,1,1]),[[],[],[]])}
    assert boundary_tie(r,1)==(True,3)
    r['tag_arrival']=np.array([1,2,2])
    assert boundary_tie(r,1)==(False,0)
    assert boundary_tie(r,2)==(True,2)
    r['tie_evidence']=np.array([1.,2.,3.])
    assert boundary_tie(r,2)==(False,0)

def test_component_id_tie_is_visible_when_neighboring_depths_differ():
    r={'order':np.array([0,1,2]),
       'final':Nomination(np.array([1,1,1]),np.array([1,5,1]),[[],[],[]]),
       'assembly_components':np.array([0,0,2]),'assembly_id_order':np.array([0,1,2])}
    assert boundary_tie(r,1)==(True,3)

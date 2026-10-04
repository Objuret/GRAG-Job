import numpy as np

from artefact.facet_graph_input import GraphInput
from artefact.facet_tag_frontier import edge_gate, inject
from artefact.facet_construction_program import run_program as original
from artefact.facet_tag_frontier_engine import run_program as injected
from facet_program_catalog import build


def fixture():
    graph=GraphInput(('a','b','c'),np.array([0,1,0]),np.array([0,0,1]),
                     np.array([[1,1,1,1,1],[.5]*5,[1]*5]),{},(),())
    matrices={'query_tag_cosines':np.array([[.8,.4]]),
              'query_chunk_cosines':np.ones((1,3)),
              'query_description_cosines':np.ones(3)}
    weights=np.ones((1,5))
    return graph,matrices,weights


def test_first_tier_changes_edge_evidence_before_chunk_reduction():
    graph,matrices,weights=fixture()
    gate,state=edge_gate(graph,matrices,weights,evidence='query_only',streams='joint',sponsors='first')
    assert state['complete_tiers']==2
    assert gate.shape==(5,1,3)
    assert np.all(gate[:,:,0]==1)
    assert np.all(gate[:,:,1]==0)  # Later tag on chunk a loses sponsorship.
    assert np.all(gate[:,:,2]==1)


def test_all_sponsors_retains_complete_tiers_with_depth_discount():
    graph,matrices,weights=fixture()
    gate,state=edge_gate(graph,matrices,weights,evidence='query_only',streams='joint',sponsors='all')
    assert state['positive_edges']==3
    assert np.all(gate[:,:,0]==1)
    assert np.all(gate[:,:,1]==.5)


def test_outgoing_facet_readings_can_reverse_tag_frontier():
    graph,matrices,weights=fixture()
    graph=GraphInput(graph.chunk_ids,graph.edge_tag,graph.edge_chunk,
                     np.array([[.1]*5,[1.]*5,[.1]*5]),{},(),())
    gate,_=edge_gate(graph,matrices,weights,evidence='outgoing_max',streams='facets',sponsors='first')
    assert np.all(gate[:,:,0]==0)
    assert np.all(gate[:,:,1]==1)


def test_query_streams_can_recruit_different_tag_sponsors():
    graph,matrices,weights=fixture()
    matrices['query_tag_cosines']=np.array([[.8,.4],[.1,.9]])
    matrices['query_chunk_cosines']=np.ones((2,3))
    weights=np.ones((2,5))
    gate,_=edge_gate(graph,matrices,weights,evidence='query_only',streams='queries',sponsors='first')
    assert gate[0,0,:2].tolist()==[1,0]
    assert gate[0,1,:2].tolist()==[0,1]


def test_unit_gate_reproduces_original_full_order_and_scores():
    graph,matrices,weights=fixture();p=build({})
    args=(graph,matrices,weights,None,np.arange(3),np.arange(3))
    old=original(p,*args)
    new=injected(inject(p),*args,frontier_gate=np.ones((5,1,3)))
    np.testing.assert_array_equal(old['order'],new['order'])
    np.testing.assert_allclose(old['states']['edge_evidence'].values,
                               new['states']['tag_frontier_edge_evidence'].values)

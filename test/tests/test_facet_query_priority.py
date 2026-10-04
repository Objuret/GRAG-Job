import numpy as np
from artefact.facet_query_priority import priority_depths,edge_gate
from artefact.facet_tag_frontier import edge_gate as scalar
from artefact.facet_graph_input import GraphInput

def test_distinct_priority_permutation_invariance():
    v=np.array([[[.3,.6,.3]],[[.8,.1,.8]],[[1,0,1]],[[.1,.3,.1]],[[.2,.4,.2]]])
    u=np.array([[.3,.9,.1,.5,.7]])
    expected,_=priority_depths(v,u)
    perm=[3,1,4,0,2]
    actual,_=priority_depths(v[perm],u[:,perm])
    np.testing.assert_array_equal(actual,expected)
    assert expected[0,0,0]==expected[0,0,2]<expected[0,0,1]

def test_zero_facets_cannot_admit_or_break_ties():
    v=np.zeros((5,1,3));v[0,0]=[.5,.5,0];v[1,0]=[0,99,999]
    depth,order=priority_depths(v,np.array([[1,0,0,0,0]]))
    assert depth.tolist()==[[[1,1,0]]];assert order==[[0]]
    assert not priority_depths(v,np.zeros((1,5)))[0].any()

def test_tied_query_priority_has_explicit_canonical_order():
    v=np.zeros((5,1,2));v[0,0]=[1,.5];v[1,0]=[0,1]
    d,o=priority_depths(v,np.array([[1,1,0,0,0]]))
    assert o==[[0,1]];assert d.tolist()==[[[1,2]]]

def test_scalar_control_is_exact_and_lex_changes_sponsor():
    g=GraphInput(('a','b'),[0,1,2],[0,0,1],[[.9,.1,0,0,0],[.2,1,0,0,0],[.9,.1,0,0,0]],{},(),())
    m={'query_tag_cosines':np.ones((1,3))};u=np.array([[.2,1,0,0,0]])
    for sponsor in ('first','all'):
        a,_=edge_gate(g,m,u,method='scalar',sponsors=sponsor)
        b,_=scalar(g,m,u,evidence='outgoing_max',streams='queries',sponsors=sponsor)
        np.testing.assert_array_equal(a,b)
    gate,state=edge_gate(g,m,u,sponsors='first')
    assert gate[0,0].tolist()==[0,1,1]
    assert state['tag_depths'].tolist()==[[[2,1,2]]]

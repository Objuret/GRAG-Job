import numpy as np
import pytest
from facet_construction_lab import combine_queries, numeric_support, contexts
from artefact.facet_joint_candidate import freeze_reference
from artefact.facet_operator_matrix import score_families
from types import SimpleNamespace


def fixture():
    p=SimpleNamespace(chunks=[{}, {}, {}],edge_tag=np.array([0,1,0,1]),
        edge_chunk=np.array([0,0,1,2]),edge_facets=np.array([[.2]*5,[.4]*5,[.7]*5,[.9]*5]),
        groups={'group':[(0,1,2)]},adjacency_pairs=[(0,1),(1,2)])
    p.reference=freeze_reference(p.edge_facets)
    m={'query_tag_cosines':np.array([[.9,.1],[.1,.9]]),
       'query_chunk_cosines':np.array([[.8,.7,0],[.4,.5,.9]]),
       'query_description_cosines':np.ones(3)}
    return p,m,np.ones((2,5))


def test_maximum_matches_reference_both_contexts():
    p,m,u=fixture()
    ref={tuple(k[f] for f in ('match','topology','graph_join','facet')):v for k,v in score_families(p,m,u)}
    for route in [('product','both','union'),('maximum','groups','intersection')]:
        combined,unique,_=numeric_support(p,m,u,*route)
        assert np.array_equal(combine_queries(combined,'maximum',unique),ref[route+('separate_facet_sum',)])


def test_joint_support_can_reverse_order_and_minimum_can_remove_access():
    # Strong isolated support vs moderate support from both queries.
    a=np.zeros((5,2,3));a[0]=[[1,.7,.8],[.1,.7,0]]
    assert combine_queries(a,'maximum',[0,1])[0].argmax()==0
    assert combine_queries(a,'mean',[0,1])[0].argmax()==1
    assert combine_queries(a,'minimum',[0,1])[0,2]==0


def test_exact_duplicate_query_does_not_change_any_reducer():
    p,m,u=fixture()
    original,unique,_=numeric_support(p,m,u,'product','both','union')
    copied={k:np.concatenate([v,v[:1]]) if k!='query_description_cosines' else v for k,v in m.items()}
    changed,distinct,_=numeric_support(p,copied,np.concatenate([u,u[:1]]),'product','both','union')
    assert len(distinct)==2
    for mode in ('maximum','mean','minimum'):
        assert np.array_equal(combine_queries(original,mode,unique),combine_queries(changed,mode,distinct))


def test_query_permutation_and_single_query_controls():
    a=np.arange(30,dtype=float).reshape(5,2,3)
    for mode in ('maximum','mean','minimum'):
        assert np.array_equal(combine_queries(a,mode,[0,1]),combine_queries(a[:,::-1],mode,[0,1]))
        assert np.array_equal(combine_queries(a[:,:1],mode,[0]),combine_queries(a[:,:1],'maximum',[0]))
    with pytest.raises(ValueError):combine_queries(a,'mystery',[0,1])
    assert len(list(contexts()))==12

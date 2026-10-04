import numpy as np
from artefact.facet_graph_input import GraphInput
from facet_structural_routes import projections


def test_employee_paths_project_their_distinct_membership_intersection_and_union():
    graph=GraphInput(tuple('abcd'),np.array([0]),np.array([0]),np.ones((1,5)),{},(),())
    row={'label':'Employee','routes':{'employee_channel':['a','b'],'employee_product':['b','c']}}
    payload={'eligible_chunk_ids':list('abcd'),'nodes':[row,row,{'label':'Employee',
        'routes':{'employee_channel':['a','b','c'],'employee_product':['a','b']}}]}
    variants=projections(graph,payload)
    group=lambda name:next(iter(variants[name].groups.values()))
    assert group('employee_channel')==((0,1),(0,1,2))
    assert group('employee_product')==((0,1),(1,2))
    assert group('employee_union')==((0,1,2),)
    assert group('employee_intersection')==((0,1),)
    assert not hasattr(variants['employee_union'],'chunks')

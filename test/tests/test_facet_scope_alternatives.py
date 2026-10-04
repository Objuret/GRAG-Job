import pytest
from artefact.facet_scope_alternatives import form_scope, scope_catalog


def landing(label, routes):
    return {'node_bindings': [{'label': label, 'node_id': label, 'routes': routes}]}


def test_default_and_route_intersection_are_different_graph_constructions():
    inputs = [landing('Employee', {'employee_channel': ['a','b'], 'employee_product': ['b','c']}),
              landing('Product', {'product_chunk': ['a','c']})]
    assert form_scope(inputs, 'abcd')[0] == {'a','c'}
    assert form_scope(inputs, 'abcd', {'route_join':'intersection','empty':'veto'})[0] == set()
    assert form_scope(inputs, 'abcd', {'name_join':'union'})[0] == {'a','b','c'}


def test_alias_binding_join_does_not_silently_choose_one_person():
    a = landing('Employee', {'employee_channel':['a','b']})
    a['node_bindings'] += landing('Employee2', {'employee_channel':['b','c']})['node_bindings']
    assert form_scope([a], 'abcd')[0] == {'a','b','c'}
    assert form_scope([a], 'abcd', {'binding_join':'intersection'})[0] == {'b'}


def test_unrouted_and_no_landing_are_not_conflated_with_negative_evidence():
    inputs = [landing('Company', {}), landing('Product', {'product_chunk':['a']})]
    assert form_scope(inputs, 'ab')[0] is None
    assert form_scope(inputs, 'ab', {'empty':'veto'})[0] == set()
    assert form_scope(inputs, 'ab', {'unrouted':'abstain'})[0] == {'a'}
    assert form_scope([], 'ab', {'empty':'veto'})[0] is None


def test_route_filter_and_invalid_endpoints():
    inputs = [landing('Employee', {'employee_channel':['a'], 'employee_product':['b']})]
    assert form_scope(inputs, 'ab', {'route_filter':'channel'})[0] == {'a'}
    assert form_scope(inputs, 'ab', {'route_filter':'product'})[0] == {'b'}
    with pytest.raises(ValueError): form_scope(inputs, 'a')
    assert len(scope_catalog()) == 96

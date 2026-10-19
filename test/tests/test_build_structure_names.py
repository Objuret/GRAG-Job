"""How `build_structure_names` reads a node's name through its pointer and makes its match keys."""
from graph.build_structure_names import _pointer, keys_of


def test_a_pointer_leads_into_dicts_and_lists():
    doc = {'eid_1': {'name': 'Ian Garcia'}, 'slack': [{'Channel': {'name': 'planning-viz'}}]}
    assert _pointer(doc, '/eid_1')['name'] == 'Ian Garcia'
    assert _pointer(doc, '/slack/0/Channel')['name'] == 'planning-viz'
    assert _pointer([{'name': 'Noah Clark'}], '/0')['name'] == 'Noah Clark'
    assert _pointer(doc, '') is doc


def test_the_keys_are_the_name_and_the_id_in_plain_form():
    assert keys_of('VizForce') == [' vizforce ']
    assert keys_of('planning-VizForce') == [' planning vizforce ']
    assert keys_of('Ian Garcia', 'eid_31cb6db5') == [' ian garcia ', ' eid 31cb6db5 ']
    assert keys_of('Noah Clark', 'CUST-0019') == [' noah clark ', ' cust 0019 ']

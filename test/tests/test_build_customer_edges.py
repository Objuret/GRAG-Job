"""Which customer ids `build_customer_edges` reads out of a record."""
from graph.build_customer_edges import customers_in, id_pattern

PATTERN = id_pattern(['CUST-0019', 'CUST-0001'])


def test_a_message_naming_a_customer_by_id_carries_it():
    record = {'Message': {'User': {'text': 'This impacts customer CUST-0019. @eid_1, can you look?'}}}
    assert customers_in(record, PATTERN) == {'CUST-0019'}


def test_only_whole_ids_count():
    record = {'text': 'CUST-00190 and XCUST-0001 and CUST-001 are no ids; (CUST-0001) is'}
    assert customers_in(record, PATTERN) == {'CUST-0001'}


def test_a_record_without_an_id_carries_no_customer():
    assert customers_in({'text': 'Noah Clark joined the call'}, PATTERN) == set()

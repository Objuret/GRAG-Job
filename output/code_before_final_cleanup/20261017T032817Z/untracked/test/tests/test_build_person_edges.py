"""The person fields `build_person_edges` reads a record's people from, per kind of chunk."""
from graph.build_person_edges import people_of


def test_slack_message_names_its_poster():
    record = {'Message': {'User': {'userId': 'eid_00000001', 'text': 'thanks @eid_00000002'}}}
    assert people_of('slack_thread_batch', record) == [('userId', 'eid_00000001')]


def test_pull_request_names_its_author_and_reviewers():
    record = {'user': {'login': 'eid_00000001'},
              'reviews': [{'user': {'login': 'eid_00000002'}}, {'user': {'login': 'EMP_123'}}]}
    assert people_of('pr_batch', record) == [('user.login', 'eid_00000001'),
                                             ('reviews.user.login', 'eid_00000002'),
                                             ('reviews.user.login', 'EMP_123')]


def test_pull_request_without_reviews():
    assert people_of('pr_batch', {'user': {'login': 'EMP_9'}, 'reviews': None}) == [('user.login', 'EMP_9')]


def test_document_names_its_author():
    assert people_of('document_part', {'author': 'eid_00000003'}) == [('author', 'eid_00000003')]


def test_transcript_names_its_participants():
    record = {'participants': ['eid_00000001', 'eid_00000002']}
    assert people_of('meeting_transcript', record) == [('participants', 'eid_00000001'),
                                                       ('participants', 'eid_00000002')]


def test_kinds_without_person_fields_name_nobody():
    assert people_of('url_batch', {'link': 'x'}) == []
    assert people_of('meeting_chat_batch', {'text': 'Charlie Davis: hi'}) == []

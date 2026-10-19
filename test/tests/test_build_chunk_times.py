from graph import build_chunk_times as T


def test_a_records_time_is_read_from_the_field_its_kind_keeps_it_in():
    day = 86400.
    assert T.time_of('slack_thread_batch', {'Message': {'User': {'timestamp': '1970-01-02T00:00:00'}}}) == day
    assert T.time_of('pr_batch', {'created_at': '1970-01-03T00:00:00', 'reviews': []}) == 2 * day
    assert T.time_of('document', {'date': '1970-01-02'}) == day
    assert T.time_of('meeting_transcript_part', {'date': '1970-01-02T01:00:00'}) == day + 3600.
    assert T.time_of('meeting_chat_batch', {'text': '1970-01-02T00:00:30\nAlice: see https://x'}) == day + 30.
    # a url list keeps no time; a field that holds none gives none
    assert T.time_of('url_batch', {'link': 'https://x', 'description': 'd', 'id': 'u'}) is None
    assert T.time_of('document', {'date': 'soon'}) is None and T.time_of('pr_batch', {}) is None
    # the time is read as it stands, on one clock
    assert T.seconds('1970-01-02T00:00:00Z') == day


def test_a_chunks_times_are_its_records_own_times_sorted(monkeypatch):
    docs = {'a.json': {'slack': [{'Message': {'User': {'timestamp': '1970-01-03T00:00:00'}}},
                                 {'Message': {'User': {'timestamp': '1970-01-01T00:01:00'}}},
                                 {'Message': {'User': {}}}],
                       'urls': [{'link': 'https://x'}]}}

    class Session:
        def run(self, cypher):
            class Rows:
                def data(self):
                    return [{'chunk': 's1', 'kind': 'slack_thread_batch', 'relpath': 'a.json',
                             'sha256': 'h', 'locator': '{"section": "slack", "indices": [0, 1, 2]}'},
                            {'chunk': 'u1', 'kind': 'url_batch', 'relpath': 'a.json', 'sha256': 'h',
                             'locator': '{"section": "urls", "index": 0}'}]
            return Rows()

    monkeypatch.setattr(T, '_load_verified_doc', lambda relpath, sha, cache: docs[relpath])
    found, counts = T.record_times(Session())
    # each record at its own time, no span made of them; a record or a chunk with no time adds none
    assert found == {'s1': [60., 2 * 86400.]}
    assert counts[('slack_thread_batch', 'record times')] == 2
    assert counts[('url_batch', 'chunks')] == 1 and counts[('url_batch', 'with a time')] == 0

import copy
import numpy as np
import pytest

from artefact import query_content as Q
from artefact import learned_relations as L


def payload():
    return {'description': 'Content describing a process and its timing.',
            'tags': [{'t': 'process timing', 'facets': dict(zip(Q.FACETS, [0, 1, .5, 1, 0]))}]}


def test_original_question_survives_and_topic_does_not_lead_by_default():
    question = 'What changed, and when?'
    _, user = Q.request(question)
    content = Q.parse(question, payload())
    assert user == 'Question: ' + question
    assert content.question == question
    assert content.tags[0].facet_priority() == (('temporal', 'activity'), ('why',), ('topic', 'concreteness'))


@pytest.mark.parametrize('bad', [float('nan'), float('inf'), True, -1, 2])
def test_no_silent_repair_of_invalid_readings(bad):
    raw = payload()
    raw['tags'][0]['facets']['why'] = bad
    with pytest.raises(ValueError):
        Q.parse('Question', raw)


def test_rejects_silent_scope_invention_and_tag_dropping():
    raw = payload()
    raw['scope'] = 'invented'
    with pytest.raises(ValueError):
        Q.parse('Question', raw)
    raw = payload()
    raw['tags'].append(copy.deepcopy(raw['tags'][0]))
    with pytest.raises(ValueError):
        Q.parse('Question', raw)


def test_zero_topic_and_negative_measurements_do_not_erase_paths():
    # Synthetic API check only; these values never enter graph/evaluation data.
    query = Q.parse('Question', payload())
    raw = np.array([[0, -2, 3, 4, 5], [7, 8, 9, 10, 11]], dtype=float)
    learned = L.LearnedEdges((('tag a', 'chunk'), ('tag b', 'chunk')), raw, 'test', 'test')
    packet = L.connect(query, learned, query_tag_cosines=[[-.1, .9]],
                       query_chunk_cosines=[[.7]], description_chunk_cosines=[.8],
                       graph_tag_names=['tag a', 'tag b'], chunk_ids=['chunk'], topic_cosines=[0, .2])
    assert packet['edge_indices'] == ((0, 0, 0), (1, 1, 0))
    assert packet['omitted_endpoints'] == 0
    np.testing.assert_array_equal(packet['learned'].raw_scores, raw)
    assert packet['tag_match'][0, 0] == -.1
    assert packet['topic_cosine'][0] == 0
    with pytest.raises(ValueError):
        packet['topic_cosine'].setflags(write=True)


def test_real_learned_layer_preserved():
    from pathlib import Path
    layer = L.load(Path(__file__).resolve().parents[2] / 'output/facet_pairs/rounds/round1')
    assert layer.raw_scores.shape == (61018, 5)
    assert layer.overlay_sha256 == '352065af504b11020bb06103d320163362538dc1b034c2df377af0e3dd5bb0ec'
    with pytest.raises(ValueError):
        layer.raw_scores.setflags(write=True)


def test_query_tags_parse_beside_the_description_tags():
    raw = payload()
    raw['query_tags'] = [{'t': 'release timing', 'facets': dict(zip(Q.FACETS, [1, .5, 0, 0, .25]))},
                         {'t': 'process timing', 'facets': dict(zip(Q.FACETS, [.5, .5, .5, .5, .5]))}]
    content = Q.parse('Question', raw)
    assert [t.text for t in content.tags] == ['process timing']
    assert [t.text for t in content.query_tags] == ['release timing', 'process timing']
    assert content.query_tags[0].readings == (1, .5, 0, 0, .25)
    assert '"query_tags"' in Q.SYSTEM


def test_answers_without_query_tags_still_parse():
    content = Q.parse('Question', payload())
    assert content.query_tags == ()
    assert [t.text for t in content.tags] == ['process timing']


@pytest.mark.parametrize('bad', [[], 'tag', [{'t': 'x'}],
                                 [{'t': 'a', 'facets': dict(zip(Q.FACETS, [0] * 5))},
                                  {'t': 'A', 'facets': dict(zip(Q.FACETS, [0] * 5))}],
                                 [{'t': 'a', 'facets': dict(zip(Q.FACETS, [0, 0, 0, 0, 2]))}]])
def test_query_tags_parse_as_strictly_as_the_tags(bad):
    raw = payload()
    raw['query_tags'] = bad
    with pytest.raises(ValueError):
        Q.parse('Question', raw)


def test_duplicate_collapse_covers_both_lists():
    from arms import artefact_v4 as V
    row = {'t': 'a', 'facets': dict(zip(Q.FACETS, [0] * 5))}
    raw = {'description': 'd', 'tags': [row, dict(row)], 'query_tags': [row, dict(row, t='A ')]}
    cleaned, dropped = V._collapse_duplicate_tags(raw)
    assert dropped == 2
    assert len(cleaned['tags']) == 1 and len(cleaned['query_tags']) == 1
    cleaned, dropped = V._collapse_duplicate_tags(payload())
    assert dropped == 0 and 'query_tags' not in cleaned

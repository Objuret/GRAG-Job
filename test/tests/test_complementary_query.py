import numpy as np
import pytest
from artefact import complementary_query as C
from artefact import learned_relations as L


def row(value):
    return {'tags': [{'t': 'shared phrase', 'facets': dict(zip(C.Q.FACETS, value))}]}


def build():
    calls = []
    answers = iter([row([0, 1, 0, 1, 0]), {'description': 'Sought content'}, row([1, 0, 1, 0, 1])])
    def call(stage, system, user, validate):
        calls.append((stage, system, user))
        return validate(next(answers))
    return C.interpret('Original question?', call), calls


def test_identical_analysis_and_independent_inputs():
    query, calls = build()
    assert calls[0][:2] == calls[2][:2]
    assert calls[0][2] == 'Text: Original question?'
    assert calls[2][2] == 'Text: Sought content'
    assert [b.origin for b in query.branches] == ['original', 'interpreted']
    # Same tag in both representations is not deduplicated across branches.
    assert query.branches[0].content.tags[0].readings != query.branches[1].content.tags[0].readings


def test_both_full_texts_and_tag_sets_reach_same_graph_procedure():
    query, _ = build()
    learned = L.LearnedEdges((('graph tag', 'chunk'),), np.zeros((1, 5)), 'test', 'test')
    matched = []
    def match(text, tags):
        matched.append((text, tags))
        value = 0.2 if text == query.question else 0.8
        return {'query_tag_cosines': [[value]], 'query_chunk_cosines': [[value]],
                'query_description_cosines': [value]}
    packets = C.connect_both(query, learned, match, graph_tag_names=['graph tag'],
                             chunk_ids=['chunk'], topic_cosines=[0])
    assert matched == [('Original question?', ['shared phrase']), ('Sought content', ['shared phrase'])]
    assert packets['original']['description_match'][0] == .2
    assert packets['interpreted']['description_match'][0] == .8
    assert packets['original']['edge_indices'] == packets['interpreted']['edge_indices']
    assert packets['original']['learned'] is packets['interpreted']['learned']


def test_description_failure_does_not_silently_become_single_branch():
    def call(stage, system, user, validate):
        return validate({'description': ''} if stage == 'describe_question' else row([1]*5))
    with pytest.raises(ValueError):
        C.interpret('Question', call)

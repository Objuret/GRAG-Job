"""Live weighting must preserve cached ranking and independent pinned weights."""
import numpy as np
import pytest
from facet_weighted_lab import WeightedLab, coefficients, DEFAULT_COEFFICIENTS
import facet_retrieval_lab as L


@pytest.mark.parametrize('value', [[0]*5, [-1,1,1,1,1], [1,2], [float('nan')]*5])
def test_invalid_coefficients(value):
    with pytest.raises(ValueError):
        coefficients(value, L.DEFAULT)


def test_other_combinations_reject_custom_coefficients():
    with pytest.raises(ValueError, match='separate_facet_sum'):
        coefficients([1,0,0,0,0], {**L.DEFAULT, 'facet':'topic_only'})


def test_real_case_cache_isolation_pinned_coefficients_and_original_response():
    lab = WeightedLab()
    payload = {'case_id':'case_001'}
    original = L.Lab.replay(lab, payload)
    default = lab.replay(payload)
    for key in ('summary','comparison_summary','movements','gold_pointers'):
        assert default[key] == original[key]
    custom = lab.replay({**payload, 'coefficients':[1,0,0,0,0], 'compare_coefficients':[0,1,0,0,0]})
    topic = lab.replay({**payload, 'policy':{**L.DEFAULT,'facet':'topic_only'}})
    assert custom['summary'] == topic['summary']
    assert [m['chunk_id'] for m in custom['movements']] == [m['chunk_id'] for m in topic['movements']]
    pinned = lab.replay({**payload, 'coefficients':[0,1,0,0,0], 'compare_coefficients':[0,1,0,0,0]})
    assert pinned['summary'] == custom['comparison_summary']
    assert all(m['old_position'] == m['new_position'] for m in pinned['movements'])
    assert lab.replay(payload)['movements'] == original['movements']

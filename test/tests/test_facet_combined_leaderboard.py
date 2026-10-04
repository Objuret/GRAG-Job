"""Selected settings must reproduce the numeric cells advertised in the lab."""
import numpy as np
import pytest
from facet_combined_leaderboard import leaderboard, ranked, METRICS
from facet_weighted_lab import WeightedLab


def test_ranking_keeps_primary_metric_and_undefined_precision_last():
    values = np.array([[.9, .1, .18], [.4, .8, .53], [.1, np.nan, 0.]])
    assert ranked(values, 0).tolist() == [0, 1, 2]
    assert ranked(values, 1).tolist() == [1, 0, 2]
    assert ranked(values, 2).tolist() == [1, 0, 2]


@pytest.mark.parametrize('metric', METRICS)
def test_live_replays_match_reference_selected_numeric_cells(metric):
    result = leaderboard(metric)
    assert result['completed_cases'] == 95
    assert result['configurations_per_case'] == 11764
    assert len(result['best_per_query']['cases']) == 95
    lab = WeightedLab()
    # One original smoke and one non-smoke query, selected mechanically by index.
    for row in (result['best_per_query']['cases'][0], result['best_per_query']['cases'][10]):
        replay = lab.replay({'case_id': row['case_id'], 'policy': row['policy'],
                             'coefficients': row['coefficients']})
        r, p = replay['summary']['recall_id'], replay['summary']['precision_id']
        f1 = 2*r*p/(r+p) if p is not None and r+p > 0 else 0.
        np.testing.assert_allclose([r, p, f1], [row[k] for k in METRICS], atol=1e-12, rtol=0)


def test_coefficient_constraints_filter_candidates_and_choices():
    for subset in ('topic_present', 'topic_largest'):
        result = leaderboard(subset=subset)
        assert all(row[subset] for row in result['leaders'] + result['best_per_query']['cases'])
    best = leaderboard(subset='topic_largest')['leaders'][0]
    assert best['coefficients'] == [.75, .75, 0., 0., .5]
    assert best['recall_id'] == pytest.approx(.509551034011632)

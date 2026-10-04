"""The grouped replay must reproduce the per-policy ranking primitives exactly."""
import numpy as np
import pytest

import facet_retrieval_lab as L
import facet_weighted_fast as F


@pytest.mark.parametrize('seed', range(5))
def test_competition_many_matches_row_wise_competition(seed):
    rng = np.random.default_rng(seed)
    values = rng.integers(0, 6, size=(7, 40)).astype(float) / 5  # many ties, many zeros
    mask = rng.random(40) > 0.3
    for m in (None, mask):
        got = F.competition_many(values, m)
        want = np.stack([L.competition(row, m) for row in values])
        assert got.dtype == np.int32
        assert np.array_equal(got, want)


def test_competition_many_unsupported_get_n_plus_one():
    values = np.zeros((2, 5))
    assert (F.competition_many(values) == 6).all()


def test_families_groups_by_match_topology_join_and_rejects_other_facets():
    policies = [dict(L.DEFAULT), {**L.DEFAULT, 'scope': 'all'}, {**L.DEFAULT, 'match': 'maximum'}]
    groups = F.families(policies)
    assert groups == {('product', 'both', 'union'): [0, 1], ('maximum', 'both', 'union'): [2]}
    with pytest.raises(ValueError):
        F.families([{**L.DEFAULT, 'facet': 'topic_only'}])


def test_max_cut_chunks_counts_smallest_units_to_the_budget():
    units = {f'c{i}': {'serialized_chars': 1000, 'artifact_ids': []} for i in range(100)}
    assert F.max_cut_chunks(units) == 72
    units['big'] = {'serialized_chars': 100000, 'artifact_ids': []}
    assert F.max_cut_chunks(units) == 72

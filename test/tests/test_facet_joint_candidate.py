import numpy as np
import pytest

from artefact.facet_joint_candidate import freeze_reference, rank_joint_candidate


def inputs():
    return dict(
        chunk_ids=["a", "b", "c"], query_tag_ids=["one", "two"],
        edge_ids=["ea", "eb", "ec"], edge_tag_indices=[0, 1, 2],
        edge_chunk_indices=[0, 1, 2], edge_facets=np.ones((3, 5)),
        query_facet_weights=np.array([[1., 0, 0, 0, 0], [1., 0, 0, 0, 0]]),
        query_tag_cosines=np.array([[1., 0, 0], [0, .8, 0]]),
        query_chunk_cosines=np.ones((2, 3)), query_description_cosines=np.ones(3),
        reference=freeze_reference(np.array([[0.] * 5, [1.] * 5])),
    )


def test_absolute_weight_attenuation_changes_relative_query_sponsorship():
    args = inputs()
    before = rank_joint_candidate(**args)
    args["query_facet_weights"][0] *= .5
    after = rank_joint_candidate(**args)
    assert before["ranked_chunk_ids"][:2] == ["a", "b"]
    assert after["ranked_chunk_ids"][:2] == ["b", "a"]
    assert after["scores"][0] == pytest.approx(before["scores"][0] / 2)
    assert after["scores"][1] == before["scores"][1]


def test_uniform_weight_scaling_preserves_order_and_scales_graph_scores():
    args = inputs()
    args["adjacency_pairs"] = [(0, 2)]
    before = rank_joint_candidate(**args)
    args["query_facet_weights"] *= .2
    after = rank_joint_candidate(**args)
    assert after["ranked_chunk_ids"] == before["ranked_chunk_ids"]
    np.testing.assert_allclose(after["scores"], .2 * before["scores"])
    np.testing.assert_allclose(after["graph_scores"], .2 * before["graph_scores"])


def test_zero_weight_facet_is_inert_and_facets_off_keeps_absolute_topic():
    args = inputs()
    before = rank_joint_candidate(**args)
    args["edge_facets"][:, 1:] = [[-100] * 4, [100] * 4, [.1] * 4]
    inactive = rank_joint_candidate(**args)
    np.testing.assert_array_equal(before["scores"], inactive["scores"])
    args["query_facet_weights"][:, 1:] = 99
    off = rank_joint_candidate(**args, facets_enabled=False)
    np.testing.assert_array_equal(before["scores"], off["scores"])
    args["query_facet_weights"][:] = 0
    args["adjacency_pairs"] = [(0, 2)]
    empty = rank_joint_candidate(**args)
    assert not empty["scores"].any()
    assert not empty["graph_scores"].any()


def test_fixed_midrank_reference_is_not_rebuilt_when_candidate_added():
    ref = freeze_reference(np.array([[0] * 5, [1] * 5, [1] * 5, [2] * 5]))
    np.testing.assert_allclose(ref.transform(np.array([[1] * 5])), .5)
    old = ref.transform(np.array([[.5] * 5, [1] * 5]))
    new = ref.transform(np.array([[.5] * 5, [1] * 5, [100] * 5]))
    np.testing.assert_array_equal(old, new[:2])
    args = inputs()
    before = rank_joint_candidate(**args)
    args["chunk_ids"].append("extra")
    args["edge_ids"].append("extra-edge")
    args["edge_tag_indices"].append(2)
    args["edge_chunk_indices"].append(3)
    args["edge_facets"] = np.vstack([args["edge_facets"], [100] * 5])
    args["query_chunk_cosines"] = np.column_stack([args["query_chunk_cosines"], [1, 1]])
    args["query_description_cosines"] = np.ones(4)
    after = rank_joint_candidate(**args)
    np.testing.assert_array_equal(before["scores"], after["scores"][:3])


def test_duplicate_routes_graph_groups_and_identical_query_tags_do_not_vote():
    args = inputs()
    args["groups"] = {"shared_channel_same_product": [[0, 1, 2]]}
    before = rank_joint_candidate(**args)
    args["edge_ids"].append("duplicate-a")
    args["edge_tag_indices"].append(3)
    args["edge_chunk_indices"].append(0)
    args["edge_facets"] = np.vstack([args["edge_facets"], args["edge_facets"][0]])
    args["query_tag_cosines"] = np.column_stack([args["query_tag_cosines"], args["query_tag_cosines"][:, 0]])
    args["query_tag_ids"].append("duplicate-one")
    for key in ("query_tag_cosines", "query_chunk_cosines", "query_facet_weights"):
        args[key] = np.vstack([args[key], args[key][0]])
    args["groups"]["shared_channel_same_product"] *= 2
    after = rank_joint_candidate(**args)
    np.testing.assert_array_equal(before["scores"], after["scores"])
    assert before["ranked_chunk_ids"] == after["ranked_chunk_ids"]


def test_negative_cosines_cannot_double_negative_rescue():
    args = inputs()
    args["query_tag_cosines"][:] = -1
    args["query_chunk_cosines"][:] = -1
    args["query_description_cosines"][:] = -1
    args["adjacency_pairs"] = [(0, 2)]
    result = rank_joint_candidate(**args)
    assert not result["scores"].any()
    assert not result["direct_scores"].any()
    assert not result["graph_scores"].any()


def test_graph_reaches_description_fit_weak_tag_neighbor_only_and_excludes_self():
    args = inputs()
    args["query_facet_weights"][1] = 0
    args["adjacency_pairs"] = [(0, 2), (0, 0)]
    result = rank_joint_candidate(**args)
    assert result["direct_scores"][0, 2] == 0
    assert result["graph_scores"][0, 2] == pytest.approx(.5 * result["direct_scores"][0, 0])
    assert result["scores"][1] == 0  # No declared relation to b.
    assert result["graph_scores"][0, 0] == 0  # Neither self edge nor return hop.
    row = next(row for row in result["rows"] if row["chunk_id"] == "c")
    assert row["provenance"]["seed_chunk_id"] == "a"
    assert row["provenance"]["edge_id"] == "ea"
    assert row["provenance"]["route_type"] == "file_adjacency"
    assert row["provenance"]["A"] == pytest.approx(sum(row["provenance"]["facet_components"]))
    args["query_chunk_cosines"][0, 2] = -1
    assert rank_joint_candidate(**args)["scores"][2] == 0
    args["adjacency_pairs"] = [(0, 3)]
    with pytest.raises(ValueError, match="outside supplied graph"):
        rank_joint_candidate(**args)


def test_group_self_exclusion_uses_second_seed_and_singletons_supply_nothing():
    args = inputs()
    args["query_tag_cosines"][0, 1] = .2
    args["groups"] = {"shared_channel_same_product": [[0, 1], [2]]}
    result = rank_joint_candidate(**args)
    assert result["graph_scores"][0, 0] == pytest.approx(.5 * result["direct_scores"][0, 1])
    assert result["graph_scores"][0, 1] == pytest.approx(.5 * result["direct_scores"][0, 0])
    assert not result["graph_scores"][:, 2].any()


def test_whole_query_fit_final_stable_tie_and_full_ranks():
    args = inputs()
    args["query_description_cosines"][:] = 0
    result = rank_joint_candidate(**args)
    assert result["ranked_chunk_ids"] == ["a", "b", "c"]
    assert result["ranks"].tolist() == [1, 2, 3]
    assert len(result["rows"]) == 3


def test_topic_and_four_auxiliary_coefficients_follow_declared_convention():
    args = inputs()
    args["query_facet_weights"][0] = [2, 3, 4, 5, 6]
    result = rank_joint_candidate(**args)
    row = next(row for row in result["rows"] if row["chunk_id"] == "a")
    assert row["provenance"]["topic_component"] == pytest.approx(2 * .75)
    assert row["provenance"]["auxiliary_component"] == pytest.approx((3 + 4 + 5 + 6) * .75 / 4)
    assert row["score"] == pytest.approx((2 + (3 + 4 + 5 + 6) / 4) * .75)

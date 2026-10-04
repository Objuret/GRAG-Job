import numpy as np
import pytest

from artefact.facet_joint_candidate import freeze_reference, rank_joint_candidate
from artefact.facet_stream_envelope import rank_facet_stream_envelope


def inputs():
    return dict(
        chunk_ids=["a", "b", "c"], query_tag_ids=["one", "two"],
        edge_ids=["ea", "eb", "ec"], edge_tag_indices=[0, 1, 2],
        edge_chunk_indices=[0, 1, 2], edge_facets=np.ones((3, 5)),
        query_facet_weights=np.array([[1., 0, 0, 0, 0], [0., 0, 1, 0, 0]]),
        query_tag_cosines=np.array([[1., 0, 0], [0, .8, 0]]),
        query_chunk_cosines=np.ones((2, 3)), query_description_cosines=np.ones(3),
        reference=freeze_reference(np.array([[0.] * 5, [1.] * 5])),
    )


def test_envelope_bounds_max_of_sums_for_random_routes_and_actual_neighbors():
    rng = np.random.default_rng(913)
    for _ in range(8):
        args = inputs()
        args["query_facet_weights"] = rng.uniform(0, 1, (2, 5))
        args["query_tag_cosines"] = rng.uniform(-1, 1, (2, 3))
        args["query_chunk_cosines"] = rng.uniform(-1, 1, (2, 3))
        args["query_description_cosines"] = rng.uniform(-1, 1, 3)
        args["edge_facets"] = rng.uniform(0, 1, (3, 5))
        args["groups"] = {"shared_product_channel": [[0, 1]]}
        args["adjacency_pairs"] = [(1, 2)]
        envelope = rank_facet_stream_envelope(**args)
        original = rank_joint_candidate(**args)
        assert np.all(envelope["scores"] + 1e-12 >= original["scores"])


def test_one_route_without_shape_equals_original_and_components_reconstruct_score():
    args = inputs()
    args["query_facet_weights"] = [[.9, .2, .7, .1, .8]]
    args["query_tag_ids"] = ["one"]
    args["query_tag_cosines"] = [[.8, .4, .1]]
    args["query_chunk_cosines"] = [[.7, .6, .9]]
    args["query_description_cosines"] = [.5, .3, .8]
    envelope = rank_facet_stream_envelope(**args)
    original = rank_joint_candidate(**args)
    np.testing.assert_allclose(envelope["scores"], original["scores"])
    for row in envelope["rows"]:
        assert row["score"] == pytest.approx(sum(p["contribution"] for p in row["provenance"].values()))
        for p in row["provenance"].values():
            assert p["Z"] == pytest.approx(p["M"] * p["D_seed"] * p["u"] * p["F"])


def test_distinct_facet_sponsors_both_survive_at_same_destination():
    args = inputs()
    args["edge_chunk_indices"] = [0, 0, 2]
    result = rank_facet_stream_envelope(**args)
    row = next(r for r in result["rows"] if r["chunk_id"] == "a")
    assert row["provenance"]["topic"]["edge_id"] == "ea"
    assert row["provenance"]["topic"]["query_tag_id"] == "one"
    assert row["provenance"]["why"]["edge_id"] == "eb"
    assert row["provenance"]["why"]["query_tag_id"] == "two"
    assert row["score"] == pytest.approx(.75 + .25 * .8 * .75)
    assert row["score"] > rank_joint_candidate(**args)["scores"][0]
    assert row["provenance"]["temporal"] is None


def test_cloned_routes_tags_and_groups_do_not_multiply_contributions():
    args = inputs()
    args["groups"] = {"shared_product_channel": [[0, 1, 2]]}
    before = rank_facet_stream_envelope(**args)
    args["edge_ids"].append("clone")
    args["edge_tag_indices"].append(3)
    args["edge_chunk_indices"].append(0)
    args["edge_facets"] = np.vstack([args["edge_facets"], args["edge_facets"][0]])
    args["query_tag_cosines"] = np.column_stack([args["query_tag_cosines"], args["query_tag_cosines"][:, 0]])
    args["query_tag_ids"].append("clone")
    for key in ("query_facet_weights", "query_chunk_cosines", "query_tag_cosines"):
        args[key] = np.vstack([args[key], args[key][0]])
    args["groups"]["shared_product_channel"] *= 2
    after = rank_facet_stream_envelope(**args)
    np.testing.assert_array_equal(before["scores"], after["scores"])
    np.testing.assert_array_equal(before["per_facet_scores"], after["per_facet_scores"])


def test_graph_facets_have_separate_seeds_and_no_self_or_second_hop():
    args = inputs()
    args["adjacency_pairs"] = [(0, 2), (1, 2), (0, 0)]
    result = rank_facet_stream_envelope(**args)
    row = next(r for r in result["rows"] if r["chunk_id"] == "c")
    assert row["provenance"]["topic"]["seed_chunk_id"] == "a"
    assert row["provenance"]["why"]["seed_chunk_id"] == "b"
    assert row["provenance"]["topic"]["Z"] == pytest.approx(.5 * .75)
    assert row["provenance"]["why"]["Z"] == pytest.approx(.5 * .8 * .75)
    assert not result["graph_scores"][:, :, :2].any()
    args["adjacency_pairs"] = []
    args["groups"] = {"shared_product_channel": [[0], [1], [2]]}
    assert not rank_facet_stream_envelope(**args)["graph_scores"].any()


def test_zero_weights_return_full_stable_order_and_no_witnesses():
    args = inputs()
    args["query_facet_weights"][:] = 0
    args["groups"] = {"shared_product_channel": [[0, 1, 2]]}
    result = rank_facet_stream_envelope(**args)
    assert result["ranked_chunk_ids"] == ["a", "b", "c"]
    assert not result["scores"].any()
    assert not result["per_facet_scores"].any()
    assert all(p is None for row in result["rows"] for p in row["provenance"].values())


def test_auxiliary_off_and_negative_cosines_keep_original_semantics():
    args = inputs()
    off = rank_facet_stream_envelope(**args, facets_enabled=False)
    assert not off["per_facet_scores"][:, 1:].any()
    assert off["scores"][0] == pytest.approx(.75)
    args["query_tag_cosines"][:] = -1
    args["query_chunk_cosines"][:] = -1
    assert not rank_facet_stream_envelope(**args)["scores"].any()

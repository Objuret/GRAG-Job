"""Behavior and source parity for the isolated forum replay; no external calls."""
import ast
from dataclasses import replace
from pathlib import Path
from typing import Optional

import numpy as np
import pytest

from artefact.facet_route_rank import (
    FACETS, ForumConfig, first_per_chunk, pool_keys, pool_steps, replay_forum,
    weighted_values,
)


def config(mode="weighted", **changes):
    return replace(ForumConfig(mode, .05, .02, .028, 1., .002), **changes)


@pytest.fixture(scope="module")
def source_functions():
    # Compile only pure functions from the CURRENT arm. Importing the whole arm
    # would consult environment/cache configuration unrelated to this operator.
    source = Path(__file__).parents[1] / "arms" / "artefact_v3.py"
    wanted = {"pool_steps", "weighted_g", "bounded_r", "mode_key_columns", "pool_key_tuples"}
    tree = ast.parse(source.read_text(encoding="utf-8"))
    subset = ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in wanted], type_ignores=[])
    env = {"np": np, "Optional": Optional, "COS_NOISE": .002}
    exec(compile(subset, str(source), "exec"), env)
    return env


@pytest.mark.parametrize("mode,adjust,place,topic", [
    ("weighted", "bounded", "after", "ordered"),
    ("weighted", "bounded", "before", "ordered"),
    ("weighted", "level", "after", "ordered"),
    ("multirank", "bounded", "after", "ordered"),
    ("multirank", "bounded", "before", "first"),
])
def test_pool_keys_match_actual_source_with_missing_and_ties(source_functions, mode, adjust, place, topic):
    rng = np.random.default_rng(220926)
    strengths = rng.normal(size=(30, 5))
    strengths[3, 1:] = np.nan
    strengths[7, 2] = np.nan
    strengths[4] = strengths[5]
    strengths[8, 0] = np.nan
    q = np.array([.4, .6, .2, .8, .7])
    order = ("activity", "concreteness", "temporal", "topic", "why")
    tc, l2, l6 = rng.normal(size=(3, 30))
    ids = [f"c{i:02d}" for i in range(30)]
    cfg = config(mode, adjust=adjust, description_place=place, topic_key=topic,
                 betas=(.722, .679, .845, .603))
    actual, names, detail = pool_keys(strengths, q, order, 2, l2, l6, tc, np.arange(30), cfg, g_band=.3)
    cols, expected_names, _ = source_functions["mode_key_columns"](
        mode, strengths[:, 0], strengths[:, 1:], order, FACETS,
        topic_band=cfg.topic_band, facet_band=cfg.facet_band,
        weights=dict(zip(FACETS[1:], q[1:])), betas=dict(zip(FACETS[1:], cfg.betas)),
        adjust=adjust, g_band=.3, topic_key=topic, r_band=cfg.r_band)
    expected, expected_names = source_functions["pool_key_tuples"](
        2, cols, expected_names, source_functions["pool_steps"](l2, cfg.description_band),
        source_functions["pool_steps"](l6, cfg.description_band), tc, ids, place)
    numeric = np.array([list(k[:-1]) + [ids.index(k[-1])] for k in expected])
    np.testing.assert_array_equal(actual, numeric)
    assert names == expected_names
    if mode == "weighted":
        g, _, _ = source_functions["weighted_g"](strengths[:, 1:], q[1:], np.array(cfg.betas))
        np.testing.assert_allclose(detail["g"], g, equal_nan=True)


def fixture_inputs(mode="weighted"):
    return dict(edge_tag=np.array([0, 1, 2, 0, 2]),
        edge_chunk=np.array([0, 1, 2, 2, 0]),
        edge_facets=np.array([[.51, 0, 1, 2, 3], [.50, 1, 3, 1, 2],
                             [.6, 2, 0, 2, 1], [.52, 1, 4, 2, 0], [.55, 4, 2, 1, 1]]),
        chunk_ids=["a", "b", "c"],
        tag_cos=np.array([[.91, .87, .5], [.4, .88, .92]]),
        part_chunk_cos=np.array([[.4, .3, .2], [.3, .4, .1]]),
        description_chunk_cos=np.array([.3, .4, .2]), centrality=np.array([.7, .8]),
        query_facets=np.array([[.9, .8, .4, .2, .1], [.8, .1, .2, .9, .4]]),
        facet_orders=[FACETS, ("activity", "topic", "concreteness", "why", "temporal")],
        config=config(mode), in_scope=np.array([True, False, True]))


@pytest.mark.parametrize("mode", ["weighted", "multirank"])
def test_global_complete_tuple_equals_actual_staged_walk(source_functions, mode):
    data = fixture_inputs(mode)
    replay = replay_forum(**data)
    et, ec = data["edge_tag"], data["edge_chunk"]
    cfg = data["config"]
    priority = {p: i for i, p in enumerate(sorted(range(2), key=lambda p: (-data["centrality"][p], p)))}
    picked = [np.floor((row.max() - row[et]) / cfg.tag_band + 1e-12).astype(int) for row in data["tag_cos"]]
    walked = []
    for sp in (0, 1):
        in_pass = np.flatnonzero(data["in_scope"][ec] == (sp == 0))
        levels = sorted({int(lv[e]) for lv in picked for e in in_pass})
        for level in levels:
            candidates = []
            for p in range(2):
                at = in_pass[picked[p][in_pass] == level]
                if not len(at):
                    continue
                s = data["edge_facets"][at]
                cols, names, _ = source_functions["mode_key_columns"](
                    mode, s[:, 0], s[:, 1:], data["facet_orders"][p], FACETS,
                    topic_band=cfg.topic_band, facet_band=cfg.facet_band,
                    weights=dict(zip(FACETS[1:], data["query_facets"][p, 1:])), r_band=cfg.r_band)
                keys, _ = source_functions["pool_key_tuples"](priority[p], cols, names,
                    source_functions["pool_steps"](data["part_chunk_cos"][p, ec[at]], cfg.description_band),
                    source_functions["pool_steps"](data["description_chunk_cos"][ec[at]], cfg.description_band),
                    data["tag_cos"][p, et[at]], [data["chunk_ids"][c] for c in ec[at]])
                candidates += [(key, p * len(et) + e) for key, e in zip(keys, at)]
            candidates.sort(key=lambda x: x[0])
            walked += [r for _, r in candidates]
    np.testing.assert_array_equal(replay.order, walked)
    seen, selected = set(), []
    for r in walked:
        c = ec[r % len(et)]
        if c not in seen:
            seen.add(c)
            selected.append(r)
    np.testing.assert_array_equal(replay.selected_routes, selected)
    assert replay.trace(selected[0])["selected"]


def two_edges(mode="weighted"):
    return dict(edge_tag=[0, 1], edge_chunk=[0, 1],
        edge_facets=np.array([[.51, 0, 0, 0, 0], [.50, 1, 0, 0, 0]]),
        chunk_ids=["a", "b"], tag_cos=np.array([[.9, .9]]),
        part_chunk_cos=np.zeros((1, 2)), description_chunk_cos=np.zeros(2),
        centrality=[.7], query_facets=np.array([[.9, 1, 0, 0, 0]]),
        facet_orders=[FACETS], config=config(mode))


@pytest.mark.parametrize("mode", ["weighted", "multirank"])
def test_facet_ablation_preserves_query_and_exposes_contribution(mode):
    data = two_edges(mode)
    original_q = data["query_facets"].copy()
    on = replay_forum(**data)
    off = replay_forum(**data, zeroed_facets=True)
    assert on.chunk_order.tolist() == [1, 0]
    assert off.chunk_order.tolist() == [0, 1]
    np.testing.assert_array_equal(original_q, data["query_facets"])
    assert on.deciding_key(0, 1)["field"] in ("adjusted topic", "temporal")


@pytest.mark.parametrize("barrier", ["scope pass", "pick level", "part rank"])
def test_higher_keys_block_better_facet_route(barrier):
    data = two_edges()
    if barrier == "scope pass":
        data["in_scope"] = [True, False]
    elif barrier == "pick level":
        data["tag_cos"] = np.array([[.9, .8]])
    else:
        data["tag_cos"] = np.array([[.9, .7], [.7, .9]])
        data["part_chunk_cos"] = np.zeros((2, 2))
        data["centrality"] = [.8, .7]
        data["query_facets"] = np.repeat(data["query_facets"], 2, axis=0)
        data["facet_orders"] *= 2
    result = replay_forum(**data)
    assert result.chunk_order.tolist() == [0, 1]
    assert result.deciding_key(*result.selected_routes)["field"] == barrier


def test_weighted_pool_extreme_reverses_existing_pair_and_common_scaling_cancels():
    topic = np.array([.51, .50])
    s = np.array([[0, 0, 0, 0], [1, 0, 0, 0]])
    _, initial = weighted_values(topic, s, [1, 0, 0, 0], np.ones(4), .028)
    _, tiny = weighted_values(topic, s, [1e-9, 0, 0, 0], np.ones(4), .028)
    _, enlarged = weighted_values(np.r_[topic, 0.], np.vstack([s, [-100, 0, 0, 0]]),
                                  [1, 0, 0, 0], np.ones(4), .028)
    assert initial[0] < initial[1]
    assert enlarged[0] > enlarged[1]
    np.testing.assert_allclose(initial, tiny, atol=0, rtol=0)


def test_multikey_pool_maximum_changes_existing_topic_bins():
    np.testing.assert_array_equal(pool_steps([.510, .509], .028), [0, 0])
    np.testing.assert_array_equal(pool_steps([.510, .509, .5375], .028), [0, 1, 0])


def test_missing_is_worst_in_multikey_but_not_uniformly_penalized_in_weighted():
    np.testing.assert_array_equal(pool_steps([np.nan, 0, 2], 1), [3, 2, 0])
    np.testing.assert_array_equal(pool_steps([np.nan, np.nan], 1), [0, 0])
    g, r = weighted_values([.5, .5, .5], [[np.nan] * 4, [-1, 0, 0, 0], [1, 0, 0, 0]],
                           np.ones(4), np.ones(4), .028)
    assert np.isnan(g[0]) and r[0] == r[1] == .5 and r[2] == .528


def test_query_topic_unused_except_all_zero_cached_fallback():
    data = two_edges()
    before = replay_forum(**data)
    data["query_facets"][0, 0] = .1
    np.testing.assert_array_equal(before.keys, replay_forum(**data).keys)
    data["query_facets"][:] = 0.
    fallback = replay_forum(**data)
    assert fallback.chunk_order.tolist() == [1, 0]
    corrected = replay_forum(**{**data, "config": replace(data["config"], cached_zero_fallback=False)})
    assert corrected.chunk_order.tolist() == [0, 1]
    data["query_facets"][0, 0] = .1
    assert replay_forum(**data).chunk_order.tolist() == [0, 1]


def test_multikey_zero_relevance_still_sorts_its_graph_column():
    data = two_edges("multirank")
    data["query_facets"][:] = 0.
    assert replay_forum(**data).chunk_order.tolist() == [1, 0]
    assert replay_forum(**data, zeroed_facets=True).chunk_order.tolist() == [0, 1]


@pytest.mark.parametrize("mode", ["weighted", "multirank"])
def test_edge_permutation_preserves_chunk_order_and_nontied_route_provenance(mode):
    data = fixture_inputs(mode)
    original = replay_forum(**data)
    permutation = np.array([4, 2, 0, 3, 1])
    permuted = replay_forum(**{**data, **{k: data[k][permutation] for k in ("edge_tag", "edge_chunk", "edge_facets")}})
    np.testing.assert_array_equal(original.chunk_order, permuted.chunk_order)
    for a, b in zip(original.selected_routes, permuted.selected_routes):
        assert a // 5 == b // 5 and a % 5 == permutation[b % 5]


def test_exact_duplicate_route_tie_changes_provenance_not_chunk_order():
    data = two_edges()
    data["edge_tag"] = np.array([0, 1, 0])
    data["edge_chunk"] = np.array([0, 0, 1])
    data["edge_facets"] = np.tile([.5, 1, 1, 1, 1], (3, 1))
    original = replay_forum(**data)
    assert original.deciding_key(0, 1)["field"] is None
    perm = np.array([1, 0, 2])
    changed = replay_forum(**{**data, **{k: data[k][perm] for k in ("edge_tag", "edge_chunk", "edge_facets")}})
    np.testing.assert_array_equal(original.chunk_order, changed.chunk_order)
    assert original.selected_routes[0] == changed.selected_routes[0] == 0
    assert perm[changed.selected_routes[0]] != original.selected_routes[0]


def test_shared_generic_max_masks_specific_route_without_predicting_full_sort():
    # The two columns here are passages, already maximized over adjacent graph
    # tags for EACH query tag. Taking another max over query tags is a separate
    # aggregation policy; it is not the cited paper's one-whole-query phrase max.
    routes = np.array([[1., 1.], [.55, .9]])  # broad report tag, specific sharing tag
    assert np.argmax(routes[1]) == 1
    np.testing.assert_array_equal(routes.max(axis=0), [1., 1.])


def test_arbitrary_arrival_is_not_the_declared_complete_key_order():
    data = two_edges()
    result = replay_forum(**data)
    assert first_per_chunk([0, 1], data["edge_chunk"], 2).tolist() == [0, 1]
    assert result.selected_routes.tolist() == [1, 0]


def test_pick_population_is_explicit_and_no_routes_are_pruned():
    data = two_edges()
    data["tag_cos"] = np.array([[.9, .8, 1.]])
    result = replay_forum(**data, candidate_tag=[True, True, False])
    assert result.keys[0, 1] == 0 and len(result.order) == 2
    with pytest.raises(ValueError, match="eligible edge"):
        replay_forum(**data, candidate_tag=[False, True, True])


def test_duplicating_an_identical_query_tag_does_not_add_evidence():
    data = fixture_inputs()
    original = replay_forum(**data)
    indices = [0, 0, 1]
    repeated = {**data, **{k: data[k][indices] for k in
                ("tag_cos", "part_chunk_cos", "centrality", "query_facets")},
                "facet_orders": [data["facet_orders"][i] for i in indices]}
    duplicate = replay_forum(**repeated)
    np.testing.assert_array_equal(original.chunk_order, duplicate.chunk_order)
    assert len(duplicate.order) > len(original.order)


def test_tied_query_centrality_uses_query_tag_input_order_as_declared_policy():
    data = two_edges()
    data.update(tag_cos=np.array([[.9, .7], [.7, .9]]),
                part_chunk_cos=np.zeros((2, 2)), centrality=np.array([.8, .8]),
                query_facets=np.repeat(data["query_facets"], 2, axis=0),
                facet_orders=[FACETS, FACETS])
    original = replay_forum(**data)
    permuted = replay_forum(**{**data, **{k: data[k][::-1] for k in
                            ("tag_cos", "part_chunk_cos", "centrality", "query_facets")}})
    assert original.chunk_order.tolist() == [0, 1]
    assert permuted.chunk_order.tolist() == [1, 0]
    assert original.deciding_key(*original.selected_routes)["field"] == "part rank"

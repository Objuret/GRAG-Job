"""Context boundaries and accounting, not semantic relevance claims."""
import json

import numpy as np
import pytest

from artefact.facet_need_frontier import merge_frontiers
from artefact.facet_recruitment_candidate import recruit_with_record_context
from harness.char_budget import cut_at_budget


def chunk(cid, bounds=(0, 5), text="abcde", **locator_changes):
    loc = {"parent_ref": "parent", "id": "record", "index": 1,
           "field": "body", "section": "content"}
    if bounds is not None:
        loc["char_range"] = list(bounds)
    loc.update(locator_changes)
    return {"chunkId": cid, "relpath": "file.json", "locator": loc, "source_text": text}


def run(chunks, scores, budget=None, streams=None):
    return recruit_with_record_context(chunk_rows=chunks,
        stream_ids=streams or ["s"], stream_scores=scores, source_character_budget=budget)


def rows(result):
    return {row["chunk_id"]: row for row in result["rows"]}


@pytest.mark.parametrize("field,value", [("parent_ref", "other"), ("id", "other"),
    ("index", 2), ("field", "title"), ("section", "other"), ("relpath", "other.json")])
def test_touching_ranges_cannot_cross_any_record_identity_field(field, value):
    a, b = chunk("a"), chunk("b", (5, 10))
    if field == "relpath":
        b[field] = value
    else:
        b["locator"][field] = value
    result = run([a, b], [[2, 0]])
    assert rows(result)["b"]["depth"] is None
    assert len(result["components"]) == 2
    assert result["selected_chunk_ids"] == ["a"]


def test_range_gap_and_nonrange_sibling_are_not_bridged():
    result = run([chunk("a"), chunk("b", (6, 10)), chunk("c", None)], [[2, 0, 0]])
    assert result["unsupported_chunk_ids"] == ["b", "c"]
    assert rows(result)["c"]["component_id"] is None


def test_supported_component_recovers_unsupported_sibling_without_new_nomination():
    chunks = [chunk("a"), chunk("b", (4, 9)), chunk("c", (9, 14)), chunk("d", (20, 25))]
    chunks[1]["locator"] = json.dumps(chunks[1]["locator"])
    scores = np.array([[3., 0., 0., 0.]])
    saved = scores.copy()
    result = run(chunks, scores)
    assert result["nomination"] == merge_frontiers(["a", "b", "c", "d"], ["s"], scores)
    np.testing.assert_array_equal(scores, saved)
    assert result["nomination"]["unsupported_chunk_ids"] == ["b", "c", "d"]
    assert result["unsupported_chunk_ids"] == ["d"]
    for cid in ("b", "c"):
        assert rows(result)[cid]["original_depth"] is None
        assert rows(result)[cid]["depth"] == 1
        assert rows(result)[cid]["trigger_chunk_ids"] == ["a"]
        assert rows(result)[cid]["context_added"] is True
    assert rows(result)["a"]["context_added"] is False
    assert result["selected_source_characters"] == 15  # overlap is counted per chunk


def test_all_zero_components_remain_unsupported():
    result = run([chunk("a"), chunk("b", (5, 10))], [[0, 0]])
    assert result["frontiers"] == []
    assert result["selected_chunk_ids"] == []
    assert result["unsupported_chunk_ids"] == ["a", "b"]
    assert all(r["depth"] is None and r["trigger_chunk_ids"] == [] and not r["context_added"]
               for r in result["rows"])


def test_earliest_component_members_trigger_without_duplicate_votes():
    chunks = [chunk("a"), chunk("b", (5, 10)), chunk("c", (10, 15))]
    result = run(chunks, [[4, 4, 1], [2, 2, 1]], streams=["s", "duplicate"])
    assert all(row["trigger_chunk_ids"] == ["a", "b"] for row in result["rows"])
    assert rows(result)["c"]["original_depth"] == 3
    assert rows(result)["c"]["depth"] == 1
    assert result["frontiers"][0]["size"] == 3
    assert len(result["selected_chunk_ids"]) == 3


@pytest.mark.parametrize("context_id,evidence_id", [("a", "z"), ("z", "a")])
def test_serving_prefix_keeps_fitting_sponsor_before_recovery_regardless_of_ids(
    context_id, evidence_id,
):
    chunks = [chunk(context_id, (0, 8), "CONTEXT!"),
              chunk(evidence_id, (8, 16), "EVIDENCE")]
    result = run(chunks, [[0, 1]])
    by_id = {c["chunkId"]: c for c in chunks}
    cut = cut_at_budget(((cid, by_id[cid]["source_text"])
                         for cid in result["selected_chunk_ids"]), 8)
    assert cut.contexts == ["EVIDENCE"]
    assert result["selected_chunk_ids"] == [evidence_id, context_id]
    assert [r["chunk_id"] for r in result["rows"]] == result["selected_chunk_ids"]
    # The research budget still admits complete frontiers, not just sponsors.
    assert run(chunks, [[0, 1]], 8)["selected_chunk_ids"] == []
    assert run(chunks, [[0, 1]], 16)["selected_chunk_ids"] == [evidence_id, context_id]


def test_all_simultaneous_nominations_precede_advanced_context():
    chunks = [chunk("a-context", (0, 5)), chunk("z-sponsor", (5, 10)),
              chunk("b-advanced", (10, 15)), chunk("y-independent", None),
              chunk("c-unsupported", (20, 25))]
    scores = [[0, 4, 1, 4, 0]]
    result = run(chunks, scores)
    assert result["selected_chunk_ids"] == [
        "y-independent", "z-sponsor", "a-context", "b-advanced"]
    assert [r["chunk_id"] for r in result["rows"] if r["depth"] is not None] == result["selected_chunk_ids"]
    assert result["nomination"] == merge_frontiers([c["chunkId"] for c in chunks], ["s"], scores)
    assert rows(result)["b-advanced"]["original_depth"] == 3
    assert rows(result)["b-advanced"]["depth"] == 1
    assert result["unsupported_chunk_ids"] == ["c-unsupported"]


def test_chunk_and_stream_permutation_preserve_recovery_and_component_ids():
    chunks = [chunk("a"), chunk("b", (5, 10)), chunk("c", (20, 25)), chunk("d", None)]
    scores = np.array([[4, 0, 2, 0], [0, 0, 3, 1]])
    first = run(chunks, scores, 15, ["x", "y"])
    order = [2, 0, 3, 1]
    second = run([chunks[i] for i in order], scores[::-1, order], 15, ["y", "x"])
    assert first == second


def test_budget_keeps_complete_frontiers_and_stops_at_first_crossing():
    chunks = [chunk("a", None, "aa"), chunk("b", None, "bbb"),
              chunk("c", None, "cccc"), chunk("d", None, "d")]
    scores = [[4, 3, 3, 1]]
    exact = run(chunks, scores, 9)
    assert exact["selected_chunk_ids"] == ["a", "b", "c"]
    assert exact["selected_source_characters"] == 9
    assert exact["crossing_frontier_chunk_ids"] == ["d"]
    short = run(chunks, scores, 8)
    assert short["selected_chunk_ids"] == ["a"]
    assert short["crossing_frontier_chunk_ids"] == ["b", "c"]
    assert short["unused_capacity"] == 6  # do not skip to the cheap later frontier
    assert run(chunks, scores, 0)["selected_chunk_ids"] == []
    assert run(chunks, scores)["selected_chunk_ids"] == ["a", "b", "c", "d"]


def test_budget_cannot_split_context_added_at_the_same_frontier():
    chunks = [chunk("a", text="aa"), chunk("b", (5, 10), "bbb")]
    assert run(chunks, [[1, 0]], 4)["selected_chunk_ids"] == []
    assert run(chunks, [[1, 0]], 5)["selected_chunk_ids"] == ["a", "b"]


@pytest.mark.parametrize("budget", [-1, 2.5, True])
def test_invalid_budget_fails_explicitly(budget):
    with pytest.raises(ValueError, match="budget"):
        run([chunk("a")], [[1]], budget)


def test_incomplete_ranged_identity_cannot_silently_recover_context():
    a = chunk("a")
    del a["locator"]["field"]
    with pytest.raises(ValueError, match="identity"):
        run([a], [[1]])

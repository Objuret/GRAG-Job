"""Regression checks for artefact_v1 query-relative level-walk retrieval."""
import argparse
import ast
import hashlib
import inspect
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

import build_tag_clusters as btc
import run
from pipelines import artefact_v1 as arm
from pipelines import artefact_v1_det as det

# The suite exercises the default value model regardless of the shell's HERB_*
# toggles and combine coefficients; each one's behavior is covered by its own
# test class, which patches it on per test. Module-scope patchers pin the
# defaults and restore the shell's environment afterwards, and redirect the
# on-disk caches to a throwaway directory so a test never reads or writes the
# real one.
_MODULE_FLAGS = (patch.object(arm, "CURVE_WALK", False),
                 patch.object(arm, "DOOR_TRACE", False),
                 patch.object(arm, "WALK_GATE", False),
                 patch.object(arm, "FRESH_INTERP", False),
                 patch.object(arm, "NO_REVIEW", False),
                 patch.object(arm, "AGG", "sum"),
                 patch.object(arm, "NORM", "relative"),
                 patch.object(arm, "NORM_SCOPE", "per_path"),
                 patch.object(arm, "W_TAG", 1.0),
                 patch.object(arm, "W_DESC", 1.0),
                 patch.object(arm, "W_SCOPE", 1.0),
                 patch.object(arm, "STR_FACET", 0.0),
                 patch.object(arm, "STR_WCHUNK", 1.0),
                 patch.object(arm, "STR_RELEVANCE", 1.0),
                 patch.object(arm, "STR_DESC_HINT", 1.0),
                 patch.object(arm, "STR_SCOPE_MATCH", 1.0),
                 patch.object(arm, "DESC_HINT_M", 2.0),
                 patch.object(arm, "STR_GUIDE", 0.0),
                 patch.object(arm, "GUIDE_TAU", 0.01))

_CACHE_TMP = None
_CACHE_PATCHES = ()


def setUpModule():
    global _CACHE_TMP, _CACHE_PATCHES
    _CACHE_TMP = tempfile.mkdtemp(prefix="artefact_v1_cache_")
    _CACHE_PATCHES = (
        patch.object(arm, "EMBED_CACHE_DIR", Path(_CACHE_TMP) / "embed"),
        patch.object(arm, "INTERP_CACHE_DIR", Path(_CACHE_TMP) / "interp"),
    )
    for p in _CACHE_PATCHES:
        p.start()
    for p in _MODULE_FLAGS:
        p.start()


def tearDownModule():
    for p in _MODULE_FLAGS:
        p.stop()
    for p in _CACHE_PATCHES:
        p.stop()
    shutil.rmtree(_CACHE_TMP, ignore_errors=True)


def _row(chunk_id, support, facet=1.0, w_chunk=1.0, relevance=1.0):
    """One opened-area chunk row: the tag-support base plus the highest-support
    edge's priority-modifier components, as _open_area returns them."""
    return {
        "chunkId": chunk_id,
        "locator": "{}",
        "relpath": "Salesforce__HERB/products/TestForce.json",
        "sha256": "sha",
        "support": support,
        "facetTerm": facet,
        "w_chunk": w_chunk,
        "relevance": relevance,
    }


class InterpreterBackendTests(unittest.TestCase):
    def test_default_interpreter_uses_claude_haiku(self):
        self.assertEqual(arm.INTERPRET_MODEL, "claude-haiku-4-5")

    def test_interpreter_dispatches_through_claude_cli_lane(self):
        response = {
            "choices": [{"message": {"content": '{"ok": true}'},
                         "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 2, "completion_tokens": 3},
        }
        with patch.object(arm.nim, "_claude_chat", return_value=response) as claude:
            parsed, tokens_in, tokens_out, _ = arm._chat_json(
                arm.INTERPRET_MODEL, "system", "user", 32)
        self.assertEqual(parsed, {"ok": True})
        self.assertEqual((tokens_in, tokens_out), (2, 3))
        claude.assert_called_once()

    def test_partless_interpretation_falls_back_to_the_description(self):
        responses = [({"description": "Find auth docs", "tags": []}, 1, 1, 0.1)]
        with patch.object(arm, "_chat_json", side_effect=responses):
            plan, calls, *_ = arm._interpret("how does auth work?", arm.INTERPRET_MODEL)
        self.assertEqual(calls, 1)
        self.assertEqual([p["t"] for p in plan["parts"]], ["Find auth docs"])


class Pass2ValidationTests(unittest.TestCase):
    @staticmethod
    def _resp(content):
        return {"choices": [{"message": {"content": content},
                             "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 7}}

    def test_a_malformed_scores_payload_retries_then_succeeds(self):
        bad = self._resp('{"scores": [{"t": "a", "facets": {"topic": "high"}}]}')
        good = self._resp('{"scores": [{"t": "a", "facets": {"topic": 0.9}}]}')
        with patch.object(arm.nim, "post", side_effect=[bad, good]) as post:
            parsed, tok_in, tok_out, _ = arm._chat_json(
                "m", "sys", "user", 64, validate=arm._validate_scores)
        self.assertEqual(post.call_count, 2)
        self.assertEqual(parsed["scores"][0]["facets"]["topic"], 0.9)
        self.assertEqual((tok_in, tok_out), (10, 14))  # both attempts counted

    def test_a_twice_malformed_payload_fails_loud_with_its_usage(self):
        bad = self._resp('{"scores": [{"t": "a", "facets": {"topic": null}}]}')
        with patch.object(arm.nim, "post", side_effect=[bad, bad]):
            with self.assertRaises(arm.InterpreterError) as ctx:
                arm._chat_json("m", "sys", "user", 64, validate=arm._validate_scores)
        e = ctx.exception
        self.assertEqual((e.calls, e.tokens_in, e.tokens_out), (2, 10, 14))
        self.assertGreaterEqual(e.time_s, 0.0)

    def test_a_drifted_tag_echo_matches_on_its_cleaned_form(self):
        scored = {f: 0.9 for f in arm.ALL_FACETS}
        responses = [
            ({"description": "d", "tags": ["Auth Flow"], "gate": None}, 1, 1, 0.1),
            ({"scores": [{"t": " AUTH  flow ", "facets": scored}]}, 1, 1, 0.1),
        ]
        with patch.object(arm, "_chat_json", side_effect=responses):
            plan, *_ = arm._interpret("q", arm.INTERPRET_MODEL)
        self.assertEqual(plan["parts"][0]["t"], "auth_flow")
        self.assertEqual(plan["parts"][0]["facets"]["topic"], 0.9)
        self.assertNotIn("unscored", plan)

    def test_unscored_tags_keep_the_neutral_default_and_are_recorded(self):
        responses = [
            ({"description": "d", "tags": ["alpha", "beta"], "gate": None}, 1, 1, 0.1),
            ({"scores": [{"t": "alpha", "facets": {"topic": 1.0}}]}, 1, 1, 0.1),
        ]
        with patch.object(arm, "_chat_json", side_effect=responses):
            plan, *_ = arm._interpret("q", arm.INTERPRET_MODEL)
        by_t = {p["t"]: p["facets"] for p in plan["parts"]}
        self.assertEqual(by_t["alpha"]["topic"], 1.0)
        self.assertEqual(by_t["beta"], {f: 0.2 for f in arm.ALL_FACETS})
        self.assertEqual(plan["unscored"], ["beta"])


class MultiKSupportTests(unittest.TestCase):
    def test_nearer_tags_carry_more_support(self):
        support = arm._multi_k_support(np.array([0.1, 0.2, 0.4]))
        self.assertTrue(support[0] > support[1] > support[2])
        self.assertAlmostEqual(float(support.sum()), 1.0)

    def test_tags_inside_more_levels_accumulate_support(self):
        d = np.full(arm.K_LEVELS[-1], 0.3)
        support = arm._multi_k_support(d)
        self.assertTrue(support[0] > support[-1])

    def test_extended_levels_cover_the_whole_ranked_set(self):
        # A stated fact has no horizon: with extend, members beyond the base
        # level sequence still carry support, less the deeper they sit.
        d = np.full(500, 0.3)
        support = arm._multi_k_support(d, extend=True)
        self.assertTrue(float(support[499]) > 0)
        self.assertTrue(support[0] > support[100] > support[499])

    def test_raw_support_is_a_pure_function_of_distance(self):
        # Unnormalized support depends only on the member's own distance and
        # level coverage — not on who else is in the pool.
        small = arm._multi_k_support(np.array([0.1, 0.2]), normalize=False)
        large = arm._multi_k_support(np.array([0.1, 0.2, 0.3, 0.4]), normalize=False)
        self.assertAlmostEqual(float(small[0]), float(large[0]))
        self.assertAlmostEqual(float(small[0]), len(arm.K_LEVELS) / 0.1 ** 2, places=4)


class UnitNormTests(unittest.TestCase):
    def test_zero_rows_stay_finite(self):
        mat = arm._unit(np.array([[3.0, 4.0], [0.0, 0.0]]))
        self.assertTrue(np.isfinite(mat).all())
        self.assertAlmostEqual(float(np.linalg.norm(mat[0])), 1.0)
        self.assertEqual(list(mat[1]), [0.0, 0.0])

    def test_a_single_vector_scales_to_unit_length(self):
        self.assertEqual(list(arm._unit(np.array([0.0, 2.0]))), [0.0, 1.0])
        self.assertTrue(np.isfinite(arm._unit(np.zeros(3))).all())


class GapBreakTests(unittest.TestCase):
    def test_a_jump_out_of_the_walked_fit_breaks(self):
        self.assertTrue(arm._gap_break([0.1, 0.1, 0.1], 0.5))

    def test_a_gap_inside_the_walked_spread_opens_on(self):
        self.assertFalse(arm._gap_break([0.05, 0.1, 0.15], 0.18))

    def test_steady_gaps_never_break(self):
        self.assertFalse(arm._gap_break([0.1, 0.1, 0.1], 0.1))

    def test_too_few_walked_gaps_carry_no_verdict(self):
        self.assertFalse(arm._gap_break([0.1, 0.1], 5.0))

    def test_noise_sized_gaps_never_break(self):
        self.assertFalse(arm._gap_break([0.0, 0.0, 0.0], 1e-10))


class SufficiencyTests(unittest.TestCase):
    def test_sufficient_at_a_level_keeps_exactly_what_was_seen(self):
        answers = [({"sufficient": False}, 1, 1, 0.1), ({"sufficient": True}, 1, 1, 0.1)]
        with patch.object(arm, "_chat_json", side_effect=answers):
            kept, log, calls, *_ = arm._sufficient_cut("q", ["c"] * 50)
        self.assertEqual(kept, arm.K_LEVELS[1])  # said yes at the second level
        self.assertEqual(calls, 2)
        self.assertEqual([r["sufficient"] for r in log], [False, True])

    def test_never_sufficient_keeps_the_full_retrieval(self):
        with patch.object(arm, "_chat_json",
                          return_value=({"sufficient": False}, 1, 1, 0.1)):
            kept, log, calls, *_ = arm._sufficient_cut("q", ["c"] * 50)
        self.assertEqual(kept, 50)
        self.assertEqual(calls, 3)  # levels 8, 16, 32 — then the hard cap

    def test_review_failure_keeps_the_full_retrieval_and_is_logged(self):
        with patch.object(arm, "_chat_json", side_effect=ValueError("garbage")):
            kept, log, calls, *_ = arm._sufficient_cut("q", ["c"] * 50)
        self.assertEqual(kept, 50)
        self.assertEqual(log[0]["decision"], "fallback")

    def test_a_failed_review_call_still_accounts_its_spent_usage(self):
        err = arm.InterpreterError("boom", calls=2, tokens_in=9, tokens_out=4,
                                   time_s=0.5)
        with patch.object(arm, "_chat_json", side_effect=err):
            kept, log, calls, tok_in, tok_out, time_s = arm._sufficient_cut(
                "q", ["c"] * 50)
        self.assertEqual(kept, 50)
        self.assertEqual((calls, tok_in, tok_out, time_s), (2, 9, 4, 0.5))


class TruncateRebuildTests(unittest.TestCase):
    def test_ids_rebuilt_from_kept_chunks_not_sliced_flat(self):
        import truncate_k
        rec = {"contexts": ["c1", "c2", "c3"],
               "context_ids": ["a", "b", "c", "d", "e"],
               "meta": {"chunk_ids": [["a", "b", "c"], ["d"], ["e"]]}}
        out = truncate_k.truncate_record(rec, 2)
        self.assertEqual(out["contexts"], ["c1", "c2"])
        self.assertEqual(out["context_ids"], ["a", "b", "c", "d"])

    def test_one_to_one_runs_without_per_chunk_ids_slice_the_flat_list(self):
        import truncate_k
        rec = {"contexts": ["c1", "c2"], "context_ids": ["a", "b"], "meta": {}}
        out = truncate_k.truncate_record(rec, 1)
        self.assertEqual(out["context_ids"], ["a"])

    def test_records_not_one_to_one_without_per_chunk_ids_fail_loud(self):
        import truncate_k
        rec = {"id": "q1", "contexts": ["c1", "c2"],
               "context_ids": ["a", "b", "c"], "meta": {}}
        with self.assertRaisesRegex(RuntimeError, "chunk_ids"):
            truncate_k.truncate_record(rec, 1)


class LevelChainTests(unittest.TestCase):
    def _unit(self, rows):
        a = np.array(rows, dtype=np.float64)
        return a / np.linalg.norm(a, axis=1, keepdims=True)

    def test_chain_widens_through_own_family_before_the_far_one(self):
        # Anchor's family (idx 0-2) must be fully added before the far family
        # (idx 3-5) enters, and the far family enters at the largest height.
        embs = self._unit([[1.0, 0.0, 0.0], [0.99, 0.02, 0.0], [0.98, 0.04, 0.0],
                           [0.0, 1.0, 0.0], [0.02, 0.99, 0.0], [0.04, 0.98, 0.0]])
        chain = arm._level_chain(embs, anchor=0)
        self.assertEqual(chain[0], (0.0, [0]))
        added_order = [set(add) for _, add in chain[1:]]
        family = {1, 2}
        crossed = set()
        for add in added_order:
            if add & {3, 4, 5}:
                self.assertEqual(crossed, family)  # own family complete first
            crossed |= add
        self.assertEqual(crossed, {1, 2, 3, 4, 5})
        heights = [h for h, _ in chain]
        self.assertEqual(heights, sorted(heights))

    def test_single_tag_pool_is_one_level(self):
        self.assertEqual(arm._level_chain(np.array([[1.0, 0.0]]), 0), [(0.0, [0])])


class _Session:
    """Scripted Neo4j stand-in: ground rows are keyed by call order (one per
    part); level opens are recorded and answered from a chunk table; the
    affinity and description-surface queries answer from optional tables."""

    def __init__(self, ground_rows, level_chunks, desc_rows=None, affinity_rows=None,
                 scope_rows=None):
        self.ground_rows = list(ground_rows)
        self.level_chunks = level_chunks
        self.desc_rows = list(desc_rows or [])
        self.affinity_rows = affinity_rows or []
        self.scope_rows = scope_rows or []
        self.opened = []
        self.area_cyphers = []

    def run(self, query, **params):
        if query == arm._GROUND_CYPHER:
            return self.ground_rows.pop(0)
        if query == arm._AREA_CHUNKS_CYPHER:
            self.area_cyphers.append(query)
            names = tuple(sorted(t["name"] for t in params["tags"]))
            self.opened.append(names)
            return self.level_chunks.get(names, [])
        if query in (arm._DESC_KNN_CYPHER, arm._DESC_KNN_EMB_CYPHER):
            return self.desc_rows.pop(0) if self.desc_rows else []
        if "UNWIND $names" in query:  # the structural-affinity query
            return self.affinity_rows
        if "vector.similarity.cosine" in query:  # the stated-scope query
            return self.scope_rows
        return []


def _ground_row(name, sim, emb):
    return {"name": name, "sim": sim, "emb": emb}


def _desc_row(chunk_id, sim, **fields):
    row = {"chunkId": chunk_id, "locator": "{}",
           "relpath": "Salesforce__HERB/products/TestForce.json",
           "sha256": "sha", "sim": sim, "desc_emb": [1.0, 0.0],
           "product": None, "section": None, "channel": None,
           "employee_id": None, "years": None}
    row.update(fields)
    return row


_NO_GATE = {"product": None, "section": None, "channel": None,
            "employee_id": None, "years": []}


def _plan(parts, gate=None):
    neutral = {f: 0.5 for f in arm.ALL_FACETS}
    return {"description": "need",
            "parts": [{"t": p, "facets": neutral} for p in parts],
            "gate": gate or dict(_NO_GATE)}


def _fake_embed(texts, kind):
    return [[1.0, 0.0]] * len(texts), 1, 1, 1, 0.01


class LevelWalkTests(unittest.TestCase):
    def test_non_positive_k_fails_before_any_work(self):
        with self.assertRaisesRegex(ValueError, "k must be positive"):
            arm._retrieve(_Session([], {}), _plan(["p"]), k=0)

    def test_walk_widens_own_family_first_and_stops_at_k(self):
        # Anchor opens alone; widening adds the close sibling; the far family
        # never opens because the pool reaches k first.
        ground = [[
            _ground_row("near_a", 0.9, [1.0, 0.0]),
            _ground_row("near_b", 0.89, [0.999, 0.045]),
            _ground_row("far_a", 0.5, [0.0, 1.0]),
            _ground_row("far_b", 0.49, [0.045, 0.999]),
        ]]
        chunks = {
            ("near_a",): [_row("c1", 0.8)],
            ("near_b",): [_row("c2", 0.7)],
            ("far_a", "far_b"): [_row("c-far", 0.9)],
        }
        session = _Session(ground, chunks)
        with patch.object(arm, "_embed", side_effect=_fake_embed):
            rows, _, meta = arm._retrieve(session, _plan(["p"]), k=2)
        self.assertEqual(session.opened, [("near_a",), ("near_b",)])
        self.assertEqual([r["chunkId"] for r in rows], ["c1", "c2"])
        self.assertEqual(len(meta["walk"]), 2)

    def test_walk_reaches_the_far_family_when_k_demands_it(self):
        ground = [[
            _ground_row("near_a", 0.9, [1.0, 0.0]),
            _ground_row("near_b", 0.89, [0.999, 0.045]),
            _ground_row("far_a", 0.5, [0.0, 1.0]),
            _ground_row("far_b", 0.49, [0.045, 0.999]),
        ]]
        chunks = {
            ("near_a",): [_row("c1", 0.8)],
            ("near_b",): [_row("c2", 0.7)],
            ("far_a", "far_b"): [_row("c-far", 0.9)],
        }
        session = _Session(ground, chunks)
        with patch.object(arm, "_embed", side_effect=_fake_embed):
            rows, _, _ = arm._retrieve(session, _plan(["p"]), k=3)
        self.assertIn(("far_a", "far_b"), session.opened)
        self.assertEqual({r["chunkId"] for r in rows}, {"c1", "c2", "c-far"})

    def test_every_part_opens_its_anchor_even_when_k_is_already_met(self):
        ground = [
            [_ground_row("p1_a", 0.9, [1.0, 0.0]),
             _ground_row("p1_b", 0.89, [0.999, 0.045])],
            [_ground_row("p2_a", 0.8, [0.0, 1.0])],
        ]
        chunks = {
            ("p1_a",): [_row("c1", 0.9), _row("c2", 0.8)],
            ("p2_a",): [_row("c-p2", 0.95)],
        }
        session = _Session(ground, chunks)
        with patch.object(arm, "_embed", side_effect=_fake_embed):
            rows, _, meta = arm._retrieve(session, _plan(["p1", "p2"]), k=2)
        self.assertIn(("p2_a",), session.opened)
        self.assertEqual([r["chunkId"] for r in rows], ["c-p2", "c1"])

    def test_chunk_touched_by_several_parts_outranks_a_single_part_grip(self):
        # cx is reached by both parts (its tag base sums 0.4 + 0.4 = 0.8); cy by
        # one part at 0.7 — cx tops the tag pool, cy sits at its floor, so the
        # plan-corroborated chunk wins the ranking.
        ground = [
            [_ground_row("a", 0.9, [1.0, 0.0])],
            [_ground_row("b", 0.8, [0.0, 1.0])],
        ]
        chunks = {
            ("a",): [_row("cx", 0.4)],
            ("b",): [_row("cx", 0.4), _row("cy", 0.7)],
        }
        session = _Session(ground, chunks)
        with patch.object(arm, "_embed", side_effect=_fake_embed):
            rows, _, _ = arm._retrieve(session, _plan(["p1", "p2"]), k=2)
        self.assertEqual([r["chunkId"] for r in rows], ["cx", "cy"])
        self.assertGreater(rows[0]["score"], rows[1]["score"])

    def test_hard_k_caps_pooled_evidence_by_score(self):
        ground = [[_ground_row("a", 0.9, [1.0, 0.0])]]
        chunks = {("a",): [_row("c1", 0.3), _row("c2", 0.9), _row("c3", 0.6)]}
        session = _Session(ground, chunks)
        with patch.object(arm, "_embed", side_effect=_fake_embed):
            rows, _, meta = arm._retrieve(session, _plan(["p"]), k=2)
        self.assertEqual([r["chunkId"] for r in rows], ["c2", "c3"])
        self.assertEqual(meta["retrieved"], 2)

    def test_empty_pool_fails_loud(self):
        session = _Session([[]], {})
        with patch.object(arm, "_embed", side_effect=_fake_embed):
            with self.assertRaisesRegex(RuntimeError, "no tag pool"):
                arm._retrieve(session, _plan(["p"]), k=5)

    def test_structural_affinity_moves_the_anchor_without_zeroing_anything(self):
        # "codename" is semantically farther than "generic", but every one of
        # its edges lands on hint-matching chunks — the (1 + affinity) raise
        # flips the anchor to it. "generic" keeps full semantic support.
        ground = [[
            _ground_row("generic", 0.65, [1.0, 0.0]),
            _ground_row("codename", 0.60, [0.0, 1.0]),
        ]]
        session = _Session(
            ground,
            {("codename",): [_row("c-code", 0.9)], ("generic",): [_row("c-gen", 0.8)]},
            affinity_rows=[{"name": "codename", "total": 10, "hits": 10},
                           {"name": "generic", "total": 10, "hits": 0}],
        )
        gate = dict(_NO_GATE, product="TestForce")
        with patch.object(arm, "_embed", side_effect=_fake_embed):
            rows, _, meta = arm._retrieve(session, _plan(["p"], gate), k=1)
        self.assertEqual(session.opened[0], ("codename",))

    def test_stated_scope_is_a_part_that_nominates_and_corroborates(self):
        # The query states a product: the matching chunk set is its own path.
        # c-both is in scope AND reached by a tag (c-weak keeps it off the tag
        # floor), so its weighted tag + scope sum beats the semantically-stronger
        # but out-of-scope c-sem; the scope-only c-scope still keeps membership.
        ground = [[_ground_row("a", 0.9, [1.0, 0.0])]]
        session = _Session(
            ground,
            {("a",): [_row("c-both", 0.40), _row("c-sem", 0.45), _row("c-weak", 0.30)]},
            affinity_rows=[{"name": "a", "total": 10, "hits": 0}],
            scope_rows=[{"chunkId": "c-both", "locator": "{}",
                         "relpath": "Salesforce__HERB/products/TestForce.json",
                         "sha256": "sha", "matched": 1, "sim": 0.9},
                        {"chunkId": "c-scope", "locator": "{}",
                         "relpath": "Salesforce__HERB/products/TestForce.json",
                         "sha256": "sha", "matched": 1, "sim": 0.8}],
        )
        gate = dict(_NO_GATE, product="TestForce")
        with patch.object(arm, "_embed", side_effect=_fake_embed):
            rows, _, meta = arm._retrieve(session, _plan(["p"], gate), k=4)
        self.assertEqual(rows[0]["chunkId"], "c-both")
        self.assertGreater(rows[0]["score"], rows[1]["score"])
        self.assertIn("stated-scope", [w["part"] for w in meta["walk"]])
        self.assertIn("c-scope", {r["chunkId"] for r in rows})

    def test_description_lookup_contributes_chunks_alongside_the_tag_path(self):
        ground = [[_ground_row("a", 0.9, [1.0, 0.0])]]
        session = _Session(
            ground,
            {("a",): [_row("c1", 0.3)]},
            desc_rows=[[_desc_row("c2", 0.8)]],
        )
        with patch.object(arm, "_embed", side_effect=_fake_embed):
            rows, _, meta = arm._retrieve(session, _plan(["p"]), k=2)
        self.assertEqual({r["chunkId"] for r in rows}, {"c1", "c2"})
        paths = [w.get("path") for w in meta["walk"]]
        self.assertIn("desc", paths)

    def test_a_zero_height_merge_widens_instead_of_anchoring(self):
        # Identical tag embeddings merge at height 0.0; only the chain's level
        # 0 is the anchor, so the zero-height merge waits for the walk and
        # never opens once the pool covers k.
        levels = _levels((0.0, "t0"), (0.0, "t1"), (0.5, "t2"))
        chunks = {("t0",): [_row("c0", 0.5)], ("t1",): [_row("c1", 0.5)],
                  ("t2",): [_row("c2", 0.5)]}
        session = _Session([], chunks)
        with patch.object(arm, "_embed", side_effect=_fake_embed), \
             patch.object(arm, "_part_levels", return_value=levels):
            rows, _, _ = arm._retrieve(session, _plan(["p"]), k=1)
        self.assertEqual(session.opened, [("t0",)])
        self.assertEqual([r["chunkId"] for r in rows], ["c0"])

    def test_the_plan_is_read_not_mutated_and_meta_carries_a_copy(self):
        ground = [[_ground_row("a", 0.9, [1.0, 0.0])]]
        session = _Session(ground, {("a",): [_row("c1", 0.5)]})
        plan = _plan(["p"])
        shaper = lambda names, embs, support: support
        plan["_support_shaper"] = shaper
        with patch.object(arm, "_embed", side_effect=_fake_embed):
            _, _, meta = arm._retrieve(session, plan, k=1)
        self.assertIs(plan["_support_shaper"], shaper)
        self.assertIsNot(meta["plan"], plan)
        self.assertNotIn("_support_shaper", meta["plan"])


def _levels(*heights_and_tags):
    return [{"height": h, "tags": [(name, 1.0)]} for h, name in heights_and_tags]


class CurveWalkTests(unittest.TestCase):
    """The curve walk (HERB_CURVE_WALK=1): one progressive frontier opens the
    cheapest next level anywhere, stops where its own trajectory breaks, and
    the opened areas' distinct chunks are the K under the caller's ceiling."""

    def test_walk_stops_at_the_trajectory_break_and_k_falls_short_of_the_ceiling(self):
        # Four even widening gaps, then a jump: the walk stops before the far
        # level, and K is the walked evidence — not the caller's k.
        levels = _levels((0.0, "t0"), (0.1, "t1"), (0.2, "t2"), (0.3, "t3"),
                         (0.4, "t4"), (2.0, "far"))
        chunks = {(f"t{i}",): [_row(f"c{i}", 0.5)] for i in range(5)}
        chunks[("far",)] = [_row("c-far", 0.9)]
        session = _Session([], chunks)
        with patch.object(arm, "_embed", side_effect=_fake_embed), \
             patch.object(arm, "_part_levels", return_value=levels), \
             patch.object(arm, "CURVE_WALK", True):
            rows, _, meta = arm._retrieve(session, _plan(["p"]), k=10)
        self.assertNotIn(("far",), session.opened)
        self.assertEqual({r["chunkId"] for r in rows},
                         {"c0", "c1", "c2", "c3", "c4"})
        self.assertEqual(meta["curve_walk"],
                         {"pool": 5, "semantic": 5, "kept": 5,
                          "stopped": True, "opened": 4})

    def test_a_steady_trajectory_opens_everything_under_the_ceiling(self):
        levels = _levels((0.0, "t0"), (0.1, "t1"), (0.2, "t2"), (0.3, "t3"),
                         (0.4, "t4"), (0.5, "t5"))
        chunks = {(f"t{i}",): [_row(f"c{i}", 0.5)] for i in range(6)}
        session = _Session([], chunks)
        with patch.object(arm, "_embed", side_effect=_fake_embed), \
             patch.object(arm, "_part_levels", return_value=levels), \
             patch.object(arm, "CURVE_WALK", True):
            rows, _, meta = arm._retrieve(session, _plan(["p"]), k=10)
        self.assertEqual(len(rows), 6)
        self.assertFalse(meta["curve_walk"]["stopped"])

    def test_description_areas_walk_the_same_frontier_and_count_toward_k(self):
        # The description neighborhood clusters like a tag pool: its anchor
        # chunk opens with the anchors and its dendrogram levels join the
        # frontier, so its chunks are walked evidence, not a flat lookup.
        levels = _levels((0.0, "t0"))
        session = _Session(
            [], {("t0",): [_row("c1", 0.5)]},
            desc_rows=[[_desc_row("c-near", 0.9, desc_emb=[1.0, 0.0]),
                        _desc_row("c-kin", 0.89, desc_emb=[0.999, 0.045])]],
        )
        plan = _plan(["p"])
        plan["description"] = "p"  # no whole-need door: one desc area only
        with patch.object(arm, "_embed", side_effect=_fake_embed), \
             patch.object(arm, "_part_levels", return_value=levels), \
             patch.object(arm, "CURVE_WALK", True):
            rows, _, meta = arm._retrieve(session, plan, k=10)
        self.assertEqual({r["chunkId"] for r in rows}, {"c1", "c-near", "c-kin"})
        desc_events = [w for w in meta["walk"] if w.get("path") == "desc"]
        self.assertEqual(len(desc_events), 2)  # anchor chunk, then the merge
        self.assertIn("height", desc_events[1])
        self.assertEqual(meta["curve_walk"]["semantic"], 3)

    def test_stated_scope_corroborates_and_competes_but_never_sets_k(self):
        # Scope vouches for many chunks; K stays the walked semantic count.
        # The scope-corroborated walked chunk wins the slot; the scope-only
        # chunk stays outside K.
        levels = _levels((0.0, "t0"))
        session = _Session(
            [], {("t0",): [_row("c1", 0.5)]},
            scope_rows=[{"chunkId": "c1", "locator": "{}",
                         "relpath": "Salesforce__HERB/products/TestForce.json",
                         "sha256": "sha", "matched": 1, "sim": 0.9},
                        {"chunkId": "c-scope", "locator": "{}",
                         "relpath": "Salesforce__HERB/products/TestForce.json",
                         "sha256": "sha", "matched": 1, "sim": 0.8}],
        )
        plan = _plan(["p"], dict(_NO_GATE, product="TestForce"))
        plan["description"] = "p"
        with patch.object(arm, "_embed", side_effect=_fake_embed), \
             patch.object(arm, "_part_levels", return_value=levels), \
             patch.object(arm, "CURVE_WALK", True):
            rows, _, meta = arm._retrieve(session, plan, k=10)
        self.assertEqual([r["chunkId"] for r in rows], ["c1"])
        self.assertEqual(meta["curve_walk"]["kept"], 1)
        self.assertEqual(meta["curve_walk"]["pool"], 2)  # scope chunk pooled...
        self.assertEqual(meta["curve_walk"]["semantic"], 1)  # ...but not counted

    def test_scope_only_evidence_under_the_walk_fails_loud(self):
        # The opened semantic areas pull nothing while stated scope fills the
        # pool: the arm raises.
        levels = _levels((0.0, "t0"))
        session = _Session(
            [], {},
            scope_rows=[{"chunkId": "c-scope", "locator": "{}",
                         "relpath": "Salesforce__HERB/products/TestForce.json",
                         "sha256": "sha", "matched": 1, "sim": 0.8}],
        )
        plan = _plan(["p"], dict(_NO_GATE, product="TestForce"))
        plan["description"] = "p"
        with patch.object(arm, "_embed", side_effect=_fake_embed), \
             patch.object(arm, "_part_levels", return_value=levels), \
             patch.object(arm, "CURVE_WALK", True):
            with self.assertRaisesRegex(RuntimeError, "stated scope"):
                arm._retrieve(session, plan, k=10)

    def test_whole_need_description_is_its_own_area(self):
        levels = _levels((0.0, "t0"))
        session = _Session(
            [], {("t0",): [_row("c1", 0.3)]},
            desc_rows=[[_desc_row("c-part", 0.9)],
                       [_desc_row("c-need", 0.85)]],
        )
        with patch.object(arm, "_embed", side_effect=_fake_embed), \
             patch.object(arm, "_part_levels", return_value=levels), \
             patch.object(arm, "CURVE_WALK", True):
            rows, _, meta = arm._retrieve(session, _plan(["p"]), k=10)
        self.assertIn("c-need", {r["chunkId"] for r in rows})
        self.assertIn("description", [w["part"] for w in meta["walk"]])

    def test_description_equal_to_a_parts_readable_form_opens_no_second_area(self):
        # The part embeds as its readable form ("auth_flow" -> "auth flow"):
        # a description equal to that form is the same area, not a new one.
        levels = _levels((0.0, "t0"))
        session = _Session([], {("t0",): [_row("c1", 0.3)]},
                           desc_rows=[[_desc_row("c-part", 0.9)]])
        plan = _plan(["auth_flow"])
        plan["description"] = "auth flow"
        with patch.object(arm, "_embed", side_effect=_fake_embed), \
             patch.object(arm, "_part_levels", return_value=levels), \
             patch.object(arm, "CURVE_WALK", True):
            rows, _, meta = arm._retrieve(session, plan, k=10)
        self.assertNotIn("description", [w["part"] for w in meta["walk"]])

    def test_tag_and_description_events_interleave_on_one_frontier(self):
        # Tag levels at 0.05 and 0.3, a description merge at 0.1: the frontier
        # opens them height-merged across the two spaces, not space-by-space.
        levels = _levels((0.0, "t0"), (0.05, "t1"), (0.3, "t2"))
        chunks = {(f"t{i}",): [_row(f"c{i}", 0.5)] for i in range(3)}
        session = _Session(
            [], chunks,
            desc_rows=[[_desc_row("c-d0", 0.9, desc_emb=[1.0, 0.0]),
                        _desc_row("c-d1", 0.85, desc_emb=[0.9, 0.43589])]],
        )
        plan = _plan(["p"])
        plan["description"] = "p"
        with patch.object(arm, "_embed", side_effect=_fake_embed), \
             patch.object(arm, "_part_levels", return_value=levels), \
             patch.object(arm, "CURVE_WALK", True):
            _, _, meta = arm._retrieve(session, plan, k=10)
        widened = [(w["path"], w["height"])
                   for w in meta["walk"] if w.get("height", 0.0) > 0.0]
        self.assertEqual(widened, [("tag", 0.05), ("desc", 0.1), ("tag", 0.3)])

    def test_part_levels_carry_raw_support_under_the_walk(self):
        # Under the curve walk tag support is the raw inverse-square weight —
        # not a distribution over the pool — so tag and description values
        # share one scale.
        ground = [[_ground_row("near", 0.9, [1.0, 0.0]),
                   _ground_row("far", 0.8, [0.0, 1.0])]]
        session = _Session(ground, {})
        vec = np.array([1.0, 0.0])
        with patch.object(arm, "CURVE_WALK", True):
            levels = arm._part_levels(session, {"t": "p"}, vec, dict(_NO_GATE))
        supports = [s for lv in levels for _, s in lv["tags"]]
        self.assertGreater(max(supports), 1.0)
        self.assertAlmostEqual(max(supports), len(arm.K_LEVELS) / 0.1 ** 2, places=2)


class DoorTraceTests(unittest.TestCase):
    def test_trace_carries_every_pooled_chunk_with_its_door_values(self):
        # c1 comes through a tag, c2 through the description surface, c-scope
        # through stated scope only — the trace shows each chunk's doors and
        # covers the whole pool, kept or not.
        ground = [[_ground_row("a", 0.9, [1.0, 0.0])]]
        session = _Session(
            ground,
            {("a",): [_row("c1", 0.3)]},
            desc_rows=[[_desc_row("c2", 0.8)]],
            scope_rows=[{"chunkId": "c-scope", "locator": "{}",
                         "relpath": "Salesforce__HERB/products/TestForce.json",
                         "sha256": "sha", "matched": 1, "sim": 0.8}],
        )
        gate = dict(_NO_GATE, product="TestForce")
        with patch.object(arm, "_embed", side_effect=_fake_embed), \
             patch.object(arm, "DOOR_TRACE", True):
            rows, _, meta = arm._retrieve(session, _plan(["p"], gate), k=2)
        trace = {t["chunkId"]: t for t in meta["door_trace"]}
        self.assertEqual(set(trace), {"c1", "c2", "c-scope"})
        self.assertGreater(trace["c1"]["tag"], 0.0)
        self.assertEqual(trace["c1"]["desc"], 0.0)
        self.assertGreater(trace["c2"]["desc"], 0.0)
        self.assertGreater(trace["c-scope"]["scope"], 0.0)
        self.assertEqual(trace["c-scope"]["tag"], 0.0)
        for t in trace.values():
            self.assertIn("locator", t)
            self.assertIn("sha256", t)


class RetrievalFlagTests(unittest.TestCase):
    def test_the_boolean_flags_parse_strict_env_one(self):
        src = inspect.getsource(arm)
        for env, const in (("HERB_CURVE_WALK", "CURVE_WALK"),
                           ("HERB_DOOR_TRACE", "DOOR_TRACE"),
                           ("HERB_WALK_GATE", "WALK_GATE"),
                           ("HERB_FRESH_INTERP", "FRESH_INTERP"),
                           ("HERB_NO_REVIEW", "NO_REVIEW")):
            self.assertIn(f'{const} = os.environ.get("{env}") == "1"', src)

    def test_the_combine_coefficients_read_from_the_environment(self):
        src = inspect.getsource(arm)
        for env, const in (("HERB_W_TAG", "W_TAG"), ("HERB_W_DESC", "W_DESC"),
                           ("HERB_W_SCOPE", "W_SCOPE"),
                           ("HERB_STR_FACET", "STR_FACET"),
                           ("HERB_STR_WCHUNK", "STR_WCHUNK"),
                           ("HERB_STR_RELEVANCE", "STR_RELEVANCE"),
                           ("HERB_STR_DESC_HINT", "STR_DESC_HINT"),
                           ("HERB_STR_SCOPE_MATCH", "STR_SCOPE_MATCH"),
                           ("HERB_DESC_HINT_M", "DESC_HINT_M"),
                           ("HERB_STR_GUIDE", "STR_GUIDE"),
                           ("HERB_GUIDE_TAU", "GUIDE_TAU"),
                           ("HERB_GUIDE_M", "GUIDE_M"),
                           ("HERB_GUIDE_LAMBDA", "GUIDE_LAMBDA")):
            self.assertIn(f'{const} = _env_float("{env}"', src)

    def test_the_guide_integer_config_reads_strict_from_the_environment(self):
        src = inspect.getsource(arm)
        for env, const in (("HERB_GUIDE_C", "GUIDE_C"),
                           ("HERB_GUIDE_SEED", "GUIDE_SEED")):
            self.assertIn(f'{const} = _env_int("{env}"', src)
        self.assertEqual(arm._env_int("HERB_GUIDE_C_UNSET_XYZ", 96), 96)
        with patch.dict(os.environ, {"HERB_GUIDE_C_BAD_XYZ": "many"}):
            with self.assertRaises(ValueError):
                arm._env_int("HERB_GUIDE_C_BAD_XYZ", 96)

    def test_both_legs_manifests_carry_the_combine_coefficients(self):
        for flags in (arm.RETRIEVAL_FLAGS, det.RETRIEVAL_FLAGS):
            for name in ("HERB_CURVE_WALK", "HERB_WALK_GATE", "HERB_NO_REVIEW",
                         "HERB_AGG", "HERB_NORM", "HERB_NORM_SCOPE", "HERB_W_TAG",
                         "HERB_W_DESC", "HERB_W_SCOPE", "HERB_STR_FACET",
                         "HERB_STR_WCHUNK", "HERB_STR_RELEVANCE",
                         "HERB_STR_DESC_HINT", "HERB_STR_SCOPE_MATCH",
                         "HERB_DESC_HINT_M",
                         "HERB_STR_GUIDE", "HERB_GUIDE_TAU", "HERB_GUIDE_C",
                         "HERB_GUIDE_M", "HERB_GUIDE_LAMBDA", "HERB_GUIDE_SEED"):
                self.assertIn(name, flags)

    def test_the_mode_switches_reject_an_unknown_value(self):
        # the modes fail loud at import, so a typo can never silently fall back
        for name, val in (("HERB_AGG", "sum"), ("HERB_NORM", "relative"),
                          ("HERB_NORM_SCOPE", "per_path")):
            self.assertIn(name, arm.RETRIEVAL_FLAGS)
            self.assertEqual(arm.RETRIEVAL_FLAGS[name], val)

    def test_the_facet_strength_defaults_inert(self):
        self.assertEqual(arm._env_float("HERB_STR_FACET_UNSET_XYZ", arm.STR_FACET),
                         arm.STR_FACET)


class RunFlagTests(unittest.TestCase):
    def test_a_flag_spec_parses_to_its_name_value_pair(self):
        self.assertEqual(run._flag("HERB_WALK_GATE=1"), ("HERB_WALK_GATE", "1"))
        self.assertEqual(run._flag("HERB_STR_GUIDE=1.0"), ("HERB_STR_GUIDE", "1.0"))
        self.assertEqual(run._flag("A=b=c"), ("A", "b=c"))  # the value keeps its '='
        self.assertEqual(run._flag("HERB_X="), ("HERB_X", ""))  # blank = unset = the pipeline's true default

    def test_a_malformed_flag_spec_fails_at_parse(self):
        for bad in ("HERB_WALK_GATE", "=1", "="):
            with self.assertRaises(argparse.ArgumentTypeError):
                run._flag(bad)

    def test_flags_land_in_this_process_environment_only(self):
        with patch.dict(os.environ, {}, clear=False):
            run._apply_flags([("HERB_RUN_FLAG_TEST_XYZ", "1")])
            self.assertEqual(os.environ["HERB_RUN_FLAG_TEST_XYZ"], "1")
        self.assertNotIn("HERB_RUN_FLAG_TEST_XYZ", os.environ)

    def test_a_blank_value_unsets_a_session_env_var(self):
        with patch.dict(os.environ, {"HERB_RUN_FLAG_TEST_XYZ": "1"}, clear=False):
            run._apply_flags([("HERB_RUN_FLAG_TEST_XYZ", "")])
            self.assertNotIn("HERB_RUN_FLAG_TEST_XYZ", os.environ)

    def test_flags_apply_before_any_pipeline_or_eval_import(self):
        # the apply site precedes the pipeline import, main's eval import, and
        # the _rejudge call whose body holds the rejudge path's eval import;
        # run.py's module scope imports from neither package
        src = inspect.getsource(run.main)
        apply_at = src.index("_apply_flags(args.flag)")
        self.assertLess(apply_at, src.index("importlib.import_module"))
        self.assertLess(apply_at, src.index("import eval.ragas"))
        self.assertLess(apply_at, src.index("_rejudge(args)"))
        self.assertIn("import eval.ragas", inspect.getsource(run._rejudge))
        for node in ast.parse(inspect.getsource(run)).body:
            names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                     else [node.module or ""] if isinstance(node, ast.ImportFrom)
                     else [])
            for name in names:
                self.assertFalse(name in ("pipelines", "eval")
                                 or name.startswith(("pipelines.", "eval.")),
                                 f"module-scope import {name} defeats --flag")


class NormalizeTests(unittest.TestCase):
    def test_min_max_spans_zero_to_one(self):
        out = arm._minmax({"a": 2.0, "b": 4.0, "c": 6.0})
        self.assertEqual((out["a"], out["c"]), (0.0, 1.0))
        self.assertAlmostEqual(out["b"], 0.5)

    def test_a_single_scale_point_maps_every_member_to_one(self):
        self.assertEqual(arm._minmax({"a": 3.0, "b": 3.0}), {"a": 1.0, "b": 1.0})

    def test_an_empty_pool_normalizes_to_nothing(self):
        self.assertEqual(arm._minmax({}), {})


class ModifierLerpTests(unittest.TestCase):
    def test_strength_zero_is_inert(self):
        self.assertEqual(arm._mod(0.0, 0.0), 1.0)
        self.assertEqual(arm._mod(5.0, 0.0), 1.0)

    def test_strength_one_is_the_raw_factor(self):
        self.assertEqual(arm._mod(2.0, 1.0), 2.0)
        self.assertAlmostEqual(arm._mod(0.4, 1.0), 0.4)

    def test_strength_interpolates_between_inert_and_full(self):
        self.assertAlmostEqual(arm._mod(2.0, 0.5), 1.5)
        self.assertAlmostEqual(arm._mod(0.0, 0.25), 0.75)

    def test_a_strength_past_one_clamps_at_zero_without_flipping_sign(self):
        # w_chunk 0.3 at strength 1.5 would be 1 + 1.5*(0.3-1) = -0.05; clamped
        # to 0 so a damped chunk never sorts below a zero-scored one.
        self.assertEqual(arm._mod(0.3, 1.5), 0.0)
        self.assertEqual(arm._mod(0.0, 3.0), 0.0)
        self.assertGreaterEqual(arm._mod(0.05, 5.0), 0.0)


class CombineTests(unittest.TestCase):
    """The three paths score on one scale: min-max base per path, strength-lerp
    modifiers, weighted sum over the union."""

    def test_a_zero_path_weight_removes_that_paths_influence(self):
        # c-desc is found only through the description lookup; with W_DESC=0 it
        # keeps union membership but contributes no value.
        ground = [[_ground_row("a", 0.9, [1.0, 0.0])]]
        session = _Session(ground, {("a",): [_row("c-tag", 0.5)]},
                           desc_rows=[[_desc_row("c-desc", 0.8)]])
        with patch.object(arm, "_embed", side_effect=_fake_embed), \
             patch.object(arm, "W_DESC", 0.0):
            rows, _, _ = arm._retrieve(session, _plan(["p"]), k=2)
        by_id = {r["chunkId"]: r["score"] for r in rows}
        self.assertEqual(by_id["c-desc"], 0.0)      # found, but no influence
        self.assertGreater(by_id["c-tag"], 0.0)

    def test_the_facet_modifier_is_inert_at_the_default_strength(self):
        # Equal tag support, different facet agreement: at STR_FACET=0 the facet
        # term cannot separate them — both sit at the pool max.
        ground = [[_ground_row("a", 0.9, [1.0, 0.0])]]
        session = _Session(ground, {("a",): [_row("c-hi", 0.5, facet=1.0),
                                             _row("c-lo", 0.5, facet=0.2)]})
        with patch.object(arm, "_embed", side_effect=_fake_embed):
            rows, _, _ = arm._retrieve(session, _plan(["p"]), k=2)
        self.assertEqual({r["score"] for r in rows}, {1.0})

    def test_a_full_facet_strength_lets_the_facet_term_damp(self):
        ground = [[_ground_row("a", 0.9, [1.0, 0.0])]]
        session = _Session(ground, {("a",): [_row("c-hi", 0.5, facet=1.0),
                                             _row("c-lo", 0.5, facet=0.2)]})
        with patch.object(arm, "_embed", side_effect=_fake_embed), \
             patch.object(arm, "STR_FACET", 1.0):
            rows, _, _ = arm._retrieve(session, _plan(["p"]), k=2)
        self.assertEqual(rows[0]["chunkId"], "c-hi")
        self.assertGreater(rows[0]["score"], rows[1]["score"])

    @staticmethod
    def _hint_session():
        # a tag chunk plus a three-row description pool whose middle row carries
        # the stated product: min-max leaves the hinted chunk between the pool's
        # floor and its closest match, where the modifier can move it
        ground = [[_ground_row("a", 0.9, [1.0, 0.0])]]
        return _Session(
            ground,
            {("a",): [_row("c-tag", 0.5)]},
            desc_rows=[[_desc_row("c-top", 0.9),
                        _desc_row("c-hint", 0.88, product="TestForce"),
                        _desc_row("c-floor", 0.5)]],
        )

    def _hint_rows(self, hint_m, strength=1.0):
        gate = dict(_NO_GATE, product="TestForce")
        with patch.object(arm, "_embed", side_effect=_fake_embed), \
             patch.object(arm, "DESC_HINT_M", hint_m), \
             patch.object(arm, "STR_DESC_HINT", strength):
            rows, _, _ = arm._retrieve(self._hint_session(), _plan(["p"], gate), k=4)
        return rows

    def test_the_hint_factor_scales_a_matching_description_chunks_score(self):
        # DESC_HINT_M is the factor STR_DESC_HINT grades: at full strength the
        # hinted chunk scores its normalized base times that factor, while the
        # unhinted rows of the same pool keep their scores.
        at_one = {r["chunkId"]: r["score"] for r in self._hint_rows(1.0)}
        at_two = {r["chunkId"]: r["score"] for r in self._hint_rows(2.0)}
        self.assertGreater(at_two["c-hint"], at_one["c-hint"])
        self.assertAlmostEqual(at_two["c-hint"], 2.0 * at_one["c-hint"], places=3)
        self.assertEqual(at_two["c-top"], at_one["c-top"])

    def test_the_hint_factor_moves_a_matching_chunk_past_the_pools_best(self):
        # mid-pool on distance: at 2.0 the hinted chunk outranks the pool's
        # closest description match; at 0.0 the modifier takes its score away
        # and it ranks below that same chunk.
        lifted = [r["chunkId"] for r in self._hint_rows(2.0)]
        removed = [r["chunkId"] for r in self._hint_rows(0.0)]
        self.assertLess(lifted.index("c-hint"), lifted.index("c-top"))
        self.assertGreater(removed.index("c-hint"), removed.index("c-top"))

    def test_the_hint_factor_is_inert_at_zero_hint_strength(self):
        # STR_DESC_HINT=0 holds the modifier at 1.0 whatever the factor is, so
        # DESC_HINT_M reaches neither the score nor the ranking.
        quiet = {r["chunkId"]: r["score"] for r in self._hint_rows(1.0, strength=0.0)}
        loud = {r["chunkId"]: r["score"] for r in self._hint_rows(4.0, strength=0.0)}
        self.assertEqual(loud, quiet)
        self.assertLess(loud["c-hint"], loud["c-top"])


class CombineModeTests(unittest.TestCase):
    """HERB_AGG / HERB_NORM / HERB_NORM_SCOPE select cells of the combine grid;
    the defaults reproduce the sum + per-path min-max combine."""

    @staticmethod
    def _two_part_session():
        # cx reached by both parts (0.4 each), cy by one part at 0.7
        ground = [[_ground_row("a", 0.9, [1.0, 0.0])],
                  [_ground_row("b", 0.8, [0.0, 1.0])]]
        chunks = {("a",): [_row("cx", 0.4)],
                  ("b",): [_row("cx", 0.4), _row("cy", 0.7)]}
        return _Session(ground, chunks)

    def test_agg_sum_lifts_a_corroborated_chunk(self):
        with patch.object(arm, "_embed", side_effect=_fake_embed):  # AGG=sum default
            rows, _, _ = arm._retrieve(self._two_part_session(), _plan(["p1", "p2"]), k=2)
        self.assertEqual(rows[0]["chunkId"], "cx")

    def test_agg_max_keeps_the_single_best_contribution(self):
        with patch.object(arm, "_embed", side_effect=_fake_embed), \
             patch.object(arm, "AGG", "max"):
            rows, _, _ = arm._retrieve(self._two_part_session(), _plan(["p1", "p2"]), k=2)
        self.assertEqual(rows[0]["chunkId"], "cy")  # 0.4 max, no corroboration lift

    @staticmethod
    def _two_range_session():
        # tag path strong (100, 50 via _row); description path weak (support from
        # a far sim), so the two paths sit on very different raw ranges
        ground = [[_ground_row("a", 0.9, [1.0, 0.0])]]
        return _Session(
            ground,
            {("a",): [_row("c-strong", 100.0), _row("c-mid", 50.0)]},
            desc_rows=[[_desc_row("c-weakbest", 0.2), _desc_row("c-weak", 0.0)]],
        )

    def test_relative_per_path_stretches_each_paths_own_range(self):
        with patch.object(arm, "_embed", side_effect=_fake_embed):  # per_path default
            rows, _, _ = arm._retrieve(self._two_range_session(), _plan(["p"]), k=4)
        order = [r["chunkId"] for r in rows]
        # the weak description best is stretched to 1.0, above the tag floor
        self.assertLess(order.index("c-weakbest"), order.index("c-mid"))

    def test_relative_global_ranks_on_the_shared_range(self):
        with patch.object(arm, "_embed", side_effect=_fake_embed), \
             patch.object(arm, "NORM_SCOPE", "global"):
            rows, _, _ = arm._retrieve(self._two_range_session(), _plan(["p"]), k=4)
        order = [r["chunkId"] for r in rows]
        # on one shared range the mid tag chunk outranks the weak description best
        self.assertLess(order.index("c-mid"), order.index("c-weakbest"))

    def test_absolute_is_pool_independent_and_order_preserving(self):
        ref = arm._ABS_REF
        self.assertAlmostEqual(arm._absolute(8.0, ref), 8.0 / (8.0 + ref))
        self.assertLess(arm._absolute(4.0, ref), arm._absolute(8.0, ref))  # order
        self.assertLess(arm._absolute(8.0, ref), 1.0)                      # < 1

    def test_absolute_equalizes_equal_distance_across_paths(self):
        # a top chunk at the same distance earns the same absolute score whether
        # it came through the 4-level tag/desc path or a deeper extended scope
        # path: base scales with the level count, and so does the reference
        tag_levels = len(arm.K_LEVELS)
        scope_levels = tag_levels + 3          # scope extended three levels deeper
        inv_d2 = 1.0 / 0.3 ** 2                # 1 / distance^2 for some distance
        tag_top = tag_levels * inv_d2          # top chunk, four levels
        scope_top = scope_levels * inv_d2      # top chunk, seven levels, same distance
        self.assertAlmostEqual(
            arm._absolute(tag_top, tag_levels * arm._ABS_UNIT),
            arm._absolute(scope_top, scope_levels * arm._ABS_UNIT))

    def test_scope_level_count_extends_with_the_matching_set(self):
        self.assertEqual(arm._n_levels(2), len(arm.K_LEVELS))       # no extension
        self.assertEqual(arm._n_levels(arm.K_LEVELS[-1]), len(arm.K_LEVELS))
        self.assertEqual(arm._n_levels(arm.K_LEVELS[-1] + 1), len(arm.K_LEVELS) + 1)

    def test_absolute_keeps_a_weak_only_pools_best_below_one(self):
        # a tag pool of only weak matches: relative would promote its best to
        # 1.0; absolute keeps it low.
        ground = [[_ground_row("a", 0.9, [1.0, 0.0])]]
        session = _Session(ground, {("a",): [_row("c-hi", 8.0), _row("c-lo", 4.0)]})
        with patch.object(arm, "_embed", side_effect=_fake_embed), \
             patch.object(arm, "NORM", "absolute"):
            rows, _, _ = arm._retrieve(session, _plan(["p"]), k=2)
        by_id = {r["chunkId"]: r["score"] for r in rows}
        self.assertLess(by_id["c-hi"], 1.0)
        self.assertGreater(by_id["c-hi"], by_id["c-lo"])

    def test_absolute_removes_the_scope_extension_inflation(self):
        # a tag chunk and the top stated-scope chunk sit at the same cosine
        # distance; under absolute they earn the same score even though scope
        # stacks an extra level through extend
        ground = [[_ground_row("a", 0.9, [1.0, 0.0])]]
        tag_support = len(arm.K_LEVELS) / 0.3 ** 2   # a 4-level top chunk at dist 0.3
        scope_rows = [{"chunkId": f"s{i:03d}", "locator": "{}",
                       "relpath": "Salesforce__HERB/products/TestForce.json",
                       "sha256": "sha", "matched": 1, "sim": 0.7}  # dist 0.3
                      for i in range(arm.K_LEVELS[-1] + 1)]          # extends one level
        session = _Session(ground, {("a",): [_row("c-tag", tag_support)]},
                           affinity_rows=[{"name": "a", "total": 10, "hits": 0}],
                           scope_rows=scope_rows)
        gate = dict(_NO_GATE, product="TestForce")
        with patch.object(arm, "_embed", side_effect=_fake_embed), \
             patch.object(arm, "NORM", "absolute"):
            rows, _, _ = arm._retrieve(session, _plan(["p"], gate), k=200)
        by_id = {r["chunkId"]: r["score"] for r in rows}
        self.assertAlmostEqual(by_id["c-tag"], by_id["s000"], places=4)

    def test_none_ranks_on_the_raw_unnormalized_base(self):
        # No normalization: paths keep raw magnitude, so a close description
        # match (support in the tens) outranks the tag chunk relative would have
        # tied it with — the reference cell, the old cross-scale behavior.
        ground = [[_ground_row("a", 0.9, [1.0, 0.0])]]
        session = _Session(ground, {("a",): [_row("c-aaa", 9.0), _row("c-bbb", 3.0)]},
                           desc_rows=[[_desc_row("c-desc", 0.4)]])
        with patch.object(arm, "_embed", side_effect=_fake_embed), \
             patch.object(arm, "NORM", "none"):
            rows, _, _ = arm._retrieve(session, _plan(["p"]), k=3)
        self.assertEqual(rows[0]["chunkId"], "c-desc")

    def test_defaults_reproduce_the_sum_per_path_minmax_combine(self):
        self.assertEqual((arm.AGG, arm.NORM, arm.NORM_SCOPE),
                         ("sum", "relative", "per_path"))


class EmbedCacheTests(unittest.TestCase):
    def test_a_miss_embeds_and_a_hit_serves_without_a_call(self):
        with patch.object(arm, "_embed", side_effect=_fake_embed) as emb:
            m1, calls1, *_ = arm._embed_cached(["alpha", "beta"], "query")
            m2, calls2, *_ = arm._embed_cached(["alpha", "beta"], "query")
        self.assertEqual(emb.call_count, 1)   # the second call is fully cached
        self.assertGreater(calls1, 0)
        self.assertEqual(calls2, 0)           # a hit reports zero NIM cost
        self.assertTrue(np.array_equal(m1, m2))

    def test_a_new_model_id_misses(self):
        with patch.object(arm, "_embed", side_effect=_fake_embed):
            arm._embed_cached(["gamma"], "query")  # populate under the real id
        with patch.object(arm, "EMBED_MODEL", "vendor/other-embedder"), \
             patch.object(arm, "_embed", side_effect=_fake_embed) as emb:
            _, calls, *_ = arm._embed_cached(["gamma"], "query")
        self.assertEqual(emb.call_count, 1)
        self.assertGreater(calls, 0)


class InterpCacheTests(unittest.TestCase):
    _PLAN = {"description": "d", "parts": [{"t": "x", "facets": {}}], "gate": {}}

    def test_a_hit_returns_the_cached_plan_without_a_call(self):
        with patch.object(arm, "_interpret",
                          return_value=(self._PLAN, 2, 5, 3, 1.0)) as interp:
            first = arm._interpret_cached("cache me", "m")
            second = arm._interpret_cached("cache me", "m")
        self.assertEqual(interp.call_count, 1)      # the second read from disk
        self.assertEqual(first[0], self._PLAN)
        self.assertEqual(second[0], self._PLAN)
        self.assertEqual(second[1:], (0, 0, 0, 0.0))  # a hit spends nothing

    def test_fresh_interp_bypasses_the_cache(self):
        with patch.object(arm, "_interpret",
                          return_value=(self._PLAN, 1, 1, 1, 0.1)) as interp:
            arm._interpret_cached("fresh me", "m")           # populate
            with patch.object(arm, "FRESH_INTERP", True):
                arm._interpret_cached("fresh me", "m")       # re-run, refresh
                arm._interpret_cached("fresh me", "m")
        self.assertEqual(interp.call_count, 3)

    def test_a_model_change_misses(self):
        with patch.object(arm, "_interpret",
                          return_value=(self._PLAN, 1, 1, 1, 0.1)) as interp:
            arm._interpret_cached("switch me", "model-a")
            arm._interpret_cached("switch me", "model-b")
        self.assertEqual(interp.call_count, 2)

    def test_the_key_folds_in_the_interpreter_signature(self):
        # the interpreter's prompts and code enter the key through _INTERP_SIG,
        # so an edit to either (which changes the signature) yields a new key
        base = arm._interp_key("q", "m")
        with patch.object(arm, "_INTERP_SIG", "a-different-signature"):
            changed = arm._interp_key("q", "m")
        self.assertNotEqual(base, changed)

    @staticmethod
    def _sig(extract_src):
        return hashlib.sha256("\x00".join([
            arm._PASS1_SYSTEM, arm._PASS2_SYSTEM, repr(sorted(arm.FILLER)),
            repr(arm.ALL_FACETS), inspect.getsource(arm._interpret),
            inspect.getsource(arm._clean_tag), inspect.getsource(arm._parse_gate),
            inspect.getsource(arm._validate_scores),
            extract_src]).encode("utf-8")).hexdigest()

    def test_the_interpreter_signature_covers_prompts_facets_and_code(self):
        # _INTERP_SIG is exactly the sha256 over the prompts, the facet set, the
        # filler set and the interpreter functions' source (the JSON extractor
        # included) — so editing any of them changes it
        self.assertEqual(arm._INTERP_SIG,
                         self._sig(inspect.getsource(arm._extract_json)))

    def test_the_key_changes_when_the_json_extractor_source_changes(self):
        # _extract_json is a transitive interpreter dependency folded into the
        # signature; a different source for it yields a different signature
        self.assertNotEqual(self._sig(inspect.getsource(arm._extract_json)),
                            self._sig("def _extract_json(text): return {}"))


class WalkGateTests(unittest.TestCase):
    """HERB_WALK_GATE=1: the flat-regime widening gate counts only the chunks
    the tag areas reached, so description lookups and stated scope rank and
    compete at the cut without stopping the walk."""

    @staticmethod
    def _session():
        # desc + scope put four chunks in the pool before widening; the tag
        # areas hold one chunk per level
        chunks = {("t0",): [_row("c-t0", 0.5)], ("t1",): [_row("c-t1", 0.5)]}
        return _Session(
            [], chunks,
            desc_rows=[[_desc_row("d1", 0.9), _desc_row("d2", 0.85)]],
            scope_rows=[{"chunkId": "s1", "locator": "{}",
                         "relpath": "Salesforce__HERB/products/TestForce.json",
                         "sha256": "sha", "matched": 1, "sim": 0.8},
                        {"chunkId": "s2", "locator": "{}",
                         "relpath": "Salesforce__HERB/products/TestForce.json",
                         "sha256": "sha", "matched": 1, "sim": 0.7}],
        )

    def test_the_gate_counts_only_the_tag_areas_evidence(self):
        levels = _levels((0.0, "t0"), (0.5, "t1"))
        session = self._session()
        plan = _plan(["p"], dict(_NO_GATE, product="TestForce"))
        with patch.object(arm, "_embed", side_effect=_fake_embed), \
             patch.object(arm, "_part_levels", return_value=levels), \
             patch.object(arm, "WALK_GATE", True):
            rows, _, _ = arm._retrieve(session, plan, k=4)
        self.assertIn(("t1",), session.opened)  # the walk widened
        # description and scope chunks still rank and compete at the cut
        self.assertEqual({r["chunkId"] for r in rows},
                         {"d1", "s1", "c-t0", "c-t1"})

    def test_without_the_flag_the_filled_pool_stops_the_walk(self):
        levels = _levels((0.0, "t0"), (0.5, "t1"))
        session = self._session()
        plan = _plan(["p"], dict(_NO_GATE, product="TestForce"))
        with patch.object(arm, "_embed", side_effect=_fake_embed), \
             patch.object(arm, "_part_levels", return_value=levels):
            arm._retrieve(session, plan, k=4)
        self.assertNotIn(("t1",), session.opened)


class GuideTests(unittest.TestCase):
    """HERB_STR_GUIDE > 0: the part's facet blend of the cached per-facet
    membership matrices lifts tag support by (1 + STR_GUIDE · g)."""

    @staticmethod
    def _tables(names=("near_a", "far_a")):
        # synthetic membership fixture: every facet matrix row sums to 1 and
        # every cell sits strictly inside (0, 1)
        rng = np.random.default_rng(7)
        U = rng.random((len(arm.ALL_FACETS), len(names), 4))
        U /= U.sum(axis=2, keepdims=True)
        return {"U": U, "row": {n: i for i, n in enumerate(names)}}

    @staticmethod
    def _session():
        ground = [[_ground_row("near_a", 0.9, [1.0, 0.0]),
                   _ground_row("far_a", 0.5, [0.0, 1.0])]]
        chunks = {("near_a",): [_row("c1", 0.8)], ("far_a",): [_row("c2", 0.7)]}
        return _Session(ground, chunks)

    def test_an_all_zero_facet_profile_blends_uniformly(self):
        zero = {f: 0.0 for f in arm.ALL_FACETS}
        flat = {f: 0.2 for f in arm.ALL_FACETS}
        with patch.object(arm, "_GUIDE", self._tables()):
            g_zero = arm._guidance(["near_a"], zero)
            g_flat = arm._guidance(["near_a"], flat)
        self.assertAlmostEqual(float(g_zero[0]), float(g_flat[0]), places=12)

    def test_a_flat_profile_is_the_uniform_blend(self):
        tables = self._tables()
        with patch.object(arm, "_GUIDE", tables):
            g = arm._guidance(["near_a"], {f: 0.2 for f in arm.ALL_FACETS})
        cells = np.full((len(arm.ALL_FACETS), 1), 0.2) * tables["U"][:, 0, :]
        expected = float(np.where(cells >= arm.GUIDE_TAU, cells, 0.0).sum())
        self.assertAlmostEqual(float(g[0]), expected, places=12)

    def test_guidance_stays_inside_the_unit_interval(self):
        skew = {"topic": 1.0, "entities": 0.3, "activity": 0.0,
                "temporal": 0.0, "evidence": 0.7}
        with patch.object(arm, "_GUIDE", self._tables()):
            g = arm._guidance(["near_a", "far_a"], skew)
        self.assertTrue(np.all(g >= 0.0))
        self.assertTrue(np.all(g <= 1.0 + 1e-12))

    def test_a_tag_outside_the_cache_index_keeps_g_zero(self):
        stats = {"matched": 0, "unmatched": 0, "g_sum": 0.0, "g_n": 0}
        with patch.object(arm, "_GUIDE", self._tables()):
            g = arm._guidance(["near_a", "nowhere"],
                              {f: 0.2 for f in arm.ALL_FACETS}, stats)
        self.assertEqual(float(g[1]), 0.0)
        self.assertGreater(float(g[0]), 0.0)
        self.assertEqual((stats["matched"], stats["unmatched"]), (1, 1))
        self.assertEqual(stats["g_n"], 2)

    def test_the_lift_scales_support_by_one_plus_str_guide_times_g(self):
        # tau 0 keeps every cell, so a cached tag's g is exactly its blend
        # total = 1 and the lift is exactly (1 + STR_GUIDE)
        part = {"t": "p", "facets": {f: 0.2 for f in arm.ALL_FACETS}}
        vec = np.array([1.0, 0.0])
        base = arm._part_levels(self._session(), part, vec, dict(_NO_GATE))
        with patch.object(arm, "_GUIDE", self._tables()), \
             patch.object(arm, "STR_GUIDE", 2.0), \
             patch.object(arm, "GUIDE_TAU", 0.0):
            lifted = arm._part_levels(self._session(), part, vec, dict(_NO_GATE))
        base_sup = {n: s for lv in base for n, s in lv["tags"]}
        lift_sup = {n: s for lv in lifted for n, s in lv["tags"]}
        for name in ("near_a", "far_a"):
            self.assertAlmostEqual(lift_sup[name], base_sup[name] * 3.0)

    @staticmethod
    def _offset_tables():
        # three pad rows push the pool tags to cache rows 3 and 4, so a pool
        # index never equals its cache row and g must land through the
        # name -> row map. near_a's uniform row (cells 0.2 * 0.25 = 0.05)
        # drops entirely below tau 0.06; far_a's concentrated row keeps one
        # 0.2 * 0.97 = 0.194 cell per facet, so g_near = 0 and g_far = 0.97.
        names = ("pad_0", "pad_1", "pad_2", "near_a", "far_a")
        U = np.full((len(arm.ALL_FACETS), len(names), 4), 0.25)
        U[:, 4, :] = [0.97, 0.01, 0.01, 0.01]
        return {"U": U, "row": {n: i for i, n in enumerate(names)}}

    def test_each_tag_lifts_by_its_own_g_and_the_anchor_follows(self):
        # near_a leads on distance (support 400 vs ~330.6); only far_a's row
        # survives tau, so its lift (x 1.485) overtakes and the anchor flips.
        ground = lambda: [[_ground_row("near_a", 0.9, [1.0, 0.0]),
                           _ground_row("far_a", 0.89, [0.0, 1.0])]]
        chunks = {("near_a",): [_row("c1", 0.8)], ("far_a",): [_row("c2", 0.7)]}
        part = {"t": "p", "facets": {f: 0.2 for f in arm.ALL_FACETS}}
        vec = np.array([1.0, 0.0])
        base = arm._part_levels(_Session(ground(), chunks), part, vec,
                                dict(_NO_GATE))
        with patch.object(arm, "_GUIDE", self._offset_tables()), \
             patch.object(arm, "STR_GUIDE", 0.5), \
             patch.object(arm, "GUIDE_TAU", 0.06):
            lifted = arm._part_levels(_Session(ground(), chunks), part, vec,
                                      dict(_NO_GATE))
        base_sup = {n: s for lv in base for n, s in lv["tags"]}
        lift_sup = {n: s for lv in lifted for n, s in lv["tags"]}
        self.assertAlmostEqual(lift_sup["far_a"],
                               base_sup["far_a"] * (1.0 + 0.5 * 0.97))
        self.assertAlmostEqual(lift_sup["near_a"], base_sup["near_a"])
        plain, guided = _Session(ground(), chunks), _Session(ground(), chunks)
        with patch.object(arm, "_embed", side_effect=_fake_embed):
            arm._retrieve(plain, _plan(["p"]), k=1)
        with patch.object(arm, "_embed", side_effect=_fake_embed), \
             patch.object(arm, "_GUIDE", self._offset_tables()), \
             patch.object(arm, "STR_GUIDE", 0.5), \
             patch.object(arm, "GUIDE_TAU", 0.06):
            arm._retrieve(guided, _plan(["p"]), k=1)
        self.assertEqual(plain.opened[0], ("near_a",))
        self.assertEqual(guided.opened[0], ("far_a",))

    def test_tau_at_one_drops_every_cell_and_the_lift_is_inert(self):
        with patch.object(arm, "_embed", side_effect=_fake_embed):
            base, _, _ = arm._retrieve(self._session(), _plan(["p"]), k=2)
        with patch.object(arm, "_embed", side_effect=_fake_embed), \
             patch.object(arm, "_GUIDE", self._tables()), \
             patch.object(arm, "STR_GUIDE", 1.0), \
             patch.object(arm, "GUIDE_TAU", 1.0):
            guided, _, meta = arm._retrieve(self._session(), _plan(["p"]), k=2)
        self.assertEqual(base, guided)
        self.assertEqual(meta["guide"],
                         {"str": 1.0, "tau": 1.0, "C": arm.GUIDE_C,
                          "m": arm.GUIDE_M, "matched": 2, "unmatched": 0,
                          "mean_g": 0.0})

    def test_off_touches_no_cache(self):
        with patch.object(arm, "_embed", side_effect=_fake_embed), \
             patch.object(arm, "_guide_tables") as tables:
            _, _, meta = arm._retrieve(self._session(), _plan(["p"]), k=2)
        tables.assert_not_called()
        self.assertNotIn("guide", meta)


class GuideBuildTests(unittest.TestCase):
    """build_tag_clusters' math on synthetic vectors — no graph, no model."""

    @staticmethod
    def _pool(n=40, dim=8, seed=3):
        rng = np.random.default_rng(seed)
        X = rng.normal(size=(n, dim))
        return X / np.linalg.norm(X, axis=1, keepdims=True)

    def test_membership_rows_sum_to_one(self):
        X = self._pool()
        V, _ = btc.weighted_spherical_kmeans(
            X, np.ones(len(X)), btc.kmeanspp_init(X, 4, seed=11))
        U = btc.memberships(X, V, 1.5)
        self.assertEqual(U.dtype, np.float32)
        self.assertTrue(np.allclose(U.sum(axis=1), 1.0, atol=1e-5))

    def test_facet_participation_counts_edge_fractions(self):
        omega = btc.facet_participation(
            [[["topic"], ["topic", "evidence"]], [[]]])
        topic, evidence = (btc._FACET_COL["topic"], btc._FACET_COL["evidence"])
        self.assertEqual(omega[0][topic], 1.0)       # topic on 2/2 edges
        self.assertEqual(omega[0][evidence], 0.5)    # evidence on 1/2
        self.assertTrue((omega[1] == 0.0).all())     # a facet-less edge
        floored = btc.floor_participation(omega, 0.05)
        self.assertAlmostEqual(floored[1][topic], 0.05)
        self.assertAlmostEqual(floored[0][topic], 1.0)

    def test_the_build_is_deterministic_for_a_fixed_seed(self):
        X = self._pool()
        w = np.linspace(0.1, 1.0, len(X))
        out = []
        for _ in range(2):
            V, it = btc.weighted_spherical_kmeans(
                X, w, btc.kmeanspp_init(X, 4, seed=20260731))
            out.append((btc.memberships(X, V, 1.5), it))
        self.assertEqual(out[0][1], out[1][1])
        self.assertTrue(np.array_equal(out[0][0], out[1][0]))


class ResolveGuardTests(unittest.TestCase):
    def test_a_relpath_escaping_the_raw_root_is_refused(self):
        with self.assertRaisesRegex(RuntimeError, "raw root"):
            arm._load_verified_doc("../outside.json", "0" * 64, {})


class DeterministicPlanTests(unittest.TestCase):
    class _S:
        def run(self, q, **p):
            return [{"p": "ActionGenie"}, {"p": "VizForce"}]

    class _Vocab:
        def __init__(self, products):
            self.products = products

        def run(self, q, **p):
            return [{"p": name} for name in self.products]

    def setUp(self):
        patcher = patch.dict(det._PRODUCTS, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_plan_extracts_only_what_the_question_literally_contains(self):
        plan = det._det_plan(
            "Which documents did eid_4afd9484 review for ActionGenie in 2026?", self._S())
        self.assertEqual(plan["gate"]["product"], "ActionGenie")
        self.assertEqual(plan["gate"]["section"], "documents")
        self.assertEqual(plan["gate"]["employee_id"], "eid_4afd9484")
        self.assertEqual(plan["gate"]["years"], [2026])
        self.assertEqual(len(plan["parts"]), 1)

    def test_plan_states_nothing_when_the_question_names_nothing(self):
        plan = det._det_plan("who approved the budget?", self._S())
        self.assertEqual(plan["gate"], {"product": None, "section": None,
                                        "channel": None, "employee_id": None,
                                        "years": []})

    def test_section_matches_its_readable_multiword_form(self):
        plan = det._det_plan(
            "What do the meeting transcripts say about the launch?", self._S())
        self.assertEqual(plan["gate"]["section"], "meeting_transcripts")

    def test_product_matches_whole_words_only(self):
        plan = det._det_plan("how does vizforcex compare?",
                             self._Vocab(["VizForce"]))
        self.assertIsNone(plan["gate"]["product"])

    def test_the_earliest_product_mention_wins(self):
        plan = det._det_plan("Compare VizForce with ActionGenie",
                             self._Vocab(["ActionGenie", "VizForce"]))
        self.assertEqual(plan["gate"]["product"], "VizForce")

    def test_a_product_tie_at_one_position_goes_to_the_longest_name(self):
        plan = det._det_plan("all about Data Cloud usage",
                             self._Vocab(["Data", "Data Cloud"]))
        self.assertEqual(plan["gate"]["product"], "Data Cloud")

    def test_facet_direction_triggers_on_question_form(self):
        d = det._facet_direction("who reviewed the report?")
        names = list(det._ANCHOR_TEXTS)
        self.assertGreater(d[names.index("entities")], d[names.index("temporal")])
        self.assertAlmostEqual(float(d.sum()), 1.0)

    def test_plural_question_forms_trigger_their_facets(self):
        d = det._facet_triggers("Which PRs mention the rollback?")
        self.assertEqual(d["evidence"], 1.0)
        self.assertEqual(det._facet_triggers("what changes did the teams ship?")
                         ["entities"], 1.0)

    def test_facet_shaper_reorders_support_toward_the_question_direction(self):
        with patch.object(det, "_ANCHORS", np.eye(5)):  # anchors = axes, no embed call
            shape = det._facet_shaper("who wrote this?")  # entities-directed
            embs = np.array([[0.0, 1.0, 0.0, 0.0, 0.0],   # pure entities tag
                             [1.0, 0.0, 0.0, 0.0, 0.0]])  # pure topic tag
            support = np.array([0.4, 0.6])                # topic tag ahead on distance
            shaped = shape(["t_ent", "t_top"], embs, support)
        # raw shaped support, on the shared scale the combine step normalizes:
        # the entities tag gains relative to the topic tag
        self.assertGreater(shaped[0] / support[0], shaped[1] / support[1])


if __name__ == "__main__":
    unittest.main()

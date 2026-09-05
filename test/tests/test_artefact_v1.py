import argparse
import ast
import hashlib
import inspect
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from graph import backup_facet_weights as bkp
from graph import build_facet_layer as bfl
from graph import build_tag_clusters as btc
import run
from arms import artefact_v1 as arm
from arms import artefact_v1_det as det

_MODULE_FLAGS = (patch.object(arm, "CURVE_WALK", False),
                 patch.object(arm, "DOOR_TRACE", False),
                 patch.object(arm, "DESC_CUT", True),
                 patch.object(arm, "FRESH_INTERP", False),
                 patch.object(arm, "NO_REVIEW", False),
                 patch.object(arm, "AGG", "sum"),
                 patch.object(arm, "NORM", "relative"),
                 patch.object(arm, "NORM_SCOPE", "per_path"),
                 patch.object(arm, "W_TAG", 1.0),
                 patch.object(arm, "W_DESC", 1.0),
                 patch.object(arm, "W_SCOPE", 1.0),
                 patch.object(arm, "W_PERSON", 1.0),
                 patch.object(arm, "PERSON_ON", True),
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
        self.assertEqual((tok_in, tok_out), (10, 14))

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
        d = np.full(500, 0.3)
        support = arm._multi_k_support(d, extend=True)
        self.assertTrue(float(support[499]) > 0)
        self.assertTrue(support[0] > support[100] > support[499])

    def test_raw_support_is_a_pure_function_of_distance(self):
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
        self.assertEqual(kept, arm.K_LEVELS[1])
        self.assertEqual(calls, 2)
        self.assertEqual([r["sufficient"] for r in log], [False, True])

    def test_never_sufficient_keeps_the_full_retrieval(self):
        with patch.object(arm, "_chat_json",
                          return_value=({"sufficient": False}, 1, 1, 0.1)):
            kept, log, calls, *_ = arm._sufficient_cut("q", ["c"] * 50)
        self.assertEqual(kept, 50)
        self.assertEqual(calls, 3)

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

    def test_a_fill_to_budget_record_is_refused(self):
        import truncate_k
        rec = {"id": "q1", "contexts": ["c1"], "context_ids": ["a"],
               "meta": {"chunk_ids": [["a"]],
                        "char_budget": {"budget": 10, "chars": 10, "kept": 1,
                                        "boundary": None, "exhausted": False}}}
        with self.assertRaisesRegex(RuntimeError, "char_budget"):
            truncate_k.truncate_record(rec, 1)

    def test_a_fill_to_budget_run_folder_is_refused(self):
        import truncate_k
        with tempfile.TemporaryDirectory() as d:
            run_dir = Path(d) / "vector__gold100__cb10__x"
            run_dir.mkdir()
            (run_dir / "arm_outputs.jsonl").write_text("", encoding="utf-8")
            (run_dir / "run_manifest.json").write_text(
                json.dumps({"char_budget": 10}), encoding="utf-8")
            with patch.object(sys, "argv", ["truncate_k.py", str(run_dir)]):
                with self.assertRaisesRegex(SystemExit, "fill-to-budget"):
                    truncate_k.main()
            self.assertEqual(list(Path(d).iterdir()), [run_dir])


class LevelChainTests(unittest.TestCase):
    def _unit(self, rows):
        a = np.array(rows, dtype=np.float64)
        return a / np.linalg.norm(a, axis=1, keepdims=True)

    def test_chain_widens_through_own_family_before_the_far_one(self):
        embs = self._unit([[1.0, 0.0, 0.0], [0.99, 0.02, 0.0], [0.98, 0.04, 0.0],
                           [0.0, 1.0, 0.0], [0.02, 0.99, 0.0], [0.04, 0.98, 0.0]])
        chain = arm._level_chain(embs, anchor=0)
        self.assertEqual(chain[0], (0.0, [0]))
        added_order = [set(add) for _, add in chain[1:]]
        family = {1, 2}
        crossed = set()
        for add in added_order:
            if add & {3, 4, 5}:
                self.assertEqual(crossed, family)
            crossed |= add
        self.assertEqual(crossed, {1, 2, 3, 4, 5})
        heights = [h for h, _ in chain]
        self.assertEqual(heights, sorted(heights))

    def test_single_tag_pool_is_one_level(self):
        self.assertEqual(arm._level_chain(np.array([[1.0, 0.0]]), 0), [(0.0, [0])])


class _Session:

    def __init__(self, ground_rows, level_chunks, desc_rows=None, affinity_rows=None,
                 scope_rows=None):
        self.ground_rows = list(ground_rows)
        self.level_chunks = level_chunks
        self.desc_rows = list(desc_rows or [])
        self.affinity_rows = affinity_rows or []
        self.scope_rows = scope_rows or []
        self.opened = []
        self.area_cyphers = []
        self.area_params = []

    def run(self, query, **params):
        if query == arm._GROUND_CYPHER:
            return self.ground_rows.pop(0)
        if query == arm._AREA_CHUNKS_CYPHER:
            self.area_cyphers.append(query)
            self.area_params.append(params)
            names = tuple(sorted(t["name"] for t in params["tags"]))
            self.opened.append(names)
            return self.level_chunks.get(names, [])
        if query in (arm._DESC_KNN_CYPHER, arm._DESC_KNN_EMB_CYPHER):
            return self.desc_rows.pop(0) if self.desc_rows else []
        if "UNWIND $names" in query:
            return self.affinity_rows
        if "vector.similarity.cosine" in query:
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


def _fake_embed(texts, kind, bar=True):
    return [[1.0, 0.0]] * len(texts), 1, 1, 1, 0.01


class LevelWalkTests(unittest.TestCase):
    def test_non_positive_k_fails_before_any_work(self):
        with self.assertRaisesRegex(ValueError, "k must be positive"):
            arm._retrieve(_Session([], {}), _plan(["p"]), k=0)

    def test_walk_widens_own_family_first_and_stops_at_k(self):
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

    def test_walk_stops_at_the_trajectory_break_and_k_falls_short_of_the_ceiling(self):
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
        levels = _levels((0.0, "t0"))
        session = _Session(
            [], {("t0",): [_row("c1", 0.5)]},
            desc_rows=[[_desc_row("c-near", 0.9, desc_emb=[1.0, 0.0]),
                        _desc_row("c-kin", 0.89, desc_emb=[0.999, 0.045])]],
        )
        plan = _plan(["p"])
        plan["description"] = "p"
        with patch.object(arm, "_embed", side_effect=_fake_embed), \
             patch.object(arm, "_part_levels", return_value=levels), \
             patch.object(arm, "CURVE_WALK", True):
            rows, _, meta = arm._retrieve(session, plan, k=10)
        self.assertEqual({r["chunkId"] for r in rows}, {"c1", "c-near", "c-kin"})
        desc_events = [w for w in meta["walk"] if w.get("path") == "desc"]
        self.assertEqual(len(desc_events), 2)
        self.assertIn("height", desc_events[1])
        self.assertEqual(meta["curve_walk"]["semantic"], 3)

    def test_stated_scope_corroborates_and_competes_but_never_sets_k(self):
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
        self.assertEqual(meta["curve_walk"]["pool"], 2)
        self.assertEqual(meta["curve_walk"]["semantic"], 1)

    def test_scope_only_evidence_under_the_walk_fails_loud(self):
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
                           ("HERB_FRESH_INTERP", "FRESH_INTERP"),
                           ("HERB_NO_REVIEW", "NO_REVIEW")):
            self.assertIn(f'{const} = os.environ.get("{env}") == "1"', src)

    def test_a_default_on_switch_reads_strict_from_the_environment(self):
        self.assertIn('DESC_CUT = _env_bool("HERB_DESC_CUT", True)',
                      inspect.getsource(arm))
        self.assertTrue(arm._env_bool("HERB_DESC_CUT_UNSET_XYZ", True))
        with patch.dict(os.environ, {"HERB_DESC_CUT_XYZ": "0"}):
            self.assertFalse(arm._env_bool("HERB_DESC_CUT_XYZ", True))
        with patch.dict(os.environ, {"HERB_DESC_CUT_XYZ": "true"}):
            with self.assertRaises(ValueError):
                arm._env_bool("HERB_DESC_CUT_XYZ", True)

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
            for name in ("HERB_CURVE_WALK", "HERB_DESC_CUT", "HERB_NO_REVIEW",
                         "HERB_AGG", "HERB_NORM", "HERB_NORM_SCOPE", "HERB_W_TAG",
                         "HERB_W_DESC", "HERB_W_SCOPE", "HERB_STR_FACET",
                         "HERB_STR_WCHUNK", "HERB_STR_RELEVANCE",
                         "HERB_STR_DESC_HINT", "HERB_STR_SCOPE_MATCH",
                         "HERB_DESC_HINT_M",
                         "HERB_STR_GUIDE", "HERB_GUIDE_TAU", "HERB_GUIDE_C",
                         "HERB_GUIDE_M", "HERB_GUIDE_LAMBDA", "HERB_GUIDE_SEED"):
                self.assertIn(name, flags)

    def test_the_mode_switches_reject_an_unknown_value(self):
        for name, val in (("HERB_AGG", "sum"), ("HERB_NORM", "relative"),
                          ("HERB_NORM_SCOPE", "per_path")):
            self.assertIn(name, arm.RETRIEVAL_FLAGS)
            self.assertEqual(arm.RETRIEVAL_FLAGS[name], val)

    def test_the_facet_strength_defaults_inert(self):
        self.assertEqual(arm._env_float("HERB_STR_FACET_UNSET_XYZ", arm.STR_FACET),
                         arm.STR_FACET)


class RunFlagTests(unittest.TestCase):
    def test_a_flag_spec_parses_to_its_name_value_pair(self):
        self.assertEqual(run._flag("HERB_DESC_CUT=0"), ("HERB_DESC_CUT", "0"))
        self.assertEqual(run._flag("HERB_STR_GUIDE=1.0"), ("HERB_STR_GUIDE", "1.0"))
        self.assertEqual(run._flag("A=b=c"), ("A", "b=c"))
        self.assertEqual(run._flag("HERB_X="), ("HERB_X", ""))

    def test_a_malformed_flag_spec_fails_at_parse(self):
        for bad in ("HERB_DESC_CUT", "=1", "="):
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
                self.assertFalse(name in ("arms", "eval")
                                 or name.startswith(("arms.", "eval.")),
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
        self.assertEqual(arm._mod(0.3, 1.5), 0.0)
        self.assertEqual(arm._mod(0.0, 3.0), 0.0)
        self.assertGreaterEqual(arm._mod(0.05, 5.0), 0.0)


class CombineTests(unittest.TestCase):

    def test_a_zero_path_weight_removes_that_paths_influence(self):
        ground = [[_ground_row("a", 0.9, [1.0, 0.0])]]
        session = _Session(ground, {("a",): [_row("c-tag", 0.5)]},
                           desc_rows=[[_desc_row("c-desc", 0.8)]])
        with patch.object(arm, "_embed", side_effect=_fake_embed), \
             patch.object(arm, "W_DESC", 0.0):
            rows, _, _ = arm._retrieve(session, _plan(["p"]), k=2)
        by_id = {r["chunkId"]: r["score"] for r in rows}
        self.assertEqual(by_id["c-desc"], 0.0)
        self.assertGreater(by_id["c-tag"], 0.0)

    def test_the_facet_modifier_is_inert_at_the_default_strength(self):
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
        ground = [[_ground_row("a", 0.9, [1.0, 0.0])]]
        return _Session(
            ground,
            {("a",): [_row("c-tag", 0.5)]},
            desc_rows=[[_desc_row("c-top", 0.9, desc_emb=[1.0, 0.0]),
                        _desc_row("c-hint", 0.88, product="TestForce",
                                  desc_emb=[0.9, 0.43589]),
                        _desc_row("c-floor", 0.5, desc_emb=[0.899, 0.438])]],
        )

    def _hint_rows(self, hint_m, strength=1.0):
        gate = dict(_NO_GATE, product="TestForce")
        with patch.object(arm, "_embed", side_effect=_fake_embed), \
             patch.object(arm, "DESC_HINT_M", hint_m), \
             patch.object(arm, "STR_DESC_HINT", strength):
            rows, _, _ = arm._retrieve(self._hint_session(), _plan(["p"], gate), k=4)
        return rows

    def test_the_hint_factor_scales_a_matching_description_chunks_score(self):
        at_one = {r["chunkId"]: r["score"] for r in self._hint_rows(1.0)}
        at_two = {r["chunkId"]: r["score"] for r in self._hint_rows(2.0)}
        self.assertGreater(at_two["c-hint"], at_one["c-hint"])
        self.assertAlmostEqual(at_two["c-hint"], 2.0 * at_one["c-hint"], places=3)
        self.assertEqual(at_two["c-top"], at_one["c-top"])

    def test_the_hint_factor_moves_a_matching_chunk_past_the_pools_best(self):
        lifted = [r["chunkId"] for r in self._hint_rows(2.0)]
        removed = [r["chunkId"] for r in self._hint_rows(0.0)]
        self.assertLess(lifted.index("c-hint"), lifted.index("c-top"))
        self.assertGreater(removed.index("c-hint"), removed.index("c-top"))

    def test_the_hint_factor_is_inert_at_zero_hint_strength(self):
        quiet = {r["chunkId"]: r["score"] for r in self._hint_rows(1.0, strength=0.0)}
        loud = {r["chunkId"]: r["score"] for r in self._hint_rows(4.0, strength=0.0)}
        self.assertEqual(loud, quiet)
        self.assertLess(loud["c-hint"], loud["c-top"])


class CombineModeTests(unittest.TestCase):

    @staticmethod
    def _two_part_session():
        ground = [[_ground_row("a", 0.9, [1.0, 0.0])],
                  [_ground_row("b", 0.8, [0.0, 1.0])]]
        chunks = {("a",): [_row("cx", 0.4)],
                  ("b",): [_row("cx", 0.4), _row("cy", 0.7)]}
        return _Session(ground, chunks)

    def test_agg_sum_lifts_a_corroborated_chunk(self):
        with patch.object(arm, "_embed", side_effect=_fake_embed):
            rows, _, _ = arm._retrieve(self._two_part_session(), _plan(["p1", "p2"]), k=2)
        self.assertEqual(rows[0]["chunkId"], "cx")

    def test_agg_max_keeps_the_single_best_contribution(self):
        with patch.object(arm, "_embed", side_effect=_fake_embed), \
             patch.object(arm, "AGG", "max"):
            rows, _, _ = arm._retrieve(self._two_part_session(), _plan(["p1", "p2"]), k=2)
        self.assertEqual(rows[0]["chunkId"], "cy")

    @staticmethod
    def _two_range_session():
        ground = [[_ground_row("a", 0.9, [1.0, 0.0])]]
        return _Session(
            ground,
            {("a",): [_row("c-strong", 100.0), _row("c-mid", 50.0)]},
            desc_rows=[[_desc_row("c-weakbest", 0.2), _desc_row("c-weak", 0.0)]],
        )

    def test_relative_per_path_stretches_each_paths_own_range(self):
        with patch.object(arm, "_embed", side_effect=_fake_embed):
            rows, _, _ = arm._retrieve(self._two_range_session(), _plan(["p"]), k=4)
        order = [r["chunkId"] for r in rows]
        self.assertLess(order.index("c-weakbest"), order.index("c-mid"))

    def test_relative_global_ranks_on_the_shared_range(self):
        with patch.object(arm, "_embed", side_effect=_fake_embed), \
             patch.object(arm, "NORM_SCOPE", "global"):
            rows, _, _ = arm._retrieve(self._two_range_session(), _plan(["p"]), k=4)
        order = [r["chunkId"] for r in rows]
        self.assertLess(order.index("c-mid"), order.index("c-weakbest"))

    def test_absolute_is_pool_independent_and_order_preserving(self):
        ref = arm._ABS_REF
        self.assertAlmostEqual(arm._absolute(8.0, ref), 8.0 / (8.0 + ref))
        self.assertLess(arm._absolute(4.0, ref), arm._absolute(8.0, ref))
        self.assertLess(arm._absolute(8.0, ref), 1.0)

    def test_absolute_equalizes_equal_distance_across_paths(self):
        tag_levels = len(arm.K_LEVELS)
        scope_levels = tag_levels + 3
        inv_d2 = 1.0 / 0.3 ** 2
        tag_top = tag_levels * inv_d2
        scope_top = scope_levels * inv_d2
        self.assertAlmostEqual(
            arm._absolute(tag_top, tag_levels * arm._ABS_UNIT),
            arm._absolute(scope_top, scope_levels * arm._ABS_UNIT))

    def test_scope_level_count_extends_with_the_matching_set(self):
        self.assertEqual(arm._n_levels(2), len(arm.K_LEVELS))
        self.assertEqual(arm._n_levels(arm.K_LEVELS[-1]), len(arm.K_LEVELS))
        self.assertEqual(arm._n_levels(arm.K_LEVELS[-1] + 1), len(arm.K_LEVELS) + 1)

    def test_absolute_keeps_a_weak_only_pools_best_below_one(self):
        ground = [[_ground_row("a", 0.9, [1.0, 0.0])]]
        session = _Session(ground, {("a",): [_row("c-hi", 8.0), _row("c-lo", 4.0)]})
        with patch.object(arm, "_embed", side_effect=_fake_embed), \
             patch.object(arm, "NORM", "absolute"):
            rows, _, _ = arm._retrieve(session, _plan(["p"]), k=2)
        by_id = {r["chunkId"]: r["score"] for r in rows}
        self.assertLess(by_id["c-hi"], 1.0)
        self.assertGreater(by_id["c-hi"], by_id["c-lo"])

    def test_absolute_removes_the_scope_extension_inflation(self):
        ground = [[_ground_row("a", 0.9, [1.0, 0.0])]]
        tag_support = len(arm.K_LEVELS) / 0.3 ** 2
        scope_rows = [{"chunkId": f"s{i:03d}", "locator": "{}",
                       "relpath": "Salesforce__HERB/products/TestForce.json",
                       "sha256": "sha", "matched": 1, "sim": 0.7}
                      for i in range(arm.K_LEVELS[-1] + 1)]
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
        self.assertEqual(emb.call_count, 1)
        self.assertGreater(calls1, 0)
        self.assertEqual(calls2, 0)
        self.assertTrue(np.array_equal(m1, m2))

    def test_a_new_model_id_misses(self):
        with patch.object(arm, "_embed", side_effect=_fake_embed):
            arm._embed_cached(["gamma"], "query")
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
        self.assertEqual(interp.call_count, 1)
        self.assertEqual(first[0], self._PLAN)
        self.assertEqual(second[0], self._PLAN)
        self.assertEqual(second[1:], (0, 0, 0, 0.0))

    def test_fresh_interp_bypasses_the_cache(self):
        with patch.object(arm, "_interpret",
                          return_value=(self._PLAN, 1, 1, 1, 0.1)) as interp:
            arm._interpret_cached("fresh me", "m")
            with patch.object(arm, "FRESH_INTERP", True):
                arm._interpret_cached("fresh me", "m")
                arm._interpret_cached("fresh me", "m")
        self.assertEqual(interp.call_count, 3)

    def test_a_model_change_misses(self):
        with patch.object(arm, "_interpret",
                          return_value=(self._PLAN, 1, 1, 1, 0.1)) as interp:
            arm._interpret_cached("switch me", "model-a")
            arm._interpret_cached("switch me", "model-b")
        self.assertEqual(interp.call_count, 2)

    def test_the_key_folds_in_the_interpreter_signature(self):
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
        self.assertEqual(arm._INTERP_SIG,
                         self._sig(inspect.getsource(arm._extract_json)))

    def test_the_key_changes_when_the_json_extractor_source_changes(self):
        self.assertNotEqual(self._sig(inspect.getsource(arm._extract_json)),
                            self._sig("def _extract_json(text): return {}"))


class WideningGateTests(unittest.TestCase):

    @staticmethod
    def _session():
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
             patch.object(arm, "_part_levels", return_value=levels):
            rows, _, _ = arm._retrieve(session, plan, k=4)
        self.assertIn(("t1",), session.opened)
        self.assertEqual({r["chunkId"] for r in rows},
                         {"d1", "s1", "c-t0", "c-t1"})

    def test_tag_reach_at_k_stops_the_walk(self):
        levels = _levels((0.0, "t0"), (0.5, "t1"))
        session = self._session()
        plan = _plan(["p"], dict(_NO_GATE, product="TestForce"))
        with patch.object(arm, "_embed", side_effect=_fake_embed), \
             patch.object(arm, "_part_levels", return_value=levels):
            arm._retrieve(session, plan, k=1)
        self.assertNotIn(("t1",), session.opened)


class DescCutTests(unittest.TestCase):

    @staticmethod
    def _session():
        return _Session(
            [[_ground_row("a", 0.9, [1.0, 0.0])]],
            {("a",): [_row("c1", 0.5)]},
            desc_rows=[[_desc_row("d-near", 0.95, desc_emb=[1.0, 0.0]),
                        _desc_row("d-kin", 0.94, desc_emb=[0.999, 0.045]),
                        _desc_row("d-far", 0.5, desc_emb=[0.0, 1.0]),
                        _desc_row("d-far2", 0.49, desc_emb=[0.045, 0.999])]],
        )

    def test_only_the_anchors_containing_cluster_is_admitted(self):
        session = self._session()
        with patch.object(arm, "_embed", side_effect=_fake_embed):
            rows, _, _ = arm._retrieve(session, _plan(["p"]), k=10)
        self.assertEqual({r["chunkId"] for r in rows},
                         {"c1", "d-near", "d-kin"})

    def test_the_walk_entry_records_the_admitted_width(self):
        session = self._session()
        with patch.object(arm, "_embed", side_effect=_fake_embed):
            _, _, meta = arm._retrieve(session, _plan(["p"]), k=10)
        desc = [w for w in meta["walk"] if w["path"] == "desc"]
        self.assertEqual([w["chunks"] for w in desc], [2])

    def test_a_single_chunk_neighborhood_admits_its_anchor(self):
        session = _Session([[_ground_row("a", 0.9, [1.0, 0.0])]],
                           {("a",): [_row("c1", 0.5)]},
                           desc_rows=[[_desc_row("d1", 0.9)]])
        with patch.object(arm, "_embed", side_effect=_fake_embed):
            rows, _, _ = arm._retrieve(session, _plan(["p"]), k=10)
        self.assertEqual({r["chunkId"] for r in rows}, {"c1", "d1"})

    def test_the_flag_off_admits_the_whole_neighborhood(self):
        session = self._session()
        with patch.object(arm, "_embed", side_effect=_fake_embed), \
             patch.object(arm, "DESC_CUT", False):
            rows, _, meta = arm._retrieve(session, _plan(["p"]), k=10)
        self.assertEqual({r["chunkId"] for r in rows},
                         {"c1", "d-near", "d-kin", "d-far", "d-far2"})
        desc = [w for w in meta["walk"] if w["path"] == "desc"]
        self.assertEqual([w["chunks"] for w in desc], [4])


class GuideTests(unittest.TestCase):

    @staticmethod
    def _tables(names=("near_a", "far_a")):
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
        names = ("pad_0", "pad_1", "pad_2", "near_a", "far_a")
        U = np.full((len(arm.ALL_FACETS), len(names), 4), 0.25)
        U[:, 4, :] = [0.97, 0.01, 0.01, 0.01]
        return {"U": U, "row": {n: i for i, n in enumerate(names)}}

    def test_each_tag_lifts_by_its_own_g_and_the_anchor_follows(self):
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
        self.assertEqual(omega[0][topic], 1.0)
        self.assertEqual(omega[0][evidence], 0.5)
        self.assertTrue((omega[1] == 0.0).all())
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


class DerivedLayerBuildTests(unittest.TestCase):

    def test_the_calibration_is_uniform_by_midrank(self):
        f = bfl.midrank_cdf(np.array([5.0, 1.0, 3.0, 9.0]))
        self.assertEqual(list(f), [3 / 5, 1 / 5, 2 / 5, 4 / 5])
        self.assertTrue(np.all((f > 0.0) & (f < 1.0)))

    def test_ties_share_their_mean_rank(self):
        f = bfl.midrank_cdf(np.array([2.0, 2.0, 7.0]))
        self.assertAlmostEqual(f[0], 1.5 / 4)
        self.assertEqual(f[0], f[1])

    def test_an_unevidenced_entry_carries_no_rank(self):
        evidenced = np.array([True, False, True])
        f = bfl.midrank_cdf(np.array([1.0, 99.0, 4.0]), evidenced)
        self.assertEqual(list(f), [1 / 3, 0.0, 2 / 3])

    def test_reliability_rises_with_evidence_and_starts_at_none(self):
        rho = bfl.reliability(np.array([0.0, 1.0, 4.0, 40.0]), 0.25)
        self.assertEqual(rho[0], 0.0)
        self.assertAlmostEqual(rho[1], 0.25)
        self.assertTrue(rho[1] < rho[2] < rho[3] < 1.0)

    def test_an_unevidenced_edge_lands_exactly_on_the_prior(self):
        score = np.array([0.3, 0.9])
        evidenced = np.array([True, False])
        rho = np.array([0.8, 0.0])
        for prior in (0.5, 0.0):
            phi = bfl.shrink(score, evidenced, rho, prior)
            self.assertEqual(phi[1], prior)

    def test_the_magnitude_sits_between_the_arithmetic_and_quadratic_means(self):
        rng = np.random.default_rng(5)
        phi = rng.random((200, len(arm.ALL_FACETS)))
        w = bfl.magnitude(phi)
        a = phi.mean(axis=1)
        q = np.sqrt((phi ** 2).mean(axis=1))
        self.assertTrue(np.all(a <= w + 1e-12))
        self.assertTrue(np.all(w <= q + 1e-12))

    def test_the_magnitude_is_the_v1_expression_over_the_derived_vector(self):
        rng = np.random.default_rng(9)
        phi = rng.random((200, 5))
        s1, s2 = phi.sum(axis=1), (phi ** 2).sum(axis=1)
        v1 = np.sqrt(s2 / 5.0) * ((s1 ** 2) / (5.0 * s2)) ** 0.25
        self.assertTrue(np.allclose(bfl.magnitude(phi), v1, rtol=0, atol=1e-15))

    def test_a_flat_query_profile_selects_nothing(self):
        rng = np.random.default_rng(11)
        phi = rng.random((500, 5))
        flat = np.full(5, 1.0 / 5)
        term = 5.0 * ((phi / phi.sum(axis=1, keepdims=True)) @ flat)
        self.assertLess(float(np.max(np.abs(term - 1.0))), 1e-12)

    def test_a_declared_name_inside_a_text_counts_once_per_occurrence(self):
        long_names = {"marcus_delgado", "vizforce"}
        tokens = "marcus_delgado_review_of_vizforce_by_marcus_delgado".split("_")
        self.assertEqual(bfl.name_count(tokens, long_names), 3)
        self.assertEqual(bfl.name_count(["unrelated", "phrase"], long_names), 0)

    def test_the_longest_run_wins_and_is_not_counted_twice(self):
        long_names = {"marcus_delgado", "delgado_review"}
        self.assertEqual(bfl.name_count(["marcus", "delgado", "review"], long_names), 1)

    def test_a_name_longer_than_the_token_window_is_not_matched(self):
        long_name = "_".join(f"tok{i}" for i in range(bfl.MAX_NAME_TOKENS + 1))
        self.assertEqual(bfl.name_count(long_name.split("_"), {long_name}), 0)

    def test_the_pair_is_the_records_carrying_the_tag(self):
        slugs = ["the_mulesoft_connector_shipped", "a_reply_about_nothing",
                 "connector_for_mulesoft_again"]
        self.assertEqual(bfl.tag_records("MuleSoft connector", slugs),
                         ([0], "verbatim"))
        self.assertEqual(bfl.tag_records("connector MuleSoft", slugs),
                         ([0, 2], "all_tokens"))
        self.assertEqual(bfl.tag_records("salesforce", slugs), ([], "none"))

    def test_a_tag_with_no_long_token_falls_back_to_nothing(self):
        self.assertEqual(bfl.tag_records("AI", ["ai_and_more", "plum"]),
                         ([0], "verbatim"))
        self.assertEqual(bfl.tag_records("AI", ["plum", "text"]), ([], "none"))

    def test_the_parity_split_is_deterministic_and_two_sided(self):
        keys = [f"chunk_{i}" for i in range(200)]
        first = bfl.sha256_parity(keys)
        self.assertTrue(np.array_equal(first, bfl.sha256_parity(keys)))
        self.assertEqual(set(first.tolist()), {0, 1})

    def test_the_register_profile_z_scores_each_feature_over_the_corpus(self):
        profiles = bfl.register_profiles(
            ['{"body": "we shipped 3 builds because the deadline moved"}',
             '{"body": "you should see https://x.example for the numbers"}',
             '{"body": "plain prose with nothing countable in it at all"}'])
        self.assertEqual(profiles.shape, (3, len(bfl.REGISTER)))
        varying = profiles.std(axis=0) > 0.5
        self.assertTrue(np.allclose(profiles[:, varying].mean(axis=0), 0.0, atol=1e-9))
        self.assertTrue(np.allclose(profiles[:, varying].std(axis=0), 1.0, atol=1e-9))

    def test_a_class_below_the_floor_is_no_prototype(self):
        rng = np.random.default_rng(13)
        profiles = rng.normal(size=(bfl.DERIVED_MIN_CLASS + 5, 4))
        declared = np.array(["slack"] * bfl.DERIVED_MIN_CLASS + ["rare"] * 5)
        match, classes = bfl.class_match(profiles, declared)
        self.assertEqual(classes, ["slack"])
        self.assertEqual(len(match), len(profiles))
        self.assertTrue(np.all(np.abs(match) <= 1.0 + 1e-9))

    def test_the_prototypes_come_from_the_chunks_and_score_the_rows_given(self):
        rng = np.random.default_rng(14)
        profiles = rng.normal(size=(bfl.DERIVED_MIN_CLASS, 4))
        declared = np.array(["slack"] * bfl.DERIVED_MIN_CLASS)
        prototype = profiles.mean(axis=0)
        match, _ = bfl.class_match(profiles, declared, np.stack([prototype, -prototype]))
        self.assertAlmostEqual(match[0], 1.0)
        self.assertAlmostEqual(match[1], -1.0)

    def test_standardising_on_a_reference_uses_its_mean_and_spread(self):
        reference = np.array([[0.0, 10.0], [2.0, 10.0], [4.0, 10.0]])
        z = bfl.standardise(np.array([[2.0, 10.0], [6.0, 10.0]]), reference)
        self.assertTrue(np.allclose(z[0], [0.0, 0.0]))
        self.assertAlmostEqual(z[1, 0], 4.0 / reference[:, 0].std())

    def test_a_locator_naming_an_excluded_section_fails_loud(self):
        for section in arm.EXCLUDED_SECTIONS:
            with self.assertRaisesRegex(RuntimeError, "excluded section"):
                bfl._resolve({"section": section, "index": 0}, {})

    def test_a_char_range_chunk_reads_its_slice_and_keeps_its_carrier_fields(self):
        doc = {"documents": [{"content": "abcdefghij", "date": "2026-01-02T00:00:00",
                              "document_type": "spec", "id": "doc_1"}]}
        records, texts = bfl._resolve(
            {"section": "documents", "index": 0, "field": "content",
             "char_range": [2, 5]}, doc)
        self.assertEqual(texts, ['{"content": "cde"}'])
        self.assertEqual(records[0]["document_type"], "spec")
        self.assertEqual(records[0]["date"], "2026-01-02T00:00:00")

    @staticmethod
    def _temporal_fixture():
        day = np.array([0.0, 1.0, 2.0, 3.0, 100.0, 101.0, np.nan])
        half = np.array([0, 1, 0, 1, 0, 1, 0])
        edges = [(0, 0), (0, 1), (0, 2), (0, 3),
                 (1, 0), (1, 1), (1, 4), (1, 5),
                 (2, 4), (3, 6)]
        rows = np.array([t for t, _ in edges])
        cols = np.array([c for _, c in edges])
        return day, rows, cols, half

    def test_a_tag_with_one_dated_chunk_carries_no_temporal_evidence(self):
        day, rows, cols, half = self._temporal_fixture()
        score, evidenced, rho, icc = bfl.temporal_terms(day, day[cols], rows, cols, half, 4)
        self.assertEqual(list(evidenced[-2:]), [False, False])
        self.assertEqual(list(rho[-2:]), [0.0, 0.0])
        self.assertTrue(evidenced[:8].all())
        for prior in (0.5, 0.0):
            phi = bfl.shrink(score, evidenced, rho, prior)
            self.assertEqual(list(phi[-2:]), [prior, prior])

    def test_a_tight_tag_scores_its_own_chunks_above_a_wide_one(self):
        day, rows, cols, half = self._temporal_fixture()
        score, _, _, _ = bfl.temporal_terms(day, day[cols], rows, cols, half, 4)
        self.assertGreater(score[0], score[4])

    def test_an_undated_pair_on_a_dated_chunk_carries_no_temporal_evidence(self):
        day, rows, cols, half = self._temporal_fixture()
        edge_day = day[cols].copy()
        edge_day[0] = np.nan
        score, evidenced, rho, _ = bfl.temporal_terms(day, edge_day, rows, cols, half, 4)
        self.assertFalse(evidenced[0])
        self.assertEqual(rho[0], 0.0)
        self.assertTrue(evidenced[1:8].all())

    def test_the_pair_day_not_the_chunk_day_sets_the_distance(self):
        day, rows, cols, half = self._temporal_fixture()
        near = bfl.temporal_terms(day, day[cols], rows, cols, half, 4)[0]
        far = day[cols].copy()
        far[0] = 100.0
        self.assertLess(bfl.temporal_terms(day, far, rows, cols, half, 4)[0][0], near[0])

    def test_the_pair_reads_its_own_records_and_the_chunk_reads_all(self):
        facts = [{"texts": ['{"body": "we shipped 3 builds because the deadline moved"}',
                            '{"body": "Marcus Delgado should review the workflow"}'],
                  "record_days": [[10], []]},
                 {"texts": ['{"body": "plain prose"}'], "record_days": [[]]}]
        table = bfl.record_table(facts, {"marcus_delgado", "short"})
        self.assertEqual(list(table["start"]), [0, 2, 3])
        self.assertEqual(list(table["names"]), [0.0, 1.0, 0.0])
        rows = np.array([0, 1, 2])
        cols = np.array([0, 0, 1])
        pair = bfl.pair_terms(["deadline", "Marcus Delgado", "nothing here"],
                              rows, cols, table, 4.0)
        self.assertEqual(list(pair["evidenced"]), [True, True, False])
        self.assertEqual(pair["found"], {"verbatim": 2, "none": 1})
        second = len(facts[0]["texts"][1])
        self.assertAlmostEqual(pair["entities"][1], bfl.PER_CHARS / second)
        self.assertAlmostEqual(pair["activity"][1], 2 * bfl.PER_CHARS / second)
        self.assertAlmostEqual(pair["activity"][0],
                               bfl.PER_CHARS / len(facts[0]["texts"][0]))
        self.assertEqual(pair["day"][0], 6.0)
        self.assertTrue(np.isnan(pair["day"][1]))
        self.assertTrue(np.isnan(pair["day"][2]))


class FacetWeightBackupTests(unittest.TestCase):

    _ROWS = [
        {"chunk_id": "c1", "tag": "auth_rotation",
         "facets": ["topic", "entities"], "w_facets": [0.5, 0.125],
         "w_chunk": 0.3061224489795918},
        {"chunk_id": "c2", "tag": "sökväg_ändring",
         "facets": None, "w_facets": None, "w_chunk": None},
    ]

    class _WriteSession:

        def __init__(self):
            self.calls = []

        def run(self, query, **params):
            self.calls.append((query, params))
            return self

        def consume(self):
            return None

    def _root(self):
        root = Path(tempfile.mkdtemp(prefix="facet_backup_"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        return root

    def _entry(self):
        return self._root() / "entry"

    def test_an_edge_survives_serialise_and_parse_unchanged(self):
        for row in self._ROWS:
            self.assertEqual(bkp.parse(bkp.serialise(row)), row)
        self.assertEqual(bkp.round_trip(self._ROWS), 0)

    def test_a_weight_comes_back_the_float_it_went_in_as(self):
        rng = np.random.default_rng(17)
        for i, v in enumerate(rng.random(500)):
            row = {"chunk_id": f"c{i}", "tag": "t", "facets": ["topic"],
                   "w_facets": [float(v)], "w_chunk": float(v)}
            self.assertEqual(bkp.parse(bkp.serialise(row)), row)

    def test_the_file_holds_the_edges_in_the_order_it_was_given(self):
        entry = self._entry()
        bkp.write_backup(self._ROWS, entry)
        lines = (entry / bkp.WEIGHTS).read_text(encoding="utf-8").splitlines()
        self.assertEqual([bkp.parse(line) for line in lines], self._ROWS)

    def test_the_manifest_records_the_count_and_the_files_hash(self):
        entry = self._entry()
        manifest = bkp.write_backup(self._ROWS, entry)
        sha, lines = bkp.digest(entry / bkp.WEIGHTS)
        self.assertEqual((manifest["sha256"], manifest["n_edges"]), (sha, lines))
        self.assertEqual(bkp.require_backup(entry), manifest)

    def test_a_missing_backup_names_the_command_that_writes_one(self):
        with self.assertRaisesRegex(RuntimeError, "backup_facet_weights.py backup"):
            bkp.require_backup(self._entry())

    def test_an_edited_backup_fails_its_own_hash(self):
        entry = self._entry()
        bkp.write_backup(self._ROWS, entry)
        path = entry / bkp.WEIGHTS
        edited = path.read_text(encoding="utf-8").replace("0.5", "0.9")
        with path.open("w", encoding="utf-8", newline="\n") as f:
            f.write(edited)
        with self.assertRaisesRegex(RuntimeError, "hashes"):
            bkp.require_backup(entry)

    def test_a_backup_short_of_its_count_fails(self):
        entry = self._entry()
        bkp.write_backup(self._ROWS, entry)
        path = entry / bkp.WEIGHTS
        with path.open("w", encoding="utf-8", newline="\n") as f:
            f.write(bkp.serialise(self._ROWS[0]) + "\n")
        marker = entry / bkp.MANIFEST
        manifest = json.loads(marker.read_text(encoding="utf-8"))
        manifest["sha256"] = bkp.digest(path)[0]
        marker.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "holds 1 edges"):
            bkp.require_backup(entry)

    def test_a_backup_of_another_run_is_not_this_ones(self):
        entry = self._entry()
        bkp.write_backup(self._ROWS, entry)
        marker = entry / bkp.MANIFEST
        manifest = json.loads(marker.read_text(encoding="utf-8"))
        manifest["run_id"] = "another_run"
        marker.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "another_run"):
            bkp.require_backup(entry)

    def test_a_line_missing_a_field_fails_loud(self):
        with self.assertRaisesRegex(ValueError, "w_chunk"):
            bkp.parse('{"chunk_id":"c1","tag":"t","facets":null,"w_facets":null}')

    def test_the_entry_is_named_by_the_graph_and_the_tagging_run(self):
        self.assertEqual(bkp.entry_dir().name, f"{arm.DATABASE}__{arm.RUN_ID}")

    def test_a_restore_writes_every_row_in_file_order(self):
        entry = self._entry()
        manifest = bkp.write_backup(self._ROWS, entry)
        rows = bkp.load_backup(entry, manifest)
        self.assertEqual(rows, self._ROWS)
        session = self._WriteSession()
        bkp.restore(session, rows)
        self.assertEqual(session.calls,
                         [(bkp._RESTORE_CYPHER, {"rows": rows, "runId": arm.RUN_ID})])

    def test_the_build_writes_the_current_graph_only(self):
        with patch.object(bfl, "DATABASE", "herb-eval"), \
             patch.object(bfl, "require_backup") as backup, \
             patch.object(bfl, "_driver") as driver:
            with self.assertRaisesRegex(SystemExit, bfl.BUILD_DATABASE):
                bfl.main()
        backup.assert_not_called()
        driver.assert_not_called()

    def test_the_build_refuses_to_write_without_a_backup(self):
        with patch.object(bfl, "DATABASE", bfl.BUILD_DATABASE), \
             patch.object(bkp, "BACKUP_DIR", self._root()), \
             patch.object(bfl, "_driver") as driver:
            with self.assertRaisesRegex(RuntimeError, "backup_facet_weights.py backup"):
                bfl.main()
        driver.assert_not_called()

    def test_a_complete_backup_lets_the_build_start(self):
        cache = self._root()
        with patch.object(bfl, "DATABASE", bfl.BUILD_DATABASE), \
             patch.object(bkp, "BACKUP_DIR", self._root()):
            entry = cache / bfl._derived_key()
            entry.mkdir(parents=True)
            (entry / "manifest.json").write_text("{}", encoding="utf-8")
            bkp.write_backup(self._ROWS, bkp.entry_dir())
            with patch.object(bfl, "DERIVED_CACHE_DIR", cache), \
                 patch.object(bfl, "_driver") as driver:
                bfl.main()
        driver.assert_not_called()


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
        with patch.object(det, "_ANCHORS", np.eye(5)):
            shape = det._facet_shaper("who wrote this?")
            embs = np.array([[0.0, 1.0, 0.0, 0.0, 0.0],
                             [1.0, 0.0, 0.0, 0.0, 0.0]])
            support = np.array([0.4, 0.6])
            shaped = shape(["t_ent", "t_top"], embs, support)
        self.assertGreater(shaped[0] / support[0], shaped[1] / support[1])


class KeepAllRankingTests(unittest.TestCase):

    @staticmethod
    def _session():
        ground = [[_ground_row("near_a", 0.9, [1.0, 0.0])]]
        chunks = {("near_a",): [_row("c1", 0.8), _row("c2", 0.7), _row("c3", 0.6)]}
        return _Session(ground, chunks)

    def test_keep_all_returns_the_whole_ranked_union(self):
        with patch.object(arm, "_embed", side_effect=_fake_embed):
            cut_rows, _, _ = arm._retrieve(self._session(), _plan(["p"]), k=2)
            all_rows, _, _ = arm._retrieve(self._session(), _plan(["p"]), k=2,
                                           keep_all=True)
        self.assertEqual([r["chunkId"] for r in cut_rows], ["c1", "c2"])
        self.assertEqual([r["chunkId"] for r in all_rows], ["c1", "c2", "c3"])

    def test_keep_all_does_not_combine_with_the_curve_walk(self):
        with patch.object(arm, "CURVE_WALK", True):
            with self.assertRaisesRegex(ValueError, "HERB_CURVE_WALK"):
                arm._retrieve(self._session(), _plan(["p"]), k=2, keep_all=True)


class BudgetContextsTests(unittest.TestCase):

    _TEXTS = {"c1": "A" * 8, "c2": "B" * 8, "c3": "C" * 8}
    _IDS = {"c1": ["a1", "a2"], "c2": ["a2", "a3"], "c3": ["a4"]}

    def setUp(self):
        self.resolved = []

    def _resolve(self, row, cache):
        cid = row["chunkId"]
        self.resolved.append(cid)
        return self._TEXTS[cid], list(self._IDS[cid])

    def _rows(self):
        return [_row("c1", 0.8), _row("c2", 0.7), _row("c3", 0.6)]

    def test_the_crossing_chunk_is_cut_to_exactly_the_budget(self):
        with patch.object(arm, "_resolve_chunk", side_effect=self._resolve):
            contexts, id_lists, context_ids, block = arm._budget_contexts(
                self._rows(), 12, {})
        self.assertEqual(contexts, ["A" * 8, "B" * 4])
        self.assertEqual(sum(len(c) for c in contexts), 12)
        self.assertEqual(id_lists, [["a1", "a2"], ["a2", "a3"]])
        self.assertEqual(context_ids, ["a1", "a2"])
        self.assertEqual(block, {"budget": 12, "chars": 12, "kept": 1,
                                 "boundary": {"id": "c2", "chars_kept": 4,
                                              "chars_full": 8},
                                 "exhausted": False})

    def test_resolution_stops_at_the_cut(self):
        with patch.object(arm, "_resolve_chunk", side_effect=self._resolve):
            arm._budget_contexts(self._rows(), 12, {})
        self.assertEqual(self.resolved, ["c1", "c2"])

    def test_an_exhausted_pool_records_its_true_total(self):
        with patch.object(arm, "_resolve_chunk", side_effect=self._resolve):
            contexts, id_lists, context_ids, block = arm._budget_contexts(
                self._rows(), 100, {})
        self.assertEqual(sum(len(c) for c in contexts), 24)
        self.assertEqual(context_ids, ["a1", "a2", "a3", "a4"])
        self.assertEqual((block["chars"], block["exhausted"]), (24, True))
        self.assertIsNone(block["boundary"])


class BudgetAnswerTests(unittest.TestCase):

    CORPUS = Path(__file__).resolve().parent.parent.parent / "data" / "corpus" / "Salesforce__HERB"

    class _Driver:
        def __init__(self, session):
            self._session = session

        def session(self, database=None):
            return self

        def __enter__(self):
            return self._session

        def __exit__(self, *exc):
            return False

    def _prepared(self, session):
        return arm.Prepared(driver=self._Driver(session),
                            directory=arm._load_person_directory(self.CORPUS))

    def test_the_model_leg_returns_exactly_n_chars_and_runs_no_review(self):
        ground = [[_ground_row("near_a", 0.9, [1.0, 0.0])]]
        chunks = {("near_a",): [_row("c1", 0.8), _row("c2", 0.7), _row("c3", 0.6)]}
        prepared = self._prepared(_Session(ground, chunks))
        texts = {"c1": "A" * 8, "c2": "B" * 8, "c3": "C" * 8}
        ids = {"c1": ["a1"], "c2": ["a2"], "c3": ["a3"]}
        with patch.object(arm, "_interpret_cached",
                          return_value=(_plan(["p"]), 0, 0, 0, 0.0)), \
             patch.object(arm, "_embed", side_effect=_fake_embed), \
             patch.object(arm, "_resolve_chunk",
                          side_effect=lambda row, cache: (texts[row["chunkId"]],
                                                          list(ids[row["chunkId"]]))), \
             patch.object(arm, "_sufficient_cut") as review:
            out = arm.answer_one_question(("q::a::0", "q?"), prepared, None,
                                          k=2, char_budget=12)
        review.assert_not_called()
        self.assertEqual(sum(len(c) for c in out.contexts), 12)
        self.assertEqual(out.contexts, ["A" * 8, "B" * 4])
        self.assertEqual(out.context_ids, ["a1"])
        self.assertEqual(out.meta["char_budget"]["boundary"]["id"], "c2")
        self.assertEqual(out.meta["chunk_ids"], [["a1"], ["a2"]])
        self.assertEqual(out.meta["returned"], 2)
        self.assertNotIn("review", out.meta)

    def test_the_det_leg_consumes_its_ranking_the_same_way(self):
        ground = [[_ground_row("near_a", 0.9, [1.0, 0.0])]]
        chunks = {("near_a",): [_row("c1", 0.8), _row("c2", 0.7)]}
        prepared = self._prepared(_Session(ground, chunks))
        texts = {"c1": "A" * 8, "c2": "B" * 8}
        with patch.dict(det._PRODUCTS, {arm.DATABASE: []}, clear=True), \
             patch.object(arm, "_embed", side_effect=_fake_embed), \
             patch.object(arm, "_resolve_chunk",
                          side_effect=lambda row, cache: (texts[row["chunkId"]],
                                                          ["x1"])):
            out = det.answer_one_question(("q::a::0", "where is the alpha spec?"),
                                          prepared, None, k=1, char_budget=10)
        self.assertEqual(sum(len(c) for c in out.contexts), 10)
        self.assertEqual(out.contexts, ["A" * 8, "BB"])
        self.assertEqual(out.context_ids, ["x1"])
        self.assertEqual(out.meta["char_budget"],
                         {"budget": 10, "chars": 10, "kept": 1,
                          "boundary": {"id": "c2", "chars_kept": 2,
                                       "chars_full": 8},
                          "exhausted": False})


if __name__ == "__main__":
    unittest.main()

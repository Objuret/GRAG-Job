"""The fill-to-budget contract: exact-N context text, whole-ids-only context_ids,
the boundary-fragment record, and the pool-exhaustion case — on the shared cut
math, the baseline arms, and the harness plumbing, with synthetic fixtures only."""
import os
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import numpy as np

import orchestrator
import run
from char_budget import cut_at_budget
from contract import ArmOutput, BuildStats, ModelUsage, QuestionWithTruth
from pipelines import lucene, vector


class CutMathTests(unittest.TestCase):
    def test_the_crossing_unit_is_cut_to_exactly_the_budget(self):
        cut = cut_at_budget([("a", "x" * 10), ("b", "y" * 10), ("c", "z" * 10)], 14)
        self.assertEqual(cut.contexts, ["x" * 10, "yyyy"])
        self.assertEqual(sum(len(c) for c in cut.contexts), 14)
        self.assertEqual((cut.kept, cut.chars), (1, 14))
        self.assertEqual(cut.boundary,
                         {"id": "b", "chars_kept": 4, "chars_full": 10})
        self.assertFalse(cut.exhausted)

    def test_a_budget_landing_on_a_whole_unit_cuts_nothing(self):
        cut = cut_at_budget([("a", "x" * 6), ("b", "y" * 4), ("c", "z" * 9)], 10)
        self.assertEqual(cut.contexts, ["x" * 6, "y" * 4])
        self.assertEqual((cut.kept, cut.chars), (2, 10))
        self.assertIsNone(cut.boundary)
        self.assertFalse(cut.exhausted)

    def test_a_first_unit_over_the_budget_becomes_the_only_fragment(self):
        cut = cut_at_budget([("a", "x" * 100)], 7)
        self.assertEqual(cut.contexts, ["x" * 7])
        self.assertEqual(cut.kept, 0)
        self.assertEqual(cut.boundary,
                         {"id": "a", "chars_kept": 7, "chars_full": 100})

    def test_an_exhausted_ranking_records_its_true_total(self):
        cut = cut_at_budget([("a", "x" * 3), ("b", "y" * 4)], 100)
        self.assertEqual(cut.contexts, ["x" * 3, "y" * 4])
        self.assertEqual((cut.kept, cut.chars), (2, 7))
        self.assertIsNone(cut.boundary)
        self.assertTrue(cut.exhausted)

    def test_an_empty_text_keeps_its_slot_without_spending_budget(self):
        cut = cut_at_budget([("a", ""), ("b", "y" * 4)], 4)
        self.assertEqual(cut.contexts, ["", "y" * 4])
        self.assertEqual((cut.kept, cut.chars), (2, 4))

    def test_consumption_is_lazy_past_the_cut(self):
        pulled = []

        def stream():
            for uid, text in [("a", "x" * 5), ("b", "y" * 5), ("c", "z" * 5)]:
                pulled.append(uid)
                yield uid, text

        cut_at_budget(stream(), 7)
        self.assertEqual(pulled, ["a", "b"])

    def test_a_budget_below_one_fails_loud(self):
        with self.assertRaisesRegex(ValueError, "char budget"):
            cut_at_budget([("a", "x")], 0)


class VectorBudgetTests(unittest.TestCase):
    @staticmethod
    def _prepared():
        return vector.Prepared(
            matrix=np.eye(3, dtype=np.float32),
            ids=["d0", "d1", "d2"],
            texts=["x" * 10, "y" * 7, "z" * 5],
            query_vecs={"q::a::0": np.array([1.0, 0.6, 0.3], dtype=np.float32)})

    def test_budget_mode_returns_exactly_n_chars_and_whole_ids_only(self):
        out = vector.answer_one_question(("q::a::0", "q?"), self._prepared(),
                                         None, k=1, char_budget=13)
        self.assertEqual(sum(len(c) for c in out.contexts), 13)
        self.assertEqual(out.contexts, ["x" * 10, "yyy"])
        self.assertEqual(out.context_ids, ["d0"])
        self.assertEqual(out.meta["char_budget"],
                         {"budget": 13, "chars": 13, "kept": 1,
                          "boundary": {"id": "d1", "chars_kept": 3,
                                       "chars_full": 7},
                          "exhausted": False})

    def test_an_exhausted_corpus_records_its_true_total(self):
        out = vector.answer_one_question(("q::a::0", "q?"), self._prepared(),
                                         None, k=1, char_budget=100)
        block = out.meta["char_budget"]
        self.assertEqual(block["chars"], 22)
        self.assertTrue(block["exhausted"])
        self.assertIsNone(block["boundary"])
        self.assertEqual(out.context_ids, ["d0", "d1", "d2"])

    def test_without_a_budget_the_k_cut_stands(self):
        out = vector.answer_one_question(("q::a::0", "q?"), self._prepared(),
                                         None, k=2)
        self.assertEqual(out.context_ids, ["d0", "d1"])
        self.assertIsNone(out.meta)


class LuceneBudgetTests(unittest.TestCase):
    _QUESTION = ("q::a::0", "alpha rocket?")

    @staticmethod
    def _prepared():
        docs = [
            {"id": "a1", "title": "alpha", "contents": "alpha alpha rocket engine"},
            {"id": "a2", "title": "alpha", "contents": "alpha rocket"},
            {"id": "a3", "title": "beta", "contents": "unrelated filler words"},
        ]
        return lucene.build_sparse_index(docs)

    def test_budget_mode_returns_exactly_n_chars_and_whole_ids_only(self):
        prepared = self._prepared()
        units = lucene.retrieve_top_k_units(self._QUESTION, prepared,
                                            len(prepared.ids))
        budget = len(units[0]["text"]) + 3
        out = lucene.answer_one_question(self._QUESTION, prepared, None,
                                         k=1, char_budget=budget)
        self.assertEqual(sum(len(c) for c in out.contexts), budget)
        self.assertEqual(out.contexts[0], units[0]["text"])
        self.assertEqual(out.contexts[1], units[1]["text"][:3])
        self.assertEqual(out.context_ids, [units[0]["id"]])
        self.assertEqual(out.meta["char_budget"]["boundary"],
                         {"id": units[1]["id"], "chars_kept": 3,
                          "chars_full": len(units[1]["text"])})
        self.assertFalse(out.meta["char_budget"]["exhausted"])

    def test_the_ranking_ends_at_the_zero_score_tail_and_exhausts_truthfully(self):
        prepared = self._prepared()
        units = lucene.retrieve_top_k_units(self._QUESTION, prepared,
                                            len(prepared.ids))
        scored = [u for u in units if u["score"] > 0.0]
        self.assertLess(len(scored), len(units))  # the fixture has a no-match doc
        out = lucene.answer_one_question(self._QUESTION, prepared, None,
                                         k=1, char_budget=10_000)
        block = out.meta["char_budget"]
        self.assertTrue(block["exhausted"])
        self.assertEqual(block["chars"], sum(len(u["text"]) for u in scored))
        self.assertEqual(sorted(out.context_ids), sorted(u["id"] for u in scored))
        self.assertNotIn("a3", out.context_ids)
        self.assertIsNone(block["boundary"])

    def test_without_a_budget_the_k_cut_stands(self):
        out = lucene.answer_one_question(self._QUESTION, self._prepared(),
                                         None, k=2)
        self.assertEqual(len(out.context_ids), 2)
        self.assertIsNone(out.meta)


class OrchestratorPassthroughTests(unittest.TestCase):
    def test_run_one_pipeline_hands_the_arm_the_budget(self):
        prepared = types.SimpleNamespace(build_stats=BuildStats(0.0, ModelUsage(), []))
        seen = []

        def arm(q, prep, generate, k, char_budget=None):
            seen.append(char_budget)
            return ArmOutput("a", ["ctx"], ["cit"], 0.0, ModelUsage(), ModelUsage())

        pipe = types.SimpleNamespace(__name__="pipelines.fake",
                                     prepare_over_corpus=lambda c: prepared,
                                     answer_one_question=arm)
        qs = [QuestionWithTruth("p::a::0", "q?", "person", [], [])]
        with tempfile.TemporaryDirectory() as d:
            orchestrator.run_one_pipeline(pipe, qs, "c/", None, d, workers=1,
                                          char_budget=42)
        self.assertEqual(seen, [42])

    def test_the_manifest_records_the_budget(self):
        bs = BuildStats(0.0, ModelUsage(), [])
        self.assertEqual(orchestrator.build_run_manifest(
            {"char_budget": 72000}, "vector", bs, 1, 1, 0).char_budget, 72000)
        self.assertIsNone(orchestrator.build_run_manifest(
            {}, "vector", bs, 1, 1, 0).char_budget)


class RunCliTests(unittest.TestCase):
    def test_the_budget_run_folder_carries_the_cb_tag(self):
        _, out_dir = run._resolve_set("gold", "vector", 5,
                                      "cb72000__20260101T000000Z")
        self.assertTrue(out_dir.name.startswith("vector__gold100__cb72000__"))

    def test_an_unsupported_arm_is_rejected(self):
        argv = ["run.py", "--arm", "hybrid", "--char-budget", "100"]
        with patch.object(sys, "argv", argv):
            with self.assertRaises(SystemExit):
                run.main()

    def test_a_non_positive_budget_is_rejected(self):
        argv = ["run.py", "--arm", "vector", "--char-budget", "0"]
        with patch.object(sys, "argv", argv):
            with self.assertRaises(SystemExit):
                run.main()

    def test_rejudge_does_not_combine_with_the_budget(self):
        argv = ["run.py", "--rejudge", "x", "--judge", "claude-haiku-4-5",
                "--char-budget", "5"]
        with patch.dict(os.environ), patch.object(sys, "argv", argv):
            with self.assertRaises(SystemExit):
                run.main()


if __name__ == "__main__":
    unittest.main()

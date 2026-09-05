import contextlib
import io
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

import export_raw
from harness import orchestrator
import run
from harness.char_budget import cut_at_budget
from harness.contract import ArmOutput, BuildStats, ModelUsage, QuestionWithTruth
from arms import lucene, vector


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
        self.assertLess(len(scored), len(units))
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

        pipe = types.SimpleNamespace(__name__="arms.fake",
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


class ExhaustionRecordTests(unittest.TestCase):

    @staticmethod
    def _pipeline(exhausted_ids):
        prepared = types.SimpleNamespace(build_stats=BuildStats(0.0, ModelUsage(), []))

        def answer(q, prep, generate, k, char_budget=None):
            meta = None if char_budget is None else {"char_budget": {
                "budget": char_budget, "chars": 4, "kept": 1, "boundary": None,
                "exhausted": q[0] in exhausted_ids}}
            return ArmOutput("", ["ctx!"], ["cit"], 0.0, ModelUsage(), ModelUsage(),
                             meta)

        return types.SimpleNamespace(__name__="arms.budgetfake",
                                     prepare_over_corpus=lambda c: prepared,
                                     answer_one_question=answer)

    def _run(self, d, exhausted_ids, config):
        root = Path(d)
        (root / "corpus" / "products").mkdir(parents=True)
        (root / "q.jsonl").write_text("".join(
            json.dumps({"id": f"b::a::{i}", "question": f"b{i}?", "type": "person",
                        "ground_truth": [], "citations": []}) + "\n"
            for i in range(3)), encoding="utf-8")
        (root / "ids.jsonl").write_text("".join(
            json.dumps({"id": f"b::a::{i}"}) + "\n" for i in range(3)),
            encoding="utf-8")
        summary = orchestrator.run(
            self._pipeline(exhausted_ids), None, root / "ids.jsonl",
            {"questions_path": root / "q.jsonl", "corpus_root": root / "corpus",
             "out_dir": str(root / "run"), "retrieval_only": True, **config})
        manifest = json.loads((root / "run" / "run_manifest.json")
                              .read_text(encoding="utf-8"))
        return summary, manifest

    def test_the_manifest_and_summary_count_the_questions_that_ran_dry(self):
        with tempfile.TemporaryDirectory() as d:
            summary, manifest = self._run(d, {"b::a::0", "b::a::2"},
                                          {"char_budget": 100})
        self.assertEqual(summary["n_exhausted"], 2)
        self.assertEqual(manifest["n_exhausted"], 2)
        self.assertEqual((manifest["char_budget"], manifest["n_ran"]), (100, 3))

    def test_a_run_that_filled_its_budget_states_the_zero(self):
        with tempfile.TemporaryDirectory() as d:
            summary, manifest = self._run(d, set(), {"char_budget": 100})
        self.assertEqual(summary["n_exhausted"], 0)
        self.assertEqual(manifest["n_exhausted"], 0)

    def test_a_depth_run_has_no_budget_to_fall_short_of(self):
        with tempfile.TemporaryDirectory() as d:
            summary, manifest = self._run(d, set(), {"top_k": 50})
        self.assertIsNone(summary["n_exhausted"])
        self.assertIsNone(manifest["n_exhausted"])


class DepthModeTests(unittest.TestCase):

    def test_neither_flag_fills_to_the_default_budget(self):
        self.assertEqual(run.DEFAULT_CHAR_BUDGET, 72000)
        self.assertEqual(run._resolve_depth(None, None, "vector"),
                         (orchestrator.DEFAULT_TOP_K, 72000))

    def test_an_explicit_k_runs_the_depth_cut_with_no_budget(self):
        self.assertEqual(run._resolve_depth(15, None, "vector"), (15, None))
        self.assertEqual(run._resolve_depth(orchestrator.DEFAULT_TOP_K, None,
                                            "artefact_v1"), (50, None))

    def test_char_budget_sets_the_budget_the_run_fills_to(self):
        self.assertEqual(run._resolve_depth(None, 5000, "lucene"),
                         (orchestrator.DEFAULT_TOP_K, 5000))

    def test_an_arm_without_the_mode_needs_an_explicit_k(self):
        with self.assertRaisesRegex(SystemExit, "-k K"):
            run._resolve_depth(None, None, "hybrid")
        self.assertEqual(run._resolve_depth(50, None, "hybrid"), (50, None))

    def test_both_flags_together_fail_loud(self):
        argv = ["run.py", "--arm", "vector", "-k", "50", "--char-budget", "72000"]
        with patch.object(sys, "argv", argv):
            with self.assertRaises(SystemExit):
                run.main()

    def test_curve_walk_without_an_explicit_k_fails_loud(self):
        curve = types.SimpleNamespace(
            __name__="arms.artefact_v1",
            RETRIEVAL_FLAGS={"HERB_CURVE_WALK": True})
        argv = ["run.py", "--arm", "artefact_v1", "--set", "10smoke"]
        with patch.object(sys, "argv", argv), \
                patch.object(run.importlib, "import_module", return_value=curve):
            with self.assertRaisesRegex(SystemExit, "-k K"):
                run.main()


class RunCliTests(unittest.TestCase):
    def test_the_depth_run_folder_carries_no_cb_tag(self):
        _, out_dir = run._resolve_set("gold", "vector", 5, "20260101T000000Z",
                                      run._run_root(None))
        self.assertEqual(out_dir.name, "vector__gold100__20260101T000000Z")

    def test_the_budget_run_folder_carries_the_cb_tag(self):
        _, out_dir = run._resolve_set("gold", "vector", 5,
                                      "cb72000__20260101T000000Z",
                                      run._run_root(72000))
        self.assertTrue(out_dir.name.startswith("vector__gold100__cb72000__"))

    def test_the_depth_family_picks_the_run_root(self):
        self.assertEqual(run._run_root(72000), run.CHARS_ROOT)
        self.assertEqual(run._run_root(None), run.CHUNKS_ROOT)
        _, budget_dir = run._resolve_set("gold", "vector", 5, "s", run._run_root(72000))
        _, topk_dir = run._resolve_set("gold", "vector", 5, "s", run._run_root(None))
        self.assertEqual(budget_dir.parent, run.CHARS_ROOT)
        self.assertEqual(topk_dir.parent, run.CHUNKS_ROOT)

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


class OutRootTests(unittest.TestCase):

    def test_a_budget_run_is_refused_the_top_k_root(self):
        with self.assertRaisesRegex(SystemExit, run.CHARS_ROOT.name):
            run._checked_out(run.CHUNKS_ROOT / "vector__gold100__cb72000__t", 72000)

    def test_a_depth_run_is_refused_the_character_budget_root(self):
        with self.assertRaisesRegex(SystemExit, run.CHUNKS_ROOT.name):
            run._checked_out(run.CHARS_ROOT / "vector__gold100__t", None)

    def test_the_root_itself_is_the_same_refusal(self):
        with self.assertRaises(SystemExit):
            run._checked_out(run.CHUNKS_ROOT, 72000)

    def test_a_run_in_its_own_family_root_is_taken_as_given(self):
        named = run.CHARS_ROOT / "vector__gold100__cb72000__t"
        self.assertEqual(run._checked_out(named, 72000), named)
        depth = run.CHUNKS_ROOT / "vector__gold100__t"
        self.assertEqual(run._checked_out(depth, None), depth)

    def test_a_directory_outside_both_roots_is_the_callers_own(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(run._checked_out(Path(d) / "probe", 72000),
                             Path(d) / "probe")
            self.assertEqual(run._checked_out(Path(d) / "probe", None),
                             Path(d) / "probe")


class RunSummaryTests(unittest.TestCase):

    def _summary_line(self, depth_argv, summary):
        arm = types.SimpleNamespace(__name__="arms.vector", RETRIEVAL_FLAGS=None)
        out = io.StringIO()
        with tempfile.TemporaryDirectory() as d:
            ids = Path(d) / "ids.jsonl"
            ids.write_text(json.dumps({"id": "b::a::0"}) + "\n", encoding="utf-8")
            argv = ["run.py", "--arm", "vector", "--set", str(ids), "--no-eval",
                    "--out", str(Path(d) / "run"), *depth_argv]
            with patch.object(sys, "argv", argv), \
                    patch.object(run.importlib, "import_module", return_value=arm), \
                    patch.object(run.abort, "watch", lambda: None), \
                    patch.object(run.orchestrator, "run",
                                 return_value={"out_dir": str(Path(d) / "run"),
                                               **summary}), \
                    contextlib.redirect_stdout(out):
                run.main()
        return out.getvalue().splitlines()[-1]

    def test_a_budget_run_reports_how_many_questions_fell_short(self):
        line = self._summary_line(
            ["--char-budget", "72000"],
            {"n_questions": 10, "n_ran": 10, "n_failed": 0, "n_exhausted": 3})
        self.assertIn("3 did not fill the 72000 char budget", line)

    def test_a_filled_budget_run_states_the_zero(self):
        line = self._summary_line(
            ["--char-budget", "72000"],
            {"n_questions": 10, "n_ran": 10, "n_failed": 0, "n_exhausted": 0})
        self.assertIn("0 did not fill the 72000 char budget", line)

    def test_a_depth_run_says_nothing_about_a_budget(self):
        line = self._summary_line(
            ["-k", "50"],
            {"n_questions": 10, "n_ran": 10, "n_failed": 0, "n_exhausted": None})
        self.assertNotIn("budget", line)
        self.assertIn("10/10 answered, 0 failed", line)


class ExportRootTests(unittest.TestCase):

    ROWS = ('{"question_id": "b::a::0", "type": "person", "metric": "m", '
            '"value": 1.0, "status": "ok"}\n'
            '{"question_id": "b::a::1", "type": "person", "metric": "m", '
            '"value": 0.0, "status": "error"}\n')

    def _folder(self, root, name, manifest=None):
        d = root / name
        d.mkdir(parents=True)
        (d / "eval_results.jsonl").write_text(self.ROWS, encoding="utf-8")
        if manifest is not None:
            (d / "run_manifest.json").write_text(json.dumps(manifest),
                                                 encoding="utf-8")
        return d

    def test_the_export_reads_the_engine_s_top_k_root(self):
        self.assertEqual(export_raw.RUNS, orchestrator.CHUNKS_ROOT)

    def test_budget_runs_are_excluded_and_k_runs_are_exported(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "k=chunks"
            root.mkdir()
            self._folder(root, "vector__gold100__20260101T000000Z__k10")
            self._folder(root, "lucene__gold100__20260102T000000Z",
                         {"top_k": 50, "char_budget": None})
            self._folder(root, "vector__gold100__20260103T000000Z",
                         {"top_k": 50, "char_budget": 72000})
            out = Path(d) / "raw.csv"
            argv = ["export_raw.py", "--out", str(out)]
            with patch.object(export_raw, "RUNS", root), \
                    patch.object(sys, "argv", argv), \
                    contextlib.redirect_stdout(io.StringIO()):
                export_raw.main()
            rows = [x for x in out.read_text(encoding="utf-8").splitlines() if x.strip()]
        self.assertEqual(rows[0], "arm,k,question_id,type,metric,value")
        self.assertEqual(sorted(rows[1:]),
                         ["lucene,50,b::a::0,person,m,1.0",
                          "vector,10,b::a::0,person,m,1.0"])


if __name__ == "__main__":
    unittest.main()

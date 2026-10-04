from __future__ import annotations

import json
import threading
import time
import unittest
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from harness import jsonl
from harness import chat
from harness import orchestrator
from harness import provenance
from harness.contract import (
    ArmOutput, BuildStats, ModelUsage, model_usage_from_dict,
    model_usage_from_telemetry,
)


class TornAppendLogTests(unittest.TestCase):

    def test_a_torn_tail_is_dropped_by_the_reader(self):
        with TemporaryDirectory() as d:
            p = Path(d) / "a.jsonl"
            p.write_bytes(b'{"id": "q1"}\n{"id": "q2"')
            self.assertEqual(jsonl.load(p), [{"id": "q1"}])

    def test_corruption_that_is_not_the_tail_raises(self):
        with TemporaryDirectory() as d:
            p = Path(d) / "a.jsonl"
            p.write_bytes(b'{"id": "q1"\n{"id": "q2"}\n')
            with self.assertRaises(json.JSONDecodeError):
                jsonl.load(p)

    def test_healing_makes_the_file_appendable_again(self):
        with TemporaryDirectory() as d:
            p = Path(d) / "a.jsonl"
            p.write_bytes(b'{"id": "q1"}\n{"id": "q2"')
            with p.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"id": "q3"}) + "\n")
            self.assertEqual(jsonl.load(p), [{"id": "q1"}])

            p.write_bytes(b'{"id": "q1"}\n{"id": "q2"')
            jsonl.heal(p)
            with p.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"id": "q3"}) + "\n")
            self.assertEqual(jsonl.load(p), [{"id": "q1"}, {"id": "q3"}])

    def test_the_resume_set_survives_a_torn_tail(self):
        with TemporaryDirectory() as d:
            p = Path(d) / "arm_outputs.jsonl"
            p.write_bytes(b'{"id": "q1"}\n{"id": "q2"}\n{"id": "q3"')
            self.assertEqual(orchestrator._done_ids(p), {"q1", "q2"})


class TransportTimingTests(unittest.TestCase):
    """the per-thread timing every arm folds into its ModelUsage (the chat lane records it)"""

    def test_timing_is_per_thread(self):
        seen = {}

        def work():
            chat.reset_timing()
            chat._record_timing(3, 1.0, 2.0, 4.0)
            seen[threading.current_thread().name] = chat.take_timing()

        chat.reset_timing()
        chat._record_timing(1, 0.5, 0.0, 0.0)
        t = threading.Thread(target=work, name="w")
        t.start()
        t.join()
        self.assertEqual(seen["w"]["attempts"], 3)
        self.assertEqual(seen["w"]["retry_s"], 4.0)
        self.assertEqual(chat.take_timing()["attempts"], 1)

    def test_a_non_claude_model_is_refused_out_loud(self):
        with self.assertRaises(RuntimeError):
            chat.post("/chat/completions", {"model": "z-ai/glm-5.1"})
        with self.assertRaises(RuntimeError):
            chat.post("/chat/completions", {"model": "haiku"})


class UsageRoundTripTests(unittest.TestCase):
    def test_the_breakdown_survives_a_write_and_a_read(self):
        u = ModelUsage(calls=1, tokens_in=10, tokens_out=2, time_s=9.0,
                       attempts=2, request_s=3.0, wait_s=5.0, retry_s=1.0)
        back = model_usage_from_dict(json.loads(json.dumps(asdict(u))))
        self.assertEqual(back, u)

    def test_a_record_written_before_the_breakdown_reads_as_zero(self):
        old = {"calls": 1, "tokens_in": 10, "tokens_out": 2, "time_s": 9.0}
        back = model_usage_from_dict(old)
        self.assertEqual((back.attempts, back.request_s, back.wait_s, back.retry_s),
                         (0, 0.0, 0.0, 0.0))
        self.assertEqual(back.time_s, 9.0)

    def test_generator_telemetry_carries_the_breakdown_through(self):
        tel = {"calls": 1, "tokens_in": 7, "tokens_out": 1, "time": 4.0,
               "attempts": 1, "request_s": 2.0, "wait_s": 2.0, "retry_s": 0.0}
        u = model_usage_from_telemetry(tel)
        self.assertEqual((u.request_s, u.wait_s, u.attempts), (2.0, 2.0, 1))


class ProvenanceTests(unittest.TestCase):
    def test_a_digest_moves_with_the_bytes(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            (root / "a.json").write_text('{"x": 1}', encoding="utf-8")
            before = provenance.tree_digest(root)
            (root / "a.json").write_text('{"x": 2}', encoding="utf-8")
            self.assertNotEqual(provenance.tree_digest(root)["sha256"], before["sha256"])

    def test_a_missing_input_is_unknown_not_a_failure(self):
        got = provenance.inputs(questions_file=Path("nope.jsonl"))
        self.assertIsNone(got["questions_sha256"])

    def test_the_manifest_names_code_machine_and_inputs(self):
        bs = BuildStats(0.0, ModelUsage(), [])
        m = orchestrator.build_run_manifest({}, "vector", bs, 1, 1, 0)
        self.assertEqual(set(m.code_version), {"commit", "branch", "dirty"})
        self.assertTrue(m.environment["python"])
        self.assertIn("packages", m.environment)
        self.assertIn("corpus", m.inputs)
        json.dumps(asdict(m))

    def test_the_manifest_records_the_flags_the_run_was_given(self):
        bs = BuildStats(0.0, ModelUsage(), [])
        m = orchestrator.build_run_manifest({"flags": {"HERB_X": "on"}}, "vector", bs, 1, 1, 0)
        self.assertEqual(m.flags, {"HERB_X": "on"})
        self.assertIsNone(orchestrator.build_run_manifest({}, "vector", bs, 1, 1, 0).flags)


class AnswerRecordTests(unittest.TestCase):
    def test_each_answer_is_stamped_with_when_it_landed(self):
        with TemporaryDirectory() as d:
            out = Path(d) / "run"

            class FakeArm:
                @staticmethod
                def prepare_over_corpus(corpus):
                    return type("P", (), {"build_stats": BuildStats(0.0, ModelUsage(), [])})()

                @staticmethod
                def answer_one_question(q, prepared, generate, k):
                    return ArmOutput("a", ["c"], ["i"], 0.1)

            qs = [orchestrator.questions.QuestionWithTruth("q1", "?", "person", [], [])]
            orchestrator.run_one_pipeline(FakeArm, qs, "c/", None, out, workers=1)

            rec = jsonl.load(out / "arm_outputs.jsonl")[0]
            self.assertIn("answered_at", rec)
            self.assertTrue(rec["answered_at"].endswith("+00:00"))


if __name__ == "__main__":
    unittest.main()

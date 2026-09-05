from __future__ import annotations

import json
import threading
import time
import unittest
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import httpx

from harness import jsonl
from harness import nim
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

    def setUp(self):
        nim.reset_timing()

    def test_a_clean_call_is_all_request_time(self):
        with TemporaryDirectory():
            with patch.object(nim, "_wait_my_turn", lambda *a, **k: None), \
                 patch.object(httpx, "post", side_effect=self._ok):
                nim.post("/chat/completions", {"model": "m"})
            t = nim.take_timing()
        self.assertEqual(t["attempts"], 1)
        self.assertEqual(t["retry_s"], 0.0)
        self.assertGreater(t["request_s"], 0.0)

    def test_queueing_lands_in_wait_not_in_request(self):
        def slow_turn(*a, **k):
            time.sleep(0.05)

        with patch.object(nim, "_wait_my_turn", slow_turn), \
             patch.object(httpx, "post", side_effect=self._ok):
            nim.post("/chat/completions", {"model": "m"})
        t = nim.take_timing()
        self.assertGreater(t["wait_s"], 0.02)
        self.assertLess(t["request_s"], t["wait_s"])

    def test_a_retried_call_separates_the_failure_cost(self):
        calls = {"n": 0}

        def flaky(url, json, headers, timeout):
            calls["n"] += 1
            if calls["n"] == 1:
                return httpx.Response(503, text="busy", request=httpx.Request("POST", url))
            return httpx.Response(200, json={"ok": True},
                                  request=httpx.Request("POST", url))

        with patch.object(nim, "_wait_my_turn", lambda *a, **k: None), \
             patch.object(nim, "_back_off", lambda *a, **k: None), \
             patch.object(httpx, "post", side_effect=flaky):
            nim.post("/chat/completions", {"model": "m"})
        t = nim.take_timing()
        self.assertEqual(t["attempts"], 2)
        self.assertGreater(t["retry_s"], 0.0)

    def test_a_call_that_gave_up_still_reports_what_it_spent(self):
        def dead(url, json, headers, timeout):
            return httpx.Response(503, text="down", request=httpx.Request("POST", url))

        with patch.object(nim, "_wait_my_turn", lambda *a, **k: None), \
             patch.object(nim, "_back_off", lambda *a, **k: None), \
             patch.object(httpx, "post", side_effect=dead):
            with self.assertRaises(RuntimeError):
                nim.post("/chat/completions", {"model": "m"}, max_tries=2)
        t = nim.take_timing()
        self.assertEqual(t["attempts"], 2)
        self.assertGreater(t["retry_s"], 0.0)

    def test_timing_is_per_thread(self):
        seen = {}

        def worker():
            nim.reset_timing()
            nim._record_timing(3, 1.0, 2.0, 4.0)
            seen[threading.current_thread().name] = nim.take_timing()

        nim._record_timing(1, 0.5, 0.0, 0.0)
        threads = [threading.Thread(target=worker, name=f"w{i}") for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        for got in seen.values():
            self.assertEqual(got["attempts"], 3)
            self.assertEqual(got["retry_s"], 4.0)
        self.assertEqual(nim.take_timing()["attempts"], 1)

    @staticmethod
    def _ok(url, json, headers, timeout):
        time.sleep(0.01)
        return httpx.Response(200, json={"ok": True}, request=httpx.Request("POST", url))


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

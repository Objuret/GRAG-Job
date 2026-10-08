"""A run is one question, and everything it did is kept: every model call whole, every embed
request, its stamps, and every start or resume of the folder it was written into."""
from __future__ import annotations

import asyncio
import json
import subprocess
import threading
import types
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np

from harness import capture
from harness import chat
from harness import embed
from harness import jsonl
from harness import orchestrator
from harness.contract import (
    ArmOutput, BuildStats, ModelUsage, QuestionWithTruth, model_usage_from_dict,
    model_usage_from_telemetry,
)

ENVELOPE = {"type": "result", "subtype": "success", "is_error": False, "duration_ms": 1500,
            "duration_api_ms": 2200, "ttft_ms": 1400, "num_turns": 1, "result": "ok",
            "stop_reason": "end_turn", "session_id": "s", "total_cost_usd": 0.0125,
            "usage": {"input_tokens": 100, "cache_creation_input_tokens": 20,
                      "cache_read_input_tokens": 30, "output_tokens": 7},
            "modelUsage": {"claude-haiku-4-5": {"inputTokens": 100, "costUSD": 0.0125}}}


def _proc(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(["claude"], returncode, stdout, stderr)


class ChatCallRecordTests(unittest.TestCase):
    def _post(self, **kw):
        return chat.post("/chat/completions", {
            "model": "claude-haiku-4-5", "temperature": 0,
            "messages": [{"role": "system", "content": "SYS"},
                         {"role": "user", "content": "the prompt as sent"}],
            "response_format": {"json_schema": {"schema": {"type": "object"}}}}, **kw)

    def test_a_call_is_kept_whole_and_handed_to_the_open_capture(self):
        cap, token = capture.start()
        try:
            with patch.object(chat.subprocess, "run",
                              return_value=_proc(0, json.dumps(ENVELOPE), "warn")):
                resp = self._post()
        finally:
            capture.stop(token)
        kept = cap.close()["calls"]
        self.assertEqual(len(kept), 1)
        rec = kept[0]
        self.assertEqual((rec["kind"], rec["seq"], rec["ok"]), ("chat", 0, True))
        self.assertEqual((rec["system"], rec["prompt"]), ("SYS", "the prompt as sent"))
        self.assertEqual(rec["schema"], {"type": "object"})
        self.assertEqual(rec["envelope"], ENVELOPE)
        self.assertEqual(rec["envelope"]["total_cost_usd"], 0.0125)
        self.assertNotIn("cost_usd", rec)
        self.assertEqual(rec["usage"], {"prompt_tokens": 150, "completion_tokens": 7,
                                        "cached_input_tokens": 30})
        self.assertEqual(rec["stderr"], "warn")
        self.assertEqual(rec["payload_dropped"], ["temperature"])
        self.assertIn("--safe-mode", rec["flags"])
        self.assertEqual([a["outcome"] for a in rec["attempts"]], ["ok"])
        self.assertTrue(rec["started_at"] and rec["finished_at"])
        self.assertEqual(resp["call"], {k: v for k, v in rec.items() if k != "seq"})
        self.assertEqual(resp["num_turns"], 1)
        self.assertNotIn("cost_usd", resp)
        json.dumps(rec)

    def test_every_failed_try_is_kept_and_a_call_that_gives_up_is_still_recorded(self):
        outcomes = [_proc(1, "", "boom"), _proc(0, "not json", ""),
                    subprocess.TimeoutExpired(["claude"], 1.0)]

        def run(*a, **k):
            nxt = outcomes.pop(0)
            if isinstance(nxt, BaseException):
                raise nxt
            return nxt

        cap, token = capture.start()
        try:
            with patch.object(chat.subprocess, "run", side_effect=run), \
                    patch.object(chat.time, "sleep", lambda s: None):
                with self.assertRaises(RuntimeError):
                    self._post(max_tries=3)
        finally:
            capture.stop(token)
        rec = cap.close()["calls"][0]
        self.assertFalse(rec["ok"])
        self.assertEqual([a["outcome"] for a in rec["attempts"]],
                         ["exit", "bad_envelope", "timeout"])
        self.assertEqual(rec["attempts"][0]["stderr"], "boom")
        self.assertEqual(rec["attempts"][1]["stdout"], "not json")
        self.assertTrue(rec["error"] and rec["finished_at"])

    def test_without_an_open_capture_a_call_works_as_before(self):
        with patch.object(chat.subprocess, "run",
                          return_value=_proc(0, json.dumps(ENVELOPE), "")):
            resp = self._post()
        self.assertEqual(resp["choices"][0]["message"]["content"], "ok")


class CaptureTests(unittest.TestCase):
    def test_a_capture_is_per_thread_and_carried_only_on_request(self):
        cap, token = capture.start()
        try:
            seen = []
            t = threading.Thread(target=lambda: seen.append(capture._active.get()))
            t.start()
            t.join()
            self.assertEqual(seen, [None])
            with ThreadPoolExecutor(max_workers=1) as ex:
                ex.submit(capture.carry(capture.record, {"kind": "embed", "n_texts": 2,
                                                         "tokens_in": 5, "encode_s": 0.25})).result()
        finally:
            capture.stop(token)
        kept = cap.close()
        self.assertEqual(len(kept["calls"]), 1)
        self.assertEqual(capture.totals(kept["calls"])["embed_tokens"], 5)
        self.assertIsNone(capture._active.get())
        capture.record({"kind": "chat"})

    def test_the_judge_call_on_a_pool_thread_lands_in_the_cells_capture(self):
        from eval import ragas as scorer

        def fake_post(path, payload, **kw):
            capture.record({"kind": "chat", "usage": {"prompt_tokens": 9, "completion_tokens": 1,
                                                      "cached_input_tokens": 0},
                            "attempts": [{"seconds": 2.0}]})
            return {"choices": [{"message": {"content": "verdict"}}],
                    "usage": {"prompt_tokens": 9, "completion_tokens": 1}}

        judge = scorer._JudgeLLM()
        prompt = types.SimpleNamespace(to_string=lambda: "judge this")
        scorer.LAST_JUDGE_USAGE = ModelUsage()
        cap, token = capture.start()
        try:
            with patch.object(scorer.chat, "post", fake_post):
                out = asyncio.run(judge.agenerate_text(prompt))
        finally:
            capture.stop(token)
        self.assertEqual(out.generations[0][0].text, "verdict")
        total = capture.totals(cap.close()["calls"])
        self.assertEqual((total["chat_calls"], total["tokens_in"], total["chat_s"]), (1, 9, 2.0))
        self.assertNotIn("cost_usd", total)
        self.assertEqual(scorer.LAST_JUDGE_USAGE.calls, 1)


class EmbedRecordTests(unittest.TestCase):
    def test_an_embed_request_is_kept_with_its_texts_tokens_and_times(self):
        fake = types.SimpleNamespace(
            max_seq_length=8192,
            tokenizer=lambda texts, **kw: {"input_ids": [[1] * (len(t) // 2) for t in texts]},
            encode=lambda texts, **kw: np.ones((len(texts), 3), dtype=np.float32))
        embed.take_totals()
        cap, token = capture.start()
        try:
            with patch.object(embed, "_embedder", lambda: fake):
                mat, calls, tokens_in, _, _ = embed._embed(["abcd", "ef"], "query", bar=False)
        finally:
            capture.stop(token)
        recs = cap.close()["calls"]
        self.assertEqual([r["texts"] for r in recs], [["abcd"], ["ef"]])
        self.assertEqual(recs[0]["input_type"], "query")
        self.assertEqual(recs[0]["tokens_in"], len("query: abcd") // 2)
        self.assertGreaterEqual(recs[0]["encode_s"], 0.0)
        self.assertEqual(calls, 2)
        self.assertEqual(embed.take_totals()["texts"], 2)
        self.assertEqual(embed.take_totals()["texts"], 0)


class RunRowTests(unittest.TestCase):
    QS = [QuestionWithTruth(f"q{i}", f"question {i}?", "person", [], []) for i in range(3)]

    @staticmethod
    def _arm(fail=()):
        prepared = types.SimpleNamespace(build_stats=BuildStats(0.0, ModelUsage(), []))

        def answer(q, prep, generate, k):
            capture.record({"kind": "embed", "n_texts": 1, "tokens_in": 4, "encode_s": 0.1})
            if q[0] in fail:
                raise RuntimeError("lane down")
            return ArmOutput("a", ["c"], ["i"], 0.1)

        return types.SimpleNamespace(__name__="arms.fake", prepare_over_corpus=lambda c: prepared,
                                     answer_one_question=answer,
                                     index_info=lambda p: {"units": 1})

    def test_a_row_keeps_its_leg_its_stamps_and_everything_it_called(self):
        with TemporaryDirectory() as d:
            orchestrator.run_one_pipeline(self._arm(), self.QS, "c/", None, d, workers=2, leg=4)
            rows = jsonl.load(Path(d) / "arm_outputs.jsonl")
            self.assertEqual([r["id"] for r in rows], ["q0", "q1", "q2"])
            for r in rows:
                self.assertEqual(r["leg"], 4)
                self.assertEqual([c["kind"] for c in r["calls"]], ["embed"])
                self.assertGreaterEqual(r["timing"]["wall_s"], 0.0)
                self.assertTrue(r["timing"]["started_at"] <= r["timing"]["finished_at"])
            self.assertEqual(orchestrator._rehydrate(rows[0]).answer, "a")

    def test_failed_tries_stay_on_record_across_resumes_with_what_they_spent(self):
        with TemporaryDirectory() as d:
            orchestrator.run_one_pipeline(self._arm(fail={"q1"}), self.QS, "c/", None, d,
                                          workers=1, leg=1)
            orchestrator.run_one_pipeline(self._arm(fail={"q1"}), self.QS, "c/", None, d,
                                          workers=1, leg=2)
            orchestrator.run_one_pipeline(self._arm(), self.QS, "c/", None, d, workers=1, leg=3)
            fails = jsonl.load(Path(d) / "failures.jsonl")
            self.assertEqual([(f["id"], f["leg"]) for f in fails], [("q1", 1), ("q1", 2)])
            self.assertTrue(all("lane down" in f["error"] and "Traceback" in f["traceback"]
                                for f in fails))
            self.assertEqual([c["kind"] for c in fails[0]["calls"]], ["embed"])
            rows = jsonl.load(Path(d) / "arm_outputs.jsonl")
            self.assertEqual(sorted((r["id"], r["leg"]) for r in rows),
                             [("q0", 1), ("q1", 3), ("q2", 1)])

    def test_every_start_of_a_folder_is_a_leg_and_an_idle_leg_changes_nothing_else(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            (root / "corpus" / "products").mkdir(parents=True)
            (root / "q.jsonl").write_text("".join(
                json.dumps({"id": q.id, "question": q.question, "type": q.type,
                            "ground_truth": [], "citations": []}) + "\n" for q in self.QS),
                encoding="utf-8")
            ids = root / "ids.jsonl"
            ids.write_text("".join(json.dumps({"id": q.id}) + "\n" for q in self.QS),
                           encoding="utf-8")
            cfg = {"questions_path": root / "q.jsonl", "corpus_root": root / "corpus",
                   "out_dir": str(root / "run"), "retrieval_only": True, "workers": 3}
            orchestrator.run(self._arm(fail={"q2"}), None, ids, cfg)
            first = json.loads((root / "run" / "run_manifest.json").read_text(encoding="utf-8"))
            orchestrator.run(self._arm(), None, ids, {**cfg, "workers": 5})
            second = json.loads((root / "run" / "run_manifest.json").read_text(encoding="utf-8"))
            orchestrator.run(self._arm(), None, ids, {**cfg, "workers": 7})
            third = json.loads((root / "run" / "run_manifest.json").read_text(encoding="utf-8"))

            self.assertEqual([leg["leg"] for leg in third["legs"]], [1, 2, 3])
            self.assertEqual([leg["workers"] for leg in third["legs"]], [3, 5, 7])
            self.assertEqual([leg["n_answered"] for leg in third["legs"]], [2, 1, 0])
            self.assertEqual([leg["n_unanswered_after"] for leg in third["legs"]], [1, 0, 0])
            leg = third["legs"][0]
            for key in ("started_at", "finished_at", "wall_s", "argv", "pid", "python_executable",
                        "prepare_s", "peak_memory_bytes", "code_version", "code_state", "index"):
                self.assertIn(key, leg)
            self.assertEqual(leg["index"], {"units": 1})
            self.assertEqual((first["n_ran"], second["n_ran"]), (2, 3))
            self.assertEqual({k: v for k, v in third.items() if k != "legs"},
                             {k: v for k, v in second.items() if k != "legs"})
            self.assertEqual(second["workers"], 5)
            self.assertIn("python_executable", second["environment"])
            self.assertNotIn("diff", second["code_state"])


class DeliveredScoreTests(unittest.TestCase):
    """a baseline row keeps the score of every context it delivered, in delivered order"""

    def test_vector_keeps_the_cosine_of_each_delivered_context_and_of_the_next_one(self):
        from arms import vector
        prepared = vector.Prepared(matrix=np.eye(3, dtype=np.float32), ids=["d0", "d1", "d2"],
                                   texts=["x" * 10, "y" * 7, "z" * 5])
        qvec = np.array([[1.0, 0.5, 0.25]], dtype=np.float32)
        with patch.object(vector, "_embed", lambda texts, mode, bar=True: (qvec, 1, 4, 0, 0.5)):
            out = vector.answer_one_question(("q", "q?"), prepared, None, k=1, char_budget=13)
        self.assertEqual(out.contexts, ["x" * 10, "yyy"])
        self.assertEqual(out.meta["ranking"],
                         {"n_units": 3, "n_ranked": 3, "scores": [1.0, 0.5], "next_score": 0.25})

    def test_lucene_keeps_the_score_of_each_delivered_context(self):
        from arms import lucene
        docs = [{"id": f"d{i}", "title": "", "contents": text} for i, text in enumerate(
            ["alpha rocket launch " * 3, "alpha notes", "nothing here", "rocket rocket alpha"])]
        prepared = lucene.build_sparse_index(docs)
        out = lucene.answer_one_question(("q", "alpha rocket?"), prepared, None, k=1,
                                         char_budget=40)
        rank = out.meta["ranking"]
        self.assertEqual(len(rank["scores"]), len(out.contexts))
        self.assertEqual(rank["scores"], sorted(rank["scores"], reverse=True))
        self.assertEqual((rank["n_units"], rank["n_ranked"]), (4, 3))
        self.assertTrue(all(s > 0 for s in rank["scores"]))
        self.assertTrue(rank["next_score"] is None or rank["next_score"] <= rank["scores"][-1])


class EvaluationLegTests(unittest.TestCase):
    """every scoring leg of a folder keeps its own usage and settings, the first one too"""

    def _run(self, root, scorer):
        (root / "corpus" / "products").mkdir(parents=True, exist_ok=True)
        q = QuestionWithTruth("q0", "question?", "person", [], [])
        (root / "q.jsonl").write_text(json.dumps(
            {"id": q.id, "question": q.question, "type": q.type, "ground_truth": [],
             "citations": []}) + "\n", encoding="utf-8")
        (root / "ids.jsonl").write_text(json.dumps({"id": q.id}) + "\n", encoding="utf-8")
        orchestrator.run(RunRowTests._arm(), scorer, root / "ids.jsonl",
                         {"questions_path": root / "q.jsonl", "corpus_root": root / "corpus",
                          "out_dir": str(root / "run"), "retrieval_only": True, "workers": 1})
        return json.loads((root / "run" / "eval_manifest.json").read_text(encoding="utf-8"))

    @staticmethod
    def _scorer(calls, tokens, mark, fail=False):
        from harness.contract import EvalResult

        def score_outputs(outs, chosen, **kw):
            if fail:
                raise RuntimeError("judge backend down")
            return [EvalResult(q.id, q.type, "fake", "f1", 1.0, "ok", {}, None) for q in chosen]

        return types.SimpleNamespace(
            __name__="eval.fake", score_outputs=score_outputs,
            LAST_JUDGE_MODEL="claude-haiku-4-5", LAST_JUDGE_BACKEND="claude-cli",
            LAST_JUDGE_REASONING_EFFORT=None, LAST_JUDGE_WALL_TIME_S=1.5,
            LAST_JUDGE_USAGE=ModelUsage(calls=calls, tokens_in=tokens),
            LAST_JUDGE_SETTINGS={"started_at": mark, "workers": 1})

    def test_each_leg_keeps_its_settings_and_the_totals_add_up(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            first = self._run(root, self._scorer(6, 600, "leg-one"))
            self.assertEqual([leg["settings"]["started_at"] for leg in first["judge_legs"]],
                             ["leg-one"])
            second = self._run(root, self._scorer(0, 0, "leg-two"))
            third = self._run(root, self._scorer(2, 200, "leg-three"))
            self.assertEqual([leg["settings"]["started_at"] for leg in third["judge_legs"]],
                             ["leg-one", "leg-two", "leg-three"])
            self.assertEqual([leg["usage"]["calls"] for leg in third["judge_legs"]], [6, 0, 2])
            self.assertEqual((second["judge_usage"]["calls"], third["judge_usage"]["calls"]), (6, 8))
            self.assertEqual(third["judge_usage"]["tokens_in"], 800)
            self.assertEqual(third["judge_elapsed_s"], 4.5)

    def test_a_leg_cut_short_still_writes_what_it_spent(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            with self.assertRaises(RuntimeError):
                self._run(root, self._scorer(3, 300, "cut", fail=True))
            kept = json.loads((root / "run" / "eval_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(kept["judge_legs"][0]["usage"]["calls"], 3)
            self.assertEqual(kept["judge_legs"][0]["settings"]["started_at"], "cut")


class UsageBlockTests(unittest.TestCase):
    def test_cost_in_a_usage_block_is_calls_tokens_and_seconds_only(self):
        # 2026-10-08: "we do NOT care about monetary cost, cost only means compute or tokens
        # or time here"; the CLI's dollar figure stays inside the kept raw response, nowhere else
        from dataclasses import asdict
        u = model_usage_from_telemetry({"calls": 1, "tokens_in": 5, "tokens_out": 1,
                                        "time": 2.0, "cost_usd": 0.25})
        self.assertNotIn("cost_usd", asdict(u))
        self.assertEqual(model_usage_from_dict(json.loads(json.dumps(asdict(u)))), u)


if __name__ == "__main__":
    unittest.main()

"""What a model call carries is what the caller asked for and nothing left over from the shell or
from the user's own Claude settings; what could not be carried is said in the call's record. And
the run's record: the code is read before the start answers, an evaluation start leaves the rows
of scores it does not compute, and the judge that made the kept scores stays named."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import subprocess
import types
import unittest
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from harness import capture
from harness import chat
from harness import jsonl
from harness import orchestrator
from harness import provenance
from harness.contract import (
    ArmOutput, BuildStats, EvalResult, ModelUsage, QuestionWithTruth,
)

ENVELOPE = {"type": "result", "subtype": "success", "is_error": False, "num_turns": 1,
            "result": "ok", "stop_reason": "end_turn",
            "usage": {"input_tokens": 10, "output_tokens": 2}}
SONNET, HAIKU = "claude-sonnet-5", "claude-haiku-4-5-20251001"
NO_EFFORT = "none sent (the model's own default)"


def _user(text="the prompt"):
    return [{"role": "user", "content": text}]


def _flag(cmd, name):
    return cmd[cmd.index(name) + 1]


class CallSettingsTests(unittest.TestCase):
    def test_no_effort_named_means_none_is_sent(self):
        call = chat.call_settings({"model": SONNET, "messages": _user()})
        self.assertNotIn("--effort", call["cmd"])
        self.assertEqual(call["env_set"]["CLAUDE_CODE_EFFORT_LEVEL"], "auto")
        self.assertEqual(call["applied"]["effort"], NO_EFFORT)

    def test_a_named_effort_goes_as_the_flag(self):
        call = chat.call_settings({"model": SONNET, "messages": _user(), "effort": "low"})
        self.assertEqual(_flag(call["cmd"], "--effort"), "low")
        self.assertNotIn("CLAUDE_CODE_EFFORT_LEVEL", call["env_set"])
        self.assertIn("CLAUDE_CODE_EFFORT_LEVEL", call["env_unset"])
        self.assertEqual(call["applied"]["effort"], "low")
        with self.assertRaises(RuntimeError):
            chat.call_settings({"model": SONNET, "messages": _user(), "effort": "lots"})

    def test_the_system_prompt_is_always_passed_and_is_empty_when_the_call_has_none(self):
        bare = chat.call_settings({"model": HAIKU, "messages": _user()})
        self.assertEqual(_flag(bare["cmd"], "--system-prompt"), "")
        given = chat.call_settings({"model": HAIKU, "messages": [
            {"role": "system", "content": "SYS"}, *_user()]})
        self.assertEqual(_flag(given["cmd"], "--system-prompt"), "SYS")
        for call in (bare, given):
            self.assertEqual(_flag(call["cmd"], "--tools"), "")
            self.assertIn("--safe-mode", call["cmd"])

    def test_every_call_switches_the_title_request_and_the_billing_line_off(self):
        call = chat.call_settings({"model": HAIKU, "messages": _user()})
        self.assertEqual(call["env_set"]["CLAUDE_CODE_DISABLE_TERMINAL_TITLE"], "1")
        self.assertEqual(call["env_set"]["CLAUDE_CODE_ATTRIBUTION_HEADER"], "0")
        self.assertEqual(chat.lane_info()["env_set"], dict(chat._ENV_FIXED))

    def test_the_answer_call_gets_thinking_off_and_its_cap_and_says_the_temperature_is_refused(self):
        call = chat.call_settings({"model": SONNET, **orchestrator._GENERATOR_SETTINGS})
        self.assertEqual(call["env_set"]["MAX_THINKING_TOKENS"], "0")
        self.assertEqual(call["env_set"]["CLAUDE_CODE_MAX_OUTPUT_TOKENS"], "8192")
        self.assertNotIn("CLAUDE_CODE_EXTRA_BODY", call["env_set"])
        self.assertEqual(call["env_unset"], ["CLAUDE_CODE_EXTRA_BODY"])
        self.assertEqual(call["applied"], {"effort": NO_EFFORT, "thinking": "off",
                                           "max_output_tokens": 8192})
        self.assertEqual(sorted(call["not_applied"]), ["min_tokens", "temperature"])
        self.assertIn("refuses a temperature", call["not_applied"]["temperature"])
        info = orchestrator.generator_info({})
        self.assertEqual(info["payload"], orchestrator._GENERATOR_SETTINGS)
        self.assertEqual((info["applied"], info["not_applied"]),
                         (call["applied"], call["not_applied"]))

    def test_the_judge_call_gets_thinking_off_and_the_temperature_it_was_handed(self):
        call = chat.call_settings({"model": HAIKU, "messages": _user(), "temperature": 0.01,
                                   "thinking": False})
        self.assertEqual(call["env_set"]["MAX_THINKING_TOKENS"], "0")
        self.assertEqual(json.loads(call["env_set"]["CLAUDE_CODE_EXTRA_BODY"]),
                         {"temperature": 0.01})
        self.assertEqual(call["applied"], {"effort": NO_EFFORT, "thinking": "off",
                                           "temperature": 0.01})
        self.assertEqual(call["not_applied"], {})

    def test_a_cap_or_a_temperature_without_thinking_off_is_said_not_applied(self):
        call = chat.call_settings({"model": HAIKU, "messages": _user(), "temperature": 0,
                                   "max_tokens": 4000})
        for name in ("MAX_THINKING_TOKENS", "CLAUDE_CODE_MAX_OUTPUT_TOKENS",
                     "CLAUDE_CODE_EXTRA_BODY"):
            self.assertNotIn(name, call["env_set"])
            self.assertIn(name, call["env_unset"])
        self.assertEqual(call["applied"]["thinking"], "the model decides")
        self.assertEqual(sorted(call["not_applied"]), ["max_tokens", "temperature"])


class CallAsSentTests(unittest.TestCase):
    def _sent(self, payload, shell):
        seen = {}

        def run(cmd, **kw):
            seen.update(cmd=cmd, **kw)
            return subprocess.CompletedProcess(cmd, 0, json.dumps(ENVELOPE).encode("utf-8"), b"")

        cap, token = capture.start()
        try:
            with patch.dict(os.environ, shell), patch.object(chat.subprocess, "run", run):
                chat.post("/chat/completions", payload)
        finally:
            capture.stop(token)
        return seen, cap.close()["calls"][0]

    def test_the_prompt_reaches_the_cli_as_the_bytes_that_are_kept(self):
        prompt = "first line\nsecond line\n\nÅngström"
        seen, rec = self._sent({"model": HAIKU, "messages": _user(prompt)}, {})
        self.assertEqual(seen["input"], prompt.encode("utf-8"))
        self.assertNotIn(b"\r", seen["input"])
        self.assertNotIn("text", seen)
        self.assertEqual(rec["prompt"], prompt)

    def test_a_switch_left_in_the_shell_does_not_reach_a_call_that_did_not_ask_for_it(self):
        shell = {"MAX_THINKING_TOKENS": "0", "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "5",
                 "CLAUDE_CODE_EXTRA_BODY": '{"temperature": 1}',
                 "CLAUDE_CODE_EFFORT_LEVEL": "max", "CLAUDE_CODE_DISABLE_TERMINAL_TITLE": "0",
                 "HERB_KEPT": "yes"}
        seen, rec = self._sent({"model": SONNET, "messages": _user()}, shell)
        env = seen["env"]
        for name in ("MAX_THINKING_TOKENS", "CLAUDE_CODE_MAX_OUTPUT_TOKENS",
                     "CLAUDE_CODE_EXTRA_BODY"):
            self.assertNotIn(name, env)
        self.assertEqual(env["CLAUDE_CODE_EFFORT_LEVEL"], "auto")
        self.assertEqual(env["CLAUDE_CODE_DISABLE_TERMINAL_TITLE"], "1")
        self.assertEqual(env["CLAUDE_CODE_ATTRIBUTION_HEADER"], "0")
        self.assertEqual(env["MEMPALACE_HOOKS_AUTO_SAVE"], "false")
        self.assertEqual(env["HERB_KEPT"], "yes")
        self.assertEqual(rec["env_set"], {**chat._ENV_FIXED, "CLAUDE_CODE_EFFORT_LEVEL": "auto"})
        self.assertEqual(rec["env_unset"], ["MAX_THINKING_TOKENS", "CLAUDE_CODE_MAX_OUTPUT_TOKENS",
                                            "CLAUDE_CODE_EXTRA_BODY"])

    def test_the_kept_call_says_what_was_applied_and_what_was_not(self):
        seen, rec = self._sent({"model": SONNET, **orchestrator._GENERATOR_SETTINGS,
                                "messages": [{"role": "system", "content": "SYS"}, *_user()]}, {})
        self.assertEqual(seen["env"]["MAX_THINKING_TOKENS"], "0")
        self.assertEqual(seen["env"]["CLAUDE_CODE_MAX_OUTPUT_TOKENS"], "8192")
        self.assertEqual(rec["applied"], {"effort": NO_EFFORT, "thinking": "off",
                                          "max_output_tokens": 8192})
        self.assertEqual(rec["payload_dropped"], ["min_tokens", "temperature"])
        self.assertEqual(rec["payload_dropped"], sorted(rec["not_applied"]))
        self.assertTrue(rec["ok"])
        json.dumps(rec)


class JudgeCallTests(unittest.TestCase):
    def test_ragas_own_temperature_reaches_the_lane_with_no_system_text_and_thinking_off(self):
        from langchain_core.prompt_values import StringPromptValue
        from eval import ragas as scorer

        sent = []

        def fake_post(path, payload, **kw):
            sent.append((payload, kw))
            return {"choices": [{"message": {"content": "verdict"}}],
                    "usage": {"prompt_tokens": 9, "completion_tokens": 1}}

        judge = scorer._JudgeLLM(model=HAIKU)
        scorer.LAST_JUDGE_USAGE = ModelUsage()
        with patch.object(scorer.chat, "post", fake_post):
            # RAGAS's own entry point: it is what picks the temperature of a call
            out = asyncio.run(judge.generate(StringPromptValue(text="judge this")))
            asyncio.run(judge.agenerate_text(StringPromptValue(text="again"), temperature=0.1))
        self.assertEqual(out.generations[0][0].text, "verdict")
        payload, kw = sent[0]
        self.assertEqual(payload, {"model": HAIKU, "messages": _user("judge this"),
                                   "temperature": judge.get_temperature(1), "thinking": False})
        self.assertEqual(payload["temperature"], 0.01)
        self.assertEqual(kw["max_tries"], scorer.JUDGE_MAX_TRIES)
        self.assertEqual(sent[1][0]["temperature"], 0.1)

    def test_the_evaluation_records_what_a_judge_call_is_given(self):
        from eval import ragas as scorer

        self.assertEqual(scorer.JUDGE_BACKEND, "claude-cli")
        info = scorer.judge_call_info(scorer._JudgeLLM(model=HAIKU))
        self.assertEqual((info["model"], info["system"]), (HAIKU, ""))
        self.assertEqual(info["applied"], {"effort": NO_EFFORT, "thinking": "off",
                                           "temperature": 0.01})
        self.assertEqual(info["not_applied"], {})
        self.assertEqual(scorer._judge_profile(HAIKU)["tries"], 1)
        self.assertEqual(os.environ["RAGAS_DO_NOT_TRACK"], "true")


class EvaluationWriterTests(unittest.TestCase):
    def test_a_start_leaves_the_rows_of_scores_it_does_not_compute(self):
        from ragas.run_config import RunConfig
        from eval import ragas as scorer

        def row(metric, status, value=0.5):
            return asdict(EvalResult("q0", "person", "arm", metric, value, status, {}, None))

        prior = [row("faithfulness", "ok"), row("answer_correctness", "error"),
                 row("context_recall_id", "ok", 0.25), row("context_precision_id", "error")]
        metrics = scorer._build_metrics(["context_precision_id", "context_recall_id"],
                                        None, None, RunConfig(max_retries=1))
        with TemporaryDirectory() as d:
            path = Path(d) / "eval_results.jsonl"
            path.write_text("".join(json.dumps(r) + "\n" for r in prior), encoding="utf-8")
            new = scorer._score_all(
                [ArmOutput("a", ["c"], ["i"], 0.1)],
                [QuestionWithTruth("q0", "question?", "person", ["gold"], ["i"])],
                "arm", metrics, {}, results_path=path, workers=1, leg_stamp="start-two")
            rows = jsonl.load(path)
        # the two judged rows stand as they were, the failed one too; the id score that was ok
        # is not made again; the one that had failed is
        self.assertEqual(rows[:3], [prior[0], prior[1], prior[2]])
        self.assertEqual([(r.metric, r.status) for r in new], [("context_precision_id", "ok")])
        self.assertEqual([(r["metric"], r["status"]) for r in rows[3:]],
                         [("context_precision_id", "ok")])


class RunRecordTests(unittest.TestCase):
    QS = [QuestionWithTruth("q0", "question?", "person", [], [])]

    def _folder(self, root):
        (root / "corpus" / "products").mkdir(parents=True, exist_ok=True)
        (root / "q.jsonl").write_text("".join(
            json.dumps({"id": q.id, "question": q.question, "type": q.type, "ground_truth": [],
                        "citations": []}) + "\n" for q in self.QS), encoding="utf-8")
        (root / "ids.jsonl").write_text(
            "".join(json.dumps({"id": q.id}) + "\n" for q in self.QS), encoding="utf-8")
        return {"questions_path": root / "q.jsonl", "corpus_root": root / "corpus",
                "out_dir": str(root / "run"), "retrieval_only": True, "workers": 1}

    @staticmethod
    def _arm(on_answer=lambda: None):
        prepared = types.SimpleNamespace(build_stats=BuildStats(0.0, ModelUsage(), []))

        def answer(q, prep, generate, k):
            on_answer()
            return ArmOutput("a", ["c"], ["i"], 0.1)

        return types.SimpleNamespace(__name__="arms.fake", prepare_over_corpus=lambda c: prepared,
                                     answer_one_question=answer)

    def test_the_code_a_start_ran_on_is_read_once_before_it_answers(self):
        order = []
        diff = b"diff --git a/x b/x\r\n+a line with its own line end\r\n"
        version = {"commit": "c0ffee", "branch": "b", "dirty": True}

        def state():
            order.append("state")
            return {"status": [" M prod/x.py"], "diff": diff,
                    "diff_sha256": hashlib.sha256(diff).hexdigest(), "untracked_sha256": {}}

        def code_version():
            order.append("version")
            return dict(version)

        with TemporaryDirectory() as d:
            root = Path(d)
            cfg = self._folder(root)
            with patch.object(provenance, "code_state", state), \
                    patch.object(provenance, "code_version", code_version):
                orchestrator.run(self._arm(lambda: order.append("answer")), None,
                                 root / "ids.jsonl", cfg)
            manifest = json.loads((root / "run" / "run_manifest.json").read_text(encoding="utf-8"))
            leg = manifest["legs"][0]
            saved = (root / "run" / leg["code_state"]["diff_file"]).read_bytes()
        self.assertEqual(order, ["version", "state", "answer"])
        self.assertEqual(saved, diff)
        self.assertEqual(hashlib.sha256(saved).hexdigest(), leg["code_state"]["diff_sha256"])
        self.assertEqual((leg["code_version"], manifest["code_version"]), (version, version))

    def test_a_start_that_makes_no_judge_call_leaves_the_judge_named(self):
        def scorer(model, calls):
            def score_outputs(outs, chosen, **kw):
                return [EvalResult(q.id, q.type, "fake", "f1", 1.0, "ok", {}, None)
                        for q in chosen]

            return types.SimpleNamespace(
                __name__="eval.fake", score_outputs=score_outputs, LAST_JUDGE_MODEL=model,
                LAST_JUDGE_BACKEND="claude-cli", LAST_JUDGE_REASONING_EFFORT=None,
                LAST_JUDGE_WALL_TIME_S=1.0, LAST_JUDGE_USAGE=ModelUsage(calls=calls),
                LAST_JUDGE_SETTINGS={"started_at": f"{calls} calls"})

        with TemporaryDirectory() as d:
            root = Path(d)
            cfg = self._folder(root)
            orchestrator.run(self._arm(), scorer(HAIKU, 6), root / "ids.jsonl", dict(cfg))
            orchestrator.run(self._arm(), scorer(None, 0), root / "ids.jsonl", dict(cfg))
            kept = json.loads((root / "run" / "eval_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(kept["judge_model"], HAIKU)
        self.assertEqual([leg["judge_model"] for leg in kept["judge_legs"]], [HAIKU, None])
        self.assertEqual(kept["judge_usage"]["calls"], 6)


class EnvironmentRecordTests(unittest.TestCase):
    def test_the_env_record_takes_what_the_cli_reads_and_never_a_secret(self):
        shell = {"CLAUDE_CODE_EFFORT_LEVEL": "low", "MAX_THINKING_TOKENS": "0",
                 "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "8192", "ANTHROPIC_API_KEY": "sk-not-kept",
                 "CLAUDE_CODE_OAUTH_TOKEN": "not-kept", "RAGAS_DO_NOT_TRACK": "true",
                 "UNRELATED_NAME": "x"}
        with patch.dict(os.environ, shell):
            env = provenance.settings_env()
        self.assertEqual(env["CLAUDE_CODE_EFFORT_LEVEL"], "low")
        self.assertEqual(env["MAX_THINKING_TOKENS"], "0")
        self.assertEqual(env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"], "8192")
        self.assertEqual(env["RAGAS_DO_NOT_TRACK"], "true")
        self.assertEqual((env["ANTHROPIC_API_KEY"], env["CLAUDE_CODE_OAUTH_TOKEN"]),
                         ("<set>", "<set>"))
        self.assertNotIn("UNRELATED_NAME", env)
        self.assertNotIn("not-kept", json.dumps(env))

    def test_the_environment_lists_every_installed_package(self):
        env = provenance.environment()
        names = {line.split("==")[0].lower() for line in env["packages_all"]}
        self.assertTrue({"numpy", "ragas", "bm25s"} <= names)
        self.assertIn(f"numpy=={env['packages']['numpy']}", env["packages_all"])
        self.assertEqual(env["packages_all"], sorted(env["packages_all"], key=str.lower))

    def test_the_saved_diff_is_gits_own_bytes(self):
        state = provenance.code_state()
        if state["diff"] is None:
            self.assertIsNone(state["diff_sha256"])
        else:
            self.assertIsInstance(state["diff"], bytes)
            self.assertEqual(hashlib.sha256(state["diff"]).hexdigest(), state["diff_sha256"])


if __name__ == "__main__":
    unittest.main()

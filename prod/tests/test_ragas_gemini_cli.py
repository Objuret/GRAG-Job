import subprocess
import unittest
from unittest.mock import patch

import eval.ragas as scorer


class _TimeoutProcess:
    pid = 4242
    returncode = None

    def __init__(self):
        self.calls = 0

    def communicate(self, input=None, timeout=None):
        self.calls += 1
        if self.calls == 1:
            raise subprocess.TimeoutExpired("gemini", timeout)
        self.returncode = -9
        return "", ""


class GeminiCliRegressionTests(unittest.TestCase):
    def tearDown(self):
        scorer._CALL_POOL.shutdown(wait=False, cancel_futures=True)

    def test_timeout_kills_the_entire_windows_cli_tree(self):
        process = _TimeoutProcess()
        with patch.object(scorer.subprocess, "Popen", return_value=process), \
             patch.object(scorer.subprocess, "run") as taskkill:
            with self.assertRaises(subprocess.TimeoutExpired):
                scorer._run_gemini_cli(["gemini"], "prompt", 1, {})
        taskkill.assert_called_once_with(
            ["taskkill", "/PID", "4242", "/T", "/F"],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(process.calls, 2)

    def test_daily_quota_failure_does_not_retry(self):
        quota = subprocess.CompletedProcess(
            ["gemini"], 1, "", "TerminalQuotaError: You have exhausted your daily quota")
        with patch.object(scorer, "_GEMINI_EXE", "gemini"), \
             patch.object(scorer, "_run_gemini_cli", return_value=quota) as run:
            with self.assertRaisesRegex(RuntimeError, "daily quota"):
                scorer._gemini_verdict("prompt", "gemini-3.5-flash", 1)
        self.assertEqual(run.call_count, 1)

    def test_terminal_quota_cell_is_identified_for_the_circuit_breaker(self):
        row = scorer.EvalResult(
            question_id="q1", type="content", arm="lucene", metric="faithfulness",
            value=0.0, status="error",
            components={"error": "TerminalQuotaError: You have exhausted your daily quota"},
            human_label=None,
        )
        with patch.object(scorer, "JUDGE_BACKEND", "gemini-cli"):
            self.assertTrue(scorer._gemini_quota_error_row(row))

if __name__ == "__main__":
    unittest.main()

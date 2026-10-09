"""No file and no field of a run folder without a word saying what it means (2026-10-09: "you
can't just have fucking smashed fields with no word or explanation to what they mean"). A real
run is made through the real code and held against the words; and the things the words claim
that a number can check are checked."""
from __future__ import annotations

import json
import os
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np

from arms import lucene, vector
from eval import ragas as scorer
from eval.ragas_catalog import SELECTED
from harness import chat, fields, orchestrator

SLACK = [{"id": f"2026010{i}-0-aaaa{i}", "Channel": {"name": "launch", "channelID": "c1"},
          "Message": {"User": {"userId": "eid_1", "timestamp": f"2026-01-0{i}T09:00:00",
                               "text": text, "utterranceID": f"2026010{i}-0-aaaa{i}"},
                      "Reactions": []}, "ThreadReplies": []}
         for i, text in enumerate(("the rocket launch slipped a week because of the valve",
                                   "valve test passed, launch is on for friday",
                                   "lunch order: three pizzas"), 1)]
DOCUMENT = {"id": "launch_plan", "type": "Plan", "content": "launch plan " * 30, "author": "eid_2",
            "date": "2026-01-02T10:00:00", "document_link": "https://example.test/launch_plan"}
QUESTIONS = [{"id": "launch::a::0", "question": "why did the rocket launch slip?", "type": "content",
              "ground_truth": ["because of the valve"], "citations": [SLACK[0]["id"]]},
             {"id": "launch::a::1", "question": "is the launch on?", "type": "content",
              "ground_truth": ["yes, for friday"], "citations": [SLACK[1]["id"]]}]


def _envelope(answer):
    return {"type": "result", "subtype": "success", "is_error": False, "num_turns": 2,
            "duration_ms": 900, "duration_api_ms": 700, "ttft_ms": 600, "stop_reason": "tool_use",
            "session_id": "s", "result": json.dumps({"answer": answer}),
            "usage": {"input_tokens": 2, "cache_creation_input_tokens": 40,
                      "cache_read_input_tokens": 0, "output_tokens": 5},
            "modelUsage": {"claude-sonnet-5": {"inputTokens": 2}}}


class _Folder(unittest.TestCase):
    """one real run of the lucene arm over a small corpus, with the model program stood in for"""

    @classmethod
    def setUpClass(cls):
        cls._tmp = TemporaryDirectory()
        root = Path(cls._tmp.name)
        (root / "corpus" / "products").mkdir(parents=True)
        (root / "corpus" / "products" / "Rocket.json").write_text(
            json.dumps({"slack": SLACK, "documents": [DOCUMENT]}), encoding="utf-8")
        (root / "q.jsonl").write_text("".join(json.dumps(q) + "\n" for q in QUESTIONS),
                                      encoding="utf-8")
        (root / "ids.jsonl").write_text("".join(json.dumps({"id": q["id"]}) + "\n"
                                                for q in QUESTIONS), encoding="utf-8")
        cls.out = root / "run"

        def run(cmd, **kw):
            return subprocess.CompletedProcess(cmd, 0, json.dumps(_envelope("it slipped")).encode(), b"")

        patches = (patch.dict(os.environ, {chat._LOGIN_TOKEN: "test-token"}),
                   patch.object(chat, "_CONFIG_DIR", root / "config"),
                   patch.object(chat, "_dotenv_loaded", True),
                   patch.object(chat.subprocess, "run", run),
                   patch.object(scorer, "metrics_to_run",
                                lambda: ["context_precision_id", "context_recall_id", "exact_match"]))
        for p in patches:
            p.start()
        try:
            orchestrator.run(lucene, scorer, root / "ids.jsonl",
                             {"questions_path": root / "q.jsonl", "corpus_root": root / "corpus",
                              "out_dir": str(cls.out), "char_budget": 200, "workers": 1})
        finally:
            for p in reversed(patches):
                p.stop()

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()


class RunFolderTests(_Folder):
    def test_the_run_made_every_file_the_words_are_about(self):
        names = {p.name for p in self.out.iterdir()}
        self.assertLessEqual({"arm_outputs.jsonl", "run_manifest.json", "eval_results.jsonl",
                              "eval_calls.jsonl", "eval_manifest.json", "failures.jsonl",
                              "eval_failures.jsonl", "FIELDS.md"}, names)
        rows = fields._lines(self.out / "arm_outputs.jsonl")
        self.assertEqual(len(rows), 2)
        self.assertEqual({c["kind"] for r in rows for c in r["calls"]}, {"chat"})

    def test_no_file_and_no_field_of_a_run_folder_is_without_a_word(self):
        self.assertEqual(fields.undescribed(self.out), [])

    def test_the_folder_explains_itself(self):
        text = (self.out / "FIELDS.md").read_text(encoding="utf-8")
        for name in ("arm_outputs.jsonl", "eval_results.jsonl", "run_manifest.json",
                     "eval_manifest.json", "eval_calls.jsonl"):
            self.assertIn(f"## `{name}`", text)
        self.assertIn("**lucene**", text)
        self.assertIn("None: every file and every field of this folder is described above.", text)
        self.assertIn(fields.source_sha256(), text)
        for metric in ("context_precision_id", "context_recall_id", "exact_match"):
            self.assertIn(f"| `{metric}` |", text)
        self.assertNotIn("gives no words", text)

    def test_what_the_words_claim_holds_in_the_numbers(self):
        checked = fields.relations(self.out)
        self.assertEqual(len(checked), 6)
        self.assertEqual([text for text, ok, _ in checked if not ok], [])

    def test_a_field_or_a_file_without_a_word_is_named(self):
        with TemporaryDirectory() as d:
            copy = Path(d)
            for p in self.out.iterdir():
                (copy / p.name).write_bytes(p.read_bytes())
            rows = fields._lines(copy / "arm_outputs.jsonl")
            rows[0]["new_thing"] = 1
            rows[0]["generator"]["new_cost"] = 2
            rows[0]["meta"]["ranking"]["new_rank"] = 3
            rows[0]["answered_at"] = {"a_dict_where_a_plain_value_is_described": 1}
            (copy / "arm_outputs.jsonl").write_text(
                "".join(json.dumps(r) + "\n" for r in rows) + '{"cut off', encoding="utf-8")
            (copy / "notes.txt").write_text("x", encoding="utf-8")
            self.assertEqual(fields.undescribed(copy), [
                "arm_outputs.jsonl: answered_at.*", "arm_outputs.jsonl: generator.new_cost",
                "arm_outputs.jsonl: meta.ranking.new_rank", "arm_outputs.jsonl: new_thing",
                "notes.txt (the file)"])
            self.assertIn("5 have none:", fields.render(copy))

    def test_a_number_that_breaks_its_word_is_caught(self):
        with TemporaryDirectory() as d:
            copy = Path(d)
            for p in self.out.iterdir():
                (copy / p.name).write_bytes(p.read_bytes())
            rows = fields._lines(copy / "arm_outputs.jsonl")
            rows[0]["generator"]["time_s"] += 30
            self.assertEqual(len(rows[0]["context_ids"]), 1)
            rows[0]["context_ids"] = []
            (copy / "arm_outputs.jsonl").write_text(
                "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
            broken = [text for text, ok, _ in fields.relations(copy) if not ok]
            self.assertEqual(len(broken), 2)
            self.assertIn("time_s", broken[0])
            self.assertIn("context_ids", broken[1])


class WordsTests(unittest.TestCase):
    def test_every_score_that_is_run_has_ragas_own_sentence_and_its_source(self):
        self.assertEqual(set(fields.SCORES), set(SELECTED))
        for name, (sentence, source, here, needs, across) in fields.SCORES.items():
            self.assertTrue(sentence and source and here and needs, name)
            self.assertIsInstance(across, bool, name)
        within = {m for m, v in fields.SCORES.items() if not v[4]}
        self.assertEqual(within, {"context_precision_id", "context_precision_nonllm",
                                  "context_recall_nonllm"})

    def test_vector_gives_words_for_everything_it_writes(self):
        prepared = vector.Prepared(matrix=np.eye(3, dtype=np.float32), ids=["d0", "d1", "d2"],
                                   texts=["x" * 10, "y" * 7, "z" * 5])
        qvec = np.array([[1.0, 0.5, 0.25]], dtype=np.float32)
        with patch.object(vector, "_embed", lambda texts, mode, bar=True: (qvec, 1, 4, 0, 0.5)):
            out = vector.answer_one_question(("q", "q?"), prepared, None, k=1, char_budget=13)
        spec = fields.spec_for("vector")
        missing = set()
        fields._missing({"meta": out.meta}, spec["arm_outputs.jsonl"], "", missing)
        fields._missing({"index": vector.index_info(prepared),
                         "retrieval_flags": vector.RETRIEVAL_FLAGS},
                        spec["run_manifest.json"], "", missing)
        self.assertEqual(missing, set())

    def test_an_arm_without_words_is_said_so_in_the_file(self):
        text = fields.render(arm="no_such_arm")
        self.assertIn("The arm `no_such_arm` gives no words for it.", text)
        self.assertIn("`no_such_arm` gives no words for them.", text)

    def test_a_word_is_a_sentence_and_names_no_number_of_a_run(self):
        def texts(fields_dict):
            for entry in fields_dict.values():
                text, below = (entry, None) if isinstance(entry, str) else entry
                yield text
                if below:
                    yield from texts(below)

        for name, (_, _, spec) in fields.FILES.items():
            for text in texts(spec or {}):
                self.assertTrue(text.strip().endswith((".", ")")), f"{name}: {text!r}")
        for arm in (lucene, vector):
            for text in texts(arm.FIELDS):
                self.assertTrue(text.strip().endswith((".", ")")), text)


if __name__ == "__main__":
    unittest.main()

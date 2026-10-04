import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from graph import facet_answers as fa


SAMPLE = """```json
{"edges": [
  {"t": "release cadence", "temporal": "It turns on when the release shipped.",
   "why": "The text says the cadence changed to cut support load.",
   "activity": "The cadence is being changed in the text.",
   "concreteness": "It names two dates and a version number."},
  {"t": "Support Load", "temporal": "Reads the same whenever written.",
   "why": "No reason is given.",
   "activity": "Only mentioned.",
   "concreteness": "General talk, no figures."}
]}
```"""


def _payload(*phrases):
    return json.dumps({"edges": [
        {"t": p, "temporal": "t", "why": "w", "activity": "a", "concreteness": "c"}
        for p in phrases]})


class Stopped(unittest.TestCase):
    """Every test leaves the module's stop flag down."""

    def setUp(self):
        fa._STOP.clear()
        self.addCleanup(fa._STOP.clear)


class Prompt(Stopped):

    def test_user_message_is_the_taggers_pass_two_shape(self):
        msg = fa.user_message("line one\nline two\n", ["alpha", "beta"])
        self.assertEqual(msg, "Text:\nline one\nline two\n\nPhrases:\n- alpha\n- beta")

    def test_tag_order_is_kept_as_given(self):
        msg = fa.user_message("x", ["zeta thing", "alpha thing"])
        self.assertLess(msg.index("- zeta thing"), msg.index("- alpha thing"))


class Parse(Stopped):

    def test_sample_payload(self):
        rows, problems = fa.parse_answers(fa.extract_json(SAMPLE),
                                          ["release cadence", "support load"])
        self.assertEqual([r["t"] for r in rows], ["release cadence", "support load"])
        self.assertTrue(all(r["matched"] for r in rows))
        self.assertEqual(problems, [])
        for r in rows:
            for field in fa.ANSWER_FIELDS:
                self.assertTrue(r[field])

    def test_unknown_phrase_is_kept_and_marked(self):
        rows, _ = fa.parse_answers(fa.extract_json(SAMPLE), ["release cadence"])
        self.assertEqual([r["matched"] for r in rows], [True, False])

    def test_a_bad_field_drops_only_that_row(self):
        bad = json.dumps({"edges": [
            {"t": "a", "temporal": "x", "why": "y", "activity": "z"},
            {"t": "b", "temporal": "x", "why": "y", "activity": "z", "concreteness": "w"}]})
        rows, problems = fa.parse_answers(fa.extract_json(bad), ["a", "b"])
        self.assertEqual([r["t"] for r in rows], ["b"])
        self.assertEqual(len(problems), 1)

    def test_no_row_surviving_raises(self):
        bad = json.dumps({"edges": [{"t": "a", "temporal": "x", "why": "y",
                                     "activity": "z"}]})
        with self.assertRaises(ValueError):
            fa.parse_answers(fa.extract_json(bad), ["a"])

    def test_empty_edges_raises(self):
        with self.assertRaises(ValueError):
            fa.parse_answers({"edges": []}, ["a"])


class Retryable(Stopped):

    def test_transport_and_rate_errors_are_retryable(self):
        self.assertTrue(fa.retryable(RuntimeError("claude exit 1: usage limit reached")))
        self.assertTrue(fa.retryable(RuntimeError("claude exit 1: 529 overloaded")))
        self.assertTrue(fa.retryable(subprocess.TimeoutExpired("claude", 120)))
        self.assertTrue(fa.retryable(RuntimeError("claude gave up after 6 tries: "
                                                  "TimeoutExpired(...)")))

    def test_broken_lane_is_not_retryable(self):
        self.assertFalse(fa.retryable(FileNotFoundError("claude")))
        self.assertFalse(fa.retryable(RuntimeError(
            "chat.post: model 'haiku' has no backend — the hosted NIM lane was purged")))
        self.assertFalse(fa.retryable(RuntimeError("claude exit 1: bad request")))
        self.assertFalse(fa.retryable(fa.abort.Aborted("q")))
        self.assertFalse(fa.retryable(ValueError("nonsense")))


class Sharding(Stopped):

    def test_every_id_in_exactly_one_shard(self):
        ids = [f"chunk::{i}" for i in range(500)]
        for n in (2, 3, 7):
            counts = [0] * n
            for cid in ids:
                hits = [k for k in range(n) if fa.in_shard(cid, k, n)]
                self.assertEqual(len(hits), 1, cid)
                counts[hits[0]] += 1
            self.assertEqual(sum(counts), len(ids))
            self.assertTrue(all(c > 0 for c in counts))

    def test_shard_is_stable(self):
        self.assertEqual(fa.shard_of("chunk::7", 2), fa.shard_of("chunk::7", 2))

    def test_parse_shard_rejects_out_of_range(self):
        self.assertEqual(fa.parse_shard("1/2"), (1, 2))
        with self.assertRaises(SystemExit):
            fa.parse_shard("2/2")
        with self.assertRaises(SystemExit):
            fa.parse_shard("half")


class Files(Stopped):

    def test_temp_then_rename_leaves_no_partial(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "sub" / "x.json"
            with patch.object(fa.json, "dump", side_effect=RuntimeError("boom")):
                with self.assertRaises(RuntimeError):
                    fa.write_json(target, {"a": 1})
            self.assertFalse(target.exists())
            self.assertEqual(list(target.parent.iterdir()), [])
            fa.write_json(target, {"a": 1})
            self.assertEqual(json.loads(target.read_text(encoding="utf-8")), {"a": 1})

    def test_status_covers_every_state(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.json"
            sha = "a" * 64
            self.assertEqual(fa.status_of(p, sha), "missing")
            p.write_text("{not json", encoding="utf-8")
            self.assertEqual(fa.status_of(p, sha), "unreadable")
            p.write_text(json.dumps({"chunk_id": "a"}), encoding="utf-8")
            self.assertEqual(fa.status_of(p, sha), "unreadable")
            p.write_text(json.dumps({"chunk_id": "a", "edges": [], "prompt_sha256": "b" * 64}),
                         encoding="utf-8")
            self.assertEqual(fa.status_of(p, sha), "prompt_mismatch")
            p.write_text(json.dumps({"chunk_id": "a", "edges": [], "prompt_sha256": sha,
                                     "given": 2, "answered": 1, "complete": False}),
                         encoding="utf-8")
            self.assertEqual(fa.status_of(p, sha), "incomplete")
            p.write_text(json.dumps({"chunk_id": "a", "edges": [], "prompt_sha256": sha,
                                     "given": 2, "answered": 2, "complete": True}),
                         encoding="utf-8")
            self.assertEqual(fa.status_of(p, sha), "done")
            self.assertTrue(fa.is_done(p, sha))

    def test_sweep_tmp(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "a.tmp").write_text("x", encoding="utf-8")
            (Path(d) / "b.json").write_text("{}", encoding="utf-8")
            self.assertEqual(fa.sweep_tmp(Path(d)), 1)
            self.assertTrue((Path(d) / "b.json").is_file())

    def test_file_stem_is_filesystem_safe_and_unique(self):
        a = fa.file_stem("herb::slack::12")
        b = fa.file_stem("herb__slack__12")
        self.assertNotIn(":", a)
        self.assertNotEqual(a, b)


def _export(path: Path, rows, sha, db="test-db"):
    fa.write_export(path, rows, {"db": db, "prompt_sha256": sha,
                                 "corpus_sha256": "corpus-sha", "model": fa.MODEL,
                                 "n_chunks": len(rows), "written": "t"})


ROWS = [
    {"chunk_id": "c::1", "kind": "slack", "product": "ActionGenie",
     "tags": ["release cadence", "support load"], "text": "some chunk text"},
    {"chunk_id": "c::2", "kind": "document", "product": "VizForce",
     "tags": ["release cadence", "support load"], "text": "other chunk text"},
]


class InputRun(Stopped):

    def setUp(self):
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.export = self.root / "export.jsonl"
        self.sha = fa.prompt_sha(fa.prompt_text())

    def _run(self, argv, post):
        with patch.object(fa, "ROOT", self.root), \
             patch.object(fa.chat, "post", side_effect=post):
            return fa.main(argv)

    def test_runs_from_export_with_a_mocked_call(self):
        _export(self.export, ROWS, self.sha)
        seen = []

        def fake_post(path, payload, **kw):
            seen.append(payload)
            return {"choices": [{"message": {"content": SAMPLE}}],
                    "usage": {"prompt_tokens": 11, "completion_tokens": 3}}

        with patch.object(fa, "ROOT", self.root), \
             patch.object(fa.chat, "post", side_effect=fake_post):
            self.assertEqual(fa.main(["--input", str(self.export)]), 0)
            self.assertEqual(len(seen), 2)
            self.assertEqual(seen[0]["messages"][0]["content"], fa.prompt_text())
            user = seen[0]["messages"][1]["content"]
            self.assertTrue(user.startswith("Text:\n"))
            self.assertIn("\n\nPhrases:\n- release cadence\n- support load", user)
            self.assertIn("some chunk text", user)

            rec = json.loads(fa.chunk_path("test-db", "c::1").read_text(encoding="utf-8"))
            self.assertEqual(rec["chunk_id"], "c::1")
            self.assertEqual(rec["prompt_sha256"], self.sha)
            self.assertEqual((rec["given"], rec["answered"], rec["complete"]), (2, 2, True))
            self.assertEqual(len(rec["edges"]), 2)
            man = json.loads(fa.manifest_path("test-db", 0, 1).read_text(encoding="utf-8"))
            self.assertEqual(man["done"], 2)
            self.assertEqual(man["remaining"], 0)
            self.assertEqual(man["totals"]["calls"], 2)
            self.assertEqual(man["corpus_sha256"], "corpus-sha")
            self.assertFalse(fa.lock_path("test-db", 0, 1).exists())

            seen.clear()
            self.assertEqual(fa.main(["--input", str(self.export)]), 0)
            self.assertEqual(seen, [])

    def test_shard_splits_the_work_and_keeps_its_own_manifest(self):
        _export(self.export, ROWS, self.sha)
        asked = []

        def fake_post(path, payload, **kw):
            asked.append(payload["messages"][1]["content"])
            return {"choices": [{"message": {"content": SAMPLE}}], "usage": {}}

        with patch.object(fa, "ROOT", self.root), \
             patch.object(fa.chat, "post", side_effect=fake_post):
            for k in (0, 1):
                fa.main(["--input", str(self.export), "--shard", f"{k}/2"])
            self.assertEqual(len(set(asked)), 2)
            self.assertTrue(fa.manifest_path("test-db", 0, 2).is_file())
            self.assertTrue(fa.manifest_path("test-db", 1, 2).is_file())

    def test_ids_run_the_same_code_path_into_another_dir(self):
        _export(self.export, ROWS, self.sha)
        seen = []

        def fake_post(path, payload, **kw):
            seen.append(payload["messages"][1]["content"])
            return {"choices": [{"message": {"content": SAMPLE}}], "usage": {}}

        smoke = self.root / "smoke"
        with patch.object(fa, "ROOT", self.root), \
             patch.object(fa.chat, "post", side_effect=fake_post):
            fa.main(["--input", str(self.export), "--ids", "c::2", "--out", str(smoke)])
            self.assertEqual(len(seen), 1)
            self.assertTrue((smoke / f"{fa.file_stem('c::2')}.json").is_file())
            smoke_message = seen[0]
            seen.clear()
            fa.main(["--input", str(self.export)])
        full = [m for m in seen if "other chunk text" in m]
        self.assertEqual(full[0], smoke_message)

    def test_parse_failure_retries_once_then_records(self):
        _export(self.export, ROWS[:1], self.sha)
        calls = []

        def fake_post(path, payload, **kw):
            calls.append(1)
            return {"choices": [{"message": {"content": "no json here"}}], "usage": {}}

        with patch.object(fa, "ROOT", self.root), \
             patch.object(fa.chat, "post", side_effect=fake_post):
            fa.main(["--input", str(self.export)])
            self.assertEqual(len(calls), fa.PARSE_TRIES)
            self.assertFalse(fa.chunk_path("test-db", "c::1").exists())
            failed = json.loads(fa.failed_path("test-db", "c::1")
                                .read_text(encoding="utf-8"))
            self.assertEqual(failed["chunk_id"], "c::1")
            self.assertFalse(failed["lane"])

    def test_failed_marker_is_skipped_until_retry_failed(self):
        _export(self.export, ROWS[:1], self.sha)
        calls = []

        def fake_post(path, payload, **kw):
            calls.append(1)
            return {"choices": [{"message": {"content": SAMPLE}}], "usage": {}}

        with patch.object(fa, "ROOT", self.root), \
             patch.object(fa.chat, "post", side_effect=fake_post):
            fa.write_json(fa.failed_path("test-db", "c::1"),
                          {"chunk_id": "c::1", "error": "earlier"})
            fa.main(["--input", str(self.export)])
            self.assertEqual(calls, [])
            fa.main(["--input", str(self.export), "--retry-failed"])
            self.assertEqual(len(calls), 1)
            self.assertFalse(fa.failed_path("test-db", "c::1").exists())
            self.assertTrue(fa.chunk_path("test-db", "c::1").is_file())

    def test_prompt_mismatch_refuses_then_re_asks(self):
        _export(self.export, ROWS[:1], self.sha)
        calls = []

        def fake_post(path, payload, **kw):
            calls.append(1)
            return {"choices": [{"message": {"content": SAMPLE}}], "usage": {}}

        with patch.object(fa, "ROOT", self.root), \
             patch.object(fa.chat, "post", side_effect=fake_post):
            fa.write_json(fa.chunk_path("test-db", "c::1"), {
                "chunk_id": "c::1", "edges": [], "given": 2, "answered": 2,
                "complete": True, "prompt_sha256": "b" * 64})
            with self.assertRaises(SystemExit):
                fa.main(["--input", str(self.export)])
            self.assertEqual(calls, [])
            fa.main(["--input", str(self.export), "--allow-prompt-mismatch"])
            self.assertEqual(len(calls), 1)
            rec = json.loads(fa.chunk_path("test-db", "c::1").read_text(encoding="utf-8"))
            self.assertEqual(rec["prompt_sha256"], self.sha)

    def test_partial_payload_re_asks_only_the_missing_phrases(self):
        row = dict(ROWS[0])
        row["tags"] = ["release cadence", "support load", "third phrase"]
        _export(self.export, [row], self.sha)
        seen = []

        def fake_post(path, payload, **kw):
            seen.append(payload["messages"][1]["content"])
            content = SAMPLE if len(seen) == 1 else _payload("third phrase")
            return {"choices": [{"message": {"content": content}}], "usage": {}}

        with patch.object(fa, "ROOT", self.root), \
             patch.object(fa.chat, "post", side_effect=fake_post):
            fa.main(["--input", str(self.export)])
        self.assertEqual(len(seen), 2)
        self.assertIn("Phrases:\n- third phrase", seen[1])
        self.assertNotIn("release cadence", seen[1])
        with patch.object(fa, "ROOT", self.root):
            rec = json.loads(fa.chunk_path("test-db", "c::1").read_text(encoding="utf-8"))
        self.assertEqual((rec["given"], rec["answered"], rec["complete"]), (3, 3, True))
        self.assertEqual([e["t"] for e in rec["edges"]][:3],
                         ["release cadence", "support load", "third phrase"])

    def test_still_missing_after_the_second_ask_is_recorded(self):
        row = dict(ROWS[0])
        row["tags"] = ["release cadence", "support load", "third phrase"]
        _export(self.export, [row], self.sha)
        calls = []

        def fake_post(path, payload, **kw):
            calls.append(1)
            return {"choices": [{"message": {"content": SAMPLE}}], "usage": {}}

        with patch.object(fa, "ROOT", self.root), \
             patch.object(fa.chat, "post", side_effect=fake_post):
            fa.main(["--input", str(self.export)])
            rec = json.loads(fa.chunk_path("test-db", "c::1").read_text(encoding="utf-8"))
            failed = json.loads(fa.failed_path("test-db", "c::1")
                                .read_text(encoding="utf-8"))
        self.assertEqual(len(calls), 2)
        self.assertEqual((rec["given"], rec["answered"], rec["complete"]), (3, 2, False))
        self.assertEqual(failed["missing"], ["third phrase"])

    def test_transport_failure_backs_off_and_retries(self):
        _export(self.export, ROWS[:1], self.sha)
        calls, waits = [], []

        def fake_post(path, payload, **kw):
            calls.append(1)
            if len(calls) < 3:
                raise RuntimeError("claude exit 1: usage limit reached")
            return {"choices": [{"message": {"content": SAMPLE}}], "usage": {}}

        with patch.object(fa, "ROOT", self.root), \
             patch.object(fa.chat, "post", side_effect=fake_post), \
             patch.object(fa._STOP, "wait", side_effect=lambda s: waits.append(s)):
            fa.main(["--input", str(self.export)])
            self.assertEqual(len(calls), 3)
            self.assertEqual(waits, [fa.BACKOFF_START_S, fa.BACKOFF_START_S * 2])
            self.assertTrue(fa.chunk_path("test-db", "c::1").is_file())

    def test_non_retryable_error_is_recorded_once(self):
        _export(self.export, ROWS[:1], self.sha)
        calls = []

        def fake_post(path, payload, **kw):
            calls.append(1)
            raise RuntimeError("claude exit 1: bad request")

        with patch.object(fa, "ROOT", self.root), \
             patch.object(fa.chat, "post", side_effect=fake_post):
            fa.main(["--input", str(self.export)])
            self.assertEqual(len(calls), 1)
            failed = json.loads(fa.failed_path("test-db", "c::1")
                                .read_text(encoding="utf-8"))
        self.assertTrue(failed["lane"])

    def test_a_broken_lane_stops_the_run(self):
        rows = [dict(ROWS[0], chunk_id=f"c::{i}") for i in range(6)]
        _export(self.export, rows, self.sha)
        calls = []

        def fake_post(path, payload, **kw):
            calls.append(1)
            raise FileNotFoundError("claude")

        with patch.object(fa, "ROOT", self.root), \
             patch.object(fa.chat, "post", side_effect=fake_post):
            fa.main(["--input", str(self.export)])
        self.assertEqual(len(calls), fa.LANE_BROKEN_N)
        self.assertTrue(fa._STOP.is_set())

    def test_interrupt_sets_stop_and_asks_nothing(self):
        _export(self.export, ROWS, self.sha)
        calls = []

        def fake_post(path, payload, **kw):
            calls.append(1)
            return {"choices": [{"message": {"content": SAMPLE}}], "usage": {}}

        fa._on_interrupt(2, None)
        self.assertTrue(fa._STOP.is_set())
        with patch.object(fa, "ROOT", self.root), \
             patch.object(fa.chat, "post", side_effect=fake_post):
            self.assertEqual(fa.main(["--input", str(self.export)]), 0)
        self.assertEqual(calls, [])

    def test_a_live_lock_refuses_the_shard(self):
        _export(self.export, ROWS[:1], self.sha)
        with patch.object(fa, "ROOT", self.root):
            fa.write_json(fa.lock_path("test-db", 0, 1),
                          {"pid": os.getpid(), "shard": "0/1", "start": "t"})
            with patch.object(fa.chat, "post", side_effect=AssertionError("no call")):
                with self.assertRaises(SystemExit):
                    fa.main(["--input", str(self.export)])

    def test_a_stale_lock_is_taken_over(self):
        _export(self.export, ROWS[:1], self.sha)

        def fake_post(path, payload, **kw):
            return {"choices": [{"message": {"content": SAMPLE}}], "usage": {}}

        with patch.object(fa, "ROOT", self.root), \
             patch.object(fa.chat, "post", side_effect=fake_post), \
             patch.object(fa, "_pid_alive", return_value=False):
            fa.write_json(fa.lock_path("test-db", 0, 1),
                          {"pid": 424242, "shard": "0/1", "start": "t"})
            self.assertEqual(fa.main(["--input", str(self.export)]), 0)
            self.assertTrue(fa.chunk_path("test-db", "c::1").is_file())

    def test_backoff_is_capped(self):
        b = fa.BACKOFF_START_S
        for _ in range(50):
            b = min(b * 2, fa.BACKOFF_CAP_S)
        self.assertEqual(b, fa.BACKOFF_CAP_S)


class Merge(Stopped):

    def _record(self, chunk_id, sha, answer="x"):
        return {"chunk_id": chunk_id, "kind": "slack", "product": "P", "tags": ["a"],
                "given": 1, "answered": 1, "complete": True,
                "edges": [{"t": "a", "matched": True, "temporal": answer, "why": "y",
                           "activity": "z", "concreteness": "w"}],
                "prompt_sha256": sha}

    def test_merges_and_reports_duplicates_and_conflicts(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            sha = fa.prompt_sha(fa.prompt_text())
            other = root / "other"
            with patch.object(fa, "ROOT", root):
                fa.write_json(fa.chunk_path("test-db", "c::1"), self._record("c::1", sha))
                fa.write_json(fa.chunk_path("test-db", "c::3"), self._record("c::3", sha))
                other.mkdir(parents=True)
                for cid, ans in (("c::1", "x"), ("c::2", "x"), ("c::3", "different")):
                    (other / f"{fa.file_stem(cid)}.json").write_text(
                        json.dumps(self._record(cid, sha, ans)), encoding="utf-8")
                report = fa.merge("test-db", other, sha)
                self.assertTrue(fa.chunk_path("test-db", "c::2").is_file())
            self.assertEqual(report["copied"], 1)
            self.assertEqual(report["duplicates"], 1)
            self.assertEqual(report["conflicts"], 1)

    def test_refuses_a_different_prompt(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            sha = fa.prompt_sha(fa.prompt_text())
            other = root / "other"
            other.mkdir(parents=True)
            (other / f"{fa.file_stem('c::9')}.json").write_text(
                json.dumps(self._record("c::9", "a" * 64)), encoding="utf-8")
            with patch.object(fa, "ROOT", root):
                with self.assertRaises(SystemExit):
                    fa.merge("test-db", other, sha)


if __name__ == "__main__":
    unittest.main()

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from graph import facet_reader as fr


def _chunk(chunk_id="c1", tags=("release cadence", "Support Load"), complete=True):
    edges = [{"t": t, "matched": True,
              "temporal": f"temporal answer for {t}",
              "why": f"why answer for {t}",
              "activity": f"activity answer for {t}",
              "concreteness": f"concreteness answer for {t}"} for t in tags]
    return {"chunk_id": chunk_id, "kind": "document", "product": "P", "tags": list(tags),
            "tag_order": "graph collect", "given": len(tags),
            "answered": len(tags) if complete else len(tags) - 1,
            "complete": complete, "edges": edges, "problems": [],
            "prompt_sha256": "66a51975"}


def _write(directory: Path, rec, name=None):
    p = directory / (name or f"{rec['chunk_id']}__abc.json")
    p.write_text(json.dumps(rec), encoding="utf-8")
    return p


class Hypotheses(unittest.TestCase):
    def test_exact_strings(self):
        self.assertEqual(
            fr.HYPOTHESES["temporal"],
            "What the text says about {tag} depends on when it happened, is happening or is due.")
        self.assertEqual(
            fr.HYPOTHESES["why"],
            "The text gives the reason for {tag}: why it is there or what it is for.")
        self.assertEqual(
            fr.HYPOTHESES["activity"],
            "{tag} is being done, changed, decided or carried out in the text.")
        self.assertEqual(
            fr.HYPOTHESES["concreteness"],
            "The text gives particulars about {tag}: figures, amounts, parts, cases or examples.")

    def test_tag_inserted_verbatim(self):
        self.assertEqual(fr.hypothesis("activity", "token expiration"),
                         "token expiration is being done, changed, decided or carried out in the text.")

    def test_braces_in_a_tag_are_not_a_format_field(self):
        self.assertEqual(fr.hypothesis("activity", "{weird}"),
                         "{weird} is being done, changed, decided or carried out in the text.")

    def test_facets_are_the_four(self):
        self.assertEqual(fr.FACETS, ("temporal", "why", "activity", "concreteness"))
        self.assertEqual(fr.OVERLAY_FACETS,
                         ["topic", "temporal", "why", "activity", "concreteness"])


class ReadAndPairs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_pairs_from_a_sample_chunk_file(self):
        _write(self.dir, _chunk())
        recs, counts = fr.read_answers(self.dir)
        self.assertEqual(counts["chunks"], 1)
        pairs = fr.build_pairs(recs, counts)
        self.assertEqual(len(pairs), 8)
        self.assertEqual(counts["edges"], 2)
        self.assertEqual({p["facet"] for p in pairs}, set(fr.FACETS))
        one = [p for p in pairs if p["tag"] == "release cadence" and p["facet"] == "why"][0]
        self.assertEqual(one["premise"], "why answer for release cadence")
        self.assertEqual(one["hypothesis"],
                         "The text gives the reason for release cadence: why it is there or "
                         "what it is for.")
        self.assertEqual(one["answer_sha"], fr.answer_sha("why answer for release cadence"))
        self.assertEqual([p["id"] for p in pairs], list(range(8)))

    def test_pairs_sorted_by_length(self):
        _write(self.dir, _chunk(tags=("a", "a much much longer phrase indeed")))
        recs, counts = fr.read_answers(self.dir)
        pairs = fr.build_pairs(recs, counts)
        lens = [len(p["premise"]) + len(p["hypothesis"]) for p in pairs]
        self.assertEqual(lens, sorted(lens))

    def test_failed_manifest_and_incomplete_are_skipped_and_counted(self):
        _write(self.dir, _chunk("good"))
        _write(self.dir, _chunk("half", complete=False), name="half__x.json")
        _write(self.dir, _chunk("bad"), name="bad__x.failed.json")
        (self.dir / "manifest.0of1.json").write_text("{}", encoding="utf-8")
        (self.dir / "junk__x.json").write_text("not json", encoding="utf-8")
        recs, counts = fr.read_answers(self.dir)
        self.assertEqual([r["chunk_id"] for r in recs], ["good"])
        self.assertEqual(counts["failed"], 1)
        self.assertEqual(counts["incomplete"], 1)
        self.assertEqual(counts["unreadable"], 1)
        self.assertEqual(counts["prompt_sha256"], ["66a51975"])

    def test_an_edge_missing_an_answer_is_skipped(self):
        rec = _chunk(tags=("a", "b"))
        rec["edges"][1]["why"] = ""
        _write(self.dir, rec)
        recs, counts = fr.read_answers(self.dir)
        pairs = fr.build_pairs(recs, counts)
        self.assertEqual(len(pairs), 4)
        self.assertEqual(counts["edges_skipped"], 1)


class Resume(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_scores_present_for_an_answer_sha_are_not_recomputed(self):
        _write(self.dir, _chunk(tags=("a",)))
        recs, counts = fr.read_answers(self.dir)
        pairs = fr.build_pairs(recs, counts)
        values = self.dir / "values.jsonl"
        keep = pairs[0]
        fr.write_jsonl(values, [{"chunk_id": keep["chunk_id"], "tag": keep["tag"],
                                 "facet": keep["facet"], "value": 0.5, "contradiction": 0.1,
                                 "margin": 0.4, "answer_sha": keep["answer_sha"]}])
        done = fr.read_values(values)
        todo = fr.pending(pairs, done)
        self.assertEqual(len(pairs), 4)
        self.assertEqual(len(todo), 3)
        self.assertNotIn(fr.value_key(keep), {fr.value_key(p) for p in todo})

    def test_a_changed_answer_is_read_again(self):
        _write(self.dir, _chunk(tags=("a",)))
        recs, counts = fr.read_answers(self.dir)
        pairs = fr.build_pairs(recs, counts)
        values = self.dir / "values.jsonl"
        stale = dict(pairs[0])
        fr.write_jsonl(values, [{"chunk_id": stale["chunk_id"], "tag": stale["tag"],
                                 "facet": stale["facet"], "value": 0.5, "contradiction": 0.1,
                                 "margin": 0.4, "answer_sha": "an older answer"}])
        self.assertEqual(len(fr.pending(pairs, fr.read_values(values))), 4)


class Merge(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        _write(self.dir, _chunk(tags=("a",)))
        recs, counts = fr.read_answers(self.dir)
        self.pairs = fr.build_pairs(recs, counts)

    def _scores(self, rows):
        p = self.dir / "scores.jsonl"
        p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
        return p

    def test_merge_with_identity_fields(self):
        rows = [{**{k: p[k] for k in ("id", "chunk_id", "tag", "facet", "answer_sha")},
                 "entailment": 0.8, "neutral": 0.15, "contradiction": 0.05} for p in self.pairs]
        merged = fr.merge_scores(self.pairs, self._scores(rows))
        self.assertEqual(len(merged), 4)
        self.assertAlmostEqual(merged[0]["value"], 0.8)
        self.assertAlmostEqual(merged[0]["contradiction"], 0.05)
        self.assertAlmostEqual(merged[0]["margin"], 0.75)
        self.assertEqual(merged[0]["answer_sha"], self.pairs[0]["answer_sha"])

    def test_merge_by_pair_id_when_identity_is_gone(self):
        rows = [{"id": p["id"], "entailment": 0.2, "neutral": 0.3, "contradiction": 0.5}
                for p in self.pairs]
        merged = fr.merge_scores(self.pairs, self._scores(rows))
        self.assertEqual(len(merged), 4)
        self.assertAlmostEqual(merged[0]["margin"], -0.3)
        self.assertEqual({m["chunk_id"] for m in merged}, {"c1"})

    def test_an_unmatchable_score_line_raises(self):
        rows = [{"id": 9999, "entailment": 0.2, "neutral": 0.3, "contradiction": 0.5}]
        with self.assertRaises(SystemExit):
            fr.merge_scores(self.pairs, self._scores(rows))


class Overlay(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_overlay_shape_matches_facet_stats(self):
        rows = [{"chunk_id": "c1", "tag": "a", "facet": f, "value": i / 10,
                 "contradiction": 0.0, "margin": i / 10, "answer_sha": "s"}
                for i, f in enumerate(fr.FACETS)]
        meta = {"answers_prompt_sha256": ["66a51975"]}
        with patch.object(fr, "overlay_path", return_value=self.dir / "db.overlay.json"):
            p = fr.write_overlay(rows, "db", self.dir / "values.jsonl", meta)
        body = json.loads(Path(p).read_text(encoding="utf-8"))
        self.assertEqual(body["facets"], ["topic", "temporal", "why", "activity", "concreteness"])
        for key in ("database", "run_id", "facets", "method", "tool", "tool_sha256",
                    "source", "edges"):
            self.assertIn(key, body)
        self.assertEqual(len(body["edges"]), 1)
        edge = body["edges"][0]
        self.assertEqual(sorted(edge), ["anchor", "chunkId", "tag", "weights"])
        self.assertEqual(edge["chunkId"], "c1")
        self.assertEqual(edge["tag"], "a")
        self.assertEqual(edge["weights"], [None, 0.0, 0.1, 0.2, 0.3])
        self.assertEqual(body["hypotheses"], dict(fr.HYPOTHESES))

    def test_overlay_keys_are_the_facet_stats_keys(self):
        from graph import facet_stats as fs
        self.assertEqual(fs.FACETS, fr.OVERLAY_FACETS)


class Labels(unittest.TestCase):
    def test_label_order_read_off_the_config(self):
        class Cfg:
            label2id = {"contradiction": 2, "neutral": 1, "entailment": 0}
        self.assertEqual(fr.label_index(Cfg()),
                         {"entailment": 0, "neutral": 1, "contradiction": 2})

    def test_a_reordered_config_is_followed(self):
        class Cfg:
            label2id = {"ENTAILMENT": 2, "NEUTRAL": 0, "CONTRADICTION": 1}
        self.assertEqual(fr.label_index(Cfg()),
                         {"entailment": 2, "neutral": 0, "contradiction": 1})

    def test_a_config_without_the_labels_raises(self):
        class Cfg:
            label2id = {"LABEL_0": 0, "LABEL_1": 1, "LABEL_2": 2}
        with self.assertRaises(SystemExit):
            fr.label_index(Cfg())


class PairsOut(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_pairs_out_loads_no_model(self):
        src = self.dir / "answers"
        src.mkdir()
        _write(src, _chunk(tags=("a", "b")))
        pairs_out = self.dir / "pairs.jsonl"
        with patch.object(fr, "score_pairs", side_effect=AssertionError("model loaded")):
            fr.main(["--db", "db", "--answers", str(src), "--out", str(self.dir / "v"),
                     "--pairs-out", str(pairs_out)])
        lines = [json.loads(l) for l in pairs_out.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(lines), 8)
        self.assertEqual(sorted(lines[0]),
                         ["answer_sha", "chunk_id", "facet", "hypothesis", "id", "premise", "tag"])
        self.assertFalse((self.dir / "v" / "values.jsonl").exists())


if __name__ == "__main__":
    unittest.main()

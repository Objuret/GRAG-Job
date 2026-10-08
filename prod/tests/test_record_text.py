"""A baseline unit's text is the record written the way the benchmark's own code writes it, the
same text for lucene and for vector, and a run's manifest says which text it ran on."""
from __future__ import annotations

import unittest

from arms import lucene, vector
from harness import orchestrator
from harness.record_text import ARTIFACT_TYPES, FORM, record_text, units_digest

SLACK = {"id": "20260101-0-aaaaa", "Channel": {"name": "planning-x", "channelID": "ch-x"},
         "Message": {"User": {"userId": "eid_1", "timestamp": "2026-01-01T09:00:00",
                              "text": "kickoff at ten", "utterranceID": "20260101-0-aaaaa"},
                     "Reactions": []},
         "ThreadReplies": []}
DOCUMENT = {"id": "x_spec", "type": "Spec", "content": "the spec body", "author": "eid_2",
            "date": "2026-01-02T10:00:00", "document_link": "https://example.test/x_spec"}
TRANSCRIPT = {"id": "x_meeting", "date": "2026-01-03T11:00:00", "document_type": "Review",
              "participants": ["eid_1", "eid_2"], "transcript": "eid_1: we ship"}
CHAT = {"id": "x_meeting_chat", "text": "2026-01-03T11:05:00\nAda: https://example.test/x_spec"}
URL = {"id": "x_url", "link": "https://example.test/a", "description": "a page about x"}
PR = {"id": "x_pr", "title": "Fix the rollback", "summary": "rolls back in order",
      "user": {"login": "eid_3"}, "created_at": "2026-01-04T12:00:00", "state": "closed",
      "mergeable": "True", "merged": "True", "link": "https://example.test/pull/7", "number": "7",
      "reviews": [{"state": "APPROVED", "user": {"login": "eid_1"},
                   "submitted_at": "2026-01-05T08:00:00", "comment": "good"},
                  {"state": "COMMENTED", "user": {"login": "eid_2"},
                   "submitted_at": "2026-01-05T09:00:00", "comment": "one nit"}]}


class FormTests(unittest.TestCase):
    def test_each_kind_is_written_in_the_benchmark_authors_form(self):
        self.assertEqual(record_text("slack", SLACK),
                         "Message ID: 20260101-0-aaaaa\nChannel Name: planning-x\n"
                         "Timestamp: 2026-01-01T09:00:00\n\neid_1: kickoff at ten")
        self.assertEqual(record_text("documents", DOCUMENT),
                         "Doc ID: x_spec\nLink: https://example.test/x_spec\n2026-01-02T10:00:00\n"
                         "Author: eid_2\n\nSpec\nthe spec body")
        self.assertEqual(record_text("meeting_chats", CHAT),
                         "Meeting ID: x_meeting_chat\n\nChats:\n"
                         "2026-01-03T11:05:00\nAda: https://example.test/x_spec")
        self.assertEqual(record_text("urls", URL),
                         "URL: https://example.test/a\n\nDescription: a page about x")
        self.assertEqual(record_text("prs", PR),
                         "Title: Fix the rollback\nAuthor: eid_3\nCreated At: 2026-01-04T12:00:00\n"
                         "State: closed\nMergeable: True\nMerged: True\n"
                         "Link: https://example.test/pull/7\nSummary: rolls back in order\n\n"
                         "Reviews:\n- APPROVED by eid_1 at 2026-01-05T08:00:00: good\n"
                         "- COMMENTED by eid_2 at 2026-01-05T09:00:00: one nit\n")

    def test_the_two_fields_the_authors_forms_do_not_write_are_kept(self):
        self.assertEqual(record_text("documents", {**DOCUMENT, "feedback": "tighten section 2"}),
                         record_text("documents", DOCUMENT) + "\ntighten section 2")
        self.assertEqual(record_text("meeting_transcripts", TRANSCRIPT),
                         "Meeting ID: x_meeting\n2026-01-03T11:00:00\n"
                         "Participants: ['eid_1', 'eid_2']\n\nReview\neid_1: we ship")
        self.assertIn("documents.feedback", FORM)
        self.assertIn("meeting_transcripts.document_type", FORM)

    def test_a_record_without_a_field_its_form_reads_is_refused(self):
        for kind, rec, field in (("slack", SLACK, "Channel"), ("documents", DOCUMENT, "author"),
                                 ("meeting_transcripts", TRANSCRIPT, "participants"),
                                 ("prs", PR, "user"), ("urls", URL, "link")):
            with self.assertRaises(KeyError, msg=kind):
                record_text(kind, {k: v for k, v in rec.items() if k != field})
        with self.assertRaises(KeyError):
            record_text("wiki", {"id": "w"})

    def test_a_url_description_stands_once(self):
        self.assertEqual(record_text("urls", URL).count("a page about x"), 1)

    def test_the_digest_moves_with_an_id_a_text_and_the_order(self):
        base = units_digest(["a", "b"], ["one", "two"])
        self.assertEqual(base, units_digest(["a", "b"], ["one", "two"]))
        for ids, texts in ((["a", "c"], ["one", "two"]), (["a", "b"], ["one", "twp"]),
                           (["b", "a"], ["two", "one"]), (["a", "b"], ["on", "etwo"])):
            self.assertNotEqual(base, units_digest(ids, texts))


class CorpusTests(unittest.TestCase):
    """the corpus the runs read: both baselines build the same units from it"""

    @classmethod
    def setUpClass(cls):
        cls.lucene_docs = lucene.ingest_corpus(orchestrator.DEFAULT_CORPUS)
        cls.vector_docs = vector._read_corpus(orchestrator.DEFAULT_CORPUS)

    def test_both_arms_hold_the_same_units_with_the_same_text(self):
        self.assertEqual([d["id"] for d in self.lucene_docs], [d["id"] for d in self.vector_docs])
        self.assertEqual([d["text"] for d in self.lucene_docs],
                         [d["text"] for d in self.vector_docs])
        self.assertEqual(len(self.lucene_docs), 38540)
        self.assertEqual({d["kind"] for d in self.lucene_docs}, set(ARTIFACT_TYPES))

    def test_every_unit_has_text_and_names_its_record(self):
        for d in self.lucene_docs:
            self.assertTrue(d["text"].strip(), d["id"])
        heads = {"slack": "Message ID: ", "documents": "Doc ID: ", "meeting_transcripts":
                 "Meeting ID: ", "meeting_chats": "Meeting ID: ", "urls": "URL: ", "prs": "Title: "}
        for d in self.lucene_docs:
            self.assertTrue(d["text"].startswith(heads[d["kind"]]), d["id"])

    def test_the_manifest_entry_of_both_arms_names_the_same_text(self):
        ids = [d["id"] for d in self.lucene_docs]
        texts = [d["text"] for d in self.lucene_docs]
        digest = units_digest(ids, texts)
        sparse = lucene.index_info(lucene.Prepared(retriever=None, stemmer=None, ids=ids,
                                                   texts=texts))
        import numpy as np
        dense = vector.index_info(vector.Prepared(matrix=np.zeros((1, 1), dtype=np.float32),
                                                  ids=ids, texts=texts))
        self.assertEqual((sparse["units_sha256"], dense["units_sha256"]), (digest, digest))
        self.assertEqual((sparse["unit_text"], dense["unit_text"]), (FORM, FORM))
        self.assertEqual((sparse["k1"], sparse["b"]), (0.9, 0.4))


if __name__ == "__main__":
    unittest.main()

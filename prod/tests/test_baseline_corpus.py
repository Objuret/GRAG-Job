import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from arms import lucene, vector
from harness.record_text import record_text

_EMPLOYEES = {
    "eid_00000001": {"employee_id": "eid_00000001", "name": "Ada Vega",
                     "role": "VP of Engineering", "location": "Berlin", "org": "slack"},
    "eid_00000002": {"employee_id": "eid_00000002", "name": "Bo Ling",
                     "role": "Software Engineer", "location": "Remote", "org": "slack"},
}
_CUSTOMERS = [
    {"name": "Cyd Marsh", "role": "CTO", "company": "BlueWave", "id": "CUST-9001"},
]
_TEAM = [
    {"employee_id": "eid_00000001", "name": "Ada Vega", "role": "VP of Engineering",
     "location": "Berlin", "org": "slack",
     "engineers": [
         {"employee_id": "eid_00000002", "name": "Bo Ling",
          "role": "Software Engineer", "location": "Remote", "org": "slack"},
     ]},
]
_PRODUCT = {
    "slack": [{"id": "20260101-0-aaaaa",
               "Channel": {"name": "general"},
               "Message": {"User": {"userId": "eid_00000001", "text": "kickoff",
                                    "timestamp": "2026-01-01T09:00:00",
                                    "utterranceID": "20260101-0-aaaaa"}}}],
    "documents": [{"id": "spec_doc", "type": "Spec", "content": "the spec body",
                   "author": "eid_00000002", "date": "2026-01-02T10:00:00",
                   "document_link": "https://sf-internal.slack.com/archives/docs/spec_doc"}],
}

# the product records in their kinds' order, then the employees and customers in the files' order
_UNIT_IDS = ["20260101-0-aaaaa", "spec_doc", "eid_00000001", "eid_00000002", "CUST-9001"]


def _fixture_corpus(tmp: Path) -> Path:
    root = tmp / "Salesforce__HERB"
    (root / "products").mkdir(parents=True)
    (root / "metadata").mkdir(parents=True)
    (root / "products" / "OneForce.json").write_text(
        json.dumps(_PRODUCT), encoding="utf-8")
    (root / "metadata" / "employee.json").write_text(
        json.dumps(_EMPLOYEES), encoding="utf-8")
    (root / "metadata" / "customers_data.json").write_text(
        json.dumps(_CUSTOMERS), encoding="utf-8")
    (root / "metadata" / "salesforce_team.json").write_text(
        json.dumps(_TEAM), encoding="utf-8")
    return root


class _CorpusCase(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = _fixture_corpus(Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def read(self, module) -> list:
        reader = module.ingest_corpus if module is lucene else module._read_corpus
        return reader(self.root)


class CorpusTests(_CorpusCase):
    def test_lucene_reads_the_records_then_the_employees_and_customers(self):
        self.assertEqual([d["id"] for d in self.read(lucene)], _UNIT_IDS)

    def test_vector_reads_the_records_then_the_employees_and_customers(self):
        self.assertEqual([d["id"] for d in self.read(vector)], _UNIT_IDS)


class MetadataUnitTests(_CorpusCase):
    def test_lucene_adds_one_unit_per_employee_and_customer(self):
        docs = self.read(lucene)
        self.assertEqual([d["kind"] for d in docs[2:]], ["employee", "employee", "customers_data"])
        self.assertEqual(len(docs), 2 + 3)

    def test_vector_adds_one_unit_per_employee_and_customer(self):
        self.assertEqual(len(self.read(vector)), 2 + 3)

    def test_the_team_file_is_not_read(self):
        (self.root / "metadata" / "salesforce_team.json").write_text("not json", encoding="utf-8")
        for module in (lucene, vector):
            self.assertEqual([d["id"] for d in self.read(module)], _UNIT_IDS, module.__name__)

    def test_unit_ids_stay_unique_across_both_arms(self):
        for module in (lucene, vector):
            ids = [d["id"] for d in self.read(module)]
            self.assertEqual(len(ids), len(set(ids)), module.__name__)

    def test_the_company_name_reaches_the_lucene_index(self):
        text = {d["id"]: d["text"] for d in self.read(lucene)}
        self.assertIn("BlueWave", text["CUST-9001"])
        self.assertIn("CUST-9001", text["CUST-9001"])

    def test_the_company_name_reaches_the_vector_index(self):
        text = {d["id"]: d["text"] for d in self.read(vector)}
        self.assertIn("BlueWave", text["CUST-9001"])

    def test_an_employee_is_written_as_record_text_writes_it(self):
        for module in (lucene, vector):
            text = {d["id"]: d["text"] for d in self.read(module)}
            self.assertEqual(text["eid_00000001"],
                             record_text("employee", _EMPLOYEES["eid_00000001"]), module.__name__)

    def test_a_metadata_id_that_is_a_record_id_fails_loud(self):
        product = json.loads(
            (self.root / "products" / "OneForce.json").read_text(encoding="utf-8"))
        product["documents"][0]["id"] = "eid_00000001"
        (self.root / "products" / "OneForce.json").write_text(
            json.dumps(product), encoding="utf-8")
        for module in (lucene, vector):
            with self.assertRaises(RuntimeError) as caught:
                self.read(module)
            self.assertIn("eid_00000001", str(caught.exception))


class CitationSpaceTests(unittest.TestCase):
    _UNITS = [
        {"id": "spec_doc", "text": "the spec body", "score": 2.0, "rank": 0},
        {"id": "eid_00000001", "text": "employee directory", "score": 1.5, "rank": 1},
        {"id": "20260101-0-aaaaa", "text": "kickoff", "score": 1.0, "rank": 2},
    ]

    def _answer(self, module):
        prepared = object()
        with patch.object(module, "retrieve_top_k_units",
                          lambda q, p, k: self._UNITS if module is lucene
                          else (self._UNITS, module.ModelUsage())):
            return module.answer_one_question(("q1", "who is Ada Vega"), prepared, None, k=3)

    def test_context_ids_keep_an_employee_beside_the_records(self):
        for module in (lucene, vector):
            out = self._answer(module)
            self.assertEqual(len(out.contexts), 3, module.__name__)
            self.assertEqual(out.context_ids, ["spec_doc", "eid_00000001", "20260101-0-aaaaa"],
                             module.__name__)
            self.assertIsNone(out.meta, module.__name__)

    def test_truncate_k_cuts_a_depth_run_by_its_ids(self):
        import truncate_k

        for module in (lucene, vector):
            out = self._answer(module)
            rec = {"id": "q1", "contexts": out.contexts,
                   "context_ids": out.context_ids, "meta": out.meta}
            cut = truncate_k.truncate_record(rec, 2)
            self.assertEqual(cut["context_ids"], ["spec_doc", "eid_00000001"], module.__name__)


class ManifestFlagTests(unittest.TestCase):
    def test_neither_arm_has_a_switch(self):
        self.assertEqual(lucene.RETRIEVAL_FLAGS, {})
        self.assertEqual(vector.RETRIEVAL_FLAGS, {})


if __name__ == "__main__":
    unittest.main()

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from arms import lucene, vector

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
               "Message": {"User": {"userId": "eid_00000001", "text": "kickoff"}}}],
    "documents": [{"id": "spec_doc", "type": "Spec", "content": "the spec body"}],
}


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

    def read(self, module, metadata_on: bool) -> list:
        with patch.object(module, "METADATA_ON", metadata_on):
            reader = module.ingest_corpus if module is lucene else module._read_corpus
            return reader(self.root)


class DefaultScopeTests(_CorpusCase):
    def test_lucene_reads_products_only_by_default(self):
        ids = [d["id"] for d in self.read(lucene, False)]
        self.assertEqual(sorted(ids), ["20260101-0-aaaaa", "spec_doc"])

    def test_vector_reads_products_only_by_default(self):
        ids = [d["id"] for d in self.read(vector, False)]
        self.assertEqual(sorted(ids), ["20260101-0-aaaaa", "spec_doc"])

    def test_the_shipped_default_is_products_only(self):
        self.assertFalse(lucene.METADATA_ON)
        self.assertFalse(vector.METADATA_ON)


class DirectoryIngestTests(_CorpusCase):
    def test_lucene_adds_one_document_per_directory_entry(self):
        docs = self.read(lucene, True)
        added = [d for d in docs if d["id"].startswith(lucene.DIRECTORY_ID_PREFIX)]
        self.assertEqual(len(added), 4)
        self.assertEqual(len(docs), 2 + 4)

    def test_vector_adds_one_document_per_directory_entry(self):
        docs = self.read(vector, True)
        added = [d for d in docs if d["id"].startswith(vector.DIRECTORY_ID_PREFIX)]
        self.assertEqual(len(added), 4)
        self.assertEqual(len(docs), 2 + 4)

    def test_a_team_leaf_is_not_emitted_twice(self):
        ids = [d["id"] for d in self.read(lucene, True)]
        self.assertIn("metadata::employee::eid_00000002", ids)
        self.assertNotIn("metadata::salesforce_team::eid_00000002", ids)
        self.assertIn("metadata::salesforce_team::eid_00000001", ids)

    def test_a_person_in_two_directories_gets_two_distinct_ids(self):
        ids = [d["id"] for d in self.read(lucene, True)]
        self.assertIn("metadata::employee::eid_00000001", ids)
        self.assertIn("metadata::salesforce_team::eid_00000001", ids)
        self.assertEqual(len(ids), len(set(ids)))

    def test_unit_ids_stay_unique_across_both_arms(self):
        for module in (lucene, vector):
            ids = [d["id"] for d in self.read(module, True)]
            self.assertEqual(len(ids), len(set(ids)), module.__name__)

    def test_the_company_name_reaches_the_lucene_index(self):
        text = {d["id"]: f'{d["title"]}\n{d["contents"]}'
                for d in self.read(lucene, True)}
        self.assertIn("BlueWave", text["metadata::customers_data::CUST-9001"])
        self.assertIn("CUST-9001", text["metadata::customers_data::CUST-9001"])

    def test_the_company_name_reaches_the_vector_index(self):
        text = {d["id"]: d["text"] for d in self.read(vector, True)}
        self.assertIn("BlueWave", text["metadata::customers_data::CUST-9001"])

    def test_a_roster_renders_its_members_with_their_ids(self):
        text = {d["id"]: d["text"] for d in self.read(vector, True)}
        leader = text["metadata::salesforce_team::eid_00000001"]
        self.assertIn("engineers: Bo Ling (eid_00000002)", leader)

    def test_an_artifact_id_in_the_directory_namespace_fails_loud(self):
        product = json.loads(
            (self.root / "products" / "OneForce.json").read_text(encoding="utf-8"))
        product["documents"][0]["id"] = "metadata::employee::eid_00000001"
        (self.root / "products" / "OneForce.json").write_text(
            json.dumps(product), encoding="utf-8")
        for module in (lucene, vector):
            with self.assertRaises(RuntimeError) as caught:
                self.read(module, True)
            self.assertIn("directory namespace", str(caught.exception))


class CitationSpaceTests(_CorpusCase):
    def test_a_directory_unit_carries_no_artifact_id(self):
        for module in (lucene, vector):
            self.assertIsNone(
                module.unit_to_artifact_id({"id": "metadata::employee::eid_00000001"}),
                module.__name__)
            self.assertEqual(
                module.unit_to_artifact_id({"id": "spec_doc"}), "spec_doc",
                module.__name__)

    def _answer(self, module, units):
        prepared = object()
        with patch.object(module, "METADATA_ON", True), \
                patch.object(module, "retrieve_top_k_units",
                             lambda q, p, k: units if module is lucene
                             else (units, module.ModelUsage())):
            return module.answer_one_question(("q1", "who is Ada Vega"), prepared, None, k=3)

    def test_context_ids_drop_the_directory_units_but_contexts_keep_them(self):
        units = [
            {"id": "spec_doc", "text": "the spec body", "score": 2.0, "rank": 0},
            {"id": "metadata::employee::eid_00000001", "text": "employee directory",
             "score": 1.5, "rank": 1},
            {"id": "20260101-0-aaaaa", "text": "kickoff", "score": 1.0, "rank": 2},
        ]
        for module in (lucene, vector):
            out = self._answer(module, units)
            self.assertEqual(len(out.contexts), 3, module.__name__)
            self.assertEqual(out.context_ids, ["spec_doc", "20260101-0-aaaaa"],
                             module.__name__)

    def test_the_per_context_id_lists_let_truncate_k_rebuild_a_depth(self):
        import truncate_k

        units = [
            {"id": "spec_doc", "text": "the spec body", "score": 2.0, "rank": 0},
            {"id": "metadata::employee::eid_00000001", "text": "employee directory",
             "score": 1.5, "rank": 1},
            {"id": "20260101-0-aaaaa", "text": "kickoff", "score": 1.0, "rank": 2},
        ]
        for module in (lucene, vector):
            out = self._answer(module, units)
            self.assertEqual(out.meta["chunk_ids"],
                             [["spec_doc"], [], ["20260101-0-aaaaa"]], module.__name__)
            rec = {"id": "q1", "contexts": out.contexts,
                   "context_ids": out.context_ids, "meta": out.meta}
            cut = truncate_k.truncate_record(rec, 2)
            self.assertEqual(cut["context_ids"], ["spec_doc"], module.__name__)

    def test_products_only_records_stay_one_id_per_context(self):
        units = [{"id": "spec_doc", "text": "the spec body", "score": 2.0, "rank": 0}]
        for module in (lucene, vector):
            prepared = object()
            with patch.object(module, "METADATA_ON", False), \
                    patch.object(module, "retrieve_top_k_units",
                                 lambda q, p, k: units if module is lucene
                                 else (units, module.ModelUsage())):
                out = module.answer_one_question(("q1", "spec"), prepared, None, k=3)
            self.assertIsNone(out.meta, module.__name__)
            self.assertEqual(out.context_ids, ["spec_doc"], module.__name__)


class ManifestFlagTests(unittest.TestCase):
    def test_both_arms_record_the_corpus_scope(self):
        self.assertEqual(lucene.RETRIEVAL_FLAGS,
                         {"HERB_BASELINE_METADATA": lucene.METADATA_ON})
        self.assertEqual(vector.RETRIEVAL_FLAGS,
                         {"HERB_BASELINE_METADATA": vector.METADATA_ON})

    def test_the_switch_reads_the_environment_and_rejects_a_typo(self):
        for module in (lucene, vector):
            with patch.dict(os.environ, {"HERB_BASELINE_METADATA": "1"}):
                self.assertTrue(module._env_bool("HERB_BASELINE_METADATA", False))
            with patch.dict(os.environ, {"HERB_BASELINE_METADATA": "true"}):
                with self.assertRaises(ValueError):
                    module._env_bool("HERB_BASELINE_METADATA", False)
            with patch.dict(os.environ, {"HERB_BASELINE_METADATA": ""}):
                self.assertFalse(module._env_bool("HERB_BASELINE_METADATA", False))


class HybridGuardTests(unittest.TestCase):
    def test_the_hybrid_arm_refuses_the_directory_corpus(self):
        from arms import hybrid

        with patch.object(lucene, "METADATA_ON", True):
            with self.assertRaises(RuntimeError) as caught:
                hybrid.prepare_over_corpus("unused")
        self.assertIn("HERB_BASELINE_METADATA", str(caught.exception))


if __name__ == "__main__":
    unittest.main()

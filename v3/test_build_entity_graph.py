"""Fixture checks for build_entity_graph: the removal predicate, the count and
set-identity gates, the directory reader, the entity derivation from record
structure, the org-tree relations, and the write guards. No database and no
corpus file is touched — everything runs on in-memory fixtures and temp
directories."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import build_entity_graph as beg


class SlugTests(unittest.TestCase):
    def test_non_alphanumeric_runs_collapse_to_one_underscore(self):
        self.assertEqual(beg.slug("Accessible Navigation Bar!"),
                         "accessible_navigation_bar")
        self.assertEqual(beg.slug("https://github.com/x/y/pull/1"),
                         "https_github_com_x_y_pull_1")
        self.assertEqual(beg.slug("--Adaptive  Compaction--"),
                         "adaptive_compaction")


class RemovalPredicateTests(unittest.TestCase):
    TAGS = {
        # dies: title slug, link slugs, URL prefixes, PR-pointer forms
        "accessible_navigation_bar",
        "https_github_com_acme_pull_1",
        "www_example_com_story",
        "github_com_django_django_pull_3704",
        "github_pr_302",
        "redis_pr_1759",
        "pull_request_4977",
        "tensorflow_tensorflow_pull_4897",
        "some_document_link_slug",
        "some_url_link_slug",
        # survives: protocol concepts (bare http_ excluded), process words,
        # decision/date tags
        "http_2_connections",
        "http_client",
        "gdpr",
        "sprint_review",
        "pr_review",
        "code_review",
        "decision_do_not_merge_the_hotfix",
        "deadline_2026_03_01",
    }
    SOURCES = {
        "pr_titles": ["Accessible Navigation Bar!"],
        "pr_links": ["https://github.com/acme/pull/1"],
        "url_links": ["some url link slug"],
        "doc_links": ["some document link slug"],
    }

    def test_the_union_is_exactly_the_dying_tags(self):
        classes = beg.derive_removal(self.TAGS, self.SOURCES)
        self.assertEqual(classes["REMOVE"], {
            "accessible_navigation_bar",
            "https_github_com_acme_pull_1",
            "www_example_com_story",
            "github_com_django_django_pull_3704",
            "github_pr_302",
            "redis_pr_1759",
            "pull_request_4977",
            "tensorflow_tensorflow_pull_4897",
            "some_document_link_slug",
            "some_url_link_slug",
        })

    def test_bare_http_protocol_tags_are_not_removed(self):
        classes = beg.derive_removal(self.TAGS, self.SOURCES)
        self.assertNotIn("http_2_connections", classes["REMOVE"])
        self.assertNotIn("http_client", classes["REMOVE"])

    def test_decision_and_date_tags_are_not_removed(self):
        classes = beg.derive_removal(self.TAGS, self.SOURCES)
        self.assertNotIn("decision_do_not_merge_the_hotfix", classes["REMOVE"])
        self.assertNotIn("deadline_2026_03_01", classes["REMOVE"])

    def test_pr_pointer_forms_match_only_with_digits(self):
        classes = beg.derive_removal({"airflow_pr", "pr_review", "github_pr_9"},
                                     {"pr_titles": [], "pr_links": [],
                                      "url_links": [], "doc_links": []})
        self.assertEqual(classes["REMOVE"], {"github_pr_9"})

    def test_removal_impact_counts_tags_edges_and_chunks(self):
        remove = {"github_pr_1", "https_x"}
        degree = {"github_pr_1": 2, "https_x": 1, "gdpr": 3}
        chunk_tags = {"c1": {"github_pr_1", "gdpr"},
                      "c2": {"https_x"},
                      "c3": {"gdpr"}}
        self.assertEqual(beg.removal_impact(remove, degree, chunk_tags),
                         {"tags": 2, "edges": 3,
                          "chunks_touched": 2, "chunks_emptied": 1})


class GateTests(unittest.TestCase):
    def test_matching_census_passes(self):
        beg.gate("fixture", {"a": 1, "b": {"x": 2}}, {"a": 1, "b": {"x": 2}})

    def test_value_mismatch_stops(self):
        with self.assertRaises(SystemExit):
            beg.gate("fixture", {"a": 1}, {"a": 2})

    def test_missing_key_stops(self):
        with self.assertRaises(SystemExit):
            beg.gate("fixture", {}, {"a": 1})

    def test_unexpected_key_stops(self):
        with self.assertRaises(SystemExit):
            beg.gate("fixture", {"a": 1, "b": 2}, {"a": 1})


class RemovedShaGateTests(unittest.TestCase):
    def test_a_different_removed_set_stops_even_with_matching_counts(self):
        with self.assertRaises(SystemExit):
            beg.gate_removed_sha(["some_other_tag", "than_the_built_set"])

    def test_the_recorded_set_identity_passes(self):
        removed = ["github_pr_1", "https_x"]
        sha = hashlib.sha256("\n".join(removed).encode("utf-8")).hexdigest()
        with patch.object(beg, "EXPECTED_REMOVED_SHA256", sha):
            self.assertEqual(beg.gate_removed_sha(removed), sha)


class GuardTests(unittest.TestCase):
    def test_protected_databases_are_refused_as_targets(self):
        for target in ("herb", "herb-eval", "neo4j", "system"):
            with self.assertRaises(SystemExit):
                beg._guard_target("herb-eval", target)

    def test_herb_is_refused_as_source_too(self):
        with self.assertRaises(SystemExit):
            beg._guard_target("herb", "scratch-db")

    def test_source_equal_target_is_refused(self):
        with self.assertRaises(SystemExit):
            beg._guard_target("scratch-db", "scratch-db")

    def test_a_name_out_of_form_is_refused(self):
        with self.assertRaises(SystemExit):
            beg._guard_target("herb-eval", "Bad`Name")

    def test_the_default_pair_passes(self):
        beg._guard_target("herb-eval", "herb-eval-v2")


class BacktickQuotingTests(unittest.TestCase):
    def test_plain_names_quote(self):
        self.assertEqual(beg._bt("Person"), "`Person`")

    def test_inner_backticks_are_doubled(self):
        self.assertEqual(beg._bt("we`ird"), "`we``ird`")


class NodeLabelKeyTests(unittest.TestCase):
    def test_labels_sort_into_the_key_and_the_first_label_returns(self):
        self.assertEqual(beg.node_label_key("4:x:1", ["B", "A"]),
                         ("A\x00B", "B"))

    def test_zero_labels_fail_loud(self):
        with self.assertRaises(SystemExit):
            beg.node_label_key("4:x:1", [])


class RequireStepTests(unittest.TestCase):
    def _write(self, directory: Path, step: str, timestamp: str) -> None:
        (directory / f"step_{step}.json").write_text(
            json.dumps({"timestamp": timestamp}), encoding="utf-8")

    def test_a_missing_step_record_fails_loud(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(beg, "BUILD_DIR", Path(tmp)):
                with self.assertRaises(SystemExit):
                    beg._require_step("scratch-db", "copy")

    def test_a_downstream_record_older_than_its_upstream_is_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "scratch-db"
            directory.mkdir()
            self._write(directory, "copy", "2026-08-13T10:00:00Z")
            self._write(directory, "cleanup", "2026-08-12T20:36:45Z")
            with patch.object(beg, "BUILD_DIR", Path(tmp)):
                copy_rec = beg._require_step("scratch-db", "copy")
                with self.assertRaises(SystemExit):
                    beg._require_step("scratch-db", "cleanup", after=copy_rec)

    def test_records_in_order_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "scratch-db"
            directory.mkdir()
            self._write(directory, "copy", "2026-08-12T20:36:02Z")
            self._write(directory, "cleanup", "2026-08-12T20:36:45Z")
            with patch.object(beg, "BUILD_DIR", Path(tmp)):
                copy_rec = beg._require_step("scratch-db", "copy")
                beg._require_step("scratch-db", "cleanup", after=copy_rec)

    def test_a_fresh_copy_clears_every_earlier_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "scratch-db"
            directory.mkdir()
            for step in ("copy", "cleanup", "entities", "relations"):
                self._write(directory, step, "2026-08-12T20:36:02Z")
            (directory / "build_manifest.json").write_text("{}", encoding="utf-8")
            with patch.object(beg, "BUILD_DIR", Path(tmp)):
                beg._clear_build_records("scratch-db")
                self.assertEqual(list(directory.iterdir()), [])


class ClassifyIdTests(unittest.TestCase):
    def test_the_three_id_spaces_and_the_malformed_rest(self):
        self.assertEqual(beg.classify_id("eid_3b36c220"), "eid")
        self.assertEqual(beg.classify_id("EMP_123456"), "emp")
        self.assertEqual(beg.classify_id("CUST-42"), "cust")
        self.assertEqual(beg.classify_id("'eid_3b36c220'"), "malformed")
        self.assertEqual(beg.classify_id("eid_4eec2a5"), "malformed")
        self.assertEqual(beg.classify_id("slack_admin_bot"), "malformed")


FIXTURE_PRODUCTS = {
    "AcmeForce": {
        "slack": [
            {"Channel": {"name": "develop-acme"},
             "Message": {"User": {"userId": "eid_aaaaaaaa",
                                  "text": "ping eid_bbbbbbbb about CUST-7"}}},
            {"Channel": {"name": "develop-acme"},
             "Message": {"User": {"userId": "eid_aaaaaaaa",
                                  "text": "eid_bbbbbbbb again"}}},
        ],
        "prs": [
            {"title": "Fix", "user": {"login": "EMP_111111"},
             "summary": "reviewed with EMP_222222 in mind",
             "reviews": [{"user": {"login": "eid_cccccccc"}, "comment": "lgtm"}]},
        ],
        "documents": [
            {"author": "eid_dddddddd", "content": "long text", "feedback": "ok"},
        ],
        "meeting_transcripts": [
            {"participants": ["eid_aaaaaaaa", "'eid_eeeeeeee'"],
             "transcript": "we met"},
        ],
        "meeting_chats": [
            {"text": "chat mentions eid_ffffffff"},
        ],
        "urls": [
            {"link": "https://example.com"},
        ],
    },
}


FIXTURE_DIRECTORIES = {
    "employees": {
        "eid_aaaaaaaa": {"role": "Software Engineer", "location": "Austin",
                         "org": "acme"},
        "eid_bbbbbbbb": {"role": "QA Specialist", "location": "Berlin",
                         "org": "acme"},
        "eid_cccccccc": {"role": "Engineering Lead", "location": "Austin",
                         "org": "beta"},
        "eid_dddddddd": {"role": "Product Manager", "location": "Sydney",
                         "org": "beta"},
    },
    "customers": {"CUST-7": {"role": "CTO", "company": "TechCorp"}},
    "orgs": ["acme", "beta"],
    "companies": ["TechCorp"],
}


class DirectoryReaderTests(unittest.TestCase):
    EMPLOYEES = {
        "eid_00000001": {"employee_id": "eid_00000001", "name": "A One",
                         "role": "VP of Engineering", "org": "acme",
                         "location": "Austin"},
    }
    CUSTOMERS = [{"id": "CUST-0001", "name": "C One", "role": "CTO",
                  "company": "TechCorp"}]

    def _read(self, employees, customers):
        def fake(name):
            return employees if name == beg.EMPLOYEE_FILE else customers
        with patch.object(beg, "read_metadata", fake):
            return beg.read_directories()

    def test_the_nodes_carry_the_directory_fields_and_no_name(self):
        out = self._read(self.EMPLOYEES, self.CUSTOMERS)
        self.assertEqual(out["employees"], {
            "eid_00000001": {"role": "VP of Engineering", "location": "Austin",
                             "org": "acme"}})
        self.assertEqual(out["customers"],
                         {"CUST-0001": {"role": "CTO", "company": "TechCorp"}})
        self.assertEqual(out["orgs"], ["acme"])
        self.assertEqual(out["companies"], ["TechCorp"])

    def test_a_missing_field_stops_the_build(self):
        broken = {"eid_00000001": {"employee_id": "eid_00000001",
                                   "role": "VP of Engineering", "org": "acme"}}
        with self.assertRaises(SystemExit):
            self._read(broken, self.CUSTOMERS)

    def test_a_key_disagreeing_with_the_entry_id_stops_the_build(self):
        broken = {"eid_00000002": dict(self.EMPLOYEES["eid_00000001"])}
        with self.assertRaises(SystemExit):
            self._read(broken, self.CUSTOMERS)

    def test_a_customer_without_a_company_stops_the_build(self):
        with self.assertRaises(SystemExit):
            self._read(self.EMPLOYEES,
                       self.CUSTOMERS + [{"id": "CUST-0002", "role": "CEO"}])

    def test_a_duplicate_customer_id_stops_the_build(self):
        with self.assertRaises(SystemExit):
            self._read(self.EMPLOYEES, self.CUSTOMERS + self.CUSTOMERS)


class MembershipEdgeTests(unittest.TestCase):
    def test_every_entry_contributes_its_own_field_value(self):
        self.assertEqual(
            beg.membership_edges(FIXTURE_DIRECTORIES["employees"], "org"),
            [("eid_aaaaaaaa", "acme"), ("eid_bbbbbbbb", "acme"),
             ("eid_cccccccc", "beta"), ("eid_dddddddd", "beta")])
        self.assertEqual(
            beg.membership_edges(FIXTURE_DIRECTORIES["customers"], "company"),
            [("CUST-7", "TechCorp")])


class EntityDerivationTests(unittest.TestCase):
    def _rows(self):
        def loc(section, indices, channel=None):
            out = {"product": "AcmeForce", "section": section, "indices": indices}
            if channel:
                out["channel"] = channel
            return out

        import json
        return [
            {"chunkId": "c_slack", "section": "slack", "product": "AcmeForce",
             "channel": "develop-acme",
             "locator": json.dumps(loc("slack", [0, 1], "develop-acme"))},
            {"chunkId": "c_pr", "section": "prs", "product": "AcmeForce",
             "channel": None, "locator": json.dumps(loc("prs", [0]))},
            {"chunkId": "c_doc", "section": "documents", "product": "AcmeForce",
             "channel": None,
             "locator": json.dumps({"product": "AcmeForce",
                                    "section": "documents", "index": 0,
                                    "field": "content", "char_range": [0, 4]})},
            {"chunkId": "c_meet", "section": "meeting_transcripts",
             "product": "AcmeForce", "channel": None,
             "locator": json.dumps(loc("meeting_transcripts", [0]))},
            {"chunkId": "c_chat", "section": "meeting_chats",
             "product": "AcmeForce", "channel": None,
             "locator": json.dumps(loc("meeting_chats", [0]))},
            {"chunkId": "c_url", "section": "urls", "product": "AcmeForce",
             "channel": None, "locator": json.dumps(loc("urls", [0]))},
            {"chunkId": "c_meta", "section": None, "product": None,
             "channel": None,
             "locator": json.dumps({"metadata": "employee", "indices": [0]})},
        ]

    def _derive(self, rows=None):
        return beg.derive_entities(rows if rows is not None else self._rows(),
                                   FIXTURE_PRODUCTS, FIXTURE_DIRECTORIES)

    def test_roles_come_from_field_structure(self):
        derived = self._derive()
        self.assertEqual(derived["census"]["involves"],
                         {"speaker": 1, "reviewer": 1, "doc_author": 1,
                          "participant": 1})
        self.assertIn(("c_slack", "eid_aaaaaaaa", "speaker"), derived["involves"])
        self.assertIn(("c_doc", "eid_dddddddd", "doc_author"), derived["involves"])
        self.assertIn(("c_pr", "eid_cccccccc", "reviewer"), derived["involves"])

    def test_speaker_dedupes_at_chunk_grain(self):
        derived = self._derive()
        speakers = [e for e in derived["involves"] if e[2] == "speaker"]
        self.assertEqual(speakers, [("c_slack", "eid_aaaaaaaa", "speaker")])

    def test_an_id_no_directory_carries_gets_no_edge_and_a_census_row(self):
        derived = self._derive()
        self.assertFalse(any(pid in ("EMP_111111", "'eid_eeeeeeee'")
                             for _, pid, _ in derived["involves"]))
        self.assertEqual(derived["census"]["unlinked_involves"],
                         {"eid": 0, "emp": 1, "cust": 0, "malformed": 1})
        self.assertEqual(derived["census"]["unlinked_involve_ids"],
                         {"eid": 0, "emp": 1, "cust": 0, "malformed": 1})
        self.assertEqual(derived["unlinked_ids"]["malformed"],
                         ["'eid_eeeeeeee'"])

    def test_mentions_are_regex_over_content_leaves_deduped(self):
        derived = self._derive()
        self.assertEqual(derived["mentions"],
                         [("c_slack", "CUST-7"), ("c_slack", "eid_bbbbbbbb")])
        self.assertEqual(derived["census"]["mentions"],
                         {"employee": 1, "customer": 1})
        self.assertEqual(derived["census"]["mention_persons"],
                         {"employee": 1, "customer": 1})

    def test_a_mentioned_id_no_directory_carries_is_censused_apart(self):
        derived = self._derive()
        self.assertEqual(derived["census"]["unlinked_mentions"],
                         {"eid": 1, "emp": 1, "cust": 0})
        self.assertEqual(derived["unlinked_ids"]["mentions"],
                         {"eid": ["eid_ffffffff"], "emp": ["EMP_222222"],
                          "cust": []})

    def test_char_range_chunks_read_the_whole_carrier_record(self):
        derived = self._derive()
        self.assertIn(("c_doc", "eid_dddddddd", "doc_author"), derived["involves"])

    def test_metadata_and_url_chunks_carry_no_person_facts(self):
        derived = self._derive()
        for cid in ("c_meta", "c_url"):
            self.assertFalse(any(e[0] == cid for e in derived["involves"]))
            self.assertFalse(any(c == cid for c, _ in derived["mentions"]))

    def test_product_and_channel_edges_come_from_chunk_attributes(self):
        derived = self._derive()
        self.assertEqual(derived["census"]["product_edges"], 6)
        self.assertEqual(derived["census"]["channel_edges"], 1)
        self.assertEqual(derived["census"]["product_nodes"], 1)
        self.assertEqual(derived["census"]["channel_nodes"], 1)

    def test_the_node_census_is_the_directories_own_population(self):
        derived = self._derive()
        self.assertEqual(derived["census"]["employee_nodes"], 4)
        self.assertEqual(derived["census"]["customer_nodes"], 1)
        self.assertEqual(derived["census"]["org_nodes"], 2)
        self.assertEqual(derived["census"]["company_nodes"], 1)

    def test_slack_channel_mismatch_fails_loud(self):
        import json
        rows = [{"chunkId": "c_bad", "section": "slack", "product": "AcmeForce",
                 "channel": "other",
                 "locator": json.dumps({"product": "AcmeForce",
                                        "section": "slack", "indices": [0],
                                        "channel": "other-channel"})}]
        with self.assertRaises(SystemExit):
            self._derive(rows)

    def test_out_of_bounds_locator_fails_loud(self):
        import json
        rows = [{"chunkId": "c_oob", "section": "prs", "product": "AcmeForce",
                 "channel": None,
                 "locator": json.dumps({"product": "AcmeForce",
                                        "section": "prs", "indices": [99]})}]
        with self.assertRaises(SystemExit):
            self._derive(rows)

    def test_a_locator_with_neither_indices_nor_index_fails_loud(self):
        with self.assertRaises(SystemExit):
            beg.resolve_records({"product": "AcmeForce", "section": "prs"},
                                "prs", FIXTURE_PRODUCTS)

    def test_a_locator_with_empty_indices_fails_loud(self):
        with self.assertRaises(SystemExit):
            beg.resolve_records({"product": "AcmeForce", "section": "prs",
                                 "indices": []}, "prs", FIXTURE_PRODUCTS)


FIXTURE_TEAM = [
    {"employee_id": "eid_00000001", "role": "VP of Engineering", "org": "acme",
     "name": "V One",
     "engineering_leads": [
         {"employee_id": "eid_00000002", "role": "Engineering Lead",
          "org": "acme", "name": "L Two",
          "engineers": [{"employee_id": "eid_00000004", "role": "Software Engineer",
                         "org": "acme", "name": "E Four"},
                        {"employee_id": "eid_00000005", "role": "Software Engineer",
                         "org": "acme", "name": "E Five"}],
          "qa_specialists": [{"employee_id": "eid_00000006", "role": "QA Specialist",
                              "org": "acme", "name": "Q Six"}]},
     ],
     "product_managers": [
         {"employee_id": "eid_00000003", "role": "Product Manager",
          "org": "acme", "name": "P Three"},
     ]},
]

class OrgTreeRelationTests(unittest.TestCase):
    def test_report_lists_are_found_by_shape_not_by_name(self):
        self.assertEqual(beg.report_lists(FIXTURE_TEAM[0]),
                         ["engineering_leads", "product_managers"])
        self.assertEqual(beg.report_lists(FIXTURE_TEAM[0]["engineering_leads"][0]),
                         ["engineers", "qa_specialists"])

    def test_manages_carries_the_source_list_field_at_every_depth(self):
        org = beg.org_tree_relations(FIXTURE_TEAM)
        self.assertEqual(org["manages"], {
            ("eid_00000001", "eid_00000002", "engineering_leads"),
            ("eid_00000001", "eid_00000003", "product_managers"),
            ("eid_00000002", "eid_00000004", "engineers"),
            ("eid_00000002", "eid_00000005", "engineers"),
            ("eid_00000002", "eid_00000006", "qa_specialists"),
        })

    def test_colleagues_pair_everyone_reporting_to_one_entry_across_its_lists(self):
        org = beg.org_tree_relations(FIXTURE_TEAM)
        self.assertEqual(org["colleague"], {
            ("eid_00000002", "eid_00000003", "eid_00000001"),
            ("eid_00000004", "eid_00000005", "eid_00000002"),
            ("eid_00000004", "eid_00000006", "eid_00000002"),
            ("eid_00000005", "eid_00000006", "eid_00000002"),
        })

    def test_one_edge_per_unordered_pair_endpoints_in_sorted_order(self):
        org = beg.org_tree_relations(FIXTURE_TEAM)
        for a, b, _ in org["colleague"]:
            self.assertLess(a, b)

    def test_the_person_set_is_every_entry_in_the_tree(self):
        org = beg.org_tree_relations(FIXTURE_TEAM)
        self.assertEqual(org["persons"], {f"eid_0000000{i}" for i in range(1, 7)})

    def test_a_tree_top_reports_to_nobody(self):
        org = beg.org_tree_relations(FIXTURE_TEAM)
        self.assertFalse(any(b == "eid_00000001" for _, b, _ in org["manages"]))


class ArchiveManifestTests(unittest.TestCase):
    def test_no_manifest_archives_to_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(beg.archive_manifest(Path(tmp) / "build_manifest.json"))

    def test_the_prior_manifest_moves_aside_under_its_own_timestamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "build_manifest.json"
            path.write_text(json.dumps({"timestamp": "2026-08-12T20:38:00Z",
                                        "graph_version": "copy+entities",
                                        "graph_census_sha256": "cd34"}),
                            encoding="utf-8")
            identity = beg.archive_manifest(path)
            self.assertEqual(identity, {"file": "build_manifest_20260812T203800Z.json",
                                        "timestamp": "2026-08-12T20:38:00Z",
                                        "graph_version": "copy+entities",
                                        "graph_census_sha256": "cd34"})
            self.assertFalse(path.exists())
            archived = json.loads((path.parent / identity["file"])
                                  .read_text(encoding="utf-8"))
            self.assertEqual(archived["graph_version"], "copy+entities")

    def test_a_manifest_without_a_timestamp_stops_the_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "build_manifest.json"
            path.write_text("{}", encoding="utf-8")
            with self.assertRaises(SystemExit):
                beg.archive_manifest(path)
            self.assertTrue(path.is_file())

    def test_an_archive_name_already_taken_stops_the_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "build_manifest.json"
            path.write_text(json.dumps({"timestamp": "2026-08-12T20:38:00Z"}),
                            encoding="utf-8")
            (path.parent / "build_manifest_20260812T203800Z.json").write_text(
                "{}", encoding="utf-8")
            with self.assertRaises(SystemExit):
                beg.archive_manifest(path)
            self.assertTrue(path.is_file())


if __name__ == "__main__":
    unittest.main()

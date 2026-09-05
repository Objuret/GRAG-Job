import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from arms import artefact_v1 as arm
from arms import artefact_v1_det as det

CORPUS = Path(__file__).resolve().parent.parent.parent / "data" / "corpus" / "Salesforce__HERB"

_MODULE_FLAGS = (patch.object(arm, "CURVE_WALK", False),
                 patch.object(arm, "DOOR_TRACE", False),
                 patch.object(arm, "DESC_CUT", True),
                 patch.object(arm, "AGG", "sum"),
                 patch.object(arm, "NORM", "relative"),
                 patch.object(arm, "NORM_SCOPE", "per_path"),
                 patch.object(arm, "W_TAG", 1.0),
                 patch.object(arm, "W_DESC", 1.0),
                 patch.object(arm, "W_SCOPE", 1.0),
                 patch.object(arm, "W_PERSON", 1.0),
                 patch.object(arm, "PERSON_ON", True),
                 patch.object(arm, "PERSON_AMBIGUOUS", "all"),
                 patch.object(arm, "PERSON_NEAR", True),
                 patch.object(arm, "STR_FACET", 0.0),
                 patch.object(arm, "STR_WCHUNK", 1.0),
                 patch.object(arm, "STR_RELEVANCE", 1.0),
                 patch.object(arm, "STR_DESC_HINT", 1.0),
                 patch.object(arm, "STR_SCOPE_MATCH", 1.0),
                 patch.object(arm, "STR_PERSON_MATCH", 1.0),
                 patch.object(arm, "STR_GUIDE", 0.0),
                 patch.object(arm, "PERSON_ROLE_W",
                              {"speaker": 1.0, "participant": 1.0,
                               "reviewer": 1.0, "pr_author": 1.0,
                               "doc_author": 1.0, "mentions": 1.0}))

DIRECTORY = None


def setUpModule():
    global DIRECTORY
    DIRECTORY = arm._load_person_directory(CORPUS)
    for p in _MODULE_FLAGS:
        p.start()


def tearDownModule():
    for p in _MODULE_FLAGS:
        p.stop()


def _tag_row(chunk_id, support):
    return {"chunkId": chunk_id, "locator": "{}",
            "relpath": "Salesforce__HERB/products/TestForce.json",
            "sha256": "sha", "support": support, "facetTerm": 1.0,
            "w_chunk": 1.0, "relevance": 1.0}


def _person_row(chunk_id, sim, roles=("speaker",)):
    return {"chunkId": chunk_id, "locator": "{}",
            "relpath": "Salesforce__HERB/products/TestForce.json",
            "sha256": "sha", "roles": list(roles), "sim": sim}


class _Session:

    def __init__(self, ground_rows, level_chunks, person_rows=None):
        self.ground_rows = list(ground_rows)
        self.level_chunks = level_chunks
        self.person_rows = person_rows or {}
        self.person_params = []

    def run(self, query, **params):
        if query == arm._GROUND_CYPHER:
            return self.ground_rows.pop(0)
        if query == arm._AREA_CHUNKS_CYPHER:
            names = tuple(sorted(t["name"] for t in params["tags"]))
            return self.level_chunks.get(names, [])
        if query == arm._PERSON_CHUNKS_CYPHER:
            self.person_params.append(params)
            return self.person_rows.get(tuple(params["pids"]), [])
        return []


class _RefusingSession(_Session):

    def run(self, query, **params):
        if query == arm._PERSON_CHUNKS_CYPHER:
            raise AssertionError("the person path queried the graph while off")
        return super().run(query, **params)


def _plan(parts):
    neutral = {f: 0.5 for f in arm.ALL_FACETS}
    return {"description": "need",
            "parts": [{"t": p, "facets": neutral} for p in parts],
            "gate": {"product": None, "section": None, "channel": None,
                     "employee_id": None, "years": []}}


def _fake_embed(texts, kind, bar=True):
    return [[1.0, 0.0]] * len(texts), 1, 1, 1, 0.01


def _ground(name, sim):
    return {"name": name, "sim": sim, "emb": [1.0, 0.0]}


def _mention(name, ids, rule="exact"):
    return {"name": name, "rule": rule, "ids": list(ids)}


def _on(**overrides):
    patches = [patch.object(arm, "PERSON_ON", True),
               patch.object(arm, "W_PERSON", 1.0)]
    patches += [patch.object(arm, name, value) for name, value in overrides.items()]
    return patches


def _off(**overrides):
    patches = [patch.object(arm, "PERSON_ON", False),
               patch.object(arm, "W_PERSON", 0.0)]
    patches += [patch.object(arm, name, value) for name, value in overrides.items()]
    return patches


class _PatchSet:
    def __init__(self, patches):
        self.patches = patches

    def __enter__(self):
        for p in self.patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in reversed(self.patches):
            p.stop()
        return False


class DirectoryTests(unittest.TestCase):

    def test_the_directory_is_the_corpus_view_never_raw(self):
        self.assertEqual(arm.EMPLOYEE_JSON, "metadata/employee.json")
        self.assertEqual(arm.CUSTOMERS_JSON, "metadata/customers_data.json")
        self.assertTrue((CORPUS / arm.EMPLOYEE_JSON).is_file())
        self.assertTrue((CORPUS / arm.CUSTOMERS_JSON).is_file())

    def test_the_census_is_the_directory_it_read(self):
        self.assertEqual(DIRECTORY["counts"],
                         {"employees": 530, "customers": 120, "names": 201,
                          "ids": 650})

    def test_every_directory_name_is_two_tokens(self):
        self.assertEqual(DIRECTORY["lengths"], (2,))

    def test_the_name_vocabulary_is_narrower_than_the_population(self):
        sizes = [len(v) for v in DIRECTORY["ids"].values()]
        self.assertEqual(len(DIRECTORY["ids"]), 201)
        self.assertEqual(max(sizes), 11)
        self.assertEqual(sum(1 for s in sizes if s == 1), 99)

    def test_a_missing_directory_fails_loud(self):
        with self.assertRaisesRegex(RuntimeError, "person directory missing"):
            arm._load_person_directory(CORPUS / "no_such_corpus")

    def test_resolving_without_a_loaded_directory_fails_loud(self):
        with self.assertRaisesRegex(RuntimeError, "no person directory is loaded"):
            arm.resolve_persons("Hannah Taylor", None)


class ResolutionTests(unittest.TestCase):

    @staticmethod
    def _rules(text):
        return [(m["rule"], m["name"]) for m in arm.resolve_persons(text, DIRECTORY)]

    def test_an_exact_name_resolves_to_the_ids_that_carry_it(self):
        found = arm.resolve_persons("What did Hannah Taylor decide?", DIRECTORY)
        self.assertEqual([m["rule"] for m in found], ["exact"])
        self.assertEqual(found[0]["name"], "Hannah Taylor")
        self.assertEqual(list(found[0]["ids"]),
                         list(DIRECTORY["ids"][("hannah", "taylor")]))

    def test_case_and_spacing_differences_resolve_as_normalized(self):
        found = arm.resolve_persons("hannah  taylor spoke", DIRECTORY)
        self.assertEqual([m["rule"] for m in found], ["normalized"])
        self.assertEqual(found[0]["ids"],
                         list(DIRECTORY["ids"][("hannah", "taylor")]))

    def test_an_id_written_in_the_query_is_taken_as_itself(self):
        found = arm.resolve_persons("did eid_9b023657 review CUST-0001?", DIRECTORY)
        self.assertEqual([(m["rule"], m["ids"]) for m in found],
                         [("id_literal", ["eid_9b023657"]),
                          ("id_literal", ["CUST-0001"])])

    def test_the_pr_login_id_space_resolves_too(self):
        found = arm.resolve_persons("who is EMP_123456?", DIRECTORY)
        self.assertEqual([(m["rule"], m["ids"]) for m in found],
                         [("id_literal", ["EMP_123456"])])

    def test_a_miscased_id_resolves_to_nothing_and_says_so(self):
        found = arm.resolve_persons("EID_792D7501 and cust-0001 and eid_9b023657",
                                    DIRECTORY)
        self.assertEqual([(m["rule"], m["name"], m["ids"]) for m in found],
                         [("unresolved", "EID_792D7501", []),
                          ("unresolved", "cust-0001", []),
                          ("id_literal", "eid_9b023657", ["eid_9b023657"])])

    def test_a_name_the_directory_does_not_carry_resolves_to_nothing(self):
        found = arm.resolve_persons("What did Zaphod Beeblebrox say?", DIRECTORY)
        self.assertEqual([(m["rule"], m["ids"]) for m in found],
                         [("unresolved", [])])

    def test_the_reordered_form_is_a_near_match(self):
        self.assertEqual(self._rules("Taylor, Hannah — her call?"),
                         [("reordered", "Taylor, Hannah")])

    def test_an_initial_and_a_last_name_is_a_near_match(self):
        found = arm.resolve_persons("Did H. Taylor sign off?", DIRECTORY)
        self.assertEqual([m["rule"] for m in found], ["initial"])
        self.assertEqual(found[0]["ids"],
                         list(DIRECTORY["initials"][("h", "taylor")]))

    def test_an_article_before_a_surname_is_not_an_initial(self):
        self.assertEqual(arm.resolve_persons("Did a Brown review the PR?", DIRECTORY), [])
        self.assertEqual(self._rules("I Brown said so"), [("unresolved", "I Brown")])
        self.assertEqual(self._rules("A Taylor is here"), [("unresolved", "A Taylor")])

    def test_those_letters_are_initials_when_written_as_initials(self):
        self.assertEqual(self._rules("Did A. Taylor sign off?"),
                         [("initial", "A. Taylor")])
        self.assertEqual(self._rules("I. Brown said so"), [("initial", "I. Brown")])

    def test_the_near_tier_is_flagged_off(self):
        with _PatchSet([patch.object(arm, "PERSON_NEAR", False)]):
            self.assertEqual(self._rules("Taylor, Hannah — her call?"),
                             [("unresolved", "Taylor, Hannah")])

    def test_the_ambiguity_policy_keeps_every_candidate_id(self):
        found = arm.resolve_persons("Hannah Taylor", DIRECTORY)
        self.assertGreater(len(found[0]["ids"]), 1)

    def test_the_ambiguity_policy_can_drop_the_mention_instead(self):
        with _PatchSet([patch.object(arm, "PERSON_AMBIGUOUS", "none")]):
            found = arm.resolve_persons("Hannah Taylor and Frank Lewis", DIRECTORY)
        self.assertEqual([(m["rule"], m["ids"]) for m in found],
                         [("ambiguous", []), ("exact", ["CUST-0001"])])

    def test_one_id_set_named_twice_is_one_mention(self):
        found = arm.resolve_persons("Hannah Taylor asked Hannah Taylor", DIRECTORY)
        self.assertEqual(len(found), 1)

    def test_mentions_come_back_in_query_order(self):
        found = arm.resolve_persons("Frank Lewis wrote to Hannah Taylor", DIRECTORY)
        self.assertEqual([m["name"] for m in found],
                         ["Frank Lewis", "Hannah Taylor"])

    def test_an_id_is_never_read_as_a_name(self):
        found = arm.resolve_persons("eid_9b023657", DIRECTORY)
        self.assertEqual([m["rule"] for m in found], ["id_literal"])

    def test_resolution_is_deterministic(self):
        text = "Hannah Taylor, Frank Lewis and H. Miller in 2026"
        self.assertEqual(arm.resolve_persons(text, DIRECTORY),
                         arm.resolve_persons(text, DIRECTORY))


class WeightZeroTests(unittest.TestCase):

    def test_the_shipped_weight_starts_where_the_other_paths_do(self):
        module = Path(arm.__file__).read_text(encoding="utf-8")
        self.assertIn('W_PERSON = _env_float("HERB_W_PERSON", 1.0)', module)
        self.assertIn("PERSON_ON = W_PERSON > 0.0", module)
        for line in ('W_TAG = _env_float("HERB_W_TAG", 1.0)',
                     'W_DESC = _env_float("HERB_W_DESC", 1.0)',
                     'W_SCOPE = _env_float("HERB_W_SCOPE", 1.0)'):
            self.assertIn(line, module)

    def test_a_negative_weight_is_refused(self):
        self.assertIn("HERB_W_PERSON must be >= 0.0",
                      Path(arm.__file__).read_text(encoding="utf-8"))

    def test_nothing_queries_the_graph_and_the_scores_do_not_move(self):
        session = _RefusingSession([[_ground("a", 0.9)]],
                                   {("a",): [_tag_row("c1", 0.5)]})
        with patch.object(arm, "_embed", side_effect=_fake_embed), \
             _PatchSet(_off()):
            quiet, _, quiet_meta = arm._retrieve(session, _plan(["p"]), k=5)
            loud, _, loud_meta = arm._retrieve(
                _RefusingSession([[_ground("a", 0.9)]],
                                 {("a",): [_tag_row("c1", 0.5)]}),
                _plan(["p"]), k=5,
                persons=[_mention("Hannah Taylor", ["eid_2f10ad20"])])
        self.assertEqual(quiet, loud)
        self.assertEqual(quiet_meta, loud_meta)
        self.assertNotIn("person", quiet_meta)

    def test_the_door_trace_carries_no_person_cell_at_weight_zero(self):
        session = _Session([[_ground("a", 0.9)]], {("a",): [_tag_row("c1", 0.5)]})
        with patch.object(arm, "_embed", side_effect=_fake_embed), \
             _PatchSet(_off(DOOR_TRACE=True)):
            _, _, meta = arm._retrieve(session, _plan(["p"]), k=5)
        self.assertEqual(set(meta["door_trace"][0]),
                         {"chunkId", "locator", "relpath", "sha256",
                          "tag", "desc", "scope", "total"})


class PersonPathTests(unittest.TestCase):

    @staticmethod
    def _session():
        return _Session(
            [[_ground("a", 0.9)]],
            {("a",): [_tag_row("c-tag", 0.5)]},
            person_rows={("eid_1",): [_person_row("c-p1", 0.9),
                                      _person_row("c-tag", 0.5)],
                         ("eid_2",): [_person_row("c-p1", 0.8)]},
        )

    def test_a_named_persons_chunks_join_the_pool_and_score(self):
        session = self._session()
        with patch.object(arm, "_embed", side_effect=_fake_embed), \
             _PatchSet(_on()):
            rows, _, meta = arm._retrieve(session, _plan(["p"]), k=5,
                                          persons=[_mention("N", ["eid_1"])])
        by_id = {r["chunkId"]: r["score"] for r in rows}
        self.assertIn("c-p1", by_id)
        self.assertGreater(by_id["c-p1"], 0.0)
        self.assertEqual(meta["person"]["chunks"], 2)

    def test_the_query_carries_the_resolved_ids_and_the_oracle_sections(self):
        session = self._session()
        with patch.object(arm, "_embed", side_effect=_fake_embed), \
             _PatchSet(_on()):
            arm._retrieve(session, _plan(["p"]), k=5,
                          persons=[_mention("N", ["eid_1", "eid_2"])])
        params = session.person_params[0]
        self.assertEqual(params["pids"], ["eid_1", "eid_2"])
        self.assertEqual(params["excludedSections"], arm._EXCLUDED_PARAM)
        self.assertEqual(params["mentionRole"], arm.MENTION_ROLE)
        self.assertEqual(params["datasetId"], arm.DATASET_ID)

    def test_a_mention_that_resolved_to_nothing_never_queries(self):
        session = self._session()
        with patch.object(arm, "_embed", side_effect=_fake_embed), \
             _PatchSet(_on()):
            _, _, meta = arm._retrieve(session, _plan(["p"]), k=5,
                                       persons=[_mention("X", [], "unresolved")])
        self.assertEqual(session.person_params, [])
        self.assertEqual(meta["person"]["named"], 0)
        self.assertEqual(meta["person"]["mentions"][0]["chunks"], 0)

    def test_the_path_only_adds_and_never_removes(self):
        with patch.object(arm, "_embed", side_effect=_fake_embed):
            before, _, _ = arm._retrieve(self._session(), _plan(["p"]), k=5)
            with _PatchSet(_on()):
                after, _, _ = arm._retrieve(
                    self._session(), _plan(["p"]), k=5,
                    persons=[_mention("N", ["eid_1"])])
        was = {r["chunkId"]: r["score"] for r in before}
        now = {r["chunkId"]: r["score"] for r in after}
        self.assertTrue(set(was) <= set(now))
        for cid, score in was.items():
            self.assertGreaterEqual(now[cid], score)

    def _role_scores(self, weight):
        roles = {role: weight for role in arm.PERSON_ROLE_W}
        with patch.object(arm, "_embed", side_effect=_fake_embed), \
             _PatchSet(_on(PERSON_ROLE_W=roles)):
            rows, _, meta = arm._retrieve(
                self._session(), _plan(["p"]), k=5,
                persons=[_mention("N", ["eid_1"])])
        return {r["chunkId"]: r["score"] for r in rows}, meta

    def test_only_adding_is_a_per_path_property(self):
        def rows(scope, persons):
            patches = [patch.object(arm, "NORM_SCOPE", scope)]
            if persons:
                patches += _on()
            with patch.object(arm, "_embed", side_effect=_fake_embed), \
                 _PatchSet(patches):
                out, _, _ = arm._retrieve(self._session(), _plan(["p"]), k=5,
                                          persons=persons)
            return {r["chunkId"]: r["score"] for r in out}
        mention = [_mention("N", ["eid_1"])]
        self.assertEqual(rows("per_path", None)["c-tag"],
                         rows("per_path", mention)["c-tag"])
        self.assertLess(rows("global", mention)["c-tag"],
                        rows("global", None)["c-tag"])

    def test_a_zero_role_weight_removes_no_chunk(self):
        by_id, meta = self._role_scores(0.0)
        self.assertIn("c-p1", by_id)
        self.assertEqual(meta["person"]["chunks"], 2)

    def test_a_zero_role_weight_damps_to_no_contribution(self):
        with patch.object(arm, "_embed", side_effect=_fake_embed):
            off, _, _ = arm._retrieve(self._session(), _plan(["p"]), k=5)
        off_by_id = {r["chunkId"]: r["score"] for r in off}
        zero, _ = self._role_scores(0.0)
        self.assertEqual(zero["c-tag"], off_by_id["c-tag"])
        self.assertEqual(zero["c-p1"], 0.0)

    def test_the_role_weight_grades_monotonically(self):
        full, half, none = (self._role_scores(w)[0] for w in (1.0, 0.5, 0.0))
        self.assertGreater(full["c-p1"], half["c-p1"])
        self.assertGreater(half["c-p1"], none["c-p1"])
        self.assertAlmostEqual(half["c-p1"], 0.5 * full["c-p1"], places=3)

    def test_a_negative_role_weight_is_refused(self):
        module = Path(arm.__file__).read_text(encoding="utf-8")
        self.assertIn("must be >= 0.0 — a role weight grades a", module)
        self.assertIn("_NEGATIVE_ROLES", module)

    def test_a_role_weight_grades_the_link(self):
        session = _Session(
            [[_ground("a", 0.9)]], {("a",): [_tag_row("c-tag", 0.5)]},
            person_rows={("eid_1",): [_person_row("c-speaker", 0.9, ["speaker"]),
                                      _person_row("c-mention", 0.9, ["mentions"])]})
        roles = dict(arm.PERSON_ROLE_W, mentions=0.25)
        with patch.object(arm, "_embed", side_effect=_fake_embed), \
             _PatchSet(_on(PERSON_ROLE_W=roles)):
            rows, _, _ = arm._retrieve(session, _plan(["p"]), k=5,
                                       persons=[_mention("N", ["eid_1"])])
        by_id = {r["chunkId"]: r["score"] for r in rows}
        self.assertGreater(by_id["c-speaker"], by_id["c-mention"])

    def test_a_chunks_best_link_is_the_one_that_counts(self):
        self.assertEqual(arm._role_weight(["mentions", "speaker"]), 1.0)

    def test_an_unknown_role_fails_loud(self):
        with self.assertRaisesRegex(RuntimeError, "has no weight"):
            arm._role_weight(["ghostwriter"])

    @staticmethod
    def _two_named_session():
        return _Session(
            [[_ground("a", 0.9)]],
            {("a",): [_tag_row("c-tag", 0.5)]},
            person_rows={("eid_1",): [_person_row("c-both", 0.9),
                                      _person_row("c-one", 0.9),
                                      _person_row("c-far", 0.1)],
                         ("eid_2",): [_person_row("c-both", 0.9)]},
        )

    def _two_named_rows(self, **overrides):
        with patch.object(arm, "_embed", side_effect=_fake_embed), \
             _PatchSet(_on(**overrides)):
            rows, _, _ = arm._retrieve(
                self._two_named_session(), _plan(["p"]), k=5,
                persons=[_mention("N1", ["eid_1"]), _mention("N2", ["eid_2"])])
        return {r["chunkId"]: r["score"] for r in rows}

    def test_carrying_more_of_the_named_persons_outranks_carrying_fewer(self):
        by_id = self._two_named_rows()
        self.assertGreater(by_id["c-both"], by_id["c-one"])
        self.assertGreater(by_id["c-one"], by_id["c-far"])

    def test_the_match_fraction_modifier_grades_by_its_strength(self):
        full = self._two_named_rows()
        inert = self._two_named_rows(STR_PERSON_MATCH=0.0)
        self.assertAlmostEqual(full["c-one"], 0.5 * inert["c-one"], places=3)
        self.assertEqual(full["c-both"], inert["c-both"])
        self.assertEqual(set(full), set(inert))

    def test_the_weight_scales_what_the_path_contributes(self):
        with patch.object(arm, "_embed", side_effect=_fake_embed):
            with _PatchSet(_on(W_PERSON=1.0)):
                light, _, _ = arm._retrieve(
                    self._session(), _plan(["p"]), k=5,
                    persons=[_mention("N", ["eid_1"])])
            with _PatchSet(_on(W_PERSON=4.0)):
                heavy, _, _ = arm._retrieve(
                    self._session(), _plan(["p"]), k=5,
                    persons=[_mention("N", ["eid_1"])])
        light_by_id = {r["chunkId"]: r["score"] for r in light}
        heavy_by_id = {r["chunkId"]: r["score"] for r in heavy}
        self.assertAlmostEqual(heavy_by_id["c-p1"], 4.0 * light_by_id["c-p1"])

    def test_the_meta_records_the_resolution_that_ran(self):
        with patch.object(arm, "_embed", side_effect=_fake_embed), \
             _PatchSet(_on()):
            _, _, meta = arm._retrieve(
                self._session(), _plan(["p"]), k=5,
                persons=[_mention("Hannah Taylor", ["eid_1"], "exact"),
                         _mention("Zaphod Beeblebrox", [], "unresolved")])
        self.assertEqual(meta["person"]["w"], 1.0)
        self.assertEqual(meta["person"]["named"], 1)
        self.assertEqual(
            [(m["name"], m["rule"], m["ids"], m["chunks"])
             for m in meta["person"]["mentions"]],
            [("Hannah Taylor", "exact", ["eid_1"], 2),
             ("Zaphod Beeblebrox", "unresolved", [], 0)])

    def test_the_walk_log_carries_the_person_openings(self):
        with patch.object(arm, "_embed", side_effect=_fake_embed), \
             _PatchSet(_on()):
            _, _, meta = arm._retrieve(
                self._session(), _plan(["p"]), k=5,
                persons=[_mention("N", ["eid_1"])])
        person_steps = [w for w in meta["walk"] if w["path"] == "person"]
        self.assertEqual(person_steps,
                         [{"part": "N", "path": "person", "ids": 1,
                           "chunks": 2, "new": 1}])

    def test_the_door_trace_carries_the_person_cell_while_on(self):
        with patch.object(arm, "_embed", side_effect=_fake_embed), \
             _PatchSet(_on(DOOR_TRACE=True)):
            _, _, meta = arm._retrieve(
                self._session(), _plan(["p"]), k=5,
                persons=[_mention("N", ["eid_1"])])
        self.assertIn("person", meta["door_trace"][0])


class PrepareTests(unittest.TestCase):

    class _Result:
        def __init__(self, row):
            self.row = row

        def consume(self):
            return None

        def single(self):
            return self.row

    class _Session:
        def __init__(self, person_nodes):
            self.person_nodes = person_nodes

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def run(self, query, **params):
            if "SHOW INDEXES" in query:
                return PrepareTests._Result(
                    {"names": [arm.GROUND_INDEX, arm.DESC_INDEX]})
            if "desc_emb IS NULL" in query:
                return PrepareTests._Result({"n": 0})
            if "HAS_CHUNK" in query:
                return PrepareTests._Result({"bad": 0})
            if "(p:Person)" in query:
                return PrepareTests._Result({"n": self.person_nodes})
            return PrepareTests._Result({})

    class _Driver:
        def __init__(self, person_nodes):
            self.person_nodes = person_nodes
            self.closed = False

        def session(self, database=None):
            return PrepareTests._Session(self.person_nodes)

        def close(self):
            self.closed = True

    def test_a_graph_without_the_entity_layer_fails_loud(self):
        driver = self._Driver(person_nodes=0)
        with _PatchSet(_on()), patch.object(arm, "_driver", return_value=driver):
            with self.assertRaisesRegex(RuntimeError, "carries no Person nodes"):
                arm.prepare_over_corpus(CORPUS)
        self.assertTrue(driver.closed)

    def test_a_graph_with_the_entity_layer_prepares_and_says_so(self):
        driver = self._Driver(person_nodes=5233)
        out = io.StringIO()
        with _PatchSet(_on()), patch.object(arm, "_driver", return_value=driver):
            with redirect_stdout(out):
                prepared = arm.prepare_over_corpus(CORPUS)
        self.assertEqual(prepared.directory["counts"]["names"], 201)
        self.assertIn("person directory 530 employees", out.getvalue())
        self.assertIn("5233 Person nodes", out.getvalue())

    def test_the_directory_is_not_read_at_weight_zero(self):
        driver = self._Driver(person_nodes=0)
        with _PatchSet(_off()), patch.object(arm, "_driver", return_value=driver), \
             patch.object(arm, "_load_person_directory") as load:
            prepared = arm.prepare_over_corpus(CORPUS)
        load.assert_not_called()
        self.assertIsNone(prepared.directory)


class FlagTests(unittest.TestCase):

    NAMES = ("HERB_W_PERSON", "HERB_STR_PERSON_MATCH", "HERB_PERSON_AMBIGUOUS",
             "HERB_PERSON_NEAR", "HERB_W_ROLE_SPEAKER", "HERB_W_ROLE_PARTICIPANT",
             "HERB_W_ROLE_REVIEWER", "HERB_W_ROLE_PR_AUTHOR",
             "HERB_W_ROLE_DOC_AUTHOR", "HERB_W_ROLE_MENTIONS")

    def test_the_interpreting_leg_records_them(self):
        for name in self.NAMES:
            self.assertIn(name, arm.RETRIEVAL_FLAGS)

    def test_the_deterministic_leg_records_them(self):
        for name in self.NAMES:
            self.assertIn(name, det.RETRIEVAL_FLAGS)

    def test_every_flag_records_the_value_the_run_carries(self):
        constants = {"HERB_W_PERSON": "W_PERSON",
                     "HERB_STR_PERSON_MATCH": "STR_PERSON_MATCH",
                     "HERB_PERSON_AMBIGUOUS": "PERSON_AMBIGUOUS",
                     "HERB_PERSON_NEAR": "PERSON_NEAR",
                     "HERB_W_ROLE_SPEAKER": "W_ROLE_SPEAKER",
                     "HERB_W_ROLE_PARTICIPANT": "W_ROLE_PARTICIPANT",
                     "HERB_W_ROLE_REVIEWER": "W_ROLE_REVIEWER",
                     "HERB_W_ROLE_PR_AUTHOR": "W_ROLE_PR_AUTHOR",
                     "HERB_W_ROLE_DOC_AUTHOR": "W_ROLE_DOC_AUTHOR",
                     "HERB_W_ROLE_MENTIONS": "W_ROLE_MENTIONS"}
        self.assertEqual(sorted(constants), sorted(self.NAMES))
        module = Path(arm.__file__).read_text(encoding="utf-8")
        for flag, constant in constants.items():
            self.assertIn(f'"{flag}": {constant},', module)

    def test_the_shipped_defaults_are_the_sources(self):
        module = Path(arm.__file__).read_text(encoding="utf-8")
        for line in ('W_PERSON = _env_float("HERB_W_PERSON", 1.0)',
                     'STR_PERSON_MATCH = _env_float("HERB_STR_PERSON_MATCH", 1.0)',
                     'PERSON_AMBIGUOUS = os.environ.get("HERB_PERSON_AMBIGUOUS", "all")',
                     'PERSON_NEAR = _env_bool("HERB_PERSON_NEAR", True)',
                     'W_ROLE_SPEAKER = _env_float("HERB_W_ROLE_SPEAKER", 1.0)',
                     'W_ROLE_PARTICIPANT = _env_float("HERB_W_ROLE_PARTICIPANT", 1.0)',
                     'W_ROLE_REVIEWER = _env_float("HERB_W_ROLE_REVIEWER", 1.0)',
                     'W_ROLE_PR_AUTHOR = _env_float("HERB_W_ROLE_PR_AUTHOR", 1.0)',
                     'W_ROLE_DOC_AUTHOR = _env_float("HERB_W_ROLE_DOC_AUTHOR", 1.0)',
                     'W_ROLE_MENTIONS = _env_float("HERB_W_ROLE_MENTIONS", 1.0)'):
            self.assertIn(line, module)

    def test_the_roles_are_the_entity_layers_own(self):
        self.assertEqual(sorted(arm.PERSON_ROLE_W),
                         ["doc_author", "mentions", "participant", "pr_author",
                          "reviewer", "speaker"])


if __name__ == "__main__":
    unittest.main()

import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import numpy as np

import run
from graph.build_facet_layer import REGISTER
from arms import artefact_v1_five_questions as arm

_CACHE = Path(tempfile.mkdtemp(prefix="five_questions_"))
_MODULE_FLAGS = (
    patch.object(arm, "FIVE_QUESTIONS_CACHE_DIR", _CACHE),
    patch.object(arm, "ROLE_SOURCE", "derived"),
    patch.object(arm, "ROLE_FIT", "raw"),
    patch.object(arm, "ENTITY_AGG", "max"),
    patch.object(arm, "ACTIVITY_AGG", "max"),
    patch.object(arm, "EVIDENCE_MATCH", "label"),
    patch.object(arm, "SILENT", "floor"),
    patch.object(arm, "COMBINE", "additive"),
    patch.object(arm, "TIME_SCALE", 0.0),
    patch.object(arm, "_QWEIGHTS", {q: 1.0 for q in arm.ALL_FACETS}),
)


def setUpModule():
    for p in _MODULE_FLAGS:
        p.start()


def tearDownModule():
    for p in _MODULE_FLAGS:
        p.stop()
    shutil.rmtree(_CACHE, ignore_errors=True)


def _unit_rows(rows):
    a = np.array(rows, dtype=np.float32)
    return a / np.linalg.norm(a, axis=1, keepdims=True)


def _chunk_row(chunk_id, **fields):
    row = {"chunkId": chunk_id, "locator": "{}",
           "relpath": "Salesforce__HERB/products/TestForce.json",
           "sha256": "sha", "empty": False, "section": "slack",
           "kind": "slack_window", "channel": None}
    row.update(fields)
    return row


_FEATURES = list(REGISTER)
_TAGS = ["t0", "t1", "t2", "t3", "t4", "t5"]
_ROLES = np.array([1, 1, 2, 2, 0, 3])
_TAG_EMB = _unit_rows([[1.0, 0.0], [0.98, 0.2], [0.0, 1.0],
                       [0.1, 0.99], [-1.0, 0.0], [0.0, -1.0]])
_EDGE_TAG = ["t0", "t2", "t1", "t3", "t4", "t5"]
_EDGE_CHUNK = ["c0", "c0", "c1", "c1", "c2", "c2"]

_D0 = float(date(2026, 1, 15).toordinal())
_D1 = float(date(2025, 6, 1).toordinal())
_D3 = float(date(2026, 3, 1).toordinal())
_DAYS = np.array([_D0, _D1, np.nan, _D3])


def _col(feature):
    return _FEATURES.index(feature)


def _zprofile():
    z = np.zeros((4, len(_FEATURES)))
    z[0, [_col("numeral"), _col("percent"), _col("money"), _col("unit")]] = 2.0
    z[1, _col("causal")] = 3.0
    z[2, [_col("modal"), _col("procedure")]] = 2.0
    z[3, [_col("first_person"), _col("second_person")]] = 2.0
    return z


def _answers(roles=None, days=None, zprofile=None, chunk_ids=None):
    return {"roles": _ROLES if roles is None else roles,
            "days": _DAYS if days is None else days,
            "zprofile": _zprofile() if zprofile is None else zprofile,
            "tag": list(_TAGS),
            "chunk_id": chunk_ids or ["c0", "c1", "c2", "c3"],
            "features": list(_FEATURES)}


def _layer(chunk_rows=None, products=(), tag_emb=None, desc_emb=None, **answer_kw):
    rows = chunk_rows or [_chunk_row("c0"), _chunk_row("c1"), _chunk_row("c2"),
                          _chunk_row("c3")]
    desc = (desc_emb if desc_emb is not None
            else _unit_rows([[1.0, 0.0], [0.6, 0.8], [-1.0, 0.0], [0.0, -1.0]]))
    return arm._build_layer(rows, list(products), list(_TAGS),
                            _TAG_EMB if tag_emb is None else tag_emb,
                            desc[:len(rows)], _EDGE_TAG, _EDGE_CHUNK,
                            _answers(**answer_kw))


_QVEC = _unit_rows([[0.9, 0.1]])[0]

_NOTHING = {"names": [], "actions": [], "time": None, "kind": None}
_NO_VECS = np.zeros((0, 2), dtype=np.float32)


class RoleTests(unittest.TestCase):
    def test_the_role_is_the_argmax_of_the_tags_marginal(self):
        phi = np.array([[0.9, 0.1, 0.5, 0.5, 0.5],
                        [0.1, 0.9, 0.5, 0.5, 0.5]])
        evidenced = np.ones(phi.shape, dtype=bool)
        fit, present = arm._role_fit_derived(phi, evidenced, ["a", "b"], ["a", "b"])
        np.testing.assert_array_equal(arm._roles(fit, present), [0, 1])

    def test_the_marginal_averages_over_the_tags_edges(self):
        phi = np.array([[0.9, 0.1, 0.5, 0.5, 0.5],
                        [0.5, 0.9, 0.5, 0.5, 0.5]])
        evidenced = np.ones(phi.shape, dtype=bool)
        fit, _ = arm._role_fit_derived(phi, evidenced, ["a", "a"], ["a"])
        np.testing.assert_allclose(fit[0], (phi - arm.PHI_NEUTRAL).mean(axis=0))

    def test_an_unevidenced_cell_contributes_nothing(self):
        phi = np.array([[0.5, 0.5, 0.5, 0.99, 0.6]])
        evidenced = np.ones(phi.shape, dtype=bool)
        evidenced[0, 3] = False
        fit, present = arm._role_fit_derived(phi, evidenced, ["a"], ["a"])
        self.assertEqual(float(fit[0, 3]), 0.0)
        self.assertEqual(arm.ALL_FACETS[arm._roles(fit, present)[0]], "evidence")

    def test_the_zscored_reading_rescales_by_the_corpus_spread(self):
        fit = np.array([[0.4, 0.10, 0.0, 0.0, 0.0],
                        [-0.4, 0.00, 0.0, 0.0, 0.0],
                        [0.0, 0.01, 0.0, 0.0, 0.0]])
        present = np.ones(3, dtype=bool)
        self.assertEqual(int(arm._roles(fit, present)[0]), 0)
        with patch.object(arm, "ROLE_FIT", "zscored"):
            self.assertEqual(int(arm._roles(fit, present)[0]), 1)

    def test_the_baked_fit_averages_the_edges_carried_facet_cells(self):
        class FakeSession:
            def run(self, cypher, **kw):
                return iter([
                    {"tag": "a", "facets": ["topic", "entities"], "weights": [0.4, 0.8]},
                    {"tag": "a", "facets": ["entities"], "weights": [0.6]},
                    {"tag": "b", "facets": None, "weights": None},
                ])
        fit, present = arm._role_fit_baked(FakeSession(), ["a", "b"])
        np.testing.assert_allclose(fit[0], [0.4, 0.7, 0.0, 0.0, 0.0])
        self.assertEqual(present.tolist(), [True, False])

    def test_a_baked_facet_outside_the_five_fails_loud(self):
        class FakeSession:
            def run(self, cypher, **kw):
                return iter([{"tag": "a", "facets": ["mystery"], "weights": [0.5]}])
        with self.assertRaisesRegex(RuntimeError, "outside"):
            arm._role_fit_baked(FakeSession(), ["a"])


class NamedThingTests(unittest.TestCase):
    def test_the_read_finds_products_eids_and_multi_capital_tokens(self):
        names = arm._named_things(
            "Did TestForce and eid_4afd9484 adopt WebRTC?", ["TestForce"])
        self.assertEqual(names, ["TestForce", "eid_4afd9484", "WebRTC"])

    def test_a_capitalized_run_drops_its_leading_question_word(self):
        names = arm._named_things("Which Data Cloud Sync documents exist?", [])
        self.assertEqual(names, ["Data Cloud Sync"])

    def test_a_run_of_question_words_alone_names_nothing(self):
        self.assertEqual(arm._named_things("What Did they build?", []), [])

    def test_a_product_matches_whole_words_only(self):
        self.assertEqual(arm._named_things("is vizforcex better?", ["VizForce"]), [])

    def test_names_deduplicate_case_insensitively_in_mention_order(self):
        names = arm._named_things("TESTFORCE beats TestForce", ["TestForce"])
        self.assertEqual(names, ["TestForce"])


class ActionPhraseTests(unittest.TestCase):
    def test_a_verb_hit_carries_its_clause_window(self):
        actions = arm._action_phrases(
            "did the team adopt streaming to reduce latency in the initial connection?")
        self.assertIn("adopt streaming to reduce latency in", actions)
        self.assertIn("reduce latency in the initial connection", actions)

    def test_the_window_stops_at_the_clause_boundary(self):
        actions = arm._action_phrases("they approved it, then celebrated")
        self.assertEqual(actions, ["approved it"])

    def test_a_capitalized_hit_names_something_rather_than_doing_it(self):
        self.assertEqual(arm._action_phrases("Was Launchpad slow?"), [])

    def test_a_query_with_no_verb_asks_no_activity(self):
        self.assertEqual(arm._action_phrases("who is the owner of the roadmap?"), [])


class TimeReferenceTests(unittest.TestCase):
    def test_an_iso_day_is_a_point(self):
        ref = arm._time_reference("what shipped on 2026-07-12?")
        self.assertEqual((ref["form"], ref["lo"], ref["hi"]),
                         ("day", date(2026, 7, 12).toordinal(),
                          date(2026, 7, 12).toordinal()))

    def test_a_quarter_is_its_own_range(self):
        ref = arm._time_reference("revenue in Q1 2026?")
        self.assertEqual((ref["form"], ref["lo"], ref["hi"]),
                         ("range", date(2026, 1, 1).toordinal(),
                          date(2026, 3, 31).toordinal()))

    def test_a_worded_quarter_reads_the_same(self):
        ref = arm._time_reference("the fourth quarter of 2025")
        self.assertEqual((ref["lo"], ref["hi"]),
                         (date(2025, 10, 1).toordinal(),
                          date(2025, 12, 31).toordinal()))

    def test_a_month_is_its_own_range(self):
        ref = arm._time_reference("the March 2026 launch")
        self.assertEqual((ref["lo"], ref["hi"]),
                         (date(2026, 3, 1).toordinal(),
                          date(2026, 3, 31).toordinal()))

    def test_stated_years_span_their_range(self):
        ref = arm._time_reference("between 2025 and 2026")
        self.assertEqual((ref["form"], ref["lo"], ref["hi"]),
                         ("range", date(2025, 1, 1).toordinal(),
                          date(2026, 12, 31).toordinal()))

    def test_a_posture_word_reads_as_recency_direction(self):
        self.assertTrue(arm._time_reference("recent incidents")["late"])
        self.assertFalse(arm._time_reference("historical context")["late"])

    def test_a_stated_year_outranks_a_posture_word(self):
        self.assertEqual(arm._time_reference("recent changes in 2026")["form"],
                         "range")

    def test_no_reference_reads_none(self):
        self.assertIsNone(arm._time_reference("who owns the roadmap?"))

    def test_a_date_shaped_token_that_is_no_calendar_day_reads_on(self):
        ref = arm._time_reference("what shipped on 2026-13-01?")
        self.assertEqual(ref["form"], "range")
        self.assertEqual(ref["lo"], date(2026, 1, 1).toordinal())

    def test_a_valid_day_after_an_invalid_one_still_reads(self):
        ref = arm._time_reference("2026-13-01 or 2026-07-12?")
        self.assertEqual((ref["form"], ref["lo"]),
                         ("day", date(2026, 7, 12).toordinal()))


class EvidenceKindTests(unittest.TestCase):
    def test_the_question_forms_map_to_the_kinds(self):
        for text, kind in (("How many issues were filed?", "number"),
                           ("Why did the launch slip?", "cause"),
                           ("Was the budget approved?", "status"),
                           ("Compare the two rollouts", "comparison"),
                           ("Summarize the outage", "summary"),
                           ("What did the customer say?", "quote")):
            self.assertEqual(arm._evidence_kind(text), kind, text)

    def test_a_form_free_question_asks_no_kind(self):
        self.assertIsNone(arm._evidence_kind("Where is the office?"))

    def test_the_first_form_wins(self):
        self.assertEqual(arm._evidence_kind("Why was it approved?"), "cause")

    def test_every_signature_feature_is_a_register_feature(self):
        for kind, marks in arm.EVIDENCE_KIND_FEATURES.items():
            for f in marks:
                self.assertIn(f, REGISTER, f"{kind}: {f}")


class MatchTests(unittest.TestCase):
    def test_the_entity_match_is_the_best_pair_on_the_half_cosine_scale(self):
        layer = _layer()
        vecs = _unit_rows([[1.0, 0.0]])
        m = arm._pair_match(vecs, layer.tag_emb, layer.ent_rows, layer.ent_cols,
                            4, "max")
        want0 = (1.0 + float(layer.tag_emb[0] @ vecs[0])) / 2.0
        want1 = (1.0 + float(layer.tag_emb[1] @ vecs[0])) / 2.0
        np.testing.assert_allclose(m, [want0, want1, 0.0, 0.0])

    def test_the_mean_reading_averages_the_per_name_bests(self):
        layer = _layer()
        vecs = _unit_rows([[1.0, 0.0], [0.0, 1.0]])
        best = arm._pair_match(vecs, layer.tag_emb, layer.ent_rows,
                               layer.ent_cols, 4, "max")
        mean = arm._pair_match(vecs, layer.tag_emb, layer.ent_rows,
                               layer.ent_cols, 4, "mean")
        for c in (0, 1):
            per = [(1.0 + float(layer.tag_emb[[0, 1][c]] @ v)) / 2.0 for v in vecs]
            self.assertAlmostEqual(mean[c], float(np.mean(per)))
            self.assertLessEqual(mean[c], best[c])

    def test_an_empty_answer_set_carries_the_floor(self):
        layer = _layer()
        m = arm._pair_match(_unit_rows([[1.0, 0.0]]), layer.tag_emb,
                            layer.ent_rows, layer.ent_cols, 4, "max")
        self.assertEqual(m[2], 0.0)
        self.assertEqual(m[3], 0.0)

    def test_the_neutral_reading_puts_silence_at_the_midpoint(self):
        layer = _layer()
        with patch.object(arm, "SILENT", "neutral"):
            m = arm._pair_match(_unit_rows([[1.0, 0.0]]), layer.tag_emb,
                                layer.ent_rows, layer.ent_cols, 4, "max")
        self.assertEqual(m[2], arm.SILENT_NEUTRAL)

    def test_a_day_reference_decays_with_distance(self):
        layer = _layer()
        m = arm._match_temporal(layer, {"form": "day", "lo": _D0, "hi": _D0})
        self.assertEqual(m[0], 1.0)
        self.assertAlmostEqual(m[1], np.exp(-(_D0 - _D1) / layer.day_scale))
        self.assertAlmostEqual(m[3], np.exp(-(_D3 - _D0) / layer.day_scale))

    def test_a_range_reference_is_flat_inside_and_decays_outside(self):
        layer = _layer()
        m = arm._match_temporal(layer, {"form": "range", "lo": _D1, "hi": _D0})
        self.assertEqual(m[0], 1.0)
        self.assertEqual(m[1], 1.0)
        self.assertAlmostEqual(m[3], np.exp(-(_D3 - _D0) / layer.day_scale))

    def test_a_posture_word_maps_onto_recency_rank(self):
        layer = _layer()
        recent = arm._match_temporal(layer, {"form": "posture", "late": True})
        self.assertGreater(recent[3], recent[0])
        self.assertGreater(recent[0], recent[1])
        oldest = arm._match_temporal(layer, {"form": "posture", "late": False})
        self.assertGreater(oldest[1], oldest[0])

    def test_an_undated_chunk_carries_the_floor_or_the_neutral(self):
        layer = _layer()
        ref = {"form": "day", "lo": _D0, "hi": _D0}
        self.assertEqual(arm._match_temporal(layer, ref)[2], arm.SILENT_FLOOR)
        with patch.object(arm, "SILENT", "neutral"):
            self.assertEqual(arm._match_temporal(layer, ref)[2],
                             arm.SILENT_NEUTRAL)

    def test_label_agreement_scores_the_labelled_chunks(self):
        layer = _layer()
        np.testing.assert_array_equal(arm._match_evidence(layer, "number"),
                                      [1.0, 0.0, 0.0, 0.0])
        np.testing.assert_array_equal(arm._match_evidence(layer, "cause"),
                                      [0.0, 1.0, 0.0, 0.0])
        np.testing.assert_array_equal(arm._match_evidence(layer, "quote"),
                                      [0.0, 0.0, 0.0, 1.0])

    def test_the_graded_reading_ranks_by_the_kind_score(self):
        layer = _layer()
        with patch.object(arm, "EVIDENCE_MATCH", "graded"):
            m = arm._match_evidence(layer, "number")
        self.assertEqual(int(np.argmax(m)), 0)

    def test_an_asked_kind_with_no_countable_mark_is_a_constant(self):
        layer = _layer()
        m = arm._match_evidence(layer, "comparison")
        self.assertEqual(len(set(m.tolist())), 1)
        with patch.object(arm, "EVIDENCE_MATCH", "graded"):
            m = arm._match_evidence(layer, "comparison")
        self.assertEqual(len(set(m.tolist())), 1)

    def test_the_topic_match_is_the_description_channel_unchanged(self):
        layer = _layer()
        np.testing.assert_allclose(arm._match_topic(layer, _QVEC),
                                   (layer.desc_emb @ _QVEC + 1.0) / 2.0)


class SilenceRuleTests(unittest.TestCase):

    def _ids(self, layer, extracted, name_vecs=_NO_VECS):
        rows, _ = arm._retrieve(layer, _QVEC, name_vecs, _NO_VECS, extracted, 50)
        return [r["chunkId"] for r in rows]

    def test_an_unasked_question_reorders_nothing(self):
        base = _layer()
        swapped_emb = _TAG_EMB.copy()
        swapped_emb[[0, 1]] = swapped_emb[[1, 0]]
        swapped = _layer(tag_emb=swapped_emb)
        self.assertEqual(self._ids(base, _NOTHING), self._ids(swapped, _NOTHING))

    def test_an_asked_question_does_reorder(self):
        base = _layer(desc_emb=_unit_rows([[0.9, 0.1], [0.88, 0.15],
                                           [-1.0, 0.0], [0.0, -1.0]]))
        asked = {"names": ["X"], "actions": [], "time": None, "kind": None}
        vecs = _unit_rows([[0.2, 0.98]])
        self.assertNotEqual(self._ids(base, _NOTHING),
                            self._ids(base, asked, name_vecs=vecs))

    def test_every_combine_treats_a_constant_question_as_silent(self):
        topic = np.array([0.9, 0.4, 0.7, 0.1])
        for combine in ("additive", "multiplicative", "noisy_or"):
            with patch.object(arm, "COMBINE", combine), \
                 patch.object(arm, "_QWEIGHTS", {q: 0.8 for q in arm.ALL_FACETS}):
                alone = arm._combine({"topic": topic})
                with_constant = arm._combine(
                    {"topic": topic, "temporal": np.full(4, 0.37)})
            np.testing.assert_array_equal(np.argsort(-alone),
                                          np.argsort(-with_constant), combine)

    def test_chunk_side_silence_never_excludes_the_chunk(self):
        layer = _layer()
        asked = {"names": ["X"], "actions": [], "time": None, "kind": None}
        rows, meta = arm._retrieve(layer, _QVEC, _unit_rows([[1.0, 0.0]]),
                                   _NO_VECS, asked, 50)
        self.assertEqual(meta["retrieved"], 4)
        self.assertIn("c3", [r["chunkId"] for r in rows])


class NoGatesTests(unittest.TestCase):

    def test_a_zero_match_never_annihilates_the_other_evidence(self):
        topic = np.array([0.9, 0.4, 0.2])
        entities = np.array([1.0, 0.0, 0.0])
        for combine in ("additive", "multiplicative", "noisy_or"):
            with patch.object(arm, "COMBINE", combine):
                score = arm._combine({"topic": topic, "entities": entities})
            self.assertTrue(np.all(score > 0.0), combine)
            self.assertGreater(score[1], score[2], combine)

    def test_an_all_zero_asked_match_reorders_nothing_under_every_combine(self):
        topic = np.array([0.9, 0.4, 0.7, 0.1])
        for combine in ("additive", "multiplicative", "noisy_or"):
            with patch.object(arm, "COMBINE", combine):
                alone = arm._combine({"topic": topic})
                with_zero = arm._combine({"topic": topic,
                                          "evidence": np.zeros(4)})
            np.testing.assert_array_equal(np.argsort(-alone),
                                          np.argsort(-with_zero), combine)

    def test_comparison_under_label_and_multiplicative_reorders_nothing(self):
        layer = _layer()
        asked = {"names": [], "actions": [], "time": None, "kind": "comparison"}
        with patch.object(arm, "COMBINE", "multiplicative"):
            with_kind, _ = arm._retrieve(layer, _QVEC, _NO_VECS, _NO_VECS,
                                         asked, 50)
            without, _ = arm._retrieve(layer, _QVEC, _NO_VECS, _NO_VECS,
                                       _NOTHING, 50)
        self.assertEqual([r["chunkId"] for r in with_kind],
                         [r["chunkId"] for r in without])

    def test_undated_chunks_survive_an_asked_temporal_under_multiplicative(self):
        layer = _layer()
        asked = {"names": [], "actions": [],
                 "time": {"form": "day", "lo": _D0, "hi": _D0, "text": "x"},
                 "kind": None}
        with patch.object(arm, "COMBINE", "multiplicative"):
            rows, meta = arm._retrieve(layer, _QVEC, _NO_VECS, _NO_VECS,
                                       asked, 50)
        scores = {r["chunkId"]: r["score"] for r in rows}
        self.assertEqual(meta["retrieved"], 4)
        self.assertIn("c2", scores)
        self.assertGreater(scores["c2"], 0.0)

    def test_an_asked_evidence_label_weights_and_never_zeroes(self):
        layer = _layer()
        asked = {"names": [], "actions": [], "time": None, "kind": "number"}
        with patch.object(arm, "COMBINE", "multiplicative"):
            rows, _ = arm._retrieve(layer, _QVEC, _NO_VECS, _NO_VECS, asked, 50)
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(r["score"] > 0.0 for r in rows))


class CombineTests(unittest.TestCase):
    _M = {"topic": np.array([0.9, 0.4]), "entities": np.array([0.2, 0.8])}

    def test_additive_is_the_weighted_sum(self):
        with patch.object(arm, "_QWEIGHTS",
                          {"topic": 2.0, "entities": 0.5, "activity": 1.0,
                           "temporal": 1.0, "evidence": 1.0}):
            np.testing.assert_allclose(
                arm._combine(self._M),
                2.0 * self._M["topic"] + 0.5 * self._M["entities"])

    def test_multiplicative_raises_each_match_to_its_weight(self):
        with patch.object(arm, "COMBINE", "multiplicative"), \
             patch.object(arm, "_QWEIGHTS",
                          {"topic": 2.0, "entities": 0.5, "activity": 1.0,
                           "temporal": 1.0, "evidence": 1.0}):
            np.testing.assert_allclose(
                arm._combine(self._M),
                self._M["topic"] ** 2.0 * self._M["entities"] ** 0.5)

    def test_noisy_or_is_one_minus_the_product_of_misses(self):
        with patch.object(arm, "COMBINE", "noisy_or"), \
             patch.object(arm, "_QWEIGHTS", {q: 0.5 for q in arm.ALL_FACETS}):
            np.testing.assert_allclose(
                arm._combine(self._M),
                1.0 - (1.0 - 0.5 * self._M["topic"])
                    * (1.0 - 0.5 * self._M["entities"]))

    def test_noisy_or_rejects_a_weight_outside_the_unit_interval(self):
        with self.assertRaisesRegex(ValueError, "noisy_or"):
            arm._validate_combine("noisy_or", {"topic": 1.5})

    def test_a_negative_weight_is_rejected_under_every_form(self):
        for combine in ("additive", "multiplicative", "noisy_or"):
            with self.assertRaisesRegex(ValueError, ">= 0"):
                arm._validate_combine(combine, {"topic": -0.1})

    def test_an_unknown_combine_fails_loud(self):
        with self.assertRaisesRegex(ValueError, "HERB_FQ_COMBINE"):
            arm._validate_combine("average", {})


class AnswersCacheTests(unittest.TestCase):
    def test_a_stored_entry_loads_back_exactly(self):
        entry = _CACHE / "roundtrip"
        arm._store_answers(entry, _ROLES, _DAYS, _zprofile(), list(_TAGS),
                           ["c0", "c1", "c2", "c3"], {"n_dated": 3})
        loaded = arm._load_answers(entry)
        np.testing.assert_array_equal(loaded["roles"], _ROLES)
        np.testing.assert_array_equal(loaded["days"], _DAYS)
        np.testing.assert_array_equal(loaded["zprofile"], _zprofile())
        self.assertEqual(loaded["tag"], list(_TAGS))
        self.assertEqual(loaded["chunk_id"], ["c0", "c1", "c2", "c3"])
        self.assertEqual(loaded["features"], list(REGISTER))

    def test_a_partial_entry_is_not_served(self):
        entry = _CACHE / "partial"
        arm._store_answers(entry, _ROLES, _DAYS, _zprofile(), list(_TAGS),
                           ["c0", "c1", "c2", "c3"], {})
        (entry / "manifest.json").unlink()
        self.assertIsNone(arm._load_answers(entry))

    def test_the_role_configuration_names_the_entry(self):
        key = arm._answers_key("d" * 64)
        with patch.object(arm, "ROLE_FIT", "zscored"):
            self.assertNotEqual(arm._answers_key("d" * 64), key)
        with patch.object(arm, "ROLE_SOURCE", "baked"):
            self.assertNotEqual(arm._answers_key("d" * 64), key)

    def test_the_content_names_the_entry(self):
        rows = [_chunk_row("c0")]
        phi = np.full((1, 5), 0.6)
        evidenced = np.ones((1, 5), dtype=bool)
        base = arm._content_digest(phi, evidenced, ["t0"], ["c0"], rows, None)
        self.assertEqual(base, arm._content_digest(phi, evidenced, ["t0"],
                                                   ["c0"], rows, None))
        self.assertNotEqual(base, arm._content_digest(phi + 0.1, evidenced,
                                                      ["t0"], ["c0"], rows, None))
        self.assertNotEqual(base, arm._content_digest(
            phi, evidenced, ["t0"], ["c0"],
            [_chunk_row("c0", locator='{"index": 1}')], None))
        self.assertNotEqual(base, arm._content_digest(
            phi, evidenced, ["t0"], ["c0"], rows,
            (np.ones((1, 5)), np.ones(1, dtype=bool))))

    def test_the_arm_side_shaping_names_the_entry(self):
        rows = [_chunk_row("c0")]
        phi = np.full((1, 5), 0.6)
        evidenced = np.ones((1, 5), dtype=bool)
        base = arm._content_digest(phi, evidenced, ["t0"], ["c0"], rows, None)
        with patch.object(arm, "PHI_NEUTRAL", 0.25):
            self.assertNotEqual(base, arm._content_digest(
                phi, evidenced, ["t0"], ["c0"], rows, None))
        with patch.object(arm, "DIVIDE_FLOOR", 1e-5):
            self.assertNotEqual(base, arm._content_digest(
                phi, evidenced, ["t0"], ["c0"], rows, None))

    def test_the_key_carries_the_content_digest(self):
        self.assertIn(("a" * 64)[:16], arm._answers_key("a" * 64))
        self.assertNotEqual(arm._answers_key("a" * 64),
                            arm._answers_key("b" * 64))

    def test_a_corrupt_manifest_reads_as_a_miss(self):
        entry = _CACHE / "corrupt_manifest"
        arm._store_answers(entry, _ROLES, _DAYS, _zprofile(), list(_TAGS),
                           ["c0", "c1", "c2", "c3"], {})
        (entry / "manifest.json").write_text("{ truncated", encoding="utf-8")
        self.assertIsNone(arm._load_answers(entry))

    def test_a_manifest_missing_its_features_reads_as_a_miss(self):
        entry = _CACHE / "featureless"
        arm._store_answers(entry, _ROLES, _DAYS, _zprofile(), list(_TAGS),
                           ["c0", "c1", "c2", "c3"], {})
        (entry / "manifest.json").write_text("{}", encoding="utf-8")
        self.assertIsNone(arm._load_answers(entry))

    def test_a_corrupt_answers_file_reads_as_a_miss(self):
        entry = _CACHE / "corrupt_npz"
        arm._store_answers(entry, _ROLES, _DAYS, _zprofile(), list(_TAGS),
                           ["c0", "c1", "c2", "c3"], {})
        data = (entry / "answers.npz").read_bytes()
        (entry / "answers.npz").write_bytes(data[:len(data) // 2])
        self.assertIsNone(arm._load_answers(entry))

    def test_a_mismatched_vocabulary_fails_loud(self):
        entry = _CACHE / "mismatch"
        with self.assertRaisesRegex(RuntimeError, "delete"):
            arm._verify_answers(_answers(), ["other"], ["c0"], entry)

    def test_a_mismatched_population_fails_loud(self):
        entry = _CACHE / "mismatch"
        with self.assertRaisesRegex(RuntimeError, "delete"):
            arm._verify_answers(_answers(), list(_TAGS), ["c0"], entry)


class RetrieveTests(unittest.TestCase):
    def test_a_non_positive_k_fails_before_any_work(self):
        with self.assertRaisesRegex(ValueError, "k must be positive"):
            arm._retrieve(_layer(), _QVEC, _NO_VECS, _NO_VECS, _NOTHING, 0)

    def test_the_callers_k_caps_the_depth(self):
        rows, meta = arm._retrieve(_layer(), _QVEC, _NO_VECS, _NO_VECS,
                                   _NOTHING, 2)
        self.assertEqual((len(rows), meta["K"]), (2, 2))

    def test_a_selected_row_carries_the_pointer_the_resolver_reads(self):
        rows, _ = arm._retrieve(_layer(), _QVEC, _NO_VECS, _NO_VECS, _NOTHING, 50)
        self.assertEqual(sorted(rows[0]),
                         ["chunkId", "locator", "relpath", "score", "sha256"])

    def test_an_oracle_chunk_is_never_selected(self):
        layer = _layer(chunk_rows=[
            _chunk_row("c0"), _chunk_row("c1"),
            _chunk_row("c2", section="answerable_questions"), _chunk_row("c3")])
        rows, meta = arm._retrieve(layer, _QVEC, _NO_VECS, _NO_VECS, _NOTHING, 50)
        self.assertNotIn("c2", [r["chunkId"] for r in rows])
        self.assertEqual(meta["population"], 3)

    def test_equal_scores_rank_on_the_chunk_id(self):
        layer = _layer(desc_emb=_unit_rows([[1.0, 0.0], [1.0, 0.0],
                                            [1.0, 0.0], [1.0, 0.0]]))
        rows, _ = arm._retrieve(layer, _QVEC, _NO_VECS, _NO_VECS, _NOTHING, 50)
        ids = [r["chunkId"] for r in rows]
        self.assertEqual(ids, sorted(ids))

    def test_the_meta_records_the_read_and_the_combine(self):
        extracted = {"names": ["TestForce"], "actions": ["approved it"],
                     "time": {"form": "day", "lo": _D0, "hi": _D0, "text": "x"},
                     "kind": "number"}
        vecs = _unit_rows([[1.0, 0.0]])
        _, meta = arm._retrieve(_layer(), _QVEC, vecs, vecs, extracted, 50)
        self.assertEqual(meta["asked"], list(arm.ALL_FACETS))
        self.assertEqual(meta["extracted"]["names"], ["TestForce"])
        self.assertEqual(meta["extracted"]["evidence_kind"], "number")
        self.assertEqual(meta["combine"]["form"], "additive")
        self.assertEqual(sorted(meta["combine"]["weights"]),
                         sorted(arm.ALL_FACETS))

    def test_an_unasked_question_is_absent_from_the_meta(self):
        _, meta = arm._retrieve(_layer(), _QVEC, _NO_VECS, _NO_VECS, _NOTHING, 50)
        self.assertEqual(meta["asked"], ["topic"])
        self.assertEqual(list(meta["combine"]["weights"]), ["topic"])


class ContractTests(unittest.TestCase):
    def test_the_arm_is_selectable_from_the_runner(self):
        self.assertIn("artefact_v1_five_questions", run.ARMS)

    def test_the_manifest_records_the_regime_the_run_carried(self):
        self.assertEqual(sorted(arm.RETRIEVAL_FLAGS), [
            "HERB_FACET_PRIOR", "HERB_FQ_ACTIVITY_AGG", "HERB_FQ_COMBINE",
            "HERB_FQ_ENTITY_AGG", "HERB_FQ_EVIDENCE", "HERB_FQ_ROLE_FIT",
            "HERB_FQ_ROLE_SOURCE", "HERB_FQ_SILENT", "HERB_FQ_TIME_SCALE",
            "HERB_FQ_W_ACTIVITY", "HERB_FQ_W_ENTITIES", "HERB_FQ_W_EVIDENCE",
            "HERB_FQ_W_TEMPORAL", "HERB_FQ_W_TOPIC"])

    def test_no_model_reads_the_query(self):
        self.assertEqual(arm.INTERPRET_MODEL, "deterministic")


if __name__ == "__main__":
    unittest.main()

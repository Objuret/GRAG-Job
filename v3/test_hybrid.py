"""Regression checks for the hybrid arm — min-max late fusion of the lucene and
vector rankings.

The fusion math (`_minmax`, `fuse`) is exercised directly on ranked (id, score)
lists. The contract path (`prepare_over_corpus`, `answer_one_question`) is exercised
with the two baseline arms stubbed on the `pipelines` package, so no BM25 or dense
index is built and the suite runs without either arm's runtime dependencies.
"""
import os
import types
import unittest
from unittest.mock import patch

import pipelines
from contract import BuildStats, ModelUsage
from pipelines import hybrid as arm


class MinMaxTests(unittest.TestCase):
    def test_min_max_spans_zero_to_one(self):
        out = arm._minmax({"a": 2.0, "b": 4.0, "c": 6.0})
        self.assertEqual((out["a"], out["c"]), (0.0, 1.0))
        self.assertAlmostEqual(out["b"], 0.5)

    def test_a_single_scale_point_maps_every_id_to_one(self):
        self.assertEqual(arm._minmax({"a": 3.0, "b": 3.0}), {"a": 1.0, "b": 1.0})

    def test_an_empty_pool_normalizes_to_nothing(self):
        self.assertEqual(arm._minmax({}), {})


class FuseTests(unittest.TestCase):
    _LUCENE = [("a", 3.0), ("b", 2.0), ("c", 1.0)]
    _VECTOR = [("a", 0.1), ("b", 0.9), ("c", 0.5)]  # a different order over the same ids

    def test_alpha_zero_reduces_to_the_lucene_order(self):
        self.assertEqual(arm.fuse(self._LUCENE, self._VECTOR, 0.0, 3), ["a", "b", "c"])

    def test_alpha_one_reduces_to_the_vector_order(self):
        self.assertEqual(arm.fuse(self._LUCENE, self._VECTOR, 1.0, 3), ["b", "c", "a"])

    def test_the_union_keeps_an_id_present_in_one_arm_only(self):
        # a only in lucene, b only in vector; each single-point pool maps to 1.0, so
        # at 0.5 both fuse to 0.5 and the id tiebreak orders them.
        self.assertEqual(arm.fuse([("a", 2.0)], [("b", 1.0)], 0.5, 5), ["a", "b"])

    def test_alpha_zero_excludes_vector_only_ids(self):
        # the vector arm carries zero weight, so its ids are never candidates: the
        # vector-only `a` cannot displace the genuine lucene hit `z`.
        self.assertEqual(arm.fuse([("m", 3.0), ("z", 1.0)], [("a", 0.9)], 0.0, 2),
                         ["m", "z"])

    def test_alpha_one_excludes_lucene_only_ids(self):
        self.assertEqual(arm.fuse([("a", 0.9)], [("m", 3.0), ("z", 1.0)], 1.0, 2),
                         ["m", "z"])

    def test_alpha_zero_with_empty_lucene_retrieves_nothing(self):
        # a lexically-empty query returns no lucene hits; the zero-weight vector arm
        # injects nothing, so the fusion is empty (not k id-sorted rows).
        self.assertEqual(arm.fuse([], [("x", 0.9), ("y", 0.5), ("z", 0.1)], 0.0, 2), [])

    def test_alpha_one_with_empty_vector_retrieves_nothing(self):
        self.assertEqual(arm.fuse([("x", 0.9), ("y", 0.5), ("z", 0.1)], [], 1.0, 2), [])

    def test_both_arms_empty_retrieves_nothing(self):
        self.assertEqual(arm.fuse([], [], 0.5, 5), [])

    def test_a_weighted_arm_short_of_k_is_not_padded_by_the_other(self):
        # lucene returns two hits under k=4 at alpha 0: no zero-tier padding from the
        # zero-weight vector arm.
        self.assertEqual(
            arm.fuse([("m", 3.0), ("z", 1.0)], [("a", 0.9), ("b", 0.5)], 0.0, 4),
            ["m", "z"])

    def test_ties_break_on_the_id_not_the_input_order(self):
        # both lucene ids share a score -> min-max maps both to 1.0; at alpha 0 they
        # fuse equal, and the id order wins over the ["b", "a"] input order.
        self.assertEqual(arm.fuse([("b", 5.0), ("a", 5.0)], [], 0.0, 2), ["a", "b"])

    def test_top_k_truncates_the_fused_union(self):
        out = arm.fuse([("a", 3.0), ("b", 2.0)], [("c", 1.0), ("d", 0.5)], 0.5, 2)
        self.assertEqual(len(out), 2)


class RetrievalFlagTests(unittest.TestCase):
    def test_retrieval_flags_carry_the_fusion_weight(self):
        self.assertEqual(arm.RETRIEVAL_FLAGS, {"HERB_HYBRID_ALPHA": arm.ALPHA})

    def test_alpha_defaults_to_a_half(self):
        self.assertEqual(arm._env_float("HERB_HYBRID_ALPHA_UNSET_XYZ", 0.5), 0.5)

    def test_a_non_numeric_alpha_fails_loud(self):
        with patch.dict(os.environ, {"HERB_HYBRID_ALPHA_BAD": "abc"}):
            with self.assertRaises(ValueError):
                arm._env_float("HERB_HYBRID_ALPHA_BAD", 0.5)


def _fake_lucene(ranked):
    """A lucene stand-in: prepare hands back a Prepared-ish with a BuildStats;
    retrieve returns ranked unit dicts (a bare list, as the real lucene arm does)."""
    units = [{"id": i, "text": f"L:{i}", "score": s, "rank": r}
             for r, (i, s) in enumerate(ranked)]
    return types.SimpleNamespace(
        METADATA_ON=False,
        prepare_over_corpus=lambda corpus: types.SimpleNamespace(
            build_stats=BuildStats(0.2, ModelUsage(time_s=0.1), [])),
        retrieve_top_k_units=lambda q, prep, k: units[:k])


def _fake_vector(ranked, usage=None):
    """A vector stand-in: retrieve returns (ranked unit dicts, ModelUsage), the pair
    the real vector arm returns; prepare's BuildStats carries an embedder cost."""
    units = [{"id": i, "text": f"V:{i}", "score": s, "rank": r}
             for r, (i, s) in enumerate(ranked)]
    used = usage or ModelUsage()
    return types.SimpleNamespace(
        METADATA_ON=False,
        prepare_over_corpus=lambda corpus: types.SimpleNamespace(
            build_stats=BuildStats(0.3, ModelUsage(calls=1, tokens_in=5, tokens_out=2,
                                                   time_s=0.5), ["embed-model"])),
        retrieve_top_k_units=lambda q, prep, k: (units[:k], used))


class PrepareStatsTests(unittest.TestCase):
    def test_build_stats_sum_both_arms(self):
        with patch.object(pipelines, "lucene", _fake_lucene([]), create=True), \
             patch.object(pipelines, "vector", _fake_vector([]), create=True):
            prepared = arm.prepare_over_corpus("corpus/")
        bs = prepared.build_stats
        self.assertAlmostEqual(bs.build_time_s, 0.5)          # 0.2 + 0.3
        self.assertAlmostEqual(bs.model.time_s, 0.6)          # 0.1 + 0.5
        self.assertEqual((bs.model.calls, bs.model.tokens_in, bs.model.tokens_out),
                         (1, 5, 2))
        self.assertEqual(bs.models, ["embed-model"])          # lucene: none, vector: one
        self.assertAlmostEqual(prepared.lucene.build_stats.build_time_s, 0.2)
        self.assertAlmostEqual(prepared.vector.build_stats.build_time_s, 0.3)


class AnswerContractTests(unittest.TestCase):
    def _run(self, lucene_ranked, vector_ranked, alpha, k, generate=None, vec_usage=None):
        prepared = arm.Prepared(lucene=object(), vector=object())
        with patch.object(pipelines, "lucene", _fake_lucene(lucene_ranked), create=True), \
             patch.object(pipelines, "vector", _fake_vector(vector_ranked, vec_usage),
                          create=True), \
             patch.object(arm, "ALPHA", alpha):
            return arm.answer_one_question(("q::a::0", "text?"), prepared, generate, k)

    def test_answer_builds_the_contract_from_the_fused_ids(self):
        out = self._run([("a", 3.0), ("b", 2.0)], [("a", 0.9), ("c", 0.5)], 0.5, 3)
        self.assertEqual(
            out.context_ids,
            arm.fuse([("a", 3.0), ("b", 2.0)], [("a", 0.9), ("c", 0.5)], 0.5, 3))
        # contexts align 1:1 with the fused ids; a shared id takes the vector text.
        text_by_id = dict(zip(out.context_ids, out.contexts))
        self.assertEqual(text_by_id["a"], "V:a")   # in both -> vector wins
        self.assertEqual(text_by_id["b"], "L:b")   # lucene-only
        self.assertEqual(text_by_id["c"], "V:c")   # vector-only
        self.assertEqual(out.answer, "")
        self.assertEqual(out.generator, ModelUsage())

    def test_the_shared_generator_answer_and_usage_pass_through(self):
        def gen(text, contexts):
            self.assertEqual(text, "text?")  # the arm hands the generator only the text
            return "the answer", {"calls": 1, "tokens_in": 11, "tokens_out": 7, "time": 0.0}

        out = self._run([("a", 1.0)], [("a", 0.5)], 0.5, 1, generate=gen)
        self.assertEqual(out.answer, "the answer")
        self.assertEqual((out.generator.calls, out.generator.tokens_in, out.generator.tokens_out),
                         (1, 11, 7))

    def test_retrieval_usage_is_forwarded_from_the_vector_arm(self):
        out = self._run([("a", 1.0)], [("a", 0.5)], 0.5, 1,
                        vec_usage=ModelUsage(calls=2, tokens_in=9))
        self.assertEqual((out.retrieval.calls, out.retrieval.tokens_in), (2, 9))
        self.assertGreaterEqual(out.search_time_s, 0.0)

    def test_alpha_one_end_to_end_ranks_on_the_vector_arm(self):
        out = self._run([("a", 3.0), ("b", 2.0), ("c", 1.0)],
                        [("a", 0.1), ("b", 0.9), ("c", 0.5)], 1.0, 3)
        self.assertEqual(out.context_ids, ["b", "c", "a"])

    def test_alpha_zero_end_to_end_ranks_on_the_lucene_arm(self):
        out = self._run([("a", 3.0), ("b", 2.0), ("c", 1.0)],
                        [("a", 0.1), ("b", 0.9), ("c", 0.5)], 0.0, 3)
        self.assertEqual(out.context_ids, ["a", "b", "c"])


if __name__ == "__main__":
    unittest.main()

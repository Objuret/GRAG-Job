"""Regression checks for the multi-step relevance weight arm."""
import math
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

import run
from pipelines import artefact_v1_relevance_weight as arm

# The suite exercises the read regime regardless of the shell's HERB_* toggles,
# and builds its tag geometry in a cache of its own.
_CACHE = Path(tempfile.mkdtemp(prefix="tag_distance_"))
_MODULE_FLAGS = (patch.object(arm, "DEMAND", "read"),
                 patch.object(arm, "TAG_DISTANCE_CACHE_DIR", _CACHE))


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
           "product": None, "channel": None, "employee_id": None, "years": None}
    row.update(fields)
    return row


_MANIFEST = {"icc_topic_vote": 0.6, "icc_temporal": 0.2}

# Two tag families around [1, 0] and [0, 1], plus one tag facing away. The
# names split 2/4 under sha256 parity, so both split-half halves can rank.
_TAG_EMB = _unit_rows([[1.0, 0.0], [0.98, 0.2], [0.95, 0.3],
                       [0.0, 1.0], [0.1, 0.99], [-1.0, 0.0]])
_EDGE_TAG = ["tag0", "tag1", "tag2", "tag3", "tag4", "tag5"]
_EDGE_CHUNK = ["c0", "c0", "c1", "c1", "c2", "c2"]

# Edge 0 sits exactly at the calibrated scale's neutral point, so the centred
# layer puts it at zero on every facet.
_OTHERS = np.array([[0.9, 0.1, 0.5, 0.4, 0.7],
                    [0.2, 0.8, 0.6, 0.5, 0.3],
                    [0.4, 0.3, 0.9, 0.2, 0.6],
                    [0.7, 0.6, 0.2, 0.8, 0.1],
                    [0.3, 0.2, 0.3, 0.6, 0.8]])
_PHI = np.vstack([np.full(5, 0.5), _OTHERS])


def _layer(chunk_rows=None, products=(), manifest=None, evidenced=None):
    rows = chunk_rows or [_chunk_row("c0"), _chunk_row("c1"), _chunk_row("c2"),
                          _chunk_row("c3")]
    desc = _unit_rows([[1.0, 0.0], [0.0, 1.0], [-1.0, 0.0], [0.0, -1.0]])[:len(rows)]
    if evidenced is None:
        evidenced = np.ones(_PHI.shape, dtype=bool)
    return arm._build_layer(rows, list(products), sorted(set(_EDGE_TAG)), _TAG_EMB,
                            desc, _EDGE_TAG, _EDGE_CHUNK, _PHI, evidenced,
                            manifest or _MANIFEST)


_QVEC = np.array([1.0, 0.0], dtype=np.float32)


def _vocabulary(seed, n=8, dim=4):
    """A vocabulary of its own: the same names at its own vectors, so each test
    digests to its own cache entry."""
    rng = np.random.default_rng(seed)
    emb = rng.standard_normal((n, dim)).astype(np.float32)
    return ([f"t{i}" for i in range(n)],
            emb / np.linalg.norm(emb, axis=1, keepdims=True))


def _computed(tag_emb, region=None):
    """The tag-to-tag geometry the walk computed from the vectors themselves."""
    u = tag_emb.astype(np.float64)
    if region is not None:
        u = u[region]
    base = 1.0 - np.clip(u @ u.T, -1.0, 1.0)
    np.fill_diagonal(base, 0.0)
    return base


class LayerBuildTests(unittest.TestCase):
    def test_the_facet_weights_are_centred_on_the_neutral_point(self):
        layer = _layer()
        np.testing.assert_allclose(layer.phi_centred, _PHI - arm.PHI_NEUTRAL)

    def test_an_edge_at_the_neutral_point_carries_exactly_zero(self):
        layer = _layer()
        np.testing.assert_array_equal(layer.phi_centred[0],
                                      np.zeros(len(arm.ALL_FACETS)))

    def test_an_unevidenced_cell_is_exactly_zero(self):
        evidenced = np.ones(_PHI.shape, dtype=bool)
        evidenced[3, 3] = False
        layer = _layer(evidenced=evidenced)
        self.assertNotEqual(float(_PHI[3, 3]), arm.PHI_NEUTRAL)
        self.assertEqual(float(layer.phi_centred[3, 3]), 0.0)
        np.testing.assert_allclose(layer.phi_centred[3, :3], _PHI[3, :3] - 0.5)

    def test_silence_dilutes_the_tags_facet_character(self):
        # identical evidenced profile; tag 0 speaks on 10/10 edges, tag 1 on 1/10
        profile = np.full(5, 0.8)
        evidenced = np.ones((20, 5), dtype=bool)
        evidenced[11:] = False
        centred = np.where(evidenced,
                           np.tile(profile, (20, 1)) - arm.PHI_NEUTRAL, 0.0)
        rows = np.array([0] * 10 + [1] * 10)
        marginal, _, _ = arm._marginals(centred, rows, 2)
        np.testing.assert_allclose(marginal[0], profile - arm.PHI_NEUTRAL)
        np.testing.assert_allclose(marginal[1], marginal[0] / 10.0)

    def test_the_reliability_combines_the_build_icc_with_the_query_side(self):
        qrho = np.array([0.5, 0.4, 0.3, 0.2, 0.1])
        expected = [0.6 * 0.5, 0.4, 0.3, 0.2 * 0.2, 0.1]
        np.testing.assert_allclose(arm._facet_reliability(_MANIFEST, qrho),
                                   expected)

    def test_the_layer_reliability_is_the_build_icc_times_the_query_side(self):
        layer = _layer()
        qrho = arm._query_reliability(sorted(set(_EDGE_TAG)), layer.tag_emb,
                                      layer.marginal, layer.marginal_mean,
                                      layer.marginal_sd, layer.desc_emb)
        np.testing.assert_allclose(layer.reliability,
                                   arm._facet_reliability(_MANIFEST, qrho))

    def test_the_oracle_sections_and_empty_chunks_are_outside_the_population(self):
        layer = _layer(chunk_rows=[
            _chunk_row("c0"),
            _chunk_row("c1", section="answerable_questions"),
            _chunk_row("c2", empty=True),
            _chunk_row("c3")])
        self.assertEqual(layer.retrievable.tolist(), [True, False, False, True])

    def test_a_chunk_the_layer_knows_and_the_graph_does_not_fails_loud(self):
        with self.assertRaisesRegex(RuntimeError, "rebuild the layer"):
            _layer(chunk_rows=[_chunk_row("c0"), _chunk_row("c1")])


class TagGeometryTests(unittest.TestCase):
    def test_the_entry_holds_the_whole_vocabularys_cosine_distance(self):
        tags, emb = _vocabulary(1)
        table = np.array(arm._tag_distance_table(tags, emb))
        np.fill_diagonal(table, 0.0)
        np.testing.assert_array_equal(table, _computed(emb))

    @staticmethod
    def _recorded_builds():
        """Every write-mode open of an entry -> (the record, the recording),
        which is what tells a build from a read: both open the same file."""
        builds = []
        opened = np.lib.format.open_memmap

        def _record(*args, **kwargs):
            if kwargs.get("mode") == "w+":
                builds.append(args[0])
            return opened(*args, **kwargs)

        return builds, patch.object(np.lib.format, "open_memmap", _record)

    def test_a_complete_entry_is_reused(self):
        tags, emb = _vocabulary(2)
        built = np.array(arm._tag_distance_table(tags, emb))
        builds, recording = self._recorded_builds()
        with recording:
            reused = np.array(arm._tag_distance_table(tags, emb))
        self.assertEqual(builds, [])
        np.testing.assert_array_equal(reused, built)

    def test_a_partial_entry_is_rebuilt_rather_than_trusted(self):
        tags, emb = _vocabulary(3)
        arm._tag_distance_table(tags, emb)
        entry = _CACHE / arm._tag_distance_key(tags, emb)
        (entry / "manifest.json").unlink()
        builds, recording = self._recorded_builds()
        with recording:
            table = np.array(arm._tag_distance_table(tags, emb))
        self.assertEqual(len(builds), 1)
        self.assertTrue((entry / "manifest.json").is_file())
        np.fill_diagonal(table, 0.0)
        np.testing.assert_array_equal(table, _computed(emb))

    def test_a_changed_vocabulary_lands_in_a_sibling_entry(self):
        tags, emb = _vocabulary(4)
        _, other = _vocabulary(5)
        self.assertNotEqual(arm._tag_distance_key(tags, emb),
                            arm._tag_distance_key(tags, other))
        self.assertNotEqual(arm._tag_distance_key(tags, emb),
                            arm._tag_distance_key([t.upper() for t in tags], emb))

    def test_the_sliced_geometry_is_the_computed_one(self):
        tags, emb = _vocabulary(6, n=40, dim=16)
        table = arm._tag_distance_table(tags, emb)
        region = np.array([0, 3, 4, 9, 17, 23, 31, 38])
        sliced = np.array(table[np.ix_(region, region)])
        np.fill_diagonal(sliced, 0.0)
        np.testing.assert_array_equal(sliced, _computed(emb, region))

    def test_the_walk_over_the_table_is_the_walk_over_the_vectors(self):
        layer = _layer()
        support, order = arm._affinity(layer, _QVEC)
        demand = arm._demand(layer, support)
        edge_weight = arm._edge_weight(layer, demand)
        sliced = arm._walk(layer, support, edge_weight, demand, order)
        with patch.object(layer, "tag_distance", _computed(layer.tag_emb)):
            computed = arm._walk(layer, support, edge_weight, demand, order)
        self.assertEqual(sliced, computed)


class QueryReliabilityTests(unittest.TestCase):
    def _qrho(self, layer):
        return arm._query_reliability(sorted(set(_EDGE_TAG)), layer.tag_emb,
                                      layer.marginal, layer.marginal_mean,
                                      layer.marginal_sd, layer.desc_emb)

    def test_the_measurement_is_five_values_inside_the_reliability_scale(self):
        qrho = self._qrho(_layer())
        self.assertEqual(qrho.shape, (len(arm.ALL_FACETS),))
        self.assertTrue(np.all(qrho >= 0.0))
        self.assertTrue(np.all(qrho <= arm.ICC_CEIL))

    def test_the_measurement_is_deterministic(self):
        layer = _layer()
        np.testing.assert_array_equal(self._qrho(layer), self._qrho(layer))

    def test_a_half_too_small_to_rank_fails_loud(self):
        emb = _unit_rows([[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]])
        with self.assertRaisesRegex(RuntimeError, "too few"):
            arm._query_reliability(["t0", "t1", "t2"], emb, np.zeros((3, 5)),
                                   np.zeros(5), np.ones(5), emb)


class AffinityTests(unittest.TestCase):
    def test_support_is_the_inverse_square_distance_over_the_log_rank(self):
        layer = _layer()
        support, order = arm._affinity(layer, _QVEC)
        cos = (layer.tag_emb @ _QVEC).astype(np.float64)
        for rank, tag in enumerate(order, start=1):
            dist = max(1.0 - cos[tag], arm.DIVIDE_FLOOR)
            self.assertAlmostEqual(support[tag],
                                   math.log(len(cos) / rank) / dist ** 2, places=9)

    def test_a_tag_on_top_of_the_query_is_floored_not_divided_by_zero(self):
        layer = _layer()
        support, order = arm._affinity(layer, _QVEC)
        top = int(order[0])
        self.assertEqual(float(layer.tag_emb[top] @ _QVEC), 1.0)
        self.assertTrue(np.isfinite(support[top]))

    def test_support_falls_with_rank_and_the_last_tag_carries_none(self):
        layer = _layer()
        support, order = arm._affinity(layer, _QVEC)
        ranked = support[order]
        self.assertTrue(np.all(np.diff(ranked) < 0.0))
        self.assertEqual(ranked[-1], 0.0)

    def test_the_whole_vocabulary_carries_weight(self):
        layer = _layer()
        support, _ = arm._affinity(layer, _QVEC)
        self.assertEqual(len(support), len(layer.tags))
        self.assertTrue(np.all(support >= 0.0))


class RegionTests(unittest.TestCase):
    def test_the_region_is_the_prefix_carrying_at_least_the_uniform_share(self):
        support = np.array([5.0, 3.0, 1.0, 0.5, 0.3, 0.2])  # share = 10/6
        region = arm._region(support, np.arange(6))
        np.testing.assert_array_equal(region, [0, 1])

    def test_a_flat_support_activates_the_whole_vocabulary(self):
        region = arm._region(np.ones(6), np.arange(6))
        np.testing.assert_array_equal(region, np.arange(6))


class DemandTests(unittest.TestCase):
    def test_the_flat_control_weights_the_five_facets_equally(self):
        layer = _layer()
        support, _ = arm._affinity(layer, _QVEC)
        with patch.object(arm, "DEMAND", "flat"):
            demand = arm._demand(layer, support)
        np.testing.assert_allclose(demand, np.full(5, 0.2))

    def test_the_read_demand_is_a_weighting_of_the_five(self):
        layer = _layer()
        support, _ = arm._affinity(layer, _QVEC)
        demand = arm._demand(layer, support)
        self.assertAlmostEqual(float(demand.sum()), 1.0)
        self.assertTrue(np.all(demand > 0.0))

    def test_zero_reliability_lands_the_demand_at_uniform(self):
        layer = _layer()
        layer.reliability = np.zeros(5)
        support, _ = arm._affinity(layer, _QVEC)
        np.testing.assert_allclose(arm._demand(layer, support), np.full(5, 0.2))

    def test_the_facet_the_neighbourhood_is_most_unusual_in_leads(self):
        layer = _layer()
        layer.reliability = np.ones(5)
        support, _ = arm._affinity(layer, _QVEC)
        weight = support / support.sum()
        scaled = (weight @ (layer.marginal - layer.marginal_mean)) / layer.marginal_sd
        self.assertEqual(int(np.argmax(arm._demand(layer, support))),
                         int(np.argmax(scaled)))

    def test_shrinkage_pulls_an_unreliable_facet_toward_uniform(self):
        layer = _layer()
        support, _ = arm._affinity(layer, _QVEC)
        layer.reliability = np.ones(5)
        full = arm._demand(layer, support)
        layer.reliability = np.array([1.0, 1.0, 1.0, 0.1, 1.0])
        shrunk = arm._demand(layer, support)
        at = arm.ALL_FACETS.index("temporal")
        self.assertLess(abs(shrunk[at] - 0.2), abs(full[at] - 0.2))


class CentredDemandTests(unittest.TestCase):
    def _centred(self):
        with patch.object(arm, "DEMAND", "centred"):
            layer = _layer()
            support, _ = arm._affinity(layer, _QVEC)
            return layer, support, arm._demand(layer, support)

    def test_the_read_regime_measures_no_expectation(self):
        self.assertIsNone(_layer().expected_demand)

    def test_the_expectation_is_the_read_averaged_over_the_probe_bank(self):
        layer, _, _ = self._centred()
        reads = [arm._demand_read(layer.marginal, layer.marginal_mean,
                                  layer.marginal_sd, layer.reliability,
                                  arm._affinity(layer, probe)[0])
                 for probe in layer.desc_emb]
        np.testing.assert_allclose(layer.expected_demand, np.mean(reads, axis=0))

    def test_the_centred_demand_is_the_read_less_the_expectation(self):
        layer, support, demand = self._centred()
        read = arm._demand_read(layer.marginal, layer.marginal_mean,
                                layer.marginal_sd, layer.reliability, support)
        np.testing.assert_allclose(demand, read - layer.expected_demand)

    def test_the_centred_demand_sums_to_zero_and_can_subtract(self):
        _, _, demand = self._centred()
        self.assertAlmostEqual(float(demand.sum()), 0.0)
        self.assertLess(float(demand.min()), 0.0)

    def test_the_arm_retrieves_under_the_centred_demand(self):
        with patch.object(arm, "DEMAND", "centred"):
            rows, meta = arm._retrieve(_layer(), _QVEC, "q", 50)
        self.assertEqual(len(rows), meta["K"])
        self.assertEqual(len(meta["areas"]), len(arm.ALL_FACETS))
        self.assertAlmostEqual(sum(meta["demand"].values()), 0.0)

    def test_a_facet_the_prompt_wants_less_than_the_corpus_subtracts(self):
        layer, support, demand = self._centred()
        weight = arm._edge_weight(layer, demand)
        below = int(np.argmin(demand))
        self.assertLess(float(demand[below]), 0.0)
        self.assertTrue(np.any(layer.phi_centred[:, below] > 0.0))
        without = arm._edge_weight(
            layer, np.where(np.arange(len(demand)) == below, 0.0, demand))
        self.assertTrue(np.any(weight < without))


class OneOperationTests(unittest.TestCase):
    def _value(self, layer, support, demand):
        """The same sum written out edge by edge."""
        out = np.zeros(len(layer.chunk_ids))
        for e in range(len(layer.rows)):
            out[layer.cols[e]] += (support[layer.rows[e]] *
                                   float(layer.phi_centred[e] @ demand))
        return out

    def test_the_value_is_the_affinity_against_the_demand_at_every_edge(self):
        layer = _layer()
        support, _ = arm._affinity(layer, _QVEC)
        demand = arm._demand(layer, support)
        value = arm._chunk_value(layer, support, arm._edge_weight(layer, demand))
        np.testing.assert_allclose(value, self._value(layer, support, demand))

    def test_every_chunk_in_the_population_receives_a_value(self):
        layer = _layer()
        support, _ = arm._affinity(layer, _QVEC)
        value = arm._chunk_value(layer, support,
                                 arm._edge_weight(layer, np.full(5, 0.2)))
        self.assertEqual(len(value), len(layer.chunk_ids))
        self.assertEqual(value[layer.chunk_ids.index("c3")], 0.0)  # no edge touches it

    def test_a_facet_the_demand_ignores_drops_out_arithmetically(self):
        layer = _layer()
        support, _ = arm._affinity(layer, _QVEC)
        demand = np.array([0.5, 0.0, 0.25, 0.25, 0.0])
        full = arm._chunk_value(layer, support, arm._edge_weight(layer, demand))
        kept = [0, 2, 3]
        partial = np.zeros(len(layer.rows))
        for f in kept:
            partial += layer.phi_centred[:, f] * demand[f]
        np.testing.assert_allclose(full, arm._chunk_value(layer, support, partial))

    def test_an_edge_at_the_neutral_point_moves_its_chunk_by_nothing(self):
        layer = _layer()
        support, _ = arm._affinity(layer, _QVEC)
        demand = arm._demand(layer, support)
        weight = arm._edge_weight(layer, demand)
        self.assertEqual(float(weight[0]), 0.0)

    def test_an_edge_with_no_evidence_contributes_exactly_nothing(self):
        evidenced = np.ones(_PHI.shape, dtype=bool)
        evidenced[1] = False
        layer = _layer(evidenced=evidenced)
        support, _ = arm._affinity(layer, _QVEC)
        weight = arm._edge_weight(layer, arm._demand(layer, support))
        np.testing.assert_array_equal(layer.phi_centred[1], np.zeros(5))
        self.assertEqual(float(weight[1]), 0.0)
        value = arm._chunk_value(layer, support, weight)
        self.assertEqual(float(value[layer.chunk_ids.index("c0")]),
                         float(support[0] * weight[0]))


class AreaTests(unittest.TestCase):
    def _families(self):
        # two families of three, each internally equidistant and far from the
        # other, so the fit a cut is scored on is the family and not one pair
        emb = _unit_rows([[1.0, 0.05, 0.0], [1.0, -0.025, 0.0433],
                          [1.0, -0.025, -0.0433],
                          [0.05, 1.0, 0.0], [-0.025, 1.0, 0.0433],
                          [-0.025, 1.0, -0.0433]])
        dist = 1.0 - np.clip(emb @ emb.T, -1.0, 1.0)
        np.fill_diagonal(dist, 0.0)
        return dist

    def test_the_chain_widens_through_the_anchors_own_family_first(self):
        levels = arm._area_levels(self._families(), anchor=0)
        self.assertEqual(levels[0], (0.0, [0]))
        crossed = set()
        for _, added in levels[1:]:
            if set(added) & {3, 4, 5}:
                self.assertEqual(crossed, {1, 2})
            crossed |= set(added)
        self.assertEqual(crossed, {1, 2, 3, 4, 5})
        heights = [h for h, _ in levels]
        self.assertEqual(heights, sorted(heights))

    def test_a_single_tag_region_is_one_level(self):
        self.assertEqual(arm._area_levels(np.zeros((1, 1)), 0), [(0.0, [0])])

    def test_the_best_fit_cuts_at_the_anchors_own_family(self):
        dist = self._families()
        levels = arm._area_levels(dist, anchor=0)
        cut = arm._best_fit(dist, levels)
        inside = {i for level in levels[:cut + 1] for i in level[1]}
        self.assertEqual(inside, {0, 1, 2})

    def test_a_facet_the_tags_differ_in_pushes_them_apart(self):
        base = np.array([[0.0, 0.4], [0.4, 0.0]])
        same = arm._facet_distances(base, np.array([0.5, 0.5]), 1.0)
        apart = arm._facet_distances(base, np.array([0.1, 0.9]), 1.0)
        self.assertEqual(same[0, 1], 0.4)
        self.assertAlmostEqual(apart[0, 1], 0.4 * 1.8)

    def test_the_stretch_reads_the_difference_in_the_facets_own_spread(self):
        base = np.array([[0.0, 0.4], [0.4, 0.0]])
        wide = arm._facet_distances(base, np.array([0.1, 0.9]), 2.0)
        narrow = arm._facet_distances(base, np.array([0.1, 0.9]), 0.5)
        self.assertAlmostEqual(wide[0, 1], 0.4 * 1.4)
        self.assertAlmostEqual(narrow[0, 1], 0.4 * 2.6)

    def test_each_facet_shapes_the_same_region_differently(self):
        layer = _layer()
        region = np.arange(len(layer.tags))
        emb = layer.tag_emb.astype(np.float64)
        base = 1.0 - np.clip(emb @ emb.T, -1.0, 1.0)
        np.fill_diagonal(base, 0.0)
        shapes = [arm._facet_distances(base, layer.marginal[region, fi],
                                       float(layer.marginal_sd[fi]))
                  for fi in range(len(arm.ALL_FACETS))]
        for fi in range(len(shapes)):
            for fj in range(fi + 1, len(shapes)):
                self.assertFalse(np.allclose(shapes[fi], shapes[fj]),
                                 f"facets {fi} and {fj} cluster identically")


class AreaOpeningTests(unittest.TestCase):
    _LEVELS = [(0.0, [0]), (0.1, [1]), (0.2, [2]), (0.3, [3])]

    def test_an_area_that_clears_the_standard_does_not_widen(self):
        opened, hit, level = arm._open_area(self._LEVELS, 1, 0.5,
                                            lambda o: 1.0 * len(o))
        self.assertEqual((opened, hit, level), ([0, 1], 2.0, 1))

    def test_a_weak_area_widens_until_it_clears_the_standard(self):
        opened, hit, level = arm._open_area(self._LEVELS, 0, 3.0,
                                            lambda o: 1.0 * len(o))
        self.assertEqual((opened, hit, level), ([0, 1, 2], 3.0, 2))

    def test_a_level_that_does_not_improve_the_hit_is_still_opened(self):
        levels = [(0.0, [0]), (0.1, [1]), (0.2, [2])]
        hits = {(0,): 5.0, (0, 1): 4.8, (0, 1, 2): 9.0}
        opened, hit, level = arm._open_area(levels, 0, 8.0,
                                            lambda o: hits[tuple(o)])
        self.assertEqual((opened, hit, level), ([0, 1, 2], 9.0, 2))

    def test_widening_stops_at_the_end_of_the_chain(self):
        opened, _, level = arm._open_area(self._LEVELS, 0, 99.0,
                                          lambda o: 1.0 * len(o))
        self.assertEqual((opened, level), ([0, 1, 2, 3], 3))

    def test_a_chain_that_never_clears_banks_the_hit_of_everything_opened(self):
        opened, hit, level = arm._open_area(self._LEVELS, 0, 99.0,
                                            lambda o: 1.0 / len(o))
        self.assertEqual((opened, hit, level), ([0, 1, 2, 3], 0.25, 3))

    def test_the_first_area_stops_at_its_best_fit_whatever_its_hit(self):
        opened, hit, level = arm._open_area(self._LEVELS, 1, None,
                                            lambda o: -5.0)
        self.assertEqual((opened, hit, level), ([0, 1], -5.0, 1))

    def test_the_standard_starts_from_the_first_areas_banked_hit(self):
        layer = _layer()
        support = np.ones(len(layer.tags))
        demand = np.array([0.9, 0.025, 0.025, 0.025, 0.025])
        _, log = arm._walk(layer, support, arm._edge_weight(layer, demand),
                           demand, np.arange(len(layer.tags)))
        self.assertEqual(log[0]["facet"], arm.ALL_FACETS[0])
        self.assertEqual(log[0]["levels"], log[0]["best_fit"] + 1)
        self.assertEqual(log[0]["standard"], log[0]["hit"])

    def test_the_areas_open_in_the_order_the_prompt_ranks_them(self):
        layer = _layer()
        support = np.ones(len(layer.tags))
        demand = np.array([0.1, 0.3, 0.2, 0.35, 0.05])
        _, log = arm._walk(layer, support, arm._edge_weight(layer, demand),
                           demand, np.arange(len(layer.tags)))
        want = [arm.ALL_FACETS[i] for i in np.argsort(-demand, kind="stable")]
        self.assertEqual([e["facet"] for e in log], want)


class GuideTests(unittest.TestCase):
    _ALL = np.ones(4, dtype=bool)

    def test_a_guide_is_zero_below_its_own_median(self):
        fit = arm._fit(np.array([1.0, 2.0, 3.0, 4.0]), self._ALL)
        self.assertEqual(fit[0], 0.0)
        self.assertEqual(fit[1], 0.0)
        self.assertGreater(fit[2], 0.0)
        self.assertGreater(fit[3], fit[2])

    def test_a_guide_that_says_the_same_of_everything_is_inert(self):
        np.testing.assert_allclose(arm._fit(np.zeros(4), self._ALL), np.zeros(4))

    def test_a_guide_at_zero_leaves_the_value_exactly_as_it_was(self):
        base = np.array([0.1, 0.5, 0.9, 0.0])
        np.testing.assert_allclose(arm._promote(base, np.zeros(4)), base)

    def test_guides_promote_and_never_demote(self):
        base = np.array([0.1, 0.5, 0.9, 0.0])
        promoted = arm._promote(base, np.array([0.0, 0.3, 0.8, 0.5]),
                                np.array([0.2, 0.0, 0.1, 0.0]))
        self.assertTrue(np.all(promoted >= base))
        self.assertTrue(np.all(promoted < 1.0))

    def test_a_stronger_fit_promotes_further(self):
        base = np.full(3, 0.4)
        promoted = arm._promote(base, np.array([0.0, 0.5, 0.9]))
        self.assertTrue(np.all(np.diff(promoted) > 0.0))


class StatedScopeTests(unittest.TestCase):
    def test_the_question_states_what_it_literally_names(self):
        layer = _layer(products=["ActionGenie", "VizForce"])
        stated = arm._stated_scope(
            layer, "Which documents did eid_4afd9484 review for ActionGenie in 2026?")
        self.assertEqual(stated, {"product": "ActionGenie", "section": "documents",
                                  "employee_id": "eid_4afd9484", "years": [2026]})

    def test_a_question_that_names_nothing_states_nothing(self):
        self.assertEqual(arm._stated_scope(_layer(products=["VizForce"]),
                                           "who approved the budget?"), {})

    def test_a_section_matches_its_readable_multiword_form(self):
        stated = arm._stated_scope(
            _layer(), "What do the meeting transcripts say about the launch?")
        self.assertEqual(stated["section"], "meeting_transcripts")

    def test_a_product_matches_whole_words_only(self):
        self.assertEqual(arm._stated_scope(_layer(products=["VizForce"]),
                                           "how does vizforcex compare?"), {})

    def test_the_earliest_product_mention_wins(self):
        stated = arm._stated_scope(_layer(products=["ActionGenie", "VizForce"]),
                                   "Compare VizForce with ActionGenie")
        self.assertEqual(stated["product"], "VizForce")

    def test_the_reach_is_the_fraction_of_the_stated_fields_a_chunk_matches(self):
        layer = _layer(chunk_rows=[
            _chunk_row("c0", product="VizForce", years=[2026]),
            _chunk_row("c1", product="VizForce"),
            _chunk_row("c2"),
            _chunk_row("c3", years=[2026])])
        reach = arm._scope_reach(layer, {"product": "VizForce", "years": [2026]})
        np.testing.assert_allclose(reach, [1.0, 0.5, 0.0, 0.5])

    def test_nothing_stated_reaches_nothing(self):
        layer = _layer()
        np.testing.assert_allclose(arm._scope_reach(layer, {}), np.zeros(4))


class RetrieveTests(unittest.TestCase):
    def test_a_non_positive_k_fails_before_any_work(self):
        with self.assertRaisesRegex(ValueError, "k must be positive"):
            arm._retrieve(_layer(), _QVEC, "q", 0)

    def test_the_depth_is_the_chunks_the_areas_reached_under_the_callers_k(self):
        layer = _layer()
        rows, meta = arm._retrieve(layer, _QVEC, "q", 50)
        self.assertEqual(meta["K"], meta["reached"])
        self.assertEqual(len(rows), meta["K"])
        self.assertLessEqual(meta["reached"], meta["population"])

    def test_the_callers_k_caps_the_depth(self):
        rows, meta = arm._retrieve(_layer(), _QVEC, "q", 1)
        self.assertEqual((len(rows), meta["K"]), (1, 1))

    def test_a_selected_row_carries_the_pointer_the_resolver_reads(self):
        rows, _ = arm._retrieve(_layer(), _QVEC, "q", 50)
        self.assertEqual(sorted(rows[0]),
                         ["chunkId", "locator", "relpath", "score", "sha256"])

    def test_an_oracle_chunk_is_never_selected(self):
        layer = _layer(chunk_rows=[
            _chunk_row("c0"), _chunk_row("c1"),
            _chunk_row("c2", section="unanswerable_questions"), _chunk_row("c3")])
        rows, meta = arm._retrieve(layer, _QVEC, "q", 50)
        self.assertNotIn("c2", [r["chunkId"] for r in rows])
        self.assertEqual(meta["population"], 3)

    def test_equal_scores_rank_on_the_chunk_id(self):
        layer = _layer()
        with patch.object(arm, "_promote", return_value=np.zeros(4)), \
             patch.object(arm, "_region", lambda support, order: order):
            rows, _ = arm._retrieve(layer, _QVEC, "q", 50)
        ids = [r["chunkId"] for r in rows]
        self.assertGreater(len(ids), 1)
        self.assertEqual(ids, sorted(ids))

    def test_the_meta_records_the_demand_the_prompt_read(self):
        _, meta = arm._retrieve(_layer(), _QVEC, "q", 50)
        self.assertEqual(sorted(meta["demand"]), sorted(arm.ALL_FACETS))
        self.assertAlmostEqual(sum(meta["demand"].values()), 1.0)
        self.assertEqual(len(meta["areas"]), len(arm.ALL_FACETS))

    def test_the_meta_records_the_reliability_the_demand_was_shrunk_by(self):
        layer = _layer()
        _, meta = arm._retrieve(layer, _QVEC, "q", 50)
        self.assertEqual(sorted(meta["reliability"]), sorted(arm.ALL_FACETS))
        np.testing.assert_allclose(
            [meta["reliability"][f] for f in arm.ALL_FACETS], layer.reliability)


class ContractTests(unittest.TestCase):
    def test_the_arm_is_selectable_from_the_runner(self):
        self.assertIn("artefact_v1_relevance_weight", run.ARMS)

    def test_the_manifest_records_the_regime_the_run_carried(self):
        self.assertEqual(sorted(arm.RETRIEVAL_FLAGS), ["HERB_DEMAND"])

    def test_no_interpreter_plans_the_query(self):
        self.assertEqual(arm.INTERPRET_MODEL, "deterministic")


if __name__ == "__main__":
    unittest.main()

"""clump_levels: what a column is cut into, and what it refuses to cut."""
import unittest

import numpy as np

from arms.artefact_v3 import WEIGHT_GRAIN, clump_levels


def levels_of(values):
    """the level per distinct value, ascending — the shape of the cut, not the row order"""
    lv = clump_levels(np.asarray(values, dtype=np.float64))
    out = {}
    for v, l in zip(np.round(values, 3), lv):
        out.setdefault(float(v), int(l))
    return [out[k] for k in sorted(out)]


class ClumpLevels(unittest.TestCase):

    def test_empty_and_single(self):
        self.assertEqual(len(clump_levels(np.zeros(0))), 0)
        self.assertEqual(list(clump_levels(np.array([0.3]))), [0])

    def test_one_value_is_one_level(self):
        """a column of identical distances orders nothing and passes every row on"""
        self.assertEqual(list(clump_levels(np.full(40, 0.30))), [0] * 40)

    def test_rows_on_one_value_never_split(self):
        d = np.array([0.10] * 7 + [0.90] * 7)
        lv = clump_levels(d)
        self.assertEqual(len(set(lv[:7])), 1)
        self.assertEqual(len(set(lv[7:])), 1)
        self.assertNotEqual(lv[0], lv[7])

    def test_levels_ascend_with_distance(self):
        d = np.array([0.9, 0.1, 0.5, 0.1])
        lv = clump_levels(d)
        self.assertLessEqual(lv[1], lv[2])
        self.assertLessEqual(lv[2], lv[0])
        self.assertEqual(lv[1], lv[3])

    def test_nothing_below_the_grain_is_separated(self):
        """the edge weights are written on a 0.001 grid; adjacent cells are not structure"""
        d = np.round(0.800 + WEIGHT_GRAIN * np.arange(5), 3).repeat(4)
        self.assertEqual(len(set(clump_levels(d))), 1)

    def test_a_far_outlier_does_not_shatter_the_clump_it_left(self):
        """the failure of a rule that tests a gap against the mean gap: once the outlier is cut
        away the remainder's span is four grain steps, and every step beats that mean"""
        d = np.array([0.10] + list(np.round(0.800 + WEIGHT_GRAIN * np.arange(5), 3)) * 4)
        lv = clump_levels(d)
        self.assertEqual(lv[0], 0)
        self.assertEqual(len(set(lv[1:])), 1)
        self.assertEqual(len(set(lv)), 2)

    def test_a_clump_with_spread_absorbs_what_sits_at_its_own_scale(self):
        """0.75 stands 0.03 off a clump that is itself spread over 0.04 — one level"""
        self.assertEqual(levels_of([0.75, 0.78, 0.79, 0.80, 0.82]), [0, 0, 0, 0, 0])

    def test_a_clump_with_no_spread_cannot_reach(self):
        """the same 0.03 against a clump of one value: the clump has no scale to absorb with,
        so 0.75 stays out. Absorption needs a reach and a reach would be an invented width."""
        self.assertEqual(levels_of([0.75] + [0.79] * 4), [0, 1])

    def test_a_column_that_is_only_chance_stays_one_level(self):
        """scattered values are not clumps; the facet says nothing and the next one speaks"""
        rng = np.random.default_rng(7)
        singles = 0
        for _ in range(200):
            d = np.round(rng.random(60), 3)
            if len(set(clump_levels(d))) == 1:
                singles += 1
        self.assertGreater(singles, 100)

    def test_a_real_separation_is_found(self):
        """two masses a long way apart, each packed at the grain"""
        left = np.round(0.10 + WEIGHT_GRAIN * np.arange(10), 3)
        right = np.round(0.80 + WEIGHT_GRAIN * np.arange(10), 3)
        lv = clump_levels(np.concatenate([left, right]))
        self.assertEqual(len(set(lv)), 2)
        self.assertEqual(len(set(lv[:10])), 1)
        self.assertEqual(len(set(lv[10:])), 1)

    def test_the_cut_is_scale_free(self):
        """the same shape at a hundredth of the span cuts the same way"""
        big = np.array([0.0, 0.001, 0.002, 0.500, 0.501, 0.502])
        small = np.array([0.0, 0.001, 0.002, 0.020, 0.021, 0.022])
        self.assertEqual(list(clump_levels(big)), list(clump_levels(small)))


if __name__ == "__main__":
    unittest.main()

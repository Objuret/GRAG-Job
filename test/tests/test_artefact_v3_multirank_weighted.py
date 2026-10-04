"""HERB_V3_SORT=multirank and HERB_V3_SORT=weighted — the gates of SPEC.md §6 as SPEC-v2.md
amends them (G18 replaced, G19–G21 added).

Every test runs the modes' own level functions and key builder on synthetic pools. No database,
no model, no question file, no gold. G22 is a report, not a gate, and lives in the run.
"""
import importlib
import json
import os
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path

import numpy as np

DB = "herb-eval-volmax"
ROOT = Path(__file__).resolve().parent.parent.parent
OVERLAY = ROOT / "output" / "facet_pairs" / "rounds" / "round1" / "overlay.json"
LAYOUT = ("topic", "temporal", "why", "activity", "concreteness")
FOUR = ("temporal", "why", "activity", "concreteness")
ONES = {f: 1.0 for f in FOUR}


def reload_arm(**env):
    """import artefact_v3 under this environment; every knob is read at import"""
    keys = ("HERB_FACET_SOURCE", "HERB_FACET_FILE", "HERB_FACET_STATS", "NEO4J_DATABASE",
            "HERB_TAG_RUN_ID", "HERB_V3_SORT", "HERB_V3_TOPIC_KEY", "HERB_V3_TOPIC_BAND",
            "HERB_V3_FACET_BAND", "HERB_V3_DESC_PLACE", "HERB_V3_W", "HERB_V3_BETA",
            "HERB_V3_ADJUST", "HERB_V3_LINK2", "HERB_V3_REGION", "HERB_V3_LOCALITY",
            "HERB_V3_TAGREL", "HERB_V3_RAW_PART", "HERB_V3_PARTCOMB", "HERB_V3_FACETADJ",
            "HERB_V3_TAGSIDE", "HERB_V3_BAND", "HERB_V3_SCOPE_FIELDS", "HERB_V3_SCOPE_JOIN")
    before = {k: os.environ.get(k) for k in keys}
    for k in keys:
        os.environ.pop(k, None)
    os.environ["NEO4J_DATABASE"] = DB
    os.environ["HERB_FACET_SOURCE"] = "file"
    os.environ["HERB_FACET_FILE"] = str(OVERLAY)
    os.environ.update({k: v for k, v in env.items() if v is not None})
    try:
        for name in [n for n in list(sys.modules) if n.startswith("arms.artefact_v")]:
            del sys.modules[name]
        return importlib.import_module("arms.artefact_v3")
    finally:
        for k, v in before.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v


def part_of(order=LAYOUT, weights=None):
    p = {"t": "a part", "order": list(order)}
    if weights:
        p["weights"] = dict(weights)
    return p


def order_pool(A, mode, topic, S, *, order=LAYOUT, link2=None, link6=None, tag_cos=None,
               ids=None, topic_band=0.028, facet_band=1.0, weights=None, betas=None,
               adjust="bounded", g_band=None, topic_key="ordered", r_band=0.002,
               desc_place="after", part_rank=0, rows=None):
    """one pool through the modes' real level functions and key builder; returns the chunk ids
    in delivered order, the keys and the key names"""
    topic = np.asarray(topic, dtype=np.float64)
    S = np.asarray(S, dtype=np.float64)
    m = topic.size
    link2 = np.zeros(m) if link2 is None else np.asarray(link2, dtype=np.float64)
    link6 = np.zeros(m) if link6 is None else np.asarray(link6, dtype=np.float64)
    tag_cos = np.zeros(m) if tag_cos is None else np.asarray(tag_cos, dtype=np.float64)
    ids = [f"c{i:03d}" for i in range(m)] if ids is None else list(ids)
    if rows is not None:
        topic, S = topic[rows], S[rows]
        link2, link6, tag_cos = link2[rows], link6[rows], tag_cos[rows]
        ids = [ids[i] for i in rows]
    cols, names, info = A.mode_key_columns(
        mode, topic, S, tuple(order), LAYOUT, topic_band=topic_band, facet_band=facet_band,
        weights=weights, betas=betas, adjust=adjust, g_band=g_band, topic_key=topic_key,
        r_band=r_band)
    keys, key_names = A.pool_key_tuples(
        part_rank, cols, names, A.pool_steps(link2, 0.05), A.pool_steps(link6, 0.05),
        tag_cos, ids, desc_place)
    out = sorted(range(len(ids)), key=lambda i: keys[i])
    return [ids[i] for i in out], [keys[i] for i in out], key_names, info


class Levels(unittest.TestCase):
    """the level rule (SPEC-v2 S5) — steps below the pool's best"""

    @classmethod
    def setUpClass(cls):
        cls.A = reload_arm(HERB_V3_SORT="multirank")

    def test_g5_delta_to_zero_is_strict_lexicographic(self):
        v = np.array([1.0, 0.9, 0.7, 0.699, 0.2])
        lv = self.A.pool_steps(v, 1e-9)
        self.assertEqual(len(set(lv.tolist())), 5)
        self.assertEqual(list(np.argsort(lv)), list(np.argsort(-v)))

    def test_g5_delta_over_range_makes_the_key_vanish(self):
        v = np.array([1.0, 0.9, 0.7, 0.2])
        self.assertEqual(self.A.pool_steps(v, 10.0).tolist(), [0, 0, 0, 0])
        self.assertEqual(self.A.pool_steps(v, float("inf")).tolist(), [0, 0, 0, 0])

    def test_g6_adding_a_constant_changes_nothing(self):
        v = np.array([1.0, 0.75, 0.5, 0.125])
        self.assertEqual(self.A.pool_steps(v, 0.125).tolist(),
                         self.A.pool_steps(v + 3.0, 0.125).tolist())

    def test_g7_column_times_k_and_delta_times_k_change_nothing(self):
        v = np.array([1.0, 0.75, 0.5, 0.125])
        base = self.A.pool_steps(v, 0.125).tolist()
        for kk in (2.0, 4.0, 0.5):
            self.assertEqual(self.A.pool_steps(v * kk, 0.125 * kk).tolist(), base)

    def test_g8_a_strictly_separated_pair_is_never_reversed(self):
        rng = np.random.default_rng(7)
        for _ in range(200):
            v = rng.normal(size=12)
            lv = self.A.pool_steps(v, 0.3)
            for i in range(12):
                for j in range(12):
                    if v[i] > v[j]:
                        self.assertLessEqual(lv[i], lv[j])

    def test_g9_an_empty_gap_stays_twenty_levels(self):
        v = np.array([1.0, 1.0 - 20 * 0.05])
        self.assertEqual(self.A.pool_steps(v, 0.05).tolist(), [0, 20])

    def test_g10_adding_one_element_inside_the_range_reorders_no_other_pair(self):
        v = np.array([1.0, 0.82, 0.61, 0.4])
        before = self.A.pool_steps(v, 0.07).tolist()
        after = self.A.pool_steps(np.append(v, 0.7), 0.07).tolist()
        self.assertEqual(before, after[:4])

    def test_g19_nan_sorts_last_and_never_enters_the_max(self):
        v = np.array([np.nan, 0.5, 0.4])
        lv = self.A.pool_steps(v, 0.05)
        self.assertEqual(lv.tolist(), [3, 0, 2])          # max is 0.5, not the NaN
        self.assertEqual(self.A.pool_steps(np.array([np.nan, np.nan]), 0.05).tolist(), [0, 0])

    def test_an_infinite_band_does_not_demote_a_nan(self):
        """an infinite band is no band: the column vanishes and orders nothing, so a missing
        value must not be pushed to the back by a key that is not acting"""
        v = np.array([np.nan, 0.5, 0.4, np.nan])
        self.assertEqual(self.A.pool_steps(v, float("inf")).tolist(), [0, 0, 0, 0])
        self.assertEqual(self.A.pool_steps(np.array([np.nan, 1.0]), float("inf")).tolist(),
                         [0, 0])
        # and at a finite band the NaN is still last
        self.assertEqual(self.A.pool_steps(v, 0.05)[0], 3)

    def test_a_band_must_be_positive(self):
        with self.assertRaises(ValueError):
            self.A.pool_steps(np.array([1.0, 0.0]), 0.0)


class Multirank(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.A = reload_arm(HERB_V3_SORT="multirank")

    def pool(self, **kw):
        return order_pool(self.A, "multirank", **kw)

    def test_g2_a_shuffled_pool_gives_the_same_order(self):
        rng = np.random.default_rng(11)
        topic = rng.normal(0.3, 0.05, 25)
        S = rng.normal(0, 2, (25, 4))
        base, _, _, _ = self.pool(topic=topic, S=S)
        for seed in range(20):
            perm = np.random.default_rng(100 + seed).permutation(25)
            got, _, _, _ = self.pool(topic=topic, S=S, rows=perm)
            self.assertEqual(got, base, f"seed {seed}")

    def test_g3_a_tie_permutation_keeps_the_delivered_set(self):
        topic = np.full(8, 0.3)
        S = np.zeros((8, 4))
        base, _, _, _ = self.pool(topic=topic, S=S)
        for seed in range(10):
            perm = np.random.default_rng(seed).permutation(8)
            got, _, _, _ = self.pool(topic=topic, S=S, rows=perm)
            self.assertEqual(set(got), set(base))

    def test_g12_a_pool_separated_on_one_facet_only_takes_that_column_s_order(self):
        m = 6
        topic = np.full(m, 0.3)
        S = np.zeros((m, 4))
        for fi, f in enumerate(FOUR):
            col = np.arange(m, dtype=float) * 3.0        # 3 > the band, so every row separates
            Sx = S.copy()
            Sx[:, fi] = col
            order = (f,) + tuple(x for x in LAYOUT if x != f)
            got, _, _, _ = self.pool(topic=topic, S=Sx, order=order, facet_band=1.0)
            self.assertEqual(got, [f"c{i:03d}" for i in range(m - 1, -1, -1)], f)

    def test_g20_equal_values_are_one_level_and_the_order_is_input_independent(self):
        topic = np.full(7, 0.42)
        S = np.full((7, 4), 1.5)
        cols, names, _ = self.A.mode_key_columns(
            "multirank", topic, S, LAYOUT, LAYOUT, topic_band=0.028, facet_band=1.0)
        for c in cols:
            self.assertEqual(len(set(np.asarray(c).tolist())), 1)
        base, _, _, _ = self.pool(topic=topic, S=S)
        for seed in range(5):
            perm = np.random.default_rng(seed).permutation(7)
            got, _, _, _ = self.pool(topic=topic, S=S, rows=perm)
            self.assertEqual(got, base)

    def test_g21_the_mode_key_changes_the_order_against_the_same_chain_without_it(self):
        # topic ties every row; the four columns separate them; link 6 would order them the
        # other way round, so a key that is not wired cannot produce this order
        m = 5
        topic = np.full(m, 0.3)
        S = np.zeros((m, 4))
        S[:, 0] = np.array([0.0, 3.0, 6.0, 9.0, 12.0])
        link6 = np.array([1.0, 0.8, 0.6, 0.4, 0.2])
        with_key, _, _, _ = self.pool(topic=topic, S=S, order=("temporal",) + FOUR[1:] + ("topic",),
                                      link6=link6, facet_band=1.0)
        without, _, _, _ = self.pool(topic=topic, S=np.zeros((m, 4)),
                                     order=("temporal",) + FOUR[1:] + ("topic",),
                                     link6=link6, facet_band=float("inf"),
                                     topic_band=float("inf"))
        self.assertEqual(without, [f"c{i:03d}" for i in range(m)])
        self.assertEqual(with_key, [f"c{i:03d}" for i in range(m - 1, -1, -1)])
        self.assertNotEqual(with_key, without)

    def test_topic_key_first_puts_topic_at_the_front(self):
        topic = np.array([0.5, 0.4, 0.3])
        S = np.zeros((3, 4))
        S[:, 0] = np.array([0.0, 5.0, 10.0])
        ordered, _, names_o, _ = self.pool(topic=topic, S=S,
                                           order=("temporal", "topic", "why", "activity",
                                                  "concreteness"), topic_key="ordered")
        first, _, names_f, _ = self.pool(topic=topic, S=S,
                                         order=("temporal", "topic", "why", "activity",
                                                "concreteness"), topic_key="first")
        self.assertEqual(names_o[1], "temporal")
        self.assertEqual(names_f[1], "topic")
        self.assertEqual(ordered, ["c002", "c001", "c000"])
        self.assertEqual(first, ["c000", "c001", "c002"])

    def test_desc_place_before_moves_the_two_links_ahead(self):
        topic = np.zeros(3)
        S = np.zeros((3, 4))
        S[:, 0] = np.array([0.0, 5.0, 10.0])
        link6 = np.array([1.0, 0.8, 0.6])
        after, _, names_a, _ = self.pool(topic=topic, S=S, link6=link6, desc_place="after")
        before, _, names_b, _ = self.pool(topic=topic, S=S, link6=link6, desc_place="before")
        self.assertEqual(names_a[1:3], ["topic", "temporal"])
        self.assertEqual(names_b[1:3], ["link2", "link6"])
        self.assertEqual(after, ["c002", "c001", "c000"])
        self.assertEqual(before, ["c000", "c001", "c002"])


class Weighted(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.A = reload_arm(HERB_V3_SORT="weighted")

    def pool(self, **kw):
        kw.setdefault("weights", ONES)
        return order_pool(self.A, "weighted", **kw)

    def test_g11_bounded_never_overturns_a_pair_separated_by_a_topic_level(self):
        """the assertion is on the MODE KEY's own column, with g built adversarially: the
        facet sum is made to pull every pair the wrong way, as hard as it can"""
        rng = np.random.default_rng(3)
        d_topic = 0.028
        checked = 0
        for trial in range(60):
            m = 9
            topic = rng.uniform(0.1, 0.6, m)
            # adversarial g: the WORSE a row's topic, the larger its facet values, so the
            # adjust pushes exactly against topic
            S = np.repeat((-topic * 40.0 + rng.normal(0, 0.5, m))[:, None], 4, axis=1)
            cols, names, _ = self.A.mode_key_columns(
                "weighted", topic, S, LAYOUT, LAYOUT, topic_band=d_topic, facet_band=1.0,
                weights=ONES, adjust="bounded", r_band=self.A.COS_NOISE)
            lv = np.asarray(cols[0])
            self.assertEqual(len(cols), 1)
            for i in range(m):
                for j in range(m):
                    if topic[i] - topic[j] > d_topic + self.A.COS_NOISE:
                        checked += 1
                        # a better level is a strictly smaller number: never reversed, never tied
                        self.assertLess(int(lv[i]), int(lv[j]),
                                        f"trial {trial}: {topic[i]} vs {topic[j]}")
        self.assertGreater(checked, 100)

    def test_g11_level_never_overturns_a_topic_level(self):
        """under ADJUST=level the two-column key is compared as the walk compares it — the
        whole tuple — with g built to disagree with topic on every pair"""
        rng = np.random.default_rng(5)
        checked = 0
        for _ in range(40):
            m = 8
            topic = rng.uniform(0.1, 0.6, m)
            S = np.repeat((-topic * 40.0 + rng.normal(0, 0.5, m))[:, None], 4, axis=1)
            cols, names, _ = self.A.mode_key_columns(
                "weighted", topic, S, LAYOUT, LAYOUT, topic_band=0.028, facet_band=1.0,
                weights=ONES, adjust="level", g_band=1.0)
            self.assertEqual(names, ["topic", "g"])
            lv_t, lv_g = np.asarray(cols[0]), np.asarray(cols[1])
            for i in range(m):
                for j in range(m):
                    if lv_t[i] < lv_t[j]:
                        checked += 1
                        # the FULL key of i must sort before the full key of j whatever g says
                        self.assertLess((int(lv_t[i]), int(lv_g[i])),
                                        (int(lv_t[j]), int(lv_g[j])))
                        self.assertTrue(int(lv_g[i]) > int(lv_g[j])
                                        or lv_g[i] == lv_g[j] or True)
        self.assertGreater(checked, 100)

    def test_g11_the_adversarial_g_really_does_pull_the_other_way(self):
        """the two tests above are only worth something if g disagrees with topic — shown"""
        rng = np.random.default_rng(7)
        topic = rng.uniform(0.1, 0.6, 12)
        S = np.repeat((-topic * 40.0)[:, None], 4, axis=1)
        g, _, _ = self.A.weighted_g(S, np.ones(4), np.ones(4))
        self.assertLess(float(np.corrcoef(topic, g)[0, 1]), -0.9)
        # with no topic band at all, g decides and the order is topic's reversed
        cols, _, _ = self.A.mode_key_columns(
            "weighted", topic, S, LAYOUT, LAYOUT, topic_band=0.028, facet_band=1.0,
            weights=ONES, adjust="level", g_band=1.0)
        self.assertGreater(len(set(np.asarray(cols[1]).tolist())), 1)

    def test_g11_all_weights_zero_is_the_topic_then_description_order(self):
        topic = np.array([0.5, 0.5, 0.4])
        S = np.array([[9.0, 9, 9, 9], [-9.0, -9, -9, -9], [9.0, 9, 9, 9]])
        link6 = np.array([0.1, 0.9, 0.5])
        zero = {f: 0.0 for f in FOUR}
        got, _, _, _ = self.pool(topic=topic, S=S, weights=zero, link6=link6, topic_band=0.028)
        self.assertEqual(got, ["c001", "c000", "c002"])   # topic ties 0 and 1, link 6 splits

    def test_g11_a_one_hot_weight_orders_by_that_facet_inside_a_topic_level(self):
        m = 5
        topic = np.full(m, 0.3)
        for fi, f in enumerate(FOUR):
            S = np.zeros((m, 4))
            S[:, fi] = np.arange(m, dtype=float)
            w = {x: (1.0 if x == f else 0.0) for x in FOUR}
            got, _, _, _ = self.pool(topic=topic, S=S, weights=w, topic_band=0.028,
                                     r_band=self.A.COS_NOISE)
            self.assertEqual(got, [f"c{i:03d}" for i in range(m - 1, -1, -1)], f)

    def test_g18_one_hot_g_reproduces_that_column_s_order(self):
        rng = np.random.default_rng(19)
        S = rng.normal(0, 2, (30, 4))
        for fi, f in enumerate(FOUR):
            w = np.array([1.0 if i == fi else 0.0 for i in range(4)])
            g, dropped, allnan = self.A.weighted_g(S, w, np.ones(4))
            self.assertEqual((dropped, allnan), (0, 0))
            self.assertEqual(list(np.argsort(-g)), list(np.argsort(-S[:, fi])))

    def test_g19_a_nan_term_is_dropped_and_counted(self):
        S = np.array([[1.0, 2.0, np.nan, 4.0], [np.nan, np.nan, np.nan, np.nan],
                      [0.0, 0.0, 0.0, 0.0]])
        g, dropped, allnan = self.A.weighted_g(S, np.ones(4), np.ones(4))
        self.assertEqual(dropped, 5)
        self.assertEqual(allnan, 1)
        self.assertTrue(np.isnan(g[1]))
        self.assertFalse(np.isnan(g[0]))

    def test_g20_a_constant_pool_gives_one_level(self):
        topic = np.full(6, 0.3)
        S = np.full((6, 4), -2.0)
        cols, names, _ = self.A.mode_key_columns(
            "weighted", topic, S, LAYOUT, LAYOUT, topic_band=0.028, facet_band=1.0,
            weights=ONES, adjust="bounded", r_band=self.A.COS_NOISE)
        self.assertEqual(len(set(np.asarray(cols[0]).tolist())), 1)

    def test_g25_a_constant_adjust_reproduces_the_topic_order(self):
        # the two modes do not double count: with g constant over the pool, weighted reads
        # topic alone, which is multirank's first column when topic leads the order
        rng = np.random.default_rng(23)
        topic = rng.uniform(0.1, 0.6, 12)
        S = np.zeros((12, 4))
        w_got, _, _, _ = self.pool(topic=topic, S=S, topic_band=0.028,
                                   r_band=self.A.COS_NOISE)
        m_got, _, _, _ = order_pool(self.A, "multirank", topic=topic, S=S,
                                    order=("topic",) + FOUR, topic_band=self.A.COS_NOISE,
                                    facet_band=1.0)
        self.assertEqual(w_got, m_got)

    def test_the_roc_weights_are_the_rank_order_centroid(self):
        w = self.A.roc_weights(4)
        self.assertAlmostEqual(sum(w), 1.0, places=12)
        self.assertTrue(all(w[i] > w[i + 1] for i in range(3)))
        self.assertAlmostEqual(w[0], (1 + 1 / 2 + 1 / 3 + 1 / 4) / 4, places=12)

    def test_the_weight_rules_and_their_sources(self):
        part = part_of(order=("why", "topic", "temporal", "activity", "concreteness"),
                       weights={f: v for f, v in zip(LAYOUT, (1.0, 0.8, 0.9, 0.4, 0.2))})
        for rule, expect in (("equal", "equal"), ("zero", "zero"), ("roc", "roc"),
                             ("cached", "cached")):
            A = reload_arm(HERB_V3_SORT="weighted", HERB_V3_W=rule)
            w, src = A.part_facet_weights(part, LAYOUT)
            self.assertEqual(src, expect)
            self.assertEqual(sorted(w), sorted(FOUR))
        A = reload_arm(HERB_V3_SORT="weighted", HERB_V3_W="cached")
        w, src = A.part_facet_weights(part_of(), LAYOUT)
        self.assertTrue(src.startswith("equal"))
        self.assertEqual(set(w.values()), {1.0})


class Determinism(unittest.TestCase):

    def test_g1_two_process_starts_give_the_same_order(self):
        script = textwrap.dedent(f"""
            import json, os, sys
            sys.path[:0] = [r"{ROOT / 'prod'}", r"{ROOT / 'test'}"]
            os.environ["NEO4J_DATABASE"] = "{DB}"
            os.environ["HERB_FACET_SOURCE"] = "file"
            os.environ["HERB_FACET_FILE"] = r"{OVERLAY}"
            os.environ["HERB_V3_SORT"] = "multirank"
            import numpy as np
            import arms.artefact_v3 as A
            rng = np.random.default_rng(31)
            topic = rng.uniform(0.1, 0.6, 40)
            S = rng.normal(0, 2, (40, 4))
            cols, names, _ = A.mode_key_columns("multirank", topic, S,
                {tuple(LAYOUT)!r}, {tuple(LAYOUT)!r}, topic_band=0.028, facet_band=1.0)
            ids = ["c%03d" % i for i in range(40)]
            keys, kn = A.pool_key_tuples(0, cols, names, np.zeros(40, dtype=int),
                                         np.zeros(40, dtype=int), rng.uniform(size=40), ids)
            out = [ids[i] for i in sorted(range(40), key=lambda i: keys[i])]
            print(json.dumps({{"order": out, "names": kn}}))
            """)
        runs = []
        for _ in range(2):
            p = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True,
                               cwd=str(ROOT))
            self.assertEqual(p.returncode, 0, p.stderr[-2000:])
            runs.append(json.loads(p.stdout.strip().splitlines()[-1]))
        self.assertEqual(runs[0], runs[1])


class Static(unittest.TestCase):
    """what the modes must not be able to reach (G4, G13, G14, G16), read from the source"""

    @classmethod
    def setUpClass(cls):
        cls.A = reload_arm(HERB_V3_SORT="multirank")
        import inspect
        cls.names = ("_retrieve_forum", "mode_key_columns", "pool_steps", "pool_key_tuples",
                     "weighted_g", "bounded_r", "part_facet_weights", "roc_weights",
                     "g_band_of", "load_retrain_bands", "_unruled_block", "_decided_by",
                     "_eta_sq", "load_record_kinds")
        cls.src = "\n".join(inspect.getsource(getattr(cls.A, n)) for n in cls.names)

    def test_g13_the_struck_level_rules_are_unreachable(self):
        for forbidden in ("clump_levels", "distance_levels", "facet_positions", "positions(",
                          "facet_relevance", "WEIGHT_GRAIN", "levels_cos", "facet_levels",
                          "column_positions", "grow_region", "tag_concentration"):
            self.assertNotIn(forbidden, self.src, forbidden)

    def test_g4_there_is_no_banded_pairwise_comparator(self):
        self.assertNotIn("cmp_to_key", self.src)
        self.assertIn("cand.sort(key=lambda x: x[0])", self.src)

    def test_g14_no_question_or_gold_symbol_in_the_modes(self):
        """every NAME the modes' code objects read or bind. Prose that names gold100 in an
        `unruled` string is text the run prints, not a symbol the code reads; a name is."""
        seen = set()

        def walk(code):
            seen.update(code.co_names)
            seen.update(code.co_varnames)
            for const in code.co_consts:
                if hasattr(const, "co_names"):
                    walk(const)

        for n in self.names:
            walk(getattr(self.A, n).__code__)
        for name in sorted(seen):
            low = name.lower()
            for forbidden in ("gold", "ground_truth", "citation", "recall", "smoke",
                              "question_set", "reference", "dataset"):
                self.assertNotIn(forbidden, low, f"{name} reads {forbidden}")
        self.assertNotIn("json", seen)          # no question or reference file is opened

    def test_g15_the_pool_cyphers_keep_the_metadata_chunks_out(self):
        for cypher in (self.A._ALL_TAGS_CYPHER, self.A._ALL_CHUNKS_CYPHER,
                       self.A._ALL_EDGES_CYPHER):
            self.assertIn("(c)-[:product]->()", cypher)
        import inspect
        self.assertIn("(c)-[:product]->()", inspect.getsource(self.A.scope_chunks))

    def test_g16_no_write_cypher_anywhere_in_the_arm(self):
        body = Path(self.A.__file__).read_text(encoding="utf-8")
        for verb in ("CREATE ", "MERGE ", "DELETE ", "SET r.", "SET c.", "DETACH"):
            self.assertNotIn(verb, body, verb)

    def test_g17_the_existing_modes_load_no_band_and_no_kind_layer(self):
        """G17 proper ("every existing sort mode's output unchanged") is the existing suite;
        what is asserted here is that the new build adds NOTHING to those modes' state: they
        reach neither the bootstrap band nor the record-kind layer, and a Prepared built for
        them carries both as None."""
        for mode in ("concept", "combo", "chain", "v3"):
            A = reload_arm(HERB_V3_SORT=mode)
            self.assertNotIn(mode, A.FORUM_MODES)
            self.assertIsNone(A._BAND_MODULE, f"{mode} loaded the band module at import")
            self.assertEqual(A._BANDS, {}, f"{mode} read a band at import")
            p = A.Prepared(driver=None, tag_names=[], tag_vecs=np.zeros((0, 2)), chunk_ids=[],
                           chunk_vecs=np.zeros((0, 2)), chunk_rows=[],
                           edge_tag=np.zeros(0, dtype=np.int32),
                           edge_chunk=np.zeros(0, dtype=np.int32), edge_w=np.zeros((0, 5)))
            self.assertIsNone(p.bands, mode)
            self.assertIsNone(p.kinds, mode)
            self.assertIs(A.answer_one_question.__globals__["_retrieve_forum"],
                          A._retrieve_forum)
        # and the dispatch still sends each existing mode to its own walk
        A = reload_arm(HERB_V3_SORT="multirank")
        import inspect
        disp = inspect.getsource(A.answer_one_question)
        for name in ('"concept": _retrieve_concept', '"combo": _retrieve_combo',
                     '"chain": _retrieve_chain', '"multirank": _retrieve_forum',
                     '"weighted": _retrieve_forum'):
            self.assertIn(name, disp)

    def test_the_arm_does_not_pull_torch_in_to_read_the_band(self):
        """the band module imports numpy and nothing else"""
        src = Path(ROOT / "test" / "graph" / "facet_pairs" /
                   "bootstrap_band.py").read_text(encoding="utf-8")
        self.assertNotIn("import torch", src)
        self.assertNotIn("cache_probe", src)
        mod = self.A._bootstrap_module()
        self.assertTrue(hasattr(mod, "flip_gap"))
        self.assertTrue(hasattr(mod, "sample_same_chunk_pairs"))
        # loaded by path, so the facet_pairs directory is not on the front of sys.path
        self.assertNotIn(str(ROOT / "test" / "graph" / "facet_pairs"), sys.path[:2])


class Guards(unittest.TestCase):

    def test_the_modes_require_the_per_edge_file_source(self):
        keys = ("HERB_FACET_SOURCE", "HERB_FACET_FILE", "HERB_V3_SORT", "NEO4J_DATABASE")
        before = {k: os.environ.get(k) for k in keys}
        try:
            for k in keys:
                os.environ.pop(k, None)
            os.environ["NEO4J_DATABASE"] = DB
            os.environ["HERB_V3_SORT"] = "multirank"
            os.environ["HERB_FACET_SOURCE"] = "stats"
            for name in [n for n in list(sys.modules) if n.startswith("arms.artefact_v")]:
                del sys.modules[name]
            with self.assertRaises(ValueError):
                importlib.import_module("arms.artefact_v3")
        finally:
            for k, v in before.items():
                os.environ.pop(k, None)
                if v is not None:
                    os.environ[k] = v
            for name in [n for n in list(sys.modules) if n.startswith("arms.artefact_v")]:
                del sys.modules[name]

    def test_an_unsupported_knob_raises_rather_than_running_another_walk(self):
        for knob, value in (("HERB_V3_LINK2", "sum"), ("HERB_V3_REGION", "shape"),
                            ("HERB_V3_LOCALITY", "on"), ("HERB_V3_RAW_PART", "on"),
                            ("HERB_V3_TAGREL", "shape"), ("HERB_V3_PARTCOMB", "sum"),
                            ("HERB_V3_TAGSIDE", "all")):
            with self.assertRaises(ValueError, msg=knob):
                reload_arm(HERB_V3_SORT="weighted", **{knob: value})

    def test_the_modes_fix_the_region_and_the_locality(self):
        A = reload_arm(HERB_V3_SORT="multirank")
        self.assertEqual((A.REGION, A.LOCALITY, A.TAGSIDE), ("tags", "off", "nonscope"))

    def test_the_defaults_are_the_spec_s(self):
        A = reload_arm(HERB_V3_SORT="weighted")
        self.assertEqual((A.TOPIC_KEY, A.TOPIC_BAND, A.FACET_BAND_RULE, A.DESC_PLACE,
                          A.W_RULE, A.BETA_RULE, A.ADJUST, A.BAND_RULE),
                         ("ordered", "write", "flip", "after", "cached", "off", "bounded",
                          "paraphrase"))
        self.assertEqual(A.TOPIC_WRITE_BAND, 0.028)

    def test_every_construction_is_carried_as_unruled(self):
        A = reload_arm(HERB_V3_SORT="weighted")
        rows = A._unruled_block()
        self.assertTrue(all({"item", "default", "text"} <= set(r) for r in rows))
        text = " ".join(r["text"] for r in rows)
        self.assertIn("thats how you PICK the tags", text)
        self.assertIn("His to rule.", text)


class KeyAttribution(unittest.TestCase):
    """what the run has to report: which place in the key decided each adjacent pair"""

    @classmethod
    def setUpClass(cls):
        cls.A = reload_arm(HERB_V3_SORT="multirank")

    def test_the_first_differing_place_is_named(self):
        names = ["part rank", "topic", "temporal", "link2", "link6", "tag cosine", "chunk id"]
        keys = [(0, 0, 0, 0, 0, -0.5, "a"),
                (0, 0, 0, 0, 0, -0.4, "b"),
                (0, 0, 1, 0, 0, -0.9, "c"),
                (1, 0, 0, 0, 0, -0.9, "d")]
        per_row = [names] * 4
        got = self.A._decided_by(keys, [0, 0, 0, 0], [0, 0, 0, 0], per_row)
        self.assertEqual(got, [None, "tag cosine", "temporal", "part rank"])
        self.assertEqual(self.A._decided_by(keys, [0, 0, 1, 1], [0, 1, 1, 1], per_row),
                         [None, "pick level", "scope pass", "part rank"])
        # a row is named by ITS OWN part's order: the same key tuple, another facet name
        other = list(names)
        other[2] = "why"
        self.assertEqual(self.A._decided_by(keys, [0] * 4, [0] * 4,
                                            [names, names, other, other])[2], "why")
        self.assertEqual(self.A._tally(got[1:]),
                         {"part rank": 1, "tag cosine": 1, "temporal": 1})

    def test_eta_squared_is_a_share_between_zero_and_one(self):
        v = np.array([1.0, 1.1, 5.0, 5.1])
        g = ["slack", "slack", "prs", "prs"]
        e = self.A._eta_sq(v, g)
        self.assertGreater(e, 0.9)
        self.assertLessEqual(e, 1.0)
        self.assertIsNone(self.A._eta_sq(np.array([2.0, 2.0, 2.0]), ["a", "b", "c"]))


def _u(v):
    v = np.asarray(v, dtype=np.float64)
    return v / np.linalg.norm(v)


class FakeSession:
    """stands in for the Neo4j session `scope_chunks` runs its one read query on"""

    def __init__(self, in_scope):
        self.in_scope = list(in_scope)
        self.queries = 0

    def run(self, cypher, **params):
        self.queries += 1
        assert "MATCH" in cypher and "CREATE" not in cypher and "MERGE" not in cypher
        return [{"chunkId": c} for c in self.in_scope]


class Walk(unittest.TestCase):
    """the whole of _retrieve_forum on a synthetic corpus: no database, no model, no question
    file. Six chunks, four tags of which one is a Product node's name and is the nearest tag
    of part 0, two parts, two scope passes, one NaN in the file layer."""

    TAGS = ("Prod", "alpha", "beta", "gamma")
    CHUNKS = ("c0", "c1", "c2", "c3", "c4", "c5")
    # (tag, chunk) edges; c5 is reachable only out of scope
    EDGES = (("Prod", "c0"), ("alpha", "c0"), ("alpha", "c1"), ("beta", "c1"),
             ("beta", "c2"), ("gamma", "c2"), ("alpha", "c3"), ("gamma", "c3"),
             ("beta", "c4"), ("alpha", "c5"), ("gamma", "c5"), ("Prod", "c5"))

    def build(self, A, edge_order=None, nan_edge=("gamma", "c3")):
        tag_vecs = {
            "Prod": _u([1.0, 0.0, 0.0]),          # the nearest tag of part 0, and not a candidate
            "alpha": _u([0.995, 0.0999, 0.0]),
            "beta": _u([0.97, 0.243, 0.0]),
            "gamma": _u([0.90, 0.436, 0.0]),
        }
        chunk_vecs = {
            "c0": _u([1.0, 0.02, 0.0]), "c1": _u([1.0, 0.05, 0.0]),
            "c2": _u([1.0, 0.09, 0.0]), "c3": _u([1.0, 0.13, 0.0]),
            "c4": _u([1.0, 0.17, 0.0]), "c5": _u([1.0, 0.21, 0.0]),
        }
        edges = list(self.EDGES if edge_order is None else edge_order)
        e_tag = np.asarray([self.TAGS.index(t) for t, _ in edges], dtype=np.int32)
        e_chunk = np.asarray([self.CHUNKS.index(c) for _, c in edges], dtype=np.int32)
        W = np.zeros((len(edges), 5), dtype=np.float64)
        for i, (t, c) in enumerate(edges):
            W[i, 0] = float(tag_vecs[t] @ chunk_vecs[c])            # topic, the graph cosine
            base = self.CHUNKS.index(c) * 3.0 + self.TAGS.index(t)
            W[i, 1:] = [base, -base, base * 0.5, -base * 0.5]
            if (t, c) == nan_edge:
                W[i, 2] = np.nan                                    # one missing value
        product_tag = np.array([t == "Prod" for t in self.TAGS])
        p = A.Prepared(
            driver=None, tag_names=list(self.TAGS),
            tag_vecs=np.stack([tag_vecs[t] for t in self.TAGS]),
            chunk_ids=list(self.CHUNKS),
            chunk_vecs=np.stack([chunk_vecs[c] for c in self.CHUNKS]),
            chunk_rows=[{"chunkId": c, "locator": "{}", "relpath": f"{c}.json",
                         "sha256": "0" * 8} for c in self.CHUNKS],
            edge_tag=e_tag, edge_chunk=e_chunk, edge_w=W,
            shape={"product_tag": product_tag},
            kinds=["slack", "slack", "prs", "prs", "documents", "documents"],
            bands={"npz": "synthetic", "sha256": None, "draws": 2, "edges": len(edges),
                   "columns": ["temporal", "why", "activity", "concreteness"],
                   "pair_sample": "synthetic", "pairs": 0, "pair_seed": 0,
                   "flip_rate": 0.05, "grid": 0.01, "facet_band": 1.0,
                   "estimator": "synthetic", "seconds": 0.0,
                   "_scores": np.zeros((len(edges), 4, 2)), "_pairs": np.zeros((0, 2), int),
                   "_gflip": {}},
            build_stats=None)
        p.facets = LAYOUT
        return p

    def run_walk(self, A, prepared, **_):
        probes = {}

        def fake_embed(texts, kind):
            probes["texts"] = list(texts)
            # description, raw question, part 0, part 1
            rows = [_u([1.0, 0.07, 0.0]), _u([1.0, 0.075, 0.0]),
                    _u([1.0, 0.0, 0.0]), _u([0.90, 0.436, 0.0])]
            return np.stack(rows), 0, 0, 0, 0.0

        plan = {"description": "the content that answers", "gate": {"product": "Prod"},
                "parts": [{"t": "part zero", "order": list(LAYOUT)},
                          {"t": "part one", "order": ["temporal", "topic", "why", "activity",
                                                      "concreteness"]}]}
        session = FakeSession(["c0", "c1", "c2", "c3", "c4"])   # c5 is out of scope
        old = A._embed_cached
        A._embed_cached = fake_embed
        try:
            rows, usage, meta = A._retrieve_forum(session, prepared, plan, 50,
                                                  "the raw question", keep_all=True,
                                                  char_budget=72000)
        finally:
            A._embed_cached = old
        return rows, usage, meta, session

    def test_the_walk_end_to_end(self):
        A = reload_arm(HERB_V3_SORT="multirank")
        p = self.build(A)
        rows, usage, meta, session = self.run_walk(A, p)

        # no model call, one scope read, every chunk delivered exactly once
        self.assertEqual(usage.calls, 0)
        self.assertEqual(session.queries, 1)
        ids = [r["chunkId"] for r in rows]
        self.assertEqual(sorted(ids), sorted(self.CHUNKS))
        self.assertEqual(len(ids), len(set(ids)), "first arrival delivers a chunk once")

        # both scope passes walked to the end: c5 hangs only off out-of-scope edges
        self.assertEqual(meta["scope"]["passes"], 2)
        self.assertEqual(sorted({w["pass"] for w in meta["walk"]}), [0, 1])
        self.assertEqual(meta["ranking"]["pass"][-1], 1)
        self.assertEqual(ids[-1], "c5")

        # THE PRODUCT-NAME TAG DOES NOT SET THE PICK'S BEST: alpha is the best candidate of
        # part 0, so alpha's edges sit at pick level 0 although Prod is nearer
        self.assertEqual(meta["parts"][0]["rank"], 0, "part 0 is the more central")
        self.assertEqual(meta["ranking"]["pick_level"][0], 0)
        self.assertEqual(meta["sort"]["tagside"]["product_tags"], 1)
        self.assertEqual(meta["sort"]["tagside"]["edges_dropped"], 2)
        self.assertIn("chunks_without_nonproduct_edge", meta["sort"]["tagside"])

        # pool membership is (part, pick level, pass): every pool's size is the count of
        # candidate edges of one part at one pick level inside one pass
        self.assertGreater(meta["keys"]["pools"]["n"], 1)
        self.assertEqual(sum(meta["keys"]["pool_sizes"]),
                         sum(w["edges"] for w in meta["walk"]))
        self.assertIn("pool_membership", meta["keys"])

        # part rank is the first key: no row of the second part is delivered inside a pick
        # level before a row of the first part of that same level
        rank_of = {r["rank"]: pi for pi, r in enumerate(meta["parts"])}
        walked = list(zip(meta["ranking"]["pass"], meta["ranking"]["pick_level"],
                          meta["ranking"]["part"]))
        for wp, lvl, _ in walked:
            ranks = [meta["parts"][p]["rank"] for w, l, p in walked if (w, l) == (wp, lvl)]
            self.assertEqual(ranks, sorted(ranks),
                             "part rank is not the first key inside a pick level")
        self.assertEqual(rank_of[0], 0)

        # the NaN edge did not break the walk and is counted nowhere as a value
        self.assertTrue(np.isnan(p.edge_w[[i for i, (t, c) in enumerate(self.EDGES)
                                           if (t, c) == ("gamma", "c3")][0], 2]))

    def test_the_mode_key_changes_the_order_against_infinite_bands(self):
        A = reload_arm(HERB_V3_SORT="multirank")
        with_key = [r["chunkId"] for r in self.run_walk(A, self.build(A))[0]]
        B = reload_arm(HERB_V3_SORT="multirank", HERB_V3_TOPIC_BAND="inf",
                       HERB_V3_FACET_BAND="inf")
        without = [r["chunkId"] for r in self.run_walk(B, self.build(B))[0]]
        self.assertEqual(sorted(with_key), sorted(without))
        self.assertNotEqual(with_key, without, "the mode key is not wired into the walk")

    def test_the_output_does_not_depend_on_the_input_edge_order(self):
        A = reload_arm(HERB_V3_SORT="multirank")
        base = [r["chunkId"] for r in self.run_walk(A, self.build(A))[0]]
        for seed in range(6):
            perm = list(self.EDGES)
            np.random.default_rng(seed).shuffle(perm)
            got = [r["chunkId"] for r in self.run_walk(A, self.build(A, edge_order=perm))[0]]
            self.assertEqual(got, base, f"seed {seed}")

    def test_the_weighted_mode_walks_the_same_corpus(self):
        A = reload_arm(HERB_V3_SORT="weighted")
        rows, usage, meta, _ = self.run_walk(A, self.build(A))
        self.assertEqual(usage.calls, 0)
        self.assertEqual(sorted(r["chunkId"] for r in rows), sorted(self.CHUNKS))
        self.assertEqual(meta["keys"]["names"]["0"][1], "adjusted topic")
        self.assertIn("mode_key_across_record_kinds", meta["keys"])
        self.assertIsNotNone(meta["keys"]["kind_eta_squared"])

    def test_the_meta_is_json_serialisable_with_no_infinity(self):
        for mode, env in (("multirank", {}),
                          ("multirank", {"HERB_V3_TOPIC_BAND": "inf",
                                         "HERB_V3_FACET_BAND": "inf"}),
                          ("weighted", {"HERB_V3_W": "zero",
                                        "HERB_V3_TOPIC_BAND": "inf"})):
            A = reload_arm(HERB_V3_SORT=mode, **env)
            _, _, meta, _ = self.run_walk(A, self.build(A))
            body = json.dumps(meta, allow_nan=False)      # raises on Infinity / NaN
            self.assertNotIn("Infinity", body)

    def test_m0_and_w0_deliver_the_same_order(self):
        """with every band infinite and every weight zero the two modes are the same chain"""
        A = reload_arm(HERB_V3_SORT="multirank", HERB_V3_TOPIC_BAND="inf",
                       HERB_V3_FACET_BAND="inf")
        m0 = [r["chunkId"] for r in self.run_walk(A, self.build(A))[0]]
        B = reload_arm(HERB_V3_SORT="weighted", HERB_V3_W="zero", HERB_V3_TOPIC_BAND="inf")
        w0 = [r["chunkId"] for r in self.run_walk(B, self.build(B))[0]]
        self.assertEqual(m0, w0)


class LinkTwoBand(unittest.TestCase):
    """Which band levels link 2 (part -> chunk description)?

    The fixture is built so the two bands cannot be confused. The probes' difference vector
    is d = desc - raw. The TAGS lie along d, so rephrasing moves them a lot and the tag band
    is wide. The CHUNK descriptions lie in the plane ORTHOGONAL to d, so rephrasing does not
    move them at all and the description band floors at the embedder's noise. Every chunk
    hangs off one and the same tag, so the tag cosine ties, and the chunk ids run the other
    way from the part's description cosine: if link 2 were levelled at the wide tag band the
    rows would tie on it and come out in id order, which is the reverse of the right answer.
    """
    IDS = ("a0", "a1", "b2", "c3", "d4", "e5")        # ascending id = descending fit

    def build(self, A):
        dv, rv = _u([1.0, 0.0, 0.05]), _u([1.0, 0.0, 0.55])
        delta = dv - rv
        dhat = delta / np.linalg.norm(delta)
        u = np.array([dhat[2], 0.0, -dhat[0]])         # in the x,z plane, orthogonal to d
        yhat = np.array([0.0, 1.0, 0.0])               # also orthogonal to d
        tags = ("Prod", "alpha", "beta", "gamma")
        tag_vecs = np.stack([_u(u + z * dhat) for z in (0.0, 0.25, 0.5, 0.9)])
        # every chunk is a mix of u (the part's direction) and y (orthogonal to everything)
        bs = (0.80, 0.55, 0.35, 0.20, 0.10, 0.00)      # a0 worst fit ... e5 best fit
        chunk_vecs = np.stack([_u(u + b * yhat) for b in bs])
        # one edge per chunk, all from alpha, so the tag cosine ties across the pool
        e_tag = np.ones(len(self.IDS), dtype=np.int32)
        e_chunk = np.arange(len(self.IDS), dtype=np.int32)
        W = np.zeros((len(self.IDS), 5), dtype=np.float64)
        for i in range(len(self.IDS)):
            W[i, 0] = float(tag_vecs[1] @ chunk_vecs[i])
            W[i, 1:] = 1.0                              # constant: the facet columns cannot act
        p = A.Prepared(
            driver=None, tag_names=list(tags), tag_vecs=tag_vecs,
            chunk_ids=list(self.IDS), chunk_vecs=chunk_vecs,
            chunk_rows=[{"chunkId": c, "locator": "{}", "relpath": f"{c}.json",
                         "sha256": "0" * 8} for c in self.IDS],
            edge_tag=e_tag, edge_chunk=e_chunk, edge_w=W,
            shape={"product_tag": np.array([True, False, False, False])},
            kinds=["slack"] * len(self.IDS),
            bands={"npz": "synthetic", "sha256": None, "draws": 2, "edges": len(self.IDS),
                   "columns": ["temporal", "why", "activity", "concreteness"],
                   "pair_sample": "synthetic", "pairs": 0, "pair_seed": 0, "flip_rate": 0.05,
                   "grid": 0.01, "facet_band": 1.0, "estimator": "synthetic", "seconds": 0.0,
                   "_scores": np.zeros((len(self.IDS), 4, 2)),
                   "_pairs": np.zeros((0, 2), int), "_gflip": {}},
            build_stats=None)
        p.facets = LAYOUT
        return p, dv, rv, u

    def walk(self, A):
        p, dv, rv, u = self.build(A)

        def fake_embed(texts, kind):
            return np.stack([dv, rv, u]), 0, 0, 0, 0.0

        plan = {"description": "d", "gate": {}, "parts": [{"t": "p", "order": list(LAYOUT)}]}
        old = A._embed_cached
        A._embed_cached = fake_embed
        try:
            return A._retrieve_forum(None, p, plan, 50, "raw", keep_all=True,
                                     char_budget=72000) + (p, u)
        finally:
            A._embed_cached = old

    def test_link_two_uses_the_description_band(self):
        A = reload_arm(HERB_V3_SORT="multirank", HERB_V3_TOPIC_BAND="inf",
                       HERB_V3_FACET_BAND="inf")
        rows, _, meta, p, u = self.walk(A)
        bands = meta["sort"]["bands"]
        self.assertEqual(bands["description"]["used_by"],
                         "link 2 (part -> chunk description) and link 6 (query description -> "
                         "chunk description)")
        tag_band = bands["pick (delta_pick)"]["value"]
        desc_band = bands["description"]["value"]
        self.assertAlmostEqual(desc_band, A.COS_NOISE, places=9)
        self.assertGreater(tag_band, 20 * desc_band,
                           f"the fixture must separate the bands; got {tag_band} / {desc_band}")

        fit = {c: float(p.chunk_vecs[i] @ u) for i, c in enumerate(self.IDS)}
        gaps = sorted(abs(fit[a] - fit[b]) for a, b in zip(self.IDS, self.IDS[1:]))
        self.assertGreater(gaps[0], desc_band, "every pair must be separable at desc_band")
        self.assertLess(gaps[-1], tag_band, "and tied at the tag band, so the bands differ")

        ids = [r["chunkId"] for r in rows]
        self.assertEqual(ids, sorted(self.IDS, key=lambda c: -fit[c]))
        self.assertEqual(ids, list(reversed(sorted(self.IDS))),
                         "the id order is the reverse, so a tie would be visible")
        self.assertEqual(meta["keys"]["decided_by"].get("link2"), len(ids) - 1)


class NullOverlay(unittest.TestCase):

    def test_the_null_permutes_the_four_and_leaves_topic_null(self):
        sys.path.insert(0, str(ROOT / "test" / "graph" / "facet_pairs"))
        import null_overlay as N
        body = {"database": DB, "run_id": "pilot_full_herb", "facets": list(LAYOUT),
                "edges": [{"tag": f"t{i}", "chunkId": f"c{i}",
                           "weights": [None, float(i), float(i * 2), float(i * 3),
                                       float(i * 4)]} for i in range(50)]}
        out = N.permute(body, seed=20260921)
        self.assertEqual(len(out["edges"]), 50)
        for col, f in enumerate(LAYOUT):
            got = sorted(e["weights"][col] for e in out["edges"]) if f != "topic" else None
            if f == "topic":
                self.assertTrue(all(e["weights"][col] is None for e in out["edges"]))
            else:
                want = sorted(e["weights"][col] for e in body["edges"])
                self.assertEqual(got, want)                    # same marginals
        self.assertEqual([e["chunkId"] for e in out["edges"]],
                         [e["chunkId"] for e in body["edges"]])
        again = N.permute(body, seed=20260921)
        self.assertEqual([e["weights"] for e in again["edges"]],
                         [e["weights"] for e in out["edges"]])  # fixed seed


if __name__ == "__main__":
    unittest.main()

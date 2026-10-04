"""order_facet_layer: validation, groups → ranks, windows, and the arm's rank source."""
import os
import unittest
from unittest.mock import patch

import numpy as np

os.environ.setdefault("NEO4J_DATABASE", "herb-eval-volmax")

from graph import order_facet_layer as ofl
from graph.db import ALL_FACETS
from arms import artefact_v3 as v3


class Validate(unittest.TestCase):

    def test_every_number_once_per_facet(self):
        check = ofl._validate(4, ALL_FACETS)
        good = {f: [[1, 3], [2], [4]] for f in ALL_FACETS}
        check(good)
        for bad in ({f: [[1, 3], [2]] for f in ALL_FACETS},          # 4 missing
                    {f: [[1, 3], [2, 3], [4]] for f in ALL_FACETS},  # 3 twice
                    {f: [[1, 3], [], [2, 4]] for f in ALL_FACETS},   # empty group
                    {f: [[1, 3], [2], [5]] for f in ALL_FACETS},     # out of range
                    {**good, "topic": None}):                         # facet missing
            with self.assertRaises(ValueError):
                check(bad)

    def test_only_the_asked_facets(self):
        check = ofl._validate(2, ("topic",))
        check({"topic": [[2], [1]]})


class Ranks(unittest.TestCase):

    def test_groups_to_ranks(self):
        rank, n = ofl.groups_to_ranks([[2, 0], [1]], 3)
        self.assertEqual(rank, [0, 1, 0])
        self.assertEqual(n, 2)

    def test_windows_slide_from_the_back(self):
        self.assertEqual(ofl.windows(5, 10), [(0, 5)])
        self.assertEqual(ofl.windows(10, 10), [(0, 10)])
        self.assertEqual(ofl.windows(25, 10), [(15, 25), (10, 20), (5, 15), (0, 10)])
        self.assertEqual(ofl.windows(12, 10), [(2, 12), (0, 10)])
        self.assertEqual(ofl.windows(3, 2), [(1, 3), (0, 2)])

    def test_pair_agreement_counts_ties_as_agreement(self):
        a = {"t": {f: ([0, 1, 1], 2) for f in ALL_FACETS}}
        b = {"t": {f: ([0, 2, 2], 3) for f in ALL_FACETS}}
        self.assertEqual(ofl.pair_agreement(a, b)["topic"], 1.0)
        c = {"t": {f: ([1, 0, 0], 2) for f in ALL_FACETS}}
        self.assertAlmostEqual(ofl.pair_agreement(a, c)["topic"], 1 / 3)


def fake_by_length(model, tag, ids, texts, facets, draw=0):
    """a stand-in model: longer text is more relevant on every facet, ties on equal length,
    and it must always be given positions it can return"""
    n = len(texts)
    order = sorted(range(n), key=lambda i: -len(texts[i]))
    groups, cur = [], []
    for i in order:
        if cur and len(texts[cur[-1]]) != len(texts[i]):
            groups.append(cur)
            cur = []
        cur.append(i)
    groups.append(cur)
    return {f: groups for f in facets}, 1, 0, 0


class OrderTag(unittest.TestCase):

    def test_single_chunk_needs_no_call(self):
        with patch.object(ofl, "order_call", side_effect=AssertionError("called")):
            per, calls, _, _ = ofl.order_tag("m", "t", ["c1"], ["x"], 20)
        self.assertEqual(calls, 0)
        self.assertEqual(per["topic"], ([0], 1))

    def test_one_call_keeps_the_models_groups(self):
        with patch.object(ofl, "order_call", fake_by_length):
            per, calls, _, _ = ofl.order_tag("m", "t", ["a", "b", "c", "d"],
                                             ["xx", "xxxx", "xx", "x"], 20)
        self.assertEqual(calls, 1)
        self.assertEqual(per["topic"], ([1, 0, 1, 2], 3))

    def test_windows_bubble_the_strongest_to_the_front(self):
        ids = [f"c{i}" for i in range(12)]
        texts = ["x" * (i + 1) for i in range(12)]          # c11 longest, sits at the back
        with patch.object(ofl, "order_call", fake_by_length):
            per, calls, _, _ = ofl.order_tag("m", "t", ids, texts, 5)
        rank, n = per["topic"]
        self.assertEqual(n, 12)
        self.assertEqual(sorted(rank), list(range(12)))       # a strict order
        self.assertEqual(rank[11], 0)                          # the longest reaches the front
        self.assertEqual(calls, len(ofl.windows(12, 5)) * len(ALL_FACETS))


class ArmRankSource(unittest.TestCase):

    def test_rank_sorts_position_across_tags_then_cosine(self):
        edges = [{"tag": "big", "chunkId": "c1", "w": [0] * 5, "rank": [3, 0, 0, 0, 0]},
                 {"tag": "small", "chunkId": "c2", "w": [0] * 5, "rank": [0, 0, 0, 0, 0]},
                 {"tag": "big", "chunkId": "c3", "w": [0] * 5, "rank": [0, 0, 0, 0, 0]}]
        cos = {"big": 0.9, "small": 0.8}
        order = tuple(ALL_FACETS)
        with patch.object(v3, "FACET_SOURCE", "rank"):
            idx, levels = v3.sort_connections(edges, cos, order, None)
        # c2 and c3 share rank 0 on the first facet and every facet: the tag's cosine decides
        self.assertEqual([edges[i]["chunkId"] for i in idx], ["c3", "c2", "c1"])
        self.assertEqual(levels["topic"], 2)

    def test_weight_source_is_untouched(self):
        edges = [{"tag": "t", "chunkId": "c1", "w": [0.9, 0, 0, 0, 0], "rank": [5, 0, 0, 0, 0]},
                 {"tag": "t", "chunkId": "c2", "w": [0.1, 0, 0, 0, 0], "rank": [0, 0, 0, 0, 0]}]
        with patch.object(v3, "FACET_SOURCE", "weight"), patch.object(v3, "FACET_KEY", "raw"):
            idx, _ = v3.sort_connections(edges, {"t": 1.0}, tuple(ALL_FACETS), None)
        self.assertEqual([edges[i]["chunkId"] for i in idx], ["c1", "c2"])


if __name__ == "__main__":
    unittest.main()

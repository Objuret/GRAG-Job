"""HERB_FACET_SOURCE=file: the five facet values read per EDGE off an overlay.

Every test re-imports the arm with the environment it means, because the source, the file and
the column layout are read at import.
"""
import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

DB = "herb-eval-volmax"
RUN_ID = "pilot_full_herb"
FACETS = ["topic", "temporal", "why", "activity", "concreteness"]


def reload_arm(**env):
    """import artefact_v3 under this environment, restoring the environment afterwards"""
    keys = ("HERB_FACET_SOURCE", "HERB_FACET_FILE", "HERB_FACET_STATS", "NEO4J_DATABASE",
            "HERB_TAG_RUN_ID", "HERB_V3_SORT")
    before = {k: os.environ.get(k) for k in keys}
    for k in keys:
        os.environ.pop(k, None)
    os.environ["NEO4J_DATABASE"] = DB
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


def write_overlay(path, edges, facets=None, database=DB, run_id=RUN_ID):
    Path(path).write_text(json.dumps(
        {"database": database, "run_id": run_id, "facets": facets or FACETS,
         "method": "test", "edges": edges}), encoding="utf-8")
    return str(path)


def prepared_of(v3, tags, chunks, edges, edge_w):
    """a Prepared with the fields the levelling reads and nothing else"""
    return v3.Prepared(
        driver=None, tag_names=list(tags),
        tag_vecs=np.eye(len(tags), 8)[:, :8],
        chunk_ids=list(chunks),
        chunk_vecs=np.eye(len(chunks), 8)[:, :8],
        chunk_rows=[{"chunkId": c, "locator": None, "relpath": "x", "sha256": None}
                    for c in chunks],
        edge_tag=np.asarray([e[0] for e in edges], dtype=np.int32),
        edge_chunk=np.asarray([e[1] for e in edges], dtype=np.int32),
        edge_w=np.asarray(edge_w, dtype=np.float64),
        facets=v3.active_facets())


class TheSourceItself(unittest.TestCase):

    def test_file_without_a_path_raises(self):
        with self.assertRaises(ValueError) as e:
            reload_arm(HERB_FACET_SOURCE="file")
        self.assertIn("HERB_FACET_FILE", str(e.exception))

    def test_file_uses_the_five_ruled_facets(self):
        with tempfile.TemporaryDirectory() as d:
            p = write_overlay(Path(d) / "o.json", [])
            v3 = reload_arm(HERB_FACET_SOURCE="file", HERB_FACET_FILE=p)
        self.assertEqual(list(v3.active_facets()), FACETS)
        self.assertEqual(v3.FACET_SOURCE, "file")

    def test_the_flags_record_the_file_and_its_sha(self):
        with tempfile.TemporaryDirectory() as d:
            p = write_overlay(Path(d) / "o.json", [])
            v3 = reload_arm(HERB_FACET_SOURCE="file", HERB_FACET_FILE=p)
            self.assertEqual(v3.RETRIEVAL_FLAGS["HERB_FACET_FILE"], p)
            self.assertEqual(len(v3.RETRIEVAL_FLAGS["facet_file_sha256"]), 64)
            self.assertIsNone(v3.RETRIEVAL_FLAGS["HERB_FACET_STATS"])


class TheReader(unittest.TestCase):

    def _read(self, edges_in_file, **over):
        with tempfile.TemporaryDirectory() as d:
            p = write_overlay(Path(d) / "o.json", edges_in_file, **over)
            v3 = reload_arm(HERB_FACET_SOURCE="file", HERB_FACET_FILE=p)
            tags, chunks = ["a", "b"], ["c1", "c2"]
            tv = np.array([[1.0, 0.0], [0.6, 0.8]])
            cv = np.array([[1.0, 0.0], [0.0, 1.0]])
            e_tag = np.array([0, 1, 0])
            e_chunk = np.array([0, 0, 1])
            return v3, v3.read_facet_file(tags, chunks, e_tag, e_chunk, tv, cv)

    def test_null_topic_becomes_the_graph_cosine(self):
        rows = [{"tag": "a", "chunkId": "c1", "weights": [None, 0.1, 0.2, 0.3, 0.4]},
                {"tag": "b", "chunkId": "c1", "weights": [None, 0.5, 0.6, 0.7, 0.8]}]
        v3, (W, meta) = self._read(rows)
        self.assertAlmostEqual(W[0, 0], 1.0)       # tag a vs chunk c1
        self.assertAlmostEqual(W[1, 0], 0.6)       # tag b vs chunk c1
        self.assertEqual(meta["edges"], 2)
        self.assertTrue(meta["per_edge"])

    def test_an_edge_the_file_misses_keeps_topic_and_loses_the_four(self):
        rows = [{"tag": "a", "chunkId": "c1", "weights": [None, 0.1, 0.2, 0.3, 0.4]}]
        v3, (W, meta) = self._read(rows)
        self.assertAlmostEqual(W[2, 0], 0.0)       # tag a vs chunk c2
        self.assertTrue(np.isnan(W[2, 1:]).all())
        self.assertEqual(meta["unanchored"], 2)

    def test_another_facet_list_raises(self):
        with self.assertRaises(RuntimeError) as e:
            self._read([], facets=["topic", "entities", "activity", "temporal", "evidence"])
        self.assertIn("facets", str(e.exception))

    def test_another_database_raises(self):
        with self.assertRaises(RuntimeError):
            self._read([], database="some-other-db")

    def test_a_missing_file_raises(self):
        with self.assertRaises(ValueError) as e:
            reload_arm(HERB_FACET_SOURCE="file", HERB_FACET_FILE="no/such/overlay.json")
        self.assertIn("HERB_FACET_FILE", str(e.exception))


def two_tags_per_chunk(values, n_chunks=20):
    """n_chunks chunks, tag a and tag b on each; tag a takes values[0], tag b values[1].
    The clump rule cuts a gap only when chance would not have left it, so the population is
    wide enough for the cut to be made."""
    tags = ["a", "b"]
    chunks = [f"c{i}" for i in range(n_chunks)]
    edges, W = [], []
    for ci in range(n_chunks):
        for ti, v in enumerate(values):
            edges.append((ti, ci))
            W.append([0.5, v, v, v, v])
    return tags, chunks, edges, W


class TheLevelling(unittest.TestCase):
    """two tags on one chunk with different values: per edge under file, one per chunk under
    stats"""

    def _positions(self, source):
        with tempfile.TemporaryDirectory() as d:
            p = write_overlay(Path(d) / "o.json", [])
            v3 = reload_arm(HERB_FACET_SOURCE=source, HERB_FACET_FILE=p,
                            HERB_FACET_STATS=p if source == "stats" else None)
            tags, chunks, edges, W = two_tags_per_chunk([0.10, 0.90])
            prep = prepared_of(v3, tags, chunks, edges, W)
            return v3, v3.facet_positions(prep, None)

    def test_file_keeps_the_two_tags_of_one_chunk_apart(self):
        v3, P = self._positions("file")
        for f in ("temporal", "why", "activity", "concreteness"):
            fi = v3.active_facets().index(f)
            self.assertNotEqual(P[0, fi], P[1, fi], f)
            self.assertLess(P[1, fi], P[0, fi], f)   # 0.90 is the stronger, position 0

    def test_stats_reads_one_value_per_chunk(self):
        v3, P = self._positions("stats")
        for f in ("temporal", "why", "activity", "concreteness"):
            fi = v3.active_facets().index(f)
            self.assertEqual(P[0, fi], P[1, fi], f)

    def test_nan_sorts_last(self):
        with tempfile.TemporaryDirectory() as d:
            p = write_overlay(Path(d) / "o.json", [])
            v3 = reload_arm(HERB_FACET_SOURCE="file", HERB_FACET_FILE=p)
            tags, chunks, edges, W = two_tags_per_chunk([0.10, 0.90])
            W[3] = [0.5, np.nan, np.nan, np.nan, np.nan]
            prep = prepared_of(v3, tags, chunks, edges, W)
            lv = v3.facet_levels(prep.edge_w, "temporal", None, prep.facets)
            self.assertEqual(int(lv[3]), int(max(lv)))
            self.assertGreater(int(lv[3]), int(lv[0]))

    def test_negative_and_zero_are_ordinary_values(self):
        with tempfile.TemporaryDirectory() as d:
            p = write_overlay(Path(d) / "o.json", [])
            v3 = reload_arm(HERB_FACET_SOURCE="file", HERB_FACET_FILE=p)
            tags, chunks, edges, W = two_tags_per_chunk([-3.0, 3.0], n_chunks=15)
            for row in W[::3]:
                row[1] = 0.0
            prep = prepared_of(v3, tags, chunks, edges, W)
            lv = v3.facet_levels(prep.edge_w, "temporal", None, prep.facets)
            at = {W[i][1]: int(lv[i]) for i in range(len(W))}
            self.assertLess(at[3.0], at[0.0])
            self.assertLess(at[0.0], at[-3.0])


class TheOtherSourcesAreUnchanged(unittest.TestCase):

    def test_stats_still_reads_herb_facet_stats(self):
        with tempfile.TemporaryDirectory() as d:
            p = write_overlay(Path(d) / "s.json", [])
            v3 = reload_arm(HERB_FACET_SOURCE="stats", HERB_FACET_STATS=p)
            self.assertEqual(v3.FACET_STATS, p)
            self.assertEqual(v3.RETRIEVAL_FLAGS["HERB_FACET_STATS"], p)
            self.assertIsNone(v3.RETRIEVAL_FLAGS["HERB_FACET_FILE"])
            self.assertEqual(list(v3.active_facets()), FACETS)

    def test_weight_keeps_the_graph_layout(self):
        v3 = reload_arm(HERB_FACET_SOURCE="weight")
        self.assertEqual(list(v3.active_facets()),
                         ["topic", "entities", "activity", "temporal", "evidence"])
        self.assertIsNone(v3.RETRIEVAL_FLAGS["HERB_FACET_FILE"])

    def test_an_unknown_source_still_raises(self):
        with self.assertRaises(ValueError):
            reload_arm(HERB_FACET_SOURCE="nonsense")


class TheRealOverlay(unittest.TestCase):
    """the round-1 overlay on disk, if it has been written"""

    PATH = Path(__file__).resolve().parents[2] / "output" / "facet_pairs" / "rounds" / "round1" / "overlay.json"

    def test_shape_and_count(self):
        if not self.PATH.is_file():
            self.skipTest("round1/overlay.json not written")
        body = json.loads(self.PATH.read_text(encoding="utf-8"))
        self.assertEqual(body["database"], DB)
        self.assertEqual(body["run_id"], RUN_ID)
        self.assertEqual(body["facets"], FACETS)
        self.assertEqual(len(body["edges"]), 61018)
        self.assertEqual(body["edge_count"], 61018)
        for row in body["edges"][:200]:
            self.assertIsNone(row["weights"][0])
            self.assertTrue(all(np.isfinite(v) for v in row["weights"][1:]))


if __name__ == "__main__":
    unittest.main()

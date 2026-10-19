"""Before any write: what the arm would read if the graph's tags were the query-mode vectors.

Two things, on the graph as it stands (read only) and the side file of query-mode tag vectors:
  topic   per edge, the stored topic against cos(query-mode tag vector, the graph's chunk
          description vector), and how the order of topic moves per tag and per chunk;
  walk    for the made-up question's query tags (output/walkthrough/20261005T040000Z), what the
          walk's first step sees in each mode: the closest graph tag, the middle and the spread
          of the closeness over the eligible graph tags, and how many graph tags stand at or
          above the same-thing level.

    .venv/Scripts/python.exe output/research/2026-10-08-query-mode-tags/what_the_walk_would_see.py

No write to the graph, no model call, no test question. Also saves the graph's stored tag vectors
to output/tag_vector_backup/ (ids, matrix, sha256), so they exist outside the graph.
"""
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np

print("what_the_walk_would_see: loading the arm's readers and neo4j", flush=True)

REPO = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]

from scipy.stats import spearmanr  # noqa: E402

from arms import artefact_v4 as A  # noqa: E402
from arms.artefact_facet_joint import _unit  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from graph.db import _driver, _readable  # noqa: E402
from harness import embed  # noqa: E402

QUERY_FILE = REPO / "output/embed_local/20261008_rev113abe4acafa_float32/tags_query.npz"
WALKTHROUGH = REPO / "output/walkthrough/20261005T040000Z/walkthrough.json"
BACKUP = REPO / "output/tag_vector_backup/herb-eval-volmax__as-stored-20261008"


def five(values):
    q = np.percentile(np.asarray(values, dtype=np.float64), [0, 25, 50, 75, 100])
    return f"lowest {q[0]:.3f}  25% {q[1]:.3f}  middle {q[2]:.3f}  75% {q[3]:.3f}  highest {q[4]:.3f}"


t0 = time.perf_counter()
driver = _driver()
try:
    with driver.session(database=A.DATABASE, default_access_mode="READ") as s:
        every_tag = [dict(r) for r in s.run(
            "MATCH (t:Tag) WHERE t.emb IS NOT NULL RETURN t.name AS id, t.emb AS vector ORDER BY id")]
        tag_rows = [dict(r) for r in s.run(A.TAG_CYPHER, run=A.RUN_ID)]
        chunk_rows = [dict(r) for r in s.run(
            "MATCH (c:Chunk) WHERE c.desc_emb IS NOT NULL AND EXISTS { "
            "MATCH (c)-[r:HAS_TAG]->() WHERE r.run_id = $run } AND (c)-[:product]->() "
            "RETURN c.chunk_id AS chunkId, c.desc_emb AS vector ORDER BY chunkId", run=A.RUN_ID)]
        edge_rows = [dict(r) for r in s.run(A.EDGE_CYPHER, run=A.RUN_ID)]
        products = [r["name"] for r in s.run(A.PRODUCT_CYPHER)]
finally:
    driver.close()
print(f"graph {A.DATABASE}: {len(every_tag)} tags with a vector, {len(tag_rows)} in the pool, "
      f"{len(chunk_rows)} chunks, {len(edge_rows)} edges  ({time.perf_counter() - t0:.0f}s)", flush=True)

# The graph's stored tag vectors, kept outside the graph.
BACKUP.mkdir(parents=True, exist_ok=True)
stored_ids = [r["id"] for r in every_tag]
stored = np.asarray([r["vector"] for r in every_tag], dtype=np.float32)
np.savez(BACKUP / "tag_emb.npz", ids=np.array(stored_ids, dtype=object), matrix=stored)
kept = {"database": A.DATABASE, "property": "Tag.emb", "n": len(stored_ids),
        "matrix_shape": list(stored.shape), "matrix_dtype": str(stored.dtype),
        "matrix_sha256": hashlib.sha256(stored.tobytes()).hexdigest(),
        "ids_sha256": hashlib.sha256("\n".join(stored_ids).encode("utf-8")).hexdigest(),
        "file_sha256": hashlib.sha256((BACKUP / "tag_emb.npz").read_bytes()).hexdigest(),
        "read_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
(BACKUP / "manifest.json").write_text(json.dumps(kept, indent=2), encoding="utf-8")
print(f"the graph's stored tag vectors saved: {BACKUP.relative_to(REPO).as_posix()}/tag_emb.npz  "
      f"{stored.shape}  matrix sha256 {kept['matrix_sha256'][:16]}", flush=True)

side = np.load(QUERY_FILE, allow_pickle=True)
side_at = {str(name): i for i, name in enumerate(side["ids"])}
if sorted(side_at) != sorted(stored_ids):
    raise SystemExit("the side file and the graph do not hold the same tags")

graph_tags = [r["id"] for r in tag_rows]
chunk_ids = [r["chunkId"] for r in chunk_rows]
at = {name: i for i, name in enumerate(graph_tags)}
ci = {name: i for i, name in enumerate(chunk_ids)}
as_stored = _unit(np.asarray([r["vector"] for r in tag_rows], dtype=np.float32))
in_query = _unit(np.asarray(side["matrix"][[side_at[t] for t in graph_tags]], dtype=np.float32))
chunk_vectors = _unit(np.asarray([r["vector"] for r in chunk_rows], dtype=np.float32))
edge_tag = np.array([at[r["tag"]] for r in edge_rows], dtype=np.int64)
edge_chunk = np.array([ci[r["chunkId"]] for r in edge_rows], dtype=np.int64)
topic_stored = np.array([r["values"][0] for r in edge_rows], dtype=np.float64)
topic_again = np.einsum("ij,ij->i", as_stored[edge_tag], chunk_vectors[edge_chunk])
topic_query = np.einsum("ij,ij->i", in_query[edge_tag], chunk_vectors[edge_chunk])

print("\n== topic on the edges ==")
print(f"stored topic against the cosine of the stored vectors, largest difference: "
      f"{np.abs(topic_stored - topic_again).max():.2e}")
print(f"stored (tag behind \"passage: \"):   {five(topic_stored)}")
print(f"made again (tag behind \"query: \"): {five(topic_query)}")
print(f"over all {topic_stored.size} edges, rank agreement of the two (Spearman): "
      f"{spearmanr(topic_stored, topic_query)[0]:.3f}")
for name, key, other in (("tag", edge_tag, edge_chunk), ("chunk", edge_chunk, edge_tag)):
    order = np.argsort(key, kind="stable")
    cuts = np.flatnonzero(np.diff(key[order])) + 1
    groups = [g for g in np.split(order, cuts) if g.size > 1]
    rho = np.array([spearmanr(topic_stored[g], topic_query[g])[0] for g in groups])
    rho = rho[np.isfinite(rho)]
    same_top = sum(int(np.argmax(topic_stored[g]) == np.argmax(topic_query[g])) for g in groups)
    print(f"per {name} with more than one edge ({len(groups)}): rank agreement of its edges' "
          f"topic {five(rho)}; its highest-topic edge is the same one for "
          f"{100.0 * same_top / len(groups):.1f}%")

print("\n== the walk's first step for the made-up question, per query tag ==")
walk = json.loads(WALKTHROUGH.read_text(encoding="utf-8"))
texts = [t["text"] for t in walk["query_tags"]]
print(f"question: {walk['question']}")
folded = {p.casefold() for p in products}
eligible = np.array([t.casefold() not in folded for t in graph_tags], dtype=bool)
readable = [_readable(t) for t in graph_tags]
modes = {"as the graph stands (stored vectors, query tags behind \"passage: \")": (as_stored, "passage"),
         "with the query-mode vectors (query tags behind \"query: \")": (in_query, "query")}
edges_of = np.bincount(edge_tag, minlength=len(graph_tags))
for label, (vectors, role) in modes.items():
    same = WK.same_thing_level(readable, vectors, eligible)
    mat = _unit(np.asarray(embed._embed([t.strip() for t in texts], role, bar=False)[0], dtype=np.float32))
    cosines = mat.astype(np.float64) @ vectors.astype(np.float64).T
    print(f"\n-- {label} --")
    print(f"the same-thing level over the pool's eligible tags: {same['level']:.4f} "
          f"({same['pairs']} pairs, middle {same['median']:.3f})")
    none = 0
    for text, row in zip(texts, cosines):
        z, middle, spread = WK.standing(row[eligible])
        best = int(np.flatnonzero(eligible)[int(np.argmax(row[eligible]))])
        picked = np.flatnonzero(eligible & (row >= same["level"]))
        none += int(picked.size == 0)
        print(f"  {text!r}: closest {graph_tags[best]!r} {row[best]:.3f}; middle {middle:.3f}, "
              f"spread {spread:.4f}; the closest stands {float(z.max()):.1f} spreads above the "
              f"middle; graph tags at or above the level {picked.size}, their edges "
              f"{int(edges_of[picked].sum())}")
    print(f"  query tags with no graph tag at or above the level: {none} of {len(texts)}")
print("done", flush=True)

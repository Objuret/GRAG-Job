"""artefact_v3GRAG — the graph-shape edition, 2026-09-09. *"do a separate artefact trying this in full"*.

The chain is query → tag → chunk → file, every link ordered for this query. What artefact_v3GRAG adds to
v3 is a region wide enough to order inside, and the shape of the graph as sort keys:

1. REGION. Per query part, every connection's fit (FIT_RULE over tag cosine and description
   cosine, as v3), levelled at the embedder's noise width (HERB_V3GRAG_REGION=noise, v3's rule).
   The KDE-basin rule (=basin) was the first build and is measured not to be a region (see the
   09-09 sweep in CLAUDE.md). Levels open nearest first until the budget fills; each opened
   level is sorted as one list. What a region should be is his open question, not settled here.
2. FILE. Inside the region a chunk stands with its file: the key is how many region chunks its
   file holds (cluster hypothesis; Callan 1994, Liu & Croft 2002, Diaz 2005). A count, no weight.
3. TAG GRAPH. Region chunks sharing a tag are neighbours; the key is a chunk's degree among
   region chunks (Kurland & Lee 2005 with degree in place of PageRank — no damping constant).
4. FACETS. The five statistics in the part's facet order, levelled as in v3.
5. Then tag cosine, then chunk id.
6. FIELDS. Product / section / years named by the question are scope: the in-scope pass
   first, as v3 (SCOPE_RULE). Hard-or-soft is his open question, untouched here.
7. ENTITIES. The question's named things (employee id, product, channel from the gate; a
   part that is a Company name) seed a breadth-first walk over the entity layer (Employee,
   Channel, Product, File, Customer, Company, manages); a chunk's key is its hop distance from
   the nearest seed (HippoRAG's mechanism with hops in place of PageRank probability).
   Unreachable sorts last; with no seed the key is constant.

Key order inside a basin: entity hops, file count, tag degree, facets, tag cosine, chunk id.
HERB_V3GRAG_KEYS switches shape keys on and off for the on/off measurement (default all on).
Facet source, interpreter (order only) and everything not named above are artefact_v3's.
"""
from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from typing import Optional

import numpy as np

from harness import chat
from harness.contract import ArmOutput, ModelUsage, unpack_generation
from arms.artefact_v2 import (
    DATABASE, DATASET_ID, INTERPRET_MODEL, NEUTRAL_FACETS, NO_REVIEW, RAW_QUESTION,
    _budget_contexts, _embed_cached, _parse_gate, _qid_text, _readable, _resolve_chunk,
    _sufficient_cut, _unit,
)
from arms import artefact_v3 as v3
from arms.artefact_v3 import (
    TEXT_SOURCES, FIT_RULE, MIN_LEVELS, SCOPE_RULE, Prepared, connection_fit,
    facet_levels, facet_order, levels, scope_chunks, _interpret_order_cached, _interpret_cached,
)

# what this arm sorts on, which is not always what v3 sorts on: v3's per-edge source reads the
# four statistics on the tag's own sentences inside _retrieve_concept, a walk this arm does not
# run — here the layer is the chunk-level statistics file, so the source recorded is stats.
FACET_SOURCE = "stats" if v3.FACET_SOURCE == "edge" else v3.FACET_SOURCE

ALL_KEYS = ("entity", "file", "tag", "facets")
_keys_env = os.environ.get("HERB_V3GRAG_KEYS")
KEYS = tuple(k for k in (",".join(ALL_KEYS) if _keys_env is None else _keys_env).split(",") if k)
FIT_MODE = os.environ.get("HERB_V3GRAG_FIT") or "connection"   # connection (v3's FIT_RULE) | desc
                            # desc: the chunk description's cosine alone — no tag in the fit, no tag
                            # in the tiebreak; "what do we get using only graph structure and chunk
                            # desc" (his question, 09-09)
for _k in KEYS:
    if _k not in ALL_KEYS:
        raise ValueError(f"HERB_V3GRAG_KEYS names {_k!r}; the keys are {ALL_KEYS}")
REGION_RULE = os.environ.get("HERB_V3GRAG_REGION") or "noise"
    # noise: v3's fit levels at the embedder's noise width (the default since the review of 09-09)
    # basin: KDE valleys of the fit — measured 09-09 to cut 6 / 10 / 13 / 106 / 30 / 61,863 rows on a
    # real part; the valleys are the sparse tail, not a region. Kept for the record, not a choice.

RETRIEVAL_FLAGS = {
    # the concept walk's knobs say nothing about this arm's run: it grows its own region over
    # the entity layer and never reads the [:channel] shape, the file adjacency or the
    # concentration half, so they stay out of this manifest
    **{key: val for key, val in v3.RETRIEVAL_FLAGS.items()
       if key not in ("HERB_V3_REGION", "HERB_V3_TAGREL", "HERB_V3_LOCALITY")},
    "HERB_FACET_SOURCE": FACET_SOURCE,
    "sentence_facets_sha256": None,
    "HERB_V3GRAG_KEYS": list(KEYS),
    "HERB_V3GRAG_REGION": REGION_RULE,
    "HERB_V3GRAG_FIT": FIT_MODE,
    "concept": "2026-09-09: region = top density basin of the fit; inside it the keys are entity "
               "hops, file count in region, tag degree in region, the five facets in the part's "
               "order, tag cosine, chunk id",
}

_ENTITY_CYPHER = {
    "chunk_product": "MATCH (c:Chunk)-[:product]->(p:Product) RETURN c.chunk_id AS a, p.name AS b",
    "chunk_channel": "MATCH (c:Chunk)-[:channel]->(ch:Channel) RETURN c.chunk_id AS a, ch.id AS b",
    "chunk_file": "MATCH (c:Chunk)<-[:HAS_CHUNK]-(f:File) RETURN c.chunk_id AS a, f.file_id AS b",
    "emp_channel": "MATCH (e:Employee)-[:slack]->(ch:Channel) RETURN e.eid AS a, ch.id AS b",
    "emp_product": "MATCH (e:Employee)-[:documents|meeting_transcripts]->(p:Product) RETURN e.eid AS a, p.name AS b",
    "file_emp": "MATCH (f:File)-[:employee]->(e:Employee) RETURN f.file_id AS a, e.eid AS b",
    "emp_manages": "MATCH (e:Employee)-[:manages]->(m:Employee) RETURN e.eid AS a, m.eid AS b",
    "file_company": "MATCH (f:File)-[:customer]->(:Customer)-[:company]->(co:Company) RETURN f.file_id AS a, co.value AS b",
    "file_company2": "MATCH (f:File)-[:company]->(co:Company) RETURN f.file_id AS a, co.value AS b",
    "file_product": "MATCH (f:File)-[:product]->(p:Product) RETURN f.file_id AS a, p.name AS b",
    "file_channel": "MATCH (f:File)-[:channel]->(ch:Channel) RETURN f.file_id AS a, ch.id AS b",
    "product_channel": "MATCH (p:Product)-[:slack]->(ch:Channel) RETURN p.name AS a, ch.id AS b",
}
_PREFIX = {"chunk": "chunk:", "emp": "emp:", "file": "file:", "product": "prod:", "channel": "chan:",
           "company": "comp:", "manages": "emp:"}


class Shape:
    """the entity layer as an undirected adjacency over typed node ids, plus chunk → file"""

    def __init__(self):
        self.adj: dict = defaultdict(set)
        self.chunk_file: dict = {}
        self.companies: dict = {}
        self.products: dict = {}
        self.channels: set = set()

    def link(self, a: str, b: str) -> None:
        self.adj[a].add(b)
        self.adj[b].add(a)

    def hops(self, seeds: list, chunk_ids: list) -> np.ndarray:
        """breadth-first hop distance from the nearest seed to every chunk; -1 unreachable"""
        dist = {s: 0 for s in seeds if s in self.adj}
        q = deque(dist)
        while q:
            u = q.popleft()
            for w in self.adj[u]:
                if w not in dist:
                    dist[w] = dist[u] + 1
                    q.append(w)
        return np.array([dist.get("chunk:" + c, -1) for c in chunk_ids], dtype=np.int64)


def load_shape(driver) -> Shape:
    t0 = time.perf_counter()
    sh = Shape()
    with driver.session(database=DATABASE) as s:
        for name, cypher in _ENTITY_CYPHER.items():
            left, right = name.split("_", 1)
            right = {"company2": "company", "emp": "emp"}.get(right, right)
            pa, pb = _PREFIX[left], _PREFIX[right]
            n = 0
            for r in s.run(cypher):
                if r["a"] is None or r["b"] is None:
                    continue
                a, b = pa + str(r["a"]), pb + str(r["b"])
                sh.link(a, b)
                n += 1
                if name == "chunk_file":
                    sh.chunk_file[str(r["a"])] = str(r["b"])
                elif right == "company":
                    sh.companies[str(r["b"]).casefold()] = b
                elif right == "product":
                    sh.products[str(r["b"]).casefold()] = b
                elif right == "channel":
                    sh.channels.add(b)
            print(f"artefact_v3GRAG:   shape {name}: {n} edges", flush=True)
    print(f"artefact_v3GRAG: shape loaded, {len(sh.adj)} nodes ({time.perf_counter() - t0:.1f}s)", flush=True)
    return sh


_SHAPE: Optional[Shape] = None


def prepare_over_corpus(corpus) -> Prepared:
    global _SHAPE
    prepared = v3.prepare_over_corpus(corpus, concept_walk=False)
    _SHAPE = load_shape(prepared.driver)
    missing = sum(1 for c in prepared.chunk_ids if c not in _SHAPE.chunk_file)
    if missing:
        raise RuntimeError(f"{missing} chunks in memory have no HAS_CHUNK file in the shape")
    return prepared


def seeds_for(plan: dict, parts: list, shape: Shape) -> list:
    """the question's named things: gate fields, and parts that are a Company or Product name"""
    gate = _parse_gate(plan.get("gate"))
    out = []
    if gate.get("employee_id"):
        out.append("emp:" + gate["employee_id"])
    if gate.get("product"):
        out.append(shape.products.get(gate["product"].casefold(), "prod:" + gate["product"]))
    if gate.get("channel"):
        out.append("chan:" + gate["channel"])
    for p in parts:
        key = _readable(p["t"]).casefold()
        if key in shape.companies:
            out.append(shape.companies[key])
        elif key in shape.products:
            out.append(shape.products[key])
    seen, uniq = set(), []
    for s in out:
        if s not in seen:
            seen.add(s)
            uniq.append(s)
    return uniq


def region_levels(conn: np.ndarray) -> np.ndarray:
    if REGION_RULE == "noise":
        return v3.levels_cos(conn)
    return levels(conn)


def sort_region(rows: list, part_cos: dict, order: tuple, hops: np.ndarray,
                shape: Shape, layout: tuple) -> tuple:
    """one opened basin of one part, sorted by the artefact_v3GRAG key; returns indices and level counts"""
    n = len(rows)
    chunk_of = [r["chunkId"] for r in rows]
    region_chunks = set(chunk_of)
    # file count in region
    file_count: dict = defaultdict(int)
    for c in region_chunks:
        file_count[shape.chunk_file[c]] += 1
    fkey = np.array([-file_count[shape.chunk_file[c]] for c in chunk_of], dtype=np.int64)
    # tag degree in region: chunks sharing a tag, counted once per chunk pair
    tag_chunks: dict = defaultdict(set)
    for r in rows:
        tag_chunks[r["tag"]].add(r["chunkId"])
    neighbours: dict = defaultdict(set)
    for t, cs in tag_chunks.items():
        for c in cs:
            neighbours[c] |= cs
    dkey = np.array([-(len(neighbours[c]) - 1) for c in chunk_of], dtype=np.int64)
    # entity hops: -1 unreachable → after every reachable value
    hkey = np.where(hops < 0, hops.max() + 1 if hops.size else 0, hops)
    W = np.asarray([r["w"] for r in rows], dtype=np.float64)
    lv = {f: facet_levels(W, f, None, layout) for f in order} if "facets" in KEYS else {}
    zero = np.zeros(n, dtype=np.int64)
    cols = [hkey if "entity" in KEYS else zero,
            fkey if "file" in KEYS else zero,
            dkey if "tag" in KEYS else zero]
    idx = sorted(range(n), key=lambda i: tuple(int(c[i]) for c in cols)
                 + tuple(int(lv[f][i]) for f in order if f in lv)
                 + ((0.0 if FIT_MODE == "desc" else -part_cos[rows[i]["tag"]]), rows[i]["chunkId"]))
    counts = {"entity": int(len(np.unique(hkey))), "file": int(len(np.unique(fkey))),
              "tag": int(len(np.unique(dkey)))}
    counts.update({f: int(len(np.unique(lv[f]))) for f in lv})
    return idx, counts


def _retrieve(session, prepared: Prepared, plan: dict, k: int, question: str,
              keep_all: bool = False, char_budget: Optional[int] = None,
              doc_cache: Optional[dict] = None) -> tuple:
    shape = _SHAPE
    if char_budget is None and k <= 0:
        raise ValueError("k must be positive when no character budget is set")
    parts = list(plan["parts"])
    probes = [_readable(p["t"]) for p in parts]
    if RAW_QUESTION:
        parts.append({"t": question, "facets": dict(NEUTRAL_FACETS), "order": list(prepared.facets)})
        probes.append(question)
    qmat, calls, tok_in, tok_out, secs = _embed_cached(probes, "query")
    usage = ModelUsage(calls=calls, tokens_in=tok_in, tokens_out=tok_out, time_s=secs)

    e_tag, e_chunk = prepared.edge_tag, prepared.edge_chunk
    seeds = seeds_for(plan, parts, shape) if "entity" in KEYS else []
    hops_all = shape.hops(seeds, prepared.chunk_ids) if seeds else np.full(len(prepared.chunk_ids), -1, dtype=np.int64)
    reachable = int((hops_all >= 0).sum()) if seeds else 0

    part_fit, part_cos, part_order, level_log = [], [], [], []
    for part, row in zip(parts, qmat):
        vec = _unit(np.asarray([float(x) for x in row], dtype=np.float64))
        tag_sims = prepared.tag_vecs @ vec
        desc_sims = prepared.chunk_vecs @ vec
        conn = desc_sims[e_chunk] if FIT_MODE == "desc" else connection_fit(tag_sims[e_tag], desc_sims[e_chunk])
        fit = region_levels(conn)
        part_fit.append(fit)
        part_cos.append({n: float(x) for n, x in zip(prepared.tag_names, tag_sims)})
        part_order.append(facet_order(part, prepared.facets))
        sizes = np.bincount(fit)
        level_log.append({"part": part["t"], "region_rule": REGION_RULE,
                          "basins": int(fit.max()) + 1, "basin_sizes": [int(x) for x in sizes[:6]],
                          "facet_order": list(part_order[-1])})

    reached: set = set()
    payload: dict = {}
    walk = []
    part_rows = [[] for _ in parts]

    def open_basin(pi: int, L: int, mask: np.ndarray, walk_pass: int) -> None:
        at = np.flatnonzero((part_fit[pi] == L) & mask)
        if at.size == 0:
            return
        rows = [{"tag": prepared.tag_names[e_tag[j]], **prepared.chunk_rows[e_chunk[j]],
                 "w": prepared.edge_w[j]} for j in at]
        hops = hops_all[e_chunk[at]]
        idx, counts = sort_region(rows, part_cos[pi], part_order[pi], hops, shape, prepared.facets)
        fresh = 0
        for j in idx:
            row = rows[j]
            cid = row["chunkId"]
            if cid not in reached:
                fresh += 1
                reached.add(cid)
            part_rows[pi].append({"chunkId": cid, "locator": row["locator"], "relpath": row["relpath"],
                                  "sha256": row["sha256"], "tag": row["tag"], "fit": L})
            payload.setdefault(cid, {f: row[f] for f in ("chunkId", "locator", "relpath", "sha256")})
        walk.append({"part": parts[pi]["t"], "basin": L, "pass": walk_pass,
                     "rows": len(rows), "chunks": len({r["chunkId"] for r in rows}),
                     "new": fresh, "key_levels": counts})

    def merged() -> list:
        out, seen = [], set()
        longest = max((len(r) for r in part_rows), default=0)
        for r in range(longest):
            for pr in part_rows:
                if r < len(pr) and pr[r]["chunkId"] not in seen:
                    seen.add(pr[r]["chunkId"])
                    out.append(pr[r])
        return out

    chars_of: dict = {}
    cache = doc_cache if doc_cache is not None else {}

    def enough() -> bool:
        if char_budget is None:
            return len(reached) >= k
        total = 0
        for row in merged():
            cid = row["chunkId"]
            if cid not in chars_of:
                chars_of[cid] = len(_resolve_chunk(row, cache)[0])
            total += chars_of[cid]
            if total >= char_budget:
                return True
        return False

    in_scope = np.ones(len(e_chunk), dtype=bool)
    scope_ids, scope_named = (set(), [])
    if SCOPE_RULE != "off":
        scope_ids, scope_named = scope_chunks(session, _parse_gate(plan.get("gate")))
        if scope_ids:
            chunk_ok = np.fromiter((c in scope_ids for c in prepared.chunk_ids), dtype=bool,
                                   count=len(prepared.chunk_ids))
            in_scope = chunk_ok[e_chunk]
    if not in_scope.any():
        in_scope = np.ones(len(e_chunk), dtype=bool)
        scope_named = []
    every = np.ones(len(e_chunk), dtype=bool)
    passes = [every] if not scope_named else ([in_scope] if SCOPE_RULE == "cut" else [in_scope, ~in_scope])

    widening = sorted((L, pi) for pi in range(len(parts)) for L in range(1, int(part_fit[pi].max()) + 1))
    for walk_pass, mask in enumerate(passes):
        if walk_pass and enough():
            break
        for pi in range(len(parts)):
            open_basin(pi, 0, mask, walk_pass)
        for L, pi in widening:
            if L >= MIN_LEVELS and enough():
                break
            open_basin(pi, L, mask, walk_pass)
    if not reached:
        raise RuntimeError("no tag of any part reaches a chunk")

    rows = merged()
    if not keep_all:
        rows = rows[:k]
    selected = [{**payload[row["chunkId"]], "tag": row["tag"], "fit": row["fit"]} for row in rows]
    meta = {
        "plan": {key: val for key, val in plan.items() if not key.startswith("_")},
        "parts": level_log,
        "walk": walk,
        "seeds": seeds, "reachable_chunks": reachable,
        "keys": list(KEYS),
        "retrieved": len(selected),
        "connections": {"chunks": len(reached), "rows_per_part": [len(r) for r in part_rows]},
        "scope": {"rule": SCOPE_RULE, "named": scope_named, "chunks": len(scope_ids)},
        "facet_layer": {"source": FACET_SOURCE, "overlay": prepared.overlay},
        "ranking": {"chunk_ids": [row["chunkId"] for row in rows]},
    }
    return selected, usage, meta


def answer_one_question(question, prepared: Prepared, generate, k: int = 50,
                        char_budget: Optional[int] = None) -> ArmOutput:
    _, text = _qid_text(question)
    chat.reset_timing()
    t0 = time.perf_counter()
    if FACET_SOURCE in TEXT_SOURCES:
        plan, interp_calls, interp_in, interp_out, interp_time = _interpret_order_cached(text, INTERPRET_MODEL)
    else:
        plan, interp_calls, interp_in, interp_out, interp_time = _interpret_cached(text, INTERPRET_MODEL)
    doc_cache: dict = {}
    with prepared.driver.session(database=DATABASE) as session:
        rows, ground_usage, meta = _retrieve(session, prepared, plan, k, text,
                                             keep_all=char_budget is not None,
                                             char_budget=char_budget, doc_cache=doc_cache)
    meta["interpreter"] = {"model": INTERPRET_MODEL, "backend": "claude-cli"}
    retrieve_wall = time.perf_counter() - t0
    rev_calls = rev_in = rev_out = 0
    rev_time = 0.0
    if char_budget is not None:
        contexts, chunk_id_lists, context_ids, meta["char_budget"] = _budget_contexts(rows, char_budget, doc_cache)
    else:
        contexts, context_ids, chunk_id_lists = [], [], []
        seen: set = set()
        for row in rows:
            chunk_text, ids = _resolve_chunk(row, doc_cache)
            contexts.append(chunk_text)
            chunk_id_lists.append(ids)
            for aid in ids:
                if aid not in seen:
                    seen.add(aid)
                    context_ids.append(aid)
        if NO_REVIEW:
            kept, review_log = len(contexts), []
        else:
            kept, review_log, rev_calls, rev_in, rev_out, rev_time = _sufficient_cut(text, contexts)
        contexts = contexts[:kept]
        chunk_id_lists = chunk_id_lists[:kept]
        seen = set()
        context_ids = []
        for ids in chunk_id_lists:
            for aid in ids:
                if aid not in seen:
                    seen.add(aid)
                    context_ids.append(aid)
        meta["review"] = {"kept": kept, "rounds": review_log}
    meta["returned"] = len(contexts)
    meta["chunk_ids"] = chunk_id_lists
    search_time_s = max(0.0, retrieve_wall - interp_time - ground_usage.time_s)
    retrieval_usage = ModelUsage(
        calls=interp_calls + ground_usage.calls + rev_calls,
        tokens_in=interp_in + ground_usage.tokens_in + rev_in,
        tokens_out=interp_out + ground_usage.tokens_out + rev_out,
        time_s=interp_time + ground_usage.time_s + rev_time,
        **chat.take_timing())
    if generate is None:
        answer, gen = "", ModelUsage()
    else:
        g0 = time.perf_counter()
        result = generate(text, contexts)
        answer, gen = unpack_generation(result, time.perf_counter() - g0)
    return ArmOutput(answer=answer, contexts=contexts, context_ids=context_ids,
                     search_time_s=search_time_s, generator=gen,
                     retrieval=retrieval_usage, meta=meta)

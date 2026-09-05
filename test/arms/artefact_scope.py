from __future__ import annotations

print("artefact_scope: the tags say which chunks belong, the stated product says "
      "where to look, the description says in what order — each tag's local "
      "enrichment against the query's own distance null, the product file, "
      "description cosine within tiers; loading numpy, scipy and the shared "
      "graph plumbing …", flush=True)

import json
import math
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Optional

import numpy as np
from scipy.special import logsumexp, ndtri
from scipy.stats import t as student_t

from harness import nim
from harness.contract import ArmOutput, BuildStats, ModelUsage, unpack_generation
from arms.artefact_composed import (
    RANK_SCORE_DP, _PROBES, _parts, _pointer, _spread,
)
from arms.artefact_v2 import (
    DATABASE, DATASET_ID, FRESH_INTERP, INTERPRET_MODEL, RAW_QUESTION, RUN_ID,
    _DESC_POOL_MATCH, _EXCLUDED_PARAM, _TAG_POOL_MATCH, _budget_contexts,
    _driver, _embed_cached, _interpret_cached, _qid_text, _resolve_chunk, _unit,
)
from harness.embed import EMBED_MODEL
from harness.progress import progress


MADK = 1.0 / ndtri(0.75)

KERNEL_TAU = np.finfo(np.float64).eps

DENSITY_BLOCK = 256

MATCH_EVIDENCE = np.log(2.0)

RETRIEVAL_FLAGS = {
    "HERB_RAW_QUESTION": RAW_QUESTION,
    "HERB_FRESH_INTERP": FRESH_INTERP,
}


_TAGS_RETURN = "RETURN t.name AS name, t.emb AS emb"

_CHUNKS_RETURN = """
RETURN c.chunk_id AS chunkId, c.locator_json AS locator,
       f.rel_path AS relpath, f.sha256 AS sha256, c.desc_emb AS emb
"""

_NO_DESC_MATCH = """
MATCH (f:File)-[:HAS_CHUNK]->(c:Chunk)
WHERE coalesce(c.empty, false) = false
  AND ($datasetId IS NULL OR f.dataset_id = $datasetId)
  AND NOT (coalesce(c.section, "") IN $excludedSections)
  AND c.desc_emb IS NULL
"""

_EDGES_MATCH = _DESC_POOL_MATCH + """
MATCH (c)-[r:HAS_TAG]->(t:Tag)
WHERE r.run_id = $runId AND t.emb IS NOT NULL
"""
_EDGES_RETURN = "RETURN c.chunk_id AS chunkId, t.name AS name"


@dataclass
class Prepared:
    tag_names: list
    tag_emb: np.ndarray
    chunk_ids: list
    pointers: list
    rel_paths: list
    desc_emb: np.ndarray
    edge_chunk: np.ndarray
    edge_tag: np.ndarray
    build_stats: Optional[BuildStats] = None


def _pull(session, match: str, returning: str, params: dict, desc: str,
          unit: str) -> list:
    total = session.run(match + "RETURN count(*) AS n", **params).single()["n"]
    rows = [dict(rec) for rec in progress(session.run(match + returning, **params),
                                          desc=desc, unit=unit, total=total)]
    if len(rows) != total:
        raise RuntimeError(
            f"{desc} returned {len(rows)} row(s) against a count of {total} — "
            f"the graph changed under the pull")
    return rows


def prepare_over_corpus(corpus) -> Prepared:
    t0 = time.perf_counter()
    print(f"artefact_scope: opening {DATABASE} …", flush=True)
    drv = _driver()
    try:
        with drv.session(database=DATABASE) as s:
            s.run("RETURN 1").consume()
            population = {"datasetId": DATASET_ID, "excludedSections": _EXCLUDED_PARAM}
            no_desc = s.run(_NO_DESC_MATCH + "RETURN count(*) AS n",
                            **population).single()["n"]
            if no_desc:
                raise RuntimeError(
                    f"{no_desc} non-empty chunk(s) of {DATASET_ID!r} outside the "
                    f"excluded sections carry no desc_emb in {DATABASE!r} — the "
                    f"arm orders every retrievable chunk by its description")
            tags = _pull(s, _TAG_POOL_MATCH, _TAGS_RETURN, {"runId": RUN_ID},
                         "tag layer", "tag")
            chunks = _pull(s, _DESC_POOL_MATCH, _CHUNKS_RETURN, population,
                           "chunk layer", "chunk")
            edges = _pull(s, _EDGES_MATCH, _EDGES_RETURN,
                          {**population, "runId": RUN_ID}, "edge layer", "edge")
    finally:
        drv.close()

    if not tags or not chunks or not edges:
        raise RuntimeError(
            f"{len(tags)} tag(s), {len(chunks)} retrievable chunk(s) and "
            f"{len(edges)} HAS_TAG edge(s) of run {RUN_ID!r} in {DATABASE!r} — "
            f"every layer has to hold something for an area to exist")

    emb_of = {row["name"]: row["emb"] for row in tags}
    if len(emb_of) != len(tags):
        raise RuntimeError(
            f"{len(tags) - len(emb_of)} tag name(s) in {DATABASE!r} are not unique "
            f"— the arm addresses a tag by its name")
    tag_names = sorted(emb_of)
    tag_emb = _unit(np.asarray([emb_of[n] for n in tag_names], dtype=np.float32))

    pointer_of = {row["chunkId"]: row for row in chunks}
    if len(pointer_of) != len(chunks):
        raise RuntimeError(
            f"{len(chunks) - len(pointer_of)} chunk id(s) in {DATABASE!r} are not "
            f"unique — pointer resolution would be ambiguous")
    chunk_ids = sorted(pointer_of)
    pointers = [_pointer(pointer_of[cid]) for cid in chunk_ids]
    rel_paths = [pointer_of[cid]["relpath"] for cid in chunk_ids]
    desc_emb = _unit(np.asarray([pointer_of[cid]["emb"] for cid in chunk_ids],
                                dtype=np.float32))

    tag_at = {n: i for i, n in enumerate(tag_names)}
    chunk_at = {cid: i for i, cid in enumerate(chunk_ids)}
    edge_chunk = np.empty(len(edges), dtype=np.int64)
    edge_tag = np.empty(len(edges), dtype=np.int64)
    for i, row in enumerate(progress(edges, desc="edge order", unit="edge")):
        edge_chunk[i] = chunk_at[row["chunkId"]]
        edge_tag[i] = tag_at[row["name"]]
    order = np.lexsort((edge_tag, edge_chunk))
    edge_chunk, edge_tag = edge_chunk[order], edge_tag[order]
    pairs = edge_chunk * len(tag_names) + edge_tag
    if len(np.unique(pairs)) != len(pairs):
        raise RuntimeError(
            f"{len(pairs) - len(np.unique(pairs))} (chunk, tag) pair(s) carry more "
            f"than one HAS_TAG edge of run {RUN_ID!r} — one edge is one membership")
    chunk_degree = np.bincount(edge_chunk, minlength=len(chunk_ids))
    if not chunk_degree.all():
        raise RuntimeError(
            f"{int((chunk_degree == 0).sum())} retrievable chunk(s) in {DATABASE!r} "
            f"carry no HAS_TAG edge of run {RUN_ID!r} — a chunk without an edge "
            f"can never be in the area")

    print(f"artefact_scope: {len(tag_names)} tags, {len(chunk_ids)} chunks, "
          f"{len(edge_chunk)} edges in memory", flush=True)
    return Prepared(
        tag_names=tag_names, tag_emb=tag_emb,
        chunk_ids=chunk_ids, pointers=pointers, rel_paths=rel_paths,
        desc_emb=desc_emb, edge_chunk=edge_chunk, edge_tag=edge_tag,
        build_stats=BuildStats(
            build_time_s=time.perf_counter() - t0,
            model=ModelUsage(),
            models=[EMBED_MODEL],
        ),
    )


def _null(d: np.ndarray) -> tuple:
    mu = np.median(d)
    up = d[d > mu] - mu
    s = MADK * np.median(up) if up.size else 0.0
    if not s > 0.0:
        raise RuntimeError(
            "degenerate distance population: no spread above the median")
    return mu, s, up / s


def _fit_nu(standardised: np.ndarray) -> tuple:
    sym = np.concatenate([standardised, -standardised])
    nu, _, c = student_t.fit(sym, floc=0.0)
    return nu, c


def _pava_dec(y: np.ndarray, x: np.ndarray) -> np.ndarray:
    order = np.argsort(x, kind="stable")
    v = y[order]
    vals, wts, cnts = [], [], []
    for i in range(len(v)):
        vals.append(v[i])
        wts.append(1.0)
        cnts.append(1)
        while len(vals) > 1 and vals[-2] < vals[-1]:
            m = (vals[-2] * wts[-2] + vals[-1] * wts[-1]) / (wts[-2] + wts[-1])
            vals[-2] = m
            wts[-2] += wts[-1]
            cnts[-2] += cnts[-1]
            vals.pop()
            wts.pop()
            cnts.pop()
    out = np.empty(len(y))
    out[order] = np.concatenate([np.full(c, val) for val, c in zip(vals, cnts)])
    return out


def _kde_exact(x: np.ndarray, h: float) -> np.ndarray:
    if not h > 0.0:
        raise RuntimeError(
            f"kernel bandwidth {h!r}: the population has no spread to smooth over")
    n = len(x)
    r = math.sqrt(2.0 * math.log(n / KERNEL_TAU))
    order = np.argsort(x, kind="stable")
    xs = x[order]
    hi = np.searchsorted(xs, xs + r * h, side="right")
    total = np.zeros(n)
    for start in range(0, n, DENSITY_BLOCK):
        stop = min(start + DENSITY_BLOCK, n)
        b = hi[stop - 1]
        u = (xs[start:stop, None] - xs[None, start:b]) / h
        k = np.exp(-0.5 * u * u)
        k[np.abs(u) > r] = 0.0
        total[start:stop] += k.sum(axis=1)
        total[stop:b] += k[:, stop - start:].sum(axis=0)
    dens = np.empty(n)
    dens[order] = total / (n * h * math.sqrt(2.0 * math.pi))
    return dens


def _local_ell(d_star: np.ndarray, d_by_part: np.ndarray) -> tuple:
    nulls, standardised = [], []
    for p in range(d_by_part.shape[0]):
        mu, s, u = _null(d_by_part[p])
        nulls.append((mu, s))
        standardised.append(u)
    nu, c = _fit_nu(np.concatenate(standardised))
    sd = d_star.std(ddof=1)
    iqr = np.subtract(*np.percentile(d_star, [75, 25]))
    h = 0.9 * min(sd, iqr / 1.34) * len(d_star) ** (-0.2)
    log_f = np.log(np.maximum(_kde_exact(d_star, h), 1e-300))
    log_f0 = logsumexp(np.stack([student_t.logpdf((d_star - mu) / (c * s), nu)
                                 - np.log(c * s) for mu, s in nulls]), axis=0)
    return np.maximum(_pava_dec(log_f - log_f0, d_star), 0.0), float(nu)


def _area(ell: np.ndarray, edge_chunk: np.ndarray, edge_tag: np.ndarray,
          n_chunks: int) -> np.ndarray:
    member = np.zeros(n_chunks, dtype=bool)
    member[edge_chunk[ell[edge_tag] > MATCH_EVIDENCE]] = True
    return member


def _scope_mask(rel_paths: list, product) -> np.ndarray:
    if not product:
        return np.zeros(len(rel_paths), dtype=bool)
    target = f"{product}.json"
    return np.array([PurePosixPath(p).parent.name == "products"
                     and PurePosixPath(p).name == target for p in rel_paths],
                    dtype=bool)


def _tiers(in_area: np.ndarray, in_scope: np.ndarray) -> np.ndarray:
    if not in_scope.any():
        return np.where(in_area, 1, 4)
    return np.where(in_area & in_scope, 1,
                    np.where(in_scope, 2, np.where(in_area, 3, 4)))


def _order(tier: np.ndarray, cosine: np.ndarray) -> np.ndarray:
    return np.lexsort((np.arange(len(tier)), -cosine, tier))


def _retrieve(prepared: Prepared, plan: dict, k: int, question: str,
              keep_all: bool = False) -> tuple:
    if k <= 0:
        raise ValueError("k must be positive")
    if RAW_QUESTION and not question.strip():
        raise ValueError(
            "HERB_RAW_QUESTION is on and the question text is empty — the raw "
            "probe has nothing to embed")

    parts = _parts(plan, question)
    qmat, calls, tok_in, tok_out, secs = _embed_cached(
        [p["text"] for p in parts], "query")
    usage = ModelUsage(calls=calls, tokens_in=tok_in, tokens_out=tok_out,
                       time_s=secs)
    probes = _unit(np.asarray(qmat, dtype=np.float32))

    d_by_part = (1.0 - (probes @ prepared.tag_emb.T).astype(np.float64)) / 2.0
    ell, nu = _local_ell(d_by_part.min(axis=0), d_by_part)
    in_area = _area(ell, prepared.edge_chunk, prepared.edge_tag,
                    len(prepared.chunk_ids))
    product = (plan.get("gate") or {}).get("product")
    in_scope = _scope_mask(prepared.rel_paths, product)
    tier = _tiers(in_area, in_scope)

    cosine = np.round((prepared.desc_emb @ probes[0]).astype(np.float64),
                      RANK_SCORE_DP)
    order = _order(tier, cosine)
    ranking = {"chunk_ids": [prepared.chunk_ids[i] for i in order],
               "scores": [float(cosine[i]) for i in order],
               "tiers": [int(tier[i]) for i in order]}
    kept = order if keep_all else order[:k]
    rows = [prepared.pointers[i] for i in kept]

    meta = {
        "n_parts": len(parts),
        "nu": nu,
        "tag_evidence": {**_spread(ell), "positive": int((ell > 0.0).sum()),
                         "admitted": int((ell > MATCH_EVIDENCE).sum())},
        "area_size": int(in_area.sum()),
        "scope": {"product": bool(product), "matched": bool(in_scope.any()),
                  "size": int(in_scope.sum())},
        "tier_sizes": np.bincount(tier, minlength=5)[1:5].tolist(),
        "ranking": ranking,
        "retrieved": len(rows),
    }
    return rows, usage, meta


def answer_one_question(question, prepared: Prepared, generate=None,
                        k: int = 50, char_budget: Optional[int] = None) -> ArmOutput:
    _, text = _qid_text(question)

    nim.reset_timing()
    t0 = time.perf_counter()
    plan, interp_calls, interp_in, interp_out, interp_time = _interpret_cached(
        text, INTERPRET_MODEL)
    rows, embed_usage, meta = _retrieve(prepared, plan, k, text,
                                        keep_all=char_budget is not None)
    meta["interpreter"] = {"model": INTERPRET_MODEL, "backend": "claude-cli"}
    retrieve_wall = time.perf_counter() - t0

    doc_cache: dict = {}
    if char_budget is not None:
        contexts, chunk_id_lists, context_ids, meta["char_budget"] = _budget_contexts(
            rows, char_budget, doc_cache)
        ids_through = meta["char_budget"]["kept"]
    else:
        contexts: list[str] = []
        context_ids: list[str] = []
        chunk_id_lists: list[list[str]] = []
        seen: set[str] = set()
        for row in rows:
            chunk_text, ids = _resolve_chunk(row, doc_cache)
            contexts.append(chunk_text)
            chunk_id_lists.append(ids)
            for aid in ids:
                if aid not in seen:
                    seen.add(aid)
                    context_ids.append(aid)
        ids_through = len(contexts)
    meta["returned"] = len(contexts)
    meta["ranking"]["ids_through"] = ids_through
    meta["ranking"]["contexts_through"] = len(contexts)
    meta["delivered_tiers"] = meta["ranking"]["tiers"][:len(contexts)]
    meta["chunk_ids"] = chunk_id_lists

    search_time_s = max(0.0, retrieve_wall - interp_time - embed_usage.time_s)
    retrieval_usage = ModelUsage(
        calls=interp_calls + embed_usage.calls,
        tokens_in=interp_in + embed_usage.tokens_in,
        tokens_out=interp_out + embed_usage.tokens_out,
        time_s=interp_time + embed_usage.time_s,
        **nim.take_timing())

    if generate is None:
        answer, gen = "", ModelUsage()
    else:
        g0 = time.perf_counter()
        result = generate(text, contexts)
        answer, gen = unpack_generation(result, time.perf_counter() - g0)

    return ArmOutput(
        answer=answer,
        contexts=contexts,
        context_ids=context_ids,
        search_time_s=search_time_s,
        generator=gen,
        retrieval=retrieval_usage,
        meta=meta,
    )


def _model_selfcheck() -> None:
    rng = np.random.default_rng(20260903)
    bulk = 0.5 + 0.1 * rng.standard_normal(20000)
    mu, s, u = _null(bulk)
    assert mu == np.median(bulk)
    assert abs(s - 0.1) < 0.01
    assert (u > 0.0).all() and abs(np.median(u) - 1.0 / MADK) < 1e-12
    try:
        _null(np.full(16, 0.3))
    except RuntimeError:
        pass
    else:
        raise AssertionError("a population with no spread yielded a null")
    print(f"  null on a Gaussian bulk of scale 0.1: median {mu:.4f}, scale "
          f"{s:.4f}; a flat population stops", flush=True)

    y = np.array([1.0, 3.0, 2.0, 0.0, 5.0, 0.0])
    fit = _pava_dec(y, np.arange(6.0))
    assert np.allclose(fit, [2.2] * 5 + [0.0])
    assert abs(fit.sum() - y.sum()) < 1e-12
    shuffled = rng.permutation(6)
    assert np.allclose(_pava_dec(y[shuffled], np.arange(6.0)[shuffled]), fit[shuffled])
    print(f"  isotonic fit of {y.tolist()} non-increasing in x: "
          f"{np.round(fit, 4).tolist()}, mean preserved, order-free", flush=True)

    gauss = rng.standard_normal(20000)
    h = 0.9 * min(gauss.std(ddof=1), np.subtract(*np.percentile(gauss, [75, 25])) / 1.34) \
        * len(gauss) ** (-0.2)
    dens = _kde_exact(gauss, h)
    truth = np.exp(-0.5 * gauss ** 2) / math.sqrt(2 * math.pi)
    assert np.abs(dens - truth).max() < 0.02
    few = gauss[:3000]
    pair = (few[:, None] - few[None, :]) / h
    untruncated = (np.exp(-0.5 * pair * pair).sum(axis=1)
                   / (len(few) * h * math.sqrt(2 * math.pi)))
    gap = np.abs(_kde_exact(few, h) / untruncated - 1.0).max()
    assert gap < 16 * KERNEL_TAU
    print(f"  exact kernel density on 20000 standard normals at h {h:.4f}: "
          f"largest gap to the true density {np.abs(dens - truth).max():.4f}; "
          f"against the untruncated sum over 3000 of them, largest relative gap "
          f"{gap:.1e}", flush=True)

    dim, n_tags, n_chunks = 32, 600, 120
    probes = _unit(rng.standard_normal((2, dim)).astype(np.float32))
    tag_emb = rng.standard_normal((n_tags, dim))
    tag_emb[:12] = 8.0 * probes[0] + rng.standard_normal((12, dim))
    tag_emb[12:18] = 8.0 * probes[1] + rng.standard_normal((6, dim))
    tag_emb = _unit(tag_emb.astype(np.float32))
    desc_emb = rng.standard_normal((n_chunks, dim))
    desc_emb[:5] = 8.0 * probes[0] + rng.standard_normal((5, dim))
    desc_emb = _unit(desc_emb.astype(np.float32))
    d_by_part = (1.0 - (probes @ tag_emb.T).astype(np.float64)) / 2.0
    d_star = d_by_part.min(axis=0)
    ell, nu = _local_ell(d_star, d_by_part)
    assert ell.shape == (n_tags,) and nu > 0.0
    assert (ell >= 0.0).all() and (ell[:18] > MATCH_EVIDENCE).all()
    assert (ell == 0.0).mean() > 0.5
    by_distance = ell[np.argsort(d_star, kind="stable")]
    assert (np.diff(by_distance) <= 1e-12).all()
    print(f"  local evidence: {int((ell > 0).sum())} of {n_tags} tags above 0, "
          f"{int((ell > MATCH_EVIDENCE).sum())} above ln 2 (18 planted), planted "
          f"tag evidence {ell[:18].min():.2f}-{ell[:18].max():.2f} nats, "
          f"non-increasing in the distance; t shape nu {nu:.2f}", flush=True)

    pairs = {(0, 0), (0, 1), (1, 0), (2, 12)}
    for chunk in range(3, n_chunks):
        for tag in rng.choice(np.arange(18, n_tags), 3, replace=False):
            pairs.add((chunk, int(tag)))
    pairs = sorted(pairs)
    edge_chunk = np.array([c for c, _ in pairs])
    edge_tag = np.array([t for _, t in pairs])
    in_area = _area(ell, edge_chunk, edge_tag, n_chunks)
    assert in_area[:3].all()
    reached = {c for c, t in pairs if ell[t] > MATCH_EVIDENCE}
    assert set(np.flatnonzero(in_area).tolist()) == reached
    print(f"  area: {int(in_area.sum())} of {n_chunks} chunks hold an edge to a "
          f"match; the three planted chunks are in", flush=True)

    rel_paths = ["X/products/A.json", "X/products/a.json", "X/metadata/A.json",
                 "X/products/sub/A.json", "X/products/A.json.bak", "X/products/B.json"]
    assert _scope_mask(rel_paths, "A").tolist() == [True] + [False] * 5
    assert _scope_mask(rel_paths, "B").tolist() == [False] * 5 + [True]
    assert not _scope_mask(rel_paths, None).any()
    assert not _scope_mask(rel_paths, "").any()
    assert not _scope_mask(rel_paths, "C").any()
    print(f"  scope: product 'A' over {rel_paths} -> "
          f"{_scope_mask(rel_paths, 'A').astype(int).tolist()}; no product or "
          f"an unmatched one -> none", flush=True)

    area = np.array([True, True, False, False])
    scope = np.array([True, False, True, False])
    assert _tiers(area, scope).tolist() == [1, 3, 2, 4]
    assert _tiers(area, np.zeros(4, dtype=bool)).tolist() == [1, 1, 4, 4]
    tier = np.array([4, 1, 1, 2, 1])
    cosine = np.array([0.9, 0.5, 0.7, 0.8, 0.5])
    assert _order(tier, cosine).tolist() == [2, 1, 4, 3, 0]
    print(f"  tiers: area {area.astype(int).tolist()} x scope "
          f"{scope.astype(int).tolist()} -> {_tiers(area, scope).tolist()}, "
          f"no scope -> {_tiers(area, np.zeros(4, dtype=bool)).tolist()}; rank "
          f"key (tier, -cosine, chunk index) -> {_order(tier, cosine).tolist()}",
          flush=True)
    print("artefact_scope model self-check OK", flush=True)


def _selfcheck() -> None:
    _model_selfcheck()
    corpus = Path(__file__).resolve().parent.parent.parent / "data" / "corpus" / DATASET_ID
    prepared = prepare_over_corpus(corpus)
    n_tags, n_chunks = len(prepared.tag_names), len(prepared.chunk_ids)
    walls, searches, shapes, positives, admitted, areas, scopes, firsts = (
        [], [], [], [], [], [], [], [])
    for probe in progress(_PROBES, desc="probing", unit="q"):
        t0 = time.perf_counter()
        out = answer_one_question(("selfcheck", probe), prepared, None,
                                  char_budget=72000)
        walls.append(time.perf_counter() - t0)
        searches.append(out.search_time_s)
        meta = out.meta
        rank = meta["ranking"]
        budget = meta["char_budget"]
        sizes = meta["tier_sizes"]
        shapes.append(meta["nu"])
        positives.append(meta["tag_evidence"]["positive"])
        admitted.append(meta["tag_evidence"]["admitted"])
        areas.append(meta["area_size"])
        scopes.append(meta["scope"]["size"])
        firsts.append(sizes[0])
        print(f"\n  {probe}", flush=True)
        print(f"    {meta['n_parts']} part(s); tag evidence {meta['tag_evidence']}; "
              f"t shape nu {meta['nu']:.2f}", flush=True)
        print(f"    area {meta['area_size']} chunk(s); scope {meta['scope']}; "
              f"tiers {sizes}", flush=True)
        print(f"    returned {meta['returned']} context(s), "
              f"{len(out.context_ids)} artifact id(s), "
              f"{sum(len(c) for c in out.contexts)} chars, delivered tiers "
              f"{np.bincount(meta['delivered_tiers'], minlength=5)[1:5].tolist()}; "
              f"retrieval model calls {out.retrieval.calls}, search "
              f"{out.search_time_s:.3f}s, wall {walls[-1]:.3f}s", flush=True)
        print(f"    ranking: {len(rank['chunk_ids'])} rank(s) recorded, "
              f"artifact ids through {rank['ids_through']}, context text "
              f"through {rank['contexts_through']}, "
              f"{len(json.dumps(rank, ensure_ascii=False))} chars of the "
              f"record", flush=True)
        assert (len(rank["chunk_ids"]) == len(rank["scores"])
                == len(rank["tiers"]) == n_chunks)
        assert len(set(rank["chunk_ids"])) == n_chunks
        assert all(a <= b for a, b in zip(rank["tiers"], rank["tiers"][1:]))
        assert all(a >= b for (a, ta), (b, tb) in zip(zip(rank["scores"], rank["tiers"]),
                                                      zip(rank["scores"][1:], rank["tiers"][1:]))
                   if ta == tb)
        assert meta["retrieved"] == n_chunks
        assert sizes == np.bincount(rank["tiers"], minlength=5)[1:5].tolist()
        assert sum(sizes) == n_chunks
        assert meta["area_size"] == sizes[0] + sizes[2]
        if meta["scope"]["matched"]:
            assert meta["scope"]["product"]
            assert meta["scope"]["size"] == sizes[0] + sizes[1] > 0
        else:
            assert meta["scope"]["size"] == 0 and sizes[1] == sizes[2] == 0
        assert rank["contexts_through"] == len(meta["chunk_ids"])
        assert rank["ids_through"] == budget["kept"]
        if budget["boundary"] is not None:
            assert rank["contexts_through"] == budget["kept"] + 1
            assert rank["chunk_ids"][budget["kept"]] == budget["boundary"]["id"]
        assert meta["delivered_tiers"] == rank["tiers"][:rank["contexts_through"]]
        resorted = sorted(zip(rank["chunk_ids"], rank["scores"], rank["tiers"]),
                          key=lambda row: (row[2], -row[1], row[0]))
        assert [cid for cid, _, _ in resorted] == rank["chunk_ids"]
        assert meta["n_parts"] >= 1
        assert meta["tag_evidence"]["n"] == n_tags
        assert 0.0 <= meta["tag_evidence"]["min"] <= meta["tag_evidence"]["max"]
        assert (0 <= meta["tag_evidence"]["admitted"]
                <= meta["tag_evidence"]["positive"] <= n_tags)
        assert meta["nu"] > 0.0
        assert len(out.context_ids) == len(set(out.context_ids))
        assert len(meta["chunk_ids"]) == len(out.contexts)
        assert out.contexts, "a probe returned no context"
    print(f"\nartefact_scope: prepare {prepared.build_stats.build_time_s:.1f}s — "
          f"{n_tags} tags, {n_chunks} chunks, {len(prepared.edge_tag)} edges in "
          f"memory", flush=True)
    print(f"  t shape over the probes: nu {min(shapes):.2f}-{max(shapes):.2f}; "
          f"{min(positives)}-{max(positives)} of {n_tags} tags above 0, "
          f"{min(admitted)}-{max(admitted)} above ln 2", flush=True)
    print(f"  area {min(areas)}-{max(areas)} chunk(s), scope "
          f"{min(scopes)}-{max(scopes)}, tier 1 {min(firsts)}-{max(firsts)} over "
          f"{n_chunks} chunks", flush=True)
    print(f"  {len(_PROBES)} probe(s): search {min(searches):.3f}-{max(searches):.3f}s, "
          f"wall with resolution {min(walls):.3f}-{max(walls):.3f}s per question",
          flush=True)
    print(f"  every chunk ranked on every probe; the record re-sorts to the arm's "
          f"order at {RANK_SCORE_DP} dp", flush=True)
    print("artefact_scope self-check OK", flush=True)


if __name__ == "__main__":
    _selfcheck()

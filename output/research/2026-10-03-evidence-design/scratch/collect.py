"""Collect the numeric arrays the instrument measurement runs on. No text is printed or saved.

Reuses the arm's own loaders: artefact_v4.prepare_over_corpus, artefact_v4._interpret (cached,
HERB_V4_OFFLINE=on, chat.post blocked) and artefact_facet_joint._query_cosines (the pinned
embedder, query prefix). The 10smoke questions come through the harness's own set loader and
are handed to the arm as (id, text); the gold fields are never read.

Output: one .npz of numbers and ids in the cache directory (default: the session scratchpad).
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

os.environ['HERB_V4_OFFLINE'] = 'on'
ROOT = Path(__file__).resolve().parents[4]
for p in (ROOT / 'prod', ROOT / 'test'):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import numpy as np

from harness import chat, orchestrator


def _blocked(*args, **kwargs):
    raise RuntimeError('model call blocked: this measurement makes none')


chat.post = _blocked

import arms.artefact_v4 as A
from arms.artefact_facet_joint import _query_cosines
from graph.db import _readable

CACHE = Path(os.environ.get('EVID_CACHE', r'C:\Users\jocke\AppData\Local\Temp\claude'
                            r'\c--Coding-exjobbet-GRAG-Job\232eaa9a-71a9-4684-8388-e4d07653f737'
                            r'\scratchpad'))
IDENTITY_N = 300
IDENTITY_SEED = 20261003

PRODUCT_OF_CHUNK = '''
MATCH (c:Chunk)-[:product]->(p:Product)
RETURN c.chunk_id AS chunkId, collect(DISTINCT p.name) AS names
'''


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    prepared = A.prepare_over_corpus(orchestrator.open_corpus(orchestrator.DEFAULT_CORPUS))
    print(f'collect: prepared in {time.perf_counter() - t0:.1f}s', flush=True)
    eligible = np.asarray(prepared.casefold_eligible, dtype=bool)
    n_chunks, n_tags = len(prepared.chunk_ids), len(prepared.graph_tags)
    print(f'collect: {n_chunks} chunks, {n_tags} graph tags, {int(eligible.sum())} eligible, '
          f'{prepared.edge_tag.size} edges, {int(eligible[prepared.edge_tag].sum())} eligible '
          f'edges', flush=True)

    # each chunk's product by name (read only), checked against the arm's own partition
    ci = {cid: i for i, cid in enumerate(prepared.chunk_ids)}
    with prepared.driver.session(database=A.DATABASE, default_access_mode='READ') as session:
        rows = session.execute_read(lambda tx: [(r['chunkId'], r['names'])
                                                for r in tx.run(PRODUCT_OF_CHUNK)])
    names_of = {}
    multi = 0
    for cid, names in rows:
        if cid in ci:
            names_of[ci[cid]] = sorted(names)
            multi += len(names) > 1
    product_names = sorted({n for names in names_of.values() for n in names})
    pid = {n: i for i, n in enumerate(product_names)}
    chunk_product = np.full(n_chunks, -1, dtype=np.int64)
    for i, names in names_of.items():
        chunk_product[i] = pid[names[0]]
    arm_product = np.asarray(prepared.structure.product)
    # same partition as the arm's structure read?
    pairs = set(zip(chunk_product.tolist(), arm_product.tolist()))
    print(f'collect: {len(product_names)} product names over {int((chunk_product >= 0).sum())} '
          f'chunks; chunks with more than one product {multi}; (name index, arm index) pairs '
          f'{len(pairs)} (a bijection has {len(product_names)})', flush=True)

    chosen = orchestrator.load_chosen_questions(ROOT / 'data' / '10smoke.jsonl')
    questions = [orchestrator.to_arm_question(q) for q in chosen]
    del chosen
    out = {}
    qids = []
    for qi, (qid, text) in enumerate(questions):
        t1 = time.perf_counter()
        query, usage, stages = A._interpret(text, prepared)
        if usage.calls or not all(s['cache_hit'] for s in stages):
            raise RuntimeError('an interpretation was not the cached one')
        d_tags = [t.text for t in query.tags]
        q_tags = [t.text for t in query.query_tags]
        m1, _, _ = _query_cosines(query.description, d_tags, prepared)
        m2, _, _ = _query_cosines(query.question, [], prepared)
        fits = [np.asarray(m1['query_tag_cosines'], dtype=np.float64)]
        if q_tags:
            m3, _, _ = _query_cosines(query.description, q_tags, prepared)
            fits.append(np.asarray(m3['query_tag_cosines'], dtype=np.float64))
        fits = np.vstack(fits)
        readings = np.array([t.readings for t in query.tags] + [t.readings for t in query.query_tags],
                            dtype=np.float64)
        side = np.array([0] * len(d_tags) + [1] * len(q_tags), dtype=np.int64)
        folded = [t.strip().casefold() for t in d_tags + q_tags]
        out[f'fits_{qi}'] = fits
        out[f'readings_{qi}'] = readings
        out[f'side_{qi}'] = side
        out[f'ddesc_{qi}'] = np.asarray(m1['query_description_cosines'], dtype=np.float64)
        out[f'dquest_{qi}'] = np.asarray(m2['query_description_cosines'], dtype=np.float64)
        out[f'dup_{qi}'] = np.array([len(folded) - len(set(folded))], dtype=np.int64)
        qids.append(qid)
        print(f'collect: {qid}: {len(d_tags)} description-side tags, {len(q_tags)} question-side '
              f'tags, {int(out[f"dup_{qi}"][0])} repeated across the lists, '
              f'{time.perf_counter() - t1:.1f}s', flush=True)
    del questions

    # B: identity reference - eligible graph tag names, readable form, QUERY prefix
    rng = np.random.default_rng(IDENTITY_SEED)
    pool = np.flatnonzero(eligible)
    pick = np.sort(rng.choice(pool, size=IDENTITY_N, replace=False))
    names = [_readable(prepared.graph_tags[i]) for i in pick]
    t2 = time.perf_counter()
    mi, _, _ = _query_cosines(names[0], names, prepared)
    ident = np.asarray(mi['query_tag_cosines'], dtype=np.float64)
    print(f'collect: identity probes embedded ({IDENTITY_N} names, '
          f'{len(set(names))} distinct readable forms) in {time.perf_counter() - t2:.1f}s',
          flush=True)

    channel_ptr = np.asarray(prepared.structure.channel_ptr)
    channels = np.asarray(prepared.structure.channels)
    np.savez_compressed(
        CACHE / 'evidence_arrays.npz',
        qids=np.array(qids), n_questions=np.array([len(qids)]),
        eligible=eligible, edge_tag=np.asarray(prepared.edge_tag),
        edge_chunk=np.asarray(prepared.edge_chunk), edge_topic=np.asarray(prepared.edge_topic),
        refit_means=np.asarray(prepared.multikey_layer.values),
        chunk_product=chunk_product, arm_product=arm_product,
        product_names=np.array(product_names),
        channel_ptr=channel_ptr, channels=channels,
        chunk_kinds=np.array(prepared.chunk_kinds),
        identity_pick=pick, identity_fits=ident.astype(np.float32),
        **out)
    print(f'collect: saved {CACHE / "evidence_arrays.npz"} '
          f'({time.perf_counter() - t0:.1f}s total)', flush=True)
    prepared.close()


if __name__ == '__main__':
    main()

"""The follow-up arrays: the query tags and the query description embedded in the PASSAGE role
(the role `test/graph/reembed_herb_eval.py` writes Tag.emb and Chunk.desc_emb under), and the
300 identity tag names in the passage role. No text is printed or saved; no model is asked.

Reuses the arm's own loaders as collect.py does. The embedding call mirrors
`artefact_facet_joint._query_cosines` (same pinned recipe, 4 threads, the same text list, the
same float64 unit normalisation); only the role handed to `harness.embed._embed` differs.

Writes symmetric_arrays.npz and identity_passage.json beside this file.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

os.environ['HERB_V4_OFFLINE'] = 'on'
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
for p in (ROOT / 'prod', ROOT / 'test', HERE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import numpy as np
from threadpoolctl import threadpool_limits

from harness import chat, orchestrator


def _blocked(*args, **kwargs):
    raise RuntimeError('model call blocked: this measurement makes none')


chat.post = _blocked

import arms.artefact_v4 as A
from arms.artefact_facet_joint import _query_embedding_texts, _unit
from graph.db import _readable
import instrument_lib as IL

OLD = Path(os.environ.get('EVID_CACHE', r'C:\Users\jocke\AppData\Local\Temp\claude'
                          r'\c--Coding-exjobbet-GRAG-Job\232eaa9a-71a9-4684-8388-e4d07653f737'
                          r'\scratchpad')) / 'evidence_arrays.npz'
IDENTITY_N = 300
IDENTITY_SEED = 20261003
KEEP_TOP = 301


def role_cosines(description, tags, prepared, role):
    """`_query_cosines` with the role as an argument."""
    with threadpool_limits(limits=4):
        os.environ['HF_HUB_OFFLINE'] = '1'
        os.environ['TRANSFORMERS_OFFLINE'] = '1'
        for name in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
            os.environ[name] = '4'
        import torch
        from harness import embed
        torch.set_num_threads(4)
        if (embed.EMBED_MODEL != 'nvidia/llama-nemotron-embed-1b-v2'
                or embed.EMBED_REVISION != '113abe4acafa848e77ead9c0623205e511932348'
                or embed.EMBED_DEVICE != 'cpu' or embed.EMBED_DTYPE != 'float32'
                or embed.EMBED_PREFIX != {'query': 'query: ', 'passage': 'passage: '}):
            raise ValueError('Pinned embedding recipe differs')
        texts = _query_embedding_texts(description, tags)
        vectors, _, _, _, _ = embed._embed(texts, role, bar=False)
        vectors = _unit(vectors)
        at = {text: i for i, text in enumerate(texts)}
        tag_vectors = vectors[[at[tag.strip()] for tag in tags]]
        description_vector = vectors[at[description]]
        return {'tags': tag_vectors @ prepared.tag_vectors.T,
                'description': description_vector @ prepared.chunk_vectors.T}


def main():
    t0 = time.perf_counter()
    old = np.load(OLD, allow_pickle=False)
    prepared = A.prepare_over_corpus(orchestrator.open_corpus(orchestrator.DEFAULT_CORPUS))
    eligible = np.asarray(prepared.casefold_eligible, dtype=bool)
    if not np.array_equal(eligible, old['eligible']):
        raise RuntimeError('the eligible tags differ from the first collection')
    el = np.flatnonzero(eligible)
    names_all = prepared.graph_tags
    differs = int(sum(1 for i in el if _readable(names_all[i]) != names_all[i]))
    print(f'collect_symmetric: prepared in {time.perf_counter() - t0:.1f}s; eligible tags whose '
          f'readable form differs from the stored name: {differs} of {el.size}', flush=True)

    chosen = orchestrator.load_chosen_questions(ROOT / 'data' / '10smoke.jsonl')
    questions = [orchestrator.to_arm_question(q) for q in chosen]
    del chosen
    if [q for q, _ in questions] != [str(q) for q in old['qids']]:
        raise RuntimeError('the question ids differ from the first collection')
    out = {}
    for qi, (qid, text) in enumerate(questions):
        t1 = time.perf_counter()
        query, usage, stages = A._interpret(text, prepared)
        if usage.calls or not all(s['cache_hit'] for s in stages):
            raise RuntimeError('an interpretation was not the cached one')
        d_tags = [t.text for t in query.tags]
        q_tags = [t.text for t in query.query_tags]
        if len(d_tags) + len(q_tags) != old[f'fits_{qi}'].shape[0]:
            raise RuntimeError('the query tags differ from the first collection')
        first = role_cosines(query.description, d_tags, prepared, 'passage')
        fits = [np.asarray(first['tags'], dtype=np.float64)]
        if q_tags:
            second = role_cosines(query.description, q_tags, prepared, 'passage')
            fits.append(np.asarray(second['tags'], dtype=np.float64))
        out[f'fits_{qi}'] = np.vstack(fits)
        out[f'ddesc_{qi}'] = np.asarray(first['description'], dtype=np.float64)
        line = (f'collect_symmetric: {qid}: {len(d_tags)} + {len(q_tags)} query tags and the '
                f'description in the passage role')
        if qi == 0:
            # the same call in the query role must give the first collection's arrays back
            again = role_cosines(query.description, d_tags, prepared, 'query')
            diff_t = float(np.abs(np.asarray(again['tags'])
                                  - old['fits_0'][:len(d_tags)]).max())
            diff_d = float(np.abs(np.asarray(again['description']) - old['ddesc_0']).max())
            out['alignment_check'] = np.array([diff_t, diff_d])
            line += (f'; query-role recomputation against the first collection: largest '
                     f'difference {diff_t:.2e} (tags), {diff_d:.2e} (description)')
        print(line + f', {time.perf_counter() - t1:.1f}s', flush=True)
    del questions

    rng = np.random.default_rng(IDENTITY_SEED)
    pick = np.sort(rng.choice(el, size=IDENTITY_N, replace=False))
    if not np.array_equal(pick, old['identity_pick']):
        raise RuntimeError('the identity sample differs from the first collection')
    names = [_readable(names_all[i]) for i in pick]
    t2 = time.perf_counter()
    ident = np.asarray(role_cosines(names[0], names, prepared, 'passage')['tags'],
                       dtype=np.float64)
    print(f'collect_symmetric: {IDENTITY_N} identity names embedded in the passage role in '
          f'{time.perf_counter() - t2:.1f}s', flush=True)
    own = ident[np.arange(pick.size), pick]
    local = (np.cumsum(eligible) - 1)[pick]
    rows, tops = [], []
    for i in range(pick.size):
        x = ident[i][el]
        row, _ = IL.describe(x)
        row['own_cos'] = float(own[i])
        row['own_rank'] = int((x >= own[i]).sum())
        row['own_z_mad'] = float((own[i] - row['median']) / row['s_mad'])
        row['best_other_cos'] = float(np.max(np.delete(x, local[i])))
        row['own_minus_best_other_in_s_mad'] = float(
            (own[i] - row['best_other_cos']) / row['s_mad'])
        rows.append(row)
        tops.append(np.sort(x)[::-1][:KEEP_TOP])
    raw_differs = [i for i in range(pick.size) if names_all[pick[i]] != names[i]]
    raw_check = None
    if raw_differs:
        raw_names = [names_all[pick[i]] for i in raw_differs]
        raw = np.asarray(role_cosines(raw_names[0], raw_names, prepared, 'passage')['tags'],
                         dtype=np.float64)
        raw_own = raw[np.arange(len(raw_differs)), pick[raw_differs]]
        raw_check = {'names': len(raw_differs),
                     'own_cos_raw_form': [float(v) for v in raw_own],
                     'own_cos_readable_form': [float(own[i]) for i in raw_differs]}
    np.savez_compressed(HERE / 'symmetric_arrays.npz', identity_top=np.array(tops),
                        identity_own=own, **out)
    (HERE / 'identity_passage.json').write_text(json.dumps({
        'probes': int(pick.size), 'eligible_tags_with_a_different_readable_form': differs,
        'raw_form_check': raw_check, 'rows': rows}, indent=0), encoding='utf-8')
    print(f'collect_symmetric: own cosine in the passage role: median {np.median(own):.6f}, '
          f'min {own.min():.6f}, max {own.max():.6f}; saved ({time.perf_counter() - t0:.1f}s '
          f'total)', flush=True)
    prepared.close()


if __name__ == '__main__':
    main()

"""The arrays behind "structure last" on the made-up question, kept on the side for
`structure_last_gauge.py`: the chain's value per chunk and its parts, the per-link quantity a
chunk takes its best of, each querytag's standing over the graph tags, the tree's places, and
the same best-link value under random graph tags standing in for a querytag.

Copied from `cluster_by_scope_made_up.py` and extended. No model call (the first call's answer
is read from the cache), nothing written but the two files beside this one, the 72,000 cut is
not used. Run from the repo root."""
import json
import pathlib
import sys

import numpy as np

sys.path[:0] = ['prod', 'test']
sys.stdout.reconfigure(encoding='utf-8')
from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_facet_joint import _query_cosines  # noqa: E402
from artefact import query_content as Q  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402

HERE = pathlib.Path('output/research/2026-10-07-structure-last')
STAND_INS = 200          # the main session's "about 200" random graph tags
SEED = 20261007
cache = pathlib.Path('output/private/artefact_v4_cache')
question = json.loads(pathlib.Path('output/walkthrough/20261005T040000Z/walkthrough.json')
                      .read_text(encoding='utf-8'))['question']


def validate(raw):
    cleaned, _ = V._collapse_duplicate_tags(raw)
    return Q.parse(question, cleaned)


content, _, _ = V._ask('querytag', Q.request(question), validate, cache, True)
query_tags = (*content.tags, *content.query_tags)
tags = [t.text for t in query_tags]
prepared = V.prepare_over_corpus('data/corpus')
layer = prepared.layer
n = len(prepared.chunk_ids)
dim = prepared.chunk_vectors.shape[1]
bare = V._QueryAxes(prepared.tag_vectors, np.eye(dim))
matrices, _, _ = _query_cosines(content.description, tags, bare, 'passage')
tag_vectors = np.asarray(matrices['query_chunk_cosines'], dtype=np.float64)
description = np.asarray(matrices['query_description_cosines'], dtype=np.float64)
matrices, _, _ = _query_cosines(content.question, [], bare)
asked = np.asarray(matrices['query_description_cosines'], dtype=np.float64)
query = {
    'cosines': tag_vectors @ prepared.tag_vectors.T.astype(np.float64),
    'readings': np.array([t.readings for t in query_tags], dtype=np.float64),
    'description_cosines': tag_vectors @ description,
    'd_description': description @ prepared.chunk_vectors.T,
    'd_question': asked @ prepared.chunk_vectors.T}
walked = WK.chain(layer, query, V.COS_NOISE)

# The chain's own loop once more, keeping what it does not return: per querytag each graph
# tag's standing and each link's fit (the same-thing links moved as the chain moves them).
eligible, tag_e, chunk_e = layer['eligible'], layer['edge_tag'], layer['edge_chunk']
rows, readings = query['cosines'], query['readings']
count = rows.shape[0]
same = layer['same_level']
orders = np.array([WK.facet_order(r) for r in readings], dtype=np.int64)
standing_of_tag = np.full((count, eligible.size), np.nan)
fit_of_link = np.zeros((count, chunk_e.size))
for i in range(count):
    z, bulk, spread = WK.standing(rows[i][eligible])
    standing_of_tag[i, eligible] = z
    fit_of_tag = np.zeros(eligible.size)
    fit_of_tag[eligible] = np.clip(z, 0., None)
    fit_edge = fit_of_tag[tag_e]
    edge_cosines = rows[i][tag_e]
    closest = float(rows[i][eligible].max())
    picked = np.flatnonzero(edge_cosines >= same)
    width = max(closest - same, 0.)
    if picked.size and width > 0:
        _, placed = WK.spread_by_facets(edge_cosines[picked], closest,
                                        width * (1. + 1e-9) + 1e-12,
                                        layer['facet_class'][picked], orders[i],
                                        layer['raw'][picked, 0])
        moved = edge_cosines.copy()
        moved[picked] = placed
        fit_edge = np.clip((moved - bulk) / spread, 0., None)
    fit_of_link[i] = fit_edge
weight = walked['centrality']
per_link = (weight[:, None] * fit_of_link).max(axis=0)       # what a chunk takes its best of
by_chunk = np.argsort(chunk_e, kind='stable')
starts = np.flatnonzero(np.r_[True, np.diff(chunk_e[by_chunk]) != 0])
if starts.size != n:
    raise RuntimeError('a chunk has no eligible link; the best-of-m arithmetic below needs one')
best = np.maximum.reduceat(per_link[by_chunk], starts)
apart = float(np.abs(best - walked['tags']).max())
print(f'the per-link quantity rebuilt here against the chain\'s tag value: largest difference '
      f'{apart:.3g} over {n} chunks')
if apart > 1e-9:
    raise RuntimeError('the rebuilt per-link quantity is not the chain\'s')

# Random graph tags standing in for a querytag, one at a time: a chunk's value is its best
# link's standing to that tag. Twice: with the stand-in tag's own links, and with them left out.
rng = np.random.default_rng(SEED)
pool = np.flatnonzero(eligible)
drawn = rng.choice(pool, size=STAND_INS, replace=False)
tv = prepared.tag_vectors.astype(np.float64)
stand_in = np.zeros((STAND_INS, n), dtype=np.float32)
stand_in_without = np.zeros((STAND_INS, n), dtype=np.float32)
for k, t in enumerate(drawn):
    row = tv @ tv[t]
    z, _, _ = WK.standing(row[eligible])
    full = np.full(eligible.size, -np.inf)
    full[eligible] = z
    link = full[tag_e]
    stand_in[k] = np.maximum.reduceat(link[by_chunk], starts)
    link = np.where(tag_e == t, -np.inf, link)
    stand_in_without[k] = np.maximum.reduceat(link[by_chunk], starts)
print(f'{STAND_INS} random graph tags stood in for a querytag (seed {SEED}); chunks whose only '
      f'link is the stand-in tag itself: {int(np.isinf(stand_in_without).sum())}')

np.savez_compressed(
    HERE / 'structure_last_arrays.npz',
    strength=walked['strength'], tags=walked['tags'], text=walked['text'], D=walked['D'],
    Qs=walked['Qs'], lift_product=walked['lift']['product'], lift_near=walked['lift']['near'],
    order=np.array(walked['order'], dtype=np.int64), level=walked['level'],
    step=np.float64(walked['step']), winner=walked['winner'], bulk=walked['bulk'],
    spread=walked['spread'], centrality=weight, readings=readings,
    cosines=rows, standing_of_tag=standing_of_tag, fit_of_link=fit_of_link.astype(np.float32),
    per_link=per_link, eligible=eligible, edge_tag=tag_e, edge_chunk=chunk_e,
    links=layer['n_c'], product=layer['product'], kind=layer['kind'], near=layer['near'],
    d_description=query['d_description'], d_question=query['d_question'],
    description_cosines=query['description_cosines'],
    stand_in=stand_in, stand_in_without=stand_in_without, stand_in_tags=drawn)
(HERE / 'structure_last_arrays.json').write_text(json.dumps({
    'question': question, 'query_tags': tags,
    'description_side_tags': len(content.tags), 'question_side_tags': len(content.query_tags),
    'kind_names': layer['kind_names'], 'same_level': layer['same_level'],
    'cos_noise': V.COS_NOISE,
    'paths': {p: sorted(int(i) for i in c) for p, c in prepared.tree['paths'].items()},
}, ensure_ascii=False), encoding='utf-8')
print(f'{count} querytags, {int(eligible.sum())} eligible graph tags, {chunk_e.size} links, '
      f'{n} chunks, {len(prepared.tree["paths"])} places; arrays kept in {HERE}')

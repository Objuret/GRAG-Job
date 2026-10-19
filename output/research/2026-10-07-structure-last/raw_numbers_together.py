"""The raw nearness values of the made-up question (`structure_last_arrays.npz`: querytag x
graph tag, query description x chunk description, question x chunk description) taken step by
step to one number per chunk, each step read against the unrelated ones of its own kind. Prints
what each step does to the scale and to the number of tags. No model call, no benchmark file,
nothing uses the 72,000 cut. Run from the repo root."""
import pathlib
import sys

import numpy as np
from scipy import stats

sys.path.insert(0, 'test/artefact')
from v4_walk import standing  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8')
A = np.load(pathlib.Path('output/research/2026-10-07-structure-last') / 'structure_last_arrays.npz')
eligible = A['eligible'].astype(bool)
cos = A['cosines'].astype(float)
edge_tag, edge_chunk = A['edge_tag'], A['edge_chunk']
links = A['links'].astype(int)
n, m = links.size, cos.shape[0]
N_TAGS, N_LINKS = int(eligible.sum()), edge_tag.size


def share_at_least(values):
    """Per value the share of the values at least as large (ties share), in (0, 1]."""
    return (values.size - stats.rankdata(values, method='min') + 1) / values.size


def spearman(a, b):
    return float(stats.spearmanr(a, b)[0])


print(f'{m} querytags, {N_TAGS} graph tags, {N_LINKS} links, {n} chunks')

print('\n== 1. the raw cosines, one querytag against all graph tags ==')
print('querytag: raw middle / top 1% / largest; tags beyond 2 and 3 spreads above the middle, '
      'as they are and with the squeeze undone (a bell has '
      f'{N_TAGS * stats.norm.sf(2):.0f} and {N_TAGS * stats.norm.sf(3):.0f})')
for i in range(m):
    row = cos[i][eligible]
    z, _, _ = standing(row)
    zu, _, _ = standing(np.arctanh(np.clip(row, -0.999999, 0.999999)))
    print(f'  {i:2d}: {np.median(row):.3f} / {np.percentile(row, 99):.3f} / {row.max():.3f}; '
          f'as they are {int((z > 2).sum()):4d} and {int((z > 3).sum()):3d}; squeeze undone '
          f'{int((zu > 2).sum()):4d} and {int((zu > 3).sum()):3d}; skew {stats.skew(row):+.2f} '
          f'-> {stats.skew(np.arctanh(np.clip(row, -0.999999, 0.999999))):+.2f}')

print('\n== 2. a chunk takes the best of its tags: the share among the LINKS, then the best-of step ==')
share_link = np.empty((m, N_LINKS))
best_share = np.ones((m, n))
for i in range(m):
    share_link[i] = share_at_least(cos[i][edge_tag])
    np.minimum.at(best_share[i], edge_chunk, share_link[i])
tried = 1. - (1. - best_share) ** links[None, :]
print('per querytag: middle of the best link\'s share over the chunks, as it is -> with the '
      'tries taken out (0.5 if a chunk\'s tags were unrelated draws); rank correlation with the '
      'number of tags, as it is -> with the tries taken out')
for i in range(m):
    print(f'  {i:2d}: {np.median(best_share[i]):.3f} -> {np.median(tried[i]):.3f}; '
          f'{spearman(-best_share[i], links):+.3f} -> {spearman(-tried[i], links):+.3f}')

print('\n== 3. over the querytags: the single best, or all of them ==')
single = 1. - (1. - tried.min(axis=0)) ** m
summed = stats.chi2.sf(-2. * np.log(tried).sum(axis=0), 2 * m)
z_tags = -stats.norm.ppf(np.clip(tried, 1e-300, 1. - 1e-16))
weight = np.clip(A['description_cosines'].astype(float), 0., None)
weighted = (weight[:, None] * z_tags).sum(axis=0) / np.sqrt((weight ** 2).sum())
print(f'the single best querytag: middle {np.median(single):.3f} (0.5 if the querytags were '
      f'unrelated); all summed: middle {np.median(summed):.3f}')
between = np.corrcoef(stats.rankdata(tried, axis=1))
print(f'the querytags against each other over the chunks, rank correlation: middle '
      f'{np.median(between[np.triu_indices(m, 1)]):+.3f}, largest '
      f'{between[np.triu_indices(m, 1)].max():+.3f}')
routes = {'single best': share_at_least(-single), 'all summed': share_at_least(-summed),
          'all summed, weighted': share_at_least(weighted)}
for name, share in routes.items():
    print(f'  {name:22s} read against the chunks again; rank correlation with the number of tags '
          f'{spearman(-share, links):+.3f}')
first = {k: set(np.argsort(v, kind='stable')[:100].tolist()) for k, v in routes.items()}
print(f'  the same chunks among the first 100: single best and all summed '
      f'{len(first["single best"] & first["all summed"])}; all summed, with and without the '
      f'weight {len(first["all summed"] & first["all summed, weighted"])}')

print('\n== 4. the description and the question against the chunk descriptions ==')
d, q = A['d_description'].astype(float), A['d_question'].astype(float)
for name, v in (('query description', d), ('question', q)):
    z, bulk, spread = standing(v)
    print(f'  {name:18s} raw middle {bulk:.3f}, spread {spread:.4f}, largest {v.max():.3f}; '
          f'chunks beyond 2 and 3 spreads: {int((z > 2).sum())} and {int((z > 3).sum())} (a bell '
          f'has {n * stats.norm.sf(2):.0f} and {n * stats.norm.sf(3):.1f}); skew {stats.skew(v):+.2f}')
print(f'  the two against each other over the chunks: rank correlation {spearman(d, q):+.3f}')
zd, zq = standing(d)[0], standing(q)[0]
text = {'the better of the two': share_at_least(np.maximum(zd, zq)),
        'the two averaged': share_at_least((zd + zq) / 2.),
        'description only': share_at_least(zd)}

print('\n== 5. the tags and the description together ==')
kind_names = None
for tag_name in ('single best', 'all summed'):
    for text_name, t_share in text.items():
        both = routes[tag_name] * t_share
        order = np.argsort(both, kind='stable')[:100]
        tag_top, text_top = routes[tag_name][order] <= 0.1, t_share[order] <= 0.1
        print(f'  tags: {tag_name:11s} description: {text_name:22s} rank correlation of the two '
              f'{spearman(routes[tag_name], t_share):+.3f}; its first 100, best tenth on tags '
              f'only / description only / both / neither: {int((tag_top & ~text_top).sum()):3d} / '
              f'{int((~tag_top & text_top).sum()):3d} / {int((tag_top & text_top).sum()):3d} / '
              f'{int((~tag_top & ~text_top).sum()):3d}; same first 100 as today '
              f'{len(set(order.tolist()) & set(A["order"][:100].tolist()))}; rank correlation '
              f'with the number of tags {spearman(-both, links):+.3f}')

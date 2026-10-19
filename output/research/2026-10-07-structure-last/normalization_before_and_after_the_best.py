"""Where the arm's normalization (middle and spread, `v4_walk.standing`) holds and where it is
lost, on the made-up question's arrays (`structure_last_arrays.npz`): the middle of the tags'
number step by step, the same for the description's, and both numbers put through `standing`
once more over the chunks. No model call, no benchmark file. Run from the repo root."""
import pathlib
import sys

import numpy as np

sys.path.insert(0, 'test/artefact')
from v4_walk import standing  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8')
A = np.load(pathlib.Path('output/research/2026-10-07-structure-last') / 'structure_last_arrays.npz')
fit, edge_chunk = A['fit_of_link'].astype(float), A['edge_chunk']
centrality, n = A['centrality'].astype(float), A['tags'].size
of_tag = A['standing_of_tag'].astype(float)[:, A['eligible'].astype(bool)]

print('the tags\' number, step by step:')
print(f'  one tag against one querytag, over all graph tags: middle {np.median(of_tag):.3f}, '
      f'top 10% {np.percentile(of_tag, 90):.3f}, top 1% {np.percentile(of_tag, 99):.3f}')
print(f'  one link against one querytag, below 0 as 0: middle {np.median(fit):.3f}')
per = np.zeros((fit.shape[0], n))
for i in range(fit.shape[0]):
    np.maximum.at(per[i], edge_chunk, fit[i])
print('  the best of a chunk\'s links, one querytag: middle per querytag '
      + ' '.join(f'{m:.3f}' for m in np.median(per, axis=1)))
print(f'  the best over the querytags too: middle {np.median(per.max(axis=0)):.3f}')
tags = (centrality[:, None] * per).max(axis=0)
print(f'  with each querytag\'s cosine to the query description as its weight (the arm): middle '
      f'{np.median(tags):.3f}; largest difference from the saved tags\' number '
      f'{np.abs(tags - A["tags"]).max():.2g}')
print('  the weights: ' + ' '.join(f'{c:.3f}' for c in np.sort(centrality)[::-1]))

print('\nthe description\'s number, step by step:')
print(f'  description alone: middle {np.median(A["D"]):.3f}; question alone: middle '
      f'{np.median(A["Qs"]):.3f}; the better of the two: middle {np.median(A["text"]):.3f}')

print('\nboth numbers through the arm\'s middle and spread once more, over the chunks:')
for name in ('tags', 'text'):
    v = A[name].astype(float)
    z, bulk, spread = standing(v)
    s = np.sort(z)
    print(f'  {name:5s} middle {bulk:.3f} spread {spread:.3f} -> lowest {s[0]:.3f}  top 10% '
          f'{np.percentile(z, 90):.3f}  top 1% {np.percentile(z, 99):.3f}  4th best {s[-4]:.3f}  '
          f'best {s[-1]:.3f}')

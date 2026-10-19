"""Random chunk descriptions standing in for a query description, with no question: for each of
200 chunks drawn at random, every chunk description's standing to that chunk's description (the
text route's quantity, `v4_walk.standing` over the pool). Kept beside this file for
`structure_last_gauge.py`. Reads the graph, writes one file here, no model call, no embedding.
Run from the repo root."""
import pathlib
import sys

import numpy as np

sys.path[:0] = ['prod', 'test']
sys.stdout.reconfigure(encoding='utf-8')
from arms import artefact_v4 as V  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402

HERE = pathlib.Path('output/research/2026-10-07-structure-last')
STAND_INS = 200
SEED = 20261008

prepared = V.prepare_over_corpus('data/corpus')
vectors = prepared.chunk_vectors.astype(np.float64)
n = vectors.shape[0]
rng = np.random.default_rng(SEED)
drawn = rng.choice(n, size=STAND_INS, replace=False)
values = np.zeros((STAND_INS, n), dtype=np.float32)
for k, c in enumerate(drawn):
    row = vectors @ vectors[c]
    values[k], _, _ = WK.standing(row)
np.savez_compressed(HERE / 'structure_last_text_standins.npz', values=values, chunks=drawn)
print(f'{STAND_INS} random chunk descriptions stood in for a query description (seed {SEED}), '
      f'{n} chunks each; kept in {HERE}')

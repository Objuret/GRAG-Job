"""Embed two made-up texts with the harness's embedder and save the vectors, to compare what two
machines give for a text neither has kept. Usage: python embed_probe.py <name>, from the repo
root."""
import hashlib
import sys

import numpy as np

sys.path[:0] = ['prod', 'test']
from harness import embed  # noqa: E402

TEXTS = ['a made-up phrase about a rollback procedure for model updates',
         'why the team changed its deployment checklist after the outage']
rows, calls, tokens_in, tokens_out, seconds = embed._embed(TEXTS, 'passage', bar=False)
vectors = np.asarray(rows, dtype=np.float32)
np.save(f'output/research/2026-10-07-desktop/embed_probe_{sys.argv[1]}.npy', vectors)
print(sys.argv[1], vectors.shape, hashlib.sha256(vectors.tobytes()).hexdigest()[:16],
      [round(float(x), 7) for x in vectors[0][:4]], f'{seconds:.1f}s')

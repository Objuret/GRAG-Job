"""The made-up question: the pick when the best fit itself sets the range - every graph tag
within (1 - best) of the question tag's closest tag - beside the pick under the serving-gap
width. No gold, no test question, no model call."""
import sys
from pathlib import Path

import numpy as np

ROOT = Path('C:/Coding/exjobbet/GRAG-Job')
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'prod'), str(ROOT / 'test')]
from artefact.v4_strength import standing
import walkthrough as W

X = W.read_inputs(Path(sys.argv[1]) / 'madeup_all_same.npz')
el = np.asarray(X['eligible'], dtype=bool)
et, ec = np.asarray(X['edge_tag']), np.asarray(X['edge_chunk'])
ok = el[et]
et, ec = et[ok], ec[ok]
cos = np.asarray(X['query_tag_cosines'])
names = X['graph_tags']
pc, pt = np.asarray(X['probe_cosines']), np.asarray(X['probe_tags'])
own = pc[np.arange(pt.size), pt]
perfect = float(np.median(own))        # what an identical phrase scores on this graph

print(f'an identical phrase scores {perfect:.3f} at the median on this graph (100 graph tag names)')
print(f'{"question tag":22s} {"best":>5s} {"bulk":>5s} {"spread":>6s} | range = 1 - best: width, tags (chunks) | range = {perfect:.3f} - best: width, tags (chunks) | serving gap 0.0175: tags (chunks)')
seen = set()
for i, text in enumerate(X['query_texts']):
    if text in seen:
        continue
    seen.add(text)
    row = cos[i]
    z, bulk, spread = standing(row[el])
    best = float(row[el].max())
    cells = []
    for width in (1. - best, max(perfect - best, 0.), 0.0175):
        tags = np.flatnonzero(el & (row >= best - width))
        chunks = np.unique(ec[np.isin(et, tags)])
        cells.append(f'{width:.3f}, {tags.size} ({chunks.size})')
    print(f'{text[:22]:22s} {best:5.3f} {bulk:5.2f} {spread:6.3f} | {cells[0]:>34s} | {cells[1]:>36s} | {cells[2]:>20s}')
    width = max(perfect - best, 0.)
    tags = np.flatnonzero(el & (row >= best - width))
    order = tags[np.argsort(-row[tags])][:8]
    print('       ' + '; '.join(f'{names[t][:24]} {row[t]:.3f}' for t in order))

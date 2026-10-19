"""The made-up question: the pick when "as close as the closest" is a share of the closest
tag's own score - every graph tag scoring at least that share of it. No gold, no model call."""
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
shares = (0.97, 0.95, 0.90)
print(f'{"question tag":22s} {"best":>5s} {"bulk":>5s} | ' + ' | '.join(f'at least {int(s * 100)}% of the best: floor, tags (chunks)' for s in shares))
seen = set()
for i, text in enumerate(X['query_texts']):
    if text in seen:
        continue
    seen.add(text)
    row = cos[i]
    _, bulk, spread = standing(row[el])
    best = float(row[el].max())
    cells = []
    for s in shares:
        tags = np.flatnonzero(el & (row >= s * best))
        chunks = np.unique(ec[np.isin(et, tags)])
        cells.append(f'{s * best:.3f}, {tags.size} ({chunks.size})')
    print(f'{text[:22]:22s} {best:5.3f} {bulk:5.2f} | ' + ' | '.join(f'{c:>40s}' for c in cells))
    tags = np.flatnonzero(el & (row >= 0.95 * best))
    order = tags[np.argsort(-row[tags])][:9]
    print('       ' + '; '.join(f'{names[t][:24]} {row[t]:.3f}' for t in order))

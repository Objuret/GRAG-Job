"""How far a graph tag's own name lands from its own stored vector in the same mode (the
probes of the walk-through dump), and what a width read from that makes of the pick on the
made-up question. No gold, no test question, no model call."""
import sys
from pathlib import Path

import numpy as np

ROOT = Path('C:/Coding/exjobbet/GRAG-Job')
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'prod'), str(ROOT / 'test')]
from artefact.v4_strength import standing
import walkthrough as W

X = W.read_inputs(Path(sys.argv[1]))
el = np.asarray(X['eligible'], dtype=bool)
et, ec = np.asarray(X['edge_tag']), np.asarray(X['edge_chunk'])
ok = el[et]
et, ec = et[ok], ec[ok]
probe_tags = np.asarray(X['probe_tags'])
pc = np.asarray(X['probe_cosines'])
names = X['graph_tags']


def five(v):
    return ' / '.join(f'{x:.3f}' for x in np.percentile(v, [5, 25, 50, 75, 95]))


own, short_cos, short_spread, rank_of_own, nearer = [], [], [], [], []
for i, t in enumerate(probe_tags):
    row = pc[i]
    z, bulk, spread = standing(row[el])
    full = np.full(row.size, -np.inf)
    full[el] = z
    own.append(row[t])
    short_cos.append(1. - row[t])
    short_spread.append((1. - row[t]) / spread)
    rank_of_own.append(int((full > full[t]).sum()) + 1)
    # other graph tags at least as close as the probe's own stored tag is to 1.0
    nearer.append(int((row[el] >= row[t] - (1. - row[t])).sum()) - 1)
own, short_cos, short_spread = map(np.array, (own, short_cos, short_spread))
print(f'{len(probe_tags)} graph tag names embedded in the same mode, each against its own stored vector')
print(f'  closeness to its own tag, 5 / 25 / 50 / 75 / 95%: {five(own)}   lowest {own.min():.3f}')
print(f'  shortfall from 1.0, same percentiles:            {five(short_cos)}   largest {short_cos.max():.3f}')
print(f'  the shortfall in the list\'s own spreads:          {five(short_spread)}   largest {short_spread.max():.3f}')
print(f'  its own tag is the closest on {int((np.array(rank_of_own) == 1).sum())} of {len(probe_tags)}')
print(f'  other graph tags within one shortfall below the own tag: median {int(np.median(nearer))}, '
      f'75% {int(np.percentile(nearer, 75))}, most {max(nearer)}')
print()
widths = {'median shortfall': float(np.median(short_cos)), '95% shortfall': float(np.percentile(short_cos, 95)),
          'largest shortfall': float(short_cos.max())}
cos = np.asarray(X['query_tag_cosines'])
print('The pick on the made-up question, "equally close" = within that shortfall (in closeness, not spreads) of the closest:')
print(f'  {"question tag":28s} ' + '   '.join(f'{k} {v:.3f}: tags (chunks)' for k, v in widths.items()))
seen = set()
for i, text in enumerate(X['query_texts']):
    if text in seen:
        continue
    seen.add(text)
    row = cos[i]
    best = row[el].max()
    cells = []
    for v in widths.values():
        tags = np.flatnonzero(el & (row >= best - v))
        cells.append(f'{tags.size} ({np.unique(ec[np.isin(et, tags)]).size})')
    print(f'  {text[:28]:28s} ' + '   '.join(f'{c:>32s}' for c in cells))
    tags = np.flatnonzero(el & (row >= best - widths['95% shortfall']))
    order = tags[np.argsort(-row[tags])][:10]
    print('       ' + '; '.join(f'{names[t][:26]} {row[t]:.3f}' for t in order))

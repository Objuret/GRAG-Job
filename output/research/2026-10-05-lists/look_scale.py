"""What the scores look like in the same mode: for one question tag of the made-up question,
graph tags from the top, the middle and the bottom of its list by name; then the spread of
every list (the made-up question's and the 100 question tags of the ten). Graph tag names only;
no gold, no question text, no model call."""
import sys
from pathlib import Path

import numpy as np

ROOT = Path('C:/Coding/exjobbet/GRAG-Job')
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'prod'), str(ROOT / 'test')]
import walkthrough as W

X = W.read_inputs(Path(sys.argv[1]) / 'madeup_all_same.npz')
el = np.asarray(X['eligible'], dtype=bool)
cos = np.asarray(X['query_tag_cosines'])
names = X['graph_tags']
idx = np.flatnonzero(el)

for wanted in ('rollback procedure', 'model updates'):
    i = X['query_texts'].index(wanted)
    row = cos[i][el]
    order = np.argsort(-row)
    n = order.size
    print(f'question tag "{wanted}" against the {n} graph tags')
    for label, places in (('the five closest', order[:5]),
                          ('five at the one-in-ten mark', order[n // 10 - 2:n // 10 + 3]),
                          ('five in the middle of the list', order[n // 2 - 2:n // 2 + 3]),
                          ('the five furthest', order[-5:])):
        print(f'   {label}: ' + '; '.join(f'{names[idx[k]][:34]} {row[k]:.3f}' for k in places))
    print()

print('every list, lowest / 1% / 25% / middle / 75% / 99% / highest score:')
seen = set()
for i, text in enumerate(X['query_texts']):
    if text in seen:
        continue
    seen.add(text)
    row = cos[i][el]
    print(f'   {text[:22]:22s} ' + ' / '.join(f'{x:.2f}' for x in np.percentile(row, [0, 1, 25, 50, 75, 99, 100])))
arrays = np.load(ROOT / 'output/research/2026-10-03-evidence-design/scratch/symmetric_arrays.npz')
stats = []
for qi in range(10):
    for row in arrays[f'fits_{qi}']:
        stats.append(np.percentile(row[el], [0, 1, 25, 50, 75, 99, 100]))
stats = np.array(stats)
print('   the 100 question tags of the ten, each column the range over the 100 lists:')
for name, col in zip(('lowest', '1%', '25%', 'middle', '75%', '99%', 'highest'), stats.T):
    print(f'      {name:8s} {col.min():.2f} to {col.max():.2f}   (typical {np.median(col):.2f})')
below = [(row[el] < 0.5).mean() for qi in range(10) for row in arrays[f'fits_{qi}']]
print(f'   share of graph tags scoring under 0.5, per list: typical {np.median(below):.4f}, most {max(below):.4f}')

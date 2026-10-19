"""Two readings of "a relative %", on the made-up question and on the 100 question tags of
the ten: (a) a share of the closest tag's score, measured from zero (built: at least 95% of
it); (b) a share of the tag's own range, from its closest tag down to the middle of its list
(the top 5% of that range). Numbers only; no gold, no question text, no model call."""
import sys
from pathlib import Path

import numpy as np

ROOT = Path('C:/Coding/exjobbet/GRAG-Job')
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'prod'), str(ROOT / 'test')]
import walkthrough as W

X = W.read_inputs(Path(sys.argv[1]) / 'madeup_all_same.npz')
el = np.asarray(X['eligible'], dtype=bool)
et, ec = np.asarray(X['edge_tag']), np.asarray(X['edge_chunk'])
ok = el[et]
et, ec = et[ok], ec[ok]
cos = np.asarray(X['query_tag_cosines'])


def picks(row):
    best, middle = float(row[el].max()), float(np.median(row[el]))
    out = {}
    for name, floor in (('95% of the score', 0.95 * best),
                        ('top 5% of the range', best - 0.05 * (best - middle)),
                        ('top 10% of the range', best - 0.10 * (best - middle))):
        tags = np.flatnonzero(el & (row >= floor))
        out[name] = (floor, tags.size, np.unique(ec[np.isin(et, tags)]).size)
    return best, middle, out


print('the made-up question: floor, picked tags (their chunks)')
seen = set()
for i, text in enumerate(X['query_texts']):
    if text in seen:
        continue
    seen.add(text)
    best, middle, out = picks(cos[i])
    print(f'  {text[:20]:20s} closest {best:.3f}, middle of its list {middle:.3f} | '
          + ' | '.join(f'{name}: {floor:.3f}, {n} ({c})' for name, (floor, n, c) in out.items()))

arrays = np.load(ROOT / 'output/research/2026-10-03-evidence-design/scratch/symmetric_arrays.npz')
rows = {name: [] for name in ('95% of the score', 'top 5% of the range', 'top 10% of the range')}
for qi in range(10):
    for row in arrays[f'fits_{qi}']:
        _, _, out = picks(row)
        for name, (_, n, c) in out.items():
            rows[name].append((n, c))
print()
print('the 100 question tags of the ten: picked tags per question tag, and their chunks (5 / 25 / 50 / 75 / 95%)')
for name, values in rows.items():
    v = np.array(values)
    print(f'  {name:22s} tags ' + ' / '.join(str(int(x)) for x in np.percentile(v[:, 0], [5, 25, 50, 75, 95]))
          + '   chunks ' + ' / '.join(str(int(x)) for x in np.percentile(v[:, 1], [5, 25, 50, 75, 95])))

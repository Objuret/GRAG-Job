"""Is there a dogleg in a question tag's list of closeness values, in the same mode?

The 100 question tags of the ten smoke questions, embedded in the passage role on 2026-10-03
(`symmetric_arrays.npz`: numbers only, no text). Per list, over the eligible graph tags, sorted
from the closest down: the largest drop between neighbours among the first 30, where it sits,
and how it compares with the same statistic taken far down the same list (ranks 201-230 and
on), where no break in meaning is expected. No gold, no question text, no model call."""
import sys
from pathlib import Path

import numpy as np

ROOT = Path('C:/Coding/exjobbet/GRAG-Job')
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'prod'), str(ROOT / 'test')]
import walkthrough as W

TOP = 30
arrays = np.load(ROOT / 'output/research/2026-10-03-evidence-design/scratch/symmetric_arrays.npz')
eligible = np.asarray(W.read_inputs(Path(sys.argv[1]) / 'madeup_all_same.npz')['eligible'], dtype=bool)
lists = []
for qi in range(10):
    fits = arrays[f'fits_{qi}']
    assert fits.shape[1] == eligible.size
    for row in fits:
        lists.append(np.sort(row[eligible])[::-1])
print(f'{len(lists)} question tag lists over {int(eligible.sum())} graph tags, same mode')


def biggest(values):
    """Largest drop between neighbours, its place (1 = after the closest), and its size over
    the median drop of the same stretch."""
    gaps = values[:-1] - values[1:]
    k = int(gaps.argmax())
    return float(gaps[k]), k + 1, float(gaps[k] / np.median(gaps))


top, deep = [], []
for v in lists:
    top.append(biggest(v[:TOP + 1]))
    for start in range(200, 800, TOP):                     # twenty stretches far down the list
        deep.append(biggest(v[start:start + TOP + 1])[2])
top = np.array(top)
deep = np.array(deep)
best = np.array([v[0] for v in lists])
print()
print(f'the largest drop among the first {TOP} tags, over the median drop of those {TOP}:')
print('   in the top of the list   5 / 25 / 50 / 75 / 95%: ' + ' / '.join(f'{x:.1f}' for x in np.percentile(top[:, 2], [5, 25, 50, 75, 95])))
print('   far down the same lists  5 / 25 / 50 / 75 / 95%: ' + ' / '.join(f'{x:.1f}' for x in np.percentile(deep, [5, 25, 50, 75, 95]))
      + f'   largest {deep.max():.1f} ({deep.size} stretches)')
for name, level in (('the 95% point', np.percentile(deep, 95)), ('the largest', deep.max())):
    above = top[:, 2] > level
    print(f'   lists whose top drop stands above {name} of the far-down stretches ({level:.1f}): {int(above.sum())} of {len(lists)}')
clear = top[:, 2] > deep.max()
print()
print('where that largest drop sits (after how many tags), for the lists standing above every far-down stretch:')
places = top[clear, 1].astype(int)
for lo, hi in ((1, 1), (2, 2), (3, 5), (6, 10), (11, 20), (21, 30)):
    print(f'   after {lo}-{hi} tags: {int(((places >= lo) & (places <= hi)).sum())}')
print()
print('by how close the closest tag is:')
for lo, hi in ((0.95, 1.01), (0.90, 0.95), (0.0, 0.90)):
    sel = (best >= lo) & (best < hi)
    if sel.any():
        print(f'   closest tag {lo:.2f}-{min(hi, 1.0):.2f}: {int(sel.sum())} lists, with a drop above every far-down stretch {int((clear & sel).sum())}; '
              f'median place of the drop {int(np.median(top[sel, 1]))}, median size {np.median(top[sel, 0]):.4f}')
print()
print('twelve lists, the first 12 values (the closest first), the place of the largest drop marked with |:')
order = np.argsort(-top[:, 2])
shown = list(order[:6]) + list(order[len(order) // 2 - 3:len(order) // 2]) + list(order[-3:])
for i in shown:
    v, k = lists[i], int(top[i, 1])
    cells = [f'{x:.3f}' for x in v[:12]]
    if k <= 12:
        cells.insert(k, '|')
    print(f'   drop x{top[i, 2]:5.1f} after {k:2d}: ' + ' '.join(cells))

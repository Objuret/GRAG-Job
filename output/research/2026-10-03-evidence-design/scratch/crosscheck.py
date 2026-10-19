"""One query tag recomputed two ways: the list statistics without instrument_lib, and the
prototype's tag evidence by a plain loop over the edges against the vectorised form in
analyse.py. Numbers only."""
from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import numpy as np
from scipy.stats import norm, rankdata

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import instrument_lib as IL

CACHE = Path(os.environ.get('EVID_CACHE', r'C:\Users\jocke\AppData\Local\Temp\claude'
                            r'\c--Coding-exjobbet-GRAG-Job\232eaa9a-71a9-4684-8388-e4d07653f737'
                            r'\scratchpad'))
QUESTION, TAG = 3, 2


def main():
    d = np.load(CACHE / 'evidence_arrays.npz', allow_pickle=False)
    eligible = d['eligible']
    el = np.flatnonzero(eligible)
    x = d[f'fits_{QUESTION}'][TAG][el]
    row, arrays = IL.describe(x)
    n = x.size
    med = np.median(x)
    s = 1.4826 * np.median(np.abs(x - med))
    z = (np.sort(x)[::-1] - med) / s
    m = 1 - np.minimum(1, n * norm.sf(z) / np.arange(1, n + 1))
    print('median', med, row['median'], '| s', s, row['s_mad'])
    print('above universal', int((z > math.sqrt(2 * math.log(n))).sum()),
          row['n_above_universal_mad'])
    print('m>0 / >0.5 / >0.9', int((m > 0).sum()), int((m > .5).sum()), int((m > .9).sum()), '|',
          row['n_m_gt_0.0_mad'], row['n_m_gt_0.5_mad'], row['n_m_gt_0.9_mad'])
    sel = np.flatnonzero(eligible[d['edge_tag']])
    et = (np.cumsum(eligible) - 1)[d['edge_tag'][sel]]
    ec = d['edge_chunk'][sel]
    N, NE = d['chunk_product'].size, sel.size
    pos = np.column_stack([rankdata(d['edge_topic'][sel]) / NE]
                          + [rankdata(d['refit_means'][sel, j]) / NE for j in range(4)])
    r = d[f'readings_{QUESTION}'][TAG]
    s_edge = np.log(NE / rankdata(-(pos @ (r / r.sum()))))
    s_tag = np.log(n / rankdata(-x))
    mm = arrays['mad']
    nc = np.bincount(ec, minlength=N)
    value, m_star = np.zeros(N), np.zeros(N)
    for e in range(NE):
        c, t = ec[e], et[e]
        v = max(0.0, mm[t] * (s_tag[t] - math.log(nc[c]) + s_edge[e]))
        if v > value[c]:
            value[c], m_star[c] = v, mm[t]
    loop = np.where(value > 0, m_star * np.log(N / rankdata(-value)), 0.0)
    me = mm[et]
    path = np.maximum(me * (s_tag[et] - np.log(nc)[ec] + s_edge), 0.0)
    v2 = np.zeros(N)
    np.maximum.at(v2, ec, path)
    order = np.lexsort((-path, ec))
    first = np.ones(order.size, dtype=bool)
    first[1:] = ec[order][1:] != ec[order][:-1]
    ms2 = np.zeros(N)
    ms2[ec[order[first]]] = me[order[first]]
    vec = np.where(v2 > 0, ms2 * np.log(N / rankdata(-v2)), 0.0)
    print('loop      : nonzero', int((loop > 0).sum()), 'max', loop.max(), 'sum', loop.sum())
    print('vectorised: nonzero', int((vec > 0).sum()), 'max', vec.max(), 'sum', vec.sum())
    print('largest |difference|', float(np.abs(loop - vec).max()))


if __name__ == '__main__':
    main()

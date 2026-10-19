"""The exact chance-corrected chunk evidence of one tag handle by a plain loop over the chunks
against `instrument_lib.chance_corrected`; and the same on simulated uniform ranks, where the
probability must be uniform whatever the chunk's tag count. Numbers only."""
from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import numpy as np
from scipy.stats import kstest, rankdata, spearmanr

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import instrument_lib as IL

OLD = Path(os.environ.get('EVID_CACHE', r'C:\Users\jocke\AppData\Local\Temp\claude'
                          r'\c--Coding-exjobbet-GRAG-Job\232eaa9a-71a9-4684-8388-e4d07653f737'
                          r'\scratchpad')) / 'evidence_arrays.npz'
QUESTION, TAG = 3, 2


def main():
    old = np.load(OLD, allow_pickle=False)
    new = np.load(HERE / 'symmetric_arrays.npz', allow_pickle=False)
    eligible = old['eligible']
    el = np.flatnonzero(eligible)
    sel = np.flatnonzero(eligible[old['edge_tag']])
    et = (np.cumsum(eligible) - 1)[old['edge_tag'][sel]]
    ec = old['edge_chunk'][sel]
    N, NE, NT = old['chunk_product'].size, sel.size, el.size
    pos = np.column_stack([rankdata(old['edge_topic'][sel]) / NE]
                          + [rankdata(old['refit_means'][sel, j]) / NE for j in range(4)])
    r = old[f'readings_{QUESTION}'][TAG]
    s_edge = np.log(NE / rankdata(-(pos @ (r / r.sum()))))
    edges_of = [[] for _ in range(N)]
    for e, c in enumerate(ec):
        edges_of[c].append(e)
    for label, fit in (('asymmetric', old[f'fits_{QUESTION}'][TAG][el]),
                       ('symmetric', new[f'fits_{QUESTION}'][TAG][el])):
        s_tag = np.log(NT / rankdata(-fit))
        v, p, ev = IL.chance_corrected(s_tag[et], s_edge, ec, N)
        loop = np.empty(N)
        for c in range(N):
            ids = edges_of[c]
            best = max(s_tag[et[e]] + s_edge[e] for e in ids)
            none = 1.0
            for e in ids:
                none *= 1.0 - min(1.0, math.exp(-(best - s_edge[e])))
            loop[c] = -math.log(1.0 - none) if none < 1.0 else float('inf')
        finite = np.isfinite(loop) & np.isfinite(ev)
        print(f'{label}: largest |loop - vectorised| over {int(finite.sum())} chunks '
              f'{float(np.abs(loop[finite] - ev[finite]).max()):.2e}; evidence mean '
              f'{ev[finite].mean():.3f}, max {ev[finite].max():.2f}')
    # uniform ranks drawn at random for every edge: p must be uniform and unrelated to n_c
    rng = np.random.default_rng(5)
    n_c = np.bincount(ec, minlength=N)
    ks, rho, means = [], [], []
    for _ in range(50):
        s_tag_e = rng.exponential(size=NE)
        _, p, ev = IL.chance_corrected(s_tag_e, s_edge, ec, N)
        ks.append(kstest(p, 'uniform').statistic)
        rho.append(spearmanr(n_c, ev)[0])
        means.append(ev.mean())
    print(f'independent exponential S_tag per edge, 50 draws: KS distance of p to uniform '
          f'{np.median(ks):.4f} ({min(ks):.4f} .. {max(ks):.4f}); Spearman(n_c, evidence) '
          f'{np.median(rho):.4f} ({min(rho):.4f} .. {max(rho):.4f}); mean evidence '
          f'{np.median(means):.4f}')


if __name__ == '__main__':
    main()

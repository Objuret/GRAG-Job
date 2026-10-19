"""The break detector (`instrument_lib.gap_stats`) on synthetic lists whose truth is known."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import instrument_lib as IL

rng = np.random.default_rng(11)
N = 16609
REF = IL.spacing_reference()
print('reference under an exponential tail:', {k: round(v, 3) for k, v in REF.items()})


def run(label, make, reps=200):
    rows = []
    for _ in range(reps):
        x = make()
        med = np.median(x)
        s = IL.MAD_K * np.median(np.abs(x - med))
        rows.append(IL.gap_stats(np.sort(x)[::-1], s, REF))
    clear = [r['first_clear_break_rank'] for r in rows if r['clear_breaks_top100']]
    fisher = [r['fisher_top100_rank'] for r in rows if r['fisher_top100_p'] < 0.01]
    med = lambda k: float(np.median([r[k] for r in rows]))
    print(f'{label}: clear break on {len(clear)} of {reps} lists'
          f' (first ranks: median {np.median(clear) if clear else float("nan"):.0f},'
          f' at rank 1: {sum(c == 1 for c in clear)}, at the planted rank shown below);'
          f' Fisher top-100 p<0.01 on {len(fisher)};'
          f' largest top-50 ratio median {med("max_ratio_top50"):.2f};'
          f' spacing ratio ranks 1-50 {med("spacing_ratio_ranks_1_50"):.2f},'
          f' 51-100 {med("spacing_ratio_ranks_51_100"):.2f};'
          f' largest top-50 gap {med("largest_gap_top50_in_s"):.2f} s,'
          f' predicted {med("largest_gap_top50_predicted_in_s"):.2f} s')
    return clear


run('pure normal', lambda: rng.normal(size=N))
run('student t, 6 df', lambda: rng.standard_t(6, N))
run('normal + 3% on an exponential tail',
    lambda: np.concatenate([rng.normal(size=N - 500), 2.0 + rng.exponential(1.2, 500)]))
for k, lift in ((1, 3.0), (1, 6.0), (5, 3.0), (5, 6.0), (20, 3.0)):
    def make(k=k, lift=lift):
        x = np.concatenate([rng.normal(size=N - 500), 2.0 + rng.exponential(1.2, 500)])
        top = np.argsort(-x)[:k]
        x[top] += lift          # the k best lifted by `lift` s above the continuum
        return x
    clear = run(f'exponential tail, the {k} best lifted by {lift} s', make)
    print(f'    first clear break exactly after rank {k}: {sum(c == k for c in clear)} lists')

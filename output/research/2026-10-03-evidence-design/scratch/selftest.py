"""The estimators on synthetic lists whose truth is known, before they are read on the arrays."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import instrument_lib as IL

rng = np.random.default_rng(7)
N = 16609
KEYS = ('median', 's_mad', 'mode_hsm', 's_mirror', 'skewness', 'ks90_best_normal', 'ks90_mad',
        'ks90_mirror', 'z_top1_mad', 'z_top10_mad', 'z_top100_mad', 'n_above_universal_mad',
        'n_m_gt_0.0_mad', 'n_m_gt_0.5_mad', 'n_m_gt_0.9_mad', 'n_m_gt_0.5_mirror',
        'n_m_gt_0.9_mirror', 'n_m_gt_0.5_mirror_med', 'n_m_gt_0.9_mirror_med',
        'n_m_gt_0.5_reflection', 'n_m_gt_0.5_reflection_med', 'n_m_gt_0.9_reflection_med',
        'n_beyond_reflected_minimum', 'n_beyond_reflected_minimum_med', 'z_min_mad',
        'n_local_gt_0.5_mad', 'n_local_gt_0.9_mad', 'top100_mean_excess_in_s_mad',
        'upper_obs_over_exp_z3_mad', 'lower_obs_over_exp_z3_mad', 'fisher_g_p', 'fisher_g_rank')


def run(label, make, reps=40):
    rows = [IL.describe(make())[0] for _ in range(reps)]
    print(label)
    for k in KEYS:
        v = np.array([r[k] for r in rows], dtype=float)
        print(f'  {k:<28} med {np.median(v):9.4g}  min {v.min():9.4g}  max {v.max():9.4g}')
    p = np.array([r['fisher_g_p'] for r in rows])
    print(f'  fisher p<0.01 share {np.mean(p < 0.01):.3f}, p<0.05 share {np.mean(p < 0.05):.3f}')


run('pure normal N(0.108, 0.029^2)', lambda: rng.normal(0.108, 0.029, N))
run('normal + 5 planted at z = 8..9',
    lambda: np.concatenate([rng.normal(0.108, 0.029, N - 5),
                            0.108 + 0.029 * rng.uniform(8, 9, 5)]))
run('normal + 1 planted at z = 11.6 (an identity match)',
    lambda: np.concatenate([rng.normal(0.108, 0.029, N - 1), [0.108 + 0.029 * 11.6]]))
run('student t, 6 df, scaled', lambda: 0.108 + 0.029 * rng.standard_t(6, N))
run('exponential upper tail on 3% (smooth continuum)',
    lambda: np.concatenate([rng.normal(0.108, 0.029, N - 500),
                            0.108 + 0.029 * (2.0 + rng.exponential(1.2, 500))]))

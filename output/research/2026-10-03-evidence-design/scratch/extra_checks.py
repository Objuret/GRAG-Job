"""Checks beside A-G on the same arrays: what the raw-cosine anchor does across query tags,
whether the tag position and the edge standing are independent inside a path, and how much the
query readings move the edge standing. Numbers only. Writes extra_results.json."""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
from scipy.stats import rankdata, spearmanr

HERE = Path(__file__).resolve().parent
CACHE = Path(os.environ.get('EVID_CACHE', r'C:\Users\jocke\AppData\Local\Temp\claude'
                            r'\c--Coding-exjobbet-GRAG-Job\232eaa9a-71a9-4684-8388-e4d07653f737'
                            r'\scratchpad'))


def mmm(values):
    v = np.asarray(values, dtype=np.float64)
    return {'median': float(np.median(v)), 'min': float(v.min()), 'max': float(v.max()),
            'p05': float(np.quantile(v, 0.05)), 'p95': float(np.quantile(v, 0.95))}


def main():
    d = np.load(CACHE / 'evidence_arrays.npz', allow_pickle=False)
    eligible = d['eligible']
    el = np.flatnonzero(eligible)
    sel = np.flatnonzero(eligible[d['edge_tag']])
    et = (np.cumsum(eligible) - 1)[d['edge_tag'][sel]]
    n_edges, n_tags = sel.size, el.size
    pos = np.column_stack([rankdata(d['edge_topic'][sel]) / n_edges]
                          + [rankdata(d['refit_means'][sel, j]) / n_edges for j in range(4)])
    degree = np.bincount(et, minlength=n_tags)
    med, s, top, qof, weights = [], [], [], [], []
    rho_all, rho_head, rho_degree, standings = [], [], [], []
    for qi in range(int(d['n_questions'][0])):
        fits = d[f'fits_{qi}'][:, el]
        for j, r in enumerate(d[f'readings_{qi}']):
            x = fits[j]
            m = np.median(x)
            med.append(m)
            s.append(1.4826 * np.median(np.abs(x - m)))
            top.append(x.max())
            qof.append(qi)
            w = r / r.sum()
            weights.append(w)
            standing = pos @ w
            standings.append(rankdata(standing))
            rank_t = rankdata(-x)
            rho_all.append(spearmanr(rank_t[et], standing)[0])
            head = rank_t[et] <= 834
            rho_head.append(spearmanr(rank_t[et][head], standing[head])[0])
            rho_degree.append(spearmanr(x, degree)[0])
    med, s, top, qof = (np.array(a) for a in (med, s, top, qof))
    weights = np.array(weights)
    z_top = (top - med) / s
    depth = np.array([top[qof == q].max() - t for q, t in zip(qof, top)])
    within = [spearmanr(top[qof == q], z_top[qof == q])[0] for q in range(10)]
    corr = np.corrcoef(np.array(standings))
    off = corr[np.triu_indices(len(standings), 1)]
    equal = rankdata(pos @ np.full(5, 0.2))
    with_equal = [np.corrcoef(st, equal)[0, 1] for st in standings]
    best = np.array(standings) > n_edges * 0.99
    overlap = [(best[i] & best[j]).sum() / best[i].sum()
               for i in range(0, len(standings), 7) for j in range(i + 1, len(standings), 7)]
    readings = np.concatenate([d[f'readings_{qi}'].ravel() for qi in range(10)])
    out = {
        'raw_anchor': {
            'spearman_background_median_vs_top1_cosine': float(spearmanr(med, top)[0]),
            'spearman_background_median_vs_top1_z': float(spearmanr(med, z_top)[0]),
            'spearman_s_vs_top1_cosine': float(spearmanr(s, top)[0]),
            'best_fit_below_question_best_cosine': mmm(depth),
            'best_fit_below_question_best_in_0.002_steps': mmm(depth / 0.002),
            'one_0.002_step_in_s': mmm(0.002 / s),
            'within_question_spearman_raw_top1_vs_z_top1': mmm(within)},
        'path_independence': {
            'spearman_tag_rank_vs_edge_standing_all_edges': mmm(rho_all),
            'spearman_tag_rank_vs_edge_standing_834_best_tags': mmm(rho_head),
            'spearman_fit_vs_tag_degree': mmm(rho_degree)},
        'edge_standing_vs_readings': {
            'query_tags': len(standings),
            'distinct_reading_values': int(np.unique(readings).size),
            'readings_sum': mmm([w.sum() for qi in range(10) for w in d[f'readings_{qi}']]),
            'normalised_weight_per_facet': {
                f: mmm(weights[:, j]) for j, f in enumerate(
                    ('topic', 'temporal', 'why', 'activity', 'concreteness'))},
            'max_minus_min_normalised_weight': mmm(weights.max(1) - weights.min(1)),
            'spearman_between_two_query_tags_standings': mmm(off),
            'spearman_with_equal_weight_standing': mmm(with_equal),
            'overlap_of_best_1pct_edges_between_two_query_tags': mmm(overlap)},
    }
    pick = d['identity_pick']
    ident = d['identity_fits'].astype(np.float64)
    own = ident[np.arange(pick.size), pick]
    imed = np.median(ident[:, el], axis=1)
    isd = 1.4826 * np.median(np.abs(ident[:, el] - imed[:, None]), axis=1)
    out['identity'] = {
        'spearman_background_median_vs_own_cosine': float(spearmanr(imed, own)[0]),
        'spearman_background_median_vs_own_z': float(spearmanr(imed, (own - imed) / isd)[0])}
    (HERE / 'extra_results.json').write_text(json.dumps(out, indent=1), encoding='utf-8')
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()

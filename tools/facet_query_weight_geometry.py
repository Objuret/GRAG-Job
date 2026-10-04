"""Describe saved query-weight geometry without questions, gold or models."""
from __future__ import annotations

from collections import Counter
import hashlib
import itertools
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'output/research/2026-09-22-retrieval-matrix'
INPUTS = BASE / 'inputs'
OUT = BASE / 'query-weight-geometry'
QUANTILES = (0., .05, .1, .25, .5, .75, .9, .95, 1.)


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def distribution(values):
    values = np.asarray(values, dtype=float).ravel()
    assert len(values) and np.isfinite(values).all()
    return {'n': len(values), 'mean': float(values.mean()),
            'population_sd': float(values.std(ddof=0)),
            'quantiles_linear': {str(q): float(np.quantile(values, q)) for q in QUANTILES}}


def correlation(values):
    centered = np.asarray(values, dtype=float)
    centered = centered - centered.mean(axis=0, keepdims=True)
    cross = centered.T @ centered
    norm = np.sqrt(np.diag(cross))
    denominator = norm[:, None] * norm[None, :]
    result = np.divide(cross, denominator, out=np.full_like(cross, np.nan), where=denominator > 0)
    return [[float(x) if np.isfinite(x) else None for x in row] for row in result]


def geometry(aux):
    """Balanced two-way additive decomposition, rows=query tags, columns=facets."""
    rows = aux.mean(axis=1)
    columns = aux.mean(axis=0)
    grand = float(aux.mean())
    residual = aux - rows[:, None] - columns[None, :] + grand
    total_ss = float(np.square(aux - grand).sum())
    row_ss = float(aux.shape[1] * np.square(rows - grand).sum())
    column_ss = float(aux.shape[0] * np.square(columns - grand).sum())
    residual_ss = float(np.square(residual).sum())
    within = float(np.square(aux - rows[:, None]).mean())
    between = float(np.var(rows))
    assert np.isclose(total_ss, row_ss + column_ss + residual_ss, rtol=1e-12, atol=1e-12)
    return {
        'rows': len(aux), 'columns': aux.shape[1], 'grand_mean': grand,
        'column_means': columns.tolist(),
        'between_tag_row_mean_variance': between,
        'mean_within_tag_facet_variance': within,
        'within_to_between_variance_ratio': within / between if between else None,
        'total_ss': total_ss, 'row_ss': row_ss, 'column_ss': column_ss, 'residual_ss': residual_ss,
        'row_fraction_total_ss': row_ss / total_ss if total_ss else None,
        'facet_fraction_total_ss': column_ss / total_ss if total_ss else None,
        'residual_fraction_total_ss': residual_ss / total_ss if total_ss else None,
        'residual_mean_square_all_cells': residual_ss / aux.size,
        'residual_root_mean_square': float(np.sqrt(residual_ss / aux.size)),
        'residual_signed': distribution(residual),
        'row_mean_distribution': distribution(rows),
        'row_range_distribution': distribution(np.ptp(aux, axis=1)),
        'row_sd_distribution': distribution(aux.std(axis=1)),
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / 'results.json'
    if target.exists():
        raise ValueError('Preserve existing geometry results')
    manifest_path = INPUTS / 'cases_manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    columns = manifest['facets']
    assert columns == ['topic', 'temporal', 'why', 'activity', 'concreteness']
    blocks, per_case, hashes = [], [], {str(manifest_path.relative_to(ROOT)): sha(manifest_path),
                                      str(Path(__file__).relative_to(ROOT)): sha(Path(__file__))}
    for case in manifest['cases']:
        path = INPUTS / case['npz']
        metadata = json.loads((INPUTS / case['meta']).read_text(encoding='utf-8'))
        digest = sha(path)
        assert digest == metadata['npz_sha256']
        hashes[str(path.relative_to(ROOT))] = digest
        with np.load(path, allow_pickle=False) as archive:
            weights = archive['query_facet_weights'].copy()
        assert weights.ndim == 2 and weights.shape[1] == 5 and np.isfinite(weights).all()
        aux = weights[:, 1:]
        per_case.append({'case_id': case['case_id'], 'cohort': case['cohort'],
                         'geometry': geometry(aux), 'column_correlations': correlation(aux),
                         'topic_auxiliary_mean_correlation': correlation(np.column_stack((weights[:, 0], aux.mean(axis=1))))[0][1]})
        blocks.append(weights)
    weights = np.concatenate(blocks)
    aux = weights[:, 1:]
    centered = np.concatenate([b - b.mean(axis=0, keepdims=True) for b in blocks])
    row_ranges = np.ptp(aux, axis=1)
    pairwise = []
    for a, b in itertools.combinations(range(4), 2):
        delta = aux[:, a] - aux[:, b]
        pairwise.append({'left': columns[a + 1], 'right': columns[b + 1],
                         'signed_difference': distribution(delta),
                         'absolute_difference': distribution(np.abs(delta)),
                         'exactly_equal_rows': int(np.count_nonzero(delta == 0))})
    pooled_diffs = np.concatenate([np.abs(aux[:, a] - aux[:, b]) for a, b in itertools.combinations(range(4), 2)])
    cutoffs = [{'quantile': q, 'row_range_cutoff': float(np.quantile(row_ranges, q)),
                'rows_at_or_below': int(np.count_nonzero(row_ranges <= np.quantile(row_ranges, q)))} for q in QUANTILES]
    rowmeans = aux.mean(axis=1)
    centered_means = centered[:, 1:].mean(axis=1)
    result = {
        'cases': len(blocks), 'query_tag_rows': len(weights), 'auxiliary_facets': columns[1:],
        'rows_per_case': distribution([len(b) for b in blocks]),
        'pooled_geometry': geometry(aux),
        'column_distributions': {name: distribution(aux[:, i]) for i, name in enumerate(columns[1:])},
        'column_correlations': correlation(aux),
        'column_correlations_after_within_query_column_centering': correlation(centered[:, 1:]),
        'topic_auxiliary_mean_correlation': correlation(np.column_stack((weights[:, 0], rowmeans)))[0][1],
        'topic_auxiliary_mean_correlation_after_within_query_centering': correlation(np.column_stack((centered[:, 0], centered_means)))[0][1],
        'same_row_pairwise_differences': pairwise,
        'all_six_pairwise_absolute_differences': distribution(pooled_diffs),
        'exactly_uniform_rows': int(np.count_nonzero(row_ranges == 0)),
        'distinct_auxiliary_values_per_row_counts': dict(sorted(Counter(len(set(row)) for row in aux).items())),
        'near_uniformity_empirical_range_cutoffs': cutoffs,
        'per_case': per_case,
        'formulas': {
            'row_mean': 'r_i = mean_f U_if, across the four auxiliary facets',
            'within_variance': 'mean_i mean_f (U_if-r_i)^2, ddof=0',
            'between_variance': 'mean_i (r_i-grand_mean)^2, ddof=0',
            'additive_residual': 'E_if=U_if-r_i-c_f+grand_mean',
            'sum_of_squares': 'SS_total=4*sum_i(r_i-grand)^2 + n*sum_f(c_f-grand)^2 + sum_if E_if^2',
            'pearson': 'Centered cross product divided by column L2 norms; constant columns return null',
            'query_centering': 'Subtract each query block column mean before concatenating; retains within-query tag differences',
            'range': 'max_f U_if-min_f U_if; empirical quantiles and inclusive counts, no categorical near-uniform threshold',
            'quantiles': 'NumPy default linear interpolation',
        },
        'limitations': [
            'Descriptive geometry of saved query weights only; no gold, rankings or semantic judgments examined.',
            'Pooled statistics give each query-tag row equal weight, so queries with more tags contribute more rows.',
            'Within-query centering controls query-level offsets; it does not establish facet meaning or calibration.',
            'High column correlation can coexist with retrieval-relevant differences. Geometry alone cannot attribute label-rotation robustness.',
            'Query-side interchangeability says nothing by itself about edge-facet validity.',
            'The additive row-plus-facet decomposition is descriptive, not a fitted retrieval model or significance test.',
        ],
        'input_sha256': hashes, 'language_model_calls': 0,
    }
    target.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    summary = {k: result[k] for k in ('cases', 'query_tag_rows', 'exactly_uniform_rows',
        'column_correlations', 'column_correlations_after_within_query_column_centering',
        'topic_auxiliary_mean_correlation', 'topic_auxiliary_mean_correlation_after_within_query_centering',
        'near_uniformity_empirical_range_cutoffs')}
    summary['decomposition'] = {k: v for k, v in result['pooled_geometry'].items() if not isinstance(v, dict)}
    summary['result_sha256'] = sha(target)
    print(json.dumps(summary, allow_nan=False), flush=True)


if __name__ == '__main__':
    main()

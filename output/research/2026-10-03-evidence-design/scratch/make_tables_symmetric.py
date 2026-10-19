"""Markdown tables for the follow-up section of instrument.md from results_symmetric.json."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = json.loads((HERE / 'results_symmetric.json').read_text(encoding='utf-8'))
MODES = ('asymmetric', 'symmetric')


def f(v, d=3):
    if v is None:
        return '-'
    if isinstance(v, int) or (abs(v) >= 100 and float(v).is_integer()):
        return f'{int(v):,}'
    if abs(v) >= 100:
        return f'{v:,.0f}'
    if abs(v) >= 10:
        return f'{v:.1f}'
    if abs(v) >= 1:
        return f'{v:.2f}'
    return f'{v:.{d}f}'


def c(s, d=3):
    return '-' if s is None else f'{f(s["median"], d)} ({f(s["min"], d)} – {f(s["max"], d)})'


def two(title, items, get):
    print(f'\n**{title}**\n')
    print('| quantity | asymmetric (query role) | symmetric (passage role) |')
    print('|---|---|---|')
    for label, key in items:
        print(f'| {label} | {get("asymmetric", key)} | {get("symmetric", key)} |')


print('reference', json.dumps(R['spacing_reference']))
print('alignment', R['alignment_check_largest_difference'], R['counts'])
A = R['A']
LIST_ROWS = [
    ('bulk centre: median cosine', 'median'), ('bulk spread s', 's_mad'),
    ('skewness', 'skewness'), ('excess kurtosis', 'excess_kurtosis'),
    ('KS central 90%, best normal', 'ks90_best_normal'),
    ('KS central 90%, MAD normal', 'ks90_mad'),
    ('top-1 cosine', 'cos_top1'), ('top-10 cosine', 'cos_top10'),
    ('top-100 cosine', 'cos_top100'),
    ('top-1 z', 'z_top1_mad'), ('top-10 z', 'z_top10_mad'), ('top-100 z', 'z_top100_mad'),
    ('above the universal threshold', 'n_above_universal_mad'),
    ('m > 0.5 / m > 0.9 counts: m > 0.5', 'n_m_gt_0.5_mad'), ('m > 0.9', 'n_m_gt_0.9_mad'),
    ('observed / normal count above +3 s', 'upper_obs_over_exp_z3_mad'),
    ('observed / normal count below -3 s', 'lower_obs_over_exp_z3_mad'),
    ('tail scale (ranks 101-200), in s', 'tail_scale_in_s'),
    ('mean spacing ranks 1-50 / tail scale', 'spacing_ratio_ranks_1_50'),
    ('mean spacing ranks 51-100 / tail scale', 'spacing_ratio_ranks_51_100'),
    ('gap after rank 1, in s', 'gap_after_rank1_in_s'),
    ('gap after rank 1 / predicted', 'gap_after_rank1_over_predicted'),
    ('largest gap in the top 50, in s', 'largest_gap_top50_in_s'),
    ('rank it follows', 'largest_gap_top50_rank'),
    ('predicted at that rank, in s', 'largest_gap_top50_predicted_in_s'),
    ('largest gap / predicted', 'largest_gap_top50_over_predicted'),
    ('largest normalised spacing in the top 50 / tail scale', 'max_ratio_top50'),
    ('rank of it', 'max_ratio_top50_rank'),
    ('largest in the top 100 / tail scale', 'max_ratio_top100'),
    ('Fisher g p, top 100', 'fisher_top100_p'), ('Fisher g p, top 50', 'fisher_top50_p'),
    ('top-100 mean excess, in s', 'top100_mean_excess_in_s_mad'),
]
two("A'. fit lists, 100 query tags", LIST_ROWS, lambda m, k: c(A[m]['summary'].get(k)))
for m in MODES:
    print(m, json.dumps({k: v for k, v in A[m].items() if k != 'summary'}))
print('\n**between the modes**\n')
for k, s in A['between_modes'].items():
    print(f'| {k} | {c(s)} |')
print('top1 same on', A['top1_same_lists'])

B = R['B']
print('\n## B')
print(json.dumps({k: v for k, v in B.items() if k not in ('symmetric', 'asymmetric')}))
sym = B['symmetric']
print(json.dumps({k: v for k, v in sym.items() if k not in ('rows', 'summary')}))
for k in ('own_cos', 'own_rank', 'own_z_mad', 'best_other_cos', 'own_minus_best_other_in_s_mad',
          'median', 's_mad', 'n_above_universal_mad', 'n_m_gt_0.5_mad', 'n_m_gt_0.9_mad',
          'z_top10_mad', 'z_top100_mad', 'tail_scale_in_s', 'gap_after_rank1_in_s',
          'gap_after_rank1_over_predicted', 'max_ratio_top50', 'skewness'):
    print(f'| {k} | {c(sym["rows"].get(k))} |')
print('asymmetric identity', json.dumps({k: v for k, v in B['asymmetric'].items()
                                         if k != 'summary'}))
for k in ('gap_after_rank1_in_s', 'gap_after_rank1_over_predicted', 'tail_scale_in_s',
          'max_ratio_top50'):
    print(f'| asym {k} | {c(B["asymmetric"]["summary"].get(k))} |')

C = R['C']
two("C'. the description against the 4,808 chunk descriptions", [r for r in LIST_ROWS],
    lambda m, k: c(C[m]['summary'].get(k)))
for m in MODES:
    print(m, json.dumps({k: v for k, v in C[m].items() if k != 'summary'}))
print(json.dumps(C['between_modes']))
print('question', c(C['question_query_role']['summary']['z_top1_mad']),
      C['question_query_role']['per_question_z_top1'])

print('\n## chance correction')
for m in MODES:
    ch = R['chance'][m]
    print(f'\n**{m}**\n')
    print('| chunk value | rho(n_c), per question (mean over its tag handles) | per handle |')
    print('|---|---|---|')
    for k in ('none', 'ln_nc', 'exact', 'fit_only_none', 'fit_only_exact', 'best_fit'):
        for cnd in ('observed', 'shuffled'):
            print(f'| {k} {cnd} | {c(ch["per_question_mean_over_handles"][f"{k}_{cnd}"])} | '
                  f'{c(ch["per_handle"][f"{k}_{cnd}"])} |')
    print('exact with:', {k: c(v) for k, v in ch['spearman_exact_with'].items()})
    print('uncorrected with best edge standing:',
          c(ch['spearman_uncorrected_with_best_edge_standing']))
    print('shuffled p KS to uniform', c(ch['shuffled_p_ks_distance_to_uniform']),
          'shuffled mean', c(ch['shuffled_exact_evidence_mean']),
          'observed mean', c(ch['observed_exact_evidence_mean']))

print("\n## F'")
for m in MODES:
    F = R['F'][m]
    print(f'\n**{m}**\n')
    print('| evidence | top z | second z | id product z | id product rank | top is id product '
          '| random 99% |')
    print('|---|---|---|---|---|---|---|')
    for label, s in F['summary'].items():
        print(f'| {label} | {c(s["top_z"])} | {c(s["second_z"])} | {c(s["named_z"])} | '
              f'{c(s["named_rank"])} | {s["top_is_named"]} of 10 | {c(s["random_p99"])} |')
    print('other', {k: c(v) for k, v in F['other'].items()})
    print('| question id | tags: top z | second | id rank | text: top z | second | id rank | '
          'description alone: id rank | question alone: id rank |')
    print('|---|---|---|---|---|---|---|---|---|')
    for q in F['per_question']:
        print(f'| {q["qid"]} | {q["tags_best_fit_top_z"]:.2f} | {q["tags_best_fit_second_z"]:.2f}'
              f' | {q["tags_best_fit_named_rank"]} | {q["text_top_z"]:.2f} | '
              f'{q["text_second_z"]:.2f} | {q["text_named_rank"]} | '
              f'{q["description_alone_named_rank"]} | {q["question_alone_named_rank"]} |')

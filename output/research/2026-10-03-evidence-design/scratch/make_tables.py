"""Markdown tables for instrument.md from results.json and extra_results.json (numbers only)."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = json.loads((HERE / 'results.json').read_text(encoding='utf-8'))
X = json.loads((HERE / 'extra_results.json').read_text(encoding='utf-8'))


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


def rows(title, summary, items):
    print(f'\n**{title}**\n')
    print('| quantity | median (min – max) |')
    print('|---|---|')
    for label, key in items:
        print(f'| {label} | {c(summary[key])} |')


A = R['A']['summary']
NULL_ROWS = [
    ('bulk centre: median cosine', 'median'),
    ('bulk spread: 1.4826·MAD (s)', 's_mad'),
    ('mirror centre: half-sample mode', 'mode_hsm'),
    ('mode − median, in s', 'mode_minus_median_in_s'),
    ('mirror spread (lower half about the mode)', 's_mirror'),
    ('mirror spread / s', 's_mirror_over_s_mad'),
    ('lower half about the median, spread', 's_lower_half_median'),
    ('upper half about the median, spread', 's_upper_half_median'),
    ('skewness (third moment)', 'skewness'),
    ('quartile skewness (Bowley)', 'bowley'),
    ('excess kurtosis', 'excess_kurtosis'),
    ('lowest value, in s from the median', 'z_min_mad'),
    ('KS, central 90%, best-fitting normal', 'ks90_best_normal'),
    ('KS, central 90%, median/MAD normal', 'ks90_mad'),
    ('KS, central 90%, mode-mirror normal', 'ks90_mirror'),
    ('KS, lower half, mode-mirror half-normal', 'ks_lower_half_mirror'),
    ('top-1 cosine', 'cos_top1'), ('top-10 cosine', 'cos_top10'), ('top-100 cosine', 'cos_top100'),
    ('top-1 in z, MAD null', 'z_top1_mad'), ('top-10 in z, MAD null', 'z_top10_mad'),
    ('top-100 in z, MAD null', 'z_top100_mad'),
    ('top-1 in z, mode-mirror null', 'z_top1_mirror'),
    ('top-10 in z, mode-mirror null', 'z_top10_mirror'),
    ('top-100 in z, mode-mirror null', 'z_top100_mirror'),
    ('universal threshold, cosine (MAD null)', 'cos_universal_mad'),
    ('above the universal threshold, MAD null', 'n_above_universal_mad'),
    ('above the universal threshold, mode-mirror null', 'n_above_universal_mirror'),
    ('above the universal threshold, median-mirror null', 'n_above_universal_mirror_med'),
    ('m > 0, MAD null', 'n_m_gt_0.0_mad'), ('m > 0.5, MAD null', 'n_m_gt_0.5_mad'),
    ('m > 0.9, MAD null', 'n_m_gt_0.9_mad'),
    ('m > 0, mode-mirror null', 'n_m_gt_0.0_mirror'),
    ('m > 0.5, mode-mirror null', 'n_m_gt_0.5_mirror'),
    ('m > 0.9, mode-mirror null', 'n_m_gt_0.9_mirror'),
    ('m > 0, median-mirror null', 'n_m_gt_0.0_mirror_med'),
    ('m > 0.5, median-mirror null', 'n_m_gt_0.5_mirror_med'),
    ('m > 0.9, median-mirror null', 'n_m_gt_0.9_mirror_med'),
    ('m > 0.5, reflection about the median (no normal)', 'n_m_gt_0.5_reflection_med'),
    ('m > 0.9, reflection about the median (no normal)', 'n_m_gt_0.9_reflection_med'),
    ('beyond the reflection of the lowest value', 'n_beyond_reflected_minimum_med'),
    ('local realness > 0.5, MAD null', 'n_local_gt_0.5_mad'),
    ('local realness > 0.9, MAD null', 'n_local_gt_0.9_mad'),
    ('m > 0 below the centre, MAD null', 'n_m_gt_0_below_centre_mad'),
    ('largest m below the centre, MAD null', 'max_m_below_centre_mad'),
    ('m of the top-1, MAD null', 'm_top1_mad'),
    ('count ratio m > 0.5, mode-mirror / MAD', 'ratio_n_m_gt_0.5_mirror_over_mad'),
    ('observed / normal count above +2 s', 'upper_obs_over_exp_z2_mad'),
    ('observed / normal count above +3 s', 'upper_obs_over_exp_z3_mad'),
    ('observed / normal count above +4 s', 'upper_obs_over_exp_z4_mad'),
    ('observed / normal count below −2 s', 'lower_obs_over_exp_z2_mad'),
    ('observed / normal count below −3 s', 'lower_obs_over_exp_z3_mad'),
    ('observed / normal count below −4 s', 'lower_obs_over_exp_z4_mad'),
    ('top-100 mean excess over the 101st, in s', 'top100_mean_excess_in_s_mad'),
    ('top-1 minus top-2, in s', 'gap_top1_top2_in_s_mad'),
    ('Fisher g p-value, top-100 spacings', 'fisher_g_p'),
    ('rank after which the largest spacing falls', 'fisher_g_rank'),
]
print('## counts')
print(json.dumps(R['counts']))
print(json.dumps(R['structure']))
print(json.dumps({k: v for k, v in R['A'].items() if not k.startswith('summary')
                  and k != 'bootstrap_spread'}))
rows('A. tag fit lists, 100 query tags, 16,609 eligible graph tags each', A, NULL_ROWS)
rows('A. bootstrap spread of the null estimators (100 resamples per list)',
     R['A']['bootstrap_spread'],
     [('sd of the median, in s', 'sd_median_in_s'), ('sd of s, relative', 'sd_s_mad_rel'),
      ('sd of the half-sample mode, in s', 'sd_mode_in_s'),
      ('sd of the mirror spread, relative to s', 'sd_s_mirror_rel')])
B = R['B']
print('\n## B')
print(json.dumps({k: v for k, v in B.items() if k != 'identity_summary'}))
rows('B. the 300 identity lists', B['identity_summary'],
     [('own cosine', 'own_cos'), ('own rank', 'own_rank'), ('own z, MAD null', 'own_z_mad'),
      ('own minus best other tag, in s', 'own_minus_best_other_in_s_mad'),
      ('background median', 'median'), ('s', 's_mad'),
      ('above the universal threshold', 'n_above_universal_mad'),
      ('m > 0.5, MAD null', 'n_m_gt_0.5_mad'), ('m > 0.9, MAD null', 'n_m_gt_0.9_mad'),
      ('local realness > 0.5', 'n_local_gt_0.5_mad'),
      ('local realness > 0.9', 'n_local_gt_0.9_mad'),
      ('m > 0.5, reflection about the median', 'n_m_gt_0.5_reflection_med'),
      ('beyond the reflection of the lowest value', 'n_beyond_reflected_minimum_med'),
      ('top-100 mean excess, in s', 'top100_mean_excess_in_s_mad'),
      ('Fisher g p-value', 'fisher_g_p')])
TEXT_ROWS = [r for r in NULL_ROWS if r[1] not in ('n_m_gt_0_below_centre_mad',)]
for name in ('description', 'question'):
    cc = R['C'][name]
    rows(f'C. {name} against the 4,808 chunk descriptions, 10 questions', cc['summary'],
         TEXT_ROWS)
    print()
    print(json.dumps({k: v for k, v in cc.items() if k != 'summary'}))
print(json.dumps(R['C']['description_vs_question_cosine_spearman']))
print('\n## edge positions')
print(json.dumps(R['edge_positions']))
for null in ('mad', 'mirror'):
    D, E = R[f'D_{null}'], R[f'E_{null}']
    rows(f'D. reach per query tag, {null} null', D['per_query_tag'],
         [('graph tags with m > 0.5', 'real_tags'),
          ('chunks carrying at least one of them', 'chunks_carrying_a_real_tag'),
          ('share of them on exactly one chunk', 'share_of_real_tags_on_one_chunk'),
          ('graph tags above the universal threshold', 'tags_above_universal'),
          ('chunks carrying at least one of those', 'chunks_carrying_a_tag_above_universal'),
          ('graph tags with m > 0', 'tags_m_gt_0'), ('chunks with e > 0', 'chunks_hit')])
    print()
    print('| question id | e>0 from ≥1 | ≥2 | ≥3 | e>1 from ≥1 | ≥2 | ≥3 |')
    print('|---|---|---|---|---|---|---|')
    for q in D['per_question']:
        print(f'| {q["qid"]} | {q["chunks_hit_by_ge1_tag_handles"]:,} | '
              f'{q["chunks_hit_by_ge2_tag_handles"]:,} | {q["chunks_hit_by_ge3_tag_handles"]:,} | '
              f'{q["chunks_e_gt_1_from_ge1_tag_handles"]:,} | '
              f'{q["chunks_e_gt_1_from_ge2_tag_handles"]:,} | '
              f'{q["chunks_e_gt_1_from_ge3_tag_handles"]:,} |')
    for kind in ('tag', 'description', 'question'):
        s = E['per_handle'][kind]
        items = [('chunks with e > 0', 'nonzero'), ('chunks with e > 0.1', 'nonzero_gt_0.1'),
                 ('chunks with e > 1', 'nonzero_gt_1'), ('max e', 'max'), ('sum of e', 'sum')]
        if kind == 'tag':
            items += [('paths with m > 0', 'paths_with_m_gt_0'),
                      ('of those floored at 0', 'paths_floored_among_m_gt_0'),
                      ('m* of a hit chunk (median over chunks)', 'm_star_of_hit_chunks_median'),
                      ('hit chunks with m* > 0.5', 'hit_chunks_with_m_star_gt_0.5'),
                      ('winning path: S_tag (median)', 'median_s_tag_of_winning_path'),
                      ('winning path: S_edge (median)', 'median_s_edge_of_winning_path'),
                      ('winning path: ln n_c (median)', 'median_ln_nc_of_winning_path'),
                      ('Spearman(chunk value, S_tag), hit chunks', 'spearman_value_s_tag'),
                      ('Spearman(chunk value, S_edge), hit chunks', 'spearman_value_s_edge'),
                      ('Spearman(chunk value, ln n_c), hit chunks', 'spearman_value_ln_nc'),
                      ('top 50 chunks: distinct winning tags', 'top50_distinct_winning_tags'),
                      ('top 50 chunks: Spearman(value, S_tag)', 'top50_spearman_value_s_tag'),
                      ('top 50 chunks: Spearman(value, S_edge)', 'top50_spearman_value_s_edge')]
        rows(f'E. e per {kind} handle, {null} null', s, items)
    a = E['across_questions']
    print(f'\n**E. correlations and weights per question, {null} null**\n')
    print('| quantity | median (min – max) over the 10 questions |')
    print('|---|---|')
    for label, s in (
            ('handles per question', a['handles']),
            ('tag–tag r, the question\'s median pair', E['tag_tag_corr_median_across_questions']),
            ('tag–tag r, the question\'s largest pair', E['tag_tag_corr_max_across_questions']),
            ('tag pairs with r > 0.5', a['tag_pairs_corr_gt_0.5']),
            ('tag pairs with r > 0.9', a['tag_pairs_corr_gt_0.9']),
            ('tag pairs', a['tag_pairs']),
            ('description–question r', a['desc_question_corr']),
            ('tag–description r, the question\'s median', E['tag_desc_corr_median_across_questions']),
            ('tag–description r, the question\'s largest', E['tag_desc_corr_max_across_questions']),
            ('tag–question r, the question\'s median', E['tag_question_corr_median_across_questions']),
            ('w of a tag handle, the question\'s median', E['w_tag_median_across_questions']),
            ('w of a tag handle, the question\'s smallest', E['w_tag_min_across_questions']),
            ('w of a tag handle, the question\'s largest', E['w_tag_max_across_questions']),
            ('w of the description', a['w_description']),
            ('w of the raw question', a['w_question']),
            ('sum of w', a['sum_w']),
            ('H² / Σr (Kish; Brown)', a['kish_brown_effective']),
            ('effective number, Li & Ji', a['li_ji_effective']),
            ('effective number, Galwey', a['galwey_effective']),
            ('share of E0 from tag handles', a['E0_share_from_tag_handles']),
            ('share of E0 from the description', a['E0_share_from_description']),
            ('share of E0 from the raw question', a['E0_share_from_question']),
            ('share from tag handles, 50 highest E0', a['top50_E0_share_from_tag_handles']),
            ('Spearman(n_c, mean tag e)', a['spearman_n_c_mean_tag_e']),
            ('same without the ln n_c term', a['spearman_n_c_mean_tag_e_without_ln_nc']),
            ('same with the fits shuffled over tags', a['spearman_n_c_mean_tag_e_shuffled_fits']),
            ('shuffled, without the ln n_c term',
             a['spearman_n_c_mean_tag_e_shuffled_fits_without_ln_nc']),
            ('product: top z', a['product_top_z']), ('product: second z', a['product_second_z']),
            ('product: 99th pct of the max z, random membership', a['product_max_z_random_p99']),
            ('channel: top z', a['channel_top_z']), ('channel: second z', a['channel_second_z']),
            ('channel: 99th pct of the max z, random membership', a['channel_max_z_random_p99']),
            ('channels above that 99th pct', a['channels_above_random_p99']),
            ('size of the top channel', a['channel_top_size'])):
        print(f'| {label} | {c(s)} |')
    pooled = E['per_question']
    print(f'\npooled tag pairs {sum(q["tag_pairs"] for q in pooled)}, r > 0.5: '
          f'{sum(q["tag_pairs_corr_gt_0.5"] for q in pooled)}, r > 0.9: '
          f'{sum(q["tag_pairs_corr_gt_0.9"] for q in pooled)}')
    print(json.dumps({k: E[k] for k in E if k.startswith('product_top_is')
                      or k.startswith('channel_top_under') or k.startswith('text_handles')
                      or k.startswith('tag_handles')}))
    print(f'\n**F. per question, {null} null**\n')
    print('| question id | product z1 | z2 | top is the id\'s product | its rank | rank, tag '
          'handles only | rank, text handles only | random 99% | channel z1 | z2 | size | under '
          'the id\'s product | random 99% | channels above it |')
    print('|---|---|---|---|---|---|---|---|---|---|---|---|---|---|')
    for q in pooled:
        print(f'| {q["qid"]} | {q["product_top_z"]:.2f} | {q["product_second_z"]:.2f} | '
              f'{"yes" if q["product_top_is_named"] else "no"} | {q["named_product_rank"]} | '
              f'{q["named_product_rank_tag_only"]} | {q["named_product_rank_text_only"]} | '
              f'{q["product_max_z_random_p99"]:.2f} | {q["channel_top_z"]:.2f} | '
              f'{q["channel_second_z"]:.2f} | {q["channel_top_size"]} | '
              f'{"yes" if q["channel_top_under_named_product"] else "no"} | '
              f'{q["channel_max_z_random_p99"]:.2f} | {q["channels_above_random_p99"]} |')
    print('\nmean tag e by n_c quartile:',
          [[round(v, 2) for v in q['mean_tag_e_by_n_c_quartile']] for q in pooled])
print('\n## extra')
print(json.dumps(X))

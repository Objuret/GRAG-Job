"""The follow-up: the fit lists, the identity, the description, the product enrichment and the
chance correction with the query tags and the query description in the passage role
(symmetric) beside the query role (asymmetric). Counts and statistics only.

Reads the first collection (evidence_arrays.npz) and the passage-role arrays
(symmetric_arrays.npz, identity_passage.json); writes results_symmetric.json beside this file.
"""
from __future__ import annotations

import json
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
MODES = ('asymmetric', 'symmetric')
RANK1_CUT = float(np.log(100.0))
PERMUTATIONS = 1000
SEED = 20261003


def mmm(values):
    v = np.asarray(values, dtype=np.float64)
    v = v[np.isfinite(v)]
    if not v.size:
        return None
    return {'median': float(np.median(v)), 'min': float(v.min()), 'max': float(v.max()),
            'p05': float(np.quantile(v, 0.05)), 'p95': float(np.quantile(v, 0.95)),
            'n': int(v.size)}


def robust_z(x):
    med = np.median(x)
    s = IL.MAD_K * np.median(np.abs(x - med))
    return (x - med) / s


def upper_half(row, desc):
    """The top of the list in units of the spread of the half above the median only
    (1.4826 (Q3 - Q2)): what the pooled MAD hides when the bulk is skewed."""
    s_up = row['s_upper_half_median']
    z = (desc - row['median']) / s_up
    return {'s_upper_over_s': s_up / row['s_mad'],
            's_lower_over_s': row['s_lower_half_median'] / row['s_mad'],
            'z_top1_upper': float(z[0]), 'z_top10_upper': float(z[9]),
            'z_top100_upper': float(z[99]),
            'n_above_universal_upper': int((z > row['universal_z']).sum())}


def main():
    old = np.load(OLD, allow_pickle=False)
    new = np.load(HERE / 'symmetric_arrays.npz', allow_pickle=False)
    ident_json = json.loads((HERE / 'identity_passage.json').read_text(encoding='utf-8'))
    qids = [str(q) for q in old['qids']]
    eligible = old['eligible']
    el = np.flatnonzero(eligible)
    N_tags = el.size
    local = np.cumsum(eligible) - 1
    sel = np.flatnonzero(eligible[old['edge_tag']])
    et, ec = local[old['edge_tag'][sel]], old['edge_chunk'][sel]
    N_edges = sel.size
    chunk_product = old['chunk_product']
    product_names = [str(p) for p in old['product_names']]
    N = chunk_product.size
    n_c = np.bincount(ec, minlength=N)
    ln_nc = np.log(n_c)
    pos = np.column_stack([rankdata(old['edge_topic'][sel]) / N_edges]
                          + [rankdata(old['refit_means'][sel, j]) / N_edges for j in range(4)])
    ref = IL.spacing_reference()
    rng = np.random.default_rng(SEED)
    fits = {'asymmetric': [old[f'fits_{qi}'][:, el] for qi in range(len(qids))],
            'symmetric': [new[f'fits_{qi}'][:, el] for qi in range(len(qids))]}
    ddesc = {'asymmetric': [old[f'ddesc_{qi}'] for qi in range(len(qids))],
             'symmetric': [new[f'ddesc_{qi}'] for qi in range(len(qids))]}
    dquest = [old[f'dquest_{qi}'] for qi in range(len(qids))]
    readings = [old[f'readings_{qi}'] for qi in range(len(qids))]
    results = {'qids': qids, 'spacing_reference': ref,
               'alignment_check_largest_difference': [float(v) for v in new['alignment_check']],
               'counts': {'query_tags': int(sum(f.shape[0] for f in fits['symmetric'])),
                          'eligible_tags': int(N_tags), 'chunks': int(N),
                          'eligible_edges': int(N_edges)}}

    # the identity reference of each mode: the cosine of a graph tag's own name to its vector
    pick = old['identity_pick']
    own_asym = old['identity_fits'].astype(np.float64)[np.arange(pick.size), pick]
    own_sym = new['identity_own']
    IDENTITY_MIN = {'asymmetric': float(own_asym.min()), 'symmetric': float(own_sym.min())}
    IDENTITY_P05 = {'asymmetric': float(np.quantile(own_asym, 0.05)),
                    'symmetric': float(np.quantile(own_sym, 0.05))}
    IDENTITY_MEDIAN = {'asymmetric': float(np.median(own_asym)),
                       'symmetric': float(np.median(own_sym))}
    results['identity_reference'] = {'minimum': IDENTITY_MIN, 'p05': IDENTITY_P05,
                                     'median': IDENTITY_MEDIAN}

    # ------------------------------------------------------------ A': the fit lists
    rows = {m: [] for m in MODES}
    between = []
    for qi in range(len(qids)):
        for j in range(fits['symmetric'][qi].shape[0]):
            tops = {}
            for m in MODES:
                x = fits[m][qi][j]
                row, _ = IL.describe(x)
                desc = np.sort(x)[::-1]
                row.update(IL.gap_stats(desc, row['s_mad'], ref))
                row.update(upper_half(row, desc))
                k = int((x >= IDENTITY_MIN[m]).sum())
                row['n_ge_identity_minimum'] = k
                if 0 < k < 200:
                    # the step from the last tag at identity level down to the next tag
                    step = desc[k - 1] - desc[k]
                    row['step_below_identity_band_cos'] = float(step)
                    row['step_below_identity_band_in_s'] = float(step / row['s_mad'])
                    row['step_below_identity_band_over_predicted'] = float(
                        k * step / (row['tail_scale_in_s'] * row['s_mad']))
                rows[m].append(row)
                tops[m] = np.argsort(-x)[:100]
            a, s = fits['asymmetric'][qi][j], fits['symmetric'][qi][j]
            union = np.union1d(tops['asymmetric'], tops['symmetric'])
            between.append({
                'top100_overlap': int(np.intersect1d(tops['asymmetric'], tops['symmetric']).size),
                'top10_overlap': int(np.intersect1d(tops['asymmetric'][:10],
                                                    tops['symmetric'][:10]).size),
                'top1_same': int(tops['asymmetric'][0] == tops['symmetric'][0]),
                'symmetric_top1_rank_in_asymmetric': int((a >= a[tops['symmetric'][0]]).sum()),
                'asymmetric_top1_rank_in_symmetric': int((s >= s[tops['asymmetric'][0]]).sum()),
                'spearman_over_union_of_top100': float(spearmanr(a[union], s[union])[0]),
                'spearman_over_asymmetric_top100': float(
                    spearmanr(a[tops['asymmetric']], s[tops['asymmetric']])[0]),
                'spearman_over_all_tags': float(spearmanr(a, s)[0]),
                'union_size': int(union.size)})
    results['A'] = {}
    for m in MODES:
        r = rows[m]
        fisher = sorted(int(x['fisher_top100_rank']) for x in r if x['fisher_top100_p'] < 0.01)
        fisher50 = sorted(int(x['fisher_top50_rank']) for x in r if x['fisher_top50_p'] < 0.01)
        clear = sorted(int(x['first_clear_break_rank']) for x in r if x['clear_breaks_top100'])
        clear50 = sorted(int(x['first_clear_break_rank_top50']) for x in r
                         if x['clear_breaks_top50'])
        results['A'][m] = {
            'summary': IL.summarise(r),
            'fisher_top100_p_lt_0.01_ranks': fisher,
            'fisher_top50_p_lt_0.01_ranks': fisher50,
            'lists_with_a_clear_break_top100': len(clear),
            'first_clear_break_ranks_top100': clear,
            'lists_with_a_clear_break_top50': len(clear50),
            'first_clear_break_ranks_top50': clear50,
            # the one pre-named rank: under an exponential tail the spacing after rank 1 over
            # the tail's scale exceeds ln 100 = 4.605 with probability 0.01
            'lists_with_rank1_gap_over_predicted_gt_ln100': int(sum(
                x['gap_after_rank1_over_predicted'] > RANK1_CUT for x in r)),
            'lists_with_top1_cos_ge_0.95': int(sum(x['cos_top1'] >= 0.95 for x in r)),
            'lists_with_top1_cos_ge_0.99': int(sum(x['cos_top1'] >= 0.99 for x in r)),
            'lists_with_top1_cos_ge_identity_minimum': int(sum(
                x['cos_top1'] >= IDENTITY_MIN[m] for x in r)),
            'lists_with_top1_cos_ge_identity_p05': int(sum(
                x['cos_top1'] >= IDENTITY_P05[m] for x in r)),
            'top1_fraction_of_way_to_identity_median': mmm(
                [(x['cos_top1'] - x['median']) / (IDENTITY_MEDIAN[m] - x['median']) for x in r]),
            'tags_at_or_above_identity_minimum': mmm(
                [x['n_ge_identity_minimum'] for x in r]),
            'tags_at_or_above_identity_minimum_histogram': {
                str(k): int(sum(x['n_ge_identity_minimum'] == k for x in r))
                for k in sorted({x['n_ge_identity_minimum'] for x in r})[:12]},
            'step_below_identity_band': {
                key: mmm([x[f'step_below_identity_band_{key}'] for x in r
                          if f'step_below_identity_band_{key}' in x])
                for key in ('cos', 'in_s', 'over_predicted')},
            'step_below_identity_band_over_predicted_gt_ln100': int(sum(
                x.get('step_below_identity_band_over_predicted', 0.0) > RANK1_CUT for x in r)),
            'top1_cos_of_lists_without_an_identity_level_tag': mmm(
                [x['cos_top1'] for x in r if x['n_ge_identity_minimum'] == 0]),
            'lists_with_more_than_one_clear_break': int(sum(x['clear_breaks_top100'] > 1
                                                            for x in r))}
    results['A']['between_modes'] = IL.summarise(between)
    results['A']['top1_same_lists'] = int(sum(b['top1_same'] for b in between))

    # ------------------------------------------------------------ B': identity
    irows = ident_json['rows']
    own = new['identity_own']
    itop = new['identity_top']
    igaps = [IL.gap_stats(itop[i], irows[i]['s_mad'], ref) for i in range(len(irows))]
    for row, g in zip(irows, igaps):
        row.update(g)
    pick = old['identity_pick']
    ident_old = old['identity_fits'].astype(np.float64)[:, el]
    agaps = []
    for i in range(pick.size):
        x = ident_old[i]
        med = np.median(x)
        s = IL.MAD_K * np.median(np.abs(x - med))
        agaps.append(IL.gap_stats(np.sort(x)[::-1], s, ref))

    def identity_block(rows_, gaps_):
        clear = [int(g['first_clear_break_rank']) for g in gaps_ if g['clear_breaks_top100']]
        return {'summary': IL.summarise(gaps_),
                'lists_with_rank1_gap_over_predicted_gt_ln100': int(sum(
                    g['gap_after_rank1_over_predicted'] > RANK1_CUT for g in gaps_)),
                'lists_with_a_clear_break_top100': len(clear),
                'clear_break_after_rank_1': int(sum(c == 1 for c in clear)),
                'fisher_top100_p_lt_0.01': int(sum(g['fisher_top100_p'] < 0.01 for g in gaps_)),
                'fisher_break_after_rank_1': int(sum(
                    g['fisher_top100_p'] < 0.01 and g['fisher_top100_rank'] == 1 for g in gaps_))}

    results['B'] = {
        'probes': len(irows),
        'eligible_tags_with_a_different_readable_form':
            ident_json['eligible_tags_with_a_different_readable_form'],
        'raw_form_check': ident_json['raw_form_check'],
        'symmetric': {'own_cos': mmm(own),
                      'own_cos_below_0.99': int((own < 0.99).sum()),
                      'own_rank_1_share': float(np.mean([r['own_rank'] == 1 for r in irows])),
                      'own_rank_max': int(max(r['own_rank'] for r in irows)),
                      'rows': IL.summarise(irows), **identity_block(irows, igaps)},
        'asymmetric': identity_block(None, agaps)}

    # ------------------------------------------------------------ C': the description
    results['C'] = {}
    for m in MODES:
        drows = [IL.describe(ddesc[m][qi])[0] for qi in range(len(qids))]
        for row, qi in zip(drows, range(len(qids))):
            row.update(IL.gap_stats(np.sort(ddesc[m][qi])[::-1], row['s_mad'], ref))
            row.update(upper_half(row, np.sort(ddesc[m][qi])[::-1]))
        results['C'][m] = {
            'summary': IL.summarise(drows),
            'per_question_z_top1': [round(r['z_top1_mad'], 3) for r in drows],
            'per_question_above_universal': [r['n_above_universal_mad'] for r in drows],
            'per_question_cos_top1': [round(r['cos_top1'], 4) for r in drows],
            'questions_with_none_above_universal': int(sum(r['n_above_universal_mad'] == 0
                                                           for r in drows)),
            'questions_with_top1_z_above_noise_p99_4.60': int(sum(r['z_top1_mad'] > 4.602
                                                                 for r in drows))}
    results['C']['between_modes'] = {
        'spearman_over_all_chunks': mmm([spearmanr(ddesc['asymmetric'][qi],
                                                   ddesc['symmetric'][qi])[0]
                                         for qi in range(len(qids))]),
        'top100_overlap': mmm([np.intersect1d(np.argsort(-ddesc['asymmetric'][qi])[:100],
                                              np.argsort(-ddesc['symmetric'][qi])[:100]).size
                               for qi in range(len(qids))]),
        'top10_overlap': mmm([np.intersect1d(np.argsort(-ddesc['asymmetric'][qi])[:10],
                                             np.argsort(-ddesc['symmetric'][qi])[:10]).size
                              for qi in range(len(qids))]),
        'symmetric_vs_question_spearman': mmm([spearmanr(ddesc['symmetric'][qi],
                                                         dquest[qi])[0]
                                               for qi in range(len(qids))]),
        'asymmetric_vs_question_spearman': mmm([spearmanr(ddesc['asymmetric'][qi],
                                                          dquest[qi])[0]
                                                for qi in range(len(qids))])}
    qrows = [IL.describe(dquest[qi])[0] for qi in range(len(qids))]
    results['C']['question_query_role'] = {
        'summary': IL.summarise(qrows),
        'per_question_z_top1': [round(r['z_top1_mad'], 3) for r in qrows]}

    # ------------------------------------------------------------ chance correction, F'
    members = [np.flatnonzero(chunk_product == p) for p in range(len(product_names))]
    member_matrix = np.zeros((len(members), N))
    for i, idx in enumerate(members):
        member_matrix[i, idx] = 1.0
    sizes = member_matrix.sum(axis=1)

    def node_z(values):
        mu, sigma = values.mean(), values.std()
        if sigma == 0:
            return np.zeros(sizes.size)
        return (member_matrix @ values / sizes - mu) / (sigma / np.sqrt(sizes))

    def random_p99(values):
        mu, sigma = values.mean(), values.std()
        block = np.array([rng.permutation(values) for _ in range(PERMUTATIONS)])
        zz = ((member_matrix @ block.T) / sizes[:, None] - mu) / (sigma / np.sqrt(sizes))[:, None]
        return float(np.quantile(zz.max(axis=0), 0.99))

    def edge_standing(r):
        total = r.sum()
        w = r / total if total > 0 else np.full(5, 0.2)
        return np.log(N_edges / rankdata(-(pos @ w), method='average'))

    def chunk_values(fit, s_edge):
        """Per chunk: the best fit of its tags; the best path S_tag + S_edge; that less
        ln n_c; and the exact chance-corrected -ln p_c."""
        s_tag = np.log(N_tags / rankdata(-fit, method='average'))
        best_fit = np.full(N, -np.inf)
        np.maximum.at(best_fit, ec, fit[et])
        v, p, exact = IL.chance_corrected(s_tag[et], s_edge, ec, N)
        v_fit, _, fit_only = IL.chance_corrected(s_tag[et], np.zeros(N_edges), ec, N)
        return {'best_fit': best_fit, 'none': v, 'ln_nc': v - ln_nc, 'exact': exact,
                'p': p, 'fit_only_exact': fit_only, 'fit_only_none': v_fit}

    kinds = ('none', 'ln_nc', 'exact', 'fit_only_none', 'fit_only_exact', 'best_fit')
    results['chance'] = {}
    results['F'] = {}
    for m in MODES:
        per_handle = {f'{k}_{c}': [] for k in kinds for c in ('observed', 'shuffled')}
        per_question = {f'{k}_{c}': [] for k in kinds for c in ('observed', 'shuffled')}
        ks_shuffled, mean_shuffled, mean_observed = [], [], []
        exact_vs = {'fit_only_exact': [], 'best_edge_standing': [], 'none': []}
        none_vs_edge = []
        fq = []
        for qi in range(len(qids)):
            obs = {k: [] for k in kinds}
            shf = {k: [] for k in kinds}
            for j in range(fits[m][qi].shape[0]):
                fit = fits[m][qi][j]
                s_edge = edge_standing(readings[qi][j])
                cv = chunk_values(fit, s_edge)
                cs = chunk_values(fit[rng.permutation(N_tags)], s_edge)
                for k in kinds:
                    obs[k].append(cv[k])
                    shf[k].append(cs[k])
                    per_handle[f'{k}_observed'].append(float(spearmanr(n_c, cv[k])[0]))
                    per_handle[f'{k}_shuffled'].append(float(spearmanr(n_c, cs[k])[0]))
                ks_shuffled.append(float(kstest(cs['p'], 'uniform').statistic))
                mean_shuffled.append(float(cs['exact'].mean()))
                mean_observed.append(float(cv['exact'].mean()))
                # what the exact value keeps of the edge standing between chunks
                best_edge = np.full(N, -np.inf)
                np.maximum.at(best_edge, ec, s_edge)
                exact_vs['fit_only_exact'].append(
                    float(spearmanr(cv['exact'], cv['fit_only_exact'])[0]))
                exact_vs['best_edge_standing'].append(
                    float(spearmanr(cv['exact'], best_edge)[0]))
                exact_vs['none'].append(float(spearmanr(cv['exact'], cv['none'])[0]))
                none_vs_edge.append(float(spearmanr(cv['none'], best_edge)[0]))
            for k in kinds:
                per_question[f'{k}_observed'].append(
                    float(spearmanr(n_c, np.mean(obs[k], axis=0))[0]))
                per_question[f'{k}_shuffled'].append(
                    float(spearmanr(n_c, np.mean(shf[k], axis=0))[0]))

            # F': plain standardised standings, chunk level, positive part
            texts = {'description': ddesc[m][qi], 'question': dquest[qi]}
            variants = {
                'best_fit': [np.maximum(robust_z(b), 0.0) for b in obs['best_fit']],
                'best_tag_z': [np.maximum(
                    (b - np.median(fits[m][qi][j]))
                    / (IL.MAD_K * np.median(np.abs(fits[m][qi][j] - np.median(fits[m][qi][j])))),
                    0.0) for j, b in enumerate(obs['best_fit'])],
                'exact': [np.maximum(robust_z(e), 0.0) for e in obs['exact']]}
            text_e = {name: np.maximum(robust_z(c), 0.0) for name, c in texts.items()}
            prefix = qids[qi].split('::')[0]
            named = [i for i, n in enumerate(product_names) if n.casefold() == prefix.casefold()]
            named = named[0]
            row = {'qid': qids[qi]}

            def enrich(label, values, with_random=False):
                z = node_z(values)
                order = np.argsort(-z)
                row[f'{label}_top_z'] = float(z[order[0]])
                row[f'{label}_second_z'] = float(z[order[1]])
                row[f'{label}_top_is_named'] = bool(order[0] == named)
                row[f'{label}_named_rank'] = int(np.flatnonzero(order == named)[0]) + 1
                row[f'{label}_named_z'] = float(z[named])
                if with_random:
                    row[f'{label}_random_p99'] = random_p99(values)

            for variant, tag_e in variants.items():
                H = np.array(tag_e + [text_e['description'], text_e['question']])
                corr = np.corrcoef(H)
                w = 1.0 / np.abs(corr).sum(axis=1)
                nt = len(tag_e)
                tag_part = (w[:nt, None] * H[:nt]).sum(axis=0)
                text_part = (w[nt:, None] * H[nt:]).sum(axis=0)
                main = variant == 'best_fit'
                enrich(f'tags_{variant}', tag_part, with_random=main)
                enrich(f'tags_unweighted_{variant}', H[:nt].sum(axis=0))
                if main:
                    enrich('text', text_part, with_random=True)
                    enrich('text_unweighted', H[nt:].sum(axis=0))
                    enrich('all', tag_part + text_part)
                    enrich('description_alone', text_e['description'])
                    enrich('question_alone', text_e['question'])
                    off = corr[:nt, :nt][np.triu_indices(nt, 1)]
                    row.update(tag_tag_corr_median=float(np.median(off)),
                               tag_pairs_corr_gt_0_5=int((off > 0.5).sum()),
                               tag_pairs=int(off.size),
                               desc_question_corr=float(corr[nt, nt + 1]),
                               sum_w=float(w.sum()), handles=int(H.shape[0]),
                               tag_e_nonzero_median=float(np.median(
                                   [(e > 0).sum() for e in tag_e])),
                               spearman_n_c_tag_part=float(spearmanr(n_c, tag_part)[0]))
            fq.append(row)
        results['chance'][m] = {
            'per_handle': {k: mmm(v) for k, v in per_handle.items()},
            'per_question_mean_over_handles': {k: mmm(v) for k, v in per_question.items()},
            'spearman_exact_with': {k: mmm(v) for k, v in exact_vs.items()},
            'spearman_uncorrected_with_best_edge_standing': mmm(none_vs_edge),
            'shuffled_p_ks_distance_to_uniform': mmm(ks_shuffled),
            'shuffled_exact_evidence_mean': mmm(mean_shuffled),
            'observed_exact_evidence_mean': mmm(mean_observed)}
        labels = sorted({k.rsplit('_top_z', 1)[0] for k in fq[0] if k.endswith('_top_z')})
        results['F'][m] = {
            'per_question': fq,
            'summary': {label: {
                'top_z': mmm([q[f'{label}_top_z'] for q in fq]),
                'second_z': mmm([q[f'{label}_second_z'] for q in fq]),
                'named_z': mmm([q[f'{label}_named_z'] for q in fq]),
                'named_rank': mmm([q[f'{label}_named_rank'] for q in fq]),
                'top_is_named': int(sum(q[f'{label}_top_is_named'] for q in fq)),
                'random_p99': (mmm([q[f'{label}_random_p99'] for q in fq])
                               if f'{label}_random_p99' in fq[0] else None)}
                for label in labels},
            'other': {k: mmm([q[k] for q in fq]) for k in (
                'tag_tag_corr_median', 'tag_pairs_corr_gt_0_5', 'desc_question_corr', 'sum_w',
                'tag_e_nonzero_median', 'spearman_n_c_tag_part')}}

    (HERE / 'results_symmetric.json').write_text(json.dumps(results, indent=1), encoding='utf-8')
    print('analyse_symmetric: wrote', HERE / 'results_symmetric.json')


if __name__ == '__main__':
    main()

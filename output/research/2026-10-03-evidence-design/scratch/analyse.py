"""Instrument measurement A-G on the collected arrays (collect.py). Counts and statistics only:
no question, tag or description text exists in the arrays, and none is printed or written.

Writes results.json beside this file.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
from scipy.stats import rankdata, spearmanr

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import instrument_lib as IL

CACHE = Path(os.environ.get('EVID_CACHE', r'C:\Users\jocke\AppData\Local\Temp\claude'
                            r'\c--Coding-exjobbet-GRAG-Job\232eaa9a-71a9-4684-8388-e4d07653f737'
                            r'\scratchpad'))
NULLS = ('mad', 'mirror')          # the two nulls the prototype (E, F) is run under
ALL_NULLS = ('mad', 'mirror', 'mirror_med', 'reflection', 'reflection_med')
PERMUTATIONS = 2000
BOOTSTRAP_DRAWS = 100
SEED = 20261003


def med_min_max(values):
    v = np.asarray(values, dtype=np.float64)
    v = v[np.isfinite(v)]
    if not v.size:
        return None
    return {'median': float(np.median(v)), 'min': float(v.min()), 'max': float(v.max()),
            'p05': float(np.quantile(v, 0.05)), 'p95': float(np.quantile(v, 0.95)),
            'n': int(v.size)}


def li_ji(corr):
    """Effective number of independent variables from the eigenvalues of their correlation
    matrix: sum_i [1(l_i >= 1) + (l_i - floor(l_i))] (Li & Ji 2005)."""
    lam = np.abs(np.linalg.eigvalsh(corr))
    return float(np.sum((lam >= 1).astype(float) + (lam - np.floor(lam))))


def galwey(corr):
    """(sum sqrt(l))^2 / sum l over the positive eigenvalues (Galwey 2009)."""
    lam = np.clip(np.linalg.eigvalsh(corr), 0, None)
    return float(np.sum(np.sqrt(lam)) ** 2 / np.sum(lam))


def kish(corr):
    """H^2 / sum_ij r_ij: the number of independent terms whose sum has the same variance as
    the sum of the H correlated ones (the design effect of Kish 1965; the scaling Brown 1975
    applies to Fisher's sum of log p-values)."""
    return float(corr.shape[0] ** 2 / corr.sum())


def main():
    data = np.load(CACHE / 'evidence_arrays.npz', allow_pickle=False)
    qids = [str(q) for q in data['qids']]
    eligible = data['eligible']
    edge_tag, edge_chunk = data['edge_tag'], data['edge_chunk']
    edge_topic, refit = data['edge_topic'], data['refit_means']
    chunk_product, product_names = data['chunk_product'], [str(p) for p in data['product_names']]
    channel_ptr, channels = data['channel_ptr'], data['channels']
    N = chunk_product.size
    el_tags = np.flatnonzero(eligible)
    N_tags = el_tags.size
    tag_local = np.cumsum(eligible) - 1
    sel = np.flatnonzero(eligible[edge_tag])
    et, ec = tag_local[edge_tag[sel]], edge_chunk[sel]
    N_edges = sel.size
    n_c = np.bincount(ec, minlength=N)
    tag_degree = np.bincount(et, minlength=N_tags)
    ln_nc = np.log(np.maximum(n_c, 1))
    rng = np.random.default_rng(SEED)
    results = {'counts': {'chunks': int(N), 'eligible_tags': int(N_tags),
                          'eligible_edges': int(N_edges), 'questions': len(qids),
                          'chunks_without_eligible_edge': int((n_c == 0).sum()),
                          'tags_on_one_chunk': int((tag_degree == 1).sum()),
                          'share_of_tags_on_one_chunk': float((tag_degree == 1).mean()),
                          'n_c_median': float(np.median(n_c)), 'n_c_min': int(n_c.min()),
                          'n_c_max': int(n_c.max())},
               'qids': qids}

    # ---------------------------------------------------------------- A: fit lists
    tag_rows, tag_arrays, tag_meta, boot_rows = [], [], [], []
    for qi in range(len(qids)):
        fits = data[f'fits_{qi}'][:, el_tags]
        side = data[f'side_{qi}']
        readings = data[f'readings_{qi}']
        for j in range(fits.shape[0]):
            row, arrays = IL.describe(fits[j])
            tag_rows.append(row)
            tag_arrays.append(arrays)
            tag_meta.append({'q': qi, 'j': j, 'side': int(side[j]), 'readings': readings[j]})
            boot_rows.append(IL.bootstrap_null_spread(fits[j], rng, BOOTSTRAP_DRAWS))
    breaks = sorted((r['fisher_g_p'], r['fisher_g_rank']) for r in tag_rows
                    if r['fisher_g_p'] < 0.01)
    results['A'] = {'query_tags': len(tag_rows),
                    'per_question': [int(data[f'fits_{qi}'].shape[0]) for qi in range(len(qids))],
                    'description_side': int(sum(m['side'] == 0 for m in tag_meta)),
                    'question_side': int(sum(m['side'] == 1 for m in tag_meta)),
                    'repeated_across_lists': int(sum(int(data[f'dup_{qi}'][0])
                                                     for qi in range(len(qids)))),
                    'readings_sum_zero': int(sum(m['readings'].sum() == 0 for m in tag_meta)),
                    'summary': IL.summarise(tag_rows),
                    'summary_description_side': IL.summarise(
                        [r for r, m in zip(tag_rows, tag_meta) if m['side'] == 0]),
                    'summary_question_side': IL.summarise(
                        [r for r, m in zip(tag_rows, tag_meta) if m['side'] == 1]),
                    'bootstrap_spread': IL.summarise(boot_rows),
                    'fisher_g_share_p_lt_0.01': float(np.mean([r['fisher_g_p'] < 0.01
                                                               for r in tag_rows])),
                    'fisher_g_breaks_p_lt_0.01_ranks': [int(r) for _, r in breaks],
                    'fisher_g_share_break_after_rank1': float(np.mean(
                        [r['fisher_g_p'] < 0.01 and r['fisher_g_rank'] == 1 for r in tag_rows])),
                    'query_tags_with_zero_real': {
                        f'{name}_m_gt_{cut}': int(sum(r[f'n_m_gt_{cut}_{name}'] == 0
                                                      for r in tag_rows))
                        for name in ALL_NULLS for cut in (0.0, 0.5, 0.9)},
                    'query_tags_with_over_1000_real': {
                        f'{name}_m_gt_{cut}': int(sum(r[f'n_m_gt_{cut}_{name}'] > 1000
                                                      for r in tag_rows))
                        for name in ALL_NULLS for cut in (0.5, 0.9)}}

    # ---------------------------------------------------------------- B: identity reference
    pick = data['identity_pick']
    ident = data['identity_fits'].astype(np.float64)
    own = ident[np.arange(pick.size), pick]
    ident_el = ident[:, el_tags]
    own_local = tag_local[pick]
    id_rows = []
    for i in range(pick.size):
        row, arrays = IL.describe(ident_el[i])
        x = ident_el[i]
        row['own_cos'] = float(own[i])
        row['own_rank'] = int((x >= own[i]).sum())
        for name in NULLS:
            loc, scale = ((row['median'], row['s_mad']) if name == 'mad'
                          else (row['mode_hsm'], row['s_mirror']))
            row[f'own_z_{name}'] = float((own[i] - loc) / scale)
            row[f'own_m_{name}'] = float(arrays[name][own_local[i]])
        row['own_minus_best_other_in_s_mad'] = float(
            (own[i] - np.max(np.delete(x, own_local[i]))) / row['s_mad'])
        id_rows.append(row)
    id_level = float(np.median(own))
    frac1 = [(r['cos_top1'] - r['median']) / (id_level - r['median']) for r in tag_rows]
    frac10 = [(r['cos_top10'] - r['median']) / (id_level - r['median']) for r in tag_rows]
    results['B'] = {
        'probes': int(pick.size),
        'identity_cos': med_min_max(own),
        'identity_summary': IL.summarise(id_rows),
        'own_rank_1_share': float(np.mean([r['own_rank'] == 1 for r in id_rows])),
        'own_rank_le_10_share': float(np.mean([r['own_rank'] <= 10 for r in id_rows])),
        'fisher_g_share_p_lt_0.01': float(np.mean([r['fisher_g_p'] < 0.01 for r in id_rows])),
        'fisher_g_share_break_after_rank1': float(np.mean(
            [r['fisher_g_p'] < 0.01 and r['fisher_g_rank'] == 1 for r in id_rows])),
        'query_top1_fraction_of_way_to_identity': med_min_max(frac1),
        'query_top10_fraction_of_way_to_identity': med_min_max(frac10),
        'query_top1_cos': med_min_max([r['cos_top1'] for r in tag_rows]),
        'query_top1_at_or_above_identity_p05': int(sum(
            r['cos_top1'] >= float(np.quantile(own, 0.05)) for r in tag_rows)),
        'query_top1_at_or_above_identity_median': int(sum(
            r['cos_top1'] >= id_level for r in tag_rows)),
    }

    # ---------------------------------------------------------------- C: text handles
    text_rows = {'description': [], 'question': []}
    text_arrays = {'description': [], 'question': []}
    for qi in range(len(qids)):
        for name, key in (('description', 'ddesc'), ('question', 'dquest')):
            row, arrays = IL.describe(data[f'{key}_{qi}'])
            text_rows[name].append(row)
            text_arrays[name].append(arrays)
    results['C'] = {name: {'summary': IL.summarise(rows),
                           'fisher_g_share_p_lt_0.01': float(np.mean(
                               [r['fisher_g_p'] < 0.01 for r in rows])),
                           'per_question': {
                               f'n_m_gt_{cut}_{null}': [r[f'n_m_gt_{cut}_{null}'] for r in rows]
                               for null in ALL_NULLS for cut in (0.5, 0.9)},
                           'per_question_z_top1_mad': [round(r['z_top1_mad'], 3) for r in rows],
                           'per_question_m_top1_mad': [round(r['m_top1_mad'], 3) for r in rows],
                           'per_question_n_above_universal_mad': [r['n_above_universal_mad']
                                                                  for r in rows]}
                    for name, rows in text_rows.items()}
    results['C']['description_vs_question_cosine_spearman'] = med_min_max(
        [spearmanr(data[f'ddesc_{qi}'], data[f'dquest_{qi}'])[0] for qi in range(len(qids))])

    # ---------------------------------------------------------------- edge positions (E)
    pos = np.column_stack([rankdata(edge_topic[sel]) / N_edges]
                          + [rankdata(refit[sel, j]) / N_edges for j in range(4)])
    results['edge_positions'] = {
        'columns': ['topic', 'temporal', 'why', 'activity', 'concreteness'],
        'spearman_between_columns': np.round(spearmanr(pos)[0], 3).tolist()}

    def tag_evidence(fit, m, readings, use_nc=True):
        rank_t = rankdata(-fit, method='average')
        s_tag = np.log(N_tags / rank_t)
        total = readings.sum()
        w = readings / total if total > 0 else np.full(5, 0.2)
        standing = pos @ w
        s_edge = np.log(N_edges / rankdata(-standing, method='average'))
        me = m[et]
        inner = s_tag[et] + s_edge - (ln_nc[ec] if use_nc else 0.0)
        path = np.maximum(me * inner, 0.0)
        value = np.zeros(N)
        np.maximum.at(value, ec, path)
        order = np.lexsort((-path, ec))
        first = np.ones(order.size, dtype=bool)
        first[1:] = ec[order][1:] != ec[order][:-1]
        top = order[first]
        m_star = np.zeros(N)
        m_star[ec[top]] = me[top]
        hit = value > 0
        position = rankdata(-value, method='average')
        e = np.where(hit, m_star * np.log(N / position), 0.0)
        parts = {}
        if hit.sum() > 2:
            win = np.full(N, -1, dtype=np.int64)
            win[ec[top]] = top
            wh = win[hit]
            for label, column in (('s_tag', s_tag[et][wh]), ('s_edge', s_edge[wh]),
                                  ('ln_nc', ln_nc[hit]), ('m_star', m_star[hit])):
                parts[f'median_{label}_of_winning_path'] = float(np.median(column))
                parts[f'spearman_value_{label}'] = (float(spearmanr(value[hit], column)[0])
                                                    if np.ptp(column) > 0 else float('nan'))
            head = np.argsort(-value)[:50]
            head = head[value[head] > 0]
            if head.size > 2:
                wt = win[head]
                parts['top50_distinct_winning_tags'] = int(np.unique(et[wt]).size)
                for label, column in (('s_tag', s_tag[et][wt]), ('s_edge', s_edge[wt]),
                                      ('ln_nc', ln_nc[head])):
                    parts[f'top50_spearman_value_{label}'] = (
                        float(spearmanr(value[head], column)[0]) if np.ptp(column) > 0
                        else float('nan'))
                    parts[f'top50_sd_{label}'] = float(np.std(column))
        return e, {**parts, 'paths_positive': int((path > 0).sum()),
                   'paths_floored_among_m_gt_0': int(((me > 0) & (path == 0)).sum()),
                   'paths_with_m_gt_0': int((me > 0).sum()),
                   'm_star_of_hit_chunks_median': float(np.median(m_star[hit])) if hit.any()
                   else float('nan'),
                   'hit_chunks_with_m_star_gt_0.5': int((hit & (m_star > 0.5)).sum())}

    def text_evidence(cos, m):
        position = rankdata(-cos, method='average')
        return m * np.log(N / position)

    # product and channel membership
    members = [np.flatnonzero(chunk_product == p) for p in range(len(product_names))]
    owner = np.repeat(np.arange(N), np.diff(channel_ptr))
    n_channels = int(channels.max()) + 1 if channels.size else 0
    channel_members = [owner[channels == g] for g in range(n_channels)]
    member_matrix = np.zeros((len(members) + n_channels, N))
    for i, idx in enumerate(members + channel_members):
        member_matrix[i, idx] = 1.0
    sizes = member_matrix.sum(axis=1)
    n_products = len(members)
    channel_product = np.array([np.bincount(chunk_product[idx], minlength=n_products).argmax()
                                for idx in channel_members])
    results['structure'] = {'products': n_products, 'channels': n_channels,
                            'product_size': med_min_max(sizes[:n_products]),
                            'channel_size': med_min_max(sizes[n_products:]),
                            'chunks_in_a_channel': int((np.diff(channel_ptr) > 0).sum())}

    def node_z(values):
        mu, sigma = values.mean(), values.std()
        if sigma == 0:
            return np.zeros(sizes.size), mu, sigma
        return (member_matrix @ values / sizes - mu) / (sigma / np.sqrt(sizes)), mu, sigma

    for null in NULLS:
        D_rows, E_handle_rows, per_question = [], {'tag': [], 'description': [], 'question': []}, []
        for qi in range(len(qids)):
            fits = data[f'fits_{qi}'][:, el_tags]
            idx = [k for k, meta in enumerate(tag_meta) if meta['q'] == qi]
            handles, kinds, no_nc, shuffled, shuffled_no_nc = [], [], [], [], []
            for k in idx:
                m = tag_arrays[k][null]
                fit = fits[tag_meta[k]['j']]
                readings = tag_meta[k]['readings']
                e, info = tag_evidence(fit, m, readings)
                no_nc.append(tag_evidence(fit, m, readings, use_nc=False)[0])
                perm = rng.permutation(N_tags)
                shuffled.append(tag_evidence(fit[perm], m[perm], readings)[0])
                shuffled_no_nc.append(tag_evidence(fit[perm], m[perm], readings, use_nc=False)[0])
                real = m > 0.5
                carried = np.zeros(N, dtype=bool)
                carried[ec[real[et]]] = True
                loc, scale = ((tag_rows[k]['median'], tag_rows[k]['s_mad']) if null == 'mad'
                              else (tag_rows[k]['mode_hsm'], tag_rows[k]['s_mirror']))
                above = (fit - loc) / scale > tag_rows[k]['universal_z']
                carried_u = np.zeros(N, dtype=bool)
                carried_u[ec[above[et]]] = True
                D_rows.append({'real_tags': int(real.sum()),
                               'chunks_carrying_a_real_tag': int(carried.sum()),
                               'share_of_real_tags_on_one_chunk': (
                                   float((tag_degree[real] == 1).mean()) if real.any()
                                   else float('nan')),
                               'tags_above_universal': int(above.sum()),
                               'chunks_carrying_a_tag_above_universal': int(carried_u.sum()),
                               'tags_m_gt_0': int((m > 0).sum()),
                               'chunks_hit': int((e > 0).sum())})
                E_handle_rows['tag'].append({'nonzero': int((e > 0).sum()),
                                             'nonzero_gt_0.1': int((e > 0.1).sum()),
                                             'nonzero_gt_1': int((e > 1).sum()),
                                             'max': float(e.max()), 'sum': float(e.sum()),
                                             **info})
                handles.append(e)
                kinds.append('tag')
            for name, key in (('description', 'ddesc'), ('question', 'dquest')):
                e = text_evidence(data[f'{key}_{qi}'], text_arrays[name][qi][null])
                E_handle_rows[name].append({'nonzero': int((e > 0).sum()),
                                            'nonzero_gt_0.1': int((e > 0.1).sum()),
                                            'nonzero_gt_1': int((e > 1).sum()),
                                            'max': float(e.max()), 'sum': float(e.sum())})
                handles.append(e)
                kinds.append(name)
            H = np.array(handles)
            kinds = np.array(kinds)
            live = H.std(axis=1) > 0
            corr = np.corrcoef(H[live])
            lk = kinds[live]
            w = 1.0 / np.abs(corr).sum(axis=1)
            is_tag = lk == 'tag'
            tt = corr[np.ix_(is_tag, is_tag)]
            off = tt[np.triu_indices(tt.shape[0], 1)] if tt.shape[0] > 1 else np.zeros(0)
            d_at = np.flatnonzero(lk == 'description')
            q_at = np.flatnonzero(lk == 'question')
            hits = (H[kinds == 'tag'] > 0).sum(axis=0)
            hits_01 = (H[kinds == 'tag'] > 0.1).sum(axis=0)
            hits_1 = (H[kinds == 'tag'] > 1).sum(axis=0)
            weighted = w[:, None] * H[live]
            E0 = weighted.sum(axis=0)
            tag_part = weighted[is_tag].sum(axis=0) if is_tag.any() else np.zeros(N)
            text_part = E0 - tag_part
            z, mu, sigma = node_z(E0)
            zp, zc = z[:n_products], z[n_products:]
            order_p, order_c = np.argsort(-zp), np.argsort(-zc)
            prefix = qids[qi].split('::')[0]
            named = [i for i, n in enumerate(product_names) if n.casefold() == prefix.casefold()]
            named = named[0] if named else -1
            family = {}
            for label, part in (('tag_only', tag_part), ('text_only', text_part)):
                zz = node_z(part)[0][:n_products]
                oo = np.argsort(-zz)
                family[f'product_top_is_named_{label}'] = bool(oo[0] == named)
                family[f'named_product_rank_{label}'] = (
                    int(np.flatnonzero(oo == named)[0]) + 1 if named >= 0 else None)
                family[f'product_top_z_{label}'] = float(zz[oo[0]])
                family[f'product_second_z_{label}'] = float(zz[oo[1]])
            # random membership: the same node sizes, E0 shuffled over the chunks
            maxp, maxc = np.empty(PERMUTATIONS), np.empty(PERMUTATIONS)
            for start in range(0, PERMUTATIONS, 250):
                block = np.array([rng.permutation(E0) for _ in range(250)])
                zz = ((member_matrix @ block.T) / sizes[:, None] - mu) / (
                    sigma / np.sqrt(sizes))[:, None]
                maxp[start:start + 250] = zz[:n_products].max(axis=0)
                maxc[start:start + 250] = zz[n_products:].max(axis=0)
            mean_e = H[kinds == 'tag'].mean(axis=0)
            quartiles = np.quantile(n_c, [0, .25, .5, .75, 1])
            per_question.append({
                'qid': qids[qi], 'handles': int(H.shape[0]), 'live_handles': int(live.sum()),
                'tag_tag_corr': med_min_max(off) if off.size else None,
                'tag_pairs_corr_gt_0.9': int((off > 0.9).sum()),
                'tag_pairs_corr_gt_0.5': int((off > 0.5).sum()),
                'tag_pairs': int(off.size),
                'desc_question_corr': (float(corr[d_at[0], q_at[0]])
                                       if d_at.size and q_at.size else None),
                'tag_desc_corr': (med_min_max(corr[is_tag][:, d_at[0]]) if d_at.size
                                  and is_tag.any() else None),
                'tag_question_corr': (med_min_max(corr[is_tag][:, q_at[0]]) if q_at.size
                                      and is_tag.any() else None),
                'w_tag': med_min_max(w[is_tag]) if is_tag.any() else None,
                'w_description': float(w[d_at[0]]) if d_at.size else None,
                'w_question': float(w[q_at[0]]) if q_at.size else None,
                'sum_w': float(w.sum()),
                'kish_brown_effective': kish(corr),
                'li_ji_effective': li_ji(corr), 'galwey_effective': galwey(corr),
                'chunks_hit_by_ge1_tag_handles': int((hits >= 1).sum()),
                'chunks_hit_by_ge2_tag_handles': int((hits >= 2).sum()),
                'chunks_hit_by_ge3_tag_handles': int((hits >= 3).sum()),
                'chunks_e_gt_0.1_from_ge1_tag_handles': int((hits_01 >= 1).sum()),
                'chunks_e_gt_0.1_from_ge3_tag_handles': int((hits_01 >= 3).sum()),
                'chunks_e_gt_1_from_ge1_tag_handles': int((hits_1 >= 1).sum()),
                'chunks_e_gt_1_from_ge2_tag_handles': int((hits_1 >= 2).sum()),
                'chunks_e_gt_1_from_ge3_tag_handles': int((hits_1 >= 3).sum()),
                'E0_nonzero': int((E0 > 0).sum()), 'E0_max': float(E0.max()),
                'E0_mean': float(mu), 'E0_sd': float(sigma),
                'E0_share_from_tag_handles': float(tag_part.sum() / E0.sum()),
                'E0_share_from_description': (float(weighted[d_at[0]].sum() / E0.sum())
                                              if d_at.size else 0.0),
                'E0_share_from_question': (float(weighted[q_at[0]].sum() / E0.sum())
                                           if q_at.size else 0.0),
                'top50_E0_share_from_tag_handles': float(
                    tag_part[np.argsort(-E0)[:50]].sum() / E0[np.argsort(-E0)[:50]].sum()),
                'spearman_n_c_mean_tag_e': float(spearmanr(n_c, mean_e)[0]),
                'spearman_n_c_mean_tag_e_without_ln_nc': float(
                    spearmanr(n_c, np.mean(no_nc, axis=0))[0]),
                'spearman_n_c_mean_tag_e_shuffled_fits': float(
                    spearmanr(n_c, np.mean(shuffled, axis=0))[0]),
                'spearman_n_c_mean_tag_e_shuffled_fits_without_ln_nc': float(
                    spearmanr(n_c, np.mean(shuffled_no_nc, axis=0))[0]),
                'mean_tag_e_by_n_c_quartile': [
                    float(mean_e[(n_c >= lo) & (n_c <= hi)].mean())
                    for lo, hi in zip(quartiles[:-1], quartiles[1:])],
                'product_top_z': float(zp[order_p[0]]),
                'product_second_z': float(zp[order_p[1]]),
                'product_top_is_named': bool(order_p[0] == named),
                'named_product_rank': int(np.flatnonzero(order_p == named)[0]) + 1
                if named >= 0 else None,
                'named_product_z': float(zp[named]) if named >= 0 else None,
                **family,
                'product_max_z_random_p95': float(np.quantile(maxp, 0.95)),
                'product_max_z_random_p99': float(np.quantile(maxp, 0.99)),
                'product_top_z_random_share_ge': float((maxp >= zp[order_p[0]]).mean()),
                'products_above_random_p99': int((zp > np.quantile(maxp, 0.99)).sum()),
                'channel_top_z': float(zc[order_c[0]]),
                'channel_second_z': float(zc[order_c[1]]),
                'channel_top_size': int(sizes[n_products + order_c[0]]),
                'channel_top_under_named_product': bool(channel_product[order_c[0]] == named),
                'channel_max_z_random_p95': float(np.quantile(maxc, 0.95)),
                'channel_max_z_random_p99': float(np.quantile(maxc, 0.99)),
                'channel_top_z_random_share_ge': float((maxc >= zc[order_c[0]]).mean()),
                'channels_above_random_p99': int((zc > np.quantile(maxc, 0.99)).sum()),
            })
        results[f'D_{null}'] = {
            'per_query_tag': IL.summarise(D_rows),
            'query_tags_with_no_real_tag': int(sum(r['real_tags'] == 0 for r in D_rows)),
            'query_tags_with_no_hit_chunk': int(sum(r['chunks_hit'] == 0 for r in D_rows)),
            'per_question': [{k: q[k] for k in q if k == 'qid' or k.startswith('chunks_')}
                             for q in per_question]}
        scalar_keys = [k for k, v in per_question[0].items()
                       if isinstance(v, (int, float)) and not isinstance(v, bool)]
        results[f'E_{null}'] = {
            'per_handle': {kind: IL.summarise(rows) for kind, rows in E_handle_rows.items()},
            'tag_handles_all_zero': int(sum(r['nonzero'] == 0 for r in E_handle_rows['tag'])),
            'text_handles_all_zero': {kind: int(sum(r['nonzero'] == 0 for r in rows))
                                      for kind, rows in E_handle_rows.items() if kind != 'tag'},
            'text_handles_max_below_1': {kind: int(sum(r['max'] < 1 for r in rows))
                                         for kind, rows in E_handle_rows.items()
                                         if kind != 'tag'},
            'per_question': per_question,
            'across_questions': {key: med_min_max([q[key] for q in per_question
                                                   if q[key] is not None])
                                 for key in scalar_keys},
            'tag_tag_corr_median_across_questions': med_min_max(
                [q['tag_tag_corr']['median'] for q in per_question if q['tag_tag_corr']]),
            'tag_tag_corr_max_across_questions': med_min_max(
                [q['tag_tag_corr']['max'] for q in per_question if q['tag_tag_corr']]),
            'tag_desc_corr_median_across_questions': med_min_max(
                [q['tag_desc_corr']['median'] for q in per_question if q['tag_desc_corr']]),
            'tag_desc_corr_max_across_questions': med_min_max(
                [q['tag_desc_corr']['max'] for q in per_question if q['tag_desc_corr']]),
            'tag_question_corr_median_across_questions': med_min_max(
                [q['tag_question_corr']['median'] for q in per_question
                 if q['tag_question_corr']]),
            'w_tag_median_across_questions': med_min_max(
                [q['w_tag']['median'] for q in per_question if q['w_tag']]),
            'w_tag_min_across_questions': med_min_max(
                [q['w_tag']['min'] for q in per_question if q['w_tag']]),
            'w_tag_max_across_questions': med_min_max(
                [q['w_tag']['max'] for q in per_question if q['w_tag']]),
            'product_top_is_named': int(sum(q['product_top_is_named'] for q in per_question)),
            'product_top_is_named_tag_only': int(sum(q['product_top_is_named_tag_only']
                                                     for q in per_question)),
            'product_top_is_named_text_only': int(sum(q['product_top_is_named_text_only']
                                                      for q in per_question)),
            'channel_top_under_named_product': int(sum(q['channel_top_under_named_product']
                                                       for q in per_question)),
        }

    (HERE / 'results.json').write_text(json.dumps(results, indent=1), encoding='utf-8')
    print('analyse: wrote', HERE / 'results.json')


if __name__ == '__main__':
    main()

"""Exact grouped replay of the weighted retrieval: one (case, match, topology,
graph_join) family, every description/scope/recovery policy in it, every
coefficient vector at once.

Why it is the same computation: `facet_retrieval_lab.schedule` keys its depth
cache on (match, topology, graph_join, facet, description) plus a mask name
(global / area / outside); scope and recovery only combine those depths. Of
the four description settings, `multiply` ranks streams × q and the other three
rank the bare streams, so a family needs at most 2 × 3 rankings per
coefficient vector where the per-policy path computes one per policy. The
delivered order is `lexsort((id_order, advanced, depth))`, a total order
because id_order is a permutation, and `cut` can consume at most 109 chunks
(the smallest units summed to 72,000 characters), so only the first PREFIX
positions of that order are ever read. Nothing here is approximated; the
runner's gate compares every metric with the per-policy path.
"""
from __future__ import annotations

import numpy as np

import facet_retrieval_lab as L
from facet_weighted_lab import DEFAULT_COEFFICIENTS
from facet_gold90_stage_budget import cut

PREFIX = 128
FAMILY_KEYS = ('match', 'topology', 'graph_join')
POLICY_KEYS = ('description', 'scope', 'recovery')


def families(policies):
    """Group policy indices by (match, topology, graph_join); every policy must be separate_facet_sum."""
    groups = {}
    for index, policy in enumerate(policies):
        if policy['facet'] != 'separate_facet_sum':
            raise ValueError('The grouped replay only covers separate_facet_sum policies')
        groups.setdefault(tuple(policy[k] for k in FAMILY_KEYS), []).append(index)
    return groups


def max_cut_chunks(units):
    sizes = np.sort([u['serialized_chars'] for u in units.values()])
    return int(np.searchsorted(np.cumsum(sizes), 72000, side='right'))


def competition_many(values, mask=None):
    """Row-wise `facet_retrieval_lab.competition`: 1 + count of strictly greater supported values."""
    m, n = values.shape
    supported = values > 0
    if mask is not None:
        supported &= mask[None, :]
    keyed = np.where(supported, -values, np.inf)
    idx = np.argsort(keyed, axis=1)
    sorted_values = np.take_along_axis(keyed, idx, axis=1)
    first = np.concatenate([np.ones((m, 1), dtype=bool), sorted_values[:, 1:] != sorted_values[:, :-1]], axis=1)
    starts = np.where(first, np.arange(n, dtype=np.int32)[None, :], 0)
    rank_sorted = np.maximum.accumulate(starts, axis=1) + 1
    ranks = np.empty((m, n), dtype=np.int32)
    np.put_along_axis(ranks, idx, rank_sorted, axis=1)
    ranks[~supported] = n + 1
    return ranks


class FastLab:
    """Wraps a `facet_weighted_lab.WeightedLab`; owns the corpus constants."""

    def __init__(self, lab):
        self.lab = lab
        self.n = lab.n
        _, self.component_index = np.unique(lab.components, return_inverse=True)
        self.component_index = self.component_index.astype(np.int64)
        self.component_count = int(self.component_index.max()) + 1
        self.id_order = lab.id_order.astype(np.int64)
        self.ids = np.asarray(lab.ids)
        self.prefix = PREFIX
        if max_cut_chunks(lab.units) >= self.prefix:
            raise ValueError('PREFIX is not larger than the most chunks the cut can consume')

    def scores(self, case, family, betas):
        """(len(betas), n) combined scores, computed exactly as `weighted_retrieve` does per row."""
        streams = case['families'][family + ('separate_facet_streams',)]
        default = case['families'][family + ('separate_facet_sum',)]
        out = np.empty((len(betas), self.n), dtype=float)
        for wi, beta in enumerate(betas):
            beta = np.asarray(beta, dtype=float)
            if np.array_equal(beta, DEFAULT_COEFFICIENTS):
                out[wi] = default[0]
            else:
                out[wi] = np.sum(streams * (beta / DEFAULT_COEFFICIENTS)[:, None], axis=0)
        return out

    def family_metrics(self, case, family, policies, betas):
        """Return {policy_index: (len(betas), 3) recall/precision/f1} for the policies of one family."""
        n, m = self.n, len(betas)
        S = self.scores(case, family, betas)
        q = case['q']
        area = case['area_mask']
        masks = {'global': None}
        if area is not None:
            masks['area'], masks['outside'] = area, ~area
        ranks, qranks = {}, {}

        def rank(multiply, name):
            key = (multiply, name)
            if key not in ranks:
                ranks[key] = competition_many(S * q[None, :] if multiply else S, masks[name])
            return ranks[key]

        def qrank(name):
            if name not in qranks:
                qranks[name] = L.competition(q, masks[name]).astype(np.int32)[None, :]
            return qranks[name]

        def depth_for(description, name):
            d = rank(description == 'multiply', name)
            if description.startswith('independent_'):
                d = np.minimum(d, qrank(name)) if description == 'independent_union' else np.maximum(d, qrank(name))
            return d

        gold = set(self.lab.gold['questions'][case['meta']['question_id']])
        units = self.lab.units
        row_offsets = (np.arange(m, dtype=np.int64) * self.component_count)[:, None] + self.component_index[None, :]
        results = {}
        for index, policy in policies:
            description, scope, recovery = (policy[k] for k in POLICY_KEYS)
            original = depth_for(description, 'global')
            if area is not None and scope != 'all':
                local = depth_for(description, 'area')
                if scope == 'equal_depth':
                    original = np.minimum(original, local)
                elif scope == 'area_only':
                    original = local
                elif scope == 'area_first':
                    outside = depth_for(description, 'outside')
                    count = np.count_nonzero(local <= n, axis=1).astype(np.int32)[:, None]
                    original = np.where(area[None, :], local, np.where(outside <= n, count + outside, n + 1))
            if recovery == 'on':
                minima = np.full(m * self.component_count, n + 1, dtype=np.int32)
                np.minimum.at(minima, row_offsets.ravel(), original.ravel())
                depth = minima.reshape(m, self.component_count)[:, self.component_index]
                advanced = original != depth
                key = (depth.astype(np.int64) * 2 + advanced) * n + self.id_order[None, :]
            else:
                depth = original
                key = depth.astype(np.int64) * (2 * n) + self.id_order[None, :]
            supported = depth <= n
            if area is not None and scope == 'area_only':
                supported &= area[None, :]
            key = np.where(supported, key, np.iinfo(np.int64).max)
            part = np.argpartition(key, self.prefix, axis=1)[:, :self.prefix]
            part_keys = np.take_along_axis(key, part, axis=1)
            prefix = np.take_along_axis(part, np.argsort(part_keys, axis=1), axis=1)
            prefix_supported = np.take_along_axis(supported, prefix, axis=1)
            metrics = np.empty((m, 3), dtype=float)
            for wi in range(m):
                row = prefix[wi][prefix_supported[wi]]
                credit, kept, budget = cut(self.ids[row], units)
                if budget['exhausted'] and len(row) == self.prefix:
                    raise AssertionError('cut ran past the prefix')
                hits = len(gold & credit)
                r = hits / len(gold) if gold else None
                p = hits / len(credit) if credit else None
                f1 = None if r is None else 0. if p is None or p + r == 0 else 2 * p * r / (p + r)
                metrics[wi] = [np.nan if v is None else v for v in (r, p, f1)]
            results[index] = metrics
        return results

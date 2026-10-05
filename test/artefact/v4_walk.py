"""artefact_v4's walk sort: the chain of the 2026-10-05 walk-through, M1 to M7, one strength per
chunk from the tags, the description and the structure. `tools/walkthrough.py` prints from this
module and the arm sorts by it.

q is a query tag, t a graph tag, e = (t, c) an eligible edge, c a chunk; N is the eligible graph
tags, E the edges whose tag is eligible, n the chunks. Every step's PROPOSAL and every
alternative is the orchestrator's calculation. Per step the PROPOSAL, then the alternative each
switch of `chain` selects, by its name in `ALTERNATIVES`:

  M1 fit        z_q(t) = (cos(q, t) - b_q) / s_q over N, b_q the median and s_q 1.4826 times the
                median |cos - b_q| (`v4_strength.standing`); fit_q(t) = max(z_q(t), 0).
                A1: fit_q(t) = cos(q, t).
  M2 positions  pos_k(e) = the edge's average rank in column k over E (1 the smallest, ties
                sharing a rank) / |E|; the columns in ALL_FACETS order: topic = cos(tag, chunk
                description), temporal, why, activity, concreteness.
  M3 weight     share_q = readings_q over their sum, five equal shares when the sum is 0;
                R_q(e) = sum_k share_q[k] * pos_k(e); factor_q(e) = R_q(e) / 0.5, 0.5 the
                position of the middle edge; w_q(e) = fit_q(t) * factor_q(e).
                A3: five equal shares. A3b: factor 1.
                C3r, the four facets as a ranking inside one class of closeness (his
                2026-10-05 "perhaps we just use them as ranking (the 4, not topic) based on
                the most important in order from the query, per tag?" and "rank the TAGS,
                no, i am not supersure how we we that"; the form, the class and its width
                are the orchestrator's):
                class_q(t) = floor((the largest cos(q, .) over N - cos(q, t)) / d), d the
                self-difference (`self_difference`: how far a graph tag's own name, embedded
                in the tags' role, lands from its own stored vector, the largest over the
                probes); inside a class the edges are ordered by the four facets in q's
                `v4_multikey.facet_order`, each facet in classes
                floor((the column's largest - value) / the column's retrain gap), then topic,
                then cos, then the edge's index; cos'_q(e) = the largest cos
                - d * (class + place / the class's size), place counted from 0;
                fit_q(e) = max((cos'_q(e) - b_q) / s_q, 0) in place of fit_q(t), cos'_q(e)
                itself under A1. With A3b the four facets leave the weight and act through
                that ranking and through the order inside a level (M7); topic as the key
                after them is the orchestrator's, his sentence says "the 4, not topic".
                Refused with A4e. Reviewed 2026-10-05: d is the gap between the serving
                that built the stored vectors and the local one, the largest of 100 probes,
                one width for every query tag - not his "fully relative to that facets tags
                numberrange"; cos' also depends on how many edges share the class.
                C3p, the same ranking with the class a share of the closest tag's own score
                (his 2026-10-05 "on the stopgap, why not just use a relative %?"):
                d_q = (1 - EQUAL_SHARE) * the largest cos(q, .) over N, so class 0 is every
                graph tag scoring at least EQUAL_SHARE of the closest one. EQUAL_SHARE is 0.95,
                the share NVIDIA's hard-negative recipe for this embedder calls "so close to
                the positive they may actually be relevant" (the TopK-PercPos rule of
                Moreira et al. 2024); its transfer from passages to tags is the
                orchestrator's. A closest tag at or below 0 leaves that query tag unranked.
                C3s, the pick as the same thing (his 2026-10-05 "what matters is the fucking
                semantic relevance of that number for the tag"): the picked graph tags of q
                are those with cos(q, t) >= L, L the level the graph's own same-thing pairs
                score (`same_thing_level`: tags equal once lower-cased or once a final s is
                dropped; the point SAME_POINT percent of those pairs' cosines lie under).
                Only the picked edges are ranked, as in C3r, and placed between L and the
                closest tag: cos'_q(e) = the largest cos - (the largest cos - L) * place /
                the number picked. Every other edge keeps its cosine; a query tag with no
                graph tag at L or above is left as it is. The pairs, the point and the
                placement are the orchestrator's.
  M4 tags      v_q(c) = the largest w_q over c's eligible edges, 0 with none;
                centrality_q = max(cos(q, query description), 0) over the question's largest;
                T(c) = max over q of centrality_q * v_q(c).
                A4a, pooled tail: K = #{e' in E: w_q(e') >= v_q(c)}; p = 1 - (1 - K / |E|)^n_c,
                n_c the chunk's eligible edges; v*_q(c) = the k-th largest w_q over E,
                k = ceil(p * |E|), in place of v.
                A4e, per edge: K_i = #{t in N: fit_q(t) * factor_q(i) >= v_q(c)} per edge i of
                c; p = 1 - prod_i (1 - K_i / |N|); v*_q(c) = the k-th largest fit_q over N,
                k = ceil(p * |N|), in place of v.
                A4b: the sum of w_q over c's edges in place of v. A4c: centrality 1.
                A4d: the sum over q in place of the max.
                C4n: v_q(c) = 0 for every chunk; the tags leave the strength and no chunk
                has a winning edge; M7's step is then cos_noise over the median spread of
                the texts in the side.
  M5 text       D, Qs = the standings over the n chunks of cos(query description, chunk
                description) and of cos(raw question, chunk description), not clipped;
                side = max(D, Qs); S = T + side.
                A5a: S = T. A5b: side = D. A5c: side = max(D, Qs, 0).
  M6 structure  two groupings: product; near group, a connected component of the file
                adjacency with at least two chunks. Product: x = S, reference the mean of S
                over the chunks. Near: x = S - the mean of S over the chunk's product,
                reference(c) the mean of x over the chunks of c's record kind that sit in a
                near group. others(c, g) = the mean of x over g's members other than c;
                raw = others - reference; on x - reference: sigma2 = the pooled within-group
                variance, tau2 = max(0, (SSB - (G - 1) * sigma2) / (M - sum n_g^2 / M)),
                SSB = sum_g n_g * (mean_g - the mean over the memberships)^2, G the groups, M
                the memberships; trust(g) = tau2 / (tau2 + sigma2 / (n_g - 1));
                lift(c, g) = max(0, trust(g) * raw(c, g)); S' = S + the two lifts.
                A6a: S' = S. A6b: trust 1. A6c: near with reference 0.
                A6d: three groupings, product, channel and record (= near group); channel and
                record on x with reference 0, a chunk in several channels taking its largest
                lift; tau2 = max(0, SSB / M - G * sigma2 / M); S' = S + the three lifts.
  M7 order      step = cos_noise / the median of the question's s_q;
                level = floor((max S' - S') / step); the order: level; inside a level the
                chunks with a winning edge first, by its pos for temporal, why, activity,
                concreteness in the winning query tag's `v4_multikey.facet_order`, descending;
                then the chunk id.
                A7: S' descending, then the chunk id.

The winning query tag of a chunk is the one with the largest centrality_q * v_q(c), the earlier
query tag on an exact tie; its winning edge is that query tag's edge of the chunk with the
largest w_q, the earlier edge on an exact tie. Nothing is read from disk and nothing is written.
"""
from __future__ import annotations

import math

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components
from scipy.stats import rankdata

from artefact.v4_multikey import facet_order
from artefact.v4_rank import ADJUST_FACETS, ALL_FACETS
from artefact.v4_strength import best_edges, centrality, level_order, shares, standing

MIDDLE = 0.5             # M3: the position of the middle edge
FACET_COLUMNS = [ALL_FACETS.index(f) for f in ADJUST_FACETS]
GROUPINGS = ('product', 'near')
FIRST_GROUPINGS = ('product', 'channel', 'record')
STRUCTURES = ('near', 'none', 'unshrunk', 'near_zero', 'first', 'first_unshrunk',
              'first_overall')
# Each alternative as the switches of `chain` it sets: the whole chain with that one step
# exchanged.
ALTERNATIVES = {
    'A1': {'fit': 'cosine'},
    'A3': {'share': 'equal'},
    'A3b': {'share': 'none'},
    'A4a': {'chunk': 'pooled'},
    'A4b': {'chunk': 'sum'},
    'A4c': {'central': 'equal'},
    'A4d': {'tags': 'sum'},
    'A4e': {'chunk': 'per_edge'},
    'A5a': {'side': 'none'},
    'A5b': {'side': 'description'},
    'A5c': {'side': 'clipped'},
    'A6a': {'structure': 'none'},
    'A6b': {'structure': 'unshrunk'},
    'A6c': {'structure': 'near_zero'},
    'A6d': {'structure': 'first'},
    'A7': {'order': 'plain'},
}
# The steps built after the walk-through, each as the switches of `chain` it sets. None is a
# PROPOSAL of the walk-through and none one of its alternatives.
CHANGES = {
    'C3r': {'rank': 'picked'},
    'C3p': {'rank': 'percent'},
    'C3s': {'rank': 'same'},
    'C4n': {'chunk': 'none'},
}
EQUAL_SHARE = 0.95       # C3p: at least this share of the closest tag's score is class 0
SAME_POINT = 5           # C3s: the percent of the same-thing pairs' cosines under the level
PROBES = 100             # C3r: the eligible graph tag names the self-difference is measured on
PROBE_SEED = 20261005    # the draw of `tools/walkthrough.py`'s probes


# ------------------------------------------------------------------ the steps, on arrays

def positions(values):
    """Per column: each value's average rank (1 the smallest, ties sharing a rank) over the
    number of rows."""
    values = np.asarray(values, dtype=np.float64)
    if values.ndim != 2 or not values.shape[0] or not np.isfinite(values).all():
        raise ValueError('Expected a nonempty table of finite values, one row per edge')
    ranks = [rankdata(values[:, k], method='average') for k in range(values.shape[1])]
    return np.column_stack(ranks) / values.shape[0]


def draw_probes(eligible, seed=PROBE_SEED, size=PROBES):
    """`size` eligible graph tags drawn without replacement by one generator from `seed`, in
    index order."""
    pool = np.flatnonzero(np.asarray(eligible, dtype=bool))
    rng = np.random.default_rng(seed)
    return np.sort(rng.choice(pool, size=min(size, pool.size), replace=False))


def self_difference(probe_cosines, probe_tags):
    """How far a graph tag's own name lands from its own stored vector: per probe 1 - its
    cosine to its own tag. Returns the largest, the median and the smallest over the probes
    and on how many the own tag is the closest."""
    cosines = np.asarray(probe_cosines, dtype=np.float64)
    tags = np.asarray(probe_tags, dtype=np.int64)
    if cosines.ndim != 2 or tags.shape != (cosines.shape[0],) or not tags.size:
        raise ValueError('Expected one row of cosines over the graph tags per probe')
    if not np.isfinite(cosines).all():
        raise ValueError('A probe cosine is not finite')
    own = cosines[np.arange(tags.size), tags]
    short = 1. - own
    if not (short > 0).all():
        raise ValueError('A probe lands on its own stored vector exactly or beyond it')
    return {'largest': float(short.max()), 'median': float(np.median(short)),
            'smallest': float(short.min()), 'probes': int(tags.size),
            'own_tag_closest': int((cosines.argmax(axis=1) == tags).sum())}


def same_thing_pairs(names):
    """The pairs (i < j) of names that are the same thing in another spelling: equal once
    lower-cased, or equal once lower-cased and a final s dropped from every word longer than
    three letters."""
    def stem(name):
        return ' '.join(w[:-1] if w.endswith('s') and len(w) > 3 else w
                        for w in name.casefold().split())
    groups = {}
    for i, name in enumerate(names):
        groups.setdefault(stem(str(name)), []).append(i)
    return [(a, b) for group in groups.values() if len(group) > 1
            for k, a in enumerate(group) for b in group[k + 1:]]


def same_thing_level(names, vectors, eligible):
    """What two graph tags that are the same thing score against each other: the cosines of
    `same_thing_pairs` over the eligible tags' stored vectors. Returns the level (the point
    SAME_POINT percent of them lie under), their median and their number; None with no pair."""
    keep = np.flatnonzero(np.asarray(eligible, dtype=bool))
    pairs = same_thing_pairs([names[i] for i in keep])
    if not pairs:
        return None
    rows = np.asarray(vectors, dtype=np.float64)[keep]
    rows = rows / np.linalg.norm(rows, axis=1, keepdims=True)
    at = np.array(pairs, dtype=np.int64)
    scores = np.einsum('ij,ij->i', rows[at[:, 0]], rows[at[:, 1]])
    return {'level': float(np.percentile(scores, SAME_POINT)), 'median': float(np.median(scores)),
            'pairs': int(scores.size), 'point': SAME_POINT}


def facet_classes(values, gaps):
    """Per edge and facet column: floor((the column's largest - value) / the column's gap)."""
    values = np.asarray(values, dtype=np.float64)
    gaps = np.asarray(gaps, dtype=np.float64)
    if values.ndim != 2 or not values.shape[0] or gaps.shape != (values.shape[1],):
        raise ValueError('Expected one gap per facet column')
    if not np.isfinite(values).all() or not np.isfinite(gaps).all() or not (gaps > 0).all():
        raise ValueError('Expected finite facet values and positive gaps')
    return np.floor((values.max(axis=0) - values) / gaps).astype(np.int64)


def ranked_closeness(cosine, best, width, facet_class, order, topic):
    """C3r for one query tag, per edge: the class of the edge's tag below `best`, the edge's
    place inside its class (0 first) under the facet classes in `order`, then topic
    descending, then the cosine descending, then the edge's index, and the cosine that place
    gives it: best - width * (class + place / the class's size)."""
    cosine = np.asarray(cosine, dtype=np.float64)
    topic = np.asarray(topic, dtype=np.float64)
    facet_class = np.asarray(facet_class, dtype=np.int64)
    order = [int(j) for j in order]
    if cosine.ndim != 1 or topic.shape != cosine.shape or facet_class.shape[0] != cosine.size:
        raise ValueError('Expected one cosine, one topic and one row of facet classes per edge')
    if sorted(order) != list(range(facet_class.shape[1])):
        raise ValueError('Expected every facet column once in the order')
    if not (np.isfinite(width) and width > 0) or not np.isfinite(best):
        raise ValueError('Expected a positive width and a finite best cosine')
    if not cosine.size:
        return np.zeros(0, dtype=np.int64), np.zeros(0, dtype=np.int64), np.zeros(0)
    if cosine.max() > best:
        raise ValueError('An edge is closer than the closest tag')
    cls = np.floor((best - cosine) / width).astype(np.int64)
    keys = [np.arange(cosine.size), -cosine, -topic]
    keys += [facet_class[:, j] for j in reversed(order)]
    by = np.lexsort((*keys, cls))
    sorted_cls = cls[by]
    starts = np.flatnonzero(np.r_[True, sorted_cls[1:] != sorted_cls[:-1]])
    sizes = np.diff(np.r_[starts, sorted_cls.size])
    inside = np.arange(sorted_cls.size) - np.repeat(starts, sizes)
    place = np.empty(cosine.size, dtype=np.int64)
    place[by] = inside
    placed = np.empty(cosine.size)
    placed[by] = best - width * (sorted_cls + inside / np.repeat(sizes, sizes))
    return cls, place, placed


def relevance(pos, share):
    """R(e) = sum_k share[k] * pos_k(e)."""
    pos = np.asarray(pos, dtype=np.float64)
    share = np.asarray(share, dtype=np.float64)
    if pos.ndim != 2 or share.shape != (pos.shape[1],):
        raise ValueError('Expected one share per position column')
    if not np.isfinite(share).all() or (share < 0).any() or not np.isclose(share.sum(), 1.):
        raise ValueError('Expected non-negative shares adding to 1')
    return pos @ share


def chance_corrected_best(w, edge_chunk, n_chunks):
    """The pooled tail. Per chunk with n_c >= 1 edges: v the largest w over its edges and the
    edge that carries it (`best_edges`); K = #{edges with w >= v}; tail = K / |E|;
    p = 1 - (1 - tail)^n_c; k = ceil(p * |E|) and v* the k-th largest w. k is taken in whole
    numbers, |E| - floor((|E| - K)^n_c / |E|^(n_c - 1)). A chunk with no edge: v nan, edge -1,
    K 0, tail nan, p nan, k 0, v* 0."""
    w = np.asarray(w, dtype=np.float64)
    edge_chunk = np.asarray(edge_chunk, dtype=np.int64)
    best, edge = best_edges(w, edge_chunk, n_chunks)
    total = int(w.size)
    n_c = np.bincount(edge_chunk, minlength=n_chunks).astype(np.int64)
    held = np.flatnonzero(n_c > 0)
    ascending = np.sort(w)
    count = np.zeros(n_chunks, dtype=np.int64)
    count[held] = total - np.searchsorted(ascending, best[held], side='left')
    k = np.zeros(n_chunks, dtype=np.int64)
    k[held] = [total - (total - int(a)) ** int(m) // total ** (int(m) - 1)
               for a, m in zip(count[held], n_c[held])]
    if held.size and (k[held].min() < 1 or k[held].max() > total):
        raise ValueError('k left [1, |E|]')
    star = np.zeros(n_chunks)
    star[held] = ascending[total - k[held]]
    tail = np.full(n_chunks, np.nan)
    tail[held] = count[held] / total
    p = np.full(n_chunks, np.nan)
    with np.errstate(divide='ignore'):
        p[held] = -np.expm1(n_c[held] * np.log1p(-tail[held]))
    return {'v': best, 'edge': edge, 'n_c': n_c, 'count': count, 'tail': tail, 'p': p, 'k': k,
            'v_star': star}


def reaching(fits, factor, target):
    """Per edge: how many of `fits` f have f * factor >= target, the product as the machine
    multiplies it, so a fit counts for the product it gives itself."""
    ascending = np.sort(np.asarray(fits, dtype=np.float64))
    factor = np.asarray(factor, dtype=np.float64)
    target = np.asarray(target, dtype=np.float64)
    if factor.shape != target.shape or factor.ndim != 1:
        raise ValueError('Expected one factor and one target per edge')
    if not ascending.size or not np.isfinite(ascending).all():
        raise ValueError('Expected a nonempty list of finite fits')
    if not (np.isfinite(factor).all() and (factor > 0).all() and np.isfinite(target).all()):
        raise ValueError('Expected positive factors and finite targets')
    size = ascending.size
    at = np.searchsorted(ascending, target / factor, side='left')
    while True:
        value = ascending[np.maximum(at - 1, 0)]
        move = (at > 0) & (value * factor >= target)
        if not move.any():
            break
        at[move] = np.searchsorted(ascending, value[move], side='left')
    while True:
        value = ascending[np.minimum(at, size - 1)]
        move = (at < size) & (value * factor < target)
        if not move.any():
            break
        at[move] = np.searchsorted(ascending, value[move], side='right')
    return size - at


def per_edge_corrected_best(fit, factor, fits, edge_chunk, n_chunks):
    """The per-edge form. w = fit * factor per edge; per chunk v the largest w over its edges
    and the edge that carries it. Per edge i of the chunk K_i = #{f in fits: f * factor_i >= v}
    (`reaching`); p = 1 - prod_i (1 - K_i / N), N the size of fits; k = ceil(p * N), taken in
    whole numbers, N - floor(prod_i (N - K_i) / N^(n_c - 1)), kept in [1, N]; v* the k-th
    largest of fits. A chunk with one edge whose fit is among fits gets that fit. A chunk with
    no edge: v nan, edge -1, p nan, k 0, v* 0."""
    fit = np.asarray(fit, dtype=np.float64)
    factor = np.asarray(factor, dtype=np.float64)
    fits = np.asarray(fits, dtype=np.float64)
    edge_chunk = np.asarray(edge_chunk, dtype=np.int64)
    if not fit.shape == factor.shape == edge_chunk.shape or fit.ndim != 1:
        raise ValueError('Expected one fit, one factor and one chunk per edge')
    best, edge = best_edges(fit * factor, edge_chunk, n_chunks)
    n_c = np.bincount(edge_chunk, minlength=n_chunks).astype(np.int64)
    held = np.flatnonzero(n_c > 0)
    size = int(fits.size)
    k = np.zeros(n_chunks, dtype=np.int64)
    star = np.zeros(n_chunks)
    p = np.full(n_chunks, np.nan)
    count = np.zeros(fit.size, dtype=np.int64)
    if held.size:
        count = reaching(fits, factor, best[edge_chunk])
        by_chunk = np.argsort(edge_chunk, kind='stable')
        rest = (size - count[by_chunk]).tolist()
        start = np.concatenate([[0], np.cumsum(n_c)]).tolist()
        power = [size ** m for m in range(int(n_c.max()))]
        k[held] = [size - math.prod(rest[start[c]:start[c + 1]]) // power[int(n_c[c]) - 1]
                   for c in held.tolist()]
        k[held] = np.clip(k[held], 1, size)
        star[held] = np.sort(fits)[size - k[held]]
        with np.errstate(divide='ignore'):
            kept = np.bincount(edge_chunk, weights=np.log1p(-count / size), minlength=n_chunks)
        p[held] = -np.expm1(kept[held])
    return {'v': best, 'edge': edge, 'n_c': n_c, 'reach': count, 'p': p, 'k': k,
            'v_star': star}


def chunk_values(fit, factor, fits, edge_chunk, n_chunks):
    """What a chunk takes from one query tag, from each edge's fit and factor: best, the
    largest w = fit * factor over its edges (0 with no edge); pooled, `chance_corrected_best`
    on w; per_edge, `per_edge_corrected_best` with `fits` the fit of every eligible tag; total,
    the sum of w over its edges."""
    fit = np.asarray(fit, dtype=np.float64)
    factor = np.asarray(factor, dtype=np.float64)
    w = fit * factor
    pooled = chance_corrected_best(w, edge_chunk, n_chunks)
    return {'w': w, 'best': np.where(pooled['n_c'] > 0, pooled['v'], 0.), 'pooled': pooled,
            'per_edge': per_edge_corrected_best(fit, factor, fits, edge_chunk, n_chunks),
            'total': np.bincount(np.asarray(edge_chunk, dtype=np.int64), weights=w,
                                 minlength=n_chunks)}


def tag_value(values, central, combine='max'):
    """T(c) from each query tag's value per chunk. max: the largest central_q * value_q(c),
    the earlier query tag on an exact tie. sum: their sum over q. Returns T, the query tag with
    the largest term, and the terms."""
    values = np.asarray(values, dtype=np.float64)
    central = np.asarray(central, dtype=np.float64)
    if values.ndim != 2 or not values.shape[0] or central.shape != (values.shape[0],):
        raise ValueError('Expected one row of chunk values and one weight per query tag')
    if not np.isfinite(values).all() or not np.isfinite(central).all():
        raise ValueError('A query tag value is not finite')
    terms = central[:, None] * values
    winner = np.argmax(terms, axis=0)
    if combine == 'max':
        total = terms[winner, np.arange(values.shape[1])]
    elif combine == 'sum':
        total = terms.sum(axis=0)
    else:
        raise ValueError(f'combine must be max or sum, got {combine!r}')
    return total, winner, terms


def text_side(d_description, d_question, mode='max'):
    """D and Qs, the standings over the chunks of the two cosine lists, not clipped, and the
    side: max(D, Qs) (max), D (description), max(D, Qs, 0) (clipped), 0 (none)."""
    d, d_bulk, d_spread = standing(d_description)
    q, q_bulk, q_spread = standing(d_question)
    if d.shape != q.shape:
        raise ValueError('Expected the two cosine lists over the same chunks')
    if mode == 'max':
        side = np.maximum(d, q)
    elif mode == 'description':
        side = d.copy()
    elif mode == 'clipped':
        side = np.clip(np.maximum(d, q), 0., None)
    elif mode == 'none':
        side = np.zeros_like(d)
    else:
        raise ValueError(f'unknown side mode {mode!r}')
    return {'D': d, 'Qs': q, 'side': side,
            'bulk': {'description': d_bulk, 'question': q_bulk},
            'spread': {'description': d_spread, 'question': q_spread}}


def memberships(chunk, node):
    """The distinct (chunk, node) pairs."""
    chunk = np.asarray(chunk, dtype=np.int64)
    node = np.asarray(node, dtype=np.int64)
    if chunk.shape != node.shape or chunk.ndim != 1:
        raise ValueError('Expected one node per chunk membership')
    if not chunk.size:
        return chunk, node
    pairs = np.unique(np.stack([chunk, node]), axis=1)
    return pairs[0], pairs[1]


def record_groups(adjacency_ptr, adjacency):
    """Per chunk the index of its near group - its connected component in the file-adjacency
    graph - when the component holds at least two chunks, else -1."""
    ptr = np.asarray(adjacency_ptr, dtype=np.int64)
    members = np.asarray(adjacency, dtype=np.int64)
    n = ptr.size - 1
    if n < 0 or ptr[0] != 0 or ptr[-1] != members.size or (np.diff(ptr) < 0).any():
        raise ValueError('Expected one CSR row of adjacent chunks per chunk')
    graph = csr_matrix((np.ones(members.size, dtype=np.int8), members, ptr), shape=(n, n))
    _, label = connected_components(graph, directed=False)
    size = np.bincount(label, minlength=n)
    grouped = size[label] >= 2
    record = np.full(n, -1, dtype=np.int64)
    if grouped.any():
        _, record[grouped] = np.unique(label[grouped], return_inverse=True)
    return record


def kind_reference(x, grouped, kind):
    """Per chunk the mean of x over the grouped chunks of its kind, 0 for a kind with none;
    and per kind that mean with the number of grouped chunks."""
    x = np.asarray(x, dtype=np.float64)
    grouped = np.asarray(grouped, dtype=bool)
    kind = np.asarray(kind, dtype=np.int64)
    if not x.shape == grouped.shape == kind.shape:
        raise ValueError('Expected one value, one flag and one kind per chunk')
    reference, table = np.zeros(x.size), {}
    for code in np.unique(kind[grouped]).tolist():
        members = grouped & (kind == code)
        value = float(x[members].mean())
        reference[kind == code] = value
        table[code] = {'reference': value, 'chunks': int(members.sum())}
    return reference, table


def group_lift(x, chunk, node, reference, shrink=True, tau='weighted'):
    """The lift of each chunk from one grouping. x: a value per chunk. chunk, node: the
    memberships, a chunk once per group it sits in. reference: a number, or one per chunk.
    With M memberships in G groups, on y = x - reference (a reference that is one number for
    every chunk leaves both variances as on x):

      n_g, mean_g   the members of group g and the mean of y over them
      sigma2        sum over the memberships of (y - mean_g)^2 / (M - G)
      SSB           sum_g n_g * (mean_g - m)^2, m the mean of y over the memberships
      tau2          weighted: max(0, SSB / M - G * sigma2 / M)
                    anova:    max(0, (SSB - (G - 1) * sigma2) / (M - sum_g n_g^2 / M)),
                              0 with a single group
      raw(c, g)     the mean of x over g's members other than c, less the reference of c
      trust(g)      tau2 / (tau2 + sigma2 / (n_g - 1)); 0 where tau2 is 0; 1 when not shrinking
      lift(c)       max(0, trust(g) * raw(c, g)), the largest over the chunk's groups

    A group of one gives no lift. With no group of two or more members there is no sigma2,
    no tau2 and no lift."""
    x = np.asarray(x, dtype=np.float64)
    chunk = np.asarray(chunk, dtype=np.int64)
    node = np.asarray(node, dtype=np.int64)
    if x.ndim != 1 or not x.size or not np.isfinite(x).all():
        raise ValueError('Expected one finite value per chunk')
    if chunk.shape != node.shape or chunk.ndim != 1:
        raise ValueError('Expected one node per chunk membership')
    if chunk.size and (chunk.min() < 0 or chunk.max() >= x.size):
        raise ValueError('A chunk membership is out of range')
    if tau not in ('weighted', 'anova'):
        raise ValueError(f'tau must be weighted or anova, got {tau!r}')
    reference = np.broadcast_to(np.asarray(reference, dtype=np.float64), x.shape)
    if not np.isfinite(reference).all():
        raise ValueError('Expected a finite reference')
    out = {'lift': np.zeros(x.size), 'pick': np.full(x.size, -1, dtype=np.int64),
           'chunk': chunk, 'node': np.zeros(0, dtype=np.int64),
           'labels': np.zeros(0, dtype=np.int64), 'size': np.zeros(0, dtype=np.int64),
           'mean': np.zeros(0), 'trust': np.zeros(0), 'raw': np.zeros(0), 'value': np.zeros(0),
           'gain': np.zeros(0), 'sigma2': None, 'tau2': None, 'between': None, 'noise': None,
           'ssb': None, 'sum_sq_over_m': None, 'grand': None, 'groups': 0,
           'memberships': int(chunk.size), 'tau': tau}
    if not chunk.size:
        return out
    labels, node = np.unique(node, return_inverse=True)
    size = np.bincount(node)
    total = np.bincount(node, weights=x[chunk])
    mean = total / size
    n_memberships, n_groups = int(chunk.size), int(size.size)
    grand = float(total.sum() / n_memberships)
    out.update(node=node, labels=labels, size=size, mean=mean, grand=grand, groups=n_groups,
               trust=np.zeros(n_groups), raw=np.full(n_memberships, np.nan),
               value=np.full(n_memberships, np.nan), gain=np.zeros(n_memberships),
               sum_sq_over_m=float((size.astype(np.float64) ** 2).sum() / n_memberships))
    if n_memberships == n_groups:
        return out
    if np.ptp(reference) > 0:
        y = x - reference
        mean_y = np.bincount(node, weights=y[chunk]) / size
        grand_y = float(y[chunk].sum() / n_memberships)
    else:
        y, mean_y, grand_y = x, mean, grand
    sigma2 = float(((y[chunk] - mean_y[node]) ** 2).sum() / (n_memberships - n_groups))
    ssb = float((size * (mean_y - grand_y) ** 2).sum())
    between = ssb / n_memberships
    noise = n_groups * sigma2 / n_memberships
    if tau == 'weighted':
        tau2 = max(0., between - noise)
    elif n_groups > 1:
        tau2 = max(0., (ssb - (n_groups - 1) * sigma2)
                   / (n_memberships - out['sum_sq_over_m']))
    else:
        tau2 = 0.
    others = size[node] - 1
    shared = others > 0
    raw = out['raw']
    raw[shared] = ((total[node[shared]] - x[chunk[shared]]) / others[shared]
                   - reference[chunk[shared]])
    trust = np.zeros(n_groups)
    plural = size >= 2
    if not shrink:
        trust[plural] = 1.
    elif tau2 > 0.:
        trust[plural] = tau2 / (tau2 + sigma2 / (size[plural] - 1))
    value = out['value']
    value[shared] = trust[node[shared]] * raw[shared]
    gain = out['gain']
    gain[shared] = np.maximum(value[shared], 0.)
    at = np.flatnonzero(shared)
    best, edge = best_edges(value[at], chunk[at], x.size)
    has = edge >= 0
    out['pick'][has] = at[edge[has]]
    out['lift'][has] = np.maximum(best[has], 0.)
    out.update(trust=trust, sigma2=sigma2, tau2=tau2, between=between, noise=noise, ssb=ssb)
    return out


def levels_and_order(chunk_ids, strength, spreads, cos_noise, has_edge, slots):
    """step = cos_noise / the median of the spreads; level = floor((max - strength) / step);
    the order by level, then the chunks with a winning edge by their four slot values,
    descending, then by chunk id (`level_order`)."""
    strength = np.asarray(strength, dtype=np.float64)
    spreads = np.asarray(spreads, dtype=np.float64)
    if strength.ndim != 1 or not strength.size or not np.isfinite(strength).all():
        raise ValueError('Expected one finite strength per chunk')
    if spreads.ndim != 1 or not spreads.size or not (spreads > 0).all():
        raise ValueError('Expected one positive spread per query tag')
    if not (np.isfinite(cos_noise) and cos_noise > 0):
        raise ValueError('Expected a positive noise')
    step = float(cos_noise) / float(np.median(spreads))
    level = np.floor((strength.max() - strength) / step).astype(np.int64)
    return step, level, level_order(chunk_ids, level, has_edge, slots)


# ------------------------------------------------------------------ the chain

def build_layer(inputs):
    """What does not depend on the query: the eligible edges, their five raw values and
    positions, each chunk's edge count and record kind, and the groupings.

    inputs: 'chunk_ids' and 'chunk_kinds' per chunk; 'eligible' per graph tag; 'edge_tag',
    'edge_chunk', 'edge_topic' per edge and 'edge_facets' (edges, 4) in ADJUST_FACETS order,
    the higher the more; 'product' per chunk; 'channel_ptr', 'channels' and 'adjacency_ptr',
    'adjacency', the CSR of each chunk's channel nodes and of its file-adjacent chunks. For
    C3r also 'facet_gaps', the four columns' retrain gaps, and 'self_difference', the width of
    "equally close"; without them the layer holds neither and `chain` refuses rank picked."""
    chunk_ids = [str(c) for c in inputs['chunk_ids']]
    n = len(chunk_ids)
    eligible = np.asarray(inputs['eligible'], dtype=bool)
    edge_tag = np.asarray(inputs['edge_tag'], dtype=np.int64)
    edge_chunk = np.asarray(inputs['edge_chunk'], dtype=np.int64)
    edge_topic = np.asarray(inputs['edge_topic'], dtype=np.float64)
    edge_facets = np.asarray(inputs['edge_facets'], dtype=np.float64)
    if (not edge_tag.shape == edge_chunk.shape == edge_topic.shape
            or edge_facets.shape != (edge_tag.size, len(ADJUST_FACETS))):
        raise ValueError('Expected one tag, chunk, topic and four facet values per edge')
    if edge_tag.size and (edge_tag.min() < 0 or edge_tag.max() >= eligible.size
                          or edge_chunk.min() < 0 or edge_chunk.max() >= n):
        raise ValueError('An edge endpoint is out of range')
    sel = np.flatnonzero(eligible[edge_tag])
    if not sel.size:
        raise ValueError('No edge carries an eligible graph tag')
    raw = np.column_stack([edge_topic[sel], edge_facets[sel]])
    product = np.asarray(inputs['product'], dtype=np.int64)
    if product.shape != (n,) or (product < 0).any():
        raise ValueError('Expected one product per chunk')
    channel_ptr = np.asarray(inputs['channel_ptr'], dtype=np.int64)
    channels = np.asarray(inputs['channels'], dtype=np.int64)
    if channel_ptr.shape != (n + 1,) or channel_ptr[-1] != channels.size:
        raise ValueError('Expected one CSR row of channels per chunk')
    kinds = [str(k) for k in inputs['chunk_kinds']]
    if len(kinds) != n:
        raise ValueError('Expected one record kind per chunk')
    kind_names = sorted(set(kinds))
    every = np.arange(n, dtype=np.int64)
    near = record_groups(inputs['adjacency_ptr'], inputs['adjacency'])
    if near.shape != (n,):
        raise ValueError('Expected the file adjacency over the same chunks')
    id_rank = np.empty(n, dtype=np.int64)
    id_rank[sorted(range(n), key=lambda i: chunk_ids[i])] = np.arange(n)
    gaps, width = inputs.get('facet_gaps'), inputs.get('self_difference')
    same = inputs.get('same_level')
    if width is not None and not (np.isfinite(width) and width > 0):
        raise ValueError('Expected a positive self-difference')
    return {'chunk_ids': chunk_ids, 'chunks': n, 'eligible': eligible, 'edges': sel,
            'edge_tag': edge_tag[sel], 'edge_chunk': edge_chunk[sel], 'raw': raw,
            'pos': positions(raw),
            'facet_class': None if gaps is None else facet_classes(raw[:, FACET_COLUMNS], gaps),
            'self_difference': None if width is None else float(width),
            'same_level': None if same is None else float(same),
            'n_c': np.bincount(edge_chunk[sel], minlength=n).astype(np.int64),
            'product': product, 'near': near, 'id_rank': id_rank, 'kinds': kinds,
            'kind_names': kind_names,
            'kind': np.array([kind_names.index(k) for k in kinds], dtype=np.int64),
            'groups': {'product': (every, product),
                       'channel': memberships(np.repeat(every, np.diff(channel_ptr)), channels),
                       'near': (every[near >= 0], near[near >= 0])}}


def structure_lifts(strength, layer, mode='near'):
    """M6 on S: per grouping the `group_lift`, and each grouping's lift per chunk.

    near            product on x = S against the mean of S; near group on x = S - the mean of
                    S over the chunk's product against `kind_reference`; tau2 anova
    unshrunk        the same with trust 1
    near_zero       the same with the near group's reference 0
    none            no grouping, no lift
    first           product, channel, record (the near groups): channel and record on
                    x = S - the product's mean against 0; tau2 weighted
    first_unshrunk  first with trust 1
    first_overall   first with channel and record on x = S against the mean of S"""
    strength = np.asarray(strength, dtype=np.float64)
    if mode not in STRUCTURES:
        raise ValueError(f'structure must be one of {STRUCTURES}, got {mode!r}')
    if mode == 'none':
        return {}, {}
    overall = float(strength.mean())
    product = layer['product']
    product_mean = np.bincount(product, weights=strength) / np.bincount(product)
    left = strength - product_mean[product]
    parts = {}
    if mode.startswith('first'):
        for kind in FIRST_GROUPINGS:
            if kind == 'product' or mode == 'first_overall':
                x, reference = strength, overall
            else:
                x, reference = left, 0.
            pairs = layer['groups']['near' if kind == 'record' else kind]
            parts[kind] = group_lift(x, *pairs, reference, shrink=mode != 'first_unshrunk')
            parts[kind].update(reference=reference, x=x, kind_reference=None)
        return parts, {kind: parts[kind]['lift'] for kind in FIRST_GROUPINGS}
    shrink = mode != 'unshrunk'
    parts['product'] = group_lift(strength, *layer['groups']['product'], overall,
                                  shrink=shrink, tau='anova')
    parts['product'].update(reference=overall, x=strength, kind_reference=None)
    if mode == 'near_zero':
        reference, table = np.zeros(strength.size), {}
    else:
        reference, table = kind_reference(left, layer['near'] >= 0, layer['kind'])
    parts['near'] = group_lift(left, *layer['groups']['near'], reference, shrink=shrink,
                               tau='anova')
    parts['near'].update(reference=reference, x=left, kind_reference=table)
    return parts, {kind: parts[kind]['lift'] for kind in GROUPINGS}


def chain(layer, query, cos_noise, *, fit='standing', share='readings', chunk='best',
          central='description', tags='max', side='max', structure='near', order='levels',
          rank='none'):
    """M1 to M7, every intermediate array. query: 'cosines' (query tags, graph tags),
    'readings' (query tags, 5), 'description_cosines' (query tags,), 'd_description' and
    'd_question' (chunks,). The switches: fit standing | cosine; share readings | equal | none;
    chunk best | pooled | per_edge | sum | none; central description | equal; tags max | sum;
    side max | none | description | clipped; structure as `structure_lifts`;
    order levels | plain; rank none | picked (C3r, on a layer built with the facet gaps and
    the self-difference) | percent (C3p, on a layer built with the facet gaps) | same (C3s,
    on a layer built with the facet gaps and the same-thing level)."""
    for name, value, allowed in (('fit', fit, ('standing', 'cosine')),
                                 ('share', share, ('readings', 'equal', 'none')),
                                 ('chunk', chunk, ('best', 'pooled', 'per_edge', 'sum',
                                                   'none')),
                                 ('central', central, ('description', 'equal')),
                                 ('order', order, ('levels', 'plain')),
                                 ('rank', rank, ('none', 'picked', 'percent', 'same'))):
        if value not in allowed:
            raise ValueError(f'{name} must be one of {allowed}, got {value!r}')
    n, eligible = layer['chunks'], layer['eligible']
    tag_e, chunk_e, pos = layer['edge_tag'], layer['edge_chunk'], layer['pos']
    rows = np.asarray(query['cosines'], dtype=np.float64)
    readings = np.asarray(query['readings'], dtype=np.float64)
    count = rows.shape[0]
    if rows.ndim != 2 or not count or rows.shape[1] != eligible.size:
        raise ValueError('Expected one cosine row over the graph tags per query tag')
    if readings.shape != (count, len(ALL_FACETS)):
        raise ValueError('Expected five readings per query tag')
    bulk, spread = np.zeros(count), np.zeros(count)
    z = np.full(rows.shape, np.nan)
    fit_of_tag = np.zeros(rows.shape)
    share_of = np.zeros((count, len(ALL_FACETS)))
    equal = np.zeros(count, dtype=bool)
    rel = np.zeros((count, chunk_e.size))
    w = np.zeros((count, chunk_e.size))
    names = ('v', 'edge', 'count', 'tail', 'p', 'k', 'v_star')
    parts = {key: [] for key in names + ('pe_p', 'pe_k', 'pe_v_star', 'total')}
    value = np.zeros((count, n))
    orders = np.array([facet_order(r) for r in readings], dtype=np.int64)
    ranked = rank != 'none'
    if ranked and layer.get('facet_class') is None:
        raise ValueError('the ranking needs a layer built with the facet gaps')
    if rank == 'picked' and layer.get('self_difference') is None:
        raise ValueError('rank picked needs a layer built with the facet gaps and the '
                         'self-difference')
    if rank == 'same' and layer.get('same_level') is None:
        raise ValueError('rank same needs a layer built with the same-thing level')
    rank_width = np.zeros(count) if ranked else None
    if ranked and chunk == 'per_edge':
        raise ValueError('the ranking places each edge; the per-edge correction draws from '
                         'the unplaced tag fits')
    edge_class = np.zeros((count, chunk_e.size), dtype=np.int64) if ranked else None
    edge_place = np.zeros((count, chunk_e.size), dtype=np.int64) if ranked else None
    for i in range(count):
        z[i, eligible], bulk[i], spread[i] = standing(rows[i][eligible])
        if fit == 'standing':
            fit_of_tag[i, eligible] = np.clip(z[i, eligible], 0., None)
        else:
            fit_of_tag[i] = rows[i]
        share_of[i], equal[i] = shares(readings[i])
        if share == 'equal':
            share_of[i] = 1. / len(ALL_FACETS)
        rel[i] = MIDDLE if share == 'none' else relevance(pos, share_of[i])
        fit_edge = fit_of_tag[i][tag_e]
        if rank == 'same':
            edge_cosines = rows[i][tag_e]
            closest = float(rows[i][eligible].max())
            picked = np.flatnonzero(edge_cosines >= layer['same_level'])
            edge_class[i] = 1
            rank_width[i] = max(closest - layer['same_level'], 0.)
            if picked.size and rank_width[i] > 0:
                # one band from the level up to the closest tag, wide enough to hold them all
                _, place, placed = ranked_closeness(
                    edge_cosines[picked], closest, rank_width[i] * (1. + 1e-9) + 1e-12,
                    layer['facet_class'][picked], orders[i], layer['raw'][picked, 0])
                edge_class[i, picked], edge_place[i, picked] = 0, place
                moved = edge_cosines.copy()
                moved[picked] = placed
                fit_edge = (np.clip((moved - bulk[i]) / spread[i], 0., None)
                            if fit == 'standing' else moved)
            elif picked.size:
                edge_class[i, picked] = 0
        elif ranked:
            closest = float(rows[i][eligible].max())
            rank_width[i] = (layer['self_difference'] if rank == 'picked'
                             else max((1. - EQUAL_SHARE) * closest, 0.))
        if ranked and rank != 'same' and rank_width[i] > 0:
            edge_class[i], edge_place[i], placed = ranked_closeness(
                rows[i][tag_e], closest, rank_width[i],
                layer['facet_class'], orders[i], layer['raw'][:, 0])
            fit_edge = (np.clip((placed - bulk[i]) / spread[i], 0., None)
                        if fit == 'standing' else placed)
        got = chunk_values(fit_edge, rel[i] / MIDDLE, fit_of_tag[i][eligible], chunk_e, n)
        w[i] = got['w']
        for key in names:
            parts[key].append(got['pooled'][key])
        parts['pe_p'].append(got['per_edge']['p'])
        parts['pe_k'].append(got['per_edge']['k'])
        parts['pe_v_star'].append(got['per_edge']['v_star'])
        parts['total'].append(got['total'])
        value[i] = {'best': got['best'], 'pooled': got['pooled']['v_star'],
                    'per_edge': got['per_edge']['v_star'], 'sum': got['total'],
                    'none': np.zeros(n)}[chunk]
    parts = {key: np.array(rows_) for key, rows_ in parts.items()}
    weight = (centrality(query['description_cosines']) if central == 'description'
              else np.ones(count))
    total, winner, terms = tag_value(value, weight, tags)
    has_edge = (layer['n_c'] > 0) & (chunk != 'none')
    win_edge = np.where(has_edge, parts['edge'][winner, np.arange(n)], -1)
    slots = np.zeros((n, len(ADJUST_FACETS)))
    held = np.flatnonzero(has_edge)
    slots[held] = np.take_along_axis(pos[win_edge[held]][:, FACET_COLUMNS],
                                     orders[winner[held]], axis=1)
    text = text_side(query['d_description'], query['d_question'], side)
    if text['side'].shape != (n,):
        raise ValueError('Expected one description cosine per chunk')
    base = total + text['side']
    groups, lifts = structure_lifts(base, layer, structure)
    strength = base + sum(lifts.values()) if lifts else base.copy()
    step_spreads = spread
    if chunk == 'none':
        named = {'max': ('description', 'question'), 'clipped': ('description', 'question'),
                 'description': ('description',), 'none': ()}[side]
        if not named:
            raise ValueError('with the tags and the text both off nothing enters the strength')
        step_spreads = np.array([text['spread'][name] for name in named])
    step, level, ordered = levels_and_order(layer['chunk_ids'], strength, step_spreads,
                                            cos_noise, has_edge, slots)
    if order == 'plain':
        ordered = np.lexsort((layer['id_rank'], -strength)).tolist()
    return {'bulk': bulk, 'spread': spread, 'z': z, 'fit': fit_of_tag, 'shares': share_of,
            'equal_shares': equal, 'facet_orders': orders, 'R': rel, 'w': w, **parts,
            'value': value, 'centrality': weight, 'terms': terms, 'T': total, 'winner': winner,
            'win_edge': win_edge, 'has_edge': has_edge, 'slots': slots, 'D': text['D'],
            'Qs': text['Qs'], 'side': text['side'], 'text_bulk': text['bulk'],
            'text_spread': text['spread'], 'S': base, 'groups': groups, 'lift': lifts,
            'S_prime': strength, 'step': step, 'level': level, 'order': ordered,
            'edge_class': edge_class, 'edge_place': edge_place, 'rank_width': rank_width}

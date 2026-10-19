"""Where the largest clouds lie by scope, on the made-up question's arrays
(`structure_last_arrays.npz`, written by `structure_last_arrays.py`, itself the copy of
`cluster_by_scope_made_up.py`; `structure_last_text_standins.npz` from
`structure_last_text_standins.py`). Prints: the shape of the value; the links per chunk; the
chance value of a best-of-m; how each "unrelated" distribution fits; each chunk's share in the
cloud under each of them; per scope every gauge side by side; the tree; random graph tags and
random chunk descriptions standing in for the question.

No model call, no benchmark file, nothing uses the 72,000 cut. Run from the repo root."""
import json
import pathlib
import sys
import time

import numpy as np
from scipy import optimize, stats
from scipy.special import gammaln

sys.stdout.reconfigure(encoding='utf-8')
HERE = pathlib.Path('output/research/2026-10-07-structure-last')
A = np.load(HERE / 'structure_last_arrays.npz')
J = json.loads((HERE / 'structure_last_arrays.json').read_text(encoding='utf-8'))
TEXT_STAND = np.load(HERE / 'structure_last_text_standins.npz')
SHUFFLES = 4000      # only the grain of a shuffle probability, 1/(SHUFFLES+1); sets no gauge
rng = np.random.default_rng(20261007)
started = time.perf_counter()

strength = A['strength'].astype(float)
tags, text = A['tags'].astype(float), A['text'].astype(float)
base = tags + text
D, Qs = A['D'].astype(float), A['Qs'].astype(float)
links = A['links'].astype(np.int64)
per_link = A['per_link'].astype(float)
edge_chunk, edge_tag = A['edge_chunk'], A['edge_tag']
eligible = A['eligible']
weight = A['centrality'].astype(float)
N, E = strength.size, per_link.size
query_tags = J['query_tags']

paths = list(J['paths'])
members = [np.array(J['paths'][p], dtype=np.int64) for p in paths]
depth = np.array([p.count('/') for p in paths])
size = np.array([m.size for m in members])
at_path = {p: i for i, p in enumerate(paths)}
G = len(paths)
LEVELS = {0: 'product', 1: 'product / kind of record', 2: 'product / slack threads / channel'}
GUMBEL_MAD = optimize.brentq(
    lambda c: stats.gumbel_r.cdf(-np.log(np.log(2)) + c) - stats.gumbel_r.cdf(-np.log(np.log(2)) - c)
    - 0.5, 0.1, 2.)       # a Gumbel's median absolute deviation over its scale


def middle_spread(x):
    m = float(np.median(x))
    return m, 1.4826 * float(np.median(np.abs(x - m)))


def quartile_skew(x):
    a, b, c = np.percentile(x, [25, 50, 75])
    return (c + a - 2 * b) / (c - a)


def small(p):
    return f'{p:8.1e}' if p < 0.001 else f'{p:8.4f}'


def tenths(p):
    return ' '.join(f'{int(c):4d}' for c in np.histogram(p, bins=np.linspace(0, 1, 11))[0])


# ---------------------------------------------------------------- 1. the shape of the value
print(f'{N} chunks, {E} links of eligible graph tags, {len(query_tags)} querytags, '
      f'{G} places ({", ".join(f"{int((depth == d).sum())} {LEVELS[d]}" for d in LEVELS)})')
print('\n== 1. the shape of the value over the pool ==')
print('                            1%     25%  middle     75%     90%     99%     top    mean'
      '      sd    skew  quartile skew')
for name, x in (("the arm's value", strength), ('tags + text (no lifts)', base),
                ('from the tags', tags), ('from the text', text),
                ('  description standing', D), ('  question standing', Qs),
                ('product lift', A['lift_product'].astype(float)),
                ('near lift', A['lift_near'].astype(float))):
    q = np.percentile(x, [1, 25, 50, 75, 90, 99])
    print(f'{name:24s}' + ''.join(f'{v:8.2f}' for v in q)
          + f'{x.max():8.2f}{x.mean():8.2f}{x.std():8.2f}{stats.skew(x):8.2f}'
          + (f'{quartile_skew(x):11.3f}' if np.percentile(x, 75) > np.percentile(x, 25) else ''))
print('   for reference: a bell shape has skew 0 and quartile skew 0; the largest of many tries '
      '(Gumbel) has skew 1.14 and quartile skew 0.118')
print(f'   chunks with a tag value above 0: {int((tags > 0).sum())}; with a product lift above 0: '
      f'{int((A["lift_product"] > 0).sum())}; with a near lift above 0: '
      f'{int((A["lift_near"] > 0).sum())}')
rho = float(np.corrcoef(D, Qs)[0, 1])
print(f'   rank correlation over the pool: tag value with text value '
      f'{stats.spearmanr(tags, text)[0]:.3f}; description standing with question standing '
      f'{stats.spearmanr(D, Qs)[0]:.3f} (Pearson {rho:.3f})')
print(f'   the larger of two bell-shaped standings with that correlation has mean '
      f'{np.sqrt((1 - rho) / np.pi):.3f} and sd {np.sqrt(1 - (1 - rho) / np.pi):.3f} '
      f'(Nadarajah & Kotz 2008); the text value has mean {text.mean():.3f}, sd {text.std():.3f}')
print(f'   skew a sum inherits: each part\'s skew times (its sd / the sum\'s sd)^3; a Gumbel tag '
      f'part of sd {tags.std():.2f} inside tags + text of sd {base.std():.2f} gives '
      f'{1.14 * (tags.std() / base.std()) ** 3:.3f}')
lifted = int(np.argmax(np.bincount(A['product'], weights=A['lift_product'])
                       / np.bincount(A['product'])))
inside_lift = A['lift_product'][A['product'] == lifted]
print(f'   the product lift inside the product it lifts most ({inside_lift.size} chunks): from '
      f'{inside_lift.min():.3f} to {inside_lift.max():.3f}; the spread of tags + text over the pool '
      f'is {middle_spread(base)[1]:.3f}')
order_arm = A['order']
print('   what the first k of the arm\'s order are made of (means): tag part, text part, product '
      'lift, near lift')
for k in (10, 100, 425, N):
    i = order_arm[:k]
    print(f'      first {k:5d}: {tags[i].mean():5.2f} {text[i].mean():5.2f} '
          f'{A["lift_product"][i].mean():5.2f} {A["lift_near"][i].mean():5.2f}')
print('   chunks above a value:      2.0   2.5   3.0   3.5   4.0\n'
      '      tag part             ' + ''.join(f'{int((tags > v).sum()):6d}' for v in (2, 2.5, 3, 3.5, 4))
      + '\n      text part            ' + ''.join(f'{int((text > v).sum()):6d}' for v in (2, 2.5, 3, 3.5, 4)))

# ---------------------------------------------------------------- 2. links per chunk
print('\n== 2. is a scope a fair random handful: links per chunk ==')
kind = A['kind']
print('   kind of record               chunks   links: mean   sd  middle   middle of: tag part  text '
      'part  tags + text')
for code, label in enumerate(J['kind_names']):
    m = links[kind == code]
    if m.size:
        print(f'   {label:26s}{m.size:8d}{m.mean():14.2f}{m.std():6.2f}{np.median(m):6.0f}'
              f'{np.median(tags[kind == code]):20.2f}{np.median(text[kind == code]):11.2f}'
              f'{np.median(base[kind == code]):11.2f}')
product = A['product']
per_product = np.array([links[product == p].mean() for p in range(product.max() + 1)])
sd_product = np.array([links[product == p].std() for p in range(product.max() + 1)])
print(f'   over the pool: mean {links.mean():.2f}, sd {links.std():.2f}, from {links.min()} to '
      f'{links.max()}')
print(f'   the 30 products\' means run from {per_product.min():.2f} to {per_product.max():.2f} '
      f'(middle {np.median(per_product):.2f}); their sds from {sd_product.min():.2f} to '
      f'{sd_product.max():.2f}')


def share_between(groups):
    total = ((links - links.mean()) ** 2).sum()
    between = sum(links[groups == g].size * (links[groups == g].mean() - links.mean()) ** 2
                  for g in np.unique(groups))
    return between / total


print(f'   share of the variance of links per chunk that lies between kinds: '
      f'{share_between(kind):.3f}; between products: {share_between(product):.3f}')
r_links = stats.spearmanr(tags, links)
print(f'   rank correlation of the tag value with the number of links: {r_links[0]:.3f} '
      f'(p {r_links[1]:.1e}); of the text value: {stats.spearmanr(text, links)[0]:.3f}; of the '
      f'arm\'s value: {stats.spearmanr(strength, links)[0]:.3f}')
edges_m = np.quantile(links, [0.25, 0.5, 0.75])
quarter = np.searchsorted(edges_m, links, side='left')
print('   the tag value by quarter of the number of links: '
      + '; '.join(f'{links[quarter == k].min()}-{links[quarter == k].max()} links: middle '
                  f'{np.median(tags[quarter == k]):.2f}' for k in range(4) if (quarter == k).any()))

# ---------------------------------------------------------------- 3. the chance value of a best-of-m
print('\n== 3. the chance value of a best-of-m (the tag part) ==')
ordered_links = np.sort(per_link)
below = np.searchsorted(ordered_links, tags, side='left')
own_top = np.bincount(edge_chunk, weights=(per_link == tags[edge_chunk]), minlength=N)
others_as_large = (E - below) - own_top
one_try = (1. + others_as_large) / (E - links + 1.)       # P(one other link is as large)
with np.errstate(divide='ignore'):
    log_miss = np.log1p(-one_try)
p_exact = -np.expm1(links * log_miss)
print(f'   H = the distribution of the per-link quantity over all {E} links; an unrelated chunk '
      f'with m links: P(best >= v) = 1 - H(v)^m')
print(f'   per-link quantity: {int((per_link == 0).sum())} of the links are 0; middle '
      f'{np.median(per_link):.2f}, 99% point {np.percentile(per_link, 99):.2f}, top '
      f'{per_link.max():.2f}; links at or above 2.0, 2.5, 3.0, 3.5: '
      + ', '.join(str(int((per_link >= v).sum())) for v in (2, 2.5, 3, 3.5)))
print(f'   chunks per tenth of p, 0-0.1 first (uniform = {N / 10:.0f} each): {tenths(p_exact)}')
print(f'   middle p {np.median(p_exact):.3f}; chunks with N*p < 1: {int((N * p_exact < 1).sum())}; '
      f'with p < 0.001: {int((p_exact < 0.001).sum())} (uniform gives {N * 0.001:.1f}); '
      f'p < 0.01: {int((p_exact < 0.01).sum())} (uniform {N * 0.01:.0f})')
print(f'   rank correlation of that p with the number of links: '
      f'{stats.spearmanr(p_exact, links)[0]:.3f}; middle p by quarter of links: '
      + ', '.join(f'{np.median(p_exact[quarter == k]):.3f}' for k in range(4)
                  if (quarter == k).any()))
first = np.argsort(p_exact)[:5]
at_least = (E - below).astype(int)
place_by_tags = N + 1 - stats.rankdata(tags, method='min')
print('   why no chunk can fall far under N*p = 1 here: H holds the chunk\'s own best link, so '
      'p >= about m * (links at least as large) / E and N*p >= about that number of links. The '
      'five smallest N*p: '
      + '; '.join(f'{N * p_exact[i]:.2f} ({at_least[i]} links at least as large, m = {links[i]})'
                  for i in first)
      + f'. N*p over the chunk\'s own place among the chunks by tag value: middle '
      f'{np.median(N * p_exact / place_by_tags):.2f}')
scores = stats.norm.ppf(stats.rankdata(per_link) / (E + 1.))
group_mean = np.bincount(edge_chunk, weights=scores, minlength=N) / links
msb = float((links * (group_mean - scores.mean()) ** 2).sum() / (N - 1))
msw = float(((scores - group_mean[edge_chunk]) ** 2).sum() / (E - N))
k0 = (E - (links ** 2).sum() / E) / (N - 1)
icc = (msb - msw) / (msb + (k0 - 1) * msw)
print(f'   the links of one chunk resemble each other: intraclass correlation of the per-link '
      f'quantity (normal scores) {icc:.3f}')
ln_m = np.log(links)
slope = stats.theilslopes(tags, ln_m)
beta = float(slope[0])
moved = tags - beta * ln_m
moved_scale = (middle_spread(moved)[1] / 1.4826) / GUMBEL_MAD
moved_law = stats.gumbel_r(np.median(moved) + beta * np.log(np.log(2)), beta)
p_moved = moved_law.sf(moved)
print(f'   the unrelated law carried out from the bulk instead: if one unrelated link exceeds v '
      f'with chance ~ exp(-v/b), the best of m is a Gumbel of scale b whose place moves up by '
      f'b*ln(m). The tag value\'s middle rises by {beta:.3f} per ln(links) (Theil-Sen, 95% '
      f'{slope[2]:.3f} to {slope[3]:.3f}); the Gumbel scale read from the spread of (tag value - '
      f'{beta:.3f}*ln(links)) is {moved_scale:.3f}')
print(f'   with it: chunks per tenth of p: {tenths(p_moved)}')
print(f'            chunks with N*p < 1: {int((N * p_moved < 1).sum())}; p < 0.001: '
      f'{int((p_moved < 0.001).sum())}; p < 0.01: {int((p_moved < 0.01).sum())}; rank '
      f'correlation of p with the number of links {stats.spearmanr(p_moved, links)[0]:.3f}')

# ---------------------------------------------------------------- 4. the "unrelated" distributions
print('\n== 4. the fitted "unrelated" distributions and how they fit the lower 90% ==')


def bell(x):
    m, s = middle_spread(x)
    return stats.norm(m, s)


def gumbel(x):
    m, s = middle_spread(x)
    b = (s / 1.4826) / GUMBEL_MAD
    return stats.gumbel_r(m + b * np.log(np.log(2)), b)


def gumbel_lower(x):
    cut = np.percentile(x, 90)
    data = stats.CensoredData(uncensored=x[x <= cut], right=np.full(int((x > cut).sum()), cut))
    loc, scale = stats.gumbel_r.fit(data)
    return stats.gumbel_r(loc, scale)


m_values, m_counts = np.unique(links, return_counts=True)


def best_of_cdf(x):
    h = np.searchsorted(ordered_links, np.atleast_1d(x), side='right') / E
    with np.errstate(divide='ignore'):
        lh = np.log(h)
    return (np.exp(m_values[None, :] * lh[:, None]) * m_counts[None, :]).sum(axis=1) / N


def fit_line(name, x, cdf):
    xs = np.sort(x)
    k = int(np.ceil(0.9 * N))
    F = cdf(xs[:k])
    apart = np.maximum(np.abs(np.arange(1, k + 1) / N - F), np.abs(np.arange(k) / N - F))
    out = 1. - cdf(xs)
    counts = [int((out < a).sum()) for a in (0.01, 0.001, 1. / N)]
    marks = [float(np.interp(u, cdf(xs), xs)) for u in (0.05, 0.25, 0.75, 0.9)]
    real = np.percentile(x, [5, 25, 75, 90])
    print(f'   {name:50s} {apart.max():6.3f} at {xs[int(np.argmax(apart))]:5.2f}   '
          + ' '.join(f'{a - b:+5.2f}' for a, b in zip(marks, real))
          + f'   {counts[0]:5d} {counts[1]:5d} {counts[2]:5d}')


print(f'   (largest gap = the largest distance between the fitted and the counted share below a '
      f'value, over the lower 90%; the four numbers: fitted less counted 5%, 25%, 75%, 90% point; '
      f'then chunks beyond the fitted 1%, 0.1% and 1/N points, where the fit alone puts '
      f'{N * 0.01:.0f}, {N * 0.001:.1f}, 1)')
print('                                                      largest gap        5%   25%   75%'
      '   90%     >1%  >0.1%  >1/N')
for label, x in (("the arm's value", strength), ('tags + text', base), ('tag part', tags),
                 ('text part', text)):
    fit_line(f'{label}: bell, middle and spread', x, bell(x).cdf)
    fit_line(f'{label}: Gumbel, middle and spread', x, gumbel(x).cdf)
    fit_line(f'{label}: Gumbel, likelihood on lower 90%', x, gumbel_lower(x).cdf)
fit_line('tag part: best-of-m, H over all links', tags, best_of_cdf)
fit_line(f'tag part less {beta:.3f}*ln(links): Gumbel, that scale', moved, moved_law.cdf)
fit_line('description standing: bell', D, stats.norm.cdf)
fit_line('question standing: bell', Qs, stats.norm.cdf)

# ---------------------------------------------------------------- 5. each chunk's share in the cloud


def grenander(p):
    """The decreasing density of p on (0, 1] with the largest likelihood: the slopes of the
    least concave majorant of the counted share below p (Grenander 1956). Per value its slope."""
    p = np.maximum(np.asarray(p, dtype=float), 1e-300)
    ux, cnt = np.unique(p, return_counts=True)
    xs, ys = np.r_[0., ux], np.r_[0., np.cumsum(cnt) / p.size]
    if xs[-1] < 1.:
        xs, ys = np.r_[xs, 1.], np.r_[ys, 1.]
    hull = [0]
    for i in range(1, xs.size):
        while len(hull) >= 2:
            a, b = hull[-2], hull[-1]
            if (ys[b] - ys[a]) * (xs[i] - xs[b]) <= (ys[i] - ys[b]) * (xs[b] - xs[a]):
                hull.pop()
            else:
                break
        hull.append(i)
    hx, hy = xs[hull], ys[hull]
    slopes = np.diff(hy) / np.diff(hx)
    seg = np.clip(np.searchsorted(hx, p, side='left') - 1, 0, slopes.size - 1)
    return slopes[seg]


def cloud_share(p):
    """Two groups, unrelated and cloud: P(cloud | p) = 1 - pi0 / f(p), with f the Grenander
    density of the p and pi0 taken as 1 (its upper bound, so the share is a lower bound). The
    shares sum to the surplus at its largest: max over x of (count of p <= x) - n*x."""
    share = np.clip(1. - 1. / grenander(p), 0., 1.)
    ps = np.sort(p)
    surplus = np.arange(1, p.size + 1) - p.size * ps
    k = int(np.argmax(surplus))
    return share, float(surplus[k]), k + 1


print('\n== 5a. per querytag, the graph tags\' standing: on the cosine and on Fisher\'s scale '
      '(atanh of the cosine) ==')
print(f'   (a bell-shaped bulk of {int(eligible.sum())} tags puts {eligible.sum() * stats.norm.sf(3):.1f} '
      f'beyond 3 spreads and {eligible.sum() * stats.norm.sf(4):.1f} beyond 4, and leaves a '
      f'surplus of about {np.sqrt(np.pi / 8) * np.sqrt(eligible.sum()):.0f} by chance somewhere '
      f'mid-list: sqrt(pi/8)*sqrt(n))')
print('   (gap = the largest distance between the bell and the counted share below a standing, '
      'over the lower 90%; same thing = graph tags at or above the arm\'s level '
      f'{J["same_level"]:.4f})')
print('   weight   top    same    on the cosine                        on Fisher\'s scale')
print('            cosine thing   skew    gap   beyond   beyond       skew    gap   beyond   beyond'
      '   surplus  among    tags with    standing (cosine) where   querytag')
print('                                         +3       -3                         +3       +4   '
      '            the first  share > 1/2  the share reaches 1/2')


def bell_gap(z):
    zs = np.sort(z)
    k = int(np.ceil(0.9 * zs.size))
    F = stats.norm.cdf(zs[:k])
    return float(np.maximum(np.abs(np.arange(1, k + 1) / zs.size - F),
                            np.abs(np.arange(k) / zs.size - F)).max())



standing_of_tag = A['standing_of_tag']
cosines = A['cosines']
by_chunk = np.argsort(edge_chunk, kind='stable')
starts = np.flatnonzero(np.r_[True, np.diff(edge_chunk[by_chunk]) != 0])
tag_share = np.zeros((len(query_tags), eligible.size))
per_querytag = np.zeros((len(query_tags), N))
for i, name in enumerate(query_tags):
    z = standing_of_tag[i, eligible]
    c = cosines[i][eligible]
    f = np.arctanh(np.minimum(c, 1. - 1e-12))
    fm, fs = middle_spread(f)
    zf = (f - fm) / fs
    share, surplus, at = cloud_share(stats.norm.sf(zf))
    tag_share[i, eligible] = share
    per_querytag[i] = np.maximum.reduceat(tag_share[i][edge_tag][by_chunk], starts)
    half = share > 0.5
    edge = f'{zf[half].min():6.2f} ({c[half].min():.3f})' if half.any() else '     none'
    print(f'   {weight[i]:6.3f}  {c.max():6.3f}{int((c >= J["same_level"]).sum()):5d}'
          f'{stats.skew(z):8.2f}{bell_gap(z):7.3f}{int((z > 3).sum()):8d}'
          f'{int((z < -3).sum()):9d}      {stats.skew(zf):6.2f}{bell_gap(zf):7.3f}'
          f'{int((zf > 3).sum()):8d}'
          f'{int((zf > 4).sum()):9d}{surplus:10.0f}{at:9d}{int(half.sum()):12d}'
          f'        {edge}          {name[:36]}')
share_querytag = (weight[:, None] * per_querytag).max(axis=0)

print('\n== 5b. each chunk\'s share in the cloud, by the "unrelated" distribution used ==')
chunk_p = {
    'value (with lifts), bell': bell(strength).sf(strength),
    'tags + text, bell': bell(base).sf(base),
    'tags + text, Gumbel': gumbel(base).sf(base),
    'tag part, bell': bell(tags).sf(tags),
    'tag part, Gumbel moved by links': p_moved,
    'tag part, best-of-m, H all links': p_exact,
    'description standing, bell': stats.norm.sf(D),
    'question standing, bell': stats.norm.sf(Qs),
}
methods = {}
print(f'   (surplus = chunks counted under a p less what the unrelated distribution alone puts '
      f'there, at the depth where that is largest; the shares sum to it; an exactly right '
      f'unrelated distribution leaves about {np.sqrt(np.pi / 8) * np.sqrt(N):.0f} by chance, '
      f'spread thin mid-list)')
print('   unrelated distribution               surplus  among the   chunks with      share of '
      'the chunk at place')
print('                                                 first       share > 1/2         1    10'
      '    20    50   100   200   500')


def share_line(name, share, surplus=None, at=None):
    top = np.sort(share)[::-1]
    print(f'   {name:36s}{share.sum() if surplus is None else surplus:8.1f}'
          + (f'{at:9d}' if at is not None else f'{"":9s}')
          + f'{int((share > 0.5).sum()):14d}          '
          + ' '.join(f'{top[k - 1]:5.2f}' for k in (1, 10, 20, 50, 100, 200, 500)))


for name, p in chunk_p.items():
    methods[name], surplus, at = cloud_share(p)
    share_line(name, methods[name], surplus, at)
methods['text part, bell'] = np.maximum(methods.pop('description standing, bell'),
                                        methods.pop('question standing, bell'))
methods['per querytag (Fisher), carried'] = share_querytag
share_line('text part: larger of the two', methods['text part, bell'])
share_line('per querytag (Fisher), carried', share_querytag)
print('   rank correlation of the share with the chunk\'s number of links: '
      + '; '.join(f'{name}: {stats.spearmanr(share, links)[0]:+.3f}'
                  for name, share in methods.items() if share.std() > 0))
names = list(methods)
print('   chunks with a share above 1/2 under both of two (rows and columns in this order):')
for a in names:
    print('      ' + ' '.join(f'{int(((methods[a] > 0.5) & (methods[b] > 0.5)).sum()):5d}'
                              for b in names) + f'   {a}')
CARRIED = ('tags + text, bell', 'tag part, Gumbel moved by links',
           'per querytag (Fisher), carried', 'text part, bell')

# ---------------------------------------------------------------- 6. the scopes
LG = gammaln(np.arange(N + 2, dtype=np.float64))


def tail_table(n):
    """P(X >= b) for X hypergeometric: b of a scope's n chunks among the pool's top t.
    Rows t = 0..N, columns b = 0..n."""
    t = np.arange(N + 1)[:, None]
    b = np.arange(n + 1)[None, :]
    k = t - b
    ok = (k >= 0) & (k <= N - n)
    kk = np.clip(k, 0, N - n)
    lp = ((LG[n + 1] - LG[b + 1] - LG[n - b + 1])
          + (LG[N - n + 1] - LG[kk + 1] - LG[N - n - kk + 1])
          - (LG[N + 1] - LG[t + 1] - LG[N - t + 1]))
    pmf = np.where(ok, np.exp(lp), 0.)
    return np.minimum(np.cumsum(pmf[:, ::-1], axis=1)[:, ::-1], 1.)


def scan(sorted_ranks, tail, n):
    """Rows of a scope's ranks in increasing order. The depth scan: the smallest upper tail over
    the depths, the count and the depth there; and the plain largest excess over the depths."""
    j = np.arange(1, n + 1)
    tl = tail[sorted_ranks, j]
    at = tl.argmin(axis=1)
    rows = np.arange(sorted_ranks.shape[0])
    excess = (j - sorted_ranks * (n / N)).max(axis=1)
    return tl[rows, at], j[at], sorted_ranks[rows, at], excess


def scan_exact(low, n, tail):
    """The chance that a random n of the N ranks reach a depth-scan value this small or
    smaller: the lattice walk of Eden, Lipson, Yogev & Yakhini 2007, summing what leaves."""
    hit = tail <= low * (1. + 1e-9)
    v = np.zeros(n + 1)
    v[0] = 1.
    b = np.arange(n + 1)
    gone = 0.
    for t in range(N):
        up = (n - b) / (N - t)
        new = v * (1. - up)
        new[1:] += v[:-1] * up[:-1]
        h = hit[t + 1]
        gone += float(new[h].sum())
        new[h] = 0.
        v = new
    return gone


check = tail_table(148)
if abs(check[50, 5] - stats.hypergeom.sf(4, N, 148, 50)) > 1e-12:
    raise RuntimeError('the hypergeometric tail table is wrong')


def ranks_of(values, ties_at_random=False):
    r = np.empty(N, dtype=np.int64)
    key = (rng.random(N), -values) if ties_at_random else (np.arange(N), -values)
    r[np.lexsort(key)] = np.arange(1, N + 1)
    return r


rank_arm = np.empty(N, dtype=np.int64)
rank_arm[order_arm] = np.arange(1, N + 1)
ORDERS = {'arm': rank_arm, 'base': ranks_of(base), 'tags': ranks_of(tags, True),
          'text': ranks_of(text, True)}
ORDER_NAMES = {'arm': "the arm's order", 'base': 'tags + text', 'tags': 'tag part alone',
               'text': 'text part alone'}
print(f'\n== 6. the scopes ==')
print(f'   the arm\'s order against the order by tags + text alone: rank correlation '
      f'{stats.spearmanr(rank_arm, ORDERS["base"])[0]:.4f}; of the arm\'s first 100, '
      f'{int((ORDERS["base"][order_arm[:100]] <= 100).sum())} are in the other\'s first 100')

perms = rng.permuted(np.tile(np.arange(1, N + 1, dtype=np.int16), (SHUFFLES, 1)), axis=1)
text_values = TEXT_STAND['values'].astype(float).copy()
text_values[np.arange(text_values.shape[0]), TEXT_STAND['chunks']] = 0.   # the stand-in itself
STAND = {'random graph tags': A['stand_in'].astype(float),
         'random graph tags, own links left out': A['stand_in_without'].astype(float),
         'random chunk descriptions': text_values}
stand_rank = {}
for label, values in STAND.items():
    r = np.empty(values.shape, dtype=np.int16)
    for k in range(values.shape[0]):
        r[k, np.lexsort((rng.random(N), -values[k]))] = np.arange(1, N + 1)
    stand_rank[label] = r

obs = {name: {k: np.zeros(G) for k in ('low', 'count', 'where', 'excess')} for name in ORDERS}
low_null = np.zeros((G, SHUFFLES))
excess_null = np.zeros((G, SHUFFLES), dtype=np.float32)
low_stand = {label: np.zeros((G, r.shape[0])) for label, r in stand_rank.items()}
mass_null = {name: np.zeros((G, SHUFFLES), dtype=np.float32) for name in CARRIED}
for n in np.unique(size):
    tail = tail_table(int(n))
    for g in np.flatnonzero(size == n):
        mem = members[g]
        rows = np.sort(np.vstack([r[mem] for r in ORDERS.values()]), axis=1)
        low, count, where, excess = scan(rows, tail, int(n))
        for k, name in enumerate(ORDERS):
            o = obs[name]
            o['low'][g], o['count'][g], o['where'][g], o['excess'][g] = (
                low[k], count[k], where[k], excess[k])
        drawn = perms[:, mem].astype(np.int64)
        low_null[g], _, _, excess_null[g] = scan(np.sort(drawn, axis=1), tail, int(n))
        for name in CARRIED:
            mass_null[name][g] = methods[name][drawn - 1].sum(axis=1)
        for label, r in stand_rank.items():
            low_stand[label][g] = scan(np.sort(r[:, mem].astype(np.int64), axis=1), tail,
                                       int(n))[0]
print(f'   {SHUFFLES} shuffles of which chunk sits in which place, the tree kept '
      f'({time.perf_counter() - started:.0f}s so far)')

bound_null = np.minimum(1., size[:, None] * low_null)     # Eden et al.: p <= n * the scan value
level_low = {d: bound_null[depth == d].min(axis=0) for d in LEVELS}
shuffle_sd = np.sqrt(size * (N - size) / (N - 1.))


def gauges_of(value, name):
    """Every gauge of one order and the value it orders by."""
    o = obs[name]
    total = np.array([value[m].sum() for m in members])
    mu, sigma = float(value.mean()), float(value.std())
    med, mad = middle_spread(value)
    bound = np.minimum(1., size * o['low'])
    family = np.zeros(G)
    for d in LEVELS:
        idx = np.flatnonzero(depth == d)
        family[idx] = (1 + (level_low[d][None, :] <= bound[idx][:, None] * (1 + 1e-12)).sum(axis=1)) \
            / (SHUFFLES + 1.)
    return {'total': total, 'mean': total / size,
            'z': (total - size * mu) / (sigma * shuffle_sd),
            'z_mid': (total - size * med) / (mad * shuffle_sd),
            'bound': bound, 'family': family,
            'own': (1 + (low_null <= o['low'][:, None] * (1 + 1e-12)).sum(axis=1)) / (SHUFFLES + 1.),
            'excess_p': (1 + (excess_null >= o['excess'][:, None] - 1e-9).sum(axis=1))
            / (SHUFFLES + 1.),
            'moments': (mu, sigma, med, mad)}


def place(values, level, largest=True):
    """Each scope's place at its level under one gauge, 1 = first."""
    v = np.where(level, -values if largest else values, np.inf)
    out = np.empty(G, dtype=np.int64)
    out[np.argsort(v, kind='stable')] = np.arange(1, G + 1)
    return out


def likelihood_ratio(share):
    """Per scope: the summed share it holds, what its size gives, and the scan statistic's
    log likelihood ratio (Kulldorff 1997, Poisson form) of holding more than its size gives."""
    M = share.sum()
    held = np.array([share[m].sum() for m in members])
    gives = size * M / N
    with np.errstate(divide='ignore', invalid='ignore'):
        llr = np.where(held > gives, held * np.log(held / gives)
                       + (M - held) * np.log((M - held) / (M - gives)), 0.)
    return held, gives, llr


GA, GB = gauges_of(strength, 'arm'), gauges_of(base, 'base')
mu, sigma, med, mad = GA['moments']
print(f'   the arm\'s value: mean {mu:.3f}, sd {sigma:.3f}; middle {med:.3f}, spread {mad:.3f}. '
      f'With the middle and the spread in place of the mean and the sd, a random handful of n '
      f'chunks does not average 0 but {(mu - med) / mad:.3f} * sqrt(n(N-1)/(N-n)): '
      f'{(mu - med) / mad * np.sqrt(20 * (N - 1) / (N - 20)):.2f} at n = 20, '
      f'{(mu - med) / mad * np.sqrt(160 * (N - 1) / (N - 160)):.2f} at n = 160')
LR = {name: likelihood_ratio(methods[name]) for name in CARRIED}
exact = {'arm': np.full(G, np.nan), 'base': np.full(G, np.nan)}
for d, label in LEVELS.items():
    level = depth == d
    idx = np.flatnonzero(level)
    firsts = {}
    for name, gz in (('arm', GA), ('base', GB)):
        firsts[name] = idx[np.argsort(gz['bound'][idx], kind='stable')[:8]]
        for g in firsts[name]:
            exact[name][g] = scan_exact(obs[name]['low'][g], int(size[g]),
                                        tail_table(int(size[g])))
    o = obs['arm']
    fisher = np.array([-np.log(rank_arm[m] / N).sum() for m in members])
    gauges = {'plain sum': place(GA['total'], level), 'mean': place(GA['mean'], level),
              'Fisher\'s sum of -ln(place/N)': place(stats.gamma.sf(fisher, size), level, False),
              'sum against its size': place(GA['z'], level),
              'the same, middle and spread': place(GA['z_mid'], level),
              'plain excess': place(GA['excess_p'] + 1e-9 / (1 + o['excess']), level, False),
              'depth scan': place(GA['bound'], level, False)}
    print(f'\n-- {label}: {idx.size} scopes of {size[idx].min()} to {size[idx].max()} chunks '
          f'(middle {int(np.median(size[idx]))}); rank correlation with the scope\'s size: plain '
          f'sum {stats.spearmanr(GA["total"][idx], size[idx])[0]:.2f}, mean '
          f'{stats.spearmanr(GA["mean"][idx], size[idx])[0]:.2f}, sum against its size '
          f'{stats.spearmanr(GA["z"][idx], size[idx])[0]:.2f}, the same with middle and spread '
          f'{stats.spearmanr(GA["z_mid"][idx], size[idx])[0]:.2f}, depth scan '
          f'{stats.spearmanr(-np.log(GA["bound"][idx]), size[idx])[0]:.2f}')
    for name, r in gauges.items():
        print(f'   first by {name:30s}: '
              + '; '.join(f'{paths[g]} ({size[g]})' for g in idx[np.argsort(r[idx])[:3]]))
    print('   the arm\'s order (its value holds the two lifts), the eight first by the depth scan; '
          '# = the scope\'s place at this level under that gauge:')
    print('   chunks      sum   #    mean   #   sum against   #  same, middle   #  plain excess  '
          '        #   depth  holds   size  surplus    scan    shuffles as large:')
    print('                                      its size         and spread        chunks  '
          'shuffle p         t*   O(t*)  gives           -log10    alone    exact  any scope')
    for g in firsts['arm']:
        gives = o['where'][g] * size[g] / N
        print(f'   {size[g]:6d}{GA["total"][g]:9.1f}{gauges["plain sum"][g]:4d}{GA["mean"][g]:8.2f}'
              f'{gauges["mean"][g]:4d}{GA["z"][g]:11.2f}{gauges["sum against its size"][g]:7d}'
              f'{GA["z_mid"][g]:10.2f}{gauges["the same, middle and spread"][g]:7d}'
              f'{o["excess"][g]:9.1f} {small(GA["excess_p"][g])}{gauges["plain excess"][g]:5d}'
              f'{int(o["where"][g]):8d}{int(o["count"][g]):7d}{gives:7.2f}'
              f'{o["count"][g] - gives:9.2f}{-np.log10(o["low"][g]):8.2f} {small(GA["own"][g])} '
              f'{small(exact["arm"][g])} {small(GA["family"][g])}   {paths[g]}')
    o = obs['base']
    print('   the order by tags + text (no lifts), the eight first by the depth scan:')
    print('   chunks   sum against   depth  holds   size  surplus    scan    shuffles as large:   '
          '        the cloud it holds / what its size gives / likelihood ratio (nats) / shuffles '
          'with as much / # its place, under:')
    print('            its size         t*   O(t*)  gives           -log10    alone    exact  '
          'any scope  ' + ''.join(f'{name[:34]:>36s}' for name in CARRIED))
    for g in firsts['base']:
        gives = o['where'][g] * size[g] / N
        line = (f'   {size[g]:6d}{GB["z"][g]:11.2f}{int(o["where"][g]):9d}{int(o["count"][g]):7d}'
                f'{gives:7.2f}{o["count"][g] - gives:9.2f}{-np.log10(o["low"][g]):8.2f} '
                f'{small(GB["own"][g])} {small(exact["base"][g])} {small(GB["family"][g])}  ')
        for name in CARRIED:
            held, give, llr = LR[name]
            p = (1 + (mass_null[name][g] >= held[g] - 1e-9).sum()) / (SHUFFLES + 1.)
            line += f'{held[g]:8.2f}{give[g]:6.2f}{llr[g]:6.1f} {small(p)}{place(llr, level)[g]:4d}    '
        print(line + paths[g])
    for name, gz in (('arm', GA), ('base', GB)):
        ordered = np.sort(-np.log10(gz['bound'][idx]))[::-1]
        gaps = ordered[:-1] - ordered[1:]
        within = [((ordered[:k] - ordered[:k].mean()) ** 2).sum()
                  + ((ordered[k:] - ordered[k:].mean()) ** 2).sum() for k in range(1, ordered.size)]
        print(f'   {ORDER_NAMES[name]}: -log10 of (n * scan value), the ten largest in order: '
              + ' '.join(f'{v:.1f}' for v in ordered[:10])
              + f'; two groups by the widest step between neighbours ({gaps.max():.1f}): the '
              f'first {int(np.argmax(gaps)) + 1} against the rest; two groups by the least '
              f'spread inside the groups (Fisher 1958): the first {int(np.argmin(within)) + 1} '
              f'against the rest')
    print(f'   the shuffle\'s own largest at this level, same scale: middle '
          f'{np.median(-np.log10(level_low[d])):.2f}, largest of {SHUFFLES} '
          f'{(-np.log10(level_low[d])).max():.2f}')
    for name in CARRIED:
        held, give, llr = LR[name]
        best = idx[np.argsort(-llr[idx], kind='stable')[:3]]
        print(f'   first by the cloud under {name:34s}: '
              + '; '.join(f'{paths[g]} (holds {held[g]:.1f}, size gives {give[g]:.1f})'
                          for g in best))
    for name in CARRIED:
        above = methods[name] > 0.5
        K = int(above.sum())
        got = np.array([int(above[members[g]].sum()) for g in idx])
        chance = stats.hypergeom.sf(got - 1, N, K, size[idx])
        best = np.argsort(chance, kind='stable')[:3]
        print(f'   the {K} chunks more likely cloud than not under {name}: '
              + '; '.join(f'{paths[idx[b]]} holds {got[b]} (size gives '
                          f'{K * size[idx[b]] / N:.1f}, hypergeometric tail {chance[b]:.1e})'
                          for b in best))

# ---------------------------------------------------------------- 7. the tree
print('\n== 7. the tree (the order by tags + text) ==')
tree_low = bound_null.min(axis=0)
o = obs['base']
print(f'   every place of the tree in one scan ({G} places): the shuffle\'s own largest, as '
      f'-log10 of (n * scan value): middle {np.median(-np.log10(tree_low)):.2f}, largest of '
      f'{SHUFFLES} {(-np.log10(tree_low)).max():.2f}; the eight first:')
for g in np.argsort(GB['bound'], kind='stable')[:8]:
    any_place = (1 + (tree_low <= GB['bound'][g] * (1 + 1e-12)).sum()) / (SHUFFLES + 1.)
    print(f'   {-np.log10(GB["bound"][g]):7.2f}  holds {int(o["count"][g]):3d} of the first '
          f'{int(o["where"][g]):4d}, {size[g]:3d} chunks; shuffles with any place as large '
          f'{small(any_place)}   {paths[g]}')

children = {}
for g, p in enumerate(paths):
    if '/' in p:
        children.setdefault(at_path[p.rsplit('/', 1)[0]], []).append(g)


def deviance(held, n_of, held_parent, n_parent):
    """2 * the binomial log likelihood ratio of each child's own rate against its parent's
    rate; held may be rows of shuffles."""
    gives = n_of * (held_parent / n_parent)
    with np.errstate(divide='ignore', invalid='ignore'):
        a = np.where(held > 0, held * np.log(held / gives), 0.)
        b = np.where(n_of - held > 0, (n_of - held) * np.log((n_of - held) / (n_of - gives)), 0.)
    return 2. * (a + b)


print('   how much of the cloud\'s unevenness each level of the tree carries: the likelihood-ratio '
      'statistic G2 splits into: between products; between kinds inside a product; between '
      'channels inside a product\'s slack threads (beside each: the shuffle\'s mean, and the '
      'shuffles with as much)')
print('   unrelated distribution                  between products        kinds inside products  '
      '  channels inside slack threads')
for name in CARRIED:
    share = methods[name]
    held = LR[name][0]
    null = mass_null[name].astype(float)
    M = share.sum()
    line = f'   {name:36s}'
    for d in LEVELS:
        idx = np.flatnonzero(depth == d)
        if d == 0:
            value = deviance(held[idx], size[idx], M, N).sum()
            chance = deviance(null[idx], size[idx][:, None], M, N).sum(axis=0)
        else:
            value, chance = 0., np.zeros(SHUFFLES)
            for parent, kids in children.items():
                if depth[parent] != d - 1:
                    continue
                kids = np.array(kids)
                value += deviance(held[kids], size[kids], held[parent], size[parent]).sum()
                chance += deviance(null[kids], size[kids][:, None], null[parent][None, :],
                                   size[parent]).sum(axis=0)
        p = (1 + (chance >= value - 1e-9).sum()) / (SHUFFLES + 1.)
        line += f'{value:8.1f}{chance.mean():8.1f} {small(p)}  '
    print(line)

top = int(np.flatnonzero(depth == 0)[np.argmin(GB['bound'][depth == 0])])
print(f'\n   under the product the depth scan puts first, {paths[top]} ({size[top]} chunks): its '
      f'own scopes, each against the product itself (the product\'s chunks shuffled among its '
      f'own scopes: the same scan inside the parent)')
inside = members[top]
inside_rank = np.empty(N, dtype=np.int64)
inside_rank[inside[np.argsort(ORDERS['base'][inside])]] = np.arange(1, inside.size + 1)
for d in (1, 2):
    kids = [g for g in range(G) if depth[g] == d and paths[g].startswith(paths[top] + '/')]
    rows = []
    for g in kids:
        n = int(size[g])
        r = np.sort(inside_rank[members[g]])
        j = np.arange(1, n + 1)
        tails = stats.hypergeom.sf(j - 1, inside.size, n, r)
        k = int(np.argmin(tails))
        rows.append((min(1., n * tails[k]), g, int(j[k]), int(r[k])))
    rows.sort()
    print(f'   {LEVELS[d]}: {len(kids)} under it')
    print('   chunks  holds  of the product\'s  size   n * scan value     in the whole pool:       '
          '   the cloud it holds under')
    print('                  first           gives  inside the parent  holds / of the first   '
          'alone   ' + '  '.join(f'{name[:24]:>24s}' for name in CARRIED))
    for value, g, count, where in rows[:8]:
        print(f'   {size[g]:6d}{count:7d}{where:12d}{where * size[g] / inside.size:11.2f}'
              f'{small(value):>14s}{int(o["count"][g]):14d} / {int(o["where"][g]):<6d}'
              f'{small(GB["own"][g])}   '
              + '  '.join(f'{methods[name][members[g]].sum():24.2f}' for name in CARRIED)
              + f'   {paths[g]}')
print('\n   what a cut at that product keeps: ' + '; '.join(
    f'{name}: {methods[name][inside].sum():.1f} of {methods[name].sum():.1f}' for name in CARRIED)
      + f'; {inside.size} of {N} chunks; of the pool\'s first 20, 50, 100 by tags + text: '
      + ', '.join(str(int((ORDERS["base"][inside] <= k).sum())) for k in (20, 50, 100)))

# ---------------------------------------------------------------- 8. stand-ins
print('\n== 8. stand-ins for the question (no question used) ==')
for a, lab in ((stats.norm.isf(0.01), '1%'), (stats.norm.isf(0.001), '0.1%'),
               (stats.norm.isf(1. / N), '1/N')):
    cnt = (text_values > a).sum(axis=1)
    print(f'   chunks beyond the bell\'s {lab} point ({a:.2f} spreads): a random chunk description '
          f'as the query description: middle {np.median(cnt):.0f}, quarter points '
          f'{np.percentile(cnt, 25):.0f} and {np.percentile(cnt, 75):.0f}; the made-up '
          f'question\'s description {int((D > a).sum())}, its question {int((Qs > a).sum())}; a '
          f'bell alone {N * stats.norm.sf(a):.1f}')
inflation = {}
for label, values in STAND.items():
    ranks = stats.rankdata(values, axis=1)
    scores = stats.norm.ppf(ranks / (N + 1.))
    scores = scores - scores.mean(axis=0)
    norm = np.linalg.norm(scores, axis=0)
    unit = scores / np.where(norm > 0, norm, 1.)
    pool_pairs = (np.linalg.norm(unit.sum(axis=1)) ** 2 - N) / (N * (N - 1.))
    print(f'   {label}: {values.shape[0]} stand-ins; each stand-in\'s chunk values put in rank '
          f'order, then correlated across the stand-ins. Any two chunks of the pool: '
          f'{pool_pairs:+.4f}')
    against = 'tags' if 'tags' in label else 'text'
    for d, name in LEVELS.items():
        idx = np.flatnonzero((depth == d) & (size >= 2))
        sq = np.array([np.linalg.norm(unit[:, members[g]].sum(axis=1)) ** 2 for g in idx])
        n = size[idx].astype(float)
        each = (sq - n) / (n * (n - 1.))
        pooled = (sq - n).sum() / (n * (n - 1.)).sum()
        inflation[label, d] = pooled
        typical = [int(np.median(size[depth == d])), int(size[depth == d].max())]
        idx = np.flatnonzero(depth == d)
        largest = -np.log10(np.minimum(1., size[idx][:, None] * low_stand[label][idx]).min(axis=0))
        chance = -np.log10(level_low[d])
        line = (f'      {name:34s} two chunks of one scope: {pooled:.3f} over pairs (mean over '
                f'scopes {each.mean():.3f}); 1 + (n-1)*rho = '
                + ', '.join(f'{1 + (k - 1) * pooled:.1f} at n = {k}' for k in typical)
                + f'. The level\'s largest cloud, -log10 of (n * scan value): middle '
                f'{np.median(largest):.1f}, quarter points {np.percentile(largest, 25):.1f} and '
                f'{np.percentile(largest, 75):.1f}, largest {largest.max():.1f} (shuffles: middle '
                f'{np.median(chance):.1f}, largest {chance.max():.1f}); above every shuffle: '
                f'{int((largest > chance.max()).sum())} of {largest.size}. The made-up question')
        for which in (against, 'base', 'arm'):
            mine = float(-np.log10(np.minimum(1., size[idx] * obs[which]['low'][idx]).min()))
            line += (f', {ORDER_NAMES[which]}: {mine:.1f} ({int((largest >= mine).sum())} '
                     f'stand-ins as large)')
        print(line)
print('   the sum against its size on tags + text, and the same divided by sqrt(1 + (n-1)*rho) '
      'with rho from the random graph tags / from the random chunk descriptions; the three first '
      'per level:')
for d, name in LEVELS.items():
    idx = np.flatnonzero(depth == d)
    for g in idx[np.argsort(-GB['z'][idx])[:3]]:
        a = 1 + (size[g] - 1) * inflation['random graph tags', d]
        b = 1 + (size[g] - 1) * inflation['random chunk descriptions', d]
        print(f'      {GB["z"][g]:6.2f} -> {GB["z"][g] / np.sqrt(a):5.2f} / '
              f'{GB["z"][g] / np.sqrt(b):5.2f}   {paths[g]} ({size[g]})')

# ---------------------------------------------------------------- 9. the plain excess and a sparse cloud
print('\n== 9. the plain excess against a sparse cloud in a big scope ==')
n = int(size[depth == 0].max())
g = int(np.flatnonzero((depth == 0) & (size == n))[0])
fpc = np.sqrt((N - n) / N)
print(f'   a scope of {n} chunks, shuffled: the plain excess has middle '
      f'{np.median(excess_null[g]):.1f} and 95% point {np.percentile(excess_null[g], 95):.1f} '
      f'chunks; exp(-2c^2/n) with the finite pool gives {0.5887 * np.sqrt(n) * fpc:.1f} and '
      f'{1.2239 * np.sqrt(n) * fpc:.1f}; shuffles with an excess of 10 or more: '
      f'{(excess_null[g] >= 10).mean():.3f} (the formula: {np.exp(-2 * 100 / (n * fpc ** 2)):.3f})')
tail = tail_table(n)
rest = np.array([np.sort(np.r_[np.arange(1, 11), 10 + rng.choice(N - 10, n - 10, replace=False) + 1])
                 for _ in range(2000)])
low, _, _, excess = scan(rest, tail, n)
p_excess = np.array([(1 + (excess_null[g] >= e - 1e-9).sum()) / (SHUFFLES + 1.) for e in excess])
print(f'   ten of its chunks put at the pool\'s first ten places, the other {n - 10} anywhere '
      f'(2000 draws): shuffle probability of the plain excess, middle {np.median(p_excess):.3f}; '
      f'the depth scan\'s value, middle {np.median(low):.1e}, never above {low.max():.1e}')
print(f'\ndone in {time.perf_counter() - started:.0f}s')

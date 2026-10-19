"""Numbers on the made-up question: the pick under a relative width, the lists against each
other, the facets on the picked edges, and three small demonstrations. Reads dumps of
tools/walkthrough.py's arrays. No gold, no test question, no model call."""
import sys
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

ROOT = Path('C:/Coding/exjobbet/GRAG-Job')
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'prod'), str(ROOT / 'test')]
from artefact.v4_strength import standing, centrality
from artefact.v4_multikey import facet_order, read_facet_gaps
from artefact.v4_rank import ADJUST_FACETS, ALL_FACETS
import walkthrough as W


def text_lists(X, label):
    d, _, _ = standing(np.asarray(X['d_description']))
    q, _, _ = standing(np.asarray(X['d_question']))
    return {f'description ({label})': d, f'raw question ({label})': q}


def main(path, text_path=None):
    X = W.read_inputs(path)
    el = np.asarray(X['eligible'], dtype=bool)
    et, ec = np.asarray(X['edge_tag']), np.asarray(X['edge_chunk'])
    ok = el[et]
    et, ec = et[ok], ec[ok]
    facets = np.asarray(X['edge_facets'])[ok]
    n = len(X['chunk_ids'])
    cos = np.asarray(X['query_tag_cosines'])
    read = np.asarray(X['query_readings'])
    cen = centrality(np.asarray(X['query_tag_description_cosines']))
    names = X['graph_tags']
    kinds = np.array(X['chunk_kinds'])
    product = np.asarray(X['product'])
    nq = len(X['query_texts'])
    print(f'{nq} question tags, {int(el.sum())} graph tags, {et.size} edges, {n} chunks')
    print()
    print('A. THE PICK. Per question tag: its closest graph tag, the bulk and spread of its own list, and how')
    print('   many graph tags (chunks they hang on) lie within 0.5 / 1 / 2 of its own spreads from the closest.')
    head = f'   {"question tag":42s} {"list":5s} {"centr":>5s} {"best":>5s} {"bulk":>5s} {"spread":>6s} {"standing":>8s} | within 0.5 / 1 / 2 spreads: tags (chunks)'
    print(head)
    z_all = np.full(cos.shape, -np.inf)
    picks = {}
    closest = {}
    for i, text in enumerate(X['query_texts']):
        z, bulk, spread = standing(cos[i][el])
        full = np.full(cos.shape[1], -np.inf)
        full[el] = z
        z_all[i] = full
        best = z.max()
        cells = []
        for width in (0.5, 1., 2.):
            tags = np.flatnonzero(full >= best - width)
            chunks = np.unique(ec[np.isin(et, tags)])
            cells.append(f'{tags.size} ({chunks.size})')
            picks[i, width] = tags
        closest[i] = np.argsort(-full)[:8]
        print(f'   {text[:42]:42s} {X["query_lists"][i][:5]:5s} {cen[i]:5.2f} {cos[i][el].max():5.2f} {bulk:5.2f} '
              f'{spread:6.3f} {best:8.2f} | {" / ".join(cells)}')
    print()
    print('   The eight closest graph tags of the three most central question tags: closeness, and the same number')
    print('   as its standing (spreads above the bulk of that list).')
    for i in np.argsort(-cen)[:3]:
        print(f'   "{X["query_texts"][i]}"')
        for t in closest[i]:
            print(f'       {cos[i][t]:.3f}   standing {z_all[i][t]:5.2f}   below the closest {z_all[i].max() - z_all[i][t]:4.2f}   {names[t][:70]}')
    print()

    # the tag list: each chunk's best standing over its edges, per question tag
    fit_e = z_all[:, et]
    T = np.full((nq, n), -np.inf)
    for i in range(nq):
        np.maximum.at(T[i], ec, fit_e[i])
    has = np.isfinite(T).any(axis=0)
    term = cen[:, None] * np.clip(np.where(np.isfinite(T), T, 0.), 0., None)
    tag_best = term.max(axis=0)
    tag_sum = term.sum(axis=0)
    lists = {'tags (best tag carries)': tag_best}
    lists.update(text_lists(X, 'same mode'))
    if text_path:
        lists.update(text_lists(W.read_inputs(text_path), 'question mode'))
    keys = list(lists)
    print('B. THE LISTS AGAINST EACH OTHER. Each list in its own spreads. Shared chunks among the first')
    print('   15 / 50 / 150 of two lists, and the rank correlation over all chunks.')
    for k in keys:
        v = np.sort(lists[k])
        print(f'   {k:30s} best {v[-1]:6.2f}   15th {v[-15]:6.2f}   50th {v[-50]:6.2f}   150th {v[-150]:6.2f}   chunks above 0: {int((v > 0).sum())}')
    tops = {k: [set(np.argsort(-lists[k], kind="stable")[:m].tolist()) for m in (15, 50, 150)] for k in keys}
    print()
    print(f'   {"shared 15/50/150, rho":30s} ' + ' '.join(f'{k[:24]:>26s}' for k in keys))
    for a in keys:
        row = []
        for b in keys:
            shared = '/'.join(str(len(tops[a][j] & tops[b][j])) for j in range(3))
            rho = spearmanr(lists[a], lists[b]).statistic
            row.append(f'{shared:>12s}  rho {rho:5.2f}')
        print(f'   {a:30s} ' + ' '.join(f'{c:>26s}' for c in row))
    print()
    print('   The first 15 of each list: record kinds and how many products they spread over.')
    for k in keys:
        top = np.argsort(-lists[k], kind='stable')[:15]
        kc = {kind: int((kinds[top] == kind).sum()) for kind in sorted(set(kinds[top]))}
        inside = product[top][product[top] >= 0]
        print(f'   {k:30s} {kc}  products {len(set(inside.tolist()))}, the commonest holds {int(np.bincount(inside).max()) if inside.size else 0}')
    print()

    # one order from two lists: best of the two against their sum
    text_key = 'raw question (question mode)' if text_path else 'raw question (same mode)'
    desc_key = 'description (same mode)'
    side = np.maximum(lists[desc_key], lists[text_key])
    orders = {'sum: tags + text': tag_best + side, 'best of the two': np.maximum(tag_best, side),
              'tags only': tag_best, 'text only': side}
    first = {k: np.argsort(-v, kind='stable')[:15] for k, v in orders.items()}
    print(f'D. ONE ORDER FROM THE TWO LISTS (text = the better of {desc_key} and {text_key}).')
    print('   The first 15 under each rule: how many of them are also in the first 15 of tags-only and of text-only,')
    print('   and how many are held up by one side alone (the other side at or below 0).')
    for k in ('sum: tags + text', 'best of the two'):
        top = first[k]
        one_side = int(((tag_best[top] <= 0) | (side[top] <= 0)).sum())
        print(f'   {k:20s} in tags-only first 15: {len(set(top) & set(first["tags only"])):2d}   in text-only first 15: '
              f'{len(set(top) & set(first["text only"])):2d}   held up by one side alone: {one_side:2d}   '
              f'shared with the other rule: {len(set(first["sum: tags + text"]) & set(first["best of the two"])):2d}')
    print()
    print('   Demonstration 1. The chunk that is first on the tags and its place on the text, the chunk first on')
    print('   the text and its place on the tags, and each one\'s place under the two rules.')
    rank = {k: np.empty(n, dtype=np.int64) for k in orders}
    for k, v in orders.items():
        rank[k][np.argsort(-v, kind='stable')] = np.arange(1, n + 1)
    for label, c in (('first on the tags', int(first['tags only'][0])), ('first on the text', int(first['text only'][0]))):
        print(f'   {label}: tags {tag_best[c]:5.2f} (place {rank["tags only"][c]}), text {side[c]:5.2f} (place {rank["text only"][c]}) '
              f'-> place under sum {rank["sum: tags + text"][c]}, under best-of-two {rank["best of the two"][c]}   [{kinds[c]}]')
    both = np.argsort(-(np.minimum(tag_best, side)), kind='stable')[0]
    print(f'   strongest on both at once: tags {tag_best[both]:5.2f} (place {rank["tags only"][both]}), text {side[both]:5.2f} '
          f'(place {rank["text only"][both]}) -> place under sum {rank["sum: tags + text"][both]}, under best-of-two '
          f'{rank["best of the two"][both]}   [{kinds[both]}]')
    print()
    print('   Demonstration 2. Does a chunk reached by several question tags come ahead of a chunk reached by one,')
    print('   at the same best strength? Over the chunks with a tag strength above 0: the rank correlation between')
    print('   the number of question tags reaching the chunk (standing above 0) and its tag strength.')
    reach = (term > 0).sum(axis=0)
    pos = tag_best > 0
    print(f'   best tag carries: rho {spearmanr(reach[pos], tag_best[pos]).statistic:5.2f}   '
          f'sum over question tags: rho {spearmanr(reach[pos], tag_sum[pos]).statistic:5.2f}   '
          f'(question tags reaching a chunk: median {int(np.median(reach[pos]))}, most {int(reach.max())})')
    edges_of = np.bincount(ec, minlength=n)
    print(f'   and against the number of tags on the chunk: best tag carries rho {spearmanr(edges_of[pos], tag_best[pos]).statistic:5.2f}   '
          f'sum over question tags rho {spearmanr(edges_of[pos], tag_sum[pos]).statistic:5.2f}')
    print()

    try:
        gaps, _ = read_facet_gaps(ROOT / 'output/facet_pairs/rounds/round1/bootstrap/BANDS.md')
    except Exception as exc:
        gaps = None
        print('   (facet gaps not read:', exc, ')')
    print('C. THE FACETS ON THE PICKED EDGES. For the three most central question tags: the facet order from its')
    print('   readings; the edges of the tags picked within 1 spread; each facet\'s range over those edges; how many')
    print('   "equal" classes the facet\'s own retrain gap makes of that range; and how the edges split key by key.')
    for i in np.argsort(-cen)[:3]:
        order = facet_order(read[i])
        tags = picks[i, 1.]
        mask = np.isin(et, tags)
        f = facets[mask]
        print(f'   "{X["query_texts"][i][:60]}"')
        print('      readings ' + ', '.join(f'{name} {read[i][ALL_FACETS.index(name)]:.2f}' for name in ALL_FACETS)
              + '  -> order ' + ' > '.join(ADJUST_FACETS[j] for j in order))
        print(f'      picked tags {tags.size}, their edges {int(mask.sum())}, chunks {np.unique(ec[mask]).size}')
        if not mask.sum() or gaps is None:
            continue
        key = np.zeros((int(mask.sum()), 0), dtype=np.int64)
        for j in order:
            col = f[:, j]
            cls = np.floor((col.max() - col) / gaps[j]).astype(np.int64)
            key = np.column_stack([key, cls])
            groups = {}
            for row in map(tuple, key.tolist()):
                groups[row] = groups.get(row, 0) + 1
            alone = sum(1 for g in groups.values() if g == 1)
            print(f'      {ADJUST_FACETS[j]:13s} range over the picked {col.min():6.2f} .. {col.max():6.2f} (whole graph '
                  f'{facets[:, j].min():6.2f} .. {facets[:, j].max():6.2f}), gap {gaps[j]:.2f} -> {int(cls.max()) + 1} classes; '
                  f'groups so far {len(groups)}, edges alone {alone}, largest group {max(groups.values())}')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)

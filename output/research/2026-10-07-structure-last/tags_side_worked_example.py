"""The tags side of artefact_v4 on the made-up question, one worked example with the graph's own
tag names: the querytags with their readings, one querytag against the graph tags (the picked
ones, the ones just under the level, the ones at the middle), the picked links with their five
values in the order the facets give them, one chunk that is hit, and chunks that are not hit.
Reads the graph (read only) for the names and the layer, the first call's answer from the
cache, and the arrays in `structure_last_arrays.npz`. No model call, no benchmark file, the
72,000 cut is not used. Run from the repo root."""
import json
import pathlib
import sys

import numpy as np

sys.path[:0] = ['prod', 'test']
sys.stdout.reconfigure(encoding='utf-8')
from arms import artefact_v4 as V  # noqa: E402
from artefact import query_content as Q  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402

HERE = pathlib.Path('output/research/2026-10-07-structure-last')
A = np.load(HERE / 'structure_last_arrays.npz')
J = json.loads((HERE / 'structure_last_arrays.json').read_text(encoding='utf-8'))
question = J['question']
cache = pathlib.Path('output/private/artefact_v4_cache')


def validate(raw):
    cleaned, _ = V._collapse_duplicate_tags(raw)
    return Q.parse(question, cleaned)


content, _, _ = V._ask('querytag', Q.request(question), validate, cache, True)
query_tags = (*content.tags, *content.query_tags)
prepared = V.prepare_over_corpus('data/corpus')
layer = prepared.layer
tag_e, chunk_e, eligible = layer['edge_tag'], layer['edge_chunk'], layer['eligible']
if not (np.array_equal(tag_e, A['edge_tag']) and np.array_equal(chunk_e, A['edge_chunk'])
        and np.array_equal(eligible, A['eligible'])
        and [t.text for t in query_tags] == J['query_tags']):
    raise RuntimeError('the graph read now is not the one the saved arrays were made from')
names, chunk_ids = list(prepared.graph_tags), list(prepared.chunk_ids)
n, same = len(chunk_ids), layer['same_level']
cos, readings = A['cosines'].astype(float), A['readings'].astype(float)
bulk, spread, weight = A['bulk'], A['spread'], A['centrality']
fit = A['fit_of_link'].astype(float)
product_of = np.empty(n, dtype=object)
for path, members in J['paths'].items():
    if path.count('/') == 0:
        product_of[np.array(members, dtype=np.int64)] = path
kind_of = [layer['kind_names'][k] for k in layer['kind']]
on_chunks = np.bincount(tag_e, minlength=len(names))
links_of = [np.flatnonzero(chunk_e == c) for c in range(n)]
FACETS = WK.RANKING_FACETS


def short(chunk):
    return chunk_ids[chunk] if len(chunk_ids[chunk]) <= 44 else chunk_ids[chunk][:41] + '...'


print(f'THE QUESTION\n  {question}')
print(f'THE QUERY DESCRIPTION (first call)\n  {content.description}')
print(f'\n{len(names)} graph tags, {int(eligible.sum())} of them compared; {tag_e.size} links; '
      f'{n} chunks; the same-thing level {same:.4f}')

print('\n== A. the querytags ==')
print('querytag | list | readings topic temporal why activity concreteness | the four in its '
      'order | cosine to the query description -> weight | middle of the graph tags\' cosine to '
      'it, spread | its closest graph tag | graph tags picked')
hit = np.zeros(n, dtype=bool)
for i, tag in enumerate(query_tags):
    order = WK.facet_order(readings[i])
    row = np.where(eligible, cos[i], -np.inf)
    picked_tags = np.flatnonzero(row >= same)
    hit[chunk_e[cos[i][tag_e] >= same]] = True
    side = 'description' if i < len(content.tags) else 'question'
    print(f'  {i:2d} "{tag.text}" | {side} | ' + ' '.join(f'{r:g}' for r in readings[i]) + ' | '
          + ' > '.join(FACETS[j] for j in order)
          + f' | {A["description_cosines"][i]:.3f} -> {weight[i]:.3f} | {bulk[i]:.3f}, '
          f'{spread[i]:.4f} | "{names[int(np.argmax(row))]}" {row.max():.3f} | {picked_tags.size}')
print(f'chunks carrying a picked tag of any querytag: {int(hit.sum())} of {n}')

Q0 = 0
print(f'\n== B. one querytag against the graph tags: "{query_tags[Q0].text}" ==')
row = np.where(eligible, cos[Q0], -np.inf)
by = np.argsort(-row, kind='stable')
picked_tags = [t for t in by if row[t] >= same]
print(f'the middle graph tag is at {bulk[Q0]:.3f}; one spread is {spread[Q0]:.4f}; picked means '
      f'at or above {same:.4f}')
print('picked (graph tag | cosine | spreads above the middle | chunks it is on):')
for t in picked_tags:
    print(f'  "{names[t]}" | {row[t]:.3f} | {(row[t] - bulk[Q0]) / spread[Q0]:+.2f} | {on_chunks[t]}')
print('the next eight under the level, not picked:')
for t in by[len(picked_tags):len(picked_tags) + 8]:
    print(f'  "{names[t]}" | {row[t]:.3f} | {(row[t] - bulk[Q0]) / spread[Q0]:+.2f} | {on_chunks[t]}')
middle = int(eligible.sum()) // 2
print('five graph tags at the middle:')
for t in by[middle - 2:middle + 3]:
    print(f'  "{names[t]}" | {row[t]:.3f} | {(row[t] - bulk[Q0]) / spread[Q0]:+.2f} | {on_chunks[t]}')
above = int((row[eligible] > bulk[Q0]).sum())
print(f'graph tags above the middle, each giving its chunks a number above 0: {above}; links '
      f'with a number above 0 for this querytag: {int((fit[Q0] > 0).sum())} of {tag_e.size}; '
      f'chunks with a number above 0 for this querytag: '
      f'{int((np.bincount(chunk_e, weights=fit[Q0] > 0, minlength=n) > 0).sum())} of {n}')

print(f'\n== C. the links of the picked tags of "{query_tags[Q0].text}", in the order the '
      'facets give them ==')
edge_cos = cos[Q0][tag_e]
picked = np.flatnonzero(edge_cos >= same)
closest = float(row.max())
width = max(closest - same, 0.)
order = WK.facet_order(readings[Q0])
place, placed = WK.spread_by_facets(edge_cos[picked], closest, width * (1. + 1e-9) + 1e-12,
                                    layer['facet_class'][picked], order,
                                    layer['raw'][picked, 0])
print(f'the order of the four from its readings: {" > ".join(FACETS[j] for j in order)}; the '
      f'gaps: {layer["facet_class"].shape[1]} facets in classes one gap wide')
print('place | graph tag | chunk | product | the tag\'s cosine | on the link: '
      + ' '.join(FACETS[j] for j in order) + ' (class) | topic | the cosine the place gives | '
      'the number (spreads above the middle)')
for k in np.argsort(place):
    e = picked[k]
    vals = ' '.join(f'{layer["raw"][e, 1 + j]:.3f} ({layer["facet_class"][e, j]})' for j in order)
    print(f'  {place[k] + 1:2d} | "{names[tag_e[e]]}" | {short(chunk_e[e])} | '
          f'{product_of[chunk_e[e]]} | {edge_cos[e]:.3f} | {vals} | {layer["raw"][e, 0]:.3f} | '
          f'{placed[k]:.3f} | {fit[Q0][e]:.2f}')


def chunk_story(c, title):
    w = int(A['winner'][c])
    mine = links_of[c]
    print(f'\n{title}: {short(c)}  ({product_of[c]}, {kind_of[c]}, {mine.size} tags)')
    print(f'  the tags\' number {A["tags"][c]:.2f}; the querytag that gave it: '
          f'"{query_tags[w].text}"; the description\'s number {A["text"][c]:.2f}')
    print('  per querytag: its nearest tag on this chunk | that tag\'s cosine | picked | the '
          'number | times the weight')
    for i, tag in enumerate(query_tags):
        e = mine[int(np.argmax(fit[i][mine]))]
        print(f'    "{tag.text}": "{names[tag_e[e]]}" | {cos[i][tag_e[e]]:.3f} | '
              f'{"yes" if cos[i][tag_e[e]] >= same else "no"} | {fit[i][e]:.2f} | '
              f'{weight[i] * fit[i][e]:.2f}' + ('   <- the largest' if i == w else ''))
    print(f'  all its tags with their cosine to "{query_tags[w].text}":')
    for e in mine[np.argsort(-cos[w][tag_e[mine]])]:
        print(f'    "{names[tag_e[e]]}" {cos[w][tag_e[e]]:.3f}'
              + ('  picked' if cos[w][tag_e[e]] >= same else ''))


print('\n== D. a chunk that is hit ==')
chunk_story(int(chunk_e[picked[int(np.argmin(place))]]), 'the first chunk of C')

print('\n== E. chunks that are not hit ==')
tags_number = A['tags'].astype(float)
others = np.flatnonzero(~hit)
chunk_story(int(others[np.argmin(np.abs(tags_number[others] - np.median(tags_number)))]),
            'the chunk at the middle of the tags\' number')
chunk_story(int(others[np.argmax(tags_number[others])]),
            'the chunk with the largest tags\' number among those not hit')
print(f'\nthe tags\' number: the {int(hit.sum())} hit chunks lie between '
      f'{tags_number[hit].min():.2f} and {tags_number[hit].max():.2f}, middle '
      f'{np.median(tags_number[hit]):.2f}; the {others.size} others between '
      f'{tags_number[others].min():.2f} and {tags_number[others].max():.2f}, middle '
      f'{np.median(tags_number[others]):.2f}; others above the lowest hit chunk: '
      f'{int((tags_number[others] > tags_number[hit].min()).sum())}')

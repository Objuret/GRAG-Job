"""One question tag of the made-up question: the picked graph tags (within the largest
self-difference of the closest), their edges, and the order the four facets give them in that
question tag's own order, each facet in classes of its retrain gap. No gold, no model call."""
import sys
from pathlib import Path

import numpy as np

ROOT = Path('C:/Coding/exjobbet/GRAG-Job')
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'prod'), str(ROOT / 'test')]
from artefact.v4_strength import standing
from artefact.v4_multikey import facet_order, read_facet_gaps
from artefact.v4_rank import ADJUST_FACETS, ALL_FACETS
import walkthrough as W

here = Path(sys.argv[1])
wanted = sys.argv[2] if len(sys.argv) > 2 else 'rollback failures'
X = W.read_inputs(here / 'madeup_all_same.npz')
XQ = W.read_inputs(here / 'madeup_text_query.npz')
el = np.asarray(X['eligible'], dtype=bool)
et, ec = np.asarray(X['edge_tag']), np.asarray(X['edge_chunk'])
ok = el[et]
et, ec = et[ok], ec[ok]
facets = np.asarray(X['edge_facets'])[ok]
topic = np.asarray(X['edge_topic'])[ok]
cos = np.asarray(X['query_tag_cosines'])
read = np.asarray(X['query_readings'])
kinds = X['chunk_kinds']
product = np.asarray(X['product'])
pnames = X['product_names']
tags = X['graph_tags']
gaps = np.asarray(read_facet_gaps(ROOT / 'output/facet_pairs/rounds/round1/bootstrap/BANDS.md')[0])
pc, pt = np.asarray(X['probe_cosines']), np.asarray(X['probe_tags'])
width = float((1. - pc[np.arange(pt.size), pt]).max())
d_desc = standing(np.asarray(X['d_description']))[0]
d_quest = standing(np.asarray(XQ['d_question']))[0]
best_all = facets.max(axis=0)

for i, text in enumerate(X['query_texts']):
    if text != wanted:
        continue
    row = cos[i]
    order = facet_order(read[i])
    picked = np.flatnonzero(el & (row >= row[el].max() - width))
    rows = np.flatnonzero(np.isin(et, picked))
    cls = np.floor((best_all - facets[rows]) / gaps).astype(np.int64)      # classes below the graph-wide best
    keyed = cls[:, list(order)]
    rank = np.lexsort((-row[et[rows]], -topic[rows], keyed[:, 3], keyed[:, 2], keyed[:, 1], keyed[:, 0]))
    print(f'question tag "{text}" ({X["query_lists"][i]} list)')
    print('  readings: ' + ', '.join(f'{name} {read[i][ALL_FACETS.index(name)]:.2f}' for name in ALL_FACETS))
    print('  facet order: ' + ' > '.join(ADJUST_FACETS[j] for j in order))
    print(f'  picked: {picked.size} graph tags within {width:.4f} of the closest ({row[el].max():.3f}); {rows.size} edges, '
          f'{np.unique(ec[rows]).size} chunks')
    print(f'  "equal" per facet (retrain gap): ' + ', '.join(f'{ADJUST_FACETS[j]} {gaps[j]:.2f}' for j in order))
    head = (f'  {"#":>2s} {"graph tag":28s} {"close":>5s} | ' + ' | '.join(f'{ADJUST_FACETS[j][:8]:>8s} cls' for j in order)
            + f' | {"topic":>5s} | {"desc":>5s} {"quest":>5s} | chunk')
    print(head)
    for place, r in enumerate(rank, 1):
        e = rows[r]
        c = ec[e]
        cells = ' | '.join(f'{facets[e][j]:8.2f} {cls[r][j]:3d}' for j in order)
        print(f'  {place:2d} {tags[et[e]][:28]:28s} {row[et[e]]:5.3f} | {cells} | {topic[e]:5.2f} | {d_desc[c]:5.2f} {d_quest[c]:5.2f} | '
              f'{kinds[c][:12]} {pnames[product[c]] if product[c] >= 0 else "-"}')
    print()

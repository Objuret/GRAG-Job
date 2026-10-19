"""The made-up question: each route in classes of its own repeat width (the pool is the top
class of any route), and the first 15 inside the pool under different inside-orders.
Widths: tags = a tag name against its own stored vector (largest shortfall over the dump's
probes); descriptions = WRITE_NOISE below. No gold, no test question, no model call."""
import sys
from pathlib import Path

import numpy as np

ROOT = Path('C:/Coding/exjobbet/GRAG-Job')
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'prod'), str(ROOT / 'test')]
from artefact.v4_strength import standing, centrality
from artefact.v4_multikey import facet_order, read_facet_gaps
from artefact.v4_rank import ADJUST_FACETS
import walkthrough as W

WRITE_NOISE = 0.028   # two writes of one chunk description, measured 2026-09-21 (CLAUDE.md)

here = Path(sys.argv[1])
X = W.read_inputs(here / 'madeup_all_same.npz')
XQ = W.read_inputs(here / 'madeup_text_query.npz')
el = np.asarray(X['eligible'], dtype=bool)
et, ec = np.asarray(X['edge_tag']), np.asarray(X['edge_chunk'])
ok = el[et]
et, ec = et[ok], ec[ok]
facets = np.asarray(X['edge_facets'])[ok]
topic = np.asarray(X['edge_topic'])[ok]
n = len(X['chunk_ids'])
cos = np.asarray(X['query_tag_cosines'])
read = np.asarray(X['query_readings'])
kinds = np.array(X['chunk_kinds'])
product = np.asarray(X['product'])
names = X['product_names']
gaps, _ = read_facet_gaps(ROOT / 'output/facet_pairs/rounds/round1/bootstrap/BANDS.md')
gaps = np.asarray(gaps)

pc, pt = np.asarray(X['probe_cosines']), np.asarray(X['probe_tags'])
short = 1. - pc[np.arange(pt.size), pt]
widths = {'median': float(np.median(short)), 'largest': float(short.max())}

d_same = np.asarray(X['d_description'])
q_same = np.asarray(X['d_question'])
q_quest = np.asarray(XQ['d_question'])
edge = names.index('EdgeForce') if 'EdgeForce' in names else -1

for wname, width in widths.items():
    print(f'=== tag width = the {wname} self-difference {width:.4f}; description width {WRITE_NOISE} ===')
    # tag route: per (question tag, edge) the class of the tag's closeness below that question tag's closest
    best_class = np.full(n, np.iinfo(np.int64).max)
    carrier = np.full((n, 2), -1)            # question tag, edge index
    for i in range(cos.shape[0]):
        row = cos[i]
        cls_tag = np.floor((row[el].max() - row) / width).astype(np.int64)
        cls_edge = cls_tag[et]
        order = np.lexsort((-row[et], cls_edge))          # class, then the closer tag
        first = np.unique(ec[order], return_index=True)
        chunks, at = first[0], order[first[1]]
        better = cls_edge[at] < best_class[chunks]
        best_class[chunks[better]] = cls_edge[at][better]
        carrier[chunks[better], 0] = i
        carrier[chunks[better], 1] = at[better]
    tag_class = best_class
    desc_class = np.floor((d_same.max() - d_same) / WRITE_NOISE).astype(np.int64)
    quest_class_same = np.floor((q_same.max() - q_same) / WRITE_NOISE).astype(np.int64)
    quest_class_q = np.floor((q_quest.max() - q_quest) / WRITE_NOISE).astype(np.int64)
    for label, quest_class in (('raw question in question mode', quest_class_q),
                               ('raw question in the same mode', quest_class_same)):
        print(f'  -- {label}')
        for name, cls in (('tags', tag_class), ('description', desc_class), ('raw question', quest_class)):
            sizes = [int((cls == k).sum()) for k in range(4)]
            in_edge = [int(((cls == k) & (product == edge)).sum()) for k in range(4)]
            print(f'     {name:13s} chunks in class 0 / 1 / 2 / 3: {" / ".join(map(str, sizes))}   of them in EdgeForce: {" / ".join(map(str, in_edge))}')
        hit = np.minimum(np.minimum(tag_class, desc_class), quest_class)
        for k in range(3):
            pool = np.flatnonzero(hit == k)
            by = {'tags only': int(((tag_class == k) & (desc_class > k) & (quest_class > k)).sum()),
                  'description only': int(((desc_class == k) & (tag_class > k) & (quest_class > k)).sum()),
                  'raw question only': int(((quest_class == k) & (tag_class > k) & (desc_class > k)).sum())}
            more = pool.size - sum(by.values())
            kc = {str(kind): int((kinds[pool] == kind).sum()) for kind in sorted(set(kinds[pool]))}
            print(f'     pool class {k}: {pool.size} chunks ({by}, by two or three routes {more}); in EdgeForce {int((product[pool] == edge).sum())}; kinds {kc}')
    print()

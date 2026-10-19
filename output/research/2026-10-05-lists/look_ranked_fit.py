"""The made-up question: the tag side with the four facets as a ranking inside "equally
close", against the tag side as closeness alone. The graph tags of a question tag stand in
classes one self-difference wide below its closest tag; inside a class the edges are ordered
by the four facets in that question tag's order (each facet in classes of its retrain gap),
then topic, then closeness; an edge's closeness becomes its class's upper edge minus
width * (its place inside the class / the class's size). No gold, no model call."""
import sys
from pathlib import Path

import numpy as np

ROOT = Path('C:/Coding/exjobbet/GRAG-Job')
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'prod'), str(ROOT / 'test')]
from artefact.v4_strength import standing, centrality
from artefact.v4_multikey import facet_order, read_facet_gaps
import walkthrough as W


def ranked_closeness(cos_e, best, width, facet_class, order, topic):
    """Per edge: the class below `best`, the place inside the class, the adjusted closeness."""
    cls = np.maximum(np.floor((best - cos_e) / width), 0).astype(np.int64)
    keys = facet_class[:, list(order)]
    idx = np.lexsort((np.arange(cos_e.size), -cos_e, -topic, keys[:, 3], keys[:, 2], keys[:, 1],
                      keys[:, 0], cls))
    sorted_cls = cls[idx]
    starts = np.flatnonzero(np.r_[True, sorted_cls[1:] != sorted_cls[:-1]])
    sizes = np.diff(np.r_[starts, sorted_cls.size])
    place = np.arange(sorted_cls.size) - np.repeat(starts, sizes)
    adjusted = np.empty(cos_e.size)
    adjusted[idx] = best - width * (sorted_cls + place / np.repeat(sizes, sizes))
    return cls, adjusted


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
cen = centrality(np.asarray(X['query_tag_description_cosines']))
product = np.asarray(X['product'])
pnames = X['product_names']
edge = pnames.index('EdgeForce')
gaps = np.asarray(read_facet_gaps(ROOT / 'output/facet_pairs/rounds/round1/bootstrap/BANDS.md')[0])
facet_class = np.floor((facets.max(axis=0) - facets) / gaps).astype(np.int64)
pc, pt = np.asarray(X['probe_cosines']), np.asarray(X['probe_tags'])
short = 1. - pc[np.arange(pt.size), pt]
text = np.maximum(standing(np.asarray(X['d_description']))[0], standing(np.asarray(XQ['d_question']))[0])


def tag_side(width):
    best_term = np.zeros(n)
    for i in range(cos.shape[0]):
        row = cos[i]
        z, bulk, spread = standing(row[el])
        if width is None:
            value_e = row[et]
        else:
            _, value_e = ranked_closeness(row[et], row[el].max(), width, facet_class, facet_order(read[i]), topic)
        fit_e = np.clip((value_e - bulk) / spread, 0., None)
        per_chunk = np.zeros(n)
        np.maximum.at(per_chunk, ec, fit_e)
        best_term = np.maximum(best_term, cen[i] * per_chunk)
    return best_term


plain = tag_side(None)
print(f'{"tag side":34s} {"first 15 shared with closeness alone":>38s} {"...of the first 50":>20s} | tags + text: first 15 shared, in EdgeForce | largest change of a chunk\'s tag term')
base15 = set(np.argsort(-plain, kind='stable')[:15].tolist())
base50 = set(np.argsort(-plain, kind='stable')[:50].tolist())
sum15 = np.argsort(-(plain + text), kind='stable')[:15]
print(f'{"closeness alone":34s} {15:>38d} {50:>20d} | {15:>3d}, {int((product[sum15] == edge).sum()):2d} |')
for name, width in (('ranked, median self-difference', float(np.median(short))),
                    ('ranked, largest self-difference', float(short.max()))):
    ranked = tag_side(width)
    t15 = set(np.argsort(-ranked, kind='stable')[:15].tolist())
    t50 = set(np.argsort(-ranked, kind='stable')[:50].tolist())
    s15 = np.argsort(-(ranked + text), kind='stable')[:15]
    print(f'{name:34s} {len(t15 & base15):>38d} {len(t50 & base50):>20d} | {len(set(s15.tolist()) & set(sum15.tolist())):>3d}, '
          f'{int((product[s15] == edge).sum()):2d} | {np.abs(ranked - plain).max():.3f} spreads (width {width:.4f})')

"""Where the first rows of each list sit, by product, on the made-up question. No gold."""
import sys
from pathlib import Path

import numpy as np

ROOT = Path('C:/Coding/exjobbet/GRAG-Job')
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'prod'), str(ROOT / 'test')]
from artefact.v4_strength import standing, centrality
import walkthrough as W

SCR = Path(sys.argv[1])
same = W.read_inputs(SCR / 'madeup_all_same.npz')
other = W.read_inputs(SCR / 'madeup_text_query.npz')
product = np.asarray(same['product'])
names = same['product_names']
print('question:', same['question'])
print('description:', same['description'])
print('product names:', len(names), 'e.g.', names[:5])
el = np.asarray(same['eligible'], dtype=bool)
et, ec = np.asarray(same['edge_tag']), np.asarray(same['edge_chunk'])
ok = el[et]
et, ec = et[ok], ec[ok]
n = len(same['chunk_ids'])
cos = np.asarray(same['query_tag_cosines'])
cen = centrality(np.asarray(same['query_tag_description_cosines']))
T = np.full((cos.shape[0], n), -np.inf)
for i in range(cos.shape[0]):
    z, _, _ = standing(cos[i][el])
    full = np.full(cos.shape[1], -np.inf)
    full[el] = z
    np.maximum.at(T[i], ec, full[et])
tags = (cen[:, None] * np.clip(np.where(np.isfinite(T), T, 0.), 0., None)).max(axis=0)
lists = {
    'tags (best tag carries)': tags,
    'description, same mode': standing(np.asarray(same['d_description']))[0],
    'description, question mode': standing(np.asarray(other['d_description']))[0],
    'raw question, same mode': standing(np.asarray(same['d_question']))[0],
    'raw question, question mode': standing(np.asarray(other['d_question']))[0],
}
sizes = np.bincount(product[product >= 0], minlength=len(names))
print()
print(f'{"list":30s} ' + '  '.join(f'first {m}: commonest product (share), products' for m in (15, 50, 150)))
for key, values in lists.items():
    cells = []
    for m in (15, 50, 150):
        top = np.argsort(-values, kind='stable')[:m]
        inside = product[top][product[top] >= 0]
        counts = np.bincount(inside, minlength=len(names))
        best = int(counts.argmax())
        cells.append(f'{names[best]} {int(counts[best])}/{m}, {int((counts > 0).sum())} products')
    print(f'{key:30s} ' + '  |  '.join(cells))
edge = [i for i, name in enumerate(names) if name.lower() == 'edgeforce']
if edge:
    e = edge[0]
    print()
    print(f'EdgeForce holds {int(sizes[e])} of {n} chunks. Of the first 15 / 50 / 150 of each list, in EdgeForce:')
    for key, values in lists.items():
        order = np.argsort(-values, kind='stable')
        print(f'   {key:30s} ' + ' / '.join(str(int((product[order[:m]] == e).sum())) for m in (15, 50, 150)))

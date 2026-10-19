"""How alike two runs' delivered sets are, and how alike they would be if the new run's own order
were read with the named product's chunks first. Per question: the overlap of the new run's
delivered chunks with the v3 walk's delivered chunks; and the overlap of the first k chunks of the
new run's order restricted to the product the question id names (k = the number the v3 walk
delivered) with the same v3 set. Reads meta.ranking and meta.returned of both runs' arm_outputs
and the graph (chunk -> product). No gold, no scores, no question text, no model call.

What the numbers are NOT: the other run's delivered set is not the gold, so an overlap here is
agreement between two builds and says nothing about recall, a recall gap or a ceiling on one."""
import io
import json
import os
import sys
from pathlib import Path

import numpy as np

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
ROOT = Path('C:/Coding/exjobbet/GRAG-Job')
sys.path[:0] = [str(ROOT / 'prod'), str(ROOT / 'test')]
os.environ['NEO4J_DATABASE'] = 'herb-eval-volmax'
from graph import db

driver = db._driver()
with driver.session(database='herb-eval-volmax', default_access_mode='READ') as session:
    product_of = {r['chunk']: r['product'] for r in session.run(
        'MATCH (c:Chunk)-[:product]->(p:Product) RETURN c.chunk_id AS chunk, p.name AS product')}
driver.close()


def read(folder, key):
    out = {}
    with open(ROOT / 'output/k=chars' / folder / 'arm_outputs.jsonl', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                row = json.loads(line)
                out[row['id']] = (row['meta']['ranking'][key], int(row['meta']['returned']))
    return out


new = read('artefact_v4__gold100__cb72000__20261005T223320Z', 'ordered_chunk_ids')
for label, folder in (('v3 walk, no growth (09-13)', 'artefact_v3__gold100__cb72000__20260913T143959Z'),
                      ('artefact_scope (09-03)', 'artefact_scope__gold100__cb72000__20260903T153153Z')):
    old = read(folder, 'chunk_ids')
    plain, first, k_new, k_old, rank_of_old = [], [], [], [], []
    for q in sorted(new):
        if q not in old:
            continue
        order, k = new[q]
        old_order, k2 = old[q]
        old_set = set(old_order[:k2])
        product = q.split('::')[0]
        inside = [c for c in order if product_of.get(c) == product]
        plain.append(len(set(order[:k]) & old_set) / len(old_set))
        first.append(len(set(inside[:k2]) & old_set) / len(old_set))
        k_new.append(k); k_old.append(k2)
        place = {c: i for i, c in enumerate(inside)}
        rank_of_old.extend(place[c] for c in old_set if c in place)
    plain, first = np.array(plain), np.array(first)
    print(f'{label}: {len(plain)} questions; delivered per question median {np.median(k_new):.0f} (new) / {np.median(k_old):.0f} (it)')
    print(f'   share of its delivered chunks the new run also delivered: mean {plain.mean():.3f}, '
          f'median {np.median(plain):.3f}; none shared on {int((plain == 0).sum())} questions')
    print(f'   the same, reading the new run\'s order with the id product\'s chunks first: mean {first.mean():.3f}, '
          f'median {np.median(first):.3f}; none shared on {int((first == 0).sum())} questions')
    r = np.array(rank_of_old)
    print(f'   where its delivered chunks stand in the new run\'s order among the product\'s own chunks '
          f'(place 0 = first): 25% / median / 75% / 90% = ' + ' / '.join(str(int(x)) for x in np.percentile(r, [25, 50, 75, 90])))

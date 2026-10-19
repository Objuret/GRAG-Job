"""What the question-side tag that IS the product name does in the saved run: how many delivered
chunks it carries (the winning query tag of a delivered row), and how many of those sit under the
product. Reads arm_outputs.jsonl (ids, meta.ranking, meta.interpreter counts), the saved
querytagger answers (tag texts compared with the product name, never printed) and the graph
(chunk -> product). No gold, no question text, no model call."""
import io
import json
import os
import re
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
out = ROOT / 'output/k=chars/artefact_v4__gold100__cb72000__20261005T223320Z'
cache = ROOT / 'output/private/artefact_v4_cache/querytag'


def unique(texts):
    seen, kept = set(), []
    for t in texts:
        if t not in seen:
            seen.add(t)
            kept.append(t)
    return kept


questions = mismatch = with_tag = 0
carried_by_product_tag = carried_in_product = delivered_total = 0
picked_by_product_tag = []
share_rows = []
other_in_product = other_total = 0
for line in open(out / 'arm_outputs.jsonl', encoding='utf-8'):
    if not line.strip():
        continue
    row = json.loads(line)
    meta = row['meta']
    product = row['id'].split('::')[0]
    key = meta['interpreter']['stages'][0]['key']
    held = json.loads(next(cache.glob(f'{key}*')).read_text(encoding='utf-8'))
    body = json.loads(re.search(r'\{.*\}', held['response']['choices'][0]['message']['content'], re.S).group(0))
    texts = unique([str(t['t']) for t in body.get('tags', [])]) + unique([str(t['t']) for t in body.get('query_tags', [])])
    questions += 1
    if len(texts) != meta['interpreter']['query_tags']:
        mismatch += 1
        continue
    is_product = [t.casefold().strip() == product.casefold() for t in texts]
    winners = meta['ranking']['delivered_query_tags']
    chunks = meta['ranking']['delivered_chunk_ids']
    delivered_total += len(chunks)
    picked = meta['diagnostics']['rank'].get('picked_edges_per_query_tag') or []
    if any(is_product):
        with_tag += 1
        n = k = 0
        for w, c in zip(winners, chunks):
            inside = product_of.get(c) == product
            if w is not None and 0 <= w < len(texts) and is_product[w]:
                n += 1
                k += inside
            else:
                other_total += 1
                other_in_product += inside
        carried_by_product_tag += n
        carried_in_product += k
        share_rows.append(n / len(chunks) if chunks else 0.)
        picked_by_product_tag.extend(picked[i] for i, flag in enumerate(is_product) if flag and i < len(picked))
print(f'questions {questions}; tag lists not matching the run\'s count: {mismatch}; with a query tag that is the product name: {with_tag}')
print(f'delivered (credited) chunks over those questions: carried by the product-name query tag {carried_by_product_tag}, '
      f'of them under the product {carried_in_product}; carried by another query tag {other_total}, of them under the product {other_in_product}')
s = np.array(share_rows)
print(f'share of a question\'s delivered chunks carried by the product-name tag: mean {s.mean():.3f}, median {np.median(s):.3f}, '
      f'questions where it carries none {int((s == 0).sum())}, where it carries half or more {int((s >= .5).sum())}')
p = np.array(picked_by_product_tag)
print(f'graph-tag edges the product-name query tag picks at the same-thing level: none on {int((p == 0).sum())} of {p.size}, '
      f'median {np.median(p):.0f}, largest {int(p.max()) if p.size else 0}')

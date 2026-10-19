"""Record kind and tag count of what each artefact run delivered on the same 99 questions, beside
the pool. Reads meta.ranking / meta.returned and the graph. No gold, no question text."""
import io
import json
import os
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
ROOT = Path('C:/Coding/exjobbet/GRAG-Job')
sys.path[:0] = [str(ROOT / 'prod'), str(ROOT / 'test')]
os.environ['NEO4J_DATABASE'] = 'herb-eval-volmax'
from graph import db

driver = db._driver()
with driver.session(database='herb-eval-volmax', default_access_mode='READ') as session:
    rows = session.run('MATCH (c:Chunk)-[:product]->(p:Product) OPTIONAL MATCH (c)-[:HAS_TAG]->(t:Tag) '
                       'RETURN c.chunk_id AS chunk, c.kind AS kind, p.name AS product, count(t) AS tags').data()
driver.close()
kind = {r['chunk']: r['kind'] for r in rows}
tags = {r['chunk']: r['tags'] for r in rows}
product_of = {r['chunk']: r['product'] for r in rows}
KINDS = ['slack_thread_batch', 'pr_batch', 'document_part', 'meeting_transcript', 'document', 'url_batch',
         'meeting_transcript_part', 'meeting_chat_batch']
pool = Counter(kind.values())
print(f'{"":38s}' + ''.join(f'{k[:14]:>15s}' for k in KINDS) + f'{"tags/chunk":>12s}')
print(f'{"pool (4,808 chunks)":38s}' + ''.join(f'{pool[k] / len(rows):15.3f}' for k in KINDS) + f'{np.mean(list(tags.values())):12.1f}')
RUNS = [('artefact_v4, new build', 'artefact_v4__gold100__cb72000__20261005T223320Z', 'ordered_chunk_ids'),
        ('artefact_v3 walk, no growth', 'artefact_v3__gold100__cb72000__20260913T143959Z', 'chunk_ids'),
        ('artefact_scope', 'artefact_scope__gold100__cb72000__20260903T153153Z', 'chunk_ids')]
new_ids = None
for label, folder, key in RUNS:
    got, inside = Counter(), Counter()
    count, n = [], 0
    with open(ROOT / 'output/k=chars' / folder / 'arm_outputs.jsonl', encoding='utf-8') as f:
        held = {}
        for line in f:
            if line.strip():
                row = json.loads(line)
                held[row['id']] = (row['meta']['ranking'][key], int(row['meta']['returned']))
    if new_ids is None:
        new_ids = set(held)
    for q in sorted(new_ids):
        order, k = held[q]
        product = q.split('::')[0]
        for c in order[:k]:
            got[kind.get(c)] += 1
            count.append(tags.get(c, 0))
            n += 1
            if product_of.get(c) == product:
                inside[kind.get(c)] += 1
    print(f'{label:38s}' + ''.join(f'{got[k] / n:15.3f}' for k in KINDS) + f'{np.mean(count):12.1f}')
    m = sum(inside.values())
    print(f'{"   its chunks under the id product":38s}' + ''.join(f'{inside[k] / m:15.3f}' for k in KINDS))
# the pool restricted to the products the 99 questions name, weighted by question
weighted = Counter()
total = 0
by_product = {}
for c, p in product_of.items():
    by_product.setdefault(p, Counter())[kind[c]] += 1
for q in sorted(new_ids):
    p = q.split('::')[0]
    for k, v in by_product[p].items():
        weighted[k] += v
        total += v
print(f'{"the id products\' own chunks":38s}' + ''.join(f'{weighted[k] / total:15.3f}' for k in KINDS))

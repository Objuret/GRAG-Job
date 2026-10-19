"""Where the delivered chunks sit, per artefact run on the hundred: the share of each question's
delivered chunks that hang under the product its question id names, with the recall_id beside it.

Reads the run folders' arm_outputs.jsonl (question ids, meta.returned and the ranked chunk ids
only; never the question, the contexts or the answer text), eval_results.jsonl (scores) and the
graph (chunk -> product). No gold file, no model call, nothing written but this print."""
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
with driver.session(database='herb-eval-volmax') as session:
    rows = session.run('MATCH (c:Chunk)-[:product]->(p:Product) '
                       'RETURN c.chunk_id AS chunk, p.name AS product').data()
driver.close()
product_of = {r['chunk']: r['product'] for r in rows}
sizes = {}
for product in product_of.values():
    sizes[product] = sizes.get(product, 0) + 1
print(f'chunks with a product edge {len(product_of)}, products {len(sizes)}, '
      f'chunks per product {min(sizes.values())}-{max(sizes.values())}')

RUNS = [('artefact_v4, new build (10-05)', 'artefact_v4__gold100__cb72000__20261005T223320Z', 'ordered_chunk_ids'),
        ('artefact_v3 walk, no growth (09-13)', 'artefact_v3__gold100__cb72000__20260913T143959Z', 'chunk_ids'),
        ('artefact_v3 walk, growth (09-13)', 'artefact_v3__gold100__cb72000__20260913T142842Z', 'chunk_ids'),
        ('artefact_scope (09-03)', 'artefact_scope__gold100__cb72000__20260903T153153Z', 'chunk_ids')]


def read(folder, key):
    order, returned = {}, {}
    with open(ROOT / 'output/k=chars' / folder / 'arm_outputs.jsonl', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                row = json.loads(line)
                meta = row['meta']
                order[row['id']] = meta['ranking'][key]
                returned[row['id']] = int(meta['returned'])
    scores = {}
    with open(ROOT / 'output/k=chars' / folder / 'eval_results.jsonl', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                row = json.loads(line)
                if row['metric'] == 'context_recall_id' and isinstance(row['value'], (int, float)):
                    scores[row['question_id']] = row['value']
    return order, returned, scores


new_order, _, _ = read(*RUNS[0][1:])
questions = sorted(new_order)
print(f'questions compared: the {len(questions)} the new run answered')
print()
head = (f'{"run":36s} {"delivered":>9s} {"in id product":>13s} {"all in":>6s} {"none in":>7s} '
        f'{"first 50 in":>11s} {"first 177 in":>12s} | recall_id where all in / some / none')
print(head)
kept = {}
for label, folder, key in RUNS:
    order, returned, scores = read(folder, key)
    share, recall, at50, at177, n_delivered = [], [], [], [], []
    for q in questions:
        if q not in order or q not in scores:
            continue
        product = q.split('::')[0]
        inside = np.array([product_of.get(c) == product for c in order[q]])
        k = returned[q]
        n_delivered.append(k)
        share.append(inside[:k].mean() if k else 0.)
        at50.append(inside[:50].mean())
        at177.append(inside[:177].mean())
        recall.append(scores[q])
    share, recall = np.array(share), np.array(recall)
    kept[label] = (share, recall)

    def f(mask):
        return f'{recall[mask].mean():.3f} ({int(mask.sum())})' if mask.any() else '-'
    print(f'{label:36s} {np.median(n_delivered):9.0f} {share.mean():13.3f} {int((share == 1).sum()):6d} '
          f'{int((share == 0).sum()):7d} {np.mean(at50):11.3f} {np.mean(at177):12.3f} | '
          f'{f(share == 1)} / {f((share > 0) & (share < 1))} / {f(share == 0)}')
print()
share, recall = kept[RUNS[0][0]]
print('the new run, questions by the share of delivered chunks under the id product: band, questions, mean recall_id')
for low, high in ((0., 0.001), (0.001, 0.25), (0.25, 0.5), (0.5, 0.75), (0.75, 0.999), (0.999, 1.01)):
    mask = (share >= low) & (share < high)
    if mask.any():
        print(f'   {low:.2f}-{min(high, 1.):.2f}: {int(mask.sum()):3d} questions, recall_id {recall[mask].mean():.3f}')
old_share, old_recall = kept[RUNS[1][0]]
if old_share.size == share.size:
    print()
    print('the same questions in the v3 walk (no growth): band of the NEW run, mean share there, mean recall_id there')
    for low, high in ((0., 0.001), (0.001, 0.25), (0.25, 0.5), (0.5, 0.75), (0.75, 0.999), (0.999, 1.01)):
        mask = (share >= low) & (share < high)
        if mask.any():
            print(f'   {low:.2f}-{min(high, 1.):.2f}: share {old_share[mask].mean():.3f}, recall_id {old_recall[mask].mean():.3f}')

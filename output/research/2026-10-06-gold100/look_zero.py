"""The questions on which the new run delivers none of the gold (recall_id 0): how much of what
it delivered there sits under the product the question id names, and what the v3 walk scores on
the same questions. Reads eval_results.jsonl, meta.ranking / meta.returned and the graph
(chunk -> product). No gold file, no question text, no model call."""
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
RUNS = ROOT / 'output/k=chars'


def recall(folder):
    out, kind = {}, {}
    for line in (RUNS / folder / 'eval_results.jsonl').read_text(encoding='utf-8').splitlines():
        if line.strip():
            r = json.loads(line)
            if r['metric'] == 'context_recall_id' and r.get('status') == 'ok':
                out[r['question_id']] = r['value']
                kind[r['question_id']] = r['type']
    return out, kind


new, kind = recall('artefact_v4__gold100__cb72000__20261005T223320Z')
old, _ = recall('artefact_v3__gold100__cb72000__20260913T143959Z')
vec, _ = recall('vector__gold100__cb72000__20260814T145615Z')
share = {}
with open(RUNS / 'artefact_v4__gold100__cb72000__20261005T223320Z' / 'arm_outputs.jsonl', encoding='utf-8') as f:
    for line in f:
        if line.strip():
            row = json.loads(line)
            order, k = row['meta']['ranking']['ordered_chunk_ids'], int(row['meta']['returned'])
            product = row['id'].split('::')[0]
            share[row['id']] = float(np.mean([product_of.get(c) == product for c in order[:k]]))
zero = sorted(q for q in new if new[q] == 0)
rest = sorted(q for q in new if new[q] > 0)
for label, ids in (('recall 0', zero), ('recall above 0', rest)):
    s = np.array([share[q] for q in ids])
    print(f'new run, questions at {label}: {len(ids)}; delivered under the id product: mean {s.mean():.3f}, '
          f'median {np.median(s):.3f}, under a quarter on {int((s < .25).sum())}, all on {int((s == 1).sum())}; '
          f'the v3 walk on the same questions: mean recall_id {np.mean([old[q] for q in ids]):.3f} '
          f'(at 0 on {sum(old[q] == 0 for q in ids)}); vector {np.mean([vec[q] for q in ids]):.3f}')
types = {}
for q in zero:
    types[kind[q]] = types.get(kind[q], 0) + 1
print('question types of the zeros:', dict(sorted(types.items())),
      '| of all 99:', {t: sum(1 for q in new if kind[q] == t) for t in sorted(set(kind.values()))})
low = sorted(q for q in new if share[q] < .25)
print(f'questions with under a quarter of the delivered chunks under the id product: {len(low)}; '
      f'at recall 0: {sum(new[q] == 0 for q in low)}; mean recall_id {np.mean([new[q] for q in low]):.3f}; '
      f'v3 walk on them {np.mean([old[q] for q in low]):.3f}')
high = sorted(q for q in new if share[q] >= .75)
print(f'questions with three quarters or more under the id product: {len(high)}; at recall 0: '
      f'{sum(new[q] == 0 for q in high)}; mean recall_id {np.mean([new[q] for q in high]):.3f}; '
      f'v3 walk on them {np.mean([old[q] for q in high]):.3f}')

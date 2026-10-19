"""Every run's recall_id beside the new run's, with the 99 questions grouped by how much of the
new run's delivery sits under the product the question id names. Reads eval_results.jsonl,
meta.ranking / meta.returned of the new run and the graph (chunk -> product). No gold file, no
question text, no model call."""
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
NEW = 'artefact_v4__gold100__cb72000__20261005T223320Z'


def recall(folder):
    out = {}
    for line in (RUNS / folder / 'eval_results.jsonl').read_text(encoding='utf-8').splitlines():
        if line.strip():
            r = json.loads(line)
            if r['metric'] == 'context_recall_id' and r.get('status') == 'ok':
                out[r['question_id']] = r['value']
    return out


new = recall(NEW)
others = {'v3 walk': recall('artefact_v3__gold100__cb72000__20260913T143959Z'),
          'scope': recall('artefact_scope__gold100__cb72000__20260903T153153Z'),
          'v2': recall('artefact_v2__gold100__cb72000__20260913T145627Z'),
          'vector': recall('vector__gold100__cb72000__20260814T145615Z'),
          'lucene': recall('lucene__gold100__cb72000__20260814T134547Z')}
share = {}
for line in open(RUNS / NEW / 'arm_outputs.jsonl', encoding='utf-8'):
    if line.strip():
        row = json.loads(line)
        order, k = row['meta']['ranking']['ordered_chunk_ids'], int(row['meta']['returned'])
        product = row['id'].split('::')[0]
        share[row['id']] = float(np.mean([product_of.get(c) == product for c in order[:k]]))
bands = [('all delivered under the product', lambda x: x == 1),
         ('three quarters or more', lambda x: x >= .75),
         ('a quarter to three quarters', lambda x: .25 <= x < .75),
         ('under a quarter', lambda x: x < .25)]
print(f'{"band of the new run":34s} {"n":>3s} {"new":>6s} ' + ' '.join(f'{k:>8s}' for k in others))
for label, inside in bands:
    ids = [q for q in new if inside(share[q])]
    print(f'{label:34s} {len(ids):3d} {np.mean([new[q] for q in ids]):6.3f} '
          + ' '.join(f'{np.mean([o[q] for q in ids]):8.3f}' for o in others.values()))

"""How much of each question's gold the places the querytagger returned from the tree hold.

For a run made under HERB_V4_SCOPE=tree (or product): per question the places it returned (read
from the saved row's meta.area), the chunks under them (the arm's own `scope_tree`), and the gold
chunks among them, through the harness's gold mapping. COUNTS ONLY: no question text, no
citation, no chunk text or id, and no place name is printed - a place is shown as its depth
(0 product, 1 record kind, 2 channel) and whether it holds gold. No model call (blocked)."""
import io
import json
import os
import sys
from pathlib import Path

import numpy as np

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
os.environ['HERB_V4_OFFLINE'] = 'on'
ROOT = Path('C:/Coding/exjobbet/GRAG-Job')
sys.path[:0] = [str(ROOT / 'prod'), str(ROOT / 'test')]
from harness import chat, orchestrator, questions as QS


def _blocked(*args, **kwargs):
    raise RuntimeError('model call blocked: this measurement makes none')


chat.post = _blocked
import arms.artefact_v2 as A2
import arms.artefact_v4 as V

RUN = ROOT / 'output/k=chars' / sys.argv[1]
prepared = V.prepare_over_corpus(orchestrator.open_corpus(orchestrator.DEFAULT_CORPUS))
try:
    tree = V._scope_tree(prepared)
finally:
    prepared.close()
docs = {}
ids_of = [set(A2._resolve_chunk(row, docs)[1]) for row in prepared.chunk_rows]
rows = [json.loads(line) for line in open(RUN / 'arm_outputs.jsonl', encoding='utf-8') if line.strip()]
truth = {q.id: q for q in QS.load_questions() if q.id in {r['id'] for r in rows}}
print(f'run {RUN.name}; questions {len(rows)}; places in the tree {tree["places"]}')
print('per question: gold chunks | under the returned places | under their products only | '
      'the returned places as depth:holds gold')
total = under = product_only = 0
kinds_right = kinds_all = 0
for row in sorted(rows, key=lambda r: r['id']):
    cites = {str(c) for c in truth[row['id']].citations}
    gold = {i for i, ids in enumerate(ids_of) if ids & cites}
    places = row['meta']['area']['places_in_the_tree']
    below = set().union(*(tree['paths'][p] for p in places if '/' in p)) if places else set()
    wide = set().union(*(tree['paths'][p.split('/')[0]] for p in places)) if places else set()
    shown = ' '.join(f'{p.count("/")}:{"gold" if tree["paths"][p] & gold else "none"}' for p in places)
    in_below, in_wide = len(gold & below), len(gold & (wide - below))
    total += len(gold)
    under += in_below
    product_only += in_wide
    for p in places:
        if '/' in p:
            kinds_all += 1
            kinds_right += bool(tree['paths'][p] & gold)
    print(f'   {len(gold):3d} | {in_below:3d} (of {len(below):3d} chunks) | {in_wide:3d} (of '
          f'{len(wide - below):3d}) | {shown}')
print(f'gold chunks {total}; under the returned places below a product {under}; under their '
      f'products only {product_only}; elsewhere {total - under - product_only}')
print(f'returned places below a product: {kinds_all}; holding gold: {kinds_right}')

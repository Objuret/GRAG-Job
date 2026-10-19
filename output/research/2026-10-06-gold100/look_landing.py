"""The names the question's own words carry, on the questions the new run answered, and where the
run's delivered chunks sit against them.

Per question: the literal whole-word landings `landing.land` reads (no nearest-name pass: every
word is passed as known), their kinds, the meet of their areas (`landing.areas`, `combine` with
drop_empty), and the share of the run's delivered chunks and of its first 50 ranked chunks inside
that meet. The product the question id names is read beside it.

Reads the run's arm_outputs.jsonl (the question text is handed to `landing.land` and never
printed; ids, meta.returned and the ranked chunk ids), eval_results.jsonl (recall_id) and the
graph. No gold file, no model call, no embedder; nothing written but this print."""
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
from artefact import landing as LAND
from graph import db


class Everything:
    def __contains__(self, item):
        return True


RUN = sys.argv[1] if len(sys.argv) > 1 else 'artefact_v4__gold100__cb72000__20261005T223320Z'
KEY = sys.argv[2] if len(sys.argv) > 2 else 'ordered_chunk_ids'
folder = ROOT / 'output/k=chars' / RUN
questions = {}
with open(folder / 'arm_outputs.jsonl', encoding='utf-8') as f:
    for line in f:
        if line.strip():
            row = json.loads(line)
            questions[row['id']] = (row['question'], row['meta']['ranking'][KEY],
                                    int(row['meta']['returned']))
recall = {}
with open(folder / 'eval_results.jsonl', encoding='utf-8') as f:
    for line in f:
        if line.strip():
            row = json.loads(line)
            if row['metric'] == 'context_recall_id' and isinstance(row['value'], (int, float)):
                recall[row['question_id']] = row['value']

driver = db._driver()
out = []
with driver.session(database='herb-eval-volmax', default_access_mode='READ') as session:
    landings = LAND.resolve_names(session)
    product_of = {r['chunk']: r['product'] for r in session.run(
        'MATCH (c:Chunk)-[:product]->(p:Product) RETURN c.chunk_id AS chunk, p.name AS product')}
    for qid in sorted(questions):
        text, order, returned = questions[qid]
        hits = LAND.land(text, list(landings), known=Everything())
        reached = LAND.areas(session, hits)
        area = LAND.combine(reached, hits, drop_empty=True)
        kinds = Counter(kind for kind, _ in (area.landings if area else {}))
        products = sorted(name for kind, name in (area.landings if area else {}) if kind == LAND.PRODUCT)
        meet = area.chunks if area and area.landings else frozenset()
        id_product = qid.split('::')[0]
        inside_meet = np.array([c in meet for c in order])
        inside_product = np.array([product_of.get(c) == id_product for c in order])
        out.append({'id': qid, 'kinds': kinds, 'products': products, 'meet': len(meet),
                    'id_product': id_product, 'landings': len(area.landings) if area else 0,
                    'dropped': len(area.dropped) if area else 0,
                    'delivered_in_meet': float(inside_meet[:returned].mean()) if meet else None,
                    'first50_in_meet': float(inside_meet[:50].mean()) if meet else None,
                    'delivered_in_product': float(inside_product[:returned].mean()),
                    'meet_in_product': (sum(product_of.get(c) == id_product for c in meet) / len(meet)
                                        if meet else None),
                    'recall': recall.get(qid)})
driver.close()

n = len(out)
print(f'run {RUN}')
print(f'questions {n}; resolved names {len(landings)} '
      f'({dict(Counter(l.kind for l in landings))})')
print()
by_count = Counter(len(o['products']) for o in out)
print('product names standing literally in the question text: '
      + ', '.join(f'{k} name(s) on {v} questions' for k, v in sorted(by_count.items())))
one = [o for o in out if len(o['products']) == 1]
print(f'   exactly one product name: {len(one)}; it is the product the question id names on '
      f'{sum(o["products"][0] == o["id_product"] for o in one)}')
some = [o for o in out if o['products']]
print(f'   at least one: {len(some)}; the id product among them on '
      f'{sum(o["id_product"] in o["products"] for o in some)}')
print('landings of each kind (questions carrying at least one): '
      + ', '.join(f'{kind} {sum(1 for o in out if o["kinds"].get(kind))}'
                  for kind in sorted({k for o in out for k in o['kinds']})))
print('landings dropped for reaching no chunk, questions:', sum(1 for o in out if o['dropped']))
with_meet = [o for o in out if o['meet']]
print(f'questions with a non-empty meet: {len(with_meet)}; no landing at all: '
      f'{sum(1 for o in out if not o["landings"])}; landings but an empty meet: '
      f'{sum(1 for o in out if o["landings"] and not o["meet"])}')
sizes = np.array([o['meet'] for o in with_meet])
print('   meet size, chunks (min / 25% / median / 75% / max): '
      + ' / '.join(str(int(x)) for x in np.percentile(sizes, [0, 25, 50, 75, 100])))
print(f'   meet wholly under the id product on {sum(o["meet_in_product"] == 1 for o in with_meet)} '
      f'of {len(with_meet)}; partly {sum(0 < o["meet_in_product"] < 1 for o in with_meet)}; '
      f'not at all {sum(o["meet_in_product"] == 0 for o in with_meet)}')
print()
share = np.array([o['delivered_in_meet'] for o in with_meet])
first = np.array([o['first50_in_meet'] for o in with_meet])
rec = np.array([o['recall'] for o in with_meet])
print(f'the run\'s delivered chunks inside the meet: mean share {share.mean():.3f}; all inside on '
      f'{int((share == 1).sum())} questions, none inside on {int((share == 0).sum())}; '
      f'first 50 ranked inside: {first.mean():.3f}')
print('   by share of delivered chunks inside the meet: band, questions, mean recall_id')
for low, high in ((0., 0.001), (0.001, 0.25), (0.25, 0.5), (0.5, 0.75), (0.75, 0.999), (0.999, 1.01)):
    mask = (share >= low) & (share < high)
    if mask.any():
        print(f'      {low:.2f}-{min(high, 1.):.2f}: {int(mask.sum()):3d} questions, recall_id {rec[mask].mean():.3f}')
rest = [o for o in out if not o['meet']]
if rest:
    print(f'questions without a meet: {len(rest)}, recall_id {np.mean([o["recall"] for o in rest]):.3f}, '
          f'delivered under the id product {np.mean([o["delivered_in_product"] for o in rest]):.3f}')

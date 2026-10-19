"""Where a question's gold sits inside its product, by the places of the graph's tree, and what a
right pick of places would deliver at the 72,000-character cut (his 2026-10-06 "i mean product
isnt the only fucking scope?").

A place is a leaf of the tree shown to him: (product, record kind) for every kind but Slack
threads, (product, Slack channel) for a Slack thread chunk (a chunk on several channels sits in
each). Gold through the harness's own mapping (citations against the record ids each chunk
delivers, `_resolve_chunk`; the cut by `_budget_contexts`). COUNTS AND MEANS ONLY: no question
text, no citation, no chunk text, no chunk id and no place name is printed.

Orders filled to the cut, each inside the set named, in the run's own saved order unless said:
  product            the named product's chunks
  gold kinds         the product's chunks of the record kinds that hold gold
  gold places        the product's chunks under the places that hold gold
  ... random         the same set in random order (mean of DRAWS shuffles)
No model call (blocked), nothing written."""
import io
import json
import os
import sys
from collections import Counter, defaultdict
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

BUDGET = 72000
DRAWS = 20
RUN = ROOT / 'output/k=chars/artefact_v4__gold100__cb72000__20261005T223320Z'

prepared = V.prepare_over_corpus(orchestrator.open_corpus(orchestrator.DEFAULT_CORPUS))
try:
    with prepared.driver.session(database=V.DATABASE, default_access_mode='READ') as session:
        product_of = {r['chunk']: r['product'] for r in session.run(
            'MATCH (c:Chunk)-[:product]->(p:Product) RETURN c.chunk_id AS chunk, p.name AS product')}
        channels_of = defaultdict(set)
        for r in session.run('MATCH (c:Chunk)-[:channel]->(ch:Channel) '
                             'RETURN c.chunk_id AS chunk, ch.id AS channel'):
            channels_of[r['chunk']].add(r['channel'])
finally:
    prepared.close()

rows_by_id = {row['chunkId']: row for row in prepared.chunk_rows}
kind_of = dict(zip(prepared.chunk_ids, prepared.chunk_kinds))
SLACK = 'slack_thread_batch'


def places(chunk):
    """The leaves of the tree the chunk sits under."""
    kind = kind_of[chunk]
    if kind == SLACK and channels_of.get(chunk):
        return {('channel', c) for c in channels_of[chunk]}
    return {('kind', kind)}


docs, resolved = {}, {}
original = A2._resolve_chunk


def cached_resolve(row, cache):
    key = row['chunkId']
    if key not in resolved:
        resolved[key] = original(row, cache)
    return resolved[key]


A2._resolve_chunk = cached_resolve
for row in prepared.chunk_rows:
    cached_resolve(row, docs)
ids_of = {cid: set(ids) for cid, (_, ids) in resolved.items()}


def delivered(order):
    _, _, context_ids, block = A2._budget_contexts([rows_by_id[c] for c in order], BUDGET, docs)
    return set(context_ids), block['kept']


saved, recorded, qtype = {}, {}, {}
for line in open(RUN / 'arm_outputs.jsonl', encoding='utf-8'):
    if line.strip():
        row = json.loads(line)
        saved[row['id']] = row['meta']['ranking']['ordered_chunk_ids']
for line in open(RUN / 'eval_results.jsonl', encoding='utf-8'):
    if line.strip():
        row = json.loads(line)
        if row['metric'] == 'context_recall_id':
            recorded[row['question_id']] = row['value']
            qtype[row['question_id']] = row['type']
truth = {q.id: q for q in QS.load_questions() if q.id in saved}

rng = np.random.default_rng(20261006)
ladder = defaultdict(list)
by_type = defaultdict(lambda: defaultdict(list))
stats = defaultdict(list)
kinds_holding = Counter()
gold_by_kind = Counter()
checks = 0
for qid in sorted(saved):
    cites = {str(c) for c in truth[qid].citations}
    product = qid.split('::')[0]
    inside = [c for c in prepared.chunk_ids if product_of.get(c) == product]
    gold = [c for c in inside if ids_of[c] & cites]
    gold_kinds = {kind_of[c] for c in gold}
    gold_places = set().union(*(places(c) for c in gold))
    all_places = set().union(*(places(c) for c in inside))
    in_kinds = [c for c in inside if kind_of[c] in gold_kinds]
    in_places = [c for c in inside if places(c) & gold_places]
    for c in gold:
        gold_by_kind[kind_of[c]] += 1
    kinds_holding[len(gold_kinds)] += 1
    top_kind = Counter(kind_of[c] for c in gold).most_common(1)[0][1] / len(gold)
    top_place = Counter(p for c in gold for p in places(c)).most_common(1)[0][1] / len(gold)
    stats['chunks in the product'].append(len(inside))
    stats['places in the product'].append(len(all_places))
    stats['gold chunks'].append(len(gold))
    stats['record kinds holding gold'].append(len(gold_kinds))
    stats['places holding gold'].append(len(gold_places))
    stats['share of the gold in its largest kind'].append(top_kind)
    stats['share of the gold in its largest place'].append(top_place)
    stats['chunks under the gold kinds'].append(len(in_kinds))
    stats['chunks under the gold places'].append(len(in_places))
    stats['gold share among the chunks under the gold places'].append(len(gold) / len(in_places))

    def recall(order):
        got, _ = delivered(order)
        return len(got & cites) / len(cites)

    order = saved[qid]
    run = recall(order)
    checks += abs(run - recorded[qid]) < 1e-9
    keep_product, keep_kinds, keep_places = set(inside), set(in_kinds), set(in_places)
    values = {
        'the run as it ran': run,
        'product, the run\'s order': recall([c for c in order if c in keep_product]),
        'gold kinds, the run\'s order': recall([c for c in order if c in keep_kinds]),
        'gold places, the run\'s order': recall([c for c in order if c in keep_places]),
        'product, random order': float(np.mean([recall(list(rng.permutation(inside)))
                                                for _ in range(DRAWS)])),
        'gold kinds, random order': float(np.mean([recall(list(rng.permutation(in_kinds)))
                                                   for _ in range(DRAWS)])),
        'gold places, random order': float(np.mean([recall(list(rng.permutation(in_places)))
                                                    for _ in range(DRAWS)])),
    }
    for name, value in values.items():
        ladder[name].append(value)
        by_type[qtype[qid]][name].append(value)

print(f'questions {len(saved)}; the run\'s recall recomputed equals the recorded one on {checks}')
print()
print('per question, min / 25% / median / 75% / max (mean):')
for name, values in stats.items():
    v = np.array(values, dtype=float)
    q = np.percentile(v, [0, 25, 50, 75, 100])
    fmt = '{:.2f}' if v.max() <= 1 else '{:.0f}'
    print(f'   {name:52s} ' + ' / '.join(fmt.format(x) for x in q) + f'   ({v.mean():.2f})')
print()
print('questions by the number of record kinds that hold their gold: '
      + ', '.join(f'{k} kind(s): {v}' for k, v in sorted(kinds_holding.items())))
few = np.array(stats['places holding gold'])
print('questions by the number of places that hold their gold: '
      + ', '.join(f'{k}: {int((few == k).sum())}' for k in sorted(set(few.tolist()))[:8])
      + (f', more: {int((few > sorted(set(few.tolist()))[7]).sum())}' if len(set(few.tolist())) > 8 else ''))
total = sum(gold_by_kind.values())
print('the gold chunks by record kind: ' + ', '.join(f'{k} {v} ({v / total:.2f})'
                                                     for k, v in gold_by_kind.most_common()))
print()
print('recall_id at the cut, mean over the questions:')
for name, values in ladder.items():
    print(f'   {name:34s} {np.mean(values):.3f}')
print()
print('the same by question type (n): ' + ' | '.join(ladder))
for kind in sorted(by_type):
    n = len(by_type[kind]['the run as it ran'])
    print(f'   {kind:9s} ({n:2d}) ' + ' | '.join(f'{np.mean(by_type[kind][name]):.3f}' for name in ladder))

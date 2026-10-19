"""Where the gold sits on each facet's scale, and what an order of the named product's chunks
could deliver at the 72,000-character cut (his 2026-10-06 "when going by this width, how IS the
actual spread of gold along this scale? say in a perfect world, what is the max potential to
float?").

Gold through the harness's own mapping: a question's citations (record ids) against the record
ids each chunk delivers (`_resolve_chunk`), the cut by `_budget_contexts` as in every run. A
chunk is a gold chunk when it delivers at least one cited record. COUNTS AND MEANS ONLY: no
question text, no citation, no chunk text and no chunk id is printed.

Per facet a chunk stands at its best edge: the largest value over its eligible edges, and that
value's class floor((the column's largest over all eligible edges - value) / the facet's width),
0 the top class - the classes the arm uses. The orders compared, each filled to the cut:
  the run          the saved order of the gold100 run (checked against its recorded recall_id)
  product first    the same saved order, the named product's chunks only
  random           the named product's chunks in random order (mean of DRAWS shuffles)
  facet, classes   by the facet's class, top first (or bottom first), random inside a class
  facet, best case by the facet's class, gold first inside a class: the most an order that goes
                   by that facet's classes first can deliver
  perfect          gold first, the chunk with most cited records per character first
No model call (blocked), nothing written."""
import io
import json
import os
import sys
import time
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
FACETS = list(V.ADJUST_FACETS)

prepared = V.prepare_over_corpus(orchestrator.open_corpus(orchestrator.DEFAULT_CORPUS))
try:
    with prepared.driver.session(database=V.DATABASE, default_access_mode='READ') as session:
        product_of = {r['chunk']: r['product'] for r in session.run(
            'MATCH (c:Chunk)-[:product]->(p:Product) RETURN c.chunk_id AS chunk, p.name AS product')}
finally:
    prepared.close()

rows_by_id = {row['chunkId']: row for row in prepared.chunk_rows}
at = {cid: i for i, cid in enumerate(prepared.chunk_ids)}
layer = prepared.walk_layer
edge_chunk = np.asarray(prepared.edge_chunk)[layer['edges']]
raw = np.asarray(layer['raw'])                      # eligible edges x (topic + four)
classes = np.asarray(layer['facet_class'])          # eligible edges x four
n = len(prepared.chunk_ids)
best_value = np.full((n, 5), -np.inf)
best_class = np.full((n, 4), 10 ** 6)
np.maximum.at(best_value, edge_chunk, raw)
np.minimum.at(best_class, edge_chunk, classes)
gaps = prepared.multikey_layer.gaps.tolist()
print('widths: ' + ', '.join(f'{f} {g}' for f, g in zip(FACETS, gaps)))
print('classes over all eligible edges, per facet (class: share of edges): '
      + ' | '.join(f + ' ' + ' '.join(f'{c}:{(classes[:, j] == c).mean():.2f}'
                                      for c in range(int(min(classes[:, j].max(), 9)) + 1))
                   for j, f in enumerate(FACETS)))

# every chunk's text length and record ids once, through the arm's own resolver
docs, resolved = {}, {}
original = A2._resolve_chunk


def cached_resolve(row, cache):
    key = row['chunkId']
    if key not in resolved:
        resolved[key] = original(row, cache)
    return resolved[key]


A2._resolve_chunk = cached_resolve
started = time.perf_counter()
for row in prepared.chunk_rows:
    cached_resolve(row, docs)
ids_of = {cid: set(ids) for cid, (_, ids) in resolved.items()}
chars_of = {cid: len(text) for cid, (text, _) in resolved.items()}
print(f'{len(resolved)} chunks resolved in {time.perf_counter() - started:.0f}s; chunks delivering no '
      f'record id: {sum(1 for v in ids_of.values() if not v)}')


def delivered(order):
    _, _, context_ids, block = A2._budget_contexts([rows_by_id[c] for c in order], BUDGET, docs)
    return set(context_ids), block['kept']


saved, recorded = {}, {}
for line in open(RUN / 'arm_outputs.jsonl', encoding='utf-8'):
    if line.strip():
        row = json.loads(line)
        saved[row['id']] = row['meta']['ranking']['ordered_chunk_ids']
for line in open(RUN / 'eval_results.jsonl', encoding='utf-8'):
    if line.strip():
        row = json.loads(line)
        if row['metric'] == 'context_recall_id':
            recorded[row['question_id']] = row['value']
truth = {q.id: q for q in QS.load_questions() if q.id in saved}
print(f'questions {len(saved)}, with citations {len(truth)}')

rng = np.random.default_rng(20261006)
ladder = defaultdict(list)
spread = {f: Counter() for f in FACETS}
spread_gold = {f: Counter() for f in FACETS}
auc = {f: [] for f in ['topic'] + FACETS}
checks = Counter()
gold_counts, gold_inside, gold_outside, cites_total, cites_reachable, cites_in_product = [], 0, 0, 0, 0, 0
kept_counts = []
for qid in sorted(saved):
    cites = {str(c) for c in truth[qid].citations}
    product = qid.split('::')[0]
    inside = [c for c in prepared.chunk_ids if product_of.get(c) == product]
    gold_all = [c for c in prepared.chunk_ids if ids_of[c] & cites]
    gold = [c for c in inside if ids_of[c] & cites]
    gold_set = set(gold)
    gold_counts.append(len(gold))
    gold_inside += len(gold)
    gold_outside += len(gold_all) - len(gold)
    cites_total += len(cites)
    cites_reachable += len(cites & set().union(*(ids_of[c] for c in prepared.chunk_ids)))
    cites_in_product += len(cites & set().union(*(ids_of[c] for c in inside))) if inside else 0

    def recall(order):
        got, kept = delivered(order)
        return len(got & cites) / len(cites), kept

    run_recall, kept = recall(saved[qid])
    kept_counts.append(kept)
    checks['run recall equals the recorded one'] += abs(run_recall - recorded[qid]) < 1e-9
    ladder['the run'].append(run_recall)
    in_product = set(inside)
    ladder['product first (the run\'s own order)'].append(
        recall([c for c in saved[qid] if c in in_product])[0])
    ladder['random order of the product'].append(float(np.mean(
        [recall(list(rng.permutation(inside)))[0] for _ in range(DRAWS)])))
    # perfect: gold first, most cited records per character first, then the rest
    left, order_gold, got = set(gold), [], set()
    while left:
        pick = max(sorted(left), key=lambda c: len((ids_of[c] & cites) - got) / max(chars_of[c], 1))
        order_gold.append(pick)
        got |= ids_of[pick] & cites
        left.discard(pick)
    ladder['perfect order'].append(recall(order_gold + [c for c in inside if c not in gold_set])[0])
    is_gold = np.array([c in gold_set for c in inside])
    idx = np.array([at[c] for c in inside])
    for j, name in enumerate(['topic'] + FACETS):
        v = best_value[idx, j]
        if is_gold.any() and (~is_gold).any():
            g, o = v[is_gold], v[~is_gold]
            auc[name].append(float(((g[:, None] > o[None, :]).sum()
                                    + .5 * (g[:, None] == o[None, :]).sum()) / (g.size * o.size)))
    ladder['topic, the chunk\'s best edge first'].append(
        recall([inside[i] for i in np.argsort(-best_value[idx, 0], kind='stable')])[0])
    for j, f in enumerate(FACETS):
        cls = best_class[idx, j]
        for c, flag in zip(cls.tolist(), is_gold.tolist()):
            spread[f][min(c, 7)] += 1
            spread_gold[f][min(c, 7)] += flag
        for label, sign in (('top class first', 1), ('bottom class first', -1)):
            runs = []
            for _ in range(DRAWS):
                shuffle = rng.permutation(len(inside))
                order = sorted(shuffle.tolist(), key=lambda i: sign * cls[i])
                runs.append(recall([inside[i] for i in order])[0])
            ladder[f'{f}, {label}, random inside a class'].append(float(np.mean(runs)))
            order = sorted(range(len(inside)), key=lambda i: (sign * cls[i], not is_gold[i],
                                                             -len(ids_of[inside[i]] & cites)
                                                             / max(chars_of[inside[i]], 1)))
            ladder[f'{f}, {label}, gold first inside a class'].append(
                recall([inside[i] for i in order])[0])

print(f'checks: {dict(checks)} of {len(saved)}')
print(f'cited records {cites_total}; delivered by some chunk of the pool {cites_reachable}; by a chunk of '
      f'the named product {cites_in_product}')
print(f'gold chunks: under the named product {gold_inside}, under another product {gold_outside}; per question '
      f'min / median / max {min(gold_counts)} / {np.median(gold_counts):.0f} / {max(gold_counts)}; '
      f'chunks that fit under the cut in the run, median {np.median(kept_counts):.0f}')
print()
print('recall_id at the cut, mean over the questions:')
for name, values in ladder.items():
    print(f'   {name:52s} {np.mean(values):.3f}')
best = np.max(np.array([ladder[f'{f}, {d}, random inside a class'] for f in FACETS
                        for d in ('top class first', 'bottom class first')]), axis=0)
print(f'   {"the best facet and direction per question, random":52s} {best.mean():.3f}')
best = np.max(np.array([ladder[f'{f}, {d}, gold first inside a class'] for f in FACETS
                        for d in ('top class first', 'bottom class first')]), axis=0)
print(f'   {"the best facet and direction per question, best case":52s} {best.mean():.3f}')
print()
print('gold against the other chunks of the product, per facet (the chunk\'s best edge): the chance that a gold '
      'chunk stands higher, mean over questions; questions above a coin')
for name, values in auc.items():
    v = np.array(values)
    print(f'   {name:14s} {v.mean():.3f}   above 0.5 on {int((v > .5).sum())} of {v.size}')
print()
print('where the product\'s chunks and its gold chunks stand, by the class of the chunk\'s best edge '
      '(class 0 the top; 7 = 7 or lower): chunks / gold chunks / gold share')
for f in FACETS:
    total, gold_total = sum(spread[f].values()), sum(spread_gold[f].values())
    print(f'   {f} (all classes: {total} / {gold_total} / {gold_total / total:.3f})')
    for c in sorted(spread[f]):
        print(f'      class {c}: {spread[f][c]:6d} / {spread_gold[f][c]:5d} / '
              f'{spread_gold[f][c] / spread[f][c]:.3f}   (of the chunks {spread[f][c] / total:.3f}, '
              f'of the gold {spread_gold[f][c] / gold_total:.3f})')

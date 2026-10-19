"""Why the same question scores differently from one querytagger answer to the next (his
2026-10-06 "the reason behind the numbers is the important part, or more, the difference").

The ten smoke questions under each saved querytagger answer (the instruction variants asked
today and last night's), run through the arm offline: no model call, the answers and the query
embeddings read from disk. `v4_walk.chain`'s own arrays are kept per question, and per signal the
chance that a gold chunk of the named product stands above another chunk of that product is
printed: D (the description against the chunk descriptions), Qs (the raw question against them),
the text term (the larger of the two), T (the tag term), S (tag + text), S' (with the lifts).
Gold through the harness's mapping. COUNTS AND MEANS ONLY: no question, description, tag,
citation, chunk text or chunk id is printed."""
import io
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

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

SOURCE = ROOT / 'output/k=chars/artefact_v4__10smoke__cb72000__20261006T172600Z'
CONFIGS = [('last night', {}),
           ('new wording', {'HERB_V4_QUERYDESC': 'looking'}),
           ('tree shown', {'HERB_V4_SCOPE': 'product'}),
           ('tree + new wording', {'HERB_V4_QUERYDESC': 'looking', 'HERB_V4_SCOPE': 'product'})]
SIGNALS = ('D', 'Qs', 'text', 'T', 'S', 'S_prime')

questions = {}
for line in open(SOURCE / 'arm_outputs.jsonl', encoding='utf-8'):
    if line.strip():
        row = json.loads(line)
        questions[row['id']] = row['question']
truth = {q.id: q for q in QS.load_questions() if q.id in questions}

prepared = V.prepare_over_corpus(orchestrator.open_corpus(orchestrator.DEFAULT_CORPUS))
held = {}
original_chain = V.WK.chain


def keeping_chain(layer, query, cos_noise, **switches):
    got = original_chain(layer, query, cos_noise, **switches)
    held['walked'] = got
    held['query'] = query
    return got


V.WK.chain = keeping_chain
docs = {}
ids_of = [set(A2._resolve_chunk(row, docs)[1]) for row in prepared.chunk_rows]
product = np.asarray(prepared.walk_layer['product'])


def auc(values, gold, pool):
    g, o = values[gold], values[pool & ~gold]
    if not g.size or not o.size:
        return float('nan')
    return float(((g[:, None] > o[None, :]).sum() + .5 * (g[:, None] == o[None, :]).sum())
                 / (g.size * o.size))


results = defaultdict(dict)
try:
    for name, env in CONFIGS:
        for key in ('HERB_V4_QUERYDESC', 'HERB_V4_SCOPE'):
            os.environ.pop(key, None)
        os.environ.update(env)
        for qid in sorted(questions):
            cites = {str(c) for c in truth[qid].citations}
            gold = np.array([bool(ids & cites) for ids in ids_of])
            pool = product == product[np.flatnonzero(gold)[0]]
            out = V.answer_one_question((qid, questions[qid]), prepared, None, 50, 72000)
            walked, query = held['walked'], held['query']
            arrays = {'D': walked['D'], 'Qs': walked['Qs'], 'text': walked['side'],
                      'T': walked['T'], 'S': walked['S'], 'S_prime': walked['S_prime']}
            got = set(out.context_ids)
            delivered = out.meta['ranking']['delivered_chunk_ids']
            index = {c: i for i, c in enumerate(prepared.chunk_ids)}
            sent = np.array([index[c] for c in delivered])
            terms = out.meta['diagnostics']['delivered_term_shares']
            winners = out.meta['ranking']['delivered_query_tags']
            n_desc = out.meta['interpreter']['description_side_tags']
            results[qid][name] = {
                'recall': len(got & cites) / len(cites),
                'auc': {s: auc(np.asarray(arrays[s], dtype=float), gold, pool) for s in SIGNALS},
                'arrays': {s: np.asarray(arrays[s], dtype=float)[pool] for s in ('D', 'T')},
                'in_product': float(pool[sent].mean()),
                'gold_delivered': int(gold[sent].sum()), 'gold': int(gold.sum()),
                'delivered': int(sent.size),
                'tag_share': terms['tags'], 'text_share': terms['description'],
                'tags': out.meta['interpreter']['query_tags'],
                'gold_carried_by_question_side_tag': int(sum(
                    1 for i, w in zip(sent.tolist(), winners) if gold[i] and w is not None
                    and w >= n_desc)),
                'T_zero_gold': int((np.asarray(walked['T'])[gold] <= 0).sum()),
            }
finally:
    V.WK.chain = original_chain
    prepared.close()

names = [name for name, _ in CONFIGS]
print('per question and answer: recall | gold delivered of gold | share of delivered under the product | '
      'the chance a gold chunk stands above another chunk of the product by D, Qs, text, tags, S, S\'')
for qid in sorted(results):
    print(f'  question {sorted(results).index(qid) + 1}')
    for name in names:
        r = results[qid][name]
        a = r['auc']
        print(f'     {name:20s} {r["recall"]:.2f} | {r["gold_delivered"]:2d} of {r["gold"]:2d} | '
              f'{r["in_product"]:.2f} | D {a["D"]:.2f}  Qs {a["Qs"]:.2f}  text {a["text"]:.2f}  '
              f'tags {a["T"]:.2f}  S {a["S"]:.2f}  S\' {a["S_prime"]:.2f}')
print()
print('mean over the ten, per answer:')
for name in names:
    rows = [results[q][name] for q in sorted(results)]
    print(f'   {name:20s} recall {np.mean([r["recall"] for r in rows]):.3f} | under the product '
          f'{np.mean([r["in_product"] for r in rows]):.2f} | '
          + '  '.join(f'{s} {np.nanmean([r["auc"][s] for r in rows]):.2f}' for s in SIGNALS)
          + f' | tag share of delivered strength {np.mean([r["tag_share"] for r in rows]):.2f}')
print()
print('between two answers for the same question (each pair of the four), over the ten questions: how alike '
      'the description ranks the product\'s chunks and how alike the tags do (rank correlation, median, min)')
pairs_d, pairs_t = [], []
for qid in results:
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = results[qid][names[i]]['arrays'], results[qid][names[j]]['arrays']
            pairs_d.append(spearmanr(a['D'], b['D'])[0])
            pairs_t.append(spearmanr(a['T'], b['T'])[0])
print(f'   description: median {np.nanmedian(pairs_d):.2f}, lowest {np.nanmin(pairs_d):.2f}; '
      f'tags: median {np.nanmedian(pairs_t):.2f}, lowest {np.nanmin(pairs_t):.2f}')
print()
flat = [(results[q][n]['recall'], results[q][n]['auc'], results[q][n]['in_product'])
        for q in results for n in names]
rec = np.array([f[0] for f in flat])
print('over the 40 question-answer pairs, the rank correlation of recall with:')
for s in SIGNALS:
    v = np.array([f[1][s] for f in flat])
    print(f'   how well {s:8s} puts gold above the rest: {spearmanr(rec, v)[0]:+.2f}')
print(f'   the share of delivered chunks under the product: '
      f'{spearmanr(rec, np.array([f[2] for f in flat]))[0]:+.2f}')
swing = []
for qid in sorted(results):
    recalls = [results[qid][n]['recall'] for n in names]
    swing.append((max(recalls) - min(recalls), qid))
print()
print('the questions by how far their recall moves between the four answers (largest first), with what moves '
      'most with it:')
for spread, qid in sorted(swing, reverse=True):
    rows = [results[qid][n] for n in names]
    r = np.array([x['recall'] for x in rows])
    parts = []
    for s in ('D', 'Qs', 'T'):
        v = np.array([x['auc'][s] for x in rows])
        parts.append(f'{s} {v.min():.2f}-{v.max():.2f}')
    inside = np.array([x['in_product'] for x in rows])
    print(f'   question {sorted(results).index(qid) + 1}: recall {r.min():.2f}-{r.max():.2f} | '
          + ', '.join(parts) + f' | under the product {inside.min():.2f}-{inside.max():.2f}')

"""Does the arm's result depend on the order in which the tag-to-chunk edges are listed? The arm
takes that order from the rows of the facet value file. Here the same edges are handed to it
sorted by (chunk id, tag) and the 99 saved questions of the gold100 run are retrieved again,
offline: no model call (the querytagger answers and the query embeddings are read from disk),
nothing written. Compared with the saved run: the full order of 4,808 chunks and the delivered
context ids, per question. The question text goes from the saved row to the arm and is never
printed. No gold file is opened."""
import io
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
os.environ['HERB_V4_OFFLINE'] = 'on'
ROOT = Path('C:/Coding/exjobbet/GRAG-Job')
sys.path[:0] = [str(ROOT / 'prod'), str(ROOT / 'test')]
from harness import chat, orchestrator


def _blocked(*args, **kwargs):
    raise RuntimeError('model call blocked: this check makes none')


chat.post = _blocked
import arms.artefact_v4 as V

MODE = sys.argv[1] if len(sys.argv) > 1 else 'sorted'
original = V.L.load


def sorted_load(directory):
    learned = original(directory)
    order = sorted(range(len(learned.endpoints)),
                   key=lambda i: (learned.endpoints[i][1], learned.endpoints[i][0]))
    endpoints = tuple(learned.endpoints[i] for i in order)
    values = np.ascontiguousarray(learned.raw_scores[order])
    moved = sum(1 for a, b in zip(endpoints, learned.endpoints) if a != b)
    print(f'edges {len(endpoints)}; in another place than in the file: {moved}', flush=True)
    return V.L.LearnedEdges(endpoints, values, learned.source_sha256, learned.overlay_sha256)


if MODE == 'sorted':
    V.L.load = sorted_load
RUN = ROOT / 'output/k=chars/artefact_v4__gold100__cb72000__20261005T223320Z'
rows = [json.loads(line) for line in open(RUN / 'arm_outputs.jsonl', encoding='utf-8') if line.strip()]
prepared = V.prepare_over_corpus(orchestrator.open_corpus(orchestrator.DEFAULT_CORPUS))
same_order = same_contexts = same_set = 0
first_difference, differing = [], []
started = time.perf_counter()
try:
    for n, row in enumerate(rows, 1):
        out = V.answer_one_question((row['id'], row['question']), prepared, None, 50, 72000)
        new_order = out.meta['ranking']['ordered_chunk_ids']
        old_order = row['meta']['ranking']['ordered_chunk_ids']
        if new_order == old_order:
            same_order += 1
        else:
            at = next(i for i, (a, b) in enumerate(zip(new_order, old_order)) if a != b)
            first_difference.append(at)
            differing.append((row['id'], at, sum(a != b for a, b in zip(new_order, old_order))))
        same_contexts += list(out.context_ids) == list(row['context_ids'])
        same_set += set(out.context_ids) == set(row['context_ids'])
        if n % 10 == 0:
            print(f'{n} of {len(rows)} done, {time.perf_counter() - started:.0f}s; full order identical on '
                  f'{same_order}, delivered ids identical on {same_contexts}', flush=True)
finally:
    prepared.close()
print(f'mode {MODE}: questions {len(rows)}; full order of 4,808 identical on {same_order}; delivered context ids '
      f'identical (and in the same order) on {same_contexts}; the same set on {same_set}')
if differing:
    print('where the full order differs: question, first differing place, places that differ')
    for qid, at, count in differing:
        print(f'   {qid}: first at place {at}, {count} places')

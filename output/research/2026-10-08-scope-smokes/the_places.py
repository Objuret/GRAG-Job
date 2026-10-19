"""The smoke runs of 2026-10-08 that gauge the scope from one source each (product level, the
clustering picks the groups), beside the references, read from their own folders: each run's
switches, its two retrieval stats, the products and chunks kept, on how many questions the kept
products hold the product the second call returned, and question by question whether its recall
is above or below the run with no scope step. Reads `run_manifest.json`, `eval_results.jsonl`
(metric values only) and each row's `meta`; no question text, no gold. Run from the repo root."""
import collections
import json
import pathlib
import statistics
import sys

sys.stdout.reconfigure(encoding='utf-8')
BASE = pathlib.Path('output/k=chars')
RUNS = [('the arm as it is (second call\'s product first)', '20261007T224247Z'),
        ('no scope step', '20261007T225424Z'),
        ('the arm\'s description number (the better of description and question)',
         '20261007T232309Z'),
        ('chunk_desc alone (query description against chunk descriptions)', '20261007T234422Z'),
        ('the question alone (question against chunk descriptions)', '20261007T234513Z'),
        ('the arm\'s tags\' number', '20261007T232451Z'),
        ('hits (chunks of the picked tags, counted)', '20261007T234605Z'),
        ('topic (the topic value on the picked tags\' links)', '20261007T234655Z'),
        ('querytags against the chunk descriptions (average)', '20261007T234744Z'),
        ('chunk_desc and hits', '20261007T234835Z'),
        ('the arm\'s description number and hits', '20261007T235303Z')]


def folder(stamp):
    return BASE / f'artefact_v4__10smoke__cb72000__{stamp}'


def read(stamp):
    metas = {}
    for line in (folder(stamp) / 'arm_outputs.jsonl').read_text(encoding='utf-8').splitlines():
        if line.strip():
            row = json.loads(line)
            meta = row.get('meta') or (row.get('output') or {}).get('meta') or {}
            metas[row.get('question_id') or row.get('qid') or row.get('id')] = meta
    values = collections.defaultdict(dict)
    for line in (folder(stamp) / 'eval_results.jsonl').read_text(encoding='utf-8').splitlines():
        if line.strip():
            cell = json.loads(line)
            if isinstance(cell.get('value'), (int, float)):
                values[cell['metric']][cell['question_id']] = float(cell['value'])
    flags = json.loads((folder(stamp) / 'run_manifest.json').read_text(encoding='utf-8'))['flags']
    return metas, values, flags


data = {name: read(stamp) for name, stamp in RUNS}
call = {q: {p.split('/')[0] for p in m['scope']['places_in_the_tree']}
        for q, m in data[RUNS[0][0]][0].items()}
off = data[RUNS[1][0]][1]['context_recall_id']
for name, stamp in RUNS:
    metas, values, flags = data[name]
    recall, precision = values['context_recall_id'], values['context_precision_id']
    line = (f'{name}\n  {stamp}; flags {flags}\n  context_recall_id '
            f'{statistics.mean(recall.values()):.3f}, context_precision_id '
            f'{statistics.mean(precision.values()):.3f} over {len(recall)}')
    clouded = {q: m for q, m in metas.items() if 'clouds' in m['scope']}
    if clouded:
        kept = [m['scope']['chunks_kept'] for m in clouded.values()]
        products = {q: {p for place in m['scope']['clouds'].values()
                        for p in place['product']['kept']} for q, m in clouded.items()}
        holds = sum(call[q] <= products[q] for q in call)
        hit_chunks = [sum(1 for _ in ())]  # placeholder, replaced below when hits were gauged
        line += (f'; products kept {sorted(len(p) for p in products.values())}; chunks kept '
                 f'{min(kept)}-{max(kept)}, middle {int(statistics.median(kept))}; the kept '
                 f'products hold the second call\'s product on {holds} of {len(call)} questions')
    up = sum(recall[q] > off[q] + 1e-12 for q in off)
    down = sum(recall[q] < off[q] - 1e-12 for q in off)
    print(line + f'\n  recall against no scope step, question by question: {up} above, {down} '
                 f'below, {len(off) - up - down} same')

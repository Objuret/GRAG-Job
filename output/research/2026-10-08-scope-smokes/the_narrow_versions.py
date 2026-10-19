"""The eight narrow smoke runs of 2026-10-08 (the gauge at the product level only) beside the
two references, read from their own folders: each run's switches, its two retrieval stats, the
chunks kept, and question by question whether its recall is above, below or the same as with no
scope step and as the arm as it is. Reads `run_manifest.json`, `eval_results.jsonl` (metric
values only) and each row's `meta`; no question text, no gold. Run from the repo root."""
import collections
import json
import pathlib
import statistics
import sys

sys.stdout.reconfigure(encoding='utf-8')
BASE = pathlib.Path('output/k=chars')
RUNS = [('the arm as it is (second call\'s product first)', '20261007T224247Z'),
        ('no scope step', '20261007T225424Z'),
        ('description alone, middle off and spread', '20261007T232309Z'),
        ('description alone, as they are', '20261007T232359Z'),
        ('tags alone, middle off and spread', '20261007T232451Z'),
        ('both places, middle off and spread', '20261007T232539Z'),
        ('both places, as they are', '20261007T232629Z'),
        ('both places, smallest to 0 largest to 1', '20261007T232722Z'),
        ('both places, by order', '20261007T232815Z'),
        ('both places, middle off and spread, two groups', '20261007T232901Z')]


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
as_it_is, off = data[RUNS[0][0]], data[RUNS[1][0]]


def against(values, other):
    mine, theirs = values['context_recall_id'], other[1]['context_recall_id']
    up = sum(mine[q] > theirs[q] + 1e-12 for q in theirs)
    down = sum(mine[q] < theirs[q] - 1e-12 for q in theirs)
    return f'{up} above, {down} below, {len(theirs) - up - down} same'


for name, stamp in RUNS:
    metas, values, flags = data[name]
    recall, precision = values['context_recall_id'], values['context_precision_id']
    kept = [m['scope']['chunks_kept'] for m in metas.values() if 'chunks_kept' in m['scope']]
    products = [sorted({p for place in m['scope']['clouds'].values()
                        for p in place['product']['kept']})
                for m in metas.values() if 'clouds' in m['scope']]
    same_as_call = sum(m['ranking']['delivered_chunk_ids']
                       == as_it_is[0][q]['ranking']['delivered_chunk_ids']
                       for q, m in metas.items())
    print(f'{name}\n  {stamp}; flags {flags}\n  context_recall_id '
          f'{statistics.mean(recall.values()):.3f}, context_precision_id '
          f'{statistics.mean(precision.values()):.3f} over {len(recall)}'
          + (f'; chunks kept {min(kept)}-{max(kept)}, middle {int(statistics.median(kept))}; '
             f'products kept {sorted(len(p) for p in products)}' if kept else '')
          + f'\n  recall question by question: against no scope step {against(values, off)}; '
            f'against the arm as it is {against(values, as_it_is)}; questions with exactly the '
            f'arm-as-it-is delivered chunks {same_as_call} of {len(metas)}')

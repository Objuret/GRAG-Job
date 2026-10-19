"""The seven smoke runs of 2026-10-08 of his idea (scope step `levels`: the clustering decides
what is hit, clouds of relevancy by scope, the largest kept with the minorities of the same
parent), beside the two references, read from their own folders: each run's switches, its two
retrieval stats, per place the chunks hit, the clouds, the largest clouds and the minorities,
the chunks kept, the questions that did not fill the budget, and question by question whether
its recall is above or below the run with no scope step. Reads `run_manifest.json`,
`eval_results.jsonl` (metric values only) and each row's `meta`; no question text, no gold. Run
from the repo root."""
import collections
import json
import pathlib
import statistics
import sys

sys.stdout.reconfigure(encoding='utf-8')
BASE = pathlib.Path('output/k=chars')
RUNS = [('the arm as it is (second call\'s product first)', '20261007T224247Z'),
        ('no scope step', '20261007T225424Z'),
        ('tags, the nearest level', '20261008T012229Z'),
        ('tags, the two nearest levels', '20261008T012319Z'),
        ('tags, all levels', '20261008T012409Z'),
        ('chunk_desc, all levels', '20261008T012459Z'),
        ('the question, all levels', '20261008T012551Z'),
        ('tags and chunk_desc, the nearest level', '20261008T012640Z'),
        ('tags and chunk_desc, all levels', '20261008T012733Z')]


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
    manifest = json.loads((folder(stamp) / 'run_manifest.json').read_text(encoding='utf-8'))
    return metas, values, manifest


def span(numbers):
    return f'{min(numbers)}-{max(numbers)} (middle {int(statistics.median(numbers))})'


data = {name: read(stamp) for name, stamp in RUNS}
off = data[RUNS[1][0]][1]['context_recall_id']
for name, stamp in RUNS:
    metas, values, manifest = data[name]
    recall, precision = values['context_recall_id'], values['context_precision_id']
    up = sum(recall[q] > off[q] + 1e-12 for q in off)
    down = sum(recall[q] < off[q] - 1e-12 for q in off)
    print(f'{name}\n  {stamp}; flags {manifest.get("flags")}\n  context_recall_id '
          f'{statistics.mean(recall.values()):.3f}, context_precision_id '
          f'{statistics.mean(precision.values()):.3f} over {len(recall)}; did not fill the '
          f'budget {manifest.get("n_exhausted")}; against no scope step {up} above, {down} '
          f'below, {len(off) - up - down} same')
    scopes = [m['scope'] for m in metas.values() if 'gauged' in m['scope']]
    if not scopes:
        continue
    print(f'  chunks kept a question {span([s["chunks_kept"] for s in scopes])}')
    for place in scopes[0]['places']:
        gauged = [s['gauged'][place] for s in scopes]
        kinds = collections.Counter(('channel' if c['scope'].count('/') == 2 else 'kind of record')
                                    for g in gauged for c in g['largest'])
        products = [len({c['scope'].split('/')[0] for c in g['largest']}) for g in gauged]
        print(f'  {place}: chunks hit {span([g["hit_chunks"] for g in gauged])}; clouds '
              f'{span([g["clouds"] for g in gauged])}; largest clouds '
              f'{span([len(g["largest"]) for g in gauged])}, of them {dict(kinds)}, under '
              f'{span(products)} products; minorities kept '
              f'{span([len(g["minorities"]) for g in gauged])}')

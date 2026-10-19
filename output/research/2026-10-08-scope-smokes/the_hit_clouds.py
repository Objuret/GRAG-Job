"""The seven smoke runs of 2026-10-08 with the scope gauged from hit chunks (`scan_clouds`:
each stage's hits are the chunks it alone would deliver inside the 72,000 characters; the tree
scan over every place), beside the two references, read from their own folders: each run's
switches, its two retrieval stats, the hits, the questions with a cloud, the clouds by level of
the tree, the minorities, the chunks kept, the questions that did not fill the budget, and
question by question whether its recall is above or below the run with no scope step. Reads
`run_manifest.json`, `eval_results.jsonl` (metric values only) and each row's `meta`; no
question text, no gold. Run from the repo root."""
import collections
import json
import pathlib
import statistics
import sys

sys.stdout.reconfigure(encoding='utf-8')
BASE = pathlib.Path('output/k=chars')
RUNS = [('the arm as it is (second call\'s product first)', '20261007T224247Z'),
        ('no scope step', '20261007T225424Z'),
        ('hits of the arm\'s own order', '20261008T003210Z'),
        ('hits of chunk_desc', '20261008T003436Z'),
        ('hits of the tags\' number', '20261008T003526Z'),
        ('hits of the question', '20261008T003617Z'),
        ('hits of topic', '20261008T003708Z'),
        ('the chunks of the picked tags, uncut', '20261008T003759Z'),
        ('hits of the tags\' number and of chunk_desc', '20261008T003848Z')]
LEVELS = ('product', 'kind of record', 'channel')


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


data = {name: read(stamp) for name, stamp in RUNS}
off = data[RUNS[1][0]][1]['context_recall_id']
for name, stamp in RUNS:
    metas, values, manifest = data[name]
    recall, precision = values['context_recall_id'], values['context_precision_id']
    line = (f'{name}\n  {stamp}; flags {manifest.get("flags")}\n  context_recall_id '
            f'{statistics.mean(recall.values()):.3f}, context_precision_id '
            f'{statistics.mean(precision.values()):.3f} over {len(recall)}; did not fill the '
            f'budget {manifest.get("n_exhausted")}')
    scans = [m['scope'] for m in metas.values() if 'clouds' in m['scope']
             and isinstance(m['scope']['clouds'], list)]
    if scans:
        with_cloud = [s for s in scans if s['clouds']]
        levels = collections.Counter(LEVELS[c['place'].count('/')]
                                     for s in scans for c in s['clouds'])
        line += (f'\n  hits a question {sorted(s["hits"] for s in scans)}; questions with a '
                 f'cloud {len(with_cloud)} of {len(scans)}; clouds a question '
                 f'{sorted(len(s["clouds"]) for s in scans)}; clouds by level '
                 f'{ {level: levels.get(level, 0) for level in LEVELS} }; minorities kept '
                 f'{sum(len(s["minorities"]) for s in scans)}; chunks kept where there is a '
                 f'cloud {sorted(s["chunks_kept"] for s in with_cloud)}; the largest ratio of '
                 f'the scatters {min(s["largest_scatter_ratio"] for s in scans):.1f}-'
                 f'{max(s["largest_scatter_ratio"] for s in scans):.1f}')
    up = sum(recall[q] > off[q] + 1e-12 for q in off)
    down = sum(recall[q] < off[q] - 1e-12 for q in off)
    print(line + f'\n  recall against no scope step, question by question: {up} above, {down} '
                 f'below, {len(off) - up - down} same')

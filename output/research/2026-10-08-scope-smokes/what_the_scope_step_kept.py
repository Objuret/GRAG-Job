"""The six smoke runs of 2026-10-08 (the ten, retrieval only, no model call) read from their own
folders: each run's switches and two retrieval stats, how many of the chunks delivered with no
scope step each version changed, where in the order the clustered step first cuts, what the
clustering kept per place and level, and whether the products it kept are the product the
second call returned. Reads `run_manifest.json`, `eval_results.jsonl` (metric values only) and
each row's `meta` in `arm_outputs.jsonl`; no question text, no gold. Run from the repo root."""
import collections
import json
import pathlib
import statistics
import sys

sys.stdout.reconfigure(encoding='utf-8')
BASE = pathlib.Path('output/k=chars')
RUNS = [('the arm as it is', '20261007T224247Z'), ('no scope step', '20261007T225424Z'),
        ('clouds, as they are', '20261007T225915Z'),
        ('clouds, middle off and spread', '20261007T225430Z'),
        ('clouds, smallest to 0 largest to 1', '20261007T230211Z'),
        ('clouds, by order', '20261007T230417Z')]
LEVELS = ('product', 'kind of record', 'channel')


def folder(stamp):
    return BASE / f'artefact_v4__10smoke__cb72000__{stamp}'


def rows(stamp):
    out = {}
    for line in (folder(stamp) / 'arm_outputs.jsonl').read_text(encoding='utf-8').splitlines():
        if line.strip():
            row = json.loads(line)
            meta = row.get('meta') or (row.get('output') or {}).get('meta') or {}
            out[row.get('question_id') or row.get('qid') or row.get('id')] = meta
    return out


metas = {name: rows(stamp) for name, stamp in RUNS}
print('== the runs ==')
for name, stamp in RUNS:
    manifest = json.loads((folder(stamp) / 'run_manifest.json').read_text(encoding='utf-8'))
    values = collections.defaultdict(list)
    for line in (folder(stamp) / 'eval_results.jsonl').read_text(encoding='utf-8').splitlines():
        if line.strip():
            cell = json.loads(line)
            if isinstance(cell.get('value'), (int, float)):
                values[cell['metric']].append(float(cell['value']))
    delivered = [len(m['ranking']['delivered_chunk_ids']) for m in metas[name].values()]
    kept = [m['scope']['chunks_kept'] for m in metas[name].values() if 'chunks_kept' in m['scope']]
    print(f'{name}: {stamp}; flags {manifest.get("flags")}; context_recall_id '
          f'{statistics.mean(values["context_recall_id"]):.3f}, context_precision_id '
          f'{statistics.mean(values["context_precision_id"]):.3f} over '
          f'{len(values["context_recall_id"])}; delivered a question {min(delivered)}-'
          f'{max(delivered)}' + (f'; kept {min(kept)}-{max(kept)}, middle '
                                 f'{int(statistics.median(kept))}' if kept else ''))

print('\n== against the run with no scope step ==')
off = metas['no scope step']
total = sum(len(m['ranking']['delivered_chunk_ids']) for m in off.values())
print(f'no scope step delivers {total} chunks over the ten questions')
for name, _ in RUNS:
    if name == 'no scope step':
        continue
    same = sum(metas[name][q]['ranking']['delivered_chunk_ids']
               == off[q]['ranking']['delivered_chunk_ids'] for q in off)
    gone, first_cut = 0, []
    for q, meta in off.items():
        mine = metas[name][q]['ranking']
        gone += len(set(meta['ranking']['delivered_chunk_ids']) - set(mine['delivered_chunk_ids']))
        if name != 'the arm as it is':
            kept = set(mine['ordered_chunk_ids'])
            first_cut.append(next((i + 1 for i, c in enumerate(meta['ranking']['ordered_chunk_ids'])
                                   if c not in kept), None))
    print(f'{name}: of those {total}, not delivered here {gone}; questions with exactly the same '
          f'delivered chunks {same} of {len(off)}'
          + (f'; position in the order of the first chunk cut, per question {sorted(first_cut)}'
             if first_cut else ''))

print('\n== what the clustering kept, per place and level (sorted over the ten questions) ==')
for name, _ in RUNS[2:]:
    print(name)
    for place in ('tags', 'description'):
        for level in LEVELS:
            cells = [m['scope']['clouds'][place][level] for m in metas[name].values()]
            print(f'  {place:11s} {level:15s} scopes kept {sorted(len(c["kept"]) for c in cells)}; '
                  f'chunks under them {sorted(c["chunks"] for c in cells)}; groups '
                  f'{sorted(c["groups"] for c in cells)}')
    kinds = collections.Counter(path.split('/')[1] for m in metas[name].values()
                                for path in m['scope']['clouds']['tags']['kind of record']['kept'])
    print(f'  tags, kind of record: the kept scopes over the ten questions by kind {dict(kinds)}')

print('\n== the products the clustering kept against the product the second call returned ==')
call = {q: {p.split('/')[0] for p in m['scope']['places_in_the_tree']}
        for q, m in metas['the arm as it is'].items()}
print('products the second call returned, per question:', sorted(len(v) for v in call.values()))
for name, _ in RUNS[2:]:
    for place in ('tags', 'description'):
        kept = {q: set(m['scope']['clouds'][place]['product']['kept'])
                for q, m in metas[name].items()}
        same = sum(kept[q] == call[q] for q in call)
        holds = sum(call[q] <= kept[q] for q in call)
        none = sum(not (call[q] & kept[q]) for q in call)
        print(f'{name:36s} {place:11s} products kept {sorted(len(v) for v in kept.values())}; '
              f'exactly the second call\'s {same} of 10; holds it among others {holds - same}; '
              f'shares none with it {none}')

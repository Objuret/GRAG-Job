"""What the per-tag facets do: the run with them against the control on the same first-call answers
with the facets' weights zero (run_without_facets.py), and both against the run before the first
call changed. Ids and counts only, no question text.

    .venv/Scripts/python.exe output/research/2026-10-19-facets-per-tag/compare.py <before> <with> <without>
"""
import json
import sys
from collections import Counter
from pathlib import Path

K = Path(__file__).resolve().parents[2] / 'k=chars'


def rows(folder):
    out = {}
    for line in (K / folder / 'arm_outputs.jsonl').read_text(encoding='utf-8').splitlines():
        if line.strip():
            r = json.loads(line)
            out[r['id']] = r
    return out


def recall(folder):
    vals = {}
    for line in (K / folder / 'eval_results.jsonl').read_text(encoding='utf-8').splitlines():
        r = json.loads(line)
        if r['metric'] == 'context_recall_id' and r['status'] == 'ok':
            vals[r['question_id']] = r['value']
    return sum(vals.values()) / len(vals), len(vals)


before, with_, without = (rows(f) for f in sys.argv[1:4])
tags = weighted = changed_chunks = 0
q_weighted = q_changed = 0
named = Counter()
for r in with_.values():
    f = r['meta']['scope']['facets']
    tags += len(f['per_query_tag'])
    weighted += f['query_tags_with_a_weight']
    q_weighted += f['query_tags_with_a_weight'] > 0
    changed_chunks += f['chunks_whose_nearness_changed']
    q_changed += f['chunks_whose_nearness_changed'] > 0
    named.update((t['facet'], t['matters']) for t in f['per_query_tag'])
print(f'query tags {tags}; with a facet that weighs {weighted}; questions with one {q_weighted}')
print('named facet and whether it matters:', {f'{k[0]} {k[1]}': v for k, v in sorted(named.items())})
print(f'chunks whose nearness the facets changed {changed_chunks}, on {q_changed} questions')
control = sum(r['meta']['scope']['facets']['chunks_whose_nearness_changed'] for r in without.values())
print(f'in the control, chunks whose nearness changed: {control}')


def differ(a, b, key):
    return sum(1 for q in a if key(a[q]) != key(b[q]))


order = lambda r: r['meta']['ranking']['ordered_chunk_ids']        # noqa: E731
handed = lambda r: r['context_ids']                                  # noqa: E731
print(f'with against without the facets: order differs on {differ(with_, without, order)} '
      f'questions, what is handed over on {differ(with_, without, handed)}')
print(f'without the facets against before the first call changed: order differs on '
      f'{differ(without, before, order)}, what is handed over on {differ(without, before, handed)}')
for name, folder in zip(('before', 'with the facets', 'without the facets'), sys.argv[1:4]):
    mean, n = recall(folder)
    print(f'context_recall_id {name}: {mean:.4f} over {n}')

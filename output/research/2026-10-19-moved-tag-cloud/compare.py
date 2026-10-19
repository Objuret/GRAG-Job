"""The moved tag cloud, with the odds and with one step per neighbour, against the control with the
facets off. Ids and counts only, no question text.

    .venv/Scripts/python.exe output/research/2026-10-19-moved-tag-cloud/compare.py <prefix>
    (the folders <prefix>_moved_cloud_odds, _step, _none under output/k=chars)
"""
import json
import statistics
import sys
from pathlib import Path

K = Path(__file__).resolve().parents[2] / 'k=chars'


def rows(folder):
    return {r['id']: r for r in (json.loads(l) for l in
                                 (K / folder / 'arm_outputs.jsonl').read_text(encoding='utf-8').splitlines()
                                 if l.strip())}


def recall(folder):
    vals = [json.loads(l) for l in (K / folder / 'eval_results.jsonl').read_text(encoding='utf-8').splitlines()]
    vals = [r['value'] for r in vals if r['metric'] == 'context_recall_id' and r['status'] == 'ok']
    return sum(vals) / len(vals)


def side(folder):
    return [json.loads(l) for l in (K / folder / 'moved.jsonl').read_text(encoding='utf-8').splitlines()
            if l.strip()]


prefix = sys.argv[1]
none = rows(f'{prefix}_moved_cloud_none')
chosen = lambda r: set(r['meta']['scope']['storyline']['chosen_chunk_ids'])      # noqa: E731
delivered = lambda r: set(r['meta']['ranking']['delivered_chunk_ids'])           # noqa: E731
print(f'control (facets off): context_recall_id {recall(f"{prefix}_moved_cloud_none"):.4f}')
for form in ('odds', 'step'):
    folder = f'{prefix}_moved_cloud_{form}'
    a = rows(folder)
    rec = side(folder)
    changed = sum(r['tag_cloud_changed'] for r in rec)
    cloud = sum(r['tag_cloud'] for r in rec)
    print(f'{form}: tag cloud chunks the facets swapped {changed} of {cloud}; questions whose chosen '
          f'chunks differ {sum(chosen(a[q]) != chosen(none[q]) for q in a)}; delivered set the same on '
          f'{sum(delivered(a[q]) == delivered(none[q]) for q in a)}; '
          f'{sum(len(delivered(a[q]) ^ delivered(none[q])) // 2 for q in a)} chunks swapped across the cut; '
          f'context_recall_id {recall(folder):.4f}')

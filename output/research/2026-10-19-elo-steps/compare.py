"""The facets as Elo surprises against the same with the facets off. Ids and counts only.

    .venv/Scripts/python.exe output/research/2026-10-19-elo-steps/compare.py <prefix>
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
    return [json.loads(l) for l in (K / folder / 'elo.jsonl').read_text(encoding='utf-8').splitlines()
            if l.strip()]


prefix = sys.argv[1]
on, off = f'{prefix}_elo_steps', f'{prefix}_elo_steps_none'
a, b = rows(on), rows(off)
rec = side(on)
chosen = lambda r: set(r['meta']['scope']['storyline']['chosen_chunk_ids'])      # noqa: E731
delivered = lambda r: set(r['meta']['ranking']['delivered_chunk_ids'])           # noqa: E731
print(f"items {sum(r['items'] for r in rec)}, moved {sum(r['items_moved'] for r in rec)}; largest move "
      f"median {statistics.median(r['largest_move'] for r in rec):.1f}, max {max(r['largest_move'] for r in rec):.1f}")
print(f"tag-cloud chunks changed {sum(r['tag_cloud_changed'] for r in rec)} of {sum(r['tag_cloud'] for r in rec)}; "
      f"chosen chunks differ on {sum(chosen(a[q]) != chosen(b[q]) for q in a)}; delivered set the same on "
      f"{sum(delivered(a[q]) == delivered(b[q]) for q in a)}; "
      f"{sum(len(delivered(a[q]) ^ delivered(b[q])) // 2 for q in a)} chunks swapped across the cut")
print(f'context_recall_id: facets on {recall(on):.4f}, off {recall(off):.4f}')

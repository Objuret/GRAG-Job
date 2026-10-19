"""The similarity as a likeliness with the facet as odds on it, against the same with the facets
off, in each placement. Ids and counts only, no question text.

    .venv/Scripts/python.exe output/research/2026-10-19-facet-likeliness/compare.py <prefix>
    (the folders <prefix>_likeliness_slot, _slot_none, _above, _above_none under output/k=chars)
"""
import json
import statistics
import sys
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
    return sum(vals.values()) / len(vals)


def side(folder):
    out = []
    for line in (K / folder / 'likeliness.jsonl').read_text(encoding='utf-8').splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


prefix = sys.argv[1]
for mode in ('slot', 'above'):
    on, off = f'{prefix}_likeliness_{mode}', f'{prefix}_likeliness_{mode}_none'
    a, b = rows(on), rows(off)
    delivered = lambda r: r['meta']['ranking']['delivered_chunk_ids']      # noqa: E731
    same_set = sum(set(delivered(a[q])) == set(delivered(b[q])) for q in a)
    swapped = sum(len(set(delivered(a[q])) ^ set(delivered(b[q]))) // 2 for q in a)
    order = sum(a[q]['meta']['ranking']['ordered_chunk_ids'] != b[q]['meta']['ranking']['ordered_chunk_ids']
                for q in a)
    rec = side(on)
    like = [r['log_likeliness_iqr'] for r in rec if r['log_likeliness_iqr'] is not None]
    odds = [r['facet_log_odds_iqr'] for r in rec if r['facet_log_odds_iqr'] is not None]
    changed = sum(r['changed'] for r in rec)
    border = sum(r['border'] for r in rec)
    print(f'{mode}: facets on against off: order differs on {order} questions; delivered set the '
          f'same on {same_set}; {swapped} chunks swapped across the cut')
    print(f'   chunks whose place the facets changed: {changed} of {border}; middle spread over a '
          f'border: log-likeliness {statistics.median(like):.3f}, facet log-odds {statistics.median(odds):.3f}')
    print(f'   context_recall_id: facets on {recall(on):.4f}, off {recall(off):.4f}')

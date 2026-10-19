"""The facets as ranks against ranks, against the facet nudge and against no facets, on the same
first-call answers. Ids and counts only, no question text.

    .venv/Scripts/python.exe output/research/2026-10-19-facet-ranks/compare.py <ranks> <nudge> <none>
"""
import json
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
    return sum(vals.values()) / len(vals), len(vals)


ranks, nudge, none = (rows(f) for f in sys.argv[1:4])
changed = sum(r['meta']['scope']['facets']['chunks_whose_place_changed'] for r in ranks.values())
with_facet = sum(r['meta']['scope']['facets']['query_tags_with_a_facet'] for r in ranks.values())
print(f'query tags with a facet that ranks: {with_facet}; chunks whose place the facets changed: '
      f'{changed}, on {sum(1 for r in ranks.values() if r["meta"]["scope"]["facets"]["chunks_whose_place_changed"])} questions')
order = lambda r: r['meta']['ranking']['ordered_chunk_ids']        # noqa: E731
handed = lambda r: r['context_ids']                                  # noqa: E731
chosen = lambda r: r['meta']['scope']['storyline']['chosen_chunk_ids']   # noqa: E731
for name, other in (('the nudge', nudge), ('no facets', none)):
    print(f'ranks against {name}: order differs on {sum(order(ranks[q]) != order(other[q]) for q in ranks)}, '
          f'what is handed over on {sum(handed(ranks[q]) != handed(other[q]) for q in ranks)}, '
          f'the chosen chunks on {sum(chosen(ranks[q]) != chosen(other[q]) for q in ranks)} of {len(ranks)}')
for name, folder in zip(('ranks', 'nudge', 'no facets'), sys.argv[1:4]):
    mean, n = recall(folder)
    print(f'context_recall_id {name}: {mean:.4f} over {n}')

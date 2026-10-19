"""Does the arm hand over the same thing with the graph's people read through the person-to-chunk edges
(`test/graph/build_person_edges.py`) as it did with the person-to-channel and person-to-product edges?
Two run folders of the hundred, retrieval only; ids only, no question text read.

    .venv/Scripts/python.exe output/research/2026-10-17-person-edges/same_hand_over.py <run before> <run after>
"""
import json
import statistics
import sys
from pathlib import Path


def rows(folder):
    out = {}
    for line in (Path(folder) / 'arm_outputs.jsonl').read_text(encoding='utf-8').splitlines():
        if line.strip():
            r = json.loads(line)
            out[r['id']] = (tuple(r['context_ids']), tuple(r['meta']['ranking']['delivered_chunk_ids']),
                            json.dumps(r['meta']['handed_over'], sort_keys=True))
    return out


def recall(folder):
    vals = [json.loads(l)['value'] for l in (Path(folder) / 'eval_results.jsonl').read_text(encoding='utf-8').splitlines()
            if l.strip() and json.loads(l)['metric'] == 'context_recall_id']
    return statistics.mean(vals), len(vals)


before, after = rows(sys.argv[1]), rows(sys.argv[2])
shared = sorted(set(before) & set(after))
print(f'questions in both runs: {len(shared)} (before {len(before)}, after {len(after)})')
print(f'same delivered records: {sum(before[q][0] == after[q][0] for q in shared)}')
print(f'same delivered chunks in the same order: {sum(before[q][1] == after[q][1] for q in shared)}')
print(f'same hand-over record (people, channels apart, what was left out): {sum(before[q][2] == after[q][2] for q in shared)}')
for name, folder in (('before', sys.argv[1]), ('after', sys.argv[2])):
    m, n = recall(folder)
    print(f'context_recall_id {name}: {m:.4f} over {n} questions')

"""Independently check delivered source-ID metrics and budget accounting.

Reads IDs and sizes, never source bodies, questions, answers or the retriever.
Can verify a growing checkpoint; never labels a partial population complete.
"""
import argparse
import hashlib
import json
from pathlib import Path
import math

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def verify(out):
    plan = read(out / 'plan.json')
    for name, expected in plan['input_sha256'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, name
    units = read(ROOT / 'output/research/2026-09-22-gold-source-trace/chunk_delivery_index.json')
    index = read(ROOT / 'output/research/2026-09-22-gold-source-trace/gold_source_index.json')
    manifest = read(ROOT / 'output/research/2026-09-22-retrieval-matrix/inputs/cases_manifest.json')
    cases = {c['case_id']: c for c in manifest['cases']}
    program_ids = {p['id'] for p in plan['programs']}
    completed = []; count = 0; by_program = {p: [] for p in program_ids}
    for cid in plan['case_ids']:
        path = out / 'cases' / (cid + '.json')
        if not path.exists():
            continue
        rows = read(path)
        assert len(rows) == len(program_ids) and {r['program_id'] for r in rows} == program_ids
        meta = (read(ROOT / plan['case_metadata'][cid]) if 'case_metadata' in plan else
                read(ROOT / 'output/research/2026-09-22-retrieval-matrix/inputs' / cases[cid]['meta']))
        gold = set(index['questions'][meta['question_id']])
        for r in rows:
            assert r['case_id'] == cid
            ids = r['full_chunk_ids']; budget = r['budget']
            assert len(ids) == len(set(ids))
            sizes = [units[c]['serialized_chars'] for c in ids]
            used = sum(sizes)
            credit = {aid for c in ids for aid in units[c]['artifact_ids']}
            hits = len(gold & credit)
            assert r['hits'] == hits and r['gold_count'] == len(gold) and r['retrieved_ids'] == len(credit)
            recall = hits / len(gold); precision = hits / len(credit) if credit else None
            f1 = 2 * recall * precision / (recall + precision) if precision is not None and recall + precision else 0.
            for key, value in [('recall_id', recall), ('precision_id', precision), ('f1_id', f1)]:
                assert r[key] is None if value is None else math.isclose(r[key], value, rel_tol=0, abs_tol=1e-14), (cid, r['program_id'], key)
            assert used <= 72000 and budget['budget'] == 72000 and budget['kept'] == len(ids)
            assert r['full_chunks'] == len(ids) and r['delivered_chars'] == budget['chars']
            boundary = budget['boundary']
            if boundary:
                assert boundary['id'] not in ids
                assert boundary['chars_full'] == units[boundary['id']]['serialized_chars']
                assert 0 <= boundary['chars_kept'] < boundary['chars_full']
                assert used + boundary['chars_kept'] == budget['chars'] == 72000
                assert not budget['exhausted']
                assert r['partial_chunk_id'] == boundary['id']
            else:
                assert budget['chars'] == used and r['partial_chunk_id'] is None
            by_program[r['program_id']].append(r)
            count += 1
        reference = next(r for r in rows if r['program_id'] == plan['programs'][0]['id'])
        for r in rows:
            assert math.isclose(r['recall_delta'], r['recall_id'] - reference['recall_id'], rel_tol=0, abs_tol=1e-14)
            assert r['delivery_changed'] == (set(r['full_chunk_ids']) != set(reference['full_chunk_ids']))
        completed.append(cid)
    summaries = []
    for pid, rows in by_program.items():
        if not rows:
            continue
        summaries.append({'program_id': pid, 'cases': len(rows), 'total_gold_hits': sum(r['hits'] for r in rows),
                          'macro_recall_id': sum(r['recall_id'] for r in rows) / len(rows)})
    result = {'verified_cases': len(completed), 'expected_cases': len(plan['case_ids']),
              'verified_deliveries': count, 'population_complete': len(completed) == len(plan['case_ids']),
              'input_hashes_verified': True, 'metrics_and_boundary_accounting_verified': True,
              'full_order_not_recomputed': True, 'case_ids': completed,
              'checkpoint_leaders_by_total_hits': sorted(summaries, key=lambda r: (-r['total_gold_hits'], r['program_id']))[:10],
              'checkpoint_leaders_by_macro_recall': sorted(summaries, key=lambda r: (-r['macro_recall_id'], r['program_id']))[:10]}
    dest = out / ('independent-verification.json' if result['population_complete'] else 'checkpoint-verification.json')
    dest.write_text(json.dumps(result, indent=2), encoding='utf-8')
    return {k: v for k, v in result.items() if k not in ('case_ids','checkpoint_leaders_by_total_hits','checkpoint_leaders_by_macro_recall')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT / 'output/research/2026-09-23-construction-programs')
    print(json.dumps(verify(parser.parse_args().out)))

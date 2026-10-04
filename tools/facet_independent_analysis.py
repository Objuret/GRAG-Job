"""Summarize the frozen independent comparison without fitting any parameters."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'output/research/2026-09-22-joint-streams/independent_sources'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    cases = read(BASE / 'protocol.json')['targets']
    envelope = read(BASE / 'facet_stream_envelope/summary.json')
    concept = read(BASE / 'concept_baseline/summary.json')
    concept_runs = {}
    for entry in concept['runs']:
        path = BASE / 'concept_baseline' / (entry['run_id'] + '.json')
        assert hashlib.sha256(path.read_bytes()).hexdigest() == entry['source_sha256']
        run = read(path)
        concept_runs[run['reading_id']] = run
    rows = []
    for case in cases:
        runs = [r for r in envelope if r['question_id'] == case['question_id']]
        for reading in sorted({r['reading_id'] for r in runs}):
            conditions = {r['condition']: r for r in runs if r['reading_id'] == reading}
            assert set(conditions) == {'intact', 'aux_facets_off', 'shape_off'}
            cr = concept_runs[reading]
            focal = {v['chunk_id']: v for v in cr['focal'].values()}
            ids = case.get('required_within_selected_pair') or [case['preferred'], case['comparison']]
            ranks = {'concept': [focal[c]['rank'] for c in ids]}
            ranks.update({k: [v['focal'][c]['rank'] for c in ids] for k, v in conditions.items()})
            row = {'question_id': case['question_id'], 'reading_id': reading,
                   'source_group': case['source_group'], 'chunk_ids': ids, 'ranks': ranks,
                   'scores': {k: [v['focal'][c]['score'] for c in ids] for k, v in conditions.items()},
                   'pair_correct': {k: v['pair_correct'] for k, v in conditions.items()},
                   'focal_graph_witnesses': {c: {f: w for f, w in conditions['intact']['focal'][c]['provenance'].items()
                       if w and w['route_type'] != 'direct'} for c in ids}}
            if case.get('preferred'):
                row['pair_correct']['concept'] = ranks['concept'][0] < ranks['concept'][1]
                row['facet_direction_effect'] = ('improvement' if row['pair_correct']['intact'] else 'regression') if (
                    row['pair_correct']['intact'] != row['pair_correct']['aux_facets_off']) else 'unchanged'
            rows.append(row)
    assert len(rows) == 14
    path = BASE / 'comparison.json'
    if path.exists():
        raise RuntimeError('Refusing to overwrite comparison')
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    for row in rows:
        print(row['reading_id'], row['ranks'], row.get('facet_direction_effect', 'complementary'))


if __name__ == '__main__':
    main()

"""Capture query-to-graph structural pointers; never print query or source text.

Uses existing exact-name matching and the pinned structural snapshot. Stores
opaque landing ordinals and graph pointers only, plus hashes and status counts.
No interpreter, embedder, source-body resolver, evaluator or gold input is used.
"""
from pathlib import Path
import hashlib
import json
import sys
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'test'))
from artefact.facet_structural_landing import load_structural_index, resolve_structural_area
from artefact.facet_scope_alternatives import form_scope, scope_catalog

OUT = ROOT / 'output/research/2026-09-23-structural-scope-inputs'
INPUTS = ROOT / 'output/research/2026-09-22-retrieval-matrix/inputs'
SNAPSHOT = ROOT / 'output/research/2026-09-22-structural-landings/structural_snapshot.json'
STRUCTURAL_SHA = '9c9e9ff8415002cdc6203ecfdc29ef6a933d9eaf8859e3d1cf8d6678037f33ce'
GRAPH_SHA = '03befcae02198fff2dff184773aa87a6b46ac6d46ced72ab05f7b05ac118af00'


def read(p):
    return json.loads(p.read_text(encoding='utf-8'))


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write_new(p, value):
    if p.exists():
        if read(p) != value:
            raise ValueError('Existing capture differs: ' + p.name)
        return
    with p.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, allow_nan=False, indent=2)


def capture():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = read(INPUTS / 'cases_manifest.json')
    paths = [Path(__file__), ROOT / 'test/artefact/facet_scope_alternatives.py',
             ROOT / 'test/artefact/facet_structural_landing.py', SNAPSHOT,
             INPUTS / 'cases_manifest.json', ROOT / 'data/questions.jsonl']
    paths.extend(INPUTS / c['meta'] for c in manifest['cases'])
    hashes = {str(p.relative_to(ROOT)): digest(p) for p in paths}
    index = load_structural_index(SNAPSHOT, sha256=STRUCTURAL_SHA,
                                 graph_sha256=GRAPH_SHA, eligible_chunk_ids=manifest['chunk_ids'])
    wanted = {c['question_id']: c for c in manifest['cases']}
    seen = set(); statuses = Counter(); labels = Counter(); different = 0; distinct_masks = Counter()
    with (ROOT / 'data/questions.jsonl').open(encoding='utf-8') as stream:
        for line in stream:
            row = json.loads(line)
            if row['id'] not in wanted:
                continue
            case = wanted[row['id']]; cid = case['case_id']
            if cid in seen:
                raise ValueError('Duplicate question identity')
            seen.add(cid)
            original_area, diagnostic = resolve_structural_area(row['question'], index)
            landings = [{'landing_id': i, 'node_bindings': [
                {'label': b['label'], 'node_id': b['node_id'], 'routes': b['routes']}
                for b in landing['node_bindings']]} for i, landing in enumerate(diagnostic['landings'])]
            reproduced, details = form_scope(landings, index.eligible)
            if reproduced != original_area:
                raise ValueError('Default does not reproduce existing structural resolution')
            old = read(INPUTS / case['meta'])['area']['chunk_ids']
            old = None if old is None else frozenset(old)
            different += old != original_area
            masks = set()
            for policy in scope_catalog():
                area, _ = form_scope(landings, index.eligible, policy)
                masks.add(None if area is None else tuple(sorted(area)))
            distinct_masks[len(masks)] += 1
            statuses[diagnostic['status']] += 1
            labels.update(b['label'] for l in landings for b in l['node_bindings'])
            write_new(OUT / (cid + '.json'), {'case_id': cid, 'question_id': row['id'],
                'landings': landings, 'default_status': diagnostic['status'],
                'default_chunk_ids': None if original_area is None else sorted(original_area),
                'saved_area_differs': old != original_area, 'distinct_scope_masks': len(masks)})
    if seen != {c['case_id'] for c in manifest['cases']}:
        raise ValueError('Question identities missing from graph-scope capture')
    if any(digest(ROOT / p) != h for p, h in hashes.items()):
        raise ValueError('Capture input changed')
    result = {'cases': len(seen), 'input_sha256': hashes, 'graph_sha256': GRAPH_SHA,
              'structural_sha256': STRUCTURAL_SHA, 'default_parity_verified': True,
              'scope_policies': len(scope_catalog()), 'saved_areas_changed': different,
              'statuses': dict(statuses), 'landing_node_labels': dict(labels),
              'distinct_masks_per_case_histogram': dict(sorted(distinct_masks.items())),
              'language_model_calls': 0, 'embeddings': 0, 'source_bodies_read': False,
              'gold_read': False, 'query_text_exported': False,
              'case_sha256': {cid: digest(OUT / (cid + '.json')) for cid in sorted(seen)},
              'limitation': index.provenance['historical_limit']}
    # JSON keys must have the same type before comparison on verified resume.
    result = json.loads(json.dumps(result))
    write_new(OUT / 'manifest.json', result)
    print(json.dumps({k: v for k, v in result.items() if k not in ('input_sha256', 'case_sha256')}))


if __name__ == '__main__':
    capture()

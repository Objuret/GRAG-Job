"""Re-read stored Opus pair labels and round1 predictions by record kind.

No model, training, database, retrieval gold, question or source-body reader.
Original first-presentation decided-pair metric is reproduced before slicing.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'test'))
from graph.facet_pairs import data as D
from graph.facet_pairs.evaluate import first_presentations, _dist

PAIR = ROOT / 'output/facet_pairs'
ROUND = PAIR / 'rounds/round1'
SNAP = ROOT / 'output/research/2026-09-21-facet-validity/route_snapshot'
OUT = ROOT / 'output/research/2026-09-22-retrieval-matrix/pair-kind-validity'
HASHES = {}


def read(path):
    raw = path.read_bytes()
    HASHES[path.relative_to(ROOT).as_posix()] = hashlib.sha256(raw).hexdigest()
    return json.loads(raw)


def rows(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for line in stream:
            h.update(line)
            if line.strip():
                yield json.loads(line)
    HASHES[path.relative_to(ROOT).as_posix()] = h.hexdigest()


def summarize(items):
    decided = [x for x in items if x['outcome'] != 'equal']
    tied = [x for x in items if x['outcome'] == 'equal']
    correct = sum(x['correct'] for x in decided)
    return {
        'n_presentations': len(items), 'n_decided': len(decided), 'n_tied': len(tied),
        'correct_decided': correct, 'agreement': correct / len(decided) if decided else None,
        'prediction_exact_ties_on_decided': sum(x['gap'] == 0 for x in decided),
        'unique_pair_ids': len({x['pair_id'] for x in items}),
        'unique_decided_pair_ids': len({x['pair_id'] for x in decided}),
        'unique_chunks': len({x[k] for x in items for k in ('a_chunk_id', 'b_chunk_id')}),
        'decided_anchor_chunk_clusters': len({min(x['a_chunk_id'], x['b_chunk_id']) for x in decided}),
        'decided_unordered_chunk_pairs': len({tuple(sorted({x['a_chunk_id'], x['b_chunk_id']})) for x in decided}),
        'abs_gap_decided': _dist([abs(x['gap']) for x in decided]),
        'abs_gap_tied': _dist([abs(x['gap']) for x in tied]),
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / 'results.json'
    if target.exists():
        raise ValueError('Preserve completed validity audit')
    graph = read(SNAP / 'graph.json')
    kinds = {c['chunk_id']: c['source_kind'] for c in graph['chunks']}
    assert all(c['original_description_metadata']['k'] == c['source_kind'] for c in graph['chunks'])
    overlay = read(ROUND / 'overlay.json')
    scores = {r['edge_id']: r for r in rows(ROUND / 'scores.jsonl')}
    assert overlay['source_sha256'] == HASHES[(ROUND / 'scores.jsonl').relative_to(ROOT).as_posix()]
    assert all([scores[r['chunkId'] + '::' + r['tag']][f] for f in D.FACETS[1:]] == r['weights'][1:] for r in overlay['edges'])
    config = read(ROUND / 'model/config.json')
    previous = read(ROUND / 'eval.json')
    membership = list(rows(ROUND / 'edges.jsonl'))
    assert all((r['split'] == 'heldout') == D.is_heldout(r['chunk_id']) for r in membership)
    answers = []
    model_counts = Counter()
    for sub in sorted(p for p in (PAIR / 'answers').iterdir() if p.is_dir()):
        for path in sorted(sub.glob('*.json')):
            raw = read(path)
            model_counts[str(raw.get('model'))] += 1
            # Drop prompt/raw fields immediately; retain only comparison metadata.
            slim = {k: raw.get(k) for k in ('a', 'b', 'answers_canonical', 'pair_id', 'row_id', 'set', 'pair_type', 'order', 'repeat')}
            slim['set'] = slim['set'] or sub.name
            slim['row_id'] = slim['row_id'] or path.stem
            answers.append(slim)
    all_obs = D.observations(answers)
    partition = D.partition_observations(all_obs)
    tv = D.training_val_split(partition['train'])
    D.assert_no_heldout(tv['fit'])
    held = first_presentations(partition['heldout'])
    def covered(obs):
        return [o for o in obs if o['a_edge_id'] in scores and o['b_edge_id'] in scores]
    fit, validation, held = covered(tv['fit']), covered(tv['val']), covered(held)
    assert len(fit) == previous['probe']['counts']['fit_obs']
    assert len(validation) == previous['probe']['counts']['val_obs']
    assert len(held) == previous['probe']['counts']['heldout_obs']
    chunkset = lambda obs: {o[k] for o in obs for k in ('a_chunk_id', 'b_chunk_id')}
    fit_chunks, val_chunks, held_chunks = map(chunkset, (fit, validation, held))
    items = []
    for o in held:
        a, b = o['a_chunk_id'], o['b_chunk_id']
        assert a in kinds and b in kinds
        gap = scores[o['a_edge_id']][o['facet']] - scores[o['b_edge_id']][o['facet']]
        correct = (gap > 0 and o['outcome'] == 'first') or (gap < 0 and o['outcome'] == 'second')
        items.append({**o, 'gap': gap, 'correct': correct, 'same_kind': kinds[a] == kinds[b], 'kind_a': kinds[a], 'kind_b': kinds[b]})
    per = {}
    for facet in D.FACETS:
        own = [x for x in items if x['facet'] == facet]
        overall = summarize(own)
        original = previous['probe']['A']['per_facet'][facet]
        assert overall['n_decided'] == original['n'] and overall['agreement'] == original['agreement']
        per[facet] = {'all': overall,
            'same_kind': summarize([x for x in own if x['same_kind']]),
            'across_kinds': summarize([x for x in own if not x['same_kind']]),
            'same_kind_distinct_chunks': summarize([x for x in own if x['same_kind'] and x['a_chunk_id'] != x['b_chunk_id']]),
            'same_tag_same_kind': summarize([x for x in own if x['same_kind'] and x['a_tag'] == x['b_tag']]),
            'same_tag_across_kinds': summarize([x for x in own if not x['same_kind'] and x['a_tag'] == x['b_tag']]),
            'same_kind_by_pair_type': {t: summarize([x for x in own if x['same_kind'] and x['pair_type'] == t]) for t in sorted({x['pair_type'] for x in own})},
            'same_kind_by_kind': {k: summarize([x for x in own if x['same_kind'] and x['kind_a'] == k]) for k in sorted({x['kind_a'] for x in own if x['same_kind']})}}
    # The numerical facet layer in the retrieval snapshot must be this same raw head.
    with np.load(SNAP / 'arrays.npz', allow_pickle=False) as archive:
        raw_aux = archive['edge_facets'][:, 1:]
        expected = np.array([[scores[e][f] for f in D.FACETS[1:]] for e in graph['edge_ids']])
        assert np.array_equal(raw_aux, expected)
    source_paths = [Path(__file__), ROOT / 'test/graph/facet_pairs/data.py', ROOT / 'test/graph/facet_pairs/evaluate.py',
                    ROOT / 'test/graph/facet_pairs/cache_probe.py', ROOT / 'test/graph/facet_pairs/cache_round.py',
                    ROOT / 'test/graph/facet_pairs/bakeoff_report.py', PAIR / 'bakeoff/REPORT.md', SNAP / 'arrays.npz']
    for path in source_paths:
        HASHES[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    result = {
        'metric': 'Original round1 A: strict score-gap sign agreement on decided labels, first repeat per pair/facet/presentation order. Equal labels excluded from accuracy and separately counted.',
        'per_facet': per, 'answer_file_model_counts': dict(model_counts),
        'split_provenance': {
            'split_rule': config['split_rule'], 'fit_observations': len(fit), 'validation_observations': len(validation),
            'heldout_first_presentation_observations': len(held),
            'fit_chunks': len(fit_chunks), 'validation_chunks': len(val_chunks), 'heldout_chunks': len(held_chunks),
            'fit_heldout_shared_chunks': len(fit_chunks & held_chunks),
            'validation_heldout_shared_chunks': len(val_chunks & held_chunks),
            'fit_validation_shared_chunks': len(fit_chunks & val_chunks),
            'heldout_observations_both_endpoints_hash_heldout': sum(D.is_heldout(o['a_chunk_id']) and D.is_heldout(o['b_chunk_id']) for o in held),
            'heldout_observations_one_endpoint_hash_heldout': sum(D.is_heldout(o['a_chunk_id']) != D.is_heldout(o['b_chunk_id']) for o in held),
            'reproduced_original_counts_and_all_facet_agreements': True,
            'gradient_status': 'Chunk-hash heldout from fit; observed overlap counts reported explicitly.',
            'selection_status': 'Not untouched test: bakeoff_report.py chooses backbone using these heldout A/B/C outcomes; head/variant selection uses training validation carve-out.',
            'historical_binding_limit': 'Current stored labels/scores reproduce recorded results exactly; no new checkpoint inference or training performed.'},
        'retrieval_layer_binding': {'overlay_sha256': HASHES[(ROUND / 'overlay.json').relative_to(ROOT).as_posix()],
            'overlay_raw_aux_values_match_scores': True, 'frozen_semantic_edge_aux_values_match_scores': True},
        'limitations': [
            'Agreement measures prediction of stored Opus choices, not correctness of facet definitions or retrieval utility.',
            'Same-kind includes same-chunk comparisons; distinct-chunk and same-tag slices are reported separately.',
            'Counts of unique pairs and chunk clusters show dependence; no IID confidence interval or new significance claim is made.',
            'Backbone was selected using this heldout set, so these are gradient-heldout descriptive diagnostics, not untouched generalization estimates.',
            'No retraining, new labels, model calls, retrieval gold or source/question text inspection.'],
        'input_sha256': HASHES, 'language_model_calls': 0,
    }
    target.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps({'per_aux_facet': {f: {k: {x: per[f][k][x] for x in ('agreement', 'n_decided', 'n_tied', 'unique_decided_pair_ids')} for k in ('same_kind', 'across_kinds', 'same_kind_distinct_chunks', 'same_tag_same_kind')} for f in D.FACETS[1:]},
        'split_provenance': result['split_provenance'], 'overlay_sha256': result['retrieval_layer_binding']['overlay_sha256'],
        'output_sha256': hashlib.sha256(target.read_bytes()).hexdigest()}), flush=True)


if __name__ == '__main__':
    main()

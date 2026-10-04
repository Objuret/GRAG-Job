"""Ablate only the concept file layer's common facet-position modifier.

Retain graph growth/locality, all links, bands, source facet transformations and
query priority. This is a diagnostic, not a new weight formula or production fix.
Four existing generations, first SCORE reading only; no new model/DB/source reads.
"""
import ast
import copy
import hashlib
import os
from pathlib import Path
from datetime import datetime, timezone

import facet_concept_replay as replay

ROOT = replay.ROOT
BASE = ROOT / 'output/research/2026-09-22-joint-streams/concept'
OUT = BASE / 'composition_control'
CAPTURE = replay.BASE / 'route_capture/query_captures.json'


def main():
    if (OUT / 'comparison.json').exists():
        raise RuntimeError('Completed composition control exists; do not overwrite')
    OUT.mkdir(parents=True, exist_ok=True)
    baseline_protocol = replay.read(BASE / 'protocol.json')
    source = ROOT / 'test/arms/artefact_v3.py'
    if replay.sha(source) != baseline_protocol['source_sha256'][str(source.relative_to(ROOT))]:
        raise ValueError('Baseline source changed')
    raw = replay.read(CAPTURE)
    adapted = copy.deepcopy(raw)
    for c in adapted['captures']:
        c['readings'] = [c['readings'][0]]
        assert c['readings'][0]['ok']
    replay.write(OUT / 'selected_readings.json', adapted)

    # Import under the same explicit settings as the unmodified offline runner.
    for name in list(os.environ):
        if name.startswith(('HERB_V3_', 'HERB_FACET_', 'HERB_RANK_')):
            os.environ.pop(name)
    os.environ['HERB_V3_SORT'] = 'concept'
    os.environ['HERB_FACET_SOURCE'] = 'file'
    os.environ['HERB_FACET_FILE'] = str(ROOT / 'output/facet_pairs/rounds/round1/overlay.json')
    from arms import artefact_v3 as arm
    tree = ast.parse(source.read_text(encoding='utf8'))
    outer = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_retrieve_concept')
    before = ast.dump(outer, include_attributes=False)
    positions = next(n for n in outer.body if isinstance(n, ast.FunctionDef) and n.name == 'positions')
    last = positions.body[-1]
    assert isinstance(last, ast.Return) and isinstance(last.value, ast.Name) and last.value.id == 'pos'
    # Compute the exact old composition for the diagnostic, then return the base.
    last.value = ast.Call(func=ast.Name(id='__facet_composition_audit', ctx=ast.Load()),
                          args=[ast.Name(id='P_base', ctx=ast.Load()), ast.Name(id='pos', ctx=ast.Load())],
                          keywords=[])
    ast.fix_missing_locations(outer)
    after = ast.dump(outer, include_attributes=False)
    (OUT / 'modified_function.py').write_text(ast.unparse(outer) + '\n', encoding='utf8')
    audits = []
    np = replay.np

    def audit_positions(base, composed):
        assert base.shape == composed.shape == (61018, 5)
        assert np.array_equal(base[:, 0], composed[:, 0])
        b, c = base[:, 1:], composed[:, 1:]
        base_equal = np.all(b == b[:, :1], axis=1)
        composed_equal = np.all(c == c[:, :1], axis=1)
        stats = {'edges': len(base), 'non_topic_coordinates': b.size,
                 'changed_coordinates': int(np.count_nonzero(b != c)),
                 'edges_with_changed_coordinate': int(np.count_nonzero(np.any(b != c, axis=1))),
                 'base_four_columns_identical': int(base_equal.sum()),
                 'composed_four_columns_identical': int(composed_equal.sum()),
                 'newly_introduced_four_column_collapses': int(np.count_nonzero(composed_equal & ~base_equal)),
                 'base_positions_sha256': hashlib.sha256(base.tobytes()).hexdigest(),
                 'composed_positions_sha256': hashlib.sha256(composed.tobytes()).hexdigest()}
        if not audits:
            np.savez_compressed(OUT / 'composition_arrays.npz', base=base, composed=composed)
        elif stats != audits[0]:
            raise ValueError('Unexpected query-dependent composition in the declared single-pass population')
        audits.append(stats)
        return base.copy()

    arm.__dict__['__facet_composition_audit'] = audit_positions
    exec(compile(ast.Module(body=[outer], type_ignores=[]), str(OUT / 'modified_function.py'), 'exec'), arm.__dict__)
    contract = {'protocol': __doc__, 'frozen_utc': datetime.now(timezone.utc).isoformat(),
                'baseline_protocol_sha256': replay.sha(BASE / 'protocol.json'),
                'runner_sha256': replay.sha(Path(replay.__file__)), 'control_sha256': replay.sha(Path(__file__)),
                'source_function_ast_before_sha256': hashlib.sha256(before.encode()).hexdigest(),
                'source_function_ast_after_sha256': hashlib.sha256(after.encode()).hexdigest(),
                'modified_function_sha256': replay.sha(OUT / 'modified_function.py'),
                'selected_readings_sha256': replay.sha(OUT / 'selected_readings.json'),
                'intervention': 'Only nested positions() return changes: audit old composed positions and return P_base.copy(). All source facet transformations remain.',
                'scope': 'All four captured inputs have no gate and one pass; no out-of-scope topic restriction is removed.',
                'expected': ['Query links, bands, seeds, growth and per-part locality computations unchanged.',
                             'Focal earliest levels and pair directions unchanged; ranks/witnesses may change within levels.',
                             'Changed ranks demonstrate influence, not improved usefulness.'],
                'metadata_warning': 'Source concentration metadata still describes the computed baseline modifier; it is bypassed in the returned positions.'}
    replay.write(OUT / 'control_contract.json', contract)
    original_read = replay.read
    replay.read = lambda path: adapted if Path(path) == CAPTURE else original_read(path)
    replay.OUT = OUT
    replay.main()
    rows = []
    for capture in adapted['captures']:
        run_id = capture['readings'][0]['id'] + '_concept_file'
        old = original_read(BASE / (run_id + '.json'))
        new = original_read(OUT / (run_id + '.json'))
        assert old['flags'] == new['flags']
        assert not old['source_metadata']['scope']['named'] and not new['source_metadata']['scope']['named']
        assert old['shape_seed_trace'] == new['shape_seed_trace']
        old_parts, new_parts = old['source_metadata']['parts'], new['source_metadata']['parts']
        for a, b in zip(old_parts, new_parts):
            for key in ('part', 'rank', 'facet_order', 'locality', 'region', 'tag_levels', 'desc_levels', 'level0_edges'):
                assert a.get(key) == b.get(key), (run_id, key)
        # The same ordered list of connection-level blocks must be retained.
        def blocks(run):
            i, result = 0, []
            for row in run['source_metadata']['walk']:
                n = row['new']
                result.append((row['pass'], row['level'], frozenset(run['chunk_order'][i:i+n])))
                i += n
            assert i == len(run['chunk_order'])
            return result
        assert blocks(old) == blocks(new), 'A changed earlier level would violate the intervention'
        for label in old['focal']:
            assert old['focal'][label]['selected_row']['fit'] == new['focal'][label]['selected_row']['fit']
        old_ranks = {cid: i for i, cid in enumerate(old['chunk_order'])}
        rows.append({'run_id': run_id, 'changed_chunk_positions': sum(a != b for a, b in zip(old['chunk_order'], new['chunk_order'])),
                     'max_position_change': max(abs(old_ranks[cid] - i) for i, cid in enumerate(new['chunk_order'])),
                     'seed_and_growth_trace_identical': True, 'per_part_locality_inputs_and_histograms_identical': True,
                     'earliest_level_chunk_blocks_identical': True,
                     'old_focal_ranks': {k: v['rank'] for k, v in old['focal'].items()},
                     'new_focal_ranks': {k: v['rank'] for k, v in new['focal'].items()},
                     'changed_focal_witnesses': {k: (old['focal'][k]['selected_route']['part'], old['focal'][k]['selected_route']['edge_id']) !=
                                                   (new['focal'][k]['selected_route']['part'], new['focal'][k]['selected_route']['edge_id']) for k in old['focal']},
                     'base_result_sha256': replay.sha(BASE / (run_id + '.json')),
                     'control_result_sha256': replay.sha(OUT / (run_id + '.json'))})
    result = {'control_contract_sha256': replay.sha(OUT / 'control_contract.json'),
              'composition': audits[0], 'position_calls_checked': len(audits), 'runs': rows,
              'limits': ['Focal witnesses only; all nonfocal route witnesses were not captured.',
                         'Locality algorithm and seed/graph inputs identical, with matching per-part histograms; no claim that selected-row locality stays equal when the selected part changes.',
                         'This ablation establishes composition effects, not a permanent repair or retrieval-quality improvement.']}
    replay.write(OUT / 'comparison.json', result)
    print(result)


if __name__ == '__main__':
    main()

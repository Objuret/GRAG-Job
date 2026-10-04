"""One declared 0.1 query-facet magnitude control using the frozen concept runner.

Keep the original eight-run runner/protocol/results unchanged. Adapt only one
captured query input at the file-reading boundary; no model or graph calls.
"""
from pathlib import Path
from datetime import datetime, timezone
import copy
import hashlib
import json

import facet_concept_replay as replay

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'output/research/2026-09-22-joint-streams/concept'
OUT = BASE / 'magnitude_control'
CAPTURE = ROOT / 'output/research/2026-09-21-facet-validity/route_capture/query_captures.json'
READING_ID = 'sharing_1_score_0'


def main():
    print('Freezing the single query-facet magnitude control (scale 0.1)', flush=True)
    raw = replay.read(CAPTURE)
    capture = next(c for c in raw['captures'] if c['generation_id'] == 'sharing_1')
    reading = next(r for r in capture['readings'] if r['id'] == READING_ID)
    if not reading['ok']:
        raise ValueError('Declared source reading is missing')
    adapted = copy.deepcopy(raw)
    adapted_capture = copy.deepcopy(capture)
    adapted_reading = copy.deepcopy(reading)
    for row in adapted_reading['values']:
        row['facets'] = {f: 0.1 * value for f, value in row['facets'].items()}
    adapted_capture['readings'] = [adapted_reading]
    adapted['captures'] = [adapted_capture]
    facets = raw['facets']
    for old, new in zip(reading['values'], adapted_reading['values']):
        order = lambda row: sorted(facets, key=lambda f: (-row['facets'][f], facets.index(f)))
        if order(old) != order(new):
            raise ValueError('The prescribed scale changed a facet order')
    OUT.mkdir(parents=True, exist_ok=True)
    replay.write(OUT / 'adapted_capture.json', adapted)
    contract = {'protocol': __doc__, 'frozen_utc': datetime.now(timezone.utc).isoformat(),
        'source_reading': READING_ID, 'generation_id': 'sharing_1', 'scale': 0.1,
        'expected': 'Full chunk order identical because FACETADJ=off carries magnitudes but uses only their ordering.',
        'only_change': 'All five values of every tag in the selected SCORE reading multiplied by 0.1; question, description, tags, graph, shape, bands and operators fixed.',
        'raw_query_facets': reading['values'], 'adapted_query_facets': adapted_reading['values'],
        'original_runner_sha256': replay.sha(Path(replay.__file__)),
        'control_runner_sha256': replay.sha(Path(__file__)),
        'original_capture_sha256': replay.sha(CAPTURE),
        'adapted_capture_sha256': replay.sha(OUT / 'adapted_capture.json'),
        'input_boundary': 'Existing runner read(CAPTURE) returns adapted_capture.json contents. Its source manifest retains the original source-file hash; this control contract records the explicit intervention.'}
    replay.write(OUT / 'control_contract.json', contract)
    original_read = replay.read
    replay.read = lambda path: adapted if Path(path) == CAPTURE else original_read(path)
    replay.OUT = OUT
    replay.main()
    name = READING_ID + '_concept_file.json'
    original = original_read(BASE / name)
    scaled = original_read(OUT / name)
    same = original['chunk_order'] == scaled['chunk_order']
    result = {'control_contract_sha256': replay.sha(OUT / 'control_contract.json'),
              'base_result_sha256': replay.sha(BASE / name), 'scaled_result_sha256': replay.sha(OUT / name),
              'identical_full_order': same, 'chunks_compared': len(original['chunk_order']),
              'changed_positions': sum(a != b for a, b in zip(original['chunk_order'], scaled['chunk_order'])),
              'raw_focal_ranks': {k: v['rank'] for k, v in original['focal'].items()},
              'scaled_focal_ranks': {k: v['rank'] for k, v in scaled['focal'].items()},
              'facet_orders_unchanged': [p['facet_order'] for p in original['source_metadata']['parts']] ==
                                        [p['facet_order'] for p in scaled['source_metadata']['parts']]}
    replay.write(OUT / 'comparison.json', result)
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()

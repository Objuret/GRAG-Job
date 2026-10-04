"""Posthoc contiguous-record context recovery on frozen recruitment frontiers."""
from collections import defaultdict
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'output/research/2026-09-22-joint-streams/independent_sources'
OUT = BASE / 'need_selection/content_audit'
GRAPH = ROOT / 'output/research/2026-09-21-facet-validity/route_snapshot/graph.json'
QUESTION_ID = 'independent_durable_messages_current_models'
BUDGET = 72000


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def components(chunks):
    """Group only identical record endpoints, then overlapping/touching ranges."""
    records = defaultdict(list)
    ranged = set()
    fields = ('parent_ref', 'id', 'index', 'field', 'section')
    for c in chunks:
        loc = json.loads(c['locator']) if isinstance(c['locator'], str) else c['locator']
        if 'char_range' not in loc:
            continue
        assert c['relpath'] and all(k in loc and loc[k] is not None for k in fields)
        start, end = loc['char_range']
        assert isinstance(start, int) and isinstance(end, int) and 0 <= start < end
        key = (c['relpath'],) + tuple(loc[k] for k in fields)
        records[key].append((start, end, c['chunkId']))
        ranged.add(c['chunkId'])
    result = []
    for key, intervals in sorted(records.items()):
        current, right = [], -1
        pieces = []
        for start, end, cid in sorted(intervals):
            if current and start > right:
                pieces.append(current)
                current = []
            current.append((start, end, cid))
            right = max(right, end) if len(current) > 1 else end
        if current:
            pieces.append(current)
        for part in pieces:
            payload = {'record': dict(zip(('relpath',) + fields, key)),
                       'members': [{'chunk_id': cid, 'char_range': [start, end]}
                                   for start, end, cid in part]}
            digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
            result.append({'component_id': digest, **payload})
    assigned = [m['chunk_id'] for comp in result for m in comp['members']]
    assert len(assigned) == len(set(assigned)) == len(ranged)
    return result, ranged, len(records)


def assemble(rows, comps, chunk_map):
    old = {r['chunk_id']: r['depth'] for r in rows}
    depths, triggers, memberships = dict(old), {}, {}
    for comp in comps:
        ids = [m['chunk_id'] for m in comp['members']]
        support = [old[cid] for cid in ids if old[cid] is not None]
        depth = min(support) if support else None
        sponsors = sorted(cid for cid in ids if depth is not None and old[cid] == depth)
        for cid in ids:
            depths[cid] = depth
            triggers[cid] = sponsors
            memberships[cid] = comp['component_id']
    grouped = defaultdict(list)
    for cid, depth in depths.items():
        if depth is not None:
            grouped[depth].append(cid)
        if old[cid] is not None:
            assert depth is not None and depth <= old[cid]
    frontiers, intervals, cumulative, cumulative_chars = [], {}, 0, 0
    kept, crossing, chars = [], [], 0
    crossed = False
    for depth, ids in sorted(grouped.items()):
        ids.sort()
        cost = sum(len(chunk_map[cid]['source_text']) for cid in ids)
        first = cumulative + 1
        cumulative += len(ids)
        cumulative_chars += cost
        intervals[depth] = (first, cumulative)
        frontiers.append({'depth': depth, 'chunk_ids': ids, 'size': len(ids),
                          'source_characters': cost, 'cumulative_size': cumulative,
                          'cumulative_source_characters': cumulative_chars})
        if not crossed:
            if chars + cost > BUDGET:
                crossing, crossed = ids, True
            else:
                kept += ids
                chars += cost
    expanded = []
    for cid in sorted(old, key=lambda c: (depths[c] is None, depths[c] or 0, c)):
        depth = depths[cid]
        first, last = intervals.get(depth, (None, None))
        expanded.append({'chunk_id': cid, 'original_depth': old[cid], 'depth': depth,
                         'first_position': first, 'last_position': last,
                         'component_id': memberships.get(cid),
                         'trigger_chunk_ids': triggers.get(cid, [cid] if depth is not None else [])})
    assert len(expanded) == len(old)
    return {'rows': expanded, 'frontiers': frontiers, 'selected_chunk_ids': kept,
            'source_characters': chars, 'unused_capacity': BUDGET - chars,
            'crossing_frontier_chunk_ids': crossing,
            'crossing_frontier_source_characters': sum(len(chunk_map[c]['source_text']) for c in crossing),
            'unsupported_chunk_ids': sorted(cid for cid, depth in depths.items() if depth is None)}


def main():
    output = OUT / 'record_context_probe.json'
    extra = OUT / 'additional_reader_packet.json'
    if output.exists() or extra.exists():
        raise RuntimeError('Refusing to overwrite frozen context-recovery evidence')
    paths = [Path(__file__), GRAPH, BASE / 'questions.json',
             OUT / 'reader_packet.json', OUT / 'private_manifest.json']
    old_manifest = read(OUT / 'private_manifest.json')
    for path, expected in old_manifest['input_sha256'].items():
        assert sha(ROOT / path) == expected, 'Frozen packet input changed'
    assert sha(OUT / 'reader_packet.json') == old_manifest['packet_sha256']
    old_packet_ids = set(old_manifest['aliases'])
    graph = read(GRAPH)
    chunks = graph['chunks']
    assert len(chunks) == 4808
    chunk_map = {c['chunkId']: c for c in chunks}
    comps, ranged, record_count = components(chunks)
    for c in chunks:
        assert hashlib.sha256(c['source_text'].encode()).hexdigest() == c['source_text_sha256']
    runs = []
    new_ids = set()
    for repeat in (0, 1):
        for mode in ('joint', 'facets'):
            path = BASE / f'need_selection/replay/{QUESTION_ID}_0_score_{repeat}_{mode}.json'
            paths.append(path)
            source = read(path)
            assert {r['chunk_id'] for r in source['rows']} == set(chunk_map)
            expanded = assemble(source['rows'], comps, chunk_map)
            old = next(x for x in old_manifest['runs'] if x['reading'] == repeat and x['mode'] == mode)
            old_selected = set(old['complete_frontier_chunk_ids'])
            selected = set(expanded['selected_chunk_ids'])
            outside = selected - old_packet_ids
            new_ids.update(outside)
            runs.append({'reading': repeat, 'mode': mode, **expanded,
                         'original_selected_chunk_ids': old['complete_frontier_chunk_ids'],
                         'original_source_characters': old['source_characters'],
                         'newly_selected_chunk_ids': sorted(selected - old_selected),
                         'displaced_original_chunk_ids': sorted(old_selected - selected),
                         'newly_selected_outside_original_reader_packet': sorted(outside)})
    # Inspect the previously selected pair only after generic grouping/reassembly.
    focal = ['1c982e912346f77d7e155393', '3b4c077ffb1c30ea0b293fb1']
    for run in runs:
        run['selected_pair_diagnostic'] = [
            {**row, 'within_source_character_budget': row['chunk_id'] in run['selected_chunk_ids']}
            for row in run['rows'] if row['chunk_id'] in focal]
    question = next(q['question'] for q in read(BASE / 'questions.json') if q['id'] == QUESTION_ID)
    ordered = sorted(new_ids, key=lambda cid: hashlib.sha256(('record-context-v1:' + cid).encode()).hexdigest())
    aliases = {cid: f'passage_{i:04d}' for i, cid in enumerate(ordered, 1001)}
    if ordered:
        write(extra, {'question': question, 'passages': [
            {'passage_id': aliases[cid],
             'graph_products': [p['name'] for p in chunk_map[cid]['scope'].get('product', [])],
             'graph_channels': [p['name'] for p in chunk_map[cid]['scope'].get('channel', [])],
             'source_kind': chunk_map[cid]['source_kind'], 'text': chunk_map[cid]['source_text']}
            for cid in ordered]})
    result = {
        'input_sha256': {str(p.relative_to(ROOT)): sha(p) for p in paths},
        'question_id': QUESTION_ID, 'budget_source_characters': BUDGET,
        'method': 'Each exact-record overlapping/touching range component inherits the minimum supported member frontier depth. Singleton/non-range chunks retain their own depth. No scores change.',
        'group_identity': ['relpath', 'locator.parent_ref', 'locator.id', 'locator.index', 'locator.field', 'locator.section'],
        'scope_limit': 'Posthoc context recovery for one known question, not a ranking proposal or evidence that general parent expansion is beneficial. No channel or product expansion.',
        'budget_limit': 'Complete frontiers; sum saved source_text lengths per chunk, including repeated overlap if any. No text merging, live resolver, truncation, token budget, or metadata cost.',
        'counts': {'chunks': len(chunks), 'char_range_chunks': len(ranged),
                   'logical_records': record_count, 'contiguous_components': len(comps),
                   'multi_chunk_components': sum(len(c['members']) > 1 for c in comps),
                   'non_range_singletons': len(chunks) - len(ranged)},
        'components': comps, 'runs': runs,
        'additional_reader_aliases': aliases,
        'additional_reader_packet_sha256': sha(extra) if ordered else None,
        'additional_reader_passages': len(ordered),
        'additional_reader_source_characters': sum(len(chunk_map[c]['source_text']) for c in ordered),
        'model_calls': 0, 'db_calls': 0,
    }
    write(output, result)
    print(json.dumps({'counts': result['counts'], 'additional_passages': len(ordered),
                      'additional_source_characters': result['additional_reader_source_characters'],
                      'runs': [{'reading': r['reading'], 'mode': r['mode'],
                                'selected': len(r['selected_chunk_ids']), 'chars': r['source_characters'],
                                'new_outside_packet': len(r['newly_selected_outside_original_reader_packet']),
                                'focal': r['selected_pair_diagnostic']} for r in runs]}, indent=2))


if __name__ == '__main__':
    main()

"""Validate source citations and join hidden-method content judgments afterward."""
from pathlib import Path
from collections import Counter
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'output/research/2026-09-22-joint-streams/independent_sources/need_selection/content_audit'
COMPONENTS = ('durability', 'model_updates', 'refresh_frequency')
CATEGORIES = ('none', 'context', 'partial', 'direct')


def read(p):
    return json.loads(p.read_text(encoding='utf-8'))


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    out = BASE / 'analysis.json'
    if out.exists():
        raise RuntimeError('Refusing to overwrite source judgments analysis')
    packet = read(BASE / 'reader_packet.json')
    manifest = read(BASE / 'private_manifest.json')
    assert sha(BASE / 'reader_packet.json') == manifest['packet_sha256']
    assert all(sha(ROOT / p) == h for p, h in manifest['input_sha256'].items())
    passages = {p['passage_id']: p for p in packet['passages']}
    readers, quotes = {}, {}
    for name in ('reader_one', 'reader_two'):
        data = read(BASE / (name + '.json'))
        entries = {r['passage_id']: r for r in data['entries']}
        assert len(entries) == len(data['entries']) == len(passages)
        assert set(entries) == set(passages)
        count = 0
        for pid, row in entries.items():
            assert row['scope'] in ('supports_requested_system', 'other_system', 'uncertain')
            assert set(row['components']) == set(COMPONENTS)
            for comp in COMPONENTS:
                value = row['components'][comp]
                assert value['category'] in CATEGORIES
                assert value['reason']
                if value['category'] in ('partial', 'direct'):
                    assert value['quotes']
                for quote in value['quotes']:
                    assert quote and quote in passages[pid]['text'], (name, pid, quote)
                    count += 1
        readers[name], quotes[name] = entries, count
    disagreements = []
    for pid in passages:
        a, b = (r[pid] for r in readers.values())
        for comp in COMPONENTS:
            ca, cb = a['components'][comp]['category'], b['components'][comp]['category']
            if ca != cb:
                disagreements.append({'passage_id': pid, 'component': comp,
                                      'reader_one': ca, 'reader_two': cb})
        if a['scope'] != b['scope']:
            disagreements.append({'passage_id': pid, 'component': 'scope',
                                  'reader_one': a['scope'], 'reader_two': b['scope']})
    runs = []
    for run in manifest['runs']:
        record = {'reading': run['reading'], 'mode': run['mode'],
                  'source_characters': run['source_characters'], 'readers': {}}
        for role, field in (('admitted', 'complete_frontier_chunk_ids'),
                            ('crossing', 'crossing_frontier_chunk_ids')):
            pids = [manifest['aliases'][cid] for cid in run[field]]
            record[role + '_passage_ids'] = pids
            for name, entries in readers.items():
                counts = {}
                for comp in COMPONENTS:
                    counts[comp] = {cat: [pid for pid in pids
                        if entries[pid]['scope'] == 'supports_requested_system'
                        and entries[pid]['components'][comp]['category'] == cat]
                                   for cat in CATEGORIES}
                record['readers'].setdefault(name, {})[role] = {
                    'scope_counts': dict(Counter(entries[pid]['scope'] for pid in pids)),
                    'requested_system_support': counts}
        runs.append(record)
    paths = [Path(__file__), BASE / 'reader_packet.json', BASE / 'private_manifest.json',
             BASE / 'reader_one.json', BASE / 'reader_two.json', BASE / 'PROTOCOL.md']
    result = {'input_sha256': {str(p.relative_to(ROOT)): sha(p) for p in paths},
              'validated_quote_substrings': quotes, 'passages_per_reader': len(passages),
              'disagreements': disagreements, 'runs': runs,
              'interpretation': 'Model source readings, not human gold or population performance; scope-qualified support counted, repeats not independent evidence.'}
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Quotes validated', quotes, '; disagreements', len(disagreements), 'of', len(passages)*3, 'component classifications')
    for run in runs:
        print(run['reading'], run['mode'], run['source_characters'], 'source chars')
        for reader, roles in run['readers'].items():
            print(reader, roles['admitted']['scope_counts'], {
                c: {v: len(ids) for v, ids in cats.items()}
                for c, cats in roles['admitted']['requested_system_support'].items()})


if __name__ == '__main__':
    main()

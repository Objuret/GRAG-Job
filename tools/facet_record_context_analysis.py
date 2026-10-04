"""Join independently read source support to the frozen record-context probe."""
from pathlib import Path
from collections import Counter
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'output/research/2026-09-22-joint-streams/independent_sources/need_selection/content_audit'
COMPS = ('durability', 'model_updates', 'refresh_frequency')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    out = BASE / 'record_content_analysis.json'
    if out.exists():
        raise RuntimeError('Refusing to overwrite frozen analysis')
    manifest = read(BASE / 'private_manifest.json')
    probe = read(BASE / 'record_context_probe.json')
    assert all(sha(ROOT / p) == h for p, h in probe['input_sha256'].items())
    assert sha(BASE / 'additional_reader_packet.json') == probe['additional_reader_packet_sha256']
    packets = [read(BASE / n) for n in ('reader_packet.json', 'additional_reader_packet.json')]
    assert packets[0]['question'] == packets[1]['question']
    texts = {p['passage_id']: p['text'] for packet in packets for p in packet['passages']}
    aliases = {**manifest['aliases'], **probe['additional_reader_aliases']}
    assert len(texts) == len(aliases) == 43
    readers, counts = {}, {}
    inputs = [Path(__file__), BASE / 'record_context_probe.json', BASE / 'private_manifest.json',
              BASE / 'reader_packet.json', BASE / 'additional_reader_packet.json']
    for name in ('reader_one', 'reader_two'):
        paths = [BASE / (name + '.json'), BASE / (name + '_additional.json')]
        inputs += paths
        rows = [r for path in paths for r in read(path)['entries']]
        assert len(rows) == len(texts)
        entries = {r['passage_id']: r for r in rows}
        assert set(entries) == set(texts)
        nquotes = 0
        for pid, row in entries.items():
            assert row['scope'] in ('supports_requested_system', 'other_system', 'uncertain')
            assert set(row['components']) == set(COMPS)
            for comp in COMPS:
                value = row['components'][comp]
                assert value['category'] in ('none', 'context', 'partial', 'direct')
                if value['category'] in ('partial', 'direct'):
                    assert value['quotes']
                for quote in value['quotes']:
                    assert quote and quote in texts[pid], (name, pid, quote)
                    nquotes += 1
        readers[name], counts[name] = entries, nquotes
    runs = []
    for run in probe['runs']:
        result = {'reading': run['reading'], 'mode': run['mode'], 'readers': {},
                  'original_source_characters': run['original_source_characters'],
                  'expanded_source_characters': run['source_characters'],
                  'expanded_chunks': len(run['selected_chunk_ids']),
                  'unused_capacity': run['unused_capacity']}
        for name, entries in readers.items():
            result['readers'][name] = {}
            for condition, field in (('original', 'original_selected_chunk_ids'),
                                     ('expanded', 'selected_chunk_ids'),
                                     ('newly_selected', 'newly_selected_chunk_ids'),
                                     ('displaced', 'displaced_original_chunk_ids')):
                pids = [aliases[cid] for cid in run[field]]
                direct = {comp: [pid for pid in pids
                          if entries[pid]['scope'] == 'supports_requested_system'
                          and entries[pid]['components'][comp]['category'] == 'direct'] for comp in COMPS}
                result['readers'][name][condition] = {
                    'scope_counts': dict(Counter(entries[pid]['scope'] for pid in pids)),
                    'direct_component_support': direct,
                    'components_with_direct_support': [c for c in COMPS if direct[c]]}
        runs.append(result)
    result = {'input_sha256': {str(p.relative_to(ROOT)): sha(p) for p in inputs},
              'validated_quote_substrings': counts, 'passages_per_reader': len(texts),
              'runs': runs,
              'limits': 'One posthoc source-content probe; LLM classifications with exact quotes, not human gold. Complete-frontier source characters are not live harness serialization.'}
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    for run in runs:
        print(run['reading'], run['mode'], 'source chars', run['expanded_source_characters'],
              'chunks', run['expanded_chunks'])
        for reader, conditions in run['readers'].items():
            print(reader, {c: {k: len(v) for k, v in value['direct_component_support'].items()}
                           for c, value in conditions.items()})


if __name__ == '__main__':
    main()

"""Join existing source readings after structural recruitment is frozen."""
from pathlib import Path
import gzip
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'output/research/2026-09-22-joint-streams/independent_sources'
AUDIT = BASE / 'need_selection/content_audit'
RUN = BASE / 'scope_recruitment/run'
COMPONENTS = ('durability', 'model_updates', 'refresh_frequency')


def read(p):
    return json.loads(p.read_text(encoding='utf-8'))


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    out = RUN / 'content_join.json'
    if out.exists():
        raise RuntimeError('Refusing to overwrite content join')
    manifest = read(RUN / 'manifest.json')
    assert all(sha(RUN / p) == h for p, h in manifest['output_sha256'].items())
    aliases = {**read(AUDIT / 'private_manifest.json')['aliases'],
               **read(AUDIT / 'record_context_probe.json')['additional_reader_aliases']}
    packets = [read(AUDIT / n) for n in ('reader_packet.json', 'additional_reader_packet.json')]
    texts = {p['passage_id']: p['text'] for packet in packets for p in packet['passages']}
    paths = [Path(__file__), RUN / 'manifest.json', RUN / 'summary.json',
             AUDIT / 'private_manifest.json', AUDIT / 'record_context_probe.json',
             AUDIT / 'reader_packet.json', AUDIT / 'additional_reader_packet.json']
    readers, quotes = {}, 0
    for name in ('reader_one', 'reader_two'):
        sources = [AUDIT / (name + '.json'), AUDIT / (name + '_additional.json')]
        paths += sources
        entries = {r['passage_id']: r for p in sources for r in read(p)['entries']}
        assert set(entries) == set(texts)
        for pid, entry in entries.items():
            for component in COMPONENTS:
                for quote in entry['components'][component]['quotes']:
                    assert quote and quote in texts[pid]
                    quotes += 1
        readers[name] = entries
    rows = []
    for row in read(RUN / 'summary.json'):
        if row['question_id'] != 'independent_durable_messages_current_models':
            continue
        path = RUN / row['file']
        paths.append(path)
        data = json.loads(gzip.decompress(path.read_bytes()))
        selected = set(data['recruitment']['selected_chunk_ids'])
        baseline = (selected - set(row['added_chunk_ids'])) | set(row['displaced_chunk_ids'])
        result = {'reading_id': row['reading_id'], 'conditions': {}}
        for label, ids in [('before', baseline), ('after', selected),
                           ('added', set(row['added_chunk_ids'])), ('displaced', set(row['displaced_chunk_ids']))]:
            known = ids & set(aliases)
            support = {}
            for name, entries in readers.items():
                support[name] = {comp: sorted(cid for cid in known
                    if entries[aliases[cid]]['scope'] == 'supports_requested_system'
                    and entries[aliases[cid]]['components'][comp]['category'] == 'direct') for comp in COMPONENTS}
            result['conditions'][label] = {'chunks': len(ids), 'judged_chunk_ids': sorted(known),
                'unjudged_chunk_ids': sorted(ids-known), 'direct_support': support}
        rows.append(result)
    result = {'input_sha256': {str(p.relative_to(ROOT)): sha(p) for p in paths},
              'validated_existing_quote_substrings': quotes, 'runs': rows,
              'limits': 'Reused model source readings, not human gold or new semantic evaluation. Unjudged passages remain unjudged.'}
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    for run in rows:
        print(run['reading_id'])
        for label, c in run['conditions'].items():
            print(label, 'unjudged', len(c['unjudged_chunk_ids']),
                  {r: {k: len(v) for k, v in supports.items()} for r, supports in c['direct_support'].items()})


if __name__ == '__main__':
    main()

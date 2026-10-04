"""Freeze a source-only, record-disjoint transfer sample; no retrieval/model calls."""
from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / 'output/research'
OUT = RESEARCH / '2026-09-22-facet-transfer'
GRAPH = RESEARCH / '2026-09-21-facet-validity/route_snapshot/graph.json'
PROTOCOL = ROOT / 'docs/2026-09-22-facet-transfer-protocol.md'
SEED = '2026-09-22-frozen-facet-transfer-v1'
EXCLUDED_PRODUCTS = {'WorkFlowGenie', 'EdgeForce', 'ActionGenie', 'SentimentForce', 'TrendForce'}


def sha(value):
    return hashlib.sha256(value).hexdigest()


def freeze(path, obj):
    data = (json.dumps(obj, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError(f'Frozen record differs: {path}')
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as f:
            f.write(data)


def record_keys(c):
    loc = json.loads(c['locator'])
    indices = loc.get('indices', [loc.get('index')])
    if indices == [None] and 'index_start' in loc:
        indices = list(range(loc['index_start'], loc['index_end'] + 1))
    if indices == [None]:
        raise ValueError(f'No record index: {c["chunkId"]}')
    return {(c['relpath'], loc['section'], loc.get('channel'), i) for i in indices}


def main():
    graph = json.loads(GRAPH.read_text(encoding='utf-8'))
    chunks = {c['chunkId']: c for c in graph['chunks']}
    records = {cid: record_keys(c) for cid, c in chunks.items()}
    paths = sorted(p for p in RESEARCH.rglob('*.json') if OUT not in p.parents and
                   any(s in p.name.lower() for s in
                       ('cases', 'pairs', 'packet', 'questions', 'case_protocol', 'selection_protocol')))
    used, inventory = set(), []
    for p in paths:
        raw = p.read_bytes()
        ids = set(re.findall(r'(?<![a-f0-9])[a-f0-9]{24}(?![a-f0-9])', raw.decode('utf-8-sig'))) & chunks.keys()
        used.update(ids)
        inventory.append({'path': p.relative_to(ROOT).as_posix(), 'sha256': sha(raw), 'chunk_ids': sorted(ids)})
    used_records = set().union(*(records[cid] for cid in used))
    excluded = {cid for cid in chunks if records[cid] & used_records or
                chunks[cid]['source_product'] in EXCLUDED_PRODUCTS}
    selected, products = [], set()
    for category, kinds in [('document', {'document', 'document_part'}),
                            ('pr', {'pr_batch'}), ('slack', {'slack_thread_batch'})]:
        candidates = sorted((cid for cid, c in chunks.items() if cid not in excluded and
                             c['source_kind'] in kinds), key=lambda cid: sha(f'{SEED}|{cid}'.encode()))
        taken = 0
        for cid in candidates:
            product = chunks[cid]['source_product']
            if product in products:
                continue
            # Transitive closure prevents a neighboring batch from leaking a
            # previously read record through overlapping source ranges.
            group_records = set(records[cid])
            while True:
                members = sorted(k for k in chunks if records[k] & group_records)
                expanded = set().union(*(records[k] for k in members))
                if expanded == group_records:
                    break
                group_records = expanded
            if group_records & used_records:
                continue
            products.add(product)
            selected.append({'id': f'transfer_{category}_{taken + 1}', 'category': category,
                             'product': product, 'seed_chunk_id': cid, 'chunk_ids': members,
                             'record_keys': sorted([list(r) for r in group_records], key=str)})
            taken += 1
            if taken == 2:
                break
        if taken != 2:
            raise ValueError(f'Insufficient eligible groups: {category}')
    manifest = {'seed': SEED, 'graph_sha256': sha(GRAPH.read_bytes()),
                'protocol_sha256': sha(PROTOCOL.read_bytes()), 'selector_sha256': sha(Path(__file__).read_bytes()),
                'inventory': inventory, 'used_chunk_count': len(used), 'excluded_chunk_count': len(excluded),
                'excluded_products': sorted(EXCLUDED_PRODUCTS), 'selected': selected}
    freeze(OUT / 'selection.json', manifest)
    for group in selected:
        packet = {'group': group, 'sources': [{k: chunks[cid][k] for k in
                  ('chunkId', 'source_product', 'source_kind', 'source_text', 'source_text_sha256', 'locator')}
                  for cid in group['chunk_ids']]}
        for source in packet['sources']:
            if sha(source['source_text'].encode()) != source['source_text_sha256']:
                raise ValueError('Source export hash mismatch')
        freeze(OUT / 'source_packets' / (group['id'] + '.json'), packet)
    print(json.dumps({'groups': [{k: g[k] for k in ('id', 'product', 'chunk_ids')} for g in selected],
                      'inventory_files': len(inventory), 'previous_chunk_ids': len(used),
                      'excluded_chunk_count': len(excluded)}, indent=2))


if __name__ == '__main__':
    main()

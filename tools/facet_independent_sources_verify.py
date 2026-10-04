"""Verify source-only functional cases; never load rankings or facet arrays."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'output/research/2026-09-22-joint-streams/independent_sources'
SNAPSHOT = ROOT / 'output/research/2026-09-21-facet-validity/route_snapshot/graph.json'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, value):
    (BASE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    graph = read(SNAPSHOT)
    chunks = {x['chunkId']: x for x in graph['chunks']}
    edges = dict(zip(graph['edge_ids'], graph['edge_relation_ids']))
    temporal_path, specificity_path = BASE / 'temporal_graph_pairs.json', BASE / 'specificity_pairs.json'
    temporal, specificity = read(temporal_path), read(specificity_path)
    assert temporal['snapshot']['sha256'] == specificity['source_snapshot_sha256'] == sha(SNAPSHOT)
    exclusions = set(temporal['selection_protocol']['excluded_focal_source_ids'])
    checked, quote_count, relation_count = set(), 0, 0

    def source(cid, expected_hash, scope):
        actual = chunks[cid]
        assert cid not in exclusions and actual['source_product'] != 'WorkFlowGenie'
        assert hashlib.sha256(actual['source_text'].encode('utf-8')).hexdigest() == expected_hash
        assert actual['scope'] == scope
        checked.add(cid)

    questions, targets = [], []
    for s in temporal['sources']:
        source(s['source_id'], s['source_text_sha256'], s['scope'])
    for pair in temporal['pairs']:
        for quote in pair['exact_support_quotes']:
            text = chunks[quote['source_id']]['source_text']
            assert text[quote['start']:quote['end_exclusive']] == quote['exact_quote']
            quote_count += 1
        rel = pair['actual_graph_relation']
        if rel['type'] == 'shared_channel_and_product':
            for cid in pair['source_ids']:
                for kind in ('channel', 'product'):
                    assert rel[f'{kind}_node_id'] in {x['node_id'] for x in chunks[cid]['scope'][kind]}
            relation_count += 2
        else:
            a, b = [chunks[x] for x in pair['source_ids']]
            la, lb = (json.loads(x['locator']) for x in (a, b))
            assert a['relpath'] == b['relpath'] == rel['relpath']
            for key in ('parent_ref', 'id', 'index', 'field'):
                assert la[key] == lb[key] == rel['record_key'][key]
            assert la['char_range'][1] == lb['char_range'][0] == rel['touching_boundary']
            relation_count += 1
        for q in pair['raw_questions']:
            questions.append({'id': q['question_id'], 'question': q['question']})
            targets.append({'question_id': q['question_id'], 'source_group': pair['pair_id'],
                            'preferred': q.get('preferred_source_id'),
                            'comparison': q.get('comparison_source_id'),
                            'required_within_selected_pair': q.get('required_source_ids')})
    for pair in specificity['pairs']:
        for s in pair['sources'].values():
            source(s['chunkId'], s['source_text_sha256'], s['actual_graph_memberships'])
            for quote in s['supporting_quotes']:
                assert quote in chunks[s['chunkId']]['source_text']
                quote_count += 1
        for link in pair['structural_links']['actual_has_tag_links']:
            assert edges[link['edge_id']] == link['relation_id']
            relation_count += 1
        for p in pair['structural_links']['shared_product_nodes']:
            assert all(p in chunks[s['chunkId']]['scope']['product'] for s in pair['sources'].values())
            relation_count += 1
        for q in pair['questions']:
            questions.append({'id': q['id'], 'question': q['question']})
            targets.append({'question_id': q['id'], 'source_group': pair['id'],
                            'preferred': q['preferred_chunkId'], 'comparison': q['comparison_chunkId']})
    assert len(questions) == len({q['id'] for q in questions}) == 7
    write('questions.json', questions)
    write('protocol.json', {
        'status': 'source_cases_frozen_before_query_generation_or_retrieval',
        'source_snapshot_sha256': sha(SNAPSHOT),
        'case_files_sha256': {p.name: sha(p) for p in (temporal_path, specificity_path)},
        'questions_sha256': sha(BASE / 'questions.json'),
        'targets': targets,
        'validation': {'source_chunks': len(checked), 'exact_quotes': quote_count,
                       'structural_assertions': relation_count},
        'measurement_contract': [
            'Only raw questions may enter GENERATE; source preferences/quotes must never enter query capture.',
            'These four source groups are untouched checks for the next full-chain design, not weights fitted to the rejected candidate.',
            'SCORE repeats are repeated measurements, not independent relevance examples.',
            'Pair preferences are local supported contrasts, not global gold or exhaustive relevance.',
            'The complementary case requires both selected passages within this pair; equivalent support elsewhere remains possible.',
            'Assess graph contribution by controlled removal and traced paths; getting both chunks alone does not prove graph causality.',
            'Preserve all source uncertainty and rejected candidates; no target changes after outcome inspection.',
        ],
    })
    print(json.dumps({'questions': len(questions), 'source_groups': len({t['source_group'] for t in targets}),
                      'source_chunks': len(checked), 'verified_quotes': quote_count,
                      'structural_assertions': relation_count}))


if __name__ == '__main__':
    main()

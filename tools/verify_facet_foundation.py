"""Read-only verification of the original learned layer against scores and graph.

No retrieval policy, query, source body, benchmark, model call or database write.
Reports numerical identity and coverage only, not semantic validity.
"""
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'test'), str(ROOT / 'prod')]
FACETS = ('topic', 'temporal', 'why', 'activity', 'concreteness')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify():
    directory = ROOT / 'output/facet_pairs/rounds/round1'
    paths = [directory / name for name in (
        'scores.jsonl', 'overlay.json', 'model/config.json',
        'model/head.pt', 'model/standardisation.npz')]
    before = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    overlay = json.loads(paths[1].read_text(encoding='utf-8'))
    config = json.loads(paths[2].read_text(encoding='utf-8'))
    assert overlay['facets'] == list(FACETS)
    assert overlay['source_sha256'] == sha(paths[0])
    assert overlay['head_config'] == config
    assert config['topic_values_seen_by_this_head'] is False
    with paths[0].open(encoding='utf-8') as source:
        rows = [json.loads(line) for line in source if line.strip()]
    scores = {(r['tag'], r['chunk_id']): r for r in rows}
    assert len(scores) == len(rows), 'Duplicate score endpoints'
    edges = {(r['tag'], r['chunkId']): r['weights'] for r in overlay['edges']}
    assert len(edges) == len(overlay['edges']) == overlay['edge_count']
    assert edges.keys() == scores.keys(), 'Overlay/score endpoint mismatch'
    for key, values in edges.items():
        assert len(values) == 5 and values[0] is None
        assert values[1:] == [scores[key][f] for f in FACETS[1:]]
    for row in rows:
        assert all(math.isfinite(row[f]) for f in FACETS)

    from graph.db import _driver
    driver = _driver()
    try:
        with driver.session(database=overlay['database'], default_access_mode='READ') as session:
            live = session.execute_read(lambda tx: list(tx.run('''
                MATCH (t:Tag)<-[r:HAS_TAG]-(c:Chunk)
                WHERE r.run_id = $runId AND (c)-[:product]->()
                RETURN t.name AS tag, c.chunk_id AS chunk_id,
                       t.emb IS NOT NULL AS tag_vector,
                       c.desc_emb IS NOT NULL AS description_vector
            ''', runId=overlay['run_id'])))
    finally:
        driver.close()
    keys = {(r['tag'], r['chunk_id']) for r in live}
    assert keys == edges.keys(), 'Live graph/overlay endpoint mismatch'
    assert len(live) == len(keys), 'Duplicate live endpoints'
    assert all(r['tag_vector'] and r['description_vector'] for r in live)
    assert before == {str(p.relative_to(ROOT)): sha(p) for p in paths}
    return {
        'purpose': 'Original learned measurement integrity, not retrieval or quality evaluation',
        'database': overlay['database'], 'run_id': overlay['run_id'],
        'edges': len(edges), 'chunks': len({k[1] for k in edges}),
        'tags': len({k[0] for k in edges}),
        'exact_score_to_overlay_auxiliary_values': len(edges) * 4,
        'live_graph_endpoints_equal': True,
        'live_topic_vector_endpoints_present': True,
        'topic_overlay_null_count': len(edges),
        'learned_topic_preserved_in_scores': True,
        'raw_head_values': {f: {
            'min': min(r[f] for r in rows), 'max': max(r[f] for r in rows),
            'distinct': len({r[f] for r in rows})} for f in FACETS},
        'source_sha256_before_and_after': before,
        'retrieval_formula': None,
        'query_graph_scale_alignment_established': False,
        'model_calls': 0, 'db_writes': 0,
    }


if __name__ == '__main__':
    result = verify()
    target = ROOT / 'output/research/2026-09-25-facet-foundation/verification.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))

"""Exercise original-question interpretation into uncollapsed graph evidence.

Uses one existing private query capture, reads graph vectors and learned edges,
and writes private evidence arrays. Does not rank, resolve sources, or read gold.
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from dataclasses import asdict
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'test'), str(ROOT/'prod')]
from artefact import query_content as Q
from artefact import learned_relations as L
from arms import artefact_facet_joint as transport
from graph.db import _driver


def main():
    out = ROOT/'output/research/2026-09-25-query-content'
    out.mkdir(parents=True, exist_ok=True)
    # The first existing case is fixed before any new result. Only its question
    # is passed to interpretation; previous tags/readings/description are unused.
    source = ROOT/'output/research/2026-09-24-interpretation-comparison/private/case_001.json'
    question = json.loads(source.read_text(encoding='utf-8'))['question']
    system, user = Q.request(question)
    parsed, usage, cache = transport._cached_stage(
        'question_content', system, user,
        lambda raw: asdict(Q.parse(question, raw)),
        ROOT/'output/private/query_content_cache')
    query = Q.QueryContent(parsed['question'], parsed['description'],
                          tuple(Q.QueryTag(t['text'], tuple(t['readings'])) for t in parsed['tags']))
    print('Interpretation available; loading graph measurements.', flush=True)
    learned = L.load(ROOT/'output/facet_pairs/rounds/round1')
    driver = _driver()
    try:
        with driver.session(database='herb-eval-volmax', default_access_mode='READ') as session:
            tag_rows = session.execute_read(lambda tx: list(tx.run('''
                MATCH (t:Tag) WHERE t.emb IS NOT NULL AND EXISTS {
                    MATCH (t)<-[r:HAS_TAG]-(c:Chunk)
                    WHERE r.run_id = $run AND (c)-[:product]->() }
                RETURN t.name AS id, t.emb AS vector ORDER BY id
            ''', run='pilot_full_herb')))
            chunk_rows = session.execute_read(lambda tx: list(tx.run('''
                MATCH (c:Chunk) WHERE c.desc_emb IS NOT NULL AND EXISTS {
                    MATCH (c)-[r:HAS_TAG]->() WHERE r.run_id = $run }
                    AND (c)-[:product]->()
                RETURN c.chunk_id AS id, c.desc_emb AS vector ORDER BY id
            ''', run='pilot_full_herb')))
    finally:
        driver.close()
    names = [r['id'] for r in tag_rows]
    ids = [r['id'] for r in chunk_rows]
    vectors = SimpleNamespace(
        tag_vectors=transport._unit(np.asarray([r['vector'] for r in tag_rows], dtype=np.float32)),
        chunk_vectors=transport._unit(np.asarray([r['vector'] for r in chunk_rows], dtype=np.float32)))
    at = {name: i for i, name in enumerate(names)}
    ci = {name: i for i, name in enumerate(ids)}
    ti = np.array([at[t] for t, c in learned.endpoints])
    ei = np.array([ci[c] for t, c in learned.endpoints])
    topic = np.einsum('ij,ij->i', vectors.tag_vectors[ti], vectors.chunk_vectors[ei])
    print('Graph measurements loaded; matching query representations.', flush=True)
    matrices, embedding_usage, recipe = transport._query_cosines(
        query.description, [t.text for t in query.tags], vectors)
    packet = L.connect(query, learned, graph_tag_names=names, chunk_ids=ids,
                       topic_cosines=topic,
                       query_tag_cosines=matrices['query_tag_cosines'],
                       query_chunk_cosines=matrices['query_chunk_cosines'],
                       description_chunk_cosines=matrices['query_description_cosines'])
    assert packet['omitted_endpoints'] == 0
    private = out/'private'; private.mkdir(exist_ok=True)
    np.savez_compressed(private/'evidence.npz',
        **{k: v for k, v in packet.items() if isinstance(v, np.ndarray)},
        raw_learned_scores=learned.raw_scores, edge_indices=np.array(packet['edge_indices']),
        query_readings=np.array([t.readings for t in query.tags]))
    (private/'identity.json').write_text(json.dumps({
        'query':asdict(query), 'edge_endpoints':learned.endpoints,
        'graph_tag_names':names, 'chunk_ids':ids}, ensure_ascii=False), encoding='utf-8')
    report = {'stage':'interpretation and evidence assembly only; no selection or evaluation',
              'fixed_case':'case_001', 'query_tags':len(query.tags),
              'learned_edges':len(learned.endpoints), 'omitted_edges':0,
              'factorized_query_edge_paths':len(query.tags)*len(learned.endpoints),
              'unchanged_learned_source_sha256':learned.source_sha256,
              'unchanged_overlay_sha256':learned.overlay_sha256,
              'interpreter_usage':asdict(usage), 'cache':cache,
              'embedding_usage':asdict(embedding_usage), 'embedding_recipe':recipe,
              'corpus_bodies_supplied':False, 'gold_read':False,
              'topic_gate':False, 'facet_average':False, 'chunk_ranking':False}
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

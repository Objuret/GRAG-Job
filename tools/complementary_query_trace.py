"""Exercise both complementary representations through the same graph matching.

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
from artefact import complementary_query as C
from artefact import learned_relations as L
from arms import artefact_facet_joint as transport
from graph.db import _driver


def main():
    out = ROOT/'output/research/2026-09-25-complementary-query'
    out.mkdir(parents=True, exist_ok=True)
    # The first existing case is fixed before any new result. Only its question
    # is passed to interpretation; previous tags/readings/description are unused.
    source = ROOT/'output/research/2026-09-24-interpretation-comparison/private/case_001.json'
    question = json.loads(source.read_text(encoding='utf-8'))['question']
    calls = []
    def call(stage, system, user, validate):
        value, usage, cache = transport._cached_stage(stage, system, user, validate,
            ROOT/'output/private/complementary_query_cache')
        calls.append({'stage': stage, 'usage': asdict(usage), 'cache': cache})
        return value
    query = C.interpret(question, call)
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
    embedding = []
    def match(text, tags):
        matrices, usage, recipe = transport._query_cosines(text, tags, vectors)
        embedding.append({'usage': asdict(usage), 'recipe': recipe})
        return matrices
    packets = C.connect_both(query, learned, match, graph_tag_names=names,
                             chunk_ids=ids, topic_cosines=topic)
    private = out/'private'; private.mkdir(exist_ok=True)
    for branch in query.branches:
        packet = packets[branch.origin]
        np.savez_compressed(private/(branch.origin+'.npz'),
            **{k:v for k,v in packet.items() if isinstance(v,np.ndarray)},
            edge_indices=np.array(packet['edge_indices']),
            query_readings=np.array([t.readings for t in branch.content.tags]))
    np.save(private/'learned_scores.npy', learned.raw_scores, allow_pickle=False)
    (private/'identity.json').write_text(json.dumps({
        'query':asdict(query), 'edge_endpoints':learned.endpoints,
        'graph_tag_names':names, 'chunk_ids':ids}, ensure_ascii=False), encoding='utf-8')
    report = {'stage':'two complementary representations through shared tag/facet and graph matching',
              'fixed_case':'case_001',
              'branches':{b.origin:{'tags':len(b.content.tags),
                  'omitted_edges':packets[b.origin]['omitted_endpoints']} for b in query.branches},
              'learned_edges':len(learned.endpoints),
              'learned_source_sha256':learned.source_sha256,
              'overlay_sha256':learned.overlay_sha256,
              'calls':calls, 'embedding':embedding,
              'same_analysis_prompt':True, 'same_matching_procedure':True,
              'corpus_bodies_supplied':False, 'gold_read':False,
              'branch_fusion_formula':None, 'chunk_ranking':False}
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

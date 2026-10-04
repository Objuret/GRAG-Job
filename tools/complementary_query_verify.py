"""Verify saved dual-branch execution without models, source bodies or gold."""
import hashlib
import json
import sys
from dataclasses import asdict
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'test'), str(ROOT/'prod')]
from artefact import complementary_query as C
from artefact import learned_relations as L


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def main():
    out = ROOT/'output/research/2026-09-25-complementary-query'
    report = read(out/'report.json')
    identity = read(out/'private/identity.json')
    calls = iter(report['calls'])
    question = read(ROOT/'output/research/2026-09-24-interpretation-comparison/private/case_001.json')['question']
    signatures = []
    def replay(stage, system, user, validate):
        stored = read(next(calls)['cache']['path'])
        signature = stored['signature']
        assert stored['ok']
        assert (signature['stage'], signature['system'], signature['user']) == (stage, system, user)
        signatures.append(signature)
        return validate(stored['raw'])
    query = C.interpret(question, replay)
    assert next(calls, None) is None
    assert json.loads(json.dumps(asdict(query))) == identity['query']
    assert signatures[0]['system'] == signatures[2]['system']
    assert signatures[0]['user'] == 'Text: ' + query.branches[0].text
    assert signatures[2]['user'] == 'Text: ' + query.branches[1].text
    learned = L.load(ROOT/'output/facet_pairs/rounds/round1')
    np.testing.assert_array_equal(np.load(out/'private/learned_scores.npy',allow_pickle=False), learned.raw_scores)
    previous_edges = None
    for branch in query.branches:
        with np.load(out/'private'/f'{branch.origin}.npz',allow_pickle=False) as arrays:
            assert arrays['tag_match'].shape == (len(branch.content.tags),len(identity['graph_tag_names']))
            assert arrays['tag_description_match'].shape == (len(branch.content.tags),len(identity['chunk_ids']))
            assert arrays['description_match'].shape == (len(identity['chunk_ids']),)
            assert all(np.isfinite(arrays[key]).all() for key in arrays.files)
            np.testing.assert_array_equal(arrays['query_readings'],[t.readings for t in branch.content.tags])
            edges = arrays['edge_indices']
            assert len(edges) == len(learned.endpoints)
            for i,t,c in edges:
                assert learned.endpoints[i] == (identity['graph_tag_names'][t],identity['chunk_ids'][c])
            if previous_edges is not None:
                np.testing.assert_array_equal(edges,previous_edges)
            previous_edges = edges.copy()
    sources = ['test/artefact/complementary_query.py','test/artefact/query_content.py',
               'test/artefact/learned_relations.py','tools/complementary_query_trace.py',
               'tools/complementary_query_verify.py','test/tests/test_complementary_query.py']
    result = {'both_representations_executed':True,'same_analysis_request':True,
              'original_branch_received_original_question_only':True,
              'interpreted_branch_received_description_only':True,
              'both_have_whole_text_and_tag_matching':True,
              'both_retain_all_learned_edges_and_query_readings':True,
              'original_learned_values_unchanged':True,
              'ranking_or_answer_quality_tested':False,
              'source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}}
    (out/'verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()

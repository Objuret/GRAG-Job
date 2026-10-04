"""One explicit input intervention: existing learned topic replaces cosine topic.

The previously frozen independent-source replay supplies every other operator.
This is an exploratory full-chain comparison on already inspected cases, not a
new heldout evaluation or a production change.
"""
from pathlib import Path
import json
import os
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[name]='4'
import numpy as np
import facet_independent_envelope as replay

ROOT=replay.ROOT
BASE=replay.BASE
OUT=BASE/'learned_topic_envelope'
SCORES=ROOT/'output/facet_pairs/rounds/round1/scores.jsonl'


def main():
    if OUT.exists() and any(OUT.iterdir()):
        raise RuntimeError('Refusing to overwrite learned-topic comparison')
    graph=replay.read(replay.STATIC/'graph.json')
    with np.load(replay.STATIC/'arrays.npz') as data:
        arrays={k:data[k] for k in data.files}
    old=arrays['edge_facets']
    topic={}
    with SCORES.open(encoding='utf-8') as stream:
        for line in stream:
            row=json.loads(line)
            assert row['edge_id']==row['chunk_id']+'::'+row['tag']
            assert row['edge_id'] not in topic
            topic[row['edge_id']]=float(row['topic'])
    values=np.array([topic[e] for e in graph['edge_ids']])
    assert np.isfinite(values).all() and len(values)==57204
    effective=old.copy();effective[:,0]=values
    assert np.array_equal(effective[:,1:],old[:,1:])
    arrays['edge_facets']=effective
    paths=[Path(__file__),Path(replay.__file__),SCORES,
           ROOT/'output/facet_pairs/rounds/round1/model/config.json',
           ROOT/'output/research/2026-09-22-topic-validation/HEAD_PROVENANCE.md',
           BASE/'LEARNED_TOPIC_COMPARISON.md']
    hashes={str(p.relative_to(ROOT)):replay.sha(p) for p in paths}
    contract={'purpose':__doc__,'input_sha256':hashes,
        'changed':'Semantic HAS_TAG edge topic values only: cached fixed round1 learned topic, aligned by exact edge ID.',
        'reference':'Rebuild the topic empirical midrank CDF over all57204 semantic edges from the replacement values. Four auxiliary reference columns stay identical.',
        'unchanged':'All query captures/embeddings/weights, graph topology, lookup vectors, D and Q description links, four auxiliary edge columns, coefficients, hop discount, facet/path aggregation, candidate population and three controls.',
        'learned_head':'Tag/full-chunk ModernBERT frozen features with linear teacher-comparison heads; no retraining. See HEAD_PROVENANCE.md.',
        'case_status':'Already inspected source cases; exploratory development comparison, not a heldout performance claim.',
        'no_model_or_db_calls':True,'source_manifest_note':'Base runner hashes original files. This contract explicitly replaces the effective edge_facets input in memory and records its saved matrix hash.'}
    original_load,original_write,original_out=replay.np.load,replay.write,replay.OUT
    # The base runner requires an empty destination. Persist effective inputs only
    # when it writes its protocol, after it has validated query/static alignment.
    def load(path,*args,**kwargs):
        if isinstance(path,(str,Path)) and Path(path)==replay.STATIC/'arrays.npz':
            return arrays
        return original_load(path,*args,**kwargs)
    def write(path,body):
        path=Path(path)
        if path==OUT/'protocol.json':
            np.save(OUT/'effective_edge_facets.npy',effective)
            contract['effective_edge_facets_sha256']=replay.sha(OUT/'effective_edge_facets.npy')
            original_write(OUT/'adapter_contract.json',contract)
            body={**body,'topic_input_intervention':contract,
                  'adapter_contract_sha256':replay.sha(OUT/'adapter_contract.json')}
        original_write(path,body)
    replay.np.load,replay.write,replay.OUT=load,write,OUT
    try:
        replay.main()
    finally:
        replay.np.load,replay.write,replay.OUT=original_load,original_write,original_out
    assert all(replay.sha(ROOT/p)==h for p,h in hashes.items())
    assert np.array_equal(np.load(OUT/'effective_edge_facets.npy'),effective)
    print('Learned-topic intervention complete; all other inputs/operators unchanged',flush=True)


if __name__=='__main__':
    main()

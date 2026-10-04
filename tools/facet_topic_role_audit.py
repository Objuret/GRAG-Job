"""Same-runtime role audit on every graph tag of the two diagnostic chunks.

No ranks, coefficients, CDF fitting, graph mutation or generated text.
"""
from pathlib import Path
import numpy as np
from facet_description_intervention import ROOT, STATIC, BASE, IDS, read, write, sha, unit

OUT = BASE / 'topic_role_audit'


def main():
    if OUT.exists() and any(OUT.iterdir()):
        raise RuntimeError('Refusing to overwrite role audit')
    graph = read(STATIC / 'graph.json')
    static = dict(np.load(STATIC / 'arrays.npz'))
    raw = dict(np.load(STATIC / 'graph_vectors.npz'))
    representations = np.load(BASE / 'description_intervention/vectors.npz')['encoded']
    previous = read(BASE / 'description_intervention/protocol.json')
    for p,h in previous['input_sha256'].items():
        assert sha(ROOT/p) == h
    at = [graph['chunk_ids'].index(cid) for cid in IDS]
    tags = sorted({graph['graph_tags'][t] for t in static['edge_tag'][np.isin(static['edge_chunk'], at)]})
    assert len(tags) == 34
    # Actual graph writer's readable text normalization, no query-specific rewrite.
    from graph.db import _readable
    texts = [_readable(t) for t in tags]
    sources = [Path(__file__), ROOT/'prod/harness/embed.py',ROOT/'test/graph/db.py',
        STATIC/'graph.json',STATIC/'arrays.npz',STATIC/'graph_vectors.npz',
        BASE/'description_intervention/protocol.json',BASE/'description_intervention/vectors.npz',
        BASE/'query_snapshot/queries.json',BASE/'query_snapshot/arrays.npz']
    hashes = {str(p.relative_to(ROOT)):sha(p) for p in sources}
    from harness import embed
    protocol = {'status':'frozen_before_same_runtime_role_measurement', 'input_sha256':hashes,
        'chunk_ids':IDS,'graph_tags':tags,'embedding_texts':texts,
        'selection':'All semantic graph tags attached to either of the two post-hoc diagnostic chunks; no outcome-based subset.',
        'conditions':['query','passage'],
        'representation_order':['description:durability','description:refresh','full_source:durability','full_source:refresh'],
        'measurement':'All 34 tag strings in both roles with same pinned local encoder, dot products against four previously saved local passage vectors. Compare role and text effects as raw cosines only.',
        'encoder':{'model':embed.EMBED_MODEL,'revision':embed.EMBED_REVISION,'prefixes':embed.EMBED_PREFIX,
                   'device':embed.EMBED_DEVICE,'dtype':embed.EMBED_DTYPE},
        'limits':'Role sensitivity is not semantic accuracy, calibrated facet relevance or a validated ranking rule. No old CDF applied to new query-role values. No graph/retrieval writes.',
        'primary_reference':'https://huggingface.co/nvidia/llama-nemotron-embed-1b-v2#model-architecture',
        'model_loads':1,'embedding_inputs':2*len(tags),'generation_calls':0,'db_calls':0}
    assert protocol['encoder']['model'] == previous['encoder']['model']
    assert protocol['encoder']['revision'] == previous['encoder']['revision']
    OUT.mkdir(parents=True)
    write(OUT/'protocol.json',protocol)
    import torch
    torch.set_num_threads(4)
    assert embed._model is None
    encoded = {}
    usage = {}
    for role in ['query','passage']:
        value,calls,tokens,_,seconds = embed._embed(texts,role,bar=False)
        encoded[role] = unit(value)
        usage[role] = {'calls':calls,'tokens':tokens,'seconds':seconds}
        print(role,'complete',flush=True)
    np.savez_compressed(OUT/'vectors.npz',**encoded)
    tag_at = {t:i for i,t in enumerate(graph['all_graph_vector_tag_names'])}
    old = unit(raw['tag_raw_float32'][[tag_at[t] for t in tags]])
    scores = {role:v@representations.T for role,v in encoded.items()}
    queries = read(BASE/'query_snapshot/queries.json')
    arrays = dict(np.load(BASE/'query_snapshot/arrays.npz'))
    controls = []
    for i,t in enumerate(tags):
        if t in queries['query_tags']:
            j = queries['query_tags'].index(t)
            controls.append({'tag':t,'maximum_saved_query_vector_difference':float(np.max(np.abs(encoded['query'][i]-arrays['query_tag_vectors'][j])))})
    rows = []
    for i,t in enumerate(tags):
        rows.append({'tag':t,'query_to_passages':scores['query'][i].tolist(),
            'passage_to_passages':scores['passage'][i].tolist(),
            'same_runtime_cross_role_cosine':float(encoded['query'][i]@encoded['passage'][i]),
            'old_vs_current_passage_cosine':float(old[i]@encoded['passage'][i])})
    assert all(sha(ROOT/p)==h for p,h in hashes.items())
    write(OUT/'results.json',{'rows':rows,'query_controls':controls,'usage':usage,
          'representation_order':protocol['representation_order']})
    write(OUT/'verification.json',{'inputs_unchanged':True,'tag_count':len(tags),
          'finite':all(np.isfinite(v).all() for v in scores.values()),
          'saved_query_controls_within_1e_5':all(c['maximum_saved_query_vector_difference']<=1e-5 for c in controls),
          'results_sha256':sha(OUT/'results.json'),'vectors_sha256':sha(OUT/'vectors.npz')})
    for r in rows:
        if r['tag'] in ['message persistence','data durability','AI models','AI Model Deployment','retraining pipeline']:
            print(r,flush=True)


if __name__=='__main__':
    main()

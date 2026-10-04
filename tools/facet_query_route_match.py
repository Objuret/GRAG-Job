"""Match every generated diagnostic query tag against the live semantic Tag vocabulary.

Use the serving embedder's pinned query prefix and normalized cosine. Save the
complete score matrix: displayed neighbors are summaries, not a retrieval cutoff.
Inspect source-chunk adjacency without replacing the production graph walk.
"""
from pathlib import Path
from datetime import datetime,timezone
import argparse
import hashlib
import json
import os
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'prod'),str(ROOT/'test')]

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--source',type=Path,required=True);args=ap.parse_args();p=args.source
    m=json.loads((p/'manifest.json').read_text());readings={j['id']:json.loads((p/(j['id']+'.json')).read_text())['answer'] for j in m['jobs']}
    tags=sorted({t for r in readings.values() for t in r['tags']})
    chunks=['62eecebfe117e91df15db8e3','23540be897d31a78f8ac0f39']
    from graph.db import _driver
    with _driver() as driver:
        with driver.session(database='herb-eval-volmax',default_access_mode='READ') as session:
            products={r['name'].casefold() for r in session.run('MATCH (p:Product) RETURN p.name AS name') if r['name']}
            graph=[dict(r) for r in session.run('MATCH (t:Tag) RETURN t.name AS name,t.emb AS vector')]
            edges=[dict(r) for r in session.run('MATCH (c:Chunk)-[:HAS_TAG]->(t:Tag) WHERE c.chunk_id IN $ids RETURN c.chunk_id AS chunk,t.name AS tag',ids=chunks)]
    graph=sorted([r for r in graph if r['name'].casefold() not in products],key=lambda r:r['name'])
    names=[r['name'] for r in graph]
    if len(set(names))!=len(names):raise ValueError('Tag names are not unique')
    vectors=np.array([r['vector'] for r in graph],dtype=np.float64)
    if vectors.shape!=(len(graph),2048) or not np.isfinite(vectors).all() or (np.linalg.norm(vectors,axis=1)==0).any():raise ValueError('Invalid tag vectors')
    original_hash=hashlib.sha256(vectors.tobytes()).hexdigest()
    vectors/=np.linalg.norm(vectors,axis=1,keepdims=True)
    graph.clear()
    os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
    import torch
    torch.set_num_threads(4)
    from harness.embed import _embed,EMBED_MODEL,EMBED_REVISION
    q,_,tokens,_,seconds=_embed(tags,'query',bar=False)
    q=q.astype(np.float64);q/=np.linalg.norm(q,axis=1,keepdims=True)
    similarities=q@vectors.T
    np.savez_compressed(p/'tag_matching_scores.npz',scores=similarities,query_vectors=q)
    index={name:i for i,name in enumerate(names)}
    adjacency={cid:[index[e['tag']] for e in edges if e['chunk']==cid and e['tag'] in index] for cid in chunks}
    phrase_rows=[]
    for i,t in enumerate(tags):
        score=similarities[i];order=np.argsort(-score,kind='stable');ranks=np.empty(len(order),dtype=int);ranks[order]=np.arange(1,len(order)+1)
        best={cid:max(adjacency[cid],key=lambda k:score[k]) for cid in chunks}
        phrase_rows.append({'query_tag':t,'nearest_graph_tag':names[order[0]],'nearest_cosine':float(score[order[0]]),
            'adjacent_routes':{cid:{'graph_tag':names[k],'cosine':float(score[k]),'global_rank':int(ranks[k])} for cid,k in best.items()}})
    results=[]
    for job,r in readings.items():
        selected=[phrase_rows[tags.index(t)] for t in r['tags']]
        results.append({'reading':job,'description':r['description'],'tags':r['tags'],'phrase_matches':selected,
            'best_route_cosine_by_chunk':{cid:max(row['adjacent_routes'][cid]['cosine'] for row in selected) for cid in chunks}})
    a={'protocol':__doc__,'database':'herb-eval-volmax','created_utc':datetime.now(timezone.utc).isoformat(),
        'manifest_sha256':hashlib.sha256((p/'manifest.json').read_bytes()).hexdigest(),
        'embedding_model':EMBED_MODEL,'embedding_revision':EMBED_REVISION,'input_type':'query','tokens':tokens,'seconds':seconds,
        'graph_vector_sha256_float64_before_normalization':original_hash,'graph_tags':names,'query_tags':tags,
        'source_chunk_tag_names':{cid:[names[k] for k in ids] for cid,ids in adjacency.items()},
        'results':results,'limits':'Local tag matching and adjacency check only. Max cosine summarizes available routes; it is not asserted to be the serving chunk score. No scope pass, levels, facet weighting, walk, deduplication, or delivered evidence evaluated.'}
    (p/'route_matches.json').write_text(json.dumps(a,indent=2)+'\n',encoding='utf-8')
    print('Matched',len(tags),'generated phrases against',len(names),'semantic graph tags',flush=True)
    for r in results:
        print(r['reading'],json.dumps(r['best_route_cosine_by_chunk']))
        print(json.dumps([(x['query_tag'],x['nearest_graph_tag'],x['adjacent_routes']) for x in r['phrase_matches']]))

if __name__=='__main__':main()

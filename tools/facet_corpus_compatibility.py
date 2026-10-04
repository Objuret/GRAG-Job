"""Exploratory compatibility term using the existing retrieval instrument.

The user clarified that a report and a report-sharing record can both carry
activity; the query determines usefulness. Retain the complete sought-content
description and compare its embedding with the live stored chunk description
embedding, exactly the query-prefix/cosine link already used by the serving arm.

Test this term alone and jointly with the original query-times-facet products.
All coefficients use the same nested subject folds. This follows inspection of
the first screen, so it is exploratory, not a newly independent validation test.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

import numpy as np
from threadpoolctl import threadpool_limits

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'prod'),str(ROOT/'test'),str(ROOT/'tools')]
from artefact.facet_tradeoff import crossfit_nonnegative
from facet_tradeoff_experiment import FACETS, metrics
from facet_corpus_ordinal_analysis import reversals


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--corpus',type=Path,required=True)
    args=ap.parse_args();out=args.corpus
    manifest=json.loads((out/'manifest.json').read_text())
    sig=hashlib.sha256((out/'manifest.json').read_bytes()).hexdigest()
    cache=out/'description_compatibility.json'
    if cache.exists():
        saved=json.loads(cache.read_text())
        if saved['manifest_sha256']!=sig:
            raise RuntimeError('description compatibility cache differs')
        scores=saved['scores']
    else:
        # Avoid a surprise model download. The repo's pinned embedder must already
        # be present locally; no change to global/user environment is made.
        os.environ['HF_HUB_OFFLINE']='1'
        os.environ['TRANSFORMERS_OFFLINE']='1'
        import torch
        torch.set_num_threads(4)
        from harness.embed import _embed, EMBED_MODEL, EMBED_REVISION
        from graph.db import _driver
        chunks=[c for d in manifest['cases']['domains'] for c in d['source_chunks']]
        with _driver() as driver:
            with driver.session(database='herb-eval-volmax',default_access_mode='READ') as session:
                rows=[dict(r) for r in session.run('MATCH (c:Chunk) WHERE c.chunk_id IN $ids RETURN c.chunk_id AS id,c.desc_emb AS vector',ids=chunks)]
        if len(rows)!=len(chunks):
            raise RuntimeError('missing live chunk vectors')
        vectors={r['id']:np.array(r['vector'],dtype=float) for r in rows}
        if any(v.shape!=(2048,) or not np.isfinite(v).all() or np.linalg.norm(v)==0 for v in vectors.values()):
            raise RuntimeError('invalid live description vector')
        vector_hashes={k:hashlib.sha256(v.tobytes()).hexdigest() for k,v in vectors.items()}
        vectors={k:v/np.linalg.norm(v) for k,v in vectors.items()}
        scores={};query_vectors={};usage=[]
        for d in manifest['cases']['domains']:
            q,calls,tin,tout,seconds=_embed(d['descriptions'],'query',bar=False)
            for qi,v in enumerate(q):
                query_vectors[f"{d['id']}_{qi}"]=v.tolist()
                for i,cid in enumerate(d['source_chunks']):
                    scores[f"{d['id']}_{qi}_{i}"]=float(v@vectors[cid])
            usage.append({'domain':d['id'],'tokens':tin,'seconds':seconds})
            print('Embedded query descriptions',d['id'],flush=True)
        saved={'protocol':__doc__,'manifest_sha256':sig,'model':EMBED_MODEL,'revision':EMBED_REVISION,
            'database':'herb-eval-volmax','scores':scores,'query_vectors':query_vectors,
            'chunk_vector_sha256_float64':vector_hashes,'usage':usage}
        cache.write_text(json.dumps(saved,indent=2)+'\n',encoding='utf-8')
    analysis=json.loads((out/'analysis.json').read_text())
    cases=analysis['sources']['direct']['fitted_products']['predictions']
    y=np.array([c['y'] for c in cases]);groups=np.array([c['domain'] for c in cases])
    compatibility=np.array([scores[f"{c['domain']}_{c['qi']}_{c['a']}"]-scores[f"{c['domain']}_{c['qi']}_{c['b']}"] for c in cases])
    q=np.array([analysis['query_values'][f"{c['domain']}_{c['qi']}"] for c in cases])
    a=json.loads((out/'graph_0.json').read_text())['answer'];b=json.loads((out/'graph_1.json').read_text())['answer']
    direct={k:np.array([np.mean([v[k][f] for v in (a,b) if k in v]) for f in FACETS]) for k in set(a)|set(b)}
    z=json.loads((out/'frozen_scores.json').read_text());frozen=dict(zip(z['keys'],np.array(z['values'])))
    live=json.loads((out/'live_topic.json').read_text())['values']
    sources={'direct':{k:np.r_[live[k],v[1:]] for k,v in direct.items()},
             'frozen':{k:np.r_[live[k],v[1:]] for k,v in frozen.items()}}
    features={'description_compatibility_only':compatibility[:,None]}
    for name,values in sources.items():
        delta=np.array([values[f"{c['domain']}_{c['a']}"]-values[f"{c['domain']}_{c['b']}"] for c in cases])
        features['compatibility_plus_'+name+'_products']=np.column_stack([compatibility,q*delta])
    result={'protocol':__doc__,'methods':{}}
    for name,x in features.items():
        fitted=crossfit_nonnegative(x,y,groups,penalties=[.001,.01,.1,1.])
        result['methods'][name]={'metrics':metrics(fitted['probabilities'],y,fitted['gap'],np.ones(len(y))),
            **reversals(cases,fitted['gap']),'folds':fitted['folds'],
            'predictions':[{**c,'gap':float(fitted['gap'][i]),'probabilities':fitted['probabilities'][i].tolist()} for i,c in enumerate(cases)]}
    (out/'compatibility_analysis.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({name:{k:v for k,v in r.items() if k not in ('predictions','folds')} for name,r in result['methods'].items()},indent=2))


if __name__=='__main__':
    with threadpool_limits(limits=1):
        main()

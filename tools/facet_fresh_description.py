"""Frozen existing description-cosine baseline for the fresh corpus screen."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'prod'),str(ROOT/'test')]

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--source',type=Path,required=True)
    args=ap.parse_args();p=args.source;manifest=json.loads((p/'manifest.json').read_text())
    sig=hashlib.sha256((p/'manifest.json').read_bytes()).hexdigest();cache=p/'description_baseline.json'
    if cache.exists():
        if json.loads(cache.read_text())['manifest_sha256']!=sig:raise ValueError('Description baseline inputs changed')
        print('Using saved description baseline');return
    os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
    import torch
    torch.set_num_threads(4)
    from harness.embed import _embed,EMBED_MODEL,EMBED_REVISION
    from graph.db import _driver
    ids=[cid for d in manifest['cases']['domains'] for cid in d['source_chunks']]
    with _driver() as driver:
        with driver.session(database='herb-eval-volmax',default_access_mode='READ') as session:
            rows=[dict(r) for r in session.run('MATCH (c:Chunk) WHERE c.chunk_id IN $ids RETURN c.chunk_id AS id,c.desc_emb AS vector',ids=ids)]
    if len(rows)!=len(ids):raise ValueError('Missing live description vectors')
    vectors={r['id']:np.array(r['vector'],dtype=float) for r in rows}
    if any(v.shape!=(2048,) or not np.isfinite(v).all() or np.linalg.norm(v)==0 for v in vectors.values()):raise ValueError('Invalid live vector')
    hashes={k:hashlib.sha256(v.tobytes()).hexdigest() for k,v in vectors.items()}
    vectors={k:v/np.linalg.norm(v) for k,v in vectors.items()};scores={};usage=[]
    for d in manifest['cases']['domains']:
        q,calls,tin,tout,seconds=_embed(d['descriptions'],'query',bar=False)
        for qi,v in enumerate(q):
            for ti,cid in enumerate(d['source_chunks']):scores[f"{d['id']}_{qi}_{ti}"]=float(v@vectors[cid])
        usage.append({'domain':d['id'],'tokens':tin,'seconds':seconds});print('Embedded',d['id'],flush=True)
    cache.write_text(json.dumps({'protocol':__doc__,'manifest_sha256':sig,'model':EMBED_MODEL,'revision':EMBED_REVISION,
        'database':'herb-eval-volmax','vector_sha256_float64':hashes,'scores':scores,'usage':usage},indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':main()

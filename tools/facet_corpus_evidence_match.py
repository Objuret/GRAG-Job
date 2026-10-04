"""Exploratory query-to-facet-evidence compatibility, with no new judge calls.

Use exact quotations already collected without queries or retrieval preferences.
Mean cosine over distinct nonempty quotes per relationship/facet; empty evidence
gets zero. Compare pooled evidence, equal query-weighted evidence, and five fitted
query-weighted evidence terms. Preserve both orientation readings, deduplicating
identical quotes. This is a post-hoc diagnostic on eight previously inspected
groups, not validation. Quotes were extracted in pairs and may omit context;
candidate independence and evidence sufficiency are not established.
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

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'prod'), str(ROOT/'test'), str(ROOT/'tools')]
from artefact.facet_tradeoff import crossfit_nonnegative
from facet_tradeoff_experiment import FACETS, metrics
from facet_corpus_ordinal_analysis import reversals


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--corpus', type=Path, required=True)
    ap.add_argument('--ordinal', type=Path, required=True)
    args = ap.parse_args()
    source = json.loads((args.corpus/'manifest.json').read_text())
    ordinal = json.loads((args.ordinal/'manifest.json').read_text())
    quotes = {}
    for job in ordinal['jobs']:
        if job['variant'] != 'evidence':
            continue
        answers = json.loads((args.ordinal/(job['id']+'.json')).read_text())['answer']
        for d in source['cases']['domains']:
            for side, idx in zip(('A', 'B'), job['orientation_not_sent'][d['id']]):
                for facet in FACETS:
                    quote = answers[d['id']][facet]['quote_'+side]
                    if quote not in d['texts'][idx]:
                        raise ValueError('Evidence is not an exact substring')
                    bucket = quotes.setdefault(f"{d['id']}_{idx}_{facet}", set())
                    if quote:
                        bucket.add(quote)
    quotes = {k: sorted(v) for k,v in sorted(quotes.items())}
    inputs = {'protocol': __doc__, 'quotes': quotes,
              'query_cache_sha256': hashlib.sha256((args.corpus/'description_compatibility.json').read_bytes()).hexdigest()}
    path = args.corpus/'evidence_match_manifest.json'
    if path.exists() and json.loads(path.read_text()) != inputs:
        raise ValueError('Evidence match inputs changed')
    path.write_text(json.dumps(inputs, indent=2)+'\n', encoding='utf-8')
    sig = hashlib.sha256(path.read_bytes()).hexdigest()
    cache = args.corpus/'evidence_match_embeddings.json'
    if cache.exists():
        saved = json.loads(cache.read_text())
        if saved['manifest_sha256'] != sig:
            raise ValueError('Evidence embedding inputs changed')
        vectors = {k: np.array(v) for k,v in saved['vectors'].items()}
    else:
        os.environ['HF_HUB_OFFLINE'] = '1'
        os.environ['TRANSFORMERS_OFFLINE'] = '1'
        import torch
        torch.set_num_threads(4)
        from harness.embed import _embed, EMBED_MODEL, EMBED_REVISION
        unique = sorted({s for bucket in quotes.values() for s in bucket})
        vectors = {}; usage = []
        for start in range(0, len(unique), 16):
            batch = unique[start:start+16]
            values, calls, tin, tout, secs = _embed(batch, 'passage', bar=False)
            vectors.update(zip(batch, values))
            usage.append({'tokens': tin, 'seconds': secs})
            print('Embedded evidence', start+len(batch), '/', len(unique), flush=True)
        cache.write_text(json.dumps({'manifest_sha256': sig, 'model': EMBED_MODEL,
            'revision': EMBED_REVISION, 'usage': usage,
            'vectors': {k:v.tolist() for k,v in vectors.items()}}, indent=2)+'\n', encoding='utf-8')
    query_vectors = json.loads((args.corpus/'description_compatibility.json').read_text())['query_vectors']
    score = {}; pooled = {}
    for d in source['cases']['domains']:
        for qi in range(len(d['descriptions'])):
            qv = np.array(query_vectors[f"{d['id']}_{qi}"])
            for idx in range(len(d['texts'])):
                key = f"{d['id']}_{qi}_{idx}"
                score[key] = []
                all_quotes = set()
                for facet in FACETS:
                    bucket = quotes[f"{d['id']}_{idx}_{facet}"]
                    score[key].append(float(np.mean([qv@vectors[s] for s in bucket])) if bucket else 0.)
                    all_quotes.update(bucket)
                pooled[key] = float(np.mean([qv@vectors[s] for s in sorted(all_quotes)])) if all_quotes else 0.
    analysis = json.loads((args.corpus/'analysis.json').read_text())
    cases = analysis['sources']['direct']['fitted_products']['predictions']
    y = np.array([c['y'] for c in cases]); groups = np.array([c['domain'] for c in cases])
    q = np.array([analysis['query_values'][f"{c['domain']}_{c['qi']}"] for c in cases])
    delta = []; pooled_delta = []
    for c in cases:
        a,b = [f"{c['domain']}_{c['qi']}_{c[side]}" for side in ('a','b')]
        delta.append(np.array(score[a])-score[b]); pooled_delta.append(pooled[a]-pooled[b])
    product = q*np.array(delta)
    features = {'pooled_evidence': np.array(pooled_delta)[:,None],
                'equal_query_products': product.sum(axis=1)[:,None],
                'fitted_query_products': product}
    result = {'protocol': __doc__, 'facet_compatibility': score, 'methods': {}}
    for name,x in features.items():
        fitted = crossfit_nonnegative(x,y,groups,penalties=[.001,.01,.1,1.])
        result['methods'][name] = {'metrics': metrics(fitted['probabilities'],y,fitted['gap'],np.ones(len(y))),
            **reversals(cases,fitted['gap']), 'folds': fitted['folds'],
            'predictions': [{**c,'gap': float(fitted['gap'][i]),'probabilities': fitted['probabilities'][i].tolist()} for i,c in enumerate(cases)]}
    (args.corpus/'evidence_match_analysis.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({name:{k:v for k,v in r.items() if k not in ('predictions','folds')} for name,r in result['methods'].items()},indent=2))


if __name__ == '__main__':
    with threadpool_limits(limits=1):
        main()

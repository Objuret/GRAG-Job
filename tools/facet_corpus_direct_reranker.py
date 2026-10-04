"""Post-hoc positive-control baseline using the pinned backbone's native head.

Score the complete sought-content description against the actual passage. This
does not use or replace the facet method: it checks whether the same backbone can
retain useful query-conditioned information discarded by scalar edge facets.
No corpus benchmark question or answer key is read. Scores are frozen before
fitting a nonnegative slope/tie parameter in the same nested subject-group folds.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import torch
from transformers import AutoConfig, AutoModelForSequenceClassification, AutoTokenizer
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'prod'),str(ROOT/'test'),str(ROOT/'tools')]
from artefact.facet_tradeoff import crossfit_nonnegative
from facet_tradeoff_experiment import metrics


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--corpus',type=Path,required=True)
    args=ap.parse_args()
    out=args.corpus
    manifest=json.loads((out/'manifest.json').read_text())
    config=json.loads((ROOT/'output/facet_pairs/rounds/round1/model/config.json').read_text())
    name,revision=config['backbone'],config['cache_meta']['revision']
    cache=out/'native_reranker_scores.json'
    sig=hashlib.sha256((out/'manifest.json').read_bytes()).hexdigest()
    if cache.exists():
        saved=json.loads(cache.read_text())
        if saved['manifest_sha256'] != sig or saved['revision'] != revision:
            raise RuntimeError('native score cache differs')
        scores=saved['scores']
    else:
        torch.set_num_threads(4)
        cfg=AutoConfig.from_pretrained(name,revision=revision,local_files_only=True,trust_remote_code=False)
        cfg.reference_compile=False
        model=AutoModelForSequenceClassification.from_pretrained(name,revision=revision,config=cfg,
            local_files_only=True,trust_remote_code=False,attn_implementation='sdpa').float().eval()
        tok=AutoTokenizer.from_pretrained(name,revision=revision,local_files_only=True)
        scores={}
        for d in manifest['cases']['domains']:
            for qi,q in enumerate(d['descriptions']):
                for i,text in enumerate(d['texts']):
                    enc=tok(q,text,return_tensors='pt',truncation='only_second',max_length=1694)
                    with torch.no_grad():
                        logit=float(model(**enc).logits[0,0])
                    scores[f"{d['id']}_{qi}_{i}"]=logit
            print('Encoded native query-passage pairs',d['id'],flush=True)
        cache.write_text(json.dumps({'protocol':__doc__,'manifest_sha256':sig,'model':name,
            'revision':revision,'scores':scores},indent=2)+'\n',encoding='utf-8')
    analysis=json.loads((out/'analysis.json').read_text())
    cases=analysis['sources']['direct']['fitted_products']['predictions']
    y=np.array([c['y'] for c in cases])
    groups=np.array([c['domain'] for c in cases])
    gap=np.array([scores[f"{c['domain']}_{c['qi']}_{c['a']}"]-scores[f"{c['domain']}_{c['qi']}_{c['b']}"] for c in cases])
    fitted=crossfit_nonnegative(gap[:,None],y,groups,penalties=[.001,.01,.1,1.])
    result={'protocol':__doc__,'metrics':metrics(fitted['probabilities'],y,fitted['gap'],np.ones(len(y))),
            'folds':fitted['folds'],'raw_direction_agreement':float((((gap>0)&(y==0))|((gap<0)&(y==1)))[y<2].mean()),
            'predictions':[{**c,'native_raw_gap':float(gap[i]),'gap':float(fitted['gap'][i]),
                'probabilities':fitted['probabilities'][i].tolist()} for i,c in enumerate(cases)]}
    (out/'native_reranker_analysis.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('predictions','protocol')},indent=2))


if __name__=='__main__':
    with threadpool_limits(limits=1):
        main()

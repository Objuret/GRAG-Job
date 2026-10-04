"""No-model parity for the experimental fixed-program arm on captured readings."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from arms import artefact_facet_program as A
from arms.artefact_v2 import _budget_contexts

ROOT=A.ROOT
INPUTS=ROOT/'output/research/2026-09-22-retrieval-matrix/inputs'
RESULTS=ROOT/'output/research/2026-09-24-tag-frontier-programs'


def check(limit=None,delivery_case=None):
 prepared=A.prepare_over_corpus(ROOT/'data/corpus/Salesforce__HERB')
 ids=prepared.graph.chunk_ids
 manifest=json.loads((INPUTS/'cases_manifest.json').read_text())
 cases=manifest['cases'] if limit is None else manifest['cases'][:limit]
 checked=0;delivery=None
 for record in cases:
  cid=record['case_id'];meta=json.loads((INPUTS/record['meta']).read_text())
  numeric=INPUTS/record['npz']
  if hashlib.sha256(numeric.read_bytes()).hexdigest()!=meta['npz_sha256']:
   raise ValueError('Frozen query readings changed')
  with np.load(numeric,allow_pickle=False) as data:
   matrices={name:data[name].copy() for name in ('query_tag_cosines','query_chunk_cosines','query_description_cosines')}
   weights=data['query_facet_weights'].copy()
  members=meta['area']['chunk_ids']
  area=None if members is None else np.array([item in set(members) for item in ids])
  result,_=A.rank_numeric(prepared,matrices,weights,area)
  saved=json.loads((RESULTS/'cases'/(cid+'.json')).read_text())
  expected=next(row for row in saved if row['program_id']==A.SELECTED_ID)
  digest=hashlib.sha256(result['order'].tobytes()).hexdigest()
  if digest!=expected['order_sha256']:raise AssertionError('Full-order mismatch: '+cid)
  checked+=1
  if cid==delivery_case:
   order=[ids[i] for i in result['order']]
   at={chunk['chunkId']:chunk for chunk in prepared.base.chunks}
   contexts,source_lists,source_ids,budget=_budget_contexts([at[item] for item in order],72000,{})
   if order[:budget['kept']]!=expected['full_chunk_ids'] or budget!=expected['budget']:
    raise AssertionError('Actual resolved 72k delivery mismatch: '+cid)
   delivery={'case_id':cid,'full_chunks':budget['kept'],'contexts_including_partial':len(contexts),
             'credited_source_ids':len(source_ids),'budget_equal':True}
 return {'numeric_full_order_cases':checked,'actual_delivery':delivery,
         'model_calls':0,'gold_input_to_retrieval':False}


if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--limit-cases',type=int)
 ap.add_argument('--delivery-case',default='case_001')
 a=ap.parse_args();print(json.dumps(check(a.limit_cases,a.delivery_case)))

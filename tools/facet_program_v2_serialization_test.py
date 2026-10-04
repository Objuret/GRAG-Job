"""No-model end-to-end serialization and delivery parity for the v2 adapter."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
from arms import artefact_facet_program_v2 as arm
from harness.contract import ModelUsage


ROOT=Path(__file__).resolve().parents[1]
INPUTS=ROOT/'output/research/2026-09-22-retrieval-matrix/inputs'
RESULTS=ROOT/'output/research/2026-09-24-tag-frontier-programs/cases'


def read(path):return json.loads(path.read_text(encoding='utf-8'))


def main():
    cases=read(INPUTS/'cases_manifest.json')['cases']
    selected=next(case for case in cases[:10]
                  if read(INPUTS/case['meta'])['area']['chunk_ids'] is not None)
    cid=selected['case_id'];qid=selected['question_id']
    raw=next(row['question'] for row in
             (json.loads(line) for line in (ROOT/'data/questions.jsonl').open(encoding='utf-8'))
             if row['id']==qid)
    prepared=arm.prepare_over_corpus(ROOT/'data/corpus/Salesforce__HERB')
    with np.load(INPUTS/selected['npz'],allow_pickle=False) as saved:
        matrices={name:saved[name].copy() for name in
                  ('query_tag_cosines','query_chunk_cosines','query_description_cosines')}
        weights=saved['query_facet_weights'].copy()
    fake_interpret=({'description':'private test placeholder','tags':[]},weights,
                    ModelUsage(),{'model':'no-model-test','stages':[]})
    fake_cosines=(matrices,ModelUsage(),{'vector_sha256':'captured-only'})
    with patch.object(arm.original.joint,'_interpret',return_value=fake_interpret),\
         patch.object(arm.original.joint,'_query_cosines',return_value=fake_cosines):
        out=arm.answer_one_question((qid,raw),prepared,lambda question,contexts:'test answer',
                                    char_budget=72000)
    encoded=json.dumps(asdict(out),ensure_ascii=False,allow_nan=False)
    expected=next(row for row in read(RESULTS/(cid+'.json'))
                  if row['program_id']==arm.original.SELECTED_ID)
    assert isinstance(out.meta['area']['chunk_ids'],list)
    assert out.meta['ranking']['order_sha256']==expected['order_sha256']
    assert out.meta['char_budget']==expected['budget']
    assert out.meta['delivered_chunk_ids'][:expected['budget']['kept']]==expected['full_chunk_ids']
    assert len(out.context_ids)==expected['retrieved_ids']
    print(json.dumps({'case_id':cid,'area_list_serialized':True,
                      'json_bytes':len(encoded.encode('utf-8')),
                      'order_equal':True,'budget_equal':True,'source_credit_count_equal':True,
                      'model_calls':0,'gold_read':False}))


if __name__=='__main__':main()

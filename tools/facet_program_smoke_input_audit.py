"""Private no-model audit of the ten raw-query inputs for the fixed program.

Only aggregate counts and opaque case IDs leave this process. Query, cache,
source, answer, and gold contents are never printed or exported.
"""
import hashlib
import json
from pathlib import Path

import numpy as np
from arms import artefact_facet_program as A
from artefact import querytagger_split_check as S
from artefact.facet_joint_candidate import FACETS
from artefact.facet_structural_landing import resolve_structural_area


ROOT=A.ROOT
INPUTS=ROOT/'output/research/2026-09-22-retrieval-matrix/inputs'
RESULTS=ROOT/'output/research/2026-09-24-tag-frontier-programs/cases'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def cached(stage, system, user, validator, directory):
    signature={'cache_version':1,'stage':stage,'model':A.joint.INTERPRET_MODEL,
               'system':system,'user':user,'max_tries':1}
    key=hashlib.sha256(json.dumps(signature,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    path=directory/stage/(key+'.json')
    if not path.is_file(): return None,'missing'
    data=read(path)
    if data.get('signature')!=signature:return None,'signature_mismatch'
    if not data.get('ok'):return None,'failed'
    try:return validator(data['raw']),'ok'
    except Exception:return None,'invalid'


def audit():
    prepared=A.prepare_over_corpus(ROOT/'data/corpus/Salesforce__HERB')
    manifest=read(INPUTS/'cases_manifest.json')
    cases=[r for r in manifest['cases'] if r['cohort']=='smoke10']
    assert len(cases)==10
    questions={row['id']:row['question'] for row in
               (json.loads(line) for line in (ROOT/'data/questions.jsonl').open(encoding='utf-8'))
               if row['id'] in {case['question_id'] for case in cases}}
    assert len(questions)==10
    report={'cases':10,'raw_scope_different':0,'full_order_different_from_saved_scope':0,
            'first_72k_full_chunks_different':0,'interpreter_source_record_different':0,
            'weights_different_from_saved_numeric':0,'cache_status':{},
            'scope_different_case_ids':[],'order_different_case_ids':[],
            'interpreter_different_case_ids':[],'model_calls':0,'gold_read':False}
    source_cache={}
    for row in cases:
        cid=row['case_id'];qid=row['question_id'];raw=questions[qid]
        meta=read(INPUTS/row['meta'])
        current_area,_=resolve_structural_area(raw,prepared.base.structural_index)
        saved_area=meta['area']['chunk_ids']
        different=(None if current_area is None else set(current_area)) != (None if saved_area is None else set(saved_area))
        if different:
            report['raw_scope_different']+=1;report['scope_different_case_ids'].append(cid)
        source=ROOT/meta['source_file']
        if source not in source_cache:
            source_cache[source]={r['id']:r for r in
                                  (json.loads(line) for line in source.open(encoding='utf-8'))}
        old=source_cache[source][qid]
        if old['question']!=raw:
            report['interpreter_source_record_different']+=1
            report['interpreter_different_case_ids'].append(cid)
        system,user=S.generate_prompt(raw)
        generation,status=cached('generate',system,user,S.parse_generate,prepared.base.cache_dir)
        report['cache_status']['generate_'+status]=report['cache_status'].get('generate_'+status,0)+1
        if generation is not None:
            system,user=S.score_prompt(generation['description'],generation['tags'])
            scores,status=cached('score',system,user,
                                 lambda x:S.parse_score(x,generation['tags']),prepared.base.cache_dir)
            report['cache_status']['score_'+status]=report['cache_status'].get('score_'+status,0)+1
            if scores is not None:
                stored=old['meta']['interpreter']
                if (stored['description']!=generation['description'] or
                    [r['t'] for r in stored['tags']]!=generation['tags'] or
                    stored['tags']!=scores['tags']):
                    report['interpreter_source_record_different']+=1
                    report['interpreter_different_case_ids'].append(cid)
                weights=np.array([[entry['facets'][facet] for facet in FACETS]
                                  for entry in scores['tags']])
                with np.load(INPUTS/row['npz'],allow_pickle=False) as arrays:
                    if not np.array_equal(weights,arrays['query_facet_weights']):
                        report['weights_different_from_saved_numeric']+=1
        with np.load(INPUTS/row['npz'],allow_pickle=False) as arrays:
            matrices={k:arrays[k].copy() for k in
                      ('query_tag_cosines','query_chunk_cosines','query_description_cosines')}
            weights=arrays['query_facet_weights'].copy()
        members=None if current_area is None else set(current_area)
        area=None if members is None else np.array([x in members for x in prepared.graph.chunk_ids])
        result,_=A.rank_numeric(prepared,matrices,weights,area)
        expected=next(x for x in read(RESULTS/(cid+'.json')) if x['program_id']==A.SELECTED_ID)
        if hashlib.sha256(result['order'].tobytes()).hexdigest()!=expected['order_sha256']:
            report['full_order_different_from_saved_scope']+=1
            report['order_different_case_ids'].append(cid)
            actual=[prepared.graph.chunk_ids[i] for i in result['order'][:len(expected['full_chunk_ids'])]]
            if actual!=expected['full_chunk_ids']:
                report['first_72k_full_chunks_different']+=1
    return report


if __name__=='__main__':
    print(json.dumps(audit()))

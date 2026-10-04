"""Audit actual ten-answer retrieval against the frozen, value-only captures.

Reads private answer records mechanically but emits only counts and opaque case
IDs. Does not read gold or run interpreters, embeddings, generators, or judges.
"""
import argparse
import hashlib
import json
from pathlib import Path


ROOT=Path(__file__).resolve().parents[1]
INPUTS=ROOT/'output/research/2026-09-22-retrieval-matrix/inputs'
RESULTS=ROOT/'output/research/2026-09-24-tag-frontier-programs/cases'
UNITS=ROOT/'output/research/2026-09-22-gold-source-trace/chunk_delivery_index.json'
PROGRAM='tag_frontier_best-macro-recall_query_only_queries_all'


def read(path):return json.loads(path.read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(run):
    manifest=read(INPUTS/'cases_manifest.json')
    cases=[case for case in manifest['cases'] if case['cohort']=='smoke10']
    assert len(cases)==10
    path=run/'arm_outputs.jsonl'
    rows=[json.loads(line) for line in path.open(encoding='utf-8') if line.strip()]
    if len(rows)!=10 or not (run/'generation_completed.json').exists():
        raise RuntimeError('Generation not complete for ten answers')
    by_id={row['id']:row for row in rows}
    if len(by_id)!=10 or set(by_id)!={case['question_id'] for case in cases}:
        raise RuntimeError('Answer identities differ from fixed smoke10')
    units=read(UNITS)
    counts={key:0 for key in ('raw_question_equal','fresh_vector_sha_equal',
                              'area_equal','full_order_equal','budget_equal',
                              'complete_chunks_equal','partial_boundary_equal',
                              'source_credit_count_equal','source_credit_set_equal',
                              'partial_source_credit_rule_equal',
                              'cache_generate_hit','cache_score_hit')}
    diff=[]
    for case in cases:
        cid=case['case_id'];row=by_id[case['question_id']]
        captured=read(INPUTS/case['meta'])
        expected=next(value for value in read(RESULTS/(cid+'.json'))
                      if value['program_id']==PROGRAM)
        meta=row['meta'];budget=meta['char_budget']
        source=ROOT/captured['source_file']
        old=next(value for value in (json.loads(line) for line in source.open(encoding='utf-8'))
                 if value['id']==case['question_id'])
        flags={
          'raw_question_equal':row['question']==old['question'],
          'fresh_vector_sha_equal':meta['embedding']['vector_sha256']==captured['embedding_hash'],
          'area_equal':(None if meta['area']['chunk_ids'] is None else set(meta['area']['chunk_ids']))==
                       (None if captured['area']['chunk_ids'] is None else set(captured['area']['chunk_ids'])),
          'full_order_equal':meta['ranking']['order_sha256']==expected['order_sha256'],
          'budget_equal':budget==expected['budget'],
          'complete_chunks_equal':meta['delivered_chunk_ids'][:budget['kept']]==expected['full_chunk_ids'],
          'partial_boundary_equal':(meta['delivered_chunk_ids'][budget['kept']]
                                    if len(meta['delivered_chunk_ids'])>budget['kept'] else None)==
                                   expected['partial_chunk_id'],
          'source_credit_count_equal':len(row['context_ids'])==expected['retrieved_ids'],
          'source_credit_set_equal':set(row['context_ids'])==set().union(
              *(set(units[chunk_id]['artifact_ids']) for chunk_id in expected['full_chunk_ids'])),
          'cache_generate_hit':meta['interpreter']['stages'][0]['cache_hit'] is True,
          'cache_score_hit':meta['interpreter']['stages'][1]['cache_hit'] is True,
        }
        full=[]
        for source_ids in meta['chunk_ids'][:budget['kept']]:
            for source_id in source_ids:
                if source_id not in full:full.append(source_id)
        flags['partial_source_credit_rule_equal']=full==row['context_ids']
        for key,ok in flags.items():
            counts[key]+=bool(ok)
            if not ok:diff.append({'case_id':cid,'check':key})
    return {'schema_version':1,'kind':'postgeneration_numeric_audit',
            'run':str(run.relative_to(ROOT)),'program_id':PROGRAM,
            'cases':10,'passed_counts':counts,'differences':diff,
            'run_output_sha256':sha(path),'fixed_inputs_sha256':{
                'selected_program':sha(ROOT/'output/research/2026-09-24-real-gold-smoke/selected-program.json'),
                'captures_manifest':sha(INPUTS/'cases_manifest.json'),
                'frozen_delivery_units':sha(UNITS),
                'checker':sha(Path(__file__))},
            'model_calls':0,'gold_read':False,'question_text_exported':False,
            'interpretation_text_exported':False,'source_text_exported':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,required=True)
    args=parser.parse_args()
    run=args.run.resolve()
    if not run.is_relative_to(ROOT/'output/k=chars'):
        raise ValueError('Run must be under output/k=chars')
    result=audit(run)
    if result['differences']:
        print(json.dumps({'cases':10,'passed_counts':result['passed_counts'],
                          'differences':result['differences'],'model_calls':0,'gold_read':False}))
        raise SystemExit(1)
    out=ROOT/'output/research/2026-09-24-real-gold-smoke'/(
        'postgeneration-numeric-audit-'+run.name+'.json')
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x',encoding='utf-8') as stream:
        json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps({'postgeneration_audit':str(out.relative_to(ROOT)),
                      'cases':10,'passed_counts':result['passed_counts'],
                      'model_calls':0,'gold_read':False}))


if __name__=='__main__':main()

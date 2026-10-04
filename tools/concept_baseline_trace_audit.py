"""Reproduce saved fresh-interpreter traces and delivered contexts before judging."""
import contextlib
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'prod'),str(ROOT/'test')]
OUT=ROOT/'output/research/2026-09-24-concept-baseline'


def read(p):return json.loads(p.read_text(encoding='utf-8'))


def main():
    import numpy as np
    plan=read(OUT/'execution-plan.json')
    assert read(OUT/'generation.exit.json')['exit_code']==0
    for f,h in plan['files'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    run=ROOT/plan['run'];checks=[]
    with (OUT/'trace-audit.log').open('a',encoding='utf-8') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
        from arms import artefact_concept_baseline as A
        p=A.prepare_over_corpus(ROOT/'data/corpus/Salesforce__HERB')
        for i,line in enumerate((run/'arm_outputs.jsonl').open(encoding='utf-8'),1):
            row=json.loads(line);meta=row['meta'];interp=meta['interpreter']
            cache=read(Path(meta['interpreter_cache']['path']))
            assert cache['signature']['system']==A.INTERPRET_SYSTEM
            assert cache['signature']['user']=='Question: '+row['question']
            assert A.parse_interpretation(cache['raw'])==interp
            tags=[r['t'] for r in interp['tags']]
            weights=np.array([[r['facets'][f] for f in A.J.FACETS] for r in interp['tags']])
            matrices,usage,recipe=A.J._query_cosines(interp['description'],tags,p.base)
            assert recipe['vector_sha256']==meta['embedding']['vector_sha256']
            result=A.rank_numeric(p,row['question'],matrices,weights)
            assert [p.graph.chunk_ids[c] for c in result['order']]==meta['full_order']
            assert np.array_equal(result['scores'],meta['scores'])
            assert np.array_equal(result['direct'],meta['direct_by_query'])
            assert np.array_equal(result['graph_offer'],meta['graph_by_query'])
            assert np.array_equal(result['area_support'],meta['area_support_by_query'])
            assert result['landings']==meta['landings']
            assert set(np.flatnonzero(result['tag_candidates']))<=set(result['order'].tolist())
            rows=[p.base.chunks[c] for c in result['order']]
            contexts,ids,credited,budget=A._budget_contexts(rows,72000,{})
            assert contexts==row['contexts'] and credited==row['context_ids'] and budget==meta['char_budget']
            assert ids==meta['chunk_ids']
            checks.append({'case':i,'interpreter_question_only_input':True,'combined_prompt_exact':True,
                           'embeddings_exact':True,'full_order_exact':True,'all_saved_stages_exact':True,
                           'all_tag_candidates_retained':True,'actual_delivery_exact':True,
                           'tag_candidates':int(result['tag_candidates'].sum()),
                           'named_area_chunks':int(result['named'].sum()),
                           'structural_bindings':len(result['landings']),
                           'distinct_matched_names':len({x['name'].casefold() for x in result['landings']}),
                           'nearest_unique_bindings':sum(x['rule']=='nearest-unique' for x in result['landings']),
                           'fully_delivered_chunks':budget['kept'],
                           'graph_support_chunks':int(np.any(result['graph_offer']>0,axis=0).sum())})
            del row,contexts
    assert len(checks)==10
    with (OUT/'trace-audit.json').open('x',encoding='utf-8') as f:
        json.dump({'checks':checks,'gold_read':False,'new_language_model_calls':0,'source_text_exported':False},f,indent=2)
    print(json.dumps({'exact_fresh_trace_replays':len(checks),'new_language_model_calls':0,'quality_evaluated':False}))


if __name__=='__main__':main()

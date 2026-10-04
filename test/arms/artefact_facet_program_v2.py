"""Serialization adapter for the sealed fixed-program experimental arm.

The numeric policy, source resolver, budget, interpretation, and generation are
delegated unchanged. Only the structural area metadata is made JSON-safe.
"""
from arms import artefact_facet_program as original


DATABASE=original.DATABASE
INTERPRET_MODEL=original.INTERPRET_MODEL
RETRIEVAL_FLAGS={**original.RETRIEVAL_FLAGS,
                 'serving_adapter':'v2 JSON-safe structural area metadata'}

# Literal additions for the blind wrapper's AST-based dependency seal.
SMOKE_PROVENANCE_PATHS=(
    'test/arms/artefact_facet_program_v2.py',
    'test/arms/artefact_facet_program.py',
)
SMOKE_MODEL_CONFIG={
    'fixed_program_id':'tag_frontier_best-macro-recall_query_only_queries_all',
    'serving_adapter':'v2 JSON-safe structural area metadata',
}


prepare_over_corpus=original.prepare_over_corpus


def answer_one_question(question, prepared, generate, k=50, char_budget=None):
    out=original.answer_one_question(question,prepared,generate,k=k,char_budget=char_budget)
    if out.meta is not None and 'area' in out.meta:
        meta=dict(out.meta)
        area=dict(meta['area'])
        chunk_ids=area.get('chunk_ids')
        area['chunk_ids']=None if chunk_ids is None else sorted(chunk_ids)
        meta['area']=area
        out.meta=meta
    return out

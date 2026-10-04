"""Experimental fixed-program artefact arm for a real 72k gold smoke.

Interpretation and query embeddings use the frozen joint arm. Retrieval receives
only immutable graph values and numeric query readings. Source resolution and
answer generation occur after the full chunk ranking is fixed.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import time

import numpy as np
from threadpoolctl import threadpool_limits

from harness import chat
from harness.contract import ArmOutput, BuildStats, ModelUsage, unpack_generation
from arms import artefact_facet_joint as joint
from arms.artefact_v2 import _budget_contexts, _resolve_chunk
from artefact.facet_graph_input import GraphInput
from artefact.facet_recruitment_candidate import _components
from artefact.facet_structural_landing import resolve_structural_area
from artefact.facet_tag_frontier import edge_gate, inject
from artefact.facet_directed_frontier_engine import run_program
from facet_directed_values import project


ROOT = Path(__file__).resolve().parents[2]
SELECTED = ROOT / 'output/research/2026-09-24-leader-gold-smokes/best-total-hits.json'
SELECTED_SHA256 = '81198bbe32285a0789d86687ee525bac1e819c44345dce7683925d8b28207275'
SELECTED_ID = 'directed_frontier_0004'
DATABASE = joint.DATABASE
INTERPRET_MODEL = joint.INTERPRET_MODEL
RETRIEVAL_FLAGS = {
    'snapshot': str(joint.SNAPSHOT),
    'snapshot_sha256': joint.PINNED_FILES,
    'fixed_program_id': SELECTED_ID,
    'fixed_program_sha256': SELECTED_SHA256,
    'scope': 'Existing raw-query structural resolver, area-first',
    'construction': 'Query-tag frontier gate before edge-to-chunk reduction',
    'budget': 'Shared source resolver after full ranking, 72k serialized characters',
}

# Literal additions; the smoke wrapper merges the joint arm's declarations.
SMOKE_PROVENANCE_PATHS = (
    'test/arms/artefact_facet_leader_hits.py',
    'test/artefact/facet_graph_input.py',
    'test/artefact/facet_construction_routes.py',
    'test/artefact/facet_tag_frontier.py',
    'test/artefact/facet_tag_frontier_fast.py',
    'test/artefact/facet_directed_frontier_engine.py',
    'tools/facet_directed_values.py',
    'output/research/2026-09-24-directed-routes/directed-snapshot.json',
    'test/artefact/facet_construction_fast.py',
    'test/artefact/facet_construction_program.py',
    'test/artefact/facet_operator_matrix.py',
    'test/artefact/facet_recruitment_candidate.py',
    'output/research/2026-09-24-leader-gold-smokes/best-total-hits.json',
    'output/research/2026-09-24-directed-frontier-programs/plan.json',
    'output/research/2026-09-24-directed-frontier-programs/report.json',
    'output/research/2026-09-24-directed-frontier-programs/independent-verification.json',
)
SMOKE_MODEL_CONFIG = {
    'fixed_program_id': 'directed_frontier_0004',
    'fixed_program_sha256': '81198bbe32285a0789d86687ee525bac1e819c44345dce7683925d8b28207275',
    'retrieval_engine': 'value-only tag frontier before edge-to-chunk reduction',
    'serving_contract': '72k serialized characters; partial boundary has no new source-ID credit',
}


@dataclass(frozen=True)
class Prepared:
    base: joint.Prepared
    graph: GraphInput
    component_labels: np.ndarray
    id_order: np.ndarray
    program: dict
    program_sha256: str
    directed_routes: object
    build_stats: BuildStats

    @property
    def provenance(self):
        return self.base.provenance


def _selected_program():
    data=SELECTED.read_bytes()
    digest=hashlib.sha256(data).hexdigest()
    if digest!=SELECTED_SHA256:
        raise ValueError('Fixed selected program hash differs')
    program=json.loads(data)
    if (program.get('id')!=SELECTED_ID or
            program.get('tag_frontier')!={'evidence':'query_only','streams':'queries','sponsors':'all'} or
            program.get('graph_route')!='product_channel'):
        raise ValueError('Fixed selected program identity differs')
    return program,digest


def prepare_over_corpus(corpus) -> Prepared:
    started=time.perf_counter()
    base=joint.prepare_over_corpus(corpus,scope_scheduling='area_first')
    ids=tuple(chunk['chunkId'] for chunk in base.chunks)
    products={}
    for ci,chunk in enumerate(base.chunks):
        for product in chunk['scope'].get('product',[]):
            products.setdefault(product['node_id'],[]).append(ci)
    graph=GraphInput(ids,base.edge_tag,base.edge_chunk,
                     base.reference.transform(base.edge_facets),base.groups,
                     base.adjacency_pairs,tuple(products.values()))
    at={cid:i for i,cid in enumerate(ids)}
    labels=np.arange(len(ids))
    components,_,_=_components(base.chunks)
    for component in components:
        members=[at[row['chunk_id']] for row in component['members']]
        labels[members]=min(members)
    id_order=np.argsort(np.argsort(np.asarray(ids)))
    program,digest=_selected_program()
    source_hashes=base.provenance.setdefault('source_sha256',{})
    for path in (Path(__file__),ROOT/'test/artefact/facet_tag_frontier.py',
                 ROOT/'test/artefact/facet_tag_frontier_fast.py'):
        source_hashes[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
    base.provenance['fixed_program']={'id':SELECTED_ID,'sha256':digest,
                                      'path':str(SELECTED.relative_to(ROOT))}
    stats=BuildStats(time.perf_counter()-started,base.build_stats.model,base.build_stats.models)
    snapshot=ROOT/'output/research/2026-09-24-directed-routes/directed-snapshot.json'
    data=snapshot.read_bytes()
    if hashlib.sha256(data).hexdigest()!='1246184fe65c08b16a16d44ecd227241755a4580e0eefec87230e48da0038bd9':raise ValueError('Pinned directed graph changed')
    routes=project(ids,json.loads(data))
    return Prepared(base,graph,labels,id_order,program,digest,routes,stats)


def rank_numeric(prepared: Prepared, matrices, weights, area_mask=None):
    """Pure retrieval stage, also used for captured-case parity without models."""
    if type(prepared.graph) is not GraphInput:
        raise TypeError('Value-only GraphInput required')
    gate,frontier=edge_gate(prepared.graph,matrices,weights,**prepared.program['tag_frontier'])
    result=run_program(inject(prepared.program),prepared.graph,matrices,weights,
                       area_mask,prepared.component_labels,prepared.id_order,
                       cache=None,frontier_gate=gate,directed_routes=prepared.directed_routes)
    return result,frontier


def answer_one_question(question, prepared: Prepared, generate, k: int = 50,
                        char_budget: int | None = None) -> ArmOutput:
    if not isinstance(question,(tuple,list)) or len(question)!=2:
        raise ValueError('Expected (question_id, raw_question)')
    _,text=question
    if not isinstance(text,str) or not text.strip():
        raise ValueError('Raw question must be nonempty text')
    if char_budget is not None and (type(char_budget) is not int or char_budget<1):
        raise ValueError('char_budget must be a positive integer or None')
    if type(k) is not int or k<1:
        raise ValueError('k must be a positive integer')
    started=time.perf_counter();chat.reset_timing()
    generation,weights,interp_usage,interp_meta=joint._interpret(text,prepared.base)
    matrices,embed_usage,embed_meta=joint._query_cosines(
        generation['description'],generation['tags'],prepared.base)
    area_ids,area_provenance=resolve_structural_area(text,prepared.base.structural_index)
    if area_ids is None:
        area=None
    else:
        members=set(area_ids)
        area=np.array([cid in members for cid in prepared.graph.chunk_ids])
    with joint._NUMERIC_LOCK,threadpool_limits(limits=4):
        result,frontier=rank_numeric(prepared,matrices,weights,area)
    ordered_ids=[prepared.graph.chunk_ids[i] for i in result['order']]
    by_id={chunk['chunkId']:chunk for chunk in prepared.base.chunks}
    ordered_rows=[by_id[cid] for cid in ordered_ids]
    doc_cache={}
    if char_budget is not None:
        contexts,id_lists,context_ids,budget=_budget_contexts(ordered_rows,char_budget,doc_cache)
    else:
        contexts,id_lists,context_ids=[],[],[]
        for row in ordered_rows[:k]:
            content,ids=_resolve_chunk(row,doc_cache)
            contexts.append(content);id_lists.append(ids)
            for aid in ids:
                if aid not in context_ids:context_ids.append(aid)
        budget=None
    retrieval=ModelUsage(**{name:getattr(interp_usage,name)+getattr(embed_usage,name)
                            for name in ModelUsage.__dataclass_fields__})
    for name,value in chat.take_timing().items():setattr(retrieval,name,value)
    meta={'policy':{'program_id':SELECTED_ID,'program_sha256':prepared.program_sha256,
                    'tag_frontier':prepared.program['tag_frontier'],
                    'scope':'existing raw-query structural resolver, area-first',
                    'source_delivery':'shared resolver after numeric ranking'},
          'snapshot':prepared.provenance,'interpreter':interp_meta,'embedding':embed_meta,
          'area':{'chunk_ids':None if area_ids is None else sorted(area_ids),'provenance':area_provenance},
          'ranking':{'full_order_chunk_ids':ordered_ids,
                     'order_sha256':hashlib.sha256(result['order'].tobytes()).hexdigest(),
                     'tag_frontier_positive_tags':frontier['positive_tags'],
                     'tag_frontier_positive_edges':frontier['positive_edges']},
          'delivered_chunk_ids':ordered_ids[:len(contexts)],'chunk_ids':id_lists,
          'returned':len(contexts),'char_budget':budget,
          'delivery_note':'Partial boundary text is delivered but its source IDs are not credited.'}
    search_time=max(0.,time.perf_counter()-started-interp_usage.time_s)
    if generate is None:answer,gen_usage='',ModelUsage()
    else:
        gen_start=time.perf_counter()
        answer,gen_usage=unpack_generation(generate(text,contexts),time.perf_counter()-gen_start)
    return ArmOutput(answer=answer,contexts=contexts,context_ids=context_ids,
                     search_time_s=search_time,generator=gen_usage,retrieval=retrieval,meta=meta)

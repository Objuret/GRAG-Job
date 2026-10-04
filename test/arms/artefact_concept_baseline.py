"""Single interpretation, retained edge evidence and graph-area corroboration.

An explicit implementation of the recovered dataflow, not a declaration that
the frozen measurements or provisional numeric policy have been validated.
"""
from dataclasses import dataclass, asdict
from pathlib import Path
import time
import numpy as np

from arms import artefact_facet_joint as J
from arms.artefact_v2 import _budget_contexts, _resolve_chunk
from artefact import querytagger as Q
from artefact import querytagger_split_check as S
from artefact.concept_baseline import ConceptGraph, retrieve, POLICY
from artefact.landing import Landing, land
from harness.contract import ArmOutput, ModelUsage, unpack_generation

ROOT=Path(__file__).resolve().parents[2]
INTERPRET_SYSTEM=(Q.GENERATE_SYSTEM.split('Return ONLY valid JSON:')[0]+'''
## Relationships through facets

Use the original question and the description you have just written together.
For every tag, judge its relevance to the content characterised by that
description through each facet. The original question remains available to
preserve its intended relationships. Do not invent facts of an unseen answer.
This is neither the tag's category nor the importance of the facet in general.

topic: looking at what the described content is about, how relevant is this tag?
temporal: looking at the described content's time relations, how relevant is this tag?
why: looking at the described content's reasons, causes and purposes, how relevant is this tag?
activity: looking at the activities and processes represented in the described content, how relevant is this tag?
concreteness: looking at the described content's specifics, how relevant is this tag?

Judge the tag's relevance to content through the facet, not whether something
is being done to the thing named by the tag. Being discussed or referenced does
not by itself imply low relevance. A date, name or number alone does not establish
a strong relationship. Values range from 0 (not relevant through that facet)
to 1 (could not be more relevant). Never force a highest value or normalize
the five values to sum to one. Several or all facets may be high or low.

Return ONLY valid JSON: {"description":"...","tags":[{"t":"semantic phrase",
"facets":{"topic":0.0,"temporal":0.0,"why":0.0,"activity":0.0,"concreteness":0.0}}]}
''')


def parse_interpretation(raw):
    if not isinstance(raw,dict) or not isinstance(raw.get('tags'),list):raise ValueError('Description and tag relations required')
    names=[r['t'] for r in raw['tags']]
    generation=S.parse_generate({'description':raw.get('description'),'tags':names})
    if len(generation['tags'])!=len(names):raise ValueError('No silent removal of interpreted tags')
    scores=S.parse_score(raw,generation['tags'])
    return {'description':generation['description'],'tags':scores['tags']}


@dataclass(frozen=True)
class Prepared:
    base: object
    graph: ConceptGraph
    names: tuple
    area_provenance: tuple
    build_stats: object

    @property
    def provenance(self):return self.base.provenance


def prepare_over_corpus(corpus):
    base=J.prepare_over_corpus(corpus)
    ids=tuple(c['chunkId'] for c in base.chunks);at={cid:i for i,cid in enumerate(ids)}
    areas=[];provenance=[];names=[]
    for key,node in sorted(base.structural_index.nodes.items()):
        names.extend(Landing(key[0],key[1],name,kind) for name,kind in node['names'])
        for route,members in sorted(node['routes'].items()):
            values=tuple(sorted(at[c] for c in members))
            if values:
                areas.append(values);provenance.append({'node':key,'route':route,'members':values})
    graph=ConceptGraph(ids,base.edge_tag,base.edge_chunk,np.maximum(base.edge_facets[:,0],0),
                       base.reference.transform(base.edge_facets)[:,1:],tuple(areas))
    return Prepared(base,graph,tuple(names),tuple(provenance),base.build_stats)


def rank_numeric(prepared, question, matrices, weights):
    hits=land(question,prepared.names)
    members=set();bindings=[];at={cid:i for i,cid in enumerate(prepared.graph.chunk_ids)}
    for hit in hits:
        node=prepared.base.structural_index.nodes[(hit.label,hit.node_id)]
        members.update(at[c] for c in node['chunks'])
        bindings.append({**asdict(hit),'reachable_chunks':len(node['chunks'])})
    result=retrieve(prepared.graph,matrices,weights,tuple(sorted(members)))
    result['landings']=bindings
    return result


def answer_one_question(question,prepared,generate,k=50,char_budget=None):
    if not isinstance(question,(tuple,list)) or len(question)!=2:raise ValueError('Expected ID and raw question')
    _,text=question
    if not isinstance(text,str) or not text.strip():raise ValueError('Nonempty question required')
    if type(k)is not int or k<1:raise ValueError('Positive k required')
    if char_budget is not None and (type(char_budget)is not int or char_budget<1):raise ValueError('Positive character budget required')
    started=time.perf_counter()
    parsed,usage,cache=J._cached_stage('interpret',INTERPRET_SYSTEM,'Question: '+text,
        parse_interpretation,ROOT/'output/private/concept_baseline_cache')
    tags=[r['t'] for r in parsed['tags']]
    weights=np.array([[r['facets'][f] for f in J.FACETS] for r in parsed['tags']])
    matrices,embed_usage,recipe=J._query_cosines(parsed['description'],tags,prepared.base)
    result=rank_numeric(prepared,text,matrices,weights)
    ordered=[prepared.base.chunks[i] for i in result['order']]
    if char_budget is not None:
        contexts,id_lists,context_ids,budget=_budget_contexts(ordered,char_budget,{})
    else:
        resolved=[_resolve_chunk(row,{}) for row in ordered[:k]]
        contexts=[r[0] for r in resolved];id_lists=[r[1] for r in resolved]
        context_ids=list(dict.fromkeys(x for ids in id_lists for x in ids));budget=None
    retrieval=ModelUsage(**{f:getattr(usage,f)+getattr(embed_usage,f) for f in ModelUsage.__dataclass_fields__})
    search_time=time.perf_counter()-started
    answer='';gen_usage=ModelUsage()
    if generate is not None:
        start=time.perf_counter();answer,gen_usage=unpack_generation(generate(text,contexts),time.perf_counter()-start)
    meta={'policy':POLICY,'interpreter':parsed,'interpreter_cache':cache,'embedding':recipe,
          'landings':result['landings'],'full_order':[prepared.graph.chunk_ids[i] for i in result['order']],
          'scores':result['scores'].tolist(),'direct_by_query':result['direct'].tolist(),
          'graph_by_query':result['graph_offer'].tolist(),'area_support_by_query':result['area_support'].tolist(),
          'unique_query_rows':result['unique_query_rows'].tolist(),'tag_candidates':int(result['tag_candidates'].sum()),
          'candidate_count':int(result['candidate'].sum()),'chunk_ids':id_lists,'char_budget':budget,
          'area_provenance':prepared.area_provenance,'snapshot':prepared.base.provenance}
    return ArmOutput(answer,contexts,context_ids,search_time,gen_usage,retrieval,meta)

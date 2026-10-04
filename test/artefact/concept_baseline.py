"""Evidence-preserving concept baseline, not a gold-selected construction.

Numeric graph/query inputs only. The explicit provisional arithmetic is recorded
in POLICY. Retains per-query/edge contributions and per-query/area support until
final combination; structural support cannot remove a direct tag candidate.
"""
from dataclasses import dataclass
import numpy as np

POLICY = {
    'topic': 'Original nonnegative topic cosine, not its percentile.',
    'auxiliary_measurement': 'Existing frozen four learned edge ranks; validity unresolved.',
    'edge_adjustment': 'topic * (1 + mean(query_auxiliary * edge_auxiliary_rank)); bounded multiplier [1,2].',
    'query_topic': 'Match strength multiplied by query topic relevance; zero scores retain tag candidacy.',
    'descriptions': 'Tag-to-description and whole-description similarities strengthen by factors [1,2], never veto tag evidence.',
    'tag_paths': 'Sum all matched distinct graph-tag edges for each query/chunk. No strongest-path selection.',
    'graph_areas': 'Every distinct captured node-route chunk set is an area; preserve named and semantic support separately.',
    'graph_support': 'Mean evidence of other chunks per area; mean across containing areas; gated only for NEW graph access by description similarity.',
    'scope': 'Named reachable union first, outside retained. Distinct mentions corroborate; no inferred Boolean exclusion.',
    'query_aggregation': 'Mean after direct and graph evidence are recorded separately per query; exact numeric duplicate queries grouped.',
    'delivery': 'No record recovery or hidden ranking rewrite; deterministic score/ID order then shared source resolver and budget.',
    'limits': 'Arithmetic and scale bridge are declared implementation choices, not historically settled or calibrated. Captured graph coverage remains limited.',
}


def immutable(value, dtype):
    a=np.asarray(value,dtype=dtype)
    return np.frombuffer(a.tobytes(),dtype=a.dtype).reshape(a.shape)


@dataclass(frozen=True, slots=True)
class ConceptGraph:
    chunk_ids: tuple
    edge_tag: np.ndarray
    edge_chunk: np.ndarray
    topic: np.ndarray
    auxiliary: np.ndarray
    areas: tuple

    def __post_init__(self):
        ids=tuple(self.chunk_ids)
        if not ids or len(set(ids))!=len(ids) or any(type(x)is not str for x in ids):
            raise ValueError('Unique opaque chunk IDs required')
        object.__setattr__(self,'chunk_ids',ids)
        for name,dtype in [('edge_tag',int),('edge_chunk',int),('topic',float),('auxiliary',float)]:
            object.__setattr__(self,name,immutable(getattr(self,name),dtype))
        et,ec=self.edge_tag,self.edge_chunk
        if et.ndim!=1 or ec.shape!=et.shape or self.topic.shape!=et.shape or self.auxiliary.shape!=(len(et),4):
            raise ValueError('Aligned edge measurements required')
        if (et<0).any() or (ec<0).any() or (ec>=len(ids)).any():raise ValueError('Invalid endpoint')
        if not np.isfinite(self.topic).all() or not np.isfinite(self.auxiliary).all():raise ValueError('Nonfinite measurement')
        if (self.topic<0).any() or (self.auxiliary<0).any() or (self.auxiliary>1).any():raise ValueError('Invalid measurement range')
        # Equal memberships must not count again just because several routes
        # describe them. The adapter retains their original provenance separately.
        areas=tuple(sorted(set(tuple(sorted(set(a))) for a in self.areas)))
        if any(any(type(c)is not int or not 0<=c<len(ids) for c in a) for a in areas):raise ValueError('Invalid area')
        object.__setattr__(self,'areas',tuple(a for a in areas if a))


def retrieve(graph, matrices, weights, named_members=()):
    if type(graph)is not ConceptGraph:raise TypeError('Value-only ConceptGraph required')
    n=len(graph.chunk_ids);et,ec=graph.edge_tag,graph.edge_chunk
    m=np.asarray(matrices['query_tag_cosines'],float)
    d=np.asarray(matrices['query_chunk_cosines'],float)
    whole=np.asarray(matrices['query_description_cosines'],float)
    u=np.asarray(weights,float)
    if m.ndim!=2 or not len(m) or d.shape!=(len(m),n) or u.shape!=(len(m),5) or whole.shape!=(n,):raise ValueError('Query alignment mismatch')
    if any(not np.isfinite(a).all() for a in (m,d,whole,u)) or (u<0).any() or (u>1).any():raise ValueError('Invalid query readings')
    if len(et) and et.max()>=m.shape[1]:raise ValueError('Missing tag vectors')
    _,unique=np.unique(np.concatenate((m,d,u),axis=1),axis=0,return_index=True)
    unique=np.sort(unique);m,d,u=m[unique],d[unique],u[unique]
    m,d,whole=np.maximum(m,0),np.maximum(d,0),np.maximum(whole,0)
    matched=m[:,et]>0
    adjustment=1+(u[:,1:]@graph.auxiliary.T)/4
    edge_base=m[:,et]*u[:,:1]*graph.topic[None,:]
    edge_values=edge_base*adjustment*(1+d[:,ec])
    direct=np.zeros((len(m),n));matched_chunks=np.zeros(n,bool)
    for qi in range(len(m)):
        np.add.at(direct[qi],ec,edge_values[qi])
        matched_chunks[ec[matched[qi]]]=True
    area_support=np.zeros((len(m),len(graph.areas)))
    graph_support=np.zeros_like(direct);membership_count=np.zeros(n,int)
    for ai,area in enumerate(graph.areas):
        members=np.asarray(area,int)
        area_support[:,ai]=direct[:,members].mean(axis=1)
        if len(members)<2:continue
        other=(direct[:,members].sum(axis=1,keepdims=True)-direct[:,members])/(len(members)-1)
        graph_support[:,members]+=np.maximum(other,0)
        membership_count[members]+=1
    graph_support/=np.maximum(membership_count,1)[None,:]
    # Graph offers do not replace, cap, or intersect direct evidence.
    graph_offer=graph_support*d
    per_query=direct*(1+whole[None,:])+graph_offer
    scores=per_query.mean(axis=0)
    named=np.zeros(n,bool)
    named_idx=np.asarray(tuple(named_members),int)
    if ((named_idx<0)|(named_idx>=n)).any():raise ValueError('Named area outside graph')
    named[named_idx]=True
    candidate=matched_chunks|np.any(graph_offer>0,axis=0)
    ids=np.asarray(graph.chunk_ids)
    order=np.lexsort((ids,-scores,~named))
    order=order[candidate[order]]
    assert np.all(candidate[matched_chunks])
    return {'order':order,'scores':scores,'candidate':candidate,'tag_candidates':matched_chunks,
            'edge_base':edge_base,'edge_adjustment':adjustment,'edge_values':edge_values,
            'direct':direct,'area_support':area_support,'graph_offer':graph_offer,
            'per_query':per_query,'named':named,'unique_query_rows':unique,'policy':POLICY}

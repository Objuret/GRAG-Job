"""Query-relative lexicographic tag tiers; numeric graph-only input contract."""
import numpy as np
from artefact.facet_graph_input import GraphInput
from artefact.facet_tag_frontier import edge_gate as scalar_gate, inject
from artefact.facet_tag_frontier_controls import gate_from_depths
from artefact.facet_tag_frontier_engine import run_program as frontier_program


def priority_depths(values, weights):
    """[facet,query,tag] keys; descending relevance, canonical index for ties.

    Zero-relevance columns cannot admit or distinguish tags. All-zero tuples
    are unsupported. Complete exactly equal positive tuples share a dense tier.
    No bands, tag limits, corpus, gold or costs are used.
    """
    v=np.asarray(values,float);u=np.asarray(weights,float)
    if v.ndim!=3 or v.shape[:2]!=(5,len(u)) or u.shape!=(v.shape[1],5):
        raise ValueError('Unaligned facet/query/tag keys')
    if any(not np.isfinite(x).all() or (x<0).any() for x in (v,u)):
        raise ValueError('Finite nonnegative keys and query readings required')
    depths=np.zeros((1,v.shape[1],v.shape[2]),np.int32);orders=[]
    for q in range(v.shape[1]):
        keys=sorted(np.flatnonzero(u[q]>0).tolist(),key=lambda f:(-u[q,f],f))
        orders.append(keys)
        if not keys:continue
        tuples=v[keys,q,:].T
        supported=np.any(tuples>0,axis=1)
        distinct=sorted(set(map(tuple,tuples[supported])),reverse=True)
        rank={key:i+1 for i,key in enumerate(distinct)}
        for t in np.flatnonzero(supported):depths[0,q,t]=rank[tuple(tuples[t])]
    return depths,orders


def edge_gate(graph,matrices,weights,*,method='lexicographic',sponsors='first'):
    if type(graph) is not GraphInput:raise TypeError('GraphInput required')
    if method=='scalar':
        return scalar_gate(graph,matrices,weights,evidence='outgoing_max',streams='queries',sponsors=sponsors)
    if method!='lexicographic':raise ValueError('Unknown priority method')
    m=np.maximum(np.asarray(matrices['query_tag_cosines'],float),0)
    u=np.asarray(weights,float)
    if m.ndim!=2 or u.shape!=(len(m),5):raise ValueError('Invalid query alignment')
    maximum=np.zeros((5,m.shape[1]),float)
    for f in range(5):np.maximum.at(maximum[f],graph.edge_tag,graph.facet_readings[:,f])
    # Positive per-facet constants do not alter lexicographic comparisons.
    values=maximum[:,None,:]*m[None,:,:]
    depths,orders=priority_depths(values,u)
    edge_depth=np.broadcast_to(depths,(5,len(m),m.shape[1]))[:,:,graph.edge_tag]
    gate=gate_from_depths(edge_depth,graph.edge_chunk,len(graph.chunk_ids),sponsors=sponsors,
                          weighting='binary' if sponsors=='first' else 'reciprocal')
    return gate,{'tag_depths':depths,'edge_depths':edge_depth,'facet_priority':orders,
        'positive_tags':int(np.any(depths>0,axis=(0,1)).sum()),
        'positive_edges':int(np.any(gate>0,axis=(0,1)).sum()),
        'complete_tiers':int(depths.max(initial=0)),
        'priority_ties':'canonical facet index; zero relevance excluded'}


def run_program(program,graph,matrices,weights,area,components,id_order):
    """Pure numeric execution, including unchanged downstream construction."""
    gate,state=edge_gate(graph,matrices,weights,**program['query_priority'])
    compiled=program if any(n['id']=='tag_frontier_gate' for n in program['nodes']) else inject(program)
    r=frontier_program(compiled,graph,matrices,weights,area,components,id_order,cache=None,frontier_gate=gate)
    r['query_priority_state']=state
    r['stages']['query_priority']={'op':'query_priority','policy':program['query_priority'],
        **{k:v for k,v in state.items() if not hasattr(v,'shape')}}
    return r

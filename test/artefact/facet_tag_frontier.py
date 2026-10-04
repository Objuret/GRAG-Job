"""Value-only tag nomination before HAS_TAG edge reduction.

No corpus, gold, source size, or arbitrary frontier width enters these operators.
Every positive score tier is admitted; a policy only changes which admitted tag
evidence an edge carries into the unchanged downstream construction.
"""
from copy import deepcopy
import numpy as np

from artefact.facet_graph_input import GraphInput


COEFFICIENTS=np.array([1.,.25,.25,.25,.25])


def inject(program):
    """Place the frontier gate immediately after edge evidence, before reduction."""
    p=deepcopy(program);nodes=[];inserted=False
    for raw in p['nodes']:
        node=deepcopy(raw)
        if inserted:
            node['inputs']=['tag_frontier_edge_evidence' if x=='edge_evidence' else x for x in node.get('inputs',[])]
        nodes.append(node)
        if node['id']=='edge_evidence':
            nodes.append(dict(id='tag_frontier_gate',op='source',inputs=[],params={'name':'tag_frontier_gate'}))
            nodes.append(dict(id='tag_frontier_edge_evidence',op='multiply',
                              inputs=['edge_evidence','tag_frontier_gate'],params={}))
            inserted=True
    if not inserted or not any('tag_frontier_edge_evidence' in n.get('inputs',[]) for n in nodes):
        raise ValueError('Program does not consume edge_evidence downstream')
    p['nodes']=nodes
    return p


def _tiers(scores):
    """Dense competition ranks over complete positive score tiers per stream."""
    flat=scores.reshape(-1,scores.shape[-1]);depth=np.zeros(flat.shape,dtype=np.int32)
    for i,row in enumerate(flat):
        live=row>0
        if live.any():
            distinct=np.unique(row[live])[::-1]
            depth[i,live]=np.searchsorted(-distinct,-row[live],side='left')+1
    return depth.reshape(scores.shape)


def edge_gate(graph,matrices,weights,*,evidence='query_only',streams='joint',sponsors='first'):
    """Return [facet,query,edge] gate and inspectable tag/edge frontier state.

    `query_only` ranks tags from query→tag and query-facet readings alone.
    `outgoing_max` additionally qualifies each tag/facet by its strongest outgoing
    graph edge facet reading. `joint`, `facets`, and `queries` choose independent
    streams. `first` admits only earliest-tier sponsors for each chunk/stream;
    `all` carries every positive sponsor with reciprocal tier depth.
    """
    if type(graph) is not GraphInput:raise TypeError('GraphInput required')
    if evidence not in ('query_only','outgoing_max') or streams not in ('joint','facets','queries') or sponsors not in ('first','all'):
        raise ValueError('Unknown tag-frontier policy')
    m=np.maximum(np.asarray(matrices['query_tag_cosines'],float),0)
    u=np.asarray(weights,float)
    et,ec=graph.edge_tag,graph.edge_chunk
    if m.ndim!=2 or u.shape!=(len(m),5) or not np.isfinite(m).all() or not np.isfinite(u).all() or (u<0).any():
        raise ValueError('Invalid numeric query readings')
    if len(et) and m.shape[1]<=int(et.max()):raise ValueError('Graph tag index outside query readings')
    scores=COEFFICIENTS[:,None,None]*u.T[:,:,None]*m[None,:,:]
    if evidence=='outgoing_max':
        maximum=np.zeros((5,m.shape[1]),float)
        for f in range(5):np.maximum.at(maximum[f],et,graph.facet_readings[:,f])
        scores=scores*maximum[:,None,:]
    if streams=='joint':tag_scores=scores.sum(axis=0).max(axis=0,keepdims=True)[None,:,:]
    elif streams=='facets':tag_scores=scores.max(axis=1,keepdims=True)
    else:tag_scores=scores.sum(axis=0,keepdims=True)
    depths=_tiers(tag_scores)
    expanded=np.broadcast_to(depths,(5,len(m),m.shape[1]))
    edge_depth=expanded[:,:,et]
    if sponsors=='first':
        earliest=np.full((5,len(m),len(graph.chunk_ids)),np.iinfo(np.int32).max,dtype=np.int32)
        for f in range(5):
            for q in range(len(m)):
                np.minimum.at(earliest[f,q],ec,np.where(edge_depth[f,q]>0,edge_depth[f,q],np.iinfo(np.int32).max))
        gate=((edge_depth>0)&(edge_depth==earliest[:,:,ec])).astype(float)
    else:gate=np.divide(1.,edge_depth,out=np.zeros(edge_depth.shape,float),where=edge_depth>0)
    return gate,{'tag_scores':tag_scores,'tag_depths':depths,'edge_depths':edge_depth,
                 'positive_tags':int(np.any(depths>0,axis=(0,1)).sum()),
                 'positive_edges':int(np.any(gate>0,axis=(0,1)).sum()),
                 'positive_chunks':int(np.unique(ec[np.any(gate>0,axis=(0,1))]).size),
                 'complete_tiers':int(depths.max(initial=0))}

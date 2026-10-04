"""Pure edge aggregation and independent recruitment primitives; no IO or outcomes."""
import numpy as np
from artefact.facet_operator_matrix import _reducer


def reduce_edges(values, targets, tags, mode, n):
    """Copies of a (chunk, graph-tag) edge do not earn extra votes.

    Duplicate endpoints with conflicting facet scores are invalid, not averaged.
    Mean divides by distinct graph tags on the chunk; sum deliberately exposes
    degree sensitivity. Neither establishes independence of different tags.
    """
    pairs=np.stack((targets,tags),axis=1)
    _,first,inverse=np.unique(pairs,axis=0,return_index=True,return_inverse=True)
    if len(first)!=len(targets) and not np.array_equal(values,values[...,first[inverse]]):
        raise ValueError('Conflicting duplicate graph edges')
    targets=targets[first]; values=values[...,first]
    if mode=='maximum':return _reducer(targets,n)(values)
    if mode not in ('mean','sum'):raise ValueError('Unknown edge reducer')
    order=np.argsort(targets,kind='stable'); sorted_t=targets[order]
    starts=np.flatnonzero(np.r_[True,sorted_t[1:]!=sorted_t[:-1]])
    out=np.zeros((*values.shape[:-1],n))
    if len(targets):
        total=np.add.reduceat(values[...,order],starts,axis=-1)
        if mode=='mean':total/=np.diff(np.r_[starts,len(targets)])
        out[...,sorted_t[starts]]=total
    return out


def independent_batches(streams, id_order):
    """Each live stream nominates its next unseen *complete score tier* per round.

    All streams see the same pre-round visited set. The union is admitted once,
    with stable-ID order inside the round. No top-k, budget or gold is involved.
    Empty/exhausted streams abstain. Already recruited copies are skipped, not
    counted as another stream's new batch. Return round depths and sponsors.
    """
    streams=np.asarray(streams)
    if streams.ndim!=2 or not len(streams) or not np.isfinite(streams).all() or (streams<0).any():
        raise ValueError('Nonempty finite nonnegative streams required')
    n=streams.shape[1]
    lists=[]
    for values in streams:
        order=np.lexsort((id_order,-values))
        lists.append(order[values[order]>0])
    pointers=[0]*len(lists); seen=np.zeros(n,dtype=bool); depth=np.full(n,n+1,dtype=int)
    sponsors=[[] for _ in range(n)]; round_no=0
    while True:
        offers={}
        for si,order in enumerate(lists):
            j=pointers[si]
            while j<len(order) and seen[order[j]]:j+=1
            if j==len(order):pointers[si]=j;continue
            score=streams[si,order[j]]
            while j<len(order) and streams[si,order[j]]==score:
                c=int(order[j])
                if not seen[c]:offers.setdefault(c,[]).append(si)
                j+=1
            pointers[si]=j
        if not offers:break
        round_no+=1
        for c,who in offers.items():seen[c]=True;depth[c]=round_no;sponsors[c]=who
    return depth,sponsors

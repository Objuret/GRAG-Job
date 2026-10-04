"""Separate tag sponsorship, tier weighting, and batch admission priority."""
import numpy as np

from artefact.facet_construction_routes import independent_batches


def gate_from_depths(edge_depths,edge_chunks,n_chunks,*,sponsors,weighting):
    if sponsors not in ('first','all') or weighting not in ('binary','reciprocal'):
        raise ValueError('Unknown frontier gate control')
    depths=np.asarray(edge_depths)
    if depths.ndim!=3 or (depths<0).any():raise ValueError('Invalid edge depths')
    ec=np.asarray(edge_chunks)
    if sponsors=='first':
        earliest=np.full((*depths.shape[:2],n_chunks),np.iinfo(np.int32).max,dtype=np.int32)
        for f in range(depths.shape[0]):
            for q in range(depths.shape[1]):
                np.minimum.at(earliest[f,q],ec,np.where(depths[f,q]>0,depths[f,q],np.iinfo(np.int32).max))
        active=(depths>0)&(depths==earliest[:,:,ec])
    else:active=depths>0
    if weighting=='binary':return active.astype(float)
    return np.divide(1.,depths,out=np.zeros(depths.shape,float),where=active)


def tag_arrival(tag_scores,edge_tags,edge_chunks,n_chunks,groups,components,*,policy):
    """Earliest complete batch to present a chunk; no fixed batch width.

    `own` uses incident tag admission. `inherit` also admits a chunk when a
    shared-entity group sponsor arrives. Linked-record recovery then gives
    siblings the earliest arrival in their component. All steps are graph-only.
    """
    if policy not in ('own','inherit'):raise ValueError('Unknown arrival policy')
    scores=np.asarray(tag_scores,float)
    tag_count=scores.shape[-1]
    depth,_=independent_batches(scores.reshape(-1,tag_count),np.arange(tag_count))
    never=int(depth.max(initial=0))+1
    # independent_batches uses n_tags+1 for tags with no support.
    live=depth<=tag_count
    edge_depth=np.where(live[np.asarray(edge_tags)],depth[np.asarray(edge_tags)],never)
    arrival=np.full(n_chunks,never,dtype=int)
    np.minimum.at(arrival,np.asarray(edge_chunks),edge_depth)
    if policy=='inherit':
        inherited=arrival.copy()
        for group in groups:
            members=np.asarray(group,dtype=int)
            if len(members)>1:inherited[members]=np.minimum(inherited[members],arrival[members].min())
        arrival=inherited
    # Recovery is downstream of nomination in both selected parents.
    comp=np.asarray(components,dtype=int)
    minima=np.full(int(comp.max())+1,never,dtype=int)
    np.minimum.at(minima,comp,arrival)
    arrival=np.minimum(arrival,minima[comp])
    return arrival,depth


def tier_priority_order(base_order,arrival,area=None):
    """Complete tag arrival tier, then the parent's downstream chunk order.

    The selected parents use area-first admission; retain that outer stratum.
    Unreached chunks follow reached chunks within their stratum.
    """
    order=np.asarray(base_order,dtype=int)
    strata=np.zeros(len(order),dtype=int) if area is None else (~np.asarray(area,dtype=bool)[order]).astype(int)
    return order[np.lexsort((np.arange(len(order)),arrival[order],strata))]

"""Opaque exact-record components as evidence transport or context assembly."""
import numpy as np

def checked_components(components,n):
    c=np.asarray(components)
    if c.shape!=(n,) or not np.issubdtype(c.dtype,np.integer) or (c<0).any() or (c>=n).any():
        raise ValueError('Aligned bounded numeric component IDs required')
    return c

def component_max(values,components):
    a=np.asarray(values,float);c=checked_components(components,a.shape[-1])
    if a.ndim!=3 or not np.isfinite(a).all() or (a<0).any():raise ValueError('Finite nonnegative stream evidence required')
    pooled=np.zeros_like(a)
    for stream in np.ndindex(a.shape[:-1]):np.maximum.at(pooled[stream],c,a[stream])
    return pooled[...,c]

def contiguous_order(order,original_depth,components,id_order):
    """Keep existing access; bundle each record at its earliest native nomination.

    Component identity comes only from overlapping/touching ranges of one exact
    source record. No source text or lengths are supplied. Shared 72k serving can
    split a bundle; no budget-dependent skip, packing or atomic-bundle claim.
    """
    order=np.asarray(order,dtype=int);depth=np.asarray(original_depth);n=len(depth)
    c=checked_components(components,n);ids=np.asarray(id_order)
    if ids.shape!=(n,) or len(set(order.tolist()))!=len(order):raise ValueError('Invalid order alignment')
    groups={}
    for chunk in order:groups.setdefault(int(c[chunk]),[]).append(int(chunk))
    members=[sorted(v,key=lambda x:(depth[x],ids[x])) for v in groups.values()]
    members.sort(key=lambda v:(depth[v[0]],ids[v[0]]))
    return np.array([chunk for group in members for chunk in group],dtype=int)

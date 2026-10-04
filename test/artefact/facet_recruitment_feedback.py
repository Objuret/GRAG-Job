"""Return first-admission evidence to traversal, using no outcomes or costs."""
import numpy as np


def nomination_evidence(nomination, values, mode):
    values=np.asarray(values)
    n=values.shape[-1];flat=values.reshape(-1,n)
    if nomination.depth.shape!=(n,) or len(nomination.sponsors)!=n:
        raise ValueError('Unaligned nomination evidence')
    selected=np.zeros_like(flat,dtype=bool)
    for chunk,sponsors in enumerate(nomination.sponsors):
        for stream in sponsors:
            if not 0<=stream<len(flat):raise ValueError('Invalid sponsor index')
            selected[stream,chunk]=True
    selected &= flat>0
    priority=np.where(nomination.depth<=n,1./np.maximum(nomination.depth,1),0.)
    if mode=='sponsor_scores':result=np.where(selected,flat,0.)
    elif mode=='inverse_sponsors':result=selected*priority[None,:]
    elif mode=='inverse_all':result=(flat>0)*priority[None,:]
    else:raise ValueError('Unknown nomination evidence mode')
    return result.reshape(values.shape)

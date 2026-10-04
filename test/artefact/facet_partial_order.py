"""Experimental interval-supported ordering, not wired into serving retrieval.

Candidate i must precede j only when lower[i] > upper[j]. Among currently
unconstrained candidates, use a fixed baseline descending and stable ID. This
extends the partial order without assuming uncertain comparisons are semantic
ties or using a potentially cyclic pairwise fallback comparator.
"""
from __future__ import annotations
import heapq
import numpy as np


def interval_order(ids, lower, upper, baseline):
    ids=list(ids)
    lo,hi,base=(np.asarray(v,dtype=float) for v in (lower,upper,baseline))
    n=len(ids)
    if any(v.shape!=(n,) or not np.isfinite(v).all() for v in (lo,hi,base)):
        raise ValueError('Aligned finite one-dimensional scores required')
    if len(set(ids))!=n or any(not isinstance(i,str) for i in ids) or (lo>hi).any():
        raise ValueError('Unique string IDs and nonempty intervals required')
    # j has no remaining predecessor exactly when upper[j] >= the largest
    # remaining lower bound. That threshold only decreases. Two heaps and a
    # sorted upper-bound list avoid constructing O(n^2) precedence edges.
    lower_heap=[(-lo[i],i) for i in range(n)];heapq.heapify(lower_heap)
    by_upper=sorted(range(n),key=lambda i:(-hi[i],ids[i]))
    alive=[True]*n;ready=[];ordered=[];cursor=0
    while lower_heap:
        while lower_heap and not alive[lower_heap[0][1]]:heapq.heappop(lower_heap)
        if not lower_heap:break
        threshold=-lower_heap[0][0]
        while cursor<n and hi[by_upper[cursor]]>=threshold:
            i=by_upper[cursor];heapq.heappush(ready,(-base[i],ids[i],i));cursor+=1
        if not ready:raise RuntimeError('Valid intervals must have an available candidate')
        _,cid,i=heapq.heappop(ready);alive[i]=False;ordered.append(cid)
    if len(ordered)!=n:raise RuntimeError('Valid interval dominance must be acyclic')
    return ordered

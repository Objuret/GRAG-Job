"""Order equal nomination tiers using numeric evidence only."""
import numpy as np

METHODS=('id','stream_sum','stream_max','sponsor_count','description','reciprocal_rank')

def reorder(result, program, id_order):
    method=program.get('tie_break','id')
    if method not in METHODS: raise ValueError('Unknown tie rule')
    if method=='id': return result
    final=result['final'];n=len(final.depth)
    streams=result['states'][program['streams_node']].values.reshape(-1,n)
    if method=='stream_sum': evidence=streams.sum(axis=0)
    elif method=='stream_max': evidence=streams.max(axis=0)
    elif method=='sponsor_count': evidence=np.array([len(x) for x in final.sponsors])
    elif method=='description': evidence=result['states']['whole_description'].values.reshape(-1,n).max(axis=0)
    else:
        evidence=np.zeros(n)
        for stream in streams:
            active=stream>0
            levels=np.unique(stream[active])[::-1]
            ranks=np.searchsorted(-levels,-stream[active])+1
            evidence[active]+=1/ranks
    order=np.lexsort((id_order,-evidence,final.original!=final.depth,final.depth))
    order=order[final.depth[order]<=n]
    return {**result,'order':order,'tie_evidence':evidence}

"""Value-only directed chunk routes, deduplicated by source chunk sponsor."""
from dataclasses import dataclass
from types import MappingProxyType
import numpy as np
from scipy.sparse import csr_matrix

@dataclass(frozen=True,slots=True)
class DirectedRoutes:
    chunk_ids:tuple
    matrices:object

def project(chunk_ids,payload):
    if set(chunk_ids)!=set(payload['eligible_chunk_ids']):raise ValueError('Chunk population mismatch')
    at={c:i for i,c in enumerate(chunk_ids)};eids=sorted(payload['employees']);eat={e:i for i,e in enumerate(eids)}
    a,b=zip(*payload['manages_edges']) if payload['manages_edges'] else ([],[])
    relation=csr_matrix((np.ones(len(a),dtype=bool),([eat[x] for x in a],[eat[x] for x in b])),shape=(len(eids),len(eids)))
    matrices={}
    for kind in ('employee_channel','employee_product'):
        pairs=[(eat[e],at[c]) for e in eids for c in payload['employees'][e][kind]]
        rows,cols=zip(*pairs) if pairs else ([],[])
        membership=csr_matrix((np.ones(len(rows),dtype=bool),(rows,cols)),shape=(len(eids),len(at)))
        forward=(membership.T@relation@membership).T.tocsr();forward.setdiag(False);forward.eliminate_zeros()
        for direction,matrix in [('forward',forward),('reverse',forward.T.tocsr()),('symmetric',forward.maximum(forward.T).tocsr())]:
            matrix.sort_indices()
            for array in (matrix.data,matrix.indices,matrix.indptr):array.flags.writeable=False
            matrices[kind+':'+direction]=matrix
    return DirectedRoutes(tuple(chunk_ids),MappingProxyType(matrices))

def propagate(values,routes,key,method='maximum',decay=.5,destination=None):
    if type(routes) is not DirectedRoutes:raise TypeError('Requires value-only DirectedRoutes')
    matrix=routes.matrices[key];n=len(routes.chunk_ids)
    if values.shape[-1]!=n:raise ValueError('Chunk alignment mismatch')
    flat=values.reshape(-1,n)
    if method in ('sum','mean'):
        out=np.asarray(matrix@flat.T).T
        if method=='mean':out=out/np.maximum(np.diff(matrix.indptr),1)[None,:]
    elif method=='maximum':
        out=np.zeros_like(flat)
        for target in range(n):
            src=matrix.indices[matrix.indptr[target]:matrix.indptr[target+1]]
            if len(src):out[:,target]=flat[:,src].max(axis=1)
    else:raise ValueError('Unknown sponsor aggregation')
    out=out.reshape(values.shape)*decay
    if destination is not None:out=out*destination[None,:,:]
    return out

"""Evaluation-side gold pointers for supported edge endpoints, after retrieval."""
import numpy as np

def enrich(reply,states,edge_chunks,chunk_ids):
    linked={r['chunk_id'] for r in reply['movements'] if r['gold_pointer_count']>0}
    for name,state in states.items():
        if getattr(state,'domain',None)!='edge' or name not in reply['stages']:continue
        values=state.values
        supported=np.any(values>0,axis=tuple(range(values.ndim-1)))
        endpoints=np.unique(np.asarray(edge_chunks)[supported])
        reply['stages'][name]['supported_chunks']=len(endpoints)
        reply['stages'][name]['gold_linked_access']=sum(chunk_ids[int(i)] in linked for i in endpoints)
    return reply

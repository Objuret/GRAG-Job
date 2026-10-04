"""Read-only explanation of effective component assembly and ID-sensitive cuts."""
import numpy as np
from artefact.facet_record_assembly import checked_components

def ordering_audit(order,original_depth,components,id_order,full_count):
    """Serving-boundary diagnostic, never an input to ranking.

    A tied component group can straddle the cut even when its neighboring chunks
    have different native depths. Checking final.depth adjacent ties is therefore
    insufficient. This reports structural ID sensitivity, not a proven score loss.
    """
    order=np.asarray(order,dtype=int);depth=np.asarray(original_depth);ids=np.asarray(id_order)
    c=checked_components(components,len(depth));members={}
    if not 0<=full_count<=len(order):raise ValueError('Invalid full delivery count')
    for rank,chunk in enumerate(order):members.setdefault(int(c[chunk]),[]).append((rank,int(chunk)))
    groups=[];keys=[]
    for component,rows in members.items():
        head=min((chunk for _,chunk in rows),key=lambda chunk:(depth[chunk],ids[chunk]))
        groups.append({'component':component,'depth':int(depth[head]),'head_id_order':int(ids[head]),
                       'start':rows[0][0],'end':rows[-1][0]+1,'rows':rows})
        for rank,chunk in rows:keys.append({'rank':rank,'chunk_index':chunk,
            'key':[int(depth[head]),int(ids[head]),int(depth[chunk]),int(ids[chunk])]})
    crossings=[]
    for d in sorted({g['depth'] for g in groups}):
        tied=[g for g in groups if g['depth']==d];start=min(g['start'] for g in tied);end=max(g['end'] for g in tied)
        if len(tied)>1 and start<=full_count<end:
            crossings.append({'kind':'component_head_id','depth':d,'start':start,'end':end,'tied_components':len(tied)})
    for group in groups:
        for d in sorted({int(depth[chunk]) for _,chunk in group['rows']}):
            positions=[rank for rank,chunk in group['rows'] if depth[chunk]==d]
            if len(positions)>1 and min(positions)<=full_count<max(positions)+1:
                crossings.append({'kind':'member_id','component':group['component'],'depth':d,
                                  'start':min(positions),'end':max(positions)+1,'tied_members':len(positions)})
    keys=sorted(keys,key=lambda row:row['rank'])
    if [row['key'] for row in keys]!=sorted(row['key'] for row in keys):
        raise ValueError('Order does not follow declared component assembly keys')
    return {'ordering':'component earliest native depth, component head stable ID, member native depth, member stable ID',
            'effective_keys':keys,'effective_order_verified':True,
            'id_sensitive_serving_cut':bool(crossings),'crossing_id_ties':crossings,
            'note':'Structural dependence on IDs; not evidence that alternative IDs change gold credit.'}

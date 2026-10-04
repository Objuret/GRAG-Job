# Recruitment-feedback extension of frozen fast engine SHA256 fa8d04faa9596f90c2c1d732bbaf8c13289a48da76aa3dc0bdea5e2348f3f55d
# Based on the frozen fast engine; adds only the nomination_evidence operation.
# Original SHA256: 32daa88d38b6c011549819d4b34ee4233fbb36e2a018812650cedca80a6fc3ac
# Keep the original sealed engine intact. Verify full-order parity before use.
"""Explicit retrieval dataflow programs over frozen inputs, never gold or costs.

Every connection is named in a JSON node's inputs. Programs are acyclic; the
explicit reachability operator has a visited set and stops at graph exhaustion.
"""
from dataclasses import dataclass
from collections import OrderedDict
import hashlib
import json
import numpy as np
from artefact.facet_construction_routes import reduce_edges, independent_batches
from artefact.facet_operator_matrix import _checked_relations, _reducer, _graph_primitives
from artefact.facet_graph_input import GraphInput
from artefact.facet_recruitment_feedback import nomination_evidence


from artefact.facet_construction_program import Signal, Nomination


def _first_distinct_rows(values):
    # All values are finite. Normalize signed zero so byte equality matches
    # numerical row equality. Keep first occurrence, exactly as the old code
    # does after sorting the return_index array.
    values = values.copy()
    values[values == 0] = 0
    seen = set(); indices = []
    for i, row in enumerate(values):
        key = row.tobytes()
        if key not in seen:
            seen.add(key); indices.append(i)
    return np.asarray(indices, dtype=int)


def run_program(program, graph, matrices, weights, saved_area, components, id_order, cache=None):
    """Return order and stages from value-only graph data; reject rich snapshots."""
    if type(graph) is not GraphInput:
        raise TypeError('Retrieval requires GraphInput, never a corpus-bearing Prepared object')
    n=len(graph.chunk_ids);et,ec=graph.edge_tag,graph.edge_chunk
    m=np.maximum(matrices['query_tag_cosines'],0);d=np.maximum(matrices['query_chunk_cosines'],0)
    q=np.maximum(matrices['query_description_cosines'],0);u=np.asarray(weights)
    if (m.ndim!=2 or d.shape!=(len(m),n) or u.shape!=(len(m),5) or q.shape!=(n,)
            or not len(m) or any(not np.isfinite(a).all() for a in (m,d,q,u)) or (u<0).any()):
        raise ValueError('Invalid aligned query readings')
    # Deduplicate exactly identical numeric query readings before any operation.
    unique=_first_distinct_rows(np.concatenate((m,d,u),axis=1))
    m,d,u=m[unique],d[unique],u[unique]
    if cache is not None:
        h=hashlib.sha256(str(id(graph)).encode())
        for a in (m,d,q,u,components,id_order,np.asarray([]) if saved_area is None else saved_area):
            h.update(str(a.shape).encode());h.update(a.tobytes())
        binding=h.hexdigest()
        if cache.get('binding')!=binding:cache.clear();cache['binding']=binding
    if cache is not None and 'fixed' in cache:
        f,groups,source,target,adj_reduce=cache['fixed']
    else:
        f=graph.facet_readings
        groups,source,target=_checked_relations(graph,n);adj_reduce=_reducer(target,n)
        if cache is not None:cache['fixed']=(f,groups,source,target,adj_reduce)
    sources={
        'tag_match':Signal(m[:,et][None,:,:],'edge'),
        'tag_description':Signal(d[:,ec][None,:,:],'edge'),
        'edge_facets':Signal(f.T[:,None,:],'edge'),
        'query_facets':Signal(u.T[:,:,None],'broadcast'),
        'coefficients':Signal(np.array([1.,.25,.25,.25,.25])[:,None,None],'broadcast'),
        'whole_description':Signal(q[None,None,:],'chunk'),
        'whole_description_edge':Signal(q[ec][None,None,:],'edge'),
        'query_description':Signal(d[None,:,:],'chunk'),
        'saved_area':Signal(np.ones(n,dtype=bool) if saved_area is None else saved_area,'mask'),
    }
    states={};trace={};relation_pairs={} if cache is None else cache.setdefault('pairs',{})
    node_cache=OrderedDict() if cache is None else cache.setdefault('nodes',OrderedDict())
    cache_keys={}
    def signal(x,domain=None):
        if not isinstance(x,Signal) or (domain is not None and x.domain!=domain):
            raise ValueError('Operation received an incompatible input domain')
        return x.values
    def transit(values,kind,decay,destination,aggregation='maximum'):
        if kind not in ('adjacency','groups','product'):raise ValueError('Unknown graph relation')
        if decay not in (1.,.5):raise ValueError('Declared decay alternatives are 1 and 0.5')
        dest=np.ones((values.shape[1],n)) if destination is None else destination
        selected_groups=groups
        if kind=='product':
            if 'product_groups' not in relation_pairs:
                relation_pairs['product_groups']=[np.array(sorted(set(v)),dtype=int) for v in graph.product_groups if len(set(v))>1]
            selected_groups=relation_pairs['product_groups']
        if aggregation=='maximum':
            adjacent,grouped=_graph_primitives(values,dest,selected_groups,source,target,adj_reduce)
            return (adjacent if kind=='adjacency' else grouped)*(decay/.5)
        if aggregation not in ('mean','sum'):raise ValueError('Unknown sponsor aggregation')
        if kind=='product':
            membership=np.zeros(n,dtype=int)
            for members in selected_groups:membership[members]+=1
            if membership.max(initial=0)>1:raise ValueError('Optimized product accumulation requires disjoint product groups')
            out=np.zeros_like(values)
            for members in selected_groups:
                total=values[...,members].sum(axis=-1,keepdims=True)-values[...,members]
                if aggregation=='mean':total/=len(members)-1
                out[...,members]=decay*np.maximum(total,0)*dest[None,:,members]
            return out
        if kind not in relation_pairs:
            pairs=sorted(set((int(a),int(b)) for group in groups for a in group for b in group if a!=b)) if kind=='groups' else list(zip(source,target))
            relation_pairs[kind]=(np.array([a for a,b in pairs],dtype=int),np.array([b for a,b in pairs],dtype=int))
        src,tgt=relation_pairs[kind]
        offers=decay*values[...,src]*dest[None,:,tgt]
        return reduce_edges(offers,tgt,src,aggregation,n)
    def rank(values,method):
        streams=values.reshape(-1,n)
        if method=='independent_batches':return independent_batches(streams,id_order)
        ranks=[]
        for row in streams:
            supported=row>0;r=np.full(n,n+1,dtype=int)
            r[supported]=1+np.searchsorted(np.sort(-row[supported]),-row[supported],side='left');ranks.append(r)
        if method=='best_rank':depth=np.min(ranks,axis=0)
        elif method=='all_streams':depth=np.max(ranks,axis=0)
        else:raise ValueError('Unknown nomination method')
        sponsors=[[i for i,r in enumerate(ranks) if r[c]==depth[c] and depth[c]<=n] for c in range(n)]
        return depth,sponsors
    nodes=program['nodes']
    if not nodes or len({r['id'] for r in nodes})!=len(nodes):raise ValueError('Unique program node IDs required')
    for node in nodes:
        name,op=node['id'],node['op'];args=node.get('params',{})
        inputs=node.get('inputs',[])
        if any(i not in states for i in inputs):raise ValueError('Inputs must precede consumers; cycles are not allowed')
        key=hashlib.sha256(json.dumps([op,args,[cache_keys[i] for i in inputs]],sort_keys=True).encode()).hexdigest()
        cache_keys[name]=key
        if key in node_cache:
            result,details=node_cache[key];node_cache.move_to_end(key)
            states[name]=result;trace[name]={**details,'inputs':inputs}
            continue
        ins=[states[i] for i in inputs]
        if op=='source':
            if inputs:raise ValueError('Source cannot consume inputs')
            result=sources[args['name']]
        elif op in ('multiply','maximum','minimum','add','average','exclusive'):
            domains={x.domain for x in ins if isinstance(x,Signal) and x.domain!='broadcast'}
            if not ins or len(domains)!=1 or not domains<= {'edge','chunk'}:raise ValueError('Incompatible arithmetic domains')
            arrays=[signal(x) for x in ins]
            result=arrays[0]
            if op=='exclusive':
                if len(arrays)!=2:raise ValueError('Exclusive support requires exactly two inputs')
                result=np.where((arrays[0]>0) != (arrays[1]>0),np.maximum(*arrays),0.)
            else:
                operation={'multiply':np.multiply,'maximum':np.maximum,'minimum':np.minimum,'add':np.add,'average':np.add}[op]
                for arr in arrays[1:]:result=operation(result,arr)
                if op=='average':result=result/len(arrays)
            result=Signal(result,domains.pop())
        elif op=='reduce':
            values=signal(ins[0]);axis={'facet':0,'query':1}[args['axis']]
            method={'maximum':'max','minimum':'min','sum':'sum','mean':'mean'}[args['method']]
            result=Signal(getattr(values,method)(axis=axis,keepdims=True),ins[0].domain)
        elif op=='edges_to_chunks':
            result=Signal(reduce_edges(signal(ins[0],'edge'),ec,et,args['method'],n),'chunk')
        elif op=='propagate':
            values=signal(ins[0],'chunk')
            destination=None if len(ins)==1 else signal(ins[1],'chunk')[0]
            result=Signal(transit(values,args['relation'],args.get('decay',1.),destination,args.get('aggregation','maximum')),'chunk')
        elif op=='concat':
            result=Signal(np.concatenate([signal(x,'chunk').reshape(1,-1,n) for x in ins],axis=1),'chunk')
        elif op=='mask':
            values=signal(ins[0],'chunk');mask=signal(ins[1],'mask')
            result=Signal(values*mask[None,None,:],'chunk')
        elif op=='peaks':
            values=signal(ins[0],'chunk').reshape(-1,n)
            positive=values.max(axis=1)>0
            regions=(values==values.max(axis=1)[:,None]) & positive[:,None]
            result=Signal(regions,'regions')
        elif op=='reach':
            reached=signal(ins[0],'regions').copy();frontier=reached.copy();rounds=0
            relations=args['relations']
            if not relations or any(r not in ('adjacency','groups','product') for r in relations):raise ValueError('Unknown reach relations')
            # Monotone finite fixed point. Revisits cannot contribute new support.
            while frontier.any():
                offers=np.zeros_like(reached)
                for relation in relations:
                    offers |= transit(frontier[None,:,:].astype(float),relation,1.,None)[0]>0
                frontier=offers & ~reached;reached |= frontier;rounds+=1
            result=Signal(reached,'regions');trace[name]={'expansion_rounds':rounds}
        elif op=='region_join':
            regions=signal(ins[0],'regions')
            # Unsupported query streams abstain, rather than define an empty region.
            active=regions[regions.any(axis=1)]
            mask=(np.any(active,axis=0) if args['method']=='union' else np.all(active,axis=0)) if len(active) else np.zeros(n,dtype=bool)
            if args['method'] not in ('union','intersection'):raise ValueError('Unknown region combination')
            trace[name]={'empty_region':not bool(mask.any())}
            result=Signal(mask,'mask')
        elif op=='nominate':
            values=signal(ins[0],'chunk');method=args['method']
            depth,sponsors=rank(values,method)
            if len(ins)==2:
                mask=signal(ins[1],'mask');admission=args['admission']
                local,local_sponsors=rank(values*mask[None,None,:],method)
                if admission=='equal_depth':depth=np.minimum(depth,local)
                elif admission=='area_only':depth=local
                elif admission=='area_first':
                    outside,outside_sponsors=rank(values*(~mask)[None,None,:],method)
                    depth=np.where(mask,local,np.where(outside<=n,np.count_nonzero(local<=n)+outside,n+1))
                    sponsors=[local_sponsors[c] if mask[c] else outside_sponsors[c] for c in range(n)]
                else:raise ValueError('Unknown scope admission')
                if admission!='area_first':sponsors=[local_sponsors[c] if mask[c] and depth[c]==local[c] else sponsors[c] for c in range(n)]
            result=Nomination(depth,depth.copy(),sponsors)
        elif op=='nomination_evidence':
            if len(ins)!=2 or not isinstance(ins[0],Nomination):
                raise ValueError('Nomination evidence requires nominations and their seed streams')
            result=Signal(nomination_evidence(ins[0],signal(ins[1],'chunk'),args['mode']),'chunk')
        elif op=='recover':
            nomination=ins[0]
            if not isinstance(nomination,Nomination):raise ValueError('Recovery requires nominations')
            minima=np.full(n,n+1,dtype=int);np.minimum.at(minima,components,nomination.depth)
            depth=minima[components]
            if len(ins)==2:depth=np.where(signal(ins[1],'mask'),depth,n+1)
            result=Nomination(depth,nomination.original,nomination.sponsors)
        else:raise ValueError('Unknown program operation: '+op)
        states[name]=result
        if isinstance(result,Signal):
            a=result.values
            if not np.isfinite(a).all() or (a<0).any():raise ValueError('Signals must be finite and nonnegative')
            trace.setdefault(name,{})
            trace[name].update(op=op,inputs=inputs,domain=result.domain,shape=list(a.shape),
                supported_chunks=int(np.any(a>0,axis=tuple(range(a.ndim-1))).sum()) if result.domain in ('chunk','regions') else int((a>0).sum()) if result.domain=='mask' else None)
        else:trace[name]={'op':op,'inputs':inputs,'supported_chunks':int((result.depth<=n).sum())}
        if cache is not None and isinstance(result,Signal):
            node_cache[key]=(result,trace[name]);cache['bytes']=cache.get('bytes',0)+result.values.nbytes
            # Memory bound only; eviction changes runtime, never retrieval semantics.
            while cache['bytes']>256*1024*1024 and node_cache:
                _,(old,_) = node_cache.popitem(last=False);cache['bytes']-=old.values.nbytes
    final=states[program['output']]
    if not isinstance(final,Nomination):raise ValueError('Program output must be nominations')
    order=np.lexsort((id_order,final.original!=final.depth,final.depth));order=order[final.depth[order]<=n]
    return {'order':order,'final':final,'stages':trace,'states':states,'query_rows':len(u),'unique_query_rows':unique.tolist()}

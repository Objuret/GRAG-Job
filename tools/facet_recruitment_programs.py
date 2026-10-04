"""Recruit before traversal versus after traversal, without a top-k frontier."""
from copy import deepcopy


def recruit_before_walk(seed,mode,placement,late_method):
    if placement not in ('graph_only','all_paths'):raise ValueError('Unknown recruitment placement')
    if late_method not in ('best_rank','independent_batches'):raise ValueError('Unknown final nomination')
    p=deepcopy(seed)
    walk=next(n for n in p['nodes'] if n['id']=='walk_1');source=walk['inputs'][0]
    nodes=[];inserted=False
    for node in p['nodes']:
        if inserted:
            if placement=='all_paths':node['inputs']=['recruited_evidence' if x==source else x for x in node['inputs']]
            elif node['id']=='walk_1':node['inputs'][0]='recruited_evidence'
        if node['op']=='nominate':node['params']['method']=late_method
        nodes.append(node)
        if node['id']==source:
            nodes.extend([
                dict(id='early_recruitment',op='nominate',inputs=[source],params={'method':'independent_batches'}),
                dict(id='recruited_evidence',op='nomination_evidence',inputs=['early_recruitment',source],params={'mode':mode})])
            inserted=True
    if not inserted:raise ValueError('Missing walk source')
    p['nodes']=nodes;p['factors']['nomination']=late_method
    p['recruitment_feedback']=dict(mode=mode,placement=placement,early_method='independent_batches')
    return p

"""Explicit placement alternatives for the existing exact-record components."""
from copy import deepcopy

MODES=('off','late','before_nomination','before_walk','contiguous')

def transform(seed,mode):
    if mode not in MODES:raise ValueError('Unknown record assembly mode')
    p=deepcopy(seed);p['record_assembly']={'mode':mode,'component_definition':'exact record, overlapping or touching source ranges','transport':'maximum','serving':'unchanged serialized 72000-character prefix, partial boundary uncredited'}
    nomination=next(n for n in p['nodes'] if n['op']=='nominate' and n['id']=='nomination')
    if mode in ('off','before_nomination'):
        p['nodes']=[n for n in p['nodes'] if n['op']!='recover'];p['output']=nomination['id'];p['factors']['recovery']='off'
    if mode in ('before_nomination','before_walk'):
        consumer=nomination if mode=='before_nomination' else next(n for n in p['nodes'] if n['op'] in ('propagate','directed_propagate'))
        node={'id':'record_component_evidence','op':'record_component_max','inputs':[consumer['inputs'][0]],'params':{}}
        consumer['inputs'][0]=node['id'];p['nodes'].insert(p['nodes'].index(consumer),node)
    if mode=='contiguous':
        p['nodes'].append({'id':'record_component_assembly','op':'record_component_assembly','inputs':[p['output']],'params':{}});p['output']='record_component_assembly'
    return p

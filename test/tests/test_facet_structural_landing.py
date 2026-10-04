import copy
import json
import hashlib

import pytest

from artefact.facet_structural_landing import (
    structural_index, load_structural_index, resolve_structural_area,
)
from artefact.facet_scope_recruitment import recruit_with_verified_area


def payload():
    def node(label, nid, names, route, chunks):
        return {'label':label,'node_id':nid,
                'names':[{'name':name,'kind':kind} for name,kind in names],
                'routes':{route:chunks} if route else {}}
    return {'schema_version':1,'graph_sha256':'frozen-graph','database':'synthetic',
        'eligible_chunk_ids':['a','b','c','d'], 'nodes':[
            node('Product','Pegasus',[('Pegasus','product')],'product_chunk',['a','b']),
            node('Product','Orion',[('Orion','product')],'product_chunk',['c','d']),
            node('Employee','e1',[('Sam Reed','full'),('Sam','first')],'employee_channel',['a','c']),
            node('Employee','e2',[('Sam West','full'),('Sam','first')],'employee_channel',['b']),
            node('Channel','release',[('release-room','channel')],'channel_chunk',['a']),
            node('Company','co',[('UnroutedCo','company')],None,[]),
        ]}


def index(value=None):
    return structural_index(value or payload(),graph_sha256='frozen-graph',eligible_chunk_ids=['a','b','c','d'])


def test_person_product_and_channel_walks_meet_on_real_memberships():
    area,meta=resolve_structural_area('What did Sam Reed decide on Pegasus in release-room?',index())
    assert area=={'a'} and meta['status']=='resolved'
    assert [x['name'] for x in meta['landings']]==['pegasus','release-room','sam reed']


def test_alias_keeps_all_nodes_and_no_arbitrary_disambiguation():
    area,meta=resolve_structural_area('Sam on Pegasus',index())
    assert area=={'a','b'} and meta['status']=='resolved_multiple_nodes'
    sam=next(x for x in meta['landings'] if x['name']=='sam')
    assert {n['node_id'] for n in sam['node_bindings']}=={'e1','e2'}


def test_containment_applies_per_occurrence_not_per_name():
    _,meta=resolve_structural_area('Sam Reed spoke to Sam.',index())
    assert {x['name']:x['spans'] for x in meta['landings']}=={
        'sam reed':[[0,8]], 'sam':[[18,21]]}


def test_one_lexical_mention_across_node_kinds_is_a_union():
    value=payload()
    value['nodes'].append({'label':'Channel','node_id':'same-name',
        'names':[{'name':'Pegasus','kind':'channel'}],'routes':{'channel_chunk':['c']}})
    area,meta=resolve_structural_area('Pegasus',index(value))
    assert area=={'a','b','c'} and len(meta['landings'])==1


@pytest.mark.parametrize('text,status,combined',[
    ('general update','no_landing',None),
    ('UnroutedCo on Pegasus','unreachable_landing',[]),
    ('Pegasus versus Orion','empty_intersection',[]),
    ('Pegasuss','no_landing',None),
    ('PegasusExtended','no_landing',None),
])
def test_unresolved_and_empty_states_never_silently_select_an_area(text,status,combined):
    area,meta=resolve_structural_area(text,index())
    assert area is None and meta['status']==status and meta['combined_chunk_ids']==combined


def test_node_and_name_order_do_not_change_result():
    original=payload(); reordered=copy.deepcopy(original)
    reordered['nodes'].reverse()
    for node in reordered['nodes']:node['names'].reverse()
    assert resolve_structural_area('Sam on Pegasus',index(original))==resolve_structural_area('Sam on Pegasus',index(reordered))


def test_global_route_remains_available_after_landing():
    chunks=[{'chunkId':c,'locator':{},'relpath':'synthetic','source_text':'unit'} for c in 'abcd']
    area,meta=resolve_structural_area('Sam Reed on Pegasus',index())
    result=recruit_with_verified_area(chunk_rows=chunks,joint_scores=[.7,.2,.9,.1],
        area_chunk_ids=area,area_provenance=meta,source_character_budget=None)
    assert set(result['recruitment']['selected_chunk_ids'])==set('abcd')
    assert result['area']['chunk_ids']==['a']


def test_capture_rejects_wrong_graph_universe_or_route_endpoints():
    for field,value in [('graph_sha256','other'),('eligible_chunk_ids',['a','b','c'])]:
        bad=payload();bad[field]=value
        with pytest.raises(ValueError):index(bad)
    bad=payload();bad['nodes'][0]['routes']['product_chunk'].append('outside')
    with pytest.raises(ValueError):index(bad)


def test_capture_file_is_hash_pinned(tmp_path):
    path=tmp_path/'capture.json';path.write_text(json.dumps(payload()))
    sha=hashlib.sha256(path.read_bytes()).hexdigest()
    result=load_structural_index(path,sha256=sha,graph_sha256='frozen-graph',eligible_chunk_ids='abcd')
    assert result.provenance['structural_capture_sha256']==sha
    with pytest.raises(ValueError,match='hash mismatch'):
        load_structural_index(path,sha256='changed',graph_sha256='frozen-graph',eligible_chunk_ids='abcd')


def test_unicode_matching_uses_the_same_equivalence_as_alias_grouping():
    value=payload()
    for name,cid in [('Iris','a'),('İris','b'),('Straße','c')]:
        value['nodes'].append({'label':'Channel','node_id':name,
            'names':[{'name':name,'kind':'channel'}],'routes':{'channel_chunk':[cid]}})
    held=index(value)
    assert resolve_structural_area('Iris',held)[0]=={'a'}
    assert resolve_structural_area('İris',held)[0]=={'b'}
    area,meta=resolve_structural_area('STRASSE',held)
    assert area=={'c'} and meta['landings'][0]['spans']==[[0,7]]
    area,meta=resolve_structural_area('Straße',held)
    assert area=={'c'} and meta['landings'][0]['spans']==[[0,6]]

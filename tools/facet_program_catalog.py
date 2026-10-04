"""Named structural hypotheses compiled into inspectable dataflow programs."""
from itertools import combinations

FACTORS={
 'matching':('product','maximum','minimum','tag_only','description_only'),
 'edge':('maximum','mean','sum'),
 'query':('maximum','mean','minimum'),
 'facet_binding':('separate','same_path'),
 'path':('parallel','direct','adjacency','groups','adjacency_then_group','group_then_adjacency','product'),
 'path_merge':('maximum','sum','mean'),
 'path_support':('maximum','mean','sum'),
 'attenuation':(.5,1.),
 'join':('union','intersection','graph_only','exclusive'),
 'description':('destination','seed','independent','off'),
 'recruitment':('joint','facets','queries','routes'),
 'nomination':('automatic','best_rank','independent_batches','all_streams'),
 'scope':('saved','seed_union','seed_intersection'),
 'admission':('equal_depth','area_first','area_only'),
 'scope_stage':('after_paths','before_paths'),
 'recovery':('on','off'),
}
DEFAULT={k:v[0] for k,v in FACTORS.items()}


def build(raw):
 p={**DEFAULT,**raw}
 if set(p)!=set(FACTORS) or any(p[k] not in v for k,v in FACTORS.items()):raise ValueError('Unknown factor')
 if p['path']=='direct' and (p['join']!='union' or p['recruitment']=='routes'):raise ValueError('No graph route to join/recruit')
 if p['facet_binding']=='same_path' and p['recruitment']=='facets':raise ValueError('Early facet collapse cannot retain independent facet streams')
 if p['path']!='parallel' and p['path_merge']!='maximum':raise ValueError('Path merge requires parallel graph routes')
 nodes=[]
 def node(name,op,inputs=(),**params):
  nodes.append({'id':name,'op':op,'inputs':list(inputs),'params':params});return name
 def source(name):
  nodes.append({'id':name,'op':'source','inputs':[],'params':{'name':name}});return name
 for name in ['tag_match','tag_description','edge_facets','query_facets','coefficients','whole_description','query_description','saved_area']:
  source(name)
 matching=p['matching']
 if matching in ('product','maximum','minimum'):match=node('matching',{'product':'multiply','maximum':'maximum','minimum':'minimum'}[matching],['tag_match','tag_description'])
 else:match='tag_match' if matching=='tag_only' else 'tag_description'
 edge=node('edge_evidence','multiply',[match,'query_facets','edge_facets'])
 if p['description']=='seed':
  source('whole_description_edge');edge=node('description_at_seed','multiply',[edge,'whole_description_edge'])
 weighted=p['facet_binding']=='same_path'
 if weighted:
  edge=node('weight_same_edge','multiply',[edge,'coefficients'])
  edge=node('facets_on_same_edge','reduce',[edge],axis='facet',method='sum')
 direct=node('direct','edges_to_chunks',[edge],method=p['edge'])
 def facets(value,name):
  if not weighted:value=node(name+'_weights','multiply',[value,'coefficients'])
  return node(name,'reduce',[value],axis='facet',method='sum')
 if p['scope']=='saved':area='saved_area'
 else:
  discovery=facets(direct,'discovery_evidence')
  peaks=node('query_seeds','peaks',[discovery])
  regions=node('reachable_regions','reach',[peaks],relations=['adjacency','groups'])
  area=node('discovered_area','region_join',[regions],method=p['scope'].removeprefix('seed_'))
 if p['scope_stage']=='before_paths':direct=node('scope_before_paths','mask',[direct,area])
 def propagate(name,value,relation):
  return node(name,'propagate',[value,'query_description'],relation=relation,decay=p['attenuation'],aggregation=p['path_support'])
 graph=None
 if p['path']=='parallel':
  adjacent=propagate('adjacent',direct,'adjacency');grouped=propagate('grouped',direct,'groups')
  graph=node('graph',{'maximum':'maximum','sum':'add','mean':'average'}[p['path_merge']],[adjacent,grouped])
 elif p['path'] in ('adjacency','groups'):graph=propagate('graph',direct,p['path'])
 elif p['path']=='adjacency_then_group':graph=propagate('graph',propagate('adjacent',direct,'adjacency'),'groups')
 elif p['path']=='group_then_adjacency':graph=propagate('graph',propagate('grouped',direct,'groups'),'adjacency')
 elif p['path']=='product':graph=propagate('graph',direct,'product')
 joined=(node('joined',{'union':'maximum','intersection':'minimum','exclusive':'exclusive'}[p['join']],[direct,graph]) if p['join']!='graph_only' else graph) if graph else direct
 def query(value,name):return node(name,'reduce',[value],axis='query',method=p['query'])
 def scalar(value,name):return facets(query(value,name+'_query'),name)
 if p['recruitment']=='joint':streams=scalar(joined,'joint_stream')
 elif p['recruitment']=='facets':
  streams=query(joined,'facet_streams')
  streams=node('facet_stream_weights','multiply',[streams,'coefficients'])
 elif p['recruitment']=='queries':streams=facets(joined,'query_streams')
 else:
  route_streams=[]
  if p['join']!='graph_only':route_streams.append(scalar(node('direct_gate','minimum',[direct,joined]),'direct_stream'))
  route_streams.append(scalar(node('graph_gate','minimum',[graph,joined]),'graph_stream'))
  streams=node('route_streams','concat',route_streams)
 if p['description']=='destination':streams=node('description_at_destination','multiply',[streams,'whole_description'])
 elif p['description']=='independent':streams=node('description_stream','concat',[streams,'whole_description'])
 method='best_rank' if p['recruitment']=='joint' and p['description']!='independent' else 'independent_batches'
 if p['nomination']!='automatic':method=p['nomination']
 nomination=node('nomination','nominate',[streams,area],method=method,admission=p['admission'])
 if p['recovery']=='on':nomination=node('recovery','recover',[nomination]+([area] if p['admission']=='area_only' else []))
 return {'schema_version':1,'factors':p,'nodes':nodes,'output':nomination,'streams_node':streams,'area_node':area}


def catalog():
 """All valid single and pair changes around the reference, plus named interactions."""
 settings=[DEFAULT]
 for k,values in FACTORS.items():
  for v in values[1:]:settings.append({**DEFAULT,k:v})
 for a,b in combinations(FACTORS,2):
  for va in FACTORS[a][1:]:
   for vb in FACTORS[b][1:]:settings.append({**DEFAULT,a:va,b:vb})
 # All parts active together, declared before looking at results. No fitted weights.
 for recruitment in ['facets','queries','routes']:
  for scope in ['seed_union','seed_intersection']:
   settings.append({**DEFAULT,'edge':'mean','query':'mean','path':'adjacency_then_group',
       'attenuation':1.,'description':'independent','recruitment':recruitment,'scope':scope,'admission':'area_first'})
 # Preserve the exact structural context of the previous verified best.
 settings.append({**DEFAULT,'matching':'maximum','path':'groups','join':'intersection',
                  'query':'mean','admission':'area_first'})
 programs=[];seen=set()
 for setting in settings:
  try:program=build(setting)
  except ValueError:continue
  key=tuple(setting.items())
  if key in seen:continue
  seen.add(key);program['id']=f'program_{len(programs):03d}';programs.append(program)
 return programs

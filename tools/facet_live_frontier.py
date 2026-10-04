"""Display adapter for the sealed tag-frontier experiment's numeric states."""
from artefact.facet_construction_program import Signal,Nomination
from artefact.facet_tag_frontier import edge_gate,inject
from artefact.facet_tag_frontier_engine import run_program
from artefact.facet_tag_frontier_controls import gate_from_depths,tag_arrival,tier_priority_order
from artefact.facet_directed_frontier_engine import run_program as run_directed_frontier
from facet_directed_values import project
from facet_directed_lab import L,SNAPSHOT

def compiled(program):
    if any(n['id']=='tag_frontier_gate' for n in program['nodes']):return program
    return inject(program)

def execute(lab,case,program):
    graph=lab.route_graphs.get(program.get('graph_route'),lab.graph)
    policy=program.get('tag_frontier_followup')
    if policy:
        _,frontier=edge_gate(graph,case['matrices'],case['weights'],evidence='query_only',streams=policy['streams'],sponsors='all')
        gate=gate_from_depths(frontier['edge_depths'],graph.edge_chunk,lab.n,sponsors=policy['sponsors'],weighting=policy['weighting'])
    else:gate,frontier=edge_gate(graph,case['matrices'],case['weights'],**program['tag_frontier'])
    backend=run_program;extra={}
    if any(n['op']=='directed_propagate' for n in program['nodes']):
        if not hasattr(lab,'directed_routes'):lab.directed_routes=project(lab.graph.chunk_ids,L.read(SNAPSHOT))
        backend=run_directed_frontier;extra['directed_routes']=lab.directed_routes
    result=backend(compiled(program),graph,case['matrices'],case['weights'],case['area'],
        lab.components,lab.id_order,cache=None,frontier_gate=gate,**extra)
    # A sealed engine copy has separate dataclass identities. Adapt types only;
    # arrays, nomination depths, sponsors and final order remain unchanged.
    result['states']={name:Signal(x.values,x.domain) if hasattr(x,'values') else
        Nomination(x.depth,x.original,x.sponsors) for name,x in result['states'].items()}
    result['final']=result['states'][program['output']]
    result['frontier_summary']={k:v for k,v in frontier.items() if not hasattr(v,'shape')}
    if policy and policy['arrival']!='none':
        groups=[g for collection in graph.groups.values() for g in collection]
        arrival,_=tag_arrival(frontier['tag_scores'],graph.edge_tag,graph.edge_chunk,lab.n,groups,lab.components,policy=policy['arrival'])
        result['order']=tier_priority_order(result['order'],arrival,case['area'])
        result['tag_arrival']=arrival
    return result

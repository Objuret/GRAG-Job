"""Read only opaque Employee manages endpoints and eligible chunk memberships."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'test'),str(ROOT/'prod'),str(ROOT/'tools')]
from facet_structural_routes import SNAPSHOT,EXPECTED_SHA
from facet_program_lab import L

OUT=ROOT/'output/research/2026-09-24-directed-routes'

def capture():
    from graph.db import _driver
    from artefact.landing import ROUTES
    if L.digest(SNAPSHOT)!=EXPECTED_SHA:raise ValueError('Frozen structural snapshot changed')
    frozen=L.read(SNAPSHOT)
    employees={r['node_id']:{k:v for k,v in r['routes'].items()} for r in frozen['nodes'] if r['label']=='Employee'}
    manifest=L.read(ROOT/'output/research/2026-09-21-facet-validity/route_snapshot/manifest.json')
    query=manifest['query_strings']['chunks'].split('RETURN',1)[0]+'RETURN c.chunk_id AS chunk_id'
    params=dict(datasetId=manifest['dataset_id'],runId=manifest['run_id'],excludedSections=manifest['excluded_sections'])
    def read(tx):
        eligible={str(r['chunk_id']) for r in tx.run(query,**params)}
        edges=sorted({(str(r['source']),str(r['target'])) for r in tx.run('MATCH (a:Employee)-[:manages]->(b:Employee) RETURN a.eid AS source, b.eid AS target')})
        # IDs in this dataset are strings, matching the pinned capture.
        memberships={k:[dict(r) for r in tx.run(ROUTES[k][1],ids=list(employees))] for k in ('employee_channel','employee_product')}
        return eligible,edges,memberships
    with _driver() as driver:
        with driver.session(database=manifest['database'],default_access_mode='READ') as session:eligible,edges,memberships=session.execute_read(read)
    if eligible!=set(frozen['eligible_chunk_ids']):raise ValueError('Eligible population drift')
    for kind,rows in memberships.items():
        actual={eid:set() for eid in employees}
        for r in rows:actual[str(r['node'])].update({str(r['chunk'])}&eligible)
        if actual!={eid:set(routes[kind]) for eid,routes in employees.items()}:raise ValueError('Employee route drift')
    if any(a not in employees or b not in employees for a,b in edges):raise ValueError('Unknown employee endpoint')
    result=dict(eligible_chunk_ids=sorted(eligible),employees=employees,manages_edges=edges,
                validation={'eligible_matches':True,'employee_memberships_match':True},
                provenance={'access_mode':'READ','structural_snapshot_sha256':EXPECTED_SHA,'capture_sha256':L.digest(Path(__file__)),
                'route':'chunk -> Employee -> manages -> Employee -> chunk','meaning':'Relationship hypothesis; no semantic relevance claim'})
    OUT.mkdir(parents=True,exist_ok=True);L.write_new(OUT/'directed-snapshot.json',result)
    print(json.dumps({'eligible':len(eligible),'employees':len(employees),'manages_edges':len(edges),'route_memberships_verified':{k:sum(len(r[k]) for r in employees.values()) for k in memberships}}))

if __name__=='__main__':capture()

"""Bounded per-query facet priority comparison, original95 plus canonical guard."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
from facet_program_lab import ProgramLab,L,plan as base_plan
from facet_program_catalog import build
from artefact.facet_query_priority import run_program
from artefact.facet_construction_program import Signal,Nomination
import facet_joint_search as runner

SELECTION=L.ROOT/'output/research/2026-09-24-structural-selection'
OUT=L.ROOT/'output/research/2026-09-24-query-priority'


def execute(lab,case,program):
    graph=getattr(lab,'route_graphs',{}).get(program.get('graph_route'),lab.graph)
    r=run_program(program,graph,case['matrices'],case['weights'],case['area'],lab.components,lab.id_order)
    r['states']={name:Signal(x.values,x.domain) if hasattr(x,'values') else
        Nomination(x.depth,x.original,x.sponsors) for name,x in r['states'].items()}
    r['final']=r['states'][program['output']]
    return r


class PriorityLab(ProgramLab):
    def execute(self,case,program):
        return execute(self,case,program) if 'query_priority' in program else super().execute(case,program)


def programs():
    ref=build({});ref.update(id='query_priority_reference',graph_route='product_channel');result=[ref]
    for name in ('best-total-hits','best-macro-recall'):
        parent=deepcopy(L.read(SELECTION/(name+'.json'))['program'])
        parent.update(id='query_priority_'+name+'_control',graph_route='product_channel');result.append(parent)
        for method in ('scalar','lexicographic'):
            for sponsors in ('first','all'):
                p=deepcopy(parent);p['id']='query_priority_'+name+'_'+method+'_'+sponsors
                p['query_priority']={'method':method,'sponsors':sponsors};result.append(p)
    return result


def plan(smoke=False):
    p=base_plan();p['programs']=programs();p['smoke_only']=smoke
    if smoke:p['case_ids']=p['case_ids'][:1]
    p['coverage']='Two unchanged parents; outgoing-facet per-query tag priority scalar versus lexicographic, first versus all sponsors. Query priorities descending per query tag, canonical facet index on tied relevance, zeros omitted. No bands or candidate cap; complete tied tuples share tiers. Downstream graph/description/scope unchanged.'
    p['parent_sha256']={str(f.relative_to(L.ROOT)):L.digest(f) for f in (SELECTION/'best-total-hits.json',SELECTION/'best-macro-recall.json',SELECTION/'selection-manifest.json')}
    for f in (Path(__file__),L.ROOT/'test/artefact/facet_query_priority.py',L.ROOT/'test/artefact/facet_tag_frontier.py',L.ROOT/'test/artefact/facet_tag_frontier_controls.py',L.ROOT/'test/artefact/facet_tag_frontier_engine.py',L.ROOT/'tools/facet_joint_search.py'):
        p['input_sha256'][str(f.relative_to(L.ROOT))]=L.digest(f)
    return p


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('command',choices=('plan','batch'))
    ap.add_argument('--out',type=Path,default=OUT);ap.add_argument('--smoke',action='store_true');a=ap.parse_args()
    if a.command=='plan':
        p=plan(a.smoke);a.out.mkdir(parents=True,exist_ok=True);L.write_new(a.out/'plan.json',p)
        print(json.dumps({'programs':len(p['programs']),'cases':len(p['case_ids'])}))
    else:runner.RouteLab=PriorityLab;runner.batch(a.out)

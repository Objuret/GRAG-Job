"""Compare evidence-based nomination ties, preserving every earlier tier."""
import argparse
import json
from pathlib import Path
from facet_program_lab import L,plan as base_plan
from facet_program_catalog import build
from facet_fast_resume import FastLab
from artefact.facet_nomination_ties import reorder,METHODS
import facet_joint_search as runner

class TieLab(FastLab):
    def execute(self,case,program):
        return reorder(super().execute(case,program),program,self.id_order)

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('command',choices=['plan','batch']);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--smoke',action='store_true');args=ap.parse_args()
    if args.command=='plan':
        parent=L.ROOT/'output/research/2026-09-24-structural-selection'
        programs=[{**build({}),'id':'ties_reference','graph_route':'product_channel'}]
        for name in ('best-total-hits','best-macro-recall'):
            seed=L.read(parent/(name+'.json'))['program']
            for method in METHODS:
                programs.append({**seed,'id':f'ties_{len(programs):03d}','tie_break':method,'tie_seed':name})
        p=base_plan();p.update(programs=programs,parent_sha256={},smoke_only=args.smoke,
            coverage='Six within-tier order rules in both selected constructions. Nomination depths, recovery priority and candidate access unchanged; no body, cost or gold enters ranking.')
        if args.smoke:p['case_ids']=p['case_ids'][:1]
        for file in [Path(__file__),L.ROOT/'test/artefact/facet_nomination_ties.py',L.ROOT/'tools/facet_fast_resume.py',L.ROOT/'tools/facet_joint_search.py',L.ROOT/'test/artefact/facet_construction_fast.py']:
            p['input_sha256'][str(file.relative_to(L.ROOT))]=L.digest(file)
        for name in ('best-total-hits','best-macro-recall','selected-rule-audit'):
            file=parent/(name+'.json');p['parent_sha256'][str(file.relative_to(L.ROOT))]=L.digest(file)
        args.out.mkdir(parents=True,exist_ok=True);L.write_new(args.out/'plan.json',p)
        print(json.dumps({'programs':len(programs),'cases':len(p['case_ids'])}))
    else:
        runner.RouteLab=TieLab;runner.batch(args.out)

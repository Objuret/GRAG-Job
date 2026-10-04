"""Deliver graph-grounded scope alternatives through the structural testbench."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import facet_joint_search as runner
from facet_fast_resume import FastLab
from facet_program_lab import L, plan as base_plan
from facet_program_catalog import build
from facet_scope_capture import OUT as SCOPE_INPUTS
from artefact.facet_scope_alternatives import scope_catalog, form_scope


class ScopeOverride:
    def execute(self, case, program):
        if 'scope_policy' not in program:
            return super().execute(case, program)
        if program['factors']['scope'] != 'saved':
            raise ValueError('Structural scope input requires the saved-area source node')
        cid=case['meta']['case_id']
        capture=L.read(SCOPE_INPUTS/(cid+'.json'))
        area,_=form_scope(capture['landings'],self.ids,program['scope_policy'])
        mask=None if area is None else np.array([cid in area for cid in self.ids])
        # Copy the case adapter; never mutate the frozen numeric capture.
        return super().execute({**case,'area':mask},program)


class ScopeLab(ScopeOverride,FastLab):
    pass


def plan(smoke=False):
    p=base_plan();manifest=L.read(SCOPE_INPUTS/'manifest.json')
    captures={cid:L.read(SCOPE_INPUTS/(cid+'.json')) for cid in p['case_ids']}
    for cid,sha in manifest['case_sha256'].items():
        if L.digest(SCOPE_INPUTS/(cid+'.json'))!=sha:raise ValueError('Scope capture changed')
    eligible=L.read(L.INPUTS/'cases_manifest.json')['chunk_ids']
    groups={}
    for policy in scope_catalog():
        masks=[]
        for cid,capture in captures.items():
            area,_=form_scope(capture['landings'],eligible,policy)
            masks.append(None if area is None else sorted(area))
        signature=hashlib.sha256(json.dumps(masks).encode()).hexdigest()
        if signature not in groups:groups[signature]={'policy':policy,'aliases':[]}
        groups[signature]['aliases'].append(policy)
    programs=[{**build({}),'id':'scope_reference','graph_route':'product_channel'}]
    contexts=[('mean_groups',dict(matching='maximum',query='mean',path='groups',join='intersection'),'product_channel'),
              ('entity_sequence',dict(path='adjacency_then_group',join='intersection'),'employee_intersection')]
    for context,factors,route in contexts:
        for recruitment in ('joint','facets'):
            for admission in ('equal_depth','area_first','area_only'):
                for stage in ('before_paths','after_paths'):
                    base=build({**factors,'recruitment':recruitment,'admission':admission,'scope_stage':stage})
                    for signature,group in [('frozen',None),*groups.items()]:
                        program={**base,'graph_route':route,'id':'scope_'+str(len(programs)).zfill(4),
                                 'scope_input_signature':signature,'context_name':context}
                        if group is not None:program['scope_policy']=group['policy']
                        programs.append(program)
    p.update(programs=programs,parent_sha256={},scope_mask_groups=groups,
             smoke_only=smoke,coverage='Graph-name scope formation crossed with recruitment, admission, traversal timing, and two structural contexts. Identical mask sequences collapsed only on these 95 captured cases.')
    if smoke:p['case_ids']=p['case_ids'][:1]
    for file in [Path(__file__),L.ROOT/'tools/facet_scope_capture.py',
                 L.ROOT/'test/artefact/facet_scope_alternatives.py',L.ROOT/'tools/facet_joint_search.py',
                 L.ROOT/'tools/facet_fast_resume.py',L.ROOT/'test/artefact/facet_construction_fast.py',
                 L.ROOT/'tools/facet_route_program_lab.py',L.ROOT/'tools/facet_structural_routes.py',
                 SCOPE_INPUTS/'manifest.json',*[SCOPE_INPUTS/(cid+'.json') for cid in captures]]:
        p['input_sha256'][str(file.relative_to(L.ROOT))]=L.digest(file)
    return p


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('command',choices=['plan','batch']);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--smoke',action='store_true');args=ap.parse_args()
    if args.command=='plan':
        p=plan(args.smoke);args.out.mkdir(parents=True,exist_ok=True);L.write_new(args.out/'plan.json',p)
        print(json.dumps({'programs':len(p['programs']),'distinct_scope_sequences':len(p['scope_mask_groups']),'cases':len(p['case_ids'])}))
    else:
        runner.RouteLab=ScopeLab;runner.batch(args.out)

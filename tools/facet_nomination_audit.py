"""Measure how often the 72k cut splits an ID-ordered nomination tie."""
import json
from pathlib import Path
import numpy as np
from facet_fast_resume import FastLab
from facet_program_lab import L


if __name__ == '__main__':
    lab=FastLab()
    programs=[]
    for folder,pid in [('construction-programs-fast','program_000'),
                       ('construction-programs-fast','program_692'),
                       ('entity-route-programs-fast','route_179')]:
        plan=L.read(L.ROOT/('output/research/2026-09-23-'+folder)/'plan.json')
        programs.append(next(p for p in plan['programs'] if p['id']==pid))
    rows=[]
    for item in lab.manifest['cases']:
        case=lab.load(item['case_id'])
        for program in programs:
            result=lab.execute(case,program)
            delivery=lab.delivery(result)
            order=result['order'];final=result['final'];cut=len(delivery['full'])
            # The last fully delivered chunk and the next chunk lie inside the
            # same exact primary ordering tier only if ID determined this cut.
            split=False;size=0;before=0
            if 0<cut<len(order):
                last,next_chunk=order[cut-1],order[cut]
                recovered=final.original!=final.depth
                split=bool(final.depth[last]==final.depth[next_chunk] and recovered[last]==recovered[next_chunk])
                if split:
                    mask=(final.depth[order]==final.depth[last]) & (recovered[order]==recovered[last])
                    size=int(mask.sum());before=int(mask[:cut].sum())
            rows.append(dict(case_id=item['case_id'],program_id=program['id'],
                             id_tie_split_by_budget=split,tier_chunks=size,tier_full_chunks=before))
        print(json.dumps({'completed_cases':len(rows)//len(programs)}),flush=True)
    report={p['id']:dict(cases=sum(r['program_id']==p['id'] for r in rows),
              cut_tie_cases=sum(r['id_tie_split_by_budget'] for r in rows if r['program_id']==p['id']),
              maximum_split_tier=max(r['tier_chunks'] for r in rows if r['program_id']==p['id'])) for p in programs}
    out=L.ROOT/'output/research/2026-09-23-nomination-audit'
    out.mkdir(parents=True,exist_ok=True)
    L.atomic(out/'results.json',{'summary':report,'cases':rows,
        'meaning':'ID resolves exact ties in nomination depth and recovery priority. No gold was used to identify split ties; delivery sizes were applied after retrieval.'})
    print(json.dumps(report),flush=True)

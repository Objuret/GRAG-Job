"""Run the declared reduction/gating/feedback construction comparison."""
import argparse
from pathlib import Path
import json
import facet_joint_search as runner
from facet_fast_resume import FastLab
from facet_ordering_programs import catalog
from facet_program_lab import plan as base_plan, L


def plan(smoke=False):
    result = base_plan()
    result.update(programs=catalog(), parent_sha256={},
                  coverage='Cross reduction before edges / before graph / after graph with destination description each step / after walk / off, walk depths 1 / 2 / 4, latest-step versus retained-seed feedback, joint / facet recruitment, product / maximum matching, and two graph projections.',
                  selection='Declared structural hypotheses, no per-case gold selection; finite-depth experiment, no convergence or exhaustive-optimum claim.',
                  smoke_only=smoke)
    if smoke:
        result['case_ids'] = result['case_ids'][:1]
    for path in [Path(__file__), L.ROOT/'tools/facet_ordering_programs.py',
                 L.ROOT/'tools/facet_joint_search.py', L.ROOT/'tools/facet_fast_resume.py',
                 L.ROOT/'tools/facet_route_program_lab.py', L.ROOT/'tools/facet_structural_routes.py',
                 L.ROOT/'test/artefact/facet_construction_fast.py']:
        result['input_sha256'][str(path.relative_to(L.ROOT))] = L.digest(path)
    return result


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('command', choices=['plan', 'batch'])
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--smoke', action='store_true')
    args = ap.parse_args()
    if args.command == 'plan':
        p = plan(args.smoke)
        args.out.mkdir(parents=True, exist_ok=True)
        L.write_new(args.out/'plan.json', p)
        print(json.dumps({'cases':len(p['case_ids']), 'programs':len(p['programs']), 'smoke':args.smoke}))
    else:
        runner.RouteLab = FastLab
        runner.batch(args.out)
        p = L.read(args.out/'plan.json')
        metadata = {x['id']:x['ordering'] for x in p['programs']}
        rows = L.read(args.out/'report.json')
        for row in rows:
            row['ordering'] = metadata[row['program_id']]
        L.atomic(args.out/'report.json', rows)

"""Ordering experiment with the explicit canonical reference required by verification."""
import argparse
import json
from pathlib import Path
import facet_ordering_lab as original
from facet_program_catalog import build
from facet_fast_resume import FastLab


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('command', choices=['plan', 'batch'])
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--smoke', action='store_true')
    args = ap.parse_args()
    L = original.L
    if args.command == 'plan':
        p = original.plan(args.smoke)
        reference = {**build({}), 'id':'ordering_reference', 'graph_route':'product_channel',
                     'ordering':{'reference':True}}
        p['programs'].insert(0, reference)
        p['input_sha256'][str(Path(__file__).relative_to(L.ROOT))] = L.digest(Path(__file__))
        args.out.mkdir(parents=True, exist_ok=True)
        L.write_new(args.out/'plan.json', p)
        print(json.dumps({'cases':len(p['case_ids']), 'programs':len(p['programs']), 'smoke':args.smoke}))
    else:
        original.runner.RouteLab = FastLab
        original.runner.batch(args.out)
        p = L.read(args.out/'plan.json')
        metadata = {x['id']:x['ordering'] for x in p['programs']}
        rows = L.read(args.out/'report.json')
        for row in rows:
            row['ordering'] = metadata[row['program_id']]
        L.atomic(args.out/'report.json', rows)

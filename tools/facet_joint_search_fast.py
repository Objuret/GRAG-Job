"""Run the unchanged higher-order search with the parity-verified fast backend.

Backend dependency injection is local to this entry point. Original search code,
old engines and sealed experiments remain unchanged on disk.
"""
import argparse
from pathlib import Path
import json
import facet_joint_search as search
from facet_fast_resume import FastLab


if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('command',choices=['plan','batch'])
 ap.add_argument('--parent',type=Path,action='append');ap.add_argument('--out',type=Path,required=True)
 args=ap.parse_args();search.RouteLab=FastLab
 if args.command=='plan':
  if not args.parent:ap.error('Completed parent experiments required')
  planned=search.make_plan([p.resolve() for p in args.parent])
  for file in [Path(__file__),search.L.ROOT/'tools/facet_fast_resume.py',
               search.L.ROOT/'test/artefact/facet_construction_fast.py']:
   planned['input_sha256'][str(file.relative_to(search.L.ROOT))]=search.L.digest(file)
  planned['runtime_backend']='Parity-verified exact query-row duplicate optimization; unchanged search and retrieval construction'
  args.out.mkdir(parents=True,exist_ok=True);search.L.write_new(args.out/'plan.json',planned)
  print(json.dumps({'programs':len(planned['programs']),'seeds':len(planned['seeds'])}))
 else:search.batch(args.out)

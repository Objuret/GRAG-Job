"""Additive numerical capture of the four successful interpretation retries.

No new interpretation or judge calls. Query text and generated interpretation
remain private; source bodies and gold are not inputs to numerical capture.
Run when enough RAM is available for the pinned local float32 embedder.
"""
from pathlib import Path
from types import SimpleNamespace
from collections import defaultdict
import ast
import contextlib
import hashlib
import json
import os
import re
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'test'),str(ROOT/'prod'),str(ROOT/'tools')]
RETRY=ROOT/'output/research/2026-09-22-retrieval-retry5'
OUT=RETRY/'numeric_inputs'
ORIGINAL=ROOT/'output/research/2026-09-22-structural-landings/pre-repair/artefact_facet_joint.py'


def read(p):return json.loads(p.read_text(encoding='utf-8'))
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write_new(p,v):
 if p.exists():
  if read(p)!=v:raise ValueError('Existing capture differs: '+p.name)
 else:
  with p.open('x',encoding='utf-8') as f:json.dump(v,f,indent=2,allow_nan=False)


def capture():
 OUT.mkdir(exist_ok=True);private=RETRY/'private';completed=read(RETRY/'interpretation_completed.json')
 with (private/'numeric_capture.log').open('a',encoding='utf-8') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
  from arms import artefact_facet_joint as A
  from artefact.facet_operator_matrix import score_families
  prepared=A.prepare_over_corpus(ROOT/'data/corpus/Salesforce__HERB')
 ids=[c['chunkId'] for c in prepared.chunks];members=defaultdict(set)
 for c in prepared.chunks:
  for p in c['scope'].get('product',[]):members[p['name']].add(c['chunkId'])
 # Reuse the original scope function, not the newer structural-name resolver.
 function=next(n for n in ast.parse(ORIGINAL.read_text(encoding='utf-8')).body if isinstance(n,ast.FunctionDef) and n.name=='_literal_area')
 namespace={'re':re};exec(compile(ast.Module(body=[function],type_ignores=[]),str(ORIGINAL),'exec'),namespace)
 scope_input=SimpleNamespace(product_members=members)
 embedding_input=SimpleNamespace(tag_vectors=prepared.tag_vectors,chunk_vectors=prepared.chunk_vectors)
 scoring_input=SimpleNamespace(chunks=(None,)*len(ids),edge_tag=prepared.edge_tag,edge_chunk=prepared.edge_chunk,
  edge_facets=prepared.edge_facets,reference=prepared.reference,groups=prepared.groups,adjacency_pairs=prepared.adjacency_pairs)
 files=[Path(__file__),ORIGINAL,RETRY/'interpretation_completed.json',ROOT/'prod/harness/embed.py']
 files += [ROOT/p for p in A.SMOKE_PROVENANCE_PATHS]
 files += [private/'interpreted'/(cid+'.json') for cid in completed['successful_cases']]
 hashes={str(p.relative_to(ROOT)):digest(p) for p in files}
 plan={'cases':completed['successful_cases'],'failed_cases':completed['failed_cases'],'input_sha256':hashes,
  'scope_policy':'Original single literal Product scope, original function reused; separate from current structural resolver.',
  'language_model_calls':0,'gold_read':False,'old_95_manifest_modified':False}
 write_new(OUT/'plan.json',plan);records=[]
 for cid in completed['successful_cases']:
  target=OUT/(cid+'.json');npz=OUT/(cid+'.npz');held=read(private/'interpreted'/(cid+'.json'))
  if target.exists():
   meta=read(target)
   if digest(npz)!=meta['npz_sha256'] or meta['interpretation_sha256']!=digest(private/'interpreted'/(cid+'.json')):raise ValueError('Existing numeric capture differs')
  else:
   generation=held['generation'];weights=np.asarray(held['weights'],dtype=float)
   with (private/'numeric_capture.log').open('a',encoding='utf-8') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
    matrices,usage,recipe=A._query_cosines(generation['description'],generation['tags'],embedding_input)
   area,provenance=namespace['_literal_area'](held['question'],scope_input)
   family=next(v for p,v in score_families(scoring_input,matrices,weights) if p==dict(match='product',topology='both',graph_join='union',facet='separate_facet_sum'))
   scores=family[0]*np.maximum(matrices['query_description_cosines'],0)
   arrays={**matrices,'query_facet_weights':weights}
   if npz.exists():
    with np.load(npz,allow_pickle=False) as old:
     if set(old.files)!=set(arrays) or any(not np.array_equal(old[k],v) for k,v in arrays.items()):raise ValueError('Orphan numeric arrays differ')
   else:
    temp=npz.with_suffix('.npz.partial')
    with temp.open('wb') as f:np.savez_compressed(f,**arrays)
    os.rename(temp,npz)
   meta={'case_id':cid,'question_id':held['question_id'],'cohort':'recovered_interpretation',
    'area':{'chunk_ids':None if area is None else sorted(area),'provenance':provenance},
    'expected_scores':scores.tolist(),'expected_scores_origin':'Recomputed reference, not a historical successful retrieval',
    'npz_sha256':digest(npz),'interpretation_sha256':digest(private/'interpreted'/(cid+'.json')),
    'embedding':recipe,'embedding_mode':'new_local_capture_from_saved_interpretation','language_model_calls':0}
   write_new(target,meta)
  records.append({'case_id':cid,'question_id':meta['question_id'],'npz':npz.name,'meta':target.name})
  print(json.dumps({'case_id':cid,'numeric_capture_verified':True}),flush=True)
 if any(digest(ROOT/p)!=h for p,h in hashes.items()):raise ValueError('Capture dependency changed')
 write_new(OUT/'cases_manifest.json',{'cases':records,'chunk_ids':ids,'failed_cases':completed['failed_cases'],
  'expected_cases':len(records),'population':'Four recovered cases only; not merged with the sealed 95-case experiment',
  'input_sha256':hashes,'language_model_calls':0,'gold_read':False})


if __name__=='__main__':capture()

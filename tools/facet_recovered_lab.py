"""Replay the four newly captured cases without altering the sealed 95 inputs."""
from pathlib import Path
import argparse
import hashlib
import json
import numpy as np
from facet_fast_resume import FastLab
from facet_program_lab import L, build, plan as base_plan

CAPTURE=L.ROOT/'output/research/2026-09-22-retrieval-retry5/numeric_inputs'
OUT=L.ROOT/'output/research/2026-09-23-recovered4-retrieval'


def combined_manifest():
 old_path=L.INPUTS/'cases_manifest.json';new_path=CAPTURE/'cases_manifest.json'
 old=L.read(old_path);new=L.read(new_path)
 if old['chunk_ids']!=new['chunk_ids']:raise ValueError('Recovered graph alignment differs')
 for name,sha in new['input_sha256'].items():
  if L.digest(L.ROOT/name)!=sha:raise ValueError('Capture dependency changed')
 records=[]
 for manifest,folder,cohort in [(old,L.INPUTS,'original95'),(new,CAPTURE,'recovered4')]:
  for c in manifest['cases']:
   npz,meta=folder/c['npz'],folder/c['meta'];held=L.read(meta)
   if L.digest(npz)!=held['npz_sha256']:raise ValueError('Numerical file hash differs')
   records.append({'case_id':c['case_id'],'question_id':c['question_id'],'cohort':cohort,
     'npz':str(npz.relative_to(L.ROOT)),'meta':str(meta.relative_to(L.ROOT)),
     'npz_sha256':L.digest(npz),'meta_sha256':L.digest(meta)})
 if len(records)!=99 or len({r['case_id'] for r in records})!=99 or len({r['question_id'] for r in records})!=99:
  raise ValueError('Expected 99 distinct recovered/original identities')
 result={'cases':records,'chunk_ids':old['chunk_ids'],'original_cases':95,'recovered_cases':4,
  'failed_cases':new['failed_cases'],'total_original_question_count':100,
  'old_manifest_sha256':L.digest(old_path),'capture_manifest_sha256':L.digest(new_path),
  'scope':'Same original literal-Product scope procedure; four reference scores recomputed, not historical successful retrievals',
  'population_note':'99 replayable cases, one failed interpretation; original comparisons remain 95-case experiments'}
 target=CAPTURE/'combined99_manifest.json'
 if target.exists():
  if L.read(target)!=result:raise ValueError('Combined index changed')
 else:L.write_new(target,result)
 return result


class RecoveredLab(FastLab):
 def __init__(self):
  super().__init__();self.manifest=combined_manifest();self.registry={c['case_id']:c for c in self.manifest['cases']}
  if self.manifest['chunk_ids']!=self.ids:raise ValueError('Combined graph differs from loaded graph')
 def load(self,cid):
  if cid not in self.loaded:
   rec=self.registry[cid];meta=L.read(L.ROOT/rec['meta']);npz=L.ROOT/rec['npz']
   if L.digest(npz)!=rec['npz_sha256'] or L.digest(L.ROOT/rec['meta'])!=rec['meta_sha256']:raise ValueError('Case inputs changed')
   with np.load(npz,allow_pickle=False) as data:
    matrices={k:data[k].copy() for k in ['query_tag_cosines','query_chunk_cosines','query_description_cosines']}
    weights=data['query_facet_weights'].copy()
   if any(not np.isfinite(a).all() for a in [*matrices.values(),weights]):raise ValueError('Nonfinite numerical readings')
   ids=meta['area']['chunk_ids'];members=None if ids is None else set(ids)
   if members is not None and not members<=set(self.ids):raise ValueError('Scope leaves graph')
   area=None if members is None else np.array([c in members for c in self.ids])
   self.loaded={cid:{'meta':meta,'matrices':matrices,'weights':weights,'area':area,'cache':{}}}
  return self.loaded[cid]


def benchmark():
 lab=RecoveredLab();OUT.mkdir(exist_ok=True)
 route_plan=L.read(L.ROOT/'output/research/2026-09-23-entity-route-programs-fast/plan.json')
 chosen={p['id']:p for p in route_plan['programs']}
 programs=[{**build({}),'id':'recovered_reference'},
   {**chosen['route_179'],'id':'recovered_route_hits'},
   {**chosen['route_163'],'id':'recovered_route_macro'},
   {**build({'matching':'maximum','query':'mean','path':'groups','join':'intersection','admission':'area_first'}),'id':'recovered_previous_best'}]
 cases=[c for c in lab.manifest['cases'] if c['cohort']=='recovered4']
 planned=base_plan();planned.update(programs=programs,case_ids=[c['case_id'] for c in cases],
  case_metadata={c['case_id']:c['meta'] for c in cases},
  purpose='Four additional recovered cases only; same fixed rules selected before these results. Not an independently sampled validation population.',
  selection='Reference, completed route leaders and previous construction leader; no per-case gold selector')
 for c in cases:
  for k in ('npz','meta'):planned['input_sha256'][c[k]]=L.digest(L.ROOT/c[k])
 for file in [Path(__file__),CAPTURE/'cases_manifest.json',CAPTURE/'combined99_manifest.json',
              L.ROOT/'tools/facet_fast_resume.py',L.ROOT/'test/artefact/facet_construction_fast.py']:
  planned['input_sha256'][str(file.relative_to(L.ROOT))]=L.digest(file)
 if (OUT/'plan.json').exists():
  if L.read(OUT/'plan.json')!=json.loads(json.dumps(planned)):raise ValueError('Recovered-case plan changed')
 else:L.write_new(OUT/'plan.json',planned)
 all_rows=[]
 for c in cases:
  case=lab.load(c['case_id']);ref=lab.execute(case,build({}));lab.parity(case,ref)
  rd,rm=lab.measured(case,ref);reforder=ref['order'].copy();rows=[]
  for p in programs:
   r=lab.execute(case,p);d,m=lab.measured(case,r)
   rows.append({'case_id':c['case_id'],'program_id':p['id'],**m,'recall_delta':m['recall_id']-rm['recall_id'],
    'candidate_access':len(r['order']),'access_changed':set(r['order'])!=set(reforder),
    'delivery_changed':set(d['full'])!=set(rd['full']),'full_chunk_ids':d['full'],'budget':d['budget'],
    'order_sha256':hashlib.sha256(r['order'].tobytes()).hexdigest()})
  (OUT/'cases').mkdir(exist_ok=True);L.atomic(OUT/'cases'/(c['case_id']+'.json'),rows);all_rows.extend(rows)
 for name,sha in planned['input_sha256'].items():
  if L.digest(L.ROOT/name)!=sha:raise ValueError('Dependency changed during recovered-case check')
 summary=[]
 for p in programs:
  rows=[r for r in all_rows if r['program_id']==p['id']]
  summary.append({'program_id':p['id'],'cases':len(rows),'total_gold_hits':sum(r['hits'] for r in rows),
   'total_gold_count':sum(r['gold_count'] for r in rows),'macro_recall':float(np.mean([r['recall_id'] for r in rows]))})
 L.atomic(OUT/'report.json',summary);L.atomic(OUT/'status.json',{'status':'complete','completed_cases':4,'programs':4,'evaluations':16})
 print(json.dumps({'combined_replayable_cases':99,'failed_interpretations':1,'recovered_results':summary}),flush=True)


if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('command',choices=['index','benchmark'])
 if ap.parse_args().command=='index':print(json.dumps({'cases':len(combined_manifest()['cases'])}))
 else:benchmark()

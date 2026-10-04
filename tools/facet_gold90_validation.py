"""Freeze and launch the remaining-90 standard retrieval run; numeric progress only."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

import facet_joint_gold_smoke as S

ROOT=S.ROOT
RUN_ROOT=ROOT/'output/k=chars'
PREFIX='artefact_facet_joint__gold90__cb72000__'
PROTOCOL=ROOT/'docs/2026-09-22-facet-gold90-protocol.md'


def now():return datetime.now(timezone.utc).isoformat()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write_new(p,value):
    with p.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2);f.write('\n')
def emit(v):print(json.dumps(v),flush=True)
def ids(p):return [json.loads(l)['id'] for l in p.read_text(encoding='utf-8').splitlines() if l.strip()]


def prepare():
    gold,smoke=ids(ROOT/'data/gold100.jsonl'),ids(ROOT/'data/10smoke.jsonl')
    assert len(gold)==len(set(gold))==100 and len(smoke)==len(set(smoke))==10 and set(smoke)<=set(gold)
    chosen=[qid for qid in gold if qid not in set(smoke)]
    assert len(chosen)==90
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    folder=RUN_ROOT/(PREFIX+stamp);folder.mkdir(exist_ok=False)
    (folder/'private').mkdir()
    subset=folder/'remaining90.jsonl'
    with subset.open('x',encoding='utf-8') as f:
        for qid in chosen:f.write(json.dumps({'id':qid})+'\n')
    frozen,_,models=S.frozen_inputs()
    for p in (Path(__file__),PROTOCOL,ROOT/'data/gold100.jsonl',ROOT/'data/10smoke.jsonl',ROOT/'data/questions.jsonl',subset):
        frozen[str(p.relative_to(ROOT))]=sha(p)
    command=[str(ROOT/'.venv/Scripts/python.exe'),'-B','-X','utf8','-u',str(ROOT/'prod/run.py'),
        '--arm','artefact_facet_joint','--set',str(subset),'--char-budget','72000','--workers','4',
        '--retrieval-only','--no-eval','--out',str(folder)]
    plan={'folder':str(folder),'created_utc':now(),'questions':90,'command':command,
        'input_sha256':frozen,'adapter_models':models,'cache':str(folder/'private/interpreter_cache'),
        'conditions':{'joint':[1,.25,.25,.25,.25],'auxiliaries_off':[1,0,0,0,0]},
        'automatic_retry':False,'generator_calls':0,'judge_calls':0}
    write_new(folder/'validation_plan.json',plan)
    write_new(folder/'prepared.json',{'plan_sha256':sha(folder/'validation_plan.json')})
    emit({'phase':'prepared','folder':str(folder),'questions':90,'model_calls':0})


def verify(plan):
    for name,expected in plan['input_sha256'].items():
        if sha(ROOT/name)!=expected:raise RuntimeError('Frozen input changed')


def count_new(path,state):
    if not path.exists():return
    with path.open('rb') as f:
        f.seek(state['offset'])
        while True:
            block=f.read(1024*1024)
            if not block:break
            state['count']+=block.count(b'\n');state['offset']+=len(block)


def execute(folder):
    folder=folder.resolve()
    assert folder.parent==RUN_ROOT.resolve() and folder.name.startswith(PREFIX)
    plan=read(folder/'validation_plan.json')
    assert sha(folder/'validation_plan.json')==read(folder/'prepared.json')['plan_sha256']
    assert plan['folder']==str(folder)
    if (folder/'started.json').exists():raise RuntimeError('Already started; do not automatically retry')
    verify(plan)
    write_new(folder/'started.json',{'at':now(),'wrapper_pid':os.getpid()})
    env=os.environ.copy();env.update(HERB_FACET_JOINT_CACHE=plan['cache'],PYTHONUNBUFFERED='1',
        HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    start=time.monotonic();success={'offset':0,'count':0};failed={'offset':0,'count':0}
    with (folder/'private/retrieval.log').open('xb') as log:
        child=subprocess.Popen(plan['command'],cwd=ROOT,env=env,stdin=subprocess.DEVNULL,
                               stdout=log,stderr=subprocess.STDOUT)
        write_new(folder/'child.json',{'pid':child.pid,'at':now(),'command':plan['command']})
        emit({'phase':'running','child_pid':child.pid,'questions':90,'folder':str(folder)})
        last=None
        while True:
            code=child.poll()
            count_new(folder/'arm_outputs.jsonl',success);count_new(folder/'failures.jsonl',failed)
            status={'phase':'running' if code is None else 'terminal','completed':success['count'],
                    'failure_records':failed['count'],'questions':90,'elapsed_s':round(time.monotonic()-start,1),
                    'child_pid':child.pid,'return_code':code,'at':now()}
            (folder/'progress.json').write_text(json.dumps(status,indent=2)+'\n',encoding='utf-8')
            changed=(code,success['count'],failed['count'])
            if changed!=last:emit(status);last=changed
            if code is not None:break
            time.sleep(10)
    verify(plan)
    manifest=read(folder/'run_manifest.json') if (folder/'run_manifest.json').exists() else {}
    result={**status,'phase':'completed' if code==0 else 'process_failed',
            'manifest':{k:manifest.get(k) for k in ('n_questions','n_ran','n_failed','generator_model','char_budget')},
            'input_hashes_unchanged':True,'no_automatic_retry':True}
    write_new(folder/'retrieval_completed.json',result);emit(result)
    return code


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',type=Path);args=p.parse_args()
    try:
        if args.run:sys.exit(execute(args.run))
        prepare()
    except Exception:
        if args.run:
            with (args.run/'private/wrapper_error.log').open('a',encoding='utf-8') as f:traceback.print_exc(file=f)
        emit({'phase':'stopped','reason':'Preflight or wrapper failure; private details retained. No automatic retry.'})
        sys.exit(1)

"""Check the unchanged querytagger on two explicit non-benchmark diagnostic questions.

The questions contrast market analysis with report sharing. Only generation is
collected here, twice per question; later scoring and graph matching stay separate.
No prompt revision, hidden target tag, reference passage or expected answer is sent.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
import argparse
import ast
import hashlib
import json
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'prod'))
from harness.chat import _CLAUDE_EXE

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--run',action='store_true');args=ap.parse_args()
    source=ROOT/'test/artefact/querytagger.py';tree=ast.parse(source.read_text(encoding='utf-8'))
    wanted={'GENERATE_SYSTEM','GENERATE_USER_TEMPLATE','MODEL'};constants={}
    for node in tree.body:
        if isinstance(node,ast.Assign):
            for target in node.targets:
                if isinstance(target,ast.Name) and target.id in wanted:constants[target.id]=ast.literal_eval(node.value)
    questions=[('analysis','What market analysis does the flowAIX market research report provide?'),
               ('sharing','Where was the flowAIX market research report shared?')]
    jobs=[{'id':f'{name}_{repeat}','question':q,'repeat':repeat,'system':constants['GENERATE_SYSTEM'],
        'user':constants['GENERATE_USER_TEMPLATE'].format(question=q)} for name,q in questions for repeat in (0,1)]
    manifest={'protocol':__doc__,'model':constants['MODEL'],'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'jobs':jobs,'scope':'Read the entire generated description and tag list. Inspect whether the requested distinction survives in either. Match all resulting tags into live Volmax before attributing a failure to facet weights. These two diagnostic questions were constructed in this experiment; no benchmark questions are used.'}
    args.out.mkdir(parents=True,exist_ok=True);path=args.out/'manifest.json'
    if path.exists() and json.loads(path.read_text())!=manifest:raise ValueError('Changed query-route manifest')
    path.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8');print('Saved four unchanged-querytagger inputs',flush=True)
    def run(j):
        p=args.out/(j['id']+'.json')
        sig={k+'_sha256':hashlib.sha256(j[k].encode()).hexdigest() for k in ('system','user')}
        if p.exists():
            r=json.loads(p.read_text())
            if r['model']!=manifest['model'] or any(r[k]!=v for k,v in sig.items()):raise ValueError('Changed response inputs')
            return r
        with tempfile.TemporaryDirectory(prefix='facet-query-route-') as cwd:
            proc=subprocess.run([_CLAUDE_EXE,'-p','--model',manifest['model'],'--output-format','json','--tools','',
                '--setting-sources','','--no-session-persistence','--system-prompt',j['system']],input=j['user'],
                cwd=cwd,capture_output=True,text=True,encoding='utf-8',timeout=300)
        transport={'model':manifest['model'],**sig,'returncode':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr,
            'created_utc':datetime.now(timezone.utc).isoformat()}
        (args.out/(j['id']+'.transport.json')).write_text(json.dumps(transport,indent=2)+'\n',encoding='utf-8')
        env=json.loads(proc.stdout)
        if proc.returncode or env.get('is_error'):
            raise RuntimeError(f"CLI exit {proc.returncode}; API status {env.get('api_error_status')}; {str(env.get('result'))[:250]}")
        raw=env['result'].strip()
        if raw.startswith('```'):raw=raw.split('\n',1)[1].rsplit('```',1)[0].strip()
        answer=json.loads(raw)
        if not isinstance(answer.get('description'),str) or not isinstance(answer.get('tags'),list) or not all(isinstance(t,str) for t in answer['tags']):raise ValueError('Invalid generation schema')
        r={'id':j['id'],'model':manifest['model'],**sig,'answer':answer,'cost_usd_reported':env.get('total_cost_usd'),
            'usage':env.get('usage'),'created_utc':datetime.now(timezone.utc).isoformat()}
        p.write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8');return r
    if args.run:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures={pool.submit(run,j):j for j in jobs}
            for future in as_completed(futures):
                j=futures[future]
                try:
                    r=future.result();print(r['id'],json.dumps(r['answer']),flush=True)
                except Exception as exc:
                    failure={'job':j['id'],'type':type(exc).__name__,'message':str(exc)[:600] if not isinstance(exc,subprocess.TimeoutExpired) else 'Collector timeout'}
                    (args.out/(j['id']+'.failed.json')).write_text(json.dumps(failure,indent=2)+'\n',encoding='utf-8');print(failure,flush=True)

if __name__=='__main__':main()

"""Aggregate the fixed baseline smoke; no ranking changes or model calls."""
import collections
import hashlib
import json
import math
from pathlib import Path
import statistics

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/research/2026-09-24-concept-baseline'


def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    plan=read(OUT/'execution-plan.json')
    assert read(OUT/'generation.exit.json')['exit_code']==0
    assert read(OUT/'judge.exit.json')['exit_code']==0
    for path,h in plan['files'].items():assert sha(ROOT/path)==h
    assert len(read(OUT/'trace-audit.json')['checks'])==10
    run=ROOT/plan['run'];judge=run.with_name(run.name+'__j-claude-haiku-4-5__10smoke')
    outputs=[json.loads(l) for l in (run/'arm_outputs.jsonl').open(encoding='utf-8')]
    assert len(outputs)==10 and len({r['id'] for r in outputs})==10
    question_map={r['id']:r['question'] for r in outputs}
    manifest=read(run/'run_manifest.json')
    assert manifest['char_budget']==72000 and manifest['n_failed']==0
    metrics=collections.defaultdict(list);seen=set()
    for line in (judge/'eval_results.jsonl').open(encoding='utf-8'):
        r=json.loads(line);key=(r['question_id'],r['metric'])
        assert key not in seen and r['question_id'] in question_map
        seen.add(key);metrics[r['metric']].append(r)
    assert len(metrics)==14 and len(seen)==140
    summary={}
    for metric,rows in metrics.items():
        good=[r['value'] for r in rows if r['status']=='ok' and isinstance(r['value'],(int,float)) and math.isfinite(r['value'])]
        assert len(rows)==10
        summary[metric]={'mean':statistics.mean(good) if good else None,'ok':len(good),'errors':10-len(good)}
    old=read(ROOT/'output/research/2026-09-24-real-gold-smoke/lucene-vector-same-ten.json')['comparison']
    baselines={}
    for name in ('Lucene','Vector','Artefact'):
        data=old[name]
        for path,h in data['source_sha256'].items():assert sha(ROOT/path)==h
        existing={}
        for line in (ROOT/data['run']/'arm_outputs.jsonl').open(encoding='utf-8'):
            r=json.loads(line)
            if r['id'] in question_map:existing[r['id']]=r['question']
        assert existing==question_map
        baselines[name]={'metrics':data['metrics'],'same_question_texts_verified':True,'historical_run':data['run'],
                         'generator':data['generator'],'judge':data['judge'],'budget':data['budget']}
    result={'status':'completed_with_reported_metric_errors' if any(v['errors'] for v in summary.values()) else 'completed',
            'run':plan['run'],'judge_run':str(judge.relative_to(ROOT)),
            'questions':10,'fresh_answers':10,'metric_cells':140,'metrics':summary,'historical_comparison':baselines,
            'retrieval_reported_calls':sum(r['retrieval'].get('calls',0) for r in outputs),
            'interpreter_cache_misses':sum(not r['meta']['interpreter_cache']['cache_hit'] for r in outputs),
            'generator_calls':sum(r['generator'].get('calls',0) for r in outputs),
            'dataflow_exact_replays':10,'source_sha256':{'outputs':sha(run/'arm_outputs.jsonl'),'metrics':sha(judge/'eval_results.jsonl')},
            'limits':['Same ten reused development cases, not heldout validation.',
                      'Historical controls were not freshly regenerated or rejudged.',
                      'Failed cells stay failures; means use successful cells, not necessarily matched success subsets.',
                      'Source-ID metrics are not answer quality or semantic validation.',
                      'Baseline arithmetic is explicit provisional policy; frozen learned facet meaning remains unresolved.']}
    with (OUT/'results.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    lines=['# First concept-baseline run','',
           'Ten fresh combined interpretations and answers; ten exact trace/delivery replays. The standard 14 metrics were attempted. This is a fixed development baseline, not a sweep or heldout superiority claim.','',
           '| Metric | Concept baseline | Earlier selected rule | Lucene | Vector | Current ok / errors |',
           '|---|---:|---:|---:|---:|---:|']
    fmt=lambda v:'unavailable' if v is None else f'{v:.6f}'
    for metric in sorted(summary):
        s=summary[metric];b=baselines
        lines.append(f"| {metric} | {fmt(s['mean'])} | {fmt(b['Artefact']['metrics'][metric]['mean'])} | {fmt(b['Lucene']['metrics'][metric]['mean'])} | {fmt(b['Vector']['metrics'][metric]['mean'])} | {s['ok']} / {s['errors']} |")
    lines+=['','All historical input file hashes and the ten original question texts were checked. Historical comparison is not a fresh paired judge experiment. See results.json for success counts, model metadata, paths and limits.','',
            'Observed construction limits: positive tag matches retain all 4,808 eligible chunks on each case; ranking, not a discovered semantic cutoff, determines delivery. The historical nearest-name heuristic adds bindings in three cases, including highly ambiguous multi-node names. No claim that these bindings are correct follows from replay parity.','',
            'Implementation: test/arms/artefact_concept_baseline.py and test/artefact/concept_baseline.py. Open choices are explicit in docs/2026-09-24-concept-baseline.md. Existing graph/measurement artifacts were not rewritten.']
    (OUT/'RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'status':result['status'],'fresh_answers':10,'successful_cells':sum(x['ok'] for x in summary.values()),
                      'error_cells':sum(x['errors'] for x in summary.values()),
                      'source_id_recall':summary['context_recall_id'],'answer_correctness':summary['answer_correctness']}))


if __name__=='__main__':main()

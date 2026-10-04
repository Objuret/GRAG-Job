"""Compare complete real smoke runs without exposing benchmark or answer text."""
import argparse
from pathlib import Path
import facet_joint_gold_smoke as W


def summarize(folder):
    records=list(W.json_rows(folder/'arm_outputs.jsonl'))
    manifest=W.read_json(folder/'run_manifest.json')
    metrics=W.literals(W.ROOT/'prod/eval/ragas_catalog.py')['SELECTED']
    judged=folder.with_name(folder.name+W.JUDGE_SUFFIX)
    return {r['id'] for r in records},{
        'folder':str(folder),'answers':len(records),
        'generator':manifest.get('generator_model'),
        'char_budget':manifest.get('char_budget'),
        'metrics':W.aggregate_metrics(judged,metrics),
        'source_sha256':{str(p):W.sha(p) for p in
            (folder/'arm_outputs.jsonl',folder/'run_manifest.json',
             judged/'eval_results.jsonl',judged/'eval_manifest.json')},
    }


def compare(folder,references):
    ids,current=summarize(folder)
    if len(ids)!=10 or current['answers']!=10 or current['char_budget']!=72000:
        raise ValueError('Complete standard ten-question 72k smoke required')
    comparisons=[]
    for reference in references:
        oldids,old=summarize(reference)
        if oldids!=ids or old['answers']!=10 or old['char_budget']!=72000:
            raise ValueError('Reference question population or budget differs')
        deltas={}
        for name,value in current['metrics']['metrics'].items():
            before=old['metrics']['metrics'][name]
            deltas[name]=value['mean']-before['mean'] if value['mean'] is not None and before['mean'] is not None else None
        comparisons.append({'reference':old,'mean_deltas':deltas,
                            'same_generator':old['generator']==current['generator']})
    result={'current':current,'comparisons':comparisons,
        'limits':['Reused development smoke questions, not held-out validation.',
                  'Generation and judge variability affect answer-quality comparisons.',
                  'All standard metrics retained; means with errors use successful cells only.']}
    W.write_new(folder/'smoke_comparison.json',result)
    W.emit({k:v for k,v in result.items() if k!='comparisons'})
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--reference',type=Path,action='append',required=True)
    args=parser.parse_args()
    compare(args.run.resolve(),[p.resolve() for p in args.reference])

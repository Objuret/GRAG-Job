"""Blind standard answer-generation/RAGAS smoke for one frozen structural rule."""
import argparse
from pathlib import Path
import sys
import facet_joint_gold_smoke as W

W.ARM='artefact_facet_program'
W.PREFIX=W.ARM+'__10smoke__cb72000__'


def commands(folder):
    python=str(Path(sys.executable).resolve())
    runner=str(W.ROOT/'tools/facet_program_runner.py')
    return {
        'generation':[python,'-u',runner,'--arm',W.ARM,'--set','10smoke',
            '--char-budget','72000','--workers','4','--generator',W.GENERATOR,
            '--no-eval','--out',str(folder)],
        'judge':[python,'-u',runner,'--rejudge',str(folder),'--set','10smoke',
            '--judge',W.JUDGE,'--workers','16'],
    }


def frozen_inputs():
    arm=W.ROOT/'test/arms/artefact_facet_program.py'
    if not arm.is_file():raise W.SafeStop('adapter_not_ready')
    base=W.literals(W.ROOT/'test/arms/artefact_facet_joint.py')
    declared=W.literals(arm)
    paths=(*base['SMOKE_PROVENANCE_PATHS'],*declared['SMOKE_PROVENANCE_PATHS'])
    files={Path(__file__).resolve(),Path(W.__file__).resolve(),arm,
           W.ROOT/'tools/facet_program_runner.py',W.ROOT/'prod/run.py'}
    files.update((W.ROOT/'prod/harness').rglob('*.py'))
    files.update((W.ROOT/'prod/eval').rglob('*.py'))
    for relative in paths:
        path=(W.ROOT/relative).resolve()
        if not path.is_relative_to(W.ROOT) or path.is_relative_to(W.ROOT/'data'):
            raise W.SafeStop('invalid_provenance_path')
        if not path.is_file():raise W.SafeStop('provenance_input_missing')
        files.add(path)
    metrics=W.literals(W.ROOT/'prod/eval/ragas_catalog.py').get('SELECTED')
    if not isinstance(metrics,list) or len(metrics)!=14 or len(set(metrics))!=14:
        raise W.SafeStop('standard_metric_catalog_changed')
    models={**base['SMOKE_MODEL_CONFIG'],**declared['SMOKE_MODEL_CONFIG']}
    return ({str(p.relative_to(W.ROOT)):W.sha(p) for p in sorted(files)},metrics,models)


W.commands=commands
W.frozen_inputs=frozen_inputs

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--prepare',action='store_true')
    mode.add_argument('--run',type=Path)
    args=parser.parse_args()
    try:
        raise SystemExit(W.execute(args.run) if args.run else W.prepare())
    except W.SafeStop as exc:
        W.emit({'phase':'refused','reason_code':str(exc)})
        raise SystemExit(1)

"""Fresh standard smoke for an explicitly fixed, sealed structural leader."""
import argparse
from pathlib import Path
import facet_program_gold_smoke as P

W=P.W

def commands(folder):
    result=P.commands(folder)
    for command in result.values():command[2]=str(W.ROOT/'tools/facet_leader_runner.py')
    return result

def frozen_inputs():
    inputs,metrics,models=P.frozen_inputs()
    arm=W.ROOT/'test/arms'/(W.ARM+'.py')
    declared=W.literals(arm)
    files=[Path(__file__).resolve(),W.ROOT/'tools/facet_leader_runner.py',arm]
    for relative in declared['SMOKE_PROVENANCE_PATHS']:
        path=(W.ROOT/relative).resolve()
        if not path.is_relative_to(W.ROOT) or path.is_relative_to(W.ROOT/'data'):
            raise W.SafeStop('invalid_provenance_path')
        files.append(path)
    for path in files:
        if not path.is_file():raise W.SafeStop('adapter_not_ready')
        inputs[str(path.relative_to(W.ROOT))]=W.sha(path)
    return inputs,metrics,{**models,**declared['SMOKE_MODEL_CONFIG']}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--leader',choices=['hits','macro'],required=True)
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--prepare',action='store_true')
    mode.add_argument('--run',type=Path)
    args=parser.parse_args()
    W.ARM='artefact_facet_leader_'+args.leader
    W.PREFIX=W.ARM+'__10smoke__cb72000__'
    W.commands=commands
    W.frozen_inputs=frozen_inputs
    try:raise SystemExit(W.execute(args.run) if args.run else W.prepare())
    except W.SafeStop as exc:
        W.emit({'phase':'refused','reason_code':str(exc)})
        raise SystemExit(1)

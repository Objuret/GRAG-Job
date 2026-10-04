"""Preserve the first smoke; run the JSON metadata repair with identical ranking."""
import argparse
from pathlib import Path
import facet_program_gold_smoke as P

W=P.W
W.ARM='artefact_facet_program_v2'
W.PREFIX=W.ARM+'__10smoke__cb72000__'


def commands(folder):
    result=P.commands(folder)
    for command in result.values():command[2]=str(W.ROOT/'tools/facet_program_runner_v2.py')
    return result


def frozen_inputs():
    inputs,metrics,models=P.frozen_inputs()
    for path in (Path(__file__).resolve(),W.ROOT/'tools/facet_program_runner_v2.py',
                 W.ROOT/'test/arms/artefact_facet_program_v2.py'):
        if not path.is_file():raise W.SafeStop('adapter_not_ready')
        inputs[str(path.relative_to(W.ROOT))]=W.sha(path)
    return inputs,metrics,{**models,'adapter_revision':'2: scope metadata set serialized as sorted IDs; ranking unchanged'}


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

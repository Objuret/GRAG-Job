"""Promote the exact recovered interpretation, preserving the original failure."""
import hashlib
import json
import os
from pathlib import Path
import shutil

import facet_joint_gold_smoke as W


def main():
    run = W.RUN_ROOT / ('artefact_facet_area__10smoke__cb72000__20260922T112609034165Z'
                        '__cached-resume')
    assert W.read_json(run / 'completed.json')['phase'] in ('completed', 'completed_with_metric_errors')
    plan = W.read_json(run / 'resume_plan.json')
    W.ARM = 'artefact_facet_area'
    assert W.frozen_inputs()[0] == plan['input_sha256']
    for path, digest in plan['cache_sha256'].items():
        assert W.sha(Path(path)) == digest, 'Source cache changed'
    source = Path(plan['cache'])
    destination = W.ROOT / 'output/private/facet_joint_cache'
    gen = source / 'generate/a09b6e7a0363f6532b02f609f9752995e3d9150f6865760147cc84fefdcf9c8e.json'
    score = source / 'score/8889803229391a7ffa41849855ef0ea540520eb284028a9806e6c11de76e98c2.json'
    target = destination / 'generate' / gen.name
    old, new = W.read_json(target), W.read_json(gen)
    assert not old['ok'] and new['ok'] and old['signature'] == new['signature']
    for path in (gen, score):
        record = W.read_json(path)
        digest = hashlib.sha256(json.dumps(record['signature'], sort_keys=True,
                                           ensure_ascii=False).encode('utf-8')).hexdigest()
        assert record['ok'] and digest == path.stem
    history = destination / 'history/2026-09-22-exact-recovery'
    history.mkdir(parents=True, exist_ok=False)
    shutil.copy2(target, history / 'original-generate-failure.json')
    hashes = {str(p): W.sha(p) for p in (target, gen, score)}
    W.write_new(history / 'plan.json', {'source_hashes': hashes, 'completed_run': str(run),
        'policy': 'Same-signature success replaces cached failure; original bytes retained.'})
    score_target = destination / 'score' / score.name
    score_target.parent.mkdir(exist_ok=True)
    if score_target.exists():
        assert W.sha(score_target) == W.sha(score)
    else:
        with score_target.open('xb') as handle:
            handle.write(score.read_bytes())
    temporary = target.with_suffix('.recovered.tmp')
    with temporary.open('xb') as handle:
        handle.write(gen.read_bytes())
    assert W.sha(target) == hashes[str(target)]
    os.replace(temporary, target)
    assert W.sha(target) == W.sha(gen)
    assert W.sha(history / 'original-generate-failure.json') == hashes[str(target)]
    assert all(W.sha(p) == hashes[str(p)] for p in (gen, score))
    W.write_new(history / 'completed.json', {'at': W.utc(), 'status': 'promoted',
        'canonical_generate_sha256': W.sha(target), 'canonical_score_sha256': W.sha(score_target),
        'source_caches_unchanged': True, 'original_failure_preserved': True})
    print(json.dumps({'status': 'promoted', 'model_calls': 0,
                      'original_failure_preserved': True, 'source_caches_unchanged': True}))


if __name__ == '__main__':
    main()

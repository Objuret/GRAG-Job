"""Prepare a blind fixed-generation SCORE comparison; no models, graph or gold."""
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/research/2026-09-24-interpretation-comparison'
INPUTS = ROOT / 'output/research/2026-09-22-retrieval-matrix/inputs'
SOURCE = ROOT / 'output/k=chars/artefact_facet_joint__10smoke__cb72000__20260922T071854164747Z__format-retry1/arm_outputs.jsonl'
CLARIFICATION = """Judge the tag's relevance to the described content through each facet. Do not substitute a judgment about whether something is being done to the thing named by the tag. Being discussed or referenced does not by itself establish low relevance through a facet. Do not treat the presence of a date, name or number alone as evidence of a strong relationship. Judge only characteristics supported by the supplied input; do not supply facts from an imagined answer."""


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if read(path) != value:
            raise ValueError('Existing comparison artifact differs: ' + path.name)
        return
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)


def main():
    prompt_path = ROOT / 'test/artefact/querytagger.py'
    constants = {}
    for node in ast.parse(prompt_path.read_text(encoding='utf-8')).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ('SCORE_SYSTEM', 'SCORE_USER_TEMPLATE'):
                    constants[target.id] = ast.literal_eval(node.value)
    original = constants['SCORE_SYSTEM']
    old = "activity — looking at what is actually going on in that content, as against what is only described, referenced or discussed: how relevant is the tag to that content, seen that way?"
    new = "activity — looking at the activities and processes represented in the described content: how relevant is the tag to that content, seen through this facet?"
    assert original.count(old) == 1 and original.count('## Weights') == 1
    clarified = original.replace(old, new).replace('## Weights', CLARIFICATION + '\n\n## Weights')
    systems = {'D0': original, 'QD0': original, 'D1': clarified, 'QD1': clarified}
    manifest = read(INPUTS / 'cases_manifest.json')
    cases = [c for c in manifest['cases'] if c['cohort'] == 'smoke10']
    assert len(cases) == 10
    wanted = {c['question_id']: c for c in cases}
    entries = []
    seen = set()
    for line in SOURCE.open('rb'):
        row = json.loads(line)
        if row['id'] not in wanted:
            continue
        case = wanted[row['id']]
        cid = case['case_id']
        assert cid not in seen
        seen.add(cid)
        meta = read(INPUTS / case['meta'])
        assert sha(line) == meta['source_record_sha256']
        assert sha((INPUTS / case['npz']).read_bytes()) == meta['npz_sha256']
        # Only query-side fields leave the saved row. Answers/contexts/IDs are discarded.
        interp = row['meta']['interpreter']
        question, description = row['question'], interp['description']
        tags = [r['t'] for r in interp['tags']]
        user = constants['SCORE_USER_TEMPLATE'].format(description=description, tags='\n'.join('- ' + t for t in tags))
        prior = read(Path(next(s['path'] for s in interp['stages'] if s['stage'] == 'score')))
        assert prior['ok'] and prior['signature']['system'] == original and prior['signature']['user'] == user
        private = {'case_id': cid, 'tags': tags, 'description': description, 'question': question,
                   'historical_weights': [[r['facets'][f] for f in ('topic','temporal','why','activity','concreteness')] for r in interp['tags']]}
        save(OUT / 'private' / (cid + '.json'), private)
        for condition in systems:
            message = user + ('\n\nOriginal question:\n' + question if condition.startswith('QD') else '')
            for repetition in (1, 2):
                request = {'case_id': cid, 'condition': condition, 'repetition': repetition,
                           'system': systems[condition], 'user': message, 'tags': tags,
                           'model': 'claude-haiku-4-5', 'temperature': 0, 'max_tokens': 4096}
                filename = f'private/requests/{cid}_{condition}_r{repetition}.json'
                save(OUT / filename, request)
                entries.append({'case_id': cid, 'condition': condition, 'repetition': repetition,
                                'request': filename, 'sha256': sha((OUT / filename).read_bytes())})
        # Keep no corpus-bearing row beyond this iteration.
        del row, prior
    assert len(seen) == 10 and len(entries) == 80
    save(OUT / 'prompts.json', systems)
    dependencies = [Path(__file__), prompt_path, ROOT/'docs/2026-09-24-interpretation-comparison-plan.md', INPUTS/'cases_manifest.json']
    plan = {'status': 'prepared_not_executed', 'cases': sorted(seen), 'requests': entries,
            'maximum_model_calls': 80, 'new_model_calls': 0, 'gold_read': False,
            'source_text_exported': False, 'input_generation_fixed': True,
            'downstream_programs': ['historical_joint', 'best_total_hits', 'best_macro_recall'],
            'source_sha256': sha(SOURCE.read_bytes()),
            'dependencies': {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in dependencies}}
    save(OUT / 'plan.json', plan)
    print(json.dumps({'cases': len(seen), 'prepared_requests': len(entries), 'model_calls': 0,
                      'historical_prompt_parity': True, 'captured_numeric_hashes_verified': True}))


if __name__ == '__main__':
    main()

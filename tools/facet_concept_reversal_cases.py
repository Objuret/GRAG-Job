"""Freeze source-backed, operator-blind cases for the composition diagnostic.

Select one inversion per captured generation by fixed hash, among source chunks
that mention the question's literal flowAIX target and share actual product
membership and earliest connection level. These are diagnostic strata, not a
retrieval gate. Selection never uses a relevance label. No source/model/DB calls.
"""
import hashlib
import itertools
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'output/research/2026-09-22-joint-streams/concept'
OUT = BASE / 'source_cases'
GRAPH = ROOT / 'output/research/2026-09-21-facet-validity/route_snapshot/graph.json'
SALT = 'joint-facet-function-20260922-v1'


def read(p):
    return json.loads(p.read_text(encoding='utf8'))


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write(p, value):
    p.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf8')


def levels(run):
    result, i = {}, 0
    for block in run['source_metadata']['walk']:
        n = block['new']
        for cid in run['chunk_order'][i:i+n]:
            result[cid] = (block['pass'], block['level'])
        i += n
    assert i == len(run['chunk_order'])
    return result


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT / 'blind_cases.json').exists():
        raise RuntimeError('Fixed case pack exists; do not select new examples after labels')
    write(OUT / 'selection_protocol.json', {'protocol': __doc__, 'salt': SALT,
          'source_sha256': sha(GRAPH), 'selection_script_sha256': sha(Path(__file__)),
          'case_count': 'One per generation if an eligible reversal exists; missing strata remain missing.',
          'label_task': 'Prefer A, B, tie or insufficient information for answering the raw question, solely from complete supplied source excerpts. Do not see method names, scores or ranks.',
          'limits': ['Four reused generations of two raw questions, not independent generalization evidence.',
                     'Literal-name and product matching select an inspection stratum only; they do not alter either retrieval.',
                     'One hash-selected reversal cannot estimate overall quality or fit facet coefficients.']})
    graph = read(GRAPH)
    chunks = {c['chunkId']: c for c in graph['chunks']}
    eligible = sorted(cid for cid, c in chunks.items() if 'flowaix' in c['source_text'].casefold())
    products = {cid: {p['node_id'] for p in c['scope'].get('product', [])} for cid, c in chunks.items()}
    public, private, missing = [], [], []
    for generation in ('analysis_0', 'analysis_1', 'sharing_0', 'sharing_1'):
        name = generation + '_score_0_concept_file.json'
        original, control = read(BASE / name), read(BASE / 'composition_control' / name)
        r0 = {cid: i for i, cid in enumerate(original['chunk_order'])}
        r1 = {cid: i for i, cid in enumerate(control['chunk_order'])}
        lev = levels(original)
        assert lev == levels(control)
        pool = [(a, b) for a, b in itertools.combinations(eligible, 2)
                if lev[a] == lev[b] and products[a] & products[b] and
                (r0[a] < r0[b]) != (r1[a] < r1[b])]
        if not pool:
            missing.append(generation)
            continue
        key = lambda pair: hashlib.sha256((SALT + generation + '|'.join(pair)).encode()).hexdigest()
        pair = min(pool, key=key)
        if int(key(pair)[-1], 16) % 2:
            pair = tuple(reversed(pair))
        case_id = 'case_' + str(len(public) + 1)
        public.append({'case_id': case_id, 'question': original['question'],
                       'passages': {label: {'text': chunks[cid]['source_text'],
                                            'source_kind': chunks[cid]['source_kind']}
                                    for label, cid in zip(('A', 'B'), pair)}})
        private.append({'case_id': case_id, 'generation': generation, 'eligible_reversals': len(pool),
                        'chunks': dict(zip(('A', 'B'), pair)), 'earliest_level': list(lev[pair[0]]),
                        'original_preference': 'A' if r0[pair[0]] < r0[pair[1]] else 'B',
                        'control_preference': 'A' if r1[pair[0]] < r1[pair[1]] else 'B',
                        'original_ranks': {label: r0[cid] + 1 for label, cid in zip(('A', 'B'), pair)},
                        'control_ranks': {label: r1[cid] + 1 for label, cid in zip(('A', 'B'), pair)},
                        'source_text_sha256': {label: hashlib.sha256(chunks[cid]['source_text'].encode()).hexdigest()
                                               for label, cid in zip(('A', 'B'), pair)},
                        'original_run_sha256': sha(BASE / name),
                        'control_run_sha256': sha(BASE / 'composition_control' / name)})
    write(OUT / 'blind_cases.json', {'task': 'Compare usefulness for answering each raw question. A/B order is hash-assigned. Tie/insufficient is permitted. Source excerpts are complete as captured, not complete documents.', 'cases': public})
    write(OUT / 'selection_manifest.json', {'protocol_sha256': sha(OUT / 'selection_protocol.json'),
          'blind_cases_sha256': sha(OUT / 'blind_cases.json'), 'literal_name_chunks': len(eligible),
          'cases': private, 'missing_strata': missing})
    print(json.dumps({'cases': len(public), 'missing': missing,
                      'candidate_counts': {c['generation']: c['eligible_reversals'] for c in private}}))


if __name__ == '__main__':
    main()

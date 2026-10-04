"""Freeze a method-hidden source packet for the completed recruitment replay."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'output/research/2026-09-22-joint-streams/independent_sources'
STATIC = ROOT / 'output/research/2026-09-21-facet-validity/route_snapshot'
OUT = BASE / 'need_selection/content_audit'
QUESTION_ID = 'independent_durable_messages_current_models'
BUDGET = 72000


def read(p):
    return json.loads(p.read_text(encoding='utf-8'))


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write(p, value):
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    if OUT.exists() and any(OUT.iterdir()):
        raise RuntimeError('Refusing to overwrite frozen content packet')
    graph = read(STATIC / 'graph.json')
    chunks = {c['chunkId']: c for c in graph['chunks']}
    questions = read(BASE / 'questions.json')
    question = next(q['question'] for q in questions if q['id'] == QUESTION_ID)
    paths = [Path(__file__), STATIC / 'graph.json', BASE / 'questions.json',
             ROOT / 'prod/run.py', ROOT / 'prod/harness/char_budget.py']
    runs, union = [], set()
    for reading in (0, 1):
        for mode in ('joint', 'facets'):
            path = BASE / f'need_selection/replay/{QUESTION_ID}_0_score_{reading}_{mode}.json'
            paths.append(path)
            result = read(path)
            kept, boundary, cost = [], [], 0
            for frontier in result['frontier_sizes']:
                ids = [r['chunk_id'] for r in result['rows'] if r['depth'] == frontier['depth']]
                next_cost = sum(len(chunks[c]['source_text']) for c in ids)
                if cost + next_cost > BUDGET:
                    boundary = ids
                    break
                kept += ids
                cost += next_cost
            union.update(kept + boundary)
            runs.append({'reading': reading, 'mode': mode, 'complete_frontier_chunk_ids': kept,
                         'source_characters': cost, 'crossing_frontier_chunk_ids': boundary})
    # Mask identities and method/order provenance, retain real scope metadata.
    ordered = sorted(union, key=lambda cid: hashlib.sha256(('content-audit-v1:' + cid).encode()).hexdigest())
    aliases = {cid: f'passage_{i:03d}' for i, cid in enumerate(ordered, 1)}
    entries = []
    for cid in ordered:
        c = chunks[cid]
        assert hashlib.sha256(c['source_text'].encode()).hexdigest() == c['source_text_sha256']
        entries.append({'passage_id': aliases[cid],
                        'graph_products': [p['name'] for p in c['scope'].get('product', [])],
                        'graph_channels': [p['name'] for p in c['scope'].get('channel', [])],
                        'source_kind': c['source_kind'], 'text': c['source_text']})
    OUT.mkdir(parents=True)
    write(OUT / 'reader_packet.json', {'question': question, 'passages': entries})
    write(OUT / 'private_manifest.json', {'question_id': QUESTION_ID, 'budget': BUDGET,
          'budget_definition': '72000 source-text characters, complete rank frontiers only; crossing frontier retained separately for boundary audit.',
          'not_live_harness': 'Actual harness can truncate a boundary text. This audit keeps complete chunks/ties and reports unused capacity; no claim to reproduce delivered production contexts.',
          'input_sha256': {str(p.relative_to(ROOT)): sha(p) for p in paths},
          'runs': runs, 'aliases': aliases,
          'packet_sha256': sha(OUT / 'reader_packet.json'),
          'pooled_passages': len(entries), 'pooled_source_characters': sum(len(x['text']) for x in entries),
          'model_calls': 0, 'db_calls': 0,
          'development_limit': 'One already inspected query selected after observed recruitment improvement. New source judgments cannot establish heldout generalization.'})
    print('Frozen', len(entries), 'passages;', sum(len(x['text']) for x in entries), 'source characters')


if __name__ == '__main__':
    main()

"""Join HERB gold citations to frozen graph routes and saved retrieval stages.

Read-only diagnostic. No model/embedding/DB calls and no change to retrieval.
Question/answer/context text and raw corpus contents are never exported.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / 'output/research/2026-09-21-facet-validity/route_snapshot'
DEFAULT_RUN = ROOT / 'output/k=chars/artefact_facet_joint__10smoke__cb72000__20260922T071854164747Z__format-retry1'
OUT = ROOT / 'output/research/2026-09-22-gold-source-trace'
FACETS = ('topic', 'temporal', 'why', 'activity', 'concreteness')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def rows(path):
    with path.open(encoding='utf-8-sig') as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def resolver():
    arm = ROOT / 'test/arms/artefact_v2.py'
    names = {'_load_verified_doc', '_nth_entry', '_resolve_chunk'}
    funcs = [n for n in ast.parse(arm.read_text(encoding='utf-8')).body
             if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in funcs} == names
    ns = {'json': json, 'hashlib': hashlib, 'Path': Path, 'RAW_ROOT': (ROOT / 'data/raw').resolve()}
    exec(compile(ast.Module(body=funcs, type_ignores=[]), str(arm), 'exec'), ns)
    return ns['_resolve_chunk']


def build_index(out, subset):
    subset_ids = {r['id'] for r in rows(subset)}
    # Deliberately retain only IDs and citations. No benchmark language is
    # displayed, exported, passed to retrieval, or used to select conditions.
    questions = {r['id']: sorted(set(str(c) for c in r.get('citations', [])))
                 for r in rows(ROOT / 'data/questions.jsonl') if r['id'] in subset_ids}
    if set(questions) != subset_ids:
        raise ValueError('Subset contains IDs missing from the benchmark inventory')
    wanted = set().union(*(set(v) for v in questions.values()))
    graph = read(SNAPSHOT / 'graph.json')
    chunks = {c['chunkId']: c for c in graph['chunks']}
    resolve, docs, unit_index, reverse = resolver(), {}, {}, defaultdict(list)
    for cid, chunk in chunks.items():
        text, aids = resolve(chunk, docs)
        unit_index[cid] = {'artifact_ids': aids, 'serialized_chars': len(text)}
        for aid in aids:
            reverse[aid].append(cid)
    mapped = {aid: sorted(reverse.get(aid, [])) for aid in sorted(wanted)}
    gold_chunks = set().union(*(set(v) for v in mapped.values()))
    tag_links = defaultdict(list)
    with np.load(SNAPSHOT / 'arrays.npz') as a:
        for e, (t, c) in enumerate(zip(a['edge_tag'], a['edge_chunk'])):
            cid = graph['chunk_ids'][int(c)]
            if cid in gold_chunks:
                tag_links[cid].append({'edge_id': graph['edge_ids'][e],
                    'relation_id': graph['edge_relation_ids'][e],
                    'tag': graph['graph_tags'][int(t)],
                    'static_facets': dict(zip(FACETS, map(float, a['edge_facets'][e])))})
    chunk_index = {cid: {'source_product': chunks[cid]['source_product'],
                        'source_kind': chunks[cid]['source_kind'],
                        'locator': json.loads(chunks[cid]['locator']),
                        'scope': chunks[cid]['scope'], **unit_index[cid],
                        'semantic_tag_links': tag_links[cid]}
                   for cid in sorted(gold_chunks)}
    provenance = {'graph_sha256': sha(SNAPSHOT / 'graph.json'),
                  'arrays_sha256': sha(SNAPSHOT / 'arrays.npz'),
                  'questions_sha256': sha(ROOT / 'data/questions.jsonl'),
                  'subset_path': str(subset.relative_to(ROOT)), 'subset_sha256': sha(subset),
                  'resolver_sha256': sha(ROOT / 'test/arms/artefact_v2.py'),
                  'raw_files_verified': [{'relpath': p, 'sha256': h} for p,h in sorted(docs)],
                  'source_text_exported': False}
    result = {'schema_version': 1, 'provenance': provenance, 'questions': questions,
              'artifacts': mapped, 'chunks': chunk_index,
              'summary': {'questions': len(questions), 'unique_gold_artifacts': len(wanted),
                          'mapped_artifacts': sum(bool(v) for v in mapped.values()),
                          'unmapped_artifacts': sum(not v for v in mapped.values()),
                          'gold_linked_chunks': len(gold_chunks),
                          'tag_links': sum(map(len, tag_links.values())),
                          'eligible_graph_chunks': len(chunks), 'raw_files_verified': len(docs)},
              'limits': 'Artifact membership is not proof of answer-bearing text. Missing mappings mean absent from this frozen eligible graph, not necessarily absent from HERB or the live DB.'}
    write(out / 'gold_source_index.json', result)
    write(out / 'chunk_delivery_index.json', unit_index)
    return result, unit_index, graph


def safe_witnesses(provenance, graph):
    result = {}
    for facet, witness in provenance.items():
        if witness is None:
            result[facet] = None
            continue
        # Query-tag text is intentionally omitted; the index is sufficient to
        # join private interpreter traces if explicitly needed later.
        keep = ('query_tag_index', 'edge_id', 'edge_index', 'graph_tag_index',
                'seed_chunk_id', 'route_type', 'M', 'D_seed', 'D_target', 'Q',
                'hop_discount', 'seed_direct', 'u', 'F', 'coefficient', 'Z', 'contribution')
        result[facet] = {k: witness[k] for k in keep if k in witness}
        if 'graph_tag_index' in witness:
            result[facet]['graph_tag'] = graph['graph_tags'][witness['graph_tag_index']]
    return result


def trace_run(folder, index, units, graph):
    cases, statuses, checked = [], Counter(), Counter()
    for r in rows(folder / 'arm_outputs.jsonl'):
        qid = r['id']
        if qid not in index['questions']:
            continue
        meta = r['meta']
        if meta.get('policy', {}).get('snapshot_sha256', {}).get('graph.json') != index['provenance']['graph_sha256']:
            raise ValueError('Saved run graph differs from pointer index')
        snapshot = meta.get('snapshot', {})
        if snapshot.get('snapshot_sha256', {}).get('arrays.npz') != index['provenance']['arrays_sha256']:
            raise ValueError('Saved facet arrays differ from pointer index')
        saved_code = {k.replace('\\', '/'): v for k,v in snapshot.get('source_sha256', {}).items()}
        if saved_code.get('test/arms/artefact_v2.py') != index['provenance']['resolver_sha256']:
            raise ValueError('Saved resolver differs from current source mapping and lengths')
        rankings = {x['chunk_id']: x for x in meta['ranking']['rows']}
        recruit = meta['recruitment']
        nomination = {x['chunk_id']: x for x in recruit['nomination']['rows']}
        recovery = {x['chunk_id']: x for x in recruit['rows']}
        order = meta['full_recovered_order']
        positions = {cid: i+1 for i,cid in enumerate(order)}
        if len(order) != len(positions):
            raise ValueError('Duplicate recovered chunk')
        costs, total = {}, 0
        for cid in order:
            total += units[cid]['serialized_chars']
            costs[cid] = total
        budget = meta['char_budget']
        if not budget:
            raise ValueError('This trace requires saved serialized-character delivery')
        full = set(order[:budget['kept']])
        boundary = budget['boundary']
        boundary_id = boundary['id'] if boundary else None
        expected_contexts = budget['kept'] + bool(boundary)
        assert len(r['contexts']) == expected_contexts
        assert meta['delivered_chunk_ids'] == order[:expected_contexts]
        assert sum(map(len, r['contexts'])) == budget['chars']
        for i, cid in enumerate(order[:budget['kept']]):
            assert len(r['contexts'][i]) == units[cid]['serialized_chars']
        if boundary:
            assert boundary_id == order[budget['kept']]
            assert len(r['contexts'][-1]) == boundary['chars_kept']
            assert boundary['chars_full'] == units[boundary_id]['serialized_chars']
        credited = set(r['context_ids'])
        expected_credit = {aid for cid in full for aid in units[cid]['artifact_ids']}
        assert credited == expected_credit
        checked.update({'saved_deliveries': 1, 'full_units': len(full), 'partial_units': bool(boundary)})
        sources = []
        for aid in index['questions'][qid]:
            pointers = []
            for cid in index['artifacts'][aid]:
                row = rankings.get(cid)
                status = ('full_unit' if cid in full else 'partial_unit' if cid == boundary_id else
                          'outside_budget' if cid in positions else 'not_nominated')
                pointers.append({'chunk_id': cid, 'score_rank': row['rank'] if row else None,
                    'score': row['score'] if row else None,
                    'nomination': nomination.get(cid), 'recovery': recovery.get(cid),
                    'delivery_position': positions.get(cid), 'complete_unit_chars': costs.get(cid),
                    'status': status, 'boundary': boundary if cid == boundary_id else None,
                    'facet_paths': safe_witnesses(row['provenance'], graph) if row else {}})
            status = ('credited' if aid in credited else 'partial_only' if any(p['status']=='partial_unit' for p in pointers)
                      else 'outside_budget' if any(p['status']=='outside_budget' for p in pointers)
                      else 'not_nominated' if pointers else 'not_in_frozen_graph')
            statuses[status] += 1
            sources.append({'artifact_id': aid, 'status': status, 'credited': aid in credited,
                            'first_score_rank': min((p['score_rank'] for p in pointers if p['score_rank'] is not None), default=None),
                            'first_delivery_position': min((p['delivery_position'] for p in pointers if p['delivery_position'] is not None), default=None),
                            'first_complete_unit_chars': min((p['complete_unit_chars'] for p in pointers if p['complete_unit_chars'] is not None), default=None),
                            'chunks': pointers})
        cases.append({'question_id': qid, 'budget': budget['budget'], 'delivered_chars': budget['chars'],
                      'gold_sources': len(sources), 'credited_sources': sum(s['credited'] for s in sources),
                      'sources': sources})
    return {'run': folder.name, 'run_sha256': sha(folder / 'arm_outputs.jsonl'), 'cases': cases,
            'summary': {'questions_traced': len(cases), 'source_question_links': sum(statuses.values()),
                        'statuses': dict(statuses), 'verified': dict(checked)},
            'limits': 'Source-level credit follows the actual harness. A full graph unit may contain only part of a cited source; neither credit nor a partial boundary proves the required answer evidence is present.'}


def render(out, index, traces):
    # Self-contained local display; use textContent for all corpus-derived labels.
    payload = json.dumps({'index': index, 'traces': traces}, ensure_ascii=False).replace('<', '\\u003c')
    template = (ROOT / 'tools/facet_gold_trace.html').read_text(encoding='utf-8')
    (out / 'index.html').write_text(template.replace('__DATA__', payload), encoding='utf-8')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', type=Path, action='append', help='Saved joint-arm folder; repeat to compare runs')
    p.add_argument('--subset', type=Path, default=ROOT / 'data/gold100.jsonl')
    p.add_argument('--out', type=Path, default=OUT)
    args = p.parse_args()
    index, units, graph = build_index(args.out, args.subset.resolve())
    traces = [trace_run(folder.resolve(), index, units, graph) for folder in (args.run or [DEFAULT_RUN])]
    write(args.out / 'run_traces.json', traces)
    render(args.out, index, traces)
    report = {'index': index['summary'], 'runs': [{k:t[k] for k in ('run','summary')} for t in traces],
              'model_calls': 0, 'embedding_calls': 0, 'retrieval_reruns': 0,
              'index_sha256': sha(args.out / 'gold_source_index.json'),
              'unit_index_sha256': sha(args.out / 'chunk_delivery_index.json'),
              'code_sha256': sha(Path(__file__)), 'template_sha256': sha(ROOT / 'tools/facet_gold_trace.html')}
    write(args.out / 'verification.json', report)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

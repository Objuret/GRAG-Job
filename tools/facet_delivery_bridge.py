"""Prepare, then explicitly replay actual serialized delivery over frozen rankings.

No model, DB, embeddings, new labels, raw content output, or ranking changes.
"""
import argparse
import ast
import gzip
import hashlib
import importlib.util
import json
import sys
import time
import traceback
from pathlib import Path

import facet_phrase_preservation_analysis as support

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'output/research/2026-09-22-joint-streams/independent_sources'
OUT = BASE / 'delivery_bridge'
PHRASE = BASE / 'fresh_smoke/phrase_preservation/analysis.json'
GRAPH = ROOT / 'output/research/2026-09-21-facet-validity/route_snapshot/graph.json'
ARM = ROOT / 'test/arms/artefact_v2.py'
CUT = ROOT / 'prod/harness/char_budget.py'
BUDGET = 72000


def read(p):
    return json.loads(p.read_text(encoding='utf-8'))


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def save(p, value):
    with p.open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write('\n')


def payload(path):
    return json.loads(gzip.decompress(path.read_bytes())) if path.name.endswith('.gz') else read(path)


def ordered(rec):
    ids = [cid for f in rec['frontiers'] for cid in sorted(f['chunk_ids'])]
    assert len(ids) == len(set(ids)), 'Recovered chunk order duplicates a chunk'
    return ids


def prepare():
    assert not (OUT / 'plan.json').exists(), 'Preserve frozen plan'
    previous = read(PHRASE)
    paths = {ROOT / p: h for p, h in previous['input_sha256'].items()}
    for p, h in paths.items():
        assert sha(p) == h, 'Prior frozen input changed: ' + str(p.relative_to(ROOT))
    for p in (Path(__file__), PHRASE, ARM, CUT, OUT / 'PROTOCOL.md', OUT / 'AREA_ORDER_REVIEW.md'):
        paths[p] = sha(p)
    conditions = []
    for row in previous['runs']:
        for cohort, value in row['cohorts'].items():
            path = ROOT / value['file']
            d = payload(path)
            assert (d['question_id'], d['reading_id']) == (row['question_id'], value['reading_id'])
            ids = ordered(d['recruitment'])
            conditions.append({'cohort': cohort, 'question_id': row['question_id'], 'reading_id': value['reading_id'],
                'file': value['file'], 'sha256': sha(path), 'ordered_chunk_ids_sha256': digest(ids),
                'supported_chunk_count': len(ids), 'research_selected_chunks': value['selected_chunks'],
                'research_source_characters': value['selected_source_characters'],
                'research_known_support': value['known_support']})
    assert len(conditions) == 42
    save(OUT / 'plan.json', {'schema_version': 1, 'budget': BUDGET, 'conditions': conditions,
        'input_sha256': {str(p.relative_to(ROOT)): h for p, h in paths.items()},
        'resolver_functions': ['_load_verified_doc', '_nth_entry', '_resolve_chunk', '_budget_contexts'],
        'raw_root': 'data/raw', 'source_resolution_executed': False,
        'scope_order_parity': 'Independent AREA_ORDER_REVIEW.md: all42 unchanged supported orders; do not append unsupported chunks.'})
    print(json.dumps({'prepared_conditions': 42, 'source_resolution_executed': False}))


def resolver(chunks):
    """Load only pure delivery helpers, with memoization in this private namespace."""
    spec = importlib.util.spec_from_file_location('_delivery_bridge_char_budget', CUT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    tree = ast.parse(ARM.read_text(encoding='utf-8'))
    names = {'_load_verified_doc', '_nth_entry', '_resolve_chunk', '_budget_contexts'}
    funcs = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    assert {n.name for n in funcs} == names
    namespace = {'json': json, 'hashlib': hashlib, 'Path': Path, 'RAW_ROOT': (ROOT / 'data/raw').resolve(),
                 'cut_at_budget': mod.cut_at_budget}
    exec(compile(ast.Module(body=funcs, type_ignores=[]), str(ARM), 'exec'), namespace)
    original = namespace['_resolve_chunk']
    docs, units = {}, {}

    def cached(row, cache):
        cid = row['chunkId']
        if cid not in units:
            units[cid] = original(row, cache)
        return units[cid]

    # This is an isolated extracted-helper namespace, not a production import.
    # The cached function returns the unchanged actual resolver's exact output.
    namespace['_resolve_chunk'] = cached
    return namespace['_budget_contexts'], lambda cid: cached(chunks[cid], docs), docs, units


def quote_map():
    """Existing strings only; eligibility comes from the frozen support auditor."""
    out = {}
    action = BASE / 'need_selection/content_audit'
    aliases = read(action / 'private_manifest.json')['aliases'] | read(action / 'record_context_probe.json')['additional_reader_aliases']
    for reader in ('reader_one', 'reader_two'):
        entries = {}
        for suffix in ('', '_additional'):
            entries.update({e['passage_id']: e for e in read(action / (reader + suffix + '.json'))['entries']})
        out[reader] = {cid: {c: v['quotes'] for c, v in entries[a]['components'].items()} for cid, a in aliases.items()}
    sent = BASE / 'crossed_content'
    aliases = read(sent / 'private_manifest.json')['aliases'] | read(sent / 'supplement_manifest.json')['aliases']
    for reader in ('reader_a', 'reader_b'):
        entries = {}
        for suffix in ('', '_supplement'):
            entries.update({e['passage_id']: e for e in read(sent / (reader + suffix + '.json'))['entries']})
        out[reader] = {cid: {c: v['quotes'] for c, v in entries[a]['components'].items()} for cid, a in aliases.items()}
    return out


def quote_check(quotes, text):
    flags = [bool(q) and (q in text or json.dumps(q, ensure_ascii=False)[1:-1] in text) for q in quotes]
    return {'verified': bool(flags) and all(flags), 'quote_count': len(flags), 'matched_quote_count': sum(flags)}


def initialize_support(chunks, get_unit, paths):
    auditor = support.make_support_auditor(GRAPH, chunks, paths)
    all_ids = list(chunks)
    fake = {'selected_chunk_ids': all_ids, 'frontiers': [{'chunk_ids': [cid], 'cumulative_source_characters': i}
            for i, cid in enumerate(all_ids)]}
    quotes = quote_map()
    cases, checks = {}, {}
    for qid in ('independent_durable_messages_current_models', 'sentiment_review_observations', 'sentiment_intended_use'):
        known = auditor(qid, fake)
        readers, case_checks = {}, {}
        for reader, value in known['readers'].items():
            if reader == 'intersection':
                continue
            readers[reader], case_checks[reader] = {}, {}
            for component, detail in value['components'].items():
                candidates = detail['selected_witness_ids']
                case_checks[reader][component] = {cid: quote_check(quotes[reader][cid][component], get_unit(cid)[0]) for cid in candidates}
                readers[reader][component] = {cid for cid in candidates if case_checks[reader][component][cid]['verified']}
        reader_names = list(readers)
        readers['intersection'] = {c: set.intersection(*(readers[r][c] for r in reader_names)) for c in readers[reader_names[0]]}
        cases[qid] = {'known': known, 'readers': readers}
        checks[qid] = case_checks
    # Event credit uses direct review evidence and quote checks by both readers;
    # the intended-use question does not reclassify that event as a required need.
    review = cases['sentiment_review_observations']
    event_verified = set.intersection(*review['readers']['intersection'].values())
    for qid, case in cases.items():
        case['events'] = {event: set(d['selected_witness_ids']) & event_verified for event, d in case['known']['events'].items()}
    return auditor, cases, checks


def group_detail(candidates, qualified, full, costs, credited, get_unit):
    candidates, qualified = set(candidates), set(qualified)
    selected = full & qualified
    finite = {cid: costs[cid] for cid in qualified if cid in costs}
    minimum = min(finite.values(), default=None)
    credited_witnesses = {cid: sorted(set(get_unit(cid)[1]) & credited) for cid in candidates}
    credited_witnesses = {cid: aids for cid, aids in credited_witnesses.items() if aids}
    return {'selected_witness_ids': sorted(selected), 'known_acquisition_cost': minimum,
        'first_known_witness_ids': sorted(cid for cid, cost in finite.items() if cost == minimum),
        'quote_unverifiable_witness_ids': sorted(candidates-qualified),
        'fully_delivered_but_quote_unverifiable_ids': sorted(full & (candidates-qualified)),
        'credited_artifact_ids_by_known_witness_chunk': credited_witnesses,
        'artifact_credit_without_fully_delivered_qualifying_witness': bool(credited_witnesses) and not bool(selected)}


def run():
    assert not (OUT / 'analysis.json').exists(), 'Preserve completed bridge'
    plan = read(OUT / 'plan.json')
    for name, expected in plan['input_sha256'].items():
        assert sha(ROOT / name) == expected, 'Frozen bridge input changed: ' + name
    start = time.perf_counter()
    chunks = {c['chunkId']: c for c in read(GRAPH)['chunks']}
    budget_contexts, get_unit, docs, units = resolver(chunks)
    paths = []
    auditor, cases, quote_checks = initialize_support(chunks, get_unit, paths)
    rows = []
    for condition in plan['conditions']:
        d = payload(ROOT / condition['file'])
        ids = ordered(d['recruitment'])
        assert digest(ids) == condition['ordered_chunk_ids_sha256']
        contexts, id_lists, artifact_ids, block = budget_contexts([chunks[cid] for cid in ids], BUDGET, docs)
        full_ids = ids[:block['kept']]
        full, credited = set(full_ids), set(artifact_ids)
        assert sum(len(t) for t in contexts) == block['chars'] <= BUDGET
        assert contexts[:block['kept']] == [get_unit(cid)[0] for cid in full_ids]
        boundary = block['boundary']
        if boundary:
            assert boundary['id'] == ids[block['kept']]
            assert contexts[-1] == get_unit(boundary['id'])[0][:boundary['chars_kept']]
        expected_artifacts = list(dict.fromkeys(aid for aids in id_lists[:block['kept']] for aid in aids))
        assert artifact_ids == expected_artifacts
        qid = condition['question_id']
        case = cases.get(qid)
        # Resolve only as far as delivery plus first known and first verified
        # witnesses require. Earlier cumulative lengths are indispensable costs.
        end = block['kept'] + bool(boundary)
        positions = {cid: i+1 for i, cid in enumerate(ids)}
        if case:
            groups = [set(v['selected_witness_ids']) for r in case['known']['readers'].values() for v in r['components'].values()]
            groups += [set(v['selected_witness_ids']) for v in case['known']['events'].values()]
            groups += [s for r in case['readers'].values() for s in r.values()] + list(case['events'].values())
            for group in groups:
                first = min((positions[cid] for cid in group if cid in positions), default=0)
                end = max(end, first)
        cumulative, frontiers, costs = 0, [], {}
        for cid in ids[:end]:
            cumulative += len(get_unit(cid)[0])
            costs[cid] = cumulative
            frontiers.append({'chunk_ids': [cid], 'cumulative_source_characters': cumulative})
        actual_rec = {'selected_chunk_ids': full_ids, 'frontiers': frontiers}
        raw_support = auditor(qid, actual_rec)
        verified = None
        if case:
            readers = {}
            for reader, components in case['readers'].items():
                detail = {c: group_detail(case['known']['readers'][reader]['components'][c]['selected_witness_ids'],
                    valid, full, costs, credited, get_unit) for c, valid in components.items()}
                minima = [v['known_acquisition_cost'] for v in detail.values()]
                readers[reader] = {'components': detail, 'all_components_fully_delivered': all(v['selected_witness_ids'] for v in detail.values()),
                    'known_complete_acquisition_cost': max(minima) if all(x is not None for x in minima) else None}
            events = {event: group_detail(case['known']['events'][event]['selected_witness_ids'], valid,
                      full, costs, credited, get_unit) for event, valid in case['events'].items()}
            verified = {'readers': readers, 'events': events, 'unjudged_fully_delivered_chunk_ids': raw_support['unjudged_selected_chunk_ids']}
        rows.append({'cohort': condition['cohort'], 'question_id': qid, 'reading_id': condition['reading_id'],
            'budget': block, 'fully_delivered_chunk_ids': full_ids, 'artifact_ids_credited': artifact_ids,
            'full_unit_source_characters': sum(len(get_unit(cid)[0]) for cid in full_ids),
            'resolved_prefix_count_for_acquisition': end, 'singleton_cumulative_costs': costs,
            'partial_boundary': None if not boundary else {**boundary, 'artifact_ids_of_unit': get_unit(boundary['id'])[1],
                'content_support_status': 'unknown; not counted as a fully delivered witness',
                'artifact_ids_already_credited_elsewhere': sorted(set(get_unit(boundary['id'])[1]) & credited)},
            'unfiltered_known_chunk_support': raw_support, 'quote_verified_support': verified,
            'research_saved_text_support': condition['research_known_support']})
        # Never write contexts or resolved text.
        del contexts
    source_docs = [{'relpath': relpath, 'expected_sha256': expected} for relpath, expected in docs]
    unit_meta = {cid: {'serialized_characters': len(text), 'resolved_text_sha256': hashlib.sha256(text.encode()).hexdigest(),
                       'artifact_ids': aids} for cid, (text, aids) in units.items()}
    result = {'plan_sha256': sha(OUT / 'plan.json'), 'conditions_completed': len(rows), 'runs': rows,
        'quote_verification': quote_checks, 'resolved_units': unit_meta, 'verified_source_documents': source_docs,
        'unique_resolved_units': len(units), 'unique_source_documents': len(docs), 'elapsed_seconds': time.perf_counter()-start,
        'limits': 'Delivery-only bridge of frozen rankings. Full-unit support is a known-witness lower bound. Partial units and unmatched evidence strings are unknown. Artifact ID credit is not supporting-content delivery. Existing model-reader judgments are not human gold or exhaustive recall.'}
    save(OUT / 'analysis.json', result)
    write_report(result)
    print(json.dumps({'conditions_completed': len(rows), 'unique_resolved_units': len(units), 'unique_source_documents': len(docs)}))


def write_report(result):
    lines = ['# Serialized-delivery bridge', '',
        'The existing 42 rankings were passed through the actual 72,000-character resolver/budget helpers. No retrieval, scope, facet weight or annotation changed. Full recovered orders, including beyond the former research cutoff, were used. The independent area/order audit passed all42 before this run.', '',
        'Full-unit support is a lower bound from previously judged witnesses whose quoted evidence can be found in the actual resolved unit. Partial boundary content and unverifiable evidence are unknown. Artifact-ID credit is reported separately and can come from another chunk of a split record.', '',
        '| Cohort | Question ID | Reading | Full units | Delivered chars | Partial unit | Credited artifact IDs | Known complete support cost | Full support |',
        '|---|---|---|---:|---:|---|---:|---:|---|']
    for row in result['runs']:
        support_result = row['quote_verified_support']
        witness = support_result['readers']['intersection'] if support_result else None
        lines.append('| '+ ' | '.join(map(str, [row['cohort'], row['question_id'], row['reading_id'].rsplit('_', 1)[-1],
            len(row['fully_delivered_chunk_ids']), row['budget']['chars'], 'yes' if row['partial_boundary'] else 'no',
            len(row['artifact_ids_credited']), witness['known_complete_acquisition_cost'] if witness else 'not audited',
            witness['all_components_fully_delivered'] if witness else 'not audited'])) + ' |')
    lines += ['', '## Event delivery', '', '| Cohort | Question ID | Reading | Event | Known complete-unit cost | Full witness | ID credited without full witness |', '|---|---|---|---|---:|---|---|']
    for row in result['runs']:
        if not row['quote_verified_support']:
            continue
        for event, value in row['quote_verified_support']['events'].items():
            lines.append('| '+ ' | '.join(map(str, [row['cohort'], row['question_id'], row['reading_id'].rsplit('_', 1)[-1], event,
                value['known_acquisition_cost'], bool(value['selected_witness_ids']), value['artifact_credit_without_fully_delivered_qualifying_witness']])) + ' |')
    checks = [v for case in result['quote_verification'].values() for reader in case.values() for component in reader.values() for v in component.values()]
    lines += ['', f"Checked {len(checks)} reader/component/witness coordinates; {sum(not v['verified'] for v in checks)} had unverifiable or missing quote evidence. Per-coordinate counts and IDs remain in analysis.json; no quote or resolved raw text is emitted.", '',
        f"Resolved {result['unique_resolved_units']} unique chunks from {result['unique_source_documents']} hash-verified source documents, cached across all42 conditions. Elapsed {result['elapsed_seconds']:.2f} seconds.", '',
        'analysis.json retains each reader and their intersection, component costs, unjudged full chunks, partial boundary metadata, exact artifact IDs, serialized unit hashes/lengths and old research measurements. The unfiltered known-chunk estimate is separate from quote-verified credit. PR6 and PR10 are distinct; PR10 is additional context for intended use, not a required second event. The differences in budgets and serialization do not by themselves establish better or worse retrieval, exhaustive recall, or valid facet semantics.']
    with (OUT / 'RESULTS.md').open('x', encoding='utf-8') as f:
        f.write('\n'.join(lines)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args()
    try:
        run() if args.run else prepare()
    except Exception as exc:
        # No raw exception text or locals: corpus values can occur in exceptions.
        record = {'exception_type': type(exc).__name__, 'frames': [
            {'file': Path(frame.filename).name, 'line': frame.lineno, 'function': frame.name}
            for frame in traceback.extract_tb(exc.__traceback__)]}
        save(OUT / ('private_exception_' + str(time.time_ns()) + '.json'), record)
        print(json.dumps({'status': 'failed', 'exception_type': type(exc).__name__, 'detail': 'private sanitized exception record saved'}))
        sys.exit(1)

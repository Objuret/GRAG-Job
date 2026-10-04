"""Audit one frozen phrase-preservation development trial; no scoring or new labels.

Support construction is copied from facet_fresh_smoke_analysis, parameterized here.
No imported globals are changed and no pipeline/capture stage is invoked.
"""
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'output/research/2026-09-22-joint-streams/independent_sources'
FRESH = BASE / 'fresh_smoke'
OUT = FRESH / 'phrase_preservation'
FACETS = ('topic', 'temporal', 'why', 'activity', 'concreteness')

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def check_hashes(mapping):
    for name, expected in mapping.items():
        assert sha(ROOT / name) == expected, 'Frozen input differs: ' + name

def verify_frozen_inputs(manifest_path, inputs, paths, key_path=('input_sha256',)):
    expected = read(manifest_path)
    for key in key_path:
        expected = expected[key]
    paths.append(manifest_path)
    for path in inputs:
        name = str(path.relative_to(ROOT))
        assert name in expected and sha(path) == expected[name], name
        paths.append(path)

def make_support_auditor(gp, chunks, paths):
    all_support={};pool_by_case={};readers_by_case={};events={}
    action=BASE/'need_selection/content_audit'; sent=BASE/'crossed_content'
    verify_frozen_inputs(BASE/'query_interpretation_intervention/content_cost.json',
        [gp,action/'private_manifest.json',action/'record_context_probe.json',
         *[action/(r+suffix+'.json') for r in ('reader_one','reader_two')
           for suffix in ('','_additional')]],paths)
    verify_frozen_inputs(sent/'private_manifest.json',[gp],paths)
    verify_frozen_inputs(sent/'join.json',
        [sent/'private_manifest.json',sent/'reader_a.json',sent/'reader_b.json'],paths)
    verify_frozen_inputs(sent/'verification.json',
        [sent/'supplement_manifest.json',sent/'supplement_packet.json',
         sent/'reader_a_supplement.json',sent/'reader_b_supplement.json'],paths,
        key_path=('supplement','input_sha256'))
    p=action/'private_manifest.json';q=action/'record_context_probe.json';paths += [p,q]
    aliases=read(p)['aliases']|read(q)['additional_reader_aliases']
    aq='independent_durable_messages_current_models'; readers={}
    for r in ('reader_one','reader_two'):
        entries={}
        for suffix in ('','_additional'):
            p=action/(r+suffix+'.json');paths.append(p)
            entries.update({e['passage_id']:e for e in read(p)['entries']})
        readers[r]={c:{cid for cid,a in aliases.items() if entries[a]['scope']=='supports_requested_system'
                         and entries[a]['components'][c]['category']=='direct'}
                    for c in ('durability','model_updates','refresh_frequency')}
        for cid,a in aliases.items():
            for v in entries[a]['components'].values():
                for quote in v['quotes']: assert quote and quote in chunks[cid]['source_text']
    readers['intersection']={c:readers['reader_one'][c]&readers['reader_two'][c] for c in readers['reader_one']}
    all_support[aq]=readers;pool_by_case[aq]=set(aliases)
    p=sent/'private_manifest.json';q=sent/'supplement_manifest.json';paths += [p,q]
    aliases=read(p)['aliases']|read(q)['aliases'];reverse={a:cid for cid,a in aliases.items()}
    for qid,components in {'sentiment_intended_use':('offering','tailoring'),
                           'sentiment_review_observations':('accuracy','tests','documentation')}.items():
        readers={}
        for r in ('reader_a','reader_b'):
            entries={}
            for suffix in ('','_supplement'):
                p=sent/(r+suffix+'.json');paths.append(p)
                entries.update({e['passage_id']:e for e in read(p)['entries']})
            readers[r]={c:{cid for cid,a in aliases.items() if entries[a]['components'][c]['scope']=='supported'
                           and entries[a]['components'][c]['category']=='direct'} for c in components}
            for cid,a in aliases.items():
                for v in entries[a]['components'].values():
                    for quote in v['quotes']: assert quote and quote in chunks[cid]['source_text']
        readers['intersection']={c:readers['reader_a'][c]&readers['reader_b'][c] for c in components}
        all_support[qid]=readers;pool_by_case[qid]=set(aliases)
        events[qid]={'PR6':{reverse['item_048'],reverse['item_060']},'PR10':{reverse['item_058']}}
    def audit(qid,rec):
        chosen=set(rec['selected_chunk_ids'])
        costs={cid:f['cumulative_source_characters'] for f in rec['frontiers'] for cid in f['chunk_ids']}
        if qid not in all_support:return None
        result={}
        for reader,cs in all_support[qid].items():
            details={}
            for c,cids in cs.items():
                finite={cid:costs[cid] for cid in cids if cid in costs};minimum=min(finite.values()) if finite else None
                details[c]={'selected_witness_ids':sorted(chosen&cids),'known_acquisition_cost':minimum,
                            'first_known_witness_ids':sorted(cid for cid,v in finite.items() if v==minimum)}
            minima=[x['known_acquisition_cost'] for x in details.values()]
            result[reader]={'components':details,'all_components_selected':all(x['selected_witness_ids'] for x in details.values()),
                            'known_complete_acquisition_cost':max(minima) if all(x is not None for x in minima) else None}
        return {'readers':result,'unjudged_selected_chunk_ids':sorted(chosen-pool_by_case[qid]),
                'events':{e:{'selected':bool(chosen&cids),'selected_witness_ids':sorted(chosen&cids),
                              'known_acquisition_cost':min((costs[cid] for cid in cids if cid in costs),default=None)}
                          for e,cids in events.get(qid,{}).items()}}
    return audit


def verify_recruitment(rec, chunks):
    """Recompute costs and maximal whole-frontier prefix, including beyond-budget costs."""
    chosen = set(rec['selected_chunk_ids'])
    assert len(chosen) == len(rec['selected_chunk_ids'])
    assert sum(len(chunks[c]['source_text']) for c in chosen) == rec['selected_source_characters'] <= 72000
    running, seen, prefix, crossed = 0, set(), set(), False
    for frontier in rec['frontiers']:
        ids = set(frontier['chunk_ids'])
        assert len(ids) == len(frontier['chunk_ids']) and not seen & ids
        seen.update(ids)
        running += sum(len(chunks[c]['source_text']) for c in ids)
        assert running == frontier['cumulative_source_characters']
        if not crossed:
            if running <= 72000:
                prefix.update(ids)
            else:
                crossed = True
    assert chosen == prefix, 'Selection is not the maximal complete-frontier budget prefix'
    return chosen


def load_capture(bundle, questions, paths):
    path = bundle / 'query_capture/query_captures.json'
    paths.append(path)
    data = read(path)
    check_hashes(data['source_sha256'])
    captures = {c['question_id']: c for c in data['captures']}
    assert len(captures) == 7 and set(captures) == set(questions)
    for qid, c in captures.items():
        assert c['question'] == questions[qid] and c['generation_validation']['ok']
        assert len(c['readings']) == 2 and {r['repeat'] for r in c['readings']} == {0, 1}
        assert all(r['ok'] for r in c['readings'])
    return data, captures


def load_demo(bundle, capture, reading, chunks, paths):
    path = bundle / 'retrieval' / reading['id'] / 'retrieval.json'
    paths.append(path)
    data = read(path)
    assert (data['question_id'], data['reading_id']) == (capture['question_id'], reading['id'])
    assert data['question'] == capture['question'] and data['description'] == capture['description']
    assert data['query_tags'] == capture['clean_tags']
    weights = [[v['facets'][f] for f in FACETS] for v in reading['values']]
    assert [v['t'] for v in reading['values']] == capture['clean_tags']
    assert data['query_facet_weights'] == weights
    check_hashes(data['input_sha256'])
    array_path = path.parent / 'ranking_arrays.npz'
    assert sha(array_path) == data['ranking_arrays_sha256']
    paths.append(array_path)
    assert data['policy']['coefficients'] == [1, .25, .25, .25, .25]
    assert data['policy']['source_character_budget'] == 72000
    chosen = verify_recruitment(data['recruitment'], chunks)
    assert {c['chunk_id'] for c in data['contexts']} == chosen
    assert all(c['source_text'] == chunks[c['chunk_id']]['source_text'] for c in data['contexts'])
    return data


# Qualitative observations recorded from the seven completed GENERATE outputs,
# before trial retrieval outcomes. These are query-fidelity observations, not new
# source relevance judgments, and do not prescribe answer-derived expected tags.
FIDELITY = {
    'independent_sensor_review_sequence': 'Preserves new sensor protocols and checking/approval sequence. The description retains dates and ordering; no specific dates or checking mechanism are invented.',
    'independent_sensor_pivot_reason': 'Preserves sensor-protocol support and reads already-merged as a merged implementation. Implementation reversal is stronger than reconsideration: the question does not establish an actual reversal. No specific cause is invented.',
    'independent_durable_messages_current_models': 'Preserves service-message durability, AI model updates, and refresh frequency. Persistence and scheduling are generic restatements, not invented concrete mechanisms. The named Smart Actions for Slack phrase survives cleaning; the audit does not silently remove it.',
    'sentiment_review_observations': 'Preserves multilingual contextual-analysis changes as a complete phrase alongside sentiment accuracy, integration tests, and documentation. The description retains the review relation; it invents no review findings.',
    'sentiment_intended_use': 'Preserves multilingual sentiment analysis and customization. The description retains enterprise benefits and tailoring but omits Slack, which remains in the raw question. Enterprise solutions and customization are broad handles, not specific promised features.',
    'trendforce_sprint_progress': 'Preserves sprint review, Kubernetes deployment, and automated scaling with completion/remaining-work concepts. Additional data load is shortened to data load: the extra-load modifier is not retained in the generated description or tags. No concrete completion status is invented.',
    'trendforce_scaling_roadmap': 'Preserves peak-load handling, manual-data-work reduction, and third-party integrations. Scalability, automation, and efficiency are broader inferences from the requested functions; no particular mechanism or integration is invented.',
}


def main():
    assert not (OUT / 'analysis.json').exists(), 'Preserve completed trial audit'
    gp = ROOT / 'output/research/2026-09-21-facet-validity/route_snapshot/graph.json'
    paths = [Path(__file__), gp, OUT / 'PROTOCOL.md', OUT / 'downstream_plan.json']
    qp = BASE / 'questions.json'
    paths.append(qp)
    questions = {q['id']: q['question'] for q in read(qp)}
    chunks = {c['chunkId']: c for c in read(gp)['chunks']}
    auditor = make_support_auditor(gp, chunks, paths)
    bundles = {'original': BASE, 'fresh': FRESH, 'trial': OUT}
    captures = {label: load_capture(bundle, questions, paths) for label, bundle in bundles.items()}
    summary_path = BASE / 'query_reconstruction/run/selection_summary.json'
    paths.append(summary_path)
    archive_manifest_path = summary_path.parent / 'manifest.json'
    paths.append(archive_manifest_path)
    archive_hashes = read(archive_manifest_path)['output_sha256']
    assert sha(summary_path) == archive_hashes[summary_path.name]
    originals = {(r['question_id'], r['reading_id']): r for r in read(summary_path) if r['mode'] == 'max'}
    assert len(originals) == 14
    rows, interpretations = [], []
    for qid, question in questions.items():
        interpretation = {'question_id': qid, 'question': question, 'trial_fidelity_observation': FIDELITY[qid], 'cohorts': {}}
        for label, (_, cs) in captures.items():
            c = cs[qid]
            interpretation['cohorts'][label] = {k: c[k] for k in ('description', 'raw_description', 'raw_tags', 'clean_tags', 'exclusions')}
            interpretation['cohorts'][label]['readings'] = [{k: r[k] for k in ('id', 'repeat', 'ok', 'values')} for r in c['readings']]
        interpretations.append(interpretation)
        for repeat in (0, 1):
            row = {'question_id': qid, 'repeat': repeat, 'cohorts': {}, 'selection_comparisons': {}}
            chosen_sets = {}
            for label, (_, cs) in captures.items():
                c = cs[qid]
                r = next(r for r in c['readings'] if r['repeat'] == repeat)
                if label == 'original':
                    saved = originals[(qid, r['id'])]
                    path = summary_path.parent / saved['file']
                    paths.append(path)
                    assert sha(path) == saved['sha256']
                    assert sha(path) == archive_hashes[path.name]
                    data = json.loads(gzip.decompress(path.read_bytes()))
                    assert (data['question_id'], data['reading_id'], data['mode']) == (qid, r['id'], 'max')
                else:
                    path = bundles[label] / 'retrieval' / r['id'] / 'retrieval.json'
                    data = load_demo(bundles[label], c, r, chunks, paths)
                rec = data['recruitment']
                chosen_sets[label] = verify_recruitment(rec, chunks)
                row['cohorts'][label] = {'reading_id': r['id'], 'file': str(path.relative_to(ROOT)),
                    'selected_chunks': len(chosen_sets[label]), 'selected_source_characters': rec['selected_source_characters'],
                    'known_support': auditor(qid, rec)}
            for left, right in (('original', 'fresh'), ('original', 'trial'), ('fresh', 'trial')):
                a, b = chosen_sets[left], chosen_sets[right]
                row['selection_comparisons'][left + '_to_' + right] = {'jaccard': len(a & b) / len(a | b),
                    'added_chunk_ids': sorted(b-a), 'removed_chunk_ids': sorted(a-b)}
            rows.append(row)
    capture_reports = {}
    for label, (data, _) in captures.items():
        receipts = [c['generation_result'] for c in data['captures']] + [r for c in data['captures'] for r in c['readings']]
        costs = [r['cost_usd_reported'] for r in receipts if r.get('cost_usd_reported') is not None]
        capture_reports[label] = {'counts': data.get('counts'), 'reported_cost_usd_sum': sum(costs), 'cost_reports_available': len(costs)}
    result = {'input_sha256': {str(p.relative_to(ROOT)): sha(p) for p in set(paths)},
        'capture_reports': capture_reports, 'trial_retrievals_verified': len(rows), 'cohorts_per_reading': 3,
        'interpretations': interpretations, 'runs': rows,
        'limits': 'Seven development questions with two SCORE readings each, not fourteen independent interpretations or held-out evaluation. Generation noise and fresh SCORE values both change; this does not isolate the prompt sentence or establish facet validity. Source labels are existing independent model judgments, not human gold. Known component/event acquisition costs are incomplete support bounds, not recall. PR10 is extra context for intended use, not a required second review. Unjudged selections remain unknown; repeat indices across cohorts are not paired stochastic replications.'}
    (OUT / 'analysis.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'trial_retrievals_verified': len(rows), 'capture_reports': capture_reports}, ensure_ascii=False))


if __name__ == '__main__':
    main()

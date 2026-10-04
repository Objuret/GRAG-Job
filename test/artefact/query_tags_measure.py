"""The description-side tags against the question-side tags of one querytagger call, no gold.

Per question of an ids file: the one `query_content` call through artefact_v4's own cache
stage (no re-ask: a failed call is recorded and the run stops); both tag lists embedded with
the arm's embedder; per list the graph tags each query tag picks at HERB_V4_BAND over the
arm's eligible tags (product names excluded casefolded), and the chunks those graph tags
reach on the arm's edge set. Writes one row per question, ids only.

    python test/artefact/query_tags_measure.py --ids data/10smoke.jsonl --out <dir> --max-calls 10
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'test'), str(ROOT / 'prod')]

from harness.progress import say  # noqa: E402


def _chunks_of(prepared, tag_indices):
    import numpy as np
    keep = np.zeros(len(prepared.graph_tags), dtype=bool)
    keep[list(tag_indices)] = True
    return set(np.unique(prepared.edge_chunk[keep[prepared.edge_tag]]).tolist())


def _side(prepared, fits, band, eligible):
    from arms.artefact_v4 import pick
    tags = set()
    best = None
    for row in fits:
        tags.update(pick(row, band, eligible).tolist())
        top = float(row[eligible].max())
        best = top if best is None else max(best, top)
    return tags, _chunks_of(prepared, tags), best


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--ids', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--max-calls', type=int, required=True)
    args = ap.parse_args(argv)
    say('query_tags_measure: loading artefact_v4 and the question ids')
    from harness.orchestrator import load_chosen_questions, to_arm_question
    from arms import artefact_v4 as V
    from arms.artefact_facet_joint import INTERPRET_MODEL, _cached_stage, _query_cosines
    from artefact import query_content as Q

    questions = [to_arm_question(q) for q in load_chosen_questions(args.ids)]
    flags = V.knobs()
    band = V.BANDS[flags['band']]
    say(f'query_tags_measure: {len(questions)} questions; band {flags["band"]} = {band}; '
        f'preparing the arm')
    prepared = V.prepare_over_corpus(ROOT / 'corpus')
    eligible = prepared.casefold_eligible
    rows, stages, calls, tokens_in, tokens_out = [], [], 0, 0, 0
    try:
        for n, (qid, text) in enumerate(questions, 1):
            system, user = Q.request(text)
            dropped = []

            def validate(raw):
                cleaned, k = V._collapse_duplicate_tags(raw)
                dropped.append(k)
                return Q.parse(text, cleaned)

            if calls >= args.max_calls:
                raise SystemExit(f'query_tags_measure: {calls} calls made, the cap; stopping')
            started = time.perf_counter()
            try:
                content, used, meta = _cached_stage('querytag', system, user, validate,
                                                    prepared.cache_dir)
            except RuntimeError as failure:
                calls += 1
                stages.append({'id': qid, 'failed': str(failure)})
                say(f'query_tags_measure: {qid} failed ({failure}); stopping, no re-ask')
                break
            calls += used.calls
            if meta['cache_hit']:
                saved = meta.get('saved_usage') or {}
                t_in, t_out = int(saved.get('prompt_tokens', 0)), int(saved.get('completion_tokens', 0))
            else:
                t_in, t_out = used.tokens_in, used.tokens_out
            tokens_in += t_in
            tokens_out += t_out
            stages.append({'id': qid, 'key': meta['key'], 'cache_hit': meta['cache_hit'],
                           'tokens_in': t_in, 'tokens_out': t_out,
                           'duplicates_dropped': dropped[-1] if dropped else None,
                           'seconds': round(time.perf_counter() - started, 1)})
            say(f'query_tags_measure: [{n}/{len(questions)}] {qid} answered '
                f'({"cache" if meta["cache_hit"] else "call"}, {t_in} in / {t_out} out); embedding')
            d_names = [t.text for t in content.tags]
            q_names = [t.text for t in content.query_tags]
            d_fit = _query_cosines(content.description, d_names, prepared)[0]['query_tag_cosines']
            q_fit = (_query_cosines(content.description, q_names, prepared)[0]['query_tag_cosines']
                     if q_names else [])
            d_tags, d_chunks, d_best = _side(prepared, d_fit, band, eligible)
            q_tags, q_chunks, q_best = _side(prepared, q_fit, band, eligible) if q_names \
                else (set(), set(), None)
            rows.append({'id': qid, 'd_n': len(d_names), 'q_n': len(q_names),
                         'overlap': len(set(d_names) & set(q_names)),
                         'd_tags': len(d_tags), 'd_chunks': len(d_chunks),
                         'q_tags': len(q_tags), 'q_chunks': len(q_chunks),
                         'q_only_tags': len(q_tags - d_tags), 'q_only_chunks': len(q_chunks - d_chunks),
                         'd_only_tags': len(d_tags - q_tags), 'd_only_chunks': len(d_chunks - q_chunks),
                         'd_best': d_best, 'q_best': q_best})
            say(f'query_tags_measure: {qid} description side {len(d_names)} tags -> '
                f'{len(d_tags)} graph tags, {len(d_chunks)} chunks; question side '
                f'{len(q_names)} tags -> {len(q_tags)} graph tags, {len(q_chunks)} chunks')
    finally:
        prepared.close()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    prompt_sha = hashlib.sha256(Q.SYSTEM.encode('utf-8')).hexdigest()
    cols = ['id', 'd_n', 'q_n', 'overlap', 'd_tags', 'd_chunks', 'q_tags', 'q_chunks',
            'q_only_tags', 'q_only_chunks', 'd_only_tags', 'd_only_chunks', 'd_best', 'q_best']

    def cell(v):
        return '-' if v is None else f'{v:.4f}' if isinstance(v, float) else str(v)

    lines = ['# Query-side tags beside description-side tags, 10smoke', '',
             f'- prompt: `test/artefact/query_content.py` SYSTEM, sha256 `{prompt_sha}`',
             f'- model: {INTERPRET_MODEL}, temperature 0, one call per question, no re-ask '
             f'(artefact_v4 `_cached_stage` stage `querytag`)',
             f'- cache: `{prepared.cache_dir}/querytag/<key>.json`, key = sha256 over '
             f'(stage, model, system, user, max_tries)',
             f'- calls this run: {calls}; tokens as the CLI counts: {tokens_in} in / {tokens_out} out',
             f'- pick: artefact_v4 `pick(fit, band, eligible)` per query tag, band HERB_V4_BAND='
             f'{flags["band"]} = {band} (the knob\'s default; read by HERB_V4_SORT=sum only — the '
             f'default sort adjust_lower has no band and reaches every eligible tag); eligible = '
             f'graph tags not equal to a product name casefolded '
             f'({int(eligible.sum())} of {len(eligible)})',
             f'- chunks reached: chunks with an edge from a picked graph tag on the arm\'s '
             f'{len(prepared.edge_tag)} learned edges over {len(prepared.chunk_ids)} chunks',
             '- columns: d = description-side tags, q = question-side tags; overlap = exact string;'
             ' *_tags / *_chunks = graph tags picked / chunks reached; q_only = reached by q not d;'
             ' d_only the reverse; *_best = highest eligible fit cosine of any tag in the list', '',
             '| ' + ' | '.join(cols) + ' |', '|' + '---|' * len(cols)]
    for r in rows:
        lines.append('| ' + ' | '.join(cell(r[c]) for c in cols) + ' |')
    if rows:
        total = {c: sum(r[c] for r in rows) for c in cols[1:12]}
        lines.append('| total | ' + ' | '.join(str(total[c]) for c in cols[1:12]) + ' | | |')
    lines += ['', '## Calls', '', '| id | key | cache_hit | tokens_in | tokens_out | duplicates dropped | failed |',
              '|---|---|---|---|---|---|---|']
    for s in stages:
        lines.append(f'| {s["id"]} | {s.get("key", "-")} | {s.get("cache_hit", "-")} | '
                     f'{s.get("tokens_in", "-")} | {s.get("tokens_out", "-")} | '
                     f'{s.get("duplicates_dropped", "-")} | {s.get("failed", "")} |')
    (out / 'REPORT.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    (out / 'rows.json').write_text(json.dumps({'rows': rows, 'calls': stages}, indent=1),
                                   encoding='utf-8')
    say(f'query_tags_measure: {len(rows)} rows, {calls} calls, written to {out}')
    return 0 if len(rows) == len(questions) else 1


if __name__ == '__main__':
    sys.exit(main())

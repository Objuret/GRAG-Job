"""Count actual winning route types in saved traces, without reranking or gold.

Private records are streamed mechanically. Only counts and numerical shares are
exported; no questions, tags, texts, answers, explanations or source IDs.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys


def main(folder):
    path = folder / 'arm_outputs.jsonl'
    counts = defaultdict(Counter)
    mass = defaultdict(lambda: defaultdict(float))
    totals = Counter()
    snapshots = set()
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for raw in stream:
            digest.update(raw)
            if not raw.strip():
                continue
            saved = json.loads(raw)
            meta = saved['meta']
            snapshots.add(meta['snapshot']['snapshot_sha256']['graph.json'])
            kept = meta['char_budget']['kept']
            delivered = set(meta['full_recovered_order'][:kept])
            totals['queries'] += 1
            totals['fully_delivered_chunks'] += kept
            per_query_graph = 0
            for row in meta['ranking']['rows']:
                scopes = ['all_candidates']
                if row['chunk_id'] in delivered:
                    scopes.append('fully_delivered')
                graph_chunk = False
                for facet, witness in row['provenance'].items():
                    route = witness['route_type'] if witness else 'unsupported'
                    contribution = witness['contribution'] if witness else 0.
                    if contribution < 0:
                        raise ValueError('Negative saved contribution')
                    for scope in scopes:
                        key = scope + '/' + facet
                        counts[key][route] += 1
                        mass[key][route] += contribution
                    if route not in ('direct', 'unsupported') and contribution > 0:
                        graph_chunk = True
                if graph_chunk and row['chunk_id'] in delivered:
                    per_query_graph += 1
            totals['delivered_chunks_with_any_graph_winner'] += per_query_graph
            totals['queries_with_any_delivered_graph_winner'] += bool(per_query_graph)
    result = {
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'input_sha256': digest.hexdigest(), 'input_bytes': path.stat().st_size,
        'tool_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'graph_sha256': sorted(snapshots), 'totals': dict(totals),
        'winning_route_counts': dict(counts),
        'winning_contribution_mass': dict(mass),
        'model_calls': 0, 'new_retrievals': 0, 'gold_read': False,
        'limits': ['Saved pre-repair run; not current serving quality.',
                   'Winner counts are exposure, not causal improvement or relevance.',
                   'Contribution mass is a score total, not a probability or fraction of recall.',
                   'Tied route labels can differ without changing scores.'],
    }
    out = folder / 'graph_route_diagnosis'
    out.mkdir(exist_ok=True)
    with (out / 'route_audit.json').open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main(Path(sys.argv[1]).resolve())

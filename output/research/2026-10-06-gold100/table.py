"""The hundred, one table: every metric the harness wrote, per run, as a mean over the questions
the new run answered (and over each run's own questions beside it), and the token and time use of
the new run. Reads eval_results.jsonl, arm_outputs.jsonl (usage fields only) and the manifests.
No gold file, no question or answer text, no model call."""
import io
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
ROOT = Path('C:/Coding/exjobbet/GRAG-Job/output/k=chars')
NEW = 'artefact_v4__gold100__cb72000__20261005T223320Z'
RUNS = [('artefact_v4', NEW),
        ('vector', 'vector__gold100__cb72000__20260814T145615Z'),
        ('lucene', 'lucene__gold100__cb72000__20260814T134547Z')]
METRICS = ['context_recall_id', 'context_precision_id', 'context_recall_llm', 'faithfulness',
           'answer_correctness', 'semantic_similarity', 'context_recall_nonllm',
           'context_precision_nonllm', 'rouge', 'bleu', 'chrf', 'string_similarity',
           'string_presence', 'exact_match']


def rows(folder):
    path = ROOT / folder / 'eval_results.jsonl'
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def values(rs, metric):
    return {r['question_id']: r['value'] for r in rs
            if r['metric'] == metric and r.get('status') == 'ok' and isinstance(r['value'], (int, float))}


held = {name: rows(folder) for name, folder in RUNS}
answered = set(values(held['artefact_v4'], 'context_recall_id'))
print(f'questions the new run answered: {len(answered)}')
status = Counter((r['metric'], r.get('status')) for r in held['artefact_v4'])
print('new run, rows per metric (ok / other): '
      + ', '.join(f'{m} {status.get((m, "ok"), 0)}/{sum(v for (mm, s), v in status.items() if mm == m and s != "ok")}'
                  for m in METRICS))
print()
print(f'{"metric":26s}' + ''.join(f'{name + " (same q)":>22s}{"n":>4s}' for name, _ in RUNS)
      + ''.join(f'{name + " (own q)":>18s}{"n":>4s}' for name, _ in RUNS[1:]))
for metric in METRICS:
    line = f'{metric:26s}'
    own = ''
    for name, _ in RUNS:
        got = values(held[name], metric)
        same = [got[q] for q in answered if q in got]
        line += f'{(sum(same) / len(same)) if same else float("nan"):22.4f}{len(same):4d}'
        if name != 'artefact_v4':
            own += f'{(sum(got.values()) / len(got)) if got else float("nan"):18.4f}{len(got):4d}'
    print(line + own)
print()
types = {r['question_id']: r['type'] for r in held['artefact_v4']}
by_type = defaultdict(list)
for q in answered:
    by_type[types[q]].append(q)
print('by question type, new run / vector / lucene on the same questions:')
for metric in ('context_recall_id', 'faithfulness', 'answer_correctness', 'context_recall_llm'):
    print(f'   {metric}')
    for kind in sorted(by_type):
        cells = []
        for name, _ in RUNS:
            got = values(held[name], metric)
            use = [got[q] for q in by_type[kind] if q in got]
            cells.append(f'{sum(use) / len(use):.3f} ({len(use)})' if use else '-')
        print(f'      {kind:9s} ' + ' / '.join(cells))
print()
new = values(held['artefact_v4'], 'context_recall_id')
for name, _ in RUNS[1:]:
    for metric in ('context_recall_id', 'answer_correctness', 'faithfulness', 'context_recall_llm'):
        a, b = values(held['artefact_v4'], metric), values(held[name], metric)
        both = [q for q in answered if q in a and q in b]
        if both:
            print(f'{metric}: new against {name}: higher on {sum(a[q] > b[q] for q in both)}, '
                  f'equal on {sum(a[q] == b[q] for q in both)}, lower on {sum(a[q] < b[q] for q in both)} of {len(both)}')
print()
gen_in, gen_out, gen_cached, gen_s, search_s, delivered, ret_in, ret_out, ret_s = ([] for _ in range(9))
with open(ROOT / NEW / 'arm_outputs.jsonl', encoding='utf-8') as f:
    for line in f:
        if line.strip():
            row = json.loads(line)
            g, r = row['generator'], row['retrieval']
            gen_in.append(g['tokens_in']); gen_out.append(g['tokens_out'])
            gen_cached.append(g.get('cached_input_tokens') or 0); gen_s.append(g.get('time_s') or 0.)
            ret_in.append(r['tokens_in']); ret_out.append(r['tokens_out']); ret_s.append(r.get('time_s') or 0.)
            search_s.append(row['search_time_s']); delivered.append(len(row['contexts']))
print(f'new run, {len(gen_in)} answered questions')
print(f'   querytagger and query embedding: tokens in {sum(ret_in):,} (median {statistics.median(ret_in):.0f}), '
      f'out {sum(ret_out):,} (median {statistics.median(ret_out):.0f}), seconds median {statistics.median(ret_s):.1f}')
print(f'   answers: tokens in {sum(gen_in):,} (median {statistics.median(gen_in):.0f}), cached {sum(gen_cached):,}, '
      f'out {sum(gen_out):,} (median {statistics.median(gen_out):.0f}), seconds median {statistics.median(gen_s):.1f}')
print(f'   search seconds median {statistics.median(search_s):.1f}; contexts delivered median {statistics.median(delivered)}')
for name in ('run_manifest.json', 'eval_manifest.json'):
    path = ROOT / NEW / name
    if path.exists():
        m = json.loads(path.read_text(encoding='utf-8'))
        keep = {k: m[k] for k in m if k in ('generator_model', 'interpreter_model', 'judge_model', 'n_questions',
                                            'n_ran', 'n_failed', 'n_exhausted', 'timestamp', 'usage',
                                            'judge_usage', 'n_cells', 'n_ok', 'n_failed_cells', 'elapsed_s',
                                            'judge', 'totals', 'cells')}
        print(f'   {name}: ' + json.dumps(keep, default=str)[:900])
        print(f'      keys: {sorted(m)}')

"""Paired differences in context_recall_id between the new run and each other run, over the
questions the new run answered: mean difference, a 95% interval by resampling the questions
(paired bootstrap, 20,000 draws, seed fixed), the sign counts and a Wilcoxon signed-rank p.
Reads eval_results.jsonl only. The choice of the two tests is the orchestrator's."""
import io
import json
import sys
from pathlib import Path

import numpy as np

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
ROOT = Path('C:/Coding/exjobbet/GRAG-Job/output/k=chars')
NEW = 'artefact_v4__gold100__cb72000__20261005T223320Z'
OTHERS = [('vector (08-14)', 'vector__gold100__cb72000__20260814T145615Z'),
          ('lucene (08-14)', 'lucene__gold100__cb72000__20260814T134547Z'),
          ('artefact_v3 walk, no growth (09-13)', 'artefact_v3__gold100__cb72000__20260913T143959Z'),
          ('artefact_scope (09-03)', 'artefact_scope__gold100__cb72000__20260903T153153Z'),
          ('artefact_v2 (09-13)', 'artefact_v2__gold100__cb72000__20260913T145627Z')]


def recall(folder):
    out = {}
    with open(ROOT / folder / 'eval_results.jsonl', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                if r['metric'] == 'context_recall_id' and r.get('status') == 'ok' and isinstance(r['value'], (int, float)):
                    out[r['question_id']] = float(r['value'])
    return out


new = recall(NEW)
ids = sorted(new)
rng = np.random.default_rng(20261006)
draws = rng.integers(0, len(ids), size=(20000, len(ids)))
try:
    from scipy.stats import wilcoxon
except Exception:
    wilcoxon = None
print(f'questions {len(ids)}; new run mean {np.mean([new[q] for q in ids]):.4f}')
for label, folder in OTHERS:
    other = recall(folder)
    if any(q not in other for q in ids):
        print(f'{label}: {sum(q not in other for q in ids)} of the questions missing, skipped')
        continue
    d = np.array([new[q] - other[q] for q in ids])
    means = d[draws].mean(axis=1)
    low, high = np.percentile(means, [2.5, 97.5])
    p = wilcoxon(d).pvalue if wilcoxon is not None and np.any(d != 0) else float('nan')
    print(f'{label:38s} new minus it: mean {d.mean():+.4f}, 95% interval {low:+.4f} to {high:+.4f}; '
          f'higher {int((d > 0).sum())} / equal {int((d == 0).sum())} / lower {int((d < 0).sum())}; Wilcoxon p {p:.2g}')

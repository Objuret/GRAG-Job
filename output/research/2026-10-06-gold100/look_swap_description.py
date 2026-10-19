"""What the changed description wording does by itself (his 2026-10-06 "how can changing the
desc-wording slightly make it worse … i just cant believe you did that shit correctly").

Two saved querytagger answers per smoke question, both made with the tree shown: A with the
description asked for as the content that would answer, B as the content the question is looking
for. The model writes the description and the tags in one answer, so B's tags are another draw
too. Here the parts are swapped and the arm run offline (no model call, embeddings from disk),
the product of the returned places floated as in the two runs:
    A            description A, tags A      (the run at 0.636)
    B            description B, tags B      (the run at 0.561)
    desc B       description B, tags A      only the description changed
    tags B       description A, tags B      only the tags changed
recall_id through the harness's gold mapping. COUNTS AND MEANS ONLY: no question, description,
tag, citation or chunk is printed."""
import io
import json
import os
import sys
from pathlib import Path

import numpy as np

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
os.environ['HERB_V4_OFFLINE'] = 'on'
os.environ['HERB_V4_SCOPE'] = 'product'
ROOT = Path('C:/Coding/exjobbet/GRAG-Job')
sys.path[:0] = [str(ROOT / 'prod'), str(ROOT / 'test')]
from harness import chat, orchestrator, questions as QS
from harness.contract import ModelUsage


def _blocked(*args, **kwargs):
    raise RuntimeError('model call blocked: this check makes none')


chat.post = _blocked
import arms.artefact_v4 as V
from artefact import query_content as Q

SOURCE = ROOT / 'output/k=chars/artefact_v4__10smoke__cb72000__20261006T173855Z'
questions = {}
for line in open(SOURCE / 'arm_outputs.jsonl', encoding='utf-8'):
    if line.strip():
        row = json.loads(line)
        questions[row['id']] = row['question']
truth = {q.id: q for q in QS.load_questions() if q.id in questions}
prepared = V.prepare_over_corpus(orchestrator.open_corpus(orchestrator.DEFAULT_CORPUS))
tree = V._scope_tree(prepared)['text']


def saved_answer(text, wording):
    system, user = Q.request(text, wording, tree)
    key = V._require_cached_answer(system, user, prepared.cache_dir)
    held = json.loads((Path(prepared.cache_dir) / 'querytag' / (key + '.json')).read_text(encoding='utf-8'))
    cleaned, _ = V._collapse_duplicate_tags(held['raw'])
    return Q.parse(text, cleaned)


current = {}


def handed(text, prepared_):
    return current['content'], ModelUsage(), [{'stage': 'querytag', 'cache_hit': True, 'key': 'swapped',
                                               'asks': 0, 'offline': True,
                                               'duplicate_tags_dropped': 0}]


V._interpret = handed
rows = {name: [] for name in ('A', 'B', 'desc B', 'tags B')}
shared_tags, description_alike = [], []
try:
    for qid in sorted(questions):
        text = questions[qid]
        a, b = saved_answer(text, 'answer'), saved_answer(text, 'looking')
        ta = {t.text.casefold() for t in a.tags + a.query_tags}
        tb = {t.text.casefold() for t in b.tags + b.query_tags}
        shared_tags.append((len(ta & tb), len(ta), len(tb)))
        description_alike.append(a.description.strip() == b.description.strip())
        cites = {str(c) for c in truth[qid].citations}
        variants = {
            'A': a, 'B': b,
            'desc B': Q.QueryContent(text, b.description, a.tags, a.query_tags, a.places),
            'tags B': Q.QueryContent(text, a.description, b.tags, b.query_tags, a.places),
        }
        for name, content in variants.items():
            current['content'] = content
            out = V.answer_one_question((qid, text), prepared, None, 50, 72000)
            rows[name].append(len(set(out.context_ids) & cites) / len(cites))
finally:
    prepared.close()

print(f'questions {len(questions)}; the two answers\' descriptions identical on {sum(description_alike)}')
print('tags shared between the two answers of a question (shared / in A / in B): '
      + ', '.join(f'{s}/{x}/{y}' for s, x, y in shared_tags))
print()
print('recall_id, mean over the ten:')
for name, values in rows.items():
    print(f'   {name:8s} {np.mean(values):.3f}')
print()
print('per question (A, B, desc B, tags B):')
for i in range(len(questions)):
    print('   question', i + 1, ' '.join(f'{rows[name][i]:.2f}' for name in rows))
a, b, d, t = (np.array(rows[name]) for name in ('A', 'B', 'desc B', 'tags B'))
print()
print(f'only the description changed (desc B minus A): mean {np.mean(d - a):+.3f}; questions up '
      f'{int((d > a + 1e-9).sum())}, down {int((d < a - 1e-9).sum())}')
print(f'only the tags changed (tags B minus A): mean {np.mean(t - a):+.3f}; questions up '
      f'{int((t > a + 1e-9).sum())}, down {int((t < a - 1e-9).sum())}')

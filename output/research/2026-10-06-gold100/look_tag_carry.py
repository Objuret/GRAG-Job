"""What moves the delivered chunks between two querytagger answers for one question (his
2026-10-06 "the reason behind the numbers is the important part, or more, the difference").

The ten smoke questions, two saved answers each, both made with the tree shown: A with the
description asked for as the content that would answer, B as the content the question is looking
for. Four runs of the arm offline (no model call, embeddings from disk), the product of the
returned places floated: A, B, description B with tags A, description A with tags B.
Printed per question and over the ten: how many of the delivered chunks stay when only the
description is swapped and when only the tags are swapped; and for the gold chunks A delivers
and B does not, what happened to their three terms (tags, text, lifts), their place in the order,
and whether the tag phrase that carried them under A stands in B's answer at all.
Gold through the harness's mapping. COUNTS AND MEANS ONLY: no question, description, tag,
citation, chunk text or chunk id is printed. The saved answers were made under the instruction
text of 17:30Z; that text is read back from the call records kept beside the answers."""
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
import arms.artefact_v2 as A2
import arms.artefact_v4 as V
from artefact import query_content as Q

SOURCE = ROOT / 'output/k=chars/artefact_v4__10smoke__cb72000__20261006T173855Z'
OLD_PLACES = 'every place where the content it is looking for can be expected'
questions = {}
for line in open(SOURCE / 'arm_outputs.jsonl', encoding='utf-8'):
    if line.strip():
        row = json.loads(line)
        questions[row['id']] = row['question']
truth = {q.id: q for q in QS.load_questions() if q.id in questions}
prepared = V.prepare_over_corpus(orchestrator.open_corpus(orchestrator.DEFAULT_CORPUS))
tree = V._scope_tree(prepared)
cache = Path(prepared.cache_dir) / 'querytag'

# the two instruction texts the saved answers were asked under
systems = {'answer': set(), 'looking': set()}
for path in cache.glob('*.started.json'):
    held = json.loads(path.read_text(encoding='utf-8'))
    if held.get('model') == V.INTERPRET_MODEL and OLD_PLACES in held.get('system', ''):
        systems['looking' if Q.LOOKING[0][1] in held['system'] else 'answer'].add(held['system'])
if any(len(texts) != 1 for texts in systems.values()):
    raise SystemExit(f'expected one instruction text each, found {({k: len(v) for k, v in systems.items()})}')
systems = {name: next(iter(texts)) for name, texts in systems.items()}


def saved_answer(text, wording):
    key = V._require_cached_answer(systems[wording], 'Question: ' + text, prepared.cache_dir)
    held = json.loads((cache / (key + '.json')).read_text(encoding='utf-8'))
    cleaned, _ = V._collapse_duplicate_tags(held['raw'])
    return Q.parse(text, cleaned)


current, kept = {}, {}
original_chain = V.WK.chain


def keeping_chain(layer, query, cos_noise, **switches):
    got = original_chain(layer, query, cos_noise, **switches)
    kept['walked'] = got
    return got


def handed(text, prepared_):
    return current['content'], ModelUsage(), [{'stage': 'querytag', 'cache_hit': True, 'key': 'swapped',
                                               'asks': 0, 'offline': True,
                                               'duplicate_tags_dropped': 0}]


V.WK.chain = keeping_chain
V._interpret = handed
docs = {}
ids_of = [set(A2._resolve_chunk(row, docs)[1]) for row in prepared.chunk_rows]
index = {c: i for i, c in enumerate(prepared.chunk_ids)}
n = len(prepared.chunk_ids)
NAMES = ('A', 'B', 'desc B', 'tags B')
per_question = []
try:
    for qid in sorted(questions):
        text = questions[qid]
        a, b = saved_answer(text, 'answer'), saved_answer(text, 'looking')
        cites = {str(c) for c in truth[qid].citations}
        gold = np.array([bool(ids & cites) for ids in ids_of])
        variants = {
            'A': a, 'B': b,
            'desc B': Q.QueryContent(text, b.description, a.tags, a.query_tags, a.places),
            'tags B': Q.QueryContent(text, a.description, b.tags, b.query_tags, a.places),
        }
        got = {}
        for name, content in variants.items():
            current['content'] = content
            out = V.answer_one_question((qid, text), prepared, None, 50, 72000)
            walked = kept['walked']
            tier, _ = V.scope_tiers(content.places or (), tree, n, below=False)
            final = sorted(walked['order'], key=lambda i: int(tier[i]))
            place = np.empty(n, dtype=np.int64)
            place[np.asarray(final)] = np.arange(n)
            phrases = [t.text.casefold() for t in content.tags + content.query_tags]
            sent = np.array([index[c] for c in out.meta['ranking']['delivered_chunk_ids']])
            got[name] = {
                'recall': len(set(out.context_ids) & cites) / len(cites),
                'sent': set(sent.tolist()), 'place': place, 'phrases': phrases,
                'T': np.asarray(walked['T'], dtype=float),
                'text': np.asarray(walked['side'], dtype=float),
                'lift': np.asarray(walked['S_prime'], dtype=float) - np.asarray(walked['S'], dtype=float),
                'strength': np.asarray(walked['S_prime'], dtype=float),
                'winner': np.asarray(walked['winner']), 'has_edge': np.asarray(walked['has_edge']),
            }
        per_question.append((gold, got))
finally:
    V.WK.chain = original_chain
    prepared.close()


def mean(values):
    return float(np.mean(values)) if len(values) else float('nan')


print(f'questions {len(per_question)}; chunks {n}')
print()
print('1. How many delivered chunks stay when one part of the answer is swapped')
print('   per question: delivered under A | still delivered with only the description swapped | with only '
      'the tags swapped | with both (B) || recall A, description swapped, tags swapped, B')
stay_d, stay_t, stay_b = [], [], []
for i, (gold, got) in enumerate(per_question, 1):
    base = got['A']['sent']
    kd, kt, kb = (len(base & got[name]['sent']) for name in ('desc B', 'tags B', 'B'))
    stay_d.append(kd / len(base))
    stay_t.append(kt / len(base))
    stay_b.append(kb / len(base))
    print(f'   question {i:2d}: {len(base):2d} | {kd:2d} | {kt:2d} | {kb:2d} || '
          + ' '.join(f'{got[name]["recall"]:.2f}' for name in ('A', 'desc B', 'tags B', 'B')))
print(f'   share of the delivered chunks that stay, mean over the ten: description swapped {mean(stay_d):.2f}, '
      f'tags swapped {mean(stay_t):.2f}, both {mean(stay_b):.2f}')
print()
print('2. The gold chunks A delivers and B does not, and the chunks B delivers in their place')
all_lost, all_in = [], []
for i, (gold, got) in enumerate(per_question, 1):
    A, B = got['A'], got['B']
    lost = sorted(c for c in A['sent'] - B['sent'] if gold[c])
    came = sorted(B['sent'] - A['sent'])
    gained = [c for c in came if gold[c]]
    line = (f'   question {i:2d}: gold chunks {int(gold.sum()):2d}; delivered under A '
            f'{sum(1 for c in A["sent"] if gold[c])}, under B {sum(1 for c in B["sent"] if gold[c])}; '
            f'lost {len(lost)}, gained {len(gained)}; chunks delivered {len(A["sent"])} / {len(B["sent"])}')
    print(line)
    for c in lost:
        carried = bool(A['has_edge'][c]) and A['T'][c] > 0
        phrase = A['phrases'][int(A['winner'][c])] if carried else None
        all_lost.append({
            'dT': B['T'][c] - A['T'][c], 'dtext': B['text'][c] - A['text'][c],
            'dlift': B['lift'][c] - A['lift'][c], 'place_a': int(A['place'][c]) + 1,
            'place_b': int(B['place'][c]) + 1, 'cut_b': len(B['sent']),
            'carried': carried, 'phrase_in_b': (phrase in B['phrases']) if carried else None,
            'T_a': A['T'][c], 'T_b': B['T'][c], 'text_a': A['text'][c], 'text_b': B['text'][c]})
    for c in came:
        all_in.append({'dT': B['T'][c] - A['T'][c], 'dtext': B['text'][c] - A['text'][c],
                       'dlift': B['lift'][c] - A['lift'][c], 'gold': bool(gold[c])})
if all_lost:
    print(f'   the {len(all_lost)} lost gold chunks, B minus A: tag term {mean([r["dT"] for r in all_lost]):+.2f}, '
          f'text term {mean([r["dtext"] for r in all_lost]):+.2f}, lifts {mean([r["dlift"] for r in all_lost]):+.2f}')
    print(f'      tag term under A {mean([r["T_a"] for r in all_lost]):.2f}, under B {mean([r["T_b"] for r in all_lost]):.2f}; '
          f'text term under A {mean([r["text_a"] for r in all_lost]):.2f}, under B {mean([r["text_b"] for r in all_lost]):.2f}')
    print(f'      place in the order under A (median) {int(np.median([r["place_a"] for r in all_lost]))}, under B '
          f'{int(np.median([r["place_b"] for r in all_lost]))} (B delivers {int(np.median([r["cut_b"] for r in all_lost]))} chunks at the median); '
          f'places past the cut under B: {sorted(r["place_b"] - r["cut_b"] for r in all_lost)}')
    carried = [r for r in all_lost if r['carried']]
    print(f'      carried by a tag under A: {len(carried)} of {len(all_lost)}; of those, the carrying phrase stands in '
          f"B's answer on {sum(1 for r in carried if r['phrase_in_b'])}")
    largest = [max(('tags', abs(r['dT'])), ('text', abs(r['dtext'])), ('lifts', abs(r['dlift'])), key=lambda x: x[1])[0]
               for r in all_lost]
    print('      the term that changed most, per lost chunk: ' + ', '.join(
        f'{name} {largest.count(name)}' for name in ('tags', 'text', 'lifts')))
if all_in:
    print(f'   the {len(all_in)} chunks B delivers and A does not ({sum(1 for r in all_in if r["gold"])} gold), B minus A: '
          f'tag term {mean([r["dT"] for r in all_in]):+.2f}, text term {mean([r["dtext"] for r in all_in]):+.2f}, '
          f'lifts {mean([r["dlift"] for r in all_in]):+.2f}')
    largest = [max(('tags', abs(r['dT'])), ('text', abs(r['dtext'])), ('lifts', abs(r['dlift'])), key=lambda x: x[1])[0]
               for r in all_in]
    print('      the term that changed most, per chunk: ' + ', '.join(
        f'{name} {largest.count(name)}' for name in ('tags', 'text', 'lifts')))
print()
print('3. How far each term moves between the two answers, over the chunks of the floated product')
for label, key in (('tag term', 'T'), ('text term', 'text'), ('lifts', 'lift'), ('strength', 'strength')):
    moves, spans = [], []
    for gold, got in per_question:
        pool = np.flatnonzero(got['A']['place'] < int(np.sum(got['A']['place'] < n)))  # all chunks
        A, B = got['A'], got['B']
        inside = np.array(sorted(A['sent'] | B['sent']))
        moves.append(float(np.mean(np.abs(B[key][inside] - A[key][inside]))))
        spans.append(float(np.std(A[key][inside])))
    print(f'   {label:10s}: mean absolute change over the chunks either answer delivers {mean(moves):.2f}; '
          f'their spread under A {mean(spans):.2f}')

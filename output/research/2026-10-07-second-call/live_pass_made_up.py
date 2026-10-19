"""One live pass of the two query-side calls on the made-up question: what is sent, what comes
back, what it costs. Run from the repo root. The tree is read from a saved second-call request,
so no graph is loaded."""
import json
import pathlib
import sys
import time

sys.path[:0] = ['prod', 'test']
sys.stdout.reconfigure(encoding='utf-8')
from arms import artefact_v4 as V  # noqa: E402
from artefact import query_content as Q  # noqa: E402

cache = pathlib.Path('output/private/artefact_v4_cache')
walk = json.loads(pathlib.Path('output/walkthrough/20261005T040000Z/walkthrough.json')
                  .read_text(encoding='utf-8'))
question = walk['question'] if isinstance(walk.get('question'), str) else walk['question']['text']
tree = None
for path in (cache / 'scope').glob('*.json'):
    if not path.name.endswith('.started.json'):
        system = json.loads(path.read_text(encoding='utf-8'))['signature']['system']
        tree = system.split('<tree>\n')[1].split('\n</tree>')[0]
        break
stack, paths = [], []
for line in tree.split('\n'):
    depth = (len(line) - len(line.lstrip(' '))) // 2
    stack[depth:] = [line.strip()]
    paths.append('/'.join(stack))
print('question:', question)
print('tree:', len(tree), 'characters,', len(paths), 'places')


def validate(raw):
    cleaned, _ = V._collapse_duplicate_tags(raw)
    return Q.parse(question, cleaned)


def saved(stage, key):
    return json.loads((cache / stage / (key + '.json')).read_text(encoding='utf-8'))


started = time.perf_counter()
first = Q.request(question)
print('\n--- first call, the message as sent ---\n' + first[1])
content, used, record = V._ask('querytag', first, validate, cache, False)
got = saved('querytag', record['key'])
print('--- first call, the answer ---')
print('description:', content.description)
for label, tags in (('tags', content.tags), ('question tags', content.query_tags)):
    for tag in tags:
        print(f'  {label}: {tag.text}  {dict(zip(Q.FACETS, tag.readings))}')
print('cache_hit', record['cache_hit'], '| asks', record['asks'], '| tokens in', used.tokens_in,
      'out', used.tokens_out, '| turns', got['response'].get('num_turns'), '| stop',
      got['response'].get('stop_reason'), f'| {used.time_s:.1f}s')
second = Q.scope_request(content, tree)
print('\n--- second call, the message as sent ---\n' + second[1])
places, used, record = V._ask('scope', second, Q.parse_places, cache, False)
got = saved('scope', record['key'])
print('--- second call, the answer ---')
print('places:', list(places), '| all in the tree:', all(p in paths for p in places))
print('cache_hit', record['cache_hit'], '| asks', record['asks'], '| tokens in', used.tokens_in,
      'out', used.tokens_out, '| turns', got['response'].get('num_turns'), '| stop',
      got['response'].get('stop_reason'), f'| {used.time_s:.1f}s')
print(f'\nwhole pass {time.perf_counter() - started:.1f}s')

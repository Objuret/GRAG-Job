"""The second call on the made-up question once more, with the CLI's turn-by-turn stream, to see
what each turn is. Reads the first call's saved answer; the tree from a saved request.
Usage: python second_call_turns.py [times]"""
import json
import os
import pathlib
import subprocess
import sys

sys.path[:0] = ['prod', 'test']
sys.stdout.reconfigure(encoding='utf-8')
from arms import artefact_v4 as V  # noqa: E402
from artefact import query_content as Q  # noqa: E402
from harness import chat  # noqa: E402

cache = pathlib.Path('output/private/artefact_v4_cache')
question = json.loads(pathlib.Path('output/walkthrough/20261005T040000Z/walkthrough.json')
                      .read_text(encoding='utf-8'))['question']
tree = None
for path in (cache / 'scope').glob('*.json'):
    if not path.name.endswith('.started.json'):
        system = json.loads(path.read_text(encoding='utf-8'))['signature']['system']
        tree = system.split('<tree>\n')[1].split('\n</tree>')[0]
        break


def validate(raw):
    cleaned, _ = V._collapse_duplicate_tags(raw)
    return Q.parse(question, cleaned)


content, _, record = V._ask('querytag', Q.request(question), validate, cache, True)
system, user, schema = Q.scope_request(content, tree)
cmd = [chat._CLAUDE_EXE, '-p', '--model', V.INTERPRET_MODEL, '--output-format', 'stream-json',
       '--verbose', '--tools', '', '--safe-mode', '--system-prompt', system,
       '--json-schema', json.dumps(schema)]
for attempt in range(int(sys.argv[1]) if len(sys.argv) > 1 else 1):
    done = subprocess.run(cmd, input=user, capture_output=True, text=True, timeout=300,
                          encoding='utf-8', cwd=chat._claude_cwd(),
                          env={**os.environ, 'MEMPALACE_HOOKS_AUTO_SAVE': 'false'})
    print(f'--- attempt {attempt + 1}, exit {done.returncode} ---')
    for line in done.stdout.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        kind = event.get('type')
        if kind in ('assistant', 'user'):
            for block in (event.get('message') or {}).get('content') or []:
                if not isinstance(block, dict):
                    print(f'  {kind}: {str(block)[:300]}')
                elif block.get('type') == 'text':
                    print(f'  {kind} text: {block["text"][:400]!r}')
                elif block.get('type') == 'tool_use':
                    print(f'  {kind} tool_use {block.get("name")}: {json.dumps(block.get("input"))[:300]}')
                elif block.get('type') == 'tool_result':
                    print(f'  {kind} tool_result: {json.dumps(block.get("content"))[:400]}')
                else:
                    print(f'  {kind} {block.get("type")}')
        elif kind == 'result':
            usage = event.get('usage') or {}
            print('  result: turns', event.get('num_turns'), '| stop', event.get('stop_reason'),
                  '| structured_output', event.get('structured_output'), '| in',
                  usage.get('input_tokens'), '+ cache write',
                  usage.get('cache_creation_input_tokens'), '+ cache read',
                  usage.get('cache_read_input_tokens'), '| out', usage.get('output_tokens'))

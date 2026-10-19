"""The made-up question's arrays, dumped once per role setting. No model call (offline guard)."""
import os, sys
from pathlib import Path
ROOT = Path('C:/Coding/exjobbet/GRAG-Job')
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'prod'), str(ROOT / 'test')]
os.environ['HERB_V4_OFFLINE'] = 'on'
out = Path(sys.argv[1])
import walkthrough as W
for name, (tag, desc, quest) in {'all_same': ('passage', 'passage', 'passage'),
                                 'text_query': ('passage', 'query', 'query')}.items():
    os.environ['HERB_V4_WALK_TAGROLE'] = tag
    os.environ['HERB_V4_WALK_DESCROLE'] = desc
    os.environ['HERB_V4_WALK_QUESTROLE'] = quest
    inputs, prepared, provenance = W.load_live(W.QUESTION)
    try:
        W.dump_inputs(inputs, out / f'madeup_{name}.npz')
    finally:
        prepared.close()
    print('dumped', name, provenance['roles'], 'model calls', provenance['model_calls_through_chat_post'],
          'embedding calls', provenance['embedding_calls'], flush=True)

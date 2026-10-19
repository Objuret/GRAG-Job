"""Each pool chunk's time in the graph (his 2026-10-17 "well then, build it!" for the 4-combo; the
abstract's Neo4j layer holds what the retrieval reads).

A chunk holds one or more records; each record keeps its own time in its own field: a Slack
message its `Message.User.timestamp`, a pull request its `created_at`, a document or a meeting
transcript its `date`, a meeting chat line the first line of its `text`. URL lists keep none. A
chunk's times are its records' own times, sorted: `times` on the Chunk node, in seconds since
1970-01-01, a time with no zone read as it stands (the dataset's times carry none). No span is
made of them: a batch's first and last record can lie far apart with nothing of it between. A
chunk whose records keep no time gets no `times`. The records are read from the dataset through
each chunk's pointer. No model call.

    write    reads the times, prints them per kind, sets `times` (the span the builder wrote
             before, time_first and time_last, is taken off)
    verify   counts the chunks that carry them
    remove   takes `times` off every chunk

    NEO4J_DATABASE=herb-eval-volmax .venv/Scripts/python.exe test/graph/build_chunk_times.py write
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / 'prod', ROOT / 'test'):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from arms.artefact_v2 import _load_verified_doc  # noqa: E402
from graph.db import _driver  # noqa: E402

DATABASE = os.environ.get('NEO4J_DATABASE', 'herb-eval-volmax')
BATCH = 2000
STAMP = re.compile(r'\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?)?')

POOL_CYPHER = '''
MATCH (f:File)-[:HAS_CHUNK]->(c:Chunk) WHERE (c)-[:product]->()
RETURN c.chunk_id AS chunk, c.kind AS kind, c.locator_json AS locator,
       f.rel_path AS relpath, f.sha256 AS sha256
'''


def seconds(text):
    """The first date or date-time a text holds, in seconds since 1970-01-01 on one clock; None
    when it holds none."""
    if not isinstance(text, str):
        return None
    found = STAMP.search(text)
    if not found:
        return None
    try:
        when = datetime.fromisoformat(found.group(0).replace(' ', 'T'))
    except ValueError:
        return None
    return (when.replace(tzinfo=None) - datetime(1970, 1, 1)).total_seconds()


def time_of(kind, record):
    """A record's own time in seconds, from the field its kind keeps it in; None when it has none."""
    if kind == 'slack_thread_batch':
        return seconds(((record.get('Message') or {}).get('User') or {}).get('timestamp'))
    if kind == 'pr_batch':
        return seconds(record.get('created_at'))
    if kind in ('document', 'document_part', 'meeting_transcript', 'meeting_transcript_part'):
        return seconds(record.get('date'))
    if kind == 'meeting_chat_batch':
        return seconds((record.get('text') or '').split('\n', 1)[0])
    return None


def record_times(session):
    """chunk id -> its records' times, sorted, over the pool, and per kind (chunks, chunks with a
    time, records with a time)."""
    docs, out, counts = {}, {}, Counter()
    for row in session.run(POOL_CYPHER).data():
        loc = json.loads(row['locator'])
        arr = _load_verified_doc(row['relpath'], row['sha256'], docs)[loc['section']]
        times = [t for t in (time_of(row['kind'], arr[i])
                             for i in (loc['indices'] if 'indices' in loc else [loc['index']]))
                 if t is not None]
        counts[(row['kind'], 'chunks')] += 1
        if times:
            out[row['chunk']] = sorted(times)
            counts[(row['kind'], 'with a time')] += 1
            counts[(row['kind'], 'record times')] += len(times)
    return out, counts


def write(session):
    found, counts = record_times(session)
    print('pool chunks by kind: chunks | with a time | record times')
    for kind in sorted({k for k, _ in counts}):
        print(f'   {kind}: {counts[(kind, "chunks")]} | {counts[(kind, "with a time")]} | '
              f'{counts[(kind, "record times")]}')
    session.run('CREATE INDEX chunk_chunk_id IF NOT EXISTS FOR (c:Chunk) ON (c.chunk_id)')
    rows = [{'chunk': c, 'times': t} for c, t in sorted(found.items())]
    for start in range(0, len(rows), BATCH):
        session.run('UNWIND $rows AS row MATCH (c:Chunk {chunk_id: row.chunk}) '
                    'SET c.times = row.times REMOVE c.time_first, c.time_last',
                    rows=rows[start:start + BATCH])
    session.run('MATCH (c:Chunk) WHERE c.time_first IS NOT NULL OR c.time_last IS NOT NULL '
                'REMOVE c.time_first, c.time_last')
    print(f'write: times set on {len(rows)} chunks of {DATABASE}')
    verify(session)


def verify(session):
    r = session.run('MATCH (c:Chunk) WHERE c.times IS NOT NULL RETURN count(c) AS n, '
                    'sum(size(c.times)) AS times, '
                    'sum(CASE WHEN c.time_first IS NOT NULL THEN 1 ELSE 0 END) AS spans').single()
    print(f"verify: {r['n']} chunks carry their records' times, {r['times']} times in all; "
          f"{r['spans']} still carry the old span")


def remove(session):
    n = session.run('MATCH (c:Chunk) WHERE c.times IS NOT NULL REMOVE c.times '
                    'RETURN count(c) AS n').single()['n']
    print(f'remove: times taken off {n} chunks')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('step', choices=('write', 'verify', 'remove'))
    args = ap.parse_args(argv)
    driver = _driver()
    try:
        with driver.session(database=DATABASE) as session:
            {'write': write, 'verify': verify, 'remove': remove}[args.step](session)
    finally:
        driver.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())

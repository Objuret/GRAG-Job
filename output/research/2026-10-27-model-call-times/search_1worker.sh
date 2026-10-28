#!/usr/bin/env bash
# The six final runs' retrieval again, one question at a time on the laptop, no model call: the
# baselines make none, the artefact reads each first call's answer from its run's store (offline).
# Only the search times are taken from these runs; each question's retrieved records are checked
# against its final run's before any time is used.
set -u
cd /c/Coding/exjobbet/GRAG-Job
PY=.venv/Scripts/python.exe
STAMP=20261027_search_1worker
run() {
  echo "=== $(date -u +%FT%TZ) start: $*"
  "$PY" prod/run.py "$@" --char-budget 72000 --workers 1 --retrieval-only --no-eval
  echo "=== $(date -u +%FT%TZ) exit $?: $*"
}
run --arm lucene --set gold --out "output/k=chars/lucene__gold100__cb72000__$STAMP"
run --arm lucene --set data/answerable715.jsonl --out "output/k=chars/lucene__answerable715__cb72000__$STAMP"
run --arm vector --set gold --out "output/k=chars/vector__gold100__cb72000__$STAMP"
run --arm vector --set data/answerable715.jsonl --out "output/k=chars/vector__answerable715__cb72000__$STAMP"
run --arm artefact_v4 --set gold --out "output/k=chars/artefact_v4__gold100__cb72000__$STAMP" \
    --flag HERB_V4_OFFLINE=on --flag HERB_V4_CACHE=C:/Coding/exjobbet/GRAG-Job-0c082a3/output/private/artefact_v4_cache
run --arm artefact_v4 --set data/answerable715.jsonl --out "output/k=chars/artefact_v4__answerable715__cb72000__$STAMP" \
    --flag HERB_V4_OFFLINE=on --flag HERB_V4_CACHE=output/private/artefact_v4_cache_20261025T211532Z_ab
echo "=== all done $(date -u +%FT%TZ)"

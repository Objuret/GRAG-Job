#!/usr/bin/env bash
# Each re-made run's first question timed again in a warm process: a fresh process makes the run's
# second question first, then the first one. No model call: the baselines make none, the artefact reads
# its first calls from the run's store (offline).
set -u
cd /c/Coding/exjobbet/GRAG-Job
PY=.venv/Scripts/python.exe
SP="C:/Users/jocke/AppData/Local/Temp/claude/c--Coding-exjobbet-GRAG-Job/9c164e78-008e-41e9-85f3-58c55027a64c/scratchpad"
STAMP=20261028_first_question_warm
run() {
  echo "=== $(date -u +%FT%TZ) start: $*"
  "$PY" prod/run.py "$@" --char-budget 72000 --workers 1 --retrieval-only --no-eval
  echo "=== $(date -u +%FT%TZ) exit $?: $*"
}
run --arm lucene --set "$SP/warm_lucene_gold100.jsonl" --out "output/k=chars/lucene__gold100__cb72000__$STAMP"
run --arm vector --set "$SP/warm_vector_gold100.jsonl" --out "output/k=chars/vector__gold100__cb72000__$STAMP"
run --arm artefact_v4 --set "$SP/warm_artefact_v4_gold100.jsonl" --out "output/k=chars/artefact_v4__gold100__cb72000__$STAMP" \
    --flag HERB_V4_OFFLINE=on --flag HERB_V4_CACHE=C:/Coding/exjobbet/GRAG-Job-0c082a3/output/private/artefact_v4_cache
run --arm lucene --set "$SP/warm_lucene_answerable715.jsonl" --out "output/k=chars/lucene__answerable715__cb72000__$STAMP"
run --arm vector --set "$SP/warm_vector_answerable715.jsonl" --out "output/k=chars/vector__answerable715__cb72000__$STAMP"
run --arm artefact_v4 --set "$SP/warm_artefact_v4_answerable715.jsonl" --out "output/k=chars/artefact_v4__answerable715__cb72000__$STAMP" \
    --flag HERB_V4_OFFLINE=on --flag HERB_V4_CACHE=output/private/artefact_v4_cache_20261025T211532Z_ab
echo "=== all done $(date -u +%FT%TZ)"

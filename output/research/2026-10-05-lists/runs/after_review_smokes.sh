#!/usr/bin/env bash
# After the review's corrections: the four tags-off runs again (their level step changed) and
# three runs that must not move (no multiplier; the ranking; the walk as it was). 10smoke,
# retrieval only, HERB_V4_OFFLINE=on.
cd /c/Coding/exjobbet/GRAG-Job || exit 1
OUT="C:/Users/jocke/AppData/Local/Temp/claude/c--Coding-exjobbet-GRAG-Job/a2b8a286-c232-49f4-b6a3-aca36f28a6b4/scratchpad/after_review_smokes"
mkdir -p "$OUT"
: > "$OUT/results.tsv"

summarise() {
  .venv/Scripts/python.exe - "$1" <<'EOF'
import json, sys, pathlib
d = pathlib.Path(sys.argv[1])
rows = [json.loads(l) for l in (d / 'eval_results.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
def col(metric):
    return {r['question_id']: r['value'] for r in rows if r['metric'] == metric and isinstance(r['value'], (int, float))}
rec, pre = col('context_recall_id'), col('context_precision_id')
per = ' '.join(f"{q}={rec[q]:.3f}" for q in sorted(rec))
print(f"{len(rec)}\t{sum(rec.values())/len(rec):.4f}\t{sum(pre.values())/len(pre):.4f}\t{per}")
EOF
}

run() {  # name questrole flag...
  name=$1; quest=$2; shift 2
  flags=()
  for f in "$@"; do flags+=(--flag "$f"); done
  log="$OUT/$name.log"
  .venv/Scripts/python.exe prod/run.py --arm artefact_v4 --set 10smoke --char-budget 72000 --retrieval-only \
      --flag HERB_V4_SORT=walk --flag HERB_V4_OFFLINE=on --flag HERB_V4_WALK_TAGROLE=passage \
      --flag HERB_V4_WALK_DESCROLE=passage --flag "HERB_V4_WALK_QUESTROLE=$quest" "${flags[@]}" > "$log" 2>&1
  code=$?
  folder=$(grep -o 'artefact_v4__10smoke__cb72000__[0-9TZ]*' "$log" | tail -1)
  if [ "$code" = 0 ] && [ -n "$folder" ]; then nums=$(summarise "output/k=chars/$folder"); else nums="FAILED: $(tail -1 "$log" | cut -c1-160)"; fi
  printf '%s\tquestion=%s %s\texit=%s\t%s\t%s\n' "$name" "$quest" "$*" "$code" "$folder" "$nums" >> "$OUT/results.tsv"
}

run "asitwas_query"           query
run "nomultiplier_query"      query HERB_V4_WALK_SHARES=off
run "ranked_query"            query HERB_V4_WALK_SHARES=off HERB_V4_WALK_RANK=picked
run "notags_query"            query HERB_V4_WALK_TAGS=off
run "notags_nostructure_query" query HERB_V4_WALK_TAGS=off HERB_V4_WALK_STRUCT=off
run "notags_passage"          passage HERB_V4_WALK_TAGS=off
run "notags_nostructure_passage" passage HERB_V4_WALK_TAGS=off HERB_V4_WALK_STRUCT=off
echo "DONE" >> "$OUT/results.tsv"

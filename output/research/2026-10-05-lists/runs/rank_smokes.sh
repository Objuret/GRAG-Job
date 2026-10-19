#!/usr/bin/env bash
# The facet ranking inside the pick (HERB_V4_WALK_RANK=picked) and the tags-off cell, on the walk
# sort with the tags and the description in the same mode. 10smoke, retrieval only,
# HERB_V4_OFFLINE=on (a cache miss raises before any model call).
cd /c/Coding/exjobbet/GRAG-Job || exit 1
OUT="C:/Users/jocke/AppData/Local/Temp/claude/c--Coding-exjobbet-GRAG-Job/a2b8a286-c232-49f4-b6a3-aca36f28a6b4/scratchpad/rank_smokes"
mkdir -p "$OUT"
: > "$OUT/results.tsv"

summarise() {
  .venv/Scripts/python.exe - "$1" <<'EOF'
import json, sys, pathlib, statistics
d = pathlib.Path(sys.argv[1])
rows = [json.loads(l) for l in (d / 'eval_results.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
def col(metric):
    return {r['question_id']: r['value'] for r in rows if r['metric'] == metric and isinstance(r['value'], (int, float))}
rec, pre = col('context_recall_id'), col('context_precision_id')
shares = {'tags': [], 'description': [], 'product': [], 'near': []}
for line in (d / 'arm_outputs.jsonl').read_text(encoding='utf-8').splitlines():
    if line.strip():
        s = ((json.loads(line).get('meta') or {}).get('diagnostics') or {}).get('delivered_term_shares') or {}
        for k in shares:
            if s.get(k) is not None:
                shares[k].append(s[k])
med = ' '.join(f"{k}={statistics.median(v):.3f}" for k, v in shares.items() if v)
per = ' '.join(f"{q}={rec[q]:.3f}" for q in sorted(rec))
print(f"{len(rec)}\t{sum(rec.values())/len(rec):.4f}\t{sum(pre.values())/len(pre):.4f}\t{med}\t{per}")
EOF
}

run() {  # name questrole flag...
  name=$1; quest=$2; shift 2
  flags=()
  for f in "$@"; do flags+=(--flag "$f"); done
  log="$OUT/$name.log"
  start=$(date +%s)
  .venv/Scripts/python.exe prod/run.py --arm artefact_v4 --set 10smoke --char-budget 72000 --retrieval-only \
      --flag HERB_V4_SORT=walk --flag HERB_V4_OFFLINE=on --flag HERB_V4_WALK_TAGROLE=passage \
      --flag HERB_V4_WALK_DESCROLE=passage --flag "HERB_V4_WALK_QUESTROLE=$quest" "${flags[@]}" > "$log" 2>&1
  code=$?
  folder=$(grep -o 'artefact_v4__10smoke__cb72000__[0-9TZ]*' "$log" | tail -1)
  if [ "$code" = 0 ] && [ -n "$folder" ]; then nums=$(summarise "output/k=chars/$folder"); else nums="FAILED: $(tail -1 "$log" | cut -c1-160)"; fi
  printf '%s\tquestion=%s %s\texit=%s\t%s\t%s\t%ss\n' "$name" "$quest" "$*" "$code" "$folder" "$nums" "$(( $(date +%s) - start ))" >> "$OUT/results.tsv"
}

S=HERB_V4_WALK_SHARES=off
R=HERB_V4_WALK_RANK=picked
for quest in query passage; do
  run "check_nomultiplier_$quest"      "$quest" $S
  run "ranked_$quest"                  "$quest" $S $R
  run "ranked_with_multiplier_$quest"  "$quest" $R
  run "ranked_nostructure_$quest"      "$quest" $S $R HERB_V4_WALK_STRUCT=off
  run "notags_$quest"                  "$quest" HERB_V4_WALK_TAGS=off
  run "notags_nostructure_$quest"      "$quest" HERB_V4_WALK_TAGS=off HERB_V4_WALK_STRUCT=off
done
# the tag side alone: the raw question's mode is not read
run "tagsonly"                 query $S HERB_V4_WALK_TEXT=off
run "tagsonly_ranked"          query $S $R HERB_V4_WALK_TEXT=off
run "tagsonly_nostructure"     query $S HERB_V4_WALK_TEXT=off HERB_V4_WALK_STRUCT=off
run "tagsonly_ranked_nostructure" query $S $R HERB_V4_WALK_TEXT=off HERB_V4_WALK_STRUCT=off
echo "DONE" >> "$OUT/results.tsv"

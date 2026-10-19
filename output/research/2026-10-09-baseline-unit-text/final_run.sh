#!/bin/bash
# One baseline on the hundred, one question at a time, from a clean checkout of the commit.
#   final_run.sh <checkout> <arm> <out folder>
# The same command into the same folder resumes. The login token goes to the run's environment
# from the main checkout's .env; it is never printed.
set -u
WT="$1"; ARM="$2"; OUT="$3"
MAIN=/c/Coding/exjobbet/GRAG-Job
CLAUDE_CODE_OAUTH_TOKEN="$(grep -E '^(export )?CLAUDE_CODE_OAUTH_TOKEN=' "$MAIN/.env" | head -1 | sed -E 's/^(export )?CLAUDE_CODE_OAUTH_TOKEN=//' | tr -d "\"'\r")"
export CLAUDE_CODE_OAUTH_TOKEN
export PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8
cd "$WT" || exit 2
echo "checkout $(git rev-parse HEAD) | status lines in code paths: $(git status --porcelain -- prod test tools data pytest.ini refresh_graph.py | wc -l) | started $(date -u +%Y-%m-%dT%H:%M:%SZ)"
"$MAIN/.venv/Scripts/python.exe" prod/run.py --arm "$ARM" --set gold --char-budget 72000 --workers 1 --out "$OUT"
echo "exit $? | finished $(date -u +%Y-%m-%dT%H:%M:%SZ)"

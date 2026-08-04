---
name: laptop-env-limits-no-graphify-broken-venv
description: "Laptop env: graphify 0.8.39 installed (refresh works here since 2026-07-21), dead .venv (use miniconda python), local Neo4j hosts herb-eval (start recipe inside)"
metadata: 
  node_type: memory
  type: project
  originSessionId: 3b7c153b-a8ae-424c-bbfe-5e9a328d91ed
---

Two machines work this repo: the desktop ("Djuret", repo at `A:\exjobbet\repo`, commits authored "Objuret") and this laptop (`C:\Coding\exjobbet\GRAG-Job`, commits authored "Joakim Wikman"). Related: [[v3-state-docs-gitignored-and-absent-on-this-machine]].

On the laptop:
- `graphify` 0.8.39 is installed (miniconda Scripts); `python refresh_graph.py` runs here (verified 2026-07-21: worklist processed, graph rebuilt 777 nodes). `docs/handoff` does not exist on this machine, so the scan notes it missing — harmless. Doc extractions go to the semantic cache via `graphify.cache.save_cached(path, {nodes, edges}, root=REPO, kind="semantic")`; mirror the node/edge schema of existing entries in `graphify-out/cache/semantic/`.
- The repo `.venv` was a synced copy of the DESKTOP's venv — dead executables on this
  laptop, but its site-packages metadata was the exact record of the versions the
  June/July runs used. That copy was destroyed (venv --clear, 2026-07-16) before the
  versions were read — **never wipe an env dir without freezing its metadata first.**
  The canonical record still lives on the desktop: `A:\exjobbet\repo\.venv`. Retrace
  owed there: `.venv\Scripts\python.exe -m pip freeze > v3\requirements.txt`, commit —
  the desktop's versions override the laptop-reconstructed pins now in
  `v3/requirements.txt` (judged RAGAS metrics can differ across ragas versions, so
  eval comparability follows the desktop stack; thesis-era used ragas 0.2.x, laptop
  reconstruction has 0.4.3).
- VS Code auto-activates the repo `.venv` in every terminal, so the user's `python`
  is whatever that venv is — rebuilt natively 2026-07-16 from v3/requirements.txt.
  If it's ever broken again, commands silently do nothing; give full-path commands
  (`C:\Users\jocke\miniconda3\python.exe …`) until fixed.
- **Neo4j runs locally** (since 2026-07-16): Neo4j Desktop 2 instance "herb" at
  `~\.Neo4jDesktop2\Data\dbmss\dbms-7863c729-b4ea-477c-9755-a06a0f9dcbfc`, auth
  DISABLED at the user's direction (localhost-only dev DB). `herb-eval` was loaded
  from the repo's git-lfs dump (`v3/artefact/data/herb-eval.dump`): 4,869 chunks,
  19,716 tags, 67,913 HAS_TAG edges, `tag_emb` + `chunk_desc_emb` + `chunk_fulltext`
  indexes, zero oracle chunks, single run_id `pilot_full_herb`.
  Start it DETACHED — a plain background task's process tree gets reaped between
  turns and takes the server with it. With JAVA_HOME set to
  `~\.Neo4jDesktop2\Cache\runtime\zulu21.*`, use PowerShell
  `Start-Process <dbms>\bin\neo4j.bat -ArgumentList console -WindowStyle Hidden`
  (redirect stdout/stderr to files); the orphaned java survives. Check port 7687
  at session start.
- NIM: working key in `v3/.env` (renewed 2026-07-16). The hosted catalog rotates —
  `z-ai/glm-5.1` became `z-ai/glm-5.2` (410 Gone on the old id); check
  `GET /v1/models` when a model id errors. qwen3.5-397b queues hard; calls need the
  480s timeouts already in the code.
- Benchmark data must stay byte-exact (the artefact arm hash-verifies raw files):
  `.gitattributes` has `v3/data/** -text`. If hash mismatches ever reappear, suspect
  `core.autocrlf=true` re-smudging — restore via `git cat-file blob` writes.

**Why:** Sessions here repeatedly re-diagnosed the same environment gaps; and one
CRLF checkout silently broke the arm's integrity checks.
**How to apply:** Tests with miniconda python from `v3/`. Neo4j must be started per
session before any artefact_v1 work. Skip the graph refresh here; flag for desktop.

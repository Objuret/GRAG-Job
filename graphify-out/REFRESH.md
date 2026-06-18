# Keeping the knowledge graph current

The graph in `graphify-out/` is a **snapshot**. Editing files doesn't update it —
you rebuild it with `refresh_graph.py` (repo root).

## Separate graph per build, on purpose

v1, v2 and v3 share class/file names, so building them together fabricates phantom
cross-build edges (e.g. `v2 chunker --uses--> v3 vector`) that are false and break the
no-cross-imports rule. So each build is its own graph, and **v3 is canon**:

- **ACTIVE — `graphify-out/`** : v3/ + in-repo (gitignored) state/handoff docs
  (docs/state, docs/handoff) + root canon (CLAUDE.md, README.md), wired by bridge edges.
  **This is the graph agents use.** No v1/v2 code.
- **v2 REFERENCE — `v2/graphify-out/`** : the artefact build, built on demand only.
- **v1 REFERENCE — `v1/graphify-out/`** : the frozen v1 stack, built on demand only.

`refresh_graph.py` is the single rebuild authority — never `graphify --update` (it would
drop the external-doc bridges).

## Usage

```powershell
python refresh_graph.py          # rebuild the ACTIVE graph (v3 + external + root)
python refresh_graph.py --v2     # rebuild the v2 REFERENCE graph (from cache, no new LLM)
python refresh_graph.py --v1     # rebuild the v1 REFERENCE graph (from cache, no new LLM)
python refresh_graph.py --force  # allow a >10% node drop (only for deliberate rescopes)
```

What happens on an active rebuild:

- **Code edits** → re-extracted via AST (free, instant). One command, done.
- **Doc edits / new external doc / deletions** → detected by content hash.
  - If a doc needs model re-reading, it does **not** ship a graph missing it. It writes
    `graphify-out/.refresh_worklist.json`, prints which docs, and stops (exit 2).
  - Then: **ask Claude Code → "process graphify-out/.refresh_worklist.json"**. The agent
    extracts each listed doc with bridges into `graphify-out/.concept_index.txt`, writing
    repo docs to graphify's semantic cache (`save_semantic_cache`) and external docs as
    sidecar fragments in `graphify-out/.external_cache/` shaped
    `{source_file,hash,nodes,edges}` (named by `frag_path()`, carrying the body-hash).
  - Re-run `python refresh_graph.py` → everything cached → full rebuild + html.

A repo doc that legitimately extracts to nothing gets an empty cache entry, so it counts
as processed and never re-flags. Re-runs are idempotent.

The v1 reference build is deterministic from the shared cache (v1 docs were already
extracted), so `--v1` needs no new model calls unless a v1 file changed — and v1 is frozen.

## Add another external folder

Edit `EXTERNAL` at the top of `refresh_graph.py`: each entry is
`(real_folder_path, "source_file/prefix/")`. The prefix is what its nodes carry as
`source_file` in the graph (keep it readable, e.g. `notes/myproject/`).

## Outputs (per graph)

`graph.json` · `graph.html` · `GRAPH_REPORT.md`. Community labels are auto-derived
(top node per cluster); run a full `/graphify .` if you want hand-curated names.

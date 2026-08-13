# Keeping the knowledge graph current

The graph in `graphify-out/` is a **snapshot**. Editing files doesn't update it —
you rebuild it with `refresh_graph.py` (repo root).

## What the graph covers

The `v3/` code: every source file graphify detects under `v3/`, minus the benchmark
dataset (`v3/data`) and the run outputs (`v3/output`). Structure comes from the AST —
files, classes, functions, calls, imports, plus the docstrings attached to them.
Prose docs are not in the graph.

`refresh_graph.py` owns the scope and is the single rebuild authority — never
`graphify --update`, which rescopes to the whole repo.

## Usage

```powershell
python refresh_graph.py          # rebuild the graph
python refresh_graph.py --force  # allow a >10% node drop (only for deliberate rescopes)
```

One command, no model calls, seconds. Re-runs are idempotent; unchanged files come
from the AST cache in `graphify-out/cache/ast/`.

The node-drop guard refuses to write a graph more than 10% smaller than the one on
disk. That is a rescope or a broken scan — check which before passing `--force`.

## Outputs

`graph.json` · `graph.html` · `GRAPH_REPORT.md` · `manifest.json`. Community labels are
auto-derived (top node per cluster); run a full `/graphify .` if you want hand-curated
names.

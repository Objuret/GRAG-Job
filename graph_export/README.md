# Graph export

`grag_graph_latest.zip` is a portable JSONL export of the local Neo4j graph (now including the fp32 `Tag.embedding` vectors). The current archive uses the live cluster dimension names: `topic`, `entities`, `activity`, `temporal`, `evidence`.

> The zip exceeds GitHub's 100 MB/file push limit, so it is **not** committed
> whole. It is committed as split `grag_graph_latest.zip.partNN` siblings and
> rebuilt by `scripts/assemble-large-assets.mjs` — which runs automatically on
> `npm install` (root `postinstall`) and at the start of `npm run graph:import`.
> The reassembled `grag_graph_latest.zip` itself is git-ignored.

Import into an empty Neo4j database:

```powershell
npm run backend:install
npm run graph:import
```

Replace an existing local graph:

```powershell
npm run graph:import -- --wipe
```

Raw exports are written to `graph_export/latest/` and are ignored by Git because they are too large uncompressed.

Regenerate the tracked archive after graph-contract changes:

```powershell
npm run graph:export
Compress-Archive -Path graph_export\latest\manifest.json,graph_export\latest\nodes.jsonl,graph_export\latest\relationships.jsonl -DestinationPath graph_export\grag_graph_latest.zip -Force
# Re-split into <100MB parts (delete stale parts first), then commit the parts:
Remove-Item graph_export\grag_graph_latest.zip.part* -ErrorAction SilentlyContinue
cmd /c "split -b 95m -d -a 2 graph_export\grag_graph_latest.zip graph_export\grag_graph_latest.zip.part"
```

The same split rule applies to the bundled model at
`frontend/public/models/Xenova/e5-small-v2/onnx/model.onnx` — committed as
`model.onnx.partNN`, reassembled by the same script.

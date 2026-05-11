# Graph export

`grag_graph_latest.zip` is a portable JSONL export of the local Neo4j graph. The current archive uses the live cluster dimension names: `topic`, `entities`, `activity`, `temporal`, `evidence`.

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
```

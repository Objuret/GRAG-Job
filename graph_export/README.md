# Graph export

`grag_graph_latest.zip` is a portable JSONL export of the local Neo4j graph.

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

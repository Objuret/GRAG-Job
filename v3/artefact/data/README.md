# herb-eval.dump

Neo4j dump of `herb-eval`, the v1 artefact graph — the one the `artefact_v1` arm
queries (see root `CLAUDE.md`). The native rebuild's graph (`herb-v3`) is a
separate, later build.

Restore on any machine with Neo4j installed:

```
neo4j-admin database load herb-eval --from-path=<dir containing this file>
```

Then start the database and set `NEO4J_URI` / `NEO4J_PASSWORD` for whichever
arm reads it (`pipelines/artefact_v1.py`).
